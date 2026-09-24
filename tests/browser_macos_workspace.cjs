const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async ({page, login, admin, apiGet, work, populated = false}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  if (!populated) await login(admin);
  await page.setViewportSize({width:1440,height:1000});
  await page.emulateMedia({reducedMotion:'no-preference',forcedColors:'none'});
  const settle = () => page.waitForFunction(() => !document.querySelector('.motion-enter,.is-theming')
    && getComputedStyle(document.querySelector('#nav-selection-lens')).willChange === 'auto');
  const open = async () => {
    await page.locator('#command-center').click();
    await page.locator('#command-center-summary:not([aria-busy])').waitFor();
    await page.locator('#command-center-content:not([hidden])').waitFor();
    await page.locator('.nav-collapse').evaluate(node => { node.open = false; });
    await page.evaluate(() => { document.querySelector('#main').scrollTop = 0; window.scrollTo(0,0); });
    await settle();
  };
  const capture = name => page.screenshot({path:path.join(shots,`a52-${name}.png`)});
  await open();
  if (await page.locator('html').getAttribute('data-theme') === 'dark') await page.locator('#theme').click();
  await settle();
  assert.match(await page.evaluate(() => getComputedStyle(document.body,'::before').backgroundImage),/wallpaper-landscape.webp/);
  assert.equal(await page.locator('#connection-status').innerText(),'Online');
  assert.equal(await page.locator('#nav-selection-lens').count(),1);
  const before = await page.locator('#command-center-content').innerHTML();
  for (const [button,state] of [['window-close','closed'],['window-minimize','minimized']]) {
    await page.locator('#'+button).click();
    assert.equal(await page.locator('#workspace-window').isHidden(),true);
    assert.equal(await page.locator('#workspace-window').getAttribute('data-state'),state);
    assert.equal(await page.locator('#workspace-launcher').isVisible(),true);
    await capture(state);
    await page.locator('#window-restore').press('Enter');
    assert.equal(await page.locator('#command-center-content').innerHTML(),before);
    assert.equal(await page.locator('#command-center').getAttribute('aria-current'),'page');
    await settle();
  }
  await page.evaluate(() => { window.a52Fullscreen = document.documentElement.requestFullscreen; document.documentElement.requestFullscreen = () => Promise.reject(new Error('Denied by test')); });
  await page.locator('#window-fullscreen').click();
  assert.equal(await page.locator('#workspace-window').evaluate(node=>node.classList.contains('is-maximized')),true);
  await capture('maximized');
  await page.locator('#window-fullscreen').click();
  assert.equal(await page.locator('#workspace-window').evaluate(node=>node.classList.contains('is-maximized')),false);
  await page.evaluate(() => { document.documentElement.requestFullscreen = window.a52Fullscreen; delete window.a52Fullscreen; });
  await page.locator('#window-fullscreen').click();
  const nativeFullscreen = await page.evaluate(() => Boolean(document.fullscreenElement));
  if (nativeFullscreen) {
    await page.evaluate(() => document.exitFullscreen());
    await page.waitForFunction(() => !document.querySelector('#workspace-window').classList.contains('is-maximized'));
  } else await page.locator('#window-fullscreen').click();
  console.log('A5.2 native fullscreen supported:',nativeFullscreen);

  const search = page.locator('#navigation-search');
  await search.fill('Kualitas');
  await search.press('ArrowDown'); await search.press('Enter');
  await page.waitForFunction(() => document.querySelector('#production-quality-insights').getAttribute('aria-current') === 'page');
  await settle();
  await search.fill('no-destination-52');
  assert.match(await page.locator('#navigation-results').innerText(),/tidak ditemukan/);
  await search.press('Escape');
  assert.equal(await search.getAttribute('aria-expanded'),'false');
  await page.locator('#workspace-attention').click();
  await page.waitForFunction(() => document.activeElement.id === 'attention-title');
  await page.evaluate(() => { Object.defineProperty(navigator,'onLine',{value:false,configurable:true}); dispatchEvent(new Event('offline')); });
  assert.equal(await page.locator('#connection-status').innerText(),'Offline');
  await page.evaluate(() => { delete navigator.onLine; dispatchEvent(new Event('online')); });
  assert.equal(await page.locator('#connection-status').innerText(),'Online');
  await page.locator('#account-control').click();
  assert.match(await page.locator('#account-detail').innerText(),/admin/);
  await page.keyboard.press('Escape');
  await page.locator('#workspace-menu summary').click();
  await page.locator('#workspace-home').click();
  await page.locator('#command-center-summary:not([aria-busy])').waitFor();

  // A real persisted pending transaction must keep the shell visible, using the existing guard.
  const me = await apiGet('/api/me');
  await page.evaluate(actor => sessionStorage.setItem('beeloft.pending.'+actor.id,JSON.stringify({actor_id:actor.id,title:'A5.2 recovery check',
    transaction:{key:'a52-window-guard',path:'/api/products',body:{sku:'A52-NOT-SUBMITTED',name:'A5.2 guard'}}})),me);
  for (const id of ['window-close','window-minimize']) {
    await page.evaluate(id=>document.getElementById(id).click(),id);
    assert.equal(await page.locator('#workspace-window').isVisible(),true);
    assert.equal(await page.locator('#dialog-title').innerText(),'Konfirmasi pencatatan sebelumnya');
  }
  await page.evaluate(actor => sessionStorage.removeItem('beeloft.pending.'+actor.id),me);
  await page.reload();
  await page.locator('#summary:not([aria-busy]) dd').first().waitFor();
  await open();

  await page.locator('#appearance').click();
  await capture('background-picker');
  await page.locator('[data-wallpaper=mist]').click();
  await page.waitForFunction(()=>localStorage.getItem('beeloft.wallpaper')==='mist');
  await page.locator('#appearance-close').click();
  await capture('mist');
  await page.reload();
  await page.locator('#summary:not([aria-busy]) dd').first().waitFor();
  assert.equal(await page.locator('html').getAttribute('data-wallpaper'),'mist');
  await page.locator('#appearance').click();
  const upload = page.locator('#wallpaper-upload');
  for (const file of [
    {name:'bad.txt',mimeType:'text/plain',buffer:Buffer.from('not an image')},
    {name:'bad.png',mimeType:'image/png',buffer:Buffer.from('invalid image bytes')},
    {name:'large.png',mimeType:'image/png',buffer:Buffer.alloc(8*1024*1024+1)}]) {
    await upload.setInputFiles(file);
    await page.waitForFunction(()=>document.querySelector('#appearance-message').textContent.startsWith('Latar belum disimpan.'));
    assert.equal(await page.locator('html').getAttribute('data-wallpaper'),'mist');
  }
  await page.evaluate(()=>{ const revoke=URL.revokeObjectURL; window.a52Revoked=[]; URL.revokeObjectURL=url=>{window.a52Revoked.push(url);revoke(url);}; });
  await upload.setInputFiles(path.join(__dirname,'../beeloft/static/wallpaper-landscape.webp'));
  await page.waitForFunction(()=>document.documentElement.dataset.wallpaper==='custom');
  assert.equal(await page.evaluate(()=>localStorage.getItem('beeloft.wallpaper')),'custom');
  const oldURL=await page.locator('html').evaluate(node=>node.style.getPropertyValue('--workspace-wallpaper'));
  await page.locator('[data-wallpaper=mist]').click();
  await page.waitForFunction(()=>document.documentElement.dataset.wallpaper==='mist');
  assert.equal(await page.evaluate(url=>window.a52Revoked.some(value=>url.includes(value)),oldURL),true,'replaced object URL revoked');
  await upload.setInputFiles(path.join(__dirname,'../beeloft/static/wallpaper-landscape.webp'));
  await page.waitForFunction(()=>document.documentElement.dataset.wallpaper==='custom');
  await page.reload();
  await page.locator('#summary:not([aria-busy]) dd').first().waitFor();
  await page.waitForFunction(()=>document.documentElement.dataset.wallpaper==='custom');
  assert.match(await page.locator('html').getAttribute('style'),/blob:/);
  await page.locator('#appearance').click();
  await page.locator('#wallpaper-reset').click();
  await page.waitForFunction(()=>document.documentElement.dataset.wallpaper==='landscape');
  assert.doesNotMatch(await page.locator('html').getAttribute('style')||'',/blob:/);
  await page.locator('#appearance-close').click();
  await open();

  // Browser metrics count application RAF separately from the sampler used to measure frame gaps.
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  const metrics = async()=>Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m=>[m.name,m.value]));
  const performanceRows = [];
  await settle();
  await page.evaluate(()=>{
    window.a52Raf=requestAnimationFrame;window.a52Executed=0;window.a52Frames=[];
    window.requestAnimationFrame=fn=>window.a52Raf(t=>{window.a52Executed++;fn(t);});
  });
  const start=await metrics();
  await page.waitForTimeout(1200);
  const end=await metrics();
  assert.equal(await page.evaluate(()=>window.a52Executed),0,'CSS shimmer causes zero idle JS RAF');
  await page.evaluate(()=>{
    const tick=t=>{window.a52Frames.push(t);window.a52Sample=window.a52Raf(tick);};
    window.a52Sample=window.a52Raf(tick);
  });
  await page.waitForTimeout(1200);
  const frameMetrics=await page.evaluate(()=>{
    cancelAnimationFrame(window.a52Sample);
    const gaps=window.a52Frames.slice(1).map((t,i)=>t-window.a52Frames[i]).sort((a,b)=>a-b);
    return {frames:gaps.length,median:gaps[Math.floor(gaps.length*.5)],p95:gaps[Math.floor(gaps.length*.95)],max:gaps.at(-1)};
  });
  performanceRows.push({action:'idle shimmer',seconds:end.Timestamp-start.Timestamp,taskMs:(end.TaskDuration-start.TaskDuration)*1000,jsRaf:0,...frameMetrics});
  await page.evaluate(()=>{window.requestAnimationFrame=window.a52Raf;delete window.a52Raf;});
  const staticRim=await page.addStyleTag({content:'.app-sidebar::after{animation:none!important}'});
  const staticStart=await metrics();await page.waitForTimeout(1200);const staticEnd=await metrics();
  performanceRows.push({action:'idle static rim',seconds:staticEnd.Timestamp-staticStart.Timestamp,taskMs:(staticEnd.TaskDuration-staticStart.TaskDuration)*1000});
  await staticRim.evaluate(node=>node.remove());
  for (const [action,run] of [
    ['minimize/restore',async()=>{await page.locator('#window-minimize').click();await page.locator('#window-restore').click();}],
    ['fullscreen/restore',async()=>{await page.locator('#window-fullscreen').click();await page.locator('#window-fullscreen').click();}],
    ['search',async()=>{await search.fill('Produksi');await search.press('Escape');await search.fill('');await search.press('Escape');}],
    ['theme',async()=>{await page.locator('#theme').click();}],
    ['scroll',async()=>{await page.evaluate(()=>document.querySelector('#main').scrollTo(0,700));await page.evaluate(()=>document.querySelector('#main').scrollTo(0,0));}],
    ['nav spring',async()=>{await page.locator('#workforce').click();await open();}],
    ['background switch',async()=>{await page.locator('#appearance').click();await page.locator('[data-wallpaper=mist]').click();await page.waitForFunction(()=>document.documentElement.dataset.wallpaper==='mist');await page.locator('[data-wallpaper=landscape]').click();await page.waitForFunction(()=>document.documentElement.dataset.wallpaper==='landscape');await page.locator('#appearance-close').click();}]]) {
    const a=await metrics();await run();await settle();const b=await metrics();
    performanceRows.push({action,elapsedMs:(b.Timestamp-a.Timestamp)*1000,taskMs:(b.TaskDuration-a.TaskDuration)*1000,layoutMs:(b.LayoutDuration-a.LayoutDuration)*1000});
  }
  const navigation=await page.evaluate(()=>performance.getEntriesByType('navigation')[0].toJSON());
  performanceRows.push({action:'navigation',domContentLoadedMs:navigation.domContentLoadedEventEnd,loadMs:navigation.loadEventEnd});
  fs.writeFileSync(path.join(shots,'a52-performance.json'),JSON.stringify(performanceRows,null,2));
  for (const mode of ['light','dark']) {
    if(await page.locator('html').getAttribute('data-theme')!==mode)await page.locator('#theme').click();
    await settle();await capture('1440-'+mode);
  }
  await page.reload();await page.locator('#summary:not([aria-busy]) dd').first().waitFor();
  assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
  await open();await page.locator('#theme').click();await settle();
  for(const width of [1440,1280,1024,981,980,768,390,320]){
    await page.setViewportSize({width,height:width<650?844:1000});await settle();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow at ${width}`);
    await page.evaluate(()=>{window.scrollTo(0,0);document.querySelector('#main').scrollTop=0;});
    await capture(width+'-light');
    if(width===390){await page.locator('#theme').click();await settle();await capture('390-dark');await page.locator('#theme').click();}
  }
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');await settle();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'320 at 200%');
  await capture('320-200');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await page.locator('#app-sidebar').evaluate(node=>getComputedStyle(node,'::after').animationName),'none');
  await page.emulateMedia({forcedColors:'active'});
  assert.equal(await page.locator('#app-sidebar').evaluate(node=>getComputedStyle(node,'::after').display),'none');
  assert.equal(await page.locator('#window-close span').evaluate(node=>getComputedStyle(node).opacity),'1');
  await page.locator('#theme').click();
  const controlColor = await page.locator('.navigation-search').evaluate(node=>getComputedStyle(node).backgroundColor);
  assert.match(controlColor,/^rgb\(/,'dark forced-color search is solid');
  await page.emulateMedia({forcedColors:'none',reducedMotion:'no-preference'});
  await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'}]});
  assert.equal(await page.locator('#app-sidebar').evaluate(node=>getComputedStyle(node).backdropFilter),'none');
  assert.match(await page.locator('.navigation-search').evaluate(node=>getComputedStyle(node).backgroundColor),/^rgb\(/,'dark reduced-transparency search is solid');
  await page.locator('#theme').click();
  await cdp.send('Emulation.setEmulatedMedia',{features:[]});await cdp.detach();
  await page.locator('.nav-collapse').evaluate(node=>{node.open=true;});
  console.log('A5.2 workspace PASS: shell, recovery guard, fullscreen/fallback, search, connectivity, attention, presets/custom persistence, preferences, 8 widths, zero idle RAF.');
};
