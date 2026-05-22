# FluxClip Colab GPU Worker

Run these cells in Colab. Local VS Code remains the master codebase; Colab is only a temporary GPU worker.

```bash
%cd /content
REPO_URL="https://github.com/YOUR_GITHUB_USER/YOUR_FLUXCLIP_REPO.git"
if [ -d fluxclip/.git ]; then
  cd fluxclip && git pull --ff-only
else
  git clone "$REPO_URL" fluxclip && cd fluxclip
fi
```

```bash
pip install -U pip
pip install fastapi uvicorn python-multipart requests pyngrok
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install openai-whisper faster-whisper moviepy opencv-python-headless numpy
apt-get update -y && apt-get install -y ffmpeg
```

```python
from pyngrok import ngrok
import os, subprocess, textwrap, time

port = 8001
public_url = ngrok.connect(port, "http").public_url
print("COLAB_GPU_WORKER_URL=", public_url)

env = os.environ.copy()
env["FLUXCLIP_UPLOAD_DIR"] = "uploads"
subprocess.Popen(["python", "colab_worker.py"], env=env)
time.sleep(5)
print(public_url + "/health")
```

Set the printed URL locally:

```powershell
$env:COLAB_GPU_WORKER_URL="https://your-ngrok-url.ngrok-free.app"
```

Or put the URL into `worker_config.json` under the `colab_gpu.url` field. The local backend will health-check `/health`, dispatch one job to Colab if healthy, and fall back to local RTX/local pipeline if unavailable.
