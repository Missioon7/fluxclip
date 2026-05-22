import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


DIAGNOSTIC_FIELDS = [
    "setup_strength",
    "payoff_strength",
    "continuation_risk",
    "context_density",
    "story_completeness_estimate",
]

SCORE_FIELDS = [
    "v40_narrative_score",
    "natural_editor_score",
    "true_creator_score",
    "context_quality",
    "payoff_bonus",
]

LIST_FIELDS = [
    "v40_narrative_reasons",
    "editor_reasons",
    "true_creator_reasons",
    "creator_qa_metadata_reasons",
]


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_jsonl(path):
    path = Path(path)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                yield {
                    "_parse_error": str(exc),
                    "_line_no": line_no,
                    "_raw_preview": line[:180],
                }


def as_number(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_list(value):
    return value if isinstance(value, list) else []


def preview(text, limit=140):
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def extract_result_clips(data):
    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        data = data["result"]
    if isinstance(data, dict) and isinstance(data.get("clips"), list):
        return data["clips"]
    if isinstance(data, dict) and isinstance(data.get("final_clips"), list):
        return data["final_clips"]
    if isinstance(data, list):
        return data
    return []


def load_clips_from_result(path, job_id=None):
    data = load_json(path)
    clips = extract_result_clips(data)
    rows = []
    for clip in clips:
        if not isinstance(clip, dict):
            continue
        row = dict(clip)
        row.setdefault("stage", "result_json")
        if job_id:
            row.setdefault("job_id", job_id)
        rows.append(row)
    return rows


def load_clips_from_log(path, job_id=None, stage=None):
    rows = []
    for row in iter_jsonl(path):
        if not isinstance(row, dict) or row.get("_parse_error"):
            continue
        if job_id and str(row.get("job_id")) != str(job_id):
            continue
        if stage and str(row.get("stage")) != str(stage):
            continue
        rows.append(row)
    return rows


def load_creator_qa(path, job_id=None):
    if not path:
        return []
    rows = []
    for row in iter_jsonl(path):
        if not isinstance(row, dict) or row.get("_parse_error"):
            continue
        if job_id and str(row.get("job_id")) != str(job_id):
            continue
        rows.append(row)
    return rows


def score_breakdown(row):
    sb = row.get("score_breakdown")
    return sb if isinstance(sb, dict) else {}


def average(values):
    values = [as_number(v) for v in values if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def field_stats(clips, field):
    values = []
    missing = 0
    for clip in clips:
        sb = score_breakdown(clip)
        if field not in sb:
            missing += 1
        else:
            values.append(sb.get(field))
    nums = [as_number(v) for v in values if isinstance(v, (int, float))]
    return {
        "present": len(values),
        "missing": missing,
        "avg": average(nums),
        "min": round(min(nums), 2) if nums else None,
        "max": round(max(nums), 2) if nums else None,
    }


def collect_reason_counts(clips):
    counters = {field: Counter() for field in LIST_FIELDS}
    for clip in clips:
        sb = score_breakdown(clip)
        for field in LIST_FIELDS:
            counters[field].update(str(x) for x in safe_list(sb.get(field)))
    return counters


def classify_clip_gaps(clip):
    sb = score_breakdown(clip)
    gaps = []

    if "setup_strength" in sb and as_number(sb.get("setup_strength")) < 8:
        gaps.append("weak_setup")
    if "payoff_strength" in sb and as_number(sb.get("payoff_strength")) < 8:
        gaps.append("weak_payoff")
    if "continuation_risk" in sb and as_number(sb.get("continuation_risk")) >= 24:
        gaps.append("continuation_risk")
    if "story_completeness_estimate" in sb and as_number(sb.get("story_completeness_estimate")) < 18:
        gaps.append("incomplete_story")
    if sb.get("context_density") == "overextended":
        gaps.append("overextended_context")
    if "weak_start" in safe_list(sb.get("editor_reasons")):
        gaps.append("editor_weak_start")
    if "weak_ending" in safe_list(sb.get("editor_reasons")):
        gaps.append("editor_weak_ending")
    if "weak_creator_start" in safe_list(sb.get("true_creator_reasons")):
        gaps.append("creator_weak_start")
    if "weak_creator_ending" in safe_list(sb.get("true_creator_reasons")):
        gaps.append("creator_weak_ending")
    if sb.get("low_confidence_asr") is True:
        gaps.append("low_confidence_asr")

    return gaps


def v40_impact(clips):
    impact = {
        "clips_with_v40_score": 0,
        "story_editor_ok": 0,
        "v40_reason_counts": Counter(),
        "avg_v40_score": None,
    }
    scores = []
    for clip in clips:
        sb = score_breakdown(clip)
        if "v40_narrative_score" in sb:
            impact["clips_with_v40_score"] += 1
            scores.append(sb.get("v40_narrative_score"))
        if sb.get("story_editor_ok") is True:
            impact["story_editor_ok"] += 1
        impact["v40_reason_counts"].update(str(x) for x in safe_list(sb.get("v40_narrative_reasons")))
    impact["avg_v40_score"] = average(scores)
    return impact


def summarize_creator_qa(rows):
    events = Counter(str(row.get("event", "unknown")) for row in rows)
    rejection_reasons = Counter()
    metadata_reasons = Counter()
    for row in rows:
        rejection_reasons.update(str(x) for x in safe_list(row.get("reasons")))
        metadata_reasons.update(str(x) for x in safe_list(row.get("metadata_reasons")))
    return {
        "events": events,
        "rejection_reasons": rejection_reasons,
        "metadata_reasons": metadata_reasons,
    }


def build_report(clips, qa_rows, source_label):
    gap_counts = Counter()
    by_clip = []
    niche_counts = Counter()
    stage_counts = Counter()
    missing_by_field = defaultdict(int)

    for index, clip in enumerate(clips, 1):
        sb = score_breakdown(clip)
        gaps = classify_clip_gaps(clip)
        gap_counts.update(gaps)
        niche_counts.update([str(clip.get("niche") or sb.get("detected_niche") or "unknown")])
        stage_counts.update([str(clip.get("stage") or "unknown")])
        for field in DIAGNOSTIC_FIELDS:
            if field not in sb:
                missing_by_field[field] += 1
        by_clip.append({
            "index": index,
            "title": clip.get("title") or f"clip_{index}",
            "start": clip.get("start"),
            "end": clip.get("end"),
            "score": clip.get("score"),
            "gaps": gaps,
            "diagnostics": {field: sb.get(field) for field in DIAGNOSTIC_FIELDS if field in sb},
            "preview": preview(clip.get("expanded_preview") or clip.get("expanded_text") or clip.get("source_preview") or clip.get("source_text")),
        })

    reason_counts = collect_reason_counts(clips)
    impact = v40_impact(clips)
    qa_summary = summarize_creator_qa(qa_rows)

    return {
        "source": source_label,
        "clip_count": len(clips),
        "stage_counts": stage_counts,
        "niche_counts": niche_counts,
        "diagnostic_field_stats": {
            field: field_stats(clips, field)
            for field in DIAGNOSTIC_FIELDS + SCORE_FIELDS
        },
        "missing_diagnostics": dict(missing_by_field),
        "reason_counts": reason_counts,
        "v40_impact": impact,
        "gap_counts": gap_counts,
        "creator_qa": qa_summary,
        "clips": by_clip,
    }


def format_counter(counter, limit=8):
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counter.most_common(limit))


def format_report(report):
    lines = []
    lines.append("# Editorial Validation Report")
    lines.append("")
    lines.append(f"Source: {report['source']}")
    lines.append(f"Clip count: {report['clip_count']}")
    lines.append(f"Stages: {format_counter(report['stage_counts'])}")
    lines.append(f"Niches: {format_counter(report['niche_counts'])}")
    lines.append("")

    lines.append("## Diagnostic Coverage")
    for field, stats in report["diagnostic_field_stats"].items():
        lines.append(
            f"- {field}: present={stats['present']} missing={stats['missing']} "
            f"avg={stats['avg']} min={stats['min']} max={stats['max']}"
        )
    lines.append("")

    lines.append("## Editorial Gaps")
    lines.append(f"- Remaining gap counts: {format_counter(report['gap_counts'])}")
    lines.append(f"- V40 narrative reasons: {format_counter(report['v40_impact']['v40_reason_counts'])}")
    lines.append(
        "- V40 impact signals: "
        f"clips_with_v40_score={report['v40_impact']['clips_with_v40_score']} "
        f"story_editor_ok={report['v40_impact']['story_editor_ok']} "
        f"avg_v40_score={report['v40_impact']['avg_v40_score']}"
    )
    lines.append("")

    lines.append("## Reason Signals")
    for field, counter in report["reason_counts"].items():
        lines.append(f"- {field}: {format_counter(counter)}")
    lines.append("")

    lines.append("## Creator QA")
    qa = report["creator_qa"]
    lines.append(f"- Events: {format_counter(qa['events'])}")
    lines.append(f"- Rejection reasons: {format_counter(qa['rejection_reasons'])}")
    lines.append(f"- Metadata reasons: {format_counter(qa['metadata_reasons'])}")
    lines.append("")

    lines.append("## Clip Review")
    for clip in report["clips"]:
        gap_text = ", ".join(clip["gaps"]) if clip["gaps"] else "none"
        diag_text = ", ".join(f"{k}={v}" for k, v in clip["diagnostics"].items()) or "no diagnostics"
        lines.append(
            f"- #{clip['index']} {clip['title']} "
            f"start={clip['start']} end={clip['end']} score={clip['score']} "
            f"gaps={gap_text} diagnostics=({diag_text})"
        )
        if clip["preview"]:
            lines.append(f"  preview: {clip['preview']}")

    lines.append("")
    lines.append("## Interpretation Guide")
    lines.append("- High continuation_risk means the clip may still start or end mid-thought.")
    lines.append("- Low setup_strength means the viewer may lack setup before the hook.")
    lines.append("- Low payoff_strength means the clip may not resolve or land cleanly.")
    lines.append("- Low story_completeness_estimate means the clip needs boundary repair or better ASR before export.")
    lines.append("- Missing diagnostics usually means the job was produced before the guarded V40/editorial diagnostics patch.")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Read completed FluxClip job JSON or analytics logs and summarize editorial diagnostics."
    )
    parser.add_argument("--result-json", help="Path to a completed job result JSON.")
    parser.add_argument("--clip-log", default="analytics/clip_intelligence.jsonl", help="Path to clip_intelligence.jsonl.")
    parser.add_argument("--creator-qa-log", default="analytics/creator_qa.jsonl", help="Path to creator_qa.jsonl.")
    parser.add_argument("--job-id", help="Filter analytics logs to one job id.")
    parser.add_argument("--stage", help="Filter clip analytics stage, for example completed or pre_export.")
    parser.add_argument("--output", help="Optional report output path.")
    args = parser.parse_args()

    clips = []
    source_parts = []
    if args.result_json:
        clips.extend(load_clips_from_result(args.result_json, args.job_id))
        source_parts.append(f"result_json={args.result_json}")
    else:
        clips.extend(load_clips_from_log(args.clip_log, args.job_id, args.stage))
        source_parts.append(f"clip_log={args.clip_log}")

    qa_rows = load_creator_qa(args.creator_qa_log, args.job_id)
    if args.job_id:
        source_parts.append(f"job_id={args.job_id}")
    if args.stage:
        source_parts.append(f"stage={args.stage}")

    report = build_report(clips, qa_rows, " ".join(source_parts))
    text = format_report(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        print(f"EDITORIAL_VALIDATION_REPORT_WRITTEN {output_path}")
    else:
        print(text)


if __name__ == "__main__":
    main()
