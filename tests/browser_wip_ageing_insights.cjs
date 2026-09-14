const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }

  const overdue=await apiGet('/api/wip-ageing-insights?status=overdue&query=DEMO-PROD-002');
  assert.deepEqual([overdue.total,overdue.summary.overdue_orders,
    overdue.items[0].active_quantity,overdue.items[0].primary_stage],[1,1,300,'cutting']);
  assert.deepEqual(overdue.items[0].positions,[{stage:'planned',quantity:100},
    {stage:'cutting',quantity:200}]);
  assert.ok(overdue.items[0].flags.includes('overdue'));

  const escaped=await apiGet('/api/wip-ageing-insights?status=all&query=DEMO-UI-ORDER-');
  assert.equal(escaped.total,1);
  assert.ok(escaped.items[0].products.some(product=>product.name==='CONTOH <uji teks>'));

  await role(viewer);
  await page.getByRole('button',{name:'WIP ageing',exact:true}).click();
  const dialog=page.locator('dialog');
  await page.locator('#wip-ageing-form select[name="status"]').selectOption('all');
  await dialog.getByLabel('Cari order, PIC, SKU, produk, atau kendala',{exact:true})
    .fill('DEMO-UI-ORDER-');
  let fail=true;
  await page.route('**/api/wip-ageing-insights?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Posisi WIP sedang dihitung ulang'})});}
    else await route.continue();
  });
  await dialog.getByRole('button',{name:'Tampilkan WIP',exact:true}).click();
  await page.locator('#wip-ageing-message').filter({hasText:'Posisi WIP sedang dihitung ulang'}).waitFor();
  await dialog.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const item=page.locator('[data-wip-ageing]');
  await item.getByRole('heading',{name:`${escaped.items[0].reference} · ${escaped.items[0].title}`,
    exact:true}).waitFor();
  await item.getByText('CONTOH <uji teks>',{exact:false}).waitFor();
  await item.getByText('Bergerak',{exact:true}).waitFor();
  assert.ok((await item.innerText()).includes('Belum cutting 50 pcs'));
  await page.unroute('**/api/wip-ageing-insights?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await item.scrollIntoViewIfNeeded();
  await dialog.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-wip-ageing-mobile.png')});
  await page.locator('#wip-ageing-form select[name="stage"]').selectOption('rework');
  await dialog.getByRole('button',{name:'Tampilkan WIP',exact:true}).click();
  await dialog.getByText('Tidak ada order aktif yang cocok dengan status dan filter ini.',
    {exact:true}).waitFor();
  await page.locator('#wip-ageing-form select[name="stage"]').selectOption('all');
  await dialog.getByRole('button',{name:'Tampilkan WIP',exact:true}).click();
  await item.getByRole('button',{name:'Buka order',exact:true}).click();
  await page.getByRole('heading',{name:escaped.items[0].title,exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('WIP ageing browser QA PASS: viewer, retry, current stages, escaping, empty state, order drill-down, mobile/200%.');
};
