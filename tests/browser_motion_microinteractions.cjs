// M5 microinteractions and theme: the theme transition that only the toggle arms, progress values
// that interpolate only when the number really changed, scanner feedback with an untouched
// keyboard path, chip tint, and the absence of any continuous decorative animation. Asserts
// lifecycle flags and settled outcomes rather than animation timings.
const assert = require('node:assert/strict');

module.exports = async ({page, login, openSidebarDestination, admin, apiGet}) => {
  const heading = name => page.getByRole('heading', {name, exact: true}).waitFor();
  const token = name => page.evaluate(key =>
    getComputedStyle(document.documentElement).getPropertyValue(key).trim(), name);
  const resultTinted = () => page.evaluate(() =>
    document.getElementById('bundle-scan-result').classList.contains('is-scan-ok'));

  await login(admin);

  // ---- first paint carries no theme transition ---------------------------------------------
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('is-theming')), false,
    'the initial paint never arms the theme transition');
  assert.equal(await page.evaluate(() => getComputedStyle(document.body).transitionDuration), '0s',
    'no colour transition is kept running for the whole session');

  // ---- the toggle is the only thing that arms it, and it lets go ---------------------------
  await page.evaluate(() => {
    window.themeLog = [];
    const root = document.documentElement;
    new MutationObserver(() => window.themeLog.push({classes: root.className}))
      .observe(root, {attributes: true, attributeFilter: ['class']});
    document.body.addEventListener('transitionrun', event => {
      if (event.propertyName === 'background-color')
        window.themeLog.push({type: 'run', target: event.target.tagName});
    }, true);
    document.body.addEventListener('transitionend', event => {
      if (event.propertyName === 'background-color')
        window.themeLog.push({type: 'end', target: event.target.tagName});
    }, true);
  });
  const themeBefore = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.locator('#theme').click();
  const duringTheme = await page.evaluate(() => ({
    theming: document.documentElement.classList.contains('is-theming'),
    duration: getComputedStyle(document.body).transitionDuration,
    theme: document.documentElement.dataset.theme,
  }));
  assert.equal(duringTheme.theming, true, 'the toggle arms the theme transition');
  assert.equal(parseFloat(duringTheme.duration) > 0, true, 'the body takes a real transition while armed');
  assert.notEqual(duringTheme.theme, themeBefore, 'the theme itself changes');
  await page.waitForTimeout(400);
  const themeLog = await page.evaluate(() => window.themeLog);
  assert.equal(themeLog.some(entry => entry.type === 'run' && entry.target === 'BODY'), true,
    'the surface really transitions rather than only gaining a class');
  assert.equal(themeLog.some(entry => entry.type === 'end' && entry.target === 'BODY'), true,
    'that transition runs to completion');
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('is-theming')), false,
    'the class is released after one token');
  assert.equal(await page.evaluate(() => getComputedStyle(document.body).transitionDuration), '0s',
    'the session goes back to having no global colour transition');

  // ---- the theme transition never replaces a component's own transition ---------------------
  // The theming selector contributes no specificity, so a page entry that is mid-flight keeps its
  // opacity and transform transition instead of being swapped for a colour one.
  const entryTransition = await page.evaluate(() => {
    const section = document.querySelector('.workspace-main > section:not([hidden])');
    section.classList.add('motion-enter', 'is-ready');
    document.documentElement.classList.add('is-theming');
    const property = getComputedStyle(section).transitionProperty;
    section.classList.remove('motion-enter', 'is-ready');
    document.documentElement.classList.remove('is-theming');
    return property;
  });
  assert.equal(entryTransition.includes('opacity') && entryTransition.includes('transform'), true,
    'an in-flight page entry keeps its own transition while the theme is armed');
  const ownedTransition = await page.evaluate(() => {
    const notice = document.getElementById('notice');
    notice.classList.add('motion-exit');
    document.documentElement.classList.add('is-theming');
    const property = getComputedStyle(notice).transitionProperty;
    notice.classList.remove('motion-exit');
    document.documentElement.classList.remove('is-theming');
    return property;
  });
  assert.equal(ownedTransition, 'opacity, transform',
    'the zero-specificity theme rule cannot replace another component transition');

  // ---- reduced motion changes the theme without arming anything -----------------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  const reducedBefore = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.locator('#theme').click();
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains('is-theming')), false,
    'reduced motion changes the theme without a transition');
  assert.notEqual(await page.evaluate(() => document.documentElement.dataset.theme), reducedBefore,
    'the theme still changes under reduced motion');
  await page.emulateMedia({reducedMotion: 'no-preference'});
  if (await page.evaluate(() => document.documentElement.dataset.theme) !== themeBefore)
    await page.locator('#theme').click();
  await page.waitForTimeout(300);

  // ---- progress values interpolate only when the number really changed ----------------------
  await openSidebarDestination('Produksi');
  await heading('Yang sedang dikerjakan.');
  await page.locator('#order-list .order-row').first().waitFor();
  const board = await apiGet('/api/production-board?' + new URLSearchParams({q: '', status: 'all',
    owner_id: '', stage: 'all', limit: '25', offset: '0'}));
  const order = board.orders[0];
  const progressValue = id => page.evaluate(key => {
    const node = document.querySelector(`.order-row progress[data-order="${key}"]`);
    return node ? Number(node.value) : null;
  }, id);
  assert.equal(await progressValue(order.id), order.totals.warehouse,
    'a first render paints the real value without a ramp from zero');

  const bumped = Number(order.totals.warehouse) + 40;
  await page.route('**/api/production-board?*', async route => {
    const response = await route.fetch();
    const body = await response.json();
    const row = body.orders.find(item => item.id === order.id);
    if (row) row.totals.warehouse = bumped;
    await route.fulfill({response, json: body});
  });
  await page.evaluate(key => {
    window.progressLog = [];
    const sample = () => {
      const node = document.querySelector(`.order-row progress[data-order="${key}"]`);
      if (node) window.progressLog.push({value: Number(node.value), at: Math.round(performance.now())});
      if (window.progressLog.length < 120) requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  }, order.id);
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('summary').hasAttribute('aria-busy'));
  await page.waitForTimeout(400);
  await page.unroute('**/api/production-board?*');
  const progressLog = await page.evaluate(() => window.progressLog);
  const intermediate = progressLog.filter(entry => entry.value > Number(order.totals.warehouse) && entry.value < bumped);
  assert.equal(intermediate.length > 0, true,
    'a changed value moves through the middle instead of jumping');
  assert.equal(progressLog.at(-1).value, bumped, 'the interpolation settles on the new value');
  const ramp = intermediate.at(-1).at - intermediate[0].at;
  assert.equal(ramp <= 300, true, `the interpolation stays inside the documented budget (${ramp}ms)`);

  // ---- reduced motion sets the new value without moving through it --------------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  await page.route('**/api/production-board?*', async route => {
    const response = await route.fetch();
    const body = await response.json();
    const row = body.orders.find(item => item.id === order.id);
    if (row) row.totals.warehouse = bumped + 25;
    await route.fulfill({response, json: body});
  });
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('summary').hasAttribute('aria-busy'));
  assert.equal(await progressValue(order.id), bumped + 25,
    'reduced motion writes the new progress value directly');
  await page.unroute('**/api/production-board?*');
  await page.emulateMedia({reducedMotion: 'no-preference'});
  await page.getByRole('button', {name: 'Muat ulang', exact: true}).click();
  await page.waitForFunction(() => !document.getElementById('summary').hasAttribute('aria-busy'));

  // ---- scanner feedback: a brief tint, and a keyboard path that never moves -----------------
  await page.route('**/api/bundles/scan?*', route => route.fulfill({status: 200, contentType: 'application/json',
    body: JSON.stringify({id: 'motion-scan-1', reference: 'BDL-MOTION', sku: 'SKU-1', size: 'M',
      quantity: 5, order_reference: 'ORD-1'})}));
  await openSidebarDestination('Scan bundle');
  await heading('Scan bundle');
  const scanInput = page.getByLabel('Kode bundle', {exact: true});
  await scanInput.fill('BEELOFT:BUNDLE:motion');
  await scanInput.press('Enter');
  await page.getByText('BDL-MOTION', {exact: false}).waitFor();
  const scanned = await page.evaluate(() => {
    const node = document.getElementById('bundle-scan-result');
    return {tinted: node.classList.contains('is-scan-ok'),
      background: getComputedStyle(node).backgroundColor,
      focusKept: document.activeElement === document.getElementById('bundle-scan-code'),
      selected: document.getElementById('bundle-scan-code').selectionStart === 0};
  });
  assert.equal(scanned.tinted, true, 'a valid scan tints the result surface');
  assert.notEqual(scanned.background, 'rgba(0, 0, 0, 0)', 'the tint is a real surface colour');
  assert.equal(scanned.focusKept, true, 'the scan leaves keyboard focus where it was');
  assert.equal(scanned.selected, true, 'the code stays selected so the next scan replaces it');
  await page.waitForTimeout(1600);
  assert.equal(await resultTinted(), false, 'the tint releases on its own');
  assert.equal(await page.evaluate(() =>
    getComputedStyle(document.getElementById('bundle-scan-result')).backgroundColor), 'rgba(0, 0, 0, 0)',
    'the surface returns to its resting colour');

  // The tint is the state a valid scan reports, so it survives reduced motion; only its release
  // moves. This is the one M5 pattern that was reachable in reduced-motion mode and it was not
  // covered: the colour was declared inside the `no-preference` query, so the signal disappeared
  // with the motion instead of staying as state.
  await page.emulateMedia({reducedMotion: 'reduce'});
  await scanInput.fill('BEELOFT:BUNDLE:motion');
  await scanInput.press('Enter');
  await page.getByText('BDL-MOTION', {exact: false}).waitFor();
  const reducedScan = await page.evaluate(() => {
    const node = document.getElementById('bundle-scan-result');
    return {tinted: node.classList.contains('is-scan-ok'),
      background: getComputedStyle(node).backgroundColor,
      transition: getComputedStyle(node).transitionDuration};
  });
  assert.equal(reducedScan.tinted, true, 'reduced motion still reports a valid scan as a state');
  assert.notEqual(reducedScan.background, 'rgba(0, 0, 0, 0)', 'the success tint is still visible');
  assert.equal(reducedScan.transition, '0s', 'the tint is not animated under reduced motion');
  await page.emulateMedia({reducedMotion: 'no-preference'});
  await page.waitForTimeout(1400);
  assert.equal(await resultTinted(), false, 'the tint still releases under the normal preference');

  await page.unroute('**/api/bundles/scan?*');
  await page.route('**/api/bundles/scan?*', route => route.fulfill({status: 404, contentType: 'application/json',
    body: JSON.stringify({detail: 'Label bundle tidak dikenal'})}));
  await scanInput.fill('BEELOFT:BUNDLE:tidak-ada');
  await scanInput.press('Enter');
  await page.getByText('Label bundle tidak dikenal', {exact: false}).waitFor();
  const rejected = await page.evaluate(() => ({
    tinted: document.getElementById('bundle-scan-result').classList.contains('is-scan-ok'),
    focusKept: document.activeElement === document.getElementById('bundle-scan-code'),
    message: document.getElementById('bundle-scan-error').hidden,
  }));
  assert.equal(rejected.tinted, false, 'a rejected scan carries no success tint');
  assert.equal(rejected.message, false, 'the failure is reported immediately');
  assert.equal(rejected.focusKept, true, 'the keyboard path survives a rejected scan');
  await page.unroute('**/api/bundles/scan?*');

  // A second scan can fail while the first success tint is still being held. Starting the new
  // attempt clears both that state and its timer, so a rejected code is never presented with a
  // stale success colour.
  await page.route('**/api/bundles/scan?*', route => {
    const code = new URL(route.request().url()).searchParams.get('code');
    if (code === 'BEELOFT:BUNDLE:cepat') return route.fulfill({status: 200,
      contentType: 'application/json', body: JSON.stringify({id: 'motion-scan-2',
        reference: 'BDL-CEPAT', sku: 'SKU-1', size: 'M', quantity: 5,
        order_reference: 'ORD-1'})});
    return route.fulfill({status: 404, contentType: 'application/json',
      body: JSON.stringify({detail: 'Label kedua tidak dikenal'})});
  });
  await scanInput.fill('BEELOFT:BUNDLE:cepat');
  await scanInput.press('Enter');
  await page.getByText('BDL-CEPAT', {exact: false}).waitFor();
  assert.equal(await resultTinted(), true, 'the first scan in a rapid pair is tinted');
  await scanInput.fill('BEELOFT:BUNDLE:gagal-cepat');
  await scanInput.press('Enter');
  await page.getByText('Label kedua tidak dikenal', {exact: false}).waitFor();
  assert.equal(await resultTinted(), false,
    'a rapid rejected scan cannot retain the preceding success tint');
  await page.unroute('**/api/bundles/scan?*');

  // ---- chips, disclosure and the absence of continuous animation ----------------------------
  const chip = await page.evaluate(() => {
    const node = document.querySelector('.status-label, .badge');
    const style = getComputedStyle(node);
    return {property: style.transitionProperty, transform: style.transform};
  });
  assert.equal(/transform|scale/.test(chip.property), false, 'a status chip animates colour only');
  assert.equal(chip.transform, 'none', 'a status chip never carries a transform');
  const caret = await page.evaluate(() => {
    const style = getComputedStyle(document.querySelector('.nav-caret'));
    return {properties: style.transitionProperty.split(',').map(value => value.trim()),
      durations: style.transitionDuration.split(',').map(value => value.trim()),
      children: getComputedStyle(document.querySelector('.nav-children')).transitionProperty};
  });
  const rotation = caret.properties.indexOf('transform');
  assert.notEqual(rotation, -1,
    'the caret really rotates — it is an .icon, so the summary colour rule used to take the shorthand');
  assert.equal(caret.properties.includes('scale') || caret.properties.includes('height'), false,
    'the caret animates rotation and colour only');
  assert.equal(parseFloat(caret.durations[rotation]) * 1000, parseFloat(await token('--motion-base')),
    'the caret duration comes from the shared token');
  assert.equal(caret.children, 'all', 'the disclosure content is never height-animated');
  // The iteration count lives on the effect's timing, not on the Animation object: reading
  // `animation.iterations` would compare undefined and pass no matter what shipped.
  const endless = () => page.evaluate(() => document.getAnimations()
    .filter(animation => (animation.effect?.getComputedTiming()?.iterations ?? 0) === Infinity).length);
  assert.equal(await endless(), 0, 'nothing in the product animates forever');

  console.log('Microinteraction browser QA PASS: only the theme toggle arms a colour transition and it '
    + 'releases after one token, progress values interpolate only when the number changed and never '
    + 'from zero, a valid scan tints the result while the keyboard path stays put, chips animate '
    + 'colour only, the caret uses the shared token, and nothing animates forever.');
};
