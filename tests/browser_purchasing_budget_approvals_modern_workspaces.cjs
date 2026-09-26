const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// A6.7 - Permintaan pembelian + Budget marketing + Inbox approval modern workspaces, behavioural half.
//
// This module SUPPLEMENTS the suites that already own the business rules - the backend suites
// (test_purchase_requests, test_marketing_budget_approvals, test_unified_approvals,
// test_approval_aggregates, test_purchase_orders), browser_purchase_requests, browser_purchase_orders,
// browser_marketing_budgets, browser_unified_approvals, the payment / workforce / payroll approval
// modules and the navigation / motion suites. What it owns is the A6.7 presentation and the
// behaviour that presentation must not have bent:
//
//   Permintaan pembelian - identity, the two utilities in the heading, one command bar with the five
//   unchanged statuses, the first page is `limit=25&status=all` with no cursor, ONE record list per
//   queue (the next page joins it, `before` = the last sequence), rows that are the API page in
//   order, empty / error / retry, escaping, and the Buat PR form's A6 fields with the unchanged
//   payload and duplicate rule.
//   The PR sheet - identity line, facts, lines, reason, rule note, role-gated decisions with one
//   primary, the decision form's A6 reason field and unchanged body, "Buat PO dari PR", PO terkait,
//   append-only history.
//   Master pemasok, Tambah pemasok, Daftar PO - the two utilities in the same grammar.
//   Budget marketing - the same queue idiom, the budget sheet, a rejection, and the form payload.
//   Inbox approval - the default `pending` 25-row offset page, the next page joining the same list,
//   the kind filter, all nine kinds from a deterministic fixture (context, stale, amounts, glyph,
//   escaping), empty / error / "Coba lagi", and "Buka approval" landing in the domain's own sheet.
//
// It also writes the deterministic A6.7 visual-review set. Pixel widths are never asserted; the
// subject is always a label, a figure, a request parameter or an overflow.
module.exports = async ({page, login, openSidebarDestination, admin, operator, viewer, apiGet, work}) => {
  const base = process.env.BEELOFT_QA_BASE;
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const review = process.env.BEELOFT_A67_REVIEW || path.join(shots, 'a67-visual-gate');
  fs.mkdirSync(review, {recursive: true});
  const shot = async (name, target = null, options = {}) => {
    const file = path.join(review, name + '.png');
    // A review shot shows the workspace, not a transient toast or the focus ring a click left behind.
    await page.evaluate(() => { const notice = document.getElementById('notice'); if (notice) notice.hidden = true;
      if (document.activeElement && document.activeElement !== document.body && !document.querySelector('dialog[open]')) document.activeElement.blur(); });
    // ...and never mid page-entry or list-replacement fade.
    await page.waitForFunction(() => !document.querySelector('.motion-enter'));
    // On a phone the workspace, not the document, scrolls: bring the page heading under the chrome.
    if (/-(390|320-200)$/.test(name) && !target) await page.evaluate(() => {
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
  // The floating window clips what overflows it, so each section is also measured against its own
  // edges: at 320px / 200% a control wider than its command bar is clipped whether or not the
  // document scrolls.
  // A box can also stay inside its section while its own text spills out of it - a one-line chip or
  // stamp capped at its column - so a visible-overflow box whose content is wider than itself counts.
  const sectionOverflow = sectionId => page.evaluate(id => {
    const section = document.getElementById(id), box = section.getBoundingClientRect();
    const control = node => ['INPUT', 'SELECT', 'TEXTAREA', 'OPTION'].includes(node.tagName);
    return [...section.querySelectorAll('*')]
      .filter(node => node.getClientRects().length && !node.closest('.visually-hidden'))
      .filter(node => { const rect = node.getBoundingClientRect(); return rect.right > box.right + 1 || rect.left < box.left - 1
        || (!control(node) && node.clientWidth > 0 && node.scrollWidth > node.clientWidth + 1 && getComputedStyle(node).overflowX === 'visible'); })
      .map(node => node.tagName.toLowerCase() + (node.id ? '#' + node.id : '') + (node.className && typeof node.className === 'string' ? '.' + node.className.split(' ')[0] : ''));
  }, sectionId);
  const fits = async (sectionId, where) => {
    assert.equal(await noDocumentOverflow(), true, `document overflow: ${where}`);
    assert.deepEqual(await sectionOverflow(sectionId), [], `content crosses its section: ${where}`);
  };
  const dialog = page.locator('dialog');
  // A dialog fits when it does not scroll sideways. When it does, the offending nodes are named, so a
  // failure says what crossed the edge instead of only that something did.
  const dialogFits = async () => {
    const offenders = await page.evaluate(() => {
      const d = document.querySelector('dialog');
      if (d.scrollWidth <= d.clientWidth) return [];
      // Measured against the content box: a node reaching into the dialog's own padding is what
      // makes it scroll sideways, long before it crosses the border.
      const style = getComputedStyle(d);
      const edge = d.getBoundingClientRect().right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight);
      // A box that crosses the edge, or text that overflows a box which itself stays inside it.
      const named = [...d.querySelectorAll('*')].filter(node => node.getClientRects().length
          && (node.getBoundingClientRect().right > edge + 1 || (node.clientWidth > 0 && node.scrollWidth > node.clientWidth + 1 && getComputedStyle(node).overflowX === 'visible')))
        .map(node => `${node.tagName.toLowerCase()}${node.id ? '#' + node.id : ''}.${String(node.className).split(' ')[0]}+${Math.round(Math.max(node.getBoundingClientRect().right - edge, node.scrollWidth - node.clientWidth))}px`);
      return named.length ? named : [`dialog scrollWidth ${d.scrollWidth} > clientWidth ${d.clientWidth}`];
    });
    if (offenders.length) console.log('dialog overflow:', offenders.slice(0, 12).join(', '));
    return offenders.length === 0;
  };
  // Every sheet and form is measured on a phone and at 320px with 200% text, then restored.
  const sheetFits = async where => {
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await dialogFits(), true, `${where} fits at 390`);
    await page.setViewportSize({width: 320, height: 800}); await text200(true);
    assert.equal(await dialogFits(), true, `${where} fits at 320 / 200%`);
    await text200(false); await page.setViewportSize({width: 1440, height: 1000});
  };
  const closeDialog = async () => {
    if (await dialog.isVisible()) { await page.keyboard.press('Escape'); await dialog.waitFor({state: 'hidden'}); }
  };
  async function role(key) {
    await closeDialog();
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
    await login(key);
  }
  // Every write here goes through the API as a named account, so ownership is real.
  async function post(url, body, apiKey = admin) {
    const response = await fetch(base + url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-API-Key': apiKey,
      'Idempotency-Key': crypto.randomUUID()}, body: JSON.stringify(body)});
    const text = await response.text(); assert.equal(response.status, 201, text); return JSON.parse(text);
  }
  const nf = new Intl.NumberFormat('id-ID');
  const n = value => nf.format(value);
  const paramsOf = url => Object.fromEntries(new URL(url).searchParams);
  const classOf = (node, prefix) => node.evaluate((element, start) => [...element.classList].find(name => name.startsWith(start)) || '', prefix);
  const toneOf = {submitted: 'status-chip-info', pending: 'status-chip-info', approved: 'status-chip-success', rejected: 'status-chip-danger', cancelled: 'status-chip-neutral'};
  const statusLabel = {submitted: 'Menunggu keputusan', pending: 'Menunggu keputusan', approved: 'Disetujui', rejected: 'Ditolak', cancelled: 'Dibatalkan'};
  const kindLabel = {purchase_request: 'Purchasing · PR', purchase_order: 'Purchasing · PO', supplier_payment: 'Finance · pembayaran supplier',
    marketing_budget: 'Marketing · budget kampanye', production_change: 'Production · perubahan order', workforce_leave: 'People · cuti',
    workforce_overtime: 'People · lembur', payroll_batch: 'People · batch payroll', ai_action: 'AI Brain · tindakan'};
  // The product formats dates, money and stamps with the browser's own Intl; expected strings are
  // built there too, so an ICU difference between Node and Chromium can never fake a failure.
  const formats = values => page.evaluate(values => {
    const day = value => new Intl.DateTimeFormat('id-ID', {day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Jakarta'})
      .format(new Date(value.length === 10 ? value + 'T12:00:00+07:00' : value));
    const stamp = value => new Intl.DateTimeFormat('id-ID', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Jakarta'}).format(new Date(value));
    const money = value => 'Rp' + BigInt(value.split('.')[0]).toLocaleString('id-ID') + ',' + value.split('.')[1];
    return values.map(([kind, value]) => kind === 'day' ? day(value) : kind === 'stamp' ? stamp(value) : money(value));
  }, values);
  const format = async (kind, value) => (await formats([[kind, value]]))[0];
  // A queue load is one GET to the list endpoint; it is settled once its load-more control is
  // released again by the finally-block.
  async function queueLoad(pathname, moreId, action) {
    const matches = r => r.method() === 'GET' && new URL(r.url()).pathname === pathname;
    const request = page.waitForRequest(matches);
    const response = page.waitForResponse(r => matches(r.request()));
    await action();
    const sent = await request, body = await (await response).json();
    await page.waitForFunction(id => { const button = document.getElementById(id); return button && !button.disabled; }, moreId);
    return {params: paramsOf(sent.url()), body};
  }
  // What a queue shows, read from the DOM exactly as an operator reads it.
  const queue = hostId => page.locator('#' + hostId).evaluate(host => ({
    hostClass: host.className, lists: host.querySelectorAll(':scope>ul.record-list').length,
    rows: [...host.querySelectorAll('.record-row')].map(row => ({
      hook: row.dataset.purchaseRequest || row.dataset.marketingBudget || row.dataset.approvalKind || '',
      glyph: row.querySelector('.metric-icon use')?.getAttribute('href') || '',
      primary: row.querySelector('.record-row-copy>h3').textContent,
      secondary: row.querySelector('.record-row-copy>.data-secondary')?.textContent ?? null,
      chips: [...row.querySelectorAll('.chip-row .status-chip')].map(chip => [chip.textContent, [...chip.classList].find(name => name.startsWith('status-chip-'))]),
      stamp: row.querySelector('.chip-row>.queue-stamp')?.textContent ?? null,
      meta: [...row.querySelectorAll('.record-row-copy>.data-meta')].map(node => node.textContent),
      amount: row.querySelector('.queue-amount-value')?.textContent ?? null,
      amountLabel: row.querySelector('.queue-amount-label')?.textContent ?? null,
      actions: [...row.querySelectorAll('.record-row-aside button')].map(button => [button.textContent, button.getAttribute('aria-label'), button.className, button.dataset.action, button.dataset.id])}))}));
  const sheet = () => page.locator('#dialog-content').evaluate(root => ({
    line: root.querySelector('.request-identity>.workspace-meta')?.textContent ?? null,
    title: root.querySelector('.request-identity>h3')?.textContent ?? null,
    chips: [...root.querySelectorAll('.request-identity .status-chip')].map(chip => [chip.textContent, [...chip.classList].find(name => name.startsWith('status-chip-'))]),
    facts: [...root.querySelectorAll('.request-facts .detail-field')].map(field => [field.querySelector('dt').textContent, field.querySelector('dd').textContent]),
    sections: [...root.querySelectorAll('.request-section>h3')].map(node => node.textContent),
    texts: [...root.querySelectorAll('.request-section>.request-text')].map(node => node.textContent),
    notes: [...root.querySelectorAll('.request-sheet>.info-panel')].map(node => node.textContent),
    decisions: [...root.querySelectorAll('.request-decisions button')].map(button => [button.textContent, button.className]),
    navigation: [...root.querySelectorAll('.request-navigation button')].map(button => button.textContent),
    history: [...root.querySelectorAll('.request-history .timeline-item')].map(item => [item.querySelector('.timeline-event').textContent,
      item.querySelector('.timeline-actor').textContent, item.querySelector('.timeline-detail').textContent]),
    markup: root.querySelectorAll('b, script').length}));
  // Earlier modules may leave the dark theme on, or another account signed in; the review set starts
  // from light, as the admin, on the board.
  await theme('light');
  await role(admin);
  // =================================== SEED ===================================
  // More than one page of each queue, owned by the operator, so paging, ownership and the default
  // pending inbox are all real. The newest PR carries markup-like text on purpose.
  const unique = Date.now();
  const kain = await post('/api/materials', {code: `A67-KAIN-${unique}`, name: 'Kain <linen> & "katun"', unit: 'm'});
  const kancing = await post('/api/materials', {code: `A67-KANCING-${unique}`, name: 'Kancing A6.7', unit: 'pcs'});
  const supplier = await post('/api/suppliers', {code: `a67-sup-${unique}`, name: 'Toko <Kain> & Benang', contact: '', address: '',
    reason: 'CONTOH pemasok A6.7'});
  const order = (await apiGet('/api/orders')).find(item => item.reference === 'DEMO-PROD-001') || (await apiGet('/api/orders'))[0];
  const prs = [];
  for (let index = 0; index < 27; index++) prs.push(await post('/api/purchase-requests', {
    reference: index === 26 ? `A67-PR-${unique}-26 <b>&</b>` : `A67-PR-${unique}-${String(index).padStart(2, '0')}`,
    order_id: index === 25 ? order.id : null, required_date: '2026-12-20', estimated_value: `${150000 + index}.50`,
    reason: `CONTOH <b>kebutuhan</b> & "cadangan" ${index}`,
    lines: [{material_id: kain.id, quantity: '2.125'}, {material_id: kancing.id, quantity: '12'}]}, operator));
  const budgets = [];
  for (let index = 0; index < 26; index++) budgets.push(await post('/api/marketing-budget-requests', {
    reference: `A67-MKT-${unique}-${String(index).padStart(2, '0')}`, campaign_name: `Kampanye <Biru> & "Akhir" ${index}`,
    channel: index % 2 ? 'Meta Ads' : 'TikTok Shop', start_date: '2026-12-01', end_date: '2026-12-31', amount: `${7500000 + index}`,
    objective: `Mendapatkan pesanan <koleksi> akhir tahun ${index}`, reason: `CONTOH plafon kampanye ${index}`}, operator));
  // Names come from the records themselves: the requests are the operator's, the supplier the admin's.
  const operatorName = (await apiGet('/api/purchase-requests/' + prs[0].id)).actor_name;
  const supplierRecord = (await apiGet('/api/suppliers?limit=500')).find(item => item.id === supplier.id);
  const adminName = supplierRecord.actor_name;
  assert.notEqual(operatorName, adminName);

  // =============================== PERMINTAAN PEMBELIAN ===============================
  const prView = page.locator('#purchase-requests-view');
  const prLoad = action => queueLoad('/api/purchase-requests', 'pr-page-more', action);
  const first = await prLoad(() => openSidebarDestination('Permintaan pembelian'));
  assert.deepEqual(first.params, {limit: '25', status: 'all'}, 'the first page is 25 rows of every status, with no cursor');
  await prView.getByRole('heading', {level: 1, name: 'Permintaan pembelian', exact: true}).waitFor();
  await prView.getByText('Ajukan kebutuhan bahan dan tinjau keputusannya sebelum dipesan ke pemasok.', {exact: true}).waitFor();
  assert.equal(await prView.locator('.workspace-eyebrow').innerText(), 'Purchasing · permintaan pembelian');
  assert.match(await page.locator('#purchase-requests-note').innerText(), /PR yang disetujui belum menjadi pesanan ke pemasok/);
  assert.equal(await prView.evaluate(node => node.classList.contains('workspace-page')), true);
  assert.equal(await page.locator('#purchase-requests').getAttribute('aria-current'), 'page');
  assert.deepEqual(await prView.locator('.workspace-actions button:not([hidden])').evaluateAll(buttons => buttons.map(b => [b.textContent, b.className])),
    [['Master pemasok', 'action-quiet'], ['Daftar PO', 'action-secondary'], ['Muat ulang PR', 'action-quiet'], ['Buat PR', 'action-primary']],
    'two utilities, a quiet refresh and ONE primary action');
  assert.equal(await page.locator('#pr-page-filter').evaluate(node => node.classList.contains('command-bar')), true);
  assert.deepEqual(await page.locator('#pr-page-status').evaluate(select => [...select.options].map(o => [o.value, o.textContent])),
    [['all', 'Semua status'], ['submitted', 'Menunggu keputusan'], ['approved', 'Disetujui'], ['rejected', 'Ditolak'], ['cancelled', 'Dibatalkan']]);
  assert.equal(await page.locator('#pr-page-filter').getByLabel('Status PR', {exact: true}).count(), 1);
  const expectPR = async rows => {
    const values = await formats(rows.flatMap(p => [['day', p.required_date], ['stamp', p.created_at], ['money', p.estimated_value]]));
    return rows.map((p, index) => ({hook: p.id, glyph: '#i-cart', primary: p.reference,
      secondary: `${p.order_reference || 'Permintaan umum'} · dibutuhkan ${values[index * 3]}`,
      chips: [[statusLabel[p.status], toneOf[p.status]]], stamp: `${p.actor_name} · ${values[index * 3 + 1]}`, meta: [],
      amount: values[index * 3 + 2], amountLabel: 'estimasi total',
      actions: [['Rincian PR', `Rincian ${p.reference}`, 'action-secondary', 'purchase-request', p.id]]}));
  };
  let shown = await queue('pr-page-list');
  assert.equal(shown.hostClass, 'list-host', 'the host keeps exactly the class the motion contract reads back');
  assert.equal(shown.lists, 1, 'one record list, not a card per request');
  assert.equal(first.body.length, 25);
  assert.deepEqual(shown.rows, await expectPR(first.body), 'every row is the API row, in order, in its A6 grammar');
  assert.equal(await page.locator('#pr-page-count').innerText(), `${n(25)} PR ditampilkan`);
  assert.equal(shown.rows[0].primary, `A67-PR-${unique}-26 <b>&</b>`, 'references render as text');
  assert.equal(await page.locator('#pr-page-list b, #pr-page-list script').count(), 0);
  assert.equal(await page.locator('#pr-page-list .state').count(), 0, 'the loading state is gone once rows arrive');
  // The next page joins the SAME list with the sequence cursor.
  const second = await prLoad(() => page.locator('#pr-page-more').click());
  assert.deepEqual(second.params, {limit: '25', status: 'all', before: String(first.body.at(-1).sequence)});
  shown = await queue('pr-page-list');
  assert.equal(shown.lists, 1, 'the next page joins the same record list');
  assert.deepEqual(shown.rows.map(row => row.hook), [...first.body, ...second.body].map(p => p.id));
  assert.equal(await page.locator('#pr-page-count').innerText(), `${n(25 + second.body.length)} PR ditampilkan`);
  await fits('purchase-requests-view', 'Permintaan pembelian at 1440');
  await toTop(); await shot('01-purchase-requests-1440-light');
  await theme('dark'); await shot('02-purchase-requests-1440-dark'); await theme('light');
  // A filter replaces the queue: no cursor, and the count starts again.
  const filtered = await prLoad(() => page.locator('#pr-page-status').selectOption('submitted'));
  assert.deepEqual(filtered.params, {limit: '25', status: 'submitted'});
  shown = await queue('pr-page-list');
  assert.deepEqual(shown.rows.map(row => row.hook), filtered.body.map(p => p.id));
  assert.ok(shown.rows.every(row => row.chips[0][0] === 'Menunggu keputusan' && row.chips[0][1] === 'status-chip-info'));
  await prLoad(() => page.locator('#pr-page-status').selectOption('all'));
  await page.setViewportSize({width: 390, height: 844});
  await fits('purchase-requests-view', 'Permintaan pembelian at 390');
  await toTop(); await shot('03-purchase-requests-390');
  await page.setViewportSize({width: 320, height: 800}); await text200(true);
  await fits('purchase-requests-view', 'Permintaan pembelian at 320 / 200%');
  await toTop(); await shot('04-purchase-requests-320-200');
  await shot('04b-purchase-requests-320-200-record', page.locator('#pr-page-list .record-row').first());
  await text200(false); await page.setViewportSize({width: 1440, height: 1000});
  // Empty is a state on the queue's own surface; the loading placeholder never lingers beside it.
  await page.route('**/api/purchase-requests?*', route => route.fulfill({status: 200, contentType: 'application/json', body: '[]'}));
  await prLoad(() => page.locator('#purchase-requests-refresh').click());
  await page.locator('#pr-page-list .empty-state').getByText('Belum ada PR yang sesuai filter.', {exact: true}).waitFor();
  assert.equal(await page.locator('#pr-page-list .empty-state-copy').innerText(),
    'Ubah status PR untuk melihat pengajuan lain, atau buat PR untuk kebutuhan bahan baru.');
  assert.deepEqual([await page.locator('#pr-page-list .record-list').count(), await page.locator('#pr-page-count').innerText(),
    await page.locator('#pr-page-more').isHidden()], [0, '', true]);
  await toTop(); await shot('05-purchase-requests-empty');
  await page.unroute('**/api/purchase-requests?*');
  // A failed first load: the danger panel, no loading text, and the load-more control is the retry.
  let failPR = true;
  await page.route('**/api/purchase-requests?*', async route => {
    if (failPR) { failPR = false; await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'Daftar PR A6.7 belum tersedia'})}); }
    else await route.continue();
  });
  await prLoad(() => page.locator('#purchase-requests-refresh').click());
  await page.locator('#pr-page-error').getByText('Daftar PR A6.7 belum tersedia', {exact: true}).waitFor();
  assert.equal(await page.locator('#pr-page-list .state').count(), 0, 'no loading text beside the error');
  const retryPR = page.getByRole('button', {name: 'Coba muat PR lagi', exact: true});
  assert.equal(await retryPR.isVisible(), true);
  await toTop(); await shot('06-purchase-requests-error');
  const retried = await prLoad(() => retryPR.click());
  assert.deepEqual(retried.params, {limit: '25', status: 'all'}, 'the retry repeats the failed page');
  assert.equal(await page.locator('#pr-page-error').isHidden(), true);
  assert.equal((await queue('pr-page-list')).rows.length, 25);
  await page.unroute('**/api/purchase-requests?*');

  // ---- the PR sheet: the operator's general request, opened by the admin ----
  const target = prs[24];
  let detail = await apiGet('/api/purchase-requests/' + target.id);
  await page.locator(`#pr-page-list [data-action="purchase-request"][data-id="${target.id}"]`).click();
  await page.getByRole('heading', {name: 'Rincian PR', exact: true}).waitFor();
  await dialog.getByText(`${target.reference} · Menunggu keputusan`, {exact: true}).waitFor();
  const [needed, estimate, submittedAt] = await formats([['day', detail.required_date], ['money', detail.estimated_value], ['stamp', detail.history[0].created_at]]);
  let view = await sheet();
  assert.deepEqual(view, {line: `${target.reference} · Menunggu keputusan`, title: 'Permintaan umum', chips: [['Menunggu keputusan', 'status-chip-info']],
    facts: [['Dibutuhkan', needed], ['Estimasi total', estimate], ['Bahan diminta', '2 bahan']],
    sections: ['Bahan yang diminta', 'Alasan pengajuan', 'Riwayat keputusan'], texts: [detail.reason],
    notes: ['Persetujuan dicatat oleh admin, termasuk pengajuan sendiri. Belum ada aturan batas nilai. Lihat PO terkait di bawah; PR dengan PO ditutup sudah final; PO aktif harus dibatalkan sebelum PR.'],
    decisions: [['Setujui PR', 'action-primary'], ['Tolak PR', 'action-destructive'], ['Batalkan PR', 'action-secondary']],
    navigation: ['Muat ulang rincian PR', 'Semua PR', 'Inbox approval'],
    history: [['Menunggu keputusan', detail.history[0].actor_name, detail.history[0].reason]], markup: 0}, 'one request sheet, every legacy fact and rule kept');
  assert.equal(detail.history[0].actor_name, operatorName, 'the submission is the operator\'s');
  assert.deepEqual(await page.locator('#dialog-content .request-lines .record-row').evaluateAll(rows => rows.map(row =>
    [row.querySelector('.data-primary').textContent, row.querySelector('.request-quantity').textContent])),
    detail.lines.map(line => [`${line.code} · ${line.name}`, line.unit === 'pcs' ? `${n(Number(line.quantity))} pcs` : '2,125 m']));
  assert.equal(await page.locator('#dialog-content [data-pr-decision]').count(), 3);
  assert.equal(await page.locator('#dialog-content .request-history time').first().innerText(), submittedAt, 'decisions are stamped in Jakarta time');
  await shot('07-pr-sheet-submitted', dialog);
  await page.setViewportSize({width: 390, height: 844});
  await shot('08-pr-sheet-390', dialog);
  await sheetFits('the PR sheet');
  // The decision form: the A6 reason field, and the unchanged decision body.
  await dialog.getByRole('button', {name: 'Setujui PR', exact: true}).click();
  await page.getByRole('heading', {name: 'Setujui PR', exact: true}).waitFor();
  const reason = dialog.getByLabel('Alasan / catatan', {exact: true});
  assert.deepEqual(await reason.evaluate(node => [node.tagName, node.name, node.required, node.maxLength, Boolean(node.closest('.field'))]),
    ['TEXTAREA', 'reason', true, 1000, true]);
  await reason.fill('CONTOH A6.7 kebutuhan diverifikasi');
  await shot('09-pr-decision-form', dialog);
  let decisionPost = page.waitForRequest(r => r.method() === 'POST' && new URL(r.url()).pathname === `/api/purchase-requests/${target.id}/decisions`);
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  assert.deepEqual(JSON.parse((await decisionPost).postData()),
    {reason: 'CONTOH A6.7 kebutuhan diverifikasi', status: 'approved', expected_revision: detail.revision}, 'the decision body is unchanged');
  await dialog.getByText(`${target.reference} · Disetujui`, {exact: true}).waitFor();
  view = await sheet();
  assert.deepEqual(view.chips, [['Disetujui', 'status-chip-success']]);
  assert.deepEqual(view.decisions, [['Batalkan PR', 'action-secondary'], ['Buat PO dari PR', 'action-primary']],
    'an approved PR without an active PO: withdraw it, or take its one forward step');
  assert.deepEqual(view.history.map(event => event[0]), ['Disetujui', 'Menunggu keputusan'], 'history is append-only, newest first');
  assert.deepEqual(view.history[0].slice(1), [adminName, 'CONTOH A6.7 kebutuhan diverifikasi']);
  // A PO from the approved PR appears under "PO terkait", and removes both PR actions again.
  detail = await apiGet('/api/purchase-requests/' + target.id);
  const po = await post('/api/purchase-orders', {reference: `A67-PO-${unique}`, request_id: target.id, expected_revision: detail.revision,
    supplier_id: supplier.id, expected_date: '2026-12-22', terms: 'CONTOH tunai', reason: 'CONTOH PO A6.7',
    prices: detail.lines.map(line => ({material_id: line.material_id, unit_price: '1.00'}))});
  await page.waitForFunction(() => !document.getElementById('pr-page-more')?.disabled);
  await dialog.getByRole('button', {name: 'Muat ulang rincian PR', exact: true}).click();
  await dialog.getByRole('heading', {name: 'PO terkait', exact: true}).waitFor();
  view = await sheet();
  assert.deepEqual(view.sections, ['Bahan yang diminta', 'Alasan pengajuan', 'PO terkait', 'Riwayat keputusan']);
  assert.deepEqual(view.decisions, [], 'an active PO leaves the PR nothing to decide');
  assert.deepEqual(await page.locator('#dialog-content .request-orders .record-row').evaluateAll(rows => rows.map(row => [
    row.querySelector('.data-primary').textContent, row.querySelector('.status-chip').textContent,
    [...row.querySelector('.status-chip').classList].find(name => name.startsWith('status-chip-')),
    row.querySelector('button').textContent, row.querySelector('button').getAttribute('aria-label')])),
    [[po.reference, 'Menunggu keputusan', 'status-chip-info', 'Buka PO', `Buka PO ${po.reference}`]]);
  await shot('10-pr-sheet-with-po', dialog);
  await dialog.getByRole('button', {name: `Buka PO ${po.reference}`, exact: true}).click();
  await page.getByRole('heading', {name: 'Rincian PO', exact: true}).waitFor();
  await dialog.getByText(`${po.reference} · Menunggu keputusan`, {exact: true}).waitFor();
  await closeDialog();

  // ---- Buat PR: the A6 field grammar, the duplicate rule, and the unchanged payload ----
  await page.waitForFunction(() => !document.getElementById('pr-page-more')?.disabled);
  await prView.getByRole('button', {name: 'Buat PR', exact: true}).click();
  await page.getByRole('heading', {name: 'Buat PR', exact: true}).waitFor();
  await dialog.getByLabel('Bahan PR', {exact: true}).waitFor();
  for (const label of ['Referensi PR', 'Tanggal dibutuhkan', 'Order produksi', 'Estimasi total (Rp)', 'Bahan PR', 'Jumlah bahan PR', 'Alasan / catatan'])
    assert.equal(await dialog.getByLabel(label, {exact: true}).evaluate(node => Boolean(node.closest('.field')) && node.labels[0].classList.contains('field-label')), true,
      `${label} is an A6 field with its label above the control`);
  assert.deepEqual(await dialog.getByLabel('Estimasi total (Rp)', {exact: true}).evaluate(node => [node.name, node.type, node.required, node.min, node.max, node.step]),
    ['estimated_value', 'number', true, '0.01', '1000000000000', '0.01']);
  assert.deepEqual(await dialog.getByLabel('Referensi PR', {exact: true}).evaluate(node => [node.name, node.required, node.maxLength]), ['reference', true, 160]);
  assert.deepEqual(await page.locator('#pr-order option').first().evaluate(node => [node.value, node.textContent]), ['', 'Permintaan umum']);
  const materialSelect = dialog.getByLabel('Bahan PR', {exact: true}), quantityInput = dialog.getByLabel('Jumlah bahan PR', {exact: true});
  await materialSelect.selectOption(kancing.id);
  assert.deepEqual(await quantityInput.evaluate(node => [node.step, node.min, node.max]), ['1', '1', '1000000'], 'a pcs material counts in whole units');
  await materialSelect.selectOption(kain.id);
  assert.deepEqual(await quantityInput.evaluate(node => [node.step, node.min]), ['0.001', '0.001']);
  await dialog.getByLabel('Referensi PR', {exact: true}).fill(`A67-PR-FORM-${unique}`);
  await dialog.getByLabel('Tanggal dibutuhkan', {exact: true}).fill('2026-12-24');
  await dialog.getByLabel('Estimasi total (Rp)', {exact: true}).fill('98765.40');
  await quantityInput.fill('1.5');
  await dialog.getByRole('button', {name: 'Tambah bahan PR', exact: true}).click();
  await dialog.getByLabel('Bahan PR', {exact: true}).nth(1).selectOption(kain.id);
  await dialog.getByLabel('Jumlah bahan PR', {exact: true}).nth(1).fill('2');
  await dialog.getByLabel('Alasan / catatan', {exact: true}).fill('CONTOH form PR A6.7');
  let formPosts = 0; const countForm = request => { if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/purchase-requests') formPosts++; };
  page.on('request', countForm);
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await dialog.getByText('Gabungkan bahan yang sama menjadi satu baris.', {exact: true}).waitFor();
  assert.equal(formPosts, 0, 'a duplicated material is refused before anything is sent');
  await shot('11-pr-form-duplicate', dialog);
  await dialog.getByLabel('Bahan PR', {exact: true}).nth(1).selectOption(kancing.id);
  await dialog.getByLabel('Jumlah bahan PR', {exact: true}).nth(1).fill('6');
  const created = page.waitForRequest(r => r.method() === 'POST' && new URL(r.url()).pathname === '/api/purchase-requests');
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  assert.deepEqual(JSON.parse((await created).postData()), {reference: `A67-PR-FORM-${unique}`, required_date: '2026-12-24', order_id: null,
    estimated_value: '98765.40', reason: 'CONTOH form PR A6.7', lines: [{material_id: kain.id, quantity: '1.5'}, {material_id: kancing.id, quantity: '6'}]},
    'the PR payload is exactly the legacy one');
  page.off('request', countForm);
  await dialog.getByText(`A67-PR-FORM-${unique} · Menunggu keputusan`, {exact: true}).waitFor();
  await closeDialog();
  await page.waitForFunction(() => !document.getElementById('pr-page-more')?.disabled);
  await prView.getByRole('button', {name: 'Buat PR', exact: true}).click();
  await dialog.getByLabel('Bahan PR', {exact: true}).waitFor();
  await sheetFits('the PR form');
  await shot('12-pr-form', dialog);
  await closeDialog();

  // ---- Master pemasok and Tambah pemasok ----
  await prView.getByRole('button', {name: 'Master pemasok', exact: true}).click();
  await page.getByRole('heading', {name: 'Master pemasok', exact: true}).waitFor();
  const suppliers = await apiGet('/api/suppliers?limit=500');
  const supplierRows = () => page.locator('#dialog-content .record-list .record-row').evaluateAll(rows => rows.map(row => ({
    primary: row.querySelector('h3').textContent, secondary: row.querySelector('.data-secondary').textContent,
    meta: [...row.querySelectorAll('.data-meta')].map(node => node.textContent), chips: row.querySelectorAll('.status-chip').length})));
  let listed = await supplierRows();
  assert.equal(listed.length, suppliers.length);
  const ours = listed.find(row => row.primary === `${supplierRecord.code} · ${supplierRecord.name}`);
  assert.deepEqual(ours, {primary: `A67-SUP-${unique} · Toko <Kain> & Benang`, secondary: 'Kontak belum diisi',
    meta: ['Alamat belum diisi', 'CONTOH pemasok A6.7', `${adminName} · ${await format('stamp', supplierRecord.created_at)}`], chips: 0},
    'master data, not a status: the two "not filled" words are kept and no chip is invented');
  assert.equal(await dialog.locator('.workspace-subhead .workspace-meta').innerText(), `${n(suppliers.length)} pemasok`);
  assert.deepEqual(await dialog.locator('.workspace-subhead button').evaluateAll(buttons => buttons.map(b => [b.textContent, b.className])),
    [['Semua PR', 'action-quiet'], ['Tambah pemasok', 'action-primary']], 'the admin action comes before a long master');
  await shot('13-suppliers', dialog);
  await sheetFits('Master pemasok');
  await dialog.getByRole('button', {name: 'Tambah pemasok', exact: true}).click();
  await page.getByRole('heading', {name: 'Tambah pemasok', exact: true}).waitFor();
  for (const label of ['Kode pemasok', 'Nama pemasok', 'Kontak pemasok', 'Alamat pemasok', 'Alasan / catatan'])
    assert.equal(await dialog.getByLabel(label, {exact: true}).evaluate(node => Boolean(node.closest('.field'))), true, `${label} is an A6 field`);
  await dialog.getByLabel('Kode pemasok', {exact: true}).fill(`a67-sup2-${unique}`);
  await dialog.getByLabel('Nama pemasok', {exact: true}).fill('Pemasok kedua A6.7');
  await dialog.getByLabel('Kontak pemasok', {exact: true}).fill('CONTOH PIC');
  await dialog.getByLabel('Alamat pemasok', {exact: true}).fill('CONTOH Bandung');
  await dialog.getByLabel('Alasan / catatan', {exact: true}).fill('CONTOH pemasok kedua');
  await shot('14-supplier-form', dialog);
  await sheetFits('the supplier form');
  const supplierPost = page.waitForRequest(r => r.method() === 'POST' && new URL(r.url()).pathname === '/api/suppliers');
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  assert.deepEqual(JSON.parse((await supplierPost).postData()), {code: `a67-sup2-${unique}`, name: 'Pemasok kedua A6.7', contact: 'CONTOH PIC',
    address: 'CONTOH Bandung', reason: 'CONTOH pemasok kedua'}, 'the supplier payload is unchanged');
  await dialog.getByText(`A67-SUP2-${unique} · Pemasok kedua A6.7`, {exact: true}).waitFor();
  listed = await supplierRows();
  assert.equal(listed.length, suppliers.length + 1);
  await closeDialog();

  // ---- Daftar PO ----
  const poLoad = action => queueLoad('/api/purchase-orders', 'po-more', action);
  const pos = await poLoad(() => prView.getByRole('button', {name: 'Daftar PO', exact: true}).click());
  await page.getByRole('heading', {name: 'Daftar PO', exact: true}).waitFor();
  assert.deepEqual(pos.params, {limit: '25', status: 'all'});
  assert.deepEqual(await page.locator('#po-status').evaluate(select => [...select.options].map(o => [o.value, o.textContent])),
    [['all', 'Semua status'], ['pending', 'Menunggu keputusan'], ['issued', 'Aktif'], ['rejected', 'Ditolak'], ['closed', 'Ditutup'], ['cancelled', 'Dibatalkan']]);
  let orders = await queue('po-list');
  assert.equal(orders.lists, 1);
  assert.deepEqual(orders.rows.map(row => row.actions[0][1]), pos.body.map(p => `Rincian PO ${p.reference}`), 'the PO list is the API page, in order');
  const poRow = orders.rows.find(row => row.primary === po.reference);
  assert.deepEqual(poRow, {hook: '', glyph: '#i-file', primary: po.reference, secondary: supplier.name,
    chips: [['Menunggu keputusan', 'status-chip-info'], ['Belum diterima', 'status-chip-neutral']], stamp: null,
    meta: [`Perkiraan datang ${await format('day', '2026-12-22')}`], amount: await format('money', pos.body.find(p => p.id === po.id).total),
    amountLabel: 'total PO', actions: [['Rincian PO', `Rincian PO ${po.reference}`, 'action-secondary', 'purchase-order', po.id]]},
    'approval status and fulfilment are two chips, each in its own words');
  await shot('15-purchase-orders', dialog);
  const issued = await poLoad(() => page.locator('#po-status').selectOption('issued'));
  assert.deepEqual(issued.params, {limit: '25', status: 'issued'}, 'the status still auto-loads');
  orders = await queue('po-list');
  assert.ok(orders.rows.every(row => row.chips[0][0] === 'Aktif' && row.chips[0][1] === 'status-chip-success'));
  await page.route('**/api/purchase-orders?*', route => route.fulfill({status: 200, contentType: 'application/json', body: '[]'}));
  await poLoad(() => page.locator('#po-refresh').click());
  await dialog.locator('.empty-state').getByText('Belum ada PO yang sesuai filter.', {exact: true}).waitFor();
  await page.unroute('**/api/purchase-orders?*');
  await poLoad(() => page.locator('#po-status').selectOption('all'));
  await page.locator('#po-list .record-row').first().waitFor();
  await sheetFits('the PO list');
  await closeDialog();

  // ================================== BUDGET MARKETING ==================================
  const budgetView = page.locator('#marketing-budgets-view');
  const budgetLoad = action => queueLoad('/api/marketing-budget-requests', 'marketing-budget-more', action);
  const budgetFirst = await budgetLoad(() => openSidebarDestination('Budget marketing'));
  assert.deepEqual(budgetFirst.params, {limit: '25', status: 'all'});
  await budgetView.getByRole('heading', {level: 1, name: 'Budget marketing', exact: true}).waitFor();
  await budgetView.getByText('Ajukan plafon kampanye ke manajemen dan pantau keputusannya.', {exact: true}).waitFor();
  assert.equal(await budgetView.locator('.workspace-eyebrow').innerText(), 'Marketing · pengajuan budget');
  assert.equal(await page.locator('#marketing-budgets-note').innerText(),
    'Daftar plafon kampanye yang diajukan ke manajemen. Persetujuan belum mencatat realisasi belanja.');
  assert.deepEqual(await budgetView.locator('.workspace-actions button:not([hidden])').evaluateAll(buttons => buttons.map(b => [b.textContent, b.className])),
    [['Inbox approval', 'action-quiet'], ['Muat ulang', 'action-quiet'], ['Ajukan budget', 'action-primary']]);
  assert.deepEqual(await page.locator('#marketing-budget-status').evaluate(select => [...select.options].map(o => [o.value, o.textContent])),
    [['all', 'Semua status'], ['submitted', 'Menunggu keputusan'], ['approved', 'Disetujui'], ['rejected', 'Ditolak'], ['cancelled', 'Dibatalkan']]);
  const expectBudget = async rows => {
    const values = await formats(rows.flatMap(row => [['day', row.start_date], ['day', row.end_date], ['stamp', row.created_at], ['money', row.amount]]));
    return rows.map((row, index) => ({hook: row.id, glyph: '#i-megaphone', primary: row.reference, secondary: `${row.campaign_name} · ${row.channel}`,
      chips: [[statusLabel[row.status], toneOf[row.status]]], stamp: `${row.actor_name} · ${values[index * 4 + 2]}`, meta: [`${values[index * 4]}–${values[index * 4 + 1]}`],
      amount: values[index * 4 + 3], amountLabel: 'plafon',
      actions: [['Rincian budget', `Rincian budget ${row.reference}`, 'action-secondary', 'marketing-budget-request', row.id]]}));
  };
  let budgetsShown = await queue('marketing-budget-list');
  assert.equal(budgetsShown.hostClass, 'list-host');
  assert.equal(budgetsShown.lists, 1);
  assert.deepEqual(budgetsShown.rows, await expectBudget(budgetFirst.body));
  assert.equal(await page.locator('#marketing-budget-list b, #marketing-budget-list script').count(), 0);
  assert.equal(await page.locator('#marketing-budget-count').innerText(), `${n(25)} pengajuan ditampilkan`);
  const budgetSecond = await budgetLoad(() => page.locator('#marketing-budget-more').click());
  assert.deepEqual(budgetSecond.params, {limit: '25', status: 'all', before: String(budgetFirst.body.at(-1).sequence)});
  budgetsShown = await queue('marketing-budget-list');
  assert.equal(budgetsShown.lists, 1, 'the next page joins the same record list');
  assert.deepEqual(budgetsShown.rows.map(row => row.hook), [...budgetFirst.body, ...budgetSecond.body].map(row => row.id));
  await fits('marketing-budgets-view', 'Budget marketing at 1440');
  await toTop(); await shot('16-marketing-budgets-1440-light');
  await theme('dark'); await shot('17-marketing-budgets-1440-dark'); await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  await fits('marketing-budgets-view', 'Budget marketing at 390');
  await toTop(); await shot('18-marketing-budgets-390');
  await page.setViewportSize({width: 320, height: 800}); await text200(true);
  await fits('marketing-budgets-view', 'Budget marketing at 320 / 200%');
  await toTop(); await shot('19-marketing-budgets-320-200');
  await shot('19b-marketing-budgets-320-200-record', page.locator('#marketing-budget-list .record-row').first());
  await text200(false); await page.setViewportSize({width: 1440, height: 1000});
  // The budget sheet, and a rejection taken from it.
  const budget = budgets[24];
  let budgetDetail = await apiGet('/api/marketing-budget-requests/' + budget.id);
  await page.locator(`#marketing-budget-list [data-action="marketing-budget-request"][data-id="${budget.id}"]`).click();
  await page.getByRole('heading', {name: 'Approval budget marketing', exact: true}).waitFor();
  await dialog.getByText(`${budget.reference} · Menunggu keputusan`, {exact: true}).waitFor();
  const [startDay, endDay, ceiling, askedAt] = await formats([['day', budgetDetail.start_date], ['day', budgetDetail.end_date], ['money', budgetDetail.amount], ['stamp', budgetDetail.created_at]]);
  view = await sheet();
  assert.deepEqual(view, {line: `${budget.reference} · Menunggu keputusan`, title: budgetDetail.campaign_name, chips: [['Menunggu keputusan', 'status-chip-info']],
    facts: [['Channel', budgetDetail.channel], ['Periode kampanye', `${startDay}–${endDay}`], ['Nominal budget', ceiling], ['Diajukan oleh', operatorName], ['Waktu pengajuan', askedAt]],
    sections: ['Objective', 'Alasan pengajuan', 'Riwayat keputusan'], texts: [budgetDetail.objective, budgetDetail.reason],
    notes: ['Persetujuan hanya mengesahkan plafon dan belum mencatat belanja.'],
    decisions: [['Setujui budget', 'action-primary'], ['Tolak budget', 'action-destructive'], ['Batalkan pengajuan', 'action-secondary']],
    navigation: ['Daftar budget', 'Inbox approval'], history: [['Menunggu keputusan', budgetDetail.history[0].actor_name, budgetDetail.history[0].reason]], markup: 0});
  await shot('20-budget-sheet', dialog);
  await sheetFits('the budget sheet');
  await dialog.getByRole('button', {name: 'Tolak budget', exact: true}).click();
  await page.getByRole('heading', {name: 'Tolak budget', exact: true}).waitFor();
  await dialog.getByLabel('Alasan / catatan', {exact: true}).fill('CONTOH A6.7 plafon terlalu tinggi');
  decisionPost = page.waitForRequest(r => r.method() === 'POST' && new URL(r.url()).pathname === `/api/marketing-budget-requests/${budget.id}/decisions`);
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  assert.deepEqual(JSON.parse((await decisionPost).postData()),
    {reason: 'CONTOH A6.7 plafon terlalu tinggi', status: 'rejected', expected_revision: budgetDetail.revision});
  await dialog.getByText(`${budget.reference} · Ditolak`, {exact: true}).waitFor();
  view = await sheet();
  assert.deepEqual([view.chips, view.decisions, view.history.map(event => event[0])],
    [[['Ditolak', 'status-chip-danger']], [], ['Ditolak', 'Menunggu keputusan']], 'a rejected budget has nothing left to decide');
  await theme('dark'); await shot('21-budget-sheet-rejected-dark', dialog); await theme('light');
  await closeDialog();
  await page.waitForFunction(() => !document.getElementById('marketing-budget-more')?.disabled);
  // The budget form: the A6 field grammar and the unchanged payload.
  await budgetView.getByRole('button', {name: 'Ajukan budget', exact: true}).click();
  await page.getByRole('heading', {name: 'Ajukan budget marketing', exact: true}).waitFor();
  for (const label of ['Referensi pengajuan', 'Nama kampanye', 'Channel marketing', 'Tanggal mulai', 'Tanggal selesai', 'Nominal budget (Rp)', 'Objective kampanye', 'Alasan / catatan'])
    assert.equal(await dialog.getByLabel(label, {exact: true}).evaluate(node => Boolean(node.closest('.field'))), true, `${label} is an A6 field`);
  assert.deepEqual(await dialog.getByLabel('Objective kampanye', {exact: true}).evaluate(node => [node.tagName, node.name, node.required, node.maxLength]),
    ['TEXTAREA', 'objective', true, 1000]);
  assert.deepEqual(await dialog.getByLabel('Nominal budget (Rp)', {exact: true}).evaluate(node => [node.name, node.min, node.max, node.step]),
    ['amount', '0.01', '1000000000000', '0.01']);
  await dialog.getByLabel('Referensi pengajuan', {exact: true}).fill(`A67-MKT-FORM-${unique}`);
  await dialog.getByLabel('Nama kampanye', {exact: true}).fill('Kampanye form A6.7');
  await dialog.getByLabel('Channel marketing', {exact: true}).fill('Shopee Ads');
  await dialog.getByLabel('Tanggal mulai', {exact: true}).fill('2027-01-01');
  await dialog.getByLabel('Tanggal selesai', {exact: true}).fill('2027-01-31');
  await dialog.getByLabel('Nominal budget (Rp)', {exact: true}).fill('2500000');
  await dialog.getByLabel('Objective kampanye', {exact: true}).fill('CONTOH objective A6.7');
  await dialog.getByLabel('Alasan / catatan', {exact: true}).fill('CONTOH alasan A6.7');
  await shot('22-budget-form', dialog);
  await sheetFits('the budget form');
  const budgetPost = page.waitForRequest(r => r.method() === 'POST' && new URL(r.url()).pathname === '/api/marketing-budget-requests');
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  assert.deepEqual(JSON.parse((await budgetPost).postData()), {reference: `A67-MKT-FORM-${unique}`, campaign_name: 'Kampanye form A6.7',
    channel: 'Shopee Ads', start_date: '2027-01-01', end_date: '2027-01-31', amount: '2500000', objective: 'CONTOH objective A6.7',
    reason: 'CONTOH alasan A6.7'}, 'the budget payload is unchanged');
  await dialog.getByText(`A67-MKT-FORM-${unique} · Menunggu keputusan`, {exact: true}).waitFor();
  await closeDialog();
  await page.waitForFunction(() => !document.getElementById('marketing-budget-more')?.disabled);

  // =================================== INBOX APPROVAL ===================================
  const inbox = page.locator('#approvals-view');
  const inboxLoad = action => queueLoad('/api/approvals', 'approval-more', action);
  const pending = await inboxLoad(() => page.locator('#approvals').click());
  assert.deepEqual(pending.params, {limit: '25', offset: '0', status: 'pending', kind: 'all'}, 'the inbox opens on pending, every kind, offset 0');
  await inbox.getByRole('heading', {level: 1, name: 'Inbox approval', exact: true}).waitFor();
  await inbox.getByText('Satu antrean untuk keputusan purchasing, finance, marketing, produksi, People, dan tindakan hasil investigasi.', {exact: true}).waitFor();
  assert.equal(await page.locator('#approvals-source-note').innerText(),
    'Nilai serta konteks asal tetap dibaca dari ledger domainnya. Keputusan diambil di rincian tiap approval.');
  assert.deepEqual(await inbox.locator('.queue-sources button').evaluateAll(buttons => buttons.map(b => [b.textContent, b.className, b.dataset.action])),
    [['Semua PR', 'action-quiet', 'purchase-requests'], ['Semua budget marketing', 'action-quiet', 'marketing-budgets'],
      ['Permintaan People', 'action-quiet', 'workforce-requests'], ['Payroll Mekari', 'action-quiet', 'mekari-payroll-summary']],
    'the four domain lists are quiet navigation, labelled as one group');
  assert.equal(await inbox.locator('.queue-sources').getAttribute('role'), 'group');
  assert.deepEqual(await page.locator('#approval-status').evaluate(select => [...select.options].map(o => [o.value, o.textContent])),
    [['pending', 'Menunggu keputusan'], ['all', 'Semua status'], ['approved', 'Disetujui'], ['rejected', 'Ditolak'], ['cancelled', 'Dibatalkan']]);
  assert.deepEqual(await page.locator('#approval-kind').evaluate(select => [...select.options].map(o => [o.value, o.textContent])),
    [['all', 'Semua jenis'], ...Object.entries(kindLabel)]);
  const expectApprovals = async rows => {
    const values = await formats(rows.flatMap(row => [['stamp', row.created_at], ['money', row.amount || '0.00']]));
    return rows.map((row, index) => ({reference: row.reference, secondary: row.title, kind: row.kind,
      chips: [[kindLabel[row.kind], 'status-chip-neutral'], [statusLabel[row.status], toneOf[row.status]]],
      lastMeta: `${row.actor_name} · ${values[index * 2]}`, amount: row.amount ? values[index * 2 + 1] : null,
      action: ['Buka approval', `Rincian approval ${row.reference}`, 'action-secondary', row.id]}));
  };
  const approvalView = rows => rows.map(row => ({reference: row.primary, secondary: row.secondary, kind: row.hook, chips: row.chips,
    lastMeta: row.stamp, amount: row.amount, action: [row.actions[0][0], row.actions[0][1], row.actions[0][2], row.actions[0][4]]}));
  let approvals = await queue('approval-list');
  assert.equal(approvals.hostClass, 'list-host');
  assert.equal(approvals.lists, 1);
  assert.equal(pending.body.length, 25);
  assert.deepEqual(approvalView(approvals.rows), await expectApprovals(pending.body), 'the inbox is the API page, in order, kind before status');
  assert.equal(await page.locator('#approval-count').innerText(), `${n(25)} approval ditampilkan`);
  const pendingNext = await inboxLoad(() => page.locator('#approval-more').click());
  assert.deepEqual(pendingNext.params, {limit: '25', offset: '25', status: 'pending', kind: 'all'}, 'the offset page');
  approvals = await queue('approval-list');
  assert.equal(approvals.lists, 1, 'the next page joins the same record list');
  assert.deepEqual(approvals.rows.map(row => row.actions[0][4]), [...pending.body, ...pendingNext.body].map(row => row.id));
  assert.equal(await page.locator('#approval-count').innerText(), `${n(25 + pendingNext.body.length)} approval ditampilkan`);
  await fits('approvals-view', 'Inbox approval at 1440');
  await toTop(); await shot('23-approvals-1440-light');
  await theme('dark'); await shot('24-approvals-1440-dark'); await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  await fits('approvals-view', 'Inbox approval at 390');
  await toTop(); await shot('25-approvals-390');
  await page.setViewportSize({width: 320, height: 800}); await text200(true);
  await fits('approvals-view', 'Inbox approval at 320 / 200%');
  await toTop(); await shot('26-approvals-320-200');
  await shot('26b-approvals-320-200-record', page.locator('#approval-list .record-row').first());
  await text200(false); await page.setViewportSize({width: 1440, height: 1000});
  // The kind filter narrows the one queue.
  const budgetsOnly = await inboxLoad(() => page.locator('#approval-kind').selectOption('marketing_budget'));
  assert.deepEqual(budgetsOnly.params, {limit: '25', offset: '0', status: 'pending', kind: 'marketing_budget'});
  approvals = await queue('approval-list');
  assert.ok(approvals.rows.length > 0 && approvals.rows.every(row => row.hook === 'marketing_budget' && row.glyph === '#i-megaphone'));
  // "Buka approval" lands in the domain's own sheet.
  const budgetApproval = budgetsOnly.body.find(row => row.id === budgets[23].id);
  await page.getByRole('button', {name: `Rincian approval ${budgetApproval.reference}`, exact: true}).click();
  await page.getByRole('heading', {name: 'Approval budget marketing', exact: true}).waitFor();
  await dialog.getByText(`${budgetApproval.reference} · Menunggu keputusan`, {exact: true}).waitFor();
  await closeDialog();
  await inboxLoad(() => page.locator('#approval-kind').selectOption('purchase_request'));
  await page.getByRole('button', {name: `Rincian approval ${prs[23].reference}`, exact: true}).click();
  await page.getByRole('heading', {name: 'Rincian PR', exact: true}).waitFor();
  await dialog.getByText(`${prs[23].reference} · Menunggu keputusan`, {exact: true}).waitFor();
  await closeDialog();
  await inboxLoad(() => page.locator('#approval-kind').selectOption('all'));

  // All nine kinds from a deterministic fixture: each keeps its own context, and every business
  // string - titles, reasons, names, invoice references - stays text.
  const at = (index, kind, fields) => ({id: `a67-fixture-${index}`, kind, status: 'cancelled', reference: `A67-FX-${index}`,
    title: `Judul <b>${index}</b> & "kutip"`, amount: null, currency: null, reason: `Alasan <script>x</script> ${index}`,
    actor_name: 'Sari <Admin>', created_at: `2031-03-0${9 - index}T02:30:00Z`, context: {}, ...fields});
  const fixture = [
    at(0, 'purchase_request', {amount: '3500000.00', currency: 'IDR', context: {required_date: '2031-03-20', line_count: 3, order_id: null}}),
    at(1, 'purchase_order', {amount: '2750000.50', currency: 'IDR', context: {expected_date: '2031-03-22', line_count: 2}}),
    at(2, 'supplier_payment', {amount: '1250000.00', currency: 'IDR', context: {invoice_reference: 'INV-<01>&', due_date: '2031-04-01'}}),
    at(3, 'marketing_budget', {amount: '7500000.00', currency: 'IDR', context: {channel: 'Meta <Ads>', start_date: '2031-03-01', end_date: '2031-03-31'}}),
    at(4, 'production_change', {context: {old_due_date: '2031-03-10', new_due_date: '2031-03-14', old_owner_name: 'Rina', new_owner_name: 'Budi <PIC>', stale: true}}),
    at(5, 'workforce_leave', {context: {start_date: '2031-03-02', end_date: '2031-03-04', days: 3}}),
    at(6, 'workforce_overtime', {context: {start_date: '2031-03-05', overtime_minutes: 90}}),
    at(7, 'payroll_batch', {amount: '98500000.00', currency: 'IDR', context: {period_start: '2031-02-01', period_end: '2031-02-28', employee_count: 42, stale: true}}),
    at(8, 'ai_action', {context: {recommendation_title: 'Tambah stok <COST-UI>'}}),
  ];
  await page.route('**/api/approvals?*', async route => {
    const query = paramsOf(route.request().url());
    if (query.status !== 'cancelled' || query.kind !== 'all') return route.continue();
    await route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(query.offset === '0' ? fixture : [])});
  });
  await inboxLoad(() => page.locator('#approval-status').selectOption('cancelled'));
  const day = await formats([['day', '2031-03-20'], ['day', '2031-03-22'], ['day', '2031-04-01'], ['day', '2031-03-01'], ['day', '2031-03-31'],
    ['day', '2031-03-10'], ['day', '2031-03-14'], ['day', '2031-03-02'], ['day', '2031-03-04'], ['day', '2031-03-05'], ['day', '2031-02-01'], ['day', '2031-02-28']]);
  approvals = await queue('approval-list');
  assert.deepEqual(approvals.rows.map(row => [row.hook, row.glyph]), [['purchase_request', '#i-cart'], ['purchase_order', '#i-file'],
    ['supplier_payment', '#i-wallet'], ['marketing_budget', '#i-megaphone'], ['production_change', '#i-layers'], ['workforce_leave', '#i-external'],
    ['workforce_overtime', '#i-activity'], ['payroll_batch', '#i-users'], ['ai_action', '#i-sparkles']], 'one record per approval, in API order, each with its domain glyph');
  assert.deepEqual(approvals.rows.map(row => row.meta.slice(0, -1)), [
    [`Dibutuhkan ${day[0]} · 3 bahan`], [`Perkiraan datang ${day[1]} · 2 bahan`], [`Invoice INV-<01>& · jatuh tempo ${day[2]}`],
    [`Meta <Ads> · ${day[3]}–${day[4]}`], [`Target ${day[5]} → ${day[6]}`, 'PIC Rina → Budi <PIC>', 'Permintaan sudah stale.'],
    [`${day[7]}–${day[8]} · 3 hari`], [`${day[9]} · 90 menit`], [`${day[10]}–${day[11]} · 42 karyawan · sumber berubah`], ['Tambah stok <COST-UI>']],
    'every kind keeps the context line it printed before');
  assert.ok(approvals.rows.every((row, index) => row.meta.at(-1) === `Alasan <script>x</script> ${index}` && row.secondary === `Judul <b>${index}</b> & "kutip"`
    && row.stamp.startsWith('Sari <Admin> · ')), 'the reason closes the record; who and when ride on the chip line');
  assert.deepEqual(approvals.rows.map(row => row.amount), ['Rp3.500.000,00', 'Rp2.750.000,50', 'Rp1.250.000,00', 'Rp7.500.000,00', null, null, null, 'Rp98.500.000,00', null],
    'an amount is shown only when the approval has one');
  assert.ok(approvals.rows.every(row => row.chips[1][0] === 'Dibatalkan' && row.chips[1][1] === 'status-chip-neutral'));
  assert.equal(await page.locator('#approval-list b, #approval-list script').count(), 0, 'no business text becomes markup');
  assert.equal(await page.locator('#approval-list .queue-warning use').getAttribute('href'), '#i-alert-triangle', 'a stale change carries a glyph, not only a tint');
  assert.equal(await page.locator('#approval-list .queue-reason').first().evaluate(node => getComputedStyle(node).webkitLineClamp), '2');
  assert.equal(await page.locator('#approval-more').isHidden(), true, 'fewer than 25 rows end the queue');
  await toTop(); await shot('27-approvals-all-kinds');
  await page.setViewportSize({width: 320, height: 800}); await text200(true);
  await fits('approvals-view', 'Inbox approval fixture at 320 / 200%');
  await shot('28-approvals-stale-change-320-200', page.locator('#approval-list .record-row[data-approval-kind="production_change"]'));
  await shot('28b-approvals-payroll-320-200', page.locator('#approval-list .record-row[data-approval-kind="payroll_batch"]'));
  await text200(false); await page.setViewportSize({width: 1440, height: 1000});
  await page.unroute('**/api/approvals?*');
  // Empty, then a failed load with its one retry.
  await page.route('**/api/approvals?*', route => route.fulfill({status: 200, contentType: 'application/json', body: '[]'}));
  await inboxLoad(() => page.getByRole('button', {name: 'Muat ulang inbox', exact: true}).click());
  await page.locator('#approval-list .empty-state').getByText('Tidak ada approval yang sesuai filter.', {exact: true}).waitFor();
  assert.equal(await page.locator('#approval-list .empty-state-copy').innerText(), 'Ubah status atau jenis approval untuk melihat keputusan lain.');
  await toTop(); await shot('29-approvals-empty');
  await page.unroute('**/api/approvals?*');
  let failInbox = true;
  await page.route('**/api/approvals?*', async route => {
    if (failInbox) { failInbox = false; await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'Inbox approval A6.7 sedang sibuk'})}); }
    else await route.continue();
  });
  await inboxLoad(() => page.getByRole('button', {name: 'Muat ulang inbox', exact: true}).click());
  await page.locator('#approval-error').getByText('Inbox approval A6.7 sedang sibuk', {exact: true}).waitFor();
  assert.equal(await page.locator('#approval-list .state').count(), 0, 'no loading text beside the error');
  await toTop(); await shot('30-approvals-error');
  const again = await inboxLoad(() => inbox.getByRole('button', {name: 'Coba lagi', exact: true}).click());
  assert.deepEqual(again.params, {limit: '25', offset: '0', status: 'pending', kind: 'all'});
  assert.equal((await queue('approval-list')).rows.length, 25);
  await page.unroute('**/api/approvals?*');

  // ===================================== ROLES =====================================
  // The operator owns the seeded requests: creation stays open, and only a withdrawal is theirs.
  await role(operator);
  await prLoad(() => openSidebarDestination('Permintaan pembelian'));
  assert.equal(await page.locator('#new-purchase-request').isVisible(), true);
  await page.locator(`#pr-page-list [data-action="purchase-request"][data-id="${prs[22].id}"]`).click();
  await dialog.getByText(`${prs[22].reference} · Menunggu keputusan`, {exact: true}).waitFor();
  assert.deepEqual((await sheet()).decisions, [['Batalkan PR', 'action-secondary']], 'the requester may withdraw their own PR, not decide it');
  await closeDialog();
  await budgetLoad(() => openSidebarDestination('Budget marketing'));
  assert.equal(await page.locator('#new-marketing-budget').isVisible(), true);
  await page.locator(`#marketing-budget-list [data-action="marketing-budget-request"][data-id="${budgets[22].id}"]`).click();
  await dialog.getByText(`${budgets[22].reference} · Menunggu keputusan`, {exact: true}).waitFor();
  assert.deepEqual((await sheet()).decisions, [['Batalkan pengajuan', 'action-secondary']]);
  await closeDialog();
  // The viewer reads every queue and every sheet, and decides nothing.
  await role(viewer);
  await prLoad(() => openSidebarDestination('Permintaan pembelian'));
  assert.equal(await page.locator('#new-purchase-request').isHidden(), true, 'a viewer cannot create a PR');
  await page.locator(`#pr-page-list [data-action="purchase-request"][data-id="${prs[22].id}"]`).click();
  await dialog.getByText(`${prs[22].reference} · Menunggu keputusan`, {exact: true}).waitFor();
  assert.equal(await page.locator('#dialog-content .request-decisions').count(), 0, 'a viewer sees no decision row at all');
  await closeDialog();
  await budgetLoad(() => openSidebarDestination('Budget marketing'));
  assert.equal(await page.locator('#new-marketing-budget').isHidden(), true);
  await page.locator(`#marketing-budget-list [data-action="marketing-budget-request"][data-id="${budgets[22].id}"]`).click();
  await dialog.getByText(`${budgets[22].reference} · Menunggu keputusan`, {exact: true}).waitFor();
  assert.equal(await page.locator('#dialog-content .request-decisions').count(), 0);
  await closeDialog();
  await inboxLoad(() => page.locator('#approvals').click());
  assert.equal((await queue('approval-list')).rows.length, 25, 'a viewer reads the inbox');
  await role(admin);
  console.log('A6.7 Purchasing + Budget + Inbox browser QA PASS: three queues in one idiom (limit 25, unchanged statuses, '
    + 'before / offset paging into ONE record list, API order, empty / error / retry, escaping), PR and budget sheets with '
    + 'role-gated decisions, one primary, unchanged decision bodies and append-only history, Buat PO dari PR and PO terkait, '
    + 'A6 forms with unchanged payloads and the duplicate rule, Master pemasok / Tambah pemasok / Daftar PO, all nine inbox '
    + 'kinds from a fixture, operator and viewer gates, 1440 / 390 / 320@200% and dark; 34 review shots.');
};
