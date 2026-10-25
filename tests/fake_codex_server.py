import json
import sys
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
import threading
import time

lock=threading.Lock();stops={};counter=0
def send(value):
    with lock:print(json.dumps(value),flush=True)
def emit(method,thread,turn_id,**kwargs):
    send({'method':method,'params':{'threadId':thread,'turnId':turn_id,**kwargs}})
def run(thread,turn,text):
    if text=='crash':
        import os
        os._exit(1)
    for part in ('first:'+text,':last'):
        if stops[turn].wait(.25 if text=='slow' else .02):
            emit('turn/completed',thread,turn,turn={'id':turn,'status':'interrupted'});return
        emit('item/agentMessage/delta',thread,turn,itemId='message',delta=part)
    emit('item/completed',thread,turn,item={'id':'message','type':'agentMessage','text':'first:'+text+':last'})
    emit('thread/tokenUsage/updated',thread,turn,tokenUsage={'last':{'inputTokens':8,'outputTokens':4,'totalTokens':12}})
    emit('turn/completed',thread,turn,turn={'id':turn,'status':'failed' if text=='fail' else 'completed'})
for line in sys.stdin:
    message=json.loads(line);method=message.get('method');p=message.get('params',{});result={}
    if method=='thread/start':
        assert p['ephemeral'] and p['sandbox']=='read-only' and p['approvalPolicy']=='never'
        counter+=1;result={'thread':{'id':'thread'+str(counter)}}
    elif method=='turn/start' and p['threadId']=='expired':
        send({'id':message['id'],'error':{'code':-32600,'message':'thread not found'}});continue
    elif method=='turn/start':
        turn='turn'+p['threadId'];stops[turn]=threading.Event()
        result={'turn':{'id':turn}}
    elif method=='turn/interrupt':stops[p['turnId']].set()
    if 'id' in message:send({'id':message['id'],'result':result})
    if method=='turn/start':threading.Thread(target=run,args=(p['threadId'],turn,p['input'][0]['text']),daemon=True).start()
