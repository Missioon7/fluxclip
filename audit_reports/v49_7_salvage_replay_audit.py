import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
AUDIT_DIR = Path(__file__).resolve().parent
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

import pipeline_runner
from v48_asr_chunk_stability_audit import load_segments, safe_float
from v48_candidate_asr_confidence_audit import infer_job_id, read_jsonl


DEFAULT_JOB_ID = "2efbe27a-4f64-41aa-9077-6f483e00fc4f"
DEFAULT_CANDIDATE_FUNNEL = Path("analytics/candidate_funnel.jsonl")
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V49_7_SALVAGE_REPLAY_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v49_7_salvage_replay_audit.json")


def read_json(path, default=None):
    if default is None:
        default = {}
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def find_asr_artifact(job_id):
    exact = Path(f"audit_reports/asr_segments_{job_id}_native_pre_retry.json")
    if exact.exists():
        return exact
    candidates = sorted(
        Path("audit_reports").glob(f"asr_segments_{job_id}*_native_pre_retry.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def selected_window(row):
    if row.get("expanded_start") is not None and row.get("expanded_end") is not None:
        start = safe_float(row.get("expanded_start"))
        end = safe_float(row.get("expanded_end"), start)
        if end > start:
            return round(start, 2), round(end, 2)
    start = safe_float(row.get("start"))
    end = safe_float(row.get("end"), start)
    return round(start, 2), round(end, 2)


def row_semantic_label(row):
    sb = row.get("score_breakdown") if isinstance(row.get("score_breakdown"), dict) else {}
    return (
        row.get("semantic_asr_confidence_label")
        or row.get("semantic_confidence_label")
        or sb.get("semantic_asr_confidence_label")
        or "unknown"
    )


def row_score(row):
    return safe_float(row.get("final_score", row.get("score", 0)))


def replayable_rows(job_id, candidate_funnel_path):
    rows = []
    for row in read_jsonl(candidate_funnel_path):
        if str(row.get("job_id")) != str(job_id):
            continue
        if row.get("final_score") is None:
            continue
        if row.get("filter_decision") not in {"accepted", "accepted_pre_dedupe", "duplicate_removed"}:
            continue
        rows.append(row)
    return rows


def current_final_windows(job_id, clip_intelligence_path):
    windows = set()
    for row in read_jsonl(clip_intelligence_path):
        if str(row.get("job_id")) != str(job_id):
            continue
        if row.get("stage") != "pre_creator_qa":
            continue
        start = round(safe_float(row.get("start")), 2)
        end = round(safe_float(row.get("end"), start), 2)
        windows.add((start, end))
    return windows


def annotate_rows(rows, chunks, current_windows):
    annotated = []
    for row in rows:
        start, end = selected_window(row)
        local_asr = pipeline_runner.v48_candidate_asr_stability(start, end, chunks)
        salvage = pipeline_runner.v49_segment_salvage_decision(
            start,
            end,
            local_asr,
            chunks,
            repaired_window_available=False,
        )
        annotated.append({
            "candidate_index": row.get("candidate_index"),
            "start": start,
            "end": end,
            "final_score": row_score(row),
            "current_finalist": (start, end) in current_windows or row.get("filter_decision") == "accepted",
            "filter_decision": row.get("filter_decision"),
            "filter_reason": row.get("filter_reason"),
            "semantic_confidence_label": row_semantic_label(row),
            "production_local_asr_label": local_asr["local_asr_confidence_label"],
            "production_unstable_overlap_ratio": local_asr["unstable_window_overlap_ratio"],
            "segment_salvage_decision": salvage["segment_salvage_decision"],
            "segment_salvage_reason": salvage["segment_salvage_reason"],
            "quarantined_unstable_windows": salvage["quarantined_unstable_windows"],
            "preview": str(row.get("expanded_preview") or row.get("text_preview") or "")[:180],
        })
    return annotated


def replay_select(annotated, limit=6):
    allowed = [
        row for row in annotated
        if row["segment_salvage_decision"] != "quarantined_unstable"
    ]
    allowed.sort(
        key=lambda row: (
            semantic_rank(row["semantic_confidence_label"]),
            row["final_score"],
        ),
        reverse=True,
    )
    selected = []
    for row in allowed:
        if any(abs(row["start"] - existing["start"]) < 12 for existing in selected):
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def semantic_rank(label):
    if label == "clean_semantics":
        return 3
    if label == "borderline_semantics":
        return 2
    if label == "degraded_semantics":
        return 1
    return 0


def summarize_rows(rows):
    return {
        "total": len(rows),
        "clean": sum(1 for row in rows if row["production_local_asr_label"] == "clean"),
        "borderline": sum(1 for row in rows if row["production_local_asr_label"] == "borderline"),
        "unstable": sum(1 for row in rows if row["production_local_asr_label"] == "unstable"),
        "semantic_labels": dict(Counter(row["semantic_confidence_label"] for row in rows)),
    }


def build_payload(args):
    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")
    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    rows = replayable_rows(args.job_id, args.candidate_funnel)
    current_windows = current_final_windows(args.job_id, args.clip_intelligence)
    annotated = annotate_rows(rows, chunks, current_windows)
    current_finalists = [row for row in annotated if row["current_finalist"]]
    current_quarantined = [
        row for row in current_finalists
        if row["segment_salvage_decision"] == "quarantined_unstable"
    ]
    predicted_finalists = replay_select(annotated)
    current_summary = summarize_rows(current_finalists)
    predicted_summary = summarize_rows(predicted_finalists)
    current_degraded = current_summary["semantic_labels"].get("degraded_semantics", 0)
    predicted_degraded = predicted_summary["semantic_labels"].get("degraded_semantics", 0)
    predicted_unstable_decreases = predicted_summary["unstable"] < current_summary["unstable"]
    semantic_degraded_increases = predicted_degraded > current_degraded

    return {
        "scope": "offline_replay_existing_artifacts_no_video_rerun",
        "job_id": args.job_id,
        "asr_artifact": str(asr_artifact),
        "source_of_truth": [
            "pipeline_runner.v48_build_asr_stability_chunks",
            "pipeline_runner.v48_candidate_asr_stability",
            "pipeline_runner.v49_segment_salvage_decision",
        ],
        "summary": {
            "replayable_candidates": len(annotated),
            "current_finalists": len(current_finalists),
            "current_finalists_quarantined": len(current_quarantined),
            "remaining_clean_or_borderline_candidates": sum(
                1 for row in annotated
                if row["segment_salvage_decision"] != "quarantined_unstable"
                and row["production_local_asr_label"] in {"clean", "borderline"}
            ),
            "predicted_finalists": len(predicted_finalists),
            "predicted_final_clean": predicted_summary["clean"],
            "predicted_final_borderline": predicted_summary["borderline"],
            "predicted_final_unstable": predicted_summary["unstable"],
            "current_final_clean": current_summary["clean"],
            "current_final_borderline": current_summary["borderline"],
            "current_final_unstable": current_summary["unstable"],
            "final_unstable_candidates_decrease": predicted_unstable_decreases,
            "semantic_degraded_finalists_increase": semantic_degraded_increases,
            "video_rerun_justified": predicted_unstable_decreases and not semantic_degraded_increases,
        },
        "current_final_summary": current_summary,
        "predicted_final_summary": predicted_summary,
        "current_finalists_quarantined": current_quarantined,
        "predicted_finalists": predicted_finalists,
        "all_replay_candidates": annotated,
        "regression_risks": [
            "Offline replay approximates production dedupe with start-time dedupe only.",
            "No repaired transcript segments exist yet, so all production-unstable windows are fail-closed.",
            "Quarantine can reduce finalist count if too few clean/borderline candidates survive.",
            "Semantic-degraded but structurally clean windows can still remain; Creator QA remains the final guard.",
        ],
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V49.7 Salvage Replay Audit Report",
        "",
        "Scope: offline replay only. No video rerun, Creator QA relaxation, ASR threshold relaxation, frontend, render, export, or subtitle changes.",
        "",
        "## Summary",
        f"- job_id: {payload['job_id']}",
        f"- replayable candidates: {s['replayable_candidates']}",
        f"- current finalists: {s['current_finalists']}",
        f"- current finalists quarantined: {s['current_finalists_quarantined']}",
        f"- remaining clean/borderline candidates: {s['remaining_clean_or_borderline_candidates']}",
        f"- current final clean/borderline/unstable: {s['current_final_clean']} / {s['current_final_borderline']} / {s['current_final_unstable']}",
        f"- predicted final clean/borderline/unstable: {s['predicted_final_clean']} / {s['predicted_final_borderline']} / {s['predicted_final_unstable']}",
        f"- final unstable candidates decrease: {s['final_unstable_candidates_decrease']}",
        f"- semantic degraded finalists increase: {s['semantic_degraded_finalists_increase']}",
        f"- video rerun justified: {s['video_rerun_justified']}",
        "",
        "## Current Finalists Quarantined",
        "| Candidate | Window | Semantic | Local ASR | Overlap | Reason |",
        "|---:|---|---|---|---:|---|",
    ]
    for row in payload["current_finalists_quarantined"]:
        lines.append(
            f"| {row['candidate_index']} | {row['start']} -> {row['end']} | "
            f"{row['semantic_confidence_label']} | {row['production_local_asr_label']} | "
            f"{row['production_unstable_overlap_ratio']} | {row['segment_salvage_reason']} |"
        )

    lines.extend([
        "",
        "## Predicted Finalists",
        "| Candidate | Window | Score | Semantic | Local ASR | Decision |",
        "|---:|---|---:|---|---|---|",
    ])
    for row in payload["predicted_finalists"]:
        lines.append(
            f"| {row['candidate_index']} | {row['start']} -> {row['end']} | "
            f"{row['final_score']} | {row['semantic_confidence_label']} | "
            f"{row['production_local_asr_label']}:{row['production_unstable_overlap_ratio']} | "
            f"{row['segment_salvage_decision']} |"
        )

    lines.extend([
        "",
        "## Regression Risks",
    ])
    for risk in payload["regression_risks"]:
        lines.append(f"- {risk}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="V49.7 offline segment salvage replay audit")
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID)
    parser.add_argument("--candidate-funnel", default=str(DEFAULT_CANDIDATE_FUNNEL))
    parser.add_argument("--clip-intelligence", default=str(DEFAULT_CLIP_INTELLIGENCE))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()
    args.candidate_funnel = Path(args.candidate_funnel)
    args.clip_intelligence = Path(args.clip_intelligence)

    payload = build_payload(args)
    md_path = Path(args.output_md)
    json_path = Path(args.output_json)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(md_path, payload)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    s = payload["summary"]
    print(f"job_id={payload['job_id']}")
    print(f"current_finalists={s['current_finalists']}")
    print(f"current_finalists_quarantined={s['current_finalists_quarantined']}")
    print(f"remaining_clean_or_borderline_candidates={s['remaining_clean_or_borderline_candidates']}")
    print(f"predicted_final_clean={s['predicted_final_clean']}")
    print(f"predicted_final_borderline={s['predicted_final_borderline']}")
    print(f"predicted_final_unstable={s['predicted_final_unstable']}")
    print(f"semantic_degraded_finalists_increase={s['semantic_degraded_finalists_increase']}")
    print(f"video_rerun_justified={s['video_rerun_justified']}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")


if __name__ == "__main__":
    main()
