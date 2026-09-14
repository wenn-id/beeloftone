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
  const product=await post('/api/products',{sku:'BND-M',name:'CONTOH bundling',color:'Blue',size:'M'},'bundle-product');
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await post('/api/orders',{reference:'DEMO-BUNDLING',title:'CONTOH alokasi bundle',
    owner_id:owner.id,due_date:'2026-12-01',lines:[{product_id:product.id,quantity:20}]},'bundle-order');
  const line=order.lines[0];
  await post('/api/movements',{line_id:line.id,from_stage:'planned',to_stage:'cutting',quantity:20},'bundle-start');
  const material=await post('/api/materials',{code:'BND-CLOTH',name:'CONTOH kain bundle',unit:'m'},'bundle-material');
  const batch=await post('/api/material-batches',{material_id:material.id,reference:'BND-BATCH',
    supplier:'CONTOH pemasok',location:'Rak B',received_date:'2026-09-11',quantity:'5',reason:'CONTOH bahan'},'bundle-batch');
  const issue=await post('/api/material-issues',{batch_id:batch.id,order_id:order.id,quantity:'3',
    reason:'CONTOH bahan cutting bundle'},'bundle-issue');
  const run=await post('/api/orders/'+order.id+'/cutting-runs',{reference:'BND-CUT',issue_id:issue.id,
    used:'2',waste:'0.25',reason:'CONTOH hasil cutting untuk bundle',outputs:[{line_id:line.id,quantity:20}]},'bundle-cut');
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  async function openOrder(){
    await page.getByRole('button',{name:/DEMO-BUNDLING/}).click();
    await page.getByRole('heading',{name:'CONTOH alokasi bundle',exact:true}).waitFor();
  }
  await role(operator);
  await openOrder();
  let failList=true;
  await page.route('**/api/orders/*/bundles?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar bundle sedang sibuk'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Bundle',exact:true}).click();
  await page.getByText('Daftar bundle sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada bundle untuk order ini.',{exact:false}).waitFor();
  await page.unroute('**/api/orders/*/bundles?*');
  await page.keyboard.press('Escape');
  await page.locator('.order-settings').getByRole('button',{name:'Hasil cutting',exact:true}).click();
  await page.getByRole('button',{name:'Rincian BND-CUT',exact:true}).click();
  await page.getByRole('button',{name:'Buat bundle',exact:true}).click();
  await page.getByLabel('Bundle ID',{exact:true}).fill('BDL-UI-001');
  await page.getByLabel('Jumlah bundle',{exact:true}).fill('8');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH bundle pertama <aman>');
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.querySelector('dialog').scrollWidth<=document.querySelector('dialog').clientWidth),true);
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.equal(await page.evaluate(()=>document.querySelector('dialog').scrollWidth<=document.querySelector('dialog').clientWidth),true);
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/cutting-runs/*/bundles',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();
  await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian bundle',exact:true}).waitFor();
  await page.unroute('**/api/cutting-runs/*/bundles');
  const bundles=await apiGet('/api/orders/'+order.id+'/bundles');
  assert.equal(bundles.length,1);
  assert.equal(bundles[0].reference,'BDL-UI-001');
  assert.equal(bundles[0].quantity,8);
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.sewing,20);
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-bundle-mobile.png')});
  await page.keyboard.press('Escape');
  await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Hasil cutting',exact:true}).click();
  await page.getByRole('button',{name:'Rincian BND-CUT',exact:true}).click();
  await page.getByRole('button',{name:'Buat bundle',exact:true}).click();
  await page.keyboard.press('Escape');
  await page.locator('dialog').waitFor({state:'hidden'});
  await role(viewer);
  await openOrder();
  await page.getByRole('button',{name:'Bundle',exact:true}).click();
  await page.getByRole('button',{name:'Rincian BDL-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Buat bundle',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Koreksi bundle',exact:true}).count(),0);
  await role(admin);
  await openOrder();
  await page.getByRole('button',{name:'Bundle',exact:true}).click();
  await page.getByRole('button',{name:'Rincian BDL-UI-001',exact:true}).click();
  await post('/api/cutting-runs/'+run.id+'/reverse',{reason:'Harus tertahan bundle'},'blocked-cut',409);
  await page.getByRole('button',{name:'Koreksi bundle',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH koreksi label bundle');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Sudah dikoreksi',exact:true}).waitFor();
  assert.equal((await apiGet('/api/bundles/'+bundles[0].id)).status,'corrected');
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.sewing,20);
  console.log('Bundling browser QA PASS: linked source, exact retry, roles, correction, unchanged WIP, mobile/200%.');
  return {order,run};
};
