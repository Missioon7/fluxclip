# V50 Repaired Text Replay Audit Report

Scope: offline replay only. This applies validated V49.9 exact-window repaired text to downstream scoring and Creator QA inputs for the current pre-Creator-QA finalists. No full video rerun, no Creator QA relaxation, and no ASR threshold relaxation were performed.

## Summary
- finalists analyzed: 6
- repaired_text_applied_count: 2
- no_hook_no_payoff_before: 6
- no_hook_no_payoff_after: 6
- creator_safe_before: 0
- creator_safe_after: 0
- predicted_final_clean: 4
- predicted_final_unstable: 2
- semantic_degraded_before/after: 2 / 2
- video_rerun_justified: True

## Per Finalist
| Window | Repaired Applied | Before Reasons | After Reasons | Before Local/Semantic | After Local/Semantic |
|---|---|---|---|---|---|
| 589.36 -> 639.36 | False | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | unstable / degraded_semantics | unstable / degraded_semantics |
| 350.36 -> 372.2 | True | asr_low_confidence, no_hook_no_payoff | no_hook_no_payoff, weak_standalone_context | unstable / borderline_semantics | clean / clean_semantics |
| 396.04 -> 412.36 | True | asr_low_confidence, no_hook_no_payoff | no_hook_no_payoff, weak_standalone_context | unstable / borderline_semantics | clean / clean_semantics |
| 1161.0 -> 1173.0 | False | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | clean / degraded_semantics | clean / degraded_semantics |
| 270.92 -> 283.76 | False | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | asr_low_confidence, no_hook_no_payoff, weak_standalone_context | unstable / clean_semantics | unstable / clean_semantics |
| 536.36 -> 548.36 | False | no_hook_no_payoff, weak_standalone_context | no_hook_no_payoff, weak_standalone_context | clean / clean_semantics | clean / clean_semantics |

## Repaired Windows
| Window | Repaired Preview |
|---|---|
| 350.36 -> 372.2 | और ये जो वेफर है, ये वेफर बनता है, वेफर याने की एक टुकड़ा टाइप का, ये टुकड़ा बनता है सेंड से, इसमें सेंड इस्तमाल होती हैं. और एक 30 सेंटिमेटर का सेमी कुंड़क्टर वेफर बनाने के लिए, करिब 10,000 लिटर स्वक्ष पानी च़िये होता ह |
| 396.04 -> 412.36 | और बड़े स्थर पर सेमीकंडॉक्टर वेफर वनाता हैं जो आगे जा कर के चिप्स बनती हैं और आईटी डपाटमेंट में यूज होती हैं इसलिए ये चेत्र चाइना की नजर में इस तरह से बसा हुगा हैं कि चाइना इसे छोडता नहीं हैं गलवान कुन्फलिक्ट हो, समझ पे  |
