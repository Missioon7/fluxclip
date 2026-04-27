import random


# -------------------------
# SPONSOR FILTER
# -------------------------
SPONSOR_WORDS = [
    "subscribe",
    "like and share",
    "like share",
    "sponsored",
    "sponsor",
    "download app",
    "link in bio",
    "promo code",
    "join telegram",
]


# -------------------------
# NICHE DETECTION
# -------------------------
NICHE_KEYWORDS = {
    "geopolitics": [
        "war", "russia", "ukraine", "china", "india",
        "america", "usa", "iran", "israel", "nato",
        "missile", "drone", "military"
    ],
    "finance": [
        "money", "stock", "crypto", "market",
        "investment", "business"
    ],
    "podcast": [
        "podcast", "interview", "guest", "host"
    ],
    "motivation": [
        "success", "discipline", "mindset",
        "failure", "hard work"
    ],
    "story": [
        "then", "suddenly", "finally",
        "one day", "after that"
    ]
}


def clean_text(text):
    if not text:
        return ""
    return str(text).strip().lower()


# -------------------------
# NICHE DETECTION
# -------------------------
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


# -------------------------
# HOOK SCORE
# -------------------------
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
        "big mistake",
        "hidden",
        "exposed",
        "breaking"
    ]

    score = 0

    for hook in hook_words:
        if hook in text:
            score += 20

    return score


# -------------------------
# EMOTION SCORE
# -------------------------
def emotion_score(text):
    text = clean_text(text)

    words = [
        "death",
        "fear",
        "destroyed",
        "revenge",
        "betrayal",
        "danger",
        "panic",
        "attack"
    ]

    score = 0

    for word in words:
        if word in text:
            score += 15

    return score


# -------------------------
# CONTROVERSY SCORE
# -------------------------
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
        "crisis"
    ]

    score = 0

    for word in words:
        if word in text:
            score += 18

    return score


# -------------------------
# RETENTION SCORE
# -------------------------
def retention_score(text):
    length = len(clean_text(text).split())

    if 12 <= length <= 45:
        return 40

    if 8 <= length <= 60:
        return 25

    return 10


# -------------------------
# STORY SCORE
# -------------------------
def story_score(text):
    text = clean_text(text)

    words = [
        "then",
        "after that",
        "suddenly",
        "finally",
        "because"
    ]

    score = 0

    for word in words:
        if word in text:
            score += 10

    return score


# -------------------------
# SPONSOR PENALTY
# -------------------------
def sponsor_penalty(text):
    text = clean_text(text)

    penalty = 0

    for word in SPONSOR_WORDS:
        if word in text:
            penalty -= 80

    return penalty


# -------------------------
# TITLE GENERATION
# -------------------------
def generate_title(niche):
    titles = {
        "geopolitics": [
            "Nobody Expected This Power Shift",
            "The Real Reason Behind This Crisis",
            "This War Just Changed Everything"
        ],
        "finance": [
            "This Money Move Changed Everything"
        ],
        "podcast": [
            "This Podcast Clip Went Viral"
        ],
        "motivation": [
            "This Mindset Will Change Your Life"
        ],
        "general": [
            "This Changed Everything",
            "What Happened Next Is Crazy"
        ]
    }

    return random.choice(
        titles.get(niche, titles["general"])
    )


# -------------------------
# HASHTAGS
# -------------------------
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
            "#viral"
        ],
        "podcast": [
            "#podcast",
            "#clips",
            "#viral"
        ],
        "general": [
            "#viral",
            "#shorts"
        ]
    }

    return tags.get(niche, tags["general"])


# -------------------------
# SCORE SEGMENT
# -------------------------
def score_segment(segment):
    text = segment.get("text", "")
    start = float(segment.get("start", 0))
    end = float(segment.get("end", start + 15))

    niche = detect_niche(text)

    scores = {
        "hook_score": hook_score(text),
        "emotion_score": emotion_score(text),
        "controversy_score": controversy_score(text),
        "retention_score": retention_score(text),
        "story_score": story_score(text),
        "sponsor_penalty": sponsor_penalty(text)
    }

    final_score = sum(scores.values())

    return {
        "text": text,
        "start": start,
        "end": end,
        "niche": niche,
        "title": generate_title(niche),
        "hashtags": generate_hashtags(niche),
        "score_breakdown": scores,
        "final_score": final_score
    }


# -------------------------
# DUPLICATE REMOVAL
# -------------------------
def remove_duplicates(scored):
    unique = []

    for clip in scored:
        duplicate = False

        for existing in unique:
            if abs(
                clip["start"] - existing["start"]
            ) < 25:
                duplicate = True
                break

        if not duplicate:
            unique.append(clip)

    return unique


# -------------------------
# FIND VIRAL SEGMENTS
# -------------------------
def find_viral_segments(transcript_segments):
    scored = []

    for segment in transcript_segments:
        result = score_segment(segment)

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

    if not scored:
        return []

    avg_score = sum(
        x["final_score"] for x in scored
    ) / len(scored)

    if avg_score > 100:
        clip_count = 8
    elif avg_score > 65:
        clip_count = 5
    else:
        clip_count = 4

    return scored[:clip_count]


# -------------------------
# MAIN ENTRY
# -------------------------
def analyze_video(transcript_segments):
    viral_segments = find_viral_segments(
        transcript_segments
    )

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