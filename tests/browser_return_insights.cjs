const assert=require('node:assert/strict');
const path=require('node:path');

// Milestone C: Analisis retur sebagai tujuan halaman di host analitik, bukan dialog
// utama. Modul yang berjalan sebelum ini menanam retur nyata, jadi empty state
// dibuktikan dengan filter yang tidak pernah cocok, bukan dengan mengasumsikan
// dataset demo kosong. Kontrak halaman: host aktif, aria-current benar, dialog
// global tidak terbuka, error+coba lagi, empty state yang jelas, akses viewer,
// mobile 390px dan 320px/200%.
module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const noMatch='RETUR-TIDAK-ADA-XYZ';
  const emptyText='Tidak ada shipment yang cocok dengan filter pada periode ini.';
  const report=await apiGet('/api/return-insights?'+new URLSearchParams({as_of:'2026-12-13',window_days:'365',query:noMatch}));
  assert.equal(report.total,0,'filter yang tidak cocok harus menjawab kosong terlepas dari data modul sebelumnya');

  await role(viewer);
  await page.getByRole('button',{name:'Analisis retur',exact:true}).click();
  const analytics=page.locator('#analytics-view');
  await page.getByRole('heading',{name:'Analisis retur per SKU',exact:true}).waitFor();
  assert.equal(await page.locator('#return-insights').getAttribute('aria-current'),'page');
  assert.equal(await page.locator('#dialog').getAttribute('open'),null,'return insights must not open the global dialog');
  await analytics.getByLabel('Cari SKU atau produk',{exact:true}).fill(noMatch);
  let fail=true;
  await page.route('**/api/return-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Retur sedang dihitung ulang'})});}
    else await route.continue();
  });
  await analytics.getByRole('button',{name:'Tampilkan analisis',exact:true}).click();
  await page.locator('#return-insights-message').filter({hasText:'Retur sedang dihitung ulang'}).waitFor();
  await analytics.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await analytics.getByText(emptyText,{exact:true}).waitFor();
  assert.equal(await page.locator('[data-return-insight-sku]').count(),0);
  await page.unroute('**/api/return-insights?*');

  // Filter yang tidak pernah cocok mempertahankan empty state, bukan menahan hasil lama.
  await analytics.getByLabel('Marketplace',{exact:true}).fill('MARKETPLACE-TIDAK-ADA-XYZ');
  await analytics.getByRole('button',{name:'Tampilkan analisis',exact:true}).click();
  await analytics.getByText(emptyText,{exact:true}).waitFor();
  assert.equal(await page.locator('[data-return-insight-sku]').count(),0);

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await analytics.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-return-insights-mobile.png')});
  await page.setViewportSize({width:320,height:900});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),
    'no document overflow at 320px / 200% text');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');
  console.log('Return insights browser QA PASS: page host, retry, viewer, empty state, mobile/200%.');
};
