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
  const product=await post('/api/products',{sku:'FIN-M',name:'CONTOH finishing',color:'Ivory',size:'M'},'fin-product');
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await post('/api/orders',{reference:'DEMO-FINISHING',title:'CONTOH proses finishing',owner_id:owner.id,
    due_date:'2026-12-01',lines:[{product_id:product.id,quantity:20}]},'fin-order');
  const line=order.lines[0];
  await post('/api/movements',{line_id:line.id,from_stage:'planned',to_stage:'cutting',quantity:20},'fin-start');
  const material=await post('/api/materials',{code:'FIN-CLOTH',name:'CONTOH kain finishing',unit:'m'},'fin-material');
  const batch=await post('/api/material-batches',{material_id:material.id,reference:'FIN-BATCH',supplier:'CONTOH pemasok',
    location:'Rak F',received_date:'2026-09-11',quantity:'5',reason:'CONTOH bahan'},'fin-batch');
  const issue=await post('/api/material-issues',{batch_id:batch.id,order_id:order.id,quantity:'3',reason:'CONTOH bahan finishing'},'fin-issue');
  const run=await post('/api/orders/'+order.id+'/cutting-runs',{reference:'FIN-CUT',issue_id:issue.id,used:'2',waste:'0.25',
    reason:'CONTOH cutting finishing',outputs:[{line_id:line.id,quantity:20}]},'fin-cut');
  const bundle=await post('/api/cutting-runs/'+run.id+'/bundles',{reference:'FIN-BDL',output_movement_id:run.outputs[0].id,
    quantity:20,reason:'CONTOH bundle finishing'},'fin-bundle');
  const job=await post('/api/bundles/'+bundle.id+'/sewing-jobs',{reference:'FIN-SEW',assignment_type:'internal',assignee:'Line Finishing <A>',
    quantity_out:20,cost:'100000.00',sent_date:'2026-09-11',reason:'CONTOH sewing sebelum finishing'},'fin-sewing');
  await post('/api/sewing-jobs/'+job.id+'/complete',{completed_quantity:16,defect_quantity:2,missing_quantity:2,
    returned_date:'2026-09-15',reason:'CONTOH sewing selesai'},'fin-sewing-complete');
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){await page.getByRole('button',{name:/DEMO-FINISHING/}).click();await page.getByRole('heading',{name:'CONTOH proses finishing',exact:true}).waitFor();}
  async function openFinishing(){await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Finishing',exact:true}).click();}

  await role(operator);await openOrder();
  let failList=true;
  await page.route('**/api/orders/*/finishing-records?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar finishing sedang sibuk'})});}
    else await route.continue();
  });
  await openFinishing();
  await page.getByText('Daftar finishing sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada catatan finishing untuk order ini.',{exact:false}).waitFor();
  await page.unroute('**/api/orders/*/finishing-records?*');
  await page.keyboard.press('Escape');
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Sewing / makloon',exact:true}).click();
  await page.getByRole('button',{name:'Rincian FIN-SEW',exact:true}).click();
  await page.getByRole('button',{name:'Catat finishing',exact:true}).click();
  await page.getByLabel('Referensi finishing',{exact:true}).fill('FIN-UI-001');
  await page.getByLabel('Jumlah selesai finishing',{exact:true}).fill('6');
  for(const label of ['Benang sudah dirapikan','Sudah disetrika','Label sudah terpasang','Hangtag sudah terpasang','Sudah dikemas'])
    await page.getByLabel(label,{exact:true}).check();
  await page.getByLabel('Tanggal selesai',{exact:true}).fill('2026-09-16');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH finishing lengkap <aman>');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/sewing-jobs/*/finishing-records',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian finishing',exact:true}).waitFor();
  await page.unroute('**/api/sewing-jobs/*/finishing-records');
  await page.getByRole('heading',{name:'Checklist finishing lengkap',exact:true}).waitFor();
  const records=await apiGet('/api/orders/'+order.id+'/finishing-records');
  assert.equal(records.length,1);assert.equal(records[0].reference,'FIN-UI-001');assert.equal(records[0].quantity,6);
  let totals=(await apiGet('/api/orders/'+order.id)).totals;
  assert.deepEqual([totals.finishing,totals.qc,totals.reject],[10,6,4]);
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-finishing-mobile.png')});
  await page.keyboard.press('Escape');await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Sewing / makloon',exact:true}).click();
  await page.getByRole('button',{name:'Rincian FIN-SEW',exact:true}).click();
  await page.getByRole('button',{name:'Catat finishing',exact:true}).click();
  await page.keyboard.press('Escape');await page.locator('dialog').waitFor({state:'hidden'});

  await role(viewer);await openOrder();await openFinishing();
  await page.getByRole('button',{name:'Rincian FIN-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi finishing',exact:true}).count(),0);

  await role(admin);await openOrder();await openFinishing();
  await page.getByRole('button',{name:'Rincian FIN-UI-001',exact:true}).click();
  await post('/api/sewing-jobs/'+job.id+'/reverse',{reason:'Masih dipakai finishing'},'fin-block-sewing',409);
  await page.getByRole('button',{name:'Koreksi finishing',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH checklist perlu dicatat ulang');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Finishing dikoreksi',exact:true}).waitFor();
  totals=(await apiGet('/api/orders/'+order.id)).totals;
  assert.deepEqual([totals.finishing,totals.qc,totals.reject],[16,0,4]);
  console.log('Finishing browser QA PASS: checklist, partial completion, lineage, retry, roles, correction, WIP, empty/error, mobile/200%.');
};
