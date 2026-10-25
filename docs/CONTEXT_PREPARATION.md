# Context preparation and reasoning controls

These settings appear near reasoning effort in the answer-provider settings.

- **Prepare context when listening starts:** enabled by default. After capture starts, the app sends the current reference material, supported screenshots, and history for a short acknowledgement. This consumes provider usage. Failure is reported without blocking listening or later answers.
- **Keep conversation context between answers:** enabled by default. New requests include a snapshot of completed turns without a fixed turn-count cutoff. Output that has not yet been generated cannot be included in another task's snapshot.
- **Request reasoning:** automatic, enabled, or disabled. Disabling uses a supported off parameter when available; otherwise it selects the lowest supported effort and a direct-answer instruction. It cannot disable reasoning that a model always performs.

## Session behavior

Codex keeps completed sessions in a persistent app-server and reuses a matching idle thread. Concurrent requests use separate sessions with full context rather than waiting for another answer. Changing the model, effort, or reference material can require a new session. Speculative drafts do not contaminate retained conversation state.

Antigravity reuses idle stream-json processes with stdin kept open. Busy sessions branch independently; failed or canceled processes are not reused. Cumulative usage is converted into per-turn increments.

LM Studio prefers native `/api/v1/chat` with `previous_response_id` and model-reported reasoning options, with a compatibility fallback for older servers. Context snapshots account for other completed tasks.

Other HTTP providers receive full context on subsequent requests. Stable material is placed first to make provider-side prefix caching possible, but cache hits are not guaranteed. Preparation is an actual model request, not merely an open network connection.

Stopping listening, canceling all answers, clearing context, or closing the app cancels unfinished preparation. Preparation counts toward usage but is not displayed as a regular answer or inserted as a conversation turn.

## Adapter review recorded on October 14, 2026

These are implementation notes from that review, not a claim that every account or future model supports every option.

| Provider | Reasoning and session behavior |
| --- | --- |
| Codex | Uses model-reported effort options. The tested Astra directory exposed low through ultra, without a true off mode. |
| Antigravity | Uses low/medium/high effort, with process reuse isolated by session, model, and effort. No true off setting was exposed. |
| LM Studio | Uses model `allowed_options`; unsupported overrides are omitted. Native failures are not automatically resubmitted. |
| Claude Code | Uses subprocess reasoning controls where supported; some models cannot disable thinking. Requests still carry full context rather than a persistent process. |
| Gemini | Uses model-specific thinking levels or budgets; off is offered only for supported models. |
| DeepSeek | Uses supported thinking and effort parameters, with full history references and no tool execution. |
| Kimi | Uses supported model-specific off/effort controls; always-thinking models do not advertise an ineffective off mode. |
| Qwen | Uses verified thinking parameters; unknown models retain service defaults. |
| Meta Muse | Uses the minimum supported effort rather than an unsupported off value. |

No paid explicit cache storage is created automatically. Preparation respects the configured output budget rather than forcing a 256-token cap. Keeping all turns does not remove the provider's context-window limit.

## Historical measurement

A synthetic Astra low test on October 14, 2026 measured 3.35 seconds to first preparation text and 1.98 seconds to the first text of a later question in the same session. It recalled a code supplied earlier. This was not a coding benchmark and does not establish a one-second guarantee.

## Protocol references used by the adapters

- [Codex app-server](https://learn.chatgpt.com/docs/app-server)
- [Antigravity headless interface](https://www.antigravity.google/docs/cli/headless/)
- [LM Studio chat](https://lmstudio.ai/docs/developer/rest/chat), [model capabilities](https://lmstudio.ai/docs/developer/rest/list), [streaming](https://lmstudio.ai/docs/developer/rest/streaming-events)
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars)
- [Gemini thinking](https://ai.google.dev/gemini-api/docs/generate-content/thinking), [caching](https://ai.google.dev/gemini-api/docs/generate-content/caching)
- [DeepSeek thinking](https://api-docs.deepseek.com/guides/thinking_mode/), [caching](https://api-docs.deepseek.com/guides/kv_cache/)
- [Kimi thinking](https://platform.kimi.ai/docs/guide/use-thinking-models), [reasoning effort](https://platform.kimi.ai/docs/guide/use-reasoning-effort)
- [Qwen thinking](https://help.aliyun.com/zh/model-studio/deep-thinking)
- [Meta reasoning](https://dev.meta.ai/docs/reasoning)
