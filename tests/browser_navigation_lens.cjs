const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, admin, viewer, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  await login(admin);
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.evaluate(() => {
    window.originalLens = document.getElementById('nav-selection-lens');
    const raf = window.requestAnimationFrame, cancel = window.cancelAnimationFrame;
    const pending = new Set();
    const frames = {executed:0, pending, raf, cancel};
    window.lensFrames = frames;
    window.requestAnimationFrame = callback => {
      const id = raf.call(window, time => { pending.delete(id); frames.executed++; callback(time); });
      pending.add(id); return id;
    };
    window.cancelAnimationFrame = id => { pending.delete(id); cancel.call(window, id); };
  });
  // A3 gave the lens physics, so "aligned" now means it has arrived *and* stopped: the target
  // rectangle plus the released compositor hint the controller only holds while a spring runs.
  // Every geometry assertion below therefore still describes the resting decoration A2 owns.
  const aligned = async id => {
    await page.waitForFunction(id => {
      const lens = document.getElementById('nav-selection-lens'), target = document.getElementById(id);
      if (lens.hidden || target.getAttribute('aria-current') !== 'page') return false;
      if (getComputedStyle(lens).willChange !== 'auto') return false;
      const a = lens.getBoundingClientRect(), b = target.getBoundingClientRect();
      return ['x','y','width','height'].every(key => Math.abs(a[key] - b[key]) < 1);
    }, id).catch(async error => {
      console.error('Lens geometry failure', await page.evaluate(id => {
        const lens = document.getElementById('nav-selection-lens'), target = document.getElementById(id);
        const sidebar = document.getElementById('app-sidebar');
        return {id, lens:lens.getBoundingClientRect().toJSON(), target:target.getBoundingClientRect().toJSON(),
          lensHidden:lens.hidden, context:lens.parentElement.className, sidebar:sidebar.getBoundingClientRect().toJSON(),
          scroll:sidebar.scrollTop, classes:sidebar.className, selected:target.getAttribute('aria-current')};
      }, id));
      throw error;
    });
    assert.equal(await page.locator('.nav-selection-lens').count(), 1);
    assert.equal(await page.evaluate(() => window.originalLens === document.getElementById('nav-selection-lens')), true);
    assert.equal(await page.locator('#app-sidebar [aria-current]').count(), 1);
    assert.deepEqual(await page.locator('#nav-selection-lens').evaluate(node => ({
      hidden:node.getAttribute('aria-hidden'), tab:node.tabIndex, text:node.textContent,
      pointer:getComputedStyle(node).pointerEvents, duration:getComputedStyle(node).transitionDuration,
      animations:node.getAnimations().length,
    })), {hidden:'true',tab:-1,text:'',pointer:'none',duration:'0s',animations:0});
  };
  const hidden = async () => {
    await page.waitForFunction(() => document.getElementById('nav-selection-lens').hidden
      && !document.getElementById('app-sidebar').classList.contains('nav-lens-ready'));
  };
  const open = async id => {
    if (!await page.locator('#app-sidebar').isVisible()) await page.locator('#menu-toggle').click();
    await page.locator('#'+id).click();
    if (!await page.locator('#app-sidebar').isVisible()) {
      await hidden();
      assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'false');
      assert.equal(await page.evaluate(() => document.activeElement === document.querySelector('.workspace-main>section:not([hidden]) h1')), true);
      await page.locator('#menu-toggle').click();
    }
    await aligned(id);
  };
  const settle = () => page.waitForFunction(() => !document.querySelector('.motion-enter,.is-theming')
    && document.getAnimations().every(animation => animation.animationName === 'sidebar-specular' || animation.playState === 'finished'));
  await page.locator('#board-home').scrollIntoViewIfNeeded();
  await aligned('board-home');
  for (const id of ['command-center','board-home','materials','workforce']) await open(id);
  const analyticsY = [];
  for (const id of ['wip-ageing-insights','capacity-plan','production-quality-insights']) {
    await open(id);
    assert.equal(await page.locator('.workspace-main>section:not([hidden])').getAttribute('id'), 'analytics-view');
    // A3 moves the lens with a transform rather than an inline `top`, so the resting position is
    // read from the rendered rectangle instead of the declaration that used to carry it.
    analyticsY.push(await page.locator('#nav-selection-lens').evaluate(node => Math.round(node.getBoundingClientRect().y)));
  }
  assert.equal(new Set(analyticsY).size, 3, 'same analytics host has three distinct lens targets');
  await page.locator('.nav-summary').click();
  await hidden();
  assert.equal(await page.locator('#production-quality-insights').getAttribute('aria-current'), 'page');
  await page.locator('.nav-summary').click();
  await aligned('production-quality-insights');

  // Navigation scrolls independently above the pinned CTA.
  for (const id of ['command-center','capacity-plan','marketing-budgets','approvals']) {
    await open(id);
    await page.locator('.sidebar-nav').evaluate(node => { node.scrollTop += node.scrollTop ? -20 : 20; });
    await aligned(id);
  }
  await open('command-center');
  await page.locator('.sidebar-nav').evaluate(node => { node.scrollTop = node.scrollHeight; });
  await hidden();
  await page.locator('.sidebar-nav').evaluate(node => { node.scrollTop = 0; });
  await aligned('command-center');
  await page.locator('#materials').hover();
  await aligned('command-center');
  await page.locator('#materials').focus();
  await page.keyboard.press('Enter');
  await aligned('materials');
  assert.equal(await page.locator('#materials').evaluate(node => getComputedStyle(node).outlineStyle), 'solid');

  // Border offsets and horizontal scrolling are measured, not assumed to be zero.
  await page.locator('#app-sidebar').evaluate(node => {
    node.style.border = '3px solid'; node.querySelector('.nav-group').style.minWidth = '300px'; node.querySelector('.sidebar-nav').scrollLeft = 20;
  });
  await aligned('materials');
  await page.locator('#app-sidebar').evaluate(node => {
    node.style.border = ''; node.querySelector('.nav-group').style.minWidth = ''; node.querySelector('.sidebar-nav').scrollLeft = 0;
  });
  await aligned('materials');

  for (const width of [1440,1024,981,980,768,390,320]) {
    await page.setViewportSize({width,height:900});
    if (width <= 980 && !await page.locator('#app-sidebar').isVisible()) await page.locator('#menu-toggle').click();
    await aligned('materials');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
  }
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await aligned('materials');
  await open('approvals');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
  await page.keyboard.press('Escape');
  await hidden();
  assert.equal(await page.locator('#app-sidebar').evaluate(node => node.inert), true);
  assert.equal(await page.evaluate(() => document.activeElement.id), 'menu-toggle');
  await page.locator('#menu-toggle').click();
  await aligned('approvals');
  await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');

  // An unavailable target and a failed measurement both restore the semantic CSS fallback.
  await open('audit-trail');
  await page.locator('#audit-trail').evaluate(node => { node.hidden = true; });
  await hidden();
  await page.locator('#audit-trail').evaluate(node => { node.hidden = false; });
  await aligned('audit-trail');
  await open('command-center');
  await page.evaluate(() => {
    const target = document.getElementById('command-center');
    window.lensRect = target.getBoundingClientRect;
    target.getBoundingClientRect = () => { throw new Error('synthetic layout failure'); };
    window.dispatchEvent(new Event('resize'));
  });
  await hidden();
  await settle();
  assert.notEqual(await page.locator('#command-center').evaluate(node => getComputedStyle(node).backgroundColor), 'rgba(0, 0, 0, 0)');
  assert.equal(await page.locator('#command-center').evaluate(node => getComputedStyle(node,'::before').content), '""');
  await open('workforce');
  await page.evaluate(() => { document.getElementById('command-center').getBoundingClientRect = window.lensRect; });
  await page.evaluate(() => { window.originalLens.remove(); });
  await page.locator('#materials').click();
  await page.waitForFunction(() => !document.getElementById('app-sidebar').classList.contains('nav-lens-ready'));
  assert.equal(await page.locator('#materials').getAttribute('aria-current'), 'page', 'navigation works without any lens node');
  await page.locator('#approvals').click();
  assert.equal(await page.locator('#approvals').getAttribute('aria-current'), 'page');
  assert.notEqual(await page.locator('#approvals').evaluate(node => getComputedStyle(node).backgroundColor), 'rgba(0, 0, 0, 0)',
    'approval also has a solid selected fallback without the lens');
  await page.evaluate(() => {
    document.getElementById('app-sidebar').prepend(window.originalLens);
    window.dispatchEvent(new Event('resize'));
  });
  await aligned('approvals');

  for (const reducedMotion of ['reduce','no-preference']) {
    await page.emulateMedia({reducedMotion});
    await page.locator('.sidebar-nav').evaluate(node => { node.scrollTop = 0; });
    const finalSelection = await page.evaluate(() => {
      for (const id of ['board-home','workforce','capacity-plan','command-center']) document.getElementById(id).click();
      return [...document.querySelectorAll('#app-sidebar [aria-current]')].map(node => node.id);
    });
    assert.deepEqual(finalSelection, ['command-center'], 'semantics settle synchronously before presentation frames');
    // Four destinations in one task still coalesce into one measurement of the *final* selection;
    // the lens is never walked through the three that were never rendered. Under reduced motion
    // that measurement is also the finished geometry; otherwise A3's spring travels to it and
    // `aligned` below is what proves it arrives exactly. Travel itself is covered by
    // browser_navigation_spring.cjs.
    const onNextFrame = await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => {
      const a = document.getElementById('nav-selection-lens').getBoundingClientRect();
      const b = document.getElementById('command-center').getBoundingClientRect();
      resolve(['x','y','width','height'].every(key => Math.abs(a[key] - b[key]) < 1));
    })));
    if (reducedMotion === 'reduce') assert.equal(onNextFrame, true, 'reduced motion has no travel at all');
    await aligned('command-center');
    await settle();
    const before = await page.evaluate(() => ({executed:window.lensFrames.executed,pending:window.lensFrames.pending.size}));
    await page.waitForTimeout(500);
    assert.deepEqual(await page.evaluate(() => ({executed:window.lensFrames.executed,pending:window.lensFrames.pending.size})), before,
      'settled navigation performs zero RAF work');
    assert.equal(before.pending, 0);
  }

  await open('backup');
  await page.locator('#logout').click();
  await page.locator('#login-view:not([hidden])').waitFor();
  await hidden();
  assert.equal(await page.locator('#nav-selection-lens').getAttribute('style'), null);
  await login(viewer);
  await page.locator('#board-home').scrollIntoViewIfNeeded();
  await aligned('board-home');
  assert.equal(await page.locator('#backup').isHidden(), true);
  assert.equal(await page.locator('#audit-trail').isHidden(), true);
  await login(admin);

  for (const [width, theme] of [[1440,'light'],[1440,'dark'],[390,'light']]) {
    await page.setViewportSize({width,height:width === 390 ? 844 : 1000});
    if (await page.locator('html').getAttribute('data-theme') !== theme) await page.locator('#theme').click();
    for (const id of ['command-center','capacity-plan','approvals']) {
      await open(id);
      if (id === 'command-center') await page.locator('#command-center-content:not([hidden])').waitFor();
      if (id === 'approvals') await page.locator('#approval-list').waitFor();
      await page.locator('#'+id).scrollIntoViewIfNeeded();
      await aligned(id);
      await settle();
      await page.screenshot({path:path.join(shots,`a2-lens-${width}-${theme}-${id}.png`)});
    }
  }
  await page.keyboard.press('Escape');
  await page.setViewportSize({width:1440,height:1000});
  await page.evaluate(() => {
    window.requestAnimationFrame = window.lensFrames.raf;
    window.cancelAnimationFrame = window.lensFrames.cancel;
    delete window.lensFrames; delete window.originalLens; delete window.lensRect;
  });
  console.log('A2 navigation lens PASS: one decorative node, geometry, analytics disclosure, sticky approvals, scroll/borders, resize/text scale, drawer/focus, fallback, rapid navigation, roles, reduced motion, zero idle RAF.');
};
