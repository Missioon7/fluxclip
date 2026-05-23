from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uuid
import os
import json
import time
import traceback
import threading
from hybrid_dispatcher import dispatch_job

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("🔥 STATIC UPLOAD DIR:", UPLOAD_DIR)

app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_DIR),
    name="uploads"
)



JOBS = {}
PIPELINE_LOCK = threading.Lock()


def normalize_status_payload(job):
    payload = dict(job or {})
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    worker_status = payload.get("worker_status") if isinstance(payload.get("worker_status"), dict) else {}
    worker_result = worker_status.get("result") if isinstance(worker_status.get("result"), dict) else {}

    source = result or worker_result or worker_status
    if isinstance(source, dict):
        if not isinstance(payload.get("clips"), list):
            payload["clips"] = source.get("clips", [])
        if not isinstance(payload.get("final_clips"), list):
            payload["final_clips"] = source.get("final_clips", [])
        payload.setdefault("summary", source.get("summary", {}))
        payload.setdefault("creator_qa", source.get("creator_qa", {}))
        if source.get("message") and not payload.get("message"):
            payload["message"] = source.get("message")
        if source.get("error") and not payload.get("error"):
            payload["error"] = source.get("error")

    if result and "result" not in payload:
        payload["result"] = result
    return payload

@app.get("/")
def home():
    return {
        "status": "FluxClip GCP API running",
        "processing": "local_rtx2050",
    }


@app.get("/worker-status")
def worker_status():
    from hybrid_router import choose_worker, WORKERS

    worker = choose_worker()

    return {
        "selected_worker": worker,
        "configured_workers": WORKERS,
        "fallback": "local_rtx2050"
    }


@app.post("/create-job")
async def create_job():
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "created",
        "stage": "Waiting for upload",
        "progress": 0,
        "worker": "local_rtx2050"
    }
    return {"job_id": job_id, "status": "created", "progress": 0}


@app.post("/upload/{job_id}")
async def upload_existing_job(job_id: str, file: UploadFile = File(...)):
    local_path = os.path.join(UPLOAD_DIR, f"{job_id}.mp4")

    try:
        file_bytes = await file.read()
        with open(local_path, "wb") as f:
            f.write(file_bytes)
            f.flush()
            os.fsync(f.fileno())

        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "stage": "Queued",
            "progress": 1,
            "file": f"{job_id}.mp4",
            "local_path": local_path,
            "worker": "local_rtx2050"
        }

        def locked_dispatch():
            with PIPELINE_LOCK:
                dispatch_job(job_id, local_path, JOBS)

        thread = threading.Thread(
            target=locked_dispatch,
            daemon=True
        )
        thread.start()

        return {"job_id": job_id, "status": "queued", "progress": 1}

    except Exception as e:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "trace": traceback.format_exc()
        }
        return JOBS[job_id]


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    gcp_job_id = str(uuid.uuid4())
    local_path = os.path.join(UPLOAD_DIR, f"{gcp_job_id}.mp4")

    try:
        file_bytes = await file.read()

        with open(local_path, "wb") as f:
            f.write(file_bytes)
            f.flush()
            os.fsync(f.fileno())

        JOBS[gcp_job_id] = {
            "job_id": gcp_job_id,
            "status": "queued",
            "progress": 0,
            "file": f"{gcp_job_id}.mp4",
            "local_path": local_path,
            "worker": "local_rtx2050"
        }

        print(f"📤 GCP CPU upload saved: {gcp_job_id}.mp4 | Job: {gcp_job_id}")
        print(f"📦 File size: {os.path.getsize(local_path)} bytes")

        def locked_dispatch():
            with PIPELINE_LOCK:
                dispatch_job(gcp_job_id, local_path, JOBS)

        thread = threading.Thread(
            target=locked_dispatch,
            daemon=True
        )
        thread.start()

        return {
            "job_id": gcp_job_id,
            "status": "queued",
            "processing": "local_rtx2050"
        }

    except Exception as e:
        JOBS[gcp_job_id] = {
            "job_id": gcp_job_id,
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "trace": traceback.format_exc()
        }
        return JOBS[gcp_job_id]

@app.get("/status/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)

    if not job:
        return {"status": "not_found", "error": "job not found"}

    return normalize_status_payload(job)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, workers=1)




# =========================================================
# 🔥 V21 Creator Feedback + Learning API
# =========================================================

@app.post("/feedback")
async def submit_feedback(payload: dict):
    """
    Stores creator/user feedback for future scoring auto-tuning.
    Expected:
    {
      "job_id": "...",
      "clip_index": 0,
      "rating": "good" | "bad",
      "reason": "bad_start|bad_ending|boring|wrong_topic|great_hook|good_context",
      "note": "optional"
    }
    """
    try:
        os.makedirs("analytics", exist_ok=True)
        row = {
            "ts": time.time(),
            "job_id": payload.get("job_id"),
            "clip_index": payload.get("clip_index"),
            "rating": payload.get("rating"),
            "reason": payload.get("reason"),
            "note": payload.get("note", ""),
        }

        with open("analytics/creator_feedback.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\\n")

        return {"ok": True, "saved": row}

    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/analytics/summary")
async def analytics_summary():
    try:
        feedback_path = "analytics/creator_feedback.jsonl"
        clip_path = "analytics/clip_intelligence.jsonl"

        feedback = []
        clips = []

        if os.path.exists(feedback_path):
            with open(feedback_path, "r", encoding="utf-8") as f:
                feedback = [json.loads(x) for x in f if x.strip()]

        if os.path.exists(clip_path):
            with open(clip_path, "r", encoding="utf-8") as f:
                clips = [json.loads(x) for x in f if x.strip()]

        ratings = {}
        reasons = {}
        niches = {}

        for r in feedback:
            ratings[r.get("rating")] = ratings.get(r.get("rating"), 0) + 1
            reasons[r.get("reason")] = reasons.get(r.get("reason"), 0) + 1

        for c in clips:
            niches[c.get("niche")] = niches.get(c.get("niche"), 0) + 1

        return {
            "ok": True,
            "clips_logged": len(clips),
            "feedback_logged": len(feedback),
            "ratings": ratings,
            "reasons": reasons,
            "niches": niches,
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}




@app.get("/analytics/deep-summary")
async def analytics_deep_summary():
    try:
        def read_jsonl(path):
            rows = []
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rows.append(json.loads(line))
                        except Exception:
                            continue
            return rows

        clips = read_jsonl("analytics/clip_intelligence.jsonl")
        feedback = read_jsonl("analytics/creator_feedback.jsonl")
        failures = read_jsonl("analytics/failure_snapshots.jsonl")
        thumbs = read_jsonl("analytics/thumbnail_intelligence.jsonl")
        visuals = read_jsonl("analytics/visual_intelligence.jsonl")

        def count_by(rows, key):
            out = {}
            for r in rows:
                v = r.get(key)
                out[v] = out.get(v, 0) + 1
            return out

        return {
            "ok": True,
            "totals": {
                "clips": len(clips),
                "feedback": len(feedback),
                "failures": len(failures),
                "thumbnail_jobs": len(thumbs),
                "visual_jobs": len(visuals),
            },
            "niches": count_by(clips, "niche"),
            "ratings": count_by(feedback, "rating"),
            "feedback_reasons": count_by(feedback, "reason"),
            "failure_stages": count_by(failures, "stage"),
            "latest_clips": clips[-10:],
            "latest_feedback": feedback[-10:],
            "latest_failures": failures[-10:],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}




@app.get("/system/health")
async def system_health():
    try:
        import shutil
        from pathlib import Path

        def file_count(folder):
            path = Path(folder)
            if not path.exists():
                return 0
            return len([x for x in path.rglob("*") if x.is_file()])

        total, used, free = shutil.disk_usage(".")

        failures = 0
        failure_path = Path("analytics/failure_snapshots.jsonl")
        if failure_path.exists():
            failures = len([x for x in failure_path.read_text(encoding="utf-8").splitlines() if x.strip()])

        return {
            "ok": True,
            "service": "fluxclip",
            "disk": {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "used_percent": round((used / total) * 100, 2) if total else 0,
            },
            "folders": {
                "uploads_files": file_count("uploads"),
                "outputs_files": file_count("outputs"),
                "analytics_files": file_count("analytics"),
            },
            "analytics": {
                "failure_snapshots": failures,
                "clip_intelligence_exists": Path("analytics/clip_intelligence.jsonl").exists(),
                "feedback_exists": Path("analytics/creator_feedback.jsonl").exists(),
                "visual_intelligence_exists": Path("analytics/visual_intelligence.jsonl").exists(),
                "thumbnail_intelligence_exists": Path("analytics/thumbnail_intelligence.jsonl").exists(),
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}




@app.get("/system/cleanup-preview")
async def cleanup_preview(days=7):
    try:
        import time
        from pathlib import Path

        cutoff = time.time() - (float(days) * 86400)

        folders = ["uploads", "outputs"]
        result = {}

        for folder in folders:
            items = []
            path = Path(folder)

            if path.exists():
                for f in path.rglob("*"):
                    if not f.is_file():
                        continue

                    try:
                        stat = f.stat()

                        if stat.st_mtime < cutoff:
                            items.append({
                                "file": str(f),
                                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                                "modified": round(stat.st_mtime),
                            })
                    except Exception:
                        pass

            result[folder] = {
                "count": len(items),
                "total_mb": round(sum(x["size_mb"] for x in items), 2),
                "files": items[:100]
            }

        return {
            "ok": True,
            "days": days,
            "preview": result
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}




@app.post("/system/cleanup-execute")
async def cleanup_execute(days=7, dry_run=True, max_files=200):
    try:
        import time
        from pathlib import Path

        cutoff = time.time() - (float(days) * 86400)
        max_files = int(max_files)
        dry_run = str(dry_run).lower() in ["true", "1", "yes"]

        removable_patterns = [
            "_input_raw_",
            "_input_clip_",
            "_thumbnail_",
            "_thumb_ai_",
            ".ass",
            ".srt",
            ".vtt",
            ".wav",
            ".tmp",
            ".log",
        ]

        candidates = []

        for folder in ["uploads", "outputs"]:
            path = Path(folder)
            if not path.exists():
                continue

            for f in path.rglob("*"):
                if not f.is_file():
                    continue

                try:
                    stat = f.stat()
                    name = f.name.lower()

                    if stat.st_mtime >= cutoff:
                        continue

                    removable = any(p in name for p in removable_patterns)

                    # old final mp4 can be cleaned only if very old
                    if "_final_" in name and name.endswith(".mp4") and float(days) >= 3:
                        removable = True

                    # NEVER delete raw original job uploads here
                    if name.endswith(".mp4") and "_input_" not in name and "_final_" not in name and "_thumb_ai_" not in name:
                        removable = False

                    if removable:
                        candidates.append({
                            "path": str(f),
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "modified": round(stat.st_mtime),
                        })
                except Exception:
                    pass

        candidates = sorted(candidates, key=lambda x: x["modified"])[:max_files]

        deleted = []
        freed_mb = 0.0

        if not dry_run:
            for item in candidates:
                try:
                    fp = Path(item["path"])
                    if fp.exists() and fp.is_file():
                        size_mb = item["size_mb"]
                        fp.unlink()
                        deleted.append(item["path"])
                        freed_mb += size_mb
                except Exception as e:
                    print(f"⚠ cleanup delete failed {item['path']}: {e}")

        return {
            "ok": True,
            "dry_run": dry_run,
            "days": days,
            "max_files": max_files,
            "candidates": len(candidates),
            "candidate_mb": round(sum(x["size_mb"] for x in candidates), 2),
            "deleted": len(deleted),
            "freed_mb": round(freed_mb, 2),
            "files": candidates[:50],
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}
