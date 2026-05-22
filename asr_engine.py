import re
import os
import torch
import whisper
import signal
import threading
import time
import subprocess
import gc
import sys
import json
from pathlib import Path


# =========================
# OPUS AI ASR ENGINE v4 SPEED
# Stable GPU Whisper + faster decode settings
# =========================

MODEL_NAME = "small"
_model = None
_model_cache = {}
_device = None

ASR_SEVERE_REASON_PREFIXES = (
    "replacement_chars=",
    "devanagari_repeated_token_ratio=",
    "repeated_hindi_phrase=",
    "ultra_short_repeated_segments=",
)
ASR_BORDERLINE_MEDIUM_SAMPLE_MIN = 50
ASR_BORDERLINE_MEDIUM_SAMPLE_MAX = 64
ASR_FW_RETRY_SAMPLE_TIMEOUT_SECONDS = 360
ASR_FW_RETRY_FULL_TIMEOUT_SECONDS = 900
ASR_FW_RETRY_SAMPLE_SECONDS = 180
ASR_FW_RETRY_HEARTBEAT_SECONDS = 30
ASR_FW_RETRY_STALL_SECONDS = 300
ASR_FW_RETRY_FULL_STALL_SECONDS = 120
ASR_FW_RETRY_CHUNK_SECONDS = 75
ASR_FW_RETRY_CHUNK_TIMEOUT_SECONDS = 180
ASR_FW_RETRY_MAX_FAILED_CHUNK_RATIO = 0.30
V49_9_WINDOW_REPAIR_MAX_TIMEOUT_SECONDS = 420


class ASRTimeout(Exception):
    pass


def _v18_timeout_handler(signum, frame):
    raise ASRTimeout("Whisper transcription timeout")


def extract_asr_wav(file_path: str) -> str:
    try:
        base, _ = os.path.splitext(file_path)
        wav_path = base + "_asr_16k.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            file_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            wav_path,
        ]
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
            return wav_path
        print(f"⚠️ ASR WAV extraction produced invalid file, using original: {file_path}")
    except Exception as e:
        print(f"⚠️ ASR WAV extraction failed, using original: {e}")
    return file_path




def get_device():
    global _device

    if _device is None:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"ASR DEVICE: {_device}")

        if _device == "cuda":
            try:
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
            except Exception:
                pass

    return _device


def get_model(model_name=None):
    global _model

    name = model_name or MODEL_NAME
    device = get_device()
    key = (name, device)
    if key not in _model_cache:
        print(f"Loading Whisper model: {name} on {device}")
        _model_cache[key] = whisper.load_model(name, device=device)
        print("Whisper ASR model ready")
        if name == MODEL_NAME:
            _model = _model_cache[key]

    return _model_cache[key]


def release_model(model_name=None):
    global _model

    name = model_name or MODEL_NAME
    keys_to_release = [key for key in _model_cache if key[0] == name]
    for key in keys_to_release:
        del _model_cache[key]

    if name == MODEL_NAME:
        _model = None

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def clean_repeated_phrases(text: str) -> str:
    text = text or ""
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()

    bad_phrases = [
        "high or high",
        "blood has been blood",
        "something something something",
        "it is not showing the media it is not showing the media",
        "because they have to save the experience of china because they have to save the experience of china",
    ]

    for phrase in bad_phrases:
        text = text.replace(phrase, "")

    text = re.sub(r"\b(\w+\s+\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\w+\s+\w+\s+\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"([\u0900-\u097F]{2,}(?:\s+[\u0900-\u097F]{2,}){0,2})\s+\1", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def v27_is_bad_asr_text(text: str) -> bool:
    return v27_bad_asr_reason(text) is not None


def has_devanagari(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", str(text or "")))


def v27_bad_asr_reason(text: str):
    text = str(text or "").strip()
    if not text:
        return "empty_text"

    low = text.lower()
    words = low.split()
    devanagari = has_devanagari(text)

    # Hard hallucination patterns seen in real output
    junk_patterns = [
        "ॐ ॐ",
        "ओम ओम",
        "om om",
        "।।।।",
        "aaaaaa",
        "mmmmmm",
        "hmmmm",
    ]

    for j in junk_patterns:
        if j in low:
            return "junk_pattern"

    # Too repetitive characters
    compact = re.sub(r"\s+", "", low)
    if len(compact) > 12:
        unique_ratio = len(set(compact)) / max(len(compact), 1)
        # Devanagari has combining marks and can look artificially repetitive.
        threshold = 0.10 if devanagari else 0.18
        if unique_ratio < threshold:
            return f"low_unique_char_ratio={unique_ratio:.2f}"

    # Excessive repeated word dominance
    if len(words) >= 4:
        top = max(words.count(w) for w in set(words))
        repeat_ratio = top / len(words)
        threshold = 0.82 if devanagari else 0.65
        if repeat_ratio > threshold:
            return f"word_repeat_ratio={repeat_ratio:.2f}"

    return None


def transcript_quality_score(text, segments=None):
    text = str(text or "")
    segments = segments if isinstance(segments, list) else []
    word_texts = []
    for s in segments:
        if not isinstance(s, dict):
            continue
        words = s.get("words", [])
        if isinstance(words, list):
            word_texts.append(" ".join(str(w.get("word", "")) for w in words if isinstance(w, dict)))

    joined = " ".join(
        [text]
        + [str(s.get("text", "")) for s in segments if isinstance(s, dict)]
        + word_texts
    )
    low = joined.lower()
    words = low.split()
    reasons = []
    penalty = 0

    malformed_patterns = [
        r"\bthe film will time\b",
        r"\bone will on\b",
        r"\byou still him\b",
        r"\bi not i would\b",
        r"\byou can the\b",
        r"\bit does mean that\b",
        r"\bif he is complete\b",
        r"\bwe will very\b",
        r"\btime had then\b",
        r"\byou one phone\b",
        r"\bhow did write\b",
    ]
    malformed_hits = sum(1 for p in malformed_patterns if re.search(p, low))
    if malformed_hits:
        penalty += malformed_hits * 18
        reasons.append(f"malformed_phrases={malformed_hits}")

    junk_patterns = ["à¥ à¥", "à¤“à¤® à¤“à¤®", "om om", "aaaaaa", "mmmmmm"]
    junk_hits = sum(1 for p in junk_patterns if p in low)
    if junk_hits:
        penalty += junk_hits * 20
        reasons.append(f"junk_repetition={junk_hits}")

    replacement_count = joined.count("\ufffd")
    if replacement_count:
        penalty += min(40, replacement_count * 10)
        reasons.append(f"replacement_chars={replacement_count}")

    hindi_tokens = re.findall(r"[\u0900-\u097F\u0688]+", joined)
    if len(hindi_tokens) >= 8:
        top_hindi = max(hindi_tokens.count(w) for w in set(hindi_tokens))
        hindi_repeat_ratio = top_hindi / max(len(hindi_tokens), 1)
        if hindi_repeat_ratio >= 0.16:
            penalty += min(45, int(hindi_repeat_ratio * 90))
            reasons.append(f"devanagari_repeated_token_ratio={hindi_repeat_ratio:.2f}")

    repeated_hindi_patterns = [
        ("अगर तो आप", r"(?:अगर\s+तो\s+आप\s*){2,}"),
        ("अपको अपको", r"(?:अपको\s*){2,}"),
        ("आप आप आप", r"(?:आप\s*){3,}"),
        ("आ\ufffd", r"(?:आ\ufffd\s*){2,}"),
        ("ड ड ड", r"(?:ड\s*){3,}"),
        ("\u0688", r"\u0688"),
    ]
    for label, pattern in repeated_hindi_patterns:
        if re.search(pattern, joined):
            penalty += 24 if label == "\u0688" else 18
            reasons.append(f"repeated_hindi_phrase={label}")

    ultra_short_repeated_segments = 0
    for fragment in [str(s.get("text", "")) for s in segments if isinstance(s, dict)]:
        frag_tokens = re.findall(r"[\u0900-\u097F\u0688]+", fragment)
        if len(frag_tokens) < 3 or len(frag_tokens) > 8:
            continue
        top_frag = max(frag_tokens.count(w) for w in set(frag_tokens))
        if top_frag >= 3 or (top_frag / max(len(frag_tokens), 1)) >= 0.60:
            ultra_short_repeated_segments += 1
    if ultra_short_repeated_segments:
        penalty += min(32, ultra_short_repeated_segments * 8)
        reasons.append(f"ultra_short_repeated_segments={ultra_short_repeated_segments}")

    helper_words = {
        "and", "then", "that", "this", "will", "would", "can", "could",
        "have", "has", "had", "is", "are", "was", "were", "to", "on",
        "in", "of", "for", "with", "so", "because", "what", "how"
    }
    content_words = [re.sub(r"[^a-z0-9]", "", w) for w in words]
    content_words = [w for w in content_words if w]

    continuation_starts = (
        "and ", "then ", "and then ", "so ", "because ", "that ",
        "which ", "if ", "in the ", "at that time", "one will"
    )
    source_fragments = [text] + [
        str(s.get("text", "")) for s in segments if isinstance(s, dict)
    ]
    continuation_hits = 0
    incomplete_hits = 0
    for fragment in source_fragments:
        frag = re.sub(r"\s+", " ", str(fragment or "").strip().lower())
        if not frag:
            continue
        frag_words = frag.split()
        if any(frag.startswith(p) for p in continuation_starts):
            continuation_hits += 1
        if (
            len(frag_words) <= 7
            and (
                frag.endswith((" is", " are", " was", " were", " will", " would", " to", " in", " on"))
                or frag in {"and what happens is", "what happens is"}
            )
        ):
            incomplete_hits += 1

    if continuation_hits:
        penalty += min(24, continuation_hits * 8)
        reasons.append(f"weak_continuation_fragments={continuation_hits}")

    if incomplete_hits:
        penalty += min(30, incomplete_hits * 15)
        reasons.append(f"incomplete_fragments={incomplete_hits}")

    malformed_structures = [
        r"\b\w+\s+will\s+(?:on|time|very)\b",
        r"\b(?:is|are|was|were)\s+(?:complete|come|go|look|write)\b",
        r"\b(?:did|do|does)\s+(?:write|like|come|go)\s+(?:this|that|story|time)\b",
        r"\b(?:you|we|they|i)\s+(?:one|not)\s+\w+\b",
        r"\b(?:film|book|story|time|one|other)\s+will\s+come\s+on\s+time\b",
        r"\bso\s+much\s+(?:child|children|people|phone|time)\b",
        r"\bcome\s+to\s+come\b",
        r"\bperson\s+comes\s+in\s+a\s+period\b",
        r"\bair\s+port\s+(?:launch|lounge)?\b",
        r"\bwrite\s+(?:mountains|some\s+nights|in\s+some\s+nights)\b",
    ]
    structure_hits = sum(1 for p in malformed_structures if re.search(p, low))
    if structure_hits:
        penalty += min(45, structure_hits * 14)
        reasons.append(f"broken_translation_structures={structure_hits}")

    if len(content_words) >= 8:
        helper_ratio = sum(1 for w in content_words if w in helper_words) / max(len(content_words), 1)
        if helper_ratio >= 0.58:
            penalty += int(helper_ratio * 24)
            reasons.append(f"helper_word_heavy={helper_ratio:.2f}")

        bigrams = list(zip(content_words, content_words[1:]))
        trigrams = list(zip(content_words, content_words[1:], content_words[2:]))
        repeated_phrases = 0
        for grams in (bigrams, trigrams):
            seen = {}
            for gram in grams:
                if all(w in helper_words for w in gram):
                    continue
                seen[gram] = seen.get(gram, 0) + 1
            repeated_phrases += sum(v - 1 for v in seen.values() if v > 1)
        if repeated_phrases:
            penalty += min(30, repeated_phrases * 6)
            reasons.append(f"repeated_helper_phrases={repeated_phrases}")

    noun_chain_patterns = [
        r"\b(?:platform|film|story|time|career|period|podcast|interviews?)\s+"
        r"(?:platform|film|story|time|career|period|podcast|interviews?)\s+"
        r"(?:platform|film|story|time|career|period|podcast|interviews?)\b",
        r"\b(?:dining|jagan|manthan|platform)\s+(?:dining|jagan|manthan|platform)\b",
    ]
    noun_chain_hits = sum(1 for p in noun_chain_patterns if re.search(p, low))
    if noun_chain_hits:
        penalty += min(24, noun_chain_hits * 12)
        reasons.append(f"unnatural_noun_chains={noun_chain_hits}")

    broken_fragments = 0
    for s in segments:
        if not isinstance(s, dict):
            continue
        seg_words = str(s.get("text", "")).split()
        if 1 <= len(seg_words) <= 3:
            broken_fragments += 1

    if segments:
        broken_ratio = broken_fragments / max(len(segments), 1)
        if broken_ratio >= 0.30:
            penalty += int(broken_ratio * 35)
            reasons.append(f"short_broken_fragments={broken_ratio:.2f}")

    if len(words) >= 8:
        top = max(words.count(w) for w in set(words))
        repeat_ratio = top / max(len(words), 1)
        if repeat_ratio > 0.35:
            penalty += int(repeat_ratio * 40)
            reasons.append(f"word_repetition={repeat_ratio:.2f}")

    return max(0, min(100, 100 - penalty)), reasons


def asr_estimated_penalty_for_reason(reason):
    reason = str(reason or "")
    if reason.startswith("malformed_phrases="):
        return int(reason.split("=", 1)[1]) * 18
    if reason.startswith("junk_repetition="):
        return int(reason.split("=", 1)[1]) * 20
    if reason.startswith("replacement_chars="):
        return min(40, int(reason.split("=", 1)[1]) * 10)
    if reason.startswith("devanagari_repeated_token_ratio="):
        return min(45, int(float(reason.split("=", 1)[1]) * 90))
    if reason.startswith("repeated_hindi_phrase="):
        return 24 if reason.endswith("\u0688") else 18
    if reason.startswith("ultra_short_repeated_segments="):
        return min(32, int(reason.split("=", 1)[1]) * 8)
    if reason.startswith("weak_continuation_fragments="):
        return min(24, int(reason.split("=", 1)[1]) * 8)
    if reason.startswith("incomplete_fragments="):
        return min(30, int(reason.split("=", 1)[1]) * 15)
    if reason.startswith("broken_translation_structures="):
        return min(45, int(reason.split("=", 1)[1]) * 14)
    if reason.startswith("helper_word_heavy="):
        return int(float(reason.split("=", 1)[1]) * 24)
    if reason.startswith("repeated_helper_phrases="):
        return min(30, int(reason.split("=", 1)[1]) * 6)
    if reason.startswith("unnatural_noun_chains="):
        return min(24, int(reason.split("=", 1)[1]) * 12)
    if reason.startswith("short_broken_fragments="):
        return int(float(reason.split("=", 1)[1]) * 35)
    if reason.startswith("word_repetition="):
        return int(float(reason.split("=", 1)[1]) * 40)
    return 0


def asr_quality_diagnostic_report(text, segments, quality_score, reasons, label="", job_id=None):
    segments = segments if isinstance(segments, list) else []
    text = str(text or "")
    reasons = [str(r) for r in (reasons or [])]
    joined_segments = " ".join(str(s.get("text", "")) for s in segments if isinstance(s, dict))
    joined = " ".join([text, joined_segments]).strip()
    words = joined.split()
    durations = [
        max(0.0, float(s.get("end", 0) or 0) - float(s.get("start", 0) or 0))
        for s in segments
        if isinstance(s, dict)
    ]
    short_segments = [
        s for s in segments
        if isinstance(s, dict) and 1 <= len(str(s.get("text", "")).split()) <= 3
    ]
    continuation_starts = (
        "and ", "then ", "and then ", "so ", "because ", "that ",
        "which ", "if ", "in the ", "at that time", "one will"
    )
    continuation_count = 0
    for s in segments:
        frag = re.sub(r"\s+", " ", str(s.get("text", "") if isinstance(s, dict) else "").strip().lower())
        if frag and any(frag.startswith(p) for p in continuation_starts):
            continuation_count += 1

    penalty_rows = []
    estimated_total = 0
    for reason in reasons:
        estimated = asr_estimated_penalty_for_reason(reason)
        estimated_total += estimated
        penalty_rows.append({
            "reason": reason,
            "estimated_penalty": estimated,
        })
    penalty_rows.sort(key=lambda r: r["estimated_penalty"], reverse=True)
    denominator = max(1, estimated_total)
    for row in penalty_rows:
        row["estimated_share_pct"] = round((row["estimated_penalty"] / denominator) * 100, 1)

    previews = []
    if segments:
        sample_indexes = sorted(set([
            0,
            min(len(segments) - 1, len(segments) // 4),
            min(len(segments) - 1, len(segments) // 2),
            min(len(segments) - 1, (len(segments) * 3) // 4),
            len(segments) - 1,
        ]))
        for idx in sample_indexes:
            seg = segments[idx]
            previews.append({
                "index": idx,
                "start": round(float(seg.get("start", 0) or 0), 2),
                "end": round(float(seg.get("end", 0) or 0), 2),
                "text": str(seg.get("text", ""))[:260],
            })

    normalization_examples = []
    for idx, seg in enumerate(segments):
        before = str(seg.get("text", "") if isinstance(seg, dict) else "")
        after = clean_repeated_phrases(before)
        if before != after:
            normalization_examples.append({
                "index": idx,
                "before": before[:220],
                "after": after[:220],
            })
        if len(normalization_examples) >= 5:
            break

    report = {
        "label": label,
        "job_id": job_id,
        "quality_score": quality_score,
        "quality_reasons": reasons,
        "score_penalty": max(0, 100 - int(quality_score or 0)),
        "estimated_penalty_total": estimated_total,
        "top_penalties": penalty_rows[:8],
        "segments": len(segments),
        "words": len(words),
        "avg_segment_duration": round(sum(durations) / max(len(durations), 1), 2),
        "short_segment_ratio": round(len(short_segments) / max(len(segments), 1), 3),
        "continuation_start_segments": continuation_count,
        "replacement_chars": joined.count("\ufffd"),
        "normalization_examples": normalization_examples,
        "transcript_previews": previews,
        "version": "v57_1_asr_quality_diagnostics",
    }

    print(
        "ASR_QUALITY_BREAKDOWN "
        f"label={label} score={quality_score} score_penalty={report['score_penalty']} "
        f"estimated_penalty_total={estimated_total} segments={len(segments)} "
        f"words={len(words)} avg_segment_duration={report['avg_segment_duration']} "
        f"short_segment_ratio={report['short_segment_ratio']} "
        f"continuation_start_segments={continuation_count}"
    )
    print(
        "ASR_TOP_PENALTIES "
        f"label={label} penalties={json.dumps(report['top_penalties'], ensure_ascii=False)[:1600]}"
    )
    print(
        "ASR_CHUNK_TRANSCRIPT_PREVIEW "
        f"label={label} previews={json.dumps(previews, ensure_ascii=False)[:1800]}"
    )
    if normalization_examples:
        print(
            "ASR_NORMALIZATION_EXAMPLES "
            f"label={label} examples={json.dumps(normalization_examples, ensure_ascii=False)[:1400]}"
        )

    try:
        safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(label or "asr"))[:80] or "asr"
        safe_job = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(job_id or "unknown"))[:120] or "unknown"
        out_path = Path("audit_reports") / f"asr_quality_breakdown_{safe_job}_{safe_label}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ASR_QUALITY_BREAKDOWN_ARTIFACT path={out_path}")
    except Exception as e:
        print(f"ASR_QUALITY_BREAKDOWN_ARTIFACT_FAILED error={e}")
    return report


def asr_rejected_ratio(raw_segments, cleaned_segments):
    raw_count = len(raw_segments) if isinstance(raw_segments, list) else 0
    kept_count = len(cleaned_segments) if isinstance(cleaned_segments, list) else 0
    if raw_count <= 0:
        return 1.0
    return round(max(0, raw_count - kept_count) / max(raw_count, 1), 4)


def asr_has_severe_repeated_hindi_garbage(reasons, text=""):
    reasons = [str(r) for r in (reasons or [])]
    joined = str(text or "")
    if any(r.startswith("repeated_hindi_phrase=") for r in reasons):
        return True
    severe_patterns = [
        r"(?:आप\s*){6,}",
        r"(?:अगर\s*){6,}",
        r"(?:तो\s*){6,}",
        r"(?:गया\s*){8,}",
        r"(?:वा\s*){8,}",
    ]
    return any(re.search(pattern, joined) for pattern in severe_patterns)


def asr_readability_score(text, segments, raw_segments=None, cleaned_segments=None):
    segments = segments if isinstance(segments, list) else []
    raw_segments = raw_segments if isinstance(raw_segments, list) else segments
    cleaned_segments = cleaned_segments if isinstance(cleaned_segments, list) else segments
    joined = " ".join(
        [str(text or "")]
        + [str(s.get("text", "")) for s in segments if isinstance(s, dict)]
    )
    words = joined.split()
    word_count = len(words)
    replacement_count = joined.count("\ufffd")
    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", joined))
    latin_chars = len(re.findall(r"[A-Za-z]", joined))
    alpha_chars = devanagari_chars + latin_chars
    devanagari_latin_ratio = alpha_chars / max(len(re.sub(r"\s+", "", joined)), 1)
    durations = [
        max(0.0, float(s.get("end", 0) or 0) - float(s.get("start", 0) or 0))
        for s in segments
        if isinstance(s, dict)
    ]
    sane_durations = [d for d in durations if 0.35 <= d <= 18.0]
    duration_sanity = len(sane_durations) / max(len(durations), 1)
    short_segments = [
        s for s in segments
        if isinstance(s, dict) and 1 <= len(str(s.get("text", "")).split()) <= 2
    ]
    short_ratio = len(short_segments) / max(len(segments), 1)
    reject_ratio = asr_rejected_ratio(raw_segments, cleaned_segments)
    replacement_per_1000_words = (replacement_count / max(word_count, 1)) * 1000

    score = 100
    if word_count < 500:
        score -= 25
    elif word_count < 2000:
        score -= 8
    if replacement_per_1000_words > 5:
        score -= min(35, int(replacement_per_1000_words * 4))
    elif replacement_per_1000_words > 1.5:
        score -= 8
    if devanagari_latin_ratio < 0.45:
        score -= 18
    if duration_sanity < 0.80:
        score -= int((0.80 - duration_sanity) * 40)
    if short_ratio > 0.18:
        score -= min(20, int(short_ratio * 70))
    if reject_ratio > 0.08:
        score -= min(30, int(reject_ratio * 200))

    details = {
        "score": max(0, min(100, int(score))),
        "word_count": word_count,
        "replacement_chars": replacement_count,
        "replacement_per_1000_words": round(replacement_per_1000_words, 3),
        "devanagari_chars": devanagari_chars,
        "latin_chars": latin_chars,
        "devanagari_latin_ratio": round(devanagari_latin_ratio, 3),
        "duration_sanity": round(duration_sanity, 3),
        "short_segment_ratio": round(short_ratio, 3),
        "rejected_ratio": reject_ratio,
        "segments": len(segments),
    }
    print(
        "ASR_READABILITY_SCORE "
        f"score={details['score']} words={word_count} replacement_chars={replacement_count} "
        f"replacement_per_1000_words={details['replacement_per_1000_words']} "
        f"devanagari_latin_ratio={details['devanagari_latin_ratio']} "
        f"duration_sanity={details['duration_sanity']} "
        f"short_segment_ratio={details['short_segment_ratio']} "
        f"rejected_ratio={reject_ratio}"
    )
    return details["score"], details


def calibrate_chunked_faster_whisper_quality(raw_quality, raw_reasons, text, raw_segments, cleaned_segments):
    raw_reasons = [str(r) for r in (raw_reasons or [])]
    readability_score, readability = asr_readability_score(
        text,
        cleaned_segments,
        raw_segments=raw_segments,
        cleaned_segments=cleaned_segments,
    )
    word_count = readability["word_count"]
    severe_repeated_hindi = asr_has_severe_repeated_hindi_garbage(raw_reasons, text)
    calibrated_penalty = 0
    calibrated_reasons = []

    for reason in raw_reasons:
        if reason.startswith("repeated_helper_phrases="):
            count = int(reason.split("=", 1)[1])
            penalty = min(8, max(0, count // 80))
            if penalty:
                calibrated_penalty += penalty
                calibrated_reasons.append(f"repeated_helper_phrases_calibrated={count}:penalty={penalty}")
            else:
                calibrated_reasons.append(f"repeated_helper_phrases_ignored_for_long_hindi={count}")
            continue
        if reason.startswith("helper_word_heavy="):
            penalty = min(6, asr_estimated_penalty_for_reason(reason))
            calibrated_penalty += penalty
            calibrated_reasons.append(f"helper_word_heavy_calibrated={reason.split('=', 1)[1]}:penalty={penalty}")
            continue
        if reason.startswith("replacement_chars="):
            count = int(reason.split("=", 1)[1])
            if word_count > 5000:
                penalty = min(18, max(4, count))
            else:
                penalty = min(40, count * 10)
            calibrated_penalty += penalty
            calibrated_reasons.append(f"replacement_chars_calibrated={count}:penalty={penalty}")
            continue
        penalty = asr_estimated_penalty_for_reason(reason)
        calibrated_penalty += penalty
        calibrated_reasons.append(f"{reason}:penalty={penalty}")

    readability_bonus = 0
    if readability_score >= 85 and word_count > 3000:
        readability_bonus = 8
    elif readability_score >= 75:
        readability_bonus = 4

    calibrated_quality = max(0, min(100, 100 - calibrated_penalty + readability_bonus))
    low_rejected_ratio = readability["rejected_ratio"] <= 0.05
    result = {
        "raw_quality": raw_quality,
        "raw_reasons": raw_reasons,
        "calibrated_quality": calibrated_quality,
        "calibrated_penalty": calibrated_penalty,
        "calibrated_reasons": calibrated_reasons,
        "readability_score": readability_score,
        "readability": readability,
        "readability_bonus": readability_bonus,
        "severe_repeated_hindi_garbage": severe_repeated_hindi,
        "rejected_ratio_low": low_rejected_ratio,
        "version": "v58_chunked_fw_hindi_calibration",
    }
    print(
        "ASR_SCORER_CALIBRATION "
        f"mode=faster_whisper_medium_retry_chunked raw_quality={raw_quality} "
        f"calibrated_quality={calibrated_quality} calibrated_penalty={calibrated_penalty} "
        f"readability_score={readability_score} rejected_ratio={readability['rejected_ratio']} "
        f"severe_repeated_hindi_garbage={severe_repeated_hindi} "
        f"reasons={calibrated_reasons}"
    )
    return result


def asr_has_severe_quality_reasons(reasons):
    return any(
        str(reason).startswith(ASR_SEVERE_REASON_PREFIXES)
        for reason in (reasons or [])
    )


def asr_is_low_confidence_quality(quality_score, reasons):
    return int(quality_score or 0) < 70 or asr_has_severe_quality_reasons(reasons)


def asr_quality_artifact_counts(reasons):
    counts = {
        "replacement_chars": 0,
        "repeated_hindi_phrase": 0,
    }
    for reason in reasons or []:
        reason = str(reason)
        if reason.startswith("replacement_chars="):
            try:
                counts["replacement_chars"] += int(reason.split("=", 1)[1])
            except ValueError:
                counts["replacement_chars"] += 1
        elif reason.startswith("repeated_hindi_phrase="):
            counts["repeated_hindi_phrase"] += 1
    return counts


def asr_should_fail_closed(quality_score, reasons, low_confidence=False):
    reasons = [str(r) for r in (reasons or [])]
    score = int(quality_score or 0)
    artifacts = asr_quality_artifact_counts(reasons)
    severe_garbage = (
        artifacts["replacement_chars"] > 0
        or artifacts["repeated_hindi_phrase"] > 0
        or any(r.startswith("devanagari_repeated_token_ratio=") for r in reasons)
        or any(r.startswith("ultra_short_repeated_segments=") for r in reasons)
    )
    if score <= 10:
        return True, "asr_quality_score_too_low"
    if bool(low_confidence) and severe_garbage:
        return True, "low_confidence_with_hindi_garbage_or_replacement_chars"
    return False, ""


def asr_kept_segments_reasonable(native_count, candidate_count):
    if candidate_count <= 0:
        return False
    if native_count <= 0:
        return candidate_count >= 3
    return candidate_count >= max(3, int(native_count * 0.5))


def should_run_full_medium_retry_candidate(
    native_quality,
    native_reasons,
    native_kept_segments,
    sample_quality,
    sample_kept_segments,
    sample_reasons=None,
):
    if not sample_kept_segments:
        return False, "medium_sample_not_good_enough"

    sample_reasons = [str(r) for r in (sample_reasons or [])]

    strong_sample = (
        sample_quality > native_quality + 15
        and sample_quality >= 55
    )
    if strong_sample:
        return True, "medium_sample_good_enough"

    sample_artifacts = asr_quality_artifact_counts(sample_reasons)
    sample_has_severe_garbage = (
        sample_artifacts["replacement_chars"] > 0
        or sample_artifacts["repeated_hindi_phrase"] > 0
    )
    if (
        sample_quality >= 50
        and sample_kept_segments >= 20
        and not sample_has_severe_garbage
    ):
        return True, "borderline_clean_sample_allow_chunked"

    native_low_confidence = asr_is_low_confidence_quality(native_quality, native_reasons)
    borderline_sample = (
        ASR_BORDERLINE_MEDIUM_SAMPLE_MIN
        <= sample_quality
        <= ASR_BORDERLINE_MEDIUM_SAMPLE_MAX
    )
    if (
        native_low_confidence
        and borderline_sample
        and asr_kept_segments_reasonable(native_kept_segments, sample_kept_segments)
    ):
        return True, "borderline_sample_native_low_confidence"

    return False, "medium_sample_not_good_enough"


def should_select_full_medium_retry(
    native_quality,
    native_reasons,
    native_kept_segments,
    medium_quality,
    medium_reasons,
    medium_kept_segments,
):
    if not medium_kept_segments:
        return False, "full_medium_no_segments"
    if medium_quality <= native_quality:
        return False, "full_medium_not_better_than_native"
    if medium_quality <= 50:
        return False, "full_medium_quality_not_above_50"
    if medium_quality < 65:
        return False, "full_medium_quality_below_65"
    if asr_is_low_confidence_quality(medium_quality, medium_reasons):
        return False, "full_medium_low_confidence"
    if not asr_kept_segments_reasonable(native_kept_segments, medium_kept_segments):
        return False, "full_medium_segments_unreasonable"

    native_artifacts = asr_quality_artifact_counts(native_reasons)
    medium_artifacts = asr_quality_artifact_counts(medium_reasons)
    if medium_artifacts["replacement_chars"] > native_artifacts["replacement_chars"]:
        return False, "full_medium_replacement_chars_worse"
    if medium_artifacts["repeated_hindi_phrase"] > native_artifacts["repeated_hindi_phrase"]:
        return False, "full_medium_repeated_phrase_worse"

    return True, "full_medium_good_enough"


def should_select_chunked_medium_retry(
    native_quality,
    native_reasons,
    native_kept_segments,
    calibrated,
    medium_kept_segments,
):
    calibrated_quality = int((calibrated or {}).get("calibrated_quality") or 0)
    readability = (calibrated or {}).get("readability") or {}
    if not medium_kept_segments:
        return False, "chunked_medium_no_segments"
    if calibrated_quality <= native_quality:
        return False, "chunked_medium_not_better_than_native"
    if calibrated_quality < 65:
        return False, "chunked_medium_calibrated_quality_below_65"
    if bool((calibrated or {}).get("severe_repeated_hindi_garbage")):
        return False, "chunked_medium_severe_repeated_hindi_garbage"
    if not bool((calibrated or {}).get("rejected_ratio_low")):
        return False, "chunked_medium_rejected_ratio_high"
    if int((calibrated or {}).get("readability_score") or 0) < 65:
        return False, "chunked_medium_readability_below_65"
    if not asr_kept_segments_reasonable(native_kept_segments, medium_kept_segments):
        return False, "chunked_medium_segments_unreasonable"
    if float(readability.get("duration_sanity", 0) or 0) < 0.75:
        return False, "chunked_medium_duration_sanity_low"

    native_artifacts = asr_quality_artifact_counts(native_reasons)
    replacement_chars = int((readability or {}).get("replacement_chars") or 0)
    if replacement_chars > max(25, native_artifacts["replacement_chars"]):
        return False, "chunked_medium_replacement_chars_too_high"

    return True, "chunked_medium_calibrated_good_enough"


def should_keep_segment(text: str) -> bool:
    text = clean_repeated_phrases(text)

    if not text:
        return False

    if v27_bad_asr_reason(text):
        return False

    words = text.split()

    if len(words) < 2:
        if has_devanagari(text) and len(text.strip()) >= 4:
            return True
        return False

    junk_words = ["thank you", "bye", "hmm", "uh", "um", "ॐ", "ओम"]
    lower = text.lower().strip()

    if lower in junk_words:
        return False

    return True


def clean_asr_segments(raw_segments, label="asr"):
    cleaned_segments = []
    rejected = []

    for s in raw_segments:
        text = clean_repeated_phrases(s.get("text", ""))

        if not should_keep_segment(text):
            reason = v27_bad_asr_reason(text)
            if not reason:
                if not text:
                    reason = "empty_text"
                elif len(text.split()) < 2:
                    reason = "too_short_non_devanagari"
                else:
                    reason = "unknown_reject"
            rejected.append((reason, text[:120]))
            continue

        start = float(s.get("start", 0))
        end = float(s.get("end", start))
        words = s.get("words", [])
        if not isinstance(words, list):
            words = []

        if end <= start:
            continue

        cleaned_segments.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "text": text,
            "words": words
        })

    print(
        f"ASR_SEGMENT_CLEANUP mode={label} "
        f"raw={len(raw_segments)} kept={len(cleaned_segments)} rejected={len(rejected)}"
    )
    for reason, preview in rejected[:10]:
        print(f"ASR_REJECT_SAMPLE mode={label} reason={reason} text={preview}")

    return cleaned_segments


def create_asr_retry_sample(asr_input: str, seconds: int = 600) -> str:
    base, _ = os.path.splitext(asr_input)
    sample_path = f"{base}_asr_retry_sample_{seconds}s.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        asr_input,
        "-t",
        str(seconds),
        sample_path,
    ]
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    if not os.path.exists(sample_path) or os.path.getsize(sample_path) <= 1000:
        raise RuntimeError(f"ASR retry sample invalid: {sample_path}")
    return sample_path


def get_audio_duration_seconds(audio_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    return max(0.0, float(str(result.stdout or "0").strip() or 0))


def v49_9_repaired_window_artifact_path(job_id, start, end):
    safe_job_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(job_id or "unknown"))[:160] or "unknown"
    start_token = int(round(float(start or 0) * 100))
    end_token = int(round(float(end or 0) * 100))
    return Path("audit_reports") / f"asr_repaired_window_{safe_job_id}_{start_token}_{end_token}.json"


def load_v49_9_repaired_window_artifact(job_id, start, end):
    path = v49_9_repaired_window_artifact_path(job_id, start, end)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        print(f"V49_9_REPAIRED_WINDOW_ARTIFACT_READ_FAILED path={path} error={e}")
        return {}
    if str(payload.get("job_id")) != str(job_id):
        return {}
    payload_start = round(float(payload.get("start", 0) or 0), 2)
    payload_end = round(float(payload.get("end", payload_start) or payload_start), 2)
    if payload_start != round(float(start or 0), 2) or payload_end != round(float(end or 0), 2):
        return {}
    payload["artifact_path"] = str(path)
    return payload


def write_v49_9_repaired_window_artifact(payload):
    payload = payload if isinstance(payload, dict) else {}
    path = v49_9_repaired_window_artifact_path(
        payload.get("job_id"),
        payload.get("start"),
        payload.get("end"),
    )
    out = dict(payload)
    out["artifact_path"] = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def extract_asr_window(file_path: str, start_seconds: float, end_seconds: float, suffix: str = "window") -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"ASR source file not found: {file_path}")
    start_seconds = max(0.0, float(start_seconds or 0))
    end_seconds = max(start_seconds + 0.25, float(end_seconds or start_seconds))
    duration = max(0.25, end_seconds - start_seconds)
    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_{suffix}_{int(round(start_seconds * 1000))}_{int(round(end_seconds * 1000))}.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_seconds:.2f}",
        "-i",
        file_path,
        "-t",
        f"{duration:.2f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        out_path,
    ]
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    if not os.path.exists(out_path) or os.path.getsize(out_path) <= 1000:
        raise RuntimeError(f"ASR window extraction invalid: {out_path}")
    return out_path


def transcribe_exact_asr_window(file_path: str, start_seconds: float, end_seconds: float, device: str = None, keep_audio: bool = False):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"ASR source file not found: {file_path}")

    window_audio_path = extract_asr_window(
        file_path,
        start_seconds,
        end_seconds,
        suffix="asr_repair_window",
    )
    probe_device = device or get_device()
    duration = max(0.25, float(end_seconds or 0) - float(start_seconds or 0))
    timeout_seconds = max(
        120,
        min(V49_9_WINDOW_REPAIR_MAX_TIMEOUT_SECONDS, int(round(duration * 12))),
    )
    try:
        raw_segments, _ = transcribe_faster_whisper_retry_guarded(
            window_audio_path,
            probe_device,
            phase="window_repair",
            timeout_seconds=timeout_seconds,
        )
        cleaned_segments = clean_asr_segments(raw_segments, label="faster_whisper_window_repair")
        repaired_text = clean_repeated_phrases(" ".join(str(s.get("text", "")) for s in cleaned_segments))
        quality_score, quality_reasons = transcript_quality_score(repaired_text, cleaned_segments)
        return {
            "window_audio_path": window_audio_path,
            "duration": round(duration, 2),
            "timeout_seconds": timeout_seconds,
            "device": probe_device,
            "raw_segments": len(raw_segments),
            "cleaned_segments": cleaned_segments,
            "repaired_text": repaired_text,
            "transcript_quality_score": quality_score,
            "transcript_quality_reasons": quality_reasons,
            "low_confidence_asr": asr_is_low_confidence_quality(quality_score, quality_reasons),
        }
    finally:
        if not keep_audio:
            try:
                if os.path.exists(window_audio_path):
                    os.remove(window_audio_path)
            except Exception:
                pass


def transcribe_medium_retry(model, audio_path: str, device: str):
    return model.transcribe(
        audio_path,
        task="transcribe",
        language="hi",
        fp16=(device == "cuda"),
        verbose=False,
        temperature=0,
        beam_size=1,
        best_of=1,
        condition_on_previous_text=False,
        word_timestamps=False,
        compression_ratio_threshold=2.4,
        logprob_threshold=-1.0,
        no_speech_threshold=0.55,
        initial_prompt=(
            "à¤¯à¤¹ à¤¹à¤¿à¤‚à¤¦à¥€ à¤”à¤° Hinglish speech à¤¹à¥ˆ. à¤¹à¤¿à¤‚à¤¦à¥€ à¤¶à¤¬à¥à¤¦à¥‹à¤‚ à¤•à¥‹ à¤¦à¥‡à¤µà¤¨à¤¾à¤—à¤°à¥€ à¤®à¥‡à¤‚ à¤¸à¤¹à¥€ à¤²à¤¿à¤–à¥‹. "
            "English words à¤•à¥‹ English à¤®à¥‡à¤‚ à¤°à¤–à¥‹."
        )
    )


def get_faster_whisper_retry_model(device: str):
    from faster_whisper import WhisperModel

    fw_device = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
    compute_type = "int8_float16" if fw_device == "cuda" else "int8"
    return WhisperModel("medium", device=fw_device, compute_type=compute_type), compute_type


def transcribe_faster_whisper_retry(model, audio_path: str):
    segments_iter, _ = model.transcribe(
        audio_path,
        language="hi",
        task="transcribe",
        beam_size=1,
        vad_filter=False,
    )
    raw_segments = []
    for seg in segments_iter:
        raw_segments.append({
            "start": float(getattr(seg, "start", 0) or 0),
            "end": float(getattr(seg, "end", 0) or 0),
            "text": getattr(seg, "text", "") or "",
        })
    return raw_segments, clean_repeated_phrases(" ".join(s["text"] for s in raw_segments))


def transcribe_faster_whisper_retry_guarded(audio_path: str, device: str, phase: str, timeout_seconds: int):
    out_path = os.path.abspath(
        f"{os.path.splitext(audio_path)[0]}_fw_retry_{phase}_{os.getpid()}_{int(time.time())}.json"
    )
    stdout_path = os.path.abspath(
        f"{os.path.splitext(audio_path)[0]}_fw_retry_{phase}_{os.getpid()}_{int(time.time())}.stdout.log"
    )
    stderr_path = os.path.abspath(
        f"{os.path.splitext(audio_path)[0]}_fw_retry_{phase}_{os.getpid()}_{int(time.time())}.stderr.log"
    )
    child_code = r'''
import json
import os
import sys
import traceback
import time

audio_path = sys.argv[1]
out_path = sys.argv[2]
device = sys.argv[3]

print(f"FW_CHILD_START audio_path={audio_path} out_path={out_path} requested_device={device}", flush=True)

def write_payload(segments, complete=False):
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({
            "segments": segments,
            "compute_type": compute_type,
            "device": fw_device,
            "complete": bool(complete),
            "updated_at": time.time(),
        }, f, ensure_ascii=False)
    os.replace(tmp_path, out_path)

try:
    from faster_whisper import WhisperModel
    import torch

    fw_device = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
    compute_type = "int8_float16" if fw_device == "cuda" else "int8"
    print(f"FW_CHILD_DEVICE fw_device={fw_device} compute_type={compute_type}", flush=True)

    model = WhisperModel("medium", device=fw_device, compute_type=compute_type)
    segments_iter, _ = model.transcribe(
        audio_path,
        language="hi",
        task="transcribe",
        beam_size=1,
        vad_filter=False,
    )

    segments = []
    for seg in segments_iter:
        segments.append({
            "start": float(getattr(seg, "start", 0) or 0),
            "end": float(getattr(seg, "end", 0) or 0),
            "text": getattr(seg, "text", "") or "",
        })
        if len(segments) == 1 or len(segments) % 10 == 0:
            write_payload(segments, complete=False)

    write_payload(segments, complete=True)
    print(f"FW_CHILD_DONE segments={len(segments)}", flush=True)
except Exception:
    traceback.print_exc()
    sys.exit(2)
'''
    phase_label = str(phase or "unknown").upper()
    if phase_label == "FULL":
        log_prefix = "ASR_FW_RETRY_FULL"
    elif phase_label == "SAMPLE":
        log_prefix = "ASR_FW_RETRY_SAMPLE"
    else:
        log_prefix = f"ASR_FW_RETRY_{phase_label}"
    stall_seconds = (
        ASR_FW_RETRY_FULL_STALL_SECONDS
        if phase_label == "FULL"
        else ASR_FW_RETRY_STALL_SECONDS
    )
    watchdog_events_path = Path("audit_reports") / f"asr_fw_retry_watchdog_{str(phase or 'unknown')}_{int(time.time())}.jsonl"

    def watchdog_log(event, **fields):
        row = {
            "ts": time.time(),
            "event": event,
            "phase": phase,
            "audio_path": audio_path,
            **fields,
        }
        try:
            Path("audit_reports").mkdir(parents=True, exist_ok=True)
            with watchdog_events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"{log_prefix}_WATCHDOG_LOG_FAILED error={e}", flush=True)
        details = " ".join(f"{k}={v}" for k, v in fields.items())
        print(f"{event} {details}".rstrip(), flush=True)

    def read_tail(path, limit=4000):
        try:
            if not os.path.exists(path):
                return ""
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
            return text[-limit:]
        except Exception as e:
            return f"<tail_read_failed {e}>"

    def read_output_payload(require_complete=False):
        if not os.path.exists(out_path):
            return None
        payload = json.loads(Path(out_path).read_text(encoding="utf-8"))
        raw_segments = payload.get("segments", [])
        if not isinstance(raw_segments, list):
            raw_segments = []
        if require_complete and not bool(payload.get("complete")):
            return None
        return payload, raw_segments

    def write_child_log(result=None, error=None):
        try:
            Path("audit_reports").mkdir(parents=True, exist_ok=True)
            safe_phase = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(phase or "unknown"))[:80]
            log_path = Path("audit_reports") / f"asr_fw_retry_child_{safe_phase}_{int(time.time())}.json"
            payload = {
                "phase": phase,
                "audio_path": audio_path,
                "out_path": out_path,
                "stdout_path": stdout_path,
                "stderr_path": stderr_path,
                "watchdog_events_path": str(watchdog_events_path),
                "timeout_seconds": timeout_seconds,
                "stall_seconds": stall_seconds,
                "returncode": getattr(result, "returncode", None) if result is not None else None,
                "stdout_tail": read_tail(stdout_path),
                "stderr_tail": read_tail(stderr_path),
                "error": str(error or ""),
                "version": "v56_1_fw_child_watchdog",
            }
            log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"ASR_FW_RETRY_CHILD_LOG path={log_path}")
        except Exception as log_error:
            print(f"ASR_FW_RETRY_CHILD_LOG_FAILED error={log_error}")

    def terminate_child(proc, reason):
        if proc.poll() is not None:
            return
        try:
            watchdog_log(f"{log_prefix}_TERMINATE", pid=proc.pid, reason=reason)
            proc.terminate()
            proc.wait(timeout=10)
            return
        except Exception:
            pass
        try:
            watchdog_log(f"{log_prefix}_KILL", pid=proc.pid, reason=reason)
            proc.kill()
            proc.wait(timeout=10)
        except Exception as e:
            watchdog_log(f"{log_prefix}_KILL_FAILED", pid=getattr(proc, "pid", None), error=e)
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=20,
                )
                watchdog_log(f"{log_prefix}_TASKKILL", pid=proc.pid, reason=reason)
            except Exception as e:
                watchdog_log(f"{log_prefix}_TASKKILL_FAILED", pid=getattr(proc, "pid", None), error=e)

    try:
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        with open(stdout_path, "w", encoding="utf-8", errors="ignore") as stdout_f, open(
            stderr_path, "w", encoding="utf-8", errors="ignore"
        ) as stderr_f:
            proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-c", child_code, audio_path, out_path, device],
                stdout=stdout_f,
                stderr=stderr_f,
                text=True,
                env=env,
            )

            watchdog_log(f"{log_prefix}_CHILD_PID", pid=proc.pid, timeout_seconds=timeout_seconds, stall_seconds=stall_seconds)
            start_wait = time.time()
            last_heartbeat = start_wait
            last_output_change = start_wait
            last_output_size = -1

            while True:
                now = time.time()
                elapsed = round(now - start_wait, 1)
                returncode = proc.poll()
                if os.path.exists(out_path):
                    current_size = os.path.getsize(out_path)
                    if current_size != last_output_size:
                        last_output_size = current_size
                        last_output_change = now
                    try:
                        complete_payload = read_output_payload(require_complete=True)
                        if complete_payload:
                            payload, raw_segments = complete_payload
                            watchdog_log(
                                f"{log_prefix}_RESULT",
                                elapsed=elapsed,
                                segments=len(raw_segments),
                                source="complete_json",
                            )
                            terminate_child(proc, "complete_output_accepted")
                            return raw_segments, clean_repeated_phrases(
                                " ".join(str(s.get("text", "")) for s in raw_segments)
                            )
                    except Exception:
                        pass

                if returncode is not None:
                    break

                if now - last_heartbeat >= ASR_FW_RETRY_HEARTBEAT_SECONDS:
                    watchdog_log(
                        f"{log_prefix}_HEARTBEAT",
                        pid=proc.pid,
                        elapsed=elapsed,
                        timeout_seconds=timeout_seconds,
                        output_exists=os.path.exists(out_path),
                        output_bytes=max(last_output_size, 0),
                        seconds_since_output_change=round(now - last_output_change, 1),
                    )
                    last_heartbeat = now

                if elapsed >= timeout_seconds:
                    terminate_child(proc, "timeout")
                    watchdog_log(f"{log_prefix}_TIMEOUT", pid=proc.pid, elapsed=elapsed, seconds=timeout_seconds)
                    write_child_log(result=proc, error=f"timeout after {elapsed}s")
                    try:
                        partial_payload = read_output_payload(require_complete=False)
                        if partial_payload:
                            _, partial_segments = partial_payload
                            watchdog_log(
                                f"{log_prefix}_PARTIAL_OUTPUT_REJECTED",
                                segments=len(partial_segments),
                                reason="timeout",
                            )
                    except Exception:
                        pass
                    raise TimeoutError(f"faster_whisper_{phase}_timeout")

                if (
                    os.path.exists(out_path)
                    and now - last_output_change >= stall_seconds
                ):
                    terminate_child(proc, "output_stall")
                    watchdog_log(
                        f"{log_prefix}_TIMEOUT",
                        pid=proc.pid,
                        elapsed=elapsed,
                        reason="output_stall",
                        seconds_since_output_change=round(now - last_output_change, 1),
                        stall_seconds=stall_seconds,
                    )
                    write_child_log(result=proc, error=f"output stall after {elapsed}s")
                    raise TimeoutError(f"faster_whisper_{phase}_output_stall")

                time.sleep(2)

            write_child_log(result=proc)

        if proc.returncode != 0:
            if os.path.exists(out_path):
                print(
                    "ASR_FW_RETRY_CHILD_NONZERO_WITH_OUTPUT "
                    f"phase={phase} returncode={proc.returncode}"
                    ,
                    flush=True,
                )
            else:
                detail = (read_tail(stderr_path) or read_tail(stdout_path) or "faster_whisper_child_failed")[-2000:]
                raise RuntimeError(f"faster_whisper_child_failed phase={phase} returncode={proc.returncode} detail={detail}")
        if not os.path.exists(out_path):
            write_child_log(result=proc, error="faster_whisper_child_no_output")
            raise RuntimeError(f"faster_whisper_child_no_output phase={phase}")
        payload, raw_segments = read_output_payload(require_complete=False)
        watchdog_log(
            f"{log_prefix}_RESULT",
            elapsed=round(time.time() - start_wait, 1),
            segments=len(raw_segments),
            source="process_exit",
        )
        return raw_segments, clean_repeated_phrases(" ".join(str(s.get("text", "")) for s in raw_segments))
    finally:
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except Exception:
            pass
        for log_path in (stdout_path, stderr_path):
            try:
                if os.path.exists(log_path):
                    os.remove(log_path)
            except Exception:
                pass


def transcribe_faster_whisper_retry_chunked(audio_path: str, device: str):
    duration = get_audio_duration_seconds(audio_path)
    if duration <= 0:
        raise RuntimeError(f"ASR chunked retry invalid duration: {audio_path}")

    chunk_seconds = ASR_FW_RETRY_CHUNK_SECONDS
    chunks = []
    start = 0.0
    while start < duration:
        end = min(duration, start + chunk_seconds)
        chunks.append((round(start, 2), round(end, 2)))
        start = end

    raw_segments = []
    failed_chunks = []
    print(
        "ASR_FW_RETRY_FULL_CHUNKED_START "
        f"duration={round(duration, 2)} chunk_seconds={chunk_seconds} "
        f"chunks={len(chunks)} timeout_per_chunk={ASR_FW_RETRY_CHUNK_TIMEOUT_SECONDS}"
    )

    for idx, (chunk_start, chunk_end) in enumerate(chunks):
        chunk_path = None
        phase = f"full_chunk_{idx:03d}"
        try:
            print(
                "ASR_FW_RETRY_FULL_CHUNK_START "
                f"index={idx} start={chunk_start} end={chunk_end}"
            )
            chunk_path = extract_asr_window(
                audio_path,
                chunk_start,
                chunk_end,
                suffix=f"fw_retry_full_chunk_{idx:03d}",
            )
            chunk_raw_segments, _ = transcribe_faster_whisper_retry_guarded(
                chunk_path,
                device,
                phase,
                ASR_FW_RETRY_CHUNK_TIMEOUT_SECONDS,
            )
            offset_segments = []
            for seg in chunk_raw_segments:
                if not isinstance(seg, dict):
                    continue
                offset_seg = dict(seg)
                offset_seg["start"] = round(float(offset_seg.get("start", 0) or 0) + chunk_start, 2)
                offset_seg["end"] = round(float(offset_seg.get("end", 0) or 0) + chunk_start, 2)
                offset_segments.append(offset_seg)
            raw_segments.extend(offset_segments)
            print(
                "ASR_FW_RETRY_FULL_CHUNK_RESULT "
                f"index={idx} raw_segments={len(chunk_raw_segments)} "
                f"merged_segments={len(raw_segments)}"
            )
        except Exception as e:
            failed_chunks.append({
                "index": idx,
                "start": chunk_start,
                "end": chunk_end,
                "error": str(e),
            })
            print(
                "ASR_FW_RETRY_FULL_CHUNK_FAILED "
                f"index={idx} start={chunk_start} end={chunk_end} error={e}"
            )
        finally:
            if chunk_path:
                try:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
                except Exception:
                    pass

        failed_ratio = len(failed_chunks) / max(len(chunks), 1)
        if failed_ratio > ASR_FW_RETRY_MAX_FAILED_CHUNK_RATIO:
            raise TimeoutError(
                "faster_whisper_full_chunked_too_many_failed_chunks "
                f"failed={len(failed_chunks)} chunks={len(chunks)}"
            )

    merged_text = clean_repeated_phrases(" ".join(str(s.get("text", "")) for s in raw_segments))
    print(
        "ASR_FW_RETRY_FULL_CHUNKED_DONE "
        f"chunks={len(chunks)} failed_chunks={len(failed_chunks)} raw_segments={len(raw_segments)}"
    )
    return raw_segments, merged_text, {
        "duration": round(duration, 2),
        "chunks": len(chunks),
        "failed_chunks": failed_chunks,
        "failed_chunk_ratio": round(len(failed_chunks) / max(len(chunks), 1), 3),
    }


def write_native_pre_retry_asr_artifact(job_id, file_path, asr_mode, quality_score, quality_reasons, cleaned_segments):
    try:
        safe_job_id = str(job_id or "").strip()
        if not safe_job_id:
            safe_job_id = Path(str(file_path or "unknown")).stem
        safe_job_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", safe_job_id)[:160] or "unknown"

        low_confidence_asr = asr_is_low_confidence_quality(quality_score, quality_reasons)
        out_segments = []
        for seg in cleaned_segments if isinstance(cleaned_segments, list) else []:
            if not isinstance(seg, dict):
                continue
            text = str(seg.get("text", "") or "").strip()
            if not text:
                continue
            out_segments.append({
                "start": float(seg.get("start", 0) or 0),
                "end": float(seg.get("end", 0) or 0),
                "text": text,
                "asr_quality_score": quality_score,
                "low_confidence_asr": low_confidence_asr,
            })

        payload = {
            "job_id": safe_job_id,
            "asr_mode": asr_mode,
            "asr_quality_score": quality_score,
            "low_confidence_asr": low_confidence_asr,
            "transcript_quality_reasons": quality_reasons or [],
            "segments": out_segments,
            "version": "v48_native_pre_retry",
        }
        out_path = Path("audit_reports") / f"asr_segments_{safe_job_id}_native_pre_retry.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"V48_NATIVE_PRE_RETRY_ASR_ARTIFACT_WRITTEN path={out_path} segments={len(out_segments)}")
    except Exception as e:
        print(f"V48_NATIVE_PRE_RETRY_ASR_ARTIFACT_FAILED error={e}")


def faster_whisper_research_config(
    language="hi",
    beam_size=5,
    vad_filter=True,
    compute_type=None,
    sample_duration=120,
):
    return {
        "language": language,
        "beam_size": int(beam_size),
        "vad_filter": bool(vad_filter),
        "compute_type": compute_type,
        "sample_duration": int(sample_duration),
    }


def run_faster_whisper_research_probe(audio_path: str, config=None, model_name="medium", device=None):
    """
    Research-only helper for controlled sample probes.
    This is intentionally not called from transcribe() or production retry flow.
    """
    from faster_whisper import WhisperModel

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"ASR research audio not found: {audio_path}")

    cfg = faster_whisper_research_config(**(config or {}))
    probe_device = device or get_device()
    fw_device = "cuda" if probe_device == "cuda" and torch.cuda.is_available() else "cpu"
    compute_type = cfg["compute_type"] or ("int8_float16" if fw_device == "cuda" else "int8")

    sample_path = audio_path
    if cfg["sample_duration"] > 0:
        sample_path = create_asr_retry_sample(audio_path, seconds=cfg["sample_duration"])

    print(
        "FW_RESEARCH_START "
        f"language={cfg['language']} "
        f"beam_size={cfg['beam_size']} "
        f"vad_filter={cfg['vad_filter']} "
        f"compute_type={compute_type} "
        f"sample_duration={cfg['sample_duration']}"
    )

    start_time = time.time()
    model = WhisperModel(model_name, device=fw_device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        sample_path,
        language=cfg["language"],
        task="transcribe",
        beam_size=cfg["beam_size"],
        vad_filter=cfg["vad_filter"],
    )

    raw_segments = []
    for seg in segments_iter:
        raw_segments.append({
            "start": float(getattr(seg, "start", 0) or 0),
            "end": float(getattr(seg, "end", 0) or 0),
            "text": getattr(seg, "text", "") or "",
        })

    text = clean_repeated_phrases(" ".join(s["text"] for s in raw_segments))
    cleaned_segments = clean_asr_segments(raw_segments, label="fw_research_probe")
    quality_score, quality_reasons = transcript_quality_score(text, cleaned_segments)
    elapsed_time = round(time.time() - start_time, 2)

    result = {
        "language": cfg["language"],
        "beam_size": cfg["beam_size"],
        "vad_filter": cfg["vad_filter"],
        "compute_type": compute_type,
        "sample_duration": cfg["sample_duration"],
        "detected_language": getattr(info, "language", None),
        "elapsed_time": elapsed_time,
        "raw_segments": len(raw_segments),
        "kept_segments": len(cleaned_segments),
        "transcript_quality_score": quality_score,
        "quality_reasons": quality_reasons,
        "preview_text": text[:500],
    }

    print(
        "FW_RESEARCH_RESULT "
        f"detected_language={result['detected_language']} "
        f"elapsed_time={result['elapsed_time']} "
        f"raw_segments={result['raw_segments']} "
        f"kept_segments={result['kept_segments']} "
        f"transcript_quality_score={result['transcript_quality_score']} "
        f"quality_reasons={result['quality_reasons']}"
    )
    print(f"FW_RESEARCH_PREVIEW {result['preview_text']}")

    return result


def transcribe(file_path: str, job_id=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    model = get_model()
    device = get_device()

    print("🔥 ASR MODE: V18 creator transcribe optimized")

    print(f"🔥 V18.4 ASR START: {file_path}")
    start_time = time.time()
    asr_mode = "native_transcribe"
    asr_input = extract_asr_wav(file_path)
    print(f"ASR_INPUT_PATH path={asr_input}")

    use_alarm = (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    )
    old_handler = None

    # 15 min hard timeout prevents infinite CPU ASR hangs.
    # Python signal only works in main thread, so disable it inside FastAPI background jobs.
    if use_alarm:
        old_handler = signal.signal(signal.SIGALRM, _v18_timeout_handler)
        signal.alarm(900)

    try:
        result = model.transcribe(
            asr_input,
            task="transcribe",
            language="hi",
            fp16=(device == "cuda"),
            verbose=False,
            word_timestamps=False,

            # CPU-safe decode settings. Keep transcription in the spoken language;
            # avoid domain-heavy prompting that can bias Hindi/Hinglish into repairs.
            temperature=0,
            beam_size=1,
            best_of=1,

            condition_on_previous_text=False,

            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.55,

            initial_prompt=(
                "यह हिंदी और Hinglish speech है. हिंदी शब्दों को देवनागरी में सही लिखो. "
                "English words को English में रखो."
            )
        )

    except ASRTimeout as e:
        print(f"⏰ V18.4 ASR TIMEOUT: {e}")
        raise Exception("ASR timeout after 15 minutes")

    except RuntimeError as e:
        msg = str(e)
        if "cannot reshape tensor of 0 elements" not in msg:
            raise

        print("⚠️ Whisper transcribe failed on empty tensor; retrying safer fallback mode")

        try:
            asr_mode = "poor_quality_fallback"
            result = model.transcribe(
                asr_input,
                task="translate",
                language=None,
                fp16=False,
                verbose=False,
            word_timestamps=True,
                temperature=0,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=True,
                no_speech_threshold=0.5
            )

        except RuntimeError as retry_e:
            print(f"⚠️ ASR empty tensor retry failed safely: {retry_e}")
            raise Exception(
                "ASR failed on this video due to Whisper empty-tensor edge case. "
                "Backend stayed stable; try another video or GPU ASR later."
            )

    finally:
        if use_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    elapsed = round(time.time() - start_time, 2)
    print(f"✅ V18.4 ASR COMPLETE in {elapsed}s")

    raw_segments = result.get("segments", [])
    print(f"ASR_NATIVE_RAW_SEGMENTS count={len(raw_segments)}")
    cleaned_segments = clean_asr_segments(raw_segments, label=asr_mode)
    print(f"ASR_NATIVE_KEPT_SEGMENTS count={len(cleaned_segments)}")

    full_text = clean_repeated_phrases(result.get("text", ""))
    global_quality_score, global_quality_reasons = transcript_quality_score(full_text, cleaned_segments)
    cleaned_text = clean_repeated_phrases(
        " ".join(str(seg.get("text", "")) for seg in cleaned_segments if isinstance(seg, dict))
    )
    cleaned_quality_score, cleaned_quality_reasons = transcript_quality_score(cleaned_text, cleaned_segments)
    quality_score = cleaned_quality_score
    quality_reasons = cleaned_quality_reasons
    print(
        "ASR_QUALITY_COMPARE "
        f"global_quality_score={global_quality_score} "
        f"cleaned_quality_score={cleaned_quality_score} "
        f"global_reasons={global_quality_reasons} "
        f"cleaned_reasons={cleaned_quality_reasons}"
    )
    write_native_pre_retry_asr_artifact(
        job_id,
        file_path,
        asr_mode,
        cleaned_quality_score,
        cleaned_quality_reasons,
        cleaned_segments,
    )

    retry_score = quality_score if cleaned_segments else 0
    force_hard_asr_failure_reason = None
    if retry_score < 70 and device != "cuda":
        force_hard_asr_failure_reason = "faster_whisper_retry_gpu_unavailable"
        print("ASR_FW_RETRY_SKIPPED reason=gpu_unavailable production_cpu_full_asr_disabled")

    if retry_score < 70 and device == "cuda":
        print(f"ASR_RETRY_TRIGGER reason=low_quality_small score={retry_score}")
        release_model(MODEL_NAME)
        sample_seconds = ASR_FW_RETRY_SAMPLE_SECONDS
        fw_model = None
        fw_compute_type = "unknown"
        selection_reason = "medium_sample_not_good_enough"
        sample_failure_reason = None
        try:
            fw_device = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
            fw_compute_type = "int8_float16" if fw_device == "cuda" else "int8"
            print(
                "ASR_FW_RETRY_SAMPLE_START "
                f"model=medium compute_type={fw_compute_type} "
                f"timeout_seconds={ASR_FW_RETRY_SAMPLE_TIMEOUT_SECONDS}"
            )
            retry_sample_path = create_asr_retry_sample(asr_input, seconds=sample_seconds)
            medium_sample_raw_segments, medium_sample_text = transcribe_faster_whisper_retry_guarded(
                retry_sample_path,
                device,
                "sample",
                ASR_FW_RETRY_SAMPLE_TIMEOUT_SECONDS,
            )
            medium_sample_cleaned_segments = clean_asr_segments(
                medium_sample_raw_segments,
                label="faster_whisper_medium_retry_sample"
            )
            medium_sample_quality, medium_sample_reasons = transcript_quality_score(
                medium_sample_text,
                medium_sample_cleaned_segments
            )
            print(
                "ASR_FW_RETRY_SAMPLE_RESULT "
                f"quality={medium_sample_quality} "
                f"kept_segments={len(medium_sample_cleaned_segments)} "
                f"reasons={medium_sample_reasons}"
            )
        except Exception as e:
            medium_sample_cleaned_segments = []
            medium_sample_quality = 0
            medium_sample_reasons = []
            selection_reason = (
                "faster_whisper_sample_timeout"
                if isinstance(e, TimeoutError)
                else "faster_whisper_retry_failed"
            )
            sample_failure_reason = selection_reason
            print(f"ASR_FW_RETRY_FAILED error={e}")

        if sample_failure_reason:
            sample_passed = False
        else:
            sample_passed, selection_reason = should_run_full_medium_retry_candidate(
                quality_score,
                quality_reasons,
                len(cleaned_segments),
                medium_sample_quality,
                len(medium_sample_cleaned_segments),
                medium_sample_reasons,
            )
        if sample_passed:
            if selection_reason == "borderline_clean_sample_allow_chunked":
                print(
                    "ASR_FW_RETRY_SAMPLE_BORDERLINE_ALLOW_CHUNKED "
                    f"sample_quality={medium_sample_quality} "
                    f"kept_segments={len(medium_sample_cleaned_segments)} "
                    f"reasons={medium_sample_reasons}"
                )
            if selection_reason == "borderline_sample_native_low_confidence":
                print(
                    "ASR_RETRY_BORDERLINE_SAMPLE "
                    f"sample_quality={medium_sample_quality} "
                    f"native_quality={quality_score}"
                )
            print(
                "ASR_FW_RETRY_CHUNKED_START "
                f"sample_quality={medium_sample_quality} "
                f"chunk_seconds={ASR_FW_RETRY_CHUNK_SECONDS} "
                f"chunk_timeout_seconds={ASR_FW_RETRY_CHUNK_TIMEOUT_SECONDS}"
            )
            print(
                "ASR_FW_RETRY_FULL_START "
                f"mode=chunked chunk_seconds={ASR_FW_RETRY_CHUNK_SECONDS} "
                f"chunk_timeout_seconds={ASR_FW_RETRY_CHUNK_TIMEOUT_SECONDS}"
            )
            selection_reason = "full_medium_not_good_enough"
            try:
                medium_raw_segments, medium_text, medium_chunk_meta = transcribe_faster_whisper_retry_chunked(
                    asr_input,
                    device,
                )
                medium_cleaned_segments = clean_asr_segments(
                    medium_raw_segments,
                    label="faster_whisper_medium_retry_chunked"
                )
                medium_quality, medium_reasons = transcript_quality_score(
                    medium_text,
                    medium_cleaned_segments
                )
                medium_calibration = calibrate_chunked_faster_whisper_quality(
                    medium_quality,
                    medium_reasons,
                    medium_text,
                    medium_raw_segments,
                    medium_cleaned_segments,
                )
                medium_quality = medium_calibration["calibrated_quality"]
                medium_reasons = medium_calibration["calibrated_reasons"]
                asr_quality_diagnostic_report(
                    medium_text,
                    medium_cleaned_segments,
                    medium_quality,
                    medium_reasons,
                    label="faster_whisper_medium_retry_chunked",
                    job_id=job_id,
                )
                print(
                    "ASR_FW_RETRY_FULL_RESULT "
                    f"quality={medium_quality} kept_segments={len(medium_cleaned_segments)} "
                    f"raw_quality={medium_calibration.get('raw_quality')} "
                    f"readability_score={medium_calibration.get('readability_score')} "
                    f"chunks={medium_chunk_meta.get('chunks')} "
                    f"failed_chunks={len(medium_chunk_meta.get('failed_chunks', []))}"
                )
                print(
                    "ASR_FW_RETRY_CHUNKED_RESULT "
                    f"quality={medium_quality} kept_segments={len(medium_cleaned_segments)} "
                    f"raw_quality={medium_calibration.get('raw_quality')} "
                    f"readability_score={medium_calibration.get('readability_score')} "
                    f"chunks={medium_chunk_meta.get('chunks')} "
                    f"failed_chunks={len(medium_chunk_meta.get('failed_chunks', []))}"
                )
            except Exception as e:
                medium_raw_segments = []
                medium_cleaned_segments = []
                medium_text = ""
                medium_quality = 0
                medium_reasons = []
                medium_chunk_meta = {}
                medium_calibration = {}
                selection_reason = (
                    "faster_whisper_full_timeout"
                    if isinstance(e, TimeoutError)
                    else "faster_whisper_full_failed"
                )
                if isinstance(e, TimeoutError):
                    force_hard_asr_failure_reason = selection_reason
                print(f"ASR_FW_RETRY_FULL_FAILED error={e}")

            if (
                medium_cleaned_segments
            ):
                select_medium, selection_reason = should_select_chunked_medium_retry(
                    quality_score,
                    quality_reasons,
                    len(cleaned_segments),
                    medium_calibration,
                    len(medium_cleaned_segments),
                )
            else:
                select_medium = False

            if select_medium:
                raw_segments = medium_raw_segments
                cleaned_segments = medium_cleaned_segments
                full_text = medium_text
                quality_score = medium_quality
                quality_reasons = medium_reasons
                asr_mode = "faster_whisper_medium_retry_chunked"
                print(
                    "ASR_FW_RETRY_SELECTED "
                    f"model=faster_whisper_medium_chunked reason={selection_reason}"
                )
            else:
                if selection_reason in {
                    "full_medium_quality_not_above_50",
                    "full_medium_quality_below_65",
                    "full_medium_low_confidence",
                    "chunked_medium_calibrated_quality_below_65",
                    "chunked_medium_severe_repeated_hindi_garbage",
                    "chunked_medium_rejected_ratio_high",
                    "chunked_medium_readability_below_65",
                    "chunked_medium_duration_sanity_low",
                    "chunked_medium_replacement_chars_too_high",
                }:
                    force_hard_asr_failure_reason = selection_reason
                print(f"ASR_FW_RETRY_SELECTED model=small reason={selection_reason}")
            print(
                "ASR_RETRY_FINAL_DECISION "
                f"sample_quality={medium_sample_quality} "
                f"native_quality={retry_score} "
                f"full_medium_quality={medium_quality} "
                f"final_selected_mode={asr_mode} "
                f"final_selection_reason={selection_reason}"
            )
        else:
            print(f"ASR_FW_RETRY_SELECTED model=small reason={selection_reason}")
            print(
                "ASR_RETRY_FINAL_DECISION "
                f"sample_quality={medium_sample_quality} "
                f"native_quality={retry_score} "
                "full_medium_quality=not_run "
                f"final_selected_mode={asr_mode} "
                f"final_selection_reason={selection_reason}"
            )

        fw_model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    if False and retry_score < 70:
        if device == "cuda":
            print(f"ASR_RETRY_TRIGGER reason=low_quality_small score={retry_score}")
            release_model(MODEL_NAME)
            try:
                retry_model = get_model("medium")
            except RuntimeError as e:
                print(f"ASR_RETRY_MODEL_LOAD_FAILED model=medium error={e}")
                retry_model = None
            sample_seconds = 600
            selection_reason = (
                "medium_sample_not_good_enough"
                if retry_model is not None
                else "medium_model_load_failed"
            )
            try:
                if retry_model is None:
                    raise RuntimeError("medium_model_unavailable")
                print(f"ASR_RETRY_SAMPLE_START seconds={sample_seconds}")
                retry_sample_path = create_asr_retry_sample(asr_input, seconds=sample_seconds)
                medium_sample_result = transcribe_medium_retry(
                    retry_model,
                    retry_sample_path,
                    device
                )
                medium_sample_raw_segments = medium_sample_result.get("segments", [])
                medium_sample_cleaned_segments = clean_asr_segments(
                    medium_sample_raw_segments,
                    label="native_transcribe_medium_retry_sample"
                )
                medium_sample_text = clean_repeated_phrases(medium_sample_result.get("text", ""))
                medium_sample_quality, _ = transcript_quality_score(
                    medium_sample_text,
                    medium_sample_cleaned_segments
                )
                print(
                    "ASR_RETRY_SAMPLE_RESULT "
                    f"quality={medium_sample_quality} "
                    f"kept_segments={len(medium_sample_cleaned_segments)}"
                )
            except Exception as e:
                medium_sample_cleaned_segments = []
                medium_sample_quality = 0
                print(f"ASR_RETRY_SAMPLE_FAILED error={e}")

            sample_passed = (
                medium_sample_cleaned_segments
                and medium_sample_quality > quality_score + 15
                and medium_sample_quality >= 55
            )
            if not sample_passed:
                medium_result = {"segments": [], "text": ""}
            else:
                print("ASR_RETRY_FULL_START")
                selection_reason = "full_medium_not_good_enough"
                medium_result = retry_model.transcribe(
                asr_input,
                task="transcribe",
                language="hi",
                fp16=(device == "cuda"),
                verbose=False,
                temperature=0,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=False,
                word_timestamps=False,
                compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,
                no_speech_threshold=0.55,
                initial_prompt=(
                    "यह हिंदी और Hinglish speech है. हिंदी शब्दों को देवनागरी में सही लिखो. "
                    "English words को English में रखो."
                )
            )
            medium_raw_segments = medium_result.get("segments", [])
            medium_cleaned_segments = clean_asr_segments(
                medium_raw_segments,
                label="native_transcribe_medium_retry"
            )
            medium_text = clean_repeated_phrases(medium_result.get("text", ""))
            medium_quality, medium_reasons = transcript_quality_score(
                medium_text,
                medium_cleaned_segments
            )
            if sample_passed:
                print(
                    "ASR_RETRY_RESULT "
                    f"model=medium quality={medium_quality} kept_segments={len(medium_cleaned_segments)}"
                )
            if (
                medium_cleaned_segments
                and medium_quality > quality_score + 15
                and medium_quality >= 55
            ):
                result = medium_result
                raw_segments = medium_raw_segments
                cleaned_segments = medium_cleaned_segments
                full_text = medium_text
                quality_score = medium_quality
                quality_reasons = medium_reasons
                asr_mode = "native_transcribe_medium_retry"
                print("ASR_RETRY_SELECTED model=medium reason=full_medium_good_enough")
            else:
                print(f"ASR_RETRY_SELECTED model=small reason={selection_reason}")
        else:
            print("ASR_RETRY_SKIPPED reason=no_cuda")
            print("ASR_RETRY_SELECTED model=small reason=no_cuda")

    if not cleaned_segments:
        asr_mode = "translate_fallback"
        fallback_reason = "native_no_segments" if not raw_segments else "native_segments_all_rejected"
        print(
            "ASR_FALLBACK_TRIGGER "
            f"reason={fallback_reason} native_raw={len(raw_segments)} native_kept=0"
        )
        print("⚠️ Native transcribe produced 0 usable segments; retrying stable translate mode")
        retry_result = model.transcribe(
            asr_input,
            task="translate",
            language=None,
            fp16=(device == "cuda"),
            verbose=False,
            word_timestamps=True,
            temperature=0,
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.55,
            initial_prompt=(
                "यह हिंदी और Hinglish speech है. हिंदी शब्दों को देवनागरी में सही लिखो. "
                "English words को English में रखो."
            )
        )
        result = retry_result
        raw_segments = result.get("segments", [])
        print(f"ASR_TRANSLATE_RAW_SEGMENTS count={len(raw_segments)}")
        cleaned_segments = clean_asr_segments(raw_segments, label=asr_mode)
        full_text = clean_repeated_phrases(result.get("text", ""))
        quality_score, quality_reasons = transcript_quality_score(full_text, cleaned_segments)

    low_confidence_asr = asr_is_low_confidence_quality(quality_score, quality_reasons)
    hard_asr_failure, hard_asr_failure_reason = asr_should_fail_closed(
        quality_score,
        quality_reasons,
        low_confidence_asr,
    )
    if force_hard_asr_failure_reason:
        hard_asr_failure = True
        hard_asr_failure_reason = force_hard_asr_failure_reason

    for seg in cleaned_segments:
        seg["asr_mode"] = asr_mode
        seg["asr_quality_score"] = quality_score
        seg["asr_quality_reasons"] = quality_reasons
        seg["low_confidence_asr"] = low_confidence_asr

    if low_confidence_asr:
        print(
            "ASR_LOW_CONFIDENCE "
            f"mode={asr_mode} quality_score={quality_score} reasons={quality_reasons}"
        )

    if hard_asr_failure:
        print(
            "ASR_HARD_FAILURE "
            f"mode={asr_mode} quality_score={quality_score} "
            f"reason={hard_asr_failure_reason} reasons={quality_reasons}"
        )

    print(f"✅ ASR DONE | kept segments: {len(cleaned_segments)}")

    print(
        f"ASR_RESULT mode={asr_mode} quality_score={quality_score} "
        f"low_confidence={low_confidence_asr} kept_segments={len(cleaned_segments)}"
    )

    return {
        "text": full_text,
        "segments": cleaned_segments,
        "asr_mode": asr_mode,
        "asr_quality_score": quality_score,
        "asr_quality_reasons": quality_reasons,
        "low_confidence_asr": low_confidence_asr,
        "asr_hard_failure": hard_asr_failure,
        "asr_hard_failure_reason": hard_asr_failure_reason,
    }

