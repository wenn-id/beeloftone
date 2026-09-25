// M3 dialog and overlay motion: the CSS-only entry on the native dialog and its backdrop, the
// guarded close helper behind the close button, Batal and Escape, and the reduced-motion and
// print paths. Asserts lifecycle flags and settled outcomes rather than animation timings, per
// the motion specification's test style.
//
// OBSERVATION PRINCIPLE — read this before adding a case here or to any future animated overlay,
// sheet or popover module.
//
// Assert the STATE AT EVENT DELIVERY, never the state when Node expected the event to arrive.
//
// The production exit is deliberately short: the opacity/transform transition runs for
// --motion-fast (120ms) and a safety timer closes the dialog at 120 + 60 = 180ms if the
// transition never completes. A Node assertion that needs a `transitionend` to be observed is
// therefore asserting that a CDP round trip plus the browser's event delivery both fit inside a
// 60ms margin. Under runner load they do not, and the module fails while production semantics are
// still perfectly correct. Making the waits longer would only hide that; widening the production
// timers would change the product.
//
// So the evidence is collected inside the page instead, in the same task that installs the
// closing state: the MutationObserver below snapshots `getAnimations()`, the computed exit
// transition, `inert` and `open` the moment `is-closing` appears. A MutationObserver callback is a
// microtask, so it always runs before any 180ms timer can fire — there is no margin left to lose,
// and the snapshot proves the exit was really CREATED regardless of who eventually closes the
// dialog. Whether the exit then finishes on `transitionend` or is cut short by the safety timer is
// recorded as an outcome, not as a pass/fail condition: exactly one of `transitionend` or
// `transitioncancel` always occurs, so requiring "one of the two" is deterministic while
// requiring `transitionend` alone is a race. A close that starts no transition at all still fails.
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
  //
  // The observer additionally takes an exit snapshot the first time `is-closing` appears after a
  // log reset. It runs as a microtask inside the task that installed the closing state, so it can
  // see what that task actually created before anything else — the safety timer included — gets a
  // chance to run. `getAnimations()` flushes pending style changes, so the CSSTransition the
  // closing class just created is already there to be read.
  const installDialogWatch = () => page.evaluate(() => {
    window.dialogLog = [];
    window.exitSnapshot = null;
    const dialog = document.getElementById('dialog');
    new MutationObserver(() => {
      window.dialogLog.push({classes: dialog.className, open: dialog.open});
      if (!dialog.classList.contains('is-closing') || window.exitSnapshot) return;
      const style = getComputedStyle(dialog);
      const running = dialog.getAnimations();
      const index = style.transitionProperty.split(',').map(part => part.trim()).indexOf('opacity');
      window.exitSnapshot = {
        open: dialog.open, inert: dialog.inert, classes: dialog.className,
        pointerEvents: style.pointerEvents,
        transitionProperty: style.transitionProperty,
        // The duration that the opacity entry of the shorthand actually resolved to.
        opacityDuration: index < 0 ? null
          : parseFloat(style.transitionDuration.split(',')[index]) * 1000,
        // Live transitions and animations the closing state left on the surface. A real exit has a
        // running CSSTransition for opacity; a withdrawn entry no longer appears here.
        transitions: running.filter(animation => animation.transitionProperty)
          .map(animation => ({property: animation.transitionProperty,
            duration: animation.effect.getTiming().duration, state: animation.playState})),
        animations: running.filter(animation => animation.animationName)
          .map(animation => animation.animationName),
      };
    }).observe(dialog, {attributes: true, attributeFilter: ['class', 'open']});
    for (const type of ['animationstart', 'animationend', 'transitionrun', 'transitionend',
      'transitioncancel', 'close'])
      dialog.addEventListener(type, event => window.dialogLog.push({type,
        name: event.animationName || event.propertyName || '', pseudo: event.pseudoElement || ''}));
  });
  const clearDialogLog = () => page.evaluate(() => {window.dialogLog = []; window.exitSnapshot = null;});
  const dialogLog = () => page.evaluate(() => window.dialogLog);
  const exitSnapshot = () => page.evaluate(() => window.exitSnapshot);
  const sawAnimation = (entries, type, name) =>
    entries.some(entry => entry.type === type && entry.name === name);
  // The backdrop transitions opacity too and reports on the same element with `pseudoElement`
  // set, so the dialog's own transition has to be picked out explicitly.
  const ownOpacity = (entries, type) =>
    entries.some(entry => entry.type === type && entry.name === 'opacity' && entry.pseudo === '');
  const markedClosing = entries => entries.filter(entry => String(entry.classes || '').includes('is-closing'));
  const closeEvents = entries => entries.filter(entry => entry.type === 'close').length;

  // A real animated exit: the closing state was installed on a still-open dialog, that dialog was
  // inert and non-interactive from the same task, and a genuine opacity transition was created
  // with the token duration. None of this depends on when Node got to look.
  const assertExitCreated = (snapshot, label) => {
    assert.ok(snapshot, `${label}: the closing state was installed and captured in the same task`);
    assert.equal(snapshot.open, true, `${label}: the dialog is still open while it exits`);
    assert.equal(snapshot.inert, true, `${label}: an accepted dismissal inerts the dialog immediately`);
    assert.match(snapshot.classes, /is-closing/, `${label}: the exit is marked as closing`);
    assert.match(snapshot.classes, /motion-exit/, `${label}: the entry is withdrawn by motion-exit`);
    assert.equal(snapshot.pointerEvents, 'none', `${label}: a dialog on its way out is not an interaction surface`);
    assert.ok(snapshot.transitionProperty.includes('opacity'),
      `${label}: the exit transition covers opacity :: ${snapshot.transitionProperty}`);
    assert.equal(snapshot.opacityDuration > 0, true,
      `${label}: the opacity exit is timed by a token :: ${snapshot.opacityDuration}`);
    const opacity = snapshot.transitions.find(entry => entry.property === 'opacity');
    assert.ok(opacity, `${label}: a CSS opacity transition really exists after dispatch :: `
      + JSON.stringify(snapshot.transitions));
    assert.equal(opacity.duration > 0, true, `${label}: that transition has a non-zero duration`);
    assert.deepEqual(snapshot.animations, [],
      `${label}: no entry animation survives to swallow the exit :: ${JSON.stringify(snapshot.animations)}`);
  };
  // How the created exit ended. Exactly one of transitionend/transitioncancel always happens, so
  // this classification is deterministic; which one won is reported for visibility only.
  const exitOutcome = (entries, label) => {
    const ran = ownOpacity(entries, 'transitionrun');
    const completed = ownOpacity(entries, 'transitionend');
    const cancelled = ownOpacity(entries, 'transitioncancel');
    assert.equal(ran, true, `${label}: the opacity exit transition begins after dispatch`);
    assert.equal(completed || cancelled, true, `${label}: the exit either completes or is closed by `
      + `the safety fallback :: ${JSON.stringify(entries)}`);
    return completed ? 'transitionend' : 'safety-fallback(transitioncancel)';
  };
  // Cleanup that the native close owns, whichever of the two closed the dialog.
  const assertClosedCleanly = async label => {
    assert.equal(await dialogClasses(), '', `${label}: no closing class survives the exit`);
    assert.equal(await page.evaluate(() => document.getElementById('dialog').inert), false,
      `${label}: inert is cleared by the native close`);
  };

  await login(admin);
  await openSidebarDestination('Produksi');
  await heading('Produksi');
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
  assert.equal(await exitSnapshot(), null, 'a dialog that is simply open never creates an exit');
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
  assertExitCreated(await exitSnapshot(), 'close button');
  const exitEnded = exitOutcome(exitLog, 'close button');
  assert.equal(closeEvents(exitLog), 1, 'the dialog closes exactly once per close');
  await assertClosedCleanly('close button');
  assert.equal(await page.evaluate(() => document.activeElement === document.querySelector('#new-order')), true,
    'focus returns to the trigger that opened the dialog');
  console.log('Dialog exit outcome (close button):', exitEnded);

  // ---- a reopen replays the entry and leaves no state behind -------------------------------
  await clearDialogLog();
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  assert.ok(sawAnimation(await dialogLog(), 'animationstart', 'dialog-enter'), 'a reopen replays the entry');

  // ---- Escape takes the same decision and the same exit as the close button ----------------
  // Escape arrives as a trusted key, so the exit cannot be dispatched from inside an evaluate
  // here. The observer snapshot is what makes this case timing-free: it is taken by the page, in
  // the task the `cancel` handler ran in, whether or not Node is keeping up.
  await clearDialogLog();
  await page.keyboard.press('Escape');
  await dialogClosed();
  const escapeLog = await dialogLog();
  assert.equal(markedClosing(escapeLog).length > 0, true,
    'Escape closes through the same helper instead of bypassing it');
  assertExitCreated(await exitSnapshot(), 'Escape');
  const escapeEnded = exitOutcome(escapeLog, 'Escape');
  assert.equal(closeEvents(escapeLog), 1, 'Escape closes exactly once');
  await assertClosedCleanly('Escape');
  console.log('Dialog exit outcome (Escape):', escapeEnded);

  // ---- a close that lands while the entry is still running still plays a real exit ----------
  // Stopping the entry and applying the closing values in one style recalculation produces no
  // transition at all: the dialog would simply vanish when the safety timer fired, and a
  // backdrop still playing its entry would keep fading in behind it. Playwright's click waits
  // for the element to settle, so a human's immediate close is dispatched synthetically.
  //
  // The open, the wait for the running entry, and the close all happen inside one page call. Waiting
  // from Node and then dispatching in a second call would be a race in its own right: the entry only
  // lasts --motion-dialog (260ms), so a slow round trip between the two calls arrives after it has
  // already finished, leaving no running entry to overlap with and failing a correct product. Once
  // the wait ends nothing is awaited again, so the "entry running" reading and the close dispatch
  // share one task and the entry cannot end between them.
  await clearDialogLog();
  const overlapStart = await page.evaluate(async () => {
    const dialog = document.getElementById('dialog');
    const entry = () => dialog.getAnimations()
      .filter(animation => animation.animationName === 'dialog-enter')
      .map(animation => animation.playState);
    document.getElementById('new-order').click();
    const deadline = performance.now() + 10000;
    while (!entry().length && performance.now() < deadline)
      await new Promise(resolve => requestAnimationFrame(resolve));
    const entryBefore = entry();
    document.getElementById('close-dialog').click();
    return {entryBefore, entryAfter: entry(),
      pointerEvents: getComputedStyle(dialog).pointerEvents};
  });
  await dialogClosed();
  const overlapLog = await dialogLog();
  assert.deepEqual(overlapStart.entryBefore, ['running'],
    'the entry is still running when the close is dispatched');
  assert.deepEqual(overlapStart.entryAfter, [],
    'the close withdraws the running entry instead of letting it swallow the exit');
  assert.equal(overlapStart.pointerEvents, 'none', 'a dialog on its way out is not an interaction surface');
  assert.equal(markedClosing(overlapLog).length > 0, true, 'the close starts during the entry');
  assertExitCreated(await exitSnapshot(), 'exit during entry');
  const overlapEnded = exitOutcome(overlapLog, 'exit during entry');
  assert.equal(closeEvents(overlapLog), 1, 'it closes exactly once');
  await assertClosedCleanly('exit during entry');
  console.log('Dialog exit outcome (during entry):', overlapEnded);

  // ---- a direct native close during the exit clears the pending motion state ----------------
  // Eight controls inside the dialog content call close() directly rather than through the
  // helper. Cleanup hangs off the native close event so that an abandoned exit cannot leave a
  // timer behind, because that timer would close whatever dialog opens next.
  await openSidebarDestination('Produksi');
  await heading('Produksi');
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  await clearDialogLog();
  const abandoned = await page.evaluate(() => {
    document.getElementById('close-dialog').click();
    const dialog = document.getElementById('dialog');
    const started = dialog.getAnimations().some(animation => animation.transitionProperty === 'opacity');
    dialog.close();
    return {started, open: dialog.open};
  });
  assert.equal(abandoned.started, true, 'the abandoned exit was a real transition before it was cut short');
  assert.equal(abandoned.open, false, 'the direct native close takes effect at once');
  // Cleanup hangs off the native close event, which `close()` queues rather than dispatching
  // synchronously, so the resting state is read once that event has actually been delivered.
  await dialogClosed();
  assert.equal(await dialogClasses(), '',
    'a direct close during the exit clears the closing classes immediately');
  assert.equal(await page.evaluate(() => document.getElementById('dialog').inert), false,
    'a direct close during the exit clears inert immediately');
  // Opened while that abandoned exit is still inside its window: with a surviving timer it would
  // be closed, and with surviving classes it would be invisible.
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  assert.equal(await page.evaluate(() => document.getElementById('dialog').open), true,
    'an abandoned exit cannot close the dialog that opens next');
  assert.equal(await dialogClasses(), '', 'the next dialog carries no closing state');
  await clearDialogLog();
  await page.keyboard.press('Escape');
  await dialogClosed();

  // ---- Batal is wired to the same guarded close --------------------------------------------
  await openSidebarDestination('Master SKU');
  await heading('Master SKU');
  await clearDialogLog();
  await page.getByRole('button', {name: 'Tambah SKU', exact: true}).click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  await clearDialogLog();
  await page.getByRole('button', {name: 'Batal', exact: true}).click();
  await dialogClosed();
  const cancelLog = await dialogLog();
  assert.equal(markedClosing(cancelLog).length > 0, true, 'Batal closes through the same helper');
  assertExitCreated(await exitSnapshot(), 'Batal');
  const cancelEnded = exitOutcome(cancelLog, 'Batal');
  assert.equal(closeEvents(cancelLog), 1, 'Batal closes exactly once');
  await assertClosedCleanly('Batal');
  console.log('Dialog exit outcome (Batal):', cancelEnded);

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
  await heading('Produksi');
  await openSidebarDestination('Scan bundle');
  await heading('Konfirmasi pencatatan sebelumnya');
  await clearDialogLog();
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  assert.notEqual(await page.locator('#dialog').getAttribute('open'), null,
    'an unresolved write still cannot be dismissed');
  assert.deepEqual(markedClosing(await dialogLog()), [], 'a refused close never starts the exit');
  assert.equal(await exitSnapshot(), null, 'a refused close creates no exit transition');
  assert.equal(await dialogClasses(), '', 'a refused close adds no class');
  assert.equal(await page.locator('#dialog').evaluate(dialog => dialog.inert), false,
    'a refused unresolved close leaves recovery interactive');
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
  // Every touch of the surface is recorded. The log is cleared once the dialog has settled, so
  // anything left in it happened during or after the exit — a mutation callback runs a microtask
  // later, which is why the entry-time write cannot be separated from the exit by reading
  // `dialog.open` inside the callback.
  await page.evaluate(() => {
    window.dialogRepaints = [];
    const content = document.getElementById('dialog-content');
    new MutationObserver(() => window.dialogRepaints.push({
      open: document.getElementById('dialog').open,
      hasDetail: content.innerHTML.includes('Input perubahan'),
      html: content.innerHTML.slice(0, 80),
    })).observe(content, {childList: true, subtree: true, characterData: true});
  });
  let releaseEvent, signalEvent, signalSettled;
  const eventStarted = new Promise(resolve => signalEvent = resolve);
  const eventReleased = new Promise(resolve => releaseEvent = resolve);
  const eventSettled = new Promise(resolve => signalSettled = resolve);
  let openWhenSettled = null;
  await page.route('**/api/audit-events/' + event.id, async route => {
    const response = await route.fetch(); signalEvent();
    await eventReleased;
    // Read while the exit is still running: the whole point is that the response settles while
    // the dialog is open, which is what forces the generation guard to be the thing that
    // rejects it rather than the `open` attribute.
    openWhenSettled = await page.evaluate(() => document.getElementById('dialog').open);
    await route.fulfill({response}); signalSettled();
  });
  await page.locator('#audit-list [data-action="audit-event"]').first().click();
  await eventStarted;
  await page.evaluate(() => {window.dialogRepaints = [];});
  await page.keyboard.press('Escape');
  releaseEvent();
  await eventSettled;
  await dialogClosed();
  await page.waitForTimeout(200);
  await page.unroute('**/api/audit-events/' + event.id);
  assert.equal(openWhenSettled, true, 'the late response settles while the dialog is still open');
  const repaints = await page.evaluate(() => window.dialogRepaints);
  assert.deepEqual(repaints, [],
    `a response that settles during the exit never touches the closing dialog :: ${JSON.stringify(repaints)}`);

  // ---- reduced motion: same result, no motion, same close path -----------------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  await openSidebarDestination('Produksi');
  await heading('Produksi');
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
  assert.equal(await exitSnapshot(), null, 'reduced motion creates no exit transition');
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
  await clearDialogLog();
  await page.getByRole('button', {name: 'Tutup dialog', exact: true}).click();
  await dialogClosed();
  const darkLog = await dialogLog();
  assertExitCreated(await exitSnapshot(), 'dark theme');
  const darkEnded = exitOutcome(darkLog, 'dark theme');
  await assertClosedCleanly('dark theme');
  console.log('Dialog exit outcome (dark theme):', darkEnded);
  // The entry in dark theme is checked on its own open, because the log above is reset right
  // before the close so that the exit evidence belongs to that close alone. This runs while the
  // dark theme is still applied; restoring the incoming theme first would check the entry in
  // whatever theme the previous module left behind instead.
  await clearDialogLog();
  await trigger.click();
  await page.locator('dialog[open]').waitFor();
  await page.waitForTimeout(400);
  assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'dark',
    'the dark-theme entry is checked while the dark theme is applied');
  assert.ok(sawAnimation(await dialogLog(), 'animationend', 'dialog-enter'), 'the entry plays in dark theme');
  await page.keyboard.press('Escape');
  await dialogClosed();
  if (startTheme !== 'dark') await page.locator('#theme').click();

  console.log('Dialog motion browser QA PASS: the native dialog and its backdrop play a CSS-only entry, '
    + 'the close button, Batal and Escape share one guarded close that creates a real opacity exit on an '
    + 'immediately inert dialog and then closes exactly once, an unresolved write still cannot be dismissed, '
    + 'a late response cannot repaint a leaving dialog, reduced motion closes immediately through the same '
    + 'path, and print never carries motion state.');
};
