# V48 Clean Window Candidate Ranking Report

Scope: offline diagnostics only. No production ranking, Creator QA, ASR, render, export, frontend, or subtitle behavior changed.

## Summary
- job_id: 2efbe27a-4f64-41aa-9077-6f483e00fc4f
- asr_artifact: audit_reports\asr_segments_2efbe27a-4f64-41aa-9077-6f483e00fc4f_native_pre_retry.json
- total funnel candidates: 20
- clean-window candidates: 6
- unstable-window candidates: 14
- final selected candidates: 6
- final selected clean candidates: 3
- final selected unstable candidates: 3
- lost clean-window candidates: 3

## Clean Windows
- 220.0 -> 340.0
- 440.0 -> 560.0
- 990.0 -> 1110.0
- 1100.0 -> 1220.0
- 1210.0 -> 1330.0
- 1430.0 -> 1550.0

## Unstable / Retry Windows
- 0.0 -> 230.0
- 330.0 -> 450.0
- 550.0 -> 1000.0
- 1320.0 -> 1440.0

## Candidate Distribution
- funnel by region: {'clean': 6, 'unstable': 14}
- final by region: {'unstable': 3, 'clean': 3}
- lost clean filter decisions: {'dna_rejected': 2, 'accepted_pre_dedupe': 1}
- lost clean filter reasons: {'v10_v15_dna_gate': 2, 'passed_build_final_filters': 1}

## Recommendation
No production ranking patch is justified from this run alone.

## Funnel Candidates
| # | Region | Window | Initial | Final | Decision | Reason | Unstable Ratio | Preview |
|---|---|---:|---:|---:|---|---|---:|---|
| 0 | clean | 516.36 -> 536.36 | 62.0 | None | dna_rejected | v10_v15_dna_gate | 0.0 | अब आपका नेदल्ल्लेंच का एक बड़ाही अच्छा मोडल है, जिस में नेदल्लेंच अपने आप बाडनी याने देता, पानी को बरनेदेता, और पानी की  |
| 1 | unstable | 589.36 -> 639.36 | 62.0 | 181.0 | accepted | selected_after_dedupe | 1.0 | अगर बशा हुए है अगर बीच में याप को केनाल्स दिखने हैं नाले ताएप के चोड़ ये नाले नहीं ये समुद्र का पानी कवार बाड के रूप में |
| 2 | clean | 1161.0 -> 1173.0 | 51.0 | 162.0 | accepted | selected_after_dedupe | 0.0 | या दीजल पेट्रोल या तेल की एरर्जी पर चलने के बचाए, अगर हीट्रोजन से चलने लगजाए, तो अनंदा जाएगा. खई रही बात यूरेनिम की, यूर |
| 3 | unstable | 1.3 -> 14.86 | 43.0 | 150.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | साथियो ज़ासकी आप जानते हैं के प्रदान मंतरी मुदी पाँज देषों की याप्र निकले हूँ हैं. मैंने पिषले विटिम बड़ाया था के पाँज त |
| 4 | unstable | 8.16 -> 47.76 | 43.0 | 148.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | उकों सी बडील करने वाले हैं. जिस में विशेश योईग के बारे में हमने चच्चा करीती के योईग और भारत के बीश में कोंषी डील होईग है |
| 5 | unstable | 10.2 -> 47.76 | 43.0 | 146.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | जिस में विशेश योईग के बारे में हमने चच्चा करीती के योईग और भारत के बीश में कोंषी डील होईग है आज़े या प्रदन मंट्री मुदि न |
| 6 | unstable | 77.76 -> 86.76 | 43.0 | 148.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | दूनिया में चाईना ताईवान, सावदखोर्या जापान ये चार बड़े देश हैं, जो सम्यकन्ड़्टर चिप्स दूनिया में सपलाई करते हैं. |
| 7 | unstable | 77.76 -> 86.76 | 43.0 | 148.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | दूनिया में चाईना ताईवान, सावदखोर्या जापान ये चार बड़े देश हैं, जो सम्यकन्ड़्टर चिप्स दूनिया में सपलाई करते हैं. |
| 8 | unstable | 146.76 -> 176.76 | 43.0 | 134.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | यो उड़ाद कोद भी ज़गा अप आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवें़ |
| 9 | unstable | 185.76 -> 199.92 | 43.0 | 134.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | हमारे यंजीनर्स को वो टेकनलोगी सिकाडो जिस से चिप्स बनती हैं अम अरे यंजीनर्स के साथ कुछ रिशच अद़बलप्में तोगी बैटरी कर सकें |
| 10 | clean | 270.92 -> 283.76 | 43.0 | 144.0 | accepted | selected_after_dedupe | 0.0 | जितनी भी भिजली अप पादित होगी, सब ग्रीन अनर्जी होगी और इस तरे से पुरा एक नेट्राक तगया जाएगा जिसे दिल्ली से मुमभाईसे और बड |
| 11 | clean | 292.06 -> 305.56 | 43.0 | 140.0 | accepted_pre_dedupe | passed_build_final_filters | 0.0 | जिस में सेम्मिकन्टर का हब भी यहाप तभीर थएयार होगा जिस में नेदर लेंट समारे मदद करेगा तो एक बड़े डेल तो हमने ये करी हैं अब |
| 12 | unstable | 350.36 -> 372.2 | 43.0 | 160.0 | accepted | selected_after_dedupe | 1.0 | और ये जो वेफर है, ये वेफर बनता है, वेफर याने की एक तोख्डा टाएप का. ये तोख्डा बनता है, सैंद से. इस में सैंद अस्तमाल होती  |
| 13 | unstable | 396.04 -> 412.36 | 43.0 | 154.0 | accepted | selected_after_dedupe | 1.0 | अर बड़े अस्टर पर सेमिकंटर वेफर वनाता है जो आगे जागर के चिपस वनती हैं और आईटी धबाटमें युज अथी हैं यस लिये चेत्र चाइना की  |
| 14 | unstable | 407.36 -> 422.36 | 43.0 | 146.0 | duplicate_removed | overlap_or_near_start_duplicate | 1.0 | गल्वान, कुन्फलिक्त हो, समय प्यांखे दिखाना हो, चाईना इस्टिये ही यह सब करता है. तिके, उसी तरह से, भारत चिवकी इस्पे एक लोंक |
| 15 | clean | 516.36 -> 536.36 | 43.0 | None | dna_rejected | v10_v15_dna_gate | 0.0 | अब आपका नेदल्ल्लेंच का एक बड़ाही अच्छा मोडल है, जिस में नेदल्लेंच अपने आप बाडनी याने देता, पानी को बरनेदेता, और पानी की  |
| 16 | clean | 536.36 -> 548.36 | 43.0 | 152.0 | accepted | selected_after_dedupe | 0.0 | नेदल्ट्झो नाम इसका मतलबी होता है पानी में दूबा हुए लेंद नेदल्ट्झो एक आसी कन्तरी रही है जिसका एक चोथा इस्सा पानी में दूबा |
| 17 | unstable | 636.36 -> 672.36 | 43.0 | 152.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | अवाप कहो थी कै है यह तेंकलोडी बारत क्या लेने गया था? जी हाँ, बारत भी अपने यह आपर यस तरे का पूरे एक सिस्टम बनारा हा आए, अ |
| 18 | unstable | 636.36 -> 672.36 | 43.0 | 152.0 | accepted_pre_dedupe | passed_build_final_filters | 1.0 | अवाप कहो थी कै है यह तेंकलोडी बारत क्या लेने गया था? जी हाँ, बारत भी अपने यह आपर यस तरे का पूरे एक सिस्टम बनारा हा आए, अ |
| 19 | unstable | 811.36 -> 841.36 | 43.0 | None | quality_rejected | bad_transcript_clip | 1.0 | अब आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आ� |

## Final Pre-Creator-QA Candidates
| # | Region | Window | Score | QA Reasons | Unstable Ratio | Preview |
|---|---|---:|---:|---|---:|---|
| 1 | unstable | 589.36 -> 639.36 | 181 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | 1.0 | अगर बशा हुए है अगर बीच में याप को केनाल्स दिखने हैं नाले ताएप के चोड़ ये नाले नहीं ये समुद्र का पानी कवार बाड के रूप में |
| 2 | unstable | 350.36 -> 372.2 | 160 | asr_low_confidence, no_hook_no_payoff | 1.0 | और ये जो वेफर है, ये वेफर बनता है, वेफर याने की एक तोख्डा टाएप का. ये तोख्डा बनता है, सैंद से. इस में सैंद अस्तमाल होती  |
| 3 | unstable | 396.04 -> 412.36 | 154 | asr_low_confidence, no_hook_no_payoff | 1.0 | अर बड़े अस्टर पर सेमिकंटर वेफर वनाता है जो आगे जागर के चिपस वनती हैं और आईटी धबाटमें युज अथी हैं यस लिये चेत्र चाइना की  |
| 4 | clean | 1161.0 -> 1173.0 | 162 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | 0.0 | या दीजल पेट्रोल या तेल की एरर्जी पर चलने के बचाए, अगर हीट्रोजन से चलने लगजाए, तो अनंदा जाएगा. खई रही बात यूरेनिम की, यूर |
| 5 | clean | 270.92 -> 283.76 | 144 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | 0.0 | जितनी भी भिजली अप पादित होगी, सब ग्रीन अनर्जी होगी और इस तरे से पुरा एक नेट्राक तगया जाएगा जिसे दिल्ली से मुमभाईसे और बड |
| 6 | clean | 536.36 -> 548.36 | 152 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | 0.0 | नेदल्ट्झो नाम इसका मतलबी होता है पानी में दूबा हुए लेंद नेदल्ट्झो एक आसी कन्तरी रही है जिसका एक चोथा इस्सा पानी में दूबा |
