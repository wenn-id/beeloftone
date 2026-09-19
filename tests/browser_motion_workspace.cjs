// M2 workspace navigation motion: the entry classes attached to activateWorkspace(), the
// selected-navigation settle, the mobile drawer entry with its inert handling, and the explicit
// reduced-motion path. Asserts lifecycle flags and settled outcomes rather than animation
// timings, per the motion specification's test style.
const assert = require('node:assert/strict');

module.exports = async ({page, login, openSidebarDestination, admin, apiGet}) => {
  const visibleSections = () => page.evaluate(() =>
    [...document.querySelectorAll('.workspace-main > section')]
      .filter(section => !section.hidden).map(section => section.id));
  const heading = name => page.getByRole('heading', {name, exact: true}).waitFor();

  // Record every class change on the workspace sections and the sidebar, so the entry
  // lifecycle can be asserted after the fact instead of raced with a polling loop.
  const watchMotion = () => page.evaluate(() => {
    window.motionLog = [];
    for (const node of [...document.querySelectorAll('.workspace-main > section'), document.getElementById('app-sidebar')]) {
      new MutationObserver(() => window.motionLog.push({id: node.id, classes: node.className}))
        .observe(node, {attributes: true, attributeFilter: ['class']});
    }
  });
  const motionLog = () => page.evaluate(() => window.motionLog);
  const settledClasses = () => page.evaluate(() =>
    [...document.querySelectorAll('.workspace-main > section, #app-sidebar')]
      .filter(node => node.classList.contains('motion-enter') || node.classList.contains('is-ready'))
      .map(node => node.id || node.className));

  await login(admin);
  await openSidebarDestination('Produksi');
  await heading('Yang sedang dikerjakan.');

  // ---- a real page change plays the entry, then cleans up after itself ------------------
  await watchMotion();
  await openSidebarDestination('People');
  await heading('Kehadiran tim yang tercatat.');
  await page.waitForTimeout(500);
  const peopleEntry = (await motionLog()).filter(entry => entry.id === 'people-view');
  assert.ok(peopleEntry.some(entry => entry.classes.includes('motion-enter')),
    'the target page receives the entry class after it is logically active');
  assert.ok(peopleEntry.some(entry => entry.classes.includes('is-ready')),
    'the entry is released on the following frame');
  assert.deepEqual(await settledClasses(), [],
    'transient motion classes are removed once the entry has played');
  assert.deepEqual(await visibleSections(), ['people-view']);
  assert.equal(await page.locator('#workforce').getAttribute('aria-current'), 'page');

  // Desktop navigation must not steal focus: only the mobile drawer contract moves it.
  const desktopFocus = await page.evaluate(() => ({
    id: document.activeElement ? document.activeElement.id : '',
    inPage: Boolean(document.activeElement && document.activeElement.closest('.workspace-main')),
  }));
  assert.equal(desktopFocus.inPage, false, 'desktop navigation does not move focus into the page');
  assert.equal(desktopFocus.id, 'workforce', 'focus stays on the control the user activated');

  // ---- the first activation after a session start does not animate ----------------------
  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  await login(admin);
  await watchMotion();
  await page.waitForTimeout(500);
  assert.deepEqual(await settledClasses(), [], 'the first page after login has no motion state');

  // ---- switching reports inside the shared analytics host does not replay the entry -----
  await openSidebarDestination('WIP ageing');
  await heading('WIP ageing & sinyal hambatan');
  await page.waitForTimeout(500);
  await watchMotion();
  await page.getByRole('button', {name: 'Kualitas produksi', exact: true}).click();
  await heading('Kualitas produksi');
  await page.waitForTimeout(500);
  const analyticsSwitch = await motionLog();
  assert.deepEqual(analyticsSwitch.filter(entry => entry.classes.includes('motion-enter')), [],
    'switching reports in one host does not replay the page entry');
  assert.deepEqual(await visibleSections(), ['analytics-view'], 'the shared host stays the active page');

  // ---- the focused case: Produksi -> People -> Approval quickly, holding a late response --
  await openSidebarDestination('Produksi');
  await heading('Yang sedang dikerjakan.');
  await page.waitForTimeout(300);
  let releaseBoard, signalBoard, finishBoard;
  const boardStarted = new Promise(resolve => signalBoard = resolve);
  const boardReleased = new Promise(resolve => releaseBoard = resolve);
  const boardFinished = new Promise(resolve => finishBoard = resolve);
  let delayBoard = true;
  await page.route('**/api/production-board?*', async route => {
    if (delayBoard) {
      delayBoard = false;
      const response = await route.fetch(); signalBoard();
      await boardReleased; await route.fulfill({response}); finishBoard();
    } else await route.continue();
  });
  await watchMotion();
  await page.getByRole('button', {name: 'Produksi', exact: true}).click();
  await boardStarted;
  const boardList = await page.evaluate(() => document.getElementById('order-list').innerHTML.length);
  await page.getByRole('button', {name: 'People', exact: true}).click();
  await page.getByRole('button', {name: 'Inbox approval', exact: true}).click();
  await heading('Satu antrean untuk setiap keputusan.');
  releaseBoard(); await boardFinished;
  await page.unroute('**/api/production-board?*');
  await page.waitForTimeout(500);
  assert.deepEqual(await visibleSections(), ['approvals-view'], 'only the final destination is active');
  assert.equal(await page.evaluate(() => document.getElementById('order-list').innerHTML.length), boardList,
    'the late board response cannot repaint the page the user left');
  assert.deepEqual(await settledClasses(), [], 'rapid navigation leaves no animation class behind');
  assert.equal(await page.locator('#app-sidebar [aria-current]').count(), 1, 'one aria-current after rapid navigation');

  // ---- reduced motion: same result, no motion at all ------------------------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  await watchMotion();
  await openSidebarDestination('People');
  await heading('Kehadiran tim yang tercatat.');
  await page.waitForTimeout(500);
  const reducedLog = await motionLog();
  assert.deepEqual(reducedLog.filter(entry => entry.classes.includes('motion-enter')), [],
    'reduced motion never receives an entry class');
  assert.deepEqual(await visibleSections(), ['people-view'], 'reduced motion reveals the target');
  assert.equal(await page.locator('#workforce').getAttribute('aria-current'), 'page',
    'reduced motion keeps aria-current identical');
  assert.equal(await page.locator('#people-view').evaluate(node => getComputedStyle(node).opacity), '1',
    'reduced motion reveals the target immediately');
  await page.emulateMedia({reducedMotion: 'no-preference'});

  // ---- desktop never makes the sidebar inert, and never animates it ---------------------
  assert.equal(await page.locator('#app-sidebar').getAttribute('inert'), null, 'desktop sidebar stays interactive');

  // ---- 320px at 200%: no overflow while the entry is in flight --------------------------
  await page.setViewportSize({width: 320, height: 900});
  await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
  await page.locator('#menu-toggle').click();
  const overflowWatch = page.evaluate(async () => {
    const root = document.documentElement;
    const deadline = performance.now() + 500;
    let overflowed = root.scrollWidth > root.clientWidth;
    while (performance.now() < deadline) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      overflowed = overflowed || root.scrollWidth > root.clientWidth;
    }
    return overflowed;
  });
  await page.getByRole('button', {name: 'Produksi', exact: true}).click();
  assert.equal(await overflowWatch, false, 'no document overflow while the drawer and page entry run');
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});

  // ---- the closed drawer is not reachable by Tab ---------------------------------------
  await page.setViewportSize({width: 390, height: 844});
  await heading('Yang sedang dikerjakan.');
  assert.equal(await page.evaluate(() => document.body.classList.contains('nav-open')), false, 'drawer settled closed');
  assert.notEqual(await page.locator('#app-sidebar').getAttribute('inert'), null,
    'a closed drawer is inert as well as unrendered');
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  let reachedInsideDrawer = 0;
  for (let step = 0; step < 40; step += 1) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(() => Boolean(document.activeElement && document.activeElement.closest('#app-sidebar'))))
      reachedInsideDrawer += 1;
  }
  assert.equal(reachedInsideDrawer, 0, 'no control inside the closed drawer is reachable by Tab');

  // ---- the drawer entry plays, and opening lifts inert ----------------------------------
  await watchMotion();
  await page.locator('#menu-toggle').click();
  assert.equal(await page.locator('#app-sidebar').getAttribute('inert'), null, 'an open drawer is interactive');
  await page.getByRole('button', {name: 'People', exact: true}).waitFor();
  await page.waitForTimeout(500);
  const drawerLog = (await motionLog()).filter(entry => entry.id === 'app-sidebar');
  assert.ok(drawerLog.some(entry => entry.classes.includes('motion-enter')), 'the drawer entry plays on open');
  assert.deepEqual(await settledClasses(), [], 'the drawer entry cleans up after itself');

  // Selecting a destination closes the drawer and keeps the heading-focus contract.
  await page.getByRole('button', {name: 'People', exact: true}).click();
  await heading('Kehadiran tim yang tercatat.');
  assert.equal(await page.evaluate(() => document.body.classList.contains('nav-open')), false);
  assert.equal(await page.evaluate(() => document.activeElement ===
    document.querySelector('#people-view').querySelector('h1')), true, 'focus lands on the new page heading');
  assert.notEqual(await page.locator('#app-sidebar').getAttribute('inert'), null, 'a closed drawer returns to inert');
  await page.setViewportSize({width: 1440, height: 1000});
  // Let the entry that the drawer navigation started finish before the next section, so the
  // assertions below measure the recovery path and not a still-playing entry.
  await page.waitForTimeout(400);

  // ---- pending recovery is unchanged and no motion hides it ----------------------------
  const actor = (await apiGet('/api/users')).find(user => user.role === 'admin');
  const pending = {actor_id: actor.id, title: 'CONTOH pending motion',
    transaction: {path: '/api/products', key: crypto.randomUUID(),
      body: JSON.stringify({sku: 'MOTION-RECOVERY-' + Date.now(), name: 'CONTOH motion', color: 'Blue', size: 'M'})}};
  const storageKey = 'beeloft.pending.' + actor.id;
  await page.evaluate(({storageKey, pending}) => sessionStorage.setItem(storageKey, JSON.stringify(pending)),
    {storageKey, pending});
  const owningPage = await visibleSections();
  const beforeRecovery = await settledClasses();
  await watchMotion();
  await openSidebarDestination('Scan bundle');
  await heading('Konfirmasi pencatatan sebelumnya');
  assert.notEqual(await page.locator('#dialog').getAttribute('open'), null, 'the recovery dialog opens');
  assert.deepEqual(await visibleSections(), owningPage, 'recovery preserves the owning page');
  assert.deepEqual(await settledClasses(), beforeRecovery, 'recovery navigation adds no motion state');
  await page.keyboard.press('Escape');
  assert.notEqual(await page.locator('#dialog').getAttribute('open'), null, 'unresolved recovery still cannot be dismissed');
  await page.getByRole('button', {name: 'Coba ulang penyimpanan', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('dialog').open);
  assert.equal(await page.evaluate(key => sessionStorage.getItem(key), storageKey), null, 'the pending draft is settled');

  console.log('Workspace motion browser QA PASS: entry motion attaches after logical activation and cleans '
    + 'up, a shared analytics host does not replay it, rapid navigation leaves one active page and no class, '
    + 'reduced motion reveals immediately with identical aria-current, the closed drawer stays inert and '
    + 'unreachable by Tab, and pending recovery is unchanged.');
};
