"""Local encrypted preferences, observed usage, and read-only Codex quota RPC."""
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid


class Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    raw = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(raw, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        function = crypt.CryptUnprotectData
        function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        description = None
    else:
        function = crypt.CryptProtectData
        function.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        description = 'Audio Answer API settings'
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), description, None, None, None, 1, ctypes.byref(output)):
        raise OSError('Windows 加密/解密失败，错误码 ' + str(ctypes.get_last_error()))
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel.LocalFree(output.pbData)


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_bytes(data)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def save_settings(path, settings):
    atomic_write(path, protect(json.dumps(settings, ensure_ascii=False).encode('utf-8')))


def load_settings(path):
    if not Path(path).exists():
        return {}
    data = json.loads(protect(Path(path).read_bytes(), decrypt=True))
    if not isinstance(data, dict):
        raise ValueError('配置格式无效')
    return data


class UsageLedger:
    """Only locally observed Gemini requests; never an account quota estimate."""
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = {'models': {}}
        self.load_error = ''
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(self.data.get('models'), dict):
                    raise ValueError()
            except (ValueError, OSError, AttributeError):
                self.data = {'models': {}}
                self.load_error = '历史用量文件不可读；未覆盖原文件，本次仅显示内存统计。'

    def record(self, model, usage, success):
        with self.lock:
            row = self.data['models'].setdefault(model, {'requests': 0, 'completed': 0, 'reported': 0,
                                                       'prompt': 0, 'output': 0, 'thoughts': 0, 'total': 0})
            row['requests'] += 1
            row['completed'] += int(success)
            if usage:
                row['reported'] += 1
                for column, name in [('prompt', 'promptTokenCount'), ('output', 'candidatesTokenCount'),
                                     ('thoughts', 'thoughtsTokenCount'), ('total', 'totalTokenCount')]:
                    value = usage.get(name)
                    if isinstance(value, int) and value >= 0:
                        row[column] += value
            if not self.load_error:
                atomic_write(self.path, json.dumps(self.data, ensure_ascii=False).encode('utf-8'))

    def summary(self):
        with self.lock:
            lines = ['Gemini：本工具累计用量（含模型测试，跨 Key 合计；不是项目总用量）']
            for model, row in self.data['models'].items():
                lines.append(f"{model}：请求 {row['requests']} 次，完成 {row['completed']} 次；"
                             f"输入 {row['prompt']:,} / 输出 {row['output']:,} / 思考 {row['thoughts']:,} / 总计 {row['total']:,} token；"
                             f"收到用量报告 {row['reported']} 次")
            if not self.data['models']:
                lines.append('尚未记录请求。更新前的用量无法补录。')
            lines.append('缺失用量报告的请求未计入 token；取消/失败仍可能计费。剩余额度未知，请查看 AI Studio。')
            if self.load_error:
                lines.append(self.load_error)
            return '\n'.join(lines)


def read_codex_account(executable, cwd, timeout=25, models_only=False):
    proc = subprocess.Popen([executable, 'app-server', '--stdio'], cwd=cwd,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    events = queue.Queue()
    def read():
        try:
            for line in proc.stdout:
                try:
                    events.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            events.put(None)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout

    def send(message):
        proc.stdin.write((json.dumps(message) + '\n').encode('utf-8'))
        proc.stdin.flush()

    def rpc(identity, method, params=None):
        message = {'id': identity, 'method': method}
        if params is not None:
            message['params'] = params
        send(message)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Codex 额度查询超时，请检查登录和网络。')
            try:
                event = events.get(timeout=remaining)
            except queue.Empty:
                raise RuntimeError('Codex 额度查询超时，请检查登录和网络。') from None
            if event is None:
                raise RuntimeError('Codex 查询进程未能启动或已退出，请在正常桌面启动工具后重试。')
            if event.get('id') == identity:
                if event.get('error'):
                    raise RuntimeError('Codex 未提供此数据，请检查 ChatGPT 登录、CLI 版本及账号权限。')
                return event.get('result', {})
    try:
        rpc(1, 'initialize', {'clientInfo': {'name': 'audio_answer', 'version': '1.0'}})
        send({'method': 'initialized'})
        if models_only:
            models, cursor, seen = [], None, set()
            while True:
                page = rpc(2+len(seen), 'model/list', {'cursor':cursor})
                models.extend((item if models_only == 'details' else item['model']) for item in page.get('data',[]) if item.get('model'))
                cursor=page.get('nextCursor')
                if not cursor: return models
                if cursor in seen: raise RuntimeError('模型目录分页异常')
                seen.add(cursor)
        limits = rpc(2, 'account/rateLimits/read')
        try:
            usage = rpc(3, 'account/usage/read')
        except RuntimeError:
            usage = {}
        return limits, usage
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        reader.join(timeout=1)
        proc.stdin.close()
        proc.stdout.close()


def format_codex_account(limits, usage):
    lines = ['Codex 官方账号额度（账号共享，并非仅本工具）']
    buckets = limits.get('rateLimitsByLimitId')
    if not buckets:
        single = limits.get('rateLimits')
        buckets = {'Codex': single} if single else {}
    found = False
    for identity, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        for slot in ('primary', 'secondary'):
            window = bucket.get(slot)
            if not window:
                continue
            used = window.get('usedPercent')
            if not isinstance(used, (int, float)):
                continue
            duration = window.get('windowDurationMins')
            label = f'{duration / 1440:g} 天' if duration and duration % 1440 == 0 else (
                f'{duration / 60:g} 小时' if duration and duration % 60 == 0 else f'{duration} 分钟' if duration else '未知周期')
            reset = window.get('resetsAt')
            try:
                reset_text = datetime.fromtimestamp(reset).astimezone().strftime('%Y-%m-%d %H:%M %Z') if reset else '未知'
            except (ValueError, OSError, OverflowError):
                reset_text = '未知'
            lines.append(f"{bucket.get('limitName') or identity} · {label}：已用 {used:g}%，剩余 {max(0, min(100, 100-used)):g}%；重置 {reset_text}")
            found = True
    if not found:
        lines.append('服务未返回可用的额度窗口；剩余未知。')
    lifetime = (usage.get('summary') or {}).get('lifetimeTokens')
    lines.append(f'官方累计 token：{lifetime:,}' if isinstance(lifetime, int) else '官方累计 token：未提供。')
    lines.append('更新时间：' + datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'))
    return '\n'.join(lines)
