import {Api, escapeHTML as e, displayDate as date, formatMaterialQuantity as materialQty} from './client.mjs';

const $ = id => document.getElementById(id);
const api = new Api();
const nf = new Intl.NumberFormat('id-ID');
const n = value => nf.format(value);
const minuteQty = value => materialQty(value,'menit');
const labels = {planned:'Belum cutting', cutting:'Cutting', sewing:'Sewing', finishing:'Finishing', qc:'QC', warehouse:'Gudang', rework:'Rework', reject:'Reject'};
const stages = ['planned','cutting','sewing','finishing','qc','warehouse'];
let user = null, transitions = [], boardData = null, selected = null, history = [], historyOffset = 0;
let offset = 0, epoch = 0, boardRequest = 0, detailRequest = 0, view = 'board', modalBusy = false, unresolved = false;
let dialogVersion = 0;
// Satu logout dalam penerbangan pada satu waktu. Klik ganda memakai ulang promise yang sama, jadi
// tidak ada perlombaan antara dua pencabutan session.
let logoutRequest = null;
let issues = [], issuesMore = false;
let activityRequest = 0, activityCursor = null, activityRows = [], activityQuery = null;
let commandCenterRequest = 0;
let auditFilters = {q:'',category:'all',actor_id:'',start_date:'',end_date:''};
let workforceFilters = {work_date:'',status:'all',q:''};
let exportBusy = false;
let noticeTimer;
let materialsRequest = 0, materialsOffset = 0;
let peopleRequest = 0, productsRequest = 0, productsCache = [];
let dialogReturnFocus = null;
// Host analitik: dua belas laporan insight berbagi satu section workspace. Satu counter
// request menjamin respons laporan yang tertinggal tidak bisa mengecat ulang laporan
// yang sekarang aktif, persis seperti counter feature-local pada halaman lain.
let analyticsRequest = 0, analyticsReport = null, analyticsFilters = {};
// Tiga tujuan Milestone D (AI, Integrasi, Audit) adalah halaman workspace, bukan modal,
// jadi masing-masing memegang request counter sendiri. aiHistoryRequest terpisah dari
// aiRequest: memuat riwayat tidak boleh menjatuhkan guard submit investigasi yang sedang
// berjalan, dan sebaliknya.
let aiRequest = 0, aiHistoryRequest = 0, aiHistoryBefore = null, aiTransaction = null;
let integrationsRequest = 0;
let auditRequest = 0;

function theme(value) {
  document.documentElement.dataset.theme = value;
  $('theme').textContent = value === 'dark' ? 'Mode terang' : 'Mode gelap';
  try { localStorage.setItem('beeloft.theme', value); } catch {}
}
try { theme(localStorage.getItem('beeloft.theme') || 'light'); } catch { theme('light'); }
$('theme').onclick = () => theme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

function sidebar(open,restoreFocus=false) {
  document.body.classList.toggle('nav-open',open);
  $('menu-toggle').setAttribute('aria-expanded',String(open));
  if(!open&&restoreFocus&&!$('menu-toggle').hidden)$('menu-toggle').focus();
}
$('menu-toggle').onclick=()=>sidebar(!document.body.classList.contains('nav-open'));
$('app-sidebar').onclick=event=>{
  const button=event.target.closest('button');if(!button)return;
  const drawerOpen=document.body.classList.contains('nav-open');
  if(!drawerOpen)return;
  queueMicrotask(()=>{
    // Tujuan halaman sudah menutup drawer dan memindahkan fokus sendiri lewat
    // activateWorkspace(). Tujuan dialog legacy masih perlu drawer ditutup dan
    // fokus diingat pada tombol menu, karena activateWorkspace tidak dipakainya.
    if(document.body.classList.contains('nav-open'))sidebar(false);
    if($('dialog').open)dialogReturnFocus=$('menu-toggle');
  });
};
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.body.classList.contains('nav-open'))sidebar(false,true);});
function activeNavigation(id) {
  for(const item of $('app-sidebar').querySelectorAll('[aria-current]'))item.removeAttribute('aria-current');
  if(id)$(id).setAttribute('aria-current','page');
}
// Registri tujuan workspace: item sidebar utama dipetakan ke section yang
// dimilikinya. Tabel ini hanya mengoordinasikan aktivasi halaman — tidak memuat
// data, tidak merender, dan tidak menyimpan logika bisnis; setiap renderer tetap
// memiliki filter, request counter, dan kontrak state-nya sendiri.
const workspaceDestinations={
  'command-center':'command-center-view',
  'board-home':'board-view',
  'materials':'materials-view',
  'workforce':'people-view',
  'products':'products-view',
  'activity':'activity-view',
  'wip-ageing-insights':'analytics-view',
  'capacity-plan':'analytics-view',
  'production-quality-insights':'analytics-view',
  'supplier-performance-insights':'analytics-view',
  'material-price-insights':'analytics-view',
  'purchase-commitment-insights':'analytics-view',
  'demand-forecast':'analytics-view',
  'replenishment':'analytics-view',
  'size-demand-insights':'analytics-view',
  'return-insights':'analytics-view',
  'dead-stock-insights':'analytics-view',
  'stock-adjustment-insights':'analytics-view',
  'ai-brain':'ai-view',
  'integrations':'integrations-view',
  'audit-trail':'audit-view'
};
// Seluruh section di dalam workspace-main, termasuk section internal seperti
// rincian order yang berbagi satu item sidebar dengan papan produksi.
// invalidate() menaikkan request counter feature-local penjaga section itu,
// supaya respons yang baru sampai setelah pengguna pindah tidak bisa mengecat
// ulang halaman yang sekarang aktif.
const workspaceSections=[
  {id:'command-center-view',view:'command-center',invalidate(){commandCenterRequest++;}},
  {id:'board-view',view:'board',invalidate(){boardRequest++;}},
  {id:'detail-view',view:'detail',invalidate(){detailRequest++;}},
  {id:'materials-view',view:'materials',invalidate(){materialsRequest++;}},
  {id:'people-view',view:'people',invalidate(){peopleRequest++;}},
  {id:'products-view',view:'products',invalidate(){productsRequest++;}},
  {id:'activity-view',view:'activity',invalidate(){activityRequest++;}},
  {id:'analytics-view',view:'analytics',invalidate(){analyticsRequest++;}},
  {id:'ai-view',view:'ai',invalidate(){aiRequest++;aiHistoryRequest++;}},
  {id:'integrations-view',view:'integrations',invalidate(){integrationsRequest++;}},
  {id:'audit-view',view:'audit',invalidate(){auditRequest++;}}
];
// Satu jalur aktivasi untuk setiap tujuan workspace: sembunyikan setiap section
// lain sambil menaikkan request counternya, tampilkan target, catat nama view
// aktif, pindahkan aria-current, lalu tutup drawer mobile dan letakkan fokus.
// Pemanggil tetap memuat data dan merender kontennya sendiri.
function activateWorkspace(navId,sectionId=workspaceDestinations[navId]){
  for(const section of workspaceSections){
    if(section.id===sectionId)continue;
    section.invalidate();
    $(section.id).hidden=true;
  }
  const target=workspaceSections.find(section=>section.id===sectionId);
  $(sectionId).hidden=false;
  if(target)view=target.view;
  activeNavigation(navId);
  if(document.body.classList.contains('nav-open')){
    sidebar(false);
    if($('dialog').open){dialogReturnFocus=$('menu-toggle');return;}
    const heading=$(sectionId).querySelector('h1');
    if(heading){heading.tabIndex=-1;heading.focus();}
  }
}

// Tujuan halaman yang dipanggil dari dalam dialog (mis. "Kembali ke Master SKU")
// menutup dialog fokusnya lebih dulu; drawer dan fokus ditangani activateWorkspace.
function navigateFromDialog(show) {
  if ($('dialog').open) $('dialog').close();
  show();
}

// Dua belas anak sidebar Analitik berbagi satu host. Memilih anak mana pun mengaktifkan
// section yang sama, lalu mengganti judul, filter, dan isi laporan. analyticsRequest dinaikkan
// di sini (bukan di invalidate() saja) karena berpindah antar laporan tidak menyembunyikan
// section, jika tidak dinaikkan respons laporan sebelumnya masih bisa mengecat hasil yang baru.
// Mengembalikan nilai request yang harus dijaga oleh loader laporan ini.
function activateAnalyticsReport(navId,title,content) {
  activateWorkspace(navId);
  analyticsRequest++;
  analyticsReport=navId;
  $('analytics-eyebrow').textContent='Analitik · '+$(navId).textContent.trim();
  $('analytics-heading').textContent=title;
  $('analytics-body').innerHTML=content;
  return analyticsRequest;
}
// Memuat ulang laporan analitik yang sedang aktif, dipakai setelah child dialog berhasil
// menyimpan (mis. master kapasitas) supaya halaman memakai data terbaru tanpa membuka ulang.
function reloadAnalytics() {
  return analyticsReports[analyticsReport]?.();
}
// Filter laporan bertahan setelah child dialog ditutup, seperti filter roster People.
// Disimpan per laporan karena setiap laporan mempunyai bidangnya sendiri; FormData hanya
// mengumpulkan kontrol bernama, dan seluruh bidang filter laporan adalah input/select biasa.
function saveAnalyticsFilters(navId,form) {
  analyticsFilters[navId]=Object.fromEntries(new FormData(form));
}
function restoreAnalyticsFilters(navId,form) {
  const saved=analyticsFilters[navId]; if(!saved)return;
  for(const [name,value] of Object.entries(saved)) {
    const input=form.elements[name];
    if(input&&value!==undefined)input.value=value;
  }
}

function notify(message) {
  $('notice').textContent = message; $('notice').hidden = false;
  clearTimeout(noticeTimer); noticeTimer = setTimeout(() => $('notice').hidden = true, 6000);
}
function message(id, text, error = false) {
  $(id).hidden = !text; $(id).textContent = text;
  $(id).classList.toggle('error', error);
}
// Menambahkan baris hasil ke daftar sekaligus membuang placeholder status yang dipasang
// oleh shell dialog. Tanpa ini daftar berbasis cursor menampilkan "Memuat ..." di atas
// halaman pertama selamanya, karena penambahan baris memakai beforeend dan placeholder
// hanya tergantikan pada kondisi kosong.
// Membersihkan placeholder "Memuat ..." di dalam dialog. Dipakai ketika pemuatan pertama
// gagal, supaya status loading tidak terbaca bersamaan dengan pesan error dan tombol
// coba lagi. Placeholder kosong atau berisi data tidak ikut dihapus.
function clearDialogLoading() {
  for (const node of $('dialog-content').querySelectorAll('.state'))
    if (/^(Memuat|Menghitung|Menggabungkan)/.test(node.textContent.trim())) node.remove();
}
function appendRows(id, html) {
  const host = $(id), first = host.firstElementChild;
  if (first && first.classList.contains('state')) first.remove();
  host.insertAdjacentHTML('beforeend', html);
}
// Peringatan session dipakai ketika logout tidak terkonfirmasi. Banner ini sengaja tidak otomatis
// hilang: selama session server belum benar-benar dicabut, statusnya harus terus terlihat. Tombol
// coba lagi hanya ditawarkan bila mencoba keluar lagi memang langkah berikutnya yang benar; ketika
// session sudah berpindah akun, yang dibutuhkan adalah masuk kembali, bukan mencabut session akun lain.
function sessionWarning(text, retry = true) {
  $('session-warning').hidden = !text; $('session-warning-text').textContent = text;
  $('session-retry').hidden = !text || !retry;
}
function clearWorkspace() {
  sessionWarning('');
  commandCenterRequest++; $('command-center-summary').replaceChildren();
  auditFilters = {q:'',category:'all',actor_id:'',start_date:'',end_date:''};
  $('command-center-attention').replaceChildren(); $('command-center-snapshots').replaceChildren();
  for(const id of ['command-center-hero','command-center-channels','command-center-contribution',
    'command-center-products','command-center-operations'])$(id).replaceChildren();
  $('command-center-period').textContent='';
  materialsRequest++; materialsOffset = 0; $('batch-list').replaceChildren(); $('material-filter').innerHTML = '<option value="">Semua bahan</option>';
  peopleRequest++; workforceFilters = {work_date:'',status:'all',q:''};
  $('workforce-list').replaceChildren(); $('workforce-summary').replaceChildren();
  productsRequest++; productsCache = []; $('product-list').replaceChildren();
  analyticsRequest++; analyticsReport = null; analyticsFilters = {};
  $('analytics-body').replaceChildren(); $('analytics-heading').textContent='Analitik'; $('analytics-eyebrow').textContent='Analitik';
  aiRequest++; aiHistoryRequest++; aiHistoryBefore = null; aiTransaction = null;
  $('ai-results').replaceChildren(); $('ai-history-list').replaceChildren(); message('ai-message',''); message('ai-history-message','');
  integrationsRequest++; $('integrations-body').replaceChildren(); message('integrations-message','');
  auditRequest++; $('audit-body').replaceChildren();
  $('backup').hidden = true;
  $('audit-trail').hidden = true;
  $('board-owner').innerHTML = '<option value="">Semua PIC</option>'; $('board-stage').value = 'all';
  activityRequest++; activityRows = []; activityCursor = null; activityQuery = null;
  $('activity-list').replaceChildren(); $('activity-summary').replaceChildren(); $('activity-day').value = ''; $('activity-end').value = ''; $('activity-export').disabled = true; $('activity-kind').value = 'all';
  epoch++; boardRequest++; detailRequest++; api.key = ''; api.actorId = ''; user = null; selected = null; boardData = null;
  dialogVersion++; modalBusy = false; unresolved = false; dialogReturnFocus=null; $('dialog').close();
  $('workspace').hidden = true; $('login-view').hidden = false; $('logout').hidden = true;
  $('menu-toggle').hidden=true;sidebar(false);
  $('account-name').textContent = ''; $('access-key').value = ''; $('order-list').replaceChildren();
  $('summary').replaceChildren(); $('detail-content').replaceChildren(); $('dialog-content').replaceChildren();
  $('notice').hidden = true; $('access-key').focus();
}
const LOGOUT_FAILED = 'Logout belum berhasil. Session di perangkat ini masih aktif dengan akun yang '
  + 'sama, jadi ruang kerja tetap terbuka agar statusnya tidak menyesatkan. Coba keluar lagi.';
const LOGOUT_UNCERTAIN = 'Logout belum terkonfirmasi karena server belum dapat dihubungi. Session di '
  + 'perangkat ini mungkin masih aktif, jadi ruang kerja tetap terbuka. Coba keluar lagi setelah koneksi pulih.';
const logoutSwitched = identity => 'Logout belum terjadi. Session di perangkat ini sudah berpindah ke '
  + `akun lain (${identity.name} · ${identity.role}) dan masih aktif, jadi ruang kerja akun sebelumnya `
  + 'ditutup supaya tidak ada tampilan bercampur identitas. Masuk kembali sebagai akun pencatat untuk '
  + 'melanjutkan; pencatatan yang belum pasti tetap tersimpan.';
// Memeriksa siapa yang sebenarnya dipegang session browser ini. Identitasnya dipertahankan, bukan
// direduksi menjadi boolean: ruang kerja lama hanya boleh tetap dipakai bila akunnya memang sama.
// 'inactive' berarti session sudah tidak aktif, 'active' menyertakan identitas yang menjawab, dan
// 'unknown' berarti statusnya belum dapat diketahui.
async function sessionIdentity() {
  try { return {state:'active', user: await api.get('/api/me')}; }
  catch (error) { return {state: error.status === 401 ? 'inactive' : 'unknown'}; }
}
// Logout hanya menutup ruang kerja bila pencabutan session terkonfirmasi. Sebelumnya setiap
// kegagalan ditelan dan ruang kerja selalu dibersihkan, sehingga UI menampilkan layar login biasa
// padahal session server masih hidup dan reload membuka kembali akun sebelumnya.
// Mengembalikan true bila logout terkonfirmasi, false bila belum.
async function logout(revoke=true) {
  // Session yang sudah diketahui mati (alur 401) tidak perlu dicabut lagi dan selalu boleh ditutup.
  if (!(revoke && user)) { clearWorkspace(); return true; }
  if (logoutRequest) return logoutRequest;
  const actorId = user.id;
  $('main').setAttribute('aria-busy','true');$('login-view').setAttribute('inert','');
  $('logout').disabled = true;$('session-retry').disabled = true;
  logoutRequest = (async () => {
    try {
      const version = epoch;
      try {
        await api.post('/api/session/logout',{});
      } catch (error) {
        // 401 adalah satu-satunya kegagalan yang membuktikan session sudah tidak aktif. CSRF 403,
        // 5xx, timeout, dan kegagalan jaringan tidak membuktikan apa pun, jadi session diperiksa
        // langsung. Server yang sudah mencabut lalu kehilangan responsnya tetap dikenali di sini,
        // sehingga aplikasi tidak terjebak selamanya pada error logout.
        const probe = error.status === 401 ? {state:'inactive'} : await sessionIdentity();
        if (version !== epoch) return true;
        if (probe.state === 'unknown') { sessionWarning(LOGOUT_UNCERTAIN); return false; }
        if (probe.state === 'active') {
          // Session masih hidup, jadi logout belum terjadi. Yang menentukan boleh atau tidaknya
          // ruang kerja dipertahankan adalah identitasnya, bukan sekadar fakta bahwa /api/me
          // menjawab: cookie session dipakai bersama seluruh tab dan dapat sudah ditukar akun lain.
          if (probe.user.id === actorId) { sessionWarning(LOGOUT_FAILED); return false; }
          // Session sudah berpindah ke akun lain dan masih aktif. Mempertahankan ruang kerja akun
          // sebelumnya akan membuat tampilan bercampur identitas: setiap pembacaan berikutnya memakai
          // session akun baru sementara UI masih menampilkan akun lama. clearWorkspace() membuang
          // seluruh state tampilan, menaikkan epoch sehingga respons lama tidak dapat menimpa konteks
          // baru, dan mengosongkan api.actorId tanpa pernah menggantinya ke akun baru. sessionStorage
          // sengaja tidak disentuh, jadi draft pending akun asli tetap dapat dipulihkan.
          clearWorkspace();
          sessionWarning(logoutSwitched(probe.user), false);
          return false;
        }
      }
      if (version !== epoch) return true;
      clearWorkspace();
      return true;
    } finally {
      logoutRequest = null;
      $('login-view').removeAttribute('inert');$('main').removeAttribute('aria-busy');
      $('logout').disabled = false;$('session-retry').disabled = false;
    }
  })();
  return logoutRequest;
}
// Tombol "Masuk ulang" hidup di dalam dialog modal, jadi banner di belakangnya tidak dapat dibaca
// maupun ditekan. Kegagalan logout karena itu ikut dilaporkan di dalam dialog yang sedang dibuka.
async function reauthenticate(target) {
  if (await logout()) return;
  // Ruang kerja dapat sudah ditutup karena session berpindah akun; dialog beserta elemen pesannya
  // ikut hilang, dan banner pada layar login sudah menjelaskan keadaannya.
  if ($(target)) message(target, $('session-warning-text').textContent, true);
}
$('logout').onclick = () => logout();
$('session-retry').onclick = () => logout();
$('sso-login').onclick = () => location.assign('/api/sso/login');
function fail(error, target) {
  if (error.status === 401) { logout(false); message('login-error', 'Sesi berakhir. Masukkan kembali kunci akses yang aktif.', true); }
  else message(target, error.message, true);
}
function enterWorkspace(me,workflow) {
  // Login yang berhasil menjadikan status session diketahui baik, jadi peringatan session apa pun
  // dari percobaan logout sebelumnya tidak boleh tertinggal di layar.
  sessionWarning('');
  user=me;api.actorId=me.id;transitions=workflow.transitions;$('access-key').value='';
  $('account-name').textContent=`${me.name} · ${me.role}`;
  $('login-view').hidden=true;$('workspace').hidden=false;$('logout').hidden=false;
  $('menu-toggle').hidden=false;
  $('new-order').hidden=me.role!=='admin';$('backup').hidden=me.role!=='admin';$('audit-trail').hidden=me.role!=='admin';offset=0;showBoard();
  const pending=readPending();if(pending)recover(pending);
}
$('login-form').onsubmit = async event => {
  event.preventDefault(); const button = event.currentTarget.querySelector('button');
  button.disabled = true; button.textContent = 'Memeriksa akses…'; message('login-error', '');
  const key=$('access-key').value.trim(),version=++epoch;
  try {
    await api.post('/api/session',{api_key:key});
    const [me, workflow] = await Promise.all([api.get('/api/me'), api.get('/api/stages')]);
    if (version !== epoch) return;
    enterWorkspace(me,workflow);
  } catch (error) { if (version === epoch) message('login-error', error.message, true); }
  finally { button.disabled = false; button.textContent = 'Buka ruang produksi'; }
};

async function restoreSession() {
  const version=++epoch;
  try{
    const [me,workflow]=await Promise.all([api.get('/api/me'),api.get('/api/stages')]);
    if(version===epoch)enterWorkspace(me,workflow);
  }catch(error){if(version===epoch&&error.status!==401)message('login-error',error.message,true);}
  finally{$('login-view').removeAttribute('inert');$('main').removeAttribute('aria-busy');}
}
async function loadLoginOptions() {
  try {
    const sso=await api.get('/api/sso');
    if(!sso.enabled)return;
    $('login-copy').textContent='Gunakan identitas perusahaan atau kunci akses lokal.';
    $('sso-login').textContent=`Masuk dengan ${sso.label}`;$('sso-login').hidden=false;$('sso-separator').hidden=false;
  } catch {}
}
loadLoginOptions();
restoreSession();

function statusHTML(order) {
  if (order.overdue) return '<span class="status-label late">Lewat target</span>';
  if (order.status === 'completed') return '<span class="status-label done">Selesai</span>';
  if (order.status === 'closed_with_reject') return '<span class="status-label done">Ditutup · ada reject</span>';
  return '<span class="status-label">Dalam produksi</span>';
}
function issueBadge(order) {
  return order.open_issues ? `<span class="status-label late">${n(order.open_issues)} kendala terbuka</span>` : '';
}
function showBoard() {
  activateWorkspace('board-home'); selected = null;
  loadBoard();
}
$('brand').onclick = event => { event.preventDefault(); if (user) showBoard(); };
$('board-home').onclick=showBoard;
$('back').onclick = () => { showBoard(); $('search').focus(); };
$('refresh').onclick = () => loadBoard();
$('issues-summary').onclick = () => { resetBoardFilters(); $('status').value = 'blocked'; loadBoard(); };
$('search-form').onsubmit = event => { event.preventDefault(); offset = 0; loadBoard(); };
$('status').onchange = $('board-owner').onchange = $('board-stage').onchange = () => { offset = 0; loadBoard(); };
function resetBoardFilters() { $('search').value = ''; $('status').value = 'all'; $('board-owner').value = ''; $('board-stage').value = 'all'; offset = 0; }
$('reset-board').onclick = () => { resetBoardFilters(); loadBoard(); };
$('previous').onclick = () => { offset = Math.max(0, offset - 25); loadBoard(); };
$('next').onclick = () => { offset += 25; loadBoard(); };

function commandMoney(value) {
  const [whole,fraction='00'] = String(value || '0.00').split('.');
  return `Rp${BigInt(whole).toLocaleString('id-ID')},${fraction.padEnd(2,'0').slice(0,2)}`;
}
function commandSource(value) {
  return value ? `Snapshot ${new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(value))}` : 'Snapshot belum tersedia';
}
function showCommandOrders(status) {
  resetBoardFilters(); $('status').value=status; showBoard();
}
/* Presentation helpers for the reconstructed Command Center surfaces.
   Every value rendered here comes from the existing /api/command-center payload;
   nothing is derived beyond counting, ratios, and scaling of real fields. */
const svgIcon = (name, extra = '') => `<svg class="icon${extra ? ' ' + extra : ''}" aria-hidden="true" focusable="false"><use href="#i-${name}"/></svg>`;
const decimalValue = value => {
  const parsed = Number(String(value ?? '0').replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : 0;
};
const percentValue = value => Math.min(100, Math.max(0, decimalValue(value)));
function commandGauge(percent, tone, label) {
  const ticks = 44, filled = Math.round(percentValue(percent) / 100 * ticks);
  let marks = '';
  for (let index = 0; index < ticks; index += 1) {
    const angle = Math.PI - (index / (ticks - 1)) * Math.PI;
    const inner = 74, outer = 92;
    const x1 = (100 + inner * Math.cos(angle)).toFixed(1), y1 = (100 - inner * Math.sin(angle)).toFixed(1);
    const x2 = (100 + outer * Math.cos(angle)).toFixed(1), y2 = (100 - outer * Math.sin(angle)).toFixed(1);
    const state = index < filled ? `is-on ${tone}` : 'is-off';
    marks += `<line class="gauge-tick ${state}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
  }
  return `<div class="gauge"><svg viewBox="0 0 200 108" role="img" aria-label="${e(label)}">${marks}</svg><p class="gauge-value">${n(Math.round(percentValue(percent)))}%</p><p class="gauge-note">${e(label)}</p></div>`;
}
function commandMeter(label, figure, ratio, note, tone) {
  const width = Math.min(100, Math.max(0, ratio * 100));
  return `<div class="meter"><div class="meter-top"><span class="meter-label">${e(label)}</span><span class="meter-figure">${e(figure)}</span></div>`
    + `<div class="meter-track"><span class="meter-fill${tone ? ' ' + tone : ''}" style="width:${width.toFixed(1)}%"></span></div>`
    + (note ? `<p class="meter-note">${e(note)}</p>` : '') + '</div>';
}
function commandSplit3(cells) {
  const peak = Math.max(1, ...cells.map(cell => cell.value));
  return '<div class="split3">' + cells.map(cell =>
    `<div class="split3-cell"><p class="split3-value">${e(cell.display)}</p><p class="split3-label">${e(cell.label)}</p>`
    + `<div class="split3-bar"><span style="width:${(cell.value / peak * 100).toFixed(1)}%"></span></div></div>`).join('') + '</div>';
}
function commandBars(rows) {
  const peak = Math.max(1, ...rows.map(row => row.value));
  const top = rows.reduce((best, row) => row.value > best ? row.value : best, 0);
  let flagged = false;
  return '<div class="barchart">' + rows.map(row => {
    const isTop = !flagged && row.value === top && top > 0;
    if (isTop) flagged = true;
    return `<div class="barchart-col${isTop ? ' is-top' : ''}">${isTop ? `<span class="barchart-cap">${n(row.value)}</span>` : ''}`
      + `<span class="barchart-bar" style="height:${Math.max(4, row.value / peak * 100).toFixed(1)}%"></span>`
      + `<span class="barchart-label" title="${e(row.label)}">${e(row.label)}</span></div>`;
  }).join('') + '</div>';
}
function commandHeroBars(rows) {
  const peak = Math.max(1, ...rows.map(row => Math.abs(row.value)));
  return '<div class="hero-chart">' + rows.map(row =>
    `<div class="hero-bar"><div class="hero-bar-top"><span class="hero-bar-label">${e(row.label)}</span><span class="hero-bar-value">${e(row.display)}</span></div>`
    + `<div class="hero-bar-track"><span class="hero-bar-fill${row.tone ? ' ' + row.tone : ''}" style="width:${(Math.abs(row.value) / peak * 100).toFixed(1)}%"></span></div></div>`).join('') + '</div>';
}
const commandDay = value => value
  ? new Intl.DateTimeFormat('id-ID',{day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'))
  : '';
const commandRange = (start, end) => !start ? '' : start === end ? commandDay(start) : `${commandDay(start)} – ${commandDay(end)}`;
/* Compact rupiah for headline figures only; the precise value stays available as a title. */
function commandMoneyShort(value) {
  const amount = decimalValue(value);
  const [scale, suffix] = amount >= 1e12 ? [1e12,' T'] : amount >= 1e9 ? [1e9,' M']
    : amount >= 1e6 ? [1e6,' jt'] : amount >= 1e3 ? [1e3,' rb'] : [1,''];
  const scaled = amount / scale;
  return 'Rp' + new Intl.NumberFormat('id-ID',{maximumFractionDigits:scale === 1 ? 0 : 1}).format(scaled) + suffix;
}
/* Sales trend: one point per real order date in the latest Jubelio batch. No gap filling, so a day
   only appears when the snapshot actually contains completed orders for it. */
function commandTrend(rows, caption) {
  const width = 600, height = 168, top = 12, bottom = 12, side = 4;
  const values = rows.map(row => decimalValue(row.gross_revenue));
  const peak = Math.max(...values, 1), floor = height - bottom, plot = floor - top;
  const step = rows.length > 1 ? (width - side * 2) / (rows.length - 1) : 0;
  const at = index => rows.length > 1 ? side + index * step : width / 2;
  const level = value => top + (1 - value / peak) * plot;
  const points = values.map((value, index) => [at(index), level(value)]);
  const line = points.map(([x, y], index) => `${index ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const area = rows.length > 1
    ? `${line} L${points[points.length-1][0].toFixed(1)} ${floor} L${points[0][0].toFixed(1)} ${floor} Z`
    : `M${(at(0)-40).toFixed(1)} ${points[0][1].toFixed(1)} L${(at(0)+40).toFixed(1)} ${points[0][1].toFixed(1)} L${(at(0)+40).toFixed(1)} ${floor} L${(at(0)-40).toFixed(1)} ${floor} Z`;
  const grid = [0,.25,.5,.75,1].map(ratio =>
    `<line class="trend-grid" x1="0" y1="${(top+ratio*plot).toFixed(1)}" x2="${width}" y2="${(top+ratio*plot).toFixed(1)}"/>`).join('');
  const dots = points.map(([x, y]) => `<circle class="trend-dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5"/>`).join('');
  const marks = rows.length > 2 ? [0, Math.floor((rows.length-1)/2), rows.length-1] : rows.map((_, index) => index);
  const ticks = [...new Set(marks)].map(index =>
    `<span>${e(commandDay(rows[index].date))}</span>`).join('');
  return `<div class="trend"><p class="trend-peak">Puncak ${e(commandMoneyShort(String(peak)))}</p>`
    + `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${e(caption)}">`
    + `<defs><linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">`
    + `<stop offset="0" stop-color="var(--primary)" stop-opacity=".24"/>`
    + `<stop offset="1" stop-color="var(--primary)" stop-opacity="0"/></linearGradient></defs>`
    + `${grid}<path class="trend-area" d="${area}"/>`
    + (rows.length > 1 ? `<path class="trend-line" d="${line}"/>` : '') + `${dots}</svg>`
    + `<div class="trend-ticks">${ticks}</div><p class="trend-note">${e(caption)}</p></div>`;
}
const ATTENTION_DOMAINS = {production:'Produksi',people:'People',inventory:'Stok',finance:'Finance',
  approval:'Approval',quality:'Kualitas',capacity:'Kapasitas',data_quality:'Data',integration:'Integrasi'};
function attentionDomainRows(attention) {
  const tally = new Map();
  for (const row of attention) tally.set(row.kind, (tally.get(row.kind) || 0) + 1);
  const rows = [...tally].map(([kind, value]) => ({label:ATTENTION_DOMAINS[kind] || kind, value}))
    .sort((left, right) => right.value - left.value || left.label.localeCompare(left.label === right.label ? left.label : right.label));
  if (rows.length <= 7) return rows;
  const rest = rows.slice(6).reduce((total, row) => total + row.value, 0);
  return [...rows.slice(0, 6), {label:'Lain', value:rest}];
}
async function showCommandCenter() {
  if(guardPending())return;
  activateWorkspace('command-center'); selected=null;
  const version=epoch,request=++commandCenterRequest;
  message('command-center-message','Menggabungkan ledger operasional dan snapshot vendor…');
  $('command-center-content').hidden=true;$('command-center-summary').setAttribute('aria-busy','true');
  try{
    const report=await api.get('/api/command-center');
    if(version!==epoch||request!==commandCenterRequest||view!=='command-center')return;
    const action={production_overdue:'command-production-overdue',production_issues:'command-production-issues',
      replenishment:'replenishment',approvals:'approvals',jubelio_stock:'jubelio-stock-reconciliation',
      production_quality:'production-quality-insights',production_capacity:'capacity-plan',
      workforce:'command-workforce',
      mekari_payables:'mekari-payables-summary',
      mekari_receivables:'mekari-receivables-summary',integrations:'integrations'};
    const critical=report.status.critical_count,overdue=report.production.overdue_orders;
    /* Marketplace business performance. Every figure below comes from the latest Jubelio order
       snapshot batch, so it is labelled by that snapshot rather than by a calendar period. */
    const market=report.sales.marketplace,stat=market.summary,live=Boolean(market.snapshot_at);
    const refunded=decimalValue(stat.refund_amount)>0,unmatched=stat.unmatched_refunds;
    const away='Snapshot order Jubelio belum tersedia';
    $('command-center-summary').innerHTML=[
      ['Penjualan bersih',live?commandMoneyShort(stat.net_revenue):'—',live?'':'belum ada snapshot','wallet',
        refunded?{tone:'chip-warning',icon:'undo',text:`Refund ${commandMoneyShort(stat.refund_amount)}`}
          :{tone:'chip-success',icon:'check-circle',text:'Tanpa refund cocok'},
        live?`${commandMoney(stat.net_revenue)} · kotor ${commandMoney(stat.gross_revenue)} dikurangi refund yang cocok`:away,
        live?commandMoney(stat.net_revenue):''],
      ['Total order',live?stat.orders:'—',live?'order':'belum ada snapshot','inbox',
        live?{tone:'chip-primary',icon:'check-circle',text:`${n(stat.completed)} selesai`}:null,
        live?`${n(stat.pending)} menunggu · ${n(stat.processing)} diproses · ${n(stat.cancelled)} batal`:away,''],
      ['Unit terjual',live?stat.units:'—',live?'pcs':'belum ada snapshot','box',null,
        live?`Dari ${n(stat.completed_orders)} order selesai · ${n(stat.marketplaces)} marketplace`:away,''],
      ['AOV order selesai',live?commandMoneyShort(stat.average_order_value):'—',live?'/order':'belum ada snapshot','trend',null,
        live?`${commandMoney(stat.average_order_value)} · kotor order selesai dibagi jumlah order selesai`:away,
        live?commandMoney(stat.average_order_value):'']
    ].map(([label,value,unit,glyph,chip,foot,exact])=>`<div class="kpi-card"><dt>${e(label)}${svgIcon(glyph)}</dt><dd><span class="kpi-value"${exact?` title="${e(exact)}"`:''}>${typeof value==='number'?n(value):e(value)}${unit?` <small>${e(unit)}</small>`:''}${chip?`<span class="chip ${chip.tone}">${svgIcon(chip.icon)}${e(chip.text)}</span>`:''}</span></dd><p class="kpi-foot">${e(foot)}</p></div>`).join('');
    $('command-center-summary').removeAttribute('aria-busy');
    $('command-center-period').textContent=live
      ?`Jubelio snapshot ${commandSource(market.snapshot_at).replace('Snapshot ','')}`
        +(market.period_start?` · order ${commandRange(market.period_start,market.period_end)}`:'')
      :'Snapshot order Jubelio belum tersedia';
    $('command-center-operations').innerHTML=[
      ['Order aktif',`${n(report.production.active_orders)} order`,overdue?'is-alert':''],
      ['Keputusan',`${n(report.approvals.pending_count)} menunggu`,report.approvals.pending_count?'is-alert':''],
      ['Exception',`${n(report.status.attention_count)} perlu perhatian`,critical?'is-alert':''],
      ['Laba bersih',report.finance.current?commandMoney(report.finance.current.net_profit):'belum ada data','']
    ].map(([label,value,tone])=>`<div class="ops-stat ${tone}"><dt>${e(label)}</dt><dd>${e(value)}</dd></div>`).join('');
    const mark={critical:'alert-octagon',warning:'alert-triangle',info:'info'};
    $('command-center-attention').innerHTML=report.attention.length
      ?'<div class="decision-head" aria-hidden="true"><span>Level</span><span>Keputusan</span><span>Tindakan</span></div>'
        +report.attention.map(row=>`<article class="command-attention decision-row ${e(row.priority)}" data-command-attention="${e(row.id)}"><span class="decision-mark" aria-hidden="true">${svgIcon(mark[row.priority]||'info')}</span><div class="decision-body"><div class="decision-title"><h3>${e(row.title)}</h3><p class="status-label ${row.priority==='critical'?'late':''}">${row.priority==='critical'?'Kritis':'Perlu perhatian'} · ${e(row.kind)}</p></div><p class="decision-detail">${e(row.detail)}</p></div><span class="decision-action"><button data-action="${e(action[row.action])}">${e(row.action_label)}${svgIcon('arrow-right')}</button></span></article>`).join('')
      :'<p class="state">Tidak ada exception aktif dari sumber yang sudah tersambung.</p>';
    const finance=report.finance.current;
    const funnel=[
      {label:'Menunggu',value:stat.pending,tone:'is-pending'},
      {label:'Diproses',value:stat.processing,tone:'is-processing'},
      {label:'Selesai',value:stat.completed,tone:'is-completed'},
      {label:'Batal',value:stat.cancelled,tone:'is-cancelled'}
    ];
    const funnelSpan=Math.max(1,funnel.reduce((total,cell)=>total+cell.value,0));
    $('command-center-hero').innerHTML=`<div class="card-head"><h2>Total penjualan</h2>${svgIcon('cart','icon-lg')}</div>`
      +`<div class="hero-body"><div class="hero-figure"><p class="hero-value" title="${live?e(commandMoney(stat.gross_revenue)):''}">${live?e(commandMoneyShort(stat.gross_revenue)):'—'}</p>`
      +`<div class="hero-meta">${live?`<span class="chip chip-primary">${svgIcon('check-circle')}${n(stat.completed_orders)} order selesai</span>`
          +`<span class="chip chip-neutral">${svgIcon('box')}${n(stat.units)} pcs</span>`:''}</div>`
      +`<p class="hero-caption">${live?`Bersih ${e(commandMoney(stat.net_revenue))} setelah refund yang cocok`
          +(unmatched?` · ${n(unmatched)} refund lain (${e(commandMoneyShort(stat.unmatched_refund_amount))}) tidak cocok dengan order di snapshot ini`:'')
        :'Belum ada snapshot order Jubelio yang tersambung.'}</p></div>`
      +(market.daily.length?`<div class="hero-trendwrap">${commandTrend(market.daily,
          `Penjualan order selesai · ${commandRange(market.trend_start,market.trend_end)}`)}</div>`
        :'<p class="state">Belum ada order selesai pada snapshot ini.</p>')
      +'</div>'
      +`<div class="hero-split"><div class="hero-split-grid">${funnel.map(cell=>`<div class="hero-split-cell ${e(cell.tone)}"><p class="hero-split-value">${n(cell.value)}</p><p class="hero-split-label">${e(cell.label)}</p></div>`).join('')}</div>`
      +`<div class="hero-split-bars">${funnel.map(cell=>`<span class="hero-split-bar ${e(cell.tone)}" style="flex:${Math.max(cell.value,funnelSpan*0.03).toFixed(2)}"></span>`).join('')}</div></div>`;
    $('command-center-channels').innerHTML=`<div class="card-head"><h3>Perbandingan performa marketplace</h3>${svgIcon('chart')}</div>`
      +(market.marketplaces.length?`<div class="table-scroll"><table class="data-table channel-table"><thead><tr>`
        +'<th scope="col">Marketplace</th><th scope="col">Order</th><th scope="col">Unit</th>'
        +'<th scope="col">AOV</th><th scope="col">Kontribusi</th><th scope="col">Penjualan</th></tr></thead><tbody>'
        +market.marketplaces.map(row=>`<tr><td><span class="channel-name">${e(row.marketplace)}</span><span class="channel-flow">${e([[row.completed,'selesai'],[row.processing,'diproses'],[row.pending,'menunggu'],[row.cancelled,'batal']].filter(([count])=>count).map(([count,word])=>`${n(count)} ${word}`).join(' · ')||'belum ada order')}</span></td>`
          +`<td class="is-num">${n(row.orders)}</td><td class="is-num">${n(row.units)}</td>`
          +`<td class="is-num">${e(commandMoney(row.average_order_value))}</td>`
          +`<td class="is-num"><span class="share"><span class="share-bar"><span style="width:${Math.min(100,decimalValue(row.contribution_percent)).toFixed(1)}%"></span></span>${e(row.contribution_percent)}%</span></td>`
          +`<td class="is-num"><strong>${e(commandMoney(row.gross_revenue))}</strong>${decimalValue(row.refund_amount)>0?`<span class="channel-net">bersih ${e(commandMoney(row.net_revenue))}</span>`:''}</td></tr>`).join('')
        +'</tbody></table></div>'
        :'<p class="state">Belum ada marketplace pada snapshot order Jubelio.</p>')
      +'<button data-action="jubelio-order-summary">Buka penjualan Jubelio</button>';
    $('command-center-contribution').innerHTML=`<div class="card-head"><h3>Kontribusi marketplace</h3>${svgIcon('plug')}</div>`
      +(market.marketplaces.length?commandHeroBars(market.marketplaces.map((row,index)=>({
          label:`${row.marketplace} · ${row.contribution_percent}%`,
          display:commandMoneyShort(row.gross_revenue),
          value:decimalValue(row.gross_revenue),
          tone:index?'is-muted':''
        })))+`<p class="command-source">Berdasarkan pendapatan kotor order selesai pada snapshot ini.</p>`
        :'<p class="state">Belum ada marketplace pada snapshot order Jubelio.</p>');
    $('command-center-products').innerHTML=`<div class="card-head"><h3>Produk terlaris</h3>${svgIcon('tag')}</div>`
      +(market.products.length?'<ol class="rank-list">'+market.products.slice(0,5).map((row,index)=>
          `<li class="rank-row"><span class="rank-mark">${index+1}</span><span class="rank-body"><span class="rank-name">${e(row.product_name||row.sku)}</span><span class="rank-meta">${e(row.sku)}${row.color?' · '+e(row.color):''}${row.size?' · '+e(row.size):''} · ${n(row.orders)} order</span></span>`
          +`<span class="rank-figures"><strong>${n(row.units)} pcs</strong><span>${e(commandMoney(row.gross_revenue))}</span></span></li>`).join('')+'</ol>'
        +`<p class="command-source">Urut berdasarkan unit terjual dari order selesai.</p>`
        :'<p class="state">Belum ada produk terjual pada snapshot ini.</p>');
    const wip=report.production.in_progress_quantity,rework=report.production.rework_quantity;
    const required=report.capacity.required_minutes,available=report.capacity.available_minutes;
    const head=(title,glyph)=>`<div class="card-head"><h3>${title}</h3>${svgIcon(glyph)}</div>`;
    const domainRows=attentionDomainRows(report.attention);
    $('command-center-snapshots').innerHTML=`
      <article class="command-snapshot snapshot-card card">${head('Antrean per domain','chart')}${domainRows.length?commandBars(domainRows)+'<p class="command-source">Jumlah exception aktif per domain operasional.</p>':'<p class="state">Belum ada exception aktif.</p>'}</article>
      <article class="command-snapshot snapshot-card card" data-command-snapshot="production">${head('Produksi','layers')}${commandMeter('Rework dari WIP',`${n(rework)} / ${n(wip)} pcs`,wip?rework/wip:0,null,rework&&wip&&rework/wip>0.05?'is-over':'')}<dl class="command-values"><dt>Lewat target</dt><dd>${n(report.production.overdue_orders)} order</dd><dt>Dalam proses</dt><dd>${n(wip)} pcs</dd><dt>Rework</dt><dd>${n(rework)} pcs</dd></dl><button data-action="command-production-overdue">Buka papan produksi</button></article>
      <article class="command-snapshot snapshot-card card" data-command-snapshot="quality">${head('Kualitas produksi','shield')}${commandGauge(report.quality.first_pass_yield_percent,report.quality.attention_groups?'is-warn':'',`Periode ${date(report.quality.period_start)} sampai ${date(report.quality.as_of)}`)}<dl class="command-values"><dt>Diperiksa</dt><dd>${n(report.quality.inspected_quantity)} pcs</dd><dt>Yield</dt><dd>${e(report.quality.first_pass_yield_percent)}%</dd><dt>Rework + reject</dt><dd>${e(report.quality.nonconforming_rate_percent)}%</dd><dt>Perlu perhatian</dt><dd>${n(report.quality.attention_groups)} line/vendor</dd></dl><button data-action="production-quality-insights">Buka analisis kualitas</button></article>
      <article class="command-snapshot snapshot-card card" data-command-snapshot="capacity">${head('Kapasitas produksi','activity')}${commandMeter('Beban vs kapasitas',`${e(minuteQty(required))} / ${e(minuteQty(available))}`,available?required/available:(required?1:0),null,available&&required>available?'is-over':available&&required/available>0.85?'is-tight':'')}<dl class="command-values"><dt>Beban 14 hari</dt><dd>${e(minuteQty(required))}</dd><dt>Tersedia</dt><dd>${e(minuteQty(available))}</dd><dt>Perlu perhatian</dt><dd>${n(report.capacity.attention_work_centers)} work center</dd><dt>Order berisiko</dt><dd>${n(report.capacity.at_risk_orders)} order</dd></dl><p class="command-source">${report.capacity.capacity_complete?'Standar aktif lengkap':'Belum lengkap: '+n(report.capacity.coverage_gaps)+' kebutuhan tahap · '+n(report.capacity.missing_standard_quantity)+' pcs'} · sampai ${date(report.capacity.horizon_end)}</p><button data-action="capacity-plan">Buka rencana kapasitas</button></article>
      <article class="command-snapshot snapshot-card card" data-command-snapshot="workforce">${head('People','users')}${commandSplit3([
        {label:'Hadir',display:n(report.workforce.present),value:report.workforce.present},
        {label:'Cuti',display:n(report.workforce.leave),value:report.workforce.leave},
        {label:'Absen',display:n(report.workforce.absent),value:report.workforce.absent}
      ])}<dl class="command-values"><dt>Karyawan aktif</dt><dd>${n(report.workforce.active_employees)} orang</dd><dt>Belum dicatat</dt><dd>${n(report.workforce.unrecorded_employees)} orang</dd><dt>Lembur</dt><dd>${e(minuteQty(report.workforce.overtime_minutes))}</dd></dl><p class="command-source">Roster ${date(report.workforce.as_of)}</p><button data-action="command-workforce">Buka roster People</button></article>
      <article class="command-snapshot snapshot-card card" data-command-snapshot="inventory">${head('Stok &amp; bahan','box')}<dl class="command-values"><dt>SKU berisiko</dt><dd>${n(report.inventory.out_of_stock+report.inventory.at_risk)}</dd><dt>Perlu produksi</dt><dd>${n(report.inventory.recommended_production_quantity)} pcs</dd><dt>Bahan perlu dibeli</dt><dd>${n(report.inventory.materials_to_purchase)}</dd><dt>Mismatch Jubelio</dt><dd>${n(report.inventory.mismatched+report.inventory.missing_from_snapshot+report.inventory.quarantined)}</dd></dl><p class="command-source">${e(commandSource(report.inventory.snapshot_at))}</p><button data-action="replenishment">Buka rekomendasi stok</button></article>
      <article class="command-snapshot snapshot-card card" data-command-snapshot="sales">${head('Penjualan Jubelio','cart')}<dl class="command-values"><dt>Order diterima</dt><dd>${n(report.sales.accepted_orders)}</dd><dt>Unit selesai</dt><dd>${n(report.sales.units)} pcs</dd><dt>Pendapatan kotor</dt><dd>${e(commandMoney(report.sales.gross_revenue))}</dd><dt>Karantina</dt><dd>${n(report.sales.quarantined_orders)}</dd></dl><p class="command-source">${e(commandSource(report.sales.snapshot_at))}</p><button data-action="jubelio-order-summary">Buka penjualan Jubelio</button></article>
      <article class="command-snapshot snapshot-card card" data-command-snapshot="finance">${head('Keuangan Mekari','wallet')}${finance?`<dl class="command-values"><dt>Pendapatan bersih</dt><dd>${e(commandMoney(finance.net_revenue))}</dd><dt>Laba bersih</dt><dd>${e(commandMoney(finance.net_profit))}</dd><dt>Saldo kas</dt><dd>${e(commandMoney(finance.cash_balance))}</dd><dt>Utang outstanding</dt><dd>${e(commandMoney(report.finance.payables.outstanding))}</dd><dt>Piutang outstanding</dt><dd>${e(commandMoney(report.finance.receivables.outstanding))}</dd></dl>`:'<p class="state">Snapshot keuangan belum tersedia.</p>'}<p class="command-source">${e(commandSource(report.finance.snapshot_at))}</p><button data-action="mekari-finance-summary">Buka keuangan Mekari</button></article>
      <article class="command-snapshot snapshot-card card" data-command-snapshot="integrations">${head('Integrasi','plug')}<dl class="command-values">${report.integrations.systems.map(row=>`<dt>${e(row.label)}</dt><dd class="status-label ${row.health==='healthy'?'done':'late'}">${e(row.health==='healthy'?'Sehat':row.health==='failed'?'Gagal':row.health==='stale'?'Stale':row.health==='incomplete'?'Belum lengkap':'Belum sync')}</dd>`).join('')}</dl><button data-action="integrations">Buka kesehatan integrasi</button></article>
      <article class="command-snapshot snapshot-card card ai-card">${head('Tanya Beeloft','sparkles')}<div class="ai-orb" aria-hidden="true"></div><p class="ai-copy">Susun analisis operasional dari data yang sudah tersambung, lalu tinjau usulan tindakannya.</p><button data-action="ai-brain">Buka Tanya Beeloft</button></article>`;
    message('command-center-message','');$('command-center-content').hidden=false;
    $('command-center-updated').textContent='Diperbarui '+new Intl.DateTimeFormat('id-ID',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Jakarta'}).format(new Date(report.generated_at));
  }catch(error){if(version===epoch&&request===commandCenterRequest){$('command-center-summary').replaceChildren();$('command-center-summary').removeAttribute('aria-busy');for(const id of ['command-center-hero','command-center-channels','command-center-contribution','command-center-products','command-center-operations'])$(id).replaceChildren();$('command-center-period').textContent='';$('command-center-updated').textContent='';fail(error,'command-center-message');}}
}
$('command-center').onclick=showCommandCenter;
$('command-center-back').onclick=showBoard;
$('command-center-refresh').onclick=showCommandCenter;

async function loadBoard() {
  const version = epoch, request = ++boardRequest;
  message('board-message', 'Memuat posisi produksi…');
  $('order-list').hidden = true; $('previous').disabled = true; $('next').disabled = true;
  $('summary').setAttribute('aria-busy', 'true');
  try {
    const query = new URLSearchParams({q:$('search').value.trim(), status:$('status').value, owner_id:$('board-owner').value, stage:$('board-stage').value, limit:25, offset});
    const result = await api.get('/api/production-board?' + query);
    if (version !== epoch || request !== boardRequest || view !== 'board') return;
    boardData = result;
    const ownerId = query.get('owner_id'), previousOwnerLabel = $('board-owner').selectedOptions[0]?.textContent;
    $('board-owner').innerHTML = '<option value="">Semua PIC</option>' + result.owners.map(owner => option(owner.id,owner.name + (owner.active ? '' : ' (akun nonaktif)'))).join('');
    if (ownerId && !result.owners.some(owner => owner.id === ownerId)) $('board-owner').insertAdjacentHTML('beforeend',option(ownerId,previousOwnerLabel || 'PIC tidak lagi memiliki order'));
    $('board-owner').value = ownerId;
    $('issues-summary').classList.toggle('has-issues', result.open_issues > 0);
    $('issues-summary').innerHTML = `${svgIcon(result.open_issues > 0 ? 'alert-triangle' : 'check-circle')}`
      + `<span><strong>${n(result.open_issues)} kendala terbuka</strong><span class="issue-link"> · lihat order terkait</span></span>`;
    $('issues-summary').hidden = false;
    const s = result.summary;
    $('summary').innerHTML = [['Order aktif',s.active,'order','layers'],['Lewat target',s.overdue,'order','alert-triangle'],
      ['Dalam proses',s.in_progress,'pcs','activity'],['Perlu rework',s.rework,'pcs','undo']]
      .map(([label,value,unit,glyph]) => `<div${glyph === 'activity' ? ' class="production-wip"' : ''}><dt>${label}${svgIcon(glyph)}</dt><dd>${n(value)} <small>${unit}</small></dd></div>`).join('');
    $('summary').removeAttribute('aria-busy');
    $('updated').textContent = 'Diperbarui ' + new Intl.DateTimeFormat('id-ID',{hour:'2-digit',minute:'2-digit'}).format(new Date());
    if (!result.orders.length) {
      message('board-message', result.summary.orders ? 'Tidak ada order yang cocok. Ubah pencarian atau filter status.' :
        user.role === 'admin' ? 'Belum ada order. Tambahkan SKU lewat Master SKU, lalu buat order produksi pertama.' : 'Belum ada order produksi. Minta admin membuat order untuk tim.');
      $('order-list').replaceChildren();
    } else {
      message('board-message',''); $('order-list').hidden = false;
      $('order-list').innerHTML = '<div class="order-grid table-head" aria-hidden="true"><span>Order / produk</span><span>Penanggung jawab</span><span>Target selesai</span><span>Diterima gudang</span><span class="status-cell">Status</span></div>' + result.orders.map(order => {
        const progress = Math.round(order.totals.warehouse / order.target_quantity * 100);
        return `<article class="order-grid order-row"><div class="cell"><button class="order-title" data-action="detail" data-id="${e(order.id)}"><span class="reference">${e(order.reference)}</span>${e(order.title)}</button><span class="hint">${order.lines.length} SKU · target ${n(order.target_quantity)} pcs</span></div>
          <div class="cell"><span class="cell-label">PIC</span>${e(order.owner_name)}</div><div class="cell"><span class="cell-label">Target selesai</span>${date(order.due_date)}</div>
          <div class="cell progress-cell"><div class="progress-note"><span>${n(order.totals.warehouse)} / ${n(order.target_quantity)} pcs</span><strong>${progress}%</strong></div><progress value="${order.totals.warehouse}" max="${order.target_quantity}" aria-label="Jumlah diterima gudang ${e(order.reference)}"></progress></div><div class="cell status-cell">${statusHTML(order)}${issueBadge(order)}</div></article>`;
      }).join('');
    }
    $('page-count').textContent = result.total ? `${offset + 1}–${Math.min(offset + 25,result.total)} dari ${n(result.total)} order` : '0 order';
    $('previous').disabled = offset === 0; $('next').disabled = offset + 25 >= result.total;
  } catch (error) { if (version === epoch && request === boardRequest) { $('summary').replaceChildren(); $('issues-summary').hidden = true; $('updated').textContent = ''; fail(error, 'board-message'); } }
}

async function openDetail(id) {
  activateWorkspace('board-home','detail-view');
  const version = epoch, request = ++detailRequest;
  message('detail-message', 'Memuat order dan riwayat…'); $('detail-content').hidden = true;
  try {
    const [order, movements, blockers] = await Promise.all([api.get('/api/orders/' + encodeURIComponent(id)), api.get(`/api/orders/${encodeURIComponent(id)}/movements?limit=100`), api.get(`/api/orders/${encodeURIComponent(id)}/issues?limit=100`)]);
    if (version !== epoch || request !== detailRequest || view !== 'detail') return;
    selected = order; issues = blockers; issuesMore = blockers.length === 100; history = movements; historyOffset = movements.length;
    message('detail-message', ''); $('detail-content').hidden = false; renderDetail(movements.length === 100);
  } catch (error) { if (version === epoch && request === detailRequest) fail(error, 'detail-message'); }
}
function renderDetail(more) {
  const o = selected;
  $('detail-content').innerHTML = `<div class="detail-top"><div><p class="eyebrow">${e(o.reference)}</p><h1>${e(o.title)}</h1></div><button data-action="refresh-detail">Muat ulang order</button></div>
    <div class="detail-meta"><div><span>Penanggung jawab</span><strong>${e(o.owner_name)}</strong></div><div><span>Target selesai</span><strong>${date(o.due_date)}</strong></div><div><span>Target produksi</span><strong>${n(o.target_quantity)} pcs</strong></div><div><span>Status</span><strong>${statusHTML(o)}</strong></div></div>
    <div class="actions order-settings">${user.role === 'admin' ? '<button data-action="edit-order">Ubah tenggat / PIC</button>' : ''}${user.role !== 'viewer' ? '<button data-action="new-production-change-request">Ajukan perubahan tenggat / PIC</button>' : ''}<button class="quiet" data-action="production-change-requests">Riwayat permintaan perubahan</button><button class="quiet" data-action="order-changes">Riwayat tenggat / PIC</button><button data-action="requirements">Kebutuhan bahan</button><button data-action="reservations">Reservasi bahan</button><button data-action="consumption">Pemakaian &amp; waste</button><button data-action="production-cost">Biaya aktual</button><button data-action="contribution-margin">Margin kontribusi</button><button data-action="cutting-runs">Hasil cutting</button><button data-action="bundles">Bundle</button><button data-action="sewing-jobs">Sewing / makloon</button><button data-action="finishing-records">Finishing</button><button data-action="final-qc-records">Final QC</button><button data-action="rework-completions">Selesai rework</button><button data-action="finished-goods">Barang jadi</button><button data-action="warehouse">Gudang</button><button data-action="marketplace-reservations">Reservasi jual</button><button data-action="marketplace-picks">Picking</button><button data-action="marketplace-packs">Packing</button><button data-action="marketplace-shipments">Shipping</button><button data-action="marketplace-returns">Retur</button><button data-action="finished-goods-adjustments">Adjustment</button><button data-action="finished-goods-stock-counts">Stock opname</button>${user.role !== 'viewer' ? '<button data-action="issue-material">Keluarkan bahan ke order</button>' : ''}<button class="quiet" data-action="order-materials">Riwayat bahan order</button></div>
    <p><button data-action="order-purchases">PR untuk order ini</button></p>
    <h2>Posisi barang sekarang</h2><div class="stages">${stages.map((stage,index) => `<div class="stage"><small><span class="stage-number">0${index + 1}</span>${labels[stage]}</small><strong>${n(o.totals[stage])}</strong> <span class="hint">pcs</span></div>`).join('')}</div>
    <div class="exceptions"><span>Rework <strong>${n(o.totals.rework)} pcs</strong></span><span>Reject <strong>${n(o.totals.reject)} pcs</strong></span><span class="hint">Jumlah seluruh posisi: ${n(Object.values(o.totals).reduce((a,b) => a+b,0))} pcs</span></div>
    <h2>Rincian per SKU</h2>${o.lines.map(line => `<article class="sku-block"><div class="sku-heading"><div><h3>${e(line.sku)}</h3><span class="hint">${e(line.name)} · ${e([line.color,line.size].filter(Boolean).join(' / '))} · target ${n(line.quantity)} pcs</span></div>${user.role !== 'viewer' ? `<div class="actions"><button data-action="move" data-id="${e(line.id)}">Catat perpindahan</button><button data-action="new-issue" data-id="${e(line.id)}">Catat kendala</button></div>` : ''}</div><div class="sku-balances">${[...stages,'rework','reject'].map(stage => `<span>${labels[stage]}<strong>${n(line.balances[stage])}</strong></span>`).join('')}</div></article>`).join('')}
    <section class="history-section" aria-labelledby="issues-heading"><div class="history-heading"><h2 id="issues-heading">Kendala produksi · ${n(o.open_issues)} terbuka</h2><span class="hint">Catatan terbaru dahulu · waktu Jakarta</span></div><div id="issue-list"></div><button id="more-issues" data-action="more-issues" ${issuesMore ? '' : 'hidden'}>Muat kendala sebelumnya</button></section>
    <section class="history-section"><div class="history-heading"><h2>Riwayat perpindahan</h2><span class="hint">Urutan pencatatan terlama · waktu Jakarta</span></div><div id="history-list"></div><button id="more-history" data-action="more-history" ${more ? '' : 'hidden'}>Muat riwayat berikutnya</button></section>`;
  renderHistory(); renderIssues();
}
function renderHistory() {
  const reversed = new Set(history.map(item => item.reversal_of).filter(Boolean));
  $('history-list').innerHTML = history.length ? history.map(item => {
    const canReverse = user.role === 'admin' && !item.reversal_of && !reversed.has(item.id) && !item.cutting_run_id && !item.sewing_job_id && !item.finishing_record_id && !item.final_qc_record_id && !item.rework_completion_id;
    const timestamp = new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(item.created_at));
    return `<article class="history-item"><time datetime="${e(item.created_at)}">${timestamp}</time><div><strong>${n(item.quantity)} pcs · ${labels[item.from_stage]} → ${labels[item.to_stage]}</strong><p class="hint">${e(item.sku)} · dicatat ${e(item.actor_name)}${item.reversal_of ? ' · Catatan pembalik' : reversed.has(item.id) ? ' · Sudah dibalik' : ''}</p>${item.reason ? `<p class="reason">${e(item.reason)}</p>` : ''}</div>${item.cutting_run_id ? `<button data-action="cutting-run" data-id="${e(item.cutting_run_id)}">Hasil cutting</button>` : ''}${item.sewing_job_id ? `<button data-action="sewing-job" data-id="${e(item.sewing_job_id)}">Job sewing</button>` : ''}${item.finishing_record_id ? `<button data-action="finishing-record" data-id="${e(item.finishing_record_id)}">Finishing</button>` : ''}${item.final_qc_record_id ? `<button data-action="final-qc-record" data-id="${e(item.final_qc_record_id)}">Final QC</button>` : ''}${item.rework_completion_id ? `<button data-action="rework-completion" data-id="${e(item.rework_completion_id)}">Selesai rework</button>` : ''}${canReverse ? `<button class="quiet history-action" data-action="reverse" data-id="${e(item.id)}">Koreksi</button>` : ''}</article>`;
  }).join('') : '<p class="state">Belum ada perpindahan. Semua target masih berada di posisi belum cutting.</p>';
}
async function moreHistory(button) {
  const id = selected.id, version = epoch, request = detailRequest;
  button.disabled = true;
  try {
    const rows = await api.get(`/api/orders/${id}/movements?limit=100&offset=${historyOffset}`);
    if (version !== epoch || request !== detailRequest) return;
    history.push(...rows); historyOffset += rows.length; renderHistory(); button.hidden = rows.length < 100;
  } catch (error) { if (version === epoch && request === detailRequest) notify(error.message); }
  finally { button.disabled = false; }
}

// Seluruh tanggal bisnis memakai zona operasional Jakarta, bukan zona perangkat pemakai.
const jakartaToday=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Jakarta'}).format(new Date());
const option = (value,label) => `<option value="${e(value)}">${e(label)}</option>`;
const field = (name,label,type='text',attrs='') => `<label>${label}<input name="${name}" type="${type}" ${attrs}></label>`;
function openDialog(title, content) {
  dialogVersion++;
  $('dialog-title').textContent = title; $('dialog-content').innerHTML = content;
  modalBusy = false; unresolved = false; if (!$('dialog').open) $('dialog').showModal();
}

const auditCategories = {master_data:'Master data',production:'Produksi',materials:'Bahan baku',
  purchasing:'Pembelian',warehouse:'Gudang',marketplace:'Marketplace',approval:'Approval',
  ai:'AI',integration:'Integrasi'};
const auditStamp = value => new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',
  timeZone:'Asia/Jakarta'}).format(new Date(value));

function showAuditEvents() {
  if (guardPending()) return;
  activateWorkspace('audit-trail');
  loadAuditEvents();
}
// Milestone D: Audit trail adalah halaman workspace. Filter, cursor pagination, dan retry
// hidup di section; hanya rincian event mentah yang tetap dialog terfokus.
async function loadAuditEvents() {
  const version=epoch,request=++auditRequest,body=$('audit-body');
  const current=()=>version===epoch&&request===auditRequest&&view==='audit';
  body.innerHTML='<p class="state">Memuat audit trail…</p>';
  let rows=[],before=null;
  try {
    const users=await api.get('/api/users');
    if(!current())return;
    body.innerHTML=`<form id="audit-filter" class="filter-form"><div class="form-grid">
        <label class="full">Cari operasi, referensi, pelaku, atau request key<input name="q" maxlength="160" value="${e(auditFilters.q)}"></label>
        <div><label for="audit-category">Kategori</label><select id="audit-category" name="category"><option value="all">Semua kategori</option>${Object.entries(auditCategories).map(([key,label])=>option(key,label)).join('')}</select></div>
        <div><label for="audit-actor">Pelaku</label><select id="audit-actor" name="actor_id"><option value="">Semua pelaku</option>${users.map(item=>option(item.id,`${item.name} · ${item.role}`)).join('')}</select></div>
        ${field('start_date','Tanggal awal','date')}${field('end_date','Tanggal akhir','date')}
      </div><div class="form-actions"><button type="button" id="audit-reset">Reset</button><button class="primary" type="submit">Terapkan filter</button></div></form>
      <p id="audit-summary" class="hint" role="status"></p><p id="audit-error" class="error" role="alert" hidden></p>
      <div id="audit-list"></div><button id="audit-more" type="button">Muat catatan sebelumnya</button>`;
    $('audit-category').value=auditFilters.category;$('audit-actor').value=auditFilters.actor_id;
    $('audit-filter').elements.start_date.value=auditFilters.start_date;
    $('audit-filter').elements.end_date.value=auditFilters.end_date;
    const render=total=>{
      $('audit-summary').textContent=`${n(total)} catatan sesuai filter.`;
      $('audit-list').innerHTML=rows.length?rows.map(item=>`<article class="audit-event">
        <p class="status-label">${e(auditCategories[item.category])}</p>
        <h4>${e(item.subject_reference||item.operation)}</h4>
        <p>${e(item.operation)} · ${e(item.subject_type)}</p>
        <p class="hint">${e(item.actor_name)} · ${e(item.actor_role)} · ${auditStamp(item.created_at)}</p>
        <button type="button" data-action="audit-event" data-id="${e(item.id)}" aria-label="Rincian audit ${e(item.subject_reference||item.operation)}">Lihat rincian</button>
      </article>`).join(''):'<p class="state">Tidak ada catatan audit yang sesuai filter.</p>';
    };
    const load=async reset=>{
      if(reset){rows=[];before=null;}
      const button=$('audit-more');button.disabled=true;message('audit-error','');
      try{
        const params=new URLSearchParams({limit:'25',...auditFilters,...(before?{before:String(before)}:{})});
        for(const [key,value] of [...params])if(!value)params.delete(key);
        const page=await api.get('/api/audit-events?'+params);
        if(!current())return;
        rows.push(...page.items);before=page.next_before;render(page.total);
        button.hidden=!before;button.textContent='Muat catatan sebelumnya';
      }catch(error){if(current()){message('audit-error',error.message,true);button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('audit-filter').onsubmit=event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget));auditFilters={...data};load(true);};
    $('audit-reset').onclick=()=>{auditFilters={q:'',category:'all',actor_id:'',start_date:'',end_date:''};loadAuditEvents();};
    $('audit-more').onclick=()=>load(false);
    await load(true);
  }catch(error){if(current())body.innerHTML=`<p class="error">${e(error.message)}</p><button data-action="audit-events">Coba lagi</button>`;}
}

async function auditEventDialog(eventId) {
  if(guardPending())return;
  const version=epoch;
  openDialog('Rincian audit','<p class="state">Memuat rincian audit…</p>');
  const modal=dialogVersion;
  try{
    const item=await api.get('/api/audit-events/'+encodeURIComponent(eventId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-title').textContent=`Audit · ${item.subject_reference||item.operation}`;
    $('dialog-content').innerHTML=`<article class="audit-event"><p class="status-label">${e(auditCategories[item.category])}</p>
      <dl class="requirement-values"><div><dt>Operasi</dt><dd>${e(item.operation)}</dd></div><div><dt>Pelaku</dt><dd>${e(item.actor_name)} · ${e(item.actor_role)}</dd></div><div><dt>Waktu Jakarta</dt><dd>${auditStamp(item.created_at)}</dd></div><div><dt>Objek</dt><dd>${e(item.subject_type)} · ${e(item.subject_id||'-')}</dd></div><div><dt>Referensi</dt><dd>${e(item.subject_reference||'-')}</dd></div><div><dt>Request key</dt><dd>${e(item.request_key)}</dd></div></dl>
      <h3>Input perubahan</h3><pre class="audit-json">${e(JSON.stringify(item.changes,null,2))}</pre>
      <h3>Hasil tersimpan</h3><pre class="audit-json">${e(JSON.stringify(item.outcome,null,2))}</pre>
      <button type="button" data-action="audit-events">Kembali ke audit trail</button></article>`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="audit-event" data-id="${e(eventId)}">Coba lagi</button>`;}
}
function closeDialog() {
  if (modalBusy || unresolved) { notify('Konfirmasi penyimpanan lewat tombol coba ulang sebelum menutup.'); return; }
  dialogVersion++; $('dialog').close();
}
$('close-dialog').onclick = closeDialog;
$('dialog').addEventListener('cancel', event => { if (modalBusy || unresolved) { event.preventDefault(); notify('Penyimpanan belum terkonfirmasi. Gunakan coba ulang.'); } else dialogVersion++; });
$('dialog').addEventListener('close',()=>{const target=dialogReturnFocus;dialogReturnFocus=null;if(target&&!target.hidden)target.focus();});
function pendingKey() { return 'beeloft.pending.' + user.id; }
function readPending() {
  try { return JSON.parse(sessionStorage.getItem(pendingKey())); } catch { return null; }
}
function clearPending(storageKey, transaction) {
  try {
    const pending = JSON.parse(sessionStorage.getItem(storageKey));
    if (transaction && pending?.transaction?.key === transaction.key) sessionStorage.removeItem(storageKey);
  } catch {}
}
// Retry pencatatan yang belum pasti hanya boleh dikirim oleh akun pencatat aslinya. Cookie session
// dipakai bersama seluruh tab, sedangkan draft pending bersifat per tab, jadi tab lain dapat
// menukar session ke akun berbeda tanpa diketahui tab ini. Server menolak retry lintas akun dengan
// 403; pemeriksaan di sini hanya mempercepat diagnosanya dan tidak menggantikan penolakan server.
async function sameActorGuard(actorId) {
  const identity = await api.get('/api/me').catch(() => null);
  if (identity && identity.id !== actorId) {
    throw Object.assign(new Error('Session browser di perangkat ini sudah berpindah ke akun lain. '
      + 'Masuk ulang sebagai akun pencatat asli untuk menyelesaikan pencatatan yang belum pasti ini.'),
      {status: 403});
  }
}
function formDialog(title, fields, collect, path, info = '', initial = null) {
  openDialog(title, `<form id="action-form">${info ? `<p class="form-info">${e(info)}</p>` : ''}<fieldset id="form-fields"><div class="form-grid">${fields}</div></fieldset><p class="error" id="form-error" role="alert" hidden></p><div class="form-actions"><button type="button" data-action="cancel-form">Batal</button><button type="button" id="reauth" hidden>Masuk ulang</button><button class="primary" id="save-form" type="submit">Simpan pencatatan</button></div></form>`);
  let transaction = initial;
  const modalVersion = dialogVersion;
  $('reauth').onclick = () => reauthenticate('form-error');
  if (initial) { unresolved = true; $('form-fields').disabled = true; $('save-form').textContent = 'Coba ulang penyimpanan'; }
  $('action-form').onsubmit = async event => {
    event.preventDefault(); if (modalBusy) return;
    const version = epoch, actorId = user.id, storageKey = pendingKey();
    const button = $('save-form'); message('form-error', '');
    try {
      if (!transaction) transaction = api.transaction(path, collect(event.currentTarget));
      sessionStorage.setItem(storageKey, JSON.stringify({transaction, title, info, actor_id: actorId}));
      modalBusy = true; $('form-fields').disabled = true; button.disabled = true; $('reauth').disabled = true; button.textContent = 'Menyimpan…';
      if (initial || unresolved) await sameActorGuard(actorId);
      const result = await api.save(transaction);
      clearPending(storageKey, transaction);
      if (version !== epoch || user?.id !== actorId || modalVersion !== dialogVersion) return;
      modalBusy = false; unresolved = false; $('dialog').close();
      notify('Pencatatan tersimpan.');
      if (view === 'analytics') reloadAnalytics();
      if (path === '/api/orders') openDetail(result.id);
      else if ((path.startsWith('/api/marketplace-shipments/') && path.endsWith('/sale-settlements')) || path.startsWith('/api/marketplace-sale-settlements/')) marketplaceSaleSettlementDialog(result.id);
      else if ((path.startsWith('/api/marketplace-shipments/') && path.endsWith('/returns')) || path.startsWith('/api/marketplace-returns/')) marketplaceReturnDialog(result.id);
      else if ((path.startsWith('/api/finished-goods-receipts/') && path.endsWith('/stock-counts')) || path.startsWith('/api/finished-goods-stock-counts/')) finishedGoodsStockCountDialog(result.id);
      else if ((path.startsWith('/api/finished-goods-receipts/') && path.endsWith('/adjustments')) || path.startsWith('/api/finished-goods-adjustments/')) finishedGoodsAdjustmentDialog(result.id);
      else if (path.endsWith('/shipments') || path.startsWith('/api/marketplace-shipments/')) marketplaceShipmentDialog(result.id);
      else if (path.endsWith('/packs') || path.startsWith('/api/marketplace-packs/')) marketplacePackDialog(result.id);
      else if (path.endsWith('/picks') || path.startsWith('/api/marketplace-picks/')) marketplacePickDialog(result.id);
      else if (path.endsWith('/marketplace-reservations') || path.startsWith('/api/marketplace-reservations/')) marketplaceReservationDialog(result.id);
      else if (path.endsWith('/warehouse-movements') || path.startsWith('/api/warehouse-movements/')) warehouseMovementDialog(result.id);
      else if (path.endsWith('/finished-goods-receipts') || path.startsWith('/api/finished-goods-receipts/')) finishedGoodsReceiptDialog(result.id);
      else if (path.endsWith('/rework-completions') || (path.startsWith('/api/rework-completions/') && path.endsWith('/reverse'))) reworkCompletionDialog(result.id);
      else if (path.endsWith('/qc-records') || path.startsWith('/api/final-qc-records/')) finalQcRecordDialog(result.id);
      else if (path.endsWith('/finishing-records') || path.startsWith('/api/finishing-records/')) finishingRecordDialog(result.id);
      else if (path.endsWith('/sewing-jobs') || path.startsWith('/api/sewing-jobs/')) sewingJobDialog(result.id);
      else if (path.includes('/handoffs') || path.startsWith('/api/bundle-handoffs/')) bundleDialog(result.bundle_id);
      else if (path.endsWith('/bundles') || path.startsWith('/api/bundles/')) bundleDialog(result.id);
      else if (path.endsWith('/cutting-runs') || path.startsWith('/api/cutting-runs/')) {
        await openDetail(result.order_id);
        if(version===epoch)cuttingRunDialog(result.id);
      }
      else if (path.endsWith('/change-requests') || path.startsWith('/api/production-change-requests/')) productionChangeRequestDialog(result.id);
      else if (path.endsWith('/payment-requests') || path.startsWith('/api/supplier-payment-requests/')) supplierPaymentRequestDialog(result.id);
      else if (path.includes('/payroll-periods/') || path.startsWith('/api/payroll-approval-requests/')) payrollApprovalRequestDialog(result.id);
      else if (path === '/api/marketing-budget-requests' || path.startsWith('/api/marketing-budget-requests/')) marketingBudgetRequestDialog(result.id);
      else if (path === '/api/ai/investigations' || /^\/api\/ai\/investigations\/[^/]+\/feedback$/.test(path)) {
        // Simpan ulang melalui dialog pemulihan tetap menyegarkan riwayat di halaman AI.
        if (view === 'ai') loadAiHistory();
        aiInvestigationDetailDialog(result.id);
      }
      else if (path === '/api/ai/action-proposals' || path.startsWith('/api/ai/action-proposals/')) aiActionProposalDialog(result.id);
      else if (path === '/api/suppliers') suppliersDialog();
      else if (path.startsWith('/api/qc-') || path.startsWith('/api/supplier-returns/') || path.endsWith('/qc-intakes')) {
        if (view === 'materials') loadMaterials();
        qualityIntakeDialog(result.id);
      }
      else if (path.startsWith('/api/purchase-orders')) {
        if (result.purchase_order_id && view === 'materials') loadMaterials();
        purchaseOrderDialog(result.purchase_order_id || result.id);
      }
      else if (path.startsWith('/api/purchase-requests')) purchaseRequestDialog(result.id);
      else if (path === '/api/workforce/requests' || path.startsWith('/api/workforce/requests/')) workforceRequestDialog(result.id);
      else if (/^\/api\/workforce\/employees(\/[^/]+\/(changes|attendance))?$/.test(path)) { if (view === 'people') loadPeople(); }
      else if (/^\/api\/products\/[^/]+\/external-mappings\/jubelio$/.test(path)) { if (view === 'products') loadProducts(); productMappingDialog(result.product_id); }
      else if (/^\/api\/products\/[^/]+\/bom$/.test(path)) bomDialog(result.product_id);
      else if (view === 'materials') loadMaterials();
      else if (view === 'people') loadPeople();
      else if (view === 'products') loadProducts();
      else if (view === 'detail' && selected) openDetail(selected.id);
      else loadBoard();
    } catch (error) {
      if (version !== epoch || modalVersion !== dialogVersion) return;
      const denied = error.status === 401 || error.status === 403;
      unresolved = Boolean(error.uncertain || (unresolved && denied));
      if (!unresolved) { clearPending(storageKey, transaction); transaction = null; }
      message('form-error', error.message + (unresolved && denied ? ' Hasil pencatatan sebelumnya masih belum pasti. Masuk ulang dengan akun pencatat yang sama; jangan membuat ulang transaksi ini.' : ''), true);
      $('reauth').hidden = !denied;
      $('form-fields').disabled = unresolved;
      button.textContent = unresolved ? 'Coba ulang penyimpanan' : 'Simpan pencatatan';
    } finally { if (version === epoch && modalVersion === dialogVersion) { modalBusy = false; button.disabled = false; $('reauth').disabled = false; } }
  };
}
function recover(pending) {
  formDialog('Konfirmasi pencatatan sebelumnya', '', () => null, pending.transaction.path,
    `${pending.title}\n${pending.info || ''}\nHalaman ditutup sebelum hasil penyimpanan terkonfirmasi. Coba ulang untuk mendapatkan hasilnya tanpa menggandakan catatan.`, pending.transaction);
}
function guardPending() { const pending = readPending(); if (pending) { recover(pending); return true; } return false; }
function moveForm(lineId) {
  if (guardPending()) return;
  const line = selected.lines.find(item => item.id === lineId);
  const sources = Object.keys(line.balances).filter(stage => line.balances[stage] > 0 && transitions.some(([from]) => from === stage));
  if (!sources.length) {
    notify(line.balances.rework > 0
      ? 'Sisa jumlah berada di tahap rework. Catat penyelesaiannya dari rincian final QC melalui "Catat selesai rework", lalu lanjutkan dengan "Inspeksi ulang".'
      : 'Tidak ada saldo yang dapat dipindahkan. Koreksi transaksi melalui riwayat jika diperlukan.');
    return;
  }
  formDialog('Catat perpindahan', `<div><label for="move-source">Dari tahap</label><select name="from_stage" id="move-source">${sources.map(stage => option(stage,`${labels[stage]} · ${n(line.balances[stage])} pcs`)).join('')}</select></div><div><label for="move-target">Ke tahap</label><select name="to_stage" id="move-target"></select></div>${field('quantity','Jumlah (pcs)','number','required min="1" step="1" id="move-quantity"')}<p class="hint" id="move-balance"></p><label class="full">Alasan / catatan<textarea name="reason" id="move-reason" maxlength="1000"></textarea></label>`, form => {
    const data = new FormData(form);
    return {line_id:line.id, from_stage:data.get('from_stage'), to_stage:data.get('to_stage'), quantity:Number(data.get('quantity')), reason:data.get('reason').trim()};
  }, '/api/movements', `${selected.reference} · ${line.sku}\nPindahkan hanya jumlah yang benar-benar sudah diserahkan ke tahap berikutnya.`);
  function targetChanged() { $('move-reason').required = ['rework','reject'].includes($('move-target').value); }
  function sourceChanged() {
    const source = $('move-source').value;
    $('move-target').innerHTML = transitions.filter(([from]) => from === source).map(([,to]) => option(to,labels[to])).join('');
    $('move-quantity').max = line.balances[source];
    $('move-balance').textContent = `Saldo tersedia: ${n(line.balances[source])} pcs. Alasan wajib untuk rework/reject.`;
    targetChanged();
  }
  $('move-source').onchange = sourceChanged; $('move-target').onchange = targetChanged; sourceChanged();
}
function reverseForm(id) {
  if (guardPending()) return;
  const movement = history.find(item => item.id === id);
  formDialog('Koreksi dengan pembalikan', '<label class="full">Alasan koreksi<textarea name="reason" required maxlength="1000"></textarea></label>', form => ({reason:new FormData(form).get('reason').trim()}),
    `/api/movements/${id}/reverse`, `${movement.sku} · ${n(movement.quantity)} pcs\n${labels[movement.to_stage]} kembali ke ${labels[movement.from_stage]}. Seluruh jumlah pada catatan ini akan dikembalikan. Riwayat asli tetap tersimpan.`);
}
async function allRows(path, extra={}) {
  let rows = [], page;
  do { page = await api.get(path+(path.includes('?')?'&':'?')+new URLSearchParams({...extra,limit:500,offset:rows.length})); rows.push(...page); } while (page.length === 500);
  return rows;
}
// Master SKU sebagai halaman workspace: browse, pencarian, dan status mapping
// ada di permukaan halaman. Tambah SKU, BOM, dan mapping tetap dialog terfokus.
function showProducts() {
  activateWorkspace('products'); selected = null;
  $('new-product').hidden = user.role !== 'admin';
  loadProducts();
}
async function loadProducts() {
  const version = epoch, request = ++productsRequest;
  const search = $('products-search'), clear = $('products-clear');
  search.disabled = true; clear.disabled = true;
  message('products-message','Memuat daftar SKU…'); $('product-list').replaceChildren();
  try {
    const [products,mappings] = await Promise.all([allRows('/api/products'),allRows('/api/product-external-mappings',{system:'jubelio'})]);
    if (version !== epoch || request !== productsRequest || view !== 'products') return;
    const byProduct=new Map(mappings.map(row=>[row.product_id,row]));
    productsCache=products.map(product=>({...product,mapping:byProduct.get(product.id)}));
    paintProducts();
    search.disabled = false; clear.disabled = false;
  } catch (error) { if (version === epoch && request === productsRequest && view === 'products') {
    message('products-message',error.message,true);
    $('products-message').insertAdjacentHTML('beforeend','<br><button id="products-retry" type="button">Coba lagi</button>');
    $('products-retry').onclick=loadProducts;
  } }
}
function paintProducts() {
  const q=$('products-search').value.trim().toLowerCase();
  const rows=!q?productsCache:productsCache.filter(p=>[p.sku,p.name,[p.color,p.size].filter(Boolean).join(' / '),p.mapping?.external_sku||''].some(value=>value.toLowerCase().includes(q)));
  message('products-message',productsCache.length?(rows.length?'':'Tidak ada SKU yang cocok dengan pencarian ini.'):'Belum ada SKU. Tambahkan produk untuk membuat order pertama.');
  $('product-list').innerHTML=rows.length?rows.map(p=>{const mapping=p.mapping;return `<div class="product-item"><div><strong>${e(p.sku)}</strong><span class="hint">${e(p.name)} · ${e([p.color,p.size].filter(Boolean).join(' / '))}</span><span class="hint">Jubelio · ${mapping?.status==='mapped'?e(mapping.external_sku):'Belum dipetakan'}</span></div><div class="actions"><button type="button" data-action="product-mapping" data-id="${e(p.id)}" aria-label="Jubelio ${e(p.sku)}">Jubelio</button><button type="button" data-action="bom" data-id="${e(p.id)}" aria-label="BOM ${e(p.sku)}">BOM</button></div></div>`;}).join(''):'';
}
function productForm() {
  if (guardPending()) return;
  formDialog('Tambah SKU', field('sku','Kode SKU','text','required maxlength="160"') + field('name','Nama produk','text','required maxlength="160"') + field('color','Warna','text','maxlength="80"') + field('size','Ukuran','text','maxlength="40"'), form => Object.fromEntries(new FormData(form)), '/api/products', 'Gunakan satu kode SKU untuk setiap kombinasi produk, warna, dan ukuran.');
}
async function productMappingDialog(productId) {
  if (guardPending()) return;
  const version=epoch;openDialog('Mapping SKU Jubelio','<p class="state">Memuat mapping…</p>');const modal=dialogVersion;
  try {
    const row=await api.get(`/api/products/${encodeURIComponent(productId)}/external-mappings/jubelio`);
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const mapped=row.status==='mapped';
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.sku)} · ${e(row.product_name)}</p><p class="hint">Jubelio adalah sumber order marketplace dan stok jual. Mapping ini hanya mencocokkan identitas; belum menjalankan sinkronisasi.</p><article class="material-event"><h3>${mapped?'Terhubung':'Belum dipetakan'}</h3>${mapped?`<p>SKU Jubelio <strong>${e(row.external_sku)}</strong></p><p>ID eksternal <strong>${e(row.external_id)}</strong></p><p class="reason">${e(row.reason)}</p><p class="hint">Revisi ${n(row.revision)} · ${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>`:'<p>Worker tidak boleh mengimpor data untuk SKU ini sebelum identitas Jubelio dipetakan.</p>'}</article><div class="actions">${user.role==='admin'?`<button class="primary" data-action="edit-product-mapping" data-id="${e(productId)}">${mapped?'Ubah mapping':'Hubungkan Jubelio'}</button>${mapped?`<button data-action="unmap-product" data-id="${e(productId)}">Lepaskan mapping</button>`:''}`:''}<button data-action="product-mapping-history" data-id="${e(productId)}">Riwayat mapping</button><button data-action="products">Kembali ke Master SKU</button></div>`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="product-mapping" data-id="${e(productId)}">Coba lagi</button>`;}
}
async function productMappingForm(productId) {
  if(guardPending())return;
  const version=epoch, row=await api.get(`/api/products/${encodeURIComponent(productId)}/external-mappings/jubelio`);
  if(version!==epoch)return;
  formDialog(row.status==='mapped'?'Ubah mapping Jubelio':'Hubungkan SKU ke Jubelio',field('external_id','ID eksternal Jubelio','text','required maxlength="160"')+field('external_sku','SKU Jubelio','text','required maxlength="160"')+'<label class="full">Alasan mapping<textarea name="reason" required maxlength="1000"></textarea></label>',form=>{const data=new FormData(form);return {expected_revision:row.revision,action:'mapped',external_id:data.get('external_id').trim(),external_sku:data.get('external_sku').trim(),reason:data.get('reason').trim()};},`/api/products/${encodeURIComponent(productId)}/external-mappings/jubelio`,`${row.sku} · simpan identifier persis seperti yang diberikan Jubelio.`);
  $('action-form').elements.external_id.value=row.external_id;$('action-form').elements.external_sku.value=row.external_sku;
}
async function unmapProductForm(productId) {
  if(guardPending())return;
  const version=epoch,row=await api.get(`/api/products/${encodeURIComponent(productId)}/external-mappings/jubelio`);
  if(version!==epoch||row.status!=='mapped')return productMappingDialog(productId);
  formDialog('Lepaskan mapping Jubelio','<label class="full">Alasan pelepasan<textarea name="reason" required maxlength="1000"></textarea></label>',form=>({expected_revision:row.revision,action:'unmapped',external_id:'',external_sku:'',reason:new FormData(form).get('reason').trim()}),`/api/products/${encodeURIComponent(productId)}/external-mappings/jubelio`,`${row.sku} · ${row.external_sku}\nWorker tidak boleh mencocokkan SKU ini setelah mapping dilepas.`);
}
async function productMappingHistoryDialog(productId) {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat mapping Jubelio','<div id="product-mapping-history"><p class="state">Memuat riwayat…</p></div><p id="product-mapping-history-error" class="error" role="alert" hidden></p><button id="product-mapping-history-more">Muat riwayat sebelumnya</button>');const modal=dialogVersion;let before=null;
  async function load(){const button=$('product-mapping-history-more');button.disabled=true;message('product-mapping-history-error','');try{const rows=await api.get(`/api/products/${encodeURIComponent(productId)}/external-mappings/jubelio/history?`+new URLSearchParams({limit:20,...(before?{before}:{})}));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;if(!before)$('product-mapping-history').replaceChildren();appendRows('product-mapping-history',rows.map(row=>`<article class="material-event"><h3>Revisi ${n(row.revision)} · ${row.status==='mapped'?'Terhubung':'Dilepas'}</h3>${row.status==='mapped'?`<p>${e(row.external_sku)} · ${e(row.external_id)}</p>`:''}<p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p></article>`).join(''));if(!before&&!rows.length)$('product-mapping-history').innerHTML='<p class="state">Belum ada riwayat mapping.</p>';before=rows.at(-1)?.sequence||before;button.hidden=rows.length<20;}catch(error){if(version===epoch&&modal===dialogVersion){message('product-mapping-history-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}finally{button.disabled=false;}}
  $('product-mapping-history-more').onclick=load;await load();
}
async function orderForm() {
  if (guardPending()) return;
  const version = epoch;
  openDialog('Buat order produksi', '<p class="state">Memuat SKU dan penanggung jawab…</p>');
  const modalVersion = dialogVersion;
  try {
    const [products, users] = await Promise.all([allRows('/api/products'), api.get('/api/users')]);
    if (version !== epoch || modalVersion !== dialogVersion || !$('dialog').open) return;
    if (!products.length) { $('dialog-content').innerHTML = '<p>Tambahkan minimal satu SKU sebelum membuat order.</p><button class="primary" data-action="new-product">Tambah SKU</button>'; return; }
    formDialog('Buat order produksi', field('reference','Referensi order','text','required maxlength="160"') + field('title','Nama order','text','required maxlength="160"') +
      `<div><label for="order-owner">Penanggung jawab</label><select id="order-owner" name="owner_id" required>${users.filter(u => u.active && u.role !== 'viewer').map(u => option(u.id,u.name)).join('')}</select></div>` + field('due_date','Target selesai','date','required') +
      '<div class="full"><h3>Produk yang dikerjakan</h3><div id="order-lines"></div><button type="button" id="add-line">Tambah baris SKU</button></div>', form => {
        const data = new FormData(form);
        const lines = [...form.querySelectorAll('.line-input')].map(row => ({product_id:row.querySelector('select').value, quantity:Number(row.querySelector('input').value)}));
        if (new Set(lines.map(line => line.product_id)).size !== lines.length) throw new Error('SKU yang sama cukup satu baris. Gabungkan jumlahnya.');
        return {reference:data.get('reference').trim(),title:data.get('title').trim(),owner_id:data.get('owner_id'),due_date:data.get('due_date'),lines};
      }, '/api/orders');
    function addLine() {
      const count = $('order-lines').children.length;
      if (count >= 100) return;
      const row = document.createElement('div'); row.className = 'line-input';
      const selectId = 'sku-' + crypto.randomUUID();
      row.innerHTML = `<div><label for="${selectId}">SKU</label><select id="${selectId}" required>${products.map(p => option(p.id,p.sku)).join('')}</select></div><label>Jumlah<input type="number" required min="1" max="1000000000" step="1"></label><button type="button" aria-label="Hapus baris SKU">Hapus</button>`;
      row.querySelector('button').onclick = () => { if ($('order-lines').children.length > 1) row.remove(); else notify('Order memerlukan minimal satu SKU.'); };
      $('order-lines').append(row);
    }
    $('add-line').onclick = addLine; addLine();
  } catch (error) { if (version === epoch && modalVersion === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="new-order">Coba lagi</button>`; }
}
$('products').onclick = showProducts; $('new-order').onclick = orderForm;
$('audit-trail').onclick = showAuditEvents;
$('workforce').onclick = showPeople;
$('scan-bundle').onclick = bundleScanDialog;
$('scan-finished-goods').onclick = finishedGoodsScanDialog;
document.addEventListener('click', event => {
  const button = event.target.closest('[data-action]'); if (!button || button.disabled) return;
  const id = button.dataset.id, output = button.dataset.output, kind = button.dataset.kind;
  const actions = {detail:() => openDetail(id),move:() => moveForm(id),reverse:() => reverseForm(id),
    'new-issue':() => issueForm(id),'resolve-issue':() => resolveIssueForm(id),'more-issues':() => moreIssues(button),
    'edit-order':editOrderForm,'order-changes':orderChangesDialog,
    'new-production-change-request':productionChangeRequestForm,'production-change-requests':()=>productionChangeRequestsDialog(id || selected?.id),
    'production-change-request':()=>productionChangeRequestDialog(id),'approvals':approvalsDialog,
    'purchase-requests':()=>purchaseRequestsDialog(),'order-purchases':()=>purchaseRequestsDialog(selected.id),
    'purchase-request':()=>purchaseRequestDialog(id),'new-purchase-request':()=>purchaseRequestForm(id || null),
    suppliers:suppliersDialog,'new-supplier':supplierForm,'purchase-orders':purchaseOrdersDialog,
    'new-purchase-order':()=>purchaseOrderForm(id),'purchase-order':()=>purchaseOrderDialog(id),
    'new-supplier-payment':()=>supplierPaymentForm(id),'supplier-payment-request':()=>supplierPaymentRequestDialog(id),
    'marketing-budgets':marketingBudgetsDialog,'new-marketing-budget':marketingBudgetForm,
    'marketing-budget-request':()=>marketingBudgetRequestDialog(id),
    'receive-po':()=>purchaseReceiptForm(id),'qc-intake-form':()=>purchaseReceiptForm(id,true),
    'qc-intake':()=>qualityIntakeDialog(id),
    'new-material':materialForm,'material-master':materialMasterDialog,'receive-material':receiptForm,
    bom:() => bomDialog(id),'edit-bom':() => bomForm(id),'bom-history':() => bomHistoryDialog(id),requirements:requirementsDialog,
    'product-mapping':()=>productMappingDialog(id),'edit-product-mapping':()=>productMappingForm(id),
    'unmap-product':()=>unmapProductForm(id),'product-mapping-history':()=>productMappingHistoryDialog(id),
    'cutting-runs':()=>cuttingRunsDialog(id || selected?.id),'new-cutting':()=>cuttingForm(id),'cutting-run':()=>cuttingRunDialog(id),
    bundles:()=>bundlesDialog(id || selected?.id),'new-bundle':()=>bundleForm(id,output),bundle:()=>bundleDialog(id),'scan-bundle':bundleScanDialog,
    'bundle-handoffs':()=>bundleHandoffsDialog(id),'new-bundle-handoff':()=>bundleHandoffForm(id),
    'accept-bundle-handoff':()=>acceptBundleHandoffForm(id),'cancel-bundle-handoff':()=>cancelBundleHandoffForm(id),
    'sewing-jobs':()=>sewingJobsDialog(id || selected?.id),'new-sewing-job':()=>sewingJobForm(id),'sewing-job':()=>sewingJobDialog(id),
    'finishing-records':()=>finishingRecordsDialog(id || selected?.id),'new-finishing-record':()=>finishingForm(id),'finishing-record':()=>finishingRecordDialog(id),
    'final-qc-records':()=>finalQcRecordsDialog(id || selected?.id),'new-final-qc-record':()=>finalQcForm(id),'final-qc-record':()=>finalQcRecordDialog(id),
    'rework-completions':()=>reworkCompletionsDialog(id || selected?.id),'final-qc-rework-completions':()=>finalQcReworkCompletionsDialog(id),
    'new-rework-completion':()=>reworkCompletionForm(id),'rework-completion':()=>reworkCompletionDialog(id),'new-reinspection':()=>reinspectionForm(id),
    'finished-goods':()=>finishedGoodsDialog(id || selected?.id),'new-finished-goods':()=>finishedGoodsForm(id),'finished-goods-receipt':()=>finishedGoodsReceiptDialog(id),'scan-finished-goods':finishedGoodsScanDialog,
    'finished-goods-traceability':()=>finishedGoodsTraceabilityDialog(id),
    warehouse:()=>warehouseDialog(id || selected?.id),'new-warehouse-movement':()=>warehouseMovementForm(id,kind),'warehouse-movement':()=>warehouseMovementDialog(id),
    'marketplace-reservations':()=>marketplaceReservationsDialog(id || selected?.id),'new-marketplace-reservation':()=>marketplaceReservationForm(id),'marketplace-reservation':()=>marketplaceReservationDialog(id),
    'marketplace-picks':()=>marketplacePicksDialog(id || selected?.id),'new-marketplace-pick':()=>marketplacePickForm(id),'marketplace-pick':()=>marketplacePickDialog(id),
    'marketplace-packs':()=>marketplacePacksDialog(id || selected?.id),'new-marketplace-pack':()=>marketplacePackForm(id),'marketplace-pack':()=>marketplacePackDialog(id),
    'marketplace-shipments':()=>marketplaceShipmentsDialog(id || selected?.id),'new-marketplace-shipment':()=>marketplaceShipmentForm(id),'marketplace-shipment':()=>marketplaceShipmentDialog(id),
    'new-sale-settlement':()=>marketplaceSaleSettlementForm(id),'sale-settlement':()=>marketplaceSaleSettlementDialog(id),'contribution-margin':()=>contributionMarginDialog(id || selected?.id),
    'marketplace-returns':()=>marketplaceReturnsDialog(id || selected?.id),'new-marketplace-return':()=>marketplaceReturnForm(id),'marketplace-return':()=>marketplaceReturnDialog(id),
    'finished-goods-adjustments':()=>finishedGoodsAdjustmentsDialog(id || selected?.id),'new-finished-goods-adjustment':()=>finishedGoodsAdjustmentForm(id),'finished-goods-adjustment':()=>finishedGoodsAdjustmentDialog(id),
    'finished-goods-stock-counts':()=>finishedGoodsStockCountsDialog(id || selected?.id),'new-finished-goods-stock-count':()=>finishedGoodsStockCountForm(id),'finished-goods-stock-count':()=>finishedGoodsStockCountDialog(id),
    consumption:consumptionDialog,'production-cost':productionCostDialog,'record-consumption':()=>consumptionForm(id),reservations:reservationsDialog,'reserve-material':()=>reservationForm('reserve'),'release-material':()=>reservationForm('release'),
    'material-batch':() => materialHistoryDialog(id),'material-batch-traceability':()=>materialBatchTraceabilityDialog(id),'scan-material-batch':materialBatchScanDialog,'issue-material':materialIssueForm,
    'order-materials':() => materialHistoryDialog(null,selected),
    'refresh-detail':() => openDetail(selected.id),'more-history':() => moreHistory(button),
    products:()=>navigateFromDialog(showProducts),approvals:approvalsDialog,'ai-brain':()=>navigateFromDialog(showAi),
    'ai-investigation':()=>aiInvestigationDetailDialog(id),'ai-action-proposal':()=>aiActionProposalDialog(id),
    integrations:()=>navigateFromDialog(showIntegrations),'integration-runs':integrationRunsDialog,
    'integration-run':()=>integrationRunDialog(id),
    'jubelio-stock-reconciliation':jubelioStockReconciliationDialog,
    'jubelio-stock-snapshots':jubelioStockSnapshotsDialog,
    'jubelio-stock-snapshot':()=>jubelioStockSnapshotDialog(id),
    'jubelio-order-summary':jubelioOrderSummaryDialog,
    'jubelio-order-snapshots':jubelioOrderSnapshotsDialog,
    'jubelio-order-snapshot':()=>jubelioOrderSnapshotDialog(id),
    'jubelio-return-summary':jubelioReturnSummaryDialog,
    'jubelio-return-snapshots':jubelioReturnSnapshotsDialog,
    'jubelio-return-snapshot':()=>jubelioReturnSnapshotDialog(id),
    'jubelio-listing-summary':jubelioListingSummaryDialog,
    'jubelio-listing-snapshots':jubelioListingSnapshotsDialog,
    'jubelio-listing-snapshot':()=>jubelioListingSnapshotDialog(id),
    'mekari-finance-summary':mekariFinanceSummaryDialog,
    'mekari-finance-snapshots':mekariFinanceSnapshotsDialog,
    'mekari-finance-snapshot':()=>mekariFinanceSnapshotDialog(id),
    'mekari-payables-summary':mekariPayablesSummaryDialog,
    'mekari-payable-snapshots':mekariPayableSnapshotsDialog,
    'mekari-payable-snapshot':()=>mekariPayableSnapshotDialog(id),
    'mekari-receivables-summary':mekariReceivablesSummaryDialog,
    'mekari-receivable-snapshots':mekariReceivableSnapshotsDialog,
    'mekari-receivable-snapshot':()=>mekariReceivableSnapshotDialog(id),
    'mekari-payroll-summary':mekariPayrollSummaryDialog,
    'mekari-payroll-snapshots':mekariPayrollSnapshotsDialog,
    'mekari-payroll-snapshot':()=>mekariPayrollSnapshotDialog(id),
    'payroll-payment-reconciliation':payrollPaymentReconciliationDialog,
    'payroll-accounting-reconciliation':payrollAccountingReconciliationDialog,
    'new-payroll-approval':()=>payrollApprovalForm(id),
    'payroll-approval-request':()=>payrollApprovalRequestDialog(id),
    'command-center':showCommandCenter,'command-production-overdue':()=>showCommandOrders('overdue'),
    'command-production-issues':()=>showCommandOrders('blocked'),
    'command-workforce':()=>{workforceFilters={work_date:jakartaToday(),status:'all',q:''};navigateFromDialog(showPeople);},
    'audit-events':()=>navigateFromDialog(showAuditEvents),'audit-event':()=>auditEventDialog(id),
    'demand-forecast':showDemandForecast,replenishment:showReplenishment,
    workforce:()=>navigateFromDialog(showPeople),'employee-master':workforceEmployeeMasterDialog,
    'new-employee':()=>workforceEmployeeForm(),'edit-employee':()=>workforceEmployeeForm(id),
    'employee-history':()=>workforceEmployeeHistoryDialog(id),
    'attendance-form':()=>workforceAttendanceForm(id,button.dataset.date),
    'attendance-history':()=>workforceAttendanceHistoryDialog(id),
    'workforce-requests':workforceRequestsDialog,'new-workforce-request':workforceRequestForm,
    'workforce-request':()=>workforceRequestDialog(id),
    'workforce-request-decision':()=>workforceRequestDecisionForm(id,button.dataset.status),
    'capacity-plan':showCapacityPlan,'production-quality-insights':showProductionQualityInsights,
    'new-work-center':()=>capacityWorkCenterForm(),
    'edit-work-center':()=>capacityWorkCenterForm(id),'new-product':productForm,
    'new-order':orderForm,'cancel-form':closeDialog};
  actions[button.dataset.action]?.();
});

function renderIssues() {
  const timestamp = value => new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(value));
  $('issue-list').innerHTML = issues.length ? issues.map(item => `<article class="issue-item">
    <div class="issue-heading"><strong>${e(item.sku)} · ${labels[item.stage]}</strong><span class="status-label ${item.resolved_at ? 'done' : 'late'}">${item.resolved_at ? 'Selesai' : 'Terbuka'}</span></div>
    <p class="reason">${e(item.description)}</p><p class="hint">PIC: ${e(item.owner_name)}${item.owner_active ? '' : ' (akun nonaktif)'} · dicatat ${e(item.creator_name)} · ${timestamp(item.created_at)}</p>
    ${item.resolved_at ? `<div class="issue-resolution"><strong>Penyelesaian</strong><p class="reason">${e(item.resolution)}</p><p class="hint">${e(item.resolver_name)} · ${timestamp(item.resolved_at)}</p></div>` : user.role !== 'viewer' ? `<button data-action="resolve-issue" data-id="${e(item.id)}">Selesaikan kendala</button>` : ''}
    </article>`).join('') : '<p class="state">Belum ada kendala yang dicatat untuk order ini.</p>';
}
async function moreIssues(button) {
  const version = epoch, request = detailRequest, id = selected.id;
  button.disabled = true;
  try {
    const rows = await api.get(`/api/orders/${id}/issues?limit=100&before=${issues.at(-1).sequence}`);
    if (version !== epoch || request !== detailRequest) return;
    const known = new Set(issues.map(i => i.id));
    issues.push(...rows.filter(i => !known.has(i.id))); issuesMore = rows.length === 100;
    renderIssues(); button.hidden = !issuesMore;
  } catch (error) { if (version === epoch && request === detailRequest) notify(error.message); }
  finally { button.disabled = false; }
}
async function issueForm(lineId) {
  if (guardPending()) return;
  const version = epoch, order = selected, line = order.lines.find(item => item.id === lineId);
  openDialog('Catat kendala', '<p class="state">Memuat penanggung jawab…</p>');
  const modalVersion = dialogVersion;
  try {
    const users = await api.get('/api/users');
    if (version !== epoch || modalVersion !== dialogVersion || !$('dialog').open) return;
    formDialog('Catat kendala', `<div><label for="issue-stage">Tahap yang terkendala</label><select id="issue-stage" name="stage">${Object.keys(labels).map(stage => option(stage,labels[stage])).join('')}</select></div>
      <div><label for="issue-owner">PIC kendala</label><select id="issue-owner" name="owner_id" required>${users.filter(u => u.active && u.role !== 'viewer').map(u => option(u.id,u.name)).join('')}</select></div>
      <label class="full">Apa kendalanya?<textarea name="description" required maxlength="1000"></textarea></label>`, form => ({line_id:line.id,...Object.fromEntries(new FormData(form))}), '/api/issues', `${order.reference} · ${line.sku}\nCatat hambatan dan orang yang akan menindaklanjutinya.`);
    if (users.some(u => u.id === order.owner_id && u.active && u.role !== 'viewer')) $('issue-owner').value = order.owner_id;
  } catch (error) { if (version === epoch && modalVersion === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="new-issue" data-id="${e(lineId)}">Coba lagi</button>`; }
}
function resolveIssueForm(id) {
  if (guardPending()) return;
  const issue = issues.find(item => item.id === id);
  formDialog('Selesaikan kendala', '<label class="full">Tindakan penyelesaian<textarea name="resolution" required maxlength="1000"></textarea></label>', form => Object.fromEntries(new FormData(form)),
    `/api/issues/${id}/resolve`, `${issue.sku} · ${labels[issue.stage]}\n${issue.description}\nCatatan penyelesaian akan tersimpan beserta nama pencatatnya.`);
}

async function editOrderForm() {
  if (guardPending()) return;
  const version = epoch, order = selected;
  openDialog('Ubah tenggat / PIC', '<p class="state">Memuat penanggung jawab…</p>');
  const modalVersion = dialogVersion;
  try {
    const users = await api.get('/api/users');
    if (version !== epoch || modalVersion !== dialogVersion || !$('dialog').open) return;
    const owners = users.filter(u => u.active && u.role !== 'viewer');
    formDialog('Ubah tenggat / PIC', field('due_date','Target selesai baru','date','required id="edit-due"') +
      `<div><label for="edit-owner">PIC order</label><select id="edit-owner" name="owner_id" required><option value="">Pilih PIC aktif</option>${owners.map(u => option(u.id,u.name)).join('')}</select></div>
      <label class="full">Alasan perubahan<textarea name="reason" required maxlength="1000"></textarea></label>`, form => ({...Object.fromEntries(new FormData(form)),expected_revision:order.revision}),
      `/api/orders/${order.id}/changes`, `${order.reference}\nSaat ini: ${date(order.due_date)} · ${order.owner_name}\nPerubahan ini berlaku untuk order. PIC kendala yang sudah dicatat tetap mengikuti catatannya masing-masing.`);
    $('edit-due').value = order.due_date;
    $('edit-owner').value = owners.some(u => u.id === order.owner_id) ? order.owner_id : '';
  } catch (error) { if (version === epoch && modalVersion === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="edit-order">Coba lagi</button>`; }
}
async function orderChangesDialog() {
  if (guardPending()) return;
  const version = epoch, order = selected;
  openDialog('Riwayat tenggat / PIC', `<p class="form-info">${e(order.reference)} · Catatan terbaru dahulu · waktu Jakarta</p><div id="order-change-list"></div><p id="changes-message" role="status"></p><button id="more-changes" type="button" hidden>Muat perubahan sebelumnya</button>`);
  const modalVersion = dialogVersion;
  let before = null;
  const current = () => version === epoch && modalVersion === dialogVersion && $('dialog').open;
  async function load() {
    if (!current()) return;
    const button = $('more-changes'); button.disabled = true;
    message('changes-message','Memuat riwayat…');
    try {
      const rows = await api.get(`/api/orders/${order.id}/changes?limit=100${before ? '&before=' + before : ''}`);
      if (!current()) return;
      message('changes-message', rows.length || before ? '' : 'Belum ada perubahan. Tenggat dan PIC masih sesuai saat order dibuat.');
      appendRows('order-change-list', rows.map(item => {
        const timestamp = new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(item.created_at));
        return `<article class="issue-item"><strong>${timestamp}</strong>
          ${item.old_due_date !== item.new_due_date ? `<p>Tenggat: ${date(item.old_due_date)} → ${date(item.new_due_date)}</p>` : ''}
          ${item.old_owner_id !== item.new_owner_id ? `<p>PIC: ${e(item.old_owner_name)} → ${e(item.new_owner_name)}</p>` : ''}
          <p class="reason">${e(item.reason)}</p><p class="hint">Diubah oleh ${e(item.actor_name)}</p></article>`;
      }).join(''));
      if (rows.length) before = rows.at(-1).sequence;
      button.textContent = 'Muat perubahan sebelumnya'; button.hidden = rows.length < 100;
    } catch (error) { if (current()) { message('changes-message',error.message,true); button.hidden = false; button.textContent = 'Coba lagi'; } }
    finally { if (current()) button.disabled = false; }
  }
  $('more-changes').onclick = load;
  await load();
}

async function productionChangeRequestForm() {
  if(guardPending())return;
  const version=epoch,order=selected;
  openDialog('Ajukan perubahan produksi','<p class="state">Memuat penanggung jawab...</p>');const modal=dialogVersion;
  try{
    const users=await api.get('/api/users');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const owners=users.filter(row=>row.active&&row.role!=='viewer');
    formDialog('Ajukan perubahan produksi',field('reference','Referensi permintaan','text','required maxlength="160"')+
      field('due_date','Target selesai yang diajukan','date','required id="request-due"')+
      `<div><label for="request-owner">PIC yang diajukan</label><select id="request-owner" name="owner_id" required>${owners.map(row=>option(row.id,row.name)).join('')}</select></div>`+
      '<label class="full">Alasan perubahan<textarea name="reason" required maxlength="1000"></textarea></label>',
      form=>({...Object.fromEntries(new FormData(form)),expected_revision:order.revision}),
      '/api/orders/'+encodeURIComponent(order.id)+'/change-requests',
      `${order.reference}\nSaat ini: ${date(order.due_date)} · ${order.owner_name}\nOrder tidak berubah sebelum admin menyetujui. Satu order hanya dapat memiliki satu permintaan yang masih menunggu.`);
    $('request-due').value=order.due_date;
    $('request-owner').value=owners.some(row=>row.id===order.owner_id)?order.owner_id:'';
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-production-change-request">Coba lagi</button>`;}
}

async function productionChangeRequestsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Permintaan perubahan produksi','<p class="state">Memuat riwayat permintaan...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const order=await api.get('/api/orders/'+encodeURIComponent(orderId));
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Permintaan menyimpan nilai sebelum dan sesudah. Order baru berubah setelah admin menyetujui.</p>${user.role!=='viewer'?`<button data-action="new-production-change-request">Ajukan perubahan</button>`:''}<button data-action="approvals">Inbox approval</button><div id="production-change-request-list"><p class="state">Memuat permintaan...</p></div><p id="production-change-request-error" class="error" role="alert" hidden></p><button id="production-change-request-more" type="button">Muat permintaan sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('production-change-request-more');button.disabled=true;message('production-change-request-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/change-requests?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('production-change-request-list').replaceChildren();
        appendRows('production-change-request-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${e(approvalStatus[row.status])}</h3><p>Target ${date(row.old_due_date)} → ${date(row.new_due_date)}</p><p>PIC ${e(row.old_owner_name)} → ${e(row.new_owner_name)}</p>${row.stale?'<p class="status-label late">Order sudah berubah; permintaan perlu ditolak dan diajukan ulang.</p>':''}<p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p><button data-action="production-change-request" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian permintaan</button></article>`).join(''));
        if(!before&&!rows.length)$('production-change-request-list').innerHTML='<p class="state">Belum ada permintaan perubahan untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat permintaan sebelumnya';
      }catch(error){if(current()){message('production-change-request-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('production-change-request-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="production-change-requests" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function productionChangeRequestDialog(requestId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian approval produksi','<p class="state">Memuat permintaan...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/production-change-requests/'+encodeURIComponent(requestId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const canCancel=row.status==='submitted'&&(user.role==='admin'||row.actor_id===user.id);
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${e(approvalStatus[row.status])}</p><h3>${e(row.order_reference)} · ${e(row.order_title)}</h3><article class="material-event"><h3>Perubahan yang diajukan</h3><p>Target ${date(row.old_due_date)} → ${date(row.new_due_date)}</p><p>PIC ${e(row.old_owner_name)} → ${e(row.new_owner_name)}</p></article>${row.stale?'<p class="error">Order sudah berubah setelah permintaan dibuat. Tolak permintaan ini, muat ulang order, lalu ajukan nilai terbaru.</p>':''}<p class="reason">${e(row.reason)}</p><p class="hint">Diajukan ${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p><div class="actions">${user.role==='admin'&&row.status==='submitted'&&!row.stale?'<button class="primary" data-production-decision="approved">Setujui perubahan</button>':''}${user.role==='admin'&&row.status==='submitted'?'<button data-production-decision="rejected">Tolak perubahan</button>':''}${canCancel?'<button data-production-decision="cancelled">Batalkan permintaan</button>':''}<button id="production-request-order">Buka order</button><button data-action="production-change-requests" data-id="${e(row.order_id)}">Riwayat order</button><button data-action="approvals">Inbox approval</button></div><h3>Riwayat keputusan</h3>${row.history.map(event=>`<article class="material-event"><strong>${e(approvalStatus[event.status])}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)} · ${purchaseStamp(event.created_at)}</p>${event.order_change_id?'<p class="hint">Perubahan order diterapkan dalam transaksi approval ini.</p>':''}</article>`).join('')}`;
    $('production-request-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(row.order_id);};
    $('dialog-content').querySelectorAll('[data-production-decision]').forEach(button=>button.onclick=()=>{
      if(guardPending())return;
      const decision=button.dataset.productionDecision;
      formDialog(button.textContent,materialReason,form=>({...Object.fromEntries(new FormData(form)),status:decision,expected_revision:row.revision}),
        '/api/production-change-requests/'+encodeURIComponent(row.id)+'/decisions',
        `${row.reference} · ${row.order_reference}\n${button.textContent}. Keputusan dan alasan tersimpan permanen.${decision==='approved'?' Tenggat/PIC order berubah saat persetujuan tersimpan.':''}`);
    });
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="production-change-request" data-id="${e(requestId)}">Coba lagi</button>`;}
}

const activityLabels = {movement:'Perpindahan barang',reversal:'Koreksi perpindahan',issue_opened:'Kendala dicatat',issue_resolved:'Kendala selesai',order_created:'Order dibuat',order_changed:'Tenggat / PIC diubah'};
$('activity').onclick = () => {
  activateWorkspace('activity'); selected = null;
  loadActivity();
};
$('activity-back').onclick = showBoard;
$('activity-form').onsubmit = event => { event.preventDefault(); loadActivity(); };
$('activity-day').onchange = $('activity-end').onchange = $('activity-kind').onchange = () => { if ($('activity-form').reportValidity()) loadActivity(); };
$('activity-more').onclick = () => loadActivity(true);
async function loadActivity(more = false) {
  if (more && !activityCursor) return;
  const version = epoch, request = ++activityRequest;
  const query = more ? {...activityQuery,...activityCursor} : {kind:$('activity-kind').value,limit:50};
  if (!more && ($('activity-day').value || $('activity-end').value)) { query.start_date = $('activity-day').value; query.end_date = $('activity-end').value; }
  if (!more) {
    activityRows = []; activityCursor = null; activityQuery = null;
    $('activity-list').replaceChildren(); $('activity-summary').replaceChildren(); $('activity-count').textContent = '';
    $('activity-more').hidden = true;
  }
  $('activity-export').disabled = true; $('activity-more').disabled = true; message('activity-message','Memuat aktivitas…');
  try {
    const result = await api.get('/api/activity?' + new URLSearchParams(query));
    if (version !== epoch || request !== activityRequest || view !== 'activity') return;
    if (!more) { activityQuery = {start_date:result.start_date,end_date:result.end_date,kind:query.kind,limit:50}; $('activity-day').value = result.start_date; $('activity-end').value = result.end_date; }
    activityRows.push(...result.items); activityCursor = result.next_before;
    const s = result.summary;
    $('activity-summary').innerHTML = [['Aktivitas tercatat',s.events,'catatan','list'],['Gudang bersih',s.warehouse_net,'pcs','archive'],
      ['Kendala dicatat',s.issues_opened,'catatan','alert-triangle'],['Kendala selesai',s.issues_resolved,'catatan','check-circle']]
      .map(([label,value,unit,glyph]) => `<div><dt>${label}${svgIcon(glyph)}</dt><dd>${n(value)} <small>${unit}</small></dd></div>`).join('');
    message('activity-message',activityRows.length ? '' : 'Tidak ada aktivitas yang cocok pada rentang ini.');
    $('activity-list').innerHTML = activityRows.map(item => {
      const stamp = new Intl.DateTimeFormat('id-ID',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Jakarta'}).format(new Date(item.created_at));
      let detail = '';
      if (['movement','reversal'].includes(item.kind)) detail = `${n(item.quantity)} pcs · ${labels[item.from_stage]} → ${labels[item.to_stage]}`;
      if (item.kind === 'issue_opened') detail = `${labels[item.to_stage]} · PIC: ${item.details.owner_name}`;
      if (item.kind === 'issue_resolved') detail = `${labels[item.to_stage]} · ${item.details.description}`;
      if (item.kind === 'order_changed') detail = `Tenggat: ${date(item.details.old_due_date)} → ${date(item.details.new_due_date)} · PIC: ${item.details.old_owner_name} → ${item.details.new_owner_name}`;
      return `<article class="history-item activity-item"><time datetime="${e(item.created_at)}">${stamp}</time><div><strong>${activityLabels[item.kind]}</strong>
        <p><button class="order-title" data-action="detail" data-id="${e(item.order_id)}">${e(item.reference)} · ${e(item.title)}</button></p>
        ${item.sku ? `<p class="hint">${e(item.sku)}</p>` : ''}${detail ? `<p>${e(detail)}</p>` : ''}
        ${item.reason ? `<p class="reason">${e(item.reason)}</p>` : ''}<p class="hint">Dicatat ${e(item.actor_name)}</p></div></article>`;
    }).join('');
    $('activity-count').textContent = `${n(activityRows.length)} catatan ditampilkan · ${n(result.total)} cocok saat dimuat`;
    $('activity-more').hidden = !activityCursor;
  } catch (error) {
    if (version === epoch && request === activityRequest && view === 'activity') fail(error,'activity-message');
  } finally { if (version === epoch && request === activityRequest) { $('activity-more').disabled = false; $('activity-export').disabled = !activityQuery || exportBusy; } }
}

for (const id of ['activity-day','activity-end','activity-kind']) $(id).addEventListener('input', () => {
  activityRequest++; activityQuery = null; activityCursor = null; activityRows = [];
  $('activity-list').replaceChildren(); $('activity-summary').replaceChildren(); $('activity-count').textContent = '';
  $('activity-more').hidden = true; $('activity-export').disabled = true;
});
$('activity-export').onclick = async () => {
  if (!activityQuery || exportBusy) return;
  const version = epoch, request = activityRequest, query = {...activityQuery}; delete query.limit;
  exportBusy = true; $('activity-export').disabled = true; $('activity-export').textContent = 'Menyiapkan CSV…';
  try {
    const blob = await api.download('/api/activity.csv?' + new URLSearchParams(query));
    if (version !== epoch || request !== activityRequest || view !== 'activity') return;
    saveDownload(blob,`beeloft-aktivitas-${query.start_date}-${query.end_date}-${query.kind}.csv`);
    notify('CSV siap diunduh. Semua hasil filter disertakan.');
  } catch (error) { if (version === epoch && request === activityRequest && view === 'activity') fail(error,'activity-message'); }
  finally { exportBusy = false; $('activity-export').textContent = 'Unduh CSV'; $('activity-export').disabled = !activityQuery; }
};

function saveDownload(blob, filename) {
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = filename;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
}

function showMaterials() {
  activateWorkspace('materials'); selected = null;
  $('receive-material').hidden = user.role === 'viewer';
  loadMaterials();
}

const bomComponentsHTML = components => components.map(c => `<div class="product-item"><div><strong>${e(c.code)}</strong><span>${e(c.name)}</span></div><span>${e(materialQty(c.quantity,c.unit))} / pcs</span></div>`).join('');
async function bomDialog(id) {
  if (guardPending()) return;
  const version = epoch; openDialog('BOM per SKU','<p class="state">Memuat BOM…</p>'); const modal = dialogVersion;
  try {
    const bom = await api.get(`/api/products/${encodeURIComponent(id)}/bom`);
    if (version !== epoch || modal !== dialogVersion || !$('dialog').open) return;
    $('dialog-content').innerHTML = `<p class="form-info">${e(bom.sku)} · ${e(bom.name)}</p><p class="hint">Kebutuhan bahan untuk membuat 1 pcs SKU ini. Angka mengikuti satuan master, belum termasuk tambahan waste otomatis.</p>${bom.revision ? `<p>Versi ${bom.revision} · ${e(bom.actor_name)} · ${date(bom.created_at)}</p><div>${bomComponentsHTML(bom.components)}</div><p class="reason">${e(bom.reason)}</p>` : '<p class="state">BOM belum diisi. Kebutuhan bahan belum dapat dihitung untuk SKU ini.</p>'}<div class="form-actions">${bom.revision ? `<button data-action="bom-history" data-id="${e(id)}">Riwayat BOM</button>` : ''}${user.role === 'admin' ? `<button class="primary" data-action="edit-bom" data-id="${e(id)}">${bom.revision ? 'Ubah BOM' : 'Isi BOM'}</button>` : ''}</div>`;
  } catch (error) { if (version === epoch && modal === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="bom" data-id="${e(id)}">Coba lagi</button>`; }
}
async function bomForm(id) {
  if (guardPending()) return;
  const version = epoch; openDialog('Susun BOM','<p class="state">Memuat bahan dan versi BOM…</p>'); const modal = dialogVersion;
  try {
    const [bom,materials] = await Promise.all([api.get(`/api/products/${encodeURIComponent(id)}/bom`),allRows('/api/materials')]);
    if (version !== epoch || modal !== dialogVersion || !$('dialog').open) return;
    if (!materials.length) { $('dialog-content').innerHTML = '<p>Admin perlu menambah master bahan melalui menu Bahan baku sebelum menyusun BOM.</p>'; return; }
    formDialog('Susun BOM','<div class="full"><div id="bom-lines"></div><button type="button" id="bom-add">Tambah bahan BOM</button></div>'+materialReason,
      form => {
        const components = [...form.querySelectorAll('.bom-line')].map(row => ({material_id:row.querySelector('select').value,quantity:row.querySelector('input').value}));
        if (new Set(components.map(c => c.material_id)).size !== components.length) throw new Error('Gabungkan bahan yang sama menjadi satu baris BOM.');
        return {components,expected_revision:bom.revision,reason:new FormData(form).get('reason')};
      },`/api/products/${encodeURIComponent(id)}/bom`,`${bom.sku} · versi ${bom.revision || 'belum diisi'}\nIsi jumlah bahan per 1 pcs produk. Menyimpan membuat versi baru dan memperbarui estimasi kebutuhan semua order SKU ini, termasuk order lama. Stok dan pengeluaran tidak berubah.`);
    const addLine = (component=null) => {
      if ($('bom-lines').children.length >= 100) return;
      const row = document.createElement('div'), token = crypto.randomUUID(); row.className='bom-line';
      row.innerHTML = `<div><label for="bom-material-${token}">Bahan BOM</label><select id="bom-material-${token}">${materials.map(m => option(m.id,`${m.code} · ${m.name} (${m.unit})`)).join('')}</select></div><label>Jumlah per pcs<input type="number" required max="1000000"></label><button type="button" aria-label="Hapus bahan BOM">Hapus</button>`;
      const select=row.querySelector('select'), input=row.querySelector('input');
      if (component) {select.value=component.material_id; input.value=component.quantity;}
      const unitChanged = () => {input.step=input.min=materials.find(m=>m.id===select.value).unit==='pcs' ? '1':'0.001';};
      select.onchange=unitChanged; unitChanged();
      row.querySelector('button').onclick=()=>{if ($('bom-lines').children.length>1) row.remove(); else notify('BOM memerlukan minimal satu bahan.');};
      $('bom-lines').append(row);
    };
    $('bom-add').onclick=()=>addLine();
    if (bom.components.length) bom.components.forEach(addLine); else addLine();
  } catch (error) { if (version === epoch && modal === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="edit-bom" data-id="${e(id)}">Coba lagi</button>`; }
}
async function bomHistoryDialog(id) {
  if (guardPending()) return;
  const version = epoch; openDialog('Riwayat BOM','<div id="bom-history"></div><p id="bom-history-error" class="error" role="alert" hidden></p><button id="bom-history-more" type="button">Muat versi sebelumnya</button>');
  const modal=dialogVersion, current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  let before=null;
  const load=async()=>{
    const button=$('bom-history-more'); button.disabled=true; message('bom-history-error','');
    try {
      const rows=await api.get(`/api/products/${encodeURIComponent(id)}/bom-history?`+new URLSearchParams({limit:10,...(before?{before}:{})}));
      if (!current()) return;
      appendRows('bom-history',rows.map(b=>`<article class="material-event"><h3>${e(b.sku)} · versi ${b.revision}</h3><p class="hint">${e(b.actor_name)} · ${date(b.created_at)}</p>${bomComponentsHTML(b.components)}<p class="reason">${e(b.reason)}</p></article>`).join(''));
      before=rows.at(-1)?.revision; button.hidden=rows.length<10;
    } catch(error) {if(current()) message('bom-history-error',error.message,true);}
    finally {if(current()) button.disabled=false;}
  };
  $('bom-history-more').onclick=load; await load();
}
async function requirementsDialog() {
  if (guardPending()) return;
  const version=epoch, order=selected;
  openDialog('Kebutuhan bahan order','<p class="state">Menghitung kebutuhan bahan…</p>'); const modal=dialogVersion;
  try {
    const report=await api.get(`/api/orders/${encodeURIComponent(order.id)}/material-requirements`);
    if (version!==epoch || modal!==dialogVersion || !$('dialog').open) return;
    $('dialog-content').innerHTML = `<p class="form-info">${e(report.reference)} · estimasi dari BOM terbaru saat dimuat</p><p class="hint">Target order × BOM per pcs. Dikeluarkan bersih sudah dikurangi pembalikan. Sisa kebutuhan dibandingkan dengan jatah order ini ditambah stok bebas semua batch. Reservasi order lain tidak ikut tersedia. Stok bebas masih bisa dialokasikan ke order lain setelah halaman dimuat. Perubahan versi BOM mengubah estimasi order lama.</p>
      ${!report.complete ? `<p class="error" role="status">Perhitungan belum lengkap. BOM belum diisi untuk ${report.missing_bom.map(s=>e(s.sku)).join(', ')}. Angka di bawah hanya mencakup SKU yang sudah memiliki BOM.</p>` : ''}
      <div id="requirements-list">${report.materials.map(m=>`<article class="material-event"><h3>${e(m.code)} · ${e(m.name)}</h3>${m.outside_bom?'<p class="status-label late">Pengeluaran / reservasi di luar BOM saat ini</p>':''}<dl class="requirement-values">${[['Kebutuhan total','required'],['Dikeluarkan bersih','issued'],['Sisa kebutuhan','remaining'],['Stok rak saat ini','stock'],['Reservasi order ini','reserved_own'],['Reservasi order lain','reserved_other'],['Stok bebas','available'],['Bisa dipakai order ini','available_to_order'],['Kekurangan','shortage']].map(([label,key])=>`<div><dt>${label}</dt><dd class="${key==='shortage' && m.shortage!=='0.000'?'status-label late':''}">${e(materialQty(m[key],m.unit))}</dd></div>`).join('')}</dl></article>`).join('')}</div>
      <h3>Dasar perhitungan</h3><div>${report.sources.map(s=>`<p>${e(s.sku)} · ${n(s.target_quantity)} pcs · ${s.revision ? 'BOM versi '+s.revision : 'BOM belum diisi'} <button class="quiet" data-action="bom" data-id="${e(s.product_id)}">Lihat BOM</button></p>`).join('')}</div><button data-action="requirements">Hitung ulang kebutuhan</button>`;
  } catch(error) {if(version===epoch && modal===dialogVersion && $('dialog').open) $('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="requirements">Coba lagi</button>`;}
}

async function reservationForm(action) {
  if (guardPending()) return;
  const version=epoch,order=selected,isReserve=action==='reserve';
  const title=isReserve?'Tambah reservasi bahan':'Lepaskan reservasi bahan';
  openDialog(title,'<p class="state">Memuat alokasi batch…</p>');const modal=dialogVersion;
  try {
    const rows=await allRows('/api/material-batches',{order_id:order.id});
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const fieldName=isReserve?'available':'reserved_for_order',batches=rows.filter(b=>Number(b[fieldName])>0);
    if(!batches.length){$('dialog-content').innerHTML=`<p>${isReserve?'Tidak ada stok bebas untuk direservasi.':'Order ini tidak memiliki reservasi yang tersisa.'}</p>`;return;}
    formDialog(title,`<div class="full"><label for="reservation-batch">Batch untuk reservasi</label><select id="reservation-batch" name="batch_id">${batches.map(b=>option(b.id,`${b.reference} · ${b.code} · ${isReserve?'bebas':'jatah order'} ${materialQty(b[fieldName],b.unit)}`)).join('')}</select></div>`+
      field('quantity',isReserve?'Jumlah tambahan reservasi':'Jumlah dilepaskan','number','required min="0.001" max="1000000" step="0.001" id="reservation-quantity"')+materialReason,
      form=>({...Object.fromEntries(new FormData(form)),order_id:order.id,action}),'/api/material-reservations',
      `${order.reference}\n${isReserve?'Jumlah ini ditambahkan ke jatah order pada batch pilihan.':'Jumlah ini dilepaskan dari jatah order dan kembali bebas untuk order lain.'} Stok fisik tidak berubah. Reservasi tidak otomatis mengikuti perubahan BOM atau selesai order.`);
    const update=()=>{const b=batches.find(b=>b.id===$('reservation-batch').value);$('reservation-quantity').max=b[fieldName];$('reservation-quantity').step=$('reservation-quantity').min=b.unit==='pcs'?'1':'0.001';};
    $('reservation-batch').onchange=update;update();
  } catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="${isReserve?'reserve-material':'release-material'}">Coba lagi</button>`;}
}
async function reservationsDialog() {
  if(guardPending())return;
  const version=epoch,order=selected;
  openDialog('Reservasi bahan order','<p class="state">Memuat reservasi…</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  try {
    const batches=await allRows(`/api/orders/${encodeURIComponent(order.id)}/material-reservations`);
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Reservasi melindungi jatah order per batch, tanpa memindahkan bahan. Pengeluaran memakai jatah sendiri terlebih dahulu. Pembalikan pengeluaran mengembalikan stok bebas; reservasi ulang perlu dicatat terpisah. Jatah tersisa tetap berlaku setelah order selesai atau BOM berubah sampai dikeluarkan atau dilepaskan.</p>
      <div id="reservation-balances">${batches.length?batches.map(b=>`<article class="material-event"><strong>${e(b.reference)} · ${e(b.code)}</strong><p>Jatah tersisa: ${e(materialQty(b.reserved_for_order,b.unit))}</p><p class="hint">${e(b.location)} · stok bebas ${e(materialQty(b.available,b.unit))}</p></article>`).join(''):'<p class="state">Belum ada reservasi untuk order ini.</p>'}</div>
      ${user.role==='admin'?'<div class="form-actions"><button data-action="release-material">Lepaskan reservasi</button><button class="primary" data-action="reserve-material">Tambah reservasi</button></div>':''}
      <h3>Riwayat reservasi</h3><div id="reservation-history"></div><p id="reservation-error" class="error" role="alert" hidden></p><button id="reservation-more" type="button">Muat riwayat reservasi</button>`;
    let before=null;
    const load=async()=>{
      const button=$('reservation-more');button.disabled=true;message('reservation-error','');
      try{
        const rows=await api.get(`/api/orders/${encodeURIComponent(order.id)}/reservation-history?`+new URLSearchParams({limit:100,...(before?{before}:{})}));
        if(!current())return;
        appendRows('reservation-history',rows.map(r=>`<article class="material-event"><strong>${{reserve:'Reservasi ditambah',release:'Reservasi dilepas',consume:'Dipakai oleh pengeluaran'}[r.kind]} · ${e(materialQty(r.quantity,r.unit))}</strong><p>${e(r.batch_reference)} · ${e(r.code)}</p><p class="reason">${e(r.reason)}</p><p class="hint">${e(r.actor_name)} · ${new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(r.created_at))}</p></article>`).join(''));
        before=rows.at(-1)?.sequence;button.hidden=rows.length<100;button.textContent='Muat reservasi sebelumnya';
      }catch(error){if(current())message('reservation-error',error.message,true);}finally{if(current())button.disabled=false;}
    };
    $('reservation-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="reservations">Coba lagi</button>`;}
}

async function cuttingRunsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Hasil cutting order','<p class="state">Memuat hasil cutting…</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  try {
    const order=await api.get('/api/orders/'+encodeURIComponent(orderId));
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Hubungkan pemakaian satu pengeluaran bahan dengan hasil potongan per SKU. Hasil yang dicatat berpindah dari cutting ke sewing.</p>
      ${user.role!=='viewer'?`<button data-action="new-cutting" data-id="${e(orderId)}">Catat hasil cutting</button>`:''}
      <div id="cutting-list"></div><p id="cutting-error" class="error" role="alert" hidden></p><button id="cutting-more">Muat hasil sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('cutting-more');button.disabled=true;message('cutting-error','');
      try {
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/cutting-runs?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        appendRows('cutting-list',rows.map(r=>`<article class="material-event"><h3>${e(r.reference)} · ${n(r.total_output)} pcs</h3>
          <p>${e(r.batch_reference)} · ${e(r.code)}</p><p>${r.reversal?'Sudah dikoreksi':'Hasil tercatat'} · ${purchaseStamp(r.created_at)}</p>
          <button data-action="cutting-run" data-id="${e(r.id)}">Rincian ${e(r.reference)}</button></article>`).join('') || (!before?'<p>Belum ada hasil cutting yang dihubungkan dengan pemakaian bahan.</p>':''));
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;
      } catch(error){if(current())message('cutting-error',error.message,true);}finally{if(current())button.disabled=false;}
    };
    $('cutting-more').onclick=load;await load();
  } catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="cutting-runs" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function cuttingForm(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat hasil cutting','<p class="state">Memuat bahan dan posisi cutting…</p>');const modal=dialogVersion;
  try {
    const [order,rows]=await Promise.all([api.get('/api/orders/'+encodeURIComponent(orderId)),allRows('/api/orders/'+encodeURIComponent(orderId)+'/material-consumption')]);
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const issues=rows.filter(i=>!i.reversed_by && Number(i.unreported)>0),lines=order.lines.filter(l=>l.balances.cutting>0);
    if(!issues.length || !lines.length){$('dialog-content').innerHTML='<p>Siapkan pengeluaran bahan yang belum dilaporkan pemakaiannya dan pcs di tahap cutting terlebih dahulu.</p>';return;}
    formDialog('Catat hasil cutting',field('reference','Referensi hasil cutting','text','required maxlength="160"')+
      `<div class="full"><label for="cutting-issue">Pengeluaran bahan</label><select id="cutting-issue" name="issue_id">${issues.map(i=>option(i.issue_id,`${i.batch_reference} · ${i.code} · belum dilaporkan ${materialQty(i.unreported,i.unit)} · ${purchaseStamp(i.created_at)} · ${i.issue_id}`)).join('')}</select></div>`+
      field('used','Bahan terpakai untuk hasil ini','number','required id="cutting-used"')+
      field('waste','Waste cutting','number','required id="cutting-waste" value="0"')+
      '<p class="full hint">Isi hasil tiap SKU yang siap masuk sewing. Biarkan nol untuk SKU yang belum selesai.</p>'+
      lines.map(l=>field('output-'+l.id,`Hasil ${e(l.sku)} (pcs)`,'number',`required min="0" max="${l.balances.cutting}" step="1" value="0"`)).join('')+materialReason,
      form=>{
        const data=new FormData(form),outputs=lines.map(l=>({line_id:l.id,quantity:Number(data.get('output-'+l.id))})).filter(l=>l.quantity>0);
        if(!outputs.length)throw new Error('Isi setidaknya satu SKU dengan jumlah hasil lebih dari nol.');
        const issue=issues.find(i=>i.issue_id===data.get('issue_id'));
        const milli=value=>Math.round(Number(value)*1000);
        if(milli(data.get('used'))+milli(data.get('waste'))>milli(issue.unreported))throw new Error('Bahan terpakai + waste melebihi jumlah yang belum dilaporkan.');
        return {reference:data.get('reference'),issue_id:issue.issue_id,used:data.get('used'),waste:data.get('waste'),reason:data.get('reason'),outputs};
      },'/api/orders/'+encodeURIComponent(orderId)+'/cutting-runs',
      `${order.reference}\nSimpan sekali untuk mencatat bahan terpakai, waste, dan perpindahan pcs cutting ke sewing. Gunakan hanya untuk hasil yang belum dicatat sebagai pemakaian maupun perpindahan terpisah. Stok rak sudah dipotong saat bahan dikeluarkan.`);
    const update=()=>{
      const issue=issues.find(i=>i.issue_id===$('cutting-issue').value),step=issue.unit==='pcs'?'1':'0.001';
      for(const name of ['used','waste']){const input=$('cutting-'+name);input.min=name==='used'?step:'0';input.step=step;input.max=issue.unreported;}
    };
    $('cutting-issue').onchange=update;update();
  } catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-cutting" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function cuttingRunDialog(id) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian hasil cutting','<p class="state">Memuat hasil cutting…</p>');const modal=dialogVersion;
  try {
    const run=await api.get('/api/cutting-runs/'+encodeURIComponent(id));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(run.reference)} · ${e(run.order_reference)}</p><h3>${n(run.total_output)} pcs hasil cutting</h3>
      <p>${e(run.batch_reference)} · ${e(run.code)}</p><p>Bahan terpakai ${e(materialQty(run.used,run.unit))} · waste ${e(materialQty(run.waste,run.unit))}</p>
      <p class="reason">${e(run.reason)}</p><p class="hint">${e(run.actor_name)} · ${purchaseStamp(run.created_at)}</p>
      ${run.outputs.map(o=>`<article class="material-event"><strong>${e(o.sku)} · ${e(o.size)} · ${e(o.color)}</strong><p>${n(o.quantity)} pcs hasil · ${n(o.bundled_quantity)} sudah dibundel · ${n(o.unbundled_quantity)} belum dibundel${run.reversal?' · cutting sudah dikoreksi':''}</p>${user.role!=='viewer' && !run.reversal && o.unbundled_quantity>0?`<button data-action="new-bundle" data-id="${e(run.id)}" data-output="${e(o.id)}">Buat bundle</button>`:''}</article>`).join('')}
      ${run.bundles.length?`<h3>Bundle dari hasil ini</h3>${run.bundles.map(b=>`<article class="material-event"><strong>${e(b.reference)} · ${n(b.quantity)} pcs</strong><p>${e(b.sku)} · ${e(b.size)} · ${b.status==='active'?'Aktif':'Sudah dikoreksi'}</p><button data-action="bundle" data-id="${e(b.id)}" aria-label="Rincian ${e(b.reference)}">Rincian bundle</button></article>`).join('')}`:''}
      ${run.reversal?`<article class="material-event"><h3>Hasil cutting dikoreksi</h3><p class="reason">${e(run.reversal.reason)}</p><p class="hint">${e(run.reversal.actor_name)} · ${purchaseStamp(run.reversal.created_at)}</p></article>`:''}
      <div class="actions"><button id="cutting-order">Buka order produksi</button><button data-action="material-batch" data-id="${e(run.batch_id)}">Batch bahan asal</button>
      <button data-action="cutting-runs" data-id="${e(run.order_id)}">Semua hasil cutting</button>${user.role==='admin' && !run.reversal?'<button id="reverse-cutting">Koreksi hasil cutting</button>':''}</div>`;
    $('cutting-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(run.order_id);};
    if($('reverse-cutting'))$('reverse-cutting').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi hasil cutting',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/cutting-runs/'+encodeURIComponent(id)+'/reverse',
        `${run.reference} · ${n(run.total_output)} pcs\nSeluruh output kembali dari sewing ke cutting dan pemakaian/waste kembali menjadi belum dilaporkan. Saldo sewing setiap SKU harus cukup. Stok rak tidak berubah. Koreksi ini mencerminkan pembetulan pencatatan; pastikan barang fisik sesuai.`);
    };
  } catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="cutting-run" data-id="${e(id)}">Coba lagi</button>`;}
}

async function bundlesDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Bundle order','<p class="state">Memuat bundle...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  $('dialog-content').innerHTML='<p class="hint">Identitas bundle terbaru ditampilkan lebih dahulu. Setiap bundle tetap terhubung ke hasil cutting dan batch bahan asal.</p><div id="bundle-list"><p class="state">Memuat bundle...</p></div><p id="bundle-error" class="error" role="alert" hidden></p><button id="bundle-more" type="button">Muat bundle sebelumnya</button>';
  let before=null;
  const load=async()=>{
    const button=$('bundle-more');button.disabled=true;message('bundle-error','');
    try{
      const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/bundles?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
      if(!current())return;
      if(!before)$('bundle-list').replaceChildren();
      appendRows('bundle-list',rows.map(b=>`<article class="material-event"><h3>${e(b.reference)} · ${n(b.quantity)} pcs</h3><p>${e(b.sku)} · ${e(b.size)} · ${b.status==='active'?'Aktif':'Sudah dikoreksi'}</p><p>${e(b.cutting_reference)} · ${e(b.batch_reference)}</p><p class="hint">${e(b.actor_name)} · ${purchaseStamp(b.created_at)}</p><button data-action="bundle" data-id="${e(b.id)}" aria-label="Rincian ${e(b.reference)}">Rincian bundle</button></article>`).join(''));
      if(!before && !rows.length)$('bundle-list').innerHTML='<p class="state">Belum ada bundle untuk order ini. Buka hasil cutting untuk membuat bundle pertama.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;
    }catch(error){if(current()){message('bundle-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current())button.disabled=false;}
  };
  $('bundle-more').onclick=load;await load();
}

function bundleScanDialog() {
  if(guardPending())return;
  openDialog('Scan bundle',`<form id="bundle-scan-form"><p class="form-info">Pindai QR pada label bundle atau masukkan Bundle ID. Scanner USB/Bluetooth dapat digunakan seperti keyboard lalu tekan Enter.</p>
    <label for="bundle-scan-code">Kode bundle<input id="bundle-scan-code" name="code" type="search" required maxlength="200" autocomplete="off" autocapitalize="characters" spellcheck="false" autofocus></label>
    <p id="bundle-scan-error" class="error" role="alert" hidden></p><div class="form-actions"><button type="button" data-action="cancel-form">Batal</button><button class="primary" type="submit">Buka bundle</button></div></form>`);
  const modal=dialogVersion,version=epoch,form=$('bundle-scan-form'),input=$('bundle-scan-code');
  input.focus();
  form.onsubmit=async event=>{
    event.preventDefault();const button=form.querySelector('[type="submit"]');button.disabled=true;message('bundle-scan-error','');
    try{
      const bundle=await api.get('/api/bundles/scan?'+new URLSearchParams({code:input.value.trim()}));
      if(version===epoch&&modal===dialogVersion&&$('dialog').open)bundleDialog(bundle.id);
    }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open){message('bundle-scan-error',error.message,true);input.select();}}
    finally{if(version===epoch&&modal===dialogVersion&&$('dialog').open)button.disabled=false;}
  };
}

async function bundleHandoffsDialog(bundleId) {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat serah-terima bundle','<p class="state">Memuat serah-terima...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  $('dialog-content').innerHTML='<p class="hint">Setiap handoff perlu akun pengirim dan penerima yang berbeda. Riwayat terbaru ditampilkan lebih dahulu.</p><div id="bundle-handoff-list"><p class="state">Memuat serah-terima...</p></div><p id="bundle-handoff-error" class="error" role="alert" hidden></p><button id="bundle-handoff-more" type="button">Muat catatan sebelumnya</button>';
  let before=null;
  const load=async()=>{
    const button=$('bundle-handoff-more');button.disabled=true;message('bundle-handoff-error','');
    try{
      const rows=await api.get('/api/bundles/'+encodeURIComponent(bundleId)+'/handoffs?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
      if(!current())return;
      if(!before)$('bundle-handoff-list').replaceChildren();
      const status={pending:'Menunggu penerima',received:'Sudah diterima',cancelled:'Dibatalkan'};
      appendRows('bundle-handoff-list',rows.map(item=>`<article class="material-event"><p class="status-label ${item.status==='received'?'done':item.status==='pending'?'late':''}">${status[item.status]}</p><h3>${e(item.from_location)} → ${e(item.to_location)}</h3><p>${e(item.bundle_reference)} · ${n(item.quantity)} pcs · ${e(item.sku)} · ${e(item.size)}</p><p class="reason">${e(item.reason)}</p><p class="hint">Dikirim ${e(item.sender_name)} · ${purchaseStamp(item.created_at)}</p>${item.status==='received'?`<p class="reason">Penerimaan: ${e(item.acceptance_reason)}</p><p class="hint">Diterima ${e(item.receiver_name)} · ${purchaseStamp(item.accepted_at)}</p>`:''}${item.status==='cancelled'?`<p class="reason">Pembatalan: ${e(item.cancellation_reason)}</p><p class="hint">Dibatalkan ${e(item.cancellation_actor_name)} · ${purchaseStamp(item.cancelled_at)}</p>`:''}<div class="actions">${item.status==='pending'&&user.role!=='viewer'&&item.sender_id!==user.id?`<button data-action="accept-bundle-handoff" data-id="${e(item.id)}">Konfirmasi terima</button>`:''}${item.status==='pending'&&user.role==='admin'?`<button data-action="cancel-bundle-handoff" data-id="${e(item.id)}">Batalkan handoff</button>`:''}</div></article>`).join(''));
      if(!before&&!rows.length)$('bundle-handoff-list').innerHTML='<p class="state">Belum ada serah-terima untuk bundle ini.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat catatan sebelumnya';
    }catch(error){if(current()){message('bundle-handoff-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current())button.disabled=false;}
  };
  $('bundle-handoff-more').onclick=load;await load();
}

async function bundleHandoffForm(bundleId) {
  if(guardPending())return;
  const version=epoch;openDialog('Serahkan bundle','<p class="state">Memuat posisi bundle...</p>');const modal=dialogVersion;
  try{
    const bundle=await api.get('/api/bundles/'+encodeURIComponent(bundleId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(bundle.status!=='active'||bundle.pending_handoff){$('dialog-content').innerHTML='<p>Bundle tidak aktif atau masih menunggu penerimaan handoff sebelumnya.</p><button data-action="bundle" data-id="'+e(bundleId)+'">Muat ulang bundle</button>';return;}
    formDialog('Serahkan bundle',field('to_location','Tujuan / stasiun penerima','text','required maxlength="160"')+materialReason,
      form=>{const data=new FormData(form);return {to_location:data.get('to_location'),reason:data.get('reason')};},
      '/api/bundles/'+encodeURIComponent(bundleId)+'/handoffs',`${bundle.reference} · ${n(bundle.quantity)} pcs\nLokasi sekarang: ${bundle.custody_location}. Penerima wajib mengonfirmasi dengan akun berbeda.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-bundle-handoff" data-id="${e(bundleId)}">Coba lagi</button>`;}
}

function acceptBundleHandoffForm(handoffId) {
  if(guardPending())return;
  formDialog('Konfirmasi terima bundle',materialReason,form=>Object.fromEntries(new FormData(form)),
    '/api/bundle-handoffs/'+encodeURIComponent(handoffId)+'/accept','Pastikan Bundle ID, jumlah, dan kondisi fisik sesuai sebelum menerima. Akun penerima harus berbeda dari pengirim.');
}

function cancelBundleHandoffForm(handoffId) {
  if(guardPending())return;
  formDialog('Batalkan handoff',materialReason,form=>Object.fromEntries(new FormData(form)),
    '/api/bundle-handoffs/'+encodeURIComponent(handoffId)+'/cancel','Pembatalan hanya berlaku untuk handoff yang belum diterima. Riwayat pengiriman tetap tersimpan.');
}

async function bundleForm(runId,outputId) {
  if(guardPending())return;
  const version=epoch;openDialog('Buat bundle','<p class="state">Memuat sisa hasil cutting...</p>');const modal=dialogVersion;
  try{
    const run=await api.get('/api/cutting-runs/'+encodeURIComponent(runId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const output=run.outputs.find(row=>row.id===outputId);
    if(!output){$('dialog-content').innerHTML='<p class="error">Output cutting tidak ditemukan pada hasil ini.</p>';return;}
    if(run.reversal || output.unbundled_quantity<1){$('dialog-content').innerHTML='<p>Output ini sudah dikoreksi atau seluruh jumlahnya sudah dibundel. Muat ulang hasil cutting.</p><button data-action="cutting-run" data-id="'+e(runId)+'">Muat ulang hasil cutting</button>';return;}
    formDialog('Buat bundle',field('reference','Bundle ID','text','required maxlength="160"')+
      field('quantity','Jumlah bundle','number',`required min="1" max="${output.unbundled_quantity}" step="1"`)+materialReason,
      form=>{const data=new FormData(form);return {reference:data.get('reference'),output_movement_id:outputId,quantity:Number(data.get('quantity')),reason:data.get('reason')};},
      '/api/cutting-runs/'+encodeURIComponent(runId)+'/bundles',
      `${run.reference} · ${output.sku} · ${output.size}\nTersedia ${n(output.unbundled_quantity)} pcs dari ${n(output.quantity)} pcs hasil cutting. Pencatatan bundle tidak memindahkan posisi WIP.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-bundle" data-id="${e(runId)}" data-output="${e(outputId)}">Coba lagi</button>`;}
}

async function bundleDialog(bundleId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian bundle','<p class="state">Memuat bundle...</p>');const modal=dialogVersion;
  try{
    const bundle=await api.get('/api/bundles/'+encodeURIComponent(bundleId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(bundle.reference)} · ${bundle.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${n(bundle.quantity)} pcs · ${e(bundle.sku)} · ${e(bundle.size)}</h3><p>${e(bundle.product_name)} · ${e(bundle.color)}</p><p>Dialokasikan ke sewing ${n(bundle.sewing_allocated_quantity)} pcs · belum dialokasikan ${n(bundle.sewing_unassigned_quantity)} pcs</p><p>Lokasi custody sekarang: <strong>${e(bundle.custody_location)}</strong>${bundle.pending_handoff?` · menuju ${e(bundle.pending_handoff.to_location)}, menunggu penerima`:``}</p><p>Hasil cutting ${e(bundle.cutting_reference)} · batch ${e(bundle.batch_reference)} · ${e(bundle.material_code)}</p><p class="reason">${e(bundle.reason)}</p><p class="hint">${e(bundle.actor_name)} · ${purchaseStamp(bundle.created_at)}</p>${bundle.reversal?`<article class="material-event"><h3>Sudah dikoreksi</h3><p class="reason">${e(bundle.reversal.reason)}</p><p class="hint">${e(bundle.reversal.actor_name)} · ${purchaseStamp(bundle.reversal.created_at)}</p></article>`:''}${bundle.status==='active'?`<section class="bundle-label" aria-label="Label bundle ${e(bundle.reference)}"><img src="/api/bundles/${e(encodeURIComponent(bundle.id))}/label.svg" alt="Kode QR bundle ${e(bundle.reference)}"><div><strong>${e(bundle.reference)}</strong><span>${e(bundle.sku)} · ukuran ${e(bundle.size)}</span><span class="bundle-label-qty">${n(bundle.quantity)} pcs</span><span>Order ${e(bundle.order_reference)}</span></div></section>`:''}<div class="actions"><button id="bundle-order">Buka order produksi</button><button data-action="cutting-run" data-id="${e(bundle.cutting_run_id)}">Hasil cutting asal</button><button data-action="material-batch" data-id="${e(bundle.batch_id)}">Batch bahan asal</button><button data-action="bundles" data-id="${e(bundle.order_id)}">Semua bundle</button><button data-action="bundle-handoffs" data-id="${e(bundle.id)}">Riwayat serah-terima</button>${user.role!=='viewer'&&bundle.status==='active'&&!bundle.pending_handoff?`<button data-action="new-bundle-handoff" data-id="${e(bundle.id)}">Serahkan bundle</button>`:``}${user.role!=='viewer'&&bundle.pending_handoff&&bundle.pending_handoff.sender_id!==user.id?`<button data-action="accept-bundle-handoff" data-id="${e(bundle.pending_handoff.id)}">Konfirmasi terima</button>`:``}${user.role==='admin'&&bundle.pending_handoff?`<button data-action="cancel-bundle-handoff" data-id="${e(bundle.pending_handoff.id)}">Batalkan handoff</button>`:``}<button data-action="sewing-jobs" data-id="${e(bundle.order_id)}">Sewing / makloon order</button>${bundle.status==='active'?'<button id="print-bundle">Cetak label</button>':''}${user.role!=='viewer' && bundle.status==='active' && bundle.sewing_unassigned_quantity>0?`<button data-action="new-sewing-job" data-id="${e(bundle.id)}">Kirim ke sewing</button>`:''}${user.role==='admin' && bundle.status==='active'?'<button id="reverse-bundle">Koreksi bundle</button>':''}</div>`;
    $('bundle-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(bundle.order_id);};
    if($('print-bundle'))$('print-bundle').onclick=()=>window.print();
    if($('reverse-bundle'))$('reverse-bundle').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi bundle',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/bundles/'+encodeURIComponent(bundle.id)+'/reverse',
        `${bundle.reference} · ${n(bundle.quantity)} pcs\nKoreksi melepaskan alokasi identitas bundle. Posisi WIP tidak berubah dan riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="bundle" data-id="${e(bundleId)}">Coba lagi</button>`;}
}

async function sewingJobsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Sewing / makloon order','<p class="state">Memuat job sewing...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  $('dialog-content').innerHTML='<p class="hint">Job terbaru ditampilkan lebih dahulu. Jumlah defect dan missing tetap tercatat terpisah meski keduanya masuk posisi reject.</p><div id="sewing-list"><p class="state">Memuat job sewing...</p></div><p id="sewing-error" class="error" role="alert" hidden></p><button id="sewing-more" type="button">Muat job sebelumnya</button>';
  let before=null;
  const load=async()=>{
    const button=$('sewing-more');button.disabled=true;message('sewing-error','');
    try{
      const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/sewing-jobs?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
      if(!current())return;
      if(!before)$('sewing-list').replaceChildren();
      const status={open:'Berjalan',completed:'Selesai',corrected:'Sudah dikoreksi'};
      appendRows('sewing-list',rows.map(job=>`<article class="material-event"><h3>${e(job.reference)} · ${n(job.quantity_out)} pcs</h3><p>${e(job.bundle_reference)} · ${e(job.sku)} · ${e(job.size)}</p><p>${job.assignment_type==='makloon'?'Makloon':'Internal'} · ${e(job.assignee)} · ${rupiah(job.cost)}</p><p>${status[job.status]} · dikirim ${date(job.sent_date)}</p><button data-action="sewing-job" data-id="${e(job.id)}" aria-label="Rincian ${e(job.reference)}">Rincian job</button></article>`).join(''));
      if(!before && !rows.length)$('sewing-list').innerHTML='<p class="state">Belum ada job sewing untuk order ini. Buka bundle untuk mengirim pekerjaan pertama.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat job sebelumnya';
    }catch(error){if(current()){message('sewing-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current())button.disabled=false;}
  };
  $('sewing-more').onclick=load;await load();
}

async function sewingJobForm(bundleId) {
  if(guardPending())return;
  const version=epoch;openDialog('Kirim ke sewing','<p class="state">Memuat bundle...</p>');const modal=dialogVersion;
  try{
    const bundle=await api.get('/api/bundles/'+encodeURIComponent(bundleId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(bundle.status!=='active' || bundle.sewing_unassigned_quantity<1){$('dialog-content').innerHTML='<p>Bundle ini sudah dikoreksi atau seluruh jumlahnya sudah dialokasikan. Muat ulang rincian bundle.</p><button data-action="bundle" data-id="'+e(bundleId)+'">Muat ulang bundle</button>';return;}
    formDialog('Kirim ke sewing',field('reference','Referensi job','text','required maxlength="160"')+
      `<div><label for="sewing-assignment">Jenis penugasan</label><select id="sewing-assignment" name="assignment_type">${option('internal','Internal')}${option('makloon','Makloon')}</select></div>`+
      field('assignee','Pelaksana / vendor','text','required maxlength="160"')+
      field('quantity_out','Jumlah keluar','number',`required min="1" max="${bundle.sewing_unassigned_quantity}" step="1"`)+
      field('cost','Biaya total (Rp)','number','required min="0" max="1000000000000" step="0.01" value="0"')+
      field('sent_date','Tanggal kirim','date','required')+materialReason,
      form=>{const data=new FormData(form);return {reference:data.get('reference'),assignment_type:data.get('assignment_type'),assignee:data.get('assignee'),quantity_out:Number(data.get('quantity_out')),cost:data.get('cost'),sent_date:data.get('sent_date'),reason:data.get('reason')};},
      '/api/bundles/'+encodeURIComponent(bundleId)+'/sewing-jobs',
      `${bundle.reference} · ${bundle.sku} · ${bundle.size}\nTersedia ${n(bundle.sewing_unassigned_quantity)} dari ${n(bundle.quantity)} pcs. Pengiriman ini mencatat alokasi bundle; posisi WIP tetap di sewing sampai hasil diterima.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-sewing-job" data-id="${e(bundleId)}">Coba lagi</button>`;}
}

async function sewingResultForm(jobId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat hasil sewing','<p class="state">Memuat job sewing...</p>');const modal=dialogVersion;
  try{
    const job=await api.get('/api/sewing-jobs/'+encodeURIComponent(jobId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(job.status!=='open'){$('dialog-content').innerHTML='<p>Hasil job ini sudah dicatat atau job sudah dikoreksi. Muat ulang rinciannya.</p><button data-action="sewing-job" data-id="'+e(jobId)+'">Muat ulang job</button>';return;}
    formDialog('Catat hasil sewing',field('completed_quantity','Jumlah selesai','number',`required min="0" max="${job.quantity_out}" step="1" value="${job.quantity_out}"`)+
      field('defect_quantity','Jumlah defect','number',`required min="0" max="${job.quantity_out}" step="1" value="0"`)+
      field('missing_quantity','Jumlah missing','number',`required min="0" max="${job.quantity_out}" step="1" value="0"`)+
      field('returned_date','Tanggal kembali','date',`required min="${e(job.sent_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={completed_quantity:Number(data.get('completed_quantity')),defect_quantity:Number(data.get('defect_quantity')),missing_quantity:Number(data.get('missing_quantity')),returned_date:data.get('returned_date'),reason:data.get('reason')};if(payload.completed_quantity+payload.defect_quantity+payload.missing_quantity!==job.quantity_out)throw new Error('Jumlah selesai + defect + missing harus sama dengan jumlah keluar.');return payload;},
      '/api/sewing-jobs/'+encodeURIComponent(jobId)+'/complete',
      `${job.reference} · ${job.assignee}\nBagi tepat ${n(job.quantity_out)} pcs menjadi selesai, defect, dan missing. Selesai masuk finishing; defect dan missing masuk reject.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="sewing-job" data-id="${e(jobId)}">Coba lagi</button>`;}
}

async function sewingJobDialog(jobId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian job sewing','<p class="state">Memuat job sewing...</p>');const modal=dialogVersion;
  try{
    const job=await api.get('/api/sewing-jobs/'+encodeURIComponent(jobId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const status={open:'Berjalan',completed:'Selesai',corrected:'Sudah dikoreksi'}[job.status];
    $('dialog-content').innerHTML=`<p class="form-info">${e(job.reference)} · ${status}</p><h3>${n(job.quantity_out)} pcs · ${e(job.bundle_reference)}</h3><p>${e(job.sku)} · ${e(job.product_name)} · ${e(job.color)} · ${e(job.size)}</p><p>${job.assignment_type==='makloon'?'Makloon':'Internal'} · ${e(job.assignee)}</p><p>Biaya total ${rupiah(job.cost)} · dikirim ${date(job.sent_date)}</p><p class="reason">${e(job.reason)}</p><p class="hint">${e(job.actor_name)} · ${purchaseStamp(job.created_at)}</p>${job.result?`<article class="material-event"><h3>Hasil sewing diterima</h3><p>Selesai ${n(job.result.completed_quantity)} pcs · defect ${n(job.result.defect_quantity)} pcs · missing ${n(job.result.missing_quantity)} pcs</p><p>Kembali ${date(job.result.returned_date)} · turnaround ${n(job.result.turnaround_days)} hari</p><p>Finishing tercatat ${n(job.finishing_completed_quantity)} pcs · belum dicatat ${n(job.finishing_remaining_quantity)} pcs</p><p class="reason">${e(job.result.reason)}</p><p class="hint">${e(job.result.actor_name)} · ${purchaseStamp(job.result.created_at)}</p></article>`:''}${job.reversal?`<article class="material-event"><h3>Job sewing dikoreksi</h3><p class="reason">${e(job.reversal.reason)}</p><p class="hint">${e(job.reversal.actor_name)} · ${purchaseStamp(job.reversal.created_at)}</p></article>`:''}<div class="actions"><button id="sewing-order">Buka order produksi</button><button data-action="bundle" data-id="${e(job.bundle_id)}">Bundle asal</button><button data-action="cutting-run" data-id="${e(job.cutting_run_id)}">Hasil cutting asal</button><button data-action="material-batch" data-id="${e(job.batch_id)}">Batch bahan asal</button><button data-action="sewing-jobs" data-id="${e(job.order_id)}">Semua job sewing</button><button data-action="finishing-records" data-id="${e(job.order_id)}">Finishing order</button>${user.role!=='viewer' && job.status==='open'?`<button id="complete-sewing">Catat hasil sewing</button>`:''}${user.role!=='viewer' && job.status==='completed' && job.finishing_remaining_quantity>0?`<button data-action="new-finishing-record" data-id="${e(job.id)}">Catat finishing</button>`:''}${user.role==='admin' && job.status!=='corrected'?`<button id="reverse-sewing">Koreksi job sewing</button>`:''}</div>`;
    $('sewing-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(job.order_id);};
    if($('complete-sewing'))$('complete-sewing').onclick=()=>sewingResultForm(job.id);
    if($('reverse-sewing'))$('reverse-sewing').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi job sewing',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/sewing-jobs/'+encodeURIComponent(job.id)+'/reverse',
        `${job.reference} · ${n(job.quantity_out)} pcs\nKoreksi membatalkan job dan mengembalikan seluruh perpindahan hasilnya ke sewing. Riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="sewing-job" data-id="${e(jobId)}">Coba lagi</button>`;}
}

async function finishingRecordsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Finishing order','<p class="state">Memuat catatan finishing...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  $('dialog-content').innerHTML='<p class="hint">Catatan terbaru ditampilkan lebih dahulu. Setiap jumlah yang selesai seluruh checklist berpindah dari finishing ke QC.</p><div id="finishing-list"><p class="state">Memuat catatan finishing...</p></div><p id="finishing-error" class="error" role="alert" hidden></p><button id="finishing-more" type="button">Muat catatan sebelumnya</button>';
  let before=null;
  const load=async()=>{
    const button=$('finishing-more');button.disabled=true;message('finishing-error','');
    try{
      const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/finishing-records?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
      if(!current())return;
      if(!before)$('finishing-list').replaceChildren();
      appendRows('finishing-list',rows.map(record=>`<article class="material-event"><h3>${e(record.reference)} · ${n(record.quantity)} pcs</h3><p>${e(record.sewing_reference)} · ${e(record.bundle_reference)} · ${e(record.sku)} · ${e(record.size)}</p><p>${record.status==='completed'?'Selesai':'Sudah dikoreksi'} · ${date(record.completed_date)}</p><button data-action="finishing-record" data-id="${e(record.id)}" aria-label="Rincian ${e(record.reference)}">Rincian finishing</button></article>`).join(''));
      if(!before && !rows.length)$('finishing-list').innerHTML='<p class="state">Belum ada catatan finishing untuk order ini. Buka job sewing yang sudah selesai untuk mencatat finishing.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat catatan sebelumnya';
    }catch(error){if(current()){message('finishing-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current())button.disabled=false;}
  };
  $('finishing-more').onclick=load;await load();
}

async function finishingForm(jobId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat finishing','<p class="state">Memuat hasil sewing...</p>');const modal=dialogVersion;
  try{
    const job=await api.get('/api/sewing-jobs/'+encodeURIComponent(jobId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(job.status!=='completed' || job.finishing_remaining_quantity<1){$('dialog-content').innerHTML='<p>Job sewing belum selesai, sudah dikoreksi, atau seluruh hasilnya sudah dicatat finishing.</p><button data-action="sewing-job" data-id="'+e(jobId)+'">Muat ulang job</button>';return;}
    const check=(name,label)=>`<label class="check-field"><input type="checkbox" name="${name}" required>${label}</label>`;
    formDialog('Catat finishing',field('reference','Referensi finishing','text','required maxlength="160"')+
      field('quantity','Jumlah selesai finishing','number',`required min="1" max="${job.finishing_remaining_quantity}" step="1"`)+
      check('thread_trimmed','Benang sudah dirapikan')+check('ironed','Sudah disetrika')+
      check('labels_attached','Label sudah terpasang')+check('hangtags_attached','Hangtag sudah terpasang')+
      check('packaged','Sudah dikemas')+field('completed_date','Tanggal selesai','date',`required min="${e(job.result.returned_date)}"`)+materialReason,
      form=>{const data=new FormData(form);return {reference:data.get('reference'),quantity:Number(data.get('quantity')),
        thread_trimmed:data.has('thread_trimmed'),ironed:data.has('ironed'),labels_attached:data.has('labels_attached'),
        hangtags_attached:data.has('hangtags_attached'),packaged:data.has('packaged'),completed_date:data.get('completed_date'),reason:data.get('reason')};},
      '/api/sewing-jobs/'+encodeURIComponent(jobId)+'/finishing-records',
      `${job.reference} · ${job.bundle_reference} · ${job.sku} · ${job.size}\nTersedia ${n(job.finishing_remaining_quantity)} dari ${n(job.result.completed_quantity)} pcs hasil sewing. Simpan hanya setelah semua langkah selesai; jumlah langsung masuk QC.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-finishing-record" data-id="${e(jobId)}">Coba lagi</button>`;}
}

async function finishingRecordDialog(recordId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian finishing','<p class="state">Memuat catatan finishing...</p>');const modal=dialogVersion;
  try{
    const record=await api.get('/api/finishing-records/'+encodeURIComponent(recordId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const checks=[['Benang dirapikan',record.thread_trimmed],['Disetrika',record.ironed],['Label terpasang',record.labels_attached],['Hangtag terpasang',record.hangtags_attached],['Dikemas',record.packaged]];
    $('dialog-content').innerHTML=`<p class="form-info">${e(record.reference)} · ${record.status==='completed'?'Selesai':'Sudah dikoreksi'}</p><h3>${n(record.quantity)} pcs · ${e(record.sku)} · ${e(record.size)}</h3><p>Job sewing ${e(record.sewing_reference)} · bundle ${e(record.bundle_reference)}</p><p>${record.assignment_type==='makloon'?'Makloon':'Internal'} · ${e(record.assignee)}</p><article class="material-event"><h3>Checklist finishing lengkap</h3>${checks.map(([label,done])=>`<p>${done?'✓':'—'} ${e(label)}</p>`).join('')}<p>Selesai ${date(record.completed_date)}</p><p>Inspeksi awal final QC tercatat ${n(record.qc_inspected_quantity)} pcs · belum diperiksa ${n(record.qc_remaining_quantity)} pcs</p></article><p class="reason">${e(record.reason)}</p><p class="hint">${e(record.actor_name)} · ${purchaseStamp(record.created_at)}</p>${record.reversal?`<article class="material-event"><h3>Finishing dikoreksi</h3><p class="reason">${e(record.reversal.reason)}</p><p class="hint">${e(record.reversal.actor_name)} · ${purchaseStamp(record.reversal.created_at)}</p></article>`:''}<div class="actions"><button id="finishing-order">Buka order produksi</button><button data-action="sewing-job" data-id="${e(record.job_id)}">Job sewing asal</button><button data-action="bundle" data-id="${e(record.bundle_id)}">Bundle asal</button><button data-action="cutting-run" data-id="${e(record.cutting_run_id)}">Hasil cutting asal</button><button data-action="material-batch" data-id="${e(record.batch_id)}">Batch bahan asal</button><button data-action="finishing-records" data-id="${e(record.order_id)}">Semua finishing</button><button data-action="final-qc-records" data-id="${e(record.order_id)}">Final QC order</button>${user.role!=='viewer' && record.status==='completed' && record.qc_remaining_quantity>0?`<button data-action="new-final-qc-record" data-id="${e(record.id)}">Catat final QC</button>`:''}${user.role==='admin' && record.status==='completed'?'<button id="reverse-finishing">Koreksi finishing</button>':''}</div>`;
    $('finishing-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(record.order_id);};
    if($('reverse-finishing'))$('reverse-finishing').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi finishing',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/finishing-records/'+encodeURIComponent(record.id)+'/reverse',
        `${record.reference} · ${n(record.quantity)} pcs\nKoreksi mengembalikan jumlah dari QC ke finishing. Checklist dan riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finishing-record" data-id="${e(recordId)}">Coba lagi</button>`;}
}

const inspectionLabel = record => record.inspection_kind==='initial'
  ? 'Inspeksi awal' : `Inspeksi ulang #${record.inspection_round-1}`;
const inspectionBadge = record => `<span class="badge ${record.inspection_kind==='initial'?'':'badge-warning'}">${e(inspectionLabel(record))}</span>`;

async function finalQcRecordsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Final QC order','<p class="state">Memuat catatan final QC...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  $('dialog-content').innerHTML=`<p class="hint">Inspeksi terbaru ditampilkan lebih dahulu. Setiap jumlah dibagi menjadi diterima gudang, rework, dan reject. Inspeksi awal memeriksa hasil finishing; inspeksi ulang memeriksa hasil rework yang sudah selesai.</p><button data-action="rework-completions" data-id="${e(orderId)}">Riwayat selesai rework order</button><div id="final-qc-list"><p class="state">Memuat catatan final QC...</p></div><p id="final-qc-error" class="error" role="alert" hidden></p><button id="final-qc-more" type="button">Muat inspeksi sebelumnya</button>`;
  let before=null;
  const load=async()=>{
    const button=$('final-qc-more');button.disabled=true;message('final-qc-error','');
    try{
      const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/final-qc-records?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
      if(!current())return;
      if(!before)$('final-qc-list').replaceChildren();
      appendRows('final-qc-list',rows.map(record=>`<article class="material-event"><h3>${e(record.reference)} · ${n(record.inspected_quantity)} pcs</h3><p>${inspectionBadge(record)}</p><p>${e(record.finishing_reference)} · ${e(record.sku)} · ${e(record.size)}</p><p>Diterima ${n(record.accepted_quantity)} · rework ${n(record.rework_quantity)} · reject ${n(record.reject_quantity)}</p><p>${record.status==='completed'?'Selesai':'Sudah dikoreksi'} · ${date(record.inspection_date)}</p><button data-action="final-qc-record" data-id="${e(record.id)}" aria-label="Rincian ${e(record.reference)}">Rincian final QC</button></article>`).join(''));
      if(!before && !rows.length)$('final-qc-list').innerHTML='<p class="state">Belum ada catatan final QC untuk order ini. Buka finishing yang selesai untuk mencatat inspeksi.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat inspeksi sebelumnya';
    }catch(error){if(current()){message('final-qc-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current())button.disabled=false;}
  };
  $('final-qc-more').onclick=load;await load();
}

async function finalQcForm(finishingId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat final QC','<p class="state">Memuat finishing...</p>');const modal=dialogVersion;
  try{
    const source=await api.get('/api/finishing-records/'+encodeURIComponent(finishingId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(source.status!=='completed' || source.qc_remaining_quantity<1){$('dialog-content').innerHTML='<p>Finishing sudah dikoreksi atau seluruh jumlahnya sudah diperiksa. Muat ulang rinciannya.</p><button data-action="finishing-record" data-id="'+e(finishingId)+'">Muat ulang finishing</button>';return;}
    formDialog('Catat final QC',field('reference','Referensi final QC','text','required maxlength="160"')+
      '<label class="full">Catatan pengukuran<textarea name="measurement_notes" required maxlength="1000"></textarea></label>'+
      '<label class="full">Catatan pemeriksaan visual<textarea name="visual_notes" required maxlength="1000"></textarea></label>'+
      field('defect_type','Jenis defect','text','required maxlength="160"')+
      field('responsible_source','Sumber penanggung jawab','text','required maxlength="160"')+
      '<label class="full">Disposition<textarea name="disposition" required maxlength="1000"></textarea></label>'+
      field('accepted_quantity','Jumlah diterima','number',`required min="0" max="${source.qc_remaining_quantity}" step="1" value="${source.qc_remaining_quantity}"`)+
      field('rework_quantity','Jumlah rework','number',`required min="0" max="${source.qc_remaining_quantity}" step="1" value="0"`)+
      field('reject_quantity','Jumlah reject','number',`required min="0" max="${source.qc_remaining_quantity}" step="1" value="0"`)+
      field('inspection_date','Tanggal inspeksi','date',`required min="${e(source.completed_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={reference:data.get('reference'),measurement_notes:data.get('measurement_notes'),visual_notes:data.get('visual_notes'),defect_type:data.get('defect_type'),responsible_source:data.get('responsible_source'),disposition:data.get('disposition'),accepted_quantity:Number(data.get('accepted_quantity')),rework_quantity:Number(data.get('rework_quantity')),reject_quantity:Number(data.get('reject_quantity')),inspection_date:data.get('inspection_date'),reason:data.get('reason')};const total=payload.accepted_quantity+payload.rework_quantity+payload.reject_quantity;if(total<1)throw new Error('Isi setidaknya satu hasil QC dengan jumlah lebih dari nol.');if(total>source.qc_remaining_quantity)throw new Error('Jumlah diterima + rework + reject melebihi finishing yang belum diperiksa.');return payload;},
      '/api/finishing-records/'+encodeURIComponent(finishingId)+'/qc-records',
      `${source.reference} · ${source.sku} · ${source.size}\nTersedia ${n(source.qc_remaining_quantity)} dari ${n(source.quantity)} pcs. Jumlah diterima, rework, dan reject langsung berpindah dari QC ke posisi masing-masing.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-final-qc-record" data-id="${e(finishingId)}">Coba lagi</button>`;}
}

async function finalQcRecordDialog(recordId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian final QC','<p class="state">Memuat catatan final QC...</p>');const modal=dialogVersion;
  try{
    const record=await api.get('/api/final-qc-records/'+encodeURIComponent(recordId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(record.reference)} · ${record.status==='completed'?'Selesai':'Sudah dikoreksi'}</p><h3>${n(record.inspected_quantity)} pcs diperiksa · ${e(record.sku)} · ${e(record.size)}</h3><p>${inspectionBadge(record)}</p><p>Finishing ${e(record.finishing_reference)} · sewing ${e(record.sewing_reference)} · bundle ${e(record.bundle_reference)}</p>${record.inspection_kind==='reinspection'?`<article class="material-event"><h3>Sumber inspeksi ulang</h3><p>Selesai rework ${e(record.rework_completion_reference)} · ${date(record.rework_completion_date)}</p><p>Inspeksi sebelumnya ${e(record.source_final_qc_reference)} · ${date(record.source_inspection_date)}</p></article>`:''}<article class="material-event"><h3>Hasil final QC</h3><p>Diterima gudang ${n(record.accepted_quantity)} pcs</p><p>Rework ${n(record.rework_quantity)} pcs · reject ${n(record.reject_quantity)} pcs</p>${record.rework_quantity?`<p>Rework selesai ${n(record.rework_completed_quantity)} pcs · belum selesai ${n(record.rework_remaining_quantity)} pcs</p>`:''}${record.rework_remaining_quantity>record.rework_completable_quantity?`<p class="error">${n(record.rework_remaining_quantity-record.rework_completable_quantity)} pcs rework catatan ini sudah tidak berada di tahap rework, karena ada perpindahan rework ke QC pada baris order ini tanpa catatan selesai rework. Koreksi perpindahan tersebut dari riwayat perpindahan order lebih dahulu.</p>`:''}<p>Diterima barang jadi ${n(record.warehouse_received_quantity)} pcs · belum diterima ${n(record.warehouse_remaining_quantity)} pcs</p><p>Inspeksi ${date(record.inspection_date)}</p></article><h3>Pengukuran</h3><p class="reason">${e(record.measurement_notes)}</p><h3>Pemeriksaan visual</h3><p class="reason">${e(record.visual_notes)}</p><h3>Defect dan disposition</h3><p>${e(record.defect_type)} · sumber ${e(record.responsible_source)}</p><p class="reason">${e(record.disposition)}</p><p class="reason">${e(record.reason)}</p><p class="hint">${e(record.actor_name)} · ${purchaseStamp(record.created_at)}</p>${record.active_rework_completion_count?`<p class="hint">${n(record.active_rework_completion_count)} catatan selesai rework aktif. Koreksi catatan tersebut sebelum mengoreksi final QC.</p>`:''}${record.reversal?`<article class="material-event"><h3>Final QC dikoreksi</h3><p class="reason">${e(record.reversal.reason)}</p><p class="hint">${e(record.reversal.actor_name)} · ${purchaseStamp(record.reversal.created_at)}</p></article>`:''}<div class="actions"><button id="final-qc-order">Buka order produksi</button>${record.inspection_kind==='reinspection'?`<button data-action="rework-completion" data-id="${e(record.rework_completion_id)}">Selesai rework asal</button><button data-action="final-qc-record" data-id="${e(record.source_final_qc_record_id)}">Inspeksi sebelumnya</button>`:''}<button data-action="finishing-record" data-id="${e(record.finishing_record_id)}">Finishing asal</button><button data-action="sewing-job" data-id="${e(record.job_id)}">Job sewing asal</button><button data-action="bundle" data-id="${e(record.bundle_id)}">Bundle asal</button><button data-action="material-batch" data-id="${e(record.batch_id)}">Batch bahan asal</button><button data-action="final-qc-records" data-id="${e(record.order_id)}">Semua final QC</button>${record.rework_quantity?`<button data-action="final-qc-rework-completions" data-id="${e(record.id)}">Riwayat selesai rework</button>`:''}<button data-action="finished-goods" data-id="${e(record.order_id)}">Barang jadi order</button>${user.role!=='viewer' && record.status==='completed' && record.rework_completable_quantity>0?`<button data-action="new-rework-completion" data-id="${e(record.id)}">Catat selesai rework</button>`:''}${user.role!=='viewer' && record.status==='completed' && record.warehouse_remaining_quantity>0?`<button data-action="new-finished-goods" data-id="${e(record.id)}">Terima barang jadi</button>`:''}${user.role==='admin' && record.status==='completed'?'<button id="reverse-final-qc">Koreksi final QC</button>':''}</div>`;
    $('final-qc-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(record.order_id);};
    if($('reverse-final-qc'))$('reverse-final-qc').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi final QC',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/final-qc-records/'+encodeURIComponent(record.id)+'/reverse',
        `${record.reference} · ${n(record.inspected_quantity)} pcs\nKoreksi mengembalikan seluruh hasil diterima, rework, dan reject ke QC. Catatan inspeksi asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="final-qc-record" data-id="${e(recordId)}">Coba lagi</button>`;}
}

const reworkCompletionRow = row => `<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>Dari ${e(row.final_qc_reference)} · ${e(row.sku)} · ${e(row.size)}</p><p>Diperiksa ulang ${n(row.reinspected_quantity)} pcs · belum diperiksa ${n(row.reinspection_remaining_quantity)} pcs</p><p>${row.status==='completed'?'Selesai':'Sudah dikoreksi'} · ${date(row.completed_date)}</p><button data-action="rework-completion" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian selesai rework</button></article>`;

function reworkCompletionList(title, path, emptyText, retryAction, retryId) {
  const version=epoch;openDialog(title,'<p class="state">Memuat catatan selesai rework...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  $('dialog-content').innerHTML='<p class="hint">Setiap catatan mengembalikan pcs dari rework ke QC dan menyimpan inspeksi asalnya, sehingga hasil rework dapat diinspeksi ulang secara sah.</p><div id="rework-completion-list"><p class="state">Memuat catatan selesai rework...</p></div><p id="rework-completion-error" class="error" role="alert" hidden></p><button id="rework-completion-more" type="button">Muat catatan sebelumnya</button>';
  let before=null;
  const load=async()=>{
    const button=$('rework-completion-more');button.disabled=true;message('rework-completion-error','');
    try{
      const rows=await api.get(path+'?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
      if(!current())return;
      if(!before)$('rework-completion-list').replaceChildren();
      appendRows('rework-completion-list',rows.map(reworkCompletionRow).join(''));
      if(!before && !rows.length)$('rework-completion-list').innerHTML=`<p class="state">${e(emptyText)}</p>`;
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat catatan sebelumnya';
    }catch(error){if(current()){message('rework-completion-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current())button.disabled=false;}
  };
  $('rework-completion-more').onclick=load;return load().catch(error=>{
    if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="${e(retryAction)}" data-id="${e(retryId)}">Coba lagi</button>`;});
}

async function reworkCompletionsDialog(orderId) {
  if(guardPending())return;
  await reworkCompletionList('Selesai rework order','/api/orders/'+encodeURIComponent(orderId)+'/rework-completions',
    'Belum ada catatan selesai rework untuk order ini. Buka final QC dengan hasil rework untuk mencatatnya.',
    'rework-completions',orderId);
}

async function finalQcReworkCompletionsDialog(recordId) {
  if(guardPending())return;
  await reworkCompletionList('Selesai rework final QC','/api/final-qc-records/'+encodeURIComponent(recordId)+'/rework-completions',
    'Belum ada catatan selesai rework untuk inspeksi ini.','final-qc-rework-completions',recordId);
}

async function reworkCompletionForm(qcId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat selesai rework','<p class="state">Memuat hasil final QC...</p>');const modal=dialogVersion;
  try{
    const qc=await api.get('/api/final-qc-records/'+encodeURIComponent(qcId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(qc.status!=='completed' || qc.rework_completable_quantity<1){$('dialog-content').innerHTML=`<p>${qc.status==='completed' && qc.rework_remaining_quantity>qc.rework_completable_quantity?`Rework catatan ini sudah dikembalikan ke QC oleh perpindahan tanpa catatan selesai rework. Koreksi perpindahan tersebut dari riwayat perpindahan order lebih dahulu.`:'Final QC sudah dikoreksi atau seluruh rework sudah diselesaikan. Muat ulang rinciannya.'}</p><button data-action="final-qc-record" data-id="${e(qcId)}">Muat ulang final QC</button>`;return;}
    const cap=qc.rework_completable_quantity;
    formDialog('Catat selesai rework',field('reference','Referensi selesai rework','text','required maxlength="160"')+
      field('quantity','Jumlah selesai rework (pcs)','number',`required min="1" max="${cap}" step="1" value="${cap}"`)+
      field('completed_date','Tanggal selesai rework','date',`required min="${e(qc.inspection_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={reference:data.get('reference'),quantity:Number(data.get('quantity')),completed_date:data.get('completed_date'),reason:data.get('reason')};if(payload.quantity<1)throw new Error('Jumlah selesai rework harus lebih dari nol.');if(payload.quantity>cap)throw new Error('Jumlah selesai rework melebihi rework yang masih berada di tahap rework.');return payload;},
      '/api/final-qc-records/'+encodeURIComponent(qcId)+'/rework-completions',
      `${qc.reference} · ${qc.sku} · ${qc.size}\nBelum selesai ${n(cap)} dari ${n(qc.rework_quantity)} pcs rework. Jumlah ini berpindah dari rework kembali ke QC dan siap diinspeksi ulang.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-rework-completion" data-id="${e(qcId)}">Coba lagi</button>`;}
}

async function reworkCompletionDialog(completionId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian selesai rework','<p class="state">Memuat catatan selesai rework...</p>');const modal=dialogVersion;
  try{
    const record=await api.get('/api/rework-completions/'+encodeURIComponent(completionId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(record.reference)} · ${record.status==='completed'?'Selesai':'Sudah dikoreksi'}</p><h3>${n(record.quantity)} pcs kembali ke QC · ${e(record.sku)} · ${e(record.size)}</h3><article class="material-event"><h3>Sumber rework</h3><p>Final QC ${e(record.final_qc_reference)} · rework ${n(record.final_qc_rework_quantity)} pcs · ${date(record.final_qc_inspection_date)}</p><p>Finishing ${e(record.finishing_reference)} · sewing ${e(record.sewing_reference)} · bundle ${e(record.bundle_reference)}</p><p>Selesai rework ${date(record.completed_date)}</p></article><article class="material-event"><h3>Status inspeksi ulang</h3><p>Sudah diperiksa ulang ${n(record.reinspected_quantity)} pcs · belum diperiksa ${n(record.reinspection_remaining_quantity)} pcs</p><p>Inspeksi ulang berikutnya tercatat sebagai inspeksi ulang #${n(record.next_inspection_round-1)}</p></article><p class="reason">${e(record.reason)}</p><p class="hint">${e(record.actor_name)} · ${purchaseStamp(record.created_at)}</p>${record.active_reinspection_count?`<p class="hint">${n(record.active_reinspection_count)} inspeksi ulang aktif. Koreksi inspeksi tersebut sebelum mengoreksi selesai rework.</p>`:''}${record.reversal?`<article class="material-event"><h3>Selesai rework dikoreksi</h3><p class="reason">${e(record.reversal.reason)}</p><p class="hint">${e(record.reversal.actor_name)} · ${purchaseStamp(record.reversal.created_at)}</p></article>`:''}<div class="actions"><button id="rework-completion-order">Buka order produksi</button><button data-action="final-qc-record" data-id="${e(record.final_qc_record_id)}">Final QC asal</button><button data-action="finishing-record" data-id="${e(record.finishing_record_id)}">Finishing asal</button><button data-action="sewing-job" data-id="${e(record.job_id)}">Job sewing asal</button><button data-action="bundle" data-id="${e(record.bundle_id)}">Bundle asal</button><button data-action="material-batch" data-id="${e(record.batch_id)}">Batch bahan asal</button><button data-action="final-qc-rework-completions" data-id="${e(record.final_qc_record_id)}">Semua selesai rework</button><button data-action="final-qc-records" data-id="${e(record.order_id)}">Final QC order</button>${user.role!=='viewer' && record.status==='completed' && record.reinspection_remaining_quantity>0?`<button data-action="new-reinspection" data-id="${e(record.id)}">Inspeksi ulang</button>`:''}${user.role==='admin' && record.status==='completed'?'<button id="reverse-rework-completion">Koreksi selesai rework</button>':''}</div>`;
    $('rework-completion-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(record.order_id);};
    if($('reverse-rework-completion'))$('reverse-rework-completion').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi selesai rework',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/rework-completions/'+encodeURIComponent(record.id)+'/reverse',
        `${record.reference} · ${n(record.quantity)} pcs\nKoreksi mengembalikan jumlah dari QC ke rework. Inspeksi ulang aktif harus dikoreksi lebih dahulu; catatan asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="rework-completion" data-id="${e(completionId)}">Coba lagi</button>`;}
}

async function reinspectionForm(completionId) {
  if(guardPending())return;
  const version=epoch;openDialog('Inspeksi ulang','<p class="state">Memuat catatan selesai rework...</p>');const modal=dialogVersion;
  try{
    const source=await api.get('/api/rework-completions/'+encodeURIComponent(completionId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(source.status!=='completed' || source.reinspection_remaining_quantity<1){$('dialog-content').innerHTML='<p>Catatan selesai rework sudah dikoreksi atau seluruh jumlahnya sudah diperiksa ulang. Muat ulang rinciannya.</p><button data-action="rework-completion" data-id="'+e(completionId)+'">Muat ulang selesai rework</button>';return;}
    const cap=source.reinspection_remaining_quantity;
    formDialog('Inspeksi ulang',field('reference','Referensi inspeksi ulang','text','required maxlength="160"')+
      '<label class="full">Catatan pengukuran<textarea name="measurement_notes" required maxlength="1000"></textarea></label>'+
      '<label class="full">Catatan pemeriksaan visual<textarea name="visual_notes" required maxlength="1000"></textarea></label>'+
      field('defect_type','Jenis defect','text','required maxlength="160"')+
      field('responsible_source','Sumber penanggung jawab','text','required maxlength="160"')+
      '<label class="full">Disposition<textarea name="disposition" required maxlength="1000"></textarea></label>'+
      field('accepted_quantity','Jumlah diterima','number',`required min="0" max="${cap}" step="1" value="${cap}"`)+
      field('rework_quantity','Jumlah rework','number',`required min="0" max="${cap}" step="1" value="0"`)+
      field('reject_quantity','Jumlah reject','number',`required min="0" max="${cap}" step="1" value="0"`)+
      field('inspection_date','Tanggal inspeksi ulang','date',`required min="${e(source.completed_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={reference:data.get('reference'),measurement_notes:data.get('measurement_notes'),visual_notes:data.get('visual_notes'),defect_type:data.get('defect_type'),responsible_source:data.get('responsible_source'),disposition:data.get('disposition'),accepted_quantity:Number(data.get('accepted_quantity')),rework_quantity:Number(data.get('rework_quantity')),reject_quantity:Number(data.get('reject_quantity')),inspection_date:data.get('inspection_date'),reason:data.get('reason')};const total=payload.accepted_quantity+payload.rework_quantity+payload.reject_quantity;if(total<1)throw new Error('Isi setidaknya satu hasil QC dengan jumlah lebih dari nol.');if(total>cap)throw new Error('Jumlah diterima + rework + reject melebihi hasil rework yang belum diperiksa.');return payload;},
      '/api/rework-completions/'+encodeURIComponent(completionId)+'/qc-records',
      `${source.reference} · ${source.sku} · ${source.size}\nInspeksi ulang #${n(source.next_inspection_round-1)} atas ${n(cap)} dari ${n(source.quantity)} pcs hasil rework. Jumlah diterima, rework, dan reject langsung berpindah dari QC ke posisi masing-masing.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-reinspection" data-id="${e(completionId)}">Coba lagi</button>`;}
}

async function finishedGoodsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Barang jadi order','<p class="state">Memuat penerimaan barang jadi...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  try{
    const [order,inventory]=await Promise.all([api.get('/api/orders/'+encodeURIComponent(orderId)),allRows('/api/finished-goods-inventory')]);
    if(!current())return;
    const productIds=new Set(order.lines.map(line=>line.product_id));
    const relevant=inventory.filter(row=>productIds.has(row.product_id));
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><h3>Inventori barang jadi</h3>${relevant.map(row=>`<article class="material-event"><strong>${e(row.sku)} · ${e(row.size)}</strong><p>Available ${n(row.available_quantity)} pcs · reserved ${n(row.reserved_quantity)} pcs · picked ${n(row.picked_quantity)} pcs · packed ${n(row.packed_quantity)} pcs · shipped ${n(row.shipped_quantity)} pcs · returned ${n(row.returned_quantity)} pcs</p><p>Sellable fisik ${n(row.sellable_quantity)} · hold ${n(row.hold_quantity)} · damaged ${n(row.damaged_quantity)} · total di gudang ${n(row.total_quantity)} pcs</p></article>`).join('')}<p class="hint">Shipped mencatat barang yang sudah keluar gudang. Returned menghitung barang yang sudah diterima kembali dan diperiksa. Angka ini adalah ledger internal Beeloft dan belum menyinkronkan stok Jubelio/WMS.</p><button data-action="warehouse" data-id="${e(orderId)}">Inventori per lokasi &amp; pergerakan</button><button data-action="marketplace-reservations" data-id="${e(orderId)}">Reservasi marketplace</button><button data-action="marketplace-picks" data-id="${e(orderId)}">Riwayat picking</button><button data-action="marketplace-packs" data-id="${e(orderId)}">Riwayat packing</button><button data-action="marketplace-shipments" data-id="${e(orderId)}">Riwayat shipping</button><button data-action="marketplace-returns" data-id="${e(orderId)}">Riwayat retur</button><button data-action="finished-goods-adjustments" data-id="${e(orderId)}">Riwayat adjustment</button><button data-action="finished-goods-stock-counts" data-id="${e(orderId)}">Riwayat stock opname</button><h3>Riwayat penerimaan</h3><div id="finished-goods-list"><p class="state">Memuat penerimaan...</p></div><p id="finished-goods-error" class="error" role="alert" hidden></p><button id="finished-goods-more" type="button">Muat penerimaan sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('finished-goods-more');button.disabled=true;message('finished-goods-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/finished-goods-receipts?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('finished-goods-list').replaceChildren();
        appendRows('finished-goods-list',rows.map(receipt=>`<article class="material-event"><h3>${e(receipt.reference)} · ${n(receipt.received_quantity)} pcs</h3><p>${e(receipt.sku)} · ${e(receipt.size)} · ${e(receipt.location)}</p><p>Sellable ${n(receipt.sellable_quantity)} · hold ${n(receipt.hold_quantity)} · ${receipt.status==='active'?'Aktif':'Sudah dikoreksi'}</p><p>${date(receipt.received_date)}</p><button data-action="finished-goods-receipt" data-id="${e(receipt.id)}" aria-label="Rincian ${e(receipt.reference)}">Rincian penerimaan</button></article>`).join(''));
        if(!before && !rows.length)$('finished-goods-list').innerHTML='<p class="state">Belum ada penerimaan barang jadi untuk order ini. Buka final QC dengan hasil diterima untuk mencatat penerimaan.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat penerimaan sebelumnya';
      }catch(error){if(current()){message('finished-goods-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('finished-goods-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finished-goods" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function finishedGoodsForm(qcId) {
  if(guardPending())return;
  const version=epoch;openDialog('Terima barang jadi','<p class="state">Memuat hasil final QC...</p>');const modal=dialogVersion;
  try{
    const qc=await api.get('/api/final-qc-records/'+encodeURIComponent(qcId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(qc.status!=='completed' || qc.warehouse_remaining_quantity<1){$('dialog-content').innerHTML='<p>Final QC sudah dikoreksi atau seluruh accepted quantity sudah diterima. Muat ulang rinciannya.</p><button data-action="final-qc-record" data-id="'+e(qcId)+'">Muat ulang final QC</button>';return;}
    formDialog('Terima barang jadi',field('reference','Referensi penerimaan','text','required maxlength="160"')+
      field('scanned_sku','SKU / barcode','text',`required maxlength="160" value="${e(qc.sku)}"`)+
      field('location','Lokasi gudang','text','required maxlength="160"')+
      field('sellable_quantity','Jumlah sellable','number',`required min="0" max="${qc.warehouse_remaining_quantity}" step="1" value="${qc.warehouse_remaining_quantity}"`)+
      field('hold_quantity','Jumlah hold','number',`required min="0" max="${qc.warehouse_remaining_quantity}" step="1" value="0"`)+
      field('received_date','Tanggal diterima','date',`required min="${e(qc.inspection_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={reference:data.get('reference'),scanned_sku:data.get('scanned_sku'),location:data.get('location'),sellable_quantity:Number(data.get('sellable_quantity')),hold_quantity:Number(data.get('hold_quantity')),received_date:data.get('received_date'),reason:data.get('reason')};const total=payload.sellable_quantity+payload.hold_quantity;if(total<1)throw new Error('Jumlah sellable + hold harus lebih dari nol.');if(total>qc.warehouse_remaining_quantity)throw new Error('Jumlah sellable + hold melebihi accepted quantity yang belum diterima.');if(payload.scanned_sku.trim().toLocaleLowerCase()!==qc.sku.toLocaleLowerCase())throw new Error('SKU hasil scan tidak cocok dengan barang dari final QC.');return payload;},
      '/api/final-qc-records/'+encodeURIComponent(qcId)+'/finished-goods-receipts',
      `${qc.reference} · ${qc.sku} · ${qc.size}\nBelum diterima ${n(qc.warehouse_remaining_quantity)} dari ${n(qc.accepted_quantity)} pcs accepted. Penerimaan mengelompokkan stok gudang menjadi sellable dan hold tanpa memindahkan WIP lagi.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-finished-goods" data-id="${e(qcId)}">Coba lagi</button>`;}
}

async function finishedGoodsReceiptDialog(receiptId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian barang jadi','<p class="state">Memuat penerimaan barang jadi...</p>');const modal=dialogVersion;
  try{
    const receipt=await api.get('/api/finished-goods-receipts/'+encodeURIComponent(receiptId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const sellable=receipt.inventory.some(row=>row.stock_status==='sellable'),hold=receipt.inventory.some(row=>row.stock_status==='hold'),damaged=receipt.inventory.some(row=>row.stock_status==='damaged');
    const reservable=receipt.inventory.some(row=>row.stock_status==='sellable'&&row.available_quantity>0);
    $('dialog-content').innerHTML=`<p class="form-info">${e(receipt.reference)} · ${receipt.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${n(receipt.received_quantity)} pcs · ${e(receipt.sku)} · ${e(receipt.size)}</h3><article class="material-event"><h3>Inventori sekarang</h3>${receipt.inventory.map(row=>`<p>${e(row.location)} · ${e(row.stock_status)} ${n(row.quantity)} pcs${row.stock_status==='sellable'?` · available ${n(row.available_quantity)} · reserved ${n(row.reserved_quantity)}`:''}</p>`).join('') || '<p>Stok penerimaan ini sudah dilepaskan.</p>'}<p>Diterima awal di ${e(receipt.location)} · ${date(receipt.received_date)}</p><p>SKU dipindai: ${e(receipt.scanned_sku)}</p></article><p>Final QC ${e(receipt.final_qc_reference)} · finishing ${e(receipt.finishing_reference)} · sewing ${e(receipt.sewing_reference)} · bundle ${e(receipt.bundle_reference)}</p><p class="reason">${e(receipt.reason)}</p><p class="hint">${e(receipt.actor_name)} · ${purchaseStamp(receipt.created_at)}</p>${receipt.active_movement_count?`<p class="hint">${n(receipt.active_movement_count)} pergerakan gudang aktif. Koreksi pergerakan tersebut sebelum mengoreksi penerimaan.</p>`:''}${receipt.active_reservation_count?`<p class="hint">${n(receipt.active_reservation_count)} reservasi marketplace aktif. Lepaskan reservasi tersebut sebelum mengoreksi penerimaan.</p>`:''}${receipt.active_adjustment_count?`<p class="hint">${n(receipt.active_adjustment_count)} adjustment aktif. Koreksi adjustment tersebut sebelum mengoreksi penerimaan.</p>`:''}${receipt.active_stock_count_count?`<p class="hint">${n(receipt.active_stock_count_count)} stock opname aktif. Koreksi catatan tersebut sebelum mengoreksi penerimaan.</p>`:''}${receipt.reversal?`<article class="material-event"><h3>Penerimaan barang jadi dikoreksi</h3><p class="reason">${e(receipt.reversal.reason)}</p><p class="hint">${e(receipt.reversal.actor_name)} · ${purchaseStamp(receipt.reversal.created_at)}</p></article>`:''}${receipt.status==='active'?`<section class="bundle-label finished-goods-label" aria-label="Label barang jadi ${e(receipt.reference)}"><img src="/api/finished-goods-receipts/${e(encodeURIComponent(receipt.id))}/label.svg" alt="Kode QR barang jadi ${e(receipt.reference)}"><div><strong>${e(receipt.reference)}</strong><span>${e(receipt.sku)} · ukuran ${e(receipt.size)}</span><span class="bundle-label-qty">${n(receipt.received_quantity)} pcs</span><span>${e(receipt.location)} · ${date(receipt.received_date)}</span><span>Order ${e(receipt.order_reference)}</span></div></section>`:''}<div class="actions"><button data-action="finished-goods-traceability" data-id="${e(receipt.id)}">Jejak stok lengkap</button><button id="finished-goods-order">Buka order produksi</button><button data-action="final-qc-record" data-id="${e(receipt.final_qc_record_id)}">Final QC asal</button><button data-action="finishing-record" data-id="${e(receipt.finishing_record_id)}">Finishing asal</button><button data-action="sewing-job" data-id="${e(receipt.job_id)}">Job sewing asal</button><button data-action="bundle" data-id="${e(receipt.bundle_id)}">Bundle asal</button><button data-action="finished-goods" data-id="${e(receipt.order_id)}">Semua barang jadi</button><button data-action="warehouse" data-id="${e(receipt.order_id)}">Gudang order</button><button data-action="marketplace-reservations" data-id="${e(receipt.order_id)}">Reservasi order</button><button data-action="finished-goods-adjustments" data-id="${e(receipt.order_id)}">Riwayat adjustment</button><button data-action="finished-goods-stock-counts" data-id="${e(receipt.order_id)}">Riwayat stock opname</button>${receipt.status==='active'?'<button id="print-finished-goods">Cetak label barang jadi</button>':''}${user.role!=='viewer'&&receipt.status==='active'?`<button data-action="new-finished-goods-stock-count" data-id="${e(receipt.id)}">Catat stock opname</button>`:''}${user.role!=='viewer'&&receipt.status==='active'?`<button data-action="new-finished-goods-adjustment" data-id="${e(receipt.id)}">Catat adjustment</button>`:''}${user.role!=='viewer'&&receipt.status==='active'&&reservable?`<button data-action="new-marketplace-reservation" data-id="${e(receipt.id)}">Reservasi marketplace</button>`:''}${user.role!=='viewer' && receipt.status==='active' && (sellable||hold||damaged)?`<button data-action="new-warehouse-movement" data-kind="transfer" data-id="${e(receipt.id)}">Transfer lokasi</button>`:''}${user.role!=='viewer' && receipt.status==='active' && hold?`<button data-action="new-warehouse-movement" data-kind="hold_release" data-id="${e(receipt.id)}">Lepaskan hold</button><button data-action="new-warehouse-movement" data-kind="hold_damage" data-id="${e(receipt.id)}">Tandai damaged</button>`:''}${user.role==='admin' && receipt.status==='active' && !receipt.active_movement_count && !receipt.active_reservation_count && !receipt.active_adjustment_count && !receipt.active_stock_count_count?'<button id="reverse-finished-goods">Koreksi penerimaan</button>':''}</div>`;
    $('finished-goods-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(receipt.order_id);};
    if($('print-finished-goods'))$('print-finished-goods').onclick=()=>window.print();
    if($('reverse-finished-goods'))$('reverse-finished-goods').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi penerimaan barang jadi',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/finished-goods-receipts/'+encodeURIComponent(receipt.id)+'/reverse',
        `${receipt.reference} · ${n(receipt.received_quantity)} pcs\nKoreksi melepaskan klasifikasi sellable/hold tanpa mengubah saldo WIP warehouse. Riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finished-goods-receipt" data-id="${e(receiptId)}">Coba lagi</button>`;}
}

const traceEventLabels={
  finished_goods_receipt:'Penerimaan barang jadi',warehouse_movement:'Pergerakan gudang',
  marketplace_reservation:'Reservasi marketplace',marketplace_reservation_release:'Pelepasan reservasi',
  marketplace_pick:'Picking',marketplace_pack:'Packing',marketplace_shipment:'Pengiriman',
  marketplace_return:'Retur pelanggan',finished_goods_adjustment:'Adjustment',finished_goods_stock_count:'Stock opname'
};
const traceStatusLabels={active:'Aktif',corrected:'Sudah dikoreksi',correction:'Koreksi',released:'Dilepaskan',shipped:'Sudah dikirim'};

async function finishedGoodsTraceabilityDialog(receiptId) {
  if(guardPending())return;
  const version=epoch;openDialog('Jejak stok barang jadi','<p class="state">Memuat jejak stok...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  const endpoint='/api/finished-goods-receipts/'+encodeURIComponent(receiptId)+'/traceability';
  try{
    const report=await api.get(endpoint+'?limit=50');
    if(!current())return;
    const receipt=report.receipt;
    $('dialog-content').innerHTML=`<p class="form-info">${e(receipt.reference)} · ${e(receipt.sku)} · ${e(receipt.size)}</p>
      <h3>${n(receipt.received_quantity)} pcs diterima · ${n(report.total)} catatan terlacak</h3>
      <article class="material-event"><h3>Posisi sekarang</h3>${receipt.inventory.map(row=>`<p>${e(row.location)} · ${e(warehouseStatus[row.stock_status])} ${n(row.quantity)} pcs${row.stock_status==='sellable'?` · available ${n(row.available_quantity)} · reserved ${n(row.reserved_quantity)}`:''}</p>`).join('')||'<p>Stok penerimaan ini sudah keluar atau dikoreksi.</p>'}</article>
      <h3>Asal produksi</h3><p>Order ${e(receipt.order_reference)} · batch ${e(receipt.batch_reference)}</p>
      <div class="actions"><button data-action="material-batch" data-id="${e(receipt.batch_id)}">Batch bahan asal</button><button data-action="bundle" data-id="${e(receipt.bundle_id)}">Bundle ${e(receipt.bundle_reference)}</button><button data-action="final-qc-record" data-id="${e(receipt.final_qc_record_id)}">Final QC ${e(receipt.final_qc_reference)}</button></div>
      <h3>Jejak penerimaan dan fulfillment</h3><p class="hint">Terbaru menurut waktu pencatatan. Jumlah pada tiap catatan bukan angka untuk dijumlahkan; stock opname dan adjustment selisih adalah dua catatan dari hitungan yang sama.</p>
      <div id="finished-goods-trace-events"></div><p id="finished-goods-trace-error" class="error" role="alert" hidden></p>
      <button id="finished-goods-trace-more" type="button">Muat catatan sebelumnya</button>
      <div class="actions"><button data-action="finished-goods-receipt" data-id="${e(receipt.id)}">Rincian penerimaan</button><button data-action="finished-goods-traceability" data-id="${e(receipt.id)}">Muat ulang jejak</button></div>`;
    let cursor=report.next_before;
    const append=rows=>{
      appendRows('finished-goods-trace-events',rows.map(row=>{
        const corrected=row.event_type.endsWith('_correction');
        const label=(corrected?'Koreksi · ':'')+traceEventLabels[row.event_type.replace(/_correction$/,'')];
        return `<article class="material-event" data-trace-event="${e(row.event_type)}"><h3>${e(label)} · ${e(row.reference)}</h3>
          <p>${n(row.quantity)} pcs · ${e(traceStatusLabels[row.status])}</p><p>${e(row.description)}</p>
          ${row.business_date?`<p>Tanggal transaksi ${date(row.business_date)}</p>`:''}
          ${row.scanned_code?`<p>Scan pada catatan asal: ${e(row.scanned_code)}</p>`:''}
          <p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · dicatat ${purchaseStamp(row.created_at)}</p>
          <button data-action="${e(row.detail_action)}" data-id="${e(row.object_id)}" aria-label="Rincian ${e(label)} ${e(row.reference)}">Buka rincian</button></article>`;
      }).join(''));
      $('finished-goods-trace-more').hidden=!cursor;
    };
    $('finished-goods-trace-more').onclick=async()=>{
      const button=$('finished-goods-trace-more');button.disabled=true;message('finished-goods-trace-error','');
      try{
        const page=await api.get(endpoint+'?'+new URLSearchParams({limit:50,...cursor}));
        if(!current())return;
        cursor=page.next_before;append(page.events);
      }catch(error){if(current())message('finished-goods-trace-error',error.message,true);}
      finally{if(current())button.disabled=false;}
    };
    append(report.events);
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finished-goods-traceability" data-id="${e(receiptId)}">Coba lagi</button>`;}
}

const warehouseStatus={sellable:'Sellable',hold:'Hold',damaged:'Damaged',picked:'Picked',packed:'Packed'};
const warehouseKind={transfer:'Transfer lokasi',hold_release:'Pelepasan hold',hold_damage:'Hold menjadi damaged'};

async function warehouseDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Gudang order','<p class="state">Memuat inventori gudang...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  try{
    const [order,inventory]=await Promise.all([api.get('/api/orders/'+encodeURIComponent(orderId)),allRows('/api/warehouse-inventory')]);
    if(!current())return;
    const productIds=new Set(order.lines.map(line=>line.product_id));
    const relevant=inventory.filter(row=>productIds.has(row.product_id));
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><h3>Inventori per lokasi</h3>${relevant.map(row=>`<article class="material-event"><strong>${e(row.sku)} · ${e(row.location)}</strong><p>${e(warehouseStatus[row.stock_status])} ${n(row.quantity)} pcs${row.stock_status==='sellable'?` · available ${n(row.available_quantity)} · reserved ${n(row.reserved_quantity)}`:''}</p></article>`).join('') || '<p class="state">Belum ada inventori barang jadi untuk order ini.</p>'}<p class="hint">Sellable dibagi menjadi available dan reserved. Picked menunggu packing; packed menunggu penyerahan ke carrier. Barang shipped sudah keluar dari inventori lokasi. Hold dan damaged tetap terpisah.</p><button data-action="finished-goods" data-id="${e(orderId)}">Penerimaan barang jadi</button><button data-action="marketplace-reservations" data-id="${e(orderId)}">Reservasi marketplace</button><button data-action="marketplace-picks" data-id="${e(orderId)}">Riwayat picking</button><button data-action="marketplace-packs" data-id="${e(orderId)}">Riwayat packing</button><button data-action="marketplace-shipments" data-id="${e(orderId)}">Riwayat shipping</button><h3>Riwayat pergerakan</h3><div id="warehouse-list"><p class="state">Memuat pergerakan...</p></div><p id="warehouse-error" class="error" role="alert" hidden></p><button id="warehouse-more" type="button">Muat pergerakan sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('warehouse-more');button.disabled=true;message('warehouse-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/warehouse-movements?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('warehouse-list').replaceChildren();
        appendRows('warehouse-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(warehouseKind[row.kind])} · ${e(row.sku)}</p><p>${e(row.from_location)} (${e(warehouseStatus[row.from_status])}) → ${e(row.to_location)} (${e(warehouseStatus[row.to_status])})</p><p>${row.status==='active'?'Aktif':'Sudah dikoreksi'} · ${date(row.moved_date)}</p><button data-action="warehouse-movement" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian pergerakan</button></article>`).join(''));
        if(!before && !rows.length)$('warehouse-list').innerHTML='<p class="state">Belum ada pergerakan gudang untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pergerakan sebelumnya';
      }catch(error){if(current()){message('warehouse-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('warehouse-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="warehouse" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function warehouseMovementForm(receiptId,kind) {
  if(guardPending())return;
  const title=warehouseKind[kind] || 'Pergerakan gudang';
  const version=epoch;openDialog(title,'<p class="state">Memuat inventori penerimaan...</p>');const modal=dialogVersion;
  try{
    const receipt=await api.get('/api/finished-goods-receipts/'+encodeURIComponent(receiptId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const buckets=receipt.inventory.filter(row=>kind==='transfer'?row.movable_quantity>0:row.stock_status==='hold');
    if(receipt.status!=='active' || !buckets.length){$('dialog-content').innerHTML='<p>Tidak ada stok aktif yang sesuai untuk tindakan ini. Muat ulang rincian penerimaan.</p><button data-action="finished-goods-receipt" data-id="'+e(receiptId)+'">Muat ulang penerimaan</button>';return;}
    const source=`<div><label for="warehouse-source">Stok asal</label><select id="warehouse-source" name="source">${buckets.map((row,index)=>option(index,`${row.location} · ${warehouseStatus[row.stock_status]} ${n(row.movable_quantity)} pcs dapat dipindah`)).join('')}</select></div>`;
    formDialog(title,field('scanned_code','SKU / QR lot','text','id="warehouse-scan-code" required maxlength="200" autocomplete="off"')+
      field('reference','Referensi pergerakan','text','required maxlength="160"')+source+
      field('to_location','Lokasi tujuan','text','required maxlength="160"')+
      field('quantity','Jumlah','number','required min="1" step="1"')+
      field('moved_date','Tanggal pergerakan','date',`required min="${e(receipt.received_date)}"`)+materialReason,
      form=>{const data=new FormData(form),bucket=buckets[Number(data.get('source'))],payload={scanned_code:data.get('scanned_code'),reference:data.get('reference'),kind,from_location:bucket.location,to_location:data.get('to_location'),quantity:Number(data.get('quantity')),moved_date:data.get('moved_date'),reason:data.get('reason')};if(![receipt.sku,receipt.scan_code].some(code=>code.toLocaleLowerCase()===payload.scanned_code.trim().toLocaleLowerCase()))throw new Error('SKU atau QR lot hasil scan tidak cocok dengan penerimaan barang jadi.');if(kind==='transfer')payload.stock_status=bucket.stock_status;if(payload.quantity>bucket.movable_quantity)throw new Error('Jumlah melebihi stok yang dapat dipindahkan pada lokasi dan status asal.');if(kind==='transfer'&&payload.from_location.trim().toLocaleLowerCase()===payload.to_location.trim().toLocaleLowerCase())throw new Error('Lokasi tujuan transfer harus berbeda dari lokasi asal.');return payload;},
      '/api/finished-goods-receipts/'+encodeURIComponent(receiptId)+'/warehouse-movements',
      `${receipt.reference} · ${receipt.sku}\nScan SKU atau QR lot pada label penerimaan sebelum stok dipindahkan.\n${kind==='transfer'?'Status stok tetap sama selama transfer.':'Keputusan hanya mengambil stok hold dari lokasi yang dipilih.'}`);
    const updateMax=()=>{const bucket=buckets[Number($('warehouse-source').value)];$('action-form').elements.quantity.max=bucket.movable_quantity;};
    $('warehouse-source').onchange=updateMax;updateMax();
    $('warehouse-scan-code').focus();
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-warehouse-movement" data-kind="${e(kind)}" data-id="${e(receiptId)}">Coba lagi</button>`;}
}

async function warehouseMovementDialog(movementId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian pergerakan gudang','<p class="state">Memuat pergerakan gudang...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/warehouse-movements/'+encodeURIComponent(movementId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(warehouseKind[row.kind])}</h3><p>${e(row.from_location)} · ${e(warehouseStatus[row.from_status])}</p><p>→ ${e(row.to_location)} · ${e(warehouseStatus[row.to_status])}</p><p>${date(row.moved_date)}</p><p>Validasi scan: ${row.scanned_code?e(row.scanned_code):'Catatan lama, dibuat sebelum scan diwajibkan'}</p></article><p>Penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.reversal?`<article class="material-event"><h3>Pergerakan gudang dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}<div class="actions"><button data-action="finished-goods-receipt" data-id="${e(row.receipt_id)}">Penerimaan asal</button><button data-action="warehouse" data-id="${e(row.order_id)}">Gudang order</button>${user.role==='admin'&&row.status==='active'?'<button id="reverse-warehouse">Koreksi pergerakan</button>':''}</div>`;
    if($('reverse-warehouse'))$('reverse-warehouse').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi pergerakan gudang',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/warehouse-movements/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · ${n(row.quantity)} pcs\nKoreksi mengembalikan stok ke lokasi dan status asal. Riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="warehouse-movement" data-id="${e(movementId)}">Coba lagi</button>`;}
}

async function marketplaceReservationsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Reservasi marketplace','<p class="state">Memuat reservasi...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  try{
    const [order,inventory]=await Promise.all([api.get('/api/orders/'+encodeURIComponent(orderId)),allRows('/api/finished-goods-inventory')]);
    if(!current())return;
    const productIds=new Set(order.lines.map(line=>line.product_id));
    const relevant=inventory.filter(row=>productIds.has(row.product_id));
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><h3>Alokasi stok jual</h3>${relevant.map(row=>`<article class="material-event"><strong>${e(row.sku)} · ${e(row.size)}</strong><p>Available ${n(row.available_quantity)} pcs · reserved ${n(row.reserved_quantity)} pcs · sellable fisik ${n(row.sellable_quantity)} pcs</p></article>`).join('') || '<p class="state">Belum ada stok sellable.</p>'}<p class="hint">Reservasi mengurangi available tanpa mengubah stok fisik atau WIP.</p><button data-action="finished-goods" data-id="${e(orderId)}">Pilih penerimaan sumber</button><h3>Riwayat reservasi</h3><div id="marketplace-list"><p class="state">Memuat reservasi...</p></div><p id="marketplace-error" class="error" role="alert" hidden></p><button id="marketplace-more" type="button">Muat reservasi sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('marketplace-more');button.disabled=true;message('marketplace-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/marketplace-reservations?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('marketplace-list').replaceChildren();
        appendRows('marketplace-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(row.marketplace)} · ${e(row.external_order_reference)}</p><p>${e(row.sku)} · ${e(row.location)} · ${row.status==='active'?'Reserved':'Dilepaskan'}</p><p>Sudah dipick ${n(row.picked_quantity)} · sisa ${n(row.remaining_quantity)} pcs · ${date(row.reserved_date)}</p><button data-action="marketplace-reservation" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian reservasi</button></article>`).join(''));
        if(!before&&!rows.length)$('marketplace-list').innerHTML='<p class="state">Belum ada reservasi marketplace untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat reservasi sebelumnya';
      }catch(error){if(current()){message('marketplace-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('marketplace-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-reservations" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function marketplaceReservationForm(receiptId) {
  if(guardPending())return;
  const version=epoch;openDialog('Reservasi marketplace','<p class="state">Memuat stok sellable...</p>');const modal=dialogVersion;
  try{
    const receipt=await api.get('/api/finished-goods-receipts/'+encodeURIComponent(receiptId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const buckets=receipt.inventory.filter(row=>row.stock_status==='sellable'&&row.available_quantity>0);
    if(receipt.status!=='active'||!buckets.length){$('dialog-content').innerHTML='<p>Tidak ada stok sellable tersedia pada penerimaan ini.</p><button data-action="finished-goods-receipt" data-id="'+e(receiptId)+'">Muat ulang penerimaan</button>';return;}
    const source=`<div><label for="marketplace-source">Stok sellable</label><select id="marketplace-source" name="source">${buckets.map((row,index)=>option(index,`${row.location} · available ${n(row.available_quantity)} pcs`)).join('')}</select></div>`;
    formDialog('Reservasi marketplace',field('reference','Referensi reservasi','text','required maxlength="160"')+
      field('marketplace','Marketplace','text','required maxlength="160"')+
      field('external_order_reference','Referensi order marketplace','text','required maxlength="160"')+source+
      field('quantity','Jumlah reservasi','number','required min="1" step="1"')+
      field('reserved_date','Tanggal reservasi','date',`required min="${e(receipt.received_date)}"`)+materialReason,
      form=>{const data=new FormData(form),bucket=buckets[Number(data.get('source'))],payload={reference:data.get('reference'),marketplace:data.get('marketplace'),external_order_reference:data.get('external_order_reference'),location:bucket.location,quantity:Number(data.get('quantity')),reserved_date:data.get('reserved_date'),reason:data.get('reason')};if(payload.quantity>bucket.available_quantity)throw new Error('Jumlah reservasi melebihi stok sellable yang tersedia.');return payload;},
      '/api/finished-goods-receipts/'+encodeURIComponent(receiptId)+'/marketplace-reservations',
      `${receipt.reference} · ${receipt.sku}\nReservasi mengikat stok tersedia ke order marketplace tanpa mengubah jumlah fisik.`);
    const updateMax=()=>{const bucket=buckets[Number($('marketplace-source').value)];$('action-form').elements.quantity.max=bucket.available_quantity;};
    $('marketplace-source').onchange=updateMax;updateMax();
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-marketplace-reservation" data-id="${e(receiptId)}">Coba lagi</button>`;}
}

async function marketplaceReservationDialog(reservationId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian reservasi marketplace','<p class="state">Memuat reservasi...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-reservations/'+encodeURIComponent(reservationId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Reserved':'Dilepaskan'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(row.marketplace)}</h3><p>Order ${e(row.external_order_reference)}</p><p>${e(row.location)} · ${date(row.reserved_date)}</p><p>Sudah dipick ${n(row.picked_quantity)} pcs · sisa ${n(row.remaining_quantity)} pcs</p></article><p>Penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.release?`<article class="material-event"><h3>Reservasi dilepaskan</h3><p>${date(row.release.released_date)}</p><p class="reason">${e(row.release.reason)}</p><p class="hint">${e(row.release.actor_name)} · ${purchaseStamp(row.release.created_at)}</p></article>`:''}${row.picked_quantity?'<p class="hint">Koreksi semua pick aktif sebelum melepas reservasi.</p>':''}<div class="actions"><button data-action="finished-goods-receipt" data-id="${e(row.receipt_id)}">Penerimaan asal</button><button data-action="marketplace-reservations" data-id="${e(row.order_id)}">Semua reservasi</button><button data-action="marketplace-picks" data-id="${e(row.order_id)}">Riwayat picking</button>${user.role!=='viewer'&&row.status==='active'&&row.remaining_quantity>0?`<button data-action="new-marketplace-pick" data-id="${e(row.id)}">Catat pick</button>`:''}${user.role!=='viewer'&&row.status==='active'&&!row.picked_quantity?'<button id="release-marketplace">Lepaskan reservasi</button>':''}</div>`;
    if($('release-marketplace'))$('release-marketplace').onclick=()=>{
      if(guardPending())return;
      formDialog('Lepaskan reservasi',field('released_date','Tanggal pelepasan','date',`required min="${e(row.reserved_date)}"`)+materialReason,
        form=>Object.fromEntries(new FormData(form)),
        '/api/marketplace-reservations/'+encodeURIComponent(row.id)+'/release',
        `${row.marketplace} · ${row.external_order_reference} · ${n(row.quantity)} pcs\nSeluruh alokasi kembali menjadi available.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-reservation" data-id="${e(reservationId)}">Coba lagi</button>`;}
}

async function marketplacePicksDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Picking marketplace','<p class="state">Memuat riwayat pick...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const order=await api.get('/api/orders/'+encodeURIComponent(orderId));
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Pick memindahkan stok reserved dari rak sellable ke lokasi staging.</p><button data-action="marketplace-reservations" data-id="${e(orderId)}">Reservasi marketplace</button><button data-action="marketplace-packs" data-id="${e(orderId)}">Riwayat packing</button><button data-action="warehouse" data-id="${e(orderId)}">Inventori gudang</button><h3>Riwayat pick</h3><div id="marketplace-pick-list"><p class="state">Memuat pick...</p></div><p id="marketplace-pick-error" class="error" role="alert" hidden></p><button id="marketplace-pick-more" type="button">Muat pick sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('marketplace-pick-more');button.disabled=true;message('marketplace-pick-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/marketplace-picks?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('marketplace-pick-list').replaceChildren();
        appendRows('marketplace-pick-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(row.marketplace)} · ${e(row.external_order_reference)}</p><p>${e(row.location)} → ${e(row.staging_location)} · ${row.status==='active'?'Di staging':'Sudah dikoreksi'}</p><p>Packed ${n(row.packed_quantity)} · sisa ${n(row.remaining_quantity)} pcs · ${date(row.picked_date)}</p><button data-action="marketplace-pick" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian pick</button></article>`).join(''));
        if(!before&&!rows.length)$('marketplace-pick-list').innerHTML='<p class="state">Belum ada pick marketplace untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pick sebelumnya';
      }catch(error){if(current()){message('marketplace-pick-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('marketplace-pick-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-picks" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function marketplacePickForm(reservationId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat pick marketplace','<p class="state">Memuat reservasi...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-reservations/'+encodeURIComponent(reservationId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(row.status!=='active'||row.remaining_quantity<1){$('dialog-content').innerHTML='<p>Reservasi ini tidak memiliki jumlah yang dapat dipick. Muat ulang rinciannya.</p><button data-action="marketplace-reservation" data-id="'+e(reservationId)+'">Muat ulang reservasi</button>';return;}
    formDialog('Catat pick marketplace',field('reference','Referensi pick','text','required maxlength="160"')+
      field('scanned_code','SKU / QR lot','text','required maxlength="200" autocomplete="off" spellcheck="false" id="pick-scan-code" autofocus')+
      field('quantity','Jumlah pick','number',`required min="1" max="${row.remaining_quantity}" step="1"`)+
      field('staging_location','Lokasi staging','text','required maxlength="160"')+
      field('picked_date','Tanggal pick','date',`required min="${e(row.reserved_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={reference:data.get('reference'),scanned_code:data.get('scanned_code'),quantity:Number(data.get('quantity')),staging_location:data.get('staging_location'),picked_date:data.get('picked_date'),reason:data.get('reason')};if(payload.quantity>row.remaining_quantity)throw new Error('Jumlah pick melebihi sisa reservasi.');if(![row.sku,row.receipt_scan_code].some(value=>value.toLocaleLowerCase()===payload.scanned_code.trim().toLocaleLowerCase()))throw new Error('SKU atau QR lot hasil scan tidak cocok dengan reservasi marketplace.');return payload;},
      '/api/marketplace-reservations/'+encodeURIComponent(row.id)+'/picks',
      `${row.reference} · ${row.marketplace} · ${row.external_order_reference}\nPindai QR lot barang jadi atau SKU ${row.sku} sebelum mengambil stok. Sisa reservasi ${n(row.remaining_quantity)} dari ${n(row.quantity)} pcs di ${row.location}.`);
    $('pick-scan-code').focus();
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-marketplace-pick" data-id="${e(reservationId)}">Coba lagi</button>`;}
}

async function marketplacePickDialog(pickId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian pick','<p class="state">Memuat catatan pick...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-picks/'+encodeURIComponent(pickId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Di staging':'Sudah dikoreksi'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(row.marketplace)} · ${e(row.external_order_reference)}</h3><p>${e(row.location)} → ${e(row.staging_location)}</p><p>Dipick ${date(row.picked_date)} · packed ${n(row.packed_quantity)} pcs · sisa ${n(row.remaining_quantity)} pcs</p><p>Validasi scan: ${row.scanned_code?e(row.scanned_code):'Catatan lama sebelum scan diwajibkan'}</p></article><p>Reservasi ${e(row.reservation_reference)} · penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.reversal?`<article class="material-event"><h3>Pick dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}${row.packed_quantity?'<p class="hint">Koreksi semua pack aktif sebelum mengoreksi pick.</p>':''}<div class="actions"><button data-action="marketplace-reservation" data-id="${e(row.reservation_id)}">Reservasi asal</button><button data-action="marketplace-picks" data-id="${e(row.order_id)}">Semua pick</button><button data-action="marketplace-packs" data-id="${e(row.order_id)}">Riwayat packing</button><button data-action="warehouse" data-id="${e(row.order_id)}">Inventori gudang</button>${user.role!=='viewer'&&row.status==='active'&&row.remaining_quantity>0?`<button data-action="new-marketplace-pack" data-id="${e(row.id)}">Catat pack</button>`:''}${user.role==='admin'&&row.status==='active'&&!row.packed_quantity?'<button id="reverse-marketplace-pick">Koreksi pick</button>':''}</div>`;
    if($('reverse-marketplace-pick'))$('reverse-marketplace-pick').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi pick',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/marketplace-picks/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · ${n(row.quantity)} pcs\nKoreksi mengembalikan barang dari staging ke reserved sellable. Riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-pick" data-id="${e(pickId)}">Coba lagi</button>`;}
}

async function marketplacePacksDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Packing marketplace','<p class="state">Memuat riwayat pack...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const order=await api.get('/api/orders/'+encodeURIComponent(orderId));
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Pack memindahkan barang dari picked ke packed pada lokasi staging yang sama.</p><button data-action="marketplace-picks" data-id="${e(orderId)}">Riwayat picking</button><button data-action="marketplace-shipments" data-id="${e(orderId)}">Riwayat shipping</button><button data-action="warehouse" data-id="${e(orderId)}">Inventori gudang</button><h3>Riwayat pack</h3><div id="marketplace-pack-list"><p class="state">Memuat pack...</p></div><p id="marketplace-pack-error" class="error" role="alert" hidden></p><button id="marketplace-pack-more" type="button">Muat pack sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('marketplace-pack-more');button.disabled=true;message('marketplace-pack-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/marketplace-packs?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('marketplace-pack-list').replaceChildren();
        appendRows('marketplace-pack-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(row.marketplace)} · ${e(row.external_order_reference)}</p><p>${e(row.sku)} · ${e(row.staging_location)} · ${row.status==='active'?'Packed':'Sudah dikoreksi'}</p><p>Shipped ${n(row.shipped_quantity)} · sisa ${n(row.remaining_quantity)} pcs · ${date(row.packed_date)}</p><button data-action="marketplace-pack" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian pack</button></article>`).join(''));
        if(!before&&!rows.length)$('marketplace-pack-list').innerHTML='<p class="state">Belum ada pack marketplace untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pack sebelumnya';
      }catch(error){if(current()){message('marketplace-pack-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('marketplace-pack-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-packs" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function marketplacePackForm(pickId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat pack marketplace','<p class="state">Memuat pick...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-picks/'+encodeURIComponent(pickId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(row.status!=='active'||row.remaining_quantity<1){$('dialog-content').innerHTML='<p>Pick ini tidak memiliki jumlah yang dapat dipack. Muat ulang rinciannya.</p><button data-action="marketplace-pick" data-id="'+e(pickId)+'">Muat ulang pick</button>';return;}
    formDialog('Catat pack marketplace',field('reference','Referensi pack','text','required maxlength="160"')+
      field('quantity','Jumlah pack','number',`required min="1" max="${row.remaining_quantity}" step="1"`)+
      field('packed_date','Tanggal pack','date',`required min="${e(row.picked_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={reference:data.get('reference'),quantity:Number(data.get('quantity')),packed_date:data.get('packed_date'),reason:data.get('reason')};if(payload.quantity>row.remaining_quantity)throw new Error('Jumlah pack melebihi sisa pick.');return payload;},
      '/api/marketplace-picks/'+encodeURIComponent(row.id)+'/packs',
      `${row.reference} · ${row.marketplace} · ${row.external_order_reference}\nSisa pick ${n(row.remaining_quantity)} dari ${n(row.quantity)} pcs di ${row.staging_location}.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-marketplace-pack" data-id="${e(pickId)}">Coba lagi</button>`;}
}

async function marketplacePackDialog(packId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian pack','<p class="state">Memuat catatan pack...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-packs/'+encodeURIComponent(packId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Packed':'Sudah dikoreksi'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(row.marketplace)} · ${e(row.external_order_reference)}</h3><p>${e(row.staging_location)} · dipack ${date(row.packed_date)}</p><p>Shipped ${n(row.shipped_quantity)} pcs · sisa ${n(row.remaining_quantity)} pcs</p><p>Sumber pick ${e(row.pick_reference)} · ${date(row.picked_date)}</p></article><p>Reservasi ${e(row.reservation_reference)} · penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.reversal?`<article class="material-event"><h3>Pack dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}${row.shipped_quantity?'<p class="hint">Koreksi semua pengiriman aktif sebelum mengoreksi pack.</p>':''}<div class="actions"><button data-action="marketplace-pick" data-id="${e(row.pick_id)}">Pick asal</button><button data-action="marketplace-packs" data-id="${e(row.order_id)}">Semua pack</button><button data-action="marketplace-shipments" data-id="${e(row.order_id)}">Riwayat shipping</button><button data-action="warehouse" data-id="${e(row.order_id)}">Inventori gudang</button>${user.role!=='viewer'&&row.status==='active'&&row.remaining_quantity>0?`<button data-action="new-marketplace-shipment" data-id="${e(row.id)}">Catat pengiriman</button>`:''}${user.role==='admin'&&row.status==='active'&&!row.shipped_quantity?'<button id="reverse-marketplace-pack">Koreksi pack</button>':''}</div>`;
    if($('reverse-marketplace-pack'))$('reverse-marketplace-pack').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi pack',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/marketplace-packs/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · ${n(row.quantity)} pcs\nKoreksi mengembalikan barang dari packed ke picked di ${row.staging_location}. Riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-pack" data-id="${e(packId)}">Coba lagi</button>`;}
}

async function marketplaceShipmentsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Shipping marketplace','<p class="state">Memuat riwayat pengiriman...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const order=await api.get('/api/orders/'+encodeURIComponent(orderId));
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Pengiriman mencatat penyerahan barang packed ke carrier dan mengeluarkannya dari inventori gudang.</p><button data-action="marketplace-packs" data-id="${e(orderId)}">Riwayat packing</button><button data-action="marketplace-returns" data-id="${e(orderId)}">Riwayat retur</button><button data-action="warehouse" data-id="${e(orderId)}">Inventori gudang</button><h3>Riwayat pengiriman</h3><div id="marketplace-shipment-list"><p class="state">Memuat pengiriman...</p></div><p id="marketplace-shipment-error" class="error" role="alert" hidden></p><button id="marketplace-shipment-more" type="button">Muat pengiriman sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('marketplace-shipment-more');button.disabled=true;message('marketplace-shipment-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/marketplace-shipments?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('marketplace-shipment-list').replaceChildren();
        appendRows('marketplace-shipment-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(row.marketplace)} · ${e(row.external_order_reference)}</p><p>${e(row.carrier)} · resi ${e(row.tracking_number)}</p><p>${e(row.sku)} · ${row.status==='shipped'?'Sudah dikirim':'Sudah dikoreksi'} · retur ${n(row.returned_quantity)} pcs · ${date(row.shipped_date)}</p><p class="hint">${row.sale_settlement_id?'Settlement '+e(row.sale_settlement_reference):'Settlement penjualan belum dicatat'}</p><button data-action="marketplace-shipment" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian pengiriman</button></article>`).join(''));
        if(!before&&!rows.length)$('marketplace-shipment-list').innerHTML='<p class="state">Belum ada pengiriman marketplace untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pengiriman sebelumnya';
      }catch(error){if(current()){message('marketplace-shipment-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('marketplace-shipment-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-shipments" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function marketplaceShipmentForm(packId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat pengiriman marketplace','<p class="state">Memuat pack...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-packs/'+encodeURIComponent(packId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(row.status!=='active'||row.remaining_quantity<1){$('dialog-content').innerHTML='<p>Pack ini tidak memiliki jumlah yang dapat dikirim. Muat ulang rinciannya.</p><button data-action="marketplace-pack" data-id="'+e(packId)+'">Muat ulang pack</button>';return;}
    formDialog('Catat pengiriman marketplace',field('reference','Referensi pengiriman','text','required maxlength="160"')+
      field('quantity','Jumlah kirim','number',`required min="1" max="${row.remaining_quantity}" step="1"`)+
      field('carrier','Carrier','text','required maxlength="160"')+
      field('tracking_number','Nomor resi','text','required maxlength="160"')+
      field('shipped_date','Tanggal kirim','date',`required min="${e(row.packed_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={reference:data.get('reference'),quantity:Number(data.get('quantity')),carrier:data.get('carrier'),tracking_number:data.get('tracking_number'),shipped_date:data.get('shipped_date'),reason:data.get('reason')};if(payload.quantity>row.remaining_quantity)throw new Error('Jumlah kirim melebihi sisa pack.');return payload;},
      '/api/marketplace-packs/'+encodeURIComponent(row.id)+'/shipments',
      `${row.reference} · ${row.marketplace} · ${row.external_order_reference}\nSisa pack ${n(row.remaining_quantity)} dari ${n(row.quantity)} pcs di ${row.staging_location}.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-marketplace-shipment" data-id="${e(packId)}">Coba lagi</button>`;}
}

async function marketplaceShipmentDialog(shipmentId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian pengiriman','<p class="state">Memuat catatan pengiriman...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-shipments/'+encodeURIComponent(shipmentId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='shipped'?'Sudah dikirim':'Sudah dikoreksi'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(row.marketplace)} · ${e(row.external_order_reference)}</h3><p>${e(row.carrier)} · resi ${e(row.tracking_number)}</p><p>Dikirim ${date(row.shipped_date)} dari ${e(row.staging_location)}</p><p>Diretur ${n(row.returned_quantity)} pcs · sisa dapat diretur ${n(row.returnable_quantity)} pcs</p><p>Sumber pack ${e(row.pack_reference)} · ${date(row.packed_date)}</p></article><p>Pick ${e(row.pick_reference)} · reservasi ${e(row.reservation_reference)} · penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.returned_quantity?'<p class="hint">Koreksi semua retur aktif sebelum mengoreksi pengiriman.</p>':''}${row.sale_settlement_id?`<p class="hint">Settlement aktif: ${e(row.sale_settlement_reference)}. Koreksi settlement sebelum mengoreksi pengiriman.</p>`:'<p class="hint">Settlement penjualan belum dicatat.</p>'}${row.reversal?`<article class="material-event"><h3>Pengiriman dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}<div class="actions"><button data-action="marketplace-pack" data-id="${e(row.pack_id)}">Pack asal</button><button data-action="marketplace-shipments" data-id="${e(row.order_id)}">Semua pengiriman</button><button data-action="marketplace-returns" data-id="${e(row.order_id)}">Semua retur</button><button data-action="contribution-margin" data-id="${e(row.order_id)}">Margin kontribusi</button><button data-action="warehouse" data-id="${e(row.order_id)}">Inventori gudang</button>${row.sale_settlement_id?`<button data-action="sale-settlement" data-id="${e(row.sale_settlement_id)}">Settlement ${e(row.sale_settlement_reference)}</button>`:user.role!=='viewer'&&row.status==='shipped'?`<button data-action="new-sale-settlement" data-id="${e(row.id)}">Catat settlement</button>`:''}${user.role!=='viewer'&&row.status==='shipped'&&row.returnable_quantity>0?`<button data-action="new-marketplace-return" data-id="${e(row.id)}">Catat retur</button>`:''}${user.role==='admin'&&row.status==='shipped'&&!row.returned_quantity&&!row.sale_settlement_id?'<button id="reverse-marketplace-shipment">Koreksi pengiriman</button>':''}</div>`;
    if($('reverse-marketplace-shipment'))$('reverse-marketplace-shipment').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi pengiriman',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/marketplace-shipments/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · ${n(row.quantity)} pcs\nKoreksi mengembalikan barang ke packed di ${row.staging_location}. Riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-shipment" data-id="${e(shipmentId)}">Coba lagi</button>`;}
}

async function marketplaceSaleSettlementForm(shipmentId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat settlement penjualan','<p class="state">Memuat pengiriman...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-shipments/'+encodeURIComponent(shipmentId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(row.status!=='shipped'||row.sale_settlement_id){$('dialog-content').innerHTML='<p>Pengiriman ini tidak dapat menerima settlement baru. Muat ulang rinciannya.</p><button data-action="marketplace-shipment" data-id="'+e(shipmentId)+'">Muat ulang pengiriman</button>';return;}
    const moneyField=(name,label,min='0')=>field(name,label,'number',`required min="${min}" max="1000000000000" step="0.01" value="0"`);
    formDialog('Catat settlement penjualan',field('reference','Referensi settlement','text','required maxlength="160"')+
      moneyField('gross_revenue','Omzet kotor','0.01')+moneyField('seller_discount','Diskon penjual')+
      moneyField('customer_refund','Refund pelanggan')+moneyField('marketplace_fee','Fee marketplace')+
      moneyField('shipping_cost','Biaya kirim ditanggung penjual')+moneyField('other_variable_cost','Biaya variabel lain')+
      field('settled_date','Tanggal settlement','date',`required min="${e(row.shipped_date)}"`)+materialReason,
      form=>{const data=Object.fromEntries(new FormData(form));return {reference:data.reference,
        gross_revenue:data.gross_revenue,seller_discount:data.seller_discount,
        customer_refund:data.customer_refund,marketplace_fee:data.marketplace_fee,
        shipping_cost:data.shipping_cost,other_variable_cost:data.other_variable_cost,
        settled_date:data.settled_date,reason:data.reason};},
      '/api/marketplace-shipments/'+encodeURIComponent(row.id)+'/sale-settlements',
      `${row.reference} · ${row.marketplace} · ${row.external_order_reference}\n${n(row.quantity)} pcs dikirim, ${n(row.returned_quantity)} pcs retur saat ini. Retur baru setelah settlement akan ditandai agar settlement dikoreksi.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-sale-settlement" data-id="${e(shipmentId)}">Coba lagi</button>`;}
}

async function marketplaceSaleSettlementDialog(settlementId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian settlement penjualan','<p class="state">Memuat settlement...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-sale-settlements/'+encodeURIComponent(settlementId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Aktif':'Sudah dikoreksi'}</p>
      <p class="status-label ${row.return_coverage_status==='current'?'done':'late'}">${row.return_coverage_status==='current'?'Cakupan retur sesuai':'Ada perubahan retur setelah settlement'}</p>
      <h3>${e(row.marketplace)} · ${e(row.external_order_reference)}</h3><p>${e(row.shipment_reference)} · ${n(row.quantity)} pcs dikirim · ${n(row.returned_quantity)} pcs retur</p>
      <dl class="requirement-values"><div><dt>Omzet kotor</dt><dd>${e(rupiah(row.gross_revenue))}</dd></div><div><dt>Diskon penjual</dt><dd>${e(rupiah(row.seller_discount))}</dd></div><div><dt>Refund pelanggan</dt><dd>${e(rupiah(row.customer_refund))}</dd></div><div><dt>Pendapatan neto</dt><dd>${e(rupiah(row.net_revenue))}</dd></div><div><dt>Fee marketplace</dt><dd>${e(rupiah(row.marketplace_fee))}</dd></div><div><dt>Biaya kirim</dt><dd>${e(rupiah(row.shipping_cost))}</dd></div><div><dt>Biaya variabel lain</dt><dd>${e(rupiah(row.other_variable_cost))}</dd></div><div><dt>Kontribusi sebelum produksi</dt><dd>${e(rupiah(row.contribution_before_production))}</dd></div></dl>
      <p class="hint">Settlement ${date(row.settled_date)} mencakup ${n(row.return_quantity)} pcs retur. Dicatat ${e(row.actor_name)} · ${purchaseStamp(row.created_at)}.</p><p class="reason">${e(row.reason)}</p>
      ${row.reversal?`<article class="material-event"><h3>Settlement dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}
      <div class="actions"><button data-action="marketplace-shipment" data-id="${e(row.shipment_id)}">Pengiriman ${e(row.shipment_reference)}</button><button data-action="contribution-margin" data-id="${e(row.order_id)}">Margin kontribusi</button>${user.role==='admin'&&row.status==='active'?'<button id="reverse-sale-settlement">Koreksi settlement</button>':''}</div>`;
    if($('reverse-sale-settlement'))$('reverse-sale-settlement').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi settlement penjualan',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/marketplace-sale-settlements/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · ${rupiah(row.net_revenue)} pendapatan neto\nRiwayat asli tetap tersimpan. Catat settlement pengganti dari pengiriman setelah koreksi.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="sale-settlement" data-id="${e(settlementId)}">Coba lagi</button>`;}
}

const returnReason={too_small:'Ukuran terlalu kecil',too_big:'Ukuran terlalu besar',wrong_item:'Barang salah',defect:'Cacat',color_mismatch:'Warna tidak sesuai',other:'Lainnya'};
const inspectedStatuses=['sellable','hold','damaged'];

async function marketplaceReturnsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Retur pelanggan','<p class="state">Memuat riwayat retur...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const order=await api.get('/api/orders/'+encodeURIComponent(orderId));
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Retur menambah kembali stok barang jadi sesuai lokasi dan hasil pemeriksaan fisik.</p><button data-action="marketplace-shipments" data-id="${e(orderId)}">Riwayat shipping</button><button data-action="warehouse" data-id="${e(orderId)}">Inventori gudang</button><h3>Riwayat retur</h3><div id="marketplace-return-list"><p class="state">Memuat retur...</p></div><p id="marketplace-return-error" class="error" role="alert" hidden></p><button id="marketplace-return-more" type="button">Muat retur sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('marketplace-return-more');button.disabled=true;message('marketplace-return-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/marketplace-returns?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('marketplace-return-list').replaceChildren();
        appendRows('marketplace-return-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(returnReason[row.return_reason])} · ${e(row.sku)}</p><p>${e(row.return_location)} · ${e(warehouseStatus[row.stock_status])} · ${row.status==='active'?'Aktif':'Sudah dikoreksi'}</p><p>Pengiriman ${e(row.shipment_reference)} · ${date(row.returned_date)}</p><button data-action="marketplace-return" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian retur</button></article>`).join(''));
        if(!before&&!rows.length)$('marketplace-return-list').innerHTML='<p class="state">Belum ada retur pelanggan untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat retur sebelumnya';
      }catch(error){if(current()){message('marketplace-return-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('marketplace-return-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-returns" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function marketplaceReturnForm(shipmentId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat retur pelanggan','<p class="state">Memuat pengiriman...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-shipments/'+encodeURIComponent(shipmentId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(row.status!=='shipped'||row.returnable_quantity<1){$('dialog-content').innerHTML='<p>Pengiriman ini tidak memiliki jumlah yang dapat diretur. Muat ulang rinciannya.</p><button data-action="marketplace-shipment" data-id="'+e(shipmentId)+'">Muat ulang pengiriman</button>';return;}
    const reasons=`<div><label for="return-reason">Alasan retur</label><select id="return-reason" name="return_reason" required>${Object.entries(returnReason).map(([value,label])=>option(value,label)).join('')}</select></div>`;
    const statuses=`<div><label for="return-status">Hasil pemeriksaan</label><select id="return-status" name="stock_status" required>${inspectedStatuses.map(value=>option(value,warehouseStatus[value])).join('')}</select></div>`;
    formDialog('Catat retur pelanggan',field('reference','Referensi retur','text','required maxlength="160"')+
      field('quantity','Jumlah retur','number',`required min="1" max="${row.returnable_quantity}" step="1"`)+reasons+
      field('return_location','Lokasi penerimaan retur','text','required maxlength="160"')+statuses+
      field('returned_date','Tanggal retur diterima','date',`required min="${e(row.shipped_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload=Object.fromEntries(data);payload.quantity=Number(payload.quantity);if(payload.quantity>row.returnable_quantity)throw new Error('Jumlah retur melebihi sisa barang yang dapat diretur.');return payload;},
      '/api/marketplace-shipments/'+encodeURIComponent(row.id)+'/returns',
      `${row.reference} · ${row.marketplace} · ${row.external_order_reference}\nDapat diretur ${n(row.returnable_quantity)} dari ${n(row.quantity)} pcs. Pilih status berdasarkan pemeriksaan fisik saat barang diterima.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-marketplace-return" data-id="${e(shipmentId)}">Coba lagi</button>`;}
}

async function marketplaceReturnDialog(returnId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian retur','<p class="state">Memuat catatan retur...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-returns/'+encodeURIComponent(returnId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(returnReason[row.return_reason])}</h3><p>Diterima ${date(row.returned_date)} di ${e(row.return_location)}</p><p>Hasil pemeriksaan: ${e(warehouseStatus[row.stock_status])}</p><p>Pengiriman ${e(row.shipment_reference)} · ${e(row.carrier)} · resi ${e(row.tracking_number)}</p></article><p>Penerimaan asal ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.reversal?`<article class="material-event"><h3>Retur dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}<div class="actions"><button data-action="marketplace-shipment" data-id="${e(row.shipment_id)}">Pengiriman asal</button><button data-action="marketplace-returns" data-id="${e(row.order_id)}">Semua retur</button><button data-action="warehouse" data-id="${e(row.order_id)}">Inventori gudang</button>${user.role==='admin'&&row.status==='active'?'<button id="reverse-marketplace-return">Koreksi retur</button>':''}</div>`;
    if($('reverse-marketplace-return'))$('reverse-marketplace-return').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi retur',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/marketplace-returns/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · ${n(row.quantity)} pcs\nKoreksi mengeluarkan kembali stok dari ${row.return_location} (${warehouseStatus[row.stock_status]}). Stok yang sudah terikat reservasi harus dilepaskan lebih dulu.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-return" data-id="${e(returnId)}">Coba lagi</button>`;}
}

async function finishedGoodsAdjustmentsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Adjustment barang jadi','<p class="state">Memuat riwayat adjustment...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const order=await api.get('/api/orders/'+encodeURIComponent(orderId));
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Adjustment mencatat selisih stok fisik pada satu penerimaan. Jumlah positif menambah stok; jumlah negatif mengurangi stok yang belum terikat reservasi.</p><button data-action="finished-goods" data-id="${e(orderId)}">Penerimaan barang jadi</button><button data-action="warehouse" data-id="${e(orderId)}">Inventori gudang</button><h3>Riwayat adjustment</h3><div id="finished-goods-adjustment-list"><p class="state">Memuat adjustment...</p></div><p id="finished-goods-adjustment-error" class="error" role="alert" hidden></p><button id="finished-goods-adjustment-more" type="button">Muat adjustment sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('finished-goods-adjustment-more');button.disabled=true;message('finished-goods-adjustment-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/finished-goods-adjustments?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('finished-goods-adjustment-list').replaceChildren();
        appendRows('finished-goods-adjustment-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${row.quantity_delta>0?'+':''}${n(row.quantity_delta)} pcs</h3><p>${e(row.sku)} · ${e(row.location)} · ${e(warehouseStatus[row.stock_status])}</p><p>Penerimaan ${e(row.receipt_reference)} · ${row.status==='active'?'Aktif':'Sudah dikoreksi'} · ${date(row.adjusted_date)}</p>${row.stock_count_id?'<p class="hint">Dibuat otomatis dari stock opname.</p>':''}<button data-action="finished-goods-adjustment" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian adjustment</button></article>`).join(''));
        if(!before&&!rows.length)$('finished-goods-adjustment-list').innerHTML='<p class="state">Belum ada adjustment barang jadi untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat adjustment sebelumnya';
      }catch(error){if(current()){message('finished-goods-adjustment-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('finished-goods-adjustment-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finished-goods-adjustments" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function finishedGoodsAdjustmentForm(receiptId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat adjustment barang jadi','<p class="state">Memuat penerimaan...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/finished-goods-receipts/'+encodeURIComponent(receiptId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(row.status!=='active'){$('dialog-content').innerHTML='<p>Penerimaan ini sudah dikoreksi dan tidak dapat menerima adjustment.</p><button data-action="finished-goods-receipt" data-id="'+e(receiptId)+'">Muat ulang penerimaan</button>';return;}
    const statuses=`<div><label for="adjustment-status">Status stok</label><select id="adjustment-status" name="stock_status" required>${inspectedStatuses.map(value=>option(value,warehouseStatus[value])).join('')}</select></div>`;
    const balances=row.inventory.map(item=>`${item.location} · ${warehouseStatus[item.stock_status]} ${n(item.quantity)} pcs${item.stock_status==='sellable'?` (${n(item.available_quantity)} available)`:''}`).join('\n')||'Belum ada saldo aktif pada penerimaan ini.';
    formDialog('Catat adjustment barang jadi',field('reference','Referensi adjustment','text','required maxlength="160"')+
      field('location','Lokasi stok','text','required maxlength="160"')+statuses+
      field('quantity_delta','Selisih jumlah (pcs)','number','required min="-1000000000" max="1000000000" step="1"')+
      field('adjusted_date','Tanggal adjustment','date',`required min="${e(row.received_date)}"`)+materialReason,
      form=>{const payload=Object.fromEntries(new FormData(form));payload.quantity_delta=Number(payload.quantity_delta);if(payload.quantity_delta===0)throw new Error('Selisih jumlah harus lebih atau kurang dari nol.');return payload;},
      '/api/finished-goods-receipts/'+encodeURIComponent(row.id)+'/adjustments',
      `${row.reference} · ${row.sku}\nSaldo penerimaan saat ini:\n${balances}\nGunakan angka positif untuk menambah dan angka negatif untuk mengurangi stok.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-finished-goods-adjustment" data-id="${e(receiptId)}">Coba lagi</button>`;}
}

async function finishedGoodsAdjustmentDialog(adjustmentId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian adjustment','<p class="state">Memuat catatan adjustment...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/finished-goods-adjustments/'+encodeURIComponent(adjustmentId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${row.quantity_delta>0?'+':''}${n(row.quantity_delta)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(row.location)} · ${e(warehouseStatus[row.stock_status])}</h3><p>Tanggal adjustment ${date(row.adjusted_date)}</p><p>Penerimaan ${e(row.receipt_reference)} · diterima ${date(row.received_date)}</p></article><p>Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.reversal?`<article class="material-event"><h3>Adjustment dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}<div class="actions"><button data-action="finished-goods-receipt" data-id="${e(row.receipt_id)}">Penerimaan asal</button><button data-action="finished-goods-adjustments" data-id="${e(row.order_id)}">Semua adjustment</button>${row.stock_count_id?`<button data-action="finished-goods-stock-count" data-id="${e(row.stock_count_id)}">Stock opname asal</button>`:''}<button data-action="warehouse" data-id="${e(row.order_id)}">Inventori gudang</button>${user.role==='admin'&&row.status==='active'&&!row.stock_count_id?'<button id="reverse-finished-goods-adjustment">Koreksi adjustment</button>':''}</div>`;
    if($('reverse-finished-goods-adjustment'))$('reverse-finished-goods-adjustment').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi adjustment',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/finished-goods-adjustments/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · ${row.quantity_delta>0?'+':''}${n(row.quantity_delta)} pcs\nKoreksi membalik selisih pada ${row.location} (${warehouseStatus[row.stock_status]}). Stok yang sudah terikat reservasi harus dilepaskan lebih dulu.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finished-goods-adjustment" data-id="${e(adjustmentId)}">Coba lagi</button>`;}
}

async function finishedGoodsStockCountsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Stock opname barang jadi','<p class="state">Memuat riwayat stock opname...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const order=await api.get('/api/orders/'+encodeURIComponent(orderId));
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Saldo sistem diambil saat pencatatan. Selisih fisik otomatis menjadi adjustment yang tetap terhubung ke stock opname.</p><div class="actions"><button data-action="finished-goods" data-id="${e(orderId)}">Penerimaan barang jadi</button><button data-action="warehouse" data-id="${e(orderId)}">Inventori gudang</button><button data-action="finished-goods-adjustments" data-id="${e(orderId)}">Riwayat adjustment</button></div><h3>Riwayat stock opname</h3><div id="finished-goods-stock-count-list"><p class="state">Memuat stock opname...</p></div><p id="finished-goods-stock-count-error" class="error" role="alert" hidden></p><button id="finished-goods-stock-count-more" type="button">Muat stock opname sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('finished-goods-stock-count-more');button.disabled=true;message('finished-goods-stock-count-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/finished-goods-stock-counts?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('finished-goods-stock-count-list').replaceChildren();
        appendRows('finished-goods-stock-count-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${e(row.sku)}</h3><p>${e(row.location)} · ${e(warehouseStatus[row.stock_status])}</p><p>Saldo sistem ${n(row.expected_quantity)} → fisik ${n(row.counted_quantity)} pcs · selisih ${row.quantity_delta>0?'+':''}${n(row.quantity_delta)}</p><p>${row.status==='active'?'Aktif':'Sudah dikoreksi'} · ${date(row.counted_date)}</p><button data-action="finished-goods-stock-count" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian stock opname</button></article>`).join(''));
        if(!before&&!rows.length)$('finished-goods-stock-count-list').innerHTML='<p class="state">Belum ada stock opname barang jadi untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat stock opname sebelumnya';
      }catch(error){if(current()){message('finished-goods-stock-count-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
      finally{if(current())button.disabled=false;}
    };
    $('finished-goods-stock-count-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finished-goods-stock-counts" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function finishedGoodsStockCountForm(receiptId) {
  if(guardPending())return;
  const version=epoch;openDialog('Catat stock opname barang jadi','<p class="state">Memuat penerimaan...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/finished-goods-receipts/'+encodeURIComponent(receiptId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(row.status!=='active'){$('dialog-content').innerHTML='<p>Penerimaan ini sudah dikoreksi dan tidak dapat dihitung.</p><button data-action="finished-goods-receipt" data-id="'+e(receiptId)+'">Muat ulang penerimaan</button>';return;}
    const statuses=`<div><label for="stock-count-status">Status stok</label><select id="stock-count-status" name="stock_status" required>${inspectedStatuses.map(value=>option(value,warehouseStatus[value])).join('')}</select></div>`;
    const balances=row.inventory.map(item=>`${item.location} · ${warehouseStatus[item.stock_status]}: ${n(item.quantity)} pcs${item.stock_status==='sellable'?` (${n(item.reserved_quantity)} reserved, ${n(item.available_quantity)} available)`:''}`).join('\n')||'Belum ada saldo aktif pada penerimaan ini. Lokasi baru akan memakai saldo sistem 0.';
    formDialog('Catat stock opname barang jadi',field('reference','Referensi stock opname','text','required maxlength="160"')+
      field('scanned_sku','SKU / barcode','text',`required maxlength="160" value="${e(row.sku)}"`)+
      field('location','Lokasi stok','text','required maxlength="160"')+statuses+
      field('counted_quantity','Jumlah fisik (pcs)','number','required min="0" max="1000000000" step="1"')+
      field('counted_date','Tanggal stock opname','date',`required min="${e(row.received_date)}"`)+materialReason,
      form=>{const payload=Object.fromEntries(new FormData(form));payload.counted_quantity=Number(payload.counted_quantity);return payload;},
      '/api/finished-goods-receipts/'+encodeURIComponent(row.id)+'/stock-counts',
      `${row.reference} · ${row.sku}\nSaldo per penerimaan saat ini:\n${balances}\nHitung satu lokasi dan status stok pada satu pencatatan. Jumlah fisik sellable tidak boleh lebih kecil dari stok yang masih reserved.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-finished-goods-stock-count" data-id="${e(receiptId)}">Coba lagi</button>`;}
}

async function finishedGoodsStockCountDialog(countId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian stock opname','<p class="state">Memuat catatan stock opname...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/finished-goods-stock-counts/'+encodeURIComponent(countId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(row.location)} · ${e(warehouseStatus[row.stock_status])}</h3><p>Saldo sistem ${n(row.expected_quantity)} pcs · fisik ${n(row.counted_quantity)} pcs</p><p>Selisih ${row.quantity_delta>0?'+':''}${n(row.quantity_delta)} pcs · dihitung ${date(row.counted_date)}</p></article><p>Penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.adjustment_id?'<p class="hint">Selisih dibuat sebagai adjustment barang jadi yang terhubung.</p>':'<p class="hint">Jumlah fisik sama dengan saldo sistem; tidak ada adjustment stok.</p>'}${row.reversal?`<article class="material-event"><h3>Stock opname dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}<div class="actions"><button data-action="finished-goods-receipt" data-id="${e(row.receipt_id)}">Penerimaan asal</button><button data-action="finished-goods-stock-counts" data-id="${e(row.order_id)}">Semua stock opname</button>${row.adjustment_id?`<button data-action="finished-goods-adjustment" data-id="${e(row.adjustment_id)}">Adjustment selisih</button>`:''}<button data-action="warehouse" data-id="${e(row.order_id)}">Inventori gudang</button>${user.role==='admin'&&row.status==='active'?'<button id="reverse-finished-goods-stock-count">Koreksi stock opname</button>':''}</div>`;
    if($('reverse-finished-goods-stock-count'))$('reverse-finished-goods-stock-count').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi stock opname',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/finished-goods-stock-counts/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · selisih ${row.quantity_delta>0?'+':''}${n(row.quantity_delta)} pcs\nKoreksi membalik adjustment yang terhubung dan mempertahankan riwayat hitung. Stok hasil penambahan yang sudah terikat reservasi harus dilepaskan lebih dulu.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finished-goods-stock-count" data-id="${e(countId)}">Coba lagi</button>`;}
}

async function consumptionForm(issueId) {
  if(guardPending())return;
  const version=epoch,order=selected;
  openDialog('Catat pemakaian & waste','<p class="state">Memuat sisa pengeluaran…</p>');const modal=dialogVersion;
  try{
    const rows=await allRows(`/api/orders/${encodeURIComponent(order.id)}/material-consumption`);
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const issue=rows.find(r=>r.issue_id===issueId);
    if(!issue || issue.reversed_by || issue.unreported==='0.000'){$('dialog-content').innerHTML='<p>Pengeluaran tidak lagi memiliki jumlah yang dapat dilaporkan. Tutup dialog dan muat ulang pemakaian order.</p>';return;}
    const step=issue.unit==='pcs'?'1':'0.001';
    formDialog('Catat pemakaian & waste',field('used','Terpakai untuk produksi','number',`required min="0" max="${e(issue.unreported)}" step="${step}" value="0"`)+
      field('waste','Waste tidak layak pakai','number',`required min="0" max="${e(issue.unreported)}" step="${step}" value="0"`)+materialReason,
      form=>({...Object.fromEntries(new FormData(form)),issue_id:issue.issue_id}),'/api/material-consumption',
      `${order.reference} · ${issue.batch_reference} · ${issue.code}\nPengeluaran ${issue.issue_id}\nBelum dilaporkan: ${materialQty(issue.unreported,issue.unit)}. Terpakai + waste tidak boleh melampaui jumlah ini. Isi sesuai satuan ${issue.unit}. Waste berarti sisa tidak layak pakai; sisa yang masih bisa dipakai tidak dicatat sebagai waste. Stok rak tidak dipotong lagi dan pcs produksi tidak berubah.`);
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="record-consumption" data-id="${e(issueId)}">Coba lagi</button>`;}
}
async function consumptionDialog() {
  if(guardPending())return;
  const version=epoch,order=selected;
  openDialog('Pemakaian & waste order','<p class="state">Memuat pemakaian bahan…</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  const stamp=value=>new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(value));
  try{
    const issues=await allRows(`/api/orders/${encodeURIComponent(order.id)}/material-consumption`);
    if(!current())return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Pemakaian dicatat per pengeluaran bahan. Terpakai adalah bahan untuk produksi; waste adalah bahan tidak layak pakai. Belum dilaporkan berarti belum ada pencatatan, bukan hasil pengecekan sisa fisik. Pencatatan ini tidak memotong stok rak atau mengubah pcs/tahap produksi.</p><div id="consumption-issues">${issues.length?issues.map(i=>`<article class="material-event"><h3>${e(i.batch_reference)} · ${e(i.code)}</h3><p class="hint">Pengeluaran ${e(i.issue_id)} · ${stamp(i.created_at)}</p>${i.reversed_by?'<p class="status-label">Pengeluaran sudah dibalik</p>':''}<dl class="requirement-values">${[['Dikeluarkan awal','issued'],['Terpakai','used'],['Waste','waste'],['Belum dilaporkan','unreported']].map(([label,key])=>`<div><dt>${label}</dt><dd>${e(materialQty(i[key],i.unit))}</dd></div>`).join('')}</dl>${user.role!=='viewer' && !i.reversed_by && i.unreported!=='0.000'?`<button data-action="record-consumption" data-id="${e(i.issue_id)}">Catat pemakaian</button>`:''}</article>`).join(''):'<p class="state">Belum ada pengeluaran bahan untuk dicatat pemakaiannya.</p>'}</div><h3>Riwayat pemakaian & waste</h3><div id="consumption-history"></div><p id="consumption-error" class="error" role="alert" hidden></p><button id="consumption-more" type="button">Muat riwayat pemakaian</button>`;
    let before=null,history=[];
    const load=async()=>{
      const button=$('consumption-more');button.disabled=true;message('consumption-error','');
      try{
        const rows=await api.get(`/api/orders/${encodeURIComponent(order.id)}/consumption-history?`+new URLSearchParams({limit:100,...(before?{before}:{})}));
        if(!current())return;
        history.push(...rows);
        appendRows('consumption-history',rows.map(r=>`<article class="material-event"><strong>${r.reversal_of?'Pembalikan pemakaian':'Pemakaian dicatat'}</strong><p>${e(r.batch_reference)} · ${e(r.code)}</p><p>Terpakai ${e(materialQty(r.used,r.unit))} · waste ${e(materialQty(r.waste,r.unit))}</p><p class="reason">${e(r.reason)}</p><p class="hint">${e(r.actor_name)} · ${stamp(r.created_at)}${r.reversed_by?' · Sudah dibalik':''}</p><p class="hint">Pengeluaran ${e(r.issue_id)}</p>${r.cutting_run_id?`<button data-action="cutting-run" data-id="${e(r.cutting_run_id)}">Hasil cutting</button>`:''}${user.role==='admin' && !r.reversal_of && !r.reversed_by && !r.cutting_run_id?`<button data-consumption-reverse="${e(r.id)}">Koreksi pemakaian</button>`:''}</article>`).join(''));
        before=rows.at(-1)?.sequence;button.hidden=rows.length<100;button.textContent='Muat pemakaian sebelumnya';
      }catch(error){if(current())message('consumption-error',error.message,true);}finally{if(current())button.disabled=false;}
    };
    $('consumption-more').onclick=load;
    $('consumption-history').onclick=event=>{
      const button=event.target.closest('[data-consumption-reverse]');if(!button || guardPending())return;
      const record=history.find(r=>r.id===button.dataset.consumptionReverse);
      formDialog('Koreksi pemakaian & waste',materialReason,form=>Object.fromEntries(new FormData(form)),`/api/material-consumption/${encodeURIComponent(record.id)}/reverse`,
        `${record.batch_reference} · terpakai ${materialQty(record.used,record.unit)} · waste ${materialQty(record.waste,record.unit)}\nPembalikan membatalkan seluruh jumlah pada catatan ini. Stok rak tidak berubah. Setelah koreksi, catat kembali angka yang benar bila diperlukan.`);
    };
    await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="consumption">Coba lagi</button>`;}
}

async function productionCostDialog() {
  if(guardPending())return;
  const version=epoch,order=selected;
  openDialog('Biaya produksi aktual','<p class="state">Menghitung biaya dari ledger…</p>');const modal=dialogVersion;
  try{
    const cost=await api.get('/api/orders/'+encodeURIComponent(order.id)+'/production-cost');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const gap=row=>row.kind==='no_material_consumption'
      ?'<p>Belum ada pemakaian bahan yang tercatat.</p>'
      :row.kind==='unpriced_consumption'
        ?`<p>Batch ${e(row.batch_reference)} · ${e(row.code)}: ${e(materialQty(row.quantity,row.unit))} terpakai tanpa harga PO.</p>`
        :`<p>Batch ${e(row.batch_reference)} · ${e(row.code)}: ${e(materialQty(row.quantity,row.unit))} pengeluaran belum dilaporkan sebagai terpakai atau waste.</p>`;
    $('dialog-content').innerHTML=`<p class="form-info">${e(cost.order_reference)} · ${e(cost.order_title)}</p>
      <p class="status-label ${cost.status==='complete'?'done':'late'}">${cost.status==='complete'?'Cakupan sumber biaya lengkap':'Cakupan biaya belum lengkap'}</p>
      <dl class="requirement-values"><div><dt>Biaya bahan</dt><dd>${e(rupiah(cost.material_cost))}</dd></div><div><dt>Sewing / makloon</dt><dd>${e(rupiah(cost.sewing_cost))}</dd></div><div><dt>Biaya tercatat</dt><dd>${e(rupiah(cost.known_cost))}</dd></div><div><dt>Total biaya</dt><dd>${cost.total_cost?e(rupiah(cost.total_cost)):'Belum tersedia'}</dd></div><div><dt>Per target pcs</dt><dd>${cost.cost_per_target_unit?e(rupiah(cost.cost_per_target_unit)):'Belum tersedia'}</dd></div><div><dt>Per barang jadi</dt><dd>${cost.cost_per_finished_unit?e(rupiah(cost.cost_per_finished_unit)):'Belum tersedia'}</dd></div></dl>
      <p class="hint">Target ${n(cost.target_quantity)} pcs · barang jadi diterima ${n(cost.finished_quantity)} pcs. Total hanya ditampilkan saat seluruh pemakaian mempunyai harga dan semua pengeluaran sudah dilaporkan.</p>
      ${cost.coverage_gaps.length?`<article class="material-event"><h3>Data biaya yang perlu dilengkapi</h3>${cost.coverage_gaps.map(gap).join('')}</article>`:''}
      <h3>Biaya bahan aktual</h3>${cost.materials.map(row=>`<article class="material-event"><h4>${e(row.code)} · ${e(row.name)}</h4><p>Batch ${e(row.batch_reference)} · dikeluarkan ${e(materialQty(row.issued,row.unit))}</p><p>Terpakai ${e(materialQty(row.used,row.unit))} · waste ${e(materialQty(row.waste,row.unit))} · belum dilaporkan ${e(materialQty(row.unreported,row.unit))}</p><p>${row.unit_price?`Harga PO ${e(rupiah(row.unit_price))}/${e(row.unit)} · biaya ${e(rupiah(row.cost))}`:'Harga PO belum tersedia'}</p><div class="actions"><button data-action="material-batch" data-id="${e(row.batch_id)}">Batch ${e(row.batch_reference)}</button>${row.purchase_order_id?`<button data-action="purchase-order" data-id="${e(row.purchase_order_id)}">PO ${e(row.purchase_order_reference)}</button>`:''}</div></article>`).join('')||'<p>Belum ada pengeluaran bahan aktif.</p>'}
      <h3>Biaya sewing / makloon</h3>${cost.sewing_jobs.map(job=>`<article class="material-event"><h4>${e(job.reference)} · ${e(job.assignment_type==='makloon'?'Makloon':'Internal')}</h4><p>${e(job.assignee)} · ${n(job.quantity_out)} pcs · ${e(rupiah(job.cost))}</p><p class="hint">${job.status==='completed'?'Hasil sudah diterima':'Pekerjaan masih terbuka'} · dikirim ${date(job.sent_date)}</p><button data-action="sewing-job" data-id="${e(job.id)}">Job ${e(job.reference)}</button></article>`).join('')||'<p>Belum ada biaya sewing atau makloon aktif.</p>'}
      <p class="hint">Cakupan saat ini hanya pemakaian bahan dan biaya job sewing/makloon. Tenaga kerja internal, finishing, QC, kemasan, freight, dan overhead belum mempunyai ledger biaya.</p>`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="production-cost">Coba lagi</button>`;}
}

async function contributionMarginDialog(orderId) {
  if(guardPending())return;
  const version=epoch;
  openDialog('Margin kontribusi','<p class="state">Menghitung margin dari settlement dan biaya produksi...</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/contribution-margin');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const gap=row=>row.kind==='no_sales_shipments'?'<p>Belum ada pengiriman marketplace aktif.</p>'
      :row.kind==='missing_sales_settlement'?`<p>Pengiriman ${e(row.shipment_reference)} belum memiliki settlement penjualan.</p>`
      :row.kind==='stale_return_coverage'?`<p>Pengiriman ${e(row.shipment_reference)}: settlement mencakup ${n(row.recorded_return_quantity)} pcs retur, sementara retur aktif sekarang ${n(row.current_return_quantity)} pcs.</p>`
      :row.kind==='no_finished_quantity'?'<p>Belum ada barang jadi yang diterima untuk dasar alokasi biaya.</p>'
      :'<p>Biaya produksi belum lengkap. Lengkapi harga dan laporan pemakaian bahan terlebih dahulu.</p>';
    $('dialog-content').innerHTML=`<p class="form-info">${e(report.order_reference)} · ${e(report.order_title)}</p>
      <p class="status-label ${report.status==='complete'?'done':'late'}">${report.status==='complete'?'Cakupan margin lengkap':'Cakupan margin belum lengkap'}</p>
      <dl class="requirement-values"><div><dt>Omzet kotor</dt><dd>${e(rupiah(report.gross_revenue))}</dd></div><div><dt>Pendapatan neto</dt><dd>${e(rupiah(report.net_revenue))}</dd></div><div><dt>Biaya jual variabel</dt><dd>${e(rupiah(report.variable_selling_cost))}</dd></div><div><dt>Kontribusi sebelum produksi</dt><dd>${e(rupiah(report.contribution_before_production))}</dd></div><div><dt>Biaya produksi teralokasi</dt><dd>${report.allocated_production_cost?e(rupiah(report.allocated_production_cost)):'Belum tersedia'}</dd></div><div><dt>Margin kontribusi</dt><dd>${report.contribution_margin!==null?e(rupiah(report.contribution_margin)):'Belum tersedia'}</dd></div><div><dt>Rasio margin</dt><dd>${report.contribution_margin_rate!==null?e(report.contribution_margin_rate)+'%':'Belum tersedia'}</dd></div></dl>
      <p class="hint">Barang jadi ${n(report.finished_quantity)} pcs · dikirim ${n(report.shipped_quantity)} pcs · retur ${n(report.returned_quantity)} pcs · terjual neto ${n(report.net_sold_quantity)} pcs. Biaya produksi dialokasikan proporsional terhadap unit terjual neto.</p>
      ${report.coverage_gaps.length?`<article class="material-event"><h3>Data margin yang perlu dilengkapi</h3>${report.coverage_gaps.map(gap).join('')}</article>`:''}
      <h3>Rincian pengiriman dan settlement</h3>${report.shipments.map(row=>`<article class="material-event"><h4>${e(row.reference)} · ${n(row.net_sold_quantity)} pcs terjual neto</h4><p>${e(row.marketplace)} · ${e(row.external_order_reference)} · dikirim ${n(row.quantity)} · retur ${n(row.returned_quantity)}</p>${row.settlement?`<p>Settlement ${e(row.settlement.reference)} · pendapatan neto ${e(rupiah(row.settlement.net_revenue))} · biaya jual ${e(rupiah(row.settlement.variable_selling_cost))}</p><button data-action="sale-settlement" data-id="${e(row.settlement.id)}">Rincian settlement</button>`:`<p class="hint">Settlement belum dicatat.</p>${user.role!=='viewer'?`<button data-action="new-sale-settlement" data-id="${e(row.id)}">Catat settlement</button>`:''}`}</article>`).join('')||'<p class="state">Belum ada pengiriman aktif.</p>'}
      <div class="actions"><button data-action="production-cost" data-id="${e(report.order_id)}">Biaya produksi</button><button data-action="marketplace-shipments" data-id="${e(report.order_id)}">Riwayat shipping</button></div>
      <p class="hint">Cakupan biaya jual: diskon penjual, refund pelanggan, fee marketplace, biaya kirim penjual, dan biaya variabel lain. Pajak, payment gateway terpisah, iklan, overhead tetap, penanganan retur, dan write-off stok belum dihitung.</p>`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="contribution-margin" data-id="${e(orderId)}">Coba lagi</button>`;}
}

const integrationHealth={healthy:'Sehat',failed:'Gagal',stale:'Stale',never_synced:'Belum pernah sync',incomplete:'Belum lengkap'};

function showIntegrations() {
  if (guardPending()) return;
  activateWorkspace('integrations');
  loadIntegrations();
}
// Milestone D: kesehatan integrasi, source of truth, dan run terbaru hidup di halaman.
// Rincian run dan rekonsiliasi tetap dialog terfokus.
async function loadIntegrations() {
  const version=epoch,request=++integrationsRequest;
  const current=()=>version===epoch&&request===integrationsRequest&&view==='integrations';
  message('integrations-message','Memuat kontrak dan status sinkronisasi…');
  $('integrations-body').replaceChildren();
  try{
    const report=await api.get('/api/integrations');
    if(!current())return;
    const age=value=>value===null?'Belum ada run':value<60?`${n(value)} menit lalu`:`${n(Math.floor(value/60))} jam lalu`;
    message('integrations-message','');
    $('integrations-body').innerHTML=`<p class="hint">Status berasal dari ledger run aktual. Scope tanpa catatan tetap ditandai belum pernah sync; sistem tidak menganggap koneksi vendor aktif hanya karena kontraknya tersedia.</p><p class="form-info">Batas stale ${n(report.stale_after_minutes/60)} jam · diperiksa ${purchaseStamp(report.generated_at)}</p>${report.systems.map(system=>`<section class="material-event" data-integration-system="${e(system.system)}"><p class="status-label ${system.health==='healthy'?'done':'late'}">${e(integrationHealth[system.health])}</p><h3>${e(system.label)}</h3>${system.product_mapping?`<p>Mapping SKU: ${n(system.product_mapping.mapped_products)} dari ${n(system.product_mapping.total_products)} terhubung · ${n(system.product_mapping.unmapped_products)} belum dipetakan.</p><div class="actions"><button data-action="products">Buka Master SKU</button><button data-action="jubelio-order-summary">Order & penjualan Jubelio</button><button data-action="jubelio-return-summary">Retur Jubelio</button><button data-action="jubelio-listing-summary">Listing Jubelio</button><button data-action="jubelio-stock-reconciliation">Rekonsiliasi stok Jubelio</button></div>`:''}${system.system==='mekari'?'<div class="actions"><button data-action="mekari-finance-summary">Keuangan Mekari</button><button data-action="mekari-payables-summary">Utang Mekari</button><button data-action="mekari-receivables-summary">Piutang Mekari</button><button data-action="mekari-payroll-summary">Payroll Mekari</button><button data-action="payroll-payment-reconciliation">Pembayaran payroll</button><button data-action="payroll-accounting-reconciliation">Akuntansi payroll</button></div>':''}<p>${n(system.attention_count)} dari ${n(system.scopes.length)} scope perlu perhatian.</p>${system.scopes.map(scope=>`<article class="material-event" data-integration-scope="${e(scope.scope)}"><p class="status-label ${scope.health==='healthy'?'done':'late'}">${e(integrationHealth[scope.health])}</p><h4>${e(scope.domain)}</h4><p>Source of truth: ${e(scope.source_of_truth)} · inbound read-only</p><p class="hint">${e(age(scope.age_minutes))}${scope.latest_run?` · dibaca ${n(scope.latest_run.records_read)} · ditulis ${n(scope.latest_run.records_written)}`:''}</p>${scope.latest_run?.error?`<p class="error">${e(scope.latest_run.error)}</p>`:''}${scope.latest_run?`<button data-action="integration-run" data-id="${e(scope.latest_run.id)}">Rincian run terbaru</button>`:''}</article>`).join('')}</section>`).join('')}`;
  }catch(error){
    // Pesan dan tombolnya adalah sibling, seperti saat ini menjadi dialog: elemen pesan
    // harus tetap berisi hanya teks statusnya agar status error dapat dicocokkan tepat.
    if(!current())return;
    message('integrations-message','');
    $('integrations-body').innerHTML=`<p class="error">${e(error.message)}</p><button id="integrations-retry" type="button">Coba lagi</button>`;
    $('integrations-retry').onclick=()=>loadIntegrations();
  }
}
$('integrations').onclick=showIntegrations;

async function integrationRunsDialog() {
  if(guardPending())return;
  openDialog('Riwayat sinkronisasi',`<p class="hint">Ledger run dari connector atau worker integrasi. Catatan terbaru ditampilkan lebih dahulu dan tidak dapat diubah.</p><form id="integration-run-filter" class="filter-form"><div class="form-grid"><label>Sistem<select name="system"><option value="all">Semua sistem</option><option value="jubelio">Jubelio</option><option value="mekari">Mekari</option></select></label><label>Status<select name="status"><option value="all">Semua status</option><option value="succeeded">Berhasil</option><option value="failed">Gagal</option></select></label></div><div class="actions"><button type="submit">Terapkan filter</button><button type="button" data-action="integrations">Kesehatan integrasi</button></div></form><p id="integration-run-message" class="state" role="status"></p><div id="integration-run-list"></div><button id="integration-run-more" type="button">Muat run sebelumnya</button>`);
  const version=epoch,modal=dialogVersion,form=$('integration-run-filter'),list=$('integration-run-list'),more=$('integration-run-more');
  let before=null,generation=0;
  const load=async reset=>{
    const request=++generation;
    if(reset){before=null;list.replaceChildren();}
    more.disabled=true;message('integration-run-message','Memuat ledger sinkronisasi…');
    try{
      const values=Object.fromEntries(new FormData(form));
      const query=new URLSearchParams({limit:50,system:values.system,status:values.status});
      if(before)query.set('before',before);
      const rows=await api.get('/api/integration-sync-runs?'+query);
      if(version!==epoch||modal!==dialogVersion||!$('dialog').open||request!==generation)return;
      message('integration-run-message',rows.length?'':list.children.length?'Tidak ada run yang lebih lama.':'Belum ada run sinkronisasi yang cocok.');
      list.insertAdjacentHTML('beforeend',rows.map(row=>`<article class="material-event"><p class="status-label ${row.status==='succeeded'?'done':'late'}">${row.status==='succeeded'?'Berhasil':'Gagal'}</p><h3>${e(row.system==='jubelio'?'Jubelio':'Mekari')} · ${e(row.scope)}</h3><p>Dibaca ${n(row.records_read)} · ditulis ${n(row.records_written)}</p>${row.error?`<p class="error">${e(row.error)}</p>`:''}<p class="hint">Selesai ${purchaseStamp(row.finished_at)} · dicatat ${e(row.actor_name)}</p><button data-action="integration-run" data-id="${e(row.id)}">Buka rincian run</button></article>`).join(''));
      before=rows.at(-1)?.sequence||before;more.hidden=rows.length<50;
    }catch(error){if(version===epoch&&modal===dialogVersion&&request===generation)message('integration-run-message',error.message,true);}
    finally{if(version===epoch&&modal===dialogVersion&&request===generation)more.disabled=false;}
  };
  form.onsubmit=event=>{event.preventDefault();load(true);};more.onclick=()=>load(false);load(true);
}

async function integrationRunDialog(runId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian sinkronisasi','<p class="state">Memuat run sinkronisasi…</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/integration-sync-runs/'+encodeURIComponent(runId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const duration=Math.max(0,Math.round((new Date(row.finished_at)-new Date(row.started_at))/1000));
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.system==='jubelio'?'Jubelio':'Mekari')} · ${e(row.scope)} · ${row.status==='succeeded'?'Berhasil':'Gagal'}</p><dl class="requirement-values"><div><dt>Mulai</dt><dd>${purchaseStamp(row.started_at)}</dd></div><div><dt>Selesai</dt><dd>${purchaseStamp(row.finished_at)}</dd></div><div><dt>Durasi</dt><dd>${n(duration)} detik</dd></div><div><dt>Record dibaca</dt><dd>${n(row.records_read)}</dd></div><div><dt>Record ditulis</dt><dd>${n(row.records_written)}</dd></div></dl>${row.error?`<h3>Error connector</h3><p class="error">${e(row.error)}</p>`:''}<h3>Alasan / konteks</h3><p class="reason">${e(row.reason)}</p><p class="hint">Cursor eksternal: ${e(row.external_cursor||'tidak dicatat')}<br>Dicatat ${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p><div class="actions"><button data-action="integration-runs">Riwayat sinkronisasi</button><button data-action="integrations">Kesehatan integrasi</button></div>`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="integration-run" data-id="${e(runId)}">Coba lagi</button>`;}
}

async function jubelioStockReconciliationDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Rekonsiliasi stok Jubelio','<p class="state">Membandingkan snapshot vendor dan ledger Beeloft…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/integrations/jubelio/finished-goods-reconciliation');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!report.snapshot){$('dialog-content').innerHTML='<p class="state">Belum ada snapshot stok Jubelio. Connector worker harus mengirim snapshot sebelum rekonsiliasi tersedia.</p><div class="actions"><button data-action="jubelio-stock-snapshots">Riwayat snapshot</button><button data-action="integrations">Kesehatan integrasi</button></div>';return;}
    const s=report.summary;
    $('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · ${report.snapshot.sync_status==='succeeded'?'Berhasil':'Ada data dikarantina'}</p><dl class="requirement-values"><div><dt>SKU cocok</dt><dd>${n(s.matched)}</dd></div><div><dt>Selisih stok</dt><dd>${n(s.mismatched)}</dd></div><div><dt>Tidak ada di snapshot</dt><dd>${n(s.missing_from_snapshot)}</dd></div><div><dt>Dikarantina</dt><dd>${n(s.quarantined)}</dd></div></dl><p class="hint">Perbandingan memakai available Jubelio (sellable dikurangi reserved) dan available ledger Beeloft. Snapshot tidak menulis atau menyesuaikan stok Beeloft.</p><div class="actions"><button data-action="jubelio-stock-snapshots">Riwayat snapshot</button><button data-action="integrations">Kesehatan integrasi</button></div><h3>Per SKU terpetakan</h3>${report.items.map(row=>`<article class="material-event"><p class="status-label ${row.status==='matched'?'done':'late'}">${row.status==='matched'?'Cocok':row.status==='mismatched'?'Selisih':'Tidak ada di snapshot'}</p><h4>${e(row.sku)} · ${e(row.product_name)}</h4><p>Beeloft ${n(row.beeloft_available_quantity)} pcs · Jubelio ${row.jubelio_available_quantity===null?'tidak tersedia':n(row.jubelio_available_quantity)+' pcs'}${row.variance_quantity===null?'':` · selisih ${n(row.variance_quantity)} pcs`}</p></article>`).join('')||'<p class="state">Belum ada SKU yang dipetakan.</p>'}<h3>Karantina identifier</h3>${report.quarantine.map(row=>`<article class="material-event"><p class="status-label late">${row.issue==='unmapped'?'Belum dipetakan':'Mapping tidak konsisten'}</p><h4>${e(row.external_sku)} · ${e(row.external_id)}</h4><p>${e(row.detail)}</p></article>`).join('')||'<p class="state">Tidak ada record yang dikarantina.</p>'}`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-stock-reconciliation">Coba lagi</button>`;}
}

async function jubelioStockSnapshotsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat snapshot stok Jubelio','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const rows=await api.get('/api/integrations/jubelio/finished-goods-snapshots?limit=100');if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="hint">Snapshot immutable dari connector worker, terbaru dahulu.</p>${rows.map(row=>`<article class="material-event"><p class="status-label ${row.sync_status==='succeeded'?'done':'late'}">${row.sync_status==='succeeded'?'Berhasil':'Ada karantina'}</p><h3>${purchaseStamp(row.snapshot_at)}</h3><p>Dibaca ${n(row.records_read)} · diterima ${n(row.accepted_count)} · dikarantina ${n(row.rejected_count)}</p><button data-action="jubelio-stock-snapshot" data-id="${e(row.id)}">Rincian snapshot</button></article>`).join('')||'<p class="state">Belum ada snapshot stok Jubelio.</p>'}<button data-action="jubelio-stock-reconciliation">Rekonsiliasi terbaru</button>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-stock-snapshots">Coba lagi</button>`;}
}

async function jubelioStockSnapshotDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian snapshot stok Jubelio','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const row=await api.get('/api/integrations/jubelio/finished-goods-snapshots/'+encodeURIComponent(batchId));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="form-info">${purchaseStamp(row.snapshot_at)} · ${row.sync_status==='succeeded'?'Berhasil':'Ada karantina'}</p><p>Dibaca ${n(row.records_read)} · diterima ${n(row.accepted_count)} · dikarantina ${n(row.rejected_count)}</p>${row.error?`<p class="error">${e(row.error)}</p>`:''}<p class="hint">Cursor ${e(row.external_cursor||'tidak dicatat')} · ${e(row.reason)} · ${e(row.actor_name)}</p><h3>Record diterima</h3>${row.items.map(item=>`<article class="material-event"><h4>${e(item.sku)} ← ${e(item.external_sku)}</h4><p>Sellable ${n(item.sellable_quantity)} · reserved ${n(item.reserved_quantity)} · available ${n(item.sellable_quantity-item.reserved_quantity)}</p></article>`).join('')||'<p class="state">Tidak ada record diterima.</p>'}<h3>Record dikarantina</h3>${row.quarantine.map(item=>`<article class="material-event"><h4>${e(item.external_sku)} · ${e(item.external_id)}</h4><p class="error">${e(item.detail)}</p></article>`).join('')||'<p class="state">Tidak ada record dikarantina.</p>'}<div class="actions"><button data-action="jubelio-stock-snapshots">Riwayat snapshot</button><button data-action="jubelio-stock-reconciliation">Rekonsiliasi terbaru</button></div>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-stock-snapshot" data-id="${e(batchId)}">Coba lagi</button>`;}
}

const jubelioOrderStatus={pending:'Menunggu',processing:'Diproses',completed:'Selesai',cancelled:'Dibatalkan'};
async function jubelioOrderSummaryDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Order & penjualan Jubelio','<p class="state">Memuat snapshot order terbaru…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/integrations/jubelio/order-summary');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!report.snapshot){$('dialog-content').innerHTML='<p class="state">Belum ada snapshot order Jubelio. Connector worker harus mengirim snapshot sebelum ringkasan tersedia.</p><div class="actions"><button data-action="jubelio-order-snapshots">Riwayat snapshot order</button><button data-action="integrations">Kesehatan integrasi</button></div>';return;}
    const s=report.summary;
    $('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · ${report.snapshot.sync_status==='succeeded'?'Berhasil':'Ada order dikarantina'}</p><dl class="requirement-values"><div><dt>Order diterima</dt><dd>${n(s.accepted_orders)}</dd></div><div><dt>Order dikarantina</dt><dd>${n(s.quarantined_orders)}</dd></div><div><dt>Unit selesai</dt><dd>${n(s.units)}</dd></div><div><dt>Penjualan kotor selesai</dt><dd>${rupiah(s.gross_revenue)}</dd></div><div><dt>Menunggu</dt><dd>${n(s.pending)}</dd></div><div><dt>Diproses</dt><dd>${n(s.processing)}</dd></div><div><dt>Selesai</dt><dd>${n(s.completed)}</dd></div><div><dt>Dibatalkan</dt><dd>${n(s.cancelled)}</dd></div></dl><p class="hint">Unit dan penjualan kotor hanya menghitung order berstatus selesai. Snapshot ini read-only dan tidak membuat order produksi, reservasi, shipment, atau settlement Beeloft.</p><div class="actions"><button data-action="jubelio-order-snapshots">Riwayat snapshot order</button><button data-action="integrations">Kesehatan integrasi</button></div><h3>Per marketplace</h3>${report.marketplaces.map(row=>`<article class="material-event"><h4>${e(row.marketplace)}</h4><p>${n(row.orders)} order · ${n(row.units)} unit · ${rupiah(row.gross_revenue)}</p></article>`).join('')||'<p class="state">Tidak ada order diterima.</p>'}<h3>Order diterima</h3>${report.orders.map(order=>`<article class="material-event"><p class="status-label ${order.status==='completed'?'done':order.status==='cancelled'?'':'late'}">${e(jubelioOrderStatus[order.status])}</p><h4>${e(order.external_order_reference)} · ${e(order.marketplace)}</h4><p>${n(order.total_quantity)} unit · ${rupiah(order.gross_revenue)}</p><p class="hint">${purchaseStamp(order.ordered_at)} · ${order.lines.map(line=>e(line.sku)+' × '+n(line.quantity)).join(' · ')}</p></article>`).join('')||'<p class="state">Tidak ada order diterima.</p>'}<h3>Order dikarantina</h3>${report.quarantine.map(order=>`<article class="material-event"><p class="status-label late">${order.issue==='unmapped'?'SKU belum dipetakan':'Mapping tidak konsisten'}</p><h4>${e(order.external_order_reference)} · ${e(order.marketplace)}</h4><p>${e(order.detail)}</p><p class="hint">${order.lines.map(line=>e(line.external_sku)+' × '+n(line.quantity)).join(' · ')}</p></article>`).join('')||'<p class="state">Tidak ada order dikarantina.</p>'}`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-order-summary">Coba lagi</button>`;}
}

async function jubelioOrderSnapshotsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat snapshot order Jubelio','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const rows=await api.get('/api/integrations/jubelio/order-snapshots?limit=100');if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="hint">Snapshot immutable dari connector worker, terbaru dahulu.</p>${rows.map(row=>`<article class="material-event"><p class="status-label ${row.sync_status==='succeeded'?'done':'late'}">${row.sync_status==='succeeded'?'Berhasil':'Ada karantina'}</p><h3>${purchaseStamp(row.snapshot_at)}</h3><p>Dibaca ${n(row.records_read)} · diterima ${n(row.accepted_count)} · dikarantina ${n(row.rejected_count)}</p><button data-action="jubelio-order-snapshot" data-id="${e(row.id)}">Rincian snapshot order</button></article>`).join('')||'<p class="state">Belum ada snapshot order Jubelio.</p>'}<button data-action="jubelio-order-summary">Ringkasan terbaru</button>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-order-snapshots">Coba lagi</button>`;}
}

async function jubelioOrderSnapshotDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian snapshot order Jubelio','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const row=await api.get('/api/integrations/jubelio/order-snapshots/'+encodeURIComponent(batchId));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="form-info">${purchaseStamp(row.snapshot_at)} · ${row.sync_status==='succeeded'?'Berhasil':'Ada karantina'}</p><p>Dibaca ${n(row.records_read)} · diterima ${n(row.accepted_count)} · dikarantina ${n(row.rejected_count)}</p>${row.error?`<p class="error">${e(row.error)}</p>`:''}<p class="hint">Cursor ${e(row.external_cursor||'tidak dicatat')} · ${e(row.reason)} · ${e(row.actor_name)}</p><h3>Order diterima</h3>${row.orders.map(order=>`<article class="material-event"><h4>${e(order.external_order_reference)} · ${e(order.marketplace)}</h4><p>${e(jubelioOrderStatus[order.status])} · ${n(order.total_quantity)} unit · ${rupiah(order.gross_revenue)}</p>${order.lines.map(line=>`<p>${e(line.sku)} ← ${e(line.external_sku)} · ${n(line.quantity)} unit · ${rupiah(line.gross_revenue)}</p>`).join('')}</article>`).join('')||'<p class="state">Tidak ada order diterima.</p>'}<h3>Order dikarantina</h3>${row.quarantine.map(order=>`<article class="material-event"><h4>${e(order.external_order_reference)} · ${e(order.marketplace)}</h4><p class="error">${e(order.detail)}</p><p>${order.lines.map(line=>e(line.external_sku)+' × '+n(line.quantity)).join(' · ')}</p></article>`).join('')||'<p class="state">Tidak ada order dikarantina.</p>'}<div class="actions"><button data-action="jubelio-order-snapshots">Riwayat snapshot order</button><button data-action="jubelio-order-summary">Ringkasan terbaru</button></div>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-order-snapshot" data-id="${e(batchId)}">Coba lagi</button>`;}
}

const jubelioReturnStatus={requested:'Diajukan',in_transit:'Dalam perjalanan',received:'Diterima',refunded:'Refund selesai',rejected:'Ditolak',cancelled:'Dibatalkan'};
async function jubelioReturnSummaryDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Retur Jubelio','<p class="state">Memuat snapshot retur terbaru…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/integrations/jubelio/return-summary');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!report.snapshot){$('dialog-content').innerHTML='<p class="state">Belum ada snapshot retur Jubelio. Connector worker harus mengirim snapshot sebelum ringkasan tersedia.</p><div class="actions"><button data-action="jubelio-return-snapshots">Riwayat snapshot retur</button><button data-action="integrations">Kesehatan integrasi</button></div>';return;}
    const s=report.summary;
    $('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · ${report.snapshot.sync_status==='succeeded'?'Berhasil':'Ada retur dikarantina'}</p><dl class="requirement-values"><div><dt>Retur diterima</dt><dd>${n(s.accepted_returns)}</dd></div><div><dt>Retur dikarantina</dt><dd>${n(s.quarantined_returns)}</dd></div><div><dt>Unit sudah diterima</dt><dd>${n(s.received_units)}</dd></div><div><dt>Refund selesai</dt><dd>${rupiah(s.refunded_amount)}</dd></div><div><dt>Diajukan</dt><dd>${n(s.requested)}</dd></div><div><dt>Dalam perjalanan</dt><dd>${n(s.in_transit)}</dd></div><div><dt>Diterima</dt><dd>${n(s.received)}</dd></div><div><dt>Sudah refund</dt><dd>${n(s.refunded)}</dd></div><div><dt>Ditolak</dt><dd>${n(s.rejected)}</dd></div><div><dt>Dibatalkan</dt><dd>${n(s.cancelled)}</dd></div></dl><p class="hint">Unit diterima hanya menghitung status diterima dan refund selesai. Nilai refund hanya menghitung status refund selesai. Snapshot ini tidak mengubah stok atau retur internal Beeloft.</p><div class="actions"><button data-action="jubelio-return-snapshots">Riwayat snapshot retur</button><button data-action="integrations">Kesehatan integrasi</button></div><h3>Per marketplace</h3>${report.marketplaces.map(row=>`<article class="material-event"><h4>${e(row.marketplace)}</h4><p>${n(row.returns)} retur · ${n(row.received_units)} unit diterima · ${rupiah(row.refunded_amount)}</p></article>`).join('')||'<p class="state">Tidak ada retur diterima.</p>'}<h3>Per SKU diterima</h3>${report.products.map(row=>`<article class="material-event"><h4>${e(row.sku)} · ${e(row.product_name)}</h4><p>${n(row.received_units)} unit diterima</p></article>`).join('')||'<p class="state">Belum ada unit retur diterima.</p>'}<h3>Retur vendor</h3>${report.returns.map(item=>`<article class="material-event"><p class="status-label ${['received','refunded'].includes(item.status)?'done':['rejected','cancelled'].includes(item.status)?'':'late'}">${e(jubelioReturnStatus[item.status])}</p><h4>${e(item.external_return_reference)} · ${e(item.marketplace)}</h4><p>Order ${e(item.external_order_reference)} · ${n(item.total_quantity)} unit · refund ${rupiah(item.refund_amount)}</p><p class="hint">${purchaseStamp(item.updated_at)} · ${item.lines.map(line=>e(line.sku)+' × '+n(line.quantity)).join(' · ')}</p></article>`).join('')||'<p class="state">Tidak ada retur diterima.</p>'}<h3>Retur dikarantina</h3>${report.quarantine.map(item=>`<article class="material-event"><p class="status-label late">${item.issue==='unmapped'?'SKU belum dipetakan':'Mapping tidak konsisten'}</p><h4>${e(item.external_return_reference)} · ${e(item.marketplace)}</h4><p>${e(item.detail)}</p><p class="hint">${item.lines.map(line=>e(line.external_sku)+' × '+n(line.quantity)).join(' · ')}</p></article>`).join('')||'<p class="state">Tidak ada retur dikarantina.</p>'}`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-return-summary">Coba lagi</button>`;}
}

async function jubelioReturnSnapshotsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat snapshot retur Jubelio','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const rows=await api.get('/api/integrations/jubelio/return-snapshots?limit=100');if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="hint">Snapshot immutable dari connector worker, terbaru dahulu.</p>${rows.map(row=>`<article class="material-event"><p class="status-label ${row.sync_status==='succeeded'?'done':'late'}">${row.sync_status==='succeeded'?'Berhasil':'Ada karantina'}</p><h3>${purchaseStamp(row.snapshot_at)}</h3><p>Dibaca ${n(row.records_read)} · diterima ${n(row.accepted_count)} · dikarantina ${n(row.rejected_count)}</p><button data-action="jubelio-return-snapshot" data-id="${e(row.id)}">Rincian snapshot retur</button></article>`).join('')||'<p class="state">Belum ada snapshot retur Jubelio.</p>'}<button data-action="jubelio-return-summary">Ringkasan terbaru</button>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-return-snapshots">Coba lagi</button>`;}
}

async function jubelioReturnSnapshotDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian snapshot retur Jubelio','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const row=await api.get('/api/integrations/jubelio/return-snapshots/'+encodeURIComponent(batchId));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="form-info">${purchaseStamp(row.snapshot_at)} · ${row.sync_status==='succeeded'?'Berhasil':'Ada karantina'}</p><p>Dibaca ${n(row.records_read)} · diterima ${n(row.accepted_count)} · dikarantina ${n(row.rejected_count)}</p>${row.error?`<p class="error">${e(row.error)}</p>`:''}<p class="hint">Cursor ${e(row.external_cursor||'tidak dicatat')} · ${e(row.reason)} · ${e(row.actor_name)}</p><h3>Retur diterima</h3>${row.returns.map(item=>`<article class="material-event"><h4>${e(item.external_return_reference)} · ${e(item.marketplace)}</h4><p>${e(jubelioReturnStatus[item.status])} · order ${e(item.external_order_reference)} · ${n(item.total_quantity)} unit · refund ${rupiah(item.refund_amount)}</p>${item.lines.map(line=>`<p>${e(line.sku)} ← ${e(line.external_sku)} · ${n(line.quantity)} unit</p>`).join('')}</article>`).join('')||'<p class="state">Tidak ada retur diterima.</p>'}<h3>Retur dikarantina</h3>${row.quarantine.map(item=>`<article class="material-event"><h4>${e(item.external_return_reference)} · ${e(item.marketplace)}</h4><p class="error">${e(item.detail)}</p><p>${item.lines.map(line=>e(line.external_sku)+' × '+n(line.quantity)).join(' · ')}</p></article>`).join('')||'<p class="state">Tidak ada retur dikarantina.</p>'}<div class="actions"><button data-action="jubelio-return-snapshots">Riwayat snapshot retur</button><button data-action="jubelio-return-summary">Ringkasan terbaru</button></div>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-return-snapshot" data-id="${e(batchId)}">Coba lagi</button>`;}
}

const jubelioListingStatus={active:'Aktif',inactive:'Nonaktif',draft:'Draft',blocked:'Diblokir'};
async function jubelioListingSummaryDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Listing Jubelio','<p class="state">Memuat snapshot listing terbaru…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/integrations/jubelio/listing-summary');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!report.snapshot){$('dialog-content').innerHTML='<p class="state">Belum ada snapshot listing Jubelio. Connector worker harus mengirim snapshot sebelum ringkasan tersedia.</p><div class="actions"><button data-action="jubelio-listing-snapshots">Riwayat snapshot listing</button><button data-action="integrations">Kesehatan integrasi</button></div>';return;}
    const s=report.summary,price=value=>value===null?'—':rupiah(value);
    $('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · ${report.snapshot.sync_status==='succeeded'?'Berhasil':'Ada listing dikarantina'}</p><dl class="requirement-values"><div><dt>Listing diterima</dt><dd>${n(s.accepted_listings)}</dd></div><div><dt>Listing dikarantina</dt><dd>${n(s.quarantined_listings)}</dd></div><div><dt>Produk aktif</dt><dd>${n(s.active_products)}</dd></div><div><dt>Aktif</dt><dd>${n(s.active)}</dd></div><div><dt>Nonaktif</dt><dd>${n(s.inactive)}</dd></div><div><dt>Draft</dt><dd>${n(s.draft)}</dd></div><div><dt>Diblokir</dt><dd>${n(s.blocked)}</dd></div><div><dt>Harga aktif terendah</dt><dd>${price(s.min_active_price)}</dd></div><div><dt>Harga aktif tertinggi</dt><dd>${price(s.max_active_price)}</dd></div></dl><p class="hint">Snapshot ini hanya membaca listing vendor. Data ini tidak mengubah master produk, harga internal, atau stok Beeloft.</p><div class="actions"><button data-action="jubelio-listing-snapshots">Riwayat snapshot listing</button><button data-action="integrations">Kesehatan integrasi</button></div><h3>Per marketplace</h3>${report.marketplaces.map(row=>`<article class="material-event"><h4>${e(row.marketplace)}</h4><p>${n(row.listings)} listing · ${n(row.active)} aktif · ${n(row.active_products)} produk aktif</p><p class="hint">Nonaktif ${n(row.inactive)} · draft ${n(row.draft)} · diblokir ${n(row.blocked)}</p></article>`).join('')||'<p class="state">Tidak ada listing diterima.</p>'}<h3>Listing vendor</h3>${report.listings.map(item=>`<article class="material-event"><p class="status-label ${item.status==='active'?'done':item.status==='blocked'?'late':''}">${e(jubelioListingStatus[item.status])}</p><h4>${e(item.listing_reference)} · ${e(item.marketplace)}</h4><p>${e(item.listing_title)} · ${rupiah(item.listed_price)}</p><p class="hint">${e(item.sku)} ← ${e(item.external_sku)} · ${purchaseStamp(item.updated_at)}</p></article>`).join('')||'<p class="state">Tidak ada listing diterima.</p>'}<h3>Listing dikarantina</h3>${report.quarantine.map(item=>`<article class="material-event"><p class="status-label late">${item.issue==='unmapped'?'SKU belum dipetakan':'Mapping tidak konsisten'}</p><h4>${e(item.listing_reference)} · ${e(item.marketplace)}</h4><p>${e(item.detail)}</p><p class="hint">${e(item.external_sku)} · ${e(item.listing_title)}</p></article>`).join('')||'<p class="state">Tidak ada listing dikarantina.</p>'}`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-listing-summary">Coba lagi</button>`;}
}

async function jubelioListingSnapshotsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat snapshot listing Jubelio','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const rows=await api.get('/api/integrations/jubelio/listing-snapshots?limit=100');if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="hint">Snapshot immutable dari connector worker, terbaru dahulu.</p>${rows.map(row=>`<article class="material-event"><p class="status-label ${row.sync_status==='succeeded'?'done':'late'}">${row.sync_status==='succeeded'?'Berhasil':'Ada karantina'}</p><h3>${purchaseStamp(row.snapshot_at)}</h3><p>Dibaca ${n(row.records_read)} · diterima ${n(row.accepted_count)} · dikarantina ${n(row.rejected_count)}</p><button data-action="jubelio-listing-snapshot" data-id="${e(row.id)}">Rincian snapshot listing</button></article>`).join('')||'<p class="state">Belum ada snapshot listing Jubelio.</p>'}<button data-action="jubelio-listing-summary">Ringkasan terbaru</button>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-listing-snapshots">Coba lagi</button>`;}
}

async function jubelioListingSnapshotDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian snapshot listing Jubelio','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const row=await api.get('/api/integrations/jubelio/listing-snapshots/'+encodeURIComponent(batchId));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="form-info">${purchaseStamp(row.snapshot_at)} · ${row.sync_status==='succeeded'?'Berhasil':'Ada karantina'}</p><p>Dibaca ${n(row.records_read)} · diterima ${n(row.accepted_count)} · dikarantina ${n(row.rejected_count)}</p>${row.error?`<p class="error">${e(row.error)}</p>`:''}<p class="hint">Cursor ${e(row.external_cursor||'tidak dicatat')} · ${e(row.reason)} · ${e(row.actor_name)}</p><h3>Listing diterima</h3>${row.listings.map(item=>`<article class="material-event"><h4>${e(item.listing_reference)} · ${e(item.marketplace)}</h4><p>${e(jubelioListingStatus[item.status])} · ${e(item.listing_title)} · ${rupiah(item.listed_price)}</p><p>${e(item.sku)} ← ${e(item.external_sku)}</p></article>`).join('')||'<p class="state">Tidak ada listing diterima.</p>'}<h3>Listing dikarantina</h3>${row.quarantine.map(item=>`<article class="material-event"><h4>${e(item.listing_reference)} · ${e(item.marketplace)}</h4><p class="error">${e(item.detail)}</p><p>${e(item.external_sku)} · ${e(item.listing_title)}</p></article>`).join('')||'<p class="state">Tidak ada listing dikarantina.</p>'}<div class="actions"><button data-action="jubelio-listing-snapshots">Riwayat snapshot listing</button><button data-action="jubelio-listing-summary">Ringkasan terbaru</button></div>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="jubelio-listing-snapshot" data-id="${e(batchId)}">Coba lagi</button>`;}
}

const financeRupiah=value=>value.startsWith('-')?'-'+rupiah(value.slice(1)):rupiah(value);
const financePeriodCard=period=>`<article class="material-event"><p class="eyebrow">${date(period.period_start)}–${date(period.period_end)} · ${e(period.currency)}</p><h3>${e(period.source_report_id)}</h3><dl class="requirement-values"><div><dt>Pendapatan bersih</dt><dd>${financeRupiah(period.net_revenue)}</dd></div><div><dt>Laba kotor</dt><dd>${financeRupiah(period.gross_profit)}</dd></div><div><dt>Laba bersih</dt><dd>${financeRupiah(period.net_profit)}</dd></div><div><dt>Kas</dt><dd>${financeRupiah(period.cash_balance)}</dd></div><div><dt>Piutang</dt><dd>${financeRupiah(period.receivables_balance)}</dd></div><div><dt>Utang</dt><dd>${financeRupiah(period.payables_balance)}</dd></div><div><dt>Posisi likuiditas</dt><dd>${financeRupiah(period.net_liquidity)}</dd></div></dl></article>`;

async function mekariFinanceSummaryDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Keuangan Mekari','<p class="state">Memuat snapshot keuangan terbaru…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/integrations/mekari/finance-summary');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!report.snapshot){$('dialog-content').innerHTML='<p class="state">Belum ada snapshot keuangan Mekari. Connector worker harus mengirim snapshot sebelum ringkasan tersedia.</p><div class="actions"><button data-action="mekari-finance-snapshots">Riwayat snapshot keuangan</button><button data-action="integrations">Kesehatan integrasi</button></div>';return;}
    if(!report.current){$('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · tidak memuat periode laporan</p><p class="state">Connector menyelesaikan snapshot kosong. Periksa sumber laporan Mekari sebelum memakai ringkasan ini.</p><div class="actions"><button data-action="mekari-finance-snapshots">Riwayat snapshot keuangan</button><button data-action="integrations">Kesehatan integrasi</button></div>`;return;}
    const current=report.current;
    $('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · periode terbaru ${date(current.period_start)}–${date(current.period_end)}</p><dl class="requirement-values"><div><dt>Pendapatan kotor</dt><dd>${financeRupiah(current.gross_revenue)}</dd></div><div><dt>Retur penjualan</dt><dd>${financeRupiah(current.sales_returns)}</dd></div><div><dt>Pendapatan bersih</dt><dd>${financeRupiah(current.net_revenue)}</dd></div><div><dt>Harga pokok</dt><dd>${financeRupiah(current.cost_of_goods_sold)}</dd></div><div><dt>Laba kotor</dt><dd>${financeRupiah(current.gross_profit)}</dd></div><div><dt>Beban operasional</dt><dd>${financeRupiah(current.operating_expenses)}</dd></div><div><dt>Pendapatan lain</dt><dd>${financeRupiah(current.other_income)}</dd></div><div><dt>Beban lain</dt><dd>${financeRupiah(current.other_expenses)}</dd></div><div><dt>Laba bersih</dt><dd>${financeRupiah(current.net_profit)}</dd></div><div><dt>Kas</dt><dd>${financeRupiah(current.cash_balance)}</dd></div><div><dt>Piutang</dt><dd>${financeRupiah(current.receivables_balance)}</dd></div><div><dt>Utang</dt><dd>${financeRupiah(current.payables_balance)}</dd></div><div><dt>Posisi likuiditas</dt><dd>${financeRupiah(current.net_liquidity)}</dd></div></dl><p class="hint">Pendapatan bersih, laba kotor, laba bersih, dan posisi likuiditas dihitung dari angka snapshot. Mekari tetap menjadi sumber pencatatan akuntansi; layar ini tidak membuat jurnal atau pembayaran.</p><div class="actions"><button data-action="mekari-finance-snapshots">Riwayat snapshot keuangan</button><button data-action="integrations">Kesehatan integrasi</button></div><h3>Periode dalam snapshot</h3>${report.periods.map(financePeriodCard).join('')}`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-finance-summary">Coba lagi</button>`;}
}

async function mekariFinanceSnapshotsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat snapshot keuangan Mekari','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const rows=await api.get('/api/integrations/mekari/finance-snapshots?limit=100');if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="hint">Snapshot immutable dari connector worker, terbaru dahulu.</p>${rows.map(row=>`<article class="material-event"><p class="status-label done">Berhasil</p><h3>${purchaseStamp(row.snapshot_at)}</h3><p>Dibaca ${n(row.records_read)} · periode ${n(row.period_count)}</p><button data-action="mekari-finance-snapshot" data-id="${e(row.id)}">Rincian snapshot keuangan</button></article>`).join('')||'<p class="state">Belum ada snapshot keuangan Mekari.</p>'}<button data-action="mekari-finance-summary">Ringkasan terbaru</button>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-finance-snapshots">Coba lagi</button>`;}
}

async function mekariFinanceSnapshotDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian snapshot keuangan Mekari','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const row=await api.get('/api/integrations/mekari/finance-snapshots/'+encodeURIComponent(batchId));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="form-info">${purchaseStamp(row.snapshot_at)} · Berhasil</p><p>Dibaca ${n(row.records_read)} · periode ${n(row.period_count)}</p><p class="hint">Cursor ${e(row.external_cursor||'tidak dicatat')} · ${e(row.reason)} · ${e(row.actor_name)}</p>${row.periods.map(financePeriodCard).join('')||'<p class="state">Snapshot ini tidak memuat periode laporan.</p>'}<div class="actions"><button data-action="mekari-finance-snapshots">Riwayat snapshot keuangan</button><button data-action="mekari-finance-summary">Ringkasan terbaru</button></div>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-finance-snapshot" data-id="${e(batchId)}">Coba lagi</button>`;}
}

const payableStatus={open:'Terbuka',partially_paid:'Dibayar sebagian',paid:'Lunas',void:'Dibatalkan'};
const payableDue=row=>row.due_in_days===null?payableStatus[row.status]:row.overdue?`${n(Math.abs(row.due_in_days))} hari lewat jatuh tempo`:row.due_in_days===0?'Jatuh tempo hari ini':`${n(row.due_in_days)} hari menuju jatuh tempo`;
const payableCard=row=>`<article class="material-event"><p class="status-label ${row.overdue?'late':row.status==='paid'?'done':''}">${e(row.overdue?'Overdue':payableStatus[row.status])}</p><h3>${e(row.reference)} · ${e(row.supplier_name)}</h3><p>Belum dibayar ${financeRupiah(row.outstanding_amount)} dari ${financeRupiah(row.original_amount)}</p><p class="hint">Invoice ${date(row.invoice_date)} · jatuh tempo ${date(row.due_date)} · ${e(payableDue(row))}</p></article>`;

async function mekariPayablesSummaryDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Utang Mekari','<p class="state">Memuat snapshot utang terbaru…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/integrations/mekari/payables-summary');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!report.snapshot){$('dialog-content').innerHTML='<p class="state">Belum ada snapshot utang Mekari. Connector worker harus mengirim snapshot sebelum ringkasan tersedia.</p><div class="actions"><button data-action="mekari-payable-snapshots">Riwayat snapshot utang</button><button data-action="integrations">Kesehatan integrasi</button></div>';return;}
    const s=report.summary;
    $('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · posisi ${date(report.snapshot.as_of)}</p><dl class="requirement-values"><div><dt>Invoice diterima</dt><dd>${n(s.accepted_payables)}</dd></div><div><dt>Terbuka</dt><dd>${n(s.open)}</dd></div><div><dt>Dibayar sebagian</dt><dd>${n(s.partially_paid)}</dd></div><div><dt>Lunas</dt><dd>${n(s.paid)}</dd></div><div><dt>Dibatalkan</dt><dd>${n(s.void)}</dd></div><div><dt>Total invoice aktif</dt><dd>${financeRupiah(s.total_original)}</dd></div><div><dt>Sudah dibayar</dt><dd>${financeRupiah(s.total_paid)}</dd></div><div><dt>Belum dibayar</dt><dd>${financeRupiah(s.total_outstanding)}</dd></div><div><dt>Overdue</dt><dd>${n(s.overdue_count)} · ${financeRupiah(s.overdue_amount)}</dd></div><div><dt>Jatuh tempo 0–7 hari</dt><dd>${n(s.due_next_7_days_count)} · ${financeRupiah(s.due_next_7_days_amount)}</dd></div></dl><p class="hint">Overdue dihitung terhadap tanggal posisi snapshot. Layar ini tidak membayar invoice, mengubah status vendor, atau membuat jurnal Mekari.</p><div class="actions"><button data-action="mekari-payable-snapshots">Riwayat snapshot utang</button><button data-action="integrations">Kesehatan integrasi</button></div><h3>Per supplier</h3>${report.suppliers.map(row=>`<article class="material-event"><h4>${e(row.supplier_name)}</h4><p>${n(row.outstanding_invoices)} invoice terbuka · ${financeRupiah(row.outstanding_amount)}</p><p class="hint">Overdue ${n(row.overdue_invoices)} · ${financeRupiah(row.overdue_amount)} · total ${n(row.invoices)} invoice</p></article>`).join('')||'<p class="state">Tidak ada invoice supplier.</p>'}<h3>Invoice vendor</h3>${report.payables.map(payableCard).join('')||'<p class="state">Snapshot ini tidak memuat invoice.</p>'}`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-payables-summary">Coba lagi</button>`;}
}

async function mekariPayableSnapshotsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat snapshot utang Mekari','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const rows=await api.get('/api/integrations/mekari/payable-snapshots?limit=100');if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="hint">Snapshot immutable dari connector worker, terbaru dahulu.</p>${rows.map(row=>`<article class="material-event"><p class="status-label done">Berhasil</p><h3>Posisi ${date(row.as_of)}</h3><p>Dibaca ${n(row.records_read)} · invoice ${n(row.payable_count)}</p><button data-action="mekari-payable-snapshot" data-id="${e(row.id)}">Rincian snapshot utang</button></article>`).join('')||'<p class="state">Belum ada snapshot utang Mekari.</p>'}<button data-action="mekari-payables-summary">Ringkasan terbaru</button>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-payable-snapshots">Coba lagi</button>`;}
}

async function mekariPayableSnapshotDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian snapshot utang Mekari','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const row=await api.get('/api/integrations/mekari/payable-snapshots/'+encodeURIComponent(batchId));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="form-info">${purchaseStamp(row.snapshot_at)} · posisi ${date(row.as_of)} · Berhasil</p><p>Dibaca ${n(row.records_read)} · invoice ${n(row.payable_count)}</p><p class="hint">Cursor ${e(row.external_cursor||'tidak dicatat')} · ${e(row.reason)} · ${e(row.actor_name)}</p>${row.payables.map(payableCard).join('')||'<p class="state">Snapshot ini tidak memuat invoice.</p>'}<div class="actions"><button data-action="mekari-payable-snapshots">Riwayat snapshot utang</button><button data-action="mekari-payables-summary">Ringkasan terbaru</button></div>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-payable-snapshot" data-id="${e(batchId)}">Coba lagi</button>`;}
}

const receivableStatus={open:'Terbuka',partially_paid:'Diterima sebagian',paid:'Lunas',void:'Dibatalkan'};
const receivableDue=row=>row.due_in_days===null?receivableStatus[row.status]:row.overdue?`${n(Math.abs(row.due_in_days))} hari lewat jatuh tempo`:row.due_in_days===0?'Jatuh tempo hari ini':`${n(row.due_in_days)} hari menuju jatuh tempo`;
const receivableCard=row=>`<article class="material-event"><p class="status-label ${row.overdue?'late':row.status==='paid'?'done':''}">${e(row.overdue?'Overdue':receivableStatus[row.status])}</p><h3>${e(row.reference)} · ${e(row.customer_name)}</h3><p>Belum diterima ${financeRupiah(row.outstanding_amount)} dari ${financeRupiah(row.original_amount)}</p><p class="hint">Invoice ${date(row.invoice_date)} · jatuh tempo ${date(row.due_date)} · ${e(receivableDue(row))}</p></article>`;

async function mekariReceivablesSummaryDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Piutang Mekari','<p class="state">Memuat snapshot piutang terbaru…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/integrations/mekari/receivables-summary');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!report.snapshot){$('dialog-content').innerHTML='<p class="state">Belum ada snapshot piutang Mekari. Connector worker harus mengirim snapshot sebelum ringkasan tersedia.</p><div class="actions"><button data-action="mekari-receivable-snapshots">Riwayat snapshot piutang</button><button data-action="integrations">Kesehatan integrasi</button></div>';return;}
    const s=report.summary;
    $('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · posisi ${date(report.snapshot.as_of)}</p><dl class="requirement-values"><div><dt>Invoice tercatat</dt><dd>${n(s.accepted_receivables)}</dd></div><div><dt>Terbuka</dt><dd>${n(s.open)}</dd></div><div><dt>Diterima sebagian</dt><dd>${n(s.partially_paid)}</dd></div><div><dt>Lunas</dt><dd>${n(s.paid)}</dd></div><div><dt>Dibatalkan</dt><dd>${n(s.void)}</dd></div><div><dt>Total invoice aktif</dt><dd>${financeRupiah(s.total_original)}</dd></div><div><dt>Sudah diterima</dt><dd>${financeRupiah(s.total_received)}</dd></div><div><dt>Belum diterima</dt><dd>${financeRupiah(s.total_outstanding)}</dd></div><div><dt>Overdue</dt><dd>${n(s.overdue_count)} · ${financeRupiah(s.overdue_amount)}</dd></div><div><dt>Jatuh tempo 0–7 hari</dt><dd>${n(s.due_next_7_days_count)} · ${financeRupiah(s.due_next_7_days_amount)}</dd></div></dl><p class="hint">Overdue dihitung terhadap tanggal posisi snapshot. Layar ini tidak menagih pelanggan, mengubah status invoice, atau membuat jurnal Mekari.</p><div class="actions"><button data-action="mekari-receivable-snapshots">Riwayat snapshot piutang</button><button data-action="integrations">Kesehatan integrasi</button></div><h3>Per pelanggan</h3>${report.customers.map(row=>`<article class="material-event"><h4>${e(row.customer_name)}</h4><p>${n(row.outstanding_invoices)} invoice terbuka · ${financeRupiah(row.outstanding_amount)}</p><p class="hint">Overdue ${n(row.overdue_invoices)} · ${financeRupiah(row.overdue_amount)} · total ${n(row.invoices)} invoice</p></article>`).join('')||'<p class="state">Tidak ada invoice pelanggan.</p>'}<h3>Invoice pelanggan</h3>${report.receivables.map(receivableCard).join('')||'<p class="state">Snapshot ini tidak memuat invoice.</p>'}`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-receivables-summary">Coba lagi</button>`;}
}

async function mekariReceivableSnapshotsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat snapshot piutang Mekari','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const rows=await api.get('/api/integrations/mekari/receivable-snapshots?limit=100');if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="hint">Snapshot immutable dari connector worker, terbaru dahulu.</p>${rows.map(row=>`<article class="material-event"><p class="status-label done">Berhasil</p><h3>Posisi ${date(row.as_of)}</h3><p>Dibaca ${n(row.records_read)} · invoice ${n(row.receivable_count)}</p><button data-action="mekari-receivable-snapshot" data-id="${e(row.id)}">Rincian snapshot piutang</button></article>`).join('')||'<p class="state">Belum ada snapshot piutang Mekari.</p>'}<button data-action="mekari-receivables-summary">Ringkasan terbaru</button>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-receivable-snapshots">Coba lagi</button>`;}
}

async function mekariReceivableSnapshotDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian snapshot piutang Mekari','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const row=await api.get('/api/integrations/mekari/receivable-snapshots/'+encodeURIComponent(batchId));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="form-info">${purchaseStamp(row.snapshot_at)} · posisi ${date(row.as_of)} · Berhasil</p><p>Dibaca ${n(row.records_read)} · invoice ${n(row.receivable_count)}</p><p class="hint">Cursor ${e(row.external_cursor||'tidak dicatat')} · ${e(row.reason)} · ${e(row.actor_name)}</p>${row.receivables.map(receivableCard).join('')||'<p class="state">Snapshot ini tidak memuat invoice.</p>'}<div class="actions"><button data-action="mekari-receivable-snapshots">Riwayat snapshot piutang</button><button data-action="mekari-receivables-summary">Ringkasan terbaru</button></div>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-receivable-snapshot" data-id="${e(batchId)}">Coba lagi</button>`;}
}

const payrollStatus={draft:'Draft',reviewing:'Ditinjau',approved:'Disetujui',paid:'Dibayar',cancelled:'Dibatalkan'};
const payrollPeriodCard=row=>{
  const approval=row.approval_request,financialChange=approval&&['period_start','period_end','currency','employee_count','gross_pay','employee_deductions','employer_contributions'].some(key=>row[key]!==approval.source[key]);
  const canSubmit=user.role!=='viewer'&&row.status==='reviewing'&&(!approval||['rejected','cancelled'].includes(approval.status)||(approval.status==='approved'&&financialChange));
  return `<article class="material-event" data-payroll-period="${e(row.id)}"><p class="status-label ${row.status==='paid'?'done':row.status==='cancelled'?'late':''}">Mekari · ${e(payrollStatus[row.status])}</p><h3>${date(row.period_start)}–${date(row.period_end)}</h3><p>${n(row.employee_count)} karyawan · gaji neto ${financeRupiah(row.net_pay)}</p><dl class="requirement-values"><div><dt>Gaji bruto</dt><dd>${financeRupiah(row.gross_pay)}</dd></div><div><dt>Potongan karyawan</dt><dd>${financeRupiah(row.employee_deductions)}</dd></div><div><dt>Kontribusi perusahaan</dt><dd>${financeRupiah(row.employer_contributions)}</dd></div><div><dt>Total biaya perusahaan</dt><dd>${financeRupiah(row.total_employer_cost)}</dd></div></dl><p class="hint">ID sumber ${e(row.external_payroll_id)}${row.payment_date?' · dibayar '+date(row.payment_date):''}</p>${row.accounting?`<p class="hint">Jurnal ${e(row.accounting.journal_reference)} · ${e(row.accounting.status==='posted'?'Posted':row.accounting.status==='reversed'?'Reversed':'Draft')}</p>`:''}${approval?`<p class="status-label ${approval.status==='approved'?'done':approval.status==='rejected'||approval.stale?'late':''}">Approval Beeloft · ${e(approvalStatus[approval.status])}${approval.stale?' · sumber berubah':''}</p><button data-action="payroll-approval-request" data-id="${e(approval.id)}" type="button">Rincian approval</button>`:''}${canSubmit?`<button data-action="new-payroll-approval" data-id="${e(row.id)}" type="button">${approval?'Ajukan ulang approval':'Ajukan approval'}</button>`:''}</article>`;
};

async function mekariPayrollSummaryDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Payroll Mekari','<p class="state">Memuat snapshot payroll terbaru…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/integrations/mekari/payroll-summary');
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!report.snapshot){$('dialog-content').innerHTML='<p class="state">Belum ada snapshot payroll Mekari. Connector worker harus mengirim snapshot sebelum ringkasan tersedia.</p><div class="actions"><button data-action="mekari-payroll-snapshots">Riwayat snapshot payroll</button><button data-action="payroll-payment-reconciliation">Rekonsiliasi pembayaran</button><button data-action="payroll-accounting-reconciliation">Rekonsiliasi akuntansi</button><button data-action="integrations">Kesehatan integrasi</button></div>';return;}
    if(!report.current){$('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · tidak memuat periode payroll</p><p class="state">Connector menyelesaikan snapshot kosong. Periksa sumber payroll Mekari sebelum memakai ringkasan ini.</p><div class="actions"><button data-action="mekari-payroll-snapshots">Riwayat snapshot payroll</button><button data-action="payroll-payment-reconciliation">Rekonsiliasi pembayaran</button><button data-action="payroll-accounting-reconciliation">Rekonsiliasi akuntansi</button><button data-action="integrations">Kesehatan integrasi</button></div>`;return;}
    const counts=report.status_counts;
    $('dialog-content').innerHTML=`<p class="form-info">Snapshot ${purchaseStamp(report.snapshot.snapshot_at)} · periode terbaru ${date(report.current.period_start)}–${date(report.current.period_end)}</p><dl class="requirement-values"><div><dt>Draft</dt><dd>${n(counts.draft)}</dd></div><div><dt>Ditinjau</dt><dd>${n(counts.reviewing)}</dd></div><div><dt>Disetujui</dt><dd>${n(counts.approved)}</dd></div><div><dt>Dibayar</dt><dd>${n(counts.paid)}</dd></div><div><dt>Dibatalkan</dt><dd>${n(counts.cancelled)}</dd></div></dl><p class="hint">Angka merupakan ringkasan agregat dari Mekari tanpa identitas karyawan. Approval Beeloft menyimpan otorisasi manajemen tanpa mengubah status Mekari, menjalankan pembayaran, atau membuat jurnal.</p><div class="actions"><button data-action="mekari-payroll-snapshots">Riwayat snapshot payroll</button><button data-action="payroll-payment-reconciliation">Rekonsiliasi pembayaran</button><button data-action="payroll-accounting-reconciliation">Rekonsiliasi akuntansi</button><button data-action="integrations">Kesehatan integrasi</button><button data-action="approvals">Inbox approval</button></div><h3>Periode terbaru</h3>${payrollPeriodCard(report.current)}<h3>Periode dalam snapshot</h3>${report.periods.map(payrollPeriodCard).join('')}`;
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-payroll-summary">Coba lagi</button>`;}
}

async function mekariPayrollSnapshotsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat snapshot payroll Mekari','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const rows=await api.get('/api/integrations/mekari/payroll-snapshots?limit=100');if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="hint">Snapshot agregat immutable dari connector worker, terbaru dahulu.</p>${rows.map(row=>`<article class="material-event"><p class="status-label done">Berhasil</p><h3>${purchaseStamp(row.snapshot_at)}</h3><p>Dibaca ${n(row.records_read)} · periode ${n(row.period_count)}</p><button data-action="mekari-payroll-snapshot" data-id="${e(row.id)}">Rincian snapshot payroll</button></article>`).join('')||'<p class="state">Belum ada snapshot payroll Mekari.</p>'}<button data-action="mekari-payroll-summary">Ringkasan terbaru</button>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-payroll-snapshots">Coba lagi</button>`;}
}

async function mekariPayrollSnapshotDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian snapshot payroll Mekari','<p class="state">Memuat snapshot…</p>');const modal=dialogVersion;
  try{const row=await api.get('/api/integrations/mekari/payroll-snapshots/'+encodeURIComponent(batchId));if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;$('dialog-content').innerHTML=`<p class="form-info">${purchaseStamp(row.snapshot_at)} · Berhasil</p><p>Dibaca ${n(row.records_read)} · periode ${n(row.period_count)}</p><p class="hint">Cursor ${e(row.external_cursor||'tidak dicatat')} · ${e(row.reason)} · ${e(row.actor_name)}</p>${row.periods.map(payrollPeriodCard).join('')||'<p class="state">Snapshot ini tidak memuat periode payroll.</p>'}<div class="actions"><button data-action="mekari-payroll-snapshots">Riwayat snapshot payroll</button><button data-action="mekari-payroll-summary">Ringkasan terbaru</button></div>`;}catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="mekari-payroll-snapshot" data-id="${e(batchId)}">Coba lagi</button>`;}
}

const payrollPaymentStatus={awaiting_payment:'Menunggu pembayaran',paid:'Sudah dibayar',exception:'Perlu perhatian'};
const payrollPaymentException={source_missing:'Periode tidak ada di snapshot payroll terbaru.',financial_mismatch:'Nilai atau konteks payroll berubah sejak approval.',source_cancelled:'Payroll dibatalkan di Mekari.',source_draft:'Payroll kembali menjadi draft di Mekari.'};
const payrollChangedField={period_start:'awal periode',period_end:'akhir periode',currency:'mata uang',employee_count:'jumlah karyawan',gross_pay:'gaji bruto',employee_deductions:'potongan karyawan',employer_contributions:'kontribusi perusahaan'};

async function payrollPaymentReconciliationDialog() {
  if(guardPending())return;
  openDialog('Rekonsiliasi pembayaran payroll',`<p class="hint">Menghubungkan approval Beeloft terbaru dengan status pembayaran pada snapshot Mekari terbaru. Laporan ini tidak mengirim uang atau membuat jurnal.</p><form id="payroll-payment-filter" class="filter-form"><div class="form-grid"><label>Status<select name="status"><option value="all">Semua status</option><option value="awaiting_payment">Menunggu pembayaran</option><option value="paid">Sudah dibayar</option><option value="exception">Perlu perhatian</option></select></label><label>Cari approval / ID payroll<input name="q" maxlength="160"></label></div><div class="actions"><button type="submit">Terapkan filter</button><button type="button" data-action="mekari-payroll-summary">Payroll Mekari</button><button type="button" data-action="payroll-accounting-reconciliation">Akuntansi payroll</button><button type="button" data-action="approvals">Inbox approval</button></div></form><p id="payroll-payment-message" class="state" role="status"></p><div id="payroll-payment-summary"></div><div id="payroll-payment-results"></div><button id="payroll-payment-more" type="button" hidden>Muat batch berikutnya</button>`);
  const version=epoch,modal=dialogVersion,form=$('payroll-payment-filter'),results=$('payroll-payment-results'),more=$('payroll-payment-more');
  let offset=0,generation=0;
  const load=async reset=>{
    const request=++generation;if(reset){offset=0;results.replaceChildren();}
    more.disabled=true;message('payroll-payment-message',reset?'Memuat rekonsiliasi…':'Memuat batch berikutnya…');
    try{
      const values=Object.fromEntries(new FormData(form));
      const report=await api.get('/api/payroll-payment-reconciliation?'+new URLSearchParams({...values,limit:25,offset}));
      if(request!==generation||version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
      const s=report.summary;
      $('payroll-payment-summary').innerHTML=`<dl class="requirement-values"><div><dt>Batch approved</dt><dd>${n(s.approved_batches)}</dd></div><div><dt>Menunggu pembayaran</dt><dd>${n(s.awaiting_payment)}</dd></div><div><dt>Sudah dibayar</dt><dd>${n(s.paid)}</dd></div><div><dt>Perlu perhatian</dt><dd>${n(s.exceptions)}</dd></div><div><dt>Gaji neto approved</dt><dd>${financeRupiah(s.expected_net_pay)}</dd></div><div><dt>Gaji neto dibayar</dt><dd>${financeRupiah(s.paid_net_pay)}</dd></div></dl>`;
      results.insertAdjacentHTML('beforeend',report.items.map(row=>{
        const detail=row.exception_reason?payrollPaymentException[row.exception_reason]||'Status sumber payroll perlu diperiksa.':'';
        const changed=row.changed_fields.length?' Bidang berubah: '+row.changed_fields.map(field=>payrollChangedField[field]||field).join(', ')+'.':'';
        return `<article class="material-event" data-payroll-payment="${e(row.id)}"><p class="status-label ${row.payment_status==='paid'?'done':row.payment_status==='exception'?'late':''}">${e(payrollPaymentStatus[row.payment_status])}</p><h3>${date(row.period_start)}–${date(row.period_end)}</h3><p>${n(row.employee_count)} karyawan · gaji neto approved ${financeRupiah(row.expected_net_pay)}</p><p>Total biaya perusahaan ${financeRupiah(row.expected_total_employer_cost)}</p><p class="hint">${e(row.approval_reference)} · ID sumber ${e(row.external_payroll_id)} · Mekari ${e(row.source_status?payrollStatus[row.source_status]:'tidak ditemukan')}${row.payment_date?' · dibayar '+date(row.payment_date):''}</p>${detail?`<p class="error">${e(detail+changed)}</p>`:''}<button data-action="payroll-approval-request" data-id="${e(row.approval_request_id)}">Rincian approval</button></article>`;
      }).join(''));
      if(reset&&!report.items.length)results.innerHTML='<p class="state">Tidak ada batch payroll untuk filter ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat batch berikutnya';message('payroll-payment-message','');
    }catch(error){if(version===epoch&&modal===dialogVersion){message('payroll-payment-message',error.message,true);more.hidden=false;more.textContent='Coba lagi';}}
    finally{more.disabled=false;}
  };
  form.onsubmit=event=>{event.preventDefault();load(true);};more.onclick=()=>load(false);load(true);
}

const payrollAccountingStatus={waiting_payment:'Menunggu pembayaran',awaiting_posting:'Menunggu posting',posted:'Sudah diposting',exception:'Perlu perhatian'};
const payrollAccountingException={payment_source_missing:'Periode tidak ada di snapshot payroll terbaru.',payment_financial_mismatch:'Nilai atau konteks payroll berubah sejak approval.',payment_source_cancelled:'Payroll dibatalkan di Mekari.',payment_source_draft:'Payroll kembali menjadi draft di Mekari.',posting_reversed:'Jurnal payroll sudah dibalik di Mekari.',posting_unbalanced:'Total debit dan kredit jurnal payroll tidak seimbang.',posting_amount_mismatch:'Nilai jurnal tidak sama dengan total biaya perusahaan yang disetujui.'};

async function payrollAccountingReconciliationDialog() {
  if(guardPending())return;
  openDialog('Rekonsiliasi akuntansi payroll',`<p class="hint">Mencocokkan payroll approved dan dibayar dengan metadata jurnal pada snapshot Mekari terbaru. Laporan ini hanya baca dan tidak membuat atau mem-posting jurnal.</p><form id="payroll-accounting-filter" class="filter-form"><div class="form-grid"><label>Status<select name="status"><option value="all">Semua status</option><option value="waiting_payment">Menunggu pembayaran</option><option value="awaiting_posting">Menunggu posting</option><option value="posted">Sudah diposting</option><option value="exception">Perlu perhatian</option></select></label><label>Cari approval / ID payroll / jurnal<input name="q" maxlength="160"></label></div><div class="actions"><button type="submit">Terapkan filter</button><button type="button" data-action="mekari-payroll-summary">Payroll Mekari</button><button type="button" data-action="payroll-payment-reconciliation">Pembayaran payroll</button><button type="button" data-action="approvals">Inbox approval</button></div></form><p id="payroll-accounting-message" class="state" role="status"></p><div id="payroll-accounting-summary"></div><div id="payroll-accounting-results"></div><button id="payroll-accounting-more" type="button" hidden>Muat batch berikutnya</button>`);
  const version=epoch,modal=dialogVersion,form=$('payroll-accounting-filter'),results=$('payroll-accounting-results'),more=$('payroll-accounting-more');
  let offset=0,generation=0;
  const load=async reset=>{
    const request=++generation;if(reset){offset=0;results.replaceChildren();}
    more.disabled=true;message('payroll-accounting-message',reset?'Memuat rekonsiliasi…':'Memuat batch berikutnya…');
    try{
      const values=Object.fromEntries(new FormData(form));
      const report=await api.get('/api/payroll-accounting-reconciliation?'+new URLSearchParams({...values,limit:25,offset}));
      if(request!==generation||version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
      const s=report.summary;
      $('payroll-accounting-summary').innerHTML=`<dl class="requirement-values"><div><dt>Batch approved</dt><dd>${n(s.approved_batches)}</dd></div><div><dt>Menunggu pembayaran</dt><dd>${n(s.waiting_payment)}</dd></div><div><dt>Menunggu posting</dt><dd>${n(s.awaiting_posting)}</dd></div><div><dt>Sudah diposting</dt><dd>${n(s.posted)}</dd></div><div><dt>Perlu perhatian</dt><dd>${n(s.exceptions)}</dd></div><div><dt>Biaya perusahaan approved</dt><dd>${financeRupiah(s.expected_employer_cost)}</dd></div><div><dt>Biaya sudah diposting</dt><dd>${financeRupiah(s.posted_employer_cost)}</dd></div></dl>`;
      results.insertAdjacentHTML('beforeend',report.items.map(row=>{
        const detail=row.exception_reason?payrollAccountingException[row.exception_reason]||'Status akuntansi payroll perlu diperiksa.':'';
        const changed=row.changed_fields.length?' Bidang berubah: '+row.changed_fields.map(field=>payrollChangedField[field]||field).join(', ')+'.':'';
        const journal=row.journal_reference?`<p class="hint">Jurnal ${e(row.journal_reference)} · ${e(row.journal_status)}${row.posting_date?' · posting '+date(row.posting_date):''}</p><p>Debit ${financeRupiah(row.debit_total)} · kredit ${financeRupiah(row.credit_total)}</p>`:'<p class="hint">Jurnal belum tersedia pada snapshot Mekari terbaru.</p>';
        return `<article class="material-event" data-payroll-accounting="${e(row.id)}"><p class="status-label ${row.workflow_status==='posted'?'done':row.workflow_status==='exception'?'late':''}">${e(payrollAccountingStatus[row.workflow_status])}</p><h3>${date(row.period_start)}–${date(row.period_end)}</h3><p>${n(row.employee_count)} karyawan · biaya perusahaan approved ${financeRupiah(row.expected_total_employer_cost)}</p><p class="hint">${e(row.approval_reference)} · ID sumber ${e(row.external_payroll_id)} · pembayaran ${e(row.payment_status?payrollStatus[row.payment_status]:'tidak ditemukan')}${row.payment_date?' '+date(row.payment_date):''}</p>${journal}${detail?`<p class="error">${e(detail+changed)}</p>`:''}<button data-action="payroll-approval-request" data-id="${e(row.approval_request_id)}">Rincian approval</button></article>`;
      }).join(''));
      if(reset&&!report.items.length)results.innerHTML='<p class="state">Tidak ada batch payroll untuk filter ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat batch berikutnya';message('payroll-accounting-message','');
    }catch(error){if(version===epoch&&modal===dialogVersion){message('payroll-accounting-message',error.message,true);more.hidden=false;more.textContent='Coba lagi';}}
    finally{more.disabled=false;}
  };
  form.onsubmit=event=>{event.preventDefault();load(true);};more.onclick=()=>load(false);load(true);
}

function renderAiInvestigation(report,target,source=report.source_payload) {
  const intents={overview:'Ringkasan bisnis',production:'Kondisi produksi',stockout:'Risiko stockout',approvals:'Antrean approval',margin:'Margin kontribusi'};
  const confidence={high:'tinggi',medium:'sedang',low:'rendah'};
  const severity={critical:'Kritis',high:'Tinggi',medium:'Sedang',info:'Informasi'};
  const unit={sku:'SKU',order:'order',issue:'kendala',item:'item',material:'bahan',pcs:'pcs'};
  const factValue=row=>row.unit==='IDR'?rupiah(String(row.value)):`${n(Number(row.value))} ${unit[row.unit]||row.unit}`;
  const focus=[...report.focus.products.map(row=>row.sku),...report.focus.orders.map(row=>row.reference)];
  const facts=report.facts.map(row=>`<div><dt>${e(row.label)}</dt><dd>${e(factValue(row))}</dd></div>`).join('');
  const findings=report.findings.map(row=>`<article class="material-event" data-ai-finding="${e(row.severity)}"><p class="status-label ${['critical','high'].includes(row.severity)?'late':row.severity==='info'?'done':''}">${e(severity[row.severity]||row.severity)}</p><h3>${e(row.title)}</h3><p>${e(row.detail)}</p><p class="hint">Sumber: ${e(row.source)}</p></article>`).join('');
  const supported=new Set(['create_production_order','create_purchase_request']);
  const recommendations=report.recommendations.map((row,index)=>`<article class="material-event" data-ai-recommendation="${e(row.kind)}"><p class="status-label late">Perlu approval</p><h3>${e(row.title)}</h3><p>${e(row.detail)}</p><p class="hint">Belum dijalankan · sumber ${e(row.source)}</p>${user.role!=='viewer'&&supported.has(row.kind)?`<button type="button" data-ai-proposal="${index}">Ajukan untuk approval</button>`:''}</article>`).join('');
  const feedback=report.feedback_summary||{helpful:0,not_helpful:0,respondents:0};
  const actionStatus={submitted:'Menunggu keputusan',approved:'Disetujui',rejected:'Ditolak',cancelled:'Dibatalkan'};
  const links=(report.linked_actions||[]).map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${e(actionStatus[row.status]||row.status)}</h3><p>${e(row.recommendation.title)}</p><button data-action="ai-action-proposal" data-id="${e(row.id)}">Buka proposal tindakan</button></article>`).join('');
  target.innerHTML=`${report.id?`<p class="form-info">Disimpan ${e(report.actor_name)} · ${purchaseStamp(report.created_at)}</p>`:''}<section class="ai-answer" aria-labelledby="ai-answer-heading"><p class="eyebrow">${e(intents[report.intent]||report.interpretation)} · keyakinan ${e(confidence[report.confidence]||report.confidence)}</p><h3 id="ai-answer-heading">Jawaban</h3><p class="hint">Pertanyaan: ${e(report.question)}</p><p>${e(report.answer)}</p><p class="hint">Analisis lokal · tidak mengirim data keluar · hanya baca${focus.length?' · fokus '+e(focus.join(', ')):''}</p></section>
    <div class="actions"><button type="button" data-ai-history>Riwayat investigasi</button></div>
    <h3>Fakta pendukung</h3><dl class="requirement-values">${facts||'<div><dt>Hasil</dt><dd>Belum ada fakta pendukung.</dd></div>'}</dl>
    <h3>Temuan</h3>${findings||'<p class="state">Tidak ada temuan yang perlu ditampilkan.</p>'}
    <h3>Rekomendasi</h3>${recommendations||'<p class="state">Belum ada rekomendasi dari hasil ini.</p>'}
    ${report.id?`<h3>Feedback tim</h3><p>${n(feedback.helpful)} membantu · ${n(feedback.not_helpful)} perlu diperbaiki · ${n(feedback.respondents)} responden</p><div class="actions"><button data-ai-feedback="helpful">Jawaban membantu</button><button data-ai-feedback="not_helpful">Perlu diperbaiki</button></div>`:''}
    ${links?`<h3>Tindakan dari investigasi ini</h3>${links}`:''}
    <details><summary>Batas analisis</summary>${report.limitations.map(item=>`<p class="hint">${e(item)}</p>`).join('')}</details>`;
  target.querySelectorAll('[data-ai-proposal]').forEach(proposal=>proposal.onclick=()=>
    aiActionProposalForm(report.recommendations[Number(proposal.dataset.aiProposal)],
      {...source,investigation_id:report.id}));
  target.querySelectorAll('[data-ai-feedback]').forEach(button=>button.onclick=()=>{
    const rating=button.dataset.aiFeedback;
    formDialog(rating==='helpful'?'Catat jawaban membantu':'Catat yang perlu diperbaiki',materialReason,
      form=>({rating,reason:new FormData(form).get('reason').trim()}),
      '/api/ai/investigations/'+encodeURIComponent(report.id)+'/feedback',
      'Feedback tersimpan sebagai event append-only. Respons terbaru Anda dipakai dalam ringkasan.');
  });
  // Riwayat hidup di halaman ai-view, jadi tombol ini menutup dialog fokusnya lebih dulu lalu
  // menggulir ke section riwayat; dari konteks lain ia memanggil halaman tersebut.
  target.querySelectorAll('[data-ai-history]').forEach(button=>button.onclick=()=>{
    if($('dialog').open)$('dialog').close();
    if(view!=='ai')showAi();
    const history=$('ai-history');
    if(history){history.scrollIntoView({block:'start'});history.querySelector('input')?.focus();}
  });
}

async function aiInvestigationDetailDialog(investigationId) {
  if(guardPending())return;
  const version=epoch;openDialog('Investigasi tersimpan','<p class="state">Memuat investigasi…</p>');const modal=dialogVersion;
  try{
    const report=await api.get('/api/ai/investigations/'+encodeURIComponent(investigationId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    renderAiInvestigation(report,$('dialog-content'));
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="ai-investigation" data-id="${e(investigationId)}">Coba lagi</button>`;}
}

// Milestone D: Tanya Beeloft adalah halaman workspace. Prompt, asumsi, hasil, feedback, dan
// riwayat investigasi hidup di ai-view; proposal tindakan dan rincian investigasi tersimpan
// tetap dialog terfokus. Aktivasi memulai ulang tampilan seperti saat dialog dibuka segar.
function showAi() {
  if(guardPending())return;
  activateWorkspace('ai-brain');
  aiTransaction=null;unresolved=false;modalBusy=false;
  $('ai-results').replaceChildren();
  message('ai-message','');
  // Milestone D: tidak ada batasan max pada as_of — dialog lama juga membiarkan pengguna
  // memilih tanggal posisi masa depan, dan data sintetis uji memakai tanggal tersebut.
  const form=$('ai-form');
  // Form adalah markup statis halaman, jadi state <details> asumsi bertahan lintas aktivasi
  // meskipun pengguna sudah keluar/masuk lagi. Dialog lama merender form segar setiap kali,
  // jadi aktivasi mengembalikan panel ke keadaan tertutup seperti saat baru dibuka.
  form.querySelector('details.ai-assumptions').open=false;
  if(!form.elements.as_of.value)form.elements.as_of.value=jakartaToday();
  [...form.elements].forEach(control=>control.disabled=false);
  $('ai-submit').textContent='Analisis dan simpan';$('ai-reauth').hidden=true;
  loadAiHistory(true);
}
async function loadAiHistory(reset=true) {
  const version=epoch,request=++aiHistoryRequest,form=$('ai-history-filter'),list=$('ai-history-list'),more=$('ai-history-more');
  const current=()=>version===epoch&&request===aiHistoryRequest&&view==='ai';
  if(reset){aiHistoryBefore=null;list.replaceChildren();}
  more.disabled=true;message('ai-history-message','Memuat riwayat investigasi…');
  try{
    const values=Object.fromEntries(new FormData(form));
    const query=new URLSearchParams({limit:50,intent:values.intent,q:values.q.trim()});
    if(aiHistoryBefore)query.set('before',aiHistoryBefore);
    const rows=await api.get('/api/ai/investigations?'+query);
    if(!current())return;
    message('ai-history-message',rows.length?'':list.children.length?'Tidak ada riwayat yang lebih lama.':'Belum ada investigasi tersimpan.');
    list.insertAdjacentHTML('beforeend',rows.map(row=>`<article class="material-event"><p class="eyebrow">${e(row.interpretation)}</p><h3>${e(row.question)}</h3><p>${e(row.answer)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)} · ${n(row.feedback_summary.respondents)} feedback · ${n(row.action_count)} tindakan</p><button data-action="ai-investigation" data-id="${e(row.id)}">Buka investigasi</button></article>`).join(''));
    aiHistoryBefore=rows.at(-1)?.sequence||aiHistoryBefore;more.hidden=rows.length<50;
  }catch(error){if(current())message('ai-history-message',error.message,true);}
  finally{if(current())more.disabled=false;}
}
async function submitAiInvestigation() {
  const version=epoch,request=aiRequest,form=$('ai-form'),button=$('ai-submit'),reauth=$('ai-reauth'),storageKey=pendingKey(),actorId=user.id;
  const current=()=>version===epoch&&request===aiRequest&&view==='ai';
  const lock=value=>[...form.elements].filter(control=>control!==button&&control!==reauth).forEach(control=>control.disabled=value);
  button.disabled=true;button.textContent='Menganalisis…';modalBusy=true;
  message('ai-message','Membaca ledger lalu menyimpan snapshot investigasi…');
  $('ai-results').replaceChildren();
  try{
    if(!aiTransaction){
      const raw=Object.fromEntries(new FormData(form));
      for(const key of ['window_days','lead_time_days','review_period_days','safety_stock_days','batch_multiple']) raw[key]=Number(raw[key]);
      aiTransaction=api.transaction('/api/ai/investigations',raw);
      sessionStorage.setItem(storageKey,JSON.stringify({transaction:aiTransaction,title:'Simpan investigasi AI',
        info:'Pertanyaan dan snapshot bukti disimpan satu kali.',actor_id:actorId}));
    }else await sameActorGuard(actorId);
    const report=await api.save(aiTransaction);
    clearPending(storageKey,aiTransaction);
    if(!current())return;
    aiTransaction=null;unresolved=false;modalBusy=false;lock(false);reauth.hidden=true;message('ai-message','');
    renderAiInvestigation(report,$('ai-results'));
    loadAiHistory(true);
    notify('Investigasi tersimpan.');
  }catch(error){
    if(current()){
      const denied=error.status===401||error.status===403;
      unresolved=Boolean(error.uncertain||(unresolved&&denied));
      if(!unresolved){clearPending(storageKey,aiTransaction);aiTransaction=null;}
      lock(unresolved);reauth.hidden=!denied;
      message('ai-message',error.message+(unresolved&&denied?' Masuk ulang dengan akun yang sama untuk memastikan snapshot tidak digandakan.':''),true);
      $('ai-message').insertAdjacentHTML('beforeend','<br><button id="ai-retry" type="button">Coba lagi</button>');
      $('ai-retry').onclick=submitAiInvestigation;
    }
  }finally{
    // Halaman bisa ditinggalkan tengah analisis (pindah nav atau session berganti), sedangkan
    // modalBusy juga mengunci dialog lain. Kunci itu dilepas di sini tanpa syarat, bukan hanya
    // saat halaman ini masih aktif; status unresolved tetap menjaga form yang terkunci.
    modalBusy=false;
    if(current()){button.disabled=false;button.textContent=unresolved?'Coba ulang penyimpanan':'Analisis dan simpan';}
  }
}
$('ai-brain').onclick=showAi;
$('ai-back').onclick=showBoard;
$('ai-reauth').onclick=()=>reauthenticate('ai-message');
$('ai-form').onsubmit=event=>{event.preventDefault();submitAiInvestigation();};
document.querySelectorAll('[data-ai-question]').forEach(example=>example.onclick=()=>{
  $('ai-question').value=example.dataset.aiQuestion;$('ai-question').focus();
});
$('ai-history-jump').onclick=()=>{const history=$('ai-history');history.scrollIntoView({block:'start'});history.querySelector('input')?.focus();};
$('ai-history-filter').onsubmit=event=>{event.preventDefault();loadAiHistory(true);};
$('ai-history-more').onclick=()=>loadAiHistory(false);
$('integrations-back').onclick=showBoard;
$('integrations-refresh').onclick=()=>loadIntegrations();
$('audit-back').onclick=showBoard;

async function aiActionProposalForm(recommendation,source) {
  if(guardPending())return;
  const common=form=>({...source,action_kind:recommendation.kind,
    subject_id:recommendation.preview.product_id||recommendation.preview.material_id,
    ...Object.fromEntries(new FormData(form))});
  if(recommendation.kind==='create_production_order'){
    const version=epoch;openDialog('Ajukan order produksi','<p class="state">Memuat daftar PIC…</p>');const modal=dialogVersion;
    try{
      const users=(await api.get('/api/users')).filter(row=>row.active&&row.role!=='viewer');
      if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
      formDialog('Ajukan order produksi',field('reference','Referensi order','text','required maxlength="160"')+
        field('title','Nama order','text','required maxlength="160"')+
        `<label>PIC produksi<select name="owner_id" required>${users.map(row=>option(row.id,row.name)).join('')}</select></label>`+
        field('due_date','Target selesai','date','required')+materialReason,
        common,'/api/ai/action-proposals',
        `${recommendation.title} · ${n(recommendation.preview.quantity)} pcs. Order baru dibuat hanya setelah admin menyetujui proposal dan rekomendasi masih sama.`);
    }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="ai-brain">Kembali ke investigasi</button>`;}
  }else{
    formDialog('Ajukan purchase request',field('reference','Referensi PR','text','required maxlength="160"')+
      field('required_date','Tanggal kebutuhan','date','required')+
      field('estimated_value','Estimasi total (Rp)','number','required min="0.01" max="1000000000000" step="0.01"')+materialReason,
      common,'/api/ai/action-proposals',
      `${recommendation.title} · ${materialQty(recommendation.preview.quantity,recommendation.preview.unit)}. PR dibuat setelah admin menyetujui proposal; PR tersebut tetap masuk workflow approval purchasing.`);
  }
}

async function aiActionProposalDialog(proposalId) {
  if(guardPending())return;
  const version=epoch;openDialog('Proposal tindakan AI','<p class="state">Memuat proposal…</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/ai/action-proposals/'+encodeURIComponent(proposalId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const production=row.action_kind==='create_production_order',action=production?'Buat order produksi':'Buat purchase request';
    const payload=row.action_payload,quantity=payload.lines[0].quantity;
    const details=production?`<p>${e(payload.title)} · ${n(quantity)} pcs · target ${date(payload.due_date)}</p>`:
      `<p>${e(materialQty(quantity,row.recommendation.preview.unit))} · dibutuhkan ${date(payload.required_date)} · ${e(rupiah(payload.estimated_value))}</p>`;
    const decisions=[];
    if(user.role==='admin'&&row.status==='submitted')decisions.push(['approved','Setujui dan jalankan'],['rejected','Tolak proposal']);
    if(row.status==='submitted'&&(user.role==='admin'||row.actor_id===user.id))decisions.push(['cancelled','Batalkan proposal']);
    const executed=row.executed_entity_id?`<p class="form-info">Tindakan selesai. ${production?'Order produksi':'Purchase request'} sudah dibuat.</p><button data-action="${production?'detail':'purchase-request'}" data-id="${e(row.executed_entity_id)}">Buka hasil tindakan</button>`:'';
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${e(approvalStatus[row.status])}</p><p class="eyebrow">${e(action)}</p><h3>${e(row.recommendation.title)}</h3>${details}<p class="reason">${e(row.reason)}</p><p class="hint">Diajukan ${e(row.actor_name)} · ${purchaseStamp(row.created_at)}. Saat approval, sistem menghitung ulang rekomendasi dan membatalkan eksekusi bila sumber berubah.</p>${executed}<div class="actions">${decisions.map(([status,label])=>`<button data-ai-action-decision="${status}">${label}</button>`).join('')}${row.investigation_id?`<button data-action="ai-investigation" data-id="${e(row.investigation_id)}">Buka investigasi asal</button>`:''}<button data-action="approvals">Inbox approval</button></div><h3>Riwayat keputusan</h3>${row.history.map(event=>`<article class="material-event"><strong>${e(approvalStatus[event.status])}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)} · ${purchaseStamp(event.created_at)}</p></article>`).join('')}`;
    $('dialog-content').querySelectorAll('[data-ai-action-decision]').forEach(button=>button.onclick=()=>{
      const decision=button.dataset.aiActionDecision;
      formDialog(button.textContent,materialReason,form=>({...Object.fromEntries(new FormData(form)),status:decision,expected_revision:row.revision}),
        '/api/ai/action-proposals/'+encodeURIComponent(row.id)+'/decisions',
        `${row.reference} · ${action}. ${decision==='approved'?'Rekomendasi diperiksa ulang lalu tindakan dijalankan dalam satu transaksi.':'Keputusan tersimpan permanen.'}`);
    });
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="ai-action-proposal" data-id="${e(proposalId)}">Coba lagi</button>`;}
}

function showDemandForecast() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('demand-forecast','Forecast demand per SKU',`<form id="forecast-form" class="filter-form">
    <p class="hint">Forecast memakai dua periode historis yang sama panjang. Demand terbaru berbobot 70% dan periode sebelumnya 30%. Retur aktif mengurangi demand pada tanggal pengiriman asal.</p>
    <div class="form-grid">
      ${field('as_of','Data sampai tanggal','date',`required value="${today}"`)}
      ${field('window_days','Panjang tiap periode (hari)','number','required min="7" max="90" step="1" value="28"')}
      ${field('horizon_days','Horizon forecast (hari)','number','required min="1" max="180" step="1" value="30"')}
      ${field('marketplace','Marketplace','text','maxlength="160" placeholder="Semua marketplace"')}
      <label class="full">Cari SKU atau produk<input name="query" type="search" maxlength="160" placeholder="Kode, nama, warna, atau ukuran"></label>
    </div>
    <div class="form-actions"><button class="primary" id="forecast-submit" type="submit">Hitung forecast</button></div>
  </form><p id="forecast-message" class="state" role="status" hidden></p><div id="forecast-results"></div>`);
  const version=epoch,form=$('forecast-form'),button=$('forecast-submit');
  restoreAnalyticsFilters('demand-forecast',form);
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='demand-forecast'&&request===analyticsRequest;
  const load=async()=>{
    if(!current())return;
    button.disabled=true;button.textContent='Menghitung…';
    message('forecast-message','Menghitung demand dari shipment dan retur aktif…');
    $('forecast-results').replaceChildren();
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','100');params.set('offset','0');
      const report=await api.get('/api/demand-forecast?'+params);
      if(!current())return;
      message('forecast-message','');
      const trends={new:'Demand baru',up:'Naik',down:'Turun',flat:'Stabil'};
      $('forecast-results').innerHTML=`<p class="form-info">Riwayat ${date(report.history_start)}–${date(report.as_of)}<br>Periode lama berakhir ${date(report.previous_period_end)} · periode terbaru mulai ${date(report.recent_period_start)}<br>Horizon ${n(report.horizon_days)} hari · total forecast ${n(Number(report.total_forecast_quantity))} pcs</p>
        <p class="hint">Hasil berupa estimasi desimal. Angka ini belum memperhitungkan stok tersedia, stok dalam perjalanan, lead time, MOQ, atau safety stock.</p>
        ${report.items.length?report.items.map(row=>`<article class="material-event" data-forecast-sku="${e(row.sku)}"><h3>${e(row.sku)} · ${n(Number(row.forecast_quantity))} pcs</h3><p>${e(row.name)}${[row.color,row.size].filter(Boolean).length?' · '+e([row.color,row.size].filter(Boolean).join(' / ')):''}</p><p class="status-label ${row.history_status==='no_history'?'late':''}">${row.history_status==='no_history'?'Belum ada riwayat demand':e(trends[row.trend])+(row.trend_percent!==null?' '+e(row.trend_percent)+'%':'')}</p><dl class="requirement-values"><div><dt>Periode sebelumnya</dt><dd>${n(row.previous_net_demand)} pcs neto</dd></div><div><dt>Periode terbaru</dt><dd>${n(row.recent_net_demand)} pcs neto</dd></div><div><dt>Rata-rata historis</dt><dd>${n(Number(row.historical_daily_rate))} pcs/hari</dd></div><div><dt>Rate forecast</dt><dd>${n(Number(row.forecast_daily_rate))} pcs/hari</dd></div></dl><p class="hint">Shipment ${n(row.shipment_count)} · retur lama ${n(row.previous_returned_quantity)} pcs · retur terbaru ${n(row.recent_returned_quantity)} pcs${row.marketplaces.length?' · '+e(row.marketplaces.join(', ')):''}</p></article>`).join(''):'<p class="state">Tidak ada SKU yang cocok dengan filter.</p>'}
        ${report.total>report.items.length?`<p class="hint">Menampilkan ${n(report.items.length)} dari ${n(report.total)} SKU. Persempit pencarian untuk melihat SKU lain.</p>`:''}`;
    }catch(error){
      if(current()){
        message('forecast-message',error.message,true);
        $('forecast-message').insertAdjacentHTML('beforeend','<br><button id="forecast-retry" type="button">Coba lagi</button>');
        $('forecast-retry').onclick=load;
      }
    }finally{if(current()){button.disabled=false;button.textContent='Hitung forecast';}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('demand-forecast',form);load();};
}
$('demand-forecast').onclick=showDemandForecast;

function showReturnInsights() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('return-insights','Analisis retur per SKU',`<form id="return-insights-form" class="filter-form">
    <p class="hint">Kohort memakai shipment dalam periode yang dipilih. Retur aktif sampai tanggal laporan dikelompokkan per SKU, ukuran, dan marketplace berdasarkan alasan yang dicatat tim.</p>
    <div class="form-grid">
      ${field('as_of','Data sampai tanggal','date',`required value="${today}"`)}
      ${field('window_days','Panjang periode (hari)','number','required min="7" max="365" step="1" value="90"')}
      ${field('marketplace','Marketplace','text','maxlength="160" placeholder="Semua marketplace"')}
      <label>Cari SKU atau produk<input name="query" type="search" maxlength="160" placeholder="Kode, nama, warna, atau ukuran"></label>
    </div>
    <div class="form-actions"><button class="primary" id="return-insights-submit" type="submit">Tampilkan analisis</button></div>
  </form><p id="return-insights-message" class="state" role="status" hidden></p><div id="return-insights-summary"></div><div id="return-insights-results"></div><button id="return-insights-more" type="button" hidden>Muat SKU berikutnya</button>`);
  const version=epoch,form=$('return-insights-form'),submit=$('return-insights-submit');
  restoreAnalyticsFilters('return-insights',form);
  let offset=0,generation=0;
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='return-insights'&&request===analyticsRequest;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('return-insights-summary').replaceChildren();$('return-insights-results').replaceChildren();}
    const gen=generation,more=$('return-insights-more');
    submit.disabled=true;more.disabled=true;more.hidden=true;
    message('return-insights-message',offset?'Memuat SKU berikutnya…':'Menghitung retur dari shipment dalam periode…');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/return-insights?'+params);
      if(!current()||gen!==generation)return;
      message('return-insights-message','');
      if(!offset)$('return-insights-summary').innerHTML=`<p class="form-info">Periode ${date(report.period_start)}–${date(report.as_of)}<br>${n(report.summary.shipped_quantity)} pcs dikirim · ${n(report.summary.returned_quantity)} pcs kembali · rate retur ${e(report.summary.return_rate)}%</p><dl class="requirement-values"><div><dt>Sizing</dt><dd>${n(report.summary.sizing_quantity)} pcs</dd></div><div><dt>Halaman produk</dt><dd>${n(report.summary.product_page_quantity)} pcs</dd></div><div><dt>Defect</dt><dd>${n(report.summary.defect_quantity)} pcs</dd></div><div><dt>Alasan lain</dt><dd>${n(report.summary.other_quantity)} pcs</dd></div></dl><p class="hint">Sizing = terlalu kecil atau besar. Halaman produk = barang atau warna tidak sesuai. Rate memakai jumlah retur dibagi jumlah yang dikirim dalam kohort.</p>`;
      const html=report.items.map(row=>`<article class="material-event" data-return-insight-sku="${e(row.sku)}"><h3>${e(row.sku)} · ${e(row.marketplace)}</h3><p>${e(row.name)}${[row.color,row.size].filter(Boolean).length?' · '+e([row.color,row.size].filter(Boolean).join(' / ')):''}</p><dl class="requirement-values"><div><dt>Dikirim</dt><dd>${n(row.shipped_quantity)} pcs</dd></div><div><dt>Diretur</dt><dd>${n(row.returned_quantity)} pcs</dd></div><div><dt>Rate retur</dt><dd><strong>${e(row.return_rate)}%</strong></dd></div><div><dt>Terlalu kecil</dt><dd>${n(row.reason_quantities.too_small)} pcs</dd></div><div><dt>Terlalu besar</dt><dd>${n(row.reason_quantities.too_big)} pcs</dd></div><div><dt>Barang tidak sesuai</dt><dd>${n(row.reason_quantities.wrong_item)} pcs</dd></div><div><dt>Warna tidak sesuai</dt><dd>${n(row.reason_quantities.color_mismatch)} pcs</dd></div><div><dt>Defect</dt><dd>${n(row.reason_quantities.defect)} pcs</dd></div><div><dt>Alasan lain</dt><dd>${n(row.reason_quantities.other)} pcs</dd></div></dl><p class="hint">${n(row.shipment_count)} shipment${row.latest_returned_date?' · retur terakhir '+date(row.latest_returned_date):' · belum ada retur pada kohort'}</p></article>`).join('');
      appendRows('return-insights-results',html);
      if(!offset&&!report.items.length)$('return-insights-results').innerHTML='<p class="state">Tidak ada shipment yang cocok dengan filter pada periode ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat SKU berikutnya';
    }catch(error){
      if(current()&&gen===generation){
        message('return-insights-message',error.message,true);
        $('return-insights-message').insertAdjacentHTML('beforeend','<br><button id="return-insights-retry" type="button">Coba lagi</button>');
        $('return-insights-retry').onclick=()=>load();
      }
    }finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('return-insights',form);load(true);};
  $('return-insights-more').onclick=()=>load();
}

async function payrollApprovalForm(periodId) {
  if(guardPending())return;
  const version=epoch;
  try{
    const report=await api.get('/api/integrations/mekari/payroll-summary');if(version!==epoch)return;
    const period=report.periods.find(row=>row.id===periodId);
    if(!period){notify('Periode tidak lagi berada pada snapshot payroll terbaru.');return;}
    formDialog('Ajukan approval payroll',materialReason,
      form=>({reason:new FormData(form).get('reason').trim()}),
      '/api/integrations/mekari/payroll-periods/'+encodeURIComponent(period.id)+'/approval-requests',
      `${period.external_payroll_id} · ${date(period.period_start)}–${date(period.period_end)} · ${financeRupiah(period.total_employer_cost)}\nApproval hanya mencatat otorisasi manajemen dan tidak mengubah Mekari atau menjalankan pembayaran.`);
  }catch(error){notify(error.message);}
}

async function payrollApprovalRequestDialog(requestId) {
  if(guardPending())return;
  const version=epoch;openDialog('Approval batch payroll','<p class="state">Memuat permintaan payroll…</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/payroll-approval-requests/'+encodeURIComponent(requestId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const source=row.source,pending=row.status==='submitted',buttons=[];
    if(pending&&user.role==='admin'&&!row.stale)buttons.push(['approved','Setujui payroll']);
    if(pending&&user.role==='admin')buttons.push(['rejected','Tolak payroll']);
    if(pending&&user.role==='operator'&&row.actor_id===user.id)buttons.push(['cancelled','Batalkan pengajuan']);
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${e(approvalStatus[row.status])}</p>${row.stale?(pending?'<p class="error">Snapshot payroll sumber sudah berubah atau tidak lagi tersedia. Permintaan ini tidak dapat disetujui.</p>':'<p class="hint">Snapshot payroll sumber berubah setelah keputusan ini dicatat.</p>'):''}<h3>${date(source.period_start)}–${date(source.period_end)}</h3><p>${n(source.employee_count)} karyawan · status Mekari ${e(payrollStatus[source.status])}</p><dl class="requirement-values"><div><dt>Gaji bruto</dt><dd>${financeRupiah(source.gross_pay)}</dd></div><div><dt>Potongan karyawan</dt><dd>${financeRupiah(source.employee_deductions)}</dd></div><div><dt>Gaji neto</dt><dd>${financeRupiah(source.net_pay)}</dd></div><div><dt>Kontribusi perusahaan</dt><dd>${financeRupiah(source.employer_contributions)}</dd></div><div><dt>Total biaya perusahaan</dt><dd>${financeRupiah(source.total_employer_cost)}</dd></div></dl><p class="reason">${e(row.reason)}</p><p class="hint">ID sumber ${e(source.external_payroll_id)} · snapshot ${purchaseStamp(source.snapshot_at)} · diajukan ${e(row.actor_name)} ${purchaseStamp(row.created_at)}. Keputusan tidak mengubah Mekari atau menjalankan pembayaran.</p><div class="actions">${buttons.map(([status,label])=>`<button data-payroll-decision="${status}" type="button">${label}</button>`).join('')}<button data-action="mekari-payroll-summary" type="button">Ringkasan payroll</button><button data-action="approvals" type="button">Inbox approval</button></div><h3>Riwayat keputusan</h3>${row.history.map(event=>`<article class="history-item"><time>${e(auditStamp(event.created_at))}</time><div><strong>${e(approvalStatus[event.status])}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)}</p></div></article>`).join('')}`;
    $('dialog-content').querySelectorAll('[data-payroll-decision]').forEach(button=>button.onclick=()=>{
      const decision=button.dataset.payrollDecision;
      formDialog(button.textContent,materialReason,
        form=>({status:decision,expected_revision:row.revision,reason:new FormData(form).get('reason').trim()}),
        '/api/payroll-approval-requests/'+encodeURIComponent(row.id)+'/decisions',
        `${row.reference} · ${financeRupiah(source.total_employer_cost)}\nKeputusan dan alasan tersimpan permanen; status sumber Mekari tidak berubah.`);
    });
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="payroll-approval-request" data-id="${e(requestId)}">Coba lagi</button>`;}
}
$('return-insights').onclick=showReturnInsights;

function showSizeDemandInsights() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('size-demand-insights','Analisis demand per ukuran',`<form id="size-demand-form" class="filter-form">
    <p class="hint">Bandingkan ukuran dalam produk dan warna yang sama. Sistem memakai demand neto dua periode serta stok tersedia saat ini untuk menunjukkan ukuran yang berisiko habis lebih dulu.</p>
    <div class="form-grid">
      ${field('as_of','Data demand sampai tanggal','date',`required value="${today}"`)}
      ${field('window_days','Panjang tiap periode (hari)','number','required min="7" max="90" step="1" value="28"')}
      ${field('lookahead_days','Horizon risiko (hari)','number','required min="1" max="180" step="1" value="30"')}
      ${field('marketplace','Marketplace demand','text','maxlength="160" placeholder="Semua marketplace"')}
      <label class="full">Cari keluarga produk atau SKU<input name="query" type="search" maxlength="160" placeholder="Kode, nama, warna, atau ukuran"></label>
    </div>
    <div class="form-actions"><button class="primary" id="size-demand-submit" type="submit">Tampilkan analisis</button></div>
  </form><p id="size-demand-message" class="state" role="status" hidden></p><div id="size-demand-summary"></div><div id="size-demand-results"></div><button id="size-demand-more" type="button" hidden>Muat keluarga berikutnya</button>`);
  const version=epoch,form=$('size-demand-form'),submit=$('size-demand-submit');
  restoreAnalyticsFilters('size-demand-insights',form);
  let offset=0,generation=0;
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='size-demand-insights'&&request===analyticsRequest;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('size-demand-summary').replaceChildren();$('size-demand-results').replaceChildren();}
    const gen=generation,more=$('size-demand-more');
    submit.disabled=true;more.disabled=true;more.hidden=true;
    message('size-demand-message',offset?'Memuat keluarga berikutnya…':'Menghitung demand dan days of cover per ukuran…');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/size-demand-insights?'+params);
      if(!current()||gen!==generation)return;
      message('size-demand-message','');
      if(!offset)$('size-demand-summary').innerHTML=`<p class="form-info">Riwayat ${date(report.history_start)}–${date(report.as_of)}<br>${n(report.summary.families)} keluarga · ${n(report.summary.size_variants)} ukuran · ${n(report.summary.families_out_of_stock+report.summary.families_within_lookahead)} keluarga perlu perhatian dalam ${n(report.lookahead_days)} hari</p><p class="hint">Filter marketplace hanya membatasi demand. Stok memakai seluruh inventori internal saat laporan dimuat. “Pemimpin konsisten” berarti demand neto ukuran tersebut berada di peringkat pertama pada kedua periode, bukan bukti stockout historis.</p>`;
      const statuses={out_of_stock:'Stok tersedia sudah habis',within_lookahead:'Berisiko dalam horizon',later:'Risiko di luar horizon',no_observed_demand:'Belum ada demand teramati'};
      const html=report.items.map(family=>{
        const first=family.first_stockout_sizes.join(', '),consistent=family.consistent_leader_sizes.join(', ');
        const sizes=family.sizes.map(row=>`<div data-size-demand-sku="${e(row.sku)}"><dt>${e(row.size)} · ${e(row.sku)}</dt><dd>Stok tersedia ${n(row.available_quantity)} pcs · demand lama ${n(row.previous_net_demand)} pcs · demand terbaru ${n(row.recent_net_demand)} pcs${row.days_of_cover===null?' · days of cover belum tersedia':' · '+n(Number(row.days_of_cover))+' hari'+(row.projected_stockout_date?' · estimasi '+date(row.projected_stockout_date):'')}${row.consistent_demand_leader?' · pemimpin demand konsisten':''}</dd></div>`).join('');
        return `<article class="material-event" data-size-demand-family="${e(family.name)}"><h3>${e(family.name)}${family.color?' · '+e(family.color):''}</h3><p class="status-label ${family.risk_status==='out_of_stock'||family.risk_status==='within_lookahead'?'late':'done'}">${e(statuses[family.risk_status])}</p>${first?`<p><strong>Risiko habis lebih dulu: ${e(first)}</strong>${family.first_stockout_date?' · '+date(family.first_stockout_date):''}</p>`:''}${consistent?`<p>Pemimpin demand konsisten: ${e(consistent)}</p>`:''}<dl class="requirement-values">${sizes}</dl></article>`;
      }).join('');
      appendRows('size-demand-results',html);
      if(!offset&&!report.items.length)$('size-demand-results').innerHTML='<p class="state">Belum ada keluarga produk dengan minimal dua ukuran yang cocok dengan filter.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat keluarga berikutnya';
    }catch(error){
      if(current()&&gen===generation){
        message('size-demand-message',error.message,true);
        $('size-demand-message').insertAdjacentHTML('beforeend','<br><button id="size-demand-retry" type="button">Coba lagi</button>');
        $('size-demand-retry').onclick=()=>load();
      }
    }finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('size-demand-insights',form);load(true);};
  $('size-demand-more').onclick=()=>load();
}
$('size-demand-insights').onclick=showSizeDemandInsights;

function showDeadStockInsights() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('dead-stock-insights','Analisis dead stock',`<form id="dead-stock-form" class="filter-form">
    <p class="hint">Kandidat dead stock adalah stok sellable yang masih tersedia, umur lot tertuanya sudah melewati ambang, dan tidak mempunyai demand neto dalam periode yang sama.</p>
    <div class="form-grid">
      ${field('as_of','Data demand sampai tanggal','date',`required value="${today}"`)}
      ${field('inactivity_days','Ambang tanpa demand (hari)','number','required min="7" max="730" step="1" value="90"')}
      ${field('marketplace','Marketplace demand','text','maxlength="160" placeholder="Semua marketplace"')}
      <label>Status<select name="status"><option value="dead_stock_candidate">Kandidat dead stock</option><option value="aging_no_sales">Stok baru tanpa penjualan</option><option value="moving">Masih bergerak</option><option value="all">Semua stok tersedia</option></select></label>
      <label class="full">Cari SKU atau produk<input name="query" type="search" maxlength="160" placeholder="Kode, nama, warna, atau ukuran"></label>
    </div>
    <div class="form-actions"><button class="primary" id="dead-stock-submit" type="submit">Tampilkan analisis</button></div>
  </form><p id="dead-stock-message" class="state" role="status" hidden></p><div id="dead-stock-summary"></div><div id="dead-stock-results"></div><button id="dead-stock-more" type="button" hidden>Muat SKU berikutnya</button>`);
  const version=epoch,form=$('dead-stock-form'),submit=$('dead-stock-submit');
  restoreAnalyticsFilters('dead-stock-insights',form);
  let offset=0,generation=0;
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='dead-stock-insights'&&request===analyticsRequest;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('dead-stock-summary').replaceChildren();$('dead-stock-results').replaceChildren();}
    const gen=generation,more=$('dead-stock-more');
    submit.disabled=true;more.disabled=true;more.hidden=true;
    message('dead-stock-message',offset?'Memuat SKU berikutnya…':'Memeriksa umur stok dan demand neto…');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/dead-stock-insights?'+params);
      if(!current()||gen!==generation)return;
      message('dead-stock-message','');
      if(!offset)$('dead-stock-summary').innerHTML=`<p class="form-info">Periode demand ${date(report.period_start)}–${date(report.as_of)}<br>${n(report.summary.dead_stock_candidates)} kandidat · ${n(report.summary.dead_stock_quantity)} pcs tersedia · ${n(report.summary.aging_no_sales_products)} SKU masih terlalu baru untuk disebut dead stock</p><p class="hint">Filter marketplace hanya membatasi demand. Stok dan umur lot memakai posisi inventori internal saat laporan dimuat. Nilai rupiah belum dihitung karena valuasi stok per lot belum tersedia.</p>`;
      const statuses={dead_stock_candidate:'Kandidat dead stock',aging_no_sales:'Stok baru tanpa penjualan',moving:'Masih bergerak'};
      const html=report.items.map(row=>`<article class="material-event" data-dead-stock-sku="${e(row.sku)}"><h3>${e(row.sku)} · ${n(row.available_quantity)} pcs tersedia</h3><p>${e(row.name)}${[row.color,row.size].filter(Boolean).length?' · '+e([row.color,row.size].filter(Boolean).join(' / ')):''}</p><p class="status-label ${row.status==='dead_stock_candidate'?'late':'done'}">${e(statuses[row.status])}</p><dl class="requirement-values"><div><dt>Umur lot tertua</dt><dd>${n(row.oldest_stock_age_days)} hari</dd></div><div><dt>Demand neto periode</dt><dd>${n(row.recent_net_demand)} pcs</dd></div><div><dt>Shipment / retur</dt><dd>${n(row.recent_shipped_quantity)} / ${n(row.recent_returned_quantity)} pcs</dd></div><div><dt>Rate demand</dt><dd>${n(Number(row.recent_daily_rate))} pcs/hari</dd></div><div><dt>Days of cover</dt><dd>${row.days_of_cover===null?'Belum tersedia':n(Number(row.days_of_cover))+' hari'}</dd></div><div><dt>Lot aktif</dt><dd>${n(row.active_lot_count)}</dd></div></dl><p class="hint">${row.oldest_available_receipt_date?'Lot tersedia sejak '+date(row.oldest_available_receipt_date):'Tanggal lot belum tersedia'}${row.newest_available_receipt_date&&row.newest_available_receipt_date!==row.oldest_available_receipt_date?' · lot terbaru '+date(row.newest_available_receipt_date):''}<br>${row.last_net_sale_date?'Penjualan neto terakhir '+date(row.last_net_sale_date)+' · '+n(row.days_since_last_net_sale)+' hari lalu':'Belum ada penjualan neto aktif sampai tanggal laporan.'}</p></article>`).join('');
      appendRows('dead-stock-results',html);
      if(!offset&&!report.items.length)$('dead-stock-results').innerHTML='<p class="state">Tidak ada SKU yang cocok dengan status dan filter ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat SKU berikutnya';
    }catch(error){
      if(current()&&gen===generation){
        message('dead-stock-message',error.message,true);
        $('dead-stock-message').insertAdjacentHTML('beforeend','<br><button id="dead-stock-retry" type="button">Coba lagi</button>');
        $('dead-stock-retry').onclick=()=>load();
      }
    }finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('dead-stock-insights',form);load(true);};
  $('dead-stock-more').onclick=()=>load();
}
$('dead-stock-insights').onclick=showDeadStockInsights;

function showStockAdjustmentInsights() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('stock-adjustment-insights','Audit adjustment stok',`<form id="stock-adjustment-insights-form" class="filter-form">
    <p class="hint">Adjustment ditandai bila jumlah atau porsinya terhadap penerimaan melewati ambang, berulang pada SKU dan bucket yang sama, atau sudah dikoreksi.</p>
    <div class="form-grid">
      ${field('as_of','Data sampai tanggal','date',`required value="${today}"`)}
      ${field('window_days','Panjang periode (hari)','number','required min="7" max="365" step="1" value="30"')}
      ${field('quantity_threshold','Ambang jumlah (pcs)','number','required min="1" max="1000000000" step="1" value="5"')}
      ${field('percentage_threshold','Ambang porsi penerimaan (%)','number','required min="1" max="100" step="1" value="20"')}
      ${field('repeat_threshold','Ambang pengulangan','number','required min="2" max="100" step="1" value="3"')}
      <label>Klasifikasi<select name="classification"><option value="flagged">Perlu diperiksa</option><option value="high">Risiko tinggi</option><option value="review">Perlu tinjauan</option><option value="normal">Normal</option><option value="all">Semua adjustment</option></select></label>
      <label>Sumber<select name="source"><option value="all">Semua sumber</option><option value="manual">Manual</option><option value="stock_count">Stock opname</option></select></label>
      <label>Status catatan<select name="record_status"><option value="all">Aktif dan dikoreksi</option><option value="active">Aktif</option><option value="corrected">Sudah dikoreksi</option></select></label>
      <label>Status stok<select name="stock_status"><option value="all">Semua status stok</option><option value="sellable">Sellable</option><option value="hold">Hold</option><option value="damaged">Damaged</option></select></label>
      ${field('location','Lokasi stok','text','maxlength="160" placeholder="Semua lokasi"')}
      <label class="full">Cari adjustment atau SKU<input name="query" type="search" maxlength="160" placeholder="Referensi, SKU, produk, order, atau alasan"></label>
    </div>
    <div class="form-actions"><button class="primary" id="stock-adjustment-insights-submit" type="submit">Tampilkan audit</button></div>
  </form><p id="stock-adjustment-insights-message" class="state" role="status" hidden></p><div id="stock-adjustment-insights-summary"></div><div id="stock-adjustment-insights-results"></div><button id="stock-adjustment-insights-more" type="button" hidden>Muat adjustment berikutnya</button>`);
  const version=epoch,form=$('stock-adjustment-insights-form'),submit=$('stock-adjustment-insights-submit');
  restoreAnalyticsFilters('stock-adjustment-insights',form);
  let offset=0,generation=0;
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='stock-adjustment-insights'&&request===analyticsRequest;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('stock-adjustment-insights-summary').replaceChildren();$('stock-adjustment-insights-results').replaceChildren();}
    const gen=generation,more=$('stock-adjustment-insights-more');
    submit.disabled=true;more.disabled=true;more.hidden=true;
    message('stock-adjustment-insights-message',offset?'Memuat adjustment berikutnya…':'Memeriksa pola adjustment…');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/stock-adjustment-insights?'+params);
      if(!current()||gen!==generation)return;
      message('stock-adjustment-insights-message','');
      if(!offset)$('stock-adjustment-insights-summary').innerHTML=`<p class="form-info">Periode ${date(report.period_start)}–${date(report.as_of)}<br>${n(report.summary.flagged_adjustments)} perlu diperiksa · ${n(report.summary.high_risk_adjustments)} risiko tinggi · ${n(report.summary.flagged_absolute_quantity)} pcs volume absolut ditandai</p><p class="hint">Sinyal adalah alat audit, bukan bukti kehilangan stok. Status koreksi memakai posisi catatan saat laporan dimuat.</p>`;
      const classes={high:'Risiko tinggi',review:'Perlu tinjauan',normal:'Normal'};
      const sources={manual:'Manual',stock_count:'Stock opname'};
      const flags={large_quantity:'Jumlah melewati ambang',large_receipt_share:'Porsi penerimaan melewati ambang',repeated_bucket:'Berulang pada SKU dan bucket yang sama',corrected_record:'Catatan sudah dikoreksi'};
      const html=report.items.map(row=>`<article class="material-event" data-stock-adjustment-insight="${e(row.id)}"><p class="status-label ${row.classification==='high'?'late':row.classification==='normal'?'done':''}">${e(classes[row.classification])}</p><h3>${e(row.reference)} · ${row.quantity_delta>0?'+':''}${n(row.quantity_delta)} pcs</h3><p>${e(row.sku)} · ${e(row.product_name)}${[row.color,row.size].filter(Boolean).length?' · '+e([row.color,row.size].filter(Boolean).join(' / ')):''}</p><dl class="requirement-values"><div><dt>Porsi penerimaan</dt><dd>${e(row.receipt_share_percent)}%</dd></div><div><dt>Pengulangan bucket</dt><dd>${n(row.bucket_adjustment_count)} catatan</dd></div><div><dt>Volume bucket</dt><dd>${n(row.bucket_absolute_quantity)} pcs</dd></div><div><dt>Sumber</dt><dd>${e(sources[row.source])}</dd></div><div><dt>Status catatan</dt><dd>${row.record_status==='active'?'Aktif':'Sudah dikoreksi'}</dd></div><div><dt>Tanggal</dt><dd>${date(row.adjusted_date)}</dd></div></dl><p>${row.flags.length?'Sinyal: '+e(row.flags.map(flag=>flags[flag]).join(' · ')):'Tidak melewati ambang audit.'}</p><p class="hint">${e(row.location)} · ${e(warehouseStatus[row.stock_status])}<br>Penerimaan ${e(row.receipt_reference)} · order ${e(row.order_reference)} · dicatat ${e(row.actor_name)}</p><button data-action="finished-goods-adjustment" data-id="${e(row.id)}">Buka adjustment</button></article>`).join('');
      appendRows('stock-adjustment-insights-results',html);
      if(!offset&&!report.items.length)$('stock-adjustment-insights-results').innerHTML='<p class="state">Tidak ada adjustment yang cocok dengan klasifikasi dan filter ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat adjustment berikutnya';
    }catch(error){
      if(current()&&gen===generation){
        message('stock-adjustment-insights-message',error.message,true);
        $('stock-adjustment-insights-message').insertAdjacentHTML('beforeend','<br><button id="stock-adjustment-insights-retry" type="button">Coba lagi</button>');
        $('stock-adjustment-insights-retry').onclick=()=>load();
      }
    }finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('stock-adjustment-insights',form);load(true);};
  $('stock-adjustment-insights-more').onclick=()=>load();
}
$('stock-adjustment-insights').onclick=showStockAdjustmentInsights;

function showSupplierPerformanceInsights() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('supplier-performance-insights','Kinerja supplier',`<form id="supplier-performance-form" class="filter-form">
    <p class="hint">PO dikelompokkan menurut supplier dan tanggal perkiraan datang. Kedatangan aktif pertama mengukur ketepatan awal; hasil QC tetap dipisahkan per satuan bahan.</p>
    <div class="form-grid">
      ${field('as_of','Data sampai tanggal','date',`required value="${today}"`)}
      ${field('window_days','Periode jatuh tempo PO (hari)','number','required min="7" max="730" step="1" value="90"')}
      <label>Status<select name="status"><option value="attention">Perlu perhatian</option><option value="healthy">Sehat</option><option value="all">Semua supplier</option></select></label>
      <label class="full">Cari supplier atau PO<input name="query" type="search" maxlength="160" placeholder="Kode, nama supplier, atau referensi PO"></label>
    </div>
    <div class="form-actions"><button class="primary" id="supplier-performance-submit" type="submit">Tampilkan kinerja</button></div>
  </form><p id="supplier-performance-message" class="state" role="status" hidden></p><div id="supplier-performance-summary"></div><div id="supplier-performance-results"></div><button id="supplier-performance-more" type="button" hidden>Muat supplier berikutnya</button>`);
  const version=epoch,form=$('supplier-performance-form'),submit=$('supplier-performance-submit');
  restoreAnalyticsFilters('supplier-performance-insights',form);
  let offset=0,generation=0;
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='supplier-performance-insights'&&request===analyticsRequest;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('supplier-performance-summary').replaceChildren();$('supplier-performance-results').replaceChildren();}
    const gen=generation,more=$('supplier-performance-more');
    submit.disabled=true;more.disabled=true;more.hidden=true;
    message('supplier-performance-message',offset?'Memuat supplier berikutnya…':'Menghitung ketepatan kedatangan dan hasil QC…');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/supplier-performance-insights?'+params);
      if(!current()||gen!==generation)return;
      message('supplier-performance-message','');
      if(!offset)$('supplier-performance-summary').innerHTML=`<p class="form-info">PO jatuh tempo ${date(report.period_start)}–${date(report.as_of)}<br>${n(report.summary.attention_suppliers)} supplier perlu perhatian · ${n(report.summary.overdue_no_arrival)} PO terlambat tanpa kedatangan · ${n(report.summary.late_first_arrivals)} kedatangan awal terlambat</p><p class="hint">Kuantitas bahan tidak dijumlahkan lintas satuan. Keputusan kualitas hanya memakai kedatangan QC aktif.</p>`;
      const flagLabels={overdue_no_arrival:'PO terlambat tanpa kedatangan',late_first_arrival:'Kedatangan awal terlambat',overdue_incomplete:'PO lewat jadwal belum lengkap',closed_shortfall:'PO ditutup dengan kekurangan',quality_reject:'Ada bahan reject',quality_hold:'Ada bahan masih hold'};
      const fulfillment={received:'Diterima lengkap',partial:'Diterima sebagian',pending:'Belum diterima'};
      const quantityList=rows=>rows.map(unit=>`${n(Number(unit.quantity))} ${e(unit.unit)}`).join(' · ')||'Belum ada';
      const delay=row=>row.first_arrival_delay_days===null?'Belum ada kedatangan aktif':row.first_arrival_delay_days>0?`${n(row.first_arrival_delay_days)} hari terlambat`:row.first_arrival_delay_days<0?`${n(Math.abs(row.first_arrival_delay_days))} hari lebih awal`:'Tepat pada tanggal perkiraan';
      const html=report.items.map(row=>`<article class="material-event" data-supplier-performance="${e(row.supplier_id)}"><p class="status-label ${row.status==='attention'?'late':'done'}">${row.status==='attention'?'Perlu perhatian':'Sehat'}</p><h3>${e(row.supplier_code)} · ${e(row.supplier_name)}</h3><dl class="requirement-values"><div><dt>PO periode</dt><dd>${n(row.purchase_order_count)}</dd></div><div><dt>Tepat waktu</dt><dd>${n(row.on_time_first_arrivals)}</dd></div><div><dt>Terlambat datang</dt><dd>${n(row.late_first_arrivals)}</dd></div><div><dt>Terlambat tanpa kedatangan</dt><dd>${n(row.overdue_no_arrival)}</dd></div><div><dt>Belum lengkap lewat jadwal</dt><dd>${n(row.overdue_incomplete_purchase_orders)}</dd></div><div><dt>Kekurangan saat ditutup</dt><dd>${n(row.closed_shortfall_purchase_orders)}</dd></div></dl><p>${row.flags.length?'Sinyal: '+e(row.flags.map(flag=>flagLabels[flag]).join(' · ')):'Tidak ada sinyal yang memerlukan perhatian.'}</p><p class="hint">Dipesan ${quantityList(row.ordered_by_unit)}<br>Diterima layak pakai ${quantityList(row.received_by_unit)}</p>${row.quality_by_unit.map(unit=>`<article class="material-event"><strong>QC ${e(unit.unit)} · ${n(unit.intake_count)} kedatangan</strong><p>Datang ${n(Number(unit.arrived))} · layak ${n(Number(unit.accepted))} · reject ${n(Number(unit.rejected))} · hold ${n(Number(unit.held))}</p><p class="hint">Usable ${e(unit.usable_rate)}% · reject ${e(unit.reject_rate)}%</p></article>`).join('')||'<p class="hint">Belum ada kedatangan melalui QC pada PO periode ini.</p>'}<h4>PO dalam periode</h4>${row.purchase_orders.map(po=>`<article class="material-event"><strong>${e(po.reference)} · ${e(fulfillment[po.fulfillment])}</strong><p>Perkiraan ${date(po.expected_date)} · ${e(delay(po))}</p><button data-action="purchase-order" data-id="${e(po.id)}">Buka PO</button></article>`).join('')}</article>`).join('');
      appendRows('supplier-performance-results',html);
      if(!offset&&!report.items.length)$('supplier-performance-results').innerHTML='<p class="state">Tidak ada supplier yang cocok dengan status dan filter periode ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat supplier berikutnya';
    }catch(error){
      if(current()&&gen===generation){
        message('supplier-performance-message',error.message,true);
        $('supplier-performance-message').insertAdjacentHTML('beforeend','<br><button id="supplier-performance-retry" type="button">Coba lagi</button>');
        $('supplier-performance-retry').onclick=()=>load();
      }
    }finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('supplier-performance-insights',form);load(true);};
  $('supplier-performance-more').onclick=()=>load();
}
$('supplier-performance-insights').onclick=showSupplierPerformanceInsights;

function showMaterialPriceInsights() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('material-price-insights','Pergerakan harga bahan',`<form id="material-price-form" class="filter-form">
    <p class="hint">Harga dibandingkan dari PO approved untuk material dan supplier yang sama. Tanggal pencatatan PO dipakai agar perubahan harga tidak bergantung pada jadwal kedatangan.</p>
    <div class="form-grid">
      ${field('as_of','Data sampai tanggal','date',`required value="${today}"`)}
      ${field('window_days','Periode pencatatan PO (hari)','number','required min="7" max="730" step="1" value="90"')}
      <label>Status perubahan<select name="status"><option value="changed">Harga berubah</option><option value="increased">Naik</option><option value="decreased">Turun</option><option value="stable">Tetap</option><option value="single_observation">Baru satu harga</option><option value="all">Semua status</option></select></label>
      <label class="full">Cari bahan, supplier, atau PO<input name="query" type="search" maxlength="160" placeholder="Kode, nama, atau referensi PO"></label>
    </div>
    <div class="form-actions"><button class="primary" id="material-price-submit" type="submit">Tampilkan harga</button></div>
  </form><p id="material-price-message" class="state" role="status" hidden></p><div id="material-price-summary"></div><div id="material-price-results"></div><button id="material-price-more" type="button" hidden>Muat harga berikutnya</button>`);
  const version=epoch,form=$('material-price-form'),submit=$('material-price-submit');
  restoreAnalyticsFilters('material-price-insights',form);
  let offset=0,generation=0;
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='material-price-insights'&&request===analyticsRequest;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('material-price-summary').replaceChildren();$('material-price-results').replaceChildren();}
    const gen=generation,more=$('material-price-more');
    submit.disabled=true;more.disabled=true;more.hidden=true;
    message('material-price-message',offset?'Memuat pergerakan harga berikutnya…':'Membandingkan harga dari PO approved…');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/material-price-insights?'+params);
      if(!current()||gen!==generation)return;
      message('material-price-message','');
      if(!offset)$('material-price-summary').innerHTML=`<p class="form-info">PO tercatat ${date(report.period_start)}–${date(report.as_of)}<br>${n(report.summary.changed_series)} dari ${n(report.summary.series)} pasangan bahan dan supplier berubah · ${n(report.summary.increased_series)} naik · ${n(report.summary.decreased_series)} turun</p><p class="hint">Ringkasan mencakup hasil pencarian sebelum filter status. Harga supplier berbeda tidak dicampur menjadi satu tren.</p>`;
      const labels={increased:'Harga naik',decreased:'Harga turun',stable:'Harga tetap',single_observation:'Baru satu harga'};
      const price=value=>rupiah(value);
      const signedPrice=value=>`${Number(value)>0?'+':Number(value)<0?'-':''}${price(value.replace('-',''))}`;
      const movement=row=>row.status==='single_observation'?'Belum dapat dibandingkan':`${signedPrice(row.price_change)} · ${Number(row.price_change_percent)>0?'+':''}${e(row.price_change_percent)}%`;
      const html=report.items.map(row=>`<article class="material-event" data-material-price="${e(row.material_id)}:${e(row.supplier_id)}"><p class="status-label ${row.status==='increased'?'late':'done'}">${e(labels[row.status])}</p><h3>${e(row.material_code)} · ${e(row.material_name)}</h3><p>${e(row.supplier_code)} · ${e(row.supplier_name)}</p><dl class="requirement-values"><div><dt>Harga awal</dt><dd>${e(price(row.earliest_unit_price))} / ${e(row.unit)}</dd></div><div><dt>Harga terbaru</dt><dd>${e(price(row.latest_unit_price))} / ${e(row.unit)}</dd></div><div><dt>Perubahan</dt><dd>${movement(row)}</dd></div><div><dt>Harga minimum</dt><dd>${e(price(row.minimum_unit_price))}</dd></div><div><dt>Harga maksimum</dt><dd>${e(price(row.maximum_unit_price))}</dd></div><div><dt>Harga rata-rata</dt><dd>${e(price(row.average_unit_price))}</dd></div></dl><p class="hint">${n(row.observation_count)} harga PO · awal ${date(row.earliest_recorded_date)} · terbaru ${date(row.latest_recorded_date)}</p><h4>Riwayat harga PO</h4>${row.history.map(po=>`<article class="material-event"><strong>${e(po.purchase_order_reference)} · ${e(price(po.unit_price))} / ${e(row.unit)}</strong><p>Dicatat ${date(po.recorded_date)} · perkiraan datang ${date(po.expected_date)}</p><button data-action="purchase-order" data-id="${e(po.purchase_order_id)}">Buka PO</button></article>`).join('')}</article>`).join('');
      appendRows('material-price-results',html);
      if(!offset&&!report.items.length)$('material-price-results').innerHTML='<p class="state">Tidak ada pergerakan harga yang cocok dengan status dan filter periode ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat harga berikutnya';
    }catch(error){
      if(current()&&gen===generation){
        message('material-price-message',error.message,true);
        $('material-price-message').insertAdjacentHTML('beforeend','<br><button id="material-price-retry" type="button">Coba lagi</button>');
        $('material-price-retry').onclick=()=>load();
      }
    }finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('material-price-insights',form);load(true);};
  $('material-price-more').onclick=()=>load();
}
$('material-price-insights').onclick=showMaterialPriceInsights;

function showPurchaseCommitmentInsights() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('purchase-commitment-insights','Komitmen pembelian terbuka',`<form id="purchase-commitment-form" class="filter-form">
    <p class="hint">Nilai terbuka adalah nilai PO approved aktif yang belum menjadi penerimaan bahan layak pakai. PO pending, ditolak, dibatalkan, dan ditutup tidak masuk laporan.</p>
    <div class="form-grid">
      ${field('as_of','Hitung umur per tanggal','date',`required value="${today}"`)}
      ${field('due_soon_days','Batas segera jatuh tempo (hari)','number','required min="1" max="90" step="1" value="7"')}
      <label>Status jadwal<select name="status"><option value="open">Semua komitmen terbuka</option><option value="overdue">Terlambat</option><option value="due_soon">Segera jatuh tempo</option><option value="scheduled">Terjadwal</option><option value="fulfilled">Diterima lengkap, belum ditutup</option><option value="all">Semua PO aktif</option></select></label>
      <label class="full">Cari PO, PR, supplier, atau bahan<input name="query" type="search" maxlength="160" placeholder="Referensi, kode, atau nama"></label>
    </div>
    <div class="form-actions"><button class="primary" id="purchase-commitment-submit" type="submit">Tampilkan komitmen</button></div>
  </form><p id="purchase-commitment-message" class="state" role="status" hidden></p><div id="purchase-commitment-summary"></div><div id="purchase-commitment-results"></div><button id="purchase-commitment-more" type="button" hidden>Muat PO berikutnya</button>`);
  const version=epoch,form=$('purchase-commitment-form'),submit=$('purchase-commitment-submit');
  restoreAnalyticsFilters('purchase-commitment-insights',form);
  let offset=0,generation=0;
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='purchase-commitment-insights'&&request===analyticsRequest;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('purchase-commitment-summary').replaceChildren();$('purchase-commitment-results').replaceChildren();}
    const gen=generation,more=$('purchase-commitment-more');
    submit.disabled=true;more.disabled=true;more.hidden=true;
    message('purchase-commitment-message',offset?'Memuat PO berikutnya…':'Menghitung komitmen PO aktif…');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/purchase-commitment-insights?'+params);
      if(!current()||gen!==generation)return;
      message('purchase-commitment-message','');
      if(!offset)$('purchase-commitment-summary').innerHTML=`<p class="form-info">Posisi ${date(report.as_of)} · jatuh tempo dekat sampai ${date(report.due_soon_end)}<br>${n(report.summary.open_purchase_orders)} PO terbuka · ${n(report.summary.overdue_purchase_orders)} terlambat · komitmen ${e(rupiah(report.summary.open_commitment_value))}</p><p class="hint">Nilai penerimaan hanya memakai bahan layak pakai. Payment approved berarti siap dibayar dan belum membuktikan transfer bank.</p>`;
      const labels={overdue:'Terlambat',due_soon:'Segera jatuh tempo',scheduled:'Terjadwal',fulfilled:'Diterima lengkap, belum ditutup'};
      const schedule=row=>row.status==='overdue'?`${n(row.overdue_days)} hari terlambat`:row.status==='fulfilled'?'Komitmen penerimaan selesai':`Perkiraan datang ${date(row.expected_date)}`;
      const html=report.items.map(row=>`<article class="material-event" data-purchase-commitment="${e(row.purchase_order_id)}"><p class="status-label ${row.status==='overdue'?'late':'done'}">${e(labels[row.status])}</p><h3>${e(row.purchase_order_reference)} · ${e(row.supplier_code)}</h3><p>${e(row.supplier_name)}</p><dl class="requirement-values"><div><dt>Nilai PO</dt><dd>${e(rupiah(row.purchase_order_value))}</dd></div><div><dt>Diterima layak pakai</dt><dd>${e(rupiah(row.usable_received_value))}</dd></div><div><dt>Komitmen terbuka</dt><dd><strong>${e(rupiah(row.open_commitment_value))}</strong></dd></div><div><dt>Payment menunggu approval</dt><dd>${e(rupiah(row.payment_pending))}</dd></div><div><dt>Payment approved</dt><dd>${e(rupiah(row.payment_approved))}</dd></div><div><dt>Belum diajukan payment</dt><dd>${e(rupiah(row.payment_unrequested))}</dd></div></dl><p>${e(schedule(row))}</p><p class="hint">PO dicatat ${date(row.created_date)} · PR ${e(row.purchase_request_reference)}</p><h4>Rincian bahan</h4>${row.lines.map(line=>`<article class="material-event"><strong>${e(line.code)} · ${e(line.name)}</strong><p>Dipesan ${e(materialQty(line.ordered_quantity,line.unit))} · diterima layak ${e(materialQty(line.usable_received_quantity,line.unit))} · terbuka ${e(materialQty(line.open_quantity,line.unit))}</p><p class="hint">${e(rupiah(line.unit_price))}/${e(line.unit)} · komitmen ${e(rupiah(line.open_commitment_value))}</p></article>`).join('')}<button data-action="purchase-order" data-id="${e(row.purchase_order_id)}">Buka PO</button></article>`).join('');
      appendRows('purchase-commitment-results',html);
      if(!offset&&!report.items.length)$('purchase-commitment-results').innerHTML='<p class="state">Tidak ada komitmen PO yang cocok dengan status dan filter ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat PO berikutnya';
    }catch(error){
      if(current()&&gen===generation){
        message('purchase-commitment-message',error.message,true);
        $('purchase-commitment-message').insertAdjacentHTML('beforeend','<br><button id="purchase-commitment-retry" type="button">Coba lagi</button>');
        $('purchase-commitment-retry').onclick=()=>load();
      }
    }finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('purchase-commitment-insights',form);load(true);};
  $('purchase-commitment-more').onclick=()=>load();
}
$('purchase-commitment-insights').onclick=showPurchaseCommitmentInsights;

function showWipAgeingInsights() {
  const today=jakartaToday();
  const ownerOptions=(boardData?.owners||[]).map(owner=>option(owner.id,
    owner.name+(owner.active?'':' (akun nonaktif)'))).join('');
  const request=activateAnalyticsReport('wip-ageing-insights','WIP ageing & sinyal hambatan',`<form id="wip-ageing-form" class="filter-form">
    <p class="hint">Umur dihitung sejak movement produksi terakhir per order, atau sejak order dibuat bila belum pernah bergerak. Posisi tahap memakai saldo ledger saat ini.</p>
    <div class="form-grid">
      ${field('as_of','Posisi per tanggal','date',`required value="${today}"`)}
      ${field('idle_days','Batas tidak bergerak (hari)','number','required min="1" max="365" step="1" value="7"')}
      <label>Status perhatian<select name="status"><option value="attention">Perlu perhatian</option><option value="stalled">Tidak bergerak</option><option value="overdue">Lewat tenggat</option><option value="blocked">Ada kendala</option><option value="rework">Ada rework</option><option value="moving">Bergerak tanpa sinyal</option><option value="all">Semua order aktif</option></select></label>
      <label>Posisi tahap<select name="stage"><option value="all">Semua tahap aktif</option>${['planned','cutting','sewing','finishing','qc','rework'].map(value=>option(value,labels[value])).join('')}</select></label>
      <label>PIC order<select name="owner_id"><option value="">Semua PIC</option>${ownerOptions}</select></label>
      <label class="full">Cari order, PIC, SKU, produk, atau kendala<input name="query" type="search" maxlength="160" placeholder="Referensi, nama, atau isi kendala"></label>
    </div>
    <div class="form-actions"><button class="primary" id="wip-ageing-submit" type="submit">Tampilkan WIP</button></div>
  </form><p id="wip-ageing-message" class="state" role="status" hidden></p><div id="wip-ageing-summary"></div><div id="wip-ageing-stages"></div><div id="wip-ageing-results"></div><button id="wip-ageing-more" type="button" hidden>Muat order berikutnya</button>`);
  const version=epoch,form=$('wip-ageing-form'),submit=$('wip-ageing-submit');
  restoreAnalyticsFilters('wip-ageing-insights',form);
  let offset=0,generation=0;
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='wip-ageing-insights'&&request===analyticsRequest;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('wip-ageing-summary').replaceChildren();$('wip-ageing-stages').replaceChildren();$('wip-ageing-results').replaceChildren();}
    const gen=generation,more=$('wip-ageing-more');
    submit.disabled=true;more.disabled=true;more.hidden=true;
    message('wip-ageing-message',offset?'Memuat order berikutnya…':'Membaca posisi dan aktivitas WIP…');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/wip-ageing-insights?'+params);
      if(!current()||gen!==generation)return;
      message('wip-ageing-message','');
      if(!offset){
        const signal=report.summary.bottleneck_signal_stage?labels[report.summary.bottleneck_signal_stage]:'Belum ada';
        $('wip-ageing-summary').innerHTML=`<p class="form-info">Umur dihitung hingga ${date(report.as_of)} · batas ${n(report.idle_days)} hari<br>${n(report.summary.active_orders)} order aktif · ${n(report.summary.attention_orders)} perlu perhatian · ${n(report.summary.stalled_quantity)} pcs tidak bergerak<br>Sinyal hambatan terbesar: <strong>${e(signal)}</strong></p><p class="hint">Sinyal memakai saldo pada order yang melewati batas tidak bergerak. Kapasitas target belum dihitung karena master line, jam kerja, dan kalender kapasitas belum tersedia.</p>`;
        $('wip-ageing-stages').innerHTML=`<h3>Posisi per tahap</h3><dl class="requirement-values">${report.stages.filter(row=>row.quantity).map(row=>`<div><dt>${e(labels[row.stage])}</dt><dd>${n(row.quantity)} pcs</dd><small>${n(row.orders)} order · ${n(row.stalled_quantity)} pcs tidak bergerak</small></div>`).join('')}</dl>`;
      }
      const flagLabels={overdue:'Lewat tenggat',blocked:'Ada kendala',stalled:'Tidak bergerak',rework:'Ada rework'};
      const html=report.items.map(row=>{
        const flags=row.flags.length?row.flags.map(flag=>`<span class="status-label late">${e(flagLabels[flag])}</span>`).join(' '):'<span class="status-label done">Bergerak</span>';
        const positions=row.positions.map(position=>`${e(labels[position.stage])} ${n(position.quantity)} pcs`).join(' · ');
        const products=row.products.map(product=>`<p>${e(product.sku)} · ${e(product.name)}${product.size?` · ${e(product.size)}`:''}${product.color?` · ${e(product.color)}`:''} · ${n(product.quantity)} pcs</p>`).join('');
        const blockers=row.open_issues.length?`<h4>Kendala terbuka</h4>${row.open_issues.map(issue=>`<p class="reason">${e(labels[issue.stage])} · ${e(issue.description)} · PIC ${e(issue.owner_name)}</p>`).join('')}`:'';
        const after=row.activity_after_as_of?' · ada movement setelah tanggal posisi':'';
        const late=row.overdue_days?` · ${n(row.overdue_days)} hari lewat tenggat`:'';
        return `<article class="material-event" data-wip-ageing="${e(row.order_id)}"><div class="issue-heading"><h3>${e(row.reference)} · ${e(row.title)}</h3><div>${flags}</div></div><p>${e(row.owner_name)} · tenggat ${date(row.due_date)}</p><dl class="requirement-values"><div><dt>Aktif</dt><dd>${n(row.active_quantity)} pcs</dd></div><div><dt>Belum cutting</dt><dd>${n(row.planned_quantity)} pcs</dd></div><div><dt>Dalam proses</dt><dd>${n(row.in_process_quantity)} pcs</dd></div><div><dt>Tanpa movement</dt><dd><strong>${n(row.inactive_days)} hari</strong></dd></div><div><dt>Kendala terbuka</dt><dd>${n(row.open_issue_count)}</dd></div><div><dt>Rework</dt><dd>${n(row.rework_quantity)} pcs</dd></div></dl><p><strong>Posisi:</strong> ${positions}</p><p class="hint">Aktivitas produksi terakhir ${date(row.latest_activity_date)} · ${e(row.activity_basis==='order_created'?'belum ada movement':'movement terakhir')}${after}${late}</p><h4>SKU</h4>${products}${blockers}<button data-action="detail" data-id="${e(row.order_id)}">Buka order</button></article>`;
      }).join('');
      appendRows('wip-ageing-results',html);
      if(!offset&&!report.items.length)$('wip-ageing-results').innerHTML='<p class="state">Tidak ada order aktif yang cocok dengan status dan filter ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat order berikutnya';
    }catch(error){
      if(current()&&gen===generation){
        message('wip-ageing-message',error.message,true);
        $('wip-ageing-message').insertAdjacentHTML('beforeend','<br><button id="wip-ageing-retry" type="button">Coba lagi</button>');
        $('wip-ageing-retry').onclick=()=>load();
      }
    }finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('wip-ageing-insights',form);load(true);};
  $('wip-ageing-more').onclick=()=>load();
}
$('wip-ageing-insights').onclick=showWipAgeingInsights;

async function capacityWorkCenterForm(workCenterId=null) {
  if(guardPending())return;
  const version=epoch;
  try{
  let current=null;
  if(workCenterId){
    const centers=await allRows('/api/work-centers');
    if(version!==epoch)return;
    current=centers.find(row=>row.id===workCenterId);
    if(!current)return notify('Work center tidak ditemukan.');
  }
  const stageOptions=['cutting','sewing','finishing','qc','rework'].map(value=>option(value,labels[value])).join('');
  if(current){
    formDialog('Ubah work center',field('name','Nama work center','text','required maxlength="160"')+
      field('daily_minutes','Kapasitas hari kerja (menit)','number','required min="1" max="100000" step="1"')+
      '<label>Status<select name="active"><option value="true">Aktif</option><option value="false">Nonaktif</option></select></label>'+
      '<label class="full">Alasan perubahan<textarea name="reason" required maxlength="1000"></textarea></label>',form=>{
        const data=new FormData(form);return {expected_revision:current.revision,name:data.get('name').trim(),
          daily_minutes:Number(data.get('daily_minutes')),active:data.get('active')==='true',reason:data.get('reason').trim()};
      },`/api/work-centers/${encodeURIComponent(current.id)}/changes`,`${current.code} · ${labels[current.stage]} · revisi ${current.revision}`);
    const form=$('action-form');form.elements.name.value=current.name;form.elements.daily_minutes.value=current.daily_minutes;
    form.elements.active.value=String(Boolean(current.active));
  }else{
    formDialog('Tambah work center',field('code','Kode work center','text','required maxlength="40"')+
      field('name','Nama work center','text','required maxlength="160"')+
      `<label>Tahap<select name="stage">${stageOptions}</select></label>`+
      field('daily_minutes','Kapasitas hari kerja (menit)','number','required min="1" max="100000" step="1" value="480"')+
      '<label class="full">Dasar kapasitas<textarea name="reason" required maxlength="1000"></textarea></label>',form=>{
        const data=new FormData(form);return {code:data.get('code').trim(),name:data.get('name').trim(),stage:data.get('stage'),
          daily_minutes:Number(data.get('daily_minutes')),reason:data.get('reason').trim()};
      },'/api/work-centers','Kapasitas harian berlaku untuk Senin sampai Jumat. Sabtu dan Minggu nol kecuali diberi override kalender.');
  }
  }catch(error){if(version===epoch)notify(error.message);}
}

async function capacityRoutingStandardForm(productId,stage) {
  if(guardPending())return;
  const version=epoch;
  try{
  const [standard,centers]=await Promise.all([
    api.get(`/api/products/${encodeURIComponent(productId)}/routing-standards/${stage}`),
    allRows('/api/work-centers',{status:'active'})
  ]);
  if(version!==epoch)return;
  const available=centers.filter(row=>row.stage===stage);
  if(!available.length)return notify(`Tambahkan work center ${labels[stage]} yang aktif terlebih dahulu.`);
  formDialog('Standar waktu SKU',`<p class="full"><strong>${e(standard.sku)} · ${e(standard.name)}</strong></p>
    <label>Work center<select name="work_center_id">${available.map(row=>option(row.id,`${row.code} · ${row.name}`)).join('')}</select></label>`+
    field('minutes_per_unit','Menit per pcs','number','required min="0.001" max="100000" step="0.001"')+
    '<label class="full">Dasar standar waktu<textarea name="reason" required maxlength="1000"></textarea></label>',form=>{
      const data=new FormData(form);return {expected_revision:standard.revision,work_center_id:data.get('work_center_id'),
        minutes_per_unit:data.get('minutes_per_unit'),reason:data.get('reason').trim()};
    },`/api/products/${encodeURIComponent(productId)}/routing-standards/${stage}`,
    `${labels[stage]} · revisi ${standard.revision}. Beban dihitung dari saldo tahap aktif dan sisa rute produksi.`);
  const form=$('action-form');
  if(standard.work_center_id)form.elements.work_center_id.value=standard.work_center_id;
  if(standard.minutes_per_unit)form.elements.minutes_per_unit.value=standard.minutes_per_unit;
  }catch(error){if(version===epoch)notify(error.message);}
}

async function capacityCalendarForm(workCenterId,workDate) {
  if(guardPending())return;
  const version=epoch;
  try{
  const calendar=await api.get(`/api/work-centers/${encodeURIComponent(workCenterId)}/calendar?`+
    new URLSearchParams({start_date:workDate,end_date:workDate}));
  if(version!==epoch)return;
  const current=calendar.items[0];
  formDialog('Override kalender kapasitas',field('work_date','Tanggal kerja','date',`required readonly value="${e(workDate)}"`)+
    field('available_minutes','Kapasitas tersedia (menit)','number',`required min="0" max="100000" step="1" value="${e(current?.available_minutes??calendar.work_center.daily_minutes)}"`)+
    '<label class="full">Alasan override<textarea name="reason" required maxlength="1000"></textarea></label>',form=>{
      const data=new FormData(form);return {work_date:data.get('work_date'),expected_revision:current?.revision||0,
        available_minutes:Number(data.get('available_minutes')),reason:data.get('reason').trim()};
    },`/api/work-centers/${encodeURIComponent(workCenterId)}/calendar`,
    `${calendar.work_center.code} · ${calendar.work_center.name}. Isi 0 untuk libur atau isi menit tambahan untuk lembur.`);
  }catch(error){if(version===epoch)notify(error.message);}
}

const workforceStatusLabels={present:'Hadir',leave:'Cuti',absent:'Absen',unrecorded:'Belum dicatat'};

async function workforcePage(path,params={}) {
  let items=[],page;
  do{
    page=await api.get(path+'?'+new URLSearchParams({...params,limit:500,offset:items.length}));
    items.push(...page.items);
  }while(page.items.length&&items.length<page.total);
  return {...page,items};
}

// People sebagai halaman workspace: roster, filter tanggal/status/pencarian,
// dan ringkasan harian ada di permukaan halaman. Catat/koreksi kehadiran, riwayat,
// dan permintaan cuti/lembur tetap dialog terfokus.
function showPeople() {
  activateWorkspace('workforce'); selected = null;
  $('new-employee').hidden = user.role !== 'admin';
  workforceFilters.work_date = workforceFilters.work_date || jakartaToday();
  const form = $('workforce-filter');
  form.elements.work_date.max = jakartaToday();
  form.elements.work_date.value = workforceFilters.work_date;
  form.elements.status.value = workforceFilters.status;
  form.elements.q.value = workforceFilters.q;
  loadPeople();
}
async function loadPeople() {
  const version = epoch, request = ++peopleRequest, form = $('workforce-filter');
  workforceFilters = {...Object.fromEntries(new FormData(form))};
  message('workforce-message','Memuat roster karyawan…');
  $('workforce-summary').hidden = true; $('workforce-list').replaceChildren();
  try{
    const params=workforceFilters;
    const [employees,attendance]=await Promise.all([
      workforcePage('/api/workforce/employees',{status:'active',q:params.q}),
      workforcePage('/api/workforce/attendance',{start_date:params.work_date,end_date:params.work_date,status:'all',q:params.q})
    ]);
    if(version!==epoch||request!==peopleRequest||view!=='people')return;
    message('workforce-message','');
    const attendanceByEmployee=new Map(attendance.items.map(item=>[item.employee_id,item]));
    const rows=employees.items.map(employee=>({employee,attendance:attendanceByEmployee.get(employee.id)||null}));
    const filtered=rows.filter(row=>params.status==='all'?(true):params.status==='unrecorded'?!row.attendance:row.attendance?.status===params.status);
    const recorded=rows.filter(row=>row.attendance),present=recorded.filter(row=>row.attendance.status==='present');
    const leave=recorded.filter(row=>row.attendance.status==='leave'),absent=recorded.filter(row=>row.attendance.status==='absent');
    const overtime=recorded.reduce((total,row)=>total+row.attendance.overtime_minutes,0);
    $('workforce-summary').innerHTML=`<div><dt>Karyawan aktif</dt><dd>${n(rows.length)}</dd></div><div><dt>Belum dicatat</dt><dd>${n(rows.length-recorded.length)}</dd></div><div><dt>Hadir</dt><dd>${n(present.length)}</dd></div><div><dt>Cuti</dt><dd>${n(leave.length)}</dd></div><div><dt>Absen</dt><dd>${n(absent.length)}</dd></div><div><dt>Lembur</dt><dd>${e(minuteQty(overtime))}</dd></div>`;
    $('workforce-summary').hidden=false;
    $('workforce-list').innerHTML=filtered.length?filtered.map(({employee,attendance:item})=>{
      const status=item?.status||'unrecorded',statusClass=status==='present'?'done':status==='absent'?'late':'';
      const detail=item?.status==='present'?`${item.clock_in.slice(0,5)}–${item.clock_out.slice(0,5)} · kerja ${minuteQty(item.work_minutes)} · lembur ${minuteQty(item.overtime_minutes)}`:item?.notes||'Belum ada catatan untuk tanggal ini.';
      return `<article class="workforce-row" data-workforce-employee="${e(employee.id)}"><div><span class="reference">${e(employee.code)} · ${e(employee.department)}</span><h3>${e(employee.name)}</h3><p>${e(detail)}</p>${item?.notes&&item.status==='present'?`<p class="hint">${e(item.notes)}</p>`:''}</div><div class="workforce-row-actions"><span class="status-label ${statusClass}">${e(workforceStatusLabels[status])}</span>${user.role!=='viewer'?`<button type="button" data-action="attendance-form" data-id="${e(employee.id)}" data-date="${e(params.work_date)}">${item?'Koreksi':'Catat'} kehadiran</button>`:''}${item?`<button type="button" data-action="attendance-history" data-id="${e(item.id)}">Riwayat</button>`:''}</div></article>`;
    }).join(''):'<p class="state">Tidak ada karyawan yang cocok dengan status dan pencarian ini.</p>';
  }catch(error){if(version===epoch&&request===peopleRequest&&view==='people'){
    message('workforce-message',error.message,true);
    $('workforce-message').insertAdjacentHTML('beforeend','<br><button id="workforce-retry" type="button">Coba lagi</button>');
    $('workforce-retry').onclick=loadPeople;
  }}
}

async function workforceEmployeeMasterDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Daftar karyawan','<p class="state">Memuat daftar karyawan…</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const report=await workforcePage('/api/workforce/employees',{status:'all'});if(!current())return;
    $('dialog-content').innerHTML=`<div class="workforce-screen"><div class="workforce-heading"><p class="hint">Status dan perubahan master tersimpan sebagai revisi.</p><div class="actions"><button data-action="workforce" type="button">Kembali ke roster</button>${user.role==='admin'?'<button class="primary" data-action="new-employee" type="button">Tambah karyawan</button>':''}</div></div><div class="product-list workforce-master">${report.items.map(item=>`<article class="product-item" data-workforce-master="${e(item.id)}"><div><strong>${e(item.code)} · ${e(item.name)}</strong><span>${e(item.department)} · ${item.active?'aktif':'nonaktif'} · revisi ${n(item.revision)}</span></div><div class="actions">${user.role==='admin'?`<button data-action="edit-employee" data-id="${e(item.id)}" type="button">Ubah</button>`:''}<button data-action="employee-history" data-id="${e(item.id)}" type="button">Riwayat</button></div></article>`).join('')||'<p class="state">Belum ada karyawan.</p>'}</div></div>`;
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="employee-master">Coba lagi</button>`;}
}

async function workforceEmployeeForm(employeeId=null) {
  if(guardPending())return;
  const version=epoch;
  try{
    const employee=employeeId?await api.get('/api/workforce/employees/'+encodeURIComponent(employeeId)):null;
    if(version!==epoch)return;
    const changing=Boolean(employee);
    formDialog(changing?'Ubah karyawan':'Tambah karyawan',
      (changing?`<p class="full"><strong>${e(employee.code)}</strong></p>`:field('code','Kode karyawan','text','required maxlength="40" autocomplete="off"'))+
      field('name','Nama karyawan','text','required maxlength="160"')+field('department','Departemen','text','required maxlength="160"')+
      (changing?'<label>Status<select name="active"><option value="true">Aktif</option><option value="false">Nonaktif</option></select></label>':'')+
      `<label class="full">${changing?'Alasan perubahan':'Sumber data awal'}<textarea name="reason" required maxlength="1000"></textarea></label>`,form=>{
        const data=new FormData(form);
        return changing?{expected_revision:employee.revision,name:data.get('name').trim(),department:data.get('department').trim(),active:data.get('active')==='true',reason:data.get('reason').trim()}:{code:data.get('code').trim(),name:data.get('name').trim(),department:data.get('department').trim(),reason:data.get('reason').trim()};
      },changing?`/api/workforce/employees/${encodeURIComponent(employee.id)}/changes`:'/api/workforce/employees',changing?`Revisi ${employee.revision}. Kode karyawan tidak dapat diubah.`:'Kode dinormalisasi menjadi huruf besar dan tidak dapat dipakai ulang.');
    const form=$('action-form');if(employee){form.elements.name.value=employee.name;form.elements.department.value=employee.department;form.elements.active.value=String(employee.active);}
  }catch(error){if(version===epoch)notify(error.message);}
}

async function workforceAttendanceForm(employeeId,workDate) {
  if(guardPending())return;
  const version=epoch;
  try{
    const [employee,report]=await Promise.all([api.get('/api/workforce/employees/'+encodeURIComponent(employeeId)),workforcePage('/api/workforce/attendance',{start_date:workDate,end_date:workDate,employee_id:employeeId})]);
    if(version!==epoch)return;const current=report.items[0]||null;
    formDialog(current?'Koreksi kehadiran':'Catat kehadiran',`<p class="full"><strong>${e(employee.code)} · ${e(employee.name)}</strong><br><span class="hint">${e(employee.department)}</span></p>`+
      field('work_date','Tanggal','date',`required readonly value="${e(workDate)}"`)+
      '<label>Status<select name="status"><option value="present">Hadir</option><option value="leave">Cuti</option><option value="absent">Absen</option></select></label>'+
      field('clock_in','Jam masuk','time','required')+field('clock_out','Jam pulang','time','required')+
      field('overtime_minutes','Lembur (menit)','number','required min="0" max="720" step="1" value="0"')+
      '<label class="full">Catatan<textarea name="notes" maxlength="1000"></textarea></label><label class="full">Alasan pencatatan atau koreksi<textarea name="reason" required maxlength="1000"></textarea></label>',form=>{
        const data=new FormData(form),present=data.get('status')==='present';
        return {work_date:data.get('work_date'),expected_revision:current?.revision||0,status:data.get('status'),clock_in:present?data.get('clock_in'):null,clock_out:present?data.get('clock_out'):null,overtime_minutes:present?Number(data.get('overtime_minutes')):0,notes:data.get('notes').trim(),reason:data.get('reason').trim()};
      },`/api/workforce/employees/${encodeURIComponent(employeeId)}/attendance`,current?`Catatan saat ini revisi ${current.revision}. Koreksi menambah revisi baru; catatan lama tetap utuh.`:'Satu catatan per karyawan per tanggal.');
    const form=$('action-form'),toggle=()=>{const present=form.elements.status.value==='present';for(const name of ['clock_in','clock_out','overtime_minutes']){form.elements[name].disabled=!present;form.elements[name].required=present;}if(!present){form.elements.clock_in.value='';form.elements.clock_out.value='';form.elements.overtime_minutes.value='0';}};
    if(current){form.elements.status.value=current.status;form.elements.clock_in.value=current.clock_in?.slice(0,5)||'';form.elements.clock_out.value=current.clock_out?.slice(0,5)||'';form.elements.overtime_minutes.value=current.overtime_minutes;form.elements.notes.value=current.notes;}
    else{form.elements.clock_in.value='08:00';form.elements.clock_out.value='17:00';}
    form.elements.status.onchange=toggle;toggle();
  }catch(error){if(version===epoch)notify(error.message);}
}

async function workforceEmployeeHistoryDialog(employeeId) {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat karyawan','<p class="state">Memuat riwayat karyawan…</p>');const modal=dialogVersion,current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const page=await api.get(`/api/workforce/employees/${encodeURIComponent(employeeId)}/history?limit=100`);if(!current())return;
    $('dialog-content').innerHTML=`<div class="workforce-screen"><p class="form-info">${e(page.employee.code)} · ${e(page.employee.name)} · ${e(page.employee.department)}</p><div>${page.items.map(item=>`<article class="history-item"><time>${e(auditStamp(item.created_at))}</time><div><strong>Revisi ${n(item.revision)} · ${item.active?'Aktif':'Nonaktif'}</strong><p>${e(item.name)} · ${e(item.department)}</p><p class="reason">${e(item.reason)}</p><p class="hint">${e(item.actor_name)}</p></div></article>`).join('')}</div>${page.next_before?'<p class="hint">Menampilkan 100 revisi terbaru.</p>':''}<button data-action="employee-master" type="button">Kembali ke daftar karyawan</button></div>`;
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="employee-history" data-id="${e(employeeId)}">Coba lagi</button>`;}
}

async function workforceAttendanceHistoryDialog(attendanceId) {
  if(guardPending())return;
  const version=epoch;openDialog('Riwayat kehadiran','<p class="state">Memuat riwayat kehadiran…</p>');const modal=dialogVersion,current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const page=await api.get(`/api/workforce/attendance/${encodeURIComponent(attendanceId)}/history?limit=100`);if(!current())return;const attendance=page.attendance;
    $('dialog-content').innerHTML=`<div class="workforce-screen"><p class="form-info">${e(attendance.employee_code)} · ${e(attendance.employee_name)}<br>${date(attendance.work_date)}</p><div>${page.items.map(item=>`<article class="history-item"><time>${e(auditStamp(item.created_at))}</time><div><strong>Revisi ${n(item.revision)} · ${e(workforceStatusLabels[item.status])}</strong><p>${item.status==='present'?`${e(item.clock_in.slice(0,5))}–${e(item.clock_out.slice(0,5))} · kerja ${e(minuteQty(item.work_minutes))} · lembur ${e(minuteQty(item.overtime_minutes))}`:'Tanpa jam kerja'}</p>${item.notes?`<p>${e(item.notes)}</p>`:''}<p class="reason">${e(item.reason)}</p><p class="hint">${e(item.actor_name)}</p></div></article>`).join('')}</div>${page.next_before?'<p class="hint">Menampilkan 100 revisi terbaru.</p>':''}<button data-action="workforce" type="button">Kembali ke roster</button></div>`;
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="attendance-history" data-id="${e(attendanceId)}">Coba lagi</button>`;}
}

const workforceRequestLabels={leave:'Cuti',overtime:'Lembur'};

async function workforceRequestsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Permintaan cuti dan lembur','<p class="state">Memuat permintaan People…</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  $('dialog-content').innerHTML=`<div class="workforce-screen"><div class="workforce-heading"><p class="hint">Approval memberi izin; kehadiran aktual tetap dicatat terpisah.</p><div class="actions"><button data-action="workforce" type="button">Kembali ke roster</button>${user.role!=='viewer'?'<button class="primary" data-action="new-workforce-request" type="button">Ajukan permintaan</button>':''}<button data-action="approvals" type="button">Inbox approval</button></div></div><form id="workforce-request-filter" class="filter-form"><div class="form-grid"><label>Status<select name="status"><option value="all">Semua status</option><option value="submitted">Menunggu keputusan</option><option value="approved">Disetujui</option><option value="rejected">Ditolak</option><option value="cancelled">Dibatalkan</option></select></label><label>Jenis<select name="kind"><option value="all">Semua jenis</option><option value="leave">Cuti</option><option value="overtime">Lembur</option></select></label><label class="full">Cari referensi, karyawan, atau departemen<input name="q" type="search" maxlength="160"></label></div><div class="form-actions"><button class="primary" type="submit">Tampilkan permintaan</button></div></form><p id="workforce-request-message" class="state" role="status"></p><dl id="workforce-request-summary" class="workforce-summary" hidden></dl><div id="workforce-request-list"></div></div>`;
  const form=$('workforce-request-filter');let generation=0;
  const load=async()=>{
    const gen=++generation;message('workforce-request-message','Memuat permintaan People…');$('workforce-request-summary').hidden=true;$('workforce-request-list').replaceChildren();
    try{
      const params=Object.fromEntries(new FormData(form)),report=await workforcePage('/api/workforce/requests',params);if(!current()||gen!==generation)return;
      message('workforce-request-message','');
      $('workforce-request-summary').innerHTML=`<div><dt>Total</dt><dd>${n(report.total)}</dd></div><div><dt>Menunggu</dt><dd>${n(report.summary.submitted)}</dd></div><div><dt>Disetujui</dt><dd>${n(report.summary.approved)}</dd></div><div><dt>Cuti</dt><dd>${n(report.summary.leave)}</dd></div><div><dt>Lembur</dt><dd>${n(report.summary.overtime)}</dd></div>`;$('workforce-request-summary').hidden=false;
      $('workforce-request-list').innerHTML=report.items.length?report.items.map(item=>`<article class="workforce-row" data-workforce-request="${e(item.id)}"><div><span class="reference">${e(item.reference)} · ${e(item.department)}</span><h3>${e(item.code)} · ${e(item.employee_name)}</h3><p>${e(workforceRequestLabels[item.kind])} · ${date(item.start_date)}${item.end_date!==item.start_date?'–'+date(item.end_date):''}${item.kind==='overtime'?' · '+e(minuteQty(item.overtime_minutes)):''}</p><p class="reason">${e(item.reason)}</p></div><div class="workforce-row-actions"><span class="status-label ${item.status==='approved'?'done':item.status==='rejected'?'late':''}">${e(approvalStatus[item.status])}</span><button data-action="workforce-request" data-id="${e(item.id)}" type="button">Rincian</button></div></article>`).join(''):'<p class="state">Belum ada permintaan yang sesuai filter.</p>';
    }catch(error){if(current()&&gen===generation){message('workforce-request-message',error.message,true);$('workforce-request-message').insertAdjacentHTML('beforeend','<br><button id="workforce-request-retry" type="button">Coba lagi</button>');$('workforce-request-retry').onclick=load;}}
  };
  form.onsubmit=event=>{event.preventDefault();load();};await load();
}

async function workforceRequestForm() {
  if(guardPending())return;
  const version=epoch;
  try{
    const employees=await workforcePage('/api/workforce/employees',{status:'active'});if(version!==epoch)return;
    if(!employees.items.length){notify('Tambahkan karyawan aktif sebelum membuat permintaan.');return;}
    formDialog('Ajukan cuti atau lembur',`<label class="full">Karyawan<select name="employee_id">${employees.items.map(item=>option(item.id,`${item.code} · ${item.name} · ${item.department}`)).join('')}</select></label><label>Jenis<select name="kind"><option value="leave">Cuti</option><option value="overtime">Lembur</option></select></label>${field('start_date','Tanggal mulai','date','required')}${field('end_date','Tanggal selesai','date','required')}${field('overtime_minutes','Lembur (menit)','number','required min="0" max="720" step="1" value="0"')}<label class="full">Alasan permintaan<textarea name="reason" required maxlength="1000"></textarea></label>`,form=>{
      const data=new FormData(form),kind=data.get('kind'),start=data.get('start_date');return {employee_id:data.get('employee_id'),kind,start_date:start,end_date:kind==='overtime'?start:data.get('end_date'),overtime_minutes:kind==='overtime'?Number(data.get('overtime_minutes')):0,reason:data.get('reason').trim()};
    },'/api/workforce/requests','Permintaan masuk ke inbox approval. Persetujuan tidak otomatis mencatat kehadiran aktual.');
    const form=$('action-form'),toggle=()=>{const overtime=form.elements.kind.value==='overtime';form.elements.end_date.readOnly=overtime;form.elements.overtime_minutes.disabled=!overtime;form.elements.overtime_minutes.required=overtime;if(overtime)form.elements.end_date.value=form.elements.start_date.value;else if(!form.elements.end_date.value)form.elements.end_date.value=form.elements.start_date.value;};
    form.elements.start_date.value=jakartaToday();form.elements.end_date.value=jakartaToday();form.elements.kind.onchange=toggle;form.elements.start_date.onchange=toggle;toggle();
  }catch(error){if(version===epoch)notify(error.message);}
}

async function workforceRequestDialog(requestId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian permintaan People','<p class="state">Memuat permintaan…</p>');const modal=dialogVersion,current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  try{
    const item=await api.get('/api/workforce/requests/'+encodeURIComponent(requestId));if(!current())return;
    const pending=item.status==='submitted',canCancel=pending&&user.role==='operator'&&user.id===item.actor_id;
    $('dialog-content').innerHTML=`<div class="workforce-screen"><p class="form-info">${e(item.reference)} · ${e(approvalStatus[item.status])}</p><h3>${e(item.code)} · ${e(item.employee_name)}</h3><p>${e(item.department)}${item.employee_active?'':' · karyawan nonaktif'}</p><article class="material-event"><h3>${e(workforceRequestLabels[item.kind])}</h3><p>${date(item.start_date)}${item.end_date!==item.start_date?'–'+date(item.end_date):''} · ${n(item.days)} hari${item.kind==='overtime'?' · '+e(minuteQty(item.overtime_minutes)):''}</p><p class="reason">${e(item.reason)}</p><p class="hint">Diajukan ${e(item.actor_name)} · ${e(auditStamp(item.created_at))}</p></article><h3>Riwayat keputusan</h3><div>${item.history.map(event=>`<article class="history-item"><time>${e(auditStamp(event.created_at))}</time><div><strong>${e(approvalStatus[event.status])}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)}</p></div></article>`).join('')}</div><div class="actions"><button data-action="workforce-requests" type="button">Semua permintaan</button><button data-action="workforce" type="button">Roster People</button>${pending&&user.role==='admin'?`<button data-action="workforce-request-decision" data-id="${e(item.id)}" data-status="approved" type="button">Setujui</button><button data-action="workforce-request-decision" data-id="${e(item.id)}" data-status="rejected" type="button">Tolak</button>`:''}${canCancel?`<button class="quiet" data-action="workforce-request-decision" data-id="${e(item.id)}" data-status="cancelled" type="button">Batalkan</button>`:''}</div></div>`;
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="workforce-request" data-id="${e(requestId)}">Coba lagi</button>`;}
}

async function workforceRequestDecisionForm(requestId,status) {
  if(guardPending())return;
  const version=epoch;
  try{
    const item=await api.get('/api/workforce/requests/'+encodeURIComponent(requestId));if(version!==epoch)return;
    const label={approved:'Setujui',rejected:'Tolak',cancelled:'Batalkan'}[status];
    formDialog(`${label} permintaan ${workforceRequestLabels[item.kind].toLowerCase()}`,`<p class="full"><strong>${e(item.reference)} · ${e(item.code)} · ${e(item.employee_name)}</strong></p><label class="full">Alasan / catatan<textarea name="reason" required maxlength="1000"></textarea></label>`,form=>({status,expected_revision:item.revision,reason:new FormData(form).get('reason').trim()}),`/api/workforce/requests/${encodeURIComponent(item.id)}/decisions`,'Keputusan tersimpan permanen di riwayat approval.');
  }catch(error){if(version===epoch)notify(error.message);}
}

async function showCapacityPlan() {
  const version=epoch;
  const request=activateAnalyticsReport('capacity-plan','Kapasitas produksi','<p class="state">Memuat master kapasitas...</p>');
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='capacity-plan'&&request===analyticsRequest;
  try{
    const [centers,products]=await Promise.all([allRows('/api/work-centers'),allRows('/api/products')]);
    if(!current())return;
    const today=jakartaToday();
    const activeCenters=centers.filter(row=>row.active);
    const admin=user.role==='admin'?`<section><h3>Master kapasitas</h3><p class="hint">Admin mengelola kapasitas dalam menit. Semua perubahan disimpan sebagai revisi.</p>
      <div class="product-list">${centers.map(row=>`<div class="product-item"><div><strong>${e(row.code)} · ${e(row.name)}</strong><span>${e(labels[row.stage])} · ${n(row.daily_minutes)} menit/hari · ${row.active?'aktif':'nonaktif'} · revisi ${n(row.revision)}</span></div><button data-action="edit-work-center" data-id="${e(row.id)}">Ubah</button></div>`).join('')||'<p>Belum ada work center.</p>'}</div>
      <div class="actions"><button data-action="new-work-center">Tambah work center</button></div>
      <div class="filter-form"><div class="form-grid"><label>SKU untuk standar<select id="capacity-standard-product">${products.map(row=>option(row.id,`${row.sku} · ${row.name}`)).join('')}</select></label>
      <label>Tahap standar<select id="capacity-standard-stage">${['cutting','sewing','finishing','qc','rework'].map(value=>option(value,labels[value])).join('')}</select></label></div>
      <div class="form-actions"><button id="capacity-standard-open" type="button" ${products.length?'':'disabled'}>Atur standar waktu</button></div></div>
      <div class="filter-form"><div class="form-grid"><label>Work center kalender<select id="capacity-calendar-center">${activeCenters.map(row=>option(row.id,`${row.code} · ${row.name}`)).join('')}</select></label>
      ${field('capacity_calendar_date','Tanggal override','date',`id="capacity-calendar-date" value="${today}"`)}</div>
      <div class="form-actions"><button id="capacity-calendar-open" type="button" ${activeCenters.length?'':'disabled'}>Atur kapasitas tanggal</button></div></div></section>`:'';
    $('analytics-body').innerHTML=`${admin}<section><h3>Rencana kapasitas</h3><form id="capacity-plan-form" class="filter-form"><p class="hint">Beban memakai saldo WIP saat ini dan standar menit untuk seluruh tahap yang masih harus dilalui sampai QC.</p><div class="form-grid">
      ${field('as_of','Mulai per tanggal','date',`required value="${today}"`)}
      ${field('horizon_days','Horizon kalender (hari)','number','required min="1" max="90" step="1" value="14"')}
      ${field('warning_percent','Peringatan utilisasi (%)','number','required min="1" max="100" step="1" value="80"')}
      <label>Status<select name="status"><option value="attention">Perlu perhatian</option><option value="overloaded">Overload</option><option value="deadline_risk">Risiko deadline</option><option value="near_capacity">Mendekati kapasitas</option><option value="available">Masih tersedia</option><option value="idle">Tanpa beban</option><option value="all">Semua</option></select></label>
      <label>Tahap<select name="stage"><option value="all">Semua tahap</option>${['cutting','sewing','finishing','qc','rework'].map(value=>option(value,labels[value])).join('')}</select></label>
      <label>Work center<select name="work_center_id"><option value="">Semua work center aktif</option>${activeCenters.map(row=>option(row.id,`${row.code} · ${row.name}`)).join('')}</select></label>
      </div><div class="form-actions"><button class="primary" id="capacity-plan-submit" type="submit">Hitung kapasitas</button></div></form>
      <p id="capacity-plan-message" class="state" role="status" hidden></p><div id="capacity-plan-summary"></div><div id="capacity-plan-gaps"></div><div id="capacity-plan-results"></div><button id="capacity-plan-more" type="button" hidden>Muat work center berikutnya</button></section>`;
    if(user.role==='admin'){
      $('capacity-standard-open').onclick=()=>capacityRoutingStandardForm($('capacity-standard-product').value,$('capacity-standard-stage').value);
      $('capacity-calendar-open').onclick=()=>capacityCalendarForm($('capacity-calendar-center').value,$('capacity-calendar-date').value);
    }
    const form=$('capacity-plan-form'),submit=$('capacity-plan-submit');let offset=0,generation=0;
    restoreAnalyticsFilters('capacity-plan',form);
    const statusLabels={overloaded:'Overload',deadline_risk:'Risiko deadline',near_capacity:'Mendekati kapasitas',available:'Masih tersedia',idle:'Tanpa beban'};
    const load=async(reset=false)=>{
      if(!current())return;
      if(reset){generation++;offset=0;$('capacity-plan-summary').replaceChildren();$('capacity-plan-gaps').replaceChildren();$('capacity-plan-results').replaceChildren();}
      const gen=generation,more=$('capacity-plan-more');submit.disabled=true;more.disabled=true;more.hidden=true;
      message('capacity-plan-message',offset?'Memuat work center berikutnya...':'Menghitung beban dan kalender kapasitas...');
      try{
        const params=new URLSearchParams(Object.fromEntries(new FormData(form)));params.set('limit','25');params.set('offset',String(offset));
        const report=await api.get('/api/capacity-plan?'+params);if(!current()||gen!==generation)return;
        message('capacity-plan-message','');
        if(!offset){
          $('capacity-plan-summary').innerHTML=`<p class="form-info">${date(report.as_of)} sampai ${date(report.horizon_end)}<br>${n(report.summary.work_centers)} work center aktif · ${n(report.summary.attention_work_centers)} perlu perhatian · ${n(report.summary.at_risk_orders)} order berisiko<br>Beban ${e(minuteQty(report.summary.required_minutes))} · tersedia ${e(minuteQty(report.summary.available_minutes))}</p><p class="hint">Hari kerja default Senin sampai Jumat. Override kalender terbaru berlaku per tanggal. Angka ini adalah estimasi standar, bukan janji jadwal produksi.</p>`;
          $('capacity-plan-gaps').innerHTML=report.coverage_gaps.length?`<h3>Data kapasitas belum lengkap</h3><p class="hint">${n(report.summary.coverage_gaps)} kebutuhan tahap belum punya standar aktif, mencakup ${n(report.summary.missing_standard_quantity)} pcs.</p>${report.coverage_gaps.slice(0,25).map(gap=>`<article class="material-event"><strong>${e(gap.order_reference)} · ${e(gap.sku)}</strong><p>${e(labels[gap.stage])} · ${n(gap.quantity)} pcs · ${gap.kind==='inactive_work_center'?'work center nonaktif':'standar waktu belum diisi'}</p></article>`).join('')}`:'';
        }
        const html=report.items.map(row=>{
          const attention=['overloaded','deadline_risk','near_capacity'].includes(row.status);
          const utilization=row.utilization_percent===null?'Belum terukur':`${e(row.utilization_percent)}%`;
          const orders=row.orders.map(order=>`<article class="material-event"><h4>${e(order.order_reference)} · ${e(order.order_title)}</h4><p>Target ${date(order.due_date)} · beban ${e(minuteQty(order.required_minutes))} · kapasitas sampai target ${e(minuteQty(order.available_minutes_by_due))}</p>${order.at_risk?`<p class="reason">Kurang ${e(minuteQty(order.capacity_shortfall_minutes))} sebelum target.</p>`:''}${order.products.map(product=>`<p class="hint">${e(product.sku)} · ${n(product.quantity)} pcs × ${e(minuteQty(product.minutes_per_unit))}/pcs = ${e(minuteQty(product.required_minutes))}</p>`).join('')}<button data-action="detail" data-id="${e(order.order_id)}">Buka order</button></article>`).join('');
          const calendar=row.days.map(day=>`${date(day.date)} ${n(day.available_minutes)} menit${day.source==='override'?' (override)':''}`).join(' · ');
          return `<article class="material-event" data-capacity-center="${e(row.id)}"><div class="issue-heading"><h3>${e(row.code)} · ${e(row.name)}</h3><span class="status-label ${attention?'late':'done'}">${e(statusLabels[row.status])}</span></div><p>${e(labels[row.stage])} · utilisasi ${utilization}</p><dl class="requirement-values"><div><dt>Beban</dt><dd>${e(minuteQty(row.required_minutes))}</dd></div><div><dt>Tersedia</dt><dd>${e(minuteQty(row.available_minutes))}</dd></div><div><dt>Sisa</dt><dd>${e(minuteQty(row.remaining_minutes))}</dd></div><div><dt>Overload</dt><dd>${e(minuteQty(row.overload_minutes))}</dd></div><div><dt>Order</dt><dd>${n(row.order_count)}</dd></div><div><dt>Berisiko</dt><dd>${n(row.at_risk_order_count)}</dd></div></dl><p class="hint">Kalender: ${calendar}</p>${orders||'<p class="state">Tidak ada beban order pada horizon ini.</p>'}</article>`;
        }).join('');
        appendRows('capacity-plan-results',html);
        if(!offset&&!report.items.length)$('capacity-plan-results').innerHTML='<p class="state">Tidak ada work center yang cocok dengan status dan filter ini.</p>';
        offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat work center berikutnya';
      }catch(error){if(current()&&gen===generation){message('capacity-plan-message',error.message,true);$('capacity-plan-message').insertAdjacentHTML('beforeend','<br><button id="capacity-plan-retry" type="button">Coba lagi</button>');$('capacity-plan-retry').onclick=()=>load();}}
      finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
    };
    form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('capacity-plan',form);load(true);};$('capacity-plan-more').onclick=()=>load();await load(true);
  }catch(error){if(current())$('analytics-body').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="capacity-plan">Coba lagi</button>`;}
}
$('capacity-plan').onclick=showCapacityPlan;

function showProductionQualityInsights() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('production-quality-insights','Kualitas produksi',`<form id="production-quality-form" class="filter-form">
    <p class="hint">Bandingkan final QC aktif pada periode terpilih dengan periode sebelumnya yang sama panjang. Koreksi final QC tidak ikut dihitung.</p>
    <div class="form-grid">
      ${field('as_of','Data sampai tanggal','date',`required value="${today}"`)}
      ${field('window_days','Panjang periode (hari)','number','required min="7" max="365" step="1" value="30"')}
      ${field('warning_percent','Batas rework + reject (%)','number','required min="1" max="100" step="1" value="5"')}
      ${field('change_threshold','Batas perubahan (poin persentase)','number','required min="1" max="100" step="1" value="1"')}
      ${field('query','Cari vendor, line, SKU, order, atau defect','search','maxlength="160"')}
      <label>Jenis pengerjaan<select name="assignment_type"><option value="all">Internal dan makloon</option><option value="internal">Internal</option><option value="makloon">Makloon</option></select></label>
      <label>Status<select name="status"><option value="attention">Perlu perhatian</option><option value="healthy">Sehat</option><option value="all">Semua</option></select></label>
    </div><div class="form-actions"><button class="primary" id="production-quality-submit" type="submit">Tampilkan kualitas</button></div>
  </form><p id="production-quality-message" class="state" role="status" hidden></p><div id="production-quality-summary"></div><div id="production-quality-results"></div><button id="production-quality-more" type="button" hidden>Muat penanggung jawab berikutnya</button>`);
  const version=epoch,current=()=>version===epoch&&view==='analytics'&&analyticsReport==='production-quality-insights'&&request===analyticsRequest;
  const form=$('production-quality-form'),submit=$('production-quality-submit');let offset=0,generation=0;
  restoreAnalyticsFilters('production-quality-insights',form);
  const trendLabels={worsening:'Memburuk',improving:'Membaik',stable:'Stabil',new_baseline:'Baseline baru'};
  const assignmentLabels={internal:'Internal',makloon:'Makloon'};
  const delta=value=>value===null?'Belum ada pembanding':`${Number(value)>0?'+':''}${e(value)} poin`;
  const load=async(reset=false)=>{
    if(!current())return;
    if(reset){generation++;offset=0;$('production-quality-summary').replaceChildren();$('production-quality-results').replaceChildren();}
    const gen=generation,more=$('production-quality-more');submit.disabled=true;more.disabled=true;more.hidden=true;
    message('production-quality-message',offset?'Memuat penanggung jawab berikutnya...':'Menghitung yield dan tren defect...');
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));params.set('limit','25');params.set('offset',String(offset));
      const report=await api.get('/api/production-quality-insights?'+params);if(!current()||gen!==generation)return;
      message('production-quality-message','');
      if(!offset){
        const s=report.summary;
        $('production-quality-summary').innerHTML=`<p class="form-info">${date(report.current_period_start)} sampai ${date(report.as_of)} dibanding ${date(report.previous_period_start)} sampai ${date(report.previous_period_end)}<br>${n(s.inspected_quantity)} pcs diperiksa · yield ${e(s.first_pass_yield_percent)}% · rework + reject ${e(s.nonconforming_rate_percent)}% · perubahan ${delta(s.nonconforming_rate_change_points)}<br>Inspeksi ulang ${n(s.reinspected_quantity)} pcs dari ${n(s.reinspection_record_count)} catatan · diterima ${n(s.reinspection_accepted_quantity)} · rework ${n(s.reinspection_rework_quantity)} · reject ${n(s.reinspection_reject_quantity)}<br>${n(s.groups)} penanggung jawab · ${n(s.attention_groups)} perlu perhatian</p><p class="hint">Perlu perhatian berarti rework + reject mencapai batas atau trennya memburuk melewati ambang perubahan. Yield first pass dihitung hanya dari inspeksi awal, sehingga satu pcs yang diperiksa ulang setelah rework tidak dihitung dua kali.</p>`;
      }
      const html=report.items.map(row=>{
        const attention=row.status==='attention',c=row.current,p=row.previous;
        const defects=row.defect_types.length?row.defect_types.map(item=>`<li><strong>${e(item.defect_type||'Tanpa jenis defect')}</strong>: ${n(item.nonconforming_quantity)} pcs dari ${n(item.record_count)} catatan</li>`).join(''):'<li>Tidak ada defect atau rework pada periode ini.</li>';
        const sources=row.responsible_sources.length?row.responsible_sources.map(item=>`<li><strong>${e(item.responsible_source||'Sumber belum diisi')}</strong>: ${n(item.nonconforming_quantity)} pcs</li>`).join(''):'<li>Tidak ada sumber masalah pada periode ini.</li>';
        const skus=row.skus.map(item=>`<article class="material-event"><strong>${e(item.sku)} · ${e(item.product_name)}</strong>${item.inspected_quantity?`<p>${e(item.color)} · ${e(item.size)} · ${n(item.inspected_quantity)} pcs diperiksa · rework + reject ${e(item.nonconforming_rate_percent)}%</p>`:`<p>${e(item.color)} · ${e(item.size)} · belum ada inspeksi awal pada periode ini</p>`}${item.reinspected_quantity?`<p>Inspeksi ulang ${n(item.reinspected_quantity)} pcs · gagal lagi ${n(item.reinspection_nonconforming_quantity)} pcs (${e(item.reinspection_nonconforming_rate_percent)}%)</p>`:''}</article>`).join('');
        const records=row.recent_records.map(item=>`<article class="material-event"><strong>${e(item.reference)} · ${e(item.order_reference)}</strong><p>${inspectionBadge(item)}</p><p>${date(item.inspection_date)} · ${e(item.sku)} · diterima ${n(item.accepted_quantity)}, rework ${n(item.rework_quantity)}, reject ${n(item.reject_quantity)}</p><p>${e(item.defect_type||'Tanpa jenis defect')} · ${e(item.responsible_source||'Sumber belum diisi')}</p><button data-action="final-qc-record" data-id="${e(item.id)}">Buka final QC ${e(item.reference)}</button></article>`).join('');
        return `<article class="material-event" data-production-quality="${e(row.assignment_type)}-${e(row.assignee)}"><div class="issue-heading"><h3>${e(row.assignee)}</h3><span class="status-label ${attention?'late':'done'}">${attention?'Perlu perhatian':'Sehat'}</span></div><p>${e(assignmentLabels[row.assignment_type])} · tren <strong>${e(trendLabels[row.trend])}</strong> · ${delta(row.nonconforming_rate_change_points)}</p><dl class="requirement-values"><div><dt>Diperiksa</dt><dd>${n(c.inspected_quantity)} pcs</dd></div><div><dt>Yield</dt><dd>${e(c.first_pass_yield_percent)}%</dd></div><div><dt>Rework + reject</dt><dd>${e(c.nonconforming_rate_percent)}%</dd></div><div><dt>Rework</dt><dd>${e(c.rework_rate_percent)}%</dd></div><div><dt>Reject</dt><dd>${e(c.reject_rate_percent)}%</dd></div><div><dt>Periode lalu</dt><dd>${e(p.nonconforming_rate_percent)}%</dd></div><div><dt>Inspeksi ulang</dt><dd>${n(c.reinspected_quantity)} pcs</dd></div></dl><h4>Jenis defect</h4><ul>${defects}</ul><h4>Sumber penanggung jawab</h4><ul>${sources}</ul><h4>SKU periode ini</h4>${skus}<h4>Final QC terbaru</h4>${records}</article>`;
      }).join('');
      appendRows('production-quality-results',html);
      if(!offset&&!report.items.length)$('production-quality-results').innerHTML='<p class="state">Tidak ada penanggung jawab yang cocok dengan status dan filter periode ini.</p>';
      offset+=report.items.length;more.hidden=offset>=report.total;more.textContent='Muat penanggung jawab berikutnya';
    }catch(error){if(current()&&gen===generation){message('production-quality-message',error.message,true);$('production-quality-message').insertAdjacentHTML('beforeend','<br><button id="production-quality-retry" type="button">Coba lagi</button>');$('production-quality-retry').onclick=()=>load();}}
    finally{if(current()&&gen===generation){submit.disabled=false;more.disabled=false;}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('production-quality-insights',form);load(true);};$('production-quality-more').onclick=()=>load();load(true);
}
$('production-quality-insights').onclick=showProductionQualityInsights;

function showReplenishment() {
  const today=jakartaToday();
  const request=activateAnalyticsReport('replenishment','Risiko stockout & rekomendasi',`<form id="replenishment-form" class="filter-form">
    <p class="hint">Stok tersedia dan produksi berjalan dibandingkan dengan demand selama lead time, periode review, dan safety stock. Kebutuhan produksi baru diterjemahkan ke bahan memakai BOM terbaru.</p>
    <div class="form-grid">
      ${field('as_of','Forecast sampai tanggal','date',`required value="${today}"`)}
      ${field('window_days','Panjang window demand (hari)','number','required min="7" max="90" step="1" value="28"')}
      ${field('lead_time_days','Lead time replenishment (hari)','number','required min="1" max="180" step="1" value="14"')}
      ${field('review_period_days','Periode review stok (hari)','number','required min="1" max="180" step="1" value="30"')}
      ${field('safety_stock_days','Safety stock (hari)','number','required min="0" max="90" step="1" value="7"')}
      ${field('batch_multiple','Kelipatan batch produksi (pcs)','number','required min="1" max="100000" step="1" value="1"')}
      ${field('marketplace','Marketplace','text','maxlength="160" placeholder="Semua marketplace"')}
      <label>Cari SKU atau produk<input name="query" type="search" maxlength="160" placeholder="Kode, nama, warna, atau ukuran"></label>
    </div>
    <div class="form-actions"><button class="primary" id="replenishment-submit" type="submit">Hitung rekomendasi</button></div>
  </form><p id="replenishment-message" class="state" role="status" hidden></p><div id="replenishment-results"></div>`);
  const version=epoch,form=$('replenishment-form'),button=$('replenishment-submit');
  restoreAnalyticsFilters('replenishment',form);
  const current=()=>version===epoch&&view==='analytics'&&analyticsReport==='replenishment'&&request===analyticsRequest;
  const load=async()=>{
    if(!current())return;
    button.disabled=true;button.textContent='Menghitung…';
    message('replenishment-message','Menggabungkan forecast, stok, produksi, BOM, PR, dan PO…');
    $('replenishment-results').replaceChildren();
    try{
      const params=new URLSearchParams(Object.fromEntries(new FormData(form)));
      params.set('limit','100');params.set('offset','0');
      const report=await api.get('/api/replenishment-recommendations?'+params);
      if(!current())return;
      message('replenishment-message','');
      const risks={out_of_stock:'Stok habis',stockout_before_replenishment:'Stockout sebelum replenishment',
        below_safety_stock:'Di bawah safety stock',covered:'Stok tercakup',
        insufficient_history:'Riwayat demand belum cukup',no_demand:'Tidak ada demand pada window'};
      const products=report.product_recommendations.map(row=>`<article class="material-event" data-replenishment-sku="${e(row.sku)}"><h3>${e(row.sku)} · ${e(risks[row.stockout_risk])}</h3><p>${e(row.name)}${[row.color,row.size].filter(Boolean).length?' · '+e([row.color,row.size].filter(Boolean).join(' / ')):''}</p><dl class="requirement-values"><div><dt>Demand forecast</dt><dd>${n(Number(row.forecast_daily_rate))} pcs/hari</dd></div><div><dt>Stok tersedia</dt><dd>${n(row.available_quantity)} pcs</dd></div><div><dt>Produksi berjalan</dt><dd>${n(row.inbound_production_quantity)} pcs</dd></div><div><dt>Days of cover</dt><dd>${row.days_of_cover===null?'Belum tersedia':n(Number(row.days_of_cover))+' hari'}</dd></div><div><dt>Reorder point</dt><dd>${n(row.reorder_point_quantity)} pcs</dd></div><div><dt>Target stok</dt><dd>${n(row.target_stock_quantity)} pcs</dd></div><div><dt>Rekomendasi produksi</dt><dd><strong>${n(row.recommended_production_quantity)} pcs</strong></dd></div></dl><p class="hint">Sellable ${n(row.sellable_quantity)} · terreservasi ${n(row.reserved_quantity)} · hold ${n(row.hold_quantity)} · batch ${n(row.batch_multiple)} pcs${row.projected_stockout_date?' · estimasi stockout '+date(row.projected_stockout_date):''}</p></article>`).join('');
      const materials=report.material_purchase_recommendations.map(row=>`<article class="material-event" data-replenishment-material="${e(row.code)}"><h3>${e(row.code)} · ${e(row.name)}</h3><p class="status-label ${row.status==='purchase'?'late':'done'}">${row.status==='purchase'?'Perlu pembelian baru':'Kebutuhan tercakup'}</p><dl class="requirement-values"><div><dt>Kebutuhan produksi berjalan</dt><dd>${e(materialQty(row.existing_production_requirement,row.unit))}</dd></div><div><dt>Kebutuhan rekomendasi baru</dt><dd>${e(materialQty(row.recommended_production_requirement,row.unit))}</dd></div><div><dt>Stok bahan</dt><dd>${e(materialQty(row.on_hand_quantity,row.unit))}</dd></div><div><dt>PR terbuka</dt><dd>${e(materialQty(row.open_purchase_request_quantity,row.unit))}</dd></div><div><dt>PO terbuka</dt><dd>${e(materialQty(row.open_purchase_order_quantity,row.unit))}</dd></div><div><dt>Rekomendasi beli</dt><dd><strong>${e(materialQty(row.recommended_purchase_quantity,row.unit))}</strong></dd></div></dl></article>`).join('');
      const gaps=report.coverage_gaps.map(gap=>`<p>SKU ${e(gap.sku)} belum mempunyai BOM untuk ${gap.context==='active_production'?'produksi yang sedang berjalan':'rekomendasi produksi baru'}.</p>`).join('');
      $('replenishment-results').innerHTML=`<p class="form-info">Horizon perencanaan sampai ${date(report.planning_horizon_end)} · ${n(report.coverage_days)} hari<br>${n(report.summary.recommended_production_quantity)} pcs direkomendasikan untuk produksi · ${n(report.summary.materials_to_purchase)} bahan perlu dibeli</p><p class="hint">Stok adalah posisi saat ini. Pipeline hanya menghitung order produksi, PR, dan PO bertanggal target di dalam horizon. Estimasi stockout memakai stok tersedia tanpa mengasumsikan tanggal kedatangan produksi berjalan.</p>${gaps?`<article class="material-event"><h3>Data yang perlu dilengkapi</h3>${gaps}</article>`:''}<h3>Risiko dan rekomendasi produksi</h3>${products||'<p class="state">Tidak ada SKU yang cocok dengan filter.</p>'}${report.total>report.product_recommendations.length?`<p class="hint">Menampilkan ${n(report.product_recommendations.length)} dari ${n(report.total)} SKU. Persempit pencarian untuk melihat SKU lain.</p>`:''}<h3>Rekomendasi pembelian bahan</h3>${materials||'<p class="state">Belum ada kebutuhan bahan yang dapat dihitung.</p>'}<p class="hint">Rekomendasi pembelian mengurangi stok bahan, PR terbuka, dan sisa PO terbuka. Harga, supplier, MOQ bahan, serta kapasitas produksi belum menentukan hasil.</p>`;
    }catch(error){
      if(current()){
        message('replenishment-message',error.message,true);
        $('replenishment-message').insertAdjacentHTML('beforeend','<br><button id="replenishment-retry" type="button">Coba lagi</button>');
        $('replenishment-retry').onclick=load;
      }
    }finally{if(current()){button.disabled=false;button.textContent='Hitung rekomendasi';}}
  };
  form.onsubmit=event=>{event.preventDefault();saveAnalyticsFilters('replenishment',form);load();};
}
$('replenishment').onclick=showReplenishment;
// Registri laporan analitik: dipakai reloadAnalytics() untuk memuat ulang laporan aktif
// setelah child dialog (mis. master kapasitas) berhasil menyimpan. Tujuan sidebar tetap
// dideklarasikan di workspaceDestinations; tabel ini hanya memetakan nav id ke renderernya.
const analyticsReports={
  'wip-ageing-insights':showWipAgeingInsights,
  'capacity-plan':showCapacityPlan,
  'production-quality-insights':showProductionQualityInsights,
  'supplier-performance-insights':showSupplierPerformanceInsights,
  'material-price-insights':showMaterialPriceInsights,
  'purchase-commitment-insights':showPurchaseCommitmentInsights,
  'demand-forecast':showDemandForecast,
  'replenishment':showReplenishment,
  'size-demand-insights':showSizeDemandInsights,
  'return-insights':showReturnInsights,
  'dead-stock-insights':showDeadStockInsights,
  'stock-adjustment-insights':showStockAdjustmentInsights
};
$('analytics-back').onclick=showBoard;
$('materials').onclick = showMaterials;
$('scan-material-batch').onclick = materialBatchScanDialog;
$('materials-back').onclick = showBoard;
$('materials-refresh').onclick = () => loadMaterials();
$('material-filter').onchange = () => { materialsOffset = 0; loadMaterials(); };
$('materials-previous').onclick = () => { materialsOffset = Math.max(0,materialsOffset-25); loadMaterials(); };
$('materials-next').onclick = () => { materialsOffset += 25; loadMaterials(); };
$('material-master').onclick = materialMasterDialog;
$('receive-material').onclick = receiptForm;
$('people-back').onclick = showBoard;
$('people-master').onclick = workforceEmployeeMasterDialog;
$('people-requests').onclick = workforceRequestsDialog;
// onclick meneruskan event sebagai argumen pertama; workforceEmployeeForm membaca
// id karyawan di situ, jadi harus dipanggil tanpa argumen saat menambah karyawan baru.
$('new-employee').onclick = () => workforceEmployeeForm();
$('workforce-filter').onsubmit = event => { event.preventDefault(); loadPeople(); };
$('products-back').onclick = showBoard;
$('products-refresh').onclick = () => loadProducts();
$('new-product').onclick = productForm;
$('products-search').oninput = paintProducts;
$('products-clear').onclick = () => { $('products-search').value = ''; paintProducts(); };
const purchaseStatus = {submitted:'Menunggu keputusan',approved:'Disetujui',rejected:'Ditolak',cancelled:'Dibatalkan'};
const approvalStatus = {pending:'Menunggu keputusan',submitted:'Menunggu keputusan',approved:'Disetujui',rejected:'Ditolak',cancelled:'Dibatalkan'};
const approvalKind = {purchase_request:'Purchasing · PR',purchase_order:'Purchasing · PO',supplier_payment:'Finance · pembayaran supplier',marketing_budget:'Marketing · budget kampanye',production_change:'Production · perubahan order',workforce_leave:'People · cuti',workforce_overtime:'People · lembur',payroll_batch:'People · batch payroll',ai_action:'AI Brain · tindakan'};
const approvalAction = {purchase_request:'purchase-request',purchase_order:'purchase-order',supplier_payment:'supplier-payment-request',marketing_budget:'marketing-budget-request',production_change:'production-change-request',workforce_leave:'workforce-request',workforce_overtime:'workforce-request',payroll_batch:'payroll-approval-request',ai_action:'ai-action-proposal'};
function approvalContextHTML(row) {
  if(row.kind==='purchase_request')return `<p>Dibutuhkan ${date(row.context.required_date)} · ${n(row.context.line_count)} bahan</p>`;
  if(row.kind==='purchase_order')return `<p>Perkiraan datang ${date(row.context.expected_date)} · ${n(row.context.line_count)} bahan</p>`;
  if(row.kind==='supplier_payment')return `<p>Invoice ${e(row.context.invoice_reference)} · jatuh tempo ${date(row.context.due_date)}</p>`;
  if(row.kind==='marketing_budget')return `<p>${e(row.context.channel)} · ${date(row.context.start_date)}–${date(row.context.end_date)}</p>`;
  if(row.kind==='workforce_leave')return `<p>${date(row.context.start_date)}${row.context.end_date!==row.context.start_date?'–'+date(row.context.end_date):''} · ${n(row.context.days)} hari</p>`;
  if(row.kind==='workforce_overtime')return `<p>${date(row.context.start_date)} · ${e(minuteQty(row.context.overtime_minutes))}</p>`;
  if(row.kind==='payroll_batch')return `<p>${date(row.context.period_start)}–${date(row.context.period_end)} · ${n(row.context.employee_count)} karyawan${row.context.stale?' · sumber berubah':''}</p>`;
  if(row.kind==='ai_action')return `<p>${e(row.context.recommendation_title)}</p>`;
  return `<p>Target ${date(row.context.old_due_date)} → ${date(row.context.new_due_date)}</p><p>PIC ${e(row.context.old_owner_name)} → ${e(row.context.new_owner_name)}</p>${row.context.stale?'<p class="status-label late">Permintaan sudah stale.</p>':''}`;
}
const rupiah = value => 'Rp' + BigInt(value.split('.')[0]).toLocaleString('id-ID') + ',' + value.split('.')[1];
const purchaseStamp = value => new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(value));
$('purchase-requests').onclick = () => purchaseRequestsDialog();
$('marketing-budgets').onclick = marketingBudgetsDialog;
$('approvals').onclick = approvalsDialog;

async function approvalsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Inbox approval','<p class="state">Memuat antrean keputusan...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  $('dialog-content').innerHTML=`<p class="hint">Satu antrean untuk keputusan purchasing, finance, marketing, produksi, People, dan tindakan hasil investigasi. Nilai serta konteks asal tetap dibaca dari ledger domainnya.</p><div class="filter-form"><div class="form-grid"><label>Status<select id="approval-status"><option value="pending">Menunggu keputusan</option><option value="all">Semua status</option><option value="approved">Disetujui</option><option value="rejected">Ditolak</option><option value="cancelled">Dibatalkan</option></select></label><label>Jenis approval<select id="approval-kind"><option value="all">Semua jenis</option><option value="purchase_request">Purchasing · PR</option><option value="purchase_order">Purchasing · PO</option><option value="supplier_payment">Finance · pembayaran supplier</option><option value="marketing_budget">Marketing · budget kampanye</option><option value="production_change">Production · perubahan order</option><option value="workforce_leave">People · cuti</option><option value="workforce_overtime">People · lembur</option><option value="payroll_batch">People · batch payroll</option><option value="ai_action">AI Brain · tindakan</option></select></label></div><div class="form-actions"><button id="approval-refresh">Muat ulang inbox</button></div></div><div class="actions"><button data-action="purchase-requests">Semua PR</button><button data-action="marketing-budgets">Semua budget marketing</button><button data-action="workforce-requests">Permintaan People</button><button data-action="mekari-payroll-summary">Payroll Mekari</button></div><div id="approval-list"><p class="state">Memuat approval...</p></div><p id="approval-error" class="error" role="alert" hidden></p><button id="approval-more" type="button">Muat approval berikutnya</button>`;
  let offset=0,generation=0;
  const load=async(reset=false)=>{
    if(reset){generation++;offset=0;$('approval-list').replaceChildren();}
    const gen=generation,button=$('approval-more');button.disabled=true;message('approval-error','');
    try{
      const rows=await api.get('/api/approvals?'+new URLSearchParams({limit:25,offset,status:$('approval-status').value,kind:$('approval-kind').value}));
      if(!current()||gen!==generation)return;
      appendRows('approval-list',rows.map(row=>`<article class="material-event"><p class="eyebrow">${e(approvalKind[row.kind])}</p><h3>${e(row.reference)} · ${e(approvalStatus[row.status])}</h3><p>${e(row.title)}</p>${row.amount?`<p><strong>${e(rupiah(row.amount))}</strong></p>`:''}${approvalContextHTML(row)}<p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p><button data-action="${approvalAction[row.kind]}" data-id="${e(row.id)}" aria-label="Rincian approval ${e(row.reference)}">Buka approval</button></article>`).join(''));
      if(!offset&&!rows.length)$('approval-list').innerHTML='<p class="state">Tidak ada approval yang sesuai filter.</p>';
      offset+=rows.length;button.hidden=rows.length<25;button.textContent='Muat approval berikutnya';
    }catch(error){if(current()&&gen===generation){message('approval-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current()&&gen===generation)button.disabled=false;}
  };
  $('approval-status').onchange=$('approval-kind').onchange=$('approval-refresh').onclick=()=>load(true);
  $('approval-more').onclick=()=>load();await load();
}

async function marketingBudgetsDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Budget marketing','<p class="state">Memuat pengajuan budget…</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  $('dialog-content').innerHTML=`<p class="hint">Daftar plafon kampanye yang diajukan ke manajemen. Persetujuan belum mencatat realisasi belanja.</p><div class="actions">${user.role!=='viewer'?'<button class="primary" data-action="new-marketing-budget">Ajukan budget</button>':''}<button id="marketing-budget-refresh">Muat ulang</button><button data-action="approvals">Inbox approval</button></div><div class="filter-form"><div class="form-grid"><div><label for="marketing-budget-status">Status</label><select id="marketing-budget-status"><option value="all">Semua status</option><option value="submitted">Menunggu keputusan</option><option value="approved">Disetujui</option><option value="rejected">Ditolak</option><option value="cancelled">Dibatalkan</option></select></div></div></div><div id="marketing-budget-list"></div><p id="marketing-budget-error" class="error" role="alert" hidden></p><button id="marketing-budget-more">Muat pengajuan berikutnya</button>`;
  let before=null,generation=0;
  const load=async(reset=false)=>{
    if(reset){generation++;before=null;$('marketing-budget-list').replaceChildren();}
    const gen=generation,button=$('marketing-budget-more');button.disabled=true;message('marketing-budget-error','');
    try{
      const rows=await api.get('/api/marketing-budget-requests?'+new URLSearchParams({limit:25,status:$('marketing-budget-status').value,...(before?{before}:{})}));
      if(!current()||gen!==generation)return;
      appendRows('marketing-budget-list',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${e(approvalStatus[row.status])}</h3><p>${e(row.campaign_name)} · ${e(row.channel)}</p><p>${date(row.start_date)}–${date(row.end_date)} · <strong>${e(rupiah(row.amount))}</strong></p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p><button data-action="marketing-budget-request" data-id="${e(row.id)}" aria-label="Rincian budget ${e(row.reference)}">Rincian budget</button></article>`).join(''));
      if(!before&&!rows.length)$('marketing-budget-list').innerHTML='<p class="state">Belum ada pengajuan budget yang sesuai filter.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pengajuan berikutnya';
    }catch(error){if(current()&&gen===generation){message('marketing-budget-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current()&&gen===generation)button.disabled=false;}
  };
  $('marketing-budget-status').onchange=$('marketing-budget-refresh').onclick=()=>load(true);
  $('marketing-budget-more').onclick=()=>load();await load();
}

function marketingBudgetForm() {
  if(guardPending())return;
  formDialog('Ajukan budget marketing',
    field('reference','Referensi pengajuan','text','required maxlength="160"')+
    field('campaign_name','Nama kampanye','text','required maxlength="160"')+
    field('channel','Channel marketing','text','required maxlength="160"')+
    field('start_date','Tanggal mulai','date','required')+
    field('end_date','Tanggal selesai','date','required')+
    field('amount','Nominal budget (Rp)','number','required min="0.01" max="1000000000000" step="0.01"')+
    '<label class="full">Objective kampanye<textarea name="objective" required maxlength="1000"></textarea></label>'+materialReason,
    form=>Object.fromEntries(new FormData(form)), '/api/marketing-budget-requests',
    'Approval mengesahkan plafon kampanye. Realisasi belanja, invoice platform, dan jurnal keuangan dicatat di sistem lain sampai integrasinya tersedia.');
}

async function marketingBudgetRequestDialog(requestId) {
  if(guardPending())return;
  const version=epoch;openDialog('Approval budget marketing','<p class="state">Memuat pengajuan…</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketing-budget-requests/'+encodeURIComponent(requestId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const buttons=[];
    if(user.role==='admin'&&row.status==='submitted')buttons.push(['approved','Setujui budget'],['rejected','Tolak budget']);
    if(row.status==='submitted'&&(user.role==='admin'||row.actor_id===user.id))buttons.push(['cancelled','Batalkan pengajuan']);
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${e(approvalStatus[row.status])}</p><h3>${e(row.campaign_name)}</h3><p>${e(row.channel)} · ${date(row.start_date)}–${date(row.end_date)}</p><p><strong>${e(rupiah(row.amount))}</strong></p><h4>Objective</h4><p class="reason">${e(row.objective)}</p><h4>Alasan pengajuan</h4><p class="reason">${e(row.reason)}</p><p class="hint">Diajukan ${e(row.actor_name)} · ${purchaseStamp(row.created_at)}. Persetujuan hanya mengesahkan plafon dan belum mencatat belanja.</p><div class="actions">${buttons.map(([status,label])=>`<button data-marketing-budget-decision="${status}">${label}</button>`).join('')}<button data-action="marketing-budgets">Daftar budget</button><button data-action="approvals">Inbox approval</button></div><h3>Riwayat keputusan</h3>${row.history.map(event=>`<article class="material-event"><strong>${e(approvalStatus[event.status])}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)} · ${purchaseStamp(event.created_at)}</p></article>`).join('')}`;
    $('dialog-content').querySelectorAll('[data-marketing-budget-decision]').forEach(button=>button.onclick=()=>{
      if(guardPending())return;
      const decision=button.dataset.marketingBudgetDecision;
      formDialog(button.textContent,materialReason,form=>({...Object.fromEntries(new FormData(form)),status:decision,expected_revision:row.revision}),
        '/api/marketing-budget-requests/'+encodeURIComponent(row.id)+'/decisions',
        `${row.reference} · ${rupiah(row.amount)}\n${button.textContent}. Keputusan dan alasan tersimpan permanen.`);
    });
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketing-budget-request" data-id="${e(requestId)}">Coba lagi</button>`;}
}

async function purchaseRequestsDialog(orderId=null) {
  if (guardPending()) return;
  const version=epoch;
  openDialog(orderId ? 'PR untuk order ini' : 'Permintaan pembelian',
    `<p class="hint">Pengajuan bahan untuk ditinjau. PR yang disetujui belum menjadi pesanan ke pemasok.</p><div class="actions">${user.role!=='viewer' ? `<button data-action="new-purchase-request" data-id="${e(orderId || '')}">Buat PR</button>` : ''}<button data-action="suppliers">Master pemasok</button><button data-action="purchase-orders">Daftar PO</button><button id="pr-refresh">Muat ulang PR</button></div><div class="filter-form"><div class="form-grid"><div><label for="pr-status">Status PR</label><select id="pr-status"><option value="all">Semua status</option>${Object.entries(purchaseStatus).map(([value,label])=>option(value,label)).join('')}</select></div></div></div><div id="pr-list"></div><p id="pr-error" role="alert" class="error" hidden></p><button id="pr-more">Muat PR berikutnya</button>`);
  const modal=dialogVersion, current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  let before=null, generation=0;
  async function load(reset=false) {
    if(reset){generation++;before=null;$('pr-list').replaceChildren();}
    const gen=generation, button=$('pr-more'); button.disabled=true; message('pr-error','');
    try {
      const rows=await api.get('/api/purchase-requests?'+new URLSearchParams({limit:25,status:$('pr-status').value,...(orderId?{order_id:orderId}:{}),...(before?{before}:{})}));
      if(!current() || gen!==generation)return;
      appendRows('pr-list', rows.map(p=>`<article class="material-event"><h3>${e(p.reference)}</h3><p>${purchaseStatus[p.status]} · dibutuhkan ${date(p.required_date)}</p><p>${e(p.order_reference || 'Permintaan umum')} · ${e(rupiah(p.estimated_value))} estimasi total</p><p class="hint">${e(p.actor_name)} · ${purchaseStamp(p.created_at)}</p><button data-action="purchase-request" data-id="${e(p.id)}" aria-label="Rincian ${e(p.reference)}">Rincian PR</button></article>`).join(''));
      if(!before && !rows.length)$('pr-list').innerHTML='<p class="state">Belum ada PR yang sesuai filter.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;
    }catch(error){if(current() && gen===generation){message('pr-error',error.message,true);clearDialogLoading();button.hidden=false;button.textContent='Coba muat PR lagi';}}
    finally{if(current() && gen===generation)button.disabled=false;}
  }
  $('pr-status').onchange=$('pr-refresh').onclick=()=>load(true);
  $('pr-more').onclick=()=>load();await load();
}

async function purchaseRequestForm(orderId=null) {
  if(guardPending())return;
  const version=epoch;
  openDialog('Buat PR','<p class="state">Memuat bahan dan order…</p>');const modal=dialogVersion;
  try{
    const [materials,orders]=await Promise.all([allRows('/api/materials'),allRows('/api/orders')]);
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(!materials.length){$('dialog-content').innerHTML='<p>Tambahkan master bahan sebelum mengajukan pembelian.</p>';return;}
    formDialog('Buat PR',field('reference','Referensi PR','text','required maxlength="160"')+
      field('required_date','Tanggal dibutuhkan','date','required')+
      `<label>Order produksi<select name="order_id" id="pr-order"><option value="">Permintaan umum</option>${orders.map(o=>option(o.id,o.reference)).join('')}</select></label>`+
      field('estimated_value','Estimasi total (Rp)','number','required min="0.01" max="1000000000000" step="0.01"')+
      '<div class="full"><h3>Bahan yang diminta</h3><div id="pr-lines"></div><button type="button" id="pr-add">Tambah bahan PR</button></div>'+materialReason,
      form=>{
        const data=Object.fromEntries(new FormData(form));
        const lines=[...form.querySelectorAll('#pr-lines .bom-line')].map(row=>({material_id:row.querySelector('select').value,quantity:row.querySelector('input').value}));
        if(new Set(lines.map(l=>l.material_id)).size!==lines.length)throw new Error('Gabungkan bahan yang sama menjadi satu baris.');
        return {...data,order_id:data.order_id || null,lines};
      },'/api/purchase-requests','Isi jumlah yang diajukan dan estimasi total seluruh bahan dalam rupiah. Pengajuan langsung menunggu keputusan admin. Periksa PR terbuka sebelum membuat permintaan tambahan; PR tidak mengurangi angka kekurangan bahan.');
    if(orderId)$('pr-order').value=orderId;
    function addLine(){
      if($('pr-lines').children.length>=100)return;
      const row=document.createElement('div');row.className='bom-line';
      const token=crypto.randomUUID();
      row.innerHTML=`<div><label for="pr-material-${token}">Bahan PR</label><select id="pr-material-${token}" required>${materials.map(m=>option(m.id,`${m.code} · ${m.name} (${m.unit})`)).join('')}</select></div><label>Jumlah bahan PR<input type="number" required max="1000000"></label><button type="button" aria-label="Hapus bahan PR">Hapus</button>`;
      const select=row.querySelector('select'),input=row.querySelector('input');
      select.onchange=()=>{input.step=input.min=materials.find(m=>m.id===select.value).unit==='pcs'?'1':'0.001';};
      select.onchange();
      row.querySelector('button').onclick=()=>{if($('pr-lines').children.length>1)row.remove();else notify('PR memerlukan minimal satu bahan.');};
      $('pr-lines').append(row);
    }
    $('pr-add').onclick=addLine;addLine();
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-purchase-request" data-id="${e(orderId || '')}">Coba lagi</button>`;}
}

async function purchaseRequestDialog(id) {
  if(guardPending())return;
  const version=epoch;
  openDialog('Rincian PR','<p class="state">Memuat permintaan pembelian…</p>');const modal=dialogVersion;
  try{
    const p=await api.get('/api/purchase-requests/'+encodeURIComponent(id));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const decisions=[];
    if(user.role==='admin' && p.status==='submitted')decisions.push(['approved','Setujui PR'],['rejected','Tolak PR']);
    if((user.role==='admin' && ['submitted','approved'].includes(p.status) && !p.purchase_orders.some(po=>!['cancelled','rejected'].includes(po.status))) ||
       (user.role==='operator' && p.actor_id===user.id && p.status==='submitted'))decisions.push(['cancelled','Batalkan PR']);
    $('dialog-content').innerHTML=`<p class="form-info">${e(p.reference)} · ${purchaseStatus[p.status]}</p><p>${e(p.order_reference || 'Permintaan umum')} · dibutuhkan ${date(p.required_date)}</p><p>Estimasi total ${e(rupiah(p.estimated_value))}</p><p class="reason">${e(p.reason)}</p><div>${p.lines.map(l=>`<article class="material-event"><strong>${e(l.code)} · ${e(l.name)}</strong><p>${e(materialQty(l.quantity,l.unit))}</p></article>`).join('')}</div><p class="hint">Persetujuan dicatat oleh admin, termasuk pengajuan sendiri. Belum ada aturan batas nilai. Lihat PO terkait di bawah; PR dengan PO ditutup sudah final; PO aktif harus dibatalkan sebelum PR.</p><div class="actions">${decisions.map(([status,label])=>`<button data-pr-decision="${status}">${label}</button>`).join('')}<button data-action="purchase-request" data-id="${e(id)}">Muat ulang rincian PR</button><button data-action="purchase-requests">Semua PR</button><button data-action="approvals">Inbox approval</button></div><h3>Riwayat keputusan</h3>${p.history.map(event=>`<article class="material-event"><strong>${purchaseStatus[event.status]}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)} · ${purchaseStamp(event.created_at)}</p></article>`).join('')}`;
    $('dialog-content').querySelector('.actions').insertAdjacentHTML('beforeend',
      `${user.role!=='viewer' && p.status==='approved' && !p.purchase_orders.some(po=>!['cancelled','rejected'].includes(po.status)) ? `<button data-action="new-purchase-order" data-id="${e(id)}">Buat PO dari PR</button>` : ''}${p.purchase_orders.map(po=>`<button data-action="purchase-order" data-id="${e(po.id)}">PO ${e(po.reference)} · ${poStatus[po.status]}</button>`).join('')}`);
    $('dialog-content').querySelectorAll('[data-pr-decision]').forEach(button=>{
      button.onclick=()=>{if(guardPending())return;
        formDialog(button.textContent,materialReason,form=>({...Object.fromEntries(new FormData(form)),status:button.dataset.prDecision,expected_revision:p.revision}),
          '/api/purchase-requests/'+encodeURIComponent(id)+'/decisions',
          `${p.reference} · ${rupiah(p.estimated_value)}\n${button.textContent}. Keputusan beserta alasan akan tersimpan. Pengajuan yang ditolak atau dibatalkan tidak dapat dibuka kembali.`);
      };
    });
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="purchase-request" data-id="${e(id)}">Coba lagi</button>`;}
}

async function suppliersDialog() {
  if(guardPending())return;
  const version=epoch;openDialog('Master pemasok','<p class="state">Memuat pemasok…</p>');const modal=dialogVersion;
  try{
    const suppliers=await allRows('/api/suppliers');
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="hint">Identitas pemasok yang dipakai saat membuat PO.</p>${suppliers.map(s=>`<article class="material-event"><h3>${e(s.code)} · ${e(s.name)}</h3><p>${e(s.contact || 'Kontak belum diisi')}</p><p>${e(s.address || 'Alamat belum diisi')}</p><p class="reason">${e(s.reason)}</p><p class="hint">${e(s.actor_name)} · ${purchaseStamp(s.created_at)}</p></article>`).join('') || '<p class="state">Belum ada pemasok.</p>'}${user.role==='admin'?'<button data-action="new-supplier">Tambah pemasok</button>':''}<button data-action="purchase-requests">Semua PR</button>`;
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="suppliers">Coba lagi</button>`;}
}
function supplierForm() {
  if(guardPending())return;
  formDialog('Tambah pemasok',field('code','Kode pemasok','text','required maxlength="160"')+
    field('name','Nama pemasok','text','required maxlength="160"')+field('contact','Kontak pemasok','text','maxlength="500"')+
    '<label class="full">Alamat pemasok<textarea name="address" maxlength="1000"></textarea></label>'+materialReason,
    form=>Object.fromEntries(new FormData(form)),'/api/suppliers',
    'Kode dan identitas pemasok disimpan permanen. Jika keliru, buat kode pemasok baru untuk PO berikutnya.');
}

async function purchaseOrdersDialog() {
  if(guardPending())return;
  const version=epoch;
  openDialog('Daftar PO','<p class="hint">PO menunggu keputusan sebelum aktif. Buka rincian untuk melihat approval, penerimaan bahan, dan sisa pesanan.</p><div class="filter-form"><div class="form-grid"><div><label for="po-status">Status PO</label><select id="po-status"><option value="all">Semua status</option><option value="pending">Menunggu keputusan</option><option value="issued">Aktif</option><option value="rejected">Ditolak</option><option value="closed">Ditutup</option><option value="cancelled">Dibatalkan</option></select></div></div></div><button id="po-refresh">Muat ulang PO</button><div id="po-list"></div><p id="po-error" class="error" role="alert" hidden></p><button id="po-more">Muat PO berikutnya</button>');
  const modal=dialogVersion,current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  let before=null,generation=0;
  async function load(reset=false){
    if(reset){generation++;before=null;$('po-list').replaceChildren();}
    const gen=generation,button=$('po-more');button.disabled=true;message('po-error','');
    try{
      const rows=await api.get('/api/purchase-orders?'+new URLSearchParams({limit:25,status:$('po-status').value,...(before?{before}:{})}));
      if(!current() || gen!==generation)return;
      appendRows('po-list',rows.map(p=>`<article class="material-event"><h3>${e(p.reference)}</h3><p>${e(p.supplier.name)} · ${poStatus[p.status]}</p><p>${e(rupiah(p.total))} · perkiraan datang ${date(p.expected_date)}</p><p>${fulfillmentLabel[p.fulfillment]}${p.lines.some(l=>l.held!=='0.000')?' · Menunggu QC':''}</p><button data-action="purchase-order" data-id="${e(p.id)}" aria-label="Rincian PO ${e(p.reference)}">Rincian PO</button></article>`).join(''));
      if(!before && !rows.length)$('po-list').innerHTML='<p class="state">Belum ada PO yang sesuai filter.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;
    }catch(error){if(current() && gen===generation){message('po-error',error.message,true);clearDialogLoading();button.hidden=false;}}
    finally{if(current() && gen===generation)button.disabled=false;}
  }
  $('po-status').onchange=$('po-refresh').onclick=()=>load(true);$('po-more').onclick=()=>load();await load();
}

async function purchaseOrderForm(requestId) {
  if(guardPending())return;
  const version=epoch;openDialog('Buat PO dari PR','<p class="state">Memuat PR dan pemasok…</p>');const modal=dialogVersion;
  try{
    const [pr,suppliers]=await Promise.all([api.get('/api/purchase-requests/'+encodeURIComponent(requestId)),allRows('/api/suppliers')]);
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    if(pr.status!=='approved' || pr.purchase_orders.some(po=>!['cancelled','rejected'].includes(po.status))){$('dialog-content').innerHTML='<p>PR belum disetujui atau sudah memiliki PO yang menunggu, aktif, atau ditutup. Buka ulang rincian PR.</p>';return;}
    if(!suppliers.length){$('dialog-content').innerHTML='<p>Tambahkan pemasok sebelum membuat PO.</p><button data-action="new-supplier">Tambah pemasok</button>';return;}
    formDialog('Buat PO dari PR',field('reference','Referensi PO','text','required maxlength="160"')+
      `<label>Pemasok PO<select name="supplier_id" required>${suppliers.map(s=>option(s.id,s.code+' · '+s.name)).join('')}</select></label>`+
      field('expected_date','Perkiraan tanggal datang','date','required')+
      '<label class="full">Syarat pembelian<textarea name="terms" required maxlength="1000"></textarea></label>'+
      `<div class="full" id="po-prices">${pr.lines.map(l=>`<article class="material-event"><h3>${e(l.code)} · ${e(materialQty(l.quantity,l.unit))}</h3><label>Harga satuan ${e(l.code)} (Rp/${e(l.unit)})<input data-price-material="${e(l.material_id)}" type="number" required min="0.01" max="1000000000" step="0.01"></label></article>`).join('')}<p id="po-total" role="status">Isi harga semua bahan untuk melihat total.</p></div>`+materialReason,
      form=>({...Object.fromEntries(new FormData(form)),request_id:pr.id,expected_revision:pr.revision,
        prices:[...form.querySelectorAll('[data-price-material]')].map(input=>({material_id:input.dataset.priceMaterial,unit_price:input.value}))}),
      '/api/purchase-orders',`${pr.reference} · batas nilai ${rupiah(pr.estimated_value)}\nSeluruh jumlah PR dibeli dari satu pemasok. Harga, jumlah dan syarat akan terkunci saat diajukan. PO menunggu approval admin dan belum boleh menerima bahan.`);
    $('po-prices').oninput=()=>{
      const inputs=[...$('po-prices').querySelectorAll('input')];
      if(inputs.some(i=>!i.validity.valid || !/^[0-9]+(\.[0-9]{1,2})?$/.test(i.value))){$('po-total').textContent='Isi harga semua bahan untuk melihat total.';return;}
      const total=inputs.reduce((sum,input)=>{
        const qty=pr.lines.find(l=>l.material_id===input.dataset.priceMaterial).quantity.replace('.','');
        const [whole,fraction='']=input.value.split('.');
        return sum+(BigInt(qty)*(BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0')))+500n)/1000n;
      },0n);
      const value=String(total/100n)+'.'+String(total%100n).padStart(2,'0');
      $('po-total').textContent='Total PO '+rupiah(value)+(total>BigInt(pr.estimated_value.replace('.',''))?' · Melebihi nilai PR yang disetujui.':'');
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-purchase-order" data-id="${e(requestId)}">Coba lagi</button>`;}
}

const poStatus={pending:'Menunggu keputusan',issued:'Aktif',rejected:'Ditolak',cancelled:'Dibatalkan',closed:'Ditutup'};
const fulfillmentLabel={pending:'Belum diterima',partial:'Diterima sebagian',received:'Diterima lengkap'};

function qualityIntakesHTML(p) {
  return `<h3>QC bahan masuk</h3><p class="hint">Hold belum dapat dipakai atau direservasi. Reject membuka kebutuhan pengganti. Catat retur setelah bahan reject dikirim kembali ke pemasok.</p>${user.role!=='viewer' && p.status==='issued' && p.lines.some(l=>l.receivable!=='0.000')?`<button data-action="qc-intake-form" data-id="${e(p.id)}">Catat kedatangan untuk QC</button>`:''}${p.qc_intakes.map(q=>`<article class="material-event"><h4>${e(q.reference)} · ${e(q.code)}</h4><p>${q.cancellation?'Kedatangan dibatalkan':`Hold ${e(materialQty(q.held,q.unit))} · layak ${e(materialQty(q.accepted,q.unit))} · reject ${e(materialQty(q.rejected,q.unit))}`}</p><button data-action="qc-intake" data-id="${e(q.id)}">Rincian QC ${e(q.reference)}</button></article>`).join('') || '<p>Belum ada kedatangan untuk QC.</p>'}`;
}

async function qualityIntakeDialog(id) {
  if(guardPending())return;
  const version=epoch;openDialog('QC bahan masuk','<p class="state">Memuat pemeriksaan…</p>');const modal=dialogVersion;
  try {
    const q=await api.get('/api/qc-intakes/'+encodeURIComponent(id));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const active=!q.cancellation && !q.po_cancelled && !q.po_closed, admin=user.role==='admin';
    $('dialog-content').innerHTML=`<p class="form-info">${e(q.reference)} · ${e(q.code)} · ${e(q.name)}</p><p>Datang ${e(materialQty(q.quantity,q.unit))} · ${date(q.received_date)} · ${e(q.location)}</p><p class="reason">${e(q.reason)}</p><p class="hint">${e(q.actor_name)} · ${purchaseStamp(q.created_at)}</p><dl class="requirement-values">${[['Hold','held'],['Layak pakai','accepted'],['Reject','rejected'],['Sudah diretur','returned'],['Belum diretur','return_pending']].map(([label,key])=>`<div><dt>${label}</dt><dd>${e(materialQty(q[key],q.unit))}</dd></div>`).join('')}</dl>${q.cancellation?`<p>Kedatangan dibatalkan</p><p class="reason">${e(q.cancellation.reason)}</p><p class="hint">${e(q.cancellation.actor_name)} · ${purchaseStamp(q.cancellation.created_at)}</p>`:''}<div class="actions"><button data-action="purchase-order" data-id="${e(q.purchase_order_id)}">PO ${e(q.purchase_order_reference)}</button>${active && admin && q.held!=='0.000'?'<button id="qc-accept">Terima layak pakai</button><button id="qc-reject">Tolak bahan</button>':''}${active && admin && q.accepted==='0.000' && q.rejected==='0.000'?'<button id="qc-cancel">Batalkan kedatangan</button>':''}</div><h3>Riwayat pemeriksaan</h3>${q.history.map(d=>`<article class="material-event"><h4>${d.reversal_of?'Koreksi ':''}${d.kind==='accept'?'Layak pakai':'Reject'} · ${e(materialQty(d.quantity,q.unit))}</h4><p class="reason">${e(d.reason)}</p><p class="hint">${e(d.actor_name)} · ${purchaseStamp(d.created_at)}</p>${d.reversed_by?'<p>Keputusan sudah dikoreksi</p>':''}${d.batch_id?`<button data-action="material-batch" data-id="${e(d.batch_id)}">Batch ${e(d.batch_reference)}</button>`:''}${active && admin && !d.reversal_of && !d.reversed_by && (d.kind==='accept' || Number(d.quantity)<=Number(q.return_pending))?`<button data-qc-reverse="${e(d.id)}">Koreksi keputusan</button>`:''}</article>`).join('') || '<p>Belum ada keputusan QC.</p>'}`;
    renderSupplierReturns(q);
    for(const kind of ['accept','reject'])if($('qc-'+kind))$('qc-'+kind).onclick=()=>qualityDecisionForm(q,kind);
    if($('qc-cancel'))$('qc-cancel').onclick=()=>{if(guardPending())return;formDialog('Batalkan kedatangan QC',materialReason,form=>Object.fromEntries(new FormData(form)),
      '/api/qc-intakes/'+encodeURIComponent(id)+'/cancel',`${q.reference}\nBatalkan hanya catatan kedatangan yang keliru. Pembatalan melepaskan seluruh jumlah hold dari PO.`);};
    $('dialog-content').querySelectorAll('[data-qc-reverse]').forEach(button=>button.onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi keputusan QC',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/qc-decisions/'+encodeURIComponent(button.dataset.qcReverse)+'/reverse',
        `${q.reference}\nSeluruh jumlah keputusan kembali ke hold. Koreksi layak pakai menarik stok batch; stok harus masih utuh dan tidak direservasi. Koreksi reject memerlukan jatah PO yang belum diisi pengganti. Pastikan barang fisiknya sesuai.`);
    });
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="qc-intake" data-id="${e(id)}">Coba lagi</button>`;}
}

function renderSupplierReturns(q) {
  const writable=user.role==='admin' && !q.cancellation && !q.po_closed;
  $('dialog-content').insertAdjacentHTML('beforeend', `<h3>Retur ke pemasok</h3>
    <p class="hint">Catat barang reject yang sudah dikirim kembali. Jumlah retur tidak mengubah stok layak pakai atau jatah pengganti PO.</p>
    ${q.po_closed?'<p>PO sudah ditutup. Riwayat retur sudah final.</p>':''}
    ${writable && q.return_pending!=='0.000'?'<button id="supplier-return">Catat retur supplier</button>':''}
    ${q.returns.map(r=>`<article class="material-event"><h4>${r.reversal_of?'Koreksi retur':'Retur'} ${e(r.reference || r.original_reference)} · ${e(materialQty(r.quantity,q.unit))}</h4>
      ${r.returned_date?`<p>Dikirim ${date(r.returned_date)}</p>`:''}<p class="reason">${e(r.reason)}</p>
      <p class="hint">${e(r.actor_name)} · ${purchaseStamp(r.created_at)}</p>${r.reversed_by?'<p>Retur sudah dikoreksi</p>':''}
      ${writable && !q.po_cancelled && !r.reversed_by && !r.reversal_of?`<button data-return-reverse="${e(r.id)}">Koreksi retur</button>`:''}</article>`).join('') || '<p>Belum ada pengiriman retur.</p>'}`);
  if($('supplier-return'))$('supplier-return').onclick=()=>{
    if(guardPending())return;
    formDialog('Catat retur supplier',
      field('reference','Referensi pengiriman retur','text','required maxlength="160"')+
      field('returned_date','Tanggal dikirim kembali','date',`required min="${e(q.received_date)}"`)+
      field('quantity','Jumlah retur','number',`required min="${q.unit==='pcs'?'1':'0.001'}" step="${q.unit==='pcs'?'1':'0.001'}" max="${e(q.return_pending)}"`)+materialReason,
      form=>Object.fromEntries(new FormData(form)), '/api/qc-intakes/'+encodeURIComponent(q.id)+'/returns',
      `${q.purchase_order_reference} · kedatangan ${q.reference}\nReject belum diretur: ${materialQty(q.return_pending,q.unit)}. Isi referensi pengiriman fisik ke pemasok PO ini.`);
  };
  $('dialog-content').querySelectorAll('[data-return-reverse]').forEach(button=>button.onclick=()=>{
    if(guardPending())return;
    const item=q.returns.find(r=>r.id===button.dataset.returnReverse);
    formDialog('Koreksi retur',materialReason,form=>Object.fromEntries(new FormData(form)),
      '/api/supplier-returns/'+encodeURIComponent(item.id)+'/reverse',
      `${item.reference} · ${materialQty(item.quantity,q.unit)}\nSeluruh jumlah catatan ini kembali menjadi reject belum diretur. Pastikan barang fisik sesuai; untuk jumlah baru, catat retur baru setelah koreksi.`);
  });
}

function renderPOClosure(p) {
  if(p.closure) {
    $('dialog-content').insertAdjacentHTML('beforeend', `<article class="material-event"><h3>Penutupan PO</h3>
      <p class="reason">${e(p.closure.reason)}</p><p class="hint">${e(p.closure.actor_name)} · ${purchaseStamp(p.closure.created_at)}</p>
      <p>Sisa tidak akan diterima. Penerimaan, QC, dan retur sudah final; stok layak pakai tetap dapat digunakan untuk produksi.</p></article>`);
  } else if(user.role==='admin' && p.status==='issued' && p.fulfillment!=='pending') {
    const ready=p.lines.every(l=>l.held==='0.000' && l.return_pending==='0.000');
    $('dialog-content').insertAdjacentHTML('beforeend', ready?'<button id="po-close">Tutup PO</button>':'<p>Selesaikan hold QC dan retur bahan reject sebelum menutup PO.</p>');
    if(ready)$('po-close').onclick=()=>{
      if(guardPending())return;
      formDialog('Tutup PO',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/purchase-orders/'+encodeURIComponent(p.id)+'/close',
        `${p.reference}\n${p.lines.map(l=>`${l.code}: diterima ${materialQty(l.received,l.unit)}, sisa tidak diterima ${materialQty(l.remaining,l.unit)}`).join('\n')}\nPenutupan permanen menghentikan penerimaan dan koreksi QC/retur. Jumlah serta nilai PO asal tetap tersimpan. Pastikan jumlah di atas sudah sesuai kesepakatan dengan pemasok.`);
    };
  }
}

function qualityDecisionForm(q,kind) {
  if(guardPending())return;
  formDialog(kind==='accept'?'Terima layak pakai':'Tolak bahan',
    field('quantity','Jumlah keputusan','number',`required min="${q.unit==='pcs'?'1':'0.001'}" step="${q.unit==='pcs'?'1':'0.001'}" max="${e(q.held)}"`)+
    (kind==='accept'?field('reference','Referensi batch layak pakai','text','required maxlength="160"')+field('location','Lokasi stok layak pakai','text','required maxlength="160"'):'')+materialReason,
    form=>({...Object.fromEntries(new FormData(form)),kind}), '/api/qc-intakes/'+encodeURIComponent(q.id)+'/decisions',
    `${q.reference} · hold ${materialQty(q.held,q.unit)}\n${kind==='accept'?'Jumlah ini masuk stok siap pakai dalam batch baru.':'Jumlah ini tetap di luar stok siap pakai. Kebutuhan pengganti pada PO dibuka kembali; retur fisik dicatat terpisah.'} Sisa yang belum diputuskan tetap hold.`);
}

function purchaseReceiptsHTML(p) {
  return `<h3>Penerimaan bahan</h3><p class="hint">Jumlah diterima adalah bahan layak pakai, dikurangi penerimaan yang dikoreksi. Pengeluaran ke produksi tidak mengurangi jumlah diterima pada PO.</p>${user.role!=='viewer' && p.status==='issued' && p.lines.some(l=>l.receivable!=='0.000')?`<button data-action="receive-po" data-id="${e(p.id)}">Terima bahan dari PO</button>`:''}${p.receipts.map(r=>{
    const line=p.lines.find(l=>l.material_id===r.material_id);
    return `<article class="material-event"><h4>${e(r.reference)} · ${e(line.code)}</h4><p>${e(materialQty(r.quantity,line.unit))} · ${e(r.location)} · diterima ${date(r.received_date)}</p><p>${r.reversed_by?'Penerimaan dikoreksi':'Penerimaan aktif'}</p><p class="reason">${e(r.reason)}</p><p class="hint">${e(r.actor_name)} · ${purchaseStamp(r.created_at)}</p><button data-action="material-batch" data-id="${e(r.batch_id)}">Riwayat batch ${e(r.reference)}</button></article>`;
  }).join('') || '<p>Belum ada penerimaan.</p>'}`;
}

async function purchaseReceiptForm(id, forQC=false) {
  if(guardPending())return;
  const title=forQC?'Catat kedatangan untuk QC':'Terima bahan dari PO';
  const version=epoch;openDialog(title,'<p class="state">Memuat sisa pesanan…</p>');const modal=dialogVersion;
  try {
    const po=await api.get('/api/purchase-orders/'+encodeURIComponent(id));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const lines=po.lines.filter(l=>l.receivable!=='0.000');
    if(po.status!=='issued' || !lines.length){$('dialog-content').innerHTML='<p>PO sudah dibatalkan, ditutup, atau seluruh bahan sudah diterima.</p>';return;}
    formDialog(title,
      `<div class="full"><label for="po-receipt-material">Bahan dari PO</label><select id="po-receipt-material" name="material_id">${lines.map(l=>option(l.material_id,`${l.code} · sisa ${materialQty(l.receivable,l.unit)}`)).join('')}</select></div>`+
      field('reference',forQC?'Referensi kedatangan':'Referensi batch','text','required maxlength="160"')+
      field('location',forQC?'Lokasi hold':'Lokasi / rak','text','required maxlength="160"')+
      field('received_date','Tanggal diterima','date','required')+
      field('quantity',forQC?'Jumlah datang':'Jumlah layak pakai','number','required id="po-receipt-quantity"')+materialReason,
      form=>Object.fromEntries(new FormData(form)), '/api/purchase-orders/'+encodeURIComponent(id)+(forQC?'/qc-intakes':'/receipts'),
      forQC?`${po.reference} · ${po.supplier.name}\nSemua jumlah datang menunggu QC sebagai hold. Belum masuk stok siap pakai. Admin memutuskan layak pakai atau reject setelah pemeriksaan.`:`${po.reference} · ${po.supplier.name}\nCatat satu bahan dan satu batch yang benar-benar diterima layak pakai. Penerimaan langsung menambah stok di lokasi ini. Untuk kiriman berikutnya, catat batch baru. Barang hold atau reject belum dicatat di sini.`);
    const update=()=>{
      const line=lines.find(l=>l.material_id===$('po-receipt-material').value), input=$('po-receipt-quantity');
      input.max=line.receivable;input.step=input.min=line.unit==='pcs'?'1':'0.001';
    };
    $('po-receipt-material').onchange=update;update();
  } catch(error) {
    if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="${forQC?'qc-intake-form':'receive-po'}" data-id="${e(id)}">Coba lagi</button>`;
  }
}

async function purchaseOrderDialog(id) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian PO','<p class="state">Memuat PO…</p>');const modal=dialogVersion;
  try{
    const [p,payments]=await Promise.all([
      api.get('/api/purchase-orders/'+encodeURIComponent(id)),
      api.get('/api/purchase-orders/'+encodeURIComponent(id)+'/payment-requests?limit=100')
    ]);
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    const approvalButtons=[];
    if(user.role==='admin'&&p.approval_status==='submitted')approvalButtons.push(['approved','Setujui penerbitan PO'],['rejected','Tolak PO']);
    if(p.approval_status==='submitted'&&(user.role==='admin'||p.actor_id===user.id))approvalButtons.push(['cancelled','Batalkan pengajuan PO']);
    $('dialog-content').innerHTML=`<p class="form-info">${e(p.reference)} · ${poStatus[p.status]}</p><h3>${e(p.supplier.code)} · ${e(p.supplier.name)}</h3><p>${e(p.supplier.contact)} · ${e(p.supplier.address)}</p><p>Perkiraan datang ${date(p.expected_date)}</p><p class="reason">Syarat: ${e(p.terms)}</p>${p.lines.map(l=>`<article class="material-event"><strong>${e(l.code)} · ${e(l.name)}</strong><p>${e(materialQty(l.quantity,l.unit))} × ${e(rupiah(l.unit_price))}/${e(l.unit)}</p><p>Nilai baris ${e(rupiah(l.line_total))}</p><p>Diterima ${e(materialQty(l.received,l.unit))} · sisa layak pakai ${e(materialQty(l.remaining,l.unit))}</p><p>Hold ${e(materialQty(l.held,l.unit))} · reject ${e(materialQty(l.rejected,l.unit))} · bisa datang ${e(materialQty(l.receivable,l.unit))}</p><p>Diretur ${e(materialQty(l.returned,l.unit))} · belum diretur ${e(materialQty(l.return_pending,l.unit))}</p></article>`).join('')}<p><strong>Total PO ${e(rupiah(p.total))}</strong></p><p class="reason">${e(p.reason)}</p><p class="hint">Diajukan ${e(p.actor_name)} · ${purchaseStamp(p.created_at)}.</p>${p.status==='pending'?'<p class="hint">Penerimaan dan QC baru tersedia setelah admin menyetujui penerbitan PO.</p>':''}<p>${fulfillmentLabel[p.fulfillment]}</p>${p.cancellation?`<article class="material-event"><h3>Pembatalan PO</h3><p class="reason">${e(p.cancellation.reason)}</p><p>${e(p.cancellation.actor_name)} · ${purchaseStamp(p.cancellation.created_at)}</p></article>`:''}<div class="actions">${approvalButtons.map(([status,label])=>`<button data-po-decision="${status}">${label}</button>`).join('')}<button data-action="purchase-request" data-id="${e(p.request_id)}">PR ${e(p.request_reference)}</button><button data-action="purchase-orders">Daftar PO</button><button data-action="approvals">Inbox approval</button>${user.role==='admin' && p.status==='issued' && p.fulfillment==='pending' && p.lines.every(l=>l.held==='0.000' && l.return_pending==='0.000')?'<button id="po-cancel">Batalkan PO</button>':''}</div><h3>Pembayaran supplier</h3><p>Menunggu approval ${e(rupiah(p.payment_pending))} · disetujui ${e(rupiah(p.payment_approved))} · sisa ${e(rupiah(p.payment_remaining))}</p><p class="hint">Approved berarti siap dibayar. Transfer bank dan jurnal akuntansi belum dijalankan aplikasi.</p>${user.role!=='viewer'&&['issued','closed'].includes(p.status)&&p.fulfillment!=='pending'&&p.payment_remaining!=='0.00'?`<button data-action="new-supplier-payment" data-id="${e(p.id)}">Ajukan pembayaran supplier</button>`:''}${payments.map(row=>`<article class="material-event"><h4>${e(row.reference)} · ${e(approvalStatus[row.status])}</h4><p>Invoice ${e(row.invoice_reference)} · ${e(rupiah(row.amount))} · jatuh tempo ${date(row.due_date)}</p><button data-action="supplier-payment-request" data-id="${e(row.id)}" aria-label="Rincian pembayaran ${e(row.reference)}">Rincian pembayaran</button></article>`).join('')||'<p>Belum ada pengajuan pembayaran.</p>'}<h3>Riwayat approval PO</h3>${p.approval_history.map(event=>`<article class="material-event"><strong>${e(approvalStatus[event.status])}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)} · ${purchaseStamp(event.created_at)}</p></article>`).join('')}`;
    renderPOClosure(p);
    $('dialog-content').insertAdjacentHTML('beforeend', qualityIntakesHTML(p)+purchaseReceiptsHTML(p));
    if($('po-cancel'))$('po-cancel').onclick=()=>{if(guardPending())return;formDialog('Batalkan PO',materialReason,form=>Object.fromEntries(new FormData(form)),
      '/api/purchase-orders/'+encodeURIComponent(id)+'/cancel',`${p.reference} · ${rupiah(p.total)}\nPembatalan seluruh PO disimpan permanen. Pastikan pembelian memang dibatalkan; aplikasi tidak mengirim pemberitahuan ke pemasok.`);};
    $('dialog-content').querySelectorAll('[data-po-decision]').forEach(button=>button.onclick=()=>{
      if(guardPending())return;
      const decision=button.dataset.poDecision;
      formDialog(button.textContent,materialReason,form=>({...Object.fromEntries(new FormData(form)),status:decision,expected_revision:p.revision}),
        '/api/purchase-orders/'+encodeURIComponent(id)+'/decisions',
        `${p.reference} · ${rupiah(p.total)}\n${button.textContent}. Keputusan dan alasan tersimpan permanen.${decision==='approved'?' PO menjadi aktif dan dapat menerima bahan setelah persetujuan tersimpan.':''}`);
    });
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="purchase-order" data-id="${e(id)}">Coba lagi</button>`;}
}

async function supplierPaymentForm(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Ajukan pembayaran supplier','<p class="state">Memuat PO…</p>');const modal=dialogVersion;
  try{
    const po=await api.get('/api/purchase-orders/'+encodeURIComponent(orderId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    if(!['issued','closed'].includes(po.status)||po.fulfillment==='pending'||po.payment_remaining==='0.00'){
      $('dialog-content').innerHTML='<p>PO belum mempunyai penerimaan aktif atau seluruh nilainya sudah diajukan.</p>';return;
    }
    formDialog('Ajukan pembayaran supplier',
      field('reference','Referensi pengajuan','text','required maxlength="160"')+
      field('invoice_reference','Referensi invoice supplier','text','required maxlength="160"')+
      field('invoice_date','Tanggal invoice','date','required')+
      field('due_date','Tanggal jatuh tempo','date','required')+
      field('amount','Nominal pembayaran (Rp)','number',`required min="0.01" max="${e(po.payment_remaining)}" step="0.01"`)+materialReason,
      form=>Object.fromEntries(new FormData(form)),
      '/api/purchase-orders/'+encodeURIComponent(orderId)+'/payment-requests',
      `${po.reference} · ${po.supplier.name}\nSisa nilai yang dapat diajukan ${rupiah(po.payment_remaining)}. Pengajuan menunggu approval dan belum memindahkan dana.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-supplier-payment" data-id="${e(orderId)}">Coba lagi</button>`;}
}

async function supplierPaymentRequestDialog(requestId) {
  if(guardPending())return;
  const version=epoch;openDialog('Approval pembayaran supplier','<p class="state">Memuat pengajuan…</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/supplier-payment-requests/'+encodeURIComponent(requestId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    const buttons=[];
    if(user.role==='admin'&&row.status==='submitted')buttons.push(['approved','Setujui pembayaran'],['rejected','Tolak pembayaran']);
    if(row.status==='submitted'&&(user.role==='admin'||row.actor_id===user.id))buttons.push(['cancelled','Batalkan pengajuan']);
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${e(approvalStatus[row.status])}</p><h3>${e(row.supplier.code)} · ${e(row.supplier.name)}</h3><p>PO ${e(row.purchase_order_reference)} · invoice ${e(row.invoice_reference)}</p><p>Tanggal invoice ${date(row.invoice_date)} · jatuh tempo ${date(row.due_date)}</p><p><strong>${e(rupiah(row.amount))}</strong></p><p class="reason">${e(row.reason)}</p><p class="hint">Diajukan ${e(row.actor_name)} · ${purchaseStamp(row.created_at)}. Persetujuan tidak menjalankan transfer bank.</p><div class="actions">${buttons.map(([status,label])=>`<button data-payment-decision="${status}">${label}</button>`).join('')}<button data-action="purchase-order" data-id="${e(row.purchase_order_id)}">Buka PO</button><button data-action="approvals">Inbox approval</button></div><h3>Riwayat keputusan</h3>${row.history.map(event=>`<article class="material-event"><strong>${e(approvalStatus[event.status])}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)} · ${purchaseStamp(event.created_at)}</p></article>`).join('')}`;
    $('dialog-content').querySelectorAll('[data-payment-decision]').forEach(button=>button.onclick=()=>{
      if(guardPending())return;
      const decision=button.dataset.paymentDecision;
      formDialog(button.textContent,materialReason,form=>({...Object.fromEntries(new FormData(form)),status:decision,expected_revision:row.revision}),
        '/api/supplier-payment-requests/'+encodeURIComponent(row.id)+'/decisions',
        `${row.reference} · ${rupiah(row.amount)}\n${button.textContent}. Keputusan dan alasan tersimpan permanen. Persetujuan menandai request siap dibayar tanpa menjalankan transfer.`);
    });
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="supplier-payment-request" data-id="${e(requestId)}">Coba lagi</button>`;}
}

const materialReason = '<label class="full">Alasan / catatan<textarea name="reason" required maxlength="1000"></textarea></label>';

function materialBatchScanDialog() {
  if(guardPending())return;
  openDialog('Scan batch bahan',`<form id="material-batch-scan-form"><p class="form-info">Pindai QR pada label bahan atau masukkan referensi batch. Scanner USB/Bluetooth dapat digunakan seperti keyboard lalu tekan Enter.</p><label for="material-batch-scan-code">Kode batch bahan</label><input id="material-batch-scan-code" name="code" required maxlength="200" autocomplete="off" spellcheck="false" autofocus><p id="material-batch-scan-error" class="error" role="alert" hidden></p><div class="form-actions"><button type="button" data-action="cancel-form">Batal</button><button class="primary" type="submit">Buka batch</button></div></form>`);
  const modal=dialogVersion,input=$('material-batch-scan-code');input.focus();
  $('material-batch-scan-form').onsubmit=async event=>{
    event.preventDefault();if(modalBusy)return;
    const button=event.currentTarget.querySelector('[type="submit"]');modalBusy=true;button.disabled=true;message('material-batch-scan-error','');
    try{
      const batch=await api.get('/api/material-batches/scan?'+new URLSearchParams({code:input.value}));
      if(modal!==dialogVersion||!$('dialog').open)return;
      modalBusy=false;$('dialog').close();materialHistoryDialog(batch.id);
    }catch(error){if(modal===dialogVersion&&$('dialog').open){modalBusy=false;button.disabled=false;message('material-batch-scan-error',error.message,true);input.focus();}}
  };
}

function finishedGoodsScanDialog() {
  if(guardPending())return;
  openDialog('Scan barang jadi',`<form id="finished-goods-scan-form"><p class="form-info">Pindai QR pada label penerimaan barang jadi atau masukkan referensinya. Scanner USB/Bluetooth dapat digunakan seperti keyboard lalu tekan Enter.</p><label for="finished-goods-scan-code">Kode barang jadi</label><input id="finished-goods-scan-code" name="code" type="search" required maxlength="200" autocomplete="off" autocapitalize="characters" spellcheck="false" autofocus><p id="finished-goods-scan-error" class="error" role="alert" hidden></p><div class="form-actions"><button type="button" data-action="cancel-form">Batal</button><button class="primary" type="submit">Buka barang jadi</button></div></form>`);
  const modal=dialogVersion,version=epoch,form=$('finished-goods-scan-form'),input=$('finished-goods-scan-code');input.focus();
  form.onsubmit=async event=>{
    event.preventDefault();const button=form.querySelector('[type="submit"]');button.disabled=true;message('finished-goods-scan-error','');
    try{
      const receipt=await api.get('/api/finished-goods-receipts/scan?'+new URLSearchParams({code:input.value.trim()}));
      if(version===epoch&&modal===dialogVersion&&$('dialog').open)finishedGoodsReceiptDialog(receipt.id);
    }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open){message('finished-goods-scan-error',error.message,true);input.select();}}
    finally{if(version===epoch&&modal===dialogVersion&&$('dialog').open)button.disabled=false;}
  };
}

async function loadMaterials() {
  const version = epoch, request = ++materialsRequest, materialId = $('material-filter').value;
  message('materials-message','Memuat stok bahan…'); $('batch-list').replaceChildren(); $('materials-page').textContent = '';
  $('materials-previous').disabled = true; $('materials-next').disabled = true;
  try {
    const [materials,batches] = await Promise.all([allRows('/api/materials'), api.get('/api/material-batches?'+new URLSearchParams({limit:26,offset:materialsOffset,material_id:materialId}))]);
    if (version !== epoch || request !== materialsRequest || view !== 'materials') return;
    $('material-filter').innerHTML = option('','Semua bahan')+materials.map(m => option(m.id,`${m.code} · ${m.name} (${m.unit})`)).join('');
    $('material-filter').value = materialId;
    message('materials-message',batches.length ? '' : 'Belum ada batch pada halaman ini. Terima bahan untuk mulai mencatat stok.');
    $('batch-list').innerHTML = batches.slice(0,25).map(b => `<article class="sku-block"><div class="sku-heading"><div><span class="reference">${e(b.code)} · ${e(b.name)}</span><h2><button class="order-title" data-action="material-batch" data-id="${e(b.id)}">${e(b.reference)}</button></h2><p class="hint">${e(b.supplier)} · ${e(b.location)} · diterima ${date(b.received_date)}</p></div><div>Saldo batch<strong class="material-balance">${e(materialQty(b.balance,b.unit))}</strong><p class="hint">Direservasi ${e(materialQty(b.reserved,b.unit))}<br>Bebas ${e(materialQty(b.available,b.unit))}</p></div></div></article>`).join('');
    $('materials-page').textContent = batches.length ? `Batch ${materialsOffset+1}–${materialsOffset+Math.min(25,batches.length)}` : '0 batch di halaman ini';
    $('materials-previous').disabled = materialsOffset === 0; $('materials-next').disabled = batches.length <= 25;
  } catch (error) { if (version === epoch && request === materialsRequest && view === 'materials') fail(error,'materials-message'); }
}

async function materialMasterDialog() {
  if (guardPending()) return;
  const version = epoch; openDialog('Master bahan','<p class="state">Memuat master bahan…</p>'); const modal = dialogVersion;
  try {
    const materials = await allRows('/api/materials');
    if (version !== epoch || modal !== dialogVersion || !$('dialog').open) return;
    $('dialog-content').innerHTML = `<div class="product-list">${materials.length ? materials.map(m => `<div class="product-item"><div><strong>${e(m.code)}</strong><span>${e(m.name)} · ${e(m.unit)}</span></div></div>`).join('') : '<p>Belum ada bahan. Admin dapat menambahkan master pertama.</p>'}</div>${user.role === 'admin' ? '<button class="primary" data-action="new-material">Tambah bahan</button>' : ''}`;
  } catch (error) { if (version === epoch && modal === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="material-master">Coba lagi</button>`; }
}
function materialForm() {
  if (guardPending()) return;
  formDialog('Tambah bahan',field('code','Kode bahan','text','required maxlength="160"')+field('name','Nama bahan','text','required maxlength="160"')+
    '<div><label for="material-unit">Satuan dasar</label><select id="material-unit" name="unit"><option value="m">Meter (m)</option><option value="kg">Kilogram (kg)</option><option value="pcs">Buah (pcs)</option></select></div>',
    form => Object.fromEntries(new FormData(form)), '/api/materials','Satu kode untuk setiap jenis bahan. Kode, nama, dan satuan tidak dapat diubah setelah disimpan.');
}
async function receiptForm() {
  if (guardPending()) return;
  const version = epoch; openDialog('Terima batch bahan','<p class="state">Memuat bahan…</p>'); const modal = dialogVersion;
  try {
    const materials = await allRows('/api/materials');
    if (version !== epoch || modal !== dialogVersion || !$('dialog').open) return;
    if (!materials.length) { $('dialog-content').innerHTML = '<p>Master bahan belum tersedia. Admin perlu menambahkannya terlebih dahulu.</p>'; return; }
    formDialog('Terima batch bahan',`<div><label for="receipt-material">Bahan diterima</label><select name="material_id" id="receipt-material">${materials.map(m => option(m.id,`${m.code} · ${m.name} (${m.unit})`)).join('')}</select></div>`+
      field('reference','Referensi batch','text','required maxlength="160"')+field('supplier','Pemasok','text','required maxlength="160"')+field('location','Lokasi / rak','text','required maxlength="160"')+
      field('received_date','Tanggal diterima','date','required')+field('quantity','Jumlah layak pakai','number','required min="0.001" max="1000000" step="0.001" id="receipt-quantity"')+materialReason,
      form => Object.fromEntries(new FormData(form)), '/api/material-batches','Catat hanya bahan layak pakai yang benar-benar diterima. Gunakan referensi unik tiap batch. Jumlah mengikuti satuan bahan; maksimal tiga desimal, pcs harus bulat.');
    const updateUnit = () => { const m = materials.find(m => m.id === $('receipt-material').value); $('receipt-quantity').step = $('receipt-quantity').min = m.unit === 'pcs' ? '1' : '0.001'; };
    $('receipt-material').onchange = updateUnit; updateUnit();
  } catch (error) { if (version === epoch && modal === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="receive-material">Coba lagi</button>`; }
}
async function materialIssueForm() {
  if (guardPending()) return;
  const version = epoch, order = selected;
  openDialog('Keluarkan bahan ke order','<p class="state">Memuat saldo batch…</p>'); const modal = dialogVersion;
  try {
    const batches = (await allRows('/api/material-batches',{order_id:order.id})).filter(b => Number(b.available_to_order)>0);
    if (version !== epoch || modal !== dialogVersion || !$('dialog').open) return;
    if (!batches.length) { $('dialog-content').innerHTML = '<p>Belum ada bahan yang dapat dikeluarkan untuk order ini. Periksa penerimaan dan reservasi order lain.</p>'; return; }
    formDialog('Keluarkan bahan ke order',`<div class="full"><label for="issue-batch">Batch bahan</label><select id="issue-batch" name="batch_id">${batches.map(b => option(b.id,`${b.reference} · ${b.code} · ${b.location} · bisa dipakai ${materialQty(b.available_to_order,b.unit)} · jatah sendiri ${materialQty(b.reserved_for_order,b.unit)}`)).join('')}</select></div>`+
      field('quantity','Jumlah dikeluarkan','number','required min="0.001" max="1000000" step="0.001" id="material-issue-quantity"')+materialReason,
      form => ({...Object.fromEntries(new FormData(form)),order_id:order.id}), '/api/material-issues',`${order.reference} · ${order.title}\nCatat jumlah yang benar-benar dikeluarkan dari rak. Pengeluaran ini tidak mengubah pcs atau tahap produksi, dan belum berarti konsumsi aktual. Reservasi order ini dipakai terlebih dahulu, lalu stok bebas.`);
    const updateUnit = () => { const b = batches.find(b => b.id === $('issue-batch').value); $('material-issue-quantity').max = b.available_to_order; $('material-issue-quantity').step = $('material-issue-quantity').min = b.unit === 'pcs' ? '1' : '0.001'; };
    $('issue-batch').onchange = updateUnit; updateUnit();
  } catch (error) { if (version === epoch && modal === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="issue-material">Coba lagi</button>`; }
}
async function materialHistoryDialog(batchId, order=null) {
  if (guardPending()) return;
  const version = epoch;
  openDialog(order ? 'Riwayat bahan order' : 'Riwayat batch bahan','<p class="state">Memuat riwayat bahan…</p>');
  const modal = dialogVersion, current = () => version === epoch && modal === dialogVersion && $('dialog').open;
  const path = order ? `/api/orders/${encodeURIComponent(order.id)}/material-movements` : `/api/material-batches/${encodeURIComponent(batchId)}/movements`;
  let rows = [], before = null;
  try {
    const batch = order ? null : await api.get('/api/material-batches/'+encodeURIComponent(batchId));
    if (!current()) return;
    $('dialog-content').innerHTML = `${batch?.qc_intake_id?`<p><button data-action="qc-intake" data-id="${e(batch.qc_intake_id)}">QC asal batch</button></p>`:''}${batch?.purchase_order_id ? `<p><button data-action="purchase-order" data-id="${e(batch.purchase_order_id)}">PO ${e(batch.purchase_order_reference)}</button></p>` : ''}<p class="form-info">${e(order ? order.reference : `${batch.reference} · ${batch.code}${batch.status==='corrected'?' · penerimaan dikoreksi':''}\n${batch.location} · saldo ${materialQty(batch.balance,batch.unit)}`)}</p>${batch?.status==='active'?`<section class="bundle-label material-batch-label" aria-label="Label batch bahan ${e(batch.reference)}"><img src="/api/material-batches/${e(encodeURIComponent(batch.id))}/label.svg" alt="Kode QR batch bahan ${e(batch.reference)}"><div><strong>${e(batch.reference)}</strong><span>${e(batch.code)} · ${e(batch.name)}</span><span class="bundle-label-qty">${e(materialQty(batch.received_quantity,batch.unit))}</span><span>${e(batch.location)} · diterima ${date(batch.received_date)}</span></div></section><div class="actions"><button id="print-material-batch" type="button">Cetak label batch</button></div>`:''}<p class="hint">Urutan terbaru · waktu Jakarta. Jumlah positif menambah stok rak; negatif menguranginya. Koreksi membalik seluruh jumlah catatan.</p><div id="material-history"></div><p id="material-history-error" class="error" role="alert" hidden></p><button id="material-history-more" type="button">Muat riwayat bahan</button>`;
    if(batch)$('material-history').insertAdjacentHTML('beforebegin',`<div class="actions"><button data-action="material-batch-traceability" data-id="${e(batch.id)}">Jejak produksi lengkap</button></div>`);
    if($('print-material-batch'))$('print-material-batch').onclick=()=>window.print();
    const load = async () => {
      const button = $('material-history-more'); button.disabled = true; message('material-history-error','');
      try {
        const page = await api.get(path+'?'+new URLSearchParams({limit:100,...(before ? {before} : {})}));
        if (!current()) return;
        rows.push(...page); before = rows.at(-1)?.sequence;
        $('material-history').innerHTML = rows.length ? rows.map(m => `<article class="material-event"><strong>${m.kind === 'receipt' ? 'Penerimaan' : m.kind === 'issue' ? 'Pengeluaran' : 'Pembalikan'} · ${e(materialQty(m.quantity,m.unit))}</strong><p>${e(m.batch_reference)} · ${e(m.code)}${m.order_reference ? ` · ${e(m.order_reference)}` : ''}</p><p class="reason">${e(m.reason)}</p><p class="hint">${e(m.actor_name)} · ${new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(m.created_at))}${m.reversed_by ? ' · Sudah dibalik' : ''}</p>${user.role === 'admin' && !m.reversal_of && !m.reversed_by && !((batch?.qc_intake_id || batch?.po_closed) && m.kind==='receipt') ? `<button type="button" data-material-reverse="${e(m.id)}">Koreksi catatan bahan</button>` : ''}</article>`).join('') : '<p class="state">Belum ada pengeluaran bahan untuk order ini.</p>';
        button.hidden = page.length < 100; button.textContent = 'Muat catatan bahan sebelumnya';
      } catch (error) { if (current()) message('material-history-error',error.message,true); }
      finally { if (current()) button.disabled = false; }
    };
    $('material-history-more').onclick = load;
    $('material-history').onclick = event => {
      const button = event.target.closest('[data-material-reverse]'); if (!button || guardPending()) return;
      const item = rows.find(m => m.id === button.dataset.materialReverse);
      formDialog('Koreksi catatan bahan',materialReason,form => Object.fromEntries(new FormData(form)),`/api/material-movements/${encodeURIComponent(item.id)}/reverse`,
        `${item.batch_reference} · ${materialQty(item.quantity,item.unit)}\nPembalikan mengembalikan seluruh jumlah catatan. Pastikan posisi bahan fisik sesuai. Penerimaan tidak dapat dibalik jika bahan masih dikeluarkan atau direservasi. Pembalikan pengeluaran mengembalikan stok bebas, tanpa mengembalikan reservasi otomatis. Pemakaian/waste yang masih tercatat harus dikoreksi terlebih dahulu.`);
    };
    await load();
  } catch (error) { if (current()) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="${order ? 'order-materials' : 'material-batch'}" data-id="${e(batchId || '')}">Coba lagi</button>`; }
}

const materialTraceLabels={
  material_receipt:'Penerimaan batch',material_issue:'Pengeluaran bahan',material_movement:'Stok bahan',
  material_reservation:'Reservasi bahan',material_reservation_release:'Pelepasan reservasi',
  material_reservation_consumption:'Pemakaian reservasi',material_consumption:'Pemakaian dan waste',
  cutting_run:'Hasil cutting',bundle:'Bundle',bundle_handoff:'Serah terima bundle',
  bundle_handoff_acceptance:'Penerimaan bundle',bundle_handoff_cancellation:'Pembatalan handoff',
  sewing_job:'Job sewing',sewing_result:'Hasil sewing',finishing:'Finishing',final_qc:'Final QC',
  final_qc_reinspection:'Inspeksi ulang final QC',rework_completion:'Selesai rework',
  finished_goods_receipt:'Penerimaan barang jadi'
};
const materialTraceStatuses={active:'Aktif',corrected:'Sudah dikoreksi',correction:'Koreksi',released:'Dilepaskan',
  consumed:'Terpakai',pending:'Menunggu penerima',received:'Sudah diterima',cancelled:'Dibatalkan',
  open:'Terbuka',completed:'Selesai'};

async function materialBatchTraceabilityDialog(batchId) {
  if(guardPending())return;
  const version=epoch;openDialog('Jejak produksi batch bahan','<p class="state">Memuat jejak produksi...</p>');const modal=dialogVersion;
  const current=()=>version===epoch&&modal===dialogVersion&&$('dialog').open;
  const endpoint='/api/material-batches/'+encodeURIComponent(batchId)+'/traceability';
  try{
    const report=await api.get(endpoint+'?limit=50');if(!current())return;
    const batch=report.batch;
    $('dialog-content').innerHTML=`<p class="form-info">${e(batch.reference)} · ${e(batch.code)} · ${e(batch.name)}</p>
      <h3>${e(materialQty(batch.received_quantity,batch.unit))} diterima · ${n(report.total)} catatan terlacak</h3>
      <article class="material-event"><h3>Posisi bahan sekarang</h3><p>Saldo ${e(materialQty(batch.balance,batch.unit))}</p><p>Available ${e(materialQty(batch.available,batch.unit))} · reserved ${e(materialQty(batch.reserved,batch.unit))}</p><p>${e(batch.location)} · ${e(batch.supplier)}</p></article>
      <div class="actions">${batch.qc_intake_id?`<button data-action="qc-intake" data-id="${e(batch.qc_intake_id)}">QC penerimaan</button>`:''}${batch.purchase_order_id?`<button data-action="purchase-order" data-id="${e(batch.purchase_order_id)}">PO ${e(batch.purchase_order_reference)}</button>`:''}</div>
      <h3>Jejak bahan sampai barang jadi</h3><p class="hint">Terbaru menurut waktu pencatatan. Nilai bahan dan pcs memakai satuan berbeda dan tidak dijumlahkan antarcatatan.</p>
      <div id="material-trace-events"></div><p id="material-trace-error" class="error" role="alert" hidden></p>
      <button id="material-trace-more" type="button">Muat catatan sebelumnya</button>
      <div class="actions"><button data-action="material-batch" data-id="${e(batch.id)}">Riwayat stok bahan</button><button data-action="material-batch-traceability" data-id="${e(batch.id)}">Muat ulang jejak</button></div>`;
    let cursor=report.next_before;
    const append=rows=>{
      appendRows('material-trace-events',rows.map(row=>{
        const corrected=row.event_type.endsWith('_correction');
        const base=row.event_type.replace(/_correction$/,'');
        const label=(corrected?'Koreksi · ':'')+(materialTraceLabels[base]||materialTraceLabels[row.event_type]);
        return `<article class="material-event" data-material-trace-event="${e(row.event_type)}"><h3>${e(label)} · ${e(row.reference)}</h3>
          <p>${e(materialQty(row.quantity,row.unit))} · ${e(materialTraceStatuses[row.status]||row.status)}</p><p>${e(row.description)}</p>
          ${row.business_date?`<p>Tanggal transaksi ${date(row.business_date)}</p>`:''}<p class="reason">${e(row.reason)}</p>
          <p class="hint">${e(row.actor_name)} · dicatat ${purchaseStamp(row.created_at)}</p>
          ${row.detail_action?`<button data-action="${e(row.detail_action)}" data-id="${e(row.detail_id)}" aria-label="Rincian ${e(label)} ${e(row.reference)}">Buka rincian</button>`:''}</article>`;
      }).join(''));
      $('material-trace-more').hidden=!cursor;
    };
    $('material-trace-more').onclick=async()=>{
      const button=$('material-trace-more');button.disabled=true;message('material-trace-error','');
      try{const page=await api.get(endpoint+'?'+new URLSearchParams({limit:50,...cursor}));if(!current())return;cursor=page.next_before;append(page.events);}
      catch(error){if(current())message('material-trace-error',error.message,true);}
      finally{if(current())button.disabled=false;}
    };
    append(report.events);
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="material-batch-traceability" data-id="${e(batchId)}">Coba lagi</button>`;}
}

$('backup').onclick = () => {
  if (guardPending()) return;
  const version = epoch;
  openDialog('Cadangan data', `<p>Unduh salinan lengkap database Beeloft: order, posisi barang, riwayat, kendala, perubahan jadwal, dan akun.</p>
    <p class="form-info">File ini memuat seluruh data produksi dan hash kunci akses akun. Simpan di folder pribadi atau drive cadangan yang hanya bisa diakses orang yang berwenang.</p>
    <p class="hint">Kunci akses asli tidak disertakan. Simpan kunci yang sudah lu miliki untuk masuk setelah pemulihan. Salinan diambil saat unduhan diminta; perubahan setelahnya masuk cadangan berikutnya.</p>
    <p class="hint">Setelah unduhan selesai, pastikan file .sqlite3 ada di lokasi pilihan lu. Untuk memeriksa cadangan, ikuti langkah pemulihan di README proyek.</p>
    <p id="backup-message" role="status" hidden></p><button id="download-backup" type="button" class="primary">Unduh cadangan database</button>`);
  const modalVersion = dialogVersion;
  const current = () => version === epoch && modalVersion === dialogVersion && $('dialog').open;
  $('download-backup').onclick = async () => {
    const button = $('download-backup'); if (button.disabled) return;
    button.disabled = true; button.textContent = 'Menyiapkan cadangan…'; message('backup-message','');
    try {
      const blob = await api.download('/api/backup');
      if (!current()) return;
      saveDownload(blob,`beeloft-backup-${new Date().toISOString().replace(/[:.]/g,'-')}.sqlite3`);
      message('backup-message','Unduhan dimulai. Periksa daftar unduhan browser untuk memastikan file sudah tersimpan.');
    } catch (error) { if (current()) fail(error,'backup-message'); }
    finally { if (current()) { button.disabled = false; button.textContent = 'Unduh cadangan database'; } }
  };
};
