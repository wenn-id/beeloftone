const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work,order,receipt,shipment})=>{
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
  await page.route('**/api/orders/*/marketplace-returns?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar retur sedang sibuk'})});}
    else await route.continue();
  });
  await page.locator('.order-settings').getByRole('button',{name:'Retur',exact:true}).click();
  await page.getByText('Daftar retur sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada retur pelanggan untuk order ini.',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/marketplace-returns?*');await page.keyboard.press('Escape');

  await page.locator('.order-settings').getByRole('button',{name:'Shipping',exact:true}).click();
  await page.getByRole('button',{name:'Rincian SHIP-RETURN-SOURCE',exact:true}).click();
  await page.getByRole('button',{name:'Catat retur',exact:true}).click();
  await page.getByLabel('Referensi retur',{exact:true}).fill('RET-UI-001');
  await page.getByLabel('Jumlah retur',{exact:true}).fill('1');
  await page.getByLabel('Alasan retur',{exact:true}).selectOption('color_mismatch');
  await page.getByLabel('Lokasi penerimaan retur',{exact:true}).fill('Area Retur <UI>');
  await page.getByLabel('Hasil pemeriksaan',{exact:true}).selectOption('hold');
  await page.getByLabel('Tanggal retur diterima',{exact:true}).fill('2026-09-30');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH warna produk tidak sesuai pesanan');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/marketplace-shipments/*/returns',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian retur',exact:true}).waitFor();
  await page.unroute('**/api/marketplace-shipments/*/returns');
  await page.getByText('Warna tidak sesuai',{exact:true}).waitFor();
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-customer-return-mobile.png')});

  const returns=await apiGet('/api/orders/'+order.id+'/marketplace-returns');
  assert.equal(returns.length,1);const returned=returns[0];
  assert.equal(returned.reference,'RET-UI-001');assert.equal(returned.shipment_id,shipment.id);
  let inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.hold_quantity,inventory.shipped_quantity,inventory.returned_quantity,inventory.total_quantity],[9,2,1,19]);
  await post('/api/marketplace-shipments/'+shipment.id+'/reverse',{reason:'Retur aktif masih terhubung'},'return-block-shipment',409);

  await page.keyboard.press('Escape');await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Adjustment',exact:true}).click();
  await page.getByText('Belum ada adjustment barang jadi untuk order ini.',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await page.locator('.order-settings').getByRole('button',{name:'Barang jadi',exact:true}).click();
  await page.getByRole('button',{name:'Rincian FG-WH-SOURCE',exact:true}).click();
  await page.getByRole('button',{name:'Catat adjustment',exact:true}).click();
  await page.getByLabel('Referensi adjustment',{exact:true}).fill('ADJ-UI-001');
  await page.getByLabel('Lokasi stok',{exact:true}).fill('Rak Opname <UI>');
  await page.getByLabel('Status stok',{exact:true}).selectOption('sellable');
  await page.getByLabel('Selisih jumlah (pcs)',{exact:true}).fill('3');
  await page.getByLabel('Tanggal adjustment',{exact:true}).fill('2026-10-01');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH hasil stock opname lebih tiga');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian adjustment',exact:true}).waitFor();
  await page.getByText('Rak Opname <UI> · Sellable',{exact:true}).waitFor();
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-adjustment-mobile.png')});

  const adjustments=await apiGet('/api/orders/'+order.id+'/finished-goods-adjustments');
  assert.equal(adjustments.length,1);const adjustment=adjustments[0];
  assert.equal(adjustment.receipt_id,receipt.id);assert.equal(adjustment.quantity_delta,3);
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.available_quantity,inventory.total_quantity],[11,9,22]);
  const reserved=await post('/api/finished-goods-receipts/'+receipt.id+'/marketplace-reservations',{
    reference:'MKT-ADJ-BLOCK',marketplace:'Shopee',external_order_reference:'SO-ADJ-BLOCK',
    location:'Rak Opname <UI>',quantity:2,reserved_date:'2026-10-02',reason:'CONTOH mengikat hasil opname'
  },'adjustment-reservation');
  await post('/api/finished-goods-adjustments/'+adjustment.id+'/reverse',{reason:'Stok masih reserved'},'adjustment-blocked',409);

  await role(viewer);await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Retur',exact:true}).click();
  await page.getByRole('button',{name:'Rincian RET-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi retur',exact:true}).count(),0);
  await page.getByRole('button',{name:'Semua retur',exact:true}).click();await page.keyboard.press('Escape');
  await page.locator('.order-settings').getByRole('button',{name:'Adjustment',exact:true}).click();
  await page.getByRole('button',{name:'Rincian ADJ-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi adjustment',exact:true}).count(),0);

  await post('/api/marketplace-reservations/'+reserved.id+'/release',{
    released_date:'2026-10-03',reason:'CONTOH melepas stok opname'
  },'adjustment-release');
  await role(admin);await openOrder();
  await page.locator('.order-settings').getByRole('button',{name:'Adjustment',exact:true}).click();
  await page.getByRole('button',{name:'Rincian ADJ-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi adjustment',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH hitungan opname diperbaiki');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('Adjustment dikoreksi',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Semua adjustment',exact:true}).click();await page.keyboard.press('Escape');
  await page.locator('.order-settings').getByRole('button',{name:'Retur',exact:true}).click();
  await page.getByRole('button',{name:'Rincian RET-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi retur',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH paket ternyata bukan retur');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('Retur dikoreksi',{exact:true}).waitFor();
  await post('/api/marketplace-shipments/'+shipment.id+'/reverse',{reason:'CONTOH shipment sumber dibatalkan'},'return-source-reverse');
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.hold_quantity,inventory.packed_quantity,
    inventory.shipped_quantity,inventory.returned_quantity,inventory.total_quantity],[8,8,3,0,0,20]);
  console.log('Returns and adjustments browser QA PASS: inspected return stock, signed adjustment, retry, roles, reservation guards, correction, shipment guard, mobile/200%.');
};
