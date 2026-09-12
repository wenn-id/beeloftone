# Verifikasi AI investigation, v0.39

Tanggal: 13 September 2026. Base `00a34b5`; branch `feature/ai-brain-investigation` pada worktree
lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Empat acceptance test baru memeriksa routing pertanyaan ke overview, produksi, stockout, approval, dan
margin; fokus berdasarkan SKU atau referensi order; fakta dan sumber; status rekomendasi yang wajib
approval dan tidak dapat dieksekusi; akses seluruh role; validasi request; backup; schema 30; serta
ketiadaan perubahan jumlah transaksi setelah investigasi.

Seluruh regression suite backend berisi **213 tests** dan lulus dalam **259,522 detik**.

## Browser dan client

Edge/Playwright menjalankan seluruh browser regression suite. Skenario AI memakai viewer untuk
menanyakan risiko stockout `COST-UI`, menerima rekomendasi produksi 20 pcs dan pembelian bahan,
memastikan tidak ada order atau PR baru, lalu memeriksa retry setelah 503, draft pertanyaan tetap ada,
header write-idempotency tidak dikirim, escaping HTML, shortcut pertanyaan, Escape, layar 390 px, dan
skala teks 200%. Seluruh alur lulus tanpa error JavaScript.

Client test memverifikasi POST hanya baca memakai pesan kegagalan pembacaan dan tidak dianggap sebagai
hasil penyimpanan yang belum pasti. Syntax check mencakup aplikasi serta seluruh browser test.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.39.0 dan endpoint `POST /api/ai/investigate`. Schema tetap
versi 30 karena fitur hanya menyusun hasil dari ledger yang sudah ada.

## Batas

Pemetaan bahasa memakai aturan kata kunci lokal dan dapat salah pada pertanyaan ambigu. Investigasi
tidak disimpan, belum memakai feedback, belum memanggil model eksternal, dan tidak dapat menjalankan
rekomendasi. Action proposal yang persisten, approval manusia, dan eksekusi terjaga menjadi milestone
Phase 6 berikutnya.
