const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,apiPost,work,qualityFinishing})=>{
  const record=await apiPost('/api/finishing-records/'+qualityFinishing.id+'/qc-records',{
    reference:'FQC-QUALITY-TREND',measurement_notes:'Ukuran sesuai toleransi',
    visual_notes:'Jahitan diperiksa menyeluruh',defect_type:'Jahitan <loncat>',
    responsible_source:'Line QC <A>',disposition:'Rework sebelum masuk gudang',
    accepted_quantity:15,rework_quantity:3,reject_quantity:2,
    inspection_date:'2026-09-15',reason:'CONTOH laporan kualitas produksi'
  },'fqc-quality-trend');
  const params=new URLSearchParams({as_of:'2026-09-30',window_days:'30',warning_percent:'20',
    change_threshold:'1',status:'attention'});
  const report=await apiGet('/api/production-quality-insights?'+params);
  assert.deepEqual([report.total,report.summary.inspected_quantity,
    report.summary.nonconforming_quantity,report.summary.first_pass_yield_percent,
    report.items[0].assignee,report.items[0].current.nonconforming_rate_percent],
    [1,20,5,'75.00','Line QC <A>','25.00']);
  assert.equal(report.items[0].recent_records[0].id,record.id);

  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(viewer);
  let fail=true;
  await page.route('**/api/production-quality-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Laporan kualitas sedang dihitung ulang'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Kualitas produksi',exact:true}).click();
  const dialog=page.locator('dialog');
  await page.locator('#production-quality-message').filter({hasText:'Laporan kualitas sedang dihitung ulang'}).waitFor();
  await dialog.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-09-30');
  await dialog.getByLabel('Batas rework + reject (%)',{exact:true}).fill('20');
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const item=page.locator('[data-production-quality]');
  await item.getByRole('heading',{name:'Line QC <A>',exact:true}).waitFor();
  await item.getByText('Perlu perhatian',{exact:true}).waitFor();
  await item.getByText('Jahitan <loncat>',{exact:true}).waitFor();
  await item.getByText('Yield').waitFor();
  assert.ok((await item.innerText()).includes('75.00%'));
  assert.equal(await item.locator('script').count(),0);
  await page.unroute('**/api/production-quality-insights?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await item.scrollIntoViewIfNeeded();
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-production-quality-mobile.png')});

  await dialog.locator('select[name="status"]').selectOption('healthy');
  await dialog.getByRole('button',{name:'Tampilkan kualitas',exact:true}).click();
  await dialog.getByText('Tidak ada penanggung jawab yang cocok dengan status dan filter periode ini.',{exact:true}).waitFor();
  await dialog.locator('select[name="status"]').selectOption('attention');
  await dialog.getByRole('button',{name:'Tampilkan kualitas',exact:true}).click();
  await item.getByRole('heading',{name:'Line QC <A>',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Command center',exact:true}).click();
  const qualitySnapshot=page.locator('[data-command-snapshot="quality"]');
  await qualitySnapshot.getByText('75.00%',{exact:true}).waitFor();
  await qualitySnapshot.getByText('25.00%',{exact:true}).waitFor();
  const alert=page.locator('[data-command-attention="production-quality"]');
  await alert.getByRole('heading',{name:'Kualitas Line QC <A> (line internal) perlu perhatian',exact:true}).waitFor();
  await alert.getByText('Rework + reject 25.00% dari 20 pcs; melewati batas 5%.',{exact:true}).waitFor();
  await alert.getByRole('button',{name:'Buka analisis kualitas',exact:true}).click();
  await item.getByRole('heading',{name:'Line QC <A>',exact:true}).waitFor();
  await item.getByRole('button',{name:'Buka final QC FQC-QUALITY-TREND',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian final QC',exact:true}).waitFor();
  console.log('Production quality browser QA PASS: yield, defect trend, escaping, retry, viewer, empty state, drill-down, mobile/200%.');
};
