import os
import whisper
import subprocess
import torch
import gc
import re
import unicodedata

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

_model = None


# =========================
# VIRAL INTENT ENGINE (V3)
# =========================
VIRAL_WORDS = {
    "secret","truth","exposed","warning","danger","war","attack",
    "drone","military","power","money","economy","government",
    "breaking","huge","massive","shocking","insane","crisis",
    "kill","risk","collapse","explosion","surprising"
}

HOOK_PATTERNS = [
    "you need to know", "this is what", "what really happens",
    "nobody tells you", "the truth is", "breaking news",
    "listen carefully", "important thing", "you won’t believe"
]

FILLER_STARTERS = {
    "okay","so","well","basically","actually","now","like","hmm"
}


# =========================
# CLEAN TEXT
# =========================
def clean_text(text):
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if unicodedata.category(c)[0] != "C")
    text = re.sub(r"[^a-zA-Z0-9\u0900-\u097F\s.,!?]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# =========================
# NOISE FILTER (HARD)
# =========================
def is_noise(text):
    words = text.lower().split()

    if len(words) < 8:
        return True

    if len(set(words)) / max(len(words),1) < 0.6:
        return True

    if len(text) < 30:
        return True

    if sum(c.isdigit() for c in text) > len(text) * 0.15:
        return True

    if len(set(words[:10])) <= 2:
        return True

    return False


# =========================
# HOOK DETECTION
# =========================
def has_hook(text):
    t = text.lower()
    return any(p in t for p in HOOK_PATTERNS)


# =========================
# VIRAL SCORE ENGINE (FINAL)
# =========================
def score(text, duration):
    t = text.lower()
    words = text.split()

    s = 0

    # 1. HOOK = KING SIGNAL
    if has_hook(t):
        s += 20

    # 2. filler penalty (IMPORTANT FIX)
    if any(t.startswith(f) for f in FILLER_STARTERS):
        s -= 6

    # 3. keyword density (controlled)
    keyword_hits = sum(1 for w in VIRAL_WORDS if w in t)
    s += min(keyword_hits * 3, 15)

    # 4. duration sweet spot
    if 6 <= duration <= 16:
        s += 10
    elif 16 < duration <= 22:
        s += 5
    elif duration > 30:
        s -= 8
    elif duration < 4:
        s -= 12

    # 5. engagement signals
    if "?" in text: s += 3
    if "!" in text: s += 2

    # 6. ideal sentence structure
    if 10 <= len(words) <= 22:
        s += 6
    elif len(words) > 25:
        s -= 3

    # 7. anti-noise boost
    if not is_noise(text):
        s += 5

    # 8. repetition penalty
    if len(set(words)) < len(words) * 0.6:
        s -= 6

    return s


# =========================
# MODEL LOADER
# =========================
def get_model():
    global _model

    if _model is None:
        print("🔥 Loading Whisper (base)...")

        if torch.cuda.is_available():
            _model = whisper.load_model("base").to("cuda")
            print("🚀 GPU ENABLED")
        else:
            _model = whisper.load_model("base")

    return _model


# =========================
# TRANSCRIBE
# =========================
def transcribe(model, file_path):
    return model.transcribe(
        file_path,
        task="transcribe",
        beam_size=5,
        best_of=5,
        temperature=0.0,
        condition_on_previous_text=False,
        no_speech_threshold=0.80,
        logprob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        fp16=torch.cuda.is_available()
    )


# =========================
# MAIN PIPELINE (OPUS V3)
# =========================
def process_video(file_path, job_id):
    try:
        print(f"\n🚀 JOB START: {job_id}")

        model = get_model()

        print("🧠 Transcribing audio...")
        result = transcribe(model, file_path)

        segments = result.get("segments", [])
        print(f"✅ Segments found: {len(segments)}")

        scored = []

        for seg in segments:
            start = float(seg["start"])
            end = float(seg["end"])
            text = clean_text(seg.get("text", ""))

            if not text:
                continue

            duration = end - start

            if duration < 4:
                continue

            if is_noise(text):
                continue

            s = score(text, duration)

            # FINAL STRICT FILTER
            if s < 13:
                continue

            scored.append({
                "start": start,
                "end": end,
                "score": s,
                "text": text
            })

        if not scored:
            print("❌ No valid clips found")
            return {"job_id": job_id, "clips": []}

        scored.sort(key=lambda x: x["score"], reverse=True)

        # DIVERSITY FILTER (ANTI REPEAT)
        final = []
        used = set()

        for s in scored:
            key = " ".join(s["text"].split()[:7])
            if key in used:
                continue
            used.add(key)
            final.append(s)
            if len(final) == 5:
                break

        clips = []

        for i, seg in enumerate(final):
            out = os.path.join(OUTPUT_FOLDER, f"{job_id}_clip_{i}.mp4")

            print(f"\n🔥 CLIP {i} | SCORE={seg['score']}")
            print(f"📝 {seg['text']}")

            subprocess.run([
                "ffmpeg","-y",
                "-ss", str(max(seg["start"] - 0.5, 0)),   # 🔥 SMART START SHIFT
                "-to", str(seg["end"] + 0.3),            # 🔥 NATURAL END EXTENSION
                "-i", file_path,
                "-c:v","libx264",
                "-preset","fast",
                "-c:a","aac",
                "-loglevel","error",
                out
            ])

            if os.path.exists(out) and os.path.getsize(out) > 1200:
                clips.append(out)
                print("✅ CREATED")

        torch.cuda.empty_cache()
        gc.collect()

        print(f"\n🎯 TOTAL CLIPS: {len(clips)}")

        return {"job_id": job_id, "clips": clips}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return {"error": str(e)}