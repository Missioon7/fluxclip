import re


# =========================
# OPUS AI CAPTION ENGINE v4.5
# Retention captions: short, punchy, emoji-ready
# =========================

MAX_WORDS_PER_CAPTION = 6
MIN_WORDS_PER_CAPTION = 1
MAX_CAPTION_DURATION = 2.2
MIN_CAPTION_DURATION = 0.65

ENABLE_EMOJIS = True


POWER_WORDS = [
    "war", "attack", "missile", "drone", "nuclear", "danger",
    "threat", "russia", "ukraine", "iran", "america", "china",
    "nato", "trump", "money", "billion", "million", "package",
    "secret", "truth", "reason", "why", "how", "what"
]


def clean_caption(text):
    if not text:
        return ""

    text = str(text)

    junk_patterns = [
        "ÛÛ’ ÛÛ’",
        "4 4",
        "....",
        "Û”Û”Û”",
        "ðŸ”¥",
        "ðŸ˜‚",
        "ðŸ˜±",
        "ðŸ’€",
    ]

    for j in junk_patterns:
        text = text.replace(j, "")

    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()

    return text


def add_context_emoji(text):
    if not ENABLE_EMOJIS:
        return text

    low = text.lower()

    if any(w in low for w in ["billion", "million", "money", "fund", "package"]):
        return text + " 💰"

    if any(w in low for w in ["war", "attack", "missile", "drone", "nuclear"]):
        return text + " ⚠️"

    if any(w in low for w in ["why", "how", "what", "kaise", "kyu"]):
        return text + " ❓"

    if any(w in low for w in ["secret", "truth", "shocking", "danger"]):
        return text + " 😳"

    return text


def emphasize_text(text):
    words = text.split()
    out = []

    for w in words:
        raw = re.sub(r"[^a-zA-Z0-9]", "", w).lower()

        if raw in POWER_WORDS:
            out.append(w.upper())
        elif re.search(r"\d", w):
            out.append(w.upper())
        else:
            out.append(w)

    result = " ".join(out)

    # first word punchy if question
    if result.lower().startswith(("why ", "how ", "what ")):
        first, *rest = result.split()
        result = " ".join([first.upper()] + rest)

    return result


def split_text_into_chunks(text, max_words=MAX_WORDS_PER_CAPTION):
    words = text.split()
    chunks = []
    current = []

    for word in words:
        current.append(word)

        should_cut = False

        if len(current) >= max_words:
            should_cut = True

        if word.endswith(("?", "!", ".")) and len(current) >= 3:
            should_cut = True

        if should_cut:
            chunk = " ".join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = []

    if current:
        chunk = " ".join(current).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def make_caption_text(text):
    text = clean_caption(text)
    text = emphasize_text(text)
    text = add_context_emoji(text)
    return text


def generate_captions(segments):
    captions = []

    for s in segments:
        text = clean_caption(s.get("text", ""))
        if not text:
            continue

        start = float(s["start"])
        end = float(s["end"])

        if end <= start:
            continue

        chunks = split_text_into_chunks(text)

        if not chunks:
            continue

        total_duration = end - start
        chunk_duration = total_duration / len(chunks)

        chunk_duration = max(MIN_CAPTION_DURATION, chunk_duration)
        chunk_duration = min(MAX_CAPTION_DURATION, chunk_duration)

        current_start = start

        for chunk in chunks:
            chunk = make_caption_text(chunk)

            if len(chunk.split()) < MIN_WORDS_PER_CAPTION:
                continue

            current_end = min(end, current_start + chunk_duration)

            if current_end <= current_start:
                continue

            captions.append({
                "start": round(current_start, 2),
                "end": round(current_end, 2),
                "text": chunk
            })

            current_start = current_end

    return captions