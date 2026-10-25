/* Meeting settings and explicit, correlated actions; private drafts stay in memory. */
(() => {
 Object.assign(translations,{
  'Meeting assistance':'会议辅助','Automatic answers':'自动回答','Response pace':'回答节奏',
  'Local speaker labels':'本地说话人标注','Suppress duplicate echo':'抑制重复回声',
  'Recap when pausing':'暂停转录时自动整理','Finish & recap':'结束并整理',
  'Automatic answers use your selected model and its allowance. Long question mode waits for Answer.':'自动回答会使用所选模型及其额度；长问题模式仍等待你点击回答。',
  'Pause transcription to change audio processing. Speaker labels identify the dominant voice per segment; short or uncertain speech keeps its source label. Echo suppression only removes near-identical playback.':'请先暂停转录再修改音频处理。每段标注主要说话人，短句或不确定时保留来源标签；回声抑制仅过滤高度相似的播放声音。',
  'Recaps send the transcript to your selected model and use its allowance.':'整理会将转录发送给所选模型，并消耗其额度。',
  'Scenes · prompt and reference material':'场景 · 提示词与资料',
  'Save the current prompt, notes, reference text and screenshots together. Loading replaces the current context; API keys are never included.':'将当前提示词、笔记、参考文字和截图一起保存。加载会替换当前上下文；不保存 API Key。',
  'Saved scenes':'已保存的场景','Scene name':'场景名称','Load scene':'加载场景','Delete scene':'删除场景','Save scene':'保存场景',
  'Refine an answer':'继续处理回答','Completed answer':'已完成的回答','Shorten':'缩短回答','Give an example':'举例说明','Complete code':'完整代码',
  'Follow-up question':'追问内容','Ask follow-up':'提交追问','No completed answers':'暂无已完成的回答','No saved scenes':'暂无场景'
 });
 const choices={
  auto_answers:[['off','Off','关闭'],['questions','On questions','问题结束后'],['pause','After each pause','每次停顿后']],
  auto_pace:[['fast','Fast','快速'],['balanced','Balanced','均衡'],['relaxed','Relaxed','从容']],
  speaker_labels:[['0','Off','关闭'],['1','On · local CPU','开启 · 本地 CPU']],
  echo_suppression:[['0','Off','关闭'],['1','On · conservative','开启 · 保守过滤']],
  auto_recap:[['0','Off','关闭'],['1','On','开启']]
 };
 const refinements=document.createElement('details');refinements.className='context-section';
 refinements.id='meeting-refinements';
 refinements.innerHTML='<summary data-i="Refine an answer">Refine an answer</summary><label class="context-field"><span data-i="Completed answer">Completed answer</span><select id="meeting-answer"></select></label><div class="context-tools"><button data-refine="shorten" data-i="Shorten">Shorten</button><button data-refine="example" data-i="Give an example">Give an example</button><button data-refine="code" data-i="Complete code">Complete code</button></div><label class="context-field"><span data-i="Follow-up question">Follow-up question</span><input id="meeting-followup" maxlength="10000"></label><button data-refine="followup" data-i="Ask follow-up">Ask follow-up</button><p id="meeting-action-status" role="status"></p>';
 $('output').before(refinements);
 const recap=document.createElement('button');recap.dataset.meeting='finish_recap';recap.dataset.i='Finish & recap';recap.textContent='Finish & recap';
 $('more-menu').append(recap);
 let state=null,busy=false,armed='',seenResult=null;
 const waiters=new Map();
 function options(id,items,empty){
  const el=$(id),key=JSON.stringify([language,items,empty]);
  if(el.dataset.meetingKey===key)return;
  const before=el.value;el.replaceChildren();
  for(const [value,text] of items.length?items:[['',t(empty)]]){const option=document.createElement('option');option.value=value;option.textContent=text;el.append(option)}
  if([...el.options].some(o=>o.value===before))el.value=before;
  el.dataset.meetingKey=key;
 }
 function message(id,text){$(id).textContent=text}
 async function request(action,data){
  const id=crypto.randomUUID();
  let timer;
  const done=new Promise((resolve,reject)=>{
   timer=setTimeout(()=>{waiters.delete(id);reject(new Error(language==='zh'?'操作尚未确认，请查看状态后重试。':'Action not confirmed. Check status before retrying.'))},15000);
   waiters.set(id,{resolve,reject});
  });
  try{await command(action,{...data,id});return await done}
  finally{clearTimeout(timer);waiters.delete(id)}
 }
 async function sceneAction(action,button){
  if(!state||busy)return;
  const name=action==='save_scene'?$('scene-name').value.trim():$('scene-picker').value;
  if(!name){message('scene-status',language==='zh'?'请选择场景或填写名称。':'Select a scene or enter a name.');return}
  const needsConfirm=action!=='save_scene'||state.meeting.scenes.includes(name),key=action+name;
  if(needsConfirm&&armed!==key){armed=key;message('scene-status',language==='zh'?'再次点击以确认此操作；加载会替换当前上下文和草稿。':'Click again to confirm; loading replaces current context and drafts.');return}
  armed='';busy=true;button.disabled=true;
  try{
   if(action==='save_scene')await window.contextEditor.apply();
   // The context editor waits for its version acknowledgement before resolving.
   await request(action,{name,version:state.meeting.scene_version,context_version:state.context_version,overwrite:needsConfirm});
   if(action==='load_scene')window.contextEditor.discard();
   message('scene-status',language==='zh'?'操作完成。':'Done.');
  }catch(error){message('scene-status',error.message)}
  finally{busy=false;button.disabled=false}
 }
 for(const key of Object.keys(choices))$(key).addEventListener('change',async()=>{try{await save(key,$(key).value)}catch{}});
 document.querySelectorAll('[data-meeting]').forEach(button=>button.addEventListener('click',async()=>{
  if(button.dataset.meeting.endsWith('_scene'))return sceneAction(button.dataset.meeting,button);
  if(busy)return;busy=true;button.disabled=true;
  try{await window.contextEditor.apply();await request('finish_recap',{})}
  catch(error){message('meeting-action-status',error.message)}finally{busy=false;button.disabled=false}
 }));
 refinements.querySelectorAll('[data-refine]').forEach(button=>button.addEventListener('click',async()=>{
  if(busy)return;busy=true;button.disabled=true;
  try{
   await window.contextEditor.apply();
   await request('quick_answer',{job:Number($('meeting-answer').value),kind:button.dataset.refine,text:$('meeting-followup').value});
   message('meeting-action-status',language==='zh'?'已创建回答任务。':'Answer task created.');
  }catch(error){message('meeting-action-status',error.message)}finally{busy=false;button.disabled=false}
 }));
 window.meetingUI={render(s){
  state=s;const m=s.meeting||{scenes:[],answers:[]};state.meeting=m;
  for(const [key,items] of Object.entries(choices)){
   options(key,items.map(([value,en,zh])=>[value,language==='zh'?zh:en]),'');
   if(!pending.has(key))$(key).value=s.options[key]||items[0][0];
   $(key).disabled=!!s.listening&&['speaker_labels','echo_suppression'].includes(key);
  }
  options('scene-picker',(m.scenes||[]).map(name=>[name,name]),'No saved scenes');
  options('meeting-answer',(m.answers||[]).map(answer=>[String(answer.id),answer.label]),'No completed answers');
  refinements.querySelectorAll('button').forEach(button=>button.disabled=busy||!(m.answers||[]).length);
  $('speaker-status').textContent=s.speaker_note||'';
  if(m.scenes_error)message('scene-status',m.scenes_error);
  document.querySelectorAll('[data-meeting="finish_recap"]').forEach(button=>button.disabled=busy||!!m.recap_pending);
  if(m.result&&m.result.id!==seenResult){
   seenResult=m.result.id;const waiter=waiters.get(m.result.id);
   if(waiter){m.result.ok?waiter.resolve(m.result):waiter.reject(new Error(m.result.error));waiters.delete(m.result.id)}
  }
 }};
})();
