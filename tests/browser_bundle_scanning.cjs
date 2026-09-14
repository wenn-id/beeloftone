const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,viewer,apiPost,work,run})=>{
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
  await page.getByRole('button',{name:'Scan bundle',exact:true}).click();
  const input=page.getByLabel('Kode bundle',{exact:true});
  assert.equal(await input.evaluate(element=>element===document.activeElement),true);
  await input.fill(bundle.scan_code);await input.press('Enter');
  await page.getByText('Pemindai bundle sedang sibuk',{exact:true}).waitFor();
  await input.press('Enter');
  await page.getByRole('heading',{name:'Rincian bundle',exact:true}).waitFor();
  await page.unroute('**/api/bundles/scan?*');
  await page.locator('.bundle-label').getByText('BDL-SCAN-UI',{exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.bundle-label img')?.naturalWidth>0);
  assert.equal(await page.locator('.bundle-label').getByText('5 pcs',{exact:true}).count(),1);

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

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-bundle-scan-label-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  console.log('Bundle scan browser QA PASS: keyboard scan, retry, viewer lookup, QR load, print, mobile/200%.');
};
