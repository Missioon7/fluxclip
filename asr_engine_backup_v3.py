import re
import torch
import whisper


# =========================
# OPUS AI ASR ENGINE v2.1
# Better Hindi/Hinglish ASR
# =========================

MODEL_NAME = "small"   # base se better, RTX 2050 pe usually manageable
_model = None


def get_model():
    global _model

    if _model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔥 Loading Whisper model: {MODEL_NAME} on {device}")
        _model = whisper.load_model(MODEL_NAME, device=device)

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

    # remove repeated same short phrase
    text = re.sub(r"\b(\w+\s+\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\w+\s+\w+\s+\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def transcribe(file_path: str):
    model = get_model()

    result = model.transcribe(
        file_path,
        task="translate",        # Hindi/Hinglish -> English for scoring + captions
        language=None,
        fp16=torch.cuda.is_available(),
        verbose=False,
        condition_on_previous_text=False,
        temperature=0,
        best_of=3,
        beam_size=5,
        initial_prompt=(
            "This is a Hindi and Hinglish geopolitical commentary video. "
            "Transcribe and translate clearly into natural English. "
            "Preserve names like Ukraine, Russia, Iran, NATO, America, China, Donald Trump, Zelensky. "
            "Avoid repetition."
        )
    )

    segments = result.get("segments", [])

    cleaned_segments = []

    for s in segments:
        text = clean_repeated_phrases(s.get("text", ""))

        if not text:
            continue

        if len(text.split()) < 2:
            continue

        cleaned_segments.append({
            "start": float(s["start"]),
            "end": float(s["end"]),
            "text": text
        })

    full_text = clean_repeated_phrases(result.get("text", ""))

    return {
        "text": full_text,
        "segments": cleaned_segments
    }