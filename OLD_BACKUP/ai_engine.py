import whisper
import torch

# --------------------
# DEVICE SETUP
# --------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print("🔥 Whisper device:", device)

# --------------------
# LOAD MODEL ONCE (IMPORTANT)
# --------------------
model = whisper.load_model("base").to(device)

# --------------------
# LANGUAGE DETECTION
# --------------------
def detect_language(file_path):
    audio = whisper.load_audio(file_path)
    audio = whisper.pad_or_trim(audio)

    mel = whisper.log_mel_spectrogram(audio).to(model.device)

    _, probs = model.detect_language(mel)
    lang = max(probs, key=probs.get)

    return lang

# --------------------
# MAIN TRANSCRIBE FUNCTION
# --------------------
def transcribe_video(file_path: str):
    lang = detect_language(file_path)

    print("🌐 Detected language:", lang)

    result = model.transcribe(
        file_path,
        language=lang,
        task="transcribe",
        temperature=0.0,
        condition_on_previous_text=False
    )

    return {
        "text": result["text"],
        "segments": result["segments"],
        "language": lang
    }