const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work,order,pick})=>{
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
  await page.route('**/api/orders/*/marketplace-packs?*',async route=>{
    if(failList){failList=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Daftar pack sedang sibuk'})});}
    else await route.continue();
  });
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Packing',exact:true}).click();
  await page.getByText('Daftar pack sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.getByText('Belum ada pack marketplace untuk order ini.',{exact:true}).waitFor();
  await page.unroute('**/api/orders/*/marketplace-packs?*');await page.keyboard.press('Escape');

  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Picking',exact:true}).click();
  await page.getByRole('button',{name:'Rincian PICK-PACK-SOURCE',exact:true}).click();
  await page.getByRole('button',{name:'Catat pack',exact:true}).click();
  await page.getByLabel('Referensi pack',{exact:true}).fill('PACK-UI-001');
  await page.getByLabel('Jumlah pack',{exact:true}).fill('3');
  await page.getByLabel('Tanggal pack',{exact:true}).fill('2026-09-26');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH paket <siap> menunggu kirim');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/marketplace-picks/*/packs',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pack',exact:true}).waitFor();
  await page.unroute('**/api/marketplace-picks/*/packs');
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-marketplace-pack-mobile.png')});

  const packs=await apiGet('/api/orders/'+order.id+'/marketplace-packs');
  assert.equal(packs.length,1);const pack=packs[0];
  assert.equal(pack.reference,'PACK-UI-001');assert.equal(pack.pick_id,pick.id);
  let inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.picked_quantity,inventory.packed_quantity,
    inventory.reserved_quantity,inventory.available_quantity,inventory.hold_quantity,inventory.total_quantity],
    [8,1,3,2,6,8,20]);
  const locations=await apiGet('/api/warehouse-inventory');
  assert.equal(locations.find(row=>row.sku==='FG-M'&&row.stock_status==='picked').location,'Meja Packing B');
  assert.equal(locations.find(row=>row.sku==='FG-M'&&row.stock_status==='packed').location,'Meja Packing B');
  await post('/api/marketplace-picks/'+pick.id+'/reverse',{reason:'Pack aktif harus dikoreksi dahulu'},'pack-block-pick',409);

  await role(viewer);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Packing',exact:true}).click();
  await page.getByRole('button',{name:'Rincian PACK-UI-001',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Koreksi pack',exact:true}).count(),0);

  await role(admin);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Packing',exact:true}).click();
  await page.getByRole('button',{name:'Rincian PACK-UI-001',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi pack',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH jumlah paket salah');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian pack',exact:true}).waitFor();
  await page.getByText('Pack dikoreksi',{exact:true}).waitFor();
  inventory=(await apiGet('/api/finished-goods-inventory')).find(row=>row.sku==='FG-M');
  assert.deepEqual([inventory.sellable_quantity,inventory.picked_quantity,inventory.packed_quantity,
    inventory.reserved_quantity,inventory.available_quantity],[8,4,0,2,6]);

  const shipSource=await post('/api/marketplace-picks/'+pick.id+'/packs',{
    reference:'PACK-SHIP-SOURCE',quantity:3,packed_date:'2026-09-27',reason:'CONTOH sumber pengiriman berikutnya'
  },'pack-ship-source');
  console.log('Marketplace packing browser QA PASS: packed inventory, partial pack, retry, roles, pick guard, correction, mobile/200%.');
  return {pack:shipSource};
};
