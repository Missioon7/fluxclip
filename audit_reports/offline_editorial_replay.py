import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import pipeline_runner as editorial
except Exception as exc:  # pragma: no cover - explicit fallback report path
    editorial = None
    EDITORIAL_IMPORT_ERROR = str(exc)
else:
    EDITORIAL_IMPORT_ERROR = None


DEFAULT_JOB_IDS = [
    "e0926df0-8fdb-4441-9d95-af58ba1a3ec5",
    "5fb7dd32-fe17-4b6b-9c0e-01ac2b8ac3a3",
    "ac65f75c-9f61-4ecd-8593-2c6a8918c41f",
]


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
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                yield {"_parse_error": str(exc), "_line_no": line_no}
                continue
            if isinstance(row, dict):
                yield row


def safe_float(value, default=0.0):
    if editorial is not None:
        return editorial.safe_float(value, default)
    try:
        return round(float(value), 2)
    except Exception:
        return default


def safe_list(value):
    return value if isinstance(value, list) else []


def score_breakdown(row):
    sb = row.get("score_breakdown")
    return sb if isinstance(sb, dict) else {}


def clip_key(row):
    return (
        str(row.get("job_id", "")),
        round(safe_float(row.get("start")), 2),
        round(safe_float(row.get("end")), 2),
    )


def text_for_clip(row):
    return str(
        row.get("expanded_text")
        or row.get("expanded_preview")
        or row.get("source_text")
        or row.get("source_preview")
        or ""
    ).strip()


def preview(text, limit=170):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def word_set(text):
    if editorial is not None:
        return editorial._v8_word_set(text)
    stop = {
        "the", "and", "but", "this", "that", "with", "from", "what",
        "when", "where", "why", "how", "you", "your", "will", "would",
    }
    words = []
    for word in str(text or "").lower().replace(",", " ").replace(".", " ").split():
        word = "".join(ch for ch in word if ch.isalnum())
        if len(word) >= 4 and word not in stop:
            words.append(word)
    return set(words)


def replay_payoff(row):
    text = text_for_clip(row)
    sb = score_breakdown(row)

    if editorial is None:
        stored = safe_float(sb.get("payoff_bonus"))
        return {
            "stored_payoff_bonus": stored,
            "stored_payoff_strength": safe_float(sb.get("payoff_strength")),
            "replayed_payoff_bonus": stored,
            "replayed_v43_bonus": safe_float(sb.get("v43_hinglish_payoff_bonus")),
            "replayed_v43_reasons": safe_list(sb.get("v43_hinglish_payoff_reasons")),
            "delta_payoff_bonus": 0.0,
            "import_fallback": True,
        }

    v43_bonus, v43_reasons = editorial.v43_hinglish_payoff_bonus(text)
    v44_bonus, v44_reasons, v44_confidence = editorial.v44_semantic_payoff_score(text)
    if editorial.v44_payoff_quality_block(text):
        replayed = 0
    else:
        replayed = max(
            editorial.v6_payoff_bonus(text),
            editorial.v7_better_payoff_bonus(text),
            v43_bonus,
            v44_bonus,
        )
    stored = safe_float(sb.get("payoff_bonus"))
    return {
        "stored_payoff_bonus": stored,
        "stored_payoff_strength": safe_float(sb.get("payoff_strength")),
        "stored_v43_bonus": safe_float(sb.get("v43_hinglish_payoff_bonus")),
        "stored_v43_reasons": safe_list(sb.get("v43_hinglish_payoff_reasons")),
        "stored_v44_score": safe_float(sb.get("v44_semantic_payoff_score")),
        "stored_v44_reasons": safe_list(sb.get("v44_semantic_payoff_reasons")),
        "stored_v44_confidence": sb.get("v44_semantic_payoff_confidence"),
        "replayed_payoff_bonus": safe_float(replayed),
        "replayed_v43_bonus": safe_float(v43_bonus),
        "replayed_v43_reasons": v43_reasons,
        "replayed_v44_score": safe_float(v44_bonus),
        "replayed_v44_reasons": v44_reasons,
        "replayed_v44_confidence": v44_confidence,
        "delta_payoff_bonus": safe_float(replayed) - stored,
    }


def replay_continuation(row):
    sb = score_breakdown(row)
    text = text_for_clip(row)
    start_text = str(sb.get("start_text") or text).strip()
    end_text = str(sb.get("end_text") or text).strip()

    if editorial is None:
        return {
            "stored_continuation_risk": safe_float(sb.get("continuation_risk")),
            "replayed_continuation_risk": safe_float(sb.get("continuation_risk")),
            "stored_story_completeness": safe_float(sb.get("story_completeness_estimate")),
            "replayed_story_completeness": safe_float(sb.get("story_completeness_estimate")),
            "import_fallback": True,
        }

    diagnostics = editorial.v41_story_diagnostics(
        text,
        start_text,
        end_text,
        safe_float(sb.get("context_quality")),
        replay_payoff(row)["replayed_payoff_bonus"],
        safe_list(sb.get("editor_reasons")),
        safe_list(sb.get("true_creator_reasons")),
        safe_float(sb.get("v40_narrative_score")),
        safe_list(sb.get("v40_narrative_reasons")),
        safe_float(sb.get("v6_arc_bonus")),
    )
    return {
        "stored_continuation_risk": safe_float(sb.get("continuation_risk")),
        "replayed_continuation_risk": safe_float(diagnostics.get("continuation_risk")),
        "stored_story_completeness": safe_float(sb.get("story_completeness_estimate")),
        "replayed_story_completeness": safe_float(diagnostics.get("story_completeness_estimate")),
        "stored_context_density": sb.get("context_density"),
        "replayed_context_density": diagnostics.get("context_density"),
    }


def replay_creator_qa(row, payoff=None):
    sb = score_breakdown(row)
    text = text_for_clip(row)
    replay_sb = dict(sb)
    if payoff is not None:
        replay_sb["payoff_bonus"] = payoff.get("replayed_payoff_bonus", sb.get("payoff_bonus"))
        replay_sb["v43_hinglish_payoff_bonus"] = payoff.get("replayed_v43_bonus", sb.get("v43_hinglish_payoff_bonus"))
        replay_sb["v43_hinglish_payoff_reasons"] = payoff.get("replayed_v43_reasons", sb.get("v43_hinglish_payoff_reasons"))
        replay_sb["v44_semantic_payoff_score"] = payoff.get("replayed_v44_score")
        replay_sb["v44_semantic_payoff_reasons"] = payoff.get("replayed_v44_reasons")
        replay_sb["v44_semantic_payoff_confidence"] = payoff.get("replayed_v44_confidence")
    clip = {
        "job_id": row.get("job_id"),
        "start": row.get("start"),
        "end": row.get("end"),
        "title": row.get("title"),
        "expanded_text": text,
        "source_text": row.get("source_text") or row.get("source_preview"),
        "score_breakdown": replay_sb,
    }
    if editorial is None:
        reasons = []
        if sb.get("low_confidence_asr") is True:
            reasons.append("asr_low_confidence")
        if safe_float(sb.get("payoff_bonus")) == 0 and safe_float(sb.get("hook_bonus")) == 0:
            reasons.append("no_hook_no_payoff")
        if safe_float(sb.get("context_quality")) < 8 or len(word_set(text)) < 6:
            reasons.append("weak_standalone_context")
        metadata = []
    else:
        reasons = editorial.creator_qa_rejection_reasons(clip, captions=[])
        metadata = editorial.creator_qa_metadata_reasons(clip)
    return {
        "decision": "reject" if reasons else "approve",
        "reasons": reasons,
        "metadata_reasons": metadata,
    }


def load_clip_rows(path, job_ids, stage=None):
    rows = []
    wanted = set(job_ids or [])
    for row in iter_jsonl(path):
        if row.get("_parse_error"):
            continue
        if wanted and str(row.get("job_id")) not in wanted:
            continue
        if stage and str(row.get("stage")) != stage:
            continue
        rows.append(row)
    return rows


def load_creator_qa_rows(path, job_ids):
    rows = []
    wanted = set(job_ids or [])
    for row in iter_jsonl(path):
        if row.get("_parse_error"):
            continue
        if wanted and str(row.get("job_id")) not in wanted:
            continue
        rows.append(row)
    return rows


def previous_qa_by_clip(qa_rows):
    by_key = {}
    zero_safe = defaultdict(list)
    for row in qa_rows:
        event = row.get("event")
        if event == "CREATOR_QA_REJECT":
            by_key[clip_key(row)] = row
        elif event == "CREATOR_QA_ZERO_SAFE_CLIPS":
            zero_safe[str(row.get("job_id"))].append(row)
    return by_key, zero_safe


def compare_reasons(old, new):
    old_set = set(safe_list(old))
    new_set = set(safe_list(new))
    return {
        "added": sorted(new_set - old_set),
        "removed": sorted(old_set - new_set),
        "same": sorted(old_set & new_set),
        "changed": old_set != new_set,
    }


def scan_incomplete_runs(log_dir, job_ids, rows_by_job, qa_zero_by_job):
    wanted = set(job_ids or [])
    started = defaultdict(lambda: {
        "upload_seen": False,
        "asr_started": False,
        "asr_completed": False,
        "qa_seen": False,
        "files": set(),
    })
    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        re.IGNORECASE,
    )
    for path in Path(log_dir).glob("*.log"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ids = set(uuid_pattern.findall(text))
        if wanted:
            ids &= wanted
        for job_id in ids:
            info = started[job_id]
            info["files"].add(str(path))
            job_text = "\n".join(line for line in text.splitlines() if job_id in line or "ASR" in line or "CREATOR_QA" in line)
            info["upload_seen"] = info["upload_seen"] or f"/upload/{job_id}" in text
            info["asr_started"] = info["asr_started"] or "ASR START" in job_text or "ASR_INPUT_PATH" in job_text
            info["asr_completed"] = info["asr_completed"] or "ASR COMPLETE" in job_text or "ASR_RESULT" in job_text
            info["qa_seen"] = info["qa_seen"] or "CREATOR_QA_REJECT" in job_text or "CREATOR_QA_ZERO_SAFE_CLIPS" in job_text

    incomplete = []
    for job_id, info in sorted(started.items()):
        has_clip_rows = bool(rows_by_job.get(job_id))
        has_zero = bool(qa_zero_by_job.get(job_id))
        if info["upload_seen"] and (not has_clip_rows or not has_zero or not info["qa_seen"]):
            incomplete.append({
                "job_id": job_id,
                "upload_seen": info["upload_seen"],
                "asr_started": info["asr_started"],
                "asr_completed": info["asr_completed"],
                "creator_qa_seen_in_logs": info["qa_seen"],
                "analytics_rows": len(rows_by_job.get(job_id, [])),
                "zero_safe_rows": len(qa_zero_by_job.get(job_id, [])),
                "files": sorted(info["files"]),
            })
    return incomplete


def build_regression(clips, qa_rows, job_ids, log_dir):
    old_qa_by_key, zero_safe = previous_qa_by_clip(qa_rows)
    rows_by_job = defaultdict(list)
    for clip in clips:
        rows_by_job[str(clip.get("job_id"))].append(clip)

    comparisons = []
    counters = Counter()
    false_positive_candidates = []

    for row in clips:
        sb = score_breakdown(row)
        payoff = replay_payoff(row)
        continuation = replay_continuation(row)
        replayed_qa = replay_creator_qa(row, payoff)
        old_qa = old_qa_by_key.get(clip_key(row))
        old_decision = "reject" if old_qa else "unknown"
        if old_decision == "unknown" and row.get("stage") in {"pre_export", "completed"}:
            old_decision = "approve"

        reason_delta = compare_reasons(
            safe_list(old_qa.get("reasons")) if old_qa else [],
            replayed_qa["reasons"],
        )
        qa_changed = old_decision != replayed_qa["decision"] or reason_delta["changed"]

        if qa_changed:
            counters["qa_changed"] += 1
        if payoff["delta_payoff_bonus"] != 0:
            counters["payoff_changed"] += 1
        if continuation["stored_continuation_risk"] != continuation["replayed_continuation_risk"]:
            counters["continuation_changed"] += 1
        if old_decision == "reject" and replayed_qa["decision"] == "approve":
            counters["possible_false_positive_release"] += 1
            false_positive_candidates.append(row)
        if old_decision == "approve" and replayed_qa["decision"] == "reject":
            counters["possible_new_rejection"] += 1

        comparisons.append({
            "job_id": row.get("job_id"),
            "stage": row.get("stage"),
            "start": row.get("start"),
            "end": row.get("end"),
            "title": row.get("title"),
            "old_decision": old_decision,
            "replayed_decision": replayed_qa["decision"],
            "old_reasons": safe_list(old_qa.get("reasons")) if old_qa else [],
            "replayed_reasons": replayed_qa["reasons"],
            "reason_delta": reason_delta,
            "qa_changed": qa_changed,
            "payoff": payoff,
            "continuation": continuation,
            "low_confidence_asr": sb.get("low_confidence_asr"),
            "preview": preview(text_for_clip(row)),
        })

    incomplete = scan_incomplete_runs(log_dir, job_ids, rows_by_job, zero_safe)
    expected_rejected = sum(1 for row in qa_rows if row.get("event") == "CREATOR_QA_REJECT")
    replay_rejected = sum(1 for c in comparisons if c["replayed_decision"] == "reject")
    return {
        "import_error": EDITORIAL_IMPORT_ERROR,
        "job_ids": job_ids,
        "clip_count": len(clips),
        "qa_row_count": len(qa_rows),
        "expected_rejected": expected_rejected,
        "replay_rejected": replay_rejected,
        "summary": dict(counters),
        "comparisons": comparisons,
        "false_positive_candidates": [
            {
                "job_id": row.get("job_id"),
                "start": row.get("start"),
                "end": row.get("end"),
                "title": row.get("title"),
                "preview": preview(text_for_clip(row)),
            }
            for row in false_positive_candidates
        ],
        "incomplete_runs": incomplete,
    }


def format_counter(mapping):
    if not mapping:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(mapping.items()))


def format_report(report):
    lines = [
        "# Offline Editorial Replay Report",
        "",
        "Scope: analytics/creator QA replay only. No video, ASR, FFmpeg, export, or server execution.",
        f"Jobs: {', '.join(report['job_ids']) if report['job_ids'] else 'all'}",
        f"Clip fixtures: {report['clip_count']}",
        f"Creator QA rows: {report['qa_row_count']}",
        f"Historical rejects: {report['expected_rejected']}",
        f"Replayed rejects: {report['replay_rejected']}",
        f"Regression counters: {format_counter(report['summary'])}",
    ]
    if report.get("import_error"):
        lines.append(f"Editorial import fallback: {report['import_error']}")
    lines.extend(["", "## Before/After Payoff"])
    for item in report["comparisons"]:
        payoff = item["payoff"]
        if payoff.get("delta_payoff_bonus") == 0:
            continue
        lines.append(
            f"- {item['job_id']} {item['start']}->{item['end']}: "
            f"payoff_bonus {payoff.get('stored_payoff_bonus')} -> "
            f"{payoff.get('replayed_payoff_bonus')} "
            f"v43 {payoff.get('stored_v43_bonus')} -> {payoff.get('replayed_v43_bonus')} "
            f"v44 {payoff.get('stored_v44_score')} -> {payoff.get('replayed_v44_score')} "
            f"confidence={payoff.get('replayed_v44_confidence')}"
        )
    if not any(item["payoff"].get("delta_payoff_bonus") != 0 for item in report["comparisons"]):
        lines.append("- No payoff deltas detected.")

    lines.extend(["", "## QA Decision Comparison"])
    changed = [item for item in report["comparisons"] if item["qa_changed"]]
    if not changed:
        lines.append("- No QA decision/reason regressions detected.")
    for item in changed:
        delta = item["reason_delta"]
        lines.append(
            f"- {item['job_id']} {item['start']}->{item['end']}: "
            f"{item['old_decision']} {item['old_reasons']} -> "
            f"{item['replayed_decision']} {item['replayed_reasons']} "
            f"added={delta['added']} removed={delta['removed']}"
        )

    lines.extend(["", "## Continuation Risk"])
    continuation_changed = [
        item for item in report["comparisons"]
        if item["continuation"]["stored_continuation_risk"]
        != item["continuation"]["replayed_continuation_risk"]
    ]
    if not continuation_changed:
        lines.append("- No continuation-risk deltas detected.")
    for item in continuation_changed:
        cont = item["continuation"]
        lines.append(
            f"- {item['job_id']} {item['start']}->{item['end']}: "
            f"risk {cont['stored_continuation_risk']} -> {cont['replayed_continuation_risk']}, "
            f"story {cont['stored_story_completeness']} -> {cont['replayed_story_completeness']}"
        )

    lines.extend(["", "## False Positive Watch"])
    if not report["false_positive_candidates"]:
        lines.append("- No historically rejected clip would be approved by offline replay.")
    for item in report["false_positive_candidates"]:
        lines.append(
            f"- {item['job_id']} {item['start']}->{item['end']} {item['title']}: {item['preview']}"
        )

    lines.extend(["", "## Interrupted/Incomplete Runs"])
    if not report["incomplete_runs"]:
        lines.append("- No incomplete runs detected for the selected jobs.")
    for item in report["incomplete_runs"]:
        lines.append(
            f"- {item['job_id']}: upload={item['upload_seen']} asr_started={item['asr_started']} "
            f"asr_completed={item['asr_completed']} qa_log={item['creator_qa_seen_in_logs']} "
            f"analytics_rows={item['analytics_rows']} zero_safe_rows={item['zero_safe_rows']}"
        )

    lines.extend(["", "## Fixture Detail"])
    for item in report["comparisons"]:
        lines.append(
            f"- {item['job_id']} {item['stage']} {item['start']}->{item['end']} "
            f"old={item['old_decision']} replay={item['replayed_decision']} "
            f"payoff={item['payoff']['stored_payoff_bonus']}->{item['payoff']['replayed_payoff_bonus']} "
            f"continuation={item['continuation']['stored_continuation_risk']}->{item['continuation']['replayed_continuation_risk']}"
        )

    return "\n".join(lines) + "\n"


def write_outputs(report, output_md, output_json):
    output_md = Path(output_md)
    output_json = Path(output_json)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(format_report(report), encoding="utf-8")
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Replay FluxClip editorial decisions offline from saved analytics fixtures."
    )
    parser.add_argument("--clip-log", default="analytics/clip_intelligence.jsonl")
    parser.add_argument("--creator-qa-log", default="analytics/creator_qa.jsonl")
    parser.add_argument("--log-dir", default="audit_reports")
    parser.add_argument("--job-id", action="append", dest="job_ids")
    parser.add_argument("--all-jobs", action="store_true")
    parser.add_argument("--stage", default="pre_creator_qa")
    parser.add_argument("--output-md", default="audit_reports/OFFLINE_EDITORIAL_REPLAY_REPORT.md")
    parser.add_argument("--output-json", default="audit_reports/offline_editorial_replay_report.json")
    args = parser.parse_args()

    job_ids = [] if args.all_jobs else (args.job_ids or DEFAULT_JOB_IDS)
    clips = load_clip_rows(args.clip_log, job_ids, stage=args.stage)
    qa_rows = load_creator_qa_rows(args.creator_qa_log, job_ids)
    report = build_regression(clips, qa_rows, job_ids, args.log_dir)
    write_outputs(report, args.output_md, args.output_json)
    print(f"OFFLINE_EDITORIAL_REPLAY_REPORT_WRITTEN {args.output_md}")
    print(f"OFFLINE_EDITORIAL_REPLAY_JSON_WRITTEN {args.output_json}")
    if report["summary"].get("possible_false_positive_release"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
