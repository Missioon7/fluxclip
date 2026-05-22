# Editorial Validation Report

Source: clip_log=analytics/clip_intelligence.jsonl job_id=e0926df0-8fdb-4441-9d95-af58ba1a3ec5 stage=pre_creator_qa
Clip count: 5
Stages: pre_creator_qa=5
Niches: general=4, education_explainer=1

## Diagnostic Coverage
- setup_strength: present=5 missing=0 avg=8.0 min=0.0 max=10.0
- payoff_strength: present=5 missing=0 avg=0.0 min=0.0 max=0.0
- continuation_risk: present=5 missing=0 avg=0.0 min=0.0 max=0.0
- context_density: present=5 missing=0 avg=None min=None max=None
- story_completeness_estimate: present=5 missing=0 avg=34.4 min=17.0 max=54.0
- v40_narrative_score: present=5 missing=0 avg=21.6 min=11.0 max=32.0
- natural_editor_score: present=5 missing=0 avg=30.0 min=30.0 max=30.0
- true_creator_score: present=5 missing=0 avg=37.6 min=36.0 max=44.0
- context_quality: present=5 missing=0 avg=6.0 min=0.0 max=10.0
- payoff_bonus: present=5 missing=0 avg=0.0 min=0.0 max=0.0

## Editorial Gaps
- Remaining gap counts: weak_payoff=5, weak_setup=1, incomplete_story=1
- V40 narrative reasons: good_story_length=3, setup_context=1, longform_context_length=1
- V40 impact signals: clips_with_v40_score=5 story_editor_ok=4 avg_v40_score=21.6

## Reason Signals
- v40_narrative_reasons: good_story_length=3, setup_context=1, longform_context_length=1
- editor_reasons: none
- true_creator_reasons: none
- creator_qa_metadata_reasons: none

## Creator QA
- Events: CREATOR_QA_REJECT=5, CREATOR_QA_ZERO_SAFE_CLIPS=1
- Rejection reasons: no_hook_no_payoff=5, weak_standalone_context=3
- Metadata reasons: missing_setup=2

## Clip Review
- #1 8 10 start=63.44 end=89.44 score=218 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=43.0)
  preview: आपको उसको होन करते रहना चाहिए और चैसे ही पहला दर्वाजा खिडकी कही भी अपको वो अपने स्किल सेट या वो वेपन्स लेकर के इंटर करना चाहिया. आपको लगता ह...
- #2 Untitled Clip start=232.8 end=249.8 score=186 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: कुछ दिन में लिखते हैं। उस बक्त आपका टाइम, फ्रेम आप माइंड में उस बक्त आप कैसे ये कहाणिया लिखते थे? इत्ते दिस्टरबड माइंद में। मैं, अच्छालि वो...
- #3 Unreasonable start=90.44 end=134.8 score=180 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=54.0)
  preview: मेरे तो लगता है आपको पर अपना टाइम आग絵 अपना बेटा आगया हुता. जिस दिन अपना बेटा आगा यह आपको ब unreasonable कि आपका आपको डुमी. अभी आपकी महनत, चि...
- #4 Untitled Clip start=0.0 end=49.12 score=168 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: तो मीटिंगे बीच में एर्पॉट के लाउज में कहीं बी लिख से था। तो मैं कहीं बी लिख लेता हूँ। आपको लगता है अक्षर्च जी कि अपना टाइम आयेगा वो अपना टाइ...
- #5 Untitled Clip start=148.8 end=203.66 score=124 gaps=weak_setup, weak_payoff, incomplete_story diagnostics=(setup_strength=0.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=17.0)
  preview: उस दिन सही माइने में पूरी महनत का जो क्रक्स है न ओउईक बून अम्रिद जो एक वो उस दिन मिलेगा तब तक मैं लगरा हुं आपका बेटे से मतलब आपका जो आपकी फर...

## Interpretation Guide
- High continuation_risk means the clip may still start or end mid-thought.
- Low setup_strength means the viewer may lack setup before the hook.
- Low payoff_strength means the clip may not resolve or land cleanly.
- Low story_completeness_estimate means the clip needs boundary repair or better ASR before export.
- Missing diagnostics usually means the job was produced before the guarded V40/editorial diagnostics patch.
