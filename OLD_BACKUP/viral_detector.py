from moviepy import VideoFileClip
import numpy as np

video_path = "uploads/input1.mp4"
clip = VideoFileClip(video_path)

duration = int(clip.duration)
step = 1  # 1 sec analysis

scores = []

print("Analyzing video for viral moments...")

for t in range(0, duration, step):
    frame = clip.get_frame(t)

    # simple energy score (brightness as proxy)
    score = np.mean(frame)

    scores.append((t, score))

clip.close()

# top moments
top = sorted(scores, key=lambda x: x[1], reverse=True)[:10]

print("\n🔥 TOP VIRAL MOMENTS:")
for t, s in top:
    print(f"Time: {t}s | Score: {s}")