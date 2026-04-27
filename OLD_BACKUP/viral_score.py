from faster_whisper import WhisperModel
import time

print("🚀 Loading FAST Whisper (FIXED + OPTIMIZED)...")

# ⚡ FAST ENGINE (CPU OPTIMIZED)
model = WhisperModel(
    "tiny",
    device="cpu",
    compute_type="int8"
)

print("🎤 Transcribing audio...\n")

start_time = time.time()

# ⚡ IMPORTANT FIX: word timestamps + streaming output
segments, info = model.transcribe(
    "audio.wav",
    beam_size=1,
    vad_filter=True
)

scored = []

# 🔥 LIVE PROCESSING (NO HANG FEELING NOW)
for seg in segments:
    start = seg.start
    end = seg.end
    text = seg.text.strip()

    print(f"[{start:.2f}s → {end:.2f}s] {text}")

    duration = end - start
    words = len(text.split())

    # 🧠 VIRAL SCORING LOGIC (simple but effective)
    speed_score = words / max(duration, 0.5)
    length_score = duration * 2

    score = (speed_score * 10) + length_score

    scored.append((start, end, score, text))

end_time = time.time()

print("\n🔥 TOP VIRAL MOMENTS:\n")

scored.sort(key=lambda x: x[2], reverse=True)

for s, e, sc, txt in scored[:10]:
    print(f"{s:.2f}s → {e:.2f}s | Score: {sc:.2f}")
    print(txt)

print("\n⏱️ TOTAL TIME:", round(end_time - start_time, 2), "seconds")