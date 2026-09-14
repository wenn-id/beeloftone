const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work,order,receipt})=>{
  async function post(url,body,key,expected=201){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,expected,await response.clone().text());return response.json();
  }
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){await page.getByRole('button',{name:/DEMO-FINISHED-GOODS/}).click();await page.getByRole('heading',{name:'CONTOH penerimaan barang jadi',exact:true}).waitFor();}
  async function openReceipt(){
    await page.locator('.order-settings').getByRole('button',{name:'Barang jadi',exact:true}).click();
    await page.getByRole('button',{name:'Rincian FG-WH-SOURCE',exact:true}).click();
  }
  async function fillMovement(reference,target,quantity,date='2026-09-19'){
    await page.getByLabel('SKU / QR lot',{exact:true}).fill(receipt.scan_code.toUpperCase());
    await page.getByLabel('Referensi pergerakan',{exact:true}).fill(reference);
    await page.getByLabel('Lokasi tujuan',{exact:true}).fill(target);
    await page.getByLabel('Jumlah',{exact:true}).fill(String(quantity));
    await page.getByLabel('Tanggal pergerakan',{exact:true}).fill(date);
    await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH stok gudang diperiksa');
  }

  await role(operator);await openOrder();
  let failList=true;
  await page.route('**/api/orders/*/warehouse-movements?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar pergerakan sedang sibuk'})});}
    else await route.continue();
  });
  await page.locator('.order-settings').getByRole('button',{name:'Gudang',exact:true}).click();
  await page.getByText('Daftar pergerakan sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada pergerakan gudang untuk order ini.',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/warehouse-movements?*');await page.keyboard.press('Escape');

  await openReceipt();await page.getByRole('button',{name:'Transfer lokasi',exact:true}).click();
  await page.waitForFunction(()=>document.activeElement?.id==='warehouse-scan-code');
  assert.match(await page.getByLabel('Stok asal',{exact:true}).inputValue(),/^0$/);
  await fillMovement('WH-UI-001','Rak Jual <B>',5);
  await page.getByLabel('SKU / QR lot',{exact:true}).fill('SKU-LAIN');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('SKU atau QR lot hasil scan tidak cocok dengan penerimaan barang jadi.',{exact:true}).waitFor();
  await page.getByLabel('SKU / QR lot',{exact:true}).fill(receipt.scan_code.toUpperCase());
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/finished-goods-receipts/*/warehouse-movements',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pergerakan gudang',exact:true}).waitFor();
  await page.getByText('Validasi scan: '+receipt.scan_code.toUpperCase(),{exact:true}).waitFor();
  await page.unroute('**/api/finished-goods-receipts/*/warehouse-movements');
  const transfer=(await apiGet('/api/orders/'+order.id+'/warehouse-movements'))[0];
  assert.equal(transfer.reference,'WH-UI-001');

  await page.getByRole('button',{name:'Penerimaan asal',exact:true}).click();
  await page.getByRole('button',{name:'Lepaskan hold',exact:true}).click();
  await fillMovement('WH-UI-RELEASE','Rak Jual <B>',3);
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pergerakan gudang',exact:true}).waitFor();
  const release=(await apiGet('/api/orders/'+order.id+'/warehouse-movements'))[0];

  await page.getByRole('button',{name:'Penerimaan asal',exact:true}).click();
  await page.getByRole('button',{name:'Tandai damaged',exact:true}).click();
  await fillMovement('WH-UI-DAMAGE','Area Rusak <C>',2);
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pergerakan gudang',exact:true}).waitFor();
  const damaged=(await apiGet('/api/orders/'+order.id+'/warehouse-movements'))[0];
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-warehouse-movement-mobile.png')});
  let inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.hold_quantity,inventory.damaged_quantity,inventory.total_quantity],[15,3,2,20]);
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.warehouse,20);

  await role(viewer);await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Gudang',exact:true}).click();
  await page.getByRole('button',{name:'Rincian WH-UI-DAMAGE',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi pergerakan',exact:true}).count(),0);

  await role(admin);await openOrder();await openReceipt();
  assert.equal(await page.getByRole('button',{name:'Koreksi penerimaan',exact:true}).count(),0);
  await post('/api/finished-goods-receipts/'+receipt.id+'/reverse',{reason:'Masih memiliki pergerakan'},'wh-block-receipt',409);
  await page.getByRole('button',{name:'Gudang order',exact:true}).click();
  await page.getByRole('button',{name:'Rincian WH-UI-DAMAGE',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi pergerakan',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH keputusan damaged salah');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Pergerakan gudang dikoreksi',exact:true}).waitFor();
  await post('/api/warehouse-movements/'+release.id+'/reverse',{reason:'CONTOH koreksi release'},'wh-reverse-release');
  await post('/api/warehouse-movements/'+transfer.id+'/reverse',{reason:'CONTOH koreksi transfer'},'wh-reverse-transfer');
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.hold_quantity,inventory.damaged_quantity],[12,8,0]);
  console.log('Warehouse browser QA PASS: SKU/lot scan, location transfer, hold release/damage, per-location inventory, retry, roles, correction, dependency, mobile/200%.');
};
