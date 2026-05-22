import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pipeline_runner as editorial


DEFAULT_FIXTURE_PATH = Path("audit_reports/editorial_payoff_fixtures.json")
DEFAULT_REPORT_PATH = Path("audit_reports/PAYOFF_SEMANTIC_FIXTURE_REPORT.md")


def load_fixtures(path):
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("fixture file must contain a JSON list")
    return data


def combined_payoff(text):
    v43_score, v43_reasons = editorial.v43_hinglish_payoff_bonus(text)
    v44_score, v44_reasons, v44_confidence = editorial.v44_semantic_payoff_score(text)
    if editorial.v44_payoff_quality_block(text):
        score = 0
    else:
        score = max(
            editorial.v6_payoff_bonus(text),
            editorial.v7_better_payoff_bonus(text),
            v43_score,
            v44_score,
        )
    return {
        "score": editorial.safe_float(score),
        "v43_score": editorial.safe_float(v43_score),
        "v43_reasons": v43_reasons,
        "v44_score": editorial.safe_float(v44_score),
        "v44_reasons": v44_reasons,
        "v44_confidence": v44_confidence,
    }


def qa_result(text, payoff):
    clip = {
        "start": 0,
        "end": 45,
        "title": "fixture",
        "expanded_text": text,
        "source_text": text,
        "score_breakdown": {
            "hook_bonus": 0,
            "payoff_bonus": payoff["score"],
            "context_quality": editorial.v7_context_quality_score(text),
            "low_confidence_asr": False,
            "editor_reasons": [],
            "true_creator_reasons": [],
        },
    }
    reasons = editorial.creator_qa_rejection_reasons(clip, captions=[])
    return {
        "decision": "reject" if reasons else "approve",
        "reasons": reasons,
    }


def evaluate_fixture(fixture):
    text = str(fixture.get("text") or "")
    expected_payoff = bool(fixture.get("expected_payoff"))
    expected_v44 = bool(fixture.get("expected_v44"))
    expected_reject = bool(fixture.get("expected_creator_qa_reject"))

    payoff = combined_payoff(text)
    qa = qa_result(text, payoff)
    actual_payoff = payoff["score"] > 0
    actual_v44 = payoff["v44_score"] > 0
    actual_reject = qa["decision"] == "reject"

    checks = {
        "payoff": actual_payoff == expected_payoff,
        "v44": actual_v44 == expected_v44,
        "creator_qa": actual_reject == expected_reject,
    }
    passed = all(checks.values())
    false_positive = actual_payoff and not expected_payoff
    false_negative = expected_payoff and not actual_payoff
    return {
        "name": fixture.get("name"),
        "language": fixture.get("language"),
        "expected_payoff": expected_payoff,
        "actual_payoff": actual_payoff,
        "expected_v44": expected_v44,
        "actual_v44": actual_v44,
        "expected_creator_qa_reject": expected_reject,
        "actual_creator_qa_reject": actual_reject,
        "combined_payoff": payoff["score"],
        "v43_score": payoff["v43_score"],
        "v43_reasons": payoff["v43_reasons"],
        "v44_score": payoff["v44_score"],
        "v44_reasons": payoff["v44_reasons"],
        "v44_confidence": payoff["v44_confidence"],
        "qa_reasons": qa["reasons"],
        "checks": checks,
        "passed": passed,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def format_report(results):
    false_positive_count = sum(1 for r in results if r["false_positive"])
    false_negative_count = sum(1 for r in results if r["false_negative"])
    failed = [r for r in results if not r["passed"]]

    lines = [
        "# Payoff Semantic Fixture Report",
        "",
        "Scope: deterministic payoff fixtures only. No video, ASR, FFmpeg, export, server, frontend, upload, or GPU flow.",
        f"Fixtures: {len(results)}",
        f"Passed: {len(results) - len(failed)}",
        f"Failed: {len(failed)}",
        f"False positives: {false_positive_count}",
        f"False negatives: {false_negative_count}",
        "",
        "## Fixtures",
    ]

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(
            f"- {status} {r['name']} ({r['language']}): "
            f"expected_payoff={r['expected_payoff']} actual_payoff={r['actual_payoff']} "
            f"combined={r['combined_payoff']} v43={r['v43_score']} "
            f"v44={r['v44_score']} confidence={r['v44_confidence']} "
            f"qa_reject={r['actual_creator_qa_reject']}"
        )
        lines.append(
            f"  reasons: v43={r['v43_reasons']} v44={r['v44_reasons']} qa={r['qa_reasons']}"
        )

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Run offline semantic payoff fixtures.")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURE_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()

    fixtures = load_fixtures(args.fixtures)
    results = [evaluate_fixture(fixture) for fixture in fixtures]
    report_text = format_report(results)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    print(report_text)
    print(f"PAYOFF_SEMANTIC_FIXTURE_REPORT_WRITTEN {report_path}")

    if any(not r["passed"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
