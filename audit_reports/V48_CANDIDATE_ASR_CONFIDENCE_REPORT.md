# V48 Candidate ASR Confidence Report

Scope: offline diagnostics only. No production ASR, Creator QA, render, export, or frontend behavior changed.

## Summary
- job_id: 2efbe27a-4f64-41aa-9077-6f483e00fc4f
- asr_artifact: audit_reports\asr_segments_2efbe27a-4f64-41aa-9077-6f483e00fc4f_native_pre_retry.json
- total candidates: 6
- candidates rejected only due to global ASR: 0
- locally clean candidates: 3
- locally borderline candidates: 0
- candidates overlapping unstable windows: 3
- locally salvageable from global ASR gate: 0

## Chunk Context
- total chunks: 14
- clean chunks: 6
- borderline chunks: 0
- unstable chunks: 8

## Top Overlap Patterns
- replacement_artifact_collapse: 3
- clean: 3

## Candidate Table
| # | Window | Local ASR | Unstable Ratio | Score | QA Reasons | Global-ASR Only | Salvageable | Preview |
|---|---:|---|---:|---:|---|---|---|---|
| 1 | 589.36 -> 639.36 | unstable | 1.0 | 0 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | False | False | अगर बशा हुए है अगर बीच में याप को केनाल्स दिखने हैं नाले ताएप के चोड़ ये नाले नहीं ये समुद्र का पानी कवार बाड  |
| 2 | 350.36 -> 372.2 | unstable | 1.0 | 0 | asr_low_confidence, no_hook_no_payoff | False | False | और ये जो वेफर है, ये वेफर बनता है, वेफर याने की एक तोख्डा टाएप का. ये तोख्डा बनता है, सैंद से. इस में सैंद अस् |
| 3 | 396.04 -> 412.36 | unstable | 1.0 | 0 | asr_low_confidence, no_hook_no_payoff | False | False | अर बड़े अस्टर पर सेमिकंटर वेफर वनाता है जो आगे जागर के चिपस वनती हैं और आईटी धबाटमें युज अथी हैं यस लिये चेत्र |
| 4 | 1161.0 -> 1173.0 | clean | 0.0 | 100 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | False | False | या दीजल पेट्रोल या तेल की एरर्जी पर चलने के बचाए, अगर हीट्रोजन से चलने लगजाए, तो अनंदा जाएगा. खई रही बात यूरेन |
| 5 | 270.92 -> 283.76 | clean | 0.0 | 100 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | False | False | जितनी भी भिजली अप पादित होगी, सब ग्रीन अनर्जी होगी और इस तरे से पुरा एक नेट्राक तगया जाएगा जिसे दिल्ली से मुमभ |
| 6 | 536.36 -> 548.36 | clean | 0.0 | 100 | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | False | False | नेदल्ट्झो नाम इसका मतलबी होता है पानी में दूबा हुए लेंद नेदल्ट्झो एक आसी कन्तरी रही है जिसका एक चोथा इस्सा पान |
