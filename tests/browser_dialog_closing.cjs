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
    await openForm();
    const before = await state();
    await page.keyboard.press('Escape');
    const closing = await state();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => !document.getElementById('dialog').open);
    await page.waitForTimeout(100);
    const orders = await savedOrders();
    const result = {before, closing, requests, mutations: orders.length};
    console.log('Dialog Escape/Enter reproduction:', JSON.stringify(result));
    assert.equal(before.focus, 'save-form');
    assert.equal(closing.open, true, 'the native dialog is still open during exit');
    assert.match(closing.classes, /is-closing/);
    assert.equal(requests, 0, 'accepted dismissal must prevent Enter from dispatching a write');
    assert.equal(orders.length, 0);
    assert.equal(closing.inert, true);

    const closed = async () => {
      await page.waitForFunction(() => {
        const dialog = document.getElementById('dialog');
        return !dialog.open && !dialog.inert && !dialog.className;
      });
      assert.equal((await state()).focus, 'new-order', 'native close restores the original trigger');
    };
    await closed();

    for (const action of ['close-button/Enter', 'Escape/Space', 'Escape/click', 'Escape/secondary-click',
      'Escape/Tab', 'Escape/Shift+Tab', 'Escape/focus', 'Escape/requestSubmit']) {
      await openForm();
      assert.equal((await state()).inert, false, 'reopening clears inert before focusing');
      const box = await page.locator(action.endsWith('/secondary-click')
        ? '#dialog [aria-label="Hapus baris SKU"]' : '#save-form').boundingBox();
      await page.evaluate(() => {
        window.closingActions = 0;
        for (const type of ['click', 'submit'])
          document.getElementById('action-form').addEventListener(type, () => {window.closingActions++;});
      });
      if (action.startsWith('close-button')) {
        const close = await page.locator('#close-dialog').boundingBox();
        await page.mouse.click(close.x + close.width / 2, close.y + close.height / 2);
      } else await page.keyboard.press('Escape');
      const exiting = await state();
      assert.equal(exiting.open, true, action + ' exercises the animated interval');
      assert.equal(exiting.inert, true);
      assert.match(exiting.classes, /is-closing/);
      const input = action.split('/')[1];
      if (input.endsWith('click')) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      else if (input === 'focus') {
        const entered = await page.evaluate(() => {
          const dialog = document.getElementById('dialog');
          return [...dialog.querySelectorAll('input,select,button')].some(control => {
            control.focus();
            return document.activeElement === control;
          });
        });
        assert.equal(entered, false, 'focus() cannot re-enter any closing control');
      } else if (input === 'requestSubmit') {
        await page.evaluate(() => document.getElementById('action-form').requestSubmit());
      } else await page.keyboard.press(input);
      const afterInput = await state();
      assert.equal(afterInput.focusInside, false, action + ' leaves no focus in the inert subtree');
      await closed();
      assert.equal(await page.evaluate(() => window.closingActions), 0, action + ' starts no form action');
      assert.equal(requests, 0, action + ' emits no mutation');
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
    await page.keyboard.press('Escape');
    assert.equal((await state()).open, false, 'reduced motion closes synchronously');
    await page.keyboard.press('Enter');
    assert.equal(requests, 0, 'Enter after reduced-motion dismissal emits no write');
    // Enter can activate the restored new-order trigger; that is a fresh, empty form.
    if ((await state()).open) await page.keyboard.press('Escape');
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
    console.log('Dialog closing QA PASS: zero writes/actions during accepted exit; keyboard, pointer, '
      + 'focus re-entry and requestSubmit blocked; focus restored, repeated/different reopen and reduced '
      + 'motion work; busy close refused and intentional write committed once.');
  } finally {
    await page.unroute('**/api/orders');
  }
};
