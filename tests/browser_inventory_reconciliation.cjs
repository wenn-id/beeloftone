const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work,order,receipt})=>{
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
  await page.route('**/api/orders/*/finished-goods-stock-counts?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar stock opname sedang sibuk'})});}
    else await route.continue();
  });
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Stock opname',exact:true}).click();
  await page.getByText('Daftar stock opname sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada stock opname barang jadi untuk order ini.',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/finished-goods-stock-counts?*');await page.keyboard.press('Escape');

  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Barang jadi',exact:true}).click();
  await page.getByRole('button',{name:'Rincian FG-WH-SOURCE',exact:true}).click();
  await page.getByRole('button',{name:'Catat stock opname',exact:true}).click();
  await page.getByLabel('Referensi stock opname',{exact:true}).fill('COUNT-UI-001');
  assert.equal(await page.getByLabel('SKU / barcode',{exact:true}).inputValue(),'FG-M');
  await page.getByLabel('Lokasi stok',{exact:true}).fill('Rak Barang Jadi A');
  await page.getByLabel('Status stok',{exact:true}).selectOption('sellable');
  await page.getByLabel('Jumlah fisik (pcs)',{exact:true}).fill('7');
  await page.getByLabel('Tanggal stock opname',{exact:true}).fill('2026-10-04');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH hitung fisik menemukan selisih satu');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/finished-goods-receipts/*/stock-counts',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian stock opname',exact:true}).waitFor();
  await page.unroute('**/api/finished-goods-receipts/*/stock-counts');
  await page.getByText('Saldo sistem 8 pcs · fisik 7 pcs',{exact:true}).waitFor();
  await page.getByText('Selisih -1 pcs · dihitung 4 Okt 2026',{exact:true}).waitFor();
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-stock-opname-mobile.png')});

  const counts=await apiGet('/api/orders/'+order.id+'/finished-goods-stock-counts');
  assert.equal(counts.length,1);const count=counts[0];
  assert.deepEqual([count.reference,count.receipt_id,count.expected_quantity,count.counted_quantity,count.quantity_delta],
    ['COUNT-UI-001',receipt.id,8,7,-1]);
  assert.ok(count.adjustment_id);
  let inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.available_quantity,inventory.total_quantity],[7,5,19]);
  await post('/api/finished-goods-adjustments/'+count.adjustment_id+'/reverse',
    {reason:'Adjustment stock opname harus dikoreksi dari sumber'},'stock-count-adjustment-blocked',409);

  await role(viewer);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Stock opname',exact:true}).click();
  await page.getByRole('button',{name:'Rincian COUNT-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi stock opname',exact:true}).count(),0);

  await role(admin);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Adjustment',exact:true}).click();
  await page.getByText('Dibuat otomatis dari stock opname.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian COUNT-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi adjustment',exact:true}).count(),0);
  await page.getByRole('button',{name:'Stock opname asal',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi stock opname',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH hitungan fisik diulang dan cocok');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('Stock opname dikoreksi',{exact:true}).waitFor();
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.available_quantity,inventory.total_quantity],[8,6,20]);
  assert.equal((await apiGet('/api/finished-goods-stock-counts/'+count.id)).status,'corrected');
  console.log('Inventory reconciliation browser QA PASS: SKU scan, expected/physical variance, linked adjustment, lost-response retry, roles, correction, mobile/200%.');
};
