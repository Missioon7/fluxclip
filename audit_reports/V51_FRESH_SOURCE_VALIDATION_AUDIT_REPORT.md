# V51 Fresh Source Validation Audit Report

Scope: one fresh validation run on a cleaner source than the V50.x audit sample, with no production logic change before the run.

## Current Run
- job_id: v51_fresh_source_23f21012
- asr_mode: native_transcribe
- asr_quality_score: 62
- low_confidence_asr: True
- asr_quality_reasons: ['replacement_chars=2', 'repeated_hindi_phrase=अपको अपको']
- candidates_found: 11
- candidates_quarantined: 6
- repaired_window_needed: 6
- pre_creator_qa_candidates: 2
- creator_safe_count: 0
- final_clips_count: 0
- salvage_allowed_clean: 1
- salvage_allowed_borderline: 2
- salvage_quarantined_unstable: 6

## Rejection Reasons
- [('no_hook_no_payoff', 2), ('weak_standalone_context', 2)]

## Same-Source Baseline
- baseline_job_id: 23f21012-b025-4521-93c0-e13d15271343
- asr_mode: faster_whisper_medium_retry
- asr_quality_score: 70
- low_confidence_asr: False
- baseline_pre_creator_qa_candidates: 5
- baseline_creator_safe_count: 0
- baseline_final_clips_count: 0
- baseline_rejection_reasons: [('no_hook_no_payoff', 5), ('weak_standalone_context', 1)]

## Assessment
- v49_7_to_v50_3_assessment: helped_not_overblocked

## Next Patch
- recommendation: target_payoff_candidate_generation_on_clean_or_borderline_windows
- reason: ASR quarantine removed unstable junk, but surviving clean/borderline candidates still fail on no_hook_no_payoff
