const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work,order,pack})=>{
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
  await page.route('**/api/orders/*/marketplace-shipments?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar pengiriman sedang sibuk'})});}
    else await route.continue();
  });
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Shipping',exact:true}).click();
  await page.getByText('Daftar pengiriman sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada pengiriman marketplace untuk order ini.',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/marketplace-shipments?*');await page.keyboard.press('Escape');

  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Packing',exact:true}).click();
  await page.getByRole('button',{name:'Rincian PACK-SHIP-SOURCE',exact:true}).click();
  await page.getByRole('button',{name:'Catat pengiriman',exact:true}).click();
  await page.getByLabel('Referensi pengiriman',{exact:true}).fill('SHIP-UI-001');
  await page.getByLabel('Jumlah kirim',{exact:true}).fill('2');
  await page.getByLabel('Carrier',{exact:true}).fill('JNE <REG>');
  await page.getByLabel('Nomor resi',{exact:true}).fill('JNE-UI-001');
  await page.getByLabel('Tanggal kirim',{exact:true}).fill('2026-09-28');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH paket diserahkan ke kurir');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/marketplace-packs/*/shipments',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pengiriman',exact:true}).waitFor();
  await page.unroute('**/api/marketplace-packs/*/shipments');
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-marketplace-shipment-mobile.png')});

  const shipments=await apiGet('/api/orders/'+order.id+'/marketplace-shipments');
  assert.equal(shipments.length,1);const shipment=shipments[0];
  assert.equal(shipment.reference,'SHIP-UI-001');assert.equal(shipment.pack_id,pack.id);
  let inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.picked_quantity,inventory.packed_quantity,
    inventory.shipped_quantity,inventory.reserved_quantity,inventory.available_quantity,
    inventory.hold_quantity,inventory.total_quantity],[8,1,1,2,2,6,8,18]);
  const locations=await apiGet('/api/warehouse-inventory');
  assert.equal(locations.find(row=>row.sku==='FG-M'&&row.stock_status==='packed').quantity,1);
  await post('/api/marketplace-packs/'+pack.id+'/reverse',{reason:'Pengiriman aktif harus dikoreksi dahulu'},
    'shipment-block-pack',409);

  await role(viewer);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Shipping',exact:true}).click();
  await page.getByRole('button',{name:'Rincian SHIP-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi pengiriman',exact:true}).count(),0);

  await role(admin);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Shipping',exact:true}).click();
  await page.getByRole('button',{name:'Rincian SHIP-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi pengiriman',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH serah terima carrier dibatalkan');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pengiriman',exact:true}).waitFor();
  await page.getByText('Pengiriman dikoreksi',{exact:true}).waitFor();
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.picked_quantity,inventory.packed_quantity,
    inventory.shipped_quantity,inventory.reserved_quantity,inventory.available_quantity,
    inventory.total_quantity],[8,1,3,0,2,6,20]);

  const returnSource=await post('/api/marketplace-packs/'+pack.id+'/shipments',{
    reference:'SHIP-RETURN-SOURCE',quantity:2,carrier:'JNE',tracking_number:'JNE-RETURN-001',
    shipped_date:'2026-09-29',reason:'CONTOH sumber retur berikutnya'},'shipment-return-source');
  console.log('Marketplace shipping browser QA PASS: outbound inventory, carrier/resi, partial ship, retry, roles, pack guard, correction, mobile/200%.');
  return {shipment:returnSource};
};
