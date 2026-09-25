// M4 data states and notifications: the notice enter/exit with its six-second semantic timer
// untouched, the in-place refresh treatment, list replacement fading as one unit, and the empty
// and error paths that must stay immediate. Asserts lifecycle flags and settled outcomes rather
// than animation timings, per the motion specification's test style.
const assert = require('node:assert/strict');

module.exports = async ({page, login, openSidebarDestination, admin, apiGet}) => {
  const heading = name => page.getByRole('heading', {name, exact: true}).waitFor();
  const listState = () => page.evaluate(() => {
    const list = document.getElementById('order-list');
    return {
      refreshing: list.classList.contains('is-refreshing'),
      motion: list.className.includes('motion-'),
      busy: list.getAttribute('aria-busy'),
      hidden: list.hidden,
      opacity: getComputedStyle(list).opacity,
      rows: list.querySelectorAll('.order-row').length,
      rowClasses: [...list.querySelectorAll('.order-row')].map(row => row.className).join('|'),
    };
  });
  // One hold at a time: the route fulfils only when the case releases it, so the state during a
  // load is observed rather than guessed from timing.
  const installBoardHold = async () => {
    let release, settle, signal;
    const started = new Promise(resolve => signal = resolve);
    const held = new Promise(resolve => release = resolve);
    const settled = new Promise(resolve => settle = resolve);
    await page.route('**/api/production-board?*', async route => {
      const response = await route.fetch(); signal();
      await held; await route.fulfill({response}); settle();
    });
    return {started, release, settled};
  };
  // The class change alone is not proof — it is also recorded when an engine coalesces the
  // updates into one style recalculation, in which case nothing ever transitions.
  const installListWatch = () => page.evaluate(() => {
    window.listLog = [];
    const list = document.getElementById('order-list');
    new MutationObserver(() => window.listLog.push({classes: list.className}))
      .observe(list, {attributes: true, attributeFilter: ['class']});
    for (const type of ['transitionrun', 'transitionend'])
      list.addEventListener(type, event => window.listLog.push({type, name: event.propertyName}));
  });
  const replaced = () => page.evaluate(() => window.listLog
    .some(entry => String(entry.classes || '').includes('motion-enter')));
  const fadeRan = () => page.evaluate(() => ({
    started: window.listLog.some(entry => entry.type === 'transitionrun' && entry.name === 'opacity'),
    finished: window.listLog.some(entry => entry.type === 'transitionend' && entry.name === 'opacity'),
  }));

  await login(admin);
  await openSidebarDestination('Produksi');
  await heading('Produksi');
  await page.locator('#order-list .order-row').first().waitFor();

  // ---- the notice enters, keeps its six seconds, then leaves -------------------------------
  // The blocked close is the cheapest deterministic notify in the product: no write and no new
  // record, so the toast lifecycle owns this case instead of borrowing another case's data.
  const actor = (await apiGet('/api/users')).find(user => user.role === 'admin');
  const storageKey = 'beeloft.pending.' + actor.id;
  await page.evaluate(({storageKey, pending}) => sessionStorage.setItem(storageKey, JSON.stringify(pending)),
    {storageKey, pending: {actor_id: actor.id, title: 'CONTOH pending gerak data',
      transaction: {path: '/api/products', key: crypto.randomUUID(),
        body: JSON.stringify({sku: 'MOTION-DATA-' + Date.now(), name: 'CONTOH gerak data',
          color: 'Blue', size: 'M'})}}});
  await page.evaluate(() => {
    window.noticeLog = [];
    const notice = document.getElementById('notice');
    new MutationObserver(() => window.noticeLog.push({classes: notice.className, hidden: notice.hidden}))
      .observe(notice, {attributes: true, attributeFilter: ['class', 'hidden']});
    for (const type of ['transitionrun', 'transitionend'])
      notice.addEventListener(type, event => window.noticeLog.push({type, name: event.propertyName}));
  });
  await openSidebarDestination('Scan bundle');
  await heading('Konfirmasi pencatatan sebelumnya');
  await page.getByRole('button', {name: 'Tutup dialog', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('notice').hidden);
  await page.waitForTimeout(400);
  const noticeEntry = await page.evaluate(() => ({
    classes: document.getElementById('notice').className,
    text: document.getElementById('notice').textContent,
    log: window.noticeLog,
  }));
  assert.equal(noticeEntry.text.includes('coba ulang sebelum menutup'), true,
    'the notice carries the message it was given');
  assert.equal(noticeEntry.log.some(entry => entry.type === 'transitionrun' && entry.name === 'opacity'), true,
    'the notice entry really transitions');
  assert.equal(noticeEntry.log.some(entry => entry.type === 'transitionend' && entry.name === 'opacity'), true,
    'the notice entry runs to completion');
  assert.equal(noticeEntry.classes, 'notice', 'the notice entry leaves no motion class behind');
  // The animation must not shorten the reading time.
  await page.waitForTimeout(4000);
  assert.equal(await page.evaluate(() => document.getElementById('notice').hidden), false,
    'the notice is still visible four seconds in');
  await page.waitForFunction(() => document.getElementById('notice').hidden, null, {timeout: 8000});
  const noticeExit = await page.evaluate(() => window.noticeLog);
  assert.equal(noticeExit.some(entry => String(entry.classes || '').includes('motion-exit')), true,
    'the notice leaves through the exit state');
  assert.equal(noticeExit.some(entry => entry.type === 'transitionend' && entry.name === 'opacity'), true,
    'the exit transition runs to completion');
  assert.equal(await page.evaluate(() => document.getElementById('notice').className), 'notice',
    'the exit leaves no motion class behind');
  await page.getByRole('button', {name: 'Coba ulang penyimpanan', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('dialog').open);
  assert.equal(await page.evaluate(key => sessionStorage.getItem(key), storageKey), null,
    'the pending draft is settled through the unchanged path');

  // ---- a manual refresh keeps the rows and dims them without blocking controls --------------
  await openSidebarDestination('Produksi');
  await heading('Produksi');
  await installListWatch();
  const rowsBefore = (await listState()).rows;
  assert.equal(rowsBefore > 0, true, 'the board has rows to preserve');
  const holdRefresh = await installBoardHold();
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await holdRefresh.started;
  await page.waitForTimeout(300);
  const duringRefresh = await listState();
  assert.equal(duringRefresh.rows, rowsBefore, 'a refresh keeps the existing rows on screen');
  assert.equal(duringRefresh.hidden, false, 'a refresh does not hide the list');
  assert.equal(duringRefresh.refreshing, true, 'the container reports the refreshing state');
  assert.equal(duringRefresh.busy, 'true', 'the refreshing container is marked busy for assistive technology');
  const dimmed = parseFloat(duringRefresh.opacity);
  assert.equal(dimmed >= 0.72 && dimmed <= 0.82, true, `the refresh dims the list inside the documented band (${dimmed})`);
  assert.equal(await page.evaluate(() =>
    ['search','status','board-owner','board-stage'].some(id => document.getElementById(id).disabled)),
    false, 'a refresh leaves the filters usable — the treatment is a signal, not a lock');
  assert.equal(await page.evaluate(() =>
    document.getElementById('previous').disabled && document.getElementById('next').disabled), true,
    'the existing pagination guard is unchanged: its buttons stay disabled while a page loads');
  holdRefresh.release(); await holdRefresh.settled;
  await page.unroute('**/api/production-board?*');
  await page.waitForTimeout(400);
  const settled = await listState();
  assert.equal(settled.refreshing, false, 'the refreshing state is removed when the load settles');
  assert.equal(settled.busy, null, 'the busy marker is removed when the load settles');
  assert.equal(parseFloat(settled.opacity), 1, 'the list returns to full opacity');
  assert.equal(await replaced(), false, 'a plain refresh does not fade the list');
  assert.equal(settled.rowClasses, duringRefresh.rowClasses, 'a plain refresh does not restyle individual rows');

  // ---- a filter change is a replacement, and only a replacement fades -----------------------
  await page.evaluate(() => {window.listLog = [];});
  const holdFilter = await installBoardHold();
  await page.locator('#board-stage').selectOption('cutting');
  await holdFilter.started;
  holdFilter.release(); await holdFilter.settled;
  await page.unroute('**/api/production-board?*');
  await page.waitForTimeout(400);
  assert.equal(await replaced(), true, 'a filter change fades the list as one unit');
  const fade = await fadeRan();
  assert.equal(fade.started, true, 'the replacement really starts an opacity transition');
  assert.equal(fade.finished, true, 'the replacement transition runs to completion');
  assert.equal((await listState()).motion, false, 'the replacement class is cleaned up after the fade');
  assert.equal(await page.evaluate(() => [...document.querySelectorAll('#order-list .order-row')]
    .some(row => row.className.includes('motion'))), false, 'no individual row is animated');

  // ---- an empty result hands over to the empty state as one unit ---------------------------
  await page.evaluate(() => {
    window.messageLog = [];
    const node = document.getElementById('board-message');
    for (const type of ['transitionrun', 'transitionend'])
      node.addEventListener(type, event => window.messageLog.push({type, name: event.propertyName}));
  });
  await page.locator('#search').fill('zzz-tidak-ada-' + Date.now());
  await page.getByRole('button', {name: 'Cari order', exact: true}).click();
  await page.getByText('Tidak ada order yang cocok', {exact: false}).waitFor();
  assert.equal(await page.evaluate(() => document.getElementById('order-list').querySelectorAll('.order-row').length), 0,
    'the list is emptied for an empty result');
  assert.equal(await page.evaluate(() => document.getElementById('board-message').className.includes('motion-')), true,
    'the empty state enters as one unit rather than appearing mid-frame');
  await page.waitForTimeout(400);
  const emptyFade = await page.evaluate(() => window.messageLog);
  assert.equal(emptyFade.some(entry => entry.type === 'transitionrun' && entry.name === 'opacity'), true,
    'the empty state really fades in rather than only changing classes');
  assert.equal(emptyFade.some(entry => entry.type === 'transitionend' && entry.name === 'opacity'), true,
    'the empty state fade runs to completion');
  assert.equal(await page.evaluate(() => document.getElementById('board-message').className), 'state',
    'the empty state cleans up after itself');
  await page.getByRole('button', {name: 'Reset filter', exact: true}).click();
  await page.locator('#order-list .order-row').first().waitFor();

  // ---- an error during a refresh is immediate and never dimmed ------------------------------
  const rowsBeforeError = (await listState()).rows;
  await page.route('**/api/production-board?*', async route => {
    await route.fulfill({status: 503, contentType: 'application/json',
      body: JSON.stringify({detail: 'Papan produksi sedang sibuk'})});
  });
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await page.getByText('Papan produksi sedang sibuk', {exact: false}).waitFor();
  const errorState = await page.evaluate(() => ({
    refreshing: document.getElementById('order-list').classList.contains('is-refreshing'),
    opacity: getComputedStyle(document.getElementById('order-list')).opacity,
    messageOpacity: getComputedStyle(document.getElementById('board-message')).opacity,
    messageClasses: document.getElementById('board-message').className,
    rows: document.getElementById('order-list').querySelectorAll('.order-row').length,
  }));
  assert.equal(errorState.refreshing, false, 'a failed refresh clears the dimming');
  assert.equal(parseFloat(errorState.opacity), 1, 'the rows the operator already had stay fully legible');
  assert.equal(parseFloat(errorState.messageOpacity), 1, 'the error message is fully legible immediately');
  assert.equal(errorState.messageClasses.includes('motion-'), false, 'the error is never faded in');
  assert.equal(errorState.rows, rowsBeforeError, 'the previous rows are still there');
  assert.equal(await page.evaluate(() => document.getElementById('summary').getAttribute('aria-busy')), null,
    'a failed reload does not leave the board reporting busy');
  await page.unroute('**/api/production-board?*');
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await page.locator('#order-list .order-row').first().waitFor();

  // ---- a query that failed the first time still counts as a replacement when it lands -------
  // The fade compares against the query that is on screen, not the one that was asked for: a
  // request that never rendered leaves the previous rows visible, so retrying it must still fade.
  await page.route('**/api/production-board?*', async route => {
    await route.fulfill({status: 503, contentType: 'application/json',
      body: JSON.stringify({detail: 'Papan produksi sedang sibuk'})});
  });
  await page.locator('#board-stage').selectOption('cutting');
  await page.getByText('Papan produksi sedang sibuk', {exact: false}).waitFor();
  await page.unroute('**/api/production-board?*');
  await page.evaluate(() => {window.listLog = [];});
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('summary').hasAttribute('aria-busy'));
  await page.waitForTimeout(400);
  assert.equal(await replaced(), true,
    'a filter whose first attempt failed still fades the list when it finally renders');
  assert.equal((await listState()).motion, false, 'that fade cleans up after itself');
  await page.locator('#board-stage').selectOption('all');
  await page.locator('#order-list .order-row').first().waitFor();

  // ---- reduced motion keeps every state signal and drops every movement ---------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  const holdReduced = await installBoardHold();
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await holdReduced.started;
  await page.waitForTimeout(250);
  const reducedRefresh = await page.evaluate(() => {
    const list = document.getElementById('order-list');
    return {refreshing: list.classList.contains('is-refreshing'),
      opacity: getComputedStyle(list).opacity,
      transition: getComputedStyle(list).transitionDuration};
  });
  assert.equal(reducedRefresh.refreshing, true, 'reduced motion still reports the refreshing state');
  assert.equal(parseFloat(reducedRefresh.opacity) < 1, true, 'reduced motion still shows the dimmed state');
  assert.equal(reducedRefresh.transition, '0s', 'reduced motion shows the dim without a transition');
  holdReduced.release(); await holdReduced.settled;
  await page.unroute('**/api/production-board?*');
  await page.evaluate(() => {window.listLog = [];});
  await page.locator('#board-stage').selectOption('all');
  await page.waitForTimeout(400);
  assert.equal(await replaced(), false, 'reduced motion never fades a replaced list');
  await page.locator('#order-list .order-row').first().waitFor();
  // The notice contract under the same preference. It is unhidden directly because the assertion
  // is about the stylesheet's promise, and a notify would need a second blocked-close fixture.
  await page.evaluate(() => {
    const notice = document.getElementById('notice');
    notice.textContent = 'Uji gerak dikurangi'; notice.hidden = false;
  });
  const noticeReduced = await page.evaluate(() => {
    const style = getComputedStyle(document.getElementById('notice'));
    return {transition: style.transitionDuration, transform: style.transform};
  });
  assert.equal(noticeReduced.transition, '0s', 'reduced motion never transitions the notice');
  assert.equal(noticeReduced.transform, 'none', 'reduced motion never moves the notice');
  await page.evaluate(() => {document.getElementById('notice').hidden = true;});
  await page.emulateMedia({reducedMotion: 'no-preference'});

  // ---- 320px at 200%, and the dark theme, keep the same states ------------------------------
  await page.setViewportSize({width: 320, height: 900});
  await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
  const overflowWatch = page.evaluate(async () => {
    const root = document.documentElement;
    const deadline = performance.now() + 600;
    let overflowed = root.scrollWidth > root.clientWidth;
    while (performance.now() < deadline) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      overflowed = overflowed || root.scrollWidth > root.clientWidth;
    }
    return overflowed;
  });
  await page.locator('#board-stage').selectOption('cutting');
  assert.equal(await overflowWatch, false, 'no document overflow while the list is replaced at 320px and 200%');
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});
  await page.setViewportSize({width: 1440, height: 1000});
  await page.locator('#board-stage').selectOption('all');
  await page.locator('#order-list .order-row').first().waitFor();

  const startTheme = await page.evaluate(() => document.documentElement.dataset.theme);
  if (startTheme !== 'dark') await page.locator('#theme').click();
  const holdDark = await installBoardHold();
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await holdDark.started;
  await page.waitForTimeout(250);
  assert.equal((await listState()).refreshing, true, 'the dark theme keeps the same refresh state');
  holdDark.release(); await holdDark.settled;
  await page.unroute('**/api/production-board?*');
  await page.waitForTimeout(300);
  assert.equal((await listState()).refreshing, false, 'the dark theme settles the refresh state');
  if (startTheme !== 'dark') await page.locator('#theme').click();

  console.log('Data state motion browser QA PASS: the notice enters and leaves without touching its '
    + 'six-second timer, a refresh keeps the rows and dims them without blocking controls, only a '
    + 'replacement fades the list as one unit, empty and error states stay immediate and legible, '
    + 'and reduced motion keeps every state signal without the movement.');
};
