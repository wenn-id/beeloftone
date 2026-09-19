const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,viewer,apiPost,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  await role(viewer);
  let fail=true;
  await page.route('**/api/integrations',async route=>{
    if(fail){fail=false;await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({detail:'Status connector belum dapat dimuat'})});}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  await page.getByText('Status connector belum dapat dimuat',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba lagi',exact:true}).click();
  const jubelio=page.locator('[data-integration-system="jubelio"]');
  await jubelio.getByRole('heading',{name:'Jubelio',exact:true}).waitFor();
  await jubelio.locator('[data-integration-scope="orders"]').getByText('Belum pernah sync',{exact:true}).waitFor();
  await jubelio.getByText('Source of truth: Jubelio · inbound read-only',{exact:true}).first().waitFor();
  assert.equal(await page.getByRole('button',{name:/Catat hasil sync/}).count(),0);
  await page.unroute('**/api/integrations');
  await page.keyboard.press('Escape');

  const finished=new Date(),started=new Date(finished.getTime()-120000);
  const common={started_at:started.toISOString(),finished_at:finished.toISOString(),records_read:12,
    records_written:10,external_cursor:'cursor-<12>',reason:'CONTOH worker read-only'};
  await apiPost('/api/integration-sync-runs',{...common,system:'jubelio',scope:'orders',status:'succeeded',error:''});
  const failed=await apiPost('/api/integration-sync-runs',{...common,system:'jubelio',scope:'finished_goods',
    status:'failed',records_written:0,error:'Vendor <timeout> saat membaca stok'});

  await page.getByRole('button',{name:'Integrasi',exact:true}).click();
  const updated=page.locator('[data-integration-system="jubelio"]');
  await updated.getByText('Gagal',{exact:true}).first().waitFor();
  await updated.locator('[data-integration-scope="orders"]').getByText('Sehat',{exact:true}).waitFor();
  await updated.locator('[data-integration-scope="finished_goods"]').getByText('Gagal',{exact:true}).waitFor();
  await updated.getByText('Vendor <timeout> saat membaca stok',{exact:true}).waitFor();
  assert.equal(await page.locator('timeout').count(),0);
  await page.setViewportSize({width:390,height:844});
  // Milestone D: kesehatan integrasi adalah halaman, jadi lebar yang diuik adalah
  // section aktifnya, bukan dialog global yang sudah tidak terbuka.
  const fits=()=>page.evaluate(()=>{const section=document.getElementById('integrations-view');
    return section.scrollWidth<=section.clientWidth
      &&document.documentElement.scrollWidth<=document.documentElement.clientWidth;});
  assert.ok(await fits(),'integrations page must not overflow at 390px');
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await fits(),'integrations page must not overflow at 390px / 200% text');
  await page.locator('#integrations-view').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-integration-health-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});

  await page.locator('button[data-action="integration-runs"]').click();
  await page.getByRole('heading',{name:'Riwayat sinkronisasi',exact:true}).waitFor();
  await page.locator('#integration-run-filter select[name="system"]').selectOption('jubelio');
  await page.locator('#integration-run-filter select[name="status"]').selectOption('failed');
  await page.getByRole('button',{name:'Terapkan filter',exact:true}).click();
  await page.getByText('Vendor <timeout> saat membaca stok',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Buka rincian run',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian sinkronisasi',exact:true}).waitFor();
  await page.getByText('Jubelio · finished_goods · Gagal',{exact:true}).waitFor();
  await page.getByText('cursor-<12>',{exact:false}).waitFor();
  // Milestone D: kesehatan integrasi tetap tampil di halaman di bawah dialog, jadi
  // teks error milik scope juga ada di sana; hitung hanya di dalam dialog rincian.
  assert.equal((await page.locator('dialog').getByText('Vendor <timeout> saat membaca stok',{exact:true}).count()),1);
  assert.ok(failed.id);
  await page.keyboard.press('Escape');
  console.log('Integration browser QA PASS: honest empty state, failure retry, source-of-truth map, health, immutable run detail, escaping, mobile/200%.');
};
