const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,openSidebarDestination,admin,operator,viewer,apiGet,work})=>{
  await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(admin);
  const batch=(await apiGet('/api/material-batches')).find(b=>b.reference==='BATCH-UI-001');
  await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
  await page.getByRole('button',{name:'Reservasi bahan',exact:true}).click();
  await page.getByText('Belum ada reservasi untuk order ini.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Tambah reservasi',exact:true}).click();
  await page.getByLabel('Batch untuk reservasi',{exact:true}).selectOption(batch.id);
  await page.getByLabel('Jumlah tambahan reservasi',{exact:true}).fill('8.125');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('Jatah cutting order satu');
  let drop=true;
  await page.route('**/api/material-reservations',async route=>{
    if(drop){drop=false;await route.fetch();await route.abort('failed');}else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});await page.unroute('**/api/material-reservations');
  assert.equal((await apiGet('/api/material-batches/'+batch.id)).available,'2.000');
  await page.getByRole('button',{name:'Semua order',exact:false}).click();
  await page.getByRole('button',{name:/DEMO-PROD-002/}).click();
  await page.getByRole('button',{name:'Keluarkan bahan ke order',exact:true}).click();
  // Scoped to the dialog: A6.2 gave the Bahan baku page a "Batch bahan" region, so an unscoped
  // label lookup can resolve to that landmark instead of this dialog's own control.
  await page.locator('#dialog').getByLabel('Batch bahan',{exact:true}).selectOption(batch.id);
  assert.equal(await page.getByLabel('Jumlah dikeluarkan',{exact:true}).getAttribute('max'),'2.000');
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Semua order',exact:false}).click();
  await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
  await page.getByRole('button',{name:'Keluarkan bahan ke order',exact:true}).click();
  await page.getByLabel('Jumlah dikeluarkan',{exact:true}).fill('2.125');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('Pakai jatah cutting');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();await page.locator('dialog').waitFor({state:'hidden'});
  assert.equal((await apiGet('/api/material-batches/'+batch.id)).reserved,'6.000');
  await page.getByRole('button',{name:'Reservasi bahan',exact:true}).click();
  await page.getByText('Jatah tersisa: 6 m',{exact:true}).waitFor();
  await page.getByText('Dipakai oleh pengeluaran · -2,125 m',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Lepaskan reservasi',exact:true}).click();
  await page.getByLabel('Jumlah dilepaskan',{exact:true}).fill('1');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('Sisa dialihkan untuk order lain');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();await page.locator('dialog').waitFor({state:'hidden'});
  assert.equal((await apiGet('/api/material-batches/'+batch.id)).available,'3.000');
  await page.getByRole('button',{name:'Reservasi bahan',exact:true}).click();
  await page.getByText('Jatah tersisa: 5 m',{exact:true}).waitFor();
  await page.getByText('Reservasi dilepas · -1 m',{exact:true}).waitFor();
  const artifacts=process.env.BEELOFT_QA_SCREENSHOTS || work;
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:path.join(artifacts,'beeloft-reservations.png'),fullPage:true});
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),'Reservation overflow '+width);
  }
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),'Reservation 200% overflow');
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.keyboard.press('Escape');
  await openSidebarDestination('Bahan baku');
  // A6.2 turned the batch row into a table: the reservation is a cell under its own "Direservasi"
  // column header rather than a "Direservasi 5 m" run of text inside a hint paragraph.
  await page.locator('#batch-list [data-batch-reserved]').getByText('5 m',{exact:true}).waitFor();
  for(const key of [operator,viewer]){
    await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);
    await page.getByRole('button',{name:/DEMO-PROD-001/}).click();
    await page.getByRole('button',{name:'Reservasi bahan',exact:true}).click();
    await page.getByText('Jatah tersisa: 5 m',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Tambah reservasi',exact:true}).count(),0);
    assert.equal(await page.getByRole('button',{name:'Lepaskan reservasi',exact:true}).count(),0);
    await page.keyboard.press('Escape');
  }
  console.log('Reservation browser QA PASS: add/retry, cross-order availability, own consumption, release, ledger, roles, mobile/200%.');
};
