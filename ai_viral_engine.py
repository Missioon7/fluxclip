import random


# -------------------------
# HARD SPONSOR / CTA FILTER
# -------------------------
SPONSOR_WORDS = [
    "subscribe", "like and share", "like share", "sponsored", "sponsor",
    "download app", "link in bio", "promo code", "join telegram",
    "comment section", "click on this link", "register now", "call now",
    "email id", "phone number", "discount code", "coupon code",

    # course/ad/CTA blocks
    "career247", "career 247", "course", "courses", "offer", "sale",
    "mega savings", "flat discount", "price increase", "certificate",
    "certificates", "interview", "interviews", "job focused",
    "golden opportunity", "limited time", "enroll", "admission",
]

HARD_SPONSOR_WORDS = [
    "career247", "career 247", "sponsored", "sponsor", "promo code",
    "discount code", "click on this link", "comment section",
    "phone number", "email id", "mega savings", "flat discount",
]


# -------------------------
# NICHE DETECTION
# -------------------------
NICHE_KEYWORDS = {
    "geopolitics": [
        "war", "russia", "ukraine", "china", "india",
        "america", "usa", "iran", "israel", "nato",
        "missile", "drone", "military", "nuclear",
        "scientist", "scientists", "white house", "fbi",
        "foreign power", "conflict", "crisis"
    ],
    "finance": [
        "money", "stock", "crypto", "market",
        "investment", "business", "profit", "loss"
    ],
    "podcast": [
        "podcast", "interview", "guest", "host", "conversation",
        "story", "he said", "she said", "i asked", "i remember",
        "कहानी", "बात", "उसने कहा", "मैंने कहा", "फिर", "अचानक"
    ],
    "motivation": [
        "success", "discipline", "mindset",
        "failure", "hard work"
    ],
    "story": [
        "then", "suddenly", "finally",
        "one day", "after that", "because", "but", "realized",
        "फिर", "अचानक", "क्योंकि", "लेकिन", "इसलिए", "मतलब"
    ]
}


def clean_text(text):
    if not text:
        return ""
    return str(text).strip().lower()


def is_sponsor_segment(text):
    text = clean_text(text)

    if any(word in text for word in HARD_SPONSOR_WORDS):
        return True

    matches = 0
    for word in SPONSOR_WORDS:
        if word in text:
            matches += 1

    return matches >= 2


def detect_niche(text):
    text = clean_text(text)

    best_niche = "general"
    best_score = 0

    for niche, keywords in NICHE_KEYWORDS.items():
        score = sum(1 for word in keywords if word in text)

        if score > best_score:
            best_score = score
            best_niche = niche

    return best_niche


def hook_score(text):
    text = clean_text(text)

    hook_words = [
        "why",
        "how",
        "secret",
        "truth",
        "real reason",
        "what happened",
        "nobody knows",
        "hidden",
        "exposed",
        "breaking",
        "mysterious",
        "suddenly",
        "who is",
        "what is",
    ]

    score = 0

    for hook in hook_words:
        if hook in text:
            score += 12

    return min(score, 36)


def emotion_score(text):
    text = text.lower()

    strong_words = ["war", "threat", "attack", "danger", "crisis", "death", "collapse"]
    medium_words = ["why", "how", "truth", "secret", "risk"]

    score = 0

    for w in strong_words:
        if w in text:
            score += 8

    for w in medium_words:
        if w in text:
            score += 4

    return score


def controversy_score(text):
    text = clean_text(text)

    words = [
        "war",
        "vs",
        "attack",
        "threat",
        "conflict",
        "nuclear",
        "missile",
        "crisis",
        "foreign power",
        "assassinate",
        "targeted",
    ]

    score = 0

    for word in words:
        if word in text:
            score += 15

    return min(score, 45)


def retention_score(text):
    length = len(clean_text(text).split())

    if 10 <= length <= 42:
        return 35

    if 8 <= length <= 60:
        return 22

    return 8


def story_score(text):
    text = clean_text(text)

    words = [
        "then",
        "after that",
        "suddenly",
        "finally",
        "because",
        "one by one",
        "but",
        "realized",
        "this means",
        "that is why",
        "फिर",
        "अचानक",
        "क्योंकि",
        "लेकिन",
        "इसलिए",
        "मतलब",
    ]

    score = 0

    for word in words:
        if word in text:
            score += 8

    return min(score, 24)


def narrative_value_score(text):
    text = clean_text(text)

    setup = [
        "because", "context", "reason", "what happened", "why",
        "क्योंकि", "कारण", "वजह", "मतलब"
    ]
    tension = [
        "but", "however", "problem", "risk", "conflict", "against",
        "लेकिन", "मगर", "समस्या", "खतरा", "विरोध"
    ]
    payoff = [
        "therefore", "this means", "that means", "this is why", "result",
        "इसलिए", "नतीजा", "यही वजह", "मतलब"
    ]
    conversation = [
        "he said", "she said", "i said", "i asked", "they asked",
        "उसने कहा", "मैंने कहा", "पूछा", "बोला", "बताया"
    ]

    score = 0
    score += min(12, sum(4 for w in setup if w in text))
    score += min(14, sum(5 for w in tension if w in text))
    score += min(18, sum(7 for w in payoff if w in text))
    score += min(12, sum(4 for w in conversation if w in text))

    words = text.split()
    if 8 <= len(words) <= 70:
        score += 8

    return min(score, 42)


def sponsor_penalty(text):
    text = clean_text(text)

    penalty = 0

    for word in SPONSOR_WORDS:
        if word in text:
            penalty -= 80

    return penalty


def generate_title(text, niche):
    text = clean_text(text)
    text_lower = text.lower()

    # V18 universal creator titles: no niche-locked geopolitics templates.
    if any(w in text_lower for w in ["why", "how", "what"]):
        return "The Real Reason This Matters"

    if any(w in text_lower for w in ["suddenly", "unexpected", "nobody", "mysterious"]):
        return "Nobody Saw This Coming"

    if any(w in text_lower for w in ["mistake", "failed", "loss", "risk", "danger"]):
        return "This One Detail Changed Everything"

    if any(w in text_lower for w in ["money", "business", "market", "profit", "loss"]):
        return "This Money Move Changes The Story"

    if any(w in text_lower for w in ["mindset", "discipline", "success", "failure"]):
        return "This Mindset Shift Is Brutal"

    words = text.split()
    key = " ".join(words[:7]) if len(words) > 7 else text

    if len(key) < 18:
        return "This Moment Changes The Whole Story"

    return key[:80]



def generate_hashtags(niche):
    tags = {
        "geopolitics": [
            "#geopolitics",
            "#worldnews",
            "#viral",
            "#shorts"
        ],
        "finance": [
            "#finance",
            "#money",
            "#viral",
            "#shorts"
        ],
        "podcast": [
            "#podcast",
            "#clips",
            "#viral",
            "#shorts"
        ],
        "motivation": [
            "#motivation",
            "#mindset",
            "#viral",
            "#shorts"
        ],
        "story": [
            "#story",
            "#viral",
            "#shorts"
        ],
        "general": [
            "#viral",
            "#shorts"
        ]
    }

    return tags.get(niche, tags["general"])


def score_segment(segment):
    text = segment.get("text", "")
    start = float(segment.get("start", 0))
    end = float(segment.get("end", start + 15))

    if is_sponsor_segment(text):
        return None

    niche = detect_niche(text)

    scores = {
        "hook_score": hook_score(text),
        "emotion_score": emotion_score(text),
        "controversy_score": controversy_score(text),
        "retention_score": retention_score(text),
        "story_score": story_score(text),
        "narrative_value": narrative_value_score(text),
        "sponsor_penalty": sponsor_penalty(text),
    }

    final_score = sum(scores.values())

    threshold = 25
    if niche in {"podcast", "story"}:
        threshold = 18
    if scores["narrative_value"] >= 18:
        threshold = min(threshold, 16)

    if final_score < threshold:
        return None

    return {
        "text": text,
        "start": start,
        "end": end,
        "niche": niche,
        "title": generate_title(text, niche),
        "hashtags": generate_hashtags(niche),
        "score_breakdown": scores,
        "final_score": final_score
    }


def remove_duplicates(scored):
    unique = []

    for clip in scored:
        duplicate = False

        for existing in unique:
            if abs(clip["start"] - existing["start"]) < 22:
                duplicate = True
                break

        if not duplicate:
            unique.append(clip)

    return unique


def find_viral_segments(transcript_segments):
    scored = []

    for segment in transcript_segments:
        result = score_segment(segment)

        if not result:
            continue

        duration = result["end"] - result["start"]

        if duration < 3:
            continue

        scored.append(result)

    scored = sorted(
        scored,
        key=lambda x: x["final_score"],
        reverse=True
    )

    scored = remove_duplicates(scored)

    return scored


def analyze_video(transcript_segments):
    viral_segments = find_viral_segments(transcript_segments)

    formatted = []

    for seg in viral_segments:
        formatted.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "score": seg["final_score"],
            "title": seg["title"],
            "hashtags": seg["hashtags"],
            "niche": seg["niche"],
            "score_breakdown": seg["score_breakdown"]
        })

    return formatted
