const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const params=new URLSearchParams({as_of:'2026-12-13',window_days:'7',horizon_days:'14',
    query:'COST-UI',marketplace:'Tokopedia <Official>'});
  const report=await apiGet('/api/demand-forecast?'+params);
  assert.equal(report.total,1);
  assert.deepEqual([report.items[0].sku,report.items[0].previous_net_demand,
    report.items[0].recent_net_demand,report.items[0].forecast_daily_rate,
    report.items[0].forecast_quantity,report.items[0].trend],
    ['COST-UI',0,5,'0.5000','7.00','new']);

  await role(viewer);
  await page.getByRole('button',{name:'Forecast demand',exact:true}).click();
  await page.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-12-13');
  await page.getByLabel('Panjang tiap periode (hari)',{exact:true}).fill('7');
  await page.getByLabel('Horizon forecast (hari)',{exact:true}).fill('14');
  await page.getByLabel('Marketplace',{exact:true}).fill('Tokopedia <Official>');
  await page.getByLabel('Cari SKU atau produk',{exact:true}).fill('COST-UI');
  let fail=true;
  await page.route('**/api/demand-forecast?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Forecast sedang dihitung ulang'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Hitung forecast',exact:true}).click();
  await page.locator('#forecast-message').filter({hasText:'Forecast sedang dihitung ulang'}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByRole('heading',{name:'COST-UI · 7 pcs',exact:true}).waitFor();
  await page.getByText('Demand baru',{exact:true}).waitFor();
  await page.getByText('Tokopedia <Official>',{exact:false}).waitFor();
  assert.equal(await page.locator('official').count(),0);
  assert.equal(await page.getByText('Belum ada riwayat demand',{exact:true}).count(),0);
  await page.unroute('**/api/demand-forecast?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-demand-forecast-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');
  console.log('Demand forecast browser QA PASS: exact weighted forecast, filters, retry, viewer access, escaping, mobile/200%.');
};
