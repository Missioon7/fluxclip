import argparse
import json
from pathlib import Path

from v48_asr_chunk_stability_audit import (
    build_asr_chunks,
    load_segments,
    safe_float,
    score_asr_chunk,
    summarize_transcript_stability,
)


DEFAULT_MD_OUT = Path("audit_reports/V48_CANDIDATE_ASR_CONFIDENCE_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v48_candidate_asr_confidence.json")
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_CANDIDATE_FUNNEL = Path("analytics/candidate_funnel.jsonl")
DEFAULT_CREATOR_QA = Path("analytics/creator_qa.jsonl")


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_jsonl(path):
    rows = []
    path = Path(path)
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def infer_job_id(asr_artifact_path):
    payload = read_json(asr_artifact_path)
    job_id = str(payload.get("job_id") or "").strip()
    if job_id:
        return job_id

    stem = Path(asr_artifact_path).stem
    prefix = "asr_segments_"
    suffix = "_native_pre_retry"
    if stem.startswith(prefix):
        stem = stem[len(prefix):]
    if stem.endswith(suffix):
        stem = stem[:-len(suffix)]
    return stem


def find_latest_asr_artifact():
    candidates = sorted(
        Path("audit_reports").glob("asr_segments_*_native_pre_retry.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def overlap_seconds(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def union_overlap_ratio(start, end, windows):
    duration = max(0.01, end - start)
    overlaps = []
    for window in windows:
        overlap = overlap_seconds(start, end, safe_float(window.get("start")), safe_float(window.get("end")))
        if overlap > 0:
            overlaps.append((
                max(start, safe_float(window.get("start"))),
                min(end, safe_float(window.get("end"))),
            ))
    if not overlaps:
        return 0.0

    overlaps.sort()
    merged = []
    for o_start, o_end in overlaps:
        if not merged or o_start > merged[-1][1]:
            merged.append([o_start, o_end])
        else:
            merged[-1][1] = max(merged[-1][1], o_end)
    total = sum(o_end - o_start for o_start, o_end in merged)
    return round(min(1.0, total / duration), 3)


def chunk_intersections(start, end, chunks):
    labels = []
    details = []
    for chunk in chunks:
        c_start = safe_float(chunk.get("chunk_start"))
        c_end = safe_float(chunk.get("chunk_end"))
        overlap = overlap_seconds(start, end, c_start, c_end)
        if overlap <= 0:
            continue
        label = str(chunk.get("stability_label") or "unknown")
        labels.append(label)
        details.append({
            "chunk_start": c_start,
            "chunk_end": c_end,
            "label": label,
            "collapse_score": chunk.get("collapse_score"),
            "overlap_seconds": round(overlap, 2),
        })
    return labels, details


def candidate_start_end(row):
    start = safe_float(row.get("start", row.get("expanded_start")))
    end = safe_float(row.get("end", row.get("expanded_end")))
    if end <= start and row.get("expanded_start") is not None:
        start = safe_float(row.get("expanded_start"))
        end = safe_float(row.get("expanded_end"))
    return start, end


def normalize_candidate(row, source):
    start, end = candidate_start_end(row)
    sb = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
    if not sb:
        sb = {
            key: row.get(key)
            for key in [
                "hook_bonus",
                "payoff_bonus",
                "v43_hinglish_payoff_bonus",
                "v44_semantic_payoff_score",
                "continuation_risk",
                "context_quality",
                "editor_reasons",
                "true_creator_reasons",
                "low_confidence_asr",
            ]
            if key in row
        }
    return {
        "job_id": row.get("job_id"),
        "source": source,
        "stage": row.get("stage"),
        "candidate_index": row.get("candidate_index"),
        "start": round(start, 2),
        "end": round(end, 2),
        "title": row.get("title"),
        "preview": row.get("expanded_preview") or row.get("source_preview") or row.get("text_preview") or row.get("preview"),
        "filter_decision": row.get("filter_decision"),
        "filter_reason": row.get("filter_reason"),
        "score": row.get("score", row.get("final_score", row.get("initial_score"))),
        "score_breakdown": sb,
    }


def load_candidates(job_id, clip_intelligence_path, candidate_funnel_path):
    candidates = []
    for row in read_jsonl(clip_intelligence_path):
        if str(row.get("job_id")) != str(job_id):
            continue
        if row.get("stage") and row.get("stage") != "pre_creator_qa":
            continue
        candidates.append(normalize_candidate(row, "clip_intelligence"))

    if candidates:
        return candidates

    for row in read_jsonl(candidate_funnel_path):
        if str(row.get("job_id")) != str(job_id):
            continue
        if row.get("filter_decision") not in {"accepted", "accepted_pre_dedupe", "duplicate_removed"}:
            continue
        candidates.append(normalize_candidate(row, "candidate_funnel"))
    return candidates


def load_creator_qa_rejections(job_id, path):
    rejections = []
    for row in read_jsonl(path):
        if str(row.get("job_id")) == str(job_id) and row.get("event") == "CREATOR_QA_REJECT":
            rejections.append(row)
    return rejections


def match_rejection(candidate, rejections):
    c_start = safe_float(candidate.get("start"))
    c_end = safe_float(candidate.get("end"))
    best = None
    best_delta = 999999.0
    for row in rejections:
        delta = abs(c_start - safe_float(row.get("start"))) + abs(c_end - safe_float(row.get("end")))
        if delta < best_delta:
            best = row
            best_delta = delta
    return best if best is not None and best_delta <= 2.0 else None


def infer_non_asr_reasons(candidate):
    sb = candidate.get("score_breakdown", {}) if isinstance(candidate.get("score_breakdown"), dict) else {}
    reasons = []
    editor_reasons = sb.get("editor_reasons") if isinstance(sb.get("editor_reasons"), list) else []
    creator_reasons = sb.get("true_creator_reasons") if isinstance(sb.get("true_creator_reasons"), list) else []

    if safe_float(sb.get("payoff_bonus")) == 0 and safe_float(sb.get("hook_bonus")) == 0:
        reasons.append("no_hook_no_payoff")
    if safe_float(sb.get("continuation_risk")) > 0:
        reasons.append("continuation_leakage")
    if "weak_start" in editor_reasons or "weak_creator_start" in creator_reasons:
        reasons.append("weak_start")
    if "weak_ending" in editor_reasons or "weak_creator_ending" in creator_reasons:
        reasons.append("weak_ending")
    if safe_float(sb.get("context_quality")) < 8:
        reasons.append("weak_standalone_context")
    return reasons


def score_candidate_asr(candidate, chunks, retry_windows):
    start = safe_float(candidate.get("start"))
    end = safe_float(candidate.get("end"))
    labels, details = chunk_intersections(start, end, chunks)
    unstable_ratio = union_overlap_ratio(start, end, retry_windows)
    has_unstable = any(label not in {"clean", "borderline"} for label in labels)
    has_borderline = "borderline" in labels

    if unstable_ratio >= 0.2:
        local_label = "unstable"
        local_low_confidence = True
        reasons = [f"unstable_window_overlap_ratio={unstable_ratio}"]
    elif unstable_ratio > 0 or has_unstable:
        local_label = "borderline"
        local_low_confidence = False
        reasons = [f"minor_unstable_overlap_ratio={unstable_ratio}"]
    elif has_borderline:
        local_label = "borderline"
        local_low_confidence = False
        reasons = ["borderline_chunk_overlap"]
    elif labels:
        local_label = "clean"
        local_low_confidence = False
        reasons = []
    else:
        local_label = "unknown"
        local_low_confidence = True
        reasons = ["no_overlapping_asr_chunks"]

    confidence_score = max(0, min(100, int(round(100 - (unstable_ratio * 100)))))
    if local_label == "borderline":
        confidence_score = min(confidence_score, 74)
    if local_low_confidence:
        confidence_score = min(confidence_score, 49)

    return {
        "overlapping_chunk_labels": sorted(set(labels)),
        "overlapping_chunks": details,
        "unstable_window_overlap_ratio": unstable_ratio,
        "local_asr_confidence_label": local_label,
        "local_low_confidence_asr": local_low_confidence,
        "local_asr_reasons": reasons,
        "chunk_confidence_score": confidence_score,
    }


def analyze_candidates(candidates, chunks, retry_windows, rejections):
    rows = []
    for candidate in candidates:
        asr = score_candidate_asr(candidate, chunks, retry_windows)
        rejection = match_rejection(candidate, rejections)
        qa_reasons = []
        if rejection and isinstance(rejection.get("reasons"), list):
            qa_reasons = [str(reason) for reason in rejection.get("reasons")]
        else:
            qa_reasons = infer_non_asr_reasons(candidate)
            if candidate.get("score_breakdown", {}).get("low_confidence_asr") is True:
                qa_reasons.insert(0, "asr_low_confidence")

        non_asr_reasons = [reason for reason in qa_reasons if reason != "asr_low_confidence"]
        global_asr_only = "asr_low_confidence" in qa_reasons and not non_asr_reasons
        locally_salvageable = (
            global_asr_only
            and asr["local_low_confidence_asr"] is False
            and asr["local_asr_confidence_label"] in {"clean", "borderline"}
        )

        rows.append({
            **candidate,
            **asr,
            "creator_qa_reasons": qa_reasons,
            "non_asr_rejection_reasons": non_asr_reasons,
            "would_fail_only_because_global_low_confidence_asr": global_asr_only,
            "locally_salvageable_from_global_asr_gate": locally_salvageable,
        })
    return rows


def summarize(rows, chunk_summary, job_id, asr_artifact):
    locally_clean = sum(1 for row in rows if row["local_asr_confidence_label"] == "clean")
    locally_borderline = sum(1 for row in rows if row["local_asr_confidence_label"] == "borderline")
    locally_unstable = sum(1 for row in rows if row["local_low_confidence_asr"] is True)
    global_asr_only = sum(1 for row in rows if row["would_fail_only_because_global_low_confidence_asr"])
    salvageable = sum(1 for row in rows if row["locally_salvageable_from_global_asr_gate"])
    overlap_patterns = {}
    for row in rows:
        key = "+".join(row["overlapping_chunk_labels"]) or "none"
        overlap_patterns[key] = overlap_patterns.get(key, 0) + 1
    return {
        "job_id": job_id,
        "asr_artifact": str(asr_artifact),
        "total_candidates": len(rows),
        "candidates_rejected_only_due_to_global_asr": global_asr_only,
        "locally_clean_candidates": locally_clean,
        "locally_borderline_candidates": locally_borderline,
        "candidates_overlapping_unstable_windows": locally_unstable,
        "locally_salvageable_from_global_asr_gate": salvageable,
        "top_overlap_patterns": [
            {"pattern": key, "count": count}
            for key, count in sorted(overlap_patterns.items(), key=lambda item: item[1], reverse=True)[:8]
        ],
        "chunk_summary": chunk_summary,
    }


def write_json_report(path, summary, rows):
    payload = {
        "summary": summary,
        "candidates": rows,
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown_report(path, summary, rows):
    lines = [
        "# V48 Candidate ASR Confidence Report",
        "",
        "Scope: offline diagnostics only. No production ASR, Creator QA, render, export, or frontend behavior changed.",
        "",
        "## Summary",
        f"- job_id: {summary['job_id']}",
        f"- asr_artifact: {summary['asr_artifact']}",
        f"- total candidates: {summary['total_candidates']}",
        f"- candidates rejected only due to global ASR: {summary['candidates_rejected_only_due_to_global_asr']}",
        f"- locally clean candidates: {summary['locally_clean_candidates']}",
        f"- locally borderline candidates: {summary['locally_borderline_candidates']}",
        f"- candidates overlapping unstable windows: {summary['candidates_overlapping_unstable_windows']}",
        f"- locally salvageable from global ASR gate: {summary['locally_salvageable_from_global_asr_gate']}",
        "",
        "## Chunk Context",
        f"- total chunks: {summary['chunk_summary'].get('total_chunks')}",
        f"- clean chunks: {summary['chunk_summary'].get('clean_chunks')}",
        f"- borderline chunks: {summary['chunk_summary'].get('borderline_chunks')}",
        f"- unstable chunks: {summary['chunk_summary'].get('unstable_chunks')}",
        "",
        "## Top Overlap Patterns",
    ]
    if summary["top_overlap_patterns"]:
        for item in summary["top_overlap_patterns"]:
            lines.append(f"- {item['pattern']}: {item['count']}")
    else:
        lines.append("- none")

    lines.extend([
        "",
        "## Candidate Table",
        "| # | Window | Local ASR | Unstable Ratio | Score | QA Reasons | Global-ASR Only | Salvageable | Preview |",
        "|---|---:|---|---:|---:|---|---|---|---|",
    ])
    for idx, row in enumerate(rows, 1):
        preview = str(row.get("preview") or "").replace("\n", " ").replace("|", "/")[:110]
        qa_reasons = ", ".join(row.get("creator_qa_reasons") or [])
        lines.append(
            f"| {idx} | {row['start']} -> {row['end']} | "
            f"{row['local_asr_confidence_label']} | "
            f"{row['unstable_window_overlap_ratio']} | "
            f"{row.get('chunk_confidence_score')} | "
            f"{qa_reasons or 'none'} | "
            f"{row['would_fail_only_because_global_low_confidence_asr']} | "
            f"{row['locally_salvageable_from_global_asr_gate']} | "
            f"{preview} |"
        )

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Offline V48 candidate-local ASR confidence audit")
    parser.add_argument("--asr-artifact", help="audit_reports/asr_segments_<job_id>_native_pre_retry.json")
    parser.add_argument("--job-id", help="Candidate analytics job id. Defaults to ASR artifact job_id.")
    parser.add_argument("--clip-intelligence", default=str(DEFAULT_CLIP_INTELLIGENCE))
    parser.add_argument("--candidate-funnel", default=str(DEFAULT_CANDIDATE_FUNNEL))
    parser.add_argument("--creator-qa", default=str(DEFAULT_CREATOR_QA))
    parser.add_argument("--chunk-size", type=float, default=120.0)
    parser.add_argument("--overlap", type=float, default=10.0)
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()

    asr_artifact = Path(args.asr_artifact) if args.asr_artifact else find_latest_asr_artifact()
    if not asr_artifact:
        raise SystemExit("No native pre-retry ASR artifact found.")

    job_id = args.job_id or infer_job_id(asr_artifact)
    _, segments = load_segments(asr_artifact)
    chunks = build_asr_chunks(segments, chunk_size=args.chunk_size, overlap=args.overlap)
    scored_chunks = [score_asr_chunk(chunk) for chunk in chunks]
    chunk_summary = summarize_transcript_stability(scored_chunks)

    candidates = load_candidates(job_id, args.clip_intelligence, args.candidate_funnel)
    rejections = load_creator_qa_rejections(job_id, args.creator_qa)
    rows = analyze_candidates(candidates, scored_chunks, chunk_summary["retry_recommended_windows"], rejections)
    summary = summarize(rows, chunk_summary, job_id, asr_artifact)

    md_path = Path(args.output_md)
    json_path = Path(args.output_json)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown_report(md_path, summary, rows)
    write_json_report(json_path, summary, rows)

    print(f"job_id={job_id}")
    print(f"asr_artifact={asr_artifact}")
    print(f"segments={len(segments)} chunks={len(scored_chunks)} candidates={len(rows)}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")
    print(
        "summary "
        f"global_asr_only={summary['candidates_rejected_only_due_to_global_asr']} "
        f"locally_clean={summary['locally_clean_candidates']} "
        f"local_unstable={summary['candidates_overlapping_unstable_windows']} "
        f"salvageable={summary['locally_salvageable_from_global_asr_gate']}"
    )


if __name__ == "__main__":
    main()
