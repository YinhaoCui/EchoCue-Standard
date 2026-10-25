# Meeting assistance

These features use the existing transcription, answer jobs, provider accounting and encrypted session storage. All automatic features start off. Manual answers still run independently and can overlap.

## Automatic answers

Settings → Meeting assistance offers Off, On questions, and After each pause, with Fast / Balanced / Relaxed pacing. Switch Question mode to Quick Q&A to use automatic answering; Long question always waits for an explicit Answer.

The application waits for finalized transcription and a quiet window (1 / 1.5 / 2.5 seconds), then creates a normal answer task. The minimum response interval is 5 / 15 / 40 seconds. Active speech and unfinished answer jobs defer automatic dispatch. The newest question replaces a pending question; any continuation finalized before dispatch is included. Short utterances, common acknowledgments and recent near-duplicate questions are filtered locally. This is a heuristic, not guaranteed semantic question understanding.

Automatic answering disables background speculation to avoid generating two answers for the same segment. It uses the selected answer provider and can consume its allowance without pressing Answer. Off remains the default. Restoring a session does not automatically submit its old transcript.

## Local speaker labels and duplicate echo

Pause transcription before changing audio processing. Local speaker labels use sherpa-onnx CAMPPlus on CPU. The roughly 28 MB model is bundled through the existing ASR manifest and downloaded by `tools/setup_streaming.cmd`; the download is checked against SHA-256 `f682b514c05d947ee3fa91cd6ec6c5c7543479a128373fa29b1faedccd21fd11`.

Model source: [official sherpa-onnx speaker recognition release](https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models).

Finalized transcript headers retain the audio source and add a label such as `[12:00:00 电脑 · Speaker 1]`. Consecutive segments from the same source and speaker share one header in the combined transcript. Labels survive session recovery, translation and export. New voice identities after recovery use new numbers; previous voice embeddings are not restored.

This version identifies the dominant speaker per pause-delimited segment, with separate voice sets for the microphone and system audio. Segments shorter than one second, low-energy audio and ambiguous matches retain the source label. It does not split multiple speakers inside one segment or separate overlapping voices. Speaker embeddings remain in memory; no additional model/API tokens are used to identify voices. Labels add a little text to answer requests. Additional CPU use and finalization latency depend on the computer and segment duration. A model error falls back to ordinary transcription and is shown in the settings status.

Suppress duplicate echo conservatively compares microphone frames with up to half a second of recent system audio. It suppresses only near-identical copies; uncertain matches and independent simultaneous speech are preserved. This is duplicate-playback suppression, not a full room-acoustic echo canceller. Headphones remain useful with external speakers, reverberation or long playback delay. No audio is sent to a cloud service for this processing.

## Refine an answer

In Listen, expand Refine an answer, select a successfully completed answer, then choose Shorten, Give an example, Complete code or enter a follow-up question. Each action creates an independent task on the currently selected model using that answer and its original transcript. Existing answers and global instructions are not edited. These actions consume normal provider usage.

## Scenes

Open Context → Scenes. Enter a name and Save scene to bind the applied prompt, personal notes, reference text and screenshots. API keys, model credentials and conversation history are not copied into scenes. Scene data is stored in `data/scenes.dpapi` using Windows DPAPI for the current Windows user.

Saving applies the context editor's current draft first. Replacing an existing name, loading or deleting requires a second click. Loading explicitly replaces current context and drafts, invalidates derived analysis and future context sessions, and keeps visible transcript and existing answers. Save and load failures are visible; stale context/library versions are rejected. A failed disk write preserves the previous scene library.

## Meeting recap

Choose Finish & recap in Settings → Meeting assistance or Listen → More. It stops capture, flushes the final speech and waits for that transcription before creating a normal, cancellable answer task. The recap includes Summary, Decisions, Action items, Open questions and Next steps, in the selected answer language. Missing owners and deadlines must be marked unspecified. Check AI-generated summaries against the original transcript.

Recap when pausing is optional and off by default. With it enabled, pausing transcription triggers the same finish-and-recap flow. Repeated clicks for the same transcript do not create duplicate recap jobs; failed or canceled requests can be retried. Starting again and collecting new segments permits another recap. Recaps use the selected answer provider and consume usage. They remain in answer history and session exports.

## Verification

Unit tests cover silence gating, duplicate filtering, source/speaker grouping, conservative echo and double-talk preservation, scene validation/write failures, selected-answer context, last-segment recap and recovery boundaries. Browser tests cover controls and explicit draft/scene actions.

Local verification on 2026-10-25: 305 backend tests and 35 headless Edge UI tests passed. The real CAMPPlus model correctly grouped the two Fangjun recordings together and the two Leijun recordings together, with different labels between people. Embedding inference took 0.043–0.117 seconds per sample on this machine. Live cloud-provider requests, real microphone/room echo and overlapping-speaker accuracy were not tested. The unit suite emitted a Tcl interpreter cleanup warning while still passing.

For a real-model smoke test, download `fangjun-sr-1.wav`, `fangjun-test-sr-1.wav`, `leijun-sr-1.wav`, and `leijun-test-sr-1.wav` from the official speaker recognition release into `work/speaker-verification`, then run `python tools/verify_speaker_model.py`. These samples are not included in releases. Passing these checks is not a measurement of accuracy in a live meeting or across all accents, microphones and rooms.
