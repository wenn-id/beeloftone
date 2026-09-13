const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const finished=new Date(),started=new Date(finished.getTime()-65000);
  const batch=await apiPost('/api/integrations/mekari/payable-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    as_of:'2026-09-13',external_cursor:'payables-<cursor-1>',reason:'CONTOH snapshot utang worker Mekari',
    payables:[
      {external_payable_id:'payable-overdue-ui',reference:'INV-<OVERDUE>',external_supplier_id:'supplier-ui-1',
       supplier_name:'PT Kain <Utama>',invoice_date:'2026-08-15',due_date:'2026-09-10',status:'open',
       currency:'IDR',original_amount:'1000000',paid_amount:'0',updated_at:finished.toISOString()},
      {external_payable_id:'payable-soon-ui',reference:'INV-<SOON>',external_supplier_id:'supplier-ui-2',
       supplier_name:'CV Zipper & Kancing',invoice_date:'2026-09-01',due_date:'2026-09-17',status:'partially_paid',
       currency:'IDR',original_amount:'500000',paid_amount:'200000',updated_at:finished.toISOString()}
    ]});
  assert.deepEqual([batch.sync_status,batch.payable_count,batch.payables[0].overdue],['succeeded',2,true]);
  await role(viewer);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  await page.getByRole('button',{name:'Utang Mekari',exact:true}).click();
  await page.getByRole('heading',{name:'Utang Mekari',exact:true}).waitFor();
  await page.getByText('1 · Rp1.000.000,00',{exact:true}).first().waitFor();
  await page.getByText('1 · Rp300.000,00',{exact:true}).first().waitFor();
  await page.getByText('INV-<OVERDUE> · PT Kain <Utama>',{exact:true}).waitFor();
  await page.getByText('INV-<SOON> · CV Zipper & Kancing',{exact:true}).waitFor();
  assert.equal(await page.locator('overdue').count(),0);
  assert.equal(await page.getByRole('button',{name:/Impor|Kirim snapshot|Catat snapshot|Bayar invoice|Buat jurnal/}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-mekari-payables-summary-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Riwayat snapshot utang',exact:true}).click();
  await page.getByText('Dibaca 2 · invoice 2',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian snapshot utang',exact:true}).click();
  await page.getByText('payables-<cursor-1>',{exact:false}).waitFor();
  await page.getByText('INV-<OVERDUE> · PT Kain <Utama>',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Mekari payable snapshot browser QA PASS: overdue and due-soon summary, history, escaping, viewer, mobile/200%.');
};
