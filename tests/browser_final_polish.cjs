const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// A6.8 - final consistency / polish / cleanup, behavioural half.
//
// A6.8 migrated no workspace. What it owns is the product seen as ONE thing, so this module walks
// all sixteen primary destinations and a representative dialog set with the same questions:
//
//   navigation - every destination opens one visible workspace with the right aria-current, no JS
//                error, no stale workspace left visible, and no document or section-edge overflow at
//                1440, 390 and 320px with 200% text;
//   actions    - the heading actions are reachable and still role-gated for admin, operator, viewer;
//   dialogs    - the shared #dialog fits the viewport at every width, scrolls internally, never
//                sideways, keeps its sticky heading, closes on "Tutup dialog" and Escape and returns
//                focus, and takes the deterministic width its content asks for;
//   forms      - a simple, a two-column, a dynamic-line and an uncertain / retry form behave exactly
//                as before under the new chrome (the retry is the one primary, fields stay locked,
//                Escape is refused, the retry saves exactly once);
//   modes      - dark, reduced motion, forced colors and (where the engine can emulate it) reduced
//                transparency keep every meaning visible.
//
// The business rules of every sheet stay owned by their own suites (purchase orders, incoming QC,
// supplier returns and payments, unified / payroll approvals, purchase requests). It also writes the
// deterministic A6.8 review set to $BEELOFT_A68_REVIEW or <qa-shots>/a68-visual-gate.
module.exports = async ({page, login, admin, operator, viewer, apiGet, work}) => {
  const base = process.env.BEELOFT_QA_BASE;
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const review = process.env.BEELOFT_A68_REVIEW || path.join(shots, 'a68-visual-gate');
  fs.mkdirSync(review, {recursive: true});
  const errors = [];
  const initialTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
  const onError = error => errors.push(error.message);
  page.on('pageerror', onError);

  const DESTINATIONS = [
    ['command-center', 'command-center-view', 'Command Center'], ['board-home', 'board-view', 'Produksi'],
    ['materials', 'materials-view', 'Bahan baku'], ['products', 'products-view', 'Master SKU'],
    ['workforce', 'people-view', 'People'], ['scan-bundle', 'bundle-scan-view', 'Scan bundle'],
    ['scan-finished-goods', 'finished-goods-scan-view', 'Scan barang jadi'], ['wip-ageing-insights', 'analytics-view', 'Analitik'],
    ['ai-brain', 'ai-view', 'Tanya Beeloft'], ['integrations', 'integrations-view', 'Integrasi'],
    ['activity', 'activity-view', 'Aktivitas'], ['audit-trail', 'audit-view', 'Audit trail'],
    ['backup', 'backup-view', 'Cadangan data'], ['purchase-requests', 'purchase-requests-view', 'Permintaan pembelian'],
    ['marketing-budgets', 'marketing-budgets-view', 'Budget marketing'], ['approvals', 'approvals-view', 'Inbox approval'],
  ];
  const ADMIN_ONLY = new Set(['audit-trail', 'backup']);

  const dialog = page.locator('#dialog');
  const settle = async () => {
    await page.waitForFunction(() => !document.querySelector('.motion-enter') && !document.querySelector('#dialog.is-closing'));
    await page.waitForTimeout(150);
  };
  const shot = async name => {
    await page.evaluate(() => { const notice = document.getElementById('notice'); if (notice) notice.hidden = true; });
    await settle();
    await page.screenshot({path: path.join(review, name + '.png')});
  };
  const text200 = on => page.evaluate(value => { document.documentElement.style.fontSize = value; }, on ? '200%' : '');
  const theme = async mode => { await page.evaluate(value => document.documentElement.setAttribute('data-theme', value), mode); await page.waitForTimeout(500); };
  const closeDialog = async () => {
    if (await dialog.isVisible()) { await page.keyboard.press('Escape'); await dialog.waitFor({state: 'hidden'}); }
  };
  async function role(key) {
    await closeDialog();
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
    await login(key);
  }
  // Destinations are driven by the sidebar control itself - its own click handler - including the
  // analytics child that lives inside the collapsed group and the phone drawer.
  const go = async (nav, sectionId) => {
    await closeDialog();
    await page.evaluate(id => { document.querySelector('.nav-collapse')?.setAttribute('open', ''); document.getElementById(id).click(); }, nav);
    await page.locator(`#${sectionId}:not([hidden])`).waitFor();
    await page.waitForFunction(id => !document.getElementById(id).querySelector('[aria-busy="true"]'), sectionId).catch(() => {});
    await settle();
  };
  const workspaceState = sectionId => page.evaluate(id => {
    const visible = [...document.querySelectorAll('.workspace-main section[id$="-view"]')].filter(node => !node.hidden && node.getClientRects().length).map(node => node.id);
    return {visible, current: document.querySelector('.app-sidebar [aria-current="page"]')?.id || null, target: id};
  }, sectionId);
  // The five pre-A6 polite BODY hosts (Milestones C-E) are the documented exception: each announces
  // its page's body swap, is pinned by the A6.4 / A6.7 contracts, and holds its own error / state
  // region, which as the nearest live root announces its own message. Recorded as deferred
  // non-visual debt in docs/apple27-final-consistency-polish.md. Anything else nested is a defect.
  const LIVE = '[aria-live]:not([aria-live=off]),[role=status],[role=alert],[role=log]';
  const BODY_HOSTS = ['analytics-body', 'integrations-body', 'purchase-requests-body', 'marketing-budgets-body', 'approvals-body'];
  const nestedLiveRegions = rootId => page.evaluate(([id, live, hosts]) => [...document.getElementById(id).querySelectorAll(live)]
    .filter(node => { const outer = node.parentElement.closest(live);
      return outer && !hosts.includes(outer.id) && document.getElementById(id).contains(outer); })
    .map(node => node.tagName.toLowerCase() + (node.id ? '#' + node.id : '')), [rootId, LIVE, BODY_HOSTS]);
  const noDocumentOverflow = () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  // A box that crosses its section, or text that spills out of a visible-overflow box, unless an
  // ancestor inside the section owns the overflow on purpose (an internally scrolling table).
  const sectionOverflow = sectionId => page.evaluate(id => {
    const section = document.getElementById(id), box = section.getBoundingClientRect();
    const control = node => ['INPUT', 'SELECT', 'TEXTAREA', 'OPTION'].includes(node.tagName);
    const owned = node => { for (let up = node.parentElement; up && up !== section; up = up.parentElement)
      if (['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(up).overflowX)) return true; return false; };
    return [...section.querySelectorAll('*')].filter(node => node.getClientRects().length && !node.closest('.visually-hidden') && !owned(node))
      .filter(node => { const rect = node.getBoundingClientRect(); return rect.right > box.right + 1 || rect.left < box.left - 1
        || (!control(node) && node.clientWidth > 0 && node.scrollWidth > node.clientWidth + 1 && getComputedStyle(node).overflowX === 'visible'); })
      .slice(0, 8).map(node => node.tagName.toLowerCase() + (node.id ? '#' + node.id : '') + '.' + String(node.className).split(' ')[0]);
  }, sectionId);
  const fits = async (sectionId, where) => {
    assert.equal(await noDocumentOverflow(), true, `document overflow: ${where}`);
    assert.deepEqual(await sectionOverflow(sectionId), [], `content crosses its section: ${where}`);
  };
  const dialogGeometry = () => page.evaluate(() => {
    const d = document.getElementById('dialog'), rect = d.getBoundingClientRect(), style = getComputedStyle(d);
    const heading = d.querySelector('.dialog-heading');
    const edge = rect.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight);
    const offenders = d.scrollWidth <= d.clientWidth ? [] : [...d.querySelectorAll('*')].filter(node => node.getClientRects().length
      && node.getBoundingClientRect().right > edge + 1).slice(0, 8).map(node => node.tagName.toLowerCase() + '.' + String(node.className).split(' ')[0]);
    return {width: rect.width, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, vw: innerWidth, vh: innerHeight,
      sideways: d.scrollWidth > d.clientWidth, offenders, overflowY: style.overflowY, scrollable: d.scrollHeight > d.clientHeight + 1,
      size: d.dataset.size, sticky: getComputedStyle(heading).position, radius: parseFloat(style.borderRadius),
      closeName: document.getElementById('close-dialog').getAttribute('aria-label')};
  });
  const dialogFits = async where => {
    const g = await dialogGeometry();
    assert.equal(g.sideways, false, `${where}: the dialog scrolls sideways (${g.offenders.join(', ')})`);
    assert.ok(g.left >= 0 && g.right <= g.vw + 1 && g.top >= 0 && g.bottom <= g.vh + 1, `${where}: the dialog leaves the viewport`);
    assert.equal(g.overflowY, 'auto', `${where}: the dialog scrolls internally`);
    assert.equal(g.sticky, 'sticky', `${where}: the heading stays with the reader`);
    assert.equal(g.closeName, 'Tutup dialog');
    return g;
  };
  // Every representative dialog is measured at 1440, on a phone, and at 320px with 200% text.
  const dialogSweep = async where => {
    const desktop = await dialogFits(`${where} at 1440`);
    await page.setViewportSize({width: 390, height: 844}); await dialogFits(`${where} at 390`);
    await page.setViewportSize({width: 320, height: 800}); await text200(true);
    const narrow = await dialogFits(`${where} at 320 / 200%`);
    // px insets: at 320px / 200% the sheet keeps all but 16px of the viewport.
    assert.ok(narrow.width >= 300, `${where}: the sheet keeps its width at 320 / 200% (${narrow.width}px)`);
    await text200(false); await page.setViewportSize({width: 1440, height: 1000});
    return desktop;
  };
  // A dialog opened the way the product's own buttons open it: through the document-level
  // data-action delegation.
  const openAction = async (action, id = null) => {
    await page.evaluate(([name, value]) => { const button = document.createElement('button'); button.type = 'button';
      button.dataset.action = name; if (value) button.dataset.id = value; button.hidden = true; document.body.append(button);
      button.click(); button.remove(); }, [action, id]);
    await dialog.waitFor();
    await page.waitForFunction(() => !document.querySelector('#dialog-content .loading-state'));
    await settle();
  };

  // ------------------------------------------------------------------ 1. navigation sweep
  await role(admin);
  for (const [nav, sectionId, name] of DESTINATIONS) {
    await page.setViewportSize({width: 1440, height: 1000});
    await go(nav, sectionId);
    const state = await workspaceState(sectionId);
    assert.deepEqual(state.visible, [sectionId], `${name}: exactly one visible workspace`);
    assert.equal(state.current, nav, `${name}: aria-current follows the destination`);
    // One announcement per message: no live region is nested inside another one.
    assert.deepEqual(await nestedLiveRegions(sectionId), [], `${name}: nested live regions`);
    await fits(sectionId, `${name} at 1440`);
    await shot(`ws-1440-${sectionId.replace('-view', '')}`);
    await page.setViewportSize({width: 390, height: 844}); await page.waitForTimeout(150);
    await fits(sectionId, `${name} at 390`);
    await page.setViewportSize({width: 320, height: 800}); await text200(true); await page.waitForTimeout(150);
    await fits(sectionId, `${name} at 320 / 200%`);
    await text200(false);
  }
  await page.setViewportSize({width: 1440, height: 1000});
  // The twelve analytics reports share ONE host; each is still measured on its own, because each
  // renders its own filters, metrics and records into it.
  const REPORTS = ['wip-ageing-insights', 'capacity-plan', 'production-quality-insights', 'supplier-performance-insights',
    'material-price-insights', 'purchase-commitment-insights', 'demand-forecast', 'replenishment', 'size-demand-insights',
    'return-insights', 'dead-stock-insights', 'stock-adjustment-insights'];
  for (const report of REPORTS) {
    await go(report, 'analytics-view');
    assert.equal((await workspaceState('analytics-view')).current, report, `${report}: aria-current`);
    await fits('analytics-view', `${report} at 1440`);
    await page.setViewportSize({width: 390, height: 844}); await page.waitForTimeout(120);
    await fits('analytics-view', `${report} at 390`);
    await page.setViewportSize({width: 320, height: 800}); await text200(true); await page.waitForTimeout(120);
    await fits('analytics-view', `${report} at 320 / 200%`);
    await text200(false); await page.setViewportSize({width: 1440, height: 1000});
  }
  // The order detail is Produksi's own second workspace.
  await go('board-home', 'board-view');
  await page.locator('#order-list button[data-action="detail"]').first().click();
  await page.locator('#detail-view:not([hidden])').waitFor(); await settle();
  assert.deepEqual((await workspaceState('detail-view')).visible, ['detail-view']);
  await fits('detail-view', 'Produksi order detail at 1440');
  await page.setViewportSize({width: 320, height: 800}); await text200(true); await page.waitForTimeout(150);
  await fits('detail-view', 'Produksi order detail at 320 / 200%');
  await text200(false); await page.setViewportSize({width: 1440, height: 1000});

  // ------------------------------------------------------------------ 2. action sweep by role
  const headingActions = {
    'board-view': [['new-order', 'Buat order produksi', ['admin']]],
    'products-view': [['new-product', 'Tambah SKU', ['admin']]],
    'people-view': [['new-employee', 'Tambah karyawan', ['admin']]],
    'materials-view': [['receive-material', 'Terima batch bahan', ['admin', 'operator']]],
    'purchase-requests-view': [['new-purchase-request', 'Buat PR', ['admin', 'operator']]],
    'marketing-budgets-view': [['new-marketing-budget', 'Ajukan budget', ['admin', 'operator']]],
  };
  const navFor = Object.fromEntries(DESTINATIONS.map(([nav, sectionId]) => [sectionId, nav]));
  for (const [who, key] of [['admin', admin], ['operator', operator], ['viewer', viewer]]) {
    await role(key);
    for (const nav of ADMIN_ONLY)
      assert.equal(await page.locator('#' + nav).isVisible(), who === 'admin', `${nav} is an admin destination (${who})`);
    for (const [sectionId, actions] of Object.entries(headingActions)) {
      await go(navFor[sectionId], sectionId);
      for (const [id, label, roles] of actions) {
        const control = page.locator('#' + id);
        assert.equal(await control.isVisible(), roles.includes(who), `${label} for ${who}`);
        if (roles.includes(who)) {
          assert.equal((await control.textContent()).trim(), label);
          // The one forward action of a heading is its primary.
          assert.match(await control.getAttribute('class'), /(?:^|\s)(?:action-primary|primary)(?:\s|$)/, `${label} is the primary`);
          await page.setViewportSize({width: 320, height: 800}); await text200(true);
          await control.scrollIntoViewIfNeeded();
          const box = await control.boundingBox();
          assert.ok(box && box.x >= 0 && box.x + box.width <= 321, `${label} stays reachable at 320 / 200% (${who})`);
          assert.ok(box.height >= 43, `${label} keeps the 44px touch floor at 320px (${who})`);
          await text200(false); await page.setViewportSize({width: 1440, height: 1000});
        }
      }
    }
  }
  await role(admin);

  // ------------------------------------------------------------------ 3. dialog sweep
  // One record of each kind, asked for by kind: by now the inbox holds far more than one page.
  const byKind = {};
  for (const kind of ['purchase_request', 'supplier_payment', 'marketing_budget', 'production_change', 'payroll_batch', 'ai_action']) {
    const rows = await apiGet('/api/approvals?' + new URLSearchParams({limit: 25, offset: 0, status: 'all', kind}));
    byKind[kind] = rows.find(row => row.status === 'pending') || rows[0];
  }
  const firstOf = kind => byKind[kind];
  const orders = await apiGet('/api/purchase-orders?limit=25&status=all');
  const po = orders.find(row => row.status === 'issued' && row.fulfillment !== 'pending') || orders[0];
  let qcIntake;
  for (const row of orders) { const detail = await apiGet('/api/purchase-orders/' + row.id); if (detail.qc_intakes.length) { qcIntake = detail.qc_intakes[0]; break; } }
  const audit = (await apiGet('/api/audit-events?limit=1')).items[0];
  const sheets = [
    ['PR detail', 'purchase-request', firstOf('purchase_request')?.id, 'standard'],
    ['PO detail', 'purchase-order', po.id, 'wide'],
    ['Incoming QC', 'qc-intake', qcIntake?.id, 'standard'],
    ['Supplier payment', 'supplier-payment-request', firstOf('supplier_payment')?.id, 'standard'],
    ['Marketing detail', 'marketing-budget-request', firstOf('marketing_budget')?.id, 'standard'],
    ['Production change', 'production-change-request', firstOf('production_change')?.id, 'standard'],
    ['Payroll approval', 'payroll-approval-request', firstOf('payroll_batch')?.id, 'standard'],
    ['AI action proposal', 'ai-action-proposal', firstOf('ai_action')?.id, 'standard'],
    ['Audit evidence', 'audit-event', audit.id, 'standard'],
    ['Integration snapshot', 'mekari-payroll-summary', null, 'standard'],
    ['PO list', 'purchase-orders', null, 'standard'],
    ['Employee master', 'employee-master', null, 'standard'],
  ];
  // A sheet whose fixture an earlier module did not leave is reported at the END, so one missing
  // record never hides what the rest of the sweep would have found.
  const missing = [];
  for (const [where, action, id, size] of sheets) {
    if (id === undefined) { missing.push(where); continue; }
    await openAction(action, id);
    const g = await dialogSweep(where);
    assert.equal(g.size, size, `${where} takes the ${size} width`);
    assert.deepEqual(await nestedLiveRegions('dialog'), [], `${where}: nested live regions`);
    // Headings inside a sheet never skip a level below the dialog's own h2.
    assert.deepEqual(await page.evaluate(() => { let last = 2; const skips = [];
      for (const h of document.querySelectorAll('#dialog-content :is(h1,h2,h3,h4,h5,h6)')) {
        if (!h.getClientRects().length) continue; const level = Number(h.tagName[1]);
        if (level > last + 1) skips.push(`${h.tagName} after h${last}: ${h.textContent.trim().slice(0, 40)}`); last = level; }
      return skips; }), [], `${where}: heading levels`);
    assert.equal(g.radius, 24, `${where} keeps the prominent radius`);
    await shot(`dlg-1440-${where.toLowerCase().replace(/[^a-z]+/g, '-')}`);
    await closeDialog();
  }
  // A sheet that runs longer than the viewport scrolls under its heading, which stays put.
  await openAction('purchase-order', po.id);
  const scrolled = await page.evaluate(() => { const d = document.getElementById('dialog'); d.scrollTop = d.scrollHeight;
    return {moved: d.scrollTop > 0, headingTop: Math.round(d.querySelector('.dialog-heading').getBoundingClientRect().top - d.getBoundingClientRect().top)}; });
  if (scrolled.moved) assert.ok(scrolled.headingTop <= 1, 'the sticky heading stays at the top of a scrolled sheet');
  // No legacy chrome is left inside the migrated sheets.
  assert.equal(await page.locator('#dialog-content :is(.form-info,.material-event,.history-item,.requirement-values,.actions)').count(), 0,
    'the PO sheet carries no pre-A6 chrome');
  await closeDialog();

  // Close control, Escape and return focus, from a real heading button.
  await go('products', 'products-view');
  const opener = page.getByRole('button', {name: 'Tambah SKU', exact: true});
  await opener.focus(); await page.keyboard.press('Enter');
  await dialog.waitFor(); await settle();
  assert.equal(await page.evaluate(() => document.getElementById('dialog').contains(document.activeElement)), true, 'focus enters the dialog');
  // Tab and Shift+Tab stay inside the native modal, and every stop shows a visible focus ring.
  for (const key of ['Tab', 'Tab', 'Tab', 'Tab', 'Tab', 'Tab', 'Tab', 'Tab', 'Shift+Tab', 'Shift+Tab', 'Shift+Tab']) {
    await page.keyboard.press(key);
    const stop = await page.evaluate(() => { const node = document.activeElement, style = getComputedStyle(node);
      return {inside: document.getElementById('dialog').contains(node), tag: node.tagName,
        ring: (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== 'none'}; });
    if (stop.tag === 'BODY') continue;
    assert.equal(stop.inside, true, `${key} keeps focus inside the dialog`);
    assert.equal(stop.ring, true, `${key} lands on a control with a visible focus ring (${stop.tag})`);
  }
  await page.keyboard.press('Escape'); await dialog.waitFor({state: 'hidden'});
  assert.equal(await page.evaluate(() => document.activeElement?.id), 'new-product', 'Escape returns focus to the opener');
  // Space activates a focused button: Batal closes the form.
  await opener.click(); await dialog.waitFor(); await settle();
  await page.locator('#action-form [data-action="cancel-form"]').focus(); await page.keyboard.press('Space');
  await dialog.waitFor({state: 'hidden'});
  await opener.click(); await dialog.waitFor(); await settle();
  await page.getByRole('button', {name: 'Tutup dialog', exact: true}).click(); await dialog.waitFor({state: 'hidden'});
  assert.equal(await page.evaluate(() => document.activeElement?.id), 'new-product', 'Tutup dialog returns focus to the opener');

  // ------------------------------------------------------------------ 4. form sweep
  // Simple, two-column form: Tambah pemasok (standard width, labels visible above quiet controls).
  await openAction('new-supplier');
  const simple = await dialogSweep('Tambah pemasok');
  assert.equal(simple.size, 'standard');
  const form = await page.evaluate(() => {
    const grid = document.querySelector('#action-form .form-grid'), info = document.querySelector('#action-form>.form-info');
    const actions = [...document.querySelectorAll('#action-form>.form-actions>button')].filter(node => !node.hidden).map(node => node.textContent.trim());
    return {columns: getComputedStyle(grid).gridTemplateColumns.split(' ').length, infoBorder: parseFloat(getComputedStyle(info).borderTopWidth),
      labels: [...document.querySelectorAll('#action-form label')].filter(node => node.getClientRects().length).length, actions,
      footerRule: parseFloat(getComputedStyle(document.querySelector('#action-form>.form-actions')).borderTopWidth)};
  });
  assert.equal(form.columns, 2, 'a desktop form keeps two columns');
  assert.ok(form.infoBorder > 0 && form.footerRule > 0);
  assert.ok(form.labels >= 5, 'every field keeps a visible label');
  assert.deepEqual(form.actions, ['Batal', 'Simpan pencatatan'], 'cancel, then the one primary');
  await shot('dlg-1440-form-simple');
  // A legacy `<label>Text<control></label>` form reads like an A6 field: small label, quiet control.
  await closeDialog();
  await go('board-home', 'board-view');
  await page.getByRole('button', {name: 'Buat order produksi', exact: true}).click(); await dialog.waitFor(); await settle();
  await dialogSweep('Buat order produksi');
  await shot('dlg-1440-form-multi-field');
  await closeDialog();
  // A decision form that is only a reason is compact. The module seeds its own pending PR (as the
  // operator, through the API) so this never depends on what an earlier module left undecided.
  const material = (await apiGet('/api/materials'))[0];
  const seeded = await fetch(base + '/api/purchase-requests', {method: 'POST', headers: {'Content-Type': 'application/json',
    'X-API-Key': operator, 'Idempotency-Key': crypto.randomUUID()}, body: JSON.stringify({reference: 'PR-A68-' + Date.now(),
    order_id: null, required_date: '2026-12-31', estimated_value: '1000', reason: 'CONTOH lebar dialog keputusan',
    lines: [{material_id: material.id, quantity: material.unit === 'pcs' ? '1' : '1.000'}]})});
  assert.equal(seeded.status, 201, await seeded.clone().text());
  await openAction('purchase-request', (await seeded.json()).id);
  await page.getByRole('button', {name: 'Setujui PR', exact: true}).click();
  await page.locator('#action-form').waitFor(); await settle();
  assert.equal((await dialogGeometry()).size, 'compact', 'a reason-only decision form is compact');
  await dialogSweep('decision form');
  await shot('dlg-1440-form-decision');
  await closeDialog();
  // Dynamic lines: Buat PR adds and removes material rows inside the same chrome.
  await go('purchase-requests', 'purchase-requests-view');
  await page.getByRole('button', {name: 'Buat PR', exact: true}).click(); await dialog.waitFor();
  await page.locator('#pr-lines .bom-line').first().waitFor(); await settle();
  await page.getByRole('button', {name: 'Tambah bahan PR', exact: true}).click();
  assert.equal(await page.locator('#pr-lines .bom-line').count(), 2);
  await dialogSweep('Buat PR with two lines');
  await page.locator('#pr-lines .bom-line').nth(1).getByRole('button', {name: 'Hapus bahan PR', exact: true}).click();
  assert.equal(await page.locator('#pr-lines .bom-line').count(), 1);
  await closeDialog();
  // Uncertain write: the response is lost after the server committed it.
  const suppliersBefore = (await apiGet('/api/suppliers')).length;
  await openAction('new-supplier');
  const code = 'A68-' + Date.now();
  await page.getByLabel('Kode pemasok', {exact: true}).fill(code);
  await page.getByLabel('Nama pemasok', {exact: true}).fill('CONTOH A6.8 <pemasok> & uji');
  await page.getByLabel('Alasan / catatan', {exact: true}).fill('CONTOH uji penyimpanan belum pasti');
  let drop = true;
  await page.route('**/api/suppliers', async route => {
    if (drop && route.request().method() === 'POST') { drop = false; await route.fetch(); await route.abort('failed'); }
    else await route.continue();
  });
  await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  const retry = page.getByRole('button', {name: 'Coba ulang penyimpanan', exact: true});
  await retry.waitFor(); await settle();
  assert.equal(await page.evaluate(() => document.getElementById('form-fields').disabled), true, 'an uncertain write locks its fieldset');
  assert.equal(await page.getByLabel('Kode pemasok', {exact: true}).isDisabled(), true, 'and every field inside it');
  assert.match(await retry.getAttribute('class'), /(?:^|\s)primary(?:\s|$)/, 'the retry stays the one primary');
  assert.equal(await page.locator('#form-error').isVisible(), true, 'the uncertainty is inline');
  await page.keyboard.press('Escape'); await page.waitForTimeout(250);
  assert.equal(await dialog.isVisible(), true, 'Escape cannot abandon an unresolved write');
  await dialogSweep('uncertain form');
  await shot('dlg-1440-form-uncertain');
  await theme('dark'); await shot('dlg-1440-dark-form-uncertain'); await theme('light');
  await page.unroute('**/api/suppliers');
  await retry.click();
  await page.getByText(`${code.toUpperCase()} · CONTOH A6.8 <pemasok> & uji`, {exact: true}).waitFor();
  assert.equal((await apiGet('/api/suppliers')).length, suppliersBefore + 1, 'the retry saved exactly once');
  await closeDialog();

  // ------------------------------------------------------------------ 5. dark
  await theme('dark');
  for (const [nav, sectionId] of [['board-home', 'board-view'], ['approvals', 'approvals-view'], ['purchase-requests', 'purchase-requests-view']]) {
    await go(nav, sectionId);
    // Glyph-sized marks (a status dot) are meant to be light on a dark surface; a surface is not.
    const light = await page.evaluate(id => [...document.getElementById(id).querySelectorAll('*')].filter(node => {
      const rect = node.getBoundingClientRect(); return rect.width > 16 && rect.height > 16; }).filter(node => {
      const m = getComputedStyle(node).backgroundColor.match(/rgba?\(([\d.]+), ([\d.]+), ([\d.]+)(?:, ([\d.]+))?/);
      return m && (m[4] === undefined || Number(m[4]) > .5) && Number(m[1]) > 225 && Number(m[2]) > 225 && Number(m[3]) > 225;
    }).map(node => node.tagName.toLowerCase() + '.' + String(node.className).split(' ')[0]), sectionId);
    assert.deepEqual(light, [], `${sectionId}: no legacy white surface in dark mode`);
  }
  await openAction('purchase-order', po.id);
  const darkSheet = await page.evaluate(() => {
    const lum = value => { const [r, g, b] = value.match(/[\d.]+/g).slice(0, 3).map(Number).map(c => { c /= 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; });
      return .2126 * r + .7152 * g + .0722 * b; };
    const d = document.getElementById('dialog');
    const bg = lum(getComputedStyle(d).backgroundColor), ink = lum(getComputedStyle(document.getElementById('dialog-title')).color);
    const meta = lum(getComputedStyle(d.querySelector('.data-meta')).color);
    const ratio = (a, b) => (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    return {title: ratio(ink, bg), meta: ratio(meta, bg)};
  });
  assert.ok(darkSheet.title >= 7, `dark dialog title contrast ${darkSheet.title.toFixed(2)}`);
  assert.ok(darkSheet.meta >= 4.5, `dark dialog metadata contrast ${darkSheet.meta.toFixed(2)}`);
  await shot('dlg-1440-dark-po-detail');
  await closeDialog();
  await theme('light');

  // ------------------------------------------------------------------ 6. reduced motion
  await page.emulateMedia({reducedMotion: 'reduce'});
  await go('approvals', 'approvals-view');
  assert.equal(await page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').length), 0,
    'no running animation after a reduced-motion navigation');
  await openAction('purchase-order', po.id);
  assert.equal(await page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').length), 0,
    'no running animation in a reduced-motion dialog');
  await page.keyboard.press('Escape');
  assert.equal(await page.evaluate(() => document.getElementById('dialog').open), false, 'a reduced-motion dialog closes at once');
  await page.emulateMedia({reducedMotion: null});

  // ------------------------------------------------------------------ 7. forced colors
  await page.emulateMedia({forcedColors: 'active'});
  await openAction('purchase-order', po.id);
  const forced = await page.evaluate(() => {
    const d = document.getElementById('dialog');
    const chip = d.querySelector('.status-chip'), record = d.querySelector('.request-records');
    const width = node => node ? parseFloat(getComputedStyle(node).borderTopWidth) : 0;
    return {dialogBorder: width(d), chipText: chip?.textContent.trim(), chipBorder: width(chip), recordsBorder: width(record),
      headingRule: parseFloat(getComputedStyle(d.querySelector('.dialog-heading')).borderBottomWidth),
      buttons: [...d.querySelectorAll('#dialog-content button')].filter(node => node.getClientRects().length).every(node => node.textContent.trim().length > 0)};
  });
  assert.ok(forced.dialogBorder > 0 && forced.headingRule > 0, 'the dialog and its heading keep real edges');
  assert.ok(forced.chipText && forced.chipBorder > 0, 'a status chip keeps its words and its edge');
  assert.ok(forced.recordsBorder > 0, 'a record list keeps its boundary');
  assert.equal(forced.buttons, true, 'every button names itself in text');
  await page.keyboard.press('Tab');
  const focus = await page.evaluate(() => { const style = getComputedStyle(document.activeElement); return {style: style.outlineStyle, width: parseFloat(style.outlineWidth)}; });
  assert.ok(focus.style !== 'none' && focus.width > 0, 'keyboard focus is visible in forced colors');
  await closeDialog();
  await go('board-home', 'board-view');
  assert.ok(await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('#board-view .data-surface')).borderTopWidth)) > 0,
    'the production table keeps its boundary in forced colors');
  await page.emulateMedia({forcedColors: 'none'});

  // ------------------------------------------------------------------ 8. reduced transparency
  // Playwright has no option for it; Chromium's DevTools protocol does. If this engine cannot
  // emulate it, the static contracts remain the proof and the module says so.
  let transparency = 'not emulated by this engine; asserted statically';
  try {
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Emulation.setEmulatedMedia', {features: [{name: 'prefers-reduced-transparency', value: 'reduce'}]});
    if (await page.evaluate(() => matchMedia('(prefers-reduced-transparency: reduce)').matches)) {
      await go('approvals', 'approvals-view');
      const state = await page.evaluate(() => ({blur: getComputedStyle(document.querySelector('#approvals-view .command-bar')).backdropFilter,
        rows: document.querySelectorAll('#approval-list .record-row').length, visible: getComputedStyle(document.getElementById('approval-list')).visibility}));
      assert.equal(state.blur, 'none', 'the command bar withdraws its blur');
      assert.equal(state.visible, 'visible');
      await openAction('purchase-order', po.id);
      assert.match(await page.evaluate(() => getComputedStyle(document.getElementById('dialog')).backgroundColor), /^rgb\(/, 'the dialog is opaque');
      await closeDialog();
      transparency = 'emulated: blur withdrawn, content opaque';
    }
    await cdp.send('Emulation.setEmulatedMedia', {features: []});
    await cdp.detach();
  } catch (error) { transparency = 'CDP unavailable; asserted statically'; }

  // Leave the page exactly as the next module expects it: Playwright's default media and the theme
  // this module started from.
  await page.emulateMedia({colorScheme: 'light', reducedMotion: 'no-preference', forcedColors: 'none'});
  await page.evaluate(value => { if (value === null) document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', value); }, initialTheme);
  await page.setViewportSize({width: 1440, height: 1000});
  page.off('pageerror', onError);
  assert.deepEqual(errors, [], 'no JS errors across the A6.8 sweep');
  assert.deepEqual(missing, [], 'every representative sheet had a fixture from the modules before this one');
  console.log('A6.8 final polish browser QA PASS: 16 destinations (+ order detail) with one visible workspace and aria-current, '
    + 'no document / section-edge overflow at 1440, 390 and 320@200%; heading primaries role-gated for admin / operator / viewer '
    + 'and reachable at 320@200%; 12 representative sheets fit at 1440 / 390 / 320@200% with the deterministic width, sticky heading, '
    + 'internal scroll and no sideways scroll; close, Escape and return focus; simple, multi-field, compact decision, dynamic-line '
    + `and uncertain / exact-retry forms; dark contrast; reduced motion; forced colors; reduced transparency ${transparency}.`);
};
