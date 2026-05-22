from asr_engine import transcribe
from ai_viral_engine import analyze_video
from asr_engine import asr_should_fail_closed
from clip_generator import generate_clips
from caption_engine import generate_captions
from subtitle_burner import burn_subtitles
from visual_engine import log_visual_intelligence, extract_best_thumbnail_frames

import traceback
import threading
import time
import glob
import re
import os
import uuid
import json
import copy
from pathlib import Path


AD_WORDS = [
    "career247", "career 247", "discount", "discount code", "coupon code",
    "course", "courses", "offer", "sale", "promotion", "coupon", "register",
    "call now", "email id", "phone number", "comment section",
    "link", "click on this link", "interview", "job focused", "certificate",
    "certificates", "price increase", "flat discount", "mega savings",
    "golden opportunity", "limited time", "enroll", "admission"
]

HARD_AD_WORDS = [
    "career247", "career 247", "sponsored", "sponsor", "promo code",
    "discount code", "click on this link", "comment section",
    "phone number", "email id", "mega savings", "flat discount",
]


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


def is_bad_transcript_clip(text):
    text = str(text or "").strip()
    if not text:
        return True

    low = text.lower()
    words = low.split()

    junk_patterns = [
        "à¥ à¥",
        "à¤“à¤® à¤“à¤®",
        "om om",
        "à¥¤à¥¤à¥¤à¥¤",
        "aaaaaa",
        "mmmmmm",
        "hmmmm",
    ]

    for j in junk_patterns:
        if j in low:
            return True

    compact = re.sub(r"\s+", "", low)
    if 20 < len(compact) < 90:
        unique_ratio = len(set(compact)) / max(len(compact), 1)
        if unique_ratio < 0.13:
            return True

    # Hindi/news/finance ASR can repeat real keywords like gold, deficit,
    # inflation, Bharat, China, tax, market etc. Only reject extreme loops.
    if len(words) >= 8:
        top = max(words.count(w) for w in set(words))
        if top / len(words) > 0.72:
            return True

    # Keep short but meaningful finance/news fragments alive.
    if len(words) < 4:
        return True

    return False


def is_ad_segment(text):
    text = str(text or "").lower()

    if any(word in text for word in HARD_AD_WORDS):
        return True

    matches = 0
    for word in AD_WORDS:
        if word in text:
            matches += 1

    return matches >= 2


def get_nearby_text(segments, start, end, window=25):
    parts = []

    for s in safe_dict_list(segments):
        ss = safe_float(s.get("start"))
        ee = safe_float(s.get("end"))

        if ee > start - window and ss < end + window:
            parts.append(str(s.get("text", "")))

    return " ".join(parts)


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


def v38_finance_economics_hashtags(text=""):
    text = str(text or "").lower()
    tags = ["#finance", "#economy", "#market", "#shorts"]

    if "trade deficit" in text or "à¤Ÿà¥à¤°à¥‡à¤¡ à¤¡à¥‡à¤«à¤¿à¤¸à¤¿à¤Ÿ" in text:
        tags.insert(2, "#TradeDeficit")
    elif "import duty" in text or "à¤‡à¤®à¥à¤ªà¥‹à¤°à¥à¤Ÿ à¤¡à¥à¤¯à¥‚à¤Ÿà¥€" in text or "gold" in text or "à¤—à¥‹à¤²à¥à¤¡" in text:
        tags.insert(2, "#ImportDuty")
    elif "inflation" in text or "à¤‡à¤¨à¥à¤«à¥à¤²à¥‡à¤¶à¤¨" in text or "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ" in text:
        tags.insert(2, "#Inflation")
    elif "export ban" in text or "sugar" in text or "à¤¶à¥à¤—à¤°" in text or "à¤¸à¥à¤—à¤°" in text:
        tags.insert(2, "#SugarMarket")

    return tags[:5]


def v40_niche_hashtags(niche, text=""):
    niche = str(niche or "general")
    text = str(text or "").lower()

    tag_map = {
        "podcast_story": ["#podcast", "#storytime", "#conversation", "#shorts"],
        "education_explainer": ["#education", "#explained", "#learn", "#shorts"],
        "geopolitics": ["#geopolitics", "#worldnews", "#explained", "#shorts"],
        "politics_news": ["#politics", "#news", "#explained", "#shorts"],
        "finance_business": ["#business", "#startup", "#money", "#shorts"],
        "crime_mystery": ["#mystery", "#truecrime", "#story", "#shorts"],
        "tech_ai": ["#ai", "#tech", "#future", "#shorts"],
        "self_improvement": ["#motivation", "#mindset", "#selfimprovement", "#shorts"],
        "health_fitness": ["#health", "#fitness", "#wellness", "#shorts"],
        "comedy_entertainment": ["#comedy", "#funny", "#entertainment", "#shorts"],
        "sports": ["#sports", "#highlights", "#shorts"],
    }

    if niche == "finance_economics":
        return v38_finance_economics_hashtags(text)

    tags = list(tag_map.get(niche, ["#viral", "#shorts"]))

    if "debate" in text or "against" in text or "à¤–à¤¿à¤²à¤¾à¤«" in text:
        tags.insert(1, "#debate")
    if "interview" in text or "à¤‡à¤‚à¤Ÿà¤°à¤µà¥à¤¯à¥‚" in text:
        tags.insert(1, "#interview")
    if "lesson" in text or "à¤¸à¥€à¤–" in text:
        tags.insert(1, "#lesson")

    deduped = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:5]


def generate_social_caption(title, hashtags, niche):
    if not isinstance(hashtags, list):
        hashtags = ["#viral", "#shorts"]

    if niche == "finance_economics":
        hashtags = v38_finance_economics_hashtags(title)
    elif hashtags == ["#viral"] or hashtags == ["#viral", "#shorts"]:
        hashtags = v40_niche_hashtags(niche, title)

    hashtag_text = " ".join(hashtags[:5])
    title = title or "This Moment Went Viral"

    if niche == "finance_economics":
        return {
            "youtube_caption": f"{title} | Finance, economy aur market impact explained. {hashtag_text}",
            "instagram_caption": f"{title}\n\n{hashtag_text}",
            "tiktok_caption": f"{title} {hashtag_text}",
            "niche": niche or "general"
        }

    return {
        "youtube_caption": f"{title} | Watch this viral moment. {hashtag_text}",
        "instagram_caption": f"{title}\n\n{hashtag_text}",
        "tiktok_caption": f"{title} ðŸ”¥ {hashtag_text}",
        "niche": niche or "general"
    }


V48_ASR_STABILITY_CHUNK_SIZE = 120.0
V48_ASR_STABILITY_CHUNK_OVERLAP = 10.0


def v48_asr_tokenize(text):
    return re.findall(r"[\u0900-\u097Fa-z0-9]+", str(text or "").lower())


def v48_asr_ngram_repetition_ratio(tokens, n):
    if len(tokens) < n * 2:
        return 0.0
    grams = [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]
    if not grams:
        return 0.0
    counts = {}
    for gram in grams:
        counts[gram] = counts.get(gram, 0) + 1
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / max(len(grams), 1)


def v48_segment_midpoint(segment):
    start = safe_float(segment.get("start"))
    end = safe_float(segment.get("end"), start)
    return start + max(0.0, end - start) / 2.0


def v48_asr_chunk_label(chunk_segments):
    text = " ".join(str(s.get("text", "")) for s in safe_dict_list(chunk_segments))
    tokens = v48_asr_tokenize(text)
    if not chunk_segments or len(tokens) < 4:
        return "empty_or_sparse_chunk", 100

    replacement_chars = text.count("\ufffd") + text.count("�")
    unique_ratio = len(set(tokens)) / max(len(tokens), 1)
    repeated_bigram_ratio = v48_asr_ngram_repetition_ratio(tokens, 2)
    repeated_trigram_ratio = v48_asr_ngram_repetition_ratio(tokens, 3)
    top_token_ratio = max(tokens.count(token) for token in set(tokens)) / max(len(tokens), 1)

    adjacent_dupes = 0
    previous = None
    short_fragments = 0
    for segment in safe_dict_list(chunk_segments):
        segment_text = re.sub(r"\s+", " ", str(segment.get("text", "")).strip().lower())
        if previous and segment_text and segment_text == previous:
            adjacent_dupes += 1
        previous = segment_text
        if len(v48_asr_tokenize(segment_text)) <= 3:
            short_fragments += 1
    short_fragment_ratio = short_fragments / max(len(chunk_segments), 1)

    collapse_score = 0
    if replacement_chars:
        collapse_score += min(35, replacement_chars * 8)
    if unique_ratio < 0.34:
        collapse_score += int((0.34 - unique_ratio) * 80)
    if top_token_ratio >= 0.45 and unique_ratio < 0.45:
        collapse_score += int(top_token_ratio * 25)
    if repeated_bigram_ratio >= 0.16:
        collapse_score += int(repeated_bigram_ratio * 65)
    if repeated_trigram_ratio >= 0.10:
        collapse_score += int(repeated_trigram_ratio * 85)
    if adjacent_dupes:
        collapse_score += min(30, adjacent_dupes * 10)
    if short_fragment_ratio >= 0.45 and len(chunk_segments) >= 3:
        collapse_score += int(short_fragment_ratio * 30)

    replacement_supported = (
        unique_ratio < 0.45
        or repeated_bigram_ratio >= 0.16
        or repeated_trigram_ratio >= 0.10
        or adjacent_dupes > 0
    )
    collapse_score = min(100, collapse_score)

    if replacement_chars >= 3 or (replacement_chars > 0 and replacement_supported):
        return "replacement_artifact_collapse", collapse_score
    if short_fragment_ratio >= 0.65 and len(chunk_segments) >= 3:
        return "short_fragment_collapse", collapse_score
    if collapse_score >= 35 and (
        repeated_bigram_ratio >= 0.16
        or repeated_trigram_ratio >= 0.10
        or adjacent_dupes > 0
        or top_token_ratio >= 0.32
    ):
        return "local_repetition_collapse", collapse_score
    if collapse_score >= 25:
        return "borderline", collapse_score
    return "clean", collapse_score


def v48_build_asr_stability_chunks(segments):
    segments = safe_dict_list(segments)
    if not segments:
        return []
    max_end = max(safe_float(s.get("end"), safe_float(s.get("start"))) for s in segments)
    step = max(1.0, V48_ASR_STABILITY_CHUNK_SIZE - V48_ASR_STABILITY_CHUNK_OVERLAP)
    chunks = []
    start = 0.0
    while start <= max_end:
        end = start + V48_ASR_STABILITY_CHUNK_SIZE
        chunk_segments = [
            segment for segment in segments
            if start <= v48_segment_midpoint(segment) < end
        ]
        label, collapse_score = v48_asr_chunk_label(chunk_segments)
        chunks.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "label": label,
            "collapse_score": collapse_score,
        })
        start += step
    return chunks


def v48_interval_overlap_ratio(start, end, windows):
    duration = max(0.01, end - start)
    overlaps = []
    for window in safe_dict_list(windows):
        overlap_start = max(start, safe_float(window.get("start")))
        overlap_end = min(end, safe_float(window.get("end")))
        if overlap_end > overlap_start:
            overlaps.append((overlap_start, overlap_end))
    if not overlaps:
        return 0.0
    overlaps.sort()
    merged = []
    for overlap_start, overlap_end in overlaps:
        if not merged or overlap_start > merged[-1][1]:
            merged.append([overlap_start, overlap_end])
        else:
            merged[-1][1] = max(merged[-1][1], overlap_end)
    total = sum(overlap_end - overlap_start for overlap_start, overlap_end in merged)
    return round(min(1.0, total / duration), 3)


def v48_candidate_asr_stability(start, end, asr_stability_chunks):
    chunks = safe_dict_list(asr_stability_chunks)
    if not chunks:
        return {
            "local_asr_confidence_label": "unknown",
            "unstable_window_overlap_ratio": 0.0,
            "chunk_confidence_score": 50,
            "local_asr_reasons": ["asr_stability_metadata_unavailable"],
        }

    overlapping = []
    unstable_windows = []
    for chunk in chunks:
        overlap_start = max(start, safe_float(chunk.get("start")))
        overlap_end = min(end, safe_float(chunk.get("end")))
        if overlap_end <= overlap_start:
            continue
        label = str(chunk.get("label") or "unknown")
        overlapping.append(label)
        if label not in {"clean", "borderline"}:
            unstable_windows.append(chunk)

    unstable_ratio = v48_interval_overlap_ratio(start, end, unstable_windows)
    if not overlapping:
        label = "unknown"
        score = 50
        reasons = ["no_overlapping_asr_chunks"]
    elif unstable_ratio >= 0.20:
        label = "unstable"
        score = max(0, int(round(100 - unstable_ratio * 100)))
        reasons = [f"unstable_window_overlap_ratio={unstable_ratio}"]
    elif unstable_ratio > 0 or "borderline" in overlapping:
        label = "borderline"
        score = min(74, max(50, int(round(100 - unstable_ratio * 100))))
        reasons = [f"minor_unstable_or_borderline_overlap={unstable_ratio}"]
    else:
        label = "clean"
        score = 100
        reasons = []

    return {
        "local_asr_confidence_label": label,
        "unstable_window_overlap_ratio": unstable_ratio,
        "chunk_confidence_score": score,
        "local_asr_reasons": reasons,
    }


def v48_asr_stability_score_adjustment(local_asr):
    label = str(local_asr.get("local_asr_confidence_label") or "unknown")
    unstable_ratio = safe_float(local_asr.get("unstable_window_overlap_ratio"))
    if label == "clean":
        return 6
    if label == "unstable" and unstable_ratio >= 0.20:
        return -min(12, max(4, int(round(unstable_ratio * 12))))
    return 0


def v49_overlapping_unstable_asr_windows(start, end, asr_stability_chunks):
    windows = []
    for chunk in safe_dict_list(asr_stability_chunks):
        label = str(chunk.get("label") or "unknown")
        if label in {"clean", "borderline"}:
            continue
        overlap_start = max(safe_float(start), safe_float(chunk.get("start")))
        overlap_end = min(safe_float(end), safe_float(chunk.get("end")))
        if overlap_end <= overlap_start:
            continue
        windows.append({
            "start": safe_float(chunk.get("start")),
            "end": safe_float(chunk.get("end")),
            "label": label,
            "collapse_score": chunk.get("collapse_score"),
            "overlap_seconds": round(overlap_end - overlap_start, 2),
        })
    return windows


def v49_segment_salvage_decision(start, end, local_asr, asr_stability_chunks, repaired_window_available=False):
    local_asr = local_asr if isinstance(local_asr, dict) else {}
    label = str(local_asr.get("local_asr_confidence_label") or "unknown")
    unstable_ratio = safe_float(local_asr.get("unstable_window_overlap_ratio"))
    unstable_windows = v49_overlapping_unstable_asr_windows(start, end, asr_stability_chunks)
    repaired_window_required = label == "unstable"

    if label == "clean":
        decision = "allowed_clean"
        reason = "production_local_asr_clean"
    elif label == "borderline":
        decision = "allowed_borderline"
        reason = "production_local_asr_borderline"
    elif repaired_window_available:
        decision = "allowed_repaired_unstable"
        reason = "unstable_window_has_repaired_segments"
    else:
        decision = "quarantined_unstable"
        reason = "production_unstable_asr_window_unrepaired"

    return {
        "segment_salvage_decision": decision,
        "quarantined_unstable_windows": unstable_windows if decision == "quarantined_unstable" else [],
        "repaired_window_required": repaired_window_required,
        "repaired_window_available": bool(repaired_window_available),
        "salvage_unstable_overlap_ratio": unstable_ratio,
        "segment_salvage_reason": reason,
    }


def v49_9_repaired_window_status(job_id, start, end):
    try:
        from asr_engine import load_v49_9_repaired_window_artifact
    except Exception:
        load_v49_9_repaired_window_artifact = None

    payload = {}
    if load_v49_9_repaired_window_artifact is not None:
        payload = load_v49_9_repaired_window_artifact(job_id, start, end)
    repaired_text = re.sub(r"\s+", " ", str(payload.get("repaired_text") or "")).strip()
    repaired_window_available = bool(payload.get("repaired_window_available")) and bool(repaired_text)
    repair_export_safe = bool(payload.get("repair_export_safe")) and repaired_window_available
    return {
        "v49_9_repair_artifact_found": bool(payload),
        "v49_9_repaired_window_available": repaired_window_available,
        "v49_9_repair_export_safe": repair_export_safe,
        "v49_9_repaired_local_asr_label": payload.get("repaired_local_asr_label"),
        "v49_9_repaired_unstable_overlap_ratio": payload.get("repaired_unstable_overlap_ratio"),
        "v49_9_repaired_transcript_quality_score": payload.get("repaired_transcript_quality_score"),
        "v49_9_repaired_low_confidence_asr": payload.get("repaired_low_confidence_asr"),
        "v49_9_repaired_semantic_label": payload.get("repaired_semantic_label"),
        "v49_9_repaired_semantic_score": payload.get("repaired_semantic_score"),
        "v49_9_repaired_text_preview": repaired_text[:220],
        "v49_9_repair_decision_reason": payload.get("repair_decision_reason") or (
            "validated_audio_backed_repair_available"
            if repaired_window_available
            else "no_validated_audio_backed_repair"
        ),
        "v49_9_repair_strict_reasons": (
            payload.get("v49_9_repair_strict_reasons", [])[:5]
            if isinstance(payload.get("v49_9_repair_strict_reasons"), list)
            else []
        ),
        "v49_9_repaired_window_artifact": payload.get("artifact_path"),
        "v49_9_repaired_text": repaired_text,
    }


def v50_1_payoff_setup_signal(text, score_breakdown=None):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    low = text.lower()
    score_breakdown = score_breakdown if isinstance(score_breakdown, dict) else {}

    explicit_result_patterns = [
        r"\bthis is why\b", r"\bthat is why\b", r"\bthis means\b", r"\bwhich means\b",
        r"\btherefore\b", r"\bas a result\b", r"\bresult is\b", r"\bin the end\b",
        r"\bfinal result\b", r"\bwhy this matters\b", r"\bimpact\b", r"\beffect\b",
        r"\biska matlab\b", r"\bisliye\b", r"\bisi liye\b", r"\bis wajah se\b",
        r"\byahi wajah\b", r"\bnateeja\b", r"\bnatija\b", r"\bkyonki\b",
    ]
    contrast_patterns = [
        r"\bbut\b", r"\bhowever\b", r"\binstead\b", r"\brather\b",
        r"\blekin\b", r"\bmagar\b", r"\bpar\b", r"\bwahin\b",
    ]
    cause_effect_patterns = [
        r"\bbecause\b", r"\bcauses?\b", r"\bleads? to\b", r"\bused to\b",
        r"\bmakes?\b", r"\bbanata\b", r"\bbanati\b", r"\buse hoti\b",
        r"\bke liye\b", r"\bke wajah se\b", r"\bke kaaran\b", r"\bso that\b",
    ]
    matter_patterns = [
        r"\bthreat\b", r"\brisk\b", r"\badvantage\b", r"\bbenefit\b", r"\bproblem\b",
        r"\bimportant\b", r"\bmatters\b", r"\bexplains?\b", r"\bpolicy\b",
        r"\bimpact\b", r"\bcomparison\b", r"\bnetwork\b", r"\bstrategy\b",
    ]
    entity_terms = [
        "india", "bharat", "china", "japan", "netherlands", "delhi", "mumbai",
        "modi", "government", "country", "countries", "company", "companies",
        "china", "bharat", "nederland", "नीदरलैंड", "चाइना", "भारत",
    ]

    explicit_hits = sum(1 for pattern in explicit_result_patterns if re.search(pattern, low))
    contrast_hits = sum(1 for pattern in contrast_patterns if re.search(pattern, low))
    cause_effect_hits = sum(1 for pattern in cause_effect_patterns if re.search(pattern, low))
    matter_hits = sum(1 for pattern in matter_patterns if re.search(pattern, low))
    entity_hits = sum(1 for term in entity_terms if term in low)

    context_quality = safe_float(score_breakdown.get("context_quality"))
    setup_strength = safe_float(score_breakdown.get("setup_strength"))
    continuation_risk = safe_float(score_breakdown.get("continuation_risk"))
    local_label = str(score_breakdown.get("local_asr_confidence_label") or "unknown")
    semantic_label = str(score_breakdown.get("semantic_asr_confidence_label") or "unknown")
    repaired_safe = bool(score_breakdown.get("v49_9_repair_export_safe"))

    setup_detected = (
        context_quality >= 8
        or setup_strength >= 8
        or not low.startswith((
            "and ", "but ", "so ", "because ", "then ", "which ", "that ", "if ",
            "after that", "at that time", "now come"
        ))
    )

    payoff_detected = False
    payoff_reason = ""
    if explicit_hits >= 1 and (cause_effect_hits >= 1 or matter_hits >= 1):
        payoff_detected = True
        payoff_reason = "explicit_result_plus_cause_effect"
    elif contrast_hits >= 1 and entity_hits >= 2 and matter_hits >= 1:
        payoff_detected = True
        payoff_reason = "entity_comparison_contrast_payoff"
    elif cause_effect_hits >= 2 and entity_hits >= 1:
        payoff_detected = True
        payoff_reason = "cause_effect_explainer_payoff"
    elif matter_hits >= 2 and entity_hits >= 2:
        payoff_detected = True
        payoff_reason = "why_this_matters_explainer_payoff"

    override = bool(
        payoff_detected
        and setup_detected
        and continuation_risk <= 24
        and local_label == "clean"
        and semantic_label in {"clean_semantics", "borderline_semantics"}
        and (repaired_safe or local_label == "clean")
    )

    return {
        "v50_1_payoff_detected": payoff_detected,
        "v50_1_setup_detected": setup_detected,
        "v50_1_payoff_reason": payoff_reason,
        "v50_1_no_hook_no_payoff_override": override,
    }


def v50_repaired_text_boundaries(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return "", ""
    words = text.split()
    if len(words) <= 8:
        return text, text
    span = max(4, min(18, len(words) // 3))
    start_text = " ".join(words[:span]).strip()
    end_text = " ".join(words[-span:]).strip()
    return start_text or text, end_text or text


def v50_effective_repaired_text_payload(combined_text, start_text, end_text, local_asr, v49_9_repair):
    combined_text = re.sub(r"\s+", " ", str(combined_text or "")).strip()
    original_preview = combined_text[:220]
    local_asr = local_asr if isinstance(local_asr, dict) else {}
    v49_9_repair = v49_9_repair if isinstance(v49_9_repair, dict) else {}
    repaired_text = re.sub(r"\s+", " ", str(v49_9_repair.get("v49_9_repaired_text") or "")).strip()
    should_apply = bool(
        v49_9_repair.get("v49_9_repaired_window_available")
        and v49_9_repair.get("v49_9_repair_export_safe")
        and repaired_text
    )
    if not should_apply:
        return {
            "combined_text": combined_text,
            "start_text": start_text,
            "end_text": end_text,
            "local_asr": local_asr,
            "metadata": {
                "v50_repaired_text_applied": False,
                "v50_original_text_preview": original_preview,
                "v50_repaired_text_preview": "",
                "v50_repaired_text_source": "",
            },
        }

    repaired_start_text, repaired_end_text = v50_repaired_text_boundaries(repaired_text)
    effective_local_asr = {
        "local_asr_confidence_label": v49_9_repair.get("v49_9_repaired_local_asr_label") or local_asr.get("local_asr_confidence_label"),
        "unstable_window_overlap_ratio": safe_float(
            v49_9_repair.get("v49_9_repaired_unstable_overlap_ratio"),
            safe_float(local_asr.get("unstable_window_overlap_ratio")),
        ),
        "chunk_confidence_score": 100 if str(v49_9_repair.get("v49_9_repaired_local_asr_label") or "") == "clean" else safe_float(local_asr.get("chunk_confidence_score"), 50),
        "local_asr_reasons": [],
    }
    if effective_local_asr["local_asr_confidence_label"] == "borderline":
        effective_local_asr["chunk_confidence_score"] = 74

    return {
        "combined_text": repaired_text,
        "start_text": repaired_start_text,
        "end_text": repaired_end_text,
        "local_asr": effective_local_asr,
        "metadata": {
            "v50_repaired_text_applied": True,
            "v50_original_text_preview": original_preview,
            "v50_repaired_text_preview": repaired_text[:220],
            "v50_repaired_text_source": "audio_backed_exact_window",
        },
    }


def v50_2_context_piece_text(segments, start, end):
    parts = []
    for seg in safe_dict_list(segments or []):
        seg_start = safe_float(seg.get("start"))
        seg_end = safe_float(seg.get("end"), seg_start)
        if seg_end <= start or seg_start >= end:
            continue
        text = re.sub(r"\s+", " ", str(seg.get("text") or "")).strip()
        if text:
            parts.append(text)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def v50_2_context_piece_guard(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return False, "empty_context"
    if is_bad_transcript_clip(text):
        return False, "bad_transcript_context"
    if is_ad_segment(text):
        return False, "ad_context"
    if _v7_is_drift(text):
        return False, "topic_drift"
    if v38_text_quality_is_severe(text):
        return False, "severe_text_quality"
    semantic = v48_semantic_asr_confidence(text)
    if semantic.get("semantic_asr_confidence_label") == "degraded_semantics":
        return False, "semantic_degraded_context"
    return True, ""


def v50_2_collect_adjacent_context(segments, anchor_start, anchor_end, asr_stability_chunks, direction="backward", max_seconds=12.0, max_gap=0.8):
    ordered = safe_dict_list(segments or [])
    selected = []
    max_seconds = max(2.0, safe_float(max_seconds, 12.0))
    max_gap = max(0.1, safe_float(max_gap, 0.8))

    if direction == "backward":
        cursor = safe_float(anchor_start)
        for seg in reversed(ordered):
            seg_start = safe_float(seg.get("start"))
            seg_end = safe_float(seg.get("end"), seg_start)
            if seg_end > cursor + 0.01:
                continue
            gap = cursor - seg_end
            if gap > max_gap:
                break
            if anchor_start - seg_start > max_seconds:
                break
            text = v50_2_context_piece_text(ordered, seg_start, anchor_start)
            local_asr = v48_candidate_asr_stability(seg_start, anchor_start, asr_stability_chunks)
            if str(local_asr.get("local_asr_confidence_label") or "unknown") == "unstable":
                break
            ok, reason = v50_2_context_piece_guard(text)
            if not ok:
                break
            semantic = v48_semantic_asr_confidence(text)
            selected.insert(0, {
                "start": round(seg_start, 2),
                "end": round(anchor_start, 2),
                "text": text,
                "local_asr_confidence_label": local_asr.get("local_asr_confidence_label"),
                "semantic_asr_confidence_label": semantic.get("semantic_asr_confidence_label"),
                "source": f"backward_adjacent_{len(selected) + 1}_segments",
                "rejected_reason": reason,
            })
            cursor = seg_start
        return selected[0] if selected else None

    cursor = safe_float(anchor_end)
    for seg in ordered:
        seg_start = safe_float(seg.get("start"))
        seg_end = safe_float(seg.get("end"), seg_start)
        if seg_start < cursor - 0.01:
            continue
        gap = seg_start - cursor
        if gap > max_gap:
            break
        if seg_end - anchor_end > max_seconds:
            break
        text = v50_2_context_piece_text(ordered, anchor_end, seg_end)
        local_asr = v48_candidate_asr_stability(anchor_end, seg_end, asr_stability_chunks)
        if str(local_asr.get("local_asr_confidence_label") or "unknown") == "unstable":
            break
        ok, reason = v50_2_context_piece_guard(text)
        if not ok:
            break
        semantic = v48_semantic_asr_confidence(text)
        selected.append({
            "start": round(anchor_end, 2),
            "end": round(seg_end, 2),
            "text": text,
            "local_asr_confidence_label": local_asr.get("local_asr_confidence_label"),
            "semantic_asr_confidence_label": semantic.get("semantic_asr_confidence_label"),
            "source": f"forward_adjacent_{len(selected) + 1}_segments",
            "rejected_reason": reason,
        })
        cursor = seg_end
    return selected[-1] if selected else None


def v50_2_context_local_asr(base_local_asr, added_contexts):
    base_local_asr = base_local_asr if isinstance(base_local_asr, dict) else {}
    labels = [str(base_local_asr.get("local_asr_confidence_label") or "unknown")]
    labels.extend(str(ctx.get("local_asr_confidence_label") or "unknown") for ctx in safe_dict_list(added_contexts))
    if any(label == "unstable" for label in labels):
        return {
            "local_asr_confidence_label": "unstable",
            "unstable_window_overlap_ratio": 1.0,
            "chunk_confidence_score": 0,
            "local_asr_reasons": ["context_shaping_added_unstable_asr"],
        }
    if any(label == "borderline" for label in labels):
        return {
            "local_asr_confidence_label": "borderline",
            "unstable_window_overlap_ratio": 0.15,
            "chunk_confidence_score": 74,
            "local_asr_reasons": ["context_shaping_added_borderline_asr"],
        }
    return {
        "local_asr_confidence_label": "clean",
        "unstable_window_overlap_ratio": 0.0,
        "chunk_confidence_score": 100,
        "local_asr_reasons": [],
    }


def v50_2_context_shape_candidate(clip, segments, asr_stability_chunks, niche="general"):
    clip = clip if isinstance(clip, dict) else {}
    score_breakdown = clip.get("score_breakdown", {}) if isinstance(clip.get("score_breakdown"), dict) else {}
    base_start = round(safe_float(clip.get("start")), 2)
    base_end = round(safe_float(clip.get("end"), base_start), 2)
    base_text = re.sub(r"\s+", " ", str(clip.get("expanded_text") or clip.get("source_text") or "")).strip()
    base_local_label = str(score_breakdown.get("local_asr_confidence_label") or "unknown")
    base_semantic_label = str(score_breakdown.get("semantic_asr_confidence_label") or "unknown")
    max_duration = min(max(18.0, safe_float(v40_clip_profile(niche).get("max"), 36.0)), 36.0)
    base_reasons = creator_qa_rejection_reasons(copy.deepcopy(clip), [])

    default_result = {
        "v50_2_context_expanded": False,
        "v50_2_original_window": [base_start, base_end],
        "v50_2_expanded_window": [base_start, base_end],
        "v50_2_setup_source": "existing_window" if safe_float(score_breakdown.get("context_quality")) >= 8 else "",
        "v50_2_payoff_source": "",
        "v50_2_expansion_rejected_reason": "",
        "v50_2_local_asr_confidence_label": base_local_label,
        "v50_2_semantic_asr_confidence_label": base_semantic_label,
        "v50_2_context_quality": safe_float(score_breakdown.get("context_quality")),
        "v50_2_payoff_bonus": safe_float(score_breakdown.get("payoff_bonus")),
        "expanded_text": base_text,
        "expanded_start_text": str(score_breakdown.get("start_text") or base_text).strip(),
        "expanded_end_text": str(score_breakdown.get("end_text") or base_text).strip(),
        "before_reasons": base_reasons,
        "after_reasons": base_reasons[:],
    }

    if "no_hook_no_payoff" not in base_reasons:
        default_result["v50_2_expansion_rejected_reason"] = "base_candidate_not_no_hook_no_payoff"
        return default_result
    if base_local_label != "clean":
        default_result["v50_2_expansion_rejected_reason"] = "base_candidate_not_clean"
        return default_result
    if base_semantic_label not in {"clean_semantics", "borderline_semantics"}:
        default_result["v50_2_expansion_rejected_reason"] = "base_candidate_semantic_degraded"
        return default_result

    base_local_asr = {
        "local_asr_confidence_label": base_local_label,
        "unstable_window_overlap_ratio": safe_float(score_breakdown.get("unstable_window_overlap_ratio")),
        "chunk_confidence_score": safe_float(score_breakdown.get("chunk_confidence_score"), 100),
        "local_asr_reasons": score_breakdown.get("local_asr_reasons", [])[:5] if isinstance(score_breakdown.get("local_asr_reasons"), list) else [],
    }
    left_context = v50_2_collect_adjacent_context(
        segments,
        base_start,
        base_end,
        asr_stability_chunks,
        direction="backward",
    )
    right_context = v50_2_collect_adjacent_context(
        segments,
        base_start,
        base_end,
        asr_stability_chunks,
        direction="forward",
    )

    if not left_context and not right_context:
        default_result["v50_2_expansion_rejected_reason"] = "no_clean_adjacent_context"
        return default_result

    variants = []
    if left_context:
        variants.append((left_context, None))
    if right_context:
        variants.append((None, right_context))
    if left_context and right_context:
        variants.append((left_context, right_context))

    best = None
    best_rank = None
    rejected_reasons = []
    for left, right in variants:
        expanded_start = round(safe_float(left.get("start"), base_start), 2) if left else base_start
        expanded_end = round(safe_float(right.get("end"), base_end), 2) if right else base_end
        if expanded_end - expanded_start > max_duration:
            rejected_reasons.append("expanded_window_too_long")
            continue

        added_contexts = [ctx for ctx in [left, right] if ctx]
        expanded_text = re.sub(
            r"\s+",
            " ",
            " ".join(part for part in [
                left.get("text") if left else "",
                base_text,
                right.get("text") if right else "",
            ] if part).strip(),
        ).strip()
        ok, reason = v50_2_context_piece_guard(expanded_text)
        if not ok:
            rejected_reasons.append(reason)
            continue

        local_asr = v50_2_context_local_asr(base_local_asr, added_contexts)
        semantic = v48_semantic_asr_confidence(expanded_text)
        if semantic.get("semantic_asr_confidence_label") == "degraded_semantics":
            rejected_reasons.append("expanded_window_semantic_degraded")
            continue

        hook_bonus = safe_float(score_breakdown.get("hook_bonus"))
        v43_bonus, _ = v43_hinglish_payoff_bonus(expanded_text)
        v44_bonus, _, _ = v44_semantic_payoff_score(expanded_text)
        if v44_payoff_quality_block(expanded_text):
            payoff_bonus = 0
        else:
            payoff_bonus = max(
                v6_payoff_bonus(expanded_text),
                v7_better_payoff_bonus(expanded_text),
                v43_bonus,
                v44_bonus,
            )
        start_text, end_text = v50_repaired_text_boundaries(expanded_text)
        test_clip = copy.deepcopy(clip)
        test_clip["expanded_text"] = expanded_text
        test_clip["start"] = expanded_start
        test_clip["end"] = expanded_end
        test_sb = test_clip.setdefault("score_breakdown", {})
        test_sb["hook_bonus"] = hook_bonus
        test_sb["payoff_bonus"] = payoff_bonus
        test_sb["context_quality"] = v7_context_quality_score(expanded_text)
        test_sb["start_text"] = start_text
        test_sb["end_text"] = end_text
        test_sb["local_asr_confidence_label"] = local_asr["local_asr_confidence_label"]
        test_sb["unstable_window_overlap_ratio"] = local_asr["unstable_window_overlap_ratio"]
        test_sb["chunk_confidence_score"] = local_asr["chunk_confidence_score"]
        test_sb["local_asr_reasons"] = local_asr["local_asr_reasons"]
        test_sb["semantic_asr_confidence_label"] = semantic["semantic_asr_confidence_label"]
        test_sb["semantic_asr_corruption_score"] = semantic["semantic_asr_corruption_score"]
        test_sb["semantic_asr_reasons"] = semantic["semantic_asr_reasons"][:5]

        after_reasons = creator_qa_rejection_reasons(test_clip, [])
        if "no_hook_no_payoff" in after_reasons:
            rejected_reasons.append("no_creator_qa_improvement")
            continue

        creator_safe = len(after_reasons) == 0
        rank = (
            1 if creator_safe else 0,
            -len(after_reasons),
            payoff_bonus,
            safe_float(test_sb.get("context_quality")),
            -(expanded_end - expanded_start),
        )
        if best is None or rank > best_rank:
            best = {
                "v50_2_context_expanded": True,
                "v50_2_original_window": [base_start, base_end],
                "v50_2_expanded_window": [expanded_start, expanded_end],
                "v50_2_setup_source": left.get("source") if left else ("existing_window" if safe_float(score_breakdown.get("context_quality")) >= 8 else ""),
                "v50_2_payoff_source": right.get("source") if right else "existing_window",
                "v50_2_expansion_rejected_reason": "",
                "v50_2_local_asr_confidence_label": local_asr["local_asr_confidence_label"],
                "v50_2_semantic_asr_confidence_label": semantic["semantic_asr_confidence_label"],
                "v50_2_context_quality": safe_float(test_sb.get("context_quality")),
                "v50_2_payoff_bonus": payoff_bonus,
                "expanded_text": expanded_text,
                "expanded_start_text": start_text,
                "expanded_end_text": end_text,
                "before_reasons": base_reasons,
                "after_reasons": after_reasons,
            }
            best_rank = rank

    if best:
        return best

    default_result["v50_2_expansion_rejected_reason"] = rejected_reasons[0] if rejected_reasons else "no_clean_payoff_context"
    return default_result


def v52_payoff_anchor_signal(text, score_breakdown=None):
    normalized = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    score_breakdown = score_breakdown if isinstance(score_breakdown, dict) else {}
    if not normalized:
        return {
            "v52_payoff_anchor_detected": False,
            "v52_payoff_anchor_reason": "",
        }
    if is_bad_transcript_clip(normalized) or is_ad_segment(normalized) or _v7_is_drift(normalized):
        return {
            "v52_payoff_anchor_detected": False,
            "v52_payoff_anchor_reason": "",
        }

    outcome_patterns = [
        "isliye", "isi liye", "iska matlab", "matlab ye", "matlab yeh",
        "natija", "nateeja", "finally", "in the end", "therefore",
        "result", "as a result", "yeh wajah hai", "ye wajah hai",
        "because of this", "this means",
    ]
    reveal_patterns = [
        "lekin", "magar", "par", "however", "but", "sach ye hai",
        "asli baat", "pata chala", "twist", "wahin",
    ]
    impact_patterns = [
        "impact", "risk", "benefit", "loss", "profit", "market",
        "policy", "government", "company", "country", "india", "bharat",
        "china", "price", "mahanga", "rights", "film", "strategy",
    ]
    emotional_patterns = [
        "us din", "tab tak", "akhirkar", "yaad rahega", "seekh",
        "lesson", "samajh", "mil jayega", "badal jayega",
    ]
    comparison_patterns = [
        "sabse", "zyada", "kam", "aage", "peeche", "top", "better",
        "compare", "comparison", "number one", "rank",
    ]

    outcome_hits = sum(1 for p in outcome_patterns if p in normalized)
    reveal_hits = sum(1 for p in reveal_patterns if p in normalized)
    impact_hits = sum(1 for p in impact_patterns if p in normalized)
    emotional_hits = sum(1 for p in emotional_patterns if p in normalized)
    comparison_hits = sum(1 for p in comparison_patterns if p in normalized)
    words = normalized.split()
    local_label = str(score_breakdown.get("local_asr_confidence_label") or "unknown")
    semantic_label = str(score_breakdown.get("semantic_asr_confidence_label") or "unknown")

    if local_label == "unstable" or semantic_label == "degraded_semantics":
        return {
            "v52_payoff_anchor_detected": False,
            "v52_payoff_anchor_reason": "",
        }
    if len(words) < 7 or len(words) > 80:
        return {
            "v52_payoff_anchor_detected": False,
            "v52_payoff_anchor_reason": "",
        }

    anchor_detected = False
    anchor_reason = ""
    if outcome_hits >= 1 and impact_hits >= 1:
        anchor_detected = True
        anchor_reason = "explicit_outcome_with_impact"
    elif reveal_hits >= 1 and impact_hits >= 1:
        anchor_detected = True
        anchor_reason = "reveal_or_contrast_with_impact"
    elif emotional_hits >= 1 and (outcome_hits >= 1 or reveal_hits >= 1):
        anchor_detected = True
        anchor_reason = "emotional_conclusion_anchor"
    elif comparison_hits >= 2 and impact_hits >= 1:
        anchor_detected = True
        anchor_reason = "comparison_or_ranking_outcome"
    elif outcome_hits >= 2:
        anchor_detected = True
        anchor_reason = "dense_outcome_language"

    return {
        "v52_payoff_anchor_detected": anchor_detected,
        "v52_payoff_anchor_reason": anchor_reason,
    }


def v52_generate_payoff_native_candidates(segments, asr_stability_chunks, niche="general", max_candidates=8):
    segments = safe_dict_list(segments or [])
    max_duration = min(max(14.0, safe_float(v40_clip_profile(niche).get("max"), 30.0)), 28.0)
    generated = []
    seen_windows = set()

    for idx, seg in enumerate(segments):
        seg_start = round(safe_float(seg.get("start")), 2)
        seg_end = round(safe_float(seg.get("end"), seg_start), 2)
        seg_text = re.sub(r"\s+", " ", str(seg.get("text") or "")).strip()
        if not seg_text or seg_end <= seg_start:
            continue

        local_asr = v48_candidate_asr_stability(seg_start, seg_end, asr_stability_chunks)
        semantic = v48_semantic_asr_confidence(seg_text)
        anchor = v52_payoff_anchor_signal(seg_text, {
            "local_asr_confidence_label": local_asr.get("local_asr_confidence_label"),
            "semantic_asr_confidence_label": semantic.get("semantic_asr_confidence_label"),
        })
        if not anchor.get("v52_payoff_anchor_detected"):
            continue

        start = seg_start
        end = seg_end
        setup_added = False

        for j in range(max(0, idx - 2), idx):
            prev = segments[j]
            prev_start = round(safe_float(prev.get("start")), 2)
            prev_end = round(safe_float(prev.get("end"), prev_start), 2)
            if seg_start - prev_start > 10.0:
                continue
            prev_text = re.sub(r"\s+", " ", str(prev.get("text") or "")).strip()
            if not prev_text:
                continue
            prev_local_asr = v48_candidate_asr_stability(prev_start, prev_end, asr_stability_chunks)
            prev_semantic = v48_semantic_asr_confidence(prev_text)
            if str(prev_local_asr.get("local_asr_confidence_label") or "unknown") == "unstable":
                continue
            if str(prev_semantic.get("semantic_asr_confidence_label") or "unknown") == "degraded_semantics":
                continue
            if is_bad_transcript_clip(prev_text) or is_ad_segment(prev_text) or _v7_is_drift(prev_text):
                continue
            if _v7_topic_shift(prev_text, seg_text):
                continue
            if seg_end - prev_start > max_duration:
                continue
            start = prev_start
            setup_added = True
            break

        if seg_end - start < 10.0 and idx + 1 < len(segments):
            nxt = segments[idx + 1]
            next_start = round(safe_float(nxt.get("start")), 2)
            next_end = round(safe_float(nxt.get("end"), next_start), 2)
            next_text = re.sub(r"\s+", " ", str(nxt.get("text") or "")).strip()
            next_local_asr = v48_candidate_asr_stability(next_start, next_end, asr_stability_chunks)
            next_semantic = v48_semantic_asr_confidence(next_text)
            if (
                next_text
                and str(next_local_asr.get("local_asr_confidence_label") or "unknown") != "unstable"
                and str(next_semantic.get("semantic_asr_confidence_label") or "unknown") != "degraded_semantics"
                and not is_bad_transcript_clip(next_text)
                and not is_ad_segment(next_text)
                and not _v7_is_drift(next_text)
                and not _v7_topic_shift(seg_text, next_text)
                and next_end - start <= max_duration
            ):
                end = next_end

        window = (round(start, 2), round(end, 2))
        if window in seen_windows:
            continue
        seen_windows.add(window)

        text = get_nearby_text(segments, start, end, window=0)
        if not text or is_bad_transcript_clip(text) or is_ad_segment(text) or _v7_is_drift(text) or v38_text_quality_is_severe(text):
            continue
        local_asr = v48_candidate_asr_stability(start, end, asr_stability_chunks)
        semantic = v48_semantic_asr_confidence(text)
        if str(local_asr.get("local_asr_confidence_label") or "unknown") == "unstable":
            continue
        if str(semantic.get("semantic_asr_confidence_label") or "unknown") == "degraded_semantics":
            continue

        v43_bonus, v43_reasons = v43_hinglish_payoff_bonus(text)
        v44_bonus, v44_reasons, v44_confidence = v44_semantic_payoff_score(text)
        if v44_payoff_quality_block(text):
            payoff_bonus = 0
        else:
            payoff_bonus = max(
                v6_payoff_bonus(text),
                v7_better_payoff_bonus(text),
                v43_bonus,
                v44_bonus,
            )
        start_text, end_text = v50_repaired_text_boundaries(text)
        score_breakdown = {
            "hook_bonus": 0,
            "payoff_bonus": payoff_bonus,
            "context_quality": v7_context_quality_score(text),
            "start_text": start_text,
            "end_text": end_text,
            "local_asr_confidence_label": local_asr.get("local_asr_confidence_label"),
            "unstable_window_overlap_ratio": local_asr.get("unstable_window_overlap_ratio"),
            "chunk_confidence_score": local_asr.get("chunk_confidence_score"),
            "local_asr_reasons": local_asr.get("local_asr_reasons", [])[:5],
            "semantic_asr_confidence_label": semantic.get("semantic_asr_confidence_label"),
            "semantic_asr_corruption_score": semantic.get("semantic_asr_corruption_score"),
            "semantic_asr_reasons": semantic.get("semantic_asr_reasons", [])[:5],
            "v43_hinglish_payoff_bonus": v43_bonus,
            "v43_hinglish_payoff_reasons": v43_reasons[:5],
            "v44_semantic_payoff_score": v44_bonus,
            "v44_semantic_payoff_reasons": v44_reasons[:5],
            "v44_semantic_payoff_confidence": v44_confidence,
            **anchor,
            "v52_generated_from_payoff_anchor": True,
            "v52_anchor_window": [seg_start, seg_end],
        }
        clip = {
            "start": round(start, 2),
            "end": round(end, 2),
            "expanded_text": text,
            "source_text": seg_text,
            "title": v9_editorial_title(text, set()),
            "score_breakdown": score_breakdown,
        }
        clip["creator_qa_reasons"] = creator_qa_rejection_reasons(copy.deepcopy(clip), [])
        clip["v52_setup_added"] = setup_added
        generated.append(clip)
        if len(generated) >= max_candidates:
            break

    return generated


def v49_log_asr_segment_salvage(job_id, event, candidate_index, start, end, local_asr, salvage):
    local_asr = local_asr if isinstance(local_asr, dict) else {}
    salvage = salvage if isinstance(salvage, dict) else {}
    row = {
        "ts": time.time(),
        "job_id": job_id or "unknown",
        "event": event,
        "candidate_index": candidate_index,
        "start": round(safe_float(start), 2),
        "end": round(safe_float(end), 2),
        "local_asr_confidence_label": local_asr.get("local_asr_confidence_label"),
        "unstable_window_overlap_ratio": local_asr.get("unstable_window_overlap_ratio"),
        "segment_salvage_decision": salvage.get("segment_salvage_decision"),
        "decision_reason": salvage.get("segment_salvage_reason"),
        "repaired_window_required": salvage.get("repaired_window_required"),
        "repaired_window_available": salvage.get("repaired_window_available"),
        "quarantined_unstable_windows": salvage.get("quarantined_unstable_windows", [])[:5],
        "version": "v49_segment_salvage_v1",
    }
    try:
        os.makedirs("analytics", exist_ok=True)
        with (Path("analytics") / "asr_segment_salvage.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"⚠️ ASR segment salvage analytics logging failed: {e}")
    print(
        f"{event} "
        f"candidate_index={candidate_index} start={row['start']} end={row['end']} "
        f"local_asr_confidence_label={row['local_asr_confidence_label']} "
        f"unstable_overlap={row['unstable_window_overlap_ratio']} "
        f"decision={row['segment_salvage_decision']} reason={row['decision_reason']}"
    )


V48_SEMANTIC_ASR_CORRUPTION_PATTERNS = [
    r"तेंकलोडी",
    r"तेकनोलोजी",
    r"टेकनलोगी",
    r"टेकनलोडी",
    r"सम्यकन्ड़्टर",
    r"सेमिकंटर्टर",
    r"सेमिकंटर",
    r"सेमिकंटक्टर",
    r"सेम्मिकन्टर",
    r"एरर्जी",
    r"नेदल्ट्झो",
    r"नेदल्लेंच",
    r"नेदलन्ज",
    r"नेदर\s+लेंज",
    r"प्रदान\s+मंतरी",
    r"प्रदन\s+मंट्री",
    r"मुदी",
    r"देषों",
    r"पाँज",
    r"याप्रा?",
    r"हीट्रोजन",
    r"यूरेनिम",
    r"सावदखोर्या",
    r"सावट्कोरीया",
]


def v48_semantic_asr_repeated_garbage(tokens):
    repeated = []
    idx = 0
    while idx < len(tokens):
        run_end = idx + 1
        while run_end < len(tokens) and tokens[run_end] == tokens[idx]:
            run_end += 1
        if run_end - idx >= 4:
            repeated.append(tokens[idx])
        idx = run_end

    for ngram_size in (2, 3):
        counts = {}
        for pos in range(0, max(0, len(tokens) - ngram_size + 1)):
            gram = tuple(tokens[pos:pos + ngram_size])
            counts[gram] = counts.get(gram, 0) + 1
        for gram, count in counts.items():
            if count >= 4:
                repeated.append(" ".join(gram))

    return sorted(set(repeated))


def v48_semantic_asr_confidence(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    tokens = v48_asr_tokenize(text)
    replacement_chars = text.count("\ufffd") + text.count("ï¿½")
    corrupted_matches = []
    for pattern in V48_SEMANTIC_ASR_CORRUPTION_PATTERNS:
        corrupted_matches.extend(match.group(0) for match in re.finditer(pattern, text))

    repeated_garbage = v48_semantic_asr_repeated_garbage(tokens)
    repeated_malformed_syllables = len(re.findall(r"([\u0900-\u097F])\1{3,}", text))
    unique_ratio = len(set(tokens)) / max(len(tokens), 1) if tokens else 1.0
    top_token_ratio = max((tokens.count(token) for token in set(tokens)), default=0) / max(len(tokens), 1)

    corruption_score = 0
    corruption_score += min(36, replacement_chars * 10)
    corruption_score += min(44, len(corrupted_matches) * 8)
    corruption_score += min(36, len(repeated_garbage) * 12)
    corruption_score += min(24, repeated_malformed_syllables * 8)
    if len(tokens) >= 16 and unique_ratio < 0.38:
        corruption_score += int((0.38 - unique_ratio) * 100)
    if len(tokens) >= 12 and top_token_ratio >= 0.36:
        corruption_score += int(top_token_ratio * 35)
    corruption_score = min(100, corruption_score)

    reasons = []
    if replacement_chars:
        reasons.append(f"replacement_chars={replacement_chars}")
    if corrupted_matches:
        reasons.append(f"known_corrupt_terms={len(corrupted_matches)}")
    if repeated_garbage:
        reasons.append(f"repeated_garbage_phrases={len(repeated_garbage)}")
    if repeated_malformed_syllables:
        reasons.append(f"repeated_malformed_syllables={repeated_malformed_syllables}")
    if len(tokens) >= 16 and unique_ratio < 0.38:
        reasons.append(f"low_unique_token_ratio={round(unique_ratio, 3)}")
    if len(tokens) >= 12 and top_token_ratio >= 0.36:
        reasons.append(f"dominant_repeated_token_ratio={round(top_token_ratio, 3)}")
    if corrupted_matches:
        reasons.append("examples=" + ",".join(sorted(set(corrupted_matches))[:5]))

    if (
        corruption_score >= 42
        or replacement_chars > 0
        or len(corrupted_matches) >= 2
        or len(repeated_garbage) >= 2
    ):
        label = "degraded_semantics"
    elif corruption_score >= 20 or corrupted_matches or repeated_garbage:
        label = "borderline_semantics"
    else:
        label = "clean_semantics"

    return {
        "semantic_asr_confidence_label": label,
        "semantic_asr_corruption_score": corruption_score,
        "semantic_asr_reasons": reasons,
    }


def v48_semantic_asr_score_adjustment(semantic_asr):
    label = str(semantic_asr.get("semantic_asr_confidence_label") or "clean_semantics")
    score = safe_float(semantic_asr.get("semantic_asr_corruption_score"))
    if label == "clean_semantics":
        return 0
    if label == "borderline_semantics":
        return -4
    if label == "degraded_semantics" and score >= 80:
        return -18
    if label == "degraded_semantics" and score >= 60:
        return -14
    if label == "degraded_semantics":
        return -10
    return 0




V49_8_TARGETED_ASR_REPAIR_REPLACEMENTS = [
    (r"तेंकलोडी|तेकनोलोजी|टेकनलोगी|टेकनलोडी", "टेक्नोलॉजी"),
    (r"सम्यकन्ड़्टर|सेमिकंटर्टर|सेमिकंटर|सेमिकंटक्टर|सेम्मिकन्टर|सेमिकंटर्टर्टर्वाला", "सेमीकंडक्टर"),
    (r"एरर्जी", "एनर्जी"),
    (r"हीट्रोजन", "हाइड्रोजन"),
    (r"यूरेनिम", "यूरेनियम"),
    (r"नेदल्ट्झो|नेदल्लेंच|नेदलन्ज|नेदर\s+लेंज|नेदल\s+लेंज|नेदलाईंसनो", "नीदरलैंड्स"),
    (r"प्रदान\s+मंतरी|प्रदन\s+मंट्री", "प्रधानमंत्री"),
    (r"मुदी", "मोदी"),
    (r"देषों", "देशों"),
    (r"पाँज", "पांच"),
    (r"याप्रा?", "यात्रा"),
    (r"चिपस", "चिप्स"),
    (r"अस्तमाल|अच्टमाल", "इस्तेमाल"),
]


def v49_8_collapse_repeated_asr_tokens(text):
    tokens = str(text or "").split()
    if not tokens:
        return "", 0
    collapsed = []
    removed = 0
    idx = 0
    while idx < len(tokens):
        run_end = idx + 1
        while run_end < len(tokens) and tokens[run_end] == tokens[idx]:
            run_end += 1
        run_len = run_end - idx
        keep_count = 2 if run_len >= 4 else run_len
        collapsed.extend(tokens[idx:idx + keep_count])
        removed += max(0, run_len - keep_count)
        idx = run_end
    return " ".join(collapsed), removed


def v49_8_targeted_asr_repair(text, local_asr=None, allow_non_unstable=False):
    local_asr = local_asr if isinstance(local_asr, dict) else {}
    local_label = str(local_asr.get("local_asr_confidence_label") or "unknown")
    original_text = re.sub(r"\s+", " ", str(text or "")).strip()
    before = v48_semantic_asr_confidence(original_text)

    if local_label != "unstable" and not allow_non_unstable:
        return {
            "v49_8_repair_attempted": False,
            "v49_8_repair_scope": "skipped_non_unstable_window",
            "v49_8_repair_replacements": [],
            "v49_8_repair_removed_repeated_tokens": 0,
            "v49_8_repair_before_label": before["semantic_asr_confidence_label"],
            "v49_8_repair_before_score": before["semantic_asr_corruption_score"],
            "v49_8_repair_after_label": before["semantic_asr_confidence_label"],
            "v49_8_repair_after_score": before["semantic_asr_corruption_score"],
            "v49_8_repair_improved": False,
            "v49_8_repaired_window_available": False,
            "v49_8_repair_export_safe": False,
            "v49_8_repaired_text_preview": original_text[:220],
            "v49_8_repair_reasons": ["not_applied_to_clean_or_borderline_window"],
        }

    repaired = original_text.replace("\ufffd", " ").replace("ï¿½", " ")
    replacements = []
    for pattern, replacement in V49_8_TARGETED_ASR_REPAIR_REPLACEMENTS:
        repaired, count = re.subn(pattern, replacement, repaired)
        if count:
            replacements.append({
                "pattern": pattern,
                "replacement": replacement,
                "count": count,
            })

    repaired = re.sub(r"([\u0900-\u097F])\1{4,}", r"\1\1", repaired)
    repaired, removed_repeated_tokens = v49_8_collapse_repeated_asr_tokens(repaired)
    repaired = re.sub(r"\s+", " ", repaired).strip()
    after = v48_semantic_asr_confidence(repaired)
    improved = after["semantic_asr_corruption_score"] < before["semantic_asr_corruption_score"]
    strong_enough = (
        after["semantic_asr_confidence_label"] in {"clean_semantics", "borderline_semantics"}
        and after["semantic_asr_corruption_score"] <= 30
        and before["semantic_asr_confidence_label"] == "degraded_semantics"
    )

    reasons = []
    if replacements:
        reasons.append(f"known_term_replacements={sum(item['count'] for item in replacements)}")
    if removed_repeated_tokens:
        reasons.append(f"collapsed_repeated_tokens={removed_repeated_tokens}")
    if before["semantic_asr_corruption_score"] != after["semantic_asr_corruption_score"]:
        reasons.append(
            f"semantic_score_delta={before['semantic_asr_corruption_score'] - after['semantic_asr_corruption_score']}"
        )
    if not strong_enough:
        reasons.append("not_export_safe_without_audio_backed_repair")

    return {
        "v49_8_repair_attempted": True,
        "v49_8_repair_scope": "unstable_window_only",
        "v49_8_repair_replacements": replacements[:8],
        "v49_8_repair_removed_repeated_tokens": removed_repeated_tokens,
        "v49_8_repair_before_label": before["semantic_asr_confidence_label"],
        "v49_8_repair_before_score": before["semantic_asr_corruption_score"],
        "v49_8_repair_after_label": after["semantic_asr_confidence_label"],
        "v49_8_repair_after_score": after["semantic_asr_corruption_score"],
        "v49_8_repair_improved": improved,
        "v49_8_repaired_window_available": False,
        "v49_8_repair_export_safe": False,
        "v49_8_repaired_text_preview": repaired[:220],
        "v49_8_repair_reasons": reasons[:8],
    }


def v48_semantic_preference_should_win(winner, loser):
    winner = winner if isinstance(winner, dict) else {}
    loser = loser if isinstance(loser, dict) else {}
    winner_sb = winner.get("score_breakdown", {}) if isinstance(winner.get("score_breakdown"), dict) else {}
    loser_sb = loser.get("score_breakdown", {}) if isinstance(loser.get("score_breakdown"), dict) else {}
    winner_label = str(winner_sb.get("semantic_asr_confidence_label") or "")
    loser_label = str(loser_sb.get("semantic_asr_confidence_label") or "")

    if loser_label != "degraded_semantics":
        return False, ""
    if winner_label not in {"clean_semantics", "borderline_semantics"}:
        return False, ""

    winner_score = safe_float(winner.get("score"))
    loser_score = safe_float(loser.get("score"))
    score_gap = round(loser_score - winner_score, 2)
    threshold = 12.0 if winner_label == "clean_semantics" else 8.0
    if score_gap < 0:
        return True, f"{winner_label}_already_above_degraded"
    if score_gap <= threshold:
        return True, f"{winner_label}_within_{int(threshold)}_points_of_degraded"
    return False, ""


def v48_apply_semantic_clean_preference(clips):
    reranked = []
    for clip in clips:
        if not isinstance(clip.get("score_breakdown"), dict):
            clip["score_breakdown"] = {}
        clip_sb = clip["score_breakdown"]
        clip_sb.setdefault("semantic_preference_applied", False)
        clip_sb.setdefault("semantic_preference_reason", "")
        reranked.append(clip)
        index = len(reranked) - 1
        while index > 0:
            winner = reranked[index]
            loser = reranked[index - 1]
            should_win, reason = v48_semantic_preference_should_win(winner, loser)
            if not should_win:
                break

            if not isinstance(winner.get("score_breakdown"), dict):
                winner["score_breakdown"] = {}
            if not isinstance(loser.get("score_breakdown"), dict):
                loser["score_breakdown"] = {}
            winner_sb = winner["score_breakdown"]
            loser_sb = loser["score_breakdown"]
            winner_index = winner_sb.get("candidate_funnel_index")
            loser_index = loser_sb.get("candidate_funnel_index")
            winner_score = safe_float(winner.get("score"))
            loser_score = safe_float(loser.get("score"))
            winner_label = winner_sb.get("semantic_asr_confidence_label")
            loser_label = loser_sb.get("semantic_asr_confidence_label")

            winner_sb["semantic_preference_applied"] = True
            winner_sb["semantic_preference_reason"] = reason
            loser_sb.setdefault("semantic_preference_applied", False)
            loser_sb.setdefault("semantic_preference_reason", "")

            print(
                "SEMANTIC_CLEAN_PREFERENCE_WIN "
                f"winner_candidate_index={winner_index} loser_candidate_index={loser_index} "
                f"winner_label={winner_label} loser_label={loser_label} "
                f"winner_score={winner_score} loser_score={loser_score} "
                f"reason={reason}"
            )

            reranked[index - 1], reranked[index] = reranked[index], reranked[index - 1]
            index -= 1
    return reranked


def _v7_segment_energy(text):
    text = str(text or "").lower()
    score = 0

    hook = [
        "why", "how", "what", "who", "secret", "truth",
        "nobody", "suddenly", "mysterious", "targeted",
        "killing", "disappear", "dead body"
    ]
    stakes = [
        "betrayed", "exposed", "collapsed", "destroyed",
        "disappeared", "missing", "trapped", "panic",
        "humiliated", "lied", "caught", "warning",
        "dead", "killed", "fear", "danger",
        "threat", "meltdown", "crisis", "breakdown",
        "shocking", "unbelievable", "escape", "failure"
    ]
    payoff = [
        "this is why", "that is why", "therefore", "because of this",
        "the reason", "this means", "clearly", "in the end",
        "finally", "result", "this happened", "that is what"
    ]
    drift = [
        "here you can see", "posted on social media", "comment section",
        "let us understand", "basically", "first of all",
        "moving on", "next topic", "another topic", "now let's talk",
        "i want to show you"
    ]

    score += sum(4 for w in hook if w in text)
    score += sum(5 for w in stakes if w in text)
    score += sum(9 for w in payoff if w in text)
    score -= sum(14 for w in drift if w in text)

    if text.endswith(("?", "!", ".")):
        score += 5

    wc = len(text.split())
    if 7 <= wc <= 38:
        score += 5
    elif wc > 55:
        score -= 6

    return score


def _v7_is_drift(text):
    text = str(text or "").lower()
    return any(w in text for w in [
        "hello friends",
        "welcome back",
        "in today's video",
        "today's video",
        "do a detailed case study",
        "detailed case study",
        "case study",
        "we will discuss",
        "we are going to discuss",
        "here you can see",
        "posted on social media",
        "comment section",
        "let us understand",
        "basically",
        "moving on",
        "next topic",
        "another topic",
        "now let's talk",
        "i want to show you"
    ])


def _v7_topic_terms(text):
    text = str(text or "").lower()
    groups = {
        "sugar_india": ["sugar", "export ban", "india", "indian", "bharat"],
        "china_naming": ["china", "chinese", "country name", "naming", "renamed"],
        "finance": ["inflation", "trade deficit", "import duty", "market", "price", "gold"],
        "politics": ["election", "government", "minister", "party", "vote", "court"],
        "war": ["war", "missile", "drone", "border", "military", "nuclear"],
        "crime": ["murder", "missing", "police", "killed", "dead body", "case"],
    }
    return {name for name, terms in groups.items() if any(t in text for t in terms)}


def _v7_topic_shift(base_text, next_text):
    base_terms = _v7_topic_terms(base_text)
    next_terms = _v7_topic_terms(next_text)
    if not base_terms or not next_terms:
        return False
    return base_terms.isdisjoint(next_terms)


def _v7_is_payoff(text):
    text = str(text or "").lower()
    return any(w in text for w in [
        "this is why",
        "that is why",
        "therefore",
        "because of this",
        "the reason is",
        "this means",
        "clearly",
        "finally",
        "in the end",
        "result",
        "will tell the public",
        "situation will be more intense",
        "people are being targeted",
        "something bigger is happening"
    ])


def expand_story_clip(segments, hook_start, hook_end, min_len=1, max_len=60):
    segments = safe_dict_list(segments)

    hook_idx = None
    for i, seg in enumerate(segments):
        if safe_float(seg.get("start")) <= hook_start <= safe_float(seg.get("end")):
            hook_idx = i
            break

    if hook_idx is None:
        return round(hook_start, 2), round(min(hook_end, hook_start + max_len), 2)

    # âœ… BEST START: only useful setup, never random padding
    start = hook_start
    best_setup_score = -999
    best_setup_start = hook_start

    hook_text = str(segments[hook_idx].get("text", "")).strip()

    for j in range(max(0, hook_idx - 4), hook_idx + 1):
        tx = str(segments[j].get("text", "")).strip()
        low = tx.lower()

        if is_ad_segment(low) or _v7_is_drift(low):
            continue
        if j != hook_idx and _v7_topic_shift(tx, hook_text):
            continue

        setup_score = _v7_segment_energy(low)

        if any(w in low for w in [
            "for the first time",
            "what is happening",
            "problem",
            "suddenly",
            "mysterious",
            "betrayed",
            "exposed",
            "missing",
            "collapsed",
            "panic",
            "caught",
            "danger",
            "threat"
        ]):
            setup_score += 6

        if len(low.split()) < 4:
            setup_score -= 8

        if setup_score > best_setup_score:
            best_setup_score = setup_score
            best_setup_start = safe_float(segments[j].get("start"))

    if best_setup_score >= 3:
        start = best_setup_start

    # âœ… BEST END: scan forward, choose climax/payoff ending before drift
    best_end = hook_end
    best_end_score = -999
    last_safe_end = hook_end

    for i in range(hook_idx, len(segments)):
        seg = segments[i]
        tx = str(seg.get("text", "")).strip()
        low = tx.lower()
        seg_end = safe_float(seg.get("end"))

        if seg_end <= start:
            continue

        duration = seg_end - start
        if duration > max_len:
            break

        if is_ad_segment(low):
            break
        if i != hook_idx and _v7_topic_shift(hook_text, tx):
            break

        if any(x in low for x in [
            "now coming to", "moving to", "another topic",
            "on the other hand", "next topic", "now let's talk"
        ]):
            break

        if _v7_is_drift(low) and duration >= 10:
            break

        last_safe_end = seg_end

        end_score = _v7_segment_energy(low)

        # reward complete natural ending
        if low.endswith((".", "!", "?")):
            end_score += 8

        # reward payoff/climax
        if _v7_is_payoff(low):
            end_score += 22

        # prefer natural shorts range, but allow longer context
        if 12 <= duration <= 42:
            end_score += 8
        elif 42 < duration <= 60:
            end_score += 2
        elif duration < 6:
            end_score -= 10

        if end_score >= best_end_score and duration >= 6:
            best_end_score = end_score
            best_end = seg_end

        # hard stop when climax/payoff is found
        if _v7_is_payoff(low) and duration >= 10:
            best_end = seg_end
            break

    if best_end <= start:
        best_end = last_safe_end

    if best_end - start > max_len:
        best_end = start + max_len

    return round(start, 2), round(best_end, 2)


def is_strong_hook(text):
    text = str(text).lower()
    triggers = [
        "suddenly", "nobody", "you won't believe",
        "this is why", "what happened next",
        "truth is", "breaking", "biggest"
    ]
    # ðŸ”¥ V5.3 hook upgrade
    emotion_words = ['shocking','crazy','insane','unbelievable']
    curiosity_words = ['why','how','what','secret']
    
    if any(t in text for t in triggers):
        return True
    
    if any(e in text for e in emotion_words):
        return True
    
    if any(c in text for c in curiosity_words) and len(text.split()) < 12:
        return True
    
    return False

def is_weak_hook(text):
    text = str(text).lower()

    weak_patterns = [
        "hello", "welcome", "today we will",
        "in this video", "i am", "let's talk",
        "we are going to", "introduction"
    ]

    return any(w in text for w in weak_patterns)



def v17_empty_curiosity_bait(text):
    text = str(text or "").lower()
    words = text.split()

    empty_curiosity_phrases = [
        "what magic did you get to see here",
        "what magic did you see here",
        "let's do a detailed case study",
        "lets do a detailed case study",
        "do a detailed case study"
    ]
    if any(p in text for p in empty_curiosity_phrases):
        return True

    question_hits = sum(1 for w in ["why", "what", "how", "secret", "real", "actually", "hidden"] if w in text)

    real_stakes = [
        "exposed", "caught", "betrayed", "collapsed", "destroyed",
        "missing", "disappeared", "killed", "lost everything",
        "panic", "warning", "threat", "danger", "humiliated",
        "proof", "leaked", "lied", "scam", "fraud", "bankrupt",
        "employees lost", "investors panicked"
    ]

    stakes_hits = sum(1 for w in real_stakes if w in text)

    filler_phrases = [
        "real reason", "actually explained", "in this video",
        "what is the secret", "how is this real",
        "why did this happen"
    ]

    filler_hits = sum(1 for w in filler_phrases if w in text)

    return question_hits >= 3 and stakes_hits == 0 and filler_hits >= 1

def viral_quality_boost(text):
    text = str(text).lower()
    if v17_empty_curiosity_bait(text):
        return -8
    boost = 0

    # V6.1 UNIVERSAL SCORING
    curiosity = ["why", "how", "what", "secret", "truth", "reason", "explained", "actually", "real"]
    emotion = ["shocking", "crazy", "insane", "unbelievable", "danger", "failure", "mistake", "risk"]
    stakes = ["money", "career", "life", "future", "business", "health", "problem", "result"]

    # V15: no topic/nation-specific boost.
    # Viral quality must come from human stakes, curiosity, emotion, or payoff.
    geo = []

    curiosity_hits = sum(1 for w in curiosity if w in text)
    boost += min(8, curiosity_hits * 2)
    boost += min(20, sum(5 for w in emotion if w in text))
    boost += min(16, sum(4 for w in stakes if w in text))

    # V15: removed residual geopolitics/topic boost.
    boost += 0

    weak_openers = ["i will explain", "in today's video", "see what happened", "let's talk"]
    if any(w in text for w in weak_openers):
        boost -= 10

    return boost





def v6_emotional_momentum_bonus(text):
    text = str(text).lower()

    escalation_words = [
        "then", "suddenly", "after that", "but",
        "however", "meanwhile", "finally",
        "eventually", "because", "therefore"
    ]

    emotional_words = [
        "danger", "risk", "collapse", "threat",
        "war", "death", "crisis", "destroy",
        "panic", "fear", "humiliate"
    ]

    score = 0

    transitions = sum(1 for w in escalation_words if w in text)
    emotions = sum(1 for w in emotional_words if w in text)

    score += min(14, transitions * 3)
    score += min(16, emotions * 4)

    return min(score, 28)


def v6_dead_zone_penalty(text):
    text = str(text).lower()

    boring_patterns = [
        "hello friends",
        "welcome back",
        "in today's video",
        "let us understand",
        "basically",
        "simply",
        "as you know",
        "first of all",
        "historical context",
        "geopolitical implications",
        "strategic positioning",
        "in detail",
        "detailed explanation",
        "analysis",
        "background",
        "we will discuss",
        "topic is related",
        "coming back to the topic"
    ]

    penalty = 0

    for p in boring_patterns:
        if p in text:
            penalty -= 14

    word_count = len(text.split())

    # low-information filler
    if word_count > 120:
        penalty -= 16

    return penalty


def v6_creator_pacing_bonus(text):
    text = str(text).lower()

    short_sentences = text.count(".")
    question_count = text.count("?")

    momentum_words = [
        "why", "how", "but", "because",
        "then", "suddenly", "now"
    ]

    momentum_hits = sum(1 for w in momentum_words if w in text)

    score = 0
    score += min(10, short_sentences * 2)
    score += min(8, question_count * 4)
    score += min(16, momentum_hits * 2)

    return min(score, 24)


def v6_payoff_bonus(text):
    text = str(text).lower()

    payoff_words = [
        "this is why",
        "that means",
        "therefore",
        "finally",
        "in the end",
        "result was",
        "because of this"
    ]

    score = sum(5 for w in payoff_words if w in text)

    return min(score, 20)


def v6_story_arc_bonus(text):
    text = str(text).lower()
    bonus = 0

    setup_words = ["because", "reason", "context", "what happened", "why"]
    tension_words = ["threat", "war", "danger", "crisis", "attack", "collapse", "survival", "humiliate"]
    payoff_words = ["therefore", "that means", "so", "result", "conclusion", "this is why"]

    if any(w in text for w in setup_words):
        bonus += 8
    if any(w in text for w in tension_words):
        bonus += 14
    if any(w in text for w in payoff_words):
        bonus += 8

    if len(text.split()) > 80:
        bonus += 6

    return min(bonus, 30)


def v6_hook_aligned_start(segments, start, end):
    # Move start slightly closer to a strong sentence, but keep context.
    best = start
    for seg in segments:
        st = safe_float(seg.get("start"))
        tx = str(seg.get("text", "")).lower()

        if st < start or st > min(end, start + 14):
            continue

        strong = any(w in tx for w in [
            "why", "how", "what", "secret", "truth",
            "threat", "war", "crisis", "attack", "danger",
            "america", "russia", "ukraine", "iran", "nato"
        ])

        weak = any(w in tx for w in [
            "i will explain", "in today's video", "hello", "welcome"
        ])

        if strong and not weak:
            # clean start: do not rewind into previous sentence tail
            best = st
            break

    return round(best, 2)


def v6_clean_unique_title(title, source_text, used_titles):
    title = str(title or "").strip()
    text = str(source_text or "").lower()

    weak_titles = [
        "this changed everything",
        "this changed everything overnight",
        "what happened next is crazy",
        "why this is happening right now",
        "this will shock you"
    ]

    weak_phrase_titles = [
        "then it will",
        "see what happened",
        "what is the",
        "i will explain",
        "in today's video",
        "tell me",
        "explained",
        "was shown",
        "difficult it is",
        "look at this"
    ]

    if len(title.split()) < 4 or title.lower() in weak_titles or any(p in title.lower() for p in weak_phrase_titles):
        if any(w in text for w in ["why", "reason"]):
            title = "The Real Reason Behind This"
        elif any(w in text for w in ["mistake", "wrong", "failure"]):
            title = "This Mistake Changes Everything"
        elif any(w in text for w in ["secret", "truth"]):
            title = "The Truth Nobody Talks About"
        elif any(w in text for w in ["how"]):
            title = "How This Actually Works"
        elif any(w in text for w in ["threat", "crisis", "danger", "risk"]):
            title = "The Real Threat Nobody Is Ignoring"
        elif "story" in text or "sister" in text or "family" in text:
            title = "The Full Story Behind This"
        elif "war" in text or "attack" in text:
            title = "This Situation Changed Everything"
        else:
            title = "What Happens Next Changes Everything"

    base = title
    n = 2
    while title in used_titles:
        title = f"{base} Part {n}"
        n += 1

    used_titles.add(title)
    return title


def v7_creator_title_from_context(existing_title, context_text, niche="general"):
    text = str(context_text or "").lower()
    existing = str(existing_title or "").strip()

    weak_titles = [
        "how this actually works",
        "what happens next changes everything",
        "this situation changed everything",
        "the real reason behind this",
        "this will shock you",
        "untitled viral clip"
    ]

    # V15: removed geopolitics-locked title rules.
    # Titles should be based on human reaction/story angle, not country/topic nouns.

    if niche == "finance_economics":
        if "trade deficit" in text or "à¤Ÿà¥à¤°à¥‡à¤¡ à¤¡à¥‡à¤«à¤¿à¤¸à¤¿à¤Ÿ" in text:
            return "Trade Deficit Ka Real Impact"
        if "import duty" in text or "à¤‡à¤®à¥à¤ªà¥‹à¤°à¥à¤Ÿ à¤¡à¥à¤¯à¥‚à¤Ÿà¥€" in text or "gold" in text or "à¤—à¥‹à¤²à¥à¤¡" in text:
            return "Gold Import Duty Se Prices Kyun Badhenge"
        if "export ban" in text or "sugar" in text or "à¤¶à¥à¤—à¤°" in text or "à¤¸à¥à¤—à¤°" in text:
            return "Sugar Export Ban Ka Market Impact"
        if "inflation" in text or "à¤‡à¤¨à¥à¤«à¥à¤²à¥‡à¤¶à¤¨" in text or "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ" in text:
            return "Inflation Risk Ab Badhta Dikh Raha Hai"

    # ðŸ”¥ V15 human-reaction titles
    if "exposed" in text and ("live" in text or "stream" in text):
        return "She Exposed Everything Live"
    if "lost 40 million" in text or "40 million dollars" in text:
        return "He Lost $40 Million In One Day"
    if "disappearing" in text or "disappeared" in text or "vanished" in text:
        if "village" in text:
            return "People Started Vanishing From This Village"
        return "People Started Disappearing Mysteriously"
    if "collapsed overnight" in text:
        return "The Startup Collapsed Overnight"
    if "if i ever get killed" in text or "would never kill myself" in text:
        return "He Predicted His Own Death"

    # If existing title is weak/generic, replace it
    if existing.lower() in weak_titles or "part " in existing.lower():
        if "why" in text or "reason" in text:
            return "The Real Reason This Is Happening"
        if "mysterious" in text or "mystery" in text:
            return "The Mystery Nobody Can Explain"
        if "targeted" in text:
            return "Why These People Are Being Targeted"
        if any(x in text for x in ["danger", "risk", "survival", "collapse", "loss"]):
            return "This Situation Is Getting Worse Fast"
        return "The Moment That Changed Everything"

    return existing


def v7_context_quality_score(text):
    text = str(text or "").lower()
    if v17_empty_curiosity_bait(text):
        return -12
    score = 0

    strong = [
        "why", "how", "who",
        "betrayed", "exposed", "missing",
        "danger", "threat", "collapse",
        "panic", "fear", "warning",
        "lied", "caught", "killed",
        "shocking", "unbelievable",
        "humiliated", "destroyed"
    ]
    payoff = [
        "this is why", "that is why", "the reason",
        "because of this", "clearly", "finally",
        "in the end", "situation will be more intense",
        "people are being targeted",
        "will tell the public"
    ]
    weak = [
        "here you can see", "posted on social media",
        "comment section", "like and share",
        "subscribe", "let us understand",
        "basically", "i want to show you"
    ]

    score += min(30, sum(3 for w in strong if w in text))
    score += min(24, sum(6 for w in payoff if w in text))
    score -= min(30, sum(10 for w in weak if w in text))

    wc = len(text.split())
    if 18 <= wc <= 110:
        score += 10
    elif wc < 8:
        score -= 15
    elif wc > 150:
        score -= 10

    return score


def v7_better_payoff_bonus(text):
    text = str(text or "").lower()
    payoff_hits = [
        "this is why", "that is why", "therefore",
        "because of this", "the reason is", "this means",
        "clearly", "finally", "in the end",
        "will tell the public", "situation will be more intense",
        "people are being targeted",
        "something bigger is happening",
        "all these deaths are happening"
    ]
    return min(28, sum(7 for p in payoff_hits if p in text))


def v43_hinglish_payoff_bonus(text):
    text = str(text or "").lower()
    normalized = re.sub(r"\s+", " ", text).strip()
    reasons = []
    score = 0

    consequence = [
        "isliye", "isi wajah se", "yeh wajah hai", "ye wajah hai",
        "nateeja", "natija", "result", "conclusion", "akhirkar",
        "akhir mein", "end mein",
    ]
    explanation = [
        "matlab yeh", "matlab ye", "iska matlab", "simple baat",
        "seedhi baat", "sidhi baat",
    ]
    lesson = [
        "seekh", "lesson", "yaad rakho", "samajhna padega",
        "samajhna hoga",
    ]
    reveal = [
        "asli baat", "sach yeh hai", "sach ye hai", "twist",
        "pata chala",
    ]
    judgment = [
        "galti yahi thi", "galti yehi thi", "problem yahi hai",
        "problem yehi hai", "solution yahi hai", "solution yehi hai",
    ]
    consequence_support = [
        "because", "kyunki", "kyonki", "wajah", "reason", "impact",
        "badal", "change", "loss", "risk", "problem", "solution",
        "galti", "sach", "seekh", "lesson", "yaad", "samajh",
    ]

    def add_hits(phrases, reason, points):
        nonlocal score
        hits = [p for p in phrases if p in normalized]
        if hits:
            score += points
            reasons.append(reason)

    add_hits(explanation, "hinglish_explanation_payoff", 7)
    add_hits(lesson, "hinglish_lesson_payoff", 7)
    add_hits(reveal, "hinglish_reveal_payoff", 7)
    add_hits(judgment, "hinglish_judgment_payoff", 8)

    consequence_hits = [p for p in consequence if p in normalized]
    if consequence_hits:
        supported = any(p in normalized for p in consequence_support)
        if supported or len(consequence_hits) >= 2:
            score += 6
            reasons.append("hinglish_consequence_payoff")

    # Do not let isolated filler words such as "matlab" or "result" carry a clip.
    if not reasons:
        return 0, []

    words = normalized.split()
    if len(words) < 14:
        return 0, []

    if v17_empty_curiosity_bait(normalized) or _v7_is_drift(normalized):
        return 0, []

    return min(score, 18), reasons[:5]


def v44_semantic_payoff_score(text):
    text = str(text or "").lower()
    normalized = re.sub(r"\s+", " ", text).strip()
    words = normalized.split()
    reasons = []

    if len(words) < 28 or len(words) > 180:
        return 0, [], "none"
    if v17_empty_curiosity_bait(normalized) or _v7_is_drift(normalized):
        return 0, [], "none"
    if is_bad_transcript_clip(normalized):
        return 0, [], "none"

    unresolved_teasers = [
        "what happened next",
        "what happens next",
        "you won't believe",
        "watch till",
        "sabse important part",
        "aage kya hua",
        "uske baad kya hua",
        "phir kya hua",
    ]
    if any(phrase in normalized for phrase in unresolved_teasers):
        return 0, [], "none"

    meta_filler_hits = sum(1 for phrase in [
        "nothing actually gets explained",
        "never tells",
        "big words",
        "sounding important",
        "conclusion phrases",
        "repeated",
        "motivational words repeat",
        "sirf motivational words",
        "koi result saamne nahi aata",
    ] if phrase in normalized)
    if meta_filler_hits >= 2:
        return 0, [], "none"
    if any(phrase in normalized for phrase in [
        "aage kya milega",
        "result ke liye aage",
        "abhi kisi ko nahi pata",
        "koi result saamne nahi aata",
        "sirf motivational words",
    ]):
        return 0, [], "none"

    sentences = [s.strip() for s in re.split(r"[.!?\n\u0964]+|à¥¤", normalized) if s.strip()]
    if len(sentences) < 2:
        return 0, [], "none"

    early = " ".join(sentences[: max(1, len(sentences) // 3)])
    late = " ".join(sentences[max(1, (len(sentences) * 2) // 3):])
    middle_late = " ".join(sentences[max(1, len(sentences) // 3):])

    setup_terms = [
        "why", "how", "what", "question", "problem", "risk", "danger",
        "mystery", "secret", "claim", "expect", "thought", "believed",
        "kyun", "kaise", "kya", "sawal", "problem", "risk", "darr",
        "raaz", "sach", "lagta", "socha", "maan", "agar",
        "struggle", "hard work", "mehnat", "mehnad", "mahnat",
        "mehnet", "wait", "intezar", "intzar", "samay", "time",
        "tayyar", "taiyar", "taiyari", "skillset", "skill set",
        "मेहनत", "महनत", "मेहनेद", "मेहनद", "स्ट्रगल", "इंतजार",
        "इन्तदार", "समय", "टाइम", "तैयार", "तैयारी",
    ]
    resolution_terms = [
        "realized", "understood", "found", "revealed", "proved", "changed",
        "lost", "won", "failed", "saved", "stopped", "decided", "became",
        "samjha", "samajh", "pata", "nikla", "badal", "mila", "gaya",
        "haar", "jeet", "bach", "ruk", "bana", "aaya",
        "milega", "milegi", "milta", "success", "safalta", "result",
        "reward", "payoff", "surrender", "sir jhuka", "sar jhuka",
        "मिलेगा", "मिलेगी", "मिला", "सक्सेस", "सक्स", "सफलता",
        "नतीजा", "सरेंडर", "सर झुका", "सिर झुका",
    ]
    contrast_terms = [
        "but", "however", "instead", "actually", "not", "never", "only",
        "lekin", "magar", "par", "asal", "nahi", "sirf", "balki",
    ]
    causal_terms = [
        "because", "so", "therefore", "made", "led", "caused", "impact",
        "kyunki", "isliye", "toh", "wajah", "asar", "natija", "nateeja",
    ]
    reveal_terms = [
        "truth", "secret", "revealed", "found out", "turns out", "real",
        "sach", "raaz", "pata chala", "asli", "nikla",
    ]
    answer_terms = [
        "called", "named", "known as", "was brought", "started", "became",
        "used", "ruled", "unified", "opened", "created", "happened",
        "kehte", "bola", "naam", "shuru", "hua", "huyi", "bana",
    ]
    takeaway_terms = [
        "lesson", "remember", "learned", "takeaway", "meaning",
        "seekh", "yaad", "samajhna", "matlab",
    ]
    effort_terms = [
        "hard work", "mehnat", "mehnad", "mahnat", "mehnet", "struggle",
        "work on yourself", "kaam kar lo", "khud pe", "skillset",
        "मेहनत", "महनत", "मेहनेद", "मेहनद", "स्ट्रगल", "काम कर",
        "खुद पे", "स्किलसेट",
    ]
    reward_terms = [
        "milega", "milegi", "milta", "success", "safalta", "reward",
        "payoff", "surrender", "sir jhuka", "sar jhuka", "badla",
        "revenge", "us din", "that day",
        "मिलेगा", "मिलेगी", "मिला", "सक्सेस", "सक्स", "सफलता",
        "बदला", "रिवेंज", "र्वेंज", "उस दिन", "सरेंडर", "सर झुका",
        "सिर झुका",
    ]
    preparation_terms = [
        "tayyar", "taiyar", "taiyari", "ready", "prepare", "preparation",
        "skillset", "skill set", "weapon", "darwaza", "door opens",
        "तैयार", "तैयारी", "स्किलसेट", "दरवाजा", "दरवाज़ा",
    ]

    def has_any(blob, terms):
        return any(term in blob for term in terms)

    motivational_setup = has_any(early + " " + middle_late, effort_terms)
    setup_present = has_any(early, setup_terms) or "?" in normalized or motivational_setup
    resolution_late = has_any(late, resolution_terms)
    contrast_shift = has_any(middle_late, contrast_terms) and setup_present
    causal_resolution = has_any(middle_late, causal_terms) and resolution_late
    reveal_shift = has_any(middle_late, reveal_terms) and setup_present
    answer_landing = (
        ("?" in normalized or has_any(early, ["why", "how", "what", "kyun", "kaise", "kya"]))
        and has_any(late, answer_terms)
        and (resolution_late or reveal_shift or causal_resolution)
    )
    takeaway_late = has_any(late, takeaway_terms) and setup_present
    effort_reward_landing = (
        motivational_setup
        and has_any(middle_late, reward_terms)
        and (
            has_any(middle_late, ["milega", "milegi", "success", "safalta", "surrender", "revenge", "badla"])
            or has_any(middle_late, ["मिलेगा", "मिलेगी", "सक्सेस", "सक्स", "सफलता", "सरेंडर", "रिवेंज", "र्वेंज", "बदला"])
        )
    )
    preparation_future_landing = (
        has_any(early + " " + middle_late, preparation_terms)
        and has_any(middle_late, reward_terms)
        and has_any(middle_late, ["door", "darwaza", "दरवाजा", "दरवाज़ा", "skillset", "स्किलसेट", "ready", "तैयार"])
    )
    that_day_landing = (
        has_any(middle_late, ["that day", "us din", "उस दिन"])
        and has_any(middle_late, reward_terms)
    )

    if setup_present:
        reasons.append("semantic_setup_present")
    if resolution_late:
        reasons.append("semantic_late_resolution")
    if contrast_shift:
        reasons.append("semantic_contrast_resolution")
    if causal_resolution:
        reasons.append("semantic_causal_resolution")
    if reveal_shift:
        reasons.append("semantic_reveal_shift")
    if answer_landing:
        reasons.append("semantic_answer_landing")
    if takeaway_late:
        reasons.append("semantic_takeaway_landing")
    if effort_reward_landing:
        reasons.append("semantic_effort_reward_landing")
    if preparation_future_landing:
        reasons.append("semantic_preparation_future_landing")
    if that_day_landing:
        reasons.append("semantic_that_day_landing")

    # Fail closed: a payoff needs a setup plus at least two independent landing cues.
    landing_cues = sum([
        bool(resolution_late),
        bool(contrast_shift),
        bool(causal_resolution),
        bool(reveal_shift),
        bool(answer_landing),
        bool(takeaway_late),
        bool(effort_reward_landing),
        bool(preparation_future_landing),
        bool(that_day_landing),
    ])
    if not setup_present or landing_cues < 2:
        return 0, [], "none"
    if "?" in normalized and not (resolution_late or reveal_shift or causal_resolution):
        return 0, [], "none"
    if (
        (effort_reward_landing or that_day_landing or preparation_future_landing)
        and not (
            resolution_late
            or contrast_shift
            or causal_resolution
            or reveal_shift
            or answer_landing
            or takeaway_late
        )
        and landing_cues < 3
    ):
        return 0, [], "none"

    score = 0
    score += 4 if setup_present else 0
    score += 5 if resolution_late else 0
    score += 4 if contrast_shift else 0
    score += 4 if causal_resolution else 0
    score += 5 if reveal_shift else 0
    score += 4 if answer_landing else 0
    score += 4 if takeaway_late else 0
    score += 5 if effort_reward_landing else 0
    score += 4 if preparation_future_landing else 0
    score += 3 if that_day_landing else 0

    if landing_cues >= 4:
        confidence = "high"
    elif landing_cues == 3:
        confidence = "medium"
    else:
        confidence = "low"

    return min(score, 14), reasons[:6], confidence


def v44_payoff_quality_block(text):
    normalized = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if not normalized:
        return True

    meta_filler_hits = sum(1 for phrase in [
        "nothing actually gets explained",
        "never tells",
        "big words",
        "sounding important",
        "conclusion phrases",
        "repeated",
        "motivational words repeat",
        "sirf motivational words",
        "koi result saamne nahi aata",
    ] if phrase in normalized)
    if meta_filler_hits >= 2:
        return True
    if any(phrase in normalized for phrase in [
        "aage kya milega",
        "result ke liye aage",
        "abhi kisi ko nahi pata",
        "koi result saamne nahi aata",
        "sirf motivational words",
    ]):
        return True

    unresolved_teasers = [
        "what happened next",
        "what happens next",
        "you won't believe",
        "watch till",
        "sabse important part",
        "aage kya hua",
        "uske baad kya hua",
        "phir kya hua",
    ]
    return any(phrase in normalized for phrase in unresolved_teasers)


def v7_stronger_dead_zone_penalty(text):
    text = str(text or "").lower()
    bad = [
        "here you can see",
        "posted on social media",
        "comment section",
        "i want to show you",
        "let us understand",
        "basically",
        "first of all",
        "you can see",
        "like and share",
        "subscribe"
    ]
    return -min(35, sum(9 for b in bad if b in text))



def _v8_first_last_segment_text(segments, start, end):
    first = ""
    last = ""

    for seg in safe_dict_list(segments):
        st = safe_float(seg.get("start"))
        ee = safe_float(seg.get("end"))
        tx = str(seg.get("text", "")).strip()

        if not tx:
            continue

        if ee > start and st < end:
            if not first:
                first = tx
            last = tx

    return first, last


def _v8_bad_start(text):
    text = str(text or "").strip().lower()
    bad = [
        "hello friends", "welcome back", "in today's video",
        "today's video", "do a detailed case study",
        "detailed case study", "we will discuss",
        "and ", "but ", "so ", "after that",
        "because ", "which ", "that ", "who ",
        "here you can see", "i want to show you",
        "as you can see", "let us understand",
        "basically", "first of all"
    ]
    return any(text.startswith(x) for x in bad)


def _v8_bad_end(text):
    text = str(text or "").strip().lower()
    bad = [
        "i want to show you",
        "here you can see",
        "posted on social media",
        "comment section",
        "let us understand",
        "moving on",
        "next topic",
        "now let's talk",
        "as you can see",
        "basically"
    ]
    if any(x in text for x in bad):
        return True

    # weak continuation ending
    if text.endswith(("and", "but", "because", "so", "then")):
        return True

    return False


def _v8_word_set(text):
    stop = {
        "the","a","an","and","or","but","is","are","was","were","to","of",
        "in","on","for","with","this","that","these","those","they","their",
        "has","have","had","will","would","could","should","from","about",
        "what","when","where","why","how","you","your","we","our"
    }
    words = []
    for w in str(text or "").lower().replace(",", " ").replace(".", " ").split():
        w = "".join(ch for ch in w if ch.isalnum())
        if len(w) >= 4 and w not in stop:
            words.append(w)
    return set(words)


def _v8_context_overlap(a, b):
    A = _v8_word_set(a)
    B = _v8_word_set(b)
    if not A or not B:
        return 0.0
    return len(A & B) / max(1, min(len(A), len(B)))


def v8_natural_editor_grade(context_text, start_text, end_text):
    ctx = str(context_text or "").lower()
    start = str(start_text or "").strip().lower()
    end = str(end_text or "").strip().lower()

    score = 20
    reasons = []

    if _v8_bad_start(start):
        score -= 25
        reasons.append("weak_start")

    if _v8_bad_end(end):
        score -= 35
        reasons.append("weak_ending")

    payoff = [
        "this is why", "that is why", "therefore", "because of this",
        "the reason", "this means", "clearly", "finally", "in the end",
        "will tell the public", "situation will be more intense",
        "people are being targeted", "outside force"
    ]

    if any(p in ctx for p in payoff):
        score += 20
        reasons.append("payoff_present")

    strong = [
        "betrayed", "exposed", "caught", "panic",
        "danger", "fear", "collapse", "killing",
        "missing", "destroyed", "warning",
        "lied", "humiliated", "trapped"
    ]

    hits = sum(1 for w in strong if w in ctx)
    score += min(8, hits * 2)

    weak = [
        "i want to show you", "here you can see", "posted on social media",
        "let us understand", "basically", "comment section", "subscribe",
        "like and share"
    ]

    weak_hits = sum(1 for w in weak if w in ctx)
    score -= min(35, weak_hits * 12)

    wc = len(ctx.split())
    if 10 <= wc <= 130:
        score += 10
    elif wc < 8:
        score -= 25
        reasons.append("too_short")
    elif wc > 170:
        score -= 15
        reasons.append("too_verbose")

    score = max(min(score, 60), -40)
    return score, reasons


def v8_diverse_title(title, context_text, used_titles):
    text = str(context_text or "").lower()
    title = str(title or "Untitled Viral Clip").strip()

    candidates = []

    if "killed" in text or "killing" in text:
        candidates.append("Why People Are Suddenly Dying")

    if "targeted" in text:
        candidates.append("Why Someone Is Being Targeted")

    if "report" in text and "public" in text:
        candidates.append("The Report That Could Escalate Everything")

    candidates.append(title)

    for c in candidates:
        if c and c not in used_titles:
            used_titles.add(c)
            return c

    base = title.replace(" Part 2", "").replace(" Part 3", "").strip()
    n = 2
    new_title = f"{base} Angle {n}"
    while new_title in used_titles:
        n += 1
        new_title = f"{base} Angle {n}"

    used_titles.add(new_title)
    return new_title



def v9_start_hook_score(text):
    text = str(text or "").strip().lower()
    score = 0

    bad_openers = [
        "hello friends", "welcome back", "in today's video",
        "today's video", "do a detailed case study",
        "detailed case study", "we will discuss",
        "what magic did you get to see here",
        "what magic did you see here",
        "let's do a detailed case study",
        "lets do a detailed case study",
        "what happens", "the second point", "made in",
        "you should", "we don't want", "increase your",
        "i don't know", "a meeting was held",
        "first of all", "basically", "here you can see",
        "i want to show you"
    ]

    if any(text.startswith(x) for x in bad_openers):
        score -= 35

    # ðŸ”¥ V13.5:
    # reward curiosity/emotion, NOT just geopolitics nouns.
    strong_openers = [
        "why", "how", "who", "what if", "nobody",
        "suddenly", "for the first time",
        "can you imagine",
        "just 40 years ago",
        "back then",
        "at that time",
        "in the next",
        "how could this be possible",
        "the reason", "this is why",
        "if i ever get killed",
        "never kill myself",
        "what happened next",
        "mysterious",
        "terrifying",
        "disappeared",
        "caught on camera",
        "secret",
        "panic"
    ]

    score += min(24, sum(8 for w in strong_openers if w in text))

    curiosity = ["why", "how", "who", "what", "mystery", "secret", "threat", "targeted"]
    score += min(20, sum(5 for w in curiosity if w in text))

    wc = len(text.split())
    if 6 <= wc <= 28:
        score += 10
    elif wc < 3:
        score -= 30
    elif wc > 45:
        score -= 10

    if text.endswith("?"):
        score += 8

    return score


def v9_end_payoff_score(text):
    text = str(text or "").strip().lower()
    score = 0

    bad_endings = [
        "depending on the capacity",
        "i want to show you",
        "here you can see",
        "posted on social media",
        "comment section",
        "what happens",
        "i will explain",
        "in today's video",
        "let us understand",
        "basically"
    ]

    if any(x in text for x in bad_endings):
        score -= 45

    weak_creator_endings = [
        "we will have to see",
        "coming time",
        "if i talk about",
        "now coming back",
        "overall",
        "basically",
        "context of india",
        "very important thing"
    ]

    if any(x in text for x in weak_creator_endings):
        score -= 40

    payoff = [
        "this is why", "that is why", "therefore",
        "because of this", "the reason is", "this means",
        "clearly", "finally", "in the end",
        "the next number", "will become more intense",
        "situation will be more intense",
        "people are being targeted",
        "outside force", "threat", "survival",
        "nuclear weapon", "drone power"
    ]

    score += min(30, sum(10 for w in payoff if w in text))

    if text.endswith((".", "!", "?")):
        score += 8

    if text.endswith("?"):
        score += 8

    wc = len(text.split())
    if 5 <= wc <= 36:
        score += 8
    elif wc > 55:
        score -= 8

    return score


def v9_clean_start_time(segments, start, end):
    best_start = start
    best_score = -999

    for seg in safe_dict_list(segments):
        st = safe_float(seg.get("start"))
        ee = safe_float(seg.get("end"))
        tx = str(seg.get("text", "")).strip()

        if st < start or st > min(end, start + 14):
            continue

        if is_ad_segment(tx) or _v8_bad_start(tx):
            continue

        score = v9_start_hook_score(tx)

        # prefer not starting too late unless clearly better
        delay = max(0, st - start)
        score -= min(10, delay * 0.8)

        if score > best_score:
            best_score = score
            best_start = st

    if best_score >= 8:
        return round(best_start, 2)

    return round(start, 2)



def v11_is_hard_bad_ending(text):
    text = str(text or "").strip().lower()

    bad = [
        "thank you for watching",
        "thanks for watching",
        "like and subscribe",
        "subscribe",
        "comment section",
        "link in the description",
        "now we will have to see",
        "we will have to see what happens",
        "so yeah",
        "overall",
        "with this note",
        "end of the video",
        "moving on",
        "now coming back to the topic",
        "coming back to the topic"
    ]

    return any(x in text for x in bad)


def v9_clean_end_time(segments, start, end):
    best_end = None
    best_score = -999

    for seg in safe_dict_list(segments):
        ee = safe_float(seg.get("end"))
        tx = str(seg.get("text", "")).strip()
        low = tx.lower()

        if ee <= start or ee > end:
            continue

        duration = ee - start
        if duration < 8:
            continue

        if is_ad_segment(tx):
            break

        if v11_is_hard_bad_ending(tx):
            continue

        if _v8_bad_end(tx) or _v7_is_drift(tx):
            continue

        score = v9_end_payoff_score(tx)

        if any(p in low for p in [
            "this is why", "that's why", "that is why",
            "nobody expected", "never kill myself",
            "everything changed", "outside force",
            "people are being targeted",
            "massive international crisis",
            "americans have never seen anything like this",
            "this is very mysterious"
        ]):
            score += 35

        if 12 <= duration <= 42:
            score += 12
        elif 42 < duration <= 60:
            score += 4

        if score > best_score:
            best_score = score
            best_end = ee

    if best_end is None:
        fallback = None
        for seg in safe_dict_list(segments):
            ee = safe_float(seg.get("end"))
            tx = str(seg.get("text", "")).strip()

            if ee <= start or ee > end:
                continue

            if is_ad_segment(tx) or v11_is_hard_bad_ending(tx) or _v8_bad_end(tx) or _v7_is_drift(tx):
                continue

            fallback = ee

        if fallback is not None:
            return round(fallback, 2)

        return round(end, 2)

    return round(best_end, 2)


def v9_true_creator_grade(context_text, start_text, end_text):
    ctx = str(context_text or "").lower()
    st = str(start_text or "").lower()
    en = str(end_text or "").lower()

    score = 0
    reasons = []

    start_score = v9_start_hook_score(st)
    end_score = v9_end_payoff_score(en)

    score += start_score
    score += end_score

    if start_score < 5:
        reasons.append("weak_creator_start")
    if end_score < 5:
        reasons.append("weak_creator_ending")

    # ðŸ”¥ V12.5 creator-retention:
    # reward emotional storytelling, not just geopolitics topics.
    high_retention = [
        "why", "how", "who",
        "suddenly", "killed", "danger",
        "mystery", "secret",
        "if i ever get killed",
        "never kill myself",
        "nobody expected",
        "what happened next",
        "believe me",
        "terrifying",
        "disappeared",
        "collapsed",
        "caught",
        "exposed",
        "panic"
    ]

    hits = sum(1 for w in high_retention if w in ctx)
    score += min(35, hits * 4)

    weak_context = [
        "i will explain this in today's video",
        "here you can see",
        "i want to show you",
        "posted on social media",
        "comment section",
        "let us understand",
        "basically"
    ]

    weak_hits = sum(1 for w in weak_context if w in ctx)
    if weak_hits:
        score -= min(45, weak_hits * 18)
        reasons.append("weak_context_drift")

    boring_info = [
        "we will discuss",
        "strategic implications",
        "geopolitical developments",
        "historical context",
        "in detail",
        "detailed explanation",
        "analysis",
        "background"
    ]

    boring_hits = sum(1 for w in boring_info if w in ctx)
    if boring_hits:
        score -= min(50, boring_hits * 18)
        reasons.append("boring_info_density")

    wc = len(ctx.split())

    # ðŸ”¥ V12.5:
    # short clips can still be elite if emotionally strong.
    if 12 <= wc <= 125:
        score += 18

    elif 7 <= wc < 12:
        if any(p in ctx for p in [
            "nobody expected",
            "what happened next",
            "never kill myself",
            "if i ever get killed",
            "collapsed overnight",
            "shocked the stadium",
            "changed the entire match",
            "mysteriously disappeared",
            "disappeared from",
            "gets crazier",
            "was insane",
            "before disappearing"
        ]):
            score += 24
        else:
            score -= 6
            reasons.append("slightly_short_context")

    elif wc < 7:
        if any(p in ctx for p in [
            "what happened next",
            "was insane",
            "mysteriously disappeared",
            "nobody expected",
            "never kill myself",
            "collapsed overnight",
            "shocked the stadium"
        ]):
            score += 18
        else:
            score -= 20
            reasons.append("too_short_context")

    elif wc > 165:
        score -= 18
        reasons.append("too_verbose_context")

    score = max(min(score, 70), -40)
    return score, reasons




# =========================================================
# ðŸ”¥ V10 UNIVERSAL CREATOR DNA ENGINE â€” PHASE 1
# =========================================================

def v10_detect_creator_niche(text):
    """
    V18.7 Universal Niche DNA Detector
    Multilingual + creator-content aware.
    Keeps serious politics/news separate from war/geopolitics.
    """
    text = str(text or "").lower()

    niche_map = {
        "finance_economics": [
            "inflation", "deflation", "trade deficit", "current account deficit",
            "import duty", "export duty", "tariff", "export ban", "sugar export",
            "global demand", "consumer price", "price shock", "market price",
            "commodity", "gold purchase", "gold import", "rupee", "dollar",
            "à¤‡à¤¨à¥à¤«à¥à¤²à¥‡à¤¶à¤¨", "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ", "à¤Ÿà¥à¤°à¥‡à¤¡ à¤¡à¥‡à¤«à¤¿à¤¸à¤¿à¤Ÿ", "à¤‡à¤®à¥à¤ªà¥‹à¤°à¥à¤Ÿ à¤¡à¥à¤¯à¥‚à¤Ÿà¥€",
            "à¤à¤•à¥à¤¸à¤ªà¥‹à¤°à¥à¤Ÿ", "à¤à¤•à¥à¤¸à¤ªà¥‹à¤°à¥à¤Ÿ à¤¬à¥ˆà¤¨", "à¤Ÿà¥ˆà¤°à¤¿à¤«", "à¤—à¥à¤²à¥‹à¤¬à¤² à¤¡à¤¿à¤®à¤¾à¤‚à¤¡",
            "à¤•à¤‚à¤œà¥à¤¯à¥‚à¤®à¤°", "à¤®à¤¾à¤°à¥à¤•à¥‡à¤Ÿ", "à¤•à¥€à¤®à¤¤", "à¤¦à¤¾à¤®", "à¤—à¥‹à¤²à¥à¤¡", "à¤°à¥à¤ªà¤¯à¤¾", "à¤¡à¥‰à¤²à¤°"
        ],

        "politics_news": [
            "bjp","congress","election","vote","voting","poll","campaign",
            "parliament","government","minister","prime minister","chief minister",
            "modi","rahul gandhi","mamata","kejriwal","west bengal","bengal",
            "bangal","india","state election","party","opposition","democracy",
            "policy","law","court","supreme court","high court",
            "à¤­à¤¾à¤œà¤ªà¤¾","à¤¬à¥€à¤œà¥‡à¤ªà¥€","à¤•à¤¾à¤‚à¤—à¥à¤°à¥‡à¤¸","à¤šà¥à¤¨à¤¾à¤µ","à¤µà¥‹à¤Ÿ","à¤®à¤¤à¤¦à¤¾à¤¨","à¤¸à¤°à¤•à¤¾à¤°",
            "à¤°à¤¾à¤œà¤¨à¥€à¤¤à¤¿","à¤ªà¥à¤°à¤§à¤¾à¤¨à¤®à¤‚à¤¤à¥à¤°à¥€","à¤®à¥à¤–à¥à¤¯à¤®à¤‚à¤¤à¥à¤°à¥€","à¤®à¤‚à¤¤à¥à¤°à¥€","à¤®à¤®à¤¤à¤¾","à¤®à¥‹à¤¦à¥€",
            "à¤¬à¤‚à¤—à¤¾à¤²","à¤­à¤¾à¤°à¤¤","à¤ªà¤¾à¤°à¥à¤Ÿà¥€","à¤µà¤¿à¤ªà¤•à¥à¤·","à¤²à¥‹à¤•à¤¸à¤­à¤¾","à¤µà¤¿à¤§à¤¾à¤¨à¤¸à¤­à¤¾","à¤•à¤¾à¤¨à¥‚à¤¨",
            "à¤…à¤¦à¤¾à¤²à¤¤","à¤¸à¥à¤ªà¥à¤°à¥€à¤® à¤•à¥‹à¤°à¥à¤Ÿ"
        ],

        "geopolitics": [
            "war","missile","drone","nato","ukraine","russia","china","iran",
            "israel","palestine","gaza","military","defense","army","border",
            "sanction","oil","trade war","nuclear","terror","terrorist",
            "à¤¯à¥à¤¦à¥à¤§","à¤®à¤¿à¤¸à¤¾à¤‡à¤²","à¤¡à¥à¤°à¥‹à¤¨","à¤šà¥€à¤¨","à¤°à¥‚à¤¸","à¤ˆà¤°à¤¾à¤¨","à¤‡à¤œà¤°à¤¾à¤‡à¤²",
            "à¤«à¤¿à¤²à¤¿à¤¸à¥à¤¤à¥€à¤¨","à¤¸à¥‡à¤¨à¤¾","à¤¬à¥‰à¤°à¥à¤¡à¤°","à¤¸à¥€à¤®à¤¾","à¤†à¤¤à¤‚à¤•","à¤ªà¤°à¤®à¤¾à¤£à¥"
        ],

        "finance_business": [
            "money","business","startup","investment","investor","market",
            "stock","income","profit","loss","revenue","sales","company",
            "brand","funding","valuation","ipo","bank","loan","tax",
            "à¤ªà¥ˆà¤¸à¤¾","à¤¬à¤¿à¤œà¤¨à¥‡à¤¸","à¤¨à¤¿à¤µà¥‡à¤¶","à¤•à¤®à¤¾à¤ˆ","à¤®à¥à¤¨à¤¾à¤«à¤¾","à¤¨à¥à¤•à¤¸à¤¾à¤¨","à¤¬à¤¾à¤œà¤¾à¤°",
            "à¤•à¤‚à¤ªà¤¨à¥€","à¤¬à¥ˆà¤‚à¤•","à¤²à¥‹à¤¨","à¤Ÿà¥ˆà¤•à¥à¤¸","à¤¶à¥‡à¤¯à¤°"
        ],

        "education_explainer": [
            "why","how","what is","explained","reason","history","science",
            "study","exam","learn","concept","facts","lesson","tutorial",
            "à¤•à¥à¤¯à¥‹à¤‚","à¤•à¥ˆà¤¸à¥‡","à¤•à¥à¤¯à¤¾ à¤¹à¥ˆ","à¤•à¤¾à¤°à¤£","à¤‡à¤¤à¤¿à¤¹à¤¾à¤¸","à¤µà¤¿à¤œà¥à¤žà¤¾à¤¨","à¤ªà¤¢à¤¼à¤¾à¤ˆ",
            "à¤à¤—à¥à¤œà¤¾à¤®","à¤¸à¥€à¤–","à¤¸à¤®à¤à¤¿à¤","à¤¤à¤¥à¥à¤¯"
        ],

        "tech_ai": [
            "ai","artificial intelligence","chatgpt","openai","google","apple",
            "microsoft","software","app","coding","python","server","gpu",
            "cloud","robot","automation","startup tech",
            "à¤à¤†à¤ˆ","à¤Ÿà¥‡à¤•","à¤¸à¥‰à¤«à¥à¤Ÿà¤µà¥‡à¤¯à¤°","à¤à¤ª","à¤•à¥‹à¤¡à¤¿à¤‚à¤—","à¤¸à¤°à¥à¤µà¤°","à¤œà¥€à¤ªà¥€à¤¯à¥‚","à¤•à¥à¤²à¤¾à¤‰à¤¡"
        ],

        "crime_mystery": [
            "crime","murder","killed","dead body","police","case","arrest",
            "missing","mystery","secret","hidden","conspiracy","investigation",
            "à¤…à¤ªà¤°à¤¾à¤§","à¤¹à¤¤à¥à¤¯à¤¾","à¤®à¤°à¥à¤¡à¤°","à¤²à¤¾à¤¶","à¤ªà¥à¤²à¤¿à¤¸","à¤—à¤¿à¤°à¤«à¥à¤¤à¤¾à¤°","à¤—à¤¾à¤¯à¤¬",
            "à¤°à¤¹à¤¸à¥à¤¯","à¤¸à¤¾à¤œà¤¿à¤¶","à¤œà¤¾à¤‚à¤š"
        ],

        "sports": [
            "football","cricket","match","player","goal","score","final",
            "world cup","ipl","wicket","run","captain","team",
            "à¤•à¥à¤°à¤¿à¤•à¥‡à¤Ÿ","à¤®à¥ˆà¤š","à¤–à¤¿à¤²à¤¾à¤¡à¤¼à¥€","à¤—à¥‹à¤²","à¤¸à¥à¤•à¥‹à¤°","à¤«à¤¾à¤‡à¤¨à¤²","à¤†à¤ˆà¤ªà¥€à¤à¤²",
            "à¤µà¤¿à¤•à¥‡à¤Ÿ","à¤°à¤¨","à¤•à¤ªà¥à¤¤à¤¾à¤¨","à¤Ÿà¥€à¤®"
        ],

        "self_improvement": [
            "discipline","motivation","focus","mindset","success","dopamine",
            "habit","productivity","confidence","hard work","failure",
            "à¤®à¥‹à¤Ÿà¤¿à¤µà¥‡à¤¶à¤¨","à¤…à¤¨à¥à¤¶à¤¾à¤¸à¤¨","à¤«à¥‹à¤•à¤¸","à¤¸à¤«à¤²à¤¤à¤¾","à¤†à¤¦à¤¤","à¤®à¥‡à¤¹à¤¨à¤¤","à¤¹à¤¾à¤°"
        ],

        "health_fitness": [
            "health","fitness","gym","workout","diet","weight loss","protein",
            "doctor","disease","medicine","sleep","mental health",
            "à¤¸à¥à¤µà¤¾à¤¸à¥à¤¥à¥à¤¯","à¤«à¤¿à¤Ÿà¤¨à¥‡à¤¸","à¤œà¤¿à¤®","à¤¡à¤¾à¤‡à¤Ÿ","à¤µà¤œà¤¨","à¤¡à¥‰à¤•à¥à¤Ÿà¤°","à¤¬à¥€à¤®à¤¾à¤°à¥€",
            "à¤¦à¤µà¤¾","à¤¨à¥€à¤‚à¤¦"
        ],

        "creator_drama": [
            "exposed","cheating","lied","caught","betrayed","scandal","fight",
            "controversy","roast","trolled","apology","relationship",
            "à¤à¤•à¥à¤¸à¤ªà¥‹à¤œ","à¤à¥‚à¤ ","à¤§à¥‹à¤–à¤¾","à¤ªà¤•à¤¡à¤¼à¤¾","à¤¸à¥à¤•à¥ˆà¤‚à¤¡à¤²","à¤²à¤¡à¤¼à¤¾à¤ˆ","à¤µà¤¿à¤µà¤¾à¤¦",
            "à¤Ÿà¥à¤°à¥‹à¤²","à¤®à¤¾à¤«à¥€"
        ],

        "podcast_story": [
            "bro","literally","podcast","conversation","story","once","then",
            "suddenly","i remember","he said","she said",
            "interview","guest","host","i asked","they said","realized",
            "à¤•à¤¹à¤¾à¤¨à¥€","à¤«à¤¿à¤°","à¤…à¤šà¤¾à¤¨à¤•","à¤‰à¤¸à¤¨à¥‡ à¤•à¤¹à¤¾","à¤®à¥ˆà¤‚à¤¨à¥‡ à¤•à¤¹à¤¾","à¤¬à¥‹à¤²à¤¾",
            "à¤¬à¤¤à¤¾à¤¯à¤¾","à¤ªà¥‚à¤›à¤¾","à¤¯à¤¾à¤¦","à¤¬à¤¾à¤¤","à¤•à¤¿à¤¸à¥à¤¸à¤¾","à¤‡à¤‚à¤Ÿà¤°à¤µà¥à¤¯à¥‚"
        ],

        "comedy_entertainment": [
            "funny","laugh","hilarious","meme","crazy","wtf","joke","prank",
            "movie","film","actor","actress","bollywood","song",
            "à¤®à¤œà¥‡à¤¦à¤¾à¤°","à¤¹à¤‚à¤¸à¥€","à¤®à¥€à¤®","à¤®à¤œà¤¾à¤•","à¤ªà¥à¤°à¥ˆà¤‚à¤•","à¤«à¤¿à¤²à¥à¤®","à¤à¤•à¥à¤Ÿà¤°",
            "à¤¬à¥‰à¤²à¥€à¤µà¥à¤¡","à¤—à¤¾à¤¨à¤¾"
        ]
    }

    scores = {}
    for niche, words in niche_map.items():
        score = 0
        for w in words:
            if w in text:
                # longer phrases are more intentional than tiny tokens
                score += 2 if len(w) >= 6 else 1
        scores[niche] = score

    if scores.get("finance_economics", 0) >= 2:
        if scores["finance_economics"] >= scores.get("politics_news", 0) - 1:
            return "finance_economics"

    best = max(scores, key=scores.get)

    if scores[best] <= 0:
        return "general"

    return best


def v10_emotional_spike_score(text):
    text = str(text or "").lower()
    if v17_empty_curiosity_bait(text):
        return 0

    spike_words = [
        "suddenly","instantly","panic","destroyed",
        "collapsed","shocking","crazy","insane",
        "dangerous","caught","exposed","threat",
        "nobody expected","turned out","humiliated",
        "if i ever get killed","never kill myself",
        "disappeared","dead body","mysterious",
        "outside force","targeted","target",
        "they will kill","he warned","believe me",
        "americans have never seen anything like this"
    ]

    finance_spike_words = [
        "inflation risk", "price shock", "consumer price", "import duty",
        "trade deficit", "export ban", "global demand", "market price",
        "policy impact", "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ", "à¤‡à¤¨à¥à¤«à¥à¤²à¥‡à¤¶à¤¨", "à¤•à¥€à¤®à¤¤", "à¤¦à¤¾à¤®",
        "à¤Ÿà¥à¤°à¥‡à¤¡ à¤¡à¥‡à¤«à¤¿à¤¸à¤¿à¤Ÿ", "à¤‡à¤®à¥à¤ªà¥‹à¤°à¥à¤Ÿ à¤¡à¥à¤¯à¥‚à¤Ÿà¥€", "à¤—à¥à¤²à¥‹à¤¬à¤² à¤¡à¤¿à¤®à¤¾à¤‚à¤¡"
    ]

    curiosity_words = [
        "why","how","what happens","secret",
        "truth","reason","actually"
    ]

    score = 0

    score += min(35, sum(5 for w in spike_words if w in text))
    score += min(18, sum(4 for w in finance_spike_words if w in text))
    score += min(18, sum(3 for w in curiosity_words if w in text))

    if "?" in text:
        score += 8

    return min(score, 50)


def v10_replayability_score(text):
    text = str(text or "").lower()
    if v17_empty_curiosity_bait(text):
        return -10

    score = 0

    replay_patterns = [
        "wait",
        "listen",
        "look carefully",
        "can you imagine",
        "just 40 years ago",
        "back then",
        "at that time",
        "in the next",
        "how could this be possible",
        "the real reason",
        "nobody talks about",
        "watch this",
        "this is why",
        "think about this",
        "here's the problem",
        "bro",
        "dude",
        "literally",
        "no way",
        "what happened next",
        "you won't believe",
        "insane",
        "crazy",
        "imagine",
        "believe me",
        "if i ever get killed",
        "never kill myself",
        "nobody expected"
    ]

    finance_replay_patterns = [
        "this means", "this is why", "because", "impact", "risk",
        "inflation", "trade deficit", "import duty", "export ban",
        "global demand", "market price", "à¤‡à¤¸à¤²à¤¿à¤", "à¤®à¤¤à¤²à¤¬", "à¤•à¥à¤¯à¥‹à¤‚à¤•à¤¿",
        "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ", "à¤•à¥€à¤®à¤¤", "à¤¦à¤¾à¤®"
    ]

    for p in replay_patterns:
        if p in text:
            score += 8

    for p in finance_replay_patterns:
        if p in text:
            score += 5

    # reward spoken creator cadence
    if "..." in text or "â€”" in text:
        score += 6

    if text.count("?") >= 1:
        score += 6

    word_count = len(text.split())

    boring_patterns = [
        "what magic did you get to see here",
        "what magic did you see here",
        "let's do a detailed case study",
        "lets do a detailed case study",
        "historical context",
        "geopolitical implications",
        "strategic positioning",
        "in detail",
        "detailed explanation",
        "analysis",
        "background",
        "let us understand",
        "we will discuss"
    ]

    score -= sum(8 for p in boring_patterns if p in text)

    if word_count > 140:
        score -= 18

    if text.count(".") > 12:
        score -= 10

    return max(min(score, 50), -35)



def v15_human_reaction_score(text):
    """
    V15 Human Reaction Engine:
    Scores creator-native human triggers, not topics.
    This is intentionally capped to avoid score inflation.
    """
    text = str(text or "").lower()
    score = 0
    reasons = []

    betrayal = [
        "betray", "betrayed", "cheated", "backstab", "lied to",
        "double crossed", "fake friend", "trusted him", "trusted her"
    ]

    humiliation = [
        "humiliated", "embarrassed", "insulted", "mocked",
        "laughed at", "roasted", "called out", "publicly"
    ]

    exposure = [
        "exposed", "leaked", "caught", "revealed", "truth came out",
        "during the live stream", "on live", "camera caught", "recorded"
    ]

    financial_disaster = [
        "lost money", "lost everything", "lost 40 million", "million dollars",
        "bankrupt", "collapsed overnight", "one mistake", "destroyed his company",
        "wiped out", "went broke"
    ]

    finance_policy_stakes = [
        "inflation risk", "price shock", "consumer price", "import duty",
        "trade deficit", "export ban", "global demand", "market price",
        "policy impact", "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ", "à¤‡à¤¨à¥à¤«à¥à¤²à¥‡à¤¶à¤¨", "à¤•à¥€à¤®à¤¤", "à¤¦à¤¾à¤®",
        "à¤Ÿà¥à¤°à¥‡à¤¡ à¤¡à¥‡à¤«à¤¿à¤¸à¤¿à¤Ÿ", "à¤‡à¤®à¥à¤ªà¥‹à¤°à¥à¤Ÿ à¤¡à¥à¤¯à¥‚à¤Ÿà¥€", "à¤—à¥à¤²à¥‹à¤¬à¤² à¤¡à¤¿à¤®à¤¾à¤‚à¤¡"
    ]

    mystery_loss = [
        "disappearing", "disappeared", "vanished", "missing",
        "mysteriously", "nobody found", "never came back"
    ]

    disbelief = [
        "nobody expected", "nobody believed", "everyone was shocked",
        "people couldn't believe", "what happened next", "insane",
        "unbelievable", "shocking"
    ]

    emotional_contradiction = [
        "smiling but", "looked normal but", "said nothing but",
        "pretended", "acted normal", "behind the scenes"
    ]

    buckets = [
        ("betrayal", betrayal, 10),
        ("humiliation", humiliation, 10),
        ("exposure", exposure, 12),
        ("financial_disaster", financial_disaster, 12),
        ("finance_policy_stakes", finance_policy_stakes, 10),
        ("mystery_loss", mystery_loss, 12),
        ("disbelief", disbelief, 8),
        ("emotional_contradiction", emotional_contradiction, 8),
    ]

    for name, words, weight in buckets:
        hits = sum(1 for w in words if w in text)
        if hits:
            score += min(weight + hits * 3, weight + 8)
            reasons.append(name)

    # Short explosive statements should not be treated as weak just because they are concise.
    words = text.split()
    if 5 <= len(words) <= 14 and score >= 12:
        score += 8
        reasons.append("short_explosive")

    # Replay psychology: the user wants to know "how/why/what happened next".
    if any(x in text for x in [
        "how did", "why did", "what happened", "what happens next",
        "then everything changed", "the truth", "the real reason"
    ]):
        score += 8
        reasons.append("replay_question")

    # Cap hard to prevent V15 from reviving boring clips alone.
    score = max(0, min(45, score))
    return score, reasons


def v10_creator_retention_score(start_text, end_text):
    st = str(start_text or "").lower()
    en = str(end_text or "").lower()

    score = 0

    strong_start = [
        "why","how","what","nobody",
        "suddenly","secret","imagine",
        "à¤•à¥à¤¯à¥‹à¤‚","à¤•à¥ˆà¤¸à¥‡","à¤•à¥à¤¯à¤¾","à¤…à¤—à¤°"
    ]

    weak_start = [
        "hello","welcome","today we",
        "in this video","let us understand"
    ]

    strong_end = [
        "this is why",
        "that's why",
        "everything changed",
        "and then",
        "the result was",
        "nobody expected",
        "à¤‡à¤¸à¤²à¤¿à¤","à¤®à¤¤à¤²à¤¬","à¤•à¥€à¤®à¤¤","à¤¦à¤¾à¤®","à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ"
    ]

    weak_end = [
        "that's it",
        "thank you",
        "so yeah",
        "overall"
    ]

    score += sum(6 for w in strong_start if w in st)
    score -= sum(8 for w in weak_start if w in st)

    score += sum(8 for w in strong_end if w in en)
    score -= sum(10 for w in weak_end if w in en)

    return max(min(score, 45), -25)


def _v9_title_case_phrase(phrase):
    words = []
    small_words = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "of", "on", "or", "the", "to", "vs", "with"}
    for i, word in enumerate(str(phrase or "").split()):
        clean = word.strip(" ,.:;!?\"'()[]{}")
        if not clean:
            continue
        low = clean.lower()
        if low == "ai":
            words.append("AI")
        elif clean.isupper() and len(clean) > 1:
            words.append(clean)
        elif i > 0 and low in small_words:
            words.append(low)
        else:
            words.append(clean[:1].upper() + clean[1:].lower())
    return " ".join(words).strip()


def _v9_grounded_title_from_text(context_text):
    raw = re.sub(r"\s+", " ", str(context_text or "")).strip()
    if not raw:
        return "Untitled Clip"

    anchor_words = [
        "inflation", "trade deficit", "import duty", "export ban", "market",
        "price", "gold", "sugar", "startup", "business", "company", "money",
        "election", "government", "court", "policy", "war", "border",
        "china", "russia", "iran", "israel", "gaza", "ai", "cricket",
        "football", "match", "goal", "fitness", "discipline", "focus",
        "doctor", "health", "murder", "missing", "police", "secret",
        "mystery", "exposed", "caught", "collapsed", "risk", "threat",
        "reason", "problem", "result", "impact"
    ]
    filler_starts = {
        "and", "but", "so", "then", "because", "which", "that", "who",
        "basically", "actually", "now", "like"
    }

    title_blocked = [
        "hello friends", "welcome back", "in today's video",
        "today's video", "do a detailed case study",
        "detailed case study", "we will discuss"
    ]
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", raw)
        if s.strip() and not any(b in s.lower() for b in title_blocked)
    ]
    if not sentences:
        sentences = [raw]

    best = sentences[0]
    best_score = -1
    for sentence in sentences:
        low = sentence.lower()
        words = re.findall(r"[A-Za-z0-9$]+", sentence)
        if len(words) < 3:
            continue
        score = sum(3 for a in anchor_words if a in low)
        score += min(4, sum(1 for w in words if any(ch.isdigit() for ch in w)))
        score += min(4, sum(1 for w in words if len(w) > 2 and w[:1].isupper()))
        if score > best_score:
            best_score = score
            best = sentence

    words = re.findall(r"[A-Za-z0-9$]+", best)
    while words and words[0].lower() in filler_starts:
        words.pop(0)
    if not words:
        words = re.findall(r"[A-Za-z0-9$]+", raw)

    low_words = [w.lower() for w in words]
    anchor_idx = next((i for i, w in enumerate(low_words) if any(a in w for a in anchor_words)), 0)
    start = max(0, anchor_idx - 2)
    end = min(len(words), start + 8)
    if end - start < 4:
        start = 0
        end = min(len(words), 8)

    phrase = " ".join(words[start:end]).strip()
    return _v9_title_case_phrase(phrase) or "Untitled Clip"


def _v9_unique_title(title, used_titles):
    base = str(title or "Untitled Clip").strip()[:70].strip() or "Untitled Clip"
    title = base
    n = 2
    while title in used_titles:
        title = f"{base} #{n}"
        n += 1
    used_titles.add(title)
    return title


def v9_editorial_title(context_text, used_titles):
    return _v9_unique_title(_v9_grounded_title_from_text(context_text), used_titles)

def smooth_clip_end(segments, end, buffer=4.0):
    # Extend only when the next segment helps finish the thought.
    base_text = ""
    for seg in safe_dict_list(segments):
        if safe_float(seg.get("end")) <= end:
            base_text = str(seg.get("text", "")).strip().lower()

    for seg in safe_dict_list(segments):
        st = safe_float(seg.get("start"))
        tx = str(seg.get("text", "")).strip().lower()
        if st >= end and st <= end + buffer:
            if is_ad_segment(tx) or _v7_is_drift(tx) or v11_is_hard_bad_ending(tx):
                return end
            if _v7_topic_shift(base_text, tx):
                return end
            if any(x in tx for x in [
                "therefore", "this means", "that means", "which means",
                "because of this", "result", "impact", "risk", "price",
                "policy", "à¤‡à¤¸à¤²à¤¿à¤", "à¤®à¤¤à¤²à¤¬", "à¤¨à¤¤à¥€à¤œà¤¾", "à¤•à¥€à¤®à¤¤", "à¤¦à¤¾à¤®"
            ]):
                return safe_float(seg.get("end"))
            if tx.startswith(("and ", "but ", "so ", "then ", "because ")):
                return safe_float(seg.get("end"))
    return end


def v39_niche_story_quality(text, start_text, end_text, niche):
    text = str(text or "").lower()
    start_text = str(start_text or "").strip().lower()
    end_text = str(end_text or "").strip().lower()
    niche = str(niche or "general")

    score = 0
    reasons = []

    explainer_niche = niche in {"finance_economics", "education_explainer"}
    mid_start_terms = (
        "and ", "but ", "then ", "which ", "that ", "who ",
        "because of", "which means", "so if"
    )
    if explainer_niche:
        mid_start_terms = (
            "and ", "but ", "then ", "which ", "that ", "who "
        )

    mid_thought_start = start_text.startswith(mid_start_terms)
    mid_thought_end = end_text.endswith(("and", "but", "because", "so", "then"))

    if mid_thought_start:
        score -= 4 if explainer_niche else 18
        reasons.append("mid_thought_start")
    if mid_thought_end:
        score -= 4 if explainer_niche else 6
        reasons.append("mid_thought_end")

    niche_payoff = {
        "finance_economics": [
            "this means", "that means", "which means", "impact", "risk",
            "price shock", "inflation", "trade deficit", "import duty",
            "policy impact", "market price", "consumer price", "à¤®à¤¤à¤²à¤¬",
            "à¤‡à¤¸à¤²à¤¿à¤", "à¤¨à¤¤à¥€à¤œà¤¾", "à¤•à¥€à¤®à¤¤", "à¤¦à¤¾à¤®", "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ"
        ],
        "geopolitics": [
            "this means", "therefore", "because of this", "threat",
            "risk", "sanction", "border", "military", "nuclear", "à¤‡à¤¸à¤²à¤¿à¤"
        ],
        "education_explainer": [
            "this means", "that means", "which means", "the reason",
            "because", "therefore", "example", "concept", "lesson",
            "à¤®à¤¤à¤²à¤¬", "à¤•à¤¾à¤°à¤£", "à¤‡à¤¸à¤²à¤¿à¤"
        ],
        "podcast_story": [
            "then", "and then", "suddenly", "he said", "she said",
            "i realized", "that was the moment", "à¤«à¤¿à¤°", "à¤…à¤šà¤¾à¤¨à¤•"
        ],
    }

    payoff_terms = niche_payoff.get(niche, []) + [
        "this is why", "that is why", "finally", "in the end", "result"
    ]
    end_hits = sum(1 for p in payoff_terms if p in end_text)
    context_hits = sum(1 for p in payoff_terms if p in text and p not in end_text)
    payoff_score = min(28, end_hits * 9 + min(8, context_hits * 2))
    if payoff_score:
        score += payoff_score
        reasons.append("niche_payoff")

    dead_terms = [
        "here you can see", "posted on social media", "comment section",
        "let us understand", "basically", "first of all", "moving on",
        "next topic", "now let's talk"
    ]
    dead_hits = sum(1 for p in dead_terms if p in text)
    if dead_hits:
        score -= min(36, dead_hits * 12)
        reasons.append("dead_zone_leakage")

    wc = len(text.split())
    if 18 <= wc <= 115:
        score += 10
        reasons.append("creator_paced_length")
    elif wc > 155:
        score -= 4
        reasons.append("overextended_context")

    return score, reasons


# =========================================================
# ðŸ”¥ V19 Universal Niche-Native Creator Engine
# =========================================================

V19_INFORMATIONAL_NICHES = {
    "politics_news", "geopolitics", "finance_business", "finance_economics",
    "education_explainer", "tech_ai", "health_fitness",
    "crime_mystery", "documentary", "commentary", "analysis",
    "news", "education", "politics"
}

V19_STRICT_CREATOR_NICHES = {
    "creator_drama", "comedy_entertainment",
    "sports", "self_improvement"
}

V40_STORY_NICHES = {
    "podcast_story", "education_explainer", "geopolitics", "politics_news",
    "finance_economics", "finance_business", "crime_mystery",
    "self_improvement", "tech_ai", "health_fitness", "general"
}

def v19_text_hits(text, words):
    text = str(text or "").lower()
    return sum(1 for w in words if w in text)

def v19_niche_native_signals(text, niche):
    text = str(text or "").lower()
    niche = str(niche or "general")

    politics_tension = [
        "bjp","congress","election","vote","government","minister",
        "opposition","democracy","court","law","policy","bengal",
        "à¤­à¤¾à¤œà¤ªà¤¾","à¤¬à¥€à¤œà¥‡à¤ªà¥€","à¤•à¤¾à¤‚à¤—à¥à¤°à¥‡à¤¸","à¤šà¥à¤¨à¤¾à¤µ","à¤µà¥‹à¤Ÿ","à¤¸à¤°à¤•à¤¾à¤°",
        "à¤°à¤¾à¤œà¤¨à¥€à¤¤à¤¿","à¤®à¤‚à¤¤à¥à¤°à¥€","à¤µà¤¿à¤ªà¤•à¥à¤·","à¤¬à¤‚à¤—à¤¾à¤²","à¤­à¤¾à¤°à¤¤","à¤œà¤¿à¤®à¥à¤®à¥‡à¤¦à¤¾à¤°",
        "à¤à¥‚à¤ ","à¤ªà¤¿à¤›à¤¡à¤¼à¤¾","à¤®à¤œà¤¬à¥‚à¤¤"
    ]

    explainer_tension = [
        "why","how","reason","because","truth","this means",
        "à¤•à¥à¤¯à¥‹à¤‚","à¤•à¥ˆà¤¸à¥‡","à¤•à¤¾à¤°à¤£","à¤®à¤¤à¤²à¤¬","à¤¸à¤š","à¤œà¤¿à¤®à¥à¤®à¥‡à¤¦à¤¾à¤°"
    ]

    conflict_tension = [
        "against","vs","fight","accuse","blame","failed","collapse",
        "à¤–à¤¿à¤²à¤¾à¤«","à¤²à¤¡à¤¼à¤¾à¤ˆ","à¤†à¤°à¥‹à¤ª","à¤œà¤¿à¤®à¥à¤®à¥‡à¤¦à¤¾à¤°","à¤«à¥‡à¤²","à¤¨à¥à¤•à¤¸à¤¾à¤¨","à¤à¥‚à¤ "
    ]

    payoff_terms = [
        "this is why","that is why","therefore","because","result",
        "à¤¯à¤¹à¥€ à¤µà¤œà¤¹","à¤‡à¤¸à¤²à¤¿à¤","à¤•à¥à¤¯à¥‹à¤‚à¤•à¤¿","à¤¨à¤¤à¥€à¤œà¤¾","à¤®à¤¤à¤²à¤¬"
    ]

    finance_terms = [
        "inflation", "trade deficit", "import duty", "export ban",
        "global demand", "market price", "consumer price", "price shock",
        "policy impact", "à¤‡à¤¨à¥à¤«à¥à¤²à¥‡à¤¶à¤¨", "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ", "à¤Ÿà¥à¤°à¥‡à¤¡ à¤¡à¥‡à¤«à¤¿à¤¸à¤¿à¤Ÿ",
        "à¤‡à¤®à¥à¤ªà¥‹à¤°à¥à¤Ÿ à¤¡à¥à¤¯à¥‚à¤Ÿà¥€", "à¤—à¥à¤²à¥‹à¤¬à¤² à¤¡à¤¿à¤®à¤¾à¤‚à¤¡", "à¤•à¥€à¤®à¤¤", "à¤¦à¤¾à¤®"
    ]

    score = 0
    reasons = []

    if niche in V19_INFORMATIONAL_NICHES:
        h = v19_text_hits(text, politics_tension)
        e = v19_text_hits(text, explainer_tension)
        c = v19_text_hits(text, conflict_tension)
        p = v19_text_hits(text, payoff_terms)
        f = v19_text_hits(text, finance_terms)

        score += min(24, h * 4)
        score += min(16, e * 4)
        score += min(18, c * 5)
        score += min(14, p * 7)
        score += min(24, f * 6)

        if h: reasons.append("info_topic_tension")
        if e: reasons.append("explainer_hook")
        if c: reasons.append("conflict_or_accountability")
        if p: reasons.append("payoff_logic")
        if f: reasons.append("finance_economics_stakes")

    else:
        creator_terms = [
            "exposed","caught","betrayed","shocking","crazy","secret",
            "funny","story","suddenly","nobody expected",
            "he said","she said","i said","i asked","conversation",
            "realized","because","but","then","therefore",
            "à¤§à¥‹à¤–à¤¾","à¤ªà¤•à¤¡à¤¼à¤¾","à¤µà¤¿à¤µà¤¾à¤¦","à¤…à¤šà¤¾à¤¨à¤•","à¤•à¤¹à¤¾à¤¨à¥€","à¤‰à¤¸à¤¨à¥‡ à¤•à¤¹à¤¾",
            "à¤®à¥ˆà¤‚à¤¨à¥‡ à¤•à¤¹à¤¾","à¤«à¤¿à¤°","à¤•à¥à¤¯à¥‹à¤‚à¤•à¤¿","à¤²à¥‡à¤•à¤¿à¤¨","à¤‡à¤¸à¤²à¤¿à¤","à¤®à¤¤à¤²à¤¬"
        ]
        h = v19_text_hits(text, creator_terms)
        score += min(25, h * 5)
        if h: reasons.append("creator_native_tension")

    wc = len(text.split())
    if 12 <= wc <= 145:
        score += 8
        reasons.append("good_context_length")
    elif wc < 7:
        score -= 18
        reasons.append("too_short")
    elif wc > 180:
        score -= 10
        reasons.append("too_long")

    return score, reasons


def v40_clip_profile(niche):
    niche = str(niche or "general")
    profiles = {
        "podcast_story": {"min": 25, "target": 42, "max": 60, "pre": 5, "post": 10},
        "education_explainer": {"min": 22, "target": 40, "max": 60, "pre": 4, "post": 10},
        "geopolitics": {"min": 24, "target": 42, "max": 60, "pre": 5, "post": 9},
        "politics_news": {"min": 22, "target": 40, "max": 60, "pre": 4, "post": 8},
        "finance_economics": {"min": 24, "target": 42, "max": 60, "pre": 4, "post": 10},
        "finance_business": {"min": 22, "target": 38, "max": 58, "pre": 4, "post": 8},
        "crime_mystery": {"min": 20, "target": 36, "max": 55, "pre": 4, "post": 8},
        "comedy_entertainment": {"min": 8, "target": 20, "max": 35, "pre": 2, "post": 4},
        "sports": {"min": 10, "target": 24, "max": 40, "pre": 2, "post": 5},
        "self_improvement": {"min": 20, "target": 36, "max": 55, "pre": 4, "post": 8},
    }
    return profiles.get(niche, {"min": 16, "target": 34, "max": 55, "pre": 3, "post": 7})


def v40_sentence_boundary_score(text, position="start"):
    text = str(text or "").strip().lower()
    if not text:
        return -20

    score = 0
    bad_start = (
        "and ", "but ", "so ", "which ", "that ", "who ",
        "because ", "à¤¤à¥‹ ", "à¤”à¤° ", "à¤²à¥‡à¤•à¤¿à¤¨ ", "à¤•à¥à¤¯à¥‹à¤‚à¤•à¤¿ ", "à¤œà¥‹ "
    )
    good_start = [
        "why", "how", "what", "listen", "imagine", "the reason",
        "à¤•à¥à¤¯à¥‹à¤‚", "à¤•à¥ˆà¤¸à¥‡", "à¤•à¥à¤¯à¤¾", "à¤¸à¥à¤¨à¤¿à¤", "à¤¦à¥‡à¤–à¤¿à¤", "à¤¸à¥‹à¤šà¤¿à¤", "à¤à¤•"
    ]
    good_end = [
        "this is why", "that is why", "therefore", "this means",
        "that means", "finally", "in the end", "result",
        "à¤‡à¤¸à¤²à¤¿à¤", "à¤®à¤¤à¤²à¤¬", "à¤¨à¤¤à¥€à¤œà¤¾", "à¤¯à¤¹à¥€ à¤µà¤œà¤¹", "à¤†à¤–à¤¿à¤°"
    ]

    if position == "start":
        if text.startswith(bad_start):
            score -= 18
        if any(w in text for w in good_start):
            score += 10
        wc = len(text.split())
        if 5 <= wc <= 35:
            score += 6
    else:
        if text.endswith(("and", "but", "because", "so", "then")):
            score -= 22
        if any(w in text for w in good_end):
            score += 18
        if text.endswith((".", "!", "?", "à¥¤")):
            score += 8
        wc = len(text.split())
        if 5 <= wc <= 42:
            score += 5

    return score


def v40_narrative_quality_score(text, start_text, end_text, niche):
    text = str(text or "").lower()
    niche = str(niche or "general")
    score = 0
    reasons = []
    v43_bonus, v43_reasons = v43_hinglish_payoff_bonus(text)
    v44_bonus, v44_reasons, _ = v44_semantic_payoff_score(text)

    setup = [
        "because", "reason", "context", "what happened", "why",
        "à¤•à¥à¤¯à¥‹à¤‚à¤•à¤¿", "à¤µà¤œà¤¹", "à¤•à¤¾à¤°à¤£", "à¤•à¤¹à¤¾à¤¨à¥€"
    ]
    buildup = [
        "but", "however", "then", "suddenly", "problem", "risk",
        "à¤²à¥‡à¤•à¤¿à¤¨", "à¤®à¤—à¤°", "à¤«à¤¿à¤°", "à¤…à¤šà¤¾à¤¨à¤•", "à¤¸à¤®à¤¸à¥à¤¯à¤¾", "à¤–à¤¤à¤°à¤¾"
    ]
    payoff = [
        "therefore", "this means", "that means", "this is why",
        "finally", "result", "impact", "lesson",
        "à¤‡à¤¸à¤²à¤¿à¤", "à¤®à¤¤à¤²à¤¬", "à¤¨à¤¤à¥€à¤œà¤¾", "à¤…à¤¸à¤°", "à¤¸à¥€à¤–"
    ]
    conversation = [
        "he said", "she said", "i said", "i asked", "they said",
        "à¤‰à¤¸à¤¨à¥‡ à¤•à¤¹à¤¾", "à¤®à¥ˆà¤‚à¤¨à¥‡ à¤•à¤¹à¤¾", "à¤¬à¥‹à¤²à¤¾", "à¤ªà¥‚à¤›à¤¾", "à¤¬à¤¤à¤¾à¤¯à¤¾"
    ]
    curiosity = [
        "why", "how", "what", "secret", "truth", "nobody",
        "à¤•à¥à¤¯à¥‹à¤‚", "à¤•à¥ˆà¤¸à¥‡", "à¤•à¥à¤¯à¤¾", "à¤¸à¤š", "à¤°à¤¾à¤œ"
    ]

    s_hits = v19_text_hits(text, setup)
    b_hits = v19_text_hits(text, buildup)
    p_hits = v19_text_hits(text, payoff)
    c_hits = v19_text_hits(text, conversation)
    q_hits = v19_text_hits(text, curiosity)

    score += min(18, s_hits * 5)
    score += min(20, b_hits * 5)
    score += min(26, p_hits * 8)
    score += min(14, v43_bonus)
    score += min(10, v44_bonus)
    score += min(18, c_hits * 5)
    score += min(14, q_hits * 4)

    if s_hits: reasons.append("setup_context")
    if b_hits: reasons.append("buildup_or_tension")
    if p_hits or v43_bonus > 0 or v44_bonus >= 8: reasons.append("payoff_or_explanation")
    reasons.extend(v43_reasons)
    reasons.extend(v44_reasons)
    if c_hits: reasons.append("speaker_flow")
    if q_hits: reasons.append("curiosity_gap")

    start_boundary = v40_sentence_boundary_score(start_text, "start")
    end_boundary = v40_sentence_boundary_score(end_text, "end")
    score += start_boundary
    score += end_boundary
    if start_boundary < 0:
        reasons.append("start_boundary_risk")
    if end_boundary < 0:
        reasons.append("ending_boundary_risk")

    wc = len(text.split())
    if niche in {"podcast_story", "education_explainer", "geopolitics", "finance_economics", "politics_news"}:
        if 35 <= wc <= 160:
            score += 16
            reasons.append("longform_context_length")
        elif wc < 24:
            score -= 4
            reasons.append("too_short_for_niche")
    elif 18 <= wc <= 120:
        score += 8
        reasons.append("good_story_length")

    return max(min(score, 85), -45), reasons


def v41_story_diagnostics(
    context_text,
    start_text,
    end_text,
    context_quality,
    payoff_bonus,
    editor_reasons,
    true_creator_reasons,
    v40_narrative_score,
    v40_narrative_reasons,
    arc_bonus,
):
    text = str(context_text or "")
    start_low = str(start_text or "").strip().lower()
    end_low = str(end_text or "").strip().lower()
    editor_reasons = editor_reasons if isinstance(editor_reasons, list) else []
    true_creator_reasons = true_creator_reasons if isinstance(true_creator_reasons, list) else []
    v40_narrative_reasons = v40_narrative_reasons if isinstance(v40_narrative_reasons, list) else []

    setup_strength = safe_float(context_quality)
    if "setup_context" in v40_narrative_reasons:
        setup_strength += 10
    if "start_boundary_risk" in v40_narrative_reasons or "weak_start" in editor_reasons:
        setup_strength -= 12
    if "weak_creator_start" in true_creator_reasons:
        setup_strength -= 10
    setup_strength = max(-40, min(60, round(setup_strength, 2)))

    payoff_strength = safe_float(payoff_bonus)
    if "payoff_or_explanation" in v40_narrative_reasons:
        payoff_strength += 12
    if "ending_boundary_risk" in v40_narrative_reasons or "weak_ending" in editor_reasons:
        payoff_strength -= 14
    if "weak_creator_ending" in true_creator_reasons:
        payoff_strength -= 12
    payoff_strength = max(-40, min(60, round(payoff_strength, 2)))

    continuation_risk = 0
    if start_low.startswith((
        "and ", "but ", "so ", "because ", "then ", "which ", "that ", "if ",
        "after that", "at that time", "now come"
    )):
        continuation_risk += 24
    if end_low.endswith(("and", "but", "because", "so", "then", "that", "if", "to", "in", "on")):
        continuation_risk += 24
    if "weak_start" in editor_reasons or "weak_creator_start" in true_creator_reasons:
        continuation_risk += 16
    if "weak_ending" in editor_reasons or "weak_creator_ending" in true_creator_reasons:
        continuation_risk += 16
    continuation_risk = min(100, continuation_risk)

    word_count = len(text.split())
    if word_count < 18:
        context_density = "thin"
    elif word_count <= 140:
        context_density = "balanced"
    elif word_count <= 180:
        context_density = "dense"
    else:
        context_density = "overextended"

    story_completeness_estimate = (
        max(-20, min(30, setup_strength))
        + max(-20, min(30, payoff_strength))
        + max(-25, min(35, safe_float(v40_narrative_score)))
        + max(-10, min(12, safe_float(arc_bonus)))
        - min(35, continuation_risk)
    )

    return {
        "setup_strength": round(setup_strength, 2),
        "payoff_strength": round(payoff_strength, 2),
        "continuation_risk": round(continuation_risk, 2),
        "context_density": context_density,
        "story_completeness_estimate": round(max(-100, min(100, story_completeness_estimate)), 2),
    }


def v42_repetition_or_filler_spike(text):
    text = str(text or "").strip().lower()
    if not text:
        return True

    if _v7_is_drift(text) or v11_is_hard_bad_ending(text):
        return True

    words = text.split()
    if len(words) >= 10:
        top = max(words.count(w) for w in set(words))
        if top / max(len(words), 1) > 0.45:
            return True

    compact = re.sub(r"\s+", "", text)
    if len(compact) >= 40 and len(set(compact)) / max(len(compact), 1) < 0.13:
        return True

    filler_phrases = [
        "basically", "overall", "coming back", "moving on",
        "in this video", "let us understand", "case study"
    ]
    return sum(1 for p in filler_phrases if p in text) >= 2


def v42_payoff_extension_metrics(segments, start, end, niche, arc_bonus):
    text = get_nearby_text(segments, start, end, window=0)
    start_text, end_text = _v8_first_last_segment_text(segments, start, end)
    v43_bonus, v43_reasons = v43_hinglish_payoff_bonus(text)
    v44_bonus, v44_reasons, v44_confidence = v44_semantic_payoff_score(text)
    if v44_payoff_quality_block(text):
        payoff_bonus = 0
    else:
        payoff_bonus = max(v6_payoff_bonus(text), v7_better_payoff_bonus(text), v43_bonus, v44_bonus)
    context_quality = v7_context_quality_score(text)
    natural_editor_score, editor_reasons = v8_natural_editor_grade(
        text,
        start_text,
        end_text
    )
    true_creator_score, true_creator_reasons = v9_true_creator_grade(
        text,
        start_text,
        end_text
    )
    v40_narrative_score, v40_narrative_reasons = v40_narrative_quality_score(
        text,
        start_text,
        end_text,
        niche
    )
    story_diagnostics = v41_story_diagnostics(
        text,
        start_text,
        end_text,
        context_quality,
        payoff_bonus,
        editor_reasons,
        true_creator_reasons,
        v40_narrative_score,
        v40_narrative_reasons,
        arc_bonus,
    )
    return {
        "text": text,
        "start_text": start_text,
        "end_text": end_text,
        "payoff_bonus": payoff_bonus,
        "context_quality": context_quality,
        "natural_editor_score": natural_editor_score,
        "editor_reasons": editor_reasons,
        "true_creator_score": true_creator_score,
        "true_creator_reasons": true_creator_reasons,
        "v40_narrative_score": v40_narrative_score,
        "v40_narrative_reasons": v40_narrative_reasons,
        "v43_hinglish_payoff_bonus": v43_bonus,
        "v43_hinglish_payoff_reasons": v43_reasons,
        "v44_semantic_payoff_score": v44_bonus,
        "v44_semantic_payoff_reasons": v44_reasons,
        "v44_semantic_payoff_confidence": v44_confidence,
        "story_diagnostics": story_diagnostics,
    }


def v42_guarded_payoff_extension(
    segments,
    start,
    end,
    niche,
    low_confidence_asr,
    story_editor_ok,
    original_metrics,
):
    reasons = []
    diagnostics = (original_metrics or {}).get("story_diagnostics", {})
    if not (
        safe_float(diagnostics.get("payoff_strength")) <= 0
        and safe_float(diagnostics.get("continuation_risk")) == 0
        and low_confidence_asr is False
        and story_editor_ok is True
    ):
        return None

    profile = v40_clip_profile(niche)
    max_end = safe_float(start) + safe_float(profile.get("max", 55))
    cur_end = safe_float(end)
    best = None
    original_payoff = safe_float(original_metrics.get("payoff_bonus"))
    original_payoff_strength = safe_float(diagnostics.get("payoff_strength"))
    original_v40 = safe_float(original_metrics.get("v40_narrative_score"))
    original_complete = safe_float(diagnostics.get("story_completeness_estimate"))
    original_continuation = safe_float(diagnostics.get("continuation_risk"))

    for seg in safe_dict_list(segments):
        st = safe_float(seg.get("start"))
        ee = safe_float(seg.get("end"))
        seg_text = str(seg.get("text", "")).strip()

        if st <= cur_end + 0.05:
            continue
        if st - cur_end > 12:
            break
        if ee > max_end:
            break
        if is_ad_segment(seg_text) or is_bad_transcript_clip(seg_text):
            reasons.append("stopped_bad_or_ad_segment")
            break
        if v38_text_quality_is_severe(seg_text) or v42_repetition_or_filler_spike(seg_text):
            reasons.append("stopped_weak_transcript_or_filler")
            break

        candidate_end = ee
        candidate_text = get_nearby_text(segments, start, candidate_end, window=0)
        if (
            is_ad_segment(candidate_text)
            or is_bad_transcript_clip(candidate_text)
            or v38_text_quality_is_severe(candidate_text)
            or v42_repetition_or_filler_spike(candidate_text)
        ):
            reasons.append("stopped_candidate_quality_risk")
            break

        candidate = v42_payoff_extension_metrics(
            segments,
            start,
            candidate_end,
            niche,
            safe_float(original_metrics.get("arc_bonus")),
        )
        candidate_diag = candidate["story_diagnostics"]
        if safe_float(candidate_diag.get("continuation_risk")) > original_continuation:
            reasons.append("stopped_continuation_risk_increased")
            break

        improved = (
            safe_float(candidate.get("payoff_bonus")) > original_payoff
            or safe_float(candidate_diag.get("payoff_strength")) > original_payoff_strength
            or safe_float(candidate.get("v40_narrative_score")) > original_v40
            or safe_float(candidate_diag.get("story_completeness_estimate")) > original_complete
        )
        if improved:
            candidate["end"] = round(candidate_end, 2)
            candidate["extension_seconds"] = round(candidate_end - safe_float(end), 2)
            candidate["payoff_extension_reasons"] = [
                "forward_extension",
                "quality_guard_passed",
            ]
            if safe_float(candidate.get("payoff_bonus")) > original_payoff:
                candidate["payoff_extension_reasons"].append("payoff_bonus_improved")
            if safe_float(candidate_diag.get("payoff_strength")) > original_payoff_strength:
                candidate["payoff_extension_reasons"].append("payoff_strength_improved")
            if safe_float(candidate.get("v40_narrative_score")) > original_v40:
                candidate["payoff_extension_reasons"].append("v40_narrative_score_improved")
            if safe_float(candidate_diag.get("story_completeness_estimate")) > original_complete:
                candidate["payoff_extension_reasons"].append("story_completeness_improved")
            best = candidate

        cur_end = candidate_end

    if best is None:
        if not reasons:
            reasons.append("no_safe_improving_extension")
        return {
            "accepted": False,
            "payoff_extension_reasons": reasons[:5],
        }

    best["accepted"] = True
    return best


def v40_extend_to_story_shape(segments, start, end, niche):
    segments = safe_dict_list(segments)
    profile = v40_clip_profile(niche)
    min_len = profile["min"]
    max_len = profile["max"]

    selected = []
    for seg in segments:
        st = safe_float(seg.get("start"))
        ee = safe_float(seg.get("end"))
        if ee >= start - profile["pre"] and st <= end + profile["post"]:
            selected.append(seg)

    if not selected:
        return round(start, 2), round(end, 2)

    cur_start = start
    cur_end = end

    for seg in reversed(segments):
        st = safe_float(seg.get("start"))
        ee = safe_float(seg.get("end"))
        tx = str(seg.get("text", "")).strip()
        if ee < start - profile["pre"] or ee > start:
            continue
        if is_ad_segment(tx) or _v7_is_drift(tx):
            break
        if v40_sentence_boundary_score(tx, "start") >= -6:
            cur_start = st

    duration = cur_end - cur_start
    for seg in segments:
        st = safe_float(seg.get("start"))
        ee = safe_float(seg.get("end"))
        tx = str(seg.get("text", "")).strip()
        if st <= cur_end:
            continue
        if st > cur_start + max_len:
            break
        if is_ad_segment(tx) or _v7_is_drift(tx) or v11_is_hard_bad_ending(tx):
            break
        cur_end = ee
        duration = cur_end - cur_start
        end_score = v40_sentence_boundary_score(tx, "end")
        if duration >= min_len and end_score >= 8:
            break
        if duration >= profile["target"] and end_score >= 0:
            break

    if cur_end - cur_start < min_len:
        for seg in segments:
            st = safe_float(seg.get("start"))
            ee = safe_float(seg.get("end"))
            tx = str(seg.get("text", "")).strip()
            if st <= cur_end:
                continue
            if ee - cur_start > max_len:
                break
            if is_ad_segment(tx) or _v7_is_drift(tx) or v11_is_hard_bad_ending(tx):
                break
            cur_end = ee
            if cur_end - cur_start >= min_len:
                break

    if cur_end - cur_start > max_len:
        cur_end = cur_start + max_len

    return round(cur_start, 2), round(cur_end, 2)


def v40_recover_speaker_setup_start(segments, start, end, niche):
    if str(niche or "general") not in V40_STORY_NICHES:
        return round(start, 2)

    segments = safe_dict_list(segments)
    first_text = ""
    previous = None

    for seg in segments:
        st = safe_float(seg.get("start"))
        ee = safe_float(seg.get("end"))
        if ee <= start:
            previous = seg
            continue
        if st < end:
            first_text = str(seg.get("text", "")).strip().lower()
            break

    if not previous:
        return round(start, 2)

    prev_start = safe_float(previous.get("start"))
    prev_end = safe_float(previous.get("end"))
    prev_text = str(previous.get("text", "")).strip().lower()

    if start - prev_end > 5.5:
        return round(start, 2)

    mid_start = first_text.startswith((
        "because ", "but ", "then ", "so ", "and ", "which ",
        "à¤•à¥à¤¯à¥‹à¤‚à¤•à¤¿ ", "à¤²à¥‡à¤•à¤¿à¤¨ ", "à¤«à¤¿à¤° ", "à¤¤à¥‹ ", "à¤”à¤° ", "à¤œà¥‹ "
    ))
    speaker_setup = any(x in prev_text for x in [
        "he said", "she said", "i said", "i asked", "they said",
        "à¤‰à¤¸à¤¨à¥‡ à¤•à¤¹à¤¾", "à¤®à¥ˆà¤‚à¤¨à¥‡ à¤•à¤¹à¤¾", "à¤ªà¥‚à¤›à¤¾", "à¤¬à¥‹à¤²à¤¾", "à¤¬à¤¤à¤¾à¤¯à¤¾",
        "what happened", "à¤•à¥à¤¯à¤¾ à¤¹à¥à¤†", "à¤•à¤¹à¤¾à¤¨à¥€", "à¤¬à¤¾à¤¤"
    ])

    if mid_start or speaker_setup:
        return round(prev_start, 2)

    return round(start, 2)

def v19_is_clean_boundary(true_creator_reasons, editor_reasons):
    hard_bad = {
        "weak_creator_start", "weak_creator_ending",
        "weak_start", "weak_ending"
    }
    found = set(true_creator_reasons or []) | set(editor_reasons or [])
    return not bool(found & hard_bad)

def v19_universal_clip_ok(
    niche,
    combined_text,
    natural_editor_score,
    true_creator_score,
    context_quality,
    true_creator_reasons,
    editor_reasons,
    native_score
):
    niche = str(niche or "general")

    if is_ad_segment(combined_text):
        return False

    clean_boundary = v19_is_clean_boundary(true_creator_reasons, editor_reasons)

    if niche in V19_INFORMATIONAL_NICHES:
        return (
            clean_boundary
            and natural_editor_score >= 24
            and true_creator_score >= 26
            and context_quality >= -12
            and native_score >= 8
        )

    if niche in V19_STRICT_CREATOR_NICHES:
        return (
            clean_boundary
            and natural_editor_score >= 28
            and true_creator_score >= 34
        )

    return (
        clean_boundary
        and natural_editor_score >= 30
        and true_creator_score >= 32
    )


def build_story_arc_candidates(segments):
    segments = safe_dict_list(segments)
    arcs = []
    current = []
    last_end = None

    def flush_arc():
        if len(current) < 2:
            return

        start = safe_float(current[0].get("start"))
        end = safe_float(current[-1].get("end"))
        text = " ".join(str(s.get("text", "")).strip() for s in current).strip()
        low = text.lower()
        if not text or end <= start or is_ad_segment(low) or is_bad_transcript_clip(text):
            return

        before_after = [
            "before", "after", "40 years ago", "just 40 years ago",
            "back then", "today", "now", "transformed", "became",
            "used to", "in the next", "years"
        ]
        documentary_contrast = [
            "can you imagine", "imagine", "how could this be possible",
            "at that time", "back then", "but", "however", "whereas",
            "on the other hand"
        ]
        historical_tension = [
            "history", "historical", "war", "china", "country", "power",
            "military", "economy", "poverty", "development", "growth",
            "collapse", "crisis", "risk", "threat"
        ]
        cause_effect = [
            "because", "reason", "this means", "that means", "therefore",
            "result", "impact", "why", "how", "so"
        ]
        payoff = [
            "this is why", "that is why", "finally", "in the end",
            "result", "impact", "changed", "became", "possible",
            "transformed"
        ]

        score = 0
        reasons = []

        ba = sum(1 for p in before_after if p in low)
        dc = sum(1 for p in documentary_contrast if p in low)
        ht = sum(1 for p in historical_tension if p in low)
        ce = sum(1 for p in cause_effect if p in low)
        po = sum(1 for p in payoff if p in low)

        if ba:
            score += min(28, ba * 7)
            reasons.append("before_after_transformation")
        if dc:
            score += min(24, dc * 6)
            reasons.append("documentary_contrast")
        if ht:
            score += min(22, ht * 4)
            reasons.append("historical_tension")
        if ce:
            score += min(20, ce * 5)
            reasons.append("cause_effect")
        if po:
            score += min(24, po * 6)
            reasons.append("payoff_present")

        topic_groups = set()
        for seg in current:
            topic_groups |= _v7_topic_terms(seg.get("text", ""))
        if len(topic_groups) <= 1:
            score += 12
            reasons.append("one_clear_idea")
        elif len(topic_groups) >= 3:
            score -= 18
            reasons.append("mixed_topics")

        word_count = len(low.split())
        if 18 <= word_count <= 135:
            score += 10
            reasons.append("arc_sized")
        elif word_count > 170:
            score -= 20
            reasons.append("overextended_arc")

        if score < 38:
            return

        niche = v10_detect_creator_niche(text)
        title = v9_editorial_title(text, set())
        arcs.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "text": text,
            "score": score,
            "title": title,
            "hashtags": v40_niche_hashtags(niche, text),
            "niche": niche,
            "score_breakdown": {
                "arc_candidate": True,
                "arc_score": score,
                "arc_reasons": reasons,
                "topic_groups": sorted(topic_groups),
                "word_count": word_count
            }
        })

    for seg in segments:
        tx = str(seg.get("text", "")).strip()
        low = tx.lower()
        st = safe_float(seg.get("start"))
        ee = safe_float(seg.get("end"))

        if not tx or ee <= st or is_ad_segment(low) or _v7_is_drift(low):
            flush_arc()
            current = []
            last_end = None
            continue

        if current:
            prev_text = str(current[-1].get("text", "")).strip()
            gap = st - safe_float(current[-1].get("end"))
            arc_start = safe_float(current[0].get("start"))
            if gap > 5.5 or ee - arc_start > 90 or _v7_topic_shift(prev_text, tx):
                flush_arc()
                current = []

        current.append(seg)
        last_end = ee

    flush_arc()
    return sorted(arcs, key=lambda x: x.get("score", 0), reverse=True)


def merge_viral_candidates(arc_candidates, viral_candidates):
    merged = safe_dict_list(arc_candidates) + safe_dict_list(viral_candidates)
    merged = sorted(merged, key=lambda x: safe_float(x.get("score")), reverse=True)

    unique = []
    for c in merged:
        start = safe_float(c.get("start"))
        end = safe_float(c.get("end"))
        text = str(c.get("text", "")).strip()
        if end <= start or not text:
            continue

        duplicate = False
        for u in unique:
            if abs(start - safe_float(u.get("start"))) < 5:
                duplicate = True
                break
            if _v8_context_overlap(text, str(u.get("text", ""))) >= 0.68:
                duplicate = True
                break

        if not duplicate:
            unique.append(c)

    return unique


def v19_recover_fallback_clips(viral, segments):
    recovered = []
    viral = safe_dict_list(viral)
    segments = safe_dict_list(segments)

    for v in viral[:8]:
        start = safe_float(v.get("start"))
        end = safe_float(v.get("end"))
        text = str(v.get("text", "")).strip()

        if start < 0 or end <= start or is_ad_segment(text):
            continue

        context_start, final_end = expand_story_clip(segments, start, end)
        final_end = smooth_clip_end(segments, final_end)
        start = v6_hook_aligned_start(segments, context_start, final_end)
        start = v9_clean_start_time(segments, start, final_end)
        final_end = v9_clean_end_time(segments, start, final_end)

        combined_text = get_nearby_text(segments, start, final_end, window=0)
        if is_ad_segment(combined_text):
            continue

        start_text, end_text = _v8_first_last_segment_text(segments, start, final_end)
        v8_score, v8_reasons = v8_natural_editor_grade(combined_text, start_text, end_text)
        v9_score, v9_reasons = v9_true_creator_grade(combined_text, start_text, end_text)
        niche = v10_detect_creator_niche(combined_text)
        native_score, native_reasons = v19_niche_native_signals(combined_text, niche)

        if not v19_universal_clip_ok(
            niche, combined_text, v8_score, v9_score, 0,
            v9_reasons, v8_reasons, native_score
        ):
            continue

        clip_title = v9_editorial_title(combined_text, set())

        recovered.append({
            "start": round(start, 2),
            "end": round(final_end, 2),
            "source_text": text,
            "expanded_text": combined_text,
            "title": clip_title,
            "hashtags": (
                v38_finance_economics_hashtags(combined_text)
                if niche == "finance_economics"
                else v.get("hashtags", ["#viral", "#shorts"])
            ),
            "niche": niche,
            "score": v.get("score", 0) + native_score + min(35, v8_score) + min(40, v9_score),
            "score_breakdown": {
                **v.get("score_breakdown", {}),
                "detected_niche": niche,
                "natural_editor_score": v8_score,
                "true_creator_score": v9_score,
                "editor_reasons": v8_reasons,
                "true_creator_reasons": v9_reasons,
                "v19_native_score": native_score,
                "v19_native_reasons": native_reasons,
                "v19_recovered": True,
                "start_text": start_text,
                "end_text": end_text
            }
        })

    return sorted(recovered, key=lambda x: x.get("score", 0), reverse=True)[:4]


def candidate_funnel_preview(text, limit=180):
    return v18_preview_text(text, limit)


def candidate_funnel_initial_metrics(text, niche):
    text = str(text or "").strip()
    niche = str(niche or "general")
    if not text:
        return {}

    try:
        v43_bonus, v43_reasons = v43_hinglish_payoff_bonus(text)
        v44_bonus, v44_reasons, v44_confidence = v44_semantic_payoff_score(text)
        payoff_bonus = 0 if v44_payoff_quality_block(text) else max(
            v6_payoff_bonus(text),
            v7_better_payoff_bonus(text),
            v43_bonus,
            v44_bonus,
        )
        context_quality = v7_context_quality_score(text)
        start_text = text
        end_text = text
        natural_editor_score, editor_reasons = v8_natural_editor_grade(
            text,
            start_text,
            end_text,
        )
        true_creator_score, true_creator_reasons = v9_true_creator_grade(
            text,
            start_text,
            end_text,
        )
        v40_narrative_score, v40_narrative_reasons = v40_narrative_quality_score(
            text,
            start_text,
            end_text,
            niche,
        )
        arc_bonus = v6_story_arc_bonus(text)
        story_diagnostics = v41_story_diagnostics(
            text,
            start_text,
            end_text,
            context_quality,
            payoff_bonus,
            editor_reasons,
            true_creator_reasons,
            v40_narrative_score,
            v40_narrative_reasons,
            arc_bonus,
        )
        return {
            "payoff_bonus": payoff_bonus,
            "v43_hinglish_payoff_bonus": v43_bonus,
            "v43_hinglish_payoff_reasons": v43_reasons,
            "v44_semantic_payoff_score": v44_bonus,
            "v44_semantic_payoff_reasons": v44_reasons,
            "v44_semantic_payoff_confidence": v44_confidence,
            "context_quality": context_quality,
            "natural_editor_score": natural_editor_score,
            "true_creator_score": true_creator_score,
            "v40_narrative_score": v40_narrative_score,
            "v40_narrative_reasons": v40_narrative_reasons,
            "setup_strength": story_diagnostics.get("setup_strength"),
            "payoff_strength": story_diagnostics.get("payoff_strength"),
            "continuation_risk": story_diagnostics.get("continuation_risk"),
            "context_density": story_diagnostics.get("context_density"),
            "story_completeness_estimate": story_diagnostics.get("story_completeness_estimate"),
        }
    except Exception as e:
        return {"metrics_error": str(e)}


def write_candidate_funnel_rows(job_id, rows):
    rows = safe_dict_list(rows)
    if not rows:
        return

    try:
        os.makedirs("analytics", exist_ok=True)
        with open("analytics/candidate_funnel.jsonl", "a", encoding="utf-8") as f:
            for row in rows:
                out = {
                    "ts": time.time(),
                    "job_id": job_id or "unknown",
                    **row,
                    "version": "candidate_funnel_v1",
                }
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(f"✅ Candidate funnel analytics logged: {len(rows)} rows")
    except Exception as e:
        print(f"⚠️ Candidate funnel analytics logging failed: {e}")


def build_final_clips(viral, segments, visual_intelligence=None, job_id=None):
    clips = []
    candidate_funnel_rows = []

    MIN_FINAL_CLIP = 1
    MAX_FINAL_CLIP = 60
    MAX_TOTAL_CLIPS = 6

    viral = safe_dict_list(viral)
    segments = safe_dict_list(segments)
    asr_modes = [str(s.get("asr_mode", "")) for s in segments if isinstance(s, dict) and s.get("asr_mode")]
    asr_quality_scores = [
        safe_float(s.get("asr_quality_score"))
        for s in segments
        if isinstance(s, dict) and s.get("asr_quality_score") is not None
    ]
    low_confidence_asr = any(bool(s.get("low_confidence_asr")) for s in segments if isinstance(s, dict))
    asr_mode = asr_modes[0] if asr_modes else "native_transcribe"
    asr_quality_score = min(asr_quality_scores) if asr_quality_scores else None
    asr_quality_reasons = []
    asr_stability_chunks = v48_build_asr_stability_chunks(segments)
    for s in segments:
        if not isinstance(s, dict):
            continue
        for reason in s.get("asr_quality_reasons", []) or []:
            if reason not in asr_quality_reasons:
                asr_quality_reasons.append(reason)

    for candidate_index, v in enumerate(viral[:20]):
        start = safe_float(v.get("start"))
        end = safe_float(v.get("end"))
        text = str(v.get("text", "")).strip()
        initial_niche = v.get("niche") or v10_detect_creator_niche(text)
        funnel_row = {
            "candidate_index": candidate_index,
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(end - start, 2),
            "text_preview": candidate_funnel_preview(text),
            "niche": initial_niche,
            "initial_score": safe_float(v.get("score")),
            "source": "merged_viral",
            "filter_decision": "silent_removed",
            "filter_reason": "not_completed",
            "payoff_extension_attempted": False,
            "payoff_extension_improved": False,
            "payoff_extension_reasons": [],
            **candidate_funnel_initial_metrics(text, initial_niche),
        }
        candidate_funnel_rows.append(funnel_row)

        # ðŸš« Skip weak hooks (intro-type)
        if is_weak_hook(text):
            funnel_row["filter_decision"] = "quality_rejected"
            funnel_row["filter_reason"] = "weak_hook"
            continue

        # ðŸ”¥ Soft hook boost only: do not reject otherwise-good clips
        hook_bonus = 8 if is_strong_hook(text) else 0


        if start < 0 or end <= start:
            funnel_row["filter_decision"] = "quality_rejected"
            funnel_row["filter_reason"] = "invalid_timing"
            continue

        # ðŸ”¥ CONTEXT PACK 1C:
        # Use ONLY the finally-selected clip range,
        # not random nearby transcript windows.
        nearby_text = ""

        combined_text = text

        if is_ad_segment(combined_text):
            print(f"âŒ Ad/CTA segment rejected: {text[:120]}")
            funnel_row["filter_decision"] = "quality_rejected"
            funnel_row["filter_reason"] = "ad_or_cta_initial"
            continue

        # Context-safe timing:
        # start a little before the detected hook, and extend enough
        # to preserve answer/context without making clips too long.
        context_start, final_end = expand_story_clip(segments, start, end)
        final_end = smooth_clip_end(segments, final_end)
        # ðŸ”¥ V11 hook-first boundary:
        # First use old soft alignment, then force true creator-grade hook start.
        start = v6_hook_aligned_start(segments, context_start, final_end)
        start = v9_clean_start_time(segments, start, final_end)
        final_end = v9_clean_end_time(segments, start, final_end)

        # âœ… REAL selected context text
        combined_text = get_nearby_text(
            segments,
            start,
            final_end,
            window=0
        )

        # V18 hard sponsor/ad gate after story expansion.
        # This catches ads that enter only after context expansion.
        if is_ad_segment(combined_text):
            print(f"âŒ V18 expanded ad/CTA rejected: {combined_text[:140]}")
            funnel_row["filter_decision"] = "quality_rejected"
            funnel_row["filter_reason"] = "ad_or_cta_expanded"
            continue

        if is_bad_transcript_clip(combined_text):
            print(f"ðŸš« Bad transcript clip rejected: {combined_text[:140]}")
            funnel_row["filter_decision"] = "quality_rejected"
            funnel_row["filter_reason"] = "bad_transcript_clip"
            continue

        detected_niche = v10_detect_creator_niche(combined_text)

        # V40 story pass: podcasts/explainers/debates need enough setup and
        # payoff to feel edited, not just extracted from a spike.
        if detected_niche in V40_STORY_NICHES and not low_confidence_asr:
            v40_profile = v40_clip_profile(detected_niche)
            shaped_start, shaped_end = v40_extend_to_story_shape(
                segments,
                start,
                final_end,
                detected_niche
            )
            shaped_start = v40_recover_speaker_setup_start(
                segments,
                shaped_start,
                shaped_end,
                detected_niche
            )
            shaped_duration = shaped_end - shaped_start
            if (
                shaped_end > shaped_start
                and shaped_duration <= v40_profile["max"]
                and (shaped_end > final_end or shaped_start < start)
            ):
                shaped_text = get_nearby_text(
                    segments,
                    shaped_start,
                    shaped_end,
                    window=0
                )
                _, shaped_end_text = _v8_first_last_segment_text(
                    segments,
                    shaped_start,
                    shaped_end
                )
                shaped_continuation_end = str(shaped_end_text or "").strip().lower().endswith((
                    "and", "but", "because", "so", "then", "that", "if", "to", "in", "on"
                ))
                if (
                    not shaped_continuation_end
                    and not is_ad_segment(shaped_text)
                    and not is_bad_transcript_clip(shaped_text)
                ):
                    start, final_end = shaped_start, shaped_end
                    combined_text = shaped_text

        quality_boost = viral_quality_boost(combined_text)
        v6_arc_bonus = v6_story_arc_bonus(combined_text)

        emotional_momentum = v6_emotional_momentum_bonus(combined_text)
        pacing_bonus = v6_creator_pacing_bonus(combined_text)
        v43_payoff_bonus, v43_payoff_reasons = v43_hinglish_payoff_bonus(combined_text)
        v44_payoff_bonus, v44_payoff_reasons, v44_payoff_confidence = v44_semantic_payoff_score(combined_text)
        if v44_payoff_quality_block(combined_text):
            payoff_bonus = 0
        else:
            payoff_bonus = max(
                v6_payoff_bonus(combined_text),
                v7_better_payoff_bonus(combined_text),
                v43_payoff_bonus,
                v44_payoff_bonus
            )
        dead_zone_penalty = (
            v6_dead_zone_penalty(combined_text)
            + v7_stronger_dead_zone_penalty(combined_text)
        )
        context_quality = v7_context_quality_score(combined_text)

        # ðŸ”¥ V10 UNIVERSAL CREATOR DNA
        emotional_spike = v10_emotional_spike_score(combined_text)
        replayability = v10_replayability_score(combined_text)

        # ðŸ”¥ V15 Human Reaction Engine
        human_reaction_score, human_reaction_reasons = v15_human_reaction_score(combined_text)

        start_text, end_text = _v8_first_last_segment_text(
            segments,
            start,
            final_end
        )
        natural_editor_score, editor_reasons = v8_natural_editor_grade(
            combined_text,
            start_text,
            end_text
        )

        true_creator_score, true_creator_reasons = v9_true_creator_grade(
            combined_text,
            start_text,
            end_text
        )

        creator_retention = v10_creator_retention_score(
            start_text,
            end_text
        )

        middle_text = combined_text[len(combined_text)//3 : (len(combined_text)*2)//3]

        v33_story_score, v33_story_reasons = v33_story_arc_score(
            start_text,
            middle_text,
            end_text
        )

        v39_story_quality, v39_story_reasons = v39_niche_story_quality(
            combined_text,
            start_text,
            end_text,
            detected_niche
        )

        v40_narrative_score, v40_narrative_reasons = v40_narrative_quality_score(
            combined_text,
            start_text,
            end_text,
            detected_niche
        )

        v19_native_score, v19_native_reasons = v19_niche_native_signals(
            combined_text,
            detected_niche
        )

        story_diagnostics = v41_story_diagnostics(
            combined_text,
            start_text,
            end_text,
            context_quality,
            payoff_bonus,
            editor_reasons,
            true_creator_reasons,
            v40_narrative_score,
            v40_narrative_reasons,
            v6_arc_bonus,
        )

        visual_score, visual_reasons = v23_visual_clip_score(
            start,
            final_end,
            visual_intelligence or {}
        )

        feedback_boost, feedback_reasons = v25_feedback_learning_boost(detected_niche)

        # ðŸ”¥ V19 balanced creator gate
        # Allow serious/news/geopolitical clips to survive if they
        # still have acceptable editor structure and context quality.

        informational_niche = detected_niche in V19_INFORMATIONAL_NICHES
        story_niche = detected_niche in V40_STORY_NICHES
        candidate_breakdown = v.get("score_breakdown", {}) if isinstance(v.get("score_breakdown"), dict) else {}
        arc_reasons = candidate_breakdown.get("arc_reasons", [])
        if not isinstance(arc_reasons, list):
            arc_reasons = []
        documentary_arc_candidate = (
            candidate_breakdown.get("arc_candidate") is True
            and "mixed_topics" not in arc_reasons
            and any(r in arc_reasons for r in [
                "before_after_transformation",
                "documentary_contrast",
                "historical_tension",
                "cause_effect",
                "payoff_present"
            ])
        )
        documentary_curiosity = any(p in combined_text.lower() for p in [
            "can you imagine",
            "just 40 years ago",
            "back then",
            "at that time",
            "in the next",
            "how could this be possible"
        ])

        informational_override = v19_universal_clip_ok(
            detected_niche,
            combined_text,
            natural_editor_score,
            true_creator_score,
            context_quality,
            true_creator_reasons,
            editor_reasons,
            v19_native_score
        )

        finance_editor_ok = (
            detected_niche == "finance_economics"
            and v19_is_clean_boundary(true_creator_reasons, editor_reasons)
            and natural_editor_score >= 24
            and true_creator_score >= 26
            and context_quality >= -12
            and v19_native_score >= 10
        )

        story_editor_ok = (
            story_niche
            and v19_is_clean_boundary(true_creator_reasons, editor_reasons)
            and natural_editor_score >= 18
            and true_creator_score >= 20
            and v40_narrative_score >= 18
            and context_quality >= -18
            and replayability >= -12
        )

        documentary_narrative_ok = (
            detected_niche in {"geopolitics", "education_explainer", "politics_news"}
            and documentary_curiosity
            and v19_is_clean_boundary(true_creator_reasons, editor_reasons)
            and natural_editor_score >= 18
            and true_creator_score >= 18
            and v40_narrative_score >= 14
            and replayability >= 0
        )

        documentary_arc_emotion_override = (
            replayability >= 24
            and (story_editor_ok or documentary_narrative_ok)
            and detected_niche in {"geopolitics", "education_explainer", "politics_news"}
            and documentary_arc_candidate
            and "weak_start" not in editor_reasons
            and "weak_ending" not in editor_reasons
            and "weak_creator_start" not in true_creator_reasons
            and "weak_creator_ending" not in true_creator_reasons
        )

        if (
            not informational_override
            and not finance_editor_ok
            and not story_editor_ok
            and not documentary_narrative_ok
            and not documentary_arc_emotion_override
            and (
                (emotional_spike < 10 and human_reaction_score < 18)
                or replayability < -5
                or creator_retention < -5
            )
        ):
            print(
                f"âŒ V10/V15 DNA rejected clip: "
                f"niche={detected_niche} emotional={emotional_spike} "
                f"human={human_reaction_score} {human_reaction_reasons} "
                f"replay={replayability} retention={creator_retention} | "
                f"start={start_text[:80]} | end={end_text[:80]}"
            )
            funnel_row.update({
                "filter_decision": "dna_rejected",
                "filter_reason": "v10_v15_dna_gate",
                "expanded_start": round(start, 2),
                "expanded_end": round(final_end, 2),
                "expanded_preview": candidate_funnel_preview(combined_text),
                "detected_niche": detected_niche,
                "emotional_spike": emotional_spike,
                "human_reaction_score": human_reaction_score,
                "human_reaction_reasons": human_reaction_reasons,
                "replayability": replayability,
                "creator_retention": creator_retention,
                "payoff_bonus": payoff_bonus,
                "v43_hinglish_payoff_bonus": v43_payoff_bonus,
                "v43_hinglish_payoff_reasons": v43_payoff_reasons,
                "v44_semantic_payoff_score": v44_payoff_bonus,
                "v44_semantic_payoff_reasons": v44_payoff_reasons,
                "v44_semantic_payoff_confidence": v44_payoff_confidence,
                "setup_strength": story_diagnostics["setup_strength"],
                "payoff_strength": story_diagnostics["payoff_strength"],
                "continuation_risk": story_diagnostics["continuation_risk"],
                "story_completeness_estimate": story_diagnostics["story_completeness_estimate"],
                "story_editor_ok": story_editor_ok,
                "natural_editor_score": natural_editor_score,
                "true_creator_score": true_creator_score,
                "v40_narrative_score": v40_narrative_score,
                "v40_narrative_reasons": v40_narrative_reasons,
            })
            continue

        # Natural editor behavior: reject bad starts/endings instead of forcing output.
        short_explosive_ok = (
            human_reaction_score >= 22
            and "short_explosive" in human_reaction_reasons
            and any(r in human_reaction_reasons for r in [
                "betrayal",
                "humiliation",
                "exposure",
                "financial_disaster",
                "mystery_loss",
                "disbelief",
                "emotional_contradiction",
            ])
            and (emotional_spike >= 5 or replayability >= 0)
            and "weak_creator_start" not in true_creator_reasons
            and "weak_creator_ending" not in true_creator_reasons


        )

        informational_editor_ok = informational_override or finance_editor_ok
        narrative_editor_ok = informational_editor_ok or story_editor_ok or documentary_narrative_ok

        if (
            not short_explosive_ok
            and not narrative_editor_ok
            and (
                true_creator_score < 38 or
                v39_story_quality < -18 or
                "weak_creator_start" in true_creator_reasons or
                "weak_creator_ending" in true_creator_reasons or
                "weak_start" in editor_reasons or
                "weak_ending" in editor_reasons or
                (natural_editor_score < 28 and true_creator_score < 55)
            )
        ):
            print(
                f"âŒ Creator editor rejected clip: "
                f"v8={natural_editor_score} {editor_reasons} | "
                f"v9={true_creator_score} {true_creator_reasons} | "
                f"emotion={emotional_spike} replay={replayability} "
                f"retention={creator_retention} "
                f"human={human_reaction_score} {human_reaction_reasons} | "
                f"start={start_text[:80]} | "
                f"end={end_text[:80]} | "
                f"{text[:120]}"
            )
            funnel_row.update({
                "filter_decision": "quality_rejected",
                "filter_reason": "creator_editor_gate",
                "expanded_start": round(start, 2),
                "expanded_end": round(final_end, 2),
                "expanded_preview": candidate_funnel_preview(combined_text),
                "detected_niche": detected_niche,
                "emotional_spike": emotional_spike,
                "human_reaction_score": human_reaction_score,
                "human_reaction_reasons": human_reaction_reasons,
                "replayability": replayability,
                "creator_retention": creator_retention,
                "payoff_bonus": payoff_bonus,
                "v43_hinglish_payoff_bonus": v43_payoff_bonus,
                "v43_hinglish_payoff_reasons": v43_payoff_reasons,
                "v44_semantic_payoff_score": v44_payoff_bonus,
                "v44_semantic_payoff_reasons": v44_payoff_reasons,
                "v44_semantic_payoff_confidence": v44_payoff_confidence,
                "setup_strength": story_diagnostics["setup_strength"],
                "payoff_strength": story_diagnostics["payoff_strength"],
                "continuation_risk": story_diagnostics["continuation_risk"],
                "story_completeness_estimate": story_diagnostics["story_completeness_estimate"],
                "story_editor_ok": story_editor_ok,
                "natural_editor_score": natural_editor_score,
                "true_creator_score": true_creator_score,
                "editor_reasons": editor_reasons,
                "true_creator_reasons": true_creator_reasons,
                "v40_narrative_score": v40_narrative_score,
                "v40_narrative_reasons": v40_narrative_reasons,
            })
            continue

        payoff_extension_attempted = False
        payoff_extension_seconds = 0
        payoff_extension_improved = False
        payoff_extension_reasons = []

        payoff_extension = v42_guarded_payoff_extension(
            segments,
            start,
            final_end,
            detected_niche,
            low_confidence_asr,
            story_editor_ok,
            {
                "payoff_bonus": payoff_bonus,
                "v40_narrative_score": v40_narrative_score,
                "arc_bonus": v6_arc_bonus,
                "story_diagnostics": story_diagnostics,
            }
        )
        if payoff_extension is not None:
            payoff_extension_attempted = True
            payoff_extension_reasons = payoff_extension.get("payoff_extension_reasons", [])

        if payoff_extension and payoff_extension.get("accepted") is True:
            extension_story_ok = (
                story_niche
                and v19_is_clean_boundary(
                    payoff_extension.get("true_creator_reasons", []),
                    payoff_extension.get("editor_reasons", [])
                )
                and safe_float(payoff_extension.get("natural_editor_score")) >= 18
                and safe_float(payoff_extension.get("true_creator_score")) >= 20
                and safe_float(payoff_extension.get("v40_narrative_score")) >= 18
                and safe_float(payoff_extension.get("context_quality")) >= -18
                and replayability >= -12
            )
            if story_niche and not extension_story_ok:
                payoff_extension_reasons = ["extension_failed_story_editor_guard"]
            else:
                final_end = safe_float(payoff_extension.get("end"), final_end)
                combined_text = payoff_extension.get("text", combined_text)
                start_text = payoff_extension.get("start_text", start_text)
                end_text = payoff_extension.get("end_text", end_text)
                payoff_bonus = payoff_extension.get("payoff_bonus", payoff_bonus)
                context_quality = payoff_extension.get("context_quality", context_quality)
                natural_editor_score = payoff_extension.get("natural_editor_score", natural_editor_score)
                editor_reasons = payoff_extension.get("editor_reasons", editor_reasons)
                true_creator_score = payoff_extension.get("true_creator_score", true_creator_score)
                true_creator_reasons = payoff_extension.get("true_creator_reasons", true_creator_reasons)
                v40_narrative_score = payoff_extension.get("v40_narrative_score", v40_narrative_score)
                v40_narrative_reasons = payoff_extension.get("v40_narrative_reasons", v40_narrative_reasons)
                v43_payoff_bonus = payoff_extension.get("v43_hinglish_payoff_bonus", v43_payoff_bonus)
                v43_payoff_reasons = payoff_extension.get("v43_hinglish_payoff_reasons", v43_payoff_reasons)
                v44_payoff_bonus = payoff_extension.get("v44_semantic_payoff_score", v44_payoff_bonus)
                v44_payoff_reasons = payoff_extension.get("v44_semantic_payoff_reasons", v44_payoff_reasons)
                v44_payoff_confidence = payoff_extension.get("v44_semantic_payoff_confidence", v44_payoff_confidence)
                story_diagnostics = payoff_extension.get("story_diagnostics", story_diagnostics)
                story_editor_ok = extension_story_ok if story_niche else story_editor_ok

                quality_boost = viral_quality_boost(combined_text)
                v6_arc_bonus = v6_story_arc_bonus(combined_text)
                emotional_momentum = v6_emotional_momentum_bonus(combined_text)
                pacing_bonus = v6_creator_pacing_bonus(combined_text)
                v43_payoff_bonus, v43_payoff_reasons = v43_hinglish_payoff_bonus(combined_text)
                v44_payoff_bonus, v44_payoff_reasons, v44_payoff_confidence = v44_semantic_payoff_score(combined_text)
                dead_zone_penalty = (
                    v6_dead_zone_penalty(combined_text)
                    + v7_stronger_dead_zone_penalty(combined_text)
                )
                emotional_spike = v10_emotional_spike_score(combined_text)
                replayability = v10_replayability_score(combined_text)
                human_reaction_score, human_reaction_reasons = v15_human_reaction_score(combined_text)
                creator_retention = v10_creator_retention_score(start_text, end_text)
                middle_text = combined_text[len(combined_text)//3 : (len(combined_text)*2)//3]
                v33_story_score, v33_story_reasons = v33_story_arc_score(
                    start_text,
                    middle_text,
                    end_text
                )
                v39_story_quality, v39_story_reasons = v39_niche_story_quality(
                    combined_text,
                    start_text,
                    end_text,
                    detected_niche
                )
                v19_native_score, v19_native_reasons = v19_niche_native_signals(
                    combined_text,
                    detected_niche
                )
                visual_score, visual_reasons = v23_visual_clip_score(
                    start,
                    final_end,
                    visual_intelligence or {}
                )
                payoff_extension_seconds = payoff_extension.get("extension_seconds", 0)
                payoff_extension_improved = True

        original_combined_text = combined_text
        local_asr = v48_candidate_asr_stability(start, final_end, asr_stability_chunks)
        v49_9_repair = v49_9_repaired_window_status(job_id, start, final_end)
        v50_repaired_payload = v50_effective_repaired_text_payload(
            combined_text,
            start_text,
            end_text,
            local_asr,
            v49_9_repair,
        )
        combined_text = v50_repaired_payload["combined_text"]
        start_text = v50_repaired_payload["start_text"]
        end_text = v50_repaired_payload["end_text"]
        local_asr = v50_repaired_payload["local_asr"]

        quality_boost = viral_quality_boost(combined_text)
        v6_arc_bonus = v6_story_arc_bonus(combined_text)
        emotional_momentum = v6_emotional_momentum_bonus(combined_text)
        pacing_bonus = v6_creator_pacing_bonus(combined_text)
        v43_payoff_bonus, v43_payoff_reasons = v43_hinglish_payoff_bonus(combined_text)
        v44_payoff_bonus, v44_payoff_reasons, v44_payoff_confidence = v44_semantic_payoff_score(combined_text)
        if v44_payoff_quality_block(combined_text):
            payoff_bonus = 0
        else:
            payoff_bonus = max(
                v6_payoff_bonus(combined_text),
                v7_better_payoff_bonus(combined_text),
                v43_payoff_bonus,
                v44_payoff_bonus
            )
        dead_zone_penalty = (
            v6_dead_zone_penalty(combined_text)
            + v7_stronger_dead_zone_penalty(combined_text)
        )
        context_quality = v7_context_quality_score(combined_text)
        emotional_spike = v10_emotional_spike_score(combined_text)
        replayability = v10_replayability_score(combined_text)
        human_reaction_score, human_reaction_reasons = v15_human_reaction_score(combined_text)
        natural_editor_score, editor_reasons = v8_natural_editor_grade(
            combined_text,
            start_text,
            end_text
        )
        true_creator_score, true_creator_reasons = v9_true_creator_grade(
            combined_text,
            start_text,
            end_text
        )
        creator_retention = v10_creator_retention_score(start_text, end_text)
        middle_text = combined_text[len(combined_text)//3 : (len(combined_text)*2)//3]
        v33_story_score, v33_story_reasons = v33_story_arc_score(
            start_text,
            middle_text,
            end_text
        )
        v39_story_quality, v39_story_reasons = v39_niche_story_quality(
            combined_text,
            start_text,
            end_text,
            detected_niche
        )
        v40_narrative_score, v40_narrative_reasons = v40_narrative_quality_score(
            combined_text,
            start_text,
            end_text,
            detected_niche
        )
        v19_native_score, v19_native_reasons = v19_niche_native_signals(
            combined_text,
            detected_niche
        )
        story_diagnostics = v41_story_diagnostics(
            combined_text,
            start_text,
            end_text,
            context_quality,
            payoff_bonus,
            editor_reasons,
            true_creator_reasons,
            v40_narrative_score,
            v40_narrative_reasons,
            v6_arc_bonus,
        )
        story_editor_ok = (
            story_niche
            and v19_is_clean_boundary(true_creator_reasons, editor_reasons)
            and natural_editor_score >= 18
            and true_creator_score >= 20
            and v40_narrative_score >= 18
            and context_quality >= -18
            and replayability >= -12
        )

        clip_title = v9_editorial_title(combined_text, set())
        asr_stability_adjustment = v48_asr_stability_score_adjustment(local_asr)
        semantic_asr = v48_semantic_asr_confidence(combined_text)
        semantic_asr_score_adjustment = v48_semantic_asr_score_adjustment(semantic_asr)
        v49_8_repair = v49_8_targeted_asr_repair(combined_text, local_asr)
        repaired_window_available = bool(v49_9_repair.get("v49_9_repaired_window_available"))
        segment_salvage = v49_segment_salvage_decision(
            start,
            final_end,
            v48_candidate_asr_stability(start, final_end, asr_stability_chunks),
            asr_stability_chunks,
            repaired_window_available=repaired_window_available,
        )

        final_score_before_asr_stability = (
            v.get("score", 0)
            + hook_bonus
            + quality_boost
            + v6_arc_bonus
            + emotional_momentum
            + pacing_bonus
            + payoff_bonus
            + dead_zone_penalty
            + min(12, context_quality)
            + emotional_spike
            + replayability
            + min(18, human_reaction_score)
            + min(20, v19_native_score)
            + min(18, max(-24, v33_story_score))
            + min(20, max(-30, v39_story_quality))
            + min(28, max(-30, v40_narrative_score))
            + min(12, visual_score)
            + creator_retention
            + min(35, natural_editor_score)
            + min(40, true_creator_score)
            + feedback_boost
        )
        score_before_semantic_asr_adjustment = final_score_before_asr_stability + asr_stability_adjustment
        final_score = score_before_semantic_asr_adjustment + semantic_asr_score_adjustment

        if asr_stability_adjustment > 0:
            print(
                "CLEAN_WINDOW_BOOST "
                f"candidate_index={candidate_index} start={round(start, 2)} end={round(final_end, 2)} "
                f"original_score={final_score_before_asr_stability} adjusted_score={score_before_semantic_asr_adjustment} "
                f"label={local_asr['local_asr_confidence_label']} "
                f"unstable_overlap={local_asr['unstable_window_overlap_ratio']}"
            )
        elif asr_stability_adjustment < 0:
            print(
                "UNSTABLE_WINDOW_PENALTY "
                f"candidate_index={candidate_index} start={round(start, 2)} end={round(final_end, 2)} "
                f"original_score={final_score_before_asr_stability} adjusted_score={score_before_semantic_asr_adjustment} "
                f"label={local_asr['local_asr_confidence_label']} "
                f"unstable_overlap={local_asr['unstable_window_overlap_ratio']}"
            )

        if semantic_asr_score_adjustment < 0:
            print(
                "SEMANTIC_ASR_PENALTY "
                f"candidate_index={candidate_index} start={round(start, 2)} end={round(final_end, 2)} "
                f"label={semantic_asr['semantic_asr_confidence_label']} "
                f"corruption_score={semantic_asr['semantic_asr_corruption_score']} "
                f"score_before={score_before_semantic_asr_adjustment} score_after={final_score} "
                f"reasons={';'.join(semantic_asr['semantic_asr_reasons'][:5])}"
            )

        if segment_salvage["segment_salvage_decision"] == "quarantined_unstable":
            funnel_row.update({
                "filter_decision": "asr_segment_quarantined",
                "filter_reason": segment_salvage["segment_salvage_reason"],
                "expanded_start": round(start, 2),
                "expanded_end": round(final_end, 2),
                "expanded_duration": round(final_end - start, 2),
                "expanded_preview": candidate_funnel_preview(combined_text),
                "detected_niche": detected_niche,
                "final_score": safe_float(final_score),
                "local_asr_confidence_label": local_asr["local_asr_confidence_label"],
                "unstable_window_overlap_ratio": local_asr["unstable_window_overlap_ratio"],
                "chunk_confidence_score": local_asr["chunk_confidence_score"],
                "local_asr_reasons": local_asr["local_asr_reasons"][:5],
                "asr_stability_score_adjustment": asr_stability_adjustment,
                "semantic_asr_confidence_label": semantic_asr["semantic_asr_confidence_label"],
                "semantic_asr_corruption_score": semantic_asr["semantic_asr_corruption_score"],
                "semantic_asr_reasons": semantic_asr["semantic_asr_reasons"][:5],
                "semantic_asr_score_adjustment": semantic_asr_score_adjustment,
                "score_before_semantic_asr_adjustment": score_before_semantic_asr_adjustment,
                **v49_8_repair,
                **v49_9_repair,
                **v50_repaired_payload["metadata"],
                **segment_salvage,
            })
            v49_log_asr_segment_salvage(
                job_id,
                "ASR_SEGMENT_QUARANTINED",
                candidate_index,
                start,
                final_end,
                local_asr,
                segment_salvage,
            )
            continue

        v49_log_asr_segment_salvage(
            job_id,
            "ASR_SEGMENT_SALVAGE_ALLOWED",
            candidate_index,
            start,
            final_end,
            local_asr,
            segment_salvage,
        )

        funnel_row.update({
            "filter_decision": "accepted_pre_dedupe",
            "filter_reason": "passed_build_final_filters",
            "expanded_start": round(start, 2),
            "expanded_end": round(final_end, 2),
            "expanded_duration": round(final_end - start, 2),
            "expanded_preview": candidate_funnel_preview(combined_text),
            "detected_niche": detected_niche,
            "final_score": safe_float(final_score),
            "hook_bonus": hook_bonus,
            "quality_boost": quality_boost,
            "v6_arc_bonus": v6_arc_bonus,
            "emotional_momentum": emotional_momentum,
            "pacing_bonus": pacing_bonus,
            "payoff_bonus": payoff_bonus,
            "v43_hinglish_payoff_bonus": v43_payoff_bonus,
            "v43_hinglish_payoff_reasons": v43_payoff_reasons,
            "v44_semantic_payoff_score": v44_payoff_bonus,
            "v44_semantic_payoff_reasons": v44_payoff_reasons,
            "v44_semantic_payoff_confidence": v44_payoff_confidence,
            "setup_strength": story_diagnostics["setup_strength"],
            "payoff_strength": story_diagnostics["payoff_strength"],
            "continuation_risk": story_diagnostics["continuation_risk"],
            "context_density": story_diagnostics["context_density"],
            "story_completeness_estimate": story_diagnostics["story_completeness_estimate"],
            "story_editor_ok": story_editor_ok,
            "natural_editor_score": natural_editor_score,
            "true_creator_score": true_creator_score,
            "editor_reasons": editor_reasons,
            "true_creator_reasons": true_creator_reasons,
            "v40_narrative_score": v40_narrative_score,
            "v40_narrative_reasons": v40_narrative_reasons,
            "payoff_extension_attempted": payoff_extension_attempted,
            "payoff_extension_seconds": payoff_extension_seconds,
            "payoff_extension_improved": payoff_extension_improved,
            "payoff_extension_reasons": payoff_extension_reasons[:5],
            "local_asr_confidence_label": local_asr["local_asr_confidence_label"],
            "unstable_window_overlap_ratio": local_asr["unstable_window_overlap_ratio"],
            "chunk_confidence_score": local_asr["chunk_confidence_score"],
            "asr_stability_score_adjustment": asr_stability_adjustment,
            "semantic_asr_confidence_label": semantic_asr["semantic_asr_confidence_label"],
            "semantic_asr_corruption_score": semantic_asr["semantic_asr_corruption_score"],
            "semantic_asr_reasons": semantic_asr["semantic_asr_reasons"][:5],
            "semantic_asr_score_adjustment": semantic_asr_score_adjustment,
            "score_before_semantic_asr_adjustment": score_before_semantic_asr_adjustment,
            **v49_8_repair,
            **v49_9_repair,
            **v50_repaired_payload["metadata"],
            **segment_salvage,
        })

        clips.append({
            "start": round(start, 2),
            "end": round(final_end, 2),
            "source_text": text,
            "expanded_text": combined_text,
            "title": clip_title,
            "hashtags": (
                v40_niche_hashtags(detected_niche, combined_text)
            ),
            "niche": detected_niche or v.get("niche", "general"),
            "score": final_score,
            "score_breakdown": {
                **v.get("score_breakdown", {}),
                "candidate_funnel_index": candidate_index,
                "hook_bonus": hook_bonus,
                "quality_boost": quality_boost,
                "v6_arc_bonus": v6_arc_bonus,
                "emotional_momentum": emotional_momentum,
                "pacing_bonus": pacing_bonus,
                "payoff_bonus": payoff_bonus,
                "v43_hinglish_payoff_bonus": v43_payoff_bonus,
                "v43_hinglish_payoff_reasons": v43_payoff_reasons,
                "v44_semantic_payoff_score": v44_payoff_bonus,
                "v44_semantic_payoff_reasons": v44_payoff_reasons,
                "v44_semantic_payoff_confidence": v44_payoff_confidence,
                "dead_zone_penalty": dead_zone_penalty,
                "context_quality": context_quality,
                  "detected_niche": detected_niche,
                  "emotional_spike": emotional_spike,
                  "replayability": replayability,
                  "human_reaction_score": human_reaction_score,
                  "human_reaction_reasons": human_reaction_reasons,
                  "short_explosive_ok": short_explosive_ok,
                  "finance_editor_ok": finance_editor_ok,
                  "story_editor_ok": story_editor_ok,
                  "creator_retention": creator_retention,
                "natural_editor_score": natural_editor_score,
                "editor_reasons": editor_reasons,
                "true_creator_score": true_creator_score,
                "true_creator_reasons": true_creator_reasons,
                "v19_native_score": v19_native_score,
                "v19_native_reasons": v19_native_reasons,
                "v33_story_score": v33_story_score,
                "v33_story_reasons": v33_story_reasons,
                "v39_story_quality": v39_story_quality,
                "v39_story_reasons": v39_story_reasons,
                "v40_narrative_score": v40_narrative_score,
                "v40_narrative_reasons": v40_narrative_reasons,
                "setup_strength": story_diagnostics["setup_strength"],
                "payoff_strength": story_diagnostics["payoff_strength"],
                "continuation_risk": story_diagnostics["continuation_risk"],
                "context_density": story_diagnostics["context_density"],
                "story_completeness_estimate": story_diagnostics["story_completeness_estimate"],
                "payoff_extension_attempted": payoff_extension_attempted,
                "payoff_extension_seconds": payoff_extension_seconds,
                "payoff_extension_improved": payoff_extension_improved,
                "payoff_extension_reasons": payoff_extension_reasons[:5],
                "visual_score": visual_score,
                "visual_reasons": visual_reasons,
                "feedback_boost": feedback_boost,
                "feedback_reasons": feedback_reasons,
                "asr_mode": asr_mode,
                "asr_quality_score": asr_quality_score,
                "asr_quality_reasons": asr_quality_reasons[:5],
                "low_confidence_asr": low_confidence_asr,
                "local_asr_confidence_label": local_asr["local_asr_confidence_label"],
                "unstable_window_overlap_ratio": local_asr["unstable_window_overlap_ratio"],
                "chunk_confidence_score": local_asr["chunk_confidence_score"],
                "local_asr_reasons": local_asr["local_asr_reasons"][:5],
                "asr_stability_score_adjustment": asr_stability_adjustment,
                "score_before_asr_stability_adjustment": final_score_before_asr_stability,
                "semantic_asr_confidence_label": semantic_asr["semantic_asr_confidence_label"],
                "semantic_asr_corruption_score": semantic_asr["semantic_asr_corruption_score"],
                "semantic_asr_reasons": semantic_asr["semantic_asr_reasons"][:5],
                "semantic_asr_score_adjustment": semantic_asr_score_adjustment,
                "score_before_semantic_asr_adjustment": score_before_semantic_asr_adjustment,
                **v49_8_repair,
                **v49_9_repair,
                **v50_repaired_payload["metadata"],
                **segment_salvage,
                "start_text": start_text,
                "end_text": end_text
            }
        })

    if len(clips) == 0:
        print("ðŸ”¥ V19 RECOVERY: no primary clips survived; trying strict fallback")
        recovered = v19_recover_fallback_clips(viral, segments)
        existing = {(round(c.get("start", 0), 1), round(c.get("end", 0), 1)) for c in clips}
        for r in recovered:
            sb = r.get("score_breakdown", {}) if isinstance(r.get("score_breakdown"), dict) else {}
            if (
                r.get("niche") == "finance_economics"
                and (
                    sb.get("v19_native_score", 0) < 14
                    or v38_text_quality_is_severe(r.get("expanded_text", ""))
                )
            ):
                continue
            key = (round(r.get("start", 0), 1), round(r.get("end", 0), 1))
            if key not in existing:
                local_asr = v48_candidate_asr_stability(
                    safe_float(r.get("start")),
                    safe_float(r.get("end")),
                    asr_stability_chunks,
                )
                v49_9_repair = v49_9_repaired_window_status(
                    job_id,
                    safe_float(r.get("start")),
                    safe_float(r.get("end")),
                )
                v50_repaired_payload = v50_effective_repaired_text_payload(
                    r.get("expanded_text") or r.get("source_text") or "",
                    str(r.get("score_breakdown", {}).get("start_text") or r.get("expanded_text") or r.get("source_text") or ""),
                    str(r.get("score_breakdown", {}).get("end_text") or r.get("expanded_text") or r.get("source_text") or ""),
                    local_asr,
                    v49_9_repair,
                )
                if v50_repaired_payload["metadata"].get("v50_repaired_text_applied"):
                    r["expanded_text"] = v50_repaired_payload["combined_text"]
                segment_salvage = v49_segment_salvage_decision(
                    safe_float(r.get("start")),
                    safe_float(r.get("end")),
                    local_asr,
                    asr_stability_chunks,
                    repaired_window_available=bool(v49_9_repair.get("v49_9_repaired_window_available")),
                )
                v49_8_repair = v49_8_targeted_asr_repair(
                    r.get("expanded_text") or r.get("source_text") or "",
                    local_asr,
                )
                r.setdefault("score_breakdown", {})["asr_mode"] = asr_mode
                r.setdefault("score_breakdown", {})["asr_quality_score"] = asr_quality_score
                r.setdefault("score_breakdown", {})["asr_quality_reasons"] = asr_quality_reasons[:5]
                r.setdefault("score_breakdown", {})["low_confidence_asr"] = low_confidence_asr
                r.setdefault("score_breakdown", {})["local_asr_confidence_label"] = local_asr["local_asr_confidence_label"]
                r.setdefault("score_breakdown", {})["unstable_window_overlap_ratio"] = local_asr["unstable_window_overlap_ratio"]
                r.setdefault("score_breakdown", {})["chunk_confidence_score"] = local_asr["chunk_confidence_score"]
                r.setdefault("score_breakdown", {})["local_asr_reasons"] = local_asr["local_asr_reasons"][:5]
                r.setdefault("score_breakdown", {})["asr_stability_score_adjustment"] = 0
                r.setdefault("score_breakdown", {}).update(v49_8_repair)
                r.setdefault("score_breakdown", {}).update(v49_9_repair)
                r.setdefault("score_breakdown", {}).update(v50_repaired_payload["metadata"])
                r.setdefault("score_breakdown", {}).update(segment_salvage)
                if segment_salvage["segment_salvage_decision"] == "quarantined_unstable":
                    v49_log_asr_segment_salvage(
                        job_id,
                        "ASR_SEGMENT_QUARANTINED",
                        None,
                        r.get("start"),
                        r.get("end"),
                        local_asr,
                        segment_salvage,
                    )
                    continue
                v49_log_asr_segment_salvage(
                    job_id,
                    "ASR_SEGMENT_SALVAGE_ALLOWED",
                    None,
                    r.get("start"),
                    r.get("end"),
                    local_asr,
                    segment_salvage,
                )
                clips.append(r)
                existing.add(key)
            if len(clips) >= 1:
                break
        print(f"ðŸ”¥ V19 RECOVERY total clips: {len(clips)}")
        if len(clips) == 0:
            write_candidate_funnel_rows(job_id, candidate_funnel_rows)
            print("ðŸ”¥ V19 DIAGNOSTIC SUMMARY")
            print(f"ðŸ”¥ Viral candidates received: {len(viral[:20])}")
            raise Exception("No valid viral clips found after universal V19 filtering")

    clips = sorted(clips, key=lambda x: x.get("score", 0), reverse=True)
    clips = v48_apply_semantic_clean_preference(clips)

    # ðŸ”¥ V6.2 dominant niche lock
    niche_counts = {}
    for c in clips:
        n = c.get('niche', 'general')
        niche_counts[n] = niche_counts.get(n, 0) + 1

    dominant_niche = max(niche_counts, key=niche_counts.get) if niche_counts else 'general'

    for c in clips:
        if c.get('niche') == 'general':
            c['niche'] = dominant_niche

    unique = []

    for c in clips:
        duplicate = False
        candidate_index = None
        sb = c.get("score_breakdown", {}) if isinstance(c.get("score_breakdown"), dict) else {}
        if sb.get("candidate_funnel_index") is not None:
            candidate_index = int(safe_float(sb.get("candidate_funnel_index"), -1))
        if candidate_index is not None and 0 <= candidate_index < len(candidate_funnel_rows):
            candidate_funnel_rows[candidate_index]["semantic_preference_applied"] = bool(
                sb.get("semantic_preference_applied")
            )
            candidate_funnel_rows[candidate_index]["semantic_preference_reason"] = (
                sb.get("semantic_preference_reason") or ""
            )

        for u in unique:
            text_c = c.get("expanded_text") or get_nearby_text(segments, c["start"], c["end"], 0)
            text_u = u.get("expanded_text") or get_nearby_text(segments, u["start"], u["end"], 0)

            if (
                _v8_context_overlap(text_c, text_u) >= 0.62
                or abs(c["start"] - u["start"]) < 12
            ):
                duplicate = True
                break

        if not duplicate:
            unique.append(c)
            if candidate_index is not None and 0 <= candidate_index < len(candidate_funnel_rows):
                candidate_funnel_rows[candidate_index]["filter_decision"] = "accepted"
                candidate_funnel_rows[candidate_index]["filter_reason"] = "selected_after_dedupe"
        elif candidate_index is not None and 0 <= candidate_index < len(candidate_funnel_rows):
            candidate_funnel_rows[candidate_index]["filter_decision"] = "duplicate_removed"
            candidate_funnel_rows[candidate_index]["filter_reason"] = "overlap_or_near_start_duplicate"

        if len(unique) >= MAX_TOTAL_CLIPS:
            break

    write_candidate_funnel_rows(job_id, candidate_funnel_rows)
    for c in unique:
        sb = c.get("score_breakdown", {}) if isinstance(c.get("score_breakdown"), dict) else {}
        sb.pop("candidate_funnel_index", None)
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


def creator_qa_asr_gate_decision(clip):
    clip = clip if isinstance(clip, dict) else {}
    sb = clip.get("score_breakdown", {}) if isinstance(clip.get("score_breakdown"), dict) else {}

    if sb.get("low_confidence_asr") is not True:
        return {
            "reject": False,
            "decision": "global_asr_not_low_confidence",
            "reasons": [],
        }

    local_label = str(sb.get("local_asr_confidence_label") or "missing")
    semantic_label = str(sb.get("semantic_asr_confidence_label") or "missing")
    semantic_score_present = sb.get("semantic_asr_corruption_score") is not None
    semantic_score = safe_float(sb.get("semantic_asr_corruption_score"), 999)
    reasons = []

    if local_label not in {"clean", "borderline"}:
        reasons.append(f"local_asr_not_safe={local_label}")
    if semantic_label not in {"clean_semantics", "borderline_semantics"}:
        reasons.append(f"semantic_asr_not_safe={semantic_label}")
    if not semantic_score_present:
        reasons.append("semantic_asr_corruption_score_missing")
    elif semantic_label == "clean_semantics" and semantic_score > 15:
        reasons.append(f"clean_semantics_score_gt_15={semantic_score}")
    elif semantic_label == "borderline_semantics" and semantic_score > 30:
        reasons.append(f"borderline_semantics_score_gt_30={semantic_score}")

    if reasons:
        return {
            "reject": True,
            "decision": "global_asr_low_confidence_retained",
            "reasons": reasons,
            "local_asr_confidence_label": local_label,
            "semantic_asr_confidence_label": semantic_label,
            "semantic_asr_corruption_score": semantic_score if semantic_score_present else None,
        }

    return {
        "reject": False,
        "decision": "asr_global_low_confidence_bypassed_by_local_semantic_confidence",
        "reasons": ["local_and_semantic_asr_within_safe_thresholds"],
        "local_asr_confidence_label": local_label,
        "semantic_asr_confidence_label": semantic_label,
        "semantic_asr_corruption_score": semantic_score,
    }


def creator_qa_rejection_reasons(clip, captions=None):
    reasons = []
    clip = clip if isinstance(clip, dict) else {}
    captions = safe_dict_list(captions or [])
    sb = clip.get("score_breakdown", {}) if isinstance(clip.get("score_breakdown"), dict) else {}

    text = str(clip.get("expanded_text") or clip.get("source_text") or "").strip()
    low = text.lower()
    start_text = str(sb.get("start_text") or text).strip()
    end_text = str(sb.get("end_text") or text).strip()
    start_low = start_text.lower()
    end_low = end_text.lower()

    weak_start_phrases = [
        "and ", "but ", "so ", "because ", "then ", "now ", "also ",
        "after that", "at that time", "one will", "these are",
        "you think", "come,", "now come", "if ", "which ", "that "
    ]
    if any(start_low.startswith(p) for p in weak_start_phrases):
        reasons.append("weak_continuation_start")

    malformed_patterns = [
        r"\bthe film will time\b",
        r"\byou can the\b",
        r"\bi not i would\b",
        r"\bit does mean that\b",
        r"\byou still him\b",
        r"\bif he is complete\b",
        r"\bwe will very\b",
        r"\bone will on\b",
        r"\btime had then\b",
        r"\byou one phone\b",
        r"\bhow did write\b",
    ]
    caption_text = " ".join(str(c.get("text", "")) for c in captions)
    grammar_blob = f"{low} {caption_text.lower()}"
    if any(re.search(p, grammar_blob) for p in malformed_patterns):
        reasons.append("malformed_grammar")

    asr_gate = creator_qa_asr_gate_decision(clip)
    sb["creator_qa_asr_gate_decision"] = asr_gate.get("decision")
    sb["creator_qa_asr_gate_reasons"] = asr_gate.get("reasons", [])[:5]
    if asr_gate.get("reject"):
        reasons.append("asr_low_confidence")
        print(
            "CREATOR_QA_ASR_GATE_RETAINED "
            f"start={safe_float(clip.get('start'))} end={safe_float(clip.get('end'))} "
            f"local_asr_confidence_label={asr_gate.get('local_asr_confidence_label')} "
            f"semantic_asr_confidence_label={asr_gate.get('semantic_asr_confidence_label')} "
            f"semantic_asr_corruption_score={asr_gate.get('semantic_asr_corruption_score')} "
            f"reasons={';'.join(asr_gate.get('reasons', [])[:5])}"
        )
    elif asr_gate.get("decision") == "asr_global_low_confidence_bypassed_by_local_semantic_confidence":
        print(
            "CREATOR_QA_ASR_GATE_LOCAL_SEMANTIC_BYPASS "
            f"start={safe_float(clip.get('start'))} end={safe_float(clip.get('end'))} "
            f"local_asr_confidence_label={asr_gate.get('local_asr_confidence_label')} "
            f"semantic_asr_confidence_label={asr_gate.get('semantic_asr_confidence_label')} "
            f"semantic_asr_corruption_score={asr_gate.get('semantic_asr_corruption_score')} "
            f"reasons={';'.join(asr_gate.get('reasons', [])[:5])}"
        )

    v50_1_signal = v50_1_payoff_setup_signal(text, sb)
    sb["v50_1_payoff_detected"] = v50_1_signal.get("v50_1_payoff_detected")
    sb["v50_1_setup_detected"] = v50_1_signal.get("v50_1_setup_detected")
    sb["v50_1_payoff_reason"] = v50_1_signal.get("v50_1_payoff_reason")
    sb["v50_1_no_hook_no_payoff_override"] = v50_1_signal.get("v50_1_no_hook_no_payoff_override")

    if (
        safe_float(sb.get("payoff_bonus")) == 0
        and safe_float(sb.get("hook_bonus")) == 0
        and not v50_1_signal.get("v50_1_no_hook_no_payoff_override")
    ):
        reasons.append("no_hook_no_payoff")

    context_quality = safe_float(sb.get("context_quality"))
    if context_quality < 8 or len(_v8_word_set(text)) < 6:
        reasons.append("weak_standalone_context")

    incomplete_endings = (
        "and", "but", "because", "so", "then", "that", "if", "in",
        "to", "from", "with", "for", "is", "has", "will", "would"
    )
    editor_reasons = sb.get("editor_reasons", [])
    creator_reasons = sb.get("true_creator_reasons", [])
    if not isinstance(editor_reasons, list):
        editor_reasons = []
    if not isinstance(creator_reasons, list):
        creator_reasons = []

    if (
        end_low.endswith(incomplete_endings)
        or "weak_ending" in editor_reasons
        or "weak_creator_ending" in creator_reasons
    ):
        reasons.append("incomplete_ending")

    return reasons


def creator_qa_metadata_reasons(clip):
    notes = []
    clip = clip if isinstance(clip, dict) else {}
    sb = clip.get("score_breakdown", {}) if isinstance(clip.get("score_breakdown"), dict) else {}

    text = str(clip.get("expanded_text") or clip.get("source_text") or "").strip()
    start_text = str(sb.get("start_text") or text).strip().lower()
    end_text = str(sb.get("end_text") or text).strip().lower()
    words = text.split()

    if start_text.startswith((
        "and ", "but ", "so ", "because ", "then ", "which ", "that ", "if ",
        "after that", "at that time", "now come"
    )):
        notes.append("mid_thought_start")

    if safe_float(sb.get("context_quality")) < 8:
        notes.append("missing_setup")

    if safe_float(sb.get("payoff_bonus")) <= 0 and (
        end_text.endswith(("and", "but", "because", "so", "then"))
        or "weak_ending" in (sb.get("editor_reasons") or [])
        or "weak_creator_ending" in (sb.get("true_creator_reasons") or [])
    ):
        notes.append("weak_payoff")

    if len(words) > 170:
        notes.append("overextended_context")

    return notes


def apply_creator_qa(job_id, clips, captions):
    approved = []
    rejected = []

    for clip in safe_dict_list(clips):
        clip_start = safe_float(clip.get("start"))
        clip_end = safe_float(clip.get("end"))
        clip_captions = get_captions_for_clip(captions, clip_start, clip_end)
        metadata_reasons = creator_qa_metadata_reasons(clip)
        if metadata_reasons:
            clip.setdefault("score_breakdown", {})["creator_qa_metadata_reasons"] = metadata_reasons
        reasons = creator_qa_rejection_reasons(clip, clip_captions)

        if reasons:
            row = {
                "ts": time.time(),
                "job_id": job_id,
                "event": "CREATOR_QA_REJECT",
                "start": clip.get("start"),
                "end": clip.get("end"),
                "title": clip.get("title"),
                "reasons": reasons,
                "metadata_reasons": metadata_reasons,
                "preview": v18_preview_text(clip.get("expanded_text"), 260),
            }
            rejected.append(row)
            print(
                "CREATOR_QA_REJECT "
                f"start={row['start']} end={row['end']} "
                f"reasons={reasons} title={row['title']}"
            )
            continue

        approved.append(clip)

    if rejected:
        try:
            Path("analytics").mkdir(exist_ok=True)
            with (Path("analytics") / "creator_qa.jsonl").open("a", encoding="utf-8") as f:
                for row in rejected:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"creator QA logging failed: {e}")

    print(f"Creator QA clips before={len(clips)} after={len(approved)} rejected={len(rejected)}")
    return approved, rejected


def creator_qa_top_reasons(rejections, limit=5):
    counts = {}
    for row in safe_dict_list(rejections):
        reasons = row.get("reasons", [])
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            reason = str(reason)
            counts[reason] = counts.get(reason, 0) + 1

    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    ]


def log_creator_qa_zero_safe_clips(job_id, rejections):
    row = {
        "ts": time.time(),
        "job_id": job_id,
        "event": "CREATOR_QA_ZERO_SAFE_CLIPS",
        "message": "No creator-safe clips found",
        "rejected_count": len(safe_dict_list(rejections)),
        "top_rejection_reasons": creator_qa_top_reasons(rejections),
    }

    print(
        "CREATOR_QA_ZERO_SAFE_CLIPS "
        f"job_id={job_id} rejected={row['rejected_count']} "
        f"top_reasons={row['top_rejection_reasons']}"
    )

    try:
        Path("analytics").mkdir(exist_ok=True)
        with (Path("analytics") / "creator_qa.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"creator QA zero-safe logging failed: {e}")

    return row


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
                    print(f"ðŸ§¹ Removed old generated file: {name}")
                except Exception:
                    pass
                break




def v13_delayed_job_cleanup(job_id, delay=300):
    """
    Production-safe cleanup:
    remove only heavy temp/original files after job completion.
    Keep final clips + thumbnails for frontend downloads.
    """

    try:
        print(f"ðŸ§¹ Cleanup scheduled for job {job_id} in {delay}s")
        time.sleep(delay)

        patterns = [
            f"uploads/{job_id}.mp4",
            f"uploads/{job_id}_input_raw_*",
            f"uploads/{job_id}_input_clip_*",
            f"uploads/{job_id}*.ass",
            f"uploads/{job_id}*.srt",
            f"uploads/{job_id}*.wav",
        ]

        deleted = 0

        for pattern in patterns:
            for path in glob.glob(pattern):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        deleted += 1
                        print(f"ðŸ§¹ Deleted temp file: {path}")
                except Exception as e:
                    print(f"âš  Cleanup failed for {path}: {e}")

        print(f"âœ… Cleanup completed for {job_id} | deleted={deleted}")

    except Exception as e:
        print(f"âŒ Cleanup thread failed for {job_id}: {e}")





def v18_cleanup_old_files(hours=18, keep_latest_jobs=12):
    try:
        now = time.time()
        folders = [Path("uploads"), Path("outputs")]
        all_files = []

        for folder in folders:
            if folder.exists():
                all_files.extend([f for f in folder.rglob("*") if f.is_file()])

        all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        protected_job_ids = set()
        for f in all_files[:keep_latest_jobs * 15]:
            m = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', f.name)
            if m:
                protected_job_ids.add(m.group(1))

        removed = 0

        for f in all_files:
            try:
                age_hours = (now - f.stat().st_mtime) / 3600
                if age_hours < hours:
                    continue

                fname = f.name.lower()

                if any(j in fname for j in protected_job_ids):
                    continue

                removable = (
                    fname.endswith(".ass")
                    or fname.endswith(".srt")
                    or fname.endswith(".vtt")
                    or fname.endswith(".wav")
                    or "_thumbnail_" in fname
                    or "_input_raw_" in fname
                    or "_input_clip_" in fname
                    or fname.endswith(".tmp")
                    or fname.endswith(".log")
                )

                if age_hours > (hours * 2):
                    removable = removable or fname.endswith(".mp4")

                if removable:
                    os.remove(str(f))
                    removed += 1
                    print(f"ðŸ§¹ V18.3 deleted: {f}")

            except Exception as e:
                print(f"âš  cleanup scan failed {f}: {e}")

        print(f"âœ… V18.3 cleanup removed={removed}")

    except Exception as e:
        print(f"âš  V18.3 cleanup failed: {e}")


def v18_preview_text(text, limit=420):
    text = str(text or "").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."

def v18_safe_score_breakdown(score_breakdown):
    if not isinstance(score_breakdown, dict):
        return {}

    keep = [
        "hook_bonus", "quality_boost", "emotional_momentum", "pacing_bonus",
        "payoff_bonus", "dead_zone_penalty", "context_quality", "detected_niche",
        "emotional_spike", "replayability", "human_reaction_score",
        "creator_retention", "natural_editor_score", "true_creator_score",
        "caption_quality_warning", "v40_narrative_score", "story_editor_ok",
        "story_score", "v33_story_score",
        "v43_hinglish_payoff_bonus", "v44_semantic_payoff_score",
        "setup_strength", "payoff_strength", "continuation_risk",
        "context_density", "story_completeness_estimate",
        "payoff_extension_attempted", "payoff_extension_seconds",
        "payoff_extension_improved",
        "asr_mode", "asr_quality_score", "low_confidence_asr",
        "local_asr_confidence_label", "unstable_window_overlap_ratio",
        "chunk_confidence_score", "asr_stability_score_adjustment",
        "score_before_asr_stability_adjustment",
        "semantic_asr_confidence_label", "semantic_asr_corruption_score",
        "semantic_asr_score_adjustment", "score_before_semantic_asr_adjustment",
        "semantic_preference_applied", "semantic_preference_reason",
        "creator_qa_asr_gate_decision",
        "v44_semantic_payoff_confidence",
        "segment_salvage_decision", "repaired_window_required",
        "repaired_window_available", "salvage_unstable_overlap_ratio",
        "segment_salvage_reason",
        "v49_8_repair_attempted", "v49_8_repair_scope",
        "v49_8_repair_removed_repeated_tokens",
        "v49_8_repair_before_label", "v49_8_repair_before_score",
        "v49_8_repair_after_label", "v49_8_repair_after_score",
        "v49_8_repair_improved", "v49_8_repaired_window_available",
        "v49_8_repair_export_safe", "v49_8_repaired_text_preview",
        "v49_9_repair_artifact_found", "v49_9_repaired_window_available",
        "v49_9_repair_export_safe", "v49_9_repaired_local_asr_label",
        "v49_9_repaired_unstable_overlap_ratio",
        "v49_9_repaired_transcript_quality_score",
        "v49_9_repaired_low_confidence_asr",
        "v49_9_repaired_semantic_label", "v49_9_repaired_semantic_score",
        "v49_9_repaired_text_preview", "v49_9_repair_decision_reason",
        "v50_repaired_text_applied", "v50_original_text_preview",
        "v50_repaired_text_preview", "v50_repaired_text_source",
        "v50_1_payoff_detected", "v50_1_setup_detected",
        "v50_1_payoff_reason", "v50_1_no_hook_no_payoff_override",
        "v50_2_context_expanded", "v50_2_original_window",
        "v50_2_expanded_window", "v50_2_setup_source",
        "v50_2_payoff_source", "v50_2_expansion_rejected_reason",
        "v50_2_local_asr_confidence_label", "v50_2_semantic_asr_confidence_label",
        "v50_2_context_quality", "v50_2_payoff_bonus",
        "v52_payoff_anchor_detected", "v52_payoff_anchor_reason",
        "v52_generated_from_payoff_anchor", "v52_anchor_window",
    ]

    out = {}
    for k in keep:
        if k in score_breakdown:
            out[k] = score_breakdown[k]

    for k in [
        "human_reaction_reasons", "editor_reasons", "true_creator_reasons",
        "v40_narrative_reasons", "asr_quality_reasons",
        "creator_qa_metadata_reasons", "payoff_extension_reasons",
        "local_asr_reasons",
        "quarantined_unstable_windows",
        "v49_8_repair_replacements", "v49_8_repair_reasons",
        "v49_9_repair_strict_reasons",
        "creator_qa_asr_gate_reasons",
        "semantic_asr_reasons",
        "v43_hinglish_payoff_reasons", "v44_semantic_payoff_reasons"
    ]:
        v = score_breakdown.get(k)
        if isinstance(v, list):
            out[k] = v[:5]

    return out















# =========================================================
# ðŸ”¥ V34 Creator Pack Metadata
# =========================================================

def v34_creator_pack_metadata(title, text, niche, visual_score=0, story_score=0):
    try:
        text = str(text or "")
        niche = str(niche or "general")
        title = str(title or v9_editorial_title(text, set()))

        hook_type = "context_hook"

        if visual_score and visual_score > 10:
            hook_type = "visual_hook"

        if story_score and story_score > 10:
            hook_type = "story_hook"

        if niche in ["politics_news", "geopolitics"]:
            hook_type = "debate_hook"
        elif niche == "finance_economics":
            hook_type = "market_hook"

        thumbnail_text = title

        if niche in ["politics_news", "geopolitics"]:
            thumbnail_text = "Big Political Turn"
        elif niche in ["finance_business", "finance_economics"]:
            low = text.lower()
            if "trade deficit" in low or "à¤Ÿà¥à¤°à¥‡à¤¡ à¤¡à¥‡à¤«à¤¿à¤¸à¤¿à¤Ÿ" in low:
                thumbnail_text = "Trade Deficit"
            elif "import duty" in low or "à¤‡à¤®à¥à¤ªà¥‹à¤°à¥à¤Ÿ à¤¡à¥à¤¯à¥‚à¤Ÿà¥€" in low:
                thumbnail_text = "Import Duty Shock"
            elif "inflation" in low or "à¤‡à¤¨à¥à¤«à¥à¤²à¥‡à¤¶à¤¨" in low or "à¤®à¤¹à¤‚à¤—à¤¾à¤ˆ" in low:
                thumbnail_text = "Inflation Risk"
            elif "sugar" in low or "à¤¶à¥à¤—à¤°" in low or "à¤¸à¥à¤—à¤°" in low:
                thumbnail_text = "Sugar Price Shock"
            else:
                thumbnail_text = "Market Impact"
        elif niche == "crime_mystery":
            thumbnail_text = "Hidden Truth"
        elif hook_type == "visual_hook":
            thumbnail_text = "Watch This Moment"

        return {
            "hook_type": hook_type,
            "thumbnail_text": thumbnail_text[:42],
            "upload_title": title[:90],
            "short_description": v18_preview_text(text, 180),
            "suggested_cta": "Watch till the end.",
            "pack_version": "V34"
        }
    except Exception as e:
        return {"pack_version": "V34", "error": str(e)}


# =========================================================
# ðŸ”¥ V33 Story Arc Intelligence
# =========================================================

def v33_story_arc_score(start_text, middle_text, end_text):
    try:
        start_text = str(start_text or "").lower()
        middle_text = str(middle_text or "").lower()
        end_text = str(end_text or "").lower()

        score = 0
        reasons = []

        setup_words = [
            "listen", "look", "imagine", "suppose",
            "à¤¸à¥à¤¨à¤¿à¤", "à¤¸à¥‹à¤šà¤¿à¤", "à¤®à¤¾à¤¨ à¤²à¥€à¤œà¤¿à¤", "à¤¦à¥‡à¤–à¤¿à¤"
        ]

        tension_words = [
            "but", "however", "suddenly", "then",
            "à¤²à¥‡à¤•à¤¿à¤¨", "à¤«à¤¿à¤°", "à¤…à¤šà¤¾à¤¨à¤•", "à¤®à¤—à¤°", "à¤œà¤¿à¤®à¥à¤®à¥‡à¤¦à¤¾à¤°", "à¤à¥‚à¤ "
        ]

        payoff_words = [
            "therefore", "finally", "that is why", "this means",
            "à¤‡à¤¸à¤²à¤¿à¤", "à¤†à¤–à¤¿à¤°à¤•à¤¾à¤°", "à¤¯à¤¹à¥€ à¤•à¤¾à¤°à¤£", "à¤¨à¤¤à¥€à¤œà¤¾", "à¤®à¤¤à¤²à¤¬"
        ]

        drift_words = [
            "anyway", "by the way", "subscribe", "like and share",
            "à¤µà¥ˆà¤¸à¥‡", "à¤¸à¤¬à¥à¤¸à¤•à¥à¤°à¤¾à¤‡à¤¬", "à¤²à¤¾à¤‡à¤• à¤•à¤°à¥‡à¤‚"
        ]

        if any(w in start_text for w in setup_words):
            score += 10
            reasons.append("strong_setup")

        if any(w in middle_text for w in tension_words):
            score += 14
            reasons.append("tension_build")

        if any(w in end_text for w in payoff_words):
            score += 18
            reasons.append("payoff_detected")

        if any(w in end_text for w in drift_words):
            score -= 15
            reasons.append("ending_drift")

        if len(end_text.split()) < 4:
            score -= 4
            reasons.append("weak_ending")

        return round(score, 2), reasons

    except Exception as e:
        print(f"âš  V33 story arc failed: {e}")
        return 0, []


# =========================================================
# ðŸ”¥ V27 ASR Text Normalization
# =========================================================

def v27_normalize_asr_text(text):
    text = str(text or "")

    fixes = {
        # Conservative exact spelling cleanup only. Avoid broad Hindi phonetic
        # rewrites; those caused caption meaning drift and hallucinated terms.
        "à¤¬à¤¾à¤œà¥à¤ªà¤¾": "à¤­à¤¾à¤œà¤ªà¤¾",
        "à¤­à¤œà¤ªà¤¾": "à¤­à¤¾à¤œà¤ªà¤¾",
        "à¤¬à¥€ à¤œà¥‡ à¤ªà¥€": "à¤¬à¥€à¤œà¥‡à¤ªà¥€",
        "à¤ªà¤¶à¥à¤›à¤¿à¤®": "à¤ªà¤¶à¥à¤šà¤¿à¤®",
        "à¤ªà¤¿à¤šà¥à¤›à¤¡à¤¾": "à¤ªà¤¿à¤›à¤¡à¤¼à¤¾",
        "à¤œà¤¿à¤®à¥à¤®à¥‡à¤¡à¤¾à¤°": "à¤œà¤¿à¤®à¥à¤®à¥‡à¤¦à¤¾à¤°",
        "à¤°à¤¾à¤œà¤¨à¤¿à¤¤à¥‡": "à¤°à¤¾à¤œà¤¨à¥€à¤¤à¤¿",
        "à¤°à¤¾à¤œà¤¨à¤¿à¤¤à¤¿": "à¤°à¤¾à¤œà¤¨à¥€à¤¤à¤¿",
        "à¤¬à¤¹à¤¾à¤°à¤¤": "à¤­à¤¾à¤°à¤¤",
        "à¤­à¤°à¤¤": "à¤­à¤¾à¤°à¤¤",
    }

    for bad, good in fixes.items():
        text = text.replace(bad, good)

    text = re.sub(r"(à¥\s*){3,}", "", text)

    # Collapse broken repeated Hindi syllables without touching normal words too much.
    text = re.sub(r"([\u0900-\u097F]{2,})\1{2,}", r"\1", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def v38_transcript_quality_report(job_id, raw_text, normalized_text, raw_segments, normalized_segments, asr_meta=None):
    try:
        Path("analytics").mkdir(exist_ok=True)
        asr_meta = asr_meta if isinstance(asr_meta, dict) else {}

        suspicious_terms = [
            "à¤—à¤²à¥‹à¤¬à¤²à¥€", "à¤¶à¥à¤µà¤°", "à¤¦à¤¿à¤®à¤¾à¤¨", "à¤¸à¥à¤à¥‡", "à¤•à¤¾à¤ªà¤¿à¤¯à¤¤", "à¤ªà¥à¤°à¤¡à¤¼",
            "à¤…à¤ªà¥à¤Ÿà¤¼", "à¤—à¤—à¤¾", "à¤•à¥‹à¤Ÿà¤¾à¤—", "à¤—à¥à¤¯à¤¾à¤ªà¥‡", "à¤ªà¥à¤¯à¤® à¤µà¥‹à¤¦à¥€"
        ]

        def count_hits(text):
            text = str(text or "")
            return {term: text.count(term) for term in suspicious_terms if term in text}

        raw_text = str(raw_text or "")
        normalized_text = str(normalized_text or "")

        row = {
            "ts": time.time(),
            "job_id": job_id,
            "raw_segments": len(safe_dict_list(raw_segments)),
            "normalized_segments": len(safe_dict_list(normalized_segments)),
            "raw_bad_terms": count_hits(raw_text),
            "normalized_bad_terms": count_hits(normalized_text),
            "raw_preview": v18_preview_text(raw_text, 320),
            "normalized_preview": v18_preview_text(normalized_text, 320),
            "asr_mode": asr_meta.get("asr_mode", "native_transcribe"),
            "asr_quality_score": asr_meta.get("asr_quality_score"),
            "asr_quality_reasons": asr_meta.get("asr_quality_reasons", []),
            "low_confidence_asr": bool(asr_meta.get("low_confidence_asr")),
            "version": "v38_transcript_quality"
        }

        with open("analytics/transcript_quality.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if row["low_confidence_asr"]:
                f.write(json.dumps({
                    "ts": time.time(),
                    "job_id": job_id,
                    "event": "ASR_LOW_CONFIDENCE",
                    "asr_mode": row["asr_mode"],
                    "asr_quality_score": row["asr_quality_score"],
                    "asr_quality_reasons": row["asr_quality_reasons"],
                    "message": "ASR_LOW_CONFIDENCE",
                }, ensure_ascii=False) + "\n")

        print(
            "ðŸ”¥ Transcript quality logged | "
            f"raw_bad={sum(row['raw_bad_terms'].values())} "
            f"normalized_bad={sum(row['normalized_bad_terms'].values())} "
            f"asr_mode={row['asr_mode']} quality={row['asr_quality_score']} "
            f"low_confidence={row['low_confidence_asr']}"
        )

    except Exception as e:
        print(f"âš  Transcript quality logging failed: {e}")


def v48_write_asr_segment_artifact(job_id, segments, asr_meta=None):
    try:
        Path("audit_reports").mkdir(exist_ok=True)
        asr_meta = asr_meta if isinstance(asr_meta, dict) else {}
        asr_mode = asr_meta.get("asr_mode", "native_transcribe")
        asr_quality_score = asr_meta.get("asr_quality_score")
        asr_quality_reasons = asr_meta.get("asr_quality_reasons", [])
        low_confidence_asr = bool(asr_meta.get("low_confidence_asr"))

        safe_segments = []
        for seg in safe_dict_list(segments):
            text = str(seg.get("text", "") or "").strip()
            if not text:
                continue
            safe_segments.append({
                "start": safe_float(seg.get("start")),
                "end": safe_float(seg.get("end")),
                "text": text,
                "asr_mode": seg.get("asr_mode", asr_mode),
                "asr_quality_score": seg.get("asr_quality_score", asr_quality_score),
                "asr_quality_reasons": seg.get("asr_quality_reasons", asr_quality_reasons),
                "low_confidence_asr": bool(seg.get("low_confidence_asr", low_confidence_asr)),
            })

        payload = {
            "job_id": job_id,
            "asr_mode": asr_mode,
            "asr_quality_score": asr_quality_score,
            "low_confidence_asr": low_confidence_asr,
            "segments": safe_segments,
            "version": "v48_asr_segments_debug",
        }
        path = Path("audit_reports") / f"asr_segments_{job_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"V48_ASR_SEGMENT_ARTIFACT_WRITTEN path={path} segments={len(safe_segments)}")
    except Exception as e:
        print(f"V48_ASR_SEGMENT_ARTIFACT_FAILED error={e}")


def v38_caption_quality_report(captions):
    captions = safe_dict_list(captions)
    if not captions:
        return False, ["no_captions"]

    suspicious_terms = [
        "à¤—à¤²à¥‹à¤¬à¤²à¥€", "à¤¶à¥à¤µà¤°", "à¤¦à¤¿à¤®à¤¾à¤¨", "à¤¸à¥à¤à¥‡", "à¤•à¤¾à¤ªà¤¿à¤¯à¤¤", "à¤ªà¥à¤°à¤¡à¤¼",
        "à¤…à¤ªà¥à¤Ÿà¤¼", "à¤—à¤—à¤¾", "à¤•à¥‹à¤Ÿà¤¾à¤—", "à¤—à¥à¤¯à¤¾à¤ªà¥‡", "à¤ªà¥à¤¯à¤® à¤µà¥‹à¤¦à¥€"
    ]

    total = 0
    bad = 0

    for c in captions:
        text = str(c.get("text", ""))
        if not text:
            continue
        total += 1
        if any(term in text for term in suspicious_terms):
            bad += 1

    if total == 0:
        return False, ["empty_caption_text"]

    bad_ratio = bad / max(total, 1)
    if total >= 4 and bad_ratio >= 0.70:
        return False, [f"caption_quality_severe={bad_ratio:.2f}"]

    if total >= 4 and bad_ratio >= 0.45:
        return False, [f"caption_bad_term_ratio={bad_ratio:.2f}"]

    return True, []


def v38_caption_quality_is_severe(reasons):
    return any("caption_quality_severe" in str(r) for r in (reasons or []))


def v38_text_quality_is_severe(text):
    text = str(text or "")
    words = text.split()
    if len(words) < 8:
        return False

    suspicious_terms = [
        "à¤—à¤²à¥‹à¤¬à¤²à¥€", "à¤¶à¥à¤µà¤°", "à¤¦à¤¿à¤®à¤¾à¤¨", "à¤¸à¥à¤à¥‡", "à¤•à¤¾à¤ªà¤¿à¤¯à¤¤", "à¤ªà¥à¤°à¤¡à¤¼",
        "à¤…à¤ªà¥à¤Ÿà¤¼", "à¤—à¤—à¤¾", "à¤•à¥‹à¤Ÿà¤¾à¤—", "à¤—à¥à¤¯à¤¾à¤ªà¥‡", "à¤ªà¥à¤¯à¤® à¤µà¥‹à¤¦à¥€"
    ]
    bad = sum(text.count(term) for term in suspicious_terms)
    return bad >= 6 or (bad / max(len(words), 1)) >= 0.14


def v27_normalize_segments(segments):
    out = []
    for seg in safe_dict_list(segments):
        seg = dict(seg)
        seg["text"] = v27_normalize_asr_text(seg.get("text", ""))
        out.append(seg)
    return out


# =========================================================
# ðŸ”¥ V26 Failure Snapshot + Retry Intelligence
# =========================================================

def v26_log_failure_snapshot(job_id, stage, error, jobs=None):
    try:
        Path("analytics").mkdir(exist_ok=True)
        row = {
            "ts": time.time(),
            "job_id": job_id,
            "stage": stage,
            "error": str(error),
            "job_state": dict((jobs or {}).get(job_id, {})) if isinstance(jobs, dict) else {},
        }
        with open("analytics/failure_snapshots.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\\n")
        print(f"âœ… V26 failure snapshot logged for {job_id}")
    except Exception as e:
        print(f"âš  V26 failure snapshot failed: {e}")


# =========================================================
# ðŸ”¥ V25 Feedback-Based Auto Learning
# =========================================================

def v25_feedback_learning_boost(niche):
    try:
        path = Path("analytics") / "creator_feedback.jsonl"
        if not path.exists():
            return 0, ["no_feedback_yet"]

        good = 0
        bad = 0
        niche = str(niche or "general")

        for line in path.read_text(encoding="utf-8").splitlines()[-500:]:
            try:
                row = json.loads(line)
            except Exception:
                continue

            rating = str(row.get("rating", "")).lower()
            note = str(row.get("note", "")).lower()
            reason = str(row.get("reason", "")).lower()

            if niche in note or niche in reason:
                if rating in ["good", "great", "like", "liked"]:
                    good += 1
                elif rating in ["bad", "poor", "dislike", "disliked"]:
                    bad += 1

        if good == 0 and bad == 0:
            return 0, ["no_niche_feedback"]

        delta = max(-12, min(12, (good - bad) * 3))
        reasons = [f"feedback_good={good}", f"feedback_bad={bad}"]

        return delta, reasons

    except Exception as e:
        print(f"âš  V25 feedback learning failed: {e}")
        return 0, ["feedback_error"]


# =========================================================
# ðŸ”¥ V23 Visual Intelligence Clip Scoring
# =========================================================

def v23_visual_clip_score(start, end, visual_data):
    try:
        if not isinstance(visual_data, dict):
            return 0, []

        moments = visual_data.get("top_moments", []) or []
        if not moments:
            return 0, []

        score = 0
        reasons = []

        for m in moments:
            ts = safe_float(m.get("time"))
            if start <= ts <= end:
                vs = safe_float(m.get("visual_score"))
                motion = safe_float(m.get("motion"))
                faces = safe_float(m.get("faces"))

                score += min(20, vs)

                if motion >= 12:
                    score += 8
                    reasons.append("high_motion")

                if faces >= 1:
                    score += 6
                    reasons.append("face_presence")

        if score > 0:
            reasons.append("visual_spike_overlap")

        return round(score, 2), list(set(reasons))

    except Exception as e:
        print(f"âš  V23 visual scoring failed: {e}")
        return 0, []


# =========================================================
# ðŸ”¥ V20 Clip Intelligence Dataset Logger
# =========================================================

def v20_log_clip_intelligence(job_id, clips, stage="generated"):
    try:
        Path("analytics").mkdir(exist_ok=True)
        path = Path("analytics") / "clip_intelligence.jsonl"

        with path.open("a", encoding="utf-8") as f:
            for c in safe_dict_list(clips):
                sb = c.get("score_breakdown", {}) if isinstance(c.get("score_breakdown"), dict) else {}
                row = {
                    "ts": time.time(),
                    "job_id": job_id,
                    "stage": stage,
                    "niche": c.get("niche"),
                    "score": c.get("score"),
                    "start": c.get("start"),
                    "end": c.get("end"),
                    "duration": round(safe_float(c.get("end")) - safe_float(c.get("start")), 2),
                    "title": c.get("title"),
                    "source_preview": v18_preview_text(c.get("source_text"), 220),
                    "expanded_preview": v18_preview_text(c.get("expanded_text"), 420),
                    "score_breakdown": v18_safe_score_breakdown(sb),
                    "story_score": sb.get("story_score", sb.get("v33_story_score")),
                    "v19_native_score": sb.get("v19_native_score"),
                    "v19_native_reasons": sb.get("v19_native_reasons"),
                    "editor_reasons": sb.get("editor_reasons"),
                    "true_creator_reasons": sb.get("true_creator_reasons"),
                    "recovered": bool(sb.get("v19_recovered")),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        print(f"âœ… V20 analytics logged: {len(clips)} clips stage={stage}")
    except Exception as e:
        print(f"âš  V20 analytics logging failed: {e}")


def run_pipeline(job_id, file_path, JOBS):
    try:
        JOBS[job_id]["status"] = "processing"
        JOBS[job_id]["stage"] = "Starting"
        JOBS[job_id]["progress"] = 5

        file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            raise Exception(f"Input video not found: {file_path}")

        print(f"ðŸ”¥ Input video: {file_path}")

        # ðŸ”¥ V22 lightweight visual intelligence foundation
        visual_data = log_visual_intelligence(job_id, file_path)
        thumb_data = extract_best_thumbnail_frames(file_path, job_id, top_n=5)

        JOBS[job_id]["visual_intelligence"] = {
            "ok": visual_data.get("ok"),
            "sampled": visual_data.get("sampled"),
            "top_moments": visual_data.get("top_moments", [])[:5],
            "ai_thumbnails": thumb_data.get("frames", [])[:5],
        }

        clean_generated_files()

        JOBS[job_id]["stage"] = "ASR"
        JOBS[job_id]["progress"] = 10
        print("ðŸ”¥ STEP 1: ASR")
        data = transcribe(file_path, job_id=job_id)

        raw_segments = safe_dict_list(data.get("segments", []))
        segments = v27_normalize_segments(raw_segments)
        text = v27_normalize_asr_text(data.get("text", ""))
        asr_meta = {
            "asr_mode": data.get("asr_mode", "native_transcribe"),
            "asr_quality_score": data.get("asr_quality_score"),
            "asr_quality_reasons": data.get("asr_quality_reasons", []),
            "low_confidence_asr": bool(data.get("low_confidence_asr")),
            "asr_hard_failure": bool(data.get("asr_hard_failure")),
            "asr_hard_failure_reason": data.get("asr_hard_failure_reason", ""),
        }
        fail_closed, fail_closed_reason = asr_should_fail_closed(
            asr_meta["asr_quality_score"],
            asr_meta["asr_quality_reasons"],
            asr_meta["low_confidence_asr"],
        )
        if fail_closed:
            asr_meta["asr_hard_failure"] = True
            asr_meta["asr_hard_failure_reason"] = (
                asr_meta["asr_hard_failure_reason"] or fail_closed_reason
            )
        JOBS[job_id]["asr_mode"] = asr_meta["asr_mode"]
        JOBS[job_id]["asr_quality_score"] = asr_meta["asr_quality_score"]
        JOBS[job_id]["low_confidence_asr"] = asr_meta["low_confidence_asr"]
        JOBS[job_id]["asr_hard_failure"] = asr_meta["asr_hard_failure"]
        JOBS[job_id]["asr_hard_failure_reason"] = asr_meta["asr_hard_failure_reason"]
        v38_transcript_quality_report(
            job_id,
            data.get("text", ""),
            text,
            safe_dict_list(data.get("segments", [])),
            segments,
            asr_meta
        )
        v48_write_asr_segment_artifact(job_id, segments, asr_meta)

        print(f"ðŸ”¥ STEP 1 DONE | segments: {len(segments)}")

        if fail_closed:
            message = (
                "Source audio/transcription quality too low for creator-safe clips. "
                "Try clearer audio or English/clean Hinglish source."
            )
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["stage"] = "Diagnostic Failed ASR"
            JOBS[job_id]["progress"] = 100
            JOBS[job_id]["message"] = message
            result = {
                "status": "diagnostic_failed_asr",
                "message": message,
                "summary": {
                    "text_preview": v18_preview_text(text, 900),
                    "segments_count": len(segments),
                    "asr_mode": asr_meta["asr_mode"],
                    "asr_quality_score": asr_meta["asr_quality_score"],
                    "asr_quality_reasons": asr_meta["asr_quality_reasons"],
                    "low_confidence_asr": asr_meta["low_confidence_asr"],
                    "asr_hard_failure_reason": asr_meta["asr_hard_failure_reason"],
                    "clips_count": 0,
                },
                "clips": [],
                "final_clips": [],
                "creator_qa": {
                    "event": "DIAGNOSTIC_FAILED_ASR",
                    "message": message,
                    "asr_mode": asr_meta["asr_mode"],
                    "asr_quality_score": asr_meta["asr_quality_score"],
                    "low_confidence_asr": asr_meta["low_confidence_asr"],
                    "asr_quality_reasons": asr_meta["asr_quality_reasons"],
                },
            }
            JOBS[job_id]["result"] = result
            print(
                "ASR_FAIL_CLOSED "
                f"job_id={job_id} quality={asr_meta['asr_quality_score']} "
                f"reason={asr_meta['asr_hard_failure_reason']}"
            )
            return result

        if not segments:
            raise Exception("No ASR segments found")

        JOBS[job_id]["stage"] = "Captions"
        JOBS[job_id]["progress"] = 30
        print("ðŸ”¥ STEP 2: Captions")
        captions = safe_dict_list(generate_captions(raw_segments))

        JOBS[job_id]["stage"] = "Viral Analysis"
        JOBS[job_id]["progress"] = 45
        print("ðŸ”¥ STEP 3: Viral analysis")
        arc_candidates = build_story_arc_candidates(segments)
        viral = merge_viral_candidates(
            arc_candidates,
            safe_dict_list(analyze_video(segments))
        )

        print(f"ðŸ”¥ Viral segments: {len(viral)}")

        JOBS[job_id]["stage"] = "Clip Generation"
        JOBS[job_id]["progress"] = 65
        print("ðŸ”¥ STEP 4: Clip generation")
        clips = build_final_clips(
            viral,
            segments,
            JOBS.get(job_id, {}).get("visual_intelligence", {}),
            job_id=job_id,
        )

        clips_before_creator_qa = len(clips)
        v20_log_clip_intelligence(job_id, clips, stage="pre_creator_qa")
        clips, creator_qa_rejections = apply_creator_qa(job_id, clips, captions)
        print(
            "Creator QA summary: "
            f"before={clips_before_creator_qa} after={len(clips)} "
            f"rejected={len(creator_qa_rejections)}"
        )

        if not clips and creator_qa_rejections:
            zero_qa_row = log_creator_qa_zero_safe_clips(job_id, creator_qa_rejections)
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["stage"] = "Completed"
            JOBS[job_id]["progress"] = 100

            result = {
                "status": "done",
                "message": "No creator-safe clips found",
                "summary": {
                    "text_preview": v18_preview_text(text, 900),
                    "segments_count": len(segments),
                    "captions_count": len(captions),
                    "viral_segments_count": len(viral),
                    "asr_mode": asr_meta["asr_mode"],
                    "asr_quality_score": asr_meta["asr_quality_score"],
                    "low_confidence_asr": asr_meta["low_confidence_asr"],
                    "clips_before_creator_qa": clips_before_creator_qa,
                    "clips_count": 0,
                    "rejected_by_creator_qa": len(creator_qa_rejections),
                    "top_rejection_reasons": zero_qa_row["top_rejection_reasons"],
                },
                "clips": [],
                "final_clips": [],
                "creator_qa": {
                    "event": "CREATOR_QA_ZERO_SAFE_CLIPS",
                    "message": "No creator-safe clips found",
                    "asr_mode": asr_meta["asr_mode"],
                    "asr_quality_score": asr_meta["asr_quality_score"],
                    "low_confidence_asr": asr_meta["low_confidence_asr"],
                    "rejections": creator_qa_rejections,
                    "top_rejection_reasons": zero_qa_row["top_rejection_reasons"],
                }
            }

            JOBS[job_id]["result"] = result
            print("No creator-safe clips found")
            return result

        v20_log_clip_intelligence(job_id, clips, stage="pre_export")

        print(f"ðŸ”¥ Clips generated before density filter: {len(clips)}")

        if not clips:
            raise Exception("No clips generated")

        generate_raw_clips_safe(file_path, clips)

        # Job-specific isolation for generated intermediate files
        for idx in range(len(clips)):
            for prefix in ["input_raw", "input_clip", "thumbnail"]:
                ext = ".jpg" if prefix == "thumbnail" else ".mp4"
                old_path = os.path.abspath(f"uploads/{prefix}_{idx}{ext}")
                new_path = os.path.abspath(f"uploads/{job_id}_{prefix}_{idx}{ext}")
                if os.path.exists(old_path):
                    os.replace(old_path, new_path)

        final_clips = []
        approved_clips = []

        JOBS[job_id]["stage"] = "Subtitles + Filtering"
        JOBS[job_id]["progress"] = 85
        print("ðŸ”¥ STEP 5: Subtitle burn + speech density filter")

        for i, clip in enumerate(clips):
            try:
                clip_start = safe_float(clip.get("start"))
                clip_end = safe_float(clip.get("end"))

                print(f"ðŸ”¥ Clip timing: {clip_start} â†’ {clip_end}")

                clip_captions = get_captions_for_clip(
                    captions,
                    clip_start,
                    clip_end
                )

                print(f"ðŸ”¥ Captions for clip: {len(clip_captions)}")

                if len(clip_captions) < 4:
                    print("âš  Low speech density clip skipped")
                    continue

                caption_ok, caption_reasons = v38_caption_quality_report(clip_captions)
                if not caption_ok:
                    print(f"âš  Caption quality warning: {caption_reasons}")
                    clip.setdefault("score_breakdown", {})["caption_quality_warning"] = caption_reasons
                    if v38_caption_quality_is_severe(caption_reasons):
                        print(f"ðŸš« Severe caption quality rejected clip: {caption_reasons}")
                        continue

                input_clip = os.path.abspath(f"uploads/{job_id}_input_clip_{i}.mp4")
                output_clip = os.path.abspath(f"uploads/{job_id}_final_{len(final_clips)}.mp4")

                if not os.path.exists(input_clip):
                    print(f"âš  Missing clip file: {input_clip}")
                    continue

                final_output = burn_subtitles(
                    input_clip,
                    clip_captions,
                    output_clip
                )

                final_clips.append(final_output)
                approved_clips.append(clip)

            except Exception as clip_error:
                print(f"âŒ Clip {i} failed: {clip_error}")
                traceback.print_exc()

        enhanced_clips = []

        used_titles = set()

        for i, clip in enumerate(approved_clips):
            video_path = final_clips[i] if i < len(final_clips) else None

            context_for_title = clip.get("expanded_text", clip.get("source_text", ""))
            clean_title = clip.get("title") or v9_editorial_title(context_for_title, set())
            clean_title = _v9_unique_title(clean_title, used_titles)

            final_hashtags = clip.get("hashtags", ["#viral"])
            final_hashtags = v40_niche_hashtags(
                clip.get("niche", "general"),
                context_for_title
            )

            social_captions = generate_social_caption(
                clean_title,
                final_hashtags,
                clip.get("niche", "general")
            )

            creator_pack = v34_creator_pack_metadata(
                clean_title,
                context_for_title,
                clip.get("niche", "general"),
                clip.get("score_breakdown", {}).get("visual_score", 0),
                clip.get("score_breakdown", {}).get("story_score", 0)
            )
            enhanced_clips.append({
                "clip_number": i + 1,
                "start": clip.get("start"),
                "end": clip.get("end"),
                "duration": round(
                    safe_float(clip.get("end")) - safe_float(clip.get("start")),
                    2
                ),
                "video_path": f"/uploads/{Path(video_path).name}" if video_path else None,
                "video_url": f"/uploads/{Path(video_path).name}" if video_path else None,
                "download_url": f"/uploads/{Path(video_path).name}" if video_path else None,
                "thumbnail_url": f"/uploads/{job_id}_thumbnail_{i}.jpg",
                "creator_pack": creator_pack,
                "source_text": v18_preview_text(clip.get("source_text", ""), 260),
                "expanded_text": v18_preview_text(clip.get("expanded_text", ""), 520),
                "title": clean_title,
                "hashtags": final_hashtags,
                "niche": clip.get("niche", "general"),
                "score": clip.get("score", 0),
                "score_breakdown": v18_safe_score_breakdown(clip.get("score_breakdown", {})),
                "social_captions": social_captions
            })

        if not enhanced_clips:
            raise Exception("All clips rejected by speech density/ad filter")

        v20_log_clip_intelligence(job_id, enhanced_clips, stage="completed")

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["stage"] = "Completed"

        # ðŸ”¥ V13 delayed production cleanup
        threading.Thread(
            target=v13_delayed_job_cleanup,
            args=(job_id,),
            daemon=True
        ).start()

        # ðŸ”¥ V18.3 storage cleanup
        threading.Thread(
            target=v18_cleanup_old_files,
            kwargs={"hours": 18, "keep_latest_jobs": 12},
            daemon=True
        ).start()

        JOBS[job_id]["progress"] = 100

        result = {
            "status": "done",
            "summary": {
                "text_preview": v18_preview_text(text, 900),
                "segments_count": len(segments),
                "captions_count": len(captions),
                "viral_segments_count": len(viral),
                "asr_mode": asr_meta["asr_mode"],
                "asr_quality_score": asr_meta["asr_quality_score"],
                "low_confidence_asr": asr_meta["low_confidence_asr"],
                "clips_count": len(enhanced_clips),
            },
            "clips": enhanced_clips,
            "final_clips": [
                f"/uploads/{Path(x).name}" if x else None
                for x in final_clips
            ]
        }

        JOBS[job_id]["result"] = result

        print("âœ… PIPELINE COMPLETE")
        print("\nðŸ”¥ FINAL RESULT SUMMARY:")
        print({"clips": len(enhanced_clips), "final_clips": len(final_clips)})

        return result

    except Exception as e:
        traceback.print_exc()

        v26_log_failure_snapshot(
            job_id,
            JOBS.get(job_id, {}).get("stage", "unknown"),
            e,
            JOBS
        )

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
        print("âŒ No input video found.")
        print("Put your original test video here:")
        print("C:\\ai_projects\\input.mp4")
    else:
        print(f"ðŸ”¥ Test video found: {test_video}")

        JOBS[job_id] = {
            "status": "queued",
            "result": None,
            "error": None
        }

        run_pipeline(job_id, test_video, JOBS)
