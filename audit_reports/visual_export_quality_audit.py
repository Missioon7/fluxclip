import json, subprocess
from pathlib import Path

SRC = Path("uploads/e0926df0-8fdb-4441-9d95-af58ba1a3ec5.mp4")
OUT = Path("audit_reports/VISUAL_EXPORT_QUALITY_AUDIT.md")
START = 112.38
END = 173.38

def ffprobe():
    cmd = [
        "ffprobe","-v","error",
        "-show_entries","format=duration,bit_rate:stream=width,height,r_frame_rate,codec_type",
        "-of","json",str(SRC)
    ]
    return json.loads(subprocess.check_output(cmd, text=True, errors="replace"))

data = ffprobe()
fmt = data.get("format", {})
video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})

w = int(video.get("width") or 0)
h = int(video.get("height") or 0)
duration = float(fmt.get("duration") or 0)
bitrate = fmt.get("bit_rate", "unknown")
fps = video.get("r_frame_rate", "unknown")

scale_factor = round(max(720 / max(w,1), 1280 / max(h,1)), 2)

if w < 320 or h < 240:
    tier = "low_res_rescue"
    blur = "severe"
    readiness = "preview_only"
    profile = "low_res_rescue"
elif w < 720 or h < 720:
    tier = "standard"
    blur = "medium"
    readiness = "viewer_grade_possible"
    profile = "viewer_grade"
else:
    tier = "high_quality"
    blur = "low"
    readiness = "viewer_grade_possible"
    profile = "viewer_grade"

reasons = []
if tier == "low_res_rescue":
    reasons.append("source resolution is extremely low; normal vertical crop will look blurry")
if scale_factor > 5:
    reasons.append(f"scale factor is very high ({scale_factor}x)")
if h < 300:
    reasons.append("foreground detail is too small for premium-looking 720x1280 export")

lines = [
    "# Visual Export Quality Audit",
    "",
    f"- source_path: {SRC}",
    f"- source_resolution: {w}x{h}",
    f"- source_duration: {duration:.2f}s",
    f"- source_fps: {fps}",
    f"- source_bitrate: {bitrate}",
    f"- canonical_window: {START}->{END}",
    f"- canonical_duration: {END-START:.2f}s",
    f"- source_tier: {tier}",
    f"- scale_factor_to_720x1280: {scale_factor}x",
    f"- blur_risk: {blur}",
    f"- current_expected_render_mode: low-res blur-background fallback",
    f"- recommended_render_profile: {profile}",
    f"- crop_confidence: low",
    f"- subtitle_risk: medium",
    f"- visual_export_readiness: {readiness}",
    "",
    "## Reasons",
]
lines += [f"- {r}" for r in reasons]
lines += [
    "",
    "## Recommended next upgrade",
    "- Build low-res rescue render profile before judging editorial output quality.",
    "- Improve blur-background composition, foreground sizing, border/shadow, and subtitle-safe zones.",
]

OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)
print(f"source_resolution={w}x{h}")
print(f"source_tier={tier}")
print(f"blur_risk={blur}")
print(f"visual_export_readiness={readiness}")
