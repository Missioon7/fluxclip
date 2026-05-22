import argparse
import copy
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
from v48_asr_chunk_stability_audit import load_segments, safe_float
from v48_candidate_asr_confidence_audit import read_jsonl


DEFAULT_JOB_ID = "v51_fresh_source_23f21012"
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V52_PAYOFF_NATIVE_GENERATION_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v52_payoff_native_generation_audit.json")


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


def current_pre_creator_clips(job_id, clip_intelligence_path):
    rows = []
    for row in read_jsonl(clip_intelligence_path):
        if str(row.get("job_id")) != str(job_id):
            continue
        if row.get("stage") != "pre_creator_qa":
            continue
        rows.append(row)
    return rows


def existing_creator_summary(rows):
    clips = []
    for row in rows:
        score_breakdown = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
        clip = {
            "start": round(safe_float(row.get("start")), 2),
            "end": round(safe_float(row.get("end"), safe_float(row.get("start"))), 2),
            "expanded_text": str(row.get("expanded_preview") or row.get("source_preview") or ""),
            "source_text": str(row.get("source_preview") or ""),
            "title": str(row.get("title") or "Untitled Clip"),
            "score_breakdown": score_breakdown,
        }
        reasons = pipeline_runner.creator_qa_rejection_reasons(copy.deepcopy(clip), [])
        clips.append({
            "start": clip["start"],
            "end": clip["end"],
            "creator_qa_reasons": reasons,
            "local_asr_confidence_label": score_breakdown.get("local_asr_confidence_label"),
            "semantic_asr_confidence_label": score_breakdown.get("semantic_asr_confidence_label"),
        })
    return clips


def false_positive_risk(generated, creator_safe_after):
    if not generated:
        return "low"
    anchor_count = sum(1 for clip in generated if clip["score_breakdown"].get("v52_payoff_anchor_detected"))
    if creator_safe_after <= 0:
        return "low"
    if creator_safe_after >= max(2, anchor_count):
        return "medium"
    return "low"


def build_payload(args):
    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")
    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    existing_rows = current_pre_creator_clips(args.job_id, args.clip_intelligence)
    existing = existing_creator_summary(existing_rows)
    generated = pipeline_runner.v52_generate_payoff_native_candidates(
        segments,
        chunks,
        niche="general",
        max_candidates=8,
    )

    generated_rows = []
    for clip in generated:
        sb = clip.get("score_breakdown", {})
        generated_rows.append({
            "start": round(safe_float(clip.get("start")), 2),
            "end": round(safe_float(clip.get("end"), safe_float(clip.get("start"))), 2),
            "title": clip.get("title"),
            "creator_qa_reasons": clip.get("creator_qa_reasons", []),
            "creator_safe": len(clip.get("creator_qa_reasons", [])) == 0,
            "local_asr_confidence_label": sb.get("local_asr_confidence_label"),
            "semantic_asr_confidence_label": sb.get("semantic_asr_confidence_label"),
            "v52_payoff_anchor_detected": sb.get("v52_payoff_anchor_detected"),
            "v52_payoff_anchor_reason": sb.get("v52_payoff_anchor_reason"),
            "v52_generated_from_payoff_anchor": sb.get("v52_generated_from_payoff_anchor"),
            "v52_anchor_window": sb.get("v52_anchor_window"),
            "text_preview": str(clip.get("expanded_text") or "")[:260],
        })

    creator_safe_before = sum(1 for row in existing if len(row["creator_qa_reasons"]) == 0)
    creator_safe_after = sum(1 for row in generated_rows if row["creator_safe"])
    no_hook_before = sum(1 for row in existing if "no_hook_no_payoff" in row["creator_qa_reasons"])
    no_hook_after = sum(1 for row in generated_rows if "no_hook_no_payoff" in row["creator_qa_reasons"])

    summary = {
        "payoff_anchors_found": sum(1 for row in generated_rows if row["v52_payoff_anchor_detected"]),
        "candidates_generated_from_payoff": len(generated_rows),
        "creator_safe_before": creator_safe_before,
        "creator_safe_after": creator_safe_after,
        "no_hook_no_payoff_before": no_hook_before,
        "no_hook_no_payoff_after": no_hook_after,
        "predicted_final_clean": sum(1 for row in generated_rows if row["local_asr_confidence_label"] == "clean"),
        "predicted_final_unstable": sum(1 for row in generated_rows if row["local_asr_confidence_label"] == "unstable"),
        "false_positive_risk": false_positive_risk(generated_rows, creator_safe_after),
        "video_rerun_justified": creator_safe_after > creator_safe_before and sum(1 for row in generated_rows if row["local_asr_confidence_label"] == "unstable") == 0,
    }
    return {
        "scope": "offline_payoff_native_candidate_generation_replay",
        "job_id": args.job_id,
        "asr_artifact": str(asr_artifact),
        "summary": summary,
        "existing_pre_creator_candidates": existing,
        "generated_payoff_candidates": generated_rows,
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V52 Payoff-Native Candidate Generation Audit Report",
        "",
        "Scope: offline replay only. This audit searches clean or borderline-semantic transcript windows for payoff anchors, then generates candidate windows outward from those anchors with fail-closed ASR, drift, and filler guards.",
        "",
        "## Summary",
        f"- payoff_anchors_found: {s['payoff_anchors_found']}",
        f"- candidates_generated_from_payoff: {s['candidates_generated_from_payoff']}",
        f"- creator_safe_before: {s['creator_safe_before']}",
        f"- creator_safe_after: {s['creator_safe_after']}",
        f"- no_hook_no_payoff_before: {s['no_hook_no_payoff_before']}",
        f"- no_hook_no_payoff_after: {s['no_hook_no_payoff_after']}",
        f"- predicted_final_clean: {s['predicted_final_clean']}",
        f"- predicted_final_unstable: {s['predicted_final_unstable']}",
        f"- false_positive_risk: {s['false_positive_risk']}",
        f"- video_rerun_justified: {s['video_rerun_justified']}",
        "",
        "## Generated Payoff Candidates",
        "| Window | Anchor | Anchor Reason | Local/Semantic | Creator QA |",
        "|---|---|---|---|---|",
    ]
    rows = payload["generated_payoff_candidates"]
    if not rows:
        lines.append("| none | none | none | none | none |")
    for row in rows:
        lines.append(
            f"| {row['start']} -> {row['end']} | {row['v52_anchor_window']} | "
            f"{row['v52_payoff_anchor_reason'] or 'none'} | "
            f"{row['local_asr_confidence_label']} / {row['semantic_asr_confidence_label']} | "
            f"{', '.join(row['creator_qa_reasons']) or 'none'} |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID)
    parser.add_argument("--clip-intelligence", type=Path, default=DEFAULT_CLIP_INTELLIGENCE)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_payload(args)
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.md_out, payload)

    for key, value in payload["summary"].items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
