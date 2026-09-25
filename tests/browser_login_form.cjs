// Regresi P2 browser: submit login lokal mengunci tombolnya sendiri, bukan tombol SSO yang
// berada lebih dahulu di form yang sama, dan satu login hanya menghasilkan satu penukaran session.
//
// `querySelector('button')` memilih tombol SSO — termasuk ketika SSO tersembunyi, karena tombol
// itu tetap elemen pertama di dalam form. Tombol submit karena itu tidak pernah dinonaktifkan
// selama request berjalan, sehingga dua submit mengirim dua POST /api/session yang berlomba
// menggantikan cookie session, dan label provider ditimpa menjadi "Buka ruang produksi" secara
// permanen: tidak terlihat ketika SSO disembunyikan, terlihat dan salah ketika SSO aktif.
//
// Modul ini memakai respons login yang tertunda supaya jendela balapan itu benar-benar terbuka,
// dan menguji kedua keadaan yang disebut issue: SSO tersembunyi dan SSO aktif.
//
//   Fase 1 — SSO tersembunyi : tombol submit terkunci selama request, satu request untuk dua klik
//                              dan satu submitRequest() yang disengaja, lalu login berhasil.
//   Fase 2 — SSO aktif       : label provider bertahan sesudah login lokal gagal maupun berhasil,
//                              tombol provider tidak ikut terkunci, dan aksinya tetap ke
//                              /api/sso/login.
const assert=require('node:assert/strict');

module.exports=async({page,login,admin})=>{
  const base=process.env.BEELOFT_QA_BASE;
  const SESSION='**/api/session',SSO='**/api/sso',SSO_LOGIN='**/api/sso/login';
  const provider='Masuk dengan Identitas Beeloft';
  const accessKey=page.getByLabel('Kunci akses',{exact:true});
  const submit=page.locator('#login-form button[type="submit"]');
  const loginError=page.locator('#login-error:not([hidden])');
  const sso=page.locator('#sso-login');
  const board=page.getByRole('heading',{name:'Produksi',exact:true});
  const settled=()=>page.locator('#main:not([aria-busy])').waitFor();

  // Keadaan kelima kontrol dibaca dalam satu perjalanan ke halaman, sehingga yang dibandingkan
  // selalu cuplikan pada momen yang sama, bukan beberapa pembacaan yang berjarak.
  const controls=()=>page.evaluate(()=>{
    const button=document.querySelector('#login-form button[type="submit"]');
    const identity=document.getElementById('sso-login');
    return {disabled:button.disabled,label:button.textContent,
      ssoLabel:identity.textContent,ssoDisabled:identity.disabled,ssoHidden:identity.hidden,
      loginHidden:document.getElementById('login-view').hidden};
  });

  // Menahan POST /api/session pertama di depan server: request sudah dikirim, jawabannya belum
  // ada. Selama itu UI harus sudah mengunci dirinya. Tidak ada respons yang dijatuhkan, jadi
  // cookie session tetap berasal dari server yang sebenarnya.
  function holdLogin(){
    const held={keys:[],waiting:true,release:null,started:null};
    held.gate=new Promise(resolve=>held.release=resolve);
    held.ready=new Promise(resolve=>held.started=resolve);
    held.route=async route=>{
      if(route.request().method()!=='POST'){await route.continue();return;}
      held.keys.push(route.request().postDataJSON().api_key);
      if(held.waiting){held.waiting=false;held.started();await held.gate;}
      await route.continue();
    };
    return held;
  }

  async function loginScreen(){
    await page.keyboard.press('Escape');
    if(await accessKey.isHidden()){
      await page.getByRole('button',{name:'Keluar',exact:true}).click();
      await accessKey.waitFor();
    }
    await settled();
  }

  // --- Fase 1: SSO tersembunyi, respons login tertunda ---------------------
  await loginScreen();
  // Muat ulang dulu supaya modul ini tidak mewarisi label provider dari login modul sebelumnya:
  // yang dibandingkan adalah markup yang benar-benar dikirim server, bukan sisa keadaan lama.
  await page.reload();
  await accessKey.waitFor();
  await settled();
  assert.equal(await sso.isHidden(),true,'server demo tidak mengonfigurasi OIDC');
  assert.deepEqual(await controls(),
    {disabled:false,label:'Buka ruang produksi',ssoLabel:'',ssoDisabled:false,ssoHidden:true,
      loginHidden:false},
    'layar login tanpa SSO harus memulai dari tombol submit yang aktif');

  const first=holdLogin();
  await page.route(SESSION,first.route);
  await accessKey.fill(admin);
  // Dua klik beruntun. Klik kedua mendarat setelah handler sinkron menonaktifkan tombolnya.
  const clicks=await page.evaluate(()=>{
    const button=document.querySelector('#login-form button[type="submit"]');
    button.click();button.click();
    return {disabled:button.disabled,label:button.textContent};
  });
  await first.ready;
  assert.equal(clicks.disabled,true,'tombol submit harus dinonaktifkan selama request berjalan');
  assert.equal(clicks.label,'Memeriksa akses…','hanya tombol submit yang boleh memakai label proses');
  assert.equal((await controls()).ssoLabel,'',
    'tombol SSO yang tersembunyi tidak boleh diberi label tombol submit');

  // requestSubmit() tetap memicu submit event walaupun tombol submit sudah nonaktif — itulah jalur
  // yang guard login-sedang-berjalan harus tutup, jadi kesannya sendiri ikut diperiksa di sini.
  const secondSubmit=await page.evaluate(()=>{
    const form=document.getElementById('login-form');
    let fired=false;
    form.addEventListener('submit',()=>{fired=true;},{once:true});
    form.requestSubmit();
    return fired;
  });
  assert.equal(secondSubmit,true,'submit kedua harus benar-benar terjadi supaya guard diuji');
  await accessKey.press('Enter');
  await page.waitForTimeout(150);
  assert.equal(first.keys.length,1,
    'klik ganda, requestSubmit, dan Enter selama request berjalan hanya boleh mengirim satu login');
  assert.equal((await controls()).disabled,true,'tombol tetap terkunci sampai hasilnya diketahui');
  assert.equal((await controls()).loginHidden,false,'layar login tidak boleh hilang sebelum hasilnya ada');

  first.release();
  await board.waitFor();
  await settled();
  assert.equal(first.keys.length,1,'login yang berhasil tetap satu penukaran session');
  assert.equal(first.keys[0],admin);
  await page.unroute(SESSION,first.route);
  assert.equal((await controls()).label,'Buka ruang produksi',
    'label tombol submit harus dipulihkan setelah request selesai');

  // --- Fase 2: SSO aktif, label dan aksi provider --------------------------
  await loginScreen();
  await page.route(SSO,route=>route.fulfill({status:200,contentType:'application/json',
    body:JSON.stringify({enabled:true,label:'Identitas Beeloft',login_url:'/api/sso/login'})}));
  await page.reload();
  await accessKey.waitFor();
  await settled();
  assert.equal(await sso.isHidden(),false,'provider yang aktif harus terlihat');
  assert.equal(await sso.textContent(),provider);
  assert.equal(await page.locator('#sso-separator').isHidden(),false);

  // Login lokal gagal: tombol provider tidak boleh ikut berubah.
  await accessKey.fill('kunci-akses-salah');
  await submit.click();
  await loginError.waitFor();
  assert.equal(await sso.textContent(),provider,
    'kegagalan login lokal tidak boleh mengganti label provider dengan label tombol submit');
  assert.equal(await sso.isHidden(),false,'tombol provider harus tetap tersedia setelah gagal');
  assert.equal((await controls()).label,'Buka ruang produksi','tombol submit harus pulih setelah gagal');
  assert.equal((await controls()).disabled,false);

  // Login lokal berhasil dengan respons tertunda: tombol provider tidak ikut terkunci.
  const second=holdLogin();
  await page.route(SESSION,second.route);
  await accessKey.fill(admin);
  const inFlight=await page.evaluate(()=>{
    const button=document.querySelector('#login-form button[type="submit"]');
    button.click();
    const identity=document.getElementById('sso-login');
    return {disabled:button.disabled,label:button.textContent,
      ssoDisabled:identity.disabled,ssoLabel:identity.textContent};
  });
  await second.ready;
  assert.equal(inFlight.disabled,true,'tombol submit harus terkunci selama request berjalan');
  assert.equal(inFlight.label,'Memeriksa akses…');
  assert.equal(inFlight.ssoDisabled,false,'tombol SSO bukan tombol yang dikunci alur login lokal');
  assert.equal(inFlight.ssoLabel,provider,'label provider tidak boleh menjadi label proses');

  second.release();
  await board.waitFor();
  await settled();
  assert.equal(second.keys.length,1);
  assert.equal(await sso.textContent(),provider,
    'login lokal yang berhasil tidak boleh menyentuh label provider');
  await page.unroute(SESSION,second.route);

  // Keluar lagi: label provider tetap seperti yang diberikan server, dan aksinya tetap ke
  // /api/sso/login. Navigasinya diperiksa sungguhan, bukan lewat handler yang dibaca dari DOM.
  await loginScreen();
  assert.equal(await sso.textContent(),provider,
    'label provider harus bertahan sampai halaman dimuat ulang');
  await page.route(SSO_LOGIN,route=>route.fulfill({status:200,contentType:'text/html',
    body:'<!doctype html><title>Penyedia identitas</title><p>Penyedia identitas</p>'}));
  await Promise.all([page.waitForURL(url=>url.pathname==='/api/sso/login'),sso.click()]);
  assert.equal(await page.title(),'Penyedia identitas','tombol SSO harus menuju provider, bukan submit lokal');
  await page.unroute(SSO_LOGIN);

  // --- Kembali ke keadaan awal --------------------------------------------
  await page.unroute(SSO);
  await page.goto(base);
  await accessKey.waitFor();
  await settled();
  assert.equal(await sso.isHidden(),true,'tanpa OIDC tombol SSO kembali tersembunyi');
  await login(admin);
  assert.equal((await controls()).loginHidden,true);
  console.log('Login form browser QA PASS: the local submit button alone is locked and labelled '
    +'during a delayed request, a double click plus requestSubmit plus Enter still send exactly one '
    +'session exchange, and the SSO provider button keeps its label and its /api/sso/login action '
    +'through a failed and a successful local login.');
};
