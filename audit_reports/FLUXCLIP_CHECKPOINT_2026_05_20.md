# FluxClip Checkpoint - 2026-05-20

## 1. Latest Confirmed Architecture

- Production pipeline still flows through `run_pipeline` in `pipeline_runner.py`.
- ASR remains in `asr_engine.py`, with small native Whisper first and guarded faster-whisper medium retry.
- Creator QA remains fail-closed and still blocks clips with `no_hook_no_payoff`, `asr_low_confidence`, weak context, and incomplete endings.
- Offline editorial replay harness exists and is working:
  - `audit_reports/offline_editorial_replay.py`
  - replay reports under `audit_reports/OFFLINE_*`
- Semantic payoff fixture suite exists and is working:
  - `audit_reports/editorial_payoff_fixtures.json`
  - `audit_reports/test_payoff_semantics.py`
  - `audit_reports/PAYOFF_SEMANTIC_FIXTURE_REPORT.md`
- Candidate funnel diagnostics are installed:
  - `analytics/candidate_funnel.jsonl`
  - funnel report generated at `audit_reports/CANDIDATE_FUNNEL_REPORT_v44_final_e0926df0.md`

## 2. What Is Solved

- Creator QA correctly fails closed.
- Offline editorial replay is stable and detects regressions/false positives.
- V44 semantic payoff detector is implemented and fixture-proven.
- V44 was expanded for Hindi/Hinglish motivational landing language:
  - effort/hard work -> reward
  - मेहनत/struggle -> मिलेगा/success
  - revenge/badla -> success/result
  - preparation/skillset -> future payoff
  - "that day/us din/उस दिन" landing
- Payoff fixtures now pass:
  - 16 fixtures
  - 16 passed
  - false positives: 0
  - false negatives: 0
- ASR retry gate improvement worked once under clean conditions:
  - job `asr_borderline_gate_e0926df0`
  - native quality 52
  - borderline medium sample quality 50
  - full medium retry quality 100
  - selected `faster_whisper_medium_retry`
  - `low_confidence_asr=False`

## 3. What Is Still Blocked

- V44 has not been conclusively validated in a clean real pipeline run after the latest refinement.
- Final real validation attempt `v44_final_e0926df0` became ASR-masked again.
- Candidate selection still tends to surface clean setup/context without detected payoff.
- No approved clips yet from this source.
- Phase 2 payoff-aware candidate promotion has not been implemented and is not yet justified by safe evidence.

## 4. Exact Reason V44 Could Not Be Fully Validated

The latest final validation run did not use clean ASR.

Job: `v44_final_e0926df0`

- `asr_mode=native_transcribe`
- `asr_quality_score=52`
- `low_confidence_asr=True`
- ASR artifact reasons:
  - `replacement_chars=3`
  - `repeated_hindi_phrase=अपको अपको`
- kept segments: 29

Because Creator QA rejected all clips with `asr_low_confidence`, this run cannot judge whether the refined V44 detector would surface a valid payoff-bearing clip under clean ASR.

## 5. Current ASR Variance Problem

Same source video can produce different ASR paths:

- Clean path:
  - `candidate_funnel_e0926df0` / earlier clean run
  - `asr_mode=faster_whisper_medium_retry`
  - `asr_quality_score=100`
  - `low_confidence_asr=False`
- Masked path:
  - `v44_final_e0926df0`
  - `asr_mode=native_transcribe`
  - `asr_quality_score=52`
  - `low_confidence_asr=True`

Root issue remains retry/sample variance: medium retry does not always become the final selected ASR despite the guarded retry patch. When native ASR remains selected, editorial validation is invalid for V44.

## 6. Current Payoff / Candidate-Funnel Finding

Clean-ASR candidate-funnel run: `candidate_funnel_e0926df0`

- merged candidates: 10
- accepted candidates: 6
- duplicate removed: 3
- silent removed: 0
- all candidate payoff signals were 0 before V44 refinement:
  - `payoff_bonus=0`
  - `v43_hinglish_payoff_bonus=0`
  - `v44_semantic_payoff_score=0`
- all 6 pre-Creator-QA clips rejected:
  - `no_hook_no_payoff=6`
  - `weak_standalone_context=3`

After V44 refinement, offline replay stayed safe:

- historical rejects: 6
- replayed rejects: 6
- no payoff deltas
- no QA regressions
- no false-positive approvals

Meaning: V44 is safer and broader in fixtures, but existing saved candidate fixtures still do not cross payoff thresholds. A clean real run is needed before considering promotion.

## 7. Files Changed Recently

- `asr_engine.py`
  - Added conservative ASR borderline retry gate.
  - Added full-medium candidate selection guards.
  - Added ASR retry decision diagnostics.

- `pipeline_runner.py`
  - Added V44 semantic payoff intelligence.
  - Added V44 quality block.
  - Added Hindi/Hinglish motivational payoff refinements.
  - Added candidate funnel diagnostics.
  - Threaded `job_id` into `build_final_clips`.

- `audit_reports/offline_editorial_replay.py`
  - Added offline editorial replay/regression harness.

- `audit_reports/editorial_payoff_fixtures.json`
  - Expanded payoff fixture suite to 16 fixtures.

- `audit_reports/test_payoff_semantics.py`
  - Added deterministic payoff fixture runner/reporting.

- Generated reports/logs include:
  - `audit_reports/PAYOFF_SEMANTIC_FIXTURE_REPORT.md`
  - `audit_reports/OFFLINE_REPLAY_candidate_funnel_e0926df0.md`
  - `audit_reports/OFFLINE_REPLAY_v44_final_e0926df0.md`
  - `audit_reports/CANDIDATE_FUNNEL_REPORT_v44_final_e0926df0.md`
  - `audit_reports/EDITORIAL_VALIDATION_*`

## 8. Safe Next Task For Next Session

Do not start with another full validation run.

Safest next task:

Add an offline ASR retry decision replay/audit using existing ASR logs and transcript-quality rows, then make ASR retry selection more reproducible before further editorial validation.

Specific next step:

- Build or extend an offline ASR decision audit that compares:
  - native quality
  - medium sample quality
  - whether full medium ran
  - final selected ASR mode
  - quality reasons
  - kept segments
  - transcript preview
- Then consider a stricter diagnostic gate:
  - if native is low confidence and medium retry candidate has previously proven clean for the same source/audio hash, require a full-medium candidate before final native fallback.

Only after ASR selection is stable should a new real validation run be used to judge V44.

## 9. Exact Continuation Prompt For Next Chat

Continue FluxClip from `FLUXCLIP_CHECKPOINT_2026_05_20`.

Current state:
- Creator QA fails closed.
- Offline editorial replay is stable.
- Candidate funnel diagnostics are installed.
- V44 semantic payoff is fixture-proven with 16/16 passing, false positives=0, false negatives=0.
- V44 was refined for Hindi/Hinglish motivational payoff language.
- Latest final real validation `v44_final_e0926df0` was ASR-masked:
  - `asr_mode=native_transcribe`
  - `asr_quality_score=52`
  - `low_confidence_asr=True`
  - `replacement_chars=3`
  - `repeated_hindi_phrase=अपको अपको`
- Clean ASR is achievable but inconsistent:
  - prior clean run selected `faster_whisper_medium_retry`
  - quality reached 100
  - low confidence false
- Do not judge V44 from ASR-masked runs.

Next task:
Work offline first on ASR retry decision stability. Do not run video validation, ASR, FFmpeg, export, or server unless explicitly approved. Inspect existing ASR logs/reports and build or improve an offline ASR retry decision audit that explains why the same source alternates between clean `faster_whisper_medium_retry` and low-confidence `native_transcribe`. Recommend or implement the smallest fail-closed ASR-side diagnostic/gating improvement only after the offline audit supports it.
