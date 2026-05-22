import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
AUDIT_DIR = Path(__file__).resolve().parent
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

import pipeline_runner
import v48_semantic_asr_confidence_audit as semantic_audit
from v48_asr_chunk_stability_audit import load_segments, safe_float
from v48_candidate_asr_confidence_audit import infer_job_id, read_jsonl


DEFAULT_JOB_ID = "2efbe27a-4f64-41aa-9077-6f483e00fc4f"
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V49_ASR_STABILITY_PARITY_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v49_asr_stability_parity.json")


def find_asr_artifact(job_id):
    exact = Path(f"audit_reports/asr_segments_{job_id}_native_pre_retry.json")
    if exact.exists():
        return exact
    candidates = sorted(
        Path("audit_reports").glob(f"asr_segments_{job_id}*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_final_clip_rows(job_id, path):
    rows = []
    for row in read_jsonl(path):
        if str(row.get("job_id")) == str(job_id) and row.get("stage") == "pre_creator_qa":
            rows.append(row)
    return rows


def audit_candidate_asr_stability(start, end, audit_chunks):
    structural = semantic_audit.compute_structural_label({}, start, end, audit_chunks)
    return {
        "local_asr_confidence_label": structural["structural_local_asr_label"],
        "unstable_window_overlap_ratio": structural["structural_unstable_overlap_ratio"],
        "chunk_confidence_score": structural["structural_chunk_confidence_score"],
        "overlapping_chunks": structural["structural_overlapping_chunks"],
    }


def production_overlapping_chunks(start, end, production_chunks):
    details = []
    for chunk in production_chunks:
        c_start = safe_float(chunk.get("start"))
        c_end = safe_float(chunk.get("end"))
        overlap_start = max(start, c_start)
        overlap_end = min(end, c_end)
        if overlap_end <= overlap_start:
            continue
        details.append({
            "start": c_start,
            "end": c_end,
            "label": chunk.get("label"),
            "collapse_score": chunk.get("collapse_score"),
            "overlap_seconds": round(overlap_end - overlap_start, 2),
        })
    return details


def classify_mismatch(row, prod_logged, prod_recomputed, audit_recomputed):
    if prod_logged["label"] != prod_recomputed["local_asr_confidence_label"]:
        return "production_logged_vs_recomputed_mismatch"
    if prod_logged["ratio"] != prod_recomputed["unstable_window_overlap_ratio"]:
        return "production_logged_ratio_vs_recomputed_ratio_mismatch"
    if prod_recomputed["local_asr_confidence_label"] != audit_recomputed["local_asr_confidence_label"]:
        return "audit_classifier_differs_from_production_classifier"
    if prod_recomputed["unstable_window_overlap_ratio"] != audit_recomputed["unstable_window_overlap_ratio"]:
        return "audit_retry_window_overlap_differs_from_production_unstable_overlap"
    return "matched"


def summarize(rows):
    label_mismatches = [row for row in rows if row["production_recomputed_label"] != row["audit_recomputed_label"]]
    ratio_mismatches = [
        row for row in rows
        if row["production_recomputed_unstable_window_overlap_ratio"] != row["audit_recomputed_unstable_window_overlap_ratio"]
    ]
    logged_mismatches = [
        row for row in rows
        if row["production_logged_label"] != row["production_recomputed_label"]
        or row["production_logged_unstable_window_overlap_ratio"] != row["production_recomputed_unstable_window_overlap_ratio"]
    ]
    reason_counts = {}
    for row in rows:
        reason = row["mismatch_reason_guess"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {
        "total_final_candidates": len(rows),
        "production_logged_vs_recomputed_mismatches": len(logged_mismatches),
        "production_vs_audit_label_mismatches": len(label_mismatches),
        "production_vs_audit_ratio_mismatches": len(ratio_mismatches),
        "mismatch_reason_counts": reason_counts,
    }


def write_markdown(path, payload):
    summary = payload["summary"]
    lines = [
        "# V49 ASR Stability Parity Report",
        "",
        "Scope: offline audit only. No production, Creator QA, frontend, render, export, subtitle, or video rerun changes.",
        "",
        "## Summary",
        f"- job_id: {summary['job_id']}",
        f"- asr_artifact: {summary['asr_artifact']}",
        f"- production chunk size/overlap: {summary['production_chunk_size']} / {summary['production_chunk_overlap']}",
        f"- audit chunk size/overlap: {summary['audit_chunk_size']} / {summary['audit_chunk_overlap']}",
        f"- total final candidates: {summary['total_final_candidates']}",
        f"- production logged vs recomputed mismatches: {summary['production_logged_vs_recomputed_mismatches']}",
        f"- production vs audit label mismatches: {summary['production_vs_audit_label_mismatches']}",
        f"- production vs audit ratio mismatches: {summary['production_vs_audit_ratio_mismatches']}",
        f"- mismatch reasons: {summary['mismatch_reason_counts']}",
        "",
        "## Root Cause",
        payload["root_cause"],
        "",
        "## Candidate Parity",
        "| # | Window | Prod Logged | Prod Recomputed | Audit Recomputed | Prod Ratio | Audit Ratio | Reason |",
        "|---:|---|---|---|---|---:|---:|---|",
    ]
    for idx, row in enumerate(payload["candidates"], 1):
        lines.append(
            f"| {idx} | {row['start']} -> {row['end']} | "
            f"{row['production_logged_label']} | {row['production_recomputed_label']} | "
            f"{row['audit_recomputed_label']} | "
            f"{row['production_recomputed_unstable_window_overlap_ratio']} | "
            f"{row['audit_recomputed_unstable_window_overlap_ratio']} | "
            f"{row['mismatch_reason_guess']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Offline V49 ASR stability production/audit parity audit")
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID)
    parser.add_argument("--clip-intelligence", default=str(DEFAULT_CLIP_INTELLIGENCE))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()

    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")

    _, segments = load_segments(asr_artifact)
    production_chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    audit_chunks, _, _ = semantic_audit.load_chunks(
        asr_artifact,
        None,
        pipeline_runner.V48_ASR_STABILITY_CHUNK_SIZE,
        pipeline_runner.V48_ASR_STABILITY_CHUNK_OVERLAP,
        args.job_id,
    )
    final_rows = load_final_clip_rows(args.job_id, args.clip_intelligence)

    rows = []
    for row in final_rows:
        start = safe_float(row.get("start"))
        end = safe_float(row.get("end"))
        score_breakdown = row.get("score_breakdown") if isinstance(row.get("score_breakdown"), dict) else {}
        prod_logged = {
            "label": str(score_breakdown.get("local_asr_confidence_label") or "missing"),
            "ratio": safe_float(score_breakdown.get("unstable_window_overlap_ratio")),
            "score": score_breakdown.get("chunk_confidence_score"),
        }
        prod_recomputed = pipeline_runner.v48_candidate_asr_stability(start, end, production_chunks)
        audit_recomputed = audit_candidate_asr_stability(start, end, audit_chunks)
        reason = classify_mismatch(row, prod_logged, prod_recomputed, audit_recomputed)

        rows.append({
            "candidate_funnel_index": score_breakdown.get("candidate_funnel_index"),
            "start": round(start, 2),
            "end": round(end, 2),
            "expanded_start": row.get("expanded_start"),
            "expanded_end": row.get("expanded_end"),
            "production_logged_label": prod_logged["label"],
            "production_logged_unstable_window_overlap_ratio": prod_logged["ratio"],
            "production_logged_chunk_confidence_score": prod_logged["score"],
            "production_recomputed_label": prod_recomputed["local_asr_confidence_label"],
            "production_recomputed_unstable_window_overlap_ratio": prod_recomputed["unstable_window_overlap_ratio"],
            "production_recomputed_chunk_confidence_score": prod_recomputed["chunk_confidence_score"],
            "production_recomputed_reasons": prod_recomputed["local_asr_reasons"],
            "audit_recomputed_label": audit_recomputed["local_asr_confidence_label"],
            "audit_recomputed_unstable_window_overlap_ratio": audit_recomputed["unstable_window_overlap_ratio"],
            "audit_recomputed_chunk_confidence_score": audit_recomputed["chunk_confidence_score"],
            "mismatch_reason_guess": reason,
            "production_overlapping_chunks": production_overlapping_chunks(start, end, production_chunks),
            "audit_overlapping_chunks": audit_recomputed["overlapping_chunks"],
        })

    summary = summarize(rows)
    summary.update({
        "job_id": args.job_id or infer_job_id(asr_artifact),
        "asr_artifact": str(asr_artifact),
        "production_chunk_size": pipeline_runner.V48_ASR_STABILITY_CHUNK_SIZE,
        "production_chunk_overlap": pipeline_runner.V48_ASR_STABILITY_CHUNK_OVERLAP,
        "audit_chunk_size": pipeline_runner.V48_ASR_STABILITY_CHUNK_SIZE,
        "audit_chunk_overlap": pipeline_runner.V48_ASR_STABILITY_CHUNK_OVERLAP,
        "production_chunk_label_counts": count_labels(production_chunks, "label"),
        "audit_chunk_label_counts": count_labels(audit_chunks, "label"),
    })

    root_cause = (
        "Semantic ASR audit local stability now uses the canonical production helpers. Historical mismatches "
        "came from audit_reports/v48_asr_chunk_stability_audit.py using audit-only metrics such as content-token "
        "filtering and different replacement-character accounting. This parity check compares production "
        "score_breakdown against the patched semantic audit path."
    )
    payload = {
        "summary": summary,
        "root_cause": root_cause,
        "candidates": rows,
    }

    md_path = Path(args.output_md)
    json_path = Path(args.output_json)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(md_path, payload)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"job_id={summary['job_id']}")
    print(f"asr_artifact={summary['asr_artifact']}")
    print(f"final_candidates={summary['total_final_candidates']}")
    print(f"production_logged_vs_recomputed_mismatches={summary['production_logged_vs_recomputed_mismatches']}")
    print(f"production_vs_audit_label_mismatches={summary['production_vs_audit_label_mismatches']}")
    print(f"production_vs_audit_ratio_mismatches={summary['production_vs_audit_ratio_mismatches']}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")


def count_labels(chunks, key):
    counts = {}
    for chunk in chunks:
        label = str(chunk.get(key) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


if __name__ == "__main__":
    main()
