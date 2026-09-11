# Verifikasi final QC — v0.22

Tanggal: 11 September 2026. Base `f5a498d`; branch `feature/final-qc` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Enam acceptance test baru memeriksa inspeksi parsial, temuan ukur/visual wajib, pembagian accepted,
rework, dan reject, lineage lengkap, tiga perpindahan WIP atomik, alokasi sumber, idempotent retry,
role, koreksi utuh, blok koreksi finishing dan movement terkait, transaksi bersamaan, rollback,
rework downstream, backup, direct-write guard, ledger immutable, serta migrasi schema 16 → 17.
Seluruh regression suite berisi **132 tests** dan lulus dalam **83,642 detik**.

## Browser dan client

Browser QA memeriksa 13 dari 20 pcs: 10 diterima gudang, 2 rework, dan 1 reject. Saldo menjadi
QC 7, gudang 10, rework 2, reject 1. Respons create sengaja diputus setelah server menyimpan;
reload dan retry dengan key yang sama tetap menghasilkan satu catatan. Viewer hanya membaca.
Koreksi finishing ditolak selama final QC aktif, lalu koreksi final QC mengembalikan saldo menjadi
QC 20, gudang 0, rework 0, reject 0. Daftar kosong, kegagalan GET, Escape, escaping teks, viewport
390 × 844, dan skala teks 200% lulus tanpa error JavaScript.

`node --check beeloft/static/app.mjs`, `node tests/test_client.mjs`, dan pemeriksaan CSV client
lulus. Screenshot `beeloft-final-qc-mobile.png` diperiksa pada ukuran asli; outcome, temuan,
lineage, tanggal, alasan, aktor, dan aksi terbaca tanpa overflow horizontal.

## Batas

Pengukuran dan visual berupa catatan bebas. Belum ada template/toleransi per SKU, sampling plan,
kode defect, foto, tanda tangan, atau instruksi rework terstruktur. Satu catatan dikoreksi seluruhnya;
buat catatan pengganti untuk hasil yang benar.
