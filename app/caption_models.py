"""Independent caption model selection, sharing existing provider credentials/catalogs."""
import re
import threading

import providers
from model_catalog import select_models
from reasoning_support import choices


def fast_model(provider, models):
    preferred = select_models(provider, models, '快速 / 省钱')
    candidates = preferred or [model for model in models
                               if re.search(r'(?:flash|lite|mini|nano|haiku|luna)', model, re.I)
                               and 'contributor' not in model]
    return next(iter(candidates), '')


class CaptionModels:
    def __init__(self, app):
        self.app = app
        self.loading = set()
        self.errors = {}

    def provider(self):
        return self.app.advanced['caption_provider'].get() or self.app.provider.get()

    def identity(self, provider):
        return provider if providers.is_cli(provider) else self.app.model_catalog_key(provider)

    def catalog(self, provider):
        a = self.app
        return a.cli_models(provider) if providers.is_cli(provider) else select_models(
            provider, a.discovered_models.get(self.identity(provider)))

    def model(self, provider, models):
        selected = self.app.advanced['caption_model'].get().strip()
        if selected:
            return selected
        quick = fast_model(provider, models)
        if quick:
            return quick
        # An unknown catalog must not be treated as evidence of a fast model.
        if providers.is_cli(provider):
            return self.app.advanced[providers.model_option(provider)].get().strip()
        return next(iter(models), '')

    def state(self):
        a = self.app
        provider = self.provider()
        identity = self.identity(provider)
        models = self.catalog(provider)
        model = self.model(provider, models)
        note = a.cli_catalog_note(provider) if providers.is_cli(provider) else a.model_catalog_note(provider)
        if identity in self.loading:
            note += ' 正在刷新字幕模型目录…'
        elif identity in self.errors:
            note += ' ' + self.errors[identity]
        if not providers.is_cli(provider) and provider != providers.LM_STUDIO and not identity[1]:
            note += ' 请先在回答模型的平台设置中填写该平台的 API Key。'
        return dict(provider=provider, models=models, resolved_model=model,
                    status=a.locale.t(note), loading=identity in self.loading)

    def inputs(self):
        a = self.app
        provider = self.provider()
        if provider not in providers.NAMES:
            return None, '未知字幕翻译平台。'
        model = self.model(provider, self.catalog(provider))
        options = {key: value.get() for key, value in a.advanced.items()}
        key = '' if providers.is_cli(provider) else self.identity(provider)[1]
        if not providers.is_cli(provider):
            if provider != providers.LM_STUDIO and not key:
                return None, '请先配置字幕翻译平台的 API Key。'
            if not model:
                return None, '请选择字幕翻译模型或刷新该平台的模型目录。'
            if provider == providers.LM_STUDIO:
                from session_support import local_base
                try:
                    local_base(options['lm_base'])
                except ValueError as exc:
                    return None, str(exc)
        else:
            options[providers.model_option(provider)] = model
        available = choices(provider, model, a.codex_capabilities)[2:]
        effort = next((level for level in ('关闭', 'none', 'minimal', 'low') if level in available), '自动')
        if provider == providers.ANTIGRAVITY:
            from antigravity_support import quick_effort, resolve_model
            effort = quick_effort(model)
            try:
                model = options['antigravity_model'] = resolve_model(model, effort)
            except ValueError as exc:
                return None, str(exc)
        return dict(provider=provider, model=model, key=key, options=options, effort=effort,
                    display_model=model or providers.get(provider).default_model), None

    def refresh(self):
        a = self.app
        provider = self.provider()
        identity = self.identity(provider)
        if identity in self.loading:
            return
        key = '' if providers.is_cli(provider) else identity[1]
        if not providers.is_cli(provider) and provider != providers.LM_STUDIO and not key:
            self.errors[identity] = '请先配置该平台的 API Key。'
            return
        self.loading.add(identity)
        self.errors.pop(identity, None)
        base = a.advanced['lm_base'].get()
        def read():
            try:
                if providers.is_cli(provider):
                    models, extra = providers.read_cli_models(provider, details=True)
                else:
                    import audio_answer
                    models, extra = audio_answer.list_provider_models(provider, key, base=base), None
                result = (provider, identity, models, extra, '')
            except Exception:
                result = (provider, identity, None, None, '字幕模型目录刷新失败；保留原列表，可手动填写模型 ID。')
            a.events.put(('caption_models', result))
        threading.Thread(target=read, daemon=True, name='caption-models').start()

    def receive(self, result):
        provider, identity, models, extra, error = result
        self.loading.discard(identity)
        if error:
            self.errors[identity] = error
            return
        self.errors.pop(identity, None)
        a = self.app
        if providers.is_cli(provider):
            a.cli_catalogs[provider] = models
            if provider == providers.CODEX and extra is not None:
                a.handle_event('codex_capabilities', extra)
            if provider == providers.ANTIGRAVITY and models:
                from antigravity_support import set_model_catalog
                set_model_catalog(models)
        else:
            a.discovered_models[identity] = models
            if provider == a.api_editing and identity == a.model_catalog_key(provider):
                a.filter_models()
