# V49.8 Targeted ASR Repair Replay Audit Report

Scope: offline replay only. The repair layer is targeted to production-unstable windows and remains fail-closed: it does not mark repaired windows available, does not substitute export text, and does not alter Creator QA.

## Summary
- job_id: 2efbe27a-4f64-41aa-9077-6f483e00fc4f
- replayable candidates: 17
- current finalists quarantined: 4
- repair attempted unstable candidates: 15
- repair improved candidates: 11
- repair label improved candidates: 11
- degraded before/after repair: 9 / 1
- repaired window available candidates: 0
- repair export safe candidates: 0
- predicted final clean/unstable after fail-closed repair: 2 / 0
- semantic degraded finalists increase: False
- unstable garbage export risk: False

## Corruption Patterns
| Pattern | Count |
|---|---:|
| `सम्यकन्ड़्टर|सेमिकंटर्टर|सेमिकंटर|सेमिकंटक्टर|सेम्मिकन्टर|सेमिकंटर्टर्टर्वाला -> सेमीकंडक्टर` | 5 |
| `तेंकलोडी|तेकनोलोजी|टेकनलोगी|टेकनलोडी -> टेक्नोलॉजी` | 4 |
| `प्रदान\s+मंतरी|प्रदन\s+मंट्री -> प्रधानमंत्री` | 3 |
| `देषों -> देशों` | 2 |
| `पाँज -> पांच` | 2 |
| `याप्रा? -> यात्रा` | 2 |
| `नेदल्ट्झो|नेदल्लेंच|नेदलन्ज|नेदर\s+लेंज|नेदल\s+लेंज|नेदलाईंसनो -> नीदरलैंड्स` | 2 |
| `मुदी -> मोदी` | 1 |
| `अस्तमाल|अच्टमाल -> इस्तेमाल` | 1 |
| `चिपस -> चिप्स` | 1 |

## Quarantined Unstable Finalists
| Candidate | Window | Before | After | Improved | Export Safe | Reasons |
|---:|---|---|---|---|---|---|
| 1 | 589.36 -> 639.36 | clean_semantics:0 | clean_semantics:0 | False | False | not_export_safe_without_audio_backed_repair |
| 10 | 270.92 -> 283.76 | clean_semantics:0 | clean_semantics:0 | False | False | not_export_safe_without_audio_backed_repair |
| 12 | 350.36 -> 372.2 | borderline_semantics:8 | clean_semantics:0 | True | False | known_term_replacements=2, semantic_score_delta=8, not_export_safe_without_audio_backed_repair |
| 13 | 396.04 -> 412.36 | borderline_semantics:8 | clean_semantics:0 | True | False | known_term_replacements=2, semantic_score_delta=8, not_export_safe_without_audio_backed_repair |

## Label Improvements
| Candidate | Window | Before | After | Repaired Text Preview |
|---:|---|---|---|---|
| 3 | 1.3 -> 14.86 | degraded_semantics:44 | clean_semantics:0 | साथियो ज़ासकी आप जानते हैं के प्रधानमंत्री मोदी पांच देशों की यात्रा निकले हूँ हैं. मैंने पिषले विटिम बड़ाया था के पांच तो देशों की यात्रा में, उकों सी बडील करन |
| 4 | 8.16 -> 47.76 | degraded_semantics:16 | clean_semantics:0 | उकों सी बडील करने वाले हैं. जिस में विशेश योईग के बारे में हमने चच्चा करीती के योईग और भारत के बीश में कोंषी डील होईग है आज़े या प्रधानमंत्री मुदि नीदरलैंड्स के |
| 5 | 10.2 -> 47.76 | degraded_semantics:24 | clean_semantics:0 | जिस में विशेश योईग के बारे में हमने चच्चा करीती के योईग और भारत के बीश में कोंषी डील होईग है आज़े या प्रधानमंत्री मुदि नीदरलैंड्स के याट्रापर गयूग हैं यह ज़ाँ प |
| 6 | 77.76 -> 86.76 | degraded_semantics:16 | borderline_semantics:8 | दूनिया में चाईना ताईवान, सावदखोर्या जापान ये चार बड़े देश हैं, जो सेमीकंडक्टर चिप्स दूनिया में सपलाई करते हैं. |
| 7 | 77.76 -> 86.76 | degraded_semantics:16 | borderline_semantics:8 | दूनिया में चाईना ताईवान, सावदखोर्या जापान ये चार बड़े देश हैं, जो सेमीकंडक्टर चिप्स दूनिया में सपलाई करते हैं. |
| 9 | 185.76 -> 199.92 | degraded_semantics:16 | clean_semantics:0 | हमारे यंजीनर्स को वो टेक्नोलॉजी सिकाडो जिस से चिप्स बनती हैं अम अरे यंजीनर्स के साथ कुछ रिशच अद़बलप्में तोगी बैटरी कर सकें उनो ने कहा है नेदल लन्स ने कि नहीं कि |
| 11 | 292.06 -> 305.56 | borderline_semantics:8 | clean_semantics:0 | जिस में सेमीकंडक्टर का हब भी यहाप तभीर थएयार होगा जिस में नेदर लेंट समारे मदद करेगा तो एक बड़े डेल तो हमने ये करी हैं अब आप ख़ेंगे के बही ये चिप्स के बारे में औ |
| 12 | 350.36 -> 372.2 | borderline_semantics:8 | clean_semantics:0 | और ये जो वेफर है, ये वेफर बनता है, वेफर याने की एक तोख्डा टाएप का. ये तोख्डा बनता है, सैंद से. इस में सैंद इस्तेमाल होती है. अर एक ती सेंटिमिटर का सेमीकंडक्टर व |
| 13 | 396.04 -> 412.36 | borderline_semantics:8 | clean_semantics:0 | अर बड़े अस्टर पर सेमीकंडक्टर वेफर वनाता है जो आगे जागर के चिप्स वनती हैं और आईटी धबाटमें युज अथी हैं यस लिये चेत्र चाइना की नजर में यस तराए से बसा उगाए के चाइना |
| 17 | 636.36 -> 672.36 | degraded_semantics:44 | clean_semantics:0 | अवाप कहो थी कै है यह टेक्नोलॉजी बारत क्या लेने गया था? जी हाँ, बारत भी अपने यह आपर यस तरे का पूरे एक सिस्टम बनारा हा आए, अगर बाड़ लोगा लोगा लो... |
| 18 | 636.36 -> 672.36 | degraded_semantics:44 | clean_semantics:0 | अवाप कहो थी कै है यह टेक्नोलॉजी बारत क्या लेने गया था? जी हाँ, बारत भी अपने यह आपर यस तरे का पूरे एक सिस्टम बनारा हा आए, अगर बाड़ लोगा लोगा लो... |

## Design
- remove replacement characters
- collapse repeated token runs
- collapse extreme repeated Devanagari characters
- replace narrow known corrupt Hindi/Hinglish terms

## Safety
- does not relax ASR stability thresholds
- does not set repaired_window_available without audio-backed repair
- does not substitute export text
- does not change Creator QA
- does not touch frontend/render/export/subtitle
