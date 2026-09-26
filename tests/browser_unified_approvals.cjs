const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work,order})=>{
  async function post(url,body,key,expected=201,apiKey=admin){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':apiKey,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,expected,await response.clone().text());return response.json();
  }
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){
    // Milestone E: '#approvals' sekarang halaman, jadi papan produksi tidak lagi
    // tertinggal aktif di bawah inbox. Kembali ke papan sebelum membuka order.
    await page.locator('#board-home').click();
    await page.getByRole('button',{name:/DEMO-FINISHED-GOODS/}).click();await page.getByRole('heading',{name:'CONTOH penerimaan barang jadi',exact:true}).waitFor();}

  await role(operator);
  let failList=true;
  await page.route('**/api/approvals?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Inbox approval sedang sibuk'})});}
    else await route.continue();
  });
  await page.locator('#approvals').click();
  await page.getByText('Inbox approval sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Tidak ada approval yang sesuai filter.',{exact:true}).waitFor();
  await page.unroute('**/api/approvals?*');await page.keyboard.press('Escape');

  const material=(await apiGet('/api/materials'))[0];
  const purchase=await post('/api/purchase-requests',{reference:'PR-UNIFIED-UI',order_id:order.id,
    required_date:'2026-12-20',estimated_value:'3500000.00',reason:'CONTOH bahan tambahan untuk approval terpadu',
    lines:[{material_id:material.id,quantity:material.unit==='pcs'?'2':'2.000'}]},'unified-pr',201,operator);

  await openOrder();
  await page.getByRole('button',{name:'Ajukan perubahan tenggat / PIC',exact:true}).click();
  await page.getByLabel('Referensi permintaan',{exact:true}).fill('PCR-UI-001');
  await page.getByLabel('Target selesai yang diajukan',{exact:true}).fill('2026-12-15');
  await page.getByLabel('PIC yang diajukan',{exact:true}).selectOption({label:(await apiGet('/api/users')).find(row=>row.role==='operator').name});
  await page.getByLabel('Alasan perubahan',{exact:true}).fill('CONTOH kapasitas line membutuhkan tambahan waktu');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/orders/*/change-requests',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian approval produksi',exact:true}).waitFor();
  await page.unroute('**/api/orders/*/change-requests');
  await page.getByText('PCR-UI-001 · Menunggu keputusan',{exact:true}).waitFor();
  assert.equal((await apiGet('/api/orders/'+order.id)).due_date,'2026-12-01');
  const production=(await apiGet('/api/orders/'+order.id+'/change-requests'))[0];
  assert.equal(production.reference,'PCR-UI-001');
  await page.locator('dialog').getByRole('button',{name:'Inbox approval',exact:true}).click();
  await page.getByText('Rp3.500.000,00',{exact:true}).waitFor();
  // Milestone E: konten dialog yang ditutup tetap ada di DOM, jadi teks baris produksi
  // muncul dua kali (di halaman approval dan di #dialog-content yang sudah ditutup).
  // Batasi pada daftar di halaman.
  await page.locator('#approval-list').getByText('Target 1 Des 2026 → 15 Des 2026',{exact:true}).waitFor();
  // A6.7: an approval is an A6 record row in the Inbox's one record list.
  assert.equal(await page.locator('#approval-list .record-row').count(),2);
  await page.locator('#approvals-view').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-unified-approvals-mobile.png')});

  await role(viewer);
  await page.locator('#approvals').click();
  await page.getByRole('button',{name:'Rincian approval PCR-UI-001',exact:true}).click();
  assert.equal(await page.locator('[data-production-decision]').count(),0);
  await page.getByRole('button',{name:'Buka order',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Ajukan perubahan tenggat / PIC',exact:true}).count(),0);

  await role(admin);
  await page.locator('#approvals').click();
  await page.getByRole('button',{name:'Rincian approval PCR-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Setujui perubahan',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH kapasitas produksi diverifikasi');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('PCR-UI-001 · Disetujui',{exact:true}).waitFor();
  assert.equal((await apiGet('/api/orders/'+order.id)).due_date,'2026-12-15');
  assert.equal((await apiGet('/api/orders/'+order.id+'/changes')).length,1);

  await page.locator('dialog').getByRole('button',{name:'Inbox approval',exact:true}).click();
  await page.getByRole('button',{name:'Rincian approval PR-UNIFIED-UI',exact:true}).click();
  await page.getByRole('button',{name:'Setujui PR',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH kebutuhan pembelian diverifikasi');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('PR-UNIFIED-UI · Disetujui',{exact:true}).waitFor();
  assert.equal((await apiGet('/api/purchase-requests/'+purchase.id)).status,'approved');
  await page.locator('dialog').getByRole('button',{name:'Inbox approval',exact:true}).click();
  await page.locator('#approval-status').selectOption('approved');
  await page.getByRole('button',{name:'Rincian approval PCR-UI-001',exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian approval PR-UNIFIED-UI',exact:true}).waitFor();
  console.log('Unified approvals browser QA PASS: combined PR/production queue, deferred order change, exact retry, roles, approval audit, filters, mobile/200%.');
};
