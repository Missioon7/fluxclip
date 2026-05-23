import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"


def read_jsonl(path, limit=2000):
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


def latest_job_id(rows):
    latest = None
    for row in rows:
        job_id = row.get("job_id")
        if not job_id:
            continue
        ts = row.get("ts", 0)
        if latest is None or ts >= latest[0]:
            latest = (ts, job_id)
    return latest[1] if latest else None


def top_previews(rows, limit=8):
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
            "hook_score": row.get("hook_score"),
            "payoff_score": row.get("payoff_score"),
            "standalone_context_score": row.get("standalone_context_score"),
            "creator_qa_reasons": row.get("creator_qa_reasons"),
            "preview": preview,
        })
    return previews[:limit]


def main():
    editorial = read_jsonl(ANALYTICS / "editorial_candidates.jsonl")
    creator_qa = read_jsonl(ANALYTICS / "creator_qa.jsonl")
    clip_intel = read_jsonl(ANALYTICS / "clip_intelligence.jsonl")
    job_id = latest_job_id(editorial) or latest_job_id(creator_qa) or latest_job_id(clip_intel)

    if not job_id:
        print(json.dumps({
            "ok": False,
            "message": "No editorial, Creator QA, or clip intelligence artifacts found.",
        }, indent=2))
        return

    erows = [r for r in editorial if r.get("job_id") == job_id]
    qrows = [r for r in creator_qa if r.get("job_id") == job_id]
    crows = [r for r in clip_intel if r.get("job_id") == job_id]

    anchors = [r for r in erows if r.get("event") == "V61_PAYOFF_ANCHOR_FOUND"]
    payoff_candidates = [r for r in erows if r.get("event") == "V61_PAYOFF_CANDIDATE_CREATED"]
    story_windows = [r for r in erows if r.get("event") == "V63_STORY_WINDOW_CREATED"]
    v62_scores = [r for r in erows if r.get("event") == "V62_HOOK_PAYOFF_SCORE"]
    v64_results = [r for r in erows if r.get("event") == "V64_ZERO_SAFE_FALLBACK_RESULT"]
    rejects = [r for r in qrows if r.get("event") == "CREATOR_QA_REJECT"]
    zero_safe = [r for r in qrows if r.get("event") == "CREATOR_QA_ZERO_SAFE_CLIPS"]
    completed = [r for r in crows if r.get("stage") == "completed"]

    reason_counts = Counter()
    for row in rejects:
        for reason in row.get("reasons", []) or []:
            reason_counts[str(reason)] += 1

    score_fail_counts = Counter()
    for row in v62_scores:
        reasons = row.get("creator_qa_reasons", []) or []
        if row.get("payoff_score", 0) <= 0:
            score_fail_counts["missing_payoff_score"] += 1
        if row.get("hook_score", 0) <= 0:
            score_fail_counts["missing_hook_score"] += 1
        if row.get("standalone_context_score", 0) < 8:
            score_fail_counts["weak_standalone_context_score"] += 1
        for reason in reasons:
            score_fail_counts[f"creator_qa_{reason}"] += 1

    rerun_justified = bool(
        anchors
        or payoff_candidates
        or story_windows
        or (v64_results and v64_results[-1].get("approved", 0) > 0)
    )

    report = {
        "ok": True,
        "job_id": job_id,
        "payoff_anchors": len(anchors),
        "payoff_native_candidates": len(payoff_candidates),
        "story_complete_candidates": len(story_windows),
        "v62_scored_candidates": len(v62_scores),
        "completed_clips": len(completed),
        "creator_qa_rejections": len(rejects),
        "creator_qa_zero_safe_events": len(zero_safe),
        "why_candidates_fail_creator_qa": reason_counts.most_common(10),
        "score_failure_signals": score_fail_counts.most_common(10),
        "v64_latest_result": v64_results[-1] if v64_results else None,
        "top_candidate_previews": top_previews(payoff_candidates + story_windows + v62_scores, limit=10),
        "rerun_justified": rerun_justified,
        "rerun_reason": (
            "New V61/V63/V64 editorial generation is installed; run a fresh Colab job to produce new artifacts."
            if rerun_justified else
            "No V61/V63 candidates found in latest artifacts; rerun still useful to verify logs on current code."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
