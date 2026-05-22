import json
from pathlib import Path

FUNNEL = Path("analytics/candidate_funnel.jsonl")
OUT = Path("audit_reports/V46_BOUNDARY_REPAIR_ANALYSIS.md")

PAYOFF_HINTS = [
    "mehnat",
    "success",
    "revenge",
    "milega",
    "millega",
    "time aayega",
    "reward",
    "future",
    "struggle",
    "hardwork",
    "payoff",
    "result",
    "phone",
    "wait",
    "dream"
]

MAX_NARRATIVE_FAMILY_SPAN = 120.0

OPENING_GLUE = [
    "to ",
    "so ",
    "and ",
    "but ",
    "because ",
    "ki ",
    "aur ",
    "lekin ",
    "तो ",
    "और ",
    "लेकिन ",
    "क्योंकि ",
]

ENDING_LEAKS = [
    "...",
    " कि ",
    " जब ",
    " अगर ",
    " because ",
    " when ",
    " if ",
]

LANDING_CUES = [
    "milega",
    "success",
    "result",
    "reward",
    "time aayega",
    "revenge",
    "मिलेगा",
    "सक्सेस",
    "मेहनत",
    "उस दिन",
    "अपना टाइम",
    "बदला",
]

def load_rows():
    rows = []
    if not FUNNEL.exists():
        return rows
    for line in FUNNEL.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows

def text_of(row):
    return " ".join(str(row.get(k, "") or "") for k in ["expanded_preview", "text_preview"])

def row_start(row):
    return fnum(row.get("expanded_start", row.get("start", 0)))

def row_end(row):
    return fnum(row.get("expanded_end", row.get("end", 0)))

def window_text(items, repair_start, repair_end):
    parts = []
    for row in items:
        if row_end(row) < repair_start or row_start(row) > repair_end:
            continue
        txt = text_of(row).strip()
        if txt and txt not in parts:
            parts.append(txt)
    return " ".join(parts)

def split_window_text(text):
    text = " ".join(str(text or "").split())
    if not text:
        return "", "", ""
    size = max(1, len(text) // 3)
    return text[:size], text[size: size * 2], text[size * 2:]

def has_hint(text):
    low = text.lower()
    return [h for h in PAYOFF_HINTS if h.lower() in low]

def fnum(value, default=0.0):
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default

def time_overlap_ratio(a, b):
    overlap = max(0.0, min(a["repair_end"], b["repair_end"]) - max(a["repair_start"], b["repair_start"]))
    shortest = max(1.0, min(a["merged_duration"], b["merged_duration"]))
    return overlap / shortest

def time_gap(a, b):
    if a["repair_end"] < b["repair_start"]:
        return b["repair_start"] - a["repair_end"]
    if b["repair_end"] < a["repair_start"]:
        return a["repair_start"] - b["repair_end"]
    return 0.0

def same_narrative_family(a, b):
    if time_overlap_ratio(a, b) >= 0.35:
        return True
    if time_gap(a, b) <= 12.0 and (
        a["edge_label"] == "strong_neighbor_chain"
        or b["edge_label"] == "strong_neighbor_chain"
        or a["duplicate_affinity"] > 0
        or b["duplicate_affinity"] > 0
    ):
        return True
    return False

def can_join_family(chain, family):
    family_start = min(member["repair_start"] for member in family)
    family_end = max(member["repair_end"] for member in family)
    joined_span = max(family_end, chain["repair_end"]) - min(family_start, chain["repair_start"])

    if any(time_overlap_ratio(chain, member) >= 0.35 for member in family):
        return True

    if joined_span > MAX_NARRATIVE_FAMILY_SPAN:
        return False

    return any(same_narrative_family(chain, member) for member in family)

def rank_value(chain_rank):
    order = {
        "editorial_winner": 4,
        "strong_editorial_candidate": 3,
        "possible_editorial_candidate": 2,
        "weak_editorial_candidate": 1,
    }
    return order.get(chain_rank, 0)

def consolidation_score(chain, max_family_overlap):
    duration = chain["merged_duration"]
    pacing_score = 2 if 45.0 <= duration <= 75.0 else 1 if 30.0 <= duration < 45.0 else 0
    decision_score = 1 if chain["decision"] in {"accepted", "accepted_pre_dedupe"} else 0
    duplicate_node_bonus = 1 if chain["decision"] == "duplicate_removed" and chain["edge_label"] == "strong_neighbor_chain" else 0
    redundancy_penalty = 2 if max_family_overlap >= 0.70 else 1 if max_family_overlap >= 0.45 else 0
    trimmed_penalty = 1 if chain["graph_trimmed"] else 0
    continuation_penalty = 2 if chain["continuation_risk"] > 0 else 0

    return (
        chain["chain_score"]
        + chain["repair_quality"]
        + chain["structural_score"]
        + pacing_score
        + decision_score
        + duplicate_node_bonus
        + rank_value(chain["chain_rank"])
        - redundancy_penalty
        - trimmed_penalty
        - continuation_penalty
    )

def boundary_validation(chain):
    setup, middle, ending = split_window_text(chain.get("window_text", ""))
    setup_low = setup.lower()
    ending_low = ending.lower()
    text_low = str(chain.get("window_text", "")).lower()

    checks = []
    score = 0

    if setup and not any(setup_low.startswith(term) for term in OPENING_GLUE):
        score += 2
        checks.append("natural_start")
    else:
        checks.append("possible_mid_thought_opening")

    if len(setup) >= 80:
        score += 1
        checks.append("setup_context_present")
    else:
        checks.append("thin_setup_context")

    if not any(term in setup_low[:160] for term in ["?", "क्या", "लगता", "lagta"]):
        score += 1
        checks.append("not_teaser_only_opening")
    else:
        checks.append("possible_teaser_opening")

    landing_hits = [cue for cue in LANDING_CUES if cue.lower() in ending_low or cue.lower() in text_low[-500:]]
    if landing_hits:
        score += 2
        checks.append(f"payoff_landing_cues={landing_hits[:4]}")
    else:
        checks.append("weak_payoff_landing")

    if landing_hits and chain["repair_quality"] >= 4:
        score += 1
        checks.append("emotional_closure_possible")
    else:
        checks.append("emotional_closure_unproven")

    stripped_end = ending.strip()
    if stripped_end and not any(stripped_end.endswith(term.strip()) for term in ENDING_LEAKS):
        score += 1
        checks.append("no_obvious_abrupt_ending")
    else:
        checks.append("possible_abrupt_ending")

    if chain["continuation_risk"] == 0 and not chain["graph_trimmed"]:
        score += 2
        checks.append("low_continuation_leakage")
    elif chain["continuation_risk"] == 0:
        score += 1
        checks.append("low_risk_but_graph_trimmed")
    else:
        checks.append("continuation_leakage_risk")

    if 45.0 <= chain["merged_duration"] <= 75.0:
        score += 2
        checks.append("creator_short_pacing_complete")
    else:
        checks.append("pacing_incomplete_or_too_short")

    if score >= 10:
        label = "boundary_validated"
    elif score >= 7:
        label = "boundary_promising_needs_review"
    elif score >= 5:
        label = "boundary_weak"
    else:
        label = "boundary_reject_research"

    return {
        "score": score,
        "label": label,
        "checks": checks,
        "setup": setup[:220],
        "middle": middle[:220],
        "ending": ending[-220:],
    }

def export_readiness(chain, validation):
    checks = validation.get("checks", [])
    pacing_safe = chain["merged_duration"] <= 75.0
    strong_chain = chain["chain_rank"] in {"editorial_winner", "strong_editorial_candidate"}
    has_abrupt_risk = any("abrupt" in check for check in checks)
    has_continuation_risk = chain["continuation_risk"] > 0 or any("continuation_leakage_risk" in check for check in checks)
    weak_boundary = validation["label"] in {"boundary_weak", "boundary_reject_research"}

    if (
        validation["label"] == "boundary_validated"
        and chain["continuation_risk"] == 0
        and pacing_safe
        and strong_chain
    ):
        return "export_ready_candidate", "validated boundary, low continuation risk, creator-short pacing, strong canonical chain"

    if (
        validation["label"] == "boundary_promising_needs_review"
        and chain["continuation_risk"] == 0
        and pacing_safe
        and not has_abrupt_risk
    ):
        return "manual_review_candidate", "promising boundary with low continuation risk and safe pacing, but emotional/payoff closure is not fully proven"

    reasons = []
    if has_abrupt_risk:
        reasons.append("abrupt ending risk")
    if has_continuation_risk:
        reasons.append("continuation leakage risk")
    if weak_boundary:
        reasons.append("weak boundary validation")
    if not pacing_safe:
        reasons.append("pacing unsafe")
    if not strong_chain:
        reasons.append("chain rank not strong enough")
    if not reasons:
        reasons.append("readiness criteria not met")

    return "reject_for_now", ", ".join(reasons)

def cluster_chains(chains):
    families = []
    for chain in sorted(chains, key=lambda c: (c["repair_start"], c["repair_end"])):
        matched = None
        for family in families:
            if can_join_family(chain, family):
                matched = family
                break
        if matched is None:
            families.append([chain])
        else:
            matched.append(chain)
    return families

def family_overlap(chain, family):
    others = [member for member in family if member is not chain]
    if not others:
        return 0.0
    return max(time_overlap_ratio(chain, other) for other in others)

def append_chain_consolidation(lines, job_id, chains):
    lines.append("### V46.6 Chain Consolidation Planner")
    if not chains:
        lines.append("- chain_candidates: 0")
        lines.append("- canonical_editorial_path: none")
        lines.append("")
        return

    families = cluster_chains(chains)
    canonicals = []

    lines.append(f"- chain_candidates: {len(chains)}")
    lines.append(f"- narrative_families: {len(families)}")
    lines.append("- consolidation_basis: repair-window overlap, near-neighbor structural continuity, creator-short pacing, low continuation risk")
    lines.append("- v46_7_boundary_validation_basis: natural start, teaser opening risk, payoff landing, emotional closure, abrupt ending risk, continuation leakage, pacing completeness")
    lines.append("")

    for family_index, family in enumerate(families, start=1):
        scored = []
        for chain in family:
            max_overlap = family_overlap(chain, family)
            scored.append((consolidation_score(chain, max_overlap), max_overlap, chain))

        scored.sort(
            key=lambda item: (
                item[0],
                item[2]["chain_score"],
                item[2]["repair_quality"],
                item[2]["structural_score"],
                -item[2]["continuation_risk"],
                -int(item[2]["graph_trimmed"]),
            ),
            reverse=True,
        )
        canonical_score, max_overlap, canonical = scored[0]
        validation = boundary_validation(canonical)
        canonical["boundary_validation"] = validation
        canonicals.append((canonical_score, family_index, canonical))

        family_start = min(member["repair_start"] for member in family)
        family_end = max(member["repair_end"] for member in family)
        member_ids = ", ".join(str(member["candidate_index"]) for member in family)

        lines.append(f"#### Family {family_index}")
        lines.append(f"- members: {member_ids}")
        lines.append(f"- family_window: {round(family_start, 2)}->{round(family_end, 2)}")
        lines.append(f"- chain_count: {len(family)}")
        lines.append(f"- canonical_candidate: {canonical['candidate_index']}")
        lines.append(f"- canonical_window: {canonical['repair_start']}->{canonical['repair_end']}")
        lines.append(f"- canonical_score: {canonical_score}")
        lines.append(f"- canonical_rank: {canonical['chain_rank']}")
        lines.append(f"- canonical_reason: highest structure-first score after redundancy, pacing, graph-trim, and continuation-risk penalties")
        lines.append(f"- boundary_validation: {validation['label']} ({validation['score']}/12)")
        lines.append(f"- boundary_checks: {', '.join(validation['checks'])}")
        lines.append(f"- boundary_setup: {validation['setup']}")
        lines.append(f"- boundary_middle: {validation['middle']}")
        lines.append(f"- boundary_ending: {validation['ending']}")
        if len(scored) > 1:
            alternatives = [
                f"{item[2]['candidate_index']}({item[0]}, overlap={round(item[1], 2)})"
                for item in scored[1:]
            ]
            lines.append(f"- redundant_alternatives: {', '.join(alternatives)}")
        else:
            lines.append("- redundant_alternatives: none")
        lines.append("")

    canonicals.sort(
        key=lambda item: (
            item[0],
            item[2]["chain_score"],
            item[2]["repair_quality"],
            item[2]["structural_score"],
            -item[2]["continuation_risk"],
        ),
        reverse=True,
    )
    final_score, family_index, final_chain = canonicals[0]
    final_validation = final_chain.get("boundary_validation") or boundary_validation(final_chain)
    readiness, readiness_reason = export_readiness(final_chain, final_validation)
    lines.append("#### V46.7 Simulated Human-Editor Final Selection")
    lines.append(f"- job_id: {job_id}")
    lines.append(f"- canonical_editorial_path: candidate {final_chain['candidate_index']}")
    lines.append(f"- selected_family: {family_index}")
    lines.append(f"- selected_window: {final_chain['repair_start']}->{final_chain['repair_end']}")
    lines.append(f"- final_consolidation_score: {final_score}")
    lines.append(f"- original_chain_score: {final_chain['chain_score']}")
    lines.append(f"- continuation_risk: {final_chain['continuation_risk']}")
    lines.append(f"- graph_trimmed: {final_chain['graph_trimmed']}")
    lines.append(f"- pacing_check: {'creator_short_safe' if final_chain['merged_duration'] <= 75.0 else 'too_long'}")
    lines.append(f"- boundary_validation: {final_validation['label']} ({final_validation['score']}/12)")
    lines.append(f"- boundary_checks: {', '.join(final_validation['checks'])}")
    lines.append("#### V46.8 Canonical Clip Export Readiness")
    lines.append(f"- export_readiness: {readiness}")
    lines.append(f"- export_readiness_reason: {readiness_reason}")
    lines.append(f"- selected_window: {final_chain['repair_start']}->{final_chain['repair_end']}")
    lines.append(f"- canonical_candidate: {final_chain['candidate_index']}")
    lines.append(f"- boundary_validation_score: {final_validation['score']}/12")
    lines.append(f"- continuation_risk: {final_chain['continuation_risk']}")
    lines.append(f"- pacing_check: {'creator_short_safe' if final_chain['merged_duration'] <= 75.0 else 'too_long'}")
    lines.append("- selection_note: one canonical path is selected from overlapping narrative families; redundant winners remain research alternatives, not separate recommendations")
    lines.append("")

rows = load_rows()
by_job = {}
for r in rows:
    by_job.setdefault(r.get("job_id", "unknown"), []).append(r)

lines = ["# V46 Boundary Repair Analysis", ""]
lines.append("Scope: offline candidate-window inspection only. No production behavior changed.")
lines.append("")

for job_id, items in by_job.items():
    items = sorted(items, key=lambda r: float(r.get("expanded_start", r.get("start", 0)) or 0))
    lines.append(f"## Job: {job_id}")
    lines.append(f"- candidates: {len(items)}")
    lines.append("")
    chains = []
    for i, r in enumerate(items):
        txt = text_of(r)
        hints = has_hint(txt)
        payoff = r.get("payoff_bonus", 0)
        v43 = r.get("v43_hinglish_payoff_bonus", 0)
        v44 = r.get("v44_semantic_payoff_score", 0)
        weak_payoff_signal = (
            float(r.get("setup_strength", 0) or 0) >= 10
            and float(r.get("story_completeness_estimate", 0) or 0) >= 25
            and float(r.get("payoff_strength", 0) or 0) == 0
            and str(r.get("filter_decision", "")) in {"accepted", "accepted_pre_dedupe", "duplicate_removed"}
        )
        if (hints or weak_payoff_signal) and float(payoff or 0) == 0 and float(v43 or 0) == 0 and float(v44 or 0) == 0:
            prev_r = items[i-1] if i > 0 else None
            next_r = items[i+1] if i + 1 < len(items) else None
            start = r.get("expanded_start", r.get("start"))
            end = r.get("expanded_end", r.get("end"))
            repair_start = min(
                float(start or 0),
                float((prev_r or {}).get("expanded_start", (prev_r or {}).get("start", start)) or start or 0)
            )
            raw_repair_end = max(
                float(end or 0),
                float((next_r or {}).get("expanded_end", (next_r or {}).get("end", end)) or end or 0)
            )

            # V46 graph-layer constraint:
            # avoid runaway 90-150s merges in offline repair simulation.
            # Keep repair hypothesis creator-short compatible.
            max_repair_span = 75.0
            repair_end = min(raw_repair_end, repair_start + max_repair_span)
            graph_trimmed = raw_repair_end > repair_end
            lines.append(f"### Candidate {r.get('candidate_index')} potential boundary repair")
            lines.append(f"- original: {start}->{end}")
            lines.append(f"- proposed repair window: {repair_start}->{repair_end}")
            lines.append(f"- hints: {hints}")
            lines.append(f"- decision: {r.get('filter_decision')} / {r.get('filter_reason')}")
            lines.append(f"- current payoff/v43/v44: {payoff}/{v43}/{v44}")
            lines.append(f"- continuation_risk: {r.get('continuation_risk')}")


            merged_duration = round(repair_end - repair_start, 2)

            # V46 edge scoring layer
            overlap_score = 0
            continuity_score = 0
            duplicate_affinity = 0
            noise_penalty = 0

            prev_decision = str((prev_r or {}).get("filter_decision", ""))
            next_decision = str((next_r or {}).get("filter_decision", ""))

            if prev_r:
                overlap_score += 1

            if next_r:
                overlap_score += 1

            if "duplicate" in prev_decision:
                duplicate_affinity += 1

            if "duplicate" in next_decision:
                duplicate_affinity += 1

            txt_low = txt.lower()

            continuity_terms = [
                "time",
                "mehn",
                "wait",
                "struggle",
                "dream",
                "revenge",
                "future",
                "career",
                "phone",
                "result"
            ]

            continuity_score += sum(
                1 for t in continuity_terms if t in txt_low
            )

            if "???" in txt or "???" in txt:
                noise_penalty += 1

            structural_score = 0

            if float(r.get("setup_strength", 0) or 0) >= 10:
                structural_score += 1

            if float(r.get("story_completeness_estimate", 0) or 0) >= 25:
                structural_score += 1

            if float(r.get("continuation_risk", 0) or 0) == 0:
                structural_score += 1

            if float(r.get("context_quality", 0) or 0) >= 10:
                structural_score += 1

            if str(r.get("filter_decision", "")) in {"accepted", "accepted_pre_dedupe"}:
                structural_score += 1

            edge_score = (
                overlap_score
                + duplicate_affinity
                + min(continuity_score, 2)
                + structural_score
                - noise_penalty
            )

            if edge_score >= 5:
                edge_label = "strong_neighbor_chain"
            elif edge_score >= 3:
                edge_label = "possible_neighbor_chain"
            else:
                edge_label = "weak_neighbor_chain"

            repair_quality = 0

            if merged_duration >= 25:
                repair_quality += 1

            if merged_duration >= 45:
                repair_quality += 1

            if float(r.get("story_completeness_estimate", 0) or 0) >= 35:
                repair_quality += 1

            if float(r.get("setup_strength", 0) or 0) >= 10:
                repair_quality += 1

            if float(r.get("continuation_risk", 0) or 0) == 0:
                repair_quality += 1

            if repair_quality >= 4:
                repair_label = "strong_repair_candidate"
            elif repair_quality >= 2:
                repair_label = "possible_repair_candidate"
            else:
                repair_label = "weak_repair_candidate"

            lines.append(f"- merged_duration: {merged_duration}")
            lines.append(f"- edge_score: {edge_score}")
            lines.append(f"- edge_label: {edge_label}")
            lines.append(f"- overlap_score: {overlap_score}")
            lines.append(f"- duplicate_affinity: {duplicate_affinity}")
            lines.append(f"- continuity_score: {continuity_score}")
            lines.append(f"- structural_score: {structural_score}")
            lines.append(f"- noise_penalty: {noise_penalty}")
            lines.append(f"- graph_trimmed: {graph_trimmed}")
            lines.append(f"- max_repair_span: {max_repair_span}")
            lines.append(f"- repair_quality_score: {repair_quality}/5")
            lines.append(f"- repair_label: {repair_label}")

            chain_score = (
                edge_score
                + repair_quality
                + structural_score
            )

            if merged_duration > 75:
                chain_score -= 2

            if float(r.get("continuation_risk", 0) or 0) > 0:
                chain_score -= 2

            if graph_trimmed:
                chain_score -= 1

            if chain_score >= 14:
                chain_rank = "editorial_winner"
            elif chain_score >= 10:
                chain_rank = "strong_editorial_candidate"
            elif chain_score >= 7:
                chain_rank = "possible_editorial_candidate"
            else:
                chain_rank = "weak_editorial_candidate"

            lines.append(f"- chain_score: {chain_score}")
            lines.append(f"- chain_rank: {chain_rank}")
            lines.append(f"- simulated_editorial_hypothesis: merged narrative may restore setup->payoff continuity")
            lines.append(f"- preview: {txt[:900]}")
            lines.append("")
            chains.append({
                "candidate_index": r.get("candidate_index"),
                "decision": str(r.get("filter_decision", "")),
                "repair_start": round(repair_start, 2),
                "repair_end": round(repair_end, 2),
                "merged_duration": merged_duration,
                "edge_score": edge_score,
                "edge_label": edge_label,
                "duplicate_affinity": duplicate_affinity,
                "structural_score": structural_score,
                "repair_quality": repair_quality,
                "chain_score": chain_score,
                "chain_rank": chain_rank,
                "continuation_risk": fnum(r.get("continuation_risk", 0)),
                "graph_trimmed": graph_trimmed,
                "window_text": window_text(items, repair_start, repair_end),
            })

    append_chain_consolidation(lines, job_id, chains)

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"WROTE {OUT}")
print(f"jobs={len(by_job)} rows={len(rows)}")
