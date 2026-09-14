const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,viewer,apiGet,work})=>{
  async function role(key){await page.keyboard.press('Escape');await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  await role(admin);

  const unique=Date.now(),requestKey='audit-ui-'+unique;
  const body={sku:'AUDIT-UI-'+unique,name:'CONTOH <audit aman>',color:'Biru',size:'M'};
  for(let attempt=0;attempt<2;attempt++){
    const response=await fetch(process.env.BEELOFT_QA_BASE+'/api/products',{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':requestKey
    },body:JSON.stringify(body)});
    assert.equal(response.status,201,await response.clone().text());
  }
  const exact=await apiGet('/api/audit-events?q='+encodeURIComponent(requestKey));
  assert.equal(exact.total,1);
  assert.equal(exact.items[0].category,'master_data');

  let fail=true;
  await page.route('**/api/audit-events?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Audit trail sedang sibuk'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Audit trail',exact:true}).click();
  await page.getByText('Audit trail sedang sibuk',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  await page.locator('#audit-list .audit-event').first().waitFor();
  await page.unroute('**/api/audit-events?*');

  await page.getByLabel('Cari operasi, referensi, pelaku, atau request key',{exact:true}).fill(body.sku);
  await page.getByLabel('Kategori',{exact:true}).selectOption('master_data');
  await page.getByRole('button',{name:'Terapkan filter',exact:true}).click();
  await page.getByText('1 catatan sesuai filter.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian audit '+body.sku,exact:true}).click();
  await page.getByRole('heading',{name:'Audit · '+body.sku,exact:true}).waitFor();
  assert.ok((await page.locator('.audit-json').first().innerText()).includes('CONTOH <audit aman>'));
  assert.equal(await page.locator('.audit-json').first().locator('script').count(),0);

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-global-audit-trail-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});

  await role(viewer);
  assert.equal(await page.getByRole('button',{name:'Audit trail',exact:true}).isVisible(),false);
  const denied=await fetch(process.env.BEELOFT_QA_BASE+'/api/audit-events',{headers:{'X-API-Key':viewer}});
  assert.equal(denied.status,403);
  console.log('Global audit trail browser QA PASS: exact retry, admin search/detail, escaping, retry, viewer guard, mobile/200%.');
};
