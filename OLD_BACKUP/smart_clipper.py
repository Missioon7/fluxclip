from moviepy import VideoFileClip
import os

video_path = "uploads/input1.mp4"
output_folder = "smart_clips"

os.makedirs(output_folder, exist_ok=True)

clip = VideoFileClip(video_path)

duration = int(clip.duration)

# fake "viral moments" (replace from Step 3 later)
viral_times = [1521, 1565, 1563, 1570]

window = 10  # 10 sec before + after

i = 1

for t in viral_times:
    start = max(0, t - window)
    end = min(duration, t + window)

    subclip = clip.subclipped(start, end)

    output_path = os.path.join(output_folder, f"viral_clip_{i}.mp4")

    subclip.write_videofile(output_path, codec="libx264", audio_codec="aac")

    print(f"🔥 Viral clip created: {start}s to {end}s")

    i += 1

clip.close()