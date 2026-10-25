<div align="center">

<img src="app/assets/echocue.png" alt="EchoCue 图标" width="96" />

# EchoCue Standard

Windows 安装版：运行 `EchoCue-Standard-1.0.0-Setup-x64.exe`，从开始菜单或可选桌面快捷方式启动。通过 Windows 设置 → 应用 → 已安装的应用卸载。安装版的配置和会话保存在 `%LOCALAPPDATA%\EchoCue Standard`，升级和卸载均保留数据。安装包包含 Python、依赖和转录模型；缺少 WebView2 时会联网安装微软运行时。安装包不包含个人密钥、配置或会话。

### 实时听写，随时应答。

把电脑声音、麦克风、参考资料与多个 AI 模型，放进同一个 Windows 桌面工作区。

[![最新版本](https://img.shields.io/github/v/release/YinhaoCui/EchoCue-Standard?label=Release)](https://github.com/YinhaoCui/EchoCue-Standard/releases/latest)
[![Windows 构建](https://github.com/YinhaoCui/EchoCue-Standard/actions/workflows/windows.yml/badge.svg)](https://github.com/YinhaoCui/EchoCue-Standard/actions/workflows/windows.yml)
![平台](https://img.shields.io/badge/Windows-x64-0078D4)
![界面语言](https://img.shields.io/badge/UI-中文%20%7C%20English-2563EB)

**中文** | [English](README.md)

**[下载安装](#下载安装) · [快速上手](#快速上手) · [功能特性](#功能特性) · [模型接入](#模型接入) · [常见问题](#常见问题) · [使用文档](#使用文档)**

</div>

当前源码版本：**1.0.0**。完整解压便携包后，请打开 `EchoCue.exe`。

## 为什么做 EchoCue？

开会、听课或讨论技术问题时，经常需要一边听、一边记，再把问题和资料整理给 AI。来回切换窗口，也容易漏掉后续内容。

EchoCue 把这几步连在一起：在本地转录电脑声音与麦克风，带上你的笔记、文档或截图，按一次快捷键即可向所选模型提问。回答生成时继续听写，后续问题可以创建新的回答任务。

| 使用场景 | 可以怎样用 |
| --- | --- |
| 会议讨论 | 查看实时转录，按需生成回答，结束时整理结论和待办 |
| 课程与讲座 | 保留原文，查看双语字幕，结合资料解释概念 |
| 技术交流 | 附上题目截图或参考文档，追问、补充示例或完善代码 |
| 回顾整理 | 编辑转录、搜索历史、恢复会话，导出 Markdown 或 JSON |

## 下载安装

**[前往 Releases 下载 Windows 便携版 →](https://github.com/YinhaoCui/EchoCue-Standard/releases/latest)**

1. 下载 `EchoCue-Standard-<version>-windows-x64.zip`。
2. 完整解压到一个文件夹。
3. 打开文件夹中的 **`EchoCue.exe`**。可为它创建桌面快捷方式。

便携包包含 Python、运行依赖和本地转录模型。请保留整个文件夹；单独移动 EXE 会丢失启动所需文件。

**运行要求：** Windows x64、可用的音频设备，以及 Microsoft Edge WebView2 Runtime。便携包不包含 WebView2，缺少时需先安装运行时。源码 ZIP 需要自行配置开发环境。

发布包功能以对应的 [Release 说明](https://github.com/YinhaoCui/EchoCue-Standard/releases)为准；本页同时介绍当前源码中的能力。

## 快速上手

1. **选模型**：选择回答通道与模型，按要求填写 API Key、登录本机 CLI，或启动 LM Studio 服务。
2. **选声音**：设置电脑声音和可选的麦克风输入，再独立选择转录模型。
3. **加资料**：按需添加个人笔记、参考文档或外部窗口截图。
4. **开始听写**：点击 **Prepare / 准备**，进入听写工作区。
5. **获取回答**：点击 **Answer / 回答**，或按 **`Ctrl + Alt + Space`**。回答逐步显示，听写继续。

长问题可选择 **Long question / 长问题**，收集完整内容后再手动提交。需要自动回答时，选择 **Quick Q&A / 快速问答**，并在会议辅助设置中开启相应策略。

## 功能特性

### 🎙️ 本地实时转录

- 分别采集电脑声音与麦克风，保留音频来源。
- 提供英文 Zipformer、中文 Zipformer 和中英双语 Paraformer。
- 支持暂停、恢复、术语替换和转录编辑；切换转录模型时保留已有文本。
- 可选本地说话人标签与重复回声抑制。标签按语音片段识别主要发言人，对重叠讲话有局限。

### 💬 多模型回答

- 在同一工作区选择本机 CLI、云端 API 或 LM Studio 回答通道。
- 回答以独立任务流式生成，可分别取消，并可换模型再次回答。
- 对已有回答进行缩短、举例、补全代码和追加追问。
- 支持刷新模型目录与手动填写模型 ID；截图和推理选项取决于通道及模型能力。

### 📎 带着资料提问

- 内置通用、编程、面试、翻译、会议、学习辅导和写作润色提示词，可载入草稿后编辑、应用并保存为自定义模板。
- 将个人笔记、参考文档和外部窗口截图加入上下文。
- 保存可复用的上下文场景，切换不同讨论所需的背景资料。
- 跨请求保留转录与已完成回答；实际可提交的内容受模型上下文容量限制。
- 可选上下文预准备、推测生成与受支持通道的会话复用。

### 📝 会议辅助与双语内容

- 可选检测到问题后回答，或在停顿后回答，并设置响应节奏。
- 结束时生成包含摘要、决策、行动项、待解决问题和后续步骤的回顾。
- 界面、字幕和回答语言独立设置，支持中文、英文与双语内容。
- 会话在本地加密保存，支持恢复、搜索和导出。自动回答与暂停时回顾默认关闭。

### 🪟 桌面悬浮工作区

- 在设置页或监听布局菜单中切换经典玻璃与 Midnight Studio 深色工作台；宽窗口下支持转录与回答左右分栏。


### 📊 用量与响应观察

- 记录通道返回的 Token、请求和缓存用量；支持部分通道的额度或余额查询。
- 提供独立的模型测速与回答任务阶段信息。
- 测速是单次运行记录；本地用量不是完整的账户账单，未返回的数据保持未知。

## 模型接入

| 接入方式 | 支持的通道 | 准备工作 |
| --- | --- | --- |
| 本机 CLI | Codex、Claude Code、Antigravity、Kiro | 安装对应 CLI 并完成它自己的登录或身份验证 |
| 云端 API | Gemini、DeepSeek、Kimi、通义千问（北京）、Meta Muse | 配置对应服务的 API Key 与可用模型 |
| 本地模型服务 | LM Studio | 启动本地服务并加载兼容模型；启用认证时填写 Token |

CLI 通道沿用各自配置的身份验证与计费方式。应用不会自动继承当前 Codex 桌面聊天的登录状态；Antigravity CLI 的登录也独立于 Gemini API 额度。

可用模型、图片输入、思考强度和会话复用能力随通道而异。刷新目录后仍应使用模型测试确认实际调用权限；模型测试会发送请求，可能产生用量。

## 默认快捷键

| 快捷键 | 操作 |
| --- | --- |
| `Ctrl + Alt + Space` | 创建回答任务 |
| `Ctrl + Alt + T` | 切换置顶 |


## 常见问题

### 可以完全离线使用吗？

本地实时转录不需要云端语音识别服务。搭配已加载模型的本地 LM Studio 服务，可以使用本地模型回答；选择远程通道时，请求所需的转录、资料和图片会发送给对应服务。

### 为什么还没点“回答”就有用量？

上下文预准备、推测生成、字幕翻译和自动回答都可能提前调用模型。跨语言及双语字幕使用所选回答通道翻译。按需开启这些功能；取消任务不会撤回已经发送的内容或已产生的用量。

### 数据保存在哪里？

设置、会话与用量记录位于 `data/`，便携版位于 `_internal/data/`；临时文件位于 `work/`。API Key 和保存的会话内容使用绑定当前 Windows 用户的 DPAPI 加密。会话不保存原始音频；Markdown 和 JSON 导出为明文。

### 为什么切换模型后，旧回答没有变化？

新设置用于后续任务。已运行的任务保留启动时的模型和上下文，可以单独取消，或使用新模型重新提问。应用不设固定对话轮数截断，但仍受模型上下文窗口、内存和文件解析能力限制。

### 中文和英文可以分别设置吗？

可以。在设置中切换界面语言，听写工作区分别设置字幕语言与回答语言。英文是默认界面语言；切换界面不会清空已有转录或回答。

## 使用文档

详细技术文档主要使用英文。

| 文档 | 内容 |
| --- | --- |
| [用户指南](docs/USER_GUIDE.md) | 启动、音频、回答任务、上下文与会话 |
| [会议辅助](docs/MEETING_ASSISTANCE.md) | 自动回答、说话人标签、场景与会议回顾 |
| [界面说明](docs/GLASS_UI.md) | 悬浮工作区、背景与窗口操作 |
| [长问题与快速问答](docs/LONG_QUESTIONS.md) | 手动提交与预测策略 |
| [上下文预准备](docs/CONTEXT_PREPARATION.md) | 预准备、会话复用与推理控制 |
| [语言设置](docs/UI_LANGUAGE.md) | 界面、转录与回答语言 |
| [用量优化与暂停恢复](docs/TOKEN_OPTIMIZATIONS.md) | 上下文、图片和翻译缓存 |
| [提示词语言与 Token 基准](docs/PROMPT_TOKEN_BENCHMARK_2026-10-17.md) | 内部提示词语言选择与实测限制 |
| [文档索引](docs/README.md) | 更多指南、基准与历史验证记录 |
| [更新日志](CHANGELOG.md) | 版本变更 |

## 本地开发

使用 Windows x64、Python、Tkinter 和 Microsoft Edge WebView2 Runtime。当前 CI 使用 **Python 3.14**。源码仓库不包含已安装依赖、下载的模型、个人数据或生成的 EXE。

在项目根目录的 PowerShell 中运行：

```powershell
# 安装应用依赖
python -m pip install --only-binary=:all: --no-binary=proxy_tools --target vendor -r requirements.txt

# 下载并校验本地转录模型
python tools/setup_streaming.py --models-only

# 构建启动程序，然后运行
powershell -ExecutionPolicy Bypass -File tools/build_launcher.ps1
.\EchoCue.exe
```

<details>
<summary><strong>测试、打包与目录结构</strong></summary>

```powershell
# 后端回归测试
python tools/run_tests.py

# 安装 UI 测试依赖，运行无头 Edge 测试
python -m pip install -r requirements-dev.txt
python tools/run_ui_tests.py --require

# 打包便携版（需先准备依赖、模型与启动程序）
python tools/package_release.py
```

测试环境需要允许本地回环连接与桌面窗口创建，UI 测试还需要 Edge。默认打包产物为 `dist/EchoCue-Standard-<version>-windows-x64.zip`，排除个人 `data/` 和 `work/`。

| 目录 | 内容 |
| --- | --- |
| `app/` | Python 后端与 Web 界面 |
| `tests/`、`tests_ui/` | 后端与界面测试 |
| `tools/` | 安装、构建、打包与开发工具 |
| `docs/` | 使用指南、版本说明与验证记录 |
| `runtime/`、`vendor/` | 本地模型、运行资源与依赖 |
| `data/`、`work/` | 本地数据与临时文件，不提交到仓库 |

[Windows CI](https://github.com/YinhaoCui/EchoCue-Standard/actions/workflows/windows.yml) 在 `main` 推送、Pull Request 和手动触发时运行测试与构建。发布新版本时更新 `VERSION` 与对应的 `docs/releases/<version>.md`；`main` 构建通过后发布 ZIP 和 SHA-256 校验文件，已有 Release 保持不变。Pull Request 不发布版本。

</details>

## 反馈与贡献

通过 [Issues](https://github.com/YinhaoCui/EchoCue-Standard/issues) 提交问题或建议。报告问题时请附上版本、Windows 版本、所用通道和复现步骤；日志中请移除 Key 与私人对话内容。

欢迎提交改进文档、模型接入与使用体验的 Pull Request。
