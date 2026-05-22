import os
import subprocess
import cv2

OUTPUT_DIR = "uploads"

MIN_CLIP_DURATION = 1
MAX_CLIP_DURATION = 60
MAX_CLIPS = 30

OUTPUT_WIDTH = 720
OUTPUT_HEIGHT = 1280


def safe_float(x, default=0.0):
    try:
        return float(x)
    except:
        return default


def safe_run(cmd):
    print("🔥 RUNNING FFmpeg:")
    print(" ".join(str(x) for x in cmd))

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("FFmpeg failed")

    print("✅ FFmpeg SUCCESS")
    return result


def clamp_duration(start, end):
    start = safe_float(start)
    end = safe_float(end)

    if end <= start:
        end = start + 20

    duration = end - start

    if duration < MIN_CLIP_DURATION:
        duration = MIN_CLIP_DURATION

    if duration > MAX_CLIP_DURATION:
        duration = MAX_CLIP_DURATION

    return start, duration


def get_video_size(video_path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        w, h = result.stdout.strip().split("x")
        return int(w), int(h)
    except:
        return 1280, 720


def detect_face_center(video_path, start_time=0):
    try:
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)

        if fps <= 0:
            fps = 25

        frame_positions = [
            int((start_time + 1) * fps),
            int((start_time + 3) * fps),
            int((start_time + 5) * fps)
        ]

        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades +
            "haarcascade_frontalface_default.xml"
        )

        centers = []

        for pos in frame_positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()

            if not ok:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(50, 50)
            )

            if len(faces) == 0:
                continue

            faces = sorted(
                faces,
                key=lambda f: f[2] * f[3],
                reverse=True
            )

            x, y, w, h = faces[0]
            centers.append(x + w / 2)

        cap.release()

        if not centers:
            return None

        return sum(centers) / len(centers)

    except:
        return None


def build_blur_background_filter():
    # V47.1 low-res rescue render:
    # Darker cinematic blur canvas + safer foreground presentation.
    # This avoids making tiny 256x144 sources look like broken full-screen crops.
    return (
        "[0:v]scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280,"
        "boxblur=36:3,"
        "eq=brightness=-0.10:contrast=1.10:saturation=1.15[bg];"
        "[0:v]scale=680:1180:force_original_aspect_ratio=decrease,"
        "unsharp=3:3:0.45,"
        "pad=iw+18:ih+18:9:9:color=black@0.55[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2-40,setsar=1,fps=25,setpts=PTS-STARTPTS"
    )


def build_crop_filter(video_path, clip_start):
    width, height = get_video_size(video_path)

    print(f"?? Source video size: {width}x{height}")

    if not width or not height:
        print("LOW_RES_VERTICAL_FALLBACK active | invalid source size")
        return build_blur_background_filter()

    crop_width = int(height * 9 / 16)

    if width < 480 or height < 360 or crop_width < 220:
        print(
            f"LOW_RES_VERTICAL_FALLBACK active | "
            f"source={width}x{height} | crop_width={crop_width}"
        )
        return build_blur_background_filter()

    if height >= width:
        return (
            "scale=720:1280:force_original_aspect_ratio=increase,"
            "crop=720:1280,"
            "setsar=1"
        )

    if crop_width > width:
        crop_width = width

    face_center = detect_face_center(video_path, clip_start)

    if face_center is None:
        x = int((width - crop_width) / 2)
        print("?? Crop mode: center fallback")
    else:
        x = int(face_center - crop_width / 2)
        x = max(0, min(x, width - crop_width))
        print(
            f"?? Crop mode: face-safe | "
            f"face_x={round(face_center,1)} | crop_x={x}"
        )

    return (
        f"crop={crop_width}:{height}:{x}:0,"
        f"scale=720:1280,"
        f"setsar=1"
    )


# -------------------------
# NEW V6 THUMBNAIL ENGINE
# -------------------------
def generate_thumbnail(video_path, clip_index):
    try:
        thumbnail_path = os.path.join(
            OUTPUT_DIR,
            f"thumbnail_{clip_index}.jpg"
        )

        safe_run([
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-ss",
            "3",
            "-vframes",
            "1",
            thumbnail_path
        ])

        if os.path.exists(thumbnail_path):
            print(f"🖼 Thumbnail created: {thumbnail_path}")
            return thumbnail_path

        return None

    except Exception as e:
        print(f"⚠ Thumbnail generation failed: {e}")
        return None


def generate_clips(file_path, clips, output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)

    created = []

    for i, clip in enumerate(clips[:MAX_CLIPS]):
        start = safe_float(clip.get("start"))
        end = safe_float(clip.get("end"))

        start, duration = clamp_duration(start, end)
        final_end = round(start + duration, 2)

        print(
            f"\n🔥 CLIP {i}: "
            f"{round(start,2)} → {final_end}"
        )

        raw_clip = os.path.join(
            output_dir,
            f"input_raw_{i}.mp4"
        )

        final_clip = os.path.join(
            output_dir,
            f"input_clip_{i}.mp4"
        )

        safe_run([
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            file_path,
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            raw_clip
        ])

        vf = build_crop_filter(file_path, start)

        filter_arg = "-filter_complex" if "[bg][fg]overlay" in vf else "-vf"

        safe_run([
            "ffmpeg",
            "-y",
            "-fflags",
            "+genpts",
            "-i",
            raw_clip,
            filter_arg,
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-af",
            "asetpts=PTS-STARTPTS",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            final_clip
        ])

        if not os.path.exists(final_clip):
            raise RuntimeError(
                f"Final clip not created: {final_clip}"
            )

        thumbnail_path = generate_thumbnail(
            final_clip,
            i
        )

        print(f"✅ FINAL CLIP CREATED: {final_clip}")

        created.append({
            "path": final_clip,
            "thumbnail": thumbnail_path,
            "start": round(start, 2),
            "end": final_end,
            "duration": round(duration, 2)
        })

    print(
        f"\n🔥 TOTAL CLIPS CREATED: {len(created)}"
    )

    return created