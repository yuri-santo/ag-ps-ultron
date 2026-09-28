/* Ultron Deck: tudo que abriria outra página ou site abre no Saitama, não no celular.
   Links externos, window.open e links dentro dos painéis embutidos (LibreChat, finanças)
   viram POST /open; o celular só mostra um aviso e continua na mesma tela. */
(()=>{'use strict';
if(window.__abrirLocal)return;window.__abrirLocal=true;
const APP_SCHEMES=['msteams:','zoommtg:','zoomus:'];
function aviso(text){try{if(typeof window.toast==='function'){window.toast(text);return}}catch{}
  let n=document.getElementById('abrirLocalAviso');
  if(!n){n=document.createElement('div');n.id='abrirLocalAviso';n.setAttribute('role','status');
    n.style.cssText='position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:99999;padding:10px 16px;border-radius:12px;background:#111c;color:#fff;font:14px system-ui;pointer-events:none;transition:opacity .3s';
    document.body.append(n)}
  n.textContent=text;n.style.opacity='1';clearTimeout(n._t);n._t=setTimeout(()=>{n.style.opacity='0'},3000)}
/* Endereço que deve abrir no Saitama, ou null para deixar o painel tratar (âncoras, rotas do próprio deck). */
function alvo(href,base){
  if(!href||typeof href!=='string')return null;const raw=href.trim();if(!raw||raw.startsWith('#'))return null;
  let u;try{u=new URL(raw,base||location.href)}catch{return null}
  if(APP_SCHEMES.includes(u.protocol))return u.href;
  if(u.protocol!=='http:'&&u.protocol!=='https:')return null;
  if(u.origin===location.origin)return null;
  return u.href}
let ultimo='',ultimoEm=0;
async function abrirNoSaitama(url){
  const agora=Date.now();if(url===ultimo&&agora-ultimoEm<1500)return;ultimo=url;ultimoEm=agora;
  aviso('Abrindo no Saitama…');
  try{const r=await fetch('/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url}),signal:AbortSignal.timeout(20000)});
    const d=await r.json().catch(()=>({}));
    aviso(d.ok?('Aberto no Saitama'+(d.app&&d.app!=='navegador'?' ('+d.app+')':'')):(d.error||'Não foi possível abrir no Saitama'))}
  catch{aviso('Não consegui conectar ao Saitama')}}
window.abrirNoSaitama=abrirNoSaitama;
function clique(doc){return e=>{
  const a=e.target&&e.target.closest?e.target.closest('a[href]'):null;if(!a)return;
  const url=alvo(a.getAttribute('href'),doc.baseURI);if(!url)return;
  e.preventDefault();e.stopImmediatePropagation();abrirNoSaitama(url)}}
function instalar(win){try{
  if(!win||win.__abrirLocalInstalado)return;const doc=win.document;win.__abrirLocalInstalado=true;
  win.addEventListener('click',clique(doc),true);
  win.addEventListener('auxclick',clique(doc),true);
  const nativo=win.open.bind(win);
  win.open=function(url,target,features){const u=alvo(String(url||''),doc.baseURI);if(u){abrirNoSaitama(u);return null}return nativo(url,target,features)};
}catch{/* iframe de outra origem ou sandbox: não há como mexer, e ele não abre abas no celular */}}
instalar(window);
function vigiar(frame){if(frame.__abrirLocalVigiado)return;frame.__abrirLocalVigiado=true;
  frame.addEventListener('load',()=>{try{instalar(frame.contentWindow)}catch{}});
  try{if(frame.contentDocument&&frame.contentDocument.readyState==='complete')instalar(frame.contentWindow)}catch{}}
document.querySelectorAll('iframe').forEach(vigiar);
new MutationObserver(ms=>{for(const m of ms)for(const n of m.addedNodes){
  if(n.nodeType!==1)continue;if(n.tagName==='IFRAME')vigiar(n);else if(n.querySelectorAll)n.querySelectorAll('iframe').forEach(vigiar)}})
  .observe(document.documentElement,{childList:true,subtree:true});
})();
