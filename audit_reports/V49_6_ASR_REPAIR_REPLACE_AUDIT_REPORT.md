# V49.6 ASR Repair/Replace Audit Report

Scope: offline-only audit using existing ASR artifacts/logs. No video rerun, production patch, Creator QA relaxation, ASR threshold relaxation, frontend, render, export, or subtitle changes.

## Summary
- jobs analyzed: 5
- total unstable chunks: 50
- repair-worthy unstable windows: 20
- quarantine windows: 30
- top recommended strategy: Segment-level salvage with unstable-window quarantine and targeted repair
- best next production patch: Segment-level salvage with unstable-window quarantine and targeted repair.
- risk level: Medium

## Canonical Inputs
- structural source of truth: `pipeline_runner.v48_build_asr_stability_chunks` and `pipeline_runner.v48_candidate_asr_stability`
- parity label mismatches: 0
- parity ratio mismatches: 0

## Primary Corrected Job
- job_id: 2efbe27a-4f64-41aa-9077-6f483e00fc4f
- chunks: 14
- chunk labels: {replacement_artifact_collapse: 9, local_repetition_collapse: 1, clean: 4}
- repair windows: 4
- quarantine windows: 6
- candidates/finalists: 20 / 6
- candidate semantic labels: {unknown: 3, degraded_semantics: 12, clean_semantics: 2, borderline_semantics: 3}
- final semantic labels: {degraded_semantics: 3, clean_semantics: 1, borderline_semantics: 2}

## Unstable Windows
| Window | Label | Collapse | Semantic | Candidates | Finalists | Action |
|---|---|---:|---|---:|---:|---|
| 0.0 -> 120.0 | replacement_artifact_collapse | 40 | degraded_semantics:100 | 5 | 0 | quarantine |
| 110.0 -> 230.0 | local_repetition_collapse | 39 | degraded_semantics:100 | 2 | 0 | quarantine |
| 220.0 -> 340.0 | replacement_artifact_collapse | 32 | degraded_semantics:100 | 2 | 1 | repair_first |
| 330.0 -> 450.0 | replacement_artifact_collapse | 37 | degraded_semantics:100 | 3 | 2 | repair_first |
| 550.0 -> 670.0 | replacement_artifact_collapse | 32 | degraded_semantics:100 | 3 | 1 | repair_first |
| 660.0 -> 780.0 | replacement_artifact_collapse | 58 | degraded_semantics:56 | 2 | 0 | repair_if_budget_allows |
| 770.0 -> 890.0 | replacement_artifact_collapse | 90 | degraded_semantics:95 | 1 | 0 | quarantine |
| 880.0 -> 1000.0 | replacement_artifact_collapse | 75 | degraded_semantics:82 | 0 | 0 | quarantine |
| 990.0 -> 1110.0 | replacement_artifact_collapse | 62 | degraded_semantics:100 | 0 | 0 | quarantine |
| 1320.0 -> 1440.0 | replacement_artifact_collapse | 39 | degraded_semantics:51 | 0 | 0 | quarantine |

## Candidate Overlap With Unstable Windows
| Window | Candidate | Final | Semantic | Local ASR | QA Reasons |
|---|---:|---|---|---|---|
| 0.0 -> 120.0 | 4 | False | degraded_semantics:34.0 | unstable:1.0 | none |
| 0.0 -> 120.0 | 5 | False | degraded_semantics:34.0 | unstable:1.0 | none |
| 0.0 -> 120.0 | 3 | False | degraded_semantics:44.0 | unstable:1.0 | none |
| 0.0 -> 120.0 | 6 | False | degraded_semantics:16.0 | unstable:1.0 | none |
| 0.0 -> 120.0 | 7 | False | degraded_semantics:16.0 | unstable:1.0 | none |
| 110.0 -> 230.0 | 8 | False | degraded_semantics:36.0 | unstable:1.0 | none |
| 110.0 -> 230.0 | 9 | False | degraded_semantics:16.0 | unstable:1.0 | none |
| 220.0 -> 340.0 | 10 | True | clean_semantics:0.0 | unstable:1.0 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context |
| 220.0 -> 340.0 | 11 | False | borderline_semantics:8.0 | unstable:1.0 | none |
| 330.0 -> 450.0 | 12 | True | borderline_semantics:8.0 | unstable:1.0 | asr_low_confidence, no_hook_no_payoff |
| 330.0 -> 450.0 | 13 | True | borderline_semantics:8.0 | unstable:1.0 | asr_low_confidence, no_hook_no_payoff |
| 330.0 -> 450.0 | 14 | False | clean_semantics:0.0 | unstable:1.0 | none |
| 550.0 -> 670.0 | 1 | True | degraded_semantics:18.0 | unstable:1.0 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context |
| 550.0 -> 670.0 | 17 | False | degraded_semantics:67.0 | unstable:1.0 | none |
| 550.0 -> 670.0 | 18 | False | degraded_semantics:67.0 | unstable:1.0 | none |
| 660.0 -> 780.0 | 17 | False | degraded_semantics:67.0 | unstable:1.0 | none |
| 660.0 -> 780.0 | 18 | False | degraded_semantics:67.0 | unstable:1.0 | none |
| 770.0 -> 890.0 | 19 | False | unknown:69 | unstable:1.0 | none |

## Windows Worth Repairing
| Window | Reason |
|---|---|
| 220.0 -> 340.0 | Unstable chunk overlaps final or clean/borderline semantic candidates; repair could change eligibility. |
| 330.0 -> 450.0 | Unstable chunk overlaps final or clean/borderline semantic candidates; repair could change eligibility. |
| 550.0 -> 670.0 | Unstable chunk overlaps final or clean/borderline semantic candidates; repair could change eligibility. |
| 660.0 -> 780.0 | Unstable chunk overlaps candidates, but no clean/borderline semantic signal survived. |

## Windows To Quarantine
| Window | Reason |
|---|---|
| 0.0 -> 120.0 | Severe structural or semantic corruption with no clean/borderline candidate evidence. |
| 110.0 -> 230.0 | Severe structural or semantic corruption with no clean/borderline candidate evidence. |
| 770.0 -> 890.0 | Severe structural or semantic corruption with no clean/borderline candidate evidence. |
| 880.0 -> 1000.0 | Severe structural or semantic corruption with no clean/borderline candidate evidence. |
| 990.0 -> 1110.0 | Severe structural or semantic corruption with no clean/borderline candidate evidence. |
| 1320.0 -> 1440.0 | No candidate eligibility evidence; exclude from ranking unless repaired. |

## Strategy Evaluation
| Rank | Strategy | Quality Impact | Runtime | Risk | Files | Offline First | Requires Rerun |
|---:|---|---|---|---|---|---|---|
| 1 | Segment-level salvage with unstable-window quarantine and targeted repair | Highest controlled impact: preserve stable segments, quarantine 30 severe windows, and repair/retry 20 candidate-relevant unstable windows before ranking. | Medium; bounded retry/repair plus cheap local stability metadata. | Medium; requires strict metadata and no threshold relaxation. | pipeline_runner.py, asr_engine.py | True | True |
| 2 | Target only unstable windows for repair/retry | High if targeted repair fixes the 20 repair-worthy unstable windows; 26 final candidates currently overlap unstable production chunks. | Medium; bounded to unstable chunk windows instead of whole-video retry. | Medium; repaired windows must remain fail-closed until parity and semantic checks pass. | asr_engine.py, pipeline_runner.py | True | True |
| 3 | Target only semantically degraded windows for normalization/repair | Medium; 36 candidate rows are semantically degraded, but semantic repair alone cannot make structurally unstable windows safe. | Low to medium for deterministic normalization; higher if retranscription is included. | Medium to high if normalized text replaces transcript text used for export. | pipeline_runner.py | True | False |
| 4 | Disable/skip faster-whisper retry for this known-failing Hindi mode | No direct transcript quality gain; only avoids no-benefit retry work when logs already predict fallback. | Lower for the known-failing mode. | Low to medium; runtime policy change can hide future retry improvements if over-broad. | asr_engine.py | True | True |
| 5 | Current fallback native small | None; preserves current low-confidence native transcript and known unstable windows. | Low current runtime after fallback completes. | Low, but leaves P0 quality failure untouched. | none | True | False |
| 6 | Replace corrupted candidate transcript text with safer cleaned/normalized text when possible | Potentially high for captions/QA text, but unsafe without audio-backed repair. | Low. | High; can fabricate clean-looking text and mask ASR failures. | pipeline_runner.py | True | False |

## Best Next Production Patch
Segment-level salvage with unstable-window quarantine and targeted repair is the best next patch. It preserves stable segments, prevents unstable windows from ranking unless repaired, and avoids both Creator QA relaxation and ASR threshold relaxation.

## Do Not Touch
- Do not relax Creator QA.
- Do not relax ASR stability thresholds.
- Do not change frontend/render/export/subtitle code.
- Do not switch blindly to a larger Whisper model as the first step.
- Do not replace export/caption text with normalized text unless audio-backed repair validates it.
- Do not allow unstable windows into candidate ranking unless repaired and revalidated.

## Exact Next Patch Prompt
```text
FluxClip V49.7 segment-level ASR salvage and unstable-window quarantine patch.

Environment:
- Local Windows only
- Path: C:\fluxclip_latest\fluxclip
- Minimal production patch only
- No frontend/render/export/subtitle changes
- Do not weaken Creator QA
- Do not relax ASR stability thresholds
- Compile every changed Python file

Context:
V49.6 offline audit found the best next strategy is segment-level salvage: preserve stable ASR segments, quarantine production-helper unstable windows, and target only candidate-relevant unstable windows for repair/retry.

Patch:
- In pipeline_runner.py, use pipeline_runner.v48_build_asr_stability_chunks output before candidate ranking.
- Prevent candidates whose selected/expanded window has production local_asr_confidence_label=unstable from ranking unless a repaired transcript segment set exists for that window.
- Preserve clean/borderline chunks and stable segments without global transcript rejection.
- Add score_breakdown metadata: segment_salvage_decision, quarantined_unstable_windows, repaired_window_required, repaired_window_available.
- In asr_engine.py only if needed, add a narrow hook for targeted unstable-window retry/repair; do not change global model policy.
- Keep Creator QA fail-closed and unchanged.

Validation:
- python -m py_compile pipeline_runner.py asr_engine.py
- Run V48/V49.6 offline audits before any video rerun.
- Proceed to a rerun only if offline replay predicts fewer unstable finalists without increasing degraded_semantics finalists.
```
