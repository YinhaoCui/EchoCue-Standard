"""Account-backed before/after prompt benchmark using synthetic data only."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import types
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
import audio_answer as app
import antigravity_support as agy
from codex_service import CodexService
from generation_context import ContextPrompt
from prompt_language import output_rule, system_prompt
from token_usage import normalize_usage


def source(ref,path):
    return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT).decode('utf-8')


def load_baseline(ref):
    text=source(ref,'app/audio_answer.py')
    system=next(ast.literal_eval(node.value) for node in ast.parse(text).body
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROMPT' for t in node.targets))
    modules=[]
    for name in ('generation_context','antigravity_support'):
        module=types.ModuleType('baseline_'+name)
        exec(compile(source(ref,'app/'+name+'.py'),'<baseline '+name+'>','exec'),module.__dict__)
        modules.append(module)
    return system,modules[0],modules[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True,help='Pre-change commit or release tag, e.g. v2026.10.17')
    parser.add_argument('--rounds',type=int,default=3,choices=range(1,6))
    parser.add_argument('--output',default='data/prompt_token_benchmark.json')
    parser.add_argument('--codex-model',default='gpt-6-astra')
    parser.add_argument('--agy-model',default='gemini-3.8-flash-low')
    args=parser.parse_args()
    old_system,old_context,old_agy=load_baseline(args.baseline)
    fixtures={
        'short':dict(profile='',documents='',history=[],transcript='What is 2 + 2? Reply with only the number.'),
        'context':dict(profile='The user is learning Python and prefers concise explanations.',
            documents='Project: an in-memory task queue. FIFO order is required. Use only the Python standard library. '+
                      'Example task labels: '+', '.join('TASK-'+str(i) for i in range(1,101))+'.',
            history=[{'转录':'Which standard-library queue supports FIFO?','回答':'collections.deque supports FIFO.'}],
            transcript='Implement take_next(queue) using deque.popleft; return None when empty. Output only the complete Python function.')}
    run='prompt-ab-'+uuid.uuid4().hex
    rows=[];prompts={}
    output=ROOT/args.output;output.parent.mkdir(parents=True,exist_ok=True)
    baseline_sha=subprocess.check_output(['git','rev-parse',args.baseline],cwd=ROOT,text=True).strip()
    report=dict(baseline=baseline_sha,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'app').glob('*.py')},started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                rounds=args.rounds,fixtures=fixtures,rows=rows,prompts=prompts,
                note='Fresh conversations per sample; synthetic inputs; provider-reported usage, not tokenizer estimates. No billing equivalence assumed.')
    ledger=app.TokenLedger(ROOT/'data/token_usage.json')
    service=CodexService(app.find_codex(),app.WORK)
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for provider,model in [('Codex',args.codex_model),('Antigravity',args.agy_model)]:
            for fixture,data in fixtures.items():
                base=dict(provider='Codex' if provider=='Codex' else 'Antigravity（本机登录）',model=model,
                          profile=data['profile'],documents=data['documents'],history=data['history'],summary='',
                          terms='',images=[],context_records=[],analysis=False,instructions='\n'+output_rule('en','en'))
                if fixture=='context':base['instructions']+='\n给出完整代码与必要步骤，不使用省略号代替实现。'
                before=old_context.ContextPrompt(base,data['transcript'],old_system.replace('用中文回答','用英文回答'))
                updated=dict(base)
                if fixture=='context':updated['instructions']='\n'+output_rule('en','en')+'\nProvide complete code and necessary steps; do not replace implementation with ellipses.'
                after=ContextPrompt(updated,data['transcript'],system_prompt(base['provider'],model,'en'))
                prompts[provider+'/'+fixture]={'before':str(before),'after':str(after)}
                for trial in range(1,args.rounds+1):
                    for variant in (('before','after') if trial%2 else ('after','before')):
                        prompt=before if variant=='before' else after
                        usage={};pieces=[];started=time.perf_counter();first=[]
                        def emit(text):
                            if text and not first:first.append(time.perf_counter()-started)
                            pieces.append(text)
                        def record(value):usage.clear();usage.update(value)
                        row=dict(provider=provider,model=model,fixture=fixture,trial=trial,variant=variant,
                                 prompt_characters=len(prompt),prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),effort='low')
                        print(json.dumps(dict(start=row),ensure_ascii=True),flush=True)
                        try:
                            if provider=='Codex':
                                service.answer(prompt,model,'low',threading.Event(),emit,record,timeout=60)
                            else:
                                transport=old_agy if variant=='before' else agy
                                transport.antigravity_answer(ROOT,prompt,model,threading.Event(),emit,on_usage=record,total_timeout=60,effort='low')
                            row['status']='ok'
                        except Exception as exc:
                            row.update(status='error',error=str(exc))
                        row.update(usage=normalize_usage(usage),raw_usage=usage,answer=''.join(pieces),
                                   elapsed=time.perf_counter()-started,first_output=first[0] if first else None)
                        rows.append(row);save()
                        ledger.record(run+':'+str(len(rows)),provider,model,usage,'Prompt A/B '+row['status'])
                        print(json.dumps(row,ensure_ascii=True),flush=True)
                        if row['status']!='ok':
                            raise RuntimeError('Benchmark stopped; inspect recorded failure before spending more quota.')
    finally:
        service.close();agy.close_service();old_agy.close_service();save()
    print('RESULT_FILE='+str(output),flush=True)


if __name__=='__main__':main()
