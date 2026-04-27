import os
import subprocess
import re


PLAY_RES_X = 720
PLAY_RES_Y = 1280


def seconds_to_ass(seconds):
    seconds = max(0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def clean_ass_text(text):
    text = str(text or "")
    text = text.replace("\\", "")
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")
    text = text.replace("{", "")
    text = text.replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def wrap_caption(text, max_chars=28):
    text = clean_ass_text(text)
    words = text.split()

    lines = []
    line = ""

    for word in words:
        test = (line + " " + word).strip()

        if len(test) <= max_chars:
            line = test
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    # max 2 lines only
    if len(lines) > 2:
        first = lines[0]
        second = " ".join(lines[1:])
        lines = [first, second]

    return r"\N".join(lines)


def write_ass_file(ass_path, captions):
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(f"""[Script Info]
Title: OPUS AI Captions Safe v4.6
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,6,2,2,55,55,205,1
Style: Pop,Arial,56,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,102,102,0,0,1,6,2,2,55,55,205,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
""")

        for idx, c in enumerate(captions):
            start = seconds_to_ass(c.get("start", 0))
            end = seconds_to_ass(c.get("end", 0))
            text = wrap_caption(c.get("text", ""))

            if not text:
                continue

            style = "Pop" if idx % 2 == 0 else "Default"
            styled_text = r"{\fad(60,60)\bord6\shad2}" + text

            f.write(
                f"Dialogue: 0,{start},{end},{style},,0,0,0,,{styled_text}\n"
            )


def burn_subtitles(video_path, captions, output_path=None):
    if not captions:
        print("⚠ No captions, skipping subtitle burn")
        return video_path

    video_path = os.path.abspath(video_path)

    if output_path:
        final_output = os.path.abspath(output_path)
    else:
        base = os.path.splitext(video_path)[0]
        final_output = base + "_final.mp4"

    ass_path = os.path.splitext(video_path)[0] + ".ass"

    write_ass_file(ass_path, captions)

    ass_path_fixed = os.path.abspath(ass_path)
    ass_path_fixed = ass_path_fixed.replace("\\", "/")
    ass_path_fixed = ass_path_fixed.replace(":", "\\:")

    if os.path.exists(final_output):
        os.remove(final_output)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", f"subtitles='{ass_path_fixed}'",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        final_output
    ]

    print("\n🔥 FFmpeg subtitle command:")
    print(" ".join(cmd))

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    if result.returncode != 0:
        print("❌ Subtitle burn failed:")
        print(result.stderr)
        return video_path

    print(f"✅ Subtitle video created: {final_output}")
    return final_output