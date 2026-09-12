const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const beforeOrders=(await apiGet('/api/orders')).length;
  const beforeRequests=(await apiGet('/api/purchase-requests')).length;
  await role(viewer);
  await page.getByRole('button',{name:'Tanya Beeloft',exact:true}).click();
  await page.getByRole('button',{name:'Risiko stockout',exact:true}).click();
  assert.equal(await page.getByLabel('Pertanyaan bisnis',{exact:true}).inputValue(),'SKU apa yang berisiko stockout?');
  await page.getByLabel('Pertanyaan bisnis',{exact:true}).fill('Apakah stok COST-UI <aman> atau akan stockout?');
  await page.getByText('Asumsi analisis',{exact:true}).click();
  await page.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-12-13');
  await page.getByLabel('Panjang window demand (hari)',{exact:true}).fill('7');
  await page.getByLabel('Lead time replenishment (hari)',{exact:true}).fill('14');
  await page.getByLabel('Periode review stok (hari)',{exact:true}).fill('30');
  await page.getByLabel('Safety stock (hari)',{exact:true}).fill('7');
  await page.getByLabel('Kelipatan batch produksi (pcs)',{exact:true}).fill('5');
  let fail=true,requestHeaders;
  await page.route('**/api/ai/investigate',async route=>{
    requestHeaders=route.request().headers();
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Analisis sedang diperbarui'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Analisis pertanyaan',exact:true}).click();
  await page.locator('#ai-message').filter({hasText:'Analisis sedang diperbarui'}).waitFor();
  assert.equal(await page.getByLabel('Pertanyaan bisnis',{exact:true}).inputValue(),'Apakah stok COST-UI <aman> atau akan stockout?');
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByRole('heading',{name:'Jawaban',exact:true}).waitFor();
  await page.getByText('20 pcs direkomendasikan untuk produksi.',{exact:false}).waitFor();
  await page.getByText('Analisis lokal · tidak mengirim data keluar · hanya baca · fokus COST-UI',{exact:true}).waitFor();
  assert.equal(requestHeaders['idempotency-key'],undefined);
  assert.equal(await page.locator('.ai-answer aman').count(),0);
  assert.ok(await page.locator('[data-ai-recommendation="create_production_order"]').getByText('Perlu approval',{exact:true}).isVisible());
  assert.ok(await page.locator('[data-ai-recommendation="create_purchase_request"]').getByText('Belum dapat dijalankan',{exact:false}).isVisible());
  assert.equal((await apiGet('/api/orders')).length,beforeOrders);
  assert.equal((await apiGet('/api/purchase-requests')).length,beforeRequests);
  await page.unroute('**/api/ai/investigate');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-ai-investigation-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');
  await page.locator('dialog').waitFor({state:'hidden'});
  console.log('AI investigation browser QA PASS: local read-only answer, focused evidence, retry, viewer, escaping, keyboard, mobile/200%.');
};
