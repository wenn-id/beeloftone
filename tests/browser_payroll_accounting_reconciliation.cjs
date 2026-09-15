const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,viewer,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const unique=Date.now(),finished=new Date(),started=new Date(finished.getTime()-5000);
  const period=(externalId,start,end,changes={})=>({external_payroll_id:externalId,
    period_start:start,period_end:end,status:'reviewing',currency:'IDR',employee_count:51,
    gross_pay:'4200000',employee_deductions:'400000',employer_contributions:'630000',
    payment_date:null,updated_at:finished.toISOString(),accounting:null,...changes});
  const accounting=(journalReference,postingDate,changes={})=>({status:'posted',
    journal_reference:journalReference,posting_date:postingDate,debit_total:'4830000',
    credit_total:'4830000',updated_at:new Date(finished.getTime()+1000).toISOString(),...changes});
  const postedId='ACC-POSTED-<'+unique+'>';
  const unbalancedId='ACC-UNBALANCED-'+unique;
  const waitingId='ACC-WAITING-'+unique;
  const journal='JV-<'+unique+'><script>';
  const importSnapshot=periods=>apiPost('/api/integrations/mekari/payroll-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    external_cursor:'accounting-'+unique,reason:'Browser QA rekonsiliasi akuntansi payroll',periods});
  const initial=await importSnapshot([
    period(postedId,'2026-12-01','2026-12-31'),
    period(unbalancedId,'2026-09-01','2026-09-30'),
    period(waitingId,'2026-08-01','2026-08-31')]);
  for(const source of initial.periods){
    const request=await apiPost('/api/integrations/mekari/payroll-periods/'+source.id+'/approval-requests',
      {reason:'Payroll disetujui untuk rekonsiliasi akuntansi'});
    await apiPost('/api/payroll-approval-requests/'+request.id+'/decisions',
      {status:'approved',expected_revision:request.revision,reason:'Biaya perusahaan sudah diperiksa'});
  }
  await importSnapshot([
    period(postedId,'2026-12-01','2026-12-31',{status:'paid',payment_date:'2026-12-31',
      accounting:accounting(journal,'2026-12-31')}),
    period(unbalancedId,'2026-09-01','2026-09-30',{status:'paid',payment_date:'2026-09-30',
      accounting:accounting('JV-UNBALANCED-'+unique,'2026-09-30',{credit_total:'4829999'})}),
    period(waitingId,'2026-08-01','2026-08-31',{status:'paid',payment_date:'2026-08-31'})]);

  await role(viewer);
  let failed=true;
  await page.route('**/api/payroll-accounting-reconciliation?*',async route=>{
    if(failed){failed=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Rekonsiliasi akuntansi sementara gagal'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  const dialog=page.locator('dialog');
  await dialog.getByRole('button',{name:'Akuntansi payroll',exact:true}).click();
  await dialog.getByText('Rekonsiliasi akuntansi sementara gagal',{exact:true}).waitFor();
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.unroute('**/api/payroll-accounting-reconciliation?*');
  const posted=dialog.locator('[data-payroll-accounting]').filter({hasText:postedId});
  await posted.getByText('Sudah diposting',{exact:true}).waitFor();
  await posted.getByText('Debit Rp4.830.000,00 · kredit Rp4.830.000,00',{exact:true}).waitFor();
  assert.equal(await posted.locator('script').count(),0);
  const unbalanced=dialog.locator('[data-payroll-accounting]').filter({hasText:unbalancedId});
  await unbalanced.getByText('Total debit dan kredit jurnal payroll tidak seimbang.',{exact:true}).waitFor();
  const waiting=dialog.locator('[data-payroll-accounting]').filter({hasText:waitingId});
  await waiting.getByText('Menunggu posting',{exact:true}).waitFor();
  assert.equal(await dialog.getByRole('button',{name:/buat jurnal|posting jurnal/i}).count(),0);

  await dialog.locator('#payroll-accounting-filter select[name="status"]').selectOption('posted');
  await dialog.getByRole('button',{name:'Terapkan filter',exact:true}).click();
  await dialog.locator('[data-payroll-accounting]').filter({hasText:postedId}).waitFor();
  assert.equal(await dialog.locator('[data-payroll-accounting]').count(),1);
  await dialog.locator('#payroll-accounting-filter input[name="q"]').fill(journal);
  await dialog.getByRole('button',{name:'Terapkan filter',exact:true}).click();
  await dialog.locator('[data-payroll-accounting]').filter({hasText:journal}).waitFor();

  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.equal(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),true,'Payroll accounting overflow at 200%');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-payroll-accounting-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});
  await role(admin);
  console.log('Payroll accounting browser QA PASS: payment-to-posting, exception, filter, retry, viewer, escaping, mobile/200%.');
};
