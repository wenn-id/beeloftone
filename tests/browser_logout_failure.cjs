// Regresi P2-A di browser sungguhan: UI tidak boleh mengaku sudah keluar ketika pencabutan session
// belum terkonfirmasi.
//
// Sebelumnya `logout()` menelan setiap kegagalan lalu tetap membersihkan ruang kerja pada blok
// finally. Layar login muncul seolah logout berhasil, padahal baris session di server masih hidup
// dan cookie belum dihapus, sehingga reload membuka kembali akun sebelumnya.
//
// Modul ini menguji keadaan session yang sebenarnya, bukan hanya tampilannya: setiap langkah
// memeriksa `/api/me` dari dalam halaman, jadi klaim UI selalu diperiksa terhadap kebenaran server.
// Perbedaan penting yang benar-benar dibedakan di sini:
//   * fulfill 5xx / 403        -> request tidak pernah mencapai server, session pasti masih hidup.
//   * abort tanpa fetch        -> request gagal sebelum terkirim.
//   * fetch() lalu abort       -> server benar-benar memproses, hanya responsnya yang dijatuhkan.
const assert=require('node:assert/strict');

module.exports=async({page,login,admin,operator,apiGet,apiPost})=>{
  const LOGOUT='**/api/session/logout';
  const warning=page.locator('#session-warning');
  const accessKey=page.getByLabel('Kunci akses',{exact:true});
  const keluar=page.getByRole('button',{name:'Keluar',exact:true});
  const workspace=page.locator('#workspace');
  // Kebenaran server untuk session milik tab ini, bukan status yang diklaim UI.
  const meStatus=()=>page.evaluate(()=>fetch('/api/me',{credentials:'same-origin',cache:'no-store'})
    .then(response=>response.status));
  const settled=async()=>{
    await page.locator('#main:not([aria-busy])').waitFor();
    assert.equal(await page.locator('#login-view').getAttribute('inert'),null,
      'inert pada layar login harus dipulihkan');
  };

  await page.keyboard.press('Escape');

  // 1. Logout normal tetap berhasil, session benar-benar dicabut, dan reload tetap logged out.
  await login(admin);
  await keluar.click();
  await accessKey.waitFor();
  await settled();
  assert.equal(await meStatus(),401,'logout sukses harus benar-benar mencabut session');
  assert.equal(await warning.isHidden(),true,'logout sukses tidak boleh memunculkan peringatan');
  await page.reload();
  await settled();
  await accessKey.waitFor();
  assert.equal(await workspace.isHidden(),true,'reload setelah logout sukses harus tetap logged out');

  // 2. Server menjawab 5xx sebelum pencabutan: UI tidak boleh mengaku logout sukses.
  await login(admin);
  let calls=0;
  await page.route(LOGOUT,route=>{calls++;return route.fulfill({status:503,
    contentType:'application/json',body:JSON.stringify({detail:'Basis data sedang sibuk.'})});});
  await keluar.click();
  await warning.waitFor();
  await settled();
  assert.equal(calls,1);
  assert.match(await warning.innerText(),/Logout belum berhasil/);
  assert.equal(await workspace.isVisible(),true,'ruang kerja harus dipertahankan dengan peringatan');
  assert.equal(await accessKey.isHidden(),true,'kegagalan tidak boleh disamarkan sebagai layar login');
  assert.equal(await meStatus(),200,'session memang masih aktif');
  // Reload memang membuka kembali akun yang sama. Itulah sebabnya peringatan tadi wajib ada.
  await page.reload();
  await settled();
  assert.equal(await workspace.isVisible(),true,'akun masih terbuka: peringatan sebelumnya benar');

  // 3. Retry setelah kegagalan harus berhasil.
  await page.unroute(LOGOUT);
  await keluar.click();
  await accessKey.waitFor();
  await settled();
  assert.equal(await meStatus(),401,'retry logout harus mencabut session');

  // 4. CSRF ditolak: 403 bukan bukti bahwa session sudah berakhir.
  await login(admin);
  await page.route(LOGOUT,route=>route.fulfill({status:403,contentType:'application/json',
    body:JSON.stringify({detail:'Token keamanan browser tidak valid.'})}));
  await keluar.click();
  await warning.waitFor();
  await settled();
  assert.match(await warning.innerText(),/Logout belum berhasil/);
  assert.equal(await accessKey.isHidden(),true,'403 tidak boleh diperlakukan sebagai logout sukses');
  assert.equal(await meStatus(),200,'session masih aktif setelah 403');
  await page.unroute(LOGOUT);

  // 5. Request dibatalkan sebelum mencapai server: kegagalan harus dinyatakan.
  await page.route(LOGOUT,route=>route.abort('failed'));
  await keluar.click();
  await warning.waitFor();
  await settled();
  assert.match(await warning.innerText(),/Logout belum berhasil/);
  assert.equal(await meStatus(),200,'session tidak pernah dicabut');

  // 6. Server maupun pemeriksaan status tidak dapat dihubungi: nyatakan belum terkonfirmasi, dan
  //    jangan menjanjikan session sudah dicabut.
  await page.route('**/api/me',route=>route.abort('failed'));
  await keluar.click();
  await page.locator('#session-warning-text').filter({hasText:'belum terkonfirmasi'}).waitFor();
  await settled();
  assert.match(await warning.innerText(),/belum terkonfirmasi/);
  assert.doesNotMatch(await warning.innerText(),/berhasil keluar|sudah keluar/);
  assert.equal(await accessKey.isHidden(),true);
  await page.unroute('**/api/me');
  await page.unroute(LOGOUT);
  assert.equal(await meStatus(),200,'session memang masih hidup selama koneksi terputus');

  // 7. Server sudah mencabut session, lalu responsnya dijatuhkan. Aplikasi harus mengenali bahwa
  //    session sudah tidak aktif dan menyelesaikan alur, bukan terjebak pada error logout.
  let processed=0;
  await page.route(LOGOUT,async route=>{processed++;await route.fetch();await route.abort('failed');});
  await keluar.click();
  await accessKey.waitFor();
  await settled();
  assert.equal(processed,1,'server harus benar-benar memproses pencabutan');
  assert.equal(await warning.isHidden(),true,'hasil yang hilang tidak boleh menjadi error permanen');
  assert.equal(await meStatus(),401,'session sudah tidak aktif, jadi alur logout selesai');
  await page.unroute(LOGOUT);

  // 8. Session sudah berakhir sebelum tombol logout ditekan (misalnya ditutup dari tab lain).
  await login(admin);
  const closedElsewhere=await page.evaluate(()=>{
    const csrf=document.cookie.split('; ').find(row=>row.startsWith('beeloft_csrf='))?.slice(13);
    return fetch('/api/session/logout',{method:'POST',credentials:'same-origin',cache:'no-store',
      headers:{'X-CSRF-Token':decodeURIComponent(csrf||'')}}).then(response=>response.status);
  });
  assert.equal(closedElsewhere,200);
  assert.equal(await meStatus(),401,'session sudah mati sebelum tombol ditekan');
  await keluar.click();
  await accessKey.waitFor();
  await settled();
  assert.equal(await warning.isHidden(),true,'session yang sudah mati harus diarahkan ke login');

  // 9. Klik ganda tidak membuat permintaan berganda dan tidak merusak state authentication.
  await login(admin);
  let posts=0;
  await page.route(LOGOUT,async route=>{posts++;
    await new Promise(resolve=>setTimeout(resolve,600));await route.continue();});
  const inFlight=await page.evaluate(()=>{
    const button=document.getElementById('logout');
    button.click();button.click();button.click();
    return {disabled:button.disabled,busy:document.getElementById('main').getAttribute('aria-busy'),
            loginHidden:document.getElementById('login-view').hidden};
  });
  assert.equal(inFlight.disabled,true,'tombol keluar harus dinonaktifkan selama permintaan berjalan');
  assert.equal(inFlight.busy,'true','aria-busy harus menyala selama permintaan berjalan');
  assert.equal(inFlight.loginHidden,true,'layar login tidak boleh muncul sebelum hasil diketahui');
  await accessKey.waitFor();
  await settled();
  assert.equal(posts,1,'klik ganda tidak boleh mengirim pencabutan berkali-kali');
  assert.equal(await meStatus(),401);
  assert.equal(await page.locator('#logout').isDisabled(),false,'disabled harus dipulihkan');
  await page.unroute(LOGOUT);

  // 10. Draft transaksi yang belum pasti tetap dapat dipulihkan lewat "Masuk ulang", termasuk ketika
  //     percobaan logout pertama gagal. Ini menjaga perbaikan P1: retry memakai idempotency key yang
  //     sama dan tidak menghasilkan mutasi bisnis kedua.
  const unique=Date.now();
  const reference='LOGOUT-ORDER-'+unique;
  const product=await apiPost('/api/products',
    {sku:'LOGOUT-'+unique,name:'CONTOH logout gagal',color:'Blue',size:'M'});
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await apiPost('/api/orders',{reference,title:'CONTOH - Logout gagal '+unique,
    owner_id:owner.id,due_date:'2026-12-31',lines:[{product_id:product.id,quantity:20}]});
  const movements=async()=>(await apiGet('/api/orders/'+order.id+'/movements')).length;

  await login(operator);
  await page.getByLabel('Cari order atau SKU',{exact:true}).fill(reference);
  await page.getByRole('button',{name:'Cari order',exact:true}).click();
  await page.getByRole('button',{name:new RegExp(reference)}).click();
  await page.getByRole('heading',{name:'CONTOH - Logout gagal '+unique,exact:true}).waitFor();
  await page.getByRole('button',{name:'Catat perpindahan',exact:true}).first().click();
  await page.getByLabel('Jumlah (pcs)',{exact:true}).fill('5');
  let dropped=false,movePosts=0;
  await page.route('**/api/movements',async route=>{
    if(route.request().method()==='POST'){
      movePosts++;
      if(!dropped){dropped=true;await route.fetch();await route.abort('failed');return;}
    }
    await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  assert.equal(await movements(),1,'server sudah mencatat perpindahan pertama');
  const draft=await page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.'))
    .map(key=>JSON.parse(sessionStorage.getItem(key))));
  assert.equal(draft.length,1);
  assert.equal(draft[0].actor_id,owner.id);

  // Tab lain menukar session bersama ke akun admin, sehingga retry ditolak 403 dan tombol
  // "Masuk ulang" muncul.
  await page.evaluate(key=>fetch('/api/session',{method:'POST',credentials:'same-origin',
    cache:'no-store',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({api_key:key})}).then(response=>response.json()),admin);
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  const reauth=page.getByRole('button',{name:'Masuk ulang',exact:true});
  await reauth.waitFor();
  assert.match(await page.locator('#form-error').innerText(),/akun lain/);

  // Percobaan logout dari dalam dialog gagal. Karena banner di belakang dialog modal tidak dapat
  // dijangkau, kegagalan harus dilaporkan di dalam dialog itu sendiri.
  await page.route(LOGOUT,route=>route.fulfill({status:500,contentType:'application/json',
    body:JSON.stringify({detail:'Server gagal memproses.'})}));
  await reauth.click();
  await page.locator('#form-error').filter({hasText:'Logout belum berhasil'}).waitFor();
  await settled();
  assert.equal(await accessKey.isHidden(),true,'logout gagal tidak boleh membuka layar login');
  assert.equal(await meStatus(),200,'session bersama masih aktif');
  assert.equal(movePosts,1,'tidak boleh ada percobaan mutasi tambahan');
  assert.equal(await movements(),1);
  const retained=await page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.'))
    .map(key=>JSON.parse(sessionStorage.getItem(key))));
  assert.equal(retained.length,1,'draft harus tetap tersimpan per akun');
  assert.equal(retained[0].transaction.key,draft[0].transaction.key,
    'idempotency key tidak boleh dibuang oleh alur logout');

  // Setelah gangguan berlalu, "Masuk ulang" tetap dapat dipakai.
  await page.unroute(LOGOUT);
  await reauth.click();
  await accessKey.waitFor();
  await settled();
  assert.equal(await meStatus(),401);
  const survived=await page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.')).length);
  assert.equal(survived,1,'logout tidak boleh membuang draft pending');

  // Akun pencatat asli masuk kembali dan menyelesaikan pencatatan yang sama, tepat satu kali.
  await login(operator);
  await page.getByRole('heading',{name:'Konfirmasi pencatatan sebelumnya',exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  assert.equal(movePosts,2);
  assert.equal(await movements(),1,'replay akun asli tidak boleh menggandakan catatan');
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.cutting,5);
  assert.equal(await page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.')).length),0,'draft harus dibersihkan');
  await page.unroute('**/api/movements');

  // Logout terakhir tetap harus benar-benar mencabut session, lalu halaman ditinggalkan dalam
  // keadaan masuk seperti yang diharapkan modul berikutnya.
  await keluar.click();
  await accessKey.waitFor();
  await settled();
  assert.equal(await meStatus(),401);
  await login(admin);
  console.log('Logout failure browser QA PASS: 5xx/403/abort keep the workspace with an honest warning, '
    +'a dropped response after a real revoke still completes, expired sessions route to login, '
    +'double clicks send one revoke, and pending drafts survive the Masuk ulang flow.');
};
