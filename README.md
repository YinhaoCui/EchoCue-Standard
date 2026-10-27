<div align="center">

<img src="app/assets/echocue.png" alt="EchoCue icon" width="96" />

# EchoCue Standard

### Live transcription. Answers when you need them.

System audio, your microphone, reference material, and multiple AI models in one Windows desktop workspace.

[![Version](https://img.shields.io/badge/Version-1.0.1-2d847a)](https://github.com/YinhaoCui/EchoCue-Standard/releases/latest)
[![Windows build](https://github.com/YinhaoCui/EchoCue-Standard/actions/workflows/windows.yml/badge.svg)](https://github.com/YinhaoCui/EchoCue-Standard/actions/workflows/windows.yml)
![Platform](https://img.shields.io/badge/Windows-x64-0078D4)
![Interface languages](https://img.shields.io/badge/UI-English%20%7C%20中文-2563EB)

[中文](README_ZH.md) | **English**

**[Download](#download) · [Quick start](#quick-start) · [Features](#features) · [Providers](#providers) · [FAQ](#faq) · [Documentation](#documentation)**

</div>

Current version: **1.0.1**. Install with `EchoCue-Standard-1.0.1-Setup-x64.exe`, or extract the portable download and open `EchoCue.exe`.

## Why EchoCue?

Meetings, lectures, and technical discussions often involve listening, taking notes, and assembling context for an AI question. Switching between those steps makes it easy to miss what comes next.

EchoCue connects them: transcribe system audio and your microphone locally, add notes, documents, or screenshots, and ask your chosen model with a shortcut. Transcription continues while answers stream. Later questions can run as separate tasks.

| Scenario | What you can do |
| --- | --- |
| Meetings | Follow live transcripts, request answers, and finish with decisions and action items |
| Lectures | Keep the original text, view bilingual captions, and explain concepts using reference material |
| Technical discussions | Attach a screenshot or document, ask follow-ups, add examples, or complete code |
| Review | Edit transcripts, search history, restore sessions, and export Markdown or JSON |

## Download

**[Download the Windows portable release →](https://github.com/YinhaoCui/EchoCue-Standard/releases/latest)**

1. Download `EchoCue-Standard-<version>-Setup-x64.exe` and run the installer.
2. Choose an optional desktop shortcut, then open EchoCue from the Start menu or desktop.
3. Uninstall through **Windows Settings → Apps → Installed apps → EchoCue**.

Installation is per user and includes Python, dependencies and transcription models. The installer installs Microsoft's WebView2 Runtime if needed; that step requires internet access. User data is kept in `%LOCALAPPDATA%\EchoCue Standard` and retained when uninstalling or upgrading. No API keys, settings or conversations are bundled.

For portable use, download `EchoCue-Standard-<version>-windows-x64.zip`, extract the complete folder, and open **`EchoCue.exe`**.

The portable package includes Python, dependencies, and local transcription models. Keep the folder intact; moving the EXE alone removes files it needs.

**Requirements:** Windows x64, an audio device, and Microsoft Edge WebView2 Runtime. WebView2 is not bundled and must be installed if missing. Source archives require development setup.

Check the matching [release notes](https://github.com/YinhaoCui/EchoCue-Standard/releases) for packaged features. This page also describes capabilities in the current source tree.

## Quick start

1. **Choose a model:** select an answer provider and model. Configure its API key, authenticate its local CLI, or start LM Studio as appropriate.
2. **Choose audio:** select system audio and an optional microphone, then select a transcription model independently.
3. **Add context:** optionally attach notes, reference documents, or an external window screenshot.
4. **Start listening:** click **Prepare** to enter the listening workspace.
5. **Ask:** click **Answer** or press **`Ctrl + Alt + Space`**. Answers stream while transcription continues.

Use **Long question** to collect speech through pauses and submit manually. For automatic answers, choose **Quick Q&A** and enable the desired policy in meeting assistance settings.

## Features

### 🎙️ Local live transcription

- Capture system audio and microphone input separately, preserving the audio source.
- Choose English Zipformer, Chinese Zipformer, or bilingual Paraformer.
- Pause, resume, edit transcripts, and apply terminology replacements. Switching transcription models preserves existing text.
- Optionally add local speaker labels and duplicate echo suppression. Labels identify the dominant voice per segment and have limits with overlapping speech.

### 💬 Multiple answer providers

- Choose a local CLI, cloud API, or LM Studio provider in the same workspace.
- Stream independent answer tasks, cancel them individually, or answer again using another model.
- Shorten an existing answer, request examples, complete code, or ask a follow-up.
- Refresh model catalogs or enter IDs manually. Image and reasoning support depend on the provider and model.

### 📎 Context for your questions

- Start from built-in General, Coding, Interview, Translate, Meeting, Learning or Writing prompts, then edit and apply them through the context workspace.
- Include personal notes, reference documents, and screenshots of an external window.
- Save reusable context scenes for different discussions.
- Retain transcripts and completed answers across requests, subject to the model's context capacity.
- Optionally prepare context in advance, use speculative generation, and reuse sessions on supported providers.

### 📝 Meeting assistance and bilingual content

- Optionally answer detected questions or respond after pauses, with configurable pacing.
- Finish with a recap covering summary, decisions, action items, open questions, and next steps.
- Set interface, caption, and answer languages independently, including bilingual content.
- Recover, search, and export locally encrypted sessions. Automatic answering and recap on pause are off by default.

### 🪟 A floating desktop workspace

- Switch between Classic Glass, light Workbench, and Black Gold Workbench from Settings or the listening Layout menu. Workbench shows transcript and answer side by side with answer task tabs.
- Restore an interactive window with the recovery shortcut.


### 📊 Usage and response observations

- Record provider-reported tokens, requests, and cache usage, with quota or balance queries for supported providers.
- Run a separate model speed test and inspect answer task stages.
- Measurements describe individual runs. Local records are not a complete account bill, and missing reports remain unknown.

## Providers

| Connection | Supported providers | Setup |
| --- | --- | --- |
| Local CLI | Codex, Claude Code, Antigravity, Kiro | Install and authenticate the corresponding CLI |
| Cloud API | Gemini, DeepSeek, Kimi, Qwen (Beijing), Meta Muse | Configure the service's API key and an available model |
| Local model server | LM Studio | Start the server and load a compatible model; provide a token if authentication is enabled |

CLI providers follow their own configured authentication and billing. The app does not automatically inherit the current Codex desktop chat's login. Antigravity CLI authentication is separate from Gemini API credit.

Model availability, image input, reasoning controls, and session reuse vary by provider. After refreshing the catalog, use a model test to confirm generation access. A test sends a request and may incur usage.

## Default shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl + Alt + Space` | Create an answer task |
| `Ctrl + Alt + T` | Toggle always on top |


## FAQ

### Can I use it offline?

Local live transcription does not require a cloud speech service. A local LM Studio server with a loaded model can provide local answers. Remote providers receive the transcript, reference material, and images needed for their requests.

### Why is there usage before I press Answer?

Context preparation, speculative generation, caption translation, and automatic answers can call the model in advance. Translated and bilingual captions use the selected answer provider. Enable these features as needed; cancellation does not undo content already sent or usage already incurred.

### Where is my data stored?

Settings, sessions, and usage records live in `data/`, or `_internal/data/` in portable releases. Temporary files live in `work/`. API keys and saved session content use Windows DPAPI encryption tied to your Windows user. Sessions do not save raw audio. Markdown and JSON exports are plaintext.

### Why does changing models leave an existing answer unchanged?

New settings affect subsequent tasks. Running tasks keep their starting model and context; cancel them individually or request another answer. There is no fixed conversation turn cutoff, but model context windows, memory, and file parsers still impose practical limits.

### Can I set English and Chinese independently?

Yes. Change the interface language in settings and set caption and answer languages separately in the listening workspace. English is the default interface language. Switching the interface preserves existing transcripts and answers.

## Documentation

| Guide | Contents |
| --- | --- |
| [User guide](docs/USER_GUIDE.md) | Startup, audio, answer tasks, context, and sessions |
| [Meeting assistance](docs/MEETING_ASSISTANCE.md) | Automatic answers, speaker labels, scenes, and recaps |
| [Interface guide](docs/GLASS_UI.md) | Floating workspace, backgrounds, and window controls |
| [Long questions and Quick Q&A](docs/LONG_QUESTIONS.md) | Manual submission and prediction policy |
| [Context preparation](docs/CONTEXT_PREPARATION.md) | Preparation, session reuse, and reasoning controls |
| [Interface language](docs/UI_LANGUAGE.md) | Interface, transcript, and answer languages |
| [Token optimizations and pause/resume](docs/TOKEN_OPTIMIZATIONS.md) | Context, image, and translation caching |
| [Documentation index](docs/README.md) | More guides, benchmarks, and historical validation |
| [Changelog](CHANGELOG.md) | Version changes |

## Development

Use Windows x64, Python, Tkinter, and Microsoft Edge WebView2 Runtime. CI currently uses **Python 3.14**. The source repository excludes installed dependencies, downloaded models, personal data, and generated EXE files.

Run from the project root in PowerShell:

```powershell
# Install application dependencies
python -m pip install --only-binary=:all: --no-binary=proxy_tools --target vendor -r requirements.txt

# Download and verify local transcription models
python tools/setup_streaming.py --models-only

# Build the launcher, then run
powershell -ExecutionPolicy Bypass -File tools/build_launcher.ps1
.\EchoCue.exe
```

<details>
<summary><strong>Tests, packaging, and directory structure</strong></summary>

```powershell
# Backend regression tests
python tools/run_tests.py

# Install UI test dependencies and run headless Edge tests
python -m pip install -r requirements-dev.txt
python tools/run_ui_tests.py --require

# Package after preparing dependencies, models, and the launcher
python tools/package_release.py
```

Tests require loopback connections and desktop window creation. UI tests also require Edge. Packaging produces `dist/EchoCue-Standard-<version>-windows-x64.zip`, excluding personal `data/` and `work/`.

| Directory | Contents |
| --- | --- |
| `app/` | Python backend and web UI |
| `tests/`, `tests_ui/` | Backend and UI tests |
| `tools/` | Setup, build, packaging, and development tools |
| `docs/` | Guides, release notes, and validation records |
| `runtime/`, `vendor/` | Local models, runtime assets, and dependencies |
| `data/`, `work/` | Local data and temporary files excluded from version control |

[Windows CI](https://github.com/YinhaoCui/EchoCue-Standard/actions/workflows/windows.yml) tests and builds on pushes to `main`, pull requests, and manual dispatch. To publish, update `VERSION` and its `docs/releases/<version>.md`. After a successful `main` build, the workflow publishes the ZIP and SHA-256 checksum, leaving existing releases unchanged. Pull requests never publish.

</details>

## Feedback and contributions

Use [Issues](https://github.com/YinhaoCui/EchoCue-Standard/issues) for bugs and suggestions. Include the app version, Windows version, provider, and reproduction steps. Remove keys and private conversation content from logs.

Pull requests improving documentation, model integrations, and everyday use are welcome.
