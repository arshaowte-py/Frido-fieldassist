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
  const html=d.body.innerHTML;
  ['undefined','NaN','null','\\[object'].forEach(bad=>{
    const n=(html.match(new RegExp(bad,'g'))||[]).length;
    if(n) errs.push(`${n}x "${bad}" in output`);
  });
  // rep table interaction
  d.querySelectorAll('nav button')[2].click();
  const q=d.getElementById('uq');
  if(q){ q.value='a'; q.dispatchEvent(new w.Event('input')); console.log('  rep filter ->', d.getElementById('ucount').textContent); }
  const th=d.querySelectorAll('#utbl th')[5]; if(th){ th.click(); console.log('  sort click ok, rows=', d.querySelectorAll('#utbl tbody tr').length); }
  console.log(errs.length? '\nISSUES:\n'+errs.join('\n') : '\nno issues');
},400);
