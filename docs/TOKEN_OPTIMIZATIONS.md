# Token efficiency and transcription controls

## Transcription is independent of answering

Use **Start transcription**, **Pause transcription**, or **Resume transcription** in the listening workspace. The default global toggle is **Ctrl+Alt+L**; customize it in shortcut settings.

Pausing stops audio capture and finalizes the audio already received. Final ASR results may still arrive after the click. Existing transcripts, context, translations, the reading layout and active answer jobs are retained. Unadopted speculative work is cancelled; it is not an explicit answer job. Resume continues in the same session. No new audio is captured while paused.

## One prepared conversation

Starting transcription prepares at most one model conversation. Repeated starts do not prepare another while that group has an active or idle conversation. There is no automatic paid spare replenishment. Concurrent explicit answer requests still get independent lanes so that one answer does not interrupt another. For stateless APIs, an identical successful preparation request is not repeated; later answers still carry the necessary reference material.

The legacy spare-session setting is disabled on loading old preferences and is no longer offered. Preparation still consumes usage when enabled. A new model, a cleared conversation, or a lost connection may require a fresh full context.

## Context and images

Editing reference material does not change the conversation identity. Confirmed stateful transports receive a patch; explicit context/history resets create a new conversation epoch. Historical transcripts already present in the current transcript are represented by exact Unicode ranges. No history content is summarized or truncated by this optimization.

Codex, Claude Code and native LM Studio compare image-content hashes against the confirmed current snapshot of their own session. Adding one image sends that image without resending unchanged images. Duplicate capture data does not add another attachment. A new or recovered session receives the complete required images again; metadata changes do not cause identical pixels to be resent.

Gemini and OpenAI-compatible stateless endpoints still need their image context on each independent request. Images are not omitted merely because another request or provider has seen them. Antigravity image input remains unsupported in this application.

## Caption translation

Successful translations are cached in memory by target language and exact trimmed source text. Switching interface or transcript languages does not erase successful results. An in-flight translation is allowed to complete and can be reused if the user switches back. Failed entries are removed on a transcript-language reset so they can be retried. Different text or a different target language remains a different translation request.

## Answer and reasoning defaults

Default instructions answer directly without restating the question. Simple questions request a short answer without a reasoning narrative; complex tasks request brief supporting evidence. Complete code and necessary steps are still required. No automatic hard output cap is introduced.

For quick mode with automatic thinking/effort settings, choose the lowest supported explicit setting (`off`, `none`, `minimal`, or `low`). Manual effort and explicit thinking preferences take precedence. Some models cannot disable thinking, and low effort does not guarantee zero reasoning tokens.

## CLI context isolation

Only the application's child CLI processes receive these settings; user-wide CLI configuration and installed skills are unchanged.

- Codex uses a small answer-only instruction file, zero project-document bytes, disabled host skill discovery and memory injection, and disabled unnecessary agent/browser/computer/image-generation tools. Existing read-only permissions, tool-request rejection and no-file-access instructions remain in force. Automatic empty-thread replenishment is disabled.
- Claude Code uses the same answer-only system instructions, with its existing safe mode, empty tool list, disabled slash commands and empty setting sources.
- Antigravity retains its explicit answer-only agent with empty tool, MCP, skill and plugin lists. The installed CLI does not advertise a supported global system-prompt replacement flag; no undocumented flag or user-account change is used.

Codex configuration keys were checked against the installed CLI feature listing and the [official configuration reference](https://developers.openai.com/codex/config-reference/). Claude and Antigravity options were checked with the installed CLI help. Feature availability may change with CLI updates.

## Validation on October 17, 2026

Synthetic live checks used `gpt-6-astra` and `gemini-3.8-flash-low`, both at low effort. Each provider received a synthetic reference code and then a follow-up in the same conversation. Both returned `ORBIT-47` on both turns. No personal reference data was supplied by the test.

| Provider | Turn | Reported input | Output | Cached input | Full completion (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Codex | 1 | 6,934 | 8 | 0 | 3.63 |
| Codex | 2 | 7,182 | 8 | 6,784 | 1.50 |
| Antigravity | 1 | 5,942 | 5 | 0 | 5.24 |
| Antigravity | 2 | 6,249 | 5 | 0 | 1.87 |

These are smoke checks, not a controlled before/after saving estimate. Reported input includes retained conversation tokens, even when the client sends only a patch. Incremental transmission does not mean the provider stops counting prior context. The previous [prompt-language benchmark](PROMPT_TOKEN_BENCHMARK_2026-10-17.md) remains a frozen record of the earlier revision and must not be relabeled as a measurement of these newer changes.

Regression tests cover one-time preparation, retained translations, changed-image-only transport, full-image fallback, lossless history references, manual reasoning precedence, pause behavior and shortcut dispatch. Mocked capture checks do not establish physical audio-device compatibility.
