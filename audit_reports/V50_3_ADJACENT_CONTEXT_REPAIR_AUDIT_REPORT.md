# V50.3 Adjacent Context Repair Audit Report

Scope: offline only. This audit retries exact adjacent setup/payoff windows around the two repaired-clean candidates, then replays context shaping only if the adjacent repaired context is clean, semantically clean, non-drifting, and not filler-only.

## Summary
- adjacent_windows_tested: 4
- adjacent_windows_repaired: 0
- context_expansion_possible_after_repair: 0
- no_hook_no_payoff_before: 2
- no_hook_no_payoff_after: 2
- creator_safe_before: 0
- creator_safe_after: 0
- predicted_final_clean: 2
- predicted_final_unstable: 0
- video_rerun_justified: False

## Adjacent Window Repairs
| Candidate | Role | Window | Local | Semantic | Usable | Drift | Filler |
|---|---|---|---|---|---|---|---|
| [350.36, 372.2] | setup | 344.56 -> 349.92 | clean | clean_semantics | False | False | True |
| [350.36, 372.2] | payoff | 372.2 -> 390.44 | failed | failed | False | False | True |
| [396.04, 412.36] | setup | 394.32 -> 396.04 | clean | clean_semantics | False | False | True |
| [396.04, 412.36] | payoff | 413.36 -> 422.36 | clean | clean_semantics | False | False | True |

## Candidate Replay
| Window | Before Reasons | After Reasons | Expansion Possible | Expanded Window | Setup/Payoff Used | Rejected Reason |
|---|---|---|---|---|---|---|
| [350.36, 372.2] | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context | False | [350.36, 372.2] | False/False | no_usable_adjacent_repair |
| [396.04, 412.36] | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context | False | [396.04, 412.36] | False/False | no_usable_adjacent_repair |
