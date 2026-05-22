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

import asr_engine
import pipeline_runner
from v48_asr_chunk_stability_audit import load_segments, safe_float
from v48_candidate_asr_confidence_audit import read_jsonl


DEFAULT_JOB_ID = "2efbe27a-4f64-41aa-9077-6f483e00fc4f"
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V50_3_ADJACENT_CONTEXT_REPAIR_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v50_3_adjacent_context_repair_audit.json")

TARGET_CANDIDATES = [
    {
        "window": (350.36, 372.2),
        "setup_window": (344.56, 349.92),
        "payoff_window": (372.2, 390.44),
    },
    {
        "window": (396.04, 412.36),
        "setup_window": (394.32, 396.04),
        "payoff_window": (413.36, 422.36),
    },
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


def build_candidate_clip(job_id, row, segments, chunks):
    start = round(safe_float(row.get("start")), 2)
    end = round(safe_float(row.get("end"), start), 2)
    score_breakdown = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
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
    clip = {
        "job_id": job_id,
        "niche": str(row.get("niche") or score_breakdown.get("detected_niche") or "general"),
        "start": start,
        "end": end,
        "source_text": original_text,
        "expanded_text": combined_text,
        "title": pipeline_runner.v9_editorial_title(combined_text, set()),
        "score_breakdown": {
            **score_breakdown,
            "hook_bonus": hook_bonus,
            "payoff_bonus": payoff_bonus,
            "context_quality": context_quality,
            "start_text": start_text,
            "end_text": end_text,
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
    return clip


def target_rows(job_id, clip_intelligence_path):
    windows = {target["window"] for target in TARGET_CANDIDATES}
    out = []
    for row in current_pre_creator_clips(job_id, clip_intelligence_path):
        start = round(safe_float(row.get("start")), 2)
        end = round(safe_float(row.get("end"), start), 2)
        if (start, end) in windows:
            out.append(row)
    return out


def repaired_context_window(video_path, start, end):
    try:
        retry_payload = asr_engine.transcribe_exact_asr_window(
            video_path,
            start,
            end,
            keep_audio=False,
        )
    except Exception as e:
        return {
            "start": round(start, 2),
            "end": round(end, 2),
            "repaired_text": "",
            "repaired_local_asr_label": "failed",
            "repaired_semantic_label": "failed",
            "repaired_semantic_score": None,
            "transcript_quality_score": 0,
            "low_confidence_asr": True,
            "topic_drift": False,
            "filler_only": True,
            "usable_after_repair": False,
            "local_asr_reasons": [f"retry_failed={str(e)[:160]}"],
            "semantic_reasons": [],
            "transcript_quality_reasons": [f"retry_failed={str(e)[:160]}"],
        }
    repaired_text = str(retry_payload.get("repaired_text") or "").strip()
    repaired_chunks = pipeline_runner.v48_build_asr_stability_chunks(retry_payload.get("cleaned_segments", []))
    repaired_local_asr = pipeline_runner.v48_candidate_asr_stability(
        0.0,
        retry_payload.get("duration", max(0.25, end - start)),
        repaired_chunks,
    )
    repaired_semantic = pipeline_runner.v48_semantic_asr_confidence(repaired_text)
    drift = pipeline_runner._v7_is_drift(repaired_text)
    filler_only = (
        pipeline_runner.is_bad_transcript_clip(repaired_text)
        or len(pipeline_runner._v8_word_set(repaired_text)) < 6
        or pipeline_runner.v7_context_quality_score(repaired_text) < 8
    )
    usable = bool(
        str(repaired_local_asr.get("local_asr_confidence_label") or "") == "clean"
        and str(repaired_semantic.get("semantic_asr_confidence_label") or "") == "clean_semantics"
        and not drift
        and not filler_only
    )
    return {
        "start": round(start, 2),
        "end": round(end, 2),
        "repaired_text": repaired_text,
        "repaired_local_asr_label": repaired_local_asr.get("local_asr_confidence_label"),
        "repaired_semantic_label": repaired_semantic.get("semantic_asr_confidence_label"),
        "repaired_semantic_score": repaired_semantic.get("semantic_asr_corruption_score"),
        "transcript_quality_score": retry_payload.get("transcript_quality_score"),
        "low_confidence_asr": retry_payload.get("low_confidence_asr"),
        "topic_drift": drift,
        "filler_only": filler_only,
        "usable_after_repair": usable,
        "local_asr_reasons": repaired_local_asr.get("local_asr_reasons", [])[:5],
        "semantic_reasons": repaired_semantic.get("semantic_asr_reasons", [])[:5],
        "transcript_quality_reasons": retry_payload.get("transcript_quality_reasons", [])[:5],
    }


def apply_adjacent_context(candidate_clip, setup_payload, payoff_payload):
    before_reasons = pipeline_runner.creator_qa_rejection_reasons(copy.deepcopy(candidate_clip), [])
    out = {
        "before_reasons": before_reasons,
        "after_reasons": before_reasons[:],
        "expanded": False,
        "expanded_window": [candidate_clip["start"], candidate_clip["end"]],
        "setup_used": False,
        "payoff_used": False,
        "rejected_reason": "",
        "expanded_text": candidate_clip.get("expanded_text", ""),
        "local_asr_confidence_label": candidate_clip["score_breakdown"].get("local_asr_confidence_label"),
        "semantic_asr_confidence_label": candidate_clip["score_breakdown"].get("semantic_asr_confidence_label"),
    }
    parts = []
    expanded_start = candidate_clip["start"]
    expanded_end = candidate_clip["end"]
    if setup_payload and setup_payload.get("usable_after_repair"):
        parts.append(str(setup_payload.get("repaired_text") or "").strip())
        expanded_start = round(safe_float(setup_payload.get("start"), expanded_start), 2)
        out["setup_used"] = True
    parts.append(str(candidate_clip.get("expanded_text") or "").strip())
    if payoff_payload and payoff_payload.get("usable_after_repair"):
        parts.append(str(payoff_payload.get("repaired_text") or "").strip())
        expanded_end = round(safe_float(payoff_payload.get("end"), expanded_end), 2)
        out["payoff_used"] = True

    if not out["setup_used"] and not out["payoff_used"]:
        out["rejected_reason"] = "no_usable_adjacent_repair"
        return out

    expanded_text = " ".join(part for part in parts if part).strip()
    if pipeline_runner._v7_is_drift(expanded_text):
        out["rejected_reason"] = "expanded_text_topic_drift"
        return out
    semantic = pipeline_runner.v48_semantic_asr_confidence(expanded_text)
    if semantic.get("semantic_asr_confidence_label") != "clean_semantics":
        out["rejected_reason"] = "expanded_text_semantic_not_clean"
        return out

    hook_bonus = safe_float(candidate_clip["score_breakdown"].get("hook_bonus"))
    v43_bonus, _ = pipeline_runner.v43_hinglish_payoff_bonus(expanded_text)
    v44_bonus, _, _ = pipeline_runner.v44_semantic_payoff_score(expanded_text)
    if pipeline_runner.v44_payoff_quality_block(expanded_text):
        payoff_bonus = 0
    else:
        payoff_bonus = max(
            pipeline_runner.v6_payoff_bonus(expanded_text),
            pipeline_runner.v7_better_payoff_bonus(expanded_text),
            v43_bonus,
            v44_bonus,
        )

    test_clip = copy.deepcopy(candidate_clip)
    test_clip["start"] = expanded_start
    test_clip["end"] = expanded_end
    test_clip["expanded_text"] = expanded_text
    test_clip["title"] = pipeline_runner.v9_editorial_title(expanded_text, set())
    start_text, end_text = pipeline_runner.v50_repaired_text_boundaries(expanded_text)
    sb = test_clip["score_breakdown"]
    sb["hook_bonus"] = hook_bonus
    sb["payoff_bonus"] = payoff_bonus
    sb["context_quality"] = pipeline_runner.v7_context_quality_score(expanded_text)
    sb["start_text"] = start_text
    sb["end_text"] = end_text
    sb["local_asr_confidence_label"] = "clean"
    sb["unstable_window_overlap_ratio"] = 0.0
    sb["chunk_confidence_score"] = 100
    sb["local_asr_reasons"] = []
    sb["semantic_asr_confidence_label"] = semantic.get("semantic_asr_confidence_label")
    sb["semantic_asr_corruption_score"] = semantic.get("semantic_asr_corruption_score")
    sb["semantic_asr_reasons"] = semantic.get("semantic_asr_reasons", [])[:5]

    after_reasons = pipeline_runner.creator_qa_rejection_reasons(test_clip, [])
    out.update({
        "after_reasons": after_reasons,
        "expanded": "no_hook_no_payoff" not in after_reasons,
        "expanded_window": [expanded_start, expanded_end],
        "expanded_text": expanded_text,
        "local_asr_confidence_label": "clean",
        "semantic_asr_confidence_label": semantic.get("semantic_asr_confidence_label"),
    })
    if "no_hook_no_payoff" in after_reasons:
        out["rejected_reason"] = "no_hook_no_payoff_persists"
    return out


def build_payload(args):
    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")
    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    rows = target_rows(args.job_id, args.clip_intelligence)
    row_map = {
        (round(safe_float(row.get("start")), 2), round(safe_float(row.get("end"), safe_float(row.get("start"))), 2)): row
        for row in rows
    }
    video_path = Path("uploads") / f"{args.job_id}.mp4"
    if not video_path.exists():
        raise SystemExit(f"Video path not found for job_id={args.job_id}: {video_path}")

    repaired_adjacent = []
    candidates = []
    for target in TARGET_CANDIDATES:
        center = target["window"]
        row = row_map.get(center)
        if not row:
            continue
        clip = build_candidate_clip(args.job_id, row, segments, chunks)
        setup_payload = repaired_context_window(str(video_path), *target["setup_window"])
        payoff_payload = repaired_context_window(str(video_path), *target["payoff_window"])
        repaired_adjacent.extend([
            {"role": "setup", "candidate_window": list(center), **setup_payload},
            {"role": "payoff", "candidate_window": list(center), **payoff_payload},
        ])
        replay = apply_adjacent_context(clip, setup_payload, payoff_payload)
        candidates.append({
            "window": list(center),
            "before_reasons": replay["before_reasons"],
            "after_reasons": replay["after_reasons"],
            "creator_safe_before": len(replay["before_reasons"]) == 0,
            "creator_safe_after": len(replay["after_reasons"]) == 0,
            "context_expansion_possible_after_repair": replay["expanded"],
            "expanded_window": replay["expanded_window"],
            "setup_used": replay["setup_used"],
            "payoff_used": replay["payoff_used"],
            "rejected_reason": replay["rejected_reason"],
            "local_asr_confidence_label": replay["local_asr_confidence_label"],
            "semantic_asr_confidence_label": replay["semantic_asr_confidence_label"],
            "expanded_text_preview": replay["expanded_text"][:260],
        })

    summary = {
        "adjacent_windows_tested": len(repaired_adjacent),
        "adjacent_windows_repaired": sum(1 for row in repaired_adjacent if row["usable_after_repair"]),
        "context_expansion_possible_after_repair": sum(
            1 for row in candidates if row["context_expansion_possible_after_repair"]
        ),
        "no_hook_no_payoff_before": sum(1 for row in candidates if "no_hook_no_payoff" in row["before_reasons"]),
        "no_hook_no_payoff_after": sum(1 for row in candidates if "no_hook_no_payoff" in row["after_reasons"]),
        "creator_safe_before": sum(1 for row in candidates if row["creator_safe_before"]),
        "creator_safe_after": sum(1 for row in candidates if row["creator_safe_after"]),
        "predicted_final_clean": sum(1 for row in candidates if row["local_asr_confidence_label"] == "clean"),
        "predicted_final_unstable": sum(1 for row in candidates if row["local_asr_confidence_label"] == "unstable"),
        "video_rerun_justified": any(row["creator_safe_after"] for row in candidates),
    }
    return {
        "scope": "offline_adjacent_context_repair_replay_no_video_rerun",
        "job_id": args.job_id,
        "asr_artifact": str(asr_artifact),
        "video_path": str(video_path),
        "summary": summary,
        "adjacent_windows": repaired_adjacent,
        "candidates": candidates,
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V50.3 Adjacent Context Repair Audit Report",
        "",
        "Scope: offline only. This audit retries exact adjacent setup/payoff windows around the two repaired-clean candidates, then replays context shaping only if the adjacent repaired context is clean, semantically clean, non-drifting, and not filler-only.",
        "",
        "## Summary",
        f"- adjacent_windows_tested: {s['adjacent_windows_tested']}",
        f"- adjacent_windows_repaired: {s['adjacent_windows_repaired']}",
        f"- context_expansion_possible_after_repair: {s['context_expansion_possible_after_repair']}",
        f"- no_hook_no_payoff_before: {s['no_hook_no_payoff_before']}",
        f"- no_hook_no_payoff_after: {s['no_hook_no_payoff_after']}",
        f"- creator_safe_before: {s['creator_safe_before']}",
        f"- creator_safe_after: {s['creator_safe_after']}",
        f"- predicted_final_clean: {s['predicted_final_clean']}",
        f"- predicted_final_unstable: {s['predicted_final_unstable']}",
        f"- video_rerun_justified: {s['video_rerun_justified']}",
        "",
        "## Adjacent Window Repairs",
        "| Candidate | Role | Window | Local | Semantic | Usable | Drift | Filler |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["adjacent_windows"]:
        lines.append(
            f"| {row['candidate_window']} | {row['role']} | {row['start']} -> {row['end']} | "
            f"{row['repaired_local_asr_label']} | {row['repaired_semantic_label']} | "
            f"{row['usable_after_repair']} | {row['topic_drift']} | {row['filler_only']} |"
        )
    lines.extend([
        "",
        "## Candidate Replay",
        "| Window | Before Reasons | After Reasons | Expansion Possible | Expanded Window | Setup/Payoff Used | Rejected Reason |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in payload["candidates"]:
        lines.append(
            f"| {row['window']} | {', '.join(row['before_reasons']) or 'none'} | "
            f"{', '.join(row['after_reasons']) or 'none'} | "
            f"{row['context_expansion_possible_after_repair']} | {row['expanded_window']} | "
            f"{row['setup_used']}/{row['payoff_used']} | {row['rejected_reason'] or 'none'} |"
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
