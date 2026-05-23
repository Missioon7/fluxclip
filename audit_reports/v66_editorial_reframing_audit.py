import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"


def read_jsonl(path, limit=4000):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def latest_job_id(*row_sets):
    latest = None
    for rows in row_sets:
        for row in rows:
            job_id = row.get("job_id")
            if not job_id:
                continue
            ts = row.get("ts", 0)
            if latest is None or ts >= latest[0]:
                latest = (ts, job_id)
    return latest[1] if latest else None


def reason_counts(rows):
    counts = Counter()
    for row in rows:
        for reason in row.get("reasons", []) or []:
            counts[str(reason)] += 1
    return counts.most_common(12)


def top_previews(rows, limit=10):
    previews = []
    for row in rows:
        preview = row.get("preview")
        if not preview:
            continue
        previews.append({
            "event": row.get("event"),
            "start": row.get("start"),
            "end": row.get("end"),
            "score": row.get("score"),
            "title_alignment_score": row.get("title_alignment_score"),
            "reframe_type": row.get("reframe_type"),
            "stakes_score": row.get("stakes_score"),
            "consequence_score": row.get("consequence_score"),
            "preview": preview,
        })
    return previews[:limit]


def main():
    editorial = read_jsonl(ANALYTICS / "editorial_candidates.jsonl")
    creator_qa = read_jsonl(ANALYTICS / "creator_qa.jsonl")
    job_id = latest_job_id(editorial, creator_qa)

    if not job_id:
        print(json.dumps({
            "ok": False,
            "message": "No editorial or Creator QA artifacts found.",
        }, indent=2))
        return

    erows = [r for r in editorial if r.get("job_id") == job_id]
    qrows = [r for r in creator_qa if r.get("job_id") == job_id]

    v66_candidates = [r for r in erows if r.get("event") == "V66_EDITORIAL_CANDIDATE_CREATED"]
    v66_boundaries = [r for r in erows if r.get("event") == "V66_CURIOSITY_BOUNDARY_FOUND"]
    v66_condensed = [r for r in erows if r.get("event") == "V66_PAYOFF_CONDENSED_WINDOW"]
    title_scores = [r for r in erows if r.get("event") == "V66_TITLE_ALIGNMENT_SCORE"]
    fallback_results = [r for r in erows if r.get("event") == "V66_EDITORIAL_FALLBACK_RESULT"]
    diagnostics = [r for r in erows if r.get("event") == "V66_CREATOR_QA_REJECTION_DIAGNOSTIC"]
    rejects = [r for r in qrows if r.get("event") == "CREATOR_QA_REJECT"]

    passed = 0
    failed = len(rejects)
    if fallback_results:
        passed = sum(int(r.get("approved", 0) or 0) for r in fallback_results)
        failed = sum(int(r.get("rejected", 0) or 0) for r in fallback_results)

    alignment_values = [
        r.get("title_alignment_score")
        for r in title_scores + v66_candidates
        if isinstance(r.get("title_alignment_score"), (int, float))
    ]

    report = {
        "ok": True,
        "job_id": job_id,
        "v66_candidates_created": len(v66_candidates),
        "v66_curiosity_boundaries_found": len(v66_boundaries),
        "v66_condensed_windows": len(v66_condensed),
        "title_alignment_scores": {
            "count": len(alignment_values),
            "min": min(alignment_values) if alignment_values else None,
            "max": max(alignment_values) if alignment_values else None,
            "average": round(sum(alignment_values) / len(alignment_values), 2) if alignment_values else None,
        },
        "creator_qa": {
            "passed": passed,
            "failed": failed,
            "top_failure_reasons": reason_counts(rejects),
        },
        "v66_rejection_diagnostics": [
            {
                "start": r.get("start"),
                "end": r.get("end"),
                "hook_score": r.get("hook_score"),
                "payoff_score": r.get("payoff_score"),
                "standalone_context_score": r.get("standalone_context_score"),
                "title_alignment_score": r.get("title_alignment_score"),
                "reframe_type": r.get("reframe_type"),
                "exact_missing_component": r.get("exact_missing_component"),
                "preview": r.get("preview"),
            }
            for r in diagnostics[:10]
        ],
        "latest_v66_fallback_result": fallback_results[-1] if fallback_results else None,
        "top_v66_candidate_previews": top_previews(v66_candidates + v66_condensed, limit=10),
        "rerun_justified": not bool(v66_candidates or fallback_results),
        "rerun_reason": (
            "Latest artifacts do not include V66 candidate/fallback logs; run a fresh job to validate V66."
            if not bool(v66_candidates or fallback_results)
            else "V66 artifacts exist for the latest job; inspect pass/fail counts before rerunning."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
