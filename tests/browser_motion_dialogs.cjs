// M3 dialog and overlay motion: the CSS-only entry on the native dialog and its backdrop, the
// guarded close helper behind the close button, Batal and Escape, and the reduced-motion and
// print paths. Asserts lifecycle flags and settled outcomes rather than animation timings, per
// the motion specification's test style.
const assert = require('node:assert/strict');

module.exports = async ({page, login, openSidebarDestination, admin, apiGet}) => {
  const heading = name => page.getByRole('heading', {name, exact: true}).waitFor();
  const dialogClasses = () => page.evaluate(() => document.getElementById('dialog').className);
  // The close event is dispatched in a later task than the attribute change, so wait for it
  // rather than reading the log the instant `open` flips.
  const dialogClosed = async (closes = 1) => {
    await page.waitForFunction(() => !document.getElementById('dialog').open);
    await page.waitForFunction(expected =>
      window.dialogLog.filter(entry => entry.type === 'close').length >= expected, closes);
  };
  const trigger = page.getByRole('button', {name: 'Buat order produksi', exact: true});

  // Instrumentation is installed once: re-installing would stack observers and listeners. The
  // class and attribute mutations give the lifecycle, and the animation/transition events are
  // the load-bearing part — a class change alone is also recorded when an engine coalesces the
  // updates into one style recalculation, in which case nothing ever animates.
  const installDialogWatch = () => page.evaluate(() => {
    window.dialogLog = [];
    const dialog = document.getElementById('dialog');
    new MutationObserver(() => window.dialogLog.push({classes: dialog.className, open: dialog.open}))
      .observe(dialog, {attributes: true, attributeFilter: ['class', 'open']});
    for (const type of ['animationstart', 'animationend', 'transitionrun', 'transitionend', 'close'])
      dialog.addEventListener(type, event =>
        window.dialogLog.push({type, name: event.animationName || event.propertyName || ''}));
  });
  const clearDialogLog = () => page.evaluate(() => {window.dialogLog = [];});
  const dialogLog = () => page.evaluate(() => window.dialogLog);
  const sawAnimation = (entries, type, name) =>
    entries.some(entry => entry.type === type && entry.name === name);
  const sawTransition = (entries, type) => entries.some(entry => entry.type === type && entry.name === 'opacity');
  const markedClosing = entries => entries.filter(entry => String(entry.classes || '').includes('is-closing'));
  const closeEvents = entries => entries.filter(entry => entry.type === 'close').length;

  await login(admin);
  await openSidebarDestination('Produksi');
  await heading('Yang sedang dikerjakan.');
  await installDialogWatch();

  // ---- entry: the surface and the backdrop animate from their first frame ------------------
  await clearDialogLog();
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  const entryLog = await dialogLog();
  assert.ok(sawAnimation(entryLog, 'animationstart', 'dialog-enter'), 'the dialog plays its entry');
  assert.ok(sawAnimation(entryLog, 'animationend', 'dialog-enter'), 'the entry runs to completion');
  assert.deepEqual(markedClosing(entryLog), [], 'a dialog that is simply open is never marked as closing');
  const backdrop = await page.evaluate(() => {
    const style = getComputedStyle(document.getElementById('dialog'), '::backdrop');
    return {name: style.animationName, duration: style.animationDuration};
  });
  assert.equal(backdrop.name, 'dialog-backdrop-enter', 'the backdrop has its own entry animation');
  assert.equal(parseFloat(backdrop.duration) > 0, true, 'the backdrop entry is timed by a token');

  // ---- exit: the close button runs the exit, then closes exactly once ----------------------
  await clearDialogLog();
  await page.getByRole('button', {name: 'Tutup dialog', exact: true}).click();
  await dialogClosed();
  const exitLog = await dialogLog();
  assert.equal(markedClosing(exitLog).length > 0, true, 'the close button marks the dialog as closing before it closes');
  assert.ok(sawTransition(exitLog, 'transitionrun'), 'the exit really starts an opacity transition');
  assert.ok(sawTransition(exitLog, 'transitionend'), 'the exit transition runs to completion');
  assert.equal(closeEvents(exitLog), 1, 'the dialog closes exactly once per close');
  assert.equal(await dialogClasses(), '', 'no closing class survives the exit');
  assert.equal(await page.evaluate(() => document.activeElement === document.querySelector('#new-order')), true,
    'focus returns to the trigger that opened the dialog');

  // ---- a reopen replays the entry and leaves no state behind -------------------------------
  await clearDialogLog();
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  assert.ok(sawAnimation(await dialogLog(), 'animationstart', 'dialog-enter'), 'a reopen replays the entry');

  // ---- Escape takes the same decision and the same exit as the close button ----------------
  await clearDialogLog();
  await page.keyboard.press('Escape');
  await dialogClosed();
  const escapeLog = await dialogLog();
  assert.equal(markedClosing(escapeLog).length > 0, true,
    'Escape closes through the same helper instead of bypassing it');
  assert.ok(sawTransition(escapeLog, 'transitionrun'), 'the Escape exit animates');
  assert.equal(closeEvents(escapeLog), 1, 'Escape closes exactly once');
  assert.equal(await dialogClasses(), '', 'Escape leaves no closing class behind');

  // ---- a close that lands while the entry is still running still plays a real exit ----------
  // Stopping the entry and applying the closing values in one style recalculation produces no
  // transition at all: the dialog would simply vanish when the safety timer fired, and a
  // backdrop still playing its entry would keep fading in behind it. Playwright's click waits
  // for the element to settle, so a human's immediate close is dispatched synthetically.
  await clearDialogLog();
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForFunction(() => document.getElementById('dialog').getAnimations()
    .some(animation => animation.animationName === 'dialog-enter'));
  const entryWasRunning = await page.evaluate(() => {
    const dialog = document.getElementById('dialog');
    const running = dialog.getAnimations().some(animation => animation.animationName === 'dialog-enter');
    document.getElementById('close-dialog').click();
    return running;
  });
  await dialogClosed();
  const overlapLog = await dialogLog();
  assert.equal(entryWasRunning, true, 'the entry is still running when the close is dispatched');
  assert.equal(markedClosing(overlapLog).length > 0, true, 'the close starts during the entry');
  assert.ok(sawTransition(overlapLog, 'transitionrun'), 'an exit that starts during the entry still transitions');
  assert.ok(sawTransition(overlapLog, 'transitionend'), 'that exit also runs to completion');
  assert.equal(closeEvents(overlapLog), 1, 'it closes exactly once');
  assert.equal(await dialogClasses(), '', 'no motion class survives a close that overlapped the entry');

  // ---- Batal is wired to the same guarded close --------------------------------------------
  await openSidebarDestination('Master SKU');
  await heading('Satu kode untuk setiap kombinasi produk.');
  await clearDialogLog();
  await page.getByRole('button', {name: 'Tambah SKU', exact: true}).click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  await clearDialogLog();
  await page.getByRole('button', {name: 'Batal', exact: true}).click();
  await dialogClosed();
  const cancelLog = await dialogLog();
  assert.equal(markedClosing(cancelLog).length > 0, true, 'Batal closes through the same helper');
  assert.equal(closeEvents(cancelLog), 1, 'Batal closes exactly once');
  assert.equal(await dialogClasses(), '', 'Batal leaves no closing class behind');

  // ---- repeated cycles never stack handlers or leave motion state --------------------------
  await clearDialogLog();
  for (let round = 0; round < 3; round += 1) {
    await page.getByRole('button', {name: 'Tambah SKU', exact: true}).click();
    await page.locator('dialog[open]').waitFor();
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('dialog').open);
  }
  await dialogClosed(3);
  const cyclesLog = await dialogLog();
  assert.equal(closeEvents(cyclesLog), 3, 'each cycle closes the dialog exactly once');
  assert.equal(await dialogClasses(), '', 'repeated open and close leaves the dialog in its resting class list');

  // ---- the blocked path is unchanged: an unresolved write cannot be dismissed --------------
  const actor = (await apiGet('/api/users')).find(user => user.role === 'admin');
  const storageKey = 'beeloft.pending.' + actor.id;
  await page.evaluate(({storageKey, pending}) => sessionStorage.setItem(storageKey, JSON.stringify(pending)),
    {storageKey, pending: {actor_id: actor.id, title: 'CONTOH pending gerak dialog',
      transaction: {path: '/api/products', key: crypto.randomUUID(),
        body: JSON.stringify({sku: 'MOTION-DIALOG-' + Date.now(), name: 'CONTOH gerak dialog',
          color: 'Blue', size: 'M'})}}});
  await openSidebarDestination('Produksi');
  await heading('Yang sedang dikerjakan.');
  await openSidebarDestination('Scan bundle');
  await heading('Konfirmasi pencatatan sebelumnya');
  await clearDialogLog();
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  assert.notEqual(await page.locator('#dialog').getAttribute('open'), null,
    'an unresolved write still cannot be dismissed');
  assert.deepEqual(markedClosing(await dialogLog()), [], 'a refused close never starts the exit');
  assert.equal(await dialogClasses(), '', 'a refused close adds no class');
  await page.getByRole('button', {name: 'Coba ulang penyimpanan', exact: true}).click();
  await dialogClosed();
  assert.equal(await page.evaluate(key => sessionStorage.getItem(key), storageKey), null,
    'the pending draft is settled through the unchanged path');

  // ---- a late response cannot paint into a dialog that is already leaving -------------------
  // The exit keeps the dialog open for one exit budget, so the request-generation guard — not
  // the `open` attribute — is what has to reject the stale response.
  const event = (await apiGet('/api/audit-events?limit=1')).items[0];
  await openSidebarDestination('Audit trail');
  await heading('Audit trail');
  let releaseEvent, signalEvent;
  const eventStarted = new Promise(resolve => signalEvent = resolve);
  const eventReleased = new Promise(resolve => releaseEvent = resolve);
  await page.route('**/api/audit-events/' + event.id, async route => {
    const response = await route.fetch(); signalEvent();
    await eventReleased; await route.fulfill({response});
  });
  await page.locator('#audit-list [data-action="audit-event"]').first().click();
  await eventStarted;
  await page.keyboard.press('Escape');
  await dialogClosed();
  releaseEvent();
  await page.waitForTimeout(300);
  await page.unroute('**/api/audit-events/' + event.id);
  assert.equal(await page.evaluate(() => document.getElementById('dialog-content').innerHTML.includes('Input perubahan')), false,
    'a response that lands during the exit cannot repaint the dialog');

  // ---- reduced motion: same result, no motion, same close path -----------------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  await openSidebarDestination('Produksi');
  await heading('Yang sedang dikerjakan.');
  await clearDialogLog();
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  assert.equal(await page.locator('#dialog').evaluate(node => getComputedStyle(node).opacity), '1',
    'reduced motion reveals the dialog immediately');
  await page.waitForTimeout(400);
  assert.deepEqual((await dialogLog()).filter(entry => entry.type === 'animationstart'), [],
    'reduced motion runs no entry animation');
  await clearDialogLog();
  await page.getByRole('button', {name: 'Tutup dialog', exact: true}).click();
  assert.equal(await page.evaluate(() => document.getElementById('dialog').open), false,
    'reduced motion closes immediately');
  assert.deepEqual(markedClosing(await dialogLog()), [], 'reduced motion never marks the dialog as closing');
  assert.equal(await page.evaluate(() => document.activeElement === document.querySelector('#new-order')), true,
    'reduced motion restores focus through the same path');
  await page.emulateMedia({reducedMotion: 'no-preference'});

  // ---- print: the static label artefact never carries motion state -------------------------
  await clearDialogLog();
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  await page.emulateMedia({media: 'print'});
  const printState = await page.evaluate(() => {
    const style = getComputedStyle(document.getElementById('dialog'));
    return {name: style.animationName, opacity: style.opacity, transform: style.transform};
  });
  assert.equal(printState.name, 'none', 'a printed dialog never plays the entry animation');
  assert.equal(printState.opacity, '1', 'a printed dialog is opaque even when captured mid-entry');
  assert.equal(printState.transform, 'none', 'a printed dialog is captured at its resting position');
  await page.emulateMedia({media: 'screen'});
  await page.keyboard.press('Escape');
  await dialogClosed();

  // ---- 320px at 200%: no overflow while the dialog enters, and it fits when settled ---------
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
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  assert.equal(await overflowWatch, false, 'no document overflow while the dialog entry runs');
  assert.equal(await page.locator('dialog[open]').evaluate(node =>
    node.scrollWidth <= node.clientWidth && node.getBoundingClientRect().width <= innerWidth), true,
    'the dialog fits at 320px and 200% text');
  await page.keyboard.press('Escape');
  await dialogClosed();
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});
  await page.setViewportSize({width: 1440, height: 1000});

  // ---- dark theme: the same lifecycle, no colour dependency --------------------------------
  // The toggle is labelled by its own text, so its accessible name flips with the theme the
  // previous module left behind. Reach it by id and put back whatever was found.
  const startTheme = await page.evaluate(() => document.documentElement.dataset.theme);
  if (startTheme !== 'dark') await page.locator('#theme').click();
  await clearDialogLog();
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  await page.getByRole('button', {name: 'Tutup dialog', exact: true}).click();
  await dialogClosed();
  const darkLog = await dialogLog();
  assert.ok(sawAnimation(darkLog, 'animationend', 'dialog-enter'), 'the entry plays in dark theme');
  assert.ok(sawTransition(darkLog, 'transitionend'), 'the exit plays in dark theme');
  assert.equal(await dialogClasses(), '', 'dark theme leaves no closing class behind');
  if (startTheme !== 'dark') await page.locator('#theme').click();

  console.log('Dialog motion browser QA PASS: the native dialog and its backdrop play a CSS-only entry, '
    + 'the close button, Batal and Escape share one guarded close that exits then closes exactly once, '
    + 'an unresolved write still cannot be dismissed, a late response cannot repaint a leaving dialog, '
    + 'reduced motion closes immediately through the same path, and print never carries motion state.');
};
