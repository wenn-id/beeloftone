const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,openSidebarDestination,admin,operator,viewer,apiPost,apiGet,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const unique=Date.now();
  const employee=await apiPost('/api/workforce/employees',{
    code:'PPL-APP-'+unique,name:'Nadia <People>',department:'People',reason:'Browser QA approval People'
  });
  const day=offset=>{const value=new Date();value.setDate(value.getDate()+offset);return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Jakarta'}).format(value);};

  await role(operator);
  await openSidebarDestination('People');
  let dialog=page.locator('dialog');
  let fail=true;
  await page.route('**/api/workforce/requests*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Permintaan People sedang dimuat ulang'})});}
    else await route.continue();
  });
  await dialog.getByRole('button',{name:'Permintaan cuti / lembur',exact:true}).click();
  await dialog.locator('#workforce-request-message').filter({hasText:'Permintaan People sedang dimuat ulang'}).waitFor();
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await dialog.getByText('Belum ada permintaan yang sesuai filter.',{exact:true}).waitFor();
  await page.unroute('**/api/workforce/requests*');

  await dialog.getByRole('button',{name:'Ajukan permintaan',exact:true}).click();
  await dialog.locator('select[name="employee_id"]').selectOption(employee.id);
  await dialog.getByLabel('Tanggal mulai').fill(day(2));
  await dialog.getByLabel('Tanggal selesai').fill(day(4));
  await dialog.getByLabel('Alasan permintaan').fill('Cuti keluarga <terencana>');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByRole('heading',{name:'Nadia <People>'}).waitFor();
  await dialog.getByText('Menunggu keputusan',{exact:true}).first().waitFor();
  assert.equal(await dialog.locator('script').count(),0);
  const leave=(await apiGet('/api/workforce/requests?kind=leave&q=Nadia')).items[0];
  assert.equal(leave.days,3);
  assert.equal((await apiGet('/api/workforce/attendance?employee_id='+employee.id)).total,0);

  await dialog.getByRole('button',{name:'Semua permintaan',exact:true}).click();
  await dialog.locator(`[data-workforce-request="${leave.id}"]`).waitFor();
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),true,'People approvals overflow');
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.equal(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),true,'People approvals overflow at 200%');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-people-approvals-mobile.png')});

  await role(viewer);
  await openSidebarDestination('People');dialog=page.locator('dialog');
  await dialog.getByRole('button',{name:'Permintaan cuti / lembur',exact:true}).click();
  assert.equal(await dialog.getByRole('button',{name:'Ajukan permintaan',exact:true}).count(),0);
  await dialog.locator(`[data-workforce-request="${leave.id}"]`).getByRole('button',{name:'Rincian',exact:true}).click();
  assert.equal(await dialog.getByRole('button',{name:/Setujui|Tolak|Batalkan/}).count(),0);

  await role(admin);
  await page.locator('#approvals').click();dialog=page.locator('dialog');
  await dialog.locator('#approval-kind').selectOption('workforce_leave');
  await dialog.getByRole('button',{name:new RegExp('Rincian approval '+leave.reference)}).click();
  await dialog.getByRole('button',{name:'Setujui',exact:true}).click();
  await dialog.getByLabel('Alasan / catatan',{exact:true}).fill('Jadwal tim sudah diperiksa');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByText(leave.reference+' · Disetujui',{exact:true}).waitFor();
  assert.equal((await apiGet('/api/workforce/requests/'+leave.id)).status,'approved');
  assert.equal((await apiGet('/api/workforce/attendance?employee_id='+employee.id)).total,0);

  await role(operator);
  await openSidebarDestination('People');dialog=page.locator('dialog');
  await dialog.getByRole('button',{name:'Permintaan cuti / lembur',exact:true}).click();
  await dialog.getByRole('button',{name:'Ajukan permintaan',exact:true}).click();
  await dialog.locator('select[name="employee_id"]').selectOption(employee.id);
  await dialog.getByLabel('Jenis').selectOption('overtime');
  await dialog.getByLabel('Tanggal mulai').fill(day(6));
  assert.equal(await dialog.getByLabel('Tanggal selesai').isEditable(),false);
  assert.equal(await dialog.getByLabel('Tanggal selesai').inputValue(),day(6));
  await dialog.getByLabel('Lembur (menit)').fill('75');
  await dialog.getByLabel('Alasan permintaan').fill('Penyelesaian packing');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByRole('button',{name:'Batalkan',exact:true}).click();
  await dialog.getByLabel('Alasan / catatan',{exact:true}).fill('Jadwal packing berubah');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByText('Dibatalkan',{exact:true}).first().waitFor();
  console.log('People approvals browser QA PASS: leave/overtime requests, unified inbox, admin decision, operator cancellation, viewer, retry, escaping, mobile/200%.');
};
