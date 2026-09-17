# Bukti pengujian: kegagalan logout dan total approval di luar batas halaman

Rencana: [audit P2 plan](audit-p2-plan.md).

## Baseline

| | |
|---|---|
| Commit baseline | `14150c65a97e78b13febba7234bf553b2c78fa84` (`main`) |
| Aplikasi / schema | 0.84.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/audit-p2-logout-and-approval-aggregates` |
| Working tree awal | bersih (`git status --porcelain` kosong) |
| Suite baseline | `Ran 389 tests in 259.985s` — **OK** |

Baseline ini adalah commit terakhir pada `main` dan sudah memuat ketiga perbaikan P1. Tidak ada checkout
paksa ke commit lama dan tidak ada perubahan lokal yang dibuang.

## Lingkungan

Python 3.12.13 pada venv bersih (`.venv`, sudah tercakup `.gitignore`), Node.js 22.23.2,
Playwright 1.63.0 dengan Chromium 153.0.8010.12, Linux. Seluruh perintah dijalankan dari akar
repositori, kecuali smoke test paket yang sengaja dijalankan dari luar source checkout. Build tool
(`build==1.6.1`) dipasang pada venv tersendiri sehingga dependensi aplikasi tidak tersentuh.

Semua reproduksi dan pengujian memakai database sementara sekali pakai
(`tempfile.TemporaryDirectory` pada test, `tests/run_browser.py` membangun demo database sendiri, dan
smoke test paket memakai `disposable.sqlite3` miliknya). Tidak ada database bisnis atau produksi yang
disentuh.

## Ringkasan hasil

| Pemeriksaan | Hasil |
|---|---|
| `python -m unittest discover -s tests` | `Ran 433 tests` — **OK**. Sebelumnya 389; 44 test baru. |
| `python -m pip check` | `No broken requirements found` |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs` | bersih |
| `node --check beeloft/static/client.mjs` | bersih |
| `node tests/test_client.mjs` | `Client checks PASS` + `CSV client checks PASS` |
| `python tests/run_browser.py --node node --playwright-module playwright --channel chromium` | 65 modul acceptance **PASS**, `assert.deepEqual(errors,[])` bersih. Sebelumnya 63; 2 modul baru. |
| `python -m build` lalu install wheel dan sdist ke venv bersih | **OK**. Lihat bagian 5. |

Channel yang dipakai adalah `chromium`, sama seperti CI. Playwright dipasang dengan
`npm install --no-save playwright@1.63.0` lalu `npx playwright install chromium`; `--with-deps` gagal
karena image sandbox tidak memakai `apt-get`, dan dependensi OS memang sudah tersedia sehingga Chromium
berjalan normal.

---

## 1. P2-A: kegagalan logout

### Reproduksi pada baseline

`tests/browser_logout_failure.cjs` dijalankan terhadap `beeloft/static/app.mjs` versi baseline (file
dipulihkan sementara dengan `git checkout HEAD --`, lalu dikembalikan). Skenario kedua modul ini
menjawab `POST /api/session/logout` dengan 503 sebelum permintaan mencapai server:

```
BASELINE_EXIT=1
locator.waitFor: Timeout 30000ms exceeded.
  - waiting for locator('#session-warning') to be visible
    63 × locator resolved to hidden <div hidden="" role="alert" id="session-warning" class="session-warning">…</div>
  at module.exports (/projects/sandbox/beeloftone/tests/browser_logout_failure.cjs:51)
```

Baseline tidak pernah memunculkan peringatan: halaman langsung menampilkan layar login walaupun session
server masih hidup. Kegagalan ini berasal dari bug, bukan dari fixture atau environment — modul yang sama
lulus penuh setelah perbaikan diterapkan, pada database demo dan browser yang sama.

### Hasil setelah perbaikan

`tests/browser_logout_failure.cjs`, 10 skenario, seluruhnya lulus di Chromium:

```
Logout failure browser QA PASS: 5xx/403/abort keep the workspace with an honest warning,
a dropped response after a real revoke still completes, expired sessions route to login,
double clicks send one revoke, and pending drafts survive the Masuk ulang flow.
```

Setiap skenario memeriksa kebenaran server, bukan hanya tampilan: status session dibaca dari dalam
halaman dengan `fetch('/api/me',{credentials:'same-origin'})`.

| # | Skenario | Cara membuatnya | Yang diverifikasi |
|---|---|---|---|
| 1 | Logout sukses | tanpa intersepsi | `/api/me` → 401, tidak ada peringatan, reload tetap logged out |
| 2 | 5xx sebelum revoke | `route.fulfill({status:503})` | banner "Logout belum berhasil", ruang kerja terlihat, layar login tidak muncul, `/api/me` → 200; reload memang membuka akun yang sama sehingga peringatan tadi terbukti benar |
| 3 | Retry setelah gagal | `unroute` lalu klik lagi | logout berhasil, `/api/me` → 401 |
| 4 | CSRF 403 | `route.fulfill({status:403})` | tidak diperlakukan sebagai logout sukses, `/api/me` → 200 |
| 5 | Dibatalkan sebelum terkirim | `route.abort('failed')` tanpa `fetch()` | kegagalan dinyatakan, session tidak pernah dicabut |
| 6 | Jaringan mati seluruhnya | `abort` pada logout **dan** `/api/me` | banner "belum terkonfirmasi", tidak ada klaim sudah keluar |
| 7 | Revoke berhasil lalu respons dijatuhkan | `await route.fetch()` lalu `route.abort('failed')` | server benar-benar memproses (`processed===1`), aplikasi mengenali `/api/me` → 401 dan menyelesaikan alur tanpa terjebak error |
| 8 | Session sudah berakhir sebelum diklik | logout dijalankan lebih dahulu dari dalam halaman | diarahkan ke login tanpa peringatan |
| 9 | Klik ganda | tiga `button.click()` berurutan di satu tick | `posts===1`, tombol `disabled` dan `aria-busy` menyala selama permintaan, layar login tidak muncul sebelum hasil diketahui, `disabled` dipulihkan |
| 10 | Draft pending dan "Masuk ulang" | respons movement dijatuhkan, session ditukar ke akun lain, logout gagal 500 | kegagalan tampil di `#form-error`, draft tetap ada dengan idempotency key yang sama, tidak ada mutasi tambahan; setelah gangguan berlalu tombol tetap bisa dipakai dan akun asli menyelesaikan pencatatan tepat satu kali |

Skenario 5 dan 7 dibedakan sungguhan, sesuai permintaan: skenario 5 membatalkan tanpa `route.fetch()`
sehingga permintaan tidak pernah terkirim, sedangkan skenario 7 memanggil `route.fetch()` agar server
benar-benar memproses pencabutan lalu hanya responsnya yang dijatuhkan.

### Bukti sisi server

`tests/test_session_logout.py`, 6 test, semuanya lulus:

```
test_successful_logout_revokes_the_session_and_clears_both_cookies ... ok
test_csrf_rejection_is_not_evidence_that_the_session_ended ... ok
test_logout_on_an_already_revoked_session_answers_401 ... ok
test_logout_on_an_expired_session_answers_401 ... ok
test_revoking_the_same_token_twice_is_safe_for_client_retries ... ok
test_one_session_logout_leaves_other_sessions_untouched ... ok
```

Test ini menegakkan tabel keputusan yang dipakai klien. Yang paling penting:
`test_csrf_rejection_is_not_evidence_that_the_session_ended` membuktikan 403 meninggalkan session yang
masih dapat membaca `/api/me` **dan** masih dapat menulis produk baru — jadi memperlakukan 403 sebagai
logout sukses memang salah.

### Jalur investigasi AI di balik dialog modal

Dialog "Tanya Beeloft" adalah `<dialog>` modal, sehingga banner `#session-warning` di belakangnya
terlihat tetapi tidak dapat dijangkau maupun ditekan. `tests/browser_ai_investigation_logout.cjs`
menguji rangkaian terburuk yang benar-benar mungkin terjadi, seluruhnya lulus di Chromium:

```
AI investigation logout browser QA PASS: an uncertain investigation survives a cross-account 403
and a failed logout, the failure is reported inside the AI dialog instead of behind the modal,
transaction.key is preserved, and the original account replays exactly once with no duplicate
investigation or audit event.
```

| Tahap | Cara membuatnya | Yang diverifikasi |
|---|---|---|
| Penyimpanan investigasi belum pasti | `await route.fetch()` lalu `route.abort('failed')` pada `POST /api/ai/investigations` | server sudah commit satu investigasi, `#ai-message` menyebut "belum terkonfirmasi", draft tersimpan pada `beeloft.pending.<operator id>`, `transaction.key` sama dengan `Idempotency-Key` yang dikirim, tepat satu event audit |
| Perlu "Masuk ulang" | session bersama ditukar ke akun admin, lalu retry diklik | `#ai-reauth` muncul, `#ai-message` cocok `/akun lain/`, tidak ada POST kedua, investigasi tetap satu |
| Logout gagal sebelum revoke | `route.fulfill({status:503})` pada logout | `#ai-message` memuat "Logout belum berhasil" dan **terlihat di dalam dialog** (`#dialog[open]` tetap 1), layar login tidak muncul, `/api/me` → 200, tombol "Masuk ulang" masih dapat dipakai, draft dan `transaction.key` tidak berubah, investigasi tetap satu |
| Logout berhasil lalu akun asli masuk lagi | `unroute` lalu klik "Masuk ulang" | `/api/me` → 401, draft tetap ada melewati logout, dialog "Konfirmasi pencatatan sebelumnya" muncul setelah login |
| Replay | klik "Coba ulang penyimpanan" | POST kedua memakai `transaction.key` yang sama, investigasi tetap **satu** dengan `id` yang sama, event audit untuk key itu tetap **satu** (tidak ada efek samping bisnis kedua), draft dibersihkan, snapshot memuat `evidence.approvals.summary` |

Dijalankan terhadap `beeloft/static/app.mjs` versi baseline `14150c6`, modul ini gagal pada tahap
logout gagal:

```
BASELINE_EXIT=1
locator.waitFor: Timeout 30000ms exceeded.
  at module.exports (tests/browser_ai_investigation_logout.cjs:91)
```

Baris 91 adalah `await page.locator('#ai-message').filter({hasText:'Logout belum berhasil'}).waitFor();`
Baseline tidak pernah memberi tahu pengguna: `logout()` menelan 503 lalu langsung menampilkan layar
login. Ini menutup keterbatasan yang sebelumnya dicatat, yaitu bahwa jalur `#ai-message` belum diuji
terpisah di browser.

---

## 2. P2-B: total approval

### Fixture dan oracle

`tests/test_approval_aggregates.py` menulis langsung ke tabel approval yang sebenarnya lewat
`store.transaction(write=True)`. Seluruh CHECK dan trigger lifecycle tetap berjalan; hanya lapisan HTTP
dan idempotency yang dilewati agar populasi di atas 1.000 baris terjangkau (1.200 baris disemai dalam
0,028 detik). Tidak ada integrity guard yang dinonaktifkan, dan validitas fixture terbukti dari
fakta bahwa jalur hidrasi lama membaca setiap baris tanpa error.

Nilai yang diharapkan berasal dari dua oracle independen, tidak ada yang memakai fungsi agregat baru:

1. **Oracle fixture** — setiap pengajuan yang disemai dicatat pada `self.expected`, dan jumlah serta
   nominalnya dihitung dengan aritmetika `Decimal` biasa di Python.
2. **Silang-uji jalur lama** — `store.approvals(1_000_000, 0, status, kind)` dihidrasi seluruhnya lalu
   dijumlahkan per baris. Implementasinya Python murni dan berbeda sama sekali dari agregasi SQL yang
   diuji.

### Reproduksi pada baseline

Populasi 610 pengajuan pending bernominal Rp1.000,00:

```
FIXTURE ORACLE (truth) : {'total': 610, 'amount': '610000.00', 'without_amount': 0}
command-center         : pending_count=500 pending_amount=500000.00
attention card         : 500 pengajuan senilai Rp500000.00 ada di inbox.
ai answer              : Ada 500 item menunggu keputusan dengan total nominal tercatat Rp500000.00.
ai facts pending       : {'label': 'Approval tertunda', 'value': 500, …}
ai evidence approvals  : type=list len=500
overview answer        : ['Ada 500 item menunggu keputusan dengan total nominal tercatat Rp500000.00']
```

Dijalankan pada baseline, modul ini melaporkan `Ran 22 tests` → `FAILED (failures=7, errors=13)`: 20 dari
22 test gagal. Sembilan gagal karena invariannya belum ada sama sekali
(`AttributeError: 'Store' object has no attribute 'approvals_summary'`), dan sebelas gagal pada angka
yang benar-benar terlihat pengguna, misalnya pada populasi campuran 500 marketing budget bernominal
ditambah 110 cuti tanpa nominal:

```
AssertionError: 'Ada 500 item menunggu keputusan dengan total nominal tercatat Rp390000.00.'
             != 'Ada 610 item menunggu keputusan dengan total nominal tercatat Rp500000.00.'

AssertionError: '500 pengajuan senilai Rp390000.00 ada di inbox.'
             != '610 pengajuan senilai Rp500000.00 ada di inbox.'
```

Kasus ini menunjukkan kedua sisi kerusakan sekaligus: 110 item hilang dari count, dan 110 item
bernominal hilang dari amount karena terdorong keluar halaman oleh item tanpa nominal.

### Hasil setelah perbaikan

Populasi dan perintah yang sama:

```
FIXTURE ORACLE (truth) : {'total': 610, 'amount': '610000.00', 'without_amount': 0}
command-center         : pending_count=610 pending_amount=610000.00 without_amount=0
attention card         : 610 pengajuan senilai Rp610000.00 ada di inbox.
ai answer              : Ada 610 item menunggu keputusan dengan total nominal tercatat Rp610000.00.
ai facts pending       : {'label': 'Approval tertunda', 'value': 610, 'unit': 'item',
                          'source': '/api/approvals/summary?status=pending'}
ai evidence            : total=610 sample_size=10 truncated=True
summary endpoint       : {'status': 'pending', 'kind': 'all', 'currency': 'IDR', 'total': 610,
                          'amount': '610000.00', 'with_amount': 610, 'without_amount': 0}
```

### Cakupan test

`tests/test_approval_aggregates.py`, 22 test dalam tiga kelas, semuanya lulus:

| Test | Yang dibuktikan |
|---|---|
| `test_boundaries_around_the_old_five_hundred_row_page` | populasi 0, 1, 499, 500, 501, dan 1.050 dilaporkan apa adanya |
| `test_single_kind_beyond_the_page_limit` | 640 pengajuan pada satu kind, nominal berbeda-beda per baris |
| `test_mixed_kinds_beyond_the_page_limit` | 810 dari campuran lima kind; `without_amount` 210 |
| `test_amounts_that_are_null_zero_or_decimal` | amount NULL (cuti, proposal produksi), nol (payroll 0), `1.00`, `0.01`, `0.33` → total `2.34` |
| `test_decided_requests_leave_the_pending_population` | 520 pending berdampingan dengan approved, rejected, cancelled; setiap status dicek |
| `test_multiple_lifecycle_events_never_double_count_one_request` | pengajuan dengan dua event tidak dihitung dua kali, dan perubahan status memindahkannya dengan benar |
| `test_list_pagination_never_changes_the_global_totals` | lima kombinasi `limit`/`offset` tidak mengubah total |
| `test_kind_filter_on_the_summary_matches_the_same_filter_on_the_list` | sepuluh nilai `kind` konsisten dengan populasi daftar |
| `test_summary_reports_every_kind_the_inbox_supports` | sembilan kind hadir pada `by_kind` |
| `test_command_center_counts_and_amount_cover_the_whole_population` | `pending_count`, `pending_amount`, `by_kind`, `pending_without_amount` |
| `test_attention_card_text_reports_the_whole_population` | teks kartu "Keputusan menunggu" |
| `test_ai_approvals_answer_and_facts_report_the_whole_population` | jawaban dan facts intent `approvals`, termasuk facts per kind |
| `test_ai_facts_cite_the_aggregate_source_not_a_limited_page` | facts merujuk `/api/approvals/summary`, findings tetap merujuk daftar |
| `test_overview_answer_uses_the_full_totals` | jawaban overview, kunci evidence tidak berubah |
| `test_evidence_separates_the_population_summary_from_the_sample` | `summary`, `sample_size`, `truncated`; detail terpotong tetapi angka penuh |
| `test_small_population_is_not_marked_as_truncated` | metadata tidak menyesatkan pada populasi kecil |
| `test_saved_investigation_keeps_the_snapshot_it_was_answered_with` | snapshot 501 tetap 501 setelah populasi tumbuh ke 510; investigasi baru memakai angka terkini |
| `test_recommendations_stay_advisory_only` | `read_only`, `approval_required`, `executable:false` |
| `test_summary_endpoint_reports_totals_with_filters` | bentuk respons, filter `kind`, sembilan kunci `by_kind` |
| `test_summary_status_filter_matches_the_list_population` | lima nilai `status` sama dengan panjang daftar |
| `test_summary_rejects_unknown_filters_and_needs_authentication` | 422 untuk `kind`/`status` tidak dikenal, 401 tanpa akses, 200 untuk admin, operator, dan viewer |
| `test_existing_list_contract_is_unchanged` | `/api/approvals` tetap list, field lengkap, `limit=1&offset=1` tetap satu baris, `limit=501` tetap 422, viewer tetap 200 |

Tidak ada assertion lama yang dilemahkan dan tidak ada test yang di-skip. Test Command Center dan AI yang
sudah ada tetap lulus tanpa diubah, termasuk
`test_management_command_center.py` yang menuntut `(pending_count, pending_amount) == (1, '1250000.50')`
serta `test_ai_investigation.py` yang menuntut `facts['Approval tertunda'] == 1` dan kunci evidence
`{'production_board','approvals','replenishment'}`.

### Biaya pembacaan

Agregasi berproyeksi minimal juga lebih murah daripada menghidrasi satu halaman. Diukur ulang
**setelah** perbaikan overflow bagian 6.1, jadi angka ini sudah mencerminkan akumulasi streaming di
Python. Populasi 1.350 pending (1.200 marketing budget dan 150 cuti), waktu terbaik dari tujuh
pengulangan:

```
populasi pending    : 1350 item, 1200000.00
approvals(500) page : 0.0236s (500 baris terhidrasi)
approvals_summary() : 0.0060s (total=1350 amount=1200000.00)
rasio               : 3.9x lebih cepat
```

Angka lama juga salah; angka baru benar dan tetap dibaca lebih cepat. Sebelum perbaikan overflow,
ringkasan yang sama terukur 0,0056 s dengan `SUM()` SQLite, jadi akumulasi di Python menambah sekitar
0,4 ms pada populasi ini — biaya yang dibayar untuk ketepatan yang dapat dibuktikan.

### Kompatibilitas evidence AI

Pemisahan `summary` dari `sample` mengubah bentuk `evidence['approvals']` dari list mentah menjadi
dict. `tests/test_ai_evidence_compatibility.py`, 7 test, semuanya lulus:

| Test | Yang dibuktikan |
|---|---|
| `test_historical_snapshot_is_returned_verbatim_and_never_recomputed` | snapshot berformat lama dikembalikan apa adanya — `answer`, `facts`, `findings`, `recommendations`, `limitations`, dan `evidence['approvals']` yang masih berupa **list** — walaupun populasi nyata sudah 520 item; baris `result_snapshot` di database tidak tersentuh |
| `test_historical_snapshot_still_lists_and_accepts_feedback` | `GET /api/ai/investigations`, filter `intent` dan `q`, serta `POST .../feedback` tetap berfungsi pada snapshot lama, dan feedback tidak menulis ulang snapshot |
| `test_new_investigation_does_not_disturb_the_historical_one` | investigasi baru berformat dict hidup berdampingan dengan yang lama pada satu database, tanpa mengubahnya |
| `test_saved_snapshot_carries_the_aggregate_behind_answer_and_facts` | ringkasan tersimpan sama dengan kebenaran fixture; `answer` dan kedua facts benar-benar dibangun darinya; facts merujuk `/api/approvals/summary`; `sum(by_kind.count) == total` dan `sum(by_kind.amount) == amount` pada snapshot yang sama |
| `test_truncated_sample_is_explained_and_never_read_as_the_total` | `truncated` menyala, `sample_size == len(sample) < summary.total`, facts memakai 530 bukan 10, findings dan recommendations sepanjang sampel, dan sumber sampel jujur menyebut daftar |
| `test_untruncated_sample_reports_the_whole_population_as_the_sample` | pada populasi kecil `truncated` mati dan `sample_size == total` |
| `test_overview_evidence_keeps_its_existing_key_shape` | kunci `evidence` overview tetap `{production_board, approvals, replenishment}`, dan kunci di dalam `approvals` serta `summary` dikunci secara eksplisit agar tidak berubah diam-diam |

Dua fakta yang membuat perubahan bentuk ini aman:

* **Tidak ada pembaca `evidence` selain brain.** `grep -n evidence beeloft/static/app.mjs` tidak
  menghasilkan satu baris pun, jadi frontend tidak pernah membaca evidence. Di backend, `evidence` hanya
  dibangun `brain._approvals()` dan disimpan; `store._ai_investigation()` mengembalikan snapshot verbatim.
* **`create_ai_action_proposal` membaca `recommendations`, bukan `evidence`.** Fingerprint rekomendasi
  yang dibandingkan diambil dari `stored_report['recommendations']`. Konten rekomendasi intent
  `approvals` tidak berubah sama sekali (sampel 10 teratas dan `source` yang sama), jadi jalur proposal
  tersambung tetap seperti sebelumnya — dibuktikan oleh
  `test_ai_investigation_memory.test_linked_action_requires_the_saved_recommendation_to_match`
  yang tetap lulus.

Dijalankan terhadap modul backend versi baseline `14150c6`, 5 dari 7 test ini gagal (semuanya yang
menguji format baru), sedangkan 2 test kompatibilitas historis lulus di kedua sisi — memang itu
perannya: menjaga agar format lama terus terbaca, bukan mereproduksi bug.

---

## 3. Regresi P1

Semua dijalankan ulang dan lulus.

| Regresi P1 | Hasil |
|---|---|
| `tests/test_static_security.py` | OK |
| `tests/test_idempotency_actor.py` | OK |
| `tests/test_rework_reinspection.py` | OK |
| `tests/browser_cross_account_retry.cjs` | `Cross-account retry browser QA PASS` |
| `tests/browser_stale_session_first_submit.cjs` | `Stale session first submit browser QA PASS` |
| `tests/browser_rework_reinspection.cjs` | PASS (dalam suite acceptance) |
| `tests/test_ai_investigation_memory.py` | OK, termasuk `test_linked_action_requires_the_saved_recommendation_to_match` |

Ketiga file test Python pertama dijalankan bersama: `Ran 33 tests in 18.593s — OK`.

Perlindungan yang secara khusus dijaga oleh perbaikan P2-A:

* `clearWorkspace()` tetap tidak menyentuh `sessionStorage`; skenario 10 pada
  `browser_logout_failure.cjs` dan seluruh rangkaian `browser_ai_investigation_logout.cjs` membuktikan
  draft bertahan melewati logout yang gagal **dan** logout yang berhasil, dengan `transaction.key` yang
  sama, serta replay yang tidak menambah event audit.
* `client.mjs` tidak diubah; `node tests/test_client.mjs` tetap menegakkan bahwa logout tidak membawa
  `X-Beeloft-Actor`.
* `starlette==1.6.0` tidak berubah pada `requirements.txt` dan terpasang di venv pengujian.

---

## 4. Kontrak, schema, dan versi

* **Schema tidak berubah.** Tidak ada file `.sql` yang disentuh (`git diff --name-only | grep -c '\.sql$'`
  → `0`), jadi `PRAGMA user_version` tetap 55 dan tidak ada versi schema yang dinaikkan tanpa alasan.
  Karena itu tidak ada uji migrasi baru; uji migrasi dan backup yang sudah ada
  (`test_browser_sessions.test_backup_and_migration_from_42`,
  `test_unified_approvals.test_immutable_backup_and_migration_from_25`,
  `test_rework_reinspection.test_rollback_backup_guards_and_migration_from_54`) tetap lulus dan masih
  memverifikasi `user_version` 55, `Store(path)` dijalankan dua kali berurutan, serta backup yang dapat
  dibaca ulang.
* **Kontrak API bertambah secara additive.** `docs/openapi.json` diregenerasi dari `app.openapi()`.
  Diff-nya tepat 77 baris tambahan dan 1 baris berubah: kenaikan `info.version` dan satu path baru
  `/api/approvals/summary`. Jumlah path 220 → 221. `/api/approvals` tidak berubah sama sekali.
* **Versi aplikasi** 0.84.0 → 0.85.0 pada `pyproject.toml`, `beeloft/api.py`, dan `README.md`, dengan
  satu bagian baru pada `docs/version-history.md`. Kenaikan ini karena kontrak API bertambah; tidak ada
  bump lain.

## 5. Build paket

Konfigurasi build ada pada `pyproject.toml`: `requires = ["setuptools>=69"]` dengan backend
`setuptools.build_meta`, `[tool.setuptools.packages.find] include = ["beeloft*"]`, dan
`[tool.setuptools.package-data] beeloft = ["*.sql", "static/*"]`. Tidak ada `MANIFEST.in`.

Build tool dipasang pada venv terpisah, jadi tidak ada dependensi aplikasi yang diubah;
`requirements.txt` dan `pyproject.toml` tetap seperti aslinya (`git status --porcelain` kosong setelah
build). `dist/` dan `build/` sudah tercakup `.gitignore`.

```
python -m venv .p2-verify/buildenv && .p2-verify/buildenv/bin/pip install build   # build==1.6.1
.p2-verify/buildenv/bin/python -m build --outdir dist .
  -> Successfully built beeloft_one-0.85.0.tar.gz and beeloft_one-0.85.0-py3-none-any.whl
```

Isi artefak diperiksa langsung, bukan diasumsikan:

| Artefak | Ukuran | `*.sql` | Aset static |
|---|---|---|---|
| `beeloft_one-0.85.0-py3-none-any.whl` | 307.523 B | 58 | `app.mjs`, `client.mjs`, `index.html`, `style.css` |
| `beeloft_one-0.85.0.tar.gz` | 419.931 B | 58 | idem, di bawah `beeloft_one-0.85.0/beeloft/static/` |

Repositori memuat 58 file `.sql` dan 4 aset static, jadi keduanya lengkap. Wheel memuat 10 modul `.py`.

### Smoke test wheel pada venv bersih di luar source checkout

Wheel dipasang ke `.p2-verify/wheelenv` (venv baru, hanya dependensi runtime dari metadata paket), dan
seluruh perintah dijalankan dari `.p2-verify/smoke`, yaitu **di luar** source checkout, sehingga
`import beeloft` pasti menyelesaikan ke `site-packages`.

```
beeloft di    : .p2-verify/wheelenv/lib64/python3.12/site-packages/beeloft
file .sql     : 58
aset static   : ['app.mjs', 'client.mjs', 'index.html', 'style.css']
APPROVAL_KINDS: 9 kind | approvals_summary: True | aggregates: 9
banner #session-warning ikut terpaket: OK
dependensi    : beeloft-one==0.85.0 fastapi==0.141.1 starlette==1.6.0 uvicorn==0.53.0 PyJWT==2.14.0 qrcode==8.2
```

CLI dijalankan terhadap **database disposable** milik smoke test, bukan database bisnis:

```
python -m beeloft --db .p2-verify/smoke/disposable.sqlite3 demo
  -> users ['admin','operator','viewer'], order 41423ba2-…
python -m beeloft --db … user --name "QA Build" --role viewer      -> akun + API key sekali tampil
python -m beeloft --db … backup .p2-verify/smoke/backup.sqlite3    -> backup dapat dibuka
     backup user_version: 55 | integrity_check: ok | foreign_key_check: clean
```

Startup server dan aset utama, lewat `python -m beeloft … serve` sebagai subprocess yang dimatikan lagi:

```
startup     : OK
200       15B application/json         /health
200    23967B text/html                /
200    23967B text/html                /static/index.html
200   570261B text/javascript          /static/app.mjs
200     3532B text/javascript          /static/client.mjs
200    58633B text/css                 /static/style.css
200   257865B application/json         /openapi.json
aset memuat perbaikan P2-A: OK          (index.html memuat #session-warning dan "Coba keluar lagi";
                                         app.mjs memuat sessionStillActive dan reauthenticate)
200 /api/approvals/summary -> total=0 amount=0.00 by_kind=9 kind
200 /api/command-center    -> pending_count=0 pending_amount=0.00 pending_without_amount=0
200 /api/approvals         -> list=True
openapi     : version=0.85.0 paths=221 summary_path=True
SMOKE TEST WHEEL: OK
```

### Smoke test sdist pada venv bersih kedua

sdist dipasang ke `.p2-verify/sdistenv` (build ulang dari sumber oleh pip) dan smoke test yang sama
dijalankan dari `.p2-verify/sdistsmoke`: import dari `site-packages`, 58 file `.sql`, empat aset static,
`Store.approvals_summary` tersedia, CLI `demo` menghasilkan tiga akun, dan `SMOKE TEST WHEEL: OK`
dengan `openapi version=0.85.0 paths=221 summary_path=True`.

## 6. Tindak lanjut komentar review pada PR #6

Dua komentar review masuk pada `44d5579` setelah CI hijau. Keduanya diperlakukan sebagai hipotesis
dan diverifikasi terhadap kode terlebih dahulu; keduanya terbukti valid dan diperbaiki.

### 6.1 Overflow integer pada `approvals_summary()` (Codex, `discussion_r4033521297`)

**Verifikasi.** `SUM()` SQLite bekerja pada integer 64-bit dengan batas `2**63-1 =
9223372036854775807`. Schema mengizinkan `mekari_payroll_snapshot_periods.gross_pay_minor` dan
`employer_contributions_minor` masing-masing sampai `100000000000000000`, jadi satu periode payroll
boleh menyumbang `2e17` satuan minor. 46 pengajuan menghasilkan `9.2e18` (masih di bawah batas) dan
47 pengajuan menghasilkan `9.4e18` (di atas batas). Nilai ini ekstrem tetapi sah menurut schema;
tidak ada klaim bahwa database produksi mana pun pernah memuatnya.

**Reproduksi sebelum perbaikan**, pada database disposable dengan
`gross_pay_minor = employer_contributions_minor = 100000000000000000`:

```
=== 46 pending payroll ===
  oracle fixture            : {'total': 46, 'amount': '92000000000000000.00'}
  store.approvals_summary   : total=46 amount=92000000000000000.00
  GET /api/approvals/summary: HTTP 200
  GET /api/command-center   : HTTP 200
  brain approvals           : Ada 46 item menunggu keputusan dengan total nominal tercatat Rp92000000000000000.00.

=== 47 pending payroll ===
  oracle fixture            : {'total': 47, 'amount': '94000000000000000.00'}
  store.approvals_summary   : OperationalError: integer overflow
  GET /api/approvals/summary: OperationalError: integer overflow
  GET /api/command-center   : OperationalError: integer overflow
  brain approvals           : OperationalError: integer overflow
```

`sqlite3.OperationalError` yang pesannya bukan `locked`/`busy` diteruskan kembali oleh handler di
`beeloft/api.py:102-107`, jadi ketiga endpoint tersebut menjadi 500.

**Perbaikan.** Tidak ada cabang nominal yang lagi menyerahkan penjumlahan kepada SQLite. Nilainya
diproyeksikan satu kolom per baris lalu diakumulasi secara streaming: integer Python untuk kolom
`*_minor`, dan `Decimal` untuk `ai_action` yang menyimpan string `'.2f'` di dalam JSON. Satuan tiap
kind kini dideklarasikan pada `APPROVAL_AGGREGATES` (`'minor'`, `'rupiah'`, atau `None`), sehingga
tidak ada pengecualian ad hoc per nama kind. Pemformatan akhir memakai `approval_amount()` yang
menaikkan presisi context sesuai besar angkanya, jadi hasilnya eksak untuk berapa pun jumlah baris
dan presisi default `Decimal` tidak ikut membatasi. Tidak ada FLOAT, REAL, `TOTAL()`, `CAST()`,
maupun pembulatan nominal, dan batas nominal bisnis pada schema tidak diturunkan. Proyeksinya tetap
minimal: tidak ada history, context, atau detail pengajuan. `count`, `amount`, `with_amount`,
`without_amount`, dan `by_kind` tetap berasal dari satu transaksi baca.

**Hasil setelah perbaikan**, populasi dan perintah yang sama:

```
=== 47 pending payroll ===
  store.approvals_summary   : total=47 amount=94000000000000000.00
  GET /api/approvals/summary: HTTP 200
  GET /api/command-center   : HTTP 200
  brain approvals           : Ada 47 item menunggu keputusan dengan total nominal tercatat Rp94000000000000000.00.
```

`tests/test_approval_aggregates.py::ApprovalSummaryOverflowTest`, 7 test, semuanya lulus:

| Test | Yang dibuktikan |
|---|---|
| `test_forty_six_payroll_approvals_stay_below_the_sqlite_limit` | batas bawah `46 × 2e17 < 2**63-1` tetap benar |
| `test_forty_seven_payroll_approvals_cross_the_limit_and_stay_exact` | `47` menghasilkan `94000000000000000.00`, `by_kind`, `with_amount`, dan silang-uji terhadap jalur hidrasi lama |
| `test_amount_stays_exact_far_beyond_the_sqlite_limit` | 150 pengajuan (`3 ×` batas) menghasilkan `300000000000000000.00` tanpa pembulatan |
| `test_extreme_amounts_mix_with_cents_zero_and_missing_amounts` | nominal ekstrem bercampur `0.01`, `0.99`, nol, JSON `0.33`, dan item tanpa nominal → `94000000000000001.33` |
| `test_status_and_kind_filters_stay_exact_at_extreme_amounts` | filter `status` dan `kind` tetap eksak, termasuk `status=all` pada 52 pengajuan |
| `test_no_amount_branch_delegates_summation_to_sqlite` | statement yang **benar-benar dieksekusi** (via `set_trace_callback`) tidak memuat `SUM(`, `TOTAL(`, `AVG(`, `CAST(`, atau `REAL`; satuan sembilan kind dikunci eksplisit |
| `test_consumers_report_extreme_totals_without_failing` | `/api/approvals/summary`, Command Center beserta kartu perhatiannya, jawaban AI approvals, dan overview semuanya 200 dan eksak |

Nilai yang diharapkan berasal dari oracle integer murni (`divmod(count * 2 * 10**17, 100)`), bukan
dari fungsi agregat yang diuji. Dijalankan terhadap `beeloft/store.py` versi `44d5579`, 6 dari 7 test
ini gagal: 5 dengan `sqlite3.OperationalError: integer overflow` dan 1 karena pelacakan SQL mendeteksi
`SUM(`. Regresi populasi di atas 500 dan seluruh 22 test P2-B sebelumnya tetap lulus.

### 6.2 Identitas `/api/me` dibuang pada logout gagal (CodeRabbit, `discussion_r4033581136`)

**Verifikasi.** `sessionStillActive()` mereduksi respons `/api/me` menjadi `true` tanpa melihat
identitasnya. Cookie session dipakai bersama seluruh tab, jadi ketika tab lain menukar session ke
akun B dan logout gagal sebelum pencabutan, `logout()` mempertahankan `user`, `api.actorId`, dan
seluruh ruang kerja akun A sementara setiap pembacaan berikutnya memakai session akun B. Pencatatan
memang tetap ditolak binding aktor server (P1), tetapi UI-nya bercampur identitas dan masih dapat
dipakai.

**Reproduksi sebelum perbaikan.** Skenario 11 pada `tests/browser_logout_failure.cjs` dijalankan
terhadap `beeloft/static/app.mjs` versi `44d5579`: ruang kerja akun lama tidak pernah ditutup.

```
BASELINE_EXIT=1
locator.waitFor: Timeout 30000ms exceeded.
  - waiting for getByLabel('Kunci akses', { exact: true }) to be visible
    63 × locator resolved to hidden <input required="" id="access-key" type="password" …/>
  at tests/browser_logout_failure.cjs:259
```

**Perbaikan.** `sessionStillActive()` diganti `sessionIdentity()` yang mempertahankan identitasnya dan
mengembalikan `{state:'active', user}`, `{state:'inactive'}`, atau `{state:'unknown'}`. `logout()`
membedakan empat keadaan:

| Keadaan | Keputusan UI |
|---|---|
| `inactive` (401) | logout terkonfirmasi, ruang kerja ditutup |
| `unknown` (5xx, timeout, jaringan mati) | belum terkonfirmasi, ruang kerja dipertahankan dengan peringatan |
| `active` dan `user.id` **sama** | logout gagal, ruang kerja dipertahankan dengan peringatan |
| `active` dan `user.id` **berbeda** | ruang kerja lama dibongkar, peringatan menjelaskan perpindahan akun |

Pada keadaan terakhir `clearWorkspace()` membuang seluruh state tampilan, menaikkan `epoch` sehingga
respons asynchronous lama tidak dapat menimpa konteks baru, dan mengosongkan `api.actorId` tanpa
pernah menggantinya ke akun B. `sessionStorage` sengaja tidak disentuh, jadi draft pending akun A
beserta `transaction.key`-nya tetap dapat dipulihkan. Banner yang tampil menyebut akun yang sekarang
memegang session, menyatakan session itu **masih aktif**, dan tidak pernah mengaku logout berhasil.
Tombol "Coba keluar lagi" tidak ditawarkan pada keadaan ini karena mencabut session akun lain bukan
langkah berikutnya yang benar; `sessionWarning(text, retry)` yang menyembunyikannya. `reauthenticate()`
kini memeriksa keberadaan elemen pesan sebelum menulisinya, sebab dialog akun lama sudah ikut ditutup.
`enterWorkspace()` membersihkan banner supaya peringatan lama tidak tertinggal setelah login berhasil.

**Cakupan browser.** `tests/browser_logout_failure.cjs` menjadi 11 skenario dan
`tests/browser_ai_investigation_logout.cjs` menjadi tiga fase; keduanya terdaftar pada
`tests/browser_smoke.cjs` dan benar-benar dijalankan runner.

| Skenario | Permukaan | Yang diverifikasi |
|---|---|---|
| Logout gagal, akun **sama** | form transaksi (skenario 10) | `#form-error` memuat "Logout belum berhasil", dialog tetap terbuka, layar login tidak muncul, `/api/me` 200 dan `id` sama dengan pembuka ruang kerja, banner menyebut "akun yang sama", draft dan `transaction.key` utuh, tidak ada mutasi tambahan |
| Logout gagal, akun **sama** | dialog AI (fase 1) | idem, dengan pesan di `#ai-message` dan `#dialog[open]` tetap 1 |
| Logout gagal, akun **berbeda** | form transaksi (skenario 11) | `#workspace` tersembunyi, `#dialog[open]` 0, `#logout` tersembunyi, `#account-name` kosong, `#order-list` kosong, banner memuat "berpindah ke akun lain", nama akun B, dan "masih aktif" tanpa klaim keluar, `#session-retry` tersembunyi, `/api/me` 200 dengan `id` akun B |
| Logout gagal, akun **berbeda** | dialog AI (fase 2) | idem, ditambah draft akun asli beserta `transaction.key` tetap utuh setelah ruang kerja dibongkar |
| Session sudah revoked / respons revoke hilang / offline | form transaksi (skenario 7, 8, 6) | tetap seperti sebelumnya: 401 menyelesaikan alur, `route.fetch()` lalu `abort` dikenali lewat `/api/me` 401, jaringan mati menghasilkan "belum terkonfirmasi" |
| Pemulihan draft dan replay | keduanya | akun asli masuk kembali, dialog "Konfirmasi pencatatan sebelumnya" muncul, replay memakai `transaction.key` yang sama, hasilnya tepat satu movement / satu investigasi dengan tepat satu event audit, draft dibersihkan |

Assertion existing yang mengharapkan ruang kerja tetap dipertahankan setelah pergantian akun sudah
disesuaikan dengan kontrak identitas yang benar. Tidak ada pemeriksaan draft, status server, maupun
jumlah audit yang dihapus; keduanya justru ditambah.

**Bukti sisi server.** `tests/test_session_logout.py::SessionIdentityAfterSwitchTest`, 2 test, lulus:
`/api/me` benar-benar menjawab identitas pengganti (`id`, `name`, `role` lengkap) setelah session
ditukar, login baru tidak mencabut session sebelumnya, logout yang gagal karena CSRF tidak mencabut
session siapa pun, dan pencatatan di bawah session yang sudah berganti tetap ditolak 403 tanpa mutasi
maupun receipt idempotency — binding aktor P1 tidak melemah.

## 7. Batas dan bagian yang belum terverifikasi

* **Windows belum diuji.** `start.ps1` dan perilaku pada Windows tidak dijalankan; sandbox ini Linux.
  Perubahan P2 tidak menyentuh path filesystem maupun `StaticFiles`, jadi risikonya rendah, tetapi
  pernyataannya tetap: belum diuji.
* **Build paket tidak dijalankan CI.** `.github/workflows/ci.yml` tidak memuat langkah `python -m build`.
  Build dan smoke test di bagian 5 dijalankan manual di sandbox ini; artinya regresi packaging tidak
  akan tertangkap otomatis oleh CI.
* **`--with-deps` Playwright gagal** karena image sandbox tidak memakai `apt-get`. Chromium dipasang
  tanpa dependensi OS tambahan dan seluruh 65 modul berjalan, jadi ini keterbatasan environment, bukan
  kegagalan aplikasi.
* **Seluruh nominal ringkasan approval dijumlahkan di Python.** Setelah perbaikan overflow, tidak ada
  cabang yang memakai `SUM()` SQLite. Biaya pembacaannya karena itu tumbuh linear terhadap jumlah
  pengajuan yang cocok filter, bukan konstan. Proyeksinya tetap satu kolom kecil per baris tanpa
  hidrasi, dan pada 1.350 pengajuan pending terukur 0,0060 s — sekitar 0,4 ms lebih lambat daripada
  `SUM()` SQLite, tetapi eksak. Populasi yang jauh lebih besar belum diukur.
* **Agregat lain di luar ringkasan approval tidak disentuh.** `beeloft/store.py` masih memakai
  `SUM(... amount_minor ...)` pada dua baris guard komitmen supplier payment (kolomnya dibatasi 1e14,
  jadi ambangnya jauh lebih tinggi). Itu di luar scope P2 dan di luar komentar review.
* **P3 tetap terbuka**: breakdown `by_kind` masih enam kunci, tanggal ekstrem masih dapat menghasilkan
  500, dan logout dengan API key tanpa cookie masih menghasilkan 500 pada server. Yang berubah untuk
  temuan terakhir hanyalah bahwa 500 dari endpoint logout kini dilaporkan apa adanya kepada pengguna,
  bukan disamarkan sebagai layar login.

## 8. Status

| Temuan | Status | Alasan |
|---|---|---|
| P2-A — logout gagal tetap menampilkan layar login | **FIXED** | Ruang kerja hanya ditutup bila pencabutan terkonfirmasi, dan hanya dipertahankan bila identitas session masih akun yang sama. Empat keadaan dibedakan: terkonfirmasi, gagal akun sama, berpindah akun, dan belum diketahui. Diverifikasi di Chromium terhadap identitas dan status session server yang sebenarnya untuk 11 skenario pada jalur biasa dan tiga fase pada jalur dialog AI modal; kedua modul gagal pada baseline maupun pada `44d5579`. |
| P2-B — total approval salah di atas 500 item | **FIXED** | Ringkasan dibaca sebagai agregat database berproyeksi minimal, terpisah dari daftar, mencakup sembilan kind, dengan uang eksak dan satu snapshot pembacaan. Command Center, kartu perhatian, jawaban AI, overview, dan evidence memakai sumber yang sama. Diverifikasi pada 0, 1, 499, 500, 501, 640, 810, 1.050, dan 1.350 item terhadap dua oracle independen, dan kompatibilitas snapshot lama ditegakkan terpisah. |
| Review Codex — overflow integer pada agregat | **FIXED** | Tidak ada cabang nominal yang menyerahkan penjumlahan kepada SQLite; akumulasi streaming dengan integer Python dan `Decimal`, terbukti eksak pada 46, 47, dan 150 pengajuan payroll bernominal maksimum schema. |
| Review CodeRabbit — identitas dibuang pada logout gagal | **FIXED** | `sessionIdentity()` mempertahankan identitas `/api/me`; ruang kerja lama hanya dipertahankan bila `id`-nya cocok, dan dibongkar dengan penjelasan bila session sudah berpindah akun. Draft akun asli beserta `transaction.key` tetap utuh dan replay tetap satu kali. |
