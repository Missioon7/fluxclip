import random

SPONSOR_WORDS = [
    "subscribe",
    "like and share",
    "like share",
    "sponsored",
    "sponsor",
    "download now",
    "download app",
    "link in bio",
    "use my code",
    "promo code",
    "follow me",
    "telegram channel",
    "join my telegram",
    "click the link",
]

NICHE_KEYWORDS = {
    "finance": ["money", "stock", "crypto", "business", "investment", "income", "profit", "loss", "market"],
    "motivation": ["success", "mindset", "discipline", "grind", "dream", "goal", "hard work", "failure"],
    "geopolitics": ["war", "china", "india", "usa", "america", "military", "border", "iran", "israel", "pakistan"],
    "podcast": ["podcast", "interview", "conversation", "guest", "host"],
    "education": ["learn", "explained", "history", "facts", "science", "study", "students"],
    "comedy": ["funny", "joke", "laugh", "comedy", "roast"],
    "story": ["then", "after that", "suddenly", "one day", "finally"],
}


def _clean_text(text):
    if text is None:
        return ""
    return str(text).strip()


def detect_niche(text):
    text = _clean_text(text).lower()

    best_niche = "general"
    best_hits = 0

    for niche, keywords in NICHE_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits > best_hits:
            best_hits = hits
            best_niche = niche

    return best_niche


def sponsor_penalty(text):
    text = _clean_text(text).lower()
    hits = sum(1 for word in SPONSOR_WORDS if word in text)
    return -60 * hits


def hook_score(text):
    text = _clean_text(text).lower()

    hooks = [
        "nobody knows",
        "truth",
        "secret",
        "what happened next",
        "you won't believe",
        "shocking",
        "biggest mistake",
        "real reason",
        "dark truth",
        "hidden",
        "exposed",
        "why",
        "how",
    ]

    return sum(18 for hook in hooks if hook in text)


def emotion_score(text):
    text = _clean_text(text).lower()

    emotional_words = [
        "death",
        "betrayal",
        "cry",
        "love",
        "destroyed",
        "fear",
        "revenge",
        "pain",
        "angry",
        "sad",
        "shock",
        "danger",
        "risk",
        "win",
        "lose",
        "failure",
        "success",
    ]

    return sum(12 for word in emotional_words if word in text)


def controversy_score(text):
    text = _clean_text(text).lower()

    words = [
        "war",
        "fight",
        "vs",
        "against",
        "ban",
        "scam",
        "exposed",
        "cheating",
        "crisis",
        "attack",
        "threat",
        "dictator",
    ]

    return sum(14 for word in words if word in text)


def retention_score(text):
    words = _clean_text(text).split()

    if not words:
        return 0

    length = len(words)

    if 18 <= length <= 75:
        return 35
    if 8 <= length < 18:
        return 22
    if 76 <= length <= 120:
        return 20

    return 8


def story_score(text):
    text = _clean_text(text).lower()

    markers = [
        "then",
        "after that",
        "suddenly",
        "but",
        "until",
        "finally",
        "because",
        "so",
    ]

    return sum(8 for marker in markers if marker in text)


def generate_title(text, niche="general"):
    niche_titles = {
        "finance": [
            "This Money Move Changed Everything",
            "Nobody Talks About This Business Truth",
            "The Finance Mistake Most People Make",
        ],
        "motivation": [
            "This Mindset Can Change Your Life",
            "The Discipline Truth Nobody Likes",
            "This Is Why Most People Fail",
        ],
        "geopolitics": [
            "This Global Move Changed Everything",
            "The Real Reason Behind This Crisis",
            "Nobody Expected This Power Shift",
        ],
        "podcast": [
            "This Podcast Moment Went Deep",
            "He Said What Nobody Expected",
            "This Conversation Changed Everything",
        ],
        "education": [
            "This Fact Will Surprise You",
            "The Simple Explanation Nobody Gives",
            "You Should Know This",
        ],
        "comedy": [
            "This Moment Was Too Funny",
            "He Did Not Just Say That",
            "This Clip Is Pure Chaos",
        ],
        "story": [
            "What Happened Next Is Crazy",
            "This Story Took A Wild Turn",
            "Nobody Expected This Ending",
        ],
        "general": [
            "This Changed Everything",
            "Nobody Expected This",
            "The Truth Behind This",
            "What Happened Next Is Crazy",
            "This Went Viral For A Reason",
        ],
    }

    titles = niche_titles.get(niche, niche_titles["general"])
    return random.choice(titles)


def generate_hashtags(niche):
    hashtag_map = {
        "finance": ["#finance", "#money", "#business", "#shorts", "#viral"],
        "motivation": ["#motivation", "#success", "#mindset", "#shorts", "#viral"],
        "geopolitics": ["#geopolitics", "#india", "#worldnews", "#shorts", "#viral"],
        "podcast": ["#podcast", "#clips", "#shorts", "#viral"],
        "education": ["#facts", "#history", "#learn", "#shorts", "#viral"],
        "comedy": ["#funny", "#comedy", "#shorts", "#viral"],
        "story": ["#storytime", "#shorts", "#viral"],
        "general": ["#viral", "#shorts", "#trending"],
    }

    return hashtag_map.get(niche, hashtag_map["general"])


def score_segment(segment):
    text = _clean_text(segment.get("text", ""))
    start = float(segment.get("start", 0))
    end = float(segment.get("end", start + 20))

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

    return {
        "text": text,
        "start": start,
        "end": end,
        "niche": niche,
        "title": generate_title(text, niche),
        "hashtags": generate_hashtags(niche),
        "score_breakdown": scores,
        "final_score": final_score,
    }


def find_viral_segments(transcript_segments):
    scored = []

    for segment in transcript_segments:
        result = score_segment(segment)

        duration = result["end"] - result["start"]
        if duration < 2:
            continue

        scored.append(result)

    scored = sorted(scored, key=lambda x: x["final_score"], reverse=True)

    if not scored:
        return []

    avg_score = sum(x["final_score"] for x in scored) / len(scored)

    if avg_score > 90:
        clip_count = 8
    elif avg_score > 55:
        clip_count = 5
    else:
        clip_count = 3

    return scored[:clip_count]


def analyze_video(transcript_segments):
    """
    Backward-compatible function for pipeline_runner.py.
    Returns same basic fields as old engine + new V3 metadata.
    """
    viral_segments = find_viral_segments(transcript_segments)

    formatted_segments = []

    for seg in viral_segments:
        formatted_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "score": seg["final_score"],
            "title": seg["title"],
            "hashtags": seg["hashtags"],
            "niche": seg["niche"],
            "score_breakdown": seg["score_breakdown"],
        })

    return formatted_segments