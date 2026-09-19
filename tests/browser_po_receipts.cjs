const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key){
    const r=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key},body:JSON.stringify(body)});
    assert.equal(r.status,201,await r.clone().text());return r.json();
  }
  const m=(await apiGet('/api/materials')).find(m=>m.unit==='m');
  const supplier=(await apiGet('/api/suppliers'))[0];
  let pr=await post('/api/purchase-requests',{reference:'PR-RECEIPT',required_date:'2026-12-01',estimated_value:'100',reason:'CONTOH penerimaan',lines:[{material_id:m.id,quantity:'3.125'}]},'receipt-pr');
  pr=await post('/api/purchase-requests/'+pr.id+'/decisions',{status:'approved',expected_revision:pr.revision,reason:'CONTOH setuju'},'receipt-approved');
  let po=await post('/api/purchase-orders',{reference:'PO-RECEIPT',request_id:pr.id,expected_revision:pr.revision,supplier_id:supplier.id,expected_date:'2026-12-02',terms:'CONTOH tunai',reason:'CONTOH pembelian',prices:[{material_id:m.id,unit_price:'10'}]},'receipt-po');
  po=await post('/api/purchase-orders/'+po.id+'/decisions',{status:'approved',expected_revision:po.revision,reason:'CONTOH penerbitan disetujui'},'receipt-po-approved');
  async function openPO(){
    await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
    await page.getByRole('button',{name:'Daftar PO',exact:true}).click();
    await page.getByRole('button',{name:'Rincian PO PO-RECEIPT',exact:true}).click();
    await page.getByText('PO-RECEIPT · Aktif',{exact:true}).waitFor();
  }
  await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(operator);
  await page.getByRole('button',{name:'Bahan baku',exact:true}).click();
  await openPO();
  await page.getByRole('button',{name:'Terima bahan dari PO',exact:true}).click();
  await page.getByLabel('Referensi batch',{exact:true}).fill('RECEIPT-UI');
  await page.getByLabel('Lokasi / rak',{exact:true}).fill('Rak <A> & B');
  await page.getByLabel('Tanggal diterima',{exact:true}).fill('2026-12-02');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH lolos pemeriksaan');
  const quantity=page.getByLabel('Jumlah layak pakai',{exact:true});
  await quantity.fill('4');assert.equal(await quantity.evaluate(e=>e.validity.rangeOverflow),true);
  await quantity.fill('1.125');
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.deepEqual(await page.evaluate(()=>{const d=document.querySelector('dialog'), r=d.getBoundingClientRect();return d.scrollWidth<=d.clientWidth?[]:[...d.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>r.right-16).map(e=>({tag:e.tagName,id:e.id,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right,dialog:r.right}));}),[]);
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.deepEqual(await page.evaluate(()=>{const d=document.querySelector('dialog'), r=d.getBoundingClientRect();return d.scrollWidth<=d.clientWidth?[]:[...d.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>r.right-16).map(e=>({tag:e.tagName,id:e.id,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right,dialog:r.right}));}),[]);
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-po-receipt-mobile.png')});
  let drop=true;
  await page.route('**/api/purchase-orders/*/receipts',async route=>{
    if(drop){drop=false;await route.fetch();await route.abort('failed');}else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByText('Diterima sebagian',{exact:true}).waitFor();
  await page.unroute('**/api/purchase-orders/*/receipts');
  let detail=await apiGet('/api/purchase-orders/'+po.id);
  assert.equal(detail.receipts.length,1);assert.equal(detail.lines[0].remaining,'2.000');
  const batch=await apiGet('/api/material-batches/'+detail.receipts[0].batch_id);
  assert.equal(batch.balance,'1.125');assert.equal(batch.purchase_order_id,po.id);
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Bahan baku',exact:true}).click();
  await openPO();
  await page.getByRole('button',{name:'Terima bahan dari PO',exact:true}).click();
  await page.getByLabel('Referensi batch',{exact:true}).fill('RECEIPT-SECOND');
  await page.getByLabel('Lokasi / rak',{exact:true}).fill('Rak C');
  await page.getByLabel('Tanggal diterima',{exact:true}).fill('2026-12-03');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH kiriman kedua');
  await page.getByLabel('Jumlah layak pakai',{exact:true}).fill('2');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('Diterima lengkap',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Terima bahan dari PO',exact:true}).count(),0);
  await page.keyboard.press('Escape');
  // Milestone E: 'Permintaan pembelian' sekarang halaman, jadi dialog PO tidak lagi
  // meninggalkan halaman bahan baku aktif di bawahnya. Kembali ke sana sebelum memeriksa batch.
  // Pemeriksaan mobile sudah selesai; kembalikan viewport desktop supaya sidebar terlihat.
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Bahan baku',exact:true}).click();
  await page.locator('#batch-list').getByRole('button',{name:'RECEIPT-SECOND',exact:true}).waitFor();
  await openPO();
  detail=await apiGet('/api/purchase-orders/'+po.id);
  await post('/api/material-movements/'+detail.receipts[0].receipt_id+'/reverse',{reason:'CONTOH koreksi kiriman kedua'},'reverse-second');
  await page.getByRole('button',{name:'Riwayat batch RECEIPT-UI',exact:true}).click();
  await page.getByRole('button',{name:'PO PO-RECEIPT',exact:true}).click();
  await page.getByText('Diterima sebagian',{exact:true}).waitFor();
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(viewer);
  await openPO();assert.equal(await page.getByRole('button',{name:'Terima bahan dari PO',exact:true}).count(),0);
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(admin);
  await openPO();assert.equal(await page.getByRole('button',{name:'Batalkan PO',exact:true}).count(),0);
  await page.getByRole('button',{name:'Riwayat batch RECEIPT-UI',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi catatan bahan',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH salah catat');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  await openPO();await page.getByText('Penerimaan dikoreksi',{exact:true}).first().waitFor();
  assert.equal(await page.getByText('Penerimaan dikoreksi',{exact:true}).count(),2);
  await page.getByRole('button',{name:'Batalkan PO',exact:true}).waitFor();
  detail=await apiGet('/api/purchase-orders/'+po.id);assert.equal(detail.lines[0].remaining,'3.125');
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-po-receipts.png')});
  await page.keyboard.press('Escape');
  console.log('PO receipt browser QA PASS: partial stock, overage, reload retry, source links, role controls, reversal, mobile/200%.');
};
