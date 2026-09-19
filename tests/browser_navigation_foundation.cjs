// Milestone A: workspace navigation foundation.
//
// Proves the activation contract for every destination integrated in this
// milestone: exactly one workspace section is visible after navigation,
// aria-current follows the destination, the mobile drawer closes and focus
// lands on the new page heading, repeated navigation does not duplicate content,
// a delayed response from a previous page cannot repaint the current one, no
// primary destination opens the global dialog, and 320px at 200% text stays
// inside the viewport.
//
// Milestone D extends the destination matrix to the three oversight pages
// (Tanya Beeloft, Integrasi, Audit trail) and adds a delayed-audit race: a
// response that lands after the user left the audit page must not render its
// rows or repaint the destination the user moved to.
const assert = require('node:assert/strict');

module.exports = async ({page, login, admin, openSidebarDestination}) => {
  await page.keyboard.press('Escape');
  await login(admin);
  await page.setViewportSize({width: 1440, height: 1000});

  const destinations = [
    {name: 'Command center', nav: 'command-center', section: 'command-center-view', heading: 'Apa yang perlu diputuskan hari ini.'},
    {name: 'Produksi', nav: 'board-home', section: 'board-view', heading: 'Yang sedang dikerjakan.'},
    {name: 'Bahan baku', nav: 'materials', section: 'materials-view', heading: 'Bahan masuk, pemakaian tercatat.'},
    {name: 'People', nav: 'workforce', section: 'people-view', heading: 'Kehadiran tim yang tercatat.', content: '#workforce-summary:not([hidden])'},
    {name: 'Master SKU', nav: 'products', section: 'products-view', heading: 'Satu kode untuk setiap kombinasi produk.', content: '#product-list .product-item'},
    {name: 'WIP ageing', nav: 'wip-ageing-insights', section: 'analytics-view', heading: 'WIP ageing & sinyal hambatan', content: '#wip-ageing-form'},
    // Milestone D: Tanya Beeloft, Integrasi, dan Audit trail adalah halaman workspace.
    // riwayat investigasi dimuat terpisah dari permintaan tulisan, jadi tunggu riwayatnya
    // tuntas sebelum mengukur lebar halaman.
    {name: 'Tanya Beeloft', nav: 'ai-brain', section: 'ai-view', heading: 'Analisis operasional dari ledger sendiri.',
      content: '#ai-form',
      ready: () => page.waitForFunction(() => {
        const message = document.getElementById('ai-history-message');
        return document.getElementById('ai-history-list').children.length > 0
          || (message && message.textContent && message.textContent !== 'Memuat riwayat investigasi…');
      })},
    {name: 'Integrasi', nav: 'integrations', section: 'integrations-view', heading: 'Status integrasi dan source of truth.',
      content: '[data-integration-system]'},
    {name: 'Audit trail', nav: 'audit-trail', section: 'audit-view', heading: 'Audit trail', content: '#audit-summary'},
    {name: 'Laporan aktivitas', nav: 'activity', section: 'activity-view', heading: 'Catatan produksi.'}
  ];
  const visibleSections = () => page.evaluate(() =>
    [...document.querySelectorAll('.workspace-main > section')]
      .filter(section => !section.hidden).map(section => section.id));
  const noOverflow = () => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const overflowReport = () => page.evaluate(() => {
    const root = document.documentElement;
    const selector = node => {
      let value = node.tagName.toLowerCase();
      if (node.id) value += `#${node.id}`;
      if (node.classList.length) value += `.${[...node.classList].join('.')}`;
      return value;
    };
    const clippedBy = node => {
      for (let ancestor = node.parentElement; ancestor && ancestor !== document.body;
           ancestor = ancestor.parentElement) {
        const overflow = getComputedStyle(ancestor).overflowX;
        if (overflow === 'auto' || overflow === 'hidden' || overflow === 'scroll')
          return selector(ancestor);
      }
      return null;
    };
    const nodes = [document.documentElement, document.body,
      ...document.body.querySelectorAll('*')].filter(node => node.getClientRects().length);
    const offenders = nodes.map(node => {
        const rect = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        return {
          selector: selector(node),
          left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width),
          clientWidth: node.clientWidth, scrollWidth: node.scrollWidth,
          minWidth: style.minWidth, whiteSpace: style.whiteSpace, overflowX: style.overflowX,
          clippedBy: clippedBy(node)
        };
      })
      .filter(item => item.right > root.clientWidth + 0.5 || item.left < -0.5 || item.scrollWidth > item.clientWidth + 1);
    return {
      viewportWidth: root.clientWidth,
      documentScrollWidth: root.scrollWidth,
      offenders: offenders.slice(0, 40)
    };
  });

  // One visible page, one aria-current, no global dialog — for every destination,
  // including the internal order-detail section that shares the board's nav item.
  for (const destination of destinations) {
    await page.getByRole('button', {name: destination.name, exact: true}).click();
    await page.getByRole('heading', {name: destination.heading, exact: true}).waitFor();
    assert.deepEqual(await visibleSections(), [destination.section], `${destination.name} is the only visible page`);
    assert.equal(await page.locator('#app-sidebar [aria-current]').count(), 1, 'exactly one sidebar item carries aria-current');
    assert.equal(await page.locator('#' + destination.nav).getAttribute('aria-current'), 'page', `aria-current on ${destination.name}`);
    assert.equal(await page.locator('#dialog').getAttribute('open'), null, `${destination.name} must not open the global dialog`);
  }
  // The order detail is an internal section reached from a board row, so it
  // shares the board's nav item. Re-enter the board before opening one.
  await page.getByRole('button', {name: 'Produksi', exact: true}).click();
  await page.getByRole('button', {name: /DEMO-PROD-001/}).first().click();
  await page.getByRole('heading', {name: 'Posisi barang sekarang'}).waitFor();
  assert.deepEqual(await visibleSections(), ['detail-view'], 'order detail is the only visible page');
  assert.equal(await page.locator('#board-home').getAttribute('aria-current'), 'page', 'order detail keeps the board aria-current');
  assert.equal(await page.locator('#dialog').getAttribute('open'), null, 'order detail must not open the global dialog');

  // Milestone C: every Analytics sidebar child shares one analytics-view host.
  // Each child must still be its own destination: one visible page, its own
  // aria-current, its own page heading, and never the global dialog as screen.
  const analyticsChildren = [
    {name: 'WIP ageing', nav: 'wip-ageing-insights', heading: 'WIP ageing & sinyal hambatan'},
    {name: 'Kapasitas produksi', nav: 'capacity-plan', heading: 'Kapasitas produksi'},
    {name: 'Kualitas produksi', nav: 'production-quality-insights', heading: 'Kualitas produksi'},
    {name: 'Kinerja supplier', nav: 'supplier-performance-insights', heading: 'Kinerja supplier'},
    {name: 'Harga bahan', nav: 'material-price-insights', heading: 'Pergerakan harga bahan'},
    {name: 'Komitmen PO', nav: 'purchase-commitment-insights', heading: 'Komitmen pembelian terbuka'},
    {name: 'Forecast demand', nav: 'demand-forecast', heading: 'Forecast demand per SKU'},
    {name: 'Rekomendasi stok', nav: 'replenishment', heading: 'Risiko stockout & rekomendasi'},
    {name: 'Analisis ukuran', nav: 'size-demand-insights', heading: 'Analisis demand per ukuran'},
    {name: 'Analisis retur', nav: 'return-insights', heading: 'Analisis retur per SKU'},
    {name: 'Dead stock', nav: 'dead-stock-insights', heading: 'Analisis dead stock'},
    {name: 'Audit adjustment', nav: 'stock-adjustment-insights', heading: 'Audit adjustment stok'}
  ];
  for (const child of analyticsChildren) {
    await page.getByRole('button', {name: child.name, exact: true}).click();
    await page.getByRole('heading', {name: child.heading, exact: true}).waitFor();
    assert.deepEqual(await visibleSections(), ['analytics-view'], `${child.name} reuses the analytics host as its only visible page`);
    assert.equal(await page.locator('#app-sidebar [aria-current]').count(), 1, 'exactly one sidebar item carries aria-current');
    assert.equal(await page.locator('#' + child.nav).getAttribute('aria-current'), 'page', `aria-current on ${child.name}`);
    assert.equal(await page.locator('#dialog').getAttribute('open'), null, `${child.name} must not open the global dialog`);
    assert.equal(await page.locator('#analytics-eyebrow').textContent(), `Analitik · ${child.name}`,
      `${child.name} updates the page eyebrow`);
  }
  // A delayed response from the report being left cannot repaint the report the
  // user moved to. WIP ageing's response is held until after the user switches
  // to the Quality report inside the same host.
  let releaseWip, signalWip, finishWip;
  const wipStarted = new Promise(resolve => signalWip = resolve);
  const wipReleased = new Promise(resolve => releaseWip = resolve);
  const wipFinished = new Promise(resolve => finishWip = resolve);
  let delayWip = true;
  await page.route('**/api/wip-ageing-insights?*', async route => {
    if (delayWip) {
      delayWip = false;
      const response = await route.fetch(); signalWip();
      await wipReleased; await route.fulfill({response}); finishWip();
    } else await route.continue();
  });
  await page.getByRole('button', {name: 'WIP ageing', exact: true}).click();
  await page.locator('#wip-ageing-form').waitFor();
  await page.getByRole('button', {name: 'Tampilkan WIP', exact: true}).click();
  await wipStarted;
  await page.getByRole('button', {name: 'Kualitas produksi', exact: true}).click();
  await page.getByRole('heading', {name: 'Kualitas produksi', exact: true}).waitFor();
  releaseWip(); await wipFinished;
  await page.waitForTimeout(150);
  assert.equal(await page.evaluate(() => document.getElementById('analytics-heading').textContent), 'Kualitas produksi',
    'late WIP response must not repaint the quality report heading');
  assert.equal(await page.locator('#wip-ageing-results').count(), 0,
    'late WIP response must not repaint the quality report body');
  assert.equal(await page.locator('[data-wip-ageing]').count(), 0,
    'late WIP response must not render WIP rows onto the quality report');
  await page.unroute('**/api/wip-ageing-insights?*');

  // Milestone D: respons audit yang lambat tidak boleh mengecat halaman yang sudah ditinggalkan
  // pengguna. Respons /api/audit-events ditahan sampai pengguna pindah ke Command center.
  let releaseAudit, signalAudit, finishAudit;
  const auditStarted = new Promise(resolve => signalAudit = resolve);
  const auditReleased = new Promise(resolve => releaseAudit = resolve);
  const auditFinished = new Promise(resolve => finishAudit = resolve);
  let delayAudit = true;
  await page.route('**/api/audit-events?*', async route => {
    if (delayAudit) {
      delayAudit = false;
      const response = await route.fetch(); signalAudit();
      await auditReleased; await route.fulfill({response}); finishAudit();
    } else await route.continue();
  });
  await page.getByRole('button', {name: 'Audit trail', exact: true}).click();
  await page.getByRole('heading', {name: 'Audit trail', exact: true}).waitFor();
  await auditStarted;
  await page.getByRole('button', {name: 'Command center', exact: true}).click();
  await page.getByRole('heading', {name: 'Apa yang perlu diputuskan hari ini.'}).waitFor();
  releaseAudit(); await auditFinished;
  await page.waitForTimeout(150);
  assert.deepEqual(await visibleSections(), ['command-center-view'],
    'late audit response must not repaint the command center');
  assert.notEqual(await page.locator('#audit-view').getAttribute('hidden'), null,
    'the audit page must stay hidden after the user left it');
  assert.equal(await page.locator('#audit-list .audit-event').count(), 0,
    'late audit response must not render rows onto the page the user left');
  await page.unroute('**/api/audit-events?*');

  // Bagian Milestone A berikutnya dimulai dari halaman detail order, jadi
  // kembali ke precondition itu sebelum memakai tombol kembali detail.
  await page.getByRole('button', {name: 'Produksi', exact: true}).click();
  await page.getByRole('button', {name: /DEMO-PROD-001/}).first().click();
  await page.getByRole('heading', {name: 'Posisi barang sekarang'}).waitFor();

  // Repeated navigation re-enters the same destination without duplicating
  // handlers or re-rendering content on top of itself.
  await page.getByRole('button', {name: 'Semua order', exact: false}).click();  await page.waitForFunction(() => !document.getElementById('order-list').hidden);
  const rows = await page.locator('.order-row').count();
  for (let repeat = 0; repeat < 3; repeat += 1)
    await page.getByRole('button', {name: 'Produksi', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('order-list').hidden);
  assert.equal(await page.locator('.order-row').count(), rows, 'repeated navigation must not duplicate board rows');
  assert.deepEqual(await visibleSections(), ['board-view']);
  assert.equal(await page.locator('#board-home').getAttribute('aria-current'), 'page');

  // A late response from the page being left cannot repaint the destination the
  // user has already moved to. The board response is held until after the user
  // navigates to the Command center.
  let releaseBoard, signalBoard, finishBoard;
  const boardStarted = new Promise(resolve => signalBoard = resolve);
  const boardReleased = new Promise(resolve => releaseBoard = resolve);
  const boardFinished = new Promise(resolve => finishBoard = resolve);
  let delayBoard = true;
  await page.route('**/api/production-board?*', async route => {
    if (delayBoard) {
      delayBoard = false;
      const response = await route.fetch(); signalBoard();
      await boardReleased; await route.fulfill({response}); finishBoard();
    } else await route.continue();
  });
  await page.getByRole('button', {name: 'Produksi', exact: true}).click();
  await boardStarted;
  const boardListLength = await page.evaluate(() => document.getElementById('order-list').innerHTML.length);
  await page.getByRole('button', {name: 'Command center', exact: true}).click();
  await page.getByRole('heading', {name: 'Apa yang perlu diputuskan hari ini.'}).waitFor();
  releaseBoard(); await boardFinished;
  await page.waitForTimeout(150);
  assert.deepEqual(await visibleSections(), ['command-center-view'], 'late board response must not repaint the command center');
  assert.equal(await page.evaluate(() => document.getElementById('order-list').innerHTML.length), boardListLength, 'late board response must not touch the hidden board');
  await page.unroute('**/api/production-board?*');

  // Mobile drawer closes on selection and focus moves to the new page heading.
  await page.setViewportSize({width: 390, height: 844});
  const menu = page.getByRole('button', {name: 'Menu', exact: true});
  assert.equal(await menu.isVisible(), true, 'mobile menu control must be reachable');
  await menu.click();
  assert.equal(await menu.getAttribute('aria-expanded'), 'true');
  assert.equal(await page.evaluate(() => document.body.classList.contains('nav-open')), true, 'drawer opens');
  await page.getByRole('button', {name: 'Command center', exact: true}).click();
  await page.getByRole('heading', {name: 'Apa yang perlu diputuskan hari ini.'}).waitFor();
  assert.equal(await page.evaluate(() => document.body.classList.contains('nav-open')), false, 'drawer closes after navigation');
  assert.equal(await menu.getAttribute('aria-expanded'), 'false');
  assert.equal(await page.evaluate(() => {
    const section = document.querySelector('.workspace-main > section:not([hidden])');
    return document.activeElement === section.querySelector('h1');
  }), true, 'focus lands on the new page heading');

  // 320px at 200% text stays clean on every foundation destination.
  await page.setViewportSize({width: 320, height: 900});
  await page.evaluate(() => document.documentElement.style.fontSize = '200%');
  for (const destination of destinations) {
    await openSidebarDestination(destination.name);
    await page.getByRole('heading', {name: destination.heading, exact: true}).waitFor();
    if (destination.content) await page.locator(destination.content).first().waitFor();
    if (destination.ready) await destination.ready();
    const fits = await noOverflow();
    assert.equal(fits, true, `no horizontal overflow on ${destination.name} at 320px / 200% text\n${JSON.stringify(await overflowReport(), null, 2)}`);
    assert.deepEqual(await visibleSections(), [destination.section]);
  }
  const responsiveMatrix = [
    [320, 100], [320, 200], [390, 200], [651, 200], [700, 200], [768, 200], [980, 200], [1440, 200]
  ];
  const setTheme = async expected => {
    if (await page.locator('html').getAttribute('data-theme') !== expected)
      await page.locator('#theme').click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), expected);
  };
  for (const colorScheme of ['light', 'dark']) {
    await setTheme(colorScheme);
    for (const [width, textScale] of responsiveMatrix) {
      await page.setViewportSize({width, height: 900});
      await page.evaluate(scale => document.documentElement.style.fontSize = `${scale}%`, textScale);
      await openSidebarDestination('Command center');
      await page.getByRole('heading', {name: destinations[0].heading, exact: true}).waitFor();
      const fits = await noOverflow();
      assert.equal(fits, true, `no horizontal overflow on Command center at ${width}px / ${textScale}% text / ${colorScheme}\n${JSON.stringify(await overflowReport(), null, 2)}`);
    }
  }
  await setTheme('light');
  await page.evaluate(() => document.documentElement.style.fontSize = '');
  await page.setViewportSize({width: 1440, height: 1000});

  console.log('Workspace navigation foundation browser QA PASS: one visible page and one aria-current '
    +'per destination including the order detail under the board item, drawer close with heading focus '
    +'at 390px, repeated navigation without duplicated rows, a late board response cannot repaint the '
    +'command center, a late audit response cannot repaint the page the user left, and no horizontal '
    +'overflow at 320px with 200% text.');
};
