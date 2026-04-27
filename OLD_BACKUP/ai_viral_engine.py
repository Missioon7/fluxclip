from moviepy import VideoFileClipimport numpy as np
from moviepy.editor import VideoFileClip
from ai_engine import transcribe_video

# -----------------------------
# VIRAL KEYWORDS (HOOK SIGNAL)
# -----------------------------
VIRAL_KEYWORDS = [
    "shocking", "crazy", "huge", "breaking", "war", "money",
    "kill", "attack", "explosion", "insane", "viral", "exposed",
    "truth", "secret", "big", "news"
]

# -----------------------------
# TEXT SCORE FUNCTION
# -----------------------------
def get_text_score(text: str):
    score = 0
    text_lower = text.lower()

    for word in VIRAL_KEYWORDS:
        if word in text_lower:
            score += 2

    # question = curiosity boost
    if "?" in text:
        score += 1

    # emotional length boost
    if len(text.split()) > 12:
        score += 1

    return score


# -----------------------------
# MAIN VIRAL ENGINE
# -----------------------------
def analyze_video(video_path: str):
    print("🔍 Loading video for viral analysis...")

    clip = VideoFileClip(video_path)
    duration = int(clip.duration)

    print("🧠 Running Whisper transcription...")
    transcript = transcribe_video(video_path)

    segments = transcript["segments"]

    results = []

    for seg in segments:
        start = float(seg["start"])
        text = seg["text"]

        try:
            frame = clip.get_frame(start)

            # -----------------------------
            # VISUAL SIGNAL
            # -----------------------------
            visual_score = np.mean(frame)

            # -----------------------------
            # MOTION SIGNAL
            # -----------------------------
            motion_score = np.std(frame)

            # -----------------------------
            # AUDIO SIGNAL (light proxy)
            # -----------------------------
            audio_score = motion_score * 0.5

            # -----------------------------
            # TEXT SIGNAL (IMPORTANT)
            # -----------------------------
            text_score = get_text_score(text)

            # -----------------------------
            # FINAL VIRAL SCORE
            # -----------------------------
            final_score = (
                visual_score * 0.2 +
                motion_score * 0.3 +
                audio_score * 0.2 +
                text_score * 10
            )

            results.append({
                "time": start,
                "score": final_score,
                "text": text.strip()
            })

        except Exception as e:
            print("Skip frame error:", e)

    clip.close()

    # -----------------------------
    # TOP VIRAL MOMENTS
    # -----------------------------
    top = sorted(results, key=lambda x: x["score"], reverse=True)[:10]

    print("\n🔥 TOP VIRAL MOMENTS:")
    for item in top:
        print(f"{int(item['time'])}s | score:{round(item['score'],2)} | {item['text']}")

    return top