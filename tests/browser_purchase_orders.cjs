const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{
      method:'POST',headers:{'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key},
      body:JSON.stringify(body)});
    assert.equal(response.status,201);return response.json();
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
  await page.getByRole('button',{name:'Master pemasok',exact:true}).click();
  await page.getByText('Belum ada pemasok.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Tambah pemasok',exact:true}).click();
  await page.getByLabel('Kode pemasok',{exact:true}).fill('supplier-qa');
  await page.getByLabel('Nama pemasok',{exact:true}).fill('Toko <kain> & Kancing');
  await page.getByLabel('Kontak pemasok',{exact:true}).fill('CONTOH PIC');
  await page.getByLabel('Alamat pemasok',{exact:true}).fill('CONTOH Bandung');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH pemasok untuk PO');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('SUPPLIER-QA · Toko <kain> & Kancing',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  const materials=await apiGet('/api/materials');
  const meter=materials.find(m=>m.unit==='m'),pcs=materials.find(m=>m.unit==='pcs');
  const pr=await post('/api/purchase-requests',{reference:'PR-FOR-PO',order_id:null,required_date:'2026-12-01',
    estimated_value:'123.45',reason:'CONTOH kebutuhan pembelian',
    lines:[{material_id:meter.id,quantity:'2.125'},{material_id:pcs.id,quantity:'3'}]},'po-pr-fixture');
  await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
  await page.getByRole('button',{name:'Daftar PO',exact:true}).click();
  await page.getByText('Belum ada PO yang sesuai filter.',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
  await page.getByRole('button',{name:'Rincian PR-FOR-PO',exact:true}).click();
  await page.getByRole('button',{name:'Setujui PR',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH admin setuju');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Buat PO dari PR',exact:true}).click();
  await page.getByLabel('Referensi PO',{exact:true}).fill('PO-QA-001');
  await page.getByLabel('Perkiraan tanggal datang',{exact:true}).fill('2026-12-02');
  await page.getByLabel('Syarat pembelian',{exact:true}).fill('CONTOH bayar setelah diterima');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH harga disepakati');
  const meterPrice=page.getByLabel('Harga satuan '+meter.code+' (Rp/m)',{exact:true});
  const pcsPrice=page.getByLabel('Harga satuan '+pcs.code+' (Rp/pcs)',{exact:true});
  await meterPrice.fill('1000');await pcsPrice.fill('1');
  await page.getByText('Melebihi nilai PR yang disetujui.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('Total PO melebihi estimasi PR',{exact:false}).waitFor();
  await meterPrice.fill('12.34');
  await page.getByText('Total PO Rp29,22',{exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  const artifacts=process.env.BEELOFT_QA_SCREENSHOTS || work;
  await page.locator('dialog').screenshot({path:path.join(artifacts,'beeloft-po-form-mobile.png')});
  const before=await apiGet('/api/material-batches');
  let drop=true;
  await page.route('**/api/purchase-orders',async route=>{
    if(drop && route.request().method()==='POST'){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(admin);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByText('PO-QA-001 · Aktif',{exact:true}).waitFor();
  await page.unroute('**/api/purchase-orders');
  assert.equal((await apiGet('/api/purchase-orders')).length,1);
  assert.deepEqual(await apiGet('/api/material-batches'),before);
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('dialog').screenshot({path:path.join(artifacts,'beeloft-purchase-order.png')});
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.getByRole('button',{name:'PR PR-FOR-PO',exact:true}).click();
  await page.getByText('PR-FOR-PO · Disetujui',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Batalkan PR',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Buat PO dari PR',exact:true}).count(),0);
  for(const role of [operator,viewer]){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(role);
    await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
    await page.getByRole('button',{name:'Master pemasok',exact:true}).click();
    await page.getByText('SUPPLIER-QA · Toko <kain> & Kancing',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Tambah pemasok',exact:true}).count(),0);
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
    await page.getByRole('button',{name:'Daftar PO',exact:true}).click();
    await page.getByRole('button',{name:'Rincian PO PO-QA-001',exact:true}).click();
    await page.getByText('PO-QA-001 · Aktif',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Batalkan PO',exact:true}).count(),0);
  }
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(admin);
  await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
  await page.getByRole('button',{name:'Daftar PO',exact:true}).click();
  await page.locator('#po-status').waitFor();
  await page.locator('#po-status').selectOption('issued');
  await page.getByRole('button',{name:'Rincian PO PO-QA-001',exact:true}).click();
  await page.getByRole('button',{name:'Batalkan PO',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH pembelian dibatalkan');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('PO-QA-001 · Dibatalkan',{exact:true}).waitFor();
  await page.getByRole('button',{name:'PR PR-FOR-PO',exact:true}).click();
  await page.getByRole('button',{name:'Buat PO dari PR',exact:true}).waitFor();
  await page.getByRole('button',{name:'Batalkan PR',exact:true}).waitFor();
  assert.equal((await apiGet('/api/purchase-requests/'+pr.id)).status,'approved');
  await page.keyboard.press('Escape');
  console.log('PO browser QA PASS: supplier, approved PR, exact live total/budget, lost-response reload retry, roles, source links, cancel, mobile/200%.');
};
