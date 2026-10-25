"""Token usage summaries, provider balances and the Usage dialog."""
import json
import threading
import time
import tkinter as tk
from tkinter import ttk
import urllib.error
import urllib.request
import webbrowser


def deepseek_balance(key, provider='DeepSeek'):
    url = 'https://api.deepseek.com/user/balance' if provider == 'DeepSeek' else 'https://api.moonshot.cn/v1/users/me/balance'
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'余额查询 HTTP {exc.code}，请检查 Key 和账号权限。') from None
    except Exception:
        raise RuntimeError('余额查询连接失败，请稍后重试。') from None
    if provider == 'Kimi':
        if data.get('code') != 0 or not isinstance(data.get('data'), dict):
            raise RuntimeError('Kimi 官方未返回有效余额。')
        balance = data['data']
        return ('Kimi 中国站官方余额（' + time.strftime('%H:%M:%S') + ' 查询）：CNY 可用 ' + str(balance.get('available_balance', '未知'))
                + '，现金 ' + str(balance.get('cash_balance', '未知')) + '，代金券 ' + str(balance.get('voucher_balance', '未知')))
    rows = data.get('balance_infos', [])
    if not rows: return 'DeepSeek：官方未返回余额明细。'
    return 'DeepSeek 官方余额（' + time.strftime('%H:%M:%S') + ' 查询）：\n' + '\n'.join(
        f"{r.get('currency','未知币种')} 可用 {r.get('total_balance','未知')}（充值 {r.get('topped_up_balance','未知')}，赠金 {r.get('granted_balance','未知')}）" for r in rows)


def usage_lines(rows, session_id):
    def empty(): return {'count': 0, 'session': 0, 'tokens': 0, 'unknown': 0, 'input': 0, 'output': 0, 'reports': 0}
    groups = {name: empty() for name in ('DeepSeek', 'Kimi', '通义千问（北京）', 'Gemini')}
    for row in rows:
        group = groups.setdefault(row['provider'], empty())
        group['count'] += 1
        group['session'] += row['request'].startswith(session_id + ':')
        usage = row.get('usage', {})
        if usage: group['reports'] += 1
        for field in ('input', 'output'): group[field] += usage.get(field, 0)
        if 'total' in usage: group['tokens'] += usage['total']
        else: group['unknown'] += 1
    return '\n'.join(f"{name}：本次 {g['session']} / 累计 {g['count']} 次调用 · 已报告输入 {g['input']} / 输出 {g['output']} / 总 Token {g['tokens']}" +
                     (f" · {g['unknown']} 次总量未知" if g['unknown'] else '') for name, g in groups.items())


class UsageUI:
    def init_usage(self):
        self.quota_window = None
        self.codex_quota_text = 'Codex 官方额度尚未查询。'
        self.quota_busy = False
        self.deepseek_balance_text = 'DeepSeek 官方余额：尚未查询。'
        self.kimi_balance_text = 'Kimi 官方余额：尚未查询。'
        self.balance_busy = set()

    def show_usage(self):
        if self.quota_window and self.quota_window.winfo_exists():
            self.quota_window.deiconify(); self.quota_window.lift()
            return
        window = self.quota_window = tk.Toplevel(self.root)
        window.title('用量与额度')
        window.geometry('850x520')
        controls = ttk.Frame(window, padding=12)
        controls.pack(fill='x')
        self.quota_button = ttk.Button(controls, text='刷新 Codex 官方额度', command=self.refresh_codex_quota)
        self.quota_button.pack(side='left')
        ttk.Button(controls, text='DeepSeek 余额', command=self.refresh_deepseek_balance).pack(side='left', padx=6)
        ttk.Button(controls, text='Kimi 余额', command=lambda: self.refresh_deepseek_balance('Kimi')).pack(side='left', padx=4)
        ttk.Button(controls, text='打开 Gemini 官方用量页', command=lambda: webbrowser.open('https://aistudio.google.com/usage')).pack(side='left', padx=8)
        ttk.Button(controls, text='Qwen 官方用量', command=lambda: webbrowser.open('https://help.aliyun.com/zh/model-studio/model-usage-statistics')).pack(side='left', padx=4)
        self.quota_output = tk.Text(window, wrap='word', font=('Microsoft YaHei UI', 11), padx=15, pady=15)
        self.quota_output.pack(fill='both', expand=True)
        self.render_usage()
        self.refresh_codex_quota()

    def render_usage(self):
        if not self.quota_window or not self.quota_window.winfo_exists():
            return
        self.quota_output.configure(state='normal')
        self.quota_output.delete('1.0', 'end')
        self.quota_output.insert('end', self.locale.t(self.codex_quota_text + '\n\n' + self.deepseek_balance_text + '\n' + self.kimi_balance_text
                                                      + '\nQwen 账户额度请查看官方用量页；下方为本工具记录。\n\n' + self.token_ledger.summary()
                                                      + '\n\n旧版 Gemini 记录：\n' + self.usage_ledger.summary()))
        self.quota_output.configure(state='disabled')
        self.quota_button.configure(state='disabled' if self.quota_busy else 'normal')

    def refresh_codex_quota(self):
        import audio_answer as a
        from account_support import read_codex_account, format_codex_account
        if self.quota_busy:
            return
        self.quota_busy = True
        self.codex_quota_text = '正在查询 Codex 官方账号额度…'
        self.render_usage()
        def read():
            try:
                limits, usage = read_codex_account(a.find_codex(), a.WORK)
                text = format_codex_account(limits, usage)
            except Exception:
                text = 'Codex 官方额度查询失败，剩余未知。请确认 Codex 已通过 ChatGPT 登录，并从正常桌面启动本工具后重试。'
            self.events.put(('codex_quota', text))
        threading.Thread(target=read, daemon=True).start()

    def refresh_deepseek_balance(self, provider='DeepSeek'):
        if provider in self.balance_busy: return
        key = self.key.get().strip() if self.provider.get() == provider else self.api_settings.get(provider, {}).get('key', '')
        attribute = 'deepseek_balance_text' if provider == 'DeepSeek' else 'kimi_balance_text'
        if not key:
            setattr(self, attribute, provider + '：请先在展开设置中填写 API Key。'); self.render_usage(); return
        self.balance_busy.add(provider)
        setattr(self, attribute, provider + '：正在查询官方余额…'); self.render_usage()
        def read():
            try: result = deepseek_balance(key, provider)
            except Exception as exc: result = provider + '：' + str(exc).replace(key, '[KEY]')
            self.events.put(('provider_balance', (provider, result)))
        threading.Thread(target=read, daemon=True).start()
