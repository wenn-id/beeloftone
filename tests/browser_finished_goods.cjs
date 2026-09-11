const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key,expected=201){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,expected,await response.clone().text());return response.json();
  }
  const product=await post('/api/products',{sku:'FG-M',name:'CONTOH barang jadi',color:'Sage',size:'M'},'fg-product');
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await post('/api/orders',{reference:'DEMO-FINISHED-GOODS',title:'CONTOH penerimaan barang jadi',owner_id:owner.id,
    due_date:'2026-12-01',lines:[{product_id:product.id,quantity:20}]},'fg-order');
  const line=order.lines[0];
  await post('/api/movements',{line_id:line.id,from_stage:'planned',to_stage:'cutting',quantity:20},'fg-start');
  const material=await post('/api/materials',{code:'FG-CLOTH',name:'CONTOH kain barang jadi',unit:'m'},'fg-material');
  const batch=await post('/api/material-batches',{material_id:material.id,reference:'FG-BATCH',supplier:'CONTOH pemasok',
    location:'Rak G',received_date:'2026-09-11',quantity:'5',reason:'CONTOH bahan'},'fg-batch');
  const issue=await post('/api/material-issues',{batch_id:batch.id,order_id:order.id,quantity:'3',reason:'CONTOH bahan barang jadi'},'fg-issue');
  const run=await post('/api/orders/'+order.id+'/cutting-runs',{reference:'FG-CUT',issue_id:issue.id,used:'2',waste:'0.25',
    reason:'CONTOH cutting barang jadi',outputs:[{line_id:line.id,quantity:20}]},'fg-cut');
  const bundle=await post('/api/cutting-runs/'+run.id+'/bundles',{reference:'FG-BDL',output_movement_id:run.outputs[0].id,
    quantity:20,reason:'CONTOH bundle barang jadi'},'fg-bundle');
  const job=await post('/api/bundles/'+bundle.id+'/sewing-jobs',{reference:'FG-SEW',assignment_type:'internal',assignee:'Line Gudang <A>',
    quantity_out:20,cost:'100000.00',sent_date:'2026-09-11',reason:'CONTOH sewing barang jadi'},'fg-sewing');
  await post('/api/sewing-jobs/'+job.id+'/complete',{completed_quantity:20,defect_quantity:0,missing_quantity:0,
    returned_date:'2026-09-15',reason:'CONTOH sewing selesai'},'fg-sewing-complete');
  const finishing=await post('/api/sewing-jobs/'+job.id+'/finishing-records',{reference:'FG-FIN',quantity:20,
    thread_trimmed:true,ironed:true,labels_attached:true,hangtags_attached:true,packaged:true,
    completed_date:'2026-09-16',reason:'CONTOH finishing lengkap'},'fg-finishing');
  const qc=await post('/api/finishing-records/'+finishing.id+'/qc-records',{reference:'FG-QC',measurement_notes:'Ukuran sesuai',
    visual_notes:'Visual sesuai',defect_type:'Tidak ada',responsible_source:'QC internal',disposition:'Diterima gudang',
    accepted_quantity:20,rework_quantity:0,reject_quantity:0,inspection_date:'2026-09-17',reason:'CONTOH QC pass'},'fg-qc');
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){await page.getByRole('button',{name:/DEMO-FINISHED-GOODS/}).click();await page.getByRole('heading',{name:'CONTOH penerimaan barang jadi',exact:true}).waitFor();}
  async function openGoods(){await page.locator('.order-settings').getByRole('button',{name:'Barang jadi',exact:true}).click();}

  await role(operator);await openOrder();
  let failList=true;
  await page.route('**/api/orders/*/finished-goods-receipts?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar barang jadi sedang sibuk'})});}
    else await route.continue();
  });
  await openGoods();await page.getByText('Daftar barang jadi sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada penerimaan barang jadi untuk order ini.',{exact:false}).waitFor();
  await page.unroute('**/api/orders/*/finished-goods-receipts?*');await page.keyboard.press('Escape');
  await page.locator('.order-settings').getByRole('button',{name:'Final QC',exact:true}).click();
  await page.getByRole('button',{name:'Rincian FG-QC',exact:true}).click();
  await page.getByRole('button',{name:'Terima barang jadi',exact:true}).click();
  await page.getByLabel('Referensi penerimaan',{exact:true}).fill('FG-UI-001');
  assert.equal(await page.getByLabel('SKU / barcode',{exact:true}).inputValue(),'FG-M');
  await page.getByLabel('Lokasi gudang',{exact:true}).fill('Rak Sellable <A>');
  await page.getByLabel('Jumlah sellable',{exact:true}).fill('12');
  await page.getByLabel('Jumlah hold',{exact:true}).fill('3');
  await page.getByLabel('Tanggal diterima',{exact:true}).fill('2026-09-18');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH barang diterima dan dihitung');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/final-qc-records/*/finished-goods-receipts',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian barang jadi',exact:true}).waitFor();
  await page.unroute('**/api/final-qc-records/*/finished-goods-receipts');
  await page.getByRole('heading',{name:'Inventori diterima',exact:true}).waitFor();
  const receipts=await apiGet('/api/orders/'+order.id+'/finished-goods-receipts');
  assert.equal(receipts.length,1);assert.equal(receipts[0].reference,'FG-UI-001');assert.equal(receipts[0].received_quantity,15);
  const totals=(await apiGet('/api/orders/'+order.id)).totals;
  assert.deepEqual([totals.warehouse,totals.qc],[20,0]);
  let inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.hold_quantity],[12,3]);
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-finished-goods-mobile.png')});
  await page.keyboard.press('Escape');await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Final QC',exact:true}).click();
  await page.getByRole('button',{name:'Rincian FG-QC',exact:true}).click();
  await page.getByRole('button',{name:'Terima barang jadi',exact:true}).click();
  await page.keyboard.press('Escape');await page.locator('dialog').waitFor({state:'hidden'});

  await role(viewer);await openOrder();await openGoods();
  await page.getByRole('button',{name:'Rincian FG-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi penerimaan',exact:true}).count(),0);

  await role(admin);await openOrder();await openGoods();
  await page.getByRole('button',{name:'Rincian FG-UI-001',exact:true}).click();
  await post('/api/final-qc-records/'+qc.id+'/reverse',{reason:'Masih dipakai penerimaan'},'fg-block-qc',409);
  await page.getByRole('button',{name:'Koreksi penerimaan',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH klasifikasi stok salah');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Penerimaan barang jadi dikoreksi',exact:true}).waitFor();
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.hold_quantity],[0,0]);
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.warehouse,20);
  console.log('Finished goods browser QA PASS: scan, sellable/hold, inventory, retry, roles, correction, unchanged WIP, empty/error, mobile/200%.');
};
