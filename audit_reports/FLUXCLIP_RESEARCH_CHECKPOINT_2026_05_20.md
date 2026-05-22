# FluxClip Research Checkpoint - 2026-05-20

## 1. Current Architecture Map

FluxClip currently has four major editorial layers:

1. ASR layer
   - `asr_engine.py`
   - Native Whisper small first.
   - Guarded faster-whisper medium retry path.
   - ASR quality scoring and low-confidence flags.

2. Candidate generation and shaping
   - `pipeline_runner.py`
   - `build_story_arc_candidates`
   - `merge_viral_candidates`
   - `build_final_clips`
   - V40 story shaping and boundary repair.
   - V42 guarded payoff extension.

3. Editorial scoring and QA
   - V40 narrative quality.
   - V41 story diagnostics.
   - V43 Hinglish payoff keywords.
   - V44 semantic payoff heuristics.
   - Creator QA fail-closed gate.

4. Offline research and regression tools
   - `audit_reports/offline_editorial_replay.py`
   - `audit_reports/test_payoff_semantics.py`
   - `analytics/candidate_funnel.jsonl`
   - `audit_reports/narrative_payoff_analysis.py`

## 2. Solved Systems

- Creator QA fails closed and prevents unsafe/no-payoff releases.
- Offline replay detects QA regressions and false-positive approvals.
- V44 payoff fixtures are deterministic and passing:
  - 16/16 passed
  - false positives: 0
  - false negatives: 0
- Candidate funnel visibility is now achieved.
- ASR retry gate improved and can produce clean ASR on the target source.
- Candidate-funnel diagnostics expose every merged candidate and filter decision.
- Offline narrative/payoff analysis now identifies human-looking payoff gaps.

## 3. Remaining Bottlenecks

1. Hindi/Hinglish ASR variance.
2. Payoff detection under noisy transcript.
3. Emotional landing discovery.
4. Distinguishing true payoff from motivational quote/filler.
5. Candidate boundary repair toward clean payoff.
6. Lack of semantic understanding beyond deterministic phrase patterns.

## 4. Exact Semantic Gap Findings

From `NARRATIVE_PAYOFF_ANALYSIS.md`:

- Candidates analyzed: 21
- `weak_payoff`: 9
- `no_detected_payoff`: 12
- human-looking payoff with `V44=0`: 10

Human-looking payoff appears in phrases like:

- "पूरी मेहनत ... उस दिन मिलेगा"
- "greatest revenge ... success"
- "आप इतनी मेहनत कर लीजे..."
- preparation / skillset / future payoff language

But V44 often scores zero because:

- payoff phrase is truncated
- setup and landing are split across duplicate/overlapping candidates
- ASR corrupts key words
- quote-like motivational language lacks explicit causal closure
- ending lacks enough clean resolution cues

## 5. ASR Variance Findings

Same source can produce clean or masked ASR.

Clean path example:

- `asr_mode=faster_whisper_medium_retry`
- `asr_quality_score=100`
- `low_confidence_asr=False`

Masked path example:

- job `v44_final_e0926df0`
- `asr_mode=native_transcribe`
- `asr_quality_score=52`
- `low_confidence_asr=True`
- `replacement_chars=3`
- `repeated_hindi_phrase=अपको अपको`

Root issue:

- Native quality is often poor.
- Retry trigger works.
- Medium retry/full-medium selection is still not fully reproducible.
- When fallback stays native, editorial validation becomes invalid.

## 6. Candidate Funnel Findings

Candidate funnel is no longer blind.

Clean-ASR run `candidate_funnel_e0926df0`:

- merged candidates: 10
- accepted: 6
- duplicate removed: 3
- silent removed: 0
- all accepted candidates still had:
  - `payoff_bonus=0`
  - `v43=0`
  - `v44=0`

Final masked run `v44_final_e0926df0`:

- merged candidates: 11
- accepted: 4
- duplicate removed: 5
- dna rejected: 1
- quality rejected: 1
- candidates with detected payoff: 0

Conclusion:

Candidate discovery is surfacing enough material for analysis. The gap is payoff interpretation and boundary quality, not raw candidate visibility.

## 7. Why Payoff Is Still Missed

Payoff is missed for four reasons:

1. Transcript quality
   - Hindi/Hinglish payoff words are often garbled.
   - ASR artifacts break causal and emotional structure.

2. Boundary split
   - Setup and payoff often land in adjacent or duplicate candidates.
   - Candidate windows contain either setup or landing, not always both.

3. Motivational ambiguity
   - "Mehnat", "success", "revenge", "milega" can be real payoff or empty quote.
   - Current V44 correctly avoids many false positives, but that also under-detects subtle true payoff.

4. No semantic model
   - Deterministic heuristics can detect patterns, but cannot robustly infer narrative closure when wording is corrupted or implicit.

## 8. What V44 Currently Succeeds / Fails At

V44 succeeds at:

- question -> answer payoff
- contrast -> resolution
- problem -> realization
- claim -> explanation
- mystery -> reveal
- clean effort -> reward fixtures
- clean preparation -> future payoff fixtures
- avoiding quote-only motivational filler
- avoiding teaser-only false positives

V44 fails or remains weak at:

- noisy Hindi/Hinglish ASR
- truncated payoff endings
- setup/payoff split across nearby candidates
- emotional payoff without explicit resolution wording
- motivational payoff where the causal link is implied
- distinguishing human-perceived closure from generic inspirational phrasing in corrupted text

## 9. Highest-Leverage Future R&D Directions

1. Offline ASR decision replay and stabilization.
2. Candidate boundary reconstruction around payoff hints.
3. Human-review payoff hint extraction from candidate funnel rows.
4. Semantic payoff scoring beyond phrase matching.
5. Preference learning from accepted/rejected creator-safe clips.
6. Multimodal validation of emotional landing, especially pauses, faces, and tone.

## 10. Suggested Next Milestone Versions

### V45 - ASR Decision Stability

Goal:

- Make clean ASR reproducible before more editorial validation.

Scope:

- Offline ASR retry decision audit.
- Source/audio hash tracking.
- Native/sample/full-medium comparison.
- Deterministic final ASR selection reason.

Success:

- Same source consistently selects clean retry when full medium is better.

### V46 - Payoff Boundary Repair

Goal:

- Rebuild candidate windows around payoff hints without loosening QA.

Scope:

- Offline candidate-window analyzer.
- Extend backward for setup and forward for payoff.
- Keep fail-closed scoring and Creator QA.

Success:

- Candidate windows contain setup + landing in one clip.

### V47 - Semantic Editorial Intelligence

Goal:

- Move beyond keyword heuristics toward narrative payoff understanding.

Scope:

- Optional embeddings or lightweight semantic similarity.
- Payoff archetype classifier.
- Human-review labels.
- Preference-learning-ready dataset.

Success:

- Detect emotional/narrative closure even when explicit payoff keywords are absent.

## 11. Upgrade Requirements

Simple heuristics:

- More phrase variants.
- Better payoff quality block.
- Boundary repair rules.
- Candidate funnel ranking diagnostics.
- ASR retry logging/auditing.

Semantic embeddings:

- Detect paraphrased payoff.
- Match setup to resolution.
- Identify effort -> reward / problem -> realization without exact phrases.
- Cluster candidate windows by narrative completeness.

Multimodal reasoning:

- Detect emotional landing from pause, face, tone, emphasis.
- Separate filler from genuine emotional closure.
- Validate whether a payoff "feels" complete in the actual video.

Preference learning:

- Learn from accepted/rejected creator clips.
- Tune payoff strength and story completeness to creator taste.
- Rank emotionally satisfying clips over merely structured clips.

## 12. Roadmap To Opus-Level Editorial Feel

1. Stabilize ASR first.
   - Editorial intelligence is unreliable if transcript quality changes run to run.

2. Keep Creator QA fail-closed.
   - Do not loosen approval gates.
   - Improve candidates before approval.

3. Build offline datasets.
   - Candidate funnel rows.
   - Payoff fixture rows.
   - Creator QA rejects.
   - Human-review hints.

4. Add boundary repair before promotion.
   - Most payoff failures are not just detection; they are setup/landing split problems.

5. Add semantic scoring.
   - Start with embeddings offline.
   - Compare setup sentence to ending sentence.
   - Score closure, consequence, realization, and emotional landing.

6. Add multimodal review.
   - Use visual and audio cues to confirm emotional beats.
   - Do not use multimodal signals to bypass QA; use them to rank candidates.

7. Add preference learning.
   - Collect creator-safe approvals and rejections.
   - Train/tune ranking around "would a human editor clip this?"

8. Final target.
   - FluxClip should select clips that have:
     - clean transcript
     - clear setup
     - narrative turn
     - emotional or informational payoff
     - clean ending
     - no ASR artifacts
     - no teaser-only release

## Final Research State

FluxClip is now architecturally mature enough for offline editorial-engine iteration. The main blocker is no longer candidate visibility or QA safety. The current frontier is stable Hindi/Hinglish ASR plus semantic payoff understanding across noisy, emotionally implicit podcast speech.
