# Bukti pengujian: agregat produksi pada jawaban fokus

Temuan: [issue #29](https://github.com/wenn-id/beeloftone/issues/29) — pertanyaan tentang satu order
dijawab dengan total seluruh produksi. `_production()` memakai ringkasan global `production_board`
apa adanya, sehingga angka order lain ikut masuk ke jawaban dan facts.

## Baseline

| | |
|---|---|
| Commit baseline | `10d330e` (`main`, perbaikan #65 sudah masuk) |
| Aplikasi / schema | 0.90.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/audit-p2-focused-production-aggregate` |
| Working tree awal | bersih |

Temuan direproduksi ulang terhadap commit tersebut sebelum satu baris pun diubah. Tidak ada checkout
paksa ke commit lama dan tidak ada perubahan lokal yang dibuang.

## Lingkungan

Python 3.14.4 pada venv repositori (`.venv`), Node.js 24.16.0, Playwright 1.63.0 dengan Chromium pada
`~/.cache/ms-playwright`, Linux. Seluruh pengujian memakai database sementara sekali pakai
(`tempfile.TemporaryDirectory` pada test dan runner browser); tidak ada database bisnis atau
produksi yang disentuh.

## Reproduksi

`Store.production_board` (`beeloft/store.py`) menghitung `summary` dari CTE `production` **tanpa**
filter apa pun. Ringkasan global itu memang kontrak KPI board: daftar boleh difilter, angka KPI tidak
boleh bergoyang. `_production()` (`beeloft/brain.py:126`) kemudian memakai `board['summary']` dan
`board['open_issues']` untuk pertanyaan yang menyebut satu order, sehingga jawabannya bercampur.

Dua order pada database disposable:

```
AUDIT-FOCUSED : 10 pcs, tenggat 2026-12-31, seluruhnya di planned
AUDIT-LATE    : 500 pcs di cutting, tenggat 2026-01-01
```

Pertanyaan `Cek produksi AUDIT-FOCUSED` mengenali tepat satu order dan evidence daftarnya juga satu
order, tetapi jawaban pada baseline:

```
Ada 2 order aktif, 1 terlambat, 0 kendala terbuka, dan 500 pcs sedang diproses.
```

Test regresi dijalankan terhadap baseline sebelum perbaikan:

| Test | Baseline `10d330e` | Sesudah perbaikan |
| --- | --- | --- |
| `test_focused_production_answer_never_reports_another_order` | FAIL — `'Ada 2 order aktif, 1 terlambat, 0 kendala terbuka, dan 500 pcs sedang diproses.'` | OK — `'Ada 1 order aktif, 0 terlambat, 0 kendala terbuka, dan 0 pcs sedang diproses.'` |
| `test_focused_production_aggregate_covers_results_beyond_one_page` | FAIL — `'Ada 125 order aktif, 5 terlambat, …'` untuk populasi fokus 120 order | OK — `'Ada 120 order aktif, 0 terlambat, …'` |
| `test_production_scope.ProductionScopeTest` (4 test) | ERROR ×4 — `Store' object has no attribute 'production_scope'` | OK |
| `test_routes_questions_to_approvals_production_margin_and_overview` | FAIL — kunci evidence `production_scope` belum ada | OK |

Dua arah kesalahan sekaligus terbukti pada test kedua: jawaban yang masih memakai KPI global
melaporkan 125 order, sedangkan jawaban yang hanya menjumlahkan halaman pertama akan melaporkan 100.
Angka yang benar adalah 120.

## Perbaikan

- `Store.production_scope(query, status, owner_id, stage)` (`beeloft/store.py`) menghitung
  `summary`, `total`, dan `open_issues` hanya atas order yang cocok filter, **tanpa** pagination:
  agregatnya `COUNT(*)`/`SUM(...)` di database, bukan penjumlahan satu halaman yang sudah
  terhidrasi. `open_issues`-nya ikut dibatasi ke order terpilih melalui join yang sama.
- Definisi populasi tidak diduplikasi. CTE per-order, kondisi filter, dan kolom ringkasan dipakai
  bersama `production_board()` melalui `PRODUCTION_CTE_SQL`, `PRODUCTION_WHERE_SQL`, dan
  `PRODUCTION_SUMMARY_COLUMNS`, sehingga agregat fokus dan daftar board tidak dapat menyimpang
  diam-diam. Refactor ini tidak mengubah keluaran `production_board()`: ringkasannya tetap global
  dan `test_board_filters.py` yang menguncinya lulus tanpa diubah.
- `_production()` (`beeloft/brain.py:126-154`) memakai `production_scope(query)` untuk jawaban dan
  keempat facts. `query` tetap diturunkan dari fokus yang sama seperti sebelumnya (satu order atau
  satu SKU); tanpa fokus, populasi scope sama dengan populasi global.
- `evidence` menyimpan keduanya: `production_board` yang membawa kontrak KPI global dan
  `production_scope` yang benar-benar mendasari jawaban. Tanpa itu snapshot akan memuat angka yang
  bertentangan dengan jawabannya sendiri. Kunci `evidence` bertambah satu secara sengaja dan
  dikunci eksplisit di tiga test yang sudah ada.
- Tidak ada perubahan schema (`user_version` tetap 55), tidak ada endpoint atau field API baru, dan
  `/api/production-board` tidak berubah sama sekali (`docs/openapi.json` hanya berubah pada
  `info.version`).

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | `Ran 536 tests` — **OK**. Sebelumnya 530 pada commit audit; 6 test baru (2 di `test_ai_investigation.py`, 4 di `test_production_scope.py`) |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs`, `node --check beeloft/static/client.mjs`, `node tests/test_client.mjs` | bersih dan **PASS** |
| `python tests/run_browser.py --node node --playwright-module <playwright> --channel chromium` | 78 modul acceptance **PASS**, tanpa JS error |
| Reproduksi baseline vs tree perbaikan | tabel di atas: jawaban fokus gagal di baseline, lulus sesudah perbaikan |

Test baru:

- `tests/test_ai_investigation.py::test_focused_production_answer_never_reports_another_order` —
  reproduksi temuan: order fokus 10 pcs yang belum jatuh tempo bersama order terlambat berisi 500 pcs
  di cutting. Jawaban dan facts hanya memuat angka order terpilih, sementara KPI board tetap
  `{'orders': 2, 'active': 2, 'overdue': 1, 'closed': 0, 'in_progress': 500, 'rework': 0}` baik pada
  daftar tak difilter maupun difilter.
- `tests/test_ai_investigation.py::test_focused_production_aggregate_covers_results_beyond_one_page` —
  populasi fokus 120 order yang melewati limit halaman 100, ditambah 5 order di luar populasi fokus.
  Jawaban menyebut 120 (bukan 125 dari KPI global, bukan 100 dari halaman pertama), dan
  `evidence.production_scope` menyimpan populasi yang sama.
- `tests/test_production_scope.py`, 4 test pada tingkat store, dengan oracle Python yang menghitung
  ulang setiap baris dari saldo tahapnya:
  - `test_selected_aggregate_matches_the_board_population_for_every_filter` — 11 kombinasi
    `query`/`status`/`owner_id`/`stage`: `total` scope sama dengan `total` daftar, dan `summary`
    scope sama dengan oracle atas baris yang dikembalikan daftar itu.
  - `test_board_kpi_stays_global_while_the_selected_aggregate_narrows` — ringkasan board identik di
    empat filter yang berbeda, sedangkan agregat scope-nya menyempit; kontrak KPI tidak berubah.
  - `test_scope_counts_only_issues_of_the_selected_orders` — kendala selesai tidak dihitung, dan
    kendala order lain tidak bocor ke scope order terpilih.
  - `test_empty_population_is_reported_as_zero_not_as_the_global_board` — populasi kosong dijawab nol,
    bukan ringkasan global.
