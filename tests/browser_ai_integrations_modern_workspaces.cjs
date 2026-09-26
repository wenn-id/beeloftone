const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// A6.5 - Tanya Beeloft + Integrasi modern workspaces, behavioural half.
//
// This module SUPPLEMENTS the business suites that run earlier in the smoke order
// (browser_ai_investigation, browser_ai_investigation_logout, browser_integrations, the four
// Jubelio and four Mekari snapshot suites and the two payroll reconciliation suites). Those own the
// business arithmetic, the idempotent retry, the cross-account refusal and the logout safety. What
// this one owns is the A6.5 presentation and the behaviour that presentation must not have bent:
//
//   Tanya Beeloft - identity, the five starters (fill + focus, never submit), the closed
//   assumptions disclosure with every default/min/max and NO max on as_of, the answer-first
//   result hierarchy, facts / findings / recommendations / limitations, history filters with the
//   50/before cursor and its stale fence, saved detail, append-only feedback, the two supported
//   proposal kinds with their field constraints, the viewer gate, admin approval with executed
//   entity navigation, and the uncertain-save lock with one transaction key.
//
//   Integrasi - identity, ledger-truth context, all five health values, source of truth, refresh
//   that keeps content, a failed load that is not treated as current, a stale response that cannot
//   repaint, all direct actions, the 50/before run ledger, run detail, snapshot histories at
//   limit=100, payroll reconciliations at 25/offset, the no-snapshot state, and no write controls.
//
// It also writes the deterministic A6.5 visual-review set. Pixel widths are never asserted; the
// subject is always a label, a figure, a request parameter or a document overflow.
module.exports = async ({page, login, openSidebarDestination, admin, operator, viewer, apiGet, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const review = process.env.BEELOFT_A65_REVIEW || path.join(shots, 'a65-visual-gate');
  fs.mkdirSync(review, {recursive: true});
  const shot = async (name, target = null, options = {}) => {
    const file = path.join(review, name + '.png');
    if (target) await target.screenshot({path: file});
    else await page.screenshot({path: file, fullPage: false, ...options});
  };
  // Review shots start at the top of the workspace, never wherever an earlier step left the scroller.
  const toTop = () => page.evaluate(() => { document.querySelectorAll('.workspace-main,#main').forEach(node => { node.scrollTop = 0; }); window.scrollTo(0, 0); });
  // A theme change runs the product's own colour transitions; the shot waits for them to finish.
  const theme = async value => {
    await page.evaluate(mode => document.documentElement.setAttribute('data-theme', mode), value);
    await page.waitForTimeout(600);
  };
  const noDocumentOverflow = () => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const dialogFits = () => page.evaluate(() => {
    const d = document.querySelector('dialog'); return d.scrollWidth <= d.clientWidth;
  });
  const dialog = page.locator('dialog');
  const aiView = page.locator('#ai-view');
  const aiForm = page.locator('#ai-form');
  const results = page.locator('#ai-results');
  async function role(key) {
    await page.keyboard.press('Escape');
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
    await login(key);
  }
  const closeDialog = async () => {
    if (await dialog.isVisible()) { await page.keyboard.press('Escape'); await dialog.waitFor({state: 'hidden'}); }
  };
  const writeControls = /Impor|Sync now|Sinkronkan|Kirim snapshot|Catat snapshot|Push|Buat jurnal|Post jurnal|Posting jurnal|Perbaiki jurnal|Bayar invoice|Tagih|Sesuaikan stok|Jalankan ulang|Hapus run|Ubah run/;

  // ============================== TANYA BEELOFT ==============================
  await role(operator);
  await theme('light');
  await openSidebarDestination('Tanya Beeloft');
  await aiView.getByRole('heading', {level: 1, name: 'Tanya Beeloft', exact: true}).waitFor();
  await aiView.getByText('Tanyakan kondisi bisnis dari ledger Beeloft dan simpan hasilnya sebagai investigasi.', {exact: true}).waitFor();
  assert.match(await aiView.locator('.ai-trust').innerText(), /lokal.*hanya membaca ledger Beeloft.*Tidak ada data yang dikirim keluar/s);
  assert.equal(await aiView.evaluate(node => node.classList.contains('workspace-page')), true);
  assert.equal(await page.locator('#ai-results').evaluate(node => node.children.length), 0,
    'activation starts without a stale answer');

  // The five starters fill and focus the question; none of them submits.
  let posts = 0;
  const countPosts = request => { if (request.method() === 'POST' && request.url().endsWith('/api/ai/investigations')) posts++; };
  page.on('request', countPosts);
  const starters = [['Risiko stockout', 'SKU apa yang berisiko stockout?'], ['Approval tertunda', 'Apa yang menunggu approval?'],
    ['Produksi terlambat', 'Order produksi mana yang terlambat?'], ['Kondisi margin', 'Bagaimana kondisi margin?'],
    ['Prioritas hari ini', 'Apa prioritas hari ini?']];
  assert.equal(await aiForm.locator('[data-ai-question]').count(), 5);
  for (const [label, question] of starters) {
    await aiForm.getByRole('button', {name: label, exact: true}).click();
    assert.equal(await page.locator('#ai-question').inputValue(), question);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'ai-question');
  }
  assert.equal(posts, 0, 'a starter never submits');
  const question = page.getByLabel('Pertanyaan bisnis', {exact: true});
  assert.deepEqual(await question.evaluate(node => [node.tagName, node.name, node.required, node.minLength, node.maxLength]),
    ['TEXTAREA', 'question', true, 2, 1000]);
  assert.equal(await page.getByRole('button', {name: 'Analisis dan simpan', exact: true}).getAttribute('id'), 'ai-submit');
  await question.fill('');
  await toTop();
  await shot('01-ai-initial-1440-light');

  // Assumptions: a closed disclosure with every constraint intact, and as_of without a max.
  assert.equal(await aiForm.locator('details.ai-assumptions').evaluate(node => node.open), false);
  await aiForm.getByText('Asumsi analisis', {exact: true}).click();
  const constraints = await aiForm.evaluate(form => ['as_of', 'window_days', 'lead_time_days', 'review_period_days',
    'safety_stock_days', 'batch_multiple'].map(name => {
    const input = form.elements[name];
    return [name, input.type, input.required, input.getAttribute('min'), input.getAttribute('max'), input.getAttribute('value')];
  }));
  assert.deepEqual(constraints, [
    ['as_of', 'date', true, null, null, null],
    ['window_days', 'number', true, '7', '90', '28'], ['lead_time_days', 'number', true, '1', '180', '14'],
    ['review_period_days', 'number', true, '1', '180', '30'], ['safety_stock_days', 'number', true, '0', '90', '7'],
    ['batch_multiple', 'number', true, '1', '100000', '1']]);
  await shot('06-ai-assumptions-open');

  // A future as_of is still accepted, and the result arrives answer-first.
  await question.fill('Apakah stok COST-UI akan stockout?');
  await aiForm.getByLabel('Data sampai tanggal', {exact: true}).fill('2026-12-13');
  await aiForm.getByLabel('Panjang window demand (hari)', {exact: true}).fill('7');
  // Long, still-valid horizons, so COST-UI's projected need outruns the order the earlier AI module
  // already executed and both supported recommendation kinds are present to review.
  await aiForm.getByLabel('Lead time replenishment (hari)', {exact: true}).fill('180');
  await aiForm.getByLabel('Periode review stok (hari)', {exact: true}).fill('180');
  await aiForm.getByLabel('Safety stock (hari)', {exact: true}).fill('90');
  await aiForm.getByLabel('Kelipatan batch produksi (pcs)', {exact: true}).fill('5');
  await page.getByRole('button', {name: 'Analisis dan simpan', exact: true}).click();
  await results.getByRole('heading', {name: 'Jawaban', exact: true}).waitFor();
  assert.equal(posts, 1);
  page.off('request', countPosts);
  const order = await results.evaluate(host => {
    const titles = [...host.querySelectorAll('.investigation-answer-title,.evidence-section h3,.investigation-limits>summary')]
      .map(node => node.textContent.trim());
    return titles;
  });
  assert.deepEqual(order.slice(0, 4), ['Jawaban', 'Fakta pendukung', 'Temuan', 'Rekomendasi'],
    'answer, then evidence, then recommendations');
  assert.equal(order.at(-1), 'Batas analisis', 'limitations close the investigation');
  assert.ok(order.includes('Feedback tim'));
  await results.getByText(/^Analisis lokal · tidak mengirim data keluar · hanya baca/).waitFor();
  assert.match(await results.locator('.investigation-answer .chip-row').innerText(), /Risiko stockout[\s\S]*Keyakinan (tinggi|sedang|rendah)/);
  assert.equal(await results.locator('.investigation-answer .chip-row').innerText().then(text => /%/.test(text)), false,
    'confidence is a word, never a percentage');
  assert.ok(await results.locator('.evidence-section').first().locator('.detail-field').count() > 0, 'facts are a detail grid');
  const recommendations = results.locator('[data-ai-recommendation]');
  assert.deepEqual(await results.locator('[data-ai-recommendation]').evaluateAll(nodes => [...new Set(nodes.map(node => node.dataset.aiRecommendation))].sort()
    .filter(kind => ['create_production_order', 'create_purchase_request'].includes(kind))),
    ['create_production_order', 'create_purchase_request'], 'both supported kinds are present to review');
  assert.ok(await recommendations.count() > 0);
  for (let index = 0; index < await recommendations.count(); index++) {
    const row = recommendations.nth(index);
    assert.ok(await row.getByText('Perlu approval', {exact: true}).isVisible());
    assert.ok(await row.getByText(/^Belum dijalankan/).isVisible());
    const kind = await row.getAttribute('data-ai-recommendation');
    const proposable = ['create_production_order', 'create_purchase_request'].includes(kind);
    assert.equal(await row.getByRole('button', {name: 'Ajukan untuk approval', exact: true}).count(), proposable ? 1 : 0,
      `only the two supported kinds offer a proposal (${kind})`);
  }
  // The first-view review of a result: assumptions collapsed as most operators leave them, and the
  // page scrolled so the composer's action and the start of the answer share the viewport.
  await aiForm.locator('details.ai-assumptions').evaluate(node => { node.open = false; });
  await toTop();
  await page.locator('#ai-submit').evaluate(node => node.scrollIntoView({block: 'start'}));
  await shot('02-ai-result-1440-light');
  await theme('dark');
  await shot('03-ai-result-1440-dark');
  await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await noDocumentOverflow(), true, 'AI result fits 390px');
  await results.scrollIntoViewIfNeeded();
  await shot('04-ai-result-390', null, {fullPage: true});
  await page.setViewportSize({width: 320, height: 720});
  await page.evaluate(() => document.documentElement.style.fontSize = '200%');
  assert.equal(await noDocumentOverflow(), true, 'AI page fits 320px at 200% text');
  await page.locator('#ai-view').evaluate(node => node.scrollIntoView());
  await shot('05-ai-320-200', null, {fullPage: true});
  await page.evaluate(() => document.documentElement.style.fontSize = '');
  await page.setViewportSize({width: 1440, height: 1000});

  // Feedback is an append-only event with the shared reason field.
  const saved = (await apiGet('/api/ai/investigations?q=' + encodeURIComponent('COST-UI akan stockout')))[0];
  await results.getByRole('button', {name: 'Perlu diperbaiki', exact: true}).click();
  await dialog.getByLabel('Alasan / catatan', {exact: true}).fill('Perlu sumber lead time <vendor>');
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await dialog.getByRole('heading', {name: 'Investigasi tersimpan', exact: true}).waitFor();
  await dialog.getByText('0 membantu · 1 perlu diperbaiki · 1 responden', {exact: true}).waitFor();
  assert.equal(await page.locator('vendor').count(), 0);
  await shot('08-ai-saved-investigation-detail', dialog);
  await closeDialog();

  // History: explicit filters, the 50/before cursor, and the stale fence.
  const historyUrls = [];
  const trackHistory = request => { if (request.method() === 'GET' && request.url().includes('/api/ai/investigations?')) historyUrls.push(new URL(request.url())); };
  page.on('request', trackHistory);
  await page.locator('#ai-history-jump').click();
  assert.equal(await page.evaluate(() => document.activeElement.name), 'q', 'the history jump focuses the first filter');
  await page.locator('#ai-history-filter select[name="intent"]').selectOption('stockout');
  await page.locator('#ai-history-filter').getByRole('button', {name: 'Terapkan filter', exact: true}).click();
  await page.locator('#ai-history-list .record-row').first().waitFor();
  const filtered = historyUrls.at(-1);
  assert.deepEqual([filtered.searchParams.get('limit'), filtered.searchParams.get('intent')], ['50', 'stockout']);
  await page.locator('#ai-history-filter input[name="q"]').fill('<tidak-ada-yang-cocok>');
  await page.locator('#ai-history-filter').getByRole('button', {name: 'Terapkan filter', exact: true}).click();
  await page.locator('#ai-history-message').getByText('Tidak ada investigasi yang cocok.', {exact: true}).waitFor();
  assert.equal(await page.locator('#ai-history-list').isVisible(), false, 'an empty list draws no empty box');
  await page.locator('#ai-history-filter input[name="q"]').fill('');
  await page.locator('#ai-history-filter select[name="intent"]').selectOption('all');
  const synthetic = Array.from({length: 50}, (_, index) => ({id: saved.id, sequence: 900000 - index,
    interpretation: 'Risiko stockout', question: `Investigasi sintetis <${index}>`, answer: 'Jawaban sintetis', actor_name: 'QA',
    created_at: saved.created_at, feedback_summary: {helpful: 0, not_helpful: 0, respondents: 0}, action_count: 0}));
  let held = null;
  await page.route('**/api/ai/investigations?*', async route => {
    const url = new URL(route.request().url());
    if (url.searchParams.get('q') === 'lambat') { held = route; return; }
    if (url.searchParams.get('before')) return route.fulfill({json: [synthetic[0]].map(row => ({...row, sequence: 1, question: 'Halaman kedua'}))});
    return route.fulfill({json: synthetic});
  });
  await page.locator('#ai-history-filter input[name="q"]').fill('lambat');
  await page.locator('#ai-history-filter').getByRole('button', {name: 'Terapkan filter', exact: true}).click();
  while (!held) await page.waitForTimeout(20);
  await page.locator('#ai-history-filter input[name="q"]').fill('');
  await page.locator('#ai-history-filter').getByRole('button', {name: 'Terapkan filter', exact: true}).click();
  await page.locator('#ai-history-list').getByText('Investigasi sintetis <49>', {exact: true}).waitFor();
  await held.fulfill({json: [{...synthetic[0], question: 'RESPON-BASI'}]});
  await page.waitForTimeout(200);
  assert.equal(await page.getByText('RESPON-BASI').count(), 0, 'an older history request never paints a newer state');
  assert.equal(await page.locator('#ai-history-list .record-row').count(), 50);
  await page.getByRole('button', {name: 'Muat investigasi sebelumnya', exact: true}).click();
  await page.locator('#ai-history-list').getByText('Halaman kedua', {exact: true}).waitFor();
  assert.equal(historyUrls.at(-1).searchParams.get('before'), String(900000 - 49), 'the cursor is the last row sequence');
  assert.equal(historyUrls.at(-1).searchParams.get('limit'), '50');
  await page.locator('#ai-history').scrollIntoViewIfNeeded();
  await shot('07-ai-history-populated');
  await page.unroute('**/api/ai/investigations?*');
  page.off('request', trackHistory);

  // Proposals: production order PIC list, purchase request numeric constraints, both unexecuted.
  const users = (await apiGet('/api/users')).filter(row => row.active && row.role !== 'viewer').map(row => row.id).sort();
  await results.locator('[data-ai-recommendation="create_production_order"]').getByRole('button', {name: 'Ajukan untuk approval', exact: true}).click();
  await dialog.getByLabel('Referensi order', {exact: true}).waitFor();
  assert.deepEqual((await dialog.locator('select[name="owner_id"] option').evaluateAll(nodes => nodes.map(node => node.value))).sort(), users);
  for (const name of ['reference', 'title', 'owner_id', 'due_date', 'reason']) assert.equal(await dialog.locator(`[name="${name}"]`).count(), 1);
  await dialog.getByText(/Order baru dibuat hanya setelah admin menyetujui proposal dan rekomendasi masih sama/).waitFor();
  await dialog.getByRole('button', {name: 'Batal', exact: true}).click();
  await dialog.waitFor({state: 'hidden'});
  await results.locator('[data-ai-recommendation="create_purchase_request"]').getByRole('button', {name: 'Ajukan untuk approval', exact: true}).click();
  const estimate = dialog.getByLabel('Estimasi total (Rp)', {exact: true});
  assert.deepEqual(await estimate.evaluate(node => [node.min, node.max, node.step, node.required]), ['0.01', '1000000000000', '0.01', true]);
  await dialog.getByText(/PR tersebut tetap masuk workflow approval purchasing/).waitFor();
  const prReference = 'AI-PR-A65-' + Date.now();
  await dialog.getByLabel('Referensi PR', {exact: true}).fill(prReference);
  await dialog.getByLabel('Tanggal kebutuhan', {exact: true}).fill('2026-12-20');
  await estimate.fill('125000');
  await dialog.getByLabel('Alasan / catatan', {exact: true}).fill('Proposal PR dari investigasi A6.5');
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await dialog.getByRole('heading', {name: 'Proposal tindakan AI', exact: true}).waitFor();
  await dialog.getByText(prReference + ' · Menunggu keputusan', {exact: true}).waitFor();
  assert.equal(await dialog.getByRole('button', {name: 'Setujui dan jalankan', exact: true}).count(), 0, 'an operator cannot approve');
  assert.equal(await dialog.getByRole('button', {name: 'Batalkan proposal', exact: true}).count(), 1, 'the actor may cancel');
  assert.equal(await dialog.getByText(/^Tindakan selesai/).count(), 0, 'nothing is executed before approval');
  await shot('09-ai-action-proposal-detail', dialog);
  const proposal = (await apiGet('/api/ai/action-proposals')).find(row => row.reference === prReference);
  assert.ok(proposal);
  assert.equal((await apiGet('/api/purchase-requests')).some(row => row.reference === prReference), false);

  // Viewer reads results but gets neither proposal entry nor decisions.
  await role(viewer);
  await openSidebarDestination('Tanya Beeloft');
  await page.locator('#ai-history-list').getByRole('button', {name: 'Buka investigasi', exact: true}).first().click();
  await dialog.getByRole('heading', {name: 'Jawaban', exact: true}).waitFor();
  assert.equal(await dialog.getByRole('button', {name: 'Ajukan untuk approval', exact: true}).count(), 0);
  await closeDialog();

  // Admin approves: re-validated, executed in the same transaction, then navigable.
  await role(admin);
  await openSidebarDestination('Tanya Beeloft');
  await page.locator(`#ai-history-list [data-action="ai-investigation"][data-id="${proposal.investigation_id}"]`).first().click();
  await dialog.getByText('Tindakan dari investigasi ini', {exact: true}).waitFor();
  await dialog.locator('li').filter({hasText: prReference}).getByRole('button', {name: 'Buka proposal tindakan', exact: true}).click();
  await dialog.getByRole('button', {name: 'Setujui dan jalankan', exact: true}).click();
  await dialog.getByLabel('Alasan / catatan', {exact: true}).fill('Kebutuhan bahan diverifikasi');
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await dialog.getByText('Tindakan selesai. Purchase request sudah dibuat.', {exact: true}).waitFor();
  const approved = await apiGet('/api/ai/action-proposals/' + proposal.id);
  assert.equal(approved.status, 'approved');
  assert.ok(approved.executed_entity_id);
  await dialog.getByRole('button', {name: 'Buka hasil tindakan', exact: true}).click();
  await page.waitForFunction(() => document.getElementById('dialog-title').textContent !== 'Proposal tindakan AI');
  await closeDialog();

  // Uncertain save: one key, the form stays locked, retry replays the same transaction.
  await openSidebarDestination('Tanya Beeloft');
  const keys = [];
  let drop = true;
  await page.route('**/api/ai/investigations', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    keys.push(route.request().headers()['idempotency-key']);
    if (drop) { drop = false; await route.fetch(); return route.abort('failed'); }
    return route.continue();
  });
  await question.fill('Apa prioritas hari ini untuk A6.5?');
  await page.getByRole('button', {name: 'Analisis dan simpan', exact: true}).click();
  await page.getByRole('button', {name: 'Coba ulang penyimpanan', exact: true}).waitFor();
  assert.equal(await question.isDisabled(), true, 'an unresolved transaction keeps the question locked');
  assert.equal(await page.locator('#ai-message').evaluate(node => node.classList.contains('error')), true);
  assert.match(await page.locator('#ai-message').innerText(), /belum terkonfirmasi/);
  await shot('10-ai-uncertain-save');
  await page.getByRole('button', {name: 'Coba ulang penyimpanan', exact: true}).click();
  await results.getByRole('heading', {name: 'Jawaban', exact: true}).waitFor();
  assert.equal(keys.length, 2);
  assert.equal(new Set(keys).size, 1, 'the retry reuses the same transaction key');
  assert.equal((await apiGet('/api/ai/investigations?q=' + encodeURIComponent('prioritas hari ini untuk A6.5'))).length, 1);
  await page.unroute('**/api/ai/investigations');

  // ============================== INTEGRASI ==============================
  const integrations = page.locator('#integrations-view');
  const body = page.locator('#integrations-body');
  await openSidebarDestination('Integrasi');
  await integrations.getByRole('heading', {level: 1, name: 'Integrasi', exact: true}).waitFor();
  await integrations.getByText('Pantau kesehatan sinkronisasi, source of truth, dan snapshot vendor.', {exact: true}).waitFor();
  await body.locator('[data-integration-system="mekari"]').waitFor();
  await body.getByText(/^Status berasal dari ledger run aktual\./).waitFor();
  await body.getByText(/^Batas stale \d+ jam · diperiksa /).waitFor();
  for (const system of ['jubelio', 'mekari']) {
    const surface = body.locator(`[data-integration-system="${system}"]`);
    assert.ok(await surface.locator('.integration-system-head .status-chip').count() === 1, `${system} states its health with a chip`);
    const scopes = surface.locator('[data-integration-scope]');
    assert.ok(await scopes.count() > 0);
    for (let index = 0; index < await scopes.count(); index++)
      assert.match(await scopes.nth(index).innerText(), /Source of truth: .+ · inbound read-only/);
  }
  await body.locator('[data-integration-system="jubelio"]').getByText(/^Mapping SKU: \d+ dari \d+ terhubung · \d+ belum dipetakan\.$/).waitFor();
  for (const label of ['Buka Master SKU', 'Order & penjualan Jubelio', 'Retur Jubelio', 'Listing Jubelio', 'Rekonsiliasi stok Jubelio',
    'Keuangan Mekari', 'Utang Mekari', 'Piutang Mekari', 'Payroll Mekari', 'Pembayaran payroll', 'Akuntansi payroll'])
    assert.equal(await body.getByRole('button', {name: label, exact: true}).count(), 1, label);
  assert.equal(await integrations.getByRole('button', {name: writeControls}).count(), 0, 'no write or sync control on the page');
  await theme('light');
  await toTop();
  await shot('11-integrations-1440-light');
  await theme('dark');
  await shot('12-integrations-1440-dark');
  await theme('light');
  await page.setViewportSize({width: 390, height: 844});
  assert.equal(await noDocumentOverflow(), true);
  await shot('13-integrations-390', null, {fullPage: true});
  await page.setViewportSize({width: 320, height: 720});
  await page.evaluate(() => document.documentElement.style.fontSize = '200%');
  assert.equal(await noDocumentOverflow(), true, 'Integrasi fits 320px at 200% text');
  await shot('14-integrations-320-200', null, {fullPage: true});
  await page.evaluate(() => document.documentElement.style.fontSize = '');
  await page.setViewportSize({width: 1440, height: 1000});

  // Manual refresh keeps the report on screen; a stale response cannot repaint it.
  let calls = 0, releaseFirst;
  const firstHeld = new Promise(resolve => { releaseFirst = resolve; });
  await page.route('**/api/integrations', async route => {
    calls++;
    if (calls === 1) {
      const response = await route.fetch(); const json = await response.json();
      json.systems[0].label = 'LABEL-BASI';
      await firstHeld; return route.fulfill({json});
    }
    return route.continue();
  });
  await integrations.getByRole('button', {name: 'Muat ulang status', exact: true}).click();
  await page.waitForFunction(() => document.getElementById('integrations-body').getAttribute('aria-busy') === 'true');
  assert.ok(await body.locator('[data-integration-system]').count() === 2, 'refresh keeps the existing systems visible');
  await integrations.getByRole('button', {name: 'Muat ulang status', exact: true}).click();
  await page.waitForFunction(() => document.getElementById('integrations-body').getAttribute('aria-busy') === null);
  releaseFirst();
  await page.waitForTimeout(300);
  assert.equal(await page.getByText('LABEL-BASI').count(), 0, 'an older integrations response never repaints a newer one');
  await page.unroute('**/api/integrations');

  // A failed load replaces the report instead of leaving it looking current, and retry works.
  let failOnce = true;
  await page.route('**/api/integrations', async route => {
    if (failOnce) { failOnce = false; return route.fulfill({status: 503, json: {detail: 'Ledger integrasi <sibuk>'}}); }
    return route.continue();
  });
  await integrations.getByRole('button', {name: 'Muat ulang status', exact: true}).click();
  await body.locator('.error-state').getByText('Ledger integrasi <sibuk>', {exact: true}).waitFor();
  assert.equal(await body.locator('[data-integration-system]').count(), 0);
  await body.getByRole('button', {name: 'Coba lagi', exact: true}).click();
  await body.locator('[data-integration-system="jubelio"]').waitFor();
  await page.unroute('**/api/integrations');

  // All five health values, rendered from a deterministic payload.
  const scope = (key, health, run = null) => ({scope: key, domain: 'Domain ' + key, source_of_truth: 'Vendor <SoT>', health,
    age_minutes: run ? 135 : null, latest_run: run});
  const mixed = {generated_at: new Date().toISOString(), stale_after_minutes: 180, systems: [
    {system: 'jubelio', label: 'Jubelio', health: 'failed', attention_count: 4,
     product_mapping: {mapped_products: 3, total_products: 5, unmapped_products: 2}, scopes: [
      scope('a', 'healthy', {id: 'r1', records_read: 12, records_written: 12, error: ''}),
      scope('b', 'failed', {id: 'r2', records_read: 4, records_written: 0, error: 'Vendor <timeout> saat membaca'}),
      scope('c', 'stale', {id: 'r3', records_read: 9, records_written: 9, error: ''}),
      scope('d', 'never_synced'), scope('e', 'incomplete', {id: 'r4', records_read: 3, records_written: 1, error: ''})]},
    {system: 'mekari', label: 'Mekari', health: 'healthy', attention_count: 0, scopes: [scope('f', 'healthy', {id: 'r5', records_read: 1, records_written: 1, error: ''})]}]};
  await page.route('**/api/integrations', route => route.fulfill({json: mixed}));
  await integrations.getByRole('button', {name: 'Muat ulang status', exact: true}).click();
  const jubelio = body.locator('[data-integration-system="jubelio"]');
  for (const [key, label] of [['a', 'Sehat'], ['b', 'Gagal'], ['c', 'Stale'], ['d', 'Belum pernah sync'], ['e', 'Belum lengkap']])
    await jubelio.locator(`[data-integration-scope="${key}"] .status-chip`).getByText(label, {exact: true}).waitFor();
  await jubelio.locator('[data-integration-scope="d"]').getByText('Belum ada run', {exact: true}).waitFor();
  await jubelio.locator('[data-integration-scope="c"]').getByText('2 jam lalu · dibaca 9 · ditulis 9', {exact: true}).waitFor();
  await jubelio.getByText('Vendor <timeout> saat membaca', {exact: true}).waitFor();
  assert.equal(await page.locator('timeout, SoT').count(), 0);
  await body.getByText('Batas stale 3 jam', {exact: false}).waitFor();
  await toTop();
  await shot('15-integrations-mixed-health');
  await page.unroute('**/api/integrations');
  await integrations.getByRole('button', {name: 'Muat ulang status', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('integrations-body').textContent.includes('Domain a'));

  // Run ledger: explicit filters, limit=50 with a before cursor, an immutable detail.
  const runUrls = [];
  const trackRuns = request => { if (request.url().includes('/api/integration-sync-runs?')) runUrls.push(new URL(request.url())); };
  page.on('request', trackRuns);
  await integrations.getByRole('button', {name: 'Riwayat sinkronisasi', exact: true}).click();
  await dialog.getByRole('heading', {name: 'Riwayat sinkronisasi', exact: true}).waitFor();
  await dialog.locator('#integration-run-list .record-row').first().waitFor();
  await dialog.locator('#integration-run-filter select[name="system"]').selectOption('jubelio');
  await dialog.locator('#integration-run-filter select[name="status"]').selectOption('failed');
  await dialog.getByRole('button', {name: 'Terapkan filter', exact: true}).click();
  await page.waitForFunction(() => document.querySelector('#integration-run-list .record-row'));
  const runQuery = runUrls.at(-1).searchParams;
  assert.deepEqual([runQuery.get('limit'), runQuery.get('system'), runQuery.get('status'), runQuery.get('before')], ['50', 'jubelio', 'failed', null]);
  assert.equal(await dialog.getByRole('button', {name: writeControls}).count(), 0);
  await shot('16-integration-run-history', dialog);
  page.off('request', trackRuns);
  await dialog.getByRole('button', {name: 'Buka rincian run', exact: true}).first().click();
  await dialog.getByRole('heading', {name: 'Rincian sinkronisasi', exact: true}).waitFor();
  for (const label of ['Mulai', 'Selesai', 'Durasi', 'Record dibaca', 'Record ditulis', 'Cursor eksternal', 'Dicatat oleh', 'Dicatat pada'])
    await dialog.locator('dt').getByText(label, {exact: true}).waitFor();
  await dialog.getByText(/^\d+ detik$/).waitFor();
  await dialog.getByText('Alasan / konteks', {exact: true}).first().waitFor();
  assert.equal(await dialog.getByRole('button', {name: /Ulang|Retry|Hapus|Ubah|Sinkron/}).count(), 0, 'a run record is immutable');
  await shot('17-integration-run-detail', dialog);
  await closeDialog();

  // Snapshot histories ask for limit=100; payroll reconciliations for 25/offset.
  const snapshotUrls = [];
  const trackSnapshots = request => { if (/\/api\/(integrations\/|payroll-)/.test(request.url())) snapshotUrls.push(request.url()); };
  page.on('request', trackSnapshots);
  const open = async (button, heading) => {
    await closeDialog();
    await body.getByRole('button', {name: button, exact: true}).click();
    await dialog.getByRole('heading', {name: heading, exact: true}).waitFor();
    await page.waitForFunction(() => !document.querySelector('#dialog-content .loading-state'));
    assert.equal(await dialog.getByRole('button', {name: writeControls}).count(), 0, `${heading} offers no write control`);
  };
  const fits200 = async name => {
    await page.setViewportSize({width: 320, height: 720});
    await page.evaluate(() => document.documentElement.style.fontSize = '200%');
    // On failure the message names the elements that stick out, so a regression is diagnosable.
    const wide = await page.evaluate(() => {
      const d = document.querySelector('dialog'), left = d.getBoundingClientRect().left, width = d.clientWidth;
      return [...d.querySelectorAll('*')].filter(node => node.getBoundingClientRect().right - left > width + 1)
        .slice(0, 6).map(node => node.tagName + '.' + node.className + ':' + (node.textContent || '').slice(0, 30));
    });
    assert.equal(await dialogFits(), true, `${name} fits 320px at 200%: ${wide.join(' | ')}`);
    await page.evaluate(() => document.documentElement.style.fontSize = '');
    await page.setViewportSize({width: 1440, height: 1000});
  };

  await open('Rekonsiliasi stok Jubelio', 'Rekonsiliasi stok Jubelio');
  await dialog.getByText('Perbandingan memakai available Jubelio (sellable dikurangi reserved) dan available ledger Beeloft. Snapshot tidak menulis atau menyesuaikan stok Beeloft.', {exact: true}).waitFor();
  for (const label of ['SKU cocok', 'Selisih stok', 'Tidak ada di snapshot', 'Dikarantina']) await dialog.locator('.metric-label').getByText(label, {exact: true}).waitFor();
  await dialog.getByText('Karantina identifier', {exact: true}).waitFor();
  await shot('18-jubelio-stock-reconciliation', dialog);
  await fits200('stock reconciliation');
  await dialog.getByRole('button', {name: 'Riwayat snapshot', exact: true}).click();
  await dialog.getByRole('heading', {name: 'Riwayat snapshot stok Jubelio', exact: true}).waitFor();
  await dialog.locator('.record-row').first().waitFor();
  await shot('21-jubelio-snapshot-history', dialog);
  await dialog.getByRole('button', {name: 'Rincian snapshot', exact: true}).first().click();
  await dialog.getByRole('heading', {name: 'Rincian snapshot stok Jubelio', exact: true}).waitFor();
  await dialog.getByText('Record dikarantina', {exact: true}).waitFor();
  await shot('22-jubelio-snapshot-detail-quarantine', dialog);

  await open('Order & penjualan Jubelio', 'Order & penjualan Jubelio');
  await dialog.getByText(/^Unit dan penjualan kotor hanya menghitung order berstatus selesai\./).waitFor();
  await shot('19-jubelio-order-summary', dialog);
  await open('Listing Jubelio', 'Listing Jubelio');
  await dialog.getByText(/tidak mengubah master produk, harga internal, atau stok Beeloft\.$/).waitFor();
  await shot('20-jubelio-listing-summary', dialog);
  await open('Retur Jubelio', 'Retur Jubelio');
  await dialog.getByText(/tidak mengubah stok atau retur internal Beeloft\.$/).waitFor();

  // No snapshot is not a healthy zero.
  await closeDialog();
  await page.route('**/api/integrations/jubelio/order-summary', route => route.fulfill({json: {snapshot: null}}));
  await body.getByRole('button', {name: 'Order & penjualan Jubelio', exact: true}).click();
  await dialog.locator('.empty-state').getByText('Belum ada snapshot order Jubelio.', {exact: true}).waitFor();
  assert.equal(await dialog.locator('.metric-strip').count(), 0, 'no zeros are fabricated without a snapshot');
  await page.unroute('**/api/integrations/jubelio/order-summary');

  await open('Keuangan Mekari', 'Keuangan Mekari');
  await dialog.getByText(/Mekari tetap menjadi sumber pencatatan akuntansi; layar ini tidak membuat jurnal atau pembayaran\.$/).waitFor();
  await shot('23-mekari-finance-summary', dialog);
  await open('Utang Mekari', 'Utang Mekari');
  await dialog.getByText(/^Overdue dihitung terhadap tanggal posisi snapshot\./).waitFor();
  await shot('24-mekari-payables-summary', dialog);
  await open('Payroll Mekari', 'Payroll Mekari');
  await dialog.getByText('Angka merupakan ringkasan agregat dari Mekari tanpa identitas karyawan.', {exact: true}).waitFor();
  await dialog.getByText('Approval Beeloft menyimpan otorisasi manajemen tanpa mengubah status Mekari, menjalankan pembayaran, atau membuat jurnal.', {exact: true}).waitFor();
  await shot('25-mekari-payroll-summary', dialog);
  await dialog.getByRole('button', {name: 'Riwayat snapshot payroll', exact: true}).first().click();
  await dialog.getByRole('button', {name: 'Rincian snapshot payroll', exact: true}).first().click();
  await dialog.getByRole('heading', {name: 'Rincian snapshot payroll Mekari', exact: true}).waitFor();
  await dialog.locator('dt').getByText('Cursor eksternal', {exact: true}).waitFor();
  await shot('28-mekari-snapshot-detail', dialog);

  await open('Pembayaran payroll', 'Rekonsiliasi pembayaran payroll');
  await dialog.locator('#payroll-payment-summary .metric-strip').waitFor();
  await shot('26-payroll-payment-reconciliation', dialog);
  await fits200('payment reconciliation');
  await open('Akuntansi payroll', 'Rekonsiliasi akuntansi payroll');
  await dialog.locator('#payroll-accounting-summary .metric-strip').waitFor();
  await shot('27-payroll-accounting-reconciliation', dialog);
  await fits200('accounting reconciliation');
  await closeDialog();
  page.off('request', trackSnapshots);
  for (const fragment of ['finished-goods-snapshots?limit=100', 'payroll-snapshots?limit=100'])
    assert.ok(snapshotUrls.some(url => url.includes(fragment)), fragment);
  for (const endpoint of ['payroll-payment-reconciliation', 'payroll-accounting-reconciliation']) {
    const url = new URL(snapshotUrls.find(item => item.includes('/api/' + endpoint + '?')));
    assert.deepEqual([url.searchParams.get('limit'), url.searchParams.get('offset')], ['25', '0'], endpoint);
  }

  await theme('light');
  console.log('A6.5 Tanya Beeloft + Integrasi browser QA PASS: starters fill without submitting, closed assumptions with '
    + 'unchanged constraints and no as_of max, answer-first evidence hierarchy, unexecuted recommendations, two supported '
    + 'proposal kinds, viewer gate, admin execution, append-only feedback, 50/before history with stale fence, uncertain save '
    + 'with one key; ledger-truth health in five states, source of truth, held refresh, failed-load replacement, stale '
    + 'repaint fence, run ledger 50/before, snapshot 100, payroll 25/offset, no-snapshot state, no write controls, '
    + '390/320@200%, dark, 28 review screenshots.');
};
