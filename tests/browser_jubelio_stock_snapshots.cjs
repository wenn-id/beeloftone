const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const mapping=(await apiGet('/api/product-external-mappings?system=jubelio&status=mapped'))[0];
  const finished=new Date(),started=new Date(finished.getTime()-90000);
  const batch=await apiPost('/api/integrations/jubelio/finished-goods-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    external_cursor:'stock-<cursor-1>',reason:'CONTOH snapshot worker Jubelio',items:[
      {external_id:mapping.external_id,external_sku:mapping.external_sku,sellable_quantity:12,reserved_quantity:2},
      {external_id:'unknown-<id>',external_sku:'UNKNOWN-<SKU>',sellable_quantity:4,reserved_quantity:1}
    ]});
  assert.deepEqual([batch.sync_status,batch.accepted_count,batch.rejected_count],['failed',1,1]);
  await role(viewer);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  await page.getByRole('button',{name:'Rekonsiliasi stok Jubelio',exact:true}).click();
  await page.getByRole('heading',{name:'Rekonsiliasi stok Jubelio',exact:true}).waitFor();
  await page.getByText('Ada data dikarantina',{exact:false}).waitFor();
  await page.getByText(/Beeloft 0 pcs · Jubelio 10 pcs · selisih 10 pcs/).waitFor();
  await page.getByText('UNKNOWN-<SKU> · unknown-<id>',{exact:true}).waitFor();
  assert.equal(await page.locator('sku').count(),0);
  assert.equal(await page.getByRole('button',{name:/Impor|Kirim snapshot|Catat snapshot/}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-jubelio-stock-reconciliation-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Riwayat snapshot',exact:true}).click();
  await page.getByText('Dibaca 2 · diterima 1 · dikarantina 1',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian snapshot',exact:true}).click();
  await page.getByText('stock-<cursor-1>',{exact:false}).waitFor();
  await page.getByText('UNKNOWN-<SKU> · unknown-<id>',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Jubelio stock snapshot browser QA PASS: worker import, quarantine, reconciliation, history, escaping, viewer, mobile/200%.');
};
