# Payoff Semantic Fixture Report

Scope: deterministic payoff fixtures only. No video, ASR, FFmpeg, export, server, frontend, upload, or GPU flow.
Fixtures: 16
Passed: 16
Failed: 0
False positives: 0
False negatives: 0

## Fixtures
- PASS english_question_answer_without_keyword_payoff (english): expected_payoff=True actual_payoff=True combined=14.0 v43=0.0 v44=14.0 confidence=medium qa_reject=False
  reasons: v43=[] v44=['semantic_setup_present', 'semantic_late_resolution', 'semantic_contrast_resolution', 'semantic_causal_resolution'] qa=[]
- PASS hinglish_realization_without_explicit_payoff (hinglish): expected_payoff=True actual_payoff=True combined=13.0 v43=0.0 v44=13.0 confidence=low qa_reject=False
  reasons: v43=[] v44=['semantic_setup_present', 'semantic_contrast_resolution', 'semantic_reveal_shift'] qa=[]
- PASS hindi_roman_mystery_reveal_without_keyword_payoff (hinglish): expected_payoff=True actual_payoff=True combined=14.0 v43=7.0 v44=14.0 confidence=medium qa_reject=False
  reasons: v43=['hinglish_reveal_payoff'] v44=['semantic_setup_present', 'semantic_late_resolution', 'semantic_contrast_resolution', 'semantic_reveal_shift'] qa=[]
- PASS english_problem_to_realization (english): expected_payoff=True actual_payoff=True combined=14.0 v43=0.0 v44=14.0 confidence=medium qa_reject=False
  reasons: v43=[] v44=['semantic_setup_present', 'semantic_late_resolution', 'semantic_contrast_resolution', 'semantic_causal_resolution'] qa=[]
- PASS hinglish_explicit_v43_payoff (hinglish): expected_payoff=True actual_payoff=True combined=7.0 v43=7.0 v44=0.0 confidence=none qa_reject=False
  reasons: v43=['hinglish_explanation_payoff'] v44=[] qa=[]
- PASS negative_setup_only_no_landing (english): expected_payoff=False actual_payoff=False combined=0.0 v43=0.0 v44=0.0 confidence=none qa_reject=True
  reasons: v43=[] v44=[] qa=['no_hook_no_payoff']
- PASS negative_contrast_but_no_resolution (hinglish): expected_payoff=False actual_payoff=False combined=0.0 v43=0.0 v44=0.0 confidence=none qa_reject=True
  reasons: v43=[] v44=[] qa=['no_hook_no_payoff']
- PASS negative_keyword_filler_should_not_pass (english): expected_payoff=False actual_payoff=False combined=0.0 v43=6.0 v44=0.0 confidence=none qa_reject=True
  reasons: v43=['hinglish_consequence_payoff'] v44=[] qa=['no_hook_no_payoff']
- PASS negative_middle_fragment_no_setup (hinglish): expected_payoff=False actual_payoff=False combined=0.0 v43=0.0 v44=0.0 confidence=none qa_reject=True
  reasons: v43=[] v44=[] qa=['no_hook_no_payoff']
- PASS hindi_effort_reward_that_day_landing (hindi): expected_payoff=True actual_payoff=True combined=14.0 v43=6.0 v44=14.0 confidence=medium qa_reject=False
  reasons: v43=['hinglish_consequence_payoff'] v44=['semantic_setup_present', 'semantic_late_resolution', 'semantic_effort_reward_landing', 'semantic_that_day_landing'] qa=[]
- PASS hinglish_revenge_success_landing (hinglish): expected_payoff=True actual_payoff=True combined=14.0 v43=0.0 v44=14.0 confidence=high qa_reject=False
  reasons: v43=[] v44=['semantic_setup_present', 'semantic_late_resolution', 'semantic_contrast_resolution', 'semantic_reveal_shift', 'semantic_effort_reward_landing'] qa=[]
- PASS hindi_preparation_future_payoff (hindi): expected_payoff=True actual_payoff=True combined=14.0 v43=6.0 v44=14.0 confidence=high qa_reject=False
  reasons: v43=['hinglish_consequence_payoff'] v44=['semantic_setup_present', 'semantic_late_resolution', 'semantic_contrast_resolution', 'semantic_causal_resolution', 'semantic_preparation_future_landing'] qa=[]
- PASS devanagari_mehnat_milega_landing (hindi): expected_payoff=True actual_payoff=True combined=14.0 v43=0.0 v44=14.0 confidence=medium qa_reject=True
  reasons: v43=[] v44=['semantic_setup_present', 'semantic_late_resolution', 'semantic_effort_reward_landing', 'semantic_that_day_landing'] qa=['weak_standalone_context']
- PASS negative_mehnat_setup_no_reward (hinglish): expected_payoff=False actual_payoff=False combined=0.0 v43=0.0 v44=0.0 confidence=none qa_reject=True
  reasons: v43=[] v44=[] qa=['no_hook_no_payoff']
- PASS negative_revenge_success_quote_only (hinglish): expected_payoff=False actual_payoff=False combined=0.0 v43=6.0 v44=0.0 confidence=none qa_reject=True
  reasons: v43=['hinglish_consequence_payoff'] v44=[] qa=['no_hook_no_payoff']
- PASS negative_preparation_teaser_no_opening (hinglish): expected_payoff=False actual_payoff=False combined=0.0 v43=6.0 v44=0.0 confidence=none qa_reject=True
  reasons: v43=['hinglish_consequence_payoff'] v44=[] qa=['no_hook_no_payoff']
