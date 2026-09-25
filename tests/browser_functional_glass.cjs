// A4: the optical material, measured as rendered pixels rather than as declared tokens.
//
// A declaration that says `backdrop-filter:blur(20px)` proves only that a string survived the
// parser. What this module asserts instead is what the engine actually painted: that the chrome is
// genuinely translucent, that the blur genuinely samples and smooths what is behind it, that the
// translucency is bounded tightly enough for every label on it to stay readable, and that the solid
// A1 baseline is exactly what comes back when the enhancement is withdrawn.
//
// It is also a regression barrier for A3: the spring, its velocity continuity, its exact settling
// and its zero idle cost all have to survive a lens that is now a filtered surface.
//
// Nothing here branches on a browser name. The one capability test is whether the engine supports
// backdrop filtering at all; an engine that does not is checked against the solid contract instead
// of being failed for a feature it never claimed.
const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, admin, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  await login(admin);
  await page.emulateMedia({reducedMotion: 'no-preference', forcedColors: 'none'});

  // Frame accounting, installed the way the A2/A3 modules install it: wrap the real pair before any
  // measurement so the idle assertions below include ordinary application frame work, and close
  // over the counter so releasing the global handle cannot break a pending callback.
  await page.evaluate(() => {
    window.originalLens = document.getElementById('nav-selection-lens');
    const raf = window.requestAnimationFrame, cancel = window.cancelAnimationFrame;
    const pending = new Set();
    const frames = {executed: 0, pending, raf, cancel};
    window.glassFrames = frames;
    window.requestAnimationFrame = callback => {
      const id = raf.call(window, time => { pending.delete(id); frames.executed++; callback(time); });
      pending.add(id); return id;
    };
    window.cancelAnimationFrame = id => { pending.delete(id); cancel.call(window, id); };
  });

  // ---- rendered-pixel sampling ---------------------------------------------------------------
  // An element screenshot is decoded inside the page, so a sample is the composited result of the
  // backdrop filter, the translucent tint, the border and everything painted underneath. Element
  // coordinates avoid every ambiguity about whether a clip is viewport- or document-relative.
  const surfaceOf = async selector => {
    const shot = (await page.locator(selector).screenshot()).toString('base64');
    const data = await page.evaluate(async encoded => {
      const blob = await (await fetch('data:image/png;base64,' + encoded)).blob();
      const bitmap = await createImageBitmap(blob);
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      canvas.getContext('2d').drawImage(bitmap, 0, 0);
      const pixels = canvas.getContext('2d').getImageData(0, 0, bitmap.width, bitmap.height);
      return {width: bitmap.width, height: bitmap.height, data: [...pixels.data]};
    }, shot);
    const ratio = data.width / (await page.locator(selector).evaluate(node => node.getBoundingClientRect().width));
    return {
      ...data,
      // CSS pixels in, device pixels out, so a sample point stays where the layout put it.
      at(x, y) {
        const px = Math.min(data.width - 1, Math.max(0, Math.round(x * ratio)));
        const py = Math.min(data.height - 1, Math.max(0, Math.round(y * ratio)));
        const index = (py * data.width + px) * 4;
        return [data.data[index], data.data[index + 1], data.data[index + 2]];
      },
    };
  };
  const luminance = ([r, g, b]) => [r, g, b].map(v => v / 255)
    .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
    .reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
  const contrast = (a, b) => {
    const [bright, dim] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (bright + .05) / (dim + .05);
  };
  const rgb = value => value.match(/[\d.]+/g).slice(0, 3).map(Number);
  const distance = (a, b) => Math.max(...[0, 1, 2].map(i => Math.abs(a[i] - b[i])));

  const optics = selector => page.locator(selector).evaluate(node => {
    const computed = getComputedStyle(node);
    const body = node.classList.contains('nav-selection-lens') ? getComputedStyle(node,'::before') : null;
    const paint = body && body.content !== 'none' && body.display !== 'none' ? body : computed;
    const filter = computed.backdropFilter && computed.backdropFilter !== 'none'
      ? computed.backdropFilter : computed.webkitBackdropFilter || 'none';
    const alpha = paint.backgroundColor.match(/[\d.]+/g);
    return {filter, background: paint.backgroundColor, boxShadow: paint.boxShadow,
      borderTopWidth: computed.borderTopWidth, borderTopColor: computed.borderTopColor,
      alpha: alpha && alpha.length > 3 ? Number(alpha[3]) : 1,
      transition: computed.transitionProperty, duration: computed.transitionDuration,
      animation: computed.animationName};
  });
  const tokenColor = token => page.evaluate(name => {
    const probe = document.createElement('span');
    probe.style.color = getComputedStyle(document.documentElement).getPropertyValue(name);
    document.body.append(probe);
    const value = getComputedStyle(probe).color; probe.remove(); return value;
  }, token);

  const settle = () => page.waitForFunction(() => !document.querySelector('.motion-enter,.is-theming')
    && document.getAnimations().every(animation => animation.animationName === 'sidebar-specular' || animation.playState === 'finished'));
  const resting = id => page.waitForFunction(id => {
    const lens = document.getElementById('nav-selection-lens'), target = document.getElementById(id);
    if (lens.hidden || target.getAttribute('aria-current') !== 'page') return false;
    if (getComputedStyle(lens).willChange !== 'auto') return false;
    const a = lens.getBoundingClientRect(), b = target.getBoundingClientRect();
    return ['x', 'y', 'width', 'height'].every(key => Math.abs(a[key] - b[key]) < 1);
  }, id);
  const open = async id => {
    if (!await page.locator('#app-sidebar').isVisible()) await page.locator('#menu-toggle').click();
    await page.locator('#' + id).click();
    if (!await page.locator('#app-sidebar').isVisible()) await page.locator('#menu-toggle').click();
    await page.locator('#' + id).scrollIntoViewIfNeeded();
    await resting(id);
    await settle();
  };
  const useTheme = async theme => {
    if (await page.locator('html').getAttribute('data-theme') !== theme) await page.locator('#theme').click();
    await settle();
  };

  const supported = await page.evaluate(() => CSS.supports('backdrop-filter', 'blur(1px)')
    || CSS.supports('-webkit-backdrop-filter', 'blur(1px)'));
  console.log(`A4 glass: engine backdrop filtering ${supported ? 'supported' : 'unavailable'}.`);

  // ---- the solid baseline is never conditional ------------------------------------------------
  // Whatever this engine supports, the unenhanced declarations have to be present and usable. This
  // is read out of the parsed stylesheet, so it is the browser's own view of the cascade: the plain
  // `.masthead` / `.app-sidebar` / `.nav-selection-lens` rules that sit outside any @supports or
  // preference query must still carry the A1 solid materials.
  const baseline = await page.evaluate(() => {
    const out = {};
    // Nesting-aware: a CSSStyleRule also exposes an (empty) cssRules list, so selectors are read
    // first and only genuine grouping rules are recursed into.
    const visit = (rules, guarded) => {
      for (const rule of rules) {
        for (const selector of (rule.selectorText || '').split(',').map(s => s.trim())) {
          if (!['.masthead', '.app-sidebar', '.nav-selection-lens'].includes(selector)) continue;
          out[selector] = out[selector] || {unguarded: [], guarded: []};
          out[selector][guarded ? 'guarded' : 'unguarded'].push(rule.style.cssText);
        }
        if (rule.cssRules && rule.cssRules.length) {
          visit(rule.cssRules, guarded || rule.conditionText !== undefined);
        }
      }
    };
    for (const sheet of document.styleSheets) { try { visit(sheet.cssRules, false); } catch { /* same-origin only */ } }
    return out;
  });
  for (const selector of ['.masthead', '.app-sidebar']) {
    const unguarded = baseline[selector].unguarded.join(' ');
    assert.ok(unguarded.includes('var(--material-functional-chrome-solid)'),
      `${selector} declares the A1 solid chrome material outside every conditional group`);
    assert.ok(!/backdrop-filter/.test(unguarded), `${selector} has no unconditional backdrop filter`);
  }
  assert.ok(baseline['.nav-selection-lens'].unguarded.join(' ').includes('var(--color-accent-soft)'),
    'the lens declares its solid accent-soft fallback unconditionally');
  assert.ok(!/backdrop-filter/.test(baseline['.nav-selection-lens'].unguarded.join(' ')),
    'the lens has no unconditional backdrop filter');
  if (supported) {
    for (const selector of ['.masthead', '.app-sidebar']) {
      assert.ok(baseline[selector].guarded.some(text => /backdrop-filter/.test(text)),
        `${selector} receives its optical treatment only inside a conditional group`);
    }
    // The lens is translucent inside the gate too, just not filtered there.
    assert.ok(baseline['.nav-selection-lens'].guarded.some(text => /--lens-glass-tint/.test(text)),
      'the lens receives its translucent tint only inside a conditional group');
    // Only a *withdrawal* may mention the property here: the reduced-transparency and forced-colors
    // groups set it to none on this selector, which is exactly what they should do.
    assert.ok(!baseline['.nav-selection-lens'].guarded.some(text => /backdrop-filter:[^;]*blur/.test(text)),
      'and adds no nested blur inside the filtered sidebar');
  }

  // Both spellings are present, and the engine kept the reduced-transparency query it was given —
  // read from the parsed stylesheet rather than from the file, so this is the browser agreeing that
  // the fallback exists rather than a substring match on source text.
  const gates = await page.evaluate(() => {
    const found = {supports: [], reducedTransparency: [], forcedColors: []};
    const visit = rules => {
      for (const rule of rules) {
        if (rule.conditionText && rule.cssRules) {
          const text = rule.conditionText;
          if (/backdrop-filter/.test(text)) found.supports.push(text);
          if (/prefers-reduced-transparency/.test(text)) found.reducedTransparency.push(rule.cssText.slice(0, 4000));
          if (/forced-colors/.test(text)) found.forcedColors.push(rule.cssText.slice(0, 4000));
        }
        if (rule.cssRules && rule.cssRules.length) visit(rule.cssRules);
      }
    };
    for (const sheet of document.styleSheets) { try { visit(sheet.cssRules); } catch { /* ignore */ } }
    return found;
  });
  // A6.0 added `workspace-primitives.css`, which owns the inner-workspace content language and
  // brings its own optical layer for exactly one surface — the command bar — with its own
  // reduced-transparency withdrawal and its own forced-colors contract. These three counts are
  // therefore an inventory of owners, and A6.0 is the second one. Everything that makes the A4
  // boundary a boundary is unchanged and still asserted below and above: the chrome gate still
  // names both spellings, the lens still gains no nested blur, content surfaces are still never
  // filtered, and every withdrawal still only ever restores a solid material. The stylesheet
  // order in index.html is style.css, workspace.css, workspace-primitives.css, so the A6 entries
  // append last and the indexed assertions below still address the sheets they were written for.
  const positive = gates.supports.filter(text => !text.startsWith('not '));
  assert.equal(positive.length, 2, 'two positive feature gates: A4 chrome and A6.0 command bar');
  assert.equal(gates.supports.filter(text=>text.startsWith('not ')).length, 2, 'workspace and liquid pseudo-elements have explicit solid fallbacks');
  for (const gate of positive) {
    assert.ok(/\bbackdrop-filter\b/.test(gate) && /-webkit-backdrop-filter/.test(gate),
      `every gate tests both the standard and the -webkit property: ${gate}`);
  }
  assert.ok(/\bbackdrop-filter\b/.test(gates.supports[0]) && /-webkit-backdrop-filter/.test(gates.supports[0]),
    `the gate tests both the standard and the -webkit property: ${gates.supports[0]}`);
  assert.equal(gates.reducedTransparency.length, 4, 'A4 material, A5.2 workspace, A5.3 optics and A6.0 workspace primitives reduced-transparency fallbacks exist');
  assert.ok(gates.reducedTransparency[0].includes('var(--material-functional-chrome-solid)'),
    'the reduced-transparency fallback restores the A1 solid chrome');
  assert.ok(gates.reducedTransparency[2].includes('--liquid-fill: var(--color-accent-soft)'),
    'the additional fallback supplies the liquid body with the solid selection material');
  // A6.0's withdrawal returns dense data surfaces to the opaque A1 material and never re-enables
  // translucency, which is the one property that makes a fallback a fallback. The A6 group is
  // located by content rather than by index: the indexed assertions above are historical, and a
  // fourth owner should not have to guess its own position in a traversal.
  const a6Transparency = gates.reducedTransparency.find(text => /\.data-surface/.test(text));
  assert.ok(a6Transparency, 'the A6.0 reduced-transparency withdrawal is present');
  assert.ok(a6Transparency.includes('var(--material-content)'),
    'the A6.0 fallback returns workspace data surfaces to an opaque material');
  assert.ok(!/backdrop-filter:\s*blur/.test(a6Transparency),
    'the A6.0 fallback withdraws the filter rather than declaring one');
  assert.equal(gates.forcedColors.length, 4, 'A4 material, A5.2 workspace, A5.3 optics and A6.0 workspace primitives forced-colors contracts exist');
  assert.ok(/backdrop-filter:\s*none/.test(gates.forcedColors[0]),
    'the forced-colors contract disables backdrop filtering');
  assert.ok(/nav-selection-lens::before/.test(gates.forcedColors[2]) && /display:\s*none/.test(gates.forcedColors[2]),
    'the additional forced-colors contract hides the liquid pseudo-elements');
  // A6.0's contract must not lean on a background colour: the status dot is its non-colour channel.
  // System colour keywords are matched case-insensitively because `cssText` serialisation
  // lowercases them — the stylesheet says `CanvasText`, the engine reports `canvastext`.
  const a6Forced = gates.forcedColors.find(text => /\.status-chip/.test(text));
  assert.ok(a6Forced, `the A6.0 forced-colors contract is present: ${gates.forcedColors.map(t => t.slice(0, 60))}`);
  assert.ok(/\.status-dot\s*\{[^}]*background:\s*canvastext/i.test(a6Forced),
    'the A6.0 forced-colors contract keeps a non-colour channel for status');
  assert.ok(/\.progress-fill\s*\{[^}]*background:\s*highlight/i.test(a6Forced),
    'the A6.0 forced-colors contract gives progress a system fill');
  assert.ok(/\.progress-track\s*\{[^}]*border:\s*1px solid canvastext/i.test(a6Forced),
    'the A6.0 forced-colors contract outlines the progress track');

  // One bounded background sheet softens the A5.2 landscape; business cards, tables and dialogs
  // retain the A4 boundary against per-surface filtering.
  await open('command-center');
  await page.locator('#command-center-content:not([hidden])').waitFor();
  const contentSurfaces = await page.evaluate(() => {
    const seen = [];
    for (const node of document.querySelectorAll(
      '.workspace-main *, dialog, .notice, .state, .card, .hero-panel, .summary, table, .sidebar-cta')) {
      const computed = getComputedStyle(node);
      const filter = [computed.backdropFilter, computed.webkitBackdropFilter].filter(v => v && v !== 'none');
      const blur = /blur\(/.test(computed.filter || '') ? computed.filter : null;
      if (filter.length || blur) {
        seen.push({tag: node.tagName, cls: node.className && String(node.className).slice(0, 60), filter, blur});
      }
    }
    return seen;
  });
  assert.deepEqual(contentSurfaces, [], 'no business card, table or dialog surface is filtered');
  const sceneFilter = await page.locator('.workspace-main').evaluate(node=>getComputedStyle(node).backdropFilter);
  if(supported) assert.ok(Number(sceneFilter.match(/blur\(([\d.]+)px\)/)?.[1]) <= 16, 'one bounded scene filter');

  // ---- A + B: masthead and sidebar ------------------------------------------------------------
  const measurements = [];
  for (const theme of ['light', 'dark']) {
    await useTheme(theme);
    await open('command-center');
    await page.locator('#command-center-content:not([hidden])').waitFor();
    const chrome = await optics('.masthead');
    const rail = await optics('#app-sidebar');
    const solidChrome = await tokenColor('--material-functional-chrome-solid');
    const canvas = await page.locator('.workspace-main').evaluate(node => getComputedStyle(node).backgroundColor);

    if (!supported) {
      // The documented fallback, asserted rather than skipped.
      for (const [name, surface] of [['masthead', chrome], ['sidebar', rail]]) {
        assert.equal(surface.filter, 'none', `${theme} ${name} has no filter without engine support`);
        assert.equal(surface.background, solidChrome, `${theme} ${name} uses the A1 solid chrome`);
      }
    } else {
      for (const [name, surface] of [['masthead', chrome], ['sidebar', rail]]) {
        assert.match(surface.filter, /blur\(/, `${theme} ${name} blurs its backdrop`);
        assert.match(surface.filter, /saturate\(/, `${theme} ${name} saturates its backdrop`);
        const radius = Number(surface.filter.match(/blur\(([\d.]+)px\)/)[1]);
        const saturation = Number(surface.filter.match(/saturate\(([\d.]+)\)/)[1]);
        assert.ok(radius >= 12 && radius <= 28, `${theme} ${name} blur ${radius}px stays in the bounded band`);
        assert.ok(saturation > 1 && saturation <= 1.6, `${theme} ${name} saturation ${saturation} stays restrained`);
        assert.ok(surface.alpha > 0 && surface.alpha < 1,
          `${theme} ${name} is translucent, not opaque (alpha ${surface.alpha})`);
        assert.notEqual(surface.background, solidChrome, `${theme} ${name} is no longer the solid material`);
        assert.equal(surface.animation, 'none', `${theme} ${name} runs no optical animation`);
        assert.ok(!/backdrop-filter/.test(surface.transition),
          `${theme} ${name} never transitions its blur radius`);
      }
      assert.ok(rail.boxShadow !== 'none', `${theme} sidebar carries its optical highlight`);
      assert.ok(chrome.boxShadow.includes('inset'), `${theme} masthead carries an inset specular highlight`);
    }
    // The hierarchy has to survive the material either way: chrome and content must not merge.
    const mastheadPixel = (await surfaceOf('.masthead')).at(700, 36);
    const canvasPixel = rgb(canvas);
    assert.ok(distance(mastheadPixel, canvasPixel) >= 2,
      `${theme} chrome stays visually distinct from the content canvas`
      + ` (${mastheadPixel} vs ${canvasPixel})`);
    measurements.push({theme, masthead: chrome.background, mastheadPixel, filter: chrome.filter,
      sidebar: rail.background, canvas});
  }

  // ---- the blur is real, and its translucency is bounded --------------------------------------
  // Two claims that a computed style cannot make. A high-frequency stripe pattern is placed behind
  // the sticky masthead: if the backdrop is genuinely blurred, neighbouring samples across those
  // stripes come out nearly identical, and the same samples diverge once the filter is removed.
  // The same probe then uses the most saturated colour the product itself paints to check that the
  // tint still holds every masthead label above 4.5:1.
  if (supported) {
    await useTheme('light');
    await open('command-center');
    const accent = await tokenColor('--color-accent');
    await page.evaluate(colour => {
      const probe = document.createElement('div');
      probe.id = 'a4-backdrop-probe';
      probe.style.cssText = 'position:fixed;inset:0 0 auto 0;height:140px;z-index:1;pointer-events:none;'
        + `background:repeating-linear-gradient(90deg,${colour} 0 3px,#ffffff 3px 6px)`;
      document.body.append(probe);
    }, accent);
    await page.waitForTimeout(150);
    const blurred = await surfaceOf('.masthead');
    const blurredRun = [0, 1, 2, 3, 4, 5].map(step => blurred.at(700 + step, 36));
    const blurredSpread = Math.max(...blurredRun.map(luminance)) - Math.min(...blurredRun.map(luminance));

    await page.locator('.masthead').evaluate(node => {
      node.dataset.a4Filter = getComputedStyle(node).backdropFilter;
      node.style.backdropFilter = 'none'; node.style.webkitBackdropFilter = 'none';
    });
    await page.waitForTimeout(150);
    const unblurred = await surfaceOf('.masthead');
    const unblurredRun = [0, 1, 2, 3, 4, 5].map(step => unblurred.at(700 + step, 36));
    const unblurredSpread = Math.max(...unblurredRun.map(luminance)) - Math.min(...unblurredRun.map(luminance));
    await page.locator('.masthead').evaluate(node => {
      node.style.backdropFilter = ''; node.style.webkitBackdropFilter = ''; delete node.dataset.a4Filter;
    });
    await page.waitForTimeout(150);

    console.log(`A4 blur proof: spread across a 3px stripe pattern ${blurredSpread.toFixed(4)} filtered`
      + ` vs ${unblurredSpread.toFixed(4)} unfiltered.`);
    assert.ok(unblurredSpread > blurredSpread * 3 && unblurredSpread > .01,
      `removing the filter must make the stripe pattern legible through the chrome`
      + ` (filtered ${blurredSpread.toFixed(4)}, unfiltered ${unblurredSpread.toFixed(4)})`);
    assert.ok(blurredSpread < .01, `the filtered chrome smooths the pattern (${blurredSpread.toFixed(4)})`);

    // Bounded translucency: the label that sits directly on the glass with the least headroom.
    const labels = await page.evaluate(() => ({
      account: getComputedStyle(document.getElementById('account-name')).color,
      brand: getComputedStyle(document.querySelector('.brand-word')).color,
    }));
    const worst = blurredRun.reduce((a, b) => luminance(a) < luminance(b) ? a : b);
    const accountContrast = contrast(rgb(labels.account), worst);
    console.log(`A4 bounded translucency: worst masthead pixel ${worst} over a full-width accent`
      + ` pattern keeps the account label at ${accountContrast.toFixed(2)}:1`
      + ` and the brand at ${contrast(rgb(labels.brand), worst).toFixed(2)}:1.`);
    assert.ok(accountContrast >= 4.5,
      `the chrome tint keeps its quietest label readable over the most saturated content the product`
      + ` paints (${accountContrast.toFixed(2)}:1 on ${worst})`);
    assert.ok(contrast(rgb(labels.brand), worst) >= 4.5, 'the brand label stays readable too');
    await page.evaluate(() => document.getElementById('a4-backdrop-probe')?.remove());
    await page.waitForTimeout(100);
  }

  // ---- C + D: the lens, in the navigation column and in the approval card ---------------------
  const lensReadings = [];
  for (const theme of ['light', 'dark']) {
    await useTheme(theme);
    for (const id of ['command-center', 'capacity-plan', 'approvals']) {
      await open(id);
      if (id === 'approvals') await page.locator('#approval-list').waitFor();
      await open(id);
      const lens = await optics('#nav-selection-lens');
      const inCta = await page.evaluate(() => document.getElementById('nav-selection-lens')
        .parentElement.classList.contains('sidebar-cta'));
      assert.equal(inCta, id === 'approvals', `${id} uses the expected positioning context`);
      // Appearance is state, never travel: the surface that moves under physics must not also be
      // interpolating its own material.
      assert.equal(lens.duration, '0s', `${theme} ${id} lens has no transition`);
      assert.equal(lens.animation, 'none', `${theme} ${id} lens has no animation`);
      const solidLens = await tokenColor('--color-accent-soft');
      if (!supported) {
        assert.equal(lens.filter, 'none', `${theme} ${id} lens is unfiltered without engine support`);
        assert.equal(lens.background, solidLens, `${theme} ${id} lens keeps the solid accent-soft fill`);
      } else {
        // Translucent in both contexts, filtered only in the approval card. In the navigation
        // column the lens sits inside the filtered sidebar, which is a backdrop root: a filter
        // there would sample that root's flat tint, show no blur, and force the whole column to be
        // re-sampled on every frame the lens moves — measurably dropping a frame per travel and
        // collapsing A3's velocity-continuity measurement. One blurred surface per column.
        assert.ok(lens.alpha > 0 && lens.alpha < 1, `${theme} ${id} lens is translucent (alpha ${lens.alpha})`);
        assert.ok(lens.boxShadow.includes('inset'), `${theme} ${id} lens carries a specular highlight`);
        if (inCta) {
          assert.match(lens.filter, /blur\(/, `${theme} ${id} lens blurs the CTA gradient beneath it`);
          const radius = Number(lens.filter.match(/blur\(([\d.]+)px\)/)[1]);
          assert.ok(radius >= 8 && radius <= 18,
            `${theme} ${id} lens keeps the smaller moving-surface blur budget (${radius}px)`);
          assert.ok(radius < Number((await optics('#app-sidebar')).filter.match(/blur\(([\d.]+)px\)/)[1]),
            'the moving lens blurs less than the static chrome it rides on');
        } else {
          assert.equal(lens.filter, 'none',
            `${theme} ${id} lens adds no nested blur inside the filtered sidebar`);
        }
      }
      // Readability and separation, from pixels: the selected label over the lens as painted, and
      // the lens itself distinguishable from both the hover affordance and the chrome behind it.
      const box = await page.locator('#nav-selection-lens').boundingBox();
      const lensPixel = (await surfaceOf('#nav-selection-lens')).at(4, box.height / 2);
      const railPixel = (await surfaceOf('#app-sidebar')).at(6, 300);
      const selected = await page.locator('#' + id).evaluate(node => getComputedStyle(node).color);
      const ratio = contrast(rgb(selected), lensPixel);
      assert.ok(ratio >= 4.5, `${theme} ${id} selected label is ${ratio.toFixed(2)}:1 on the painted lens`);
      if (id !== 'approvals') {
        assert.ok(distance(lensPixel, railPixel) >= 6,
          `${theme} ${id} lens is distinguishable from the chrome material (${lensPixel} vs ${railPixel})`);
      }
      lensReadings.push({theme, id, filter: lens.filter, background: lens.background,
        pixel: lensPixel, selected, contrast: Number(ratio.toFixed(3))});
    }
    // Hover must stay a local affordance rather than a second selection surface.
    await open('command-center');
    await page.locator('#materials').hover();
    await page.waitForTimeout(150);
    const hoverPixel = (await surfaceOf('#materials')).at(6, 20);
    const selectedPixel = (await surfaceOf('#nav-selection-lens'))
      .at(4, (await page.locator('#nav-selection-lens').boundingBox()).height / 2);
    assert.ok(distance(hoverPixel, selectedPixel) >= 6,
      `${theme} hover stays distinct from the selected lens (${hoverPixel} vs ${selectedPixel})`);
    await page.mouse.move(0, 0);
  }
  await useTheme('light');
  console.log('A4 lens readings ' + JSON.stringify(lensReadings.map(r =>
    [`${r.id}/${r.theme}`, r.contrast])));

  // ---- E: one lens, same node, across all three contexts --------------------------------------
  for (const id of ['marketing-budgets', 'approvals', 'command-center']) {
    await open(id);
    if (id === 'approvals') await page.locator('#approval-list').waitFor();
    await open(id);
    assert.equal(await page.locator('.nav-selection-lens').count(), 1, `${id}: exactly one lens node exists`);
    assert.equal(await page.evaluate(() => window.originalLens === document.getElementById('nav-selection-lens')),
      true, `${id}: the original lens node survived`);
    assert.equal(await page.locator('#app-sidebar [aria-current]').count(), 1, `${id}: one selected destination`);
    assert.deepEqual(await page.locator('#nav-selection-lens').evaluate(node => ({
      hidden: node.getAttribute('aria-hidden'), tab: node.tabIndex, text: node.textContent,
      pointer: getComputedStyle(node).pointerEvents, children: node.childElementCount,
      beforePointer: getComputedStyle(node, '::before').pointerEvents,
      afterPointer: getComputedStyle(node, '::after').pointerEvents,
    })), {hidden: 'true', tab: -1, text: '', pointer: 'none', children: 0,
      beforePointer: 'none', afterPointer: 'none'},
      `${id}: the lens stays empty, inert and non-focusable, pseudo-elements included`);
  }

  // ---- F + G + H: the A3 spring still behaves, with glass on ----------------------------------
  await open('command-center');
  await page.locator('#app-sidebar').evaluate(node => { node.scrollTop = 0; });
  // Sampling starts when the controller actually promotes the lens, not on the frame the click
  // happened: the measurement frame is coalesced, so the first frame after a click is still at the
  // old destination and carries no compositor hint yet.
  const travel = await page.evaluate(() => new Promise(resolve => {
    const lens = document.getElementById('nav-selection-lens');
    const frames = [];
    let started = false, ticks = 0;
    const moving = () => getComputedStyle(lens).willChange !== 'auto';
    document.getElementById('products').click();
    const tick = () => {
      ticks++;
      const inFlight = moving();
      if (inFlight) started = true;
      if (started) { const box = lens.getBoundingClientRect(); frames.push({y: box.y, h: box.height}); }
      if (ticks < 150 && (!started || inFlight)) requestAnimationFrame(tick);
      else resolve({frames, ticks, willChange: getComputedStyle(lens).willChange});
    };
    requestAnimationFrame(tick);
  }));
  const positions = new Set(travel.frames.map(frame => Math.round(frame.y * 10)));
  assert.ok(positions.size >= 5,
    `the spring still renders intermediate frames with glass on (${positions.size} distinct positions`
    + ` across ${travel.frames.length} promoted frames, ${travel.ticks} ticks)`);
  assert.ok(travel.frames.every(frame => Number.isFinite(frame.y) && frame.h > 0),
    'no frame writes a non-finite or collapsed geometry');
  await resting('products');
  assert.equal(travel.willChange, 'auto', 'a settled lens released its compositor hint');
  const settledBox = await page.evaluate(() => {
    const a = document.getElementById('nav-selection-lens').getBoundingClientRect();
    const b = document.getElementById('products').getBoundingClientRect();
    return ['x', 'y', 'width', 'height'].map(key => Math.abs(a[key] - b[key]));
  });
  assert.ok(settledBox.every(delta => delta < .05), `the lens settles exactly (${settledBox})`);

  // Rapid retarget: the latest destination still wins and nothing is left pending.
  const rapid = await page.evaluate(async () => {
    const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
    for (const id of ['board-home', 'workforce', 'capacity-plan', 'command-center']) {
      document.getElementById(id).click();
      await frame(); await frame(); await frame();
    }
    return [...document.querySelectorAll('#app-sidebar [aria-current]')].map(node => node.id);
  });
  assert.deepEqual(rapid, ['command-center'], 'rapid retarget ends on the final destination');
  await resting('command-center');
  await settle();
  assert.equal(await page.locator('.nav-selection-lens').count(), 1, 'rapid retarget created no second lens');

  // Idle: a settled filtered lens still costs nothing per frame.
  const before = await page.evaluate(() => ({executed: window.glassFrames.executed,
    pending: window.glassFrames.pending.size}));
  await page.waitForTimeout(500);
  assert.deepEqual(await page.evaluate(() => ({executed: window.glassFrames.executed,
    pending: window.glassFrames.pending.size})), before,
    'a settled glass lens performs zero frame work');
  assert.equal(before.pending, 0, 'no frame is left pending');

  // ---- I: reduced motion keeps the material and removes only the travel ----------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  await open('command-center');
  await page.locator('#app-sidebar').evaluate(node => { node.scrollTop = 0; });
  const reduced = await page.evaluate(() => new Promise(resolve => {
    const lens = document.getElementById('nav-selection-lens');
    document.getElementById('workforce').click();
    requestAnimationFrame(() => {
      const first = lens.getBoundingClientRect();
      requestAnimationFrame(() => {
        const second = lens.getBoundingClientRect();
        const computed = getComputedStyle(lens);
        resolve({
          moved: Math.abs(second.y - first.y),
          onTarget: Math.abs(first.y - document.getElementById('workforce').getBoundingClientRect().y),
          hidden: lens.hidden, first: first.y,
          target: document.getElementById('workforce').getBoundingClientRect().y,
          filter: computed.backdropFilter && computed.backdropFilter !== 'none'
            ? computed.backdropFilter : computed.webkitBackdropFilter || 'none',
          background: computed.backgroundColor, willChange: computed.willChange,
        });
      });
    });
  }));
  assert.ok(reduced.onTarget < 1,
    `reduced motion places the lens on its target immediately (${JSON.stringify(reduced)})`);
  assert.equal(reduced.moved, 0, 'reduced motion produces no travel at all');
  assert.equal(reduced.willChange, 'auto', 'reduced motion never requests compositor promotion');
  if (supported) {
    assert.ok(reduced.background.startsWith('rgba('),
      'reduced motion keeps the material: transparency and motion are separate preferences');
    assert.match(await page.locator('.masthead').evaluate(node => getComputedStyle(node).backdropFilter),
      /blur\(/, 'and the chrome is still filtered under reduced motion');
  }
  const idleReduced = await page.evaluate(() => ({executed: window.glassFrames.executed,
    pending: window.glassFrames.pending.size}));
  await page.waitForTimeout(400);
  assert.deepEqual(await page.evaluate(() => ({executed: window.glassFrames.executed,
    pending: window.glassFrames.pending.size})), idleReduced, 'reduced motion also idles at zero frames');
  await page.emulateMedia({reducedMotion: 'no-preference'});

  // ---- reduced transparency: the solid material comes back ------------------------------------
  // Emulated through the devtools protocol where the harness exposes it, because the preference has
  // no scripted equivalent. The structural guarantee above does not depend on this being available.
  // Only the *setup* may be tolerated. An assertion failure inside a catch would report itself as
  // "not emulable" and let the module pass, which would make this the one check here that cannot
  // fail; and leaving the emulation on would silently push every later assertion in this module —
  // the drawer material, forced colours, the screenshots — into reduced-transparency mode. So the
  // capability probe is caught, the assertions are not, and the emulation is always handed back.
  let reducedTransparencyChecked = false;
  let session = null;
  try {
    session = await page.context().newCDPSession(page);
    await session.send('Emulation.setEmulatedMedia',
      {features: [{name: 'prefers-reduced-transparency', value: 'reduce'}]});
  } catch (error) {
    session = null;
    console.log('A4 reduced-transparency behaviour not emulable here; structural contract asserted '
      + 'instead: ' + error.message);
  }
  if (session) {
    try {
      await page.waitForTimeout(150);
      const solidChrome = await tokenColor('--material-functional-chrome-solid');
      const solidLens = await tokenColor('--color-accent-soft');
      for (const [name, selector] of [['masthead', '.masthead'], ['sidebar', '#app-sidebar']]) {
        const surface = await optics(selector);
        assert.equal(surface.filter, 'none', `reduced transparency removes the ${name} filter`);
        assert.equal(surface.background, solidChrome, `reduced transparency restores the ${name} solid material`);
        assert.equal(surface.boxShadow, 'none', `reduced transparency drops the ${name} optical shadow`);
      }
      const lens = await optics('#nav-selection-lens');
      assert.equal(lens.filter, 'none', 'reduced transparency removes the lens filter');
      assert.equal(lens.background, solidLens, 'reduced transparency restores the solid selection fill');
      reducedTransparencyChecked = true;
    } finally {
      await session.send('Emulation.setEmulatedMedia', {features: []}).catch(() => {});
      await session.detach().catch(() => {});
      await page.waitForTimeout(150);
    }
  }
  await page.emulateMedia({reducedMotion: 'no-preference', forcedColors: 'none'});
  await useTheme('light');

  // ---- K: mobile drawer keeps its material and its lifecycle ----------------------------------
  await page.setViewportSize({width: 390, height: 844});
  await page.locator('#menu-toggle').click();
  assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'true');
  assert.equal(await page.locator('#app-sidebar').evaluate(node => node.inert), false);
  await open('materials');
  if (supported) {
    const drawer = await optics('#app-sidebar');
    assert.match(drawer.filter, /blur\(/, 'the visible drawer carries the same material family');
    assert.ok(drawer.alpha < 1, 'the visible drawer is translucent');
    assert.ok(drawer.boxShadow.includes('inset'), 'the drawer keeps an optical edge');
  }
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.getElementById('app-sidebar').checkVisibility());
  assert.equal(await page.locator('#app-sidebar').isVisible(), false, 'the closed drawer paints nothing');
  assert.equal(await page.locator('#app-sidebar').evaluate(node => node.inert), true);
  assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'), 'false');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'menu-toggle',
    'drawer focus restoration is unchanged');
  await page.setViewportSize({width: 1440, height: 1000});
  await settle();

  // ---- L: forced colours -----------------------------------------------------------------------
  await page.emulateMedia({forcedColors: 'active'});
  await open('capacity-plan');
  const forced = await page.evaluate(() => {
    const read = node => {
      const computed = getComputedStyle(node);
      return {filter: computed.backdropFilter, webkit: computed.webkitBackdropFilter,
        shadow: computed.boxShadow, borderWidth: computed.borderTopWidth};
    };
    const selected = document.querySelector('#app-sidebar [aria-current="page"]');
    return {masthead: read(document.querySelector('.masthead')),
      sidebar: read(document.getElementById('app-sidebar')),
      lens: read(document.getElementById('nav-selection-lens')),
      current: selected?.getAttribute('aria-current'), selectedId: selected?.id};
  });
  for (const [name, surface] of Object.entries(forced).filter(([key]) => key !== 'current' && key !== 'selectedId')) {
    assert.ok(!surface.filter || surface.filter === 'none', `forced colours disable the ${name} filter`);
    assert.ok(!surface.webkit || surface.webkit === 'none', `forced colours disable the ${name} -webkit filter`);
    assert.equal(surface.shadow, 'none', `forced colours drop the ${name} decorative shadow`);
  }
  assert.equal(forced.lens.borderWidth, '2px', 'the selection survives forced colours as a visible outline');
  assert.equal(forced.current, 'page', 'aria-current is unaffected by forced colours');
  assert.equal(forced.selectedId, 'capacity-plan');
  // Keyboard-driven focus, so `:focus-visible` genuinely matches rather than relying on a
  // programmatic focus the engine is free to treat as invisible. Tab also avoids activating a
  // destination, so the selected state under test does not move.
  await page.locator('#products').focus();
  await page.keyboard.press('Tab');
  const focusRing = await page.evaluate(() => {
    const active = document.activeElement;
    const computed = getComputedStyle(active);
    return {id: active.id, inSidebar: document.getElementById('app-sidebar').contains(active),
      style: computed.outlineStyle, width: computed.outlineWidth};
  });
  assert.equal(focusRing.inSidebar, true, 'Tab keeps keyboard focus inside the navigation');
  assert.equal(focusRing.style, 'solid',
    `the focus ring stays visible in forced colours (${JSON.stringify(focusRing)})`);
  await page.locator('#app-sidebar').evaluate(node => { node.scrollTop = 0; });
  await page.emulateMedia({forcedColors: 'none'});
  await settle();

  // ---- J: review screenshots --------------------------------------------------------------------
  for (const [width, theme] of [[1440, 'light'], [1440, 'dark'], [1024, 'light'], [390, 'light'], [390, 'dark']]) {
    await page.setViewportSize({width, height: width === 390 ? 844 : 1000});
    await useTheme(theme);
    for (const id of ['command-center', 'capacity-plan', 'approvals']) {
      await open(id);
      if (id === 'command-center') await page.locator('#command-center-content:not([hidden])').waitFor();
      if (id === 'approvals') await page.locator('#approval-list').waitFor();
      await open(id);
      await page.screenshot({path: path.join(shots, `a4-glass-${width}-${theme}-${id}.png`)});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth
        <= document.documentElement.clientWidth + 1), `${width} ${theme} ${id} does not overflow`);
    }
    if (width === 390) await page.keyboard.press('Escape');
  }
  await page.setViewportSize({width: 1440, height: 1000});
  await useTheme('light');

  await page.evaluate(() => {
    window.requestAnimationFrame = window.glassFrames.raf;
    window.cancelAnimationFrame = window.glassFrames.cancel;
    delete window.glassFrames; delete window.originalLens;
  });
  console.log('A4 measurements ' + JSON.stringify(measurements.map(m =>
    [m.theme, m.masthead, m.filter, m.mastheadPixel])));
  console.log(`A4 functional glass PASS: solid baseline unconditional, one @supports gate with both`
    + ` properties, measured blur and bounded translucency on masthead and sidebar, prominent lens in`
    + ` both contexts with 4.5:1 labels, one lens node across three contexts, A3 spring frames and`
    + ` exact settle preserved, zero idle frames, reduced motion keeps material,`
    + ` reduced transparency ${reducedTransparencyChecked ? 'restores solid' : 'structurally asserted'},`
    + ` drawer lifecycle and forced colours intact, business surfaces unfiltered with one bounded scene sheet.`);
};
