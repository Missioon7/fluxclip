from faster_whisper import WhisperModel
import time

print("🚀 Loading Faster Whisper (FAST ENGINE)...")

start_time = time.time()

# ⚡ FAST + CPU OPTIMIZED
model = WhisperModel("base", device="cpu", compute_type="int8")

print("🎤 Transcribing audio...")

segments, info = model.transcribe("audio.wav")

print("\n🔥 TRANSCRIPTION RESULT:\n")

for seg in segments:
    print(f"[{seg.start:.2f}s → {seg.end:.2f}s] {seg.text}")

end_time = time.time()

print("\n⏱️ Time Taken:", round(end_time - start_time, 2), "seconds")