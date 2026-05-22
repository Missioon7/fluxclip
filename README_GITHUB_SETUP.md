# FluxClip GitHub Setup

FluxClip is developed locally in VS Code. GitHub is the sync source for Colab GPU workers; generated videos, uploads, logs, virtualenvs, and backups should stay out of Git.

## Local Setup

```powershell
git clone <your-repo-url> fluxclip
cd fluxclip
python -m venv venv
.\venv\Scripts\activate
pip install -U pip
pip install fastapi uvicorn python-multipart requests torch openai-whisper faster-whisper moviepy opencv-python numpy
```

Install `ffmpeg` and ensure it is available on `PATH`.

Run the local backend:

```powershell
python server.py
```

Optional Colab worker URL:

```powershell
$env:COLAB_GPU_WORKER_URL="https://your-colab-tunnel-url"
```

The backend reads `worker_config.json`, tries a healthy `colab_gpu` worker first, and falls back to the local RTX/local pipeline if unavailable.

## Colab Worker Setup

Use `COLAB_WORKER_SETUP.md` in Colab:

1. Clone or pull the GitHub repo.
2. Install Python dependencies and `ffmpeg`.
3. Start `colab_worker.py`.
4. Expose the worker through a tunnel.
5. Put the public URL in local `COLAB_GPU_WORKER_URL` or `worker_config.json`.

The Colab worker exposes:

```text
GET  /health
POST /process
GET  /status/{job_id}
GET  /uploads/{file}
```

## GPU Requirements

- Local fallback: NVIDIA GPU with CUDA is preferred for production ASR.
- Colab worker: CUDA GPU runtime required.
- Production should not run full ASR retry on CPU.
- `ffmpeg` and `ffprobe` are required for audio extraction and chunking.

## Verification

Before pushing:

```powershell
python -m py_compile asr_engine.py pipeline_runner.py server.py hybrid_router.py hybrid_dispatcher.py colab_worker.py
```

Check what will be committed:

```powershell
git status --short
git add .gitignore README_GITHUB_SETUP.md COLAB_WORKER_SETUP.md worker_config.json colab_worker.py hybrid_router.py hybrid_dispatcher.py asr_engine.py pipeline_runner.py server.py
git status --short
```

Do not commit `uploads/`, `outputs/`, `venv/`, `*.tar.gz`, runtime logs, or generated ASR artifacts.
