const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, openSidebarDestination, admin, viewer, apiGet, apiPost, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const endpoint = '**/api/production-board?*';
  const ready = async () => {
    await page.locator('#summary[aria-busy]').waitFor({state:'detached'});
    await page.locator('#order-list:not([hidden]) .order-row').first().waitFor();
  };
  const loaded = async action => {
    const response = page.waitForResponse(r => r.url().includes('/api/production-board?'));
    await action();
    const result = await response;
    await page.locator('#summary[aria-busy]').waitFor({state:'detached'});
    return new URL(result.url());
  };
  const noOverflow = async label => {
    const failures = await page.evaluate(() => {
      const vw = innerWidth;
      const describe = el => {
        const box = el.getBoundingClientRect(), cs = getComputedStyle(el);
        const cls = el.className && el.className.baseVal === undefined ? String(el.className).trim().split(/\s+/).join('.') : '';
        return `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${cls ? '.' + cls : ''} L=${Math.round(box.left)} R=${Math.round(box.right)} sw=${el.scrollWidth} cw=${el.clientWidth} min=${cs.minWidth} ws=${cs.whiteSpace}`;
      };
      // Controls, KPI values and row cells must stay inside the viewport and inside themselves.
      // One documented exception: A6/(S)34's narrow-width table strategy is for `.data-surface` to
      // become a horizontal scroll container so the columns keep a readable rhythm instead of
      // collapsing an order reference to one character per line. Content inside a scroller is
      // MEANT to extend past the viewport - that is what scrolling it means - so those elements
      // are held only to the self-clipping test. The document-level check below is what still
      // guarantees the page itself never scrolls sideways.
      const scrolled = el => {
        for (let node = el.parentElement; node && node !== document.body; node = node.parentElement) {
          const overflow = getComputedStyle(node).overflowX;
          if (overflow === 'auto' || overflow === 'scroll') return true;
        }
        return false;
      };
      const bad = [];
      for (const el of document.querySelectorAll('#board-view input, #board-view select, #board-view button, #summary dd, #summary dt, #order-list .data-cell')) {
        if (!el.getClientRects().length) continue;
        const box = el.getBoundingClientRect();
        if (el.scrollWidth > el.clientWidth + 1) { bad.push(describe(el)); continue; }
        if (scrolled(el)) continue;
        if (box.left < 0 || box.right > vw + 1) bad.push(describe(el));
      }
      // When the document itself overflows, name the innermost element(s) responsible
      // instead of reporting only the page, so a future failure points at the real cause.
      if (document.documentElement.scrollWidth > vw) {
        const overflowing = [...document.querySelectorAll('body *')]
          .filter(el => el.getClientRects().length && (el.getBoundingClientRect().right > vw + 1 || el.scrollWidth > el.clientWidth + 1));
        // Drop any element that still contains a wider descendant; the deepest offenders remain.
        const innermost = overflowing.filter(el => overflowing.every(other => other === el || !el.contains(other)));
        for (const el of innermost.slice(0, 10)) bad.push(describe(el));
        if (!bad.length) bad.push('html (document scroll overflow with no visible offending element)');
      }
      return bad;
    });
    assert.deepEqual(failures, [], label + ': controls, values and rows fit without clipping');
  };
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.evaluate(() => {document.documentElement.style.fontSize='';});
  if (await page.locator('dialog[open]').count()) await page.keyboard.press('Escape');
  await login(admin);
  await openSidebarDestination('Produksi');
  await ready();
  await page.setViewportSize({width:1920,height:1000});
  if (await page.locator('#theme').textContent() === 'Mode terang') await page.locator('#theme').click();

  const shape = await page.evaluate(() => {
    const board=document.querySelector('#board-view'), surface=board.querySelector('.production-work');
    const box=board.getBoundingClientRect(), parent=board.parentElement.getBoundingClientRect();
    const cards=[...document.querySelectorAll('#summary>div')];
    const search=document.querySelector('#search').getBoundingClientRect();
    const status=document.querySelector('#status').getBoundingClientRect();
    const submit=document.querySelector('#board-view .production-search').getBoundingClientRect();
    const list=document.querySelector('#order-list');
    const statusCell=document.querySelector('#order-list .order-row>td:nth-child(5)');
    return {
      width:box.width, centered:Math.abs((box.left+box.right)-(parent.left+parent.right))<2,
      cardHeights:cards.map(el=>el.getBoundingClientRect().height),
      cardBackgrounds:cards.map(el=>getComputedStyle(el).backgroundColor),
      // A6 tints the semantic tile, never the card body: that is what keeps four metrics from
      // reading as four tabs with one selected.
      tileBackgrounds:cards.map(el=>getComputedStyle(el.querySelector('.metric-icon')).backgroundColor),
      icons:cards.map(el=>{const svg=el.querySelector('svg');return {hidden:svg.getAttribute('aria-hidden'), focusable:svg.getAttribute('focusable'), resolves:!!document.querySelector(svg.querySelector('use').getAttribute('href')), tile:getComputedStyle(svg.parentElement).backgroundColor};}),
      figureRatio:parseFloat(getComputedStyle(cards[0].querySelector('dd')).fontSize)/parseFloat(getComputedStyle(cards[0].querySelector('dt')).fontSize),
      // One command bar, one row: the search leads it, the submit sits on the same baseline, and
      // the filters are compact beside them rather than stacked underneath.
      searchPriority:search.width>status.width && Math.abs(search.top-status.top)<2 && Math.abs(search.bottom-submit.bottom)<2,
      commandGeometry:{searchW:search.width,statusW:status.width,searchTop:search.top,statusTop:status.top,searchBottom:search.bottom,submitBottom:submit.bottom},
      contained:['#search-form','#order-list','.pagination'].every(sel=>surface.contains(board.querySelector(sel))),
      resetBackground:getComputedStyle(document.querySelector('#reset-board')).backgroundColor,
      headerBackground:getComputedStyle(document.querySelector('#order-list .data-header th')).backgroundColor,
      // The data surface carries the material now; the grouping element is a transparent
      // container, because two nested cards would put two borders around one table.
      listBackground:getComputedStyle(list).backgroundColor,
      surfaceBackground:getComputedStyle(surface).backgroundColor,
      listBorder:parseFloat(getComputedStyle(list).borderTopWidth),
      chipWidth:board.querySelector('.status-chip').getBoundingClientRect().width,
      cellWidth:statusCell.getBoundingClientRect().width,
    };
  });
  assert.ok(shape.width>=1320 && shape.width<=1380 && shape.centered, 'wide Production column is bounded and centered');
  assert.ok(shape.cardHeights.every(height=>height<130), 'desktop KPI cards are denser than the baseline');
  assert.equal(new Set(shape.cardBackgrounds).size,1, 'metric card bodies stay neutral - these are metrics, not selected tabs');
  assert.ok(new Set(shape.tileBackgrounds).size>=2, 'the semantic tiles carry the distinction instead');
  assert.ok(shape.figureRatio>1.7, `the figure dominates its label (${shape.figureRatio})`);
  for(const icon of shape.icons){assert.equal(icon.hidden,'true');assert.equal(icon.focusable,'false');assert.ok(icon.resolves);assert.notEqual(icon.tile,'rgba(0, 0, 0, 0)');}
  assert.ok(shape.searchPriority, 'search and submit lead one compact command bar: '+JSON.stringify(shape.commandGeometry));
  assert.ok(shape.contained, 'command bar, rows and pagination share one working surface');
  assert.equal(shape.resetBackground,'rgba(0, 0, 0, 0)', 'reset stays tertiary');
  assert.notEqual(shape.headerBackground,shape.listBackground, 'the quiet table header is still distinguishable');
  assert.equal(shape.surfaceBackground,'rgba(0, 0, 0, 0)', 'the grouping element adds no second card');
  assert.ok(shape.listBorder>0, 'the order list is the bordered primary data surface');
  assert.ok(shape.chipWidth<shape.cellWidth, 'status is shrink-wrapped');
  const data=await apiGet('/api/production-board?limit=25&offset=0');
  const number=new Intl.NumberFormat('id-ID');
  assert.deepEqual(await page.locator('#summary dd').allTextContents(),
    [[data.summary.active,'order'],[data.summary.overdue,'order'],[data.summary.in_progress,'pcs'],[data.summary.rework,'pcs']].map(([v,u])=>`${number.format(v)} ${u}`));

  // Count-only fixtures exercise presentation; the real response supplies every other field.
  const tones=[];
  for(const count of [0,3]){
    await page.route(endpoint,async route=>{const response=await route.fetch();const body=await response.json();body.open_issues=count;await route.fulfill({response,json:body});});
    await loaded(()=>page.locator('#refresh').click());
    const tone=await page.locator('#issues-summary').evaluate(el=>({text:el.textContent, color:getComputedStyle(el).color, background:getComputedStyle(el).backgroundColor, active:el.classList.contains('has-issues'), glyph:el.querySelector('use').getAttribute('href'),
      // A6 keeps an attention note's copy at the readable ink and carries the semantic in the
      // surface tint, its border and the leading icon. The icon is the colour channel to read.
      iconColor:getComputedStyle(el.querySelector('.icon')).color, border:getComputedStyle(el).borderTopColor,
      title:el.querySelector('.attention-note-title').textContent.trim(),
      reason:el.querySelector('.attention-note-reason').textContent.trim()}));
    assert.match(tone.text,new RegExp(`${count} kendala terbuka`));
    assert.equal(tone.title,`${count} kendala terbuka`,'the count is the note title');
    assert.ok(tone.reason.length>0,'the note says what the operator can do about it');
    assert.equal(tone.active,count>0);assert.equal(tone.glyph,count?'#i-alert-triangle':'#i-check-circle');
    tones.push(tone);
    await page.unroute(endpoint);
  }
  assert.notEqual(tones[0].background,tones[1].background,'the cleared and raised states have different tints');
  assert.notEqual(tones[0].border,tones[1].border,'...and different edges');
  assert.notEqual(tones[0].iconColor,tones[1].iconColor,'...and different semantic icon colours');
  assert.equal(tones[0].color,tones[1].color,'the copy itself stays at the readable ink in both states');
  const issueQuery=await loaded(()=>page.locator('#issues-summary').click());
  assert.equal(issueQuery.searchParams.get('status'),'blocked');
  await loaded(()=>page.locator('#reset-board').click());
  await ready();

  for(const [selector,value,param] of [['#status','active','status'],['#board-owner',data.owners[0].id,'owner_id'],['#board-stage','cutting','stage']]){
    const url=await loaded(()=>page.locator(selector).selectOption(value));
    assert.equal(url.searchParams.get(param),value);
  }
  await loaded(()=>page.locator('#reset-board').click());
  assert.equal(await page.locator('#status').inputValue(),'all');
  assert.equal(await page.locator('#board-owner').inputValue(),'');
  assert.equal(await page.locator('#board-stage').inputValue(),'all');
  await page.locator('#search').fill('NO-SUCH-PREMIUM-ORDER');
  await loaded(()=>page.locator('#board-view .production-search').click());
  assert.match(await page.locator('#board-message').textContent(),/Tidak ada order yang cocok/);
  await loaded(()=>page.locator('#reset-board').click());
  assert.equal(await page.locator('#search').inputValue(),'');

  // Real orders guarantee a second page in either a focused or full-suite run.
  const total=(await apiGet('/api/production-board?limit=25&offset=0')).total;
  if(total<26){
    const products=await apiGet('/api/products?limit=100&offset=0');
    for(let i=total;i<26;i++) await apiPost('/api/orders',{reference:`PREMIUM-DEMO-${i}-${Date.now()}`,title:'CONTOH pagination',owner_id:data.owners[0].id,due_date:'2099-01-01',lines:[{product_id:products[0].id,quantity:10}]});
  }
  await loaded(()=>page.locator('#refresh').click());await ready();
  const firstRef=await page.locator('.reference').first().textContent();
  assert.equal((await loaded(()=>page.locator('#next').click())).searchParams.get('offset'),'25');await ready();
  assert.notEqual(await page.locator('.reference').first().textContent(),firstRef);
  assert.equal((await loaded(()=>page.locator('#previous').click())).searchParams.get('offset'),'0');await ready();
  assert.equal(await page.locator('.reference').first().textContent(),firstRef);

  for(const theme of ['light','dark']){
    if(await page.locator('#theme').textContent() !== (theme==='dark'?'Mode terang':'Mode gelap')) await page.locator('#theme').click();
    // Park the pointer outside the list first. A6 rows carry a 4%-alpha hover overlay, and a
    // pointer left sitting on a row after the pagination clicks would otherwise be measured as
    // part of that row's backdrop.
    await page.mouse.move(0,0);
    await page.locator('#board-view .workspace-title').hover();
    const contrast = await page.evaluate(() => {
      // Alpha is composited rather than discarded. A6 surfaces are deliberately translucent
      // (`#ffffffeb` over the wallpaper) and its hover and selection states are low-alpha
      // overlays, so reading only the first non-transparent background - and reading it as if
      // it were opaque - measures a colour that is never actually on screen. Every layer from
      // the element up to the first opaque one is blended over the page canvas instead.
      const parse = value => {
        const parts = (value.match(/[\d.]+/g) || []).map(Number);
        return {r:parts[0]||0, g:parts[1]||0, b:parts[2]||0, a:parts.length>3?parts[3]:1};
      };
      const probe = value => {
        const node = document.createElement('span');
        node.style.color = value; document.body.appendChild(node);
        const resolved = getComputedStyle(node).color; node.remove();
        return parse(resolved);
      };
      const canvas = probe('var(--canvas)');
      const backdrop = el => {
        const layers = [];
        for (let node = el; node; node = node.parentElement) {
          const layer = parse(getComputedStyle(node).backgroundColor);
          if (layer.a > 0) layers.push(layer);
          if (layer.a >= 1) break;
        }
        let base = canvas;
        for (const layer of layers.reverse())
          base = {r:layer.r*layer.a + base.r*(1-layer.a),
                  g:layer.g*layer.a + base.g*(1-layer.a),
                  b:layer.b*layer.a + base.b*(1-layer.a), a:1};
        return base;
      };
      const luminance = ({r,g,b}) => [r,g,b].map(c => c/255)
        .map(c => c<=.04045?c/12.92:((c+.055)/1.055)**2.4)
        .reduce((sum,c,i)=>sum+c*[.2126,.7152,.0722][i],0);
      return [...document.querySelectorAll('#summary dt, #summary dd, #summary small, #issues-summary, #issues-summary .attention-note-title, #issues-summary .attention-note-reason, #search-form label, #search-form input, #search-form select, #search-form button, #production-filter-hint, #updated, #order-list .data-header th, #order-list .reference, #order-list .data-secondary, #order-list .data-meta, #order-list .progress-value, #order-list .order-title, #order-list .status-chip, #new-order')].map(el=>{
        const fg=luminance(parse(getComputedStyle(el).color)),bg=luminance(backdrop(el));
        return {label:el.id || el.textContent.trim().slice(0,35),
          ratio:(Math.max(fg,bg)+.05)/(Math.min(fg,bg)+.05)};
      });
    });
    assert.deepEqual(contrast.filter(c=>c.ratio<4.5),[],`${theme}: Production text meets AA contrast`);
    for(const width of [1440,1280,1024,768,390,320]){
      await page.setViewportSize({width,height:width<500?844:900});
      await noOverflow(`${theme} ${width}`);
      if(width<500){
        const sizes=await page.locator('#board-view button, #board-view input, #board-view select').evaluateAll(nodes=>nodes.filter(n=>n.getClientRects().length).map(n=>n.getBoundingClientRect().height));
        assert.ok(sizes.every(h=>h>=44),'mobile controls have 44px touch height');
      }
      if(width===1440 || width===390) {await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(shots,`premium-${theme}-${width}.png`)});}
    }
    await page.setViewportSize({width:1440,height:900});
    await page.evaluate(()=>document.documentElement.style.fontSize='200%');
    for(const width of [1440,390,320]){
      await page.setViewportSize({width,height:900});
      await noOverflow(`${theme} ${width} at 200% text`);
    }
    await page.setViewportSize({width:1440,height:900});
    await page.locator('#search').focus();
    const focus=await page.locator('#search').evaluate(el=>getComputedStyle(el).outlineStyle);
    assert.notEqual(focus,'none');
    await page.keyboard.press('Tab');assert.equal(await page.locator('#board-view .production-search').evaluate(el=>el===document.activeElement),true);
    await page.keyboard.press('Tab');assert.equal(await page.locator('#status').evaluate(el=>el===document.activeElement),true);
    await page.locator('#new-order').click();await page.locator('#dialog-content input').first().waitFor();
    assert.equal(await page.locator('dialog[open]').evaluate(el=>el.scrollWidth<=el.clientWidth && el.getBoundingClientRect().width<=innerWidth),true,'create order dialog fits at enlarged text');
    await page.keyboard.press('Escape');await page.evaluate(()=>document.documentElement.style.fontSize='');
  }
  // Dark mode is tuned, not inverted: the data surface resolves to the A6 workspace surface
  // token (near-opaque over the wallpaper, or the flat A1 material where translucency is off),
  // and it is never simply the page canvas.
  const dark=await page.evaluate(()=>{
    const root=getComputedStyle(document.documentElement);
    const list=document.querySelector('#order-list');
    const resolve=value=>{
      const probe=document.createElement('span');probe.style.color=value;list.appendChild(probe);
      const colour=getComputedStyle(probe).color;probe.remove();return colour;
    };
    return {actual:getComputedStyle(list).backgroundColor,
      // Either is correct and both are the A6 surface: the near-opaque tint where the engine
      // has backdrop filtering, the flat A1 material where it does not.
      tint:resolve('var(--workspace-surface-tint)'), solid:resolve('var(--workspace-surface)'),
      canvasColour:resolve('var(--canvas)'), canvas:root.getPropertyValue('--canvas').trim()};
  });
  assert.ok([dark.tint,dark.solid].includes(dark.actual),
    `the dark data surface is the A6 workspace surface (got ${dark.actual})`);
  assert.notEqual(dark.actual,dark.canvasColour,'the data surface is never just the page canvas');
  assert.equal(dark.canvas,'#151517');
  await page.locator('#theme').click();

  let release;const gate=new Promise(resolve=>release=resolve);
  await page.route(endpoint,async route=>{await gate;await route.continue();});
  await page.locator('#refresh').click();
  // M4/§08: a reload with rows already on screen keeps them and signals the request in place, so
  // the in-flight state here is the busy marker and the dim, not a placeholder that replaces the
  // data. The pagination guard is unchanged.
  await page.locator('#order-list[aria-busy]').waitFor();
  assert.equal(await page.locator('#order-list').isHidden(),false);
  assert.equal(await page.locator('#order-list .order-row').first().isVisible(),true);
  assert.equal(await page.locator('#next').isDisabled(),true);
  release();await ready();await page.unroute(endpoint);
  // With nothing left to preserve, the same control still shows the loading placeholder and
  // hides the list: that state belongs to a load from scratch, and it is asserted here so the
  // distinction itself stays covered.
  await page.locator('#search').fill('zzz-premium-tidak-ada');
  await page.getByRole('button',{name:'Cari order',exact:true}).click();
  await page.locator('#board-message').filter({hasText:'Tidak ada order yang cocok'}).waitFor();
  let releaseEmpty;const emptyGate=new Promise(resolve=>releaseEmpty=resolve);
  await page.route(endpoint,async route=>{await emptyGate;await route.continue();});
  await page.locator('#refresh').click();
  await page.locator('#board-message').filter({hasText:'Memuat'}).waitFor();
  assert.equal(await page.locator('#order-list').isHidden(),true);
  // Let the released response land before the route is removed, or the pending handler's
  // continue() races the removal and throws.
  releaseEmpty();await page.locator('#summary[aria-busy]').waitFor({state:'detached'});
  await page.unroute(endpoint);
  await page.getByRole('button',{name:'Reset filter',exact:true}).click();
  await ready();
  await page.route(endpoint,route=>route.fulfill({status:503,json:{detail:'CONTOH production request failed'}}));
  await page.locator('#refresh').click();await page.locator('#board-message').filter({hasText:'CONTOH production request failed'}).waitFor();
  assert.equal(await page.locator('#issues-summary').isHidden(),true);
  await page.unroute(endpoint);await loaded(()=>page.locator('#refresh').click());await ready();

  await login(viewer);await ready();
  assert.equal(await page.locator('#new-order').isHidden(),true);
  await page.locator('.order-title').first().click();await page.locator('#detail-content h1').waitFor();
  assert.equal(await page.locator('#detail-content [data-action="move"], #detail-content [data-action="edit-order"]').count(),0);
  await openSidebarDestination('Produksi');await ready();
  // Expiry still goes through the existing authentication failure path.
  await page.route(endpoint,route=>route.fulfill({status:401,json:{detail:'Session expired'}}));
  await page.locator('#refresh').click();await page.getByLabel('Kunci akses',{exact:true}).waitFor();
  await page.unroute(endpoint);await login(admin);
  await page.emulateMedia({reducedMotion:'no-preference'});
  console.log('Production premium browser QA PASS: bounded column, KPI/API parity, glyphs, issue states, toolbar, filters, pagination, light/dark, six widths, 200% text, focus, dialogs, loading/empty/error, viewer and expired session.');
};
