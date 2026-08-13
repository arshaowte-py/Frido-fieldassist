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
   ['dist','q'],['vel','q'],['dbeat','q','d'],['zcov',null,'z'],['ws',null,'z'],['prod','q','c']]
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
  console.log(errs.length? '\nISSUES:\n'+errs.join('\n') : '\nno issues');
},400);
