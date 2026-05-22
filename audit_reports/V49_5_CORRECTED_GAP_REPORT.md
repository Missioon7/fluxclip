# V49.5 Corrected Master Gap Report

Scope: offline-only correction after V49.4 ASR stability parity fix. No video rerun, no production patch, no Creator QA/frontend/render/export/subtitle changes.

## Source Audits Rerun
- `python audit_reports\v48_candidate_asr_confidence_audit.py`
- `python audit_reports\v48_clean_window_candidate_ranking_audit.py`
- `python audit_reports\v48_semantic_asr_confidence_audit.py`
- `python audit_reports\v49_asr_stability_parity_audit.py`
- `python audit_reports\v49_master_gap_audit.py`

No audit scripts were changed, so no compile step was needed.

## Parity-Corrected Facts
- Stability source of truth: `production_helpers`
- Parity status: 6/6 final candidates matched production labels and ratios
- Production vs audit label mismatches: 0
- Production vs audit ratio mismatches: 0
- Production chunk labels: 9 `replacement_artifact_collapse`, 1 `local_repetition_collapse`, 4 `clean`
- Corrected semantic audit structural labels: 4 clean, 16 unstable across 20 candidates
- Semantic labels: 1 clean, 2 borderline, 17 degraded across 20 candidates
- Final semantic labels: 5 degraded, 1 clean
- Final structural labels from corrected semantic/parity path: 4 unstable, 2 clean
- Candidate `270.92 -> 283.76`: structural unstable, semantic clean, unstable overlap 1.0, overlapping production chunk `220.0 -> 340.0` labeled `replacement_artifact_collapse`

## Previous Conclusions Invalid Due To Audit Drift
1. The old conclusion that candidate `270.92 -> 283.76` was locally clean/salvageable is invalid. It is semantic-clean but production-structural unstable.
2. The old P0 framing that "global ASR fail-closed rejects locally/semantically usable candidates" is invalid for the corrected latest job. The only clean-semantic finalist is not locally stable.
3. Any proposed Creator QA rollback or local-semantic bypass based on the old `270.92 -> 283.76` clean-window label is invalid.
4. Legacy clean-window counts from reports that did not use production helpers are diagnostic only and must not drive production decisions unless reconciled against V49 parity.
5. A ranking-only patch is not justified as the next fix. Ranking can surface cleaner text, but corrected structural parity shows the surfaced clean-semantic candidate still fails ASR stability.

## Conclusions That Remain Valid
1. The native ASR artifact is still severely degraded: production parity sees 10 unstable chunks out of 14.
2. Semantic ASR degradation remains a real blocker: 17/20 candidates are degraded, and 5/6 finalists are degraded.
3. Creator QA correctly produces zero safe clips for the corrected latest job: all finalists still have `asr_low_confidence` and `no_hook_no_payoff`; 4/6 also have `weak_standalone_context`.
4. V48.9 semantic preference still helps as a ranking and diagnostic layer because it can surface clean/borderline semantic windows, but it does not solve structural ASR instability.
5. Candidate expansion/editorial context remains a secondary blocker because all finalists have zero payoff, but expanding bad ASR text is not the first fix.
6. Retry behavior remains suspect because final artifacts are still native-transcribe low confidence, but the next change should replace or repair unstable-window ASR behavior rather than weaken QA.

## Current True Blocker Ranking
1. P0 - ASR unstable-window corruption in the source transcript.
   Evidence: parity-fixed production labels show 10/14 chunks unstable and 4/6 finalists unstable. Candidate `270.92 -> 283.76` is clean_semantics but structurally unstable.
   Target: retry path replace/repair for unstable Hindi/Hinglish windows, not QA rollback.

2. P0 - Hindi semantic ASR corruption across candidate text.
   Evidence: semantic audit reports 17/20 degraded candidates and 5/6 degraded finalists.
   Target: deterministic Hindi semantic ASR repair/normalization diagnostics after unstable-window repair is defined.

3. P1 - Editorial payoff/setup extraction has no usable payoff.
   Evidence: Creator QA rejects 6/6 finalists with `no_hook_no_payoff`; latest average payoff is 0.0.
   Target: candidate expansion/payoff repair only after ASR text quality is locally stable enough to evaluate.

4. P1 - Ranking/dedupe can still lose cleaner candidates.
   Evidence: V48.9 helps surface cleaner semantic windows, but corrected clean/borderline semantic candidates are structurally unstable.
   Target: keep V48.9; defer ranking/dedupe patch.

5. P2 - Retry path runtime policy.
   Evidence: fallback remains low-confidence native ASR.
   Target: replace or scope retry behavior after offline unstable-window repair audit predicts improvement.

## Gate And Patch Decisions
- V49.1 Creator QA gate: correct; no rollback. Do not weaken `asr_low_confidence`, `no_hook_no_payoff`, or `weak_standalone_context`.
- V48.9 semantic preference: still helpful; keep it. It helps ranking diagnostics but is insufficient while local ASR stability fails.
- ASR stability classifier thresholds: do not relax. The parity-fixed classifier is now aligned with production and is catching real unstable chunks.
- Hindi semantic ASR repair/normalization: yes, but after preserving structural fail-closed behavior.
- Retry path disable/replace: yes, this is the recommended next target.
- Candidate expansion: defer until ASR repair gives stable text to expand.
- Creator QA: do not patch next except to add metadata/reporting if needed.

## Exact Next Recommended Patch
Patch: V49.6 offline unstable-window ASR repair/replace audit, then a narrow retry-path replacement only if the offline audit predicts improvement.

Risk: medium for production, low for the audit-only preflight. The risk is transcript policy drift: replacing unstable windows can improve candidate quality, but it must not allow structurally unstable or semantically degraded text through Creator QA.

## Do Not Touch
- Do not roll back V49.1 Creator QA.
- Do not weaken Creator QA acceptance thresholds.
- Do not export rejected clips.
- Do not change frontend/render/export/subtitle code.
- Do not relax ASR stability classifier thresholds to make `270.92 -> 283.76` pass.
- Do not treat legacy clean-window labels as production truth unless V49 parity agrees.
- Do not run another long-video job before an offline repair/replay audit predicts improvement.

## Exact Next Codex Prompt
```text
FluxClip V49.6 offline unstable-window ASR repair/replace audit.

Environment:
- Local Windows only
- Path: C:\fluxclip_latest\fluxclip
- Offline only
- No video rerun
- No production patch unless explicitly requested after audit
- No frontend/render/export/subtitle changes
- Do not weaken Creator QA
- Do not relax ASR stability thresholds
- Compile only if changing audit scripts

Context:
V49.4 fixed ASR stability parity. The corrected source of truth is production_helpers:
- production_vs_audit_label_mismatches=0
- production_vs_audit_ratio_mismatches=0
- candidate 270.92 -> 283.76 is semantic clean but production-structural unstable with unstable overlap 1.0
- corrected semantic audit: 17/20 candidates degraded, 5/6 finalists degraded, 4/6 finalists structurally unstable

Task:
Create an audit-only V49.6 report that evaluates whether unstable Hindi/Hinglish ASR windows should be repaired, retranscribed, or replaced before candidate ranking/Creator QA.

Requirements:
- Use existing ASR artifacts and logs only.
- Use pipeline_runner production stability helpers as the structural source of truth.
- For each unstable chunk, report overlap with funnel/final candidates, replacement artifacts, repetition collapse, semantic corruption, and whether a local repair/retry would plausibly change candidate eligibility.
- Compare three options without changing production:
  1. keep current native ASR fallback
  2. disable/shorten the current no-benefit retry path
  3. replace retry with targeted unstable-window repair/retranscription
- Do not propose Creator QA relaxation.
- Do not propose ASR threshold relaxation.

Outputs:
- audit_reports/V49_6_ASR_REPAIR_REPLACE_AUDIT_REPORT.md
- audit_reports/v49_6_asr_repair_replace_audit.json

Return:
- corrected top unstable windows
- candidate eligibility impact
- recommended retry/repair strategy
- risk level
- exact next production patch prompt only if audit evidence supports one
```
