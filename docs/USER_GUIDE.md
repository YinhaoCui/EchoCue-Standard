# EchoCue user guide

See [Meeting assistance](MEETING_ASSISTANCE.md) for optional automatic answers, local speaker labels, duplicate echo suppression, answer refinement, encrypted scenes and meeting recaps.

## Start and prepare

For installation, run `EchoCue-Standard-1.0.1-Setup-x64.exe`. It installs for the current user, adds a Start-menu entry and offers a desktop shortcut. Uninstall from Windows Settings → Apps → Installed apps. User data stays in `%LOCALAPPDATA%\EchoCue Standard` after upgrades and uninstall; existing source/portable data is not automatically imported. To migrate, close the app and copy your source or portable `data` folder into `%LOCALAPPDATA%\EchoCue Standard\data` on the same Windows account. The installer includes Python, dependencies and transcription models, and installs WebView2 online if missing.

Launch `EchoCue.exe` from the complete application folder. Source checkouts require dependency setup and launcher compilation first; see the [project README](../README.md). Select an answer provider, model, and supported reasoning options, then select audio devices and a transcription model independently.

Click **Prepare** to enter the listening workspace. With preparation enabled, reference material and history are sent in advance and count toward provider usage. Preparation failure does not prevent a later answer. The listening layout reserves more space for transcript and reply text; opening settings does not clear either pane or cancel tasks.

## Workspaces

Choose **Interface style** at the top of Settings, or **Layout → Interface style** in Listen. **Classic Glass** retains the original floating layout. **Midnight Studio** uses a graphite palette, a compact workspace rail, and side-by-side transcript and answer panels on wide windows; narrower windows stack the panels. Drag the divider to change the split, use Left/Right while it is focused, or double-click to reset. Styles and the split are saved even when Remember keys is off. Switching styles keeps current drafts, transcripts, answers and active tasks.

Settings now use a single column with separate navigation for models, audio, meeting assistance, context, preferences and usage. Model IDs, reasoning and the LM Studio address are under **Model options**. Request limits, prediction, preparation, session reuse and answer mode remain available under **Preferences → Generation options**.

Settings groups model, audio, context and preferences controls in one page. Prepare enters the listening page without clearing the session. Drag an empty area of the top capsule to move the window. Use Settings to return to configuration. The old main-interface entry has been removed; some tools still use native dialogs.


Background choices in Preferences are translucent color, frosted surface and opaque. Frosted surface is a tinted material, not desktop blur. See [interface notes](GLASS_UI.md).

Resize the window from any outer edge or corner; there is no visible corner badge. In Classic Glass, drag a panel's left or right edge to change its width. In wide Midnight Studio, the transcript's right edge and the answer's left edge move the shared divider; their outer edges resize the window. Old independent panel widths do not create gaps in the two-column layout. Keyboard focus highlights the divider and supports arrow-key adjustments; double-click resets it. Horizontal bars in the stacked layout adjust panel heights.

Listening transparency also applies to title-bar, sidebar, button, input, menu and drawer backgrounds. Text and icons stay opaque. Settings remain readable independently of the listening transparency value.

## Live transcription

The local choices are English Zipformer, Chinese Zipformer, and bilingual Paraformer. The mixed-language option is the saved default when no preference exists. The app preloads the selected engine and keeps it resident. System audio and microphone input have independent recognition states; use headphones to reduce duplicate capture.

Speech appears as provisional text that may change, followed by finalized segments after a pause. Pause presets are 0.35, 0.65, and 1.0 seconds. Shorter pauses can create more segments. Model loading, noise, speech patterns, and CPU load affect latency and accuracy.

Switching transcription models finalizes the old stream before processing new input and preserves previous text. Audio arriving during model loading is queued. Queue duration and processing-wait metrics are not the complete speech-to-caption latency.

Selecting an older transcript stops the display from following live text while capture continues. Return to the full live transcript to resume that view. When reading earlier lines, incoming text does not force the scroll position to the bottom. Transcript headers are grouped by audio source rather than repeated for each consecutive segment from the same source.

## Answer tasks

Click **Answer** or press **Ctrl + Alt + Space**. Each task captures the relevant audio boundary, waits for that transcription to finalize, and creates an independent context snapshot. Listening continues. Repeated requests do not cancel earlier answers.

Replies stream as body text arrives in the answer panel. Active answers have individual cancel controls. Use Copy to copy the displayed output or Answer again to submit the current transcript using the current settings; another request may consume additional usage.

Select an existing transcript and request another answer with a different model without running speech recognition again. Completed history is retained without a fixed six-turn or time cutoff. Concurrent tasks include the context available when their snapshots are made, not future output from other running tasks.

The app does not impose a fixed conversation-length cutoff. Provider context windows, output limits, available memory, and file parsers still impose practical limits. Incomplete streams preserve received text and are marked accordingly. Continuing an answer creates another task rather than silently replacing the original.

## Context and screenshots

**Built-in scenarios** is available in Settings → Context and the listening Context drawer. Choose General, Coding, Interview, Translate, Meeting, Learning or Writing, then select **Use preset**. This loads an editable prompt draft; existing text requires confirmation before replacement. Select **Apply changes** to use it in future requests. Answering also applies pending context drafts through the existing workflow. Running tasks keep their original instructions. You can edit the prompt and save it in your local encrypted template library.

The presets guide response structure: coding emphasizes concrete code and verification limits; interview avoids invented personal experience; translation preserves meaning and formatting; meetings separate decisions from proposals and identify unspecified owners; learning explains progressively; writing preserves the author's facts and voice. Presets follow the selected answer language. They do not change providers or grant additional model capabilities.

Add personal notes or supported documents in the context workspace. Analyze them before answering when useful; analysis is a model request and consumes usage. Editing a transcript changes future context, not already generated answers. Temporary transcription drafts are not duplicated in finalized context.

To attach a screenshot, focus the external window first, then return and capture it. The app remembers the recent external window. Keep it open and not minimized, inspect the image, and remove blank or protected captures. Screenshot support depends on the selected provider and vision model; an unsupported channel reports the limitation instead of silently dropping the image.

Screenshots can be included in preparation, analysis, or answer requests. Stored context and session attachments use local encryption. Temporary image files may remain after abnormal process termination.

## Sessions and editing

The session tools provide recovery, transcript editing, terminology, search, and export. Changed session data is encrypted with Windows DPAPI and saved approximately every five seconds to `data/sessions.sqlite3`. A crash can lose the final unsaved interval. Raw audio is not included in saved sessions.

Stop listening and finish or cancel active answers before restoring a session. Restoration creates a separate session; incomplete tasks remain interrupted with their existing text and are not automatically resubmitted. Provisional transcript drafts remain distinct from finalized records.

Terminology entries can be reference words or exact replacement rules in the form `recognized phrase => preferred phrase`. This does not re-recognize audio and can produce inappropriate replacements; review results. Markdown and JSON exports are plaintext, and JSON may include saved reference material.

## Models and reasoning

Refresh the provider's model directory, choose a listed model, or enter a compatible ID. A blank CLI model selection uses that CLI's default; API providers require a model ID. New settings affect new tasks; existing tasks keep their starting configuration.

A successful API refresh replaces built-in presets, including when the server returns no models. The selector retains chat-compatible entries; existing category descriptions only order and describe returned models. On failure, the last successful catalog for the same key and service address stays available, or unverified presets are shown if no catalog has been fetched. Catalogs are cached for this run only, and their source is shown beside the selector. LM Studio has no built-in model IDs. A saved or manually entered model remains selected even if the catalog no longer lists it, with an explicit label; it is not automatically replaced. Catalog visibility does not establish generation access. Claude Code's speed-test selector also reads the CLI catalog instead of always loading fixed aliases.

Reasoning effort and the reasoning toggle use verified model-specific capabilities. Some models always reason and cannot truly disable it. Unknown model capabilities retain service defaults rather than sending guessed parameters. See [context preparation](CONTEXT_PREPARATION.md) for session and adapter details.

Antigravity uses its local CLI account, independently of Gemini API credit. An IDE login does not necessarily authenticate the CLI. Claude Code follows its configured authentication and billing method. LM Studio needs a running local server. DeepSeek uses API requests, not automated private website endpoints.

## Usage and balances

Local records include provider-reported input, output, reasoning, cached, and total tokens, including tests and preparation. Repeated cumulative stream reports are not repeatedly added. Missing usage after errors or cancellation remains unknown. These records do not contain prompts or keys and are not a complete account-wide bill.

Codex quota queries and supported DeepSeek/Kimi balance queries are separate from local token counts. Balance queries are manual and apply to the current key, while local totals can span different keys. Qwen's official usage page provides account-level information that the app cannot infer from partial token records.

## Speed tests

The model speed-test window has its own provider, model, effort, and answer-mode selection. It uses a fixed Python task: implement an O(n) `unique_in_order(items)` function that preserves order and does not modify the input, with assertions for empty input, duplicates, and negative numbers. Personal context and transcripts are excluded.

Results show first body text, completion time, average characters per second, reported output tokens, and status. Reasoning text does not count as the first answer body. Average speed includes waiting and is not pure decoding throughput. The app does not execute generated code or automatically establish correctness. A test can time out after 120 seconds; canceling it does not cancel ordinary answer tasks.

Task cards distinguish dispatch, transcription wait, context preparation, model first text, receipt, first display, UI queueing, and completion. First-display timing is an application measurement, not a physical screen measurement. Speculation may shorten the wait after a keypress while still consuming earlier model computation. No subsecond guarantee is made.

## Window controls

Open **Settings → Shortcuts** to edit all six global shortcuts, restore their defaults, and save/apply them. The Listen menu and workspace rail open this same section. Invalid or duplicate combinations retain your edits for correction and leave the current bindings unchanged. Registration status is shown in the page; a combination occupied by another application must be changed. Reset loads a draft and only takes effect after Save and apply. The editor does not open a separate native window.



English is the default interface language. Chinese remains available from the language selector. Language changes preserve settings, active tasks, transcription language, and existing content.
