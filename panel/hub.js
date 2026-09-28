/* Integrated modules: render data as text, never execute returned HTML. */
(()=>{
const modules=[['chat','Conversar','00'],['team','Kanban','01'],['docs','Documentação','02'],['drive','Google Drive','03'],['rag','Base RAG','04'],['knowledge','Conhecimento','05'],['email','EasySapers','06'],['agents','Agentes','07'],['router','9router','08'],['preferences','Preferências','09'],['videos','Vídeos','10'],['agenda','Agenda','11'],['applications','Aplicativos','12'],['finance','Financeiro','13'],['connections','Conexões locais','14'],['home','Casa','15'],['campaigns','Estúdio de vendas','16'],['librechat','LibreChat','17'],['research','Pesquisa de vendas','18'],['flow','Vídeo IA / acesso','19']];
const hub=document.createElement('section');hub.className='hub';hub.hidden=true;hub.innerHTML='<div class="hub-top"><button class="hub-back" aria-label="Voltar ao cockpit">← Voltar</button><div><h1 id="hubTitle">Central</h1><small>ULTRON / CONTROLE INTEGRADO</small></div><button class="hub-refresh">Atualizar</button></div><div class="hub-tabs"></div><div class="hub-content"></div>';document.body.append(hub);
const content=hub.querySelector('.hub-content'),tabs=hub.querySelector('.hub-tabs');let current='team',generation=0,driveParents=['root'];
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}
function button(text,callback,cls='action'){const b=el('button',text,cls);b.onclick=callback;return b}
function block(text){return el('pre',text,'hub-pre')}
function hint(text){return el('p',text,'hub-muted')}
async function api(action,data={}){const stamp=generation;const r=await fetch('/hub',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...data}),signal:AbortSignal.timeout(110000)});const result=await r.json();if(stamp!==generation)throw new DOMException('Tela alterada','AbortError');if(!r.ok||!result.ok)throw Error(result.error||'Consulta indisponível');return result}
function fail(e){if(e.name==='AbortError')return;content.replaceChildren(el('div',e.message||String(e),'hub-error'))}
function toolbar(placeholder,search){const row=el('form',undefined,'hub-toolbar'),input=el('input');input.placeholder=placeholder;row.append(input,button('Buscar',()=>{}));row.onsubmit=e=>{e.preventDefault();search(input.value)};return row}
function card(title,details,callback){const c=el(callback?'button':'article',undefined,'hub-card');c.append(el('h2',title));for(const d of details)c.append(el('p',d));if(callback)c.onclick=callback;return c}
function grid(){const g=el('div',undefined,'hub-grid');content.append(g);return g}
for(const [id,label]of modules){const b=button(label,()=>open(id),'');b.dataset.module=id;tabs.append(b)}
hub.querySelector('.hub-back').onclick=()=>{hub.hidden=true;stopLive();generation++;history.replaceState(null,'',location.pathname+location.search)};hub.querySelector('.hub-refresh').onclick=()=>location.hash.startsWith('#kanban/')?task(decodeURIComponent(location.hash.slice(8))):open(current);
function ready(){stopLive();content.replaceChildren()}
async function open(id){if(!views[id])return;stopLive();history.replaceState(null,'',location.pathname+location.search+'#'+(id==='team'?'kanban':id));current=id;hub.hidden=false;hub.querySelector('#hubTitle').textContent=modules.find(m=>m[0]===id)?.[1]||'Central';tabs.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.module===id));content.replaceChildren(hint('Consultando dados reais…'));const stamp=++generation;try{await views[id](stamp)}catch(e){if(stamp===generation)fail(e)}}
let chatSession=localStorage.getItem('deck:chat:session')||null;
const views={
chat:async()=>{ready();const timeline=el('div'),input=el('textarea');input.placeholder='Converse com Ultron. A resposta e a voz aparecem aqui.';
const send=async(listen=false)=>{const text=input.value.trim();if(!text&&!listen)return;talk.disabled=true;mic.disabled=true;input.value='';timeline.append(card('Você',[listen?'Escutando o microfone do Saitama por 8 segundos…':text]));const pending=card('Ultron',['Preparando resposta e segunda verificação…']);timeline.append(pending);
try{const r=await api('chat_start',{text,listen,session:chatSession,profile:'ultron',speak:true});let result;for(let i=0;i<130;i++){await new Promise(resolve=>setTimeout(resolve,3000));result=await api('chat_status',{job:r.job});if(result.status==='done')break;}if(result?.status!=='done')throw Error('Resposta ainda pendente.');const answer=result.result;if(!answer.ok)throw Error(answer.error||'Resposta indisponível');chatSession=answer.session;localStorage.setItem('deck:chat:session',chatSession);pending.replaceChildren(el('h2','Ultron'),el('p',answer.text));if(answer.transcript)pending.prepend(hint('Reconhecido: '+answer.transcript));if(answer.audio){const audio=el('audio');audio.controls=true;audio.src=answer.audio;pending.append(audio);audio.play().catch(()=>{});}if(answer.audio_error)pending.append(hint(answer.audio_error));}catch(e){if(e.name!=='AbortError')pending.replaceChildren(hint(e.message))}finally{talk.disabled=false;mic.disabled=false;}};
const talk=button('Enviar para Ultron',()=>send(false)),mic=button('Escutar no Saitama · 8 s',()=>send(true));content.append(hint('Conversa real com Hermes e voz neste painel. O botão de escuta usa o microfone do computador Saitama.'),timeline,input,talk,mic,button('Nova conversa',()=>{chatSession=null;localStorage.removeItem('deck:chat:session');open('chat')}));},
team:async()=>{const d=await api('kanban');ready();renderKanban(d)},
docs:async()=>documents(),
videos:async()=>{const d=await api('videos');ready();content.append(hint('Testes internos: confira a identidade do produto, o manuseio e os direitos de uso antes de publicar.'));const g=grid();for(const f of d.videos)g.append(card(f.name,[f.folder,Math.ceil(f.bytes/1024/1024)+' MB'],()=>{ready();const video=el('video');video.controls=true;video.playsInline=true;video.preload='metadata';video.className='hub-media';video.src='/media/'+f.id;content.append(button('← Biblioteca',()=>open('videos')),el('h2',f.name),video);}));},
agenda:async()=>{const stamp=generation;const r=await fetch('/meetings');const d=await r.json();if(stamp!==generation)return;ready();if(!d.ok)throw Error(d.error||'Agenda indisponível');content.append(hint('Agenda EasySapers. Entrar abre a reunião no Saitama: Teams e Zoom pelo app, os demais no navegador do desktop.'));const g=grid();for(const m of d.meetings){const c=card(m.subject,[m.start||m.time||'',m.organizer||'']);c.append(button('Entrar no Saitama',async()=>{const result=await (await fetch('/meeting/join',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:m.key})})).json();c.append(hint(result.ok?'Reunião aberta no Saitama'+(result.app?' ('+result.app+')':''):result.error));}));if(m.can_decline)c.append(button('Recusar convite',async()=>{if(!confirm('Recusar este convite de reunião e avisar o organizador?'))return;const result=await (await fetch('/meeting/decline',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:m.key,confirmed:true})})).json();c.append(hint(result.ok?'Convite recusado':result.error));}));g.append(c)}if(!d.meetings.length)content.append(hint('Nenhuma reunião encontrada hoje.'));},
drive:async()=>drive(),
rag:async()=>{const d=await api('rag_list');ready();content.append(hint('Selecione as fontes e pesquise. A base preserva arquivo, data e trechos; não substitui as memórias.'));const chosen=new Set(d.documents.map(f=>f.file_id));const result=el('div',undefined,'hub-detail');content.append(toolbar('Pergunte aos documentos',async query=>{result.replaceChildren(hint('Pesquisando…'));try{const r=await api('rag_search',{query,file_ids:[...chosen]});result.replaceChildren();for(const item of r.hits||[]){const hit=Array.isArray(item)?item[0]:item;result.append(card(hit.metadata?.source||hit.metadata?.file_id||'Trecho recuperado',[hit.page_content||JSON.stringify(hit)]))}if(!(r.hits||[]).length)result.append(hint('Nenhum trecho encontrado.'));result.append(hint(r.notice))}catch(e){result.replaceChildren(hint(e.message))}}));for(const f of d.documents){const l=el('label',undefined,'hub-check'),c=el('input');c.type='checkbox';c.checked=true;c.onchange=()=>c.checked?chosen.add(f.file_id):chosen.delete(f.file_id);l.append(c,el('span',(f.name||f.file_id)+' · '+(f.chunks||'?')+' trechos · '+(f.indexed_at||'')));content.append(l)}content.append(result)},
knowledge:async()=>knowledge(),
email:async()=>{const d=await api('workmail_list');ready();content.append(hint('EasySapers · '+d.unread_count+' não lidos · últimas 30 mensagens. Abrir aqui não marca como lido.'));const g=grid();for(const m of d.messages)g.append(card((m.unread?'● ':'')+m.subject,[m.sender,m.date],async()=>{try{const r=await api('workmail_read',{uid:m.uid});ready();content.append(button('← Caixa EasySapers',()=>open('email')),el('h2',r.message.subject),hint(r.message.sender+' · '+r.message.date),block(r.message.content))}catch(e){fail(e)}}))},
agents:async()=>{const d=await api('agents');ready();content.append(hint('Perfis e conexões preservados. Atribua tarefas pelo quadro da equipe.'));const g=grid();for(const a of d.agents)g.append(card(a.name,[a.model||'Modelo padrão',a.provider||'Provedor configurado'],()=>newTask(a.name)))},
router:async()=>{const d=await api('router');ready();content.append(hint('Conexões e modelos reais. Segredos nunca são enviados ao painel.'));const g=grid();for(const p of d.providers)g.append(card(p.provider,[p.name,p.isActive?'Habilitado · '+p.status:'Desabilitado',p.error_code?'Último erro: '+p.error_code:'Prioridade '+p.priority]));content.append(el('h2','Rotas por função'));for(const c of d.combos)content.append(card(c.name,c.models));content.append(el('h2','Uso nas últimas 24 horas'));const table=el('table'),head=el('tr');for(const s of ['Provedor / modelo','Chamadas','Entrada','Saída'])head.append(el('th',s));table.append(head);for(const u of d.usage){const row=el('tr');for(const v of [u.provider+' / '+u.model,u.requests,u.input_tokens,u.output_tokens])row.append(el('td',String(v)));table.append(row)}content.append(table)},
preferences:async()=>{const d=await api('preferences');ready();content.append(block(d.content))}
};
async function documents(query='',offset=0){const d=await api('docs',{query,offset});ready();content.append(toolbar('Buscar nome ou pasta de documento',q=>documents(q)),hint(d.total+' documentos · página '+(Math.floor(offset/60)+1)));const g=grid();for(const f of d.documents)g.append(card(f.name,[f.path,Math.ceil(f.bytes/1024)+' KB'],async()=>{try{const r=await api('doc',{path:f.path});ready();content.append(button('← Documentos',()=>documents(query,offset)),el('h2',r.name),block(r.content))}catch(e){fail(e)}}));if(offset)content.append(button('← Anterior',()=>documents(query,Math.max(0,offset-60))));if(d.next_offset!==null)content.append(button('Mais documentos →',()=>documents(query,d.next_offset)));}

const kanbanColumns=[['blocked','Aguardando'],['todo','Planejado'],['ready','Pronto'],['running','Em andamento'],['review','Em revisão'],['scheduled','Agendado'],['done','Concluído'],['archived','Arquivado']];
function boardStatus(value){return ({doing:'running',completed:'done',open:'todo',triage:'todo'})[value]||value}
function statusLabel(value){return kanbanColumns.find(c=>c[0]===boardStatus(value))?.[1]||value}
function boardDate(value){if(!value)return 'Data não registrada';const numeric=Number(value);const date=new Date(Number.isFinite(numeric)?numeric*1000:String(value));return Number.isNaN(date.getTime())?'Data não registrada':date.toLocaleString('pt-BR')}
let stopLive=()=>{};
function watchBoard(refresh){stopLive();let active=true,busy=false;const timer=setInterval(async()=>{if(!active||busy||hub.hidden||document.hidden)return;busy=true;try{await refresh(()=>active)}catch(e){if(active&&e.name!=='AbortError'){const status=content.querySelector('.kanban-live');if(status)status.textContent='Atualização indisponível; tentando novamente em 15 s.'}}finally{busy=false}},15000);stopLive=()=>{active=false;clearInterval(timer)}}
function discussionCard(c){const n=el('article',undefined,'kanban-message');n.dataset.commentId=c.id;n.append(el('h4',c.author||'Autor não informado'),el('time',boardDate(c.created_at)),el('p',c.body));return n}
function renderKanban(initial){
 let data=initial;
 const tools=el('div',undefined,'hub-toolbar');
 const search=el('input');search.type='search';search.placeholder='Buscar tarefa, responsável ou participante';search.setAttribute('aria-label','Buscar tarefas');
 const who=el('select');who.setAttribute('aria-label','Responsável');
 const include=el('input');include.type='checkbox';include.id='kanbanDone';const label=el('label',undefined,'kanban-check');label.append(include,el('span','Mostrar concluídas'));
 const archived=el('input');archived.type='checkbox';archived.id='kanbanArchived';const history=el('label',undefined,'kanban-check');history.append(archived,el('span','Mostrar arquivadas'));
 const activity=el('section',undefined,'kanban-activity');activity.setAttribute('aria-label','Conversas recentes dos agentes');
 tools.append(button('Nova tarefa',()=>newTask()),button('Conversas dos agentes',()=>activity.scrollIntoView({behavior:'smooth',block:'start'})),search,who,label,history);content.append(tools);
 const counts=el('p',undefined,'hub-muted');counts.setAttribute('role','status');const live=hint('Atualização automática a cada 15 s');live.classList.add('kanban-live');content.append(counts,live,hint('Quadro único do Hermes · abra um cartão para acompanhar a conversa, as revisões e as evidências. Rotinas mostram a ocorrência mais recente, inclusive quando concluída.'));
 const board=el('div',undefined,'kanban-board');board.setAttribute('aria-label','Quadro de tarefas');content.append(board,activity);
 const render=()=>{
  const tasks=data.tasks||[],selected=who.value;who.replaceChildren(new Option('Todos os responsáveis',''));
  for(const name of [...new Set(tasks.map(t=>(t.assignee||'').toLowerCase()).filter(Boolean))].sort())who.append(new Option(name,name));who.value=selected;
  const q=search.value.trim().toLocaleLowerCase('pt-BR');
  const visible=tasks.filter(t=>(archived.checked||t.status!=='archived')&&(include.checked||boardStatus(t.status)!=='done'||t.recurring_current)&&(!who.value||(t.assignee||'').toLowerCase()===who.value)&&(!q||(t.title+' '+(t.assignee||'')+' '+(t.participants||'')).toLocaleLowerCase('pt-BR').includes(q)));
  counts.textContent=visible.length+' tarefas visíveis · '+(data.archived_count||0)+' arquivadas com histórico';board.replaceChildren();
  const columns=[...kanbanColumns];if(visible.some(t=>!columns.some(c=>c[0]===boardStatus(t.status))))columns.push(['other','Outros estados']);
  for(const [key,name] of columns){
   const members=visible.filter(t=>key==='other'?!kanbanColumns.some(c=>c[0]===boardStatus(t.status)):boardStatus(t.status)===key);
   if((key==='done'&&!include.checked&&!members.length)||(key==='archived'&&!archived.checked))continue;
   const column=el('section',undefined,'kanban-column');column.dataset.status=key;column.append(el('h2',name+' · '+members.length,'kanban-heading'));
   for(const item of members){const reason=({needs_input:'Precisa da sua informação',capability:'Recurso pendente',dependency:'Depende de outra tarefa',transient:'Falha temporária'})[item.block_kind];
    const details=[item.assignee||'Sem responsável',reason||statusLabel(item.status),item.comment_count+' mensagens · '+item.run_count+' execuções'];
    if(item.recurring_current)details.push('Rotina atual · '+item.occurrence_date);
    if(item.participants)details.push('Participantes: '+item.participants);
    const c=card(item.title,details,()=>task(item.id));c.classList.add('kanban-card');c.dataset.taskId=item.id;column.append(c);
   }
   if(!members.length)column.append(hint('Nenhuma tarefa nesta etapa.'));board.append(column);
  }
  activity.replaceChildren(el('h2','Conversas recentes dos agentes'),hint('Mensagens registradas no Hermes, com autor e data. Abra a tarefa para ler a conversa completa.'));
  const messages=(data.activity||[]).filter(c=>(!who.value||(c.author||'').toLowerCase().includes(who.value))&&(!q||(c.title+' '+c.author+' '+c.body).toLocaleLowerCase('pt-BR').includes(q)));
  for(const c of messages.slice(0,12)){const n=discussionCard(c);n.prepend(button(c.title,()=>task(c.task_id)));activity.append(n)}
  if(!messages.length)activity.append(hint('Nenhuma mensagem registrada para este filtro.'));
 };
 const refresh=async active=>{const d=await api('kanban',{include_archived:archived.checked});if(!active()||!board.isConnected)return;data=d;render();live.textContent='Atualizado às '+new Date().toLocaleTimeString('pt-BR')+' · acompanha a cada 15 s'};
 search.oninput=render;who.onchange=render;include.onchange=render;archived.onchange=()=>refresh(()=>board.isConnected).catch(fail);render();watchBoard(refresh);
}
async function task(id){
 stopLive();const d=await api('task',{id});ready();if(!d.task){content.append(hint('Tarefa não encontrada'));return}
 history.replaceState(null,'',location.pathname+location.search+'#kanban/'+encodeURIComponent(id));
 const heading=el('h2',d.task.title),state=hint(''),live=hint('Atualização automática a cada 15 s');live.classList.add('kanban-live');
 const description=el('details');description.append(el('summary','Pedido e resultado'),block(d.task.body||''));if(d.task.result)description.append(el('h3','Resultado'),block(d.task.result));
 const thread=el('section',undefined,'kanban-thread');thread.setAttribute('aria-label','Conversa da tarefa');
 const related=el('section',undefined,'kanban-related'),execution=el('details',undefined,'kanban-execution');
 execution.append(el('summary','Execuções e histórico do fluxo'));const records=el('div');execution.append(records);
 content.append(button('Voltar ao Kanban',()=>open('team')),heading,state,live,description,related,thread);
 const paint=value=>{
  heading.textContent=value.task.title;state.textContent=statusLabel(value.task.status)+' · '+(value.task.assignee||'Sem responsável')+' · '+id;
  thread.replaceChildren(el('h3','Conversa entre os agentes'));for(const c of value.comments||[])thread.append(discussionCard(c));if(!value.comments?.length)thread.append(hint('Ainda não há mensagens registradas nesta tarefa.'));
  related.replaceChildren();for(const [label,items]of [['Depende de',value.parents],['Tarefas relacionadas',value.children]])if(items?.length){related.append(el('h3',label));for(const item of items)related.append(button(item.title+' · '+statusLabel(item.status),()=>task(item.id)))}
  records.replaceChildren(el('h3','Execuções'));for(const run of value.runs||[])records.append(card(run.profile+' · '+run.status,[boardDate(run.started_at)+' → '+boardDate(run.ended_at),run.summary||run.outcome||'Sem resumo registrado',run.error||'']));if(!value.runs?.length)records.append(hint('Nenhuma execução de worker registrada. Comentários acima mantêm a autoria original.'));
  if(value.attachments?.length){records.append(el('h3','Evidências anexadas'));for(const a of value.attachments)records.append(hint(a.filename+' · '+(a.uploaded_by||'Autor não informado')+' · '+boardDate(a.created_at)))}
  records.append(el('h3','Mudanças de estado'));const labels={created:'Tarefa criada',claimed:'Execução assumida',spawned:'Agente iniciado',completed:'Concluída',review_requested:'Revisão solicitada',changes_requested:'Correções solicitadas',blocked:'Bloqueada',unblocked:'Retomada',archived:'Arquivada',linked:'Dependência registrada',commented:'Mensagem registrada',attached:'Evidência anexada',crashed:'Falha na execução',gave_up:'Tentativas esgotadas'};
  for(const event of value.events||[]){if(event.kind==='commented')continue;records.append(card(labels[event.kind]||event.kind,[boardDate(event.created_at),...Object.entries(event.details||{}).map(([k,v])=>k+': '+(typeof v==='object'?JSON.stringify(v):String(v)))]))}
 };
 paint(d);
 const input=el('textarea');input.placeholder='Responda ao pedido, registre uma decisão ou forneça informação atualizada e sua fonte.';
 const send=button('Registrar resposta',async()=>{if(!input.value.trim())return;send.disabled=true;try{await api('task_reply',{id,text:input.value,confirmed:true});input.value='';const value=await api('task',{id});paint(value)}catch(e){live.textContent=e.message}finally{send.disabled=false}});
 content.append(el('h3','Sua resposta'),input,send);
 if(d.task.status==='blocked')content.append(button('Responder e retomar tarefa',async()=>{if(!input.value.trim())return;if(!confirm('Registrar sua resposta e colocar esta tarefa novamente na fila dos agentes?'))return;try{await api('task_resume',{id,text:input.value,confirmed:true});await task(id)}catch(e){live.textContent=e.message}}));
 content.append(execution);
 watchBoard(async active=>{const value=await api('task',{id});if(!active()||!thread.isConnected||!value.task)return;paint(value);live.textContent='Atualizado às '+new Date().toLocaleTimeString('pt-BR')+' · seu texto digitado é preservado'});
}

async function newTask(assignee='ultron'){ready();const title=el('input');title.placeholder='Título da tarefa';const who=el('input');who.value=assignee;who.placeholder='Agente responsável';const body=el('textarea');body.placeholder='Objetivo, informações, fontes e resultado esperado';content.append(el('h2','Nova tarefa'),title,who,body,button('Criar no quadro',async()=>{if(!title.value.trim()||!body.value.trim())return;try{const r=await api('task_create',{title:title.value,assignee:who.value,text:body.value,confirmed:true,request_id:(globalThis.crypto?.randomUUID?.()||'deck-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2))});await task(r.task_id)}catch(e){fail(e)}}))}
async function drive(query='',pageToken=''){const parent=driveParents.at(-1);const d=await api('drive_list',{parent,query,page_token:pageToken});ready();content.append(toolbar('Buscar arquivos no Drive',q=>drive(q)));if(driveParents.length>1)content.append(button('← Pasta anterior',()=>{driveParents.pop();drive()}));content.append(hint(d.notice));const g=grid();for(const f of d.files)g.append(card((f.mimeType.endsWith('.folder')?'▣ ':'')+f.name,[f.modifiedTime||'',f.size?Math.ceil(f.size/1024)+' KB':'Pasta / documento Google'],async()=>{if(f.mimeType.endsWith('.folder')){driveParents.push(f.id);await drive();return}try{const r=await api('drive_preview',{id:f.id});ready();content.append(button('← Arquivos',()=>drive()),el('h2',f.name));if(r.content)content.append(block(r.content));else if(r.media){const media=el(r.file.mimeType==='application/pdf'?'iframe':'img');media.className='hub-media';media.src=r.media;if(media.tagName==='IFRAME')media.setAttribute('sandbox','');content.append(media)}else content.append(hint(r.preview_unavailable))}catch(e){fail(e)}}));if(pageToken)content.append(button('Primeira página',()=>drive(query)));if(d.nextPageToken)content.append(button('Mais arquivos →',()=>drive(query,d.nextPageToken)))}
async function knowledge(query=''){const d=await api('knowledge',{query});ready();content.append(toolbar('Buscar fatos e conhecimento',q=>knowledge(q)),hint(d.notice),hint(d.facts.length+' fatos nesta consulta · '+d.entities.length+' entidades · '+d.banks.length+' bancos'));const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.classList.add('hub-graph');svg.setAttribute('viewBox','0 0 900 430');const detail=el('div',undefined,'hub-detail'),points=new Map();const entities=d.entities.filter(e=>d.edges.some(x=>x.entity_id===e.entity_id&&d.facts.some(f=>f.fact_id===x.fact_id))).slice(0,38);entities.forEach((e,i)=>points.set('e'+e.entity_id,{x:450+330*Math.cos(i/entities.length*Math.PI*2),y:215+160*Math.sin(i/entities.length*Math.PI*2)}));d.facts.slice(0,65).forEach((f,i)=>points.set('f'+f.fact_id,{x:450+170*Math.cos(i/Math.min(d.facts.length,65)*Math.PI*2),y:215+90*Math.sin(i/Math.min(d.facts.length,65)*Math.PI*2)}));for(const edge of d.edges){const a=points.get('e'+edge.entity_id),b=points.get('f'+edge.fact_id);if(!a||!b)continue;const l=document.createElementNS(ns,'line');for(const [k,v]of Object.entries({x1:a.x,y1:a.y,x2:b.x,y2:b.y}))l.setAttribute(k,v);svg.append(l)}for(const e of entities){const p=points.get('e'+e.entity_id),c=document.createElementNS(ns,'circle'),t=document.createElementNS(ns,'text');c.setAttribute('cx',p.x);c.setAttribute('cy',p.y);c.setAttribute('r',7);c.setAttribute('fill','#85d8b7');t.setAttribute('x',p.x+10);t.setAttribute('y',p.y+4);t.textContent=e.name.slice(0,22);c.onclick=()=>{detail.replaceChildren(el('h3',e.name));for(const fact of d.facts.filter(f=>d.edges.some(x=>x.entity_id===e.entity_id&&x.fact_id===f.fact_id)))detail.append(card(fact.category,[fact.content,fact.updated_at]))};svg.append(c,t)}for(const f of d.facts){const p=points.get('f'+f.fact_id);if(!p)continue;const c=document.createElementNS(ns,'circle');c.setAttribute('cx',p.x);c.setAttribute('cy',p.y);c.setAttribute('r',4);c.setAttribute('fill','#bb9eff');c.onclick=()=>detail.replaceChildren(block(f.content));svg.append(c)}content.append(svg,hint('Toque em um nó para consultar seus fatos. Relações são as armazenadas; o desenho não cria novas conexões.'),detail);const g=grid();for(const f of d.facts)g.append(card(f.category,[f.content,f.updated_at]))}
views.applications=async()=>{const d=await api('applications');ready();content.append(hint(d.notice));
for(const item of d.needs_input){const box=el('article',undefined,'hub-card');box.append(el('h2',item.name+' foi removido'),hint('Qual aplicativo deve ocupar o lugar dele?'));for(const c of item.candidates)box.append(button(c.name,async()=>{await api('application_choice',{missing:item.id,replacement:c.id});open('applications')}));box.append(button('Manter sem substituto',async()=>{await api('application_choice',{missing:item.id,replacement:'ignore'});open('applications')}));content.append(box)}
content.append(el('h2','Mais usados desde a ativação'));const frequent=grid();for(const app of d.frequent)frequent.append(card(app.name,[Math.round(app.seconds/60)+' minutos em primeiro plano']));
content.append(el('h2','Produtividade instalada'));const installed=grid();for(const app of d.apps.filter(a=>a.present&&a.category!=='other'))installed.append(card(app.name,[app.category]));
};
views.finance=async()=>{ready();const frame=el('iframe');frame.src='/finance/';frame.title='Painel financeiro local';frame.className='hub-finance';content.append(frame)};
views.connections=async()=>{const d=await api('connections');ready();content.append(hint('Serviços locais e autenticação. As credenciais ficam no servidor.'));const g=grid();for(const item of d.services)g.append(card(item.name,[item.ok?'Disponível':'Precisa de atenção',item.note||'']));for(const auth of d.google_auth||[]){content.append(card(auth.name,[auth.state,'Verificado em '+auth.checked_at,...(auth.needs_consent?['No notebook, abra '+auth.consent_url+' para autorizar sua conta.']:[])]));}content.append(el('h2','Conexões Nango'));for(const item of d.connections)content.append(card(item.provider_config_key,[item.connection_id]));content.append(el('h2','Cofre Flowsint'));for(const item of d.vault)content.append(card(item.name,['Credencial armazenada no cofre cifrado']));if(d.errors.length)content.append(block(d.errors.join('\n')));};

views.home=async()=>{
 const d=await api('home_assistant',{request:{action:'states'}});ready();
 try { const modes=await api('home_automations',{request:{action:'snapshot'}});
 content.append(el('h2','Ambiente de trabalho'),hint(modes.notice));
 const controls=el('div',undefined,'mode-controls');
 for(const mode of modes.modes){const b=button(mode.label,async()=>{b.disabled=true;try{await api('home_automations',{request:{action:'mode',mode:mode.id}});await new Promise(r=>setTimeout(r,600));open('home')}catch(e){content.append(hint(e.message));b.disabled=false}});b.setAttribute('aria-pressed',String(modes.mode===mode.id));controls.append(b)}
 content.append(controls,hint('Modo: '+modes.mode_label+' · ciclo: '+modes.timer.state+' · medição há '+(modes.age_seconds??'—')+' s'));
 for(const n of modes.notices)content.append(card(n.title,[n.message]));
 if(modes.stale)content.append(hint('Medições desatualizadas: o painel não presume que os serviços continuam disponíveis.'));
 }catch(e){content.append(hint('Modos locais: '+e.message))}

 content.append(hint('Home Assistant local. Comandos afetam os dispositivos identificados abaixo.'));
 const g=grid();
 for(const item of d.entities){
  const c=card(item.name,[item.entity_id,item.state+(item.unit?' '+item.unit:'')]);g.append(c);
  const domain=item.entity_id.split('.')[0];
  const command=async(service,data={})=>{
   const controls=[...c.querySelectorAll('button,input')];controls.forEach(x=>x.disabled=true);
   try{await api('home_assistant',{request:{action:'service',entity_id:item.entity_id,service,data}});await open('home');}
   catch(e){c.append(hint(e.message));}finally{controls.forEach(x=>x.disabled=false);}
  };
  if(['switch','light','input_boolean','media_player'].includes(domain)){
   const powered=['on','playing','paused','idle','buffering'].includes(item.state);
   const toggle=button(powered?'Desligar':'Ligar',()=>command(powered?'turn_off':'turn_on'),'ha-switch');
   toggle.setAttribute('role','switch');toggle.setAttribute('aria-checked',String(powered));toggle.disabled=['unavailable','unknown'].includes(item.state);c.append(toggle);
  }
  if(domain==='media_player'&&!['unavailable','unknown'].includes(item.state)){
   c.append(button('Pausar',()=>command('media_pause')),button('Reproduzir',()=>command('media_play')));
   const knownVolume=Number.isFinite(item.volume_level);
   const label=el('label',knownVolume?'Volume do dispositivo':'Volume não informado pelo dispositivo'),range=el('input');range.type='range';range.min='0';range.max='100';range.value=String(knownVolume?Math.round(item.volume_level*100):0);range.setAttribute('aria-label','Volume de '+item.name);
   range.onchange=()=>command('volume_set',{volume_level:Number(range.value)/100});label.append(range);c.append(label);
  }
 }
};


views.campaigns=async()=>{const d=await api('campaigns');ready();content.append(hint('HOGOS adaptado ao Ultron: campanhas de produto, roteiro visual, render e revisão. Publicações exigem conexão e recibo verificável.'));const g=grid();for(const c of d.campaigns)g.append(card(c.run_id,[c.target.site_slug+' · '+c.target.slug,c.state,'Próximos responsáveis: '+c.next_profiles.join(', ')]));if(!d.campaigns.length)content.append(hint('Peça ao Ultron uma campanha com o produto e o canal desejados.'));content.append(button('Ver vídeos produzidos',()=>open('videos')));};
views.librechat=async()=>{ready();content.append(hint('Converse com o mesmo Ultron pelo endpoint Ultron Local. O endpoint 9router Local conversa diretamente com os modelos. Login próprio do LibreChat, guardado no cofre local.'));const frame=el('iframe');frame.src='/librechat/';frame.title='LibreChat local';frame.className='hub-finance';content.append(frame);};
views.research=async()=>{
 const [d,j]=await Promise.all([api('viral_research'),api('content_research')]);ready();
 content.append(hint(d.notice),hint('Pesquisa: '+j.job.status+(j.running?' · em execução':'')));
 const start=button('Pesquisar produtos e referências',async()=>{start.disabled=true;try{await api('content_research',{request:{action:'start'}});open('research')}catch(e){content.append(hint(e.message));start.disabled=false}});start.disabled=j.running;content.append(start);
 for(const p of j.job.products||[])content.append(card(p.label,[p.category,p.eligibility,p.offer_status,p.media_status]));
 for(const run of d.research){content.append(el('h2',run.query),hint(run.status+' · '+run.checked_at));const g=grid();for(const r of run.references){g.append(card(r.title,[r.views.toLocaleString('pt-BR')+' visualizações · '+r.duration+' s',r.channel,r.published_at?(r.freshness_verified?'Publicação confirmada: ':'Publicação aproximada: ')+r.published_at:'Data não confirmada',r.url,'Referência visual; sem licença de reutilização']))}}
 if(!d.research.length)content.append(hint('Nenhuma pesquisa concluída ainda.'));
};
let flowHeartbeat;
views.flow=async()=>{
 const d=await api('flow_session',{request:{action:'status'}});ready();clearInterval(flowHeartbeat);
 content.append(hint(d.notice),card('Produção generativa',[String(d.generation.generated_count)+' clipes gerados',d.generation.state,d.generation.provider||'Provedor pendente']));
 const controls=el('div',undefined,'mode-controls');content.append(controls);
 controls.append(button(d.running?'Recarregar sessão':'Iniciar navegador Docker',async()=>{await api('flow_session',{request:{action:'start'}});open('flow')}));
 const stop=button('Suspender e liberar memória',async()=>{const f=content.querySelector('iframe');if(f)f.remove();await api('flow_session',{request:{action:'stop'}});open('flow')});stop.disabled=!d.running;controls.append(stop);
 content.append(hint('Login dentro deste painel. A sessão é suspensa após 15 minutos sem uso; seu perfil é preservado. Nenhuma janela abre no Windows.'));
 if(d.running){const frame=el('iframe');frame.src='/flow/vnc.html?autoconnect=true&resize=scale&path=flow/websockify';frame.title='Google Flow dentro do Docker';frame.className='hub-finance';content.append(frame);await api('flow_session',{request:{action:'touch'}});flowHeartbeat=setInterval(()=>{if(current!=='flow'||hub.hidden){clearInterval(flowHeartbeat);return}if(!document.hidden)api('flow_session',{request:{action:'touch'}}).catch(()=>{})},30000)}
};
window.openDeckModule=open;
const agentsPage=document.querySelector('.page[aria-label="Agentes"]');if(agentsPage){agentsPage.replaceChildren();const label=el('div',undefined,'page-label');label.append(el('h1','Central de comando.'));const g=el('div',undefined,'module-grid');for(const [id,name,no]of modules){const b=button('',()=>open(id),'key');b.append(el('b',no),el('span',name));g.append(b)}agentsPage.append(label,g,hint('Tudo aqui: equipe, arquivos, conhecimento e controle dos agentes.'))}
/* 27/09/2026: botões "Abrir … no Saitama" e os cartões Hermes/Kanban/9router voltaram a abrir no desktop (POST /action e /open via abrir-local.js); as telas internas continuam nos módulos do hub. */
/* Atalhos ↗ do topo abrem o Outlook no Saitama (caixa e calendário); o celular fica onde está. As listas continuam na página 04 e no módulo EasySapers. */
for(const [id,action]of [['showInbox','outlook'],['showMeetings','outlook_cal']]){const b=document.getElementById(id);if(b){b.onclick=null;b.dataset.action=action;b.title='Abre no Saitama'}}
const quick=document.querySelector('.quick-daily');
if(quick){const shortcut=button('',()=>open('team'),'kanban-shortcut');shortcut.append(el('b','KANBAN'),el('span','Tarefas e pendências'));quick.prepend(shortcut)}
async function openFromHash(){const key=location.hash.slice(1);if(key.startsWith('kanban/')){const taskId=decodeURIComponent(key.slice(7));await open('team');await task(taskId);return}const id=key==='kanban'?'team':key;if(views[id])open(id)}
window.addEventListener('hashchange',openFromHash);openFromHash();
})();
