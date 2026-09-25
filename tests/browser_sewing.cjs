const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key,expected=201){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,expected,await response.clone().text());
    return response.json();
  }
  const product=await post('/api/products',{sku:'SEW-M',name:'CONTOH sewing',color:'Blue',size:'M'},'sew-product');
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await post('/api/orders',{reference:'DEMO-SEWING',title:'CONTOH job sewing',owner_id:owner.id,
    due_date:'2026-12-01',lines:[{product_id:product.id,quantity:20}]},'sew-order');
  const line=order.lines[0];
  await post('/api/movements',{line_id:line.id,from_stage:'planned',to_stage:'cutting',quantity:20},'sew-start');
  const material=await post('/api/materials',{code:'SEW-CLOTH',name:'CONTOH kain sewing',unit:'m'},'sew-material');
  const batch=await post('/api/material-batches',{material_id:material.id,reference:'SEW-BATCH',supplier:'CONTOH pemasok',
    location:'Rak S',received_date:'2026-09-11',quantity:'5',reason:'CONTOH bahan'},'sew-batch');
  const issue=await post('/api/material-issues',{batch_id:batch.id,order_id:order.id,quantity:'3',reason:'CONTOH bahan sewing'},'sew-issue');
  const run=await post('/api/orders/'+order.id+'/cutting-runs',{reference:'SEW-CUT',issue_id:issue.id,used:'2',waste:'0.25',
    reason:'CONTOH cutting sewing',outputs:[{line_id:line.id,quantity:20}]},'sew-cut');
  const bundle=await post('/api/cutting-runs/'+run.id+'/bundles',{reference:'SEW-BDL',output_movement_id:run.outputs[0].id,
    quantity:20,reason:'CONTOH bundle sewing'},'sew-bundle');
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){await page.getByRole('button',{name:/DEMO-SEWING/}).click();await page.getByRole('heading',{name:'CONTOH job sewing',exact:true}).waitFor();}
  async function openJobs(){await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Sewing / makloon',exact:true}).click();}

  await role(operator);await openOrder();
  let failList=true;
  await page.route('**/api/orders/*/sewing-jobs?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar job sedang sibuk'})});}
    else await route.continue();
  });
  await openJobs();
  await page.getByText('Daftar job sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada job sewing untuk order ini.',{exact:false}).waitFor();
  await page.unroute('**/api/orders/*/sewing-jobs?*');
  await page.keyboard.press('Escape');
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Bundle',exact:true}).click();
  await page.getByRole('button',{name:'Rincian SEW-BDL',exact:true}).click();
  await page.getByRole('button',{name:'Kirim ke sewing',exact:true}).click();
  await page.getByLabel('Referensi job',{exact:true}).fill('SEW-UI-001');
  await page.getByLabel('Jenis penugasan',{exact:true}).selectOption('makloon');
  await page.getByLabel('Pelaksana / vendor',{exact:true}).fill('Atelier <Satu>');
  await page.getByLabel('Jumlah keluar',{exact:true}).fill('12');
  await page.getByLabel('Biaya total (Rp)',{exact:true}).fill('240000');
  await page.getByLabel('Tanggal kirim',{exact:true}).fill('2026-09-11');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH kirim makloon <aman>');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/bundles/*/sewing-jobs',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian job sewing',exact:true}).waitFor();
  await page.unroute('**/api/bundles/*/sewing-jobs');
  const jobs=await apiGet('/api/orders/'+order.id+'/sewing-jobs');
  assert.equal(jobs.length,1);assert.equal(jobs[0].reference,'SEW-UI-001');assert.equal(jobs[0].quantity_out,12);
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.sewing,20);
  await page.getByRole('button',{name:'Catat hasil sewing',exact:true}).click();
  await page.getByLabel('Jumlah selesai',{exact:true}).fill('10');
  await page.getByLabel('Jumlah defect',{exact:true}).fill('1');
  await page.getByLabel('Jumlah missing',{exact:true}).fill('1');
  await page.getByLabel('Tanggal kembali',{exact:true}).fill('2026-09-15');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH hasil makloon diterima');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Hasil sewing diterima',exact:true}).waitFor();
  const totals=(await apiGet('/api/orders/'+order.id)).totals;
  assert.deepEqual([totals.sewing,totals.finishing,totals.reject],[8,10,2]);
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-sewing-mobile.png')});
  await page.keyboard.press('Escape');await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Bundle',exact:true}).click();
  await page.getByRole('button',{name:'Rincian SEW-BDL',exact:true}).click();
  await page.getByRole('button',{name:'Kirim ke sewing',exact:true}).click();
  await page.keyboard.press('Escape');await page.locator('dialog').waitFor({state:'hidden'});

  await role(viewer);await openOrder();await openJobs();
  await page.getByRole('button',{name:'Rincian SEW-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Catat hasil sewing',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Koreksi job sewing',exact:true}).count(),0);

  await role(admin);await openOrder();await openJobs();
  await page.getByRole('button',{name:'Rincian SEW-UI-001',exact:true}).click();
  await post('/api/bundles/'+bundle.id+'/reverse',{reason:'Masih dipakai job'},'sew-block-bundle',409);
  await page.getByRole('button',{name:'Koreksi job sewing',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH hasil perlu dicatat ulang');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Job sewing dikoreksi',exact:true}).waitFor();
  const restored=(await apiGet('/api/orders/'+order.id)).totals;
  assert.deepEqual([restored.sewing,restored.finishing,restored.reject],[20,0,0]);
  console.log('Sewing browser QA PASS: assignment, cost, outcome, turnaround, retry, roles, correction, WIP, empty/error, mobile/200%.');
};
