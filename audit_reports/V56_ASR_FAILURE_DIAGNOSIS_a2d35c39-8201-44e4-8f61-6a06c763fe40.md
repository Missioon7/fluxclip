# V56 ASR Failure Diagnosis

- Job: `a2d35c39-8201-44e4-8f61-6a06c763fe40`
- Final ASR artifact: `audit_reports/asr_segments_a2d35c39-8201-44e4-8f61-6a06c763fe40.json`
- Native pre-retry artifact: `audit_reports/asr_segments_a2d35c39-8201-44e4-8f61-6a06c763fe40_native_pre_retry.json`
- Source video: `uploads/a2d35c39-8201-44e4-8f61-6a06c763fe40.mp4`
- ASR sample: `uploads/a2d35c39-8201-44e4-8f61-6a06c763fe40_asr_16k_asr_retry_sample_180s.wav`

## Artifact Summary

- Native pre-retry mode: `native_transcribe`
- Native pre-retry quality: `0`
- Native pre-retry low confidence: `true`
- Native pre-retry kept segments: `134`
- Final selected mode: `native_transcribe`
- Final selected quality: `0`
- Final low confidence: `true`
- Final kept segments: `134`
- Quality reasons: `replacement_chars=62`, `repeated_hindi_phrase=आप आप आप`, `repeated_hindi_phrase=आ�`, `ultra_short_repeated_segments=1`, `repeated_helper_phrases=29`

## Candidate/QA Summary

- Candidate funnel rows found: `20`
- Funnel decisions: `15 asr_segment_quarantined`, `2 accepted`, `2 dna_rejected`, `1 quality_rejected`
- Pre-Creator-QA clip rows found: `2`
- Completed exported clip rows found: `0`
- Creator QA rows found: `3`
- Creator QA result: both pre-QA candidates rejected for `asr_low_confidence`, `no_hook_no_payoff`, and `weak_standalone_context`; zero creator-safe clips.

## Why The Pipeline Continued

`pipeline_runner.run_pipeline()` wrote transcript quality and ASR segment artifacts, then only stopped when `segments` was empty. It did not fail closed on `asr_quality_score=0`, `low_confidence_asr=true`, replacement characters, or repeated Hindi garbage. Because 134 cleaned segments existed, execution continued into captions, viral analysis, and clip generation before Creator QA rejected the selected clips.

## Block Decision

Final clips should be blocked. The transcript has global hard ASR failure signals and cannot support creator-safe, context-complete shorts. The correct production behavior is to write ASR diagnostics and complete the job with no clips using the user-facing message: `Source audio/transcription quality too low for creator-safe clips. Try clearer audio or English/clean Hinglish source.`
