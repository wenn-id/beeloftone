# Rencana Implementasi: Mode Jubelio Demo

> **Untuk pekerja agen:** Gunakan pedoman eksekusi bertahap. Setiap langkah menggunakan checkbox (`- [ ]`) untuk pelacakan.

**Goal:** Mengimplementasikan mode "Jubelio Demo" di Beeloft One menggunakan provider simulasi in-process deterministik, kontrol sinkronisasi UI, isolasi database demo, dan aliran ingestion snapshot existing tanpa mengubah skema tabel core.

**Architecture:** Provider dataset sintetis terisolasi (`beeloft/jubelio_demo.py`) menghasilkan snapshot order, stok, listing, dan retur pakaian anak (~30 SKU, 120 order baseline, skenario pembaruan bertahap) melalui jalur snapshot existing (`/api/integrations/jubelio/*-snapshots`). Read model existing membaca batch snapshot terbaru. Kunci konkurensi database (`jubelio_demo_state`) mencegah eksekusi ganda, dan kontrol UI pada kartu Integrasi mengelola siklus demo.

**Tech Stack:** Python 3.12, SQLite 3 (WAL mode), FastAPI, Pydantic v2, Vanilla JS / CSS Workspace Primitives, Playwright Browser Tests.

**Spec:** `docs/superpowers/specs/2026-09-28-jubelio-demo-design.md`

## Global Constraints

- Gunakan jalur ingestion existing: `import_jubelio_order_snapshot`, `import_jubelio_stock_snapshot`, `import_jubelio_return_snapshot`, `import_jubelio_listing_snapshot`.
- Jangan membuat tabel order/stok paralel atau dashboard paralel.
- Setiap batch snapshot harus memuat data LENGKAP untuk scope yang digantikannya (bukan delta terpotong yang menghilangkan data lama).
- Dataset deterministik berbasis tanggal acuan tetap: `2026-09-28T00:00:00Z`.
- Karantina historis bersifat immutable; evaluasi ulang dilakukan melalui batch baru setelah pemetaan SKU.
- Proteksi konkurensi di tingkat database transaksi, bukan variabel memori tunggal.
- Mode demo hanya aktif pada database demo terverifikasi.
- Pertahankan file `seed55.py` dan branch worktree terpisah `feat/jubelio-demo-connector`.

---

### Task 1: Module `beeloft/jubelio_demo.py` (Dataset Sintetis, Skenario & Concurrency Lock)

**Files:**
- Create: `beeloft/jubelio_demo.py`
- Test: `tests/test_jubelio_demo.py`

**Interfaces:**
- Produces:
  - `JubelioDemoDataset.generate_baseline()`: `dict` berisi `orders`, `items` (stock), `returns`, `listings`
  - `JubelioDemoDataset.generate_scenario_2()`: `dict` berisi `orders` (145 total), `items` (stock updated), `returns`, `listings`
  - `JubelioDemoManager(store)`:
    - `ensure_table(db)`
    - `is_demo_database()` -> `bool`
    - `get_status()` -> `dict`
    - `activate(actor, key)` -> `dict`
    - `sync_current(actor, key)` -> `dict`
    - `next_scenario(actor, key)` -> `dict`
    - `reset_scenarios(actor, key)` -> `dict`

- [ ] **Langkah 1: Tulis tes unit untuk dataset deterministik dan kelengkapan snapshot**
  Buat `tests/test_jubelio_demo.py` untuk menguji konsistensi matematika dataset (jumlah revenue minor baris order = total order, total unit per kanal, status valid, format UTC).

- [ ] **Langkah 2: Jalankan tes unit dan pastikan gagal**
  Jalankan `python -m unittest tests/test_jubelio_demo.py -v` (harus gagal: `No module named 'beeloft.jubelio_demo'`).

- [ ] **Langkah 3: Implementasikan `beeloft/jubelio_demo.py`**
  Implementasikan dataset 30 SKU pakaian anak (Luna, Milo, Kiko, Caca, Bimo), 28 mapped, 2 unmapped; baseline 120 order; skenario 2 dengan 145 order kumulatif; database locking pada tabel `jubelio_demo_state`.

- [ ] **Langkah 4: Jalankan tes unit dan pastikan lulus**
  Jalankan `python -m unittest tests/test_jubelio_demo.py -v` (harus lulus).

- [ ] **Langkah 5: Commit perubahan Task 1**
  `git add beeloft/jubelio_demo.py tests/test_jubelio_demo.py`
  `git commit -m "feat(jubelio-demo): implement synthetic dataset, scenario engine, and db lock"`

---

### Task 2: Integrasi Store & CLI Demo Seed

**Files:**
- Modify: `beeloft/store.py`
- Modify: `beeloft/__main__.py`
- Test: `tests/test_jubelio_demo.py`

**Interfaces:**
- Consumes: `JubelioDemoManager` dari Task 1
- Produces:
  - `Store.jubelio_demo_status()`
  - `Store.jubelio_demo_activate(actor, key)`
  - `Store.jubelio_demo_sync(actor, key)`
  - `Store.jubelio_demo_next_scenario(actor, key)`
  - `Store.jubelio_demo_reset(actor, key)`
  - `python -m beeloft demo`: otomatis menyuntikkan aktivasi Jubelio Demo dan baseline snapshot.

- [ ] **Langkah 1: Tambahkan tes integrasi untuk pemanggilan Store dan CLI demo**
  Tambahkan pengujian pemanggilan Store method dan penolakan pada database non-demo di `tests/test_jubelio_demo.py`.

- [ ] **Langkah 2: Jalankan tes dan pastikan gagal**
  Jalankan `python -m unittest tests/test_jubelio_demo.py -v` (gagal pada method Store yang belum ada).

- [ ] **Langkah 3: Tambahkan method delegasi di `Store` dan perbarui `beeloft/__main__.py`**
  Hubungkan `Store` dengan `JubelioDemoManager` dan lengkapi perintah `demo` di CLI agar menginisialisasi database demo dengan state siap pakai.

- [ ] **Langkah 4: Jalankan tes dan pastikan lulus**
  Jalankan `python -m unittest tests/test_jubelio_demo.py -v` (harus lulus).

- [ ] **Langkah 5: Commit perubahan Task 2**
  `git add beeloft/store.py beeloft/__main__.py tests/test_jubelio_demo.py`
  `git commit -m "feat(jubelio-demo): wire demo methods in Store and enhance CLI demo command"`

---

### Task 3: Model Pydantic & Endpoint API Demo

**Files:**
- Modify: `beeloft/models.py`
- Modify: `beeloft/api.py`
- Test: `tests/test_jubelio_demo.py`

**Interfaces:**
- Produces:
  - `GET /api/integrations/jubelio/demo/status`
  - `POST /api/integrations/jubelio/demo/activate`
  - `POST /api/integrations/jubelio/demo/sync`
  - `POST /api/integrations/jubelio/demo/next-scenario`
  - `POST /api/integrations/jubelio/demo/reset`

- [ ] **Langkah 1: Tambahkan tes API untuk endpoint demo**
  Uji response code (200, 400 non-demo, 403 non-admin pada POST, 409 lock concurrency).

- [ ] **Langkah 2: Jalankan tes dan pastikan gagal**
  Jalankan `python -m unittest tests/test_jubelio_demo.py -v`.

- [ ] **Langkah 3: Definisikan model dan daftarkan endpoint di `beeloft/api.py`**
  Tambahkan route `/api/integrations/jubelio/demo/*` dengan guard role `admin` pada mutasi dan `Idempotency-Key` (RequestKey).

- [ ] **Langkah 4: Jalankan tes dan pastikan seluruh tes API lulus**
  Jalankan `python -m unittest tests/test_jubelio_demo.py -v`.

- [ ] **Langkah 5: Commit perubahan Task 3**
  `git add beeloft/models.py beeloft/api.py tests/test_jubelio_demo.py`
  `git commit -m "feat(jubelio-demo): expose demo control endpoints with admin authorization"`

---

### Task 4: Antarmuka Pengguna di `beeloft/static/app.mjs`

**Files:**
- Modify: `beeloft/static/app.mjs`
- Test: `tests/test_apple27_ai_integrations_workspace_contract.py`

**Interfaces:**
- Tampilan:
  - Badge `Jubelio Demo · Simulasi` pada kartu integrasi Jubelio
  - Panel kontrol demo: status aktif, indikator skenario, tombol "Sinkronkan sekarang", "Jalankan skenario berikutnya", "Reset skenario"
  - Otomatis memperbarui data integrasi dan invalidasi cache Command Center saat sinkronisasi tuntas.

- [ ] **Langkah 1: Tambahkan pemeriksaan kontrak frontend di tes Python**
  Pastikan kontrak UI memuat elemen kontrol demo Jubelio.

- [ ] **Langkah 2: Implementasikan kontrol UI di `app.mjs`**
  Modifikasi fungsi `integrationSystem` dan handler aksi untuk menyajikan kontrol demo Jubelio saat terdeteksi mode demo.

- [ ] **Langkah 3: Jalankan tes kontrak frontend**
  Jalankan `python -m unittest tests/test_apple27_ai_integrations_workspace_contract.py -v`.

- [ ] **Langkah 4: Commit perubahan Task 4**
  `git add beeloft/static/app.mjs tests/test_apple27_ai_integrations_workspace_contract.py`
  `git commit -m "feat(jubelio-demo): add Jubelio Demo badge and manual sync controls in UI"`

---

### Task 5: Pengujian Browser Acceptance Playwright

**Files:**
- Create: `tests/browser_jubelio_demo.cjs`
- Modify: `tests/run_browser.py`

- [ ] **Langkah 1: Tulis skenario pengujian browser lengkap**
  Uji alur browser:
  1. Login Admin Demo
  2. Buka Integrasi -> badge terlihat -> klik "Sinkronkan sekarang" (Skenario 1)
  3. Buka Command Center -> verifikasi performa marketplace dan angka penjualan terisi
  4. Buka dialog detail order dan rekonsiliasi stok
  5. Buka Master SKU -> petakan SKU karantina
  6. Kembali ke Integrasi -> klik "Sinkronkan sekarang" -> karantina terselesaikan
  7. Klik "Jalankan skenario berikutnya" -> skenario 2 termuat tanpa duplikasi.

- [ ] **Langkah 2: Jalankan modul browser test**
  Jalankan `node tests/run_browser.py` atau node runner Playwright yang sesuai.

- [ ] **Langkah 3: Commit perubahan Task 5**
  `git add tests/browser_jubelio_demo.cjs tests/run_browser.py`
  `git commit -m "test(jubelio-demo): add browser acceptance test for full demo workflow"`

---

### Task 6: OpenAPI, README Test Count, Dokumentasi & Finalisasi

**Files:**
- Modify: `docs/openapi.json`
- Modify: `README.md`
- Create: `docs/jubelio-demo-guide.md`

- [ ] **Langkah 1: Regenerasi OpenAPI**
  Jalankan `python scripts/regenerate_openapi.py` dan verifikasi `tests/test_openapi_contract.py`.

- [ ] **Langkah 2: Sinkronkan jumlah tes di `README.md`**
  Jalankan `python -m unittest tests/test_readme_test_count.py -v` dan perbarui angka di README.

- [ ] **Langkah 3: Buat dokumentasi panduan demo**
  Tulis `docs/jubelio-demo-guide.md` yang memuat perintah aktivasi dan urutan presentasi 5 menit.

- [ ] **Langkah 4: Jalankan seluruh suite tes unit & integrasi**
  Jalankan `python -m unittest discover -s tests -v`.

- [ ] **Langkah 5: Commit dokumentasi dan finalisasi**
  `git add docs/ README.md`
  `git commit -m "docs(jubelio-demo): update openapi, readme test count, and add demo guide"`

- [ ] **Langkah 6: Push dan buat Pull Request**
  `git push -u origin feat/jubelio-demo-connector`
  `gh pr create --title "[Jubelio Demo] In-process simulation provider and UI controls" --body "..."`
