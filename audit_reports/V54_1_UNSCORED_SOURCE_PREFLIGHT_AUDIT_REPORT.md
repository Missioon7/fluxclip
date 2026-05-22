# V54.1 Unscored Source Preflight Audit Report

Scope: ASR-only preflight on V54 unscored raw uploads, followed by V53-style source quality scoring. This script is resume-safe and writes partial output after each source.

- total_unscored_sources: 5
- sources_attempted_this_run: 0
- sources_preflighted: 5
- sources_failed: 0
- sources_remaining: 0
- good_sources: 0
- borderline_sources: 0
- poor_sources: 5
- best_source_for_full_generation: None
- expected_clip_yield: low
- recommended_next_action: do_not_run_full_generation_on_this_batch_collect_stronger_sources

| Job | Status | Score | Label | Yield | ASR | Unstable Ratio | Clean/Borderline | Anchor Density | Context Density | Filler Ratio | Notes |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| 42007af6-770d-4192-bed6-1fbe7588c168 | completed | 0 | poor | low | 0.0 | 0.00 | 0.31 | 0.00 | 0.40 | 0.90 | artifact_reused=True |
| 44198754-4f75-4428-9926-616c0ce170c9 | completed | 0 | poor | low | 0.0 | 0.00 | 0.31 | 0.00 | 0.40 | 0.90 | artifact_reused=True |
| 646ad490-6470-4d8f-ace2-7b3ddceb49d7 | completed | 0 | poor | low | 0.0 | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | artifact_reused=False |
| 833d13b2-a3aa-4fae-97da-f715a5ee3149 | completed | 0 | poor | low | 0.0 | 0.00 | 0.31 | 0.00 | 0.40 | 0.90 | artifact_reused=True |
| c537ca42-8d0d-4f67-a279-7e63156f32ea | completed | 0 | poor | low | 0.0 | 0.00 | 0.31 | 0.00 | 0.40 | 0.90 | artifact_reused=False |
