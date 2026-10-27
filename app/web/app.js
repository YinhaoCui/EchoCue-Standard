/* Local presentation only. Text from models and transcripts is never interpreted as HTML. */
const $ = id => document.getElementById(id);
const token = location.hash.slice(1);
history.replaceState(null, '', '/');
let current = null, language = 'en', inFlight = false;
const pending = new Map();
// A page message stays up for a few seconds before the next poll's status replaces it.
let noticeUntil = 0;
function notice(text){ $('status').textContent=text; noticeUntil=Date.now()+4000; }
const translations = {
 'Caption translation model':'字幕翻译模型','Translation provider':'翻译平台','Translation model':'翻译模型','Translation model ID':'翻译模型 ID',
 'Refresh translation models':'刷新翻译模型','Auto · prefer fast models':'自动 · 优先快速模型','Same provider as answers':'与回答使用相同平台',
 'Independent of answers. Uses the lowest supported thinking level. API keys are shared with the selected provider settings.':'独立于回答模型，自动使用最低支持的思考档；API Key 沿用所选平台的配置。',
 Transparency:'透明度',Taskbar:'任务栏','Tray icon':'托盘图标',Analysis:'分析结果',Screenshots:'截图',On:'已开启',Off:'已关闭',
 'Background':'背景效果','Microphone device':'麦克风设备','Check APIs':'检测 API','Edit transcript':'编辑转录','Vocabulary':'术语词典','Export session':'导出会话',
 'Transcript finalization':'转录定稿速度','Incremental context':'增量上下文','Request timeout':'请求超时','Output tokens':'输出 Token',
 'Cancel answers':'取消回答',
 Settings:'设置',Listen:'监听',Ready:'待机',Listening:'监听中',Models:'模型',Audio:'音频',Context:'上下文',
 Preferences:'偏好',Shortcuts:'快捷键','Model speed test':'模型测速',
 'Your workspace, ready when you are':'配置好，即可开始','Set up your session':'准备你的会话',
 'AI model':'回答模型','Choose how your answers take shape.':'选择回答模型和思考方式。',Provider:'平台',Model:'模型',
 'Refresh models':'刷新模型','Model ID':'模型 ID','Usage & quota':'用量与额度','API key':'API 密钥','Reasoning effort':'思考强度',
 Thinking:'要求思考','Answer style':'回答方式','Audio & transcription':'音频与转录','Separate listening from answering.':'转录与回答独立设置。',
 'Audio source':'声音来源','Playback device':'播放设备','Transcription engine':'转录引擎','Transcript language':'转录语言',
 'Answer language':'回答语言','Question mode':'提问模式','Long questions wait for you to select Answer.':'长问题会等待你点击回答。',
 'Session context':'会话上下文','Analyze first':'先分析资料','Give your answers the right background.':'添加回答需要的背景资料。',
 'Add file':'添加文件','Capture window':'截取窗口','View screenshots':'查看截图','Personal notes & goals':'个人资料与目标',
 'Reference text':'参考文本','Save context encrypted':'加密保存上下文','Session preferences':'会话偏好',
 'Prepare context':'提前准备上下文','Prediction policy':'预生成策略','Keep conversation history':'保留全部对话',
 'Additional instructions':'补充要求','Observed usage':'本工具记录的用量','Changes are saved on this computer.':'设置保存在本机。',
 'Prepare session':'准备会话','Start transcription':'开始转录','Resume transcription':'继续转录',Pause:'暂停',Answer:'回答',
 Capture:'截图',Pin:'置顶',More:'更多',
 'Session history':'历史会话','Live transcript':'实时转录',Copy:'复制','AI answer':'回答','Answer again':'再次回答','Edit notes':'编辑资料',
 'Connection lost. Reconnecting…':'连接中断，正在重连…','Connecting to the local application…':'正在连接本机程序…',
 'Copied':'已复制','Saved':'已保存','Working…':'处理中…',
 'Smaller text':'缩小文字','Bold text':'文字加粗','Text outline':'文字描边','Text color':'文字颜色','Panel color':'面板颜色','Larger text':'放大文字','Drag to resize · double-click to reset':'拖动调整大小 · 双击恢复默认',
 Layout:'布局',Presets:'预设',Save:'保存','Text and panels':'文字与面板','Reset layout':'恢复默认布局',Window:'窗口',Session:'会话',
 'Preset name':'预设名称',Default:'默认',Compact:'紧凑','Large text':'大字','Delete preset':'删除预设',
 'Interface style':'界面风格','Interface language':'界面语言','Classic Glass':'经典玻璃','Midnight Studio':'深色工作台','Cosmic Gravity':'宇宙引力',
 'Default model':'默认模型',
 'English':'英语','Chinese':'中文','Coding':'编程','Shortcuts ready':'快捷键已就绪',
 'LM Studio URL':'LM Studio 地址',
 'Model options':'模型高级选项','Generation options':'生成与上下文选项','Window appearance':'窗口外观',
 'Resize transcript and answer':'调整转录与回答区域'
 ,'Global shortcuts':'全局快捷键','Save and apply':'保存并应用','Restore defaults':'恢复默认',
 'Create an answer':'生成回答','Always on top':'窗口置顶','Start / pause transcription':'开始／暂停转录',
 'Enter combinations such as Ctrl+Alt+P or Ctrl+Shift+F8. Changes apply after saving.':'填写 Ctrl+Alt+P 或 Ctrl+Shift+F8 等组合，保存后生效。'
};
const optionNames = {
 '电脑':['System audio','电脑'],'麦克风':['Microphone','麦克风'],'电脑 + 麦克风':['System + microphone','电脑 + 麦克风'],
 '长问题':['Long question','长问题'],'快速问答':['Quick Q&A','快速问答'],'开启':['On','开启'],'关闭':['Off','关闭'],
 '自动':['Auto','自动'],'仅疑问句':['Questions only','仅疑问句'],'每段定稿':['Every segment','每段定稿'],
 '中英双语':['Chinese + English','中英双语'],'原文':['Original','原文'],'快速':['Quick','快速'],'推理':['Reasoning','推理'],
 'Antigravity（本机登录）':['Antigravity','Antigravity'],'Claude Code（本机登录）':['Claude Code','Claude Code'],'Kiro（本机登录）':['Kiro','Kiro'],
 '通义千问（北京）':['Qwen (Beijing)','通义千问（北京）']
};
Object.assign(optionNames,{
 '英文 · Zipformer':['English · Zipformer','英文 · Zipformer'],
 '中文 · Zipformer':['Chinese · Zipformer','中文 · Zipformer'],
 '中英混合 · Paraformer':['Bilingual · Paraformer','中英混合 · Paraformer'],
 '快速 · 0.35 秒':['Fast · 0.35 s','快速 · 0.35 秒'],'均衡 · 0.65 秒':['Balanced · 0.65 s','均衡 · 0.65 秒'],'稳妥 · 1.0 秒':['Stable · 1.0 s','稳妥 · 1.0 秒'],'不限时':['Unlimited','不限时']
 ,'服务默认':['Service default','服务默认']
});
const t = text => language === 'zh' ? (translations[text] || text) : text;
const label = text => optionNames[text]?.[language === 'zh' ? 1 : 0] || (language==='en'?text.replace('预算 ','Budget '):text);
function setLanguage(value) {
 language = value; document.documentElement.lang=value;
 document.querySelectorAll('[data-i]').forEach(el => el.textContent=t(el.dataset.i));
 // Toolbar buttons may collapse to icons; keep their names as tooltips.
 document.querySelectorAll('.listen-toolbar [data-i]').forEach(el => el.title=el.textContent);
 document.querySelectorAll('[data-title]').forEach(el => el.title=language==='zh'?t(el.dataset.title)+' · 双击恢复默认':el.dataset.title+' · double-click to reset');
 $('preset-name').placeholder=t('Preset name');presetSignature='';
 $('model').placeholder=t('Default model');
 document.querySelectorAll('[data-font]').forEach(el => {el.title=t(el.dataset.step<0?'Smaller text':'Larger text');el.setAttribute('aria-label',el.title)});
 document.querySelectorAll('.splitter,.side-grip').forEach(el => el.title=t('Drag to resize · double-click to reset'));
}
function choose(id, values, value) {
 const el=$(id);
 if (document.activeElement === el || pending.has(id) || el.getAttribute('aria-expanded')==='true') return;
 const signature=JSON.stringify([values,language]);
 if (el.dataset.options !== signature) {
  el.replaceChildren(...values.map(item => {
   const option=document.createElement('option');
   option.value=typeof item==='object'? item.value:item;
   option.textContent=typeof item==='object'? item.text:label(item);
   return option;
  }));
  el.dataset.options=signature;
 }
 el.value=value;
}
function input(id,value) {
 const el=$(id);
 if(document.activeElement!==el&&!pending.has(id)&&!window.contextEditor?.isDirty(id)) el.value=value??'';
}
function view(name) {
 document.body.dataset.view=name;
 $(name==='listen'?'listen-status':'settings-status').appendChild(document.querySelector('.statusbar'));
 $('settings').hidden=name!=='settings'; $('listen').hidden=name!=='listen';
 document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===name));
 window.workbench?.syncContext();
}
function darkWorkspace(){return ['midnight','cosmic','workbench'].includes(document.body.dataset.theme)}
function midnightColumns(){return darkWorkspace()&&matchMedia('(min-width:1101px)').matches}
function applyTheme(value){
 const choice=['classic','cosmic','workbench'].includes(value)?value:'workbench';
 const theme=choice==='cosmic'?'workbench':choice,palette=choice==='cosmic'?'gold':'light';
 for(const id of ['ui_theme','live-ui-theme'])if($(id)?.options.length)$(id).value=choice;
 if(document.body.dataset.theme===theme&&document.body.dataset.palette===palette)return;
 document.body.dataset.theme=theme;
 document.body.dataset.palette=palette;
 window.workbench?.themeChanged();
 for(const id of ['listen_text_color','listen_panel_color'])applyColor(id,pending.get(id)??current?.options?.[id]);
 requestAnimationFrame(()=>{applyLayout(...layout);positionMenus();scheduleShape()});
}
function textStream(id,value) {
 // Both panels show Markdown; renderMarkdown redraws only the blocks that changed.
 const el=$(id);
 if(el._mdSource===value)return;
 const follow=el.scrollHeight-el.scrollTop-el.clientHeight<60;
 renderMarkdown(el,value||'');
 if(follow) el.scrollTop=el.scrollHeight;
}
function attachments(id,images) {
 const el=$(id), signature=JSON.stringify(images);
 if(el.dataset.signature===signature)return;
 el.dataset.signature=signature;
 el.replaceChildren(...images.map(image=>{
  const button=document.createElement('button');button.textContent='▧ '+image.title+'  ×';
  button.title=language==='zh'?'移除这张截图':'Remove this screenshot';
  button.onclick=()=>command('remove_image',{id:image.id});
  return button;
 }));
}
async function command(action,data={}) {
 try {
  const response=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json','X-Listener-Token':token},body:JSON.stringify({action,...data})});
  if(!response.ok)throw new Error('Request rejected ('+response.status+')');
 } catch(error) { $('status').textContent=error.message; throw error; }
}
async function save(id,value) {
 pending.set(id,value);
 try { await command('settings',{values:{[id]:value}}); }
 finally { setTimeout(()=>pending.delete(id),500); }
}
const fields=['ui_theme','listen_transparency','listen_text_color','listen_panel_color','background_mode','microphone','asr_pause','incremental_context','deadline','max_output','provider','model','key','effort','thinking_policy','answer_mode','source','device','asr_engine','caption','answer','question_mode','warm_context','speculate','history','profile','documents','instructions','lm_base','language'];
fields.push('caption_model');
fields.forEach(id=>$(id).addEventListener('change',async()=>{
 if(['profile','documents','instructions'].includes(id))return;
 const el=$(id), value=el.type==='checkbox'?el.checked:el.value;
 if(id==='ui_theme')applyTheme(value);
 await save(id,value);
 if(id==='provider')await command('refresh');
 if(id==='key')el.value='';
}));
$('model-picker').onchange=async()=>{
 $('model').value=$('model-picker').value;
 await save('model',$('model-picker').value);
};
$('caption_provider').onchange=async()=>{
 const provider=$('caption_provider').value;
 $('caption_model').value='';
 pending.set('caption_provider',provider);pending.set('caption_model','');
 try{await command('settings',{values:{caption_provider:provider,caption_model:''}})}
 finally{setTimeout(()=>{pending.delete('caption_provider');pending.delete('caption_model')},500)}
};
$('caption-model-picker').onchange=()=>{
 $('caption_model').value=$('caption-model-picker').value;
 save('caption_model',$('caption_model').value);
};
[['live-caption','caption'],['live-answer','answer'],['live-mode','question_mode']].forEach(([id,target])=>{
 $(id).onchange=()=>save(target,$(id).value);
});
document.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>view(el.dataset.view));
document.querySelectorAll('[data-section]').forEach(el=>el.onclick=()=>{
 if(el.dataset.section==='preferences')document.querySelector('#preferences details').open=true;
 $(el.dataset.section).scrollIntoView({behavior:'smooth',block:'start'});
 document.querySelectorAll('[data-section]').forEach(b=>b.classList.toggle('active',b===el));
});
document.querySelectorAll('[data-action]').forEach(el=>el.onclick=async()=>{
 const action=el.dataset.action;
 if(action==='hotkeys'){goToShortcuts();return}
 el.disabled=true;
 try{
  // Persist focused text before submission, not on every keystroke.
  if(window.contextEditor)await window.contextEditor.apply();
  await command(action);
  if(action==='prepare')view('listen');
 }catch(error){$('status').textContent=error.message;noticeUntil=Date.now()+8000;}
 finally{el.disabled=false}
});
document.querySelectorAll('[data-window]').forEach(el=>el.onclick=()=>command('window',{value:el.dataset.window}));
document.querySelectorAll('[data-native]').forEach(el=>el.onclick=()=>{
 const fn=el.dataset.native;
 if(window.pywebview?.api?.[fn])window.pywebview.api[fn]();
 else if(fn==='close')command('close');
});
document.querySelectorAll('[data-copy]').forEach(el=>el.onclick=async()=>{
 try{const source=el.dataset.copy==='output'&&document.body.dataset.theme==='workbench'?$('workbench-output'):$(el.dataset.copy);await navigator.clipboard.writeText(source._mdSource??source.textContent);el.textContent=t('Copied');setTimeout(()=>el.textContent=t('Copy'),1000)}
 catch{ $('status').textContent=language==='zh'?'请选择正文后按 Ctrl+C。':'Select the text and press Ctrl+C.'; }
});
$('more').onclick=()=>toggleMenu('more-menu');
$('layout-button').onclick=()=>toggleMenu('layout-menu');
// One toolbar menu open at a time; a click outside closes it.
const MENUS={'more-menu':'more','layout-menu':'layout-button'};
function toggleMenu(id,open=id?$(id).hidden:false){
 for(const [menu,button] of Object.entries(MENUS)){
  const show=menu===id&&open;
  $(menu).hidden=!show;$(button).setAttribute('aria-expanded',String(show));
 }
 positionMenus();scheduleShape();
}
function positionMenus(){
 for(const [id,anchor] of Object.entries(MENUS)){
  const menu=$(id);if(menu.hidden)continue;
  const button=$(anchor).getBoundingClientRect(),parent=menu.offsetParent.getBoundingClientRect();
  const above=document.body.dataset.theme==='workbench'||button.bottom>innerHeight/2;
  const space=Math.max(40,above?button.top-16:innerHeight-button.bottom-16);
  menu.style.maxHeight=Math.min(520,space)+'px';menu.style.maxWidth=(innerWidth-16)+'px';
  const rect=menu.getBoundingClientRect();
  menu.style.right='auto';menu.style.bottom='auto';
  menu.style.left=(Math.max(8,Math.min(button.right-rect.width,innerWidth-rect.width-8))-parent.left)+'px';
  menu.style.top=((above?Math.max(8,button.top-rect.height-8):button.bottom+8)-parent.top)+'px';
 }
}
addEventListener('resize',positionMenus);
document.addEventListener('scroll',positionMenus,true);
document.addEventListener('pointerdown',event=>{
 if(!event.target.closest('.menu,#more,#layout-button'))toggleMenu(null);
});
$('context-toggle').onclick=()=>$('context-drawer').hidden=!$('context-drawer').hidden;
$('context-close').onclick=()=>$('context-drawer').hidden=true;

// Move the context panel independently; its content remains selectable.
const contextDrawer=$('context-drawer');
const contextHandle=contextDrawer.querySelector('.section-title');
let contextDrag=null;
function positionContext(left,top){
 const rect=contextDrawer.getBoundingClientRect();
 const x=Math.max(8,Math.min(left,innerWidth-rect.width-8));
 const y=Math.max(8,Math.min(top,innerHeight-rect.height-8));
 contextDrawer.style.left=x+'px';contextDrawer.style.top=y+'px';
 contextDrawer.style.right='auto';contextDrawer.style.bottom='auto';
 scheduleShape();
}
contextHandle.addEventListener('pointerdown',event=>{
 if(event.button!==0 || event.target.closest('button,input,select,a'))return;
 const rect=contextDrawer.getBoundingClientRect();
 contextDrawer.style.height=rect.height+'px';
 contextDrag={id:event.pointerId,x:event.clientX-rect.left,y:event.clientY-rect.top};
 contextHandle.setPointerCapture(event.pointerId);
 contextHandle.classList.add('dragging');
 event.preventDefault();
});
contextHandle.addEventListener('pointermove',event=>{
 if(contextDrag?.id!==event.pointerId)return;
 positionContext(event.clientX-contextDrag.x,event.clientY-contextDrag.y);
});
function stopContextDrag(event){
 if(contextDrag?.id!==event.pointerId)return;
 contextDrag=null;contextHandle.classList.remove('dragging');
 if(contextHandle.hasPointerCapture(event.pointerId))contextHandle.releasePointerCapture(event.pointerId);
}
for(const name of ['pointerup','pointercancel','lostpointercapture'])contextHandle.addEventListener(name,stopContextDrag);
// Resize the context panel from its corner; it stays inside the viewport.
const contextResize=$('context-resize');
let contextSizing=null;
function sizeContext(width,height){
 const rect=contextDrawer.getBoundingClientRect();
 const w=Math.max(320,Math.min(width,innerWidth-rect.left-8));
 const h=Math.max(220,Math.min(height,innerHeight-rect.top-8));
 contextDrawer.style.width=w+'px';contextDrawer.style.height=h+'px';
 scheduleShape();
}
contextResize.addEventListener('pointerdown',event=>{
 if(event.button!==0)return;
 const rect=contextDrawer.getBoundingClientRect();
 // Pin the top-left corner so only the dragged corner moves.
 positionContext(rect.left,rect.top);
 contextSizing={id:event.pointerId,x:event.clientX,y:event.clientY,width:rect.width,height:rect.height};
 contextResize.setPointerCapture(event.pointerId);
 event.preventDefault();event.stopPropagation();
});
contextResize.addEventListener('pointermove',event=>{
 if(contextSizing?.id!==event.pointerId)return;
 sizeContext(contextSizing.width+event.clientX-contextSizing.x,contextSizing.height+event.clientY-contextSizing.y);
});
function stopContextResize(event){
 if(contextSizing?.id!==event.pointerId)return;
 contextSizing=null;
 if(contextResize.hasPointerCapture(event.pointerId))contextResize.releasePointerCapture(event.pointerId);
}
for(const name of ['pointerup','pointercancel','lostpointercapture'])contextResize.addEventListener(name,stopContextResize);
addEventListener('resize',()=>{
 if(contextDrawer.hidden || !contextDrawer.style.left)return;
 const rect=contextDrawer.getBoundingClientRect();positionContext(rect.left,rect.top);
 if(contextDrawer.style.width)sizeContext(rect.width,rect.height);
});
document.addEventListener('keydown',event=>{
 if(event.key==='Escape'){toggleMenu(null);$('context-drawer').hidden=true}
});
function render(s) {
 if(!s.provider)return;
 current=s;
 if(language!==s.language)setLanguage(s.language);
 if(!pending.has('ui_theme'))applyTheme(s.options.ui_theme||'workbench');
 const styles=[{value:'workbench',text:t('Dual-track Workbench')},{value:'cosmic',text:t('Workbench · Black Gold')},{value:'classic',text:t('Classic Glass')}];
 for(const id of ['ui_theme','live-ui-theme'])choose(id,styles,pending.get('ui_theme')||s.options.ui_theme||'workbench');
 if(document.activeElement!==$('listen_transparency')&&!pending.has('listen_transparency'))applyTransparency(s.options.listen_transparency||12);
 for(const id of ['listen_text_color','listen_panel_color'])
  if(document.activeElement!==$(id)&&!pending.has(id))applyColor(id,s.options[id]);
 for(const id of TOGGLES)if(!pending.has(id))applyToggle(id,s.options[id]||'0');
 document.body.dataset.background=s.options.background_mode||'frosted';
 choose('background_mode',[{value:'translucent',text:s.language==='zh'?'半透明底色':'Translucent'},{value:'frosted',text:s.language==='zh'?'磨砂底色':'Frosted surface'},{value:'opaque',text:s.language==='zh'?'不透明':'Opaque'}],s.options.background_mode||'frosted');
 choose('microphone',[{value:'',text:s.language==='zh'?'系统默认':'System default'},...(s.microphones||[])],s.microphone||'');
 choose('asr_pause',['快速 · 0.35 秒','均衡 · 0.65 秒','稳妥 · 1.0 秒'],s.options.asr_pause);
 choose('incremental_context',['开启','关闭'],s.options.incremental_context);
 choose('deadline',['不限时','120','300','600','1800'],s.options.deadline);
 choose('max_output',['服务默认','4096','8192','16384','32768'],s.options.max_output);
 const active=s.jobs.filter(j=>!j.done),jobSignature=JSON.stringify(active);
 if($('active-jobs').dataset.signature!==jobSignature){$('active-jobs').dataset.signature=jobSignature;$('active-jobs').replaceChildren(...active.map(j=>{const b=document.createElement('button');b.textContent=(s.language==='zh'?'取消回答 #':'Cancel answer #')+j.id;b.onclick=()=>command('cancel_job',{id:j.id});return b}))}

 if(language!==s.language)setLanguage(s.language);
 choose('language',['en','zh'].map(x=>({value:x,text:x==='en'?'English':'中文'})),s.language);
 choose('provider',s.providers,s.provider);input('model',s.model);
 const captionConfig=s.caption_translation||{};
 choose('caption_provider',[{value:'',text:t('Same provider as answers')},...s.providers],s.options.caption_provider||'');
 input('caption_model',s.options.caption_model||'');
 $('caption_model').placeholder=t('Auto · prefer fast models');
 if(!pending.has('caption_provider')&&!pending.has('caption_model')){
  const models=[...new Set(captionConfig.models||[])].filter(Boolean),selected=s.options.caption_model||'';
  if(selected&&!models.includes(selected))models.push({value:selected,text:selected+(language==='zh'?'（自定义）':' (custom)')});
  const resolved=captionConfig.resolved_model;
  choose('caption-model-picker',[{value:'',text:t('Auto · prefer fast models')+(resolved?' · '+resolved:'')},...models],selected);
 }
 $('caption-model-status').textContent=captionConfig.status||'';
 document.querySelector('[data-action="refresh_caption_models"]').disabled=!!captionConfig.loading;
 $('model-status').textContent=s.model_status||'';
 if(!pending.has('model')&&!pending.has('provider')){
  const models=[...new Set(s.models||[])].filter(Boolean);
  if(s.model&&!models.includes(s.model))models.push({value:s.model,text:s.model+(language==='zh'?'（已选，目录未列出）':' (selected, not listed)')});
  const emptyLabel=s.cli?(language==='zh'?'平台默认模型':'Provider default'):(language==='zh'?'选择或输入模型 ID':'Choose or enter a model ID');
  choose('model-picker',[{value:'',text:emptyLabel},...models],s.model||'');
 }
 choose('effort',s.efforts,s.effort);
 choose('thinking_policy',['自动','开启','关闭'],s.options.thinking_policy);
 choose('answer_mode',['快速','推理',{value:'Coding',text:t('Coding')}],s.answer_mode);
 choose('source',['电脑','麦克风','电脑 + 麦克风'],s.options.source);
 choose('device',s.devices.map((name,index)=>({value:String(index),text:name})),String(s.device));
 choose('asr_engine',s.engines,s.options.asr_engine);
 const readingLanguages=[{value:'English',text:t('English')},{value:'中文',text:t('Chinese')},'中英双语'];
 for(const id of ['caption','live-caption'])choose(id,['原文',...readingLanguages],s.caption);
 for(const id of ['answer','live-answer'])choose(id,readingLanguages,s.answer);
 for(const id of ['question_mode','live-mode'])choose(id,['长问题','快速问答'],s.options.question_mode);
 for(const id of ['warm_context'])choose(id,['开启','关闭'],s.options[id]);
 choose('speculate',['仅疑问句','每段定稿','关闭'],s.options.speculate);
 $('key-field').hidden=s.cli;
 $('lm_base').closest('label').hidden=s.provider!=='LM Studio';
 $('key').placeholder=s.has_key?(language==='zh'?'已保存；留空保持原密钥':'Saved key; leave blank to keep it'):(language==='zh'?'输入 API 密钥':'Enter API key');
 for(const id of ['profile','documents','instructions'])input(id,s[id]);
 input('lm_base',s.options.lm_base);
 if(!pending.has('history'))$('history').checked=s.history;
 $('dot').classList.toggle('on',s.listening);$('live-label').textContent=t(s.listening?'Listening':'Ready');
 $('pause').textContent=t(s.listening?'Pause':'Start transcription');$('pause').dataset.icon=s.listening?'pause-fill':'play-fill';
 $('prepare').disabled=s.preparing;
 if(Date.now()>noticeUntil)$('status').textContent=t(s.status);
 $('model-badge').textContent=label(s.provider)+' / '+(s.model||'Default');
 $('job-count').textContent=s.jobs.filter(j=>!j.done).length+(language==='zh'?' 个回答进行中':' active answers');
 $('usage').textContent=language==='en'?s.usage.replaceAll('本次','session'):s.usage;
 attachments('settings-attachments',s.images);attachments('live-attachments',s.images);
 textStream('transcript',s.transcript);textStream('output',s.output);
 $('pin').classList.toggle('selected',s.native.topmost);

 window.contextEditor?.render(s);
 window.meetingUI?.render(s);
 renderContextImages(s.images);
 renderReadingLayout(s.options);
 renderPresets(s.options.listen_presets);
 renderHotkeys(s);
 window.workbench?.render(s);
 window.settingsTools?.render(s);
 if(s.navigation_request?.id&&s.navigation_request.id!==lastNavigation){lastNavigation=s.navigation_request.id;if(s.navigation_request.section==='shortcuts')goToShortcuts()}

}
// Live state arrives as changes only (see app/state_feed.py). The request waits
// on the app until something changes, so an idle page sends about one request
// a second and a busy one gets each update as soon as it is published.
const feed={boot:'',rev:-1,base:null,texts:{transcript:{v:null,text:''},output:{v:null,text:''}}};
function mergeFeed(data){
 if(data.boot!==feed.boot){feed.boot=data.boot;for(const key in feed.texts)feed.texts[key]={v:null,text:''}}
 feed.rev=data.rev;
 if(data.state)feed.base=data.state;
 for(const key of ['transcript','output']){
  const entry=data[key];if(!entry)continue;
  const now=feed.texts[key];
  now.text='text' in entry?entry.text:now.text.slice(0,entry.keep)+entry.add;
  now.v=entry.v;
 }
 return feed.base&&{...feed.base,transcript:feed.texts.transcript.text,output:feed.texts.output.text};
}
async function poll() {
 if(inFlight)return;
 inFlight=true;let delay=0;
 try {
  const have=feed.texts,query=`rev=${feed.rev}&boot=${feed.boot}&tv=${have.transcript.v??''}&ov=${have.output.v??''}&wait=1`;
  const response=await fetch('/state?'+query,{headers:{'X-Listener-Token':token}});
  if(!response.ok)throw new Error();
  const state=mergeFeed(await response.json());
  if(state)render(state);
  document.body.classList.remove('offline');
 }catch{document.body.classList.add('offline');$('status').textContent=t('Connection lost. Reconnecting…');delay=1000}
 finally{inFlight=false;setTimeout(poll,delay)}
}
poll();

// Tell the host where the clickable surfaces are, including menus. The window is
// not clipped (edges stay anti-aliased); everywhere else, clicks reach the desktop.
// Drag bars report their whole bar, so a thin handle is still easy to grab.
let lastShape='', shapeScheduled=false;
function isKeyboardEditor(el){
 return el instanceof HTMLElement && !el.disabled && !el.readOnly &&
  (el.isContentEditable || el.tagName==='TEXTAREA' || (el.tagName==='INPUT' && ['text','password','search','email','url','tel','number'].includes(el.type)));
}
document.addEventListener('focusin',scheduleShape);
document.addEventListener('focusout',scheduleShape);
function syncWindowShape(){
 shapeScheduled=false;
 placeWindowResizeTargets();
 if(!window.pywebview?.api?.shape)return;
 const rects=[...document.querySelectorAll('.capsule,.workspace-rail,#settings,#listen>.glass,#listen>.splitter,.side-grip,.window-resize-edge,.statusbar,.menu,.drawer,.resize-grip,.image-viewer')]
  .filter(el=>el.getClientRects().length && getComputedStyle(el).visibility!=='hidden')
  .map(el=>{const r=el.getBoundingClientRect();return [r.x,r.y,r.width,r.height,parseFloat(getComputedStyle(el).borderTopLeftRadius)||0]});
 // Showing a menu with an input must not activate the window; editing may.
 const editor=document.activeElement;
 const editing=!!document.querySelector('.image-viewer:not([hidden])') || (isKeyboardEditor(editor) && !editor.closest('details:not([open])') && editor.getClientRects().length && getComputedStyle(editor).visibility!=='hidden');
 const frost_rects=[...document.querySelectorAll('.capsule,#listen>.glass')]
  .filter(el=>el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden')
  .map(el=>{const r=el.getBoundingClientRect();return [r.x,r.y,r.width,r.height,parseFloat(getComputedStyle(el).borderTopLeftRadius)||0]});
 const layout={width:innerWidth,rects,view:document.body.dataset.view,frost:Number($('live-listen-frost')?.value||0),frost_rects,mouse_only:document.body.dataset.view==='listen'&&!editing,keyboard_editing:document.body.dataset.view==='listen'&&!!editing}, signature=JSON.stringify(layout);
 if(signature===lastShape)return;
 window.pywebview.api.shape(layout).then(applied=>{if(applied)lastShape=signature;else setTimeout(scheduleShape,250)}).catch(()=>{lastShape='';setTimeout(scheduleShape,250)});
}
function scheduleShape(){if(!shapeScheduled){shapeScheduled=true;requestAnimationFrame(syncWindowShape)}}
addEventListener('pywebviewready',scheduleShape);
addEventListener('resize',scheduleShape);
new ResizeObserver(scheduleShape).observe(document.querySelector('.shell'));
new MutationObserver(scheduleShape).observe(document.querySelector('.shell'),{attributes:true,subtree:true,attributeFilter:['hidden','class','open']});
scheduleShape();

// Match the reference's two independent columns rather than equal-height rows.
const settingsGrid=document.querySelector('.settings-grid');
for(const ids of [['models','audio','meeting-settings'],['context','preferences']]){
 const column=document.createElement('div');column.className='settings-column';
 ids.forEach(id=>column.appendChild($(id)));settingsGrid.appendChild(column);
}
const questionRow=$('question_mode').closest('label');
$('context').insertBefore(questionRow,$('context').querySelector('.inline'));
$('context').insertBefore($('instructions').closest('label'),$('context').querySelector('.inline'));
view('settings');

// Secondary editors stay available without dominating the overview.
const notes=document.createElement('details');notes.className='notes-editor';
const notesTitle=document.createElement('summary');notesTitle.dataset.i='Edit notes';notesTitle.textContent=t('Edit notes');notes.appendChild(notesTitle);
for(const id of ['profile','documents'])notes.appendChild($(id).closest('label'));
notes.appendChild(document.querySelector('[data-action="save_context"]'));
$('context').appendChild(notes);
const usageCard=document.createElement('section');usageCard.className='card usage-card';usageCard.id='usage-settings';
const usageTitle=document.createElement('h2');usageTitle.dataset.i='Observed usage';usageTitle.textContent=t('Observed usage');usageCard.appendChild(usageTitle);
usageCard.appendChild(document.querySelector('.usage'));
$('context').after(usageCard);
const preferencesDetails=document.createElement('details');
const preferencesTitle=document.createElement('summary');preferencesTitle.dataset.i='Session preferences';preferencesTitle.textContent=t('Session preferences');
preferencesDetails.appendChild(preferencesTitle);
const preferenceHeading=$('preferences').querySelector('h2');preferenceHeading.remove();
while($('preferences').firstChild)preferencesDetails.appendChild($('preferences').firstChild);
preferencesDetails.appendChild($('answer_mode').closest('label'));
$('preferences').appendChild(preferencesDetails);

// Reuse the original controls and handlers; advanced settings get their own space.
function settingsGroup(host,title,ids,open=false){
 const details=document.createElement('details');details.className='settings-options';details.open=open;
 const summary=document.createElement('summary');summary.dataset.i=title;summary.textContent=t(title);details.append(summary);
 for(const id of ids)details.append($(id).closest('label'));
 host.append(details);return details;
}
settingsGroup($('models'),'Model options',['model','effort','thinking_policy','lm_base']);
$('audio').append($('asr_pause').closest('label'),questionRow);
$('context').append($('history').closest('label'));
settingsGroup(preferencesDetails,'Window appearance',['background_mode'],true);
settingsGroup(preferencesDetails,'Generation options',['answer_mode','deadline','max_output','warm_context','speculate','incremental_context']);
const styleRow=document.createElement('label');styleRow.className='style-menu-row';
const styleLabel=document.createElement('span');styleLabel.dataset.i='Interface style';styleLabel.textContent=t('Interface style');
const liveStyle=document.createElement('select');liveStyle.id='live-ui-theme';liveStyle.setAttribute('aria-label','Interface style');
styleRow.append(styleLabel,liveStyle);$('layout-menu').prepend(styleRow);
liveStyle.onchange=()=>{applyTheme(liveStyle.value);save('ui_theme',liveStyle.value)};

const hotkeySection=document.createElement('section');hotkeySection.className='card';hotkeySection.id='shortcuts';
const hotkeyHeading=document.createElement('h2');hotkeyHeading.dataset.i='Global shortcuts';hotkeyHeading.textContent=t('Global shortcuts');hotkeySection.append(hotkeyHeading);
const hotkeyHelp=document.createElement('p');hotkeyHelp.dataset.i='Enter combinations such as Ctrl+Alt+P or Ctrl+Shift+F8. Changes apply after saving.';hotkeyHelp.textContent=t(hotkeyHelp.dataset.i);hotkeySection.append(hotkeyHelp);
const hotkeyLabels={hotkey:'Create an answer',topmost:'Always on top',transcription:'Start / pause transcription'};
for(const [action,title] of Object.entries(hotkeyLabels)){
 const label=document.createElement('label'),name=document.createElement('span'),input=document.createElement('input');
 name.dataset.i=title;name.textContent=t(title);input.id='hotkey-'+action;input.dataset.hotkey=action;input.autocomplete='off';input.spellcheck=false;
 input.addEventListener('input',()=>{hotkeyDraft=true});label.append(name,input);hotkeySection.append(label);
}
const hotkeyStatus=document.createElement('p');hotkeyStatus.id='hotkey-status';hotkeyStatus.setAttribute('role','status');hotkeySection.append(hotkeyStatus);
const hotkeyButtons=document.createElement('div');hotkeyButtons.className='inline';
for(const [id,title] of [['hotkeys-default','Restore defaults'],['hotkeys-save','Save and apply']]){
 const button=document.createElement('button');button.id=id;button.dataset.i=title;button.textContent=t(title);if(id==='hotkeys-save')button.className='primary';hotkeyButtons.append(button);
}
hotkeySection.append(hotkeyButtons);const hotkeyEditStatus=document.createElement('p');hotkeyEditStatus.id='hotkey-edit-status';hotkeyEditStatus.setAttribute('role','status');hotkeySection.append(hotkeyEditStatus);
$('preferences').after(hotkeySection);
const hotkeyNav=document.querySelector('#settings [data-action="hotkeys"]');hotkeyNav.dataset.section='shortcuts';hotkeyNav.classList.add('side');document.querySelector('#settings .side-bottom').before(hotkeyNav);
let hotkeyDraft=false,hotkeyBusy=false,lastNavigation='';
function goToShortcuts(){toggleMenu(null);view('settings');if(document.body.dataset.theme==='workbench'){window.workbench?.selectSection('shortcuts');return}requestAnimationFrame(()=>{$('shortcuts').scrollIntoView({behavior:'smooth',block:'start'});document.querySelectorAll('[data-section]').forEach(el=>el.classList.toggle('active',el.dataset.section==='shortcuts'))})}
function renderHotkeys(s){
 for(const input of document.querySelectorAll('[data-hotkey]')){if(!hotkeyDraft&&!hotkeyBusy)input.value=s.hotkeys?.[input.dataset.hotkey]||'';input.disabled=hotkeyBusy}
 $('hotkey-status').textContent=t(s.hotkey_status||'');
 $('hotkeys-save').disabled=$('hotkeys-default').disabled=hotkeyBusy;
}
$('hotkeys-default').onclick=()=>{for(const input of document.querySelectorAll('[data-hotkey]'))input.value=current?.hotkey_defaults?.[input.dataset.hotkey]||'';hotkeyDraft=true;$('hotkey-edit-status').textContent=language==='zh'?'默认值已载入，保存后生效。':'Defaults loaded. Save to apply them.'};
$('hotkeys-save').onclick=async()=>{
 const values=Object.fromEntries([...document.querySelectorAll('[data-hotkey]')].map(el=>[el.dataset.hotkey,el.value]));
 const id=crypto.randomUUID();hotkeyBusy=true;renderHotkeys(current);$('hotkey-edit-status').textContent=t('Working…');
 try{
  await command('save_hotkeys',{id,values});const deadline=Date.now()+8000;
  while(current?.hotkey_result?.id!==id){if(Date.now()>deadline)throw Error(language==='zh'?'尚未确认保存成功，请检查状态后重试。':'Save not confirmed. Check the status and try again.');await new Promise(resolve=>setTimeout(resolve,80))}
  if(!current.hotkey_result.ok)throw Error(current.hotkey_result.error);
  hotkeyDraft=false;$('hotkey-edit-status').textContent=language==='zh'?'设置已保存，注册结果见上方。':'Settings saved. Registration status is shown above.';
 }catch(error){$('hotkey-edit-status').textContent=error.message}
 finally{hotkeyBusy=false;renderHotkeys(current)}
};

// Bootstrap Icons are bundled locally; labels remain readable by screen readers.
const iconRules={
 // Scope to buttons: <body data-view> must never receive an icon or inline-flex.
 'button[data-view="settings"]':'gear','button[data-view="listen"]':'headphones',
 '[data-section="models"],#models h2':'cpu','[data-section="audio"],#audio h2':'mic',
 '[data-section="context"],#context h2':'folder2-open','[data-section="preferences"]':'sliders',
 '[data-section="meeting-settings"]':'chat-square-text','[data-section="usage-settings"]':'speedometer2',
 '[data-action="hotkeys"]':'keyboard','[data-action="speed"]':'speedometer2',
 '[data-action="prepare"]':'play-fill','[data-action="answer"]':'chat-square-text',
 '[data-action="capture"]':'camera','[data-action="import"]':'file-earmark-plus',
 '[data-action="analyze"]':'search','[data-action="refresh"]':'arrow-clockwise',
 '[data-action="usage"],.usage-card h2':'speedometer2','[data-action="save_context"]':'shield-check',
 '[data-action="screenshots"],#context-toggle':'folder2-open','[data-copy]':'clipboard',
 '[data-window="topmost"]':'pin-angle','#more':'three-dots','#layout-button':'sliders','#layout-reset':'arrow-clockwise',
 '[data-native="close"],#context-close':'x-lg','[data-native="minimize"]':'dash',
 '[data-native="maximize"]':'square','[data-action="cancel"]':'x-lg',
 '.answer-panel h2':'chat-square-text','.transcript-panel h2':'soundwave'
};
for(const [selector,icon] of Object.entries(iconRules))document.querySelectorAll(selector).forEach(el=>el.dataset.icon=icon);
document.querySelectorAll('[data-native],#context-close').forEach(el=>el.classList.add('icon-only'));
setLanguage(language);

$('preferences').querySelector('details').open=true;

const settingsScroller=document.querySelector('.settings-content');
let settingsScrollFrame=0;
settingsScroller.addEventListener('scroll',()=>{
 if(settingsScrollFrame||document.body.dataset.theme==='workbench')return;
 settingsScrollFrame=requestAnimationFrame(()=>{
  settingsScrollFrame=0;
  if(document.body.dataset.theme==='workbench')return;
  const top=settingsScroller.getBoundingClientRect().top+90;
  const links=[...document.querySelectorAll('button[data-section]')];
  const active=links.filter(link=>$(link.dataset.section).getBoundingClientRect().top<=top).at(-1)||links[0];
  links.forEach(link=>link.classList.toggle('active',link===active));
 });
},{passive:true});

// Drag the toolbar background and labels, never its interactive controls.
document.addEventListener('mousedown',event=>{
 if(event.button!==0 || !event.target.closest('.capsule,.listen-toolbar'))return;
 if(event.target.closest('button,input,select,textarea,a,summary,[contenteditable],.menu'))return;
 if(!window.pywebview?.api?.drag)return;
 event.preventDefault();
 window.pywebview.api.drag().catch(()=>{});
});

function applyTransparency(value){
 const amount=Math.max(1,Math.min(99,Number(value)||12));
 $('listen_transparency').value=amount;$('transparency-value').textContent=amount+'%';
 document.documentElement.style.setProperty('--listen-alpha',String(1-amount/100));
 updateHalo();
}
$('listen_transparency').addEventListener('input',()=>applyTransparency($('listen_transparency').value));
let contextImageSignature='',contextImageUrls=[];
async function renderContextImages(images){
 const signature=JSON.stringify(images);
 if(signature===contextImageSignature)return;
 contextImageSignature=signature;
 contextImageUrls.forEach(url=>URL.revokeObjectURL(url));contextImageUrls=[];
 const host=$('context-images');host.replaceChildren();
 if(!images.length){const empty=document.createElement('p');empty.textContent=language==='zh'?'暂无截图。添加后可在这里检查并移除。':'No screenshots. Add one to preview or remove it here.';host.append(empty);}
 for(const item of images){
  const figure=document.createElement('figure'),caption=document.createElement('figcaption');
  caption.textContent=item.title;figure.appendChild(caption);host.appendChild(figure);
  const remove=document.createElement('button');remove.textContent=language==='zh'?'移除截图':'Remove screenshot';remove.onclick=()=>command('remove_image',{id:item.id});figure.append(remove);
  try{
   const response=await fetch('/image/'+encodeURIComponent(item.id),{headers:{'X-Listener-Token':token}});
   if(!response.ok)throw Error('Image unavailable');
   const blob=await response.blob();if(contextImageSignature!==signature)return;
   const url=URL.createObjectURL(blob);contextImageUrls.push(url);
   const img=document.createElement('img');img.src=url;img.alt=item.title;img.tabIndex=0;img.setAttribute('role','button');
   img.ondblclick=()=>window.settingsTools?.openImage(item.id);
   img.onkeydown=e=>{if(e.key==='Enter')window.settingsTools?.openImage(item.id)};
   figure.prepend(img);
  }catch{caption.textContent=item.title+' — '+(language==='zh'?'预览不可用':'Preview unavailable')}
 }
}

// Frameless windows resize from an invisible target at the bottom-right corner.
// Screen coordinates stay stable while the window grows under the pointer.
const resizeGrip=$('resize-grip');
resizeGrip.dataset.resizeEdge='bottom-right';resizeGrip.classList.add('window-resize-edge');
for(const edge of ['left','right','top','bottom','top-left','top-right','bottom-left']){
 const target=document.createElement('div');target.className='window-resize-edge';target.dataset.resizeEdge=edge;
 target.setAttribute('aria-hidden','true');document.body.append(target);
}
function windowFrame(){
 const rects=[...document.querySelectorAll('.capsule,#settings,.workspace-rail,#listen>.glass:not(.drawer)')].filter(el=>el.getClientRects().length).map(el=>el.getBoundingClientRect());
 return {left:Math.min(...rects.map(r=>r.left)),right:Math.max(...rects.map(r=>r.right)),top:Math.min(...rects.map(r=>r.top)),bottom:Math.max(...rects.map(r=>r.bottom))};
}
function placeWindowResizeTargets(){
 const r=windowFrame();if(!Number.isFinite(r.left))return;
 for(const target of document.querySelectorAll('.window-resize-edge')){
  const edge=target.dataset.resizeEdge,corner=edge.includes('-'),size=edge==='bottom-right'?22:corner?12:7;
  const width=corner?size:edge==='top'||edge==='bottom'?Math.max(0,r.right-r.left-34):size;
  const height=corner?size:edge==='left'||edge==='right'?Math.max(0,r.bottom-r.top-24):size;
  let x=edge.includes('right')?r.right-width:edge==='top'||edge==='bottom'?r.left+12:r.left;
  // Classic panels have their own width grips; keep window edges in the outer gutter.
  if(document.body.dataset.theme==='classic'&&!corner){
   if(edge==='left')x=Math.max(0,r.left-width);
   if(edge==='right')x=Math.min(innerWidth-width,r.right);
  }
  const y=edge.includes('bottom')?r.bottom-height:edge==='left'||edge==='right'?r.top+12:r.top;
  Object.assign(target.style,{left:x+'px',top:y+'px',right:'auto',bottom:'auto',width:width+'px',height:height+'px'});
 }
}
let sizing=null;
function startWindowResize(event,edge,target=event.currentTarget){
 if(event.button!==0 || !window.pywebview?.api?.resize)return;
 const state=sizing={id:event.pointerId,edge,target,x:event.screenX,y:event.screenY,width:outerWidth,height:outerHeight,left:screenX,top:screenY,dx:0,dy:0,next:null,busy:false,finished:false,ready:!window.pywebview.api.bounds};
 target.setPointerCapture(event.pointerId);
 event.preventDefault();
 if(!state.ready)window.pywebview.api.bounds().then(rect=>{Object.assign(state,rect);state.ready=true;queueResize(state)}).catch(()=>{state.ready=true;queueResize(state)});
}
function queueResize(state){
 if(!state.ready)return;
 const left=state.edge.includes('left'),top=state.edge.includes('top');
 const width=Math.max(760,Math.min(10000,state.width+(left?-state.dx:state.edge.includes('right')?state.dx:0)));
 const height=Math.max(560,Math.min(10000,state.height+(top?-state.dy:state.edge.includes('bottom')?state.dy:0)));
 state.next=left||top?[width,height,state.left+(left?state.width-width:0),state.top+(top?state.height-height:0)]:[width,height];
 requestAnimationFrame(()=>flushResize(state));
}
function flushResize(state=sizing){
 if(!state||state.busy||!state.next)return;
 const next=state.next;state.next=null;state.busy=true;
 window.pywebview.api.resize(...next).catch(()=>{}).finally(()=>{state.busy=false;if(state.next)requestAnimationFrame(()=>flushResize(state));else if(state.finished&&sizing===state)sizing=null});
}
for(const target of document.querySelectorAll('.window-resize-edge'))target.addEventListener('pointerdown',event=>startWindowResize(event,target.dataset.resizeEdge));
addEventListener('pointermove',event=>{
 if(sizing?.id!==event.pointerId||sizing.finished)return;
 sizing.dx=event.screenX-sizing.x;sizing.dy=event.screenY-sizing.y;queueResize(sizing);
});
function stopResize(event){
 if(sizing?.id!==event.pointerId||sizing.finished)return;
 const state=sizing;state.finished=true;flushResize(state);
 if(state.target.hasPointerCapture(event.pointerId))state.target.releasePointerCapture(event.pointerId);
}
for(const name of ['pointerup','pointercancel','lostpointercapture'])addEventListener(name,stopResize);

// Reading text size for the live transcript and the AI answer.
const FONT_MIN=12,FONT_MAX=40;
function applyFont(key,value){
 const size=Math.max(FONT_MIN,Math.min(FONT_MAX,Number(value)||21));
 document.documentElement.style.setProperty(key==='transcript_font_size'?'--transcript-size':'--answer-size',size+'px');
 return size;
}
document.querySelectorAll('[data-font]').forEach(el=>el.onclick=()=>{
 const key=el.dataset.font, now=Number(pending.get(key)??current?.options?.[key])||21;
 const size=applyFont(key,now+Number(el.dataset.step));
 save(key,String(size));
});

// Drag bars between the toolbar, transcript and answer panels, plus side grips
// that set each panel's width on its own (each stays centered).
// Layout is "toolbar,transcript,toolbarWidth,transcriptWidth,answerWidth" in px;
// 0 keeps that dimension at its default size.
const listenPage=$('listen'),toolbar=document.querySelector('.listen-toolbar'),transcriptPanel=document.querySelector('.transcript-panel');
const answerPanel=document.querySelector('.answer-panel'),panels=[toolbar,transcriptPanel,answerPanel];
const ANSWER_MIN=150,TOOLBAR_RANGE=[56,200],TRANSCRIPT_MIN=100,WIDTH_MIN=560;
let layout=[0,0,0,0,0],splitting=null;
let midnightSplit=40;
function applyMidnightSplit(value){
 midnightSplit=Math.max(25,Math.min(65,Number(value)||40));
 listenPage.style.setProperty('--midnight-columns',`${midnightSplit}fr 12px ${100-midnightSplit}fr`);
 placeSideGrips();
}
const sideGrips=panels.flatMap((panel,index)=>['left','right'].map(edge=>{
 const grip=document.createElement('div');
 grip.className='side-grip';grip.dataset.edge=edge;grip.dataset.panel=String(index);grip.tabIndex=0;
 grip.setAttribute('role','separator');grip.setAttribute('aria-orientation','vertical');grip.setAttribute('aria-label','Resize width');
 grip.title=t('Drag to resize · double-click to reset');
 document.body.appendChild(grip);return grip;
}));
function placeSideGrips(){
 const visible=document.body.dataset.view==='listen'&&!listenPage.hidden;
 for(const grip of sideGrips){
  grip.hidden=!visible;if(!visible)continue;
  const r=panels[grip.dataset.panel].getBoundingClientRect();
  grip.style.top=r.top+'px';grip.style.height=r.height+'px';
  grip.style.left=(grip.dataset.edge==='left'?r.left:r.right-grip.offsetWidth)+'px';
 }
 scheduleShape();
}
function rowNeed(el){
 // Width a flex row needs to show every visible child at its current size.
 const cs=getComputedStyle(el),kids=[...el.children].filter(k=>k.getClientRects().length);
 const inner=kids.reduce((sum,k)=>sum+(k.classList.contains('inline')?rowNeed(k):k.getBoundingClientRect().width),0);
 return inner+(parseFloat(cs.columnGap)||0)*Math.max(0,kids.length-1)+parseFloat(cs.paddingLeft)+parseFloat(cs.paddingRight)
  +parseFloat(cs.borderLeftWidth)+parseFloat(cs.borderRightWidth);
}
function toolbarNeed(){return rowNeed(toolbar)}
function applyLayout(...values){
 const v=[...values,0,0,0,0,0].slice(0,5).map(x=>Math.round(Number(x)||0));
 const maxWidth=listenPage.clientWidth;
 panels.forEach((panel,i)=>{
  if(midnightColumns()&&i>0){panel.style.width='';panel.style.alignSelf='stretch';return}
  const w=v[2+i];
  const available=midnightColumns()&&i>0?(maxWidth-12)*(i===1?midnightSplit:100-midnightSplit)/100:maxWidth;
  const minimum=midnightColumns()&&i>0?240:WIDTH_MIN;
  if(w){v[2+i]=Math.round(Math.min(available,Math.max(minimum,w)));panel.style.width=v[2+i]+'px';panel.style.alignSelf=midnightColumns()?'stretch':'center'}
  else{panel.style.width='';panel.style.alignSelf=''}
 });
 // The toolbar's buttons collapse to icons as it narrows, but past that point
 // they would overlap. Grow it back to what its buttons need at this width.
 if(v[2]){const need=Math.ceil(toolbarNeed());if(need>v[2]){v[2]=Math.min(maxWidth,need);toolbar.style.width=v[2]+'px'}}
 if(v[0]){v[0]=Math.max(TOOLBAR_RANGE[0],Math.min(TOOLBAR_RANGE[1],v[0]));toolbar.style.minHeight=toolbar.style.height=v[0]+'px'}
 else toolbar.style.minHeight=toolbar.style.height='';
 if(v[1]&&!midnightColumns()){
  const splitters=[...listenPage.querySelectorAll(':scope>.splitter')].reduce((sum,el)=>sum+el.offsetHeight,0);
  const room=listenPage.clientHeight-toolbar.offsetHeight-splitters-ANSWER_MIN;
  v[1]=Math.max(TRANSCRIPT_MIN,Math.min(Math.max(TRANSCRIPT_MIN,room),v[1]));transcriptPanel.style.flex='0 0 '+v[1]+'px';
 }else transcriptPanel.style.flex='';
 const divider=document.querySelector('.splitter[data-split="transcript"]');
 divider.setAttribute('aria-orientation',midnightColumns()?'vertical':'horizontal');
 layout=v;placeSideGrips();
 return layout;
}
function saveLayout(){save('listen_layout',layout.some(Boolean)?layout.join(','):'')}
function startSplit(el,event){
 if(event.button!==0)return;
 if(midnightColumns()&&el.dataset.panel!==undefined&&Number(el.dataset.panel)>0){
  const outside=el.dataset.panel==='1'&&el.dataset.edge==='left'||el.dataset.panel==='2'&&el.dataset.edge==='right';
  if(outside){startWindowResize(event,el.dataset.edge,el);return}
 }
 const panel=el.dataset.panel;
 splitting={id:event.pointerId,x:event.clientX,y:event.clientY,
  split:midnightSplit,total:listenPage.clientWidth-12,
  heights:[toolbar.offsetHeight,transcriptPanel.offsetHeight],width:panel===undefined?0:panels[panel].offsetWidth};
 el.setPointerCapture(event.pointerId);el.classList.add('dragging');event.preventDefault();
}
function moveSplit(el,dx,dy,start){
 if(midnightColumns()&&(el.dataset.split==='transcript'||Number(el.dataset.panel)>0)){
  applyMidnightSplit(start.split+dx/start.total*100);return;
 }
 const next=[...layout];
 if(el.dataset.edge){
  // A centered panel grows on both sides, so one edge moves twice as far.
  next[2+Number(el.dataset.panel)]=start.width+(el.dataset.edge==='right'?dx:-dx)*2;
 }else if(el.dataset.split==='toolbar'){next[0]=start.heights[0]+dy;next[1]=start.heights[1]-dy}
 else next[1]=start.heights[1]+dy;
 applyLayout(...next);
}
function stopSplit(el,event){
 if(splitting?.id!==event.pointerId)return;
 splitting=null;el.classList.remove('dragging');
 if(el.hasPointerCapture(event.pointerId))el.releasePointerCapture(event.pointerId);
 if(midnightColumns()&&(el.dataset.split==='transcript'||Number(el.dataset.panel)>0))save('midnight_split',String(Math.round(midnightSplit)));
 else saveLayout();
}
const now=el=>({split:midnightSplit,total:listenPage.clientWidth-12,heights:[toolbar.offsetHeight,transcriptPanel.offsetHeight],width:el.dataset.panel===undefined?0:panels[el.dataset.panel].offsetWidth});
for(const el of [...document.querySelectorAll('.splitter'),...sideGrips]){
 el.addEventListener('pointerdown',event=>startSplit(el,event));
 el.addEventListener('pointermove',event=>{
  if(splitting?.id!==event.pointerId)return;
  moveSplit(el,event.clientX-splitting.x,event.clientY-splitting.y,splitting);
 });
 for(const name of ['pointerup','pointercancel','lostpointercapture'])el.addEventListener(name,event=>stopSplit(el,event));
 el.addEventListener('keydown',event=>{
  if(midnightColumns()&&(el.dataset.split==='transcript'||Number(el.dataset.panel)>0)){
   const step={ArrowLeft:-1,ArrowRight:1}[event.key];if(!step)return;
   event.preventDefault();applyMidnightSplit(midnightSplit+step);save('midnight_split',String(Math.round(midnightSplit)));return;
  }
  const step=(el.dataset.edge?{ArrowLeft:-10,ArrowRight:10}:{ArrowUp:-10,ArrowDown:10})[event.key];
  if(!step)return;
  event.preventDefault();
  if(el.dataset.edge)moveSplit(el,el.dataset.edge==='right'?step/2:-step/2,0,now(el));
  else moveSplit(el,0,step,now(el));
  saveLayout();
 });
 // Double-click a side grip to reset that panel's width; a bar resets the heights.
 el.addEventListener('dblclick',()=>{
  if(midnightColumns()&&(el.dataset.split==='transcript'||Number(el.dataset.panel)>0)){applyMidnightSplit(40);save('midnight_split','40');return}
  const next=[...layout];
  if(el.dataset.edge)next[2+Number(el.dataset.panel)]=0;else next[0]=next[1]=0;
  applyLayout(...next);saveLayout();
 });
}
addEventListener('resize',()=>applyLayout(...layout));
new ResizeObserver(placeSideGrips).observe(listenPage);
new MutationObserver(placeSideGrips).observe(document.body,{attributes:true,attributeFilter:['data-view']});
function renderReadingLayout(options){
 for(const key of ['transcript_font_size','answer_font_size'])if(!pending.has(key))applyFont(key,options[key]);
 if(!splitting&&!pending.has('midnight_split')&&Number(options.midnight_split||40)!==midnightSplit)applyMidnightSplit(options.midnight_split);
 if(splitting||pending.has('listen_layout')||document.body.dataset.view!=='listen')return;
 let saved=String(options.listen_layout||'').split(',').map(Number);
 // Older saves used one shared width for all three panels.
 if(saved.length===3)saved=[saved[0],saved[1],saved[2],saved[2],saved[2]];
 while(saved.length<5)saved.push(0);
 if(saved.join(',')!==layout.join(','))applyLayout(...saved);
}

// Listening text and panel colors. The outline behind text uses the opposite
// brightness of the text and grows as panels become more see-through.
const COLOR_DEFAULTS={listen_text_color:'#ffffff',listen_panel_color:'#213953'};
const hexRgb=hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
function applyColor(id,value){
 let hex=/^#[0-9a-f]{6}$/i.test(value||'')?value.toLowerCase():COLOR_DEFAULTS[id];
 const follow=(pending.get('listen_theme_colors')??current?.options?.listen_theme_colors??'1')==='1';
 if(follow){
  const light=document.body.dataset.theme==='workbench'&&document.body.dataset.palette!=='gold';
  hex=id==='listen_text_color'?(light?'#202c3d':document.body.dataset.theme==='classic'?'#ffffff':'#f0e9da'):(light?'#ffffff':document.body.dataset.theme==='classic'?'#213953':'#151619');
 }
 $(id).value=hex;
 const root=document.documentElement.style;
 if(id==='listen_text_color')root.setProperty('--listen-text',hex);
 else root.setProperty('--listen-rgb',hexRgb(hex).join(','));
 updateHalo();
}
function updateHalo(){
 const [r,g,b]=hexRgb($('listen_text_color').value||'#ffffff');
 const light=(0.2126*r+0.7152*g+0.0722*b)/255>0.5;
 const see=1-(Number(getComputedStyle(document.documentElement).getPropertyValue('--listen-alpha'))||.88);
 const strength=(0.25+0.65*Math.min(1,see*1.3)).toFixed(2);
 const halo=light?`rgba(0,0,0,${strength})`:`rgba(255,255,255,${strength})`;
 document.documentElement.style.setProperty('--listen-halo',halo);
 // The outline is optional: off by default, switched in the More menu.
 document.documentElement.style.setProperty('--listen-shadow',document.body.dataset.textOutline==='1'?`0 0 1px ${halo},0 0 2px ${halo},0 0 7px ${halo}`:'none');
}
// Bold text and text outline switches.
const TOGGLES=['listen_text_bold','listen_text_outline'];
function applyToggle(id,value){
 const on=value==='1';
 document.body.dataset[id==='listen_text_bold'?'textBold':'textOutline']=on?'1':'0';
 const button=document.querySelector(`[data-toggle="${id}"]`);
 button.setAttribute('role','switch');button.setAttribute('aria-checked',String(on));button.dataset.state=t(on?'On':'Off');
 if(id==='listen_text_outline')updateHalo();
}
document.querySelectorAll('[data-toggle]').forEach(el=>el.onclick=()=>{
 const id=el.dataset.toggle,value=document.body.dataset[id==='listen_text_bold'?'textBold':'textOutline']==='1'?'0':'1';
 applyToggle(id,value);save(id,value);
});
for(const id of ['listen_text_color','listen_panel_color'])$(id).addEventListener('input',()=>{pending.set('listen_theme_colors','0');save('listen_theme_colors','0');applyColor(id,$(id).value)});
// Double-click a color swatch to restore its default.
for(const id of ['listen_text_color','listen_panel_color'])$(id).closest('label').addEventListener('dblclick',event=>{
 event.preventDefault();applyColor(id,COLOR_DEFAULTS[id]);save(id,COLOR_DEFAULTS[id]);
});

// Layout presets. A preset holds every Listen-page look setting; keys it
// leaves out fall back to the defaults, so "Default" doubles as a full reset.
const LAYOUT_DEFAULTS={listen_transparency:'12',transcript_font_size:'21',answer_font_size:'21',listen_layout:'',
 listen_text_color:'#ffffff',listen_panel_color:'#213953',listen_text_bold:'0',listen_text_outline:'0'};
const BUILTIN_PRESETS=[
 {name:'Default',values:{}},
 {name:'Compact',values:{listen_transparency:'25',transcript_font_size:'16',answer_font_size:'16',listen_layout:'56,140,0,0,0'}},
 {name:'Large text',values:{listen_transparency:'8',transcript_font_size:'28',answer_font_size:'30',listen_text_bold:'1'}}
];
const MAX_PRESETS=5;
var presetSignature='';
function userPresets(raw=current?.options?.listen_presets){
 if(pending.has('listen_presets'))raw=pending.get('listen_presets');
 try{const list=JSON.parse(raw||'[]');return Array.isArray(list)?list:[]}catch{return []}
}
function currentLook(){
 const size=name=>String(parseInt(getComputedStyle(document.documentElement).getPropertyValue(name))||21);
 return {listen_transparency:String($('listen_transparency').value),transcript_font_size:size('--transcript-size'),
  answer_font_size:size('--answer-size'),listen_layout:layout.some(Boolean)?layout.join(','):'',
  listen_text_color:$('listen_text_color').value,listen_panel_color:$('listen_panel_color').value,
  listen_text_bold:document.body.dataset.textBold==='1'?'1':'0',listen_text_outline:document.body.dataset.textOutline==='1'?'1':'0'};
}
async function applyLook(values){
 const look={...LAYOUT_DEFAULTS,...values};
 // Explicit colors in existing presets remain authoritative; Default follows the theme.
 look.listen_theme_colors=values.listen_panel_color||values.listen_text_color?'0':'1';
 pending.set('listen_theme_colors',look.listen_theme_colors);
 applyTransparency(look.listen_transparency);
 applyColor('listen_text_color',look.listen_text_color);applyColor('listen_panel_color',look.listen_panel_color);
 for(const id of TOGGLES)applyToggle(id,look[id]);
 for(const key of ['transcript_font_size','answer_font_size'])applyFont(key,look[key]);
 const sizes=String(look.listen_layout||'').split(',').map(Number);
 applyLayout(...(sizes.length===3?[sizes[0],sizes[1],sizes[2],sizes[2],sizes[2]]:sizes));
 for(const [key,value] of Object.entries(look))pending.set(key,value);
 try{await command('settings',{values:look})}
 finally{setTimeout(()=>Object.keys(look).forEach(key=>pending.delete(key)),500)}
}
function savePresets(list){return save('listen_presets',list.length?JSON.stringify(list):'')}
function renderPresets(raw){
 const list=userPresets(raw),signature=JSON.stringify([list,language]);
 if(signature===presetSignature)return;
 presetSignature=signature;
 const rows=[...BUILTIN_PRESETS.map(p=>({...p,builtin:true})),...list].map(preset=>{
  const row=document.createElement('div');row.className='preset-row';
  const use=document.createElement('button');use.className='preset-apply';use.type='button';
  use.textContent=preset.builtin?t(preset.name):preset.name;use.dataset.preset=preset.name;
  use.onclick=()=>{applyLook(preset.values);toggleMenu(null)};
  row.appendChild(use);
  if(!preset.builtin){
   const remove=document.createElement('button');remove.className='preset-delete';remove.type='button';
   remove.textContent='×';remove.title=t('Delete preset')+' · '+preset.name;remove.setAttribute('aria-label',remove.title);
   remove.onclick=()=>{savePresets(userPresets().filter(p=>p.name!==preset.name));presetSignature='';renderPresets()};
   row.appendChild(remove);
  }
  return row;
 });
 $('preset-list').replaceChildren(...rows);
}
$('preset-form').addEventListener('submit',async event=>{
 event.preventDefault();
 const name=$('preset-name').value.trim();
 if(!name)return $('preset-name').focus();
 const zh=language==='zh',key=name.toLocaleLowerCase();
 if(BUILTIN_PRESETS.some(p=>[p.name,t(p.name)].some(n=>n.toLocaleLowerCase()===key))){
  notice(zh?'这个名称已被内置预设使用。':'That name is used by a built-in preset.');return;
 }
 const list=userPresets(),others=list.filter(p=>p.name.toLocaleLowerCase()!==key);
 if(others.length>=MAX_PRESETS){
  notice(zh?`最多保存 ${MAX_PRESETS} 个预设，请先删除一个。`:`You can save up to ${MAX_PRESETS} presets. Delete one first.`);return;
 }
 // Saving under an existing name replaces that preset.
 const next=list.some(p=>p.name.toLocaleLowerCase()===key)
  ?list.map(p=>p.name.toLocaleLowerCase()===key?{name,values:currentLook()}:p)
  :[...list,{name,values:currentLook()}];
 $('preset-name').value='';
 await savePresets(next);presetSignature='';renderPresets();
 notice(zh?`已保存布局预设“${name}”。`:`Saved layout preset “${name}”.`);
});
$('layout-reset').onclick=()=>{applyLook({});if(darkWorkspace()){applyMidnightSplit(40);save('midnight_split','40')}toggleMenu(null)};
