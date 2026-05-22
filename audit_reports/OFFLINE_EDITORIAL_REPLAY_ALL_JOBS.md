# Offline Editorial Replay Report

Scope: analytics/creator QA replay only. No video, ASR, FFmpeg, export, or server execution.
Jobs: all
Clip fixtures: 14
Creator QA rows: 50
Historical rejects: 41
Replayed rejects: 14
Regression counters: qa_changed=1

## Before/After Payoff
- No payoff deltas detected.

## QA Decision Comparison
- 23f21012-b025-4521-93c0-e13d15271343 313.58->344.58: reject ['no_hook_no_payoff'] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['weak_standalone_context'] removed=[]

## Continuation Risk
- No continuation-risk deltas detected.

## False Positive Watch
- No historically rejected clip would be approved by offline replay.

## Interrupted/Incomplete Runs
- 3f2a656f-e1ae-4b00-a582-068fc92d2e7c: upload=True asr_started=True asr_completed=True qa_log=True analytics_rows=0 zero_safe_rows=1
- ac65f75c-9f61-4ecd-8593-2c6a8918c41f: upload=True asr_started=True asr_completed=True qa_log=False analytics_rows=0 zero_safe_rows=0

## Fixture Detail
- 23f21012-b025-4521-93c0-e13d15271343 pre_creator_qa 156.08->192.46 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 23f21012-b025-4521-93c0-e13d15271343 pre_creator_qa 235.58->249.58 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 23f21012-b025-4521-93c0-e13d15271343 pre_creator_qa 0.0->34.08 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 23f21012-b025-4521-93c0-e13d15271343 pre_creator_qa 313.58->344.58 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 23f21012-b025-4521-93c0-e13d15271343 pre_creator_qa 34.08->78.08 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- e0926df0-8fdb-4441-9d95-af58ba1a3ec5 pre_creator_qa 63.44->89.44 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- e0926df0-8fdb-4441-9d95-af58ba1a3ec5 pre_creator_qa 232.8->249.8 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- e0926df0-8fdb-4441-9d95-af58ba1a3ec5 pre_creator_qa 90.44->134.8 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- e0926df0-8fdb-4441-9d95-af58ba1a3ec5 pre_creator_qa 0.0->49.12 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- e0926df0-8fdb-4441-9d95-af58ba1a3ec5 pre_creator_qa 148.8->203.66 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 5fb7dd32-fe17-4b6b-9c0e-01ac2b8ac3a3 pre_creator_qa 0.0->17.32 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 5fb7dd32-fe17-4b6b-9c0e-01ac2b8ac3a3 pre_creator_qa 97.32->109.32 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 5fb7dd32-fe17-4b6b-9c0e-01ac2b8ac3a3 pre_creator_qa 184.32->198.32 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 5fb7dd32-fe17-4b6b-9c0e-01ac2b8ac3a3 pre_creator_qa 205.32->241.32 old=reject replay=reject payoff=0.0->0.0 continuation=0.0->0.0
