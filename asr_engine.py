import re
import os

# =========================
# OPUS AI ASR ENGINE
# Railway Lightweight Mode
# Whisper/Torch disabled for cloud boot
# =========================

MODEL_NAME = "small"
_model = None
_device = "cpu"


def get_device():
    print("⚠️ Railway lightweight mode: ASR device forced to CPU placeholder")
    return "cpu"


def get_model():
    print("⚠️ Railway lightweight mode: Whisper model disabled")
    return None


def clean_repeated_phrases(text: str) -> str:
    text = text or ""
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()

    bad_phrases = [
        "high or high",
        "blood has been blood",
        "something something something",
        "it is not showing the media it is not showing the media",
        "because they have to save the experience of china because they have to save the experience of china",
    ]

    for phrase in bad_phrases:
        text = text.replace(phrase, "")

    text = re.sub(r"\b(\w+\s+\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\w+\s+\w+\s+\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def should_keep_segment(text: str) -> bool:
    text = clean_repeated_phrases(text)

    if not text:
        return False

    words = text.split()

    if len(words) < 2:
        return False

    junk_words = ["thank you", "bye", "hmm", "uh", "um"]
    lower = text.lower().strip()

    if lower in junk_words:
        return False

    return True


def transcribe(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    print("⚠️ Railway lightweight mode: Whisper transcription disabled")

    return {
        "text": "",
        "segments": []
    }