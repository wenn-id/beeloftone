const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,apiPost,work,receipt})=>{
  const endpoint='/api/finished-goods-receipts/'+receipt.id+'/traceability';
  const current=await apiGet('/api/finished-goods-receipts/'+receipt.id);
  const hold=current.inventory.find(row=>row.stock_status==='hold');
  for(let index=0;index<52;index++){
    await apiPost('/api/finished-goods-receipts/'+receipt.id+'/stock-counts',{
      reference:'TRACE-COUNT-'+index,scanned_sku:receipt.sku,location:hold.location,
      stock_status:'hold',counted_quantity:hold.quantity,counted_date:'2026-10-01',
      reason:'CONTOH hitung <ulang> & cocok'
    });
  }
  await page.keyboard.press('Escape');await login(viewer);
  await page.getByRole('button',{name:'Scan barang jadi',exact:true}).click();
  await page.getByLabel('Kode barang jadi',{exact:true}).fill(receipt.scan_code);
  await page.getByRole('button',{name:'Buka barang jadi',exact:true}).click();
  await page.getByRole('button',{name:'Jejak stok lengkap',exact:true}).waitFor();
  let failFirst=true,failNext=true;
  await page.route('**/api/finished-goods-receipts/*/traceability?*',async route=>{
    const isNext=route.request().url().includes('before_time');
    if((!isNext&&failFirst)||(isNext&&failNext)){
      if(isNext)failNext=false;else failFirst=false;
      await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Jejak stok sedang sibuk'})});
    }else await route.continue();
  });
  await page.getByRole('button',{name:'Jejak stok lengkap',exact:true}).click();
  await page.getByText('Jejak stok sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.locator('[data-trace-event]').first().waitFor();
  assert.equal(await page.locator('[data-trace-event]').count(),50);
  assert.equal(await page.locator('#finished-goods-trace-events ulang').count(),0);
  await page.getByRole('button',{name:'Muat catatan sebelumnya',exact:true}).click();
  await page.getByText('Jejak stok sedang sibuk',{exact:true}).waitFor();
  assert.equal(await page.locator('[data-trace-event]').count(),50);
  await page.getByRole('button',{name:'Muat catatan sebelumnya',exact:true}).click();
  await page.locator('[data-trace-event="finished_goods_receipt"]').waitFor();
  const report=await apiGet(endpoint);
  assert.equal(await page.locator('[data-trace-event]').count(),report.total);
  assert.equal(await page.getByRole('button',{name:'Muat catatan sebelumnya',exact:true}).isHidden(),true);
  for(const type of ['warehouse_movement','marketplace_pick','marketplace_pack','marketplace_shipment',
    'marketplace_return','finished_goods_adjustment','finished_goods_stock_count_correction']){
    assert.ok(await page.locator('[data-trace-event="'+type+'"]').count(),type);
  }
  assert.equal(await page.getByRole('button',{name:'Koreksi pergerakan',exact:true}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-traceability-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-trace-event="marketplace_shipment"]').first().getByRole('button').click();
  await page.getByRole('heading',{name:'Rincian pengiriman',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await page.unroute('**/api/finished-goods-receipts/*/traceability?*');
  console.log('Finished goods traceability browser QA PASS: scan entry, full lot history, corrections, cursor/retry, viewer, detail links, escaping, mobile/200%.');
};
