import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
UPLOADS = ROOT / "uploads"


def read_jsonl_tail(path, limit=500):
    if not path.exists():
        return []
    rows = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        return [{"_read_error": str(e), "_path": str(path)}]
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"_parse_error": line[:240], "_path": str(path)})
    return rows


def latest_job_id(*row_groups):
    latest = None
    for rows in row_groups:
        for row in rows:
            job_id = row.get("job_id")
            ts = row.get("ts", 0)
            if not job_id:
                continue
            if latest is None or ts >= latest[0]:
                latest = (ts, job_id)
    return latest[1] if latest else None


def frontend_clip_compatible(clip):
    if not isinstance(clip, dict):
        return False
    return bool(
        clip.get("video_url")
        or clip.get("video_path")
        or clip.get("download_url")
        or clip.get("path")
        or clip.get("file")
        or clip.get("url")
    )


def upload_exists(url_or_path):
    if not isinstance(url_or_path, str) or not url_or_path:
        return False
    clean = url_or_path.replace("\\", "/")
    marker = "uploads/"
    if marker in clean:
        clean = clean[clean.index(marker) + len(marker):]
    else:
        clean = os.path.basename(clean)
    return (UPLOADS / clean).exists()


def main():
    creator_rows = read_jsonl_tail(ANALYTICS / "creator_qa.jsonl")
    clip_rows = read_jsonl_tail(ANALYTICS / "clip_intelligence.jsonl")
    job_id = latest_job_id(creator_rows, clip_rows)

    if not job_id:
        print(json.dumps({
            "ok": False,
            "message": "No analytics job artifacts found.",
            "checked": [
                str(ANALYTICS / "creator_qa.jsonl"),
                str(ANALYTICS / "clip_intelligence.jsonl"),
            ],
        }, indent=2))
        return

    job_creator_rows = [r for r in creator_rows if r.get("job_id") == job_id]
    job_clip_rows = [r for r in clip_rows if r.get("job_id") == job_id]
    completed_rows = [r for r in job_clip_rows if r.get("stage") == "completed"]
    pre_v60_rows = [r for r in job_clip_rows if r.get("stage") == "pre_creator_qa_v60"]
    zero_safe = [r for r in job_creator_rows if r.get("event") == "CREATOR_QA_ZERO_SAFE_CLIPS"]
    rejects = [r for r in job_creator_rows if r.get("event") == "CREATOR_QA_REJECT"]
    v60_rows = [r for r in job_creator_rows if str(r.get("event", "")).startswith("V60_")]

    final_files = sorted(UPLOADS.glob(f"{job_id}_final_*.mp4"))
    thumbnail_files = sorted(UPLOADS.glob(f"{job_id}_thumbnail_*.jpg"))

    sample_clips = []
    missing_urls = []
    for row in completed_rows[-10:]:
        clip = {
            "title": row.get("title"),
            "start": row.get("start"),
            "end": row.get("end"),
            "score": row.get("score"),
        }
        sample_clips.append(clip)

    for file_path in final_files:
        if not file_path.exists():
            missing_urls.append(str(file_path))

    report = {
        "ok": True,
        "job_id": job_id,
        "worker_status_shape": {
            "expected_top_level": ["status", "progress", "result", "clips", "final_clips", "summary", "creator_qa"],
            "note": "Live in-memory /status cannot be inspected offline; this audit uses latest analytics and upload artifacts.",
        },
        "clips_present": len(completed_rows) > 0 or len(final_files) > 0,
        "local_status_clips_present": "unknown_offline",
        "frontend_compatible_clips_array": len(completed_rows) > 0 or len(final_files) > 0,
        "completed_clip_rows": len(completed_rows),
        "pre_creator_qa_v60_rows": len(pre_v60_rows),
        "final_files": [f"/uploads/{p.name}" for p in final_files],
        "thumbnail_files": [f"/uploads/{p.name}" for p in thumbnail_files],
        "missing_sync_files_or_urls": missing_urls,
        "v60_events": {
            "count": len(v60_rows),
            "applied": sum(1 for r in v60_rows if r.get("event") == "V60_CONTEXT_EXPANSION_APPLIED"),
            "skipped": sum(1 for r in v60_rows if r.get("event") == "V60_CONTEXT_EXPANSION_SKIPPED"),
            "replay": sum(1 for r in v60_rows if r.get("event") == "V60_CREATOR_QA_REPLAY_RESULT"),
        },
        "rejection_reason_if_no_clips": None,
        "sample_completed_clips": sample_clips,
    }

    if not report["clips_present"]:
        if zero_safe:
            latest_zero = zero_safe[-1]
            report["rejection_reason_if_no_clips"] = {
                "event": latest_zero.get("event"),
                "message": latest_zero.get("message"),
                "rejected_count": latest_zero.get("rejected_count"),
                "top_rejection_reasons": latest_zero.get("top_rejection_reasons"),
            }
        elif rejects:
            report["rejection_reason_if_no_clips"] = {
                "event": "CREATOR_QA_REJECT",
                "rejected_count": len(rejects),
                "latest_reasons": rejects[-1].get("reasons"),
            }
        else:
            report["rejection_reason_if_no_clips"] = "No completed clips and no Creator QA rejection artifact found."

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
