from fastapi import FastAPI, UploadFile, File, BackgroundTasks
import os
import uuid
import shutil
import whisper
import torch
import subprocess
import gc
import re
import unicodedata

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =========================
# JOB STORE
# =========================
JOBS = {}

_model = None


# =========================
# SAFE MODEL LOADER (FIXED)
# =========================
def get_model():
    global _model

    if _model is None:
        print("🔥 Loading Whisper...")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = whisper.load_model("base", device=device)

        print(f"🚀 MODEL LOADED ON {device.upper()}")

    return _model


# =========================
# CLEAN TEXT
# =========================
def clean_text(text):
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================
# VIRAL SCORE ENGINE (STABLE)
# =========================
def score(text, duration):
    t = text.lower()
    words = text.split()

    s = 0

    viral = ["war", "drone", "money", "attack", "breaking", "power", "crisis"]
    hook = ["you need", "this is", "what happens", "listen", "truth"]

    if any(h in t for h in hook):
        s += 10

    s += sum(2 for w in viral if w in t)

    if 6 <= duration <= 18:
        s += 6

    if "?" in text:
        s += 2

    if len(words) > 10:
        s += 2

    return s


# =========================
# TRANSCRIBE (FIXED STABILITY)
# =========================
def transcribe(model, file_path):
    return model.transcribe(
        file_path,
        task="transcribe",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False
    )


# =========================
# PIPELINE (SAFE VERSION)
# =========================
def process_video(job_id, file_path):
    try:
        JOBS[job_id]["status"] = "processing"

        model = get_model()

        result = transcribe(model, file_path)
        segments = result.get("segments", [])

        clips = []

        for i, seg in enumerate(segments):

            # 🔥 SAFETY FIX (IMPORTANT)
            if seg.get("start") is None or seg.get("end") is None:
                continue

            text = clean_text(seg.get("text", ""))
            start = float(seg["start"])
            end = float(seg["end"])

            duration = end - start

            if duration < 4:
                continue

            s = score(text, duration)

            if s < 8:
                continue

            out_file = os.path.join(OUTPUT_DIR, f"{job_id}_clip_{i}.mp4")

            subprocess.run([
                "ffmpeg", "-y",
                "-ss", str(start),
                "-to", str(end),
                "-i", file_path,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-loglevel", "error",
                out_file
            ])

            if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
                clips.append({
                    "file": out_file,
                    "text": text,
                    "score": s
                })

        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["clips"] = clips

        torch.cuda.empty_cache()
        gc.collect()

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)


# =========================
# API ROUTES
# =========================

@app.get("/")
def home():
    return {"status": "OPUS AI running 🚀"}


@app.post("/upload")
async def upload(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):

    job_id = str(uuid.uuid4())

    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    JOBS[job_id] = {
        "status": "queued",
        "file": file.filename,
        "clips": []
    }

    background_tasks.add_task(process_video, job_id, file_path)

    return {
        "job_id": job_id,
        "status": "queued"
    }


@app.get("/status/{job_id}")
def status(job_id: str):
    return JOBS.get(job_id, {"error": "job not found"})