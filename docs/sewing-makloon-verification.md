# Verifikasi sewing dan makloon — v0.20

Tanggal: 11 September 2026. Base `5b41fd4`; branch `feature/sewing-makloon`
pada worktree lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan

Tes backend memeriksa alokasi beberapa job parsial, biaya IDR presisi, hasil selesai/defect/missing,
turnaround, perpindahan WIP yang seimbang, koreksi seluruh job, role, tanggal dan total hasil,
referensi unik, idempotent retry, transaksi bersamaan, rollback, blok koreksi bundle dan movement
terkait, kondisi downstream QC, cursor, persistence, backup, direct-write guard, serta ledger yang
immutable. Migrasi 14 → 15 mempertahankan bundle lama tanpa membuat job historis.

Browser QA menjalankan alur operator dari bundle 20 pcs: mengirim 12 pcs ke vendor dengan biaya
Rp240.000,00, lalu menerima 10 selesai, 1 defect, dan 1 missing. Saldo akhir menjadi sewing 8,
finishing 10, reject 2. Respons pertama saat membuat job sengaja diputus sesudah server menyimpan;
reload dan retry dengan key sama tetap menghasilkan satu job. Viewer hanya membaca. Admin
mengoreksi job dan saldo kembali ke sewing 20, finishing 0, reject 0. Daftar kosong, kegagalan GET,
Escape, escaping teks, viewport 390 × 844, dan skala teks 200% juga diperiksa.

## Hasil

- `../../.venv/Scripts/python.exe -m unittest discover -s tests -q` dengan `PYTHONPATH`
  diarahkan ke worktree: **120 tests OK** dalam 104,564 detik.
- `node --check beeloft/static/app.mjs`: **PASS**.
- `node tests/test_client.mjs`: **Client checks PASS** dan **CSV client checks PASS**.
- `../../.venv/Scripts/python.exe -m pip check`: **No broken requirements found**.
- Browser suite: seluruh modul lulus, termasuk **Sewing browser QA PASS**, dan pemeriksaan
  akhir tidak menemukan error JavaScript.
- OpenAPI dibuat ulang dari `create_app()`: versi **0.20.0** dan lima path Sewing tersedia.

Screenshot `beeloft-sewing-mobile.png` diperiksa pada ukuran asli; rincian job, biaya, sumber
bundle, hasil, dan turnaround terbaca tanpa overflow horizontal.

## Batas

Pelaksana/vendor masih berupa snapshot teks bebas. Belum ada master vendor, capacity planning,
invoice/pembayaran, formula ongkos per pcs, penerimaan sebagian, rework decision, attachment,
pesan ke vendor, atau barcode scan. Satu job diselesaikan satu kali untuk seluruh jumlah keluar.
