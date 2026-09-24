const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async ({page, login, admin, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work, rows = [];
  await login(admin);
  await page.emulateMedia({reducedMotion:'reduce',forcedColors:'none'});
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('#command-center').click();
  await page.locator('#command-center-content:not([hidden])').waitFor();
  const nav = page.locator('.sidebar-nav');
  const read = () => page.evaluate(() => {
    const box = selector => document.querySelector(selector).getBoundingClientRect().toJSON();
    const nav = document.querySelector('.sidebar-nav'), copy = document.querySelector('.sidebar-cta-copy');
    const tail = nav.querySelector('.nav-group-tail');
    return {viewport:[innerWidth,innerHeight],theme:document.documentElement.dataset.theme,
      card:box('.sidebar-cta'),button:box('#approvals'),nav:box('.sidebar-nav'),sidebar:box('#app-sidebar'),
      navClient:nav.clientHeight,navScroll:nav.scrollHeight,navTop:nav.scrollTop,
      businessGap:tail.getBoundingClientRect().top-tail.previousElementSibling.getBoundingClientRect().bottom,
      purchase:box('#purchase-requests'),marketing:box('#marketing-budgets'),
      sidebarTop:document.querySelector('#app-sidebar').scrollTop,
      copyLines:copy.getBoundingClientRect().height / parseFloat(getComputedStyle(copy).lineHeight),
      scrollbar:getComputedStyle(nav).scrollbarWidth,overflow:getComputedStyle(nav).overflowY,
      document:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],
      mainScrollbar:getComputedStyle(document.querySelector('.workspace-main')).overflowY};
  });
  const verify = async label => {
    const row = await read();rows.push({label,...row});
    assert.ok(row.nav.bottom <= row.card.top,`${label}: nav ends above card`);
    assert.ok(row.card.bottom <= row.sidebar.bottom,`${label}: card stays inside sidebar`);
    assert.ok(row.sidebar.bottom <= row.viewport[1],`${label}: sidebar stays in viewport`);
    assert.equal(row.sidebarTop,0,`${label}: sidebar itself never scrolls`);
    assert.ok(Math.abs(row.businessGap)<1,`${label}: business destinations keep their original spacing after the previous group`);
    assert.equal(row.scrollbar,'none');assert.equal(row.overflow,'auto');assert.equal(row.mainScrollbar,'auto');
    assert.ok(row.document[0] <= row.viewport[0] && row.document[1] <= row.viewport[1],`${label}: no document overflow ${JSON.stringify(row)}`);
    assert.ok(row.copyLines <= 2.01,`${label}: supporting copy stays within two lines`);
    assert.ok(row.button.height >= (row.viewport[0] <= 980 ? 44 : 32));
    return row;
  };
  const capture = name => page.screenshot({path:path.join(shots,`${name}.png`)});
  for (const theme of ['light','dark']) {
    if(await page.locator('html').getAttribute('data-theme') !== theme)await page.locator('#theme').click();
    for(const [width,height] of [[1440,1000],[1280,800],[1024,768],[768,768],[1440,600],[1024,480]]) {
      await page.setViewportSize({width,height});
      if(!await page.locator('#app-sidebar').isVisible())await page.locator('#menu-toggle').click();
      await page.locator('.nav-collapse').evaluate(node=>{node.open=false;});
      await nav.evaluate(node=>{node.scrollTop=0;});
      await verify(`${theme}-${width}-${height}`);
      if(width===1440 && height===1000){
        await capture(`normal-${theme}`);
        await page.locator('.sidebar-cta').screenshot({path:path.join(shots,`card-${theme}.png`)});
      }
      await page.locator('.nav-collapse').evaluate(node=>{node.open=true;});
      const pinned = (await read()).card;
      await nav.hover();await page.mouse.wheel(0,2000);
      await page.waitForFunction(()=>document.querySelector('.sidebar-nav').scrollTop>0);
      await nav.evaluate(node=>{node.scrollTop=node.scrollHeight;});
      const scrolled = await verify(`${theme}-${width}-${height}-scrolled`);
      assert.equal(scrolled.card.y,pinned.y);assert.equal(scrolled.card.height,pinned.height);
      await page.locator('#marketing-budgets').focus();
      await page.keyboard.press('Shift+Tab');await page.keyboard.press('Tab');
      const focus = await page.locator('#marketing-budgets').evaluate(node=>{
        const r=node.getBoundingClientRect(),n=node.closest('nav').getBoundingClientRect(),s=getComputedStyle(node);
        return {visible:node.matches(':focus-visible'),outline:s.outlineStyle,inside:r.top-4>=n.top && r.bottom+4<=n.bottom};
      });
      assert.deepEqual(focus,{visible:true,outline:'solid',inside:true});
      await page.mouse.move(width-40,90);
      if(width===1440&&height===600)await capture(`short-scrolled-${theme}`);
      if(theme==='light'&&width!==1440)await capture(`responsive-${width}-${height}`);
    }
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('#theme').click();
  await nav.evaluate(node=>{node.scrollTop=0;});
  await page.locator('#command-center').focus();await page.keyboard.press('PageDown');
  await page.waitForFunction(()=>document.querySelector('.sidebar-nav').scrollTop>0);
  await page.locator('.nav-collapse').evaluate(node=>{node.open=false;});
  await nav.evaluate(node=>{node.scrollTop=0;});
  const normal = await read();
  await page.evaluate(()=>{window.utilityFullscreen=document.documentElement.requestFullscreen;document.documentElement.requestFullscreen=()=>Promise.reject(new Error('QA fallback'));});
  await page.locator('#window-fullscreen').click();
  const maximized = await verify('maximized');
  assert.equal(maximized.card.height,normal.card.height);
  await capture('maximized');
  await page.locator('#window-fullscreen').click();
  assert.deepEqual((await read()).card,normal.card,'restore returns exact card geometry');
  await page.evaluate(()=>{document.documentElement.requestFullscreen=window.utilityFullscreen;delete window.utilityFullscreen;});
  await page.locator('#window-fullscreen').click();
  assert.equal(await page.evaluate(()=>Boolean(document.fullscreenElement)),true);
  await verify('native-fullscreen');await capture('fullscreen');
  await page.evaluate(()=>document.exitFullscreen());
  await page.waitForFunction(()=>!document.querySelector('#workspace-window').classList.contains('is-maximized'));
  assert.deepEqual((await read()).card,normal.card);
  await page.locator('#approvals').focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>document.querySelector('#approvals').getAttribute('aria-current')==='page');
  assert.equal(await page.locator('#approvals').getAttribute('aria-current'),'page');
  await page.locator('#command-center').click();
  await page.locator('#command-center-content:not([hidden])').waitFor();
  await page.locator('.workspace-main').hover();await page.mouse.wheel(0,500);
  await page.waitForFunction(()=>document.querySelector('.workspace-main').scrollTop>0);
  assert.equal((await read()).card.y,normal.card.y);
  assert.equal(await page.evaluate(()=>scrollY),0);
  fs.writeFileSync(path.join(shots,'measurements.json'),JSON.stringify(rows,null,2));
  console.log('Sidebar utility PASS: pinned footer, isolated hidden nav scroll, keyboard focus, CTA action, light/dark, responsive and native/fallback fullscreen.',JSON.stringify(rows.map(r=>({label:r.label,card:r.card.height,nav:r.navClient}))));
};
