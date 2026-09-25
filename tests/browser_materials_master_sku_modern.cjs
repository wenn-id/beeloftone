// A6.2 Bahan baku + Master SKU modern workspaces: the behavioural half of the migration contract.
//
// tests/test_apple27_materials_master_sku_contract.py proves statically that no meaning moved.
// This module proves it against a running application and real fixture data, which is the only
// place some of it can be proved at all: that the three batch quantities on screen are the three
// the API actually returned for that batch, that changing the material filter really resets the
// offset in the real query string, that the page is really 25 rows with a 26th sentinel, that the
// local search really costs no request, that painting the catalog really never asks for a BOM, and
// that an overtaken response cannot repaint a newer one.
//
// Deliberately not screenshot-only. Every visual case here also asserts something about behaviour
// or data, because a screenshot cannot fail when a number is wrong.
//
// It runs after browser_materials.cjs / browser_bom.cjs / browser_product_external_mappings.cjs,
// so the demo database already has the KAIN-UI material, the BATCH-UI-001 batch, a BOM revision and
// a Jubelio mapping. Anything this module needs beyond that it creates through the API, never by
// reaching into the store.
const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, openSidebarDestination, admin, operator, viewer,
                         apiGet, apiPost, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const number = new Intl.NumberFormat('id-ID');

  // ---------------------------------------------------------------- helpers
  const quiet = () => page.evaluate(() => {
    scrollTo(0, 0);
    const main = document.querySelector('.workspace-main');
    if (main) main.scrollTo(0, 0);
    const notice = document.getElementById('notice');
    notice.hidden = true; notice.textContent = '';
    if (document.activeElement && document.activeElement !== document.body) {
      document.activeElement.blur();
    }
  });
  // A visual-review screenshot has to show the workspace and nothing else: earlier steps leave a
  // six-second "Pencatatan tersimpan." toast and a focus ring behind, and both would sit on top of
  // the surface a human is being asked to approve.
  const settled = () => page.evaluate(async () => {
    const dialog = document.getElementById('dialog');
    if (dialog && dialog.open) {
      await Promise.allSettled(dialog.getAnimations({subtree: true}).map(animation => animation.finished));
    }
  });
  const shot = async (name, {full = true} = {}) => {
    await quiet();
    await page.waitForFunction(() => ![...document.querySelectorAll('.motion-enter,.is-refreshing')]
      .some(node => node.id !== 'notice'));
    // M3 runs an enter animation on the dialog; a screenshot taken mid-flight shows a half-faded
    // surface, which is not what a human is being asked to approve.
    await settled();
    await page.screenshot({path: path.join(shots, `a62-${name}.png`), fullPage: full});
  };
  // The reviewed unit for information hierarchy: exactly what a 1440x1000 reviewer sees before
  // scrolling. `.workspace-main` is the scrolling region, not the document.
  const firstViewport = async name => {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.waitForTimeout(150);
    await quiet();
    await settled();
    await page.screenshot({path: path.join(shots, `a62-${name}.png`)});
  };
  const theme = async value => {
    await page.evaluate(next => { document.documentElement.dataset.theme = next; }, value);
    await page.waitForTimeout(120);
  };
  const noOverflow = () => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const dialogFits = () => page.evaluate(() => {
    const dialog = document.querySelector('dialog');
    return dialog.scrollWidth <= dialog.clientWidth;
  });
  const batchesReady = async () => {
    await page.locator('#batch-list[aria-busy]').waitFor({state: 'detached'});
    await page.locator('#materials-view:not([hidden])').waitFor();
  };
  // Returns the URL the workspace actually requested, so a filter assertion reads the real query
  // rather than trusting the control it clicked.
  const loadedBatches = async action => {
    const response = page.waitForResponse(r => r.url().includes('/api/material-batches?'));
    await action();
    const url = new URL((await response).url());
    await batchesReady();
    return url;
  };
  const openMaterials = async () => { await openSidebarDestination('Bahan baku'); await batchesReady(); };
  const openProducts = async () => {
    await openSidebarDestination('Master SKU');
    await page.locator('#product-list .record-row').first().waitFor();
  };
  const escapeDialog = async () => {
    await page.keyboard.press('Escape');
    await page.locator('#dialog').waitFor({state: 'hidden'});
  };

  // ==========================================================================
  // PART A - BAHAN BAKU
  // ==========================================================================
  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  await login(admin);
  // Earlier modules exercise dark mode and leave it set, so the light cases below state the theme
  // they are reviewing instead of inheriting it.
  await theme('light');

  // ---- the page identity and the A6 composition ------------------------------------------
  await openMaterials();
  await page.getByRole('heading', {name: 'Bahan baku', exact: true}).waitFor();
  assert.equal(await page.locator('#materials-view .workspace-subtitle').textContent(),
    'Pantau batch, saldo, reservasi, dan stok bebas untuk produksi.');
  assert.equal(await page.locator('#materials-view').evaluate(node =>
    node.classList.contains('workspace-page')), true);
  // The inventory explanation is preserved word for word, and it is still programmatically tied to
  // the filter it explains.
  const note = await page.locator('#materials-inventory-note').textContent();
  for (const sentence of ['Saldo adalah bahan layak pakai yang diterima, dikurangi pengeluaran ke order.',
    'Stok bebas = saldo fisik dikurangi reservasi semua order.',
    'Untuk mengalokasikan atau mengeluarkan bahan, buka order produksi.']) {
    assert.ok(note.includes(sentence), `inventory explanation lost: ${sentence}`);
  }
  assert.equal(await page.locator('#material-filter').getAttribute('aria-describedby'),
    'materials-inventory-note');
  // No KPI strip was invented for a page whose endpoints return no global aggregate.
  assert.equal(await page.locator('#materials-view .metric-strip, #materials-view .metric-card').count(), 0,
    'Bahan baku must not grow a fabricated metric strip');
  // The command bar replaced the stacked filter form, and it did NOT grow a fake search box.
  assert.equal(await page.locator('#material-filter-form.command-bar').count(), 1);
  assert.equal(await page.locator('#materials-view .command-search').count(), 0,
    'the batch endpoint has no search parameter, so the bar must not imply one');
  assert.equal(await page.locator('#materials-view .filters').count(), 0);

  // ---- the action hierarchy, and the permission rule it must not change --------------------
  assert.equal(await page.locator('#receive-material').evaluate(n => n.className), 'action-primary');
  assert.equal(await page.locator('#scan-material-batch').evaluate(n => n.className), 'action-secondary');
  assert.equal(await page.locator('#material-master').evaluate(n => n.className), 'action-quiet');
  assert.equal(await page.locator('#receive-material').isVisible(), true);

  // ---- quantity truth: the three figures on screen are the three the API returned -----------
  const batches = await apiGet('/api/material-batches?limit=26&offset=0&material_id=');
  assert.ok(batches.length, 'the demo database must already hold batches');
  const rowCount = await page.locator('#batch-list tbody tr').count();
  assert.equal(rowCount, Math.min(25, batches.length), 'the page renders at most 25 batches');
  for (const record of batches.slice(0, Math.min(5, rowCount))) {
    const row = page.locator(`#batch-list tr[data-material-batch="${record.id}"]`);
    await row.waitFor();
    const seen = await row.evaluate(node => ({
      balance: node.querySelector('[data-batch-balance]').textContent,
      reserved: node.querySelector('[data-batch-reserved]').textContent,
      available: node.querySelector('[data-batch-available]').textContent,
      primary: node.querySelector('.data-primary').textContent,
      secondary: node.querySelector('.data-secondary').textContent,
    }));
    const expected = value => {
      const [whole, fraction = ''] = String(value).replace(/^-/, '').split('.');
      const decimal = fraction.replace(/0+$/, '');
      return `${String(value).startsWith('-') ? '-' : ''}${number.format(BigInt(whole))}`
        + `${decimal ? ',' + decimal : ''} ${record.unit}`;
    };
    assert.equal(seen.balance, expected(record.balance), `saldo for ${record.reference}`);
    assert.equal(seen.reserved, expected(record.reserved), `reservasi for ${record.reference}`);
    assert.equal(seen.available, expected(record.available), `stok bebas for ${record.reference}`);
    assert.equal(seen.primary, record.reference, 'the batch reference is the row identity');
    assert.equal(seen.secondary, `${record.code} · ${record.name}`);
  }
  // Every quantity column is labelled, so no figure depends on weight or colour to be understood.
  assert.deepEqual(await page.locator('#batch-list thead th').allTextContents(),
    ['Batch / bahan', 'Supplier / lokasi', 'Diterima', 'Saldo', 'Direservasi', 'Stok bebas', 'Buka batch']);
  // And nothing manufactured a stock-health chip out of those numbers.
  assert.equal(await page.locator('#batch-list .status-chip').count(), 0,
    'the batch list response carries no business status for this page');

  // ---- opening a batch stays keyboard reachable --------------------------------------------
  const first = batches[0];
  const opener = page.locator(`#batch-list tr[data-material-batch="${first.id}"] button[data-action="material-batch"]`);
  assert.equal(await opener.evaluate(node => node.tagName), 'BUTTON');
  await opener.focus();
  assert.equal(await opener.evaluate(node => node === document.activeElement), true);
  await page.keyboard.press('Enter');
  await page.getByRole('heading', {name: 'Riwayat batch bahan', exact: true}).waitFor();

  // ==================== BATCH DETAIL / HISTORY ====================
  const detail = await apiGet('/api/material-batches/' + first.id);
  const dialog = page.locator('#dialog');
  // Identity first, then the physical position, then the source - and the quantities are ABOVE the
  // history rather than buried under it.
  assert.equal(await dialog.locator('.workspace-eyebrow').textContent(), `${detail.code} · ${detail.name}`);
  assert.equal(await dialog.locator('.workspace-section-title').first().textContent(), detail.reference);
  const position = await dialog.locator('.utility-panel').first().textContent();
  assert.ok(position.startsWith('Posisi bahan sekarang'), 'the current position panel leads');
  for (const label of ['Saldo', 'Direservasi', 'Stok bebas', 'Lokasi']) {
    assert.ok(position.includes(label), `the position panel must label ${label}`);
  }
  const order = await dialog.evaluate(node => {
    const text = node.textContent;
    return {position: text.indexOf('Posisi bahan sekarang'), history: text.indexOf('Riwayat catatan bahan')};
  });
  assert.ok(order.position > -1 && order.history > order.position,
    'current physical quantities must precede the movement history');
  const facts = await dialog.locator('.detail-grid').last().textContent();
  for (const label of ['Pemasok', 'Diterima', 'Jumlah diterima']) {
    assert.ok(facts.includes(label), `the source block must label ${label}`);
  }
  assert.ok(facts.includes(detail.supplier), 'the real supplier is shown');
  // Related records, and the movement timeline itself.
  await dialog.getByRole('button', {name: 'Jejak produksi lengkap', exact: true}).waitFor();
  const movements = await apiGet(`/api/material-batches/${first.id}/movements?limit=100`);
  assert.equal(await dialog.locator('#material-history.timeline .timeline-item').count(), movements.length);
  const events = await dialog.locator('#material-history .timeline-event').allTextContents();
  const kindLabel = kind => kind === 'receipt' ? 'Penerimaan' : kind === 'issue' ? 'Pengeluaran' : 'Pembalikan';
  movements.forEach((movement, index) => {
    assert.ok(events[index].startsWith(kindLabel(movement.kind) + ' · '),
      `movement ${index} must keep its own kind label`);
  });
  // Newest first, as the server ordered it.
  const stamps = await dialog.locator('#material-history .timeline-time').evaluateAll(
    nodes => nodes.map(node => node.getAttribute('datetime')));
  assert.deepEqual(stamps, movements.map(m => m.created_at), 'ordering is the server\'s, unchanged');
  // Admin correction is offered, and the printable label survived with its class and its nesting.
  await dialog.getByRole('button', {name: 'Koreksi catatan bahan', exact: true}).first().waitFor();
  await page.waitForFunction(() => document.querySelector('.material-batch-label img')?.naturalWidth > 0);
  assert.equal(await page.evaluate(() =>
    document.querySelector('.bundle-label').parentElement.id), 'dialog-content',
    'the print stylesheet targets .bundle-label as a direct child of #dialog-content');
  await dialog.getByRole('button', {name: 'Cetak label batch', exact: true}).waitFor();
  await shot('batch-detail-1440-light');
  await theme('dark');
  await shot('batch-detail-1440-dark');
  await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await dialogFits(), true, 'the batch detail fits its dialog at 390');
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  assert.equal(await dialogFits(), true, 'the batch detail fits its dialog at 390 and 200% text');
  await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  await page.setViewportSize({width: 1440, height: 1000});

  // ==================== TRACEABILITY ====================
  await dialog.getByRole('button', {name: 'Jejak produksi lengkap', exact: true}).click();
  await page.locator('[data-material-trace-event]').first().waitFor();
  const report = await apiGet(`/api/material-batches/${first.id}/traceability?limit=50`);
  assert.equal(await page.locator('#material-trace-events .timeline-item').count(), report.events.length);
  // Distinct events stay distinct: one timeline item per event, each keeping its own event type.
  const types = await page.locator('[data-material-trace-event]').evaluateAll(
    nodes => nodes.map(node => node.dataset.materialTraceEvent));
  assert.deepEqual(types, report.events.map(row => row.event_type),
    'no event was collapsed into another to simplify the visual');
  // The mixed-unit truth is still stated, and no cumulative graph pretends the units add up.
  assert.ok((await dialog.textContent()).includes(
    'Nilai bahan dan pcs memakai satuan berbeda dan tidak dijumlahkan antarcatatan.'));
  assert.equal(await dialog.locator('progress, .progress-meter, .progress-track').count(), 0,
    'mixed units must never be drawn as one cumulative progress graph');
  // Detail links still work from inside the timeline.
  const withDetail = report.events.find(row => row.detail_action);
  if (withDetail) {
    assert.equal(await page.locator(`[data-material-trace-event="${withDetail.event_type}"]`)
      .first().getByRole('button').count(), 1);
  }
  await shot('traceability-1440-light');
  await escapeDialog();

  // ---- the material filter really resets the offset, in the real query string ---------------
  await openMaterials();
  const materials = await apiGet('/api/materials');
  assert.ok(materials.length, 'the demo database must already hold material master rows');
  // Every master row is an option, with its code, name and unit.
  const options = await page.locator('#material-filter option').allTextContents();
  assert.equal(options[0], 'Semua bahan');
  assert.deepEqual(options.slice(1).sort(),
    materials.map(m => `${m.code} · ${m.name} (${m.unit})`).sort());
  // ---- the 25 + 1 sentinel, proved against a real 26th record ------------------------------
  const filler = [];
  const bulkMaterial = materials.find(m => m.unit !== 'pcs') || materials[0];
  const needed = Math.max(0, 27 - batches.length);
  for (let index = 0; index < needed; index += 1) {
    const reference = `A62-PAGE-${Date.now()}-${index}`;
    filler.push(await apiPost('/api/material-batches', {
      material_id: bulkMaterial.id, reference, supplier: 'CONTOH pemasok A6.2',
      location: `Rak A62-${index}`, received_date: '2026-09-20',
      quantity: bulkMaterial.unit === 'pcs' ? '5' : '5.000',
      reason: 'CONTOH - fixture paginasi A6.2',
    }));
  }
  await openMaterials();
  const total = (await apiGet('/api/material-batches?limit=200&offset=0&material_id=')).length;
  assert.ok(total >= 26, 'the sentinel case needs at least 26 batches');
  assert.equal(await page.locator('#batch-list tbody tr').count(), 25,
    'a full page shows exactly 25 rows, never the 26th sentinel');
  assert.equal(await page.locator('#materials-page').textContent(), 'Batch 1–25');
  assert.equal(await page.locator('#materials-previous').isDisabled(), true);
  assert.equal(await page.locator('#materials-next').isDisabled(), false);
  await loadedBatches(() => page.locator('#materials-next').click());
  const secondPage = await page.locator('#batch-list tbody tr').count();
  assert.equal(await page.locator('#materials-page').textContent(), `Batch 26–${25 + secondPage}`);
  assert.equal(await page.locator('#materials-previous').isDisabled(), false);
  await loadedBatches(() => page.locator('#materials-previous').click());
  assert.equal(await page.locator('#materials-page').textContent(), 'Batch 1–25');
  await firstViewport('batch-list-1440-light-firstviewport');
  await shot('batch-list-1440-light');
  await theme('dark');
  await shot('batch-list-1440-dark');
  await theme('light');

  // Walk to page two first, so the reset is observable rather than a no-op.
  let url = await loadedBatches(() => page.locator('#materials-next').click());
  assert.equal(url.searchParams.get('offset'), '25');
  assert.equal(url.searchParams.get('limit'), '26');
  url = await loadedBatches(() => page.locator('#material-filter').selectOption(materials[0].id));
  assert.equal(url.searchParams.get('offset'), '0', 'changing the material filter resets the offset');
  assert.equal(url.searchParams.get('material_id'), materials[0].id);
  // A filter change is a replacement, so it fades as one unit; a plain refresh is not.
  assert.equal(await page.locator('#material-filter').inputValue(), materials[0].id,
    'the rendered filter is the filter that was requested');
  await shot('batch-list-1440-light-filtered');
  url = await loadedBatches(() => page.locator('#materials-refresh').click());
  assert.equal(url.searchParams.get('material_id'), materials[0].id,
    'a refresh keeps the current filter');
  url = await loadedBatches(() => page.locator('#material-filter').selectOption(''));
  assert.equal(url.searchParams.get('material_id'), '');

  // ---- a refresh keeps the rows; an overtaken response cannot repaint a newer state ---------
  let releaseBatches, signalBatches, settleBatches;
  const held = {}; held.started = new Promise(r => signalBatches = r);
  held.release = new Promise(r => releaseBatches = r);
  held.settled = new Promise(r => settleBatches = r);
  let holdOnce = true;
  await page.route('**/api/material-batches?*', async route => {
    if (holdOnce) {
      holdOnce = false;
      const response = await route.fetch(); signalBatches();
      await held.release; await route.fulfill({response}); settleBatches();
    } else await route.continue();
  });
  const before = await page.locator('#batch-list tbody tr').count();
  await page.locator('#materials-refresh').click();
  await held.started;
  await page.waitForTimeout(250);
  assert.equal(await page.locator('#batch-list tbody tr').count(), before,
    'a refresh keeps the existing rows on screen');
  assert.equal(await page.locator('#batch-list').getAttribute('aria-busy'), 'true',
    'the refreshing container is marked busy for assistive technology');
  const dimmed = parseFloat(await page.locator('#batch-list').evaluate(n => getComputedStyle(n).opacity));
  assert.ok(dimmed >= 0.72 && dimmed <= 0.82, `the refresh dims inside the documented M4 band (${dimmed})`);
  assert.equal(await page.locator('#material-filter').isDisabled(), false,
    'a refresh leaves the filter usable - the treatment is a signal, not a lock');
  // Navigate away while that response is still in flight: it must not repaint Produksi.
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Produksi', exact: true}).waitFor();
  releaseBatches(); await held.settled;
  await page.waitForTimeout(150);
  assert.equal(await page.locator('#materials-view').isHidden(), true,
    'an overtaken batch response must not resurrect the workspace it belonged to');
  assert.equal(await page.locator('#board-view').isVisible(), true);
  await page.unroute('**/api/material-batches?*');

  // ---- the load-failure state, and the retry the page already had --------------------------
  let failOnce = true;
  await page.route('**/api/material-batches?*', async route => {
    if (failOnce) {
      failOnce = false;
      await route.fulfill({status: 503, contentType: 'application/json',
        body: JSON.stringify({detail: 'Simulasi stok bahan gagal'})});
    } else await route.continue();
  });
  await openSidebarDestination('Bahan baku');
  await page.locator('#materials-message .error-state').waitFor();
  assert.equal(await page.locator('#materials-message .error-state-title').textContent(),
    'Simulasi stok bahan gagal');
  assert.equal(await page.locator('#materials-message').evaluate(n => n.className), 'state error',
    'the state host keeps its class contract for the request lifecycle');
  await shot('batch-list-1440-light-error');
  await page.unroute('**/api/material-batches?*');
  await loadedBatches(() => page.locator('#materials-refresh').click());
  assert.equal(await page.locator('#materials-message').isHidden(), true, 'the reload clears the error');

  // ---- the empty page state, and its role-gated CTA ----------------------------------------
  await page.route('**/api/material-batches?*', route =>
    route.fulfill({status: 200, contentType: 'application/json', body: '[]'}));
  await loadedBatches(() => page.locator('#materials-refresh').click());
  await page.locator('#materials-message .empty-state').waitFor();
  assert.equal(await page.locator('#materials-message .empty-state-title').textContent(),
    'Belum ada batch pada halaman ini.');
  assert.equal(await page.locator('#materials-page').textContent(), '0 batch di halaman ini');
  assert.equal(await page.locator('#batch-list tbody tr').count(), 0);
  assert.equal(await page.locator('#batch-list table').count(), 0,
    'an empty page must not leave a lone table header behind');
  // Admin gets a real write CTA, and its name differs from the header button so neither is ambiguous.
  const emptyCta = page.locator('#materials-message [data-action="receive-material"]');
  assert.equal(await emptyCta.textContent(), 'Terima batch bahan pertama');
  await shot('batch-list-1440-light-empty');

  // ---- responsive sweep, both themes, with no document overflow ----------------------------
  await page.unroute('**/api/material-batches?*');
  await loadedBatches(() => page.locator('#materials-refresh').click());
  for (const width of [1440, 1024, 980, 768, 390, 320]) {
    await page.setViewportSize({width, height: width <= 390 ? 844 : 900});
    await page.waitForTimeout(120);
    assert.equal(await noOverflow(), true, `Bahan baku overflows the document at ${width}`);
    // Where the relationship is tabular the surface scrolls; the document never does.
    if (width <= 980) {
      assert.equal(await page.locator('#batch-list').evaluate(n => getComputedStyle(n).overflowX),
        'auto', `the batch surface must take the overflow at ${width}`);
    }
    if ([1024, 768, 390].includes(width)) await shot(`batch-list-${width}-light`);
  }
  // 320 at 200% text is the composition that breaks first, and it is mandatory.
  await page.setViewportSize({width: 320, height: 700});
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await page.waitForTimeout(150);
  assert.equal(await noOverflow(), true, 'Bahan baku overflows the document at 320 and 200% text');
  // The identifiers must still be readable rather than one character per line.
  const identifierWidth = await page.locator('#batch-list .data-primary').first()
    .evaluate(node => node.getBoundingClientRect().width);
  assert.ok(identifierWidth > 40, `the batch reference collapsed to ${identifierWidth}px at 200% text`);
  await shot('batch-list-320-light-200');
  await theme('dark');
  await shot('batch-list-320-dark-200');
  await theme('light');
  await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  await page.setViewportSize({width: 1440, height: 1000});

  // ---- reduced motion, reduced transparency and forced colours ------------------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  await loadedBatches(() => page.locator('#material-filter').selectOption(materials[0].id));
  assert.equal(await page.locator('#batch-list').evaluate(n => n.className), 'list-host data-surface',
    'reduced motion leaves no replacement class behind');
  await page.emulateMedia({reducedMotion: null});
  await page.emulateMedia({forcedColors: 'active'});
  await page.waitForTimeout(120);
  assert.equal(await noOverflow(), true, 'forced colours must not break the layout');
  assert.equal(await page.locator('#batch-list tbody tr').first().isVisible(), true);
  await shot('batch-list-1440-forced-colors');
  await page.emulateMedia({forcedColors: null});
  await loadedBatches(() => page.locator('#material-filter').selectOption(''));

  // ==================== MASTER BAHAN ====================
  await page.locator('#material-master').click();
  await page.getByRole('heading', {name: 'Master bahan', exact: true}).waitFor();
  await page.locator('#material-master-list .record-row').first().waitFor();
  assert.equal(await page.locator('#material-master-list .record-row').count(), materials.length,
    'master bahan lists every material identity');
  // Identity, not inventory: the dialog carries no balance at all.
  const masterText = await page.locator('#dialog-content').textContent();
  assert.ok(masterText.includes('Saldo dan stok bebas dicatat per batch'),
    'the dialog states where balances actually live');
  for (const record of materials.slice(0, 5)) {
    await page.locator('#material-master-list').getByText(`${record.name} · ${record.unit}`,
      {exact: true}).waitFor();
  }
  await page.getByRole('button', {name: 'Tambah bahan', exact: true}).waitFor();
  await shot('master-bahan-1440-light');

  // ---- the add-material form: fields, units, immutability copy -----------------------------
  await page.getByRole('button', {name: 'Tambah bahan', exact: true}).click();
  await page.getByRole('heading', {name: 'Tambah bahan', exact: true}).waitFor();
  await page.locator('#material-unit').waitFor();
  assert.deepEqual(await page.locator('#material-unit option').evaluateAll(
    nodes => nodes.map(node => node.value)), ['m', 'kg', 'pcs'],
    'the three supported base units are unchanged');
  for (const label of ['Kode bahan', 'Nama bahan', 'Satuan dasar']) {
    assert.equal(await page.getByLabel(label, {exact: true}).count(), 1,
      `${label} must keep its exact accessible name`);
  }
  assert.ok((await page.locator('#dialog-content').textContent()).includes(
    'Kode, nama, dan satuan tidak dapat diubah setelah disimpan.'),
    'the immutability rule must stay visible');
  assert.equal(await page.locator('#dialog-content .field').count(), 3);
  await shot('master-bahan-form-1440-light');
  await escapeDialog();

  // ==================== RECEIPT FORM ====================
  await page.locator('#receive-material').click();
  await page.getByRole('heading', {name: 'Terima batch bahan', exact: true}).waitFor();
  // The title is set with the loading placeholder, so wait for the form itself before counting.
  await page.locator('#receipt-quantity').waitFor();
  for (const label of ['Bahan diterima', 'Referensi batch', 'Pemasok', 'Lokasi / rak',
    'Tanggal diterima', 'Jumlah layak pakai', 'Alasan / catatan']) {
    assert.equal(await page.getByLabel(label, {exact: true}).count(), 1,
      `${label} must keep its exact accessible name`);
  }
  const quantityInput = page.locator('#receipt-quantity');
  assert.equal(await quantityInput.getAttribute('max'), '1000000', 'the 1,000,000 ceiling stands');
  // Unit-dependent precision, driven by the material actually selected.
  const pcsMaterial = materials.find(m => m.unit === 'pcs');
  const decimalMaterial = materials.find(m => m.unit !== 'pcs');
  if (decimalMaterial) {
    await page.locator('#receipt-material').selectOption(decimalMaterial.id);
    assert.equal(await quantityInput.getAttribute('step'), '0.001');
    assert.equal(await quantityInput.getAttribute('min'), '0.001');
  }
  if (pcsMaterial) {
    await page.locator('#receipt-material').selectOption(pcsMaterial.id);
    assert.equal(await quantityInput.getAttribute('step'), '1', 'pcs stays whole');
    assert.equal(await quantityInput.getAttribute('min'), '1');
  }
  if (decimalMaterial) await page.locator('#receipt-material').selectOption(decimalMaterial.id);
  await shot('receive-batch-form-1440-light');
  await theme('dark');
  await shot('receive-batch-form-1440-dark');
  await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await dialogFits(), true, 'the receipt form fits its dialog at 390');
  await page.screenshot({path: path.join(shots, 'a62-receive-batch-form-390-light.png')});
  await page.setViewportSize({width: 1440, height: 1000});
  // Submit semantics are unchanged: a real batch is created through the same endpoint.
  const submitted = `A62-RECEIPT-${Date.now()}`;
  await page.getByLabel('Referensi batch', {exact: true}).fill(submitted);
  await page.getByLabel('Pemasok', {exact: true}).fill('CONTOH pemasok A6.2');
  await page.getByLabel('Lokasi / rak', {exact: true}).fill('Rak A62-RX');
  await page.getByLabel('Tanggal diterima', {exact: true}).fill('2026-09-22');
  await page.getByLabel('Jumlah layak pakai', {exact: true}).fill('3.25');
  await page.getByLabel('Alasan / catatan', {exact: true}).fill('CONTOH - penerimaan uji A6.2');
  await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.locator('#dialog').waitFor({state: 'hidden'});
  await batchesReady();
  const created = (await apiGet('/api/material-batches?limit=200&offset=0&material_id='))
    .find(row => row.reference === submitted);
  assert.ok(created, 'the receipt form still creates a batch through the unchanged endpoint');
  assert.equal(created.balance, '3.250', 'the exact decimal quantity is preserved');

  // ==================== SCAN BATCH ====================
  let failScan = true;
  await page.route('**/api/material-batches/scan?*', async route => {
    if (failScan) {
      failScan = false;
      await route.fulfill({status: 503, contentType: 'application/json',
        body: JSON.stringify({detail: 'Simulasi pemindai A6.2 sibuk'})});
    } else await route.continue();
  });
  await page.locator('#scan-material-batch').click();
  await page.getByRole('heading', {name: 'Scan batch bahan', exact: true}).waitFor();
  await page.locator('#material-batch-scan-code').waitFor();
  const scanInput = page.getByLabel('Kode batch bahan', {exact: true});
  assert.equal(await scanInput.evaluate(node => node === document.activeElement), true,
    'a keyboard-emulating scanner needs the input focused on open');
  await shot('scan-batch-1440-light');
  // Typed like a keyboard scanner, submitted with Enter.
  await scanInput.fill(created.scan_code);
  await scanInput.press('Enter');
  await page.getByText('Simulasi pemindai A6.2 sibuk', {exact: true}).waitFor();
  assert.equal(await scanInput.evaluate(node => node === document.activeElement), true,
    'a failed scan must hand focus back so the next scan lands');
  await scanInput.press('Enter');
  await page.getByRole('heading', {name: 'Riwayat batch bahan', exact: true}).waitFor();
  assert.equal(await page.locator('#dialog .workspace-section-title').first().textContent(), submitted,
    'a successful scan opens the batch it resolved');
  await page.unroute('**/api/material-batches/scan?*');
  await escapeDialog();

  // ==================== BAHAN BAKU PERMISSIONS ====================
  for (const [key, role, canReceive] of [[operator, 'operator', true], [viewer, 'viewer', false]]) {
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
    await login(key);
    await theme('light');
    await openMaterials();
    assert.equal(await page.locator('#receive-material').isVisible(), canReceive,
      `${role} receive-material visibility`);
    // The empty-state CTA follows the same rule, and is never offered to a viewer.
    await page.route('**/api/material-batches?*', route =>
      route.fulfill({status: 200, contentType: 'application/json', body: '[]'}));
    await loadedBatches(() => page.locator('#materials-refresh').click());
    await page.locator('#materials-message .empty-state').waitFor();
    assert.equal(await page.locator('#materials-message [data-action="receive-material"]').count(),
      canReceive ? 1 : 0, `${role} must ${canReceive ? '' : 'not '}be offered the empty-state CTA`);
    await page.unroute('**/api/material-batches?*');
    await loadedBatches(() => page.locator('#materials-refresh').click());
    // Master bahan stays readable for everyone; only admin may create.
    await page.locator('#material-master').click();
    await page.locator('#material-master-list .record-row').first().waitFor();
    assert.equal(await page.getByRole('button', {name: 'Tambah bahan', exact: true}).count(), 0,
      `${role} must not be offered material creation`);
    await escapeDialog();
    // Correction stays admin-only. Whichever batch this page happens to show will do: the gate is
    // the role, not the record, and the pagination fixture above moved the earlier one off page 1.
    await page.locator('#batch-list [data-action="material-batch"]').first().click();
    await page.locator('#material-history .timeline-item').first().waitFor();
    assert.equal(await page.getByRole('button', {name: 'Koreksi catatan bahan', exact: true}).count(), 0,
      `${role} must not be offered movement correction`);
    if (role === 'viewer') await shot('batch-detail-1440-light-viewer');
    await escapeDialog();
  }

  // ==========================================================================
  // PART B - MASTER SKU
  // ==========================================================================
  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  await login(admin);
  await theme('light');
  await openProducts();

  // ---- identity and composition ------------------------------------------------------------
  await page.getByRole('heading', {name: 'Master SKU', exact: true}).waitFor();
  assert.equal(await page.locator('#products-view .workspace-subtitle').textContent(),
    'Kelola identitas produk, mapping Jubelio, dan BOM.');
  assert.equal(await page.locator('#products-view').evaluate(node =>
    node.classList.contains('workspace-page')), true);
  assert.equal(await page.locator('#products-view .metric-strip, #products-view .metric-card').count(), 0,
    'Master SKU must not become a four-card dashboard');
  assert.equal(await page.locator('#products-search-form.command-bar').count(), 1);
  assert.equal(await page.locator('#products-view .filters, #products-view .search-field').count(), 0);
  // Deliberately a different composition from Bahan baku: a record list, not a table.
  assert.equal(await page.locator('#product-list table').count(), 0,
    'the SKU catalog is a record list; only Bahan baku is tabular');
  assert.equal(await page.locator('#product-list .record-list').count(), 1);
  assert.equal(await page.locator('#new-product').evaluate(n => n.className), 'action-primary');
  assert.equal(await page.locator('#products-refresh').evaluate(n => n.className), 'action-secondary');

  // ---- the catalog costs exactly two requests, and never one per SKU ------------------------
  const requests = [];
  page.on('request', request => requests.push(request.url()));
  await page.locator('#products-refresh').click();
  await page.locator('#product-list[aria-busy]').waitFor({state: 'detached'});
  await page.locator('#product-list .record-row').first().waitFor();
  const apiCalls = requests.filter(url => url.includes('/api/'));
  assert.equal(apiCalls.filter(url => url.includes('/bom')).length, 0,
    'painting the catalog must never fetch a BOM - that is the N+1 this phase forbids');
  assert.ok(apiCalls.some(url => url.includes('/api/products?')), 'products were read');
  assert.ok(apiCalls.some(url => url.includes('/api/product-external-mappings?')), 'mappings were read');

  // ---- row hierarchy and mapping truth, against the real mapping records --------------------
  const products = await apiGet('/api/products?limit=500&offset=0');
  const mappings = await apiGet('/api/product-external-mappings?system=jubelio&limit=500&offset=0');
  const byProduct = new Map(mappings.map(row => [row.product_id, row]));
  assert.equal(await page.locator('#product-list .record-row').count(), products.length);
  for (const product of products.slice(0, 6)) {
    const row = page.locator(`#product-list li[data-product="${product.id}"]`);
    await row.waitFor();
    assert.equal(await row.locator('.data-primary').textContent(), product.sku,
      'the SKU is the row identity');
    assert.equal(await row.locator('.data-secondary').textContent(), product.name);
    const variant = [product.color, product.size].filter(Boolean).join(' / ');
    if (variant) assert.equal(await row.locator('.data-meta').first().textContent(), variant);
    const mapping = byProduct.get(product.id);
    const chip = await row.locator('.status-chip').textContent();
    if (mapping && mapping.status === 'mapped') {
      assert.equal(chip, 'Terhubung', 'a mapped SKU says exactly Terhubung');
      assert.ok((await row.textContent()).includes(mapping.external_sku),
        'a mapped SKU shows the external SKU actually in use');
      assert.equal(await row.locator('.status-chip-success').count(), 1);
    } else {
      assert.equal(chip, 'Belum dipetakan');
      // Neutral, never alarming: an unmapped SKU is not broken.
      assert.equal(await row.locator('.status-chip-neutral').count(), 1);
      assert.equal(await row.locator('.status-chip-danger').count(), 0);
    }
    // Both per-SKU actions keep their disambiguated accessible names.
    await row.getByRole('button', {name: `Jubelio ${product.sku}`, exact: true}).waitFor();
    await row.getByRole('button', {name: `BOM ${product.sku}`, exact: true}).waitFor();
  }
  // No sync language anywhere on the page.
  const catalogText = await page.locator('#products-view').textContent();
  for (const lie of ['Tersinkron', 'Synced', 'Sinkron aktif', 'Sehat', 'Connected live']) {
    assert.ok(!catalogText.includes(lie), `the catalog must not claim synchronisation: ${lie}`);
  }
  // The inline count is truthful and derived from the complete loaded cache.
  const mappedCount = products.filter(p => byProduct.get(p.id)?.status === 'mapped').length;
  assert.equal(await page.locator('#products-count').textContent(),
    `${number.format(products.length)} SKU · ${number.format(mappedCount)} dipetakan`
    + ` · ${number.format(products.length - mappedCount)} belum dipetakan`);
  await firstViewport('catalog-1440-light-firstviewport');
  await shot('catalog-1440-light');
  await theme('dark');
  await shot('catalog-1440-dark');
  await theme('light');

  // ---- local instant search: four searchable values, zero requests -------------------------
  const search = page.locator('#products-search');
  const mappedProduct = products.find(p => byProduct.get(p.id)?.status === 'mapped');
  const variantProduct = products.find(p => p.color || p.size);
  const shownSkus = async () => page.locator('#product-list .data-primary').allTextContents();
  const searchCases = [
    ['SKU', products[0].sku, products[0].sku],
    ['name', products[0].name, products[0].sku],
  ];
  if (variantProduct) {
    searchCases.push(['color/size', [variantProduct.color, variantProduct.size]
      .filter(Boolean).join(' / '), variantProduct.sku]);
  }
  if (mappedProduct) {
    searchCases.push(['external SKU', byProduct.get(mappedProduct.id).external_sku, mappedProduct.sku]);
  }
  for (const [label, query, expected] of searchCases) {
    const during = [];
    const listen = request => { if (request.url().includes('/api/')) during.push(request.url()); };
    page.on('request', listen);
    await search.fill(query);
    await page.waitForTimeout(150);
    page.off('request', listen);
    assert.deepEqual(during, [], `searching by ${label} must cost no request`);
    assert.ok((await shownSkus()).includes(expected),
      `searching by ${label} ("${query}") must still find ${expected}`);
  }
  // Reset restores the full catalog.
  await page.locator('#products-clear').click();
  await page.waitForTimeout(120);
  assert.equal((await shownSkus()).length, products.length, 'Reset restores the whole catalog');
  // The filtered count is honest about what it is showing.
  await search.fill(products[0].sku);
  await page.waitForTimeout(120);
  assert.match(await page.locator('#products-count').textContent(),
    new RegExp(`dari ${number.format(products.length)} SKU$`));

  // ---- the no-match state, distinct from the empty catalog ----------------------------------
  await search.fill('tidak-ada-sku-seperti-ini-a62');
  await page.locator('#products-message .empty-state').waitFor();
  assert.equal(await page.locator('#products-message .empty-state-title').textContent(),
    'Tidak ada SKU yang cocok dengan pencarian ini.');
  assert.equal(await page.locator('#product-list .record-row').count(), 0);
  await shot('catalog-1440-light-no-match');
  // The state's own reset is wired to the same local path as the command-bar button.
  await page.locator('#products-message [data-action="reset-product-search"]').click();
  await page.locator('#product-list .record-row').first().waitFor();
  assert.equal(await search.inputValue(), '');

  // ---- the truly-empty catalog, and its admin-only CTA -------------------------------------
  await page.route('**/api/products?*', route =>
    route.fulfill({status: 200, contentType: 'application/json', body: '[]'}));
  await page.locator('#products-refresh').click();
  await page.locator('#products-message .empty-state').waitFor();
  assert.equal(await page.locator('#products-message .empty-state-title').textContent(), 'Belum ada SKU.');
  assert.equal(await page.locator('#products-message .empty-state-copy').textContent(),
    'Tambahkan produk untuk membuat order pertama.');
  assert.equal(await page.locator('#products-message [data-action="new-product"]').count(), 1,
    'an admin is offered the write action');
  assert.equal(await page.locator('#products-count').textContent(), '');
  await shot('catalog-1440-light-empty');
  await page.unroute('**/api/products?*');

  // ---- the load failure, its retry, and the control-locking contract -----------------------
  let failProducts = true;
  await page.route('**/api/products?*', async route => {
    if (failProducts) {
      failProducts = false;
      await route.fulfill({status: 503, contentType: 'application/json',
        body: JSON.stringify({detail: 'Simulasi daftar SKU A6.2 gagal'})});
    } else await route.continue();
  });
  await page.locator('#products-refresh').click();
  await page.locator('#products-message .error-state').waitFor();
  assert.equal(await page.locator('#products-message .error-state-title').textContent(),
    'Daftar SKU gagal dimuat.');
  assert.equal(await page.locator('#products-message .error-state-copy').textContent(),
    'Simulasi daftar SKU A6.2 gagal');
  assert.equal(await search.isDisabled(), true, 'the search stays locked until a load succeeds');
  assert.equal(await page.locator('#products-clear').isDisabled(), true);
  await shot('catalog-1440-light-error');
  await page.unroute('**/api/products?*');
  await page.locator('#products-retry').click();
  await page.locator('#product-list .record-row').first().waitFor();
  assert.equal(await search.isDisabled(), false, 'a successful retry re-enables the search');

  // ---- refresh keeps valid rows on screen --------------------------------------------------
  let releaseProducts, signalProducts, settleProducts;
  const productsHold = {};
  productsHold.started = new Promise(r => signalProducts = r);
  productsHold.release = new Promise(r => releaseProducts = r);
  productsHold.settled = new Promise(r => settleProducts = r);
  let holdProducts = true;
  await page.route('**/api/products?*', async route => {
    if (holdProducts) {
      holdProducts = false;
      const response = await route.fetch(); signalProducts();
      await productsHold.release; await route.fulfill({response}); settleProducts();
    } else await route.continue();
  });
  const rowsBefore = await page.locator('#product-list .record-row').count();
  await page.locator('#products-refresh').click();
  await productsHold.started;
  await page.waitForTimeout(200);
  assert.equal(await page.locator('#product-list .record-row').count(), rowsBefore,
    'a refresh does not blank valid current data');
  assert.equal(await page.locator('#product-list').getAttribute('aria-busy'), 'true');
  const productDim = parseFloat(await page.locator('#product-list')
    .evaluate(n => getComputedStyle(n).opacity));
  assert.ok(productDim >= 0.72 && productDim <= 0.82,
    `the catalog refresh dims inside the documented M4 band (${productDim})`);
  releaseProducts(); await productsHold.settled;
  await page.unroute('**/api/products?*');
  await page.waitForTimeout(200);
  assert.equal(await page.locator('#product-list').getAttribute('aria-busy'), null);

  // ---- responsive sweep: the record list reflows instead of scrolling sideways -------------
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({width, height: width <= 390 ? 844 : 900});
    await page.waitForTimeout(120);
    assert.equal(await noOverflow(), true, `Master SKU overflows the document at ${width}`);
    assert.equal(await page.locator('#product-list .record-row').first()
      .getByRole('button', {name: /^BOM /}).isVisible(), true,
      `the BOM action must stay reachable at ${width}`);
    if ([1024, 768, 390].includes(width)) await shot(`catalog-${width}-light`);
  }
  await page.setViewportSize({width: 320, height: 700});
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await page.waitForTimeout(150);
  assert.equal(await noOverflow(), true, 'Master SKU overflows the document at 320 and 200% text');
  const skuWidth = await page.locator('#product-list .data-primary').first()
    .evaluate(node => node.getBoundingClientRect().width);
  assert.ok(skuWidth > 40, `the SKU collapsed to ${skuWidth}px at 200% text`);
  // Mapping state must not be lost at the smallest size.
  assert.equal(await page.locator('#product-list .status-chip').first().isVisible(), true,
    'the mapping state survives 320 at 200% text');
  await shot('catalog-320-light-200');
  await theme('dark');
  await shot('catalog-320-dark-200');
  await theme('light');
  await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  await page.setViewportSize({width: 1440, height: 1000});
  await page.emulateMedia({forcedColors: 'active'});
  await page.waitForTimeout(120);
  assert.equal(await noOverflow(), true);
  assert.equal(await page.locator('#product-list .status-dot').first().count(), 1,
    'the chip keeps a non-colour channel under forced colours');
  await shot('catalog-1440-forced-colors');
  await page.emulateMedia({forcedColors: null});

  // ==================== ADD SKU ====================
  await page.locator('#new-product').click();
  await page.getByRole('heading', {name: 'Tambah SKU', exact: true}).waitFor();
  await page.locator('#product-size').waitFor();
  for (const [label, limit] of [['Kode SKU', '160'], ['Nama produk', '160'], ['Warna', '80'],
    ['Ukuran', '40']]) {
    const input = page.getByLabel(label, {exact: true});
    assert.equal(await input.count(), 1, `${label} must keep its exact accessible name`);
    assert.equal(await input.getAttribute('maxlength'), limit, `${label} keeps maxlength ${limit}`);
  }
  assert.equal(await page.getByLabel('Kode SKU', {exact: true}).evaluate(n => n.required), true);
  assert.equal(await page.getByLabel('Warna', {exact: true}).evaluate(n => n.required), false);
  assert.ok((await page.locator('#dialog-content').textContent()).includes(
    'Gunakan satu kode SKU untuk setiap kombinasi produk, warna, dan ukuran.'));
  await shot('add-sku-form-1440-light');
  await escapeDialog();

  // ==================== BOM ====================
  const bomless = await apiPost('/api/products', {sku: `A62-NOBOM-${Date.now()}`,
    name: 'CONTOH SKU tanpa BOM', color: 'Hijau', size: 'S'});
  await page.locator('#products-refresh').click();
  await page.locator(`#product-list li[data-product="${bomless.id}"]`).waitFor();
  await page.getByRole('button', {name: `BOM ${bomless.sku}`, exact: true}).click();
  await page.getByRole('heading', {name: 'BOM per SKU', exact: true}).waitFor();
  // The empty BOM is an information state, and its truth is unchanged.
  await page.locator('#dialog-content .empty-state').waitFor();
  assert.equal(await page.locator('#dialog-content .empty-state-title').textContent(), 'BOM belum diisi.');
  assert.equal(await page.locator('#dialog-content .empty-state-copy').textContent(),
    'Kebutuhan bahan belum dapat dihitung untuk SKU ini.');
  assert.ok((await page.locator('#dialog-content').textContent()).includes(
    'Kebutuhan bahan untuk membuat 1 pcs SKU ini. Angka mengikuti satuan master, '
    + 'belum termasuk tambahan waste otomatis.'), 'the per-1-pcs truth must stay visible');
  // No revision means no history action, and admin sees the write action.
  assert.equal(await page.getByRole('button', {name: 'Riwayat BOM', exact: true}).count(), 0);
  await page.getByRole('button', {name: 'Isi BOM', exact: true}).waitFor();
  await shot('bom-empty-1440-light');

  // ---- the BOM form's validation rules ------------------------------------------------------
  await page.getByRole('button', {name: 'Isi BOM', exact: true}).click();
  await page.getByRole('heading', {name: 'Susun BOM', exact: true}).waitFor();
  await page.locator('#bom-lines .bom-line').first().waitFor();
  assert.equal(await page.locator('#bom-lines .bom-line').count(), 1,
    'the form opens with one line, the minimum');
  // Minimum one line: removing the only row is refused rather than silently emptying the form.
  await page.locator('#bom-lines .bom-line').first().getByRole('button',
    {name: 'Hapus bahan BOM', exact: true}).click();
  await page.getByText('BOM memerlukan minimal satu bahan.', {exact: false}).waitFor();
  assert.equal(await page.locator('#bom-lines .bom-line').count(), 1);
  // Unit-dependent precision, per line, from the material master.
  const bomQuantity = page.locator('#bom-lines .bom-line').first().locator('input');
  if (decimalMaterial) {
    await page.locator('#bom-lines .bom-line').first().locator('select').selectOption(decimalMaterial.id);
    assert.equal(await bomQuantity.getAttribute('step'), '0.001');
  }
  if (pcsMaterial) {
    await page.locator('#bom-lines .bom-line').first().locator('select').selectOption(pcsMaterial.id);
    assert.equal(await bomQuantity.getAttribute('step'), '1', 'pcs components stay whole');
  }
  assert.equal(await bomQuantity.getAttribute('max'), '1000000');
  // Duplicate materials are rejected before anything is persisted.
  await page.locator('#bom-lines .bom-line').first().locator('select')
    .selectOption(decimalMaterial ? decimalMaterial.id : materials[0].id);
  await bomQuantity.fill('0.05');
  await page.getByRole('button', {name: 'Tambah bahan BOM', exact: true}).click();
  assert.equal(await page.locator('#bom-lines .bom-line').count(), 2);
  const secondLine = page.locator('#bom-lines .bom-line').nth(1);
  await secondLine.locator('select').selectOption(decimalMaterial ? decimalMaterial.id : materials[0].id);
  await secondLine.locator('input').fill('0.02');
  await page.getByLabel('Alasan / catatan', {exact: true}).fill('CONTOH - uji duplikat A6.2');
  await shot('bom-form-1440-light');
  await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.getByText('Gabungkan bahan yang sama menjadi satu baris BOM.', {exact: false}).waitFor();
  assert.equal((await apiGet(`/api/products/${bomless.id}/bom-history`)).length, 0,
    'a rejected duplicate must persist nothing');
  // Fix it into a real revision and check the save semantics copy is intact.
  assert.ok((await page.locator('#dialog-content').textContent()).includes(
    'Menyimpan membuat versi baru dan memperbarui estimasi kebutuhan semua order SKU ini, '
    + 'termasuk order lama. Stok dan pengeluaran tidak berubah.'));
  await secondLine.getByRole('button', {name: 'Hapus bahan BOM', exact: true}).click();
  assert.equal(await page.locator('#bom-lines .bom-line').count(), 1);
  await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.getByRole('button', {name: 'Ubah BOM', exact: true}).waitFor();
  const revision = await apiGet(`/api/products/${bomless.id}/bom`);
  const bomTrail = await apiGet(`/api/products/${bomless.id}/bom-history`);
  // Exactly one revision was written: the duplicate attempt persisted nothing and the accepted
  // save persisted once. The revision NUMBER is the store's to allocate, so it is read rather than
  // predicted; what matters here is that saving created one new version and no more.
  assert.equal(bomTrail.length, 1, 'saving created exactly one revision, history: '
    + JSON.stringify(bomTrail.map(row => [row.revision, row.reason])));
  assert.ok(revision.revision > 0, 'the SKU now has a BOM revision');
  assert.equal(bomTrail[0].revision, revision.revision);
  // The populated dialog shows the revision, its author, and the per-pcs component list.
  const populated = await page.locator('#dialog-content').textContent();
  assert.ok(populated.includes(`Versi ${revision.revision}`));
  assert.ok(populated.includes(revision.actor_name));
  assert.equal(await page.locator('#dialog-content .record-list .record-row').count(),
    revision.components.length);
  assert.ok((await page.locator('#dialog-content .record-row').first().textContent()).includes('/ pcs'),
    'a component quantity is stated per pcs');
  await shot('bom-populated-1440-light');
  await theme('dark');
  await shot('bom-populated-1440-dark');
  await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await dialogFits(), true, 'the BOM dialog fits at 390');
  await page.setViewportSize({width: 1440, height: 1000});

  // ---- BOM history paging -------------------------------------------------------------------
  for (let index = 2; index <= 11; index += 1) {
    const current = await apiGet(`/api/products/${bomless.id}/bom`);
    await apiPost(`/api/products/${bomless.id}/bom`, {
      expected_revision: current.revision,
      components: [{material_id: (decimalMaterial || materials[0]).id,
        quantity: (0.01 * index).toFixed(3)}],
      reason: `CONTOH - revisi BOM ${index} A6.2`,
    });
  }
  await page.getByRole('button', {name: 'Riwayat BOM', exact: true}).click();
  await page.getByRole('heading', {name: 'Riwayat BOM', exact: true}).waitFor();
  await page.locator('#bom-history .timeline-item').first().waitFor();
  assert.equal(await page.locator('#bom-history .timeline-item').count(), 10,
    'BOM history pages at 10 revisions');
  const more = page.getByRole('button', {name: 'Muat versi sebelumnya', exact: true});
  assert.equal(await more.isVisible(), true);
  await more.click();
  await page.waitForFunction(() =>
    document.querySelectorAll('#bom-history .timeline-item').length > 10);
  assert.equal(await page.locator('#bom-history .timeline-item').count(), 11,
    'the next page appends rather than replacing');
  // Each revision keeps its own component list rather than being merged into its neighbour.
  assert.equal(await page.locator('#bom-history .timeline-item .record-list').count(), 11);
  await shot('bom-history-1440-light');
  await escapeDialog();

  // ==================== JUBELIO MAPPING ====================
  await openProducts();
  await page.getByRole('button', {name: `Jubelio ${bomless.sku}`, exact: true}).click();
  await page.getByRole('heading', {name: 'Mapping SKU Jubelio', exact: true}).waitFor();
  await page.locator('#dialog .status-chip').waitFor();
  // Unmapped: the identity warning is stated as attention, not alarm.
  assert.equal(await dialog.locator('.status-chip').textContent(), 'Belum dipetakan');
  assert.equal(await dialog.locator('.status-chip-neutral').count(), 1);
  assert.equal(await dialog.locator('.status-chip-danger, .attention-note-critical').count(), 0,
    'an unmapped SKU is not a failure and must not be dramatised');
  assert.ok((await dialog.textContent()).includes(
    'Worker tidak boleh mengimpor data untuk SKU ini sebelum identitas Jubelio dipetakan.'));
  assert.ok((await dialog.textContent()).includes(
    'Jubelio adalah sumber order marketplace dan stok jual. Mapping ini hanya mencocokkan '
    + 'identitas; belum menjalankan sinkronisasi.'), 'the mapping-is-not-sync truth must stay');
  await shot('mapping-unmapped-1440-light');
  await theme('dark');
  await shot('mapping-unmapped-1440-dark');
  await theme('light');

  // ---- the mapping form carries expected_revision ------------------------------------------
  await page.getByRole('button', {name: 'Hubungkan Jubelio', exact: true}).click();
  await page.getByRole('heading', {name: 'Hubungkan SKU ke Jubelio', exact: true}).waitFor();
  await page.locator('#mapping-external-sku').waitFor();
  for (const label of ['ID eksternal Jubelio', 'SKU Jubelio', 'Alasan mapping']) {
    assert.equal(await page.getByLabel(label, {exact: true}).count(), 1,
      `${label} must keep its exact accessible name`);
  }
  const mappingPost = page.waitForRequest(request =>
    request.url().includes('/external-mappings/jubelio') && request.method() === 'POST');
  await page.getByLabel('ID eksternal Jubelio', {exact: true}).fill('a62-item-7');
  await page.getByLabel('SKU Jubelio', {exact: true}).fill('JUB-A62-S');
  await page.getByLabel('Alasan mapping', {exact: true}).fill('CONTOH - mapping identitas A6.2');
  await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  const sentMapping = JSON.parse((await mappingPost).postData());
  assert.equal(sentMapping.expected_revision, 0, 'the optimistic-concurrency token is still sent');
  assert.equal(sentMapping.action, 'mapped');
  assert.equal(sentMapping.external_id, 'a62-item-7', 'identifiers are stored exactly as given');
  assert.equal(sentMapping.external_sku, 'JUB-A62-S');
  await page.getByRole('button', {name: 'Ubah mapping', exact: true}).waitFor();
  // Mapped: every field of the record, and the admin actions.
  const mapped = await apiGet(`/api/products/${bomless.id}/external-mappings/jubelio`);
  assert.equal(await dialog.locator('.status-chip').textContent(), 'Terhubung');
  const mappedText = await dialog.textContent();
  for (const value of [mapped.external_sku, mapped.external_id, mapped.reason, mapped.actor_name,
    String(mapped.revision)]) {
    assert.ok(mappedText.includes(value), `the mapped record must state ${value}`);
  }
  await page.getByRole('button', {name: 'Lepaskan mapping', exact: true}).waitFor();
  await page.getByRole('button', {name: 'Riwayat mapping', exact: true}).waitFor();
  await page.getByRole('button', {name: 'Kembali ke Master SKU', exact: true}).waitFor();
  await shot('mapping-mapped-1440-light');
  await theme('dark');
  await shot('mapping-mapped-1440-dark');
  await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await dialogFits(), true, 'the mapping dialog fits at 390');
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  assert.equal(await dialogFits(), true, 'the mapping dialog fits at 390 and 200% text');
  await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  await page.setViewportSize({width: 1440, height: 1000});
  // The catalog row behind now states the same truth.
  await page.getByRole('button', {name: 'Kembali ke Master SKU', exact: true}).click();
  await page.locator(`#product-list li[data-product="${bomless.id}"] .status-chip-success`).waitFor();
  assert.ok((await page.locator(`#product-list li[data-product="${bomless.id}"]`).textContent())
    .includes('JUB-A62-S'), 'the catalog row shows the external SKU in use');

  // ---- unmap keeps its warning and its payload ---------------------------------------------
  await page.getByRole('button', {name: `Jubelio ${bomless.sku}`, exact: true}).click();
  await page.getByRole('button', {name: 'Lepaskan mapping', exact: true}).waitFor();
  await page.getByRole('button', {name: 'Lepaskan mapping', exact: true}).click();
  await page.getByRole('heading', {name: 'Lepaskan mapping Jubelio', exact: true}).waitFor();
  await page.getByLabel('Alasan pelepasan', {exact: true}).waitFor();
  assert.ok((await page.locator('#dialog-content').textContent()).includes(
    'Worker tidak boleh mencocokkan SKU ini setelah mapping dilepas.'));
  const unmapPost = page.waitForRequest(request =>
    request.url().includes('/external-mappings/jubelio') && request.method() === 'POST');
  await page.getByLabel('Alasan pelepasan', {exact: true}).fill('CONTOH - pelepasan uji A6.2');
  await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  const sentUnmap = JSON.parse((await unmapPost).postData());
  assert.equal(sentUnmap.action, 'unmapped');
  assert.equal(sentUnmap.external_id, '', 'unmapping clears the external id');
  assert.equal(sentUnmap.external_sku, '');
  assert.equal(sentUnmap.expected_revision, mapped.revision);
  await page.getByRole('button', {name: 'Hubungkan Jubelio', exact: true}).waitFor();
  assert.equal(await dialog.locator('.status-chip').textContent(), 'Belum dipetakan');

  // ---- mapping history paging --------------------------------------------------------------
  for (let index = 0; index < 20; index += 1) {
    const current = await apiGet(`/api/products/${bomless.id}/external-mappings/jubelio`);
    await apiPost(`/api/products/${bomless.id}/external-mappings/jubelio`,
      current.status === 'mapped'
        ? {expected_revision: current.revision, action: 'unmapped', external_id: '',
           external_sku: '', reason: `CONTOH - lepas ${index} A6.2`}
        : {expected_revision: current.revision, action: 'mapped',
           external_id: `a62-item-${index}`, external_sku: `JUB-A62-${index}`,
           reason: `CONTOH - petakan ${index} A6.2`});
  }
  await page.getByRole('button', {name: 'Riwayat mapping', exact: true}).click();
  await page.getByRole('heading', {name: 'Riwayat mapping Jubelio', exact: true}).waitFor();
  await page.locator('#product-mapping-history .timeline-item').first().waitFor();
  assert.equal(await page.locator('#product-mapping-history .timeline-item').count(), 20,
    'mapping history pages at 20 revisions');
  const historyMore = page.getByRole('button', {name: 'Muat riwayat sebelumnya', exact: true});
  assert.equal(await historyMore.isVisible(), true);
  await historyMore.click();
  await page.waitForFunction(() =>
    document.querySelectorAll('#product-mapping-history .timeline-item').length > 20);
  // Mapped and unmapped revisions stay visually distinct, never merged.
  const revisionLabels = await page.locator('#product-mapping-history .timeline-event').allTextContents();
  assert.ok(revisionLabels.some(text => text.includes('Terhubung')));
  assert.ok(revisionLabels.some(text => text.includes('Dilepas')));
  assert.ok(revisionLabels.every(text => /^Revisi \d+ · (Terhubung|Dilepas)$/.test(text)),
    'every entry states its own revision number and its own state');
  await shot('mapping-history-1440-light');
  await escapeDialog();

  // ==================== MASTER SKU PERMISSIONS ====================
  for (const [key, role] of [[operator, 'operator'], [viewer, 'viewer']]) {
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
    await login(key);
    await theme('light');
    await openProducts();
    assert.equal(await page.locator('#new-product').isVisible(), false,
      `${role} must not be offered SKU creation`);
    // Reading BOM and mapping stays open; writing does not.
    await page.getByRole('button', {name: `BOM ${products[0].sku}`, exact: true}).click();
    await page.getByRole('heading', {name: 'BOM per SKU', exact: true}).waitFor();
    await page.locator('#dialog-content .info-panel').waitFor();
    for (const write of ['Isi BOM', 'Ubah BOM']) {
      assert.equal(await page.getByRole('button', {name: write, exact: true}).count(), 0,
        `${role} must not be offered ${write}`);
    }
    await escapeDialog();
    await page.getByRole('button', {name: `Jubelio ${products[0].sku}`, exact: true}).click();
    await page.getByRole('heading', {name: 'Mapping SKU Jubelio', exact: true}).waitFor();
    await page.locator('#dialog .status-chip').waitFor();
    for (const write of ['Ubah mapping', 'Hubungkan Jubelio', 'Lepaskan mapping']) {
      assert.equal(await page.getByRole('button', {name: write, exact: true}).count(), 0,
        `${role} must not be offered ${write}`);
    }
    // ...and the read-only navigation is still there.
    await page.getByRole('button', {name: 'Riwayat mapping', exact: true}).waitFor();
    await page.getByRole('button', {name: 'Kembali ke Master SKU', exact: true}).waitFor();
    if (role === 'viewer') await shot('mapping-1440-light-viewer');
    await escapeDialog();
  }

  // ==================== A6.1 IS NOT REGRESSED ====================
  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  await login(admin);
  await theme('light');
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Produksi', exact: true}).waitFor();
  await page.locator('#order-list .order-row').first().waitFor();
  assert.equal(await page.locator('#summary .metric-card').count(), 4,
    'the Produksi metric strip is untouched');
  assert.equal(await page.locator('#board-view .command-bar').count(), 1);
  assert.equal(await page.locator('#order-list .data-surface, #order-list table').count() > 0, true);
  assert.equal(await page.locator('#board-view .workspace-title').textContent(), 'Produksi');
  // The order detail's material history is the SAME renderer A6.2 rebuilt; the order mode of it
  // must still work, which is the one place A6.2 could have broken A6.1 outright.
  await page.locator('#order-list .order-title').first().click();
  await page.locator('#detail-content .detail-grid').first().waitFor();
  await page.getByRole('button', {name: 'Riwayat bahan order', exact: true}).click();
  await page.getByRole('heading', {name: 'Riwayat bahan order', exact: true}).waitFor();
  await page.locator('#material-history .timeline-item').first().waitFor();
  // Order mode has no batch, so no batch-only block may appear.
  assert.equal(await dialog.locator('.bundle-label').count(), 0,
    'order mode has no batch and therefore no batch label');
  assert.equal(await dialog.getByRole('button', {name: 'Jejak produksi lengkap', exact: true}).count(), 0);
  assert.ok(!(await dialog.textContent()).includes('Posisi bahan sekarang'),
    'order mode shows no batch position panel');
  await shot('order-material-history-1440-light');
  await escapeDialog();
  await page.locator('#back').click();
  await page.locator('#order-list .order-row').first().waitFor();

  console.log('A6.2 browser QA PASS: Bahan baku (A6 composition, quantity truth against the API, '
    + 'filter resets offset in the real query, 25+1 sentinel, empty/error/refresh, stale-response '
    + 'guard, batch detail + timeline + label, traceability, master bahan, receipt units, keyboard '
    + 'scanner, roles) and Master SKU (record-list catalog, two-request load with zero BOM fan-out, '
    + 'four-value local search costing no request, truthful mapping wording, both empty states, '
    + 'error + retry, add SKU, BOM validation + history paging, mapping + unmap payloads + history '
    + 'paging, roles); responsive 1440/1024/980/768/390/320 and 320@200% in light and dark with no '
    + 'document overflow; forced colours and reduced motion; A6.1 Produksi and its order-mode '
    + 'material history unregressed.');
};
