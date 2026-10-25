"""Model-specific reasoning controls; explicit selections override quick mode."""
from prompt_language import language, choose
import providers
import tkinter as tk

DEFAULT = '自动'

def choices(provider, model, codex_caps=None):
    base=[DEFAULT,'服务默认']
    if provider=='Meta Muse' and model.startswith(('muse-spark-','muse-wonder-')):
        return base+['minimal','low','medium','high','xhigh']+(['max'] if model in ('muse-spark-1.3','muse-wonder-1.0') else [])
    if provider==providers.ANTIGRAVITY:return base+['low','medium','high']
    if provider in (providers.CLAUDE,providers.KIRO):return base+['low','medium','high','xhigh','max']
    if provider=='Codex':
        levels=(codex_caps or {}).get(model)
        return base + (levels if levels is not None else ['low','medium','high','xhigh','max','ultra'])
    if provider=='Kimi':
        if model=='kimi-k3': return base+['low','high','max']
        if model in ('kimi-k2.5','kimi-k2.6'): return base+['关闭','开启']
    if provider=='DeepSeek' and model in ('deepseek-flash','deepseek-v4-flash','deepseek-v4-pro'):
        return base+['关闭','low','high','max']
    if provider=='通义千问（北京）' and model.startswith(('qwen3.8-','qwen3.7-','qwen3.6-','qwen3.5-')):
        return base+['关闭','开启','预算 1024','预算 4096','预算 8192','预算 16384','预算 32768']
    if provider=='Gemini':
        if model in ('gemini-2.5-flash','gemini-2.5-flash-lite','gemini-2.5-pro'):
            return base+([] if model.endswith('-pro') else ['关闭'])+['预算 1024','预算 4096','预算 8192','预算 16384']
        if model in ('gemini-3.8-flash','gemini-3.7-flash','gemini-3.1-pro-preview'):
            return base+['low','medium','high']
        if model in ('gemini-3.6-flash','gemini-3.5-flash','gemini-3.5-flash-lite','gemini-3-flash-preview'):
            return base+['minimal','low','medium','high']
    return base

def parameters(provider, model, selection):
    if selection in (DEFAULT,'服务默认'): return {}
    if selection not in choices(provider,model): raise ValueError('当前模型不支持所选思考设置。')
    if provider=='Meta Muse':return {'reasoning_effort':selection}
    if provider=='Kimi' and model=='kimi-k3': return {'reasoning_effort':selection}
    if provider=='DeepSeek':
        return {'thinking':{'type':'disabled'}} if selection=='关闭' else {'thinking':{'type':'enabled'},'reasoning_effort':selection}
    if provider=='Kimi': return {'thinking':{'type':'enabled' if selection=='开启' else 'disabled'}}
    if provider=='通义千问（北京）':
        value={'enable_thinking':selection!='关闭'}
        if selection.startswith('预算 '): value['thinking_budget']=int(selection.split()[1])
        return value
    if provider=='Gemini':
        if selection=='关闭': return {'thinkingBudget':0}
        if selection.startswith('预算 '): return {'thinkingBudget':int(selection.split()[1])}
        return {'thinkingLevel':selection}
    return {}


def thinking_policy(provider, model, selection, enabled, mode_reasoning, caps=None):
    """Resolve explicit user intent without claiming unsupported reasoning can be disabled."""
    if enabled == '自动': return selection, mode_reasoning, ''
    available = choices(provider, model, caps)[2:]
    if enabled == '关闭':
        effort = next((x for x in ('关闭','none','minimal','low') if x in available), '服务默认')
        return effort, False, choose(language(provider,model),'直接简洁回答，不展开推理说明，减少等待。','Answer directly and concisely without a reasoning narrative; minimize delay.')
    effort = selection
    if effort in ('关闭','none','minimal','自动','服务默认'):
        effort = next((x for x in ('开启','medium','high','low','预算 1024') if x in available), '服务默认')
    return effort, True, choose(language(provider,model),'充分检查问题和答案，给出可靠结论及必要依据。','Check the problem and answer carefully; provide a reliable conclusion with necessary supporting evidence.')

class ReasoningState:
    def init_reasoning(self):
        self.reasoning_settings=dict(self.saved.get('reasoning_settings',{}))
        self.codex_capabilities={}
        self.reasoning_selection=tk.StringVar(value=DEFAULT)
        self.reasoning_note=tk.StringVar()
        self.context_warm_note=tk.StringVar(value='提前准备会产生调用用量；缓存命中由服务决定。')
        self.model.trace_add('write',lambda *_:self.update_reasoning())
        for key in providers.MODEL_OPTIONS:
            self.advanced[key].trace_add('write',lambda *_:self.update_reasoning())

    def reasoning_identity(self):
        provider=self.provider.get()
        model=self.advanced[self.cli_key(provider)].get() if providers.is_cli(provider) else self.model.get()
        return provider,model

    def update_reasoning(self):
        provider,model=self.reasoning_identity()
        values=choices(provider,model,self.codex_capabilities)
        selected=self.reasoning_settings.get(provider+'|'+model,DEFAULT)
        self.reasoning_selection.set(selected if selected in values else DEFAULT)
        self.reasoning_note.set(('原生接口按模型能力应用思考开关；旧接口由服务控制' if provider=='LM Studio' else '由模型或本地服务控制') if len(values)==2 else ('刷新模型目录可获取该模型支持的档位' if provider=='Codex' and model not in self.codex_capabilities else ('自动使用 CLI 默认强度' if provider=='Codex' else '自动跟随回答模式；手动选择优先')))

    def save_reasoning(self,event=None):
        provider,model=self.reasoning_identity()
        self.reasoning_settings[provider+'|'+model]=self.reasoning_selection.get()
        self.schedule_save()
