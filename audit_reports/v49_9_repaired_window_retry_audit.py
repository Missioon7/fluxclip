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

import asr_engine
import pipeline_runner
from v48_asr_chunk_stability_audit import load_segments, safe_float
from v48_candidate_asr_confidence_audit import read_jsonl


DEFAULT_JOB_ID = "2efbe27a-4f64-41aa-9077-6f483e00fc4f"
DEFAULT_CANDIDATE_FUNNEL = Path("analytics/candidate_funnel.jsonl")
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_CREATOR_QA = Path("analytics/creator_qa.jsonl")
DEFAULT_VISUAL_INTELLIGENCE = Path("analytics/visual_intelligence.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V49_9_REPAIRED_WINDOW_RETRY_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v49_9_repaired_window_retry_audit.json")


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


def creator_qa_reasons(job_id, creator_qa_path):
    result = {}
    for row in read_jsonl(creator_qa_path):
        if str(row.get("job_id")) != str(job_id):
            continue
        event = str(row.get("event") or "")
        if event != "CREATOR_QA_REJECT":
            continue
        start = round(safe_float(row.get("start")), 2)
        end = round(safe_float(row.get("end"), start), 2)
        result[(start, end)] = [str(reason) for reason in row.get("reasons", [])]
    return result


def find_video_path(job_id, visual_intelligence_path):
    found = None
    for row in read_jsonl(visual_intelligence_path):
        if str(row.get("job_id")) != str(job_id):
            continue
        path = str(row.get("video_path") or "").strip()
        if path:
            found = path
    return found


def summarize_candidate_row(row, chunks, current_windows):
    start, end = selected_window(row)
    local_asr = pipeline_runner.v48_candidate_asr_stability(start, end, chunks)
    salvage = pipeline_runner.v49_segment_salvage_decision(
        start,
        end,
        local_asr,
        chunks,
        repaired_window_available=False,
    )
    return {
        "candidate_index": row.get("candidate_index"),
        "start": start,
        "end": end,
        "duration": round(end - start, 2),
        "final_score": safe_float(row.get("final_score", row.get("score", 0))),
        "current_finalist": (start, end) in current_windows,
        "filter_decision": row.get("filter_decision"),
        "semantic_asr_confidence_label": (
            row.get("semantic_asr_confidence_label")
            or row.get("semantic_confidence_label")
            or "unknown"
        ),
        "semantic_asr_corruption_score": row.get("semantic_asr_corruption_score"),
        "original_preview": str(row.get("expanded_preview") or row.get("text_preview") or "")[:240],
        "original_local_asr": local_asr,
        "segment_salvage_decision": salvage["segment_salvage_decision"],
        "quarantined_unstable_windows": salvage["quarantined_unstable_windows"],
    }


def strict_window_availability(repaired_local_asr, retry_payload):
    reasons = []
    label = str(repaired_local_asr.get("local_asr_confidence_label") or "unknown")
    overlap = safe_float(repaired_local_asr.get("unstable_window_overlap_ratio"))
    quality = int(retry_payload.get("transcript_quality_score", 0) or 0)
    cleaned_segments = retry_payload.get("cleaned_segments", [])

    if label not in {"clean", "borderline"}:
        reasons.append(f"repaired_local_asr_label={label}")
    if overlap >= 0.20:
        reasons.append(f"repaired_unstable_overlap_ratio={overlap}")
    if quality < 70:
        reasons.append(f"repaired_transcript_quality_score={quality}")
    if retry_payload.get("low_confidence_asr"):
        reasons.append("repaired_transcript_low_confidence_asr")
    if len(cleaned_segments) <= 0:
        reasons.append("repaired_window_has_no_cleaned_segments")

    return len(reasons) == 0, reasons


def strict_export_safety(repaired_local_asr, repaired_semantic, retry_payload):
    reasons = []
    label = str(repaired_local_asr.get("local_asr_confidence_label") or "unknown")
    semantic_label = str(repaired_semantic.get("semantic_asr_confidence_label") or "unknown")
    semantic_score = int(repaired_semantic.get("semantic_asr_corruption_score", 0) or 0)

    if label != "clean":
        reasons.append(f"repair_export_requires_clean_local_asr={label}")
    if retry_payload.get("low_confidence_asr"):
        reasons.append("repair_export_requires_non_low_confidence_asr")
    if semantic_label not in {"clean_semantics", "borderline_semantics"}:
        reasons.append(f"repair_export_semantic_label={semantic_label}")
    if semantic_score > 30:
        reasons.append(f"repair_export_semantic_score={semantic_score}")

    return len(reasons) == 0, reasons


def audit_quarantined_candidate(job_id, candidate, video_path, creator_qa_map):
    retry_payload = asr_engine.transcribe_exact_asr_window(
        video_path,
        candidate["start"],
        candidate["end"],
        keep_audio=False,
    )
    repaired_chunks = pipeline_runner.v48_build_asr_stability_chunks(retry_payload["cleaned_segments"])
    repaired_local_asr = pipeline_runner.v48_candidate_asr_stability(
        0.0,
        retry_payload["duration"],
        repaired_chunks,
    )
    repaired_semantic = pipeline_runner.v48_semantic_asr_confidence(retry_payload["repaired_text"])
    repaired_window_available, availability_reasons = strict_window_availability(
        repaired_local_asr,
        retry_payload,
    )
    repair_export_safe, export_reasons = strict_export_safety(
        repaired_local_asr,
        repaired_semantic,
        retry_payload,
    )
    current_reject_reasons = creator_qa_map.get((candidate["start"], candidate["end"]), [])
    remaining_non_asr_reasons = [
        reason for reason in current_reject_reasons
        if reason != "asr_low_confidence"
    ]
    would_be_creator_safe = repair_export_safe and not remaining_non_asr_reasons

    artifact_payload = {
        "version": "v49_9_repaired_window_v1",
        "job_id": job_id,
        "start": candidate["start"],
        "end": candidate["end"],
        "duration": candidate["duration"],
        "video_path": video_path,
        "candidate_index": candidate["candidate_index"],
        "original_local_asr_label": candidate["original_local_asr"]["local_asr_confidence_label"],
        "original_unstable_overlap_ratio": candidate["original_local_asr"]["unstable_window_overlap_ratio"],
        "original_semantic_label": candidate["semantic_asr_confidence_label"],
        "original_semantic_score": candidate.get("semantic_asr_corruption_score"),
        "original_preview": candidate["original_preview"],
        "repaired_text": retry_payload["repaired_text"],
        "repaired_local_asr_label": repaired_local_asr["local_asr_confidence_label"],
        "repaired_unstable_overlap_ratio": repaired_local_asr["unstable_window_overlap_ratio"],
        "repaired_transcript_quality_score": retry_payload["transcript_quality_score"],
        "repaired_low_confidence_asr": retry_payload["low_confidence_asr"],
        "repaired_semantic_label": repaired_semantic["semantic_asr_confidence_label"],
        "repaired_semantic_score": repaired_semantic["semantic_asr_corruption_score"],
        "repaired_window_available": repaired_window_available,
        "repair_export_safe": repair_export_safe,
        "repair_decision_reason": (
            "validated_audio_backed_repair_available"
            if repaired_window_available
            else "audio_backed_repair_failed_strict_availability_gate"
        ),
        "v49_9_repair_strict_reasons": sorted(set(availability_reasons + export_reasons)),
        "current_creator_qa_reasons": current_reject_reasons,
        "remaining_non_asr_creator_qa_reasons": remaining_non_asr_reasons,
        "would_be_creator_safe_after_asr_repair": would_be_creator_safe,
    }
    artifact_path = asr_engine.write_v49_9_repaired_window_artifact(artifact_payload)

    return {
        **artifact_payload,
        "artifact_path": str(artifact_path),
        "repaired_segments": len(retry_payload["cleaned_segments"]),
        "repaired_chunks": repaired_chunks,
        "repaired_transcript_quality_reasons": retry_payload["transcript_quality_reasons"],
        "repaired_local_asr_reasons": repaired_local_asr["local_asr_reasons"],
        "repaired_semantic_reasons": repaired_semantic["semantic_asr_reasons"],
    }


def build_payload(args):
    asr_artifact = find_asr_artifact(args.job_id)
    if not asr_artifact:
        raise SystemExit(f"No ASR artifact found for job_id={args.job_id}")
    video_path = find_video_path(args.job_id, args.visual_intelligence)
    if not video_path or not Path(video_path).exists():
        raise SystemExit(f"Source video not found for job_id={args.job_id}: {video_path}")

    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    rows = replayable_rows(args.job_id, args.candidate_funnel)
    current_windows = current_final_windows(args.job_id, args.clip_intelligence)
    creator_qa_map = creator_qa_reasons(args.job_id, args.creator_qa)

    annotated = [summarize_candidate_row(row, chunks, current_windows) for row in rows]
    quarantined_finalists = [
        row for row in annotated
        if row["current_finalist"] and row["segment_salvage_decision"] == "quarantined_unstable"
    ]
    quarantined_finalists.sort(key=lambda row: row["final_score"], reverse=True)

    repaired_results = []
    failures = []
    for candidate in quarantined_finalists:
        try:
            repaired_results.append(audit_quarantined_candidate(args.job_id, candidate, video_path, creator_qa_map))
        except Exception as e:
            failures.append({
                "candidate_index": candidate["candidate_index"],
                "start": candidate["start"],
                "end": candidate["end"],
                "error": str(e),
            })

    repaired_window_available = sum(1 for row in repaired_results if row["repaired_window_available"])
    repair_export_safe = sum(1 for row in repaired_results if row["repair_export_safe"])
    would_be_creator_safe = sum(1 for row in repaired_results if row["would_be_creator_safe_after_asr_repair"])
    predicted_final_clean = sum(
        1
        for row in repaired_results
        if row["repaired_window_available"]
        and row["repaired_local_asr_label"] == "clean"
    )

    return {
        "scope": "offline_audio_backed_repaired_window_retry_no_full_video_rerun",
        "job_id": args.job_id,
        "asr_artifact": str(asr_artifact),
        "video_path": video_path,
        "source_of_truth": [
            "pipeline_runner.v48_build_asr_stability_chunks",
            "pipeline_runner.v48_candidate_asr_stability",
            "pipeline_runner.v49_segment_salvage_decision",
            "asr_engine.transcribe_exact_asr_window",
        ],
        "summary": {
            "current_quarantined_finalists": len(quarantined_finalists),
            "audio_backed_repairs_completed": len(repaired_results),
            "audio_backed_repairs_failed": len(failures),
            "repaired_window_available_candidates": repaired_window_available,
            "repair_export_safe_candidates": repair_export_safe,
            "would_be_creator_safe_after_asr_repair": would_be_creator_safe,
            "predicted_final_clean_from_repaired_windows": predicted_final_clean,
            "predicted_final_unstable_from_repaired_windows": max(
                0,
                len(quarantined_finalists) - repaired_window_available,
            ),
            "video_rerun_justified": repaired_window_available > 0,
        },
        "current_quarantined_finalists": quarantined_finalists,
        "repaired_window_results": repaired_results,
        "repair_failures": failures,
        "design": {
            "flow": [
                "extract exact candidate expanded window from source MP4",
                "retry ASR only on quarantined unstable finalists",
                "score repaired transcript with existing transcript_quality_score",
                "recompute repaired local stability with production helpers",
                "set repaired_window_available only if repaired window becomes clean or borderline and transcript is not low confidence",
                "set repair_export_safe only if repaired transcript is clean-local-ASR and semantically clean or borderline",
            ],
            "safety": [
                "no Creator QA relaxation",
                "no ASR threshold relaxation",
                "no normalized metadata used as export text",
                "no frontend/render/export/subtitle changes",
                "pipeline remains fail-closed without validated repair artifact",
            ],
        },
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V49.9 Repaired Window Retry Audit Report",
        "",
        "Scope: offline only. This audit extracts exact audio windows for the quarantined unstable finalists, retries ASR on those windows, and writes fail-closed repair artifacts. No full video rerun, no Creator QA relaxation, and no threshold relaxation were performed.",
        "",
        "## Summary",
        f"- job_id: {payload['job_id']}",
        f"- current quarantined finalists: {s['current_quarantined_finalists']}",
        f"- audio-backed repairs completed: {s['audio_backed_repairs_completed']}",
        f"- audio-backed repairs failed: {s['audio_backed_repairs_failed']}",
        f"- repaired window available candidates: {s['repaired_window_available_candidates']}",
        f"- repair export safe candidates: {s['repair_export_safe_candidates']}",
        f"- would be creator-safe after ASR repair: {s['would_be_creator_safe_after_asr_repair']}",
        f"- predicted final clean from repaired windows: {s['predicted_final_clean_from_repaired_windows']}",
        f"- predicted final unstable from repaired windows: {s['predicted_final_unstable_from_repaired_windows']}",
        f"- video rerun justified: {s['video_rerun_justified']}",
        "",
        "## Quarantined Finalists",
        "| Candidate | Window | Score | Original Local ASR | Original Semantic | Unstable Windows |",
        "|---:|---|---:|---|---|---|",
    ]
    for row in payload["current_quarantined_finalists"]:
        unstable_windows = ", ".join(
            f"{item['start']} -> {item['end']} ({item['label']})"
            for item in row["quarantined_unstable_windows"]
        ) or "none"
        lines.append(
            f"| {row['candidate_index']} | {row['start']} -> {row['end']} | {row['final_score']} | "
            f"{row['original_local_asr']['local_asr_confidence_label']}:{row['original_local_asr']['unstable_window_overlap_ratio']} | "
            f"{row['semantic_asr_confidence_label']} | {unstable_windows} |"
        )

    lines.extend([
        "",
        "## Audio-Backed Repair Results",
        "| Candidate | Window | Repaired Local ASR | Quality | Semantic | Available | Export Safe | Creator-Safe After ASR |",
        "|---:|---|---|---:|---|---|---|---|",
    ])
    for row in payload["repaired_window_results"]:
        lines.append(
            f"| {row['candidate_index']} | {row['start']} -> {row['end']} | "
            f"{row['repaired_local_asr_label']}:{row['repaired_unstable_overlap_ratio']} | "
            f"{row['repaired_transcript_quality_score']} | "
            f"{row['repaired_semantic_label']}:{row['repaired_semantic_score']} | "
            f"{row['repaired_window_available']} | {row['repair_export_safe']} | "
            f"{row['would_be_creator_safe_after_asr_repair']} |"
        )

    lines.extend([
        "",
        "## Repair Decisions",
        "| Candidate | Availability Reason | Remaining Non-ASR QA Reasons | Artifact |",
        "|---:|---|---|---|",
    ])
    for row in payload["repaired_window_results"]:
        lines.append(
            f"| {row['candidate_index']} | {row['repair_decision_reason']} | "
            f"{', '.join(row['remaining_non_asr_creator_qa_reasons']) or 'none'} | "
            f"`{row['artifact_path']}` |"
        )

    if payload["repair_failures"]:
        lines.extend([
            "",
            "## Repair Failures",
            "| Candidate | Window | Error |",
            "|---:|---|---|",
        ])
        for row in payload["repair_failures"]:
            lines.append(
                f"| {row['candidate_index']} | {row['start']} -> {row['end']} | {row['error']} |"
            )

    lines.extend([
        "",
        "## Best Next Production Patch",
        "Use the new per-window repair artifacts only as a fail-closed gating input inside `build_final_clips()`. Do not enable ranking from repaired windows unless the artifact says `repaired_window_available=true`. Do not treat `repair_export_safe=true` as a Creator QA bypass; non-ASR Creator QA reasons still apply.",
        "",
        "## Do Not Touch",
        "- Do not weaken Creator QA.",
        "- Do not relax ASR stability thresholds.",
        "- Do not substitute V49.8 normalized metadata for export text.",
        "- Do not rerun a full video job until the exact-window repair evidence justifies it.",
        "- Do not alter frontend, render, export, or subtitle code.",
    ])

    path = Path(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="V49.9 repaired-window exact-audio retry audit")
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID)
    parser.add_argument("--candidate-funnel", type=Path, default=DEFAULT_CANDIDATE_FUNNEL)
    parser.add_argument("--clip-intelligence", type=Path, default=DEFAULT_CLIP_INTELLIGENCE)
    parser.add_argument("--creator-qa", type=Path, default=DEFAULT_CREATOR_QA)
    parser.add_argument("--visual-intelligence", type=Path, default=DEFAULT_VISUAL_INTELLIGENCE)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    return parser.parse_args()


def main():
    args = parse_args()
    payload = build_payload(args)
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(args.md_out, payload)
    summary = payload["summary"]
    print(f"current_quarantined_finalists={summary['current_quarantined_finalists']}")
    print(f"audio_backed_repairs_completed={summary['audio_backed_repairs_completed']}")
    print(f"repaired_window_available_candidates={summary['repaired_window_available_candidates']}")
    print(f"repair_export_safe_candidates={summary['repair_export_safe_candidates']}")
    print(f"would_be_creator_safe_after_asr_repair={summary['would_be_creator_safe_after_asr_repair']}")
    print(f"video_rerun_justified={summary['video_rerun_justified']}")


if __name__ == "__main__":
    main()
