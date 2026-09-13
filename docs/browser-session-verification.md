# Verifikasi session browser aman, v0.52

Tanggal: 14 September 2026. Base `6f90118`; branch `feature/browser-sessions` pada worktree lokal.
Semua pengujian memakai database sementara.

## Cakupan backend

Lima acceptance test baru memeriksa atribut cookie, ketiadaan API key mentah dalam response, autentikasi
session untuk pembacaan, proteksi CSRF untuk perubahan data, logout dan pencabutan session, penyimpanan
hash token, kompatibilitas API key untuk worker, validasi input, akun nonaktif, expiry, backup/restore,
dan migrasi schema 42 ke 43.

Seluruh suite backend lulus: **269 test dalam 168,629 detik** (`python -m unittest discover -s tests
-p 'test_*.py'`). Waktu proses end-to-end runner adalah 169,562 detik.

## Browser dan client

Client test memeriksa `credentials=same-origin`, mode session tanpa header API key, serta pengiriman token
CSRF untuk request yang mengubah data. Edge/Playwright memeriksa atribut cookie, pemulihan session setelah
reload, kolom API key yang tetap kosong, ketiadaan header API key pada request dashboard, login/logout,
dan seluruh regression suite browser. Seluruh regression suite browser lulus.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.52.0, `POST /api/session`, `POST /api/session/logout`, dan
`GET /api/me`. Database baru dan hasil migrasi memakai schema 43. Tiga dependency aplikasi memenuhi
batas versi yang dideklarasikan. Kompilasi Python 3.12, syntax 44 file JavaScript, client test, browser
final, dan pemeriksaan diff lulus sebelum commit rilis.

## Batas

API key lokal masih menjadi credential bootstrap. Aplikasi belum menyediakan konfigurasi penyedia
identitas, discovery OIDC, redirect/callback, pemetaan claim ke user/role, MFA, atau SSO.
