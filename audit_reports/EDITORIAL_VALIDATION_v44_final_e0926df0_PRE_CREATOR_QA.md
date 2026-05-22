# Editorial Validation Report

Source: clip_log=analytics/clip_intelligence.jsonl job_id=v44_final_e0926df0 stage=pre_creator_qa
Clip count: 4
Stages: pre_creator_qa=4
Niches: general=4

## Diagnostic Coverage
- setup_strength: present=4 missing=0 avg=10.0 min=10.0 max=10.0
- payoff_strength: present=4 missing=0 avg=0.0 min=0.0 max=0.0
- continuation_risk: present=4 missing=0 avg=0.0 min=0.0 max=0.0
- context_density: present=4 missing=0 avg=None min=None max=None
- story_completeness_estimate: present=4 missing=0 avg=29.0 min=29.0 max=29.0
- v40_narrative_score: present=4 missing=0 avg=19.0 min=19.0 max=19.0
- natural_editor_score: present=4 missing=0 avg=30.0 min=30.0 max=30.0
- true_creator_score: present=4 missing=0 avg=36.0 min=36.0 max=36.0
- context_quality: present=4 missing=0 avg=10.0 min=10.0 max=10.0
- payoff_bonus: present=4 missing=0 avg=0.0 min=0.0 max=0.0

## Editorial Gaps
- Remaining gap counts: weak_payoff=4, low_confidence_asr=4
- V40 narrative reasons: good_story_length=4
- V40 impact signals: clips_with_v40_score=4 story_editor_ok=4 avg_v40_score=19.0

## Reason Signals
- v40_narrative_reasons: good_story_length=4
- editor_reasons: none
- true_creator_reasons: none
- creator_qa_metadata_reasons: none

## Creator QA
- Events: CREATOR_QA_REJECT=4, CREATOR_QA_ZERO_SAFE_CLIPS=1
- Rejection reasons: asr_low_confidence=4, no_hook_no_payoff=4, weak_standalone_context=2
- Metadata reasons: none

## Clip Review
- #1 Untitled Clip start=0.0 end=17.32 score=172 gaps=weak_payoff, low_confidence_asr diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: तो में बीच में एर्पोट के लाँज में कही बिलिख से. तो में कही बिलिख लिख. अपको लकता अख्शजी की अपना टाईम आएगा वो अपना टाईम आगा एग इतने पोटकास यतन...
- #2 Untitled Clip start=97.32 end=109.32 score=164 gaps=weak_payoff, low_confidence_asr diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: खिल कि अगर भी अबही भी अपकी मेहनेद शिद्धत और पहुच में कही नकही कोई कमी होगी अपी दिवाँ में जोला है, मेरी पुरी महनत, मेरा फैवरेट कोटेशन हमेशाच़...
- #3 Untitled Clip start=184.32 end=198.32 score=156 gaps=weak_payoff, low_confidence_asr diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: अगर अक्ष्द गुप्ता की एक मन्शा है एक जो ख़ाएश है अगर वो पूरी करने में जागरन मन्तन और अमारा दैनिक जागरन का पलाट्फोम
- #4 Untitled Clip start=205.32 end=241.32 score=156 gaps=weak_payoff, low_confidence_asr diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: लिकन आप ने जब ये कहानिया लिख ही, एक रह्टर्स का लिखने का कोई श्पेस नहीं होता, नी जब ये कहानिया लिख ही एक इमपोट्ट़न बात है कि अपका फ्रेम अप मा...

## Interpretation Guide
- High continuation_risk means the clip may still start or end mid-thought.
- Low setup_strength means the viewer may lack setup before the hook.
- Low payoff_strength means the clip may not resolve or land cleanly.
- Low story_completeness_estimate means the clip needs boundary repair or better ASR before export.
- Missing diagnostics usually means the job was produced before the guarded V40/editorial diagnostics patch.
