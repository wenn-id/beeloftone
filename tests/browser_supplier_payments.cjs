const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key,apiKey=admin){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':apiKey,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,201,await response.clone().text());return response.json();
  }
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  async function openPO(){
    await page.getByRole('button',{name:'Permintaan pembelian',exact:true}).click();
    await page.getByRole('button',{name:'Daftar PO',exact:true}).click();
    await page.getByRole('button',{name:'Rincian PO PO-PAYMENT',exact:true}).click();
    await page.getByText('PO-PAYMENT · Aktif',{exact:true}).waitFor();
  }

  const material=await post('/api/materials',{code:'KAIN-PAYMENT',name:'Kain pembayaran',unit:'m'},'payment-material');
  const supplier=(await apiGet('/api/suppliers'))[0];
  let pr=await post('/api/purchase-requests',{reference:'PR-PAYMENT',required_date:'2026-12-01',
    estimated_value:'100',reason:'CONTOH pembayaran supplier',
    lines:[{material_id:material.id,quantity:'2'}]},'payment-pr',operator);
  pr=await post('/api/purchase-requests/'+pr.id+'/decisions',{status:'approved',
    expected_revision:pr.revision,reason:'CONTOH kebutuhan disetujui'},'payment-pr-approved');
  let po=await post('/api/purchase-orders',{reference:'PO-PAYMENT',request_id:pr.id,
    expected_revision:pr.revision,supplier_id:supplier.id,expected_date:'2026-12-02',
    terms:'CONTOH bayar 14 hari',reason:'CONTOH pembelian untuk pembayaran',
    prices:[{material_id:material.id,unit_price:'50'}]},'payment-po',operator);
  po=await post('/api/purchase-orders/'+po.id+'/decisions',{status:'approved',
    expected_revision:po.revision,reason:'CONTOH PO disetujui'},'payment-po-approved');
  await post('/api/purchase-orders/'+po.id+'/receipts',{material_id:material.id,
    reference:'PAYMENT-RECEIPT',location:'Rak pembayaran',received_date:'2026-12-02',
    quantity:'2',reason:'CONTOH bahan diterima'},'payment-receipt',operator);

  await role(operator);await openPO();
  await page.getByText('Menunggu approval Rp0,00 · disetujui Rp0,00 · sisa Rp100,00',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Ajukan pembayaran supplier',exact:true}).click();
  await page.getByLabel('Referensi pengajuan',{exact:true}).fill('PAY-UI-001');
  await page.getByLabel('Referensi invoice supplier',{exact:true}).fill('INV-<001>&');
  await page.getByLabel('Tanggal invoice',{exact:true}).fill('2026-12-02');
  await page.getByLabel('Tanggal jatuh tempo',{exact:true}).fill('2026-12-16');
  await page.getByLabel('Nominal pembayaran (Rp)',{exact:true}).fill('60');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH invoice cocok dengan penerimaan');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/purchase-orders/*/payment-requests',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Approval pembayaran supplier',exact:true}).waitFor();
  await page.unroute('**/api/purchase-orders/*/payment-requests');
  await page.getByText('PAY-UI-001 · Menunggu keputusan',{exact:true}).waitFor();
  await page.getByText('INV-<001>&',{exact:false}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Setujui pembayaran',exact:true}).count(),0);
  const request=(await apiGet('/api/purchase-orders/'+po.id+'/payment-requests'))[0];
  assert.equal(request.amount,'60.00');
  await page.locator('dialog').getByRole('button',{name:'Inbox approval',exact:true}).click();
  await page.locator('#approval-list').getByText('Finance · pembayaran supplier',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian approval PAY-UI-001',exact:true}).click();

  await role(viewer);
  await page.locator('#approvals').click();
  await page.getByRole('button',{name:'Rincian approval PAY-UI-001',exact:true}).click();
  assert.equal(await page.locator('[data-payment-decision]').count(),0);

  await role(admin);
  await page.locator('#approvals').click();
  await page.getByRole('button',{name:'Rincian approval PAY-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Setujui pembayaran',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH invoice dan penerimaan diverifikasi');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('PAY-UI-001 · Disetujui',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Buka PO',exact:true}).click();
  await page.getByText('Menunggu approval Rp0,00 · disetujui Rp60,00 · sisa Rp40,00',{exact:true}).waitFor();
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-supplier-payment-approval-mobile.png')});
  await page.locator('dialog').getByRole('button',{name:'Inbox approval',exact:true}).click();
  await page.locator('#approval-status').selectOption('approved');
  await page.locator('#approval-kind').selectOption('supplier_payment');
  await page.getByRole('button',{name:'Rincian approval PAY-UI-001',exact:true}).waitFor();
  console.log('Supplier payment approval browser QA PASS: received PO source, amount balance, lost-response retry, unified inbox, roles, approval audit, escaping, mobile/200%.');
};
