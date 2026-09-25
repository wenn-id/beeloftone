const assert=require('node:assert/strict');
const path=require('node:path');

module.exports=async({page,login,admin,operator,viewer,apiGet,work})=>{
  async function post(url,body,key,expected=201){
    const response=await fetch(process.env.BEELOFT_QA_BASE+url,{method:'POST',headers:{
      'Content-Type':'application/json','X-API-Key':admin,'Idempotency-Key':key
    },body:JSON.stringify(body)});
    assert.equal(response.status,expected,await response.clone().text());return response.json();
  }
  const product=await post('/api/products',{sku:'RWK-M',name:'CONTOH inspeksi ulang',color:'Clay',size:'M'},'rwk-product');
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await post('/api/orders',{reference:'DEMO-REWORK-QC',title:'CONTOH rework dan inspeksi ulang',owner_id:owner.id,
    due_date:'2026-12-01',lines:[{product_id:product.id,quantity:20}]},'rwk-order');
  const line=order.lines[0];
  await post('/api/movements',{line_id:line.id,from_stage:'planned',to_stage:'cutting',quantity:20},'rwk-start');
  const material=await post('/api/materials',{code:'RWK-CLOTH',name:'CONTOH kain inspeksi ulang',unit:'m'},'rwk-material');
  const batch=await post('/api/material-batches',{material_id:material.id,reference:'RWK-BATCH',supplier:'CONTOH pemasok',
    location:'Rak R',received_date:'2026-09-11',quantity:'5',reason:'CONTOH bahan'},'rwk-batch');
  const issue=await post('/api/material-issues',{batch_id:batch.id,order_id:order.id,quantity:'3',reason:'CONTOH bahan inspeksi ulang'},'rwk-issue');
  const run=await post('/api/orders/'+order.id+'/cutting-runs',{reference:'RWK-CUT',issue_id:issue.id,used:'2',waste:'0.25',
    reason:'CONTOH cutting inspeksi ulang',outputs:[{line_id:line.id,quantity:20}]},'rwk-cut');
  const bundle=await post('/api/cutting-runs/'+run.id+'/bundles',{reference:'RWK-BDL',output_movement_id:run.outputs[0].id,
    quantity:20,reason:'CONTOH bundle inspeksi ulang'},'rwk-bundle');
  const job=await post('/api/bundles/'+bundle.id+'/sewing-jobs',{reference:'RWK-SEW',assignment_type:'internal',assignee:'Line Rework <A>',
    quantity_out:20,cost:'100000.00',sent_date:'2026-09-11',reason:'CONTOH sewing inspeksi ulang'},'rwk-sewing');
  await post('/api/sewing-jobs/'+job.id+'/complete',{completed_quantity:20,defect_quantity:0,missing_quantity:0,
    returned_date:'2026-09-15',reason:'CONTOH sewing selesai'},'rwk-sewing-complete');
  const finishing=await post('/api/sewing-jobs/'+job.id+'/finishing-records',{reference:'RWK-FIN',quantity:20,
    thread_trimmed:true,ironed:true,labels_attached:true,hangtags_attached:true,packaged:true,
    completed_date:'2026-09-16',reason:'CONTOH finishing lengkap'},'rwk-finishing');

  async function role(key){await closeDialog();await page.getByRole('button',{name:'Keluar',exact:true}).click();await login(key);}
  async function closeDialog(){
    if(await page.locator('dialog').isVisible()){
      await page.keyboard.press('Escape');
      await page.locator('dialog').waitFor({state:'hidden'});
    }
  }
  async function openOrder(){
    await closeDialog();
    if(await page.locator('#back').isVisible())await page.locator('#back').click();
    await page.getByRole('button',{name:/DEMO-REWORK-QC/}).click();
    await page.getByRole('heading',{name:'CONTOH rework dan inspeksi ulang',exact:true}).waitFor();
  }
  async function openQc(){await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Final QC',exact:true}).click();}
  async function totals(){return (await apiGet('/api/orders/'+order.id)).totals;}
  async function conserved(label){
    const current=await totals();
    const sum=Object.values(current).reduce((total,value)=>total+value,0);
    assert.equal(sum,20,`${label}: order quantity must stay conserved, got ${JSON.stringify(current)}`);
    return current;
  }
  async function openFinalQcRecord(reference){
    await openOrder();await openQc();
    await page.getByRole('button',{name:'Rincian '+reference,exact:true}).click();
    await page.getByRole('heading',{name:'Rincian final QC',exact:true}).waitFor();
  }
  async function completeRework(reference,quantity,completedDate){
    await page.getByRole('button',{name:'Catat selesai rework',exact:true}).click();
    await page.getByLabel('Referensi selesai rework',{exact:true}).fill(reference);
    await page.getByLabel('Jumlah selesai rework (pcs)',{exact:true}).fill(String(quantity));
    await page.getByLabel('Tanggal selesai rework',{exact:true}).fill(completedDate);
    await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH rework '+reference+' selesai dikerjakan');
    await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
    await page.getByRole('heading',{name:'Rincian selesai rework',exact:true}).waitFor();
  }
  async function reinspect(reference,accepted,rework,reject,inspectionDate){
    await page.getByRole('button',{name:'Inspeksi ulang',exact:true}).click();
    await page.getByLabel('Referensi inspeksi ulang',{exact:true}).fill(reference);
    await page.getByLabel('Catatan pengukuran',{exact:true}).fill('Ukuran diperiksa ulang setelah rework');
    await page.getByLabel('Catatan pemeriksaan visual',{exact:true}).fill('Visual diperiksa ulang <aman>');
    await page.getByLabel('Jenis defect',{exact:true}).fill(rework?'Noda sisa':'Tidak ada');
    await page.getByLabel('Sumber penanggung jawab',{exact:true}).fill('Tim rework');
    await page.getByLabel('Disposition',{exact:true}).fill('Lolos setelah rework, sisa kembali ke rework');
    await page.getByLabel('Jumlah diterima',{exact:true}).fill(String(accepted));
    await page.getByLabel('Jumlah rework',{exact:true}).fill(String(rework));
    await page.getByLabel('Jumlah reject',{exact:true}).fill(String(reject));
    await page.getByLabel('Tanggal inspeksi ulang',{exact:true}).fill(inspectionDate);
    await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH inspeksi ulang '+reference);
    await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
    await page.getByRole('heading',{name:'Rincian final QC',exact:true}).waitFor();
  }

  // 1. Inspeksi awal dari finishing: 12 diterima, 8 rework.
  await role(operator);await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Finishing',exact:true}).click();
  await page.getByRole('button',{name:'Rincian RWK-FIN',exact:true}).click();
  await page.getByRole('button',{name:'Catat final QC',exact:true}).click();
  await page.getByLabel('Referensi final QC',{exact:true}).fill('RWK-QC-1');
  await page.getByLabel('Catatan pengukuran',{exact:true}).fill('Lingkar dada sesuai toleransi');
  await page.getByLabel('Catatan pemeriksaan visual',{exact:true}).fill('Delapan pcs perlu perbaikan jahitan');
  await page.getByLabel('Jenis defect',{exact:true}).fill('Jahitan loncat');
  await page.getByLabel('Sumber penanggung jawab',{exact:true}).fill('Sewing internal');
  await page.getByLabel('Disposition',{exact:true}).fill('Delapan pcs masuk rework');
  await page.getByLabel('Jumlah diterima',{exact:true}).fill('12');
  await page.getByLabel('Jumlah rework',{exact:true}).fill('8');
  await page.getByLabel('Jumlah reject',{exact:true}).fill('0');
  await page.getByLabel('Tanggal inspeksi',{exact:true}).fill('2026-09-17');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH inspeksi awal selesai');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian final QC',exact:true}).waitFor();
  await page.getByText('Inspeksi awal',{exact:true}).first().waitFor();
  await page.getByText('Rework selesai 0 pcs · belum selesai 8 pcs',{exact:false}).waitFor();
  assert.deepEqual(await conserved('after initial inspection'),
    {planned:0,cutting:0,sewing:0,finishing:0,qc:0,rework:8,reject:0,warehouse:12});

  // 2. Perpindahan generik rework -> qc tidak tersedia lagi di UI.
  const stages=await apiGet('/api/stages');
  assert.ok(!stages.transitions.some(([from,to])=>from==='rework'&&to==='qc'),
    'generic rework -> qc transition must no longer be advertised');
  await post('/api/movements',{line_id:line.id,from_stage:'rework',to_stage:'qc',quantity:8,
    reason:'CONTOH tanpa lineage'},'rwk-generic-refused',422);
  await openOrder();
  await page.getByRole('button',{name:'Catat perpindahan',exact:true}).first().click();
  const moveSources=await page.locator('#move-source option').evaluateAll(items=>items.map(item=>item.value));
  assert.ok(!moveSources.includes('rework'),'Catat perpindahan must not offer rework as a source');
  // Baris yang sisanya di rework tidak boleh diarahkan ke pembalikan, tetapi ke alur selesai rework.
  await page.getByText('Catat penyelesaiannya dari rincian final QC',{exact:false}).waitFor();
  await closeDialog();
  // Order detail menyediakan pintu masuk langsung ke riwayat selesai rework.
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Selesai rework',exact:true}).click();
  await page.getByRole('heading',{name:'Selesai rework order',exact:true}).waitFor();
  await page.getByText('Belum ada catatan selesai rework untuk order ini',{exact:false}).waitFor();
  await closeDialog();

  // 3. Catat selesai rework dari inspeksi awal, dengan retry setelah respons hilang.
  await openFinalQcRecord('RWK-QC-1');
  await page.getByRole('button',{name:'Catat selesai rework',exact:true}).click();
  await page.getByLabel('Referensi selesai rework',{exact:true}).fill('RWK-DONE-1');
  await page.getByLabel('Jumlah selesai rework (pcs)',{exact:true}).fill('8');
  await page.getByLabel('Tanggal selesai rework',{exact:true}).fill('2026-09-18');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH rework pertama selesai');
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog');return d.scrollWidth<=d.clientWidth;}));
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  let drop=true;
  await page.route('**/api/final-qc-records/*/rework-completions',async route=>{
    if(route.request().method()==='POST'&&drop){drop=false;await route.fetch();await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  await page.reload();await login(operator);await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian selesai rework',exact:true}).waitFor();
  await page.unroute('**/api/final-qc-records/*/rework-completions');
  const completions=await apiGet('/api/orders/'+order.id+'/rework-completions');
  assert.equal(completions.length,1);
  assert.equal(completions[0].reference,'RWK-DONE-1');
  assert.equal(completions[0].quantity,8);
  assert.equal(completions[0].reinspection_remaining_quantity,8);
  assert.deepEqual(await conserved('after first rework completion'),
    {planned:0,cutting:0,sewing:0,finishing:0,qc:8,rework:0,reject:0,warehouse:12});
  await page.locator('dialog').screenshot({path:path.join(process.env.BEELOFT_QA_SCREENSHOTS||work,'beeloft-rework-completion-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});

  // 4. Inspeksi ulang #1: 3 diterima, 5 kembali ke rework.
  await page.getByRole('heading',{name:'Status inspeksi ulang',exact:true}).waitFor();
  await reinspect('RWK-QC-2',3,5,0,'2026-09-19');
  await page.getByText('Inspeksi ulang #1',{exact:true}).first().waitFor();
  await page.getByText('Selesai rework RWK-DONE-1',{exact:false}).waitFor();
  await page.getByText('Inspeksi sebelumnya RWK-QC-1',{exact:false}).waitFor();
  assert.deepEqual(await conserved('after first reinspection'),
    {planned:0,cutting:0,sewing:0,finishing:0,qc:0,rework:5,reject:0,warehouse:15});

  // 5. Siklus kedua: selesai rework lagi lalu inspeksi ulang #2 meloloskan sisanya.
  await completeRework('RWK-DONE-2',5,'2026-09-20');
  assert.deepEqual(await conserved('after second rework completion'),
    {planned:0,cutting:0,sewing:0,finishing:0,qc:5,rework:0,reject:0,warehouse:15});
  await reinspect('RWK-QC-3',5,0,0,'2026-09-21');
  await page.getByText('Inspeksi ulang #2',{exact:true}).first().waitFor();
  assert.deepEqual(await conserved('after second reinspection'),
    {planned:0,cutting:0,sewing:0,finishing:0,qc:0,rework:0,reject:0,warehouse:20});

  // 6. Terima barang jadi langsung dari inspeksi ulang terakhir.
  await page.getByRole('button',{name:'Terima barang jadi',exact:true}).click();
  await page.getByLabel('Referensi penerimaan',{exact:true}).fill('RWK-FG-1');
  assert.equal(await page.getByLabel('SKU / barcode',{exact:true}).inputValue(),'RWK-M');
  await page.getByLabel('Lokasi gudang',{exact:true}).fill('Rak Rework <A>');
  await page.getByLabel('Jumlah sellable',{exact:true}).fill('5');
  await page.getByLabel('Jumlah hold',{exact:true}).fill('0');
  await page.getByLabel('Tanggal diterima',{exact:true}).fill('2026-09-22');
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH hasil inspeksi ulang masuk gudang');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian barang jadi',exact:true}).waitFor();
  const receipts=await apiGet('/api/orders/'+order.id+'/finished-goods-receipts');
  assert.equal(receipts.length,1);
  assert.equal(receipts[0].reference,'RWK-FG-1');
  assert.equal(receipts[0].received_quantity,5);
  assert.deepEqual(await conserved('after finished goods receipt'),
    {planned:0,cutting:0,sewing:0,finishing:0,qc:0,rework:0,reject:0,warehouse:20});

  // 7. Riwayat final QC membedakan inspeksi awal dan setiap inspeksi ulang.
  const records=await apiGet('/api/orders/'+order.id+'/final-qc-records');
  assert.deepEqual(records.map(row=>[row.reference,row.inspection_kind,row.inspection_round]),
    [['RWK-QC-3','reinspection',3],['RWK-QC-2','reinspection',2],['RWK-QC-1','initial',1]]);
  await openOrder();await openQc();
  await page.getByRole('button',{name:'Rincian RWK-QC-1',exact:true}).waitFor();
  const historyText=await page.locator('#final-qc-list').innerText();
  for(const label of ['Inspeksi awal','Inspeksi ulang #1','Inspeksi ulang #2'])
    assert.ok(historyText.includes(label),`Final QC history must show ${label}`);
  await page.getByRole('button',{name:'Riwayat selesai rework order',exact:true}).click();
  await page.getByRole('heading',{name:'Selesai rework order',exact:true}).waitFor();
  await page.getByRole('button',{name:'Rincian RWK-DONE-2',exact:true}).click();
  await page.getByRole('heading',{name:'Rincian selesai rework',exact:true}).waitFor();

  // 8. Lineage lengkap dari inspeksi ulang sampai batch bahan.
  const trace=await apiGet('/api/material-batches/'+batch.id+'/traceability?limit=500');
  const kinds=new Set(trace.events.map(row=>row.event_type));
  for(const kind of ['material_issue','cutting_run','bundle','sewing_job','finishing','final_qc',
                     'rework_completion','final_qc_reinspection','finished_goods_receipt'])
    assert.ok(kinds.has(kind),`traceability must expose ${kind}`);

  // 9. Viewer read-only.
  await role(viewer);await openOrder();await openQc();
  await page.getByRole('button',{name:'Rincian RWK-QC-1',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Catat selesai rework',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Koreksi final QC',exact:true}).count(),0);
  await page.getByRole('button',{name:'Riwayat selesai rework',exact:true}).click();
  await page.getByRole('button',{name:'Rincian RWK-DONE-1',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Inspeksi ulang',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Koreksi selesai rework',exact:true}).count(),0);

  // 10. Koreksi harus dibongkar dari hilir ke hulu.
  await role(admin);
  const completionOne=completions[0];
  const completionTwo=(await apiGet('/api/orders/'+order.id+'/rework-completions'))
    .find(row=>row.reference==='RWK-DONE-2');
  const initial=records.find(row=>row.reference==='RWK-QC-1');
  const second=records.find(row=>row.reference==='RWK-QC-2');
  const third=records.find(row=>row.reference==='RWK-QC-3');
  await post('/api/final-qc-records/'+initial.id+'/reverse',{reason:'CONTOH masih dipakai selesai rework'},'rwk-block-initial',409);
  await post('/api/rework-completions/'+completionOne.id+'/reverse',{reason:'CONTOH masih dipakai inspeksi ulang'},'rwk-block-completion',409);
  await post('/api/finishing-records/'+finishing.id+'/reverse',{reason:'CONTOH masih dipakai final QC'},'rwk-block-finishing',409);
  await post('/api/movements/'+completionOne.movement_id+'/reverse',{reason:'CONTOH koreksi terpisah'},'rwk-block-movement',409);
  await openOrder();
  await page.locator('#detail-content .panel-grid').getByRole('button',{name:'Barang jadi',exact:true}).click();
  await page.getByRole('button',{name:'Rincian RWK-FG-1',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi penerimaan',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH penerimaan salah lokasi');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Penerimaan barang jadi dikoreksi',exact:true}).waitFor();
  await openFinalQcRecord('RWK-QC-3');
  await page.getByRole('button',{name:'Koreksi final QC',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH inspeksi ulang kedua salah catat');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Final QC dikoreksi',exact:true}).waitFor();
  assert.deepEqual(await conserved('after correcting the last reinspection'),
    {planned:0,cutting:0,sewing:0,finishing:0,qc:5,rework:0,reject:0,warehouse:15});
  await openOrder();await openQc();
  await page.getByRole('button',{name:'Riwayat selesai rework order',exact:true}).click();
  await page.getByRole('button',{name:'Rincian RWK-DONE-2',exact:true}).click();
  await page.getByRole('button',{name:'Koreksi selesai rework',exact:true}).click();
  await page.getByLabel('Alasan / catatan',{exact:true}).fill('CONTOH selesai rework kedua salah jumlah');
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('heading',{name:'Selesai rework dikoreksi',exact:true}).waitFor();
  assert.deepEqual(await conserved('after correcting the second rework completion'),
    {planned:0,cutting:0,sewing:0,finishing:0,qc:0,rework:5,reject:0,warehouse:15});
  await post('/api/final-qc-records/'+second.id+'/reverse',{reason:'CONTOH inspeksi ulang pertama salah'},'rwk-reverse-second');
  await post('/api/rework-completions/'+completionTwo.id+'/reverse',{reason:'CONTOH sudah dikoreksi'},'rwk-recompletion',409);
  await post('/api/rework-completions/'+completionOne.id+'/reverse',{reason:'CONTOH selesai rework pertama salah'},'rwk-reverse-completion');
  await post('/api/final-qc-records/'+initial.id+'/reverse',{reason:'CONTOH inspeksi awal salah'},'rwk-reverse-initial');
  const finalTotals=await conserved('after unwinding every correction');
  assert.deepEqual(finalTotals,{planned:0,cutting:0,sewing:0,finishing:0,qc:20,rework:0,reject:0,warehouse:0});
  const source=await apiGet('/api/finishing-records/'+finishing.id);
  assert.deepEqual([source.qc_inspected_quantity,source.qc_remaining_quantity],[0,20]);
  assert.equal(third.inspection_round,3);
  // Riwayat ledger tetap terbaca setelah semua koreksi.
  const history=await apiGet('/api/orders/'+order.id+'/movements?limit=500');
  assert.ok(history.some(row=>row.from_stage==='rework'&&row.to_stage==='qc'&&row.rework_completion_id),
    'historical rework -> qc movements must remain readable with their lineage');
  console.log('Rework reinspection browser QA PASS: finishing → final QC → rework → selesai rework → inspeksi ulang → accepted → barang jadi, repeated cycle, conserved quantities, generic rework return refused, lineage, roles, reverse-order corrections, retry, mobile/200%.');
  return {reworkOrder:order,reworkFinishing:finishing,reworkBatch:batch};
};
