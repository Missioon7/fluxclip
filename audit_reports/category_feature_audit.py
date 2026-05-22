from pathlib import Path
import re, json

p = Path("pipeline_runner.py")
text = p.read_text(errors="ignore").lower()

categories = {
    "podcast_interview": [
        "speaker", "conversation", "interview", "question", "answer",
        "debate", "host", "guest", "interrupt"
    ],
    "geopolitics_news": [
        "geopolitics", "politics_news", "government", "war", "election",
        "china", "india", "pakistan", "russia", "america", "israel"
    ],
    "finance_business": [
        "finance_business", "money", "business", "market", "stock",
        "revenue", "profit", "startup", "sales"
    ],
    "crime_mystery": [
        "crime_mystery", "crime", "murder", "case", "police",
        "hidden truth", "investigation"
    ],
    "entertainment_drama": [
        "drama", "celebrity", "movie", "show", "viral",
        "reaction", "emotion", "shocking"
    ],
    "education_explainer": [
        "education", "explainer", "learn", "lesson", "why",
        "how", "therefore", "that means"
    ],
}

report = {}

for cat, terms in categories.items():
    hits = {}
    for term in terms:
        lines = []
        for i, line in enumerate(text.splitlines(), 1):
            if term in line:
                lines.append(i)
        if lines:
            hits[term] = lines[:20]

    report[cat] = {
        "terms_found": len(hits),
        "total_terms": len(terms),
        "coverage_percent": round(len(hits) / len(terms) * 100, 2),
        "hits": hits
    }

Path("audit_reports/category_feature_audit.json").write_text(json.dumps(report, indent=2))

print("✅ Category audit saved: audit_reports/category_feature_audit.json")
for cat, data in report.items():
    print(f"{cat}: {data['terms_found']}/{data['total_terms']} = {data['coverage_percent']}%")
