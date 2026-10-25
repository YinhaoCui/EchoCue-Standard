"""The single table of answer providers.

Every other module asks this table what a provider is (local-login CLI or
API), where its model setting lives, whether it accepts screenshots and how
to call it, instead of repeating provider names.
"""
from dataclasses import dataclass
import re
import threading

# Provider names are persisted in saved settings; keep them byte-for-byte.
CODEX = 'Codex'
ANTIGRAVITY = 'Antigravity（本机登录）'
CLAUDE = 'Claude Code（本机登录）'
KIRO = 'Kiro（本机登录）'
META = 'Meta Muse'
GEMINI = 'Gemini'
KIMI = 'Kimi'
DEEPSEEK = 'DeepSeek'
QWEN = '通义千问（北京）'
LM_STUDIO = 'LM Studio'


@dataclass(frozen=True)
class Provider:
    name: str
    cli: bool = False
    model_option: str = ''   # advanced option holding a CLI provider's model ID
    note: str = ''           # one-line description shown with the provider
    model_note: str = '留空使用默认模型；也可输入模型 ID。'
    images: bool = True      # screenshots can be attached to answers
    stateful: bool = False   # keeps a resumable conversation between answers
    default_model: str = '默认'  # label used when the CLI model is left empty
    base: str = ''           # API base URL
    env: str = ''            # environment variable that may hold the API key


PROVIDERS = {p.name: p for p in (
    Provider(CODEX, cli=True, model_option='codex_model', note='Codex · 本机账号', stateful=True),
    Provider(ANTIGRAVITY, cli=True, model_option='antigravity_model', note='Antigravity · 本机账号',
             model_note='快速回答模式不改变此通道的模型档位；低思考档可能更快，但复杂问题推理能力可能下降。',
             stateful=True),
    Provider(CLAUDE, cli=True, model_option='claude_model', note='Claude Code · 沿用本机 CLI 身份验证，支持截图',
             model_note='Claude Code model catalog; refresh to read CLI metadata. Custom model IDs are supported.',
             stateful=True),
    Provider(KIRO, cli=True, model_option='kiro_model', note='Kiro · 沿用本机 kiro-cli 登录',
             model_note='Kiro model catalog; refresh to read kiro-cli models. Leave empty for auto.',
             default_model='auto'),
    Provider(META, note='Meta 官方 API · 支持转录与截图 · 使用 Meta Model API Key，按 API 用量计费。',
             base='https://api.meta.ai/v1', env='MODEL_API_KEY'),
    Provider(GEMINI, note='Gemini · API', env='GEMINI_API_KEY'),
    Provider(KIMI, base='https://api.moonshot.cn/v1', env='MOONSHOT_API_KEY'),
    Provider(DEEPSEEK, images=False, base='https://api.deepseek.com', env='DEEPSEEK_API_KEY'),
    Provider(QWEN, base='https://dashscope.aliyuncs.com/compatible-mode/v1', env='DASHSCOPE_API_KEY'),
    Provider(LM_STUDIO, note='LM Studio：本机服务，Key 可留空（启用认证时填写本地 Token）。', stateful=True,
             base='http://127.0.0.1:1234/v1', env='LM_STUDIO_API_KEY'),
)}

CLI_PROVIDERS = [p.name for p in PROVIDERS.values() if p.cli]
API_NAMES = [p.name for p in PROVIDERS.values() if not p.cli]
NAMES = [*CLI_PROVIDERS, *API_NAMES]
MODEL_OPTIONS = [PROVIDERS[name].model_option for name in CLI_PROVIDERS]
STATEFUL = {p.name for p in PROVIDERS.values() if p.stateful}


def get(name):
    return PROVIDERS.get(name, Provider(name))


def is_cli(name):
    return get(name).cli


def model_option(name):
    """The advanced option holding a CLI provider's model; KeyError for API providers."""
    option = get(name).model_option
    if not option:
        raise KeyError(name)
    return option


def accepts_images(name):
    return get(name).images


def note(name):
    provider = get(name)
    if provider.note:
        return provider.note
    return name + '：本地转录后仅发送文字；使用该平台自己的 Key，可能按量计费。'


def migrate(name):
    """Map provider names saved by older versions to current ones."""
    if name == 'DeepSeek 网页（手动粘贴）':
        return DEEPSEEK
    if 'Gemini CLI' in (name or ''):
        return ANTIGRAVITY
    return name if name in PROVIDERS else CODEX


def cli_answer(name, prompt, model, cancel, emit, *, on_usage=None, total_timeout=600, effort='自动',
               images=(), image_paths=(), session_key=None, thinking_policy='自动', transcript='', instructions=''):
    """Send one prompt through a local-login CLI provider and stream text to emit.

    prompt may be a string or a generation_context.ContextPrompt. Codex also
    receives the plain transcript and instructions it records with the turn.
    Transports are looked up on audio_answer at call time so one patch point
    covers every caller.
    """
    import audio_answer as a
    common = dict(on_usage=on_usage, total_timeout=total_timeout, effort=effort)
    lane = {'session_key': session_key} if session_key else {}
    if name == CODEX:
        sent = []

        def forward(text):
            sent.append(text)
            emit(text)
        result = a.codex_answer(transcript, instructions, cancel, model=model, on_text=forward, prompt_override=prompt,
                                **common, **lane, **({'image_paths': image_paths} if image_paths else {}))
        if not sent and result:
            emit(result)
        return result
    if name == CLAUDE:
        extra = {'images': images} if images else {}
        if thinking_policy != '自动':
            extra['thinking_policy'] = thinking_policy
        return a.claude_answer(a.ROOT, prompt, model, cancel, emit, **common, **extra, **lane)
    if name == KIRO:
        return a.kiro_answer(a.ROOT, prompt, model, cancel, emit, **common, **({'images': images} if images else {}))
    if name == ANTIGRAVITY:
        return a.antigravity_answer(a.ROOT, prompt, model, cancel, emit, **common, **lane,
                                    **({'images': images} if images else {}))
    raise ValueError('Not a local-login provider: ' + str(name))


def read_cli_models(name, *, details=False):
    """Read a CLI provider's model catalog.

    Returns (models, extra): extra is Codex's per-model capability list when
    details=True, or Antigravity's raw catalog text when no ID could be parsed.
    """
    import audio_answer as a
    if name == KIRO:
        from kiro_support import read_model_catalog
        return read_model_catalog(a.ROOT), None
    if name == CLAUDE:
        from claude_support import read_model_catalog
        return read_model_catalog(a.ROOT), None
    if name == CODEX:
        if details:
            items = a.read_codex_account(a.find_codex(), a.WORK, models_only='details')
            return [item['model'] for item in items], items
        return a.read_codex_account(a.find_codex(), a.WORK, models_only=True), None
    if name == ANTIGRAVITY:
        from antigravity_support import find_antigravity
        raw = a.run_process([find_antigravity(), 'models'], threading.Event(), timeout=30)
        models = list(dict.fromkeys(re.findall(r'\b(?:gemini|claude|gpt)-[A-Za-z0-9._-]+', raw)))
        return models, (None if models else raw)
    raise ValueError('Not a local-login provider: ' + str(name))
