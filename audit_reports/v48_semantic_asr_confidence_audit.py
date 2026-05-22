import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pipeline_runner
from v48_asr_chunk_stability_audit import (
    load_segments,
    safe_float,
    tokenize_for_asr_audit,
)
from v48_candidate_asr_confidence_audit import (
    find_latest_asr_artifact,
    infer_job_id,
    read_jsonl,
)


DEFAULT_CHUNK_REPORT = Path("audit_reports/v48_asr_chunk_stability.json")
DEFAULT_CANDIDATE_FUNNEL = Path("analytics/candidate_funnel.jsonl")
DEFAULT_CLIP_INTELLIGENCE = Path("analytics/clip_intelligence.jsonl")
DEFAULT_CREATOR_QA = Path("analytics/creator_qa.jsonl")
DEFAULT_MD_OUT = Path("audit_reports/V48_SEMANTIC_ASR_CONFIDENCE_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v48_semantic_asr_confidence.json")

EDITORIAL_REASONS = {
    "no_hook_no_payoff",
    "weak_standalone_context",
    "missing_setup",
    "weak_start",
    "weak_ending",
    "continuation_leakage",
}

KNOWN_MALFORMED_TOKEN_PATTERNS = [
    r"तेंकलोडी",
    r"तेकनोलोजी",
    r"टेकनलोगी",
    r"टेकनलोडी",
    r"सम्यकन्ड़्टर",
    r"सेमिकंटर्टर",
    r"सेमिकंटर",
    r"सेमिकंटक्टर",
    r"सेम्मिकन्टर",
    r"एरर्जी",
    r"नेदल्ट्झो",
    r"नेदल्लेंच",
    r"नेदलन्ज",
    r"नेदर\s+लेंज",
    r"पाँज",
    r"देषों",
    r"याप्रा?",
    r"प्रदान\s+मंतरी",
    r"प्रदन\s+मंट्री",
    r"मुदी",
    r"हीट्रोजन",
    r"यूरेनिम",
    r"सावदखोर्या",
    r"सावट्कोरीया",
    r"अस्ट्री\s+आनाम",
]

BROKEN_NAMED_ENTITY_PATTERNS = [
    r"नेदल्ट्झो",
    r"नेदल्लेंच",
    r"नेदलन्ज",
    r"नेदर\s+लेंज",
    r"प्रदान\s+मंतरी",
    r"प्रदन\s+मंट्री",
    r"मुदी",
    r"पाँज\s+देषों",
    r"सावदखोर्या",
    r"सावट्कोरीया",
    r"अस्ट्री\s+आनाम",
]

TECHNICAL_TERM_CORRUPTION_PATTERNS = [
    r"तेंकलोडी",
    r"तेकनोलोजी",
    r"टेकनलोगी",
    r"टेकनलोडी",
    r"सम्यकन्ड़्टर",
    r"सेमिकंटर्टर",
    r"सेमिकंटर",
    r"सेमिकंटक्टर",
    r"सेम्मिकन्टर",
    r"एरर्जी",
    r"हीट्रोजन",
    r"यूरेनिम",
    r"सपलाई",
]

PHONETIC_SUSPICION_PATTERNS = [
    r"दाएक्स",
    r"खेनाल",
    r"ताएप",
    r"कवार",
    r"अफान",
    r"तोख्डा",
    r"सैंद",
    r"अस्तमाल",
    r"सुक्ष",
    r"गलिश्टर",
    r"पिगलिवोई",
    r"वनाता",
    r"चिपस",
    r"धबाटमें",
    r"कुन्फ़लिक्त|कुन्फलिक्त",
    r"स्टर्टिजी",
    r"लोगा",
    r"निवेंग़ा",
]


def normalize_text(text):
    text = str(text or "")
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def selected_window(row):
    expanded_start = row.get("expanded_start")
    expanded_end = row.get("expanded_end")
    if expanded_start is not None and expanded_end is not None:
        start = safe_float(expanded_start)
        end = safe_float(expanded_end)
        if end > start:
            return round(start, 2), round(end, 2), "expanded"
    start = safe_float(row.get("start"))
    end = safe_float(row.get("end"))
    return round(start, 2), round(end, 2), "source"


def candidate_preview(row):
    return normalize_text(
        row.get("expanded_preview")
        or row.get("source_preview")
        or row.get("text_preview")
        or row.get("preview")
        or ""
    )


def clip_preview(row):
    return normalize_text(row.get("expanded_preview") or row.get("source_preview") or row.get("preview") or "")


def count_pattern_matches(text, patterns):
    matches = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            matches.append(match.group(0))
    return len(matches), sorted(set(matches))


def count_replacement_chars(text):
    return text.count("\ufffd") + text.count("ï¿½")


def count_malformed_tokens(tokens, known_matches):
    malformed = 0
    for token in tokens:
        if token in known_matches:
            malformed += 1
            continue
        if re.search(r"([\u0900-\u097F])\1{3,}", token):
            malformed += 1
            continue
        if len(token) >= 14 and re.search(r"[\u0900-\u097F]", token):
            malformed += 1
            continue
        if re.search(r"्[ािीुूेैोौंःँ]", token):
            malformed += 1
    return malformed


def repeated_garbage_phrase_count(tokens):
    if not tokens:
        return 0, []

    repeated = []
    idx = 0
    while idx < len(tokens):
        run_end = idx + 1
        while run_end < len(tokens) and tokens[run_end] == tokens[idx]:
            run_end += 1
        run_len = run_end - idx
        if run_len >= 4:
            repeated.append(" ".join(tokens[idx:run_end]))
        idx = run_end

    for ngram_size in (2, 3):
        counts = {}
        for pos in range(0, max(0, len(tokens) - ngram_size + 1)):
            gram = tuple(tokens[pos:pos + ngram_size])
            counts[gram] = counts.get(gram, 0) + 1
        for gram, count in counts.items():
            if count >= 4:
                repeated.append(" ".join(gram))

    unique_repeated = sorted(set(repeated))
    return len(unique_repeated), unique_repeated[:8]


def score_semantic_corruption(text):
    text = normalize_text(text)
    tokens = tokenize_for_asr_audit(text)

    suspicious_count, suspicious_matches = count_pattern_matches(
        text, KNOWN_MALFORMED_TOKEN_PATTERNS + PHONETIC_SUSPICION_PATTERNS
    )
    broken_named_entity_count, broken_named_entity_matches = count_pattern_matches(
        text, BROKEN_NAMED_ENTITY_PATTERNS
    )
    technical_term_corruption_count, technical_term_matches = count_pattern_matches(
        text, TECHNICAL_TERM_CORRUPTION_PATTERNS
    )
    repeated_count, repeated_examples = repeated_garbage_phrase_count(tokens)
    replacement_chars = count_replacement_chars(text)
    malformed_token_count = count_malformed_tokens(tokens, set(suspicious_matches))

    unique_ratio = len(set(tokens)) / max(len(tokens), 1) if tokens else 1.0
    score = 0
    score += min(36, replacement_chars * 10)
    score += min(40, suspicious_count * 8)
    score += min(30, malformed_token_count * 5)
    score += min(30, broken_named_entity_count * 10)
    score += min(30, technical_term_corruption_count * 10)
    score += min(36, repeated_count * 12)
    if len(tokens) >= 16 and unique_ratio < 0.38:
        score += int((0.38 - unique_ratio) * 100)
    score = min(100, score)

    if (
        score >= 42
        or repeated_count >= 2
        or replacement_chars > 0
        or broken_named_entity_count >= 2
        or technical_term_corruption_count >= 2
    ):
        label = "degraded_semantics"
    elif score >= 20 or suspicious_count > 0 or broken_named_entity_count > 0 or technical_term_corruption_count > 0:
        label = "borderline_semantics"
    else:
        label = "clean_semantics"

    reasons = []
    if replacement_chars:
        reasons.append(f"replacement_chars={replacement_chars}")
    if suspicious_count:
        reasons.append(f"suspicious_phonetic_tokens={suspicious_count}")
    if malformed_token_count:
        reasons.append(f"malformed_hindi_tokens={malformed_token_count}")
    if repeated_count:
        reasons.append(f"repeated_garbage_phrases={repeated_count}")
    if broken_named_entity_count:
        reasons.append(f"broken_named_entities={broken_named_entity_count}")
    if technical_term_corruption_count:
        reasons.append(f"technical_term_corruptions={technical_term_corruption_count}")
    if len(tokens) >= 16 and unique_ratio < 0.38:
        reasons.append(f"low_unique_token_ratio={round(unique_ratio, 3)}")

    return {
        "semantic_corruption_score": score,
        "semantic_confidence_label": label,
        "malformed_hindi_token_count": malformed_token_count,
        "suspicious_phonetic_token_count": suspicious_count,
        "repeated_garbage_phrase_count": repeated_count,
        "broken_named_entity_count": broken_named_entity_count,
        "technical_term_corruption_count": technical_term_corruption_count,
        "replacement_char_count": replacement_chars,
        "semantic_reasons": reasons,
        "suspicious_examples": suspicious_matches[:12],
        "broken_named_entity_examples": broken_named_entity_matches[:8],
        "technical_term_examples": technical_term_matches[:8],
        "repeated_garbage_examples": repeated_examples,
    }


def chunk_intersections(start, end, chunks):
    labels = []
    details = []
    for chunk in chunks:
        c_start = safe_float(chunk.get("start"))
        c_end = safe_float(chunk.get("end"))
        overlap_start = max(start, c_start)
        overlap_end = min(end, c_end)
        if overlap_end <= overlap_start:
            continue
        label = str(chunk.get("label") or "unknown")
        labels.append(label)
        details.append({
            "chunk_start": c_start,
            "chunk_end": c_end,
            "label": label,
            "collapse_score": chunk.get("collapse_score"),
            "overlap_seconds": round(overlap_end - overlap_start, 2),
        })
    return labels, details


def compute_structural_label(row, start, end, chunks):
    existing = row.get("local_asr_confidence_label")
    if not existing and isinstance(row.get("score_breakdown"), dict):
        existing = row["score_breakdown"].get("local_asr_confidence_label")
    labels, details = chunk_intersections(start, end, chunks)
    local_asr = pipeline_runner.v48_candidate_asr_stability(start, end, chunks)
    return {
        "structural_local_asr_label": local_asr["local_asr_confidence_label"],
        "pipeline_local_asr_confidence_label": str(existing) if existing else None,
        "structural_unstable_overlap_ratio": local_asr["unstable_window_overlap_ratio"],
        "structural_chunk_confidence_score": local_asr["chunk_confidence_score"],
        "structural_local_asr_reasons": local_asr["local_asr_reasons"],
        "structural_chunk_labels": sorted(set(labels)),
        "structural_overlapping_chunks": details,
    }


def load_funnel_rows(job_id, path):
    return [row for row in read_jsonl(path) if str(row.get("job_id")) == str(job_id)]


def load_final_rows(job_id, path):
    return [
        row for row in read_jsonl(path)
        if str(row.get("job_id")) == str(job_id) and row.get("stage") == "pre_creator_qa"
    ]


def load_creator_qa_rejections(job_id, path):
    return [
        row for row in read_jsonl(path)
        if str(row.get("job_id")) == str(job_id) and row.get("event") == "CREATOR_QA_REJECT"
    ]


def match_window(start, end, rows, tolerance=2.0):
    best = None
    best_delta = 999999.0
    for row in rows:
        delta = abs(start - safe_float(row.get("start"))) + abs(end - safe_float(row.get("end")))
        if delta < best_delta:
            best = row
            best_delta = delta
    return best if best is not None and best_delta <= tolerance else None


def infer_editorial_reasons(row):
    reasons = []
    if safe_float(row.get("payoff_bonus")) == 0 and safe_float(row.get("hook_bonus")) == 0:
        reasons.append("no_hook_no_payoff")
    if safe_float(row.get("context_quality")) < 8:
        reasons.append("weak_standalone_context")
    if safe_float(row.get("continuation_risk")) > 0:
        reasons.append("continuation_leakage")
    if row.get("story_editor_ok") is False:
        reasons.append("story_editor_not_ok")
    return reasons


def classify_rejection_driver(qa_reasons, metadata_reasons, semantic_label, structural_label, row):
    qa_set = set(qa_reasons or [])
    metadata_set = set(metadata_reasons or [])
    editorial_set = (qa_set | metadata_set) & EDITORIAL_REASONS
    degraded = semantic_label == "degraded_semantics"
    borderline = semantic_label == "borderline_semantics"
    structural_clean = structural_label == "clean"

    if degraded and "asr_low_confidence" in qa_set:
        return "asr_semantic_driven"
    if degraded and editorial_set:
        return "asr_semantic_driven" if structural_clean else "mixed_asr_semantic_and_editorial"
    if borderline and "asr_low_confidence" in qa_set and structural_clean:
        return "possible_asr_semantic_driven"
    if editorial_set and not degraded:
        return "editorial_driven"
    if row.get("filter_reason") in {"bad_transcript_clip"} or row.get("filter_decision") == "quality_rejected":
        return "asr_semantic_driven" if degraded else "structural_asr_driven"
    if degraded:
        return "asr_semantic_risk"
    return "not_rejected_or_unclear"


def annotate_candidates(funnel_rows, final_rows, rejections, chunks):
    annotated = []
    for row in funnel_rows:
        start, end, basis = selected_window(row)
        final_row = match_window(start, end, final_rows) if row.get("filter_decision") == "accepted" else None
        qa_row = match_window(start, end, rejections)
        preview = clip_preview(final_row) if final_row else candidate_preview(row)
        structural = compute_structural_label(row, start, end, chunks)
        semantic = score_semantic_corruption(preview)

        qa_reasons = []
        metadata_reasons = []
        if qa_row:
            qa_reasons = [str(reason) for reason in qa_row.get("reasons", [])]
            metadata_reasons = [str(reason) for reason in qa_row.get("metadata_reasons", [])]
        elif row.get("filter_decision") not in {"accepted", "accepted_pre_dedupe"}:
            qa_reasons = infer_editorial_reasons(row)

        rejection_driver = classify_rejection_driver(
            qa_reasons,
            metadata_reasons,
            semantic["semantic_confidence_label"],
            structural["structural_local_asr_label"],
            row,
        )
        clean_structural_degraded_semantics = (
            structural["structural_local_asr_label"] == "clean"
            and semantic["semantic_confidence_label"] == "degraded_semantics"
        )
        semantic_degradation_explains_no_hook = (
            clean_structural_degraded_semantics
            and "no_hook_no_payoff" in set(qa_reasons)
        )

        annotated.append({
            "candidate_index": row.get("candidate_index"),
            "start": start,
            "end": end,
            "window_basis": basis,
            "source_start": round(safe_float(row.get("start")), 2),
            "source_end": round(safe_float(row.get("end")), 2),
            "initial_score": row.get("initial_score"),
            "final_score": row.get("final_score") if row.get("final_score") is not None else (final_row or {}).get("score"),
            "filter_decision": row.get("filter_decision"),
            "filter_reason": row.get("filter_reason"),
            "final_pre_creator_qa_selected": final_row is not None,
            "creator_qa_reasons": qa_reasons,
            "creator_qa_metadata_reasons": metadata_reasons,
            "rejection_driver": rejection_driver,
            "clean_structural_window_with_degraded_semantics": clean_structural_degraded_semantics,
            "semantic_degradation_explains_no_hook_no_payoff": semantic_degradation_explains_no_hook,
            "preview_text": preview[:320],
            **structural,
            **semantic,
        })
    return annotated


def counts_by(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key, "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def summarize_production_stability_chunks(chunks, asr_artifact):
    clean = sum(1 for chunk in chunks if chunk.get("label") == "clean")
    borderline = sum(1 for chunk in chunks if chunk.get("label") == "borderline")
    unstable_chunks = [chunk for chunk in chunks if chunk.get("label") not in {"clean", "borderline"}]
    retry_windows = []
    for chunk in unstable_chunks:
        start = safe_float(chunk.get("start"))
        end = safe_float(chunk.get("end"))
        if retry_windows and start <= retry_windows[-1]["end"]:
            retry_windows[-1]["end"] = max(retry_windows[-1]["end"], end)
        else:
            retry_windows.append({"start": start, "end": end})

    return {
        "total_chunks": len(chunks),
        "clean_chunks": clean,
        "borderline_chunks": borderline,
        "unstable_chunks": len(chunks) - clean - borderline,
        "retry_recommended_windows": retry_windows,
        "preserved_clean_regions": [
            {"start": safe_float(chunk.get("start")), "end": safe_float(chunk.get("end"))}
            for chunk in chunks
            if chunk.get("label") == "clean"
        ],
        "risky_collapsed_regions": [
            {
                "start": safe_float(chunk.get("start")),
                "end": safe_float(chunk.get("end")),
                "label": chunk.get("label"),
                "collapse_score": chunk.get("collapse_score"),
            }
            for chunk in unstable_chunks
        ],
        "global_vs_chunk_mismatch_explanation": (
            "Semantic ASR audit uses production ASR stability helpers for local structural labels."
        ),
        "chunk_source": "recomputed",
        "chunk_source_artifact": str(asr_artifact),
        "stability_source": "production_helpers",
    }


def load_chunks(asr_artifact, chunk_report_path, chunk_size, overlap, job_id=None):
    _, segments = load_segments(asr_artifact)
    chunks = pipeline_runner.v48_build_asr_stability_chunks(segments)
    chunk_summary = summarize_production_stability_chunks(chunks, asr_artifact)
    if chunk_report_path:
        chunk_summary["ignored_chunk_report"] = str(chunk_report_path)
    return chunks, chunk_summary, segments


def build_recommendation(summary):
    if summary["clean_structural_degraded_semantics"] > 0:
        return (
            "Next production patch should target ASR semantic confidence first: add deterministic semantic "
            "corruption scoring to candidate selection/QA metadata, keep ASR fail-closed, and use it before "
            "ranking promotes structurally clean but semantically degraded windows."
        )
    if summary["semantically_degraded_candidates"] > summary["semantically_clean_candidates"]:
        return (
            "Next patch should target ASR model retry policy for semantically degraded regions, then candidate "
            "selection after retry evidence exists."
        )
    return "No production patch is justified from this semantic audit alone."


def summarize(job_id, asr_artifact, chunk_summary, rows, final_rows):
    final_selected = [row for row in rows if row["final_pre_creator_qa_selected"]]
    summary = {
        "job_id": job_id,
        "asr_artifact": str(asr_artifact),
        "chunk_source": chunk_summary.get("chunk_source", "unknown"),
        "chunk_source_artifact": chunk_summary.get("chunk_source_artifact"),
        "stability_source": chunk_summary.get("stability_source", "unknown"),
        "total_candidates": len(rows),
        "final_selected_candidates": len(final_rows),
        "structurally_clean_candidates": sum(1 for row in rows if row["structural_local_asr_label"] == "clean"),
        "structurally_borderline_candidates": sum(1 for row in rows if row["structural_local_asr_label"] == "borderline"),
        "structurally_unstable_candidates": sum(1 for row in rows if row["structural_local_asr_label"] == "unstable"),
        "semantically_clean_candidates": sum(1 for row in rows if row["semantic_confidence_label"] == "clean_semantics"),
        "semantically_borderline_candidates": sum(1 for row in rows if row["semantic_confidence_label"] == "borderline_semantics"),
        "semantically_degraded_candidates": sum(1 for row in rows if row["semantic_confidence_label"] == "degraded_semantics"),
        "final_semantically_degraded_candidates": sum(1 for row in final_selected if row["semantic_confidence_label"] == "degraded_semantics"),
        "clean_structural_degraded_semantics": sum(1 for row in rows if row["clean_structural_window_with_degraded_semantics"]),
        "final_clean_structural_degraded_semantics": sum(
            1 for row in final_selected if row["clean_structural_window_with_degraded_semantics"]
        ),
        "candidates_rejected_mainly_due_to_asr_semantic_degradation": sum(
            1 for row in rows if row["rejection_driver"] in {"asr_semantic_driven", "possible_asr_semantic_driven"}
        ),
        "candidates_rejected_mainly_due_to_real_editorial_weakness": sum(
            1 for row in rows if row["rejection_driver"] == "editorial_driven"
        ),
        "structurally_clean_no_hook_due_to_semantic_degradation": sum(
            1 for row in rows if row["semantic_degradation_explains_no_hook_no_payoff"]
        ),
        "semantic_label_counts": counts_by(rows, "semantic_confidence_label"),
        "structural_label_counts": counts_by(rows, "structural_local_asr_label"),
        "rejection_driver_counts": counts_by(rows, "rejection_driver"),
        "chunk_summary": chunk_summary,
    }
    summary["recommended_next_production_patch"] = build_recommendation(summary)
    return summary


def markdown_table_row(idx, row):
    preview = row["preview_text"].replace("|", "/")[:120]
    qa_reasons = ", ".join(row.get("creator_qa_reasons") or [])
    reasons = ", ".join(row.get("semantic_reasons") or [])
    return (
        f"| {idx} | {row['candidate_index']} | {row['start']} -> {row['end']} | "
        f"{row['structural_local_asr_label']} | {row['semantic_confidence_label']} | "
        f"{row['semantic_corruption_score']} | {row['final_pre_creator_qa_selected']} | "
        f"{row['rejection_driver']} | {qa_reasons or 'none'} | {reasons or 'none'} | {preview} |"
    )


def write_markdown_report(path, summary, rows):
    lines = [
        "# V48 Semantic ASR Confidence Report",
        "",
        "Scope: offline diagnostics only. No production ranking, ASR, Creator QA, frontend, render, export, or subtitle behavior changed.",
        "",
        "## Summary",
        f"- job_id: {summary['job_id']}",
        f"- asr_artifact: {summary['asr_artifact']}",
        f"- chunk_source: {summary['chunk_source']}",
        f"- chunk_source_artifact: {summary['chunk_source_artifact']}",
        f"- stability_source: {summary['stability_source']}",
        f"- total candidates: {summary['total_candidates']}",
        f"- final selected candidates: {summary['final_selected_candidates']}",
        f"- structurally clean candidates: {summary['structurally_clean_candidates']}",
        f"- semantically clean candidates: {summary['semantically_clean_candidates']}",
        f"- semantically borderline candidates: {summary['semantically_borderline_candidates']}",
        f"- semantically degraded candidates: {summary['semantically_degraded_candidates']}",
        f"- final semantically degraded candidates: {summary['final_semantically_degraded_candidates']}",
        f"- clean structural windows with degraded semantics: {summary['clean_structural_degraded_semantics']}",
        f"- final clean structural windows with degraded semantics: {summary['final_clean_structural_degraded_semantics']}",
        f"- candidates rejected mainly due to semantic ASR degradation: {summary['candidates_rejected_mainly_due_to_asr_semantic_degradation']}",
        f"- candidates rejected mainly due to real editorial weakness: {summary['candidates_rejected_mainly_due_to_real_editorial_weakness']}",
        f"- clean-structural no_hook_no_payoff likely semantic-degradation-driven: {summary['structurally_clean_no_hook_due_to_semantic_degradation']}",
        "",
        "## Distribution",
        f"- structural labels: {summary['structural_label_counts']}",
        f"- semantic labels: {summary['semantic_label_counts']}",
        f"- rejection drivers: {summary['rejection_driver_counts']}",
        "",
        "## Recommendation",
        summary["recommended_next_production_patch"],
        "",
        "## Candidate Table",
        "| # | Candidate | Window | Structural ASR | Semantic Label | Semantic Score | Final | Driver | Creator QA Reasons | Semantic Reasons | Preview |",
        "|---|---:|---:|---|---|---:|---|---|---|---|---|",
    ]
    for idx, row in enumerate(rows, 1):
        lines.append(markdown_table_row(idx, row))

    degraded_clean = [row for row in rows if row["clean_structural_window_with_degraded_semantics"]]
    lines.extend([
        "",
        "## Structurally Clean But Semantically Degraded",
    ])
    if not degraded_clean:
        lines.append("- none")
    else:
        for row in degraded_clean:
            examples = ", ".join(row.get("suspicious_examples") or row.get("technical_term_examples") or [])
            lines.append(
                f"- candidate {row['candidate_index']} {row['start']} -> {row['end']}: "
                f"score={row['semantic_corruption_score']}, final={row['final_pre_creator_qa_selected']}, "
                f"driver={row['rejection_driver']}, examples={examples or 'none'}"
            )

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json_report(path, summary, rows):
    payload = {
        "summary": summary,
        "candidates": rows,
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Offline V48 semantic ASR confidence audit")
    parser.add_argument("--asr-artifact", help="audit_reports/asr_segments_<job_id>_native_pre_retry.json")
    parser.add_argument("--job-id", help="Candidate analytics job id. Defaults to ASR artifact job_id.")
    parser.add_argument("--candidate-funnel", default=str(DEFAULT_CANDIDATE_FUNNEL))
    parser.add_argument("--clip-intelligence", default=str(DEFAULT_CLIP_INTELLIGENCE))
    parser.add_argument("--creator-qa", default=str(DEFAULT_CREATOR_QA))
    parser.add_argument("--chunk-report", default=str(DEFAULT_CHUNK_REPORT))
    parser.add_argument("--chunk-size", type=float, default=120.0)
    parser.add_argument("--overlap", type=float, default=10.0)
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()

    asr_artifact = Path(args.asr_artifact) if args.asr_artifact else find_latest_asr_artifact()
    if not asr_artifact:
        raise SystemExit("No native pre-retry ASR artifact found.")

    job_id = args.job_id or infer_job_id(asr_artifact)
    _, segments = load_segments(asr_artifact)
    scored_chunks, chunk_summary, recomputed_segments = load_chunks(
        asr_artifact,
        args.chunk_report,
        args.chunk_size,
        args.overlap,
        job_id,
    )
    if recomputed_segments is not None:
        segments = recomputed_segments

    funnel_rows = load_funnel_rows(job_id, args.candidate_funnel)
    final_rows = load_final_rows(job_id, args.clip_intelligence)
    rejections = load_creator_qa_rejections(job_id, args.creator_qa)
    rows = annotate_candidates(
        funnel_rows,
        final_rows,
        rejections,
        scored_chunks,
    )
    summary = summarize(job_id, asr_artifact, chunk_summary, rows, final_rows)

    md_path = Path(args.output_md)
    json_path = Path(args.output_json)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown_report(md_path, summary, rows)
    write_json_report(json_path, summary, rows)

    print(f"job_id={job_id}")
    print(f"asr_artifact={asr_artifact}")
    print(f"chunk_source={summary['chunk_source']}")
    print(f"chunk_source_artifact={summary['chunk_source_artifact']}")
    print(f"stability_source={summary['stability_source']}")
    print(f"segments={len(segments)} chunks={len(scored_chunks)} candidates={len(rows)}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")
    print(
        "summary "
        f"structurally_clean={summary['structurally_clean_candidates']} "
        f"semantic_clean={summary['semantically_clean_candidates']} "
        f"semantic_degraded={summary['semantically_degraded_candidates']} "
        f"asr_semantic_driven={summary['candidates_rejected_mainly_due_to_asr_semantic_degradation']} "
        f"editorial_driven={summary['candidates_rejected_mainly_due_to_real_editorial_weakness']}"
    )
    print(f"recommendation={summary['recommended_next_production_patch']}")


if __name__ == "__main__":
    main()
