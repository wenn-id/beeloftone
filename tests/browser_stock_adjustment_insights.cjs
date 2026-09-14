const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const params=new URLSearchParams({as_of:'2026-10-05',window_days:'7',quantity_threshold:'5',
    percentage_threshold:'20',repeat_threshold:'3',query:'FG-M'});
  const report=await apiGet('/api/stock-adjustment-insights?'+params);
  assert.deepEqual([report.total,report.summary.flagged_adjustments,report.summary.review_adjustments,
    report.summary.corrected_adjustments,report.summary.flagged_absolute_quantity],[1,1,1,1,3]);
  assert.deepEqual([report.items[0].reference,report.items[0].classification,
    report.items[0].record_status,report.items[0].source,report.items[0].receipt_share_percent],
    ['ADJ-UI-001','review','corrected','manual','15.00']);
  assert.deepEqual(report.items[0].flags,['corrected_record']);

  await role(viewer);
  await page.getByRole('button',{name:'Audit adjustment',exact:true}).click();
  const dialog=page.locator('dialog');
  await dialog.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-10-05');
  await dialog.getByLabel('Panjang periode (hari)',{exact:true}).fill('7');
  await dialog.getByLabel('Cari adjustment atau SKU',{exact:true}).fill('FG-M');
  let fail=true;
  await page.route('**/api/stock-adjustment-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Audit adjustment sedang dihitung ulang'})});}
    else await route.continue();
  });
  await dialog.getByRole('button',{name:'Tampilkan audit',exact:true}).click();
  await page.locator('#stock-adjustment-insights-message').filter({hasText:'Audit adjustment sedang dihitung ulang'}).waitFor();
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const item=page.locator('[data-stock-adjustment-insight]');
  await item.getByRole('heading',{name:'ADJ-UI-001 · +3 pcs',exact:true}).waitFor();
  await item.getByText('Perlu tinjauan',{exact:true}).waitFor();
  assert.ok((await item.innerText()).includes('Catatan sudah dikoreksi'));
  assert.ok((await item.innerText()).includes('Rak Opname <UI>'));
  await page.unroute('**/api/stock-adjustment-insights?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await item.scrollIntoViewIfNeeded();
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-stock-adjustment-insights-mobile.png')});
  await page.locator('#stock-adjustment-insights-form select[name="classification"]').selectOption('normal');
  await dialog.getByRole('button',{name:'Tampilkan audit',exact:true}).click();
  await dialog.getByText('Tidak ada adjustment yang cocok dengan klasifikasi dan filter ini.',{exact:true}).waitFor();
  await page.locator('#stock-adjustment-insights-form select[name="classification"]').selectOption('flagged');
  await dialog.getByRole('button',{name:'Tampilkan audit',exact:true}).click();
  await item.getByRole('button',{name:'Buka adjustment',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian adjustment',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Koreksi adjustment',exact:true}).count(),0);
  await page.keyboard.press('Escape');
  console.log('Stock adjustment insights browser QA PASS: transparent flags, retry, viewer, empty state, drill-down, mobile/200%.');
};
