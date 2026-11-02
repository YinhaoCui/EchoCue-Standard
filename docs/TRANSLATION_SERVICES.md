# 字幕专用翻译服务

字幕翻译可独立选择大模型，或内置免 Key 的 DeepL、谷歌翻译、微软翻译。回答平台、回答模型和问答上下文不受影响。入口为工作台「设置 → 模型与连接 → 字幕翻译模型」；经典界面位于「音频与转录」。

## 内置免 Key 翻译

选择 `DeepL（内置免 Key）`、`谷歌翻译（内置免 Key）` 或 `微软翻译（内置免 Key）`，即可使用。英文界面对应 `DeepL (built-in)`、`Google Translate (built-in)`、`Microsoft Translator (built-in)`。

这三个实现直接通过 HTTPS 请求上游，不启动独立软件，不需要 API Key。它们使用非官方接口，可用性和限流可能变化。遇到 HTTP 429 时，应用会暂停该平台的后续请求至少 60 秒，避免持续重试。没有自动切换平台。

支持中文、英文和中英双语字幕。长文本按最多 1500 个 UTF-16 单元完整分段送译，沿用字幕预译、队列和过期结果保护。英文原文生成双语字幕时复用原文，只请求中文翻译。

## 已移除的接入方式

独立 `DLX` 服务和 `Google Cloud Translation` 付费接口已从平台列表、设置和调用路径移除，安装包也不再收录 DLX 组件。旧 DLX 选择迁移为内置 DeepL；旧 Google Cloud 选择迁移为内置谷歌翻译，并清除已失效的专用模型选择。旧令牌和 Cloud Key 不再读取或保存。

内置 DeepL 的协议参考 [DLX](https://github.com/OwO-Network/DLX)，其 MIT 许可证保留在 `docs/DLX_LICENSE.txt`。内置谷歌和微软的参考项目许可证保留在 `docs/DEEPSEEK_HARNESS_LICENSE.txt`。历史测速文档描述当时的测试结果，不代表已移除服务仍可选择。

## 验证范围

自动测试覆盖请求格式、双语、取消、错误提示、长文本完整性、429 冷却、平台选择与回答隔离、旧设置迁移、移除控件和打包排除 DLX。历史真实接口测速见 `BUILTIN_TRANSLATION_BENCHMARK_2026-11-01.md`；请求时间不能代表语音到字幕的完整延迟。
