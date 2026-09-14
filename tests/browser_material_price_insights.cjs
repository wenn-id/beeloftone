const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const params=new URLSearchParams({window_days:'730',status:'all',query:'KAIN-QC'});
  const report=await apiGet('/api/material-price-insights?'+params);
  assert.deepEqual([report.total,report.summary.series,report.summary.observations],[1,1,1]);
  assert.deepEqual([report.items[0].material_code,report.items[0].supplier_code,
    report.items[0].status,report.items[0].latest_unit_price],
    ['KAIN-QC','SUPPLIER-QA','single_observation','10.00']);

  await role(viewer);
  await page.getByRole('button',{name:'Harga bahan',exact:true}).click();
  const dialog=page.locator('dialog');
  await dialog.getByLabel('Periode pencatatan PO (hari)',{exact:true}).fill('730');
  await page.locator('#material-price-form select[name="status"]').selectOption('all');
  await dialog.getByLabel('Cari bahan, supplier, atau PO',{exact:true}).fill('KAIN-QC');
  let fail=true;
  await page.route('**/api/material-price-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Riwayat harga sedang dihitung ulang'})});}
    else await route.continue();
  });
  await dialog.getByRole('button',{name:'Tampilkan harga',exact:true}).click();
  await page.locator('#material-price-message').filter({hasText:'Riwayat harga sedang dihitung ulang'}).waitFor();
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const item=page.locator('[data-material-price]');
  await item.getByRole('heading',{name:'KAIN-QC · Kain pemeriksaan',exact:true}).waitFor();
  await item.getByText('SUPPLIER-QA · Toko <kain> & Kancing',{exact:true}).waitFor();
  await item.getByText('Baru satu harga',{exact:true}).waitFor();
  assert.ok((await item.innerText()).includes('Rp10,00 / m'));
  await page.unroute('**/api/material-price-insights?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await item.scrollIntoViewIfNeeded();
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-material-price-mobile.png')});
  await page.locator('#material-price-form select[name="status"]').selectOption('increased');
  await dialog.getByRole('button',{name:'Tampilkan harga',exact:true}).click();
  await dialog.getByText('Tidak ada pergerakan harga yang cocok dengan status dan filter periode ini.',
    {exact:true}).waitFor();
  await page.locator('#material-price-form select[name="status"]').selectOption('all');
  await dialog.getByRole('button',{name:'Tampilkan harga',exact:true}).click();
  await item.getByRole('button',{name:'Buka PO',exact:true}).click();
  await page.getByText('PO-QC · Aktif',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Material price browser QA PASS: viewer, retry, escaping, single price, empty state, PO drill-down, mobile/200%.');
};
