# V49.9 Repaired Window Retry Audit Report

Scope: offline only. This audit extracts exact audio windows for the quarantined unstable finalists, retries ASR on those windows, and writes fail-closed repair artifacts. No full video rerun, no Creator QA relaxation, and no threshold relaxation were performed.

## Summary
- job_id: 2efbe27a-4f64-41aa-9077-6f483e00fc4f
- current quarantined finalists: 4
- audio-backed repairs completed: 2
- audio-backed repairs failed: 2
- repaired window available candidates: 2
- repair export safe candidates: 2
- would be creator-safe after ASR repair: 0
- predicted final clean from repaired windows: 2
- predicted final unstable from repaired windows: 2
- video rerun justified: True

## Quarantined Finalists
| Candidate | Window | Score | Original Local ASR | Original Semantic | Unstable Windows |
|---:|---|---:|---|---|---|
| 1 | 589.36 -> 639.36 | 181.0 | unstable:1.0 | degraded_semantics | 550.0 -> 670.0 (replacement_artifact_collapse) |
| 12 | 350.36 -> 372.2 | 160.0 | unstable:1.0 | borderline_semantics | 330.0 -> 450.0 (replacement_artifact_collapse) |
| 13 | 396.04 -> 412.36 | 154.0 | unstable:1.0 | borderline_semantics | 330.0 -> 450.0 (replacement_artifact_collapse) |
| 10 | 270.92 -> 283.76 | 144.0 | unstable:1.0 | clean_semantics | 220.0 -> 340.0 (replacement_artifact_collapse) |

## Audio-Backed Repair Results
| Candidate | Window | Repaired Local ASR | Quality | Semantic | Available | Export Safe | Creator-Safe After ASR |
|---:|---|---|---:|---|---|---|---|
| 12 | 350.36 -> 372.2 | clean:0.0 | 100 | clean_semantics:0 | True | True | False |
| 13 | 396.04 -> 412.36 | clean:0.0 | 100 | clean_semantics:0 | True | True | False |

## Repair Decisions
| Candidate | Availability Reason | Remaining Non-ASR QA Reasons | Artifact |
|---:|---|---|---|
| 12 | validated_audio_backed_repair_available | no_hook_no_payoff | `audit_reports\asr_repaired_window_2efbe27a-4f64-41aa-9077-6f483e00fc4f_35036_37220.json` |
| 13 | validated_audio_backed_repair_available | no_hook_no_payoff | `audit_reports\asr_repaired_window_2efbe27a-4f64-41aa-9077-6f483e00fc4f_39604_41236.json` |

## Repair Failures
| Candidate | Window | Error |
|---:|---|---|
| 1 | 589.36 -> 639.36 | faster_whisper_child_failed |
| 10 | 270.92 -> 283.76 | faster_whisper_child_failed |

## Best Next Production Patch
Use the new per-window repair artifacts only as a fail-closed gating input inside `build_final_clips()`. Do not enable ranking from repaired windows unless the artifact says `repaired_window_available=true`. Do not treat `repair_export_safe=true` as a Creator QA bypass; non-ASR Creator QA reasons still apply.

## Do Not Touch
- Do not weaken Creator QA.
- Do not relax ASR stability thresholds.
- Do not substitute V49.8 normalized metadata for export text.
- Do not rerun a full video job until the exact-window repair evidence justifies it.
- Do not alter frontend, render, export, or subtitle code.
