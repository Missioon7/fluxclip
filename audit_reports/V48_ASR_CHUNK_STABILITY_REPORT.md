# V48 ASR Chunk Stability Report

Scope: offline longform Hindi/Hinglish ASR chunk stability audit only. No Whisper, FFmpeg, server, or production behavior changes.
Input artifact: audit_reports\asr_segments_cb7f65ba-222e-4e82-869f-57d399a3f146_native_pre_retry.json

## Summary
- total chunks: 14
- clean chunks: 6
- borderline chunks: 0
- unstable chunks: 8
- devanagari count: 8833
- mojibake marker count: 0
- replacement char count: 49
- global vs chunk mismatch: Chunk audit can preserve clean regions while retrying only unstable windows.

## Retry Recommended Windows
- 0.0 -> 230.0
- 330.0 -> 450.0
- 550.0 -> 1000.0
- 1320.0 -> 1440.0

## Preserved Clean Regions
- 220.0 -> 340.0
- 440.0 -> 560.0
- 990.0 -> 1110.0
- 1100.0 -> 1220.0
- 1210.0 -> 1330.0
- 1430.0 -> 1550.0

## Risky Collapsed Regions
- 0.0 -> 120.0 | replacement_artifact_collapse | collapse_score=27
- 110.0 -> 230.0 | local_repetition_collapse | collapse_score=36
- 330.0 -> 450.0 | replacement_artifact_collapse | collapse_score=17
- 550.0 -> 670.0 | replacement_artifact_collapse | collapse_score=26
- 660.0 -> 780.0 | replacement_artifact_collapse | collapse_score=49
- 770.0 -> 890.0 | replacement_artifact_collapse | collapse_score=100
- 880.0 -> 1000.0 | replacement_artifact_collapse | collapse_score=81
- 1320.0 -> 1440.0 | replacement_artifact_collapse | collapse_score=35

## Chunk Detail
### 0.0 -> 120.0
- stability_label: replacement_artifact_collapse
- retry_recommended: True
- segment_count: 11
- word_count: 175
- unique_token_ratio: 0.634
- top_token_ratio: 0.131
- repeated_bigram_ratio: 0.15
- repeated_trigram_ratio: 0.136
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.091
- devanagari_count: 734
- mojibake_marker_count: 0
- replacement_char_count: 2
- collapse_score: 27
- collapse_type: replacement_artifact_collapse
- preview_text: साथियो नमशकार. साथियो ज़ासकी आप जानते हैं के प्रदान मंतरी मुदी पाँज देषों की याप्र निकले हूँ हैं. मैंने पिषले विटिम बड़ाया था के पाँज तो देषों की याप्रा में, उकों सी बडील करने वाले हैं. जिस में विशेश योईग के बारे में हमने चच्चा करीती के योईग और भारत के बीश में कोंषी डील होईग है आ

### 110.0 -> 230.0
- stability_label: local_repetition_collapse
- retry_recommended: True
- segment_count: 6
- word_count: 115
- unique_token_ratio: 0.539
- top_token_ratio: 0.2
- repeated_bigram_ratio: 0.258
- repeated_trigram_ratio: 0.239
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 439
- mojibake_marker_count: 0
- replacement_char_count: 0
- collapse_score: 36
- collapse_type: local_repetition_collapse
- preview_text: यो उड़ाद कोद भी ज़गा अप आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवेंग़ा आप निवें़ अगर कर के था है के हमें चिप्स बना कर के दू ना बारत गया नेदलन्ज बारत नेदलन्ज से केता है के हमें वो मशिल्स दे दो जो चिप्स बनाती हैं हमारे यंजीनर्स को वो टेकनलोगी सिकाडो जिस से 

### 220.0 -> 340.0
- stability_label: clean
- retry_recommended: False
- segment_count: 17
- word_count: 215
- unique_token_ratio: 0.647
- top_token_ratio: 0.033
- repeated_bigram_ratio: 0.048
- repeated_trigram_ratio: 0.03
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 760
- mojibake_marker_count: 0
- replacement_char_count: 2
- collapse_score: 16
- collapse_type: none
- preview_text: तो लेरा अगा पर एक चोड़ासा एक पूरा चित्र बनाय जारा है जिसे एक तरीके से हम मिनी जापान कै सकते है जिसे जापान है बलको इसमाथ पूरा जापान ही निसमाथ है या आम्दाबात के साथ वेस्ट में एक जगा एकषार की लिए गये जो तीस कलोमेटर चोडी य बड़े यस तर पर सेमिकंटक्टर, चप्स अलग �alag और अग आप यटी के प्व

### 330.0 -> 450.0
- stability_label: replacement_artifact_collapse
- retry_recommended: True
- segment_count: 24
- word_count: 278
- unique_token_ratio: 0.522
- top_token_ratio: 0.065
- repeated_bigram_ratio: 0.156
- repeated_trigram_ratio: 0.11
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 1053
- mojibake_marker_count: 0
- replacement_char_count: 1
- collapse_score: 17
- collapse_type: replacement_artifact_collapse
- preview_text: तो जो सेमिकंटक्टर चिप्स बनाई जाती है, जो सेमिकंटक्टर वेफर से. और ये जो वेफर है, ये वेफर बनता है, वेफर याने की एक तोख्डा टाएप का. ये तोख्डा बनता है, सैंद से. इस में सैंद अस्तमाल होती है. अर एक ती सेंटिमिटर का सेमिकंटक्टर वेफर बनाने के लिए करी दस हजार लिटर सुक्ष पानी चाही होता है, 

### 440.0 -> 560.0
- stability_label: clean
- retry_recommended: False
- segment_count: 9
- word_count: 132
- unique_token_ratio: 0.682
- top_token_ratio: 0.061
- repeated_bigram_ratio: 0.112
- repeated_trigram_ratio: 0.062
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 751
- mojibake_marker_count: 0
- replacement_char_count: 0
- collapse_score: 0
- collapse_type: none
- preview_text: अपन ये रेने सास पातनर्षिप सेमिकंटर् सपलाई चेन सेमिकंटर् सपलाई चेन को फैसिलितेट करता है जापान ये रेने सास पातनर्षिप सेमिकंटर्टर सपलाई चेन, सेमिकंटर्टर सपलाई चेन को फैसिलितेट करता है, साथकोरी अएलेक्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट् ताईवान से, 

### 550.0 -> 670.0
- stability_label: replacement_artifact_collapse
- retry_recommended: True
- segment_count: 12
- word_count: 190
- unique_token_ratio: 0.558
- top_token_ratio: 0.095
- repeated_bigram_ratio: 0.134
- repeated_trigram_ratio: 0.12
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 750
- mojibake_marker_count: 0
- replacement_char_count: 2
- collapse_score: 26
- collapse_type: replacement_artifact_collapse
- preview_text: जी देखे एगो पहले मैं आपको यह देखा चुका हूं के यूरोप का यह चोता सा देशे नेदल लेंज यह तो अगर आप ग़द से देखोगे तो यह भी यसका मैप है अगर तो आप देखागा वन फोर्ट अरीया यह पानी में दूवावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावावाव

### 660.0 -> 780.0
- stability_label: replacement_artifact_collapse
- retry_recommended: True
- segment_count: 3
- word_count: 110
- unique_token_ratio: 0.564
- top_token_ratio: 0.191
- repeated_bigram_ratio: 0.232
- repeated_trigram_ratio: 0.222
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 355
- mojibake_marker_count: 0
- replacement_char_count: 2
- collapse_score: 49
- collapse_type: replacement_artifact_collapse
- preview_text: ये नदिया अप देखें तो तापी आरी है, नरमदा आरी है, माही आरी है, साबरमती है, भोगवा है, तीके और शेत्रूंजी है, ये भिकाडा है, और भुकु नी दिखेरी मुजे है। तो यह तो पर्ष्टन को नेदलन के तेकनलोगी का अच्टमाल करते हुए, हम फलड प्रूथ बुटर प्रूथ बनाएंगे, अगर तेकनलोगी हम को आगी भी किसी इजेश के कुन

### 770.0 -> 890.0
- stability_label: replacement_artifact_collapse
- retry_recommended: True
- segment_count: 3
- word_count: 87
- unique_token_ratio: 0.46
- top_token_ratio: 0.207
- repeated_bigram_ratio: 0.463
- repeated_trigram_ratio: 0.439
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 298
- mojibake_marker_count: 0
- replacement_char_count: 19
- collapse_score: 100
- collapse_type: replacement_artifact_collapse
- preview_text: अगुज्रात में जो ये गल्फव्खंबात में बनाने वाले हैं पानी की टेकनलोगी वाला ये से बोलते हैं कल पासार प्रोजेक ये तीस से चोथिस क्लोमिटर देम बनाएगा गल्फव्खंबात के पास बाइसो यसक्ष्वरे क्लोमिटर फ्रैष्वोटर लिजरवार बना अब आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको आपको

### 880.0 -> 1000.0
- stability_label: replacement_artifact_collapse
- retry_recommended: True
- segment_count: 4
- word_count: 76
- unique_token_ratio: 0.553
- top_token_ratio: 0.224
- repeated_bigram_ratio: 0.333
- repeated_trigram_ratio: 0.305
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 354
- mojibake_marker_count: 0
- replacement_char_count: 18
- collapse_score: 81
- collapse_type: replacement_artifact_collapse
- preview_text: एक लाक करोडो से उपर का अई लेए आप आप आप आप आप आ� आप आ� आ� आ� आ� आ� आ� आ� आ� आ� आ� आ� आ� आ� आ� आ� आ� � तो जो तो बगर बगर बगर बगर बगर बगर बगर बग तो इतना में आपको बताचुका अग़ा तुट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट्ट

### 990.0 -> 1110.0
- stability_label: clean
- retry_recommended: False
- segment_count: 6
- word_count: 166
- unique_token_ratio: 0.56
- top_token_ratio: 0.127
- repeated_bigram_ratio: 0.127
- repeated_trigram_ratio: 0.068
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 632
- mojibake_marker_count: 0
- replacement_char_count: 2
- collapse_score: 16
- collapse_type: none
- preview_text: इसके बाद तो समिकंटर्टर्टर्वाला बतादिया और फलर्ट तेकनालोगी फलर्ट से कैसे बच्छें बो बतादिया अप तीस्टी बडी चीस जो मुदिजी नेदलाईंसनो करने गये उस पर आईए एं। ग्रीन हीट्रोजन बारत ने अपने हैंक मिशन चलाया था, तो जो हाँर तेश में नेस्नल हीट्रोजन ग्रीन हीट्रोजन मिशन, जिसके तहाँ तम दीरे अपने 

### 1100.0 -> 1220.0
- stability_label: clean
- retry_recommended: False
- segment_count: 15
- word_count: 224
- unique_token_ratio: 0.554
- top_token_ratio: 0.085
- repeated_bigram_ratio: 0.087
- repeated_trigram_ratio: 0.05
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 834
- mojibake_marker_count: 0
- replacement_char_count: 0
- collapse_score: 0
- collapse_type: none
- preview_text: अगर उगर लिए तो आप दूगाँ बादियों तो आप दूगाँ तो आप दूगाँ तो आप दूगाँ तो आप दूगाँ तो आप दूगाँ तो आप दूगाँ तो आप अगर बडगर के काम कर रही है और एक हजार हीडूजन फूलिंग श्टेशन्स बनाचोखी है और एक मिल्यन जीरो एमिशन्स फूल्ट सेल एक्टरिक विकल्स भी बनाचोखी है जो दोगार तीस तक इंकी सड़कों पर आजा

### 1210.0 -> 1330.0
- stability_label: clean
- retry_recommended: False
- segment_count: 10
- word_count: 201
- unique_token_ratio: 0.652
- top_token_ratio: 0.104
- repeated_bigram_ratio: 0.152
- repeated_trigram_ratio: 0.123
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 710
- mojibake_marker_count: 0
- replacement_char_count: 0
- collapse_score: 10
- collapse_type: none
- preview_text: तेखे भारा जापान के साथ भी अच्छे ची डील्स कर रहा है, अप देखे रहे है, उसकारन भी है. अप नेशनल ग्रीन आईटोजन मिशन लेगर के आए थी जिस में हमारा उदेश लेगर के हम आने वाले समें लग बग दवलपिं ग्रीन आईटोजन प्रटक्षन केपिस्टी अप अग्टिस त्रीस फ्याम मिल्यन मेट्रिक तन की हैम आईटोजन केपिस्टी बनाने 

### 1320.0 -> 1440.0
- stability_label: replacement_artifact_collapse
- retry_recommended: True
- segment_count: 7
- word_count: 120
- unique_token_ratio: 0.658
- top_token_ratio: 0.142
- repeated_bigram_ratio: 0.202
- repeated_trigram_ratio: 0.173
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 462
- mojibake_marker_count: 0
- replacement_char_count: 1
- collapse_score: 35
- collapse_type: replacement_artifact_collapse
- preview_text: अगर बगर बगर बगर बगर बगर बगर बगर ब� अगर नावन या ब्लेक हैट्विजन के रहे दे थे जब यह विन देनर्ची अज़ शोलगण जी से करोगे तो ज़े ग्रीन हैट्विजन के लिए थे थे थे थे थे थे थे थे थे थे थे थे थे थे थे थे अदरबाद, अडीसा, कोलकता, असम, अदर प्रदेश, पंजामबे, यह 10 जगा प्रोज्यक्त चले रहे हैं, यह सब

### 1430.0 -> 1550.0
- stability_label: clean
- retry_recommended: False
- segment_count: 15
- word_count: 184
- unique_token_ratio: 0.679
- top_token_ratio: 0.109
- repeated_bigram_ratio: 0.136
- repeated_trigram_ratio: 0.118
- adjacent_duplicate_segment_count: 0
- short_fragment_ratio: 0.0
- devanagari_count: 701
- mojibake_marker_count: 0
- replacement_char_count: 0
- collapse_score: 10
- collapse_type: none
- preview_text: अप दूश्टेड है तेकनलोजी लेने में कि अगे तेकनलोजी है और हम वनना चाराई है आत मिरवर अमें ना बहार से खाना मगाना पडे, जो अमारे पह सफिष्ट्यन तबी होता ही है अद्रीया बाद्टागा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा लगा ल लेक्तरे लेक्र ज़ोड़ है, उस में व
