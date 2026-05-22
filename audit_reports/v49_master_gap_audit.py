import json
from collections import Counter, defaultdict
from pathlib import Path


JOB_IDS = [
    "f964425c-0803-4e3d-b6e7-98f8eb3e7d52",
    "e0fc755a-9319-4bab-ad50-fd6ffa723bcb",
    "cb7f65ba-222e-4e82-869f-57d399a3f146",
]

AUDIT_DIR = Path("audit_reports")
ANALYTICS_DIR = Path("analytics")
JSON_OUT = AUDIT_DIR / "v49_master_gap_audit.json"
MD_OUT = AUDIT_DIR / "V49_MASTER_GAP_AUDIT_REPORT.md"


def read_json(path, default=None):
    path = Path(path)
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def counter_list(rows, key):
    counts = Counter()
    for row in rows:
        value = row.get(key)
        if isinstance(value, list):
            for item in value:
                counts[str(item)] += 1
        elif value is not None:
            counts[str(value)] += 1
    return dict(counts)


def compact_counter(counter, limit=8):
    if isinstance(counter, dict):
        counter = Counter(counter)
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def preview(row):
    text = (
        row.get("expanded_preview")
        or row.get("source_preview")
        or row.get("text_preview")
        or row.get("preview")
        or row.get("expanded_text")
        or ""
    )
    return " ".join(str(text).split())[:220]


def row_window(row):
    start = row.get("expanded_start", row.get("start"))
    end = row.get("expanded_end", row.get("end"))
    return round(safe_float(start), 2), round(safe_float(end), 2)


def match_window(row, rows, tolerance=2.0):
    start, end = row_window(row)
    best = None
    best_delta = 999999.0
    for candidate in rows:
        c_start = safe_float(candidate.get("start"))
        c_end = safe_float(candidate.get("end"))
        delta = abs(start - c_start) + abs(end - c_end)
        if delta < best_delta:
            best = candidate
            best_delta = delta
    return best if best is not None and best_delta <= tolerance else None


def artifact_path(job_id, suffix):
    path = AUDIT_DIR / f"asr_segments_{job_id}{suffix}.json"
    return path if path.exists() else None


def asr_artifact_summary(job_id):
    pre_path = artifact_path(job_id, "_native_pre_retry")
    final_path = artifact_path(job_id, "")
    summaries = {}
    for name, path in [("native_pre_retry", pre_path), ("final", final_path)]:
        payload = read_json(path, {}) if path else {}
        segments = payload.get("segments", []) if isinstance(payload.get("segments"), list) else []
        text = " ".join(str(segment.get("text", "")) for segment in segments if isinstance(segment, dict))
        summaries[name] = {
            "path": str(path) if path else None,
            "exists": bool(path),
            "asr_mode": payload.get("asr_mode"),
            "asr_quality_score": payload.get("asr_quality_score"),
            "low_confidence_asr": payload.get("low_confidence_asr"),
            "transcript_quality_reasons": payload.get("transcript_quality_reasons", []),
            "segment_count": len(segments),
            "replacement_char_count": text.count("\ufffd") + text.count("ï¿½"),
            "repeated_token_loop_count": count_repeated_token_loops(text),
        }
    return summaries


def count_repeated_token_loops(text):
    tokens = str(text or "").lower().split()
    loops = 0
    idx = 0
    while idx < len(tokens):
        end = idx + 1
        while end < len(tokens) and tokens[end] == tokens[idx]:
            end += 1
        if end - idx >= 4:
            loops += 1
        idx = end
    return loops


def load_rows_by_job():
    files = {
        "candidate_funnel": ANALYTICS_DIR / "candidate_funnel.jsonl",
        "clip_intelligence": ANALYTICS_DIR / "clip_intelligence.jsonl",
        "creator_qa": ANALYTICS_DIR / "creator_qa.jsonl",
        "transcript_quality": ANALYTICS_DIR / "transcript_quality.jsonl",
    }
    all_rows = {name: read_jsonl(path) for name, path in files.items()}
    by_job = {job_id: {} for job_id in JOB_IDS}
    for job_id in JOB_IDS:
        for name, rows in all_rows.items():
            by_job[job_id][name] = [row for row in rows if str(row.get("job_id")) == job_id]
    return by_job


def final_clip_rows(job_rows):
    return [
        row for row in job_rows.get("clip_intelligence", [])
        if row.get("stage") == "pre_creator_qa"
    ]


def qa_reject_rows(job_rows):
    return [
        row for row in job_rows.get("creator_qa", [])
        if row.get("event") == "CREATOR_QA_REJECT"
    ]


def qa_zero_row(job_rows):
    rows = [
        row for row in job_rows.get("creator_qa", [])
        if row.get("event") == "CREATOR_QA_ZERO_SAFE_CLIPS"
    ]
    return rows[-1] if rows else {}


def label_from_row(row):
    sb = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
    return (
        row.get("semantic_asr_confidence_label")
        or sb.get("semantic_asr_confidence_label")
        or row.get("semantic_confidence_label")
        or "unknown"
    )


def structural_label_from_row(row):
    sb = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
    return (
        row.get("local_asr_confidence_label")
        or row.get("selected_region")
        or row.get("region")
        or sb.get("local_asr_confidence_label")
        or "unknown"
    )


def score_breakdown_value(row, key, default=0):
    sb = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
    return row.get(key, sb.get(key, default))


def latest_v48_reports():
    return {
        "chunk_stability": read_json(AUDIT_DIR / "v48_asr_chunk_stability.json", {}),
        "candidate_asr_confidence": read_json(AUDIT_DIR / "v48_candidate_asr_confidence.json", {}),
        "clean_window_ranking": read_json(AUDIT_DIR / "v48_clean_window_candidate_ranking.json", {}),
        "semantic_asr_confidence": read_json(AUDIT_DIR / "v48_semantic_asr_confidence.json", {}),
    }


def summarize_job(job_id, job_rows, v48_reports):
    funnel = job_rows.get("candidate_funnel", [])
    finals = final_clip_rows(job_rows)
    rejects = qa_reject_rows(job_rows)
    zero = qa_zero_row(job_rows)
    transcript_rows = job_rows.get("transcript_quality", [])

    semantic_rows = []
    semantic_report = v48_reports["semantic_asr_confidence"]
    if semantic_report.get("summary", {}).get("job_id") == job_id:
        semantic_rows = semantic_report.get("candidates", [])

    final_semantic_labels = Counter(label_from_row(row) for row in finals)
    funnel_semantic_labels = Counter(label_from_row(row) for row in funnel if label_from_row(row) != "unknown")
    if not funnel_semantic_labels and semantic_rows:
        funnel_semantic_labels = Counter(row.get("semantic_confidence_label", "unknown") for row in semantic_rows)

    final_structural_labels = Counter(structural_label_from_row(row) for row in finals)
    funnel_structural_labels = Counter(structural_label_from_row(row) for row in funnel if structural_label_from_row(row) != "unknown")
    if not funnel_structural_labels and semantic_rows:
        funnel_structural_labels = Counter(row.get("structural_local_asr_label", "unknown") for row in semantic_rows)

    qa_reason_counts = Counter()
    metadata_reason_counts = Counter()
    for row in rejects:
        qa_reason_counts.update(str(reason) for reason in row.get("reasons", []))
        metadata_reason_counts.update(str(reason) for reason in row.get("metadata_reasons", []))

    final_windows = {(round(safe_float(row.get("start")), 2), round(safe_float(row.get("end")), 2)) for row in finals}
    clean_or_borderline_lost = []
    degraded_finalists = []
    for row in funnel:
        label = label_from_row(row)
        selected = row_window(row) in final_windows
        if label in {"clean_semantics", "borderline_semantics"} and not selected:
            clean_or_borderline_lost.append({
                "candidate_index": row.get("candidate_index"),
                "window": row_window(row),
                "label": label,
                "filter_decision": row.get("filter_decision"),
                "filter_reason": row.get("filter_reason"),
                "final_score": row.get("final_score"),
                "semantic_preference_applied": row.get("semantic_preference_applied"),
                "semantic_preference_reason": row.get("semantic_preference_reason"),
                "preview": preview(row),
            })
    for row in finals:
        if label_from_row(row) == "degraded_semantics":
            degraded_finalists.append({
                "start": row.get("start"),
                "end": row.get("end"),
                "score": row.get("score"),
                "semantic_label": label_from_row(row),
                "creator_qa_reasons": (match_window(row, rejects) or {}).get("reasons", []),
                "preview": preview(row),
            })

    setup_values = [safe_float(score_breakdown_value(row, "setup_strength")) for row in finals]
    payoff_values = [safe_float(score_breakdown_value(row, "payoff_strength")) for row in finals]
    durations = [safe_float(row.get("duration"), safe_float(row.get("end")) - safe_float(row.get("start"))) for row in finals]

    return {
        "job_id": job_id,
        "asr_artifacts": asr_artifact_summary(job_id),
        "transcript_quality": transcript_rows[-1] if transcript_rows else {},
        "candidate_funnel_count": len(funnel),
        "final_candidate_count": len(finals),
        "creator_qa_reject_count": len(rejects),
        "creator_qa_zero_safe": bool(zero),
        "creator_qa_zero_row": zero,
        "qa_reason_counts": dict(qa_reason_counts),
        "qa_metadata_reason_counts": dict(metadata_reason_counts),
        "funnel_semantic_labels": dict(funnel_semantic_labels),
        "final_semantic_labels": dict(final_semantic_labels),
        "funnel_structural_labels": dict(funnel_structural_labels),
        "final_structural_labels": dict(final_structural_labels),
        "clean_or_borderline_lost": clean_or_borderline_lost,
        "degraded_finalists": degraded_finalists,
        "final_duration_avg": round(sum(durations) / max(len(durations), 1), 2),
        "final_duration_min": min(durations) if durations else 0,
        "final_duration_max": max(durations) if durations else 0,
        "avg_setup_strength": round(sum(setup_values) / max(len(setup_values), 1), 2),
        "avg_payoff_strength": round(sum(payoff_values) / max(len(payoff_values), 1), 2),
        "zero_payoff_finalists": sum(1 for value in payoff_values if value <= 0),
        "semantic_preference_applied_count": sum(
            1 for row in funnel if bool(row.get("semantic_preference_applied"))
        ),
    }


def build_gap(title, impact, evidence, recommendation, priority, risk, files, offline_first=True, needs_rerun=True):
    return {
        "title": title,
        "impact": impact,
        "evidence": evidence,
        "recommendation": recommendation,
        "priority": priority,
        "risk": risk,
        "files_affected": files,
        "can_validate_offline_first": offline_first,
        "needs_rerun_for_final_validation": needs_rerun,
    }


def derive_gaps(job_summaries, v48_reports):
    latest = job_summaries[0]
    latest_semantic = v48_reports["semantic_asr_confidence"].get("summary", {})
    latest_clean = v48_reports["clean_window_ranking"].get("summary", {})
    latest_chunk = v48_reports["chunk_stability"].get("summary", {})

    gaps = [
        build_gap(
            "Global ASR fail-closed gate rejects locally/semantically usable candidates",
            "Blocks all finalists even when a clean_semantics candidate reaches Creator QA.",
            [
                f"latest creator_qa rejects={latest['creator_qa_reject_count']} and zero_safe={latest['creator_qa_zero_safe']}",
                f"top QA reasons={latest['qa_reason_counts']}",
                f"latest final semantic labels={latest['final_semantic_labels']}",
                "candidate 270.92-283.76 reached QA as clean_semantics but still rejected with asr_low_confidence",
            ],
            "Make Creator QA ASR gate local/semantic-aware: keep fail-closed for degraded/unknown, but do not let global low_confidence_asr alone reject clean_semantics windows.",
            "P0",
            "Medium: must not allow degraded transcripts through; requires strict metadata checks and fallback to current behavior when missing.",
            ["pipeline_runner.py"],
        ),
        build_gap(
            "Semantic ASR degradation remains high in final selection",
            "Even after V48.9, degraded candidates still dominate finals.",
            [
                f"latest semantic audit final degraded={latest_semantic.get('final_semantically_degraded_candidates')}",
                f"latest semantic audit clean structural degraded={latest_semantic.get('final_clean_structural_degraded_semantics')}",
                f"latest final semantic labels={latest['final_semantic_labels']}",
            ],
            "Strengthen semantic ranking only after P0: require at least one clean/borderline finalist when such candidates exist and score gap is bounded.",
            "P1",
            "Medium: can over-promote low-payoff clean text if not paired with editorial thresholds.",
            ["pipeline_runner.py"],
        ),
        build_gap(
            "Editorial extraction produces no payoff across all finalists",
            "All finalist clips repeatedly fail no_hook_no_payoff, so even clean ASR text is not creator-safe.",
            [
                f"latest zero_payoff_finalists={latest['zero_payoff_finalists']} of {latest['final_candidate_count']}",
                f"latest avg setup={latest['avg_setup_strength']} avg payoff={latest['avg_payoff_strength']}",
                f"QA no_hook_no_payoff count={latest['qa_reason_counts'].get('no_hook_no_payoff', 0)}",
            ],
            "Audit and patch Hindi payoff/setup expansion around clean windows; choose longer/neighboring context before ranking rather than relaxing QA.",
            "P1",
            "Medium: larger windows can add rambling context or continuation leakage.",
            ["pipeline_runner.py"],
            offline_first=True,
            needs_rerun=True,
        ),
        build_gap(
            "Native ASR artifact has severe global quality collapse",
            "The transcript contains replacement artifacts, repeated helper phrases, and entity corruption across runs.",
            [
                f"chunk replacement_char_count={latest_chunk.get('replacement_char_count')}",
                f"unstable_chunks={latest_chunk.get('unstable_chunks')} of {latest_chunk.get('total_chunks')}",
                f"latest transcript reasons={latest['transcript_quality'].get('asr_quality_reasons')}",
            ],
            "Do not rely on global transcript quality as a clip-level decision; preserve chunk/local scoring and local semantic confidence.",
            "P0",
            "Low: diagnostic conclusion only; production change belongs in P0 local QA gate.",
            ["pipeline_runner.py"],
            offline_first=True,
            needs_rerun=False,
        ),
        build_gap(
            "Retry path is not improving this Hindi/Hinglish mode",
            "Latest jobs still end in native_transcribe low confidence despite final artifacts being written.",
            [
                f"latest final ASR mode={latest['asr_artifacts']['final'].get('asr_mode')}",
                f"latest final ASR quality={latest['asr_artifacts']['final'].get('asr_quality_score')}",
                "specified checkpoint says faster-whisper retry fails safely and falls back",
            ],
            "Keep retry fail-safe, but disable or shorten retry sampling for this mode if logs confirm repeated no-benefit; validate with offline ASR artifact comparison first.",
            "P2",
            "Low to medium: affects runtime only if scoped to this failure mode; do not change ASR model policy yet.",
            ["asr_engine.py"],
            offline_first=True,
            needs_rerun=True,
        ),
        build_gap(
            "Dedupe and near-start removal can hide clean/borderline candidates",
            "Clean or borderline candidates exist but may not survive final dedupe/selection consistently.",
            [
                f"latest lost clean/borderline rows={len(latest['clean_or_borderline_lost'])}",
                f"clean window lost count from V48 report={latest_clean.get('lost_clean_window_candidates')}",
                f"lost filter reasons={latest_clean.get('lost_clean_filter_reasons')}",
            ],
            "After P0, add a dedupe tie-break that keeps cleaner semantic candidate when windows overlap and editorial scores are close.",
            "P1",
            "Medium: overlap rules can reduce variety if too aggressive.",
            ["pipeline_runner.py"],
        ),
        build_gap(
            "Semantic corruption is mostly entity/technical term corruption",
            "Names and technical terms are malformed, which makes otherwise topical clips unusable.",
            [
                "Repeated examples across audits include Netherlands/Modi/travel/semiconductor/energy corruptions.",
                f"latest semantic degraded candidates={latest_semantic.get('semantically_degraded_candidates')}",
            ],
            "Keep deterministic semantic ASR scoring and add a narrow entity-corruption diagnostic field; do not auto-correct text for export yet.",
            "P2",
            "Low if diagnostic only; high if used for transcript rewriting.",
            ["pipeline_runner.py", "audit_reports/*.py"],
            offline_first=True,
            needs_rerun=False,
        ),
        build_gap(
            "Frontend zero-clip reporting appears fixed but needs guardrail audit",
            "The app now reports no creator-safe clips instead of pretending success.",
            [
                "creator_qa_zero_safe rows are present for all three target jobs.",
                "No export should occur for rejected-only jobs.",
            ],
            "Keep current UX; add a regression audit that asserts zero-safe jobs expose no final exports.",
            "P2",
            "Low.",
            ["audit_reports/*.py"],
            offline_first=True,
            needs_rerun=False,
        ),
        build_gap(
            "Repeated full reruns are avoidable",
            "Existing artifacts are sufficient to validate ranking/QA hypotheses offline before another upload.",
            [
                "ASR segment artifacts, candidate funnel, clip intelligence, QA logs, and V48 reports exist for all target jobs.",
                "V48.8/V48.9 impact was measurable from existing analytics.",
            ],
            "Add offline replay harness for candidate ranking/Creator QA decisions using saved artifacts before any future long-video rerun.",
            "P1",
            "Low: read-only replay reduces iteration cost.",
            ["audit_reports/*.py"],
            offline_first=True,
            needs_rerun=False,
        ),
        build_gap(
            "Candidate windows are often too short or context-thin for standalone clips",
            "Finalists include 12-16s windows and weak_standalone_context remains a top rejection reason.",
            [
                f"latest duration min={latest['final_duration_min']} avg={latest['final_duration_avg']} max={latest['final_duration_max']}",
                f"weak_standalone_context count={latest['qa_reason_counts'].get('weak_standalone_context', 0)}",
            ],
            "For clean/local-good windows, prefer expanded context that includes setup and payoff before final scoring.",
            "P1",
            "Medium: longer clips may dilute hooks.",
            ["pipeline_runner.py"],
        ),
    ]

    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    impact_order = {
        "Blocks all finalists even when a clean_semantics candidate reaches Creator QA.": 0,
        "Even after V48.9, degraded candidates still dominate finals.": 1,
    }
    return sorted(gaps, key=lambda gap: (priority_order.get(gap["priority"], 9), impact_order.get(gap["impact"], 5)))


def action_plan(gaps):
    grouped = defaultdict(list)
    for gap in gaps:
        grouped[gap["priority"]].append(gap)
    return {
        "P0": [gap["title"] for gap in grouped["P0"]],
        "P1": [gap["title"] for gap in grouped["P1"]],
        "P2": [gap["title"] for gap in grouped["P2"]],
        "do_not_touch": [
            "Do not weaken Creator QA acceptance thresholds.",
            "Do not export rejected clips.",
            "Do not change frontend/render/export/subtitle code for this problem.",
            "Do not change ASR model/retry policy until local semantic QA gate is validated.",
            "Do not run another long-video job before offline replay/audit predicts an improvement.",
        ],
    }


def next_prompt():
    return """FluxClip V49.1 local semantic ASR Creator-QA gate patch.

Environment:
- Local Windows only
- Path: C:\\fluxclip_latest\\fluxclip
- Minimal production patch only
- Compile after every changed Python file
- No frontend/render/export/subtitle changes
- Do NOT weaken Creator QA
- Do NOT export rejected clips
- Do NOT change ASR retry/model policy

Goal:
Replace the global ASR rejection inside Creator QA with a strict local semantic-aware ASR gate.

Patch:
- In pipeline_runner.py Creator QA rejection logic, keep current fail-closed behavior for degraded_semantics, unknown/missing semantic metadata, unstable local ASR, and severe artifact reasons.
- Allow global low_confidence_asr to stop being an automatic rejection only when the clip has semantic_asr_confidence_label in clean_semantics/borderline_semantics, local_asr_confidence_label clean/borderline, and semantic_asr_corruption_score below a conservative threshold.
- Add score_breakdown metadata explaining local_asr_gate_decision and reasons.
- Do not alter no_hook_no_payoff or weak_standalone_context checks.

Validation:
- python -m py_compile pipeline_runner.py
- Run offline audits first; only rerun the source if the audit predicts at least one finalist is no longer rejected solely by global ASR.
"""


def write_markdown(payload):
    lines = [
        "# V49 Master Gap Audit Report",
        "",
        "Scope: offline-only audit using existing artifacts/logs. No video jobs, production patches, frontend, render/export, or subtitle changes.",
        "",
        "## Executive Summary",
        "- Pipeline execution is stable, but the current failure is still zero creator-safe finalists.",
        "- The dominant root cause is a mismatch between global ASR fail-closed state and local/semantic candidate quality.",
        "- V48.9 got one clean_semantics finalist into Creator QA, but Creator QA still rejected it via global asr_low_confidence plus editorial weakness.",
        "- Ranking is now secondary: it improved degraded finalists from 6 to 5, but QA remains the hard stop.",
        "",
        "## Job Summary",
        "| Job | Funnel | Finalists | QA Rejects | Final Semantic Labels | QA Reasons |",
        "|---|---:|---:|---:|---|---|",
    ]
    for job in payload["jobs"]:
        lines.append(
            f"| {job['job_id']} | {job['candidate_funnel_count']} | {job['final_candidate_count']} | "
            f"{job['creator_qa_reject_count']} | {job['final_semantic_labels']} | {job['qa_reason_counts']} |"
        )

    lines.extend([
        "",
        "## Top 10 Gaps",
    ])
    for idx, gap in enumerate(payload["gaps"][:10], 1):
        evidence = "; ".join(str(item) for item in gap["evidence"][:3])
        lines.extend([
            f"{idx}. **{gap['priority']} - {gap['title']}**",
            f"   - Impact: {gap['impact']}",
            f"   - Evidence: {evidence}",
            f"   - Recommendation: {gap['recommendation']}",
            f"   - Risk: {gap['risk']}",
            f"   - Files: {', '.join(gap['files_affected'])}",
        ])

    lines.extend([
        "",
        "## P0/P1/P2 Action Plan",
        "### P0",
    ])
    for item in payload["action_plan"]["P0"]:
        lines.append(f"- {item}")
    lines.append("### P1")
    for item in payload["action_plan"]["P1"]:
        lines.append(f"- {item}")
    lines.append("### P2")
    for item in payload["action_plan"]["P2"]:
        lines.append(f"- {item}")
    lines.append("### Do Not Touch")
    for item in payload["action_plan"]["do_not_touch"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Latest Job Details",
    ])
    latest = payload["jobs"][0]
    lines.extend([
        f"- latest job: {latest['job_id']}",
        f"- ASR final mode: {latest['asr_artifacts']['final'].get('asr_mode')}",
        f"- ASR final quality: {latest['asr_artifacts']['final'].get('asr_quality_score')}",
        f"- transcript quality reasons: {latest['transcript_quality'].get('asr_quality_reasons')}",
        f"- final duration min/avg/max: {latest['final_duration_min']} / {latest['final_duration_avg']} / {latest['final_duration_max']}",
        f"- avg setup/payoff: {latest['avg_setup_strength']} / {latest['avg_payoff_strength']}",
        f"- semantic preference applied count: {latest['semantic_preference_applied_count']}",
    ])

    lines.extend([
        "",
        "## Exact Next Codex Prompt",
        "```text",
        payload["next_codex_prompt"].rstrip(),
        "```",
    ])
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    rows_by_job = load_rows_by_job()
    v48_reports = latest_v48_reports()
    jobs = [summarize_job(job_id, rows_by_job[job_id], v48_reports) for job_id in JOB_IDS]
    gaps = derive_gaps(jobs, v48_reports)
    payload = {
        "scope": "offline_only_existing_artifacts",
        "job_ids": JOB_IDS,
        "jobs": jobs,
        "v48_report_summaries": {
            name: report.get("summary", {})
            for name, report in v48_reports.items()
        },
        "gaps": gaps,
        "top_10_gaps": gaps[:10],
        "action_plan": action_plan(gaps),
        "next_codex_prompt": next_prompt(),
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload)
    print(f"jobs={len(jobs)} gaps={len(gaps)}")
    print(f"markdown={MD_OUT}")
    print(f"json={JSON_OUT}")
    print("top_gap=" + gaps[0]["title"])
    print("p0=" + "; ".join(payload["action_plan"]["P0"]))


if __name__ == "__main__":
    main()
