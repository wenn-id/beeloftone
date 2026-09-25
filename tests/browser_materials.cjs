const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page,login,admin,operator,viewer,apiGet,work}) => {
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(admin);
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Bahan baku',exact:true}).click();
  await page.getByText('Belum ada batch pada halaman ini.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Master bahan',exact:true}).click();
  await page.getByRole('button',{name:'Tambah bahan',exact:true}).click();
  await page.getByLabel('Kode bahan',{exact:true}).fill('KAIN-UI');
  await page.getByLabel('Nama bahan',{exact:true}).fill('Katun <biru> & putih');
  await page.getByLabel('Satuan dasar',{exact:true}).selectOption('m');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Terima batch bahan',exact:true}).click();
  await page.getByLabel('Referensi batch',{exact:true}).fill('BATCH-UI-001');
  await page.getByLabel('Pemasok',{exact:true}).fill('CONTOH pemasok');
  await page.getByLabel('Lokasi / rak',{exact:true}).fill('Rak A-01');
  await page.getByLabel('Tanggal diterima',{exact:true}).fill('2026-09-11');
  await page.getByLabel('Jumlah layak pakai',{exact:true}).fill('10.125');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH - bahan lolos pemeriksaan');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('#batch-list [data-batch-balance]').getByText('10,125 m',{exact:true}).waitFor();
  const batch = (await apiGet('/api/material-batches'))[0];
  await page.getByRole('button',{name:'BATCH-UI-001',exact:true}).click();
  await page.getByText('Penerimaan · 10,125 m',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Papan produksi',exact:false}).filter({visible:true}).click();
  await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
  await page.getByRole('button',{name:'Keluarkan bahan ke order',exact:true}).click();
  await page.getByLabel('Jumlah dikeluarkan',{exact:true}).fill('2.125');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('Untuk cutting order demo');
  let loseResponse = true;
  await page.route('**/api/material-issues', async route => {
    if (loseResponse) { loseResponse=false; await route.fetch(); await route.abort('failed'); }
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  await page.unroute('**/api/material-issues');
  assert.equal((await apiGet('/api/material-batches/'+batch.id)).balance,'8.000');
  assert.equal((await apiGet('/api/material-batches/'+batch.id+'/movements')).length,2);
  await page.getByRole('button',{name:'Riwayat bahan order',exact:true}).click();
  await page.getByText('Pengeluaran · -2,125 m',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Koreksi catatan bahan',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH - seluruh bahan kembali ke rak');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  assert.equal((await apiGet('/api/material-batches/'+batch.id)).balance,'10.125');
  await page.getByRole('button',{name:'Bahan baku',exact:true}).click();
  await page.locator('#batch-list [data-batch-balance]').getByText('10,125 m',{exact:true}).waitFor();
  await page.evaluate(()=>document.getElementById('notice').hidden=true);
  const artifacts = process.env.BEELOFT_QA_SCREENSHOTS || work;
  await page.screenshot({path:path.join(artifacts,'beeloft-materials-desktop.png'),fullPage:true});
  for (const width of [320,390,768]) {
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Materials overflow at '+width);
  }
  await page.getByRole('button',{name:'BATCH-UI-001',exact:true}).click();
  await page.getByText('Pembalikan · 2,125 m',{exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(artifacts,'beeloft-materials-history-mobile.png'),fullPage:true});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.querySelector('dialog').scrollWidth<=document.querySelector('dialog').clientWidth),'Material dialog overflow at 200%');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.keyboard.press('Escape');
  for (const [key,canReceive] of [[operator,true],[viewer,false]]) {
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
    await page.getByRole('button',{name:'Bahan baku',exact:true}).click();
    await page.getByRole('button',{name:'BATCH-UI-001',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Terima batch bahan',exact:true}).isVisible(),canReceive);
    await page.getByRole('button',{name:'Master bahan',exact:true}).click();
    await page.getByText('Katun <biru> & putih · m',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Tambah bahan',exact:true}).count(),0);
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'BATCH-UI-001',exact:true}).click();
    await page.getByText('Penerimaan · 10,125 m',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Koreksi catatan bahan',exact:true}).count(),0);
    await page.keyboard.press('Escape');
  }
  let failScan=true;
  await page.route('**/api/material-batches/scan?*',async route=>{
    if(failScan){failScan=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Pemindai batch sedang sibuk'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Scan batch bahan',exact:true}).click();
  const scan=page.getByLabel('Kode batch bahan',{exact:true});
  assert.equal(await scan.evaluate(element=>element===document.activeElement),true);
  await scan.fill(batch.scan_code);await scan.press('Enter');
  await page.getByText('Pemindai batch sedang sibuk',{exact:true}).waitFor();
  await scan.press('Enter');
  await page.getByRole('heading',{name:'Riwayat batch bahan',exact:true}).waitFor();
  await page.unroute('**/api/material-batches/scan?*');
  await page.waitForFunction(()=>document.querySelector('.material-batch-label img')?.naturalWidth>0);
  await page.locator('.material-batch-label').getByText('Katun <biru> & putih',{exact:false}).waitFor();
  await page.evaluate(()=>{window.__materialBatchPrinted=false;window.print=()=>{window.__materialBatchPrinted=true;};});
  await page.getByRole('button',{name:'Cetak label batch',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.__materialBatchPrinted),true);
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.keyboard.press('Escape');
  console.log('Materials browser QA PASS: receive, exact decimal issue, retry, QR batch scan/print, roles, mobile, escaped text.');
};
