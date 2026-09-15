const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key,expected=201){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,expected,await response.clone().text());return response.json();
  }
  const product=await post('/api/products',{sku:'FQC-M',name:'CONTOH final QC',color:'Black',size:'M'},'fqc-product');
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await post('/api/orders',{reference:'DEMO-FINAL-QC',title:'CONTOH inspeksi final',owner_id:owner.id,
    due_date:'2026-12-01',lines:[{product_id:product.id,quantity:20}]},'fqc-order');
  const line=order.lines[0];
  await post('/api/movements',{line_id:line.id,from_stage:'planned',to_stage:'cutting',quantity:20},'fqc-start');
  const material=await post('/api/materials',{code:'FQC-CLOTH',name:'CONTOH kain final QC',unit:'m'},'fqc-material');
  const batch=await post('/api/material-batches',{material_id:material.id,reference:'FQC-BATCH',supplier:'CONTOH pemasok',
    location:'Rak Q',received_date:'2026-09-11',quantity:'5',reason:'CONTOH bahan'},'fqc-batch');
  const issue=await post('/api/material-issues',{batch_id:batch.id,order_id:order.id,quantity:'3',reason:'CONTOH bahan final QC'},'fqc-issue');
  const run=await post('/api/orders/'+order.id+'/cutting-runs',{reference:'FQC-CUT',issue_id:issue.id,used:'2',waste:'0.25',
    reason:'CONTOH cutting final QC',outputs:[{line_id:line.id,quantity:20}]},'fqc-cut');
  const bundle=await post('/api/cutting-runs/'+run.id+'/bundles',{reference:'FQC-BDL',output_movement_id:run.outputs[0].id,
    quantity:20,reason:'CONTOH bundle final QC'},'fqc-bundle');
  const job=await post('/api/bundles/'+bundle.id+'/sewing-jobs',{reference:'FQC-SEW',assignment_type:'internal',assignee:'Line QC <A>',
    quantity_out:20,cost:'100000.00',sent_date:'2026-09-11',reason:'CONTOH sewing final QC'},'fqc-sewing');
  await post('/api/sewing-jobs/'+job.id+'/complete',{completed_quantity:20,defect_quantity:0,missing_quantity:0,
    returned_date:'2026-09-15',reason:'CONTOH sewing selesai'},'fqc-sewing-complete');
  const finishing=await post('/api/sewing-jobs/'+job.id+'/finishing-records',{reference:'FQC-FIN',quantity:20,
    thread_trimmed:true,ironed:true,labels_attached:true,hangtags_attached:true,packaged:true,
    completed_date:'2026-09-16',reason:'CONTOH finishing lengkap'},'fqc-finishing');
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){await page.getByRole('button',{name:/DEMO-FINAL-QC/}).click();await page.getByRole('heading',{name:'CONTOH inspeksi final',exact:true}).waitFor();}
  async function openQc(){await page.locator('.order-settings').getByRole('button',{name:'Final QC',exact:true}).click();}

  await role(operator);await openOrder();
  let failList=true;
  await page.route('**/api/orders/*/final-qc-records?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar final QC sedang sibuk'})});}
    else await route.continue();
  });
  await openQc();await page.getByText('Daftar final QC sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada catatan final QC untuk order ini.',{exact:false}).waitFor();
  await page.unroute('**/api/orders/*/final-qc-records?*');await page.keyboard.press('Escape');
  await page.locator('.order-settings').getByRole('button',{name:'Finishing',exact:true}).click();
  await page.getByRole('button',{name:'Rincian FQC-FIN',exact:true}).click();
  await page.getByRole('button',{name:'Catat final QC',exact:true}).click();
  await page.getByLabel('Referensi final QC',{exact:true}).fill('FQC-UI-001');
  await page.getByLabel('Catatan pengukuran',{exact:true}).fill('Lingkar dada sesuai toleransi <aman>');
  await page.getByLabel('Catatan pemeriksaan visual',{exact:true}).fill('Jahitan rapi, satu noda ditemukan');
  await page.getByLabel('Jenis defect',{exact:true}).fill('Noda ringan');
  await page.getByLabel('Sumber penanggung jawab',{exact:true}).fill('Finishing internal');
  await page.getByLabel('Disposition',{exact:true}).fill('Noda masuk rework, cacat berat reject');
  await page.getByLabel('Jumlah diterima',{exact:true}).fill('10');
  await page.getByLabel('Jumlah rework',{exact:true}).fill('2');
  await page.getByLabel('Jumlah reject',{exact:true}).fill('1');
  await page.getByLabel('Tanggal inspeksi',{exact:true}).fill('2026-09-17');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH inspeksi final selesai');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/finishing-records/*/qc-records',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian final QC',exact:true}).waitFor();
  await page.unroute('**/api/finishing-records/*/qc-records');
  await page.getByRole('heading',{name:'Hasil final QC',exact:true}).waitFor();
  const records=await apiGet('/api/orders/'+order.id+'/final-qc-records');
  assert.equal(records.length,1);assert.equal(records[0].reference,'FQC-UI-001');assert.equal(records[0].inspected_quantity,13);
  let totals=(await apiGet('/api/orders/'+order.id)).totals;
  assert.deepEqual([totals.qc,totals.warehouse,totals.rework,totals.reject],[7,10,2,1]);
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-final-qc-mobile.png')});
  await page.keyboard.press('Escape');await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Finishing',exact:true}).click();
  await page.getByRole('button',{name:'Rincian FQC-FIN',exact:true}).click();
  await page.getByRole('button',{name:'Catat final QC',exact:true}).click();
  await page.keyboard.press('Escape');await page.locator('dialog').waitFor({state:'hidden'});

  await role(viewer);await openOrder();await openQc();
  await page.getByRole('button',{name:'Rincian FQC-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi final QC',exact:true}).count(),0);

  await role(admin);await openOrder();await openQc();
  await page.getByRole('button',{name:'Rincian FQC-UI-001',exact:true}).click();
  await post('/api/finishing-records/'+finishing.id+'/reverse',{reason:'Masih dipakai final QC'},'fqc-block-finishing',409);
  await page.getByRole('button',{name:'Koreksi final QC',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH inspeksi perlu dicatat ulang');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Final QC dikoreksi',exact:true}).waitFor();
  totals=(await apiGet('/api/orders/'+order.id)).totals;
  assert.deepEqual([totals.qc,totals.warehouse,totals.rework,totals.reject],[20,0,0,0]);
  console.log('Final QC browser QA PASS: findings, outcomes, lineage, retry, roles, correction, WIP, empty/error, mobile/200%.');
  return {qualityFinishing:finishing,qualityOrder:order,qualityProduct:product};
};
