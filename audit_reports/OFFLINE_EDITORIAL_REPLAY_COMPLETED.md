# Offline Editorial Replay Report

Scope: analytics/creator QA replay only. No video, ASR, FFmpeg, export, or server execution.
Jobs: all
Clip fixtures: 45
Creator QA rows: 50
Historical rejects: 41
Replayed rejects: 35
Regression counters: payoff_changed=4, possible_new_rejection=35, qa_changed=35

## Before/After Payoff
- 2ac63a4a-9a9c-4b60-b930-1b12a289bac3 44.4->87.4: payoff_bonus 0.0 -> 7.0 v43 0.0 -> 0.0 v44 0.0 -> 0.0 confidence=none
- ab620f35-1874-49ed-a711-ad8ecffa380f 44.4->87.4: payoff_bonus 0.0 -> 7.0 v43 0.0 -> 0.0 v44 0.0 -> 0.0 confidence=none
- 8297786b-93e7-463f-9b70-29d3e0adb07f 89.4->118.0: payoff_bonus 7.0 -> 0.0 v43 0.0 -> 0.0 v44 0.0 -> 0.0 confidence=none
- fc4dd8d6-f81d-46ca-869b-3e07fb2c4aae 89.4->118.0: payoff_bonus 7.0 -> 0.0 v43 0.0 -> 0.0 v44 0.0 -> 0.0 confidence=none

## QA Decision Comparison
- 7cb9834e-c5bf-44b2-ae90-d636a7cc2434 83.64->99.64: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 7cb9834e-c5bf-44b2-ae90-d636a7cc2434 0.0->30.0: approve [] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['no_hook_no_payoff', 'weak_standalone_context'] removed=[]
- 06617e6d-7f09-40c8-abbb-7ea1532e839c 83.64->99.64: approve [] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['no_hook_no_payoff', 'weak_standalone_context'] removed=[]
- 357adb6d-f6cc-47af-a412-dc770fd82d29 83.64->99.64: approve [] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['no_hook_no_payoff', 'weak_standalone_context'] removed=[]
- a637fe15-7070-4129-9c5d-f75c7ff30c3c 83.64->99.64: approve [] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['no_hook_no_payoff', 'weak_standalone_context'] removed=[]
- 593ad2b7-0507-4866-bc43-281f069efaac 83.64->99.64: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- b83018af-1b9b-4254-95db-9d36224b5103 83.64->99.64: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- a0af728d-1587-46fd-8c38-f6209c168031 83.64->99.64: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 8f4b69eb-9dfd-4685-9f6d-3612201df1c7 83.64->99.64: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 0bc03658-7799-4482-b3c9-1a6e2b1ebb64 83.64->99.64: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 897ce723-9d02-40e7-8dce-062b4a62411d 7.56->22.76: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 4eb26efd-8793-44de-bcb9-19a36fffe2c0 60.0->73.0: approve [] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['no_hook_no_payoff', 'weak_standalone_context'] removed=[]
- 3cf591c1-e8e7-4fb0-b352-25cc85ffaadc 60.0->73.0: approve [] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['no_hook_no_payoff', 'weak_standalone_context'] removed=[]
- 35693927-b0c3-494e-8777-f690458afaf4 7.56->22.76: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- c0fe51da-2bb2-4728-b3f3-214f01731b2f 60.0->73.0: approve [] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['no_hook_no_payoff', 'weak_standalone_context'] removed=[]
- 74a8657e-a4af-4f00-9eb3-0692075f56f2 60.0->73.0: approve [] -> reject ['no_hook_no_payoff', 'weak_standalone_context'] added=['no_hook_no_payoff', 'weak_standalone_context'] removed=[]
- 2ac63a4a-9a9c-4b60-b930-1b12a289bac3 44.4->87.4: approve [] -> reject ['weak_standalone_context'] added=['weak_standalone_context'] removed=[]
- ab620f35-1874-49ed-a711-ad8ecffa380f 44.4->87.4: approve [] -> reject ['weak_standalone_context'] added=['weak_standalone_context'] removed=[]
- 8297786b-93e7-463f-9b70-29d3e0adb07f 89.4->118.0: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 8297786b-93e7-463f-9b70-29d3e0adb07f 0.0->32.6: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- fc4dd8d6-f81d-46ca-869b-3e07fb2c4aae 89.4->118.0: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- fc4dd8d6-f81d-46ca-869b-3e07fb2c4aae 0.0->32.6: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 392f3f35-d20a-4d61-9104-98b8c5a032f8 0.0->14.3: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f 221.82->239.58: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f 299.84->319.68: approve [] -> reject ['weak_continuation_start'] added=['weak_continuation_start'] removed=[]
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f 23.88->38.4: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f 86.94->109.06: approve [] -> reject ['weak_continuation_start', 'no_hook_no_payoff'] added=['no_hook_no_payoff', 'weak_continuation_start'] removed=[]
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f 175.5->201.44: approve [] -> reject ['weak_continuation_start', 'no_hook_no_payoff'] added=['no_hook_no_payoff', 'weak_continuation_start'] removed=[]
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f 0.0->14.32: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 12d00cc4-e601-457d-9614-dc443364ac71 221.82->239.58: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 12d00cc4-e601-457d-9614-dc443364ac71 299.84->319.68: approve [] -> reject ['weak_continuation_start'] added=['weak_continuation_start'] removed=[]
- 12d00cc4-e601-457d-9614-dc443364ac71 23.88->38.4: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]
- 12d00cc4-e601-457d-9614-dc443364ac71 86.94->109.06: approve [] -> reject ['weak_continuation_start', 'no_hook_no_payoff'] added=['no_hook_no_payoff', 'weak_continuation_start'] removed=[]
- 12d00cc4-e601-457d-9614-dc443364ac71 175.5->201.44: approve [] -> reject ['weak_continuation_start', 'no_hook_no_payoff'] added=['no_hook_no_payoff', 'weak_continuation_start'] removed=[]
- 12d00cc4-e601-457d-9614-dc443364ac71 0.0->14.32: approve [] -> reject ['no_hook_no_payoff'] added=['no_hook_no_payoff'] removed=[]

## Continuation Risk
- No continuation-risk deltas detected.

## False Positive Watch
- No historically rejected clip would be approved by offline replay.

## Interrupted/Incomplete Runs
- 23f21012-b025-4521-93c0-e13d15271343: upload=True asr_started=True asr_completed=True qa_log=True analytics_rows=0 zero_safe_rows=1
- 3f2a656f-e1ae-4b00-a582-068fc92d2e7c: upload=True asr_started=True asr_completed=True qa_log=True analytics_rows=0 zero_safe_rows=1
- 5fb7dd32-fe17-4b6b-9c0e-01ac2b8ac3a3: upload=True asr_started=True asr_completed=True qa_log=True analytics_rows=0 zero_safe_rows=1
- ac65f75c-9f61-4ecd-8593-2c6a8918c41f: upload=True asr_started=True asr_completed=True qa_log=False analytics_rows=0 zero_safe_rows=0
- e0926df0-8fdb-4441-9d95-af58ba1a3ec5: upload=True asr_started=True asr_completed=True qa_log=True analytics_rows=0 zero_safe_rows=1

## Fixture Detail
- 7cb9834e-c5bf-44b2-ae90-d636a7cc2434 completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 7cb9834e-c5bf-44b2-ae90-d636a7cc2434 completed 0.0->30.0 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 06617e6d-7f09-40c8-abbb-7ea1532e839c completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 357adb6d-f6cc-47af-a412-dc770fd82d29 completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- a637fe15-7070-4129-9c5d-f75c7ff30c3c completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 593ad2b7-0507-4866-bc43-281f069efaac completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- b83018af-1b9b-4254-95db-9d36224b5103 completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- a0af728d-1587-46fd-8c38-f6209c168031 completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 8f4b69eb-9dfd-4685-9f6d-3612201df1c7 completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 0bc03658-7799-4482-b3c9-1a6e2b1ebb64 completed 83.64->99.64 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 897ce723-9d02-40e7-8dce-062b4a62411d completed 7.56->22.76 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 4eb26efd-8793-44de-bcb9-19a36fffe2c0 completed 60.0->73.0 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 3cf591c1-e8e7-4fb0-b352-25cc85ffaadc completed 60.0->73.0 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 35693927-b0c3-494e-8777-f690458afaf4 completed 7.56->22.76 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- c0fe51da-2bb2-4728-b3f3-214f01731b2f completed 60.0->73.0 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 74a8657e-a4af-4f00-9eb3-0692075f56f2 completed 60.0->73.0 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 2ac63a4a-9a9c-4b60-b930-1b12a289bac3 completed 44.4->87.4 old=approve replay=reject payoff=0.0->7.0 continuation=0.0->0.0
- ab620f35-1874-49ed-a711-ad8ecffa380f completed 44.4->87.4 old=approve replay=reject payoff=0.0->7.0 continuation=0.0->0.0
- 8297786b-93e7-463f-9b70-29d3e0adb07f completed 38.3->93.7 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- 8297786b-93e7-463f-9b70-29d3e0adb07f completed 89.4->118.0 old=approve replay=reject payoff=7.0->0.0 continuation=0.0->0.0
- 8297786b-93e7-463f-9b70-29d3e0adb07f completed 0.0->32.6 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- fc4dd8d6-f81d-46ca-869b-3e07fb2c4aae completed 38.3->93.7 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- fc4dd8d6-f81d-46ca-869b-3e07fb2c4aae completed 89.4->118.0 old=approve replay=reject payoff=7.0->0.0 continuation=0.0->0.0
- fc4dd8d6-f81d-46ca-869b-3e07fb2c4aae completed 0.0->32.6 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 392f3f35-d20a-4d61-9104-98b8c5a032f8 completed 44.4->87.4 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- 392f3f35-d20a-4d61-9104-98b8c5a032f8 completed 93.7->118.0 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- 392f3f35-d20a-4d61-9104-98b8c5a032f8 completed 0.0->14.3 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- f05d00d4-5e5c-4115-9c47-3fca1e07fed6 completed 44.4->87.4 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- f05d00d4-5e5c-4115-9c47-3fca1e07fed6 completed 93.7->118.0 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- ab40268e-89e3-414f-9a2a-f78142904d4d completed 93.7->118.0 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- bb46e980-0381-44c9-abc9-82c15fd840fe completed 93.7->118.0 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- d1806733-8a65-473b-b7da-935778dcf03a completed 93.7->118.0 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- cbc85323-c416-42fb-a9f2-7e1b12046137 completed 93.74->117.74 old=approve replay=approve payoff=7.0->7.0 continuation=0.0->0.0
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f completed 221.82->239.58 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f completed 299.84->319.68 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f completed 23.88->38.4 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f completed 86.94->109.06 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f completed 175.5->201.44 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- cd1ae9f8-d99e-4009-b500-43d557fd4d1f completed 0.0->14.32 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 12d00cc4-e601-457d-9614-dc443364ac71 completed 221.82->239.58 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 12d00cc4-e601-457d-9614-dc443364ac71 completed 299.84->319.68 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 12d00cc4-e601-457d-9614-dc443364ac71 completed 23.88->38.4 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 12d00cc4-e601-457d-9614-dc443364ac71 completed 86.94->109.06 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 12d00cc4-e601-457d-9614-dc443364ac71 completed 175.5->201.44 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
- 12d00cc4-e601-457d-9614-dc443364ac71 completed 0.0->14.32 old=approve replay=reject payoff=0.0->0.0 continuation=0.0->0.0
