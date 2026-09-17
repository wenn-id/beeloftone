# Perbaikan P3: rincian kategori approval, batas aritmetika tanggal, dan logout tanpa cookie

Tiga temuan P3 terakhir dari audit awal. Ketiganya berdiri sendiri dan tidak menuntut perubahan
schema, framework, integrasi, maupun ulang rancang UI.

Baseline yang diperiksa: `main` pada `c77248bedd788744bd6ee6776d40bf4bc33dce79` (PR #6 sudah merged,
CI hijau sesudah merge). `main` lokal identik dengan `origin/main` pada SHA tersebut setelah
`git fetch`, jadi tidak ada perubahan baru yang perlu diikutkan. Pekerjaan berjalan di branch
`fix/audit-p3-approval-breakdown-date-logout` yang dibuat dari SHA itu; branch PR #6 tidak
dilanjutkan.

| Temuan | Ringkas | Berkas inti |
| --- | --- | --- |
| P3-A | `approvals.by_kind` Command Center hanya memuat enam dari sembilan kategori | `beeloft/command_center.py` |
| P3-B | Tanggal ekstrem yang lolos validasi membuat perhitungan periode gagal dan dijawab HTTP 500 | `beeloft/store.py` |
| P3-C | Logout dengan API key tanpa cookie session dijawab HTTP 500 | `beeloft/api.py` |

Seluruh pengujian memakai database disposable (`tempfile`). Tidak ada demo, migrasi percobaan,
fixture, penghapusan database, atau pembuatan ulang akun pada database bisnis.

## 1. P3-A: rincian kategori approval harus lengkap

### Reproduksi

Command Center sudah membaca agregat, bukan halaman daftar — perbaikan P2 itu tetap berlaku. Yang
salah hanya rinciannya (`beeloft/command_center.py:224` pada baseline):

```python
"by_kind": {kind: approval_kinds[kind]["count"] for kind in (
    "purchase_request", "purchase_order", "supplier_payment", "marketing_budget",
    "production_change", "ai_action")},
```

`store.approvals_summary()` mengenal sembilan kind dan selalu mengisi kesembilanya, tetapi rincian
di atas memilih enam dengan tangan. Dengan fixture berisi 3 marketing + 5 cuti + 4 lembur +
2 payroll, baseline melaporkan:

```
store approvals_summary by_kind keys (9)
command center by_kind keys       (6)   hilang: payroll_batch, workforce_leave, workforce_overtime
pending_count                     14
sum(by_kind.values())              3
```

Akibatnya `pending_count` menghitung 14 sementara rinciannya hanya menjelaskan 3; sebelas pengajuan
People dan payroll tidak pernah terlihat pada rincian, dan jumlah rincian tidak dapat direkonsiliasi
dengan totalnya.

### Akar masalah

Daftar kategori ditulis tetap di lapisan penyajian, terpisah dari `APPROVAL_KINDS` yang menjadi
sumber kebenaran. Setiap kind baru harus diingat dua kali, dan yang terlupa gagal tanpa suara.

### Invarian

* Rinciannya menurunkan kategorinya dari `APPROVAL_KINDS`, bukan dari daftar tetap.
* Untuk scope pending yang sama: `sum(by_kind.values()) == pending_count`.
* Kategori tanpa pengajuan pending tetap hadir bernilai `0`.
* Enam kunci lama beserta tipe nilainya (`int`) tidak berubah.
* Sumbernya tetap `approvals_summary()`; tidak ada definisi pending kedua dan tidak ada pembacaan
  ulang dari halaman daftar approval.
* `pending_amount` dan semantik nominal per kind tidak disentuh. Cuti dan lembur yang tidak punya
  nominal tetap dihitung dalam jumlah.
* `GET /api/approvals` tetap mengembalikan list, bukan object.

### Bentuk perbaikan

Satu perubahan additive di `beeloft/command_center.py`:

```python
"by_kind": {kind: approval_kinds[kind]["count"] for kind in APPROVAL_KINDS},
```

### Konsumen rincian

Ditelusuri seluruhnya sebelum memilih bentuk perbaikan:

| Konsumen | Keadaan | Tindakan |
| --- | --- | --- |
| `beeloft/static/app.mjs` | **Tidak pernah membaca `by_kind`.** Command Center hanya menampilkan `pending_count` pada strip operasi (`app.mjs:405`). `grep -rn "by_kind" beeloft/static/` kosong. | Tidak ada perubahan UI |
| Label kategori di UI | `approvalKind` (`app.mjs:4014`) sudah memuat label Bahasa Indonesia untuk kesembilan kind, begitu pula `<option>` filter "Jenis approval" pada inbox | Tidak ada perubahan |
| Drill-down kategori → inbox | **Tidak ada.** `approvalsDialog()` tidak menerima argumen dan selalu membuka filter `kind=all` | Tidak ditambahkan: panel atau navigasi baru di luar cakupan |
| `beeloft/brain.py:113` (facts AI) | Sudah melakukan iterasi seluruh kunci `summary['by_kind']`, jadi pemetaan kategorinya memang lengkap | Tidak ada perubahan; ditambah tes penjaga |
| Kartu perhatian Command Center | Memakai `approvals["total"]` dan `approvals["amount"]` | Tidak ada perubahan |
| Laporan/ekspor | `beeloft/reports.py` hanya CSV aktivitas | Tidak terkait |

Karena rinciannya belum punya permukaan UI, perbaikannya murni pada kontrak payload
`GET /api/command-center`. Menambahkan panel kategori baru akan menjadi penambahan UI yang tidak
diminta, jadi tidak dilakukan.

## 2. P3-B: aritmetika tanggal tidak boleh menjadi HTTP 500

### Reproduksi

Titik awal yang dilaporkan, `Store.production_quality_insights()`, menurunkan tiga tanggal:

```python
current_start=as_of_date-timedelta(days=window_days-1)
previous_end=current_start-timedelta(days=1)
previous_start=previous_end-timedelta(days=window_days-1)
```

`datetime.date` hanya mewakili 0001-01-01 sampai 9999-12-31, jadi `as_of=0001-01-01` sudah keluar
dari kalender bahkan dengan `window_days` terkecil yang diizinkan. `timedelta` menjawabnya dengan
`OverflowError: date value out of range`; `beeloft/api.py` tidak punya handler untuk itu, sehingga
kegagalannya sampai ke klien sebagai HTTP 500.

Masalahnya bukan satu fungsi. Setiap laporan memakai pola yang sama, jadi pemeriksaan pada satu
tempat tidak menyelesaikannya. Terdampak pada baseline (semuanya HTTP 500):

| Endpoint | Parameter | Input pemicu | Baseline | Diharapkan |
| --- | --- | --- | --- | --- |
| `GET /api/demand-forecast` | `as_of`, `window_days` | `as_of=0001-01-01` | 500 | 422 |
| `GET /api/return-insights` | `as_of`, `window_days` | `as_of=0001-01-01` | 500 | 422 |
| `GET /api/size-demand-insights` | `as_of`, `window_days` | `as_of=0001-01-01` | 500 | 422 |
| `GET /api/dead-stock-insights` | `as_of`, `inactivity_days` | `as_of=0001-01-01` | 500 | 422 |
| `GET /api/stock-adjustment-insights` | `as_of`, `window_days` | `as_of=0001-01-01` | 500 | 422 |
| `GET /api/supplier-performance-insights` | `as_of`, `window_days` | `as_of=0001-01-01` | 500 | 422 |
| `GET /api/material-price-insights` | `as_of`, `window_days` | `as_of=0001-01-01` | 500 | 422 |
| `GET /api/production-quality-insights` | `as_of`, `window_days` | `as_of=0001-01-01` | 500 | 422 |
| `GET /api/purchase-commitment-insights` | `as_of`, `due_soon_days` | `as_of=9999-12-31` | 500 | 422 |
| `GET /api/capacity-plan` | `as_of`, `horizon_days` | `as_of=9999-12-31` | 500 | 422 |
| `GET /api/capacity-plan` (loop hari) | `as_of`, `horizon_days` | `as_of=9999-12-31&horizon_days=1` dengan work center ada | 500 | 200 |
| `GET /api/replenishment-recommendations` | `as_of`, `lead_time_days`, `review_period_days`, `safety_stock_days`, `window_days` | `as_of=0001-01-01` atau `9999-12-31` | 500 | 422 |
| `POST /api/ai/investigate` | `as_of` di body | `as_of=0001-01-01` | 500 | 422 |
| `POST /api/ai/investigations` | `as_of` di body | `as_of=0001-01-01` | 500 | 422 |
| `POST /api/ai/action-proposals` | `as_of` di body | `as_of=0001-01-01` | 500 | 422 |

Dua kasus perlu dicatat khusus:

* **Loop hari `capacity_plan`.** Bentuk `while cursor<=horizon_end` yang diakhiri
  `cursor+=timedelta(days=1)` selalu menambah sekali lagi setelah hari terakhir diproses, hanya
  untuk mengevaluasi syarat berhenti. Horizon yang berakhir tepat pada 9999-12-31 karena itu keluar
  dari kalender walaupun seluruh harinya sah. Ini baru terlihat bila ada work center; tanpa data
  loop-nya tidak pernah berjalan, sehingga reproduksinya menuntut fixture work center.
* **Proyeksi habis stok.** `size_demand_insights` dan `replenishment_recommendations` memproyeksikan
  `projected_stockout_date` dari stok dibagi laju permintaan. Jarak harinya berasal dari data, bukan
  dari parameter permintaan, jadi stok besar dengan laju sangat kecil dapat memproyeksikan ribuan
  tahun ke depan dan meledak untuk `as_of` apa pun.

Yang **tidak** terdampak, diperiksa dan dikonfirmasi:

* `GET /api/wip-ageing-insights` — `idle_days` tidak dipakai untuk aritmetika tanggal; 200 pada
  kedua ujung kalender.
* `Store.audit_events()` dan `Store.activity()` sudah punya `except (OverflowError, ValueError)`
  dan menjawab 422. Keduanya menjadi preseden bentuk perbaikan ini.
* `capacity_calendar()` dan `attendance_records()` hanya membandingkan urutan tanggal.

### Akar masalah

Validasi parameter hanya memastikan setiap nilai sah sendiri-sendiri: `as_of` dapat diparse sebagai
tanggal, dan lebar periode berada di dalam batas `ge`/`le`. Yang tidak diperiksa adalah apakah
periode yang diturunkan dari kombinasi keduanya masih ada di kalender.

### Kontrak

* Tanggal dan rentang yang seluruh periodenya dapat dihitung tetap diterima, termasuk 0001-01-01 dan
  9999-12-31 sendiri.
* Kombinasi yang menunjuk ke luar kalender ditolak `422` dengan pesan Bahasa Indonesia yang menyebut
  parameter yang bersangkutan.
* Tidak ada batas tahun buatan seperti 1900–2100; yang ditolak adalah kombinasinya, bukan tanggalnya.
* Tidak ada penggantian tanggal diam-diam, pemangkasan window, atau laporan kosong yang berpura-pura
  berhasil.
* Tidak ada `except Exception`/`except OverflowError` global. Penangkapan berada tepat di sekitar
  satu operasi tanggal dan hanya untuk `OverflowError`, sehingga kesalahan perhitungan lain —
  termasuk perhitungan nominal — tetap muncul sebagai bug.
* Jalur HTTP maupun jalur internal (investigasi AI dan proposal tindakan yang memanggil fungsi
  laporan yang sama) terlindungi, karena pemeriksaannya ada di store.
* Zona operasional Jakarta dan batas periode existing dipertahankan.

### Bentuk perbaikan

Dua helper kecil di `beeloft/store.py`, dipakai di titik operasi tanggalnya:

```python
def shift_date(anchor, days, parameters):   # 422 bila hasilnya tidak ada di kalender
def projected_date(anchor, days):           # None bila proyeksi dari data melampaui kalender
```

`shift_date` untuk batas periode yang diturunkan dari parameter permintaan (14 pemanggilan).
`projected_date` untuk proyeksi yang jarak harinya berasal dari data (2 pemanggilan): permintaannya
sah, jadi jawaban yang benar adalah "tidak ada tanggal habis stok yang terwakili" — nilai `None`
yang sama seperti produk tanpa laju permintaan, yang memang sudah menjadi nilai sah pada kedua
laporan itu.

Loop hari `capacity_plan` diubah menjadi iterasi ordinal
(`range(as_of_date.toordinal(), horizon_end.toordinal()+1)`) sehingga berhenti tanpa pernah
menghitung tanggal di luar horizon. Urutan dan isi harinya tidak berubah.

### Batas aman per endpoint

Batas aman adalah jarak dari `as_of` ke tepi periode terjauh yang dihitung endpoint tersebut.
Nilainya dipakai sebagai tabel uji dan dibuktikan oleh tesnya sendiri: bila jaraknya salah, tanggal
"batas aman" akan ikut ditolak dan tesnya gagal.

| Endpoint | Jarak dari `as_of` | Contoh batas aman |
| --- | --- | --- |
| `demand-forecast`, `size-demand-insights` | `2*window_days - 1` ke belakang | `window_days=7` → `0001-01-14` |
| `production-quality-insights` | `2*window_days - 1` ke belakang | `window_days=7` → `0001-01-14` |
| `return-insights`, `stock-adjustment-insights`, `supplier-performance-insights`, `material-price-insights` | `window_days - 1` ke belakang | `window_days=7` → `0001-01-07` |
| `dead-stock-insights` | `inactivity_days - 1` ke belakang | `inactivity_days=7` → `0001-01-07` |
| `purchase-commitment-insights` | `due_soon_days` ke depan | `due_soon_days=1` → `9999-12-30` |
| `capacity-plan` | `horizon_days - 1` ke depan | `horizon_days=1` → `9999-12-31` |
| `replenishment-recommendations` | `lead_time_days + review_period_days + safety_stock_days` ke depan, dan `2*window_days - 1` ke belakang | lead 1 + review 1 + safety 0 → `9999-12-29` |

## 3. P3-C: logout tanpa cookie session

### Reproduksi

Baseline `beeloft/api.py:168`:

```python
store.revoke_browser_session(request.cookies['beeloft_session'])
```

`actor()` meloloskan request yang membawa `X-API-Key` tanpa memeriksa cookie apa pun, jadi akses
dictionary itu tidak aman:

```
POST /api/session/logout  (X-API-Key sah, tanpa cookie)  -> 500  KeyError: 'beeloft_session'
POST /api/session/logout  (tanpa kredensial)             -> 401  (benar)
```

Selain 500 tersebut, reproduksi menemukan perilaku kedua yang lebih serius: request ber-API-key yang
**membawa cookie akun lain** mencabut session browser akun tersebut. Jalur API key tidak melewati
pemeriksaan CSRF, sehingga pencabutan itu terjadi tanpa bukti kepemilikan token CSRF sama sekali.

### Akar masalah

Endpoint mengasumsikan cookie selalu ada karena request sudah ter-autentikasi, padahal autentikasi
bersama punya dua jalur dan hanya satu di antaranya membawa cookie. Endpoint juga mencabut *cookie
apa pun yang terkirim*, bukan session yang memberinya akses.

### Kontrak

Prioritas kredensial dinyatakan eksplisit: **`X-API-Key` tetap menang atas cookie** (tidak berubah
dari baseline), dan **satu-satunya session yang boleh dicabut logout adalah session yang
meng-autentikasi request itu.**

| Kredensial | Hasil | Efek pada session |
| --- | --- | --- |
| API key sah, tanpa cookie | `200 {"status":"signed_out"}` (no-op) | Tidak ada |
| API key sah, dengan cookie akun sama | `200 {"status":"signed_out"}` (no-op) | Cookie **tidak** dicabut: tidak ada bukti CSRF |
| API key sah, dengan cookie akun lain | `200 {"status":"signed_out"}` (no-op) | Session akun lain **tidak** dicabut |
| Cookie sah + CSRF benar | `200 {"status":"signed_out"}` | Session dicabut, kedua cookie dihapus |
| Cookie sah + CSRF salah/hilang | `403` | Tidak ada; session tetap hidup |
| Cookie kedaluwarsa/sudah dicabut | `401` | Tidak ada |
| API key tidak sah / akun nonaktif | `401` | Tidak ada |
| Tanpa kredensial | `401` | Tidak ada |
| Penyimpanan gagal saat mencabut | bukan `200` | Tidak ada; session tetap hidup |

Turunan yang ikut ditegakkan:

* Jawaban no-op **bukan** pencabutan API key. Kunci yang sama tetap sah untuk `/api/me` dan untuk
  menulis.
* Jalur no-op tidak mengirim `Set-Cookie` penghapus, karena tidak ada session yang diakhiri. Cookie
  browser yang masih hidup tidak boleh terputus dari session-nya di server.
* Tidak ada session lain yang dibuat atau dicabut sebagai efek samping.
* Kegagalan penyimpanan tidak ditangkap, sehingga logout yang gagal tidak pernah terlihat berhasil.
* Perubahan ini tidak melemahkan CSRF; ia justru menghapus satu jalur pencabutan yang sebelumnya
  melewatinya.

### Bentuk perbaikan

`actor()` mencatat kredensial yang dipakainya pada `request.state.browser_session` — token session
bila cookie itulah yang meng-autentikasi (dan karena itu sudah lewat pemeriksaan CSRF), `None` bila
API key. `close_session()` mencabut hanya token itu, dan menjawab no-op bila `None`.

Perbaikan ini tidak cukup dengan mengganti `[...]` menjadi `.get()`: itu akan membuat request
ber-API-key mencabut cookie yang menempel padanya tanpa CSRF, yaitu perilaku baseline yang justru
harus dihentikan.

Klien browser tidak terpengaruh. `beeloft/static/app.mjs` tidak pernah mengisi `api.key` (hanya
mengosongkannya pada `clearWorkspace`), jadi UI selalu memakai cookie dan tidak pernah mengirim
kedua kredensial sekaligus.

## 4. Batas perubahan

Yang **dipertahankan** dan diuji ulang: dependency keamanan StaticFiles; idempotency global dan
`X-Beeloft-Actor`; rework completion, inspeksi ulang, dan konservasi kuantitas; logout gagal/tidak
pasti serta pemulihan draft per akun; penanganan pergantian identitas session; agregat approval
lengkap dengan nominal eksak tanpa overflow SUM SQLite; kompatibilitas evidence investigasi AI
historis.

Yang **tidak** dikerjakan: redesign UI, framework baru, integrasi baru, refactor besar, panel
Command Center baru, dan perubahan schema. Schema database tetap versi 55 dan tidak ada migrasi.

Peningkatan CI di luar kebutuhan tes task ini dicatat terpisah pada
[bukti pengujian](audit-p3-verification.md), bukan dikerjakan di sini.
