import json
import sys
from pathlib import Path


CONFIG_PATH = Path("worker_config.json")


def normalize_url(url):
    url = str(url or "").strip().rstrip("/")
    if not url:
        raise ValueError("Missing trycloudflare URL")
    if "trycloudflare.com" not in url:
        raise ValueError("URL must be a trycloudflare.com URL")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def load_config():
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"workers": []}


def update_workers(config, url):
    workers = config.get("workers")
    if isinstance(workers, dict):
        colab = workers.setdefault("colab_gpu", {})
        colab.update({
            "url": url,
            "priority": 0,
            "enabled": True,
        })
        config["workers"] = workers
        return config

    if not isinstance(workers, list):
        workers = []

    found = False
    for worker in workers:
        if isinstance(worker, dict) and worker.get("name") == "colab_gpu":
            worker["url"] = url
            worker["priority"] = 0
            worker["enabled"] = True
            found = True
            break

    if not found:
        workers.insert(0, {
            "name": "colab_gpu",
            "url": url,
            "priority": 0,
            "enabled": True,
            "requires_gpu": True,
        })

    config["workers"] = workers
    config.setdefault("prefer_worker", "colab_gpu")
    config.setdefault("poll_interval_seconds", 8)
    config.setdefault("max_wait_seconds", 1800)
    config.setdefault("upload_dir", "uploads")
    return config


def main():
    if len(sys.argv) != 2:
        print("Usage: python update_colab_worker_url.py https://your-tunnel.trycloudflare.com")
        return 2

    try:
        url = normalize_url(sys.argv[1])
        config = update_workers(load_config(), url)
        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"Updated {CONFIG_PATH} colab_gpu URL to {url}")
        return 0
    except Exception as e:
        print(f"Failed to update Colab worker URL: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
