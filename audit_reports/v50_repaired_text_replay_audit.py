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
from v48_asr_chunk_stability_audit import load_segments, safe_float
from v48_candidate_asr_confidence_audit import read_jsonl


DEFAULT_JOB_ID = "2efbe27a-4f64-41aa-9077-6f483e00fc4f"
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V50_REPAIRED_TEXT_REPLAY_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v50_repaired_text_replay_audit.json")


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


def summarize_clip(job_id, row, segments, chunks, apply_repair):
    start = round(safe_float(row.get("start")), 2)
    end = round(safe_float(row.get("end"), start), 2)
    score_breakdown = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
    original_text = pipeline_runner.get_nearby_text(segments, start, end, window=0)
    original_local_asr = pipeline_runner.v48_candidate_asr_stability(start, end, chunks)
    v49_9_repair = pipeline_runner.v49_9_repaired_window_status(job_id, start, end)

    if apply_repair:
        payload = pipeline_runner.v50_effective_repaired_text_payload(
            original_text,
            score_breakdown.get("start_text") or original_text,
            score_breakdown.get("end_text") or original_text,
            original_local_asr,
            v49_9_repair,
        )
    else:
        payload = {
            "combined_text": original_text,
            "start_text": score_breakdown.get("start_text") or original_text,
            "end_text": score_breakdown.get("end_text") or original_text,
            "local_asr": original_local_asr,
            "metadata": {
                "v50_repaired_text_applied": False,
                "v50_original_text_preview": original_text[:220],
                "v50_repaired_text_preview": "",
                "v50_repaired_text_source": "",
            },
        }

    combined_text = payload["combined_text"]
    start_text = str(payload["start_text"] or combined_text)
    end_text = str(payload["end_text"] or combined_text)
    local_asr = payload["local_asr"]
    hook_bonus = int(score_breakdown.get("hook_bonus", 0) or 0)
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
    semantic_asr = pipeline_runner.v48_semantic_asr_confidence(combined_text)

    clip = {
        "start": start,
        "end": end,
        "source_text": str(row.get("source_preview") or "")[:220],
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
            "low_confidence_asr": score_breakdown.get("low_confidence_asr", True),
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
    reasons = pipeline_runner.creator_qa_rejection_reasons(clip, [])
    metadata_reasons = pipeline_runner.creator_qa_metadata_reasons(clip)
    return {
        "start": start,
        "end": end,
        "title": clip["title"],
        "expanded_text_preview": combined_text[:240],
        "local_asr_confidence_label": clip["score_breakdown"]["local_asr_confidence_label"],
        "semantic_asr_confidence_label": clip["score_breakdown"]["semantic_asr_confidence_label"],
        "semantic_asr_corruption_score": clip["score_breakdown"]["semantic_asr_corruption_score"],
        "hook_bonus": hook_bonus,
        "payoff_bonus": payoff_bonus,
        "context_quality": context_quality,
        "creator_qa_reasons": reasons,
        "creator_qa_metadata_reasons": metadata_reasons,
        "creator_safe": len(reasons) == 0,
        "v50_repaired_text_applied": payload["metadata"]["v50_repaired_text_applied"],
        "v50_original_text_preview": payload["metadata"]["v50_original_text_preview"],
        "v50_repaired_text_preview": payload["metadata"]["v50_repaired_text_preview"],
        "v50_repaired_text_source": payload["metadata"]["v50_repaired_text_source"],
        "v49_9_repaired_window_available": v49_9_repair.get("v49_9_repaired_window_available"),
        "v49_9_repair_export_safe": v49_9_repair.get("v49_9_repair_export_safe"),
    }


def build_payload(args):
    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")
    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    rows = current_pre_creator_clips(args.job_id, args.clip_intelligence)
    before = [summarize_clip(args.job_id, row, segments, chunks, apply_repair=False) for row in rows]
    after = [summarize_clip(args.job_id, row, segments, chunks, apply_repair=True) for row in rows]

    before_map = {(row["start"], row["end"]): row for row in before}
    after_map = {(row["start"], row["end"]): row for row in after}
    comparisons = []
    for key in before_map:
        comparisons.append({
            "start": key[0],
            "end": key[1],
            "before": before_map[key],
            "after": after_map[key],
        })

    before_no_hook = sum(1 for row in before if "no_hook_no_payoff" in row["creator_qa_reasons"])
    after_no_hook = sum(1 for row in after if "no_hook_no_payoff" in row["creator_qa_reasons"])
    before_creator_safe = sum(1 for row in before if row["creator_safe"])
    after_creator_safe = sum(1 for row in after if row["creator_safe"])
    before_clean = sum(1 for row in before if row["local_asr_confidence_label"] == "clean")
    after_clean = sum(1 for row in after if row["local_asr_confidence_label"] == "clean")
    before_unstable = sum(1 for row in before if row["local_asr_confidence_label"] == "unstable")
    after_unstable = sum(1 for row in after if row["local_asr_confidence_label"] == "unstable")
    before_degraded = sum(1 for row in before if row["semantic_asr_confidence_label"] == "degraded_semantics")
    after_degraded = sum(1 for row in after if row["semantic_asr_confidence_label"] == "degraded_semantics")

    return {
        "scope": "offline_repaired_text_substitution_replay_no_video_rerun",
        "job_id": args.job_id,
        "asr_artifact": str(asr_artifact),
        "summary": {
            "finalists_analyzed": len(before),
            "repaired_text_applied_count": sum(1 for row in after if row["v50_repaired_text_applied"]),
            "no_hook_no_payoff_before": before_no_hook,
            "no_hook_no_payoff_after": after_no_hook,
            "creator_safe_before": before_creator_safe,
            "creator_safe_after": after_creator_safe,
            "predicted_final_clean": after_clean,
            "predicted_final_unstable": after_unstable,
            "semantic_degraded_before": before_degraded,
            "semantic_degraded_after": after_degraded,
            "video_rerun_justified": (
                after_clean > before_clean
                and after_unstable < before_unstable
                and after_degraded <= before_degraded
                and after_creator_safe >= before_creator_safe
            ),
        },
        "before": before,
        "after": after,
        "comparisons": comparisons,
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V50 Repaired Text Replay Audit Report",
        "",
        "Scope: offline replay only. This applies validated V49.9 exact-window repaired text to downstream scoring and Creator QA inputs for the current pre-Creator-QA finalists. No full video rerun, no Creator QA relaxation, and no ASR threshold relaxation were performed.",
        "",
        "## Summary",
        f"- finalists analyzed: {s['finalists_analyzed']}",
        f"- repaired_text_applied_count: {s['repaired_text_applied_count']}",
        f"- no_hook_no_payoff_before: {s['no_hook_no_payoff_before']}",
        f"- no_hook_no_payoff_after: {s['no_hook_no_payoff_after']}",
        f"- creator_safe_before: {s['creator_safe_before']}",
        f"- creator_safe_after: {s['creator_safe_after']}",
        f"- predicted_final_clean: {s['predicted_final_clean']}",
        f"- predicted_final_unstable: {s['predicted_final_unstable']}",
        f"- semantic_degraded_before/after: {s['semantic_degraded_before']} / {s['semantic_degraded_after']}",
        f"- video_rerun_justified: {s['video_rerun_justified']}",
        "",
        "## Per Finalist",
        "| Window | Repaired Applied | Before Reasons | After Reasons | Before Local/Semantic | After Local/Semantic |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["comparisons"]:
        before = row["before"]
        after = row["after"]
        lines.append(
            f"| {row['start']} -> {row['end']} | {after['v50_repaired_text_applied']} | "
            f"{', '.join(before['creator_qa_reasons']) or 'none'} | "
            f"{', '.join(after['creator_qa_reasons']) or 'none'} | "
            f"{before['local_asr_confidence_label']} / {before['semantic_asr_confidence_label']} | "
            f"{after['local_asr_confidence_label']} / {after['semantic_asr_confidence_label']} |"
        )

    lines.extend([
        "",
        "## Repaired Windows",
        "| Window | Repaired Preview |",
        "|---|---|",
    ])
    repaired_any = False
    for row in payload["after"]:
        if not row["v50_repaired_text_applied"]:
            continue
        repaired_any = True
        lines.append(f"| {row['start']} -> {row['end']} | {row['v50_repaired_text_preview']} |")
    if not repaired_any:
        lines.append("| none | none |")

    path = Path(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="V50 repaired text replay audit")
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID)
    parser.add_argument("--clip-intelligence", type=Path, default=DEFAULT_CLIP_INTELLIGENCE)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    return parser.parse_args()


def main():
    args = parse_args()
    payload = build_payload(args)
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(args.md_out, payload)
    s = payload["summary"]
    print(f"repaired_text_applied_count={s['repaired_text_applied_count']}")
    print(f"no_hook_no_payoff_before={s['no_hook_no_payoff_before']}")
    print(f"no_hook_no_payoff_after={s['no_hook_no_payoff_after']}")
    print(f"creator_safe_before={s['creator_safe_before']}")
    print(f"creator_safe_after={s['creator_safe_after']}")
    print(f"predicted_final_clean={s['predicted_final_clean']}")
    print(f"predicted_final_unstable={s['predicted_final_unstable']}")
    print(f"video_rerun_justified={s['video_rerun_justified']}")


if __name__ == "__main__":
    main()
