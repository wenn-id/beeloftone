const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiPost,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  const finished=new Date(),started=new Date(finished.getTime()-65000);
  const batch=await apiPost('/api/integrations/mekari/finance-snapshots',{
    started_at:started.toISOString(),finished_at:finished.toISOString(),snapshot_at:finished.toISOString(),
    external_cursor:'finance-<cursor-1>',reason:'CONTOH snapshot ringkasan keuangan worker Mekari',periods:[{
      source_report_id:'FIN-<UI-1>',period_start:'2026-09-01',period_end:'2026-09-30',currency:'IDR',
      gross_revenue:'2000000',sales_returns:'200000',cost_of_goods_sold:'800000',
      operating_expenses:'500000',other_income:'100000',other_expenses:'50000',cash_balance:'900000',
      receivables_balance:'300000',payables_balance:'250000'
    }]});
  assert.deepEqual([batch.sync_status,batch.period_count,batch.periods[0].net_profit],['succeeded',1,'550000.00']);
  await role(viewer);
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  await page.getByRole('button',{name:'Keuangan Mekari',exact:true}).click();
  await page.getByRole('heading',{name:'Keuangan Mekari',exact:true}).waitFor();
  await page.getByText('Rp1.800.000,00',{exact:true}).first().waitFor();
  await page.getByText('Rp550.000,00',{exact:true}).first().waitFor();
  await page.getByText('FIN-<UI-1>',{exact:true}).waitFor();
  assert.equal(await page.locator('ui-1').count(),0);
  assert.equal(await page.getByRole('button',{name:/Impor|Kirim snapshot|Catat snapshot|Buat jurnal/}).count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-mekari-finance-summary-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Riwayat snapshot keuangan',exact:true}).click();
  await page.getByText('Dibaca 1 · periode 1',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian snapshot keuangan',exact:true}).click();
  await page.getByText('finance-<cursor-1>',{exact:false}).waitFor();
  await page.getByText('FIN-<UI-1>',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Mekari finance snapshot browser QA PASS: derived management summary, history, escaping, viewer, mobile/200%.');
};
