# Bukti pengujian: hidrasi order pada metadata focus investigasi

Temuan: [issue #36](https://github.com/wenn-id/beeloftone/issues/36) — pertanyaan approval
menjalankan `_focus()` sebelum dispatch intent, dan fungsi itu memuat seluruh produk beserta seluruh
detail order. Jawaban approval sendiri hanya memakai agregat dan contoh approval, jadi biaya hidrasi
itu tidak pernah terpakai.

## Baseline

| | |
|---|---|
| Commit baseline | `c388a0f` (`main`, perbaikan #70 sudah masuk) |
| Aplikasi / schema | 0.94.0 / `PRAGMA user_version` 55 |
| Working tree awal | bersih |

Audit pada issue mencatat commit `f8921e76` dan aplikasi 0.87.0. Temuan direproduksi ulang terhadap
`c388a0f` sebelum satu baris pun diubah, dan angkanya identik dengan tabel di issue. Tidak ada
checkout paksa ke commit lama dan tidak ada perubahan lokal yang dibuang.

## Lingkungan

Python 3.13.13 pada venv repositori (`.venv`), Node.js 24.19.0, Linux. Seluruh pengujian memakai
database sementara sekali pakai (`tempfile.TemporaryDirectory`); tidak ada database bisnis atau
produksi yang disentuh.

## Reproduksi

`_focus()` (`beeloft/brain.py:31-40` pada baseline) memanggil `store.orders(1_000_000_000, 0)`.
`Store.orders` (`beeloft/store.py:7121-7124` pada baseline) memanggil `_order()` untuk setiap baris,
dan `_order()` membaca revision, lines, balances per line, serta hitungan kendala terbuka. Biayanya
tumbuh sekitar lima statement per order. `investigate()` menjalankan `_focus()` untuk **semua**
intent (`beeloft/brain.py:200` pada baseline), termasuk `approvals` yang tidak memakai hasilnya sama
sekali: `_approvals(store)` hanya menerima `store`.

Pengukuran memakai statement yang benar-benar dieksekusi SQLite lewat `set_trace_callback`, bukan
teks sumber. Populasi sintetis satu baris per order, pertanyaan `approval persetujuan`:

| Order | Statement SQL baseline | Statement SQL sesudah | Waktu baseline | Waktu sesudah |
|---|---:|---:|---:|---:|
| 100 | 528 | 28 | 0,024 detik | 0,019 detik |
| 1.000 | 5.028 | 28 | 0,056 detik | 0,023 detik |
| 5.000 | 25.028 | 28 | 0,210 detik | 0,031 detik |

Kolom baseline mereproduksi tabel issue persis (528 / 5.028 / 25.028). Sesudah perbaikan jumlahnya
konstan 28 pada ketiga ukuran: biaya lima statement per order hilang sepenuhnya, bukan berkurang.
Waktu tetap satu pengukuran per ukuran dan bukan benchmark produksi — yang dikunci test adalah
jumlah query, bukan durasinya.

Ke-28 statement itu seluruhnya bukan detail order: dua pembacaan identitas (`products`, `orders`),
sembilan agregat `approvals_summary`, sembilan pembacaan id untuk daftar contoh, dan `BEGIN`/`COMMIT`
per transaksi.

Test regresi dijalankan terhadap baseline sebelum perbaikan:

| Test | Baseline `c388a0f` | Sesudah perbaikan |
| --- | --- | --- |
| `test_approval_cost_stays_flat_while_the_order_population_grows` | FAIL — `126 != 626` untuk populasi 20 lalu 120 order | OK — jumlah statement identik pada kedua populasi |
| `test_approval_path_never_touches_order_detail_tables` | FAIL — `'order_changes' unexpectedly found in "select coalesce(max(sequence),0) from order_changes where order_id=…"` | OK |
| 8 test lain pada `tests/test_ai_focus_hydration.py` | OK (mengunci kontrak yang memang belum berubah) | OK |

Selisih `626 - 126 = 500` pada 100 order tambahan adalah lima statement per order yang disebut issue,
terukur langsung dan bukan angka yang dipatok di dalam test.

## Perbaikan

- `Store.order_identities(limit, offset)` (`beeloft/store.py`) membaca `id`, `reference`, dan `title`
  dalam satu statement, dengan `ORDER BY` yang sama seperti `orders()` sehingga paginasinya tetap
  dapat dibandingkan. `Store.product_identities(limit, offset)` melakukan hal setara untuk `id`,
  `sku`, dan `name`.
- `_focus()` (`beeloft/brain.py`) memakai kedua pembacaan identitas itu. Metadata focus tetap bagian
  dari kontrak jawaban dan bentuknya tidak berubah; yang hilang hanya hidrasi yang tidak dipakai
  untuk mencocokkan SKU atau referensi order. Detail dimuat belakangan, oleh jalur intent yang
  benar-benar memerlukannya.
- `Store.order_ids_for_products(product_ids)` (`beeloft/store.py`) memilih order yang memiliki baris
  untuk salah satu produk, juga tanpa hidrasi dan dengan urutan yang sama seperti `orders()`.
- `_margin()` (`beeloft/brain.py`) bekerja atas id order, bukan atas order yang sudah dihidrasi.
  Fokus order memakai id dari focus, fokus produk memakai `order_ids_for_products()`, dan tanpa fokus
  memakai daftar identitas. `contribution_margin()` tetap yang memuat detail, dan hanya untuk order
  yang benar-benar dilaporkan. Pemotongan 100 order serta flag `evidence.truncated` tidak berubah.
- `investigate()` tidak lagi menerima daftar produk yang sebelumnya dibuang (`focus,_,orders` menjadi
  `focus,orders`).
- Tidak ada cache, service, atau dependency baru; tidak ada perubahan schema (`user_version` tetap
  55); tidak ada endpoint atau field API baru. `docs/openapi.json` diregenerasi dari `app.openapi()`
  dan hanya berubah pada `info.version`.

Jalur `stockout`, `production`, dan `overview` tidak pernah memakai order yang dihidrasi `_focus()`,
sehingga ikut berhenti membayar biaya yang sama. Hanya intent `margin` yang masih memuat detail
order, dan itu memang yang dilaporkannya.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | `Ran 549 tests` — **OK**. Sebelumnya 539; 10 test baru di `tests/test_ai_focus_hydration.py` |
| `python -m pip check` | `No broken requirements found.` |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs`, `node --check beeloft/static/client.mjs` | bersih |
| `node tests/test_client.mjs` | **PASS** (escaping, tanggal, retry, POST read-only, header auth, actor, error terstruktur, CSV, batas tanggal) |
| Reproduksi baseline vs tree perbaikan | tabel di atas: dua test gagal di baseline, lulus sesudah perbaikan |

Suite browser Playwright tidak dijalankan di lingkungan pengembangan ini karena browser Playwright
tidak terpasang. Perubahan ini tidak menyentuh `beeloft/static/` maupun berkas UI lain — hanya
`beeloft/brain.py` dan `beeloft/store.py` — sehingga modul browser tidak terpengaruh. CI repositori
menjalankannya dan kedua job hijau pada
[run 35592599810](https://github.com/wenn-id/beeloftone/actions/runs/35592599810): `Core tests`
**success** dan `Browser acceptance` **success**.

Test baru, seluruhnya di `tests/test_ai_focus_hydration.py`:

- `ApprovalPathHydrationTest::test_approval_cost_stays_flat_while_the_order_population_grows` —
  reproduksi temuan. Jumlah statement investigasi approval pada populasi 20 order harus identik
  dengan populasi 120 order, sampai ke daftar statement-nya. Oracle biaya hidrasinya independen dan
  hidup: `store.orders()` pada populasi yang sama diukur di test itu juga dan harus tetap berbiaya
  minimal lima statement per order, sedangkan `order_identities()` satu statement. Jadi test
  membuktikan biaya itu masih ada di jalur hidrasi, dan tidak lagi dibayar jalur approval.
- `ApprovalPathHydrationTest::test_approval_path_never_touches_order_detail_tables` — tidak satu pun
  statement menyebut `balances`, `order_lines`, atau `order_changes`.
- `ApprovalPathHydrationTest::test_approval_answer_aggregates_and_evidence_stay_correct` — jawaban,
  facts, `evidence.summary`, ukuran contoh, dan flag `truncated` diperiksa terhadap oracle fixture
  `ApprovalFixture`, dengan 30 order di database untuk memastikan hasilnya tidak bergantung pada
  populasi order. Metadata focus kosong tetap dilaporkan sebagai `{'products': [], 'orders': []}`.
- `ApprovalPathHydrationTest::test_focus_metadata_contract_is_unchanged` — pertanyaan yang menyebut
  referensi order dan SKU tetap menghasilkan focus dengan kunci `id`/`reference`/`title` dan
  `id`/`sku`/`name` yang sama seperti sebelumnya.
- `MarginSelectionTest` (3 test) — oracle-nya logika lama: memfilter order yang sudah dihidrasi di
  Python, lalu dibandingkan dengan `evidence.contribution_margins` hasil investigasi. Diperiksa
  untuk tanpa fokus, fokus produk, dan fokus order, pada populasi dua produk dengan tenggat yang
  sengaja tidak searah dengan urutan pembuatan sehingga penyimpangan `ORDER BY` akan terlihat.
- `IdentityReadTest` (2 test) — `order_identities()` sama dengan proyeksi identitas dari
  `orders()` termasuk urutan dan paginasi, `product_identities()` sama dengan proyeksi dari
  `products()`, dan `order_ids_for_products()` benar untuk daftar kosong, id tidak dikenal, dan id
  berulang, dengan satu statement dan tanpa menyentuh `balances`.
- `AuthenticatedEndpointTest::test_endpoint_answer_is_identical_to_the_direct_call` — jawaban
  `POST /api/ai/investigate` identik dengan pemanggilan `investigate()` langsung.
