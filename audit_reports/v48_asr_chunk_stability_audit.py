import argparse
import json
import re
from pathlib import Path


DEFAULT_INPUT_CANDIDATES = [
    Path("audit_reports/ASR_BORDERLINE_VALIDATION_RESULT_asr_borderline_gate_e0926df0.json"),
    Path("audit_reports/CANDIDATE_FUNNEL_VALIDATION_RESULT_candidate_funnel_e0926df0.json"),
    Path("analytics/transcript_quality.jsonl"),
]
DEFAULT_MD_OUT = Path("audit_reports/V48_ASR_CHUNK_STABILITY_REPORT.md")
DEFAULT_JSON_OUT = Path("audit_reports/v48_asr_chunk_stability.json")

COMMON_HINDI_FILLERS = {
    "तो",
    "कि",
    "आप",
    "मैं",
    "है",
    "हैं",
    "और",
    "मतलब",
    "देखो",
    "वो",
    "ये",
    "यह",
    "था",
    "थी",
    "के",
    "का",
    "की",
    "में",
    "से",
}
COMMON_ENGLISH_FILLERS = {
    "so",
    "that",
    "you",
    "i",
    "and",
    "is",
    "are",
    "the",
    "to",
    "in",
    "of",
    "like",
    "mean",
}


def unicode_diagnostics(text):
    text = str(text or "")
    return {
        "devanagari_count": len(re.findall(r"[\u0900-\u097F]", text)),
        "mojibake_marker_count": text.count("à¤") + text.count("à¥") + text.count("Ã"),
        "replacement_char_count": text.count("\ufffd") + text.count("ï¿½"),
    }


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_text_for_asr_audit(text):
    text = str(text or "")
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_for_asr_audit(text):
    text = normalize_text_for_asr_audit(text).lower()
    return re.findall(r"[\u0900-\u097Fa-z0-9]+", text)


def content_tokens(tokens):
    return [
        token for token in tokens
        if token not in COMMON_HINDI_FILLERS and token not in COMMON_ENGLISH_FILLERS
    ]


def ngram_repetition_ratio(tokens, n):
    if len(tokens) < n * 2:
        return 0.0
    grams = [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]
    if not grams:
        return 0.0
    counts = {}
    for gram in grams:
        counts[gram] = counts.get(gram, 0) + 1
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / max(len(grams), 1)


def adjacent_duplicate_segment_count(segments):
    count = 0
    previous = None
    for segment in segments:
        text = normalize_text_for_asr_audit(segment.get("text", "")).lower()
        if not text:
            continue
        if previous and text == previous:
            count += 1
        previous = text
    return count


def segment_midpoint(segment):
    start = safe_float(segment.get("start", 0))
    end = safe_float(segment.get("end", start))
    return start + max(0.0, end - start) / 2.0


def segment_end(segment):
    start = safe_float(segment.get("start", 0))
    return safe_float(segment.get("end", start), start)


def coerce_segment(obj):
    if not isinstance(obj, dict):
        return None
    if "text" not in obj:
        return None
    start = safe_float(obj.get("start", obj.get("start_time", obj.get("chunk_start", 0))))
    end = safe_float(obj.get("end", obj.get("end_time", obj.get("chunk_end", start))))
    text = normalize_text_for_asr_audit(obj.get("text", obj.get("transcript", "")))
    if not text:
        return None
    if end <= start:
        end = start + 0.01
    return {
        "start": round(start, 2),
        "end": round(end, 2),
        "text": text,
    }


def collect_segments_from_obj(obj):
    segments = []
    if isinstance(obj, list):
        for item in obj:
            direct = coerce_segment(item)
            if direct:
                segments.append(direct)
            else:
                segments.extend(collect_segments_from_obj(item))
    elif isinstance(obj, dict):
        direct = coerce_segment(obj)
        if direct:
            segments.append(direct)
        for key in ("segments", "cleaned_segments", "raw_segments", "asr_segments", "transcript_segments"):
            value = obj.get(key)
            if isinstance(value, list):
                segments.extend(collect_segments_from_obj(value))
        for key in ("result", "asr", "transcript", "data", "payload"):
            value = obj.get(key)
            if isinstance(value, (dict, list)):
                segments.extend(collect_segments_from_obj(value))
    return segments


def load_json_or_jsonl(path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
    return json.loads(raw)


def load_segments(path=None):
    selected_path = Path(path) if path else next((p for p in DEFAULT_INPUT_CANDIDATES if p.exists()), None)
    if not selected_path:
        return None, []
    obj = load_json_or_jsonl(selected_path)
    segments = collect_segments_from_obj(obj)
    deduped = []
    seen = set()
    for segment in sorted(segments, key=lambda s: (s["start"], s["end"], s["text"])):
        key = (segment["start"], segment["end"], segment["text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(segment)
    return selected_path, deduped


def build_asr_chunks(segments, chunk_size=120, overlap=10):
    if not segments:
        return []
    max_end = max(segment_end(segment) for segment in segments)
    step = max(1.0, float(chunk_size) - float(overlap))
    chunks = []
    start = 0.0
    while start <= max_end:
        end = start + float(chunk_size)
        chunk_segments = [
            segment for segment in segments
            if start <= segment_midpoint(segment) < end
        ]
        chunk_text = " ".join(segment["text"] for segment in chunk_segments)
        chunks.append({
            "chunk_start": round(start, 2),
            "chunk_end": round(end, 2),
            "segments": chunk_segments,
            "text": normalize_text_for_asr_audit(chunk_text),
        })
        start += step
    return chunks


def detect_repeated_token_collapse(chunk_text, chunk_segments):
    tokens = tokenize_for_asr_audit(chunk_text)
    meaningful = content_tokens(tokens)
    token_basis = meaningful if len(meaningful) >= 5 else tokens
    unique_ratio = len(set(tokens)) / max(len(tokens), 1) if tokens else 0.0
    top_token_ratio = 0.0
    top_content_token_ratio = 0.0

    if tokens:
        top_token_ratio = max(tokens.count(token) for token in set(tokens)) / len(tokens)
    if meaningful:
        top_content_token_ratio = max(meaningful.count(token) for token in set(meaningful)) / len(meaningful)

    repeated_bigram_ratio = ngram_repetition_ratio(token_basis, 2)
    repeated_trigram_ratio = ngram_repetition_ratio(token_basis, 3)
    adjacent_dupes = adjacent_duplicate_segment_count(chunk_segments)
    short_fragments = 0
    for segment in chunk_segments:
        if len(tokenize_for_asr_audit(segment.get("text", ""))) <= 3:
            short_fragments += 1
    short_fragment_ratio = short_fragments / max(len(chunk_segments), 1) if chunk_segments else 0.0
    unicode_diag = unicode_diagnostics(chunk_text)
    replacement_chars = unicode_diag["replacement_char_count"]

    collapse_score = 0
    if replacement_chars:
        collapse_score += min(35, replacement_chars * 8)
    if len(tokens) < 4 and chunk_segments:
        collapse_score += 25
    if unique_ratio and unique_ratio < 0.34:
        collapse_score += int((0.34 - unique_ratio) * 80)
    if top_content_token_ratio >= 0.32 and unique_ratio < 0.55:
        collapse_score += int(top_content_token_ratio * 45)
    elif top_token_ratio >= 0.45 and unique_ratio < 0.45:
        collapse_score += int(top_token_ratio * 25)
    if repeated_bigram_ratio >= 0.16:
        collapse_score += int(repeated_bigram_ratio * 65)
    if repeated_trigram_ratio >= 0.10:
        collapse_score += int(repeated_trigram_ratio * 85)
    if adjacent_dupes:
        collapse_score += min(30, adjacent_dupes * 10)
    if short_fragment_ratio >= 0.45 and len(chunk_segments) >= 3:
        collapse_score += int(short_fragment_ratio * 30)

    replacement_supported_by_instability = (
        unique_ratio < 0.45
        or repeated_bigram_ratio >= 0.16
        or repeated_trigram_ratio >= 0.10
        or adjacent_dupes > 0
    )

    if not chunk_segments:
        collapse_type = "empty_or_sparse_chunk"
    elif replacement_chars >= 3 or (replacement_chars > 0 and replacement_supported_by_instability):
        collapse_type = "replacement_artifact_collapse"
    elif short_fragment_ratio >= 0.65 and len(chunk_segments) >= 3:
        collapse_type = "short_fragment_collapse"
    elif collapse_score >= 35 and (
        repeated_bigram_ratio >= 0.16
        or repeated_trigram_ratio >= 0.10
        or adjacent_dupes > 0
        or top_content_token_ratio >= 0.32
    ):
        collapse_type = "local_repetition_collapse"
    else:
        collapse_type = "none"

    return {
        "word_count": len(tokens),
        "unique_token_ratio": round(unique_ratio, 3),
        "top_token_ratio": round(top_token_ratio, 3),
        "top_content_token_ratio": round(top_content_token_ratio, 3),
        "repeated_bigram_ratio": round(repeated_bigram_ratio, 3),
        "repeated_trigram_ratio": round(repeated_trigram_ratio, 3),
        "adjacent_duplicate_segment_count": adjacent_dupes,
        "short_fragment_ratio": round(short_fragment_ratio, 3),
        "replacement_chars": replacement_chars,
        **unicode_diag,
        "collapse_score": min(100, collapse_score),
        "collapse_type": collapse_type,
    }


def classify_chunk_stability(metrics):
    if metrics["segment_count"] == 0 or metrics["word_count"] < 4:
        return "empty_or_sparse_chunk", True
    if metrics["collapse_type"] == "replacement_artifact_collapse":
        return "replacement_artifact_collapse", True
    if metrics["collapse_type"] == "short_fragment_collapse":
        return "short_fragment_collapse", True
    if metrics["collapse_type"] == "local_repetition_collapse" and metrics["collapse_score"] >= 35:
        return "local_repetition_collapse", True
    if metrics["collapse_score"] >= 25:
        return "borderline", False
    return "clean", False


def score_asr_chunk(chunk):
    segments = chunk.get("segments", [])
    text = chunk.get("text", "")
    collapse = detect_repeated_token_collapse(text, segments)
    metrics = {
        "chunk_start": chunk["chunk_start"],
        "chunk_end": chunk["chunk_end"],
        "segment_count": len(segments),
        **collapse,
        "preview_text": text[:280],
    }
    stability_label, retry_recommended = classify_chunk_stability(metrics)
    metrics["stability_label"] = stability_label
    metrics["retry_recommended"] = retry_recommended
    return metrics


def merge_retry_windows(chunks):
    windows = []
    for chunk in chunks:
        if not chunk.get("retry_recommended"):
            continue
        start = chunk["chunk_start"]
        end = chunk["chunk_end"]
        if windows and start <= windows[-1]["end"]:
            windows[-1]["end"] = max(windows[-1]["end"], end)
        else:
            windows.append({"start": start, "end": end})
    return windows


def summarize_transcript_stability(chunks):
    total = len(chunks)
    clean = sum(1 for chunk in chunks if chunk["stability_label"] == "clean")
    borderline = sum(1 for chunk in chunks if chunk["stability_label"] == "borderline")
    unstable = total - clean - borderline
    retry_windows = merge_retry_windows(chunks)
    preserved = [
        {"start": chunk["chunk_start"], "end": chunk["chunk_end"]}
        for chunk in chunks
        if chunk["stability_label"] == "clean"
    ]
    risky = [
        {
            "start": chunk["chunk_start"],
            "end": chunk["chunk_end"],
            "label": chunk["stability_label"],
            "collapse_score": chunk["collapse_score"],
        }
        for chunk in chunks
        if chunk["stability_label"] not in {"clean", "borderline"}
    ]
    mismatch = (
        "Chunk audit can preserve clean regions while retrying only unstable windows."
        if clean and unstable
        else "No clean/unstable split detected in available artifact."
    )
    unicode_totals = {
        "devanagari_count": sum(int(chunk.get("devanagari_count", 0) or 0) for chunk in chunks),
        "mojibake_marker_count": sum(int(chunk.get("mojibake_marker_count", 0) or 0) for chunk in chunks),
        "replacement_char_count": sum(int(chunk.get("replacement_char_count", 0) or 0) for chunk in chunks),
    }
    return {
        "total_chunks": total,
        "clean_chunks": clean,
        "borderline_chunks": borderline,
        "unstable_chunks": unstable,
        **unicode_totals,
        "retry_recommended_windows": retry_windows,
        "preserved_clean_regions": preserved,
        "risky_collapsed_regions": risky,
        "global_vs_chunk_mismatch_explanation": mismatch,
    }


def write_markdown_report(summary, chunks, path, input_path=None):
    lines = [
        "# V48 ASR Chunk Stability Report",
        "",
        "Scope: offline longform Hindi/Hinglish ASR chunk stability audit only. No Whisper, FFmpeg, server, or production behavior changes.",
        f"Input artifact: {input_path or 'none'}",
        "",
        "## Summary",
        f"- total chunks: {summary['total_chunks']}",
        f"- clean chunks: {summary['clean_chunks']}",
        f"- borderline chunks: {summary['borderline_chunks']}",
        f"- unstable chunks: {summary['unstable_chunks']}",
        f"- devanagari count: {summary.get('devanagari_count', 0)}",
        f"- mojibake marker count: {summary.get('mojibake_marker_count', 0)}",
        f"- replacement char count: {summary.get('replacement_char_count', 0)}",
        f"- global vs chunk mismatch: {summary['global_vs_chunk_mismatch_explanation']}",
        "",
        "## Retry Recommended Windows",
    ]
    if summary["retry_recommended_windows"]:
        for window in summary["retry_recommended_windows"]:
            lines.append(f"- {window['start']} -> {window['end']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Preserved Clean Regions"])
    if summary["preserved_clean_regions"]:
        for window in summary["preserved_clean_regions"][:30]:
            lines.append(f"- {window['start']} -> {window['end']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Risky Collapsed Regions"])
    if summary["risky_collapsed_regions"]:
        for region in summary["risky_collapsed_regions"]:
            lines.append(
                f"- {region['start']} -> {region['end']} | "
                f"{region['label']} | collapse_score={region['collapse_score']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Chunk Detail"])
    for chunk in chunks:
        lines.extend([
            f"### {chunk['chunk_start']} -> {chunk['chunk_end']}",
            f"- stability_label: {chunk['stability_label']}",
            f"- retry_recommended: {chunk['retry_recommended']}",
            f"- segment_count: {chunk['segment_count']}",
            f"- word_count: {chunk['word_count']}",
            f"- unique_token_ratio: {chunk['unique_token_ratio']}",
            f"- top_token_ratio: {chunk['top_token_ratio']}",
            f"- repeated_bigram_ratio: {chunk['repeated_bigram_ratio']}",
            f"- repeated_trigram_ratio: {chunk['repeated_trigram_ratio']}",
            f"- adjacent_duplicate_segment_count: {chunk['adjacent_duplicate_segment_count']}",
            f"- short_fragment_ratio: {chunk['short_fragment_ratio']}",
            f"- devanagari_count: {chunk.get('devanagari_count', 0)}",
            f"- mojibake_marker_count: {chunk.get('mojibake_marker_count', 0)}",
            f"- replacement_char_count: {chunk.get('replacement_char_count', 0)}",
            f"- collapse_score: {chunk['collapse_score']}",
            f"- collapse_type: {chunk['collapse_type']}",
            f"- preview_text: {chunk['preview_text']}",
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_json_report(summary, chunks, path, input_path=None):
    payload = {
        "input_artifact": str(input_path) if input_path else None,
        "summary": summary,
        "chunks": chunks,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Offline V48 ASR chunk stability audit")
    parser.add_argument("--input", help="JSON or JSONL artifact containing ASR segment-like objects")
    parser.add_argument("--chunk-size", type=float, default=120.0)
    parser.add_argument("--overlap", type=float, default=10.0)
    parser.add_argument("--output-md", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_OUT))
    args = parser.parse_args()

    input_path, segments = load_segments(args.input)
    chunks = build_asr_chunks(segments, chunk_size=args.chunk_size, overlap=args.overlap)
    scored_chunks = [score_asr_chunk(chunk) for chunk in chunks]
    summary = summarize_transcript_stability(scored_chunks)

    md_path = Path(args.output_md)
    json_path = Path(args.output_json)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown_report(summary, scored_chunks, md_path, input_path=input_path)
    write_json_report(summary, scored_chunks, json_path, input_path=input_path)

    print(f"input_artifact={input_path}")
    print(f"segments={len(segments)} chunks={len(scored_chunks)}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")
    print(
        "summary "
        f"clean={summary['clean_chunks']} "
        f"borderline={summary['borderline_chunks']} "
        f"unstable={summary['unstable_chunks']}"
    )


if __name__ == "__main__":
    main()
