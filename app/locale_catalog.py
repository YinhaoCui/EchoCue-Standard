"""English presentation catalog; Chinese strings remain stable internal identifiers."""
EN = dict(line.split('|',1) for line in '''
EchoCue  ·  实时工作台|EchoCue · Live workspace
设置中心|Settings
配置模型、音频与资料，点击准备进入监听工作台。|Configure your model, audio and context, then select Prepare.
回答平台与模型|Provider & model
音频与上下文|Audio & context
偏好与设备|Preferences & devices
音频与转录|Audio & transcription
资料与上下文|Files & context
回答方式|Answer provider
回答模式|Answer mode
回答模型|Answer model
模型分类|Model category
回答任务|Answer tasks
本轮要求 · 可选|Instructions · optional
开始转录|Start transcription
暂停转录|Pause transcription
继续转录|Resume transcription
转录已暂停|Transcription paused
开始／暂停转录|Start / pause transcription
转录已暂停；已有内容保留，正在生成的回答继续。|Transcription paused; existing text is retained and answers continue.
截图内容未变化，已复用现有截图。|Screenshot unchanged; reused the existing attachment.
只准备一个会话；后续回答复用，忙碌时按需新建。|Prepare one conversation; reuse it for answers and create another only when busy.
准备|Prepare
停止监听|Stop listening
开始监听|Start listening
生成回答|Generate answer
全部回复|All responses
任务卡片|Task cards
回复|Response
转录|Transcript
复制|Copy
保存设置|Save settings
记住 Key（本机加密）|Remember key (encrypted locally)
窗口置顶|Always on top
检测全部 API|Check all APIs
检测 Key|Check key
尚未检测|Not checked
测试所选模型|Test selected model
刷新官方模型目录|Refresh model catalog
刷新模型目录|Refresh models
刷新目录|Refresh catalog
刷新|Refresh
回答间保留全部对话|Keep all conversation history
开始监听即发送上下文|Send context when listening starts
要求模型思考|Thinking preference
思考强度|Reasoning effort
自动|Auto
服务默认|Service default
开启|On
关闭|Off
快速|Fast
推理|Reasoning
全部|All
未分类|Uncategorized
默认|Default
Gemini 快速回复|Gemini fast response
Codex · 本机账号|Codex · local account
Antigravity · 本机账号|Antigravity · local account
Antigravity（本机登录）|Antigravity (local login)
Claude Code（本机登录）|Claude Code (local login)
Kiro（本机登录）|Kiro (local login)
Kiro · 沿用本机 kiro-cli 登录|Kiro · local kiro-cli login
Claude Code · 沿用本机 CLI 身份验证，支持截图|Claude Code · local CLI authentication, supports screenshots
通义千问（北京）|Qwen (Beijing)
LM Studio：本机服务，Key 可留空（启用认证时填写本地 Token）。|LM Studio: local server. Leave the key blank unless authentication is enabled.
Meta 官方 API · 支持转录与截图 · 使用 Meta Model API Key，按 API 用量计费。|Meta API · transcript and screenshot input · uses your Meta Model API key; usage is billed by the provider.
本地服务，无需云端 Key；先刷新模型目录|Local server; no cloud key required. Refresh the model catalog first.
选择或刷新本地模型|Select or refresh a local model
填入 Key 后自动加密保存|Keys are encrypted and saved automatically
已加密保存，下次打开自动填入|Saved securely; restored on next launch
已加载本机加密配置|Loaded encrypted local settings
未保存 Key；快捷键和布局已保存|Key not saved; shortcuts and layout saved
保存失败，Key 仅在本次内存中；请检查目录权限|Save failed. The key remains in memory only; check folder permissions.
已有配置无法解密；请重新填写 Key 并保存。|Saved settings could not be decrypted. Enter your key again and save.
Key 或模型已修改，请重新检测。|Key or model changed. Run the check again.
播放设备|Playback device
整体界面不透明度|Window opacity
轻透 ← → 实色|Transparent ← → Opaque
本地实时转录 · 可在监听中切换|Local live transcription · switch while listening
转录语言 / 模型|Transcription language / model
转录引擎：待机|Transcription engine: idle
音频 / 转录 / 本地模型设置|Audio / transcription / local models
声音来源（停止监听后改）|Audio source (stop listening to change)
电脑 + 麦克风|System audio + microphone
电脑|System audio
麦克风设备|Microphone device
麦克风|Microphone
系统默认|System default
停顿多久后定稿|Pause before finalizing
快速 · 0.35 秒|Fast · 0.35 s
均衡 · 0.65 秒|Balanced · 0.65 s
稳妥 · 1.0 秒|Careful · 1.0 s
快速档更早定稿，但可能把一句话拆成多段；所有内容仍完整保留。|Fast mode finalizes sooner and may split a sentence. All content is retained.
会话增量同步（完整记录保留）|Incremental context (keep complete records)
准备备用会话（额外用量）|Prepare spare sessions (extra usage)
说完即预先生成回答|Generate ahead after speech
仅疑问句|Questions only
每段定稿|Every finalized segment
每次处理总时限（秒）|Request timeout (seconds)
不限时|No limit
输出 Token（可选限制）|Output tokens (optional limit)
LM Studio 本机服务地址|LM Studio server URL
打开 Antigravity：登录账号|Open Antigravity to sign in
应用并保存设置|Apply and save
应用到本次会话|Apply to this session
加密保存资料|Save context securely
个人资料 / 场景 / 目标|Profile / scenario / goals
参考文件内容（可编辑；不按字符数截断）|Reference documents (editable; no character truncation)
回答时带入本次会话全部对话（不限制轮数）|Include all conversation history (no turn limit)
导入文件|Import files
所有文件|All files
先分析资料|Analyze context
清空上下文|Clear context
上下文已本机加密保存。|Context saved with local encryption.
资料、历史和已保存的上下文已清空。|Documents, history and saved context cleared.
请先在“资料与上下文”导入文件或填写个人资料，并应用。|Import documents or enter a profile in Files & context, then apply.
音频设置已保存；可切换到监听工作台。|Audio settings saved. You can open the live workspace.
音频设置已改变，请重新开始监听。|Audio settings changed. Restart listening.
开启提前准备后，开始监听即向所选平台发送资料；也会在分析或回答时发送。文件仅作为参考。|With preparation enabled, context is sent when listening starts, and when analyzing or answering. Documents are reference material only.
不支持关闭时采用最低可用档位与直接回答提示|If off is unavailable, use the lowest supported effort and a direct-answer instruction
刷新模型目录可获取该模型支持的档位|Refresh the model catalog for supported effort levels
原生接口按模型能力应用思考开关；旧接口由服务控制|The native API applies supported reasoning settings; legacy APIs use server defaults
提前准备会产生调用用量；缓存命中由服务决定。|Preparation uses your quota; cache hits depend on the provider.
由模型或本地服务控制|Controlled by the model or local server
自动使用 CLI 默认强度|Auto uses the CLI default effort
自动跟随回答模式；手动选择优先|Auto follows the answer mode; manual selection takes priority
预算 |Budget 
监听工作台|Live workspace
监听布局设置|Workspace layout
点击准备进入监听工作台，再按回答键生成答案|Select Prepare to enter the live workspace, then Answer to generate
监听中|Listening
监听已停止|Listening stopped
已停止|Stopped
回答中|Answering
最近任务 #|Latest task #
任务 #|Task #
任务|Tasks
回答|Answer
设置|Settings
更多|More
结束|Exit
窗口|Window
用量与额度|Usage & quota
详细 Token / Codex 额度|Token details / Codex quota
用量|Usage
DeepSeek 余额|DeepSeek balance
Kimi 余额|Kimi balance
Qwen 官方用量|Qwen usage portal
刷新 Codex 官方额度|Refresh Codex quota
打开 Gemini 官方用量页|Open Gemini usage portal
Codex 官方额度尚未查询。|Codex quota has not been checked.
DeepSeek 官方余额：尚未查询。|DeepSeek balance has not been checked.
Kimi 官方余额：尚未查询。|Kimi balance has not been checked.
取消全部回答|Cancel all answers
取消所选任务|Cancel selected task
继续所选回答|Continue selected answer
清空缓存|Clear audio buffer
本次转录记录|Session transcripts
查看全部实时转录|Show live transcript
用当前模型回答所选转录|Answer selected transcript with current model
会话与工具|Session & tools
会话记录 / 恢复|Session history / restore
编辑转录|Edit transcript
术语表|Glossary
搜索本次会话|Search this session
搜索|Search
导出|Export
本机加密会话|Encrypted local sessions
会话每 5 秒本机加密保存|Session encrypted locally every 5 seconds
最后保存|Last saved
恢复选中会话|Restore selected session
删除选中记录|Delete selected record
删除会话|Delete session
删除选中的本机保存记录？此操作不可恢复。|Delete the selected local session? This cannot be undone.
请先停止监听并等待回答结束，再恢复会话。|Stop listening and wait for answers to finish before restoring a session.
会话已恢复；未完成的任务保留正文，可手动重试。|Session restored. Interrupted answers are retained and can be retried.
已中断（从会话恢复）|Interrupted (restored session)
请先选择需要修改的转录。|Select a transcript to edit first.
保存修改|Save changes
保存并用当前模型回答|Save and answer with current model
保存术语表|Save glossary
已导出会话；导出文件是可阅读的明文。|Session exported as readable plaintext.
上下文 ▸|Context ▸
上下文 ▾|Context ▾
加入上下文|Add to context
截取窗口|Capture window
最近截图|Recent screenshots
暂无截图|No screenshots
查看 / 编辑资料|View / edit context
查看全部截图|View all screenshots
查看截图|View screenshot
补充文本 · 下次回答时自动加入会话资料|Additional text · included with your next answer
补充文本已加入上下文，后续回答会带入。|Text added to context for subsequent answers.
截取活动窗口|Capture active window
上下文截图|Context screenshots
移除所选截图|Remove selected screenshot
点击截图查看；移除后不再用于新的回答。截图中如有黑屏，请移除后重试。|Select a screenshot to view it. Removed images are excluded from new answers. Remove black captures and try again.
请先切到需要截图的窗口，再返回点击“截取活动窗口”。|Switch to the target window first, then return and select Capture active window.
截图已加入上下文：|Screenshot added to context: 
上下文已变更，本次截图未加入，请重新截图。|Context changed during capture. Capture the window again.
未命名窗口|Untitled window
正在截取：|Capturing: 
；可点击“查看截图”检查。|; select View screenshot to check it.
快捷键设置…|Keyboard shortcuts…
快捷键设置|Keyboard shortcuts
全局快捷键|Global shortcuts
恢复默认|Restore defaults
保存并应用|Save and apply
正常交互|Interactive
已置顶|Always on top
等待快捷键注册|Waiting for shortcut registration
在快捷键设置中自定义按键|Customize keys in Keyboard shortcuts
例如 Ctrl+Alt+P 或 Ctrl+Shift+F8。保存后立即生效。|For example Ctrl+Alt+P or Ctrl+Shift+F8. Changes apply when saved.
不同功能不能使用相同快捷键。|Each action must use a different shortcut.
快捷键必须包含修饰键和一个主键。|A shortcut requires modifiers and one main key.
使用 Ctrl/Alt/Shift/Win + 字母、数字、F1–F24 或 Space。|Use Ctrl/Alt/Shift/Win plus a letter, digit, F1–F24 or Space.
设置已保存。注册结果见下方；被占用的组合请重新修改。|Settings saved. Check registration below; change shortcuts already in use.
请先恢复鼠标操作，再修改快捷键。|Restore mouse interaction before editing shortcuts.
快捷键已应用 · |Shortcuts applied · 
快捷键不可用：|Shortcut unavailable: 
正在更新快捷键…|Updating shortcuts…
正在注册快捷键…|Registering shortcuts…
模型测速|Model speed test
Coding 回答测速|Coding speed test
平台|Provider
时间|Time
总耗时|Total time
平均字/秒|Chars / second
输出Token|Output tokens
首段等待|Time to first text
结果|Result
开始 Coding 测速|Start coding test
取消测速|Cancel test
测速中 · |Testing · 
内置题目：实现 unique_in_order(items)，整数列表去重并保持顺序，O(n)，附三种情况的 assert 测试。|Built-in task: implement unique_in_order(items), deduplicate integers in O(n), preserve order, and add three assertion tests.
独立选择测速模型，不改变正常回答配置。固定 Python 编程题，不带入个人资料或转录；云端请求可能计费。|Choose a test model independently. Uses a fixed Python task without personal context or transcripts. Cloud requests may incur charges.
选择平台与模型后开始；CLI 模型留空使用默认。Key 和本地服务地址沿用已配置值。|Choose a provider and model. Leave the CLI model blank for its default. Uses your configured key and local server address.
已记录用量。测试只代表本次编程题；结果不自动执行或判定代码正确性。|Usage recorded. Results apply to this coding task only; generated code is not executed or graded.
请先选择回答模型。|Select an answer model first.
请先在主窗口填写 API Key。|Enter an API key in Settings first.
请先在主窗口设置该平台的 API Key。|Set this provider's API key in Settings first.
已加载常用别名；可用模型以账号权限为准，也可输入完整 ID。|Common aliases loaded. Availability depends on your account; you may enter a full model ID.
目录读取失败；请检查登录、Key 和网络，也可手动填写模型 ID。|Could not load the catalog. Check login, key and network, or enter a model ID.
使用默认|Use default
选择低延迟档|Choose low latency
留空使用默认模型；也可输入模型 ID。|Leave blank for the default, or enter a model ID.
常用模型别名，非账号权限目录；可填写完整模型 ID，留空使用 CLI 默认。|Common aliases, not an account-access catalog. Enter a model ID or leave blank for the CLI default.
已加载常用别名（非账号权限目录）；也可输入完整模型 ID。|Common aliases loaded (not account entitlements). You may enter a full model ID.
正在读取账号模型目录…|Loading account model catalog…
Antigravity 模型目录|Antigravity model catalog
从目录复制模型 ID，填入主窗口的回答模型。|Copy a model ID into the answer model field.
目录读取失败，请检查该 CLI 的登录和网络；仍可手动输入模型 ID。|Catalog unavailable. Check CLI login and network, or enter a model ID manually.
快速回答模式不改变此通道的模型档位；低思考档可能更快，但复杂问题推理能力可能下降。|Fast mode does not change this provider's model tier. Lower effort may be faster but less effective on complex tasks.
账号目录没有当前模型同系列的低思考档；保留原模型，请在目录中选择其他模型测速。|No lower-effort variant of this model was found. The current model is retained; select another to test.
正在运行|Running
处理中|Processing
正文生成 |Text generation 
按键到接收 |Key to receipt 
按键到显示 |Key to display 
本机派发 |Dispatch 
转录等待 |Transcription wait 
资料准备 |Context preparation 
模型首字 |Model first text 
模型等待 |Model wait 
界面排队 |UI queue 
等待转录定稿|Waiting for finalized transcript
预生成采用率 |Prediction adoption rate 
预生成命中|Prediction adopted
实时生成|On-demand generation
预生成|Pre-generated
正文|Text
重试|Retry
继续|Continue
已取消|Cancelled
取消|Cancel
完成|Complete
失败|Failed
未报告|Not reported
不可测|Not measured
未知|Unknown
输出截断|Output truncated
读取失败|Read failed
恢复失败|Restore failed
导入失败|Import failed
导出失败|Export failed
设置错误|Settings error
启动失败|Startup failed
模型测试可能产生费用|Model tests may incur charges
测试失败|Test failed
测试完成|Test complete
连通性测试|Connectivity test
全部 API 检测结果|API check results
尚未监听。选择播放设备，然后点击“准备”。|Not listening. Choose a playback device, then select Prepare.
准备中：正在启动监听，随后准备模型上下文…|Preparing: starting audio, then preparing model context…
已停止监听并清空两个声源的缓存。|Listening stopped; both audio buffers cleared.
已切换设备，请点击“开始监听”。|Device changed. Start listening again.
实时转录：尚未监听|Live transcription: not listening
实时转录：已跟上语音|Live transcription: up to date
实时转录：待处理 |Live transcription: pending 
实时转录中：|Transcribing: 
。说完后稍候可见文字；按快捷键只触发回答。|. Text appears after speech; the answer shortcut triggers generation only.
正在保存会话并关闭…|Saving session and closing…
正在查询 Codex 官方账号额度…|Checking Codex account quota…
正在检测接口…|Checking API…
正在测试所选模型…|Testing selected model…
正在读取官方目录，不发送生成请求…|Loading the official catalog without generating an answer…
正在转录本次音频…|Transcribing this audio…
音频缓存已清空。|Audio buffer cleared.
本次转录已取消。|Transcription cancelled.
拖动分隔线调整阅读空间|Drag the divider to resize the reading panes
正在发送上下文；监听与回答可继续。|Sending context; listening and answering remain available.
上下文准备请求已完成；可续接通道将复用空闲会话。|Context preparation complete. Supported providers will reuse idle sessions.
上下文准备已停止；下次回答仍会携带完整资料。|Context preparation stopped. Your next answer will still include the full context.
上下文已发送；后续携带完整资料，缓存命中由服务决定。|Context sent. Future requests include all reference material; caching depends on the provider.
开始回答；转录和其他回答继续进行…|Generating; transcription and other answers continue…
回答已结束。若提示输出上限，可选中此任务继续回答。|Answer finished. If output was truncated, select this task and Continue.
等待按键之前已收集语音的转录完成…|Waiting for transcription of audio captured before the key press…
已取消全部回答；实时转录继续。|All answers cancelled; live transcription continues.
此任务结束|Task finished
已完成|Complete
失败，可重试|Failed; retry available
准备上下文或回答时发送|Sent during context preparation or answering
张截图|screenshots
字资料|characters of context
积压 |Backlog 
处理等待 |Processing wait 
正在追赶，音频完整保留|Catching up; all audio is retained
尚无正文|no text yet
次 · 按键到显示中位 |samples · median key-to-display 
取消和失败不记为零延迟|Cancellations and failures are not counted as zero latency
秒|s
段|segments
已读取 |Loaded 
已选择 |Selected 
个模型；可用权限以账号为准。|models; availability depends on your account.
个模型；请选择或输入模型 ID。|models; select or enter a model ID.
模型|Model
资料|Context
会话|Session
截图|Screenshot
；仅后续回答使用此档位，完整上下文保留。|; applies to future answers only; complete context is retained.
请先填写当前平台的 API Key。|Enter this provider's API key first.
请先填写当前平台的 Key，再刷新模型目录。|Enter this provider's key before refreshing the model catalog.
请先停止监听再刷新设备。|Stop listening before refreshing devices.
请选择播放设备。|Select a playback device.
请选择实际麦克风设备。|Select a physical microphone device.
未发现播放设备，请连接耳机或扬声器后重启工具。|No playback device found. Connect headphones or speakers and restart the app.
无法开始监听：|Could not start listening: 
无法切换转录模型：|Could not change transcription model: 
音频采集已中断：|Audio capture interrupted: 
麦克风采集失败：|Microphone capture failed: 
中文 · Zipformer|Chinese · Zipformer
英文 · Zipformer|English · Zipformer
中英混合 · Paraformer|Chinese + English · Paraformer
文字（先转录）|Text (transcribe first)
本轮要求|Instructions
补充要求：|Additional instructions: 
未收到答案文字|No answer text received
网络连接失败或超时，请检查网络后重试。|Connection failed or timed out. Check your network and retry.
身份验证失败，请检查 API Key。|Authentication failed. Check your API key.
API Key 无效或已过期，请重新复制或创建 Key。|API key is invalid or expired. Copy it again or create a new key.
服务暂时不可用，请稍后重试。|Service temporarily unavailable. Try again later.
音频设备已断开，请重新选择设备。|Audio device disconnected. Select a device again.
没有识别到语音，请检查音频来源和输入音量。|No speech detected. Check the audio source and input volume.
没有可用的转录文字。|No transcript is available.
请开始监听；说完一句后即可看到转录。|Start listening. Transcription appears after each sentence.
没有访问权限，请检查项目、Key 限制及服务开通状态。|Access denied. Check the project, key restrictions and service access.
自定义模型|Custom model
自定义模型：价格和能力请核对官方说明。|Custom model: check the provider's documentation for pricing and capabilities.
处理中，已有内容已保留|Processing; existing content retained
处理失败，已有内容已保留|Request failed; existing content retained
预算|Budget
未填写 Key，已跳过。|No key entered; skipped.
用量记录保存失败，本次统计仅保留在内存。|Could not save usage; this session's statistics remain in memory.
界面语言|Interface language
English / 中文|English / 中文
'''.strip().splitlines() if '|' in line)

EN.update({
    '全部平台：本工具观察到的 token 用量（不等于账户余额或账单）':'All providers: token usage observed by this app (not your account balance or bill)',
    '未返回用量的请求记为未知，不按零计算。思考/缓存通常是其他字段的子集，不能再次相加。':'Requests without usage reports are unknown, not zero. Reasoning/cache tokens usually overlap other fields; do not add them again.',
    '历史文件不可读，本次仅在内存统计，未覆盖原文件。':'History could not be read. Statistics are kept in memory; the original file was not overwritten.',
    '尚未记录请求。更新前的用量无法补录。':'No requests recorded yet. Earlier usage cannot be reconstructed.',
    'Codex 官方账号额度（账号共享，并非仅本工具）':'Codex account quota (shared across your account, not only this app)',
    'Codex 未提供此数据，请检查 ChatGPT 登录、CLI 版本及账号权限。':'Codex did not provide this data. Check ChatGPT login, CLI version and account access.',
    'Codex 查询进程未能启动或已退出，请在正常桌面启动工具后重试。':'The Codex query process could not start or exited. Launch this app from the desktop and retry.',
    'Codex 额度查询超时，请检查登录和网络。':'Codex quota query timed out. Check login and network.',
    'Gemini：本工具累计用量（含模型测试，跨 Key 合计；不是项目总用量）':'Gemini: usage recorded by this app (includes tests and all keys; not project-wide usage)',
    '历史用量文件不可读；未覆盖原文件，本次仅显示内存统计。':'Usage history could not be read. The original file was retained; showing in-memory statistics.',
    '官方累计 token：未提供。':'Official cumulative tokens: unavailable.',
    '官方累计 token：':'Official cumulative tokens: ',
    '服务未返回可用的额度窗口；剩余未知。':'The service returned no quota window; remaining quota is unknown.',
    '缺失用量报告的请求未计入 token；取消/失败仍可能计费。剩余额度未知，请查看 AI Studio。':'Requests without usage reports are not included in token totals. Cancelled/failed requests may still be billed. Check AI Studio for remaining quota.',
    '更新时间：':'Updated: ', '：已用 ':': used ', '%，剩余 ':'%, remaining ', '%；重置 ':'%; resets ',
    ' 分钟':' minutes', ' 小时':' hours', ' 天':' days', ' 次有报告；':' reported; ', ' 次请求，':' requests, ',
    ' 次，完成 ':' requests, completed ', ' 次；输入 ':' requests; input ', ' token；收到用量报告 ':' tokens; usage reports ',
    '缓存命中':'Cache hit', '输入':'Input', '输出':'Output', '总计':'Total', '思考':'Reasoning',
    '上下文未发送：':'Context not sent: ', '上下文准备失败：':'Context preparation failed: ',
    '已取消此回答。':'This answer was cancelled.',
    '当前 LM Studio 不支持原生会话接口；使用完整上下文兼容模式，思考由本地服务控制。':'This LM Studio version has no native session API. Using full-context compatibility mode; reasoning is controlled by the local server.',
    '当前通道尚未接入图片输入。请选择 Codex、Gemini 或其他视觉模型，或在“查看截图”中移除图片。':'This provider does not support image input here. Choose a vision-capable model or remove images in View screenshots.',
    '该任务尚无转录，请等待转录完成后重试。':'This task has no transcript yet. Wait for transcription and retry.',
    '该任务没有已生成的答案，请用转录重答。':'This task has no answer yet. Retry using its transcript.',
    '请先选择一个已结束的回答；正在进行的任务会继续运行。':'Select a finished answer first. Running tasks will continue.',
    '请先选择一段转录。':'Select a transcript first.',
    '请刷新本地模型目录并选择模型。':'Refresh local models and select one.',
    '请填写当前平台的 Key。':'Enter a key for this provider.',
    'Token 用量保存失败，本次统计仅在内存。':'Token usage could not be saved; statistics remain in memory.',
    '快速 / 省钱':'Fast / budget',
    '低延迟、低成本的日常问答':'Low-latency, low-cost everyday Q&A',
    '新一代 Flash，复杂任务与代码问答':'New-generation Flash for complex tasks and coding',
    '复杂软件与多步任务':'Complex software and multi-step tasks',
    '速度与多模态能力平衡':'Balanced speed and multimodal capability',
    '通用 Flash':'General-purpose Flash',
    '轻量低成本':'Lightweight, low cost',
    '高能力预览版；可用性可能变化':'High-capability preview; availability may change',
    'Flash 预览版':'Flash preview',
    '旧版低成本备选':'Earlier low-cost option',
    '旧版平衡备选':'Earlier balanced option',
    '旧版复杂任务备选':'Earlier option for complex tasks',
    '标准模式；日常问答、截图和代码任务':'Standard mode: everyday Q&A, screenshots and coding',
    '标准模式；复杂推理和软件工程任务':'Standard mode: complex reasoning and software engineering',
    '上一代标准模式备选':'Previous-generation standard option',
    '早期标准模式备选':'Earlier standard option',
    '可关闭思考，适合日常问答':'Supports disabling thinking; suitable for everyday Q&A',
    '旗舰推理；始终思考，快速模式降低思考强度':'Flagship reasoning; always thinks, fast mode lowers effort',
    'Code 高速服务版本；始终思考，不等于更便宜':'High-speed Code service; always thinks, not necessarily cheaper',
    '代码专用；始终思考':'Coding-focused; always thinks',
    'V4.1 Flash；快速模式关闭思考':'V4.1 Flash; fast mode disables thinking',
    'V4 Pro；适合复杂推理和代码':'V4 Pro; complex reasoning and coding',
    '新一代轻量模型，成本优先':'New-generation lightweight model, cost-focused',
    '旗舰复杂推理，成本更高':'Flagship complex reasoning, higher cost',
    '代码和 Agent 能力与成本平衡':'Balances coding, agent capabilities and cost',
    '轻量备选':'Lightweight alternative',
    '专用代码模型':'Dedicated coding model',
    '轻量代码模型':'Lightweight coding model',
    '代码模型备选':'Alternative coding model',
    '旧版平衡模型':'Earlier balanced model',
    '旧版轻量模型':'Earlier lightweight model',
    '保留旧版选择，权限以账号为准':'Legacy option; access depends on your account',
    '接口发现或自定义模型；请核对能力、输入类型和费用':'Discovered or custom model; verify capabilities, input types and costs',
    'Contributor 模式：提交内容可能用于训练 Meta 模型；标准模式请选择不带 contributor 的版本。':'Contributor mode: submitted content may be used to train Meta models. For standard mode, choose a model without contributor in its ID.',
    '首段等待包含网络与思考；平均字/秒=答案字符数÷总耗时，不等于模型解码 Token/s。流式接口收到首段正文即显示。':'Time to first text includes network and reasoning time. Chars/s is answer characters divided by total time, not decoding tokens/s. Streaming responses appear as soon as text arrives.',
    ' · 本次 ':' · session ', ' 次 / 已报告 ':' requests / reported ',
    ' · 思考：':' · reasoning: ', '文字回答':'Text answer', '资料分析':'Context analysis',
    '已创建独立任务 #':'Created independent task #', '，此前任务继续运行。':'; earlier tasks continue.',
    ' 使用说完时已开始的预生成回答。':' uses an answer pre-generated after speech.',
    ' 个任务':' tasks', ' · 正在回答 ':' · active answers ',
    '已报告 Token ':'Reported tokens ', '执行中，等待服务返回用量':'Running; waiting for provider usage data',
    ' 次总量未知':' requests with unknown totals', ' / 总 Token ':' / total tokens ',
    ' 次调用 · 已报告输入 ':' requests · reported input ', ' / 输出 ':' / output ', ' / 累计 ':' / cumulative ',
    'Qwen 账户免费额度/账单请查看官方用量页；上方是本工具观察值。':'Check Qwen’s official usage page for free quota and billing. Values above are observed by this app.',
    'Qwen 账户额度请查看官方用量页；下方为本工具记录。':'Check Qwen’s official page for account quota. App usage records follow below.',
    '旧版 Gemini 记录：':'Legacy Gemini records:',
    '：正在查询官方余额…':': checking account balance…',
    '：请先在展开设置中填写 API Key。':': enter an API key in Settings first.',
    'Codex 官方额度查询失败，剩余未知。请确认 Codex 已通过 ChatGPT 登录，并从正常桌面启动本工具后重试。':'Could not retrieve Codex quota. Ensure Codex is signed in with ChatGPT, then launch this app from the desktop and retry.',
    '当前模型不支持所选思考设置。':'This model does not support the selected reasoning setting.',
    '截图数据无效，请重试。':'Invalid screenshot data. Try again.',
    '截图超时，请检查目标窗口是否无响应。':'Screenshot timed out. Check whether the target window is responding.',
    '无法截取该窗口：请保持窗口打开且未最小化；受保护窗口可能无法截图。':'Could not capture this window. Keep it open and not minimized; protected windows may block capture.',
    '窗口尚未就绪':'Window is not ready',
    '保存失败，请检查目录写入权限。':'Save failed. Check folder write permissions.',
    '设置已保存；快捷键线程不可用，请重启程序。':'Settings saved, but the shortcut service is unavailable. Restart the app.',
    '等待回答\n\n准备完成后点击“回答”，或使用窗口菜单中设置的快捷键。':'Waiting for an answer\n\nSelect Answer when ready, or use your configured shortcut.',
    '等待语音输入\n\n开始监听后，实时字幕将显示在这里。':'Waiting for audio\n\nLive captions will appear here when listening starts.',
    '一句话定稿并稳定 0.35 秒后在后台开始回答；按快捷键时若转录与设置未变，直接显示已生成内容。\n按键采用前核对转录、资料、模型与设置；不匹配则丢弃并重答。未采用的预生成不进入对话，但仍计入用量。':'Generate in the background after finalized speech is stable for 0.35 seconds. The answer shortcut adopts matching predictions immediately.\nTranscript, context, model and settings must still match. Discarded predictions do not enter conversation history, but may still consume quota.',
    '转录与回答独立：英文 / 中文使用 Zipformer，中英混合使用 Paraformer。\n同时采集时分开转录并标注声源；建议戴耳机，减少麦克风重复录入扬声器声音。\nLM Studio：在 Developer 页面启动服务，再回主窗口刷新模型目录。':'Transcription and answering are independent: Zipformer for English or Chinese, Paraformer for mixed speech.\nSources are transcribed separately. Headphones help prevent microphone echo.\nLM Studio: start its local server, then refresh models here.',
    '切换到监听工作台或回答时自动应用资料。分析结果用于后续回答。\nDOCX 导入正文；文字型 PDF 需 setup_context.cmd。扫描件需先 OCR。\n上下文仍可能超过所选模型窗口；可删除原文件内容，仅保留所需摘要。':'Context is applied when opening the live workspace or answering. Analysis is used in later answers.\nDOCX text and text-based PDF are supported when dependencies are installed; scanned files need OCR.\nModel context limits still apply. You can replace document text with your own summary.',
    '每行一个术语，供回答参考；纠错使用“识别错误 => 正确术语”。\n纠错仅应用于后续语音，替换结果请核对。':'One term per line. To correct recognition, use "recognized text => correct term".\nCorrections apply to future speech only; please check the results.',
    '提词器 HUD':'Teleprompter HUD',
    '提词器':'Teleprompter',
    '灵动胶囊':'Mini pill',
    '胶囊':'Mini',
    '展开':'Expand',
    '双栏':'Split view',
    '复制代码':'Copy code',
    '已复制代码。':'Code copied to clipboard.',
    '自动跟随':'Auto-scroll',
    '实时字幕':'Live caption',
    '电脑 · 识别中':'System audio · live',
    '麦克风 · 识别中':'Microphone · live',
    '等待语音输入…':'Waiting for speech…',
    '正在监听语音输入…':'Listening for speech…',
    '监听待机 · 按快捷键回答':'Ready · press shortcut to answer',
})

EN.update({'转录语言':'Transcript language','回答语言':'Answer language','原文':'Original'})
EN.update({
    '等待快捷键注册': 'Waiting for shortcut registration',
    '设置已保存，等待快捷键重新注册。': 'Settings saved. Waiting for shortcut registration.',
    '设置已保存；快捷键线程不可用，请重启程序。': 'Settings saved; the shortcut thread is unavailable. Restart the application.',
    '保存失败，请检查目录写入权限。': 'Could not save settings. Check directory write permissions.',
    '不同功能不能使用相同快捷键。': 'Each action must use a different shortcut.',
    '快捷键必须包含修饰键和一个主键。': 'Include modifiers and one main key.',
    '使用 Ctrl/Alt/Shift/Win + 字母、数字、F1–F24 或 Space。': 'Use Ctrl/Alt/Shift/Win with a letter, number, F1-F24, or Space.',
})

EN.update({'提问模式':'Question mode','长问题':'Long question','快速问答':'Quick Q&A','长问题：听完后点击回答；快速问答：允许预生成。':'Long question: select Answer when finished. Quick Q&A: predictions allowed.'})

EN.update({'中英双语':'Chinese + English'})

EN.update({
    '目录来源：最近一次成功获取。':'Catalog source: last successful refresh.',
    '目录来源：内置预设，尚未验证可用性。':'Catalog source: built-in presets; availability not verified.',
    '尚未获取本地模型目录，请刷新或手动填写模型 ID。':'Local catalog not loaded. Refresh or enter a model ID.',
    '尚未获取账号模型目录，请刷新或手动填写模型 ID。':'Account catalog not loaded. Refresh or enter a model ID.',
    '目录读取失败；保留原列表，请检查登录、Key 和网络，也可手动填写模型 ID。':'Catalog refresh failed. Previous list retained; check login, key and network, or enter a model ID.',
})
