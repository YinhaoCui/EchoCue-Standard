"""Explicit, paid/account-usage test: GPT-6 Astra, identical small coding prompts."""
from pathlib import Path
import json
import sys
import threading
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import audio_answer as app
from codex_service import CodexService
from codex_stream import stream_process

PROMPT='Write a Python function stable_unique(items) that removes duplicate hashable items while preserving order. Return only the function code, no tools or explanations.'
MODEL='gpt-6-astra'
def main():
    results=[]
    run_id='benchmark-'+uuid.uuid4().hex
    ledger=app.TokenLedger(app.ROOT/'data/token_usage.json')
    service=CodexService(app.find_codex(),app.WORK)
    try:
        for mode in ('old_exec','resident_first','resident_reuse_1','resident_reuse_2'):
            chunks=[];usage={};first=[];started=time.monotonic()
            def emit(text):
                if text and not first:first.append(time.monotonic()-started)
                chunks.append(text)
            if mode=='old_exec':
                args=[app.find_codex(),'exec','--json','--ignore-user-config','--ephemeral','--skip-git-repo-check',
                    '--sandbox','read-only','--color','never','--model',MODEL,'-c','model_reasoning_effort="low"',
                    '-c','features.shell_tool=false','-c','web_search="disabled"','-']
                answer=stream_process(args,PROMPT,threading.Event(),app.WORK,180,emit,usage.update)
            else:
                answer=service.answer(PROMPT,MODEL,'low',threading.Event(),emit,usage.update,timeout=180)
            row={'mode':mode,'model':MODEL,'effort':'low','first_seconds':first[0] if first else None,
                 'total_seconds':time.monotonic()-started,'characters':len(answer),'usage':usage,
                 'pid':service.process.pid if mode!='old_exec' else None,'answer':answer}
            results.append(row)
            ledger.record(run_id+':'+mode,'Codex',MODEL,usage,'测速完成')
            print(json.dumps({k:v for k,v in row.items() if k!='answer'},ensure_ascii=True),flush=True)
            (app.ROOT/'data/codex_resident_benchmark.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:service.close()
if __name__=='__main__':main()
