const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const unique=Date.now();
  const payroll=(externalId,gross='3500000',updated=new Date().toISOString())=>({
    external_payroll_id:externalId,period_start:'2026-10-01',period_end:'2026-10-31',status:'reviewing',
    currency:'IDR',employee_count:47,gross_pay:gross,employee_deductions:'350000',
    employer_contributions:'525000',payment_date:null,updated_at:updated
  });
  const snapshot=async period=>{
    const finished=new Date(),started=new Date(finished.getTime()-5000);
    return apiPost('/api/integrations/mekari/payroll-snapshots',{
      started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
      external_cursor:'approval-'+unique,reason:'Browser QA approval payroll',periods:[period]
    });
  };

  const external='PAY-REVIEW-<'+unique+'>';
  const source=(await snapshot(payroll(external))).periods[0];
  await role(operator);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  let dialog=page.locator('dialog');
  await dialog.getByRole('button',{name:'Payroll Mekari',exact:true}).click();
  const card=dialog.locator(`[data-payroll-period="${source.id}"]`).first();
  await card.getByText('Mekari · Ditinjau',{exact:true}).waitFor();
  assert.equal(await card.locator('script').count(),0);
  await card.getByRole('button',{name:'Ajukan approval',exact:true}).click();
  await dialog.getByLabel('Alasan / catatan',{exact:true}).fill('Payroll Oktober <siap> diputuskan');
  let lost=true;
  await page.route('**/api/integrations/mekari/payroll-periods/*/approval-requests',async route=>{
    if(lost&&route.request().method()==='POST'){lost=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await dialog.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.unroute('**/api/integrations/mekari/payroll-periods/*/approval-requests');
  await dialog.getByRole('heading',{name:'1 Okt 2026–31 Okt 2026',exact:true}).waitFor();
  await dialog.getByText('Menunggu keputusan',{exact:true}).first().waitFor();
  const request=(await apiGet('/api/payroll-approval-requests')).find(row=>row.source.external_payroll_id===external);
  assert.ok(request);assert.equal(request.stale,false);
  assert.equal((await apiGet('/api/payroll-approval-requests')).filter(row=>row.source.external_payroll_id===external).length,1);

  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.equal(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),true,'Payroll approval overflow at 200%');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-payroll-approval-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});

  await role(viewer);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();dialog=page.locator('dialog');
  await dialog.getByRole('button',{name:'Payroll Mekari',exact:true}).click();
  assert.equal(await dialog.getByRole('button',{name:/Ajukan.*approval/}).count(),0);
  await dialog.locator(`[data-payroll-period="${source.id}"]`).first().getByRole('button',{name:'Rincian approval',exact:true}).click();
  assert.equal(await dialog.getByRole('button',{name:/Setujui payroll|Tolak payroll|Batalkan pengajuan/}).count(),0);

  await role(admin);
  await page.locator('#approvals').click();dialog=page.locator('dialog');
  await dialog.locator('#approval-kind').selectOption('payroll_batch');
  await dialog.getByRole('button',{name:new RegExp('Rincian approval '+request.reference)}).click();
  await dialog.getByRole('button',{name:'Setujui payroll',exact:true}).click();
  await dialog.getByLabel('Alasan / catatan',{exact:true}).fill('Nominal dan jumlah karyawan sudah diperiksa');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByText(request.reference+' · Disetujui',{exact:true}).waitFor();
  const approved=await apiGet('/api/payroll-approval-requests/'+request.id);
  assert.equal(approved.status,'approved');assert.equal(approved.source.status,'reviewing');

  const staleExternal='PAY-STALE-'+unique;
  const first=(await snapshot(payroll(staleExternal))).periods[0];
  await role(operator);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();dialog=page.locator('dialog');
  await dialog.getByRole('button',{name:'Payroll Mekari',exact:true}).click();
  await dialog.locator(`[data-payroll-period="${first.id}"]`).first().getByRole('button',{name:'Ajukan approval',exact:true}).click();
  await dialog.getByLabel('Alasan / catatan',{exact:true}).fill('Menunggu keputusan sebelum perubahan');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByText('Menunggu keputusan',{exact:true}).first().waitFor();
  const staleRequest=(await apiGet('/api/payroll-approval-requests')).find(row=>row.source.external_payroll_id===staleExternal);
  assert.ok(staleRequest);
  await snapshot(payroll(staleExternal,'3750000',new Date(Date.now()+1000).toISOString()));

  await role(admin);
  await page.locator('#approvals').click();dialog=page.locator('dialog');
  await dialog.locator('#approval-kind').selectOption('payroll_batch');
  await dialog.getByRole('button',{name:new RegExp('Rincian approval '+staleRequest.reference)}).click();
  await dialog.getByText('Snapshot payroll sumber sudah berubah atau tidak lagi tersedia. Permintaan ini tidak dapat disetujui.',{exact:true}).waitFor();
  assert.equal(await dialog.getByRole('button',{name:'Setujui payroll',exact:true}).count(),0);
  await dialog.getByRole('button',{name:'Tolak payroll',exact:true}).click();
  await dialog.getByLabel('Alasan / catatan',{exact:true}).fill('Gunakan snapshot payroll terbaru');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByText(staleRequest.reference+' · Ditolak',{exact:true}).waitFor();
  console.log('Payroll approval browser QA PASS: reviewing source, exact retry, unified inbox, admin approval, stale guard, operator/viewer roles, escaping, mobile/200%.');
};
