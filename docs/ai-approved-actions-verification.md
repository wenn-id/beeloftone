# Verifikasi proposal dan eksekusi tindakan AI, v0.40

Tanggal: 13 September 2026. Base `453b30c`; branch `feature/ai-approved-actions` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Lima acceptance test baru memeriksa proposal order produksi dan PR, derivasi jumlah dari rekomendasi
server, ketiadaan transaksi sebelum approval, unified inbox, akses viewer/operator/admin, keputusan
idempotent, cancellation/rejection, filter, stale recommendation, rollback atomik, ledger immutable,
backup, dan migrasi schema 30 ke 31.

Seluruh suite backend lulus: **218 test dalam 428,179 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`).

Approval produksi membuat tepat satu order 156 pcs pada fixture backend. Approval pembelian membuat PR
submitted 253,875 meter dengan estimasi nilai yang diisi pengguna. Penambahan PR lain setelah proposal
dibuat mengubah rekomendasi dan membuat approval lama ditolak tanpa menambah PR atau event keputusan.

## Browser dan client

Edge/Playwright menjalankan seluruh browser regression suite. Operator mengajukan order 20 pcs dari
rekomendasi `COST-UI`, browser kehilangan response pertama, lalu memulihkan proposal dengan
Idempotency-Key yang sama setelah reload. Viewer tidak melihat kontrol keputusan. Admin menyetujui dan
satu order tertaut dibuat. Escaping HTML, Inbox Approval, form dan detail pada layar 390 px, skala teks
200%, keyboard Escape, dark theme, dan ketiadaan error JavaScript ikut diperiksa.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.40.0 dan keempat endpoint proposal tindakan AI. Schema
database adalah versi 31.

## Batas

Eksekusi hanya mendukung order produksi satu SKU dan PR satu bahan dari rekomendasi stockout. Approval
PR AI membuat pengajuan purchasing, bukan menyetujui pembeliannya. Proposal tidak menjalankan
perubahan bebas, approval massal, atau write ke sistem eksternal.
