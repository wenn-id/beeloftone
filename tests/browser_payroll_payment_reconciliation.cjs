const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,viewer,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const unique=Date.now(),finished=new Date(),started=new Date(finished.getTime()-5000);
  const period=(externalId,start,end,changes={})=>({external_payroll_id:externalId,
    period_start:start,period_end:end,status:'reviewing',currency:'IDR',employee_count:48,
    gross_pay:'4200000',employee_deductions:'400000',employer_contributions:'630000',
    payment_date:null,updated_at:finished.toISOString(),...changes});
  const paidId='PAY-PAID-<'+unique+'>';
  const changedId='PAY-CHANGED-'+unique;
  const importSnapshot=periods=>apiPost('/api/integrations/mekari/payroll-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    external_cursor:'payment-'+unique,reason:'Browser QA rekonsiliasi pembayaran',periods});
  const initial=await importSnapshot([
    period(paidId,'2026-11-01','2026-11-30'),
    period(changedId,'2026-10-01','2026-10-31')]);
  for(const source of initial.periods){
    const request=await apiPost('/api/integrations/mekari/payroll-periods/'+source.id+'/approval-requests',
      {reason:'Payroll disetujui untuk rekonsiliasi'});
    await apiPost('/api/payroll-approval-requests/'+request.id+'/decisions',
      {status:'approved',expected_revision:request.revision,reason:'Nominal sudah diperiksa'});
  }
  await importSnapshot([
    period(paidId,'2026-11-01','2026-11-30',{status:'paid',payment_date:'2026-11-30',
      updated_at:new Date(finished.getTime()+1000).toISOString()}),
    period(changedId,'2026-10-01','2026-10-31',{gross_pay:'4500000',
      updated_at:new Date(finished.getTime()+1000).toISOString()})]);

  await role(viewer);
  let failed=true;
  await page.route('**/api/payroll-payment-reconciliation?*',async route=>{
    if(failed){failed=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Rekonsiliasi sementara gagal'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  // Milestone D: kesehatan integrasi adalah halaman, jadi tombol rekonsiliasi berada di
  // integrations-view; hasil rekonsiliasinya tetap dialog terfokus.
  await page.getByRole('button',{name:'Pembayaran payroll',exact:true}).click();
  await page.getByRole('heading',{name:'Rekonsiliasi pembayaran payroll',exact:true}).waitFor();
  const dialog=page.locator('dialog');
  await dialog.getByText('Rekonsiliasi sementara gagal',{exact:true}).waitFor();
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.unroute('**/api/payroll-payment-reconciliation?*');
  await dialog.locator('[data-payroll-payment]').getByText('Sudah dibayar',{exact:true}).first().waitFor();
  await dialog.locator('[data-payroll-payment]').getByText('Perlu perhatian',{exact:true}).first().waitFor();
  const paid=dialog.locator(`[data-payroll-payment]`).filter({hasText:paidId});
  await paid.getByText(/Mekari Dibayar · dibayar 30 Nov 2026$/).waitFor();
  assert.equal(await paid.locator('script').count(),0);
  const changed=dialog.locator(`[data-payroll-payment]`).filter({hasText:changedId});
  await changed.getByText('Nilai atau konteks payroll berubah sejak approval. Bidang berubah: gaji bruto.',{exact:true}).waitFor();

  await dialog.locator('#payroll-payment-filter select[name="status"]').selectOption('paid');
  await dialog.getByRole('button',{name:'Terapkan filter',exact:true}).click();
  await dialog.locator('[data-payroll-payment]').getByText('Sudah dibayar',{exact:true}).first().waitFor();
  assert.equal(await dialog.locator('[data-payroll-payment]').count(),1);
  await dialog.locator('#payroll-payment-filter input[name="q"]').fill('<'+unique+'>');
  await dialog.getByRole('button',{name:'Terapkan filter',exact:true}).click();
  await dialog.locator(`[data-payroll-payment]`).filter({hasText:paidId}).waitFor();

  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.equal(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),true,'Payroll payment overflow at 200%');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-payroll-payment-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});
  await role(admin);
  console.log('Payroll payment reconciliation browser QA PASS: approved-to-paid, mismatch, filter, retry, viewer, escaping, mobile/200%.');
};
