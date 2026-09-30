const S = { tab:'project', pid:null, data:null, risks:null, detail:null, busy:false, health:null, csv:null };
const $ = (h) => { const d=document.createElement('div'); d.innerHTML=h.trim(); return d.firstChild; };
const esc = (s)=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const SHAPE = {HIGH:'▲', MEDIUM:'◆', LOW:'●', INSUFFICIENT_EVIDENCE:'■'};
const WORD  = {HIGH:'High', MEDIUM:'Medium', LOW:'Low', INSUFFICIENT_EVIDENCE:'Insufficient evidence'};
const band = (b)=> b ? `<span class="band b-${b}"><span class="sh">${SHAPE[b]||''}</span>${WORD[b]||esc(b)}</span>` : '<span class="sub">not set</span>';

async function api(url, opts){ const r = await fetch(url, opts); const j = await r.json().catch(()=>({})); if(!r.ok) throw Object.assign(new Error(j.detail||j.error||r.status),{payload:j}); return j; }

const TABS = [['project','Project'],['overview','Overview'],['outlook','Outlook'],['evidence','Evidence'],['register','Risk register'],['suggested','Suggested'],['compare','What changed']];
function nav(){
  document.getElementById('nav').innerHTML = TABS.map(([k,l])=>
    `<button class="${S.tab===k?'on':''}" data-t="${k}" ${!S.pid&&k!=='project'?'disabled style="opacity:.4"':''}>${l}</button>`).join('');
  document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{ if(b.disabled)return; S.tab=b.dataset.t; S.detail=null; render(); });
}

function render(){
  nav();
  const m = document.getElementById('app');
  m.innerHTML='';
  if(S.tab==='project') return m.append(viewProject());
  if(!S.data) { m.innerHTML='<div class="empty">Pick or save a project first.</div>'; return; }
  if(S.detail) return m.append(viewDetail());
  if(S.tab==='overview') return m.append(viewOverview());
  if(S.tab==='outlook')  return m.append(viewOutlook());
  if(S.tab==='evidence') return m.append(viewEvidence());
  if(S.tab==='register') return m.append(viewRegister());
  if(S.tab==='suggested') return m.append(viewSuggested());
  if(S.tab==='compare')  return m.append(viewCompare());
}

/* ---------- project ---------- */
function viewProject(){
  const p = S.data?.project || {};
  const h = $(`<div>
    <div class="card"><h2>Search capability</h2><div id="hz" class="sub">checking…</div></div>
    <div class="card"><h2>Proposed project</h2>
      <div class="sub" style="margin-bottom:10px">Example inputs only. These do not describe a real company or a real scheme.</div>
      <div class="grid">
        <div><label>Project name</label><input id="f_name" value="${esc(p.name||'Proposed UK data centre')}"></div>
        <div><label>UK location</label><input id="f_location" value="${esc(p.location||'Slough, Berkshire')}"></div>
        <div><label>Capacity (MW)</label><input id="f_capacity_mw" type="number" value="${p.capacity_mw??120}"></div>
        <div><label>Cooling approach</label><select id="f_cooling">
          ${['evaporative (water)','closed loop liquid','air cooled'].map(c=>`<option ${p.cooling===c?'selected':''}>${c}</option>`).join('')}
        </select></div>
        <div><label>Expected grid demand (MW)</label><input id="f_grid_demand_mw" type="number" value="${p.grid_demand_mw??110}"></div>
        <div><label>Nearest homes (metres)</label><input id="f_residential_m" type="number" value="${p.residential_m??400}"></div>
      </div>
      <label>Project context</label><textarea id="f_context">${esc(p.context||'Greenfield site, existing 132kV substation 2km away, local campaign group already active.')}</textarea>
      <div class="row" style="margin-top:14px">
        <button class="act ghost" id="save">${S.pid?'Update project':'Save project'}</button>
        <button class="act" id="run" ${S.pid?'':'disabled'}>\u25B6 Run the search</button>
        <span id="runmsg" class="sub"></span>
      </div>
      <div class="sub" style="margin-top:9px">Save the project, then run the search. It queries all five planning concerns live, resolves every link to its publisher, and writes a review you can open on the other tabs.</div>
      <div id="runbox"></div>
    </div>
    <div class="card"><h2>Saved projects</h2><div id="plist" class="sub">…</div></div>
  </div>`);
  setTimeout(async()=>{
    try{ const hz = S.health || (S.health = await api('/api/health'));
      document.getElementById('hz').innerHTML = hz.ok
        ? `<span style="color:var(--cyan);font-weight:600">Connected</span> — Gemini <code>${esc(hz.model)}</code> with Google Search grounding. Sources are retrieved live and every link is resolved to the publisher before it is stored.`
        : `<div class="warn"><b>Live search is not available, so no findings will be shown.</b><br>${esc(hz.reason)}</div>`;
    }catch(e){ document.getElementById('hz').innerHTML = `<div class="warn">Could not reach the API: ${esc(e.message)}</div>`; }
    const ps = await api('/api/projects');
    document.getElementById('plist').innerHTML = ps.length? ps.map(x=>`<div class="rowline" data-p="${x.id}"><div><b>${esc(x.name)}</b><div class="meta">${esc(x.location)} · ${x.capacity_mw}MW · saved ${esc((x.created_at||'').slice(0,10))}</div></div><span class="sub">open →</span></div>`).join('') : '<span class="sub">none yet</span>';
    document.querySelectorAll('[data-p]').forEach(el=>el.onclick=async()=>{ S.pid=+el.dataset.p; S.data=await api('/api/projects/'+S.pid); S.tab='overview'; render(); });
  });
  h.querySelector('#save').onclick = async()=>{
    const body = {id:S.pid, name:v('f_name'), location:v('f_location'), capacity_mw:+v('f_capacity_mw'),
      cooling:v('f_cooling'), grid_demand_mw:+v('f_grid_demand_mw'), residential_m:+v('f_residential_m'), context:v('f_context')};
    const r = await api('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    S.pid=r.id; S.data=await api('/api/projects/'+S.pid); render();
  };
  h.querySelector('#run').onclick = runReview;
  return h;
}
const v = (id)=>document.getElementById(id).value;

async function runReview(){
  const msg=document.getElementById('runmsg'); const btn=document.getElementById('run');
  btn.disabled=true; msg.innerHTML='<span class="spin"></span> searching five concerns, this takes a minute…';
  try{
    await api('/api/projects/'+S.pid+'/review',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({key:(localStorage.getItem('demokey')||'')})});
    S.data = await api('/api/projects/'+S.pid); S.tab='overview'; render();
  }catch(e){
    msg.innerHTML=''; btn.disabled=false;
    const locked = (e.payload||{}).error==='search_locked';
    document.getElementById('runbox').innerHTML = locked
      ? `<div class="note"><b>Live search is locked on this hosted demo.</b><br>${esc(e.message)}
         <div class="row" style="margin-top:8px"><input id="dk" placeholder="demo key" style="max-width:220px">
         <button class="act sm" id="dks">unlock</button></div></div>`
      : `<div class="warn"><b>Search failed, so nothing was saved.</b><br>${esc(e.message)}</div>`;
    const dks=document.getElementById('dks');
    if(dks) dks.onclick=()=>{ localStorage.setItem('demokey',document.getElementById('dk').value.trim()); runReview(); };
  }
}

/* ---------- overview ---------- */
function viewOverview(){
  const {project:p, assessments:a=[], changed} = S.data;
  const el = $(`<div>
    <div class="card"><h2>${esc(p.name)}</h2>
      <div class="sub">${esc(p.location)} · ${p.capacity_mw}MW · ${esc(p.cooling)} · grid ${p.grid_demand_mw}MW · homes ${p.residential_m}m</div>
      <div class="sub" style="margin-top:8px">${esc(p.context)}</div></div>
    ${!a.length?'<div class="card"><div class="empty">No review yet. Go to Project and press Run search.</div></div>':''}
    ${a.length?`<div class="card"><h2>Planning concerns, most worth your attention first</h2>
      <div class="sub" style="margin-bottom:6px">Impact and likelihood are assessed separately and never combined into one score. Impact comes from your project inputs. Likelihood comes only from comparable planning decisions found.</div>
      ${a.map(x=>`<div class="rowline" data-c="${esc(x.concern)}">
        <div><b style="text-transform:capitalize">${esc(x.concern)}</b>
          <div class="meta">${x.leads_found||0} decision lead(s) found · ${x.decisions_found} outcome(s) you have confirmed</div></div>
        <div class="bands"><span class="sub" style="font-size:11px">impact</span>${band(x.impact_band)}
        <span class="sub" style="font-size:11px">likelihood</span>${band(x.likelihood_band)}</div></div>`).join('')}
      </div>`:''}
    ${a.some(x=>x.insufficient)?`<div class="card"><h2>Needs attention</h2>
      <div class="note">${a.filter(x=>x.insufficient).length} concern(s) have too little evidence to judge likelihood. That is an evidence gap to close, not a low risk. Chase the planning authority's own decisions on: ${a.filter(x=>x.insufficient).map(x=>esc(x.concern)).join(', ')}.</div></div>`:''}
    ${changed?`<div class="card"><h2>What changed</h2>${changed.has_prior
      ? `<div class="sub">${changed.new.length} new source(s), ${changed.gone.length} no longer returned, ${changed.unchanged} unchanged since the previous review.</div>`
      : `<div class="note">${esc(changed.message)}</div>`}</div>`:''}
  </div>`);
  el.querySelectorAll('[data-c]').forEach(r=>r.onclick=()=>{ S.detail=r.dataset.c; render(); });
  return el;
}

/* ---------- risk detail ---------- */
function viewDetail(){
  const a = (S.data.assessments||[]).find(x=>x.concern===S.detail);
  const ev = (S.data.evidence||[]).filter(e=>e.concern===S.detail);
  const dec = ev.filter(e=>e.source_type==='planning_decision'||e.source_type==='reported_decision');
  const el = $(`<div>
    <div class="row" style="margin-bottom:12px"><button class="act ghost sm" id="back">← back</button>
      <b style="text-transform:capitalize">${esc(S.detail)}</b></div>
    <div class="card"><div class="row">
      <div><div class="sub">Impact, from your project inputs</div>${band(a.impact_band)}</div>
      <div style="margin-left:28px"><div class="sub">Likelihood, from comparable decisions</div>${band(a.likelihood_band)}</div></div>
      <div class="basis"><b>Why this impact</b><ul>${a.impact_basis.map(b=>`<li>${esc(b)}</li>`).join('')}</ul></div>
      <div class="basis"><b>Why this likelihood</b><ul>${a.likelihood_basis.map(b=>`<li>${esc(b)}</li>`).join('')}</ul></div>
      ${a.insufficient?'<div class="note"><b>Insufficient evidence is not low risk.</b> Too few comparable planning decisions were retrieved to say anything about likelihood. Treat this as a gap to close.</div>':''}
    </div>
    <div class="card"><h2>Comparison cases (${dec.length})</h2>
      <div class="sub">These are decision records and reports of decisions. A report in the press is a <b>lead</b>, not a decision: open it, check the authority's own page, then record the outcome. Only outcomes you confirm count towards likelihood.</div>
      ${dec.length?dec.map(e=>srcRow(e,true)).join(''):'<div class="empty">No comparable planning decision was retrieved. Nothing is assumed in its place.</div>'}</div>
    <div class="card"><h2>All evidence for this concern (${ev.length})</h2>${ev.length?ev.map(e=>srcRow(e,true)).join(''):'<div class="empty">none</div>'}</div>
    <div class="card"><h2>Open questions</h2><ul class="sub">
      <li>Has the local authority published a decision on a comparable scheme that search did not return?</li>
      <li>Is there a local plan policy specific to this concern at ${esc(S.data.project.location)}?</li>
      <li>Which of these sources is a proposal or objection rather than a final decision?</li></ul></div>
  </div>`);
  el.querySelector('#back').onclick=()=>{ S.detail=null; render(); };
  el.querySelectorAll('[data-oc]').forEach(b=>b.onclick=async()=>{
    await api('/api/evidence/'+b.dataset.oc+'/outcome',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({outcome:b.dataset.ov})});
    S.data = await api('/api/projects/'+S.pid); render();
  });
  return el;
}
const OUTCOMES=['approved','refused','pending','withdrawn'];
const srcRow = (e, confirmable)=>`<div class="src">
  <a href="${esc(e.resolved_url)}" target="_blank" rel="noopener">${esc(e.title||e.resolved_url)}</a>
  <div class="meta">
    <span class="tag ${(e.source_type==='planning_decision'||e.source_type==='reported_decision')?'pd':''}">${esc((e.source_type||'unknown').replace(/_/g,' '))}</span>
    <span class="tag">${esc(e.claim_type||'').replace(/_/g,' ')}</span>
    ${esc(e.publisher||'')} · published ${e.published_date?esc(e.published_date):'not available'} · retrieved ${esc((e.retrieved_at||'').replace('T',' ').slice(0,16))}
  </div>
  ${(e.source_type==='planning_decision'||e.source_type==='reported_decision') ? (e.outcome_confirmed
     ? `<div class="meta"><b>Outcome: ${esc(e.outcome)}</b> (confirmed by you, counts towards likelihood)</div>`
     : (confirmable ? `<div class="row" style="margin-top:6px"><span class="sub" style="font-size:12px">Outcome not confirmed, so it does not count. Open the link, then record it:</span>
        ${OUTCOMES.map(o=>`<button class="act ghost sm" data-oc="${e.id}" data-ov="${o}">${o}</button>`).join('')}</div>`
       : `<div class="meta">Outcome not confirmed, so it does not count towards likelihood.</div>`)) : ''}
  </div>`;

/* ---------- evidence ---------- */
function viewEvidence(){
  const ev = S.data.evidence||[];
  const el = $(`<div class="card"><h2>Evidence (${ev.length})</h2>
    <div class="row" style="margin-bottom:10px">
      <select id="fc"><option value="">All concerns</option>${[...new Set(ev.map(e=>e.concern))].map(c=>`<option>${esc(c)}</option>`).join('')}</select>
      <select id="ft"><option value="">All source types</option>${[...new Set(ev.map(e=>e.source_type))].map(c=>`<option>${esc(c)}</option>`).join('')}</select>
    </div><div id="elist">${ev.map(srcRow).join('')||'<div class="empty">No evidence yet.</div>'}</div></div>`);
  const upd=()=>{ const c=el.querySelector('#fc').value, t=el.querySelector('#ft').value;
    el.querySelector('#elist').innerHTML = ev.filter(e=>(!c||e.concern===c)&&(!t||e.source_type===t)).map(srcRow).join('')||'<div class="empty">Nothing matches.</div>'; };
  el.querySelector('#fc').onchange=upd; el.querySelector('#ft').onchange=upd;
  return el;
}

/* ---------- register ---------- */
function viewRegister(){
  const el = $(`<div>
    <div class="card"><h2>Risk register</h2><div id="reg">loading…</div></div>
    <div class="card"><h2>Add a risk</h2>
      <div class="grid">
        <div><label>Category</label><input id="r_cat" value="Planning"></div>
        <div><label>Risk</label><input id="r_title" placeholder="Planning permission refused on grid capacity"></div>
        <div><label>Likelihood</label><select id="r_l">${['','LOW','MEDIUM','HIGH','INSUFFICIENT_EVIDENCE'].map(b=>`<option value="${b}">${b?WORD[b]:'not set'}</option>`).join('')}</select></div>
        <div><label>Impact</label><select id="r_i">${['','LOW','MEDIUM','HIGH','INSUFFICIENT_EVIDENCE'].map(b=>`<option value="${b}">${b?WORD[b]:'not set'}</option>`).join('')}</select></div>
      </div>
      <label>Existing mitigation</label><input id="r_m"><label>Notes</label><input id="r_n">
      <div style="margin-top:12px"><button class="act" id="addr">Add to register</button></div></div>
    <div class="card"><h2>Import a CSV risk register</h2>
      <div class="sub">Sample at <code>sample_risk_register.csv</code>, included only to demonstrate import.</div>
      <input type="file" id="csvf" accept=".csv" style="margin-top:10px"><div id="csvp"></div></div>
  </div>`);
  setTimeout(async()=>{ S.risks = await api(`/api/projects/${S.pid}/risks`); drawReg(el); });
  el.querySelector('#addr').onclick = async()=>{
    const t=el.querySelector('#r_title').value.trim(); if(!t) return;
    await api(`/api/projects/${S.pid}/risks`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({category:el.querySelector('#r_cat').value,title:t,likelihood_band:el.querySelector('#r_l').value,
      impact_band:el.querySelector('#r_i').value,mitigation:el.querySelector('#r_m').value,notes:el.querySelector('#r_n').value,origin:'manual',accepted:true})});
    S.risks = await api(`/api/projects/${S.pid}/risks`); el.querySelector('#r_title').value=''; drawReg(el);
  };
  el.querySelector('#csvf').onchange = (e)=>{ const f=e.target.files[0]; if(!f)return;
    const rd=new FileReader(); rd.onload=async()=>{ S.csv=rd.result;
      const pv = await api(`/api/projects/${S.pid}/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv:S.csv})});
      drawPreview(el, pv); }; rd.readAsText(f); };
  return el;
}
function drawReg(el){
  const rs = S.risks.register||[];
  el.querySelector('#reg').innerHTML = rs.length? `<table><tr><th>Category</th><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Mitigation</th><th>Origin</th><th></th></tr>
    ${rs.map(r=>`<tr><td>${esc(r.category)}</td><td>${esc(r.title)}</td><td>${band(r.likelihood_band)}</td><td>${band(r.impact_band)}</td><td>${esc(r.mitigation)}</td><td><span class="tag">${esc(r.origin)}</span></td><td><button class="act ghost sm" data-del="${r.id}">remove</button></td></tr>`).join('')}</table>`
    : '<div class="empty">Register is empty. Add a risk, import a CSV, or accept a suggestion.</div>';
  el.querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{ await api('/api/risks/'+b.dataset.del,{method:'DELETE'}); S.risks=await api(`/api/projects/${S.pid}/risks`); drawReg(el); });
}
function drawPreview(el, pv){
  const fields=[['title','Risk (required)'],['category','Category'],['likelihood','Likelihood'],['impact','Impact'],['mitigation','Mitigation'],['notes','Notes']];
  el.querySelector('#csvp').innerHTML = `<div class="basis"><b>${pv.row_count} row(s) found.</b> Map your columns before anything is imported.</div>
    <div class="grid">${fields.map(([k,l])=>`<div><label>${l}</label><select id="m_${k}"><option value="">— none —</option>${pv.columns.map(c=>`<option ${c.toLowerCase().includes(k)?'selected':''}>${esc(c)}</option>`).join('')}</select></div>`).join('')}</div>
    <table style="margin-top:12px"><tr>${pv.columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>
    ${pv.sample.map(r=>`<tr>${pv.columns.map(c=>`<td>${esc(r[c])}</td>`).join('')}</tr>`).join('')}</table>
    <div style="margin-top:12px"><button class="act" id="doimp">Import ${pv.row_count} row(s)</button></div>`;
  el.querySelector('#doimp').onclick = async()=>{
    const mapping={}; fields.forEach(([k])=>mapping[k]=el.querySelector('#m_'+k).value);
    const r = await api(`/api/projects/${S.pid}/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv:S.csv,mapping})});
    S.risks=await api(`/api/projects/${S.pid}/risks`); el.querySelector('#csvp').innerHTML=`<div class="basis">Imported ${r.imported} row(s).</div>`; drawReg(el);
  };
}

/* ---------- suggested ---------- */
function viewSuggested(){
  const el=$(`<div class="card"><h2>Suggested risks</h2>
    <div class="sub">Derived from search evidence. Nothing here is in your register until you accept it.</div>
    <div style="margin:12px 0"><button class="act ghost" id="gen">Generate from latest review</button></div>
    <div id="sg">loading…</div></div>`);
  const draw=async()=>{ S.risks=await api(`/api/projects/${S.pid}/risks`); const s=S.risks.suggested||[];
    el.querySelector('#sg').innerHTML = s.length? s.map(r=>`<div class="rowline"><div><b>${esc(r.title)}</b><div class="meta">${esc(r.notes)}</div></div>
      <div class="bands">${band(r.impact_band)}${band(r.likelihood_band)}<button class="act sm" data-acc="${r.id}">accept</button><button class="act ghost sm" data-del="${r.id}">dismiss</button></div></div>`).join('')
      : '<div class="empty">No suggestions pending.</div>';
    el.querySelectorAll('[data-acc]').forEach(b=>b.onclick=async()=>{ await api('/api/risks/'+b.dataset.acc+'/accept',{method:'POST'}); draw(); });
    el.querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{ await api('/api/risks/'+b.dataset.del,{method:'DELETE'}); draw(); });
  };
  setTimeout(draw);
  el.querySelector('#gen').onclick=async()=>{ await api(`/api/projects/${S.pid}/suggest`,{method:'POST'}); draw(); };
  return el;
}

/* ---------- outlook: the forward look ---------- */
const OSTATE = {
  BUILDING:{w:'Pressure building', sh:'\u25B2', c:'o-build'},
  PRESENT: {w:'Signal present',    sh:'\u25C6', c:'o-pres'},
  THIN:    {w:'Too thin to read',  sh:'\u25A0', c:'o-thin'},
  NO_SIGNAL:{w:'Nothing yet',      sh:'\u25CB', c:'o-none'}
};
function viewOutlook(){
  const el = $(`<div>
    <div class="card"><h2>What is building, before it becomes a decision</h2>
      <div class="sub">A refused application is the end of the story. This counts the public signal that runs ahead of it, and whether that signal is growing since the last review. It does not predict the decision.</div>
      <div id="ol" style="margin-top:14px">loading\u2026</div></div>
    <div class="card"><h2>What this is, and what it is not</h2>
      <div class="sub">Stated here so nothing in the demo implies more than it does.</div>
      <div id="gaps" style="margin-top:12px"></div></div>
  </div>`);
  setTimeout(async()=>{
    let d; try { d = await api(`/api/projects/${S.pid}/outlook`); }
    catch(e){ el.querySelector('#ol').innerHTML = '<div class="empty">Run a review first.</div>'; return; }
    el.querySelector('#ol').innerHTML = `<table>
      <tr><th>Concern</th><th>Signals now</th><th>Last review</th><th>Direction</th><th>Outlook</th></tr>
      ${d.outlook.map(o=>{
        const m = OSTATE[o.state] || OSTATE.THIN;
        const arrow = o.direction==='rising' ? '\u2197' : o.direction==='falling' ? '\u2198' : o.direction==='flat' ? '\u2192' : '\u2013';
        return `<tr>
          <td><b>${esc(o.concern)}</b><div class="meta">${esc(o.basis)}</div></td>
          <td style="font-variant-numeric:tabular-nums"><b>${o.signals_now}</b></td>
          <td style="font-variant-numeric:tabular-nums">${o.signals_prev===null?'<span class="sub">no baseline</span>':o.signals_prev}</td>
          <td>${arrow} ${esc(o.direction)}<div class="meta">${esc(o.note)}</div></td>
          <td><span class="band ${m.c}"><span class="sh">${m.sh}</span>${m.w}</span></td></tr>`;
      }).join('')}</table>
      <div class="basis" style="margin-top:14px">A signal is a petition, a campaign page, a consultation response or a council publication that our search returned and whose link resolved to a real publisher. Counting them is not the same as forecasting a decision.</div>`;
    el.querySelector('#gaps').innerHTML = d.gaps.map(g=>
      `<div class="rowline"><div><b>${g.have?'Built':'Not built'}</b> &nbsp; ${esc(g.item)}</div>
       <div class="bands"><span class="tag ${g.have?'t-yes':'t-no'}">${g.have?'in the prototype':'next'}</span></div></div>`).join('');
  });
  return el;
}

/* ---------- compare ---------- */
function viewCompare(){
  const c = S.data.changed;
  if(!c) return $('<div class="card"><div class="empty">Run a review first.</div></div>');
  if(!c.has_prior) return $(`<div class="card"><h2>What changed</h2><div class="note">${esc(c.message)}</div></div>`);
  return $(`<div><div class="card"><h2>New since last review (${c.new.length})</h2>${c.new.map(srcRow).join('')||'<div class="empty">none</div>'}</div>
    <div class="card"><h2>No longer returned (${c.gone.length})</h2>
      <div class="sub">A source dropping out of results is not evidence that anything changed on the ground.</div>
      ${c.gone.map(srcRow).join('')||'<div class="empty">none</div>'}</div>
    <div class="card"><h2>Unchanged</h2><div class="sub">${c.unchanged} source(s) returned in both reviews.</div></div></div>`);
}

(async function(){ try{ S.health=await api('/api/health'); }catch(e){} render(); })();
