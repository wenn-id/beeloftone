# Verifikasi finishing — v0.21

Tanggal: 11 September 2026. Base `02456bd`; branch `feature/finishing` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Enam acceptance test baru memeriksa catatan parsial, lima checklist wajib, tanggal selesai,
lineage ke sewing/bundle/cutting/batch, perpindahan finishing ke QC, alokasi sumber, idempotent
retry, role, koreksi utuh, blok koreksi sewing dan movement terkait, transaksi bersamaan,
rollback, downstream warehouse, backup, direct-write guard, ledger immutable, serta migrasi
schema 15 → 16. Seluruh regression suite berisi **126 tests** dan lulus dalam **57,344 detik**.

## Browser dan client

Browser QA mencatat 6 dari 16 pcs hasil sewing setelah kelima checklist dikonfirmasi. Saldo
menjadi finishing 10, QC 6, reject 4. Respons create sengaja diputus setelah server menyimpan;
reload dan retry dengan key yang sama tetap menghasilkan satu catatan. Viewer hanya membaca.
Koreksi sewing ditolak selama finishing aktif, lalu koreksi finishing mengembalikan saldo menjadi
finishing 16, QC 0, reject 4. Daftar kosong, kegagalan GET, Escape, escaping teks, viewport
390 × 844, dan skala teks 200% juga lulus tanpa error JavaScript.

`node --check beeloft/static/app.mjs`, `node tests/test_client.mjs`, dan pemeriksaan CSV client
lulus. Screenshot `beeloft-finishing-mobile.png` diperiksa pada ukuran asli; checklist, lineage,
jumlah, tanggal, alasan, aktor, serta aksi terbaca tanpa overflow horizontal.

## Batas

Catatan hanya menyimpan checklist yang sudah lengkap dan belum menyimpan waktu mulai/selesai per
aktivitas, pekerja atau stasiun per langkah, bahan habis pakai, SKU kemasan, attachment, barcode,
atau exception khusus finishing. Satu catatan dikoreksi seluruhnya; buat catatan pengganti untuk
jumlah yang benar.
