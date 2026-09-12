const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key},body:JSON.stringify(body)});
    assert.equal(response.status,201,await response.clone().text());return response.json();
  }
  const material=await post('/api/materials',{code:'KAIN-RETUR',name:'Kain untuk retur',unit:'m'},'return-material');
  let pr=await post('/api/purchase-requests',{reference:'PR-RETUR',required_date:'2026-12-01',estimated_value:'100',reason:'CONTOH retur',lines:[{material_id:material.id,quantity:'3'}]},'return-pr');
  pr=await post('/api/purchase-requests/'+pr.id+'/decisions',{status:'approved',expected_revision:pr.revision,reason:'CONTOH disetujui'},'return-approve');
  const supplier=(await apiGet('/api/suppliers'))[0];
  let po=await post('/api/purchase-orders',{reference:'PO-RETUR',request_id:pr.id,expected_revision:pr.revision,supplier_id:supplier.id,expected_date:'2026-12-02',terms:'CONTOH tunai',reason:'CONTOH pembelian',prices:[{material_id:material.id,unit_price:'10'}]},'return-po');
  po=await post('/api/purchase-orders/'+po.id+'/decisions',{status:'approved',expected_revision:po.revision,reason:'CONTOH penerbitan disetujui'},'return-po-approved');
  const intake=await post('/api/purchase-orders/'+po.id+'/qc-intakes',{material_id:material.id,reference:'QC-RETUR',location:'Hold',received_date:'2026-12-02',quantity:'3',reason:'CONTOH tiba'},'return-intake');
  await post('/api/qc-intakes/'+intake.id+'/decisions',{kind:'accept',quantity:'1',reference:'READY-RETUR',location:'Rak siap',reason:'CONTOH layak'},'return-accept');
  await post('/api/qc-intakes/'+intake.id+'/decisions',{kind:'reject',quantity:'2',reason:'CONTOH cacat'},'return-reject');
  async function openPO(){
    await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
    await page.getByRole('button',{name:'Daftar PO',exact:true}).click();
    await page.getByRole('button',{name:'Rincian PO PO-RETUR',exact:true}).click();
    await page.getByRole('heading',{name:'QC bahan masuk',exact:true}).waitFor();
  }
  async function openQC(){
    await openPO();await page.getByRole('button',{name:'Rincian QC QC-RETUR',exact:true}).click();
    await page.getByRole('heading',{name:'Retur ke pemasok',exact:true}).waitFor();
  }
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  await role(operator);await openQC();
  assert.equal(await page.getByRole('button',{name:'Catat retur supplier',exact:true}).count(),0);
  await role(viewer);await openQC();
  assert.equal(await page.getByRole('button',{name:'Catat retur supplier',exact:true}).count(),0);
  await role(admin);await openPO();
  assert.equal(await page.getByRole('button',{name:'Tutup PO',exact:true}).count(),0);
  await page.getByRole('button',{name:'Rincian QC QC-RETUR',exact:true}).click();
  await page.getByRole('button',{name:'Catat retur supplier',exact:true}).click();
  const stockBefore=await apiGet('/api/material-batches');
  await page.getByLabel('Referensi pengiriman retur',{exact:true}).fill('RET <supplier>');
  await page.getByLabel('Tanggal dikirim kembali',{exact:true}).fill('2026-12-03');
  await page.getByLabel('Jumlah retur',{exact:true}).fill('3');
  assert.equal(await page.getByLabel('Jumlah retur',{exact:true}).evaluate(el=>el.validity.rangeOverflow),true);
  await page.getByLabel('Jumlah retur',{exact:true}).fill('0.5');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH kirim sebagian');
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  }
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:390,height:844});
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-return-mobile.png')});
  let drop=true;
  await page.route('**/api/qc-intakes/*/returns',async route=>{if(drop){drop=false;await route.fetch();await route.abort('failed');}else await route.continue();});
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(admin);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Retur RET <supplier> · 0,5 m',exact:true}).waitFor();
  await page.unroute('**/api/qc-intakes/*/returns');
  let qc=await apiGet('/api/qc-intakes/'+intake.id);
  assert.equal(qc.returns.length,1);assert.equal(qc.return_pending,'1.500');
  assert.deepEqual(await apiGet('/api/material-batches'),stockBefore);
  await page.getByRole('button',{name:'Koreksi retur',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH salah jumlah');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('Retur sudah dikoreksi',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Catat retur supplier',exact:true}).click();
  await page.getByLabel('Referensi pengiriman retur',{exact:true}).fill('RET-FINAL');
  await page.getByLabel('Tanggal dikirim kembali',{exact:true}).fill('2026-12-03');
  await page.getByLabel('Jumlah retur',{exact:true}).fill('2');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH semua reject dikirim');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Retur RET-FINAL · 2 m',exact:true}).waitFor();
  await page.getByRole('button',{name:'PO PO-RETUR',exact:true}).click();
  await page.getByRole('button',{name:'Tutup PO',exact:true}).click();
  await page.getByText(/sisa tidak diterima 2 m/).waitFor();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH pemasok tidak mengganti sisa');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('PO-RETUR · Ditutup',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Terima bahan dari PO',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Tutup PO',exact:true}).count(),0);
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-po-closed.png')});
  await page.getByRole('button',{name:'Rincian QC QC-RETUR',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi retur',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Koreksi keputusan',exact:true}).count(),0);
  await page.getByRole('button',{name:'PO PO-RETUR',exact:true}).click();
  await page.getByRole('button',{name:'Daftar PO',exact:true}).click();
  await page.getByLabel('Status PO',{exact:true}).selectOption('closed');
  await page.getByRole('button',{name:'Rincian PO PO-RETUR',exact:true}).waitFor();
  const final=await apiGet('/api/purchase-orders/'+po.id);
  assert.equal(final.status,'closed');assert.equal(final.lines[0].receivable,'0.000');assert.equal(final.lines[0].remaining,'2.000');
  await role(viewer);await openPO();
  await page.getByRole('heading',{name:'Penutupan PO',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Supplier returns browser QA PASS: partial return, lost-response reload/retry, correction, roles, closure/shortfall, closed filter, mobile/200%.');
};
