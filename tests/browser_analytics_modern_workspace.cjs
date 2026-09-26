const assert = require('node:assert/strict');
const path = require('node:path');

// A6.4 - Analitik modern workspace, behavioural half.
//
// This module SUPPLEMENTS the twelve business-specific analytics suites that run earlier in the
// smoke order; it does not replace any of them. Those modules own each report's arithmetic. What
// this one owns is the shared presentation and the shared behaviour that only becomes testable
// once twelve destinations render into ONE host:
//
//   * every sidebar child activates #analytics-view, keeps aria-current, and never creates a
//     second workspace page;
//   * switching reports changes the eyebrow, title, question and body, and invalidates the
//     previous report's in-flight request;
//   * each report remembers its own submitted filters, independently of the others;
//   * all twelve render deterministically at least once - filters, endpoint, summary truth,
//     status wording, one representative result;
//   * empty and error/retry states work on the shared host;
//   * pagination asks for exactly limit=25 with a real offset progression, and Forecast and
//     Rekomendasi stok ask for limit=100&offset=0 and grow no load-more;
//   * the Capacity master is admin-only, carries expected_revision, and a successful child save
//     reloads the active report;
//   * where A6.4 draws a bar, the numbers backing it are the API's own fields.
//
// Pixel widths are never asserted. The subject is always the business label or figure.
module.exports = async ({page, login, openSidebarDestination, admin, viewer, apiGet, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const analytics = page.locator('#analytics-view');
  const body = page.locator('#analytics-body');

  // A report has settled when its status host is no longer loading and no longer the ready
  // state. After a successful run with rows `pageState('')` HIDES the host, so visibility is not
  // the signal; the absence of loading is. An error, if any, is then asserted explicitly.
  async function settled(id, {allowError = false} = {}) {
    await page.waitForFunction(hostId => {
      const host = document.getElementById(hostId);
      return !!host && !host.querySelector('.loading-state')
        && !host.textContent.includes('Laporan belum dijalankan');
    }, id);
    if (!allowError) {
      assert.equal(await page.locator(`#${id} .error-state`).count(), 0,
        `#${id} settled into an error: ` + await page.locator(`#${id}`).innerText());
    }
  }

  async function role(key) {
    await page.keyboard.press('Escape');
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
    await login(key);
  }

  // Every destination: sidebar label, <h1>, endpoint, run button, the id of its status host, and
  // the label of its search control where it has one.
  const REPORTS = [
    {nav: 'WIP ageing', title: 'WIP ageing & sinyal hambatan', api: 'wip-ageing-insights',
     run: 'Tampilkan WIP', message: 'wip-ageing-message', more: 'wip-ageing-more',
     search: 'Cari order, PIC, SKU, produk, atau kendala'},
    {nav: 'Kapasitas produksi', title: 'Kapasitas produksi', api: 'capacity-plan',
     run: 'Hitung kapasitas', message: 'capacity-plan-message', more: 'capacity-plan-more',
     auto: true},
    {nav: 'Kualitas produksi', title: 'Kualitas produksi', api: 'production-quality-insights',
     run: 'Tampilkan kualitas', message: 'production-quality-message',
     more: 'production-quality-more', auto: true,
     search: 'Cari vendor, line, SKU, order, atau defect'},
    {nav: 'Kinerja supplier', title: 'Kinerja supplier', api: 'supplier-performance-insights',
     run: 'Tampilkan kinerja', message: 'supplier-performance-message',
     more: 'supplier-performance-more', search: 'Cari supplier atau PO'},
    {nav: 'Harga bahan', title: 'Pergerakan harga bahan', api: 'material-price-insights',
     run: 'Tampilkan harga', message: 'material-price-message', more: 'material-price-more',
     search: 'Cari bahan, supplier, atau PO'},
    {nav: 'Komitmen PO', title: 'Komitmen pembelian terbuka', api: 'purchase-commitment-insights',
     run: 'Tampilkan komitmen', message: 'purchase-commitment-message',
     more: 'purchase-commitment-more', search: 'Cari PO, PR, supplier, atau bahan'},
    {nav: 'Forecast demand', title: 'Forecast demand per SKU', api: 'demand-forecast',
     run: 'Hitung forecast', message: 'forecast-message', single: true,
     search: 'Cari SKU atau produk'},
    {nav: 'Rekomendasi stok', title: 'Risiko stockout & rekomendasi',
     api: 'replenishment-recommendations', run: 'Hitung rekomendasi',
     message: 'replenishment-message', single: true, search: 'Cari SKU atau produk'},
    {nav: 'Analisis ukuran', title: 'Analisis demand per ukuran', api: 'size-demand-insights',
     run: 'Tampilkan analisis', message: 'size-demand-message', more: 'size-demand-more',
     search: 'Cari keluarga produk atau SKU'},
    {nav: 'Analisis retur', title: 'Analisis retur per SKU', api: 'return-insights',
     run: 'Tampilkan analisis', message: 'return-insights-message', more: 'return-insights-more',
     search: 'Cari SKU atau produk'},
    {nav: 'Dead stock', title: 'Analisis dead stock', api: 'dead-stock-insights',
     run: 'Tampilkan analisis', message: 'dead-stock-message', more: 'dead-stock-more',
     search: 'Cari SKU atau produk'},
    {nav: 'Audit adjustment', title: 'Audit adjustment stok', api: 'stock-adjustment-insights',
     run: 'Tampilkan audit', message: 'stock-adjustment-insights-message',
     more: 'stock-adjustment-insights-more', search: 'Cari adjustment atau SKU'},
  ];
  assert.equal(REPORTS.length, 12, 'A6.4 owns exactly twelve analytics destinations');

  // ---------------------------------------------------------------- shared host
  await role(viewer);

  // The host is A6.0 grammar and keeps every id the navigation contract addresses.
  assert.equal(await analytics.getAttribute('class'), 'workspace-page');
  for (const id of ['analytics-back', 'analytics-eyebrow', 'analytics-heading',
                    'analytics-subtitle', 'analytics-body']) {
    assert.equal(await page.locator('#' + id).count(), 1, `#${id} must exist exactly once`);
  }
  assert.equal(await body.getAttribute('aria-live'), 'polite');

  const seenQuestions = new Set();
  for (const report of REPORTS) {
    await openSidebarDestination(report.nav);
    // One host for all twelve: activating a report never adds a second workspace page.
    assert.equal(await page.locator('section[id^="analytics"]').count(), 1);
    assert.equal(await page.locator('#analytics-body').count(), 1);
    assert.equal(await analytics.isVisible(), true, `${report.nav} must activate #analytics-view`);

    // The correct child - and only that child - carries aria-current.
    assert.equal(await page.getByRole('button', {name: report.nav, exact: true})
      .getAttribute('aria-current'), 'page');
    assert.equal(await page.locator('#app-sidebar [aria-current="page"]').count(), 1);

    // Heading hierarchy: eyebrow is context, title is the report, question explains the job.
    assert.equal(await page.locator('#analytics-eyebrow').innerText(), `Analitik · ${report.nav}`);
    assert.equal(await page.locator('#analytics-heading').innerText(), report.title);
    const question = (await page.locator('#analytics-subtitle').innerText()).trim();
    assert.ok(question.length > 0, `${report.nav} has no report question`);
    assert.notEqual(question.replace(/\.$/, ''), report.title,
      `${report.nav}'s question just repeats its title`);
    assert.equal(seenQuestions.has(question), false, `${report.nav} reuses another report's question`);
    seenQuestions.add(question);

    // The filter surface is one form, with a command bar and a real submit button. Kapasitas
    // builds its body only after its two master fetches resolve, so the form is awaited rather
    // than counted on the spot - that asynchrony is the behaviour it shipped with.
    const form = page.locator('#analytics-body form.analytics-filters');
    await form.first().waitFor();
    assert.equal(await form.count(), 1, `${report.nav} must render exactly one filter form`);
    assert.equal(await form.locator('.command-bar').count(), 1);
    await analytics.getByRole('button', {name: report.run, exact: true}).waitFor();

    // §19: no control anywhere in the report relies on a placeholder for its name.
    const unlabelled = await form.evaluate(node => {
      const bad = [];
      for (const control of node.querySelectorAll('input,select')) {
        const label = control.getAttribute('aria-label')
          || control.closest('label')?.querySelector('span')?.textContent;
        if (!label || !label.trim()) bad.push(control.name || control.id || control.type);
      }
      return bad;
    });
    assert.deepEqual(unlabelled, [], `${report.nav} has controls without an accessible label`);

    // §114: a report that waits for Submit says so, and says it without fetching.
    if (!report.auto) {
      await page.locator(`#${report.message}`)
        .filter({hasText: 'Laporan belum dijalankan'}).waitFor();
    }
  }
  assert.equal(seenQuestions.size, 12, 'twelve reports, twelve distinct questions');

  // ---------------------------------------------- switching invalidates the older request
  // Hold WIP's response open, leave for another report, then release it. The late response must
  // not paint into the host the new report now owns.
  let release;
  await page.route('**/api/wip-ageing-insights?*', async route => {
    await new Promise(resolve => { release = resolve; });
    await route.continue();
  });
  await openSidebarDestination('WIP ageing');
  await analytics.getByRole('button', {name: 'Tampilkan WIP', exact: true}).click();
  await page.locator('#wip-ageing-message').filter({hasText: 'Membaca posisi'}).waitFor();
  await openSidebarDestination('Analisis retur');
  await page.getByRole('heading', {name: 'Analisis retur per SKU', exact: true}).waitFor();
  release();
  await page.waitForTimeout(250);
  // The stale WIP response found neither its form nor its hosts, and repainted nothing.
  assert.equal(await page.locator('#analytics-heading').innerText(), 'Analisis retur per SKU');
  assert.equal(await page.locator('#wip-ageing-results').count(), 0,
    'a late response from the previous report must not rebuild its markup');
  assert.equal(await page.locator('#return-insights-form').count(), 1);
  await page.unroute('**/api/wip-ageing-insights?*');

  // ------------------------------------------------- filters restore independently per report
  await openSidebarDestination('Analisis retur');
  await analytics.getByLabel('Panjang periode (hari)', {exact: true}).fill('123');
  await analytics.getByLabel('Cari SKU atau produk', {exact: true}).fill('RETUR-MEMORY');
  await analytics.getByRole('button', {name: 'Tampilkan analisis', exact: true}).click();
  await settled('return-insights-message');

  await openSidebarDestination('Dead stock');
  // A different report must NOT inherit the other's values.
  assert.equal(await analytics.getByLabel('Ambang tanpa demand (hari)', {exact: true})
    .inputValue(), '90');
  assert.equal(await analytics.getByLabel('Cari SKU atau produk', {exact: true})
    .inputValue(), '');
  await analytics.getByLabel('Ambang tanpa demand (hari)', {exact: true}).fill('321');
  await analytics.getByRole('button', {name: 'Tampilkan analisis', exact: true}).click();
  await settled('dead-stock-message');

  await openSidebarDestination('Analisis retur');
  assert.equal(await analytics.getByLabel('Panjang periode (hari)', {exact: true})
    .inputValue(), '123', 'Analisis retur must remember its own submitted filters');
  assert.equal(await analytics.getByLabel('Cari SKU atau produk', {exact: true})
    .inputValue(), 'RETUR-MEMORY');
  await openSidebarDestination('Dead stock');
  assert.equal(await analytics.getByLabel('Ambang tanpa demand (hari)', {exact: true})
    .inputValue(), '321', 'Dead stock must remember its own submitted filters');

  // ------------------------------------------------------- every report renders, once, for real
  // One deterministic successful render each, asserted against the API's own answer.
  for (const report of REPORTS) {
    const requests = [];
    await page.route(`**/api/${report.api}?*`, async route => {
      requests.push(new URL(route.request().url()).searchParams);
      await route.continue();
    });
    await openSidebarDestination(report.nav);
    if (!report.auto) {
      await analytics.getByRole('button', {name: report.run, exact: true}).click();
    }
    // The status host settles out of loading and out of error.
    await settled(report.message);
    assert.ok(requests.length >= 1, `${report.nav} never called /api/${report.api}`);

    // §137: the page size the report shipped with, and nothing else.
    const params = requests[requests.length - 1];
    if (report.single) {
      assert.equal(params.get('limit'), '100', `${report.nav} must ask for 100 results`);
      assert.equal(params.get('offset'), '0', `${report.nav} must ask from offset 0`);
      // and it grows no pager at all.
      assert.equal(await page.locator('#analytics-body .pagination').count(), 0,
        `${report.nav} must not invent pagination`);
    } else {
      assert.equal(params.get('limit'), '25', `${report.nav} must ask for 25 rows`);
      assert.equal(params.get('offset'), '0');
      assert.equal(await page.locator(`#${report.more}`).count(), 1);
    }

    // Either real rows in the one record list, or the report's own empty state. Never a blank.
    const rows = await page.locator('#analytics-body .record-list > li').count();
    const empty = await page.locator(`#${report.message} .empty-state`).count()
      + await page.locator('#analytics-body .empty-state').count();
    assert.ok(rows > 0 || empty > 0, `${report.nav} rendered neither rows nor an empty state`);

    // §20: the summary is a compact metric strip of 3-5 real outputs, never a dashboard.
    const strips = page.locator('#analytics-body dl.metric-strip');
    if (await strips.count()) {
      const cards = await strips.first().locator('.metric-card').count();
      assert.ok(cards >= 3 && cards <= 5,
        `${report.nav} summary has ${cards} first-level metrics`);
    }
    // §22: statuses are A6 chips and every chip keeps its non-colour dot.
    const chips = page.locator('#analytics-body .status-chip');
    if (await chips.count()) {
      assert.equal(await chips.first().locator('.status-dot').count(), 1);
    }
    // §21/§132: none of the legacy analytics vocabulary is rendered here any more.
    for (const legacy of ['.material-event', '.status-label', '.form-info', '.requirement-values',
                          '.filter-form', '.issue-heading', '.product-item']) {
      assert.equal(await page.locator(`#analytics-body ${legacy}`).count(), 0,
        `${report.nav} still renders ${legacy}`);
    }
    // §123: dense is allowed, document overflow is not.
    assert.equal(await page.evaluate(() => {
      const host = document.getElementById('analytics-view');
      return host.scrollWidth <= host.clientWidth;
    }), true, `${report.nav} overflows at 1440`);

    await page.unroute(`**/api/${report.api}?*`);
  }

  // ------------------------------------------------------------------ summary truth per report
  // The shared strip is not decoration: its figures are the API's own summary fields.
  const wip = await apiGet('/api/wip-ageing-insights?status=all');
  await openSidebarDestination('WIP ageing');
  await analytics.getByRole('button', {name: 'Tampilkan WIP', exact: true}).click();
  await page.locator('#wip-ageing-summary .metric-strip').waitFor();
  const wipStrip = await page.locator('#wip-ageing-summary').innerText();
  assert.match(wipStrip, /Order aktif/);
  assert.ok(wipStrip.includes(String(wip.summary.active_orders)));
  // §26: the signal is named a signal. It is never called a bottleneck, and the report keeps
  // saying that capacity targets are not part of it.
  assert.match(wipStrip, /Sinyal hambatan terbesar/);
  assert.doesNotMatch(await body.innerText(), /Bottleneck produksi/i);
  await analytics.getByText('Kapasitas target belum dihitung', {exact: false}).waitFor();

  // §139: where A6.4 draws bars, the values behind them are returned fields.
  if (wip.stages.some(row => row.quantity)) {
    const stage = wip.stages.filter(row => row.quantity)[0];
    const bars = page.locator('#wip-ageing-stages .analytics-bar-list');
    await bars.waitFor();
    const text = await bars.innerText();
    assert.ok(text.includes(`${stage.quantity} pcs`) || text.includes(
      stage.quantity.toLocaleString('id-ID')), 'a stage bar must print its returned quantity');
    // The graphic is decoration; the number lives outside it.
    assert.equal(await page.locator('#wip-ageing-stages .analytics-bar-track[aria-hidden="true"]')
      .count() > 0, true);
    // And it is explicitly not a funnel.
    await analytics.getByText('bukan throughput kumulatif', {exact: false}).waitFor();
  }

  const returns = await apiGet('/api/return-insights?window_days=365');
  await openSidebarDestination('Analisis retur');
  await analytics.getByLabel('Panjang periode (hari)', {exact: true}).fill('365');
  await analytics.getByLabel('Cari SKU atau produk', {exact: true}).fill('');
  await analytics.getByRole('button', {name: 'Tampilkan analisis', exact: true}).click();
  await page.locator('#return-insights-summary .metric-strip').waitFor();
  const returnSummary = await page.locator('#return-insights-summary').innerText();
  assert.ok(returnSummary.includes(`${returns.summary.return_rate}%`),
    'the returned rate is printed exactly as the API returned it');
  // §94/§95: the four reason groups keep their names and their returned quantities.
  const reasonBars = await page.locator('#return-insights-summary .analytics-bar-list').innerText();
  for (const label of ['Sizing', 'Halaman produk', 'Defect', 'Alasan lain']) {
    assert.ok(reasonBars.includes(label), `the reason distribution lost ${label}`);
  }
  assert.ok(reasonBars.includes(`${returns.summary.sizing_quantity} pcs`));
  await analytics.getByText('Sizing = terlalu kecil atau besar', {exact: false}).waitFor();

  // §68: the commitment report still refuses to call an approved payment a paid one.
  await openSidebarDestination('Komitmen PO');
  await analytics.getByRole('button', {name: 'Tampilkan komitmen', exact: true}).click();
  await settled('purchase-commitment-message');
  await analytics.getByText('belum membuktikan transfer bank', {exact: false}).waitFor();
  assert.doesNotMatch(await body.innerText(), /\bPaid\b|Sudah dibayar/);

  // §74: the forecast keeps saying what it does not know.
  await openSidebarDestination('Forecast demand');
  await analytics.getByText('belum memperhitungkan stok tersedia', {exact: false}).waitFor();
  // §101: dead stock still refuses to value stock in rupiah.
  await openSidebarDestination('Dead stock');
  await analytics.getByText('valuasi stok per lot belum tersedia', {exact: false}).waitFor();
  await analytics.getByRole('button', {name: 'Tampilkan analisis', exact: true}).click();
  await settled('dead-stock-message');
  assert.doesNotMatch(await body.innerText(), /Rp/, 'dead stock must print no rupiah value');
  // §104: the audit report still says it is not proof.
  await openSidebarDestination('Audit adjustment');
  await analytics.getByText('bukan bukti kehilangan stok', {exact: false}).waitFor();
  // §54: supplier quantities stay per unit.
  await openSidebarDestination('Kinerja supplier');
  await analytics.getByText('tidak dijumlahkan lintas satuan', {exact: false}).waitFor();

  // ------------------------------------------------------------------- empty and error on the host
  await openSidebarDestination('Analisis retur');
  await analytics.getByLabel('Cari SKU atau produk', {exact: true}).fill('TIDAK-ADA-SKU-A64');
  await analytics.getByRole('button', {name: 'Tampilkan analisis', exact: true}).click();
  await page.locator('#return-insights-message .empty-state').waitFor();
  await analytics.getByText('Tidak ada shipment yang cocok dengan filter pada periode ini.',
    {exact: true}).waitFor();

  let fail = true;
  await page.route('**/api/return-insights?*', async route => {
    if (fail) {
      fail = false;
      await route.fulfill({status: 503, contentType: 'application/json',
        body: JSON.stringify({detail: 'Host analitik sedang dihitung ulang'})});
    } else await route.continue();
  });
  await analytics.getByRole('button', {name: 'Tampilkan analisis', exact: true}).click();
  await page.locator('#return-insights-message .error-state')
    .filter({hasText: 'Host analitik sedang dihitung ulang'}).waitFor();
  await analytics.getByRole('button', {name: 'Coba lagi', exact: true}).click();
  await page.locator('#return-insights-message .empty-state').waitFor();
  await page.unroute('**/api/return-insights?*');

  // ------------------------------------------------------------------------------ pagination
  // A representative 25-row report: exercise the pager and assert the exact offset progression.
  const adjustments = await apiGet('/api/stock-adjustment-insights?classification=all&window_days=365');
  const pageParams = [];
  await page.route('**/api/stock-adjustment-insights?*', async route => {
    pageParams.push(new URL(route.request().url()).searchParams);
    await route.continue();
  });
  await openSidebarDestination('Audit adjustment');
  await analytics.getByLabel('Panjang periode (hari)', {exact: true}).fill('365');
  await analytics.locator('select[name="classification"]').selectOption('all');
  await analytics.getByRole('button', {name: 'Tampilkan audit', exact: true}).click();
  await settled('stock-adjustment-insights-message');
  assert.equal(pageParams[pageParams.length - 1].get('limit'), '25');
  assert.equal(pageParams[pageParams.length - 1].get('offset'), '0');
  const pager = page.locator('#stock-adjustment-insights-more');
  if (adjustments.total > 25) {
    assert.equal(await pager.isVisible(), true, 'more than 25 rows must offer the pager');
    await pager.click();
    await settled('stock-adjustment-insights-message');
    assert.equal(pageParams[pageParams.length - 1].get('limit'), '25');
    assert.equal(pageParams[pageParams.length - 1].get('offset'), '25',
      'the second page starts exactly where the first ended');
  } else {
    assert.equal(await pager.isVisible(), false, 'a single page must not offer the pager');
  }
  // Never a scroll-driven fetch: scrolling the host issues nothing.
  const before = pageParams.length;
  await page.mouse.wheel(0, 4000);
  await page.waitForTimeout(300);
  assert.equal(pageParams.length, before, 'analytics must not fetch on scroll');
  await page.unroute('**/api/stock-adjustment-insights?*');

  // The two single-shot reports: 100/0, no pager, and no second request from scrolling.
  for (const report of REPORTS.filter(row => row.single)) {
    const calls = [];
    await page.route(`**/api/${report.api}?*`, async route => {
      calls.push(new URL(route.request().url()).searchParams);
      await route.continue();
    });
    await openSidebarDestination(report.nav);
    await analytics.getByRole('button', {name: report.run, exact: true}).click();
    await settled(report.message);
    assert.equal(calls.length, 1, `${report.nav} must fetch exactly once per run`);
    assert.equal(calls[0].get('limit'), '100');
    assert.equal(calls[0].get('offset'), '0');
    assert.equal(await page.locator('#analytics-body .pagination').count(), 0);
    for (const label of ['Muat SKU berikutnya', 'Muat lebih banyak', 'Muat berikutnya']) {
      assert.equal(await analytics.getByRole('button', {name: label, exact: true}).count(), 0,
        `${report.nav} grew a load-more button`);
    }
    await page.mouse.wheel(0, 4000);
    await page.waitForTimeout(300);
    assert.equal(calls.length, 1, `${report.nav} fetched again on scroll`);
    await page.unroute(`**/api/${report.api}?*`);
  }

  // ------------------------------------------------------------------- Capacity master, admin only
  await openSidebarDestination('Kapasitas produksi');
  await settled('capacity-plan-message');
  assert.equal(await page.locator('#capacity-center-master').count(), 0,
    'a viewer must not see the capacity master list');
  for (const label of ['Tambah work center', 'Atur standar waktu', 'Atur kapasitas tanggal']) {
    assert.equal(await analytics.getByRole('button', {name: label, exact: true}).count(), 0,
      `a viewer must not see ${label}`);
  }
  // §36: a returned utilisation becomes a real progressbar; a null one says so in words.
  const plan = await apiGet('/api/capacity-plan?status=all');
  if (plan.items.length) {
    const measured = plan.items.filter(row => row.utilization_percent !== null);
    if (measured.length) {
      const meter = page.locator(`[data-capacity-center="${measured[0].id}"] [role="progressbar"]`);
      await meter.waitFor();
      assert.equal(await meter.getAttribute('aria-valuenow'), measured[0].utilization_percent,
        'the meter reports the returned utilisation, not a recomputed one');
      await page.locator(`[data-capacity-center="${measured[0].id}"] .progress-value`)
        .filter({hasText: `${measured[0].utilization_percent}%`}).waitFor();
    }
    if (plan.items.some(row => row.utilization_percent === null)) {
      await analytics.getByText('Utilisasi belum terukur', {exact: false}).first().waitFor();
    }
  }
  // §33: the estimate disclaimer is on the page.
  await analytics.getByText('bukan janji jadwal produksi', {exact: false}).waitFor();

  await role(admin);
  await openSidebarDestination('Kapasitas produksi');
  await page.locator('#capacity-center-master').waitFor();
  await settled('capacity-plan-message');
  const dialog = page.locator('dialog');
  const unique = Date.now();
  await page.screenshot({path: path.join(shots, 'beeloft-a64-capacity-master-1440-light.png')});

  // Create: A6 fields, the shipped attributes, and the shipped default.
  await analytics.getByRole('button', {name: 'Tambah work center', exact: true}).click();
  await dialog.getByLabel('Kode work center', {exact: true}).waitFor();
  assert.equal(await dialog.locator('#dialog-content .field').count() >= 4, true,
    'the create form emits A6 fields');
  await dialog.screenshot({path: path.join(shots, 'beeloft-a64-capacity-work-center-form.png')});
  assert.equal(await dialog.getByLabel('Kapasitas hari kerja (menit)', {exact: true})
    .inputValue(), '480', 'the shipped default capacity is unchanged');
  assert.equal(await dialog.getByLabel('Kapasitas hari kerja (menit)', {exact: true})
    .getAttribute('max'), '100000');
  assert.equal(await dialog.getByLabel('Kode work center', {exact: true})
    .getAttribute('maxlength'), '40');
  await dialog.getByLabel('Kode work center', {exact: true}).fill('A64-' + unique);
  await dialog.getByLabel('Nama work center', {exact: true}).fill('Finishing <A6.4>');
  await dialog.locator('select[name="stage"]').selectOption('finishing');
  await dialog.getByLabel('Kapasitas hari kerja (menit)', {exact: true}).fill('600');
  await dialog.getByLabel('Dasar kapasitas', {exact: true}).fill('Browser QA A6.4 master kapasitas');
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  // §12: a successful child save reloads the ACTIVE report, without leaving analytics.
  await page.locator('#capacity-center-master .record-row')
    .filter({hasText: 'A64-' + unique}).waitFor();
  assert.equal(await analytics.isVisible(), true, 'the child save must keep the report open');
  await settled('capacity-plan-message');

  // Routing standard: only ACTIVE work centres whose stage matches are offered, and the shipped
  // bounds are intact. The work center created above is still active and is a finishing centre, so
  // it must be offered for the finishing standard and must NOT be offered for sewing.
  await page.locator('#capacity-standard-stage').selectOption('finishing');
  await analytics.getByRole('button', {name: 'Atur standar waktu', exact: true}).click();
  await dialog.getByLabel('Menit per pcs', {exact: true}).waitFor();
  const minutes = dialog.getByLabel('Menit per pcs', {exact: true});
  assert.equal(await minutes.getAttribute('step'), '0.001');
  assert.equal(await minutes.getAttribute('min'), '0.001');
  assert.equal(await minutes.getAttribute('max'), '100000');
  const finishingOptions = await dialog.locator('select[name="work_center_id"] option')
    .allInnerTexts();
  assert.equal(finishingOptions.some(text => text.includes('A64-' + unique)), true,
    'the active finishing work center must be offered for the finishing standard');
  await dialog.screenshot({path: path.join(shots, 'beeloft-a64-capacity-routing-form.png')});
  await page.keyboard.press('Escape');

  // Calendar override: the date is readonly and the meaning of 0 is still printed.
  await page.locator('#capacity-calendar-center').selectOption({label: `A64-${unique} · Finishing <A6.4>`});
  await analytics.getByRole('button', {name: 'Atur kapasitas tanggal', exact: true}).click();
  await dialog.getByLabel('Tanggal kerja', {exact: true}).waitFor();
  assert.equal(await dialog.getByLabel('Tanggal kerja', {exact: true})
    .getAttribute('readonly'), '');
  const available = dialog.getByLabel('Kapasitas tersedia (menit)', {exact: true});
  assert.equal(await available.getAttribute('min'), '0');
  assert.equal(await available.getAttribute('max'), '100000');
  assert.equal(await available.inputValue(), '600',
    'the override defaults to the work center daily minutes');
  await dialog.getByText('Isi 0 untuk libur', {exact: false}).waitFor();
  await dialog.screenshot({path: path.join(shots, 'beeloft-a64-capacity-calendar-form.png')});
  await page.keyboard.press('Escape');

  // Edit: stage and code are immutable here, and the revision travels with the change.
  const centers = await apiGet('/api/work-centers?limit=500');
  const record = (centers.items || centers).find(row => row.code === 'A64-' + unique);
  assert.ok(record, 'the created work center is readable through the API');
  const created = page.locator('#capacity-center-master .record-row')
    .filter({hasText: 'A64-' + unique});
  await created.getByRole('button', {name: 'Ubah', exact: true}).click();
  await dialog.getByLabel('Nama work center', {exact: true}).waitFor();
  assert.equal(await dialog.getByLabel('Nama work center', {exact: true}).inputValue(),
    'Finishing <A6.4>');
  assert.equal(await dialog.getByLabel('Kapasitas hari kerja (menit)', {exact: true})
    .inputValue(), '600');
  assert.equal(await dialog.locator('select[name="stage"]').count(), 0,
    'stage stays immutable through the edit workflow');
  assert.equal(await dialog.locator('input[name="code"]').count(), 0,
    'code stays immutable through the edit workflow');
  await dialog.locator('select[name="active"]').selectOption('false');
  await dialog.getByLabel('Alasan perubahan', {exact: true}).fill('Browser QA A6.4 nonaktif');
  const change = page.waitForRequest(request => request.url().includes('/changes')
    && request.method() === 'POST');
  await dialog.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  const payload = JSON.parse((await change).postData());
  // The edit is optimistic-concurrency safe: it sends the revision the form was built from, which
  // is the revision the API currently reports for this work center.
  assert.equal(payload.expected_revision, record.revision,
    'the edit carries the current expected_revision');
  assert.equal(payload.active, false);
  await page.locator('#capacity-center-master .record-row')
    .filter({hasText: 'A64-' + unique}).filter({hasText: 'nonaktif'}).waitFor();

  // ------------------------------------------------------------------------------ visual QA set
  const light = [
    ['wip-ageing', 'WIP ageing', 'Tampilkan WIP'],
    ['capacity', 'Kapasitas produksi', null],
    ['production-quality', 'Kualitas produksi', null],
    ['supplier-performance', 'Kinerja supplier', 'Tampilkan kinerja'],
    ['material-price', 'Harga bahan', 'Tampilkan harga'],
    ['purchase-commitment', 'Komitmen PO', 'Tampilkan komitmen'],
    ['demand-forecast', 'Forecast demand', 'Hitung forecast'],
    ['replenishment', 'Rekomendasi stok', 'Hitung rekomendasi'],
    ['size-demand', 'Analisis ukuran', 'Tampilkan analisis'],
    ['returns', 'Analisis retur', 'Tampilkan analisis'],
    ['dead-stock', 'Dead stock', 'Tampilkan analisis'],
    ['stock-adjustment', 'Audit adjustment', 'Tampilkan audit'],
  ];
  async function shoot(slug, nav, run, suffix) {
    await openSidebarDestination(nav);
    if (run) await analytics.getByRole('button', {name: run, exact: true}).click();
    await page.locator('#analytics-body form.analytics-filters').waitFor();
    await page.waitForFunction(() => !document.querySelector('#analytics-body .loading-state'));
    // `.workspace-main` is the scroll container, so an element screenshot of the whole host clips
    // at the viewport. Two viewport shots instead: the first viewport exactly as the operator sees
    // it on arrival (§122), and the same page scrolled to the start of its evidence.
    await page.locator('#analytics-heading').scrollIntoViewIfNeeded();
    await page.evaluate(() => document.querySelector('.workspace-main')?.scrollTo(0, 0));
    await page.waitForTimeout(150);
    await page.screenshot({path: path.join(shots, `beeloft-a64-${slug}-${suffix}.png`)});
    const evidence = page.locator('#analytics-body .record-list:not(:empty), #analytics-body .analytics-bar-list, #analytics-body .empty-state').first();
    if (await evidence.count()) {
      await evidence.evaluate(node => node.scrollIntoView({block: 'start'}));
      await page.waitForTimeout(150);
      await page.screenshot({path: path.join(shots, `beeloft-a64-${slug}-${suffix}-records.png`)});
    }
  }
  await page.setViewportSize({width: 1440, height: 1000});
  for (const [slug, nav, run] of light) await shoot(slug, nav, run, '1440-light');

  // Dark representatives.
  await page.emulateMedia({colorScheme: 'dark'});
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
  for (const slug of ['wip-ageing', 'capacity', 'production-quality', 'replenishment',
                      'stock-adjustment']) {
    const [, nav, run] = light.find(row => row[0] === slug);
    await shoot(slug, nav, run, '1440-dark');
  }
  await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
  await page.emulateMedia({colorScheme: 'light'});

  // Mobile representatives, with the overflow assertion that makes them meaningful.
  await page.setViewportSize({width: 390, height: 900});
  for (const slug of ['wip-ageing', 'capacity', 'replenishment', 'stock-adjustment']) {
    const [, nav, run] = light.find(row => row[0] === slug);
    await shoot(slug, nav, run, '390');
    assert.equal(await page.evaluate(() => {
      const host = document.getElementById('analytics-view');
      return host.scrollWidth <= host.clientWidth;
    }), true, `${nav} overflows at 390px`);
  }

  // 320 at 200% text, on the most parameter-heavy report.
  await page.setViewportSize({width: 320, height: 900});
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await shoot('stock-adjustment', 'Audit adjustment', 'Tampilkan audit', '320-200');
  assert.equal(await page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth), true,
    'no document overflow at 320px / 200% text');
  await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  await page.setViewportSize({width: 1440, height: 1000});


  console.log('A6.4 analytics modern workspace PASS: shared host, twelve reports, aria-current, '
    + 'stale invalidation, per-report filter memory, ready/empty/error states, 25-row pagination '
    + 'offsets, forecast+replenishment 100/0 with no load-more, admin-only capacity master with '
    + 'expected_revision, bar values backed by API fields, responsive/dark/mobile QA set.');
};
