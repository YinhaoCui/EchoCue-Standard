"""Model catalogs for the local-login CLI providers."""
import threading
import tkinter as tk
from tkinter import ttk
import providers

CLI_PRESETS = {providers.CLAUDE: ['sonnet', 'opus', 'haiku']}


class CliModels:
    def init_cli_models(self):
        self.cli_catalogs = {}
        self.cli_loading = set()
        self.cli_model_note = tk.StringVar(value=providers.Provider('').model_note)
        for key in providers.MODEL_OPTIONS:
            self.advanced[key].trace_add('write', lambda *_: self.schedule_save())

    def cli_key(self, provider=None):
        return providers.model_option(provider or self.provider.get())

    def cli_models(self, provider=None):
        """Model IDs to offer for a CLI provider: its catalog, or the saved model."""
        provider = provider or self.provider.get()
        value = self.advanced[self.cli_key(provider)].get()
        return list(self.cli_catalogs.get(provider, CLI_PRESETS.get(provider, [value] if value else [])))

    def cli_catalog_note(self, provider):
        if provider in self.cli_catalogs:
            return '目录来源：最近一次成功获取。'
        if provider in CLI_PRESETS:
            return '目录来源：内置预设，尚未验证可用性。'
        return '尚未获取账号模型目录，请刷新或手动填写模型 ID。'

    def show_cli_model(self, provider):
        self.cli_model_note.set(self.cli_catalog_note(provider) + ' ' + providers.get(provider).model_note)

    def default_cli_model(self):
        self.advanced[self.cli_key()].set('')

    def refresh_cli_models(self):
        provider = self.provider.get()
        if provider in self.cli_loading: return
        self.cli_loading.add(provider)
        self.cli_model_note.set('正在读取账号模型目录…')
        def read():
            try:
                models, extra = providers.read_cli_models(provider, details=True)
                if provider == providers.CODEX:
                    self.events.put(('codex_capabilities', extra))
                    extra = None
                self.events.put(('cli_models', (provider, models, extra or '', '')))
            except Exception:
                self.events.put(('cli_models', (provider, [], '', '目录读取失败，请检查该 CLI 的登录和网络；仍可手动输入模型 ID。')))
        threading.Thread(target=read, daemon=True).start()

    def receive_cli_models(self, result):
        provider, models, raw, error = result
        self.cli_loading.discard(provider)
        if not error: self.cli_catalogs[provider] = models
        if not error and models and provider == providers.ANTIGRAVITY:
            from antigravity_support import set_model_catalog
            set_model_catalog(models)
        if self.provider.get() == provider:
            self.cli_model_note.set(self.cli_catalog_note(provider) + ' ' + (error or f'已读取 {len(models)} 个模型；可用权限以账号为准。'))
        if raw and not models:
            window = tk.Toplevel(self.root); window.title('Antigravity 模型目录'); window.geometry('760x500')
            ttk.Label(window, text='从目录复制模型 ID，填入主窗口的回答模型。').pack(anchor='w', padx=12, pady=12)
            text = tk.Text(window, wrap='word'); text.pack(fill='both', expand=True, padx=12, pady=12)
            text.insert('end', raw); text.configure(state='disabled')
