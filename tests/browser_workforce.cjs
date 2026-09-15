const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiPost,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  await page.setViewportSize({width:1280,height:900});
  if(await page.evaluate(()=>document.documentElement.dataset.theme==='dark'))await page.getByRole('button',{name:'Mode terang',exact:true}).click();
  const unique=Date.now(),today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Jakarta'}).format(new Date());
  const employee=await apiPost('/api/workforce/employees',{
    code:'PPL-'+unique,name:'Ayu <Produksi>',department:'Produksi',reason:'Browser QA People'
  });

  await role(admin);
  let fail=true;
  await page.route('**/api/workforce/attendance?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Roster sedang dimuat ulang'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'People',exact:true}).click();
  let dialog=page.locator('dialog');
  await dialog.locator('#workforce-message').filter({hasText:'Roster sedang dimuat ulang'}).waitFor();
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).click();
  let row=dialog.locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByRole('heading',{name:'Ayu <Produksi>',exact:true}).waitFor();
  assert.equal(await row.locator('script').count(),0);
  await row.getByText('Belum dicatat',{exact:true}).waitFor();
  await page.unroute('**/api/workforce/attendance?*');

  await row.getByRole('button',{name:'Catat kehadiran',exact:true}).click();
  await dialog.getByLabel('Alasan pencatatan atau koreksi').fill('Masuk shift pagi');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  row=dialog.locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByText('Hadir',{exact:true}).waitFor();
  assert.ok((await row.innerText()).includes('08:00–17:00'));

  await row.getByRole('button',{name:'Koreksi kehadiran',exact:true}).click();
  await dialog.getByLabel('Alasan pencatatan atau koreksi').waitFor();
  await dialog.getByLabel('Status').selectOption('leave');
  assert.equal(await dialog.getByLabel('Jam masuk').isDisabled(),true);
  assert.equal(await dialog.getByLabel('Jam pulang').isDisabled(),true);
  assert.equal(await dialog.getByLabel('Lembur (menit)').isDisabled(),true);
  await dialog.getByLabel('Catatan',{exact:true}).fill('Cuti tahunan');
  await dialog.getByLabel('Alasan pencatatan atau koreksi').fill('Koreksi supervisor');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  row=dialog.locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByText('Cuti',{exact:true}).waitFor();
  await row.getByRole('button',{name:'Riwayat',exact:true}).click();
  await dialog.getByText('Revisi 2 · Cuti',{exact:true}).waitFor();
  await dialog.getByText('Revisi 1 · Hadir',{exact:true}).waitFor();
  await dialog.getByRole('button',{name:'Kembali ke roster',exact:true}).click();

  await dialog.getByRole('button',{name:'Tambah karyawan',exact:true}).click();
  const createdCode='PPL-UI-'+unique;
  await dialog.getByLabel('Kode karyawan').fill(createdCode.toLowerCase());
  await dialog.getByLabel('Nama karyawan').fill('Bima <Gudang>');
  await dialog.getByLabel('Departemen').fill('Gudang');
  await dialog.getByLabel('Sumber data awal').fill('Daftar staf aktif');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  const createdRow=dialog.locator('[data-workforce-employee]').filter({hasText:createdCode});
  await createdRow.getByRole('heading',{name:'Bima <Gudang>',exact:true}).waitFor();
  await dialog.getByRole('button',{name:'Daftar karyawan',exact:true}).click();
  const master=dialog.locator('[data-workforce-master]').filter({hasText:createdCode});
  await master.getByRole('button',{name:'Ubah',exact:true}).click();
  await dialog.getByLabel('Status').selectOption('false');
  await dialog.getByLabel('Alasan perubahan').fill('Kontrak selesai');
  await dialog.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await dialog.getByText('Roster harian',{exact:true}).waitFor();
  assert.equal(await dialog.locator('[data-workforce-employee]').filter({hasText:createdCode}).count(),0);

  await role(operator);
  await page.getByRole('button',{name:'People',exact:true}).click();
  dialog=page.locator('dialog');row=dialog.locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByRole('heading',{name:'Ayu <Produksi>',exact:true}).waitFor();
  assert.equal(await dialog.getByRole('button',{name:'Tambah karyawan',exact:true}).count(),0);
  await row.getByRole('button',{name:'Koreksi kehadiran',exact:true}).waitFor();

  await role(viewer);
  await page.getByRole('button',{name:'People',exact:true}).click();
  dialog=page.locator('dialog');row=dialog.locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByRole('heading',{name:'Ayu <Produksi>',exact:true}).waitFor();
  assert.equal(await dialog.getByRole('button',{name:'Tambah karyawan',exact:true}).count(),0);
  assert.equal(await dialog.getByRole('button',{name:/Catat kehadiran|Koreksi kehadiran/}).count(),0);
  await row.getByRole('button',{name:'Riwayat',exact:true}).waitFor();

  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),true,'People dialog overflow');
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.equal(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),true,'People dialog overflow at 200%');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.evaluate(()=>document.getElementById('theme').click());
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'dark');
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-people-mobile-dark.png')});
  await page.evaluate(()=>document.getElementById('theme').click());

  await dialog.locator('#workforce-filter select[name="status"]').selectOption('absent');
  await dialog.getByRole('button',{name:'Tampilkan roster',exact:true}).click();
  await dialog.getByText('Tidak ada karyawan yang cocok dengan status dan pencarian ini.',{exact:true}).waitFor();
  console.log('People browser QA PASS: admin/operator/viewer, retry, master, attendance correction/history, escaping, empty state, mobile/200%, dark theme.');
};
