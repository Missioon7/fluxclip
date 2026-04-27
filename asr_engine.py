import re
import os
import torch
import whisper


# =========================
# OPUS AI ASR ENGINE v4 SPEED
# Stable GPU Whisper + faster decode settings
# =========================

MODEL_NAME = "small"
_model = None
_device = None


def get_device():
    global _device

    if _device is None:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔥 ASR DEVICE: {_device}")

        if _device == "cuda":
            try:
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
            except Exception:
                pass

    return _device


def get_model():
    global _model

    if _model is None:
        device = get_device()
        print(f"🔥 Loading Whisper model: {MODEL_NAME} on {device}")
        _model = whisper.load_model(MODEL_NAME, device=device)
        print("✅ Whisper ASR model ready")

    return _model


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

    model = get_model()
    device = get_device()

    print("🔥 ASR MODE: V4 speed optimized")

    result = model.transcribe(
        file_path,
        task="translate",
        language=None,
        fp16=(device == "cuda"),

        # Speed-focused settings
        verbose=False,
        temperature=0,
        beam_size=1,
        best_of=1,

        # Reduces hallucination/repetition and improves speed stability
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
        logprob_threshold=-1.0,
        no_speech_threshold=0.6,

        initial_prompt=(
            "Hindi and Hinglish geopolitical or podcast style video. "
            "Translate clearly into natural English. "
            "Preserve names like India, China, USA, Russia, Ukraine, Iran, NATO, Trump, Zelensky. "
            "Avoid repetition."
        )
    )

    raw_segments = result.get("segments", [])
    cleaned_segments = []

    for s in raw_segments:
        text = clean_repeated_phrases(s.get("text", ""))

        if not should_keep_segment(text):
            continue

        start = float(s.get("start", 0))
        end = float(s.get("end", start))

        if end <= start:
            continue

        cleaned_segments.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "text": text
        })

    full_text = clean_repeated_phrases(result.get("text", ""))

    print(f"✅ ASR DONE | kept segments: {len(cleaned_segments)}")

    return {
        "text": full_text,
        "segments": cleaned_segments
    }