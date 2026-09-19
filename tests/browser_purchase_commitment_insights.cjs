const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const params=new URLSearchParams({status:'all',query:'PO-QC'});
  const report=await apiGet('/api/purchase-commitment-insights?'+params);
  assert.deepEqual([report.total,report.summary.open_purchase_orders,
    report.summary.open_commitment_value],[1,1,'31.25']);
  assert.deepEqual([report.items[0].purchase_order_reference,report.items[0].supplier_code,
    report.items[0].status,report.items[0].open_commitment_value],
    ['PO-QC','SUPPLIER-QA','scheduled','31.25']);

  await role(viewer);
  await page.getByRole('button',{name:'Komitmen PO',exact:true}).click();
  const analytics=page.locator('#analytics-view');
  await page.locator('#purchase-commitment-form select[name="status"]').selectOption('all');
  await analytics.getByLabel('Cari PO, PR, supplier, atau bahan',{exact:true}).fill('PO-QC');
  let fail=true;
  await page.route('**/api/purchase-commitment-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Komitmen pembelian sedang dihitung ulang'})});}
    else await route.continue();
  });
  await analytics.getByRole('button',{name:'Tampilkan komitmen',exact:true}).click();
  await page.locator('#purchase-commitment-message')
    .filter({hasText:'Komitmen pembelian sedang dihitung ulang'}).waitFor();
  await analytics.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const item=page.locator('[data-purchase-commitment]');
  await item.getByRole('heading',{name:'PO-QC · SUPPLIER-QA',exact:true}).waitFor();
  await item.getByText('Toko <kain> & Kancing',{exact:true}).waitFor();
  await item.getByText('Terjadwal',{exact:true}).waitFor();
  assert.ok((await item.innerText()).includes('Komitmen terbuka\nRp31,25'));
  assert.ok((await item.innerText()).includes('KAIN-QC · Kain pemeriksaan'));
  await page.unroute('**/api/purchase-commitment-insights?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await item.scrollIntoViewIfNeeded();
  await analytics.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-purchase-commitment-mobile.png')});
  await page.locator('#purchase-commitment-form select[name="status"]').selectOption('overdue');
  await analytics.getByRole('button',{name:'Tampilkan komitmen',exact:true}).click();
  await analytics.getByText('Tidak ada komitmen PO yang cocok dengan status dan filter ini.',
    {exact:true}).waitFor();
  await page.locator('#purchase-commitment-form select[name="status"]').selectOption('all');
  await analytics.getByRole('button',{name:'Tampilkan komitmen',exact:true}).click();
  await item.getByRole('button',{name:'Buka PO',exact:true}).click();
  await page.getByText('PO-QC · Aktif',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Purchase commitment browser QA PASS: viewer, retry, open value, escaping, empty state, PO drill-down, mobile/200%.');
};
