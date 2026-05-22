# V53 Source Quality Gate Audit Report

Scope: audit-only source quality evaluation. This scores recent sources for likely clip yield before full clip generation, without production blocking.

- jobs_evaluated: 6

| Job | Score | Label | Likely Yield | Dominant Failure | Recommended Action | ASR | Clean/Borderline | Unstable Ratio | Anchor Density | Context Density | Filler Ratio | Semantic Ratio |
|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| v51_fresh_source_23f21012 | 1 | poor | low | unstable_asr_dominant | avoid_full_generation_until_source_or_asr_capture_improves | 62.0 | 0.55 | 0.55 | 0.00 | 0.00 | 0.97 | 0.14 |
| 2efbe27a-4f64-41aa-9077-6f483e00fc4f | 0 | poor | low | missing_standalone_payoff | use_source_for_payoff_generation_experiments_only | 0.0 | 0.31 | 0.00 | 0.00 | 0.40 | 0.90 | 0.26 |
| cb7f65ba-222e-4e82-869f-57d399a3f146 | 0 | poor | low | missing_standalone_payoff | use_source_for_payoff_generation_experiments_only | 0.0 | 0.31 | 0.00 | 0.00 | 0.40 | 0.90 | 0.26 |
| e0fc755a-9319-4bab-ad50-fd6ffa723bcb | 0 | poor | low | missing_standalone_payoff | use_source_for_payoff_generation_experiments_only | 0.0 | 0.31 | 0.00 | 0.00 | 0.40 | 0.90 | 0.26 |
| e6c97f3b-bd73-4401-a690-4f8b373af49c | 0 | poor | low | missing_standalone_payoff | use_source_for_payoff_generation_experiments_only | 0.0 | 0.31 | 0.00 | 0.00 | 0.40 | 0.90 | 0.26 |
| f964425c-0803-4e3d-b6e7-98f8eb3e7d52 | 0 | poor | low | missing_standalone_payoff | use_source_for_payoff_generation_experiments_only | 0.0 | 0.31 | 0.00 | 0.00 | 0.40 | 0.90 | 0.26 |
