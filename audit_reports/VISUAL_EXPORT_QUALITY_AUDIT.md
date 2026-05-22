# Visual Export Quality Audit

- source_path: uploads\e0926df0-8fdb-4441-9d95-af58ba1a3ec5.mp4
- source_resolution: 256x144
- source_duration: 347.61s
- source_fps: 25/1
- source_bitrate: 692920
- canonical_window: 112.38->173.38
- canonical_duration: 61.00s
- source_tier: low_res_rescue
- scale_factor_to_720x1280: 8.89x
- blur_risk: severe
- current_expected_render_mode: low-res blur-background fallback
- recommended_render_profile: low_res_rescue
- crop_confidence: low
- subtitle_risk: medium
- visual_export_readiness: preview_only

## Reasons
- source resolution is extremely low; normal vertical crop will look blurry
- scale factor is very high (8.89x)
- foreground detail is too small for premium-looking 720x1280 export

## Recommended next upgrade
- Build low-res rescue render profile before judging editorial output quality.
- Improve blur-background composition, foreground sizing, border/shadow, and subtitle-safe zones.