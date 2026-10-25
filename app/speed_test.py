"""Synthetic model latency test, isolated from transcript and personal context."""
import threading
import time
import uuid
import tkinter as tk
from tkinter import ttk
from session_support import Cancelled
from token_usage import normalize_usage
from reasoning_support import choices
from model_catalog import select_models
import providers

PROMPT = ('编程测速题：使用 Python 实现 unique_in_order(items)，对整数列表去重并保持首次出现的顺序。'
          '要求时间复杂度 O(n)，不修改输入列表，不使用第三方库。'
          '给出完整函数，以及空列表、重复元素、负数三种情况的 assert 测试。'
          '只输出一个 Python 代码块，不附加解释，不调用工具或执行代码。')
EN_PROMPT = ('Implement Python unique_in_order(items): deduplicate an integer list while preserving first occurrence order. '
             'Use O(n) time, do not mutate the input and use no third-party libraries. '
             'Provide the complete function and assert tests for empty lists, duplicates and negative numbers. '
             'Output one Python code block only, without explanation, tools or code execution.')


def benchmark_prompt(provider, model):
    from prompt_language import language, choose
    return choose(language(provider,model),PROMPT,EN_PROMPT)

BENCHMARK_ID = 'python-unique-in-order-v1'

def measure(generate, streaming=True):
    started=time.perf_counter()
    first=None
    pieces=[]
    usage={}
    status='完成'
    error=''
    def emit(text):
        nonlocal first
        if text:
            if first is None: first=time.perf_counter()-started
            pieces.append(text)
    def report(value):
        if isinstance(value,dict): usage.clear(); usage.update(value)
    try:
        generate(emit,report)
        if not pieces: raise RuntimeError('未收到答案文字')
        if any('达到模型输出上限' in piece for piece in pieces): status='输出截断'
    except Cancelled: status='已取消'
    except Exception as exc: status='失败'; error=str(exc)
    elapsed=time.perf_counter()-started
    text=''.join(pieces)
    normalized=normalize_usage(usage)
    return {'first':first if streaming else None,'elapsed':elapsed,'characters':len(text),
            'chars_per_second':len(text)/elapsed if elapsed else 0,
            'output_tokens':normalized.get('output'),'usage':usage,'status':status,'error':error,'text':text}

class SpeedTestUI:
    def show_speed_test(self):
        if getattr(self,'speed_window',None) and self.speed_window.winfo_exists():
            self.speed_window.deiconify(); self.speed_window.lift(); return
        import audio_answer as a
        if not hasattr(self,'speed_results'): self.speed_results=[]
        window=self.speed_window=tk.Toplevel(self.root)
        window.title('Coding 回答测速'); window.geometry('1100x760')
        box=ttk.Frame(window,padding=18); box.pack(fill='both',expand=True)
        ttk.Label(box,text='Coding 回答测速',style='Brand.TLabel').pack(anchor='w')
        ttk.Label(box,text='独立选择测速模型，不改变正常回答配置。固定 Python 编程题，不带入个人资料或转录；云端请求可能计费。',wraplength=980).pack(anchor='w',pady=8)
        ttk.Label(box,text='内置题目：实现 unique_in_order(items)，整数列表去重并保持顺序，O(n)，附三种情况的 assert 测试。',wraplength=980,style='Muted.TLabel').pack(anchor='w',pady=(0,8))
        self.speed_provider=tk.StringVar(value=self.provider.get())
        self.speed_model=tk.StringVar()
        self.speed_status=tk.StringVar()
        self.speed_effort=tk.StringVar(value=self.reasoning_selection.get())
        self.speed_mode=tk.StringVar(value=self.answer_mode.get())
        self.speed_fast=tk.BooleanVar(value=self.fast_mode.get())
        self.speed_models={}; self.speed_catalogs={}; self.speed_editing=None
        selection=ttk.Frame(box); selection.pack(fill='x',pady=6)
        ttk.Label(selection,text='平台').pack(side='left')
        platform=ttk.Combobox(selection,textvariable=self.speed_provider,values=providers.NAMES,state='readonly',width=21)
        platform.pack(side='left',padx=8); platform.bind('<<ComboboxSelected>>',lambda _:self.change_speed_provider())
        ttk.Label(selection,text='模型').pack(side='left')
        self.speed_model_box=ttk.Combobox(selection,textvariable=self.speed_model,width=39)
        self.speed_model_box.pack(side='left',padx=8)
        ttk.Button(selection,text='刷新目录',command=self.refresh_speed_models).pack(side='left')
        settings=ttk.Frame(box); settings.pack(fill='x',pady=6)
        ttk.Label(settings,text='思考强度').pack(side='left')
        self.speed_effort_box=ttk.Combobox(settings,textvariable=self.speed_effort,state='readonly',width=16)
        self.speed_effort_box.pack(side='left',padx=8)
        ttk.Label(settings,text='回答模式').pack(side='left')
        ttk.Combobox(settings,textvariable=self.speed_mode,values=['快速','推理','Coding'],state='readonly',width=10).pack(side='left',padx=8)
        ttk.Checkbutton(settings,text='Gemini 快速回复',variable=self.speed_fast).pack(side='left')
        self.speed_model.trace_add('write',lambda *_:self.update_speed_effort())
        self.change_speed_provider()
        controls=ttk.Frame(box); controls.pack(fill='x',pady=6)
        ttk.Button(controls,text='开始 Coding 测速',style='Primary.TButton',command=self.start_speed_test).pack(side='left')
        ttk.Button(controls,text='取消测速',command=self.cancel_speed_test).pack(side='left',padx=8)
        ttk.Label(box,textvariable=self.speed_status,wraplength=980).pack(anchor='w',pady=8)
        columns=('time','provider','model','effort','first','total','rate','tokens','status')
        table=self.speed_table=ttk.Treeview(box,columns=columns,show='headings',height=9)
        for key,label,width in zip(columns,['时间','平台','模型','思考强度','首段等待','总耗时','平均字/秒','输出Token','结果'],[80,100,190,85,85,80,90,85,80]):
            table.heading(key,text=label); table.column(key,width=width,minwidth=55)
        scroll=ttk.Scrollbar(box,orient='vertical',command=table.yview)
        table.configure(yscrollcommand=scroll.set); scroll.pack(side='right',fill='y'); table.pack(fill='both',expand=True)
        table.bind('<<TreeviewSelect>>',self.show_speed_detail)
        ttk.Label(box,text='首段等待包含网络与思考；平均字/秒=答案字符数÷总耗时，不等于模型解码 Token/s。流式接口收到首段正文即显示。',wraplength=980,style='Muted.TLabel').pack(anchor='w',pady=8)
        self.speed_detail=tk.Text(box,height=5,wrap='word',relief='flat',bg='#101824',padx=10,pady=8,state='disabled')
        self.speed_detail.pack(fill='x')
        self.render_speed_results()
        self.tick_speed()

    def speed_key(self,provider):
        return self.key.get().strip() if self.api_editing==provider else self.api_settings.get(provider,{}).get('key','')

    def change_speed_provider(self):
        import audio_answer as a
        if self.speed_editing is not None: self.speed_models[self.speed_editing]=self.speed_model.get()
        provider=self.speed_provider.get(); self.speed_editing=provider
        if providers.is_cli(provider):
            initial=self.advanced[self.cli_key(provider)].get()
        else:
            initial=self.model.get() if provider==self.api_editing else self.api_settings.get(provider,{}).get('model','')
        self.speed_model_box['values']=self.speed_catalog(provider)
        self.speed_status.set(self.speed_catalog_note(provider))
        self.speed_model.set(self.speed_models.get(provider,initial))
        self.speed_effort.set(self.reasoning_settings.get(provider+'|'+self.speed_model.get(),'自动'))
        self.update_speed_effort()

    def update_speed_effort(self):
        values=choices(self.speed_provider.get(),self.speed_model.get(),self.codex_capabilities)
        self.speed_effort_box.configure(values=values,state='readonly' if len(values)>2 else 'disabled')
        if self.speed_effort.get() not in values: self.speed_effort.set('自动')

    def speed_catalog_key(self, provider):
        return provider if providers.is_cli(provider) else self.model_catalog_key(provider)

    def speed_catalog(self, provider):
        key=self.speed_catalog_key(provider)
        if key in self.speed_catalogs:return self.speed_catalogs[key]
        return self.cli_models(provider) if providers.is_cli(provider) else select_models(provider,self.discovered_models.get(key))

    def speed_catalog_note(self, provider):
        if self.speed_catalog_key(provider) in self.speed_catalogs:
            return '目录来源：最近一次成功获取。'
        return self.cli_catalog_note(provider) if providers.is_cli(provider) else self.model_catalog_note(provider)

    def refresh_speed_models(self):
        import audio_answer as a
        provider=self.speed_provider.get(); key=self.speed_key(provider)
        catalog_key=self.speed_catalog_key(provider)
        self.speed_model_box['values']=self.speed_catalog(provider)
        window=self.speed_window
        base=self.advanced['lm_base'].get()
        if provider in a.API_PROVIDERS and provider!='LM Studio' and not key:
            self.speed_status.set('请先在主窗口设置该平台的 API Key。'); return
        self.speed_status.set('正在读取 '+provider+' 模型目录…')
        def read():
            try:
                if providers.is_cli(provider): models=providers.read_cli_models(provider)[0]
                else: models=select_models(provider,a.list_provider_models(provider,key,base=base))
                self.events.put(('speed_models',(window,provider,catalog_key,models,'')))
            except Exception:
                self.events.put(('speed_models',(window,provider,catalog_key,[],'目录读取失败；保留原列表，请检查登录、Key 和网络，也可手动填写模型 ID。')))
        threading.Thread(target=read,daemon=True).start()

    def receive_speed_models(self,value):
        window,provider,catalog_key,models,error=value
        if self.speed_window is not window or not window.winfo_exists(): return
        if not error: self.speed_catalogs[catalog_key]=models
        if not error and models and provider==providers.ANTIGRAVITY:
            from antigravity_support import set_model_catalog
            set_model_catalog(models)
        if self.speed_provider.get()!=provider or catalog_key!=self.speed_catalog_key(provider):return
        if not error:self.speed_model_box['values']=models
        self.speed_status.set(self.speed_catalog_note(provider)+' '+(error or f'已读取 {len(models)} 个模型；请选择或输入模型 ID。'))

    def cancel_speed_test(self):
        if getattr(self,'speed_cancel',None): self.speed_cancel.set()

    def tick_speed(self):
        if self.closed or not self.speed_window.winfo_exists(): return
        if getattr(self,'speed_busy',False):
            self.speed_status.set(f"测速中 · {self.speed_target} · {time.monotonic()-self.speed_started:.1f} 秒")
        window=self.speed_window
        self.root.after(250,lambda:self.tick_speed() if self.speed_window is window else None)

    def start_speed_test(self):
        import audio_answer as a
        if getattr(self,'speed_busy',False): return
        provider=self.speed_provider.get()
        key=self.speed_key(provider)
        options={k:v.get() for k,v in self.advanced.items()}
        model=self.speed_model.get().strip()
        effort=self.speed_effort.get()
        if provider==providers.ANTIGRAVITY:
            from antigravity_support import resolve_model
            try:model=resolve_model(model,effort)
            except ValueError as exc:self.speed_status.set(str(exc));return
        if provider in a.API_PROVIDERS and provider!='LM Studio' and not key:
            self.speed_status.set('请先在主窗口填写 API Key。'); return
        if provider in a.API_PROVIDERS and (not model or model=='选择或刷新本地模型'):
            self.speed_status.set('请先选择回答模型。'); return
        reasoning=self.speed_mode.get() in ('推理','Coding')
        fast=self.speed_fast.get() and not reasoning
        self.speed_cancel=cancel=threading.Event()
        self.speed_busy=True; self.speed_started=time.monotonic()
        self.speed_target=provider+' / '+(model or '默认')
        prompt=benchmark_prompt(provider,model)
        def generate(emit,usage):
            if providers.is_cli(provider):
                # Codex builds its own answer-only prompt around the benchmark question.
                providers.cli_answer(provider,None if provider==providers.CODEX else prompt,model,cancel,emit,
                                     on_usage=usage,total_timeout=120,effort=effort,transcript=prompt)
            elif provider=='Gemini':
                a.gemini_answer(None,key,model,'',cancel,emit,fast=fast,on_usage=usage,transcript=prompt,total_timeout=120,max_output=None,effort=effort)
            else:
                a.compatible_answer(provider,prompt,key,model,'',cancel,emit,reasoning=reasoning,base=options['lm_base'],total_timeout=120,on_usage=usage,max_output=None,effort=effort)
        def work():
            result=measure(generate,streaming=True)
            if cancel.is_set(): result['status']='已取消'
            if key: result['error']=result['error'].replace(key,'[KEY]')
            result.update(provider=provider,model=model or '默认',effort=effort,time=time.strftime('%H:%M:%S'),benchmark=BENCHMARK_ID)
            try:
                self.token_ledger.record(self.session_id+':speed-'+uuid.uuid4().hex,provider,model or '默认',result['usage'],'测速'+result['status'])
            except Exception: self.events.put(('usage_save_error','测速用量保存失败。'))
            self.events.put(('usage_updated',''))
            self.events.put(('speed_result',result))
        self.speed_worker=threading.Thread(target=work,daemon=True)
        self.speed_worker.start()

    def receive_speed_result(self,result):
        self.speed_busy=False
        self.speed_results.append(result)
        if self.speed_window.winfo_exists():
            self.render_speed_results()
            self.speed_status.set(result['status']+' · '+(result['error'] or '已记录用量。测试只代表本次编程题；结果不自动执行或判定代码正确性。'))

    def render_speed_results(self):
        self.speed_table.delete(*self.speed_table.get_children())
        for i,r in enumerate(self.speed_results):
            self.speed_table.insert('', 'end',iid=str(i),values=tuple(self.locale.t(v) for v in (r['time'],r['provider'],r['model'],r['effort'],
                f"{r['first']:.2f}s" if r['first'] is not None else '不可测',f"{r['elapsed']:.2f}s",f"{r['chars_per_second']:.1f}",
                r['output_tokens'] if r['output_tokens'] is not None else '未知',r['status'])))

    def show_speed_detail(self,event=None):
        selected=self.speed_table.selection()
        if not selected:return
        result=self.speed_results[int(selected[0])]
        self.speed_detail.configure(state='normal'); self.speed_detail.delete('1.0','end')
        self.speed_detail.insert('end',result['error'] or result['text']); self.speed_detail.configure(state='disabled')
