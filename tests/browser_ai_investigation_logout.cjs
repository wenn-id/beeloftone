// Regresi P2-A pada jalur investigasi AI: kegagalan logout tidak boleh tersembunyi di belakang
// dialog modal, dan ruang kerja hanya boleh dipertahankan bila session masih milik akun yang sama.
//
// Dialog "Tanya Beeloft" adalah <dialog> modal. Ketika logout gagal, banner #session-warning di
// belakangnya memang terlihat tetapi tidak dapat dijangkau maupun ditekan, sehingga pengguna yang
// sedang menatap dialog tidak akan pernah tahu bahwa dirinya belum keluar. Karena itu tombol
// "Masuk ulang" pada dialog AI melaporkan kegagalan ke #ai-message, yaitu tempat yang sedang dilihat.
//
// Cookie session dipakai bersama seluruh tab, jadi hasil /api/me pada logout yang gagal belum tentu
// milik akun yang membuka ruang kerja. Modul ini menguji kedua kemungkinannya:
//   Fase 1 — session masih akun yang sama : ruang kerja dipertahankan, kegagalan tampil di dialog.
//   Fase 2 — session sudah akun lain      : ruang kerja lama dibongkar, sebab tampilannya akan
//                                           bercampur identitas; peringatan menjelaskan perpindahan.
//   Fase 3 — akun asli masuk kembali      : draft dipulihkan dan replay tepat satu kali.
//
// Perbaikan P1 yang dijaga: draft per akun beserta transaction.key bertahan melewati kedua jenis
// kegagalan logout, dan replay tidak menggandakan investigasi maupun event audit.
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
  // Identitas yang benar-benar dipegang session browser ini, bukan yang ditampilkan UI.
  const identity=()=>page.evaluate(()=>fetch('/api/me',{credentials:'same-origin',cache:'no-store'})
    .then(response=>response.ok?response.json():null));
  const drafts=()=>page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.'))
    .map(key=>({key,value:JSON.parse(sessionStorage.getItem(key))})));
  const aiMessage=()=>page.locator('#ai-message').innerText();
  const warning=page.locator('#session-warning');
  const accessKey=page.getByLabel('Kunci akses',{exact:true});
  const reauth=page.getByRole('button',{name:'Masuk ulang',exact:true});
  const retry=page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true});
  const settled=async()=>{
    await page.locator('#main:not([aria-busy])').waitFor();
    assert.equal(await page.locator('#login-view').getAttribute('inert'),null,
      'inert pada layar login harus dipulihkan');
  };

  await page.keyboard.press('Escape');
  await login(operator);

  // --- Investigasi dikirim, server commit, responsnya dijatuhkan -----------
  let dropped=false,refuseOnce=false;const postKeys=[];
  await page.route(INVESTIGATIONS,async route=>{
    if(route.request().method()==='POST'){
      postKeys.push(route.request().headers()['idempotency-key']);
      if(!dropped){dropped=true;await route.fetch();await route.abort('failed');return;}
      // Penolakan sekali untuk memunculkan "Masuk ulang" tanpa mengganti akun apa pun.
      if(refuseOnce){refuseOnce=false;await route.fulfill({status:403,
        contentType:'application/json',body:JSON.stringify({detail:'Snapshot ditolak server.'})});
        return;}
    }
    await route.continue();
  });
  await openSidebarDestination('Tanya Beeloft');
  await page.getByLabel('Pertanyaan bisnis',{exact:true}).fill(question);
  await page.getByRole('button',{name:'Analisis dan simpan',exact:true}).click();
  await retry.waitFor();
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

  // --- Fase 1: logout gagal, session masih milik akun yang SAMA -----------
  refuseOnce=true;
  await retry.click();
  await reauth.waitFor();
  assert.equal(postKeys.length,2);
  assert.match(await aiMessage(),/Snapshot ditolak server/);

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
  assert.match(await warning.innerText(),/akun yang sama/);
  assert.equal(await accessKey.isHidden(),true,
    'logout gagal tidak boleh disamarkan sebagai layar login');
  assert.equal(await meStatus(),200,'session memang belum dicabut');
  assert.equal((await identity()).id,owner.id,'session masih milik akun yang membuka ruang kerja');
  assert.equal(await reauth.isVisible(),true,'tombol Masuk ulang harus tetap dapat dipakai');
  const afterSameAccount=await drafts();
  assert.equal(afterSameAccount.length,1,'draft harus tetap tersimpan setelah logout gagal');
  assert.equal(afterSameAccount[0].value.transaction.key,transactionKey,
    'idempotency key tidak boleh berubah karena alur logout');
  assert.equal(postKeys.length,2,'logout gagal tidak boleh memicu pengiriman ulang');
  assert.equal((await investigations()).length,1);

  // --- Fase 2: session ditukar akun lain, lalu logout gagal lagi ----------
  const switched=await page.evaluate(key=>fetch('/api/session',{method:'POST',
    credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({api_key:key})}).then(response=>response.json()),admin);
  assert.notEqual(switched.id,owner.id,'session bersama seharusnya sudah milik akun lain');
  await retry.click();
  // Tombol "Masuk ulang" sudah terlihat sejak fase 1, jadi yang ditunggu adalah pesan barunya.
  await page.locator('#ai-message').filter({hasText:'akun lain'}).waitFor();
  await reauth.waitFor();
  assert.equal(postKeys.length,2,'retry lintas akun tidak boleh dikirim ke server');
  assert.equal((await investigations()).length,1,'tidak boleh ada investigasi kedua');

  await reauth.click();
  await accessKey.waitFor();
  await settled();
  assert.equal(logoutCalls,2);
  // Ruang kerja akun lama dibongkar seluruhnya, termasuk dialog AI-nya.
  assert.equal(await page.locator('#workspace').isHidden(),true,
    'ruang kerja identitas lama harus ditutup');
  assert.equal(await page.locator('#dialog[open]').count(),0,'dialog AI akun lama harus ditutup');
  assert.equal(await page.locator('#account-name').innerText(),'');
  const message=await warning.innerText();
  assert.match(message,/berpindah ke akun lain/);
  assert.match(message,new RegExp(switched.name));
  assert.match(message,/masih aktif/);
  assert.doesNotMatch(message,/berhasil keluar|sudah keluar/);
  assert.equal(await page.locator('#session-retry').isHidden(),true,
    'mencabut session akun lain bukan langkah berikutnya yang benar');
  assert.equal(await meStatus(),200,'session akun lain memang belum dicabut');
  assert.equal((await identity()).id,switched.id);
  // Draft akun asli tetap utuh walaupun ruang kerjanya dibongkar.
  const afterSwitch=await drafts();
  assert.equal(afterSwitch.length,1,'draft akun asli tidak boleh dibuang');
  assert.equal(afterSwitch[0].key,'beeloft.pending.'+owner.id);
  assert.equal(afterSwitch[0].value.transaction.key,transactionKey);
  assert.equal((await investigations()).length,1);
  await page.unroute(LOGOUT);

  // --- Fase 3: akun asli masuk kembali dan menyelesaikan pencatatan -------
  await login(operator);
  assert.equal(await warning.isHidden(),true,'peringatan harus hilang setelah masuk kembali');
  await page.getByRole('heading',{name:'Konfirmasi pencatatan sebelumnya',exact:true}).waitFor();
  await retry.click();
  // Replay yang berhasil menutup dialog konfirmasi lalu membuka detail investigasi yang tersimpan.
  await page.getByRole('heading',{name:'Investigasi tersimpan',exact:true}).waitFor();
  await page.getByRole('heading',{name:'Jawaban',exact:true}).waitFor();
  assert.equal(postKeys.length,3,'replay harus benar-benar dikirim sekali lagi');
  assert.equal(postKeys[2],transactionKey,'replay harus memakai idempotency key yang sama');
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
  console.log('AI investigation logout browser QA PASS: an uncertain investigation survives a failed '
    +'logout on the same account with the failure reported inside the AI dialog, a switched session '
    +'tears the stale workspace down with an honest explanation instead of keeping a mixed-identity '
    +'view, transaction.key is preserved through both, and the original account replays exactly once '
    +'with no duplicate investigation or audit event.');
};
