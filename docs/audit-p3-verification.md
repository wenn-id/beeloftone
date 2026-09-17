# Bukti pengujian: rincian kategori approval, batas aritmetika tanggal, dan logout tanpa cookie

Bukti untuk [rencana perbaikan P3](audit-p3-plan.md).

## Baseline

```
$ git fetch origin --prune
$ git rev-parse origin/main
c77248bedd788744bd6ee6776d40bf4bc33dce79
$ git rev-parse main
c77248bedd788744bd6ee6776d40bf4bc33dce79
$ git rev-list --left-right --count main...origin/main
0	0
$ git status --short          # kosong
```

Baseline yang benar-benar dipakai: **`c77248bedd788744bd6ee6776d40bf4bc33dce79`** ("Fix P2 audit:
reliable logout and complete approval aggregates (#6)"). `main` lokal identik dengan `origin/main`
setelah `fetch`, jadi tidak ada perubahan baru yang perlu diikutkan dan SHA-nya sama dengan yang
disebutkan pada penugasan.

Branch kerja `fix/audit-p3-approval-breakdown-date-logout` dibuat dari SHA tersebut. Branch PR #6
tidak dilanjutkan. Tidak ada `reset`, `force-checkout`, atau pembuangan perubahan lokal.

`origin/main` diperiksa ulang sebelum publikasi dan masih berada pada `c77248be`, jadi baseline
tidak bergerak dan tidak ada rebase maupun pemeriksaan kompatibilitas tambahan yang diperlukan.

**SHA yang benar-benar diuji: `4ef1eac9dda8e825f6801c0b946537ec32613e4c`.** Seluruh hasil pada
dokumen ini dijalankan ulang pada commit tersebut. Commit dokumen tidak menyentuh kode maupun tes;
CI pada HEAD yang dipublikasikan menjalankan ulang semuanya.

Commit pada branch:

| SHA | Subject |
| --- | --- |
| `445b7b3` | Complete the approval category breakdown |
| `d20b24f` | Validate date arithmetic boundaries |
| `d681c1f` | Handle session logout without a browser cookie |
| `64954e8` | Record the P3 audit fixes and regenerate the API contract |
| `dcb4f73` | Pin the stockout projection and logout credential contracts |
| `4ef1eac` | Actually exercise shift_date in the unrelated-error test |

Perbandingan sebelum/sesudah memakai checkout terpisah, bukan penggantian working tree:

```
$ git worktree add /projects/sandbox/baseline c77248bedd788744bd6ee6776d40bf4bc33dce79 --detach
$ git worktree list
/projects/sandbox/beeloftone  c77248b [fix/audit-p3-approval-breakdown-date-logout]
/projects/sandbox/baseline    c77248b (detached HEAD)
```

Berkas tes baru dijalankan terhadap kode baseline lewat salinan disposable
(`/projects/sandbox/baseline-run`, hasil `tar` dari worktree tanpa `.git`) dengan
`PYTHONPATH=/projects/sandbox/baseline-run`, sehingga working tree branch tidak pernah disentuh.

## Lingkungan

| Komponen | Nilai |
| --- | --- |
| OS | Linux x86_64 (bukan Ubuntu; tidak ada `apt-get`) |
| Python | 3.12.13 (venv `/projects/sandbox/venv312`), sama dengan `PYTHON_VERSION` CI |
| Node.js | v22.23.2, sama dengan `NODE_VERSION` CI |
| Playwright | 1.63.0, `chromium-headless-shell` 153.0.8010.12 (`--channel chromium`) |
| Database uji | `tempfile.TemporaryDirectory()` per test; demo browser memakai database disposable milik `tests/run_browser.py` |

Tidak ada demo, migrasi percobaan, fixture, penghapusan database, atau pembuatan ulang akun
operasional pada database bisnis.

Baseline suite sebelum perubahan apa pun, untuk memastikan titik awalnya hijau:

```
$ python -m unittest discover -s tests
Ran 433 tests in 277.927s
OK
```

## Ringkasan hasil

Status keseluruhan: **Implemented and locally verified; pending PR review and CI.**

| Temuan | Status | Bukti utama |
| --- | --- | --- |
| P3-A | **FIXED** | `by_kind` memuat kesembilan kategori; `sum(by_kind.values()) == pending_count`; 11/14 test baru gagal pada baseline |
| P3-B | **FIXED** | 15 jalur yang tadinya 500 kini 422 berpesan; batas aman tetap 200; 14/28 test baru dan modul browser baru gagal pada baseline |
| P3-C | **FIXED** | Logout API key tanpa cookie 200 no-op; pencabutan lintas akun tanpa CSRF dihentikan; 10/18 test baru gagal pada baseline |
| Kontrak A (semantik `None` proyeksi) | **TERBUKTI, tanpa perubahan kode** | Demand, cover, dan risiko identik pada dua tanggal acuan; hanya proyeksinya berbeda; 7/8 test gagal pada baseline ([bagian 8](#8-kontrak-a-semantik-none-pada-proyeksi-habis-stok)) |
| Kontrak B (kredensial dan cookie logout) | **TERBUKTI, tanpa perubahan kode** | `Set-Cookie` kosong pada jalur no-op; `rows()` tabel session tidak berubah; session tetap dipakai lewat cookie; 5/6 test gagal pada baseline ([bagian 9](#9-kontrak-b-api-key-logout-sebagai-no-op)) |

| Perintah | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | **Ran 507 tests — OK** (baseline 433, +74) |
| `python -m pip check` | No broken requirements found |
| `python -m compileall -q beeloft` | OK |
| `node --check beeloft/static/app.mjs` | OK |
| `node --check beeloft/static/client.mjs` | OK |
| `node tests/test_client.mjs` | 3 baris PASS, termasuk pemeriksaan batas tanggal baru |
| `python tests/run_browser.py --channel chromium` | exit 0, 67 baris PASS termasuk modul baru |
| `python -m build` | `beeloft_one-0.86.0-py3-none-any.whl` dan `.tar.gz` |
| Smoke wheel + sdist di venv bersih, dari luar checkout | LULUS |

## 1. P3-A: rincian kategori approval

### Reproduksi pada baseline

Skrip reproduksi memakai fixture 3 marketing + 5 cuti + 4 lembur + 2 payroll pada database
disposable, lalu memanggil `build_command_center()` langsung:

```
store approvals_summary by_kind keys (9): [ai_action, marketing_budget, payroll_batch,
    production_change, purchase_order, purchase_request, supplier_payment, workforce_leave,
    workforce_overtime]
command center by_kind keys  (6): [ai_action, marketing_budget, production_change,
    purchase_order, purchase_request, supplier_payment]
MISSING from command center     : [payroll_batch, workforce_leave, workforce_overtime]
pending_count                  : 14
sum(by_kind.values())          : 3
INVARIANT sum == pending_count : False
hidden population (leave+overtime+payroll) : 11
```

### Hasil setelah perbaikan

Fixture yang sama:

```
command center by_kind keys  (9): [ai_action, marketing_budget, payroll_batch, production_change,
    purchase_order, purchase_request, supplier_payment, workforce_leave, workforce_overtime]
MISSING from command center     : []
pending_count                  : 14
sum(by_kind.values())          : 14
INVARIANT sum == pending_count : True
hidden population (leave+overtime+payroll) : 0
```

### Fixture sembilan kind

`NineKindFixture` mengisi kesembilan kategori dengan pengajuan yang sah. Enam kategori memakai seed
SQL yang sudah ada (`ApprovalFixture`), yang tetap menjalankan seluruh CHECK dan trigger lifecycle.
Tiga kategori — `purchase_order`, `supplier_payment`, `production_change` — tidak punya seed SQL
karena rantai FK dan trigger-nya panjang, jadi dibuat lewat endpoint aslinya:

* `purchase_order` pending: PR disetujui lewat `/api/purchase-requests/{id}/decisions`, lalu
  `POST /api/purchase-orders` tanpa keputusan.
* `supplier_payment` pending: PO kedua disetujui, bahannya diterima lewat
  `/api/purchase-orders/{id}/receipts`, lalu `POST /api/purchase-orders/{id}/payment-requests`.
* `production_change` pending: `POST /api/orders/{id}/change-requests`.

Dengan begitu yang dihitung memang pengajuan sah menurut aturan aplikasi, bukan baris yang ditanam
paksa. Nilai harapan selalu berasal dari oracle fixture (`self.record`/`self.oracle`), bukan dari
fungsi agregat yang diuji.

### Cakupan test

`tests/test_approval_aggregates.py::CommandCenterApprovalBreakdownTest` — **14 test, OK**:

| Test | Yang ditegakkan |
| --- | --- |
| `test_breakdown_reports_every_kind_the_aggregate_knows` | Kesembilan kind punya pengajuan sah; `set(by_kind) == set(APPROVAL_KINDS)`; total dan nominal cocok dengan oracle |
| `test_breakdown_sums_to_the_pending_count_for_the_same_scope` | `sum(by_kind.values()) == pending_count` pada populasi campuran |
| `test_categories_without_pending_requests_stay_present_as_zero` | Kategori kosong tetap ada bernilai 0 |
| `test_empty_dataset_reports_every_category_as_zero` | Dataset kosong: sembilan kunci bernilai 0, total 0, nominal `'0.00'` |
| `test_leave_only_overtime_only_and_payroll_only_datasets_are_visible` | Tiga dataset yang seluruhnya tidak terlihat pada baseline |
| `test_leave_and_overtime_without_amounts_are_counted_but_add_no_nominal` | Cuti/lembur dihitung dalam jumlah, tidak menambah nominal |
| `test_terminal_decisions_leave_the_breakdown_with_the_pending_scope` | Campuran pending dan keputusan terminal (approved/rejected/cancelled) |
| `test_breakdown_stays_exact_beyond_the_old_five_hundred_row_page` | 640 pending (> 500) dilaporkan apa adanya |
| `test_the_six_original_categories_keep_their_values_and_types` | Enam nilai lama tidak bergeser; setiap nilai `int` dan bukan `bool` |
| `test_breakdown_counts_match_the_aggregate_and_the_list_per_category` | Rinciannya sama dengan agregat *dan* dengan daftar per kategori — bukan definisi pending kedua |
| `test_amount_semantics_per_kind_are_untouched_by_the_breakdown` | Nominal per kind tetap milik agregat dan tidak berubah |
| `test_extreme_amounts_do_not_disturb_the_added_categories` | 47 payroll × 2 × 10¹⁷ satuan minor (melewati 2⁶³−1) tetap eksak; oracle integer murni |
| `test_approvals_list_endpoint_is_still_a_list` | `GET /api/approvals` tetap list dengan sembilan kind |
| `test_ai_facts_report_the_added_categories_too` | Facts AI memuat cuti, lembur, dan payroll |

Berkas keseluruhan tetap hijau: `test_approval_aggregates` **43 test, OK** (29 test P2 lama + 14
baru).

### Tes baru gagal pada baseline

```
$ cd /projects/sandbox/baseline-run/tests
$ PYTHONPATH=/projects/sandbox/baseline-run python -m unittest \
    test_approval_aggregates.CommandCenterApprovalBreakdownTest
Ran 14 tests
FAILED (failures=9, errors=4)      # angka ini termasuk subTest; per test: 11 gagal, 3 lulus
```

**11 dari 14 gagal pada kode baseline** dan lulus pada branch. Tiga yang lulus di kedua sisi adalah
tes yang memang menjaga perilaku existing agar tidak berubah:
`test_approvals_list_endpoint_is_still_a_list`,
`test_amount_semantics_per_kind_are_untouched_by_the_breakdown`, dan
`test_ai_facts_report_the_added_categories_too` (facts AI sudah lengkap sejak P2). Contoh kegagalan:

```
AssertionError: {'marketing_budget': 4} != {'workforce_leave': 5, 'workforce_overtime': 3,
                                            'payroll_batch': 2, 'marketing_budget': 4}
```

### Konsumen rincian

`grep -rn "by_kind" beeloft/static/` kosong: UI tidak pernah membaca rincian ini, dan Command Center
hanya menampilkan `pending_count` (`app.mjs:405`) yang sejak P2 sudah mencakup seluruh populasi.
Tidak ada drill-down kategori → inbox pada baseline (`approvalsDialog()` tidak menerima argumen).
Karena itu **tidak ada modul browser untuk P3-A dan tidak ada perubahan UI**: menambahkan panel
kategori berarti menambah permukaan UI yang tidak diminta. Label Bahasa Indonesia untuk kesembilan
kategori sudah lengkap di `approvalKind` (`app.mjs:4014`) bila kelak dipakai.

Facts AI (`brain.py:113`) sudah melakukan iterasi seluruh kunci agregat, jadi pemetaan kategorinya
memang tidak pernah tidak lengkap; kini ada tes penjaga untuk itu.

## 2. P3-B: batas aritmetika tanggal

### Reproduksi pada baseline

```
500 /api/production-quality-insights {'as_of': '0001-01-01'}
500 /api/production-quality-insights {'as_of': '0001-01-01', 'window_days': 7}
500 /api/demand-forecast             {'as_of': '0001-01-01'}
500 /api/return-insights             {'as_of': '0001-01-01'}
500 /api/dead-stock-insights         {'as_of': '0001-01-01'}
500 /api/stock-adjustment-insights   {'as_of': '0001-01-01'}
500 /api/supplier-performance-insights {'as_of': '0001-01-01'}
500 /api/material-price-insights     {'as_of': '0001-01-01'}
500 /api/size-demand-insights        {'as_of': '0001-01-01'}
500 /api/replenishment-recommendations {'as_of': '0001-01-01'}
500 /api/purchase-commitment-insights {'as_of': '9999-12-31'}
500 /api/capacity-plan               {'as_of': '9999-12-31'}
200 /api/capacity-plan               {'as_of': '9999-12-31', 'horizon_days': 1}
500 /api/replenishment-recommendations {'as_of': '9999-12-31'}
200 /api/wip-ageing-insights         {'as_of': '0001-01-01'}
500 POST /api/ai/investigate    {'as_of': '0001-01-01'}
500 POST /api/ai/investigations  {'as_of': '0001-01-01'}

Exception asli dari store (dipanggil langsung):
  OverflowError: date value out of range
```

Dua baris `200` di atas adalah hasil reproduksi, bukan dugaan, dan keduanya perlu ditindaklanjuti
secara berbeda:

* `wip-ageing-insights` memang tidak melakukan aritmetika tanggal atas `as_of`. Tidak ada perbaikan.
* `capacity-plan` dengan `horizon_days=1` hanya lulus karena database reproduksi belum punya work
  center, sehingga loop hari tidak pernah berjalan. Dengan satu work center, jalur yang sama pada
  baseline meledak — dibuktikan di bawah.

### Loop hari `capacity_plan` dibuktikan terpisah

Skrip yang sama dijalankan pada dua checkout, dengan satu work center dibuat lebih dulu:

```
################ BASELINE c77248be ################
store: /projects/sandbox/baseline/beeloft/store.py
work center created: 201
  horizon berakhir tepat di 9999-12-31 -> 500  {'as_of': '9999-12-31', 'horizon_days': 1}
  horizon berakhir 9999-12-30          -> 200  {'as_of': '9999-12-30', 'horizon_days': 1}
  horizon melewati kalender            -> 500  {'as_of': '9999-12-31', 'horizon_days': 2}
  tanggal normal                       -> 200  {'as_of': '2026-09-23', 'horizon_days': 3}
  langsung ke store: OverflowError: date value out of range

################ BRANCH (fixed) ################
store: /projects/sandbox/beeloftone/beeloft/store.py
work center created: 201
  horizon berakhir tepat di 9999-12-31 -> 200  {'as_of': '9999-12-31', 'horizon_days': 1}
  horizon berakhir 9999-12-30          -> 200  {'as_of': '9999-12-30', 'horizon_days': 1}
  horizon melewati kalender            -> 422  {'as_of': '9999-12-31', 'horizon_days': 2}
  tanggal normal                       -> 200  {'as_of': '2026-09-23', 'horizon_days': 3}
  langsung ke store: OK, hari pertama: 9999-12-31
```

Ini sekaligus pasangan "batas aman" / "satu hari di luar batas aman" untuk horizon.

### Hasil setelah perbaikan

Seluruh jalur yang tadinya 500 menjadi 422 dengan pesan Bahasa Indonesia:

```
422 /api/production-quality-insights {'as_of': '0001-01-01'}
...
422 POST /api/ai/investigations {'as_of': '0001-01-01'}

DomainError: Kombinasi as_of dan window_days menunjuk tanggal di luar kalender yang terwakili
(0001-01-01 sampai 9999-12-31). Sesuaikan parameter tersebut lalu muat ulang laporannya.
```

Pesan menyebut parameter yang bersangkutan per endpoint, misalnya `as_of dan inactivity_days`,
`as_of dan due_soon_days`, `as_of dan horizon_days`, serta
`as_of dengan lead_time_days, review_period_days, dan safety_stock_days`.

### Cakupan test

`tests/test_date_boundaries.py` — **36 test, OK** (28 di bawah ini, ditambah 8 test kontrak proyeksi
pada [bagian 8](#8-kontrak-a-semantik-none-pada-proyeksi-habis-stok)):

| Test | Yang ditegakkan |
| --- | --- |
| `test_extreme_dates_are_refused_with_422_not_500` | 0001-01-01 dan 9999-12-31 pada 19 kombinasi endpoint/parameter; span nol tetap 200 |
| `test_extreme_dates_are_accepted_when_the_period_still_fits` | Tanggal ekstremnya sendiri sah bila periodenya masih terwakili |
| `test_safe_boundary_is_accepted_and_one_day_further_is_refused` | Batas aman tepat → 200; satu hari di luarnya → 422, untuk seluruh tabel endpoint |
| `test_literal_boundaries_for_the_reported_endpoint` | Batas ditulis literal tanpa aritmetika di dalam tes: `0001-01-14` (200, `previous_period_start == '0001-01-01'`) vs `0001-01-13` (422) |
| `test_capacity_plan_enumerates_the_last_representable_day` | Loop hari mengembalikan `['9999-12-31']`, dan `['9999-12-29','9999-12-30','9999-12-31']` untuk horizon tiga hari |
| `test_error_message_names_the_parameters_involved` | Pesan menyebut parameternya dan tidak menyebut parameter yang tidak terkait |
| `test_minimum_and_maximum_allowed_windows_work_on_a_normal_date` | Window/horizon minimum dan maksimum yang diizinkan endpoint |
| `test_windows_outside_the_allowed_range_are_still_refused` | Batas `ge`/`le` existing tidak dilonggarkan |
| `test_dates_that_do_not_exist_on_the_calendar_are_refused` | `2026-02-30`, `2025-02-29`, `2026-13-01`, `2026-00-10`, `2026-09-31`, `10000-01-01`, `0000-12-31`, `kemarin`, `2026-9-23` |
| `test_leap_day_and_month_and_year_rollovers_are_computed_correctly` | 2024 kabisat vs 2025, pergantian bulan dan tahun, dengan tanggal harapan ditulis tangan |
| `test_single_day_ranges_are_accepted_across_the_date_range_endpoints` | Rentang satu hari pada audit, aktivitas, kehadiran, kalender work center |
| `test_start_date_after_end_date_is_refused_on_every_range_endpoint` | `start_date > end_date` → 422 pada lima endpoint termasuk ekspor CSV |
| `test_timezone_conversion_at_the_calendar_edge_answers_422_not_500` | Konversi tengah malam Jakarta → UTC di tepi kalender |
| `test_operational_jakarta_default_is_unchanged` | Tanpa `as_of`, laporan memakai `jakarta_today()` |
| `test_normal_dates_return_the_same_periods_as_before_the_fix` | Periode untuk tanggal normal identik dengan baseline |
| `test_reports_are_read_only_even_when_the_date_is_refused` | `iterdump()` sebelum/sesudah identik untuk tiga permintaan yang ditolak |
| `InvestigationDateBoundaryTest` (6 test) | Jalur internal AI; penolakan tidak meninggalkan investigasi, receipt, atau audit |
| `StockProjectionBoundaryTest` (3 test) | Proyeksi dari data menjawab 200 dengan `None`, bukan 422 |
| `ShiftDateHelperTest` (3 test) | Unit helper; hanya `OverflowError` ditangani |

Nilai harapan independen: batas aman dihitung dari `date.min`/`date.max` dengan `timedelta` biasa di
dalam tes, bukan dengan `shift_date` yang sedang diuji; sebagian ditulis sebagai tanggal literal.

### Zona waktu di tepi kalender

`audit_events` dan `activity` menggabungkan tanggal lokal pada tengah malam Jakarta lalu mengubahnya
ke UTC. Tengah malam 0001-01-01 di Jakarta jatuh sebelum awal kalender dalam UTC, jadi jalur ini
memang terdampak konversi zona waktu:

```
/api/audit-events?start_date=0001-01-01&end_date=0001-01-01 -> 422
/api/activity?day=0001-01-01                                -> 422
/api/audit-events?start_date=9999-12-31&end_date=9999-12-31 -> 422
    {"detail":"Tanggal audit di luar jangkauan."}
/api/audit-events?start_date=9999-12-29&end_date=9999-12-30 -> 200
/api/activity?day=9999-12-31                                -> 200
```

Semuanya adalah perilaku baseline yang **sudah** benar: kedua fungsi punya
`except (OverflowError, ValueError)` sejak sebelumnya dan menjawab 422, bukan 500. Tidak ada
perubahan kode di jalur ini; tesnya ditambahkan sebagai penjaga. `attendance_records` tidak
melakukan konversi zona waktu dan melayani kedua ujung kalender.

### Tidak ada efek samping pada permintaan yang ditolak

`InvestigationDateBoundaryTest` memeriksa langsung ke database disposable:

* `POST /api/ai/investigations` dengan `as_of=0001-01-01` dan `Idempotency-Key: p3b-refused` → 422;
  jumlah baris `ai_investigations`, `requests`, dan `audit_events` tidak berubah.
* Kunci idempotency yang sama masih dapat dipakai sesudahnya untuk permintaan yang sah, dan replay
  dengan kunci itu mengembalikan hasil yang sama persis (tidak ada duplikat).
* `POST /api/ai/action-proposals` dengan kombinasi yang sama juga 422 tanpa menyisakan baris.

Penyebabnya: `create_ai_investigation()` menjalankan `investigate()` sebagai statement pertama di
dalam transaksi tulis, sebelum `INSERT`, dan `_write()` menulis audit serta receipt hanya setelah
`perform` selesai. `DomainError` membatalkan seluruh transaksi.

### Nilai untuk tanggal normal tidak berubah

`test_production_quality_insights` (2 test, OK) tetap menegakkan seluruh angka baseline untuk
`as_of=2026-09-23&window_days=7`, termasuk `current_period_start=2026-09-17`,
`previous_period_start=2026-09-10`, `previous_period_end=2026-09-16`, dan `PRAGMA user_version == 55`.
Test tambahan mengulang pemeriksaan periode itu beserta `demand-forecast` (`2026-08-27`,
`2026-08-26`, `2026-07-30`) dan `capacity-plan` (`horizon_end=2026-10-06`) dengan tanggal yang
dihitung tangan.

### Error validasi terlihat di UI

`node tests/test_client.mjs` menambah pemeriksaan bahwa 422 berisi `detail` string diteruskan apa
adanya ke layar dan **tidak** ditandai `uncertain`, sehingga UI tidak menawarkan ulang penyimpanan
untuk permintaan yang tidak akan pernah berhasil. Kontrasnya diuji juga: hanya 5xx pada transaksi
yang boleh menjadi `uncertain`.

```
Date boundary client checks PASS: 422 detail reaches the UI and never looks uncertain.
```

Modul browser baru `tests/browser_date_boundaries.cjs` (didaftarkan pada `tests/browser_smoke.cjs`)
memeriksanya di browser sungguhan:

```
Date boundary browser QA PASS: out-of-range dates surface the Indonesian message inside the
report dialog, safe boundaries still load, and a refused investigation never looks like an
unconfirmed save.
```

Yang diperiksa: dialog "Kualitas produksi" dengan `as_of=0001-01-01` menampilkan pesan yang menyebut
`as_of` dan `window_days` (bukan "Internal Server Error"); tanggal sah sesudahnya langsung memuat
laporan dari dialog yang sama; batas aman `0001-01-14` dengan jendela 7 hari tetap dilayani dan
`0001-01-13` ditolak; "Kapasitas produksi" dengan `9999-12-31` menyebut `horizon_days`, sedangkan
horizon satu hari tetap dilayani; dan investigasi AI yang ditolak tidak pernah menampilkan
"belum terkonfirmasi" atau "Coba ulang penyimpanan".

Modul ini gagal pada kode baseline:

```
$ PYTHONPATH=/projects/sandbox/baseline-run python tests/run_browser.py --channel chromium
locator.waitFor: Timeout 30000ms exceeded.
  - waiting for locator('#production-quality-message')
      .filter({ hasText: /di luar kalender yang terwakili/ }) to be visible
    at module.exports (/projects/sandbox/baseline-run/tests/browser_date_boundaries.cjs:16:53)
EXIT=1
```

### Tes baru gagal pada baseline

```
$ PYTHONPATH=/projects/sandbox/baseline-run python -m unittest test_date_boundaries
Ran 28 tests
FAILED (errors=50)      # termasuk subTest; per test: 14 gagal, 14 lulus
ImportError: cannot import name 'projected_date' from 'beeloft.store'
```

**14 dari 28 gagal pada kode baseline** dan seluruhnya lulus pada branch. Empat belas yang lulus di
kedua sisi adalah tes yang menegakkan perilaku yang memang sudah benar sebelum perbaikan: tanggal
tidak valid secara kalender, `start_date > end_date`, rentang satu hari, batas `ge`/`le` window,
konversi zona waktu pada `audit_events`/`activity` yang sudah punya penjaga, default Jakarta, dan
periode untuk tanggal normal. Keduanya penting: yang pertama membuktikan perbaikan, yang kedua
membuktikan tidak ada yang rusak.

## 3. P3-C: logout tanpa cookie session

### Reproduksi pada baseline

```
500 POST /api/session/logout  (X-API-Key, tanpa cookie)
     body: Internal Server Error
401 POST /api/session/logout  (tanpa kredensial)

Exception asli:
  KeyError: 'beeloft_session'
```

Reproduksi menemukan masalah kedua yang tidak disebut pada laporan temuan: request ber-API-key yang
**membawa cookie akun lain** mencabut session browser akun tersebut, tanpa pemeriksaan CSRF sama
sekali (jalur API key tidak melewatinya). Dibuktikan oleh dua tes baru yang **FAIL** pada baseline:

```
FAIL: test_an_api_key_beside_its_own_cookie_does_not_revoke_that_session
FAIL: test_an_api_key_never_revokes_another_accounts_session
```

### Hasil setelah perbaikan

```
200 POST /api/session/logout  (X-API-Key, tanpa cookie)
     body: {"status":"signed_out"}
401 POST /api/session/logout  (tanpa kredensial)
```

### Cakupan test

`tests/test_session_logout.py::LogoutWithoutABrowserCookieTest` — **18 test, OK**:

| Test | Yang ditegakkan |
| --- | --- |
| `test_api_key_without_a_cookie_answers_200_instead_of_500` | 200 `{"status":"signed_out"}`, `Cache-Control: no-store`, tidak ada session dibuat/dicabut |
| `test_repeated_api_key_logouts_stay_a_safe_no_op` | Empat panggilan berulang tetap 200 |
| `test_the_no_op_logout_does_not_revoke_the_api_key` | `/api/me` dan penulisan dengan kunci yang sama tetap berhasil sesudahnya |
| `test_every_role_may_call_the_no_op_logout` | admin, operator, viewer |
| `test_the_no_op_logout_does_not_clear_cookies_it_did_not_revoke` | Tidak ada `Set-Cookie` pada jalur no-op |
| `test_an_invalid_api_key_without_a_cookie_is_still_401` | API key tidak sah → 401 |
| `test_no_credentials_at_all_is_still_401` | Tanpa kredensial → 401 dengan pesan yang menyebut `X-API-Key` |
| `test_an_inactive_account_key_is_refused` | Akun nonaktif → 401 |
| `test_a_valid_cookie_still_revokes_the_session_and_clears_both_cookies` | Jalur sukses cookie tidak berubah |
| `test_a_missing_or_wrong_csrf_token_is_still_refused` | 403 pada CSRF hilang dan salah; session masih dapat dipakai; percobaan dengan token benar baru mencabut |
| `test_a_revoked_or_expired_cookie_is_still_401` | Kompatibel dengan penanganan 401 pada klien P2 |
| `test_an_api_key_beside_its_own_cookie_does_not_revoke_that_session` | Prioritas kredensial eksplisit; tidak ada pencabutan tanpa bukti CSRF |
| `test_an_api_key_never_revokes_another_accounts_session` | Session akun lain tetap hidup dan tetap miliknya |
| `test_the_cookie_path_still_revokes_only_the_session_that_authenticated` | Session kedua tidak tersentuh |
| `test_a_no_op_logout_leaves_every_other_session_active` | Dua session lain tetap aktif setelah no-op |
| `test_a_storage_failure_is_not_reported_as_a_successful_logout` | Trigger `RAISE(ABORT)` pada `DELETE` → bukan 200, session tetap hidup; setelah trigger dibuang logout berhasil |
| `test_the_actor_binding_header_still_applies_to_logout` | `X-Beeloft-Actor` yang salah tetap 403 |
| `test_logout_needs_no_idempotency_key` | Jumlah baris `requests` dan `audit_events` tidak berubah |

Delapan test P2 lama pada berkas yang sama tetap lulus. Bersama 6 test kontrak kredensial pada
[bagian 9](#9-kontrak-b-api-key-logout-sebagai-no-op), berkas ini berisi **32 test, OK**.

### Tes baru gagal pada baseline

```
$ PYTHONPATH=/projects/sandbox/baseline-run python -m unittest test_session_logout
Ran 26 tests
FAILED (failures=2, errors=13)      # termasuk subTest

$ PYTHONPATH=/projects/sandbox/baseline-run python -m unittest \
    test_session_logout.LogoutWithoutABrowserCookieTest
Ran 18 tests                        # per test: 10 gagal, 8 lulus
```

**10 dari 18 tes baru gagal pada baseline** dan seluruhnya lulus pada branch. Delapan yang lulus di
kedua sisi adalah tes yang menegakkan pengamanan existing agar tidak melemah: 401 tanpa kredensial,
401 untuk API key tidak sah dan akun nonaktif, 403 untuk CSRF hilang/salah, 401 untuk cookie
kedaluwarsa/sudah dicabut, jalur sukses cookie, dan kegagalan penyimpanan yang tidak disamarkan.

Dua kegagalan yang paling penting bukan tentang HTTP 500, melainkan tentang pencabutan lintas akun:

```
FAIL: test_an_api_key_beside_its_own_cookie_does_not_revoke_that_session
FAIL: test_an_api_key_never_revokes_another_accounts_session
    AssertionError: session tidak boleh dicabut tanpa bukti CSRF
```

Ketiga kelas P2 lama pada berkas yang sama (`SessionLogoutEvidenceTest` 6 test,
`SessionIdentityAfterSwitchTest` 2 test) lulus di kedua sisi dan tidak diubah.

## 4. Regresi P1/P2 yang dipertahankan

Semuanya dijalankan ulang dan lulus di dalam `unittest discover` serta browser suite:

| Perbaikan | Bukti |
| --- | --- |
| Dependency keamanan StaticFiles | `python -m pip check` bersih; `starlette>=1.3.1,<2` di `pyproject.toml` tidak disentuh; `requirements.txt` tetap `starlette==1.6.0` |
| Idempotency global dan `X-Beeloft-Actor` | `test_session_logout.SessionIdentityAfterSwitchTest`; `browser_cross_account_retry.cjs`; `browser_stale_session_first_submit.cjs`; test baru `test_the_actor_binding_header_still_applies_to_logout` |
| Rework completion, inspeksi ulang, konservasi kuantitas | `browser_rework_reinspection.cjs` PASS |
| Logout gagal/tidak pasti dan pemulihan draft per akun | `browser_logout_failure.cjs` dan `browser_ai_investigation_logout.cjs` PASS; `SessionLogoutEvidenceTest` tetap utuh |
| Penanganan pergantian identitas session | `SessionIdentityAfterSwitchTest` (2 test) |
| Agregat approval lengkap, nominal eksak tanpa overflow SUM SQLite | `ApprovalSummaryOverflowTest` (7 test) tetap lulus; test P3-A baru mengulang kasus 47 × 2 × 10¹⁷ |
| Kompatibilitas evidence investigasi AI historis | `test_ai_evidence_compatibility` **7 test, OK** |

Tidak ada assertion yang dilemahkan dan tidak ada regresi yang di-skip. Satu-satunya penyesuaian
pada tes lama adalah penambahan berkas/kelas baru; `SessionLogoutEvidenceTest` dan
`ApprovalSummary*Test` tidak diubah.

## 5. Kontrak, schema, dan versi

Versi dinaikkan **0.85.0 → 0.86.0**, mengikuti konvensi repository di mana setiap PR perbaikan audit
menaikkan satu minor (0.83.0 → 0.84.0 → 0.85.0). Diperbarui di `pyproject.toml`, `beeloft/api.py`,
dan `README.md`.

`docs/openapi.json` diregenerasi dari `app.openapi()` dengan setelan yang sama seperti berkas
terkomit (`json.dumps(..., indent=2, ensure_ascii=False)` plus newline akhir; kesetaraan
round-trip diverifikasi lebih dulu pada 0.85.0). Diff-nya dua baris:

```
-    "version": "0.85.0"
+    "version": "0.86.0"
...
         "summary": "Close Session",
+        "description": "Menutup session browser yang memberi akses pada request ini. ..."
```

Diperiksa secara terprogram: tidak ada path ditambah atau dihapus, `components` identik, dan
satu-satunya operasi yang berubah adalah `POST /api/session/logout` (hanya `description`).

Perubahan kontrak yang tidak tampak pada schema OpenAPI, karena kedua endpoint mengembalikan objek
tanpa model:

* `GET /api/command-center` → `approvals.by_kind` bertambah tiga kunci (`workforce_leave`,
  `workforce_overtime`, `payroll_batch`) secara additive. Enam kunci lama beserta tipe `int` tidak
  berubah. `pending_count`, `pending_amount`, dan `pending_without_amount` tidak berubah.
* Dua belas endpoint laporan dan tiga endpoint AI kini menjawab `422 {"detail": "<pesan>"}` untuk
  kombinasi tanggal yang tidak terwakili kalender, menggantikan `500`.
* `POST /api/session/logout` kini menjawab `200 {"status":"signed_out"}` untuk kredensial API key
  tanpa session browser, menggantikan `500`.

**Tidak ada perubahan schema database.** `PRAGMA user_version` tetap **55**, dipastikan oleh
`test_production_quality_insights` yang menegakkannya. Karena itu tidak ada migrasi baru, dan
pengujian migrasi/startup berulang/backup-restore/integrity tidak diperlukan untuk perubahan ini;
`test_backup*` dan pemeriksaan foreign key existing tetap lulus di dalam suite.

## 6. Build paket dan smoke test

```
$ /projects/sandbox/buildenv/bin/python -m build --outdir /projects/sandbox/dist .
Successfully built beeloft_one-0.86.0.tar.gz and beeloft_one-0.86.0-py3-none-any.whl
```

Build memakai venv terpisah (`pip install build`) agar tidak mengubah environment uji.

Smoke test dijalankan dari `/projects/sandbox/repro` (di luar checkout), pada venv bersih, dengan
database disposable yang dibuat oleh `python -m beeloft --db <tmp> demo` dan server pada port bebas:

```
$ /projects/sandbox/smokeenv/bin/python -m pip check
No broken requirements found.
$ /projects/sandbox/smokeenv/bin/python /projects/sandbox/repro/smoke_installed.py
cwd     : /projects/sandbox/repro
package : /projects/sandbox/smokeenv/lib64/python3.12/site-packages/beeloft
versi API terpasang : 0.86.0
P3-A OK : by_kind 9 kategori, jumlah 0 == pending_count 0
P3-B OK : tanggal ekstrem -> 422 berpesan, batas aman -> 200 (0001-01-01..0001-01-07)
P3-C OK : logout API key tanpa cookie 200 (berulang), API key tetap sah, tanpa kredensial 401
SMOKE TEST PAKET TERPASANG: LULUS
```

Diulang pada venv kedua dengan sdist (`beeloft_one-0.86.0.tar.gz`) dan hasilnya identik. Smoke test
menegaskan modulnya berasal dari `site-packages`, bukan dari checkout.

Dataset demo tidak punya approval pending, jadi angka P3-A pada smoke test adalah kasus kosong
(`0 == 0`) dengan sembilan kunci hadir. Populasi tidak kosong diuji lengkap oleh
`CommandCenterApprovalBreakdownTest`.

## 7. Batas dan bagian yang belum terverifikasi

* **Windows tidak diuji.** `start.ps1` tidak dijalankan; sandbox ini Linux. Klaim kompatibilitas
  Windows tidak dibuat.
* **CI dijalankan pada HEAD yang dipublikasikan, bukan pada `main` atau PR #6.** CI hijau dari
  keduanya tidak dipakai sebagai bukti P3. Statusnya dilaporkan pada PR; sampai CI selesai, hanya
  hasil lokal di atas yang berlaku, dan status pekerjaan ini adalah *implemented and locally
  verified; pending PR review and CI* — bukan "audit ditutup".
* **Satu konsumen hipotetis pada Kontrak A belum tertutup:** pembaca yang mengambil
  `projected_stockout_date` sendirian tanpa `days_of_cover`/`stockout_risk` tidak dapat membedakan
  "di luar kalender" dari "tanpa demand". Tidak ada pembaca seperti itu di repo ini dan tesnya
  mengunci pasangan field tersebut, tetapi konsumen baru di masa depan perlu memakai pasangannya
  atau menuntut metadata alasan additive.
* **Kontrak A pada sisi UI diverifikasi dengan pembacaan kode, bukan dengan tes browser.**
  `app.mjs:3246/3247/3988` mengunci kalimatnya pada `days_of_cover===null`, bukan pada proyeksinya;
  membangun stok bertanggal 9999 di dalam dataset demo browser tidak dilakukan. Invarian datanya
  ditegakkan pada level HTTP.
* **Playwright dipasang tanpa dependency sistem.** `npx playwright install --with-deps chromium`
  gagal karena image ini bukan Ubuntu (`apt-get: command not found`), jadi hanya biner Chromium yang
  dipasang. Suite-nya berjalan dan lulus, tetapi bukan konfigurasi yang identik dengan job `browser`
  di CI. Job CI itu memakai `--with-deps` pada `ubuntu-latest` dan tidak diubah.
* **Browser suite dijalankan dengan `--channel chromium`**, bukan `msedge` yang menjadi default
  `run_browser.py`. Ini sama dengan yang dipakai CI.
* **Tidak ada modul browser untuk P3-A dan P3-C.** Untuk P3-A karena rincian `by_kind` tidak punya
  permukaan UI (lihat bagian 1); untuk P3-C karena UI selalu memakai cookie dan tidak pernah
  mengirim API key, sehingga kombinasi yang diperbaiki tidak dapat dihasilkan dari browser. Keduanya
  tercakup pada level HTTP dan store.
* **`InvestigationCreate.as_of` memakai `date.today()`**, bukan `jakarta_today()`, sehingga default
  investigasi dapat berbeda satu hari dari default endpoint laporan antara 17:00–24:00 UTC. Ini
  perilaku baseline, tidak terkait ketiga temuan P3, dan sengaja tidak diubah agar tidak menggeser
  angka yang sudah di-pin. Dicatat sebagai temuan terpisah.
* **Batas aman per endpoint diturunkan dari pembacaan kode**, lalu dibuktikan oleh tesnya. Kalau
  suatu endpoint kelak mengubah jarak periodenya, tabel di
  [rencana](audit-p3-plan.md) harus ikut diperbarui; tesnya akan gagal lebih dulu.
* **Peningkatan CI tidak dikerjakan.** `.github/workflows/ci.yml` tidak diubah. Yang layak
  dipertimbangkan terpisah: menjalankan `python -m build` dan smoke test paket di CI (keduanya baru
  dijalankan manual), serta memasang `pyenv`/matriks Python bila dukungan >3.12 ingin dijamin.
* Ketiga temuan ini adalah temuan P3 terakhir dari audit awal. Ditanganinya delapan temuan audit
  tidak berarti aplikasinya bebas bug; hanya berarti kedelapan temuan itu punya perbaikan beserta
  regresinya.

## 8. Kontrak A: semantik None pada proyeksi habis stok

`projected_date()` mengembalikan `None` ketika tanggal habis stok jatuh di luar kalender, dan `None`
juga sudah lebih dulu menjadi nilai untuk SKU tanpa laju permintaan. Pertanyaannya: apakah kedua
keadaan itu masih dapat dibedakan oleh pembacanya?

**Jawabannya ya, dan kontraknya sudah benar sebelum pemeriksaan ini — tidak ada perubahan kode.**
Yang menyatakan "ada demand atau tidak" bukan tanggal proyeksinya, melainkan
`days_of_cover`/`forecast_daily_rate` bersama `stockout_risk` (replenishment) atau `risk_status`
(size demand).

### Pembaca field ini

| Pembaca | Yang dibacanya | Kesimpulan |
| --- | --- | --- |
| `store.py:5404-5434` `replenishment_recommendations` | `risk` dihitung dari `available`, `cover`, `reorder_point`; `cover_days` terisi setiap kali `rate` bukan nol. Cabang tanpa rate menetapkan `cover_days=stockout=None` **dan** `risk='no_demand'/'insufficient_history'` | Dua keadaan itu berbeda pada `days_of_cover` dan `stockout_risk` |
| `store.py:4256-4290` `size_demand_insights` | `risk_rank` dan `risk_status` dihitung dari `cover`, bukan dari `projected`; baris tanpa rate tetap `risk_status='no_observed_demand'` dan `days_of_cover=None` | Sama |
| `store.py:4301-4316` agregasi keluarga | `first_stockout_date` = min proyeksi yang ada; `earliest_projected_stockout_date` = min lintas keluarga | Melaporkan "tanggal terwakili paling awal", bukan mengubah status |
| `store.py:4307` pengurutan keluarga | `row['first_stockout_date'] or '9999-12-31'` | **Hanya kunci pengurutan**, tidak pernah menjadi nilai di respons — ditegakkan oleh tes |
| `brain.py:74-82` findings AI | `stockout_risk` dan `days_of_cover` saja | **Tidak pernah membaca `projected_stockout_date`** |
| `app.mjs:3246` baris ukuran | `row.days_of_cover===null ? ' · days of cover belum tersedia' : ' · N hari' + (row.projected_stockout_date ? ' · estimasi <tanggal>' : '')` | Kalimat "belum tersedia" dikunci pada `days_of_cover`, bukan pada proyeksi |
| `app.mjs:3247` kartu keluarga | Label status dari `family.risk_status`; tanggal hanya ditambahkan bila ada | Status tidak bergantung proyeksi |
| `app.mjs:3988` kartu replenishment | Judul dari `risks[row.stockout_risk]`; sel "Days of cover" dikunci pada `days_of_cover===null`; "estimasi stockout" hanya bila ada | Sama |

### Bukti eksperimen terkontrol

`tests/test_date_boundaries.py::StockProjectionSemanticsTest` — **8 test, OK**. Fixture-nya satu
penjualan berdemand positif bertanggal `9999-12-05`, dibaca pada dua tanggal acuan dengan parameter
identik (`window_days=14, lead_time_days=1, review_period_days=1, safety_stock_days=0`). Cover
13,33 hari dari `9999-12-18` menunjuk `10000-01-01`; dari `9999-12-10` menunjuk `9999-12-24`.

| Field | `as_of=9999-12-10` | `as_of=9999-12-18` |
| --- | --- | --- |
| `forecast_daily_rate` | `0.3000` | `0.3000` |
| `recent_net_demand` | 6 | 6 |
| `available_quantity` | 4 | 4 |
| `days_of_cover` | `13.33` | `13.33` |
| `reorder_point_quantity` / `target_stock_quantity` | 1 / 1 | 1 / 1 |
| `stockout_risk` | `covered` | `covered` |
| `summary` | identik | identik |
| **`projected_stockout_date`** | **`9999-12-24`** | **`null`** |

Yang ditegakkan:

* **Demand positif tetap dilaporkan positif.** `forecast_daily_rate='0.3000'`, `recent_net_demand=6`,
  dan `days_of_cover='13.33'` tetap terisi ketika proyeksinya `None`.
* **Angka dan status risiko mengikuti perhitungan bisnis.** Sepuluh field bisnis dibandingkan
  langsung antara kedua tanggal dan seluruhnya sama; hanya proyeksinya berbeda.
* **Tidak ditafsirkan sebagai "tidak ada demand" atau "tidak ada risiko".**
  `stockout_risk not in ('no_demand','insufficient_history')`, dan penghitung populasi menegaskannya:
  `summary['no_demand']==0`, `summary['insufficient_history']==0`, `summary['covered']==1`.
* **Tidak ada penggantian, clipping, atau pemangkasan window.** Proyeksinya bukan `'9999-12-31'`,
  bukan `as_of`, bukan `planning_horizon_end`; `window_days=14`, `coverage_days=2`,
  `planning_horizon_end='9999-12-20'`, dan periode forecast (`history_start='9999-11-21'`,
  `previous_period_end='9999-12-04'`, `recent_period_start='9999-12-05'`) dilaporkan apa adanya.
  `'9999-12-31'` tidak muncul sama sekali pada respons yang diserialisasi.

Satu respons size demand memuat **kedua arti `None` sekaligus**, dan keduanya tetap terpisah:

| Ukuran | `recent_net_demand` | `forecast_daily_rate` | `days_of_cover` | `projected_stockout_date` | `risk_rank` | `risk_status` |
| --- | --- | --- | --- | --- | --- | --- |
| M | 6 | `0.3000` | `13.33` | `null` | 1 | `later` |
| L | 0 | `0.0000` | `null` | `null` | `null` | `no_observed_demand` |

Pada level keluarga, `first_stockout_date` menjadi `null` sementara `risk_status` tetap `later` dan
`first_stockout_sizes` tetap `['M']` — keluarganya tidak berubah menjadi "tanpa demand". Kontrolnya
pada `as_of=9999-12-10` melaporkan `9999-12-24` untuk demand yang sama.

Pembacaan AI diuji langsung: SKU berdemand positif dengan proyeksi tak terwakili dinilai `covered`
sehingga bukan temuan, dan **tidak pernah** dilabeli `'tidak ada demand pada window'`; SKU yang
memang tanpa riwayat tetap dilaporkan sebagai `'riwayat demand belum cukup'` dengan
`'coverage belum tersedia'`. Jawaban AI tidak memuat string `'9999'` sama sekali.

**7 dari 8 test ini gagal pada baseline** `c77248be` (di sana permintaannya HTTP 500). Satu yang
lulus di kedua sisi adalah kontrol tanggal terwakili.

### Sisa ambiguitas

Tidak ada yang terlihat pada konsumen, jadi tidak ada metadata alasan yang ditambahkan. Perlu
dicatat jujur: sebuah konsumen yang membaca `projected_stockout_date` **sendirian**, tanpa
`days_of_cover` atau `stockout_risk`, tidak dapat membedakan kedua keadaan. Tidak ada konsumen
seperti itu di repo ini — ketiga pembaca (store, brain, app.mjs) selalu membaca pasangannya, dan tes
di atas mengunci pasangan tersebut. Bila kelak ada konsumen baru yang membaca proyeksinya sendirian,
metadata alasan additive (misalnya `projected_stockout_status`) menjadi pilihan yang tepat.

## 9. Kontrak B: API-key logout sebagai no-op

`LogoutWithoutABrowserCookieTest` (18 test) sudah menegakkan status HTTP dan jumlah session untuk
setiap kombinasi kredensial. `LogoutCredentialAndCookieContractTest` (**6 test, OK**) menutup apa
yang tidak dapat dibuktikan oleh status 200 saja: header `Set-Cookie` dan keadaan session yang
sebenarnya, dibaca baris demi baris dari tabel `browser_sessions`
(`token_hash, csrf_hash, user_id, expires_at`).

| Yang harus terbukti | Test | Bukti |
| --- | --- | --- |
| Session yang tidak mengautentikasi request tidak dicabut | `test_same_identity_cookie_is_not_touched_and_still_authenticates`, `test_other_identity_cookie_is_not_touched_and_still_authenticates` | `rows()` sebelum == sesudah, bukan hanya `COUNT(*)` |
| Respons tidak menghapus atau menimpa cookie yang bukan target | keduanya, lewat `assert_no_cookie_touched()` | `response.headers.get_list('set-cookie') == []`, dan cookie klien masih bernilai sama |
| Session tersebut tetap bisa dipakai lewat autentikasi cookie | keduanya | `/api/me` lewat cookie menjawab identitas pemiliknya; identitas sama juga berhasil menulis (201) dengan CSRF |
| API key tetap valid setelah no-op | `test_the_api_key_stays_valid_after_a_no_op_logout_that_carried_a_cookie` | Cookie dibersihkan, lalu `/api/me` dan satu penulisan berhasil dengan API key yang sama |
| Logout normal lewat cookie tetap butuh CSRF dan mencabut session yang sesuai | `test_same_identity_...`, `test_other_identity_...` | Tanpa CSRF → 403 dan session masih 1; dengan CSRF → 200, `Set-Cookie` menghapus `beeloft_session` dan `beeloft_csrf`, session menjadi 0 |
| Hanya session yang mengautentikasi yang dicabut | `test_only_the_authenticating_session_is_revoked_when_several_exist` | Tiga session: no-op menyisakan ketiganya; logout cookie menyisakan dua, keduanya masih milik akun aslinya |
| Kegagalan storage bukan sukses palsu | `test_a_storage_failure_beside_a_cookie_is_not_a_false_success` | Trigger `RAISE(ABORT)` pada `DELETE`: no-op tetap 200 tanpa menyentuh penyimpanan; logout cookie menjawab ≥400, `rows()` tidak berubah, session masih dapat dipakai; setelah trigger dibuang logout berhasil |
| Berulang tetap aman | `test_repeated_no_op_logouts_beside_a_cookie_stay_harmless` | Tiga panggilan, `rows()` tidak berubah, session masih dipakai sesudahnya |

Pada kasus identitas berbeda, penulisan lewat cookie operator dijawab `403 "Role ini tidak
diizinkan..."` — aturan role, bukan session atau CSRF. Perbedaannya dibuktikan berdampingan: token
CSRF yang salah pada request yang sama dijawab `403 "Token keamanan browser tidak valid."` lebih
dulu, sebelum role diperiksa. Jadi 403 pertama memang membuktikan session dan CSRF-nya lolos.

**Prioritas kredensial, dinyatakan eksplisit:** `X-API-Key` menang atas cookie (tidak berubah dari
baseline), dan logout hanya mencabut session yang memberinya akses. Konsekuensinya sebuah API key
tidak dapat mengakhiri session browser akun mana pun tanpa bukti kepemilikan token CSRF-nya.

**5 dari 6 test ini gagal pada baseline** `c77248be`, termasuk kedua kasus pencabutan lintas akun.
Satu yang lulus di kedua sisi adalah validitas API key, yang perilaku lama pun sudah memenuhi.

## 10. Tindak lanjut komentar review pada PR #7

CI pada HEAD yang dipublikasikan: **sukses**, kedua job (`Core tests`, `Browser acceptance`) —
[run 35204619157](https://github.com/wenn-id/beeloftone/actions/runs/35204619157) pada
`628ae9f0deb140469c79e809c646ae44d8222018`. CI hijau pada `main` atau PR #6 tidak dipakai sebagai
bukti P3.

Review otomatis: **Codex** tidak menemukan masalah ("Didn't find any major issues") pada `628ae9f0de`.
**CodeRabbit** menyetujui (`APPROVED`) dengan satu nitpick, yang valid dan sudah diperbaiki.

### 10.1 `shift_date` tidak pernah dijalankan pada tes "unrelated errors" (CodeRabbit, review `5233731544`)

Temuan: pada `tests/test_date_boundaries.py`,

```python
with self.assertRaises(ZeroDivisionError):
    shift_date(date(2026, 1, 1), 1 // 0, 'as_of')
```

`1 // 0` dievaluasi saat menyusun daftar argumen, jadi assertion-nya lulus **tanpa pernah masuk ke
helper maupun blok `try`-nya**. Tesnya karena itu tidak membuktikan apa pun tentang cakupan
`except OverflowError`.

Diverifikasi terhadap kode, bukan diterima begitu saja — helper dibungkus lalu pemanggilannya
dihitung:

```
calls recorded with the old 1//0 form: 0   (0 == helper never ran)
```

Perbaikannya minimal: anchor diganti objek yang `__add__`-nya melempar, sehingga kesalahannya terjadi
**di dalam** `anchor + timedelta(days=days)` tempat penjaganya berada, dan assertion memeriksa pesan
exception yang hanya dapat berasal dari objek itu. Dua kasus `TypeError` yang sudah ada memang sejak
awal gagal di dalam operasi yang sama, jadi dipertahankan.

```
$ python -m unittest test_date_boundaries.ShiftDateHelperTest
Ran 3 tests
OK
$ python -m unittest discover -s tests
Ran 507 tests
OK
```

Diperbaiki pada `4ef1eac`. Tidak ada komentar yang ditandai selesai tanpa perbaikan dan pengujiannya.

Tidak ada review comment berbasis baris (`pulls/7/comments` kosong) dan tidak ada temuan review lain
yang terbuka pada saat dokumen ini ditulis.

## 11. Status

**Implemented and locally verified; pending PR review and CI.**

Ini bukan pernyataan bahwa audit sudah ditutup. Ketiga temuan P3 punya perbaikan beserta regresi yang
menguncinya dan seluruh tes lokal hijau, tetapi review dan CI pada HEAD yang dipublikasikan belum
selesai. Ditanganinya delapan temuan audit juga tidak berarti aplikasinya bebas bug.

| Temuan | Status | Ringkas bukti |
| --- | --- | --- |
| P3-A: breakdown approval belum memasukkan cuti, lembur, dan payroll | **FIXED** | `by_kind` diturunkan dari `APPROVAL_KINDS`; kesembilan kategori hadir; `sum(by_kind.values()) == pending_count`; enam nilai lama tidak bergeser; 14 test baru, 11 di antaranya gagal pada baseline |
| P3-B: tanggal ekstrem yang lolos validasi menyebabkan HTTP 500 | **FIXED** | 15 jalur (12 endpoint laporan + 3 endpoint AI) berubah dari 500 menjadi 422 berpesan; batas aman tetap 200; loop hari `capacity_plan` diperbaiki; tanggal normal tidak berubah; 28 test (14 gagal pada baseline) + 1 modul browser yang gagal pada baseline |
| P3-C: logout dengan API key tanpa cookie menyebabkan HTTP 500 | **FIXED** | 200 no-op tanpa mencabut API key; pencabutan session lintas akun tanpa CSRF dihentikan; 18 test baru, 10 di antaranya gagal pada baseline |
| Kontrak A: semantik `None` pada proyeksi habis stok | **TERBUKTI, tanpa perubahan kode** | `days_of_cover` dan `stockout_risk`/`risk_status` yang membedakan, bukan proyeksinya; sentinel `'9999-12-31'` tidak pernah dilaporkan; 8 test, 7 gagal pada baseline |
| Kontrak B: kredensial dan cookie pada logout | **TERBUKTI, tanpa perubahan kode** | Tidak ada `Set-Cookie` pada jalur no-op; baris session utuh; session tetap dipakai lewat cookie termasuk untuk menulis; 6 test, 5 gagal pada baseline |

Dicatat terpisah, tidak dikerjakan pada task ini: default `as_of` investigasi AI memakai
`date.today()` proses alih-alih `jakarta_today()`, dan CI belum menjalankan `python -m build` beserta
smoke test paket.
