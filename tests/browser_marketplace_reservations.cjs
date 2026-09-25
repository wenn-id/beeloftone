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
    await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Barang jadi',exact:true}).click();
    await page.getByRole('button',{name:'Rincian FG-WH-SOURCE',exact:true}).click();
  }

  await role(operator);await openOrder();
  let failList=true;
  await page.route('**/api/orders/*/marketplace-reservations?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar reservasi sedang sibuk'})});}
    else await route.continue();
  });
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Reservasi jual',exact:true}).click();
  await page.getByText('Daftar reservasi sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada reservasi marketplace untuk order ini.',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/marketplace-reservations?*');await page.keyboard.press('Escape');

  await openReceipt();await page.getByRole('button',{name:'Reservasi marketplace',exact:true}).click();
  await page.getByLabel('Referensi reservasi',{exact:true}).fill('MKT-UI-001');
  await page.getByLabel('Marketplace',{exact:true}).fill('Tokopedia <Official>');
  await page.getByLabel('Referensi order marketplace',{exact:true}).fill('TKP-ORDER-001');
  await page.getByLabel('Jumlah reservasi',{exact:true}).fill('5');
  await page.getByLabel('Tanggal reservasi',{exact:true}).fill('2026-09-20');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH order marketplace dialokasikan');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/finished-goods-receipts/*/marketplace-reservations',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian reservasi marketplace',exact:true}).waitFor();
  await page.unroute('**/api/finished-goods-receipts/*/marketplace-reservations');
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-marketplace-reservation-mobile.png')});
  const reservations=await apiGet('/api/orders/'+order.id+'/marketplace-reservations');
  assert.equal(reservations.length,1);const reservation=reservations[0];
  assert.equal(reservation.reference,'MKT-UI-001');assert.equal(reservation.receipt_id,receipt.id);
  let inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.reserved_quantity,inventory.available_quantity],[12,5,7]);
  await post('/api/finished-goods-receipts/'+receipt.id+'/warehouse-movements',{reference:'WH-RESERVED-BLOCK',
    scanned_code:receipt.sku,kind:'transfer',from_location:'Rak Barang Jadi A',to_location:'Rak Jual',stock_status:'sellable',quantity:8,
    moved_date:'2026-09-21',reason:'Melebihi available'},'market-block-transfer',409);
  await post('/api/finished-goods-receipts/'+receipt.id+'/reverse',{reason:'Masih reserved'},'market-block-receipt',409);
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.warehouse,20);

  await role(viewer);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Reservasi jual',exact:true}).click();
  await page.getByRole('button',{name:'Rincian MKT-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Lepaskan reservasi',exact:true}).count(),0);

  await role(operator);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Reservasi jual',exact:true}).click();
  await page.getByRole('button',{name:'Rincian MKT-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Lepaskan reservasi',exact:true}).click();
  await page.getByLabel('Tanggal pelepasan',{exact:true}).fill('2026-09-21');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH pesanan marketplace batal');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Reservasi dilepaskan',exact:true}).waitFor();
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.reserved_quantity,inventory.available_quantity],[12,0,12]);
  const pickSource=await post('/api/finished-goods-receipts/'+receipt.id+'/marketplace-reservations',{reference:'MKT-PICK-SOURCE',
    marketplace:'Shopee',external_order_reference:'SHP-PICK-001',location:'Rak Barang Jadi A',quantity:6,
    reserved_date:'2026-09-22',reason:'CONTOH sumber pick berikutnya'},'market-pick-source');
  console.log('Marketplace reservation browser QA PASS: available/reserved, channel order, retry, roles, release, stock protection, mobile/200%.');
  return {reservation:pickSource};
};
