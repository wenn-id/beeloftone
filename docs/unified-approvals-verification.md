# Verifikasi unified approval inbox, v0.31

Tanggal: 12 September 2026. Base `301b377`; branch `feature/unified-approvals` pada
worktree lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Enam acceptance test baru memeriksa inbox gabungan PR/produksi, filter dan pagination, pengajuan
tanpa efek langsung pada order, persetujuan yang menerapkan perubahan dan menghubungkan audit,
penolakan/pembatalan, role, retry idempotent, revision stale, satu permintaan pending per order,
keputusan bersamaan, rollback atomik, backup, ledger immutable, validasi trigger, serta migrasi
schema 25 → 26. Seluruh regression suite berisi **179 tests** dan lulus dalam **257,093 detik**.

## Browser dan client

Browser QA membuka inbox kosong dan memulihkan kegagalan GET, lalu menampilkan PR Rp3.500.000 dan
permintaan perubahan target produksi dalam satu antrean. Respons create perubahan produksi sengaja
diputus setelah server menyimpan; reload dan retry menghasilkan satu permintaan. Order tidak berubah
saat pending. Viewer hanya membaca, operator mengajukan, dan admin menyetujui PR serta perubahan
produksi. Riwayat order terbuat setelah approval dan filter status approved menampilkan kedua objek.

Seluruh browser suite lulus melalui Edge/Playwright tanpa error JavaScript. Viewport 390 × 844,
skala teks 200%, escaping, empty/error state, dan seluruh alur lama turut diperiksa. `node --check`
untuk aplikasi dan browser test lulus. Kontrak `docs/openapi.json` diperbarui ke v0.31.0.

## Batas

Belum ada threshold nilai, approval bertingkat, delegasi, komentar, lampiran, reminder/notifikasi,
supplier-payment approval, marketing-budget approval, atau write ke Mekari/Jubelio. Inbox saat ini
merupakan read model atas dua ledger domain, bukan workflow engine generik.
