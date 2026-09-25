// A6.1 Produksi modern workspace: the behavioural half of the migration contract.
//
// tests/test_apple27_production_workspace_contract.py proves statically that no meaning moved.
// This module proves it against a running application and real fixture data, which is the only
// place some of it can be proved at all: that the four metric cards carry the four numbers the
// board endpoint actually returned, that progress is warehouse-over-target rather than an
// invented completion figure, that each filter still produces the same query string, that the
// two empty states are genuinely different states, and that an overtaken response cannot repaint
// a newer one.
//
// Deliberately not screenshot-only. Every visual case here also asserts something about
// behaviour or data, because a screenshot cannot fail when a number is wrong.
const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, openSidebarDestination, admin, operator, viewer,
                         apiGet, apiPost, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const endpoint = '**/api/production-board?*';
  const number = new Intl.NumberFormat('id-ID');

  const ready = async () => {
    await page.locator('#summary[aria-busy]').waitFor({state: 'detached'});
    await page.locator('#order-list:not([hidden]) .order-row').first().waitFor();
  };
  // Returns the URL the board actually requested, so a filter assertion reads the real query
  // rather than trusting the control it clicked.
  const loaded = async action => {
    const response = page.waitForResponse(r => r.url().includes('/api/production-board?'));
    await action();
    const url = new URL((await response).url());
    await page.locator('#summary[aria-busy]').waitFor({state: 'detached'});
    return url;
  };
  // A visual-review screenshot has to show the workspace and nothing else. Earlier steps in this
  // module legitimately leave a six-second "Pencatatan tersimpan." toast and a focus ring behind,
  // and both would sit on top of the surface a human is being asked to approve.
  const shot = async name => {
    await page.evaluate(() => {
      scrollTo(0, 0);
      const notice = document.getElementById('notice');
      notice.hidden = true; notice.textContent = '';
      if (document.activeElement && document.activeElement !== document.body) {
        document.activeElement.blur();
      }
    });
    await page.waitForFunction(() => !document.querySelector('#board-view').className.includes('motion-')
      && !document.getElementById('order-list').className.includes('motion-'));
    await page.screenshot({path: path.join(shots, `a61-${name}.png`), fullPage: true});
  };
  // The reviewed unit for information hierarchy: exactly what a 1440x1000 reviewer sees before
  // scrolling. `.workspace-main` is the scrolling region, not the document, so it is what has to
  // be returned to the top.
  const firstViewport = async name => {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.waitForTimeout(150);
    await page.evaluate(() => {
      document.querySelector('.workspace-main').scrollTo(0, 0);
      const notice = document.getElementById('notice');
      notice.hidden = true; notice.textContent = '';
      if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
    });
    await page.screenshot({path: path.join(shots, `a61-${name}.png`)});
  };
  const theme = async wanted => {
    const offer = wanted === 'dark' ? 'Mode gelap' : 'Mode terang';
    if (await page.locator('#theme').textContent() === offer) await page.locator('#theme').click();
    await page.waitForFunction(want => (document.documentElement.dataset.theme || 'light') === want, wanted);
  };
  // A synthetic board payload for the states real demo data cannot reach. Only the fields the
  // renderer already consumes are supplied - inventing one here would be the very thing the
  // phase forbids.
  const boardPayload = (over = {}) => ({
    summary: {active: 0, overdue: 0, in_progress: 0, rework: 0, orders: 0, ...(over.summary || {})},
    open_issues: over.open_issues ?? 0,
    orders: over.orders ?? [],
    owners: over.owners ?? [],
    total: over.total ?? 0,
  });

  await page.emulateMedia({reducedMotion: 'reduce'});
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});
  if (await page.locator('dialog[open]').count()) await page.keyboard.press('Escape');
  await page.setViewportSize({width: 1440, height: 900});
  await login(admin);
  await theme('light');
  await openSidebarDestination('Produksi');
  await ready();

  // ---- the heading is the workspace, not a slogan -------------------------------------------
  const heading = await page.evaluate(() => {
    const board = document.getElementById('board-view');
    const title = board.querySelector('.workspace-title');
    const list = document.getElementById('order-list');
    const strip = document.getElementById('summary');
    return {
      title: title.textContent.trim(),
      subtitle: board.querySelector('.workspace-subtitle').textContent.trim(),
      level: title.tagName,
      actions: [...board.querySelectorAll('.workspace-heading .workspace-actions button')]
        .filter(b => !b.hidden).map(b => b.textContent.trim()),
      // The order list, not the metric band, owns the workspace: the strip must be the shorter
      // of the two on a desktop viewport.
      stripHeight: strip.getBoundingClientRect().height,
      listHeight: list.getBoundingClientRect().height,
    };
  });
  assert.equal(heading.title, 'Produksi');
  assert.equal(heading.level, 'H1', 'the workspace name is the page heading');
  assert.equal(heading.subtitle, 'Pantau order, progres, kendala, dan output produksi.');
  assert.deepEqual(heading.actions, ['Muat ulang', 'Buat order produksi']);
  assert.ok(heading.listHeight > heading.stripHeight,
    `the order list is the centre of the page (list ${heading.listHeight} vs strip ${heading.stripHeight})`);

  // ---- the four metrics are the four real payload fields, with their real units -------------
  const payload = await apiGet('/api/production-board?limit=25&offset=0');
  const metrics = await page.evaluate(() => [...document.querySelectorAll('#summary>div')].map(card => ({
    label: card.querySelector('dt').textContent.trim(),
    value: card.querySelector('dd').textContent.replace(/\s+/g, ' ').trim(),
    unit: card.querySelector('.metric-unit').textContent.trim(),
    tone: [...card.classList].find(name => name.startsWith('metric-card-')) || null,
  })));
  assert.deepEqual(metrics.map(m => m.label),
    ['Order aktif', 'Lewat target', 'Dalam proses', 'Perlu rework']);
  assert.deepEqual(metrics.map(m => m.value), [
    `${number.format(payload.summary.active)} order`,
    `${number.format(payload.summary.overdue)} order`,
    `${number.format(payload.summary.in_progress)} pcs`,
    `${number.format(payload.summary.rework)} pcs`,
  ], 'the metric strip is the board summary, not a recomputed one');
  assert.deepEqual(metrics.map(m => m.unit), ['order', 'order', 'pcs', 'pcs']);
  assert.equal(metrics[0].tone, 'metric-card-info');
  assert.equal(metrics[2].tone, 'metric-card-info');
  assert.equal(metrics[1].tone, payload.summary.overdue > 0 ? 'metric-card-danger' : null);
  assert.equal(metrics[3].tone, payload.summary.rework > 0 ? 'metric-card-warning' : null);
  // The summary is global: a filtered board reports the same four numbers.
  const stripBefore = await page.locator('#summary').innerText();
  await loaded(() => page.locator('#status').selectOption('overdue'));
  assert.equal(await page.locator('#summary').innerText(), stripBefore,
    'the metric strip covers all production, never the filtered page');
  await loaded(() => page.locator('#reset-board').click());
  await ready();

  // ---- the updated stamp is present and quiet ----------------------------------------------
  const stamp = await page.evaluate(() => {
    const updated = document.getElementById('updated');
    const section = document.getElementById('production-orders-heading');
    return {text: updated.textContent.trim(),
      size: parseFloat(getComputedStyle(updated).fontSize),
      headingSize: parseFloat(getComputedStyle(section).fontSize)};
  });
  assert.match(stamp.text, /^Diperbarui \d{2}[.:]\d{2}$/, 'the freshness stamp is a real time');
  assert.ok(stamp.size < stamp.headingSize, 'the stamp never carries heading weight');

  // ---- progress means warehouse / target, per row, against the payload ----------------------
  const rows = await page.evaluate(() => [...document.querySelectorAll('#order-list .order-row')].map(row => ({
    reference: row.querySelector('.reference').textContent.trim(),
    secondary: row.querySelector('.data-secondary').textContent.trim(),
    legend: row.querySelector('.progress-legend .data-meta').textContent.trim(),
    percent: row.querySelector('.progress-value').textContent.trim(),
    value: Number(row.querySelector('progress[data-order]').value),
    max: Number(row.querySelector('progress[data-order]').max),
    progressLabel: row.querySelector('progress[data-order]').getAttribute('aria-label'),
    chips: [...row.querySelectorAll('.status-chip')].map(chip => chip.textContent.trim()),
    buttons: row.querySelectorAll('button').length,
    owner: row.children[1].textContent.trim(),
    due: row.children[2].textContent.trim(),
  })));
  assert.equal(rows.length, payload.orders.length);
  for (const [index, order] of payload.orders.entries()) {
    const row = rows[index];
    const expected = Math.round(order.totals.warehouse / order.target_quantity * 100);
    assert.equal(row.reference, order.reference);
    assert.equal(row.owner, order.owner_name, 'the PIC cell is the real owner name');
    assert.equal(row.value, order.totals.warehouse, 'progress value is the warehouse quantity');
    assert.equal(row.max, order.target_quantity, 'progress maximum is the production target');
    assert.equal(row.legend,
      `${number.format(order.totals.warehouse)} / ${number.format(order.target_quantity)} pcs`);
    assert.equal(row.percent, `${expected}%`);
    assert.equal(row.progressLabel, `Jumlah diterima gudang ${order.reference}`,
      'the accessible label still says what the number counts');
    assert.equal(row.secondary,
      `${order.lines.length} SKU · target ${number.format(order.target_quantity)} pcs`);
    assert.equal(row.buttons, 1, 'a row exposes exactly one control, so its name is unambiguous');
    // Status truth, including the overdue override and the secondary issue indicator.
    const status = order.overdue ? 'Lewat target'
      : order.status === 'completed' ? 'Selesai'
      : order.status === 'closed_with_reject' ? 'Ditutup · ada reject' : 'Dalam produksi';
    assert.equal(row.chips[0], status, `${order.reference} status is truthful`);
    assert.equal(row.chips.length, order.open_issues ? 2 : 1);
    if (order.open_issues) assert.equal(row.chips[1], `${number.format(order.open_issues)} kendala terbuka`,
      'the issue chip reads completely for a screen reader');
  }
  // The table is semantic, and every column header is a real header cell.
  const table = await page.evaluate(() => {
    const head = [...document.querySelectorAll('#order-list .data-header th')];
    return {columns: head.map(th => th.textContent.trim()),
      scopes: head.map(th => th.getAttribute('scope')),
      rowTag: document.querySelector('#order-list .order-row').tagName,
      cellTag: document.querySelector('#order-list .data-cell').tagName,
      scrolls: getComputedStyle(document.getElementById('order-list')).overflowX};
  });
  assert.deepEqual(table.columns,
    ['Order / produk', 'PIC', 'Target selesai', 'Progress', 'Status', 'Buka order']);
  assert.deepEqual(table.scopes, Array(6).fill('col'));
  assert.equal(table.rowTag, 'TR');
  assert.equal(table.cellTag, 'TD');

  // ---- the issue summary: count, tone and its load-bearing action ---------------------------
  const issues = await page.evaluate(() => {
    const note = document.getElementById('issues-summary');
    return {title: note.querySelector('.attention-note-title').textContent.trim(),
      reason: note.querySelector('.attention-note-reason').textContent.trim(),
      raised: note.classList.contains('has-issues'),
      glyph: note.querySelector('use').getAttribute('href')};
  });
  assert.equal(issues.title, `${number.format(payload.open_issues)} kendala terbuka`);
  assert.equal(issues.raised, payload.open_issues > 0);
  assert.equal(issues.glyph, payload.open_issues > 0 ? '#i-alert-triangle' : '#i-check-circle');
  assert.ok(issues.reason.length > 0);

  // ---- the two informational strips are secondary, and measurably so ----------------------
  // The cleared all-clear and the stage-filter explanation both sit between the metric strip and
  // the order list, so any weight they carry is weight the data loses. Measured rather than
  // eyeballed: a cleared note is a single shrink-wrapped row, the hint carries no panel, and the
  // order list starts high enough to show rows in the first viewport.
  await page.route(endpoint, async route => {
    const response = await route.fetch();
    const body = await response.json();
    body.open_issues = 0;
    await route.fulfill({response, json: body});
  });
  await loaded(() => page.locator('#refresh').click());
  await ready();
  const strips = await page.evaluate(() => {
    const note = document.getElementById('issues-summary');
    const hint = document.getElementById('production-filter-hint');
    const board = document.getElementById('board-view');
    const copy = note.querySelector('.attention-note-copy');
    const title = note.querySelector('.attention-note-title');
    const reason = note.querySelector('.attention-note-reason');
    return {
      cleared: note.classList.contains('attention-note-success'),
      raised: note.classList.contains('has-issues'),
      noteHeight: Math.round(note.getBoundingClientRect().height),
      noteWidth: Math.round(note.getBoundingClientRect().width),
      boardWidth: Math.round(board.getBoundingClientRect().width),
      // One row: the count and the reason share a baseline instead of stacking.
      oneRow: Math.abs(title.getBoundingClientRect().top - reason.getBoundingClientRect().top) < 4,
      copyDirection: getComputedStyle(copy).flexDirection,
      tint: getComputedStyle(note).backgroundColor,
      iconColour: getComputedStyle(note.querySelector('.icon')).color,
      hintHeight: Math.round(hint.getBoundingClientRect().height),
      hintBackground: getComputedStyle(hint).backgroundColor,
      hintText: hint.textContent.trim(),
      hintDescribes: document.getElementById('board-stage').getAttribute('aria-describedby'),
      // The separator between the two runs is drawn, not written.
      noteText: note.textContent.trim(),
    };
  });
  assert.equal(strips.cleared, true);
  assert.equal(strips.raised, false);
  assert.equal(strips.oneRow, true, 'a cleared all-clear is one row, not a two-line panel');
  assert.equal(strips.copyDirection, 'row');
  assert.ok(strips.noteHeight <= 34, `the cleared note is compact (${strips.noteHeight}px)`);
  assert.ok(strips.noteWidth < strips.boardWidth,
    'and shrink-wrapped rather than a full-width callout');
  assert.notEqual(strips.tint, 'rgba(0, 0, 0, 0)', 'it keeps a restrained success tint');
  assert.notEqual(strips.iconColour, 'rgba(0, 0, 0, 0)');
  assert.ok(!strips.noteText.includes('·'),
    'the decorative separator never enters the text content or the accessible name');
  assert.match(strips.noteText, /^0 kendala terbuka/);
  // The hint keeps every word and its programmatic relationship, and loses only its surface.
  assert.match(strips.hintText, /Posisi barang menampilkan order yang masih memiliki saldo di tahap tersebut\./);
  assert.match(strips.hintText, /Ringkasan di atas mencakup seluruh produksi\./);
  assert.equal(strips.hintDescribes, 'production-filter-hint');
  assert.equal(strips.hintBackground, 'rgba(0, 0, 0, 0)', 'the hint is a caption, not a panel');
  assert.ok(strips.hintHeight <= 40, `the hint reads as secondary (${strips.hintHeight}px)`);
  // The clear state is still the same control, with the same behaviour.
  const clearedQuery = await loaded(() => page.locator('#issues-summary').click());
  assert.equal(clearedQuery.searchParams.get('status'), 'blocked',
    'a cleared note keeps the exact click semantics of the raised one');
  await page.unroute(endpoint);
  await loaded(() => page.locator('#reset-board').click());
  await ready();
  // The raised state is deliberately NOT compacted, so it must still be the taller of the two.
  await page.route(endpoint, async route => {
    const response = await route.fetch();
    const body = await response.json();
    body.open_issues = 3;
    await route.fulfill({response, json: body});
  });
  await loaded(() => page.locator('#refresh').click());
  await ready();
  const raisedStrip = await page.evaluate(() => {
    const note = document.getElementById('issues-summary');
    return {height: Math.round(note.getBoundingClientRect().height),
      width: Math.round(note.getBoundingClientRect().width),
      board: Math.round(document.getElementById('board-view').getBoundingClientRect().width)};
  });
  assert.ok(raisedStrip.height > strips.noteHeight,
    `a raised issue count keeps the prominent treatment (${raisedStrip.height} vs ${strips.noteHeight})`);
  assert.ok(raisedStrip.width > strips.noteWidth, 'and keeps the full width');
  await page.unroute(endpoint);
  await loaded(() => page.locator('#refresh').click());
  await ready();
  // The raised state, forced deterministically rather than left to whatever the fixture's own
  // count happens to be at this point in the suite. Only `open_issues` is overridden; every other
  // field is the real response.
  await page.route(endpoint, async route => {
    const response = await route.fetch();
    const body = await response.json();
    body.open_issues = 3;
    await route.fulfill({response, json: body});
  });
  await loaded(() => page.locator('#refresh').click());
  await ready();
  const raised = await page.evaluate(() => {
    const note = document.getElementById('issues-summary');
    return {title: note.querySelector('.attention-note-title').textContent.trim(),
      reason: note.querySelector('.attention-note-reason').textContent.trim(),
      raised: note.classList.contains('has-issues'),
      glyph: note.querySelector('use').getAttribute('href'),
      arrow: note.querySelectorAll('use').length};
  });
  assert.equal(raised.title, '3 kendala terbuka');
  assert.equal(raised.reason, 'Lihat order terkait');
  assert.equal(raised.raised, true);
  assert.equal(raised.glyph, '#i-alert-triangle');
  assert.equal(raised.arrow, 2, 'the raised state points at the action it performs');
  await shot('board-1440-light-issues');
  await page.unroute(endpoint);
  await loaded(() => page.locator('#refresh').click());
  await ready();
  const blocked = await loaded(() => page.locator('#issues-summary').click());
  assert.equal(blocked.searchParams.get('status'), 'blocked',
    'the issue summary still resets the filters and selects the blocked status');
  assert.equal(await page.locator('#status').inputValue(), 'blocked');
  await loaded(() => page.locator('#reset-board').click());
  await ready();

  // ---- every filter still produces exactly the query it produced before ---------------------
  const baseline = {q: '', status: 'all', owner_id: '', stage: 'all', limit: '25', offset: '0'};
  const query = url => Object.fromEntries([...url.searchParams.entries()]);
  assert.deepEqual(query(await loaded(() => page.locator('#refresh').click())), baseline,
    'a plain reload asks for the unfiltered first page');
  for (const [control, value, key] of [['#status', 'active', 'status'],
                                       ['#board-owner', payload.owners[0].id, 'owner_id'],
                                       ['#board-stage', 'cutting', 'stage']]) {
    const url = await loaded(() => page.locator(control).selectOption(value));
    assert.equal(query(url)[key], value, `${control} drives ${key}`);
    assert.equal(query(url).offset, '0', 'changing a filter returns to the first page');
  }
  // Reset restores every control and the query.
  const reset = await loaded(() => page.locator('#reset-board').click());
  assert.deepEqual(query(reset), baseline);
  for (const [control, value] of [['#search', ''], ['#status', 'all'], ['#board-owner', ''],
                                  ['#board-stage', 'all']]) {
    assert.equal(await page.locator(control).inputValue(), value);
  }
  await ready();
  // Search submits on the button and on Enter, and neither queries per keystroke.
  let requests = 0;
  page.on('request', request => {if (request.url().includes('/api/production-board?')) requests++;});
  await page.locator('#search').fill(payload.orders[0].reference);
  await page.waitForTimeout(400);
  assert.equal(requests, 0, 'typing never queries the board');
  const submitted = await loaded(() => page.getByRole('button', {name: 'Cari order', exact: true}).click());
  assert.equal(query(submitted).q, payload.orders[0].reference);
  await ready();
  const entered = await loaded(() => page.locator('#search').press('Enter'));
  assert.equal(query(entered).q, payload.orders[0].reference, 'keyboard submission still works');
  await ready();

  // ---- a filtered miss and a genuinely empty board are different states --------------------
  await page.locator('#search').fill('A61-TIDAK-ADA-ORDER-INI');
  await loaded(() => page.getByRole('button', {name: 'Cari order', exact: true}).click());
  const noMatch = await page.evaluate(() => ({
    title: document.querySelector('#board-message .empty-state-title').textContent.trim(),
    copy: document.querySelector('#board-message .empty-state-copy').textContent.trim(),
    action: document.querySelectorAll('#board-message button').length,
    listHidden: document.getElementById('order-list').hidden,
  }));
  assert.equal(noMatch.title, 'Tidak ada order yang cocok.');
  assert.match(noMatch.copy, /Reset filter/);
  assert.equal(noMatch.action, 0, 'a filtered miss offers no create action - nothing is missing');
  assert.equal(noMatch.listHidden, true);
  await shot('board-1440-light-no-match');
  await loaded(() => page.locator('#reset-board').click());
  await ready();

  await page.route(endpoint, route => route.fulfill({json: boardPayload()}));
  await loaded(() => page.locator('#refresh').click());
  const emptyBoard = await page.evaluate(() => ({
    title: document.querySelector('#board-message .empty-state-title').textContent.trim(),
    copy: document.querySelector('#board-message .empty-state-copy').textContent.trim(),
    action: [...document.querySelectorAll('#board-message button')].map(b => b.textContent.trim()),
    pageCount: document.getElementById('page-count').textContent.trim(),
  }));
  assert.equal(emptyBoard.title, 'Belum ada order.');
  assert.match(emptyBoard.copy, /Master SKU/);
  assert.deepEqual(emptyBoard.action, ['Buat order produksi pertama'],
    'an admin looking at a genuinely empty board is offered the real action');
  assert.equal(emptyBoard.pageCount, '0 order');
  await shot('board-1440-light-empty');
  await page.unroute(endpoint);

  // A non-admin gets the same state without an action they cannot perform.
  await page.route(endpoint, route => route.fulfill({json: boardPayload()}));
  await login(operator);
  await page.locator('#board-message .empty-state-title').waitFor();
  assert.equal(await page.locator('#board-message .empty-state-title').textContent(),
    'Belum ada order produksi.');
  assert.equal(await page.locator('#board-message button').count(), 0,
    'an operator is never offered an action the role cannot take');
  await page.unroute(endpoint);
  await login(admin);
  await openSidebarDestination('Produksi');
  await ready();

  // ---- a failed load says so, and never presents stale rows as current ---------------------
  const rowsBefore = await page.locator('#order-list .order-row').count();
  await page.route(endpoint, route => route.fulfill({status: 503,
    json: {detail: 'CONTOH A6.1 board failure'}}));
  await page.locator('#refresh').click();
  await page.locator('#board-message .error-state-title').waitFor();
  const failure = await page.evaluate(() => ({
    message: document.getElementById('board-message').textContent,
    flagged: document.getElementById('board-message').classList.contains('error'),
    rows: document.querySelectorAll('#order-list .order-row').length,
    dimmed: document.getElementById('order-list').classList.contains('is-refreshing'),
    issuesHidden: document.getElementById('issues-summary').hidden,
    stamp: document.getElementById('updated').textContent,
    busy: document.getElementById('summary').hasAttribute('aria-busy'),
  }));
  assert.match(failure.message, /CONTOH A6.1 board failure/, 'the real reason is shown');
  assert.equal(failure.flagged, true);
  assert.equal(failure.rows, rowsBefore, 'the rows the operator already had stay readable');
  assert.equal(failure.dimmed, false, 'a failure clears the refresh dim immediately');
  assert.equal(failure.issuesHidden, true, 'a stale issue count is withdrawn, not left standing');
  assert.equal(failure.stamp, '', 'and so is the freshness stamp');
  assert.equal(failure.busy, false);
  await page.unroute(endpoint);
  await loaded(() => page.locator('#refresh').click());
  await ready();

  // ---- an overtaken response can never repaint a newer one ---------------------------------
  let releaseStale;
  const staleHeld = new Promise(resolve => releaseStale = resolve);
  let call = 0;
  await page.route(endpoint, async route => {
    call += 1;
    if (call === 1) {
      await staleHeld;
      await route.fulfill({json: boardPayload({
        summary: {active: 999, overdue: 999, in_progress: 999, rework: 999, orders: 999},
        total: 1, owners: [],
        orders: [{id: 'a61-stale', reference: 'A61-STALE-RESPONSE', title: 'CONTOH tersalip',
          owner_name: 'CONTOH', due_date: '2099-01-01', lines: [{}], target_quantity: 10,
          totals: {planned: 10, cutting: 0, sewing: 0, finishing: 0, qc: 0, warehouse: 0,
            rework: 0, reject: 0},
          status: 'active', overdue: false, open_issues: 0}],
      })});
    } else {
      await route.continue();
    }
  });
  const staleLanded = page.waitForResponse(r => r.url().includes('/api/production-board?')
    && new URL(r.url()).searchParams.get('stage') === 'all');
  await page.locator('#refresh').click();            // request 1, held
  await page.locator('#board-stage').selectOption('cutting');  // request 2, lands first
  await page.locator('#summary[aria-busy]').waitFor({state: 'detached'});
  releaseStale();
  // Same reasoning as above: observe the overtaken response actually arriving before unrouting,
  // so this case tests the guard rather than a request that never landed.
  await staleLanded;
  await page.waitForTimeout(400);
  const afterStale = await page.evaluate(() => ({
    markup: document.getElementById('order-list').innerHTML,
    stage: document.getElementById('board-stage').value,
    active: document.querySelector('#summary dd').textContent.trim(),
  }));
  assert.ok(!afterStale.markup.includes('A61-STALE-RESPONSE'),
    'an overtaken board response must not repaint the current one');
  assert.notEqual(afterStale.active, '999 order', 'nor repaint the metric strip');
  assert.equal(afterStale.stage, 'cutting');
  await page.unroute(endpoint);
  await loaded(() => page.locator('#board-stage').selectOption('all'));
  await ready();

  // ---- pagination is unchanged -------------------------------------------------------------
  const total = (await apiGet('/api/production-board?limit=25&offset=0')).total;
  if (total > 25) {
    const firstPage = await page.locator('#order-list .reference').first().textContent();
    const next = await loaded(() => page.locator('#next').click());
    assert.equal(query(next).offset, '25');
    await ready();
    assert.notEqual(await page.locator('#order-list .reference').first().textContent(), firstPage);
    assert.match(await page.locator('#page-count').textContent(), /^26–\d+ dari [\d.]+ order$/);
    const previous = await loaded(() => page.locator('#previous').click());
    assert.equal(query(previous).offset, '0');
    await ready();
    assert.equal(await page.locator('#order-list .reference').first().textContent(), firstPage);
  }
  assert.match(await page.locator('#page-count').textContent(), /^1–\d+ dari [\d.]+ order$/);

  // ---- a refresh keeps the rows; only a load from scratch replaces them ---------------------
  let releaseHold;
  const held = new Promise(resolve => releaseHold = resolve);
  await page.route(endpoint, async route => {await held; await route.continue();});
  // The released response has to be observed landing before the route is removed, or
  // `unroute()` can win the race against the still-suspended handler's `continue()` and the
  // handler throws "Route is already handled" from outside any assertion.
  const heldResponse = page.waitForResponse(r => r.url().includes('/api/production-board?'));
  await page.locator('#refresh').click();
  await page.locator('#order-list[aria-busy]').waitFor();
  const during = await page.evaluate(() => ({
    hidden: document.getElementById('order-list').hidden,
    rows: document.querySelectorAll('#order-list .order-row').length,
    dim: parseFloat(getComputedStyle(document.getElementById('order-list')).opacity),
    filtersUsable: !['search', 'status', 'board-owner', 'board-stage']
      .some(id => document.getElementById(id).disabled),
    paginationGuarded: document.getElementById('previous').disabled
      && document.getElementById('next').disabled,
  }));
  assert.equal(during.hidden, false, 'a refresh never blanks the table');
  assert.ok(during.rows > 0);
  assert.ok(during.dim < 1 && during.dim >= 0.7, `the documented refresh dim (${during.dim})`);
  assert.equal(during.filtersUsable, true, 'the refresh treatment is a signal, not a lock');
  assert.equal(during.paginationGuarded, true);
  releaseHold();
  await heldResponse;
  await page.locator('#summary[aria-busy]').waitFor({state: 'detached'});
  await page.unroute(endpoint);
  await ready();

  // ---- opening an order stays inside the same modern language -------------------------------
  const order = await apiGet(`/api/orders/${encodeURIComponent(payload.orders[0].id)}`);
  await page.getByRole('button', {name: new RegExp(order.reference)}).first().click();
  await page.locator('#detail-content h1').waitFor();
  const detail = await page.evaluate(() => {
    const host = document.getElementById('detail-content');
    const facts = [...host.querySelectorAll(':scope>.detail-grid>.detail-field')];
    const groups = [...host.querySelectorAll('.panel-grid>.utility-panel')];
    const balancePanel = host.querySelector('section .utility-panel .detail-grid-compact');
    return {
      eyebrow: host.querySelector('.workspace-eyebrow').textContent.trim(),
      title: host.querySelector('h1').textContent.trim(),
      titleClass: host.querySelector('h1').className,
      refresh: Boolean(host.querySelector('[data-action="refresh-detail"]')),
      facts: facts.map(f => [f.querySelector('dt').textContent.trim(),
        f.querySelector('dd').textContent.replace(/\s+/g, ' ').trim()]),
      groupTitles: groups.map(g => g.querySelector('.utility-panel-title').textContent.trim()),
      actions: [...host.querySelectorAll('.panel-grid button')].map(b => b.dataset.action),
      stages: [...balancePanel.querySelectorAll('.detail-field')]
        .map(f => [f.querySelector('dt').textContent.trim(),
          f.querySelector('dd').textContent.replace(/\s+/g, ' ').trim()]),
      exceptions: [...host.querySelectorAll('.utility-panel')]
        .filter(p => (p.querySelector('.utility-panel-title') || {}).textContent === 'Saldo pengecualian')
        .flatMap(p => [...p.querySelectorAll('.detail-field')]
          .map(f => [f.querySelector('dt').textContent.trim(),
            f.querySelector('dd').textContent.replace(/\s+/g, ' ').trim()])),
      totalNote: host.querySelector('.workspace-meta').textContent.trim(),
      antiFunnel: host.querySelector('.info-panel').textContent,
      timeline: host.querySelectorAll('#history-list.timeline .timeline-item').length,
      issuesHeading: document.getElementById('issues-heading').textContent.trim(),
      onlyVisibleSection: [...document.querySelectorAll('.workspace-main > section')]
        .filter(s => !s.hidden).map(s => s.id),
    };
  });
  assert.equal(detail.eyebrow, order.reference, 'the reference is the context line');
  assert.equal(detail.title, order.title, 'the order name is the heading');
  assert.match(detail.titleClass, /workspace-title/);
  assert.equal(detail.refresh, true);
  assert.deepEqual(detail.facts, [
    ['Penanggung jawab', order.owner_name],
    ['Target selesai', detail.facts[1][1]],
    ['Target produksi', `${number.format(order.target_quantity)} pcs`],
    ['Status', detail.facts[3][1]],
  ]);
  assert.deepEqual(detail.groupTitles,
    ['Order & perencanaan', 'Alur produksi', 'Fulfilment & marketplace']);
  // Not one action was lost when 27 flat buttons became three groups.
  assert.equal(new Set(detail.actions).size, detail.actions.length, 'no action is duplicated');
  for (const required of ['edit-order', 'requirements', 'cutting-runs', 'bundles', 'sewing-jobs',
                          'finishing-records', 'final-qc-records', 'finished-goods', 'warehouse',
                          'marketplace-picks', 'marketplace-packs', 'marketplace-shipments',
                          'finished-goods-stock-counts', 'order-purchases', 'order-materials']) {
    assert.ok(detail.actions.includes(required), `${required} survived the regrouping`);
  }
  // Stage read-out: the six real positions, with the real balances, explicitly not a funnel.
  assert.deepEqual(detail.stages, [
    ['Belum cutting', `${number.format(order.totals.planned)} pcs`],
    ['Cutting', `${number.format(order.totals.cutting)} pcs`],
    ['Sewing', `${number.format(order.totals.sewing)} pcs`],
    ['Finishing', `${number.format(order.totals.finishing)} pcs`],
    ['QC', `${number.format(order.totals.qc)} pcs`],
    ['Gudang', `${number.format(order.totals.warehouse)} pcs`],
  ], 'the stage strip is the current balances from the order payload');
  assert.deepEqual(detail.exceptions, [
    ['Rework', `${number.format(order.totals.rework)} pcs`],
    ['Reject', `${number.format(order.totals.reject)} pcs`],
  ]);
  const sum = Object.values(order.totals).reduce((a, b) => a + b, 0);
  assert.equal(detail.totalNote, `Jumlah seluruh posisi: ${number.format(sum)} pcs`);
  assert.match(detail.antiFunnel, /bukan jumlah yang sudah selesai melewatinya/,
    'the page states that these are balances, so the strip cannot be read as a funnel');
  assert.ok(detail.timeline > 0, 'movement history renders as an A6 timeline');
  assert.match(detail.issuesHeading, /^Kendala produksi · [\d.]+ terbuka$/);
  assert.deepEqual(detail.onlyVisibleSection, ['detail-view'], 'detail is the only visible page');

  // Every SKU line keeps its identity, its balances and its two actions. Selected by `.sku-record`
  // rather than "a panel containing a .data-primary", because the utility rows carry one too.
  const sku = await page.evaluate(() => [...document.querySelectorAll('#detail-content .sku-record')]
    .map(panel => ({
      code: panel.querySelector('.data-primary').textContent.trim(),
      meta: panel.querySelector('.data-secondary').textContent.trim(),
      balances: [...panel.querySelectorAll('.detail-field')]
        .map(f => f.querySelector('dd').textContent.replace(/\s+/g, ' ').trim()),
      actions: [...panel.querySelectorAll('button')].map(b => b.dataset.action),
    })));
  assert.equal(sku.length, order.lines.length);
  for (const [index, line] of order.lines.entries()) {
    assert.equal(sku[index].code, line.sku);
    assert.match(sku[index].meta, new RegExp(`target ${number.format(line.quantity)} pcs$`));
    assert.deepEqual(sku[index].balances,
      ['planned', 'cutting', 'sewing', 'finishing', 'qc', 'warehouse', 'rework', 'reject']
        .map(stage => `${number.format(line.balances[stage])} pcs`),
      'eight balances per SKU, straight from the order payload');
    assert.deepEqual(sku[index].actions, ['move', 'new-issue']);
  }

  // ---- the reviewed information hierarchy, measured on the page ----------------------------
  const hierarchy = await page.evaluate(() => {
    const host = document.getElementById('detail-content');
    const top = selector => {
      const node = host.querySelector(selector);
      return node ? Math.round(node.getBoundingClientRect().top) : null;
    };
    const back = document.getElementById('back').getBoundingClientRect();
    const eyebrow = host.querySelector('.workspace-eyebrow').getBoundingClientRect();
    return {
      heading: top('.workspace-heading'),
      facts: top(':scope>.detail-grid'),
      position: top('#stage-balance-heading'),
      sku: top('#sku-detail-heading'),
      actions: top('#order-actions-heading'),
      issues: top('#issues-heading'),
      history: top('#history-heading'),
      // The back control has to be shrink-wrapped, left-aligned with the order identity, and
      // directly above it - not a full-width button with centred text floating mid-page.
      backLeft: Math.round(back.left), backBottom: Math.round(back.bottom),
      eyebrowLeft: Math.round(eyebrow.left), eyebrowTop: Math.round(eyebrow.top),
      backWidth: Math.round(back.width),
      mainWidth: Math.round(document.querySelector('.workspace-main').clientWidth),
    };
  });
  const sequence = [hierarchy.heading, hierarchy.facts, hierarchy.position, hierarchy.sku,
    hierarchy.actions, hierarchy.issues, hierarchy.history];
  assert.deepEqual(sequence, [...sequence].sort((a, b) => a - b),
    `the reviewed order is heading -> summary -> position -> SKU -> actions -> issues -> history (${sequence})`);
  assert.ok(hierarchy.position < hierarchy.actions,
    'current position is operational data and outranks the action catalogue');
  assert.ok(hierarchy.sku < hierarchy.actions, 'so does the SKU detail');
  assert.equal(hierarchy.backLeft, hierarchy.eyebrowLeft,
    'the back control is left-aligned with the order identity');
  assert.ok(hierarchy.backWidth < hierarchy.mainWidth / 3,
    `the back control is shrink-wrapped, not a full-width bar (${hierarchy.backWidth})`);
  // Directly above the identity, close enough to read as part of it rather than as a control
  // belonging to the page in general.
  const backGap = hierarchy.eyebrowTop - hierarchy.backBottom;
  assert.ok(backGap >= 0 && backGap <= 24,
    `the back control sits immediately above the order identity (gap ${backGap}px)`);

  // ---- navigational actions are rows, commands are buttons ---------------------------------
  const weights = await page.evaluate(() => {
    const host = document.getElementById('detail-content');
    const rows = [...host.querySelectorAll('.utility-rows>.record-row')];
    const commands = [...host.querySelectorAll('.panel-grid .action-row>button')];
    const style = node => getComputedStyle(node);
    return {
      rowCount: rows.length,
      commandCount: commands.length,
      commandActions: commands.map(b => b.dataset.action),
      // A row reads as a list entry: no capsule, left-aligned, and a trailing chevron.
      rowShape: rows.map(row => ({
        action: row.dataset.action,
        name: row.textContent.trim(),
        justify: style(row).justifyContent,
        radius: parseFloat(style(row).borderRadius),
        background: style(row).backgroundColor,
        shadow: style(row).boxShadow,
        chevron: Boolean(row.querySelector('svg[aria-hidden=true] use')),
        chevronLast: row.lastElementChild.tagName.toLowerCase() === 'svg',
        divider: parseFloat(style(row).borderBottomWidth),
        height: Math.round(row.getBoundingClientRect().height),
      })),
      // A command still looks like a command.
      commandShape: commands.map(b => ({action: b.dataset.action,
        radius: parseFloat(style(b).borderRadius),
        background: style(b).backgroundColor})),
      groupHeights: [...host.querySelectorAll('.panel-grid>.utility-panel')]
        .map(panel => Math.round(panel.getBoundingClientRect().height)),
    };
  });
  assert.equal(weights.rowCount, 24, 'the navigational actions are compact rows');
  assert.equal(weights.commandCount, 3, 'and only the three real commands stay buttons');
  assert.deepEqual(weights.commandActions.sort(),
    ['edit-order', 'issue-material', 'new-production-change-request']);
  for (const row of weights.rowShape) {
    assert.equal(row.justify, 'flex-start', `${row.action} row is left-aligned`);
    assert.equal(row.radius, 0, `${row.action} row is not a capsule`);
    assert.equal(row.background, 'rgba(0, 0, 0, 0)', `${row.action} row carries no control surface`);
    assert.equal(row.shadow, 'none', `${row.action} row carries no elevation`);
    assert.equal(row.chevron, true, `${row.action} row says that it opens something`);
    assert.equal(row.chevronLast, true, `${row.action} chevron trails the label`);
    assert.ok(row.height <= 44, `${row.action} row is compact (${row.height})`);
    assert.ok(row.name.length > 0, `${row.action} row keeps its label as its accessible name`);
  }
  // The dividers, not gaps, give the list its rhythm: the last row in each group closes it.
  assert.ok(weights.rowShape.filter(row => row.divider === 0).length >= 3,
    'each group ends without a trailing divider');
  for (const command of weights.commandShape) {
    assert.ok(command.radius > 0, `${command.action} still reads as a button`);
    assert.notEqual(command.background, 'rgba(0, 0, 0, 0)');
  }
  // Every action a child-dialog module reaches is still reachable by its own accessible name.
  for (const label of ['Hasil cutting', 'Bundle', 'Sewing / makloon', 'Finishing', 'Final QC',
                       'Barang jadi', 'Gudang', 'Picking', 'Packing', 'Shipping', 'Retur',
                       'Adjustment', 'Stock opname', 'Reservasi jual', 'Selesai rework']) {
    assert.equal(await page.locator('#detail-content .panel-grid')
      .getByRole('button', {name: label, exact: true}).count(), 1,
      `"${label}" is still addressable as exactly one control`);
  }

  // ---- and the first viewport now reaches real SKU information ------------------------------
  await page.setViewportSize({width: 1440, height: 1000});
  await page.waitForTimeout(150);
  await page.evaluate(() => document.querySelector('.workspace-main').scrollTo(0, 0));
  const firstScreen = await page.evaluate(() => {
    const visible = selector => {
      const node = document.querySelector(selector);
      if (!node) return false;
      const box = node.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight + 1;
    };
    return {
      position: visible('#stage-balance-heading'),
      exceptions: visible('#detail-content .utility-panel .detail-grid-compact'),
      skuHeading: visible('#sku-detail-heading'),
      skuBalances: visible('#detail-content .sku-record .detail-grid-compact'),
      actionsBelowFold: (document.querySelector('#order-actions-heading')
        .getBoundingClientRect().top) > innerHeight * 0.55,
    };
  });
  assert.equal(firstScreen.position, true, 'current position is in the first viewport');
  assert.equal(firstScreen.exceptions, true, 'and so are the balances themselves');
  assert.equal(firstScreen.skuHeading, true, 'the SKU section is reached without scrolling');
  assert.equal(firstScreen.skuBalances, true, 'including real SKU balances');
  assert.equal(firstScreen.actionsBelowFold, true,
    'the action catalogue no longer dominates the first viewport');
  await page.setViewportSize({width: 1440, height: 900});
  await page.waitForTimeout(120);
  await shot('detail-1440-light');
  await firstViewport('detail-1440-firstviewport');
  await page.setViewportSize({width: 1440, height: 900});
  await theme('dark');
  await shot('detail-1440-dark');
  await theme('light');
  // The detail page on a phone: the action groups stack, the balances keep wrapping in columns
  // rather than becoming one balance per row, and nothing overflows the document.
  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(150);
  const detailMobile = await page.evaluate(() => {
    const host = document.getElementById('detail-content');
    const groups = [...host.querySelectorAll('.panel-grid>.utility-panel')]
      .map(panel => Math.round(panel.getBoundingClientRect().top));
    const balances = [...host.querySelectorAll('section .utility-panel .detail-grid-compact')]
      .slice(0, 1).flatMap(grid => [...grid.querySelectorAll('.detail-field')]
        .map(field => Math.round(field.getBoundingClientRect().top)));
    return {
      documentOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      groupsStacked: new Set(groups).size === groups.length,
      balanceRows: new Set(balances).size,
      balanceCount: balances.length,
      fits: host.getBoundingClientRect().right <= innerWidth + 1,
    };
  });
  assert.equal(detailMobile.documentOverflow, false, 'order detail does not overflow at 390');
  assert.equal(detailMobile.fits, true);
  assert.equal(detailMobile.groupsStacked, true, 'the three action groups stack on a phone');
  assert.ok(detailMobile.balanceRows < detailMobile.balanceCount,
    'stage balances still wrap in columns rather than one per row');
  await shot('detail-390-light');
  await page.setViewportSize({width: 1440, height: 900});
  await page.waitForTimeout(120);

  // Back restores the board and puts focus where it was.
  await page.getByRole('button', {name: 'Semua order', exact: true}).click();
  await ready();
  assert.equal(await page.evaluate(() => document.activeElement.id), 'search',
    'returning to the board restores focus to the search field');

  // ---- roles ------------------------------------------------------------------------------
  await login(viewer);
  await openSidebarDestination('Produksi');
  await ready();
  assert.equal(await page.locator('#new-order').isHidden(), true, 'a viewer cannot create orders');
  await page.getByRole('button', {name: new RegExp(order.reference)}).first().click();
  await page.locator('#detail-content h1').waitFor();
  const readOnly = await page.evaluate(() => ({
    groups: document.querySelectorAll('#detail-content .panel-grid>.utility-panel').length,
    writes: document.querySelectorAll('#detail-content [data-action="move"], '
      + '#detail-content [data-action="new-issue"], #detail-content [data-action="edit-order"], '
      + '#detail-content [data-action="issue-material"], #detail-content [data-action="reverse"], '
      + '#detail-content [data-action="resolve-issue"], '
      + '#detail-content [data-action="new-production-change-request"]').length,
    reads: document.querySelectorAll('#detail-content [data-action="requirements"]').length,
  }));
  assert.equal(readOnly.writes, 0, 'the redesign gives a viewer no write action');
  assert.equal(readOnly.groups, 3, 'a viewer sees the same grouping, only emptier');
  assert.equal(readOnly.reads, 1, 'and keeps the read-only views');
  await login(operator);
  await openSidebarDestination('Produksi');
  await ready();
  await page.getByRole('button', {name: new RegExp(order.reference)}).first().click();
  await page.locator('#detail-content h1').waitFor();
  const operatorActions = await page.evaluate(() => ({
    move: document.querySelectorAll('#detail-content [data-action="move"]').length,
    issueMaterial: document.querySelectorAll('#detail-content [data-action="issue-material"]').length,
    editOrder: document.querySelectorAll('#detail-content [data-action="edit-order"]').length,
  }));
  assert.ok(operatorActions.move > 0, 'an operator keeps the operational actions');
  assert.equal(operatorActions.issueMaterial, 1);
  assert.equal(operatorActions.editOrder, 0, 'and still cannot edit the order');
  await login(admin);
  await openSidebarDestination('Produksi');
  await ready();

  // ---- create order: presentation modernised, rules untouched ------------------------------
  await page.locator('#new-order').click();
  await page.locator('#dialog-content .field input').first().waitFor();
  const form = await page.evaluate(() => ({
    fields: [...document.querySelectorAll('#dialog-content .field>.field-label')]
      .map(l => l.textContent.trim()),
    lines: document.querySelectorAll('#order-lines .line-input').length,
    lineShape: [...document.querySelectorAll('#order-lines .line-input:first-child>*')]
      .map(node => node.className || node.tagName.toLowerCase()),
    help: Boolean(document.querySelector('#dialog-content .field-help')),
    remove: document.querySelector('#order-lines .line-input button').className,
  }));
  assert.deepEqual(form.fields.slice(0, 4),
    ['Referensi order', 'Nama order', 'Penanggung jawab', 'Target selesai']);
  assert.equal(form.lines, 1, 'the form opens with one SKU line');
  assert.deepEqual(form.lineShape, ['field', 'field', 'action-quiet'],
    'a line is SKU, quantity and a quiet remove - not three cards');
  assert.equal(form.help, true);
  assert.match(form.remove, /action-quiet/, 'removing a line is quiet, not destructive-red');
  await shot('create-order-desktop');
  // The minimum-line rule, the duplicate rule and the add/remove behaviour.
  await page.getByRole('button', {name: 'Hapus baris SKU', exact: true}).first().click();
  await page.getByText('Order memerlukan minimal satu SKU.').waitFor();
  assert.equal(await page.locator('#order-lines .line-input').count(), 1,
    'the last SKU line cannot be removed');
  await page.getByRole('button', {name: 'Tambah baris SKU', exact: true}).click();
  assert.equal(await page.locator('#order-lines .line-input').count(), 2);
  const products = await apiGet('/api/products?limit=100&offset=0');
  await page.getByLabel('SKU', {exact: true}).nth(0).selectOption(products[0].id);
  await page.getByLabel('SKU', {exact: true}).nth(1).selectOption(products[0].id);
  await page.getByLabel('Jumlah', {exact: true}).nth(0).fill('5');
  await page.getByLabel('Jumlah', {exact: true}).nth(1).fill('5');
  await page.getByLabel('Referensi order', {exact: true}).fill(`A61-DUP-${Date.now()}`);
  await page.getByLabel('Nama order', {exact: true}).fill('CONTOH duplikat SKU');
  await page.getByLabel('Target selesai', {exact: true}).fill('2099-01-01');
  await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.getByText('SKU yang sama cukup satu baris. Gabungkan jumlahnya.').waitFor();
  assert.equal(await page.locator('dialog[open]').count(), 1,
    'a rejected duplicate keeps the form open and the work intact');
  await page.getByRole('button', {name: 'Hapus baris SKU', exact: true}).nth(1).click();
  assert.equal(await page.locator('#order-lines .line-input').count(), 1);
  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(150);
  const mobileForm = await page.evaluate(() => {
    const dialog = document.querySelector('dialog[open]');
    return {fits: dialog.getBoundingClientRect().width <= innerWidth
        && dialog.scrollWidth <= dialog.clientWidth,
      removeVisible: document.querySelector('#order-lines .line-input button')
        .getBoundingClientRect().width > 0};
  });
  assert.equal(mobileForm.fits, true, 'the create-order dialog fits a phone');
  assert.equal(mobileForm.removeVisible, true, 'and removing a line stays reachable');
  await page.screenshot({path: path.join(shots, 'a61-create-order-mobile.png')});
  await page.keyboard.press('Escape');
  await page.locator('dialog').waitFor({state: 'hidden'}).catch(() => {});
  await page.setViewportSize({width: 1440, height: 900});
  await ready();
  // The real submission path, with its existing idempotency contract, still works.
  const created = `A61-OK-${Date.now()}`;
  await page.locator('#new-order').click();
  await page.locator('#dialog-content .field input').first().waitFor();
  await page.getByLabel('Referensi order', {exact: true}).fill(created);
  await page.getByLabel('Nama order', {exact: true}).fill('CONTOH A6.1 order baru');
  await page.getByLabel('Target selesai', {exact: true}).fill('2099-06-01');
  await page.getByLabel('SKU', {exact: true}).first().selectOption(products[0].id);
  await page.getByLabel('Jumlah', {exact: true}).first().fill('7');
  await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.locator('#detail-content h1').waitFor();
  assert.equal(await page.locator('#detail-content .workspace-eyebrow').textContent(), created,
    'a saved order opens its own detail page, as before');
  assert.equal(await page.evaluate(() => sessionStorage.length), 0,
    'the pending-write record is cleared once the save is confirmed');
  await openSidebarDestination('Produksi');
  await ready();

  // ---- responsive: the required widths, plus 320 at 200% text -------------------------------
  const layout = async label => page.evaluate(name => {
    const board = document.getElementById('board-view');
    const list = document.getElementById('order-list');
    const scroller = getComputedStyle(list).overflowX;
    const offenders = [...document.querySelectorAll('#board-view *')].filter(el => {
      if (!el.getClientRects().length) return false;
      if (el.scrollWidth > el.clientWidth + 1 && el !== list) {
        // Content inside the table scroller is meant to exceed the viewport.
        for (let node = el; node; node = node.parentElement)
          if (node !== el && ['auto', 'scroll'].includes(getComputedStyle(node).overflowX)) return false;
        return true;
      }
      return false;
    }).map(el => `${el.tagName.toLowerCase()}.${String(el.className).split(/\s+/)[0]}`);
    return {name,
      documentOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      boardFits: board.getBoundingClientRect().right <= innerWidth + 1,
      tableScrolls: ['auto', 'scroll'].includes(scroller),
      metricColumns: new Set([...document.querySelectorAll('#summary>div')]
        .map(el => Math.round(el.getBoundingClientRect().top))).size,
      offenders: [...new Set(offenders)],
      identifierLines: [...document.querySelectorAll('#order-list .reference')]
        .map(el => Math.round(el.getBoundingClientRect().height
          / parseFloat(getComputedStyle(el).lineHeight))),
    };
  }, label);
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({width, height: width < 500 ? 844 : 900});
    await page.waitForTimeout(120);
    const state = await layout(String(width));
    assert.equal(state.documentOverflow, false, `${width}: the document never scrolls sideways`);
    assert.equal(state.boardFits, true, `${width}: the workspace fits the viewport`);
    assert.deepEqual(state.offenders, [], `${width}: nothing clips inside itself`);
    if (width <= 980) assert.equal(state.tableScrolls, true,
      `${width}: the table keeps its columns and hands the overflow to its surface`);
    // No identifier is ever crushed to one character per line.
    for (const lines of state.identifierLines) {
      assert.ok(lines <= 2, `${width}: an order reference wrapped onto ${lines} lines`);
    }
    if ([1440, 1024, 768, 390].includes(width)) await shot(`board-${width}-light`);
  }
  // ---- and the order list reaches the first viewport with real rows in it -------------------
  await page.setViewportSize({width: 1440, height: 1000});
  await page.waitForTimeout(150);
  await page.evaluate(() => document.querySelector('.workspace-main').scrollTo(0, 0));
  const boardFirstScreen = await page.evaluate(() => {
    const box = selector => {
      const node = document.querySelector(selector);
      return node ? Math.round(node.getBoundingClientRect().top) : null;
    };
    const rows = [...document.querySelectorAll('#order-list .order-row')]
      .filter(row => row.getBoundingClientRect().bottom <= innerHeight + 1).length;
    return {
      heading: box('#board-view .workspace-title'),
      strip: box('#summary'),
      note: box('#issues-summary'),
      bar: box('#search-form'),
      hint: box('#production-filter-hint'),
      section: box('#production-orders-heading'),
      header: box('#order-list .data-header'),
      stripBottom: Math.round(document.getElementById('summary').getBoundingClientRect().bottom),
      noteHeight: Math.round(document.getElementById('issues-summary').getBoundingClientRect().height),
      hintHeight: Math.round(document.getElementById('production-filter-hint').getBoundingClientRect().height),
      rowsInView: rows,
      total: document.querySelectorAll('#order-list .order-row').length,
      viewport: innerHeight,
    };
  });
  const boardOrder = [boardFirstScreen.heading, boardFirstScreen.strip, boardFirstScreen.note,
    boardFirstScreen.bar, boardFirstScreen.hint, boardFirstScreen.section, boardFirstScreen.header];
  assert.deepEqual(boardOrder, [...boardOrder].sort((a, b) => a - b),
    `board order is heading -> metrics -> issues -> command bar -> hint -> section -> table (${boardOrder})`);
  console.log('A6.1 board first viewport:', JSON.stringify(boardFirstScreen));
  // The guard that actually means something. An absolute pixel budget for the section heading
  // would mostly be measuring the frozen masthead chrome above it (~103px), so what is pinned is
  // the part A6.1 owns: everything BETWEEN the metric strip and the order list. That run is the
  // command bar plus the two informational strips plus their section gaps, and it is where the
  // vertical weight the review objected to lived.
  const betweenStripAndTable = boardFirstScreen.section - boardFirstScreen.stripBottom;
  assert.ok(betweenStripAndTable <= 200,
    `the command bar and the two informational strips stay compact (${betweenStripAndTable}px)`);
  assert.ok(boardFirstScreen.noteHeight <= 34,
    `the cleared issue note is a single row (${boardFirstScreen.noteHeight}px)`);
  assert.ok(boardFirstScreen.hintHeight <= 40,
    `the stage-filter hint reads as a caption (${boardFirstScreen.hintHeight}px)`);
  assert.ok(boardFirstScreen.header < boardFirstScreen.viewport * 0.56,
    `the table starts in the upper half of the first viewport (${boardFirstScreen.header}px)`);
  assert.ok(boardFirstScreen.rowsInView >= Math.min(5, boardFirstScreen.total),
    `the first viewport shows real order rows (${boardFirstScreen.rowsInView} of ${boardFirstScreen.total})`);
  await firstViewport('board-1440-firstviewport');
  await page.setViewportSize({width: 1440, height: 900});
  await page.waitForTimeout(120);
  await page.setViewportSize({width: 320, height: 844});
  await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
  await page.waitForTimeout(150);
  const zoomed = await layout('320@200%');
  assert.equal(zoomed.documentOverflow, false, '320 at 200% text: no document overflow');
  assert.deepEqual(zoomed.offenders, [], '320 at 200% text: nothing clips inside itself');
  // Every control that belongs to the page CHROME - the heading actions, the command bar, the
  // pagination - has to be reachable without sideways movement. Controls inside the table are
  // held to a different and equally explicit promise: the surface around them scrolls, which is
  // asserted separately, and is the documented narrow-width strategy rather than a clipped
  // action.
  const zoom = await page.evaluate(() => {
    const scrolled = el => {
      for (let node = el.parentElement; node; node = node.parentElement)
        if (['auto', 'scroll'].includes(getComputedStyle(node).overflowX)) return true;
      return false;
    };
    const controls = [...document.querySelectorAll('#board-view button, #board-view select, #board-view input')]
      .filter(el => el.getClientRects().length);
    const list = document.getElementById('order-list');
    return {
      chrome: controls.filter(el => !scrolled(el))
        .map(el => ({name: (el.textContent || el.id).trim().slice(0, 24),
          right: el.getBoundingClientRect().right})),
      inTable: controls.filter(scrolled).length,
      tableReachable: list.scrollWidth > list.clientWidth
        && ['auto', 'scroll'].includes(getComputedStyle(list).overflowX),
    };
  });
  for (const control of zoom.chrome) {
    assert.ok(control.right <= 321, `320 at 200%: "${control.name}" stays reachable (${control.right})`);
  }
  assert.ok(zoom.inTable > 0, 'the rows still carry their controls at 320 and 200% text');
  assert.equal(zoom.tableReachable, true,
    'and the surface around them scrolls, so none of them is clipped away');
  await shot('board-320-light-200');
  await page.evaluate(() => {document.documentElement.style.fontSize = '';});
  await page.setViewportSize({width: 1440, height: 900});
  await ready();

  // ---- dark mode is tuned, not inverted ---------------------------------------------------
  await theme('dark');
  await ready();
  const dark = await page.evaluate(() => {
    const list = document.getElementById('order-list');
    const row = document.querySelector('#order-list .order-row');
    const header = document.querySelector('#order-list .data-header th');
    const chip = document.querySelector('#order-list .status-chip');
    const focusProbe = document.getElementById('search');
    focusProbe.focus();
    return {
      surface: getComputedStyle(list).backgroundColor,
      divider: getComputedStyle(row.firstElementChild).borderBottomColor,
      header: getComputedStyle(header).backgroundColor,
      headerInk: getComputedStyle(header).color,
      chipInk: getComputedStyle(chip).color,
      chipTint: getComputedStyle(chip).backgroundColor,
      progressTrack: getComputedStyle(document.querySelector('#order-list .progress-native')).backgroundColor,
      focusRing: getComputedStyle(focusProbe).outlineStyle,
    };
  });
  assert.notEqual(dark.divider, 'rgba(0, 0, 0, 0)', 'rows stay separated in dark mode');
  assert.notEqual(dark.header, dark.surface, 'the table header stays distinguishable');
  assert.notEqual(dark.headerInk, dark.surface);
  assert.notEqual(dark.chipInk, dark.chipTint, 'status chips stay readable');
  assert.notEqual(dark.progressTrack, 'rgba(0, 0, 0, 0)', 'the progress track keeps a body');
  await shot('board-1440-dark');
  await theme('light');
  await ready();

  // ---- forced colours: status and progress never rely on colour alone ----------------------
  await page.emulateMedia({forcedColors: 'active'});
  await page.waitForTimeout(150);
  const forced = await page.evaluate(() => {
    const chip = document.querySelector('#order-list .status-chip');
    const meter = document.querySelector('#order-list .progress-native');
    return {
      chipBorder: parseFloat(getComputedStyle(chip).borderTopWidth),
      dot: Boolean(chip.querySelector('.status-dot')),
      dotPainted: getComputedStyle(chip.querySelector('.status-dot')).backgroundColor,
      meterBorder: parseFloat(getComputedStyle(meter).borderTopWidth),
      statusText: chip.textContent.trim().length,
      rowBorder: parseFloat(getComputedStyle(
        document.querySelector('#order-list .order-row').firstElementChild).borderBottomWidth),
      buttonBorder: parseFloat(getComputedStyle(document.getElementById('refresh')).borderTopWidth),
    };
  });
  assert.ok(forced.chipBorder > 0, 'a status chip keeps a real border under forced colours');
  assert.equal(forced.dot, true, 'and keeps its non-colour channel');
  assert.notEqual(forced.dotPainted, 'rgba(0, 0, 0, 0)');
  assert.ok(forced.statusText > 0, 'status is never conveyed by colour alone');
  assert.ok(forced.meterBorder > 0, 'progress keeps a visible structure');
  assert.ok(forced.rowBorder > 0, 'rows keep their separation');
  assert.ok(forced.buttonBorder > 0, 'controls stay visible');
  await page.emulateMedia({forcedColors: 'none'});

  // ---- reduced transparency makes the workspace solid, where the engine applies it ---------
  // Asserted only when the preference is genuinely active. The option is accepted by the driver
  // but this Chromium build does not evaluate `prefers-reduced-transparency`, so measuring
  // regardless would assert against the ordinary rendering and pass for the wrong reason. The
  // withdrawal itself is pinned statically in
  // tests/test_apple27_modern_workspace_foundation_contract.py.
  await page.emulateMedia({reducedTransparency: 'reduce'}).catch(() => {});
  await page.waitForTimeout(150);
  const transparency = await page.evaluate(() => {
    const alpha = value => {
      const parts = (value.match(/[\d.]+/g) || []).map(Number);
      return parts.length > 3 ? parts[3] : 1;
    };
    return {
      applied: matchMedia('(prefers-reduced-transparency: reduce)').matches,
      recognised: matchMedia('(prefers-reduced-transparency: reduce)').media
        !== 'not all',
      list: alpha(getComputedStyle(document.getElementById('order-list')).backgroundColor),
      bar: alpha(getComputedStyle(document.getElementById('search-form')).backgroundColor),
      blur: getComputedStyle(document.getElementById('search-form')).backdropFilter,
    };
  });
  assert.equal(transparency.recognised, true, 'the engine parses the transparency preference');
  if (transparency.applied) {
    assert.equal(transparency.list, 1, 'the data surface becomes fully opaque');
    assert.equal(transparency.bar, 1, 'and so does the command bar');
    assert.ok(['none', ''].includes(transparency.blur), 'the blur is withdrawn');
  } else {
    // The enhancement is at least confirmed to BE an enhancement: the ordinary rendering is
    // translucent, so there is something for the preference to withdraw.
    assert.ok(transparency.list < 1, 'the data surface is translucent by default');
  }
  await page.emulateMedia({reducedTransparency: 'no-preference'}).catch(() => {});

  // ---- reduced motion, and no idle frame loop ----------------------------------------------
  await page.emulateMedia({reducedMotion: 'reduce'});
  await ready();
  const still = await page.evaluate(() => ({
    row: getComputedStyle(document.querySelector('#order-list .order-row')).transitionDuration,
    list: getComputedStyle(document.getElementById('order-list')).transitionDuration,
    animated: [...document.querySelectorAll('#board-view *')]
      .filter(el => getComputedStyle(el).animationName !== 'none').length,
  }));
  assert.equal(still.animated, 0, 'no element on the board animates');
  assert.equal(still.row, '0s', 'reduced motion removes the row transition');
  assert.equal(still.list, '0s');
  // A settled board must not be holding an animation frame open.
  await page.evaluate(() => {
    window.__a61Frames = 0;
    window.__a61Raf = window.requestAnimationFrame;
    window.requestAnimationFrame = callback => {window.__a61Frames++; return window.__a61Raf(callback);};
  });
  await page.waitForTimeout(1200);
  const frames = await page.evaluate(() => {
    const count = window.__a61Frames;
    window.requestAnimationFrame = window.__a61Raf;
    delete window.__a61Raf; delete window.__a61Frames;
    return count;
  });
  assert.ok(frames <= 2, `a settled Produksi board schedules no idle frames (saw ${frames})`);

  // ---- the shell, the lens and the scroll architecture are untouched by this page -----------
  const shell = await page.evaluate(() => {
    const main = document.querySelector('.workspace-main');
    return {
      lens: document.querySelectorAll('#nav-selection-lens').length,
      current: document.querySelector('#board-home').getAttribute('aria-current'),
      mainScrolls: getComputedStyle(main).overflow,
      bodyHidden: getComputedStyle(document.body).overflow,
      documentScrollbar: document.documentElement.scrollHeight
        <= document.documentElement.clientHeight + 1,
      cta: Boolean(document.querySelector('.sidebar-cta')),
      window: Boolean(document.querySelector('.workspace-window')),
    };
  });
  assert.equal(shell.lens, 1, 'exactly one navigation lens');
  assert.equal(shell.current, 'page', 'Produksi is the current destination');
  assert.equal(shell.mainScrolls, 'auto', 'the main region is still the scrolling region');
  assert.equal(shell.bodyHidden, 'hidden', 'the document itself still does not scroll');
  assert.equal(shell.documentScrollbar, true, 'no second app-level scrollbar appeared');
  assert.equal(shell.cta, true);
  assert.equal(shell.window, true);

  await page.emulateMedia({reducedMotion: 'no-preference'});
  await login(admin);
  console.log('A6.1 Produksi modern workspace browser QA PASS: heading identity, four real '
    + 'metrics with real units and data-driven tones, global summary under filters, issue '
    + 'attention surface and its blocked-status action, every filter query, reset, search submit '
    + 'and Enter with no per-keystroke query, filtered miss vs genuinely empty board vs role, '
    + 'load failure, overtaken-response guard, pagination, refresh-in-place, order detail '
    + '(eyebrow/title, four facts, three action groups with every action, stage balances, SKU '
    + 'balances, timeline, focus restore), admin/operator/viewer, create-order presentation with '
    + 'minimum-line/duplicate/idempotency rules intact, 1440/1024/768/390/320 and 320 at 200% '
    + 'text, dark mode, forced colours, reduced transparency, reduced motion, zero idle frames, '
    + 'shell/lens/scroll architecture unchanged.');
};
