const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  await role(operator);
  await page.getByRole('button',{name:'Budget marketing',exact:true}).click();
  await page.getByRole('heading',{name:'Pengajuan budget kampanye.',exact:true}).waitFor();
  await page.getByRole('button',{name:'Ajukan budget',exact:true}).click();
  await page.getByLabel('Referensi pengajuan',{exact:true}).fill('MKT-UI-001');
  await page.getByLabel('Nama kampanye',{exact:true}).fill('Koleksi <Biru>&');
  await page.getByLabel('Channel marketing',{exact:true}).fill('Meta Ads');
  await page.getByLabel('Tanggal mulai',{exact:true}).fill('2026-12-01');
  await page.getByLabel('Tanggal selesai',{exact:true}).fill('2026-12-31');
  await page.getByLabel('Nominal budget (Rp)',{exact:true}).fill('7500000');
  await page.getByLabel('Objective kampanye',{exact:true}).fill('Mendapatkan pesanan koleksi akhir tahun');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH alokasi kampanye Desember');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/marketing-budget-requests',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Approval budget marketing',exact:true}).waitFor();
  await page.unroute('**/api/marketing-budget-requests');
  await page.getByText('MKT-UI-001 · Menunggu keputusan',{exact:true}).waitFor();
  await page.getByText('Koleksi <Biru>&',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Setujui budget',exact:true}).count(),0);
  const request=(await apiGet('/api/marketing-budget-requests?status=submitted'))[0];
  assert.equal(request.amount,'7500000.00');
  await page.locator('dialog').getByRole('button',{name:'Inbox approval',exact:true}).click();
  await page.locator('#approval-list').getByText('Marketing · budget kampanye',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian approval MKT-UI-001',exact:true}).click();

  await role(viewer);
  await page.getByRole('button',{name:'Budget marketing',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Ajukan budget',exact:true}).count(),0);
  await page.getByRole('button',{name:'Rincian budget MKT-UI-001',exact:true}).click();
  assert.equal(await page.locator('[data-marketing-budget-decision]').count(),0);

  await role(admin);
  await page.getByRole('button',{name:'Inbox approval',exact:true}).click();
  await page.locator('#approval-kind').selectOption('marketing_budget');
  await page.getByRole('button',{name:'Rincian approval MKT-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Setujui budget',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH plafon dan periode disetujui');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('MKT-UI-001 · Disetujui',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Daftar budget',exact:true}).click();
  await page.locator('#marketing-budget-status').selectOption('approved');
  await page.getByRole('button',{name:'Rincian budget MKT-UI-001',exact:true}).waitFor();
  await page.locator('#marketing-budgets-view').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-marketing-budgets-mobile.png')});
  console.log('Marketing budget approval browser QA PASS: submission, lost-response retry, inbox, roles, approval audit, escaping, mobile/200%.');
};
