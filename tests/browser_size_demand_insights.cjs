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

  await post('/api/products',{sku:'FG-L',name:'CONTOH barang jadi',color:'Sage',size:'L'},'size-insight-product');
  const params=new URLSearchParams({as_of:'2026-10-01',window_days:'7',lookahead_days:'30',
    query:'FG-L',marketplace:'Shopee'});
  const report=await apiGet('/api/size-demand-insights?'+params);
  assert.deepEqual([report.total,report.summary.size_variants,report.summary.families_within_lookahead],
    [1,2,1]);
  assert.deepEqual([report.items[0].first_stockout_sizes,report.items[0].first_stockout_date],
    [['M'],'2026-10-31']);
  const medium=report.items[0].sizes.find(row=>row.sku==='FG-M');
  assert.deepEqual([medium.available_quantity,medium.forecast_daily_rate,medium.days_of_cover],
    [6,'0.2000','30.00']);

  await role(viewer);
  await page.getByRole('button',{name:'Analisis ukuran',exact:true}).click();
  await page.getByLabel('Data demand sampai tanggal',{exact:true}).fill('2026-10-01');
  await page.getByLabel('Panjang tiap periode (hari)',{exact:true}).fill('7');
  await page.getByLabel('Horizon risiko (hari)',{exact:true}).fill('30');
  await page.getByLabel('Marketplace demand',{exact:true}).fill('Shopee');
  await page.getByLabel('Cari keluarga produk atau SKU',{exact:true}).fill('FG-L');
  let fail=true;
  await page.route('**/api/size-demand-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Analisis ukuran sedang dihitung ulang'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Tampilkan analisis',exact:true}).click();
  await page.locator('#size-demand-message').filter({hasText:'Analisis ukuran sedang dihitung ulang'}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const family=page.locator('[data-size-demand-family="CONTOH barang jadi"]');
  await family.getByRole('heading',{name:'CONTOH barang jadi · Sage',exact:true}).waitFor();
  await family.getByText('Risiko habis lebih dulu: M',{exact:false}).waitFor();
  assert.ok((await family.locator('[data-size-demand-sku="FG-M"]').innerText()).includes('30 hari'));
  assert.ok((await family.locator('[data-size-demand-sku="FG-L"]').innerText()).includes('days of cover belum tersedia'));
  await page.unroute('**/api/size-demand-insights?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('#analytics-view').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-size-demand-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.getByLabel('Cari keluarga produk atau SKU',{exact:true}).fill('KELUARGA-TIDAK-ADA');
  await page.getByRole('button',{name:'Tampilkan analisis',exact:true}).click();
  await page.getByText('Belum ada keluarga produk dengan minimal dua ukuran yang cocok dengan filter.',
    {exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Size demand browser QA PASS: family search, current stockout risk, retry, viewer, empty state, mobile/200%.');
};
