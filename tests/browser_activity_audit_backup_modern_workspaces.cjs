const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// A6.6 - Aktivitas + Audit trail + Cadangan data modern workspaces, behavioural half.
//
// This module SUPPLEMENTS the suites that already own the business rules - the backend unit suites
// (test_activity, test_activity_export, test_audit_trail, test_backup_download), the smoke flow's
// Activity/backup checks, browser_audit_trail, browser_workspace_utilities' backup stale guard and
// the navigation / motion suites. What it owns is the A6.6 presentation and the behaviour that
// presentation must not have bent:
//
//   Aktivitas - all three roles can read it; the first request carries kind + limit=50 and NO
//   dates, and the server's Jakarta default is written back into both inputs; date/kind `change`
//   auto-loads and submit still works; any edit invalidates the visible report and the export at
//   once; the four summary values are the returned ones and stay range-wide when a kind is
//   selected; every event kind renders its own detail, escaped, in Jakarta time; the 50-row
//   before_time + before_id cursor appends and is not disturbed by an event recorded after page 1;
//   CSV export is the full successful filter (no limit, no cursor), single-flight and restored.
//
//   Audit trail - admin-only in the navigation and the API; /api/users is read before the ledger;
//   25 rows per page, newest first, `before` sequence cursor, filter total; search / category /
//   actor / date filters, Reset, empty state, top-level retry; the evidence dialog keeps every
//   field and both raw JSON documents, escaped, with no mutation control.
//
//   Cadangan data - admin-only; opening it never downloads; GET /api/backup once, busy lock,
//   success wording, .sqlite3 filename shape, inline 503 failure with a manual retry, and a stale
//   response that cannot start a download after the user left.
//
// It also writes the deterministic A6.6 visual-review set. Pixel widths are never asserted; the
// subject is always a label, a figure, a request parameter or a document overflow.
module.exports = async ({page, login, openSidebarDestination, admin, operator, viewer, apiGet, apiPost, work}) => {
  const base = process.env.BEELOFT_QA_BASE;
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const review = process.env.BEELOFT_A66_REVIEW || path.join(shots, 'a66-visual-gate');
  fs.mkdirSync(review, {recursive: true});
  const shot = async (name, target = null, options = {}) => {
    const file = path.join(review, name + '.png');
    // A review shot shows the workspace, not a transient toast or the focus ring a fill() left behind.
    await page.evaluate(() => { const notice = document.getElementById('notice'); if (notice) notice.hidden = true;
      if (document.activeElement && document.activeElement !== document.body && !document.querySelector('dialog[open]')) document.activeElement.blur(); });
    // ...and never mid page-entry or list-replacement fade.
    await page.waitForFunction(() => !document.querySelector('.motion-enter'));
    // On a phone the workspace, not the document, scrolls: bring the page heading under the chrome.
    if (/-(390|320-200)$/.test(name)) await page.evaluate(() => {
      const heading = [...document.querySelectorAll('.workspace-main > section')].find(node => !node.hidden)?.querySelector('h1');
      if (heading) heading.scrollIntoView({block: 'start'});
    });
    if (target) await target.screenshot({path: file});
    else await page.screenshot({path: file, fullPage: false, ...options});
  };
  const toTop = () => page.evaluate(() => { document.querySelectorAll('.workspace-main,#main').forEach(node => { node.scrollTop = 0; }); window.scrollTo(0, 0); });
  const theme = async value => {
    await page.evaluate(mode => document.documentElement.setAttribute('data-theme', mode), value);
    await page.waitForTimeout(600);
  };
  const text200 = on => page.evaluate(value => { document.documentElement.style.fontSize = value; }, on ? '200%' : '');
  const noDocumentOverflow = () => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  // A document-overflow check cannot see what the floating window clips, so each migrated section is
  // also measured against its own edges: at 320px / 200% a control wider than its command bar is a
  // clipped control whether or not the document scrolls.
  const sectionOverflow = sectionId => page.evaluate(id => {
    const section = document.getElementById(id), box = section.getBoundingClientRect();
    return [...section.querySelectorAll('*')]
      .filter(node => node.getClientRects().length && !node.closest('.visually-hidden'))
      .filter(node => { const rect = node.getBoundingClientRect(); return rect.right > box.right + 1 || rect.left < box.left - 1; })
      .map(node => node.tagName.toLowerCase() + (node.id ? '#' + node.id : ''));
  }, sectionId);
  const fits = async (sectionId, where) => {
    assert.equal(await noDocumentOverflow(), true, `document overflow: ${where}`);
    assert.deepEqual(await sectionOverflow(sectionId), [], `content crosses its section: ${where}`);
  };
  const dialogFits = () => page.evaluate(() => {
    const d = document.querySelector('dialog'); return d.scrollWidth <= d.clientWidth;
  });
  const dialog = page.locator('dialog');
  const closeDialog = async () => {
    if (await dialog.isVisible()) { await page.keyboard.press('Escape'); await dialog.waitFor({state: 'hidden'}); }
  };
  async function role(key) {
    await closeDialog();
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
    await login(key);
  }
  const nf = new Intl.NumberFormat('id-ID');
  const n = value => nf.format(value);
  const jakartaDay = (offset = 0) => new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Jakarta'})
    .format(new Date(Date.now() + offset * 86400000));
  const today = jakartaDay();
  const paramsOf = url => Object.fromEntries(new URL(url).searchParams);
  const mutationControls = /Ubah|Hapus|Edit|Delete|Pulihkan|Restore|Replay|Undo|Batalkan|Ulangi|Unggah|Upload/;

  // Earlier modules may leave the dark theme on; the review set starts from light.
  await theme('light');
  // ================================= AKTIVITAS ==================================
  const activityView = page.locator('#activity-view');
  const activityForm = page.locator('#activity-form');
  const exportButton = page.locator('#activity-export');
  const kindSelect = activityForm.getByLabel('Jenis aktivitas', {exact: true});
  const dayInput = activityForm.getByLabel('Dari tanggal', {exact: true});
  const endInput = activityForm.getByLabel('Sampai tanggal', {exact: true});
  const isActivity = url => url.includes('/api/activity?');
  // A report is settled when its count line is written and the finally-block has re-evaluated export.
  const reportSettled = () => page.waitForFunction(() =>
    document.getElementById('activity-count').textContent !== ''
    || document.querySelector('#activity-message .error-state'));
  // Runs `action`, returns the request parameters and the parsed body of the report it triggered.
  async function report(action) {
    const request = page.waitForRequest(r => isActivity(r.url()));
    const response = page.waitForResponse(r => isActivity(r.url()));
    await action();
    const sent = await request, body = await (await response).json();
    await reportSettled();
    return {params: paramsOf(sent.url()), body};
  }
  const summaryText = () => page.locator('#activity-summary').evaluate(node =>
    [...node.querySelectorAll('.metric-card')].map(card => [card.querySelector('dt').textContent.trim(),
      card.querySelector('dd').textContent.replace(/\s+/g, ' ').trim()]));
  const expectedSummary = s => [['Aktivitas tercatat', `${n(s.events)} catatan`], ['Gudang bersih', `${n(s.warehouse_net)} pcs`],
    ['Kendala dicatat', `${n(s.issues_opened)} catatan`], ['Kendala selesai', `${n(s.issues_resolved)} catatan`]];

  // ---- every role reads Activity, and the first load is the server's Jakarta default ----
  for (const key of [operator, viewer, admin]) {
    await role(key);
    assert.equal(await page.locator('#activity').isVisible(), true, 'Activity is a destination for every role');
    const first = await report(() => openSidebarDestination('Laporan aktivitas'));
    assert.equal(first.params.kind, 'all');
    assert.equal(first.params.limit, '50', 'the on-screen report stays 50 rows');
    for (const absent of ['start_date', 'end_date', 'day', 'before_time', 'before_id'])
      assert.equal(absent in first.params, false, `the first request carries no ${absent}`);
    assert.equal(first.body.start_date, today, 'the backend defaults the report to today in Asia/Jakarta');
    assert.equal(await dayInput.inputValue(), first.body.start_date, 'the returned start date is written back');
    assert.equal(await endInput.inputValue(), first.body.end_date, 'the returned end date is written back');
    assert.equal(await page.locator('#activity').getAttribute('aria-current'), 'page');
    assert.equal(await activityView.locator('[data-action="move"]').count(), 0, 'Activity has no write control');
  }

  // ---- identity, Jakarta context, command bar and the exact kind vocabulary ----
  await activityView.getByRole('heading', {level: 1, name: 'Aktivitas', exact: true}).waitFor();
  await activityView.getByText('Telusuri catatan produksi dalam waktu Jakarta dan ekspor hasilnya.', {exact: true}).waitFor();
  assert.match(await activityView.locator('.workspace-eyebrow').innerText(), /waktu Jakarta/);
  assert.match(await page.locator('#activity-range').innerText(), /waktu Jakarta · semua jenis aktivitas$/);
  assert.equal(await activityView.evaluate(node => node.classList.contains('workspace-page')), true);
  assert.equal(await activityForm.evaluate(node => node.classList.contains('command-bar')), true);
  assert.deepEqual(await kindSelect.evaluate(select => [...select.options].map(o => [o.value, o.textContent])), [
    ['all', 'Semua aktivitas'], ['movement', 'Perpindahan barang'], ['reversal', 'Koreksi perpindahan'],
    ['issue_opened', 'Kendala dicatat'], ['issue_resolved', 'Kendala selesai'], ['order_created', 'Order dibuat'],
    ['order_changed', 'Tenggat / PIC diubah']]);
  assert.deepEqual(await Promise.all([dayInput, endInput].map(input => input.evaluate(node => [node.type, node.required, node.max]))),
    [['date', true, ''], ['date', true, '']], 'the dates keep their required rule and gain no max=today rule');
  assert.match(await page.locator('#activity-summary-note').innerText(),
    /Ringkasan mencakup semua jenis pada rentang terpilih\. Gudang bersih = barang masuk dikurangi pembalikannya pada rentang pencatatan; angkanya bisa negatif\. Posisi barang saat ini ada di papan produksi\. CSV memuat seluruh hasil filter; maksimal 366 hari dan 10\.000 catatan\./);

  // ---- seed a real cursor walk: more than one 50-row page of today's order_created events ----
  const unique = Date.now();
  const users = await apiGet('/api/users');
  const products = await apiGet('/api/products');
  const product = (products.items || products)[0];
  const owner = users.find(item => item.role === 'operator') || users[0];
  const seedOrder = index => apiPost('/api/orders', {reference: `A66-ACT-${unique}-${String(index).padStart(2, '0')}`,
    title: `CONTOH <b>A6.6</b> & "kutip" ${index}`, owner_id: owner.id, due_date: jakartaDay(30),
    lines: [{product_id: product.id, quantity: 5}]});
  const seeded = [];
  for (let index = 0; index < 56; index++) seeded.push(await seedOrder(index));

  // ---- change auto-loads (kind), with dates now carried from the inputs ----
  const created = await report(() => kindSelect.selectOption('order_created'));
  assert.deepEqual([created.params.kind, created.params.limit, created.params.start_date, created.params.end_date],
    ['order_created', '50', today, today]);
  assert.equal(created.body.items.length, 50);
  assert.ok(created.body.next_before && created.body.next_before.before_time && created.body.next_before.before_id,
    'the cursor is the before_time + before_id pair');
  assert.equal(await page.locator('#activity-list > li').count(), 50);
  assert.equal(await page.locator('#activity-list > li[data-activity-kind="order_created"]').count(), 50);
  const more = page.getByRole('button', {name: 'Muat aktivitas sebelumnya', exact: true});
  assert.equal(await more.isVisible(), true, 'load-more shows only while next_before exists');
  assert.equal(await page.locator('#activity-count').innerText(),
    `${n(50)} catatan ditampilkan · ${n(created.body.total)} cocok saat dimuat`);

  // An event recorded AFTER page 1 must not disturb the historical walk of this report.
  const late = await seedOrder(99);
  const older = await report(() => more.click());
  // Appending keeps the count line written, so wait for the appended rows themselves.
  await page.waitForFunction(count => document.querySelectorAll('#activity-list > li').length === count, 50 + older.body.items.length);
  assert.equal(older.params.before_time, created.body.next_before.before_time);
  assert.equal(older.params.before_id, created.body.next_before.before_id);
  assert.deepEqual([older.params.kind, older.params.limit, older.params.start_date, older.params.end_date],
    ['order_created', '50', today, today], 'loading older records keeps the loaded report query');
  const walked = await page.locator('#activity-list .order-title').allInnerTexts();
  assert.equal(walked.length, 50 + older.body.items.length, 'older records append to the same timeline');
  assert.equal(new Set(walked).size, walked.length, 'the two-part cursor never repeats an event');
  assert.equal(walked.some(label => label.startsWith(late.reference)), false,
    'an event recorded after page 1 does not enter the historical walk');
  assert.equal(await page.locator('#activity-count').innerText(),
    `${n(walked.length)} catatan ditampilkan · ${n(older.body.total)} cocok saat dimuat`);

  // ---- the summary is range-wide and NOT narrowed by kind ----
  const all = await report(() => kindSelect.selectOption('all'));
  assert.deepEqual(await summaryText(), expectedSummary(all.body.summary), 'the four values are the returned summary');
  const issues = await report(() => kindSelect.selectOption('issue_opened'));
  assert.deepEqual(issues.body.summary, all.body.summary, 'the backend summary ignores the kind filter');
  assert.deepEqual(await summaryText(), expectedSummary(all.body.summary), 'the strip still describes the whole range');
  assert.ok(all.body.summary.events > issues.body.total, 'the summary counts more than the filtered timeline shows');
  assert.equal(await page.locator('#activity-list > li:not([data-activity-kind="issue_opened"])').count(), 0);
  assert.equal(await page.locator('#activity-summary .metric-card-danger').count(), 0, 'no summary figure is painted as an error');

  // ---- any edit invalidates the visible report and the export at once ----
  assert.equal(await exportButton.isEnabled(), true, 'a successfully loaded report can be exported');
  let releaseHeld; const held = new Promise(resolve => { releaseHeld = resolve; });
  await page.route('**/api/activity?*', async route => { await held; await route.continue(); });
  const pending = page.waitForResponse(r => isActivity(r.url()));
  await kindSelect.selectOption('movement');
  const invalidated = await page.evaluate(() => ({
    exportDisabled: document.getElementById('activity-export').disabled,
    rows: document.getElementById('activity-list').children.length,
    summary: document.getElementById('activity-summary').children.length,
    count: document.getElementById('activity-count').textContent,
    range: document.getElementById('activity-range').textContent,
    more: document.getElementById('activity-more').hidden}));
  assert.deepEqual(invalidated, {exportDisabled: true, rows: 0, summary: 0, count: '', range: '', more: true},
    'editing a filter clears the stale report and disables its export until the new one resolves');
  await shot('07b-activity-invalidated-while-loading');
  releaseHeld(); await pending; await reportSettled();
  await page.unroute('**/api/activity?*');
  assert.equal(await exportButton.isEnabled(), true);

  // ---- valid date change auto-loads; explicit submit still works ----
  const widened = await report(() => dayInput.fill(jakartaDay(-1)));
  assert.deepEqual([widened.params.start_date, widened.params.end_date, widened.params.kind], [jakartaDay(-1), today, 'movement']);
  const submitted = await report(() => activityForm.getByRole('button', {name: 'Tampilkan aktivitas', exact: true}).click());
  assert.deepEqual([submitted.params.start_date, submitted.params.end_date], [jakartaDay(-1), today]);
  await report(() => dayInput.fill(today));
  await report(() => kindSelect.selectOption('all'));

  // ---- CSV: the complete successful filter, single-flight, restored after success and error ----
  const csvRequests = [];
  let releaseCsv; const csvHeld = new Promise(resolve => { releaseCsv = resolve; });
  await page.route('**/api/activity.csv?*', async route => { csvRequests.push(route.request().url()); await csvHeld; await route.continue(); });
  const download = page.waitForEvent('download');
  await exportButton.click();
  await page.waitForFunction(() => document.getElementById('activity-export').textContent === 'Menyiapkan CSV…');
  assert.equal(await exportButton.isDisabled(), true);
  await toTop();
  await shot('07-activity-export-busy');
  // Even a click that reaches the handler past the disabled attribute is refused by exportBusy.
  await exportButton.evaluate(button => { button.disabled = false; button.click(); button.disabled = true; });
  assert.equal(csvRequests.length, 1, 'a second export cannot start while the first is preparing');
  const csvParams = paramsOf(csvRequests[0]);
  assert.deepEqual(csvParams, {start_date: today, end_date: today, kind: 'all'},
    'export sends the loaded range and kind only - no limit and no cursor');
  releaseCsv();
  const file = await download;
  assert.equal(file.suggestedFilename(), `beeloft-aktivitas-${today}-${today}-all.csv`);
  assert.ok(fs.readFileSync(await file.path(), 'utf8').startsWith('\ufeff'));
  await page.waitForFunction(() => document.getElementById('activity-export').textContent === 'Unduh CSV');
  assert.equal(await exportButton.isEnabled(), true);
  await page.unroute('**/api/activity.csv?*');
  let downloads = 0; const countDownload = () => downloads++;
  page.on('download', countDownload);
  await page.route('**/api/activity.csv?*', route => route.fulfill({status: 422, contentType: 'application/json',
    body: JSON.stringify({detail: 'Hasil melebihi 10.000 catatan. Persempit tanggal atau jenis aktivitas, lalu unduh lagi.'})}));
  await exportButton.click();
  await page.locator('#activity-message .error-state').getByText('Hasil melebihi 10.000 catatan. Persempit tanggal atau jenis aktivitas, lalu unduh lagi.', {exact: true}).waitFor();
  await page.waitForFunction(() => document.getElementById('activity-export').textContent === 'Unduh CSV'
    && !document.getElementById('activity-export').disabled);
  assert.equal(downloads, 0, 'a refused export never downloads a partial file');
  assert.ok(await page.locator('#activity-list > li').count() > 0, 'an export error leaves the report in place');
  page.off('download', countDownload);
  await page.unroute('**/api/activity.csv?*');

  // ---- every event kind, rendered from a deterministic fixture ----
  // The fixture mirrors the backend contract exactly: the summary is range-wide and the kind filter
  // narrows the items only. `created_at` is UTC; 2031-03-01T17:20Z is already 2 Mar 00.20 in Jakarta.
  const fixtureDay = '2031-03-02';
  const target = seeded[0];
  const at = (utc, fields) => ({event_id: 'a66-' + utc, created_at: utc, order_id: target.id, reference: 'PO-2031-0302',
    title: 'Kemeja <b>linen</b> & celana "kargo"', sku: null, quantity: null, from_stage: null, to_stage: null,
    reason: null, actor_name: 'Sari <Admin>', details: {}, ...fields});
  const fixture = [
    at('2031-03-02T09:40:00Z', {kind: 'order_changed', details: {old_due_date: '2031-03-10', new_due_date: '2031-03-14',
      old_owner_name: 'Rina Operator', new_owner_name: 'Budi Operator'}, reason: 'Kain datang terlambat'}),
    at('2031-03-02T08:15:00Z', {kind: 'issue_resolved', to_stage: 'qc', details: {description: 'Benang putus sudah diganti, jahitan diulang'}, actor_name: 'Rina Operator'}),
    at('2031-03-02T06:05:00Z', {kind: 'issue_opened', to_stage: 'qc', details: {owner_name: 'Rina Operator'}, reason: 'Jahitan lepas <script>alert(1)</script> di 3 pcs'}),
    at('2031-03-02T05:30:00Z', {kind: 'reversal', sku: 'KMJ-LIN-M-NVY', quantity: 5, from_stage: 'finishing', to_stage: 'sewing', reason: 'Salah catat jumlah'}),
    at('2031-03-02T04:10:00Z', {kind: 'movement', sku: 'KMJ-LIN-M-NVY', quantity: 40, from_stage: 'sewing', to_stage: 'finishing', actor_name: 'Budi Operator'}),
    at('2031-03-02T02:45:00Z', {kind: 'movement', sku: 'KMJ-LIN-L-NVY', quantity: 25, from_stage: 'cutting', to_stage: 'sewing', actor_name: 'Budi Operator'}),
    at('2031-03-01T17:20:00Z', {kind: 'order_created', sku: 'KMJ-LIN-M-NVY'}),
  ];
  const fixtureSummary = {events: 128, warehouse_net: -12, issues_opened: 3, issues_resolved: 2};
  await page.route('**/api/activity?*', async route => {
    const query = paramsOf(route.request().url());
    if (query.start_date !== fixtureDay) return route.continue();
    const items = fixture.filter(item => query.kind === 'all' || item.kind === query.kind);
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({start_date: query.start_date,
      end_date: query.end_date || query.start_date, kind: query.kind, total: items.length, summary: fixtureSummary, items, next_before: null})});
  });
  await report(() => endInput.fill(fixtureDay));
  await report(() => dayInput.fill(fixtureDay));
  assert.deepEqual(await page.locator('#activity-list > li').evaluateAll(items => items.map(item => item.dataset.activityKind)),
    fixture.map(item => item.kind), 'one timeline item per event, newest first, never regrouped');
  const rendered = await page.locator('#activity-list > li').evaluateAll(items => items.map(item => ({
    time: item.querySelector('time').textContent, datetime: item.querySelector('time').getAttribute('datetime'),
    event: item.querySelector('.timeline-event').textContent,
    order: item.querySelector('.order-title').textContent, action: item.querySelector('.order-title').dataset.action,
    id: item.querySelector('.order-title').dataset.id,
    sku: item.querySelector('.activity-sku')?.textContent || null,
    details: [...item.querySelectorAll('.timeline-detail:not(.activity-order):not(.activity-sku):not(.activity-reason)')].map(node => node.textContent),
    reason: item.querySelector('.activity-reason')?.textContent || null,
    actor: item.querySelector('.timeline-actor').textContent})));
  assert.deepEqual(rendered.map(row => row.event), ['Tenggat / PIC diubah', 'Kendala selesai', 'Kendala dicatat',
    'Koreksi perpindahan', 'Perpindahan barang', 'Perpindahan barang', 'Order dibuat']);
  for (const row of rendered) {
    assert.equal(row.order, 'PO-2031-0302 · Kemeja <b>linen</b> & celana "kargo"', 'reference and title render as text');
    assert.deepEqual([row.action, row.id], ['detail', target.id], 'the order stays actionable through data-action=detail');
    assert.match(row.time, /2 Mar 2031/, 'every fixture event belongs to the Jakarta business day');
  }
  assert.match(rendered[6].time, /00[.:]20/, 'the timestamp is Jakarta time, not browser-local time');
  assert.deepEqual(rendered[0].details.length, 1);
  assert.match(rendered[0].details[0], /^Tenggat: 10 Mar 2031 → 14 Mar 2031 · PIC: Rina Operator → Budi Operator$/);
  assert.deepEqual(rendered[1].details, ['QC · Benang putus sudah diganti, jahitan diulang']);
  assert.deepEqual(rendered[2].details, ['QC · PIC: Rina Operator']);
  assert.deepEqual(rendered[3].details, ['5 pcs · Finishing → Sewing']);
  assert.deepEqual(rendered[4].details, ['40 pcs · Sewing → Finishing']);
  assert.deepEqual(rendered[6].details, [], 'order created invents no detail the endpoint did not return');
  assert.equal(rendered[4].sku, 'KMJ-LIN-M-NVY');
  assert.equal(rendered[0].sku, null);
  assert.equal(rendered[2].reason, 'Jahitan lepas <script>alert(1)</script> di 3 pcs');
  assert.equal(rendered[3].reason, 'Salah catat jumlah');
  assert.equal(rendered[6].actor, 'Dicatat Sari <Admin>');
  assert.equal(await page.locator('#activity-list script, #activity-list b').count(), 0, 'no business text becomes markup');
  assert.deepEqual(await summaryText(), expectedSummary(fixtureSummary));
  assert.equal(await page.locator('#activity-summary dd').nth(1).innerText(), `${n(-12)} pcs`, 'a negative warehouse net is shown as the figure it is');

  // Visual review: populated timeline.
  await fits('activity-view', 'Activity at 1440');
  await toTop();
  await shot('01-activity-1440-light');
  await theme('dark'); await shot('02-activity-1440-dark'); await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  await fits('activity-view', 'Activity at 390');
  await toTop(); await shot('03-activity-390', null, {fullPage: true});
  await page.setViewportSize({width: 320, height: 800});
  await text200(true);
  await fits('activity-view', 'Activity at 320 / 200%');
  await toTop(); await shot('04-activity-320-200', null, {fullPage: true});
  await text200(false);
  await page.setViewportSize({width: 1440, height: 1000});
  const moves = await report(() => kindSelect.selectOption('movement'));
  assert.equal(moves.params.kind, 'movement');
  assert.equal(await page.locator('#activity-list > li').count(), 2);
  assert.deepEqual(await summaryText(), expectedSummary(fixtureSummary), 'the filtered timeline keeps the range summary');
  await toTop(); await shot('05-activity-filtered-movement');
  // The order reference opens the A6.1 order detail and Activity is re-entered with its range kept.
  await page.locator('#activity-list .order-title').first().click();
  await page.locator('#detail-view').waitFor();
  assert.equal(await page.locator('#board-home').getAttribute('aria-current'), 'page');
  await report(() => openSidebarDestination('Laporan aktivitas'));
  assert.equal(await dayInput.inputValue(), fixtureDay);
  await page.unroute('**/api/activity?*');

  // Empty state: a range without activity is not "no activity ever".
  await report(() => kindSelect.selectOption('all'));
  await report(() => dayInput.fill('2000-01-01'));
  await report(() => endInput.fill('2000-01-01'));
  await page.locator('#activity-message .empty-state').getByText('Tidak ada aktivitas yang cocok pada rentang ini.', {exact: true}).waitFor();
  assert.equal(await page.locator('#activity-list > li').count(), 0);
  assert.equal(await page.locator('#activity-summary .metric-card').count(), 4, 'an empty range still reports its four figures');
  await toTop(); await shot('06-activity-empty');
  await report(() => endInput.fill(today));
  await report(() => dayInput.fill(today));

  // ================================= AUDIT TRAIL =================================
  const auditView = page.locator('#audit-view');
  assert.equal(await page.locator('#audit-trail').isVisible(), true, 'admin sees Audit trail');
  const auditLoad = async action => {
    const log = [];
    const record = request => {
      const url = request.url();
      if (url.endsWith('/api/users')) log.push(['users', url]);
      else if (url.includes('/api/audit-events?')) log.push(['events', url]);
    };
    page.on('request', record);
    const response = page.waitForResponse(r => r.url().includes('/api/audit-events?'));
    await action();
    const body = await (await response).json();
    await page.waitForFunction(() => document.getElementById('audit-summary')?.textContent
      && !document.getElementById('audit-more')?.disabled);
    page.off('request', record);
    return {log, body, params: paramsOf(log.filter(([kind]) => kind === 'events').at(-1)[1])};
  };
  const rowIds = () => page.locator('#audit-list [data-action="audit-event"]').evaluateAll(buttons => buttons.map(b => b.dataset.id));

  const opened = await auditLoad(() => openSidebarDestination('Audit trail'));
  assert.deepEqual(opened.log.map(([kind]) => kind), ['users', 'events'], 'the actor list is read before the ledger');
  assert.deepEqual(opened.params, {limit: '25', category: 'all'}, 'limit 25, and empty filters are not sent');
  await auditView.getByRole('heading', {level: 1, name: 'Audit trail', exact: true}).waitFor();
  await auditView.getByText('Telusuri perubahan bisnis dan keputusan approval yang tersimpan sebagai catatan read-only.', {exact: true}).waitFor();
  assert.match(await page.locator('#audit-readonly-note').innerText(),
    /Riwayat perubahan bisnis dan keputusan approval\. Catatan bersifat read-only, urut dari yang terbaru, dan dikelola admin\./);
  assert.equal(await auditView.evaluate(node => node.classList.contains('workspace-page')), true);
  assert.equal(await page.locator('#audit-filter').evaluate(node => node.classList.contains('command-bar')), true);
  const firstPage = await apiGet('/api/audit-events?limit=25&category=all');
  assert.deepEqual(await rowIds(), firstPage.items.map(item => item.id), 'the ledger is the API page, in order');
  assert.ok(firstPage.items.every((item, index, rows) => !index || rows[index - 1].sequence > item.sequence), 'newest first by sequence');
  assert.equal(await page.locator('#audit-summary').innerText(), `${n(firstPage.total)} catatan sesuai filter.`);
  assert.equal(await page.locator('#audit-list .record-list .record-row.audit-event').count(), 25);
  assert.equal(await page.locator('#audit-list .status-chip:not(.status-chip-neutral)').count(), 0, 'category is a neutral classification');
  assert.equal(await auditView.getByRole('button', {name: mutationControls}).count(), 0, 'the ledger offers no mutation');
  assert.deepEqual(await page.locator('#audit-category').evaluate(select => [...select.options].map(o => [o.value, o.textContent])), [
    ['all', 'Semua kategori'], ['master_data', 'Master data'], ['production', 'Produksi'], ['materials', 'Bahan baku'],
    ['purchasing', 'Pembelian'], ['warehouse', 'Gudang'], ['marketplace', 'Marketplace'], ['approval', 'Approval'],
    ['ai', 'AI'], ['integration', 'Integrasi']]);
  assert.deepEqual(await page.locator('#audit-actor').evaluate(select => [...select.options].map(o => [o.value, o.textContent])),
    [['', 'Semua pelaku'], ...users.map(item => [item.id, `${item.name} · ${item.role}`])], 'actors come from /api/users as returned');
  assert.equal(await page.locator('#audit-filter input[name="q"]').getAttribute('maxlength'), '160');
  await fits('audit-view', 'Audit at 1440');
  await toTop(); await shot('08-audit-1440-light');
  await theme('dark'); await shot('09-audit-1440-dark'); await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  await fits('audit-view', 'Audit at 390');
  await toTop(); await shot('10-audit-390', null, {fullPage: true});
  await page.setViewportSize({width: 320, height: 800}); await text200(true);
  await fits('audit-view', 'Audit at 320 / 200%');
  await toTop(); await shot('11-audit-320-200', null, {fullPage: true});
  await text200(false); await page.setViewportSize({width: 1440, height: 1000});

  // Older records append without replaying the list motion; the total stays the filter total.
  assert.ok(firstPage.next_before, 'the seeded ledger has more than one page');
  await page.evaluate(() => {
    window.auditMotion = [];
    new MutationObserver(() => window.auditMotion.push(document.getElementById('audit-list').className))
      .observe(document.getElementById('audit-list'), {attributes: true, attributeFilter: ['class']});
  });
  const paged = await auditLoad(() => page.getByRole('button', {name: 'Muat catatan sebelumnya', exact: true}).click());
  assert.deepEqual(paged.params, {limit: '25', category: 'all', before: String(firstPage.next_before)}, 'the sequence cursor');
  const secondPage = await apiGet('/api/audit-events?limit=25&category=all&before=' + firstPage.next_before);
  assert.deepEqual(await rowIds(), [...firstPage.items, ...secondPage.items].map(item => item.id));
  assert.equal(await page.locator('#audit-summary').innerText(), `${n(firstPage.total)} catatan sesuai filter.`,
    'the count is the filter total, not the rows before the cursor');
  assert.deepEqual(await page.evaluate(() => window.auditMotion.filter(name => name.includes('motion-enter'))), [],
    'loading older records never animates the whole list');

  // Search, category, actor and date filters submit explicitly; a filter change may fade the list.
  const seededAudit = await apiGet('/api/audit-events?q=' + encodeURIComponent(`A66-ACT-${unique}`));
  assert.equal(seededAudit.total, 57);
  let typed = 0; const countTyping = request => { if (request.url().includes('/api/audit-events?')) typed++; };
  page.on('request', countTyping);
  await page.locator('#audit-filter input[name="q"]').fill(`A66-ACT-${unique}`);
  page.off('request', countTyping);
  assert.equal(typed, 0, 'typing a search never queries');
  const searched = await auditLoad(() => page.locator('#audit-filter').getByRole('button', {name: 'Terapkan filter', exact: true}).click());
  assert.deepEqual(searched.params, {limit: '25', q: `A66-ACT-${unique}`, category: 'all'});
  assert.equal(await page.locator('#audit-summary').innerText(), `${n(57)} catatan sesuai filter.`);
  const category = seededAudit.items[0].category;
  await page.locator('#audit-category').selectOption(category);
  await page.locator('#audit-actor').selectOption(seededAudit.items[0].actor_id);
  await page.locator('#audit-filter input[name="start_date"]').fill(today);
  await page.locator('#audit-filter input[name="end_date"]').fill(today);
  const filtered = await auditLoad(() => page.locator('#audit-filter').getByRole('button', {name: 'Terapkan filter', exact: true}).click());
  assert.deepEqual(filtered.params, {limit: '25', q: `A66-ACT-${unique}`, category, actor_id: seededAudit.items[0].actor_id,
    start_date: today, end_date: today});
  const filteredApi = await apiGet('/api/audit-events?' + new URLSearchParams(filtered.params));
  assert.equal(await page.locator('#audit-summary').innerText(), `${n(filteredApi.total)} catatan sesuai filter.`);
  assert.deepEqual(await rowIds(), filteredApi.items.map(item => item.id));
  await toTop(); await shot('12-audit-filtered');

  // Evidence dialog: every field, both raw JSON documents, escaped, and navigation only.
  const subject = filteredApi.items.find(item => JSON.stringify(item.changes || {}).includes('<b>A6.6</b>')) || filteredApi.items[0];
  const detail = await apiGet('/api/audit-events/' + subject.id);
  await page.locator(`#audit-list [data-action="audit-event"][data-id="${subject.id}"]`).click();
  await page.getByRole('heading', {name: `Audit · ${detail.subject_reference || detail.operation}`, exact: true}).waitFor();
  const facts = await page.locator('#dialog-content .audit-facts .detail-field').evaluateAll(fields =>
    fields.map(field => [field.querySelector('dt').textContent, field.querySelector('dd').textContent]));
  const stamp = await page.evaluate(value => new Intl.DateTimeFormat('id-ID', {dateStyle: 'medium', timeStyle: 'short',
    timeZone: 'Asia/Jakarta'}).format(new Date(value)), detail.created_at);
  const categoryLabel = await page.locator(`#audit-category option[value="${detail.category}"]`).textContent();
  assert.deepEqual(facts, [['Kategori', categoryLabel], ['Operasi', detail.operation],
    ['Pelaku', `${detail.actor_name} · ${detail.actor_role}`], ['Waktu Jakarta', stamp],
    ['Objek', `${detail.subject_type} · ${detail.subject_id || '-'}`], ['Referensi', detail.subject_reference || '-'],
    ['Request key', detail.request_key]]);
  const evidence = page.locator('#dialog-content .audit-evidence-section');
  assert.deepEqual(await evidence.locator('h3').allInnerTexts(), ['Input perubahan', 'Hasil tersimpan']);
  assert.deepEqual(await evidence.locator('pre.audit-json').evaluateAll(pres => pres.map(pre => pre.textContent)),
    [JSON.stringify(detail.changes, null, 2), JSON.stringify(detail.outcome, null, 2)], 'the stored JSON, unmerged and verbatim');
  assert.ok((await evidence.locator('pre.audit-json').first().textContent()).includes('<b>A6.6</b>'), 'HTML-like input stays text');
  assert.equal(await page.locator('#dialog-content b, #dialog-content script').count(), 0);
  assert.deepEqual(await page.locator('#dialog-content button').allInnerTexts(), ['Kembali ke audit trail'], 'navigation only, no mutation');
  await shot('13-audit-event-detail', dialog);
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await dialogFits(), true);
  await page.setViewportSize({width: 320, height: 800}); await text200(true);
  assert.equal(await dialogFits(), true, 'the evidence dialog fits at 320 / 200%');
  await text200(false); await page.setViewportSize({width: 1440, height: 1000});
  await page.getByRole('button', {name: 'Kembali ke audit trail', exact: true}).click();
  await dialog.waitFor({state: 'hidden'});
  await page.locator('#audit-list .audit-event').first().waitFor();
  assert.equal(await auditView.isVisible(), true);

  // Long raw evidence: a deterministic payload with long unbroken values and a redacted secret.
  const longValue = 'X'.repeat(180);
  await page.route('**/api/audit-events/' + subject.id, route => route.fulfill({status: 200, contentType: 'application/json',
    body: JSON.stringify({...detail, request_key: 'idem-' + 'k'.repeat(120),
      changes: {...detail.changes, note: `Catatan panjang ${longValue}`, access_token: '[REDACTED]', nested: {lines: [{sku: 'SKU-' + longValue, qty: 5}]}},
      outcome: {...detail.outcome, client_secret: '[REDACTED]', snapshot: {record_count: 1200, summarized: true}}})}));
  await page.locator(`#audit-list [data-action="audit-event"][data-id="${subject.id}"]`).click();
  await page.locator('#dialog-content .audit-evidence').waitFor();
  assert.ok((await page.locator('#dialog-content pre.audit-json').first().textContent()).includes('"access_token": "[REDACTED]"'));
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await dialogFits(), true, 'long evidence wraps inside the dialog');
  await shot('14-audit-raw-json-long', dialog);
  await page.setViewportSize({width: 1440, height: 1000});
  await closeDialog();
  await page.unroute('**/api/audit-events/' + subject.id);

  // Empty state, Reset, and the top-level retry.
  await page.locator('#audit-filter input[name="q"]').fill('tidak-ada-' + unique);
  await auditLoad(() => page.locator('#audit-filter').getByRole('button', {name: 'Terapkan filter', exact: true}).click());
  await page.locator('#audit-list .empty-state').getByText('Tidak ada catatan audit yang sesuai filter.', {exact: true}).waitFor();
  assert.equal(await page.locator('#audit-summary').innerText(), '0 catatan sesuai filter.');
  const reset = await auditLoad(() => page.locator('#audit-reset').click());
  assert.deepEqual(reset.log.map(([kind]) => kind), ['users', 'events'], 'Reset rebuilds the workspace');
  assert.deepEqual(reset.params, {limit: '25', category: 'all'});
  assert.deepEqual(await page.locator('#audit-filter').evaluate(form => ['q', 'category', 'actor_id', 'start_date', 'end_date']
    .map(name => form.elements[name].value)), ['', 'all', '', '', '']);
  // Leave first, so the board's own reads are finished before the one /api/users failure is armed.
  await openSidebarDestination('Produksi');
  await page.locator('#summary dd').first().waitFor();
  let failUsers = true;
  await page.route('**/api/users', async route => {
    if (failUsers) { failUsers = false; await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'Daftar pelaku belum tersedia'})}); }
    else await route.continue();
  });
  await openSidebarDestination('Audit trail');
  await page.locator('#audit-body .error-state').getByText('Daftar pelaku belum tersedia', {exact: true}).waitFor();
  assert.equal(await page.locator('#audit-filter').count(), 0, 'a failed setup leaves no broken command bar');
  await auditLoad(() => page.locator('#audit-body [data-action="audit-events"]').click());
  await page.unroute('**/api/users');
  assert.equal(await page.locator('#audit-list .audit-event').count(), 25);

  // ================================ CADANGAN DATA ================================
  const backupView = page.locator('#backup-view');
  const backupButton = page.locator('#download-backup');
  let backupRequests = [];
  const recordBackup = request => { if (new URL(request.url()).pathname === '/api/backup') backupRequests.push([request.method(), request.url()]); };
  page.on('request', recordBackup);
  await openSidebarDestination('Cadangan data');
  await backupView.getByRole('heading', {level: 1, name: 'Cadangan data', exact: true}).waitFor();
  assert.deepEqual(backupRequests, [], 'opening Backup never creates a backup');
  await backupView.getByText('Unduh salinan database Beeloft yang konsisten untuk arsip dan pemulihan.', {exact: true}).waitFor();
  const copy = await backupView.innerText();
  for (const truth of ['order, posisi barang, riwayat, kendala, perubahan jadwal, dan akun', 'hash kunci akses akun',
    'Kunci akses asli tidak disertakan.', 'Simpan kunci yang sudah lu miliki untuk masuk setelah pemulihan.',
    'Salinan diambil saat unduhan diminta; perubahan setelahnya masuk cadangan berikutnya.',
    'hanya bisa diakses orang yang berwenang', '.sqlite3', 'ikuti langkah pemulihan di README proyek', 'Pemulihan tidak dilakukan dari halaman ini.'])
    assert.ok(copy.includes(truth), `backup copy keeps: ${truth}`);
  assert.doesNotMatch(copy, /password|kata sandi|berisi kunci akses|riwayat cadangan|terakhir dicadangkan|jadwal cadangan/i);
  assert.deepEqual(await backupView.locator('button').allInnerTexts(), ['Unduh cadangan database'], 'one action, no restore or upload');
  assert.equal(await backupView.locator('input, [type=file], .status-chip, table').count(), 0);
  assert.equal(await backupView.evaluate(node => node.classList.contains('workspace-page')), true);
  await fits('backup-view', 'Backup at 1440');
  await toTop(); await shot('15-backup-1440-light');
  await theme('dark'); await shot('16-backup-1440-dark'); await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  await fits('backup-view', 'Backup at 390');
  await toTop(); await shot('17-backup-390', null, {fullPage: true});
  await page.setViewportSize({width: 320, height: 800}); await text200(true);
  await fits('backup-view', 'Backup at 320 / 200%');
  assert.equal(await backupButton.isVisible(), true);
  await toTop(); await shot('18-backup-320-200', null, {fullPage: true});
  await text200(false); await page.setViewportSize({width: 1440, height: 1000});

  // Busy lock, one GET, success wording and the timestamped .sqlite3 name.
  let releaseBackup; const backupHeld = new Promise(resolve => { releaseBackup = resolve; });
  await page.route('**/api/backup', async route => { await backupHeld; await route.continue(); });
  const backupDownload = page.waitForEvent('download');
  await backupButton.click();
  await page.waitForFunction(() => document.getElementById('download-backup').textContent === 'Menyiapkan cadangan…');
  assert.equal(await backupButton.isDisabled(), true);
  await backupButton.evaluate(button => button.click());
  await toTop(); await shot('19-backup-preparing');
  releaseBackup();
  const saved = await backupDownload;
  assert.deepEqual(backupRequests.map(([method, url]) => [method, new URL(url).pathname + new URL(url).search]), [['GET', '/api/backup']],
    'exactly one GET /api/backup');
  assert.match(saved.suggestedFilename(), /^beeloft-backup-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z\.sqlite3$/);
  assert.equal(fs.readFileSync(await saved.path()).subarray(0, 16).toString(), 'SQLite format 3\x00');
  await page.locator('#backup-message').getByText('Unduhan dimulai. Periksa daftar unduhan browser untuk memastikan file sudah tersimpan.', {exact: true}).waitFor();
  assert.deepEqual([await backupButton.isEnabled(), await backupButton.textContent()], [true, 'Unduh cadangan database']);
  await page.unroute('**/api/backup');

  // Inline 503 failure: no file, the button restored, and an explicit retry succeeds.
  let backupDownloads = 0; const countBackup = () => backupDownloads++;
  page.on('download', countBackup);
  await page.route('**/api/backup', route => route.fulfill({status: 503, contentType: 'application/json',
    body: JSON.stringify({detail: 'Cadangan belum dapat dibuat. Periksa ruang penyimpanan server lalu coba lagi.'})}));
  await backupButton.click();
  await page.locator('#backup-message.error').getByText('Cadangan belum dapat dibuat. Periksa ruang penyimpanan server lalu coba lagi.', {exact: true}).waitFor();
  assert.equal(backupDownloads, 0, 'a failed backup never downloads a placeholder');
  assert.deepEqual([await backupButton.isEnabled(), await backupButton.textContent()], [true, 'Unduh cadangan database']);
  await toTop(); await shot('20-backup-failure');
  await page.unroute('**/api/backup');
  const retried = page.waitForEvent('download');
  await backupButton.click();
  await retried;
  await page.locator('#backup-message:not(.error)').getByText(/^Unduhan dimulai\./).waitFor();

  // A delayed response cannot start a download after the user left.
  backupDownloads = 0;
  let releaseStale, staleStarted; const staleHeld = new Promise(resolve => { releaseStale = resolve; });
  const staleSeen = new Promise(resolve => { staleStarted = resolve; });
  let staleDone; const staleFinished = new Promise(resolve => { staleDone = resolve; });
  await page.route('**/api/backup', async route => { staleStarted(); await staleHeld; await route.continue(); staleDone(); });
  await backupButton.click(); await staleSeen;
  await openSidebarDestination('Produksi');
  releaseStale(); await staleFinished; await page.waitForTimeout(300);
  assert.equal(backupDownloads, 0, 'a stale backup response starts no download');
  assert.equal(await backupView.isHidden(), true);
  assert.equal(await page.getByText('Unduhan dimulai.', {exact: false}).isVisible(), false, 'no success leaks into another workspace');
  await openSidebarDestination('Cadangan data');
  assert.deepEqual([await page.locator('#backup-message').isHidden(), await backupButton.isEnabled()], [true, true]);
  page.off('download', countBackup);
  page.off('request', recordBackup);
  await page.unroute('**/api/backup');

  // ============================== ADMIN-ONLY GATES ===============================
  const auditEventId = firstPage.items[0].id;
  for (const key of [operator, viewer]) {
    await role(key);
    assert.equal(await page.locator('#audit-trail').isHidden(), true, 'Audit trail is hidden from non-admin roles');
    assert.equal(await page.locator('#backup').isHidden(), true, 'Backup is hidden from non-admin roles');
    await page.locator('#backup').evaluate(button => button.click());
    assert.equal(await backupView.isHidden(), true, 'the activation check refuses a non-admin');
    for (const url of ['/api/audit-events', '/api/audit-events/' + auditEventId, '/api/backup'])
      assert.equal((await fetch(base + url, {headers: {'X-API-Key': key}})).status, 403, `${url} is admin-only`);
    // ...while Activity stays readable.
    await report(() => openSidebarDestination('Laporan aktivitas'));
    assert.equal(await activityView.isVisible(), true);
  }
  await role(admin);
  console.log('A6.6 Activity + Audit + Backup browser QA PASS: three roles read Activity from the Jakarta default, '
    + 'auto-change and submit, stale-filter invalidation, range-wide summary, six event kinds escaped in Jakarta time, '
    + '50-row two-part cursor stable under a late event, full-filter single-flight CSV; admin-only Audit with users-first '
    + 'setup, 25-row sequence cursor, filter total, search/category/actor/date/reset/empty/retry, verbatim escaped evidence; '
    + 'admin-only Backup with one GET, busy lock, .sqlite3 name, inline 503 + retry and a stale-response guard; 20+ review shots.');
};
