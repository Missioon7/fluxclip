import os
from moviepy.editor import VideoFileClip
import uuid

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# CLIP GENERATOR (OPUS STYLE)
# -----------------------------
def generate_clips(video_path: str, viral_segments: list, max_clips: int = 5):
    """
    viral_segments format:
    [
        {"time": 12, "score": 80},
        {"time": 45, "score": 75}
    ]
    """

    print("✂️ Generating viral clips...")

    clip = VideoFileClip(video_path)
    duration = clip.duration

    # sort by highest score
    top_segments = sorted(
        viral_segments,
        key=lambda x: x["score"],
        reverse=True
    )[:max_clips]

    output_files = []

    for i, seg in enumerate(top_segments):
        start = max(0, seg["time"] - 3)
        end = min(duration, seg["time"] + 7)

        print(f"🎬 Cutting clip {i+1}: {start}s → {end}s")

        subclip = clip.subclip(start, end)

        filename = f"{uuid.uuid4()}_clip_{i+1}.mp4"
        output_path = os.path.join(OUTPUT_DIR, filename)

        # TikTok-friendly export (fast + compressed)
        subclip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="ultrafast",
            threads=4,
            verbose=False,
            logger=None
        )

        output_files.append({
            "clip": output_path,
            "start": start,
            "end": end
        })

    clip.close()

    print("✅ All clips generated!")

    return output_files