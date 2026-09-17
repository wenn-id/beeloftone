import assert from 'node:assert/strict';
import {Api, escapeHTML, displayDate} from '../beeloft/static/client.mjs';

assert.equal(escapeHTML('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
assert.equal(displayDate('2026-09-30').includes('30'), true);
const requests = [];
const api = new Api(async (path, options) => {
  requests.push({path, options});
  if (requests.length === 1) throw new TypeError('Network failed after server commit');
  return new Response(JSON.stringify({id: 'saved-once'}), {status: 201});
});
api.key = 'test-only-key';
const transaction = api.transaction('/api/movements', {quantity: 20});
await assert.rejects(api.save(transaction), error => error.uncertain === true);
assert.deepEqual(await api.save(transaction), {id: 'saved-once'});
assert.equal(requests[0].options.headers['Idempotency-Key'], requests[1].options.headers['Idempotency-Key']);
assert.equal(requests[0].options.body, requests[1].options.body);
assert.equal(requests[0].options.headers['X-API-Key'], 'test-only-key');
assert.equal(requests[0].options.credentials,'same-origin');
const denied = new Api(async () => new Response(JSON.stringify({detail: 'Tidak diizinkan'}), {status: 403}));
await assert.rejects(denied.get('/api/orders'), error => error.status === 403 && !error.uncertain);
const invalid = new Api(async () => new Response(JSON.stringify({detail: [{loc: ['body', 'quantity'], msg: 'Invalid quantity'}]}), {status: 422}));
await assert.rejects(invalid.get('/api/orders'), error => error.message.includes('quantity'));
const readPosts=[];
const reader=new Api(async(path,options)=>{readPosts.push({path,options});throw new TypeError('Offline');});
reader.key='read-key';
await assert.rejects(reader.post('/api/ai/investigate',{question:'Apa prioritas hari ini?'}),
  error=>error.uncertain===false&&error.message.startsWith('Data belum dapat dimuat'));
assert.equal(readPosts[0].options.method,'POST');
assert.equal(readPosts[0].options.headers['Idempotency-Key'],undefined);
assert.equal(readPosts[0].options.headers['Content-Type'],'application/json');
const sessionRequests=[];
const sessionApi=new Api(async(path,options)=>{sessionRequests.push({path,options});return new Response('{}');});
sessionApi.csrf='csrf-test-token';
await sessionApi.save(sessionApi.transaction('/api/products',{sku:'SESSION'}));
assert.equal(sessionRequests[0].options.headers['X-API-Key'],undefined);
assert.equal(sessionRequests[0].options.headers['X-CSRF-Token'],'csrf-test-token');
assert.equal(sessionRequests[0].options.credentials,'same-origin');
// Binding aktor: setiap pencatatan menyatakan akun yang menyusunnya, sedangkan login/logout yang
// memakai post() tanpa key tidak boleh membawanya agar pemulihan lewat "Masuk ulang" tetap jalan.
assert.equal(sessionRequests[0].options.headers['X-Beeloft-Actor'],undefined);
const boundRequests=[];
const boundApi=new Api(async(path,options)=>{boundRequests.push({path,options});return new Response('{}');});
boundApi.actorId='actor-a';
await boundApi.save(boundApi.transaction('/api/movements',{quantity:1}));
await boundApi.post('/api/session/logout',{});
await boundApi.get('/api/me');
assert.equal(boundRequests[0].options.headers['X-Beeloft-Actor'],'actor-a');
assert.equal(boundRequests[1].options.headers['X-Beeloft-Actor'],undefined);
assert.equal(boundRequests[2].options.headers['X-Beeloft-Actor'],undefined);
console.log('Client checks PASS: escaping, date, exact write retry, read-only POST, auth header, actor binding, structured errors.');
const exported = new Api(async (path, options) => {
  assert.equal(options.headers['X-API-Key'],'test-csv-key');
  return new Response('ID,Catatan\r\n1,"Uji, CSV"\r\n',{headers:{'Content-Type':'text/csv'}});
});
exported.key = 'test-csv-key';
assert.equal(await (await exported.download('/api/activity.csv')).text(),'ID,Catatan\r\n1,"Uji, CSV"\r\n');
await assert.rejects(denied.download('/api/activity.csv'), error => error.status === 403 && !error.uncertain);
console.log('CSV client checks PASS: authenticated blob and JSON access errors.');
const {formatMaterialQuantity} = await import('../beeloft/static/client.mjs');
assert.equal(formatMaterialQuantity('1000000000000000.125','m'),'1.000.000.000.000.000,125 m');
assert.equal(formatMaterialQuantity('-0.125','kg'),'-0,125 kg');
assert.equal(formatMaterialQuantity('10.000','pcs'),'10 pcs');


// P3-B: penolakan batas tanggal harus sampai ke layar sebagai pesannya sendiri. Investigasi yang
// disimpan adalah transaksi ber-Idempotency-Key, jadi 500 dulu ditandai `uncertain` dan UI
// menawarkan "coba ulang penyimpanan" untuk permintaan yang tidak akan pernah berhasil. 422
// membawa pesan Bahasa Indonesia yang menyebut parameternya dan tidak pernah uncertain.
const outOfRange = 'Kombinasi as_of dan window_days menunjuk tanggal di luar kalender yang terwakili (0001-01-01 sampai 9999-12-31). Sesuaikan parameter tersebut lalu muat ulang laporannya.';
const refused = new Api(async () => new Response(JSON.stringify({detail: outOfRange}), {status: 422}));
await assert.rejects(refused.get('/api/production-quality-insights?as_of=0001-01-01'),
  error => error.status === 422 && error.uncertain === false && error.message === outOfRange);
await assert.rejects(refused.save(refused.transaction('/api/ai/investigations', {as_of: '0001-01-01'})),
  error => error.status === 422 && error.uncertain === false && error.message === outOfRange);
assert.equal(outOfRange.includes('as_of'), true);
assert.equal(outOfRange.includes('window_days'), true);
// Kontras: hanya 5xx pada transaksi yang boleh membuat hasilnya tidak pasti.
const broken = new Api(async () => new Response(JSON.stringify({detail: 'Internal Server Error'}), {status: 500}));
await assert.rejects(broken.save(broken.transaction('/api/ai/investigations', {as_of: '0001-01-01'})),
  error => error.status === 500 && error.uncertain === true);
console.log('Date boundary client checks PASS: 422 detail reaches the UI and never looks uncertain.');
