const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const finished=new Date(),started=new Date(finished.getTime()-65000);
  const batch=await apiPost('/api/integrations/mekari/payroll-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    external_cursor:'payroll-<cursor-1>',reason:'CONTOH snapshot payroll worker Mekari',periods:[
      {external_payroll_id:'PAY-<AUG>',period_start:'2026-08-01',period_end:'2026-08-31',status:'approved',
       currency:'IDR',employee_count:42,gross_pay:'1000000',employee_deductions:'100000',
       employer_contributions:'150000',payment_date:null,updated_at:finished.toISOString()},
      {external_payroll_id:'PAY-<SEP>',period_start:'2026-09-01',period_end:'2026-09-30',status:'paid',
       currency:'IDR',employee_count:45,gross_pay:'2000000',employee_deductions:'200000',
       employer_contributions:'300000',payment_date:'2026-09-30',updated_at:finished.toISOString()}
    ]});
  assert.deepEqual([batch.sync_status,batch.period_count,batch.periods[0].net_pay],['succeeded',2,'1800000.00']);
  assert.equal('employee_name' in batch.periods[0],false);
  await role(viewer);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  await page.getByRole('button',{name:'Payroll Mekari',exact:true}).click();
  await page.getByRole('heading',{name:'Payroll Mekari',exact:true}).waitFor();
  await page.getByText('45 karyawan · gaji neto Rp1.800.000,00',{exact:true}).first().waitFor();
  await page.getByText('Rp2.300.000,00',{exact:true}).first().waitFor();
  await page.getByText('ID sumber PAY-<SEP> · dibayar 30 Sep 2026',{exact:true}).first().waitFor();
  assert.equal(await page.locator('sep').count(),0);
  assert.equal(await page.getByRole('button',{name:/Impor|Kirim snapshot|Catat snapshot|Setujui payroll|Bayar payroll|Buat jurnal/}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-mekari-payroll-summary-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Riwayat snapshot payroll',exact:true}).click();
  await page.getByText('Dibaca 2 · periode 2',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian snapshot payroll',exact:true}).click();
  await page.getByText('payroll-<cursor-1>',{exact:false}).waitFor();
  await page.getByText('ID sumber PAY-<SEP> · dibayar 30 Sep 2026',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Mekari payroll snapshot browser QA PASS: aggregate status and cost, no employee identity, history, escaping, viewer, mobile/200%.');
};
