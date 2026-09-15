# Tren kualitas produksi dan vendor

## Tujuan

Mengubah catatan final QC yang sudah ada menjadi sinyal kualitas per line internal atau vendor makloon. Planner
dapat melihat yield, tingkat defect, arah perubahan, SKU terdampak, dan catatan sumber tanpa menunggu integrasi
eksternal.

## Dasar hitung

Laporan memakai final QC aktif dengan tanggal inspeksi pada dua periode berurutan yang sama panjang. Jika
`as_of` adalah 30 September dan panjang periode 30 hari, periode aktif adalah 1–30 September dan pembandingnya
2 Agustus–31 Agustus. Catatan final QC yang telah dibalik sebagai koreksi dikeluarkan dari kedua periode.

Setiap catatan dikelompokkan menurut jenis pengerjaan dan nama assignee pada job sewing. Nama dibandingkan tanpa
membedakan huruf besar dan kecil. Metrik yang dihitung:

- first-pass yield = diterima / seluruh pcs yang diperiksa;
- rework rate = rework / seluruh pcs yang diperiksa;
- reject rate = reject / seluruh pcs yang diperiksa;
- nonconforming rate = (rework + reject) / seluruh pcs yang diperiksa;
- perubahan kualitas = nonconforming rate periode aktif dikurangi periode pembanding, dalam poin persentase.

Tren berstatus `worsening`, `improving`, atau `stable` berdasarkan ambang perubahan. Kelompok tanpa data periode
pembanding mendapat `new_baseline`. Status `attention` diberikan jika nonconforming rate mencapai batas peringatan
atau tren memburuk. Ringkasan tetap mewakili seluruh populasi yang cocok dengan filter pencarian dan jenis
pengerjaan sebelum filter status diterapkan.

## Detail dan filter

Setiap kelompok memuat statistik periode aktif dan pembanding, agregat SKU, jenis defect, sumber penanggung jawab,
serta lima final QC terbaru. Pencarian diterapkan pada referensi QC, defect, sumber, assignee, order, SKU, nama
produk, warna, dan ukuran. Filter lain mencakup tanggal akhir, periode 7–365 hari, batas peringatan, ambang
perubahan, jenis pengerjaan, status, limit, dan offset.

## Antarmuka dan API

Pilih **Kualitas produksi** dari navigasi. Dialog menyediakan ringkasan periode, loading, error/retry, empty state,
pagination, tampilan mobile, serta drill-down ke rincian final QC.

`GET /api/production-quality-insights` dapat dibaca admin, operator, dan viewer. Endpoint tidak menulis data dan
tidak menambah tabel, sehingga schema tetap versi 49.

## Batas

Angka mencerminkan final QC yang sudah dicatat, bukan seluruh output produksi yang belum diperiksa. Assignee dan
sumber penanggung jawab berasal dari input operasional sehingga konsistensi penamaan menentukan kualitas
pengelompokan. Laporan tidak menilai akar masalah atau membuat tindakan koreksi otomatis. Runtime connector
Jubelio dan Mekari tetap ditunda sampai akses API resmi tersedia.
