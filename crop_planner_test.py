import json
from pathlib import Path


INPUT_PATH = Path("audit_reports") / "face_tracking_test.json"
OUTPUT_PATH = Path("audit_reports") / "crop_planner_test.json"


def clamp(value, low, high):
    return max(low, min(high, value))


def main():
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))

    video_width = int(data.get("video_width") or 0)
    video_height = int(data.get("video_height") or 0)
    frames = data.get("frames", [])

    if video_width <= 0 or video_height <= 0:
        raise ValueError("Invalid video dimensions in face tracking report")

    crop_width = int(video_height * 9 / 16)
    max_crop_x = max(0, video_width - crop_width)
    video_center_x = video_width / 2.0

    smoothed_x = None
    previous_crop_x = None
    planned = []

    for frame in frames:
        detected = bool(frame.get("detected"))
        center_x = frame.get("center_x")

        if detected and center_x is not None:
            target_x = float(center_x)
        elif smoothed_x is not None:
            target_x = smoothed_x
        else:
            target_x = video_center_x

        if smoothed_x is None:
            smoothed_x = target_x
        else:
            smoothed_x = smoothed_x * 0.93 + target_x * 0.07

        crop_x = clamp(smoothed_x - crop_width / 2.0, 0, max_crop_x)
        if previous_crop_x is not None:
            crop_x = clamp(
                crop_x,
                previous_crop_x - 18,
                previous_crop_x + 18
            )
            crop_x = clamp(crop_x, 0, max_crop_x)
        previous_crop_x = crop_x

        planned.append({
            "frame_index": frame.get("frame_index"),
            "time_sec": frame.get("time_sec"),
            "detected": detected,
            "target_x": round(target_x, 2),
            "smoothed_x": round(smoothed_x, 2),
            "crop_x": round(crop_x, 2),
            "crop_width": crop_width
        })

    crop_values = [p["crop_x"] for p in planned]
    min_crop_x = min(crop_values) if crop_values else 0
    max_crop_x_seen = max(crop_values) if crop_values else 0
    avg_crop_x = sum(crop_values) / len(crop_values) if crop_values else 0
    movement_range = max_crop_x_seen - min_crop_x
    movement_significant = movement_range >= max(24, crop_width * 0.12)

    report = {
        "source_report": str(INPUT_PATH),
        "video_width": video_width,
        "video_height": video_height,
        "crop_width": crop_width,
        "min_crop_x": round(min_crop_x, 2),
        "max_crop_x": round(max_crop_x_seen, 2),
        "avg_crop_x": round(avg_crop_x, 2),
        "sampled_frames": len(planned),
        "movement_range": round(movement_range, 2),
        "movement_significant": movement_significant,
        "frames": planned
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"crop_width: {crop_width}")
    print(f"min crop_x: {round(min_crop_x, 2)}")
    print(f"max crop_x: {round(max_crop_x_seen, 2)}")
    print(f"avg crop_x: {round(avg_crop_x, 2)}")
    print(f"number of sampled frames: {len(planned)}")
    print(f"movement is significant: {movement_significant}")


if __name__ == "__main__":
    main()
