import re


# =========================
# OPUS AI VIRAL ENGINE v4
# Semantic + hook + controversy scoring
# =========================

MIN_CLIP_SECONDS = 18
MAX_CLIP_SECONDS = 55

TARGET_CANDIDATES = 12
MIN_GAP_SECONDS = 45
MIN_SCORE_THRESHOLD = 28


HOOK_WORDS = [
    "wait", "listen", "look", "but", "however",
    "secret", "truth", "real reason", "hidden",
    "breaking", "big update", "major update",

    "suno", "dekho", "ruk", "lekin",
    "asli wajah", "sach", "raaz"
]

QUESTION_WORDS = [
    "why", "how", "what", "who", "when",
    "kyu", "kaise", "kya", "kaun"
]

CONTROVERSY_WORDS = [
    "war", "attack", "collapse", "destroy",
    "nuclear", "missile", "drone", "threat",
    "sanction", "china", "russia", "ukraine",
    "iran", "america", "trump", "nato",
    "exposed", "crisis", "oil", "economy"
]

MONEY_WORDS = [
    "billion", "million", "crore",
    "trillion", "fund", "package"
]

ENDING_WORDS = [
    "remember",
    "this is important",
    "this changes everything",
    "this is huge",
    "think about it"
]

FILLER_WORDS = [
    "umm",
    "uhh",
    "hmm",
    "you know",
    "like like"
]


def clean_text(text):
    text = text or ""
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_count(text):
    return len(re.findall(r"\w+", text.lower()))


def contains_any(text, words):
    text_low = text.lower()
    return sum(1 for w in words if w.lower() in text_low)


def contains_numbers(text):
    return len(re.findall(r"\d+", text))


def text_similarity(a, b):
    a_words = set(re.findall(r"\w+", a.lower()))
    b_words = set(re.findall(r"\w+", b.lower()))

    if not a_words or not b_words:
        return 0

    return len(a_words & b_words) / max(1, len(a_words | b_words))


def build_windows(segments):
    windows = []

    clean_segments = []

    for s in segments:
        text = clean_text(s.get("text", ""))

        if not text:
            continue

        clean_segments.append({
            "start": float(s["start"]),
            "end": float(s["end"]),
            "text": text
        })

    for i in range(len(clean_segments)):
        start = clean_segments[i]["start"]
        combined_text = []

        for j in range(i, len(clean_segments)):
            end = clean_segments[j]["end"]
            duration = end - start

            if duration > MAX_CLIP_SECONDS:
                break

            combined_text.append(clean_segments[j]["text"])

            if duration >= MIN_CLIP_SECONDS:
                full_text = clean_text(
                    " ".join(combined_text)
                )

                windows.append({
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "text": full_text,
                    "first_text": clean_segments[i]["text"],
                    "last_text": clean_segments[j]["text"]
                })

    return windows


def score_window(window):
    text = window["text"]
    first_text = window["first_text"]
    last_text = window["last_text"]
    duration = window["duration"]

    wc = word_count(text)

    score = 0

    # Opening hook power
    score += contains_any(first_text, HOOK_WORDS) * 10
    score += contains_any(first_text, QUESTION_WORDS) * 8

    # Semantic controversy
    score += contains_any(text, CONTROVERSY_WORDS) * 6

    # Money/data claims perform well
    score += contains_any(text, MONEY_WORDS) * 5
    score += contains_numbers(text) * 2

    # Ending punch
    score += contains_any(last_text, ENDING_WORDS) * 8

    # speech density
    density = wc / max(1, duration)
    score += min(20, density * 6)

    # ideal clip duration
    if 22 <= duration <= 40:
        score += 20
    elif 18 <= duration <= 55:
        score += 12

    # punctuation hook
    if "?" in text:
        score += 4

    if "!" in text:
        score += 2

    # penalty
    score -= contains_any(text, FILLER_WORDS) * 5

    if wc < 20:
        score -= 15

    return round(max(0, score), 2)


def overlap_ratio(a, b):
    start = max(a["start"], b["start"])
    end = min(a["end"], b["end"])

    overlap = max(0, end - start)

    shorter = min(
        a["end"] - a["start"],
        b["end"] - b["start"]
    )

    if shorter <= 0:
        return 0

    return overlap / shorter


def is_duplicate(candidate, selected):
    for item in selected:
        if overlap_ratio(candidate, item) > 0.20:
            return True

        if abs(candidate["start"] - item["start"]) < MIN_GAP_SECONDS:
            return True

        if text_similarity(
            candidate["text"],
            item["text"]
        ) > 0.35:
            return True

    return False


def analyze_video(segments):
    windows = build_windows(segments)

    viral = []

    for w in windows:
        score = score_window(w)

        if score >= MIN_SCORE_THRESHOLD:
            viral.append({
                "start": float(w["start"]),
                "end": float(w["end"]),
                "text": w["text"],
                "score": score
            })

    viral.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    selected = []

    for candidate in viral:
        if not is_duplicate(candidate, selected):
            selected.append(candidate)

        if len(selected) >= TARGET_CANDIDATES:
            break

    return selected