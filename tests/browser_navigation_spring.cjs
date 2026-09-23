// A3: the one A2 lens now has physics. These checks watch the real rendered rectangle across
// real frames instead of trusting class names or sleeping for a duration. They deliberately
// avoid asserting a position at an exact millisecond: what is asserted is that travel happens,
// that it reaches the latest destination after a retarget, that
// a layout correction does not become decorative movement, and that the loop stops dead when it
// arrives. No production internals are exposed for the tests; everything below is read from the
// DOM, computed style, and the page's own frame callbacks. Velocity continuity itself is checked
// against the shipped controller with a test-owned clock, so scheduler latency cannot hide it.
const assert = require('node:assert/strict');
const verifyVelocityContinuity = require('./test_navigation_spring.cjs');

module.exports = async ({page, login, admin, viewer}) => {
  await login(admin);
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.setViewportSize({width:1440, height:1000});

  // Frame instrumentation owns its own counter so releasing the global handle later cannot
  // break a callback that is still pending, and so the application's own frames are counted too.
  await page.evaluate(() => {
    window.springLens = document.getElementById('nav-selection-lens');
    const raf = window.requestAnimationFrame, cancel = window.cancelAnimationFrame;
    const pending = new Set();
    const frames = {executed:0, pending, raf, cancel, offset:0};
    window.springFrames = frames;
    window.requestAnimationFrame = callback => {
      const id = raf.call(window, time => { pending.delete(id); frames.executed++; callback(time + frames.offset); });
      pending.add(id); return id;
    };
    window.cancelAnimationFrame = id => { pending.delete(id); cancel.call(window, id); };
  });
  const frames = () => page.evaluate(() => ({executed:window.springFrames.executed, pending:window.springFrames.pending.size}));
  const rect = id => page.evaluate(id => {
    const node = id ? document.getElementById(id) : window.springLens;
    const box = node.getBoundingClientRect();
    return {x:box.x, y:box.y, width:box.width, height:box.height};
  }, id ?? null);

  // Arrived means exactly arrived: the target rectangle to render tolerance, the compositor hint
  // released, and no scripted motion class left behind. `will-change` is production behaviour,
  // not a test hook: the controller only sets it while the spring is actually running.
  const arrived = async id => {
    await page.waitForFunction(id => {
      const lens = window.springLens, target = document.getElementById(id);
      if (lens.hidden || target.getAttribute('aria-current') !== 'page') return false;
      const a = lens.getBoundingClientRect(), b = target.getBoundingClientRect();
      return ['x','y','width','height'].every(key => Math.abs(a[key] - b[key]) < .05)
        && getComputedStyle(lens).willChange === 'auto' && !document.querySelector('.motion-enter');
    }, id, {timeout:5000}).catch(async error => {
      console.error('A3 settle failure', await page.evaluate(id => {
        const lens = window.springLens, target = document.getElementById(id);
        return {id, lens:lens.getBoundingClientRect().toJSON(), target:target.getBoundingClientRect().toJSON(),
          hidden:lens.hidden, style:lens.getAttribute('style'), parent:lens.parentElement.className,
          willChange:getComputedStyle(lens).willChange, current:target.getAttribute('aria-current')};
      }, id));
      throw error;
    });
    assert.equal(await page.locator('.nav-selection-lens').count(), 1, 'exactly one lens');
    assert.equal(await page.evaluate(() => window.springLens === document.getElementById('nav-selection-lens')), true,
      'the same DOM node survives; nothing is cloned, ghosted or cross-faded');
    assert.equal(await page.locator('#app-sidebar [aria-current]').count(), 1, 'exactly one aria-current');
  };
  const hidden = () => page.waitForFunction(() => window.springLens.hidden
    && !document.getElementById('app-sidebar').classList.contains('nav-lens-ready'));

  // One click, then one sample per frame, read after the page's own callbacks for that frame
  // have already written. `semantic` is captured synchronously, before any frame runs at all.
  const travel = (id, count = 40, {interrupt = null, at = 0} = {}) => page.evaluate(
    async ({id, count, interrupt, at}) => {
      const lens = window.springLens;
      const read = () => {
        const box = lens.getBoundingClientRect();
        return {y:box.y, x:box.x, width:box.width, height:box.height,
          parent:lens.parentElement.id || lens.parentElement.className, style:lens.getAttribute('style') || ''};
      };
      const before = read();
      document.getElementById(id).click();
      const semantic = {selected:[...document.querySelectorAll('#app-sidebar [aria-current]')].map(node => node.id),
        section:document.querySelector('.workspace-main>section:not([hidden])')?.id,
        drawer:document.body.classList.contains('nav-open')};
      const samples = [];
      let interrupted = null;
      for (let index = 0; index < count; index++) {
        await new Promise(resolve => requestAnimationFrame(resolve));
        samples.push(read());
        if (interrupt && index === at) {
          interrupted = samples.length - 1;
          document.getElementById(interrupt).click();
        }
      }
      return {before, semantic, samples, interrupted};
    }, {id, count, interrupt, at});

  const spread = samples => new Set(samples.map(sample => Math.round(sample.y * 10))).size;
  const clean = samples => samples.every(sample => !/NaN|Infinity/.test(sample.style)
    && sample.width > 0 && sample.height > 0);

  const start = async id => { await page.evaluate(() => { document.getElementById('app-sidebar').scrollTop = 0; });
    await page.locator('#' + id).click(); await arrived(id); };

  // ---- A. Normal travel: semantics immediately, presentation physically ----------------------
  await start('command-center');
  const normal = await travel('board-home');
  assert.deepEqual(normal.semantic.selected, ['board-home'], 'aria-current moves before any frame runs');
  assert.equal(normal.semantic.section, 'board-view', 'the page is already active while the lens is still travelling');
  const boardTarget = await rect('board-home');
  assert.ok(Math.abs(normal.samples[0].y - normal.before.y) < 1.5,
    `no teleport: the first frame is still at the old destination (${normal.samples[0].y} vs ${normal.before.y})`);
  assert.ok(Math.abs(normal.samples[0].y - boardTarget.y) > 20,
    'the first frame has not arrived at the new destination');
  const between = normal.samples.filter(sample => sample.y > normal.before.y + 2 && sample.y < boardTarget.y - 2);
  assert.ok(between.length >= 3, `intermediate positions exist (${between.length})`);
  assert.ok(spread(normal.samples) >= 8, `the lens is rendered at many distinct positions (${spread(normal.samples)})`);
  assert.equal(clean(normal.samples), true, 'no NaN, Infinity or non-positive dimension is ever written');
  // Both compositor requests are live while travelling and both are withdrawn on settling, so no
  // layer promotion outlives the motion that needed it.
  assert.ok(normal.samples.some(sample => sample.style.includes('translate3d')
    && sample.style.includes('will-change')), 'travel asks the compositor for a layer');
  await arrived('board-home');
  const resting = await page.evaluate(() => window.springLens.getAttribute('style'));
  assert.ok(!resting.includes('translate3d') && !resting.includes('will-change') && resting.includes('translate('),
    `a settled lens keeps neither a 3D transform nor a compositor hint (${resting})`);
  assert.deepEqual(await rect(), await rect('board-home'), 'final geometry is the target geometry');

  // Deformation is measured between two destinations of identical size, so every pixel of excess
  // height is the velocity stretch itself rather than the physical resize of case B.
  await start('command-center');
  const long = await travel('products', 45);
  const products = await rect('products');
  assert.deepEqual([products.height, products.width], [(await rect('command-center')).height, (await rect('command-center')).width],
    'source and destination are the same size, so any excess is deformation');
  const stretch = Math.max(...long.samples.map(sample => sample.height)) / products.height;
  assert.ok(stretch > 1.01 && stretch <= 1.071,
    `velocity elongates the lens along its dominant axis, tightly capped (peak ${(stretch * 100 - 100).toFixed(1)}%)`);
  const narrowed = Math.min(...long.samples.map(sample => sample.width)) / products.width;
  assert.ok(narrowed > .96 && narrowed < 1,
    `and narrows it very slightly across that axis (${(100 - narrowed * 100).toFixed(1)}%)`);
  await arrived('products');
  assert.deepEqual(await rect(), products, 'no deformation survives the settle');

  // ---- B. Size morph: a 40px row to a 34px analytics child ----------------------------------
  await start('workforce');
  const before = await rect('workforce');
  const morph = await travel('capacity-plan', 45);
  const child = await rect('capacity-plan');
  assert.notEqual(before.height, child.height, 'the two destinations really are different sizes');
  const heights = morph.samples.map(sample => sample.height);
  assert.ok(heights.some(height => height < before.height - .5 && height > child.height + .5),
    `height passes through intermediate values ${before.height} -> ${child.height}`);
  await arrived('capacity-plan');
  assert.deepEqual(await rect(), child, 'width and height converge on the real child geometry');

  // ---- C. Rapid retarget: four destinations, none allowed to finish --------------------------
  await start('command-center');
  const rapid = await page.evaluate(async () => {
    const lens = window.springLens, positions = [];
    const ids = ['workforce', 'capacity-plan', 'replenishment', 'command-center'];
    for (const id of ids) {
      document.getElementById(id).click();
      // Three frames each: far less than the ~20 frames a settle needs.
      for (let index = 0; index < 3; index++) await new Promise(resolve => requestAnimationFrame(resolve));
      positions.push({id, y:lens.getBoundingClientRect().y, selected:[...document.querySelectorAll('#app-sidebar [aria-current]')].map(node => node.id)});
    }
    return positions;
  });
  for (const step of rapid) assert.deepEqual(step.selected, [step.id], 'every click lands semantically at once');
  await arrived('command-center');
  assert.deepEqual(await rect(), await rect('command-center'), 'the latest destination wins the final write');
  const stale = await rect('replenishment');
  assert.ok(Math.abs((await rect()).y - stale.y) > 20, 'no stale destination is written at the end');
  assert.equal((await frames()).pending, 0, 'rapid navigation leaves no frame pending');

  // ---- D. Velocity continuity: momentum survives a reversal ---------------------------------
  // Check the physical state at retarget and the next integrator step directly. A fixed rendered
  // coast after five asynchronous frames depends on refresh rate and missed frames, not just
  // preserved velocity. Cases A/B still measure real rendered travel and deformation.
  verifyVelocityContinuity();
  await start('command-center');
  const reversed = await travel('replenishment', 40, {interrupt:'command-center', at:4});
  assert.equal(clean(reversed.samples), true);
  await arrived('command-center');
  assert.deepEqual(await rect(), await rect('command-center'), 'the rendered reversal reaches the latest target exactly');

  // ---- E. Approval context: one object, two positioning contexts ----------------------------
  await start('marketing-budgets');
  const intoCta = await travel('approvals', 45);
  assert.equal(intoCta.samples[0].parent.includes('sidebar-cta'), true, 'the lens is reparented into the CTA at once');
  assert.ok(Math.abs(intoCta.samples[0].y - intoCta.before.y) < 1.5,
    `reparenting alone moves nothing in viewport space (${intoCta.before.y} -> ${intoCta.samples[0].y})`);
  assert.ok(spread(intoCta.samples) >= 8, 'it then travels physically inside the new context');
  assert.equal(clean(intoCta.samples), true);
  await arrived('approvals');
  assert.equal(await page.evaluate(() => window.springLens.parentElement.className.includes('sidebar-cta')), true);
  assert.deepEqual(await rect(), await rect('approvals'));
  // Reaching marketing-budgets scrolled the sidebar; the return destination has to be on screen
  // for the reparent to be about coordinates rather than about an unmeasurable target.
  await page.evaluate(() => { document.getElementById('app-sidebar').scrollTop = 0; });
  await arrived('approvals');
  const outOfCta = await travel('command-center', 45);
  assert.equal(outOfCta.samples[0].parent, 'app-sidebar', 'and back into the sidebar context');
  assert.ok(Math.abs(outOfCta.samples[0].y - outOfCta.before.y) < 1.5,
    `the return reparent does not jump either (${outOfCta.before.y} -> ${outOfCta.samples[0].y})`);
  assert.ok(spread(outOfCta.samples) >= 8);
  await arrived('command-center');
  assert.equal(await page.locator('.nav-selection-lens').count(), 1, 'no second approval indicator was created');

  // ---- F. Analytics collapse cancels, reopening snaps ---------------------------------------
  await start('capacity-plan');
  await page.locator('.nav-summary').click();
  await hidden();
  assert.equal((await frames()).pending, 0, 'collapsing cancels the motion frame');
  assert.equal(await page.locator('#capacity-plan').getAttribute('aria-current'), 'page', 'semantics survive the collapse');
  const reopened = await page.evaluate(async () => {
    const lens = window.springLens, samples = [];
    document.querySelector('.nav-summary').click();
    for (let index = 0; index < 6; index++) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      const box = lens.getBoundingClientRect();
      samples.push({y:box.y, hidden:lens.hidden});
    }
    const target = document.getElementById('capacity-plan').getBoundingClientRect();
    return {samples, target:target.y};
  });
  const firstVisible = reopened.samples.find(sample => !sample.hidden);
  assert.ok(Math.abs(firstVisible.y - reopened.target) < .05,
    'reopening snaps straight to the child; it does not fly in from a stale hidden position');
  await arrived('capacity-plan');

  // ---- G. Sidebar scroll stays exact, it does not spring behind the content ------------------
  const scrolled = await page.evaluate(async () => {
    const lens = window.springLens, sidebar = document.getElementById('app-sidebar'), samples = [];
    sidebar.scrollTop += 60;
    for (let index = 0; index < 5; index++) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      const a = lens.getBoundingClientRect(), b = document.getElementById('capacity-plan').getBoundingClientRect();
      samples.push(Math.abs(a.y - b.y));
    }
    return samples;
  });
  assert.ok(scrolled.every(offset => offset < .05),
    `scrolling keeps the lens exactly on its button, with no chase (${JSON.stringify(scrolled)})`);
  assert.equal((await frames()).pending, 0, 'a scroll correction starts no spring');
  await page.evaluate(() => { document.getElementById('app-sidebar').scrollTop = 0; });
  await arrived('capacity-plan');

  // ---- H. Resize corrects geometry without decorative travel ---------------------------------
  const settledFrames = await frames();
  await page.setViewportSize({width:1100, height:1000});
  await arrived('capacity-plan');
  const resizeCost = (await frames()).executed - settledFrames.executed;
  assert.ok(resizeCost < 8, `a layout correction is a snap, not a journey (${resizeCost} frames)`);
  await page.setViewportSize({width:1440, height:1000});
  await arrived('capacity-plan');

  // ---- Large frame gaps and non-monotonic time must not explode ------------------------------
  for (const offset of [3000, -3000]) {
    await start('command-center');
    await page.evaluate(offset => {
      document.getElementById('replenishment').click();
      // A resumed background tab, a long task or a clock that moves backwards: the integrator
      // must refuse the interval rather than turn it into velocity.
      requestAnimationFrame(() => { window.springFrames.offset = offset; });
    }, offset);
    await page.waitForTimeout(120);
    await page.evaluate(() => { window.springFrames.offset = 0; });
    await arrived('replenishment');
    assert.deepEqual(await rect(), await rect('replenishment'), `a ${offset}ms timestamp jump settles exactly`);
  }

  // ---- I. Mobile drawer keeps its immediate lifecycle ---------------------------------------
  await page.setViewportSize({width:390, height:844});
  // Establish a known selection through the drawer itself, which closes on every navigation.
  await page.locator('#menu-toggle').click();
  await page.locator('#command-center').click();
  await hidden();
  await page.locator('#menu-toggle').click();
  await page.evaluate(() => { document.getElementById('app-sidebar').scrollTop = 0; });
  await arrived('command-center');
  const drawer = await travel('workforce', 6);
  assert.equal(drawer.semantic.drawer, false, 'the drawer still closes immediately; it does not wait for the lens');
  assert.deepEqual(drawer.semantic.selected, ['workforce']);
  await hidden();
  assert.equal(await page.locator('#app-sidebar').evaluate(node => node.inert), true);
  assert.equal((await frames()).pending, 0, 'the hidden drawer cancels motion');
  await page.locator('#menu-toggle').click();
  const reopenedDrawer = await page.evaluate(async () => {
    const lens = window.springLens, samples = [];
    for (let index = 0; index < 6; index++) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      const a = lens.getBoundingClientRect(), b = document.getElementById('workforce').getBoundingClientRect();
      samples.push({hidden:lens.hidden, offset:Math.abs(a.y - b.y)});
    }
    return samples;
  });
  const shown = reopenedDrawer.find(sample => !sample.hidden);
  assert.ok(shown.offset < .05, 'reopening the drawer shows the lens already on the current destination');
  await arrived('workforce');
  await page.setViewportSize({width:1440, height:1000});
  await arrived('workforce');

  // ---- J. Reduced motion: no travel at all --------------------------------------------------
  await page.emulateMedia({reducedMotion:'reduce'});
  await start('command-center');
  for (const id of ['board-home', 'capacity-plan', 'replenishment', 'approvals', 'command-center']) {
    const instant = await page.evaluate(async id => {
      const lens = window.springLens;
      document.getElementById(id).click();
      const executed = window.springFrames.executed;
      await new Promise(resolve => requestAnimationFrame(resolve));
      const a = lens.getBoundingClientRect(), b = document.getElementById(id).getBoundingClientRect();
      const first = ['x', 'y', 'width', 'height'].every(key => Math.abs(a[key] - b[key]) < .05);
      const willChange = getComputedStyle(lens).willChange;
      await new Promise(resolve => requestAnimationFrame(resolve));
      const second = lens.getBoundingClientRect();
      return {first, willChange, moved:Math.abs(second.y - a.y), spent:window.springFrames.executed - executed};
    }, id);
    assert.equal(instant.first, true, `${id}: reduced motion places the lens on the very next frame`);
    assert.equal(instant.willChange, 'auto', `${id}: no compositor hint, because nothing is animating`);
    assert.ok(instant.moved < .05, `${id}: and it does not move afterwards`);
    assert.ok(instant.spent <= 3, `${id}: no integrator frames are spent (${instant.spent})`);
    await arrived(id);
  }
  const reducedIdle = await frames();
  await page.waitForTimeout(500);
  assert.deepEqual(await frames(), reducedIdle, 'reduced motion performs zero frame work at rest');

  // ---- K. The preference changing mid-flight cancels and snaps -------------------------------
  await page.emulateMedia({reducedMotion:'no-preference'});
  await start('command-center');
  await page.locator('#replenishment').click();
  await page.waitForTimeout(60);
  const flying = await rect();
  const destination = await rect('replenishment');
  assert.ok(Math.abs(flying.y - destination.y) > 20, 'the spring really is still in flight');
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.waitForFunction(() => {
    const a = window.springLens.getBoundingClientRect(), b = document.getElementById('replenishment').getBoundingClientRect();
    return ['x', 'y', 'width', 'height'].every(key => Math.abs(a[key] - b[key]) < .05);
  }, null, {timeout:1000});
  assert.equal(await page.evaluate(() => getComputedStyle(window.springLens).willChange), 'auto');
  await page.waitForTimeout(200);
  assert.equal((await frames()).pending, 0, 'the cancelled spring leaves no pending frame');
  assert.deepEqual(await rect(), destination, 'it snapped to the latest target, not to where it happened to be');
  // Returning the preference replays nothing; only the next navigation may move.
  await page.emulateMedia({reducedMotion:'no-preference'});
  const quiet = await frames();
  await page.waitForTimeout(300);
  assert.deepEqual(await frames(), quiet, 'restoring the preference does not resume old travel');

  // ---- Session teardown carries no momentum into the next identity --------------------------
  await start('board-home');
  await page.locator('#replenishment').click();
  await page.locator('#logout').click();
  await page.locator('#login-view:not([hidden])').waitFor();
  await hidden();
  assert.equal(await page.evaluate(() => window.springLens.getAttribute('style')), null,
    'logout clears geometry, velocity and the compositor hint together');
  assert.equal((await frames()).pending, 0, 'and cancels both the measurement and the motion frame');
  await login(viewer);
  await page.evaluate(() => { document.getElementById('app-sidebar').scrollTop = 0; });
  const fresh = await page.evaluate(async () => {
    const lens = window.springLens, samples = [];
    for (let index = 0; index < 6; index++) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      const a = lens.getBoundingClientRect(), b = document.getElementById('board-home').getBoundingClientRect();
      samples.push({hidden:lens.hidden, offset:Math.abs(a.y - b.y)});
    }
    return samples;
  });
  const first = fresh.find(sample => !sample.hidden);
  assert.ok(first.offset < .05, 'the new session starts settled on its own destination, with no flight from the old one');
  assert.equal(await page.locator('#audit-trail').isHidden(), true, 'and the admin-only destinations are gone');
  await arrived('board-home');
  await login(admin);
  await page.evaluate(() => { document.getElementById('app-sidebar').scrollTop = 0; });
  await arrived('board-home');

  // ---- L. Idle: nothing runs once the object has arrived -------------------------------------
  await start('capacity-plan');
  await page.waitForTimeout(100);
  const idle = await frames();
  assert.equal(idle.pending, 0);
  await page.waitForTimeout(500);
  assert.deepEqual(await frames(), idle, 'a settled lens performs zero frame work across 500ms');

  await page.evaluate(() => {
    window.requestAnimationFrame = window.springFrames.raf;
    window.cancelAnimationFrame = window.springFrames.cancel;
    delete window.springFrames; delete window.springLens;
  });
  console.log('A3 navigation spring PASS: immediate semantics, physical travel, size morph, rapid retarget, '
    + 'preserved momentum, approval reparent without a jump, collapse/scroll/resize corrections, bounded frame gaps, '
    + 'mobile drawer, reduced motion and mid-flight preference change, session teardown, zero idle frames.');
};
