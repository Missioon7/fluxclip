from moviepy import VideoFileClip
import os

video_path = os.path.join("uploads", "input1.mp4")

clip = VideoFileClip(video_path)

print("Video loaded successfully")
print("Duration:", clip.duration)
print("FPS:", clip.fps)
print("Size:", clip.size)

clip.close()