const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, admin, operator, viewer, openSidebarDestination, work}) => {
  await login(admin);
  const scanners = [
    {name:'Scan bundle', prefix:'bundle-scan', endpoint:'bundles'},
    {name:'Scan barang jadi', prefix:'finished-goods-scan', endpoint:'finished-goods-receipts'}
  ];
  for (const {name, prefix, endpoint} of scanners) {
    await openSidebarDestination(name);
    const input = page.locator('#'+prefix+'-code');
    const result = page.locator('#'+prefix+'-result');
    const message = page.locator('#'+prefix+'-message');
    assert.equal(await result.textContent(),'');
    assert.match(await message.textContent(),/Belum ada hasil scan/);
    await input.fill('NOT-FOUND-UTILITY'); await input.press('Enter');
    await page.locator('#'+prefix+'-error:not([hidden])').waitFor();
    assert.match(await page.locator('#'+prefix+'-error').textContent(),/tidak ditemukan/);
    assert.equal(await message.isHidden(),true);

    // Hold a scan across leaving and re-entering the same page; checking view alone is insufficient.
    let release, started, finished, requests = 0;
    const pending = new Promise(resolve => started = resolve);
    const held = new Promise(resolve => release = resolve);
    const delivered = new Promise(resolve => finished = resolve);
    const pattern = '**/api/'+endpoint+'/scan?*';
    const record = {id:'synthetic', reference:'QR <img src=x onerror=alert(1)>', sku:'SKU <aman>',
      size:'M', quantity:5, received_quantity:5, order_reference:'ORDER <aman>'};
    await page.route(pattern, async route => {
      requests++;
      const first = requests === 1;
      if (first) { started(); await held; }
      await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
        ...record, reference:first?'STALE SCAN':record.reference
      })});
      if (first) finished();
    });
    await input.press('Enter'); await pending;
    assert.match(await message.textContent(),/Mencari/);
    await page.locator('#'+prefix+'-form').evaluate(form => form.requestSubmit());
    assert.equal(requests,1,'repeated submit must not dispatch a second read while busy');
    await openSidebarDestination('Produksi');
    await openSidebarDestination(name);
    await input.press('Enter');
    await result.getByText(record.reference,{exact:true}).waitFor();
    release(); await delivered;
    await page.waitForTimeout(150);
    assert.equal(await result.locator('img').count(),0,'scan reference must be escaped');
    assert.equal(await result.getByText('STALE SCAN',{exact:true}).count(),0);
    assert.equal(await result.getByText(record.reference,{exact:true}).count(),1);
    assert.equal(await page.locator('#dialog').getAttribute('open'),null);
    assert.equal(await page.locator('#'+prefix+'-form button').isEnabled(),true);
    await page.unroute(pattern);
  }

  // Every migrated page is usable with its real result/controls at all roadmap sizes.
  for (const [name, prefix] of [...scanners.map(row => [row.name,row.prefix]),['Cadangan data','backup']]) {
    for (const [width, scale, theme] of [[1440,100,'light'],[1440,100,'dark'],[1024,100,'light'],
      [768,100,'light'],[390,100,'light'],[320,200,'light'],[320,200,'dark']]) {
      await page.setViewportSize({width,height:1000});
      await page.evaluate(value => document.documentElement.style.fontSize=value+'%',scale);
      if (await page.locator('html').getAttribute('data-theme') !== theme) await page.locator('#theme').click();
      await openSidebarDestination(name);
      assert.equal(await page.locator('#dialog').getAttribute('open'),null);
      assert.deepEqual(await page.locator('.workspace-main > section').evaluateAll(sections =>
        sections.filter(section => !section.hidden).map(section => section.id)),[prefix+'-view']);
      assert.equal(await page.locator('#app-sidebar [aria-current="page"]').count(),1);
      assert.equal(await page.locator('#'+(prefix==='backup'?'backup':'scan-'+prefix.replace(/-scan$/,''))).getAttribute('aria-current'),'page');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),true,
        `${name} overflow at ${width}px / ${scale}% / ${theme}`);
      if (width <= 390) {
        assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'),'false');
        assert.equal(await page.locator('#'+prefix+'-view h1').evaluate(heading => document.activeElement===heading),true);
      }
      if ([1440,390,320].includes(width)) await page.screenshot({path:path.join(
        process.env.BEELOFT_QA_SCREENSHOTS||work,`beeloft-${prefix}-${width}-${scale}-${theme}.png`),fullPage:true});
    }
  }
  await page.evaluate(() => document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  if (await page.locator('html').getAttribute('data-theme') !== 'light') await page.locator('#theme').click();

  let releaseBackup, startedBackup, finishedBackup, downloads=0, backupRequests=0;
  const backupStarted = new Promise(resolve => startedBackup=resolve);
  const backupHeld = new Promise(resolve => releaseBackup=resolve);
  const backupDelivered = new Promise(resolve => finishedBackup=resolve);
  const onDownload = () => downloads++;
  page.on('download',onDownload);
  await page.route('**/api/backup',async route => {
    backupRequests++; startedBackup(); await backupHeld;
    await route.fulfill({status:200,contentType:'application/vnd.sqlite3',body:'synthetic stale backup'});
    finishedBackup();
  });
  await openSidebarDestination('Cadangan data');
  assert.equal(backupRequests,0,'opening backup must not download');
  await page.locator('#download-backup').click(); await backupStarted;
  await page.locator('#download-backup').evaluate(button => button.click());
  assert.equal(backupRequests,1,'double click must not duplicate the backup request');
  await openSidebarDestination('Produksi');
  await openSidebarDestination('Cadangan data');
  releaseBackup(); await backupDelivered; await page.waitForTimeout(150);
  assert.equal(downloads,0,'a stale backup must not start a download after re-entry');
  assert.equal(await page.locator('#backup-message').isHidden(),true);
  assert.equal(await page.locator('#download-backup').isEnabled(),true);
  page.off('download',onDownload); await page.unroute('**/api/backup');

  for (const key of [operator,viewer]) {
    await login(key);
    assert.equal(await page.locator('#backup').isHidden(),true);
    await page.locator('#backup').evaluate(button => button.click());
    assert.equal(await page.locator('#backup-view').isHidden(),true);
    for (const {name,prefix} of scanners) {
      await openSidebarDestination(name);
      assert.equal(await page.locator('#'+prefix+'-code').inputValue(),'');
      assert.equal(await page.locator('#'+prefix+'-result').textContent(),'');
      assert.equal(await page.locator('#'+prefix+'-view').isVisible(),true);
    }
  }
  // Auth failures use the existing expiry flow and clear persistent scanner state.
  await page.route('**/api/finished-goods-receipts/scan?*',route => route.fulfill({
    status:401,contentType:'application/json',body:JSON.stringify({detail:'Sesi berakhir'})
  }));
  await page.locator('#finished-goods-scan-code').fill('EXPIRED');
  await page.locator('#finished-goods-scan-code').press('Enter');
  await page.locator('#login-view').waitFor();
  assert.equal(await page.locator('#finished-goods-scan-code').inputValue(),'');
  await page.unroute('**/api/finished-goods-receipts/scan?*');
  await login(admin);
  console.log('Workspace utilities QA PASS: scanner page state, keyboard/retry, escaping, stale scans/download, roles, session reset, mobile focus, light/dark reflow.');
};
