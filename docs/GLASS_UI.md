# Floating capsule interface

The default launcher opens the concept 04 desktop interface: a detached capsule navigation bar, a frosted settings panel, and separate transcript and answer surfaces. HTML/CSS/JavaScript renders the interface; the existing Python controller continues to own audio, model sessions, history, encrypted settings and global shortcuts.

## Architecture

The web interface is the only interface. Its controller, `app/audio_answer.py`, is headless: it builds no main window, and all state lives in plain attributes and Tk variables, never in widgets. Tk remains as the controller's event loop and for the small native dialogs listed below. The controller is split by job: `audio_capture.py` (capture and transcription), `api_clients.py` (Gemini, OpenAI-compatible and Codex clients), `answer_jobs.py`, `session_control.py`, `settings_state.py`, `cli_models.py`, `reasoning_support.py`, `screenshot_context.py` and `usage_ui.py`. Every provider is described once in `providers.py` (kind, model option, screenshot support, resumable sessions and CLI transport); other modules ask that table instead of repeating provider names.

The controller runs on its own main thread. A separate pywebview process uses Edge WebView2 to render local assets. A random-port HTTP server binds only to 127.0.0.1. State and command endpoints require a per-launch bearer token and reject cross-origin requests. The token is passed to the child in its environment, never saved to disk. Keys are not returned in state snapshots. Transcript and model text is rendered as text, not executable HTML.

Commands are queued and executed on the Tk thread. Model requests retain the existing asynchronous implementation. Both readers follow incoming text only while the user is at the bottom. No transcript or answer truncation is introduced.

## Desktop integration


The WebView uses transparent desktop composition. Whole-window Windows accent blur is explicitly disabled in every mode: it blurs the rectangular HWND bounds even outside the rounded content region. Background choices are translucent color, a denser frosted surface treatment, and opaque panels. The frosted surface does not blur the actual desktop; implementing that accurately requires a different composition architecture. Text remains opaque, and space outside panels stays clear.

The Windows host uses DWM composition for the WebView alpha channel, preserving antialiased CSS corners and transparent space between surfaces. A rounded native window region clips the host to the visible panels and open menus. Chinese text uses Microsoft YaHei UI; English uses Segoe UI Variable Text, with local font fallbacks.

Settings follow two independent columns: model and audio controls on the left, context and observed usage on the right. Secondary notes and preferences expand in place. The status and Prepare action share the main panel's footer. Listening uses one action capsule, a transcript surface, and an answer surface with its status integrated at the bottom; Settings remains available in the action capsule.

The local machine requires Microsoft Edge WebView2 and the pywebview/pythonnet dependencies listed in requirements.txt. The portable build includes Python packages; it does not install WebView2. The classic Tk interface has been removed from the code, not just from the launcher. If the web process fails, a startup error points to the diagnostic log and closes the controller.

Navigation, section headings and actions use locally bundled Bootstrap Icons. Their MIT license is included in `app/web/icons/LICENSE.txt`; no icon network requests are needed at runtime.

## Scope

This is an interface migration, not a model-latency improvement. Real requests, context preparation and prediction continue to consume usage according to the selected provider. Account balance is distinct from locally observed token totals.

## Validation


### Update validation (2026-10-21)

All 227 automated tests passed after the transparency, icon, and bilingual changes. Native Windows inspection confirmed clear space outside the panels and opaque text over translucent backgrounds. Browser checks at transparency values 1, 50, and 99 confirmed that only background alpha changed. Icon tests validate all nine embedded sizes; bilingual tests cover pending and failed translations, caching, saved settings, and independent language instructions. Paid provider translation quality was not tested in this validation.

## Listening controls


Native accent state 0 is applied before restoring DWM alpha composition with an explicit empty blur region. Reversing this order can leave an opaque base under CSS translucency. Native clipping includes two physical pixels of padding so it does not cut through CSS antialiasing. Neither the WebView host nor auxiliary dialogs use whole-window opacity.

Transcript language and Answer language have visible labels and independent Chinese + English choices. Bilingual caption translation retains the original speech while pending or failed; finalized translations use both language labels. It uses the selected answer provider and can incur usage. Bilingual answer instructions ask for corresponding Chinese and English explanations without duplicating code.
