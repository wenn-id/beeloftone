// The board and activity summary cards carry the same blue glyph the Command Center KPI
// cards do. This proves the glyphs render from the local sprite, stay decorative, and did
// not change any metric value or accessible label.
const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, openSidebarDestination, admin, apiGet, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;

  async function closeDialog() {
    if (await page.locator('dialog[open]').count()) {
      await page.keyboard.press('Escape');
      await page.locator('dialog').waitFor({state: 'hidden'}).catch(() => {});
    }
  }
  const readCards = selector => page.evaluate(sel => {
    // Resolve --primary through a probe so it is comparable with computed colours, which
    // the engine always reports as rgb().
    const probe = document.createElement('span');
    probe.style.color = 'var(--primary)';
    document.body.appendChild(probe);
    const primary = getComputedStyle(probe).color;
    probe.remove();
    return [...document.querySelectorAll(sel + '>div')].map(cell => {
      const dt = cell.querySelector('dt');
      const dd = cell.querySelector('dd');
      const glyph = dt.querySelector('svg');
      const use = glyph ? glyph.querySelector('use') : null;
      return {
        // The label is the dt text with the decorative glyph contributing nothing.
        label: dt.textContent.trim(),
        value: dd.textContent.trim(),
        hasGlyph: Boolean(glyph),
        glyphHref: use ? use.getAttribute('href') : null,
        ariaHidden: glyph ? glyph.getAttribute('aria-hidden') : null,
        focusable: glyph ? glyph.getAttribute('focusable') : null,
        glyphColour: glyph ? getComputedStyle(glyph).color : null,
        glyphBox: glyph ? glyph.getBoundingClientRect().width : null,
        // The glyph sits at the end of the first line, opposite the label.
        glyphRight: glyph ? glyph.getBoundingClientRect().right : null,
        dtRight: dt.getBoundingClientRect().right,
        primary,
        resolvesInSprite: use ? Boolean(document.querySelector(use.getAttribute('href'))) : false,
      };
    });
  }, selector);

  // State the acting account: the board summary is visible to every role, but pinning it
  // keeps the comparison against /api/production-board deterministic.
  await page.setViewportSize({width: 1440, height: 900});
  await closeDialog();
  await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  // login() resets the viewport to 1440x1000 unless told not to; keep 1440x900 so the desktop assertions and screenshots use the requested height.
  await login(admin, {resetViewport: false});
  await closeDialog();
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Yang sedang dikerjakan.'}).waitFor();
  await page.locator('#summary dd').first().waitFor();

  const board = await readCards('#summary');
  assert.equal(board.length, 4, 'the board keeps exactly four summary cards');
  assert.deepEqual(board.map(card => card.label),
    ['Order aktif', 'Lewat target', 'Dalam proses', 'Perlu rework'],
    'summary labels are unchanged by the glyphs');

  // Values still come from the board summary endpoint, unchanged.
  const boardApi = await apiGet('/api/production-board?limit=25&offset=0');
  const summary = boardApi.summary;
  assert.equal(board[0].value.replace(/\s+/g, ' '),
    `${new Intl.NumberFormat('id-ID').format(summary.active)} order`);
  assert.equal(board[1].value.replace(/\s+/g, ' '),
    `${new Intl.NumberFormat('id-ID').format(summary.overdue)} order`);
  assert.equal(board[2].value.replace(/\s+/g, ' '),
    `${new Intl.NumberFormat('id-ID').format(summary.in_progress)} pcs`);
  assert.equal(board[3].value.replace(/\s+/g, ' '),
    `${new Intl.NumberFormat('id-ID').format(summary.rework)} pcs`);

  for (const card of board) {
    assert.equal(card.hasGlyph, true, `${card.label} carries a glyph`);
    assert.equal(card.ariaHidden, 'true', `${card.label} glyph is decorative`);
    assert.equal(card.focusable, 'false', `${card.label} glyph is not focusable`);
    assert.ok(card.glyphHref && card.glyphHref.startsWith('#i-'),
      `${card.label} glyph comes from the local sprite, not an external asset`);
    assert.equal(card.resolvesInSprite, true,
      `${card.label} glyph resolves to a symbol in the inline sprite`);
    assert.equal(card.glyphColour, card.primary,
      `${card.label} glyph uses the primary colour like the dashboard KPI glyphs`);
    assert.ok(card.glyphBox >= 14 && card.glyphBox <= 22,
      `${card.label} glyph renders at the shared icon scale (${card.glyphBox}px)`);
    assert.ok(card.dtRight - card.glyphRight < 4,
      `${card.label} glyph is aligned to the end of the label row`);
  }
  const boardGlyphs = board.map(card => card.glyphHref);
  assert.equal(new Set(boardGlyphs).size, boardGlyphs.length,
    'each board metric gets its own glyph');

  // The dashboard KPI cards these copy must use the same treatment.
  await openSidebarDestination('Command center');
  await page.getByRole('heading', {name: 'Apa yang perlu diputuskan hari ini.'}).waitFor();
  await page.locator('#command-center-summary dd').first().waitFor();
  const dashboard = await readCards('#command-center-summary');
  assert.equal(dashboard.length, 4);
  for (const card of dashboard) {
    assert.equal(card.hasGlyph, true);
    assert.equal(card.ariaHidden, 'true');
  }
  assert.equal(dashboard[0].glyphColour, board[0].glyphColour,
    'board and dashboard KPI glyphs share one colour treatment');
  assert.equal(dashboard[0].glyphBox, board[0].glyphBox,
    'board and dashboard KPI glyphs share one scale');

  // The activity report uses the same summary grid and must match.
  await openSidebarDestination('Laporan aktivitas');
  await page.getByRole('heading', {name: 'Catatan produksi.'}).waitFor();
  await page.getByRole('button', {name: 'Tampilkan aktivitas', exact: true}).click();
  await page.locator('#activity-summary dd').first().waitFor();
  const activity = await readCards('#activity-summary');
  assert.equal(activity.length, 4);
  assert.deepEqual(activity.map(card => card.label),
    ['Aktivitas tercatat', 'Gudang bersih', 'Kendala dicatat', 'Kendala selesai']);
  for (const card of activity) {
    assert.equal(card.hasGlyph, true, `${card.label} carries a glyph`);
    assert.equal(card.ariaHidden, 'true');
    assert.equal(card.glyphColour, card.primary);
  }

  // No emoji and no remote icon source anywhere in the summary grids.
  const sourcing = await page.evaluate(() => ({
    remoteIcons: document.querySelectorAll(
      '#summary img, #activity-summary img, #command-center-summary img').length,
    externalUse: [...document.querySelectorAll('#summary use, #activity-summary use')]
      .filter(u => !/^#i-/.test(u.getAttribute('href') || '')).length,
    emoji: /\p{Extended_Pictographic}/u.test(
      (document.getElementById('summary').textContent || '')
      + (document.getElementById('activity-summary').textContent || '')),
    stylesheets: [...document.styleSheets]
      .map(sheet => sheet.href).filter(href => href && !href.startsWith(location.origin)).length,
  }));
  assert.equal(sourcing.remoteIcons, 0, 'no image assets were introduced');
  assert.equal(sourcing.externalUse, 0, 'every glyph references the inline sprite');
  assert.equal(sourcing.emoji, false, 'no emoji in the summary grids');
  assert.equal(sourcing.stylesheets, 0, 'no external stylesheet or icon CDN');

  // Dark mode retakes the token colour, and the glyph survives 200% text zoom and mobile.
  await openSidebarDestination('Produksi');
  await page.locator('#summary dd').first().waitFor();
  await page.getByRole('button', {name: 'Mode gelap', exact: true}).click();
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  const darkCards = await readCards('#summary');
  for (const card of darkCards) {
    assert.equal(card.hasGlyph, true);
    assert.equal(card.glyphColour, card.primary, 'dark mode glyphs follow the dark primary token');
  }
  await page.screenshot({path: path.join(shots, 'kpi-glyphs-board-dark.png')});
  await page.getByRole('button', {name: 'Mode terang', exact: true}).click();
  await page.waitForFunction(() => (document.documentElement.dataset.theme || 'light') === 'light');

  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
  const zoomed = await readCards('#summary');
  for (const card of zoomed) assert.equal(card.hasGlyph, true, 'glyphs survive 200% text zoom');
  assert.equal(await page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth), true,
    'no horizontal overflow at 390px with 200% text zoom');
  await page.screenshot({path: path.join(shots, 'kpi-glyphs-board-mobile-200.png')});
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});
  await page.setViewportSize({width: 1440, height: 900});

  console.log('Board KPI glyph browser QA PASS: sprite-sourced decorative glyphs on board and '
    + 'activity summaries, unchanged labels and values, dashboard-matched colour and scale, '
    + 'no emoji/CDN/image assets, dark mode, 390px at 200% text zoom.');
};
