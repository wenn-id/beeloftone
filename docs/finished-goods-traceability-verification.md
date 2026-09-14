# Verifikasi jejak stok barang jadi, v0.62

Tanggal: 14 September 2026. Base `bdd3139`; branch `feature/global-audit-trail`, worktree lokal.
Semua pengujian memakai database sementara, tanpa mengubah data operasional.

## Backend

Dua acceptance test tambahan pada `test_returns_adjustments.py` memeriksa:

- Rantai receipt → reservasi → pick → pack → shipment → return, warehouse movement, adjustment,
  stock opname, koreksi setiap tahap, serta pelepasan reservasi.
- Catatan asli berstatus corrected tetap tampil, sedangkan koreksi mempunyai event tersendiri.
- Stock opname yang menghasilkan adjustment menyimpan kedua catatan dan kedua koreksinya.
- Snapshot database sebelum/sesudah GET identik. Admin, operator, dan viewer menerima laporan yang sama.
- Pemisahan dua receipt pada SKU/QC yang sama, cursor pada timestamp yang sama, dan catatan baru
  di antara dua halaman. Tidak ada duplikasi atau event yang terlewat.
- Validasi limit/cursor, autentikasi, dan receipt yang tidak ditemukan.

Acceptance terkait lulus: 8 test dalam 13,972 detik.
Seluruh regression backend lulus: **297 test dalam 400,972 detik**, melalui
`python -m unittest discover -s tests -p 'test_*.py'`.

## Browser dan visual

Seluruh suite Edge/Playwright lulus tanpa error JavaScript. Modul traceability membuat 52 hitungan
tambahan tanpa selisih pada lot uji, lalu memeriksa halaman pertama 50 event dan halaman lanjutan.
Kegagalan GET awal dan halaman lanjutan dapat dicoba lagi tanpa menghapus/menggandakan riwayat.
Scan QR membuka receipt dan tombol jejak; riwayat menampilkan semua tahap sampai retur dan koreksi.
Viewer dapat menelusuri rincian pengiriman, sedangkan tindakan koreksi tidak muncul.

Screenshot mobile pada lebar 390 px dan teks 200% diperiksa: teks panjang membungkus, tombol terbaca,
dan tidak ada overflow horizontal. Tampilan menggunakan komponen riwayat dan tema proyek yang ada.
Screenshot lokal: `outputs/qa-v062/beeloft-traceability-mobile.png` di workspace induk.

## Pemeriksaan rilis dan batas

Client tests, syntax 49 file JavaScript, compile Python, dan pip check lulus. OpenAPI dan paket
memakai 0.62.0; kontrak GET memuat cursor; schema tetap 48 dan integrity_check mengembalikan ok.
Pemeriksaan `git diff --check` lulus sebelum commit.

Riwayat satu lot disusun di memori; belum ada pengujian lot dengan ribuan event. Posisi stok/status
dihitung per request dan tidak dibekukan antarpaging. Jejak produksi sebelum receipt tersedia melalui
tautan sumber. Settlement finansial dan runtime connector Jubelio/Mekari tetap di luar cakupan.
