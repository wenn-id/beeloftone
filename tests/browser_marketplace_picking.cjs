const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work,order,reservation})=>{
  async function post(url,body,key,expected=201,apiKey=admin){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':apiKey,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,expected,await response.clone().text());return response.json();
  }
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function openOrder(){await page.getByRole('button',{name:/DEMO-FINISHED-GOODS/}).click();await page.getByRole('heading',{name:'CONTOH penerimaan barang jadi',exact:true}).waitFor();}

  await role(operator);await openOrder();
  let failList=true;
  await page.route('**/api/orders/*/marketplace-picks?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar pick sedang sibuk'})});}
    else await route.continue();
  });
  await page.locator('.order-settings').getByRole('button',{name:'Picking',exact:true}).click();
  await page.getByText('Daftar pick sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada pick marketplace untuk order ini.',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/marketplace-picks?*');await page.keyboard.press('Escape');

  await page.locator('.order-settings').getByRole('button',{name:'Reservasi jual',exact:true}).click();
  await page.getByRole('button',{name:'Rincian MKT-PICK-SOURCE',exact:true}).click();
  await page.getByRole('button',{name:'Catat pick',exact:true}).click();
  const scan=page.getByLabel('SKU / QR lot',{exact:true});
  await page.waitForFunction(()=>document.activeElement?.id==='pick-scan-code');
  assert.equal(await scan.evaluate(element=>element===document.activeElement),true);
  await page.getByLabel('Referensi pick',{exact:true}).fill('PICK-UI-001');
  await scan.fill('SKU-SALAH');
  await page.getByLabel('Jumlah pick',{exact:true}).fill('4');
  await page.getByLabel('Lokasi staging',{exact:true}).fill('Meja Packing <A>');
  await page.getByLabel('Tanggal pick',{exact:true}).fill('2026-09-23');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH barang diambil untuk packing');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('SKU atau QR lot hasil scan tidak cocok dengan reservasi marketplace.',{exact:true}).waitFor();
  await scan.fill(reservation.receipt_scan_code);
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/marketplace-reservations/*/picks',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pick',exact:true}).waitFor();
  await page.unroute('**/api/marketplace-reservations/*/picks');
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-marketplace-pick-mobile.png')});
  const picks=await apiGet('/api/orders/'+order.id+'/marketplace-picks');
  assert.equal(picks.length,1);const pick=picks[0];
  assert.equal(pick.reference,'PICK-UI-001');assert.equal(pick.reservation_id,reservation.id);
  assert.equal(pick.scanned_code,reservation.receipt_scan_code);
  let inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.picked_quantity,inventory.reserved_quantity,
    inventory.available_quantity,inventory.hold_quantity,inventory.total_quantity],[8,4,2,6,8,20]);
  const locations=await apiGet('/api/warehouse-inventory');
  assert.equal(locations.find(row=>row.sku==='FG-M'&&row.stock_status==='picked').location,'Meja Packing <A>');
  await post('/api/marketplace-reservations/'+reservation.id+'/release',{
    released_date:'2026-09-24',reason:'Pick aktif harus dikoreksi dahulu'},'pick-block-release',409,operator);

  await role(viewer);await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Picking',exact:true}).click();
  await page.getByRole('button',{name:'Rincian PICK-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi pick',exact:true}).count(),0);

  await role(admin);await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Picking',exact:true}).click();
  await page.getByRole('button',{name:'Rincian PICK-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi pick',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH lokasi staging salah');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pick',exact:true}).waitFor();
  await page.getByText('Pick dikoreksi',{exact:true}).waitFor();
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.picked_quantity,inventory.reserved_quantity,
    inventory.available_quantity],[12,0,6,6]);
  const packSource=await post('/api/marketplace-reservations/'+reservation.id+'/picks',{
    reference:'PICK-PACK-SOURCE',scanned_code:reservation.sku,quantity:4,staging_location:'Meja Packing B',picked_date:'2026-09-25',
    reason:'CONTOH sumber pack berikutnya'},'pick-pack-source');
  console.log('Marketplace picking browser QA PASS: SKU/lot scan, staging inventory, partial pick, retry, roles, release guard, correction, mobile/200%.');
  return {pick:packSource};
};
