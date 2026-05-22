# Editorial Validation Report

Source: clip_log=analytics/clip_intelligence.jsonl job_id=23f21012-b025-4521-93c0-e13d15271343 stage=pre_creator_qa
Clip count: 5
Stages: pre_creator_qa=5
Niches: general=5

## Diagnostic Coverage
- setup_strength: present=5 missing=0 avg=10.0 min=10.0 max=10.0
- payoff_strength: present=5 missing=0 avg=0.0 min=0.0 max=0.0
- continuation_risk: present=5 missing=0 avg=0.0 min=0.0 max=0.0
- context_density: present=5 missing=0 avg=None min=None max=None
- story_completeness_estimate: present=5 missing=0 avg=31.4 min=29.0 max=35.0
- v40_narrative_score: present=5 missing=0 avg=19.0 min=19.0 max=19.0
- natural_editor_score: present=5 missing=0 avg=30.0 min=30.0 max=30.0
- true_creator_score: present=5 missing=0 avg=37.6 min=36.0 max=44.0
- context_quality: present=5 missing=0 avg=10.0 min=10.0 max=10.0
- payoff_bonus: present=5 missing=0 avg=0.0 min=0.0 max=0.0

## Editorial Gaps
- Remaining gap counts: weak_payoff=5
- V40 narrative reasons: good_story_length=5
- V40 impact signals: clips_with_v40_score=5 story_editor_ok=5 avg_v40_score=19.0

## Reason Signals
- v40_narrative_reasons: good_story_length=5
- editor_reasons: none
- true_creator_reasons: none
- creator_qa_metadata_reasons: none

## Creator QA
- Events: CREATOR_QA_REJECT=5, CREATOR_QA_ZERO_SAFE_CLIPS=1
- Rejection reasons: no_hook_no_payoff=5, weak_standalone_context=1
- Metadata reasons: none

## Clip Review
- #1 Untitled Clip start=156.08 end=192.46 score=185 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: वो एक बून अम्रिद जो है न वो उस दिन मिलेगा. तब तक मैं लगा रहूं। मौश्ट शौट में क्यूकि शायद कुछ लोग एक खनेक्ट मिस कर रहे हूं. अपका बेटे से मतलब...
- #2 Untitled Clip start=235.58 end=249.58 score=180 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: आप प्रेमाइंड में उस वक्त आप कैसे ये कहाणिया लिखते थे? इत्ते डिस्टरब्ड माइंड में. मैं आज्च्छी वो कहाणी न, स्पिती जी, मैं पब्लिक के लिए और पब्...
- #3 Untitled Clip start=0.0 end=34.08 score=174 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=35.0)
  preview: तो मीटिंगे बीच में एर्पॉट के लाउज में कहीं बी लिख से था। तो मैं कहीं बी लिख लेता हूँ। आपको लगता है अक्षर्च जी कि अपना टाइम आयेगा वो अपना टाइ...
- #4 Marvel DC 10 start=313.58 end=344.58 score=172 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=35.0)
  preview: वो आपको दिकता ही रहे है यह आपसे सटाही रहे हैं. आप प्यार तो फिर भी करते है न. तो वो जो उनका समय था मेरे साथ, मैं उस समय को डालना लग जा आओग उन...
- #5 Untitled Clip start=34.08 end=78.08 score=168 gaps=weak_payoff diagnostics=(setup_strength=10.0, payoff_strength=0.0, continuation_risk=0, context_density=balanced, story_completeness_estimate=29.0)
  preview: आपको लगता हैं कि एक बार ऐसा होता हैं करियर में एक बंदे का एक ऐसा पीरेड आता है और इसे मैं खुद भी वास्ता रखती हूं आपको लगता है आपका वो समया आच...

## Interpretation Guide
- High continuation_risk means the clip may still start or end mid-thought.
- Low setup_strength means the viewer may lack setup before the hook.
- Low payoff_strength means the clip may not resolve or land cleanly.
- Low story_completeness_estimate means the clip needs boundary repair or better ASR before export.
- Missing diagnostics usually means the job was produced before the guarded V40/editorial diagnostics patch.
