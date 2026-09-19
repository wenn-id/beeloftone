const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const params=new URLSearchParams({as_of:'2027-01-01',inactivity_days:'30',query:'FG-M'});
  const report=await apiGet('/api/dead-stock-insights?'+params);
  assert.deepEqual([report.total,report.summary.dead_stock_candidates,
    report.summary.dead_stock_quantity],[1,1,6]);
  assert.deepEqual([report.items[0].sku,report.items[0].status,report.items[0].available_quantity,
    report.items[0].oldest_stock_age_days,report.items[0].last_net_sale_date],
    ['FG-M','dead_stock_candidate',6,105,null]);

  await role(viewer);
  await page.getByRole('button',{name:'Dead stock',exact:true}).click();
  await page.getByLabel('Data demand sampai tanggal',{exact:true}).fill('2027-01-01');
  await page.getByLabel('Ambang tanpa demand (hari)',{exact:true}).fill('30');
  await page.getByLabel('Cari SKU atau produk',{exact:true}).fill('FG-M');
  let fail=true;
  await page.route('**/api/dead-stock-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Analisis dead stock sedang dihitung ulang'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Tampilkan analisis',exact:true}).click();
  await page.locator('#dead-stock-message').filter({hasText:'Analisis dead stock sedang dihitung ulang'}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const item=page.locator('[data-dead-stock-sku="FG-M"]');
  await item.getByRole('heading',{name:'FG-M · 6 pcs tersedia',exact:true}).waitFor();
  await item.getByText('Kandidat dead stock',{exact:true}).waitFor();
  assert.ok((await item.innerText()).includes('105 hari'));
  assert.ok((await item.innerText()).includes('Belum ada penjualan neto aktif sampai tanggal laporan.'));
  await page.unroute('**/api/dead-stock-insights?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('#analytics-view').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-dead-stock-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.locator('#dead-stock-form select[name="status"]').selectOption('moving');
  await page.getByRole('button',{name:'Tampilkan analisis',exact:true}).click();
  await page.getByText('Tidak ada SKU yang cocok dengan status dan filter ini.',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Dead stock browser QA PASS: aged available stock, corrected sales, retry, viewer, empty state, mobile/200%.');
};
