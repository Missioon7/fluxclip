# FluxClip ASR Decision Memo - 2026-05-20

## Scope

This memo records the completed faster-whisper Hindi/Hinglish ASR research checkpoint for FluxClip.

No production ASR integration is approved from these results. The current production ASR path should remain stable and unchanged.

## Matrix Results

| Config | Status | Quality / Output | Decision |
| --- | --- | --- | --- |
| `language="hi"`, `vad_filter=False`, `compute_type="int8_float16"`, 600s | Stable run | `quality=6`; catastrophic Hindi collapse; garbled preview | Reject |
| `language=None`, `vad_filter=False`, `compute_type="int8_float16"`, 600s | Stable run | `quality=31`; detected English; semantic English output | Research-only semantic candidate |
| `language="hi"`, `vad_filter=True`, `compute_type="int8_float16"`, 600s | One successful run, rerun unstable | `quality~46` once; best Hindi candidate by score, but native abort on rerun | Reject for production |
| `language=None`, `vad_filter=True`, `compute_type="int8_float16"`, 600s | Stable run | `quality=46`; detected English; semantic output, not Hindi/Hinglish fidelity | Best stable research-only fallback |
| `language="hi"`, `vad_filter=True`, `compute_type="int8"`, 600s | Too slow / unstable | Stopped after extended runtime | Reject |
| `language="hi"`, `vad_filter=True`, `compute_type="int8_float16"`, 60s | Native abort | No reliable result | Reject |
| `language="hi"`, `vad_filter=True`, `compute_type="int8_float16"`, 120s | Native abort | No reliable result | Reject |
| `language=None`, `vad_filter=True`, `compute_type="int8_float16"`, 120s | Stable run | detected English; `quality=46`; coherent semantic English | Research-only semantic candidate |
| `language="hi"`, `beam_size=5`, `vad_filter=False`, `compute_type="int8_float16"`, 60s | Native abort | Forced Hindi crashes without VAD | Reject |
| `language="hi"`, `beam_size=5`, `vad_filter=True`, `compute_type="int8"`, 60s CUDA | Native abort | `int8` does not avoid crash | Reject |
| `language="hi"`, `beam_size=5`, `vad_filter=True`, `compute_type="int8"`, 60s CPU | Too slow | Exceeded practical runtime | Reject |
| `language="hi"`, `beam_size=1`, `vad_filter=False`, `compute_type="int8_float16"`, 10s CUDA | Printed empty result, then native abort | `detected_language=hi`; `raw_segments=0`; empty preview | Reject |
| `language="hi"`, `beam_size=1`, `vad_filter=False`, `compute_type="int8"`, 10s CUDA | Printed empty result, then native abort | `detected_language=hi`; `raw_segments=0`; empty preview | Reject |
| `language="hi"`, `beam_size=1`, `vad_filter=False`, `compute_type="int8"`, 10s CPU | Completed | Took about 274s for 10s audio; zero segments | Reject for practicality |

## Final Decision

Do not integrate forced-Hindi faster-whisper into production on this machine.

The forced `language="hi"` path is blocked by native instability on CUDA and unusable runtime on CPU. The crash persists with:

- 10s samples
- `beam_size=1`
- `vad_filter=False`
- `compute_type="int8_float16"`
- `compute_type="int8"`

This means the failure is not isolated to long audio, beam search size, VAD, or float16 compute alone.

## Stable Semantic Fallback Candidate

The only stable faster-whisper candidate from this checkpoint is:

```text
language=None
vad_filter=True
compute_type=int8_float16
device=cuda
```

This path produced coherent semantic English output and remained stable in controlled probes.

It is not a Hindi/Hinglish fidelity solution. It may be useful later as a research-only semantic fallback for clip understanding, but it should not replace the production ASR transcript.

## Why The Hindi Path Is Blocked

Forced Hindi decode currently fails the stability requirement:

- CUDA native-aborts even on 10s input.
- Lowering `beam_size` to 1 does not prevent the abort.
- Disabling faster-whisper VAD does not prevent the abort.
- Switching CUDA compute to `int8` does not prevent the abort.
- CPU avoids the CUDA abort but is too slow and produced zero segments on the 10s probe.

The best-scoring forced-Hindi result is therefore not production-safe.

## Future Options

The next research path should avoid forced Hindi on the current faster-whisper CUDA stack until the runtime is changed or isolated.

Recommended future options:

- External VAD pre-split before non-forced faster-whisper decode.
- Retry a different faster-whisper / CTranslate2 version later.
- Try whisper.cpp or another local Whisper runtime later.
- Try faster-whisper `large-v3-turbo` later if available and stable on this machine.
- Evaluate a cloud ASR option later for Hindi/Hinglish fidelity.
- Keep the current production ASR path stable for now.

## What Must Not Be Changed Yet

Do not:

- Integrate forced-Hindi faster-whisper into production.
- Modify production `transcribe()` behavior for faster-whisper.
- Add automatic faster-whisper retry selection.
- Change ASR rejection thresholds based on the unstable Hindi result.
- Replace current production ASR with semantic English fallback output.
- Run full 1h production ASR as part of this research checkpoint.
- Patch FFmpeg, crop, frontend, server flow, or export logic for this ASR issue.

## Production Files Intentionally Untouched

The following production files are intentionally not part of this ASR decision patch:

- `asr_engine.py`
- `pipeline_runner.py`
- `caption_engine.py`
- `clip_generator.py`
- `visual_engine.py`
- `server.py`

The only artifact added by this checkpoint is this memo:

```text
audit_reports/ASR_DECISION_2026_05_20.md
```
