import os
import subprocess

# 📌 INPUT VIDEO
VIDEO_PATH = "uploads/input1.mp4"

# 📌 SAMPLE VIRAL SEGMENTS (abhi dummy, next step me AI se aayenge)
# format: (start_time, end_time)
segments = [
    (0, 20),
    (30, 55),
    (60, 90)
]

# 📁 output folder
os.makedirs("final_clips", exist_ok=True)

print("🚀 Starting Auto Clip Cutter...")

for i, (start, end) in enumerate(segments):

    output_path = f"final_clips/clip_{i+1}.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", VIDEO_PATH,
        "-ss", str(start),
        "-to", str(end),
        "-c:v", "libx264",
        "-c:a", "aac",
        output_path
    ]

    subprocess.run(cmd)

    print(f"🔥 Clip created: {output_path}")

print("\n✅ ALL VIRAL CLIPS GENERATED SUCCESSFULLY!")