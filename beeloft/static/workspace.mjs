export function createWorkspace({guardPending, busy, theme, showCommandCenter, syncLens}) {
  const $ = id => document.getElementById(id), root = document.documentElement;
  const shell = $('workspace-window'), launcher = $('workspace-launcher');
  let state = 'open', account = null, returnFocus = null, customURL = null, wallpaperRevision = 0;
  let fullscreenPending = false;
  const status = () => {
    $('connection-status').textContent = !navigator.onLine ? 'Offline' : account ? 'Online' : 'Belum masuk';
    $('connection-status').dataset.online = String(navigator.onLine && Boolean(account));
  };
  addEventListener('online', status);
  addEventListener('offline', status);
  function windowState(next) {
    if (next !== 'open' && (guardPending() || busy() || $('dialog').open)) return;
    if (next !== 'open') {
      returnFocus = document.activeElement;
      $('workspace-menu').open = false;
      closeSearch();
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      shell.classList.remove('is-maximized');
    }
    state = next;
    shell.dataset.state = state;
    shell.hidden = state !== 'open';
    shell.inert = state !== 'open';
    launcher.hidden = state === 'open';
    launcher.classList.toggle('is-minimized', state === 'minimized');
    $('launcher-description').textContent = state === 'minimized' ? 'Ruang kerja diminimalkan.' : 'Ruang kerja ditutup.';
    $('window-restore').textContent = state === 'minimized' ? 'Pulihkan ruang kerja' : 'Open Beeloft One';
    if (state === 'open') {
      (returnFocus?.isConnected ? returnFocus : $('workspace-home')).focus();
      syncLens();
    } else $('window-restore').focus();
    fullscreenLabel();
  }
  $('window-close').onclick = () => windowState('closed');
  $('window-minimize').onclick = () => windowState('minimized');
  $('window-restore').onclick = () => windowState('open');
  function fullscreenLabel() {
    const label = shell.classList.contains('is-maximized') ? 'Exit fullscreen' : 'Enter fullscreen';
    $('window-fullscreen').setAttribute('aria-label', label);
    $('window-fullscreen').title = label;
  }
  document.addEventListener('fullscreenchange', () => {
    if (document.fullscreenElement && state !== 'open') document.exitFullscreen().catch(() => {});
    shell.classList.toggle('is-maximized', Boolean(document.fullscreenElement) && state === 'open');
    fullscreenLabel();
    syncLens();
  });
  $('window-fullscreen').onclick = async () => {
    if (fullscreenPending) return;
    fullscreenPending = true;
    try {
      if (shell.classList.contains('is-maximized')) {
        if (document.fullscreenElement) { try { await document.exitFullscreen(); } catch {} }
        shell.classList.toggle('is-maximized', Boolean(document.fullscreenElement));
      } else {
        shell.classList.add('is-maximized');
        try { await root.requestFullscreen(); } catch { /* Internal maximize remains available. */ }
      }
    } finally { fullscreenPending = false; fullscreenLabel(); syncLens(); }
  };

  const search = $('navigation-search'), results = $('navigation-results');
  let matches = [], selected = 0;
  function closeSearch() {
    results.hidden = true;
    search.setAttribute('aria-expanded', 'false');
    search.removeAttribute('aria-activedescendant');
  }
  function selectResult(index) {
    selected = index;
    [...results.children].forEach((node, i) => node.setAttribute('aria-selected', String(i === index)));
    if (matches.length) {
      search.setAttribute('aria-activedescendant', `navigation-result-${index}`);
      results.children[index].scrollIntoView({block:'nearest'});
    } else search.removeAttribute('aria-activedescendant');
  }
  function renderSearch() {
    if (!account) return closeSearch();
    const query = search.value.trim().toLocaleLowerCase('id');
    matches = [...$('app-sidebar').querySelectorAll('button')]
      .filter(button => !button.hidden && !button.disabled && button.textContent.toLocaleLowerCase('id').includes(query));
    results.replaceChildren(...matches.map((button, index) => {
      const option = document.createElement('div');
      option.id = `navigation-result-${index}`;
      option.setAttribute('role', 'option');
      option.textContent = button.textContent.trim();
      option.onmousedown = event => event.preventDefault();
      option.onclick = () => activateResult(index);
      return option;
    }));
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.textContent = 'Halaman tidak ditemukan.';
      results.append(empty);
    }
    results.hidden = false;
    search.setAttribute('aria-expanded', 'true');
    selectResult(0);
  }
  function activateResult(index) {
    const target = matches[index];
    if (!target || guardPending()) return;
    closeSearch();
    const group = target.closest('details');
    if (group) group.open = true;
    target.click();
    search.value = '';
    if (getComputedStyle(target).display !== 'none' && target.getClientRects().length) target.focus();
    else $('main').focus();
  }
  search.oninput = renderSearch;
  search.onfocus = renderSearch;
  search.onkeydown = event => {
    if (event.key === 'Escape') { event.preventDefault(); closeSearch(); }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (results.hidden) renderSearch();
      else if (matches.length) selectResult((selected + (event.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length);
    }
    if (event.key === 'Enter' && !results.hidden) { event.preventDefault(); activateResult(selected); }
  };
  document.addEventListener('pointerdown', event => {
    if (!event.target.closest('.navigation-search')) closeSearch();
    if (!event.target.closest('#workspace-menu')) $('workspace-menu').open = false;
  });
  document.addEventListener('focusin', event => { if (!event.target.closest('.navigation-search')) closeSearch(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') $('workspace-menu').open = false;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && account && state === 'open' && !$('dialog').open && !$('appearance-dialog').matches(':popover-open')) {
      event.preventDefault(); search.focus();
    }
  });
  $('workspace-home').onclick = () => { $('workspace-menu').open = false; showCommandCenter(); };
  $('workspace-attention').onclick = async () => {
    if (guardPending()) return;
    await showCommandCenter();
    if (!account || $('command-center-content').hidden || $('command-center-view').hidden) return;
    $('attention-title').focus();
    $('attention-title').scrollIntoView({block:'center'});
  };

  const appearance = $('appearance-dialog'), message = $('appearance-message');
  const presets = new Set(['landscape', 'mist']);
  const preference = () => { try { return localStorage.getItem('beeloft.wallpaper') || 'landscape'; } catch { return 'landscape'; } };
  function markWallpaper() {
    for (const button of appearance.querySelectorAll('[data-wallpaper]'))
      button.setAttribute('aria-pressed', String(button.dataset.wallpaper === root.dataset.wallpaper));
  }
  function paintWallpaper(name, blob) {
    const previous = customURL;
    customURL = blob ? URL.createObjectURL(blob) : null;
    if (customURL) root.style.setProperty('--workspace-wallpaper', `url("${customURL}")`);
    else root.style.removeProperty('--workspace-wallpaper');
    root.dataset.wallpaper = name;
    if (previous) URL.revokeObjectURL(previous);
    markWallpaper();
  }
  async function wallpaperBlob(operation, value) {
    const db = await new Promise((resolve, reject) => {
      const request = indexedDB.open('beeloft.appearance', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('wallpaper');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error('Penyimpanan sedang dipakai tab lain.'));
    });
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction('wallpaper', operation === 'get' ? 'readonly' : 'readwrite');
        const store = tx.objectStore('wallpaper');
        const request = operation === 'put' ? store.put(value, 'custom') : store[operation]('custom');
        tx.oncomplete = () => resolve(request.result);
        tx.onabort = () => reject(tx.error || new Error('Penyimpanan dibatalkan.'));
        tx.onerror = () => reject(tx.error);
      });
    } finally { db.close(); }
  }
  async function validateImage(blob) {
    if (!blob || !['image/jpeg', 'image/png', 'image/webp'].includes(blob.type)) throw new Error('Pilih gambar JPEG, PNG, atau WebP.');
    if (blob.size > 8 * 1024 * 1024) throw new Error('Ukuran gambar maksimal 8 MB.');
    let bitmap;
    try { bitmap = await createImageBitmap(blob); }
    catch { throw new Error('Gambar tidak dapat dibaca.'); }
    const pixels = bitmap.width * bitmap.height;
    bitmap.close();
    if (pixels > 32000000) throw new Error('Resolusi gambar maksimal 32 megapiksel.');
  }
  async function chooseWallpaper(name, blob, reset = false) {
    const revision = ++wallpaperRevision;
    const controls = [...appearance.querySelectorAll('[data-wallpaper],#wallpaper-upload,#wallpaper-reset')];
    controls.forEach(control => { control.disabled = true; });
    message.textContent = '';
    try {
      if (blob) { await validateImage(blob); await wallpaperBlob('put', blob); }
      localStorage.setItem('beeloft.wallpaper', name);
      if (revision === wallpaperRevision) { paintWallpaper(name, blob); message.textContent = 'Latar tersimpan di browser ini.'; }
      if (reset) {
        try { await wallpaperBlob('delete'); }
        catch { message.textContent = 'Latar default tersimpan. Gambar lama belum dapat dihapus dari penyimpanan browser.'; }
      }
    } catch (error) { message.textContent = `Latar belum disimpan. ${error.message}`; }
    finally { controls.forEach(control => { control.disabled = false; }); $('wallpaper-upload').value = ''; }
  }
  for (const button of appearance.querySelectorAll('[data-wallpaper]')) button.onclick = () => chooseWallpaper(button.dataset.wallpaper);
  $('wallpaper-upload').onchange = event => { if (event.target.files[0]) chooseWallpaper('custom', event.target.files[0]); };
  $('wallpaper-reset').onclick = () => chooseWallpaper('landscape', null, true);
  $('appearance-close').onclick = () => { appearance.hidePopover(); $('appearance').focus(); };
  function openAppearance() {
    $('workspace-menu').open = false;
    appearance.querySelector(`input[value="${root.dataset.theme === 'dark' ? 'dark' : 'light'}"]`).checked = true;
    markWallpaper();
    appearance.showPopover();
    $('appearance-close').focus();
  }
  $('appearance').onclick = openAppearance;
  $('workspace-appearance').onclick = openAppearance;
  for (const radio of appearance.querySelectorAll('[name=appearance-theme]')) radio.onchange = () => theme(radio.value, true);
  if (preference() === 'custom') {
    const revision = wallpaperRevision;
    wallpaperBlob('get').then(async blob => {
      await validateImage(blob);
      if (revision === wallpaperRevision) paintWallpaper('custom', blob);
    }).catch(() => { message.textContent = 'Latar tersimpan tidak tersedia. Latar default ditampilkan.'; });
  } else if (presets.has(preference())) paintWallpaper(preference());
  markWallpaper();
  status();
  return {
    session(me) {
      account = me;
      if (state !== 'open') windowState('open');
      closeSearch();
      search.value = '';
      search.disabled = !me;
      $('workspace-home').disabled = !me;
      $('workspace-attention').disabled = !me;
      $('account-detail').textContent = me ? `${me.name} · ${me.role}` : 'Belum masuk';
      $('account-control').setAttribute('aria-label', me ? `Akun ${me.name}` : 'Akun saat ini');
      status();
    }
  };
}
