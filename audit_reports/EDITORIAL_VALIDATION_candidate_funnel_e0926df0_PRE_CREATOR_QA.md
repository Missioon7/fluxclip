# Editorial Validation Report

Source: clip_log=analytics/clip_intelligence.jsonl job_id=candidate_funnel_e0926df0 stage=pre_creator_qa
Clip count: 6
Stages: pre_creator_qa=6
Niches: general=6

## Diagnostic Coverage
- setup_strength: present=6 missing=0 avg=10.0 min=10.0 max=10.0
- payoff_strength: present=6 missing=0 avg=0.0 min=0.0 max=0.0
- continuation_risk: present=6 missing=0 avg=0.0 min=0.0 max=0.0
- context_density: present=6 missing=0 avg=None min=None max=None
- story_completeness_estimate: present=6 missing=0 avg=34.67 min=29.0 max=37.0
- v40_narrative_score: present=6 missing=0 avg=21.67 min=19.0 max=27.0
- natural_editor_score: present=6 missing=0 avg=30.0 min=30.0 max=30.0
- true_creator_score: present=6 missing=0 avg=38.67 min=36.0 max=44.0
- context_quality: present=6 missing=0 avg=10.0 min=10.0 max=10.0
- payoff_bonus: present=6 missing=0 avg=0.0 min=0.0 max=0.0

## Editorial Gaps
- Remaining gap counts: weak_payoff=6
- V40 narrative reasons: good_story_length=6
- V40 impact signals: clips_with_v40_score=6 story_editor_ok=6 avg_v40_score=21.67

## Reason Signals
- v40_narrative_reasons: good_story_length=6
- editor_reasons: none
- true_creator_reasons: none
- creator_qa_metadata_reasons: none

## Creator QA
- Events: CREATOR_QA_REJECT=6, CREATOR_QA_ZERO_SAFE_CLIPS=1
- Rejection reasons: no_hook_no_payoff=6, weak_standalone_context=3
- Metadata reasons: none

## Clip Review
- #1 Untitled Clip start=285.38 end=305.38 score=193 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=37.0)
  preview: तो वो आप दिना में इस उम्र में आता आते था का आच्छुका होता. तो वैसी मेरा एक टाइम स्लॉर्ट मेरे बच्चे के साथ जमा हुआ था कि ये टाइम है जब मैं और...
- #2 Untitled Clip start=17.28 end=53.38 score=188 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=35.0)
  preview: धोनी इंटर्टेंट्यूनट ने यह फिल्म कि राइत्स खिताब के राइत्स ले लिए हैं। इस पर भी फिल्म आने वाले समय पे आए गै, यह दोी पाट हैं. तो इस पर भी फिल्...
- #3 Untitled Clip start=126.38 end=165.38 score=181 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=35.0)
  preview: तो ये एक जीस का इंतदार हैं, उस दिन मैं बोलूगा कि मैं पूरी तरीके से अपना बेटा हैं। ये दो लाइन मेरे दिमांग में थी जब मेरा स्ट्रूगल और हाडवाक श...
- #4 Untitled Clip start=30.28 end=85.28 score=174 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=35.0)
  preview: तो इस पर भी फिल्म आने की समाबरा हैं, आपको लिखता है कि आपका वो समय आगे हैं, क्योंकि एक बार ऐसा होता है कि करियर में एक बंदे का एक सा पीरेड आथ...
- #5 Time start=229.38 end=249.38 score=172 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=37.0)
  preview: पहाडों पे जाकर के लिखना पश्ण करते हैं, कुछ रात में लिखते हैं, कुछ दिन में लिखते हैं, उस बक्त आपका पर time, फ्रेम आप माइंड में, उस बक्त आप कै...
- #6 Untitled Clip start=159.38 end=214.38 score=156 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: महुँज शौट में कि शायद कुछ लोग एं कनेक्ट मिस कर रहे हूं, अपका बेटे से मतलब आपका जो आपकी फुर्स्ट वाइव के साथ जो आपके बेटे हैं उनसे मतलब हैं। म...

## Interpretation Guide
- High continuation_risk means the clip may still start or end mid-thought.
- Low setup_strength means the viewer may lack setup before the hook.
- Low payoff_strength means the clip may not resolve or land cleanly.
- Low story_completeness_estimate means the clip needs boundary repair or better ASR before export.
- Missing diagnostics usually means the job was produced before the guarded V40/editorial diagnostics patch.
