const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,viewer,apiGet,work})=>{
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(admin);
  const orders=await apiGet('/api/orders'), order=orders.find(o=>o.reference==='DEMO-PROD-001');
  const product=order.lines[0], material=(await apiGet('/api/materials')).find(m=>m.code==='KAIN-UI');
  await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
  await page.getByRole('button',{name:'Kebutuhan bahan',exact:true}).click();
  await page.getByText(/Perhitungan belum lengkap/).waitFor();
  await page.getByRole('button',{name:'Lihat BOM',exact:true}).click();
  await page.getByText(/BOM belum diisi. Kebutuhan/).waitFor();
  await page.getByRole('button',{name:'Isi BOM',exact:true}).click();
  await page.getByLabel('Bahan BOM',{exact:true}).selectOption(material.id);
  await page.getByLabel('Jumlah per pcs',{exact:true}).fill('0.05');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH - standar kebutuhan bahan');
  let drop=true;
  await page.route('**/api/products/*/bom',async route=>{
    if(route.request().method()==='POST' && drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('button',{name:'Ubah BOM',exact:true}).waitFor();
  await page.unroute('**/api/products/*/bom');
  assert.equal((await apiGet('/api/products/'+product.product_id+'/bom-history')).length,1);
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Kebutuhan bahan',exact:true}).click();
  await page.locator('#requirements-list').getByText('25 m',{exact:true}).first().waitFor();
  await page.locator('#requirements-list').getByText('14,875 m',{exact:true}).waitFor();
  const artifacts=process.env.BEELOFT_QA_SCREENSHOTS || work;
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:path.join(artifacts,'beeloft-bom-requirements.png'),fullPage:true});
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),'Requirements dialog overflow '+width);
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),'Requirements 200% overflow');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.getByRole('button',{name:'Lihat BOM',exact:true}).click();
  await page.getByRole('button',{name:'Ubah BOM',exact:true}).click();
  await page.getByLabel('Jumlah per pcs',{exact:true}).fill('0.07');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('Draft tab pertama');
  const current=await apiGet('/api/products/'+product.product_id+'/bom');
  const response=await fetch(process.env.BEELOFT_QA_BASE+'/api/products/'+product.product_id+'/bom',{
    method:'POST',headers:{'X-API-Key':admin,'Idempotency-Key':crypto.randomUUID(),'Content-Type':'application/json'},
    body:JSON.stringify({expected_revision:current.revision,components:[{material_id:material.id,quantity:'0.06'}],reason:'Perubahan dari tab kedua'})});
  assert.equal(response.status,201);
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText(/BOM sudah berubah/).waitFor();
  assert.equal((await apiGet('/api/products/'+product.product_id+'/bom')).components[0].quantity,'0.060');
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Master SKU',exact:true}).click();
  await page.getByRole('button',{name:'BOM '+product.sku,exact:true}).click();
  await page.getByRole('button',{name:'Riwayat BOM',exact:true}).click();
  await page.getByText('Perubahan dari tab kedua',{exact:true}).waitFor();
  await page.getByText('CONTOH - standar kebutuhan bahan',{exact:true}).waitFor();
  await page.screenshot({path:path.join(artifacts,'beeloft-bom-history-mobile.png'),fullPage:true});
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(viewer);
  await page.getByRole('button',{name:'Master SKU',exact:true}).click();
  await page.getByRole('button',{name:'BOM '+product.sku,exact:true}).click();
  await page.getByText('Perubahan dari tab kedua',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Ubah BOM',exact:true}).count(),0);
  await page.keyboard.press('Escape');
  console.log('BOM browser QA PASS: missing BOM, create, lost-response retry, exact requirements, stale revision, history, viewer, mobile/200%.');
};
