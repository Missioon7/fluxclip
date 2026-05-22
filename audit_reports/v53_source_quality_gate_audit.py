import argparse
import json
import re
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
from v48_candidate_asr_confidence_audit import read_jsonl


DEFAULT_MD_OUT = Path("audit_reports/V53_SOURCE_QUALITY_GATE_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v53_source_quality_gate_audit.json")
DEFAULT_JOB_IDS = [
    "v51_fresh_source_23f21012",
    "2efbe27a-4f64-41aa-9077-6f483e00fc4f",
    "f964425c-0803-4e3d-b6e7-98f8eb3e7d52",
    "e0fc755a-9319-4bab-ad50-fd6ffa723bcb",
    "cb7f65ba-222e-4e82-869f-57d399a3f146",
]


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


def transcript_quality_row(job_id):
    best = {}
    for row in read_jsonl("analytics/transcript_quality.jsonl"):
        if str(row.get("job_id")) != str(job_id):
            continue
        if "asr_quality_score" in row:
            best = row
    return best


def candidate_funnel_rows(job_id):
    return [row for row in read_jsonl("analytics/candidate_funnel.jsonl") if str(row.get("job_id")) == str(job_id)]


def pre_creator_rows(job_id):
    return [
        row for row in read_jsonl("analytics/clip_intelligence.jsonl")
        if str(row.get("job_id")) == str(job_id) and row.get("stage") == "pre_creator_qa"
    ]


def creator_qa_rows(job_id):
    return [row for row in read_jsonl("analytics/creator_qa.jsonl") if str(row.get("job_id")) == str(job_id)]


def segment_salvage_rows(job_id):
    path = Path("analytics/asr_segment_salvage.jsonl")
    if not path.exists():
        return []
    return [row for row in read_jsonl(path) if str(row.get("job_id")) == str(job_id)]


def safe_ratio(numerator, denominator):
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def source_quality_score(metrics):
    score = 0
    score += min(30, max(0, int(round(metrics["asr_quality_score"] * 0.3))))
    score += min(20, int(round(metrics["clean_or_borderline_window_ratio"] * 20)))
    score += min(15, int(round(metrics["payoff_anchor_density"] * 30)))
    score += min(10, int(round(metrics["standalone_context_density"] * 20)))
    score -= min(20, int(round(metrics["unstable_candidate_ratio"] * 25)))
    score -= min(12, int(round(metrics["filler_ratio"] * 20)))
    score -= min(18, int(round(metrics["semantic_degradation_ratio"] * 24)))
    return max(0, min(100, score))


def source_quality_label(score):
    if score >= 65:
        return "good"
    if score >= 40:
        return "borderline"
    return "poor"


def likely_clip_yield(metrics, label):
    if label == "good" and metrics["payoff_anchor_density"] >= 0.08 and metrics["unstable_candidate_ratio"] <= 0.35:
        return "medium_to_high"
    if label == "borderline" and metrics["clean_or_borderline_window_ratio"] >= 0.2:
        return "low_to_medium"
    return "low"


def dominant_failure_reason(metrics, rejection_counter):
    if metrics["unstable_candidate_ratio"] >= 0.5:
        return "unstable_asr_dominant"
    if rejection_counter.get("no_hook_no_payoff", 0) >= max(2, rejection_counter.get("weak_standalone_context", 0)):
        return "missing_standalone_payoff"
    if rejection_counter.get("weak_standalone_context", 0) >= 2:
        return "weak_standalone_context"
    if metrics["semantic_degradation_ratio"] >= 0.35:
        return "semantic_degradation"
    if metrics["filler_ratio"] >= 0.35:
        return "filler_heavy_source"
    return "mixed_quality_constraints"


def recommended_action(label, dominant_reason, metrics):
    if label == "good":
        return "run_full_pipeline_normally"
    if dominant_reason == "unstable_asr_dominant":
        return "avoid_full_generation_until_source_or_asr_capture_improves"
    if dominant_reason in {"missing_standalone_payoff", "weak_standalone_context"} and metrics["clean_or_borderline_window_ratio"] >= 0.15:
        return "use_source_for_payoff_generation_experiments_only"
    if dominant_reason == "semantic_degradation":
        return "avoid_full_generation_until_semantic_cleanliness_improves"
    return "skip_or_deprioritize_source_for_full_generation"


def compute_metrics(job_id):
    artifact_path = find_asr_artifact(job_id)
    if not artifact_path:
        return None
    artifact = read_json(artifact_path, {})
    segments = artifact.get("segments", [])
    if not isinstance(segments, list):
        segments = []
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    tq = transcript_quality_row(job_id)
    funnel = candidate_funnel_rows(job_id)
    pre_creator = pre_creator_rows(job_id)
    creator_rows = creator_qa_rows(job_id)
    salvage = segment_salvage_rows(job_id)

    eligible_segments = []
    payoff_anchors = 0
    standalone_context_segments = 0
    filler_segments = 0
    semantic_degraded_segments = 0
    clean_or_borderline_segments = 0

    for seg in segments:
        start = float(seg.get("start", 0) or 0)
        end = float(seg.get("end", start) or start)
        if end <= start:
            continue
        text = re.sub(r"\s+", " ", str(seg.get("text") or "")).strip()
        if not text:
            continue
        local_asr = pipeline_runner.v48_candidate_asr_stability(start, end, chunks)
        semantic = pipeline_runner.v48_semantic_asr_confidence(text)
        local_label = str(local_asr.get("local_asr_confidence_label") or "unknown")
        semantic_label = str(semantic.get("semantic_asr_confidence_label") or "unknown")
        if local_label in {"clean", "borderline"}:
            clean_or_borderline_segments += 1
        if semantic_label == "degraded_semantics":
            semantic_degraded_segments += 1
        filler = (
            pipeline_runner.is_bad_transcript_clip(text)
            or pipeline_runner.v38_text_quality_is_severe(text)
            or len(pipeline_runner._v8_word_set(text)) < 5
        )
        if filler:
            filler_segments += 1
        if local_label == "unstable" or semantic_label == "degraded_semantics" or filler:
            continue
        eligible_segments.append((start, end, text, local_label, semantic_label))
        if pipeline_runner.v7_context_quality_score(text) >= 8:
            standalone_context_segments += 1
        anchor = pipeline_runner.v52_payoff_anchor_signal(text, {
            "local_asr_confidence_label": local_label,
            "semantic_asr_confidence_label": semantic_label,
        })
        if anchor.get("v52_payoff_anchor_detected"):
            payoff_anchors += 1

    rejection_counter = Counter()
    creator_safe_count = 0
    for row in creator_rows:
        if row.get("event") == "CREATOR_QA_APPROVED":
            creator_safe_count += 1
        if row.get("event") == "CREATOR_QA_REJECT":
            for reason in row.get("reasons", []):
                rejection_counter[str(reason)] += 1

    candidates_found = len(funnel)
    candidates_quarantined = sum(1 for row in funnel if row.get("filter_decision") == "asr_segment_quarantined")
    repaired_window_needed = sum(1 for row in funnel if row.get("repaired_window_required") is True)
    pre_creator_count = len(pre_creator)

    metrics = {
        "job_id": job_id,
        "artifact_path": str(artifact_path),
        "asr_quality_score": float(
            tq.get("asr_quality_score", artifact.get("asr_quality_score", 0)) or 0
        ),
        "low_confidence_asr": bool(
            tq.get("low_confidence_asr", artifact.get("low_confidence_asr", False))
        ),
        "segment_count": len(segments),
        "eligible_segment_count": len(eligible_segments),
        "clean_or_borderline_window_count": clean_or_borderline_segments,
        "clean_or_borderline_window_ratio": safe_ratio(clean_or_borderline_segments, len(segments)),
        "unstable_candidate_ratio": safe_ratio(candidates_quarantined, candidates_found),
        "payoff_anchor_density": safe_ratio(payoff_anchors, len(eligible_segments)),
        "standalone_context_density": safe_ratio(standalone_context_segments, len(eligible_segments)),
        "filler_ratio": safe_ratio(filler_segments, len(segments)),
        "semantic_degradation_ratio": safe_ratio(semantic_degraded_segments, len(segments)),
        "candidates_found": candidates_found,
        "candidates_quarantined": candidates_quarantined,
        "repaired_window_needed": repaired_window_needed,
        "pre_creator_qa_candidates": pre_creator_count,
        "creator_safe_count": creator_safe_count,
        "rejection_reasons": rejection_counter.most_common(),
        "salvage_summary": Counter(str(row.get("segment_salvage_decision") or "") for row in salvage),
    }
    score = source_quality_score(metrics)
    label = source_quality_label(score)
    dominant = dominant_failure_reason(metrics, rejection_counter)
    metrics.update({
        "source_quality_score": score,
        "source_quality_label": label,
        "likely_clip_yield": likely_clip_yield(metrics, label),
        "dominant_failure_reason": dominant,
        "recommended_action": recommended_action(label, dominant, metrics),
    })
    metrics["salvage_summary"] = dict(metrics["salvage_summary"])
    return metrics


def discover_job_ids(seed_job_ids):
    discovered = []
    for job_id in seed_job_ids:
        if job_id not in discovered:
            discovered.append(job_id)
    for path in sorted(Path("audit_reports").glob("asr_segments_*_native_pre_retry.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        job_id = path.name[len("asr_segments_"):-len("_native_pre_retry.json")]
        if job_id not in discovered:
            discovered.append(job_id)
        if len(discovered) >= 8:
            break
    return discovered


def build_payload(job_ids):
    rows = []
    for job_id in discover_job_ids(job_ids):
        metrics = compute_metrics(job_id)
        if metrics:
            rows.append(metrics)
    rows.sort(key=lambda row: (-row["source_quality_score"], row["job_id"]))
    return {
        "jobs_evaluated": len(rows),
        "sources": rows,
    }


def write_markdown(path, payload):
    lines = [
        "# V53 Source Quality Gate Audit Report",
        "",
        "Scope: audit-only source quality evaluation. This scores recent sources for likely clip yield before full clip generation, without production blocking.",
        "",
        f"- jobs_evaluated: {payload['jobs_evaluated']}",
        "",
        "| Job | Score | Label | Likely Yield | Dominant Failure | Recommended Action | ASR | Clean/Borderline | Unstable Ratio | Anchor Density | Context Density | Filler Ratio | Semantic Ratio |",
        "|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sources"]:
        lines.append(
            f"| {row['job_id']} | {row['source_quality_score']} | {row['source_quality_label']} | "
            f"{row['likely_clip_yield']} | {row['dominant_failure_reason']} | {row['recommended_action']} | "
            f"{row['asr_quality_score']} | {row['clean_or_borderline_window_ratio']:.2f} | "
            f"{row['unstable_candidate_ratio']:.2f} | {row['payoff_anchor_density']:.2f} | "
            f"{row['standalone_context_density']:.2f} | {row['filler_ratio']:.2f} | "
            f"{row['semantic_degradation_ratio']:.2f} |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", action="append", dest="job_ids", default=[])
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    job_ids = args.job_ids or DEFAULT_JOB_IDS
    payload = build_payload(job_ids)
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.md_out, payload)

    for row in payload["sources"]:
        print(f"job_id={row['job_id']}")
        for key in [
            "source_quality_score",
            "source_quality_label",
            "likely_clip_yield",
            "dominant_failure_reason",
            "recommended_action",
        ]:
            print(f"{key}={row[key]}")
        print("--")


if __name__ == "__main__":
    main()
