const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const finished=new Date(),started=new Date(finished.getTime()-65000);
  const batch=await apiPost('/api/integrations/mekari/receivable-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    as_of:'2026-09-13',external_cursor:'receivables-<cursor-1>',reason:'CONTOH snapshot piutang worker Mekari',
    receivables:[
      {external_receivable_id:'receivable-overdue-ui',reference:'INV-<OVERDUE>',external_customer_id:'customer-ui-1',
       customer_name:'Customer <Wholesale>',invoice_date:'2026-08-15',due_date:'2026-09-10',status:'open',
       currency:'IDR',original_amount:'1000000',received_amount:'0',updated_at:finished.toISOString()},
      {external_receivable_id:'receivable-soon-ui',reference:'INV-<SOON>',external_customer_id:'customer-ui-2',
       customer_name:'Marketplace & Reseller',invoice_date:'2026-09-01',due_date:'2026-09-17',status:'partially_paid',
       currency:'IDR',original_amount:'500000',received_amount:'200000',updated_at:finished.toISOString()}
    ]});
  assert.deepEqual([batch.sync_status,batch.receivable_count,batch.receivables[0].overdue],['succeeded',2,true]);
  await role(viewer);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  await page.getByRole('button',{name:'Piutang Mekari',exact:true}).click();
  await page.getByRole('heading',{name:'Piutang Mekari',exact:true}).waitFor();
  await page.getByText('1 · Rp1.000.000,00',{exact:true}).first().waitFor();
  await page.getByText('1 · Rp300.000,00',{exact:true}).first().waitFor();
  await page.getByText('INV-<OVERDUE> · Customer <Wholesale>',{exact:true}).waitFor();
  await page.getByText('INV-<SOON> · Marketplace & Reseller',{exact:true}).waitFor();
  assert.equal(await page.locator('overdue').count(),0);
  assert.equal(await page.getByRole('button',{name:/Impor|Kirim snapshot|Catat snapshot|Tagih pelanggan|Buat jurnal/}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-mekari-receivables-summary-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Riwayat snapshot piutang',exact:true}).click();
  await page.getByText('Dibaca 2 · invoice 2',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian snapshot piutang',exact:true}).click();
  await page.getByText('receivables-<cursor-1>',{exact:false}).waitFor();
  await page.getByText('INV-<OVERDUE> · Customer <Wholesale>',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Mekari receivable snapshot browser QA PASS: overdue and due-soon summary, history, escaping, viewer, mobile/200%.');
};
