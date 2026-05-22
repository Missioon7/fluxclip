# V49 ASR Stability Parity Report

Scope: offline audit only. No production, Creator QA, frontend, render, export, subtitle, or video rerun changes.

## Summary
- job_id: 2efbe27a-4f64-41aa-9077-6f483e00fc4f
- asr_artifact: audit_reports\asr_segments_2efbe27a-4f64-41aa-9077-6f483e00fc4f_native_pre_retry.json
- production chunk size/overlap: 120.0 / 10.0
- audit chunk size/overlap: 120.0 / 10.0
- total final candidates: 6
- production logged vs recomputed mismatches: 0
- production vs audit label mismatches: 0
- production vs audit ratio mismatches: 0
- mismatch reasons: {'matched': 6}

## Root Cause
Semantic ASR audit local stability now uses the canonical production helpers. Historical mismatches came from audit_reports/v48_asr_chunk_stability_audit.py using audit-only metrics such as content-token filtering and different replacement-character accounting. This parity check compares production score_breakdown against the patched semantic audit path.

## Candidate Parity
| # | Window | Prod Logged | Prod Recomputed | Audit Recomputed | Prod Ratio | Audit Ratio | Reason |
|---:|---|---|---|---|---:|---:|---|
| 1 | 589.36 -> 639.36 | unstable | unstable | unstable | 1.0 | 1.0 | matched |
| 2 | 350.36 -> 372.2 | unstable | unstable | unstable | 1.0 | 1.0 | matched |
| 3 | 396.04 -> 412.36 | unstable | unstable | unstable | 1.0 | 1.0 | matched |
| 4 | 1161.0 -> 1173.0 | clean | clean | clean | 0.0 | 0.0 | matched |
| 5 | 270.92 -> 283.76 | unstable | unstable | unstable | 1.0 | 1.0 | matched |
| 6 | 536.36 -> 548.36 | clean | clean | clean | 0.0 | 0.0 | matched |
