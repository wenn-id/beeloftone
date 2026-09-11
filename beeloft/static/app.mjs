import {Api, escapeHTML as e, displayDate as date, formatMaterialQuantity as materialQty} from './client.mjs';

const $ = id => document.getElementById(id);
const api = new Api();
const nf = new Intl.NumberFormat('id-ID');
const n = value => nf.format(value);
const labels = {planned:'Belum cutting', cutting:'Cutting', sewing:'Sewing', finishing:'Finishing', qc:'QC', warehouse:'Gudang', rework:'Rework', reject:'Reject'};
const stages = ['planned','cutting','sewing','finishing','qc','warehouse'];
let user = null, transitions = [], boardData = null, selected = null, history = [], historyOffset = 0;
let offset = 0, epoch = 0, boardRequest = 0, detailRequest = 0, view = 'board', modalBusy = false, unresolved = false;
let dialogVersion = 0;
let issues = [], issuesMore = false;
let activityRequest = 0, activityCursor = null, activityRows = [], activityQuery = null;
let exportBusy = false;
let noticeTimer;
let materialsRequest = 0, materialsOffset = 0;

function theme(value) {
  document.documentElement.dataset.theme = value;
  $('theme').textContent = value === 'dark' ? 'Mode terang' : 'Mode gelap';
  try { localStorage.setItem('beeloft.theme', value); } catch {}
}
try { theme(localStorage.getItem('beeloft.theme') || 'light'); } catch { theme('light'); }
$('theme').onclick = () => theme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

function notify(message) {
  $('notice').textContent = message; $('notice').hidden = false;
  clearTimeout(noticeTimer); noticeTimer = setTimeout(() => $('notice').hidden = true, 6000);
}
function message(id, text, error = false) {
  $(id).hidden = !text; $(id).textContent = text;
  $(id).classList.toggle('error', error);
}
function logout() {
  materialsRequest++; materialsOffset = 0; $('batch-list').replaceChildren(); $('material-filter').innerHTML = '<option value="">Semua bahan</option>';
  $('backup').hidden = true;
  $('board-owner').innerHTML = '<option value="">Semua PIC</option>'; $('board-stage').value = 'all';
  activityRequest++; activityRows = []; activityCursor = null; activityQuery = null;
  $('activity-list').replaceChildren(); $('activity-summary').replaceChildren(); $('activity-day').value = ''; $('activity-end').value = ''; $('activity-export').disabled = true; $('activity-kind').value = 'all';
  epoch++; boardRequest++; detailRequest++; api.key = ''; user = null; selected = null; boardData = null;
  dialogVersion++; modalBusy = false; unresolved = false; $('dialog').close();
  $('workspace').hidden = true; $('login-view').hidden = false; $('logout').hidden = true;
  $('account-name').textContent = ''; $('access-key').value = ''; $('order-list').replaceChildren();
  $('summary').replaceChildren(); $('detail-content').replaceChildren(); $('dialog-content').replaceChildren();
  $('notice').hidden = true; $('access-key').focus();
}
$('logout').onclick = logout;
function fail(error, target) {
  if (error.status === 401) { logout(); message('login-error', 'Akses berakhir. Masukkan kembali kunci akses yang aktif.', true); }
  else message(target, error.message, true);
}
$('login-form').onsubmit = async event => {
  event.preventDefault(); const button = event.currentTarget.querySelector('button');
  button.disabled = true; button.textContent = 'Memeriksa akses…'; message('login-error', '');
  api.key = $('access-key').value.trim(); const version = ++epoch;
  try {
    const [me, workflow] = await Promise.all([api.get('/api/me'), api.get('/api/stages')]);
    if (version !== epoch) return;
    user = me; transitions = workflow.transitions; $('access-key').value = '';
    $('account-name').textContent = `${me.name} · ${me.role}`;
    $('login-view').hidden = true; $('workspace').hidden = false; $('logout').hidden = false;
    $('new-order').hidden = me.role !== 'admin'; $('backup').hidden = me.role !== 'admin'; offset = 0; showBoard();
    const pending = readPending();
    if (pending) recover(pending);
  } catch (error) { if (version === epoch) { api.key = ''; message('login-error', error.message, true); } }
  finally { button.disabled = false; button.textContent = 'Buka ruang produksi'; }
};

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
  materialsRequest++; $('materials-view').hidden = true;
  activityRequest++; $('activity-view').hidden = true;
  view = 'board'; detailRequest++; selected = null;
  $('board-view').hidden = false; $('detail-view').hidden = true; loadBoard();
}
$('brand').onclick = event => { event.preventDefault(); if (user) showBoard(); };
$('back').onclick = () => { showBoard(); $('search').focus(); };
$('refresh').onclick = () => loadBoard();
$('issues-summary').onclick = () => { resetBoardFilters(); $('status').value = 'blocked'; loadBoard(); };
$('search-form').onsubmit = event => { event.preventDefault(); offset = 0; loadBoard(); };
$('status').onchange = $('board-owner').onchange = $('board-stage').onchange = () => { offset = 0; loadBoard(); };
function resetBoardFilters() { $('search').value = ''; $('status').value = 'all'; $('board-owner').value = ''; $('board-stage').value = 'all'; offset = 0; }
$('reset-board').onclick = () => { resetBoardFilters(); loadBoard(); };
$('previous').onclick = () => { offset = Math.max(0, offset - 25); loadBoard(); };
$('next').onclick = () => { offset += 25; loadBoard(); };

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
    $('issues-summary').textContent = `${n(result.open_issues)} kendala terbuka · lihat order terkait`;
    $('issues-summary').hidden = false;
    const s = result.summary;
    $('summary').innerHTML = [['Order aktif',s.active,'order'],['Lewat target',s.overdue,'order'],['Dalam proses',s.in_progress,'pcs'],['Perlu rework',s.rework,'pcs']]
      .map(([label,value,unit]) => `<div><dt>${label}</dt><dd>${n(value)} <small>${unit}</small></dd></div>`).join('');
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
  materialsRequest++; $('materials-view').hidden = true;
  activityRequest++; $('activity-view').hidden = true;
  view = 'detail'; boardRequest++; $('board-view').hidden = true; $('detail-view').hidden = false;
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
    <div class="actions order-settings">${user.role === 'admin' ? '<button data-action="edit-order">Ubah tenggat / PIC</button>' : ''}<button class="quiet" data-action="order-changes">Riwayat tenggat / PIC</button><button data-action="requirements">Kebutuhan bahan</button><button data-action="reservations">Reservasi bahan</button><button data-action="consumption">Pemakaian &amp; waste</button>${user.role !== 'viewer' ? '<button data-action="issue-material">Keluarkan bahan ke order</button>' : ''}<button class="quiet" data-action="order-materials">Riwayat bahan order</button></div>
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
    const canReverse = user.role === 'admin' && !item.reversal_of && !reversed.has(item.id);
    const timestamp = new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(item.created_at));
    return `<article class="history-item"><time datetime="${e(item.created_at)}">${timestamp}</time><div><strong>${n(item.quantity)} pcs · ${labels[item.from_stage]} → ${labels[item.to_stage]}</strong><p class="hint">${e(item.sku)} · dicatat ${e(item.actor_name)}${item.reversal_of ? ' · Catatan pembalik' : reversed.has(item.id) ? ' · Sudah dibalik' : ''}</p>${item.reason ? `<p class="reason">${e(item.reason)}</p>` : ''}</div>${canReverse ? `<button class="quiet history-action" data-action="reverse" data-id="${e(item.id)}">Koreksi</button>` : ''}</article>`;
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

const option = (value,label) => `<option value="${e(value)}">${e(label)}</option>`;
const field = (name,label,type='text',attrs='') => `<label>${label}<input name="${name}" type="${type}" ${attrs}></label>`;
function openDialog(title, content) {
  dialogVersion++;
  $('dialog-title').textContent = title; $('dialog-content').innerHTML = content;
  modalBusy = false; unresolved = false; if (!$('dialog').open) $('dialog').showModal();
}
function closeDialog() {
  if (modalBusy || unresolved) { notify('Konfirmasi penyimpanan lewat tombol coba ulang sebelum menutup.'); return; }
  dialogVersion++; $('dialog').close();
}
$('close-dialog').onclick = closeDialog;
$('dialog').addEventListener('cancel', event => { if (modalBusy || unresolved) { event.preventDefault(); notify('Penyimpanan belum terkonfirmasi. Gunakan coba ulang.'); } else dialogVersion++; });
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
function formDialog(title, fields, collect, path, info = '', initial = null) {
  openDialog(title, `<form id="action-form">${info ? `<p class="form-info">${e(info)}</p>` : ''}<fieldset id="form-fields"><div class="form-grid">${fields}</div></fieldset><p class="error" id="form-error" role="alert" hidden></p><div class="form-actions"><button type="button" data-action="cancel-form">Batal</button><button type="button" id="reauth" hidden>Masuk ulang</button><button class="primary" id="save-form" type="submit">Simpan pencatatan</button></div></form>`);
  let transaction = initial;
  const modalVersion = dialogVersion;
  $('reauth').onclick = logout;
  if (initial) { unresolved = true; $('form-fields').disabled = true; $('save-form').textContent = 'Coba ulang penyimpanan'; }
  $('action-form').onsubmit = async event => {
    event.preventDefault(); if (modalBusy) return;
    const version = epoch, actorId = user.id, storageKey = pendingKey();
    const button = $('save-form'); message('form-error', '');
    try {
      if (!transaction) transaction = api.transaction(path, collect(event.currentTarget));
      sessionStorage.setItem(storageKey, JSON.stringify({transaction, title, info}));
      modalBusy = true; $('form-fields').disabled = true; button.disabled = true; $('reauth').disabled = true; button.textContent = 'Menyimpan…';
      const result = await api.save(transaction);
      clearPending(storageKey, transaction);
      if (version !== epoch || user?.id !== actorId || modalVersion !== dialogVersion) return;
      modalBusy = false; unresolved = false; $('dialog').close();
      notify('Pencatatan tersimpan.');
      if (path === '/api/orders') openDetail(result.id);
      else if (path.startsWith('/api/purchase-requests')) purchaseRequestDialog(result.id);
      else if (/^\/api\/products\/[^/]+\/bom$/.test(path)) bomDialog(result.product_id);
      else if (view === 'materials') loadMaterials();
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
  if (!sources.length) { notify('Tidak ada saldo yang dapat dipindahkan. Koreksi transaksi melalui riwayat jika diperlukan.'); return; }
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
  do { page = await api.get(path+'?'+new URLSearchParams({...extra,limit:500,offset:rows.length})); rows.push(...page); } while (page.length === 500);
  return rows;
}
async function productsDialog() {
  if (guardPending()) return;
  const version = epoch;
  openDialog('Master SKU', '<p class="state">Memuat daftar SKU…</p>');
  const modalVersion = dialogVersion;
  try {
    const products = await allRows('/api/products');
    if (version !== epoch || modalVersion !== dialogVersion || !$('dialog').open) return;
    $('dialog-content').innerHTML = `<div class="product-list">${products.length ? products.map(p => `<div class="product-item"><div><strong>${e(p.sku)}</strong><span class="hint">${e(p.name)} · ${e([p.color,p.size].filter(Boolean).join(' / '))}</span></div><button type="button" data-action="bom" data-id="${e(p.id)}" aria-label="BOM ${e(p.sku)}">BOM</button></div>`).join('') : '<p>Belum ada SKU. Tambahkan produk untuk membuat order pertama.</p>'}</div>${user.role === 'admin' ? '<button class="primary" data-action="new-product">Tambah SKU</button>' : ''}`;
  } catch (error) { if (version === epoch && modalVersion === dialogVersion && $('dialog').open) $('dialog-content').innerHTML = `<p class="error">${e(error.message)}</p><button data-action="products">Coba lagi</button>`; }
}
function productForm() {
  if (guardPending()) return;
  formDialog('Tambah SKU', field('sku','Kode SKU','text','required maxlength="160"') + field('name','Nama produk','text','required maxlength="160"') + field('color','Warna','text','maxlength="80"') + field('size','Ukuran','text','maxlength="40"'), form => Object.fromEntries(new FormData(form)), '/api/products', 'Gunakan satu kode SKU untuk setiap kombinasi produk, warna, dan ukuran.');
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
$('products').onclick = productsDialog; $('new-order').onclick = orderForm;
document.addEventListener('click', event => {
  const button = event.target.closest('[data-action]'); if (!button || button.disabled) return;
  const id = button.dataset.id;
  const actions = {detail:() => openDetail(id),move:() => moveForm(id),reverse:() => reverseForm(id),
    'new-issue':() => issueForm(id),'resolve-issue':() => resolveIssueForm(id),'more-issues':() => moreIssues(button),
    'edit-order':editOrderForm,'order-changes':orderChangesDialog,
    'purchase-requests':()=>purchaseRequestsDialog(),'order-purchases':()=>purchaseRequestsDialog(selected.id),
    'purchase-request':()=>purchaseRequestDialog(id),'new-purchase-request':()=>purchaseRequestForm(id || null),
    'new-material':materialForm,'material-master':materialMasterDialog,'receive-material':receiptForm,
    bom:() => bomDialog(id),'edit-bom':() => bomForm(id),'bom-history':() => bomHistoryDialog(id),requirements:requirementsDialog,
    consumption:consumptionDialog,'record-consumption':()=>consumptionForm(id),reservations:reservationsDialog,'reserve-material':()=>reservationForm('reserve'),'release-material':()=>reservationForm('release'),
    'material-batch':() => materialHistoryDialog(id),'issue-material':materialIssueForm,
    'order-materials':() => materialHistoryDialog(null,selected),
    'refresh-detail':() => openDetail(selected.id),'more-history':() => moreHistory(button),
    products:productsDialog,'new-product':productForm,'new-order':orderForm,'cancel-form':closeDialog};
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
      $('order-change-list').insertAdjacentHTML('beforeend', rows.map(item => {
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

const activityLabels = {movement:'Perpindahan barang',reversal:'Koreksi perpindahan',issue_opened:'Kendala dicatat',issue_resolved:'Kendala selesai',order_created:'Order dibuat',order_changed:'Tenggat / PIC diubah'};
$('activity').onclick = () => {
  materialsRequest++; $('materials-view').hidden = true;
  view = 'activity'; boardRequest++; detailRequest++; selected = null;
  $('board-view').hidden = true; $('detail-view').hidden = true; $('activity-view').hidden = false;
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
    $('activity-summary').innerHTML = [['Aktivitas tercatat',s.events,'catatan'],['Gudang bersih',s.warehouse_net,'pcs'],['Kendala dicatat',s.issues_opened,'catatan'],['Kendala selesai',s.issues_resolved,'catatan']]
      .map(([label,value,unit]) => `<div><dt>${label}</dt><dd>${n(value)} <small>${unit}</small></dd></div>`).join('');
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
  view = 'materials'; boardRequest++; detailRequest++; activityRequest++; selected = null;
  $('board-view').hidden = true; $('detail-view').hidden = true; $('activity-view').hidden = true; $('materials-view').hidden = false;
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
      $('bom-history').insertAdjacentHTML('beforeend',rows.map(b=>`<article class="material-event"><h3>${e(b.sku)} · versi ${b.revision}</h3><p class="hint">${e(b.actor_name)} · ${date(b.created_at)}</p>${bomComponentsHTML(b.components)}<p class="reason">${e(b.reason)}</p></article>`).join(''));
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
        $('reservation-history').insertAdjacentHTML('beforeend',rows.map(r=>`<article class="material-event"><strong>${{reserve:'Reservasi ditambah',release:'Reservasi dilepas',consume:'Dipakai oleh pengeluaran'}[r.kind]} · ${e(materialQty(r.quantity,r.unit))}</strong><p>${e(r.batch_reference)} · ${e(r.code)}</p><p class="reason">${e(r.reason)}</p><p class="hint">${e(r.actor_name)} · ${new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(r.created_at))}</p></article>`).join(''));
        before=rows.at(-1)?.sequence;button.hidden=rows.length<100;button.textContent='Muat reservasi sebelumnya';
      }catch(error){if(current())message('reservation-error',error.message,true);}finally{if(current())button.disabled=false;}
    };
    $('reservation-more').onclick=load;await load();
  }catch(error){if(current())$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="reservations">Coba lagi</button>`;}
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
        $('consumption-history').insertAdjacentHTML('beforeend',rows.map(r=>`<article class="material-event"><strong>${r.reversal_of?'Pembalikan pemakaian':'Pemakaian dicatat'}</strong><p>${e(r.batch_reference)} · ${e(r.code)}</p><p>Terpakai ${e(materialQty(r.used,r.unit))} · waste ${e(materialQty(r.waste,r.unit))}</p><p class="reason">${e(r.reason)}</p><p class="hint">${e(r.actor_name)} · ${stamp(r.created_at)}${r.reversed_by?' · Sudah dibalik':''}</p><p class="hint">Pengeluaran ${e(r.issue_id)}</p>${user.role==='admin' && !r.reversal_of && !r.reversed_by?`<button data-consumption-reverse="${e(r.id)}">Koreksi pemakaian</button>`:''}</article>`).join(''));
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
$('materials').onclick = showMaterials;
$('materials-back').onclick = showBoard;
$('materials-refresh').onclick = () => loadMaterials();
$('material-filter').onchange = () => { materialsOffset = 0; loadMaterials(); };
$('materials-previous').onclick = () => { materialsOffset = Math.max(0,materialsOffset-25); loadMaterials(); };
$('materials-next').onclick = () => { materialsOffset += 25; loadMaterials(); };
$('material-master').onclick = materialMasterDialog;
$('receive-material').onclick = receiptForm;
const purchaseStatus = {submitted:'Menunggu keputusan',approved:'Disetujui',rejected:'Ditolak',cancelled:'Dibatalkan'};
const rupiah = value => 'Rp' + BigInt(value.split('.')[0]).toLocaleString('id-ID') + ',' + value.split('.')[1];
const purchaseStamp = value => new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(value));
$('purchase-requests').onclick = () => purchaseRequestsDialog();

async function purchaseRequestsDialog(orderId=null) {
  if (guardPending()) return;
  const version=epoch;
  openDialog(orderId ? 'PR untuk order ini' : 'Permintaan pembelian',
    `<p class="hint">Pengajuan bahan untuk ditinjau. PR yang disetujui belum menjadi pesanan ke pemasok.</p><div class="actions">${user.role!=='viewer' ? `<button data-action="new-purchase-request" data-id="${e(orderId || '')}">Buat PR</button>` : ''}<button id="pr-refresh">Muat ulang PR</button></div><label for="pr-status">Status PR</label><select id="pr-status"><option value="all">Semua status</option>${Object.entries(purchaseStatus).map(([value,label])=>option(value,label)).join('')}</select><div id="pr-list"></div><p id="pr-error" role="alert" class="error" hidden></p><button id="pr-more">Muat PR berikutnya</button>`);
  const modal=dialogVersion, current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  let before=null, generation=0;
  async function load(reset=false) {
    if(reset){generation++;before=null;$('pr-list').replaceChildren();}
    const gen=generation, button=$('pr-more'); button.disabled=true; message('pr-error','');
    try {
      const rows=await api.get('/api/purchase-requests?'+new URLSearchParams({limit:25,status:$('pr-status').value,...(orderId?{order_id:orderId}:{}),...(before?{before}:{})}));
      if(!current() || gen!==generation)return;
      $('pr-list').insertAdjacentHTML('beforeend', rows.map(p=>`<article class="material-event"><h3>${e(p.reference)}</h3><p>${purchaseStatus[p.status]} · dibutuhkan ${date(p.required_date)}</p><p>${e(p.order_reference || 'Permintaan umum')} · ${e(rupiah(p.estimated_value))} estimasi total</p><p class="hint">${e(p.actor_name)} · ${purchaseStamp(p.created_at)}</p><button data-action="purchase-request" data-id="${e(p.id)}" aria-label="Rincian ${e(p.reference)}">Rincian PR</button></article>`).join(''));
      if(!before && !rows.length)$('pr-list').innerHTML='<p class="state">Belum ada PR yang sesuai filter.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;
    }catch(error){if(current() && gen===generation){message('pr-error',error.message,true);button.hidden=false;button.textContent='Coba muat PR lagi';}}
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
    if((user.role==='admin' && ['submitted','approved'].includes(p.status)) ||
       (user.role==='operator' && p.actor_id===user.id && p.status==='submitted'))decisions.push(['cancelled','Batalkan PR']);
    $('dialog-content').innerHTML=`<p class="form-info">${e(p.reference)} · ${purchaseStatus[p.status]}</p><p>${e(p.order_reference || 'Permintaan umum')} · dibutuhkan ${date(p.required_date)}</p><p>Estimasi total ${e(rupiah(p.estimated_value))}</p><p class="reason">${e(p.reason)}</p><div>${p.lines.map(l=>`<article class="material-event"><strong>${e(l.code)} · ${e(l.name)}</strong><p>${e(materialQty(l.quantity,l.unit))}</p></article>`).join('')}</div><p class="hint">Persetujuan dicatat oleh admin, termasuk pengajuan sendiri. Belum ada aturan batas nilai. PR ini belum menjadi PO ke pemasok.</p><div class="actions">${decisions.map(([status,label])=>`<button data-pr-decision="${status}">${label}</button>`).join('')}<button data-action="purchase-request" data-id="${e(id)}">Muat ulang rincian PR</button><button data-action="purchase-requests">Semua PR</button></div><h3>Riwayat keputusan</h3>${p.history.map(event=>`<article class="material-event"><strong>${purchaseStatus[event.status]}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)} · ${purchaseStamp(event.created_at)}</p></article>`).join('')}`;
    $('dialog-content').querySelectorAll('[data-pr-decision]').forEach(button=>{
      button.onclick=()=>{if(guardPending())return;
        formDialog(button.textContent,materialReason,form=>({...Object.fromEntries(new FormData(form)),status:button.dataset.prDecision,expected_revision:p.revision}),
          '/api/purchase-requests/'+encodeURIComponent(id)+'/decisions',
          `${p.reference} · ${rupiah(p.estimated_value)}\n${button.textContent}. Keputusan beserta alasan akan tersimpan. Pengajuan yang ditolak atau dibatalkan tidak dapat dibuka kembali.`);
      };
    });
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="purchase-request" data-id="${e(id)}">Coba lagi</button>`;}
}

const materialReason = '<label class="full">Alasan / catatan<textarea name="reason" required maxlength="1000"></textarea></label>';

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
    $('dialog-content').innerHTML = `<p class="form-info">${e(order ? order.reference : `${batch.reference} · ${batch.code}\n${batch.location} · saldo ${materialQty(batch.balance,batch.unit)}`)}</p><p class="hint">Urutan terbaru · waktu Jakarta. Jumlah positif menambah stok rak; negatif menguranginya. Koreksi membalik seluruh jumlah catatan.</p><div id="material-history"></div><p id="material-history-error" class="error" role="alert" hidden></p><button id="material-history-more" type="button">Muat riwayat bahan</button>`;
    const load = async () => {
      const button = $('material-history-more'); button.disabled = true; message('material-history-error','');
      try {
        const page = await api.get(path+'?'+new URLSearchParams({limit:100,...(before ? {before} : {})}));
        if (!current()) return;
        rows.push(...page); before = rows.at(-1)?.sequence;
        $('material-history').innerHTML = rows.length ? rows.map(m => `<article class="material-event"><strong>${m.kind === 'receipt' ? 'Penerimaan' : m.kind === 'issue' ? 'Pengeluaran' : 'Pembalikan'} · ${e(materialQty(m.quantity,m.unit))}</strong><p>${e(m.batch_reference)} · ${e(m.code)}${m.order_reference ? ` · ${e(m.order_reference)}` : ''}</p><p class="reason">${e(m.reason)}</p><p class="hint">${e(m.actor_name)} · ${new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(m.created_at))}${m.reversed_by ? ' · Sudah dibalik' : ''}</p>${user.role === 'admin' && !m.reversal_of && !m.reversed_by ? `<button type="button" data-material-reverse="${e(m.id)}">Koreksi catatan bahan</button>` : ''}</article>`).join('') : '<p class="state">Belum ada pengeluaran bahan untuk order ini.</p>';
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
