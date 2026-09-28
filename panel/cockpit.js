(()=>{'use strict';
const el=id=>document.getElementById(id);const viewport=el('pages');let state=null,busy=false;
const uid=()=>globalThis.crypto?.randomUUID?.()||'deck-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
async function call(path,data){const r=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok)throw Error('HTTP '+r.status);return r.json()}
const indicator=document.createElement('span');indicator.className='swipe-indicator';indicator.textContent='01 / 04 · DESLIZE';document.querySelector('.brand').append(indicator);
viewport.addEventListener('scroll',()=>{indicator.textContent=String(Math.round(viewport.scrollLeft/viewport.clientWidth)+1).padStart(2,'0')+' / 04 · DESLIZE'},{passive:true});
const group=el('meetingStart').parentElement;
function key(id,label,handler){let b=el(id);if(!b){b=document.createElement('button');b.id=id;b.className='key toggle-key';const span=document.createElement('span');span.textContent=label;b.append(span);group.append(b)}b.onclick=handler;return b}
el('meetingStart').classList.add('toggle-key');el('meetingStart').setAttribute('aria-pressed','false');
const pause=key('meetingPause','Pausar / continuar',()=>command(state?.status==='paused'?'resume':'pause'));pause.setAttribute('aria-pressed','false');
const record=key('meetingRecords','Transcrição e análise',showRecords);record.classList.remove('toggle-key');
const alerts=key('meetingAlerts','Alertas e contexto',showAlerts);alerts.classList.remove('toggle-key');
el('meetingIndicator').classList.add('instrument-status');
function display(result){if(!result.ok){el('meetingIndicator').textContent=result.error||'Consulta indisponível';return}state=result.session;const active=state?.status==='active';el('meetingStart').setAttribute('aria-pressed',String(result.recording===true));pause.setAttribute('aria-pressed',String(state?.status==='paused'));pause.disabled=busy||!['active','paused'].includes(state?.status);el('meetingStart').disabled=busy||['active','paused','ending'].includes(state?.status);el('meetingStop').disabled=busy||!['active','paused'].includes(state?.status);el('meetingIndicator').dataset.state=state?.status||'idle';
const names={active:result.recording?'CAPTURANDO DOIS CANAIS':'AGUARDANDO ÁUDIO',paused:'PAUSADA',ending:'PROCESSANDO TRANSCRIÇÃO E ANÁLISE',complete:'CONCLUÍDA'};
el('meetingIndicator').textContent=state?names[state.status]+' · '+state.title+' · '+result.transcript_count+' trechos'+(result.heartbeat_age!=null?' · sinal há '+Math.round(result.heartbeat_age)+' s':''):'Pronto. Telegram e painel controlam a mesma reunião.';
if(result.last_error&&active&&!result.recording)el('meetingIndicator').textContent+=' · '+result.last_error;
}
async function refresh(){try{display(await call('/meeting/status'))}catch{el('meetingIndicator').textContent='Ponte indisponível. Registros permanecem preservados.'}}
async function command(action,value=''){if(busy)return;busy=true;try{const r=await call('/meeting/'+action,{session_id:state?.id,request_id:uid(),value,key:action==='start'&&typeof selectedMeeting!=='undefined'?selectedMeeting:null});display(r);return r}catch{el('meetingIndicator').textContent='Sem confirmação de execução. Atualize o estado antes de repetir.'}finally{busy=false;await refresh()}}
el('meetingStart').onclick=()=>command('start');el('meetingStop').onclick=()=>command('stop');
async function showRecords(){let overlay=document.createElement('section');overlay.className='meeting-records';overlay.setAttribute('role','dialog');overlay.setAttribute('aria-label','Registro da reunião');const header=document.createElement('header'),title=document.createElement('strong'),close=document.createElement('button');title.textContent='REGISTRO DA REUNIÃO';close.textContent='Fechar';close.className='pill';close.onclick=()=>overlay.remove();header.append(title,close);overlay.append(header);document.body.append(overlay);try{const r=await call('/meeting/records');for(const [name,text] of [['Transcrição integral',r.transcript||'Ainda não há transcrição.'],['Análise da reunião',r.analysis||'A análise final aparece após encerrar.']]){const h=document.createElement('h2'),p=document.createElement('pre');h.textContent=name;p.textContent=text;overlay.append(h,p)}}catch{title.textContent='Registro indisponível nesta consulta'}}
async function showAlerts(){
 const overlay=document.createElement('section');overlay.className='meeting-records';overlay.style.overflowWrap='anywhere';overlay.role='dialog';overlay.setAttribute('aria-label','Alertas e contexto');
 const header=document.createElement('header'),title=document.createElement('strong'),close=document.createElement('button'),body=document.createElement('div');
 title.textContent='ALERTAS E CONTEXTO';close.textContent='Fechar';close.className='pill';close.onclick=()=>{overlay.remove();alerts.focus()};header.append(title,close);overlay.append(header,body);document.body.append(overlay);close.focus();overlay.onkeydown=e=>{if(e.key==='Escape')close.click()};
 function node(tag,text){const n=document.createElement(tag);n.textContent=text;return n}
 function button(parent,label,handler){const b=node('button',label);b.className='pill';b.style.margin='6px';b.onclick=handler;parent.append(b);return b}
 async function perform(action,value=''){const r=await command(action,value);if(r?.ok)await load();else body.prepend(node('p',r?.error||'Sem confirmação. Atualize antes de repetir.'))}
 function field(label,value,action,caption){const box=document.createElement('div'),id='context-'+action,l=node('label',label),input=document.createElement('input');l.htmlFor=id;input.id=id;input.value=value||'';input.style.cssText='display:block;width:min(100%,480px);padding:12px;margin:8px 0;color:inherit;background:#171d28;border:1px solid #667085;border-radius:6px';box.append(l,input);button(box,caption,()=>perform(action,input.value));body.append(box)}
 async function load(){
  const r=await call('/meeting/records');if(!r.ok)throw Error(r.error||'Consulta indisponível');body.replaceChildren();
  body.append(node('p',r.session?r.session.title+' · '+(r.session.state.project||'Projeto não selecionado'):'Prepare a agenda; inicie a captura pelo botão Iniciar reunião.'));
  if(r.session){
   const st=r.session.state||{};
   button(body,st.alerts_muted?'Ativar alertas':'Silenciar alertas',()=>perform(st.alerts_muted?'unmute':'mute'));
   field('Cliente dos chamados',st.ticket_client||'automatico','client','Salvar cliente');
   field('Projeto da reunião',st.project,'project','Salvar projeto');
   field('IDs dos chamados deste projeto',(st.selected_ticket_ids||[]).join(','),'tickets','Vincular chamados');
   if(st.intelligence_sources)body.append(node('p','Fontes consultadas: '+Object.entries(st.intelligence_sources).map(([k,v])=>k+' — '+v).join('; ')));
  }
  button(body,'Preparar agenda',()=>perform('prepare'));
  for(const event of r.preparation||[]){const line=node('div',event.subject+' · '+new Date(event.start).toLocaleString('pt-BR'));if(r.session)button(line,'Usar este convite',()=>perform('select_event',event.id));body.append(line)}
  body.append(node('h2','Perguntas e evidências'));
  if(!r.alerts?.length)body.append(node('p','Nenhum alerta validado nesta reunião.'));
  const names={pending:'Aguardando envio',sent:'Enviado',uncertain:'Envio sem confirmação',cancelled:'Resolvido ou descartado',superseded:'Contexto alterado',stale:'Expirado',suppressed:'Registrado sem notificação'};
  for(const row of r.alerts||[]){const card=document.createElement('article');card.style.cssText='padding:16px;margin:14px 0;border:1px solid #667085;border-radius:10px';const f=row.finding;
   card.append(node('p',names[row.status]||row.status),node('h3',f.claim),node('p',f.question));if(f.uncertainty)card.append(node('p','Limite: '+f.uncertainty));
   for(const ref of f.transcript_refs||[])card.append(node('p','Fala '+ref.id+' · '+new Date(ref.at*1000).toLocaleTimeString('pt-BR')));
   for(const ref of f.evidence_refs||[])card.append(node('p',ref.id+' · '+(ref.dated_at||'Data desconhecida')+' · '+ref.source));
   for(const [label,value] of [['Útil','useful'],['Incorreto','incorrect'],['Resolvido','resolved']])button(card,label,()=>perform('feedback',row.finding_id+' '+value));body.append(card);
  }
 }
 try{await load()}catch{body.append(node('p','Consulta indisponível. Feche e tente atualizar.'))}
}
const audio=document.querySelector('.volume-readout');audio.replaceChildren();const radio=document.createElement('div');radio.className='radio-control';const dial=document.createElement('div');dial.className='radio-dial';dial.role='slider';dial.tabIndex=0;dial.setAttribute('aria-label','Volume do computador');dial.setAttribute('aria-valuemin','0');dial.setAttribute('aria-valuemax','100');const pointer=document.createElement('i');pointer.className='dial-pointer';dial.append(pointer);const readout=document.createElement('div'),number=document.createElement('div'),hint=document.createElement('div');number.className='radio-number';hint.className='radio-hint';hint.textContent='Arraste para cima ou para baixo. Setas ajustam o volume.';readout.append(number,hint);radio.append(dial,readout);audio.append(radio);let vol=0,startY=0,startVol=0,drag=false;
function draw(v){vol=Math.max(0,Math.min(100,Math.round(v)));number.textContent=vol+'%';dial.style.setProperty('--rotation',(-135+vol*2.7)+'deg');dial.setAttribute('aria-valuenow',String(vol))}
async function sync(){try{const r=await call('/volume');if(r.ok&&!drag){draw(r.volume);document.querySelectorAll('[data-action=vol_mute]').forEach(b=>{b.classList.add('toggle-key');b.setAttribute('aria-pressed',String(r.muted))})}}catch{number.textContent='—'}}
async function commit(){try{const r=await call('/action',{action:'vol_set',payload:vol});if(r.ok)draw(r.volume)}finally{await sync()}}
dial.onpointerdown=e=>{drag=true;startY=e.clientY;startVol=vol;dial.setPointerCapture(e.pointerId)};dial.onpointermove=e=>{if(drag)draw(startVol+(startY-e.clientY)/1.5)};dial.onpointerup=()=>{drag=false;commit()};dial.onpointercancel=()=>{drag=false;sync()};dial.onkeydown=e=>{if(['ArrowUp','ArrowRight','ArrowDown','ArrowLeft','Home','End'].includes(e.key)){e.preventDefault();draw(e.key==='Home'?0:e.key==='End'?100:vol+(['ArrowUp','ArrowRight'].includes(e.key)?2:-2));commit()}};
refresh();sync();setInterval(()=>{if(!document.hidden&&!busy)refresh()},8000);setInterval(()=>{if(!document.hidden)sync()},5000);
})();
