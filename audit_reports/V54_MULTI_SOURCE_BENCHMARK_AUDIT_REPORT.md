# V54 Multi-Source Benchmark Audit Report

Scope: benchmark-pack audit over available raw source videos. Sources with V53-compatible artifacts are scored directly. Unscored sources are deferred until preflight source-quality scoring is available.

- total_sources_tested: 10
- good_sources: 0
- borderline_sources: 0
- poor_sources: 5
- unscored_sources: 5
- best_source_for_full_rerun: None
- expected_clip_yield: low
- recommended_next_action: preload_v53_scoring_on_unscored_sources_before_any_full_generation

| Job | Label | Score | Yield | Action | Artifact |
|---|---|---:|---|---|---|
| 2efbe27a-4f64-41aa-9077-6f483e00fc4f | poor | 0 | low | use_source_for_payoff_generation_experiments_only | True |
| f964425c-0803-4e3d-b6e7-98f8eb3e7d52 | poor | 0 | low | use_source_for_payoff_generation_experiments_only | True |
| e0fc755a-9319-4bab-ad50-fd6ffa723bcb | poor | 0 | low | use_source_for_payoff_generation_experiments_only | True |
| cb7f65ba-222e-4e82-869f-57d399a3f146 | poor | 0 | low | use_source_for_payoff_generation_experiments_only | True |
| e6c97f3b-bd73-4401-a690-4f8b373af49c | poor | 0 | low | use_source_for_payoff_generation_experiments_only | True |
| 833d13b2-a3aa-4fae-97da-f715a5ee3149 | unscored |  | unknown | preload_v53_source_quality_before_full_generation | False |
| 44198754-4f75-4428-9926-616c0ce170c9 | unscored |  | unknown | preload_v53_source_quality_before_full_generation | False |
| 42007af6-770d-4192-bed6-1fbe7588c168 | unscored |  | unknown | preload_v53_source_quality_before_full_generation | False |
| c537ca42-8d0d-4f67-a279-7e63156f32ea | unscored |  | unknown | preload_v53_source_quality_before_full_generation | False |
| 646ad490-6470-4d8f-ace2-7b3ddceb49d7 | unscored |  | unknown | preload_v53_source_quality_before_full_generation | False |
