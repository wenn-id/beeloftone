# Bukti pengujian: submit login lokal tidak boleh mengunci tombol SSO

Temuan: [issue #30](https://github.com/wenn-id/beeloftone/issues/30) — `querySelector('button')`
memilih tombol SSO yang berada lebih dahulu di dalam form, sehingga tombol submit login lokal tidak
pernah dinonaktifkan selama request berjalan dan label provider ditimpa oleh label tombol submit.

## Baseline

| | |
|---|---|
| Commit baseline | `d180167c9dd15d1e940d15e209fba987f7b03cab` (`main`), audit pada `f8921e763a8b317f3680229aedb9406ddba687c8` |
| Aplikasi / schema | 0.91.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/audit-p2-local-login-submit` |
| Working tree awal | bersih; tidak ada perubahan yang dibuang |

Temuan direproduksi ulang terhadap commit tersebut: handler `login-form` tidak berubah antara
`f8921e7` dan `d180167` (`git diff f8921e7..HEAD -- beeloft/static/app.mjs` tidak menyentuh baris
`querySelector('button')`), jadi cacat yang sama masih ada di `main`.

## Lingkungan

Python 3.14.4 pada venv repositori (`.venv`), Node.js 24.16.0, Playwright 1.63.0 dengan Chromium,
Linux. Seluruh pengujian memakai database sementara sekali pakai (`tempfile.TemporaryDirectory`);
tidak ada database bisnis atau produksi yang disentuh.

## Reproduksi

`$('login-form').onsubmit` mengambil tombolnya dengan `event.currentTarget.querySelector('button')`.
Tombol SSO (`#sso-login`, `type="button"`) adalah elemen pertama di dalam form, dan tetap elemen
pertama ketika `hidden` diset oleh `loadLoginOptions()` saat `/api/sso` menjawab `enabled:false`.
Akibatnya:

- yang dinonaktifkan dan diberi label `Memeriksa akses…` adalah tombol provider, bukan tombol submit;
- tombol submit tetap aktif selama request, jadi submit kedua mengirim `POST /api/session` kedua yang
  berlomba menggantikan cookie session;
- blok `finally` menulis `Buka ruang produksi` ke tombol provider. Ketika SSO aktif, label
  `Masuk dengan <provider>` hilang permanen dan tombol itu tetap mengarah ke `/api/sso/login`.

Modul `tests/browser_login_form.cjs` menahan `POST /api/session` pertama di depan server dengan
respons tertunda, lalu menghitung berapa request yang benar-benar terkirim sementara request pertama
masih berjalan. Baseline dijalankan tiga kali terhadap `d180167`, dengan assert yang lebih awal
dinonaktifkan sementara supaya tiap cacat tercapai:

| Baseline `d180167` | Hasil |
| --- | --- |
| Seluruh assert aktif, dua klik pada tombol submit | gagal pada `tombol submit harus dinonaktifkan selama request berjalan` (`false !== true`) |
| Assert tombol dinonaktifkan dilewati | gagal pada `tombol SSO yang tersembunyi tidak boleh diberi label tombol submit` — tombol provider berisi `Memeriksa akses…` |
| Ketiga assert tombol dilewati | gagal pada jumlah request: **4** `POST /api/session` (2 klik, 1 `requestSubmit()`, 1 Enter) untuk satu kali login |

Salinan kerja sementara itu sudah dikembalikan sebelum commit; hanya assert produksi yang menjadi
bagian perubahan ini.

## Perbaikan

- Pemilihan tombol dipersempit ke tombol submit form ini:
  `event.currentTarget.querySelector('button[type="submit"]')`. Tombol provider tidak lagi disentuh
  oleh alur login lokal, sehingga labelnya tetap seperti yang diberikan `/api/sso` dan aksinya tetap
  `location.assign('/api/sso/login')`.
- Guard satu login dalam penerbangan (`loginRequest`), pola yang sama dengan `logoutRequest`: submit
  selama percobaan pertama berjalan tidak mengirim penukaran session kedua. Penonaktifan tombol saja
  tidak cukup — `form.requestSubmit()` tetap memicu `submit` event ketika tombol defaultnya
  dinonaktifkan (diverifikasi pada Chromium 1.63.0), dan itu jalur yang guard ini tutup.
- Label tombol submit disimpan sebelum diubah dan dipulihkan dari salinan itu, bukan dari literal,
  jadi hanya tombol yang benar-benar dipakai yang dikembalikan ke labelnya.

Tidak ada perubahan schema (`user_version` tetap 55), tidak ada endpoint atau field API baru, dan
tidak ada perubahan pada alur SSO maupun pada `POST /api/session`.

## Cakupan tes

`tests/browser_login_form.cjs`, dijalankan `tests/browser_smoke.cjs`:

| Keadaan | Yang diperiksa |
| --- | --- |
| SSO tersembunyi, respons login tertunda | tombol submit nonaktif dan berlabel `Memeriksa akses…` selama request; layar login belum hilang; tombol SSO yang tersembunyi tidak menerima label tombol submit |
| SSO tersembunyi, satu login satu request | dua klik + `requestSubmit()` (yang kesannya sendiri diperiksa benar-benar memicu `submit` event) + Enter selama request berjalan menghasilkan tepat satu `POST /api/session`, dan label tombol submit pulih sesudah selesai |
| SSO aktif, login lokal gagal | label `Masuk dengan Identitas Beeloft` dan visibilitas tombol provider tidak berubah; tombol submit pulih ke `Buka ruang produksi` |
| SSO aktif, login lokal berhasil | tombol provider tidak ikut terkunci maupun berlabel proses, labelnya bertahan sesudah ruang kerja terbuka dan sesudah keluar lagi |
| SSO aktif, aksi provider | klik tombol provider benar-benar berpindah ke `/api/sso/login` (navigasi nyata, bukan pembacaan handler) |

## Hasil

| Perintah | Hasil |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests` | 536 test lulus |
| `tests/run_browser.py --channel chromium` | 79 modul browser lulus, tanpa error JavaScript |
| Baseline `d180167` tanpa perbaikan | modul baru gagal seperti tabel di atas: tombol submit tidak terkunci, label provider tertimpa, dan 4 request untuk satu login |
