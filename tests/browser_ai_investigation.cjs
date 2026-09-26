const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,openSidebarDestination,admin,operator,viewer,apiGet,work})=>{
  async function role(key){
    await page.keyboard.press('Escape');
    await page.getByRole('button',{name:'Keluar',exact:true}).click();
    await login(key);
  }
  // Milestone D: parameter ai-view memakai label yang sama dengan form analytics di
  // analytics-view, dan getByLabel menyentuh seluruh DOM termasuk section tersembunyi,
  // jadi setiap lookup parameter dibatasi pada form ini.
  const aiForm=page.locator('#ai-form');

  const beforeOrders=(await apiGet('/api/orders')).length;
  const beforeRequests=(await apiGet('/api/purchase-requests')).length;
  await role(viewer);
  await openSidebarDestination('Tanya Beeloft');
  await page.getByRole('button',{name:'Risiko stockout',exact:true}).click();
  assert.equal(await page.getByLabel('Pertanyaan bisnis',{exact:true}).inputValue(),'SKU apa yang berisiko stockout?');
  await page.getByLabel('Pertanyaan bisnis',{exact:true}).fill('Apakah stok COST-UI <aman> atau akan stockout?');
  await page.getByText('Asumsi analisis',{exact:true}).click();
  await aiForm.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-12-13');
  await aiForm.getByLabel('Panjang window demand (hari)',{exact:true}).fill('7');
  await aiForm.getByLabel('Lead time replenishment (hari)',{exact:true}).fill('14');
  await aiForm.getByLabel('Periode review stok (hari)',{exact:true}).fill('30');
  await aiForm.getByLabel('Safety stock (hari)',{exact:true}).fill('7');
  await aiForm.getByLabel('Kelipatan batch produksi (pcs)',{exact:true}).fill('5');
  let lostInvestigation=true;const investigationKeys=[];
  await page.route('**/api/ai/investigations',async route=>{
    investigationKeys.push(route.request().headers()['idempotency-key']);
    if(lostInvestigation){lostInvestigation=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Analisis dan simpan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  assert.equal(await page.getByLabel('Pertanyaan bisnis',{exact:true}).inputValue(),'Apakah stok COST-UI <aman> atau akan stockout?');
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Jawaban',exact:true}).waitFor();
  // Milestone D: hasil dan riwayat investigasi kini berbagi satu halaman, dan teks jawaban
  // muncul di keduanya, jadi klaim hasil dibatasi pada area hasil.
  const aiResults=page.locator('#ai-results');
  await aiResults.getByText('20 pcs direkomendasikan untuk produksi.',{exact:false}).waitFor();
  await aiResults.getByText('Analisis lokal · tidak mengirim data keluar · hanya baca · fokus COST-UI',{exact:true}).waitFor();
  assert.ok(investigationKeys[0]);
  assert.equal(new Set(investigationKeys).size,1);
  // A6.5: the answer surface is `.investigation-answer`; the escaping claim moves with it.
  assert.equal(await page.locator('.investigation-answer').count(),1);
  assert.equal(await page.locator('.investigation-answer aman').count(),0);
  assert.equal(await page.getByRole('button',{name:'Ajukan untuk approval',exact:true}).count(),0);
  assert.ok(await page.locator('[data-ai-recommendation="create_production_order"]').getByText('Perlu approval',{exact:true}).isVisible());
  assert.ok(await page.locator('[data-ai-recommendation="create_purchase_request"]').getByText('Belum dijalankan',{exact:false}).isVisible());
  assert.equal((await apiGet('/api/orders')).length,beforeOrders);
  assert.equal((await apiGet('/api/purchase-requests')).length,beforeRequests);
  const viewerInvestigation=(await apiGet('/api/ai/investigations')).find(row=>row.question.includes('<aman>'));
  assert.ok(viewerInvestigation);
  await page.unroute('**/api/ai/investigations');

  await page.getByRole('button',{name:'Jawaban membantu',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('Angka dan sumber membantu keputusan <stok>');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Investigasi tersimpan',exact:true}).waitFor();
  await page.getByText('1 membantu · 0 perlu diperbaiki · 1 responden',{exact:true}).waitFor();
  assert.equal(await page.locator('stok').count(),0);

  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-ai-investigation-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');
  await page.locator('dialog').waitFor({state:'hidden'});

  await openSidebarDestination('Tanya Beeloft');
  await page.getByRole('button',{name:'Riwayat investigasi',exact:true}).click();
  await page.getByText('Apakah stok COST-UI <aman> atau akan stockout?',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Buka investigasi',exact:true}).click();
  await page.getByText('1 membantu · 0 perlu diperbaiki · 1 responden',{exact:true}).waitFor();

  await role(operator);
  await openSidebarDestination('Tanya Beeloft');
  await page.getByLabel('Pertanyaan bisnis',{exact:true}).fill('Apakah stok COST-UI akan stockout?');
  await page.getByText('Asumsi analisis',{exact:true}).click();
  await aiForm.getByLabel('Data sampai tanggal',{exact:true}).fill('2026-12-13');
  await aiForm.getByLabel('Panjang window demand (hari)',{exact:true}).fill('7');
  await aiForm.getByLabel('Lead time replenishment (hari)',{exact:true}).fill('14');
  await aiForm.getByLabel('Periode review stok (hari)',{exact:true}).fill('30');
  await aiForm.getByLabel('Safety stock (hari)',{exact:true}).fill('7');
  await aiForm.getByLabel('Kelipatan batch produksi (pcs)',{exact:true}).fill('5');
  await page.getByRole('button',{name:'Analisis dan simpan',exact:true}).click();
  const productionRecommendation=page.locator('[data-ai-recommendation="create_production_order"]');
  await productionRecommendation.getByRole('button',{name:'Ajukan untuk approval',exact:true}).click();
  await page.getByLabel('Referensi order',{exact:true}).fill('AI-ACTION-UI');
  await page.getByLabel('Nama order',{exact:true}).fill('Replenishment COST-UI <review>');
  const operatorUser=(await apiGet('/api/users')).find(row=>row.role==='operator');
  await page.locator('select[name="owner_id"]').selectOption(operatorUser.id);
  await page.getByLabel('Target selesai',{exact:true}).fill('2026-12-20');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH rekomendasi stockout sudah diperiksa operator');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  let lost=true;
  await page.route('**/api/ai/action-proposals',async route=>{
    if(route.request().method()==='POST'&&lost){lost=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Proposal tindakan AI',exact:true}).waitFor();
  await page.getByText('AI-ACTION-UI · Menunggu keputusan',{exact:true}).waitFor();
  await page.unroute('**/api/ai/action-proposals');
  assert.equal((await apiGet('/api/orders')).some(row=>row.reference==='AI-ACTION-UI'),false);
  const proposal=(await apiGet('/api/ai/action-proposals')).find(row=>row.reference==='AI-ACTION-UI');
  assert.ok(proposal);
  assert.ok(proposal.investigation_id);
  const sourceInvestigation=await apiGet('/api/ai/investigations/'+proposal.investigation_id);
  assert.equal(sourceInvestigation.linked_actions[0].id,proposal.id);

  await role(viewer);
  await page.locator('#approvals').click();
  await page.locator('#approval-kind').selectOption('ai_action');
  await page.getByRole('button',{name:'Rincian approval AI-ACTION-UI',exact:true}).click();
  assert.equal(await page.locator('[data-ai-action-decision]').count(),0);

  await role(admin);
  await page.locator('#approvals').click();
  await page.locator('#approval-kind').selectOption('ai_action');
  await page.getByRole('button',{name:'Rincian approval AI-ACTION-UI',exact:true}).click();
  await page.getByRole('button',{name:'Setujui dan jalankan',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH kebutuhan produksi dan parameter sudah diverifikasi');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByText('AI-ACTION-UI · Disetujui',{exact:true}).waitFor();
  await page.getByText('Tindakan selesai. Order produksi sudah dibuat.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Buka investigasi asal',exact:true}).click();
  await page.getByText('Tindakan dari investigasi ini',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Buka proposal tindakan',exact:true}).click();
  await page.getByText('AI-ACTION-UI · Disetujui',{exact:true}).waitFor();
  const approved=await apiGet('/api/ai/action-proposals/'+proposal.id);
  const executed=await apiGet('/api/orders/'+approved.executed_entity_id);
  assert.deepEqual([approved.status,approved.executed_entity_type,executed.reference,
    executed.title,executed.target_quantity],['approved','production_order','AI-ACTION-UI',
    'Replenishment COST-UI <review>',20]);
  assert.equal(await page.locator('review').count(),0);
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,
    'beeloft-ai-approved-action-mobile.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:1000});
  await page.keyboard.press('Escape');
  console.log('AI investigation browser QA PASS: persistent snapshot retry, history, feedback, linked proposal, viewer guard, admin execution, escaping, mobile/200%.');
};
