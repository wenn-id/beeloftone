# Perbaikan P1: dependensi Starlette dan pengikatan idempotency key ke akun pencatat

Rilis stabilisasi. Tidak ada fitur produk baru dan tidak ada connector vendor.

## 1. Dependensi Starlette

### Temuan

Lock sebelumnya memakai `starlette==0.52.1`. Versi itu terkena lima advisory yang sudah diperbaiki di
rilis saat ini:

| Advisory | CVE | Ringkas | Diperbaiki di |
|---|---|---|---|
| GHSA-86qp-5c8j-p5mr | CVE-2026-48710 | BadHost: Host header tidak divalidasi sehingga `request.url.path` teracuni dan otorisasi berbasis path dapat dilewati | 1.0.1 |
| GHSA-wqp7-x3pw-xc5r | CVE-2026-48818 | SSRF dan kebocoran NTLMv2 melalui UNC path pada `StaticFiles` di Windows | 1.1.0 |
| GHSA-x746-7m8f-x49c | CVE-2026-48817 | Metode HTTP arbitrer dapat mencapai atribut `HTTPEndpoint` | 1.1.0 |
| GHSA-jp82-jpqv-5vv3 | CVE-2026-54282 | Path request yang tidak divalidasi ikut membentuk authority dan meracuni `request.url` | 1.3.0 |
| GHSA-82w8-qh3p-5jfq | CVE-2026-54283 | Limit `request.form()` diabaikan untuk `application/x-www-form-urlencoded` | 1.3.1 |

Advisory yang disebut dalam laporan (GHSA-wqp7-x3pw-xc5r) pertama kali ditutup di 1.1.0, tetapi 1.1.0
masih terkena CVE-2026-54282 dan CVE-2026-54283. Karena itu target upgrade bukan 1.1.0.

### Keputusan

- Lock dinaikkan ke `starlette==1.6.0`, rilis terbaru dan tanpa advisory terbuka.
- Batas deklaratif menjadi `starlette>=1.3.1,<2`, yaitu batas keamanan: seluruh rilis di bawah 1.3.1
  masih terkena setidaknya satu advisory di atas.
- Batas `fastapi` dinaikkan ke `>=0.134,<1`. FastAPI di bawah 0.133 memasang batas atas pada Starlette
  yang menolak 1.x, sehingga tanpa kenaikan ini constraint deklaratif tidak dapat diselesaikan.
- `uvicorn`, `PyJWT`, `qrcode`, `httpx`, dan seluruh dependensi transitif tidak diubah. Resolusi ulang
  pada Python 3.12 menghasilkan set yang identik kecuali Starlette.
- Aplikasi memakai `StaticFiles` pada `/static`, jadi komponen yang terkena CVE-2026-48818 memang
  dipakai di produk ini.

### Bentuk perbaikan di Starlette 1.x

`StaticFiles.lookup_path()` sekarang menolak path absolut lebih dahulu:

```python
if path.startswith(("/", "\\")):
    return "", None
```

Penolakan terjadi sebelum `os.path.join`, sebelum `os.path.realpath`, dan sebelum `os.stat`. Pada
0.52.1 penolakan baru terjadi pada pemeriksaan `os.path.commonpath`, yaitu setelah `realpath` sempat
me-resolve UNC path dan memicu koneksi SMB pada Windows.

### Bentuk pengujian regresi

Tes tidak boleh bergantung pada Windows dan tidak boleh membuat request SMB nyata. Karena guard
`startswith(("/", "\\"))` berlaku sama di semua platform, regresi dapat dibuktikan di Linux:

1. Request UNC-style ke `/static/...` ditolak dengan 404 dan tidak pernah 200.
2. `os.path.realpath`, `os.path.abspath`, dan `os.stat` diintip. Tidak satu pun boleh menerima
   argumen yang memuat authority penyerang. Ini yang membedakan versi rentan dari versi aman:
   pada 0.52.1 `realpath` menerima path tersebut, pada 1.6.0 tidak pernah.
3. `socket.getaddrinfo`, `socket.create_connection`, dan `socket.socket.connect` dipasangi guard yang
   gagal keras bila menyentuh host penyerang atau port 445. Guard ini membuktikan tidak ada I/O
   jaringan, sekaligus memastikan tes tidak pernah benar-benar menghubungi SMB.
4. Host uji memakai TLD `.invalid` (RFC 2606) sehingga tidak dapat resolve walau guard gagal.
5. Satu tes tambahan menegaskan batas versi Starlette terpasang, supaya penurunan lock kembali ke
   rilis yang terkena advisory langsung gagal di CI.

## 2. Retry transaksi tidak pasti lintas akun

### Reproduksi dan verdict

Alur yang diaudit: `api.transaction()` → `sessionStorage` → `readPending()` → `recover()` →
`formDialog()` → session browser lintas tab → `Store._write()` → tabel `requests`.

Urutan yang menghasilkan mutasi kedua:

1. Tab 1 masuk sebagai akun A dan mengirim write. Jaringan terputus setelah server commit, jadi
   klien menandai hasil `uncertain` dan menyimpan draft di
   `sessionStorage['beeloft.pending.<A>'] = {transaction:{path,body,key:K}, title, info}`.
   Dialog terkunci dengan tombol **Coba ulang penyimpanan**; `user` di memori tab 1 tetap A.
2. Tab 2 pada origin yang sama logout lalu login sebagai akun B. Cookie `beeloft_session` dan
   `beeloft_csrf` dipakai bersama seluruh tab, sedangkan `sessionStorage` bersifat per tab. Tab 1
   tidak pernah diberi tahu.
3. Tab 1 menekan Coba ulang. `client.mjs` membaca ulang cookie CSRF terbaru pada setiap request,
   sehingga retry dikirim memakai session B dengan `Idempotency-Key: K` dan payload A.
4. Server: `actor()` me-resolve B. `Store._write()` mencari receipt dengan
   `WHERE actor_id=? AND key=?`, tidak menemukan apa pun karena receipt milik A, lalu menjalankan
   `perform(db)` untuk kedua kalinya.

Hasilnya mutasi bisnis kedua, event audit kedua dengan `request_key` sama tetapi `actor_id` berbeda,
dan baris `requests` kedua. Tidak ada bentrok primary key karena PK-nya `(actor_id, key)`.

Jadi: **perilaku saat ini dapat menghasilkan mutasi kedua.** Satu-satunya penghalang adalah konvensi
klien, yaitu penamaan `sessionStorage` per user id, dan itu tidak mengikat server sama sekali.

### Invarian yang harus dijaga server

| # | Invarian |
|---|---|
| I1 | Satu idempotency key mengikat paling banyak satu transaksi logis pada seluruh database, bukan per akun. |
| I2 | Satu key menghasilkan paling banyak satu efek samping bisnis, apa pun akun yang mengirim retry. |
| I3 | Akun pencatat asli yang mengulang key dengan payload sama menerima respons pertama secara byte-identical, tanpa event audit baru. |
| I4 | Key sama dengan payload berbeda ditolak 409, tanpa mutasi. |
| I5 | Akun berbeda yang memakai key milik akun lain ditolak 403, tanpa mutasi, apa pun payload-nya. |
| I6 | Kegagalan yang membatalkan transaksi tidak meninggalkan receipt, sehingga key yang sama masih dapat dipakai untuk percobaan berikutnya. |
| I7 | Akun nonaktif ditolak 401 lebih dahulu, sebelum pemilikan key maupun payload diperiksa. |
| I8 | Atribusi audit tetap menunjuk akun yang benar-benar melakukan mutasi, dan replay tidak menambah atribusi baru. |

I5 memakai 403, bukan 409, dan itu disengaja. Klien sudah memperlakukan 401/403 sebagai `denied`:
draft dipertahankan, flag `unresolved` tetap menyala, dan tombol **Masuk ulang** muncul dengan pesan
"Masuk ulang dengan akun pencatat yang sama". Dengan 409 klien justru membuang draft, sehingga akun A
kehilangan jalur pemulihan yang sah. 403 juga tidak membocorkan respons A kepada B.

### Urutan pemeriksaan di `_write()`

Urutan menentukan status yang dikembalikan, jadi ditetapkan eksplisit:

1. Akun masih ada dan `active=1`, jika tidak 401. (I7)
2. Ambil receipt dengan `WHERE key=?`, tanpa filter akun.
3. Jika receipt ada dan `actor_id` berbeda dari akun sekarang, 403. (I5)
4. Role akun sekarang harus diizinkan, jika tidak 403.
5. Jika receipt ada dan fingerprint berbeda, 409. (I4)
6. Jika receipt ada, kembalikan respons tersimpan. (I3)
7. Jalankan `perform`, catat audit, simpan receipt, semuanya dalam satu transaksi. (I6, I8)

Langkah 4 tetap berada sebelum langkah 5 dan 6 supaya perilaku lama tidak berubah: akun asli yang
role-nya diturunkan tetap menerima 403 saat mengulang, bukan respons cache.

### Migrasi schema 53 → 54

Perbaikan perilaku sebenarnya bisa dilakukan hanya dengan mengubah query lookup. Migrasi tetap
dilakukan karena penyebab akarnya ada di schema: PK `(actor_id, key)` secara struktural mengizinkan
satu key hidup sekali per akun. Repositori ini menegakkan aturan bisnis di database, jadi invarian
keamanan tidak sepantasnya hanya dijaga di Python.

Bentuk migrasi `beeloft/request_keys.sql`:

1. Buat `request_key_conflicts`, tabel immutable untuk menyimpan receipt duplikat historis beserta
   waktu deteksi. Tidak ada data yang dibuang tanpa jejak.
2. Buat tabel `requests` baru dengan `key TEXT NOT NULL PRIMARY KEY` dan `actor_id` sebagai kolom
   biasa yang tetap ber-foreign key ke `users(id)`.
3. Pindahkan satu receipt per key, yaitu yang paling awal menurut `created_at` lalu `rowid`. Receipt
   paling awal adalah transaksi yang benar-benar mengoriginasi key tersebut.
4. Salin receipt yang tersingkir ke `request_key_conflicts`.
5. `DROP` tabel lama, `RENAME` tabel baru, lalu `PRAGMA user_version=54`.

Seluruh langkah berjalan dalam satu `BEGIN IMMEDIATE ... COMMIT`, mengikuti pola migrasi lain di
repositori ini. `schema.sql` tidak diubah karena file itu adalah baseline historis versi 1; database
baru tetap melewati rantai migrasi sampai 54.

### Implikasi kompatibilitas

- **Namespace key menjadi global.** Sebelumnya dua akun boleh memakai string key yang sama. Sesudah
  ini akun kedua ditolak 403. Untuk klien yang memakai UUID acak per transaksi, seperti dashboard
  ini, peluang bentrok dapat diabaikan. Untuk script yang memakai key deterministik sederhana,
  misalnya `k1`, perubahan ini terlihat.
- **Dampak pada kode yang ada nol.** Seluruh 354 test Python dan 61 modul acceptance browser
  dijalankan dengan instrumentasi yang mencatat setiap kemunculan key yang sudah dipakai akun lain.
  Hasilnya nol kejadian, jadi tidak ada jalur yang ada sekarang yang bergantung pada namespace per
  akun. Seeder demo memakai `demo-product`, `demo-order`, `demo-move-N` dengan satu akun, dan
  `tests/run_browser.py` memakai key lain lagi dengan satu akun.
- **Duplikat historis.** Database yang sudah pernah terkena bug ini bisa memuat key yang sama di
  beberapa akun. Migrasi tidak gagal: receipt paling awal dipertahankan, sisanya diarsipkan. Receipt
  hanya cache respons, bukan ledger bisnis, jadi pengarsipan tidak menghapus catatan bisnis apa pun.
  Mutasi ganda yang mungkin sudah terjadi tetap ada di ledger dan tetap dapat ditelusuri melalui
  `audit_events.request_key`, yaitu dua event dengan `request_key` sama dan `actor_id` berbeda.
- **Downgrade aplikasi.** Binary lama terhadap database v54 gagal tertutup dengan
  `RuntimeError: Unsupported database schema version: 54` karena tuple versi yang diterima maksimal
  53. Kebijakan backup sebelum upgrade tetap berlaku.
- **Query positional.** `INSERT INTO requests VALUES(?,?,?,?,?)` tidak lagi aman karena urutan kolom
  berubah, jadi insert ditulis dengan nama kolom eksplisit.
- **Pertahanan berlapis.** Setelah migrasi, insert kedua dengan key sama melanggar primary key dan
  memunculkan `IntegrityError` yang sudah dipetakan ke 409 oleh `api.py`, bahkan bila suatu saat
  pemeriksaan di Python hilang.

### Sisi klien untuk retry

Server menjadi penegak invarian. Perubahan klien hanya untuk UX dan diagnosa:

- Draft pending menyimpan `actor_id` di dalam record, bukan hanya pada nama key `sessionStorage`,
  sehingga record dapat menjelaskan dirinya sendiri.
- `recover()` menolak menawarkan retry ketika `actor_id` pada draft tidak sama dengan akun yang
  sedang aktif, dan mengarahkan pengguna untuk masuk kembali sebagai akun pencatat asli.
- 403 dari server sudah memicu perilaku klien yang benar tanpa perubahan lain: draft dipertahankan
  dan tombol Masuk ulang muncul.

## 3. Submit pertama di bawah session yang sudah berganti

### Celah yang tersisa

Kepemilikan idempotency key hanya menolong bila key-nya sudah pernah dipakai. Pada **submit pertama**
sebuah form, key masih baru, jadi server melihat request yang sah dari akun yang sedang memegang
session bersama. Urutannya:

1. Tab 1 masuk sebagai akun A dan membuka form mutasi, belum menekan simpan. State akun di tab itu
   hanya ada di memori.
2. Tab lain menukar session bersama ke akun B.
3. Tab 1 menekan simpan untuk pertama kali. Guard klien yang ada hanya berjalan untuk retry
   (`if (initial || unresolved)`), sehingga request dikirim apa adanya.
4. Server me-resolve akun B, key belum pernah dipakai, mutasi dijalankan dan **diatribusikan ke akun
   B** tanpa ada yang salah dari sudut pandang server.

Jalur investigasi AI memakai pola yang sama dan terkena hal yang sama.

### Keputusan: binding aktor yang ditegakkan server

Klien menyatakan akun yang dipakainya saat menyusun request melalui header `X-Beeloft-Actor`, dan
server menolak 403 sebelum mutasi dijalankan bila akun yang benar-benar ter-autentikasi berbeda.
Pemeriksaan diletakkan pada dependency `actor()` di `beeloft/api.py`, yaitu satu tempat yang dilewati
seluruh endpoint.

Alternatif yang dipertimbangkan dan tidak dipilih:

- **Pre-flight `GET /api/me` sebelum setiap penyimpanan.** Menambah satu round trip pada setiap
  pencatatan, dan tetap menyisakan celah TOCTOU: session dapat berganti antara pemeriksaan dan POST.
- **Membandingkan cookie CSRF dengan nilai saat login.** Lokal dan tanpa round trip, tetapi hanya
  mendeteksi "session diganti", bukan "akun berbeda". Login ulang oleh akun yang sama juga mengubah
  cookie, sehingga menimbulkan penolakan palsu.

Binding aktor tidak punya kedua kelemahan itu: pemeriksaan bersifat atomik terhadap request yang sama
dan membandingkan identitas, bukan token.

### Invarian tambahan

| # | Invarian |
|---|---|
| I9 | Setiap pencatatan dari browser menyatakan akun penyusunnya, dan pernyataan itu diverifikasi server sebelum mutasi dijalankan. |
| I10 | Pernyataan yang tidak cocok menghasilkan 403 tanpa mutasi, tanpa event audit, dan tanpa receipt, sehingga key-nya masih dapat dipakai akun yang sah. |
| I11 | Header ini tidak pernah memberi akses. Nilainya hanya dapat menolak request, bukan meloloskannya; autentikasi dan otorisasi tetap berasal dari API key atau cookie session. |

### Yang dipertahankan

- **Klien API key.** Header hanya dikirim oleh dashboard. Request tanpa header tidak diperiksa, jadi
  perilaku klien API key, CLI, dan seluruh test lama tidak berubah.
- **Kepemilikan idempotency key global.** Tetap berlaku dan tetap menjadi penjaga retry.
- **Otorisasi.** Pemeriksaan role tidak disentuh. Viewer tetap ditolak walau binding-nya cocok, dan
  request tanpa kredensial tetap 401 walau membawa header.
- **Pemulihan draft pending.** Login dan logout memakai `post()` tanpa idempotency key, sehingga
  keduanya tidak pernah membawa binding. Tombol **Masuk ulang** tetap dapat logout dari session milik
  akun lain, dan draft pending tetap dapat diselesaikan setelah masuk kembali sebagai akun asli.

### Batas

Milestone ini tidak menambah TTL atau pembersihan tabel `requests`, tidak menambah notifikasi
lintas tab, tidak menyentuh isu Final QC/rework, dan tidak mengubah aturan bisnis modul apa pun.
Binding aktor hanya dikirim untuk pencatatan ber-idempotency-key; request baca belum membawanya.
Schema naik dari 53 ke 54.
