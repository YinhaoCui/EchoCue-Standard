"""Synthetic live checks: retained context and coding latency; never send personal documents."""
from pathlib import Path
import argparse,json,sys,threading,uuid,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import audio_answer as a
from codex_service import CodexService
import antigravity_support as agy
import claude_support as claude
from generation_context import ContextPrompt
from speed_test import measure,PROMPT
settings=a.load_settings(a.SETTINGS_FILE);options=settings.get('advanced',{})
parser=argparse.ArgumentParser()
parser.add_argument('providers',nargs='*',choices=['Codex','Antigravity','Claude Code'])
parser.add_argument('--rounds',type=int,choices=range(1,6),default=1)
args=parser.parse_args()
service=CodexService(a.find_codex(),a.WORK)
rows=[];run='incremental-'+uuid.uuid4().hex
ledger=a.TokenLedger(a.ROOT/'data/token_usage.json')
providers=['Codex','Antigravity']
try:claude.find_claude();providers.append('Claude Code')
except RuntimeError:pass
if args.providers:providers=args.providers
output='generation_latency_'+time.strftime('%Y%m%d_%H%M%S')+'.json'
print('RESULT_FILE='+output,flush=True)
try:
 for provider in providers:
  model=(options.get('codex_model') or 'gpt-6-astra') if provider=='Codex' else ((options.get('antigravity_model') or '') if provider=='Antigravity' else (options.get('claude_model') or 'sonnet'))
  if provider=='Antigravity':model=agy.resolve_model(model,'low')
  state=dict(profile='',documents='The verification code for this synthetic test is ORBIT-47.',summary='',terms='',instructions='',history=[],context_records=[],images=[],analysis=False)
  previous=None
  phases=[('prepare','Remember the supplied document.'),('recall','What is the verification code? Reply only with the code.')]+[(f'coding_{i+1}',PROMPT) for i in range(args.rounds)]
  for phase,text in phases:
   state['_preparing']=phase=='prepare';prompt=ContextPrompt(state,text,'Answer supplied questions without tools or file access.')
   print(json.dumps({'provider':provider,'phase':phase,'model':model},ensure_ascii=True),flush=True)
   def generate(emit,usage):
    cancel=threading.Event()
    if provider=='Codex':service.answer(prompt,model,'low',cancel,emit,usage,timeout=45,session_key=(run,provider))
    elif provider=='Antigravity':agy.antigravity_answer(a.ROOT,prompt,model,cancel,emit,on_usage=usage,total_timeout=45,effort='low',session_key=(run,provider))
    else:claude.claude_answer(a.ROOT,prompt,model,cancel,emit,on_usage=usage,total_timeout=45,effort='low',session_key=(run,provider))
   row=measure(generate);row.update(provider=provider,model=model,phase=phase,effort='low',wire_characters=len(prompt.render(previous)))
   if phase=='recall':row['context_verified']='ORBIT-47' in row['text']
   rows.append(row);ledger.record(run+':'+provider+':'+phase,provider,model,row['usage'],'增量测试'+row['status'])
   (a.ROOT/'data'/output).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({k:v for k,v in row.items() if k not in ('text','usage')},ensure_ascii=True),flush=True)
   if row['status']!='完成':break
   previous=prompt.state
   if phase!='prepare':state['history'].append({'转录':text,'回答':row['text']})
finally:
 service.close();agy.close_service();claude.close_service()
