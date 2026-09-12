const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,viewer,apiGet,work})=>{
  async function post(url,body,key){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,201,await response.clone().text());return response.json();
  }
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  async function openOrder(reference,title){
    await page.locator('#brand').click();
    await page.getByLabel('Cari order atau SKU').fill(reference);
    await page.getByRole('button',{name:'Cari order',exact:true}).click();
    const row=page.locator('.order-row').filter({hasText:reference});
    await row.waitFor();await row.locator('[data-action="detail"]').click();
    await page.getByRole('heading',{name:title,exact:true}).waitFor();
  }

  const product=await post('/api/products',{sku:'COST-UI',name:'CONTOH produk biaya',color:'Biru',size:'M'},'cost-product');
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await post('/api/orders',{reference:'DEMO-COST-UI',title:'CONTOH biaya aktual',
    owner_id:owner.id,due_date:'2026-12-31',lines:[{product_id:product.id,quantity:10}]},'cost-order');
  const material=await post('/api/materials',{code:'COST-CLOTH-UI',name:'Kain <biaya>&',unit:'m'},'cost-material');
  const supplier=(await apiGet('/api/suppliers'))[0];
  let pr=await post('/api/purchase-requests',{reference:'PR-COST-UI',order_id:order.id,
    required_date:'2026-12-01',estimated_value:'200.00',reason:'CONTOH bahan costing',
    lines:[{material_id:material.id,quantity:'2'}]},'cost-pr');
  pr=await post('/api/purchase-requests/'+pr.id+'/decisions',{status:'approved',
    expected_revision:pr.revision,reason:'CONTOH kebutuhan disetujui'},'cost-pr-approved');
  let po=await post('/api/purchase-orders',{reference:'PO-COST-UI',request_id:pr.id,
    expected_revision:pr.revision,supplier_id:supplier.id,expected_date:'2026-12-02',
    terms:'CONTOH tunai',reason:'CONTOH harga costing',
    prices:[{material_id:material.id,unit_price:'100'}]},'cost-po');
  po=await post('/api/purchase-orders/'+po.id+'/decisions',{status:'approved',
    expected_revision:po.revision,reason:'CONTOH PO disetujui'},'cost-po-approved');
  const batch=await post('/api/purchase-orders/'+po.id+'/receipts',{material_id:material.id,
    reference:'COST-BATCH-UI',location:'Rak biaya',received_date:'2026-12-02',quantity:'2',
    reason:'CONTOH bahan diterima'},'cost-receipt');
  const issue=await post('/api/material-issues',{batch_id:batch.id,order_id:order.id,quantity:'2',
    reason:'CONTOH keluar untuk produksi'},'cost-issue');
  await post('/api/material-consumption',{issue_id:issue.id,used:'1.5',waste:'0.5',
    reason:'CONTOH pemakaian dan waste'},'cost-consumption');
  const empty=await post('/api/orders',{reference:'DEMO-COST-GAP-UI',title:'CONTOH biaya belum lengkap',
    owner_id:owner.id,due_date:'2026-12-31',lines:[{product_id:product.id,quantity:5}]},'cost-empty-order');

  const report=await apiGet('/api/orders/'+order.id+'/production-cost');
  assert.deepEqual([report.status,report.material_cost,report.sewing_cost,report.total_cost,
    report.cost_per_target_unit],['complete','200.00','0.00','200.00','20.00']);
  assert.equal(report.materials[0].batch_reference,'COST-BATCH-UI');

  await role(viewer);await openOrder(order.reference,order.title);
  let fail=true;
  await page.route('**/api/orders/*/production-cost',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Perhitungan biaya sedang sibuk'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Biaya aktual',exact:true}).click();
  await page.getByText('Perhitungan biaya sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Cakupan sumber biaya lengkap',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/production-cost');
  await page.getByRole('heading',{name:'COST-CLOTH-UI · Kain <biaya>&',exact:true}).waitFor();
  await page.getByText('Total biaya').waitFor();
  await page.getByText('Rp200,00',{exact:true}).first().waitFor();
  await page.getByRole('button',{name:'Batch COST-BATCH-UI',exact:true}).waitFor();
  await page.getByRole('button',{name:'PO PO-COST-UI',exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-production-cost-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.keyboard.press('Escape');

  await openOrder(empty.reference,empty.title);
  await page.getByRole('button',{name:'Biaya aktual',exact:true}).click();
  await page.getByText('Cakupan biaya belum lengkap',{exact:true}).waitFor();
  await page.getByText('Belum ada pemakaian bahan yang tercatat.',{exact:true}).waitFor();
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');
  await page.locator('#brand').click();
  await page.getByRole('button',{name:'Reset filter',exact:true}).click();
  await page.locator('.order-row').first().waitFor();
  console.log('Production cost browser QA PASS: exact PO material cost, explicit coverage gap, error retry, viewer access, escaping, mobile/200%.');
};
