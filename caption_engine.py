import re


# =========================
# OPUS AI CAPTION ENGINE v4.5
# Retention captions: short, punchy, emoji-ready
# =========================

MAX_WORDS_PER_CAPTION = 6
MIN_WORDS_PER_CAPTION = 1
MAX_CAPTION_DURATION = 2.25
MIN_CAPTION_DURATION = 0.75

ENABLE_EMOJIS = False


POWER_WORDS = [
    "secret", "truth", "danger", "risk", "warning",
    "mistake", "failed", "exposed", "shocking",
    "billion", "million"
]

BOUNDARY_WORDS = {
    "but", "because", "so", "then", "however", "actually", "therefore",
    "lekin", "magar", "kyunki", "par", "toh", "matlab", "phir", "isliye",
    "लेकिन", "मगर", "क्योंकि", "पर", "तो", "मतलब", "फिर", "इसलिए"
}


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
    text = re.sub(r"(.)\1{5,}", r"\1", text)
    text = re.sub(r"(ॐ\s*){2,}", "", text)
    text = re.sub(r"(ओम\s*){2,}", "", text)
    text = re.sub(r"\b(\w+)\s+\1\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"([\u0900-\u097F]{2,})\s+\1\s+\1", r"\1", text)
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
    emphasized = 0

    for w in words:
        raw = re.sub(r"[^a-zA-Z0-9]", "", w).lower()

        if raw in POWER_WORDS and emphasized < 1 and len(raw) > 4:
            out.append(w.upper())
            emphasized += 1
        else:
            out.append(w)

    return " ".join(out)


def split_text_into_chunks(text, max_words=MAX_WORDS_PER_CAPTION):
    words = text.split()
    chunks = []
    current = []

    for word in words:
        current.append(word)

        should_cut = False

        if len(current) >= max_words:
            should_cut = True

        clean_word = word.lower().strip(",.!?।")

        if word.endswith(("?", "!", ".", ",", "।")) and len(current) >= 3:
            should_cut = True

        if clean_word in BOUNDARY_WORDS and len(current) >= 4:
            should_cut = True

        if len(" ".join(current)) > 34 and len(current) >= 3:
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


def generate_word_timestamp_captions(words, segment_start, segment_end):
    if not isinstance(words, list):
        return []

    usable = []
    for w in words:
        if not isinstance(w, dict):
            continue

        word = clean_caption(w.get("word", ""))
        if not word:
            continue

        try:
            start = float(w.get("start", segment_start))
            end = float(w.get("end", start))
        except Exception:
            continue

        if end <= start:
            continue

        usable.append({
            "word": word,
            "start": max(segment_start, start),
            "end": min(segment_end, end)
        })

    if not usable:
        return []

    captions = []
    current = []

    def flush_current():
        if not current:
            return

        text = make_caption_text(" ".join(i["word"] for i in current))
        if len(text.split()) < MIN_WORDS_PER_CAPTION:
            current.clear()
            return

        start = current[0]["start"]
        end = current[-1]["end"]
        if end > start:
            captions.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "text": text
            })
        current.clear()

    for item in usable:
        current.append(item)
        clean_word = item["word"].lower().strip(",.!?।")

        should_cut = False
        if len(current) >= 5:
            should_cut = True
        elif len(current) >= 2 and item["word"].endswith(("?", "!", ".", ",", "।")):
            should_cut = True
        elif len(current) >= 3 and clean_word in BOUNDARY_WORDS:
            should_cut = True
        elif len(" ".join(i["word"] for i in current)) > 28 and len(current) >= 2:
            should_cut = True

        if should_cut:
            flush_current()

    if current and len(current) == 1 and captions:
        last = captions[-1]
        merged_text = make_caption_text(last["text"] + " " + current[0]["word"])
        if len(merged_text.split()) <= 5:
            last["text"] = merged_text
            last["end"] = round(current[0]["end"], 2)
            current.clear()

    flush_current()
    return captions


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

        word_captions = []
        if not s.get("low_confidence_asr"):
            word_captions = generate_word_timestamp_captions(s.get("words", []), start, end)
        if word_captions:
            captions.extend(word_captions)
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
