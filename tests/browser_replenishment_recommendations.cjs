const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,viewer,apiGet,work,costOrder})=>{
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

  const material=(await apiGet('/api/materials')).find(row=>row.code==='COST-CLOTH-UI');
  assert.ok(material);
  await post('/api/products/'+costOrder.lines[0].product_id+'/bom',{expected_revision:0,
    reason:'CONTOH BOM rekomendasi stok',components:[{material_id:material.id,quantity:'1'}]},
    'replenishment-bom');
  const params=new URLSearchParams({as_of:'2026-12-13',window_days:'7',lead_time_days:'14',
    review_period_days:'30',safety_stock_days:'7',batch_multiple:'5',query:'COST-UI',
    marketplace:'Tokopedia <Official>'});
  const report=await apiGet('/api/replenishment-recommendations?'+params);
  assert.equal(report.coverage_complete,true);
  assert.deepEqual([report.product_recommendations[0].sku,
    report.product_recommendations[0].available_quantity,
    report.product_recommendations[0].forecast_daily_rate,
    report.product_recommendations[0].days_of_cover,
    report.product_recommendations[0].projected_stockout_date,
    report.product_recommendations[0].inbound_production_quantity,
    report.product_recommendations[0].recommended_production_quantity],
    ['COST-UI',5,'0.5000','10.00','2026-12-23',5,20]);
  assert.deepEqual([report.material_purchase_recommendations[0].code,
    report.material_purchase_recommendations[0].existing_production_requirement,
    report.material_purchase_recommendations[0].recommended_production_requirement,
    report.material_purchase_recommendations[0].recommended_purchase_quantity],
    ['COST-CLOTH-UI','5.000','20.000','25.000']);

  await role(viewer);
  await page.getByRole('button',{name:'Rekomendasi stok',exact:true}).click();
  // Milestone D: kelima label parameter ini dimiliki juga oleh ai-view, dan getByLabel
  // menyentuh section tersembunyi, jadi batasi pada host laporan ini.
  await page.getByLabel('Forecast sampai tanggal',{exact:true}).fill('2026-12-13');
  await page.locator('#analytics-view').getByLabel('Panjang window demand (hari)',{exact:true}).fill('7');
  await page.locator('#analytics-view').getByLabel('Lead time replenishment (hari)',{exact:true}).fill('14');
  await page.locator('#analytics-view').getByLabel('Periode review stok (hari)',{exact:true}).fill('30');
  await page.locator('#analytics-view').getByLabel('Safety stock (hari)',{exact:true}).fill('7');
  await page.locator('#analytics-view').getByLabel('Kelipatan batch produksi (pcs)',{exact:true}).fill('5');
  await page.getByLabel('Marketplace',{exact:true}).fill('Tokopedia <Official>');
  await page.getByLabel('Cari SKU atau produk',{exact:true}).fill('COST-UI');
  let fail=true;
  await page.route('**/api/replenishment-recommendations?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Rekomendasi stok sedang diperbarui'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Hitung rekomendasi',exact:true}).click();
  await page.locator('#replenishment-message').filter({hasText:'Rekomendasi stok sedang diperbarui'}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByRole('heading',{name:'COST-UI · Stockout sebelum replenishment',exact:true}).waitFor();
  const product=page.locator('[data-replenishment-sku="COST-UI"]');
  await product.getByText('20 pcs',{exact:true}).waitFor();
  await product.getByText('23 Des 2026',{exact:false}).waitFor();
  const materialCard=page.locator('[data-replenishment-material="COST-CLOTH-UI"]');
  await materialCard.getByRole('heading',{name:'COST-CLOTH-UI · Kain <biaya>&',exact:true}).waitFor();
  assert.equal(await materialCard.locator('biaya').count(),0);
  assert.ok((await materialCard.innerText()).includes('25 m'));
  await page.unroute('**/api/replenishment-recommendations?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('#analytics-view').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-replenishment-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');
  console.log('Replenishment browser QA PASS: stockout, production/material recommendations, retry, viewer, escaping, mobile/200%.');
};
