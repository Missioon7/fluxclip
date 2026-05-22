# V50.2 Context Shaping Replay Audit Report

Scope: offline replay only. This audit tests setup/payoff context expansion for the repaired-clean or locally clean target windows, but rejects any expansion that adds unstable ASR, semantic degradation, drift, filler, or no Creator QA improvement.

## Summary
- candidates_tested: 4
- candidates_expanded: 0
- no_hook_no_payoff_before: 4
- no_hook_no_payoff_after: 4
- creator_safe_before: 0
- creator_safe_after: 0
- predicted_final_clean: 4
- predicted_final_unstable: 0
- video_rerun_justified: False

## Candidate Results
| Window | Repaired Clean | Before Reasons | After Reasons | Expanded | Expanded Window | Rejected Reason |
|---|---|---|---|---|---|---|
| 350.36 -> 372.2 | True | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context | False | [350.36, 372.2] | no_clean_adjacent_context |
| 396.04 -> 412.36 | True | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context | False | [396.04, 412.36] | no_clean_adjacent_context |
| 1161.0 -> 1173.0 | False | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | False | [1161.0, 1173.0] | base_candidate_semantic_degraded |
| 536.36 -> 548.36 | False | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context | False | [536.36, 548.36] | no_clean_adjacent_context |

## Context Decisions
| Window | Setup Source | Payoff Source | After Local/Semantic | After Context/Payoff |
|---|---|---|---|---|
| 350.36 -> 372.2 | existing_window | none | clean / clean_semantics | 10.0 / 0.0 |
| 396.04 -> 412.36 | existing_window | none | clean / clean_semantics | 10.0 / 0.0 |
| 1161.0 -> 1173.0 | existing_window | none | clean / degraded_semantics | 10.0 / 0.0 |
| 536.36 -> 548.36 | existing_window | none | clean / clean_semantics | 10.0 / 0.0 |

## After Text Previews
| Window | After Preview |
|---|---|
| 350.36 -> 372.2 | और ये जो वेफर है, ये वेफर बनता है, वेफर याने की एक टुकड़ा टाइप का, ये टुकड़ा बनता है सेंड से, इसमें सेंड इस्तमाल होती हैं. और एक 30 सेंटिमेटर का सेमी कुंड़क्टर वेफर बनाने के लिए, करिब 10,000 लिटर स्वक्ष पानी च़िये होता है, जो ग्लेश्टेर से पेगला गौग पानी होता ह |
| 396.04 -> 412.36 | और बड़े स्थर पर सेमीकंडॉक्टर वेफर वनाता हैं जो आगे जा कर के चिप्स बनती हैं और आईटी डपाटमेंट में यूज होती हैं इसलिए ये चेत्र चाइना की नजर में इस तरह से बसा हुगा हैं कि चाइना इसे छोडता नहीं हैं गलवान कुन्फलिक्ट हो, समझ पे आखें दिखाना हो चाइना इसलिए ही ये सब करता |
| 1161.0 -> 1173.0 | या दीजल पेट्रोल या तेल की एरर्जी पर चलने के बचाए, अगर हीट्रोजन से चलने लगजाए, तो अनंदा जाएगा. खई रही बात यूरेनिम की, यूरेनिम से भी न चलवा सकते हैं, |
| 536.36 -> 548.36 | नेदल्ल्ल्ल्ट्झो नाम इसका मतलबी होता है पानी में दूबा हुए लेंद नेदल्ल्ल्ल्ल्ट्झो एक आसी कन्तरी रही है जिसका एक चोथा इस्सा पानी में दूबा रहेता था |
