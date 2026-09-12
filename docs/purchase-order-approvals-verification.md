# Verifikasi approval penerbitan Purchase Order, v0.32

Tanggal: 12 September 2026. Base `e0e657b`; branch `feature/purchase-order-approvals` pada worktree
lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Acceptance test memeriksa PO pending dan inbox terpadu, filter status/jenis, role pengaju dan
pemutus, pembatalan pemohon, penolakan dan PO pengganti, idempotency, revision guard, keputusan
bersamaan, rollback atomik, ledger immutable, serta guard SQLite terhadap receipt, QC intake, dan
pembatalan sebelum approval. Migrasi schema 26 → 27 diuji dua kali dan membuktikan PO historis
dibackfill approved tanpa mengubah status bisnisnya. Seluruh regression suite berisi **183 tests**
dan lulus dalam **316,467 detik**.

## Browser dan client

Browser QA membuat PO dengan simulasi respons create yang terputus, reload, lalu retry dengan key
yang sama. Rincian menampilkan status pending dan menyembunyikan penerimaan serta QC. PO ditemukan
di inbox terpadu, disetujui admin, berubah aktif, dan riwayat approval tampil sebelum alur
pembatalan lama dijalankan. Seluruh alur receipt, incoming QC, retur supplier, produksi, gudang,
marketplace, retur pelanggan, stock opname, dan unified approvals lama juga dijalankan. Seluruh
Edge/Playwright suite lulus tanpa error JavaScript, termasuk viewport mobile dan skala teks 200%.
`node --check` untuk aplikasi serta seluruh browser test lulus. Kontrak `docs/openapi.json`
diperbarui ke v0.32.0.

## Batas

Belum ada threshold nilai, approval bertingkat, matriks approver, dokumen PO, pengiriman ke pemasok,
komentar, reminder/notifikasi, supplier-payment approval, atau integrasi Mekari/Jubelio.
