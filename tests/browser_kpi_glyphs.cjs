// Board/activity retain blue glyphs; A5.2 gives operational KPIs four semantic tiles.
// All glyphs remain decorative and resolve from the local sprite.
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
  if (await page.locator('html').getAttribute('data-theme') === 'dark') await page.locator('#theme').click();
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

  // A5.2 wraps the same glyph scale in a padded material tile.
  await openSidebarDestination('Command center');
  await page.getByRole('heading', {name: 'Command center', exact:true}).waitFor();
  await page.locator('#command-center-summary dd').first().waitFor();
  const dashboard = await readCards('#command-center-summary');
  assert.equal(dashboard.length, 4);
  for (const card of dashboard) {
    assert.equal(card.hasGlyph, true);
    assert.equal(card.ariaHidden, 'true');
  }
  assert.deepEqual(dashboard.map(card=>card.glyphHref),['#i-cart','#i-inbox','#i-wallet','#i-alert-triangle']);
  assert.equal(new Set(dashboard.map(card=>card.glyphColour)).size,4,'operational KPIs have four semantic colours');
  assert.ok(dashboard.every(card=>card.resolvesInSprite && card.focusable==='false'));
  const tilePadding = await page.locator('#command-center-summary dt .icon').first()
    .evaluate(node => parseFloat(getComputedStyle(node).paddingLeft) + parseFloat(getComputedStyle(node).paddingRight));
  assert.equal(dashboard[0].glyphBox - tilePadding, 26,
    '50px dashboard tile contains a 26px drawing and 12px padding');

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
    + 'activity summaries, unchanged labels and values, four semantic dashboard tiles, '
    + 'no emoji/CDN/image assets, dark mode, 390px at 200% text zoom.');
};
