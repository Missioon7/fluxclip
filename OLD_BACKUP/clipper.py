import os
from .ffmpeg_utils import run

def generate_clips(video, segments, out_dir):

    clips = []

    for i, seg in enumerate(segments):

        start = float(seg["start"])
        end = float(seg["end"])
        duration = end - start

        if duration < 5:
            continue

        out = os.path.join(out_dir, f"clip_{i}.mp4")

        run([
            "ffmpeg", "-y",
            "-i", video,
            "-ss", str(start),
            "-t", str(duration),
            "-vf", "scale=1080:1920,crop=ih*9/16:ih",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            out
        ])

        clips.append(out)

    return clips