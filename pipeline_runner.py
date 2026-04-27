from asr_engine import transcribe
from ai_viral_engine import analyze_video
from clip_generator import generate_clips
from caption_engine import generate_captions
from subtitle_burner import burn_subtitles

import traceback
import os
import uuid


def safe_float(x, default=0.0):
    try:
        return round(float(x), 2)
    except Exception:
        return default


def safe_dict_list(x):
    if not isinstance(x, list):
        return []
    return [i for i in x if isinstance(i, dict)]


def safe_get(d, key):
    if not isinstance(d, dict):
        return None
    return d.get(key)


def get_captions_for_clip(captions, clip_start, clip_end):
    captions = safe_dict_list(captions)
    result = []
    clip_duration = clip_end - clip_start

    for c in captions:
        s = safe_get(c, "start")
        e = safe_get(c, "end")

        if s is None or e is None:
            continue

        s = safe_float(s)
        e = safe_float(e)

        if e < clip_start or s > clip_end:
            continue

        start = max(0, s - clip_start)
        end = min(clip_duration, e - clip_start)

        if end - start < 0.15:
            continue

        text = str(safe_get(c, "text") or "").strip()

        if not text:
            continue

        result.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "text": text
        })

    return result


def generate_social_caption(title, hashtags, niche):
    if not isinstance(hashtags, list):
        hashtags = ["#viral", "#shorts"]

    hashtag_text = " ".join(hashtags[:5])
    title = title or "This Moment Went Viral"

    return {
        "youtube_caption": f"{title} | Watch this viral moment. {hashtag_text}",
        "instagram_caption": f"{title}\n\n{hashtag_text}",
        "tiktok_caption": f"{title} 🔥 {hashtag_text}",
        "niche": niche or "general"
    }


def build_final_clips(viral, segments):
    clips = []

    MIN_FINAL_CLIP = 18
    MAX_FINAL_CLIP = 35
    MAX_TOTAL_CLIPS = 8

    viral = safe_dict_list(viral)
    segments = safe_dict_list(segments)

    for v in viral[:12]:
        start = safe_float(v.get("start"))
        end = safe_float(v.get("end"))

        if start < 0 or end <= start:
            continue

        duration = end - start

        if duration < MIN_FINAL_CLIP:
            final_end = start + MIN_FINAL_CLIP
        elif duration > MAX_FINAL_CLIP:
            final_end = start + MAX_FINAL_CLIP
        else:
            final_end = end

        clips.append({
            "start": round(start, 2),
            "end": round(final_end, 2),
            "source_text": v.get("text", ""),
            "title": v.get("title", "Untitled Viral Clip"),
            "hashtags": v.get("hashtags", ["#viral"]),
            "niche": v.get("niche", "general"),
            "score": v.get("score", 0),
            "score_breakdown": v.get("score_breakdown", {})
        })

    if len(clips) < 3:
        print("⚠ Using fallback clips")

        for s in segments[:8]:
            start = safe_float(s.get("start"))

            if start < 0:
                continue

            clips.append({
                "start": round(start, 2),
                "end": round(start + 20, 2),
                "source_text": s.get("text", ""),
                "title": "Auto Generated Clip",
                "hashtags": ["#shorts", "#viral"],
                "niche": "general",
                "score": 0,
                "score_breakdown": {}
            })

    unique = []

    for c in clips:
        duplicate = False

        for u in unique:
            if abs(c["start"] - u["start"]) < 15:
                duplicate = True
                break

        if not duplicate:
            unique.append(c)

        if len(unique) >= MAX_TOTAL_CLIPS:
            break

    return unique


def generate_raw_clips_safe(file_path, clips):
    simple_clips = []

    for c in clips:
        simple_clips.append({
            "start": c.get("start"),
            "end": c.get("end")
        })

    try:
        return generate_clips(file_path, simple_clips)
    except TypeError:
        try:
            return generate_clips(file_path, simple_clips, "uploads")
        except TypeError:
            return generate_clips(simple_clips, file_path)


def find_test_video():
    search_dirs = [".", "uploads"]
    video_exts = [".mp4", ".mov", ".mkv", ".avi", ".webm"]

    banned_patterns = [
        "input_raw_",
        "input_clip_",
        "final_",
        "output_",
        "clip_"
    ]

    preferred_names = [
        "input.mp4",
        "myvideo.mp4",
        "video.mp4",
        "video (2).mp4"
    ]

    for preferred in preferred_names:
        root_path = os.path.abspath(preferred)
        if os.path.exists(root_path):
            return root_path

        upload_path = os.path.abspath(os.path.join("uploads", preferred))
        if os.path.exists(upload_path):
            return upload_path

    for folder in search_dirs:
        if not os.path.exists(folder):
            continue

        for name in os.listdir(folder):
            lower_name = name.lower()

            if not lower_name.endswith(tuple(video_exts)):
                continue

            should_skip = False

            for pattern in banned_patterns:
                if pattern in lower_name:
                    should_skip = True
                    break

            if should_skip:
                continue

            path = os.path.abspath(os.path.join(folder, name))

            if os.path.isfile(path):
                return path

    return None


def clean_generated_files():
    os.makedirs("uploads", exist_ok=True)

    prefixes = [
        "input_raw_",
        "input_clip_",
        "final_",
        "thumbnail_"
    ]

    for name in os.listdir("uploads"):
        lower = name.lower()

        for prefix in prefixes:
            if lower.startswith(prefix):
                try:
                    os.remove(os.path.join("uploads", name))
                    print(f"🧹 Removed old generated file: {name}")
                except Exception:
                    pass
                break


def run_pipeline(job_id, file_path, JOBS):
    try:
        JOBS[job_id]["status"] = "processing"

        file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            raise Exception(f"Input video not found: {file_path}")

        print(f"🔥 Input video: {file_path}")

        clean_generated_files()

        print("🔥 STEP 1: ASR")
        data = transcribe(file_path)

        segments = safe_dict_list(data.get("segments", []))
        text = data.get("text", "")

        print(f"🔥 STEP 1 DONE | segments: {len(segments)}")

        if not segments:
            raise Exception("No ASR segments found")

        print("🔥 STEP 2: Captions")
        captions = safe_dict_list(generate_captions(segments))

        print("🔥 STEP 3: Viral analysis")
        viral = safe_dict_list(analyze_video(segments))

        print(f"🔥 Viral segments: {len(viral)}")

        print("🔥 STEP 4: Clip generation")
        clips = build_final_clips(viral, segments)

        print(f"🔥 Clips generated before density filter: {len(clips)}")

        if not clips:
            raise Exception("No clips generated")

        generate_raw_clips_safe(file_path, clips)

        final_clips = []
        approved_clips = []

        print("🔥 STEP 5: Subtitle burn + speech density filter")

        for i, clip in enumerate(clips):
            try:
                clip_start = safe_float(clip.get("start"))
                clip_end = safe_float(clip.get("end"))

                print(f"🔥 Clip timing: {clip_start} → {clip_end}")

                clip_captions = get_captions_for_clip(
                    captions,
                    clip_start,
                    clip_end
                )

                print(f"🔥 Captions for clip: {len(clip_captions)}")

                if len(clip_captions) < 4:
                    print("⚠ Low speech density clip skipped")
                    continue

                input_clip = os.path.abspath(f"uploads/input_clip_{i}.mp4")
                output_clip = os.path.abspath(f"uploads/final_{len(final_clips)}.mp4")

                if not os.path.exists(input_clip):
                    print(f"⚠ Missing clip file: {input_clip}")
                    continue

                final_output = burn_subtitles(
                    input_clip,
                    clip_captions,
                    output_clip
                )

                final_clips.append(final_output)
                approved_clips.append(clip)

            except Exception as clip_error:
                print(f"❌ Clip {i} failed: {clip_error}")
                traceback.print_exc()

        enhanced_clips = []

        for i, clip in enumerate(approved_clips):
            video_path = final_clips[i] if i < len(final_clips) else None

            social_captions = generate_social_caption(
                clip.get("title", "Untitled Viral Clip"),
                clip.get("hashtags", ["#viral"]),
                clip.get("niche", "general")
            )

            enhanced_clips.append({
                "clip_number": i + 1,
                "start": clip.get("start"),
                "end": clip.get("end"),
                "duration": round(
                    safe_float(clip.get("end")) - safe_float(clip.get("start")),
                    2
                ),
                "video_path": video_path,
                "download_url": video_path,
                "source_text": clip.get("source_text", ""),
                "title": clip.get("title", "Untitled Viral Clip"),
                "hashtags": clip.get("hashtags", ["#viral"]),
                "niche": clip.get("niche", "general"),
                "score": clip.get("score", 0),
                "score_breakdown": clip.get("score_breakdown", {}),
                "social_captions": social_captions
            })

        if not enhanced_clips:
            raise Exception("All clips rejected by speech density filter")

        JOBS[job_id]["status"] = "completed"

        result = {
            "status": "done",
            "text": text,
            "captions": captions,
            "viral_segments": viral,
            "clips": enhanced_clips,
            "final_clips": final_clips
        }

        JOBS[job_id]["result"] = result

        print("✅ PIPELINE COMPLETE")
        print("\n🔥 FINAL RESULT:")
        print(result)

        return result

    except Exception as e:
        traceback.print_exc()

        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)

        return {
            "status": "failed",
            "error": str(e)
        }


if __name__ == "__main__":
    JOBS = {}
    job_id = str(uuid.uuid4())

    test_video = find_test_video()

    if not test_video:
        print("❌ No input video found.")
        print("Put your original test video here:")
        print("C:\\ai_projects\\input.mp4")
    else:
        print(f"🔥 Test video found: {test_video}")

        JOBS[job_id] = {
            "status": "queued",
            "result": None,
            "error": None
        }

        run_pipeline(job_id, test_video, JOBS)