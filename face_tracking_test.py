import argparse
import json
from pathlib import Path

import cv2


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def run_face_tracking_test(video_path):
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = safe_float(cap.get(cv2.CAP_PROP_FPS), 0.0)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        raise RuntimeError(f"Could not load Haar cascade: {cascade_path}")

    sampled = []
    frame_index = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_index % 15 != 0:
            frame_index += 1
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        detected = False
        center_x = None
        center_y = None
        confidence = 0.0

        if len(faces) > 0:
            x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
            center_x = x + w / 2.0
            center_y = y + h / 2.0
            confidence = 1.0
            detected = True

        sampled.append({
            "frame_index": frame_index,
            "time_sec": round(frame_index / fps, 3) if fps > 0 else 0.0,
            "detected": detected,
            "center_x": round(center_x, 2) if center_x is not None else None,
            "center_y": round(center_y, 2) if center_y is not None else None,
            "confidence": round(confidence, 4)
        })

        frame_index += 1

    cap.release()

    detected_frames = [f for f in sampled if f["detected"]]
    total_sampled = len(sampled)
    detected_count = len(detected_frames)
    detection_rate = (detected_count / total_sampled * 100.0) if total_sampled else 0.0
    centers_x = [f["center_x"] for f in detected_frames if f["center_x"] is not None]
    avg_center_x = sum(centers_x) / len(centers_x) if centers_x else None

    report = {
        "video_path": str(video_path),
        "video_width": width,
        "video_height": height,
        "sample_every_frames": 15,
        "total_sampled_frames": total_sampled,
        "frames_with_face_detected": detected_count,
        "detection_rate_percent": round(detection_rate, 2),
        "average_face_center_x": round(avg_center_x, 2) if avg_center_x is not None else None,
        "frames": sampled
    }

    output_path = Path("audit_reports") / "face_tracking_test.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"video width: {width}")
    print(f"video height: {height}")
    print(f"total sampled frames: {total_sampled}")
    print(f"frames with face detected: {detected_count}")
    print(f"detection rate percentage: {round(detection_rate, 2)}")
    print(f"average face center x: {round(avg_center_x, 2) if avg_center_x is not None else None}")
    print(f"json report: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Sample video frames and test face tracking.")
    parser.add_argument("video_path", help="Path to the input video")
    args = parser.parse_args()
    run_face_tracking_test(args.video_path)


if __name__ == "__main__":
    main()
