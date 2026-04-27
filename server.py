from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uuid
import os


import traceback
import threading

from pipeline_runner import run_pipeline

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

device = "cuda" if torch.cuda.is_available() else "cpu"
print("🔥 DEVICE:", device)

model = whisper.load_model("base").to(device)
print("🔥 Whisper model loaded successfully")


@app.get("/")
def home():
    return {"status": "OPUS AI running 🚀"}


def start_pipeline(job_id, file_path):
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
        "status": "queued"
    }


@app.get("/status/{job_id}")
def status(job_id: str):
    return JOBS.get(job_id, {"status": "not_found", "error": "job not found"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        workers=1
    )