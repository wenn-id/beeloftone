const { chromium } = require(process.env.BEELOFT_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = process.env.BEELOFT_QA_BASE;
const work = process.env.BEELOFT_QA_WORK;
assert.ok(base && work && process.env.BEELOFT_QA_CREDENTIALS, 'Run through tests/run_browser.py with an isolated demo database.');
const creds = JSON.parse(fs.readFileSync(process.env.BEELOFT_QA_CREDENTIALS,'utf8').replace(/^\uFEFF/,''));
const admin = creds.users[0].api_key, operator = creds.users[1].api_key, viewer = creds.users[2].api_key;

(async () => {
  const browser = await chromium.launch({headless:true,channel:process.env.BEELOFT_BROWSER_CHANNEL || 'msedge'});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  async function login(key) {
    await page.getByLabel('Kunci akses',{exact:true}).fill(key);
    await page.getByRole('button',{name:'Buka ruang produksi',exact:true}).click();
    await page.getByRole('heading',{name:'Yang sedang dikerjakan.'}).waitFor();
    await page.locator('#summary dd').first().waitFor();
  }
  async function apiGet(url) {
    const response = await fetch(base+url,{headers:{'X-API-Key':admin}});
    assert.equal(response.status,200); return response.json();
  }
  await page.goto(base);
  await page.getByLabel('Kunci akses',{exact:true}).fill('invalid');
  await page.getByRole('button',{name:'Buka ruang produksi',exact:true}).click();
  await page.locator('#login-error:not([hidden])').waitFor();
  await login(admin);
  await page.getByLabel('Status',{exact:true}).selectOption('overdue');
  await page.waitForFunction(() => document.querySelectorAll('.order-row').length === 1 && !document.getElementById('order-list').hidden);
  assert.equal((await page.locator('.order-row').innerText()).includes('DEMO-PROD-002'),true);
  await page.getByLabel('Status',{exact:true}).selectOption('all');
  await page.waitForFunction(() => document.querySelectorAll('.order-row').length === 3 && !document.getElementById('order-list').hidden);
  let failBoard = true;
  await page.route('**/api/production-board?*',async route => {
    if (failBoard) { failBoard=false; await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Simulasi koneksi terputus'})}); }
    else await route.continue();
  });
  await page.getByRole('button',{name:'Muat ulang',exact:true}).click();
  await page.getByText('Simulasi koneksi terputus',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Muat ulang',exact:true}).click();
  await page.waitForFunction(() => !document.getElementById('order-list').hidden);
  let releaseProducts, signalProducts, finishProducts;
  const productsStarted = new Promise(resolve => signalProducts = resolve);
  const productsReleased = new Promise(resolve => releaseProducts = resolve);
  const productsFinished = new Promise(resolve => finishProducts = resolve);
  let delayProducts = true;
  await page.route('**/api/products?*', async route => {
    if (delayProducts) {
      delayProducts = false;
      const response = await route.fetch(); signalProducts();
      await productsReleased; await route.fulfill({response}); finishProducts();
    } else await route.continue();
  });
  await page.getByRole('button',{name:'Master SKU',exact:true}).click();
  await productsStarted;
  await page.getByRole('button',{name:'Tutup dialog',exact:true}).click();
  await page.getByRole('button',{name:'Buat order produksi',exact:true}).click();
  await page.getByLabel('Nama order',{exact:true}).fill('Draft must survive delayed response');
  releaseProducts(); await productsFinished;
  await page.waitForTimeout(100);
  assert.equal(await page.getByLabel('Nama order',{exact:true}).inputValue(),'Draft must survive delayed response');
  await page.getByRole('button',{name:'Tutup dialog',exact:true}).click();
  await page.screenshot({path:path.join(work,'dashboard-desktop.png'),fullPage:true});
  await page.getByLabel('Cari order atau SKU').fill('not-found');
  await page.getByRole('button',{name:'Cari order',exact:true}).click();
  await page.getByText('Tidak ada order yang cocok.',{exact:false}).waitFor();
  await page.getByLabel('Cari order atau SKU').fill('');
  await page.getByRole('button',{name:'Cari order',exact:true}).click();
  await page.locator('.order-row').first().waitFor();

  await page.getByRole('button',{name:'Master SKU',exact:true}).click();
  await page.getByRole('button',{name:'Tambah SKU',exact:true}).click();
  const unique = Date.now();
  await page.getByLabel('Kode SKU',{exact:true}).fill('DEMO-UI-'+unique);
  await page.getByLabel('Nama produk',{exact:true}).fill('CONTOH <uji teks>');
  await page.getByLabel('Warna',{exact:true}).fill('Biru');
  await page.getByLabel('Ukuran',{exact:true}).fill('L');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Buat order produksi',exact:true}).click();
  await page.getByLabel('Referensi order',{exact:true}).fill('DEMO-UI-ORDER-'+unique);
  await page.getByLabel('Nama order',{exact:true}).fill('CONTOH - Uji dashboard '+unique);
  await page.getByLabel('Target selesai',{exact:true}).fill('2099-01-01');
  await page.getByLabel('Jumlah',{exact:true}).fill('20');
  await page.getByRole('button',{name:'Tambah baris SKU',exact:true}).click();
  await page.getByLabel('SKU',{exact:true}).nth(1).selectOption({label:'DEMO-UI-'+unique});
  await page.getByLabel('Jumlah',{exact:true}).nth(1).fill('30');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'CONTOH - Uji dashboard '+unique,exact:true}).waitFor();
  const board = await apiGet('/api/production-board?q=DEMO-UI-ORDER-'+unique);
  const orderId = board.orders[0].id;
  assert.equal(board.orders[0].target_quantity,50);
  await page.getByRole('button',{name:'Catat perpindahan',exact:true}).first().click();
  await page.getByLabel('Jumlah (pcs)',{exact:true}).fill('10');
  let intercepted = false, authDenied = false;
  await page.route('**/api/movements',async route => {
    if (!intercepted && route.request().method()==='POST') {
      intercepted = true; await route.fetch(); await route.abort('failed');
    } else if (!authDenied && route.request().method()==='POST') {
      authDenied = true;
      await route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Simulated expired access'})});
    } else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();
  await login(admin);
  await page.getByRole('heading',{name:'Konfirmasi pencatatan sebelumnya'}).waitFor();
  const originalPending = await page.evaluate(() => Object.keys(sessionStorage).filter(key=>key.startsWith('beeloft.pending.')).map(key=>sessionStorage.getItem(key)));
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('button',{name:'Masuk ulang',exact:true}).waitFor();
  const retainedPending = await page.evaluate(() => Object.keys(sessionStorage).filter(key=>key.startsWith('beeloft.pending.')).map(key=>sessionStorage.getItem(key)));
  assert.equal(JSON.parse(originalPending[0]).transaction.key,JSON.parse(retainedPending[0]).transaction.key);
  await page.getByRole('button',{name:'Masuk ulang',exact:true}).click();
  await login(admin);
  await page.getByRole('heading',{name:'Konfirmasi pencatatan sebelumnya'}).waitFor();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  const movements = await apiGet('/api/orders/'+orderId+'/movements');
  assert.equal(movements.length,1);
  assert.equal((await apiGet('/api/orders/'+orderId)).totals.cutting,10);
  await page.getByRole('button',{name:new RegExp('DEMO-UI-ORDER-'+unique)}).click();
  await page.getByRole('button',{name:'Koreksi',exact:true}).click();
  await page.getByLabel('Alasan koreksi',{exact:true}).fill('CONTOH koreksi input');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  await page.getByText('Sudah dibalik',{exact:false}).waitFor();
  assert.equal((await apiGet('/api/orders/'+orderId)).totals.planned,50);

  await page.getByRole('button',{name:'Semua order',exact:false}).click();
  await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
  await page.getByRole('heading',{name:'Posisi barang sekarang'}).waitFor();
  await page.evaluate(()=>document.getElementById('notice').hidden=true);
  await page.screenshot({path:path.join(work,'dashboard-detail.png'),fullPage:true});
  await page.getByRole('button',{name:'Mode gelap',exact:true}).click();
  await page.screenshot({path:path.join(work,'dashboard-dark.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(work,'dashboard-mobile.png'),fullPage:true});
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true);
  for (const width of [320,768,1440]) {
    await page.setViewportSize({width,height:900});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true,'Overflow at '+width);
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),true,'Overflow at 200% text');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.getByRole('button',{name:'Catat perpindahan',exact:true}).first().click();
  await page.keyboard.press('Escape');
  await page.locator('dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(viewer);
  assert.equal(await page.getByRole('button',{name:'Buat order produksi',exact:true}).isVisible(),false);
  await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
  await page.getByRole('heading',{name:'Posisi barang sekarang'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Catat perpindahan',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Koreksi',exact:true}).count(),0);
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(operator);
  await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
  await page.getByRole('button',{name:'Catat perpindahan',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Koreksi',exact:true}).count(),0);
  assert.deepEqual(errors,[]);
  await browser.close();
  console.log('Browser QA PASS: login, filters, SKU, multi-SKU order, partial move, lost-response reload/retry exactly once, reversal, roles, dark theme, mobile overflow, Escape; no JS errors.');
})().catch(error => {console.error(error);process.exit(1);});
