const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,work,receipt})=>{
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(viewer);
  let fail=true;
  await page.route('**/api/finished-goods-receipts/scan?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Pemindai barang jadi sedang sibuk'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Scan barang jadi',exact:true}).click();
  const input=page.getByLabel('Kode barang jadi',{exact:true});
  assert.equal(await input.evaluate(element=>element===document.activeElement),true);
  await input.fill(receipt.scan_code);await input.press('Enter');
  await page.getByText('Pemindai barang jadi sedang sibuk',{exact:true}).waitFor();
  await input.press('Enter');
  await page.locator('#finished-goods-scan-result').getByText(receipt.reference,{exact:true}).waitFor();
  assert.equal(await page.locator('#dialog').getAttribute('open'),null);
  await page.getByRole('button',{name:'Rincian barang jadi',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian barang jadi',exact:true}).waitFor();
  await page.unroute('**/api/finished-goods-receipts/scan?*');
  await page.locator('.finished-goods-label').getByText(receipt.reference,{exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.finished-goods-label img')?.naturalWidth>0);
  assert.equal(await page.locator('.finished-goods-label').getByText('20 pcs',{exact:true}).count(),1);
  assert.equal(await page.getByRole('button',{name:'Transfer lokasi',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Reservasi marketplace',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Catat stock opname',exact:true}).count(),0);

  const label=await fetch(process.env.BEELOFT_QA_BASE+'/api/finished-goods-receipts/'+receipt.id+'/label.svg',
    {headers:{'X-API-Key':viewer}});
  assert.equal(label.status,200);assert.match(label.headers.get('content-type'),/^image\/svg\+xml/);
  assert.ok((await label.text()).includes(receipt.scan_code));
  await page.evaluate(()=>{window.__finishedGoodsPrinted=false;window.print=()=>{window.__finishedGoodsPrinted=true;};});
  await page.getByRole('button',{name:'Cetak label barang jadi',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.__finishedGoodsPrinted),true);
  await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('.finished-goods-label').isVisible(),true);
  assert.equal(await page.locator('#main').isVisible(),false);
  await page.emulateMedia({media:'screen'});
  await page.getByRole('button',{name:'Tutup dialog',exact:true}).click();
  assert.equal(await page.locator('#finished-goods-scan-view').isVisible(),true);
  assert.equal(await input.inputValue(),receipt.scan_code);
  await page.getByRole('button',{name:'Rincian barang jadi',exact:true}).click();

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-finished-goods-scan-label-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');
  console.log('Finished goods scan browser QA PASS: keyboard scan, QR, print, viewer controls, retry, mobile/200%.');
};
