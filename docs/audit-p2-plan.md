# Perbaikan P2: kegagalan logout dan total approval di luar batas halaman

Rilis perbaikan. Tidak ada fitur produk baru, tidak ada connector vendor, dan tidak ada perubahan
schema database.

Baseline yang dipakai: `main` pada commit `14150c65a97e78b13febba7234bf553b2c78fa84`, aplikasi 0.84.0,
schema database 55. Baseline ini sudah memuat ketiga perbaikan P1 (Starlette 1.6.0, idempotency key
global dengan binding `X-Beeloft-Actor`, serta rework completion dan inspeksi ulang final QC). Working
tree bersih saat pekerjaan dimulai dan seluruh 389 test baseline hijau sebelum satu baris pun diubah.

Dua temuan yang dikerjakan:

* **P2-A** — logout gagal tetapi UI menampilkan layar login; reload kemudian membuka kembali akun
  sebelumnya.
* **P2-B** — total approval, nominal, dan jawaban AI salah ketika jumlah pending melebihi 500 item.

---

## 1. P2-A: logout harus mencerminkan status session yang sebenarnya

### Reproduksi

`beeloft/static/app.mjs` pada baseline:

```js
async function logout(revoke=true) {
  $('main').setAttribute('aria-busy','true');$('login-view').setAttribute('inert','');
  try{if(revoke&&user)await api.post('/api/session/logout',{});}catch{}
  finally{clearWorkspace();$('login-view').removeAttribute('inert');$('main').removeAttribute('aria-busy');}
}
```

`catch{}` menelan setiap kegagalan dan `finally` selalu menjalankan `clearWorkspace()`. Dijalankan di
Chromium melalui `tests/browser_logout_failure.cjs` pada baseline, dengan `POST /api/session/logout`
dijawab 503 sebelum mencapai server:

```
locator.waitFor: Timeout 30000ms exceeded.
  - waiting for locator('#session-warning') to be visible
    63 × locator resolved to hidden <div hidden="" role="alert" id="session-warning" …>
  at tests/browser_logout_failure.cjs:51
```

Tidak ada peringatan apa pun; halaman langsung menampilkan layar login. Padahal:

* `beeloft/api.py` hanya menghapus cookie pada jalur sukses — `response.delete_cookie(...)` berada
  setelah `store.revoke_browser_session(...)`, jadi kegagalan meninggalkan `beeloft_session` dan
  `beeloft_csrf` utuh;
* baris session di tabel `browser_sessions` tidak pernah dihapus;
* `restoreSession()` pada reload memanggil `/api/me` dengan `credentials:'same-origin'`, cookie yang
  masih hidup lolos autentikasi, dan `enterWorkspace()` membuka kembali akun sebelumnya.

### Akar masalah

UI menyamakan "permintaan logout selesai dijalankan" dengan "session sudah dicabut". Keduanya berbeda,
dan perbedaan itu tidak pernah diperiksa.

### Invarian

1. Ruang kerja hanya boleh ditutup bila pencabutan session terkonfirmasi.
2. Satu-satunya kegagalan yang membuktikan session sudah tidak aktif adalah 401. CSRF 403, 5xx,
   timeout, dan kegagalan jaringan tidak membuktikan apa pun.
3. Ketika hasil belum pasti, status session diperiksa langsung ke `/api/me` sebelum UI berubah.
4. Ketidakpastian tidak boleh menjadi jalan buntu permanen: server yang sudah mencabut lalu kehilangan
   responsnya harus tetap dikenali.
5. Browser offline tidak boleh dijanjikan sebagai "session sudah dicabut".
6. Draft transaksi yang belum pasti tetap tersimpan per akun beserta idempotency key-nya.

### Tabel keputusan

| Hasil `POST /api/session/logout` | Pemeriksaan `/api/me` | Keputusan UI |
|---|---|---|
| 200 | — | Logout terkonfirmasi, ruang kerja ditutup |
| 401 | — (401 sudah cukup) | Session memang mati, ruang kerja ditutup |
| 403 CSRF | 200 | **Gagal.** Ruang kerja dipertahankan dengan peringatan |
| 5xx | 200 | **Gagal.** Ruang kerja dipertahankan dengan peringatan |
| abort sebelum terkirim | 200 | **Gagal.** Ruang kerja dipertahankan dengan peringatan |
| respons dijatuhkan setelah server mencabut | 401 | Logout terkonfirmasi, ruang kerja ditutup |
| jaringan mati seluruhnya | tidak dapat dijangkau | **Belum terkonfirmasi.** Ruang kerja dipertahankan |

Sisi server dari tabel ini ditegakkan `tests/test_session_logout.py`: 403 CSRF membiarkan session tetap
dapat membaca dan menulis, session yang sudah dicabut maupun kedaluwarsa menjawab 401, `revoke` dua kali
aman, dan logout satu perangkat tidak menyentuh session perangkat lain.

### Bentuk perbaikan

`logout()` sekarang mengembalikan boolean dan hanya memanggil `clearWorkspace()` ketika pencabutan
terkonfirmasi. Pemeriksaannya mempertahankan identitas, bukan sekadar fakta bahwa `/api/me` menjawab,
karena cookie session dipakai bersama seluruh tab dan dapat sudah ditukar akun lain:

```js
async function sessionIdentity() {
  try { return {state:'active', user: await api.get('/api/me')}; }
  catch (error) { return {state: error.status === 401 ? 'inactive' : 'unknown'}; }
}
```

Hanya `inactive` yang mengizinkan penutupan ruang kerja sebagai logout yang berhasil. Pada `active`,
yang menentukan langkah berikutnya adalah `user.id`: bila cocok dengan akun yang membuka ruang kerja,
ruang kerja dipertahankan dengan peringatan; bila berbeda, ruang kerja lama dibongkar karena
tampilannya akan bercampur identitas.

Perubahan UI dipilih yang paling kecil dan konsisten dengan aplikasi: satu banner `#session-warning`
(`role="alert"`) di dalam `<main>` bersama tombol **Coba keluar lagi**. Banner memakai token
`--warning`, `--warning-bg`, dan `--warning-edge` yang sudah ada, sengaja tidak otomatis hilang, dan
dibersihkan `clearWorkspace()` serta `enterWorkspace()` sehingga tidak pernah tertinggal setelah status
session kembali diketahui. Pesannya membedakan tiga keadaan — gagal dengan akun yang sama, session
sudah berpindah akun, dan belum terkonfirmasi — dan tidak pernah menyatakan pengguna sudah keluar.
Tombol coba lagi disembunyikan pada keadaan berpindah akun, sebab mencabut session akun lain bukan
langkah berikutnya yang benar.

Tombol **Masuk ulang** pada dialog transaksi pending hidup di dalam `<dialog>` modal, sehingga banner di
belakangnya tidak dapat dibaca maupun ditekan. Karena itu kedua tombol tersebut (`#reauth` dan
`#ai-reauth`) memanggil `reauthenticate(target)` yang meneruskan kegagalan ke `#form-error` atau
`#ai-message`, yaitu tempat yang sedang dilihat pengguna. Tombol tetap dapat dipakai: pada logout yang
berhasil alurnya sama seperti sebelumnya.

Perlombaan dijaga dua lapis: `logoutRequest` menyimpan satu promise dalam penerbangan sehingga klik
ganda memakai ulang permintaan yang sama, dan `$('logout')` serta `$('session-retry')` dinonaktifkan
secara sinkron sebelum `await` pertama. `aria-busy`, `inert`, dan `disabled` dipulihkan pada `finally`
untuk semua jalur. Penjaga generasi `epoch` yang sudah ada dipakai agar respons logout yang terlambat
tidak menimpa konteks login yang lebih baru.

### Yang dipertahankan

* `clearWorkspace()` tetap tidak menyentuh `sessionStorage`; tidak ada `sessionStorage.clear()` dan
  tidak ada idempotency key yang dibuang.
* `logout(false)` dari jalur 401 (`fail()`) tetap menutup ruang kerja secara sinkron seperti sebelumnya.
* `client.mjs` tidak diubah, jadi logout tetap tidak membawa `Idempotency-Key` maupun
  `X-Beeloft-Actor` — invarian yang diuji `tests/test_client.mjs`.
* CSRF, autentikasi, dan role guard tidak dilemahkan; tidak ada endpoint server yang diubah.
* Logout tetap hanya menyangkut session Beeloft. Tidak ada global logout ke penyedia SSO.

---

## 2. P2-B: total approval tidak boleh bergantung pada halaman daftar

### Reproduksi

`Store.approvals()` mengembalikan `items[offset:offset+limit]`, sebuah *halaman*, tanpa total. Dua
konsumen menyusun total global dari halaman itu:

```python
# beeloft/command_center.py
approvals = store.approvals(limit=500, status="pending")
approval_amount = sum((Decimal(row["amount"]) for row in approvals if row.get("amount")), Decimal())
... "pending_count": len(approvals)

# beeloft/brain.py
rows=store.approvals(500,0,'pending','all')
answer=f"Ada {len(rows)} item menunggu keputusan dengan total nominal tercatat Rp{format(amount,'.2f')}."
```

Karena `items.sort(..., reverse=True)`, halaman itu adalah 500 item **terbaru**; sisanya hilang dari
setiap total. Dengan 610 pengajuan pending bernilai Rp1.000,00 masing-masing:

| Sumber | Baseline | Kebenaran fixture |
|---|---|---|
| `/api/command-center` `pending_count` / `pending_amount` | 500 / `500000.00` | 610 / `610000.00` |
| Kartu perhatian "Keputusan menunggu" | `500 pengajuan senilai Rp500000.00 …` | `610 pengajuan senilai Rp610000.00 …` |
| Jawaban AI intent `approvals` | `Ada 500 item menunggu keputusan …` | `Ada 610 item …` |
| Jawaban overview | mewarisi angka yang sama | idem |

Pada populasi campuran, nominalnya bisa salah lebih jauh lagi. Dengan 500 marketing budget bernominal
dan 110 cuti tanpa nominal, baseline menjawab `Ada 500 item menunggu keputusan dengan total nominal
tercatat Rp390000.00` — 110 item terpotong dari count **dan** 110 item bernominal terpotong dari amount.

### Akar masalah

Tidak ada sumber agregat. Definisi "pending" dan penjumlahan nominal disusun ulang oleh setiap konsumen
di atas pembacaan daftar yang dipaginasi.

### Invarian

1. Ringkasan dibaca terpisah dari daftar dan tidak dipengaruhi `limit`/`offset`.
2. Satu pengajuan dihitung satu kali. Status berasal dari event terakhir yang sah; `submitted` di sumber
   berarti `pending` di inbox; `approved`, `rejected`, dan `cancelled` bukan pending.
3. Item tanpa nominal tetap dihitung pada count, tetapi tidak menambah amount.
4. Uang dihitung eksak dan tidak pernah bergantung pada batas integer database: nilai `*_minor`
   diproyeksikan lalu diakumulasi dengan integer Python, dan hasilnya dinormalkan lewat `Decimal`.
   Tidak ada float, tidak ada `SUM`/`TOTAL` berbasis REAL, dan tidak ada `SUM` integer 64-bit yang
   dapat overflow.
5. Count dan amount dalam satu ringkasan berasal dari satu snapshot pembacaan database.
6. Seluruh sembilan kind yang didukung inbox tercakup.

### Desain

`Store.approvals_summary(status='pending', kind='all')` menjadi satu-satunya sumber angka ringkasan.
Definisi bersama diangkat ke konstanta modul di `beeloft/store.py`:

* `APPROVAL_KINDS` — sembilan kind inbox.
* `APPROVAL_EVENT_STATUS` — pemetaan status inbox ke status event (`pending` ↔ `submitted`). Pemetaan ini
  bijektif, jadi satu literal status cukup untuk memfilter agregat.
* `APPROVAL_AGGREGATES` — per kind: tabel sumber, tabel event, kolom relasi, ekspresi nominal dalam
  satuan minor, dan filter tambahan.

Agregasi dilakukan di database dengan proyeksi minimal. Tidak ada `history`, `context`, atau detail
pengajuan yang dihidrasi:

```sql
SELECT <ekspresi_nominal> AS amount
FROM <sumber> t
WHERE 1=1 AND (SELECT status FROM <events> WHERE <kolom>=t.id
               ORDER BY sequence DESC LIMIT 1)=?
```

Barisnya diiterasi secara streaming, lalu `count`, `with_amount`, dan akumulator nominal dihitung di
Python. Kind yang memang tidak punya nominal cukup memakai `SELECT COUNT(*)`. Penjumlahan sengaja
tidak diserahkan kepada `SUM()` SQLite: akumulatornya integer 64-bit dan dapat overflow untuk data
yang masih sah menurut schema — rinciannya di bagian 6.1 dokumen bukti.

Subquery berkorelasi pada event terakhir adalah pola yang sudah dipakai `purchase_requests()` dan
`marketing_budget_requests()`. Pola ini penting: seluruh tabel event bersifat append-only, sehingga
`COUNT(*)` yang di-*join* ke tabel event akan menggandakan pengajuan sebanyak jumlah event-nya.

Dua kind memerlukan penanganan khusus:

* `payroll_batch` — nominalnya turunan, `gross_pay_minor + employer_contributions_minor`, diambil lewat
  `JOIN mekari_payroll_snapshot_periods`.
* `ai_action` — nominalnya string `'.2f'` di dalam kolom JSON `action_payload`, bukan kolom `*_minor`.
  Nilainya diproyeksikan apa adanya lalu dijumlahkan dengan `Decimal` di Python. Alternatifnya adalah
  `CAST(... AS REAL)` di SQL, yang justru memasukkan pembulatan uang lewat float dan karena itu ditolak.
  Proyeksinya tetap satu kolom kecil per baris, tanpa hidrasi.

`production_change`, `workforce_leave`, dan `workforce_overtime` memang tidak punya nominal: keduanya
menyumbang count saja. Seluruh query berjalan dalam satu `self.transaction()`, jadi count dan amount
selalu berasal dari satu snapshot.

Bentuk kembalian:

```python
{'status':…, 'kind':…, 'currency':'IDR', 'total':int, 'amount':'0.00',
 'with_amount':int, 'without_amount':int,
 'by_kind':{kind:{'count':int,'amount':'0.00'}}}
```

### Kontrak API

* `GET /api/approvals` **tidak berubah**: tetap mengembalikan list, dengan pagination, filter, urutan,
  dan permission yang sama. Batas `limit` tetap 500 dan tidak diganti menjadi angka raksasa.
* `GET /api/approvals/summary` ditambahkan. Endpoint ringkasan ini memang diperlukan karena facts AI
  mengutip sumbernya kepada pengguna: menunjuk `/api/approvals?status=pending` untuk sebuah angka
  agregat akan mengesankan satu halaman terbatas sebagai seluruh data. Filter `status` dan `kind`
  memakai literal yang sama dengan daftar (`ApprovalStatus`, `ApprovalKind`), dan permission-nya sama,
  yaitu setiap aktor terautentikasi termasuk viewer.
* `/api/command-center` mendapat satu field tambahan yang bersifat additive,
  `approvals.pending_without_amount`, untuk menjelaskan mengapa count dapat melebihi jumlah item
  bernominal.
* `approvals.by_kind` **dipertahankan bentuknya**, yaitu `{kind: int}` dengan enam kunci yang sama.
  Hitungannya kini benar untuk populasi di atas 500, tetapi daftar kunci tidak diperluas.

### Evidence AI

`brain._approvals()` membaca ringkasan untuk angka dan daftar hanya sebanyak contoh yang ditampilkan
(`APPROVAL_SAMPLE = 10`, sebelumnya mengambil 500 baris lalu memotongnya menjadi 10). Evidence memisahkan
populasi dari sampel secara eksplisit:

```python
{'approvals': {'summary': summary, 'sample': rows,
               'sample_size': len(rows), 'truncated': total > len(rows)}}
```

Ringkasan yang mendasari jawaban ikut tersimpan di snapshot investigasi, jadi jawaban tetap dapat
diaudit. Findings dan recommendations tetap dibatasi 10 dan tetap merujuk `/api/approvals?status=pending`
karena isinya memang item daftar. Rekomendasi tetap `approval_required: true` dan `executable: false`.
Investigasi yang sudah tersimpan tidak diubah secara retroaktif: `result_snapshot` dibaca apa adanya dan
tidak pernah dihitung ulang.

---

## 3. Batas perubahan

Tidak dikerjakan, dan tetap terbuka sebagai P3:

* **Breakdown approval belum mencakup cuti, lembur, dan payroll.** `approvals.by_kind` sengaja tetap
  berisi enam kunci, jadi `sum(by_kind.values())` masih dapat lebih kecil daripada `pending_count`.
  Agregat baru sudah menyediakan sembilan kind pada `by_kind` miliknya sendiri dan pada
  `/api/approvals/summary`, sehingga data untuk memperbaiki breakdown kini tersedia — tetapi UI dan
  bentuk field Command Center tidak diubah.
* **Tanggal ekstrem menyebabkan HTTP 500.** Tidak disentuh.
* **Logout dengan API key tanpa cookie menyebabkan HTTP 500.** `api.py` masih mengindeks
  `request.cookies['beeloft_session']` tanpa penjagaan. Perbaikan P2-A tidak menyembunyikan hal ini:
  500 dari endpoint logout kini justru dilaporkan apa adanya sebagai "logout belum berhasil", bukan
  disamarkan sebagai layar login. Perilaku server tidak diubah.

Tidak ada refactor authentication maupun analytics. Tidak ada abstraction baru di luar satu metode
Store, tiga konstanta definisi bersama, satu endpoint ringkasan, satu banner, dan satu helper
`reauthenticate`.

Schema database tidak berubah, sehingga `PRAGMA user_version` tetap 55 dan tidak ada migrasi baru.
Versi aplikasi dinaikkan 0.84.0 → 0.85.0 karena kontrak API bertambah, dan `docs/openapi.json`
diregenerasi.

Bukti: [audit P2 verification](audit-p2-verification.md).
