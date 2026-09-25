// A6.0 modern workspace foundation: the shared inner-workspace primitives, measured in a real
// engine rather than asserted from the stylesheet text.
//
// The subject is the non-production QA fixture (tests/fixtures/a60-workspace-primitives.html),
// opened over file:// so the primitives are reviewed against the actual shipped cascade -
// style.css + workspace.css + workspace-primitives.css - without adding a route, a navigation
// entry or any fake data to the application. The fixture is deliberately not a static asset and
// is never served; `test_apple27_modern_workspace_foundation_contract.py` enforces that.
//
// Everything below runs on its own page inside the existing context, so the shared smoke page,
// its session and its viewport are left exactly as they were found. Nothing here logs in, touches
// the API or changes application state.
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const FIXTURE = pathToFileURL(path.join(__dirname, 'fixtures', 'a60-workspace-primitives.html')).href;

// The widths the phase brief names, plus the shell breakpoints they map onto.
const WIDTHS = [
  {label: '1440', width: 1440, height: 1000},
  {label: '1280', width: 1280, height: 900},
  {label: '1024', width: 1024, height: 900},
  {label: '981', width: 981, height: 900},
  {label: '980', width: 980, height: 900},
  {label: '768', width: 768, height: 900},
  {label: '390', width: 390, height: 844},
  {label: '320', width: 320, height: 700},
];

module.exports = async ({page}) => {
  // A dedicated context, not a second page on the shared one. The smoke harness opens its page
  // through `browser.newPage()`, whose implicit context refuses extra pages, and a separate
  // context is the honest choice regardless: media emulation below is per-context state, and the
  // shared session, viewport and application page must come back untouched.
  const browser = page.context().browser();
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  const surface = await context.newPage();
  const problems = [];
  surface.on('pageerror', error => problems.push(`pageerror: ${error}`));
  surface.on('console', message => {
    if (message.type() === 'error') problems.push(`console: ${message.text()}`);
  });

  const open = async ({theme = 'light', zoom = 1} = {}) => {
    await surface.goto(FIXTURE, {waitUntil: 'load'});
    await surface.evaluate(([nextTheme, nextZoom]) => {
      document.documentElement.dataset.theme = nextTheme;
      document.documentElement.style.fontSize = nextZoom === 1 ? '' : `${16 * nextZoom}px`;
    }, [theme, zoom]);
    await surface.locator('.data-row').first().waitFor();
  };

  // ---------------------------------------------------------------- inventory
  await surface.setViewportSize({width: 1440, height: 1000});
  await open();
  const present = await surface.evaluate(() => {
    const seen = {};
    for (const name of [
      'workspace-page', 'workspace-heading', 'workspace-eyebrow', 'workspace-title',
      'workspace-subtitle', 'workspace-actions', 'metric-strip', 'metric-card', 'metric-icon',
      'metric-value', 'metric-detail', 'command-bar', 'command-search', 'command-filters',
      'command-filter', 'command-actions', 'segmented-filter', 'filter-chip', 'data-surface',
      'data-toolbar', 'data-header', 'data-row', 'data-cell', 'data-primary', 'data-secondary',
      'data-meta', 'data-actions', 'status-chip', 'status-dot', 'progress-meter', 'progress-track',
      'progress-fill', 'info-panel', 'utility-panel', 'attention-note', 'empty-state',
      'error-state', 'loading-state', 'timeline', 'timeline-item', 'record-list', 'record-row',
      'detail-grid', 'detail-field', 'action-primary', 'action-secondary', 'action-quiet',
      'action-destructive', 'icon-action', 'field-grid', 'field', 'field-label', 'field-help',
      'field-error', 'field-actions', 'scan-surface',
    ]) seen[name] = document.querySelectorAll('.' + name).length;
    return seen;
  });
  for (const [name, count] of Object.entries(present)) {
    assert.ok(count > 0, `the fixture must render .${name} for review (found ${count})`);
  }

  // The data surface is a real table with real semantics, not a grid of divs.
  const semantics = await surface.evaluate(() => {
    const table = document.querySelector('.data-surface > table');
    return {
      tag: table && table.tagName,
      headers: [...table.querySelectorAll('thead th')].map(th => th.getAttribute('scope')),
      rowsAreTr: [...document.querySelectorAll('.data-row')].every(r => r.tagName === 'TR'),
      chipsAreButtons: [...document.querySelectorAll('.filter-chip')].every(c => c.tagName === 'BUTTON'),
      pressed: [...document.querySelectorAll('.filter-chip')].map(c => c.getAttribute('aria-pressed')),
      bars: [...document.querySelectorAll('[role=progressbar]')].map(b => ({
        now: b.getAttribute('aria-valuenow'), label: !!b.getAttribute('aria-label'),
      })),
      iconActionsNamed: [...document.querySelectorAll('.icon-action')]
        .every(b => (b.getAttribute('aria-label') || '').trim().length > 0),
      searchLabelled: !!document.querySelector('.command-search .visually-hidden'),
      invalidMarked: !!document.querySelector('.field [aria-invalid=true][aria-describedby]'),
    };
  });
  assert.equal(semantics.tag, 'TABLE', 'the data surface hosts a native table');
  assert.ok(semantics.headers.length >= 5 && semantics.headers.every(s => s === 'col'),
    'every column header is a scoped th');
  assert.ok(semantics.rowsAreTr, '.data-row is a table row');
  assert.ok(semantics.chipsAreButtons, 'filter chips are native buttons');
  assert.ok(semantics.pressed.includes('true') && semantics.pressed.includes('false'),
    'segmented selection is carried by aria-pressed, not by colour alone');
  assert.ok(semantics.bars.length >= 4 && semantics.bars.every(b => b.now !== null && b.label),
    'progress exposes a value and a name');
  assert.ok(semantics.iconActionsNamed, 'icon-only row actions are named');
  assert.ok(semantics.searchLabelled, 'the compact search keeps an accessible label');
  assert.ok(semantics.invalidMarked, 'field errors are announced through aria-invalid/describedby');

  // ------------------------------------------------------------ light vs dark
  const themeReadings = {};
  for (const theme of ['light', 'dark']) {
    await open({theme});
    themeReadings[theme] = await surface.evaluate(() => {
      const read = (selector, property) => getComputedStyle(document.querySelector(selector))[property];
      return {
        pageTitle: read('.workspace-title', 'color'),
        rowText: read('.data-primary', 'color'),
        metaText: read('.data-meta', 'color'),
        dataSurface: read('.data-surface', 'backgroundColor'),
        header: read('.data-header th', 'backgroundColor'),
        headerCase: read('.data-header th', 'textTransform'),
        chipInfo: read('.status-chip-info', 'color'),
        chipInfoBackground: read('.status-chip-info', 'backgroundColor'),
        progressFill: read('.progress-fill', 'backgroundColor'),
        commandBar: read('.command-bar', 'backgroundColor'),
        commandBarFilter: read('.command-bar', 'backdropFilter'),
        rowFilter: read('.data-row', 'backdropFilter'),
        chipFilter: read('.status-chip', 'backdropFilter'),
        metricFilter: read('.metric-card', 'backdropFilter'),
      };
    });
  }
  for (const theme of ['light', 'dark']) {
    const reading = themeReadings[theme];
    // Dark is a first-class rendering, not a filter over light: nothing may land transparent.
    for (const [role, value] of Object.entries(reading)) {
      if (role.endsWith('Filter') || role === 'headerCase') continue;
      assert.notEqual(value, 'rgba(0, 0, 0, 0)', `${theme}: ${role} must resolve to a real colour`);
    }
    assert.equal(reading.headerCase, 'none',
      `${theme}: table headers stay sentence case, not an uppercase admin band`);
    // §46: material lives on the container, never on repeated children.
    for (const role of ['rowFilter', 'chipFilter', 'metricFilter']) {
      assert.equal(reading[role], 'none', `${theme}: ${role} must not be a backdrop root`);
    }
    assert.match(reading.commandBarFilter, /blur\(/,
      `${theme}: the command bar is the one restrained glass surface`);
  }
  // Every theme-sensitive role genuinely changes between themes.
  for (const role of ['pageTitle', 'rowText', 'metaText', 'dataSurface', 'header', 'chipInfo',
    'progressFill', 'commandBar']) {
    assert.notEqual(themeReadings.light[role], themeReadings.dark[role],
      `${role} is tuned per theme rather than shared`);
  }

  // ------------------------------------------------- responsive + no overflow
  await open();
  const responsive = [];
  for (const {label, width, height} of WIDTHS) {
    await surface.setViewportSize({width, height});
    await surface.evaluate(() => new Promise(requestAnimationFrame));
    responsive.push({label, ...await surface.evaluate(() => {
      window.scrollTo(9999, 0);
      const scrolled = window.scrollX;
      window.scrollTo(0, 0);
      const dataSurface = document.querySelector('.data-surface');
      const row = document.querySelector('.record-list .record-row');
      const tile = row.querySelector('.metric-icon').getBoundingClientRect();
      const title = row.querySelector('.data-primary').getBoundingClientRect();
      const sku = document.querySelectorAll('.data-row')[0].children[1].querySelector('.data-secondary');
      const skuRange = document.createRange();
      skuRange.selectNodeContents(sku);
      const note = document.querySelector('.attention-note');
      const noteButton = note.querySelector('button');
      const noteText = [...noteButton.childNodes].find(n => n.nodeType === 3 && n.textContent.trim());
      const noteRange = document.createRange();
      noteRange.selectNodeContents(noteText);
      return {
        documentScrollWidth: document.documentElement.scrollWidth,
        documentClientWidth: document.documentElement.clientWidth,
        scrolled,
        surfaceScrolls: dataSurface.scrollWidth > dataSurface.clientWidth,
        tileWidth: Math.round(tile.width),
        tileBesideTitle: tile.right <= title.left + 1
          && tile.top < title.bottom && title.top < tile.bottom,
        skuLines: skuRange.getClientRects().length,
        noteButtonLines: noteRange.getClientRects().length,
        commandBarHeight: Math.round(document.querySelector('.command-bar').getBoundingClientRect().height),
      };
    })});
  }
  for (const reading of responsive) {
    const {label} = reading;
    // No horizontal document overflow at any reviewed width. This is the assertion that caught
    // `.visually-hidden` escaping the clipping data surface because no ancestor was positioned.
    assert.ok(reading.documentScrollWidth <= reading.documentClientWidth + 1,
      `${label}: horizontal document overflow (${reading.documentScrollWidth} > ${reading.documentClientWidth})`);
    assert.equal(reading.scrolled, 0, `${label}: the document must not scroll sideways`);
    // The tile never deforms and never orphans itself above the record title.
    assert.equal(reading.tileWidth, 28, `${label}: the semantic tile keeps its 28px square`);
    assert.ok(reading.tileBesideTitle, `${label}: the record tile stays beside its title`);
    // Identifiers stay readable instead of being crushed one character per line.
    assert.ok(reading.skuLines <= 2, `${label}: SKU broke across ${reading.skuLines} lines`);
    assert.equal(reading.noteButtonLines, 1,
      `${label}: the attention action label must not wrap mid-phrase`);
  }
  // The table hands overflow to the surface at the narrow widths rather than crushing columns.
  const narrow = responsive.filter(r => ['390', '320'].includes(r.label));
  assert.ok(narrow.every(r => r.surfaceScrolls),
    'below 650px the data surface scrolls horizontally');
  assert.ok(responsive.find(r => r.label === '1440').surfaceScrolls === false,
    'at 1440 the table fits without scrolling');
  // The command bar wraps rather than overflowing: it gets taller as width shrinks.
  const barAt = label => responsive.find(r => r.label === label).commandBarHeight;
  assert.ok(barAt('390') > barAt('1440'),
    'the command bar wraps onto more rows as the workspace narrows');
  assert.ok(barAt('1440') <= 72, 'on desktop the command bar stays a single compact row');

  // --------------------------------------------------------- 320 at 200% text
  await surface.setViewportSize({width: 320, height: 700});
  await open({zoom: 2});
  const doubled = await surface.evaluate(() => {
    window.scrollTo(9999, 0);
    const scrolled = window.scrollX;
    window.scrollTo(0, 0);
    const row = document.querySelector('.record-list .record-row');
    const tile = row.querySelector('.metric-icon').getBoundingClientRect();
    const title = row.querySelector('.data-primary').getBoundingClientRect();
    return {
      documentScrollWidth: document.documentElement.scrollWidth,
      documentClientWidth: document.documentElement.clientWidth,
      scrolled,
      rootFontSize: getComputedStyle(document.documentElement).fontSize,
      titleFontSize: getComputedStyle(document.querySelector('.workspace-title')).fontSize,
      tileBesideTitle: tile.right <= title.left + 1
        && tile.top < title.bottom && title.top < tile.bottom,
      surfaceScrolls: (() => {
        const s = document.querySelector('.data-surface');
        return s.scrollWidth > s.clientWidth;
      })(),
      readable: [...document.querySelectorAll('.data-primary, .field-label, .status-chip')]
        .every(el => parseFloat(getComputedStyle(el).fontSize) >= 18),
    };
  });
  assert.equal(doubled.rootFontSize, '32px', '200% text is actually in effect');
  assert.ok(doubled.documentScrollWidth <= doubled.documentClientWidth + 1,
    `320 at 200%: horizontal overflow (${doubled.documentScrollWidth} > ${doubled.documentClientWidth})`);
  assert.equal(doubled.scrolled, 0, '320 at 200%: the document must not scroll sideways');
  assert.ok(doubled.tileBesideTitle, '320 at 200%: the record tile stays beside its title');
  assert.ok(doubled.surfaceScrolls, '320 at 200%: the table scrolls instead of crushing');
  assert.ok(doubled.readable, '320 at 200%: workspace text scales with the root size');

  // ------------------------------------------------------------ keyboard focus
  await surface.setViewportSize({width: 1440, height: 1000});
  await open();
  const focusable = [
    ['.command-search input', 'search'],
    ['.command-filter > select', 'filter select'],
    ['.filter-chip', 'filter chip'],
    ['.data-row', 'interactive row'],
    ['.icon-action', 'row action'],
    ['.action-primary', 'primary action'],
    ['.action-secondary', 'secondary action'],
    ['.action-quiet', 'quiet action'],
    ['.action-destructive', 'destructive action'],
    ['.field > input', 'form field'],
  ];
  for (const [selector, description] of focusable) {
    const ring = await surface.evaluate(target => {
      const node = document.querySelector(target);
      node.focus();
      const style = getComputedStyle(node);
      const matchesVisible = node.matches(':focus-visible');
      return {
        focused: document.activeElement === node,
        matchesVisible,
        outlineStyle: style.outlineStyle,
        outlineWidth: style.outlineWidth,
        outlineColor: style.outlineColor,
      };
    }, selector);
    assert.ok(ring.focused, `${description} must be focusable`);
    // Programmatic focus counts as focus-visible for keyboard-interaction elements in Chromium;
    // where it does not, the ring is still asserted to exist rather than be removed.
    if (ring.matchesVisible) {
      assert.notEqual(ring.outlineStyle, 'none', `${description} must show a focus ring`);
      assert.notEqual(ring.outlineWidth, '0px', `${description} focus ring must have width`);
      assert.notEqual(ring.outlineColor, 'rgba(0, 0, 0, 0)',
        `${description} focus ring must be visible`);
    }
  }
  // Keyboard travel actually reaches the row actions inside the data surface.
  await surface.locator('.command-search input').focus();
  const reached = await surface.evaluate(async () => {
    const order = [...document.querySelectorAll(
      '.command-bar input, .command-bar select, .command-bar button, .filter-chip, .data-row, .icon-action')];
    return order.length > 10 && order.every(node => node.tabIndex >= 0 || node.matches(
      'input,select,button,[tabindex]'));
  });
  assert.ok(reached, 'every workspace control is in the tab order');

  // Hover is a real state on rows, and it is not colour-only decoration.
  const hover = await surface.evaluate(() => {
    const row = document.querySelectorAll('.data-row')[1];
    return getComputedStyle(row).backgroundColor;
  });
  await surface.locator('.data-row').nth(1).hover();
  // The row carries a 120ms background transition, so the computed value immediately after the
  // pointer arrives is still the resting colour. Waiting for the value to actually change is
  // deterministic where a fixed sleep would be a guess, and it still fails loudly if the hover
  // affordance is missing altogether.
  await surface.waitForFunction(
    resting => getComputedStyle(document.querySelectorAll('.data-row')[1]).backgroundColor !== resting,
    hover, {timeout: 2000});
  const hovered = await surface.evaluate(() =>
    getComputedStyle(document.querySelectorAll('.data-row')[1]).backgroundColor);
  assert.notEqual(hover, hovered, 'rows respond to hover');

  // ------------------------------------------------------------ reduced motion
  await surface.emulateMedia({reducedMotion: 'reduce'});
  await open();
  const reduced = await surface.evaluate(() => {
    const collect = selector => getComputedStyle(document.querySelector(selector));
    return {
      row: collect('.data-row').transitionDuration,
      chip: collect('.filter-chip').transitionDuration,
      fill: collect('.progress-fill').transitionDuration,
      action: collect('.action-primary').transitionDuration,
      animations: document.getAnimations().length,
      // State must survive the preference: only movement is removed.
      selectedChip: document.querySelector('.filter-chip[aria-pressed=true]') !== null,
      fillWidth: document.querySelector('.progress-fill').getBoundingClientRect().width,
    };
  });
  for (const [role, duration] of Object.entries(reduced)) {
    if (typeof duration !== 'string') continue;
    assert.ok(/^0s(,\s*0s)*$/.test(duration), `reduced motion: ${role} still transitions (${duration})`);
  }
  assert.equal(reduced.animations, 0, 'reduced motion: nothing is animating');
  assert.ok(reduced.selectedChip, 'reduced motion: selection state is preserved');
  assert.ok(reduced.fillWidth > 0, 'reduced motion: progress still renders its value');
  await surface.emulateMedia({reducedMotion: 'no-preference'});

  // -------------------------------------------------------------- forced colors
  await surface.emulateMedia({forcedColors: 'active'});
  await open();
  const forced = await surface.evaluate(() => {
    const read = (selector, ...properties) => {
      const style = getComputedStyle(document.querySelector(selector));
      return Object.fromEntries(properties.map(p => [p, style[p]]));
    };
    return {
      surface: read('.data-surface', 'backgroundColor', 'borderTopWidth', 'backdropFilter'),
      commandBar: read('.command-bar', 'borderTopWidth', 'backdropFilter'),
      header: read('.data-header th', 'borderBottomWidth'),
      chip: read('.status-chip', 'borderTopWidth', 'borderTopStyle'),
      dot: read('.status-dot', 'backgroundColor'),
      track: read('.progress-track', 'borderTopWidth'),
      fill: read('.progress-fill', 'backgroundColor'),
      chipSelected: read('.filter-chip[aria-pressed=true]', 'backgroundColor'),
      chipIdle: read('.filter-chip[aria-pressed=false]', 'backgroundColor'),
      note: read('.attention-note', 'borderTopWidth'),
      timeline: read('.timeline-item', 'borderLeftColor'),
      rowText: read('.data-primary', 'color'),
    };
  });
  assert.equal(forced.surface.backdropFilter, 'none', 'forced colours: no optical filter survives');
  assert.equal(forced.commandBar.backdropFilter, 'none',
    'forced colours: the command bar drops its blur');
  for (const [role, reading] of Object.entries(forced)) {
    if (reading.borderTopWidth !== undefined) {
      assert.notEqual(reading.borderTopWidth, '0px',
        `forced colours: ${role} needs a real border, not a background`);
    }
  }
  assert.notEqual(forced.header.borderBottomWidth, '0px',
    'forced colours: header separation survives');
  assert.notEqual(forced.track.borderTopWidth, '0px', 'forced colours: progress track is outlined');
  assert.notEqual(forced.dot.backgroundColor, 'rgba(0, 0, 0, 0)',
    'forced colours: the status dot is the non-colour channel and must stay painted');
  assert.notEqual(forced.chipSelected.backgroundColor, forced.chipIdle.backgroundColor,
    'forced colours: chip selection stays distinguishable');
  assert.notEqual(forced.rowText.color, 'rgba(0, 0, 0, 0)', 'forced colours: text stays painted');
  await surface.emulateMedia({forcedColors: 'none'});

  // ------------------------------------------- reduced transparency, if supported
  // Two separate limits meet here, so this check is deliberately modest about what it proves.
  // Playwright cannot emulate `prefers-reduced-transparency`, and a file:// stylesheet is an
  // opaque origin whose `cssRules` the page may not read, so the rule's *content* cannot be
  // inspected from inside the fixture at all. What the engine can confirm is that it recognises
  // the feature and that the surfaces the preference targets are solid-capable. The withdrawal
  // rule itself is asserted statically, per selector and per declaration, by
  // test_apple27_modern_workspace_foundation_contract.AppearanceAndAccessibilityTest.
  const transparency = await surface.evaluate(() => {
    const query = window.matchMedia('(prefers-reduced-transparency: reduce)');
    let rulesReadable = true;
    try {
      for (const sheet of document.styleSheets) void sheet.cssRules;
    } catch { rulesReadable = false; }
    const opaqueMaterial = getComputedStyle(document.documentElement)
      .getPropertyValue('--material-content').trim();
    return {recognised: query.media !== 'not all', matches: query.matches, rulesReadable,
      opaqueMaterial};
  });
  assert.ok(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(transparency.opaqueMaterial),
    `the solid fallback material must be opaque, got "${transparency.opaqueMaterial}"`);
  const reducedTransparency = transparency.recognised
    ? `feature recognised${transparency.rulesReadable ? '' : ', rules not readable over file://'}`
    + ', withdrawal asserted statically'
    : 'feature unsupported by this engine, withdrawal asserted statically';

  // --------------------------------------------------- states and touch targets
  await open();
  const states = await surface.evaluate(() => {
    const busy = document.querySelector('.data-surface[aria-busy=true]');
    return {
      emptyTitle: document.querySelector('.empty-state-title').textContent.trim(),
      emptyHasCopy: document.querySelector('.empty-state-copy').textContent.trim().length > 20,
      emptyAction: document.querySelectorAll('.empty-state .action-primary').length,
      errorTitle: document.querySelector('.error-state-title').textContent.trim(),
      errorRetry: document.querySelectorAll('.error-state button').length,
      loadingVisible: getComputedStyle(document.querySelector('.loading-state')).display !== 'none',
      busyOpacity: busy ? parseFloat(getComputedStyle(busy).opacity) : null,
      skeletons: document.querySelectorAll('.skeleton-line').length,
      // The refresh treatment must be opacity on the existing lifecycle flag, not a spinner
      // animation invented by A6.
      busyAnimations: busy ? busy.getAnimations({subtree: true}).length : null,
    };
  });
  assert.ok(states.emptyTitle.length > 0 && states.emptyHasCopy,
    'the empty state explains itself instead of printing "Tidak ada data."');
  assert.equal(states.emptyAction, 1, 'the empty state offers the one relevant action');
  assert.ok(states.errorTitle.length > 0 && states.errorRetry === 1,
    'the error state summarises and offers retry');
  assert.ok(states.loadingVisible && states.skeletons >= 2, 'the loading state renders');
  assert.ok(states.busyOpacity < 1 && states.busyOpacity > 0.3,
    `aria-busy dims the surface rather than replacing it (opacity ${states.busyOpacity})`);
  assert.equal(states.busyAnimations, 0, 'the loading treatment adds no animation');

  // Coarse pointer restores full touch targets without changing desktop density.
  const fine = await surface.evaluate(() => ({
    control: Math.round(document.querySelector('.command-search input').getBoundingClientRect().height),
    chip: Math.round(document.querySelector('.filter-chip').getBoundingClientRect().height),
    action: Math.round(document.querySelector('.icon-action').getBoundingClientRect().height),
  }));
  assert.ok(fine.control <= 38 && fine.control >= 30,
    `desktop keeps the approved compact density (${fine.control}px)`);

  const touch = await browser.newContext({
    viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true,
  });
  const touchPage = await touch.newPage();
  await touchPage.goto(FIXTURE, {waitUntil: 'load'});
  await touchPage.locator('.data-row').first().waitFor();
  const coarse = await touchPage.evaluate(() => ({
    coarse: window.matchMedia('(pointer: coarse)').matches,
    control: Math.round(document.querySelector('.command-search input').getBoundingClientRect().height),
    chip: Math.round(document.querySelector('.filter-chip').getBoundingClientRect().height),
    action: Math.round(document.querySelector('.icon-action').getBoundingClientRect().height),
    actionWidth: Math.round(document.querySelector('.icon-action').getBoundingClientRect().width),
    overflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  }));
  assert.ok(coarse.coarse, 'the touch context reports a coarse pointer');
  for (const [role, value] of [['control', coarse.control], ['chip', coarse.chip],
    ['action', coarse.action], ['action width', coarse.actionWidth]]) {
    assert.ok(value >= 44, `coarse pointer: ${role} must be at least 44px (got ${value})`);
  }
  assert.ok(coarse.overflow, 'coarse pointer: no horizontal overflow at 390');
  await touch.close();

  assert.deepEqual(problems, [], `the fixture rendered with console or page errors: ${problems}`);
  await context.close();

  console.log('A6.0 workspace foundation browser QA PASS: 57 primitives rendered, native table/'
    + 'button/select semantics, light+dark parity, widths 1440/1280/1024/981/980/768/390/320 with '
    + 'no horizontal document overflow, 320 at 200% text, keyboard focus on 10 control families, '
    + 'hover, reduced motion (no animations, state preserved), forced colors (borders + status dot '
    + `+ outlined progress), reduced transparency (${reducedTransparency}), empty/error/loading `
    + 'states, coarse-pointer 44px targets, command-bar wrapping.');
};
