const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,openSidebarDestination,admin,operator,viewer,apiGet,apiPost,work,run})=>{
  const bundle=await apiPost('/api/cutting-runs/'+run.id+'/bundles',{reference:'BDL-SCAN-UI',
    output_movement_id:run.outputs[0].id,quantity:5,reason:'CONTOH label QR untuk handoff'},'bundle-scan-ui');
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  await role(viewer);

  let fail=true;
  await page.route('**/api/bundles/scan?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Pemindai bundle sedang sibuk'})});}
    else await route.continue();
  });
  await openSidebarDestination('Scan bundle');
  const input=page.getByLabel('Kode bundle',{exact:true});
  assert.equal(await input.evaluate(element=>element===document.activeElement),true);
  await input.fill(bundle.scan_code);await input.press('Enter');
  await page.getByText('Pemindai bundle sedang sibuk',{exact:true}).waitFor();
  await input.press('Enter');
  await page.locator('#bundle-scan-result').getByText(bundle.reference,{exact:true}).waitFor();
  assert.equal(await page.locator('#dialog').getAttribute('open'),null);
  await page.getByRole('button',{name:'Rincian bundle',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian bundle',exact:true}).waitFor();
  await page.unroute('**/api/bundles/scan?*');
  await page.locator('.bundle-label').getByText('BDL-SCAN-UI',{exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.bundle-label img')?.naturalWidth>0);
  assert.equal(await page.locator('.bundle-label').getByText('5 pcs',{exact:true}).count(),1);
  assert.equal(await page.getByRole('button',{name:'Serahkan bundle',exact:true}).count(),0);

  const label=await fetch(process.env.BEELOFT_QA_BASE+'/api/bundles/'+bundle.id+'/label.svg',
    {headers:{'X-API-Key':viewer}});
  assert.equal(label.status,200);assert.match(label.headers.get('content-type'),/^image\/svg\+xml/);
  assert.ok((await label.text()).includes(bundle.scan_code));
  await page.evaluate(()=>{window.__bundlePrinted=false;window.print=()=>{window.__bundlePrinted=true;};});
  await page.getByRole('button',{name:'Cetak label',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.__bundlePrinted),true);
  await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('.bundle-label').isVisible(),true);
  assert.equal(await page.locator('#main').isVisible(),false);
  await page.emulateMedia({media:'screen'});
  await page.getByRole('button',{name:'Tutup dialog',exact:true}).click();
  assert.equal(await page.locator('#bundle-scan-view').isVisible(),true);
  assert.equal(await input.inputValue(),bundle.scan_code);
  await page.getByRole('button',{name:'Rincian bundle',exact:true}).click();

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-bundle-scan-label-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});

  await role(admin);
  await openSidebarDestination('Scan bundle');
  await page.getByLabel('Kode bundle',{exact:true}).fill('bdl-scan-ui');
  await page.getByLabel('Kode bundle',{exact:true}).press('Enter');
  await page.getByRole('button',{name:'Rincian bundle',exact:true}).click();
  await page.getByRole('button',{name:'Serahkan bundle',exact:true}).click();
  await page.getByRole('button',{name:'Batal',exact:true}).click();
  assert.equal(await page.locator('#bundle-scan-view').isVisible(),true);
  assert.equal((await apiGet('/api/bundles/'+bundle.id+'/handoffs')).length,0);
  await page.getByRole('button',{name:'Rincian bundle',exact:true}).click();
  await page.getByRole('button',{name:'Serahkan bundle',exact:true}).click();
  await page.getByLabel('Tujuan / stasiun penerima',{exact:true}).fill('Sewing Line A <aman>');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH diserahkan setelah hitung fisik');
  const handoffKeys=[];
  await page.route('**/api/bundles/'+bundle.id+'/handoffs',async route=>{
    handoffKeys.push(route.request().headers()['idempotency-key']);
    if(handoffKeys.length===1){await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#dialog').getAttribute('open'),'');
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByText('menunggu penerima',{exact:false}).waitFor();
  assert.equal(handoffKeys.length,2); assert.ok(handoffKeys[0]); assert.equal(handoffKeys[0],handoffKeys[1]);
  assert.equal((await apiGet('/api/bundles/'+bundle.id+'/handoffs')).length,1);
  await page.unroute('**/api/bundles/'+bundle.id+'/handoffs');
  assert.equal(await page.getByRole('button',{name:'Konfirmasi terima',exact:true}).count(),0);

  await role(operator);
  await openSidebarDestination('Scan bundle');
  await page.getByLabel('Kode bundle',{exact:true}).fill(bundle.scan_code);
  await page.getByLabel('Kode bundle',{exact:true}).press('Enter');
  await page.getByRole('button',{name:'Rincian bundle',exact:true}).click();
  await page.getByRole('button',{name:'Konfirmasi terima',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH jumlah dan kondisi fisik sesuai');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  // A6.3: custody is a labelled fact in the bundle detail's "Posisi bundle sekarang" grid, so the
  // label is a <dt> without the sentence colon it carried as prose, and the location keeps its own
  // text node in the <dd> - which is what the exact match below still proves.
  await page.getByText('Lokasi custody sekarang',{exact:false}).waitFor();
  await page.getByText('Sewing Line A <aman>',{exact:true}).waitFor();

  let failHistory=true;
  await page.route('**/api/bundles/*/handoffs?*',async route=>{
    if(failHistory){failHistory=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Riwayat handoff sedang sibuk'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Riwayat serah-terima',exact:true}).click();
  await page.getByText('Riwayat handoff sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Sudah diterima',{exact:true}).waitFor();
  await page.getByText('Sewing Line A <aman>',{exact:false}).waitFor();
  await page.unroute('**/api/bundles/*/handoffs?*');
  console.log('Bundle scan/handoff browser QA PASS: keyboard scan, QR, print, two-party custody, history retry, roles, mobile/200%.');
};
