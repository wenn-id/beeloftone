# Bukti pengujian: authorization endpoint OIDC yang sudah ber-query

Temuan: [issue #31](https://github.com/wenn-id/beeloftone/issues/31) — URL otorisasi menempelkan
parameter OAuth ke query bawaan authorization endpoint, sehingga `response_type` tidak pernah menjadi
parameter tersendiri pada provider yang memakai parameter policy/tenant.

## Baseline

| | |
|---|---|
| Commit baseline | `c884f8667659086a84a8357a143839d1f9c87509` (`main`) |
| Aplikasi / schema | 0.92.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/audit-p2-oidc-authorization-query` |
| Working tree awal | bersih; tidak ada perubahan yang dibuang |

Temuan direproduksi ulang terhadap commit tersebut sebelum satu baris pun diubah. Baris yang menjadi
sumber masalah, `beeloft/oidc.py:139` pada baseline, tidak berubah antara commit audit
`f8921e763a8b317f3680229aedb9406ddba687c8` dan `c884f86`. Tidak ada checkout paksa ke commit lama.

## Lingkungan

Python 3.14.4 pada venv repositori (`.venv`), Node.js 24.16.0, Playwright 1.63.0 dengan Chromium pada
`~/.cache/ms-playwright`, Linux. Seluruh pengujian memakai database sementara sekali pakai
(`tempfile.TemporaryDirectory` pada test dan runner browser); tidak ada database bisnis atau
produksi yang disentuh, dan tidak ada jaringan yang dihubungi — discovery, token, serta JWKS dilayani
transport OIDC palsu bertanda tangan RSA seperti suite `test_oidc_sso.py`.

## Reproduksi

Skrip reproduksi menjalankan alur nyata `GET /api/sso/login` terhadap transport palsu yang metadata
discovery-nya memuat authorization endpoint ber-query, lalu mem-parse `Location` header dengan
`urllib.parse.parse_qs`. Tiga endpoint diuji: tanpa query, satu parameter policy, dan dua parameter.

Baseline `c884f86`:

| Authorization endpoint | `Location` yang dihasilkan | Hasil parse |
| --- | --- | --- |
| `…/authorize` | `…/authorize?response_type=code&…` | benar |
| `…/authorize?p=tenant-policy` | `…/authorize?p=tenant-policy?response_type=code&…` | `p = tenant-policy?response_type=code`, tidak ada `response_type` |
| `…/authorize?p=tenant-policy&realm=beeloft` | `…/authorize?p=tenant-policy&realm=beeloft?response_type=code&…` | `realm = beeloft?response_type=code`, tidak ada `response_type` |

Tanda `?` kedua tidak pernah menjadi pemisah query: `response_type` menempel pada nilai parameter
terakhir milik endpoint, jadi parameter itu hilang dari permintaan otorisasi. Sesudah perbaikan,
ketiga endpoint menghasilkan URL dengan query bawaan utuh dan delapan parameter OAuth sebagai
parameter tersendiri:

| Authorization endpoint | `Location` yang dihasilkan | Hasil parse |
| --- | --- | --- |
| `…/authorize` | `…/authorize?response_type=code&…` | 8 parameter OAuth, tanpa parameter lain |
| `…/authorize?p=tenant-policy` | `…/authorize?p=tenant-policy&response_type=code&…` | `p = tenant-policy` + 8 parameter OAuth |
| `…/authorize?p=tenant-policy&realm=beeloft` | `…/authorize?p=tenant-policy&realm=beeloft&response_type=code&…` | `p` dan `realm` utuh + 8 parameter OAuth |

## Perbaikan

- `OidcClient.authorization_request` tidak lagi menyambung `'?' + query` secara langsung. Endpoint
  dipecah dengan `urllib.parse.urlsplit`, query bawaan dipertahankan apa adanya, dan parameter OAuth
  disambung sebagai parameter query tersendiri sebelum `urlunsplit` menyusun ulang URL. Pemisah yang
  dipakai mengikuti keberadaan query bawaan, jadi endpoint tanpa query, endpoint dengan `?` kosong,
  dan endpoint dengan satu atau lebih parameter semuanya menghasilkan URL yang benar.
- Nilai parameter OAuth tidak berubah: `response_type=code`, `client_id`, `redirect_uri`,
  `scope=openid profile email`, `state`, `nonce`, `code_challenge`, dan `code_challenge_method=S256`
  tetap dibangkitkan dan di-encode seperti sebelumnya.
- Validasi metadata tidak dilonggarkan: `_https_url` tetap menolak endpoint tanpa host, berfragment,
  ber-kredensial, atau bukan HTTPS (selain loopback), dan discovery tetap mensyaratkan kecocokan
  issuer yang persis.

Tidak ada perubahan schema (`user_version` tetap 55), tidak ada endpoint atau field API baru, dan
tidak ada perubahan perilaku untuk endpoint yang memang tidak memiliki query.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | `Ran 537 tests` — **OK** (536 pada `main`; 1 test baru). |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs` dan `beeloft/static/client.mjs` | bersih |
| `node tests/test_client.mjs` | lulus |
| `python tests/run_browser.py --node node --playwright-module <playwright> --channel chromium` | 79 modul acceptance **PASS**, tanpa JS error |
| Skrip reproduksi pada baseline dan tree perbaikan | `response_type` hilang pada 3 endpoint ber-query → 8 parameter OAuth tersendiri pada ketiga endpoint |

Test baru di `tests/test_oidc_sso.py`:

- `test_authorization_endpoint_query_is_kept_as_separate_parameters` menjalankan login lengkap
  terhadap empat bentuk authorization endpoint: `/authorize`, `/authorize?`,
  `/authorize?p=tenant-policy`, dan `/authorize?p=tenant-policy&realm=beeloft`. Untuk setiap bentuk
  ia menegaskan query bawaan bertahan dengan nilai aslinya, himpunan parameter pada `Location` persis
  query bawaan ditambah delapan parameter OAuth, `redirect_uri`/`scope`/`client_id` benar, PKCE yang
  dikirim cocok dengan `code_challenge` S256 dari `code_verifier` yang tersimpan di
  `oidc_login_attempts`, dan callback dengan token sah menutup alur `303` + session seperti pada
  endpoint tanpa query.
- `FakeOidcTransport` menerima `authorization_endpoint` opsional supaya metadata discovery dapat
  memuat query policy/tenant; nilainya default ke perilaku lama (`issuer + '/authorize'`), jadi test
  lain tidak berubah.

Test baru gagal pada baseline `c884f86` (`AssertionError: … 'response_type'` untuk tiga endpoint
ber-query) dan lulus sesudah perbaikan, sehingga bukan test yang selalu benar.

## Catatan operasional

Penyedia identitas yang memakai query bawaan pada authorization endpoint — mis. `?p=<policy>` pada
Azure AD B2C atau parameter tenant/realm sejenis — kini menerima `response_type`, `client_id`,
`state`, `nonce`, dan PKCE sebagai parameter tersendiri, sehingga login SSO berjalan tanpa perubahan
konfigurasi `BEELOFT_OIDC_*`. Bila endpoint sekaligus membawa parameter dengan nama yang sama seperti
parameter OAuth (mis. `?response_type=token` yang salah konfigurasi), provider tetap memutuskan
parameter mana yang dipakai; perbaikan ini sengaja tidak membuang query bawaan karena RFC 6749 §3.1
mensyaratkan query itu dipertahankan, dan konfigurasi seperti itu memang harus diperbaiki di sisi
metadata, bukan diam-diam ditimpa aplikasi.
