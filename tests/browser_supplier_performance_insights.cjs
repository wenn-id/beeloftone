const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const params=new URLSearchParams({as_of:'2026-12-05',window_days:'7'});
  const report=await apiGet('/api/supplier-performance-insights?'+params);
  assert.deepEqual([report.total,report.summary.attention_suppliers,report.summary.purchase_orders,
    report.summary.arrived_purchase_orders,report.summary.on_time_first_arrivals,
    report.summary.overdue_no_arrival,report.summary.overdue_incomplete_purchase_orders,
    report.summary.closed_shortfall_purchase_orders,report.summary.qc_intakes],[1,1,3,1,1,2,3,1,1]);
  const supplier=report.items[0];
  assert.deepEqual([supplier.supplier_code,supplier.status,supplier.ordered_by_unit[0].quantity,
    supplier.received_by_unit[0].quantity,supplier.quality_by_unit[0].reject_rate],
    ['SUPPLIER-QA','attention','9.250','1.000','66.67']);
  assert.deepEqual(supplier.flags,
    ['overdue_no_arrival','overdue_incomplete','closed_shortfall','quality_reject']);

  await role(viewer);
  await page.getByRole('button',{name:'Kinerja supplier',exact:true}).click();
  const analytics=page.locator('#analytics-view');
  await analytics.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-12-05');
  await analytics.getByLabel('Periode jatuh tempo PO (hari)',{exact:true}).fill('7');
  let fail=true;
  await page.route('**/api/supplier-performance-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Kinerja supplier sedang dihitung ulang'})});}
    else await route.continue();
  });
  await analytics.getByRole('button',{name:'Tampilkan kinerja',exact:true}).click();
  await page.locator('#supplier-performance-message').filter({hasText:'Kinerja supplier sedang dihitung ulang'}).waitFor();
  await analytics.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const item=page.locator('[data-supplier-performance]');
  await item.getByRole('heading',{name:'SUPPLIER-QA · Toko <kain> & Kancing',exact:true}).waitFor();
  await item.getByText('Perlu perhatian',{exact:true}).waitFor();
  assert.ok((await item.innerText()).includes('PO terlambat tanpa kedatangan'));
  await item.getByText('Usable 33.33% · reject 66.67%',{exact:true}).waitFor();
  await page.unroute('**/api/supplier-performance-insights?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await item.scrollIntoViewIfNeeded();
  await analytics.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-supplier-performance-mobile.png')});
  await page.locator('#supplier-performance-form select[name="status"]').selectOption('healthy');
  await analytics.getByRole('button',{name:'Tampilkan kinerja',exact:true}).click();
  await analytics.getByText('Tidak ada supplier yang cocok dengan status dan filter periode ini.',{exact:true}).waitFor();
  await page.locator('#supplier-performance-form select[name="status"]').selectOption('attention');
  await analytics.getByRole('button',{name:'Tampilkan kinerja',exact:true}).click();
  const po=item.locator('.material-event').filter({has:page.getByText('PO-RETUR · Diterima sebagian',{exact:true})});
  await po.getByRole('button',{name:'Buka PO',exact:true}).click();
  await page.getByText('PO-RETUR · Ditutup',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Supplier performance browser QA PASS: delivery and QC signals, retry, viewer, empty state, drill-down, mobile/200%.');
};
