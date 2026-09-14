const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work,costOrder,costRun})=>{
  async function post(url,body,key,expected=201,apiKey=admin){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':apiKey,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,expected,await response.clone().text());return response.json();
  }
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){
    await page.locator('#brand').click();
    await page.getByLabel('Cari order atau SKU').fill(costOrder.reference);
    await page.getByRole('button',{name:'Cari order',exact:true}).click();
    await page.locator('.order-row').filter({hasText:costOrder.reference}).getByRole('button').click();
    await page.getByRole('heading',{name:costOrder.title,exact:true}).waitFor();
  }

  const bundle=await post('/api/cutting-runs/'+costRun.id+'/bundles',{reference:'MARGIN-BUNDLE-UI',
    output_movement_id:costRun.outputs[0].id,quantity:10,reason:'CONTOH bundle margin'},'margin-bundle');
  let job=await post('/api/bundles/'+bundle.id+'/sewing-jobs',{reference:'MARGIN-SEW-UI',
    assignment_type:'internal',assignee:'Tim jahit internal',quantity_out:10,cost:'0',
    sent_date:'2026-12-03',reason:'CONTOH sewing margin'},'margin-sewing');
  job=await post('/api/sewing-jobs/'+job.id+'/complete',{completed_quantity:10,defect_quantity:0,
    missing_quantity:0,returned_date:'2026-12-04',reason:'CONTOH sewing selesai'},'margin-sewing-complete');
  const finishing=await post('/api/sewing-jobs/'+job.id+'/finishing-records',{reference:'MARGIN-FIN-UI',
    quantity:10,thread_trimmed:true,ironed:true,labels_attached:true,hangtags_attached:true,
    packaged:true,completed_date:'2026-12-05',reason:'CONTOH finishing lengkap'},'margin-finishing');
  const qc=await post('/api/finishing-records/'+finishing.id+'/qc-records',{reference:'MARGIN-QC-UI',
    measurement_notes:'CONTOH ukuran sesuai',visual_notes:'CONTOH visual sesuai',defect_type:'Tidak ada',
    responsible_source:'Tidak ada',disposition:'Terima semua',accepted_quantity:10,rework_quantity:0,
    reject_quantity:0,inspection_date:'2026-12-06',reason:'CONTOH QC lengkap'},'margin-qc');
  const receipt=await post('/api/final-qc-records/'+qc.id+'/finished-goods-receipts',{
    reference:'MARGIN-FG-UI',scanned_sku:qc.sku,location:'Rak Margin UI',sellable_quantity:10,
    hold_quantity:0,received_date:'2026-12-07',reason:'CONTOH barang jadi margin'},'margin-fg');
  const reservation=await post('/api/finished-goods-receipts/'+receipt.id+'/marketplace-reservations',{
    reference:'MARGIN-RES-UI',marketplace:'Tokopedia <Official>',external_order_reference:'TKP-MARGIN-UI',
    location:'Rak Margin UI',quantity:5,reserved_date:'2026-12-08',reason:'CONTOH reservasi margin'},'margin-reservation');
  const pick=await post('/api/marketplace-reservations/'+reservation.id+'/picks',{reference:'MARGIN-PICK-UI',
    scanned_code:receipt.scan_code,quantity:5,staging_location:'Meja Margin UI',picked_date:'2026-12-09',
    reason:'CONTOH pick margin'},'margin-pick');
  const pack=await post('/api/marketplace-picks/'+pick.id+'/packs',{reference:'MARGIN-PACK-UI',quantity:5,
    packed_date:'2026-12-10',reason:'CONTOH pack margin'},'margin-pack');
  const shipment=await post('/api/marketplace-packs/'+pack.id+'/shipments',{reference:'MARGIN-SHIP-UI',
    quantity:5,carrier:'JNE',tracking_number:'MARGIN-TRACK-UI',shipped_date:'2026-12-11',
    reason:'CONTOH shipment margin'},'margin-shipment');

  await role(operator);await openOrder();
  let fail=true;
  await page.route('**/api/orders/*/contribution-margin',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Perhitungan margin sedang sibuk'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Margin kontribusi',exact:true}).click();
  await page.getByText('Perhitungan margin sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Cakupan margin belum lengkap',{exact:true}).waitFor();
  await page.getByText('Pengiriman MARGIN-SHIP-UI belum memiliki settlement penjualan.',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/contribution-margin');
  await page.getByRole('button',{name:'Catat settlement',exact:true}).click();
  await page.getByLabel('Referensi settlement',{exact:true}).fill('SETTLE-UI-<1>');
  await page.getByLabel('Omzet kotor',{exact:true}).fill('500');
  await page.getByLabel('Diskon penjual',{exact:true}).fill('20');
  await page.getByLabel('Refund pelanggan',{exact:true}).fill('0');
  await page.getByLabel('Fee marketplace',{exact:true}).fill('50');
  await page.getByLabel('Biaya kirim ditanggung penjual',{exact:true}).fill('10');
  await page.getByLabel('Biaya variabel lain',{exact:true}).fill('5');
  await page.getByLabel('Tanggal settlement',{exact:true}).fill('2026-12-12');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH settlement final <aman>');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/marketplace-shipments/*/sale-settlements',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian settlement penjualan',exact:true}).waitFor();
  await page.unroute('**/api/marketplace-shipments/*/sale-settlements');
  await page.getByText('Tokopedia <Official> · TKP-MARGIN-UI',{exact:true}).waitFor();
  await page.getByText('Rp480,00',{exact:true}).waitFor();
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-contribution-margin-mobile.png')});

  const settlements=await apiGet('/api/orders/'+costOrder.id+'/sale-settlements');
  assert.equal(settlements.length,1);assert.equal(settlements[0].shipment_id,shipment.id);
  const report=await apiGet('/api/orders/'+costOrder.id+'/contribution-margin');
  assert.deepEqual([report.status,report.net_revenue,report.variable_selling_cost,
    report.allocated_production_cost,report.contribution_margin,report.contribution_margin_rate],
    ['complete','480.00','65.00','100.00','315.00','65.63']);

  await role(viewer);await openOrder();
  await page.getByRole('button',{name:'Margin kontribusi',exact:true}).click();
  await page.getByText('Cakupan margin lengkap',{exact:true}).waitFor();
  await page.getByText('Rp315,00',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Catat settlement',exact:true}).count(),0);
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');await page.locator('#brand').click();
  await page.getByRole('button',{name:'Reset filter',exact:true}).click();
  await page.locator('.order-row').first().waitFor();
  console.log('Contribution margin browser QA PASS: settlement ledger, exact allocation, retry, lost-response recovery, viewer access, escaping, mobile/200%.');
};
