import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
AUDIT_DIR = Path(__file__).resolve().parent
if str(AUDIT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_DIR))

import asr_engine
from v53_source_quality_gate_audit import compute_metrics


DEFAULT_V54_JSON = Path("audit_reports/v54_multi_source_benchmark_audit.json")
DEFAULT_MD_OUT = Path("audit_reports/V54_1_UNSCORED_SOURCE_PREFLIGHT_AUDIT_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v54_1_unscored_source_preflight_audit.json")
DEFAULT_LIMIT = 1


def load_v54_unscored_sources(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = payload.get("sources", [])
    return [row for row in sources if row.get("source_quality_label") == "unscored"]


def read_existing_payload(path):
    path = Path(path)
    if not path.exists():
        return {"summary": {}, "sources": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"summary": {}, "sources": []}
    if not isinstance(payload, dict):
        return {"summary": {}, "sources": []}
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    return {
        "summary": payload.get("summary", {}),
        "sources": sources,
    }


def source_sort_key(row):
    metrics = row.get("metrics") or {}
    return (-int(metrics.get("source_quality_score", -1) or -1), str(row.get("job_id") or ""))


def source_output_artifact(job_id):
    return ROOT / "audit_reports" / f"asr_segments_{job_id}_native_pre_retry.json"


def preflight_source(source_row, source_index, total_sources):
    job_id = str(source_row.get("job_id"))
    video_path = Path(str(source_row.get("video_path")))
    if not video_path.is_absolute():
        video_path = (ROOT / video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found for preflight: {video_path}")

    artifact = source_output_artifact(job_id)
    print(f"selected_source_filename={video_path.name}")
    print(f"selected_source_index={source_index}/{total_sources}")
    print(f"output_artifact_path={artifact}")

    if not artifact.exists():
        result = asr_engine.transcribe(str(video_path), job_id=job_id)
        preflight_meta = {
            "artifact_reused": False,
            "asr_mode": result.get("asr_mode"),
            "asr_quality_score": result.get("asr_quality_score"),
            "low_confidence_asr": result.get("low_confidence_asr"),
            "segments_count": len(result.get("segments", [])),
        }
    else:
        preflight_meta = {
            "artifact_reused": True,
            "asr_mode": "cached_artifact",
            "asr_quality_score": None,
            "low_confidence_asr": None,
            "segments_count": None,
        }

    metrics = compute_metrics(job_id)
    if not metrics:
        raise RuntimeError(f"V53 metrics unavailable after preflight for job_id={job_id}")
    return {
        "job_id": job_id,
        "video_path": str(video_path),
        "preflight_meta": preflight_meta,
        "metrics": metrics,
    }


def expected_clip_yield(best):
    if not best:
        return "low"
    return str(best["metrics"].get("likely_clip_yield") or "low")


def recommended_next_action(rows, best):
    good = [row for row in rows if row["metrics"].get("source_quality_label") == "good"]
    borderline = [row for row in rows if row["metrics"].get("source_quality_label") == "borderline"]
    if good or borderline:
        return "run_full_generation_on_best_preflighted_source_only"
    return "do_not_run_full_generation_on_this_batch_collect_stronger_sources"


def build_summary(rows, total_unscored, attempted_this_run):
    successful = [row for row in rows if row.get("status") == "completed" and row.get("metrics")]
    scored = sorted(successful, key=source_sort_key)
    best = None
    for row in scored:
        if row["metrics"]["source_quality_label"] in {"good", "borderline"}:
            best = row
            break
    if best is None and scored:
        best = scored[0]

    return {
        "total_unscored_sources": total_unscored,
        "sources_attempted_this_run": attempted_this_run,
        "sources_preflighted": len(successful),
        "sources_completed": len(successful),
        "sources_failed": sum(1 for row in rows if row.get("status") == "failed"),
        "sources_remaining": max(total_unscored - len(rows), 0),
        "good_sources": sum(1 for row in scored if row["metrics"]["source_quality_label"] == "good"),
        "borderline_sources": sum(1 for row in scored if row["metrics"]["source_quality_label"] == "borderline"),
        "poor_sources": sum(1 for row in scored if row["metrics"]["source_quality_label"] == "poor"),
        "best_source_for_full_generation": best["job_id"] if best and best["metrics"]["source_quality_label"] in {"good", "borderline"} else None,
        "expected_clip_yield": expected_clip_yield(best),
        "recommended_next_action": recommended_next_action(scored, best),
    }


def write_markdown(path, payload):
    s = payload["summary"]
    lines = [
        "# V54.1 Unscored Source Preflight Audit Report",
        "",
        "Scope: ASR-only preflight on V54 unscored raw uploads, followed by V53-style source quality scoring. This script is resume-safe and writes partial output after each source.",
        "",
        f"- total_unscored_sources: {s['total_unscored_sources']}",
        f"- sources_attempted_this_run: {s['sources_attempted_this_run']}",
        f"- sources_preflighted: {s['sources_preflighted']}",
        f"- sources_failed: {s['sources_failed']}",
        f"- sources_remaining: {s['sources_remaining']}",
        f"- good_sources: {s['good_sources']}",
        f"- borderline_sources: {s['borderline_sources']}",
        f"- poor_sources: {s['poor_sources']}",
        f"- best_source_for_full_generation: {s['best_source_for_full_generation']}",
        f"- expected_clip_yield: {s['expected_clip_yield']}",
        f"- recommended_next_action: {s['recommended_next_action']}",
        "",
        "| Job | Status | Score | Label | Yield | ASR | Unstable Ratio | Clean/Borderline | Anchor Density | Context Density | Filler Ratio | Notes |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(payload["sources"], key=source_sort_key):
        m = row.get("metrics") or {}
        if row.get("status") == "failed":
            lines.append(
                f"| {row['job_id']} | failed | 0 | error | low | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | {row.get('error', 'unknown_error')} |"
            )
            continue
        lines.append(
            f"| {row['job_id']} | {row.get('status', 'completed')} | {m['source_quality_score']} | {m['source_quality_label']} | {m['likely_clip_yield']} | "
            f"{m['asr_quality_score']} | {m['unstable_candidate_ratio']:.2f} | {m['clean_or_borderline_window_ratio']:.2f} | "
            f"{m['payoff_anchor_density']:.2f} | {m['standalone_context_density']:.2f} | {m['filler_ratio']:.2f} | "
            f"artifact_reused={row.get('preflight_meta', {}).get('artifact_reused')} |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def persist_outputs(json_out, md_out, rows, total_unscored, attempted_this_run):
    ordered_rows = sorted(rows, key=source_sort_key)
    payload = {
        "summary": build_summary(ordered_rows, total_unscored, attempted_this_run),
        "sources": ordered_rows,
    }
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_out, payload)
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v54-json", type=Path, default=DEFAULT_V54_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--max-runtime-seconds", type=int, default=None)
    args = parser.parse_args()

    all_sources = load_v54_unscored_sources(args.v54_json)
    existing_payload = read_existing_payload(args.json_out)
    processed_job_ids = {
        str(row.get("job_id"))
        for row in existing_payload.get("sources", [])
        if row.get("status") in {"completed", "failed"}
    }
    rows = [row for row in existing_payload.get("sources", []) if str(row.get("job_id")) in processed_job_ids]
    pending_sources = [
        (index, row)
        for index, row in enumerate(all_sources, start=1)
        if str(row.get("job_id")) not in processed_job_ids
    ]
    limit = max(0, int(args.limit))
    selected_sources = pending_sources[:limit]
    attempted_this_run = 0
    started_at = time.monotonic()

    for source_index, source_row in selected_sources:
        if args.max_runtime_seconds is not None and attempted_this_run > 0:
            elapsed = time.monotonic() - started_at
            if elapsed >= args.max_runtime_seconds:
                print(f"early_stop_guard=max_runtime_reached elapsed_seconds={round(elapsed, 2)}")
                break

        attempted_this_run += 1
        job_id = str(source_row.get("job_id"))
        try:
            result_row = preflight_source(source_row, source_index, len(all_sources))
            result_row["status"] = "completed"
        except Exception as exc:
            result_row = {
                "job_id": job_id,
                "video_path": str(source_row.get("video_path") or ""),
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "preflight_meta": {
                    "artifact_reused": source_output_artifact(job_id).exists(),
                    "early_stop_guard": "asr_engine_transcribe_has_900_second_native_timeout",
                },
            }
            print(f"source_failed job_id={job_id} error={result_row['error']}")
        rows = [row for row in rows if str(row.get("job_id")) != job_id]
        rows.append(result_row)
        persist_outputs(args.json_out, args.md_out, rows, len(all_sources), attempted_this_run)

    payload = persist_outputs(args.json_out, args.md_out, rows, len(all_sources), attempted_this_run)

    for key, value in payload["summary"].items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
