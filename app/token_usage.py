"""Per-request official token reports; no invented counts for missing reports."""
import json
from pathlib import Path
import threading
import time
from account_support import atomic_write

def normalize_usage(raw):
    if not raw or not isinstance(raw, dict):
        return {}
    mapping = {
        'input': ('prompt_tokens', 'input_tokens', 'promptTokenCount'),
        'output': ('completion_tokens', 'output_tokens', 'candidatesTokenCount', 'total_output_tokens'),
        'thinking': ('thinking_tokens', 'thoughtsTokenCount', 'reasoning_output_tokens'),
        'cache': ('cache_read_tokens', 'cache_read_input_tokens', 'cached_input_tokens', 'cachedContentTokenCount', 'prompt_cache_hit_tokens'),
        'cache_creation': ('cache_creation_input_tokens',),
        'total': ('total_tokens', 'totalTokenCount'),
    }
    result = {}
    for name, aliases in mapping.items():
        for key in aliases:
            value = raw.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                result[name] = value; break
    details = raw.get('completion_tokens_details') or {}
    if isinstance(details.get('reasoning_tokens'), int):
        result['thinking'] = details['reasoning_tokens']
    details = raw.get('prompt_tokens_details') or {}
    if isinstance(details.get('cached_tokens'), int):
        result['cache'] = details['cached_tokens']
    return result

class TokenLedger:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.rows = []
        self.error = ''
        if self.path.exists():
            try:
                self.rows = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(self.rows, list): raise ValueError()
            except Exception:
                self.rows = []; self.error = '历史文件不可读，本次仅在内存统计，未覆盖原文件。'

    def record(self, request, provider, model, raw, status):
        row = {'request': request, 'time': time.strftime('%Y-%m-%d %H:%M:%S'),
               'provider': provider, 'model': model, 'usage': normalize_usage(raw), 'status': status}
        with self.lock:
            # One cumulative report per request, never sum repeated stream snapshots.
            self.rows = [r for r in self.rows if r.get('request') != request] + [row]
            if not self.error:
                atomic_write(self.path, json.dumps(self.rows, ensure_ascii=False).encode('utf-8'))

    def summary(self):
        with self.lock:
            groups = {}
            for row in self.rows:
                key = (row['provider'], row['model'])
                group = groups.setdefault(key, {'requests': 0, 'reports': 0, 'totals': {}})
                group['requests'] += 1
                if row['usage']: group['reports'] += 1
                for field, value in row['usage'].items():
                    group['totals'][field] = group['totals'].get(field, 0) + value
            lines = ['全部平台：本工具观察到的 token 用量（不等于账户余额或账单）']
            for (provider, model), group in groups.items():
                totals = group['totals']
                values = ' / '.join(f'{label} {totals.get(key, "未知")}' for key, label in
                                   [('input','输入'),('output','输出'),('thinking','思考'),('cache','缓存命中'),('total','总计')])
                lines.append(f'{provider} · {model}：{group["requests"]} 次请求，{group["reports"]} 次有报告；{values}')
            lines.append('未返回用量的请求记为未知，不按零计算。思考/缓存通常是其他字段的子集，不能再次相加。')
            if self.error: lines.append(self.error)
            return '\n'.join(lines)
