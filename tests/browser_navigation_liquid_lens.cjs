const assert = require('node:assert/strict');
const verifyOptics = require('./test_navigation_liquid_lens.cjs');

module.exports = async ({page, login, admin}) => {
  verifyOptics();
  await login(admin);
  await page.emulateMedia({reducedMotion:'no-preference',forcedColors:'none'});
  const originalTheme = await page.locator('html').getAttribute('data-theme');
  await page.evaluate(() => {
    const raf = window.requestAnimationFrame, cancel = window.cancelAnimationFrame, pending = new Set();
    window.liquidQA = {node:document.getElementById('nav-selection-lens'),raf,cancel,pending,executed:0};
    window.requestAnimationFrame = callback => {
      const id = raf.call(window, time => {pending.delete(id);window.liquidQA.executed++;callback(time);});
      pending.add(id); return id;
    };
    window.cancelAnimationFrame = id => {pending.delete(id);cancel.call(window,id);};
  });
  const arrived = async id => {
    await page.waitForFunction(id => {
      const lens = document.getElementById('nav-selection-lens'), target = document.getElementById(id);
      const a = lens.getBoundingClientRect(), b = target.getBoundingClientRect();
      return !lens.hidden && target.getAttribute('aria-current') === 'page'
        && getComputedStyle(lens).willChange === 'auto'
        && ['x','y','width','height'].every(k => Math.abs(a[k]-b[k]) < .05)
        && !document.querySelector('.motion-enter,.is-theming') && window.liquidQA.pending.size === 0;
    }, id);
    const rest = await page.evaluate(() => {
      const lens = window.liquidQA.node, css = getComputedStyle(lens);
      return {count:document.querySelectorAll('.nav-selection-lens').length,
        same:lens === document.getElementById('nav-selection-lens'),
        dynamic:lens.getAttribute('style').includes('--liquid-'),
        rest:['stretch','bulge','offset','taper','rim','leading'].map(k => css.getPropertyValue('--liquid-'+k).trim()),
        pseudo:getComputedStyle(lens,'::before').content,pointer:css.pointerEvents,aria:lens.getAttribute('aria-hidden')};
    });
    assert.deepEqual(rest, {count:1,same:true,dynamic:false,rest:['1','1','0px','0px','0','50%'],pseudo:await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches)?'none':'""',pointer:'none',aria:'true'});
  };
  const start = async id => {
    await page.evaluate(() => {document.querySelector('.sidebar-nav').scrollTop=0;});
    if (!await page.locator('#app-sidebar').isVisible()) await page.locator('#menu-toggle').click();
    await page.locator('#'+id).click();
    if (!await page.locator('#app-sidebar').isVisible()) await page.locator('#menu-toggle').click();
    await arrived(id);
  };
  // This clock is test-only. Drain A2 measurement frames before taking over, as PR #96 requires.
  // Real scheduler/performance samples are collected separately, without this clock or layout reads.
  const travel = async (ids, {forced=false,opaque=false}={}) => {
    const result = await page.evaluate(async ids => {
      window.dispatchEvent(new Event('resize'));
      for(let n=0;n<10;n++) await new Promise(requestAnimationFrame);
      const nativeRaf=window.requestAnimationFrame,nativeCancel=window.cancelAnimationFrame;
      const pending=new Map();let serial=0;
      const lens=window.liquidQA.node;
      window.requestAnimationFrame=callback=>{pending.set(++serial,callback);return serial;};
      window.cancelAnimationFrame=id=>pending.delete(id);
      const read=time=>{
        const css=getComputedStyle(lens),body=getComputedStyle(lens,'::before'),rim=getComputedStyle(lens,'::after');
        return {time,box:lens.getBoundingClientRect().toJSON(),style:lens.getAttribute('style'),
          stretch:parseFloat(css.getPropertyValue('--liquid-stretch')),bulge:parseFloat(css.getPropertyValue('--liquid-bulge')),
          offset:parseFloat(css.getPropertyValue('--liquid-offset')),taper:parseFloat(css.getPropertyValue('--liquid-taper')),
          rim:parseFloat(css.getPropertyValue('--liquid-rim')),leading:parseFloat(css.getPropertyValue('--liquid-leading')),
          transform:body.transform,body:body.content,display:body.display,rimDisplay:rim.display,
          fill:body.backgroundColor,parentFill:css.backgroundColor,parentImage:css.backgroundImage,filter:css.backdropFilter,willChange:css.willChange,
          parent:lens.parentElement.className,clip:getComputedStyle(lens.parentElement).overflow,
          same:lens===document.getElementById('nav-selection-lens'),count:document.querySelectorAll('.nav-selection-lens').length};
      };
      const before=read(0),samples=[],selections=[];
      try {
        for(let n=0;n<85;n++){
          if(n%5===0 && n/5<ids.length){
            const id=ids[n/5];document.getElementById(id).click();
            selections.push([...document.querySelectorAll('#app-sidebar [aria-current]')].map(node=>node.id));
          }
          for(const [id,callback] of [...pending]){pending.delete(id);callback(1000+n*1000/60);}
          samples.push(read(n*1000/60));
        }
        return {before,samples,selections,pending:pending.size};
      } finally {
        window.requestAnimationFrame=nativeRaf;window.cancelAnimationFrame=nativeCancel;
        for(const callback of pending.values()) nativeRaf.call(window,callback);
      }
    }, ids);
    assert.deepEqual(result.selections,ids.map(id=>[id]),'semantics change synchronously, before any optical frame');
    assert.equal(result.pending,0,'the only spring clock settles');
    const flight=result.samples.filter(s=>s.stretch>1.001);
    assert.ok(flight.length>3,'several physically driven optical frames exist');
    for(const s of result.samples){
      assert.equal(s.same,true);assert.equal(s.count,1);assert.ok(!/NaN|Infinity/.test(s.style));
      assert.ok(s.stretch>=1 && s.stretch<=1.35 && s.bulge>=1 && s.bulge<=1.09);
      if(!s.parent.includes('sidebar-cta'))assert.equal(s.filter,'none','ordinary moving lens has no nested blur');
      if(s.stretch>1.001){
        assert.match(s.parentFill,/^rgba\(\d+, \d+, \d+, 0\)$/,'the parent cannot paint a second resting capsule');
        assert.equal(s.parentImage,'none','one persistent pseudo-element owns the body paint');
        assert.equal(s.filter,'none','even the approval filter is withdrawn while the optical body travels');
        assert.equal(Math.sign(s.offset),Math.sign(s.taper));
        assert.equal(Math.sign(s.offset),Math.sign(s.leading-50));
        if(forced)assert.equal(s.display,'none');
        else {assert.equal(s.body,'""');assert.notEqual(s.display,'none');assert.notEqual(s.transform,'none');}
        if(opaque||forced)assert.equal(s.rimDisplay,'none');
        if(opaque)assert.match(s.fill,/^rgb\(/,'reduced transparency body is solid');
        if(s.parent.includes('sidebar-cta'))assert.equal(s.clip,'visible','incoming optical envelope is not sliced at CTA');
      }
    }
    await arrived(ids.at(-1));
    return result;
  };
  for(const theme of ['light','dark']){
    await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    await start('command-center');
    const down=await travel(['board-home']);assert.ok(down.samples.some(s=>s.offset>0));
    const up=await travel(['command-center']);assert.ok(up.samples.some(s=>s.offset<0));
    const long=await travel(['products']);assert.ok(Math.max(...long.samples.map(s=>s.stretch))>=1.34);
    assert.ok(Math.max(...long.samples.map(s=>s.box.height*s.stretch))<long.before.box.height*1.445,
      'long travel stays in the bounded envelope, never bridges the entire distance');
    await travel(['command-center']);
    const reversal=await travel(['products','command-center']);
    assert.ok(reversal.samples.some(s=>s.offset>0)&&reversal.samples.some(s=>s.offset<0));
    assert.ok(reversal.samples[5].offset>0,'the old direction survives the first reversal frame');
    await travel(['workforce','products','materials','command-center']);
    const into=await travel(['approvals']);assert.match(into.samples[0].parent,/sidebar-cta/);
    assert.ok(Math.abs(into.before.box.y-into.samples[0].box.y)<.05,'rebase into CTA preserves viewport position');
    const out=await travel(['command-center']);assert.match(out.samples[0].parent,/^app-sidebar(?: |$)/);
    assert.ok(Math.abs(out.before.box.y-out.samples[0].box.y)<.05,'rebase out preserves viewport position');
    const crossing=await travel(['products','approvals','command-center']);
    assert.ok(crossing.samples[5].stretch>1.001&&crossing.samples[10].stretch>1.001,
      'optical deformation survives both mid-flight context changes');
  }
  await start('capacity-plan');
  assert.deepEqual(await page.locator('.nav-summary').evaluate(node=>({position:getComputedStyle(node).position,z:getComputedStyle(node).zIndex})),
    {position:'relative',z:'2'},'the analytics heading paints above the travelling lens');
  await travel(['production-quality-insights']);
  assert.equal(await page.locator('#analytics-view').evaluate(node=>node.classList.contains('motion-enter')),false,
    'analytics children do not replay their common host entry');
  await page.locator('.sidebar-nav').evaluate(node=>{node.scrollTop+=25;});await arrived('production-quality-insights');
  await start('materials');
  await page.locator('#materials').focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('#materials').evaluate(node=>getComputedStyle(node).outlineStyle),'solid');
  for(const width of [1440,1280,1024,981,980,768,390,320]){
    await page.setViewportSize({width,height:1000});
    if(!await page.locator('#app-sidebar').isVisible())await page.locator('#menu-toggle').click();
    await arrived('materials');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  }
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');await arrived('materials');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('#workforce').click();
  assert.equal(await page.locator('#app-sidebar').evaluate(node=>node.inert),true,'mobile navigation closes immediately');
  await page.locator('#menu-toggle').click();await arrived('workforce');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.emulateMedia({reducedMotion:'reduce'});await start('command-center');
  await page.evaluate(()=>document.getElementById('products').click());await arrived('products');
  assert.equal(await page.locator('#nav-selection-lens').evaluate(node=>getComputedStyle(node,'::after').content),'none');
  await page.emulateMedia({reducedMotion:'no-preference',forcedColors:'active'});
  await start('command-center');await travel(['products'],{forced:true});
  assert.equal(await page.locator('#nav-selection-lens').evaluate(node=>getComputedStyle(node).borderStyle),'solid');
  await page.emulateMedia({forcedColors:'none'});
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'},{name:'prefers-reduced-motion',value:'no-preference'}]});
  assert.equal(await page.evaluate(()=>matchMedia('(prefers-reduced-transparency: reduce)').matches),true);
  await start('command-center');await travel(['products'],{opaque:true});
  await travel(['approvals'],{opaque:true});await travel(['command-center'],{opaque:true});
  await cdp.send('Emulation.setEmulatedMedia',{features:[]});await cdp.detach();
  await page.emulateMedia({reducedMotion:'no-preference',forcedColors:'none'});
  await start('command-center');
  const quiet=await page.evaluate(()=>({executed:window.liquidQA.executed,pending:window.liquidQA.pending.size}));
  await page.waitForTimeout(160);
  assert.deepEqual(await page.evaluate(()=>({executed:window.liquidQA.executed,pending:window.liquidQA.pending.size})),quiet);
  assert.equal(quiet.pending,0,'zero idle RAF');
  await page.evaluate(theme=>{
    document.documentElement.dataset.theme=theme;
    window.requestAnimationFrame=window.liquidQA.raf;window.cancelAnimationFrame=window.liquidQA.cancel;delete window.liquidQA;
  },originalTheme);
  console.log('A5.3 liquid lens PASS: one node, bounded optical silhouette, both directions, momentum reversal, rapid retarget, CTA/rebase/clipping, analytics, focus, responsive/text zoom, fallbacks, exact rest, zero idle RAF.');
};
