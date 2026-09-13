const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const mapping=(await apiGet('/api/product-external-mappings?system=jubelio&status=mapped'))[0];
  const finished=new Date(),started=new Date(finished.getTime()-65000);
  const batch=await apiPost('/api/integrations/jubelio/return-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    external_cursor:'returns-<cursor-1>',reason:'CONTOH snapshot retur worker Jubelio',returns:[
      {external_return_id:'accepted-return-ui',external_return_reference:'RET-<UI-1>',
       external_order_id:'accepted-ui-1',external_order_reference:'ORDER-<UI-1>',marketplace:'Shopee <Official>',
       status:'refunded',updated_at:finished.toISOString(),refund_amount:'120000.50',lines:[{
       external_id:mapping.external_id,external_sku:mapping.external_sku,quantity:1}]},
      {external_return_id:'unknown-return-ui',external_return_reference:'BAD-<RETURN>',
       external_order_id:'unknown-ui-1',external_order_reference:'BAD-<ORDER>',marketplace:'Tokopedia',
       status:'received',updated_at:finished.toISOString(),refund_amount:'0',lines:[{
       external_id:'unknown-<id>',external_sku:'UNKNOWN-<RETURN-SKU>',quantity:2}]}
    ]});
  assert.deepEqual([batch.sync_status,batch.accepted_count,batch.rejected_count],['failed',1,1]);
  await role(viewer);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  await page.getByRole('button',{name:'Retur Jubelio',exact:true}).click();
  await page.getByRole('heading',{name:'Retur Jubelio',exact:true}).waitFor();
  await page.getByText('Ada retur dikarantina',{exact:false}).waitFor();
  await page.getByText('Rp120.000,50',{exact:true}).first().waitFor();
  await page.getByText('RET-<UI-1> · Shopee <Official>',{exact:true}).waitFor();
  await page.getByText('BAD-<RETURN> · Tokopedia',{exact:true}).waitFor();
  await page.getByText('UNKNOWN-<RETURN-SKU> × 2',{exact:true}).waitFor();
  assert.equal(await page.locator('return-sku').count(),0);
  assert.equal(await page.getByRole('button',{name:/Impor|Kirim snapshot|Catat snapshot/}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-jubelio-return-summary-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Riwayat snapshot retur',exact:true}).click();
  await page.getByText('Dibaca 2 · diterima 1 · dikarantina 1',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian snapshot retur',exact:true}).click();
  await page.getByText('returns-<cursor-1>',{exact:false}).waitFor();
  await page.getByText('RET-<UI-1> · Shopee <Official>',{exact:true}).waitFor();
  await page.getByText('BAD-<RETURN> · Tokopedia',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Jubelio return snapshot browser QA PASS: whole-return quarantine, refund summary, history, escaping, viewer, mobile/200%.');
};
