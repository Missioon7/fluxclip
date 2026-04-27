import random


# -------------------------
# HARD SPONSOR / CTA FILTER
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

    # course/ad/CTA blocks
    "career247",
    "career 247",
    "discount",
    "course",
    "courses",
    "offer",
    "sale",
    "mega savings",
    "flat discount",
    "price increase",
    "comment section",
    "click on this link",
    "register now",
    "call now",
    "email id",
    "phone number",
    "certificate",
    "certificates",
    "interview",
    "interviews",
    "job focused",
    "golden opportunity",
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


def is_sponsor_segment(text):
    text = clean_text(text)

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
    text = clean_text(text)

    words = [
        "death",
        "dead",
        "fear",
        "destroyed",
        "danger",
        "panic",
        "attack",
        "killed",
        "missing",
        "weak",
    ]

    score = 0

    for word in words:
        if word in text:
            score += 12

    return min(score, 36)


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
    ]

    score = 0

    for word in words:
        if word in text:
            score += 8

    return min(score, 24)


def sponsor_penalty(text):
    text = clean_text(text)

    penalty = 0

    for word in SPONSOR_WORDS:
        if word in text:
            penalty -= 80

    return penalty


def generate_title(text, niche):
    text = clean_text(text)

    if "nuclear" in text and ("scientist" in text or "scientists" in text):
        return "Why Nuclear Scientists Are Dying"

    if "china" in text and ("america" in text or "usa" in text):
        return "US vs China Just Got Darker"

    if "foreign power" in text:
        return "A Foreign Power Is Targeting Them"

    if "war" in text:
        return "This War Just Changed Everything"

    titles = {
        "geopolitics": [
            "Nobody Expected This Power Shift",
            "The Real Reason Behind This Crisis",
            "This Global Crisis Is Getting Worse"
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
        "story": [
            "What Happened Next Is Crazy"
        ],
        "general": [
            "This Changed Everything",
            "What Happened Next Is Crazy"
        ]
    }

    return random.choice(titles.get(niche, titles["general"]))


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
        "sponsor_penalty": sponsor_penalty(text),
    }

    final_score = sum(scores.values())

    if final_score < 25:
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

    return scored[:5]


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