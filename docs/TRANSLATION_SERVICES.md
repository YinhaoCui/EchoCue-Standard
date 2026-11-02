# 字幕专用翻译服务

字幕翻译可独立选择大模型、三个内置免 Key 接口、Google Cloud Translation 或 DLX 服务。回答平台、回答模型和问答上下文不受影响。入口为工作台「设置 → 模型与连接 → 字幕翻译模型」；经典界面位于「音频与转录」。

## 内置免 Key 翻译（无需 DLX 软件）

平台选择 `DeepL（内置免 Key）`、`谷歌翻译（内置免 Key）` 或 `微软翻译（内置免 Key）`，即可开始监听。英文界面对应 `DeepL (built-in)`、`Google Translate (built-in)`、`Microsoft Translator (built-in)`。

这三个实现直接包含在 EchoCue 的 Python 源码中，由应用直接发送 HTTPS 请求，不下载或启动 DLX，也不需要 API Key、Google Cloud 项目或微软订阅 Key。仍需联网，文本会发送到所选服务。不会把回答上下文、已有 Google Cloud Key 或 DLX 访问令牌发送给这些接口。

| 选项 | 调用方式 |
| --- | --- |
| DeepL | 参考 DLX 的匿名 oneshot 请求格式，直接访问 `oneshot-free.www.deepl.com/v1/translate` |
| Google | POST 表单至 `translate.googleapis.com/translate_a/single`，使用 `client=gtx`，拼接所有译文片段 |
| Microsoft | POST 文本数组至 Edge 的 `edge.microsoft.com/translate/translatetext`，自动检测原文语言 |

这些均为非官方开发者接口，可能限流、停用或改变格式，不能保证长期可用或不限量。DeepL 使用所查 DLX 版本中的请求字段与客户端版本信息，沿用 EchoCue 的普通 HTTPS 传输；没有引入 Go TLS 指纹库、动态 iOS 版本查询或 Cookie 预热。上游兼容性变化时需维护实现，内置并不会自动解除上游限流。

支持中、英及中英双语。为适配最严格的请求上限，原文按最多 1500 个 UTF-16 单元分段，完整送译，不截断长字幕。收到完整结果后更新字幕；沿用现有稳定片段预译、队列、缓存和过期结果保护。一次请求返回 429 后，该平台至少冷却 60 秒；如果 `Retry-After` 为更长的整数秒则遵守该等待时间，不立即重试，也不自动把文字发给其他平台。

2026-11-01 通过实际字幕翻译路由测试中译英和英译中，三个平台共六次请求全部成功，未启动 DLX。详细样本和测量边界见 [内置翻译实测](BUILTIN_TRANSLATION_BENCHMARK_2026-11-01.md)。

参考源码与归属：

- [DLX translate.go](https://github.com/OwO-Network/DLX/blob/83f97d336d145c56b06fb0316f7187f41954c664/translate/translate.go)，MIT，版权和许可原文见 [DLX_LICENSE.txt](DLX_LICENSE.txt)。
- [DeepSeek Harness 的匿名协议实现](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/experimental/translator/src/provider.ts)，MIT，许可见 [DEEPSEEK_HARNESS_LICENSE.txt](DEEPSEEK_HARNESS_LICENSE.txt)。

## Google Cloud Translation

1. 在 Google Cloud 项目启用 Cloud Translation API 和结算，创建适用于该 API 的 Key。
2. 将字幕翻译平台设为 `Google Cloud Translation`，填写独立的 API Key，点击保存。
3. 选择中文、英文或中英双语字幕，正常开始监听。

使用官方 Basic v2 接口的 `nmt` 模型；Key 通过请求头发送，不放在 URL 中。Google 按字符量结算，Google Meet 或 Gemini 订阅不代表获得此 API 的调用资格。此接口完整返回一次翻译，不提供逐字流；收到后立即更新字幕。稳定片段预译会增加请求及计费字符量。

Key 输入框始终为空，仅提示是否配置。只有启用现有「记住 API Key」选项，才随其他凭证保存在 Windows DPAPI 加密设置中；关闭该选项后只在本次运行中使用。也可在启动前设置 `GOOGLE_TRANSLATE_API_KEY` 环境变量。

官方说明：[Basic v2 translate](https://docs.cloud.google.com/translate/docs/reference/rest/v2/translate)、[计费](https://cloud.google.com/translate/pricing)。

## 可选 DLX 服务（保留原有接入方式）

`DLX` 选项连接独立服务，与前面的内置 DeepL 区分。如果安装了可选组件，第一次实际翻译时在后台启动它，默认监听 `127.0.0.1:1188`；无需另开终端。EchoCue 退出时关闭由它启动的 DLX。如果默认地址已经运行 DLX，则复用现有服务，不会关闭那个进程。端口被其他软件占用会提示启动失败。

默认地址为 `http://127.0.0.1:1188/translate`。也可以填写自行运行的服务地址：允许本机 HTTP 或 HTTPS 地址，自动补充 `/translate`。访问令牌选填，通过 `Authorization: Bearer` 请求头发送；保存方式与 Google Key 相同，也支持启动前的 `DLX_TOKEN` 环境变量。修改内置服务的令牌后，下次请求自动重启该组件使配置生效。

调用 `POST /translate`，自动识别原文语言，支持中文、英文及中英双语字幕。长文本按最多 1500 个 UTF-16 单元分段，完整送译；混合语言双语需要两次目标语言翻译。接口完整返回后更新字幕，沿用已有的预译、队列与过期结果保护。

DLX 是[独立开源项目](https://github.com/OwO-Network/DLX)，不是 DeepL 官方 API；本机组件仍需联网访问上游。可用性、速度和限流由上游决定，不保证免费额度或持续可用。2026-11-01 的一次实测中，本机组件约 1.1 秒启动成功，但翻译返回 HTTP 429；该次未取得成功译文，不能据此报告实际翻译速度。

### 组件与打包

- 固定使用上游 `v1.3.1` 的 Windows x64 资产 `deeplx_windows_amd64.exe`，本地保存为 `runtime/dlx/deeplx.exe`。
- SHA-256：`fa1107779606222578568053381989a2e921db270a10dd8128bd9dd2b7857f4b`。
- 组件遵循上游 MIT 许可证，随包保留 `runtime/dlx/LICENSE.txt`。不修改上游二进制。
- 只有需要独立 DLX 服务时，才使用 `python tools/setup_dlx.py` 下载并校验可选组件和许可证；正常安装与 Windows CI 不再要求下载 DLX。二进制不提交到 Git。
- 发布打包不要求存在 DLX。若本地已有可选组件，则保留组件和许可证；缺少对应许可证会报错，不收录 DLX 运行日志。内置翻译源码随正常应用文件打包，本次没有生成或发布新安装包。

## 验证范围

自动测试覆盖请求格式、中英双语、取消、错误提示、凭证不回传页面、按设置保存凭证、独立选择平台、切换时清理旧译文、长文本完整性、内置服务启动与复用、令牌更新后重启、仅关闭自身进程，以及打包保留组件与许可证。另使用真实本机 HTTP 替代服务验证字幕到服务的完整调用。

内置三个接口已完成真实双向短句测试，并验证不启动子进程、不读取官方付费凭证、格式异常、长文本完整性和 429 冷却。Google Cloud 未使用付费 Key 调用；独立 DLX 之前的测速遇到 429。不同实现和不同时刻的成功状态不能相互替代，也不能将短句请求时间当作语音到字幕的完整延迟。
