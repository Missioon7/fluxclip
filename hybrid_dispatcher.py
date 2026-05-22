import os
import time
import requests
from urllib.parse import urlparse
from pipeline_runner import run_pipeline
from hybrid_router import choose_worker, load_worker_config

UPLOAD_DIR = load_worker_config().get("upload_dir", "uploads")

POLL_INTERVAL = int(load_worker_config().get("poll_interval_seconds", 8))
MAX_WAIT_SECONDS = int(load_worker_config().get("max_wait_seconds", 1800))
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _download(url, worker_url=None):
    if not isinstance(url, str):
        return url

    if url.startswith("/content/uploads/") and worker_url:
        url = worker_url.rstrip("/") + "/uploads/" + os.path.basename(url)

    elif url.startswith("uploads/") and worker_url:
        url = worker_url.rstrip("/") + "/" + url

    elif url.startswith("/uploads/") and worker_url:
        url = worker_url.rstrip("/") + url

    if not url.startswith("http"):
        return url

    filename = os.path.basename(urlparse(url).path)
    if not filename:
        return url

    local_path = os.path.join(UPLOAD_DIR, filename)

    r = requests.get(url, timeout=300)
    r.raise_for_status()

    with open(local_path, "wb") as f:
        f.write(r.content)

    return f"/uploads/{filename}"

def _sync_item(item, worker_url=None):
    if isinstance(item, str):
        return _download(item, worker_url)

    if isinstance(item, dict):
        for key in ["url", "download_url", "path", "file", "video_path", "thumbnail_url"]:
            if key in item and isinstance(item[key], str):
                value = item[key]
                if value.startswith("http"):
                    item[key] = _download(value, worker_url)
                elif value.startswith("/uploads/"):
                    item[key] = value
        return item

    return item

def _sync_result_files(result, worker_url=None):
    for key in ["final_clips", "clips", "thumbnails"]:
        if isinstance(result.get(key), list):
            result[key] = [_sync_item(x, worker_url) for x in result[key]]
    return result

def dispatch_job(job_id, local_path, jobs):
    worker = choose_worker()

    if not worker:
        jobs[job_id]["worker"] = "local_rtx2050"
        jobs[job_id]["worker_mode"] = "fallback_local"
        return run_pipeline(job_id, local_path, jobs)

    try:
        jobs[job_id]["worker"] = worker["name"]
        jobs[job_id]["worker_mode"] = "gpu_worker_async"
        jobs[job_id]["status"] = "uploading_to_worker"
        jobs[job_id]["progress"] = 3

        with open(local_path, "rb") as f:
            start_res = requests.post(
                f'{worker["url"]}/process',
                files={"file": f},
                data={"job_id": job_id},
                timeout=300
            )

        start_res.raise_for_status()
        start_data = start_res.json()

        worker_job_id = start_data.get("worker_job_id", job_id)

        jobs[job_id]["worker_job_id"] = worker_job_id
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 5

        started = time.time()

        while True:
            if time.time() - started > MAX_WAIT_SECONDS:
                raise TimeoutError("GPU worker polling timed out")

            status_res = requests.get(
                f'{worker["url"]}/status/{worker_job_id}',
                timeout=120
            )
            status_res.raise_for_status()
            worker_status = status_res.json()

            jobs[job_id]["worker_status"] = worker_status
            jobs[job_id]["status"] = worker_status.get("status", jobs[job_id].get("status", "processing"))
            jobs[job_id]["progress"] = worker_status.get("progress", jobs[job_id].get("progress", 5))

            if worker_status.get("status") in ["done", "completed"]:
                if isinstance(worker_status.get("result"), dict):
                    result = _sync_result_files(worker_status["result"], worker["url"])
                    jobs[job_id]["result"] = result
                    jobs[job_id]["clips"] = result.get("clips", [])
                    jobs[job_id]["final_clips"] = result.get("final_clips", [])
                    jobs[job_id]["viral_segments"] = result.get("viral_segments", [])
                    jobs[job_id]["text"] = result.get("text", "")
                else:
                    worker_status = _sync_result_files(worker_status, worker["url"])
                    jobs[job_id].update(worker_status)
                jobs[job_id]["worker"] = worker["name"]
                jobs[job_id]["worker_mode"] = "gpu_worker_async"
                jobs[job_id]["status"] = "done"
                jobs[job_id]["progress"] = 100
                return jobs[job_id]

            if worker_status.get("status") == "failed":
                raise RuntimeError(worker_status.get("error", "GPU worker failed"))

            time.sleep(POLL_INTERVAL)

    except Exception as e:
        jobs[job_id]["worker_error"] = str(e)
        jobs[job_id]["worker_mode"] = "gpu_failed_fallback_local"
        jobs[job_id]["worker"] = "local_rtx2050"
        return run_pipeline(job_id, local_path, jobs)
