const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(viewer);

  let fail=true;
  await page.route('**/api/command-center',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Command center sedang diperbarui'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Command center',exact:true}).click();
  await page.getByText('Command center sedang diperbarui',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Muat ulang',exact:true}).click();
  await page.getByRole('heading',{name:'Apa yang perlu diputuskan hari ini.',exact:true}).waitFor();
  await page.locator('#command-center-summary dd').first().waitFor();
  await page.locator('[data-command-snapshot="production"]').waitFor();
  await page.locator('[data-command-snapshot="inventory"]').waitFor();
  await page.locator('[data-command-snapshot="sales"]').getByText('Pendapatan kotor',{exact:true}).waitFor();
  await page.locator('[data-command-snapshot="finance"]').getByText('Laba bersih',{exact:true}).waitFor();
  await page.locator('[data-command-snapshot="integrations"]').waitFor();
  assert.ok((await page.locator('[data-command-attention]').count())>0);
  assert.equal((await apiGet('/api/command-center')).status.state,'attention');
  await page.unroute('**/api/command-center');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth));
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-management-command-center-mobile.png'),fullPage:true});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});

  await page.locator('[data-command-snapshot="production"]').getByRole('button',{name:'Buka papan produksi'}).click();
  await page.getByRole('heading',{name:'Yang sedang dikerjakan.',exact:true}).waitFor();
  await page.getByRole('button',{name:'Command center',exact:true}).click();
  await page.locator('[data-command-snapshot="integrations"]').getByRole('button',{name:'Buka kesehatan integrasi'}).click();
  await page.getByRole('heading',{name:'Kesehatan integrasi',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Management command center browser QA PASS: consolidated snapshots, exception queue, retry, viewer, drill-down, mobile/200%.');
};
