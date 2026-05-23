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

def _download(url, worker_url=None, required=True, context="file"):
    if not isinstance(url, str):
        return url

    original_url = url
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
    local_url = f"/uploads/{filename}"

    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        print(
            "WORKER_RESULT_SYNC_FILE "
            f"context={context} source={url} local={local_url} status=exists"
        )
        return local_url

    try:
        r = requests.get(url, timeout=300)
        r.raise_for_status()

        with open(local_path, "wb") as f:
            f.write(r.content)

        print(
            "WORKER_RESULT_SYNC_FILE "
            f"context={context} source={url} local={local_url} bytes={len(r.content)}"
        )
        return local_url
    except Exception as e:
        print(
            "WORKER_RESULT_SYNC_FAILED "
            f"context={context} source={url} original={original_url} error={e}"
        )
        if required:
            raise
        return original_url

def _sync_item(item, worker_url=None, context="item"):
    if isinstance(item, str):
        return _download(item, worker_url, required=True, context=context)

    if isinstance(item, dict):
        item = dict(item)
        for key in ["url", "download_url", "path", "file", "video_path", "video_url"]:
            if key in item and isinstance(item[key], str):
                value = item[key]
                if value.startswith("http"):
                    item[key] = _download(value, worker_url, required=True, context=f"{context}.{key}")
                elif value.startswith("/uploads/"):
                    item[key] = _download(value, worker_url, required=True, context=f"{context}.{key}")
                elif value.startswith("uploads/") or value.startswith("/content/uploads/"):
                    item[key] = _download(value, worker_url, required=True, context=f"{context}.{key}")
        for key in ["thumbnail", "thumbnail_url", "thumbnail_path"]:
            if key in item and isinstance(item[key], str):
                value = item[key]
                if value.startswith(("http", "/uploads/", "uploads/", "/content/uploads/")):
                    item[key] = _download(value, worker_url, required=False, context=f"{context}.{key}")
        return item

    return item

def _sync_result_files(result, worker_url=None):
    result = dict(result or {})
    print(
        "WORKER_RESULT_SYNC_START "
        f"status={result.get('status')} clips={len(result.get('clips') or []) if isinstance(result.get('clips'), list) else 0} "
        f"final_clips={len(result.get('final_clips') or []) if isinstance(result.get('final_clips'), list) else 0}"
    )
    for key in ["final_clips", "clips", "thumbnails"]:
        if isinstance(result.get(key), list):
            result[key] = [
                _sync_item(x, worker_url, context=f"{key}[{idx}]")
                for idx, x in enumerate(result[key])
            ]
    if isinstance(result.get("clips"), list):
        result["clips"] = [_normalize_clip(c, idx) for idx, c in enumerate(result["clips"])]
    print(
        "WORKER_RESULT_SYNC_DONE "
        f"status={result.get('status')} clips={len(result.get('clips') or []) if isinstance(result.get('clips'), list) else 0} "
        f"final_clips={len(result.get('final_clips') or []) if isinstance(result.get('final_clips'), list) else 0}"
    )
    return result

def _normalize_clip(clip, idx=0):
    if not isinstance(clip, dict):
        return clip
    clip = dict(clip)
    media_url = (
        clip.get("video_url")
        or clip.get("download_url")
        or clip.get("video_path")
        or clip.get("path")
        or clip.get("file")
    )
    if media_url:
        clip.setdefault("video_url", media_url)
        clip.setdefault("download_url", media_url)
        clip.setdefault("video_path", media_url)
    if clip.get("duration") is None and clip.get("start") is not None and clip.get("end") is not None:
        try:
            clip["duration"] = round(float(clip["end"]) - float(clip["start"]), 2)
        except Exception:
            pass
    clip.setdefault("clip_number", idx + 1)
    return clip

def _merge_worker_result_into_job(job_id, jobs, worker_status, worker):
    result = worker_status.get("result") if isinstance(worker_status.get("result"), dict) else dict(worker_status)
    result = _sync_result_files(result, worker.get("url"))
    clips = result.get("clips") if isinstance(result.get("clips"), list) else []
    final_clips = result.get("final_clips") if isinstance(result.get("final_clips"), list) else []

    jobs[job_id]["result"] = result
    jobs[job_id]["clips"] = clips
    jobs[job_id]["final_clips"] = final_clips
    jobs[job_id]["viral_segments"] = result.get("viral_segments", [])
    jobs[job_id]["text"] = result.get("text", "")
    jobs[job_id]["summary"] = result.get("summary", {})
    jobs[job_id]["creator_qa"] = result.get("creator_qa", {})
    jobs[job_id]["message"] = result.get("message", "")
    jobs[job_id]["error"] = result.get("error", "")
    jobs[job_id]["worker"] = worker["name"]
    jobs[job_id]["worker_mode"] = "gpu_worker_async"
    jobs[job_id]["status"] = "done"
    jobs[job_id]["stage"] = "Completed"
    jobs[job_id]["progress"] = 100
    print(
        "WORKER_STATUS_MERGE_DONE "
        f"job_id={job_id} worker={worker['name']} clips={len(clips)} final_clips={len(final_clips)} "
        f"result_status={result.get('status')} message={result.get('message', '')}"
    )
    return jobs[job_id]

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
            jobs[job_id]["stage"] = worker_status.get("stage", jobs[job_id].get("stage", "Processing"))

            if worker_status.get("status") in ["done", "completed"]:
                return _merge_worker_result_into_job(job_id, jobs, worker_status, worker)

            if worker_status.get("status") == "failed":
                raise RuntimeError(worker_status.get("error", "GPU worker failed"))

            time.sleep(POLL_INTERVAL)

    except Exception as e:
        jobs[job_id]["worker_error"] = str(e)
        jobs[job_id]["worker_mode"] = "gpu_failed_fallback_local"
        jobs[job_id]["worker"] = "local_rtx2050"
        return run_pipeline(job_id, local_path, jobs)
