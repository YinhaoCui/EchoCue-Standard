/* Dual-track presentation. Reparent live controls; keep their handlers and drafts. */
(() => {
 const enabled=()=>document.body.dataset.theme==='workbench';
 Object.assign(translations,{
  'Workbench · Black Gold':'双轨工作台 · 黑金','Listening frost':'监听页磨砂度','Follow theme colors':'监听配色跟随主题',
  'Dual-track Workbench':'双轨工作台','Models & connections':'模型与连接','Interface settings':'界面设置','Usage & diagnostics':'用量与检测',
  'Style & language':'风格与语言','Desktop effects':'桌面效果','Text & colors':'文字与配色',
  'Choose the application palette and display language.':'选择应用配色和显示语言。',
  'Adjust desktop blur and transparency independently. Text stays sharp.':'独立调整桌面磨砂和透明度，文字保持清晰。',
  'Follow the theme, or choose your own reading colors.':'使用主题配色，或单独调整阅读颜色与文字样式。',
  'Start with a template, then edit the prompt for this session.':'选择模板后可继续编辑提示词，应用后用于本次会话。',
  'Context & scenes':'上下文与场景','Template library':'模板库',
  'All answers':'全部回答','Back to live':'回到实时','Return to listening':'返回监听',
  'Choose a task above. Listening continues independently.':'在上方选择任务，实时转录会继续进行。',
  'Settings apply as you change them. Context drafts and shortcuts have their own Apply button.':'普通设置修改后即时保存；上下文草稿和快捷键需单独应用。',
  'No answer yet. Request an answer when you are ready.':'暂无回答，准备好后点击“回答”。',
  'No transcript yet. Start transcription to listen.':'暂无转录，点击“开始转录”进行监听。'
 });
 const make=(tag,cls,text)=>{const el=document.createElement(tag);el.className=cls||'';if(text){el.dataset.i=text;el.textContent=t(text)}return el};
 const appearanceControls=[];
 for(const [container,prefix] of [[document.querySelector('.appearance-controls'),'settings'],[$('layout-menu'),'live']]){
  const group=make('div','frost-controls'),label=make('label'),title=make('span','','Listening frost');
  const slider=document.createElement('input');slider.type='range';slider.min='0';slider.max='100';slider.step='1';slider.id=prefix+'-listen-frost';
  title.id=slider.id+'-label';slider.setAttribute('aria-labelledby',title.id);
  const value=make('output');value.htmlFor=slider.id;
  label.append(title,slider,value);
  const colors=make('label','theme-colors'),check=document.createElement('input');check.type='checkbox';check.id=prefix+'-theme-colors';colors.append(check,make('span','','Follow theme colors'));
  group.append(label,colors);container.append(group);appearanceControls.push({slider,value,check});
  slider.oninput=()=>{applyFrost(slider.value);pending.set('listen_frost',slider.value)};
  slider.onchange=()=>save('listen_frost',slider.value);
  check.onchange=()=>{pending.set('listen_theme_colors',check.checked?'1':'0');save('listen_theme_colors',check.checked?'1':'0');for(const id of ['listen_text_color','listen_panel_color'])applyColor(id,current?.options?.[id]);syncAppearance(current)};
 }
 function applyFrost(raw){
  const amount=Math.max(0,Math.min(100,Number(raw)||0));
  // Desktop blur is composed below the WebView by Windows, never simulated in CSS.
  for(const {slider,value} of appearanceControls){slider.value=amount;value.value=amount+'%'}
  scheduleShape();
 }
 function syncAppearance(s){
  applyFrost(pending.get('listen_frost')??s?.options?.listen_frost??35);
  for(const {check} of appearanceControls)check.checked=(pending.get('listen_theme_colors')??s?.options?.listen_theme_colors??'1')==='1';
 }
 const appearance=make('section','card');appearance.id='interface-settings';
 appearance.append(make('h2','','Interface settings'),document.querySelector('.appearance-controls'));
 $('usage-settings').before(appearance);
 const languageLabel=make('label');$('language').before(languageLabel);languageLabel.append(make('span','','Interface language'),$('language'));
 const appearanceNav=make('button','side','Interface settings');appearanceNav.dataset.section=appearance.id;
 appearanceNav.dataset.icon='palette';
 document.querySelector('[data-section="usage-settings"]').before(appearanceNav);
 appearanceNav.onclick=()=>{if(!enabled())appearance.scrollIntoView({behavior:'smooth'})};
 const sections={models:'Models & connections',audio:'Audio & transcription','meeting-settings':'Meeting assistance',context:'Context & scenes',preferences:'Session preferences',shortcuts:'Global shortcuts','interface-settings':'Interface settings','usage-settings':'Usage & diagnostics'};
 let section='models',selected='all',tabsSignature='',presetSignature='',contextDocked=false;
 const homes=new Map();
 function move(el,parent){if(!homes.has(el)){const marker=document.createComment('control home');el.before(marker);homes.set(el,marker)}parent.append(el)}
 function restore(el){const marker=homes.get(el);if(marker)marker.after(el)}
 const listeningControls=make('div','interface-listening-controls');appearance.append(listeningControls);
 const appearanceItems=[document.querySelector('.transparency-control'),document.querySelector('#layout-menu .color-row'),...document.querySelectorAll('#layout-menu [data-toggle]')];
 const appearanceGroup=(title,description)=>{const group=make('section','interface-group'),heading=make('div','interface-group-heading');heading.append(make('h3','',title),make('p','',description));group.append(heading);appearance.append(group);return group};
 const styleGroup=appearanceGroup('Style & language','Choose the application palette and display language.');
 styleGroup.append(document.querySelector('.appearance-controls'));
 const effectsGroup=appearanceGroup('Desktop effects','Adjust desktop blur and transparency independently. Text stays sharp.');
 const effectsFields=make('div','interface-effects');effectsGroup.append(effectsFields);
 const frostSettings=$('settings-listen-frost').closest('.frost-controls');
 effectsFields.append($('settings-listen-frost').closest('label'));
 const colorGroup=appearanceGroup('Text & colors','Follow the theme, or choose your own reading colors.');
 colorGroup.classList.add('interface-colors');
 colorGroup.append($('settings-theme-colors').closest('label'),listeningControls);frostSettings.remove();
 const contextMain=make('div','workbench-context-main'),shelf=make('div','workbench-context-shelf');
 const templateBar=make('div','workbench-template-bar');
 templateBar.append(make('h3','','Template library'),make('p','','Start with a template, then edit the prompt for this session.'));
 $('context').append(templateBar,contextMain,shelf);
 const presets=make('div','workbench-presets');templateBar.append(presets);
 const library=$('prompt-template').closest('.prompt-library');
 const scenes=$('scene-picker').closest('.context-section');
 const memory=$('context-history').closest('.context-memory');
 const disclosureStates=new Map();
 const returnButton=make('button','quiet','Return to listening');returnButton.onclick=()=>view('listen');
 $('prepare').before(returnButton);
 const hint=make('p','workbench-save-note','Settings apply as you change them. Context drafts and shortcuts have their own Apply button.');
 $('settings-footer').before(hint);
 const contextApplyBar=document.querySelector('.context-settings-save');
 const captionHome=document.createComment('caption settings home');$('caption-model-settings').before(captionHome);
 const workbenchTabs=make('div','workbench-tabs');workbenchTabs.setAttribute('role','tablist');workbenchTabs.setAttribute('aria-label','Answer tasks');
 const output=make('div','reading answer');output.id='workbench-output';output.tabIndex=0;output.setAttribute('role','tabpanel');
 const taskInfo=make('div','workbench-task-info');
 const cancel=make('button','quiet','Cancel answers');cancel.onclick=()=>command('cancel_job',{id:Number(selected)}).catch(()=>{});
 const taskLabel=make('span');taskInfo.append(taskLabel,cancel);
 document.querySelector('.answer-panel .reading-heading').after(workbenchTabs,taskInfo);
 $('output').after(output);
 const liveButton=make('button','workbench-back-live','Back to live');
 liveButton.onclick=()=>{$('transcript').scrollTop=$('transcript').scrollHeight;liveButton.hidden=true};
 $('transcript').after(liveButton);
 const updateFollow=()=>{liveButton.hidden=$('transcript').scrollHeight-$('transcript').scrollTop-$('transcript').clientHeight<60};
 $('transcript').addEventListener('scroll',updateFollow,{passive:true});

 function selectSection(id){
  if(!sections[id])return;section=id;
  document.querySelectorAll('[data-section]').forEach(button=>{
   const active=button.dataset.section===id;button.classList.toggle('active',active);
   if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
  });
  for(const key of Object.keys(sections))$(key).classList.toggle('workbench-section-active',key===id);
  if(enabled()){
   const heading=document.querySelector('.intro h1');heading.dataset.i=sections[id];heading.textContent=t(sections[id]);
   document.querySelector('.settings-content').scrollTop=0;
   if(id==='preferences')document.querySelector('#preferences details').open=true;
   if(id==='context')move(contextApplyBar,$('settings-footer'));else contextMain.append(contextApplyBar);
  }
  scheduleShape();
 }
 // Capture only the new theme's navigation, leaving legacy themes untouched.
 document.addEventListener('click',event=>{
  if(!enabled())return;
  const nav=event.target.closest('[data-section],button[data-action="hotkeys"]');
  if(!nav)return;
  event.preventDefault();event.stopImmediatePropagation();
  if(nav.dataset.action==='hotkeys'){toggleMenu(null);view('settings')}
  selectSection(nav.dataset.section||'shortcuts');
 },true);
 function syncContext(){
  for(const el of appearanceItems){if(document.body.dataset.view==='settings')move(el,el.classList.contains('transparency-control')?effectsFields:listeningControls);else restore(el)}
  const dock=enabled()&&document.body.dataset.view==='settings';
  if(dock!==contextDocked){
   contextDocked=dock;
   if(dock){for(const el of [library,scenes])disclosureStates.set(el,el.open);move(library,shelf);move(scenes,shelf);move(memory,contextMain);library.open=true;scenes.open=true}
   else{restore(library);restore(scenes);restore(memory);for(const [el,open] of disclosureStates)el.open=open;disclosureStates.clear()}
  }
  scheduleShape();
 }
 function themeChanged(){
  if(enabled()){
   for(const child of [...$('context').children])if(child!==contextMain&&child!==shelf&&child!==templateBar)move(child,contextMain);
   document.querySelector('#context .notes-editor').open=true;
   $('models').append($('caption-model-settings'));
   for(const [key,text] of Object.entries(sections)){
    const nav=document.querySelector(`[data-section="${key}"]`);if(nav){nav.dataset.originalLabel??=nav.dataset.i;nav.dataset.i=text;nav.textContent=t(text)}
   }
  }else{
   restore(contextApplyBar);
   for(const child of [...contextMain.children])restore(child);
   captionHome.after($('caption-model-settings'));
   document.querySelectorAll('[data-original-label]').forEach(el=>{el.dataset.i=el.dataset.originalLabel;el.textContent=t(el.dataset.i)});
   const heading=document.querySelector('.intro h1');heading.dataset.i='Set up your session';heading.textContent=t(heading.dataset.i);
  }
  syncContext();selectSection(section);tabsSignature='';
  if(current)render(current);
 }
 function selectTask(id){
  selected=id;tabsSignature='';output._mdSource=null;output.scrollTop=0;
  if(id!=='all'&&[...$('meeting-answer').options].some(o=>o.value===id))$('meeting-answer').value=id;
  render(current);
 }
 workbenchTabs.addEventListener('keydown',event=>{
  const steps={ArrowLeft:-1,ArrowRight:1,Home:0,End:0};if(!(event.key in steps))return;
  const buttons=[...workbenchTabs.children],index=buttons.indexOf(document.activeElement);if(index<0)return;
  event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+steps[event.key]+buttons.length)%buttons.length;
  buttons[next].click();buttons[next].focus();
 });
 function render(s){
  syncAppearance(s);
  if(!enabled()||!s)return;
  const jobs=s.jobs||[];
  if(selected!=='all'&&!jobs.some(j=>String(j.id)===selected)){selected='all';tabsSignature=''}
  const signature=JSON.stringify([language,selected,jobs.map(j=>[j.id,j.done,j.completed,j.state])]);
  if(signature!==tabsSignature){
   tabsSignature=signature;
   const items=[['all',t('All answers')],...jobs.map(j=>[String(j.id),(language==='zh'?'回答 ':'Answer ')+j.id+' · '+(j.done?(j.completed?(language==='zh'?'完成':'Done'):(language==='zh'?'已结束':'Ended')):(language==='zh'?'进行中':'Running'))])];
   workbenchTabs.replaceChildren(...items.map(([id,text])=>{
    const button=make('button');button.textContent=text;button.id='answer-tab-'+id;button.setAttribute('role','tab');button.setAttribute('aria-selected',String(id===selected));button.setAttribute('aria-controls',output.id);button.tabIndex=id===selected?0:-1;button.onclick=()=>selectTask(id);return button;
   }));
   output.setAttribute('aria-labelledby','answer-tab-'+selected);
  }
  const job=jobs.find(j=>String(j.id)===selected);
  taskLabel.textContent=job?[job.provider,job.model,job.state].filter(Boolean).join(' · '):t('Choose a task above. Listening continues independently.');
  cancel.hidden=!job||job.done;
  cancel.textContent=language==='zh'?'取消此任务':'Cancel this task';
  const text=job?.span?s.output.slice(job.span[0],job.span[1]):s.output;
  textStream(output.id,text||'');
  output.dataset.empty=t('No answer yet. Request an answer when you are ready.');
  $('transcript').dataset.empty=t('No transcript yet. Start transcription to listen.');
  const signaturePresets=JSON.stringify([s.prompt_presets,language]);
  if(signaturePresets!==presetSignature){
   presetSignature=signaturePresets;
   presets.replaceChildren(...(s.prompt_presets||[]).map(p=>{
    const button=make('button');button.textContent=language==='zh'?p.name_zh:p.name;
    button.onclick=()=>{
     const select=$('settings-builtin-prompt');select.value=p.id;select.dispatchEvent(new Event('change',{bubbles:true}));
     $('settings-builtin-load').click();$('instructions').focus();
    };return button;
   }));
  }
  if(s.navigation_request?.section==='shortcuts'&&document.body.dataset.view==='settings'&&section!=='shortcuts'&&s.navigation_request.id!==render.navigation){render.navigation=s.navigation_request.id;selectSection('shortcuts')}
  updateFollow();
 }
 window.workbench={render,themeChanged,syncContext,selectSection};
 themeChanged();setLanguage(language);
})();
