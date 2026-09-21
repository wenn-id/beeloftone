# Bukti pengujian: state callback OIDC non-ASCII ditolak tanpa 500

Temuan: [issue #35](https://github.com/wenn-id/beeloftone/issues/35) — dengan SSO aktif,
`/api/sso/callback?code=x&state=%C3%A9` dijawab HTTP 500 karena `secrets.compare_digest()` melempar
`TypeError` pada `str` yang memuat karakter non-ASCII. Request seperti itu semestinya ditolak sebagai
state tidak sah.

## Baseline

| | |
|---|---|
| Commit baseline | `c388a0f1ed3521257e67780c2223b1f83a305e5e` (`main`) |
| Aplikasi / schema | 0.94.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/audit-p3-oidc-state-non-ascii` |
| Working tree awal | bersih; tidak ada perubahan yang dibuang |

Temuan direproduksi ulang terhadap commit tersebut sebelum satu baris pun diubah. Baris yang menjadi
sumber masalah tidak berubah antara commit audit `f8921e763a8b317f3680229aedb9406ddba687c8` dan
`c388a0f`: pada kedua commit `beeloft/api.py:162` berbunyi persis
`if not secrets.compare_digest(browser_state,state):`. Tidak ada checkout paksa ke commit lama.

## Lingkungan

Python 3.12.13 pada venv repositori (`.venv`), Node.js 22.23.2, Playwright 1.63.0 dengan Chromium
headless shell 153.0.8010.12, Linux. Seluruh pengujian memakai database sementara sekali pakai
(`tempfile.TemporaryDirectory` pada test dan runner browser); tidak ada database bisnis atau
produksi yang disentuh, dan tidak ada jaringan yang dihubungi — discovery, token, serta JWKS
dilayani transport OIDC palsu bertanda tangan RSA. Reproduksi tidak melewati autentikasi: seluruh
request di bawah dikirim tanpa session dan tanpa API key.

## Reproduksi

`secrets.compare_digest()` menerima `str` hanya bila kedua argumennya ASCII. Argumen non-ASCII
dijawab `TypeError: comparing strings with non-ASCII characters is not supported`, tanpa peduli sisi
mana yang non-ASCII dan tanpa peduli apakah sisi lainnya kosong:

| Cookie `beeloft_oidc_state` | `state` pada query | Hasil `compare_digest` |
| --- | --- | --- |
| `''` | `é` | `TypeError` |
| `abc` | `é` | `TypeError` |
| `é` | `abc` | `TypeError` |

Kedua nilai itu sepenuhnya dikendalikan pengirim request, sehingga `TypeError` dapat dipicu dari dua
arah. Pada baseline `c388a0f`, dengan SSO aktif dan tanpa kredensial apa pun:

| Request | Baseline `c388a0f` | Sesudah perbaikan |
| --- | --- | --- |
| `?code=x&state=%C3%A9` (reproduksi issue) | **500** `Internal Server Error` | 401 `State login OIDC tidak cocok dengan browser.` |
| `?code=x&state=%C3%A9%C3%A9` | **500** | 401 |
| `?code=x&state=%E2%82%AC` | **500** | 401 |
| `state` sah + cookie `beeloft_oidc_state=\xe9` | **500** | 401 |
| `?code=x&state=abc%20def` | 401 | 401 |
| `?code=x&state=a.b` | 401 | 401 |
| `?code=x&state=abc` | 401 | 401 |

Baris terakhir menunjukkan batas temuan: state ASCII yang tidak cocok memang sudah ditolak 401 pada
baseline. Yang rusak hanya state di luar ASCII, dan jalur cookie ikut terkena karena cookie
di-decode latin-1 dari header, sehingga byte `\xe9` mentah pada `Cookie` menjadi `str` non-ASCII di
dalam handler. Jalur cookie itu bahkan merusak callback yang `state`-nya sah.

## Perbaikan

- `beeloft/api.py` menambahkan `oidc_state_bytes()`. State diperiksa lebih dahulu terhadap alfabet
  yang memang diterbitkan aplikasi — `OidcClient.authorization_request` memakai
  `secrets.token_urlsafe`, jadi state sah hanya memuat huruf, angka, `-`, dan `_` — lalu dibandingkan
  sebagai byte ASCII. Nilai kosong atau di luar alfabet menghasilkan `None`.
- `sso_callback` memeriksa kedua sisi: `state` pada query dan cookie `beeloft_oidc_state`. Bila salah
  satu di luar alfabet, atau keduanya tidak identik, request ditolak `OidcError(401, ...)` dengan
  pesan yang sama seperti sebelumnya. Satu pesan untuk semua kegagalan state menjaga agar respons
  tidak mengungkap sisi mana yang cacat, persis seperti perilaku baseline untuk state ASCII.
- Perbandingan state yang sah tetap lewat `secrets.compare_digest` atas byte ASCII, sehingga tetap
  constant-time. Pemeriksaan alfabet tidak menyentuh nilai cookie sebagai perbandingan, hanya
  himpunan karakternya, sehingga tidak ada nilai rahasia yang bocor lewat waktu eksekusi.
- State di luar alfabet berhenti sebelum `store.consume_oidc_login_attempt()`, sehingga tidak dapat
  menghabiskan attempt yang tersimpan. Batas panjang tetap dipegang `Query(max_length=512)` seperti
  sebelumnya, dan `min_length=1` tetap menolak state kosong dengan 422.
- Tidak ada perubahan pada `/api/sso/login`, penerbitan state/nonce/PKCE, pertukaran code, verifikasi
  tanda tangan, pemeriksaan nonce/`azp`/subject, maupun cookie session. Tidak ada perubahan schema
  (`user_version` tetap 55), endpoint, atau field API — `docs/openapi.json` diregenerasi dari
  `app.openapi()` dan diff-nya hanya baris `"version"`. Versi aplikasi 0.94.0 → 0.95.0.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | `Ran 541 tests` — **OK** (539 pada `main`; 2 test baru). |
| `python -m pip check` | `No broken requirements found.` |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs` dan `beeloft/static/client.mjs` | bersih |
| `node tests/test_client.mjs` | lulus |
| `python tests/run_browser.py --node node --playwright-module playwright --channel chromium` | 79 modul acceptance **PASS**, tanpa JS error |
| Skrip reproduksi pada baseline dan tree perbaikan | 4 request 500 → seluruhnya 401 |

Test baru di `tests/test_oidc_sso.py`:

- `test_state_outside_the_issued_alphabet_is_rejected_without_a_server_error` menjalankan login SSO
  yang sah, lalu mengirim delapan callback dengan state di luar alfabet — termasuk `%C3%A9` persis
  seperti issue, `%C3%A9%C3%A9`, `%E2%82%AC`, `%00`, spasi, titik, `+`, dan state sah yang diberi
  satu karakter non-ASCII di ujungnya. Semuanya harus dijawab 401 dengan detail yang sama dan tanpa
  cookie session. Test ini juga menegaskan penolakan itu tidak menukar code (`token_requests` tetap
  kosong) dan tidak menghabiskan attempt (`oidc_login_attempts` tetap satu baris), lalu meneruskan
  alur yang sama dengan state sah: 303 ke `/`, `/api/me` mengembalikan akun tertaut, baris attempt
  habis, dan replay state yang sama ditolak 401 tanpa pertukaran code kedua.
- `test_non_ascii_state_cookie_is_rejected_without_a_server_error` mengirim `state` yang sah bersama
  header `Cookie` ber-byte mentah `\xe9` dalam tiga bentuk (`\xe9`, `\xe9\xe9`, dan state sah yang
  diberi `\xe9`). Ketiganya harus 401, tanpa pertukaran code, dan attempt tetap utuh.
- Helper `lenient_client()` membangun `TestClient(raise_server_exceptions=False)` supaya exception
  yang tidak tertangani terlihat sebagai respons 500 dan dapat dibandingkan dengan 401 yang
  diharapkan; tanpa itu test hanya gagal dengan `TypeError` dari dalam handler dan tidak dapat
  membedakan penolakan yang benar dari kegagalan server.

Kedua test gagal pada baseline `c388a0f` dengan 7 subtest `AssertionError: 500 != 401 : Internal
Server Error` (4 pada jalur query, 3 pada jalur cookie) lalu lulus sesudah perbaikan, sehingga bukan
test yang selalu benar. Subtest ASCII pada test pertama (`abc%20def`, `a.b`, `a%2Bb`) memang sudah
lulus pada baseline; keberadaannya menjaga agar penolakan state ASCII tidak bergeser.

## Catatan operasional

Tidak ada perubahan konfigurasi. Pengguna dengan SSO aktif tidak melihat perbedaan pada login yang
normal: `/api/sso/login` tetap menerbitkan state yang sama bentuknya, dan callback yang sah tetap
berakhir 303 ke `/` dengan cookie session. Yang berubah hanya jawaban untuk callback yang state-nya
tidak pernah diterbitkan aplikasi: sekarang 401 dengan pesan yang dapat dibaca operator, bukan 500
yang meninggalkan traceback di log server.
