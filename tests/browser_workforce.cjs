// Milestone B: People is a persistent workspace page; record-specific tasks
// (attendance correction/history, employee master, new employee) stay dialogs.
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
  const unique=Date.now();
  const employee=await apiPost('/api/workforce/employees',{
    code:'PPL-'+unique,name:'Ayu <Produksi>',department:'Produksi',reason:'Browser QA People'
  });
  const roster=()=>page.locator('#people-view');
  const dialog=()=>page.locator('dialog');
  const openPeople=async()=>{
    await page.getByRole('button',{name:'People',exact:true}).click();
    await page.getByRole('heading',{name:'People',exact:true}).waitFor();
  };

  await role(admin);
  let fail=true;
  await page.route('**/api/workforce/attendance?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Roster sedang dimuat ulang'})});}
    else await route.continue();
  });
  await openPeople();
  await roster().locator('#workforce-message').filter({hasText:'Roster sedang dimuat ulang'}).waitFor();
  await roster().getByRole('button',{name:'Coba lagi',exact:true}).click();
  let row=roster().locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByRole('heading',{name:'Ayu <Produksi>',exact:true}).waitFor();
  assert.equal(await row.locator('script').count(),0);
  await row.getByText('Belum dicatat',{exact:true}).waitFor();
  await page.unroute('**/api/workforce/attendance?*');

  await row.getByRole('button',{name:'Catat kehadiran',exact:true}).click();
  await dialog().getByLabel('Alasan pencatatan atau koreksi').fill('Masuk shift pagi');
  await dialog().getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  row=roster().locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByText('Hadir',{exact:true}).waitFor();
  assert.ok((await row.innerText()).includes('08:00–17:00'));

  await row.getByRole('button',{name:'Koreksi kehadiran',exact:true}).click();
  await dialog().getByLabel('Alasan pencatatan atau koreksi').waitFor();
  await dialog().getByLabel('Status').selectOption('leave');
  assert.equal(await dialog().getByLabel('Jam masuk').isDisabled(),true);
  assert.equal(await dialog().getByLabel('Jam pulang').isDisabled(),true);
  assert.equal(await dialog().getByLabel('Lembur (menit)').isDisabled(),true);
  await dialog().getByLabel('Catatan',{exact:true}).fill('Cuti tahunan');
  await dialog().getByLabel('Alasan pencatatan atau koreksi').fill('Koreksi supervisor');
  await dialog().getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  row=roster().locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByText('Cuti',{exact:true}).waitFor();
  await row.getByRole('button',{name:'Riwayat',exact:true}).click();
  await dialog().getByText('Revisi 2 · Cuti',{exact:true}).waitFor();
  await dialog().getByText('Revisi 1 · Hadir',{exact:true}).waitFor();
  await dialog().getByRole('button',{name:'Kembali ke roster',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});

  await roster().getByRole('button',{name:'Tambah karyawan',exact:true}).click();
  const createdCode='PPL-UI-'+unique;
  await dialog().getByLabel('Kode karyawan').fill(createdCode.toLowerCase());
  await dialog().getByLabel('Nama karyawan').fill('Bima <Gudang>');
  await dialog().getByLabel('Departemen').fill('Gudang');
  await dialog().getByLabel('Sumber data awal').fill('Daftar staf aktif');
  await dialog().getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  await roster().locator('[data-workforce-employee]').filter({hasText:createdCode})
    .getByRole('heading',{name:'Bima <Gudang>',exact:true}).waitFor();
  await roster().getByRole('button',{name:'Daftar karyawan',exact:true}).click();
  await dialog().locator('[data-workforce-master]').filter({hasText:createdCode}).waitFor();
  await dialog().locator('[data-workforce-master]').filter({hasText:createdCode})
    .getByRole('button',{name:'Ubah',exact:true}).click();
  await dialog().getByLabel('Status').selectOption('false');
  await dialog().getByLabel('Alasan perubahan').fill('Kontrak selesai');
  await dialog().getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  await roster().locator(`[data-workforce-employee="${employee.id}"]`)
    .getByRole('heading',{name:'Ayu <Produksi>',exact:true}).waitFor();
  assert.equal(await roster().locator('[data-workforce-employee]').filter({hasText:createdCode}).count(),0);

  await role(operator);
  await openPeople();
  row=roster().locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByRole('heading',{name:'Ayu <Produksi>',exact:true}).waitFor();
  assert.equal(await roster().getByRole('button',{name:'Tambah karyawan',exact:true}).count(),0);
  await row.getByRole('button',{name:'Koreksi kehadiran',exact:true}).waitFor();

  await role(viewer);
  await openPeople();
  row=roster().locator(`[data-workforce-employee="${employee.id}"]`);
  await row.getByRole('heading',{name:'Ayu <Produksi>',exact:true}).waitFor();
  assert.equal(await roster().getByRole('button',{name:'Tambah karyawan',exact:true}).count(),0);
  assert.equal(await row.getByRole('button',{name:/Catat kehadiran|Koreksi kehadiran/}).count(),0);
  await row.getByRole('button',{name:'Riwayat',exact:true}).waitFor();

  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true,'People page overflow');
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true,'People page overflow at 200%');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.evaluate(()=>document.getElementById('theme').click());
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'dark');
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-people-mobile-dark.png'),fullPage:true});
  await page.evaluate(()=>document.getElementById('theme').click());

  await roster().locator('#workforce-status').selectOption('absent');
  await roster().getByRole('button',{name:'Tampilkan roster',exact:true}).click();
  await roster().getByText('Tidak ada karyawan yang cocok dengan status dan pencarian ini.',{exact:true}).waitFor();
  console.log('People browser QA PASS: page roster, admin/operator/viewer, retry, master, attendance correction/history, escaping, empty-filter state, mobile/200%, dark theme.');
};
