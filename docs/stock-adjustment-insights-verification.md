# Verifikasi audit adjustment stok, v0.67

Tanggal: 14 September 2026. Base `718fc9f`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak mengubah data operasional.

## Backend

Dua acceptance test memeriksa flag jumlah besar, porsi penerimaan, pengulangan bucket, koreksi, klasifikasi,
sumber manual dan stock opname, volume absolut, urutan, filter, pagination, role, validasi, backup, schema, dan
sifat GET read-only. Tes terarah lulus **2 tes** dalam 1,925 detik.

Regresi backend penuh lulus **307 tes** dalam 293,523 detik.

## Browser dan visual

QA Edge memakai adjustment manual +3 pcs yang sudah dikoreksi. Laporan harus menandainya untuk tinjauan,
menjelaskan flag koreksi, mempertahankan karakter HTML sebagai teks, membuka adjustment asal, dan melindungi
aksi koreksi dari viewer. Error/retry, empty state, lebar 390 px, zoom 200%, serta overflow horizontal diperiksa.

Seluruh Edge QA lulus tanpa error JavaScript, termasuk audit adjustment dan seluruh modul lama. Pemeriksaan
visual screenshot kartu hasil pada lebar 390 px menunjukkan hierarki, label, angka, alasan flag, dan tombol
drill-down terbaca tanpa overflow. Zoom teks 200% diuji sebelum screenshot dan tetap tidak menimbulkan overflow
horizontal.

## Release checks

Client tests, syntax **53 file JavaScript**, kompilasi Python, dan `pip check` lulus. OpenAPI serta paket memakai
versi 0.67.0 dan kontrak memuat route baru. Database baru mencapai schema 48; `integrity_check` mengembalikan
`ok` dan `foreign_key_check` kosong. `git diff --check` serta pemeriksaan string UI tanpa em dash lulus.

## Batas

Flag bersifat deterministik dan transparan, tetapi tetap memerlukan pemeriksaan manusia. Laporan tidak menghitung
nilai rupiah dan tidak menulis adjustment atau audit event. Runtime connector Jubelio/Mekari tidak dicakup.
