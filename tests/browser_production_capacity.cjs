const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,viewer,apiGet,apiPost,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  const [products,users]=await Promise.all([apiGet('/api/products?limit=500'),apiGet('/api/users')]);
  const product=products.findLast(row=>row.name==='CONTOH <uji teks>');
  const owner=users.find(row=>row.role==='operator'&&row.active);
  assert.ok(product&&owner);
  const unique=Date.now();
  const center=await apiPost('/api/work-centers',{
    code:'CAP-UI-'+unique,name:'Sewing <utama>',stage:'sewing',daily_minutes:10,
    reason:'Browser QA kapasitas produksi'
  });
  await apiPost(`/api/products/${product.id}/routing-standards/sewing`,{
    expected_revision:0,work_center_id:center.id,minutes_per_unit:'10.000',
    reason:'Browser QA standar waktu'
  });
  const due=new Date(Date.now()+5*86400000).toISOString().slice(0,10);
  const order=await apiPost('/api/orders',{
    reference:'CAP-UI-ORDER-'+unique,title:'Kapasitas <uji> '+unique,owner_id:owner.id,due_date:due,
    lines:[{product_id:product.id,quantity:30}]
  });
  const report=await apiGet('/api/capacity-plan?status=all&work_center_id='+encodeURIComponent(center.id));
  assert.equal(report.total,1);
  assert.equal(report.items[0].status,'overloaded');
  assert.ok(report.items[0].orders.some(row=>row.order_id===order.id&&row.at_risk));

  await role(admin);
  await page.getByRole('button',{name:'Kapasitas produksi',exact:true}).click();
  const analytics=page.locator('#analytics-view');
  const dialog=page.locator('dialog');
  const centerMaster=analytics.locator('.product-item').filter({hasText:center.code});
  await centerMaster.getByRole('button',{name:'Ubah',exact:true}).click();
  assert.equal(await dialog.getByLabel('Nama work center',{exact:true}).inputValue(),'Sewing <utama>');
  assert.equal(await dialog.getByLabel('Kapasitas hari kerja (menit)',{exact:true}).inputValue(),'10');
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Kapasitas produksi',exact:true}).click();
  await page.locator('#capacity-standard-product').selectOption(product.id);
  await page.locator('#capacity-standard-stage').selectOption('sewing');
  await analytics.getByRole('button',{name:'Atur standar waktu',exact:true}).click();
  assert.equal(await dialog.getByLabel('Menit per pcs',{exact:true}).inputValue(),'10.000');
  assert.equal(await dialog.locator('select[name="work_center_id"]').inputValue(),center.id);
  await page.keyboard.press('Escape');

  await role(viewer);
  let fail=true;
  await page.route('**/api/capacity-plan?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Kapasitas sedang dihitung ulang'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Kapasitas produksi',exact:true}).click();
  await page.locator('#capacity-plan-message').filter({hasText:'Kapasitas sedang dihitung ulang'}).waitFor();
  await analytics.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const card=page.locator(`[data-capacity-center="${center.id}"]`);
  await card.getByRole('heading',{name:`${center.code} · Sewing <utama>`,exact:true}).waitFor();
  await card.getByRole('heading',{name:`${order.reference} · ${order.title}`,exact:true}).waitFor();
  await card.getByText(product.sku,{exact:false}).waitFor();
  await card.locator('.status-label').getByText('Overload',{exact:true}).waitFor();
  assert.equal(await analytics.getByRole('button',{name:'Tambah work center',exact:true}).count(),0);
  assert.ok((await card.innerText()).includes('30 pcs × 10 menit/pcs = 300 menit'));
  await page.unroute('**/api/capacity-plan?*');

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.getElementById('analytics-view');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await card.scrollIntoViewIfNeeded();
  await analytics.screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-production-capacity-mobile.png')});

  await page.locator('#capacity-plan-form select[name="status"]').selectOption('idle');
  await analytics.getByRole('button',{name:'Hitung kapasitas',exact:true}).click();
  await analytics.getByText('Tidak ada work center yang cocok dengan status dan filter ini.',{exact:true}).waitFor();
  await page.locator('#capacity-plan-form select[name="status"]').selectOption('all');
  await page.locator('#capacity-plan-form select[name="work_center_id"]').selectOption(center.id);
  await analytics.getByRole('button',{name:'Hitung kapasitas',exact:true}).click();
  await card.getByRole('button',{name:'Buka order',exact:true}).click();
  await page.getByRole('heading',{name:order.title,exact:true}).waitFor();
  await page.keyboard.press('Escape');
  console.log('Production capacity browser QA PASS: viewer, retry, overload/deadline risk, escaping, empty state, drill-down, mobile/200%.');
};
