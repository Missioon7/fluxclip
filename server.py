from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uuid
import os
import traceback
import threading

try:
    from pipeline_runner import run_pipeline
    PIPELINE_AVAILABLE = True
except Exception as e:
    run_pipeline = None
    PIPELINE_AVAILABLE = False
    PIPELINE_IMPORT_ERROR = str(e)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

JOBS = {}

print("⚠️ Railway lightweight mode: torch/whisper disabled")


@app.get("/")
def home():
    return {
        "status": "FluxClip backend running 🚀",
        "mode": "railway-lightweight",
        "pipeline_available": PIPELINE_AVAILABLE,
    }


def start_pipeline(job_id, file_path):
    if not PIPELINE_AVAILABLE or run_pipeline is None:
        JOBS[job_id] = {
            "status": "failed",
            "progress": 0,
            "error": "Pipeline disabled in Railway lightweight mode",
            "message": "Heavy AI processing will run on GPU worker/local machine later."
        }
        return

    try:
        run_pipeline(job_id, file_path, JOBS)
    except Exception as e:
        JOBS[job_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "trace": traceback.format_exc()
        }


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}.mp4")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    JOBS[job_id] = {
        "status": "queued",
        "progress": 0,
        "file": file.filename,
        "path": file_path
    }

    print(f"📤 Uploaded: {file.filename} | Job: {job_id}")

    thread = threading.Thread(
        target=start_pipeline,
        args=(job_id, file_path),
        daemon=True
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "mode": "railway-lightweight"
    }


@app.get("/status/{job_id}")
def status(job_id: str):
    return JOBS.get(job_id, {"status": "not_found", "error": "job not found"})


@app.get("/health")
def health():
    return {"ok": True, "service": "fluxclip-backend"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=False,
        workers=1
    )