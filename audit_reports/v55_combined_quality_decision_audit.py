import json
import re
from pathlib import Path


AUDIT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = AUDIT_DIR / "v55_combined_quality_decision_audit.json"
DEFAULT_MD_OUT = AUDIT_DIR / "V55_COMBINED_QUALITY_DECISION_AUDIT_REPORT.md"
V54_1_JSON = AUDIT_DIR / "v54_1_unscored_source_preflight_audit.json"

REPORT_FILES = [
    "V49_7_SALVAGE_REPLAY_AUDIT_REPORT.md",
    "V49_8_TARGETED_ASR_REPAIR_REPLAY_AUDIT_REPORT.md",
    "V49_9_REPAIRED_WINDOW_RETRY_AUDIT_REPORT.md",
    "V50_REPAIRED_TEXT_REPLAY_AUDIT_REPORT.md",
    "V50_1_PAYOFF_SETUP_REPLAY_AUDIT_REPORT.md",
    "V50_2_CONTEXT_SHAPING_REPLAY_AUDIT_REPORT.md",
    "V50_3_ADJACENT_CONTEXT_REPAIR_AUDIT_REPORT.md",
    "V51_FRESH_SOURCE_VALIDATION_AUDIT_REPORT.md",
    "V52_PAYOFF_NATIVE_GENERATION_AUDIT_REPORT.md",
    "V53_SOURCE_QUALITY_GATE_AUDIT_REPORT.md",
    "V54_MULTI_SOURCE_BENCHMARK_AUDIT_REPORT.md",
    "V54_1_UNSCORED_SOURCE_PREFLIGHT_AUDIT_REPORT.md",
]


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def extract_summary_bullets(markdown_text):
    bullets = {}
    in_summary = False
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Summary"):
            in_summary = True
            continue
        if stripped.startswith("## ") and in_summary:
            break
        if not in_summary and stripped.startswith("- "):
            key, sep, value = stripped[2:].partition(":")
            if sep and key.strip() not in bullets:
                bullets[key.strip()] = value.strip()
        elif in_summary and stripped.startswith("- "):
            key, sep, value = stripped[2:].partition(":")
            if sep and key.strip() not in bullets:
                bullets[key.strip()] = value.strip()
    return bullets


def parse_int(value, default=0):
    match = re.search(r"-?\d+", str(value))
    return int(match.group(0)) if match else default


def parse_bool(value):
    return str(value).strip().lower() == "true"


def load_report_summaries():
    summaries = {}
    for report_name in REPORT_FILES:
        path = AUDIT_DIR / report_name
        summaries[report_name] = extract_summary_bullets(read_text(path))
    return summaries


def classify_findings(v54_1_payload, summaries):
    v49_8 = summaries["V49_8_TARGETED_ASR_REPAIR_REPLAY_AUDIT_REPORT.md"]
    v49_9 = summaries["V49_9_REPAIRED_WINDOW_RETRY_AUDIT_REPORT.md"]
    v50 = summaries["V50_REPAIRED_TEXT_REPLAY_AUDIT_REPORT.md"]
    v50_1 = summaries["V50_1_PAYOFF_SETUP_REPLAY_AUDIT_REPORT.md"]
    v50_2 = summaries["V50_2_CONTEXT_SHAPING_REPLAY_AUDIT_REPORT.md"]
    v50_3 = summaries["V50_3_ADJACENT_CONTEXT_REPAIR_AUDIT_REPORT.md"]
    v51 = summaries["V51_FRESH_SOURCE_VALIDATION_AUDIT_REPORT.md"]
    v52 = summaries["V52_PAYOFF_NATIVE_GENERATION_AUDIT_REPORT.md"]
    v54_1_summary = v54_1_payload["summary"]

    source_rows = v54_1_payload.get("sources", [])
    poor_source_jobs = [row["job_id"] for row in source_rows if row.get("metrics", {}).get("source_quality_label") == "poor"]
    dominant_reasons = sorted({
        row.get("metrics", {}).get("dominant_failure_reason")
        for row in source_rows
        if row.get("metrics")
    })
    dominant_reasons = [reason for reason in dominant_reasons if reason]

    working = [
        "Fail-closed ASR quarantine and salvage logic reduce unstable finalists without weakening Creator QA.",
        "Targeted and audio-backed ASR repair can improve local ASR and semantic cleanliness on some exact windows.",
        "Resume-safe source preflight now scores raw sources one at a time and reuses existing ASR artifacts.",
        "Source-quality scoring is consistently identifying weak uploads before any full-generation run.",
    ]

    still_failing = [
        "Creator-safe output remains zero across the repair, replay, and fresh-source audits.",
        "The batch still has no source rated good or borderline after V54.1 completed all five unscored sources.",
        "Payoff and standalone-context failures persist after repaired text replay, payoff override replay, and context shaping replay.",
        "No audit in this chain justifies full generation on the current batch.",
    ]

    asr_source_failures = [
        f"V49.9 completed only {parse_int(v49_9.get('audio-backed repairs completed'))} audio-backed repairs while {parse_int(v49_9.get('audio-backed repairs failed'))} failed, so ASR cleanup is partial.",
        f"V51 fresh-source validation still showed asr_quality_score={v51.get('asr_quality_score')} with low_confidence_asr={v51.get('low_confidence_asr')}.",
        f"V54.1 finished with sources_completed={v54_1_summary['sources_completed']}, good_sources={v54_1_summary['good_sources']}, borderline_sources={v54_1_summary['borderline_sources']}, poor_sources={v54_1_summary['poor_sources']}.",
        f"Observed source-quality dominant failures across V54.1: {', '.join(dominant_reasons) if dominant_reasons else 'unknown'}.",
    ]

    payoff_context_failures = [
        f"V50 repaired-text replay kept creator_safe_after={v50.get('creator_safe_after')} and no_hook_no_payoff_after={v50.get('no_hook_no_payoff_after')}.",
        f"V50.1 payoff setup replay found override_count={v50_1.get('override_count')} and creator_safe_after={v50_1.get('creator_safe_after')}.",
        f"V50.2 context shaping replay expanded {v50_2.get('candidates_expanded')} candidates and still left creator_safe_after={v50_2.get('creator_safe_after')}.",
        f"V50.3 adjacent context repair produced context_expansion_possible_after_repair={v50_3.get('context_expansion_possible_after_repair')}.",
        f"V52 payoff-native generation found payoff_anchors_found={v52.get('payoff_anchors_found')} and candidates_generated_from_payoff={v52.get('candidates_generated_from_payoff')}.",
    ]

    batch_assessment = {
        "worth_full_generation": False,
        "reason": (
            "No source in the completed V54.1 batch is good or borderline, and the repair/replay chain never produced creator-safe candidates."
        ),
        "poor_source_jobs": poor_source_jobs,
    }

    return {
        "working": working,
        "still_failing": still_failing,
        "asr_source_quality_failures": asr_source_failures,
        "payoff_context_failures": payoff_context_failures,
        "batch_assessment": batch_assessment,
    }


def choose_recommendation(v54_1_payload, summaries):
    v54_1_summary = v54_1_payload["summary"]
    if (
        v54_1_summary.get("sources_completed") == 5
        and v54_1_summary.get("good_sources") == 0
        and v54_1_summary.get("borderline_sources") == 0
        and v54_1_summary.get("poor_sources") == 5
        and v54_1_summary.get("best_source_for_full_generation") is None
    ):
        return "collect_stronger_sources"

    if v54_1_summary.get("good_sources", 0) > 0 or v54_1_summary.get("borderline_sources", 0) > 0:
        return "run_full_generation_on_best_source"

    v49_9 = summaries["V49_9_REPAIRED_WINDOW_RETRY_AUDIT_REPORT.md"]
    if parse_bool(v49_9.get("repair export safe candidates")) and parse_int(v49_9.get("would be creator-safe after ASR repair")) > 0:
        return "production_wire_source_preflight_gate"

    return "collect_stronger_sources"


def build_payload():
    summaries = load_report_summaries()
    v54_1_payload = read_json(V54_1_JSON)
    findings = classify_findings(v54_1_payload, summaries)
    recommendation = choose_recommendation(v54_1_payload, summaries)

    return {
        "reports_used": REPORT_FILES,
        "recommendation": recommendation,
        "decision_constraints": {
            "do_not_weaken_creator_qa": True,
            "do_not_relax_asr_thresholds": True,
            "do_not_patch_candidate_generation": True,
            "do_not_run_full_generation_on_this_batch": True,
        },
        "v54_1_batch_summary": v54_1_payload["summary"],
        "findings": findings,
        "source_quality_snapshot": [
            {
                "job_id": row["job_id"],
                "label": row.get("metrics", {}).get("source_quality_label"),
                "score": row.get("metrics", {}).get("source_quality_score"),
                "likely_clip_yield": row.get("metrics", {}).get("likely_clip_yield"),
                "dominant_failure_reason": row.get("metrics", {}).get("dominant_failure_reason"),
                "creator_safe_count": row.get("metrics", {}).get("creator_safe_count"),
            }
            for row in v54_1_payload.get("sources", [])
        ],
        "report_summaries": summaries,
    }


def write_markdown(path, payload):
    batch = payload["v54_1_batch_summary"]
    findings = payload["findings"]
    lines = [
        "# V55 Combined Quality Decision Audit Report",
        "",
        "Scope: combined audit-only decision across V49.7 through V54.1. No Creator QA weakening, no ASR threshold relaxation, no candidate-generation patch, and no full generation were performed.",
        "",
        "## Final Decision",
        f"- recommendation: {payload['recommendation']}",
        f"- worth_full_generation: {findings['batch_assessment']['worth_full_generation']}",
        f"- reason: {findings['batch_assessment']['reason']}",
        "",
        "## Batch Summary",
        f"- sources_completed: {batch['sources_completed']}",
        f"- good_sources: {batch['good_sources']}",
        f"- borderline_sources: {batch['borderline_sources']}",
        f"- poor_sources: {batch['poor_sources']}",
        f"- best_source_for_full_generation: {batch['best_source_for_full_generation']}",
        f"- expected_clip_yield: {batch['expected_clip_yield']}",
        "",
        "## What Is Working",
    ]
    for item in findings["working"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## What Is Still Failing",
    ])
    for item in findings["still_failing"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## ASR And Source-Quality Failures",
    ])
    for item in findings["asr_source_quality_failures"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Payoff And Context Failures",
    ])
    for item in findings["payoff_context_failures"]:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Source Snapshot",
        "",
        "| Job | Label | Score | Yield | Dominant Failure | Creator-Safe Count |",
        "|---|---|---:|---|---|---:|",
    ])
    for row in payload["source_quality_snapshot"]:
        lines.append(
            f"| {row['job_id']} | {row['label']} | {row['score']} | {row['likely_clip_yield']} | "
            f"{row['dominant_failure_reason']} | {row['creator_safe_count']} |"
        )

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    payload = build_payload()
    DEFAULT_JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(DEFAULT_MD_OUT, payload)
    print(f"recommendation={payload['recommendation']}")
    print(f"sources_completed={payload['v54_1_batch_summary']['sources_completed']}")
    print(f"good_sources={payload['v54_1_batch_summary']['good_sources']}")
    print(f"borderline_sources={payload['v54_1_batch_summary']['borderline_sources']}")
    print(f"poor_sources={payload['v54_1_batch_summary']['poor_sources']}")


if __name__ == "__main__":
    main()
