# V49 Master Gap Audit Report

Scope: offline-only audit using existing artifacts/logs. No video jobs, production patches, frontend, render/export, or subtitle changes.

## Executive Summary
- Pipeline execution is stable, but the current failure is still zero creator-safe finalists.
- The dominant root cause is a mismatch between global ASR fail-closed state and local/semantic candidate quality.
- V48.9 got one clean_semantics finalist into Creator QA, but Creator QA still rejected it via global asr_low_confidence plus editorial weakness.
- Ranking is now secondary: it improved degraded finalists from 6 to 5, but QA remains the hard stop.

## Job Summary
| Job | Funnel | Finalists | QA Rejects | Final Semantic Labels | QA Reasons |
|---|---:|---:|---:|---|---|
| f964425c-0803-4e3d-b6e7-98f8eb3e7d52 | 20 | 6 | 6 | {'degraded_semantics': 3, 'borderline_semantics': 2, 'clean_semantics': 1} | {'asr_low_confidence': 6, 'no_hook_no_payoff': 6, 'weak_standalone_context': 4} |
| e0fc755a-9319-4bab-ad50-fd6ffa723bcb | 20 | 6 | 6 | {'degraded_semantics': 4, 'borderline_semantics': 2} | {'asr_low_confidence': 6, 'no_hook_no_payoff': 6, 'weak_standalone_context': 4} |
| cb7f65ba-222e-4e82-869f-57d399a3f146 | 20 | 6 | 6 | {'unknown': 6} | {'asr_low_confidence': 6, 'no_hook_no_payoff': 6, 'weak_standalone_context': 5} |

## Top 10 Gaps
1. **P0 - Global ASR fail-closed gate rejects locally/semantically usable candidates**
   - Impact: Blocks all finalists even when a clean_semantics candidate reaches Creator QA.
   - Evidence: latest creator_qa rejects=6 and zero_safe=True; top QA reasons={'asr_low_confidence': 6, 'no_hook_no_payoff': 6, 'weak_standalone_context': 4}; latest final semantic labels={'degraded_semantics': 3, 'borderline_semantics': 2, 'clean_semantics': 1}
   - Recommendation: Make Creator QA ASR gate local/semantic-aware: keep fail-closed for degraded/unknown, but do not let global low_confidence_asr alone reject clean_semantics windows.
   - Risk: Medium: must not allow degraded transcripts through; requires strict metadata checks and fallback to current behavior when missing.
   - Files: pipeline_runner.py
2. **P0 - Native ASR artifact has severe global quality collapse**
   - Impact: The transcript contains replacement artifacts, repeated helper phrases, and entity corruption across runs.
   - Evidence: chunk replacement_char_count=49; unstable_chunks=8 of 14; latest transcript reasons=['replacement_chars=62', 'repeated_hindi_phrase=आप आप आप', 'repeated_hindi_phrase=आ�', 'ultra_short_repeated_segments=1', 'repeated_helper_phrases=29']
   - Recommendation: Do not rely on global transcript quality as a clip-level decision; preserve chunk/local scoring and local semantic confidence.
   - Risk: Low: diagnostic conclusion only; production change belongs in P0 local QA gate.
   - Files: pipeline_runner.py
3. **P1 - Semantic ASR degradation remains high in final selection**
   - Impact: Even after V48.9, degraded candidates still dominate finals.
   - Evidence: latest semantic audit final degraded=5; latest semantic audit clean structural degraded=2; latest final semantic labels={'degraded_semantics': 3, 'borderline_semantics': 2, 'clean_semantics': 1}
   - Recommendation: Strengthen semantic ranking only after P0: require at least one clean/borderline finalist when such candidates exist and score gap is bounded.
   - Risk: Medium: can over-promote low-payoff clean text if not paired with editorial thresholds.
   - Files: pipeline_runner.py
4. **P1 - Editorial extraction produces no payoff across all finalists**
   - Impact: All finalist clips repeatedly fail no_hook_no_payoff, so even clean ASR text is not creator-safe.
   - Evidence: latest zero_payoff_finalists=6 of 6; latest avg setup=8.33 avg payoff=0.0; QA no_hook_no_payoff count=6
   - Recommendation: Audit and patch Hindi payoff/setup expansion around clean windows; choose longer/neighboring context before ranking rather than relaxing QA.
   - Risk: Medium: larger windows can add rambling context or continuation leakage.
   - Files: pipeline_runner.py
5. **P1 - Dedupe and near-start removal can hide clean/borderline candidates**
   - Impact: Clean or borderline candidates exist but may not survive final dedupe/selection consistently.
   - Evidence: latest lost clean/borderline rows=2; clean window lost count from V48 report=3; lost filter reasons={'v10_v15_dna_gate': 2, 'passed_build_final_filters': 1}
   - Recommendation: After P0, add a dedupe tie-break that keeps cleaner semantic candidate when windows overlap and editorial scores are close.
   - Risk: Medium: overlap rules can reduce variety if too aggressive.
   - Files: pipeline_runner.py
6. **P1 - Repeated full reruns are avoidable**
   - Impact: Existing artifacts are sufficient to validate ranking/QA hypotheses offline before another upload.
   - Evidence: ASR segment artifacts, candidate funnel, clip intelligence, QA logs, and V48 reports exist for all target jobs.; V48.8/V48.9 impact was measurable from existing analytics.
   - Recommendation: Add offline replay harness for candidate ranking/Creator QA decisions using saved artifacts before any future long-video rerun.
   - Risk: Low: read-only replay reduces iteration cost.
   - Files: audit_reports/*.py
7. **P1 - Candidate windows are often too short or context-thin for standalone clips**
   - Impact: Finalists include 12-16s windows and weak_standalone_context remains a top rejection reason.
   - Evidence: latest duration min=12.0 avg=20.83 max=50.0; weak_standalone_context count=4
   - Recommendation: For clean/local-good windows, prefer expanded context that includes setup and payoff before final scoring.
   - Risk: Medium: longer clips may dilute hooks.
   - Files: pipeline_runner.py
8. **P2 - Retry path is not improving this Hindi/Hinglish mode**
   - Impact: Latest jobs still end in native_transcribe low confidence despite final artifacts being written.
   - Evidence: latest final ASR mode=native_transcribe; latest final ASR quality=0; specified checkpoint says faster-whisper retry fails safely and falls back
   - Recommendation: Keep retry fail-safe, but disable or shorten retry sampling for this mode if logs confirm repeated no-benefit; validate with offline ASR artifact comparison first.
   - Risk: Low to medium: affects runtime only if scoped to this failure mode; do not change ASR model policy yet.
   - Files: asr_engine.py
9. **P2 - Semantic corruption is mostly entity/technical term corruption**
   - Impact: Names and technical terms are malformed, which makes otherwise topical clips unusable.
   - Evidence: Repeated examples across audits include Netherlands/Modi/travel/semiconductor/energy corruptions.; latest semantic degraded candidates=17
   - Recommendation: Keep deterministic semantic ASR scoring and add a narrow entity-corruption diagnostic field; do not auto-correct text for export yet.
   - Risk: Low if diagnostic only; high if used for transcript rewriting.
   - Files: pipeline_runner.py, audit_reports/*.py
10. **P2 - Frontend zero-clip reporting appears fixed but needs guardrail audit**
   - Impact: The app now reports no creator-safe clips instead of pretending success.
   - Evidence: creator_qa_zero_safe rows are present for all three target jobs.; No export should occur for rejected-only jobs.
   - Recommendation: Keep current UX; add a regression audit that asserts zero-safe jobs expose no final exports.
   - Risk: Low.
   - Files: audit_reports/*.py

## P0/P1/P2 Action Plan
### P0
- Global ASR fail-closed gate rejects locally/semantically usable candidates
- Native ASR artifact has severe global quality collapse
### P1
- Semantic ASR degradation remains high in final selection
- Editorial extraction produces no payoff across all finalists
- Dedupe and near-start removal can hide clean/borderline candidates
- Repeated full reruns are avoidable
- Candidate windows are often too short or context-thin for standalone clips
### P2
- Retry path is not improving this Hindi/Hinglish mode
- Semantic corruption is mostly entity/technical term corruption
- Frontend zero-clip reporting appears fixed but needs guardrail audit
### Do Not Touch
- Do not weaken Creator QA acceptance thresholds.
- Do not export rejected clips.
- Do not change frontend/render/export/subtitle code for this problem.
- Do not change ASR model/retry policy until local semantic QA gate is validated.
- Do not run another long-video job before offline replay/audit predicts an improvement.

## Latest Job Details
- latest job: f964425c-0803-4e3d-b6e7-98f8eb3e7d52
- ASR final mode: native_transcribe
- ASR final quality: 0
- transcript quality reasons: ['replacement_chars=62', 'repeated_hindi_phrase=आप आप आप', 'repeated_hindi_phrase=आ�', 'ultra_short_repeated_segments=1', 'repeated_helper_phrases=29']
- final duration min/avg/max: 12.0 / 20.83 / 50.0
- avg setup/payoff: 8.33 / 0.0
- semantic preference applied count: 4

## Exact Next Codex Prompt
```text
FluxClip V49.1 local semantic ASR Creator-QA gate patch.

Environment:
- Local Windows only
- Path: C:\fluxclip_latest\fluxclip
- Minimal production patch only
- Compile after every changed Python file
- No frontend/render/export/subtitle changes
- Do NOT weaken Creator QA
- Do NOT export rejected clips
- Do NOT change ASR retry/model policy

Goal:
Replace the global ASR rejection inside Creator QA with a strict local semantic-aware ASR gate.

Patch:
- In pipeline_runner.py Creator QA rejection logic, keep current fail-closed behavior for degraded_semantics, unknown/missing semantic metadata, unstable local ASR, and severe artifact reasons.
- Allow global low_confidence_asr to stop being an automatic rejection only when the clip has semantic_asr_confidence_label in clean_semantics/borderline_semantics, local_asr_confidence_label clean/borderline, and semantic_asr_corruption_score below a conservative threshold.
- Add score_breakdown metadata explaining local_asr_gate_decision and reasons.
- Do not alter no_hook_no_payoff or weak_standalone_context checks.

Validation:
- python -m py_compile pipeline_runner.py
- Run offline audits first; only rerun the source if the audit predicts at least one finalist is no longer rejected solely by global ASR.
```
