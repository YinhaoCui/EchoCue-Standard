"""Live synthetic release validation; no personal settings or documents are loaded."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
import audio_answer as app
import antigravity_support as agy
from codex_service import CodexService
from generation_context import ContextPrompt
from prompt_language import preparation,system_prompt
from speed_test import benchmark_prompt,measure
from token_usage import normalize_usage


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds',type=int,choices=range(1,6),default=3)
    parser.add_argument('--codex-model',default='gpt-6-astra')
    parser.add_argument('--agy-model',default='gemini-3.8-flash-low')
    parser.add_argument('--output',default='data/release_validation.json')
    args=parser.parse_args()
    output=ROOT/args.output;output.parent.mkdir(parents=True,exist_ok=True)
    report=dict(started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rounds=args.rounds,
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'app').glob('*.py')},rows=[])
    run='release-check-'+uuid.uuid4().hex
    service=CodexService(app.find_codex(),app.WORK)
    ledger=app.TokenLedger(ROOT/'data/token_usage.json')
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        for provider,model in [('Codex',args.codex_model),('Antigravity',args.agy_model)]:
            for trial in range(1,args.rounds+1):
                code='ORBIT-'+str(46+trial)
                state=dict(provider=provider,model=model,profile='',documents='The verification code is '+code+'.',
                    summary='',terms='',instructions='Answer in English. Follow the requested output format.',history=[],context_records=[],images=[],analysis=False)
                previous=None;session=(run,provider,trial)
                phases=[('prepare',preparation('en')),('recall','What is the verification code? Reply only with the code.'),
                        ('coding',benchmark_prompt(provider,model))]
                for phase,question in phases:
                    state['_preparing']=phase=='prepare'
                    prompt=ContextPrompt(state,question,system_prompt(provider,model,'en'))
                    def generate(emit,usage):
                        if provider=='Codex':service.answer(prompt,model,'low',threading.Event(),emit,usage,timeout=60,session_key=session)
                        else:agy.antigravity_answer(ROOT,prompt,model,threading.Event(),emit,on_usage=usage,total_timeout=60,effort='low',session_key=session)
                    print(json.dumps(dict(start=provider,trial=trial,phase=phase)),flush=True)
                    row=measure(generate)
                    row.update(provider=provider,model=model,trial=trial,phase=phase,effort='low',
                        normalized_usage=normalize_usage(row['usage']),wire_characters=len(prompt.render(previous)),
                        full_context_characters=len(prompt),status={'完成':'completed','失败':'failed','取消':'cancelled','输出截断':'truncated'}.get(row['status'],row['status']))
                    if phase=='recall':row['context_verified']=row['text'].strip()==code
                    if phase=='coding':row['format_checks']={s:s in row['text'] for s in ('def unique_in_order','assert')}
                    report['rows'].append(row);save()
                    ledger.record(run+':'+provider+':'+str(trial)+':'+phase,provider,model,row['usage'],'Release validation '+row['status'])
                    print(json.dumps({k:v for k,v in row.items() if k not in ('text','usage')},ensure_ascii=True),flush=True)
                    if row['status']!='completed':raise RuntimeError('Provider validation failed; inspect recorded error.')
                    previous=prompt.state
                    if phase!='prepare':state['history'].append({'转录':question,'回答':row['text']})
                if provider=='Codex':
                    # This benchmark owns its service; retire just this confirmed thread.
                    with service.lock:saved=service.sessions.pop(session,None)
                    if saved:service.rpc('thread/unsubscribe',{'threadId':saved[1]},timeout=5)
                else:agy.discard_session(session)
    finally:
        service.close();agy.close_service();save()
    print('RESULT_FILE='+str(output),flush=True)


if __name__=='__main__':main()
