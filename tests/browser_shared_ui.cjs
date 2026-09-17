// Regression cover for the shared UI layer introduced by the section-unification work.
//
// The point of these checks is that a section other than the Command Center still renders
// the Command Center's surfaces: one radius ladder, one filter toolbar, one list-row card,
// one dialog chrome, and loading / empty / error states that cannot be mistaken for each
// other. Assertions therefore look at rendered geometry and computed style rather than at
// class names, except where a class is the only stable handle for a shared component.
const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, openSidebarDestination, admin, viewer, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const px = value => Math.round(parseFloat(value));

  async function closeDialog() {
    if (await page.locator('dialog[open]').count()) {
      await page.keyboard.press('Escape');
      await page.locator('dialog').waitFor({state: 'hidden'}).catch(() => {});
    }
  }
  const noPageOverflow = () => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth);

  // Earlier modules add orders, so the demo order is not necessarily on the first page.
  // Reach it the way a user would: search for it, then open it.
  async function openDemoOrder() {
    await closeDialog();
    await openSidebarDestination('Produksi');
    await page.getByRole('heading', {name: 'Yang sedang dikerjakan.'}).waitFor();
    await page.locator('#search').fill('DEMO-PROD-001');
    await page.getByRole('button', {name: 'Cari order', exact: true}).click();
    const row = page.getByRole('button', {name: /DEMO-PROD-001/}).first();
    await row.waitFor();
    await row.click();
    await page.locator('#detail-content h1').waitFor();
  }

  // Pin the desktop viewport and the acting account so the assertions do not inherit
  // whatever the previously executed module left behind. Several checks below cover
  // admin-only sections, so this module states the role it needs.
  await page.setViewportSize({width: 1440, height: 900});
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});
  await closeDialog();
  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  // login() resets the viewport to 1440x1000 unless told not to; keep 1440x900 so the dialog-fit assertion uses the requested height.
  await login(admin, {resetViewport: false});
  await closeDialog();
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Yang sedang dikerjakan.'}).waitFor();
  await page.locator('#summary dd').first().waitFor();

  // ---- the radius ladder from DESIGN.md must survive the shared layer ----------------
  const ladder = await page.evaluate(() => {
    const radius = node => node ? parseFloat(getComputedStyle(node).borderRadius) : null;
    return {
      card: radius(document.querySelector('#summary>div')),
      input: radius(document.querySelector('#search')),
      nav: radius(document.querySelector('#board-home')),
      chip: radius(document.querySelector('#order-list .status-label')),
      button: parseFloat(getComputedStyle(document.querySelector('#refresh')).borderRadius),
      buttonHeight: document.querySelector('#refresh').getBoundingClientRect().height,
    };
  });
  assert.equal(ladder.card, 20, 'primary surfaces stay at 20px');
  assert.equal(ladder.input, 12, 'inputs stay at 12px');
  assert.equal(ladder.nav, 10, 'navigation rows stay at 10px');
  assert.equal(ladder.chip, 8, 'chips and badges stay at 8px');
  assert.ok(ladder.button >= ladder.buttonHeight / 2, 'buttons keep the pill treatment');

  // ---- page heading, summary, filter toolbar, list, pagination are all present -------
  const boardShell = await page.evaluate(() => {
    const surface = node => {
      const style = getComputedStyle(node);
      return {radius: parseFloat(style.borderRadius), border: parseFloat(style.borderTopWidth)};
    };
    return {
      eyebrow: document.querySelector('#board-view .eyebrow').textContent.trim(),
      headingActions: document.querySelectorAll('#board-view .page-heading .actions button').length,
      kpis: document.querySelectorAll('#summary>div').length,
      filter: surface(document.querySelector('#search-form')),
      tableHead: Boolean(document.querySelector('#order-list .table-head')),
      rows: document.querySelectorAll('#order-list .order-row').length,
      pagination: Boolean(document.querySelector('#board-view .pagination')),
    };
  });
  assert.ok(boardShell.eyebrow.length > 0, 'page heading keeps its eyebrow');
  assert.ok(boardShell.headingActions >= 1);
  assert.equal(boardShell.kpis, 4);
  assert.equal(boardShell.filter.radius, 20, 'the board filter toolbar is a 20px surface');
  assert.ok(boardShell.filter.border > 0, 'the filter toolbar is a bordered surface');
  assert.equal(boardShell.tableHead, true);
  assert.ok(boardShell.rows > 0);
  assert.equal(boardShell.pagination, true);

  // ---- status chips must shrink-wrap, never stretch to fill their slot ---------------
  await openDemoOrder();
  const chip = await page.evaluate(() => {
    const node = document.querySelector('.detail-meta .status-label');
    const slot = node.parentElement;
    return {
      display: getComputedStyle(node).display,
      chipWidth: node.getBoundingClientRect().width,
      slotWidth: slot.getBoundingClientRect().width,
    };
  });
  assert.equal(chip.display, 'inline-flex', 'the order status chip stays an inline-flex chip');
  assert.ok(chip.chipWidth < chip.slotWidth - 20,
    `status chip must not fill its slot (${chip.chipWidth} vs ${chip.slotWidth})`);

  // ---- order detail metadata and history read as surfaces ---------------------------
  const detail = await page.evaluate(() => ({
    metaRadius: parseFloat(getComputedStyle(document.querySelector('.detail-meta')).borderRadius),
    metaCells: document.querySelectorAll('.detail-meta>div').length,
    stages: document.querySelectorAll('.stages .stage').length,
    skuCards: document.querySelectorAll('#detail-content .sku-block').length,
  }));
  assert.ok(detail.metaRadius >= 14, 'order metadata sits on a rounded surface');
  assert.equal(detail.metaCells, 4);
  assert.ok(detail.stages >= 6);
  assert.ok(detail.skuCards > 0);

  // ---- dialog chrome: rounded surface, ruled heading, fits inside the viewport -------
  await page.getByRole('button', {name: 'Kebutuhan bahan', exact: true}).click();
  await page.locator('dialog[open]').waitFor();
  await page.getByRole('heading', {name: 'Kebutuhan bahan order', exact: true}).waitFor();
  // The heading is painted with the loading placeholder, so wait for the metric list itself
  // rather than racing the fetch.
  await page.locator('#dialog-content .requirement-values').first().waitFor();
  const dialogShell = await page.evaluate(() => {
    const dialog = document.querySelector('dialog[open]');
    const heading = dialog.querySelector('.dialog-heading');
    const box = dialog.getBoundingClientRect();
    return {
      radius: parseFloat(getComputedStyle(dialog).borderRadius),
      headingRule: parseFloat(getComputedStyle(heading).borderBottomWidth),
      withinViewport: box.width <= window.innerWidth && box.height <= window.innerHeight + 1,
      noInnerOverflow: dialog.scrollWidth <= dialog.clientWidth,
      metricRows: dialog.querySelectorAll('.requirement-values>div').length,
    };
  });
  assert.equal(dialogShell.radius, 20, 'dialogs use the primary surface radius');
  assert.ok(dialogShell.headingRule > 0, 'the dialog heading is separated by a rule');
  assert.equal(dialogShell.withinViewport, true, 'the dialog stays inside the viewport');
  assert.equal(dialogShell.noInnerOverflow, true, 'the dialog does not scroll sideways');
  assert.ok(dialogShell.metricRows > 0, 'metric lists render as label/value rows');
  await closeDialog();

  // ---- a dialog filter toolbar is the same surface as the board's --------------------
  await openSidebarDestination('WIP ageing');
  await page.locator('dialog[open]').waitFor();
  await page.locator('#wip-ageing-form').waitFor();
  const dialogFilter = await page.evaluate(() => {
    const style = getComputedStyle(document.querySelector('#wip-ageing-form'));
    return {radius: parseFloat(style.borderRadius), border: parseFloat(style.borderTopWidth)};
  });
  assert.equal(dialogFilter.radius, 20, 'analytics filters use the shared toolbar surface');
  assert.ok(dialogFilter.border > 0);
  await closeDialog();

  // ---- loading, empty and error must be three distinguishable states ----------------
  // Loading: hold the response open and assert the surface announces progress.
  let release = null, held = false;
  const gate = new Promise(resolve => {release = resolve;});
  // Hold only the first approvals request; later ones (filter changes) pass straight through.
  await page.route('**/api/approvals?**', async route => {
    if (!held) {
      held = true;
      await gate;
    }
    await route.continue().catch(() => {});
  });
  await openSidebarDestination('Inbox approval');
  await page.locator('dialog[open]').waitFor();
  await page.locator('#approval-list .state').waitFor();
  assert.match(await page.locator('#approval-list .state').textContent(), /Memuat/,
    'a pending list announces that it is loading');
  release();
  // Once content arrives the loading placeholder must be gone, not left above the rows.
  await page.waitForFunction(() => {
    const host = document.getElementById('approval-list');
    if (!host) return false;
    const stale = [...host.querySelectorAll('.state')].some(n => /Memuat/.test(n.textContent));
    return !stale && host.children.length > 0;
  });
  const afterLoad = await page.evaluate(() => {
    const host = document.getElementById('approval-list');
    return {
      stale: [...host.querySelectorAll('.state')].filter(n => /Memuat/.test(n.textContent)).length,
      rows: host.querySelectorAll('.material-event').length,
      emptyState: host.querySelector('.state') ? host.querySelector('.state').textContent.trim() : '',
    };
  });
  assert.equal(afterLoad.stale, 0, 'the loading placeholder is cleared once the list resolves');
  assert.ok(afterLoad.rows > 0 || afterLoad.emptyState.length > 0,
    'a resolved list shows either rows or an explicit empty state');

  // Empty: a result set with nothing in it says so, and is not phrased as loading. The
  // response is forced rather than filtered, so the assertion does not depend on whatever
  // approvals earlier modules happen to have created.
  await page.unroute('**/api/approvals?**');
  await page.route('**/api/approvals?**', route =>
    route.fulfill({status: 200, contentType: 'application/json', body: '[]'}));
  await page.getByRole('button', {name: 'Muat ulang inbox', exact: true}).click();
  await page.waitForFunction(() => {
    const host = document.getElementById('approval-list');
    return host && !host.querySelector('.material-event')
      && host.querySelector('.state') && !/Memuat/.test(host.querySelector('.state').textContent);
  });
  const empty = await page.locator('#approval-list .state').textContent();
  assert.doesNotMatch(empty, /Memuat/, 'an empty result is not phrased as loading');
  assert.ok(empty.trim().length > 0, 'an empty result explains itself');
  await closeDialog();
  await page.unroute('**/api/approvals?**');

  // Error: a failed first load reports the failure and offers a retry, with no loading
  // text left behind next to it.
  await page.route('**/api/approvals?**', route =>
    route.fulfill({status: 503, contentType: 'application/json',
      body: JSON.stringify({detail: 'Inbox approval sedang diperbarui'})}));
  await openSidebarDestination('Inbox approval');
  await page.locator('dialog[open]').waitFor();
  await page.getByText('Inbox approval sedang diperbarui', {exact: true}).waitFor();
  const errorState = await page.evaluate(() => {
    const content = document.getElementById('dialog-content');
    return {
      loadingLeftOver: [...content.querySelectorAll('.state')]
        .filter(n => /Memuat|Menghitung/.test(n.textContent)).length,
      retry: [...content.querySelectorAll('button')].some(b => /Coba lagi/.test(b.textContent)),
      errorVisible: Boolean(content.querySelector('.error:not([hidden])')),
    };
  });
  assert.equal(errorState.loadingLeftOver, 0,
    'a failed load must not leave a loading placeholder beside the error');
  assert.equal(errorState.retry, true, 'a failed load offers a retry');
  assert.equal(errorState.errorVisible, true);
  await page.unroute('**/api/approvals?**');
  await closeDialog();

  // ---- Command Center is the reference and must not have moved -----------------------
  await page.setViewportSize({width: 1440, height: 900});
  await openSidebarDestination('Command center');
  await page.getByRole('heading', {name: 'Apa yang perlu diputuskan hari ini.'}).waitFor();
  await page.locator('#command-center-summary dd').first().waitFor();
  // The KPI row paints before the two bands are unhidden; measuring the panels any earlier
  // reports zero widths for both.
  await page.locator('#command-center-content:not([hidden])').waitFor();
  await page.locator('.attention-panel').waitFor({state: 'visible'});
  await page.locator('.snapshot-panel').waitFor({state: 'visible'});
  const dashboard = await page.evaluate(() => {
    const attention = document.querySelector('.attention-panel').getBoundingClientRect();
    const rail = document.querySelector('.snapshot-panel').getBoundingClientRect();
    return {
      kpis: document.querySelectorAll('#command-center-summary .kpi-card').length,
      kpiGlyphs: document.querySelectorAll('#command-center-summary dt svg').length,
      bands: document.querySelectorAll('.band-heading .band-step').length,
      hero: Boolean(document.querySelector('#command-center-hero .hero-body')),
      channelTable: Boolean(document.querySelector('#command-center-channels .data-table')),
      snapshots: document.querySelectorAll('[data-command-snapshot]').length,
      decisionRows: document.querySelectorAll('[data-command-attention]').length,
      attentionWider: attention.width > rail.width,
      kpiRadius: parseFloat(getComputedStyle(
        document.querySelector('#command-center-summary .kpi-card')).borderRadius),
    };
  });
  assert.equal(dashboard.kpis, 4, 'the dashboard keeps four KPI cards');
  assert.equal(dashboard.kpiGlyphs, 4, 'each dashboard KPI card keeps its glyph');
  assert.equal(dashboard.bands, 2, 'both numbered bands survive');
  assert.equal(dashboard.hero, true);
  assert.equal(dashboard.channelTable, true);
  assert.ok(dashboard.snapshots > 0);
  assert.ok(dashboard.decisionRows > 0);
  assert.equal(dashboard.attentionWider, true,
    'the decision queue stays the desktop focal point');
  assert.equal(dashboard.kpiRadius, 20);
  assert.equal(await noPageOverflow(), true, 'dashboard has no horizontal overflow at 1440');
  await page.screenshot({path: path.join(shots, 'shared-ui-command-center-light.png')});

  // ---- dark theme uses the token set, not an inversion -------------------------------
  await page.getByRole('button', {name: 'Mode gelap', exact: true}).click();
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  const dark = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    const canvas = style.getPropertyValue('--canvas').trim();
    const surface = getComputedStyle(document.querySelector('#command-center-summary .kpi-card'));
    const luminance = colour => {
      const [r, g, b] = colour.match(/\d+/g).map(Number);
      return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    };
    return {canvas, cardBg: surface.backgroundColor, cardLuminance: luminance(surface.backgroundColor)};
  });
  assert.ok(dark.canvas.length > 0, 'dark theme resolves its canvas token');
  assert.ok(dark.cardLuminance < 0.4, 'dark surfaces are dark, not inverted light');
  assert.equal(await noPageOverflow(), true, 'no horizontal overflow in dark mode');
  await page.screenshot({path: path.join(shots, 'shared-ui-command-center-dark.png')});

  // A section other than the dashboard must be equally dark-correct.
  await openSidebarDestination('People');
  await page.locator('dialog[open]').waitFor();
  await page.locator('#workforce-summary').waitFor();
  const peopleDark = await page.evaluate(() => {
    const cell = document.querySelector('#workforce-summary>div');
    const filter = document.querySelector('#workforce-filter');
    const luminance = colour => {
      const [r, g, b] = colour.match(/\d+/g).map(Number);
      return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    };
    return {
      statCells: document.querySelectorAll('#workforce-summary>div').length,
      statRadius: parseFloat(getComputedStyle(cell).borderRadius),
      statLuminance: luminance(getComputedStyle(cell).backgroundColor),
      filterRadius: parseFloat(getComputedStyle(filter).borderRadius),
    };
  });
  assert.ok(peopleDark.statCells >= 5, 'the roster keeps its stat cells');
  assert.ok(peopleDark.statRadius >= 12, 'roster stats are cards, not a ledger strip');
  assert.ok(peopleDark.statLuminance < 0.4, 'roster stat cards follow the dark tokens');
  assert.equal(peopleDark.filterRadius, 20, 'the roster filter is the shared toolbar');
  await page.screenshot({path: path.join(shots, 'shared-ui-people-dark.png')});
  await closeDialog();
  await page.getByRole('button', {name: 'Mode terang', exact: true}).click();
  await page.waitForFunction(() => (document.documentElement.dataset.theme || 'light') === 'light');

  // ---- mobile: toolbars reflow, nothing overflows, dialogs stay usable ---------------
  await page.setViewportSize({width: 390, height: 844});
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Yang sedang dikerjakan.'}).waitFor();
  assert.equal(await noPageOverflow(), true, 'no horizontal overflow at 390px');
  const mobileBoard = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('#summary>div')].map(n => n.getBoundingClientRect());
    const search = document.querySelector('#search').getBoundingClientRect();
    const form = document.querySelector('#search-form').getBoundingClientRect();
    return {
      stacked: cards.every(box => box.width > 200),
      // Every KPI card keeps a complete border once the grid collapses.
      borderedRight: [...document.querySelectorAll('#summary>div')]
        .every(n => parseFloat(getComputedStyle(n).borderRightWidth) > 0),
      searchFitsToolbar: search.width <= form.width,
    };
  });
  assert.equal(mobileBoard.stacked, true, 'KPI cards reflow to full width on mobile');
  assert.equal(mobileBoard.borderedRight, true,
    'KPI cards keep their right border when the grid collapses');
  assert.equal(mobileBoard.searchFitsToolbar, true, 'filter controls reflow inside the toolbar');
  await page.screenshot({path: path.join(shots, 'shared-ui-board-mobile.png')});

  await openSidebarDestination('Kapasitas produksi');
  await page.locator('dialog[open]').waitFor();
  await page.locator('#capacity-plan-form').waitFor();
  const mobileDialog = await page.evaluate(() => {
    const dialog = document.querySelector('dialog[open]');
    return {
      fits: dialog.getBoundingClientRect().width <= window.innerWidth,
      noSideScroll: dialog.scrollWidth <= dialog.clientWidth,
      // The admin master section is grouped rather than sharing one grid with the plan filter.
      groupedForms: dialog.querySelectorAll('.filter-form').length,
    };
  });
  assert.equal(mobileDialog.fits, true, 'dialogs fit the mobile viewport');
  assert.equal(mobileDialog.noSideScroll, true, 'dialogs do not scroll sideways on mobile');
  assert.ok(mobileDialog.groupedForms >= 2,
    'the capacity master controls are grouped into their own toolbars');
  assert.equal(await noPageOverflow(), true);
  await page.screenshot({path: path.join(shots, 'shared-ui-capacity-mobile.png')});
  await closeDialog();
  await page.setViewportSize({width: 1440, height: 900});

  // ---- an integration snapshot nests its surfaces instead of flattening them ---------
  await openSidebarDestination('Integrasi');
  await page.locator('dialog[open]').waitFor();
  await page.locator('[data-integration-system]').first().waitFor();
  const nesting = await page.evaluate(() => {
    const outer = document.querySelector('[data-integration-system]');
    const inner = outer.querySelector('[data-integration-scope]');
    const radius = node => parseFloat(getComputedStyle(node).borderRadius);
    return {outer: radius(outer), inner: inner ? radius(inner) : null,
      chips: outer.querySelectorAll('.status-label').length};
  });
  assert.equal(nesting.outer, 20, 'an integration system is a primary surface');
  assert.ok(nesting.inner !== null && nesting.inner < nesting.outer,
    'a surface nested inside one steps its radius down');
  assert.ok(nesting.chips > 0, 'integration health is stated with a labelled chip');
  await closeDialog();

  // ---- viewer: the same surfaces, without the mutation controls ----------------------
  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  await login(viewer, {resetViewport: false});
  await openDemoOrder();
  const readOnly = await page.evaluate(() => {
    const labels = [...document.querySelectorAll('#detail-content button')]
      .map(b => b.textContent.trim());
    return {
      recordMovement: labels.some(l => l === 'Catat perpindahan'),
      editOrder: labels.some(l => l === 'Ubah tenggat / PIC'),
      correction: labels.some(l => l === 'Koreksi'),
      // The surfaces themselves are unchanged for a viewer.
      metaCells: document.querySelectorAll('.detail-meta>div').length,
      chipDisplay: getComputedStyle(document.querySelector('.detail-meta .status-label')).display,
    };
  });
  assert.equal(readOnly.recordMovement, false, 'a viewer cannot record movements');
  assert.equal(readOnly.editOrder, false, 'a viewer cannot edit the order');
  assert.equal(readOnly.correction, false, 'a viewer cannot post corrections');
  assert.equal(readOnly.metaCells, 4, 'a viewer sees the same metadata surface');
  assert.equal(readOnly.chipDisplay, 'inline-flex');
  await page.screenshot({path: path.join(shots, 'shared-ui-order-detail-viewer.png')});

  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  // Hand the suite back its default viewport and the admin account.
  await login(admin);
  console.log('Shared UI browser QA PASS: radius ladder, page heading, KPI cards, filter '
    + 'toolbars, list/pagination, dialog chrome, metric lists, distinguishable '
    + 'loading/empty/error, Command Center reference intact, dark tokens, 390px reflow, '
    + 'nested surfaces, viewer read-only.');
};
