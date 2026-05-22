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
import v48_semantic_asr_confidence_audit as semantic_audit
from v48_asr_chunk_stability_audit import load_segments, safe_float, tokenize_for_asr_audit
from v48_candidate_asr_confidence_audit import infer_job_id, read_jsonl


DEFAULT_MD_OUT = Path("audit_reports/V49_6_ASR_REPAIR_REPLACE_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v49_6_asr_repair_replace_audit.json")
DEFAULT_CANDIDATE_FUNNEL = Path("analytics/candidate_funnel.jsonl")
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_CREATOR_QA = Path("analytics/creator_qa.jsonl")
DEFAULT_TRANSCRIPT_QUALITY = Path("analytics/transcript_quality.jsonl")

UNSTABLE_LABELS = {
    "replacement_artifact_collapse",
    "local_repetition_collapse",
    "short_fragment_collapse",
    "empty_or_sparse_chunk",
}


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


def normalize_text(text):
    return " ".join(str(text or "").replace("\r", " ").replace("\n", " ").split())


def segment_midpoint(segment):
    start = safe_float(segment.get("start"))
    end = safe_float(segment.get("end"), start)
    return start + max(0.0, end - start) / 2.0


def overlap_seconds(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def selected_window(row):
    expanded_start = row.get("expanded_start")
    expanded_end = row.get("expanded_end")
    if expanded_start is not None and expanded_end is not None:
        start = safe_float(expanded_start)
        end = safe_float(expanded_end)
        if end > start:
            return round(start, 2), round(end, 2), "expanded"
    start = safe_float(row.get("start"))
    end = safe_float(row.get("end"), start)
    return round(start, 2), round(end, 2), "source"


def row_preview(row):
    return normalize_text(
        row.get("expanded_preview")
        or row.get("source_preview")
        or row.get("text_preview")
        or row.get("preview")
        or row.get("text")
        or ""
    )


def row_semantic_label(row):
    sb = row.get("score_breakdown") if isinstance(row.get("score_breakdown"), dict) else {}
    return (
        row.get("semantic_asr_confidence_label")
        or row.get("semantic_confidence_label")
        or sb.get("semantic_asr_confidence_label")
        or "unknown"
    )


def row_semantic_score(row):
    sb = row.get("score_breakdown") if isinstance(row.get("score_breakdown"), dict) else {}
    value = row.get("semantic_asr_corruption_score", sb.get("semantic_asr_corruption_score"))
    if value is None:
        value = row.get("semantic_corruption_score")
    return safe_float(value, None)


def discover_artifacts():
    artifacts = {}
    for path in sorted(Path("audit_reports").glob("asr_segments_*_native_pre_retry.json")):
        job_id = infer_job_id(path)
        artifacts[job_id] = {
            "native_pre_retry": path,
            "final": Path(f"audit_reports/asr_segments_{job_id}.json"),
        }
    return artifacts


def load_rows_by_job(path):
    rows_by_job = {}
    for row in read_jsonl(path):
        job_id = str(row.get("job_id") or "").strip()
        if not job_id:
            continue
        rows_by_job.setdefault(job_id, []).append(row)
    return rows_by_job


def qa_rejection_by_window(rows):
    by_window = {}
    for row in rows:
        if row.get("event") != "CREATOR_QA_REJECT":
            continue
        start = round(safe_float(row.get("start")), 2)
        end = round(safe_float(row.get("end")), 2)
        by_window[(start, end)] = row
    return by_window


def final_windows(rows):
    windows = set()
    for row in rows:
        if row.get("stage") != "pre_creator_qa":
            continue
        start = round(safe_float(row.get("start")), 2)
        end = round(safe_float(row.get("end")), 2)
        windows.add((start, end))
    return windows


def normalize_candidate_rows(job_id, funnel_rows, final_rows, qa_rows):
    candidates = []
    final_window_set = final_windows(final_rows)
    qa_by_window = qa_rejection_by_window(qa_rows)
    seen = set()
    seen_windows = set()

    for row in funnel_rows:
        start, end, basis = selected_window(row)
        key = ("funnel", row.get("candidate_index"), start, end)
        if key in seen:
            continue
        seen.add(key)
        seen_windows.add((start, end))
        qa = qa_by_window.get((start, end), {})
        score = row_semantic_score(row)
        if score is None:
            score = semantic_audit.score_semantic_corruption(row_preview(row))["semantic_corruption_score"]
        candidates.append({
            "job_id": job_id,
            "source": "candidate_funnel",
            "candidate_index": row.get("candidate_index"),
            "start": start,
            "end": end,
            "window_basis": basis,
            "filter_decision": row.get("filter_decision"),
            "filter_reason": row.get("filter_reason"),
            "final_pre_creator_qa_selected": (start, end) in final_window_set,
            "semantic_confidence_label": row_semantic_label(row),
            "semantic_corruption_score": score,
            "creator_qa_reasons": qa.get("reasons", []),
            "preview": row_preview(row)[:220],
        })

    for row in final_rows:
        if row.get("stage") != "pre_creator_qa":
            continue
        start = round(safe_float(row.get("start")), 2)
        end = round(safe_float(row.get("end"), start), 2)
        if (start, end) in seen_windows:
            continue
        key = ("final", start, end)
        if key in seen:
            continue
        seen.add(key)
        seen_windows.add((start, end))
        qa = qa_by_window.get((start, end), {})
        sb = row.get("score_breakdown") if isinstance(row.get("score_breakdown"), dict) else {}
        candidates.append({
            "job_id": job_id,
            "source": "clip_intelligence",
            "candidate_index": sb.get("candidate_funnel_index"),
            "start": start,
            "end": end,
            "window_basis": "final",
            "filter_decision": "accepted",
            "filter_reason": "pre_creator_qa",
            "final_pre_creator_qa_selected": True,
            "semantic_confidence_label": row_semantic_label(row),
            "semantic_corruption_score": row_semantic_score(row) or 0,
            "creator_qa_reasons": qa.get("reasons", []),
            "preview": row_preview(row)[:220],
        })
    return candidates


def build_chunk_texts(segments, chunks):
    details = []
    for chunk in chunks:
        start = safe_float(chunk.get("start"))
        end = safe_float(chunk.get("end"))
        chunk_segments = [
            segment for segment in segments
            if start <= segment_midpoint(segment) < end
        ]
        text = normalize_text(" ".join(str(segment.get("text", "")) for segment in chunk_segments))
        semantic = semantic_audit.score_semantic_corruption(text)
        tokens = tokenize_for_asr_audit(text)
        details.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "label": chunk.get("label"),
            "collapse_score": chunk.get("collapse_score"),
            "segment_count": len(chunk_segments),
            "token_count": len(tokens),
            "text_preview": text[:220],
            "semantic_corruption_score": semantic["semantic_corruption_score"],
            "semantic_confidence_label": semantic["semantic_confidence_label"],
            "semantic_reasons": semantic["semantic_reasons"],
            "replacement_char_count": semantic["replacement_char_count"],
            "repeated_garbage_phrase_count": semantic["repeated_garbage_phrase_count"],
            "broken_named_entity_count": semantic["broken_named_entity_count"],
            "technical_term_corruption_count": semantic["technical_term_corruption_count"],
        })
    return details


def attach_candidate_overlap(chunks, candidates, production_chunks):
    for chunk in chunks:
        c_start = chunk["start"]
        c_end = chunk["end"]
        overlapping = []
        final_overlap_count = 0
        clean_or_borderline_count = 0
        for candidate in candidates:
            overlap = overlap_seconds(c_start, c_end, candidate["start"], candidate["end"])
            if overlap <= 0:
                continue
            stability = pipeline_runner.v48_candidate_asr_stability(
                candidate["start"],
                candidate["end"],
                production_chunks,
            )
            semantic_label = candidate.get("semantic_confidence_label") or "unknown"
            if candidate.get("final_pre_creator_qa_selected"):
                final_overlap_count += 1
            if semantic_label in {"clean_semantics", "borderline_semantics"}:
                clean_or_borderline_count += 1
            overlapping.append({
                "candidate_index": candidate.get("candidate_index"),
                "source": candidate.get("source"),
                "start": candidate["start"],
                "end": candidate["end"],
                "overlap_seconds": round(overlap, 2),
                "final_pre_creator_qa_selected": candidate.get("final_pre_creator_qa_selected"),
                "filter_decision": candidate.get("filter_decision"),
                "semantic_confidence_label": semantic_label,
                "semantic_corruption_score": candidate.get("semantic_corruption_score"),
                "production_local_asr_label": stability["local_asr_confidence_label"],
                "production_unstable_overlap_ratio": stability["unstable_window_overlap_ratio"],
                "creator_qa_reasons": candidate.get("creator_qa_reasons", []),
            })
        chunk["candidate_overlap_count"] = len(overlapping)
        chunk["final_candidate_overlap_count"] = final_overlap_count
        chunk["clean_or_borderline_candidate_overlap_count"] = clean_or_borderline_count
        chunk["candidate_overlaps"] = sorted(
            overlapping,
            key=lambda row: (
                not row["final_pre_creator_qa_selected"],
                -safe_float(row["overlap_seconds"]),
                row["start"],
            ),
        )
    return chunks


def classify_window_action(chunk):
    label = str(chunk.get("label") or "unknown")
    collapse = safe_float(chunk.get("collapse_score"))
    semantic_score = safe_float(chunk.get("semantic_corruption_score"))
    final_count = int(chunk.get("final_candidate_overlap_count") or 0)
    candidate_count = int(chunk.get("candidate_overlap_count") or 0)
    cleanish_count = int(chunk.get("clean_or_borderline_candidate_overlap_count") or 0)

    if label not in UNSTABLE_LABELS:
        return "preserve_stable", "Stable by production helper."
    if final_count or cleanish_count:
        return (
            "repair_first",
            "Unstable chunk overlaps final or clean/borderline semantic candidates; repair could change eligibility.",
        )
    if collapse >= 70 or semantic_score >= 70:
        return (
            "quarantine",
            "Severe structural or semantic corruption with no clean/borderline candidate evidence.",
        )
    if candidate_count:
        return (
            "repair_if_budget_allows",
            "Unstable chunk overlaps candidates, but no clean/borderline semantic signal survived.",
        )
    return "quarantine", "No candidate eligibility evidence; exclude from ranking unless repaired."


def summarize_job(job_id, artifact_paths, row_maps):
    native_path = artifact_paths["native_pre_retry"]
    _, segments = load_segments(native_path)
    production_chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    chunk_details = build_chunk_texts(segments, production_chunks)
    funnel_rows = row_maps["candidate_funnel"].get(job_id, [])
    final_rows = row_maps["clip_intelligence"].get(job_id, [])
    qa_rows = row_maps["creator_qa"].get(job_id, [])
    transcript_rows = row_maps["transcript_quality"].get(job_id, [])
    candidates = normalize_candidate_rows(job_id, funnel_rows, final_rows, qa_rows)
    chunk_details = attach_candidate_overlap(chunk_details, candidates, production_chunks)

    for chunk in chunk_details:
        action, reason = classify_window_action(chunk)
        chunk["recommended_action"] = action
        chunk["recommended_action_reason"] = reason

    unstable_chunks = [chunk for chunk in chunk_details if chunk["label"] in UNSTABLE_LABELS]
    repair_windows = [chunk for chunk in unstable_chunks if chunk["recommended_action"].startswith("repair")]
    quarantine_windows = [chunk for chunk in unstable_chunks if chunk["recommended_action"] == "quarantine"]
    final_candidates = [candidate for candidate in candidates if candidate.get("final_pre_creator_qa_selected")]
    semantic_counts = Counter(candidate.get("semantic_confidence_label") or "unknown" for candidate in candidates)
    final_semantic_counts = Counter(candidate.get("semantic_confidence_label") or "unknown" for candidate in final_candidates)
    chunk_label_counts = Counter(chunk.get("label") or "unknown" for chunk in chunk_details)
    window_action_counts = Counter(chunk.get("recommended_action") for chunk in chunk_details)

    latest_transcript_quality = transcript_rows[-1] if transcript_rows else {}
    final_artifact = artifact_paths["final"] if artifact_paths["final"].exists() else None
    final_artifact_payload = read_json(final_artifact, {}) if final_artifact else {}

    return {
        "job_id": job_id,
        "asr_artifacts": {
            "native_pre_retry": str(native_path),
            "final": str(final_artifact) if final_artifact else None,
            "final_exists": bool(final_artifact),
            "final_asr_mode": final_artifact_payload.get("asr_mode"),
            "final_asr_quality_score": final_artifact_payload.get("asr_quality_score"),
            "final_low_confidence_asr": final_artifact_payload.get("low_confidence_asr"),
        },
        "transcript_quality": latest_transcript_quality,
        "segment_count": len(segments),
        "chunk_label_counts": dict(chunk_label_counts),
        "window_action_counts": dict(window_action_counts),
        "total_chunks": len(chunk_details),
        "unstable_chunk_count": len(unstable_chunks),
        "repair_window_count": len(repair_windows),
        "quarantine_window_count": len(quarantine_windows),
        "candidate_count": len(candidates),
        "final_candidate_count": len(final_candidates),
        "candidate_semantic_label_counts": dict(semantic_counts),
        "final_semantic_label_counts": dict(final_semantic_counts),
        "unstable_windows": unstable_chunks,
        "repair_windows": repair_windows,
        "quarantine_windows": quarantine_windows,
        "final_candidate_impacts": summarize_final_candidate_impacts(final_candidates, production_chunks),
    }


def summarize_final_candidate_impacts(final_candidates, production_chunks):
    rows = []
    for candidate in final_candidates:
        stability = pipeline_runner.v48_candidate_asr_stability(
            candidate["start"],
            candidate["end"],
            production_chunks,
        )
        rows.append({
            "candidate_index": candidate.get("candidate_index"),
            "start": candidate["start"],
            "end": candidate["end"],
            "semantic_confidence_label": candidate.get("semantic_confidence_label"),
            "semantic_corruption_score": candidate.get("semantic_corruption_score"),
            "production_local_asr_label": stability["local_asr_confidence_label"],
            "production_unstable_overlap_ratio": stability["unstable_window_overlap_ratio"],
            "creator_qa_reasons": candidate.get("creator_qa_reasons", []),
            "eligibility_impact": candidate_eligibility_impact(candidate, stability),
        })
    return rows


def candidate_eligibility_impact(candidate, stability):
    semantic_label = candidate.get("semantic_confidence_label")
    qa_reasons = set(candidate.get("creator_qa_reasons") or [])
    if stability["local_asr_confidence_label"] == "unstable":
        return "blocked_by_production_structural_asr"
    if semantic_label == "degraded_semantics":
        return "blocked_by_semantic_corruption_even_if_structurally_clean"
    if "no_hook_no_payoff" in qa_reasons:
        return "still_blocked_by_editorial_payoff_after_asr"
    if "asr_low_confidence" in qa_reasons:
        return "could_become_candidate_after_local_repair_but_needs_qa_replay"
    return "unclear_or_not_blocked"


def strategy_matrix(jobs):
    total_unstable = sum(job["unstable_chunk_count"] for job in jobs)
    total_repair = sum(job["repair_window_count"] for job in jobs)
    total_quarantine = sum(job["quarantine_window_count"] for job in jobs)
    total_final_impacted = sum(
        1 for job in jobs for row in job["final_candidate_impacts"]
        if row["production_local_asr_label"] == "unstable"
    )
    total_degraded_candidates = sum(
        job["candidate_semantic_label_counts"].get("degraded_semantics", 0)
        for job in jobs
    )

    return [
        {
            "rank": 5,
            "strategy": "Current fallback native small",
            "expected_quality_impact": "None; preserves current low-confidence native transcript and known unstable windows.",
            "runtime_cost": "Low current runtime after fallback completes.",
            "implementation_risk": "Low, but leaves P0 quality failure untouched.",
            "production_files_affected": [],
            "offline_validation_first": True,
            "requires_rerun": False,
            "recommendation": "Do not keep as the only path.",
        },
        {
            "rank": 4,
            "strategy": "Disable/skip faster-whisper retry for this known-failing Hindi mode",
            "expected_quality_impact": "No direct transcript quality gain; only avoids no-benefit retry work when logs already predict fallback.",
            "runtime_cost": "Lower for the known-failing mode.",
            "implementation_risk": "Low to medium; runtime policy change can hide future retry improvements if over-broad.",
            "production_files_affected": ["asr_engine.py"],
            "offline_validation_first": True,
            "requires_rerun": True,
            "recommendation": "Secondary runtime patch only after repair/replacement policy is defined.",
        },
        {
            "rank": 2,
            "strategy": "Target only unstable windows for repair/retry",
            "expected_quality_impact": (
                f"High if targeted repair fixes the {total_repair} repair-worthy unstable windows; "
                f"{total_final_impacted} final candidates currently overlap unstable production chunks."
            ),
            "runtime_cost": "Medium; bounded to unstable chunk windows instead of whole-video retry.",
            "implementation_risk": "Medium; repaired windows must remain fail-closed until parity and semantic checks pass.",
            "production_files_affected": ["asr_engine.py", "pipeline_runner.py"],
            "offline_validation_first": True,
            "requires_rerun": True,
            "recommendation": "Strong candidate, but pair with segment-level quarantine so unrepaired windows cannot rank.",
        },
        {
            "rank": 3,
            "strategy": "Target only semantically degraded windows for normalization/repair",
            "expected_quality_impact": (
                f"Medium; {total_degraded_candidates} candidate rows are semantically degraded, "
                "but semantic repair alone cannot make structurally unstable windows safe."
            ),
            "runtime_cost": "Low to medium for deterministic normalization; higher if retranscription is included.",
            "implementation_risk": "Medium to high if normalized text replaces transcript text used for export.",
            "production_files_affected": ["pipeline_runner.py"],
            "offline_validation_first": True,
            "requires_rerun": False,
            "recommendation": "Use as diagnostic metadata after structural repair, not as first production patch.",
        },
        {
            "rank": 6,
            "strategy": "Replace corrupted candidate transcript text with safer cleaned/normalized text when possible",
            "expected_quality_impact": "Potentially high for captions/QA text, but unsafe without audio-backed repair.",
            "runtime_cost": "Low.",
            "implementation_risk": "High; can fabricate clean-looking text and mask ASR failures.",
            "production_files_affected": ["pipeline_runner.py"],
            "offline_validation_first": True,
            "requires_rerun": False,
            "recommendation": "Do not use as first patch; keep replacement diagnostic-only.",
        },
        {
            "rank": 1,
            "strategy": "Segment-level salvage with unstable-window quarantine and targeted repair",
            "expected_quality_impact": (
                f"Highest controlled impact: preserve stable segments, quarantine {total_quarantine} severe windows, "
                f"and repair/retry {total_repair} candidate-relevant unstable windows before ranking."
            ),
            "runtime_cost": "Medium; bounded retry/repair plus cheap local stability metadata.",
            "implementation_risk": "Medium; requires strict metadata and no threshold relaxation.",
            "production_files_affected": ["pipeline_runner.py", "asr_engine.py"],
            "offline_validation_first": True,
            "requires_rerun": True,
            "recommendation": "Best next production patch if implemented fail-closed.",
        },
    ]


def choose_primary_job(jobs, v49_5):
    primary = (
        v49_5.get("parity_corrected_facts", {}).get("job_id")
        or v49_5.get("candidate_270_92_corrected", {}).get("job_id")
    )
    if primary:
        for job in jobs:
            if job["job_id"] == primary:
                return job
    return max(jobs, key=lambda job: (job["repair_window_count"], job["unstable_chunk_count"])) if jobs else None


def build_payload(args):
    artifacts = discover_artifacts()
    row_maps = {
        "candidate_funnel": load_rows_by_job(args.candidate_funnel),
        "clip_intelligence": load_rows_by_job(args.clip_intelligence),
        "creator_qa": load_rows_by_job(args.creator_qa),
        "transcript_quality": load_rows_by_job(args.transcript_quality),
    }
    jobs = []
    for job_id, paths in artifacts.items():
        jobs.append(summarize_job(job_id, paths, row_maps))
    jobs.sort(key=lambda job: job["job_id"])

    v49_5 = read_json("audit_reports/v49_5_corrected_gap_report.json", {})
    parity = read_json("audit_reports/v49_asr_stability_parity.json", {})
    strategies = sorted(strategy_matrix(jobs), key=lambda item: item["rank"])
    primary_job = choose_primary_job(jobs, v49_5)
    top_strategy = strategies[0] if strategies else {}

    payload = {
        "scope": "offline_only_existing_artifacts_no_production_changes",
        "inputs": {
            "native_pre_retry_artifacts": [str(paths["native_pre_retry"]) for paths in artifacts.values()],
            "final_asr_artifacts_considered": [
                str(paths["final"]) for paths in artifacts.values() if paths["final"].exists()
            ],
            "candidate_funnel": str(args.candidate_funnel),
            "clip_intelligence": str(args.clip_intelligence),
            "creator_qa": str(args.creator_qa),
            "transcript_quality": str(args.transcript_quality),
            "corrected_gap_report": "audit_reports/v49_5_corrected_gap_report.json",
            "parity_report": "audit_reports/v49_asr_stability_parity.json",
        },
        "canonical_source_of_truth": {
            "structural_helpers": [
                "pipeline_runner.v48_build_asr_stability_chunks",
                "pipeline_runner.v48_candidate_asr_stability",
            ],
            "parity_status": parity.get("summary", {}),
            "creator_qa_relaxation_allowed": False,
            "asr_threshold_relaxation_allowed": False,
        },
        "summary": {
            "jobs_analyzed": len(jobs),
            "total_unstable_chunks": sum(job["unstable_chunk_count"] for job in jobs),
            "total_repair_windows": sum(job["repair_window_count"] for job in jobs),
            "total_quarantine_windows": sum(job["quarantine_window_count"] for job in jobs),
            "top_recommended_strategy": top_strategy.get("strategy"),
            "best_next_production_patch": "Segment-level salvage with unstable-window quarantine and targeted repair.",
            "risk_level": "Medium",
        },
        "primary_job_id": primary_job["job_id"] if primary_job else None,
        "jobs": jobs,
        "strategy_evaluation": strategies,
        "do_not_touch": [
            "Do not relax Creator QA.",
            "Do not relax ASR stability thresholds.",
            "Do not change frontend/render/export/subtitle code.",
            "Do not switch blindly to a larger Whisper model as the first step.",
            "Do not replace export/caption text with normalized text unless audio-backed repair validates it.",
            "Do not allow unstable windows into candidate ranking unless repaired and revalidated.",
        ],
        "next_patch_prompt": next_patch_prompt(),
    }
    return payload


def next_patch_prompt():
    return (
        "FluxClip V49.7 segment-level ASR salvage and unstable-window quarantine patch.\n\n"
        "Environment:\n"
        "- Local Windows only\n"
        "- Path: C:\\fluxclip_latest\\fluxclip\n"
        "- Minimal production patch only\n"
        "- No frontend/render/export/subtitle changes\n"
        "- Do not weaken Creator QA\n"
        "- Do not relax ASR stability thresholds\n"
        "- Compile every changed Python file\n\n"
        "Context:\n"
        "V49.6 offline audit found the best next strategy is segment-level salvage: preserve stable ASR segments, "
        "quarantine production-helper unstable windows, and target only candidate-relevant unstable windows for repair/retry.\n\n"
        "Patch:\n"
        "- In pipeline_runner.py, use pipeline_runner.v48_build_asr_stability_chunks output before candidate ranking.\n"
        "- Prevent candidates whose selected/expanded window has production local_asr_confidence_label=unstable from ranking unless a repaired transcript segment set exists for that window.\n"
        "- Preserve clean/borderline chunks and stable segments without global transcript rejection.\n"
        "- Add score_breakdown metadata: segment_salvage_decision, quarantined_unstable_windows, repaired_window_required, repaired_window_available.\n"
        "- In asr_engine.py only if needed, add a narrow hook for targeted unstable-window retry/repair; do not change global model policy.\n"
        "- Keep Creator QA fail-closed and unchanged.\n\n"
        "Validation:\n"
        "- python -m py_compile pipeline_runner.py asr_engine.py\n"
        "- Run V48/V49.6 offline audits before any video rerun.\n"
        "- Proceed to a rerun only if offline replay predicts fewer unstable finalists without increasing degraded_semantics finalists.\n"
    )


def format_counts(counts):
    if not counts:
        return "{}"
    return "{" + ", ".join(f"{key}: {value}" for key, value in counts.items()) + "}"


def write_markdown(path, payload):
    summary = payload["summary"]
    primary = next((job for job in payload["jobs"] if job["job_id"] == payload.get("primary_job_id")), None)
    lines = [
        "# V49.6 ASR Repair/Replace Audit Report",
        "",
        "Scope: offline-only audit using existing ASR artifacts/logs. No video rerun, production patch, Creator QA relaxation, ASR threshold relaxation, frontend, render, export, or subtitle changes.",
        "",
        "## Summary",
        f"- jobs analyzed: {summary['jobs_analyzed']}",
        f"- total unstable chunks: {summary['total_unstable_chunks']}",
        f"- repair-worthy unstable windows: {summary['total_repair_windows']}",
        f"- quarantine windows: {summary['total_quarantine_windows']}",
        f"- top recommended strategy: {summary['top_recommended_strategy']}",
        f"- best next production patch: {summary['best_next_production_patch']}",
        f"- risk level: {summary['risk_level']}",
        "",
        "## Canonical Inputs",
        "- structural source of truth: `pipeline_runner.v48_build_asr_stability_chunks` and `pipeline_runner.v48_candidate_asr_stability`",
        f"- parity label mismatches: {payload['canonical_source_of_truth']['parity_status'].get('production_vs_audit_label_mismatches')}",
        f"- parity ratio mismatches: {payload['canonical_source_of_truth']['parity_status'].get('production_vs_audit_ratio_mismatches')}",
        "",
    ]

    if primary:
        lines.extend([
            "## Primary Corrected Job",
            f"- job_id: {primary['job_id']}",
            f"- chunks: {primary['total_chunks']}",
            f"- chunk labels: {format_counts(primary['chunk_label_counts'])}",
            f"- repair windows: {primary['repair_window_count']}",
            f"- quarantine windows: {primary['quarantine_window_count']}",
            f"- candidates/finalists: {primary['candidate_count']} / {primary['final_candidate_count']}",
            f"- candidate semantic labels: {format_counts(primary['candidate_semantic_label_counts'])}",
            f"- final semantic labels: {format_counts(primary['final_semantic_label_counts'])}",
            "",
        ])

        lines.extend([
            "## Unstable Windows",
            "| Window | Label | Collapse | Semantic | Candidates | Finalists | Action |",
            "|---|---|---:|---|---:|---:|---|",
        ])
        for chunk in primary["unstable_windows"]:
            lines.append(
                f"| {chunk['start']} -> {chunk['end']} | {chunk['label']} | "
                f"{chunk['collapse_score']} | {chunk['semantic_confidence_label']}:{chunk['semantic_corruption_score']} | "
                f"{chunk['candidate_overlap_count']} | {chunk['final_candidate_overlap_count']} | "
                f"{chunk['recommended_action']} |"
            )
        lines.append("")

        lines.extend([
            "## Candidate Overlap With Unstable Windows",
            "| Window | Candidate | Final | Semantic | Local ASR | QA Reasons |",
            "|---|---:|---|---|---|---|",
        ])
        for chunk in primary["unstable_windows"]:
            for row in chunk["candidate_overlaps"][:6]:
                reasons = ", ".join(str(reason) for reason in row.get("creator_qa_reasons", [])) or "none"
                lines.append(
                    f"| {chunk['start']} -> {chunk['end']} | {row.get('candidate_index')} | "
                    f"{row.get('final_pre_creator_qa_selected')} | "
                    f"{row.get('semantic_confidence_label')}:{row.get('semantic_corruption_score')} | "
                    f"{row.get('production_local_asr_label')}:{row.get('production_unstable_overlap_ratio')} | "
                    f"{reasons} |"
                )
        lines.append("")

        lines.extend([
            "## Windows Worth Repairing",
            "| Window | Reason |",
            "|---|---|",
        ])
        for chunk in primary["repair_windows"]:
            lines.append(f"| {chunk['start']} -> {chunk['end']} | {chunk['recommended_action_reason']} |")
        lines.append("")

        lines.extend([
            "## Windows To Quarantine",
            "| Window | Reason |",
            "|---|---|",
        ])
        for chunk in primary["quarantine_windows"]:
            lines.append(f"| {chunk['start']} -> {chunk['end']} | {chunk['recommended_action_reason']} |")
        lines.append("")

    lines.extend([
        "## Strategy Evaluation",
        "| Rank | Strategy | Quality Impact | Runtime | Risk | Files | Offline First | Requires Rerun |",
        "|---:|---|---|---|---|---|---|---|",
    ])
    for row in payload["strategy_evaluation"]:
        files = ", ".join(row["production_files_affected"]) or "none"
        lines.append(
            f"| {row['rank']} | {row['strategy']} | {row['expected_quality_impact']} | "
            f"{row['runtime_cost']} | {row['implementation_risk']} | {files} | "
            f"{row['offline_validation_first']} | {row['requires_rerun']} |"
        )

    lines.extend([
        "",
        "## Best Next Production Patch",
        "Segment-level salvage with unstable-window quarantine and targeted repair is the best next patch. It preserves stable segments, prevents unstable windows from ranking unless repaired, and avoids both Creator QA relaxation and ASR threshold relaxation.",
        "",
        "## Do Not Touch",
    ])
    for item in payload["do_not_touch"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Exact Next Patch Prompt",
        "```text",
        payload["next_patch_prompt"].rstrip(),
        "```",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="V49.6 offline unstable-window ASR repair/replace audit")
    parser.add_argument("--candidate-funnel", default=str(DEFAULT_CANDIDATE_FUNNEL))
    parser.add_argument("--clip-intelligence", default=str(DEFAULT_CLIP_INTELLIGENCE))
    parser.add_argument("--creator-qa", default=str(DEFAULT_CREATOR_QA))
    parser.add_argument("--transcript-quality", default=str(DEFAULT_TRANSCRIPT_QUALITY))
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()

    args.candidate_funnel = Path(args.candidate_funnel)
    args.clip_intelligence = Path(args.clip_intelligence)
    args.creator_qa = Path(args.creator_qa)
    args.transcript_quality = Path(args.transcript_quality)

    payload = build_payload(args)
    md_path = Path(args.output_md)
    json_path = Path(args.output_json)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(md_path, payload)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = payload["summary"]
    print(f"jobs_analyzed={summary['jobs_analyzed']}")
    print(f"total_unstable_chunks={summary['total_unstable_chunks']}")
    print(f"repair_windows={summary['total_repair_windows']}")
    print(f"quarantine_windows={summary['total_quarantine_windows']}")
    print(f"top_recommended_strategy={summary['top_recommended_strategy']}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")


if __name__ == "__main__":
    main()
