import os
import whisper

from ffmpeg_utils import cut_video, burn_subtitles
from viral_detector import detect_viral_moments
from captions import generate_captions

# load whisper once (FAST)
model = whisper.load_model("base")


def process_full_video(video_path, output_dir):

    print("🚀 AI PIPELINE STARTED")

    os.makedirs(output_dir, exist_ok=True)

    # 1. TRANSCRIBE
    result = model.transcribe(video_path)
    segments = result.get("segments", [])

    # 2. VIRAL DETECTION
    viral_segments = detect_viral_moments(segments)

    # fallback (IMPORTANT FIX for your 10 sec issue)
    if not viral_segments or len(viral_segments) == 0:
        viral_segments = [{"start": 0, "end": 10}]

    output_files = []

    # 3. CUT + CAPTION + BURN
    for i, seg in enumerate(viral_segments):

        print(f"🎬 Processing clip {i}")

        clip = cut_video(
            video_path,
            seg["start"],
            seg["end"],
            output_dir,
            i
        )

        captions = generate_captions(
            result,
            seg,
            output_dir,
            i
        )

        final = burn_subtitles(
            clip,
            captions,
            output_dir,
            i
        )

        output_files.append(final)

    print("✅ AI PIPELINE COMPLETED")

    return output_files