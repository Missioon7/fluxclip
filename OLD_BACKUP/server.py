from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
import traceback
import torch
import whisper

# -----------------------------
# OPTIONAL MODULES (SAFE IMPORT)
# -----------------------------
try:
    from ai_engine import transcribe_video
except:
    transcribe_video = None

try:
    from ai_viral_engine import analyze_video
except:
    analyze_video = None

try:
    from clip_generator import generate_clips
except:
    generate_clips = None

try:
    from subtitle_burner import burn_subtitles
except:
    burn_subtitles = None


app = FastAPI()

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# FOLDERS
# -----------------------------
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# JOB STORE
# -----------------------------
JOBS = {}

# -----------------------------
# DEVICE SETUP
# -----------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print("🔥 Using device:", device)

# -----------------------------
# LOAD WHISPER
# -----------------------------
model = whisper.load_model("base").to(device)


# -----------------------------
# SAFE UPDATE FUNCTION
# -----------------------------
def update_job(job_id, data):
    if job_id not in JOBS:
        JOBS[job_id] = {}
    JOBS[job_id].update(data)


# -----------------------------
# PIPELINE
# -----------------------------
def process_video(job_id: str, file_path: str):
    print(f"\n🧠 JOB STARTED: {job_id}")

    try:
        update_job(job_id, {"status": "processing"})

        # -------------------------
        # 1. TRANSCRIPTION
        # -------------------------
        print("🎙️ Transcribing...")

        if transcribe_video:
            transcript = transcribe_video(file_path)
        else:
            result = model.transcribe(
                file_path,
                task="transcribe",
                temperature=0.0,
                condition_on_previous_text=False
            )
            transcript = {
                "text": result.get("text", ""),
                "segments": result.get("segments", [])
            }

        text = transcript["text"]
        segments = transcript["segments"]

        update_job(job_id, {
            "text": text,
            "segments": segments
        })

        # -------------------------
        # 2. VIRAL ENGINE
        # -------------------------
        print("🔥 Viral analysis...")

        if analyze_video:
            viral_segments = analyze_video(file_path)
        else:
            viral_segments = [
                {"start": 0, "end": 10, "score": 0.5}
            ]

        update_job(job_id, {"viral_segments": viral_segments})

        # -------------------------
        # 3. CLIP GENERATION
        # -------------------------
        print("✂️ Generating clips...")

        if generate_clips:
            clips = generate_clips(file_path, viral_segments)
        else:
            clips = [{"clip": "mock.mp4", "score": 0.5}]

        update_job(job_id, {"clips": clips})

        # -------------------------
        # 4. SUBTITLE BURN (OPTIONAL)
        # -------------------------
        print("📝 Subtitle processing...")

        if burn_subtitles:
            final_video = burn_subtitles(file_path, segments, OUTPUT_DIR)
            update_job(job_id, {"final_video": final_video})

        # -------------------------
        # DONE
        # -------------------------
        update_job(job_id, {"status": "done"})

        print("🚀 JOB COMPLETED")

    except Exception as e:
        print("❌ ERROR:")
        print(traceback.format_exc())

        update_job(job_id, {
            "status": "error",
            "error": str(e)
        })


# -----------------------------
# ROUTES
# -----------------------------
@app.get("/")
def home():
    return {"status": "OPUS backend running 🚀"}


# -----------------------------
# UPLOAD
# -----------------------------
@app.post("/upload")
async def upload(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):

    job_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    JOBS[job_id] = {
        "status": "queued",
        "file": file.filename,
        "path": file_path
    }

    print(f"📤 Uploaded: {file.filename} | Job: {job_id}")

    background_tasks.add_task(process_video, job_id, file_path)

    return {
        "job_id": job_id,
        "status": "queued"
    }


# -----------------------------
# STATUS
# -----------------------------
@app.get("/status/{job_id}")
def status(job_id: str):
    return JOBS.get(job_id, {"error": "job not found"})