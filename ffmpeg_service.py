import subprocess
from config import FFMPEG_PRESET, CRF, CLIP_DURATION


# =========================
# RUN FFmpeg COMMAND
# =========================
def run_cmd(cmd):
    print("\n🔥 FFmpeg:")
    print(" ".join(cmd))

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        print("❌ ERROR:")
        print(result.stderr)
        raise Exception("FFmpeg failed")

    print("✅ SUCCESS")
    return True


# =========================
# CLIP CUT
# =========================
def extract_clip(input_path, output_path, start_time):
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(CLIP_DURATION),
        "-c:v", "libx264",
        "-preset", FFMPEG_PRESET,
        "-c:a", "aac",
        output_path
    ]
    return run_cmd(cmd)


# =========================
# VERTICAL FORMAT (SHORTS)
# =========================
def format_vertical(input_path, output_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=720:1280",
        "-c:v", "libx264",
        "-preset", FFMPEG_PRESET,
        "-c:a", "aac",
        output_path
    ]
    return run_cmd(cmd)


# =========================
# SUBTITLE BURN
# =========================
def burn_subtitles(input_path, ass_path, output_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", f"subtitles={ass_path}",
        "-c:v", "libx264",
        "-preset", FFMPEG_PRESET,
        "-crf", str(CRF),
        "-c:a", "aac",
        output_path
    ]
    return run_cmd(cmd)