from pathlib import Path
import ast, re, json

FILES = ["server.py", "pipeline_runner.py", "visual_engine.py"]

checks = {
    "server_routes": [
        "worker-status", "status/{job_id}", "feedback",
        "cleanup-preview", "deep", "analytics", "production-health"
    ],
    "pipeline_features": [
        "v19_niche_native_signals",
        "v23_visual_clip_score",
        "v25_feedback_learning_boost",
        "v33_story_arc_score",
        "v34_creator_pack_metadata",
        "extract_best_thumbnail_frames",
        "log_visual_intelligence",
        "creator_pack",
        "score_breakdown",
        "detected_niche",
        "payoff_bonus",
        "story_score",
        "visual_score",
    ],
    "quality_risks": [
        "No valid viral clips found",
        "weak_creator_start",
        "weak_creator_ending",
        "sponsor",
        "CTA",
        "ad",
        "rejected",
        "continue",
        "return []",
    ],
    "asr_safety": [
        "signal.alarm",
        "threading.current_thread",
        "main_thread",
        "ASRTimeout",
        "transcribe",
        "task=\"transcribe\"",
    ],
}

report = {}

for file in FILES:
    p = Path(file)
    if not p.exists():
        report[file] = {"exists": False}
        continue

    text = p.read_text(errors="ignore")
    lines = text.splitlines()

    data = {
        "exists": True,
        "lines": len(lines),
        "syntax_ok": True,
        "functions": [],
        "matches": {},
    }

    try:
        tree = ast.parse(text)
        data["functions"] = [
            n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    except Exception as e:
        data["syntax_ok"] = False
        data["syntax_error"] = str(e)

    for group, terms in checks.items():
        data["matches"][group] = {}
        for term in terms:
            hits = []
            for i, line in enumerate(lines, 1):
                if term.lower() in line.lower():
                    hits.append({"line": i, "text": line.strip()[:180]})
            data["matches"][group][term] = hits[:10]

    report[file] = data

out = Path("audit_reports/full_code_audit.json")
out.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("✅ Audit saved:", out)
for file, data in report.items():
    print("\n===", file, "===")
    print("exists:", data.get("exists"))
    print("lines:", data.get("lines"))
    print("syntax_ok:", data.get("syntax_ok"))
    print("functions:", len(data.get("functions", [])))
    for group in checks:
        found = sum(1 for term, hits in data.get("matches", {}).get(group, {}).items() if hits)
        total = len(checks[group])
        print(f"{group}: {found}/{total}")
