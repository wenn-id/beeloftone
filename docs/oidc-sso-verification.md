# Verifikasi login OIDC / SSO, v0.53

Tanggal: 14 September 2026. Base `6f4736b`; branch `feature/oidc-sso` pada worktree lokal. Semua
pengujian memakai database dan pasangan kunci sementara; tidak ada credential atau provider nyata.

## Cakupan backend

Lima acceptance test OIDC memeriksa discovery, authorization redirect, PKCE S256, state/nonce yang
di-hash, cookie state yang terikat browser, pertukaran code, verifikasi signature RS256/JWKS, issuer,
audience, expiry dan nonce, session browser hasil SSO, mapping user/role, unknown identity, user nonaktif,
konfigurasi nonaktif/tidak lengkap, konflik mapping, unlink, backup, dan migrasi schema 43 ke 44. CLI
link/unlink juga dijalankan melalui subprocess sungguhan.

Seluruh suite backend lulus: **274 test dalam 161,948 detik** (`python -m unittest discover -s tests
-p 'test_*.py'`). Waktu proses end-to-end runner adalah 162,807 detik.

## Browser dan client

Seluruh regression suite Edge/Playwright lulus dengan mode OIDC nonaktif, termasuk login API key,
pemulihan session, seluruh modul operasional, mobile, skala teks 200%, dan ketiadaan error JavaScript.
Mode OIDC aktif diuji terpisah pada server/database sementara: tombol berlabel provider tampil, jalur
API key lokal tetap tersedia, dan screenshot desktop diperiksa secara visual.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.53.0 dan tiga endpoint OIDC pada tiga path. Database baru dan hasil
migrasi memakai schema 44. Empat dependency aplikasi memenuhi batas versi yang dideklarasikan;
PyJWT dengan backend kriptografi memverifikasi signature asymmetric. Kompilasi Python 3.12, syntax
44 file JavaScript, client test, browser final, dan pemeriksaan diff lulus sebelum commit rilis.

## Batas

Pengujian memakai provider deterministik lokal pada boundary transport. Konfigurasi tenant, redirect URI,
client credential, dan kebijakan claim tetap harus divalidasi terhadap provider pilihan sebelum produksi.
