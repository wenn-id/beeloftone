# Bukti pengujian: encoding client_secret_basic sesuai RFC 6749 §2.3.1

Temuan: [issue #32](https://github.com/wenn-id/beeloftone/issues/32) — client ID dan client secret
digabung mentah menjadi `id:secret` sebelum Base64, sehingga provider yang memisah kredensial pada
titik dua pertama lalu mem-form-decode setiap nilai menerima kredensial yang berbeda dari yang
dikonfigurasi.

## Baseline

| | |
|---|---|
| Commit baseline | `97815b8cc1d2334022ef4c32c27d4e56c7be8a6c` (`main`) |
| Aplikasi / schema | 0.93.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/audit-p2-oidc-client-secret-basic` |
| Working tree awal | bersih; tidak ada perubahan yang dibuang |

Temuan direproduksi ulang terhadap commit tersebut sebelum satu baris pun diubah. Baris yang menjadi
sumber masalah, `beeloft/oidc.py:93` pada baseline, tidak berubah antara commit audit
`f8921e763a8b317f3680229aedb9406ddba687c8` dan `97815b8`. Tidak ada checkout paksa ke commit lama.

## Lingkungan

Python 3.14.4 pada venv repositori (`.venv`), Node.js 24.16.0, Playwright 1.63.0 dengan Chromium pada
`~/.cache/ms-playwright`, Linux. Seluruh pengujian memakai database sementara sekali pakai
(`tempfile.TemporaryDirectory` pada test dan runner browser); tidak ada database bisnis atau
produksi yang disentuh, dan tidak ada jaringan yang dihubungi — discovery, token, serta JWKS
dilayani transport OIDC palsu bertanda tangan RSA.

## Reproduksi

Skrip reproduksi membangun header `Authorization` persis seperti `UrlTransport.form_post`, lalu
membacanya persis seperti provider menurut RFC 6749 §2.3.1: Base64 di-decode, dipisah pada titik dua
pertama, dan username serta password di-form-decode terpisah dengan `unquote_plus`.

Baseline `97815b8`:

| Client ID | Client secret | Yang dibaca provider | Hasil |
| --- | --- | --- | --- |
| `client:id` | `secret+percent%value` | id `client`, secret `id:secret percent%value` | salah |
| `client id` | `secret value` | id `client id`, secret `secret value` | benar |
| `100%client` | `a%2Bb` | id `100%client`, secret `a+b` | salah |
| `client:with:colon` | `secret:with:colon` | id `client`, secret `with:colon:secret:with:colon` | salah |

Nilai yang di-Base64 mentah membuat titik dua pertama di dalam client ID menjadi pemisah palsu, dan
`+`/`%` yang tidak di-encode berubah arti saat provider mem-form-decode. Sesudah perbaikan, keempat
pasangan dibaca provider dengan nilai aslinya:

| Client ID | Client secret | Yang dibaca provider | Hasil |
| --- | --- | --- | --- |
| `client:id` | `secret+percent%value` | id `client:id`, secret `secret+percent%value` | benar |
| `client id` | `secret value` | id `client id`, secret `secret value` | benar |
| `100%client` | `a%2Bb` | id `100%client`, secret `a%2Bb` | benar |
| `client:with:colon` | `secret:with:colon` | id `client:with:colon`, secret `secret:with:colon` | benar |

## Perbaikan

- `UrlTransport.form_post` tidak lagi menggabungkan nilai mentah. Setiap nilai di-form-encode
  terpisah dengan `urllib.parse.quote_plus` (RFC 6749 §2.3.1 memakai
  `application/x-www-form-urlencoded` Appendix B), hasilnya baru digabung dengan `:`, lalu di-Base64.
  Titik dua di dalam nilai kini menjadi `%3A`, sehingga pemisah pertama yang dibaca provider selalu
  pemisah yang benar.
- Jalur `client_secret_post` tidak disentuh: `OidcClient.exchange` tetap mengirim `client_secret` di
  body form dan tidak mengirim header `Authorization`, dan `urllib.parse.urlencode` tetap
  menangani encoding body seperti sebelumnya.
- Tidak ada perubahan pada validasi `OidcConfig`, discovery, PKCE, verifikasi tanda tangan, maupun
  pemeriksaan nonce/`azp`/subject. Tidak ada perubahan schema (`user_version` tetap 55), endpoint,
  atau field API. Versi aplikasi 0.93.0 → 0.94.0.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | `Ran 539 tests` — **OK** (537 pada `main`; 2 test baru). |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs` dan `beeloft/static/client.mjs` | bersih |
| `node tests/test_client.mjs` | lulus |
| `python tests/run_browser.py --node node --playwright-module <playwright> --channel chromium` | 79 modul acceptance **PASS**, tanpa JS error |
| Skrip reproduksi pada baseline dan tree perbaikan | 3 dari 4 pasangan rusak → 4 dari 4 dibaca provider dengan nilai asli |

Test baru di `tests/test_oidc_sso.py`:

- `test_basic_auth_form_encodes_each_credential_before_base64` menjalankan `OidcClient.exchange`
  lengkap di atas `UrlTransport` asli dengan jaringan dimatikan (`ProviderUrlTransport` menyimpan
  `urllib.request.Request` yang benar-benar dibangun `form_post`). Untuk empat pasangan kredensial —
  titik dua, plus, persen, dan spasi — ia menegaskan provider yang memisah lalu mem-form-decode
  header menerima client ID dan secret asli, `client_secret` tidak ikut di body, dan pertukaran code
  tetap menghasilkan identitas yang terverifikasi.
- `test_client_secret_post_keeps_the_secret_in_the_form_body` menegaskan jalur
  `client_secret_post` tetap bekerja: tidak ada header `Authorization`, dan body form memuat
  `client_id` serta `client_secret` dengan nilai aslinya (termasuk `+` dan `%`).
- `ProviderUrlTransport` menambahkan transport palsu berbasis `UrlTransport` asli dengan metode
  autentikasi yang dapat dipilih, sehingga test lama (yang memakai `FakeOidcTransport` dengan
  `client_secret_post`) tidak berubah.

Test `test_basic_auth_form_encodes_each_credential_before_base64` gagal pada baseline `97815b8` untuk
3 dari 4 pasangan (`AssertionError: Tuples differ: ('client', 'id:secret percent%value') !=
('client:id', 'secret+percent%value')` dan seterusnya) lalu lulus sesudah perbaikan, sehingga bukan
test yang selalu benar. Test `test_client_secret_post_keeps_the_secret_in_the_form_body` lulus pada
baseline maupun tree perbaikan — jalur itu memang tidak terkena temuan, dan test-nya menjaga agar
perbaikan Basic tidak menggeser perilakunya.

## Catatan operasional

Provider yang hanya mendukung `client_secret_basic` — dan kredensialnya memuat `:`, `+`, `%`, atau
spasi — kini menerima nilai yang sama dengan yang dikonfigurasi pada `BEELOFT_OIDC_CLIENT_ID` dan
`BEELOFT_OIDC_CLIENT_SECRET`, tanpa perubahan konfigurasi. Provider yang mendukung
`client_secret_post` tetap memakai jalur itu seperti sebelumnya, karena pemilihan metode di
`OidcClient.exchange` tidak berubah.
