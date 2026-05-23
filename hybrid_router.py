import json
import os
from pathlib import Path

import requests


DEFAULT_WORKERS = [
    {
        "name": "colab_gpu",
        "url_env": "COLAB_GPU_WORKER_URL",
        "url": "",
        "priority": 1,
        "enabled": True,
        "requires_gpu": True,
    },
    {
        "name": "local_rtx2050",
        "url_env": "LOCAL_GPU_WORKER_URL",
        "url": "",
        "priority": 2,
        "enabled": True,
        "requires_gpu": True,
    },
    {
        "name": "kaggle_gpu",
        "url_env": "KAGGLE_GPU_WORKER_URL",
        "url": "",
        "priority": 3,
        "enabled": False,
        "requires_gpu": True,
    },
]


def load_worker_config(path="worker_config.json"):
    config = {
        "prefer_worker": "colab_gpu",
        "poll_interval_seconds": 8,
        "max_wait_seconds": 1800,
        "upload_dir": "uploads",
        "workers": DEFAULT_WORKERS,
    }
    cfg_path = Path(path)
    if cfg_path.exists():
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update({k: v for k, v in loaded.items() if k != "workers"})
                if isinstance(loaded.get("workers"), (list, dict)):
                    config["workers"] = loaded["workers"]
        except Exception as e:
            print(f"worker_config_load_failed path={cfg_path} error={e}")
    return config


def configured_workers():
    config = load_worker_config()
    workers = []
    prefer_worker = str(config.get("prefer_worker") or "").strip()
    configured = config.get("workers") or []
    if isinstance(configured, dict):
        configured = [
            {"name": name, **value}
            for name, value in configured.items()
            if isinstance(value, dict)
        ]
    for idx, worker in enumerate(configured):
        if not isinstance(worker, dict) or worker.get("enabled") is False:
            continue
        item = dict(worker)
        env_name = item.get("url_env")
        env_url = os.getenv(str(env_name), "").strip() if env_name else ""
        item["url"] = (env_url or str(item.get("url") or "")).rstrip("/")
        item["priority"] = int(item.get("priority", idx + 10))
        if prefer_worker and item.get("name") == prefer_worker:
            item["priority"] = min(item["priority"], 0)
        workers.append(item)
    workers.sort(key=lambda w: w.get("priority", 999))
    return workers


WORKERS = configured_workers()


def choose_worker(timeout=5):
    available = []

    for worker in configured_workers():
        url = worker.get("url", "")

        if not url:
            print(f"GPU worker skipped: {worker.get('name')} has no URL")
            continue

        try:
            r = requests.get(f"{url}/health", timeout=timeout)
            print(f"GPU health check {worker.get('name')} -> HTTP {r.status_code}")

            if r.status_code != 200:
                continue

            data = r.json()
            print(f"GPU health data {worker.get('name')}: {data}")

            gpu_ok = (
                data.get("ok") is True
                and (
                    worker.get("requires_gpu") is not True
                    or data.get("gpu") is True
                    or str(data.get("device", "")).lower() == "cuda"
                    or "cuda" in str(data).lower()
                )
            )
            busy = bool(data.get("busy"))

            if gpu_ok and not busy:
                selected = dict(worker)
                selected["health"] = data
                available.append(selected)
            elif busy:
                print(f"GPU worker busy: {worker.get('name')} active_job_id={data.get('active_job_id')}")

        except Exception as e:
            print(f"GPU worker unavailable {worker.get('name')}: {e}")
            continue

    if not available:
        print("No remote GPU worker available; using local RTX/local pipeline fallback")
        return None

    available.sort(key=lambda w: w.get("priority", 999))
    selected = available[0]
    print(f"Selected GPU worker: {selected['name']}")
    return selected
