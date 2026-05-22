# Editorial Validation Report

Source: clip_log=analytics/clip_intelligence.jsonl job_id=candidate_funnel_e0926df0 stage=pre_export
Clip count: 0
Stages: none
Niches: none

## Diagnostic Coverage
- setup_strength: present=0 missing=0 avg=None min=None max=None
- payoff_strength: present=0 missing=0 avg=None min=None max=None
- continuation_risk: present=0 missing=0 avg=None min=None max=None
- context_density: present=0 missing=0 avg=None min=None max=None
- story_completeness_estimate: present=0 missing=0 avg=None min=None max=None
- v40_narrative_score: present=0 missing=0 avg=None min=None max=None
- natural_editor_score: present=0 missing=0 avg=None min=None max=None
- true_creator_score: present=0 missing=0 avg=None min=None max=None
- context_quality: present=0 missing=0 avg=None min=None max=None
- payoff_bonus: present=0 missing=0 avg=None min=None max=None

## Editorial Gaps
- Remaining gap counts: none
- V40 narrative reasons: none
- V40 impact signals: clips_with_v40_score=0 story_editor_ok=0 avg_v40_score=None

## Reason Signals
- v40_narrative_reasons: none
- editor_reasons: none
- true_creator_reasons: none
- creator_qa_metadata_reasons: none

## Creator QA
- Events: CREATOR_QA_REJECT=6, CREATOR_QA_ZERO_SAFE_CLIPS=1
- Rejection reasons: no_hook_no_payoff=6, weak_standalone_context=3
- Metadata reasons: none

## Clip Review

## Interpretation Guide
- High continuation_risk means the clip may still start or end mid-thought.
- Low setup_strength means the viewer may lack setup before the hook.
- Low payoff_strength means the clip may not resolve or land cleanly.
- Low story_completeness_estimate means the clip needs boundary repair or better ASR before export.
- Missing diagnostics usually means the job was produced before the guarded V40/editorial diagnostics patch.
