// M1 motion foundation: canonical tokens, tactile press feedback, focus polish and the
// explicit reduced-motion path. This asserts semantic outcomes — which scale a control
// settles at, whether a transition exists at all, whether a control's own transform survives —
// rather than animation timing curves, per the motion specification's test style.
//
// Tactile feedback is proven on Produksi first (the golden screen) and only then on the
// shared controls, matching the milestone's validation order.
const assert = require('node:assert/strict');

module.exports = async ({page, login, openSidebarDestination, admin, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;

  const pressScale = el => getComputedStyle(el).scale;
  const isPressed = value => value !== 'none' && parseFloat(value) < 1;

  // Press a control, run `body` while the pointer is genuinely down, then release away from
  // the control so no click fires — no navigation, no mutation, no dialog.
  async function whilePressed(locator, body) {
    await locator.scrollIntoViewIfNeeded();
    const box = await locator.boundingBox();
    assert.ok(box, 'a control must be laid out before it can be pressed');
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    try {
      return await body();
    } finally {
      await page.mouse.move(1, 1);
      await page.mouse.up();
    }
  }

  // The press scale is transitioned, so the first frame still reads the resting value. Wait
  // for the press to settle instead of sampling the instant the button goes down.
  async function settledPressScale(locator) {
    const deadline = Date.now() + 800;
    let value = await locator.evaluate(pressScale);
    while (!isPressed(value) && Date.now() < deadline) {
      await page.waitForTimeout(25);
      value = await locator.evaluate(pressScale);
    }
    return value;
  }

  // The negative case: sample across a window and require that no press is ever observed.
  async function scaleStaysUnpressed(locator, windowMs = 240) {
    const deadline = Date.now() + windowMs;
    let observed = await locator.evaluate(pressScale);
    let pressed = isPressed(observed);
    while (Date.now() < deadline) {
      await page.waitForTimeout(25);
      observed = await locator.evaluate(pressScale);
      pressed = pressed || isPressed(observed);
    }
    return {pressed, observed};
  }

  // `:focus-visible` only matches once focus arrives from the keyboard, so walk the tab order
  // instead of calling focus(), which would silently skip the ring.
  async function focusViaKeyboard(selector) {
    await page.evaluate(() => document.activeElement && document.activeElement.blur());
    for (let step = 0; step < 120; step += 1) {
      await page.keyboard.press('Tab');
      if (await page.evaluate(sel => document.activeElement === document.querySelector(sel), selector)) return true;
    }
    return false;
  }

  // The disclosure caret is transitioned too, so the closed state must be read after the
  // rotation settles rather than on the frame the `<details>` flips.
  const caretStates = () => page.evaluate(async () => {
    const collapse = document.querySelector('.nav-collapse');
    const caret = collapse.querySelector('.nav-caret');
    const wasOpen = collapse.open;
    const open = getComputedStyle(caret).transform;
    collapse.open = false;
    const deadline = performance.now() + 900;
    let closed = getComputedStyle(caret).transform;
    while (closed === open && performance.now() < deadline) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      closed = getComputedStyle(caret).transform;
    }
    collapse.open = wasOpen;
    return {open, closed, durations: getComputedStyle(caret).transitionDuration
      .split(',').map(value => value.trim())};
  });

  await login(admin);

  // ---- the token set is the single source of timing and easing -------------------------
  const tokens = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return ['--motion-instant', '--motion-fast', '--motion-base', '--motion-enter',
      '--motion-dialog', '--motion-slow', '--ease-standard', '--ease-enter', '--ease-exit']
      .reduce((all, name) => ({...all, [name]: root.getPropertyValue(name).trim()}), {});
  });
  assert.equal(tokens['--motion-instant'], '80ms');
  assert.equal(tokens['--motion-fast'], '120ms');
  assert.equal(tokens['--motion-base'], '180ms');
  assert.equal(tokens['--motion-enter'], '220ms');
  assert.equal(tokens['--motion-dialog'], '260ms');
  assert.equal(tokens['--motion-slow'], '320ms');
  for (const name of ['--ease-standard', '--ease-enter', '--ease-exit']) {
    assert.ok(tokens[name].startsWith('cubic-bezier('), name + ' resolves to a curve');
  }

  // ---- Produksi first: the board's own controls ----------------------------------------
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Yang sedang dikerjakan.', exact: true}).waitFor();
  await page.locator('#summary dd').first().waitFor();

  const boardPress = await whilePressed(page.locator('#refresh'), async () => {
    const scale = await settledPressScale(page.locator('#refresh'));
    const style = await page.locator('#refresh').evaluate(el => {
      const computed = getComputedStyle(el);
      return {
        transform: computed.transform,
        durations: computed.transitionDuration.split(',').map(value => value.trim()),
        timing: computed.transitionTimingFunction,
      };
    });
    return {...style, scale};
  });
  assert.ok(isPressed(boardPress.scale), 'a pressed board control settles at a reduced scale');
  assert.equal(boardPress.transform, 'none',
    'press feedback uses the individual scale property, so a control\'s own transform is never overwritten');
  assert.ok(boardPress.durations.every(value => value === '0.12s' || value === '0.08s'),
    'every button transition duration comes from a motion token, not a raw value');
  assert.ok(boardPress.timing.includes('cubic-bezier(0.22, 1, 0.36, 1)'),
    'button transitions use the shared standard curve');

  // A disabled control must not look like it accepted the press.
  await page.locator('#refresh').evaluate(el => {el.disabled = true;});
  const disabled = await whilePressed(page.locator('#refresh'), () => scaleStaysUnpressed(page.locator('#refresh')));
  await page.locator('#refresh').evaluate(el => {el.disabled = false;});
  assert.equal(disabled.pressed, false, 'a disabled control does not animate a press it cannot accept');

  // The quiet variant shares the same grammar.
  const quietScale = await whilePressed(page.locator('#reset-board'), () => settledPressScale(page.locator('#reset-board')));
  assert.ok(isPressed(quietScale), 'the quiet control variant keeps the same press feedback');

  // ---- focus polish without delaying visibility ----------------------------------------
  assert.equal(await focusViaKeyboard('#refresh'), true, 'the board control is reachable by keyboard');
  const focus = await page.locator('#refresh').evaluate(el => {
    const style = getComputedStyle(el);
    return {
      outlineStyle: style.outlineStyle,
      outlineWidth: parseFloat(style.outlineWidth),
      radius: parseFloat(style.borderRadius),
      transitionProperty: style.transitionProperty,
    };
  });
  assert.notEqual(focus.outlineStyle, 'none', 'keyboard focus shows a ring');
  assert.ok(focus.outlineWidth > 0, 'the focus ring has real weight');
  assert.equal(focus.radius, 12, 'focus preserves the A1 control radius');
  assert.ok(!focus.transitionProperty.split(',').map(value => value.trim()).includes('outline'),
    'focus visibility never depends on a transition');

  // ---- then the shared controls --------------------------------------------------------
  const navScale = await whilePressed(page.locator('#board-home'), () => settledPressScale(page.locator('#board-home')));
  assert.ok(isPressed(navScale), 'the shared navigation control carries the same press feedback');

  const navCaret = await caretStates();
  assert.notEqual(navCaret.open, navCaret.closed, 'the disclosure caret still rotates between states');
  // M5: the caret is also an `.icon`, so it declares the rotation and the glyph colour together.
  // Every duration it declares still has to come from the token set.
  assert.deepEqual(navCaret.durations.filter(value => value !== '0.18s'), [],
    'every caret duration comes from the motion token set');

  // ---- no overflow at the 320px / 200% boundary while a control is pressed -------------
  await page.setViewportSize({width: 320, height: 900});
  await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
  const overflowWhilePressed = await whilePressed(page.locator('#refresh'), async () => {
    await settledPressScale(page.locator('#refresh'));
    return page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  });
  assert.equal(overflowWhilePressed, false, 'press feedback must not introduce document overflow at 320px/200%');
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});
  await page.setViewportSize({width: 1440, height: 1000});

  // ---- reduced motion is an explicit no-motion path, not a missing one -----------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  const reduced = await whilePressed(page.locator('#refresh'), async () => {
    const observed = await scaleStaysUnpressed(page.locator('#refresh'));
    const durations = await page.locator('#refresh').evaluate(el =>
      getComputedStyle(el).transitionDuration.split(',').map(value => value.trim()));
    return {...observed, durations};
  });
  assert.equal(reduced.pressed, false, 'reduced motion receives no press movement');
  assert.ok(reduced.durations.every(value => parseFloat(value) === 0),
    'reduced motion runs no transitions at all');

  // State must survive the loss of motion: the caret still reports open and closed, and it
  // gets there without a transition.
  const reducedCaret = await caretStates();
  assert.notEqual(reducedCaret.open, reducedCaret.closed,
    'reduced motion keeps every state change, just without movement');
  assert.deepEqual(reducedCaret.durations.filter(value => parseFloat(value) !== 0), [],
    'reduced motion resolves the caret state without a transition');

  await page.emulateMedia({reducedMotion: 'no-preference'});

  console.log('Motion foundation browser QA PASS: canonical tokens drive every control transition, '
    + 'press feedback scales without touching transform, disabled controls stay inert, focus is '
    + 'immediate and keeps the control\'s own radius, and reduced motion removes movement without '
    + 'removing state.');
};
