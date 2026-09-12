# Verifikasi approval budget marketing, v0.34

Tanggal: 13 September 2026. Base `d0e7b29`; branch `feature/marketing-budget-approvals` pada
worktree lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Acceptance test memeriksa pengajuan, detail, daftar dan pagination, filter status, inbox terpadu,
nominal IDR eksak, periode kampanye, objective, role, cancel oleh pembuat, approve/reject admin,
idempotency, revision guard, keputusan bersamaan, rollback atomik, backup, migrasi schema 28 → 29,
serta ledger immutable. Seluruh regression suite berisi **193 tests** dan lulus dalam **373,878
detik**.

## Browser dan client

Browser QA mengajukan budget sebagai operator dengan simulasi respons terputus. Reload dan retry
memakai idempotency key yang sama dan menghasilkan satu request. Viewer membaca daftar/detail tanpa
tombol pengajuan atau keputusan. Admin menyetujui dari inbox terpadu, lalu hasilnya muncul pada
filter approved. Nama kampanye memakai karakter HTML untuk memeriksa escaping; viewport mobile dan
skala teks 200% turut diperiksa. Seluruh Edge/Playwright suite lulus tanpa error JavaScript.

## Batas

Approved berarti plafon kampanye disahkan. Belum ada realisasi belanja, saldo budget, vendor/media
plan, PO, invoice platform, pembayaran, reimbursement, jurnal, attachment, threshold, approval
bertingkat, komentar, reminder, notifikasi, atau integrasi Mekari/Jubelio.
