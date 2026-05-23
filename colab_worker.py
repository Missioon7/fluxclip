from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import threading
import time
import traceback
import uuid

import torch

from pipeline_runner import run_pipeline


UPLOAD_DIR = os.getenv("FLUXCLIP_UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="FluxClip Colab GPU Worker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

JOBS = {}
WORKER_LOCK = threading.Lock()
ACTIVE_JOB_ID = None


def _merge_result_contract(job):
    job = dict(job or {})
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    if result:
        job.setdefault("clips", result.get("clips", []))
        job.setdefault("final_clips", result.get("final_clips", []))
        job.setdefault("summary", result.get("summary", {}))
        job.setdefault("creator_qa", result.get("creator_qa", {}))
        if result.get("message"):
            job.setdefault("message", result.get("message"))
        if result.get("error"):
            job.setdefault("error", result.get("error"))
    return job


@app.get("/health")
def health():
    return {
        "ok": True,
        "worker": "colab_gpu",
        "gpu": bool(torch.cuda.is_available()),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "busy": ACTIVE_JOB_ID is not None,
        "active_job_id": ACTIVE_JOB_ID,
        "jobs": len(JOBS),
    }


def _run_worker_job(job_id, local_path):
    global ACTIVE_JOB_ID
    try:
        JOBS[job_id]["status"] = "processing"
        JOBS[job_id]["stage"] = "Starting"
        JOBS[job_id]["progress"] = 5
        result = run_pipeline(job_id, local_path, JOBS)
        JOBS[job_id]["result"] = result
        JOBS[job_id].update(_merge_result_contract(JOBS[job_id]))
        if JOBS[job_id].get("status") not in {"failed", "completed", "done"}:
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["progress"] = 100
    except Exception as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)
        JOBS[job_id]["trace"] = traceback.format_exc()
    finally:
        ACTIVE_JOB_ID = None
        try:
            WORKER_LOCK.release()
        except RuntimeError:
            pass


@app.post("/process")
async def process(file: UploadFile = File(...), job_id: str = Form(None)):
    global ACTIVE_JOB_ID
    if not torch.cuda.is_available():
        raise HTTPException(status_code=503, detail="CUDA GPU unavailable")
    if not WORKER_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail={"error": "worker_busy", "active_job_id": ACTIVE_JOB_ID})

    worker_job_id = str(job_id or uuid.uuid4())
    ACTIVE_JOB_ID = worker_job_id
    local_path = os.path.join(UPLOAD_DIR, f"{worker_job_id}.mp4")

    try:
        data = await file.read()
        with open(local_path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        JOBS[worker_job_id] = {
            "job_id": worker_job_id,
            "worker": "colab_gpu",
            "status": "queued",
            "stage": "Queued",
            "progress": 1,
            "file": os.path.basename(local_path),
            "local_path": local_path,
            "created_at": time.time(),
        }

        thread = threading.Thread(target=_run_worker_job, args=(worker_job_id, local_path), daemon=True)
        thread.start()
        return {"ok": True, "worker_job_id": worker_job_id, "status": "queued", "progress": 1}
    except Exception:
        ACTIVE_JOB_ID = None
        try:
            WORKER_LOCK.release()
        except RuntimeError:
            pass
        raise


@app.get("/status/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"status": "not_found", "error": "job not found"}
    status_value = job.get("status")
    if status_value == "completed":
        status_value = "done"
    normalized = _merge_result_contract(job)
    return {**normalized, "status": status_value}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False, workers=1)
