# V55 Combined Quality Decision Audit Report

Scope: combined audit-only decision across V49.7 through V54.1. No Creator QA weakening, no ASR threshold relaxation, no candidate-generation patch, and no full generation were performed.

## Final Decision
- recommendation: collect_stronger_sources
- worth_full_generation: False
- reason: No source in the completed V54.1 batch is good or borderline, and the repair/replay chain never produced creator-safe candidates.

## Batch Summary
- sources_completed: 5
- good_sources: 0
- borderline_sources: 0
- poor_sources: 5
- best_source_for_full_generation: None
- expected_clip_yield: low

## What Is Working
- Fail-closed ASR quarantine and salvage logic reduce unstable finalists without weakening Creator QA.
- Targeted and audio-backed ASR repair can improve local ASR and semantic cleanliness on some exact windows.
- Resume-safe source preflight now scores raw sources one at a time and reuses existing ASR artifacts.
- Source-quality scoring is consistently identifying weak uploads before any full-generation run.

## What Is Still Failing
- Creator-safe output remains zero across the repair, replay, and fresh-source audits.
- The batch still has no source rated good or borderline after V54.1 completed all five unscored sources.
- Payoff and standalone-context failures persist after repaired text replay, payoff override replay, and context shaping replay.
- No audit in this chain justifies full generation on the current batch.

## ASR And Source-Quality Failures
- V49.9 completed only 2 audio-backed repairs while 2 failed, so ASR cleanup is partial.
- V51 fresh-source validation still showed asr_quality_score=62 with low_confidence_asr=True.
- V54.1 finished with sources_completed=5, good_sources=0, borderline_sources=0, poor_sources=5.
- Observed source-quality dominant failures across V54.1: filler_heavy_source, missing_standalone_payoff, semantic_degradation.

## Payoff And Context Failures
- V50 repaired-text replay kept creator_safe_after=0 and no_hook_no_payoff_after=6.
- V50.1 payoff setup replay found override_count=0 and creator_safe_after=0.
- V50.2 context shaping replay expanded 0 candidates and still left creator_safe_after=0.
- V50.3 adjacent context repair produced context_expansion_possible_after_repair=0.
- V52 payoff-native generation found payoff_anchors_found=0 and candidates_generated_from_payoff=0.

## Source Snapshot

| Job | Label | Score | Yield | Dominant Failure | Creator-Safe Count |
|---|---|---:|---|---|---:|
| 42007af6-770d-4192-bed6-1fbe7588c168 | poor | 0 | low | filler_heavy_source | 0 |
| 44198754-4f75-4428-9926-616c0ce170c9 | poor | 0 | low | filler_heavy_source | 0 |
| 646ad490-6470-4d8f-ace2-7b3ddceb49d7 | poor | 0 | low | semantic_degradation | 0 |
| 833d13b2-a3aa-4fae-97da-f715a5ee3149 | poor | 0 | low | filler_heavy_source | 0 |
| c537ca42-8d0d-4f67-a279-7e63156f32ea | poor | 0 | low | missing_standalone_payoff | 0 |
