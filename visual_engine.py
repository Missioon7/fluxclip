import cv2
import json
import time
from pathlib import Path

def analyze_visual_moments(video_path, sample_every_sec=2.0, max_frames=900):
    """
    V22 Visual Intelligence Foundation:
    - scene brightness
    - motion energy
    - face presence if haarcascade available
    - visual spike moments
    Lightweight, safe CPU version.
    """
    video_path = str(video_path)
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return {"ok": False, "error": "video_open_failed", "moments": []}

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total_frames / fps if fps else 0

    step = max(1, int(fps * sample_every_sec))
    face_cascade = None

    try:
        haar = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(haar)
    except Exception:
        face_cascade = None

    moments = []
    prev_gray = None
    frame_idx = 0
    sampled = 0

    while sampled < max_frames:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_idx % step != 0:
            frame_idx += 1
            continue

        ts = frame_idx / fps if fps else 0
        small = cv2.resize(frame, (320, 180))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        brightness = float(gray.mean())
        motion = 0.0

        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            motion = float(diff.mean())

        faces = 0
        if face_cascade is not None and not face_cascade.empty():
            detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
            faces = len(detected)

        visual_score = 0
        visual_score += min(30, motion * 1.8)
        visual_score += 10 if faces > 0 else 0
        visual_score += 6 if 45 <= brightness <= 190 else -4

        moments.append({
            "time": round(ts, 2),
            "brightness": round(brightness, 2),
            "motion": round(motion, 2),
            "faces": faces,
            "visual_score": round(visual_score, 2),
        })

        prev_gray = gray
        frame_idx += 1
        sampled += 1

    cap.release()

    top = sorted(moments, key=lambda x: x["visual_score"], reverse=True)[:20]

    return {
        "ok": True,
        "duration": round(duration, 2),
        "sampled": len(moments),
        "top_moments": top,
    }


def log_visual_intelligence(job_id, video_path):
    try:
        Path("analytics").mkdir(exist_ok=True)
        data = analyze_visual_moments(video_path)
        row = {
            "ts": time.time(),
            "job_id": job_id,
            "video_path": str(video_path),
            "visual": data,
        }
        with open("analytics/visual_intelligence.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"✅ V22 visual intelligence logged for {job_id}")
        return data
    except Exception as e:
        print(f"⚠ V22 visual intelligence failed: {e}")
        return {"ok": False, "error": str(e)}




def extract_best_thumbnail_frames(video_path, job_id, top_n=5):
    """
    V24 Thumbnail Intelligence:
    saves best visual frames from V22 top moments.
    """
    try:
        data = analyze_visual_moments(video_path)
        if not data.get("ok"):
            return {"ok": False, "error": data.get("error"), "frames": []}

        out_dir = Path("uploads")
        out_dir.mkdir(exist_ok=True)

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25

        frames = []
        for i, m in enumerate(data.get("top_moments", [])[:top_n]):
            ts = float(m.get("time", 0))
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(ts * fps))
            ok, frame = cap.read()
            if not ok:
                continue

            path = out_dir / f"{job_id}_thumb_ai_{i}.jpg"
            cv2.imwrite(str(path), frame)

            frames.append({
                "time": round(ts, 2),
                "path": f"/uploads/{path.name}",
                "visual_score": m.get("visual_score"),
                "motion": m.get("motion"),
                "faces": m.get("faces"),
                "brightness": m.get("brightness"),
            })

        cap.release()

        row = {
            "ts": time.time(),
            "job_id": job_id,
            "frames": frames,
        }

        Path("analytics").mkdir(exist_ok=True)
        with open("analytics/thumbnail_intelligence.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        print(f"✅ V24 thumbnail frames extracted: {len(frames)}")
        return {"ok": True, "frames": frames}

    except Exception as e:
        print(f"⚠ V24 thumbnail extraction failed: {e}")
        return {"ok": False, "error": str(e), "frames": []}
