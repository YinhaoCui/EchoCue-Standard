/* Settings and previews stay in the existing desktop window. */
(() => {
 const make=(tag,id,text)=>{const el=document.createElement(tag);if(id)el.id=id;if(text){el.dataset.i=text;el.textContent=t(text)}return el};
 Object.assign(translations,{
  'Usage & diagnostics':'用量与检测','Run API check':'开始检测 API','Start benchmark':'开始测速','Cancel benchmark':'取消测速',
  'Refresh catalog':'刷新模型目录','Benchmark mode':'测速模式','Gemini fast reply':'Gemini 快速回复','Results':'结果',
  'Benchmark uses a synthetic coding question, without your transcript or personal context.':'测速使用固定编程题，不发送转录或个人上下文。',
  'API checks read model catalogs. They do not confirm generation permission or remaining quota.':'API 检测读取模型目录，不代表生成权限或剩余额度。',
  'Refresh Codex quota':'刷新 Codex 额度','DeepSeek balance':'DeepSeek 余额','Kimi balance':'Kimi 余额',
  'Gemini official usage':'Gemini 官方用量','Qwen official usage':'Qwen 官方用量','Legacy Gemini usage':'旧版 Gemini 用量',
  'Full image':'完整图片','Fit image':'适应窗口','Actual size':'原始大小','Zoom in':'放大','Zoom out':'缩小','Close preview':'关闭预览',
  'No screenshots yet.':'暂无截图。','Loading image…':'正在加载图片…','Image unavailable.':'图片加载失败。',
  'Remove screenshot':'移除截图','Ready to test.':'准备就绪。','Running…':'正在运行…','No results yet.':'暂无结果。',
  'Time':'时间','First token':'首字延迟','Total time':'总耗时','Characters/s':'字符/秒','Output tokens':'输出 Token','Status':'状态',
  'Provider':'平台','Model':'模型','Full answer':'完整回答','Usage by model':'按模型统计用量'
 });
 const card=$('usage-settings');card.querySelector('h2').dataset.i='Usage & diagnostics';
 document.querySelector('[data-section="usage-settings"]').dataset.i='Usage & diagnostics';
 document.querySelectorAll('#settings .side-bottom [data-action="speed"],#settings .side-bottom [data-action="check_apis"]').forEach(el=>el.remove());
 const notice=make('p','tools-notice');notice.setAttribute('role','status');card.append(notice);
 const run=async(action,data={})=>{try{await command(action,data)}catch(error){notice.textContent=error.message}};
 const section=(id,title)=>{const el=make('section',id);el.className='diagnostic-section';el.append(make('h3','',title));card.append(el);return el};
 const button=(host,id,title,handler)=>{const el=make('button',id,title);el.type='button';el.onclick=handler;host.append(el);return el};
 const quota=section('quota-tools','Usage & quota'),quotaActions=make('div');quotaActions.className='inline';quota.append(quotaActions);
 button(quotaActions,'quota-refresh','Refresh Codex quota',()=>run('refresh_quota'));
 for(const provider of ['DeepSeek','Kimi'])button(quotaActions,'balance-'+provider,provider+' balance',()=>run('refresh_balance',{provider}));
 for(const provider of ['Gemini','Qwen'])button(quotaActions,'usage-'+provider,provider+' official usage',()=>run('open_usage_page',{provider}));
 quota.append(make('pre','quota-report'));
 const byModel=make('details');byModel.append(make('summary','','Usage by model'),make('pre','model-usage'));quota.append(byModel);
 const legacy=make('details');legacy.append(make('summary','','Legacy Gemini usage'),make('pre','legacy-usage'));quota.append(legacy);
 const speed=section('speed-tools','Model speed test');
 speed.append(make('p','','Benchmark uses a synthetic coding question, without your transcript or personal context.'));
 const form=make('div');form.className='diagnostic-form';speed.append(form);
 const field=(id,title,tag='select')=>{const label=make('label'),input=make(tag,id);label.append(make('span','',title),input);form.append(label);return input};
 field('speed-provider','Provider');const model=field('speed-model','Model','input');model.setAttribute('list','speed-model-list');model.maxLength=256;
 speed.append(make('datalist','speed-model-list'));
 field('speed-effort','Reasoning effort');field('speed-mode','Benchmark mode');const fast=field('speed-fast','Gemini fast reply','input');fast.type='checkbox';
 const speedActions=make('div');speedActions.className='inline';speed.append(speedActions);
 const values=()=>({provider:$('speed-provider').value,model:model.value,effort:$('speed-effort').value,mode:$('speed-mode').value,fast:fast.checked});
 $('speed-provider').onchange=()=>run('speed_select',{provider:$('speed-provider').value});
 model.onchange=()=>run('speed_select',{model:model.value});
 for(const id of ['speed-effort','speed-mode','speed-fast'])$(id).onchange=()=>run('speed_select',values());
 button(speedActions,'speed-refresh','Refresh catalog',()=>run('speed_refresh',values()));
 button(speedActions,'speed-start','Start benchmark',()=>run('speed_start',values())).className='primary';
 button(speedActions,'speed-cancel','Cancel benchmark',()=>run('speed_cancel'));
 const speedStatus=make('p','speed-status');speedStatus.setAttribute('role','status');speed.append(speedStatus);
 const results=make('div','speed-results');results.className='diagnostic-results';speed.append(results);
 const detail=make('pre','speed-detail');detail.tabIndex=0;speed.append(detail);
 const api=section('api-tools','Check APIs');api.append(make('p','','API checks read model catalogs. They do not confirm generation permission or remaining quota.'));
 button(api,'api-start','Run API check',()=>run('check_apis'));
 const report=make('pre','api-report');report.setAttribute('role','status');api.append(report);
 function openTools(part){
  view('settings');window.workbench.selectSection('usage-settings');
  if(!current?.diagnostics?.speed)run('speed');
  requestAnimationFrame(()=>$(part).scrollIntoView({block:'start'}));
 }
 document.addEventListener('click',event=>{
  const action=event.target.closest('[data-action]')?.dataset.action;
  if(['usage','speed','check_apis','screenshots'].includes(action)){
   event.preventDefault();event.stopImmediatePropagation();
   if(action==='screenshots'){openImage();return}
   openTools(action==='speed'?'speed-tools':action==='check_apis'?'api-tools':'quota-tools');
  }else if(event.target.closest('[data-section="usage-settings"]')&&!current?.diagnostics?.speed)run('speed');
 },true);
 // Workbench's capture handler owns sidebar navigation, so initialize lazily on render too.
 let opening=false,resultSignature='';
 function selectOptions(id,items,value){
  const el=$(id),signature=JSON.stringify([items,language]);
  if(el.dataset.options!==signature){el.replaceChildren(...items.map(item=>{const o=make('option');o.value=item;o.textContent=id==='speed-mode'?(item==='Coding'?(language==='zh'?'编程':'Coding'):label(item)):item;return o}));el.dataset.options=signature}
  el.value=value;
 }
 function render(s){
  const d=s?.diagnostics||{},b=d.speed;
  if(document.body.dataset.view==='settings'&&card.classList.contains('workbench-section-active')&&!b&&!opening){opening=true;run('speed')}
  if(b){
   opening=false;selectOptions('speed-provider',s.providers,b.provider);
   if(document.activeElement!==model)model.value=b.model;
   const modelSignature=JSON.stringify(b.models);
   if($('speed-model-list').dataset.options!==modelSignature){$('speed-model-list').replaceChildren(...(b.models||[]).map(value=>{const o=make('option');o.value=value;return o}));$('speed-model-list').dataset.options=modelSignature}
   selectOptions('speed-effort',b.efforts,b.effort);selectOptions('speed-mode',['快速','推理','Coding'],b.mode);fast.checked=b.fast;
   form.querySelectorAll('input,select').forEach(el=>el.disabled=b.busy);
   $('speed-start').disabled=$('speed-refresh').disabled=b.busy;$('speed-cancel').disabled=!b.busy;
   speedStatus.textContent=b.busy?t('Running…'):b.status||t('Ready to test.');
   const sig=JSON.stringify([b.results,language]);
   if(sig!==resultSignature){
    resultSignature=sig;results.replaceChildren();
    if(!b.results?.length){results.append(make('p','','No results yet.'));detail.textContent=''}
    else{
     const table=make('table'),head=make('tr');
     for(const name of ['Time','Provider','Model','Reasoning effort','First token','Total time','Characters/s','Output tokens','Status','Results'])head.append(make('th','',name));
     table.append(head);
     b.results.forEach((r,index)=>{
      const row=make('tr');
      for(const value of [r.time,r.provider,r.model,r.effort,r.first==null?'—':r.first.toFixed(2)+'s',r.elapsed.toFixed(2)+'s',r.chars_per_second.toFixed(1),r.output_tokens??'—',r.status]){const cell=make('td');cell.textContent=value;row.append(cell)}
      const cell=make('td');button(cell,'','Full answer',()=>{detail.textContent=r.error||r.text;detail.focus()});row.append(cell);table.append(row);
      if(index===b.results.length-1)detail.textContent=r.error||r.text;
     });results.append(table);
    }
   }
  }else{$('speed-start').disabled=$('speed-refresh').disabled=$('speed-cancel').disabled=true}
  $('api-start').disabled=!!d.api?.busy;report.textContent=d.api?.report||t('Ready to test.');
  const q=d.quota||{};$('quota-report').textContent=[q.codex,q.deepseek,q.kimi].filter(Boolean).join('\n\n');
  $('model-usage').textContent=q.models||'—';$('legacy-usage').textContent=q.legacy||'—';$('quota-refresh').disabled=!!q.busy;
  for(const provider of ['DeepSeek','Kimi'])$('balance-'+provider).disabled=(q.balances||[]).includes(provider);
  if(!viewer.hidden)refreshImages(s.images||[]);
 }
 const viewer=make('div','image-viewer');viewer.className='image-viewer';viewer.hidden=true;viewer.setAttribute('role','dialog');viewer.setAttribute('aria-modal','true');viewer.setAttribute('aria-labelledby','image-title');
 const header=make('div');header.className='image-viewer-header';header.append(make('h2','image-title','Full image'));
 const image=make('img','full-image'),viewport=make('div','image-viewport');viewport.tabIndex=0;viewport.append(image);
 const imageNotice=make('p','image-notice');imageNotice.setAttribute('role','status');
 const listing=make('div','image-list');listing.setAttribute('aria-label','Screenshots');
 let source='',imageId=null,sequence=0,origin=null,zoom=null,imagesSignature='';
 function size(value){zoom=value;image.style.width=value===null?'':image.naturalWidth*value+'px';image.style.maxWidth=value===null?'100%':'none';image.style.maxHeight=value===null?'100%':'none';$('image-zoom').textContent=value===null?t('Fit image'):Math.round(value*100)+'%'}
 button(header,'image-fit','Fit image',()=>size(null));button(header,'image-actual','Actual size',()=>size(1));
 button(header,'image-minus','Zoom out',()=>size(Math.max(.1,(zoom??Math.min(viewport.clientWidth/image.naturalWidth,viewport.clientHeight/image.naturalHeight,1))/1.25)));
 header.append(make('output','image-zoom'));
 button(header,'image-plus','Zoom in',()=>size(Math.min(8,(zoom??Math.min(viewport.clientWidth/image.naturalWidth,viewport.clientHeight/image.naturalHeight,1))*1.25)));
 button(header,'image-remove','Remove screenshot',()=>imageId&&run('remove_image',{id:imageId}));
 const close=()=>{sequence++;viewer.hidden=true;document.querySelector('.shell').inert=false;if(source)URL.revokeObjectURL(source);source='';image.removeAttribute('src');origin?.focus();scheduleShape()};
 button(header,'image-close','Close preview',close);
 viewer.append(header,listing,imageNotice,viewport);document.body.append(viewer);
 image.ondblclick=()=>size(zoom===null?1:null);
 function refreshImages(items){
  const sig=JSON.stringify(items);if(sig===imagesSignature)return;imagesSignature=sig;
  listing.replaceChildren(...items.map(item=>{const el=make('button');el.textContent=item.title;el.onclick=()=>openImage(item.id);return el}));
  if(!items.some(item=>item.id===imageId))openImage(items[0]?.id);
 }
 async function openImage(id){
  const items=current?.images||[];const item=items.find(i=>i.id===id)||items[0];imageId=item?.id;
  if(viewer.hidden)origin=document.activeElement;
  viewer.hidden=false;document.querySelector('.shell').inert=true;refreshImages(items);$('image-close').focus();scheduleShape();
  const request=++sequence;if(source)URL.revokeObjectURL(source);source='';image.removeAttribute('src');
  imageNotice.textContent=t(item?'Loading image…':'No screenshots yet.');$('image-remove').disabled=!item;
  header.querySelectorAll('#image-fit,#image-actual,#image-minus,#image-plus').forEach(el=>el.disabled=!item);
  if(!item)return;
  image.alt=item.title;$('image-title').textContent=item.title;
  try{
   const response=await fetch('/image/'+encodeURIComponent(item.id),{headers:{'X-Listener-Token':token}});if(!response.ok)throw Error();
   const blob=await response.blob();if(request!==sequence)return;
   source=URL.createObjectURL(blob);image.onload=()=>{if(request===sequence){size(null);imageNotice.textContent=''}};
   image.onerror=()=>{if(request===sequence)imageNotice.textContent=t('Image unavailable.')};image.src=source;
  }catch{if(request===sequence)imageNotice.textContent=t('Image unavailable.')}
 }
 document.addEventListener('keydown',event=>{
  if(viewer.hidden)return;
  if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();close()}
  if(event.key==='Tab'){
   const focusable=[...viewer.querySelectorAll('button:not(:disabled),[tabindex="0"]')];
   const first=focusable[0],last=focusable.at(-1);
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
  }
 },true);
 window.settingsTools={render,openImage};setLanguage(language);if(current)render(current);
})();
