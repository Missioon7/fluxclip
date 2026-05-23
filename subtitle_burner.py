import os
import re
import subprocess
from pathlib import Path


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


def ass_escape(text):
    return clean_ass_text(text).replace(",", " ")


def wrap_caption(text, max_chars=22):
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

    if len(lines) > 2:
        first = lines[0]
        second = " ".join(lines[1:])
        lines = [first, second]

    return r"\N".join(lines)


def write_ass_file(ass_path, captions, hook_text=None):
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(f"""[Script Info]
Title: FluxClip Captions + Editorial Hook
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Noto Sans Devanagari,34,&H00FFFFFF,&H000000FF,&H00000000,&H66000000,-1,0,0,0,100,100,0,0,1,3,1,2,70,70,90,1
Style: Pop,Noto Sans Devanagari,38,&H00FFFFFF,&H000000FF,&H00000000,&H66000000,-1,0,0,0,102,102,0,0,1,3,1,2,70,70,90,1
Style: Hook,Noto Sans Devanagari,42,&H00FFFFFF,&H000000FF,&H00111111,&HAA000000,-1,0,0,0,100,100,0,0,1,4,2,8,56,56,72,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
""")

        if hook_text:
            hook = wrap_caption(hook_text, max_chars=24)
            if hook:
                f.write(
                    "Dialogue: 1,0:00:00.00,0:00:02.80,Hook,,0,0,0,,"
                    + r"{\fad(120,180)\bord4\shad2}" + hook + "\n"
                )

        for idx, c in enumerate(captions):
            start = seconds_to_ass(c.get("start", 0))
            end = seconds_to_ass(c.get("end", 0))
            text = wrap_caption(c.get("text", ""))
            if not text:
                continue
            style = "Pop" if idx % 2 == 0 else "Default"
            styled_text = r"{\fad(40,40)\bord3\shad1}" + text
            f.write(f"Dialogue: 0,{start},{end},{style},,0,0,0,,{styled_text}\n")


def safe_hook_text(metadata):
    metadata = metadata if isinstance(metadata, dict) else {}
    text = metadata.get("hook_text") or metadata.get("title") or metadata.get("upload_title") or ""
    text = ass_escape(text)
    words = text.split()
    if len(words) > 14:
        text = " ".join(words[:14])
    return text[:96].strip()


def broll_terms(metadata):
    metadata = metadata if isinstance(metadata, dict) else {}
    raw = " ".join(str(metadata.get(k, "")) for k in ["niche", "title", "text"])
    tokens = re.findall(r"[a-zA-Z0-9]+", raw.lower())
    stop = {"the", "and", "for", "with", "this", "that", "clip", "video", "shorts", "general"}
    return [t for t in tokens if len(t) >= 4 and t not in stop][:18]


def select_broll_asset(metadata, broll_dir="assets/broll"):
    if os.getenv("FLUXCLIP_ENABLE_BROLL", "1").strip().lower() in {"0", "false", "no"}:
        print("TRANSFORMATIVE_BROLL_SKIPPED reason=disabled")
        return None

    root = Path(broll_dir)
    if not root.exists() or not root.is_dir():
        print(f"TRANSFORMATIVE_BROLL_SKIPPED reason=no_broll_dir path={broll_dir}")
        return None

    exts = {".mp4", ".mov", ".mkv", ".webm", ".jpg", ".jpeg", ".png"}
    assets = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in exts]
    if not assets:
        print(f"TRANSFORMATIVE_BROLL_SKIPPED reason=no_assets path={broll_dir}")
        return None

    terms = broll_terms(metadata)
    if not terms:
        print("TRANSFORMATIVE_BROLL_SKIPPED reason=no_match_terms")
        return None

    for asset in assets:
        name = asset.stem.lower()
        if any(term in name for term in terms):
            print(f"TRANSFORMATIVE_BROLL_SELECTED asset={asset} terms={terms[:5]}")
            return str(asset)

    print(f"TRANSFORMATIVE_BROLL_SKIPPED reason=no_matching_asset terms={terms[:5]}")
    return None


def apply_broll_overlay(video_path, broll_path, output_path):
    if not broll_path:
        return video_path, False

    video_path = os.path.abspath(video_path)
    output_path = os.path.abspath(output_path)
    ext = Path(broll_path).suffix.lower()
    if os.path.exists(output_path):
        os.remove(output_path)

    if ext in {".jpg", ".jpeg", ".png"}:
        input_args = ["-i", video_path, "-loop", "1", "-t", "3", "-i", broll_path]
    else:
        input_args = ["-i", video_path, "-stream_loop", "-1", "-t", "3", "-i", broll_path]

    cmd = [
        "ffmpeg", "-y", *input_args,
        "-filter_complex",
        "[1:v]scale=300:-1,format=rgba,colorchannelmixer=aa=0.90[br];"
        "[0:v][br]overlay=W-w-28:120:enable='between(t,3,6)'",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "copy",
        output_path,
    ]
    print("\nTRANSFORMATIVE_BROLL_FFMPEG:")
    print(" ".join(cmd))
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if result.returncode != 0 or not os.path.exists(output_path):
        print(f"TRANSFORMATIVE_BROLL_SKIPPED reason=ffmpeg_failed error={result.stderr[-500:]}")
        return video_path, False
    return output_path, True


def burn_subtitles(video_path, captions, output_path=None, transform_metadata=None, return_metadata=False):
    empty_metadata = {
        "transformative_overlay_applied": False,
        "broll_applied": False,
        "broll_asset": "",
    }
    if not captions:
        print("No captions, skipping subtitle burn")
        return (video_path, empty_metadata) if return_metadata else video_path

    video_path = os.path.abspath(video_path)
    transform_metadata = transform_metadata if isinstance(transform_metadata, dict) else {}
    hook_text = safe_hook_text(transform_metadata)
    overlay_applied = bool(hook_text)

    if output_path:
        final_output = os.path.abspath(output_path)
    else:
        base = os.path.splitext(video_path)[0]
        final_output = base + "_final.mp4"

    ass_path = os.path.splitext(video_path)[0] + ".ass"
    write_ass_file(ass_path, captions, hook_text=hook_text)

    ass_path_fixed = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")

    if os.path.exists(final_output):
        os.remove(final_output)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{ass_path_fixed}'",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac",
        final_output,
    ]

    print("\nFFmpeg subtitle command:")
    print(" ".join(cmd))
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    if result.returncode != 0:
        print("Subtitle burn failed:")
        print(result.stderr)
        return (video_path, empty_metadata) if return_metadata else video_path

    broll_asset = select_broll_asset(transform_metadata)
    broll_applied = False
    if broll_asset:
        base, ext = os.path.splitext(final_output)
        broll_output = base + "_broll" + ext
        final_output, broll_applied = apply_broll_overlay(final_output, broll_asset, broll_output)

    metadata = {
        "transformative_overlay_applied": overlay_applied,
        "broll_applied": broll_applied,
        "broll_asset": os.path.basename(broll_asset) if broll_asset and broll_applied else "",
    }
    print(f"Subtitle video created: {final_output}")
    return (final_output, metadata) if return_metadata else final_output
