const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,apiPost,work})=>{
  const unique=Date.now(),today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Jakarta'}).format(new Date());
  const absent=await apiPost('/api/workforce/employees',{
    code:'CMD-ABS-'+unique,name:'Sari <Packing>',department:'Packing',reason:'Browser QA Command Center'
  });
  await apiPost(`/api/workforce/employees/${absent.id}/attendance`,{
    work_date:today,expected_revision:0,status:'absent',clock_in:null,clock_out:null,
    overtime_minutes:0,notes:'Sakit',reason:'Browser QA Command Center'
  });
  const missing=await apiPost('/api/workforce/employees',{
    code:'CMD-MISS-'+unique,name:'Dewi <Cutting>',department:'Cutting',reason:'Browser QA Command Center'
  });
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
  await page.locator('[data-command-snapshot="quality"]').getByText('Yield',{exact:true}).waitFor();
  await page.locator('[data-command-snapshot="capacity"]').getByText('Beban 14 hari',{exact:true}).waitFor();
  const people=page.locator('[data-command-snapshot="workforce"]');
  await people.getByText('Belum dicatat',{exact:true}).waitFor();
  assert.ok((await people.innerText()).includes('1 orang'));
  await page.locator('[data-command-snapshot="inventory"]').waitFor();
  await page.locator('[data-command-snapshot="sales"]').getByText('Pendapatan kotor',{exact:true}).waitFor();
  await page.locator('[data-command-snapshot="finance"]').getByText('Laba bersih',{exact:true}).waitFor();
  await page.locator('[data-command-snapshot="integrations"]').waitFor();
  assert.ok((await page.locator('[data-command-attention]').count())>0);
  const attentionPanel=page.locator('.attention-panel');
  const snapshotPanel=page.locator('.snapshot-panel');
  await attentionPanel.waitFor();await snapshotPanel.waitFor();
  const attentionBox=await attentionPanel.boundingBox(),snapshotBox=await snapshotPanel.boundingBox();
  assert.ok(attentionBox.width>snapshotBox.width,'Decision queue must remain the desktop focal point');
  assert.equal(await page.getByRole('button',{name:'Command center',exact:true}).getAttribute('aria-current'),'page');
  await page.locator('[data-command-attention="production-capacity-risk"]')
    .getByRole('heading',{name:'Kapasitas produksi berisiko',exact:true}).waitFor();
  await page.locator('[data-command-attention="production-capacity-coverage"]')
    .getByRole('heading',{name:'Standar kapasitas belum lengkap',exact:true}).waitFor();
  await page.locator('[data-command-attention="workforce-incomplete"]')
    .getByRole('heading',{name:'Kehadiran belum lengkap',exact:true}).waitFor();
  await page.locator('[data-command-attention="workforce-absence"]')
    .getByRole('heading',{name:'Karyawan absen hari ini',exact:true}).waitFor();
  assert.equal((await apiGet('/api/command-center')).status.state,'attention');
  await page.unroute('**/api/command-center');
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'command-center-desktop.png'),fullPage:true});

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth));
  const menu=page.getByRole('button',{name:'Menu',exact:true});
  await menu.click();assert.equal(await menu.getAttribute('aria-expanded'),'true');
  assert.equal(await page.locator('#app-sidebar').isVisible(),true);
  await page.locator('#app-sidebar .nav-item').first().focus();
  await page.keyboard.press('Escape');assert.equal(await menu.getAttribute('aria-expanded'),'false');
  assert.equal(await menu.evaluate(element=>element===document.activeElement),true);
  assert.equal(await page.locator('#app-sidebar').isVisible(),false);
  await menu.click();await page.getByRole('button',{name:'People',exact:true}).click();
  await page.locator('dialog[open]').waitFor();await page.keyboard.press('Escape');
  await page.locator('dialog').waitFor({state:'hidden'});
  assert.equal(await menu.evaluate(element=>element===document.activeElement),true);
  assert.equal(await page.locator('#command-center').getAttribute('aria-current'),'page');
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'command-center-mobile.png'),fullPage:true});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth));
  await page.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'command-center-200-text.png'),fullPage:true});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});

  await page.locator('[data-command-attention="workforce-incomplete"]')
    .getByRole('button',{name:'Buka roster People',exact:true}).click();
  const peopleDialog=page.locator('dialog');
  await peopleDialog.locator(`[data-workforce-employee="${missing.id}"]`)
    .getByText('Belum dicatat',{exact:true}).waitFor();
  await peopleDialog.locator(`[data-workforce-employee="${absent.id}"]`)
    .getByText('Absen',{exact:true}).waitFor();
  assert.equal(await peopleDialog.getByRole('button',{name:/Catat kehadiran|Koreksi kehadiran/}).count(),0);
  await page.keyboard.press('Escape');

  await page.locator('[data-command-attention="production-capacity-risk"]')
    .getByRole('button',{name:'Buka rencana kapasitas',exact:true}).click();
  const capacityDialog=page.locator('dialog');
  await capacityDialog.getByRole('heading',{name:'Kapasitas produksi',exact:true}).waitFor();
  await capacityDialog.locator('[data-capacity-center]').filter({hasText:'Overload'}).first().waitFor();
  await page.keyboard.press('Escape');

  await page.locator('[data-command-snapshot="production"]').getByRole('button',{name:'Buka papan produksi'}).click();
  await page.getByRole('heading',{name:'Yang sedang dikerjakan.',exact:true}).waitFor();
  await page.getByRole('button',{name:'Command center',exact:true}).click();
  await page.locator('[data-command-snapshot="integrations"]').getByRole('button',{name:'Buka kesehatan integrasi'}).click();
  await page.getByRole('heading',{name:'Kesehatan integrasi',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Management command center browser QA PASS: consolidated snapshots, exception queue, retry, viewer, drill-down, mobile/200%.');
};
