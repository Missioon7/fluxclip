from moviepy import VideoFileClip

video = VideoFileClip("uploads/input1.mp4")
video.audio.write_audiofile("audio.wav")

print("Audio extracted successfully")