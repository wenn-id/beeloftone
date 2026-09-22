// M6 consistency and performance cleanup: every one of the 27 primary destinations measured at
// every responsive width for document overflow and leftover motion state, the refresh and
// replacement grammar propagated to the remaining list pages, and the reduced-motion path
// confirmed across the patterns M1-M5 introduced. Assertions measure settled state and lifecycle
// flags rather than animation timings, per the motion specification's test style.
const assert = require('node:assert/strict');

// The destination table is the contract under test: a new sidebar destination must be added here
// deliberately, and the section it activates is what the one-visible-section assertion compares.
const DESTINATIONS = [
  {nav: 'command-center', label: 'Command center', section: 'command-center-view'},
  {nav: 'board-home', label: 'Produksi', section: 'board-view'},
  {nav: 'materials', label: 'Bahan baku', section: 'materials-view'},
  {nav: 'workforce', label: 'People', section: 'people-view'},
  {nav: 'scan-bundle', label: 'Scan bundle', section: 'bundle-scan-view'},
  {nav: 'scan-finished-goods', label: 'Scan barang jadi', section: 'finished-goods-scan-view'},
  {nav: 'products', label: 'Master SKU', section: 'products-view'},
  {nav: 'wip-ageing-insights', label: 'WIP ageing', section: 'analytics-view'},
  {nav: 'capacity-plan', label: 'Kapasitas produksi', section: 'analytics-view'},
  {nav: 'production-quality-insights', label: 'Kualitas produksi', section: 'analytics-view'},
  {nav: 'supplier-performance-insights', label: 'Kinerja supplier', section: 'analytics-view'},
  {nav: 'material-price-insights', label: 'Harga bahan', section: 'analytics-view'},
  {nav: 'purchase-commitment-insights', label: 'Komitmen PO', section: 'analytics-view'},
  {nav: 'demand-forecast', label: 'Forecast demand', section: 'analytics-view'},
  {nav: 'replenishment', label: 'Rekomendasi stok', section: 'analytics-view'},
  {nav: 'size-demand-insights', label: 'Analisis ukuran', section: 'analytics-view'},
  {nav: 'return-insights', label: 'Analisis retur', section: 'analytics-view'},
  {nav: 'dead-stock-insights', label: 'Dead stock', section: 'analytics-view'},
  {nav: 'stock-adjustment-insights', label: 'Audit adjustment', section: 'analytics-view'},
  {nav: 'ai-brain', label: 'Tanya Beeloft', section: 'ai-view'},
  {nav: 'integrations', label: 'Integrasi', section: 'integrations-view'},
  {nav: 'activity', label: 'Laporan aktivitas', section: 'activity-view'},
  {nav: 'audit-trail', label: 'Audit trail', section: 'audit-view'},
  {nav: 'backup', label: 'Cadangan data', section: 'backup-view'},
  {nav: 'purchase-requests', label: 'Permintaan pembelian', section: 'purchase-requests-view'},
  {nav: 'marketing-budgets', label: 'Budget marketing', section: 'marketing-budgets-view'},
  {nav: 'approvals', label: 'Inbox approval', section: 'approvals-view'},
];
// 1440, 1024, 768, 390 and 320 are the specification's regression widths; 320 is measured again
// with the root at 200% text, which is the composition that breaks first.
const WIDTHS = [1440, 1024, 768, 390, 320];

module.exports = async ({page, login, admin, apiGet, apiPost}) => {
  // Destinations are addressed by their own id, not by accessible name: the sidebar CTA label
  // ("Inbox approval") is also rendered as an action button inside other pages, so a name lookup
  // can resolve twice depending on what was rendered before. The sweep always measures at desktop
  // width, where the sidebar is not a drawer.
  const openDestination = async nav => {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator(`#app-sidebar #${nav}`).click();
  };
  // Only the workspace is polled: the notice owns its own six-second semantic timer and hiding it
  // early to make this helper faster would be measuring the test rather than the product.
  const settle = (timeout = 15000) => page.waitForFunction(() => {
    const dialog = document.getElementById('dialog');
    if (dialog.classList.contains('is-closing') || dialog.classList.contains('motion-exit')) return false;
    return [...document.querySelectorAll('.motion-enter,.is-ready,.is-refreshing')]
      .every(node => node.id === 'notice');
  }, null, {timeout});
  const overflow = () => page.evaluate(async () => {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const root = document.documentElement;
    return root.scrollWidth - root.clientWidth;
  });
  const visibleSections = () => page.evaluate(() =>
    [...document.querySelectorAll('.workspace-main > section')].filter(node => !node.hidden).map(node => node.id));
  const activeDestinations = () => page.evaluate(() =>
    [...document.querySelectorAll('#app-sidebar [aria-current]')].map(node => node.id));
  // Observes the real lifecycle: a class change alone is also recorded when an engine coalesces
  // both updates into one style recalculation, in which case nothing ever transitions. One observer
  // and one pair of listeners exist at a time: reinstalling without releasing the previous ones
  // would leave them pushing into the next list's log, and an entry from a previous page could make
  // a "no fade here" assertion pass on someone else's transition.
  const watchFade = listId => page.evaluate(id => {
    window.fadeWatch?.observer.disconnect();
    for (const [node, type, listener] of window.fadeWatch?.listeners ?? [])
      node.removeEventListener(type, listener);
    window.fadeLog = [];
    const node = document.getElementById(id);
    const observer = new MutationObserver(() => window.fadeLog.push({classes: node.className}));
    observer.observe(node, {attributes: true, attributeFilter: ['class']});
    const listeners = [];
    for (const type of ['transitionrun', 'transitionend']) {
      const listener = event => window.fadeLog.push({type, name: event.propertyName});
      node.addEventListener(type, listener);
      listeners.push([node, type, listener]);
    }
    window.fadeWatch = {observer, listeners};
  }, listId);
  const clearFade = () => page.evaluate(() => {window.fadeLog = [];});
  const fadeState = () => page.evaluate(() => ({
    asked: window.fadeLog.some(entry => String(entry.classes || '').includes('motion-enter')),
    started: window.fadeLog.some(entry => entry.type === 'transitionrun' && entry.name === 'opacity'),
    finished: window.fadeLog.some(entry => entry.type === 'transitionend' && entry.name === 'opacity'),
    classes: window.fadeLog.at(-1)?.classes ?? null,
  }));
  // A replacement is observed through its own lifecycle, not through the passage of time: the
  // bounded wait gives the request time to land and the transition time to finish, and a missing
  // fade falls through to the assertion below instead of failing here with a timeout.
  const awaitFade = () => page.waitForFunction(
    () => window.fadeLog.some(entry => entry.type === 'transitionend' && entry.name === 'opacity'),
    null, {timeout: 4000}).catch(() => {});
  const motionStateOf = id => page.evaluate(target => {
    const node = document.getElementById(target);
    return {classes: node.className, opacity: getComputedStyle(node).opacity,
      busy: node.getAttribute('aria-busy'), hidden: node.hidden,
      transition: getComputedStyle(node).transitionDuration};
  }, id);
  // One held request at a time: the in-flight state is observed rather than guessed from timing.
  const hold = async pattern => {
    let release, settleHold, signal;
    const started = new Promise(resolve => signal = resolve);
    const held = new Promise(resolve => release = resolve);
    const settled = new Promise(resolve => settleHold = resolve);
    await page.route(pattern, async route => {
      const response = await route.fetch(); signal();
      await held; await route.fulfill({response}); settleHold();
    });
    return {started, release, settled};
  };

  await login(admin);
  if (await page.locator('#theme').textContent() === 'Mode terang') await page.locator('#theme').click();

  // ---- every destination, every responsive width --------------------------------------------
  // One navigation per destination, measured after each resize: the layout is what has to hold at
  // each width, so re-flowing the same page is the measurement rather than re-fetching it.
  for (const destination of DESTINATIONS) {
    await page.setViewportSize({width: 1440, height: 1000});
    await openDestination(destination.nav);
    await page.mouse.move(0, 0);
    await page.waitForFunction(id => !document.getElementById(id).hasAttribute('hidden'), destination.section);
    await settle();
    assert.deepEqual(await activeDestinations(), [destination.nav],
      `${destination.label} must be the single active destination`);
    assert.deepEqual(await visibleSections(), [destination.section],
      `${destination.label} must show exactly its own section`);
    // A1: the same selected destination and solid chrome must resolve in both palettes.
    for (const theme of ['light', 'dark']) {
      if (theme === 'dark') await page.locator('#theme').click();
      await page.waitForFunction(() => !document.documentElement.classList.contains('is-theming'));
      await page.waitForFunction(nav => {
        const selected = document.getElementById(nav);
        getComputedStyle(selected).color;
        return selected.getAnimations({subtree: true}).every(animation => animation.playState === 'finished');
      }, destination.nav);
      // A4 made the chrome and the selection lens translucent where the engine supports it, so a
      // computed `background-color` is no longer the colour a label actually sits on. Reading the
      // declaration and ignoring its alpha would have quietly inflated every ratio below, so the
      // ground is composited here instead: the lens tint over the material behind it, and — in the
      // approval context, where that material is a gradient that cannot be sampled from a computed
      // style — over *every* stop of that gradient, keeping whichever stop gives the worst result.
      // That is deliberately more pessimistic than the real rendering. The authoritative
      // pixel-level measurement lives in browser_functional_glass.cjs; this stays a cheap
      // cross-check that covers all 27 destinations in both palettes.
      const material = await page.evaluate(nav => {
        const root = getComputedStyle(document.documentElement);
        const color = token => {
          const probe = document.createElement('span');
          probe.style.color = root.getPropertyValue(token);
          document.body.append(probe);
          const value = getComputedStyle(probe).color; probe.remove(); return value;
        };
        const filterOf = style => style.backdropFilter && style.backdropFilter !== 'none'
          ? style.backdropFilter : (style.webkitBackdropFilter || 'none');
        const selected = getComputedStyle(document.getElementById(nav));
        const lens = document.getElementById('nav-selection-lens');
        const lensStyle = getComputedStyle(lens);
        const chromeStyle = getComputedStyle(document.querySelector('.masthead'));
        const railStyle = getComputedStyle(document.getElementById('app-sidebar'));
        const inCta = lens.parentElement.classList.contains('sidebar-cta');
        return {
          ready: document.getElementById('app-sidebar').classList.contains('nav-lens-ready') && !lens.hidden,
          inCta,
          selected: selected.color, expectedLabel: color('--color-accent'),
          selectedBackground: selected.backgroundColor,
          lensGround: lensStyle.backgroundColor,
          expectedGround: color(inCta ? '--lens-glass-cta-tint' : '--lens-glass-tint'),
          expectedSolidGround: color('--color-accent-soft'),
          chrome: chromeStyle.backgroundColor, chromeFilter: filterOf(chromeStyle),
          rail: railStyle.backgroundColor,
          expectedChrome: color('--material-functional-chrome-solid'),
          canvas: getComputedStyle(document.querySelector('.workspace-main')).backgroundColor,
          ctaStops: getComputedStyle(document.querySelector('.sidebar-cta')).backgroundImage
            .match(/rgba?\([^)]*\)/g) || [],
        };
      }, destination.nav);
      const parse = value => {
        const parts = value.match(/[\d.]+/g).map(Number);
        return {r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1};
      };
      const over = (top, bottom) => ({
        r: top.r * top.a + bottom.r * (1 - top.a),
        g: top.g * top.a + bottom.g * (1 - top.a),
        b: top.b * top.a + bottom.b * (1 - top.a), a: 1,
      });
      const luminance = ({r, g, b}) => [r, g, b].map(value => value / 255)
        .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
        .reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
      const ratio = (a, b) => {
        const [bright, dim] = [luminance(a), luminance(b)].sort((x, y) => y - x);
        return (bright + .05) / (dim + .05);
      };
      const canvas = parse(material.canvas);
      const glass = material.chromeFilter !== 'none';
      // Behind the navigation column is the page canvas; behind the approval CTA is its gradient.
      const backings = material.ready && material.inCta && material.ctaStops.length
        ? material.ctaStops.map(parse)
        : [over(parse(material.rail), canvas)];
      const grounds = material.ready
        ? backings.map(backing => over(parse(material.lensGround), backing))
        : [over(parse(material.selectedBackground), over(parse(material.rail), canvas))];
      const label = parse(material.selected);
      const contrast = Math.min(...grounds.map(ground => ratio(label, ground)));
      if (destination.nav !== 'approvals' || await page.locator('#app-sidebar.nav-lens-ready').count()) {
        assert.equal(material.selected, material.expectedLabel, `${destination.label}: ${theme} selected label`);
        // One shared selection surface, still driven by tokens rather than a per-destination colour:
        // the glass tint where the enhancement applies, the A1 solid fill where it does not.
        assert.equal(material.lensGround, glass ? material.expectedGround : material.expectedSolidGround,
          `${destination.label}: ${theme} selected ground`);
      }
      assert.ok(contrast >= 4.5,
        `${destination.label}: ${theme} selected text contrast ${contrast.toFixed(3)}`
        + ` on the composited selection surface (${JSON.stringify(grounds)})`);
      if (glass) {
        // The chrome is allowed to be translucent, but it must stay bounded and it must not dissolve
        // into the content canvas it sits against.
        const chrome = parse(material.chrome);
        assert.ok(chrome.a > .6 && chrome.a < 1,
          `${theme} chrome tint alpha ${chrome.a} is translucent but bounded`);
        assert.match(material.chromeFilter, /blur\(/, `${theme} chrome blurs its backdrop`);
        assert.notDeepEqual(over(chrome, canvas), canvas, `${theme} canvas and chrome stay distinct`);
      } else {
        assert.equal(material.chrome, material.expectedChrome, `${theme} chrome uses the solid material`);
        assert.notEqual(material.canvas, material.chrome, `${theme} canvas and chrome stay distinct`);
      }
      assert.ok(await overflow() <= 1, `${destination.label}: ${theme} desktop has no overflow`);
    }
    await page.locator('#theme').click();
    await page.waitForFunction(() => !document.documentElement.classList.contains('is-theming'));
    for (const width of WIDTHS) {
      await page.setViewportSize({width, height: 900});
      const spill = await overflow();
      assert.equal(spill <= 1, true,
        `${destination.label} overflows the document by ${spill}px at ${width}px`);
    }
    await page.setViewportSize({width: 320, height: 900});
    await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
    const zoomed = await overflow();
    assert.equal(zoomed <= 1, true,
      `${destination.label} overflows the document by ${zoomed}px at 320px and 200% text`);
    await page.evaluate(() => {document.documentElement.style.fontSize = '';});
    // The settled page carries no transient motion state anywhere, including the sidebar the
    // mobile drawer uses and the dialog the secondary tasks use.
    const leftovers = await page.evaluate(() => ({
      sections: [...document.querySelectorAll('.workspace-main > section')]
        .filter(node => node.className.includes('motion-') || node.className.includes('is-ready'))
        .map(node => node.id),
      lists: [...document.querySelectorAll('.list-host')]
        .filter(node => node.className.includes('motion-') || node.classList.contains('is-refreshing')
          || node.hasAttribute('aria-busy'))
        .map(node => node.id),
      sidebar: document.getElementById('app-sidebar').className,
    }));
    assert.deepEqual(leftovers.sections, [], `${destination.label} leaves no motion class on a section`);
    assert.deepEqual(leftovers.lists, [], `${destination.label} leaves no motion or busy state on a list`);
    assert.equal(leftovers.sidebar.split(' ').every(name => ['app-sidebar', 'nav-open', 'nav-lens-ready'].includes(name)), true,
      `${destination.label} leaves no motion class on the sidebar`);
  }
  await page.setViewportSize({width: 1440, height: 1000});

  // ---- no continuous animation anywhere in the product --------------------------------------
  // The iteration count lives on the effect's timing, not on the Animation object: reading
  // `animation.iterations` would compare undefined and pass no matter what shipped.
  const endless = await page.evaluate(() => document.getAnimations()
    .filter(animation => (animation.effect?.getComputedTiming()?.iterations ?? 0) === Infinity).length);
  assert.equal(endless, 0, 'nothing in the product animates forever');

  // ---- workspace entry: only a real destination change plays it ------------------------------
  await openDestination('board-home');
  await settle();
  await watchFade('order-list');
  await openDestination('workforce');
  await settle();
  assert.deepEqual(await visibleSections(), ['people-view'], 'the destination changed');
  const sectionClasses = await page.evaluate(() => document.getElementById('people-view').className);
  assert.equal(sectionClasses.includes('motion-'), false,
    'a settled destination carries no entry class once the motion has played');
  await page.evaluate(() => {window.sectionLog = [];});
  await openDestination('wip-ageing-insights');
  await settle();
  await openDestination('capacity-plan');
  await settle();
  assert.deepEqual(await visibleSections(), ['analytics-view'],
    'the twelve analytics reports share one section');

  // ---- the propagated replacement fade ------------------------------------------------------
  // Audit trail carries real ledger rows, so a filter change replaces content rather than a
  // placeholder.
  await openDestination('audit-trail');
  // The section is assembled after its own users request, so the list does not exist on the frame
  // the click returns on.
  await page.waitForFunction(() => (document.getElementById('audit-list')?.children.length ?? 0) > 0);
  await settle();
  await watchFade('audit-list');
  // The audit filter applies on submit only, and "Terapkan filter" is also rendered by the other
  // filter forms in the document, so the control is addressed inside its own form.
  await page.locator('#audit-category').selectOption({index: 1});
  await page.locator('#audit-filter button[type=submit]').click();
  await awaitFade();
  await settle();
  const auditFade = await fadeState();
  assert.equal(auditFade.started, true, 'an audit filter change fades the list as one unit');
  assert.equal(auditFade.finished, true, 'the audit replacement transition runs to completion');
  assert.equal((await motionStateOf('audit-list')).classes, 'list-host',
    'the audit replacement class is cleaned up');
  await clearFade();
  await page.getByRole('button', {name: 'Reset', exact: true}).click();
  await page.waitForFunction(() => (document.getElementById('audit-list')?.children.length ?? 0) > 0);
  await awaitFade();
  await settle();
  assert.equal((await fadeState()).asked, false,
    'resetting the audit section rebuilds it from scratch, which is a first render and never fades');

  // People keeps its roster in a static container, so a filter submit is a replacement and
  // re-entering the page with the same filter is not.
  await apiPost('/api/workforce/employees', {code: 'MOTION-' + Date.now(), name: 'CONTOH gerak roster',
    department: 'Produksi', reason: 'Fixture uji gerak M6'});
  await openDestination('workforce');
  await page.waitForFunction(() => document.querySelectorAll('#workforce-list .workforce-row').length > 0);
  await settle();
  await watchFade('workforce-list');
  await openDestination('board-home');
  await settle();
  await openDestination('workforce');
  await page.waitForFunction(() => document.querySelectorAll('#workforce-list .workforce-row').length > 0);
  await settle();
  assert.equal((await fadeState()).asked, false,
    'returning to People with the same filter is a first render for that page, not a replacement');
  await clearFade();
  await page.locator('#workforce-status').selectOption('present');
  await page.getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await awaitFade();
  await settle();
  const rosterFade = await fadeState();
  assert.equal(rosterFade.started, true, 'a roster filter change fades the list as one unit');
  assert.equal(rosterFade.finished, true, 'the roster replacement transition runs to completion');
  assert.equal((await motionStateOf('workforce-list')).classes, 'list-host',
    'the roster replacement class is cleaned up');
  assert.equal(await page.evaluate(() => [...document.querySelectorAll('#workforce-list .workforce-row')]
    .some(row => row.className.includes('motion'))), false, 'no individual roster row is animated');

  // The three approval-queue pages share one idiom and share one assertion: the filter change is
  // the replacement, and it fades whether or not the filtered queue has rows to show.
  for (const [label, nav, select, list] of [['Permintaan pembelian', 'purchase-requests', '#pr-page-status', 'pr-page-list'],
    ['Budget marketing', 'marketing-budgets', '#marketing-budget-status', 'marketing-budget-list'],
    ['Inbox approval', 'approvals', '#approval-status', 'approval-list']]) {
    await openDestination(nav);
    await page.waitForFunction(id => document.getElementById(id), list);
    await settle();
    await watchFade(list);
    await page.locator(select).selectOption({index: 1});
    await awaitFade();
    await settle();
    const faded = await fadeState();
    assert.equal(faded.started, true, `${label}: a filter change fades the queue as one unit`);
    assert.equal(faded.finished, true, `${label}: the queue replacement transition runs to completion`);
    assert.equal((await motionStateOf(list)).classes, 'list-host',
      `${label}: the queue replacement class is cleaned up`);
  }

  // ---- representative secondary dialogs ------------------------------------------------------
  // M3 proves the close contract in depth on one dialog; M6 checks that dialogs opened from other
  // destinations settle the same way, since a secondary task never becomes a second router.
  const dialogState = () => page.evaluate(() => {
    const dialog = document.getElementById('dialog');
    return {open: dialog.open, closing: dialog.classList.contains('is-closing'),
      motion: dialog.className.includes('motion-'),
      focus: document.activeElement === document.body ? 'body' : (document.activeElement?.id || 'control')};
  });
  await openDestination('audit-trail');
  await page.waitForFunction(() => (document.getElementById('audit-list')?.children.length ?? 0) > 0);
  await page.locator('#audit-list button[data-action="audit-event"]').first().click();
  await page.waitForFunction(() => document.getElementById('dialog').open);
  await settle();
  assert.equal((await dialogState()).open, true, 'an audit detail opens through the native dialog');
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.getElementById('dialog').open);
  await settle();
  const auditDialog = await dialogState();
  assert.equal(auditDialog.open, false, 'Escape closes the audit dialog through the guarded path');
  assert.equal(auditDialog.closing || auditDialog.motion, false,
    'the closed audit dialog keeps no exit state');
  assert.notEqual(auditDialog.focus, 'body', 'focus returns to the page rather than being dropped');
  assert.equal(await page.evaluate(() => document.querySelectorAll('#audit-list article').length) > 0, true,
    'the page behind the dialog keeps its rows and its scroll position');

  await openDestination('integrations');
  await page.waitForFunction(() => (document.getElementById('integrations-body')?.children.length ?? 0) > 0);
  await page.getByRole('button', {name: 'Riwayat sinkronisasi', exact: true}).click();
  await page.waitForFunction(() => document.getElementById('dialog').open);
  await settle();
  // The close control carries an aria-label, so it is addressed by its own id rather than by the
  // visible word it shows.
  await page.locator('#close-dialog').click();
  await page.waitForFunction(() => !document.getElementById('dialog').open);
  await settle();
  const runsDialog = await dialogState();
  assert.equal(runsDialog.open, false, 'the sync history dialog closes through its own control');
  assert.equal(runsDialog.closing || runsDialog.motion, false,
    'the closed sync history dialog keeps no exit state');

  // ---- the propagated refresh treatment ------------------------------------------------------
  // Integrations has no filter, so its refresh control is the only path that can keep content: the
  // status stays on screen, dimmed and reported busy, instead of resetting to a loading line.
  await openDestination('integrations');
  await page.waitForFunction(() => document.getElementById('integrations-body').children.length > 0);
  await settle();
  const holdIntegrations = await hold('**/api/integrations');
  await page.getByRole('button', {name: 'Muat ulang status', exact: true}).click();
  await holdIntegrations.started;
  await page.waitForTimeout(250);
  const integrationRefresh = await motionStateOf('integrations-body');
  assert.equal(integrationRefresh.hidden, false, 'an integrations refresh keeps the status on screen');
  assert.equal(integrationRefresh.classes.includes('is-refreshing'), true,
    'an integrations refresh reports the refreshing state');
  assert.equal(integrationRefresh.busy, 'true',
    'an integrations refresh marks the container busy for assistive technology');
  const integrationDim = parseFloat(integrationRefresh.opacity);
  assert.equal(integrationDim >= 0.72 && integrationDim <= 0.82, true,
    `the refresh dims inside the documented band (${integrationDim})`);
  assert.equal(await page.evaluate(() => document.getElementById('integrations-body').children.length > 0), true,
    'the existing status sections are still there during the refresh');
  holdIntegrations.release(); await holdIntegrations.settled;
  await page.unroute('**/api/integrations');
  await settle();
  const integrationSettled = await motionStateOf('integrations-body');
  assert.equal(integrationSettled.classes.includes('is-refreshing'), false,
    'the refreshing state is removed when the load settles');
  assert.equal(integrationSettled.busy, null, 'the busy marker is removed when the load settles');
  assert.equal(parseFloat(integrationSettled.opacity), 1, 'the container returns to full opacity');
  // Opening the destination is not a refresh: it has no previous context to preserve.
  await openDestination('board-home');
  await settle();
  const holdIntegrationsNav = await hold('**/api/integrations');
  await openDestination('integrations');
  await holdIntegrationsNav.started;
  await page.waitForTimeout(250);
  const integrationNav = await motionStateOf('integrations-body');
  assert.equal(integrationNav.classes.includes('is-refreshing'), false,
    'opening integrations is a first load, not a refresh');
  holdIntegrationsNav.release(); await holdIntegrationsNav.settled;
  await page.unroute('**/api/integrations');
  await settle();

  // The command centre is the same grammar on the largest surface: the report the operator is
  // reading stays visible under the refresh, while the KPI strip keeps its numbers.
  await openDestination('command-center');
  await page.waitForFunction(() => !document.getElementById('command-center-content').hidden);
  await settle();
  const holdCommand = await hold('**/api/command-center');
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await holdCommand.started;
  await page.waitForTimeout(250);
  const commandRefresh = await motionStateOf('command-center-content');
  assert.equal(commandRefresh.hidden, false, 'a command centre refresh keeps the report on screen');
  assert.equal(commandRefresh.classes.includes('is-refreshing'), true,
    'a command centre refresh reports the refreshing state');
  const commandDim = parseFloat(commandRefresh.opacity);
  assert.equal(commandDim >= 0.72 && commandDim <= 0.82, true,
    `the command centre refresh dims inside the documented band (${commandDim})`);
  assert.equal(await page.evaluate(() =>
    document.getElementById('command-center-summary').children.length > 0), true,
    'the KPI strip is never emptied before the new report lands');
  holdCommand.release(); await holdCommand.settled;
  await page.unroute('**/api/command-center');
  await settle();
  const commandSettled = await motionStateOf('command-center-content');
  assert.equal(commandSettled.classes.includes('is-refreshing'), false,
    'the command centre refreshing state is removed when the load settles');
  assert.equal(parseFloat(commandSettled.opacity), 1, 'the report returns to full opacity');
  // Opening the destination again hides the report while it loads, exactly as before M6.
  await openDestination('board-home');
  await settle();
  const holdCommandNav = await hold('**/api/command-center');
  await openDestination('command-center');
  await holdCommandNav.started;
  await page.waitForTimeout(250);
  assert.equal((await motionStateOf('command-center-content')).hidden, true,
    'opening the command centre is a first load and still shows the loading state');
  holdCommandNav.release(); await holdCommandNav.settled;
  await page.unroute('**/api/command-center');
  await settle();
  // A refresh that fails leaves no half-populated report: the panels the loader clears are only
  // some of the ones it fills, so anything left behind would show stale figures next to the error.
  await page.route('**/api/command-center', route => route.fulfill({status: 503,
    contentType: 'application/json', body: JSON.stringify({detail: 'Command center sedang sibuk'})}));
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await page.getByText('Command center sedang sibuk', {exact: false}).waitFor();
  await settle();
  const failedRefresh = await page.evaluate(() => {
    const content = document.getElementById('command-center-content');
    return {hidden: content.hidden, refreshing: content.classList.contains('is-refreshing'),
      busy: content.getAttribute('aria-busy'),
      populated: ['command-center-hero','command-center-channels','command-center-contribution',
        'command-center-products','command-center-operations','command-center-attention',
        'command-center-snapshots'].filter(id => document.getElementById(id).children.length)};
  });
  assert.equal(failedRefresh.hidden, true,
    'a failed refresh does not leave a half-populated report on screen');
  assert.equal(failedRefresh.refreshing, false, 'a failed refresh releases the dim');
  assert.equal(failedRefresh.busy, null, 'a failed refresh releases the busy marker');
  assert.deepEqual(failedRefresh.populated, [],
    'a failed refresh empties every panel the success path fills, not only some of them');
  await page.unroute('**/api/command-center');
  // Retrying after a failure is a first load again, so the loading state is what the operator sees.
  const holdRetry = await hold('**/api/command-center');
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await holdRetry.started;
  await page.waitForTimeout(250);
  assert.equal((await motionStateOf('command-center-content')).classes.includes('is-refreshing'), false,
    'a retry after a failed report is a first load, not a refresh with data to preserve');
  holdRetry.release(); await holdRetry.settled;
  await page.unroute('**/api/command-center');
  await settle();
  assert.equal(await page.evaluate(() => !document.getElementById('command-center-content').hidden), true,
    'the retry restores the report');

  // ---- reduced motion: every state signal, no movement ---------------------------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  for (const destination of DESTINATIONS.filter(entry =>
    ['board-home', 'workforce', 'command-center', 'integrations', 'audit-trail'].includes(entry.nav))) {
    await openDestination(destination.nav);
    await settle();
    const reduced = await page.evaluate(id => {
      const section = document.getElementById(id);
      const hosts = [...section.querySelectorAll('.list-host, .state'), section];
      return {classes: section.className,
        transitions: hosts.map(node => getComputedStyle(node).transitionDuration),
        transforms: hosts.map(node => getComputedStyle(node).transform),
        entry: [...document.querySelectorAll('.motion-enter,.is-ready')].filter(node => node.id !== 'notice').length};
    }, destination.section);
    assert.equal(reduced.classes.includes('motion-'), false,
      `${destination.label} plays no entry motion under reduced motion`);
    assert.equal(reduced.entry, 0, `${destination.label} leaves no motion class under reduced motion`);
    assert.equal(reduced.transitions.every(value => value === '0s'), true,
      `${destination.label} transitions nothing under reduced motion (${reduced.transitions})`);
    assert.equal(reduced.transforms.every(value => value === 'none' || value === 'matrix(1, 0, 0, 1, 0, 0)'), true,
      `${destination.label} moves nothing under reduced motion (${reduced.transforms})`);
  }
  // The refresh signal survives the preference: it is state, so it is still reported and still
  // visible, only without the fade into it. The page is opened first so the held request belongs to
  // the refresh control and not to the navigation.
  await openDestination('integrations');
  await page.waitForFunction(() => (document.getElementById('integrations-body')?.children.length ?? 0) > 0);
  await settle();
  const holdReduced = await hold('**/api/integrations');
  await page.getByRole('button', {name: 'Muat ulang status', exact: true}).click();
  await holdReduced.started;
  await page.waitForTimeout(250);
  const reducedRefresh = await motionStateOf('integrations-body');
  assert.equal(reducedRefresh.classes.includes('is-refreshing'), true,
    'reduced motion still reports the refreshing state');
  assert.equal(parseFloat(reducedRefresh.opacity) < 1, true, 'reduced motion still shows the dimmed state');
  assert.equal(reducedRefresh.transition, '0s', 'reduced motion shows the dim without a transition');
  holdReduced.release(); await holdReduced.settled;
  await page.unroute('**/api/integrations');
  await settle();
  // A replacement does not fade under the preference either, but it still replaces.
  await openDestination('workforce');
  await settle();
  await clearFade();
  await page.locator('#workforce-status').selectOption('all');
  await page.getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await page.waitForFunction(() => document.getElementById('workforce-list').children.length > 0);
  await page.waitForTimeout(500);
  await settle();
  assert.equal((await fadeState()).asked, false, 'reduced motion never fades a replaced list');
  assert.equal(await page.evaluate(() => document.getElementById('workforce-list').children.length > 0), true,
    'the roster is still replaced under reduced motion');
  await page.emulateMedia({reducedMotion: 'no-preference'});

  // ---- 320px at 200% while a replacement is in flight ----------------------------------------
  await page.setViewportSize({width: 320, height: 900});
  await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
  const overflowWatch = page.evaluate(async () => {
    const root = document.documentElement;
    const deadline = performance.now() + 800;
    let spilled = root.scrollWidth > root.clientWidth;
    while (performance.now() < deadline) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      spilled = spilled || root.scrollWidth > root.clientWidth;
    }
    return spilled;
  });
  await page.getByRole('button', {name: 'Menu', exact: true}).click();
  await page.locator('#app-sidebar #audit-trail').click();
  await page.waitForFunction(() => (document.getElementById('audit-list')?.children.length ?? 0) > 0);
  await page.locator('#audit-category').selectOption({index: 1});
  await page.locator('#audit-filter button[type=submit]').click();
  assert.equal(await overflowWatch, false, 'no document overflow while a list is replaced at 320px and 200%');
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});
  await page.setViewportSize({width: 1440, height: 1000});

  console.log('Consistency browser QA PASS: all 27 destinations hold their layout and leave no motion '
    + 'state at 1440/1024/768/390/320 and at 320 with 200% text, the refresh and replacement grammar '
    + 'reaches the remaining list pages, and reduced motion keeps every state signal without movement.');
};
