# V49.7 Salvage Replay Audit Report

Scope: offline replay only. No video rerun, Creator QA relaxation, ASR threshold relaxation, frontend, render, export, or subtitle changes.

## Summary
- job_id: 2efbe27a-4f64-41aa-9077-6f483e00fc4f
- replayable candidates: 17
- current finalists: 6
- current finalists quarantined: 4
- remaining clean/borderline candidates: 2
- current final clean/borderline/unstable: 2 / 0 / 4
- predicted final clean/borderline/unstable: 2 / 0 / 0
- final unstable candidates decrease: True
- semantic degraded finalists increase: False
- video rerun justified: True

## Current Finalists Quarantined
| Candidate | Window | Semantic | Local ASR | Overlap | Reason |
|---:|---|---|---|---:|---|
| 1 | 589.36 -> 639.36 | degraded_semantics | unstable | 1.0 | production_unstable_asr_window_unrepaired |
| 10 | 270.92 -> 283.76 | clean_semantics | unstable | 1.0 | production_unstable_asr_window_unrepaired |
| 12 | 350.36 -> 372.2 | borderline_semantics | unstable | 1.0 | production_unstable_asr_window_unrepaired |
| 13 | 396.04 -> 412.36 | borderline_semantics | unstable | 1.0 | production_unstable_asr_window_unrepaired |

## Predicted Finalists
| Candidate | Window | Score | Semantic | Local ASR | Decision |
|---:|---|---:|---|---|---|
| 2 | 1161.0 -> 1173.0 | 162.0 | degraded_semantics | clean:0.0 | allowed_clean |
| 16 | 536.36 -> 548.36 | 152.0 | degraded_semantics | clean:0.0 | allowed_clean |

## Regression Risks
- Offline replay approximates production dedupe with start-time dedupe only.
- No repaired transcript segments exist yet, so all production-unstable windows are fail-closed.
- Quarantine can reduce finalist count if too few clean/borderline candidates survive.
- Semantic-degraded but structurally clean windows can still remain; Creator QA remains the final guard.
