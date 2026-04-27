import os
import subprocess
import textwrap
import uuid

# -----------------------------
# VIRAL SUBTITLE CONFIG (OPUS STYLE)
# -----------------------------
FONT_SIZE = 56
FONT_NAME = "Arial"
MAX_WIDTH = 34

PRIMARY_COLOR = "&H00FFFFFF"   # white
OUTLINE_COLOR = "&H00000000"   # black
BOX_COLOR = "&H80000000"       # semi-transparent black


# -----------------------------
# TEXT CLEANING (CRASH FIX)
# -----------------------------
def clean_text(text: str):
    if not text:
        return ""

    text = text.replace("\n", " ")
    text = text.replace(",", " ")
    text = text.replace(";", " ")
    return text.strip()


# -----------------------------
# WRAP TEXT (MOBILE OPTIMIZED)
# -----------------------------
def wrap_text(text: str):
    text = clean_text(text)
    return r"\N".join(textwrap.wrap(text, width=MAX_WIDTH))


# -----------------------------
# TIME FORMAT (ASS FORMAT SAFE)
# -----------------------------
def format_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int((t - int(t)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# -----------------------------
# CREATE ASS FILE (FIXED FORMAT)
# -----------------------------
def create_ass(segments, ass_path):

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment
Style: Default,Arial,56,&H00FFFFFF,&H00000000,&H80000000,1,0,3,3,1,2

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = ""

    for seg in segments:
        start = format_time(seg["start"])
        end = format_time(seg["end"])
        text = wrap_text(seg.get("text", ""))

        # SAFETY: avoid ASS breaking
        text = text.replace("{", "").replace("}", "")

        events += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + events)

    return ass_path


# -----------------------------
# FFmpeg EXECUTION (SAFE + LOGGING)
# -----------------------------
def run_ffmpeg(cmd):
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if process.returncode != 0:
        print("❌ FFmpeg ERROR:")
        print(process.stderr.decode("utf-8", errors="ignore"))
        raise Exception("FFmpeg subtitle burn failed")

    return True


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def burn_subtitles(video_path, segments, output_dir):

    if not os.path.exists(video_path):
        raise FileNotFoundError("Video not found")

    file_id = str(uuid.uuid4())
    ass_path = os.path.join(output_dir, f"{file_id}.ass")
    output_path = os.path.join(output_dir, f"{file_id}_subbed.mp4")

    print("📝 Creating ASS subtitles...")

    create_ass(segments, ass_path)

    print("🔥 Burning subtitles via FFmpeg...")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "copy",
        output_path
    ]

    run_ffmpeg(cmd)

    print("✅ Subtitle burn complete:", output_path)

    return output_path