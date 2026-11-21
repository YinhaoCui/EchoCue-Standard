"""Offline model presets and descriptions; successful discovery replaces presets."""

import re

CATEGORIES = ('全部', '快速 / 省钱', '推理', 'Coding', '未分类')
# Categories describe suitable tasks, not exclusive capabilities or speed guarantees.
CATALOG = {
    'Meta Muse': {
        'muse-spark-1.3': ('快速 / 省钱,推理,Coding', '标准模式；日常问答、截图和代码任务'),
        'muse-wonder-1.0': ('推理,Coding', '标准模式；复杂推理和软件工程任务'),
        'muse-spark-1.2': ('推理,Coding', '上一代标准模式备选'),
        'muse-spark-1.1': ('推理,Coding', '早期标准模式备选'),
    },
    'Gemini': {
        'gemini-3.5-flash-lite': ('快速 / 省钱', '低延迟、低成本的日常问答'),
        'gemini-3.8-flash': ('快速 / 省钱,推理,Coding', '新一代 Flash，复杂任务与代码问答'),
        'gemini-3.7-flash': ('推理,Coding', '复杂软件与多步任务'),
        'gemini-3.6-flash': ('快速 / 省钱,推理', '速度与多模态能力平衡'),
        'gemini-3.5-flash': ('快速 / 省钱,推理', '通用 Flash'),
        'gemini-3.1-flash-lite': ('快速 / 省钱', '轻量低成本'),
        'gemini-3.1-pro-preview': ('推理,Coding', '高能力预览版；可用性可能变化'),
        'gemini-3-flash-preview': ('快速 / 省钱,推理,Coding', 'Flash 预览版'),
        'gemini-2.5-flash-lite': ('快速 / 省钱', '旧版低成本备选'),
        'gemini-2.5-flash': ('快速 / 省钱,推理', '旧版平衡备选'),
        'gemini-2.5-pro': ('推理,Coding', '旧版复杂任务备选'),
    },
    'Kimi': {
        'kimi-k2.6': ('快速 / 省钱,推理,Coding', '可关闭思考，适合日常问答'),
        'kimi-k3': ('推理,Coding', '旗舰推理；始终思考，快速模式降低思考强度'),
        'kimi-k2.7-code-highspeed': ('Coding', 'Code 高速服务版本；始终思考，不等于更便宜'),
        'kimi-k2.7-code': ('推理,Coding', '代码专用；始终思考'),
    },
    'DeepSeek': {
        'deepseek-flash': ('快速 / 省钱,推理,Coding', 'V4.1 Flash；快速模式关闭思考'),
        'deepseek-v4-pro': ('推理,Coding', 'V4 Pro；适合复杂推理和代码'),
    },
    '通义千问（北京）': {
        'qwen3.8-flash': ('快速 / 省钱,推理,Coding', '新一代轻量模型，成本优先'),
        'qwen3.8-max': ('推理,Coding', '旗舰复杂推理，成本更高'),
        'qwen3.7-plus': ('推理,Coding', '代码和 Agent 能力与成本平衡'),
        'qwen3.7-flash': ('快速 / 省钱,推理', '轻量备选'),
        'qwen3-coder-plus': ('Coding', '专用代码模型'),
        'qwen3-coder-flash': ('快速 / 省钱,Coding', '轻量代码模型'),
        'qwen3-coder-next': ('Coding', '代码模型备选'),
        'qwen3.6-plus': ('推理,Coding', '旧版平衡模型'),
        'qwen3.6-flash': ('快速 / 省钱,推理', '旧版轻量模型'),
        'qwen3.5-plus': ('推理,Coding', '旧版平衡模型'),
        'qwen3.5-flash': ('快速 / 省钱,推理', '旧版轻量模型'),
        'qwen-flash': ('快速 / 省钱', '保留旧版选择，权限以账号为准'),
    },
}


def describe(provider, model):
    if provider == 'Meta Muse' and model.endswith('-contributor'):
        return '[推理,Coding] Contributor 模式：提交内容可能用于训练 Meta 模型；标准模式请选择不带 contributor 的版本。'
    tags, note = CATALOG.get(provider, {}).get(model, ('未分类', '接口发现或自定义模型；请核对能力、输入类型和费用'))
    return f'[{tags}] {note}。'


def chat_candidate(model):
    return not any(
        word in model.lower()
        for word in (
            'embedding',
            'embed-',
            'tts',
            'transcribe',
            'imagen',
            'veo',
            'image-generation',
            'native-audio',
            'live',
            'realtime',
            'rerank',
            '-image',
            'nano-banana',
            'omni-',
            'lyria',
            'computer-use',
        )
    )


EFFORT_ORDER = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')
_VERSION = re.compile(r'\d+(?:\.\d+)*')


def _parts(model):
    """Split an ID into (family, version, snapshot date, effort rank) for ordering only."""
    tokens = model.lower().split('-')
    effort = 0
    if len(tokens) > 1 and tokens[-1] in EFFORT_ORDER:
        effort = EFFORT_ORDER.index(tokens.pop()) + 1
    family, version, date = [], (), 0
    for token in tokens:
        if token.isdigit() and len(token) == 8:
            date = int(token)
        elif _VERSION.fullmatch(token):
            version += tuple(int(n) for n in token.split('.'))
        else:
            family.append(token)
    return tuple(family), version, date, effort


def arrange(models, drop=()):
    """One ordering for every model list.

    Removes blanks, duplicates and the IDs in drop. Families stay in the order
    the provider listed them (usually its recommendation); inside a family the
    newest version comes first, undated IDs before dated snapshots, and effort
    variants always run low to high.
    """
    seen, rows = set(), []
    for model in models or ():
        if not isinstance(model, str):
            continue
        model = model.strip()
        if model and model not in seen and model not in drop:
            seen.add(model)
            rows.append((model, *_parts(model)))
    order = {}
    for row in rows:
        order.setdefault(row[1], len(order))
    rows.sort(key=lambda row: (row[3] != 0, -row[3], row[4]))
    rows.sort(key=lambda row: row[2], reverse=True)
    rows.sort(key=lambda row: order[row[1]])
    return [row[0] for row in rows]


def select_models(provider, discovered=None, category='全部'):
    # None means not fetched. An empty successful response must stay empty.
    presets = CATALOG.get(provider, {})
    if discovered is None:
        discovered = presets
    if provider == 'Meta Muse':
        discovered = [m for m in discovered if isinstance(m, str) and m.startswith(('muse-spark-', 'muse-wonder-'))]
    available = {m for m in discovered if isinstance(m, str) and m and chat_candidate(m)}
    # API listings have no meaningful order, so unknown families go alphabetically.
    models = [m for m in presets if m in available] + arrange(sorted(available - set(presets)))
    return [
        m
        for m in models
        if category == '全部' or category in CATALOG.get(provider, {}).get(m, ('未分类', ''))[0].split(',')
    ]


def thinking_options(provider, model, reasoning=False):
    if provider == 'Meta Muse' and model in CATALOG[provider]:
        return {'reasoning_effort': 'high' if reasoning else 'minimal'}
    if provider == 'Kimi':
        if model == 'kimi-k3':
            return {'reasoning_effort': 'high' if reasoning else 'low'}
        if model in ('kimi-k2.5', 'kimi-k2.6'):
            return {'thinking': {'type': 'enabled' if reasoning else 'disabled'}}
        return {}  # Code models always think; unknown models retain server defaults.
    if provider == 'DeepSeek' and model in CATALOG['DeepSeek']:
        return {'thinking': {'type': 'enabled' if reasoning else 'disabled'}}
    if (
        provider == '通义千问（北京）'
        and model in CATALOG[provider]
        and model.startswith(('qwen3.8-', 'qwen3.7-', 'qwen3.6-', 'qwen3.5-'))
    ):
        return {'enable_thinking': reasoning}
    return {}
