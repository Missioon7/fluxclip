# V50.1 Payoff Setup Replay Audit Report

Scope: offline replay only. This audit evaluates a narrow `no_hook_no_payoff` override for already clean or repaired-clean candidates with strong explanatory payoff evidence. No Creator QA thresholds were weakened globally.

## Summary
- finalists analyzed: 6
- no_hook_no_payoff_before: 6
- no_hook_no_payoff_after: 6
- creator_safe_before: 0
- creator_safe_after: 0
- predicted_final_clean: 4
- predicted_final_unstable: 2
- override_count: 0
- false_positive_risk: low
- video_rerun_justified: False

## Finalists
| Window | Local/Semantic | Repaired Applied | Payoff Detected | Override | Before Reasons | After Reasons |
|---|---|---|---|---|---|---|
| 589.36 -> 639.36 | unstable / degraded_semantics | False | False (none) | False | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | asr_low_confidence, no_hook_no_payoff, weak_standalone_context |
| 350.36 -> 372.2 | clean / clean_semantics | True | False (none) | False | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context |
| 396.04 -> 412.36 | clean / clean_semantics | True | False (none) | False | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context |
| 1161.0 -> 1173.0 | clean / degraded_semantics | False | False (none) | False | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | asr_low_confidence, no_hook_no_payoff, weak_standalone_context |
| 270.92 -> 283.76 | unstable / clean_semantics | False | False (none) | False | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | asr_low_confidence, no_hook_no_payoff, weak_standalone_context |
| 536.36 -> 548.36 | clean / clean_semantics | False | False (none) | False | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context |
