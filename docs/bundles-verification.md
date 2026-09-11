# Verifikasi bundling — v0.19

Tanggal: 11 September 2026. Base `52533c7`; branch `feature/bundles` pada
worktree lokal. Pengujian menggunakan database sementara dan tidak memakai data
bisnis.

## Hasil otomatis

- `../../.venv/Scripts/python.exe -m unittest discover -s tests -q` dengan
  `PYTHONPATH` diarahkan ke worktree: **112 tests OK** dalam 95,611 detik.
- `node --check beeloft/static/app.mjs`: **PASS**.
- `node tests/test_client.mjs`: **Client checks PASS** dan **CSV client checks PASS**.
- `../../.venv/Scripts/python.exe -m pip check`: **No broken requirements found**.
- OpenAPI dibuat dari `create_app()` pada database sementara: versi **0.19.0**,
  empat path Bundling tersedia, dan `BundleCreate` mewajibkan `reference`,
  `output_movement_id`, `quantity`, serta `reason`.

Tes backend Bundling mencakup dua bundle parsial pada satu output, lineage order,
SKU/ukuran, cutting run dan batch bahan, WIP yang tidak berubah, idempotent replay,
role, referensi case-insensitive, input boolean/over-allocation, sumber lintas run,
dua alokasi bersamaan, rollback setelah insert, cursor, persistence, backup,
koreksi seluruh catatan, blok koreksi cutting, direct-write guard termasuk Bundle
ID dengan spasi tepi, list cutting yang hanya membawa ringkasan alokasi, serta
sejarah bundle dan koreksi yang immutable.

Migrasi diuji dari schema 13 ke 14. Hasil cutting lama tetap dapat dibaca, daftar
bundle awal kosong, output lama seluruhnya belum dibundel, dan `user_version`
menjadi 14. Migrasi tidak mengarang identitas bundle historis.

## Browser

Perintah:

```powershell
../../.venv/Scripts/python.exe tests/run_browser.py `
  --node C:/Users/acer/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe `
  --playwright-module C:/Users/acer/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright `
  --channel msedge
```

Seluruh modul browser lulus, termasuk `Bundling browser QA PASS`, dan pemeriksaan
akhir melaporkan tidak ada error JavaScript. Daftar bundle diuji saat respons GET
gagal, berhasil dicoba ulang, dan masih kosong. Alur lalu membuat data nyata melalui
API, masuk sebagai operator, membuka output cutting, dan membuat bundle 8 pcs. Respons
pertama sengaja diputus setelah server menyimpan; reload dan **Coba ulang
penyimpanan** dengan key yang sama mengembalikan bundle yang sama, sehingga daftar
tetap berisi satu record dan saldo sewing tetap 20 pcs.

Viewer dapat membuka daftar serta lineage tetapi tidak melihat aksi membuat atau
mengoreksi. Operator dapat membuat dan tidak dapat mengoreksi. Admin melihat aksi
koreksi; koreksi cutting ditolak selama bundle aktif, lalu koreksi bundle berhasil
tanpa mengubah WIP. Form native dialog menutup dengan Escape. Dialog tidak overflow
pada viewport 390 × 844 maupun skala teks 200%.

Screenshot `beeloft-bundle-mobile.png` diperiksa pada ukuran aslinya. Bundle ID,
status, 8 pcs, SKU/ukuran, hasil cutting, batch/material asal, alasan, aktor/waktu,
dan empat link tindakan terbaca tanpa clipping. Style yang sudah ada mencukupi,
sehingga tidak ada perubahan CSS.

## Batas yang tetap berlaku

Bundle hanya memberi identitas pada output cutting dan belum mengikuti pergerakan
antar tahap. Versi ini belum membuat barcode/label, mencetak atau memindai, membagi
atau menggabungkan bundle, mengirim ke vendor sewing, menghitung biaya, atau mencatat
defect dan missing pieces. Tindakan di aplikasi harus mengikuti kondisi fisik.
