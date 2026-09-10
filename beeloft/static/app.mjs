import {Api, escapeHTML as e, displayDate as date} from './client.mjs';

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
let noticeTimer;

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
  activityRequest++; activityRows = []; activityCursor = null; activityQuery = null;
  $('activity-list').replaceChildren(); $('activity-summary').replaceChildren(); $('activity-day').value = ''; $('activity-kind').value = 'all';
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
    $('new-order').hidden = me.role !== 'admin'; offset = 0; showBoard();
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
  activityRequest++; $('activity-view').hidden = true;
  view = 'board'; detailRequest++; selected = null;
  $('board-view').hidden = false; $('detail-view').hidden = true; loadBoard();
}
$('brand').onclick = event => { event.preventDefault(); if (user) showBoard(); };
$('back').onclick = () => { showBoard(); $('search').focus(); };
$('refresh').onclick = () => loadBoard();
$('issues-summary').onclick = () => { $('status').value = 'blocked'; $('search').value = ''; offset = 0; loadBoard(); };
$('search-form').onsubmit = event => { event.preventDefault(); offset = 0; loadBoard(); };
$('status').onchange = () => { offset = 0; loadBoard(); };
$('previous').onclick = () => { offset = Math.max(0, offset - 25); loadBoard(); };
$('next').onclick = () => { offset += 25; loadBoard(); };

async function loadBoard() {
  const version = epoch, request = ++boardRequest;
  message('board-message', 'Memuat posisi produksi…');
  $('order-list').hidden = true; $('previous').disabled = true; $('next').disabled = true;
  $('summary').setAttribute('aria-busy', 'true');
  try {
    const query = new URLSearchParams({q:$('search').value.trim(), status:$('status').value, limit:25, offset});
    const result = await api.get('/api/production-board?' + query);
    if (version !== epoch || request !== boardRequest || view !== 'board') return;
    boardData = result;
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
    <div class="actions order-settings">${user.role === 'admin' ? '<button data-action="edit-order">Ubah tenggat / PIC</button>' : ''}<button class="quiet" data-action="order-changes">Riwayat tenggat / PIC</button></div>
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
async function allRows(path) {
  let rows = [], page;
  do { page = await api.get(`${path}?limit=500&offset=${rows.length}`); rows.push(...page); } while (page.length === 500);
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
    $('dialog-content').innerHTML = `<div class="product-list">${products.length ? products.map(p => `<div class="product-item"><div><strong>${e(p.sku)}</strong><span class="hint">${e(p.name)} · ${e([p.color,p.size].filter(Boolean).join(' / '))}</span></div></div>`).join('') : '<p>Belum ada SKU. Tambahkan produk untuk membuat order pertama.</p>'}</div>${user.role === 'admin' ? '<button class="primary" data-action="new-product">Tambah SKU</button>' : ''}`;
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
  view = 'activity'; boardRequest++; detailRequest++; selected = null;
  $('board-view').hidden = true; $('detail-view').hidden = true; $('activity-view').hidden = false;
  loadActivity();
};
$('activity-back').onclick = showBoard;
$('activity-form').onsubmit = event => { event.preventDefault(); loadActivity(); };
$('activity-day').onchange = $('activity-kind').onchange = () => { if ($('activity-form').reportValidity()) loadActivity(); };
$('activity-more').onclick = () => loadActivity(true);
async function loadActivity(more = false) {
  if (more && !activityCursor) return;
  const version = epoch, request = ++activityRequest;
  const query = more ? {...activityQuery,...activityCursor} : {kind:$('activity-kind').value,limit:50};
  if (!more && $('activity-day').value) query.day = $('activity-day').value;
  if (!more) {
    activityRows = []; activityCursor = null; activityQuery = null;
    $('activity-list').replaceChildren(); $('activity-summary').replaceChildren(); $('activity-count').textContent = '';
    $('activity-more').hidden = true;
  }
  $('activity-more').disabled = true; message('activity-message','Memuat aktivitas…');
  try {
    const result = await api.get('/api/activity?' + new URLSearchParams(query));
    if (version !== epoch || request !== activityRequest || view !== 'activity') return;
    if (!more) { activityQuery = {day:result.day,kind:query.kind,limit:50}; $('activity-day').value = result.day; }
    activityRows.push(...result.items); activityCursor = result.next_before;
    const s = result.summary;
    $('activity-summary').innerHTML = [['Aktivitas tercatat',s.events,'catatan'],['Gudang bersih',s.warehouse_net,'pcs'],['Kendala dicatat',s.issues_opened,'catatan'],['Kendala selesai',s.issues_resolved,'catatan']]
      .map(([label,value,unit]) => `<div><dt>${label}</dt><dd>${n(value)} <small>${unit}</small></dd></div>`).join('');
    message('activity-message',activityRows.length ? '' : 'Tidak ada aktivitas yang cocok pada tanggal ini.');
    $('activity-list').innerHTML = activityRows.map(item => {
      const stamp = new Intl.DateTimeFormat('id-ID',{hour:'2-digit',minute:'2-digit',second:'2-digit',timeZone:'Asia/Jakarta'}).format(new Date(item.created_at));
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
  } finally { if (version === epoch && request === activityRequest) $('activity-more').disabled = false; }
}
