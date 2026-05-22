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


DEFAULT_JOB_ID = "2efbe27a-4f64-41aa-9077-6f483e00fc4f"
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V50_2_CONTEXT_SHAPING_REPLAY_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v50_2_context_shaping_replay_audit.json")
TARGET_WINDOWS = [
    (350.36, 372.2),
    (396.04, 412.36),
    (1161.0, 1173.0),
    (536.36, 548.36),
]


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


def target_rows(job_id, clip_intelligence_path):
    windows = {(round(start, 2), round(end, 2)) for start, end in TARGET_WINDOWS}
    rows = []
    for row in current_pre_creator_clips(job_id, clip_intelligence_path):
        start = round(safe_float(row.get("start")), 2)
        end = round(safe_float(row.get("end"), start), 2)
        if (start, end) in windows:
            rows.append(row)
    return rows


def build_candidate_clip(job_id, row, segments, chunks):
    start = round(safe_float(row.get("start")), 2)
    end = round(safe_float(row.get("end"), start), 2)
    score_breakdown = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
    niche = str(row.get("niche") or score_breakdown.get("detected_niche") or "general")
    original_text = pipeline_runner.get_nearby_text(segments, start, end, window=0)
    original_local_asr = pipeline_runner.v48_candidate_asr_stability(start, end, chunks)
    v49_9_repair = pipeline_runner.v49_9_repaired_window_status(job_id, start, end)
    payload = pipeline_runner.v50_effective_repaired_text_payload(
        original_text,
        score_breakdown.get("start_text") or original_text,
        score_breakdown.get("end_text") or original_text,
        original_local_asr,
        v49_9_repair,
    )
    combined_text = payload["combined_text"]
    start_text = str(payload["start_text"] or combined_text).strip()
    end_text = str(payload["end_text"] or combined_text).strip()
    local_asr = payload["local_asr"]
    semantic_asr = pipeline_runner.v48_semantic_asr_confidence(combined_text)
    hook_bonus = safe_float(score_breakdown.get("hook_bonus"))
    v43_bonus, _ = pipeline_runner.v43_hinglish_payoff_bonus(combined_text)
    v44_bonus, _, _ = pipeline_runner.v44_semantic_payoff_score(combined_text)
    if pipeline_runner.v44_payoff_quality_block(combined_text):
        payoff_bonus = 0
    else:
        payoff_bonus = max(
            pipeline_runner.v6_payoff_bonus(combined_text),
            pipeline_runner.v7_better_payoff_bonus(combined_text),
            v43_bonus,
            v44_bonus,
        )
    context_quality = pipeline_runner.v7_context_quality_score(combined_text)

    return {
        "job_id": job_id,
        "niche": niche,
        "start": start,
        "end": end,
        "source_text": original_text,
        "expanded_text": combined_text,
        "title": pipeline_runner.v9_editorial_title(combined_text, set()),
        "score": safe_float(row.get("score", 0)),
        "score_breakdown": {
            **score_breakdown,
            "hook_bonus": hook_bonus,
            "payoff_bonus": payoff_bonus,
            "context_quality": context_quality,
            "start_text": start_text,
            "end_text": end_text,
            "low_confidence_asr": bool(score_breakdown.get("low_confidence_asr", True)),
            "local_asr_confidence_label": local_asr.get("local_asr_confidence_label"),
            "unstable_window_overlap_ratio": local_asr.get("unstable_window_overlap_ratio"),
            "chunk_confidence_score": local_asr.get("chunk_confidence_score"),
            "local_asr_reasons": local_asr.get("local_asr_reasons", [])[:5],
            "semantic_asr_confidence_label": semantic_asr["semantic_asr_confidence_label"],
            "semantic_asr_corruption_score": semantic_asr["semantic_asr_corruption_score"],
            "semantic_asr_reasons": semantic_asr["semantic_asr_reasons"][:5],
            **v49_9_repair,
            **payload["metadata"],
        },
    }


def summarize_candidate(clip, segments, chunks):
    before_reasons = pipeline_runner.creator_qa_rejection_reasons(copy.deepcopy(clip), [])
    shaping = pipeline_runner.v50_2_context_shape_candidate(
        copy.deepcopy(clip),
        segments,
        chunks,
        niche=str(clip.get("niche") or "general"),
    )
    score_breakdown = clip.get("score_breakdown", {})
    return {
        "start": clip["start"],
        "end": clip["end"],
        "local_asr_confidence_label": score_breakdown.get("local_asr_confidence_label"),
        "semantic_asr_confidence_label": score_breakdown.get("semantic_asr_confidence_label"),
        "v50_repaired_text_applied": bool(score_breakdown.get("v50_repaired_text_applied")),
        "before_reasons": before_reasons,
        "after_reasons": shaping.get("after_reasons", before_reasons),
        "creator_safe_before": len(before_reasons) == 0,
        "creator_safe_after": len(shaping.get("after_reasons", before_reasons)) == 0,
        "v50_2_context_expanded": shaping.get("v50_2_context_expanded", False),
        "v50_2_original_window": shaping.get("v50_2_original_window"),
        "v50_2_expanded_window": shaping.get("v50_2_expanded_window"),
        "v50_2_setup_source": shaping.get("v50_2_setup_source"),
        "v50_2_payoff_source": shaping.get("v50_2_payoff_source"),
        "v50_2_expansion_rejected_reason": shaping.get("v50_2_expansion_rejected_reason"),
        "v50_2_local_asr_confidence_label": shaping.get("v50_2_local_asr_confidence_label"),
        "v50_2_semantic_asr_confidence_label": shaping.get("v50_2_semantic_asr_confidence_label"),
        "v50_2_context_quality": shaping.get("v50_2_context_quality"),
        "v50_2_payoff_bonus": shaping.get("v50_2_payoff_bonus"),
        "text_preview_before": str(clip.get("expanded_text") or "")[:260],
        "text_preview_after": str(shaping.get("expanded_text") or clip.get("expanded_text") or "")[:260],
    }


def build_payload(args):
    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")
    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    rows = target_rows(args.job_id, args.clip_intelligence)
    clips = [build_candidate_clip(args.job_id, row, segments, chunks) for row in rows]
    results = [summarize_candidate(clip, segments, chunks) for clip in clips]

    no_hook_before = sum(1 for row in results if "no_hook_no_payoff" in row["before_reasons"])
    no_hook_after = sum(1 for row in results if "no_hook_no_payoff" in row["after_reasons"])
    creator_safe_before = sum(1 for row in results if row["creator_safe_before"])
    creator_safe_after = sum(1 for row in results if row["creator_safe_after"])
    predicted_final_clean = sum(
        1 for row in results
        if row["v50_2_local_asr_confidence_label"] == "clean"
    )
    predicted_final_unstable = sum(
        1 for row in results
        if row["v50_2_local_asr_confidence_label"] == "unstable"
    )
    summary = {
        "candidates_tested": len(results),
        "candidates_expanded": sum(1 for row in results if row["v50_2_context_expanded"]),
        "no_hook_no_payoff_before": no_hook_before,
        "no_hook_no_payoff_after": no_hook_after,
        "creator_safe_before": creator_safe_before,
        "creator_safe_after": creator_safe_after,
        "predicted_final_clean": predicted_final_clean,
        "predicted_final_unstable": predicted_final_unstable,
        "video_rerun_justified": (
            creator_safe_after > creator_safe_before
            and predicted_final_unstable <= 0
        ),
    }
    return {
        "scope": "offline_context_shaping_replay_no_video_rerun",
        "job_id": args.job_id,
        "asr_artifact": str(asr_artifact),
        "summary": summary,
        "candidates": results,
    }


def write_markdown(path, payload):
    summary = payload["summary"]
    lines = [
        "# V50.2 Context Shaping Replay Audit Report",
        "",
        "Scope: offline replay only. This audit tests setup/payoff context expansion for the repaired-clean or locally clean target windows, but rejects any expansion that adds unstable ASR, semantic degradation, drift, filler, or no Creator QA improvement.",
        "",
        "## Summary",
        f"- candidates_tested: {summary['candidates_tested']}",
        f"- candidates_expanded: {summary['candidates_expanded']}",
        f"- no_hook_no_payoff_before: {summary['no_hook_no_payoff_before']}",
        f"- no_hook_no_payoff_after: {summary['no_hook_no_payoff_after']}",
        f"- creator_safe_before: {summary['creator_safe_before']}",
        f"- creator_safe_after: {summary['creator_safe_after']}",
        f"- predicted_final_clean: {summary['predicted_final_clean']}",
        f"- predicted_final_unstable: {summary['predicted_final_unstable']}",
        f"- video_rerun_justified: {summary['video_rerun_justified']}",
        "",
        "## Candidate Results",
        "| Window | Repaired Clean | Before Reasons | After Reasons | Expanded | Expanded Window | Rejected Reason |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["candidates"]:
        lines.append(
            f"| {row['start']} -> {row['end']} | {row['v50_repaired_text_applied']} | "
            f"{', '.join(row['before_reasons']) or 'none'} | "
            f"{', '.join(row['after_reasons']) or 'none'} | "
            f"{row['v50_2_context_expanded']} | "
            f"{row['v50_2_expanded_window']} | "
            f"{row['v50_2_expansion_rejected_reason'] or 'none'} |"
        )
    lines.extend([
        "",
        "## Context Decisions",
        "| Window | Setup Source | Payoff Source | After Local/Semantic | After Context/Payoff |",
        "|---|---|---|---|---|",
    ])
    for row in payload["candidates"]:
        lines.append(
            f"| {row['start']} -> {row['end']} | {row['v50_2_setup_source'] or 'none'} | "
            f"{row['v50_2_payoff_source'] or 'none'} | "
            f"{row['v50_2_local_asr_confidence_label']} / {row['v50_2_semantic_asr_confidence_label']} | "
            f"{row['v50_2_context_quality']} / {row['v50_2_payoff_bonus']} |"
        )
    lines.extend([
        "",
        "## After Text Previews",
        "| Window | After Preview |",
        "|---|---|",
    ])
    for row in payload["candidates"]:
        lines.append(f"| {row['start']} -> {row['end']} | {row['text_preview_after']} |")
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

    summary = payload["summary"]
    for key in [
        "candidates_tested",
        "candidates_expanded",
        "no_hook_no_payoff_before",
        "no_hook_no_payoff_after",
        "creator_safe_before",
        "creator_safe_after",
        "predicted_final_clean",
        "predicted_final_unstable",
        "video_rerun_justified",
    ]:
        print(f"{key}={summary[key]}")


if __name__ == "__main__":
    main()
