import json
import sys
from pathlib import Path

import cv2


PLANNER_PATH = Path("audit_reports") / "crop_planner_test.json"
OUTPUT_PATH = Path("uploads") / "smart_crop_preview.mp4"
PREVIEW_SECONDS = 10.0
OUTPUT_SIZE = (720, 1280)


def load_crop_plan():
    data = json.loads(PLANNER_PATH.read_text(encoding="utf-8"))
    frames = data.get("frames", [])
    crop_width = int(data.get("crop_width") or 0)

    if crop_width <= 0:
        raise ValueError("Invalid crop_width in crop planner report")
    if not frames:
        raise ValueError("No crop planner frames found")

    timeline = []
    for frame in frames:
        time_sec = frame.get("time_sec")
        crop_x = frame.get("crop_x")
        if time_sec is None or crop_x is None:
            continue
        timeline.append((float(time_sec), float(crop_x)))

    if not timeline:
        raise ValueError("No usable crop_x timeline found")

    timeline.sort(key=lambda item: item[0])
    return crop_width, timeline


def nearest_crop_x(timeline, time_sec, cursor):
    while cursor + 1 < len(timeline):
        current_distance = abs(timeline[cursor][0] - time_sec)
        next_distance = abs(timeline[cursor + 1][0] - time_sec)
        if next_distance > current_distance:
            break
        cursor += 1
    return timeline[cursor][1], cursor


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python smart_crop_preview.py <source_video_path>")

    source_path = Path(sys.argv[1])
    if not source_path.exists():
        raise FileNotFoundError(f"Source video not found: {source_path}")

    crop_width, timeline = load_crop_plan()

    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open source video: {source_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    if source_width <= 0 or source_height <= 0:
        cap.release()
        raise RuntimeError("Could not read source video dimensions")
    if crop_width > source_width:
        cap.release()
        raise ValueError("crop_width is wider than source video")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(OUTPUT_PATH),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        OUTPUT_SIZE
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Could not create output video: {OUTPUT_PATH}")

    max_frames = int(round(fps * PREVIEW_SECONDS))
    max_crop_x = source_width - crop_width
    crop_values = []
    timeline_cursor = 0
    frame_count = 0

    while frame_count < max_frames:
        ok, frame = cap.read()
        if not ok:
            break

        time_sec = frame_count / fps
        crop_x, timeline_cursor = nearest_crop_x(timeline, time_sec, timeline_cursor)
        x = int(round(max(0, min(max_crop_x, crop_x))))
        cropped = frame[0:source_height, x:x + crop_width]
        resized = cv2.resize(cropped, OUTPUT_SIZE, interpolation=cv2.INTER_AREA)
        writer.write(resized)

        crop_values.append(x)
        frame_count += 1

    writer.release()
    cap.release()

    if not crop_values:
        raise RuntimeError("No frames were rendered")

    print(f"output path: {OUTPUT_PATH}")
    print(f"frame count: {frame_count}")
    print(f"fps: {round(fps, 2)}")
    print(f"crop range used: {min(crop_values)} to {max(crop_values)}")


if __name__ == "__main__":
    main()
