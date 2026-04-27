import os
import subprocess

video_path = "uploads/input1.mp4"

# yahan tum apne top viral segments daal sakte ho
top_segments = [
    (30, 60),
    (90, 120),
    (150, 180)
]

os.makedirs("clips", exist_ok=True)

for i, (start, end) in enumerate(top_segments):
    output = f"clips/clip_{i}.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-ss", str(start),
        "-to", str(end),
        "-c", "copy",
        output
    ]

    subprocess.run(cmd)

    print(f"🔥 Clip created: {output}")