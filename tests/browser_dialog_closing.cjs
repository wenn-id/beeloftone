// PR #87 regression: once a dismissal has been accepted, the dialog is inert immediately and
// nothing — trusted keyboard, trusted pointer, programmatic focus, a scripted click or
// requestSubmit() — may start a form action, re-enter focus into the closing subtree, or emit a
// write. The original defect was that an accepted close left the focused submit button keyboard
// active, so Enter still produced a POST.
//
// OBSERVATION PRINCIPLE — read this before adding a case here or to any future animated overlay,
// sheet or popover module.
//
// Assert the STATE AT EVENT DELIVERY, never the state when Node expected the event to arrive.
//
// The exit is short on purpose: the transition runs for --motion-fast (120ms) and a safety timer
// closes the dialog at 180ms. The old shape of this module was
//
//     press Escape  ->  return to Node  ->  send a second key  ->  assume it landed while closing
//
// which silently assumes a CDP round trip completes inside that window. Under load it does not:
// the exit has legitimately finished, focus is back on the trigger, and the second key then
// activates that trigger as a brand new interaction. Reporting that as a closing-guard failure is
// a false alarm, and padding the waits would only convert it into a test that proves nothing.
//
// So every trusted probe is recorded by the page at the moment it is delivered, together with
// `open`, `inert`, the class list and the active element, and the result is interpreted against
// that recorded state. A probe that genuinely lands in the closing window must prove the full
// contract; a probe that lands after a legitimate close is treated as the fresh interaction it
// really is, and whatever it opened is cleaned up.
//
// Because delivery timing cannot be commanded, closing-window coverage is never left to chance.
// Two mechanisms guarantee it, and both are load-bearing:
//
//   1. localClosingProbe() dispatches the accepted close and then attacks the closing dialog —
//      focus() re-entry, a scripted click on the submit control, requestSubmit() — inside a single
//      page task. No timer can interleave with a task, so the dialog is provably still open,
//      inert and closing for every one of those attempts.
//   2. trustedKeyDuringClose() presses a real key and dispatches the accepted close from inside
//      that key's own capture-phase keydown, so the key's native default action — the actual
//      mechanism behind the PR #87 POST — resolves while the dialog is already inert, with no
//      margin to lose. A synthetic KeyboardEvent would not exercise that default action at all,
//      so it is deliberately not used as a substitute.
//
// What the guard can and cannot promise is worth stating, because it is why the assertions look
// the way they do. Chromium does not synchronously blur an element that was already focused when
// its subtree became inert, so a trusted key can still reach that control and a `click` can still
// be dispatched from it. The product cannot prevent that event — which is exactly why the
// centralised capture-phase `submit` guard exists. The load-bearing assertions are therefore that
// no submit ever escapes that guard, that no write is emitted, and that focus can never RE-ENTER
// the closing subtree. Click delivery is recorded for visibility, not asserted away.
const assert = require('node:assert/strict');

module.exports = async ({page, login, openSidebarDestination, admin, apiGet}) => {
  await login(admin);
  await openSidebarDestination('Produksi');
  const reference = 'DIALOG-CLOSING-' + Date.now();
  const savedOrders = async () => (await apiGet('/api/production-board?q=' + encodeURIComponent(reference)))
    .orders.filter(order => order.reference === reference);
  const openForm = async () => {
    await page.locator('#new-order').click();
    await page.getByLabel('Referensi order', {exact: true}).fill(reference);
    await page.getByLabel('Nama order', {exact: true}).fill('CONTOH dialog closing guard');
    await page.getByLabel('Target selesai', {exact: true}).fill('2099-01-01');
    await page.getByLabel('Jumlah', {exact: true}).fill('1');
    await page.locator('#save-form').focus();
    await page.waitForTimeout(350);
  };
  const state = () => page.evaluate(() => {
    const dialog = document.getElementById('dialog');
    return {open: dialog.open, classes: dialog.className, inert: dialog.inert,
      focus: document.activeElement.id, focusInside: dialog.contains(document.activeElement)};
  });

  // Installed once. A capture listener on `document` runs before the dialog's own capture-phase
  // submit guard, so a submit is recorded here even though the guard then swallows it; whether it
  // escaped the guard is counted separately, on the form itself, in the bubble phase.
  await page.evaluate(() => {
    window.delivery = [];
    // Never drained: a monotonic count of native closes is what tells a still-running exit apart
    // from a dialog that has closed and been opened again, without guessing from `open` alone.
    window.closeCount = 0;
    // The state the accepted dismissal itself installed, captured by the page in the same task that
    // installed it. Reading this back from Node with a round trip would be the very race this
    // module exists to remove: the dialog is only open for one exit budget, so a late round trip
    // would find it already closed and report a missing `is-closing` that was really there.
    window.closingSnapshot = null;
    const dialog = document.getElementById('dialog');
    new MutationObserver(() => {
      if (!dialog.classList.contains('is-closing') || window.closingSnapshot) return;
      window.closingSnapshot = {open: dialog.open, inert: dialog.inert, classes: dialog.className,
        focus: document.activeElement ? document.activeElement.id : '',
        focusInside: dialog.contains(document.activeElement)};
    }).observe(dialog, {attributes: true, attributeFilter: ['class']});
    dialog.addEventListener('close', () => {window.closeCount++;});
    for (const type of ['keydown', 'keyup', 'pointerdown', 'click', 'submit', 'close'])
      document.addEventListener(type, event => window.delivery.push({
        t: Math.round(performance.now()), type, key: event.key || '', trusted: event.isTrusted,
        target: (event.target && event.target.id) || (event.target && event.target.tagName) || '',
        open: dialog.open, inert: dialog.inert, classes: dialog.className,
        active: document.activeElement ? document.activeElement.id : '',
        focusInside: dialog.contains(document.activeElement),
      }), true);
  });
  const drain = () => page.evaluate(() => {const log = window.delivery; window.delivery = []; return log;});
  const armClosingSnapshot = () => page.evaluate(() => {window.closingSnapshot = null;});
  const closingSnapshot = () => page.evaluate(() => window.closingSnapshot);
  // The accepted dismissal installed a real closing state on a still-open, already-inert dialog.
  const assertAcceptedDismissal = (snapshot, label) => {
    assert.ok(snapshot, `${label}: the accepted dismissal installed a closing state`);
    assert.equal(snapshot.open, true, `${label}: the native dialog is still open during exit`);
    assert.equal(snapshot.inert, true, `${label}: an accepted dismissal inerts the dialog immediately`);
    assert.match(snapshot.classes, /is-closing/, `${label}: the exit is marked as closing`);
  };
  // Counts only what got past the centralised guard: these sit on the form, in the bubble phase,
  // and stopImmediatePropagation() in the guard means a blocked submit never arrives.
  const watchFormActions = () => page.evaluate(() => {
    window.escapedActions = {click: 0, submit: 0};
    const form = document.getElementById('action-form');
    for (const type of ['click', 'submit'])
      form.addEventListener(type, () => {window.escapedActions[type]++;});
  });
  const escapedActions = () => page.evaluate(() => window.escapedActions);
  const CLOSING = 'closing-window', AFTER = 'after-close';
  const classify = record => !record ? 'not-delivered'
    : record.open && record.inert && /is-closing/.test(record.classes) ? CLOSING
    : record.open ? 'open-not-closing' : AFTER;
  const describe = record => record ? `${record.type}${record.key ? '[' + record.key + ']' : ''}`
    + ` tgt=${record.target} open=${record.open} inert=${record.inert} cls="${record.classes}"`
    + ` active=${record.active} inside=${record.focusInside}` : 'none';

  // Resting state only. Focus is asserted separately, because a probe that legitimately landed
  // after the close may have clicked or tabbed somewhere else entirely, and that is not a defect.
  const settled = () => page.waitForFunction(() => {
    const dialog = document.getElementById('dialog');
    return !dialog.open && !dialog.inert && !dialog.className;
  });
  const closed = async () => {
    await settled();
    assert.equal((await state()).focus, 'new-order', 'native close restores the original trigger');
  };
  const closeCount = () => page.evaluate(() => window.closeCount);
  const waitForCloses = expected => page.waitForFunction(n => window.closeCount >= n, expected);
  // Waits for the accepted dismissal to actually complete, then reports whether the probe had ALSO
  // opened a fresh dialog. A probe that legitimately landed after the close may have activated the
  // restored trigger; that is a new, empty form rather than a violation, but it must not leak into
  // the next case. Counting native closes is what distinguishes it from an exit still in flight —
  // testing `open` alone would call every unfinished exit a stray dialog.
  const settleAfterProbe = async baseline => {
    await waitForCloses(baseline + 1);
    if (!(await state()).open) return false;
    await page.keyboard.press('Escape');
    await waitForCloses(baseline + 2);
    return true;
  };

  let requests = 0;
  let allowWrite = false, releaseWrite, writeStarted;
  await page.route('**/api/orders', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    requests++;
    if (allowWrite) {
      writeStarted();
      await new Promise(resolve => {releaseWrite = resolve;});
      return route.continue();
    }
    // Count attempted writes without letting the failing baseline mutate the fixture.
    await route.fulfill({status: 422, contentType: 'application/json',
      body: JSON.stringify({detail: 'Regression intercepted the mutation before server dispatch'})});
  });
  try {
    // ---- the PR #87 sequence, interpreted by where the second key actually landed -------------
    await openForm();
    const before = await state();
    assert.equal(before.focus, 'save-form', 'the submit control is focused before the dismissal');
    await watchFormActions();
    await drain();
    const enterBaseline = await closeCount();
    await armClosingSnapshot();
    await page.keyboard.press('Escape');
    const closing = await closingSnapshot();
    await page.keyboard.press('Enter');
    const enterLog = await drain();
    const enterRecord = enterLog.find(record => record.type === 'keydown' && record.key === 'Enter');
    const enterWhere = classify(enterRecord);
    console.log('Dialog Escape/Enter delivery:', enterWhere, '::', describe(enterRecord),
      JSON.stringify({closing, requests}));
    assertAcceptedDismissal(closing, 'Escape');
    assert.notEqual(enterWhere, 'open-not-closing',
      'Enter cannot arrive at an open dialog that is not closing :: ' + describe(enterRecord));
    if (enterWhere === CLOSING) {
      // The real regression window: Enter reached the still-inert dialog.
      assert.equal((await escapedActions()).submit, 0,
        'no submit escapes the guard while the dialog is closing');
      assert.equal(requests, 0, 'accepted dismissal must prevent Enter from dispatching a write');
    } else {
      // The exit had legitimately finished and focus was already back on the trigger, so this
      // Enter is a new interaction on that trigger — not a closing-guard breach.
      assert.equal(enterRecord.focusInside, false,
        'a post-close Enter is delivered outside the dialog subtree :: ' + describe(enterRecord));
      assert.equal(enterRecord.active, 'new-order',
        'a post-close Enter lands on the restored trigger :: ' + describe(enterRecord));
      assert.equal(requests, 0, 'a post-close Enter still emits no stale write');
    }
    assert.equal((await savedOrders()).length, 0, 'nothing was written during the accepted exit');
    if (await settleAfterProbe(enterBaseline))
      console.log('Dialog Escape/Enter: cleaned up a fresh dialog the post-close Enter legitimately opened.');
    await closed();

    // ---- guaranteed closing-window coverage, browser-local and timing-free -------------------
    // Everything below the close dispatch happens in the same page task, so the dialog is provably
    // open, inert and closing for each attempt. This is what keeps the contract load-bearing when
    // the trusted probes above legitimately land after the close.
    const localClosingProbe = () => page.evaluate(() => {
      const dialog = document.getElementById('dialog');
      const form = document.getElementById('action-form');
      const escaped = {click: 0, submit: 0};
      const tally = event => {escaped[event.type]++;};
      for (const type of ['click', 'submit']) form.addEventListener(type, tally);
      // Accepted dismissal through the production close button.
      document.getElementById('close-dialog').click();
      const atDispatch = {open: dialog.open, inert: dialog.inert, classes: dialog.className,
        pointerEvents: getComputedStyle(dialog).pointerEvents};
      // 1. focus() may not re-enter any control in the closing subtree.
      //
      // Focus has to be parked outside the dialog first. Chromium does not synchronously blur the
      // element that was already focused when the subtree became inert, so probing straight away
      // would find `document.activeElement === control` for that one control and report a re-entry
      // that never happened — the focus simply had not left yet. Blurring first makes this a real
      // test of whether inert can be re-entered, which is the actual contract. That the still
      // focused control cannot be *activated* is proven separately, with a real key, by
      // trustedKeyDuringClose().
      const residualFocus = dialog.contains(document.activeElement)
        ? (document.activeElement.id || document.activeElement.tagName) : null;
      if (document.activeElement) document.activeElement.blur();
      const parked = dialog.contains(document.activeElement);
      const reentered = [...dialog.querySelectorAll('input,select,button,textarea,[tabindex]')]
        .filter(control => {control.focus(); return document.activeElement === control;})
        .map(control => control.id || control.name || control.tagName);
      // 2. a scripted click on the submit control may not produce a form action.
      document.getElementById('save-form').click();
      // 3. requestSubmit() may not bypass the guard.
      let requestSubmitError = null;
      try { form.requestSubmit(); } catch (error) { requestSubmitError = String(error); }
      const after = {open: dialog.open, inert: dialog.inert, classes: dialog.className,
        active: document.activeElement ? document.activeElement.id : '',
        focusInside: dialog.contains(document.activeElement)};
      for (const type of ['click', 'submit']) form.removeEventListener(type, tally);
      return {atDispatch, residualFocus, parked, reentered, requestSubmitError, escaped, after};
    });
    await openForm();
    assert.equal((await state()).inert, false, 'reopening clears inert before focusing');
    const local = await localClosingProbe();
    console.log('Dialog closing-window probe:', JSON.stringify(local));
    assert.equal(local.atDispatch.open, true, 'the probe runs while the dialog is still open');
    assert.equal(local.atDispatch.inert, true, 'the probe runs while the dialog is inert');
    assert.match(local.atDispatch.classes, /is-closing/, 'the probe runs while the dialog is closing');
    assert.equal(local.atDispatch.pointerEvents, 'none', 'the closing dialog is not an interaction surface');
    assert.equal(local.after.open, true, 'the whole probe ran inside the closing window');
    assert.equal(local.after.inert, true, 'the dialog stayed inert for the whole probe');
    assert.equal(local.parked, false, 'focus really was parked outside the dialog before probing');
    assert.deepEqual(local.reentered, [],
      'focus() cannot re-enter any closing control :: ' + JSON.stringify(local.reentered));
    assert.equal(local.after.focusInside, false, 'no focus is left inside the inert subtree');
    assert.equal(local.escaped.submit, 0,
      'neither a scripted click nor requestSubmit() gets a submit past the guard');
    assert.equal(requests, 0, 'the closing-window probe emits no write');
    await closed();
    assert.equal((await savedOrders()).length, 0, 'the closing-window probe wrote nothing');

    // ---- the PR #87 mechanism itself, with a real key and no timing margin -------------------
    // The accepted close is dispatched from inside the trusted keydown, so the key's own native
    // default action — activating the focused submit button — resolves while the dialog is already
    // inert. This is the exact path that used to emit a POST.
    //
    // Which event carries the activation differs by key: Chromium activates a button from Enter on
    // `keydown`, but from Space on `keyup`. Binding the dismissal to the wrong one would put the
    // activation in a LATER task than the dismissal, and the probe would then depend on that task
    // arriving inside the 180ms window — exactly the coupling this module exists to remove. So the
    // dismissal is dispatched from the capture phase of whichever event actually activates. Capture
    // runs before the button's default handler, so the activation that follows is guaranteed to
    // resolve against an already-inert dialog.
    const activationEvent = key => key === ' ' ? 'keyup' : 'keydown';
    const trustedKeyDuringClose = async key => {
      await page.evaluate(({probeKey, closeOn}) => {
        window.closeAtKey = null;
        const dialog = document.getElementById('dialog');
        const once = event => {
          if (!event.isTrusted || event.key !== probeKey) return;
          document.removeEventListener(closeOn, once, true);
          document.getElementById('close-dialog').click();
          window.closeAtKey = {open: dialog.open, inert: dialog.inert, classes: dialog.className,
            active: document.activeElement ? document.activeElement.id : ''};
        };
        document.addEventListener(closeOn, once, true);
      }, {probeKey: key, closeOn: activationEvent(key)});
      await drain();
      // The hold is not a wait for anything to settle: it is deliberately longer than the 180ms
      // fallback, and the probe still lands inside the closing window because the dismissal and the
      // activation share one event. How long a key is held cannot widen or narrow that window.
      await page.keyboard.press(key, {delay: 220});
      return {dispatch: await page.evaluate(() => window.closeAtKey), log: await drain()};
    };
    for (const key of ['Enter', ' ']) {
      const label = key === ' ' ? 'Space' : key;
      await openForm();
      await watchFormActions();
      const probe = await trustedKeyDuringClose(key);
      // The initiating keydown is by construction recorded before the close is dispatched — the
      // document-level recorder is installed first, so it runs ahead of the one-shot listener. What
      // has to land inside the closing window is the key's RESOLUTION: the activation of the
      // focused submit control and the submit event that activation produces.
      const activations = probe.log.filter(record => record.trusted
        && (record.type === 'click' || record.type === 'submit'));
      console.log(`Dialog trusted ${label} during accepted close:`,
        JSON.stringify({dispatch: probe.dispatch, delivered: probe.log.map(describe)}));
      assert.ok(probe.dispatch, `${label}: the accepted close ran inside the trusted keydown`);
      assert.equal(probe.dispatch.open, true, `${label}: the dialog is still open when the key resolves`);
      assert.equal(probe.dispatch.inert, true, `${label}: the dismissal inerted the dialog immediately`);
      assert.match(probe.dispatch.classes, /is-closing/, `${label}: the exit is running`);
      assert.equal(probe.dispatch.active, 'save-form', `${label}: the submit control was the focused target`);
      // The native default action really happened: without these the case would prove nothing, and
      // a synthetic KeyboardEvent would never have produced them at all.
      assert.ok(activations.some(record => record.type === 'click' && record.target === 'save-form'),
        `${label}: the trusted key activated the focused submit control :: `
        + JSON.stringify(probe.log.map(describe)));
      assert.ok(activations.some(record => record.type === 'submit' && record.target === 'action-form'),
        `${label}: that activation produced a real submit for the guard to stop :: `
        + JSON.stringify(probe.log.map(describe)));
      // And every part of that resolution was delivered to an inert, closing dialog.
      for (const record of activations)
        assert.equal(classify(record), CLOSING,
          `${label}: the key resolved inside the closing window :: ${describe(record)}`);
      assert.equal((await escapedActions()).submit, 0,
        `${label}: no submit escapes the guard once the dismissal is accepted`);
      assert.equal(requests, 0, `${label}: a trusted key during an accepted close emits no write`);
      await closed();
      assert.equal((await savedOrders()).length, 0, `${label}: nothing was written`);
    }

    // ---- trusted pointer and Tab probes, interpreted by where they landed --------------------
    for (const action of ['close-button/Enter', 'Escape/Space', 'Escape/click', 'Escape/secondary-click',
      'Escape/Tab', 'Escape/Shift+Tab']) {
      await openForm();
      assert.equal((await state()).inert, false, 'reopening clears inert before focusing');
      const box = await page.locator(action.endsWith('/secondary-click')
        ? '#dialog [aria-label="Hapus baris SKU"]' : '#save-form').boundingBox();
      await watchFormActions();
      await drain();
      const baseline = await closeCount();
      await armClosingSnapshot();
      if (action.startsWith('close-button')) {
        const close = await page.locator('#close-dialog').boundingBox();
        await page.mouse.click(close.x + close.width / 2, close.y + close.height / 2);
      } else await page.keyboard.press('Escape');
      assertAcceptedDismissal(await closingSnapshot(), action);
      await drain();
      const input = action.split('/')[1];
      if (input.endsWith('click')) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      else await page.keyboard.press(input);
      const log = await drain();
      const record = log.find(entry => entry.trusted && (input.endsWith('click')
        ? entry.type === 'pointerdown'
        : entry.type === 'keydown' && entry.key === input.split('+').pop().replace('Space', ' ')))
        || log.find(entry => entry.trusted && entry.type === 'keydown');
      const where = classify(record);
      console.log(`Dialog ${action} delivery:`, where, '::', describe(record));
      if (where === CLOSING) {
        // In-window: the dismissal was accepted, so nothing this input does may reach a form
        // action or a write. Focus containment for this state is proven browser-locally by
        // localClosingProbe(), which cannot lose the race; asserting it again from a recorded
        // trusted delivery would only re-introduce a dependency on Chromium's asynchronous blur
        // of the control that was focused when the subtree became inert.
        assert.equal((await escapedActions()).submit, 0, action + ' gets no submit past the guard');
      } else {
        // The exit had legitimately finished before this input arrived. That makes it a fresh
        // interaction on a restored trigger, not a breach — but it still has to be true that the
        // close completed properly first, which the recorded state is what proves.
        assert.equal(where, AFTER,
          action + ' lands either in the closing window or after the close :: ' + describe(record));
        assert.equal(record.focusInside, false,
          action + ' is delivered outside the dialog subtree once it has closed :: ' + describe(record));
        assert.equal(record.active, 'new-order',
          action + ' only arrives once focus is back on the trigger :: ' + describe(record));
      }
      assert.equal(requests, 0, action + ' emits no mutation');
      if (await settleAfterProbe(baseline))
        console.log(`Dialog ${action}: cleaned up a fresh dialog opened after the legitimate close.`);
      await settled();
      // Focus is pinned only where the probe cannot have moved it. While the dialog is inert the
      // page outside it is blocked by the modal, so an in-window probe leaves the restored trigger
      // focused; a post-close click or Tab legitimately focuses something else, and for those the
      // recorded delivery state above already proved the trigger had been restored.
      if (where === CLOSING)
        assert.equal((await state()).focus, 'new-order', action + ' restores the original trigger');
      assert.equal(requests, 0, action + ' still emits no mutation after cleanup');
    }

    // The next different dialog is usable after native close and cleanup.
    await openSidebarDestination('Master SKU');
    await page.getByRole('button', {name: 'Tambah SKU', exact: true}).click();
    await page.getByLabel('Kode SKU', {exact: true}).fill('CONTOH-CLOSING-REOPEN');
    assert.equal((await state()).focusInside, true);
    assert.equal((await state()).inert, false);
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.getElementById('dialog').open);
    await openSidebarDestination('Produksi');

    await page.emulateMedia({reducedMotion: 'reduce'});
    await openForm();
    await watchFormActions();
    const reducedBaseline = await closeCount();
    await page.keyboard.press('Escape');
    assert.equal((await state()).open, false, 'reduced motion closes synchronously');
    await page.keyboard.press('Enter');
    assert.equal(requests, 0, 'Enter after reduced-motion dismissal emits no write');
    // Enter can activate the restored new-order trigger; that is a fresh, empty form.
    if (await settleAfterProbe(reducedBaseline))
      console.log('Reduced motion: cleaned up a fresh dialog opened by the post-close Enter.');
    await closed();
    await page.emulateMedia({reducedMotion: 'no-preference'});

    // A genuine in-flight write refuses dismissal, then succeeds normally after release.
    await openForm();
    allowWrite = true;
    const started = new Promise(resolve => {writeStarted = resolve;});
    await page.keyboard.press('Enter');
    await started;
    try {
      await page.keyboard.press('Escape');
      const busy = await state();
      assert.equal(busy.open, true);
      assert.equal(busy.inert, false, 'a refused busy close must not inert the dialog');
      assert.equal(busy.classes, '');
      assert.equal(requests, 1, 'only the intentional submission is dispatched');
    } finally { releaseWrite(); }
    await page.waitForFunction(() => !document.getElementById('dialog').open);
    await page.getByRole('heading', {name: 'CONTOH dialog closing guard', exact: true}).waitFor();
    const saved = await savedOrders();
    assert.equal(saved.length, 1, 'reopened form writes exactly one real synthetic order');
    assert.equal((await state()).inert, false, 'confirmed-write native close cleans up');
    console.log('Dialog closing QA PASS: zero writes/actions during accepted exit; a real key resolving '
      + 'inside the accepted close cannot submit, focus re-entry, scripted click and requestSubmit are '
      + 'blocked while provably inert, trusted probes are judged by their delivery state, focus restored, '
      + 'repeated/different reopen and reduced motion work; busy close refused and intentional write '
      + 'committed once.');
  } finally {
    await page.unroute('**/api/orders');
  }
};
