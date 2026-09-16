// Regresi P1 di browser sungguhan: pencatatan yang belum pasti tidak boleh diselesaikan setelah
// tab lain menukar session browser ke akun berbeda.
//
// sessionStorage bersifat per tab, sedangkan cookie session dan CSRF dipakai bersama seluruh tab
// pada origin yang sama. Karena itu tab yang masih menyimpan draft pending milik akun A dapat
// mengirim retry memakai session akun B tanpa pernah diberi tahu bahwa akunnya sudah berganti.
//
// Penegakan invarian ada di server dan diuji di tests/test_idempotency_actor.py. Modul ini menguji
// sisi klien: retry lintas akun dihentikan sebelum request terkirim, draft tetap dipertahankan,
// tombol Masuk ulang muncul, dan setelah masuk kembali sebagai akun pencatat asli hasilnya tetap
// satu catatan.
const assert=require('node:assert/strict');

module.exports=async({page,login,admin,operator,apiGet,apiPost})=>{
  const unique=Date.now(),base=new URL(page.url()).origin;
  const reference='XACCT-ORDER-'+unique;
  const product=await apiPost('/api/products',
    {sku:'XACCT-'+unique,name:'CONTOH retry lintas akun',color:'Blue',size:'M'});
  const owner=(await apiGet('/api/users')).find(user=>user.role==='operator');
  const order=await apiPost('/api/orders',{reference,title:'CONTOH - Retry lintas akun '+unique,
    owner_id:owner.id,due_date:'2026-12-31',lines:[{product_id:product.id,quantity:20}]});
  const movements=async()=>(await apiGet('/api/orders/'+order.id+'/movements')).length;

  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(operator);
  await page.getByLabel('Cari order atau SKU',{exact:true}).fill(reference);
  await page.getByRole('button',{name:'Cari order',exact:true}).click();
  await page.getByRole('button',{name:new RegExp(reference)}).click();
  await page.getByRole('heading',{name:'CONTOH - Retry lintas akun '+unique,exact:true}).waitFor();

  // Akun A mengirim perpindahan. Server commit, klien kehilangan responsnya.
  await page.getByRole('button',{name:'Catat perpindahan',exact:true}).first().click();
  await page.getByLabel('Jumlah (pcs)',{exact:true}).fill('7');
  let dropped=false,posts=0;
  await page.route('**/api/movements',async route=>{
    if(route.request().method()==='POST'){
      posts++;
      if(!dropped){dropped=true;await route.fetch();await route.abort('failed');return;}
    }
    await route.continue();
  });
  await page.getByRole('button',{name:'Simpan pencatatan',exact:true}).click();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).waitFor();
  assert.equal(posts,1);
  assert.equal(await movements(),1,'server sudah commit perpindahan pertama');
  const draft=await page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.'))
    .map(key=>[key,JSON.parse(sessionStorage.getItem(key))]));
  assert.equal(draft.length,1);
  assert.equal(draft[0][0],'beeloft.pending.'+draft[0][1].actor_id,'draft harus menyebut akun pencatat');
  assert.equal(draft[0][1].actor_id,owner.id);

  // Tab kedua pada browser yang sama masuk sebagai akun B. Yang benar-benar berubah dari sudut
  // pandang tab pertama hanyalah cookie session dan CSRF yang dipakai bersama seluruh origin, jadi
  // pergantian itu dilakukan dengan login session langsung. Halaman harness dibuat lewat
  // browser.newPage() sehingga context implisitnya tidak mengizinkan tab tambahan, dan state
  // in-memory tab pertama memang harus tetap utuh seperti tab yang tidak pernah diberi tahu.
  await page.evaluate(key=>fetch('/api/session',{method:'POST',credentials:'same-origin',
    cache:'no-store',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({api_key:key})}).then(response=>response.json()),admin);
  const switched=await page.evaluate(()=>fetch('/api/me',{credentials:'same-origin',cache:'no-store'})
    .then(response=>response.json()));
  assert.notEqual(switched.id,owner.id,'session bersama seharusnya sudah milik akun lain');

  // Tab pertama menekan Coba ulang penyimpanan sementara session sudah milik akun B.
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.getByRole('button',{name:'Masuk ulang',exact:true}).waitFor();
  assert.match(await page.locator('#form-error').innerText(),/akun lain/);
  assert.equal(posts,1,'retry lintas akun tidak boleh dikirim ke endpoint mutasi');
  assert.equal(await movements(),1,'tidak boleh ada mutasi kedua');
  const retained=await page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.'))
    .map(key=>JSON.parse(sessionStorage.getItem(key))));
  assert.equal(retained.length,1,'draft harus dipertahankan agar akun asli tetap dapat memulihkan');
  assert.equal(retained[0].transaction.key,draft[0][1].transaction.key);
  assert.equal(retained[0].actor_id,owner.id);

  // Masuk kembali sebagai akun pencatat asli, lalu selesaikan pencatatan yang sama.
  await page.getByRole('button',{name:'Masuk ulang',exact:true}).click();
  await login(operator);
  await page.getByRole('heading',{name:'Konfirmasi pencatatan sebelumnya',exact:true}).waitFor();
  await page.getByRole('button',{name:'Coba ulang penyimpanan',exact:true}).click();
  await page.locator('dialog').waitFor({state:'hidden'});
  assert.equal(posts,2);
  assert.equal(await movements(),1,'replay akun asli tidak boleh menggandakan catatan');
  assert.equal((await apiGet('/api/orders/'+order.id)).totals.cutting,7);
  assert.equal((await page.evaluate(()=>Object.keys(sessionStorage)
    .filter(key=>key.startsWith('beeloft.pending.')).length)),0,'draft harus dibersihkan');
  await page.unroute('**/api/movements');
  console.log('Cross-account retry browser QA PASS: uncertain draft survives a shared-session switch, '
    +'cross-account retry is refused before dispatch, original actor replays exactly once.');
};
