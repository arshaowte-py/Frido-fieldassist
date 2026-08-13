const {JSDOM} = require('jsdom'); const fs=require('fs');
const dom = new JSDOM(fs.readFileSync('dist/index.html','utf8'),{runScripts:'dangerously'});
const w=dom.window, d=w.document;
const errs=[]; w.onerror=e=>errs.push(e);
setTimeout(()=>{
  const tabs=[...d.querySelectorAll('nav button')];
  console.log('tabs:', tabs.map(t=>t.textContent).join(' | '));
  tabs.forEach(t=>{ try{ t.click(); }catch(e){ errs.push(t.textContent+': '+e.message); } });
  tabs.forEach((t,i)=>{
    const p=d.querySelectorAll('.panel')[i];
    const len=p.innerHTML.length;
    console.log(`  ${t.textContent.padEnd(18)} ${String(len).padStart(6)} chars  tables=${p.querySelectorAll('table').length} bars=${p.querySelectorAll('.bar').length}`);
    if(len<400) errs.push('EMPTY PANEL: '+t.textContent);
  });
  // check for unresolved values
  const html=d.body.innerHTML.replace(/<script[\s\S]*?<\/script>/g,'');
  ['undefined','NaN','null','\\[object'].forEach(bad=>{
    const n=(html.match(new RegExp(bad,'g'))||[]).length;
    if(n) errs.push(`${n}x "${bad}" in output`);
  });
  // every filterable table: search, select and a sort click
  [['urep','q','z'],['mgr','q'],['askus','q','c'],['areps','q','m'],
   ['dist','q'],['vel','q'],['dbeat','q','d'],['zcov',null,'z'],['ws',null,'z'],['prod','q','c'],
   ['rrep','q'],['rout','q','s']]
  .forEach(([id,sq,ss])=>{
    if(!d.getElementById(id+'-t')) return;
    if(sq){ const e=d.getElementById(`${id}-${sq}`);
      if(e){ e.value='a'; e.dispatchEvent(new w.Event('input')); } else errs.push(`${id}: search missing`); }
    // selects on optional columns only render when the source export supplies them
    if(ss){ const e=d.getElementById(`${id}-${ss}`);
      if(e){ if(e.options.length<2) errs.push(`${id}: ${ss} select has no options`);
             else { e.value=e.options[1].value; e.dispatchEvent(new w.Event('change')); } } }
    const th=[...d.querySelectorAll(`#${id}-tbl th.sortable`)][0];
    if(th) th.click(); else errs.push(`${id}: no sortable column`);
    const n=d.querySelectorAll(`#${id}-tbl tbody tr`).length;
    console.log(`  ${id.padEnd(8)} filtered -> ${String(n).padStart(4)} rows  (${d.getElementById(id+'-n').textContent})`);
  });
  // ---- KPI trend arrows ----
  // top-level const/let are not window properties, so reach page scope via eval
  const px = expr => JSON.parse(w.eval(`JSON.stringify(${expr})`));
  // a partial final month must not be trended against a full one
  const T = px('TREND');
  if (!T) errs.push('TREND did not compute');
  else {
    const monthly = px('D.monthly').map(m=>m.month);
    if (T.partial.includes(T.cur.month)) errs.push('TREND compares a partial month');
    if (T.cur.month === T.prev.month) errs.push('TREND compares a month to itself');
    if (monthly.indexOf(T.cur.month) <= monthly.indexOf(T.prev.month))
      errs.push('TREND runs backwards');
    console.log(`  trend    ${T.prev.month} -> ${T.cur.month}   partial: ${T.partial.join(',')||'none'}`);
    d.querySelectorAll('nav button')[0].click();
    const pills = d.querySelectorAll('#p-overview .kpi .delta');
    if (!pills.length) errs.push('no trend pills rendered');
    console.log(`  arrows   ${pills.length} KPI deltas: ` +
      [...pills].map(p=>p.textContent.trim().replace(/\s+/g,'')).join(' '));
  }

  // ---- CSV export ----
  ['rout','dist'].forEach(id=>{
    if(!d.getElementById(id+'-t')) return;
    const csv = w.csvFor(id);
    const lines = csv.split('\n');
    const shown = w.ftableRows(id).length;
    if (lines.length - 1 !== shown)
      errs.push(`${id}: csv has ${lines.length-1} rows, table filtered to ${shown}`);
    // header count must match every body row's field count (quoting correctness)
    const cols = lines[0].split(',').length;
    const bad = lines.slice(1).findIndex(l =>
      (l.match(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/g)||[]).length + 1 !== cols);
    if (bad >= 0) errs.push(`${id}: csv row ${bad+1} has wrong field count`);
    console.log(`  csv      ${id.padEnd(6)} ${lines.length-1} rows x ${cols} cols`);
  });

  // ---- deep link + sticky filters ----
  if (d.getElementById('rout-s')) {
    // baseline under whatever filters the loop above left set, so the restore
    // assertion tests the sticky filter and not those
    const before = w.ftableRows('rout').length;
    w.eval('STICKY.seg="Churned"; syncSticky();');
    const segCol = [...d.querySelectorAll('#rout-tbl tbody tr')]
      .map(tr=>tr.children[1].textContent.trim());
    const leak = segCol.filter(v=>v!=='Churned');
    if (leak.length) errs.push(`sticky seg leaked ${leak.length} non-Churned rows`);
    if (!segCol.length) errs.push('sticky seg filtered everything out');
    // the select itself must move, not just the underlying rows
    if (d.getElementById('rout-s').value !== 'Churned')
      errs.push('sticky value did not reach the select');
    console.log(`  sticky   seg=Churned -> ${segCol.length} rows`);
    // clearing releases the shared filter but must leave the table's own
    // search box alone — the two are deliberately independent
    w.eval('STICKY.seg=""; syncSticky();');
    if (d.getElementById('rout-s').value !== '') errs.push('sticky clear left the select set');
    if (w.ftableRows('rout').length <= segCol.length)
      errs.push('clearing the sticky filter did not widen the result set');
    if (d.getElementById('rout-q').value !== 'a')
      errs.push('sticky clear wrongly reset the local search box');

    // regression: a link that omits a shared filter must CLEAR it rather than
    // inherit whatever the recipient already had set, or the link does not show
    // the sender's view.
    w.eval('STICKY.seg="Churned"; syncSticky();');
    w.eval('location.hash="#tab=outlets"; applyHash();');
    if (w.eval('STICKY.seg') !== '')
      errs.push('applyHash kept a filter the hash did not name');
    if (d.getElementById('rout-s').value !== '')
      errs.push('applyHash left a stale filter on the select');
    console.log('  hashreset ok — filter absent from the hash is released');
  }

  console.log(errs.length? '\nISSUES:\n'+errs.join('\n') : '\nno issues');
},400);
