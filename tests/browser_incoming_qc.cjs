const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key){
    const r=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key},body:JSON.stringify(body)});
    assert.equal(r.status,201,await r.clone().text());return r.json();
  }
  const m=await post('/api/materials',{code:'KAIN-QC',name:'Kain pemeriksaan',unit:'m'},'qc-material');
  const supplier=(await apiGet('/api/suppliers'))[0];
  let pr=await post('/api/purchase-requests',{reference:'PR-QC',required_date:'2026-12-01',estimated_value:'100',reason:'CONTOH QC',lines:[{material_id:m.id,quantity:'3.125'}]},'qc-pr');
  pr=await post('/api/purchase-requests/'+pr.id+'/decisions',{status:'approved',expected_revision:pr.revision,reason:'CONTOH setuju'},'qc-approved');
  let po=await post('/api/purchase-orders',{reference:'PO-QC',request_id:pr.id,expected_revision:pr.revision,supplier_id:supplier.id,expected_date:'2026-12-02',terms:'CONTOH tunai',reason:'CONTOH pembelian',prices:[{material_id:m.id,unit_price:'10'}]},'qc-po');
  po=await post('/api/purchase-orders/'+po.id+'/decisions',{status:'approved',expected_revision:po.revision,reason:'CONTOH penerbitan disetujui'},'qc-po-approved');
  async function openPO(){
    await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
    await page.getByRole('button',{name:'Daftar PO',exact:true}).click();
    await page.getByRole('button',{name:'Rincian PO PO-QC',exact:true}).click();
    await page.getByText('PO-QC · Aktif',{exact:true}).waitFor();
  }
  async function openQC(){await openPO();await page.getByRole('button',{name:'Rincian QC ARRIVAL <QC>',exact:true}).click();await page.getByText('ARRIVAL <QC> · KAIN-QC · Kain pemeriksaan',{exact:true}).waitFor();}
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  await role(operator);await openPO();
  await page.getByRole('button',{name:'Catat kedatangan untuk QC',exact:true}).click();
  await page.getByLabel('Referensi kedatangan',{exact:true}).fill('ARRIVAL <QC>');
  await page.getByLabel('Lokasi hold',{exact:true}).fill('Area pemeriksaan');
  await page.getByLabel('Tanggal diterima',{exact:true}).fill('2026-12-02');
  await page.getByLabel('Jumlah datang',{exact:true}).fill('3.125');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH menunggu pemeriksaan');
  const before=await apiGet('/api/material-batches');
  let drop=true;
  await page.route('**/api/purchase-orders/*/qc-intakes',async route=>{if(drop){drop=false;await route.fetch();await route.abort('failed');}else await route.continue();});
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByText('ARRIVAL <QC> · KAIN-QC · Kain pemeriksaan',{exact:true}).waitFor();
  await page.unroute('**/api/purchase-orders/*/qc-intakes');
  assert.deepEqual(await apiGet('/api/material-batches'),before);
  let detail=await apiGet('/api/purchase-orders/'+po.id);assert.equal(detail.qc_intakes.length,1);assert.equal(detail.lines[0].held,'3.125');
  const intakeId=detail.qc_intakes[0].id;
  assert.equal(await page.getByRole('button',{name:'Terima layak pakai',exact:true}).count(),0);
  await role(viewer);await openQC();
  assert.equal(await page.getByRole('button',{name:'Terima layak pakai',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Tolak bahan',exact:true}).count(),0);
  await role(admin);await page.getByRole('button',{name:'Bahan baku',exact:true}).click();await openQC();
  await page.getByRole('button',{name:'Terima layak pakai',exact:true}).click();
  await page.getByLabel('Jumlah keputusan',{exact:true}).fill('4');
  assert.equal(await page.getByLabel('Jumlah keputusan',{exact:true}).evaluate(e=>e.validity.rangeOverflow),true);
  await page.getByLabel('Jumlah keputusan',{exact:true}).fill('1.125');
  await page.getByLabel('Referensi batch layak pakai',{exact:true}).fill('QC-BATCH');
  await page.getByLabel('Lokasi stok layak pakai',{exact:true}).fill('Rak lolos QC');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH warna dan ukuran sesuai');
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  }
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-qc-form-mobile.png')});
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Batch QC-BATCH',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  // Milestone E: 'Permintaan pembelian' sekarang halaman, jadi dialog PO/QC tidak lagi
  // meninggalkan halaman bahan baku aktif di bawahnya. Kembali ke sana sebelum memeriksa batch.
  // Pemeriksaan mobile sudah selesai; kembalikan viewport desktop supaya sidebar terlihat.
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Bahan baku',exact:true}).click();
  await page.locator('#batch-list').getByRole('button',{name:'QC-BATCH',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi catatan bahan',exact:true}).count(),0);
  await page.getByRole('button',{name:'QC asal batch',exact:true}).click();
  await page.getByRole('button',{name:'Tolak bahan',exact:true}).click();
  await page.getByLabel('Jumlah keputusan',{exact:true}).fill('2');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH noda pada bahan');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Reject · 2 m',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Terima layak pakai',exact:true}).count(),0);
  detail=await apiGet('/api/purchase-orders/'+po.id);
  assert.equal(detail.lines[0].received,'1.125');assert.equal(detail.lines[0].rejected,'2.000');assert.equal(detail.lines[0].receivable,'2.000');
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-incoming-qc.png')});
  for(const heading of ['Layak pakai · 1,125 m','Reject · 2 m']){
    await page.locator('.material-event').filter({has:page.getByRole('heading',{name:heading,exact:true})}).getByRole('button',{name:'Koreksi keputusan',exact:true}).click();
    await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH pemeriksaan ulang');
    await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
    await page.getByText('ARRIVAL <QC> · KAIN-QC · Kain pemeriksaan',{exact:true}).waitFor();
  }
  const qc=await apiGet('/api/qc-intakes/'+intakeId);assert.equal(qc.held,'3.125');assert.equal(qc.history.length,4);
  await page.getByRole('button',{name:'Batalkan kedatangan',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH salah pencatatan kedatangan');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('Kedatangan dibatalkan',{exact:true}).waitFor();
  assert.equal((await apiGet('/api/purchase-orders/'+po.id)).lines[0].receivable,'3.125');
  await page.keyboard.press('Escape');
  console.log('Incoming QC browser QA PASS: hold outside stock, reload retry, roles, partial acceptance, reject, stock refresh, batch source, correction/cancellation, mobile/200%.');
};
