import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"


def read_jsonl(path, limit=5000):
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


def previews(rows, limit=8):
    out = []
    for row in rows:
        preview = row.get("preview") or row.get("expanded_preview") or row.get("text_preview")
        if not preview:
            continue
        out.append({
            "event": row.get("event"),
            "start": row.get("start"),
            "end": row.get("end"),
            "reason": row.get("reason"),
            "missing": row.get("missing"),
            "hook": row.get("hook"),
            "v67_story_score": row.get("v67_story_score"),
            "v67_payoff_score": row.get("v67_payoff_score"),
            "v67_standalone_score": row.get("v67_standalone_score"),
            "preview": preview,
        })
    return out[:limit]


def count_reasons(rows):
    counter = Counter()
    for row in rows:
        for reason in row.get("reasons", []) or []:
            counter[str(reason)] += 1
    return counter.most_common(12)


def main():
    editorial = read_jsonl(ANALYTICS / "editorial_candidates.jsonl")
    creator_qa = read_jsonl(ANALYTICS / "creator_qa.jsonl")
    clip_intel = read_jsonl(ANALYTICS / "clip_intelligence.jsonl")
    job_id = latest_job_id(editorial, creator_qa, clip_intel)

    if not job_id:
        print(json.dumps({
            "ok": False,
            "message": "No editorial, Creator QA, or clip intelligence artifacts found.",
        }, indent=2))
        return

    erows = [r for r in editorial if r.get("job_id") == job_id]
    qrows = [r for r in creator_qa if r.get("job_id") == job_id]
    crows = [r for r in clip_intel if r.get("job_id") == job_id]

    story_found = [r for r in erows if r.get("event") == "V67_STORY_UNIT_FOUND"]
    story_skipped = [r for r in erows if r.get("event") == "V67_STORY_UNIT_SKIPPED"]
    hooks = [r for r in erows if r.get("event") == "V67_SYNTHETIC_HOOK_CREATED"]
    bridges_applied = [r for r in erows if r.get("event") == "V67_CONTEXT_BRIDGE_APPLIED"]
    bridges_skipped = [r for r in erows if r.get("event") == "V67_CONTEXT_BRIDGE_SKIPPED"]
    validation_pass = [r for r in erows if r.get("event") == "V67_PAYOFF_VALIDATION_PASS"]
    validation_fail = [r for r in erows if r.get("event") == "V67_PAYOFF_VALIDATION_FAIL"]
    preflight = [r for r in erows if r.get("event") == "V67_CREATOR_QA_PREFLIGHT"]
    fallback_results = [r for r in erows if r.get("event") == "V67_ZERO_SAFE_STORY_FALLBACK_RESULT"]
    rejects = [r for r in qrows if r.get("event") == "CREATOR_QA_REJECT"]
    completed = [r for r in crows if r.get("stage") == "completed"]

    before_reasons = Counter()
    for row in preflight:
        for reason in row.get("likely_failure_reasons", []) or []:
            before_reasons[str(reason)] += 1

    skip_reasons = Counter(str(r.get("reason") or "unknown") for r in story_skipped)
    source_has_enough_story_density = len(story_found) >= 3 or (
        len(story_found) >= 1 and len(story_found) >= max(1, len(story_skipped) // 5)
    )

    report = {
        "ok": True,
        "job_id": job_id,
        "story_units_found": len(story_found),
        "story_units_skipped": len(story_skipped),
        "story_unit_skip_reasons": skip_reasons.most_common(10),
        "synthetic_hooks_created": len(hooks),
        "context_bridges_applied": len(bridges_applied),
        "context_bridges_skipped": len(bridges_skipped),
        "payoff_validation": {
            "pass": len(validation_pass),
            "fail": len(validation_fail),
        },
        "creator_qa_before_preflight_likely_reasons": before_reasons.most_common(10),
        "creator_qa_after": {
            "completed_clip_rows": len(completed),
            "reject_rows": len(rejects),
            "top_failure_reasons": count_reasons(rejects),
        },
        "latest_v67_fallback_result": fallback_results[-1] if fallback_results else None,
        "top_story_unit_previews": previews(story_found, limit=8),
        "top_failed_previews": previews(validation_fail + story_skipped, limit=8),
        "source_has_enough_story_density": source_has_enough_story_density,
        "rerun_justified": not bool(story_found or fallback_results or preflight),
        "rerun_reason": (
            "Latest artifacts do not contain V67 logs; run a fresh job to validate standalone story compilation."
            if not bool(story_found or fallback_results or preflight)
            else "V67 artifacts exist for the latest job; inspect story density and QA pass/fail before rerunning."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
