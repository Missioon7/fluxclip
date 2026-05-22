import csv
import json
from pathlib import Path


INPUT_PATH = Path("audit_reports") / "crop_planner_test.json"
CSV_PATH = Path("audit_reports") / "crop_plan_timeline.csv"
SUMMARY_PATH = Path("audit_reports") / "crop_plan_summary.txt"


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def main():
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    frames = data.get("frames", [])

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["time_sec", "target_x", "smoothed_x", "crop_x", "detected"]
        )
        writer.writeheader()
        for frame in frames:
            writer.writerow({
                "time_sec": frame.get("time_sec"),
                "target_x": frame.get("target_x"),
                "smoothed_x": frame.get("smoothed_x"),
                "crop_x": frame.get("crop_x"),
                "detected": frame.get("detected")
            })

    crop_values = [safe_float(frame.get("crop_x")) for frame in frames]
    jumps = [
        abs(crop_values[i] - crop_values[i - 1])
        for i in range(1, len(crop_values))
    ]
    max_jump = max(jumps) if jumps else 0.0

    total_frames = len(frames)
    crop_width = data.get("crop_width")
    min_crop_x = data.get("min_crop_x")
    max_crop_x = data.get("max_crop_x")
    avg_crop_x = data.get("avg_crop_x")
    smooth_enough = bool(total_frames) and max_jump <= 36

    summary = "\n".join([
        "Crop Plan Movement Summary",
        f"total frames: {total_frames}",
        f"crop_width: {crop_width}",
        f"min crop_x: {min_crop_x}",
        f"max crop_x: {max_crop_x}",
        f"avg crop_x: {avg_crop_x}",
        f"max jump between sampled crop_x values: {round(max_jump, 2)}",
        f"movement looks smooth enough for FFmpeg integration: {smooth_enough}",
        ""
    ])
    SUMMARY_PATH.write_text(summary, encoding="utf-8")

    print(f"csv: {CSV_PATH}")
    print(f"summary: {SUMMARY_PATH}")
    print(f"total frames: {total_frames}")
    print(f"crop_width: {crop_width}")
    print(f"min crop_x: {min_crop_x}")
    print(f"max crop_x: {max_crop_x}")
    print(f"avg crop_x: {avg_crop_x}")
    print(f"max jump between sampled crop_x values: {round(max_jump, 2)}")
    print(f"movement looks smooth enough for FFmpeg integration: {smooth_enough}")


if __name__ == "__main__":
    main()
