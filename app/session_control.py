"""Session saving and recovery, transcript edits and the glossary."""
import copy
import json
import math
import statistics
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from session_data import SessionStore, SessionWriter, record_text


def latency_summary(job):
    timing=job.get('timing',{})
    if not timing:return '等待转录定稿'
    parts=[f"本机派发 {timing.get('dispatch',0):.2f}s",f"转录等待 {timing.get('asr_wait',0):.2f}s"]
    if 'context_prepare' in timing:parts.append(f"资料准备 {timing['context_prepare']:.2f}s")
    if 'first_reply' in timing:
        parts.append(f"模型首字 {timing['first_reply']:.2f}s")
        parts.append(f"按键到接收 {timing['first_total']:.2f}s")
    if 'first_display' in timing:
        parts.append(f"按键到显示 {timing['first_display']:.2f}s")
        parts.append(f"界面排队 {timing.get('display_queue',0):.2f}s")
    elif 'model_start' in timing and 'first_reply' not in timing:
        wait=timing.get('model_elapsed',max(0,time.monotonic()-job['started']-timing['model_start']))
        parts.append(f"模型等待 {wait:.1f}s（尚无正文）")
    if 'generation' in timing:parts.append(f"正文生成 {timing['generation']:.2f}s")
    if timing.get('speculative'):parts.append('预生成命中')
    return ' · '.join(parts)


def latency_statistics(jobs):
    groups={}
    for job in jobs.values():
        if 'first_display' not in job.get('timing',{}):continue
        groups.setdefault((job.get('provider',''),job.get('model',''),job.get('effort',''),bool(job['timing'].get('speculative'))),[]).append(job['timing']['first_display'])
    lines=[]
    for (provider,model,effort,predicted),samples in groups.items():
        samples.sort();p95=samples[max(0,math.ceil(.95*len(samples))-1)]
        name=f'{provider} / {model}'+(f' / {effort}' if effort else '')
        lines.append(f"{name} · {'预生成' if predicted else '实时生成'} · {len(samples)} 次 · 按键到显示中位 {statistics.median(samples):.2f}s / P95 {p95:.2f}s")
    eligible=[job for job in jobs.values() if job.get('prediction_eligible')]
    if eligible:
        hits=sum(bool(job.get('timing',{}).get('speculative')) for job in eligible)
        lines.append(f'预生成采用率 {hits}/{len(eligible)}（{hits/len(eligible):.0%}）；取消和失败不记为零延迟')
    return '\n'.join(lines)


class SessionControl:
    def record_first_display(self,job):
        now=time.monotonic();timing=job.setdefault('timing',{})
        timing.setdefault('first_display',max(0,now-job['started']))
        timing.setdefault('display_queue',max(0,now-max(job['started'],timing.get('first_received_at',now))))

    def init_sessions(self):
        import audio_answer as a
        self.live_dirty = False
        self.last_live_render = 0
        self.last_session_tick = 0
        self.last_session_save = time.monotonic()
        self.session_disabled = False
        self.session_writer = None
        self.session_store = SessionStore(a.data_path(a.ROOT, 'sessions.sqlite3'))
        self.session_note = tk.StringVar(value='会话每 5 秒本机加密保存')
        self.pipeline_note = tk.StringVar(value='转录引擎：待机')
        self.terms = self.saved.get('terms','')
        self.live.terms = self.terms

    def session_tick(self):
        now = time.monotonic()
        if self.live_dirty and now-self.last_live_render >= .12 and self.follow_live:
            self.render_live_transcript()
            self.live_dirty=False;self.last_live_render=now
        if now-self.last_session_tick < .5: return
        self.last_session_tick=now
        with self.live.lock:
            seconds=self.live.queued_bytes/(self.live.rate*2)
            lag=self.live.processing_lag if seconds or now-self.live.last_processed<2 else 0
        self.pipeline_note.set(f'积压 {seconds:.1f} 秒 · 处理等待 {lag:.2f} 秒'
                               + (' · 正在追赶，音频完整保留' if seconds>2 else ''))
        if now-self.last_session_save>=5:
            self.save_session()
            self.last_session_save=now

    def session_payload(self):
        with self.live.lock:
            records=copy.deepcopy(self.live.records)
        if not records and not self.jobs and not self.live_drafts and not self.context_images and not getattr(self,'session_checkpoint_exists',False): return None
        jobs=[]
        for identity,job in self.jobs.items():
            item={k:v for k,v in job.items() if k not in ('cancel','mark','started','timeout')}
            item['id']=identity
            item['elapsed']=job.get('elapsed',time.monotonic()-job['started'])
            if item.get('target') is not None: item.pop('transcript',None)
            jobs.append(item)
        payload={'title':time.strftime('%Y-%m-%d')+' · '+(records[0].get('body','')[:35] if records else '回答会话'),
                 'history':copy.deepcopy(self.history),'profile':self.profile,'documents':self.documents,'instructions':self.instructions.get(),
                 'summary':self.context_summary,'images':copy.deepcopy(self.context_images),'terms':self.terms,'drafts':copy.deepcopy(self.live_drafts),
                 'edits':copy.deepcopy([r for r in self.transcript_records if 'original' in r and not (isinstance(r['id'],int) and r['id']<0)])}
        for record in records: payload['segment:'+str(record['sequence'])]=record
        for job in jobs: payload['job:'+str(job['id'])]=job
        return payload

    def save_session(self):
        if self.session_disabled: return
        payload=self.session_payload()
        if payload is None: return
        self.session_checkpoint_exists=True
        if self.session_writer is None:
            self.session_writer=SessionWriter(self.session_store,lambda text:self.events.put(('session_saved',text)))
        self.session_writer.submit(self.session_id,payload)

    def session_browser(self):
        self.save_session()
        win=tk.Toplevel(self.root);win.title('本机加密会话');win.geometry('750x440')
        tree=ttk.Treeview(win,columns=('date','title'),show='headings')
        tree.heading('date',text='最后保存');tree.heading('title',text='会话')
        tree.column('date',width=150);tree.column('title',width=500)
        tree.pack(fill='both',expand=True,padx=12,pady=12)
        def refresh():
            tree.delete(*tree.get_children())
            try:
                for identity,stamp,title in self.session_store.list():
                    tree.insert('', 'end',iid=identity,values=(time.strftime('%m-%d %H:%M',time.localtime(stamp)),title))
            except Exception as exc: messagebox.showerror('读取失败',str(exc),parent=win)
        def restore():
            if not tree.selection(): return
            if self.capture.active() or self.mic.active() or any(not j['done'] for j in self.jobs.values()):
                messagebox.showinfo('正在运行','请先停止监听并等待回答结束，再恢复会话。',parent=win);return
            self.save_session()
            if self.session_writer: self.session_writer.close();self.session_writer=None
            try: payload=self.session_store.load(tree.selection()[0]);self.restore_payload(payload)
            except Exception as exc: messagebox.showerror('恢复失败',str(exc),parent=win);return
            # Restoring creates a separate session so the saved source is preserved.
            import uuid
            self.session_id=uuid.uuid4().hex;self.session_disabled=False
            win.destroy()
        def delete():
            if not tree.selection(): return
            identity=tree.selection()[0]
            if not messagebox.askyesno('删除会话','删除选中的本机保存记录？此操作不可恢复。',parent=win): return
            if identity==self.session_id:
                self.session_disabled=True
                if self.session_writer: self.session_writer.close();self.session_writer=None
                self.session_note.set('本次会话保存已停止；重启或恢复其他会话后恢复自动保存')
            self.session_store.delete(identity);refresh()
        row=ttk.Frame(win);row.pack(fill='x',padx=12,pady=8)
        for title,command in [('刷新',refresh),('恢复选中会话',restore),('删除选中记录',delete)]:
            ttk.Button(row,text=title,command=command).pack(side='left',padx=4)
        refresh()

    def restore_payload(self,payload):
        from streaming_asr import StreamingLiveTranscriber
        import queue
        payload=copy.deepcopy(payload)
        self.live.close()
        self.live.thread.join(timeout=2)
        keep=[]
        while True:
            try: event=self.events.get_nowait()
            except queue.Empty: break
            if not event[0].startswith('live_') and event[0]!='job':keep.append(event)
        for event in keep:self.events.put(event)
        self.live=StreamingLiveTranscriber(self.live.root,lambda kind,value:self.events.put((kind,value)))
        self.live.engine=self.advanced['asr_engine'].get()
        self.update_asr_pause()
        self.preload_asr()
        records=sorted([v for k,v in payload.items() if k.startswith('segment:')],key=lambda r:r['sequence'])
        self.live.records=records
        self.live.completed=self.live.submitted=max((r['sequence'] for r in records),default=0)
        for record in records:
            self.live.sources[record['source']]=dict(pre=b'',data=0,quiet=0,generation=record['generation'],
                                                   detector=__import__('speech_activity').SpeechActivity(self.live.rate))
        self.live_text=record_text(records)
        from live_transcription import append_transcript
        self.live_last_source=append_transcript('',None,records[-1])[1] if records else None
        if hasattr(self, 'auto_answers'):
            self.reset_meeting()
        self.live_drafts={} # Unconfirmed text is restored as a separate, editable record below.
        self.history=payload.get('history',[])
        self.profile=payload.get('profile','');self.documents=payload.get('documents','')
        self.instructions.set(payload.get('instructions',''))
        self.context_summary=payload.get('summary','');self.terms=payload.get('terms','');self.live.terms=self.terms
        self.context_images=payload.get('images',[]);self.update_screenshot_note()
        self.jobs.clear();self.job_labels.clear();self.transcript_records.clear()
        self.context_version+=1
        self.put_text('',replace=True)
        for record in records: self.remember_transcript(record['text'],-record['sequence'],select=False)
        for index,(source,draft) in enumerate(payload.get('drafts',{}).items()):
            self.remember_transcript('[恢复的未确认草稿 · '+source+']\n'+draft['text'], 'draft-'+str(index),select=False)
        for item in sorted([v for k,v in payload.items() if k.startswith('job:')],key=lambda j:j['id']):
            identity=item.pop('id');was_done=item.get('done',False)
            item.update(cancel=threading.Event(),done=True,started=time.monotonic()-item.get('elapsed',0),timeout=float('inf'))
            if item.get('target') is not None: item['transcript']=record_text(records,item['target'])
            if not was_done: item['state']='已中断（从会话恢复）'
            self.jobs[identity]=item;self.job_labels[identity]=item['label']
            self.put_text('\n\n'+item['label']+'\n')
            self.add_answer_region(identity,item.get('answer',''))
        self.ask_revision=max(self.jobs,default=0)
        for record in payload.get('edits',[]):
            self.remember_transcript(record['text'],record['id'],select=False)
            self.transcript_records[-1]['original']=record['original']
        self.follow_live=True;self.render_live_transcript()
        self.status.set('会话已恢复；未完成的任务保留正文，可手动重试。')

    def edit_transcript(self):
        index=self.selected_transcript
        if not 0<=index<len(self.transcript_records):
            self.status.set('请先选择需要修改的转录。');return
        record=self.transcript_records[index]
        win=tk.Toplevel(self.root);win.title('编辑转录');win.geometry('750x480')
        text=tk.Text(win,wrap='word');text.pack(fill='both',expand=True,padx=12,pady=12)
        text.insert('1.0',record['text'])
        def save(answer=False):
            self.update_transcript(record,text.get('1.0','end-1c'))
            win.destroy()
            if answer: self.ask(reuse=True)
        row=ttk.Frame(win);row.pack(fill='x',padx=12,pady=8)
        ttk.Button(row,text='保存修改',command=save).pack(side='left')
        ttk.Button(row,text='保存并用当前模型回答',command=lambda:save(True)).pack(side='left',padx=8)

    def update_transcript(self,record,text):
        record.setdefault('original',record['text']);record['text']=text
        identity=record['id']
        if isinstance(identity,int) and identity<0:
            with self.live.lock:
                for segment in self.live.records:
                    if segment['sequence']==-identity:
                        segment.setdefault('original',segment['text'])
                        segment['text']=text
                        segment['body']=text.split('\n',1)[1] if text.startswith('[') and '\n' in text else text
                self.live_text=record_text(self.live.records)
        self.select_transcript();self.save_session()

    def edit_terms(self):
        win=tk.Toplevel(self.root);win.title('术语表');win.geometry('680x420')
        ttk.Label(win,text='每行一个术语，供回答参考；纠错使用“识别错误 => 正确术语”。\n纠错仅应用于后续语音，替换结果请核对。').pack(anchor='w',padx=12,pady=10)
        text=tk.Text(win,wrap='word');text.pack(fill='both',expand=True,padx=12);text.insert('1.0',self.terms)
        def save():
            self.terms=text.get('1.0','end-1c');self.live.terms=self.terms
            self.save_preferences();win.destroy()
        ttk.Button(win,text='保存术语表',command=save).pack(anchor='e',padx=12,pady=8)

    def export_session(self):
        path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.md',filetypes=[('Markdown','.md'),('JSON','.json')])
        if not path:return
        payload=self.session_payload() or {}
        from pathlib import Path
        if path.endswith('.json'): content=json.dumps(payload,ensure_ascii=False,indent=2)
        else: content='# 转录\n\n'+self.live_text+'\n\n# 回答\n\n'+'\n\n'.join(j['label']+'\n'+j['answer'] for j in self.jobs.values())
        try: Path(path).write_text(content,encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('导出失败',str(exc),parent=self.root);return
        self.status.set('已导出会话；导出文件是可阅读的明文。')
