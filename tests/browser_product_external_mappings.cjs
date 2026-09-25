const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,openSidebarDestination,admin,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  // Menahan satu GET mapping sesudah responsnya tiba, supaya dialog bisa ditutup dan draft
  // lain sempat diketik sebelum respons lama dilepas.
  async function holdMappingResponse(){
    const held={};
    held.started=new Promise(resolve=>held.signal=resolve);
    held.released=new Promise(resolve=>held.release=resolve);
    held.finished=new Promise(resolve=>held.done=resolve);
    await page.route('**/api/products/*/external-mappings/jubelio',async route=>{
      if(route.request().method()!=='GET')return route.continue();
      const response=await route.fetch();held.signal();
      await held.released;await route.fulfill({response});held.done();
    });
    return held;
  }
  const order=(await apiGet('/api/orders')).find(row=>row.reference==='DEMO-PROD-001');
  const product=order.lines[0];
  await role(admin);
  await openSidebarDestination('Master SKU');
  await page.getByRole('button',{name:'Jubelio '+product.sku,exact:true}).click();
  await page.getByRole('heading',{name:'Mapping SKU Jubelio',exact:true}).waitFor();
  await page.locator('#dialog').getByText('Belum dipetakan',{exact:true}).waitFor();
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
  await page.locator('#dialog').getByText('JUB-<LUNA>-M',{exact:true}).waitFor();
  await page.locator('#dialog').getByText('item-<42>',{exact:true}).waitFor();
  assert.equal(await page.locator('luna').count(),0);
  await page.unroute('**/api/products/*/external-mappings/jubelio');
  const history=await apiGet('/api/products/'+product.product_id+'/external-mappings/jubelio/history');
  assert.equal(history.length,1);
  // Respons lama tidak boleh mengganti dialog yang dibuka sesudah dialog asal ditutup.
  const delayedEdit=await holdMappingResponse();
  await page.getByRole('button',{name:'Ubah mapping',exact:true}).click();
  await delayedEdit.started;
  await page.keyboard.press('Escape');
  await page.locator('#dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Tambah SKU',exact:true}).click();
  await page.getByLabel('Kode SKU',{exact:true}).fill('UNRELATED-DRAFT');
  delayedEdit.release();await delayedEdit.finished;
  await page.waitForTimeout(100);
  assert.equal(await page.getByRole('heading',{name:'Tambah SKU',exact:true}).isVisible(),true);
  assert.equal(await page.getByLabel('Kode SKU',{exact:true}).inputValue(),'UNRELATED-DRAFT');
  assert.equal(await page.getByRole('heading',{name:'Ubah mapping Jubelio',exact:true}).count(),0);
  assert.equal(await page.getByRole('heading',{name:'Hubungkan SKU ke Jubelio',exact:true}).count(),0);
  await page.keyboard.press('Escape');
  await page.locator('#dialog').waitFor({state:'hidden'});
  await page.unroute('**/api/products/*/external-mappings/jubelio');
  // Jalur unmap memakai guard yang sama: respons lama tidak boleh membuka lagi dialog mapping.
  await page.getByRole('button',{name:'Jubelio '+product.sku,exact:true}).click();
  await page.getByRole('heading',{name:'Mapping SKU Jubelio',exact:true}).waitFor();
  const delayedUnmap=await holdMappingResponse();
  await page.getByRole('button',{name:'Lepaskan mapping',exact:true}).click();
  await delayedUnmap.started;
  await page.keyboard.press('Escape');
  await page.locator('#dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Tambah SKU',exact:true}).click();
  await page.getByLabel('Kode SKU',{exact:true}).fill('UNRELATED-UNMAP-DRAFT');
  delayedUnmap.release();await delayedUnmap.finished;
  await page.waitForTimeout(100);
  assert.equal(await page.getByRole('heading',{name:'Tambah SKU',exact:true}).isVisible(),true);
  assert.equal(await page.getByLabel('Kode SKU',{exact:true}).inputValue(),'UNRELATED-UNMAP-DRAFT');
  assert.equal(await page.getByRole('heading',{name:'Lepaskan mapping Jubelio',exact:true}).count(),0);
  assert.equal(await page.getByRole('heading',{name:'Mapping SKU Jubelio',exact:true}).count(),0);
  await page.keyboard.press('Escape');
  await page.locator('#dialog').waitFor({state:'hidden'});
  await page.unroute('**/api/products/*/external-mappings/jubelio');
  await page.getByRole('button',{name:'Jubelio '+product.sku,exact:true}).click();
  await page.getByRole('heading',{name:'Mapping SKU Jubelio',exact:true}).waitFor();

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

  // Sesudah logout, respons mapping yang tertunda tidak boleh membuka dialog di layar login.
  const delayedLogout=await holdMappingResponse();
  await page.getByRole('button',{name:'Ubah mapping',exact:true}).click();
  await delayedLogout.started;
  await page.keyboard.press('Escape');
  await page.locator('#dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await page.getByLabel('Kunci akses',{exact:true}).waitFor();
  delayedLogout.release();await delayedLogout.finished;
  await page.waitForTimeout(100);
  assert.equal(await page.locator('#dialog').getAttribute('open'),null);
  assert.equal(await page.getByRole('heading',{name:'Ubah mapping Jubelio',exact:true}).count(),0);
  await page.unroute('**/api/products/*/external-mappings/jubelio');

  await login(viewer);
  await openSidebarDestination('Master SKU');
  await page.getByRole('button',{name:'Jubelio '+product.sku,exact:true}).click();
  await page.locator('#dialog').getByText('JUB-<LUNA>-M',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Ubah mapping',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Lepaskan mapping',exact:true}).count(),0);
  await page.getByRole('button',{name:'Riwayat mapping',exact:true}).click();
  await page.getByText('CONTOH mapping master sebelum read sync',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Product mapping browser QA PASS: empty state, idempotent retry, delayed-response draft survival, post-logout guard, escaping, coverage, history, roles, mobile/200%.');
};
