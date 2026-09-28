const assert=require('node:assert/strict');
const path=require('node:path');

// P01 (#48): alur UI template jasa dan tarif upah berversi.
// Urutan yang diuji: kelompok jasa -> jenis pekerjaan -> tarif + tanggal
// berlaku -> template beberapa pekerjaan -> penerapan ke SKU -> riwayat ->
// preview tarif per tanggal. Tarif hilang dan tarif nonaktif harus memberi
// pesan eksplisit, bukan nominal nol atau tarif terbaru secara diam-diam.
module.exports=async({page,login,openSidebarDestination,admin,viewer,apiGet,work})=>{
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(admin);
  await openSidebarDestination('Master katalog');

  // -- Kelompok jasa --------------------------------------------------------
  await page.getByRole('tab',{name:'Kelompok jasa',exact:true}).click();
  await page.getByText(/Belum ada kelompok jasa/).waitFor();
  await page.getByRole('button',{name:'Tambah',exact:true}).click();
  await page.getByLabel('Kode kelompok',{exact:true}).fill('QA-JAHIT-GRUP');
  await page.getByLabel('Nama kelompok',{exact:true}).fill('QA Kelompok Jahit');
  await page.getByLabel('Alasan pencatatan',{exact:true}).fill('CONTOH - kelompok jasa QA');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('#master-catalog-list').getByText('QA-JAHIT-GRUP',{exact:true}).waitFor();

  // -- Jenis pekerjaan -----------------------------------------------------
  await page.getByRole('tab',{name:'Jenis pekerjaan',exact:true}).click();
  await page.getByText(/Belum ada jenis pekerjaan/).waitFor();
  for(const [code,name] of [['QA-JAHIT','QA Jahit'],['QA-LABEL','QA Pasang Label']]){
    await page.getByRole('button',{name:'Tambah',exact:true}).click();
    await page.getByLabel('Kode pekerjaan',{exact:true}).fill(code);
    await page.getByLabel('Nama pekerjaan',{exact:true}).fill(name);
    await page.getByLabel('Kelompok jasa',{exact:true}).selectOption({label:/QA-JAHIT-GRUP/});
    await page.getByLabel('Alasan pencatatan',{exact:true}).fill('CONTOH - jenis pekerjaan QA');
    await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
    await page.locator('#master-catalog-list').getByText(code,{exact:true}).waitFor();
  }
  const workTypes=await apiGet('/api/work-types');
  const jahit=workTypes.find(w=>w.code==='QA-JAHIT'), label=workTypes.find(w=>w.code==='QA-LABEL');
  assert.ok(jahit&&label,'kedua jenis pekerjaan QA tersimpan');
  assert.equal(jahit.service_group_code,'QA-JAHIT-GRUP');

  // -- Tarif hilang memberi pesan eksplisit --------------------------------
  await page.getByRole('button',{name:'Tarif QA-JAHIT',exact:true}).click();
  await page.getByText(/Belum ada tarif/).waitFor();
  await page.getByRole('button',{name:'Preview tarif per tanggal',exact:true}).click();
  await page.getByLabel('Tanggal pengerjaan',{exact:true}).fill('2026-09-15');
  await page.getByRole('button',{name:'Lihat tarif',exact:true}).click();
  await page.getByText(/belum pernah dibuat/).waitFor();
  await page.keyboard.press('Escape');

  // -- Revisi tarif R1 dan R2 dengan tanggal berlaku -----------------------
  await page.getByRole('button',{name:'Tarif QA-JAHIT',exact:true}).click();
  await page.getByRole('button',{name:'Tambah revisi tarif',exact:true}).click();
  await page.getByLabel('Basis tarif',{exact:true}).selectOption('lusin');
  await page.getByLabel('Nominal (Rp)',{exact:true}).fill('120.00');
  await page.getByLabel('Mulai berlaku',{exact:true}).fill('2026-09-01');
  await page.getByLabel('Berakhir (opsional)',{exact:true}).fill('2026-09-16');
  await page.getByLabel('Alasan tarif baru',{exact:true}).fill('CONTOH - tarif R1');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText(/Revisi 1/).first().waitFor();
  await page.getByRole('button',{name:'Tambah revisi tarif',exact:true}).click();
  await page.getByLabel('Basis tarif',{exact:true}).selectOption('lusin');
  await page.getByLabel('Nominal (Rp)',{exact:true}).fill('144.00');
  await page.getByLabel('Mulai berlaku',{exact:true}).fill('2026-09-16');
  await page.getByLabel('Alasan tarif baru',{exact:true}).fill('CONTOH - tarif R2');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText(/Revisi 2/).first().waitFor();

  // Interval tumpang tindih ditolak server, bukan diterima diam-diam.
  await page.getByRole('button',{name:'Tambah revisi tarif',exact:true}).click();
  await page.getByLabel('Basis tarif',{exact:true}).selectOption('lusin');
  await page.getByLabel('Nominal (Rp)',{exact:true}).fill('200.00');
  await page.getByLabel('Mulai berlaku',{exact:true}).fill('2026-09-20');
  await page.getByLabel('Alasan tarif baru',{exact:true}).fill('CONTOH - overlap');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText(/tumpang tindih/).waitFor();
  await page.keyboard.press('Escape');

  // Tarif untuk pekerjaan kedua supaya resolve SKU lengkap.
  await page.getByRole('button',{name:'Tarif QA-LABEL',exact:true}).click();
  await page.getByRole('button',{name:'Tambah revisi tarif',exact:true}).click();
  await page.getByLabel('Basis tarif',{exact:true}).selectOption('pcs');
  await page.getByLabel('Nominal (Rp)',{exact:true}).fill('10.00');
  await page.getByLabel('Mulai berlaku',{exact:true}).fill('2026-09-01');
  await page.getByLabel('Alasan tarif baru',{exact:true}).fill('CONTOH - tarif label');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText(/Revisi 1/).first().waitFor();
  await page.keyboard.press('Escape');

  // -- Preview tarif tepat pada batas tanggal efektif ----------------------
  await page.getByRole('button',{name:'Tarif QA-JAHIT',exact:true}).click();
  await page.getByRole('button',{name:'Preview tarif per tanggal',exact:true}).click();
  await page.getByLabel('Tanggal pengerjaan',{exact:true}).fill('2026-09-15');
  await page.getByLabel('Jumlah pcs (opsional)',{exact:true}).fill('13');
  await page.getByRole('button',{name:'Lihat tarif',exact:true}).click();
  await page.getByText('QA-JAHIT#1',{exact:true}).waitFor();
  await page.getByLabel('Tanggal pengerjaan',{exact:true}).fill('2026-09-16');
  await page.getByRole('button',{name:'Lihat tarif',exact:true}).click();
  await page.getByText('QA-JAHIT#2',{exact:true}).waitFor();
  // 13 pcs = 13/12 lusin; 13/12 x 144.00 = 156.00 tanpa float.
  await page.getByText('Rp156.00',{exact:true}).waitFor();
  await page.getByText('13/12',{exact:false}).first().waitFor();
  const preview=await apiGet('/api/work-types/'+jahit.id+'/rate-preview?effective_date=2026-09-16&pcs=13');
  assert.equal(preview.wage_minor,15600);
  assert.equal(preview.lusin_exact,'13/12');
  assert.equal(preview.rate_revision,'QA-JAHIT#2');
  const artifacts=process.env.BEELOFT_QA_SCREENSHOTS || work;
  await page.screenshot({path:path.join(artifacts,'beeloft-p01-rate-preview.png'),fullPage:true});
  await page.keyboard.press('Escape');

  // -- Template jasa dengan beberapa pekerjaan -----------------------------
  await page.getByRole('tab',{name:'Template jasa',exact:true}).click();
  await page.getByText(/Belum ada template jasa/).waitFor();
  await page.getByRole('button',{name:'Tambah',exact:true}).click();
  await page.getByLabel('Kode template',{exact:true}).fill('QA-TPL-JASA');
  await page.getByLabel('Nama template',{exact:true}).fill('QA Template Jasa');
  await page.getByLabel('Catatan',{exact:true}).fill('CONTOH - dua pekerjaan');
  await page.locator('[data-service-row]').first().locator('[data-work-type]').selectOption(jahit.id);
  await page.getByRole('button',{name:'Tambah baris pekerjaan',exact:true}).click();
  await page.locator('[data-service-row]').nth(1).locator('[data-work-type]').selectOption(label.id);
  await page.getByLabel('Alasan pencatatan',{exact:true}).fill('CONTOH - template jasa QA');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('#master-catalog-list').getByText('QA-TPL-JASA',{exact:true}).waitFor();
  const templates=await apiGet('/api/service-templates');
  const template=templates.find(t=>t.code==='QA-TPL-JASA');
  assert.equal(template.components.length,2,'satu template memakai dua pekerjaan');

  // -- Penerapan template ke SKU -------------------------------------------
  const product=(await apiGet('/api/products'))[0];
  await page.getByRole('button',{name:'Terapkan',exact:true}).first().click();
  await page.getByLabel('SKU tujuan',{exact:true}).selectOption(product.id);
  await page.getByLabel('Alasan penerapan template',{exact:true}).fill('CONTOH - penerapan template jasa');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText(/Revisi template 1/).waitFor();
  await page.getByText(/QA-JAHIT, QA-LABEL/).waitFor();
  await page.keyboard.press('Escape');

  // -- Riwayat penerapan dan preview tarif dari halaman SKU ----------------
  await openSidebarDestination('Master SKU');
  await page.getByRole('button',{name:'Jasa dan tarif '+product.sku,exact:true}).click();
  await page.getByText('QA-TPL-JASA',{exact:false}).first().waitFor();
  await page.getByRole('button',{name:'Preview tarif per tanggal',exact:true}).click();
  await page.getByLabel('Tanggal pengerjaan',{exact:true}).fill('2026-09-16');
  await page.getByRole('button',{name:'Lihat tarif',exact:true}).click();
  await page.getByText('QA-JAHIT#2',{exact:true}).waitFor();
  await page.getByText('QA-LABEL#1',{exact:true}).waitFor();
  await page.screenshot({path:path.join(artifacts,'beeloft-p01-sku-rates.png'),fullPage:true});
  await page.keyboard.press('Escape');

  // -- Tarif nonaktif: pesan eksplisit, snapshot lama tidak berubah --------
  const before=await apiGet('/api/work-types/'+jahit.id+'/rate-preview?effective_date=2026-09-16');
  await openSidebarDestination('Master katalog');
  await page.getByRole('tab',{name:'Jenis pekerjaan',exact:true}).click();
  await page.getByRole('button',{name:'Tarif QA-JAHIT',exact:true}).click();
  await page.getByRole('button',{name:'Nonaktifkan tarif',exact:true}).click();
  await page.getByLabel('Alasan penonaktifan',{exact:true}).fill('CONTOH - hentikan tarif');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText(/Revisi 3/).first().waitFor();
  await page.getByRole('button',{name:'Preview tarif per tanggal',exact:true}).click();
  await page.getByLabel('Tanggal pengerjaan',{exact:true}).fill('2026-09-16');
  await page.getByRole('button',{name:'Lihat tarif',exact:true}).click();
  await page.getByText(/nonaktif pada/).waitFor();
  // Tanggal yang dicakup revisi lama tetap terbaca: histori tidak dihapus.
  await page.getByLabel('Tanggal pengerjaan',{exact:true}).fill('2026-09-15');
  await page.getByRole('button',{name:'Lihat tarif',exact:true}).click();
  await page.getByText('QA-JAHIT#1',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  const history=await apiGet('/api/work-types/'+jahit.id+'/rate-history');
  assert.equal(history.length,3,'revisi tarif tetap append-only');
  assert.equal(history[0].active,0);
  assert.equal(history[1].amount_minor,before.amount_minor,'nominal revisi lama tidak berubah');

  // -- Riwayat revisi template ---------------------------------------------
  await page.getByRole('tab',{name:'Template jasa',exact:true}).click();
  await page.getByRole('button',{name:'Riwayat QA-TPL-JASA',exact:true}).click();
  await page.getByText(/Revisi 1/).first().waitFor();
  await page.keyboard.press('Escape');

  // -- Izin: viewer membaca, tidak menulis ---------------------------------
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(viewer);
  await openSidebarDestination('Master katalog');
  await page.getByRole('tab',{name:'Jenis pekerjaan',exact:true}).click();
  await page.locator('#master-catalog-list').getByText('QA-JAHIT',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Tambah',exact:true}).count(),0,'viewer tidak melihat tombol Tambah');
  await page.getByRole('button',{name:'Tarif QA-JAHIT',exact:true}).click();
  await page.getByText(/Riwayat tarif/).waitFor();
  assert.equal(await page.getByRole('button',{name:'Tambah revisi tarif',exact:true}).count(),0,'viewer tidak dapat menambah tarif');
  await page.getByRole('button',{name:'Preview tarif per tanggal',exact:true}).waitFor();
  await page.keyboard.press('Escape');

  // -- Mobile dan 200% teks tidak meluber ----------------------------------
  await page.getByRole('button',{name:'Tarif QA-LABEL',exact:true}).click();
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),'Rate dialog overflow '+width);
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}),'Rate dialog 200% overflow');
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');

  console.log('P01 browser QA PASS: kelompok/jenis pekerjaan, tarif berversi, batas tanggal efektif, overlap ditolak, konversi pcs/lusin eksak, template banyak pekerjaan, penerapan SKU, riwayat, tarif nonaktif, izin viewer, mobile/200%.');
};
