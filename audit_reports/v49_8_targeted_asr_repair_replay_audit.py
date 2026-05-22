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
DEFAULT_MD_OUT = Path("audit_reports/V49_8_TARGETED_ASR_REPAIR_REPLAY_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v49_8_targeted_asr_repair_replay_audit.json")


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


def row_text(row, semantic_row=None):
    semantic_row = semantic_row if isinstance(semantic_row, dict) else {}
    return str(
        semantic_row.get("preview_text")
        or row.get("expanded_preview")
        or row.get("source_preview")
        or row.get("text_preview")
        or row.get("preview")
        or ""
    )


def row_semantic_label(row, semantic_row=None):
    semantic_row = semantic_row if isinstance(semantic_row, dict) else {}
    sb = row.get("score_breakdown") if isinstance(row.get("score_breakdown"), dict) else {}
    return (
        semantic_row.get("semantic_confidence_label")
        or row.get("semantic_asr_confidence_label")
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


def load_semantic_candidate_map(job_id):
    payload = read_json("audit_reports/v48_semantic_asr_confidence.json", {})
    if payload.get("summary", {}).get("job_id") != job_id:
        return {}
    result = {}
    for row in payload.get("candidates", []):
        result[row.get("candidate_index")] = row
    return result


def annotate_rows(rows, chunks, current_windows, semantic_map):
    annotated = []
    for row in rows:
        semantic_row = semantic_map.get(row.get("candidate_index"), {})
        start, end = selected_window(row)
        local_asr = pipeline_runner.v48_candidate_asr_stability(start, end, chunks)
        salvage = pipeline_runner.v49_segment_salvage_decision(
            start,
            end,
            local_asr,
            chunks,
            repaired_window_available=False,
        )
        repair = pipeline_runner.v49_8_targeted_asr_repair(row_text(row, semantic_row), local_asr)
        annotated.append({
            "candidate_index": row.get("candidate_index"),
            "start": start,
            "end": end,
            "final_score": row_score(row),
            "current_finalist": (start, end) in current_windows or row.get("filter_decision") == "accepted",
            "filter_decision": row.get("filter_decision"),
            "semantic_confidence_label": row_semantic_label(row, semantic_row),
            "production_local_asr_label": local_asr["local_asr_confidence_label"],
            "production_unstable_overlap_ratio": local_asr["unstable_window_overlap_ratio"],
            "segment_salvage_decision": salvage["segment_salvage_decision"],
            "quarantined_unstable_windows": salvage["quarantined_unstable_windows"],
            **repair,
        })
    return annotated


def replay_select(annotated, limit=6):
    allowed = [
        row for row in annotated
        if row["segment_salvage_decision"] != "quarantined_unstable"
    ]
    allowed.sort(key=lambda row: (row["final_score"], row["start"]), reverse=True)
    selected = []
    for row in allowed:
        if any(abs(row["start"] - existing["start"]) < 12 for existing in selected):
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def summarize_rows(rows):
    return {
        "total": len(rows),
        "clean": sum(1 for row in rows if row["production_local_asr_label"] == "clean"),
        "borderline": sum(1 for row in rows if row["production_local_asr_label"] == "borderline"),
        "unstable": sum(1 for row in rows if row["production_local_asr_label"] == "unstable"),
        "semantic_labels": dict(Counter(row["semantic_confidence_label"] for row in rows)),
    }


def replacement_counter(rows):
    counter = Counter()
    for row in rows:
        for replacement in row.get("v49_8_repair_replacements", []):
            counter[f"{replacement['pattern']} -> {replacement['replacement']}"] += replacement["count"]
    return dict(counter.most_common())


def build_payload(args):
    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")
    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    rows = replayable_rows(args.job_id, args.candidate_funnel)
    current_windows = current_final_windows(args.job_id, args.clip_intelligence)
    semantic_map = load_semantic_candidate_map(args.job_id)
    annotated = annotate_rows(rows, chunks, current_windows, semantic_map)
    current_finalists = [row for row in annotated if row["current_finalist"]]
    quarantined = [
        row for row in current_finalists
        if row["segment_salvage_decision"] == "quarantined_unstable"
    ]
    repair_attempted = [row for row in annotated if row["v49_8_repair_attempted"]]
    repair_improved = [row for row in repair_attempted if row["v49_8_repair_improved"]]
    repair_label_improved = [
        row for row in repair_attempted
        if row["v49_8_repair_before_label"] != row["v49_8_repair_after_label"]
    ]
    export_safe_repairs = [row for row in repair_attempted if row["v49_8_repair_export_safe"]]
    repaired_available = [row for row in repair_attempted if row["v49_8_repaired_window_available"]]
    predicted_finalists = replay_select(annotated)
    predicted_summary = summarize_rows(predicted_finalists)
    current_summary = summarize_rows(current_finalists)
    degraded_before = sum(
        1 for row in repair_attempted
        if row["v49_8_repair_before_label"] == "degraded_semantics"
    )
    degraded_after = sum(
        1 for row in repair_attempted
        if row["v49_8_repair_after_label"] == "degraded_semantics"
    )

    return {
        "scope": "offline_targeted_unstable_window_repair_replay_no_video_rerun",
        "job_id": args.job_id,
        "asr_artifact": str(asr_artifact),
        "source_of_truth": [
            "pipeline_runner.v48_build_asr_stability_chunks",
            "pipeline_runner.v48_candidate_asr_stability",
            "pipeline_runner.v49_segment_salvage_decision",
            "pipeline_runner.v49_8_targeted_asr_repair",
        ],
        "summary": {
            "replayable_candidates": len(annotated),
            "current_finalists": len(current_finalists),
            "current_finalists_quarantined": len(quarantined),
            "repair_attempted_unstable_candidates": len(repair_attempted),
            "repair_improved_candidates": len(repair_improved),
            "repair_label_improved_candidates": len(repair_label_improved),
            "repair_export_safe_candidates": len(export_safe_repairs),
            "repaired_window_available_candidates": len(repaired_available),
            "degraded_before_repair": degraded_before,
            "degraded_after_repair": degraded_after,
            "current_final_clean": current_summary["clean"],
            "current_final_unstable": current_summary["unstable"],
            "predicted_final_clean": predicted_summary["clean"],
            "predicted_final_unstable": predicted_summary["unstable"],
            "semantic_degraded_finalists_increase": (
                predicted_summary["semantic_labels"].get("degraded_semantics", 0)
                > current_summary["semantic_labels"].get("degraded_semantics", 0)
            ),
            "unstable_garbage_export_risk": len(export_safe_repairs) > 0,
            "production_behavior": "fail_closed_metadata_only",
        },
        "corruption_patterns": replacement_counter(repair_attempted),
        "current_finalists_quarantined": quarantined,
        "repair_improved_candidates": repair_improved,
        "repair_label_improved_candidates": repair_label_improved,
        "predicted_finalists_after_fail_closed_repair": predicted_finalists,
        "all_candidates": annotated,
        "design": {
            "scope": "Only call repair for production local_asr_confidence_label=unstable.",
            "normalization_steps": [
                "remove replacement characters",
                "collapse repeated token runs",
                "collapse extreme repeated Devanagari characters",
                "replace narrow known corrupt Hindi/Hinglish terms",
            ],
            "safety": [
                "does not relax ASR stability thresholds",
                "does not set repaired_window_available without audio-backed repair",
                "does not substitute export text",
                "does not change Creator QA",
                "does not touch frontend/render/export/subtitle",
            ],
        },
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V49.8 Targeted ASR Repair Replay Audit Report",
        "",
        "Scope: offline replay only. The repair layer is targeted to production-unstable windows and remains fail-closed: it does not mark repaired windows available, does not substitute export text, and does not alter Creator QA.",
        "",
        "## Summary",
        f"- job_id: {payload['job_id']}",
        f"- replayable candidates: {s['replayable_candidates']}",
        f"- current finalists quarantined: {s['current_finalists_quarantined']}",
        f"- repair attempted unstable candidates: {s['repair_attempted_unstable_candidates']}",
        f"- repair improved candidates: {s['repair_improved_candidates']}",
        f"- repair label improved candidates: {s['repair_label_improved_candidates']}",
        f"- degraded before/after repair: {s['degraded_before_repair']} / {s['degraded_after_repair']}",
        f"- repaired window available candidates: {s['repaired_window_available_candidates']}",
        f"- repair export safe candidates: {s['repair_export_safe_candidates']}",
        f"- predicted final clean/unstable after fail-closed repair: {s['predicted_final_clean']} / {s['predicted_final_unstable']}",
        f"- semantic degraded finalists increase: {s['semantic_degraded_finalists_increase']}",
        f"- unstable garbage export risk: {s['unstable_garbage_export_risk']}",
        "",
        "## Corruption Patterns",
        "| Pattern | Count |",
        "|---|---:|",
    ]
    if payload["corruption_patterns"]:
        for pattern, count in payload["corruption_patterns"].items():
            lines.append(f"| `{pattern}` | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend([
        "",
        "## Quarantined Unstable Finalists",
        "| Candidate | Window | Before | After | Improved | Export Safe | Reasons |",
        "|---:|---|---|---|---|---|---|",
    ])
    for row in payload["current_finalists_quarantined"]:
        reasons = ", ".join(row.get("v49_8_repair_reasons", [])) or "none"
        lines.append(
            f"| {row['candidate_index']} | {row['start']} -> {row['end']} | "
            f"{row['v49_8_repair_before_label']}:{row['v49_8_repair_before_score']} | "
            f"{row['v49_8_repair_after_label']}:{row['v49_8_repair_after_score']} | "
            f"{row['v49_8_repair_improved']} | {row['v49_8_repair_export_safe']} | {reasons} |"
        )

    lines.extend([
        "",
        "## Label Improvements",
        "| Candidate | Window | Before | After | Repaired Text Preview |",
        "|---:|---|---|---|---|",
    ])
    for row in payload["repair_label_improved_candidates"]:
        preview = str(row.get("v49_8_repaired_text_preview", "")).replace("|", " ")[:160]
        lines.append(
            f"| {row['candidate_index']} | {row['start']} -> {row['end']} | "
            f"{row['v49_8_repair_before_label']}:{row['v49_8_repair_before_score']} | "
            f"{row['v49_8_repair_after_label']}:{row['v49_8_repair_after_score']} | {preview} |"
        )

    lines.extend([
        "",
        "## Design",
    ])
    for item in payload["design"]["normalization_steps"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Safety")
    for item in payload["design"]["safety"]:
        lines.append(f"- {item}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="V49.8 targeted unstable-window ASR repair replay audit")
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
    print(f"repair_attempted_unstable_candidates={s['repair_attempted_unstable_candidates']}")
    print(f"repair_improved_candidates={s['repair_improved_candidates']}")
    print(f"repair_label_improved_candidates={s['repair_label_improved_candidates']}")
    print(f"degraded_before_repair={s['degraded_before_repair']}")
    print(f"degraded_after_repair={s['degraded_after_repair']}")
    print(f"repaired_window_available_candidates={s['repaired_window_available_candidates']}")
    print(f"repair_export_safe_candidates={s['repair_export_safe_candidates']}")
    print(f"predicted_final_clean={s['predicted_final_clean']}")
    print(f"predicted_final_unstable={s['predicted_final_unstable']}")
    print(f"unstable_garbage_export_risk={s['unstable_garbage_export_risk']}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")


if __name__ == "__main__":
    main()
