# Editorial Validation Report

Source: clip_log=analytics/clip_intelligence.jsonl job_id=asr_borderline_gate_e0926df0 stage=pre_creator_qa
Clip count: 1
Stages: pre_creator_qa=1
Niches: general=1

## Diagnostic Coverage
- setup_strength: present=1 missing=0 avg=10.0 min=10.0 max=10.0
- payoff_strength: present=1 missing=0 avg=0.0 min=0.0 max=0.0
- continuation_risk: present=1 missing=0 avg=0.0 min=0.0 max=0.0
- context_density: present=1 missing=0 avg=None min=None max=None
- story_completeness_estimate: present=1 missing=0 avg=35.0 min=35.0 max=35.0
- v40_narrative_score: present=1 missing=0 avg=19.0 min=19.0 max=19.0
- natural_editor_score: present=1 missing=0 avg=30.0 min=30.0 max=30.0
- true_creator_score: present=1 missing=0 avg=36.0 min=36.0 max=36.0
- context_quality: present=1 missing=0 avg=10.0 min=10.0 max=10.0
- payoff_bonus: present=1 missing=0 avg=0.0 min=0.0 max=0.0

## Editorial Gaps
- Remaining gap counts: weak_payoff=1
- V40 narrative reasons: good_story_length=1
- V40 impact signals: clips_with_v40_score=1 story_editor_ok=1 avg_v40_score=19.0

## Reason Signals
- v40_narrative_reasons: good_story_length=1
- editor_reasons: none
- true_creator_reasons: none
- creator_qa_metadata_reasons: none

## Creator QA
- Events: CREATOR_QA_REJECT=1, CREATOR_QA_ZERO_SAFE_CLIPS=1
- Rejection reasons: no_hook_no_payoff=1
- Metadata reasons: none

## Clip Review
- #1 Untitled Clip start=0.0 end=39.08 score=174 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=35.0)
  preview: तो मीटिंगे बीच में एर्पॉट के लाउज में कहीं बी लिख से था। तो मैं कहीं बी लिख लेता हूँ। आपको लगता है अक्षर्च जी कि अपना टाइम आयेगा वो अपना टाइ...

## Interpretation Guide
- High continuation_risk means the clip may still start or end mid-thought.
- Low setup_strength means the viewer may lack setup before the hook.
- Low payoff_strength means the clip may not resolve or land cleanly.
- Low story_completeness_estimate means the clip needs boundary repair or better ASR before export.
- Missing diagnostics usually means the job was produced before the guarded V40/editorial diagnostics patch.
