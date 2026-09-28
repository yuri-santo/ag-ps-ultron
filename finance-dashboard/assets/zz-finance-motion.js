/* On-demand transitions for real Plotly 3D coordinates. No polling or idle render loop. */
(function () {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const cache = new Map(), cameras = new Map(), states = new WeakMap(), counters = new Map();
  const stats = window.financeMotion = {version: 1, started: 0, finished: 0, cancelled: 0, frames: 0, errors: 0};
  let monthNav=null;
  window.dash_clientside=Object.assign({},window.dash_clientside,{
    finance_motion:{navigate:function(p,n,h,current) {
      p=p||0;n=n||0;h=h||0;
      const now=new Date(),today=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0');
      current=/^\d{4}-\d{2}$/.test(current||'') ? current : today;
      if (!monthNav || p<monthNav.p || n<monthNav.n || h<monthNav.h) monthNav={p:0,n:0,h:0,value:current,input:current};
      if (!p&&!n&&!h) {monthNav.value=current;monthNav.input=current;return window.dash_clientside.no_update;}
      if (current!==monthNav.value && current!==monthNav.input) monthNav.value=current;
      const delta=(n-monthNav.n)-(p-monthNav.p),todayClick=h>monthNav.h;
      const parts=monthNav.value.split('-').map(Number),index=parts[0]*12+parts[1]-1+delta;
      const result=todayClick ? today : Math.floor(index/12)+'-'+String(((index%12)+12)%12+1).padStart(2,'0');
      monthNav={p,n,h,value:result,input:current};
      return result;
    }}
  });
  const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  const visible = el => {const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight;};
  const fingerprint = gd => JSON.stringify([gd.layout?.meta?.motion, gd.data?.map(t => [t.uid,t.x,t.y,t.z,t.vertexcolor,t.color])]);
  const snapshot = gd => ({signature: fingerprint(gd), traces: clone(gd.data), period: gd.layout.meta.motion.period});
  const trim = map => {while (map.size > 45) map.delete(map.keys().next().value);};
  const ease = t => 1 - Math.pow(1-t,3);

  function origin(previous, target) {
    const byId = new Map((previous?.ids || []).map((id,i) => [String(id),i]));
    const compatible = previous && previous.type === target.type;
    const out = {};
    for (const axis of ['x','y','z']) {
      const values = target[axis];
      if (!Array.isArray(values)) continue;
      // A topology change gets a depth entrance; triangles never connect unrelated sectors.
      const sameTopology = compatible && (!target.i || JSON.stringify(previous.i) === JSON.stringify(target.i));
      out[axis] = values.map((v,i) => {
        if (Array.isArray(v)) return v.map((n,j) => compatible && previous[axis]?.[i]?.[j] != null ? previous[axis][i][j] : (axis==='z' ? 0 : n));
        if (v === null) return null;
        let at = target.ids && byId.size ? byId.get(String(target.ids[i])) : i;
        const old = sameTopology && at !== undefined ? previous[axis]?.[at] : undefined;
        return typeof old === 'number' ? old : (axis === 'z' ? 0 : v);
      });
    }
    return out;
  }
  function tween(from, to, t) {
    if (t>=1) return clone(to); // Exact selected-month geometry; no accumulated rounding.
    return to.map((v,i) => Array.isArray(v) ? tween(from[i] || [], v, t) :
      (typeof v === 'number' && typeof from[i] === 'number' ? from[i]+(v-from[i])*t : v));
  }
  async function change(gd) {
    const meta = gd.layout?.meta?.motion;
    if (meta?.readable && gd.data) {
      const signature=JSON.stringify([meta.period,gd.data.map(t=>[t.uid,t.x,t.y,t.values,t.z])]);
      const previous=states.get(gd);
      if(previous?.signature===signature)return;
      states.set(gd,{signature,period:meta.period});
      gd.dataset.motionPeriod=String(meta.period||'');gd.dataset.motionState='complete';
      if(previous && !reduced.matches && !document.hidden && visible(gd)) {
        const layer=gd.querySelector('.cartesianlayer') || gd.querySelector('.pielayer');
        if(layer) {
          layer.getAnimations().forEach(animation=>animation.cancel());
          const animation=layer.animate([{opacity:.3,transform:'translateY(7px)'},{opacity:1,transform:'translateY(0)'}],{duration:420,easing:'cubic-bezier(.2,.7,.25,1)'});
          stats.started++;animation.finished.then(()=>stats.finished++).catch(()=>stats.cancelled++);
        }
      }
      return;
    }
    if (!meta?.spatial || !window.Plotly || !gd.data) return;
    let state = states.get(gd);
    if (!state) {state={token:0, busy:false, signature:null}; states.set(gd,state);}
    if (state.busy) {
      if (meta.period === state.period && meta.key === state.key) return;
      state.token++; state.busy=false; stats.cancelled++;
    }
    const target = snapshot(gd), key = String(meta.key);
    if (state.signature === target.signature) return;
    state.signature = target.signature;
    const previous = cache.get(key);
    cache.set(key,target); trim(cache);
    if (cameras.has(key)) {
      state.busy=true; state.period=meta.period; state.key=key;
      try {await Plotly.relayout(gd, {'scene.camera': cameras.get(key)});} catch (_) {stats.errors++;}
      state.busy=false;
    }
    if (!previous || !previous.traces?.length || reduced.matches || document.hidden || !visible(gd)) return;
    if (previous.signature===target.signature) return;
    if (JSON.stringify(previous.traces.map(t=>[t.uid,t.x,t.y,t.z]))===JSON.stringify(target.traces.map(t=>[t.uid,t.x,t.y,t.z]))) return;
    const old = new Map(previous.traces.map((t,i) => [t.uid || String(i),t]));
    const starts = target.traces.map((t,i) => origin(old.get(t.uid || String(i)),t));
    const indices = target.traces.map((_,i) => i);
    if (!indices.length) {gd.closest('.dash-graph')?.animate([{opacity:.2},{opacity:1}],{duration:450}); return;}
    const token = ++state.token;
    state.busy=true; state.period=meta.period; state.key=key;
    gd.dataset.motionState='running'; stats.started++;
    let started=performance.now();
    try {
      // Sequential awaited updates cap work to ~14 frames/s, without queued GPU redraws.
      for (let frame=0; frame<=12; frame++) {
        if (token!==state.token || !gd.isConnected || gd.layout?.meta?.motion?.period!==meta.period) {stats.cancelled++; return;}
        const done = document.hidden || reduced.matches || !visible(gd);
        const progress = done ? 1 : Math.min(1,(performance.now()-started)/850);
        const t = frame===12 ? 1 : ease(progress);
        const update = {};
        for (const axis of ['x','y','z']) update[axis] = target.traces.map((tr,i) => Array.isArray(tr[axis]) ? tween(starts[i][axis] || [],tr[axis],t) : null);
        // Hover data always shows the selected month's exact number during the transition.
        await Plotly.restyle(gd, update, indices);
        stats.frames++;
        if (t>=1) break;
        await new Promise(resolve => setTimeout(resolve,60));
      }
      if (token===state.token && gd.isConnected) {
        gd.dataset.motionState='complete'; gd.dataset.motionPeriod=String(meta.period || ''); stats.finished++;
      }
    } catch (_) {stats.errors++; gd.dataset.motionState='fallback';}
    finally {
      if (token===state.token) {state.busy=false; schedule();}
    }
  }
  function attach(gd) {
    if (gd.dataset.motionBound || typeof gd.on!=='function') return;
    gd.dataset.motionBound='1';
    gd.on('plotly_afterplot', () => change(gd));
    gd.on('plotly_relayout', event => {
      const key=gd.layout?.meta?.motion?.key;
      if (key && event['scene.camera']) {cameras.set(String(key),clone(event['scene.camera'])); trim(cameras);}
    });
    change(gd);
  }
  function kpis() {
    document.querySelectorAll('.glass-card-kpi h4').forEach(el => {
      const text=el.textContent;
      if (el.dataset.motionText===text) return;
      el.dataset.motionText=text;
      const match=text.match(/^([^\d-]*)(-?[\d.,]+)(.*)$/);
      if (!match || /\d/.test(match[3])) return;
      const raw=match[2], comma=raw.lastIndexOf(','), dot=raw.lastIndexOf('.');
      const decimal=comma>dot ? ',' : '.';
      const numeric=Number(raw.replace(decimal===',' ? /\./g : /,/g,'').replace(',','.'));
      if (!Number.isFinite(numeric)) return;
      const label=el.closest('.glass-card-kpi')?.querySelector('span')?.textContent;
      const key=location.pathname+'|'+String(label).replace(/\(?20\d{2}-\d{2}\)?/g,'').trim(), previous=counters.get(key); counters.set(key,numeric); trim(counters);
      if (previous===undefined || previous===numeric || reduced.matches || !visible(el)) return;
      const places=raw.includes(decimal) ? raw.split(decimal).pop().length : 0;
      const start=performance.now();
      function frame(now) {
        if (!el.isConnected || el.textContent!==text || reduced.matches || document.hidden) {el.removeAttribute('data-motion-value');return;}
        const t=Math.min(1,(now-start)/650);
        el.dataset.motionValue=match[1]+(previous+(numeric-previous)*ease(t)).toLocaleString(decimal===','?'pt-BR':'en-US',{minimumFractionDigits:places,maximumFractionDigits:places})+match[3];
        if (t<1) requestAnimationFrame(frame); else el.removeAttribute('data-motion-value');
      }
      requestAnimationFrame(frame);
    });
  }
  let queued=false, lastLabel='', pageNode=null;
  function scan() {
    queued=false;
    document.querySelectorAll('.js-plotly-plot').forEach(gd => {attach(gd); if(!states.get(gd)?.busy) change(gd);});
    const page=document.getElementById('page'), label=document.getElementById('mes-label')?.textContent || '';
    if (page && (label!==lastLabel || page.firstElementChild!==pageNode)) {
      if (lastLabel && !reduced.matches) page.animate([{opacity:.55,transform:'perspective(1500px) translateY(12px) rotateX(1deg)',filter:'blur(1.5px)'},{opacity:1,transform:'none',filter:'blur(0px)'}],{duration:560,easing:'cubic-bezier(.2,.7,.25,1)'});
      pageNode=page.firstElementChild;lastLabel=label;
    }
    kpis();
  }
  function schedule() {if (!queued) {queued=true; requestAnimationFrame(scan);}}
  new MutationObserver(records => {
    if (records.some(r => !r.target.closest?.('.js-plotly-plot'))) schedule();
  }).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  document.addEventListener('DOMContentLoaded',schedule);
  document.addEventListener('visibilitychange',schedule);
  schedule();
})();
