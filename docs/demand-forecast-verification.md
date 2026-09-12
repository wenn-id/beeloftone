# Verifikasi demand forecast, v0.37

Tanggal: 13 September 2026. Base `8018803`; branch `feature/demand-forecast` pada worktree
lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Empat acceptance test baru memeriksa dua window historis yang berdampingan, bobot 70/30,
pembulatan HALF_UP, horizon forecast, tanggal `as_of`, shipment aktif, retur aktif, koreksi shipment,
filter marketplace, pencarian SKU/produk, pagination, produk tanpa riwayat, role viewer, validasi
parameter, backup, dan schema versi 30. Contoh utama menghasilkan demand lama 10 pcs, demand terbaru
4 pcs setelah retur, rate forecast 0,4143 pcs/hari, dan forecast 12,43 pcs untuk 30 hari.

Seluruh regression suite backend berisi **205 tests** dan lulus dalam **267,065 detik**. Regresi
terarah untuk margin kontribusi, shipping marketplace, retur/adjustment, dan barang jadi juga lulus.

## Browser dan client

Edge/Playwright menjalankan seluruh browser regression suite. QA forecast memakai shipment 5 pcs
pada window terbaru dan memverifikasi rate 0,5000 pcs/hari serta forecast 7 pcs untuk horizon 14 hari.
Filter tanggal, panjang window, horizon, marketplace, dan SKU; retry setelah respons 503; akses
viewer; escaping teks marketplace; layout mobile; skala teks 200%; dan ketiadaan error JavaScript
semuanya lulus.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.37.0 dan endpoint `GET /api/demand-forecast`. Schema tetap
versi 30 karena fitur ini hanya membaca ledger shipment, retur, koreksi, dan master produk yang sudah
ada.

## Batas

Forecast belum menggabungkan stok, PO inbound, lead time, MOQ, safety stock, promosi, musiman, atau
data eksternal marketplace. `as_of` membatasi tanggal bisnis pada ledger aktif sekarang dan tidak
merekonstruksi waktu pencatatan koreksi. Stockout dan rekomendasi pembelian menjadi milestone
berikutnya.
