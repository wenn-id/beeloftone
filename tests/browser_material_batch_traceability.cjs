const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work,receipt})=>{
  const batch=await apiGet('/api/material-batches/'+receipt.batch_id);
  await page.keyboard.press('Escape');await login(viewer);
  await page.getByRole('button',{name:'Bahan baku',exact:true}).click();
  await page.getByRole('button',{name:'Scan batch bahan',exact:true}).click();
  await page.getByLabel('Kode batch bahan',{exact:true}).fill(batch.scan_code);
  await page.getByRole('button',{name:'Buka batch',exact:true}).click();
  await page.getByRole('button',{name:'Jejak produksi lengkap',exact:true}).waitFor();
  let failFirst=true;
  await page.route('**/api/material-batches/*/traceability?*',async route=>{
    if(failFirst){failFirst=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Jejak produksi sedang sibuk'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Jejak produksi lengkap',exact:true}).click();
  await page.getByText('Jejak produksi sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.locator('[data-material-trace-event]').first().waitFor();
  for(const type of ['material_receipt','material_issue','material_consumption','cutting_run','bundle',
    'sewing_job','sewing_result','finishing','final_qc','finished_goods_receipt']){
    assert.ok(await page.locator('[data-material-trace-event="'+type+'"]').count(),type);
  }
  assert.equal(await page.getByRole('button',{name:'Muat catatan sebelumnya',exact:true}).isHidden(),true);
  await page.getByText('internal ke Line Gudang <A>',{exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-material-traceability-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-material-trace-event="finished_goods_receipt"]').first().getByRole('button').click();
  await page.getByRole('heading',{name:'Rincian barang jadi',exact:true}).waitFor();
  await page.keyboard.press('Escape');await page.unroute('**/api/material-batches/*/traceability?*');
  console.log('Material batch traceability browser QA PASS: scan entry, production lineage, retry, viewer, detail links, escaping, mobile/200%.');
};
