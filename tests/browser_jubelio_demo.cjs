const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, admin, viewer, apiGet, apiPost, openSidebarDestination, work}) => {
  await page.keyboard.press('Escape');
  if (await page.getByRole('button', {name: 'Keluar', exact: true}).isVisible()) {
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
  }
  await login(admin);

  const goto = async (name) => {
    if (openSidebarDestination) {
      await openSidebarDestination(name);
    } else {
      const id = name === 'Command center' ? '#command-center'
        : name === 'Integrasi' ? '#integrations'
        : name === 'Master SKU' ? '#products' : '';
      if (id) await page.locator(id).click();
      else await page.getByRole('button', {name, exact: true}).click();
    }
  };

  // 1. Open Integrasi and explicitly activate demo on this database.
  await goto('Integrasi');
  await page.getByRole('heading', {name: 'Integrasi', exact: true}).waitFor();
  await page.getByText('Jubelio Demo · Simulasi', {exact: true}).waitFor();
  await page.getByRole('button', {name: 'Aktifkan demo', exact: true}).click();
  await page.locator('#main:not([aria-busy])').waitFor();
  await page.getByText('Skenario 0', {exact: false}).waitFor();

  // 2. Perform baseline sync
  const syncBtn = page.getByRole('button', {name: 'Sinkronkan sekarang', exact: true});
  await syncBtn.waitFor();
  await syncBtn.click();
  await page.locator('#main:not([aria-busy])').waitFor();
  await page.getByText('12 record dikarantina', {exact: false}).waitFor();
  await page.getByText('112 diterima · 8 karantina', {exact: false}).waitFor();
  await page.getByText('Jubelio Demo · Simulasi', {exact: true}).waitFor();

  // 3. Inspect Command Center
  await goto('Command center');
  await page.getByRole('heading', {name: 'Command center', exact: true}).waitFor();
  await page.locator('#command-center-summary dd').first().waitFor();
  await page.locator('#command-center-channels .channel-name').filter({hasText: 'Shopee'}).waitFor();
  await page.locator('#command-center-channels .channel-name').filter({hasText: 'Tokopedia'}).waitFor();
  await page.locator('#command-center-channels .channel-name').filter({hasText: 'TikTok Shop'}).waitFor();

  // 4. Return to Integrasi and inspect Order detail
  await goto('Integrasi');
  await page.getByRole('button', {name: 'Order & penjualan Jubelio', exact: true}).click();
  await page.locator('#dialog').getByRole('heading', {name: 'Order & penjualan Jubelio', exact: true}).waitFor();
  await page.locator('#dialog').getByText('Ada order dikarantina', {exact: false}).waitFor();
  await page.locator('#dialog').getByText('Order diterima').first().waitFor();
  await page.keyboard.press('Escape');

  // 5. Inspect Stock Reconciliation
  await page.getByRole('button', {name: 'Rekonsiliasi stok Jubelio', exact: true}).click();
  await page.locator('#dialog').getByRole('heading', {name: 'Rekonsiliasi stok Jubelio', exact: true}).waitFor();
  await page.locator('#dialog').getByText('SKU cocok').first().waitFor();
  await page.locator('#dialog').getByText('JUB-SKU-BIMO-NAVY-L', {exact: false}).waitFor();
  await page.keyboard.press('Escape');

  // 6. Advance scenario to introduce new orders, status changes, stock changes, and returns.
  await goto('Integrasi');
  const nextBtn = page.getByRole('button', {name: 'Jalankan skenario berikutnya', exact: true});
  await nextBtn.waitFor();
  await nextBtn.click();
  await page.locator('#main:not([aria-busy])').waitFor();
  await page.getByText('Skenario 2', {exact: false}).waitFor();
  assert.equal((await apiGet('/api/integrations/jubelio/order-summary')).summary.accepted_orders, 136);

  // 7. Map both previously quarantined SKUs, then re-evaluate into new complete snapshots.
  await goto('Master SKU');
  await page.getByRole('heading', {name: 'Master SKU', exact: true}).waitFor();
  for (const [sku, externalId, externalSku] of [
    ['DEMO-BIMO-PANTS-L', 'JUB-EXT-025', 'JUB-SKU-BIMO-NAVY-L'],
    ['DEMO-CACA-DRESS-S', 'JUB-EXT-019', 'JUB-SKU-CACA-SAGE-S']
  ]) {
    const row = page.getByRole('button', {name: `Jubelio ${sku}`, exact: true});
    await row.waitFor();
    await row.click();
    await page.getByRole('heading', {name: 'Mapping SKU Jubelio', exact: true}).waitFor();
    await page.getByRole('button', {name: 'Hubungkan Jubelio', exact: true}).click();
    await page.getByLabel('ID eksternal Jubelio', {exact: true}).fill(externalId);
    await page.getByLabel('SKU Jubelio', {exact: true}).fill(externalSku);
    await page.getByLabel('Alasan mapping', {exact: true}).fill('Pemetaan demo perbaikan karantina');
    await page.getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
    await page.getByRole('heading', {name: 'Mapping SKU Jubelio', exact: true}).waitFor();
    // The saved form closes and the mapping dialog reopens with a loading body; wait for the
    // loaded mapping, then make sure the dialog is really gone before the next row is clicked,
    // otherwise the still-open dialog intercepts that click.
    await page.locator('#dialog-content .status-chip').filter({hasText: 'Terhubung'}).waitFor();
    await page.keyboard.press('Escape');
    await page.locator('#dialog').waitFor({state: 'hidden'});
  }

  await goto('Integrasi');
  await page.getByRole('button', {name: 'Sinkronkan sekarang', exact: true}).click();
  await page.locator('#main:not([aria-busy])').waitFor();
  await page.getByText('Skenario 2 · succeeded', {exact: false}).waitFor();
  for (const [url, acceptedKey, rejectedKey, accepted] of [
    ['/api/integrations/jubelio/finished-goods-reconciliation', 'accepted_items', 'quarantined', 30],
    ['/api/integrations/jubelio/order-summary', 'accepted_orders', 'quarantined_orders', 145],
    ['/api/integrations/jubelio/return-summary', 'accepted_returns', 'quarantined_returns', 6],
    ['/api/integrations/jubelio/listing-summary', 'accepted_listings', 'quarantined_listings', 30]
  ]) {
    const result = await apiGet(url);
    if (url.endsWith('finished-goods-reconciliation')) {
      assert.equal(result.items.length, 31);
      assert.equal(result.quarantine.length, 0);
    } else {
      assert.equal(result.summary[acceptedKey], accepted);
      assert.equal(result.summary[rejectedKey], 0);
    }
  }
  const history = await apiGet('/api/integration-sync-runs?limit=100&system=jubelio');
  assert.ok(history.length >= 12);

  // 8. Mobile responsive / zoom verification
  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => document.documentElement.style.fontSize = '200%');
  assert.ok(await page.evaluate(() => document.body.scrollWidth <= window.innerWidth + 20));
  await page.screenshot({path: path.join(process.env.BEELOFT_QA_SCREENSHOTS || work, 'beeloft-jubelio-demo-mobile.png')});
  await page.evaluate(() => document.documentElement.style.fontSize = '');
  await page.setViewportSize({width: 1440, height: 1000});

  console.log('Jubelio demo browser QA PASS: activation, baseline, command center, quarantine mapping, resync, next scenario.');
};
