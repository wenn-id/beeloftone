const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key},body:JSON.stringify(body)});
    assert.equal(response.status,201,await response.clone().text());return response.json();
  }
  const products=[];
  for(const size of ['M','L'])products.push(await post('/api/products',{sku:'CUT-'+size,name:'CONTOH cutting',color:'Blue',size},'cut-product-'+size));
  const owner=(await apiGet('/api/users')).find(u=>u.role==='operator');
  const order=await post('/api/orders',{reference:'DEMO-CUTTING',title:'CONTOH hasil cutting',owner_id:owner.id,due_date:'2026-12-01',lines:products.map(p=>({product_id:p.id,quantity:30}))},'cut-order');
  for(const line of order.lines)await post('/api/movements',{line_id:line.id,from_stage:'planned',to_stage:'cutting',quantity:30},'cut-start-'+line.id);
  const material=await post('/api/materials',{code:'CUT-CLOTH',name:'CONTOH kain cutting',unit:'m'},'cut-material');
  const batch=await post('/api/material-batches',{material_id:material.id,reference:'CUT-BATCH',supplier:'CONTOH pemasok',location:'Rak C',received_date:'2026-09-11',quantity:'10',reason:'CONTOH bahan'},'cut-batch');
  await post('/api/material-issues',{batch_id:batch.id,order_id:order.id,quantity:'6',reason:'CONTOH pengeluaran cutting'},'cut-issue');
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){await page.getByRole('button',{name:/DEMO-CUTTING/}).click();await page.getByRole('heading',{name:'CONTOH hasil cutting',exact:true}).waitFor();}
  async function openRuns(){await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Hasil cutting',exact:true}).click();}
  await role(operator);await openOrder();await openRuns();
  await page.getByText('Belum ada hasil cutting yang dihubungkan dengan pemakaian bahan.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Catat hasil cutting',exact:true}).click();
  await page.getByLabel('Referensi hasil cutting',{exact:true}).fill('CUT <M+L>');
  await page.getByLabel('Bahan terpakai untuk hasil ini',{exact:true}).fill('3');
  await page.getByLabel('Waste cutting',{exact:true}).fill('0.5');
  await page.getByLabel('Hasil CUT-M (pcs)',{exact:true}).fill('31');
  assert.equal(await page.getByLabel('Hasil CUT-M (pcs)',{exact:true}).evaluate(el=>el.validity.rangeOverflow),true);
  await page.getByLabel('Hasil CUT-M (pcs)',{exact:true}).fill('20');
  await page.getByLabel('Hasil CUT-L (pcs)',{exact:true}).fill('10');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH hasil potong <aman>');
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),'Cutting form overflow');
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),'Cutting 200% overflow');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-cutting-form-mobile.png')});
  let drop=true;
  await page.route('**/api/orders/*/cutting-runs',async route=>{if(route.request().method()==='POST' && drop){drop=false;await route.fetch();await route.abort('failed');}else await route.continue();});
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'30 pcs hasil cutting',exact:true}).waitFor();
  await page.unroute('**/api/orders/*/cutting-runs');
  assert.equal(await page.getByRole('button',{name:'Koreksi hasil cutting',exact:true}).count(),0);
  const runs=await apiGet('/api/orders/'+order.id+'/cutting-runs');assert.equal(runs.length,1);
  let current=await apiGet('/api/orders/'+order.id);assert.equal(current.totals.sewing,30);assert.equal(current.totals.cutting,30);
  assert.equal((await apiGet('/api/material-batches/'+batch.id)).balance,'4.000');
  assert.equal((await apiGet('/api/orders/'+order.id+'/material-consumption'))[0].unreported,'2.500');
  await page.getByRole('button',{name:'Buka order produksi',exact:true}).click();
  await page.getByRole('button',{name:'Pemakaian & waste',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi pemakaian',exact:true}).count(),0);
  await page.locator('#consumption-history').getByRole('button',{name:'Hasil cutting',exact:true}).click();
  await page.getByRole('heading',{name:'30 pcs hasil cutting',exact:true}).waitFor();
  await role(viewer);await openOrder();await openRuns();
  assert.equal(await page.getByRole('button',{name:'Catat hasil cutting',exact:true}).count(),0);
  await page.getByRole('button',{name:'Rincian CUT <M+L>',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi hasil cutting',exact:true}).count(),0);
  await role(admin);await openOrder();await openRuns();
  await page.getByRole('button',{name:'Rincian CUT <M+L>',exact:true}).click();
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS || work,'beeloft-cutting-output.png')});
  await page.getByRole('button',{name:'Koreksi hasil cutting',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH salah catat hasil');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Hasil cutting dikoreksi',exact:true}).waitFor();
  current=await apiGet('/api/orders/'+order.id);assert.equal(current.totals.cutting,60);assert.equal(current.totals.sewing,0);
  assert.equal((await apiGet('/api/orders/'+order.id+'/material-consumption'))[0].unreported,'6.000');
  assert.equal((await apiGet('/api/material-batches/'+batch.id)).balance,'4.000');
  await page.keyboard.press('Escape');
  console.log('Cutting browser QA PASS: multi-size output, linked consumption/waste, exact reload retry, source history, role checks, whole correction, mobile/200%.');
};
