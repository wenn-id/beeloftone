const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const mapping=(await apiGet('/api/product-external-mappings?system=jubelio&status=mapped'))[0];
  const finished=new Date(),started=new Date(finished.getTime()-65000);
  const batch=await apiPost('/api/integrations/jubelio/listing-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    external_cursor:'listings-<cursor-1>',reason:'CONTOH snapshot listing worker Jubelio',listings:[
      {external_listing_id:'accepted-listing-ui',listing_reference:'LIST-<UI-1>',external_id:mapping.external_id,
       external_sku:mapping.external_sku,marketplace:'Shopee <Official>',listing_title:'Luna <Promo>',
       status:'active',listed_price:'125000.50',updated_at:finished.toISOString()},
      {external_listing_id:'unknown-listing-ui',listing_reference:'BAD-<LISTING>',external_id:'unknown-<id>',
       external_sku:'UNKNOWN-<LISTING-SKU>',marketplace:'Tokopedia',listing_title:'Unknown <Listing>',
       status:'blocked',listed_price:'99000',updated_at:finished.toISOString()}
    ]});
  assert.deepEqual([batch.sync_status,batch.accepted_count,batch.rejected_count],['failed',1,1]);
  await role(viewer);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  await page.getByRole('button',{name:'Listing Jubelio',exact:true}).click();
  await page.getByRole('heading',{name:'Listing Jubelio',exact:true}).waitFor();
  await page.getByText('Ada listing dikarantina',{exact:false}).waitFor();
  await page.getByText('Rp125.000,50',{exact:true}).first().waitFor();
  await page.getByText('LIST-<UI-1> · Shopee <Official>',{exact:true}).waitFor();
  await page.getByText('BAD-<LISTING> · Tokopedia',{exact:true}).waitFor();
  await page.getByText('UNKNOWN-<LISTING-SKU> · Unknown <Listing>',{exact:true}).waitFor();
  assert.equal(await page.locator('listing-sku').count(),0);
  assert.equal(await page.getByRole('button',{name:/Impor|Kirim snapshot|Catat snapshot/}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-jubelio-listing-summary-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Riwayat snapshot listing',exact:true}).click();
  await page.getByText('Dibaca 2 · diterima 1 · dikarantina 1',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian snapshot listing',exact:true}).click();
  await page.getByText('listings-<cursor-1>',{exact:false}).waitFor();
  await page.getByText('LIST-<UI-1> · Shopee <Official>',{exact:true}).waitFor();
  await page.getByText('BAD-<LISTING> · Tokopedia',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Jubelio listing snapshot browser QA PASS: quarantine, status and price summary, history, escaping, viewer, mobile/200%.');
};
