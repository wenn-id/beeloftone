const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page,login,admin,operator,viewer,apiGet,work}) => {
  const seeded = await fetch(process.env.BEELOFT_QA_BASE+'/api/materials',{
    method:'POST',headers:{'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':'pr-pcs-fixture'},
    body:JSON.stringify({code:'PR-BUTTON',name:'Kancing untuk PR',unit:'pcs'})});
  assert.equal(seeded.status,201);
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
  await page.getByText('Belum ada PR yang sesuai filter.',{exact:true}).waitFor();
  let fail=true;
  await page.route('**/api/purchase-requests?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar PR uji belum tersedia'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Muat ulang PR',exact:true}).click();
  await page.getByText('Daftar PR uji belum tersedia',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba muat PR lagi',exact:true}).click();
  await page.getByText('Belum ada PR yang sesuai filter.',{exact:true}).waitFor();
  await page.unroute('**/api/purchase-requests?*');
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click(); await login(operator);
  await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
  await page.getByRole('button',{name:'PR untuk order ini',exact:true}).click();
  await page.getByRole('button',{name:'Buat PR',exact:true}).click();
  const order=(await apiGet('/api/orders')).find(o=>o.reference==='DEMO-PROD-001');
  assert.equal(await page.locator('#pr-order').inputValue(),order.id);
  const materials=await apiGet('/api/materials'), meter=materials.find(m=>m.unit==='m'), pcs=materials.find(m=>m.unit==='pcs');
  await page.getByLabel('Referensi PR',{exact:true}).fill('PR-QA-<cutting>');
  await page.getByLabel('Tanggal dibutuhkan',{exact:true}).fill('2026-12-01');
  await page.getByLabel('Estimasi total (Rp)',{exact:true}).fill('123456.78');
  await page.getByLabel('Bahan PR',{exact:true}).selectOption(meter.id);
  await page.getByLabel('Jumlah bahan PR',{exact:true}).fill('2.125');
  await page.getByRole('button',{name:'Tambah bahan PR',exact:true}).click();
  await page.getByLabel('Bahan PR',{exact:true}).nth(1).selectOption(pcs.id);
  await page.getByLabel('Jumlah bahan PR',{exact:true}).nth(1).fill('3');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH <script> kebutuhan produksi & cadangan');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-pr-form-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});
  const before=await apiGet('/api/material-batches');
  let drop=true;
  await page.route('**/api/purchase-requests',async route=>{
    if(drop && route.request().method()==='POST'){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian PR',exact:true}).waitFor();
  await page.getByText('Rp123.456,78',{exact:false}).waitFor();
  await page.unroute('**/api/purchase-requests');
  assert.equal((await apiGet('/api/purchase-requests')).length,1);
  assert.equal(await page.getByRole('button',{name:'Setujui PR',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Batalkan PR',exact:true}).count(),1);
  assert.equal(await page.locator('#dialog-content script').count(),0);
  assert.deepEqual(await apiGet('/api/material-batches'),before);
  const pr=(await apiGet('/api/purchase-requests'))[0];
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-purchase-request.png')});
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(viewer);
  await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Buat PR',exact:true}).count(),0);
  await page.getByRole('button',{name:'Rincian PR-QA-<cutting>',exact:true}).click();
  await page.getByRole('heading',{name:'Riwayat keputusan',exact:true}).waitFor();
  assert.equal(await page.locator('[data-pr-decision]').count(),0);
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(admin);
  await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
  await page.getByRole('button',{name:'Rincian PR-QA-<cutting>',exact:true}).click();
  await page.getByRole('button',{name:'Tolak PR',exact:true}).click();
  const saved=await fetch(process.env.BEELOFT_QA_BASE+'/api/purchase-requests/'+pr.id+'/decisions',{
    method:'POST',headers:{'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':'pr-other-tab'},
    body:JSON.stringify({status:'approved',expected_revision:pr.revision,reason:'CONTOH - disetujui tab lain'})});
  assert.equal(saved.status,201);
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH - formulir tertinggal');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('PR sudah berubah.',{exact:false}).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
  await page.getByLabel('Status PR',{exact:true}).selectOption('approved');
  await page.getByRole('button',{name:'Rincian PR-QA-<cutting>',exact:true}).click();
  await page.getByRole('button',{name:'Batalkan PR',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH - rencana dibatalkan');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('PR-QA-<cutting> · Dibatalkan',{exact:true}).waitFor();
  assert.equal(await page.locator('[data-pr-decision]').count(),0);
  await page.keyboard.press('Escape');
  console.log('Purchase request browser QA PASS: multi-material order PR, retry after reload, role access, stale decision, filter, cancellation, escaping, mobile/200%.');
};
