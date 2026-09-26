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
    await page.getByRole('heading', {name: 'Produksi', exact: true}).waitFor();
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
  if (await page.locator('html').getAttribute('data-theme') === 'dark') await page.locator('#theme').click();
  await closeDialog();
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Produksi', exact: true}).waitFor();
  await page.locator('#summary dd').first().waitFor();

  // ---- the radius ladder, now read against the A6 workspace scale on a migrated page ----
  // A6.1 moved Produksi onto the A6.0 content primitives, and A6.0's approved scale for inner
  // workspace content deliberately sits just INSIDE the shell's own (data surface 16, panel 12,
  // control 10) so a table reads as content within the window rather than as a second window.
  // The shell itself is untouched, which is why the navigation row is still asserted at 20.
  const ladder = await page.evaluate(() => {
    const radius = selector => {
      const node = document.querySelector(selector);
      return node ? parseFloat(getComputedStyle(node).borderRadius) : null;
    };
    return {
      dataSurface: radius('#order-list'),
      panel: radius('#summary>div'),
      input: radius('#search'),
      nav: radius('#board-home'),
      chip: radius('#order-list .status-chip'),
      button: radius('#refresh'),
      commandBar: radius('#search-form'),
    };
  });
  assert.equal(ladder.dataSurface, 16, 'the primary data surface uses the A6 surface radius');
  assert.equal(ladder.panel, 12, 'metric cards and utility panels use the A6 panel radius');
  assert.equal(ladder.input, 10, 'workspace controls use the A6 control radius');
  assert.equal(ladder.nav, 20, 'A5.2 navigation is untouched and keeps the rounded toolbar family');
  assert.ok(ladder.chip >= 100, 'status chips are pills, so the label length never changes the shape');
  assert.equal(ladder.button, ladder.input, 'buttons and inputs share one control radius');
  assert.equal(ladder.commandBar, ladder.input, 'the command bar is a control surface, not a card');

  // ---- page heading, metric strip, command bar, data surface, pagination are all present ----
  const boardShell = await page.evaluate(() => {
    const surface = node => {
      const style = getComputedStyle(node);
      return {radius: parseFloat(style.borderRadius), border: parseFloat(style.borderTopWidth)};
    };
    return {
      title: document.querySelector('#board-view .workspace-title').textContent.trim(),
      subtitle: document.querySelector('#board-view .workspace-subtitle').textContent.trim(),
      headingActions: document.querySelectorAll('#board-view .workspace-heading .workspace-actions button').length,
      kpis: document.querySelectorAll('#summary>div').length,
      metricCards: document.querySelectorAll('#summary .metric-card').length,
      commandBar: surface(document.querySelector('#search-form')),
      filters: document.querySelectorAll('#search-form .command-filter').length,
      tableHead: Boolean(document.querySelector('#order-list .data-header')),
      columns: document.querySelectorAll('#order-list .data-header th').length,
      rows: document.querySelectorAll('#order-list .order-row').length,
      rowsAreTableRows: [...document.querySelectorAll('#order-list .order-row')]
        .every(row => row.tagName === 'TR'),
      pagination: Boolean(document.querySelector('#board-view .pagination')),
    };
  });
  assert.equal(boardShell.title, 'Produksi', 'the page identity is the workspace name');
  assert.ok(boardShell.subtitle.length > 0, 'the page heading keeps a subtitle');
  assert.ok(boardShell.headingActions >= 1);
  assert.equal(boardShell.kpis, 4);
  assert.equal(boardShell.metricCards, 4, 'the four real board metrics are A6 metric cards');
  assert.ok(boardShell.commandBar.border > 0, 'the command bar is a bordered surface');
  assert.equal(boardShell.filters, 3, 'status, PIC and stage are compact command-bar filters');
  assert.equal(boardShell.tableHead, true);
  assert.equal(boardShell.columns, 6);
  assert.ok(boardShell.rows > 0);
  assert.equal(boardShell.rowsAreTableRows, true, 'the order list is a semantic table');
  assert.equal(boardShell.pagination, true);

  // ---- status chips must shrink-wrap, never stretch to fill their slot ---------------
  await openDemoOrder();
  const chip = await page.evaluate(() => {
    const node = document.querySelector('#detail-content .detail-grid .status-chip');
    const slot = node.closest('.detail-field');
    return {
      display: getComputedStyle(node).display,
      chipWidth: node.getBoundingClientRect().width,
      slotWidth: slot.getBoundingClientRect().width,
    };
  });
  assert.equal(chip.display, 'inline-flex', 'the order status chip stays an inline-flex chip');
  assert.ok(chip.chipWidth < chip.slotWidth - 20,
    `status chip must not fill its slot (${chip.chipWidth} vs ${chip.slotWidth})`);

  // ---- order detail metadata, stage balances and SKU records read as A6 surfaces -----
  const detail = await page.evaluate(() => ({
    metaCells: document.querySelectorAll('#detail-content>.detail-grid>.detail-field').length,
    stages: document.querySelectorAll('#detail-content .detail-grid-compact .detail-field').length,
    skuCards: document.querySelectorAll('#detail-content .utility-panel').length,
    actionGroups: document.querySelectorAll('#detail-content .panel-grid>.utility-panel').length,
    panelRadius: parseFloat(getComputedStyle(document.querySelector('#detail-content .utility-panel')).borderRadius),
    timeline: document.querySelectorAll('#history-list.timeline .timeline-item').length,
  }));
  assert.equal(detail.metaCells, 4, 'the four order facts stay four fields');
  // Six flow positions plus rework and reject, then eight more for every SKU line.
  assert.ok(detail.stages >= 8, `stage balances are still enumerated (${detail.stages})`);
  assert.ok(detail.skuCards > 0);
  assert.equal(detail.actionGroups, 3, 'the flat action list is three workflow groups');
  assert.equal(detail.panelRadius, 12, 'detail panels use the A6 panel radius');
  assert.ok(detail.timeline > 0, 'movement history is an A6 timeline');

  // ---- dialog chrome: rounded surface, ruled heading, fits inside the viewport -------
  await page.getByRole('button', {name: 'Kebutuhan bahan', exact: true}).click();
  await page.locator('dialog[open]').waitFor();
  await page.getByRole('heading', {name: 'Kebutuhan bahan order', exact: true}).waitFor();
  // The heading is painted with the loading placeholder, so wait for the metric list itself
  // rather than racing the fetch.
  await Promise.race([
    page.locator('#dialog-content .requirement-values').first().waitFor(),
    page.getByText(/Perhitungan belum lengkap/).waitFor(),
  ]);
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
      incomplete: /Perhitungan belum lengkap/.test(dialog.textContent),
    };
  });
  assert.equal(dialogShell.radius, 24, 'floating dialogs use the prominent radius above content cards');
  assert.ok(dialogShell.headingRule > 0, 'the dialog heading is separated by a rule');
  assert.equal(dialogShell.withinViewport, true, 'the dialog stays inside the viewport');
  assert.equal(dialogShell.noInnerOverflow, true, 'the dialog does not scroll sideways');
  assert.ok(dialogShell.metricRows > 0 || dialogShell.incomplete,
    'a complete report shows label/value rows; missing BOM shows the explicit incomplete-data state');
  await closeDialog();

  // ---- an analytics filter toolbar is the same surface as the board's ----------------
  await openSidebarDestination('WIP ageing');
  await page.locator('#analytics-view').waitFor();
  await page.locator('#wip-ageing-form').waitFor();
  // A6.4 made this literal rather than coincidental: an analytics report's filter surface is the
  // SAME `.command-bar` primitive the Produksi board is built from, so the two are compared to each
  // other instead of to a hard-coded radius. The report's <form> is now the two-tier wrapper that
  // holds the bar and the assumptions panel, and carries no surface of its own.
  const dialogFilter = await page.evaluate(() => {
    const read = node => {
      const style = getComputedStyle(node);
      return {radius: parseFloat(style.borderRadius), border: parseFloat(style.borderTopWidth)};
    };
    return {analytics: read(document.querySelector('#wip-ageing-form .command-bar')),
            board: read(document.querySelector('#search-form'))};
  });
  assert.deepEqual(dialogFilter.analytics, dialogFilter.board,
    'analytics filters use the shared toolbar surface');
  assert.ok(dialogFilter.analytics.radius > 0);
  assert.ok(dialogFilter.analytics.border > 0);

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
  await page.locator('#approvals-view:not([hidden])').waitFor();
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
  await page.locator('#approvals-view:not([hidden])').waitFor();
  await page.getByText('Inbox approval sedang diperbarui', {exact: true}).waitFor();
  const errorState = await page.evaluate(() => {
    const content = document.getElementById('approvals-body');
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

  // ---- A5 preserves the dashboard contracts while recomposing its sections ----------
  await page.setViewportSize({width: 1440, height: 900});
  await openSidebarDestination('Command center');
  await page.getByRole('heading', {name: 'Command center', exact:true}).waitFor();
  await page.locator('#command-center-summary dd').first().waitFor();
  // The KPI row paints before the two bands are unhidden; measuring the panels any earlier
  // reports zero widths for both.
  await page.locator('#command-center-content:not([hidden])').waitFor();
  await page.locator('.attention-panel').waitFor({state: 'visible'});
  await page.locator('.approval-panel').waitFor({state: 'visible'});
  const dashboard = await page.evaluate(() => {
    const attention = document.querySelector('.attention-panel').getBoundingClientRect();
    const rail = document.querySelector('.approval-panel').getBoundingClientRect();
    return {
      kpis: document.querySelectorAll('#command-center-summary .kpi-card').length,
      kpiGlyphs: document.querySelectorAll('#command-center-summary dt svg').length,
      sections: ['.command-overview','.command-middle','.operations-section','.business-section','.context-section']
        .every(selector => document.querySelector('#command-center-view '+selector)),
      hero: Boolean(document.querySelector('#command-center-hero .hero-panel .hero-ring')),
      channelReady: Boolean(document.querySelector('#command-center-channels .data-table'))
        || /Belum ada marketplace pada snapshot order Jubelio/.test(document.querySelector('#command-center-channels').textContent),
      snapshots: document.querySelectorAll('[data-command-snapshot]').length,
      decisionRows: document.querySelectorAll('[data-command-attention]').length,
      equalCards: Math.abs(attention.width-rail.width)<1 && Math.abs(attention.height-rail.height)<1 && Math.abs(attention.y-rail.y)<1,
      kpiRadius: parseFloat(getComputedStyle(
        document.querySelector('#command-center-summary .kpi-card')).borderRadius),
    };
  });
  assert.equal(dashboard.kpis, 4, 'the dashboard keeps four KPI cards');
  assert.equal(dashboard.kpiGlyphs, 4, 'each dashboard KPI card keeps its glyph');
  assert.equal(dashboard.sections, true, 'A5 keeps sales, decisions, marketplace and business context');
  assert.equal(dashboard.hero, true);
  assert.equal(dashboard.channelReady, true, 'marketplace data or its explicit missing-snapshot state is rendered');
  assert.ok(dashboard.snapshots > 0);
  assert.ok(dashboard.decisionRows > 0);
  assert.equal(dashboard.equalCards, true,
    'the lower context cards share one equal desktop row');
  assert.equal(dashboard.kpiRadius, 18);
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
  await page.getByRole('heading', {name: 'People', exact: true}).waitFor();
  await page.locator('#people-view:not([hidden])').waitFor();
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
  // A6.3: the roster filter is the A6 command bar, so its radius is the control radius (10px)
  // rather than the 20px card radius the legacy `.filters` toolbar carried.
  assert.equal(peopleDark.filterRadius, 10, 'the roster filter is the A6 command bar');
  await page.screenshot({path: path.join(shots, 'shared-ui-people-dark.png')});
  await closeDialog();
  await page.getByRole('button', {name: 'Mode terang', exact: true}).click();
  await page.waitForFunction(() => (document.documentElement.dataset.theme || 'light') === 'light');

  // ---- mobile: toolbars reflow, nothing overflows, dialogs stay usable ---------------
  await page.setViewportSize({width: 390, height: 844});
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Produksi', exact: true}).waitFor();
  assert.equal(await noPageOverflow(), true, 'no horizontal overflow at 390px');
  const mobileBoard = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('#summary>div')].map(n => n.getBoundingClientRect());
    const summary = document.querySelector('#summary').getBoundingClientRect();
    const search = document.querySelector('#search').getBoundingClientRect();
    const form = document.querySelector('#search-form').getBoundingClientRect();
    return {
      reflowed: cards.length === 4 && cards[0].top === cards[1].top
        && cards[2].top === cards[3].top && cards[2].top > cards[0].bottom
        && cards[0].right < cards[1].left && cards[2].right < cards[3].left
        && cards.every(box => box.left >= summary.left && box.right <= summary.right),
      textFits: [...document.querySelectorAll('#summary dt, #summary dd')]
        .every(n => n.scrollWidth <= n.clientWidth),
      // Every KPI card keeps a complete border once the grid collapses.
      borderedRight: [...document.querySelectorAll('#summary>div')]
        .every(n => parseFloat(getComputedStyle(n).borderRightWidth) > 0),
      searchFitsToolbar: search.width <= form.width,
    };
  });
  assert.equal(mobileBoard.reflowed, true, 'Production KPI cards reflow to two contained rows on mobile');
  assert.equal(mobileBoard.textFits, true, 'mobile KPI labels and values fit without clipping');
  assert.equal(mobileBoard.borderedRight, true,
    'KPI cards keep their right border when the grid collapses');
  assert.equal(mobileBoard.searchFitsToolbar, true, 'filter controls reflow inside the toolbar');
  await page.waitForFunction(() => !document.querySelector('#board-view').classList.contains('motion-enter'));
  await page.screenshot({path: path.join(shots, 'shared-ui-board-mobile.png')});

  await openSidebarDestination('Kapasitas produksi');
  await page.locator('#analytics-view').waitFor();
  await page.locator('#capacity-plan-form').waitFor();
  const mobileAnalytics = await page.evaluate(() => {
    const host = document.getElementById('analytics-view');
    return {
      fits: host.getBoundingClientRect().width <= window.innerWidth,
      noSideScroll: host.scrollWidth <= host.clientWidth,
      // The admin master section is still grouped rather than sharing one grid with the plan
      // filter. A6.4 renames the grouping: the two master tool groups are A6 utility panels and
      // the plan filter is its own two-tier form, so the separation is now structural.
      groupedForms: host.querySelectorAll('.utility-panel').length,
      planForms: host.querySelectorAll('form.analytics-filters').length,
      masterList: host.querySelectorAll('#capacity-center-master').length,
    };
  });
  assert.equal(mobileAnalytics.fits, true, 'the analytics page fits the mobile viewport');
  assert.equal(mobileAnalytics.noSideScroll, true, 'the analytics page does not scroll sideways on mobile');
  assert.ok(mobileAnalytics.groupedForms >= 2,
    'the capacity master controls are grouped into their own toolbars');
  assert.equal(mobileAnalytics.planForms, 1, 'the plan filter is one form, separate from the master');
  assert.equal(mobileAnalytics.masterList, 1, 'the work-centre master is its own record list');
  assert.equal(await noPageOverflow(), true);
  await page.screenshot({path: path.join(shots, 'shared-ui-capacity-mobile.png')});
  await page.setViewportSize({width: 1440, height: 900});

  // ---- an integration snapshot nests its surfaces instead of flattening them ---------
  // Milestone D: Integrasi adalah halaman, jadi permukaannya diukur di integrations-view.
  await openSidebarDestination('Integrasi');
  await page.locator('#integrations-view:not([hidden])').waitFor();
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
      metaCells: document.querySelectorAll('#detail-content>.detail-grid>.detail-field').length,
      chipDisplay: getComputedStyle(document.querySelector('#detail-content .detail-grid .status-chip')).display,
      // A6.1 regrouped the actions; a viewer still gets the same three groups, only emptier.
      actionGroups: document.querySelectorAll('#detail-content .panel-grid>.utility-panel').length,
    };
  });
  assert.equal(readOnly.recordMovement, false, 'a viewer cannot record movements');
  assert.equal(readOnly.editOrder, false, 'a viewer cannot edit the order');
  assert.equal(readOnly.correction, false, 'a viewer cannot post corrections');
  assert.equal(readOnly.metaCells, 4, 'a viewer sees the same metadata surface');
  assert.equal(readOnly.chipDisplay, 'inline-flex');
  assert.equal(readOnly.actionGroups, 3, 'a viewer sees the same workflow grouping');
  await page.screenshot({path: path.join(shots, 'shared-ui-order-detail-viewer.png')});

  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  // Hand the suite back its default viewport and the admin account.
  await login(admin);
  console.log('Shared UI browser QA PASS: radius ladder, page heading, KPI cards, filter '
    + 'toolbars, list/pagination, dialog chrome, metric lists, distinguishable '
    + 'loading/empty/error, Command Center reference intact, dark tokens, 390px reflow, '
    + 'nested surfaces, viewer read-only.');
};
