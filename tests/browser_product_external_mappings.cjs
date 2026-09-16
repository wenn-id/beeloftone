const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,openSidebarDestination,admin,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  const order=(await apiGet('/api/orders')).find(row=>row.reference==='DEMO-PROD-001');
  const product=order.lines[0];
  await role(admin);
  await openSidebarDestination('Master SKU');
  await page.getByRole('button',{name:'Jubelio '+product.sku,exact:true}).click();
  await page.getByRole('heading',{name:'Mapping SKU Jubelio',exact:true}).waitFor();
  await page.getByText('Belum dipetakan',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Hubungkan Jubelio',exact:true}).click();
  await page.getByLabel('ID eksternal Jubelio',{exact:true}).fill('item-<42>');
  await page.getByLabel('SKU Jubelio',{exact:true}).fill('JUB-<LUNA>-M');
  await page.getByLabel('Alasan mapping',{exact:true}).fill('CONTOH mapping master sebelum read sync');
  let dropped=true;
  await page.route('**/api/products/*/external-mappings/jubelio',async route=>{
    if(route.request().method()==='POST'&&dropped){dropped=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Mapping SKU Jubelio',exact:true}).waitFor();
  await page.getByText('JUB-<LUNA>-M',{exact:true}).waitFor();
  await page.getByText('item-<42>',{exact:true}).waitFor();
  assert.equal(await page.locator('luna').count(),0);
  await page.unroute('**/api/products/*/external-mappings/jubelio');
  const history=await apiGet('/api/products/'+product.product_id+'/external-mappings/jubelio/history');
  assert.equal(history.length,1);

  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-product-mapping-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Riwayat mapping',exact:true}).click();
  await page.getByText('CONTOH mapping master sebelum read sync',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await openSidebarDestination('Integrasi');
  const coverage=page.locator('[data-integration-system="jubelio"]');
  await coverage.getByText(/Mapping SKU: 1 dari/).waitFor();
  await page.getByRole('button',{name:'Buka Master SKU',exact:true}).click();
  await page.getByRole('button',{name:'Jubelio '+product.sku,exact:true}).click();
  await page.getByRole('button',{name:'Ubah mapping',exact:true}).waitFor();

  await role(viewer);
  await openSidebarDestination('Master SKU');
  await page.getByRole('button',{name:'Jubelio '+product.sku,exact:true}).click();
  await page.getByText('JUB-<LUNA>-M',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Ubah mapping',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Lepaskan mapping',exact:true}).count(),0);
  await page.getByRole('button',{name:'Riwayat mapping',exact:true}).click();
  await page.getByText('CONTOH mapping master sebelum read sync',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Product mapping browser QA PASS: empty state, idempotent retry, escaping, coverage, history, roles, mobile/200%.');
};
