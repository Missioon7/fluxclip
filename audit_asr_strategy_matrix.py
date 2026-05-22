import argparse
import json
import time
from pathlib import Path

import torch

from asr_engine import (
    clean_asr_segments,
    clean_repeated_phrases,
    create_asr_retry_sample,
    extract_asr_wav,
    get_device,
    get_model,
    transcript_quality_score,
    transcribe_faster_whisper_retry_guarded,
)


def evaluate_whisper_native(audio_path, task, language, label):
    start = time.time()
    model = get_model("small")
    device = get_device()
    result = model.transcribe(
        audio_path,
        task=task,
        language=language,
        fp16=(device == "cuda"),
        verbose=False,
        word_timestamps=False,
        temperature=0,
        beam_size=1,
        best_of=1,
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
        logprob_threshold=-1.0,
        no_speech_threshold=0.55,
    )
    raw_segments = result.get("segments", [])
    cleaned_segments = clean_asr_segments(raw_segments, label=label)
    text = clean_repeated_phrases(result.get("text", ""))
    quality_score, reasons = transcript_quality_score(text, cleaned_segments)
    return {
        "strategy": label,
        "ok": True,
        "quality_score": quality_score,
        "quality_reasons": reasons,
        "raw_segments": len(raw_segments),
        "kept_segments": len(cleaned_segments),
        "preview": text[:700],
        "elapsed_seconds": round(time.time() - start, 2),
    }


def evaluate_faster_whisper(audio_path, device):
    start = time.time()
    raw_segments, text = transcribe_faster_whisper_retry_guarded(
        audio_path,
        device,
        "matrix_medium_sample",
        360,
    )
    cleaned_segments = clean_asr_segments(raw_segments, label="matrix_faster_whisper_medium")
    quality_score, reasons = transcript_quality_score(text, cleaned_segments)
    return {
        "strategy": "D_faster_whisper_medium_hi",
        "ok": True,
        "quality_score": quality_score,
        "quality_reasons": reasons,
        "raw_segments": len(raw_segments),
        "kept_segments": len(cleaned_segments),
        "preview": text[:700],
        "elapsed_seconds": round(time.time() - start, 2),
    }


def run_matrix(input_path, sample_seconds):
    source = str(Path(input_path).resolve())
    asr_audio = extract_asr_wav(source)
    sample_audio = create_asr_retry_sample(asr_audio, seconds=sample_seconds)
    device = get_device()
    results = []

    strategies = [
        ("A_whisper_small_native_transcribe_auto", "transcribe", None),
        ("B_whisper_small_translate_auto", "translate", None),
        ("C_whisper_small_forced_language_hi", "transcribe", "hi"),
    ]
    for label, task, language in strategies:
        try:
            results.append(evaluate_whisper_native(sample_audio, task, language, label))
        except Exception as e:
            results.append({"strategy": label, "ok": False, "error": str(e)})

    try:
        results.append(evaluate_faster_whisper(sample_audio, device))
    except Exception as e:
        results.append({"strategy": "D_faster_whisper_medium_hi", "ok": False, "error": str(e)})

    ok_scores = [r.get("quality_score", 0) for r in results if r.get("ok")]
    best_score = max(ok_scores or [0])
    return {
        "source": source,
        "asr_audio": asr_audio,
        "sample_audio": sample_audio,
        "sample_seconds": sample_seconds,
        "device": device,
        "cuda_available": bool(torch.cuda.is_available()),
        "results": results,
        "best_quality_score": best_score,
        "full_video_rerun_allowed": best_score > 50,
        "version": "v56_asr_strategy_matrix",
    }


def write_reports(report):
    out_dir = Path("audit_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "V56_ASR_STRATEGY_MATRIX_REPORT.json"
    md_path = out_dir / "V56_ASR_STRATEGY_MATRIX_REPORT.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# V56 ASR Strategy Matrix Report",
        "",
        f"- Source: `{report['source']}`",
        f"- Sample seconds: {report['sample_seconds']}",
        f"- Device: {report['device']}",
        f"- CUDA available: {report['cuda_available']}",
        f"- Best quality score: {report['best_quality_score']}",
        f"- Full video rerun allowed: {report['full_video_rerun_allowed']}",
        "",
        "| Strategy | OK | Quality | Elapsed | Raw/Kept | Reasons | Preview |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for row in report["results"]:
        preview = str(row.get("preview", row.get("error", ""))).replace("\n", " ")[:220]
        reasons = ", ".join(str(x) for x in row.get("quality_reasons", []))[:220]
        raw_kept = f"{row.get('raw_segments', 0)}/{row.get('kept_segments', 0)}"
        lines.append(
            f"| {row.get('strategy')} | {row.get('ok')} | {row.get('quality_score', '')} | "
            f"{row.get('elapsed_seconds', '')} | {raw_kept} | {reasons} | {preview} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="V56 research-only ASR strategy matrix.")
    parser.add_argument("input", help="Video or audio path to sample.")
    parser.add_argument("--sample-seconds", type=int, default=120)
    args = parser.parse_args()

    report = run_matrix(args.input, args.sample_seconds)
    json_path, md_path = write_reports(report)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Best quality score: {report['best_quality_score']}")
    if not report["full_video_rerun_allowed"]:
        print("No full video rerun: no strategy exceeded quality > 50.")


if __name__ == "__main__":
    main()
