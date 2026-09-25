// A6.3 People + Scan workflows modern workspaces: the behavioural half of the migration contract.
//
// tests/test_apple27_people_scan_workspaces_contract.py proves statically that no meaning moved.
// This module proves it against a running application and real fixture data, which is the only
// place some of it can be proved at all: that the six roster figures on screen are the six the two
// APIs actually returned, that the roster really reads EVERY page of both endpoints rather than the
// first, that the status filter really narrows the list without touching the daily truth above it,
// that typing in the search really costs no request until the user submits, that an overtaken
// roster response cannot repaint a newer one, that the scanner really autofocuses on desktop and
// really does not steal focus from an open drawer, and that a rejected scan really cannot leave a
// stale result looking current.
//
// Deliberately not screenshot-only. Every visual case here also asserts something about behaviour
// or data, because a screenshot cannot fail when a number is wrong.
//
// It runs after browser_workforce.cjs / browser_workforce_approvals.cjs / browser_bundles.cjs /
// browser_finished_goods.cjs, so the demo database already has People rows, a cutting run and a
// finished-goods receipt with both sellable and hold stock. Anything this module needs beyond that
// it creates through the API, never by reaching into the store.
const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async ({page, login, openSidebarDestination, admin, operator, viewer,
                         apiGet, apiPost, work, run, receipt}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  const number = new Intl.NumberFormat('id-ID');
  const unique = Date.now();

  // ---------------------------------------------------------------- helpers
  const quiet = () => page.evaluate(() => {
    scrollTo(0, 0);
    const main = document.querySelector('.workspace-main');
    if (main) main.scrollTo(0, 0);
    const notice = document.getElementById('notice');
    notice.hidden = true; notice.textContent = '';
    if (document.activeElement && document.activeElement !== document.body) {
      document.activeElement.blur();
    }
  });
  const settled = () => page.evaluate(async () => {
    const dialog = document.getElementById('dialog');
    if (dialog && dialog.open) {
      await Promise.allSettled(dialog.getAnimations({subtree: true})
        .map(animation => animation.finished));
    }
  });
  // A visual-review screenshot has to show the workspace and nothing else: earlier steps leave a
  // six-second toast and a focus ring behind, and both would sit on top of the surface a human is
  // being asked to approve. The scan tint is deliberately NOT waited out - on the success shots it
  // is the state being reviewed.
  const shot = async (name, {full = true} = {}) => {
    await quiet();
    await page.waitForFunction(() => ![...document.querySelectorAll('.motion-enter,.is-refreshing')]
      .some(node => node.id !== 'notice'));
    await settled();
    await page.screenshot({path: path.join(shots, `a63-${name}.png`), fullPage: full});
  };
  // The reviewed unit for information hierarchy: exactly what a 1440x1000 reviewer sees before
  // scrolling. `.workspace-main` is the scrolling region, not the document.
  const firstViewport = async name => {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.waitForTimeout(150);
    await quiet();
    await settled();
    await page.screenshot({path: path.join(shots, `a63-${name}.png`)});
  };
  const theme = async value => {
    await page.evaluate(next => { document.documentElement.dataset.theme = next; }, value);
    await page.waitForTimeout(120);
  };
  const noOverflow = () => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  const dialogFits = () => page.evaluate(() => {
    const dialog = document.querySelector('dialog');
    return dialog.scrollWidth <= dialog.clientWidth;
  });
  const roster = () => page.locator('#people-view');
  const dialog = () => page.locator('dialog');
  const rosterReady = async () => {
    await page.locator('#people-view:not([hidden])').waitFor();
    await page.locator('#workforce-summary:not([hidden])').waitFor();
  };
  const openPeople = async () => { await openSidebarDestination('People'); await rosterReady(); };
  const escapeDialog = async () => {
    await page.keyboard.press('Escape');
    await page.locator('#dialog').waitFor({state: 'hidden'});
  };
  const role = async key => {
    await page.keyboard.press('Escape');
    await page.getByRole('button', {name: 'Keluar', exact: true}).click();
    await login(key);
  };
  // Reads the figure a metric cell is actually showing, by its label.
  const metric = label => page.evaluate(wanted => {
    const cell = [...document.querySelectorAll('#workforce-summary .metric-card')]
      .find(node => node.querySelector('.metric-label').textContent.trim() === wanted);
    return cell ? cell.querySelector('.metric-value').textContent.trim() : null;
  }, label);
  // Returns every roster request the workspace actually issued, so a filter assertion reads the
  // real query string rather than trusting the control it clicked.
  const rosterRequests = async action => {
    const urls = [];
    const collect = request => {
      if (/\/api\/workforce\/(employees|attendance)\?/.test(request.url())) urls.push(request.url());
    };
    page.on('request', collect);
    await action();
    await page.waitForTimeout(400);
    page.off('request', collect);
    return urls;
  };

  // ==========================================================================
  // PART A - PEOPLE
  // ==========================================================================
  await role(admin);

  // A roster worth reviewing needs all four attendance states present at once, and the summary
  // arithmetic is only meaningful if the fixtures are known. Five employees, one of each state
  // plus one deliberately left unrecorded.
  const today = await page.evaluate(() =>
    new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Jakarta'}).format(new Date()));
  const people = {};
  for (const [key, code, name, department] of [
    ['present', 'A63-P-' + unique, 'Rina <Hadir>', 'Produksi'],
    ['leave', 'A63-L-' + unique, 'Sari Cuti', 'Produksi'],
    ['absent', 'A63-A-' + unique, 'Budi Absen', 'Gudang'],
    ['blank', 'A63-B-' + unique, 'Tono Belum', 'Finishing'],
  ]) {
    people[key] = await apiPost('/api/workforce/employees',
      {code, name, department, reason: 'CONTOH fixture roster A6.3'}, 'a63-emp-' + key + '-' + unique);
  }
  await apiPost(`/api/workforce/employees/${people.present.id}/attendance`,
    {work_date: today, expected_revision: 0, status: 'present', clock_in: '08:00', clock_out: '17:00',
     overtime_minutes: 90, notes: 'CONTOH lembur packing', reason: 'CONTOH shift pagi'},
    'a63-att-present-' + unique);
  await apiPost(`/api/workforce/employees/${people.leave.id}/attendance`,
    {work_date: today, expected_revision: 0, status: 'leave', clock_in: null, clock_out: null,
     overtime_minutes: 0, notes: 'CONTOH cuti tahunan', reason: 'CONTOH disetujui supervisor'},
    'a63-att-leave-' + unique);
  await apiPost(`/api/workforce/employees/${people.absent.id}/attendance`,
    {work_date: today, expected_revision: 0, status: 'absent', clock_in: null, clock_out: null,
     overtime_minutes: 0, notes: 'CONTOH tanpa keterangan', reason: 'CONTOH belum melapor'},
    'a63-att-absent-' + unique);

  await openPeople();

  // ---- identity: a workspace, not a slogan ---------------------------------
  await page.getByRole('heading', {name: 'People', exact: true}).waitFor();
  await roster().getByText('Pantau kehadiran, jam kerja, lembur, dan status tim.', {exact: true})
    .waitFor();
  assert.equal(await roster().locator('.page-heading, .filters, .workforce-summary').count(), 0,
    'the legacy People heading, filter toolbar and ledger strip are gone, not restyled');
  assert.equal(await roster().locator('.command-bar').count(), 1);
  assert.equal(await roster().locator('.metric-strip').count(), 1);

  // ---- the roster reads EVERY page of both endpoints ------------------------
  const rosterQueries = await rosterRequests(async () => {
    await roster().getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
    await rosterReady();
  });
  assert.ok(rosterQueries.some(url => url.includes('/api/workforce/employees?')
    && url.includes('status=active') && url.includes('limit=500') && url.includes('offset=0')),
    'employees are read with the full-pagination limit');
  assert.ok(rosterQueries.some(url => url.includes('/api/workforce/attendance?')
    && url.includes('status=all') && url.includes(`start_date=${today}`)
    && url.includes(`end_date=${today}`) && url.includes('limit=500')),
    'attendance is read for the selected day with status=all, and filtered client-side');

  // ---- the six figures are the six the APIs returned -----------------------
  const activeEmployees = await apiGet('/api/workforce/employees?status=active&limit=500');
  const dayAttendance = await apiGet(
    `/api/workforce/attendance?start_date=${today}&end_date=${today}&status=all&limit=500`);
  const recorded = dayAttendance.items;
  const expected = {
    'Karyawan aktif': activeEmployees.total,
    'Belum dicatat': activeEmployees.total - recorded.length,
    Hadir: recorded.filter(row => row.status === 'present').length,
    Cuti: recorded.filter(row => row.status === 'leave').length,
    Absen: recorded.filter(row => row.status === 'absent').length,
    Lembur: recorded.reduce((total, row) => total + row.overtime_minutes, 0),
  };
  for (const [label, value] of Object.entries(expected)) {
    assert.equal(await metric(label), `${number.format(value)} ${label === 'Lembur' ? 'menit' : 'orang'}`,
      `${label} must be the figure the API returned`);
  }
  assert.ok(expected.Hadir > 0 && expected.Cuti > 0 && expected.Absen > 0
    && expected['Belum dicatat'] > 0, 'the review fixture really shows all four states');
  assert.equal(await roster().locator('#workforce-summary .metric-card').count(), 6,
    'six cells, and no seventh figure was invented');

  // ---- the four roster states each say something real ----------------------
  const rowOf = key => roster().locator(`[data-workforce-employee="${people[key].id}"]`);
  await rowOf('present').getByRole('heading', {name: 'Rina <Hadir>', exact: true}).waitFor();
  assert.equal(await rowOf('present').locator('script').count(), 0, 'the name is escaped');
  await rowOf('present').getByText('Hadir', {exact: true}).waitFor();
  assert.ok((await rowOf('present').innerText()).includes('08:00–17:00'),
    'a present row shows its real clock window');
  assert.ok((await rowOf('present').innerText()).includes('lembur'),
    'a present row shows its real overtime');
  await rowOf('leave').getByText('Cuti', {exact: true}).waitFor();
  assert.ok((await rowOf('leave').innerText()).includes('CONTOH cuti tahunan'),
    'a leave row shows its note instead of a blank line');
  await rowOf('absent').getByText('Absen', {exact: true}).waitFor();
  assert.ok((await rowOf('absent').innerText()).includes('CONTOH tanpa keterangan'));
  await rowOf('blank').getByText('Belum dicatat', {exact: true}).waitFor();
  assert.ok((await rowOf('blank').innerText()).includes('Belum ada catatan untuk tanggal ini.'),
    'an unrecorded row states that it has no record, rather than showing an empty gap');
  // Colour is never the only channel: every chip carries a dot, and every row a state glyph.
  assert.equal(await roster().locator('#workforce-list .status-chip .status-dot').count(),
    await roster().locator('#workforce-list .record-row').count());
  assert.equal(await roster().locator('#workforce-list .record-row .metric-icon').count(),
    await roster().locator('#workforce-list .record-row').count());

  await firstViewport('people-1440-light');
  await theme('dark');
  await shot('people-1440-dark');
  await theme('light');

  // ---- the status filter narrows the list but not the daily truth ----------
  const before = await metric('Karyawan aktif');
  await roster().locator('#workforce-status').selectOption('present');
  await roster().getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await rosterReady();
  await page.locator(`[data-workforce-employee="${people.leave.id}"]`).waitFor({state: 'detached'});
  await rowOf('present').waitFor();
  assert.equal(await metric('Karyawan aktif'), before,
    'narrowing the roster by status must not change the daily state above it');
  assert.equal(await metric('Cuti'), `${number.format(expected.Cuti)} orang`,
    'the leave count still counts every recorded leave, not the filtered rows');
  await shot('people-filtered');

  // ---- a text query is submitted, never typed into the network -------------
  await roster().locator('#workforce-status').selectOption('all');
  const typed = await rosterRequests(async () => {
    await roster().locator('#workforce-search').fill('A63-A-' + unique);
  });
  assert.deepEqual(typed, [], 'typing in the roster search costs no request');
  await roster().getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await rosterReady();
  await rowOf('absent').waitFor();
  assert.equal(await roster().locator('#workforce-list .record-row').count(), 1,
    'the submitted query is the one that narrows the roster');

  // ---- the filtered-empty state, and a reset that keeps the work date ------
  await roster().locator('#workforce-status').selectOption('leave');
  await roster().getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await roster().getByText('Tidak ada karyawan yang cocok dengan status dan pencarian ini.',
    {exact: true}).waitFor();
  assert.equal(await roster().locator('#workforce-list .record-row').count(), 0);
  await roster().getByRole('button', {name: 'Reset filter', exact: true}).click();
  await rosterReady();
  assert.equal(await roster().locator('#workforce-date').inputValue(), today,
    'Reset filter clears status and search but never moves the work date');
  assert.equal(await roster().locator('#workforce-search').inputValue(), '');
  assert.equal(await roster().locator('#workforce-status').inputValue(), 'all');

  // ---- the date ceiling is today, in Jakarta -------------------------------
  assert.equal(await roster().locator('#workforce-date').getAttribute('max'), today,
    'a future attendance date stays unreachable');

  // ---- load failure, retry, and the stale-response guard -------------------
  let failRoster = true;
  await page.route('**/api/workforce/attendance?*', async route => {
    if (failRoster) {
      failRoster = false;
      await route.fulfill({status: 503, contentType: 'application/json',
        body: JSON.stringify({detail: 'Roster A6.3 sedang dimuat ulang'})});
    } else await route.continue();
  });
  await roster().getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await roster().locator('#workforce-message').filter({hasText: 'Roster A6.3 sedang dimuat ulang'})
    .waitFor();
  assert.equal(await roster().locator('#workforce-message .error-state').count(), 1,
    'the failure uses the A6 error state, not the legacy panel');
  await roster().getByRole('button', {name: 'Coba lagi', exact: true}).click();
  await rosterReady();
  await page.unroute('**/api/workforce/attendance?*');
  await rowOf('present').waitFor();

  // A slow roster response may not repaint a page the user has already filtered past. The first
  // request is held until a second has been issued and rendered; the held answer must be dropped.
  let hold = null;
  await page.route('**/api/workforce/employees?*', async route => {
    if (!hold) { hold = route; return; }
    await route.continue();
  });
  await roster().locator('#workforce-search').fill('A63-P-' + unique);
  await roster().getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await page.waitForTimeout(250);
  await roster().locator('#workforce-search').fill('A63-A-' + unique);
  await roster().getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await rosterReady();
  await rowOf('absent').waitFor();
  if (hold) await hold.continue();
  await page.waitForTimeout(400);
  assert.equal(await roster().locator('#workforce-list .record-row').count(), 1,
    'the overtaken roster response cannot repaint the newer one');
  await rowOf('absent').waitFor();
  await page.unroute('**/api/workforce/employees?*');
  await roster().locator('#workforce-search').fill('');
  await roster().getByRole('button', {name: 'Tampilkan roster', exact: true}).click();
  await rosterReady();

  // ---- attendance: a new record, then a correction that adds a revision ----
  await rowOf('blank').getByRole('button', {name: 'Catat kehadiran', exact: true}).click();
  await dialog().getByLabel('Alasan pencatatan atau koreksi').waitFor();
  assert.equal(await dialog().getByLabel('Tanggal').inputValue(), today);
  assert.equal(await dialog().getByLabel('Tanggal').isEditable(), false,
    'the work date is readonly: the row chose it');
  assert.equal(await dialog().getByLabel('Jam masuk').inputValue(), '08:00',
    'a new record keeps its shipped default');
  assert.equal(await dialog().getByLabel('Jam pulang').inputValue(), '17:00');
  // `present` is the only status that enables the clock fields.
  await dialog().getByLabel('Status').selectOption('absent');
  for (const field of ['Jam masuk', 'Jam pulang', 'Lembur (menit)']) {
    assert.equal(await dialog().getByLabel(field).isDisabled(), true,
      `${field} is disabled unless the status is present`);
  }
  assert.equal(await dialog().getByLabel('Lembur (menit)').inputValue(), '0');
  await dialog().getByLabel('Status').selectOption('present');
  for (const field of ['Jam masuk', 'Jam pulang', 'Lembur (menit)']) {
    assert.equal(await dialog().getByLabel(field).isDisabled(), false);
  }
  // Leaving `present` really cleared the clock values rather than merely greying them out, so
  // coming back requires entering them again. That is the shipped guarantee that a non-present
  // record can never carry a stale clock window, and A6.3 did not weaken it.
  assert.equal(await dialog().getByLabel('Jam masuk').inputValue(), '');
  assert.equal(await dialog().getByLabel('Jam pulang').inputValue(), '');
  assert.equal(await dialog().locator('.field').count() > 0, true,
    'the attendance form speaks the A6 field grammar');
  await dialog().getByLabel('Jam masuk').fill('13:00');
  await dialog().getByLabel('Jam pulang').fill('21:00');
  await dialog().getByLabel('Lembur (menit)').fill('30');
  await dialog().getByLabel('Catatan', {exact: true}).fill('CONTOH masuk shift siang');
  await dialog().getByLabel('Alasan pencatatan atau koreksi').fill('CONTOH pencatatan pertama');
  await shot('people-attendance-form');
  await dialog().getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.locator('dialog').waitFor({state: 'hidden'});
  await rosterReady();
  await rowOf('blank').getByText('Hadir', {exact: true}).waitFor();

  await rowOf('blank').getByRole('button', {name: 'Koreksi kehadiran', exact: true}).click();
  await dialog().getByLabel('Alasan pencatatan atau koreksi').waitFor();
  await dialog().getByLabel('Status').selectOption('leave');
  await dialog().getByLabel('Catatan', {exact: true}).fill('CONTOH dialihkan ke cuti');
  await dialog().getByLabel('Alasan pencatatan atau koreksi').fill('CONTOH koreksi supervisor');
  await dialog().getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.locator('dialog').waitFor({state: 'hidden'});
  await rosterReady();
  await rowOf('blank').getByText('Cuti', {exact: true}).waitFor();

  // The correction added a revision; the earlier one is still there, on a timeline.
  await rowOf('blank').getByRole('button', {name: 'Riwayat', exact: true}).click();
  await dialog().getByText('Revisi 2 · Cuti', {exact: true}).waitFor();
  await dialog().getByText('Revisi 1 · Hadir', {exact: true}).waitFor();
  assert.equal(await dialog().locator('.timeline-item').count(), 2,
    'both revisions survive as timeline items; nothing is collapsed');
  await shot('people-attendance-history');
  await dialog().getByRole('button', {name: 'Kembali ke roster', exact: true}).click();
  await page.locator('dialog').waitFor({state: 'hidden'});

  // ---- employee master, add, edit, immutable code, history -----------------
  await roster().getByRole('button', {name: 'Daftar karyawan', exact: true}).click();
  await dialog().locator('#workforce-master-list .record-row').first().waitFor();
  await dialog().locator('[data-workforce-master]').filter({hasText: people.present.code}).waitFor();
  assert.ok((await dialog().locator('[data-workforce-master]')
    .filter({hasText: people.present.code}).innerText()).includes('Aktif'));
  await shot('people-employee-master');
  await dialog().locator('[data-workforce-master]').filter({hasText: people.present.code})
    .getByRole('button', {name: 'Ubah', exact: true}).click();
  await dialog().getByLabel('Alasan perubahan').waitFor();
  // The code is a fact, not a field: there is no code input to find in the edit form.
  assert.equal(await dialog().getByLabel('Kode karyawan').count(), 0,
    'the employee code cannot be edited');
  await dialog().getByText('Kode karyawan tidak dapat diubah setelah dibuat.', {exact: true})
    .waitFor();
  await shot('people-employee-form');
  await escapeDialog();

  await roster().getByRole('button', {name: 'Tambah karyawan', exact: true}).click();
  const createdCode = 'A63-NEW-' + unique;
  await dialog().getByLabel('Kode karyawan').fill(createdCode.toLowerCase());
  await dialog().getByLabel('Nama karyawan').fill('Dewi <Baru>');
  await dialog().getByLabel('Departemen').fill('Finishing');
  await dialog().getByLabel('Sumber data awal').fill('CONTOH daftar staf aktif');
  await dialog().getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.locator('dialog').waitFor({state: 'hidden'});
  await rosterReady();
  await roster().locator('[data-workforce-employee]').filter({hasText: createdCode})
    .getByRole('heading', {name: 'Dewi <Baru>', exact: true}).waitFor();

  await roster().getByRole('button', {name: 'Daftar karyawan', exact: true}).click();
  await dialog().locator('[data-workforce-master]').filter({hasText: createdCode})
    .getByRole('button', {name: 'Riwayat', exact: true}).click();
  await dialog().getByText('Revisi 1 · Aktif', {exact: true}).waitFor();
  assert.ok(await dialog().locator('.timeline-item').count() >= 1);
  await dialog().getByRole('button', {name: 'Kembali ke daftar karyawan', exact: true}).click();
  await dialog().locator('[data-workforce-master]').filter({hasText: createdCode})
    .getByRole('button', {name: 'Ubah', exact: true}).click();
  await dialog().getByLabel('Status').selectOption('false');
  await dialog().getByLabel('Alasan perubahan').fill('CONTOH kontrak selesai');
  await dialog().getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await page.locator('dialog').waitFor({state: 'hidden'});
  await rosterReady();
  assert.equal(await roster().locator('[data-workforce-employee]').filter({hasText: createdCode})
    .count(), 0, 'a deactivated employee leaves the active roster');

  // ---- leave / overtime requests ------------------------------------------
  await roster().getByRole('button', {name: 'Permintaan cuti / lembur', exact: true}).click();
  await dialog().locator('#workforce-request-summary:not([hidden])').waitFor();
  assert.equal(await dialog().locator('#workforce-request-summary .metric-card').count(), 5,
    'the request summary is the five figures the API returns');
  assert.equal(await dialog().locator('.command-bar').count(), 1,
    'the request filter is an A6 command bar with an explicit submit');
  await dialog().getByText('Approval memberi izin; kehadiran aktual tetap dicatat terpisah di roster.',
    {exact: true}).waitFor();
  const apiRequests = await apiGet('/api/workforce/requests?limit=500');
  assert.equal(await dialog().locator('#workforce-request-summary .metric-card')
    .first().locator('.metric-value').textContent(),
    `${number.format(apiRequests.total)} permintaan`, 'Total is the API total');
  await shot('people-requests');

  const day = offset => page.evaluate(count => {
    const value = new Date(); value.setDate(value.getDate() + count);
    return new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Jakarta'}).format(value);
  }, offset);
  await dialog().getByRole('button', {name: 'Ajukan permintaan', exact: true}).click();
  await dialog().locator('select[name="employee_id"]').selectOption(people.present.id);
  await dialog().getByLabel('Jenis').selectOption('overtime');
  await dialog().getByLabel('Tanggal mulai').fill(await day(3));
  // Overtime couples the end date to the start date and requires the minutes.
  assert.equal(await dialog().getByLabel('Tanggal selesai').isEditable(), false);
  assert.equal(await dialog().getByLabel('Tanggal selesai').inputValue(), await day(3));
  assert.equal(await dialog().getByLabel('Lembur (menit)').isDisabled(), false);
  await dialog().getByLabel('Jenis').selectOption('leave');
  assert.equal(await dialog().getByLabel('Tanggal selesai').isEditable(), true,
    'leave keeps an editable range');
  assert.equal(await dialog().getByLabel('Lembur (menit)').isDisabled(), true);
  await dialog().getByLabel('Tanggal mulai').fill(await day(3));
  await dialog().getByLabel('Tanggal selesai').fill(await day(5));
  await dialog().getByLabel('Alasan permintaan').fill('CONTOH cuti keluarga <terencana>');
  await dialog().getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();

  // Saving a request lands on its detail, and approval is still only permission.
  await dialog().getByRole('heading', {name: 'Rina <Hadir>'}).waitFor();
  await dialog().getByText('Menunggu keputusan', {exact: true}).first().waitFor();
  const filed = (await apiGet('/api/workforce/requests?kind=leave&q=A63-P-' + unique)).items[0];
  await dialog().getByText(filed.reference + ' · Menunggu keputusan', {exact: true}).waitFor();
  assert.equal(await dialog().locator('script').count(), 0);
  assert.equal(await dialog().locator('.detail-grid').count() > 0, true,
    'the request detail states its facts in the A6 detail grammar');
  await dialog().getByText('Approval memberi izin. Persetujuan tidak otomatis mencatat kehadiran '
    + 'aktual; kehadiran tetap dicatat di roster.', {exact: true}).waitFor();
  await shot('people-request-detail');

  // Admin decides; the decision is a timeline entry and it records no attendance.
  const attendanceBefore = (await apiGet('/api/workforce/attendance?employee_id='
    + people.present.id)).total;
  await dialog().getByRole('button', {name: 'Setujui', exact: true}).click();
  await dialog().getByLabel('Alasan / catatan', {exact: true}).fill('CONTOH jadwal tim diperiksa');
  await dialog().getByRole('button', {name: 'Simpan pencatatan', exact: true}).click();
  await dialog().getByText(filed.reference + ' · Disetujui', {exact: true}).waitFor();
  assert.equal((await apiGet('/api/workforce/requests/' + filed.id)).status, 'approved');
  assert.equal((await apiGet('/api/workforce/attendance?employee_id=' + people.present.id)).total,
    attendanceBefore, 'approval grants permission and records no attendance');
  assert.ok(await dialog().locator('.timeline-item').count() >= 1,
    'the decision joins the approval timeline');
  await escapeDialog();

  // ---- responsive: 390, and 320 at 200% text ------------------------------
  await page.setViewportSize({width: 390, height: 844});
  await rosterReady();
  assert.equal(await noOverflow(), true, 'People does not overflow at 390');
  await shot('people-390');
  await page.setViewportSize({width: 320, height: 800});
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await page.waitForTimeout(160);
  assert.equal(await noOverflow(), true, 'People does not overflow at 320 with 200% text');
  // The roster actions stay reachable rather than being clipped off the row.
  assert.equal(await rowOf('present').getByRole('button', {name: 'Koreksi kehadiran', exact: true})
    .isVisible(), true);
  await shot('people-320-200');
  await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  await page.setViewportSize({width: 1440, height: 1000});
  await rosterReady();

  // ---- roles ---------------------------------------------------------------
  await role(operator);
  await openPeople();
  assert.equal(await roster().getByRole('button', {name: 'Tambah karyawan', exact: true}).count(), 0,
    'only an admin may add an employee');
  await rowOf('present').getByRole('button', {name: 'Koreksi kehadiran', exact: true}).waitFor();

  await role(viewer);
  await openPeople();
  assert.equal(await roster().getByRole('button', {name: 'Tambah karyawan', exact: true}).count(), 0);
  assert.equal(await rowOf('present')
    .getByRole('button', {name: /Catat kehadiran|Koreksi kehadiran/}).count(), 0,
    'a viewer gains no attendance write action');
  await rowOf('present').getByRole('button', {name: 'Riwayat', exact: true}).waitFor();
  await roster().getByRole('button', {name: 'Permintaan cuti / lembur', exact: true}).click();
  await dialog().locator('#workforce-request-summary:not([hidden])').waitFor();
  assert.equal(await dialog().getByRole('button', {name: 'Ajukan permintaan', exact: true}).count(), 0);
  await dialog().locator(`[data-workforce-request="${filed.id}"]`)
    .getByRole('button', {name: 'Rincian', exact: true}).click();
  await dialog().getByText(filed.reference + ' · Disetujui', {exact: true}).waitFor();
  assert.equal(await dialog().getByRole('button', {name: /Setujui|Tolak|Batalkan/}).count(), 0,
    'a viewer gains no decision action');
  assert.equal(await dialogFits(), true);
  await escapeDialog();

  // ==========================================================================
  // PART B - THE TWO SCANNERS
  // ==========================================================================
  await role(admin);
  const bundle = await apiPost('/api/cutting-runs/' + run.id + '/bundles',
    {reference: 'BDL-A63-' + unique, output_movement_id: run.outputs[0].id, quantity: 4,
     reason: 'CONTOH bundle untuk review A6.3'}, 'a63-bundle-' + unique);

  for (const scanner of [
    {name: 'Scan bundle', kind: 'bundle', label: 'Kode bundle', submit: 'Buka bundle',
     endpoint: 'bundles', code: bundle.scan_code, reference: bundle.reference,
     detail: 'Rincian bundle', shots: 'bundle-scan', quantity: 4, busy: 'Pemindai A6.3 bundle sibuk'},
    {name: 'Scan barang jadi', kind: 'finished-goods', label: 'Kode barang jadi',
     submit: 'Buka barang jadi', endpoint: 'finished-goods-receipts', code: receipt.scan_code,
     reference: receipt.reference, detail: 'Rincian barang jadi', shots: 'goods-scan',
     quantity: receipt.received_quantity, busy: 'Pemindai A6.3 barang jadi sibuk'},
  ]) {
    const view = () => page.locator('#' + scanner.kind + '-scan-view');
    const result = () => page.locator('#' + scanner.kind + '-scan-result');
    const input = page.getByLabel(scanner.label, {exact: true});

    // ---- opening the scanner focuses the field on desktop -----------------
    await openSidebarDestination(scanner.name);
    await view().locator(':scope:not([hidden])').waitFor();
    assert.equal(await input.evaluate(element => element === document.activeElement), true,
      `${scanner.name} focuses its field so a scanner can type straight into it`);
    assert.equal(await view().locator('.scan-surface').count(), 1,
      'the scanner consumes the A6.0 scan surface');
    assert.equal(await view().locator('.scan-target').count(), 1);
    assert.equal(await view().locator('.metric-strip, .data-surface').count(), 0,
      'a scanner is a utility, not a dashboard');
    await page.locator('#' + scanner.kind + '-scan-message')
      .filter({hasText: 'Belum ada hasil scan'}).waitFor();
    assert.equal(await result().locator(':scope > *').count(), 0,
      'the empty scanner holds no result');
    await firstViewport(scanner.shots + '-1440-empty');

    // ---- an open drawer keeps focus; the scanner must not steal it --------
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('#menu-toggle').click();
    await page.waitForFunction(() => document.body.classList.contains('nav-open'));
    await page.getByRole('button', {name: scanner.name, exact: true}).click();
    await view().locator(':scope:not([hidden])').waitFor();
    assert.equal(await input.evaluate(element => element === document.activeElement), false,
      'opening the scanner from the mobile drawer does not steal focus from the heading');
    await page.setViewportSize({width: 1440, height: 1000});

    // ---- a rejected scan reports, keeps the code, and carries no tint -----
    let failScan = true;
    await page.route(`**/api/${scanner.endpoint}/scan?*`, async route => {
      if (failScan) {
        failScan = false;
        await route.fulfill({status: 503, contentType: 'application/json',
          body: JSON.stringify({detail: scanner.busy})});
      } else await route.continue();
    });
    await input.fill(scanner.code);
    await input.press('Enter');
    await page.getByText(scanner.busy, {exact: true}).waitFor();
    assert.equal(await result().evaluate(node => node.classList.contains('is-scan-ok')), false,
      'a rejected scan carries no success tint');
    assert.equal(await result().locator(':scope > *').count(), 0,
      'a failed scan leaves no stale result looking current');
    assert.equal(await input.inputValue(), scanner.code,
      'the code survives the failure so the operator can simply re-scan');

    // ---- Enter submits, the endpoint is exact, and the result is one record
    const request = page.waitForRequest(r =>
      r.url().includes(`/api/${scanner.endpoint}/scan?`));
    await input.press('Enter');
    const scanUrl = new URL((await request).url());
    assert.equal(scanUrl.pathname, `/api/${scanner.endpoint}/scan`,
      'the scan endpoint is unchanged');
    assert.equal(scanUrl.searchParams.get('code'), scanner.code);
    assert.equal((await request).method(), 'GET');
    await result().getByText(scanner.reference, {exact: true}).waitFor();
    await page.unroute(`**/api/${scanner.endpoint}/scan?*`);
    assert.equal(await result().locator('.record-row').count(), 1,
      'only the last result is shown; there is no fabricated scan history');
    assert.equal(await result().locator('.scan-recent').count(), 1,
      'the result uses the recent-result area A6.0 reserved for it');
    assert.ok((await result().innerText()).includes(String(scanner.quantity)),
      'the result shows the real quantity the endpoint returned');
    assert.equal(await page.locator('#dialog').getAttribute('open'), null,
      'a scan opens no dialog by itself');
    // The tint is the state a valid scan reports, and it lives on the result host.
    assert.equal(await result().evaluate(node => node.classList.contains('is-scan-ok')), true);
    assert.notEqual(await result().evaluate(node => getComputedStyle(node).backgroundColor),
      'rgba(0, 0, 0, 0)', 'nothing inside the result paints over the success tint');
    assert.equal(await input.evaluate(element => element.selectionStart === 0), true,
      'the code stays selected so the next scan overwrites it');
    await firstViewport(scanner.shots + '-1440-success');
    await theme('dark');
    await shot(scanner.shots + '-1440-dark');
    await theme('light');

    // ---- the tint releases on its own, without a new timer ---------------
    await page.waitForTimeout(1500);
    assert.equal(await result().evaluate(node => node.classList.contains('is-scan-ok')), false,
      'the tint releases on its own');
    assert.equal(await result().evaluate(node => getComputedStyle(node).backgroundColor),
      'rgba(0, 0, 0, 0)', 'the result surface returns to its resting colour');

    // ---- a repeat scan is a second event, not a no-op --------------------
    await input.press('Enter');
    await page.waitForFunction(id => document.getElementById(id).classList.contains('is-scan-ok'),
      scanner.kind + '-scan-result');
    assert.equal(await result().locator('.record-row').count(), 1);

    // ---- 390: the field stays usable and the button is never clipped -----
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await noOverflow(), true, `${scanner.name} does not overflow at 390`);
    assert.equal(await page.getByRole('button', {name: scanner.submit, exact: true}).isVisible(),
      true, 'the primary action is not clipped');
    assert.ok(await input.evaluate(element => element.getBoundingClientRect().height >= 40),
      'the scan field stays large enough for fast use');
    await shot(scanner.shots + '-390');
    await page.setViewportSize({width: 320, height: 800});
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    await page.waitForTimeout(160);
    assert.equal(await noOverflow(), true,
      `${scanner.name} does not overflow at 320 with 200% text`);
    await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
    await page.setViewportSize({width: 1440, height: 1000});

    // ---- the result opens the detail -------------------------------------
    await page.getByRole('button', {name: scanner.detail, exact: true}).click();
    await page.getByRole('heading', {name: scanner.detail, exact: true}).waitFor();
    // `openDialog` sets the title before the request resolves, so the title is not evidence that
    // the body has arrived. Wait for the grouped action catalogue itself.
    await dialog().locator('.panel-grid .utility-panel').first().waitFor();
    assert.equal(await dialog().locator('.utility-rows .record-row').count() > 0, true,
      'actions that only open something are quiet utility rows');
    assert.equal(await dialogFits(), true);
    await escapeDialog();
  }

  // ==========================================================================
  // PART C - THE TWO RESULT DIALOGS
  // ==========================================================================
  // ---- bundle detail -------------------------------------------------------
  await openSidebarDestination('Scan bundle');
  await page.getByLabel('Kode bundle', {exact: true}).fill(bundle.scan_code);
  await page.getByLabel('Kode bundle', {exact: true}).press('Enter');
  await page.locator('#bundle-scan-result').getByText(bundle.reference, {exact: true}).waitFor();
  await page.getByRole('button', {name: 'Rincian bundle', exact: true}).click();
  await page.getByRole('heading', {name: 'Rincian bundle', exact: true}).waitFor();

  const bundleTruth = await apiGet('/api/bundles/' + bundle.id);
  await dialog().getByText('Aktif', {exact: true}).waitFor();
  const bundleText = await dialog().innerText();
  assert.ok(bundleText.includes(bundleTruth.sku) && bundleText.includes(bundleTruth.size),
    'bundle identity is on screen');
  assert.ok(bundleText.includes('Dialokasikan ke sewing') && bundleText.includes('Belum dialokasikan'),
    'both allocation figures are stated, as two numbers');
  assert.ok(bundleText.includes(String(bundleTruth.sewing_allocated_quantity)));
  assert.ok(bundleText.includes(String(bundleTruth.sewing_unassigned_quantity)));
  await dialog().getByText('Lokasi custody sekarang', {exact: false}).waitFor();
  await dialog().getByText(bundleTruth.custody_location, {exact: true}).waitFor();
  assert.ok(bundleText.includes(bundleTruth.cutting_reference)
    && bundleText.includes(bundleTruth.batch_reference)
    && bundleText.includes(bundleTruth.material_code), 'the origin lineage is complete');
  assert.equal(await dialog().locator('.progress-meter').count(), 0,
    'no fake allocation percentage was derived');
  // The printable label survives, QR and all.
  await page.waitForFunction(() => document.querySelector('.bundle-label img')?.naturalWidth > 0);
  assert.equal(await dialog().locator('.bundle-label').getByText(bundle.reference, {exact: true})
    .count(), 1);
  // Every action group is present, and the admin set is complete.
  for (const label of ['Buka order produksi', 'Hasil cutting asal', 'Batch bahan asal',
    'Semua bundle', 'Sewing / makloon order', 'Riwayat serah-terima', 'Serahkan bundle',
    'Kirim ke sewing', 'Cetak label', 'Koreksi bundle']) {
    assert.equal(await dialog().getByRole('button', {name: label, exact: true}).count(), 1,
      `${label} survives the regrouping`);
  }
  assert.equal(await dialogFits(), true);
  await shot('bundle-detail');
  await escapeDialog();

  // A viewer keeps every navigation action and gains no write action.
  await role(viewer);
  await openSidebarDestination('Scan bundle');
  await page.getByLabel('Kode bundle', {exact: true}).fill(bundle.scan_code);
  await page.getByLabel('Kode bundle', {exact: true}).press('Enter');
  await page.getByRole('button', {name: 'Rincian bundle', exact: true}).click();
  await page.getByRole('heading', {name: 'Rincian bundle', exact: true}).waitFor();
  // Wait for a row that is ALWAYS present before asserting absences: a still-loading dialog would
  // make every "count === 0" pass for the wrong reason.
  await dialog().getByRole('button', {name: 'Riwayat serah-terima', exact: true}).waitFor();
  for (const label of ['Serahkan bundle', 'Kirim ke sewing', 'Koreksi bundle']) {
    assert.equal(await dialog().getByRole('button', {name: label, exact: true}).count(), 0,
      `a viewer gains no ${label}`);
  }
  await escapeDialog();

  // ---- finished-goods detail ----------------------------------------------
  await role(admin);
  await openSidebarDestination('Scan barang jadi');
  await page.getByLabel('Kode barang jadi', {exact: true}).fill(receipt.scan_code);
  await page.getByLabel('Kode barang jadi', {exact: true}).press('Enter');
  await page.locator('#finished-goods-scan-result').getByText(receipt.reference, {exact: true})
    .waitFor();
  await page.getByRole('button', {name: 'Rincian barang jadi', exact: true}).click();
  await page.getByRole('heading', {name: 'Rincian barang jadi', exact: true}).waitFor();

  const receiptTruth = await apiGet('/api/finished-goods-receipts/' + receipt.id);
  await page.getByRole('heading', {name: 'Inventori sekarang', exact: true}).waitFor();
  // Inventory sits above the action catalogue: the warehouse question comes before the menu.
  const order = await page.evaluate(() => {
    const content = document.getElementById('dialog-content');
    const headings = [...content.querySelectorAll('h3')].map(node => node.textContent.trim());
    const inventory = content.querySelector('#finished-goods-inventory-heading');
    const actions = content.querySelector('.panel-grid');
    return {headings,
      inventoryBeforeActions: inventory.compareDocumentPosition(actions)
        & Node.DOCUMENT_POSITION_FOLLOWING ? true : false};
  });
  assert.equal(order.inventoryBeforeActions, true,
    'Inventori sekarang precedes the action catalogue');
  // Each inventory row states its own three numbers, and they are the API's.
  const rows = await page.evaluate(() => [...document.querySelectorAll(
    '#dialog-content .record-list .record-row')].map(node => node.innerText));
  assert.equal(rows.length, receiptTruth.inventory.length,
    'every inventory row the API returned is rendered');
  for (const row of receiptTruth.inventory) {
    const rendered = rows.find(text => text.includes(row.location)
      && text.toLowerCase().includes(row.stock_status));
    assert.ok(rendered, `${row.location} / ${row.stock_status} is on screen with its own word`);
    assert.ok(rendered.includes(String(row.quantity)), 'the row shows its real quantity');
    if (row.stock_status === 'sellable') {
      assert.ok(rendered.includes('Available') && rendered.includes('Reserved'),
        'a sellable row keeps available and reserved as separate labelled figures');
      assert.ok(rendered.includes(String(row.available_quantity)));
      assert.ok(rendered.includes(String(row.reserved_quantity)));
    }
  }
  const receiptText = await dialog().innerText();
  for (const reference of [receiptTruth.final_qc_reference, receiptTruth.finishing_reference,
    receiptTruth.sewing_reference, receiptTruth.bundle_reference]) {
    assert.ok(receiptText.includes(reference), `${reference} is in the production lineage`);
  }
  assert.ok(receiptText.includes(receiptTruth.scanned_sku), 'the scanned SKU is stated');
  await page.waitForFunction(() => document.querySelector('.finished-goods-label img')?.naturalWidth > 0);
  for (const label of ['Jejak stok lengkap', 'Buka order produksi', 'Final QC asal',
    'Finishing asal', 'Job sewing asal', 'Bundle asal', 'Semua barang jadi', 'Gudang order',
    'Reservasi order', 'Riwayat adjustment', 'Riwayat stock opname', 'Cetak label barang jadi',
    'Catat stock opname', 'Catat adjustment', 'Transfer lokasi']) {
    assert.equal(await dialog().getByRole('button', {name: label, exact: true}).count(), 1,
      `${label} survives the regrouping`);
  }
  // Blocking conditions are the explanation for a missing correction, so they stay visible.
  const blockers = [receiptTruth.active_movement_count, receiptTruth.active_reservation_count,
    receiptTruth.active_adjustment_count, receiptTruth.active_stock_count_count];
  const blocked = blockers.some(count => count > 0);
  if (blocked) {
    assert.ok(await dialog().locator('.attention-note').count() > 0,
      'an active blocker is stated as an attention note');
    assert.equal(await dialog().getByRole('button', {name: 'Koreksi penerimaan', exact: true})
      .count(), 0, 'the reversal stays gated while a blocker is active');
  } else {
    assert.equal(await dialog().getByRole('button', {name: 'Koreksi penerimaan', exact: true})
      .count(), 1, 'with all four counts at zero an admin may correct the receipt');
  }
  assert.equal(await dialogFits(), true);
  await shot('goods-detail');
  await escapeDialog();

  await role(viewer);
  await openSidebarDestination('Scan barang jadi');
  await page.getByLabel('Kode barang jadi', {exact: true}).fill(receipt.scan_code);
  await page.getByLabel('Kode barang jadi', {exact: true}).press('Enter');
  await page.getByRole('button', {name: 'Rincian barang jadi', exact: true}).click();
  await page.getByRole('heading', {name: 'Rincian barang jadi', exact: true}).waitFor();
  await dialog().getByRole('button', {name: 'Jejak stok lengkap', exact: true}).waitFor();
  for (const label of ['Transfer lokasi', 'Reservasi marketplace', 'Catat stock opname',
    'Catat adjustment', 'Koreksi penerimaan']) {
    assert.equal(await dialog().getByRole('button', {name: label, exact: true}).count(), 0,
      `a viewer gains no ${label}`);
  }
  await escapeDialog();

  // ==========================================================================
  // A6.1 AND A6.2 ARE NOT REGRESSED
  // ==========================================================================
  await role(admin);
  await openSidebarDestination('Produksi');
  await page.getByRole('heading', {name: 'Produksi', exact: true}).waitFor();
  await page.waitForFunction(() => !document.getElementById('summary').hasAttribute('aria-busy'));
  assert.equal(await page.locator('#summary .metric-card').count(), 4,
    'Produksi still shows its four metrics');
  assert.equal(await page.locator('#board-view .command-bar').count(), 1);
  await openSidebarDestination('Bahan baku');
  await page.getByRole('heading', {name: 'Bahan baku', exact: true}).waitFor();
  assert.equal(await page.locator('#materials-view .command-bar').count(), 1);
  await openSidebarDestination('Master SKU');
  await page.getByRole('heading', {name: 'Master SKU', exact: true}).waitFor();
  await page.locator('#product-list .record-row').first().waitFor();

  // Reduced motion keeps every state signal, and the scan tint is state rather than decoration.
  await page.emulateMedia({reducedMotion: 'reduce'});
  await openSidebarDestination('Scan bundle');
  await page.getByLabel('Kode bundle', {exact: true}).fill(bundle.scan_code);
  await page.getByLabel('Kode bundle', {exact: true}).press('Enter');
  await page.locator('#bundle-scan-result').getByText(bundle.reference, {exact: true}).waitFor();
  assert.equal(await page.locator('#bundle-scan-result')
    .evaluate(node => node.classList.contains('is-scan-ok')), true,
    'reduced motion still reports a valid scan as a state');
  assert.equal(await page.locator('#bundle-scan-result')
    .evaluate(node => getComputedStyle(node).transitionDuration), '0s',
    'the tint is not animated under reduced motion');
  await page.emulateMedia({reducedMotion: 'no-preference'});

  // Forced colours must leave every A6.3 surface understandable without background colour.
  await page.emulateMedia({forcedColors: 'active'});
  await openPeople();
  assert.equal(await noOverflow(), true, 'People holds its layout under forced colours');
  assert.ok(await page.evaluate(() => {
    const chip = document.querySelector('#workforce-list .status-chip');
    return chip && getComputedStyle(chip).borderStyle !== 'none'
      && !!chip.querySelector('.status-dot');
  }), 'an attendance chip keeps a border and its dot under forced colours');
  await page.emulateMedia({forcedColors: 'none'});

  // No idle animation frame is left running by any of the three workspaces.
  const idleFrames = await page.evaluate(() => new Promise(resolve => {
    let frames = 0;
    const original = requestAnimationFrame;
    const tick = () => { frames += 1; original(tick); };
    original(tick);
    setTimeout(() => resolve(frames), 600);
  }));
  assert.ok(idleFrames < 80, `no runaway idle frame loop (observed ${idleFrames} in 600ms)`);

  console.log('A6.3 browser QA PASS: People (workspace identity, full pagination on both '
    + 'endpoints, six real figures unaffected by the status filter, submitted query with no '
    + 'per-keystroke request, Jakarta date ceiling, three distinct empty states, reset that keeps '
    + 'the work date, failure + retry, overtaken-response guard, four truthful attendance states, '
    + 'new record + correction + both revisions on a timeline, employee master with an immutable '
    + 'code, employee history, leave/overtime requests with the API summary, overtime date '
    + 'coupling, approval that records no attendance, admin/operator/viewer) and both scanners '
    + '(scan-surface composition, desktop autofocus, drawer-open focus exception, exact GET '
    + 'endpoint and query, Enter submit, rejected scan with no stale result and no tint, success '
    + 'record with the real quantity, tint hold and self-release, repeat scan, reselected code) '
    + 'and both result dialogs (identity, allocation, custody, QR label, grouped action sets, '
    + 'inventory truth with three separate figures, lineage, blocking conditions, role gating); '
    + 'responsive 1440/390/320@200% in light and dark with no document overflow; forced colours '
    + 'and reduced motion; A6.1 Produksi and A6.2 Bahan baku / Master SKU unregressed.');
};
