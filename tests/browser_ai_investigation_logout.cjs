// Regresi P2-A pada jalur investigasi AI: kegagalan logout tidak boleh tersembunyi di belakang
// dialog modal, dan draft investigasi yang belum pasti tidak boleh hilang karenanya.
//
// Dialog "Tanya Beeloft" adalah <dialog> modal. Ketika logout gagal, banner #session-warning di
// belakangnya memang terlihat tetapi tidak dapat dijangkau maupun ditekan, sehingga pengguna yang
// sedang menatap dialog tidak akan pernah tahu bahwa dirinya belum keluar. Karena itu tombol
// "Masuk ulang" pada dialog AI melaporkan kegagalan ke #ai-message, yaitu tempat yang sedang dilihat.
//
// Rangkaian yang diuji adalah kasus terburuk yang benar-benar mungkin terjadi:
//   1. penyimpanan investigasi dikirim, server commit, responsnya hilang  -> hasil belum pasti;
//   2. tab lain menukar session bersama ke akun lain                      -> retry ditolak 403;
//   3. pengguna menekan "Masuk ulang" tetapi logout gagal sebelum revoke  -> harus dinyatakan;
//   4. setelah gangguan berlalu, logout berhasil dan akun asli masuk lagi -> retry tepat satu kali.
//
// Perbaikan P1 yang dijaga di sini: draft per akun bertahan melewati logout yang gagal maupun yang
// berhasil, transaction.key tidak pernah berubah, dan replay tidak menggandakan investigasi maupun
// event audit.
const assert=require('node:assert/strict');

module.exports=async({page,login,openSidebarDestination,admin,operator,apiGet})=>{
  const LOGOUT='**/api/session/logout';
  const INVESTIGATIONS='**/api/ai/investigations';
  const unique=Date.now();
  // Pertanyaan memuat "approval" dan "menunggu keputusan" supaya intent-nya approvals, jadi snapshot
  // yang tersimpan ikut membuktikan agregat P2-B benar-benar diabadikan pada evidence.
  const question='Antrean approval '+unique+' apa yang menunggu keputusan?';
  const marker='antrean approval '+unique;

  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const investigations=()=>apiGet('/api/ai/investigations?q='+encodeURIComponent(marker));
  const auditFor=async key=>(await apiGet('/api/audit-events?q='+encodeURIComponent(key))).items;
  const meStatus=()=>page.evaluate(()=>fetch('/api/me',{credentials:'same-origin',cache:'no-store'})
    .then(response=>response.status));
  const drafts=()=>page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.'))
    .map(key=>({key,value:JSON.parse(sessionStorage.getItem(key))})));
  const aiMessage=()=>page.locator('#ai-message').innerText();
  const settled=async()=>{
    await page.locator('#main:not([aria-busy])').waitFor();
    assert.equal(await page.locator('#login-view').getAttribute('inert'),null,
      'inert pada layar login harus dipulihkan');
  };

  await page.keyboard.press('Escape');
  await login(operator);

  // --- 1. Investigasi dikirim, server commit, responsnya dijatuhkan ---------
  let dropped=false;const postKeys=[];
  await page.route(INVESTIGATIONS,async route=>{
    if(route.request().method()==='POST'){
      postKeys.push(route.request().headers()['idempotency-key']);
      if(!dropped){dropped=true;await route.fetch();await route.abort('failed');return;}
    }
    await route.continue();
  });
  await openSidebarDestination('Tanya Beeloft');
  await page.getByLabel('Pertanyaan bisnis',{exact:true}).fill(question);
  await page.getByRole('button',{name:'Analisis dan simpan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  assert.equal(postKeys.length,1);
  assert.match(await aiMessage(),/belum terkonfirmasi/);
  const saved=await investigations();
  assert.equal(saved.length,1,'server sudah menyimpan investigasi pertama');
  assert.equal(saved[0].actor_id,owner.id);
  const draft=await drafts();
  assert.equal(draft.length,1);
  assert.equal(draft[0].key,'beeloft.pending.'+owner.id,'draft harus dinamai per akun pencatat');
  assert.equal(draft[0].value.actor_id,owner.id);
  const transactionKey=draft[0].value.transaction.key;
  assert.ok(transactionKey);
  assert.equal(transactionKey,postKeys[0],'draft harus menyimpan idempotency key yang dikirim');
  assert.equal((await auditFor(transactionKey)).length,1,'tepat satu event audit untuk commit pertama');

  // --- 2. Tab lain menukar session bersama, retry ditolak 403 --------------
  await page.evaluate(key=>fetch('/api/session',{method:'POST',credentials:'same-origin',
    cache:'no-store',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({api_key:key})}).then(response=>response.json()),admin);
  assert.equal(await meStatus(),200);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  const reauth=page.getByRole('button',{name:'Masuk ulang',exact:true});
  await reauth.waitFor();
  assert.match(await aiMessage(),/akun lain/);
  assert.equal(postKeys.length,1,'retry lintas akun tidak boleh dikirim ke server');
  assert.equal((await investigations()).length,1,'tidak boleh ada investigasi kedua');

  // --- 3. "Masuk ulang" ditekan, tetapi logout gagal sebelum revoke --------
  let logoutCalls=0;
  await page.route(LOGOUT,route=>{logoutCalls++;return route.fulfill({status:503,
    contentType:'application/json',body:JSON.stringify({detail:'Basis data sedang sibuk.'})});});
  await reauth.click();
  await page.locator('#ai-message').filter({hasText:'Logout belum berhasil'}).waitFor();
  await settled();
  assert.equal(logoutCalls,1);
  // Pesan harus berada di dalam dialog yang sedang dibuka, bukan hanya di banner di belakangnya.
  assert.equal(await page.locator('#dialog[open]').count(),1,'dialog AI harus tetap terbuka');
  assert.equal(await page.locator('#ai-message').isVisible(),true,
    'kegagalan logout harus terbaca di dalam dialog AI');
  assert.match(await aiMessage(),/Logout belum berhasil/);
  assert.equal(await page.getByLabel('Kunci akses',{exact:true}).isHidden(),true,
    'logout gagal tidak boleh disamarkan sebagai layar login');
  assert.equal(await meStatus(),200,'session memang belum dicabut');
  assert.equal(await reauth.isVisible(),true,'tombol Masuk ulang harus tetap dapat dipakai');
  const afterFailure=await drafts();
  assert.equal(afterFailure.length,1,'draft harus tetap tersimpan setelah logout gagal');
  assert.equal(afterFailure[0].value.transaction.key,transactionKey,
    'idempotency key tidak boleh berubah karena alur logout');
  assert.equal(postKeys.length,1,'logout gagal tidak boleh memicu pengiriman ulang');
  assert.equal((await investigations()).length,1);

  // --- 4. Gangguan berlalu: logout berhasil, akun asli masuk lagi ----------
  await page.unroute(LOGOUT);
  await reauth.click();
  await page.getByLabel('Kunci akses',{exact:true}).waitFor();
  await settled();
  assert.equal(await meStatus(),401,'logout kedua harus benar-benar mencabut session');
  const afterLogout=await drafts();
  assert.equal(afterLogout.length,1,'logout tidak boleh membuang draft pending');
  assert.equal(afterLogout[0].value.transaction.key,transactionKey);

  await login(operator);
  await page.getByRole('heading',{name:'Konfirmasi pencatatan sebelumnya',exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  // Replay yang berhasil menutup dialog konfirmasi lalu membuka detail investigasi yang tersimpan.
  await page.getByRole('heading',{name:'Investigasi tersimpan',exact:true}).waitFor();
  await page.getByRole('heading',{name:'Jawaban',exact:true}).waitFor();
  assert.equal(postKeys.length,2,'replay harus benar-benar dikirim sekali lagi');
  assert.equal(postKeys[1],transactionKey,'replay harus memakai idempotency key yang sama');
  const replayed=await investigations();
  assert.equal(replayed.length,1,'replay tidak boleh menggandakan investigasi');
  assert.equal(replayed[0].id,saved[0].id,'replay harus mengembalikan investigasi yang sama');
  assert.equal((await auditFor(transactionKey)).length,1,
    'replay tidak boleh menambah event audit, jadi tidak ada efek samping bisnis kedua');
  assert.equal((await drafts()).length,0,'draft harus dibersihkan setelah hasilnya pasti');

  // Snapshot yang tersimpan harus memuat agregat yang mendasari jawabannya.
  const detail=await apiGet('/api/ai/investigations/'+saved[0].id);
  assert.equal(detail.intent,'approvals');
  const evidence=detail.evidence.approvals;
  assert.equal(typeof evidence.summary.total,'number');
  assert.equal(evidence.sample_size,evidence.sample.length);
  assert.equal(typeof evidence.truncated,'boolean');
  assert.equal(detail.answer,replayed[0].answer,'jawaban yang direplay harus identik dengan snapshot');
  await page.unroute(INVESTIGATIONS);

  // Tinggalkan halaman masuk sebagai admin seperti yang diharapkan modul berikutnya.
  await page.keyboard.press('Escape');
  await page.locator('dialog').waitFor({state:'hidden'});
  await login(admin);
  console.log('AI investigation logout browser QA PASS: an uncertain investigation survives a '
    +'cross-account 403 and a failed logout, the failure is reported inside the AI dialog instead of '
    +'behind the modal, transaction.key is preserved, and the original account replays exactly once '
    +'with no duplicate investigation or audit event.');
};
