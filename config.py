# =========================
# OPUS AI CONFIG
# =========================

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------
# FOLDERS
# -----------------
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

RAW_CLIPS_DIR = os.path.join(OUTPUT_DIR, "raw_clips")
FINAL_CLIPS_DIR = os.path.join(OUTPUT_DIR, "final")

# -----------------
# MODEL SETTINGS
# -----------------
WHISPER_MODEL = "base"
DEVICE = "cuda"  # auto override later if needed

# -----------------
# VIDEO SETTINGS
# -----------------
CLIP_DURATION = 20  # seconds
OUTPUT_RESOLUTION = "720x1280"

# -----------------
# CAPTION SETTINGS
# -----------------
MIN_CAPTION_DURATION = 0.15

# -----------------
# FFmpeg SETTINGS
# -----------------
FFMPEG_PRESET = "ultrafast"
CRF = 23

# -----------------
# SAFETY
# -----------------
MAX_CLIPS = 5