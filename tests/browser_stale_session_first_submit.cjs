// Regresi integritas lintas tab: form yang dibuka akun A tidak boleh menghasilkan mutasi milik
// akun B pada submit PERTAMA.
//
// Cookie session dan CSRF dipakai bersama seluruh tab pada satu origin, sedangkan state akun di
// dalam tab hanya ada di memori. Karena itu tab yang membuka form sebagai akun A dapat mengirim
// submit pertamanya memakai session akun B tanpa pernah diberi tahu bahwa akunnya sudah berganti.
// Idempotency key pada submit pertama masih baru, jadi kepemilikan key tidak dapat menolongnya:
// server melihat request yang sah dari akun B.
//
// Perbaikannya adalah binding aktor: klien menyatakan akun yang dipakainya saat menyusun request
// melalui header X-Beeloft-Actor, dan server menolak 403 sebelum mutasi dijalankan bila akun yang
// benar-benar ter-autentikasi berbeda. Modul ini menguji jalur perpindahan produksi dan jalur
// investigasi AI, keduanya pada submit pertama.
const assert=require('node:assert/strict');

module.exports=async({page,login,openSidebarDestination,admin,operator,apiGet,apiPost})=>{
  const unique=Date.now(),reference='STALE-ORDER-'+unique,title='CONTOH - Stale session '+unique;
  const product=await apiPost('/api/products',
    {sku:'STALE-'+unique,name:'CONTOH stale session',color:'Blue',size:'M'});
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await apiPost('/api/orders',{reference,title,owner_id:owner.id,due_date:'2026-12-31',
    lines:[{product_id:product.id,quantity:20}]});

  const movements=()=>apiGet('/api/orders/'+order.id+'/movements');
  const auditFor=async key=>(await apiGet('/api/audit-events?q='+encodeURIComponent(key))).items;
  const switchSession=key=>page.evaluate(value=>fetch('/api/session',{method:'POST',
    credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({api_key:value})}).then(response=>response.json()),key);
  const identity=()=>page.evaluate(()=>fetch('/api/me',{credentials:'same-origin',cache:'no-store'})
    .then(response=>response.json()));

  async function openMoveForm(){
    await page.getByLabel('Cari order atau SKU',{exact:true}).fill(reference);
    await page.getByRole('button',{name:'Cari order',exact:true}).click();
    await page.getByRole('button',{name:new RegExp(reference)}).click();
    await page.getByRole('heading',{name:title,exact:true}).waitFor();
    await page.getByRole('button',{name:'Catat perpindahan',exact:true}).first().click();
    await page.getByLabel('Jumlah (pcs)',{exact:true}).fill('6');
  }

  // --- Perpindahan produksi -------------------------------------------------
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(operator);
  await openMoveForm();

  const moveKeys=[];
  await page.route('**/api/movements',async route=>{
    if(route.request().method()==='POST')moveKeys.push(route.request().headers()['idempotency-key']);
    await route.continue();
  });

  // Tab lain menukar session bersama ke akun B. Form akun A belum pernah disubmit.
  await switchSession(admin);
  assert.notEqual((await identity()).id,owner.id,'session bersama seharusnya sudah milik akun lain');

  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Masuk ulang',exact:true}).waitFor();
  assert.match(await page.locator('#form-error').innerText(),/akun lain/);
  assert.equal((await movements()).length,0,'submit pertama tidak boleh membuat mutasi');
  assert.ok(moveKeys.length>0,'submit pertama seharusnya membawa Idempotency-Key');
  for(const key of moveKeys)
    assert.equal((await auditFor(key)).length,0,'tidak boleh ada event audit untuk submit yang ditolak');

  // Masuk kembali sebagai akun pembuka form, lalu simpan tepat satu kali.
  await page.getByRole('button',{name:'Masuk ulang',exact:true}).click();
  await login(operator);
  assert.equal((await identity()).id,owner.id);
  await openMoveForm();
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  const recorded=await movements();
  assert.equal(recorded.length,1,'setelah masuk ulang, pencatatan harus tersimpan tepat satu kali');
  assert.equal(recorded[0].actor_id,owner.id,'mutasi harus diatribusikan ke akun pembuka form');
  assert.equal(recorded[0].quantity,6);
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.cutting,6);
  await page.unroute('**/api/movements');

  // --- Investigasi AI ------------------------------------------------------
  const question='Stale session '+unique+' apakah stok aman?';
  const investigations=async()=>(await apiGet('/api/ai/investigations?q='
    +encodeURIComponent('Stale session '+unique))).length;
  const aiKeys=[];
  await page.route('**/api/ai/investigations',async route=>{
    if(route.request().method()==='POST')aiKeys.push(route.request().headers()['idempotency-key']);
    await route.continue();
  });
  async function askAi(){
    await openSidebarDestination('Tanya Beeloft');
    await page.getByLabel('Pertanyaan bisnis',{exact:true}).fill(question);
  }
  await askAi();
  await switchSession(admin);
  assert.notEqual((await identity()).id,owner.id);
  await page.getByRole('button',{name:'Analisis dan simpan',exact:true}).click();
  await page.getByRole('button',{name:'Masuk ulang',exact:true}).waitFor();
  assert.match(await page.locator('#ai-message').innerText(),/akun lain/);
  assert.equal(await investigations(),0,'investigasi tidak boleh tersimpan oleh akun lain');
  for(const key of aiKeys)
    assert.equal((await auditFor(key)).length,0,'tidak boleh ada event audit untuk investigasi ditolak');

  await page.getByRole('button',{name:'Masuk ulang',exact:true}).click();
  await login(operator);
  await askAi();
  await page.getByRole('button',{name:'Analisis dan simpan',exact:true}).click();
  await page.getByRole('heading',{name:'Jawaban',exact:true}).waitFor();
  assert.equal(await investigations(),1,'investigasi harus tersimpan tepat satu kali');
  await page.keyboard.press('Escape');
  await page.unroute('**/api/ai/investigations');
  console.log('Stale session first submit browser QA PASS: form opened by one account cannot be '
    +'dispatched under a replaced shared session, no mutation and no audit event, and the original '
    +'account still saves exactly once.');
};
