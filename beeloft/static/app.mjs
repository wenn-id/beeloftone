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
    <div class="actions order-settings">${user.role === 'admin' ? '<button data-action="edit-order">Ubah tenggat / PIC</button>' : ''}<button class="quiet" data-action="order-changes">Riwayat tenggat / PIC</button><button data-action="requirements">Kebutuhan bahan</button><button data-action="reservations">Reservasi bahan</button><button data-action="consumption">Pemakaian &amp; waste</button><button data-action="cutting-runs">Hasil cutting</button><button data-action="bundles">Bundle</button><button data-action="sewing-jobs">Sewing / makloon</button><button data-action="finishing-records">Finishing</button><button data-action="final-qc-records">Final QC</button><button data-action="finished-goods">Barang jadi</button><button data-action="warehouse">Gudang</button><button data-action="marketplace-reservations">Reservasi jual</button><button data-action="marketplace-picks">Picking</button><button data-action="marketplace-packs">Packing</button>${user.role !== 'viewer' ? '<button data-action="issue-material">Keluarkan bahan ke order</button>' : ''}<button class="quiet" data-action="order-materials">Riwayat bahan order</button></div>
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
    const canReverse = user.role === 'admin' && !item.reversal_of && !reversed.has(item.id) && !item.cutting_run_id && !item.sewing_job_id && !item.finishing_record_id && !item.final_qc_record_id;
    const timestamp = new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'}).format(new Date(item.created_at));
    return `<article class="history-item"><time datetime="${e(item.created_at)}">${timestamp}</time><div><strong>${n(item.quantity)} pcs · ${labels[item.from_stage]} → ${labels[item.to_stage]}</strong><p class="hint">${e(item.sku)} · dicatat ${e(item.actor_name)}${item.reversal_of ? ' · Catatan pembalik' : reversed.has(item.id) ? ' · Sudah dibalik' : ''}</p>${item.reason ? `<p class="reason">${e(item.reason)}</p>` : ''}</div>${item.cutting_run_id ? `<button data-action="cutting-run" data-id="${e(item.cutting_run_id)}">Hasil cutting</button>` : ''}${item.sewing_job_id ? `<button data-action="sewing-job" data-id="${e(item.sewing_job_id)}">Job sewing</button>` : ''}${item.finishing_record_id ? `<button data-action="finishing-record" data-id="${e(item.finishing_record_id)}">Finishing</button>` : ''}${item.final_qc_record_id ? `<button data-action="final-qc-record" data-id="${e(item.final_qc_record_id)}">Final QC</button>` : ''}${canReverse ? `<button class="quiet history-action" data-action="reverse" data-id="${e(item.id)}">Koreksi</button>` : ''}</article>`;
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
      else if (path.endsWith('/packs') || path.startsWith('/api/marketplace-packs/')) marketplacePackDialog(result.id);
      else if (path.endsWith('/picks') || path.startsWith('/api/marketplace-picks/')) marketplacePickDialog(result.id);
      else if (path.endsWith('/marketplace-reservations') || path.startsWith('/api/marketplace-reservations/')) marketplaceReservationDialog(result.id);
      else if (path.endsWith('/warehouse-movements') || path.startsWith('/api/warehouse-movements/')) warehouseMovementDialog(result.id);
      else if (path.endsWith('/finished-goods-receipts') || path.startsWith('/api/finished-goods-receipts/')) finishedGoodsReceiptDialog(result.id);
      else if (path.endsWith('/qc-records') || path.startsWith('/api/final-qc-records/')) finalQcRecordDialog(result.id);
      else if (path.endsWith('/finishing-records') || path.startsWith('/api/finishing-records/')) finishingRecordDialog(result.id);
      else if (path.endsWith('/sewing-jobs') || path.startsWith('/api/sewing-jobs/')) sewingJobDialog(result.id);
      else if (path.endsWith('/bundles') || path.startsWith('/api/bundles/')) bundleDialog(result.id);
      else if (path.endsWith('/cutting-runs') || path.startsWith('/api/cutting-runs/')) {
        await openDetail(result.order_id);
        if(version===epoch)cuttingRunDialog(result.id);
      }
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
  const id = button.dataset.id, output = button.dataset.output, kind = button.dataset.kind;
  const actions = {detail:() => openDetail(id),move:() => moveForm(id),reverse:() => reverseForm(id),
    'new-issue':() => issueForm(id),'resolve-issue':() => resolveIssueForm(id),'more-issues':() => moreIssues(button),
    'edit-order':editOrderForm,'order-changes':orderChangesDialog,
    'purchase-requests':()=>purchaseRequestsDialog(),'order-purchases':()=>purchaseRequestsDialog(selected.id),
    'purchase-request':()=>purchaseRequestDialog(id),'new-purchase-request':()=>purchaseRequestForm(id || null),
    suppliers:suppliersDialog,'new-supplier':supplierForm,'purchase-orders':purchaseOrdersDialog,
    'new-purchase-order':()=>purchaseOrderForm(id),'purchase-order':()=>purchaseOrderDialog(id),
    'receive-po':()=>purchaseReceiptForm(id),'qc-intake-form':()=>purchaseReceiptForm(id,true),
    'qc-intake':()=>qualityIntakeDialog(id),
    'new-material':materialForm,'material-master':materialMasterDialog,'receive-material':receiptForm,
    bom:() => bomDialog(id),'edit-bom':() => bomForm(id),'bom-history':() => bomHistoryDialog(id),requirements:requirementsDialog,
    'cutting-runs':()=>cuttingRunsDialog(id || selected?.id),'new-cutting':()=>cuttingForm(id),'cutting-run':()=>cuttingRunDialog(id),
    bundles:()=>bundlesDialog(id || selected?.id),'new-bundle':()=>bundleForm(id,output),bundle:()=>bundleDialog(id),
    'sewing-jobs':()=>sewingJobsDialog(id || selected?.id),'new-sewing-job':()=>sewingJobForm(id),'sewing-job':()=>sewingJobDialog(id),
    'finishing-records':()=>finishingRecordsDialog(id || selected?.id),'new-finishing-record':()=>finishingForm(id),'finishing-record':()=>finishingRecordDialog(id),
    'final-qc-records':()=>finalQcRecordsDialog(id || selected?.id),'new-final-qc-record':()=>finalQcForm(id),'final-qc-record':()=>finalQcRecordDialog(id),
    'finished-goods':()=>finishedGoodsDialog(id || selected?.id),'new-finished-goods':()=>finishedGoodsForm(id),'finished-goods-receipt':()=>finishedGoodsReceiptDialog(id),
    warehouse:()=>warehouseDialog(id || selected?.id),'new-warehouse-movement':()=>warehouseMovementForm(id,kind),'warehouse-movement':()=>warehouseMovementDialog(id),
    'marketplace-reservations':()=>marketplaceReservationsDialog(id || selected?.id),'new-marketplace-reservation':()=>marketplaceReservationForm(id),'marketplace-reservation':()=>marketplaceReservationDialog(id),
    'marketplace-picks':()=>marketplacePicksDialog(id || selected?.id),'new-marketplace-pick':()=>marketplacePickForm(id),'marketplace-pick':()=>marketplacePickDialog(id),
    'marketplace-packs':()=>marketplacePacksDialog(id || selected?.id),'new-marketplace-pack':()=>marketplacePackForm(id),'marketplace-pack':()=>marketplacePackDialog(id),
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
        $('cutting-list').insertAdjacentHTML('beforeend',rows.map(r=>`<article class="material-event"><h3>${e(r.reference)} · ${n(r.total_output)} pcs</h3>
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
      $('bundle-list').insertAdjacentHTML('beforeend',rows.map(b=>`<article class="material-event"><h3>${e(b.reference)} · ${n(b.quantity)} pcs</h3><p>${e(b.sku)} · ${e(b.size)} · ${b.status==='active'?'Aktif':'Sudah dikoreksi'}</p><p>${e(b.cutting_reference)} · ${e(b.batch_reference)}</p><p class="hint">${e(b.actor_name)} · ${purchaseStamp(b.created_at)}</p><button data-action="bundle" data-id="${e(b.id)}" aria-label="Rincian ${e(b.reference)}">Rincian bundle</button></article>`).join(''));
      if(!before && !rows.length)$('bundle-list').innerHTML='<p class="state">Belum ada bundle untuk order ini. Buka hasil cutting untuk membuat bundle pertama.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;
    }catch(error){if(current()){message('bundle-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
    finally{if(current())button.disabled=false;}
  };
  $('bundle-more').onclick=load;await load();
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
    $('dialog-content').innerHTML=`<p class="form-info">${e(bundle.reference)} · ${bundle.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${n(bundle.quantity)} pcs · ${e(bundle.sku)} · ${e(bundle.size)}</h3><p>${e(bundle.product_name)} · ${e(bundle.color)}</p><p>Dialokasikan ke sewing ${n(bundle.sewing_allocated_quantity)} pcs · belum dialokasikan ${n(bundle.sewing_unassigned_quantity)} pcs</p><p>Hasil cutting ${e(bundle.cutting_reference)} · batch ${e(bundle.batch_reference)} · ${e(bundle.material_code)}</p><p class="reason">${e(bundle.reason)}</p><p class="hint">${e(bundle.actor_name)} · ${purchaseStamp(bundle.created_at)}</p>${bundle.reversal?`<article class="material-event"><h3>Sudah dikoreksi</h3><p class="reason">${e(bundle.reversal.reason)}</p><p class="hint">${e(bundle.reversal.actor_name)} · ${purchaseStamp(bundle.reversal.created_at)}</p></article>`:''}<div class="actions"><button id="bundle-order">Buka order produksi</button><button data-action="cutting-run" data-id="${e(bundle.cutting_run_id)}">Hasil cutting asal</button><button data-action="material-batch" data-id="${e(bundle.batch_id)}">Batch bahan asal</button><button data-action="bundles" data-id="${e(bundle.order_id)}">Semua bundle</button><button data-action="sewing-jobs" data-id="${e(bundle.order_id)}">Sewing / makloon order</button>${user.role!=='viewer' && bundle.status==='active' && bundle.sewing_unassigned_quantity>0?`<button data-action="new-sewing-job" data-id="${e(bundle.id)}">Kirim ke sewing</button>`:''}${user.role==='admin' && bundle.status==='active'?'<button id="reverse-bundle">Koreksi bundle</button>':''}</div>`;
    $('bundle-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(bundle.order_id);};
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
      $('sewing-list').insertAdjacentHTML('beforeend',rows.map(job=>`<article class="material-event"><h3>${e(job.reference)} · ${n(job.quantity_out)} pcs</h3><p>${e(job.bundle_reference)} · ${e(job.sku)} · ${e(job.size)}</p><p>${job.assignment_type==='makloon'?'Makloon':'Internal'} · ${e(job.assignee)} · ${rupiah(job.cost)}</p><p>${status[job.status]} · dikirim ${date(job.sent_date)}</p><button data-action="sewing-job" data-id="${e(job.id)}" aria-label="Rincian ${e(job.reference)}">Rincian job</button></article>`).join(''));
      if(!before && !rows.length)$('sewing-list').innerHTML='<p class="state">Belum ada job sewing untuk order ini. Buka bundle untuk mengirim pekerjaan pertama.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat job sebelumnya';
    }catch(error){if(current()){message('sewing-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
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
      $('finishing-list').insertAdjacentHTML('beforeend',rows.map(record=>`<article class="material-event"><h3>${e(record.reference)} · ${n(record.quantity)} pcs</h3><p>${e(record.sewing_reference)} · ${e(record.bundle_reference)} · ${e(record.sku)} · ${e(record.size)}</p><p>${record.status==='completed'?'Selesai':'Sudah dikoreksi'} · ${date(record.completed_date)}</p><button data-action="finishing-record" data-id="${e(record.id)}" aria-label="Rincian ${e(record.reference)}">Rincian finishing</button></article>`).join(''));
      if(!before && !rows.length)$('finishing-list').innerHTML='<p class="state">Belum ada catatan finishing untuk order ini. Buka job sewing yang sudah selesai untuk mencatat finishing.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat catatan sebelumnya';
    }catch(error){if(current()){message('finishing-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
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
    $('dialog-content').innerHTML=`<p class="form-info">${e(record.reference)} · ${record.status==='completed'?'Selesai':'Sudah dikoreksi'}</p><h3>${n(record.quantity)} pcs · ${e(record.sku)} · ${e(record.size)}</h3><p>Job sewing ${e(record.sewing_reference)} · bundle ${e(record.bundle_reference)}</p><p>${record.assignment_type==='makloon'?'Makloon':'Internal'} · ${e(record.assignee)}</p><article class="material-event"><h3>Checklist finishing lengkap</h3>${checks.map(([label,done])=>`<p>${done?'✓':'—'} ${e(label)}</p>`).join('')}<p>Selesai ${date(record.completed_date)}</p><p>Final QC tercatat ${n(record.qc_inspected_quantity)} pcs · belum diperiksa ${n(record.qc_remaining_quantity)} pcs</p></article><p class="reason">${e(record.reason)}</p><p class="hint">${e(record.actor_name)} · ${purchaseStamp(record.created_at)}</p>${record.reversal?`<article class="material-event"><h3>Finishing dikoreksi</h3><p class="reason">${e(record.reversal.reason)}</p><p class="hint">${e(record.reversal.actor_name)} · ${purchaseStamp(record.reversal.created_at)}</p></article>`:''}<div class="actions"><button id="finishing-order">Buka order produksi</button><button data-action="sewing-job" data-id="${e(record.job_id)}">Job sewing asal</button><button data-action="bundle" data-id="${e(record.bundle_id)}">Bundle asal</button><button data-action="cutting-run" data-id="${e(record.cutting_run_id)}">Hasil cutting asal</button><button data-action="material-batch" data-id="${e(record.batch_id)}">Batch bahan asal</button><button data-action="finishing-records" data-id="${e(record.order_id)}">Semua finishing</button><button data-action="final-qc-records" data-id="${e(record.order_id)}">Final QC order</button>${user.role!=='viewer' && record.status==='completed' && record.qc_remaining_quantity>0?`<button data-action="new-final-qc-record" data-id="${e(record.id)}">Catat final QC</button>`:''}${user.role==='admin' && record.status==='completed'?'<button id="reverse-finishing">Koreksi finishing</button>':''}</div>`;
    $('finishing-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(record.order_id);};
    if($('reverse-finishing'))$('reverse-finishing').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi finishing',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/finishing-records/'+encodeURIComponent(record.id)+'/reverse',
        `${record.reference} · ${n(record.quantity)} pcs\nKoreksi mengembalikan jumlah dari QC ke finishing. Checklist dan riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finishing-record" data-id="${e(recordId)}">Coba lagi</button>`;}
}

async function finalQcRecordsDialog(orderId) {
  if(guardPending())return;
  const version=epoch;openDialog('Final QC order','<p class="state">Memuat catatan final QC...</p>');const modal=dialogVersion;
  const current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  $('dialog-content').innerHTML='<p class="hint">Inspeksi terbaru ditampilkan lebih dahulu. Setiap jumlah dibagi menjadi diterima gudang, rework, dan reject.</p><div id="final-qc-list"><p class="state">Memuat catatan final QC...</p></div><p id="final-qc-error" class="error" role="alert" hidden></p><button id="final-qc-more" type="button">Muat inspeksi sebelumnya</button>';
  let before=null;
  const load=async()=>{
    const button=$('final-qc-more');button.disabled=true;message('final-qc-error','');
    try{
      const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/final-qc-records?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
      if(!current())return;
      if(!before)$('final-qc-list').replaceChildren();
      $('final-qc-list').insertAdjacentHTML('beforeend',rows.map(record=>`<article class="material-event"><h3>${e(record.reference)} · ${n(record.inspected_quantity)} pcs</h3><p>${e(record.finishing_reference)} · ${e(record.sku)} · ${e(record.size)}</p><p>Diterima ${n(record.accepted_quantity)} · rework ${n(record.rework_quantity)} · reject ${n(record.reject_quantity)}</p><p>${record.status==='completed'?'Selesai':'Sudah dikoreksi'} · ${date(record.inspection_date)}</p><button data-action="final-qc-record" data-id="${e(record.id)}" aria-label="Rincian ${e(record.reference)}">Rincian final QC</button></article>`).join(''));
      if(!before && !rows.length)$('final-qc-list').innerHTML='<p class="state">Belum ada catatan final QC untuk order ini. Buka finishing yang selesai untuk mencatat inspeksi.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat inspeksi sebelumnya';
    }catch(error){if(current()){message('final-qc-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
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
    $('dialog-content').innerHTML=`<p class="form-info">${e(record.reference)} · ${record.status==='completed'?'Selesai':'Sudah dikoreksi'}</p><h3>${n(record.inspected_quantity)} pcs diperiksa · ${e(record.sku)} · ${e(record.size)}</h3><p>Finishing ${e(record.finishing_reference)} · sewing ${e(record.sewing_reference)} · bundle ${e(record.bundle_reference)}</p><article class="material-event"><h3>Hasil final QC</h3><p>Diterima gudang ${n(record.accepted_quantity)} pcs</p><p>Rework ${n(record.rework_quantity)} pcs · reject ${n(record.reject_quantity)} pcs</p><p>Diterima barang jadi ${n(record.warehouse_received_quantity)} pcs · belum diterima ${n(record.warehouse_remaining_quantity)} pcs</p><p>Inspeksi ${date(record.inspection_date)}</p></article><h3>Pengukuran</h3><p class="reason">${e(record.measurement_notes)}</p><h3>Pemeriksaan visual</h3><p class="reason">${e(record.visual_notes)}</p><h3>Defect dan disposition</h3><p>${e(record.defect_type)} · sumber ${e(record.responsible_source)}</p><p class="reason">${e(record.disposition)}</p><p class="reason">${e(record.reason)}</p><p class="hint">${e(record.actor_name)} · ${purchaseStamp(record.created_at)}</p>${record.reversal?`<article class="material-event"><h3>Final QC dikoreksi</h3><p class="reason">${e(record.reversal.reason)}</p><p class="hint">${e(record.reversal.actor_name)} · ${purchaseStamp(record.reversal.created_at)}</p></article>`:''}<div class="actions"><button id="final-qc-order">Buka order produksi</button><button data-action="finishing-record" data-id="${e(record.finishing_record_id)}">Finishing asal</button><button data-action="sewing-job" data-id="${e(record.job_id)}">Job sewing asal</button><button data-action="bundle" data-id="${e(record.bundle_id)}">Bundle asal</button><button data-action="material-batch" data-id="${e(record.batch_id)}">Batch bahan asal</button><button data-action="final-qc-records" data-id="${e(record.order_id)}">Semua final QC</button><button data-action="finished-goods" data-id="${e(record.order_id)}">Barang jadi order</button>${user.role!=='viewer' && record.status==='completed' && record.warehouse_remaining_quantity>0?`<button data-action="new-finished-goods" data-id="${e(record.id)}">Terima barang jadi</button>`:''}${user.role==='admin' && record.status==='completed'?'<button id="reverse-final-qc">Koreksi final QC</button>':''}</div>`;
    $('final-qc-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(record.order_id);};
    if($('reverse-final-qc'))$('reverse-final-qc').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi final QC',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/final-qc-records/'+encodeURIComponent(record.id)+'/reverse',
        `${record.reference} · ${n(record.inspected_quantity)} pcs\nKoreksi mengembalikan seluruh hasil diterima, rework, dan reject ke QC. Catatan inspeksi asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="final-qc-record" data-id="${e(recordId)}">Coba lagi</button>`;}
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
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><h3>Inventori barang jadi</h3>${relevant.map(row=>`<article class="material-event"><strong>${e(row.sku)} · ${e(row.size)}</strong><p>Available ${n(row.available_quantity)} pcs · reserved ${n(row.reserved_quantity)} pcs · picked ${n(row.picked_quantity)} pcs · packed ${n(row.packed_quantity)} pcs</p><p>Sellable fisik ${n(row.sellable_quantity)} · hold ${n(row.hold_quantity)} · damaged ${n(row.damaged_quantity)} · total ${n(row.total_quantity)} pcs</p></article>`).join('')}<p class="hint">Angka ini adalah ledger internal Beeloft dan belum menyinkronkan stok Jubelio/WMS.</p><button data-action="warehouse" data-id="${e(orderId)}">Inventori per lokasi &amp; pergerakan</button><button data-action="marketplace-reservations" data-id="${e(orderId)}">Reservasi marketplace</button><button data-action="marketplace-picks" data-id="${e(orderId)}">Riwayat picking</button><button data-action="marketplace-packs" data-id="${e(orderId)}">Riwayat packing</button><h3>Riwayat penerimaan</h3><div id="finished-goods-list"><p class="state">Memuat penerimaan...</p></div><p id="finished-goods-error" class="error" role="alert" hidden></p><button id="finished-goods-more" type="button">Muat penerimaan sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('finished-goods-more');button.disabled=true;message('finished-goods-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/finished-goods-receipts?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('finished-goods-list').replaceChildren();
        $('finished-goods-list').insertAdjacentHTML('beforeend',rows.map(receipt=>`<article class="material-event"><h3>${e(receipt.reference)} · ${n(receipt.received_quantity)} pcs</h3><p>${e(receipt.sku)} · ${e(receipt.size)} · ${e(receipt.location)}</p><p>Sellable ${n(receipt.sellable_quantity)} · hold ${n(receipt.hold_quantity)} · ${receipt.status==='active'?'Aktif':'Sudah dikoreksi'}</p><p>${date(receipt.received_date)}</p><button data-action="finished-goods-receipt" data-id="${e(receipt.id)}" aria-label="Rincian ${e(receipt.reference)}">Rincian penerimaan</button></article>`).join(''));
        if(!before && !rows.length)$('finished-goods-list').innerHTML='<p class="state">Belum ada penerimaan barang jadi untuk order ini. Buka final QC dengan hasil diterima untuk mencatat penerimaan.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat penerimaan sebelumnya';
      }catch(error){if(current()){message('finished-goods-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
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
    $('dialog-content').innerHTML=`<p class="form-info">${e(receipt.reference)} · ${receipt.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${n(receipt.received_quantity)} pcs · ${e(receipt.sku)} · ${e(receipt.size)}</h3><article class="material-event"><h3>Inventori sekarang</h3>${receipt.inventory.map(row=>`<p>${e(row.location)} · ${e(row.stock_status)} ${n(row.quantity)} pcs${row.stock_status==='sellable'?` · available ${n(row.available_quantity)} · reserved ${n(row.reserved_quantity)}`:''}</p>`).join('') || '<p>Stok penerimaan ini sudah dilepaskan.</p>'}<p>Diterima awal di ${e(receipt.location)} · ${date(receipt.received_date)}</p><p>SKU dipindai: ${e(receipt.scanned_sku)}</p></article><p>Final QC ${e(receipt.final_qc_reference)} · finishing ${e(receipt.finishing_reference)} · sewing ${e(receipt.sewing_reference)} · bundle ${e(receipt.bundle_reference)}</p><p class="reason">${e(receipt.reason)}</p><p class="hint">${e(receipt.actor_name)} · ${purchaseStamp(receipt.created_at)}</p>${receipt.active_movement_count?`<p class="hint">${n(receipt.active_movement_count)} pergerakan gudang aktif. Koreksi pergerakan tersebut sebelum mengoreksi penerimaan.</p>`:''}${receipt.active_reservation_count?`<p class="hint">${n(receipt.active_reservation_count)} reservasi marketplace aktif. Lepaskan reservasi tersebut sebelum mengoreksi penerimaan.</p>`:''}${receipt.reversal?`<article class="material-event"><h3>Penerimaan barang jadi dikoreksi</h3><p class="reason">${e(receipt.reversal.reason)}</p><p class="hint">${e(receipt.reversal.actor_name)} · ${purchaseStamp(receipt.reversal.created_at)}</p></article>`:''}<div class="actions"><button id="finished-goods-order">Buka order produksi</button><button data-action="final-qc-record" data-id="${e(receipt.final_qc_record_id)}">Final QC asal</button><button data-action="finishing-record" data-id="${e(receipt.finishing_record_id)}">Finishing asal</button><button data-action="sewing-job" data-id="${e(receipt.job_id)}">Job sewing asal</button><button data-action="bundle" data-id="${e(receipt.bundle_id)}">Bundle asal</button><button data-action="finished-goods" data-id="${e(receipt.order_id)}">Semua barang jadi</button><button data-action="warehouse" data-id="${e(receipt.order_id)}">Gudang order</button><button data-action="marketplace-reservations" data-id="${e(receipt.order_id)}">Reservasi order</button>${user.role!=='viewer'&&receipt.status==='active'&&reservable?`<button data-action="new-marketplace-reservation" data-id="${e(receipt.id)}">Reservasi marketplace</button>`:''}${user.role!=='viewer' && receipt.status==='active' && (sellable||hold||damaged)?`<button data-action="new-warehouse-movement" data-kind="transfer" data-id="${e(receipt.id)}">Transfer lokasi</button>`:''}${user.role!=='viewer' && receipt.status==='active' && hold?`<button data-action="new-warehouse-movement" data-kind="hold_release" data-id="${e(receipt.id)}">Lepaskan hold</button><button data-action="new-warehouse-movement" data-kind="hold_damage" data-id="${e(receipt.id)}">Tandai damaged</button>`:''}${user.role==='admin' && receipt.status==='active' && !receipt.active_movement_count && !receipt.active_reservation_count?'<button id="reverse-finished-goods">Koreksi penerimaan</button>':''}</div>`;
    $('finished-goods-order').onclick=()=>{if(guardPending())return;$('dialog').close();openDetail(receipt.order_id);};
    if($('reverse-finished-goods'))$('reverse-finished-goods').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi penerimaan barang jadi',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/finished-goods-receipts/'+encodeURIComponent(receipt.id)+'/reverse',
        `${receipt.reference} · ${n(receipt.received_quantity)} pcs\nKoreksi melepaskan klasifikasi sellable/hold tanpa mengubah saldo WIP warehouse. Riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="finished-goods-receipt" data-id="${e(receiptId)}">Coba lagi</button>`;}
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
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><h3>Inventori per lokasi</h3>${relevant.map(row=>`<article class="material-event"><strong>${e(row.sku)} · ${e(row.location)}</strong><p>${e(warehouseStatus[row.stock_status])} ${n(row.quantity)} pcs${row.stock_status==='sellable'?` · available ${n(row.available_quantity)} · reserved ${n(row.reserved_quantity)}`:''}</p></article>`).join('') || '<p class="state">Belum ada inventori barang jadi untuk order ini.</p>'}<p class="hint">Sellable dibagi menjadi available dan reserved. Picked menunggu packing di staging; packed menunggu pengiriman. Hold dan damaged tetap terpisah dari stok jual.</p><button data-action="finished-goods" data-id="${e(orderId)}">Penerimaan barang jadi</button><button data-action="marketplace-reservations" data-id="${e(orderId)}">Reservasi marketplace</button><button data-action="marketplace-picks" data-id="${e(orderId)}">Riwayat picking</button><button data-action="marketplace-packs" data-id="${e(orderId)}">Riwayat packing</button><h3>Riwayat pergerakan</h3><div id="warehouse-list"><p class="state">Memuat pergerakan...</p></div><p id="warehouse-error" class="error" role="alert" hidden></p><button id="warehouse-more" type="button">Muat pergerakan sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('warehouse-more');button.disabled=true;message('warehouse-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/warehouse-movements?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('warehouse-list').replaceChildren();
        $('warehouse-list').insertAdjacentHTML('beforeend',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(warehouseKind[row.kind])} · ${e(row.sku)}</p><p>${e(row.from_location)} (${e(warehouseStatus[row.from_status])}) → ${e(row.to_location)} (${e(warehouseStatus[row.to_status])})</p><p>${row.status==='active'?'Aktif':'Sudah dikoreksi'} · ${date(row.moved_date)}</p><button data-action="warehouse-movement" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian pergerakan</button></article>`).join(''));
        if(!before && !rows.length)$('warehouse-list').innerHTML='<p class="state">Belum ada pergerakan gudang untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pergerakan sebelumnya';
      }catch(error){if(current()){message('warehouse-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
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
    formDialog(title,field('reference','Referensi pergerakan','text','required maxlength="160"')+source+
      field('to_location','Lokasi tujuan','text','required maxlength="160"')+
      field('quantity','Jumlah','number','required min="1" step="1"')+
      field('moved_date','Tanggal pergerakan','date',`required min="${e(receipt.received_date)}"`)+materialReason,
      form=>{const data=new FormData(form),bucket=buckets[Number(data.get('source'))],payload={reference:data.get('reference'),kind,from_location:bucket.location,to_location:data.get('to_location'),quantity:Number(data.get('quantity')),moved_date:data.get('moved_date'),reason:data.get('reason')};if(kind==='transfer')payload.stock_status=bucket.stock_status;if(payload.quantity>bucket.movable_quantity)throw new Error('Jumlah melebihi stok yang dapat dipindahkan pada lokasi dan status asal.');if(kind==='transfer'&&payload.from_location.trim().toLocaleLowerCase()===payload.to_location.trim().toLocaleLowerCase())throw new Error('Lokasi tujuan transfer harus berbeda dari lokasi asal.');return payload;},
      '/api/finished-goods-receipts/'+encodeURIComponent(receiptId)+'/warehouse-movements',
      `${receipt.reference} · ${receipt.sku}\n${kind==='transfer'?'Status stok tetap sama selama transfer.':'Keputusan hanya mengambil stok hold dari lokasi yang dipilih.'}`);
    const updateMax=()=>{const bucket=buckets[Number($('warehouse-source').value)];$('action-form').elements.quantity.max=bucket.movable_quantity;};
    $('warehouse-source').onchange=updateMax;updateMax();
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-warehouse-movement" data-kind="${e(kind)}" data-id="${e(receiptId)}">Coba lagi</button>`;}
}

async function warehouseMovementDialog(movementId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian pergerakan gudang','<p class="state">Memuat pergerakan gudang...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/warehouse-movements/'+encodeURIComponent(movementId));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Aktif':'Sudah dikoreksi'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(warehouseKind[row.kind])}</h3><p>${e(row.from_location)} · ${e(warehouseStatus[row.from_status])}</p><p>→ ${e(row.to_location)} · ${e(warehouseStatus[row.to_status])}</p><p>${date(row.moved_date)}</p></article><p>Penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.reversal?`<article class="material-event"><h3>Pergerakan gudang dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}<div class="actions"><button data-action="finished-goods-receipt" data-id="${e(row.receipt_id)}">Penerimaan asal</button><button data-action="warehouse" data-id="${e(row.order_id)}">Gudang order</button>${user.role==='admin'&&row.status==='active'?'<button id="reverse-warehouse">Koreksi pergerakan</button>':''}</div>`;
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
        $('marketplace-list').insertAdjacentHTML('beforeend',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(row.marketplace)} · ${e(row.external_order_reference)}</p><p>${e(row.sku)} · ${e(row.location)} · ${row.status==='active'?'Reserved':'Dilepaskan'}</p><p>Sudah dipick ${n(row.picked_quantity)} · sisa ${n(row.remaining_quantity)} pcs · ${date(row.reserved_date)}</p><button data-action="marketplace-reservation" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian reservasi</button></article>`).join(''));
        if(!before&&!rows.length)$('marketplace-list').innerHTML='<p class="state">Belum ada reservasi marketplace untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat reservasi sebelumnya';
      }catch(error){if(current()){message('marketplace-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
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
        $('marketplace-pick-list').insertAdjacentHTML('beforeend',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(row.marketplace)} · ${e(row.external_order_reference)}</p><p>${e(row.location)} → ${e(row.staging_location)} · ${row.status==='active'?'Di staging':'Sudah dikoreksi'}</p><p>Packed ${n(row.packed_quantity)} · sisa ${n(row.remaining_quantity)} pcs · ${date(row.picked_date)}</p><button data-action="marketplace-pick" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian pick</button></article>`).join(''));
        if(!before&&!rows.length)$('marketplace-pick-list').innerHTML='<p class="state">Belum ada pick marketplace untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pick sebelumnya';
      }catch(error){if(current()){message('marketplace-pick-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
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
      field('quantity','Jumlah pick','number',`required min="1" max="${row.remaining_quantity}" step="1"`)+
      field('staging_location','Lokasi staging','text','required maxlength="160"')+
      field('picked_date','Tanggal pick','date',`required min="${e(row.reserved_date)}"`)+materialReason,
      form=>{const data=new FormData(form),payload={reference:data.get('reference'),quantity:Number(data.get('quantity')),staging_location:data.get('staging_location'),picked_date:data.get('picked_date'),reason:data.get('reason')};if(payload.quantity>row.remaining_quantity)throw new Error('Jumlah pick melebihi sisa reservasi.');return payload;},
      '/api/marketplace-reservations/'+encodeURIComponent(row.id)+'/picks',
      `${row.reference} · ${row.marketplace} · ${row.external_order_reference}\nSisa reservasi ${n(row.remaining_quantity)} dari ${n(row.quantity)} pcs di ${row.location}.`);
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="new-marketplace-pick" data-id="${e(reservationId)}">Coba lagi</button>`;}
}

async function marketplacePickDialog(pickId) {
  if(guardPending())return;
  const version=epoch;openDialog('Rincian pick','<p class="state">Memuat catatan pick...</p>');const modal=dialogVersion;
  try{
    const row=await api.get('/api/marketplace-picks/'+encodeURIComponent(pickId));
    if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Di staging':'Sudah dikoreksi'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(row.marketplace)} · ${e(row.external_order_reference)}</h3><p>${e(row.location)} → ${e(row.staging_location)}</p><p>Dipick ${date(row.picked_date)} · packed ${n(row.packed_quantity)} pcs · sisa ${n(row.remaining_quantity)} pcs</p></article><p>Reservasi ${e(row.reservation_reference)} · penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.reversal?`<article class="material-event"><h3>Pick dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}${row.packed_quantity?'<p class="hint">Koreksi semua pack aktif sebelum mengoreksi pick.</p>':''}<div class="actions"><button data-action="marketplace-reservation" data-id="${e(row.reservation_id)}">Reservasi asal</button><button data-action="marketplace-picks" data-id="${e(row.order_id)}">Semua pick</button><button data-action="marketplace-packs" data-id="${e(row.order_id)}">Riwayat packing</button><button data-action="warehouse" data-id="${e(row.order_id)}">Inventori gudang</button>${user.role!=='viewer'&&row.status==='active'&&row.remaining_quantity>0?`<button data-action="new-marketplace-pack" data-id="${e(row.id)}">Catat pack</button>`:''}${user.role==='admin'&&row.status==='active'&&!row.packed_quantity?'<button id="reverse-marketplace-pick">Koreksi pick</button>':''}</div>`;
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
    $('dialog-content').innerHTML=`<p class="form-info">${e(order.reference)}</p><p class="hint">Pack memindahkan barang dari picked ke packed pada lokasi staging yang sama. Stok packed menunggu proses pengiriman.</p><button data-action="marketplace-picks" data-id="${e(orderId)}">Riwayat picking</button><button data-action="warehouse" data-id="${e(orderId)}">Inventori gudang</button><h3>Riwayat pack</h3><div id="marketplace-pack-list"><p class="state">Memuat pack...</p></div><p id="marketplace-pack-error" class="error" role="alert" hidden></p><button id="marketplace-pack-more" type="button">Muat pack sebelumnya</button>`;
    let before=null;
    const load=async()=>{
      const button=$('marketplace-pack-more');button.disabled=true;message('marketplace-pack-error','');
      try{
        const rows=await api.get('/api/orders/'+encodeURIComponent(orderId)+'/marketplace-packs?'+new URLSearchParams({limit:25,...(before?{before}:{})}));
        if(!current())return;
        if(!before)$('marketplace-pack-list').replaceChildren();
        $('marketplace-pack-list').insertAdjacentHTML('beforeend',rows.map(row=>`<article class="material-event"><h3>${e(row.reference)} · ${n(row.quantity)} pcs</h3><p>${e(row.marketplace)} · ${e(row.external_order_reference)}</p><p>${e(row.sku)} · ${e(row.staging_location)} · ${row.status==='active'?'Packed':'Sudah dikoreksi'}</p><p>Sumber ${e(row.pick_reference)} · ${date(row.packed_date)}</p><button data-action="marketplace-pack" data-id="${e(row.id)}" aria-label="Rincian ${e(row.reference)}">Rincian pack</button></article>`).join(''));
        if(!before&&!rows.length)$('marketplace-pack-list').innerHTML='<p class="state">Belum ada pack marketplace untuk order ini.</p>';
        before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pack sebelumnya';
      }catch(error){if(current()){message('marketplace-pack-error',error.message,true);button.hidden=false;button.textContent='Coba lagi';}}
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
    $('dialog-content').innerHTML=`<p class="form-info">${e(row.reference)} · ${row.status==='active'?'Packed':'Sudah dikoreksi'}</p><h3>${n(row.quantity)} pcs · ${e(row.sku)} · ${e(row.size)}</h3><article class="material-event"><h3>${e(row.marketplace)} · ${e(row.external_order_reference)}</h3><p>${e(row.staging_location)} · dipack ${date(row.packed_date)}</p><p>Sumber pick ${e(row.pick_reference)} · ${date(row.picked_date)}</p></article><p>Reservasi ${e(row.reservation_reference)} · penerimaan ${e(row.receipt_reference)} · Final QC ${e(row.final_qc_reference)} · batch ${e(row.batch_reference)}</p><p class="reason">${e(row.reason)}</p><p class="hint">${e(row.actor_name)} · ${purchaseStamp(row.created_at)}</p>${row.reversal?`<article class="material-event"><h3>Pack dikoreksi</h3><p class="reason">${e(row.reversal.reason)}</p><p class="hint">${e(row.reversal.actor_name)} · ${purchaseStamp(row.reversal.created_at)}</p></article>`:''}<div class="actions"><button data-action="marketplace-pick" data-id="${e(row.pick_id)}">Pick asal</button><button data-action="marketplace-packs" data-id="${e(row.order_id)}">Semua pack</button><button data-action="warehouse" data-id="${e(row.order_id)}">Inventori gudang</button>${user.role==='admin'&&row.status==='active'?'<button id="reverse-marketplace-pack">Koreksi pack</button>':''}</div>`;
    if($('reverse-marketplace-pack'))$('reverse-marketplace-pack').onclick=()=>{
      if(guardPending())return;
      formDialog('Koreksi pack',materialReason,form=>Object.fromEntries(new FormData(form)),
        '/api/marketplace-packs/'+encodeURIComponent(row.id)+'/reverse',
        `${row.reference} · ${n(row.quantity)} pcs\nKoreksi mengembalikan barang dari packed ke picked di ${row.staging_location}. Riwayat asli tetap tersimpan.`);
    };
  }catch(error){if(version===epoch&&modal===dialogVersion&&$('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="marketplace-pack" data-id="${e(packId)}">Coba lagi</button>`;}
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
        $('consumption-history').insertAdjacentHTML('beforeend',rows.map(r=>`<article class="material-event"><strong>${r.reversal_of?'Pembalikan pemakaian':'Pemakaian dicatat'}</strong><p>${e(r.batch_reference)} · ${e(r.code)}</p><p>Terpakai ${e(materialQty(r.used,r.unit))} · waste ${e(materialQty(r.waste,r.unit))}</p><p class="reason">${e(r.reason)}</p><p class="hint">${e(r.actor_name)} · ${stamp(r.created_at)}${r.reversed_by?' · Sudah dibalik':''}</p><p class="hint">Pengeluaran ${e(r.issue_id)}</p>${r.cutting_run_id?`<button data-action="cutting-run" data-id="${e(r.cutting_run_id)}">Hasil cutting</button>`:''}${user.role==='admin' && !r.reversal_of && !r.reversed_by && !r.cutting_run_id?`<button data-consumption-reverse="${e(r.id)}">Koreksi pemakaian</button>`:''}</article>`).join(''));
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
    `<p class="hint">Pengajuan bahan untuk ditinjau. PR yang disetujui belum menjadi pesanan ke pemasok.</p><div class="actions">${user.role!=='viewer' ? `<button data-action="new-purchase-request" data-id="${e(orderId || '')}">Buat PR</button>` : ''}<button data-action="suppliers">Master pemasok</button><button data-action="purchase-orders">Daftar PO</button><button id="pr-refresh">Muat ulang PR</button></div><label for="pr-status">Status PR</label><select id="pr-status"><option value="all">Semua status</option>${Object.entries(purchaseStatus).map(([value,label])=>option(value,label)).join('')}</select><div id="pr-list"></div><p id="pr-error" role="alert" class="error" hidden></p><button id="pr-more">Muat PR berikutnya</button>`);
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
    if((user.role==='admin' && ['submitted','approved'].includes(p.status) && !p.purchase_orders.some(po=>po.status!=='cancelled')) ||
       (user.role==='operator' && p.actor_id===user.id && p.status==='submitted'))decisions.push(['cancelled','Batalkan PR']);
    $('dialog-content').innerHTML=`<p class="form-info">${e(p.reference)} · ${purchaseStatus[p.status]}</p><p>${e(p.order_reference || 'Permintaan umum')} · dibutuhkan ${date(p.required_date)}</p><p>Estimasi total ${e(rupiah(p.estimated_value))}</p><p class="reason">${e(p.reason)}</p><div>${p.lines.map(l=>`<article class="material-event"><strong>${e(l.code)} · ${e(l.name)}</strong><p>${e(materialQty(l.quantity,l.unit))}</p></article>`).join('')}</div><p class="hint">Persetujuan dicatat oleh admin, termasuk pengajuan sendiri. Belum ada aturan batas nilai. Lihat PO terkait di bawah; PR dengan PO ditutup sudah final; PO aktif harus dibatalkan sebelum PR.</p><div class="actions">${decisions.map(([status,label])=>`<button data-pr-decision="${status}">${label}</button>`).join('')}<button data-action="purchase-request" data-id="${e(id)}">Muat ulang rincian PR</button><button data-action="purchase-requests">Semua PR</button></div><h3>Riwayat keputusan</h3>${p.history.map(event=>`<article class="material-event"><strong>${purchaseStatus[event.status]}</strong><p class="reason">${e(event.reason)}</p><p class="hint">${e(event.actor_name)} · ${purchaseStamp(event.created_at)}</p></article>`).join('')}`;
    $('dialog-content').querySelector('.actions').insertAdjacentHTML('beforeend',
      `${user.role==='admin' && p.status==='approved' && !p.purchase_orders.some(po=>po.status!=='cancelled') ? `<button data-action="new-purchase-order" data-id="${e(id)}">Buat PO dari PR</button>` : ''}${p.purchase_orders.map(po=>`<button data-action="purchase-order" data-id="${e(po.id)}">PO ${e(po.reference)} · ${poStatus[po.status]}</button>`).join('')}`);
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
  openDialog('Daftar PO','<p class="hint">PO tercatat internal. Buka rincian untuk mencatat penerimaan bahan dan melihat sisa pesanan.</p><label for="po-status">Status PO</label><select id="po-status"><option value="all">Semua status</option><option value="issued">Aktif</option><option value="closed">Ditutup</option><option value="cancelled">Dibatalkan</option></select><button id="po-refresh">Muat ulang PO</button><div id="po-list"></div><p id="po-error" class="error" role="alert" hidden></p><button id="po-more">Muat PO berikutnya</button>');
  const modal=dialogVersion,current=()=>version===epoch && modal===dialogVersion && $('dialog').open;
  let before=null,generation=0;
  async function load(reset=false){
    if(reset){generation++;before=null;$('po-list').replaceChildren();}
    const gen=generation,button=$('po-more');button.disabled=true;message('po-error','');
    try{
      const rows=await api.get('/api/purchase-orders?'+new URLSearchParams({limit:25,status:$('po-status').value,...(before?{before}:{})}));
      if(!current() || gen!==generation)return;
      $('po-list').insertAdjacentHTML('beforeend',rows.map(p=>`<article class="material-event"><h3>${e(p.reference)}</h3><p>${e(p.supplier.name)} · ${poStatus[p.status]}</p><p>${e(rupiah(p.total))} · perkiraan datang ${date(p.expected_date)}</p><p>${fulfillmentLabel[p.fulfillment]}${p.lines.some(l=>l.held!=='0.000')?' · Menunggu QC':''}</p><button data-action="purchase-order" data-id="${e(p.id)}" aria-label="Rincian PO ${e(p.reference)}">Rincian PO</button></article>`).join(''));
      if(!before && !rows.length)$('po-list').innerHTML='<p class="state">Belum ada PO yang sesuai filter.</p>';
      before=rows.at(-1)?.sequence;button.hidden=rows.length<25;
    }catch(error){if(current() && gen===generation){message('po-error',error.message,true);button.hidden=false;}}
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
    if(pr.status!=='approved' || pr.purchase_orders.some(po=>po.status!=='cancelled')){$('dialog-content').innerHTML='<p>PR belum disetujui atau sudah memiliki PO aktif/ditutup. Buka ulang rincian PR.</p>';return;}
    if(!suppliers.length){$('dialog-content').innerHTML='<p>Tambahkan pemasok sebelum membuat PO.</p><button data-action="new-supplier">Tambah pemasok</button>';return;}
    formDialog('Buat PO dari PR',field('reference','Referensi PO','text','required maxlength="160"')+
      `<label>Pemasok PO<select name="supplier_id" required>${suppliers.map(s=>option(s.id,s.code+' · '+s.name)).join('')}</select></label>`+
      field('expected_date','Perkiraan tanggal datang','date','required')+
      '<label class="full">Syarat pembelian<textarea name="terms" required maxlength="1000"></textarea></label>'+
      `<div class="full" id="po-prices">${pr.lines.map(l=>`<article class="material-event"><h3>${e(l.code)} · ${e(materialQty(l.quantity,l.unit))}</h3><label>Harga satuan ${e(l.code)} (Rp/${e(l.unit)})<input data-price-material="${e(l.material_id)}" type="number" required min="0.01" max="1000000000" step="0.01"></label></article>`).join('')}<p id="po-total" role="status">Isi harga semua bahan untuk melihat total.</p></div>`+materialReason,
      form=>({...Object.fromEntries(new FormData(form)),request_id:pr.id,expected_revision:pr.revision,
        prices:[...form.querySelectorAll('[data-price-material]')].map(input=>({material_id:input.dataset.priceMaterial,unit_price:input.value}))}),
      '/api/purchase-orders',`${pr.reference} · batas nilai ${rupiah(pr.estimated_value)}\nSeluruh jumlah PR dibeli dari satu pemasok. Harga, jumlah dan syarat akan terkunci saat disimpan. PO tercatat internal; belum dikirim ke pemasok dan belum menambah stok.`);
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

const poStatus={issued:'Aktif',cancelled:'Dibatalkan',closed:'Ditutup'};
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
    const p=await api.get('/api/purchase-orders/'+encodeURIComponent(id));
    if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;
    $('dialog-content').innerHTML=`<p class="form-info">${e(p.reference)} · ${poStatus[p.status]}</p><h3>${e(p.supplier.code)} · ${e(p.supplier.name)}</h3><p>${e(p.supplier.contact)} · ${e(p.supplier.address)}</p><p>Perkiraan datang ${date(p.expected_date)}</p><p class="reason">Syarat: ${e(p.terms)}</p>${p.lines.map(l=>`<article class="material-event"><strong>${e(l.code)} · ${e(l.name)}</strong><p>${e(materialQty(l.quantity,l.unit))} × ${e(rupiah(l.unit_price))}/${e(l.unit)}</p><p>Nilai baris ${e(rupiah(l.line_total))}</p><p>Diterima ${e(materialQty(l.received,l.unit))} · sisa layak pakai ${e(materialQty(l.remaining,l.unit))}</p><p>Hold ${e(materialQty(l.held,l.unit))} · reject ${e(materialQty(l.rejected,l.unit))} · bisa datang ${e(materialQty(l.receivable,l.unit))}</p><p>Diretur ${e(materialQty(l.returned,l.unit))} · belum diretur ${e(materialQty(l.return_pending,l.unit))}</p></article>`).join('')}<p><strong>Total PO ${e(rupiah(p.total))}</strong></p><p class="reason">${e(p.reason)}</p><p class="hint">Dicatat ${e(p.actor_name)} · ${purchaseStamp(p.created_at)}.</p><p>${fulfillmentLabel[p.fulfillment]}</p>${p.cancellation?`<article class="material-event"><h3>Pembatalan PO</h3><p class="reason">${e(p.cancellation.reason)}</p><p>${e(p.cancellation.actor_name)} · ${purchaseStamp(p.cancellation.created_at)}</p></article>`:''}<div class="actions"><button data-action="purchase-request" data-id="${e(p.request_id)}">PR ${e(p.request_reference)}</button><button data-action="purchase-orders">Daftar PO</button>${user.role==='admin' && p.status==='issued' && p.fulfillment==='pending' && p.lines.every(l=>l.held==='0.000' && l.return_pending==='0.000')?'<button id="po-cancel">Batalkan PO</button>':''}</div>`;
    renderPOClosure(p);
    $('dialog-content').insertAdjacentHTML('beforeend', qualityIntakesHTML(p)+purchaseReceiptsHTML(p));
    if($('po-cancel'))$('po-cancel').onclick=()=>{if(guardPending())return;formDialog('Batalkan PO',materialReason,form=>Object.fromEntries(new FormData(form)),
      '/api/purchase-orders/'+encodeURIComponent(id)+'/cancel',`${p.reference} · ${rupiah(p.total)}\nPembatalan seluruh PO disimpan permanen. Pastikan pembelian memang dibatalkan; aplikasi tidak mengirim pemberitahuan ke pemasok.`);};
  }catch(error){if(version===epoch && modal===dialogVersion && $('dialog').open)$('dialog-content').innerHTML=`<p class="error">${e(error.message)}</p><button data-action="purchase-order" data-id="${e(id)}">Coba lagi</button>`;}
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
    $('dialog-content').innerHTML = `${batch?.qc_intake_id?`<p><button data-action="qc-intake" data-id="${e(batch.qc_intake_id)}">QC asal batch</button></p>`:''}${batch?.purchase_order_id ? `<p><button data-action="purchase-order" data-id="${e(batch.purchase_order_id)}">PO ${e(batch.purchase_order_reference)}</button></p>` : ''}<p class="form-info">${e(order ? order.reference : `${batch.reference} · ${batch.code}\n${batch.location} · saldo ${materialQty(batch.balance,batch.unit)}`)}</p><p class="hint">Urutan terbaru · waktu Jakarta. Jumlah positif menambah stok rak; negatif menguranginya. Koreksi membalik seluruh jumlah catatan.</p><div id="material-history"></div><p id="material-history-error" class="error" role="alert" hidden></p><button id="material-history-more" type="button">Muat riwayat bahan</button>`;
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
