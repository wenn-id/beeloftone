# Verifikasi approval pembayaran supplier, v0.33

Tanggal: 12 September 2026. Base `1463485`; branch `feature/supplier-payment-approvals` pada
worktree lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Acceptance test memeriksa syarat PO approved dan receipt aktif, nilai penerimaan parsial, batas
nominal kumulatif pending/approved, pelepasan nominal setelah reject/cancel, request pada PO closed,
role, idempotency, revision guard, pagination, keputusan bersamaan, dua request nominal yang
bersaing, rollback atomik, backup, migrasi schema 27 → 28, serta ledger immutable. Trigger SQLite
mencegah koreksi receipt bila nilai penerimaan tersisa tidak lagi menutup request aktif. Seluruh
regression suite berisi **189 tests** dan lulus dalam **383,623 detik**.

## Browser dan client

Browser QA membuat PR, PO approved, dan receipt, lalu mengajukan pembayaran dengan simulasi respons
terputus. Reload dan retry memakai idempotency key yang sama dan menghasilkan satu request. Operator
mengajukan, viewer membaca tanpa tombol keputusan, dan admin menyetujui dari inbox terpadu. Detail
PO menampilkan nominal pending, approved, serta sisa; invoice berisi karakter HTML untuk memeriksa
escaping. Viewport mobile dan skala teks 200% turut diperiksa. Seluruh Edge/Playwright suite lulus
tanpa error JavaScript. `node --check` untuk aplikasi dan seluruh browser test lulus. Kontrak
`docs/openapi.json` diperbarui ke v0.33.0.

## Batas

Approved berarti siap dibayar. Belum ada transfer bank, status paid/failed, jurnal, pajak,
withholding, attachment invoice, credit note, invoice lintas PO, threshold, approval bertingkat,
komentar, reminder, notifikasi, atau integrasi Mekari/Jubelio.
