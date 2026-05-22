import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pipeline_runner as editorial


DEFAULT_JOB_IDS = [
    "candidate_funnel_e0926df0",
    "v44_final_e0926df0",
]


def iter_jsonl(path):
    path = Path(path)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def compact(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def preview(text, limit=260):
    text = compact(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def split_window(text):
    text = compact(text)
    if not text:
        return "", "", ""

    sentences = [s.strip() for s in re.split(r"[.!?\n\u0964]+|à¥¤", text) if s.strip()]
    if len(sentences) >= 3:
        third = max(1, len(sentences) // 3)
        setup = " ".join(sentences[:third])
        middle = " ".join(sentences[third : max(third + 1, (len(sentences) * 2) // 3)])
        ending = " ".join(sentences[max(third + 1, (len(sentences) * 2) // 3) :])
        return setup, middle, ending

    words = text.split()
    third = max(1, len(words) // 3)
    return (
        " ".join(words[:third]),
        " ".join(words[third : third * 2]),
        " ".join(words[third * 2 :]),
    )


PATTERNS = {
    "effort_reward": [
        "mehnat", "mehnad", "mahnat", "मेहनत", "महनत", "मेहनेद", "मेहनद",
        "struggle", "hard work", "milega", "मिलेगा", "success", "safalta",
        "सक्सेस", "सक्स", "फल मिलेगा",
    ],
    "contrast_reveal": [
        "lekin", "लेकिन", "par", "पर", "but", "actually", "asal", "asli",
        "sach", "पता", "nikla", "revealed", "turns out",
    ],
    "motivational_landing": [
        "greatest revenge", "revenge", "रिवेंज", "र्वेंज", "badla", "बदला",
        "surrender", "सरेंडर", "sir jhuka", "sar jhuka", "itni mehnat",
        "इतनी मेहनत", "poori mehnat", "पूरी मेहनत",
    ],
    "preparation_future": [
        "taiyar", "tayyar", "तैयार", "taiyari", "तैयारी", "skillset",
        "स्किलसेट", "darwaza", "दरवाजा", "दरवाज़ा", "weapon",
    ],
    "unresolved_teaser": [
        "aage kya", "आगे क्या", "phir kya", "उसके बाद क्या", "watch till",
        "sabse important part", "सबसे important", "result ke liye aage",
    ],
    "incomplete_setup": [
        "agar", "अगर", "kyunki", "क्योंकि", "because", "lekin", "लेकिन",
        "jab", "जब", "if", "when",
    ],
}


def phrase_hits(text, phrases):
    low = compact(text).lower()
    return [p for p in phrases if p.lower() in low]


def analyze_text(text):
    setup, middle, ending = split_window(text)
    v43, v43_reasons = editorial.v43_hinglish_payoff_bonus(text)
    v44, v44_reasons, v44_confidence = editorial.v44_semantic_payoff_score(text)
    quality_blocked = editorial.v44_payoff_quality_block(text)
    combined = 0 if quality_blocked else max(
        editorial.v6_payoff_bonus(text),
        editorial.v7_better_payoff_bonus(text),
        v43,
        v44,
    )

    hits = {name: phrase_hits(text, values) for name, values in PATTERNS.items()}
    end_hits = {
        name: phrase_hits(ending, values)
        for name, values in PATTERNS.items()
    }

    possible_reveal = (
        hits["contrast_reveal"]
        or end_hits["effort_reward"]
        or end_hits["motivational_landing"]
        or end_hits["preparation_future"]
    )
    unresolved = bool(hits["unresolved_teaser"])
    incomplete = (
        len(ending.split()) < 8
        or compact(ending).lower().endswith((
            "and", "but", "because", "so", "then", "that", "if", "to",
            "agar", "kyunki", "lekin", "जब", "अगर", "क्योंकि", "लेकिन",
        ))
    )

    if combined > 0 and not unresolved and not incomplete:
        rank = "likely_true_payoff"
    elif possible_reveal and not unresolved:
        rank = "weak_payoff"
    elif possible_reveal and unresolved:
        rank = "false_payoff"
    else:
        rank = "no_detected_payoff"

    hints = []
    if end_hits["effort_reward"] or end_hits["motivational_landing"]:
        hints.append("candidate likely contains payoff near end")
        hints.append("possible motivational landing")
    if hits["contrast_reveal"]:
        hints.append("possible reveal phrase")
    if not possible_reveal:
        hints.append("candidate lacks emotional resolution")
    if unresolved:
        hints.append("unresolved teaser chain")
    if incomplete:
        hints.append("possible incomplete setup/ending chain")
    if combined == 0 and possible_reveal:
        hints.append("human-looking payoff not recognized by V44")

    return {
        "setup": setup,
        "middle": middle,
        "ending": ending,
        "combined_payoff": editorial.safe_float(combined),
        "v43": editorial.safe_float(v43),
        "v43_reasons": v43_reasons,
        "v44": editorial.safe_float(v44),
        "v44_reasons": v44_reasons,
        "v44_confidence": v44_confidence,
        "quality_blocked": quality_blocked,
        "hits": hits,
        "ending_hits": end_hits,
        "rank": rank,
        "hints": sorted(set(hints)),
    }


def load_candidate_rows(job_ids, path):
    rows = []
    wanted = set(job_ids)
    for row in iter_jsonl(path):
        if wanted and row.get("job_id") not in wanted:
            continue
        text = row.get("expanded_preview") or row.get("text_preview") or ""
        rows.append({
            "job_id": row.get("job_id"),
            "candidate_index": row.get("candidate_index"),
            "start": row.get("expanded_start", row.get("start")),
            "end": row.get("expanded_end", row.get("end")),
            "decision": row.get("filter_decision"),
            "reason": row.get("filter_reason"),
            "stored_payoff": row.get("payoff_bonus"),
            "stored_v43": row.get("v43_hinglish_payoff_bonus"),
            "stored_v44": row.get("v44_semantic_payoff_score"),
            "stored_completeness": row.get("story_completeness_estimate"),
            "stored_continuation": row.get("continuation_risk"),
            "text": text,
        })
    return rows


def format_report(rows):
    analyzed = []
    for row in rows:
        analysis = analyze_text(row["text"])
        analyzed.append({**row, "analysis": analysis})

    rank_counts = Counter(item["analysis"]["rank"] for item in analyzed)
    decision_counts = Counter(item["decision"] for item in analyzed)
    v44_misses = [
        item for item in analyzed
        if item["analysis"]["v44"] == 0
        and any(item["analysis"]["hits"][k] for k in [
            "effort_reward", "motivational_landing", "preparation_future", "contrast_reveal"
        ])
    ]

    lines = [
        "# Narrative Payoff Analysis",
        "",
        "Scope: offline analysis of saved candidate transcript windows only. No ASR, video, FFmpeg, export, or server execution.",
        f"Candidates analyzed: {len(analyzed)}",
        "",
        "## Summary",
    ]
    for key, count in sorted(decision_counts.items()):
        lines.append(f"- decision {key}: {count}")
    for key, count in sorted(rank_counts.items()):
        lines.append(f"- rank {key}: {count}")
    lines.append(f"- human-looking payoff with V44=0: {len(v44_misses)}")
    lines.append("")

    lines.append("## Candidate Detail")
    for item in analyzed:
        a = item["analysis"]
        phrase_summary = []
        for key in ["effort_reward", "contrast_reveal", "motivational_landing", "preparation_future", "unresolved_teaser"]:
            if a["hits"][key]:
                phrase_summary.append(f"{key}={a['hits'][key][:5]}")
        lines.extend([
            "",
            f"### {item['job_id']} candidate {item['candidate_index']} ({item['start']}->{item['end']})",
            f"- decision: {item['decision']} / {item['reason']}",
            f"- stored payoff/v43/v44: {item['stored_payoff']} / {item['stored_v43']} / {item['stored_v44']}",
            f"- replayed payoff/v43/v44: {a['combined_payoff']} / {a['v43']} / {a['v44']} confidence={a['v44_confidence']}",
            f"- rank: {a['rank']}",
            f"- stored completeness/continuation: {item['stored_completeness']} / {item['stored_continuation']}",
            f"- phrase hits: {'; '.join(phrase_summary) if phrase_summary else 'none'}",
            f"- human-review hints: {', '.join(a['hints']) if a['hints'] else 'none'}",
            f"- setup: {preview(a['setup'])}",
            f"- middle: {preview(a['middle'])}",
            f"- ending: {preview(a['ending'])}",
        ])

    lines.extend([
        "",
        "## Semantic Gap Notes",
        "- If `human-looking payoff with V44=0` is nonzero, the gap is detector semantics or transcript corruption, not candidate visibility.",
        "- If candidates are ranked `weak_payoff`, they should not bypass Creator QA; they are review hints only.",
        "- If payoff language is present only in noisy/garbled text, ASR stability remains the upstream blocker.",
    ])

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Offline narrative/payoff analysis for saved FluxClip candidates.")
    parser.add_argument("--candidate-log", default="analytics/candidate_funnel.jsonl")
    parser.add_argument("--job-id", action="append", dest="job_ids")
    parser.add_argument("--output", default="audit_reports/NARRATIVE_PAYOFF_ANALYSIS.md")
    args = parser.parse_args()

    job_ids = args.job_ids or DEFAULT_JOB_IDS
    rows = load_candidate_rows(job_ids, args.candidate_log)
    report = format_report(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"NARRATIVE_PAYOFF_ANALYSIS_WRITTEN {output}")


if __name__ == "__main__":
    main()
