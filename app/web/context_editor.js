/* Shared, explicit drafts for settings and the floating context editor.
   Text stays in memory until applied; never store private context in localStorage. */
(() => {
 const keys=['profile','documents','instructions'],draft=new Map();
 let baseVersion=null,flight=null,notice='',clearArmed=false,clearTimer;
 let templateBusy=false,armed='',librarySignature='';
 Object.assign(translations,{
  'Reset position':'恢复位置','Answer requirements':'回答要求',
  'Analysis · AI-generated':'资料分析 · AI 生成',
  'Analysis is a reference, not a confirmed fact. Editing sources clears it.':'分析仅供参考，不代表已确认事实；修改资料后会清除。',
  'Conversation memory':'问答记忆','Use previous Q&A':'回答时带上历史问答',
  'Clear Q&A memory':'清空问答记忆',
  'Keeps your notes, transcript and visible answers. Already sent content cannot be recalled from a provider.':'保留资料、转录和已显示的回答。已发送给服务商的内容无法撤回。',
  'Apply changes':'应用修改','Discard draft':'放弃草稿'
  ,'Prompt':'提示词（Prompt）','Describe the role, task and answer format. Put background facts in the sources below.':'填写 AI 的角色、任务和回答格式；背景事实放在下方资料中。',
  'Prompt templates · saved on this computer':'提示词模板 · 保存在本机','Saved templates':'已保存的模板',
  'Load into editor':'载入编辑区','Delete template':'删除模板','Template name':'模板名称','Save as template':'保存为模板',
  'Built-in scenarios':'内置场景','Use preset':'使用预设',
  'Loads an editable draft. Apply it to use it for future requests.':'载入为可编辑草稿，应用后用于后续请求。'
 });
 const local=(zh,en)=>language==='zh'?zh:en;
 const presetControls=[];let presetArmed='';
 for(const [prefix,target] of [['builtin','context-instructions'],['settings-builtin','instructions']]){
  const box=document.createElement('div');box.className='builtin-prompts';
  const label=document.createElement('label'),title=document.createElement('span');title.dataset.i='Built-in scenarios';title.textContent=t('Built-in scenarios');
  const select=document.createElement('select');select.id=prefix+'-prompt';label.append(title,select);
  const load=document.createElement('button');load.id=prefix+'-load';load.dataset.i='Use preset';load.textContent=t('Use preset');
  const hint=document.createElement('p');hint.dataset.i='Loads an editable draft. Apply it to use it for future requests.';hint.textContent=t(hint.dataset.i);
  box.append(label,load,hint);$(target).closest('label').before(box);presetControls.push({select,load});
  select.onchange=()=>{presetArmed='';for(const item of presetControls)item.load.textContent=t('Use preset');renderPresets(current)};
  load.onclick=()=>{
   const preset=current?.prompt_presets?.find(item=>item.id===select.value);if(!preset)return;
   const existing=$('context-instructions').value;
   if(existing.trim()&&existing!==preset.text&&presetArmed!==prefix+':'+preset.id){
    presetArmed=prefix+':'+preset.id;load.textContent=local('确认替换提示词','Confirm replacing prompt');return;
   }
   presetArmed='';for(const item of presetControls)item.load.textContent=t('Use preset');
   $('context-instructions').value=preset.text;edit('instructions',$('context-instructions'));
   $('prompt-status').textContent=local('已载入内置场景草稿；应用后生效。','Built-in scenario loaded as a draft. Apply to use it.');
  };
 }
 function renderPresets(s){
  for(const {select,load} of presetControls){
   const values=s.prompt_presets||[],signature=JSON.stringify([values,language]);
   if(select.dataset.signature!==signature){
    presetArmed='';for(const item of presetControls)item.load.textContent=t('Use preset');
    const previous=select.value;select.replaceChildren(new Option(local('选择场景…','Choose a scenario…'),''));
    for(const preset of values)select.add(new Option(language==='zh'?preset.name_zh:preset.name,preset.id));
    select.value=previous;select.dataset.signature=signature;
   }
   load.disabled=!select.value||!!flight;
  }
 }
 const settingsBar=document.createElement('div');settingsBar.className='context-settings-save';
 const settingsApply=document.createElement('button');settingsApply.dataset.i='Apply changes';
 const settingsStatus=document.createElement('span');settingsStatus.setAttribute('role','status');
 settingsBar.append(settingsApply,settingsStatus);$('context').append(settingsBar);
 function status(message){notice=message;$('context-edit-status').textContent=message;settingsStatus.textContent=message;}
 function render(s){
  for(const key of keys)for(const id of [key,'context-'+key]){
   const el=$(id),value=draft.has(key)?draft.get(key):s[key]||'';
   if(el.value!==value)el.value=value;
  }
  $('context-history').checked=!!s.history;
  const count=s.history_count||0;
  $('context-summary').textContent=local(
   `当前资料：${s.documents.length.toLocaleString()} 字 · ${s.images.length} 张截图 · ${s.history?count:0} 轮问答`,
   `Current context: ${s.documents.length.toLocaleString()} characters · ${s.images.length} screenshots · ${s.history?count:0} Q&A turns`);
  $('context-memory-status').textContent=s.history?
   local(`后续回答会带上 ${count} 轮问答及本轮完整转录。`,`Future answers include ${count} Q&A turns and the complete current transcript.`):
   local(`历史问答未发送；本机保留 ${count} 轮。资料和本轮转录仍会发送。`,`History is excluded; ${count} turns remain locally. Sources and the current transcript are still included.`);
  $('context-analysis').textContent=s.summary||local('暂无分析。可先添加资料，再点击“先分析资料”。','No analysis yet. Add sources, then choose Analyze first.');
  $('context-apply').disabled=settingsApply.disabled=!!flight||!draft.size;
  $('context-reload').disabled=!!flight||!draft.size;
  if(!flight)status(notice|| (draft.size?local('有未应用的修改；点击应用，或回答时自动应用。','Unapplied changes. Apply now, or they will be applied before answering.'):local('当前资料已应用。加密保存后，下次启动可继续使用。','Current context is applied. Save encrypted to reuse it after restarting.')));
  renderTemplates(s);
  renderPresets(s);
 }
 function edit(key,el){
  presetArmed='';
  for(const item of presetControls)item.load.textContent=t('Use preset');
  if(key==='instructions')resetArmed();
  if(baseVersion===null)baseVersion=current?.context_version;
  draft.set(key,el.value);notice='';
  for(const id of [key,'context-'+key])if($(id)!==el)$(id).value=el.value;
  if(current)render(current);
 }
 for(const key of keys)for(const id of [key,'context-'+key])$(id).addEventListener('input',()=>edit(key,$(id)));
 function resetArmed(){
  armed='';
  for(const [id,label] of [['prompt-load','Load into editor'],['prompt-delete','Delete template'],['prompt-save','Save as template']])$(id).textContent=t(label);
 }
 function confirmAction(key,button,message){
  if(armed===key){resetArmed();return true;}
  resetArmed();armed=key;button.textContent=message;return false;
 }
 function renderTemplates(s){
  const templates=s.prompt_templates||{},select=$('prompt-template');
  const signature=JSON.stringify([templates,language]);
  if(signature!==librarySignature){
   const selected=select.value;librarySignature=signature;resetArmed();
   select.replaceChildren();
   select.add(new Option(local('选择模板…','Choose a template…'),''));
   for(const name of Object.keys(templates))select.add(new Option(name,name));
   select.value=Object.hasOwn(templates,selected)?selected:'';
  }
  const unavailable=templateBusy||!!s.prompt_templates_error;
  for(const id of ['prompt-load','prompt-delete'])$(id).disabled=unavailable||!select.value;
  $('prompt-save').disabled=unavailable;
  select.disabled=templateBusy;$('prompt-name').disabled=templateBusy;
  const placeholder=local('例如：你是面试辅助助手。先给可直接口述的回答，再补充解释；不要编造经历。','Example: Act as an interview assistant. Start with an answer I can say aloud, then explain. Do not invent experience.');
  for(const id of ['instructions','context-instructions'])$(id).placeholder=placeholder;
  if(s.prompt_templates_error)$('prompt-status').textContent=local('模板文件读取失败，原文件已保留。请检查本机加密文件。','Could not read the template library. The original encrypted file was preserved.');
 }
 $('prompt-template').onchange=()=>{
  resetArmed();$('prompt-name').value=$('prompt-template').value;
  $('prompt-status').textContent='';renderTemplates(current);
 };
 $('prompt-name').oninput=()=>resetArmed();
 $('prompt-load').onclick=()=>{
  const name=$('prompt-template').value,text=current?.prompt_templates?.[name];
  if(typeof text!=='string')return;
  const existing=$('context-instructions').value;
  if(existing.trim()&&existing!==text&&!confirmAction('load:'+name,$('prompt-load'),local('确认替换编辑区','Confirm replacing editor text')))return;
  $('context-instructions').value=text;edit('instructions',$('context-instructions'));
  $('prompt-status').textContent=local('已载入草稿；应用后生效。','Loaded as a draft. Apply to use it.');
 };
 async function templateCommand(action,extra){
  const id=crypto.randomUUID();templateBusy=true;renderTemplates(current);
  $('prompt-status').textContent=local('正在保存…','Saving…');
  try{
   await command(action,{id,version:current.prompt_templates_version,...extra});
   const deadline=Date.now()+8000;
   while(current?.prompt_result?.id!==id){
    if(Date.now()>deadline)throw Error('timeout');
    await new Promise(resolve=>setTimeout(resolve,80));
   }
   if(!current.prompt_result.ok)throw Error(current.prompt_result.error);
   $('prompt-status').textContent=action==='delete_prompt_template'?local('模板已删除；编辑区内容保留。','Template deleted; editor text kept.'):local('模板已加密保存到本机。保存模板不会自动应用。','Template saved encrypted on this computer. It has not been applied.');
   if(action==='save_prompt_template')$('prompt-template').value=extra.name;
  }catch{ $('prompt-status').textContent=local('操作未确认成功；编辑内容已保留，请检查模板列表后重试。','Operation not confirmed. Editor text retained; check the library and retry.'); }
  finally{templateBusy=false;resetArmed();renderTemplates(current);}
 }
 $('prompt-save').onclick=()=>{
  const name=$('prompt-name').value.trim(),text=$('context-instructions').value;
  if(!name||!text.trim()){$('prompt-status').textContent=local('请填写提示词和模板名称。','Enter a prompt and a template name.');return;}
  const exists=Object.hasOwn(current?.prompt_templates||{},name);
  if(exists&&!confirmAction('save:'+name,$('prompt-save'),local('确认覆盖同名模板','Confirm replacing template')))return;
  templateCommand('save_prompt_template',{name,text,overwrite:exists});
 };
 $('prompt-delete').onclick=()=>{
  const name=$('prompt-template').value;if(!name)return;
  if(!confirmAction('delete:'+name,$('prompt-delete'),local('确认删除模板','Confirm deleting template')))return;
  templateCommand('delete_prompt_template',{name});
 };
 async function commit(){
  const values=Object.fromEntries(draft),version=baseVersion,id=crypto.randomUUID();
  status(local('正在应用…','Applying…'));
  try{
   await command('apply_context',{values,version,id});
   const deadline=Date.now()+8000;
   while(current?.context_edit?.id!==id){
    if(Date.now()>deadline)throw Error(local('未收到确认，草稿已保留；连接恢复后请检查当前内容。','No confirmation received. Draft retained; check context after reconnecting.'));
    await new Promise(resolve=>setTimeout(resolve,80));
   }
   if(!current.context_edit.ok)throw Error(local('资料已在其他操作中变更。草稿仍保留；请复制需要的内容，再放弃草稿加载最新资料。','Context changed elsewhere. Draft retained; copy anything you need before discarding it to reload current sources.'));
   for(const [key,value] of Object.entries(values))if(draft.get(key)===value)draft.delete(key);
   baseVersion=draft.size?current.context_version:null;
   notice=local('已应用；后续回答使用最新资料。','Applied. Future answers use the updated context.');
  }catch(error){status(error.message);throw error;}
  finally{flight=null;if(current)render(current);}
 }
 function apply(){
  if(flight)return flight.then(()=>draft.size?apply():undefined);
  if(!draft.size)return Promise.resolve();
  flight=commit();if(current)render(current);return flight;
 }
 for(const button of [$('context-apply'),settingsApply])button.onclick=()=>apply().catch(()=>{});
 $('context-reload').onclick=()=>{draft.clear();baseVersion=null;notice='';render(current);};
 $('context-history').onchange=()=>save('history',$('context-history').checked).catch(()=>{});
 $('context-clear-history').onclick=async()=>{
  const button=$('context-clear-history');
  if(!clearArmed){
   clearArmed=true;button.textContent=local('再次点击确认清空','Click again to confirm');
   clearTimeout(clearTimer);clearTimer=setTimeout(()=>{clearArmed=false;button.textContent=t('Clear Q&A memory');},5000);return;
  }
  clearArmed=false;clearTimeout(clearTimer);button.disabled=true;
  try{await command('clear_history');}catch{}finally{button.disabled=false;button.textContent=t('Clear Q&A memory');}
 };
 $('context-reset').onclick=()=>{for(const key of ['left','right','top','bottom','width','height'])contextDrawer.style[key]='';scheduleShape();};
 function show(open){contextDrawer.hidden=!open;$('context-toggle').setAttribute('aria-expanded',String(open));scheduleShape();if(!open)$('context-toggle').focus();}
 $('context-toggle').setAttribute('aria-controls','context-drawer');$('context-toggle').setAttribute('aria-expanded','false');
 $('context-toggle').onclick=()=>show(contextDrawer.hidden);
 $('context-close').onclick=()=>show(false);
 document.addEventListener('keydown',event=>{
  if(event.key==='Escape')$('context-toggle').setAttribute('aria-expanded','false');
  if((event.ctrlKey||event.metaKey)&&event.key==='Enter'&&event.target.closest('#context-drawer,#context')){event.preventDefault();apply().catch(()=>{});}
 });
 window.contextEditor={render,apply,isDirty:key=>draft.has(key),discard:()=>{draft.clear();baseVersion=null;notice='';render(current)}};
 if(language)setLanguage(language);
 if(current)render(current);
})();
