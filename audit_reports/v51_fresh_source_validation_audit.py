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

from v48_candidate_asr_confidence_audit import read_jsonl


DEFAULT_JOB_ID = "v51_fresh_source_23f21012"
DEFAULT_BASELINE_JOB_ID = "23f21012-b025-4521-93c0-e13d15271343"
DEFAULT_MD_OUT = Path("audit_reports/V51_FRESH_SOURCE_VALIDATION_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v51_fresh_source_validation_audit.json")


def rows_for_job(path, job_id):
    rows = []
    for row in read_jsonl(path):
        if str(row.get("job_id")) == str(job_id):
            rows.append(row)
    return rows


def first_transcript_quality(job_id):
    rows = rows_for_job(Path("analytics/transcript_quality.jsonl"), job_id)
    for row in rows:
        if "asr_quality_score" in row:
            return row
    return {}


def candidate_rows(job_id):
    return rows_for_job(Path("analytics/candidate_funnel.jsonl"), job_id)


def pre_creator_rows(job_id):
    rows = []
    for row in rows_for_job(Path("analytics/clip_intelligence.jsonl"), job_id):
        if row.get("stage") == "pre_creator_qa":
            rows.append(row)
    return rows


def creator_qa_rows(job_id):
    return rows_for_job(Path("analytics/creator_qa.jsonl"), job_id)


def salvage_rows(job_id):
    path = Path("analytics/asr_segment_salvage.jsonl")
    if not path.exists():
        return []
    return rows_for_job(path, job_id)


def summarize_rejections(rows):
    counter = Counter()
    for row in rows:
        if row.get("event") != "CREATOR_QA_REJECT":
            continue
        for reason in row.get("reasons", []):
            counter[str(reason)] += 1
    return counter


def final_clips_count(job_id):
    prefix = f"{job_id}_final_"
    return len(list(Path("uploads").glob(f"{prefix}*.mp4")))


def helped_or_overblocked(current, baseline):
    if current["creator_safe_count"] > baseline["creator_safe_count"]:
        return "helped"
    if current["creator_safe_count"] == baseline["creator_safe_count"] == 0:
        if current["candidates_quarantined"] > 0 and current["final_clips_count"] == 0:
            return "helped_not_overblocked"
        return "inconclusive"
    if current["candidates_found"] < baseline["candidates_found"] and current["creator_safe_count"] < baseline["creator_safe_count"]:
        return "over_blocked"
    return "inconclusive"


def build_summary(job_id, baseline_job_id):
    tq = first_transcript_quality(job_id)
    funnel = candidate_rows(job_id)
    pre_creator = pre_creator_rows(job_id)
    creator = creator_qa_rows(job_id)
    salvage = salvage_rows(job_id)
    rejection_counter = summarize_rejections(creator)

    current = {
        "job_id": job_id,
        "asr_mode": tq.get("asr_mode"),
        "asr_quality_score": tq.get("asr_quality_score"),
        "low_confidence_asr": tq.get("low_confidence_asr"),
        "asr_quality_reasons": tq.get("asr_quality_reasons", [])[:5],
        "candidates_found": len(funnel),
        "candidates_quarantined": sum(1 for row in funnel if row.get("filter_decision") == "asr_segment_quarantined"),
        "repaired_window_needed": sum(1 for row in funnel if row.get("repaired_window_required") is True),
        "pre_creator_qa_candidates": len(pre_creator),
        "creator_safe_count": sum(1 for row in creator if row.get("event") == "CREATOR_QA_APPROVED"),
        "rejection_reasons": rejection_counter.most_common(),
        "final_clips_count": final_clips_count(job_id),
        "salvage_allowed_clean": sum(1 for row in salvage if row.get("segment_salvage_decision") == "allowed_clean"),
        "salvage_allowed_borderline": sum(1 for row in salvage if row.get("segment_salvage_decision") == "allowed_borderline"),
        "salvage_quarantined_unstable": sum(1 for row in salvage if row.get("segment_salvage_decision") == "quarantined_unstable"),
    }

    baseline_creator = creator_qa_rows(baseline_job_id)
    baseline = {
        "job_id": baseline_job_id,
        "asr_mode": first_transcript_quality(baseline_job_id).get("asr_mode"),
        "asr_quality_score": first_transcript_quality(baseline_job_id).get("asr_quality_score"),
        "low_confidence_asr": first_transcript_quality(baseline_job_id).get("low_confidence_asr"),
        "candidates_found": len(pre_creator_rows(baseline_job_id)),
        "creator_safe_count": sum(1 for row in baseline_creator if row.get("event") == "CREATOR_QA_APPROVED"),
        "rejection_reasons": summarize_rejections(baseline_creator).most_common(),
        "final_clips_count": final_clips_count(baseline_job_id),
    }
    current["v49_7_to_v50_3_assessment"] = helped_or_overblocked(current, baseline)
    return {
        "current": current,
        "baseline_same_source": baseline,
    }


def next_patch_recommendation(summary):
    current = summary["current"]
    if current["creator_safe_count"] > 0:
        return {
            "recommendation": "no_patch_before_more_validation",
            "reason": "fresh source produced creator-safe clips"
        }
    if current["candidates_quarantined"] > 0 and current["pre_creator_qa_candidates"] > 0:
        return {
            "recommendation": "target_payoff_candidate_generation_on_clean_or_borderline_windows",
            "reason": "ASR quarantine removed unstable junk, but surviving clean/borderline candidates still fail on no_hook_no_payoff"
        }
    if current["candidates_quarantined"] > 0 and current["pre_creator_qa_candidates"] == 0:
        return {
            "recommendation": "target_audio_backed_repair_for_unstable_windows",
            "reason": "current pipeline is blocked at unstable-window quarantine before usable finalists survive"
        }
    return {
        "recommendation": "collect_second_clean_source_before_patch",
        "reason": "fresh-source evidence is too weak or mixed"
    }


def write_markdown(path, payload):
    current = payload["summary"]["current"]
    baseline = payload["summary"]["baseline_same_source"]
    rec = payload["next_patch_recommendation"]
    lines = [
        "# V51 Fresh Source Validation Audit Report",
        "",
        "Scope: one fresh validation run on a cleaner source than the V50.x audit sample, with no production logic change before the run.",
        "",
        "## Current Run",
        f"- job_id: {current['job_id']}",
        f"- asr_mode: {current['asr_mode']}",
        f"- asr_quality_score: {current['asr_quality_score']}",
        f"- low_confidence_asr: {current['low_confidence_asr']}",
        f"- asr_quality_reasons: {current['asr_quality_reasons']}",
        f"- candidates_found: {current['candidates_found']}",
        f"- candidates_quarantined: {current['candidates_quarantined']}",
        f"- repaired_window_needed: {current['repaired_window_needed']}",
        f"- pre_creator_qa_candidates: {current['pre_creator_qa_candidates']}",
        f"- creator_safe_count: {current['creator_safe_count']}",
        f"- final_clips_count: {current['final_clips_count']}",
        f"- salvage_allowed_clean: {current['salvage_allowed_clean']}",
        f"- salvage_allowed_borderline: {current['salvage_allowed_borderline']}",
        f"- salvage_quarantined_unstable: {current['salvage_quarantined_unstable']}",
        "",
        "## Rejection Reasons",
        f"- {current['rejection_reasons']}",
        "",
        "## Same-Source Baseline",
        f"- baseline_job_id: {baseline['job_id']}",
        f"- asr_mode: {baseline['asr_mode']}",
        f"- asr_quality_score: {baseline['asr_quality_score']}",
        f"- low_confidence_asr: {baseline['low_confidence_asr']}",
        f"- baseline_pre_creator_qa_candidates: {baseline['candidates_found']}",
        f"- baseline_creator_safe_count: {baseline['creator_safe_count']}",
        f"- baseline_final_clips_count: {baseline['final_clips_count']}",
        f"- baseline_rejection_reasons: {baseline['rejection_reasons']}",
        "",
        "## Assessment",
        f"- v49_7_to_v50_3_assessment: {current['v49_7_to_v50_3_assessment']}",
        "",
        "## Next Patch",
        f"- recommendation: {rec['recommendation']}",
        f"- reason: {rec['reason']}",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID)
    parser.add_argument("--baseline-job-id", default=DEFAULT_BASELINE_JOB_ID)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    summary = build_summary(args.job_id, args.baseline_job_id)
    payload = {
        "summary": summary,
        "next_patch_recommendation": next_patch_recommendation(summary),
    }
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.md_out, payload)

    current = summary["current"]
    for key in [
        "asr_quality_score",
        "candidates_found",
        "candidates_quarantined",
        "repaired_window_needed",
        "creator_safe_count",
        "final_clips_count",
    ]:
        print(f"{key}={current[key]}")
    print(f"rejection_reasons={current['rejection_reasons']}")
    print(f"v49_7_to_v50_3_assessment={current['v49_7_to_v50_3_assessment']}")
    print(f"next_patch_recommendation={payload['next_patch_recommendation']['recommendation']}")


if __name__ == "__main__":
    main()
