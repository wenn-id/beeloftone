const assert=require('node:assert/strict');

// P3-B di layar: penolakan batas tanggal harus muncul sebagai pesannya sendiri di dalam dialog
// laporan, bukan sebagai error generik. Sebelum perbaikan, `as_of` di tepi kalender membuat server
// menjawab HTTP 500 sehingga pengguna hanya melihat "Internal Server Error" tanpa tahu parameter
// mana yang harus diubah, dan laporannya tidak pernah dapat dimuat lagi tanpa menutup dialog.
module.exports=async({page,login,openSidebarDestination,admin,viewer})=>{
  const dialog=page.locator('dialog');
  const outOfRange=/di luar kalender yang terwakili/;

  // ---------------------------------------------------------------- analisis kualitas
  await openSidebarDestination('Kualitas produksi');
  await dialog.getByLabel('Data sampai tanggal',{exact:true}).fill('0001-01-01');
  await dialog.getByRole('button',{name:'Tampilkan kualitas',exact:true}).click();
  const qualityMessage=page.locator('#production-quality-message');
  await qualityMessage.filter({hasText:outOfRange}).waitFor();
  const qualityText=await qualityMessage.innerText();
  assert.ok(qualityText.includes('as_of'),'pesan harus menyebut as_of: '+qualityText);
  assert.ok(qualityText.includes('window_days'),'pesan harus menyebut window_days: '+qualityText);
  assert.ok(qualityText.includes('0001-01-01 sampai 9999-12-31'),qualityText);
  assert.ok(!/Internal Server Error/i.test(qualityText),qualityText);
  assert.ok(!/belum terkonfirmasi/i.test(qualityText),'laporan hanya dibaca, jangan tawarkan retry penyimpanan');
  // Kesalahan ini tidak mematikan dialog: tanggal yang sah langsung memuat laporannya.
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).waitFor();
  await dialog.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-09-30');
  await dialog.getByRole('button',{name:'Tampilkan kualitas',exact:true}).click();
  await page.locator('#production-quality-summary .form-info').waitFor();
  assert.equal(await qualityMessage.isVisible(),false);

  // Batas aman tepat: 0001-01-14 dengan jendela 7 hari masih dapat dihitung seluruhnya.
  await dialog.getByLabel('Data sampai tanggal',{exact:true}).fill('0001-01-14');
  await dialog.getByLabel('Panjang periode (hari)',{exact:true}).fill('7');
  await dialog.getByRole('button',{name:'Tampilkan kualitas',exact:true}).click();
  await page.locator('#production-quality-results').getByText(
    'Tidak ada penanggung jawab yang cocok dengan status dan filter periode ini.',{exact:true}).waitFor();
  assert.equal(await qualityMessage.isVisible(),false,'batas aman tidak boleh ditolak');
  // Satu hari di luar batas aman ditolak lagi dengan pesan yang sama.
  await dialog.getByLabel('Data sampai tanggal',{exact:true}).fill('0001-01-13');
  await dialog.getByRole('button',{name:'Tampilkan kualitas',exact:true}).click();
  await qualityMessage.filter({hasText:outOfRange}).waitFor();
  await page.keyboard.press('Escape');

  // ---------------------------------------------------------------- rencana kapasitas
  await page.getByRole('button',{name:'Kapasitas produksi',exact:true}).click();
  await page.locator('#capacity-plan-form').waitFor();
  await dialog.getByLabel('Mulai per tanggal',{exact:true}).fill('9999-12-31');
  await dialog.getByLabel('Horizon kalender (hari)',{exact:true}).fill('14');
  await dialog.getByRole('button',{name:'Hitung kapasitas',exact:true}).click();
  const capacityMessage=page.locator('#capacity-plan-message');
  await capacityMessage.filter({hasText:outOfRange}).waitFor();
  const capacityText=await capacityMessage.innerText();
  assert.ok(capacityText.includes('horizon_days'),'pesan harus menyebut horizon_days: '+capacityText);
  assert.ok(!/Internal Server Error/i.test(capacityText),capacityText);
  // Horizon satu hari berakhir pada tanggal itu sendiri, jadi masih terwakili kalender.
  await dialog.getByLabel('Horizon kalender (hari)',{exact:true}).fill('1');
  await dialog.getByRole('button',{name:'Hitung kapasitas',exact:true}).click();
  await page.locator('#capacity-plan-summary .form-info').waitFor();
  assert.equal(await capacityMessage.isVisible(),false,'horizon satu hari di 9999-12-31 tetap sah');
  await page.keyboard.press('Escape');

  // ---------------------------------------------------------------- investigasi AI (viewer)
  // Investigasi yang disimpan adalah transaksi ber-Idempotency-Key. 500 dulu membuat klien
  // menandainya "belum terkonfirmasi" dan menawarkan ulang penyimpanan yang tidak akan berhasil.
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(viewer);
  await openSidebarDestination('Tanya Beeloft');
  await page.getByLabel('Pertanyaan bisnis',{exact:true}).fill('Apakah stok akan habis?');
  await page.getByText('Asumsi analisis',{exact:true}).click();
  await page.getByLabel('Data sampai tanggal',{exact:true}).fill('0001-01-01');
  await page.getByRole('button',{name:'Analisis dan simpan',exact:true}).click();
  const brainMessage=page.locator('#ai-message');
  await brainMessage.filter({hasText:outOfRange}).waitFor();
  const brainText=await brainMessage.innerText();
  assert.ok(!/belum terkonfirmasi/i.test(brainText),
    'penolakan 422 tidak boleh terlihat sebagai penyimpanan yang tidak pasti: '+brainText);
  assert.ok(!/Coba ulang penyimpanan/i.test(brainText),brainText);
  assert.ok(!/Internal Server Error/i.test(brainText),brainText);
  // Tanggal yang sah tetap dapat disimpan dari dialog yang sama.
  await page.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-12-13');
  await page.getByRole('button',{name:'Analisis dan simpan',exact:true}).click();
  await page.locator('#ai-results .ai-answer').waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(admin);
  console.log('Date boundary browser QA PASS: out-of-range dates surface the Indonesian message '
    +'inside the report dialog, safe boundaries still load, and a refused investigation never '
    +'looks like an unconfirmed save.');
};
