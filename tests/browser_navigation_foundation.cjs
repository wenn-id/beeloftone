// Milestone A: workspace navigation foundation.
//
// Proves the activation contract for every destination integrated in this
// milestone: exactly one workspace section is visible after navigation,
// aria-current follows the destination, the mobile drawer closes and focus
// lands on the new page heading, repeated navigation does not duplicate content,
// a delayed response from a previous page cannot repaint the current one, no
// primary destination opens the global dialog, and 320px at 200% text stays
// inside the viewport.
const assert = require('node:assert/strict');

module.exports = async ({page, login, admin, openSidebarDestination}) => {
  await page.keyboard.press('Escape');
  await login(admin);
  await page.setViewportSize({width: 1440, height: 1000});

  const destinations = [
    {name: 'Command center', nav: 'command-center', section: 'command-center-view', heading: 'Apa yang perlu diputuskan hari ini.'},
    {name: 'Produksi', nav: 'board-home', section: 'board-view', heading: 'Yang sedang dikerjakan.'},
    {name: 'Bahan baku', nav: 'materials', section: 'materials-view', heading: 'Bahan masuk, pemakaian tercatat.'},
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

  // Repeated navigation re-enters the same destination without duplicating
  // handlers or re-rendering content on top of itself.
  await page.getByRole('button', {name: 'Semua order', exact: false}).click();
  await page.waitForFunction(() => !document.getElementById('order-list').hidden);
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
    +'command center, and no horizontal overflow at 320px with 200% text.');
};
