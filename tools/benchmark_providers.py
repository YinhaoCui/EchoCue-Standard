from pathlib import Path
import sys,json,threading,time,uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import audio_answer as a
from speed_test import PROMPT,measure
from codex_service import CodexService
from antigravity_support import antigravity_answer, close_service as close_agy
from lmstudio_support import answer as lm_answer
s=a.load_settings(a.SETTINGS_FILE);options=s.get('advanced',{})
service=CodexService(a.find_codex(),a.WORK)
ledger=a.TokenLedger(a.ROOT/'data/token_usage.json')
run='latency-'+uuid.uuid4().hex
rows=[]
try:
 for provider in ('Codex','Antigravity','LM Studio'):
  model=options.get('codex_model') or 'gpt-6-astra' if provider=='Codex' else (options.get('antigravity_model','') if provider=='Antigravity' else s.get('apis',{}).get('LM Studio',{}).get('model',''))
  for trial in (1,2):
   print(json.dumps({'start':provider,'trial':trial,'model':model or 'default'}),flush=True)
   def generate(emit,usage):
    cancel=threading.Event()
    if provider=='Codex':service.answer(PROMPT,model,'low',cancel,emit,usage,timeout=60,session_key=(run,provider))
    elif provider=='Antigravity':antigravity_answer(a.ROOT,PROMPT,model,cancel,emit,on_usage=usage,total_timeout=60,session_key=(run,provider))
    else:
     key=s.get('apis',{}).get('LM Studio',{}).get('key','')
     native=lm_answer(options.get('lm_base') or 'http://127.0.0.1:1234/v1',key,model,PROMPT,'只回答给定问题，不调用工具。',cancel,emit,usage,60,2048,'关闭',(run,provider))
     if not native:a.compatible_answer('LM Studio',PROMPT,key,model,'',cancel,emit,base=options.get('lm_base'),on_usage=usage,total_timeout=60,max_output=2048)
   row=measure(generate);row.update(provider=provider,model=model or 'default',trial=trial,effort='low' if provider=='Codex' else 'default')
   rows.append(row)
   ledger.record(run+':'+provider+':'+str(trial),provider,model or 'default',row['usage'],'测速'+row['status'])
   (a.ROOT/'data/provider_latency_benchmark.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({k:v for k,v in row.items() if k not in ('text','usage')},ensure_ascii=True),flush=True)
   if row['status']!='完成':break
finally:
 service.close()
 close_agy()
