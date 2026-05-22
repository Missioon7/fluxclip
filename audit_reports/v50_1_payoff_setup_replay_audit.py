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
DEFAULT_MD_OUT = Path("audit_reports/V50_1_PAYOFF_SETUP_REPLAY_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v50_1_payoff_setup_replay_audit.json")


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


def old_creator_qa_reasons(clip):
    reasons = []
    clip = clip if isinstance(clip, dict) else {}
    sb = clip.get("score_breakdown", {}) if isinstance(clip.get("score_breakdown"), dict) else {}
    text = str(clip.get("expanded_text") or clip.get("source_text") or "").strip()
    low = text.lower()
    start_text = str(sb.get("start_text") or text).strip()
    end_text = str(sb.get("end_text") or text).strip()
    start_low = start_text.lower()
    end_low = end_text.lower()

    weak_start_phrases = [
        "and ", "but ", "so ", "because ", "then ", "now ", "also ",
        "after that", "at that time", "one will", "these are",
        "you think", "come,", "now come", "if ", "which ", "that "
    ]
    if any(start_low.startswith(p) for p in weak_start_phrases):
        reasons.append("weak_continuation_start")

    malformed_patterns = [
        r"\bthe film will time\b",
        r"\byou can the\b",
        r"\bi not i would\b",
        r"\bit does mean that\b",
        r"\byou still him\b",
        r"\bif he is complete\b",
        r"\bwe will very\b",
        r"\bone will on\b",
        r"\btime had then\b",
        r"\byou one phone\b",
        r"\bhow did write\b",
    ]
    if any(__import__("re").search(p, low) for p in malformed_patterns):
        reasons.append("malformed_grammar")

    asr_gate = pipeline_runner.creator_qa_asr_gate_decision(clip)
    if asr_gate.get("reject"):
        reasons.append("asr_low_confidence")

    if safe_float(sb.get("payoff_bonus")) == 0 and safe_float(sb.get("hook_bonus")) == 0:
        reasons.append("no_hook_no_payoff")

    context_quality = safe_float(sb.get("context_quality"))
    if context_quality < 8 or len(pipeline_runner._v8_word_set(text)) < 6:
        reasons.append("weak_standalone_context")

    incomplete_endings = (
        "and", "but", "because", "so", "then", "that", "if", "in",
        "to", "from", "with", "for", "is", "has", "will", "would"
    )
    editor_reasons = sb.get("editor_reasons", [])
    creator_reasons = sb.get("true_creator_reasons", [])
    if not isinstance(editor_reasons, list):
        editor_reasons = []
    if not isinstance(creator_reasons, list):
        creator_reasons = []
    if (
        end_low.endswith(incomplete_endings)
        or "weak_ending" in editor_reasons
        or "weak_creator_ending" in creator_reasons
    ):
        reasons.append("incomplete_ending")
    return reasons


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
    start_text = str(payload["start_text"] or combined_text)
    end_text = str(payload["end_text"] or combined_text)
    local_asr = payload["local_asr"]
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


def false_positive_risk_label(overrides, total_clean_candidates, creator_safe_after):
    if overrides <= 0:
        return "low"
    if creator_safe_after <= 0:
        return "medium"
    if overrides >= max(2, total_clean_candidates):
        return "medium"
    return "low"


def build_payload(args):
    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")
    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    rows = current_pre_creator_clips(args.job_id, args.clip_intelligence)
    clips = [build_candidate_clip(args.job_id, row, segments, chunks) for row in rows]

    results = []
    for clip in clips:
        before = old_creator_qa_reasons(clip)
        after = pipeline_runner.creator_qa_rejection_reasons(clip, [])
        sb = clip.get("score_breakdown", {})
        results.append({
            "start": clip["start"],
            "end": clip["end"],
            "local_asr_confidence_label": sb.get("local_asr_confidence_label"),
            "semantic_asr_confidence_label": sb.get("semantic_asr_confidence_label"),
            "v50_repaired_text_applied": sb.get("v50_repaired_text_applied"),
            "v50_1_payoff_detected": sb.get("v50_1_payoff_detected"),
            "v50_1_setup_detected": sb.get("v50_1_setup_detected"),
            "v50_1_payoff_reason": sb.get("v50_1_payoff_reason"),
            "v50_1_no_hook_no_payoff_override": sb.get("v50_1_no_hook_no_payoff_override"),
            "before_reasons": before,
            "after_reasons": after,
            "creator_safe_before": len(before) == 0,
            "creator_safe_after": len(after) == 0,
            "text_preview": str(clip.get("expanded_text") or "")[:260],
        })

    no_hook_before = sum(1 for row in results if "no_hook_no_payoff" in row["before_reasons"])
    no_hook_after = sum(1 for row in results if "no_hook_no_payoff" in row["after_reasons"])
    creator_safe_before = sum(1 for row in results if row["creator_safe_before"])
    creator_safe_after = sum(1 for row in results if row["creator_safe_after"])
    predicted_final_clean = sum(1 for row in results if row["local_asr_confidence_label"] == "clean")
    predicted_final_unstable = sum(1 for row in results if row["local_asr_confidence_label"] == "unstable")
    overrides = sum(1 for row in results if row["v50_1_no_hook_no_payoff_override"])
    clean_or_repaired_clean = sum(
        1 for row in results
        if row["local_asr_confidence_label"] == "clean"
    )

    summary = {
        "finalists_analyzed": len(results),
        "no_hook_no_payoff_before": no_hook_before,
        "no_hook_no_payoff_after": no_hook_after,
        "creator_safe_before": creator_safe_before,
        "creator_safe_after": creator_safe_after,
        "predicted_final_clean": predicted_final_clean,
        "predicted_final_unstable": predicted_final_unstable,
        "override_count": overrides,
        "false_positive_risk": false_positive_risk_label(
            overrides,
            clean_or_repaired_clean,
            creator_safe_after,
        ),
        "video_rerun_justified": (
            creator_safe_after > creator_safe_before
            and predicted_final_unstable <= 2
        ),
    }

    return {
        "scope": "offline_payoff_setup_replay_no_video_rerun",
        "job_id": args.job_id,
        "asr_artifact": str(asr_artifact),
        "summary": summary,
        "finalists": results,
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V50.1 Payoff Setup Replay Audit Report",
        "",
        "Scope: offline replay only. This audit evaluates a narrow `no_hook_no_payoff` override for already clean or repaired-clean candidates with strong explanatory payoff evidence. No Creator QA thresholds were weakened globally.",
        "",
        "## Summary",
        f"- finalists analyzed: {s['finalists_analyzed']}",
        f"- no_hook_no_payoff_before: {s['no_hook_no_payoff_before']}",
        f"- no_hook_no_payoff_after: {s['no_hook_no_payoff_after']}",
        f"- creator_safe_before: {s['creator_safe_before']}",
        f"- creator_safe_after: {s['creator_safe_after']}",
        f"- predicted_final_clean: {s['predicted_final_clean']}",
        f"- predicted_final_unstable: {s['predicted_final_unstable']}",
        f"- override_count: {s['override_count']}",
        f"- false_positive_risk: {s['false_positive_risk']}",
        f"- video_rerun_justified: {s['video_rerun_justified']}",
        "",
        "## Finalists",
        "| Window | Local/Semantic | Repaired Applied | Payoff Detected | Override | Before Reasons | After Reasons |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["finalists"]:
        lines.append(
            f"| {row['start']} -> {row['end']} | "
            f"{row['local_asr_confidence_label']} / {row['semantic_asr_confidence_label']} | "
            f"{row['v50_repaired_text_applied']} | "
            f"{row['v50_1_payoff_detected']} ({row['v50_1_payoff_reason'] or 'none'}) | "
            f"{row['v50_1_no_hook_no_payoff_override']} | "
            f"{', '.join(row['before_reasons']) or 'none'} | "
            f"{', '.join(row['after_reasons']) or 'none'} |"
        )

    path = Path(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="V50.1 payoff/setup replay audit")
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
    print(f"no_hook_no_payoff_before={s['no_hook_no_payoff_before']}")
    print(f"no_hook_no_payoff_after={s['no_hook_no_payoff_after']}")
    print(f"creator_safe_before={s['creator_safe_before']}")
    print(f"creator_safe_after={s['creator_safe_after']}")
    print(f"predicted_final_clean={s['predicted_final_clean']}")
    print(f"predicted_final_unstable={s['predicted_final_unstable']}")
    print(f"false_positive_risk={s['false_positive_risk']}")
    print(f"video_rerun_justified={s['video_rerun_justified']}")


if __name__ == "__main__":
    main()
