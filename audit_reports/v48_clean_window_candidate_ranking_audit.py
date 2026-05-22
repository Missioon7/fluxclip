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
from v48_candidate_asr_confidence_audit import (
    find_latest_asr_artifact,
    infer_job_id,
    overlap_seconds,
    read_json,
    read_jsonl,
    union_overlap_ratio,
)


DEFAULT_CHUNK_REPORT = Path("audit_reports/v48_asr_chunk_stability.json")
DEFAULT_CANDIDATE_FUNNEL = Path("analytics/candidate_funnel.jsonl")
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_CREATOR_QA = Path("analytics/creator_qa.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V48_CLEAN_WINDOW_CANDIDATE_RANKING_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v48_clean_window_candidate_ranking.json")


def candidate_preview(row):
    return (
        row.get("expanded_preview")
        or row.get("source_preview")
        or row.get("text_preview")
        or row.get("preview")
        or ""
    )


def row_window(row, prefer_expanded=True):
    if prefer_expanded and row.get("expanded_start") is not None and row.get("expanded_end") is not None:
        start = safe_float(row.get("expanded_start"))
        end = safe_float(row.get("expanded_end"))
        if end > start:
            return round(start, 2), round(end, 2), "expanded"
    start = safe_float(row.get("start"))
    end = safe_float(row.get("end"))
    return round(start, 2), round(end, 2), "source"


def chunk_labels_for_window(start, end, chunks):
    labels = []
    overlaps = []
    for chunk in chunks:
        c_start = safe_float(chunk.get("chunk_start"))
        c_end = safe_float(chunk.get("chunk_end"))
        overlap = overlap_seconds(start, end, c_start, c_end)
        if overlap <= 0:
            continue
        label = str(chunk.get("stability_label") or "unknown")
        labels.append(label)
        overlaps.append({
            "chunk_start": c_start,
            "chunk_end": c_end,
            "label": label,
            "collapse_score": chunk.get("collapse_score"),
            "overlap_seconds": round(overlap, 2),
        })
    return labels, overlaps


def classify_region(start, end, chunks, retry_windows):
    labels, overlaps = chunk_labels_for_window(start, end, chunks)
    unstable_ratio = union_overlap_ratio(start, end, retry_windows)
    if not labels:
        region = "unknown"
    elif unstable_ratio >= 0.2 or any(label not in {"clean", "borderline"} for label in labels):
        region = "unstable"
    elif "borderline" in labels or unstable_ratio > 0:
        region = "borderline"
    else:
        region = "clean"
    return {
        "region": region,
        "labels": sorted(set(labels)),
        "unstable_overlap_ratio": unstable_ratio,
        "overlaps": overlaps,
    }


def load_chunks(asr_artifact, chunk_report_path, chunk_size, overlap):
    report = read_json(chunk_report_path)
    if report.get("chunks"):
        return report.get("chunks"), report.get("summary", {})

    _, segments = load_segments(asr_artifact)
    chunks = [score_asr_chunk(chunk) for chunk in build_asr_chunks(segments, chunk_size=chunk_size, overlap=overlap)]
    return chunks, summarize_transcript_stability(chunks)


def load_funnel_rows(job_id, path):
    return [
        row for row in read_jsonl(path)
        if str(row.get("job_id")) == str(job_id)
    ]


def load_final_rows(job_id, path):
    return [
        row for row in read_jsonl(path)
        if str(row.get("job_id")) == str(job_id) and row.get("stage") == "pre_creator_qa"
    ]


def load_creator_qa_summary(job_id, path):
    rejects = []
    zero_safe = None
    for row in read_jsonl(path):
        if str(row.get("job_id")) != str(job_id):
            continue
        if row.get("event") == "CREATOR_QA_REJECT":
            rejects.append(row)
        elif row.get("event") == "CREATOR_QA_ZERO_SAFE_CLIPS":
            zero_safe = row
    return rejects, zero_safe


def final_window_keys(final_rows):
    keys = set()
    for row in final_rows:
        start = round(safe_float(row.get("start")), 1)
        end = round(safe_float(row.get("end")), 1)
        keys.add((start, end))
    return keys


def annotate_funnel_rows(rows, chunks, retry_windows, final_keys):
    annotated = []
    for row in rows:
        selected_start, selected_end, selected_basis = row_window(row, prefer_expanded=True)
        source_start, source_end, _ = row_window(row, prefer_expanded=False)
        selected_region = classify_region(selected_start, selected_end, chunks, retry_windows)
        source_region = classify_region(source_start, source_end, chunks, retry_windows)
        filter_decision = str(row.get("filter_decision") or "unknown")
        final_selected = (
            filter_decision == "accepted"
            or (round(selected_start, 1), round(selected_end, 1)) in final_keys
            or (round(source_start, 1), round(source_end, 1)) in final_keys
        )
        annotated.append({
            "candidate_index": row.get("candidate_index"),
            "source_start": source_start,
            "source_end": source_end,
            "selected_start": selected_start,
            "selected_end": selected_end,
            "selected_window_basis": selected_basis,
            "initial_score": row.get("initial_score"),
            "final_score": row.get("final_score"),
            "filter_decision": filter_decision,
            "filter_reason": row.get("filter_reason"),
            "selected_region": selected_region["region"],
            "selected_chunk_labels": selected_region["labels"],
            "selected_unstable_overlap_ratio": selected_region["unstable_overlap_ratio"],
            "source_region": source_region["region"],
            "source_chunk_labels": source_region["labels"],
            "source_unstable_overlap_ratio": source_region["unstable_overlap_ratio"],
            "final_selected": final_selected,
            "payoff_bonus": row.get("payoff_bonus"),
            "v43_hinglish_payoff_bonus": row.get("v43_hinglish_payoff_bonus"),
            "v44_semantic_payoff_score": row.get("v44_semantic_payoff_score"),
            "continuation_risk": row.get("continuation_risk"),
            "context_quality": row.get("context_quality"),
            "story_completeness_estimate": row.get("story_completeness_estimate"),
            "preview": candidate_preview(row),
        })
    return annotated


def annotate_final_rows(rows, chunks, retry_windows, qa_rejects):
    annotated = []
    for row in rows:
        start = safe_float(row.get("start"))
        end = safe_float(row.get("end"))
        region = classify_region(start, end, chunks, retry_windows)
        best_reasons = []
        best_delta = 999999.0
        for reject in qa_rejects:
            delta = abs(start - safe_float(reject.get("start"))) + abs(end - safe_float(reject.get("end")))
            if delta < best_delta:
                best_delta = delta
                best_reasons = reject.get("reasons", [])
        if best_delta > 2.0:
            best_reasons = []
        sb = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
        annotated.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "score": row.get("score"),
            "region": region["region"],
            "chunk_labels": region["labels"],
            "unstable_overlap_ratio": region["unstable_overlap_ratio"],
            "creator_qa_reasons": best_reasons,
            "payoff_bonus": sb.get("payoff_bonus"),
            "v44_semantic_payoff_score": sb.get("v44_semantic_payoff_score"),
            "context_quality": sb.get("context_quality"),
            "preview": candidate_preview(row),
        })
    return annotated


def counts_by(items, key):
    counts = {}
    for item in items:
        value = item.get(key, "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def lost_clean_reasons(rows):
    clean_rows = [row for row in rows if row["selected_region"] == "clean"]
    lost = [row for row in clean_rows if not row["final_selected"]]
    reason_counts = counts_by(lost, "filter_decision")
    detail_counts = counts_by(lost, "filter_reason")
    return clean_rows, lost, reason_counts, detail_counts


def build_recommendation(summary):
    if summary["clean_window_candidates"] <= 0:
        return "No clean-window candidates were generated; next patch should add clean-window candidate discovery diagnostics before ranking changes."
    if summary["final_selected_clean_candidates"] <= 0 and summary["clean_window_candidates"] > 0:
        return (
            "Evidence supports diagnostics-first ASR stability ranking: add local ASR confidence to score_breakdown "
            "and apply a conservative unstable-window penalty before final dedupe. Do not loosen Creator QA."
        )
    if summary["final_selected_unstable_candidates"] > summary["final_selected_clean_candidates"]:
        return (
            "Evidence supports a conservative unstable-window ranking penalty or clean-window tie-breaker, "
            "with Creator QA unchanged."
        )
    return "No production ranking patch is justified from this run alone."


def summarize(job_id, asr_artifact, chunk_summary, funnel_rows, final_rows, zero_safe):
    clean_rows, lost_clean, lost_filter_counts, lost_reason_counts = lost_clean_reasons(funnel_rows)
    summary = {
        "job_id": job_id,
        "asr_artifact": str(asr_artifact),
        "chunk_summary": chunk_summary,
        "clean_windows": chunk_summary.get("preserved_clean_regions", []),
        "unstable_windows": chunk_summary.get("retry_recommended_windows", []),
        "total_funnel_candidates": len(funnel_rows),
        "clean_window_candidates": len(clean_rows),
        "unstable_window_candidates": sum(1 for row in funnel_rows if row["selected_region"] == "unstable"),
        "borderline_window_candidates": sum(1 for row in funnel_rows if row["selected_region"] == "borderline"),
        "final_selected_candidates": len(final_rows),
        "final_selected_clean_candidates": sum(1 for row in final_rows if row["region"] == "clean"),
        "final_selected_unstable_candidates": sum(1 for row in final_rows if row["region"] == "unstable"),
        "lost_clean_window_candidates": len(lost_clean),
        "lost_clean_filter_decisions": lost_filter_counts,
        "lost_clean_filter_reasons": lost_reason_counts,
        "funnel_candidates_by_region": counts_by(funnel_rows, "selected_region"),
        "final_candidates_by_region": counts_by(final_rows, "region"),
        "creator_qa_zero_safe": zero_safe or {},
    }
    summary["recommended_minimal_patch"] = build_recommendation(summary)
    return summary


def write_json_report(path, summary, funnel_rows, final_rows):
    payload = {
        "summary": summary,
        "funnel_candidates": funnel_rows,
        "final_candidates": final_rows,
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def short_text(text, limit=120):
    text = str(text or "").replace("\n", " ").replace("|", "/").strip()
    return text[:limit]


def write_markdown_report(path, summary, funnel_rows, final_rows):
    lines = [
        "# V48 Clean Window Candidate Ranking Report",
        "",
        "Scope: offline diagnostics only. No production ranking, Creator QA, ASR, render, export, frontend, or subtitle behavior changed.",
        "",
        "## Summary",
        f"- job_id: {summary['job_id']}",
        f"- asr_artifact: {summary['asr_artifact']}",
        f"- total funnel candidates: {summary['total_funnel_candidates']}",
        f"- clean-window candidates: {summary['clean_window_candidates']}",
        f"- unstable-window candidates: {summary['unstable_window_candidates']}",
        f"- final selected candidates: {summary['final_selected_candidates']}",
        f"- final selected clean candidates: {summary['final_selected_clean_candidates']}",
        f"- final selected unstable candidates: {summary['final_selected_unstable_candidates']}",
        f"- lost clean-window candidates: {summary['lost_clean_window_candidates']}",
        "",
        "## Clean Windows",
    ]
    for window in summary["clean_windows"]:
        lines.append(f"- {window.get('start')} -> {window.get('end')}")
    if not summary["clean_windows"]:
        lines.append("- none")

    lines.extend(["", "## Unstable / Retry Windows"])
    for window in summary["unstable_windows"]:
        lines.append(f"- {window.get('start')} -> {window.get('end')}")
    if not summary["unstable_windows"]:
        lines.append("- none")

    lines.extend([
        "",
        "## Candidate Distribution",
        f"- funnel by region: {summary['funnel_candidates_by_region']}",
        f"- final by region: {summary['final_candidates_by_region']}",
        f"- lost clean filter decisions: {summary['lost_clean_filter_decisions']}",
        f"- lost clean filter reasons: {summary['lost_clean_filter_reasons']}",
        "",
        "## Recommendation",
        summary["recommended_minimal_patch"],
        "",
        "## Funnel Candidates",
        "| # | Region | Window | Initial | Final | Decision | Reason | Unstable Ratio | Preview |",
        "|---|---|---:|---:|---:|---|---|---:|---|",
    ])
    for row in funnel_rows:
        lines.append(
            f"| {row.get('candidate_index')} | {row['selected_region']} | "
            f"{row['selected_start']} -> {row['selected_end']} | "
            f"{row.get('initial_score')} | {row.get('final_score')} | "
            f"{row.get('filter_decision')} | {row.get('filter_reason')} | "
            f"{row.get('selected_unstable_overlap_ratio')} | {short_text(row.get('preview'))} |"
        )

    lines.extend([
        "",
        "## Final Pre-Creator-QA Candidates",
        "| # | Region | Window | Score | QA Reasons | Unstable Ratio | Preview |",
        "|---|---|---:|---:|---|---:|---|",
    ])
    for idx, row in enumerate(final_rows, 1):
        reasons = ", ".join(str(r) for r in row.get("creator_qa_reasons", []))
        lines.append(
            f"| {idx} | {row['region']} | {row['start']} -> {row['end']} | "
            f"{row.get('score')} | {reasons or 'none'} | "
            f"{row.get('unstable_overlap_ratio')} | {short_text(row.get('preview'))} |"
        )

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Offline V48 clean-window candidate ranking audit")
    parser.add_argument("--asr-artifact", help="audit_reports/asr_segments_<job_id>_native_pre_retry.json")
    parser.add_argument("--job-id")
    parser.add_argument("--chunk-report", default=str(DEFAULT_CHUNK_REPORT))
    parser.add_argument("--candidate-funnel", default=str(DEFAULT_CANDIDATE_FUNNEL))
    parser.add_argument("--clip-intelligence", default=str(DEFAULT_CLIP_INTELLIGENCE))
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

    chunks, chunk_summary = load_chunks(asr_artifact, args.chunk_report, args.chunk_size, args.overlap)
    retry_windows = chunk_summary.get("retry_recommended_windows", [])
    funnel_rows = load_funnel_rows(job_id, args.candidate_funnel)
    final_raw_rows = load_final_rows(job_id, args.clip_intelligence)
    qa_rejects, zero_safe = load_creator_qa_summary(job_id, args.creator_qa)

    final_keys = final_window_keys(final_raw_rows)
    annotated_funnel = annotate_funnel_rows(funnel_rows, chunks, retry_windows, final_keys)
    annotated_final = annotate_final_rows(final_raw_rows, chunks, retry_windows, qa_rejects)
    summary = summarize(job_id, asr_artifact, chunk_summary, annotated_funnel, annotated_final, zero_safe)

    md_path = Path(args.output_md)
    json_path = Path(args.output_json)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown_report(md_path, summary, annotated_funnel, annotated_final)
    write_json_report(json_path, summary, annotated_funnel, annotated_final)

    print(f"job_id={job_id}")
    print(f"asr_artifact={asr_artifact}")
    print(f"funnel_candidates={len(annotated_funnel)} final_candidates={len(annotated_final)}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")
    print(
        "summary "
        f"clean_funnel={summary['clean_window_candidates']} "
        f"unstable_funnel={summary['unstable_window_candidates']} "
        f"final_clean={summary['final_selected_clean_candidates']} "
        f"final_unstable={summary['final_selected_unstable_candidates']} "
        f"lost_clean={summary['lost_clean_window_candidates']}"
    )


if __name__ == "__main__":
    main()
