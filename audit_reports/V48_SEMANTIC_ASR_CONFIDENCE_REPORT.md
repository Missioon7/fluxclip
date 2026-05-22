# V48 Semantic ASR Confidence Report

Scope: offline diagnostics only. No production ranking, ASR, Creator QA, frontend, render, export, or subtitle behavior changed.

## Summary
- job_id: 2efbe27a-4f64-41aa-9077-6f483e00fc4f
- asr_artifact: audit_reports\asr_segments_2efbe27a-4f64-41aa-9077-6f483e00fc4f_native_pre_retry.json
- chunk_source: recomputed
- chunk_source_artifact: audit_reports\asr_segments_2efbe27a-4f64-41aa-9077-6f483e00fc4f_native_pre_retry.json
- stability_source: production_helpers
- total candidates: 20
- final selected candidates: 6
- structurally clean candidates: 4
- semantically clean candidates: 1
- semantically borderline candidates: 2
- semantically degraded candidates: 17
- final semantically degraded candidates: 5
- clean structural windows with degraded semantics: 4
- final clean structural windows with degraded semantics: 2
- candidates rejected mainly due to semantic ASR degradation: 7
- candidates rejected mainly due to real editorial weakness: 2
- clean-structural no_hook_no_payoff likely semantic-degradation-driven: 4

## Distribution
- structural labels: {'clean': 4, 'unstable': 16}
- semantic labels: {'degraded_semantics': 17, 'clean_semantics': 1, 'borderline_semantics': 2}
- rejection drivers: {'asr_semantic_driven': 7, 'asr_semantic_risk': 9, 'editorial_driven': 2, 'not_rejected_or_unclear': 1, 'mixed_asr_semantic_and_editorial': 1}

## Recommendation
Next production patch should target ASR semantic confidence first: add deterministic semantic corruption scoring to candidate selection/QA metadata, keep ASR fail-closed, and use it before ranking promotes structurally clean but semantically degraded windows.

## Candidate Table
| # | Candidate | Window | Structural ASR | Semantic Label | Semantic Score | Final | Driver | Creator QA Reasons | Semantic Reasons | Preview |
|---|---:|---:|---|---|---:|---|---|---|---|---|
| 1 | 0 | 516.36 -> 536.36 | clean | degraded_semantics | 69 | False | asr_semantic_driven | no_hook_no_payoff, weak_standalone_context, continuation_leakage, story_editor_not_ok | suspicious_phonetic_tokens=3, malformed_hindi_tokens=3, broken_named_entities=2, technical_term_corruptions=1 | अब आपका नेदल्ल्लेंच का एक बड़ाही अच्छा मोडल है, जिस में नेदल्लेंच अपने आप बाडनी याने देता, पानी को बरनेदेता, और पानी की  |
| 2 | 1 | 589.36 -> 639.36 | unstable | degraded_semantics | 75 | True | asr_semantic_driven | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | replacement_chars=1, suspicious_phonetic_tokens=5, malformed_hindi_tokens=5 | अगर बशा हुए है अगर बीच में याप को केनाल्स दिखने हैं नाले ताएप के चोड़ ये नाले नहीं ये समुद्र का पानी कवार बाड के रूप में |
| 3 | 2 | 1161.0 -> 1173.0 | clean | degraded_semantics | 82 | True | asr_semantic_driven | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | suspicious_phonetic_tokens=4, malformed_hindi_tokens=4, technical_term_corruptions=4 | या दीजल पेट्रोल या तेल की एरर्जी पर चलने के बचाए, अगर हीट्रोजन से चलने लगजाए, तो अनंदा जाएगा. खई रही बात यूरेनिम की, यूर |
| 4 | 3 | 1.3 -> 14.86 | unstable | degraded_semantics | 100 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=8, malformed_hindi_tokens=7, broken_named_entities=3 | साथियो ज़ासकी आप जानते हैं के प्रदान मंतरी मुदी पाँज देषों की याप्र निकले हूँ हैं. मैंने पिषले विटिम बड़ाया था के पाँज त |
| 5 | 4 | 8.16 -> 47.76 | unstable | degraded_semantics | 36 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=2, broken_named_entities=2 | उकों सी बडील करने वाले हैं. जिस में विशेश योईग के बारे में हमने चच्चा करीती के योईग और भारत के बीश में कोंषी डील होईग है |
| 6 | 5 | 10.2 -> 47.76 | unstable | degraded_semantics | 41 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=2, malformed_hindi_tokens=1, broken_named_entities=2 | जिस में विशेश योईग के बारे में हमने चच्चा करीती के योईग और भारत के बीश में कोंषी डील होईग है आज़े या प्रदन मंट्री मुदि न |
| 7 | 6 | 77.76 -> 86.76 | unstable | degraded_semantics | 56 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=2, malformed_hindi_tokens=2, broken_named_entities=1, technical_term_corruptions=2 | दूनिया में चाईना ताईवान, सावदखोर्या जापान ये चार बड़े देश हैं, जो सम्यकन्ड़्टर चिप्स दूनिया में सपलाई करते हैं. |
| 8 | 7 | 77.76 -> 86.76 | unstable | degraded_semantics | 56 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=2, malformed_hindi_tokens=2, broken_named_entities=1, technical_term_corruptions=2 | दूनिया में चाईना ताईवान, सावदखोर्या जापान ये चार बड़े देश हैं, जो सम्यकन्ड़्टर चिप्स दूनिया में सपलाई करते हैं. |
| 9 | 8 | 146.76 -> 176.76 | unstable | degraded_semantics | 100 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=6, malformed_hindi_tokens=6, repeated_garbage_phrases=4 | यो उड़ाद कोद भी ज़गा अप आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवें़ |
| 10 | 9 | 185.76 -> 199.92 | unstable | degraded_semantics | 46 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=2, malformed_hindi_tokens=2, technical_term_corruptions=2 | हमारे यंजीनर्स को वो टेकनलोगी सिकाडो जिस से चिप्स बनती हैं अम अरे यंजीनर्स के साथ कुछ रिशच अद़बलप्में तोगी बैटरी कर सकें |
| 11 | 10 | 270.92 -> 283.76 | unstable | clean_semantics | 0 | True | editorial_driven | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | none | जितनी भी भिजली अप पादित होगी, सब ग्रीन अनर्जी होगी और इस तरे से पुरा एक नेट्राक तगया जाएगा जिसे दिल्ली से मुमभाईसे और बड |
| 12 | 11 | 292.06 -> 305.56 | unstable | borderline_semantics | 23 | False | not_rejected_or_unclear | none | suspicious_phonetic_tokens=1, malformed_hindi_tokens=1, technical_term_corruptions=1 | जिस में सेम्मिकन्टर का हब भी यहाप तभीर थएयार होगा जिस में नेदर लेंट समारे मदद करेगा तो एक बड़े डेल तो हमने ये करी हैं अब |
| 13 | 12 | 350.36 -> 372.2 | unstable | degraded_semantics | 80 | True | asr_semantic_driven | asr_low_confidence, no_hook_no_payoff | suspicious_phonetic_tokens=9, malformed_hindi_tokens=9, technical_term_corruptions=1 | और ये जो वेफर है, ये वेफर बनता है, वेफर याने की एक तोख्डा टाएप का. ये तोख्डा बनता है, सैंद से. इस में सैंद अस्तमाल होती  |
| 14 | 13 | 396.04 -> 412.36 | unstable | degraded_semantics | 75 | True | asr_semantic_driven | asr_low_confidence, no_hook_no_payoff | suspicious_phonetic_tokens=5, malformed_hindi_tokens=5, technical_term_corruptions=1 | अर बड़े अस्टर पर सेमिकंटर वेफर वनाता है जो आगे जागर के चिपस वनती हैं और आईटी धबाटमें युज अथी हैं यस लिये चेत्र चाइना की  |
| 15 | 14 | 407.36 -> 422.36 | unstable | borderline_semantics | 26 | False | editorial_driven | no_hook_no_payoff, weak_standalone_context | suspicious_phonetic_tokens=2, malformed_hindi_tokens=2 | गल्वान, कुन्फलिक्त हो, समय प्यांखे दिखाना हो, चाईना इस्टिये ही यह सब करता है. तिके, उसी तरह से, भारत चिवकी इस्पे एक लोंक |
| 16 | 15 | 516.36 -> 536.36 | clean | degraded_semantics | 69 | False | asr_semantic_driven | no_hook_no_payoff, weak_standalone_context, continuation_leakage, story_editor_not_ok | suspicious_phonetic_tokens=3, malformed_hindi_tokens=3, broken_named_entities=2, technical_term_corruptions=1 | अब आपका नेदल्ल्लेंच का एक बड़ाही अच्छा मोडल है, जिस में नेदल्लेंच अपने आप बाडनी याने देता, पानी को बरनेदेता, और पानी की  |
| 17 | 16 | 536.36 -> 548.36 | clean | degraded_semantics | 46 | True | asr_semantic_driven | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | suspicious_phonetic_tokens=2, malformed_hindi_tokens=2, broken_named_entities=2 | नेदल्ट्झो नाम इसका मतलबी होता है पानी में दूबा हुए लेंद नेदल्ट्झो एक आसी कन्तरी रही है जिसका एक चोथा इस्सा पानी में दूबा |
| 18 | 17 | 636.36 -> 672.36 | unstable | degraded_semantics | 100 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=11, malformed_hindi_tokens=11, repeated_garbage_phrases=3, technical_term_corruptions=1 | अवाप कहो थी कै है यह तेंकलोडी बारत क्या लेने गया था? जी हाँ, बारत भी अपने यह आपर यस तरे का पूरे एक सिस्टम बनारा हा आए, अ |
| 19 | 18 | 636.36 -> 672.36 | unstable | degraded_semantics | 100 | False | asr_semantic_risk | none | suspicious_phonetic_tokens=11, malformed_hindi_tokens=11, repeated_garbage_phrases=3, technical_term_corruptions=1 | अवाप कहो थी कै है यह तेंकलोडी बारत क्या लेने गया था? जी हाँ, बारत भी अपने यह आपर यस तरे का पूरे एक सिस्टम बनारा हा आए, अ |
| 20 | 19 | 811.36 -> 841.36 | unstable | degraded_semantics | 69 | False | mixed_asr_semantic_and_editorial | no_hook_no_payoff | replacement_chars=1, repeated_garbage_phrases=3, low_unique_token_ratio=0.15 | अब आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आ� |

## Structurally Clean But Semantically Degraded
- candidate 0 516.36 -> 536.36: score=69, final=False, driver=asr_semantic_driven, examples=तेकनोलोजी, नेदल्लेंच
- candidate 2 1161.0 -> 1173.0: score=82, final=True, driver=asr_semantic_driven, examples=एरर्जी, यूरेनिम, हीट्रोजन
- candidate 15 516.36 -> 536.36: score=69, final=False, driver=asr_semantic_driven, examples=तेकनोलोजी, नेदल्लेंच
- candidate 16 536.36 -> 548.36: score=46, final=True, driver=asr_semantic_driven, examples=नेदल्ट्झो
