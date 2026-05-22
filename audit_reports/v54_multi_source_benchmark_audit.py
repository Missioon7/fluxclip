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

from v53_source_quality_gate_audit import compute_metrics, find_asr_artifact


DEFAULT_MD_OUT = Path("audit_reports/V54_MULTI_SOURCE_BENCHMARK_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v54_multi_source_benchmark_audit.json")


def raw_source_videos(limit=10):
    videos = []
    for path in sorted(
        Path("uploads").glob("*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        name = path.name.lower()
        if any(token in name for token in ["_final_", "_input_", "smart_crop_preview", "_asr_"]):
            continue
        videos.append(path)
        if len(videos) >= limit:
            break
    return videos


def classify_source(job_id, path):
    metrics = compute_metrics(job_id)
    if metrics:
        recommend_full_generation = metrics["source_quality_label"] in {"good", "borderline"}
        return {
            "job_id": job_id,
            "video_path": str(path),
            "artifact_available": True,
            "source_quality_score": metrics["source_quality_score"],
            "source_quality_label": metrics["source_quality_label"],
            "likely_clip_yield": metrics["likely_clip_yield"],
            "dominant_failure_reason": metrics["dominant_failure_reason"],
            "recommended_action": metrics["recommended_action"],
            "recommend_full_generation": recommend_full_generation,
            "creator_safe_count": metrics["creator_safe_count"],
            "candidates_found": metrics["candidates_found"],
            "candidates_quarantined": metrics["candidates_quarantined"],
        }
    return {
        "job_id": job_id,
        "video_path": str(path),
        "artifact_available": False,
        "source_quality_score": None,
        "source_quality_label": "unscored",
        "likely_clip_yield": "unknown",
        "dominant_failure_reason": "needs_preflight_source_quality_scoring",
        "recommended_action": "preload_v53_source_quality_before_full_generation",
        "recommend_full_generation": False,
        "creator_safe_count": None,
        "candidates_found": None,
        "candidates_quarantined": None,
    }


def expected_clip_yield(best_source):
    if not best_source:
        return "low"
    label = best_source.get("source_quality_label")
    if label == "good":
        return best_source.get("likely_clip_yield", "medium_to_high")
    if label == "borderline":
        return best_source.get("likely_clip_yield", "low_to_medium")
    return "low"


def recommended_next_action(rows, best_source):
    good = [row for row in rows if row["source_quality_label"] == "good"]
    borderline = [row for row in rows if row["source_quality_label"] == "borderline"]
    if good or borderline:
        return "run_full_generation_on_best_borderline_or_good_source_only"
    unscored = [row for row in rows if row["source_quality_label"] == "unscored"]
    if unscored:
        return "preload_v53_scoring_on_unscored_sources_before_any_full_generation"
    return "do_not_patch_logic_yet_collect_stronger_sources"


def build_payload(limit):
    rows = []
    for path in raw_source_videos(limit=limit):
        job_id = path.stem
        rows.append(classify_source(job_id, path))
    scored = [row for row in rows if row["source_quality_score"] is not None]
    scored.sort(key=lambda row: (-row["source_quality_score"], row["job_id"]))
    best = None
    for row in scored:
        if row["source_quality_label"] in {"good", "borderline"}:
            best = row
            break
    if best is None and scored:
        best = scored[0]

    summary = {
        "total_sources_tested": len(rows),
        "good_sources": sum(1 for row in rows if row["source_quality_label"] == "good"),
        "borderline_sources": sum(1 for row in rows if row["source_quality_label"] == "borderline"),
        "poor_sources": sum(1 for row in rows if row["source_quality_label"] == "poor"),
        "unscored_sources": sum(1 for row in rows if row["source_quality_label"] == "unscored"),
        "best_source_for_full_rerun": best["job_id"] if best and best["source_quality_label"] in {"good", "borderline"} else None,
        "expected_clip_yield": expected_clip_yield(best),
        "recommended_next_action": recommended_next_action(rows, best),
    }
    return {
        "summary": summary,
        "sources": rows,
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V54 Multi-Source Benchmark Audit Report",
        "",
        "Scope: benchmark-pack audit over available raw source videos. Sources with V53-compatible artifacts are scored directly. Unscored sources are deferred until preflight source-quality scoring is available.",
        "",
        f"- total_sources_tested: {s['total_sources_tested']}",
        f"- good_sources: {s['good_sources']}",
        f"- borderline_sources: {s['borderline_sources']}",
        f"- poor_sources: {s['poor_sources']}",
        f"- unscored_sources: {s['unscored_sources']}",
        f"- best_source_for_full_rerun: {s['best_source_for_full_rerun']}",
        f"- expected_clip_yield: {s['expected_clip_yield']}",
        f"- recommended_next_action: {s['recommended_next_action']}",
        "",
        "| Job | Label | Score | Yield | Action | Artifact |",
        "|---|---|---:|---|---|---|",
    ]
    for row in payload["sources"]:
        score = "" if row["source_quality_score"] is None else row["source_quality_score"]
        lines.append(
            f"| {row['job_id']} | {row['source_quality_label']} | {score} | "
            f"{row['likely_clip_yield']} | {row['recommended_action']} | {row['artifact_available']} |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_payload(limit=max(1, args.limit))
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.md_out, payload)

    for key, value in payload["summary"].items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
