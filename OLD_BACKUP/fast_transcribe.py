from faster_whisper import WhisperModel
import time

print("🚀 Loading FAST Whisper...")

model = WhisperModel("tiny", device="cpu", compute_type="int8")

print("🎤 Transcribing...")

start = time.time()

segments, info = model.transcribe("audio.wav")

text = ""

for seg in segments:
    text += seg.text + " "

end = time.time()

print("\n🔥 TRANSCRIPTION DONE")
print("⏱️ Time:", round(end - start, 2), "sec\n")
print(text)