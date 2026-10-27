# Changelog

## 1.0.1

- Replace the retired Midnight Studio preview with the integrated light and Black Gold Workbench, with answer tabs and reorganized settings.
- Add inline model diagnostics, image preview, caption model selection, and progressive bilingual captions with preserved source records.
- Improve listening layout, window resizing, and focus handling.
- Remove the obsolete standalone design prototype and screenshot-only browser test; retain behavioral regression coverage for Classic and both Workbench palettes.

## 1.0.0

- Start the 1.0.0 version series, following the previous date-based versions.
- Use English for the default README and provide a separate Chinese README.
- Rename the application, launcher, assets, internal identifiers, and portable packages to EchoCue.
- Include both README languages in portable packages.

## 2026.10.23.1

- Edit context and prompts directly in the context panel, with explicit apply/discard and protection against stale updates.
- Save, load and delete named prompt templates in local encrypted storage.
- Invalidate stale AI preparation and conversation memory when context changes.
- Reduce CI artifact retention to one day and upload portable bundles only for main-branch publishing.

## 2026.10.22.4

- Draw dropdown lists, the color picker and tooltips inside the page, and turn off the right-click menu and autofill lists, so no WebView2 popup window can show in a screen share (`app/web/popups.js`).

## 2026.10.22.3

- Drag handles are thin solid lines with no pale edge; the window keeps only the painted pixels.
- Stop the top toolbar shrinking past the width its buttons need, so collapsed icons never overlap.
- Add Settings > Preferences > Taskbar and Tray icon; add a system tray icon with a right-click settings menu (`app/tray_menu.py`).
- Answer about screenshots on every provider: Antigravity and Kiro read image files (Kiro on its V3 engine); text-only providers get Windows OCR text (`app/image_text.py`, `app/ocr_image.ps1`).
- Render the Live transcript and AI answer as Markdown, built as safe DOM nodes and updated incrementally (`app/web/markdown.js`).

## 2026.10.22.2

- Send live state to the web page as changes only. The page used to fetch the whole state, full transcript and answer included, about five times a second even when nothing changed. Now each read waits until something changes (up to 1 second), settings are sent only when they change, and the transcript and answer send only their changed tail. The page also edits the text in place instead of rebuilding it. See `app/state_feed.py`.

## 2026.10.22

- Save the Listen-page look (transparency, text sizes, panel sizes, colors, Bold text, Text outline and presets) on every exit, even when Remember keys is off. API keys still follow Remember keys.
- Add a Layout menu to the Listen toolbar: built-in presets (Default, Compact, Large text), up to five named presets of your own, the text and panel colors, Bold text, Text outline, and Reset layout.
- Move the color pickers off the toolbar and group the More menu into Window and Session. Only one toolbar menu opens at a time; clicking outside or pressing Esc closes it.
- Check every look value before applying any, so a preset applies whole or not at all.
- Add Playwright browser tests for the web page (`tests_ui/`, run with `tools/run_ui_tests.py`), and run them in CI in headless Edge.

## 2026.10.21.4

- Remove the old Tk interface from the code. The controller behind the web interface is now headless and keeps no state in widgets; only the small native dialogs still use Tk.
- Describe every answer provider once in `app/providers.py`; the rest of the app reads provider kind, model option, screenshot support and CLI transport from it.
- Split `app/audio_answer.py`: audio capture, API clients, sessions, settings and usage now live in their own modules.
- The Usage dialog now has the DeepSeek and Kimi balance buttons that were only on the old monitor panel.

## 2026.10.21.3

- Add Kiro (local kiro-cli login) as an answer provider, with its model catalog, reasoning effort, captions and speed test. Answers run with no tools, and each one-shot Kiro chat is deleted afterward. Screenshots are not sent to Kiro.
- Keep the English listening toolbar on one row: secondary buttons collapse to icons with tooltips on narrower windows.
- Add a corner grip to resize the frameless window.
- Resize the Context panel from its corner, and apply listening transparency to it and to the listening selects.
- Add A−/A+ text size controls (12–40 px) for the live transcript and the AI answer.
- Add text color and panel color pickers next to Transparency (double-click to reset).
- Add Bold text and Text outline switches to the More menu (both off by default). The outline uses the opposite brightness of the text and strengthens as panels become more see-through.
- Add drag bars between the toolbar, transcript and answer panels, and side grips that set each panel's width on its own (kept centered); arrow keys adjust them. Double-click a bar to reset heights, or a side grip to reset that panel's width. Sizes are saved.

## 2026.10.21.2

- Read Claude Code model aliases and resolved IDs from CLI initialization metadata instead of returning three hard-coded aliases. Catalog reads do not submit a generation turn.
- Replace filtered model autocomplete with an explicit model selector while retaining custom model IDs.
- Refresh model catalogs after switching providers and retry the latest API catalog request when another refresh is still running.

## 2026.10.21.1

- Allow dragging the context panel by its title bar, keep it within the viewport, and preserve text selection and close-button interaction.

## 2026.10.21

- Restore DWM alpha composition after disabling native accents, removing the gray host rectangle and opaque base behind translucent panels.
- Keep text and icons opaque while adjusting panel backgrounds; preserve antialiased panel edges inside the native clipping region.
- Add the multi-resolution blue waveform application icon to the EXE and desktop host.
- Label transcript and answer language selectors in the listening workspace and add independent Chinese + English modes.
- Keep source speech visible while bilingual captions are being translated or when translation fails.

## 2026.10.20

- Replace the main interface with a local HTML/CSS/JavaScript Floating Capsule workspace hosted by Python and WebView2.
- Consolidate settings and integrate the listening status into the answer panel.
- Add local icons, native toolbar dragging, and rounded panel clipping. Disable whole-window accent blur to avoid the rectangular gray surround.
- Preserve English/Chinese interfaces, independent content languages, full transcripts, concurrent answers and existing provider integrations.
- Restore audio-engine reconfiguration and canonical reasoning values across interface languages.
- Remove the legacy main-interface entry and fallback; retain backend/native-dialog dependencies.
- Package WebView dependencies and extend portable smoke checks. Personal settings, keys, sessions and diagnostics remain excluded.

See [release notes](docs/releases/2026.10.20.md) for installation and validation limitations.

## Earlier releases

See [dated release notes](docs/releases/) for earlier changes and validation records.
