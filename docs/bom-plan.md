# BOM dasar dan kebutuhan bahan — Phase 2

Melanjutkan blueprint halaman 8 dan 15–16 di branch lokal `feature/core-materials`, dasar `117b24f`. Tidak push atau merge main.

Admin menyimpan satu BOM per SKU sebagai versi immutable. Satu versi berisi 1–100 bahan unik dan jumlah per pcs, mengikuti satuan master (m/kg/pcs). Kuantitas string desimal, maksimal tiga desimal dan 1.000.000 satuan per pcs; bahan pcs harus bulat. Simpan memerlukan alasan dan expected_revision; perubahan dari tab lama ditolak. Revisi kosong belum ada berarti revision 0. Tidak ada hapus/nonaktif BOM pada increment ini; koreksi dengan versi baru. Retry memakai receipt transaksi yang sudah ada.

Read-only kebutuhan order menggunakan BOM terbaru tiap SKU, dengan daftar revisi sumber. Ini estimasi saat dimuat, bukan snapshot BOM saat order dibuat. Rumus per bahan: kebutuhan = jumlah target SKU × jumlah BOM, digabung lintas SKU; dikeluarkan bersih = pengeluaran ke order dikurangi pembalikannya; sisa kebutuhan = max(kebutuhan − dikeluarkan, 0); kekurangan = max(sisa kebutuhan − saldo semua batch di rak, 0). Bahan dikeluarkan di luar BOM tetap ditampilkan dan ditandai. WIP/reject tidak mengurangi target perencanaan. SKU tanpa BOM ditandai belum lengkap; hasil parsial tidak boleh dinyatakan cukup untuk keseluruhan order.

Perhitungan memakai integer thousandths Python agar hasil agregasi besar tidak melampaui integer SQLite. Output jumlah berupa string desimal. Baca dalam satu transaksi snapshot. Tidak memindahkan stok, mereservasi, mengunci produksi, memasukkan allowance waste, atau menghitung biaya. Saldo yang sama masih bisa digunakan order lain. Akses baca semua role; write admin aktif dengan audit.

Implementasi inline:

- [x] Acceptance tests `tests/test_bom.py`: aggregation, issue/reversal, missing BOM, exact arithmetic, revision conflict/retry, validation/roles, migration/rollback.
- [x] Schema 5 `bom.sql`; input models; store methods and API GET/POST `/api/products/{id}/bom`, GET `/api/products/{id}/bom-history`, GET `/api/orders/{id}/material-requirements`.
- [x] UI Master SKU → BOM (lihat, riwayat, ubah) dan order → Kebutuhan bahan; gunakan dialog/form/recovery/guards yang sudah ada. Uji browser dan mobile.
- [x] Full tests, review independen, README/OpenAPI/verifikasi; commit lokal.
