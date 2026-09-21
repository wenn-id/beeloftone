# M01: kesiapan master produk, bahan dan satuan

Persiapan [#43](https://github.com/wenn-id/beeloftone/issues/43), diperiksa pada
22 September 2026, commit `145e734496037d136d786a45e772f74d48279d7c`,
v0.97.0/schema 55. **BLOCKED_F02: belum implementasi atau business accepted.**

PR F02 #77 sudah merged, tetapi [kontrak F02](f02-shared-contracts.md) masih
DRAFT dan secara eksplisit belum membuka implementasi domain. Issue #41 masih
terbuka; sign-off A1/A2/A3 dan A0/pemilik bisnis masih PENDING. Merge dokumen ini
tidak menyelesaikan #43 atau mengesahkan keputusan bisnis.

## Pemetaan HEAD ke hasil kerja M01

| Area | Perilaku existing dan sumber | Gap yang harus ditutup setelah kontrak diterima |
|---|---|---|
| Identitas produk | `ProductCreate` menerima SKU, nama, warna, ukuran; SKU dipangkas dan diubah ke huruf besar. `products.id` UUID server, SKU unik `COLLATE NOCASE` ([model](../beeloft/models.py), [schema](../beeloft/schema.sql)) | Kategori/subkategori/tipe/seri, status aktif dan mapping ID legacy belum tersedia. Jangan mengganti ID/FK atau menormalkan ulang SKU existing |
| Identitas bahan | `MaterialCreate` menerima kode, nama, unit `m/kg/pcs`; kode dinormalisasi dan unik tanpa membedakan kapital. Master immutable ([materials.sql](../beeloft/materials.sql)) | Belum warna/ukuran bahan, klasifikasi, harga referensi, status aktif, atau mapping ID legacy |
| Duplikat dan impor | POST master duplikat memberi 409; retry memakai receipt `_write`. Mapping produk Jubelio punya revision, histori dan guard benturan ID/SKU ([test_product_external_mappings.py](../tests/test_product_external_mappings.py)) | Belum importer master legacy atau namespace material. Mapping Jubelio tidak membuktikan impor legacy aman; harus ada pemetaan sumber eksplisit dan laporan penolakan |
| Qty dasar | Produk integer pcs; bahan string Decimal sampai 3 desimal disimpan sebagai `quantity_milli`; bahan pcs wajib bulat (`Store._material_amount`) | Belum input lusin/konversi berversi. Aturan unit tambahan dan presisi harus diputuskan; jangan mengubah angka ledger existing |
| Harga bahan | Harga aktual PO dan analitik harga tersedia; costing memakai harga PO batch ([test_material_price_insights.py](../tests/test_material_price_insights.py), `Store.production_cost`) | Harga referensi master belum ada. Pemilik harus menetapkan currency, basis unit, tanggal berlaku, dan perbedaannya dengan harga transaksi; bukan fallback otomatis biaya historis |
| Template/BOM | BOM per SKU sudah append-only, beralasan, dijaga revision dan idempotency (`Store.save_bom`, [bom.sql](../beeloft/bom.sql)) | Belum lineage template legacy ke revision BOM. Pakai mekanisme BOM existing; tentukan identitas sumber, duplikat, dan konflik template |
| UI/transaksi | Master SKU bisa dicari lokal berdasarkan SKU/nama/warna-ukuran/external SKU; form order memakai ID produk. Master bahan tersedia sebagai daftar/dialog dan pilihan pada transaksi ([app.mjs](../beeloft/static/app.mjs)) | Master bahan belum punya pencarian teks; metadata baru, konversi dan nonaktif belum punya UI/error state. Verifikasi pencarian dan pilihan transaksi setelah implementasi |

`GET /api/products` dan `GET /api/materials` saat ini hanya menerima limit/offset,
bukan filter pencarian server. `allRows` memuat semua halaman untuk pilihan UI.
Izin baseline: admin membuat master, mapping dan BOM; reader harus terautentikasi.
Ini perilaku teknis existing, bukan persetujuan matriks role perusahaan D17.

## Keputusan yang dibutuhkan

Semua referensi berikut masih OPEN dalam [register F01](f01-decisions-evidence.md).
Pemilik mengisi jawaban, scope, tanggal efektif, approver dan referensi bukti aman
dipublikasikan. Tidak ada nilai default bisnis yang ditetapkan paket ini.

| Referensi | Jawaban yang diperlukan untuk M01 |
|---|---|
| D01 / EX01 | Kamus kolom legacy ke One: wajib/opsional/dihapus beserta alasan; hierarki kategori/subkategori/tipe/seri; makna warna/ukuran bahan; keunikan dan namespace ID; duplikat ditolak atau dipetakan; arti aktif/nonaktif untuk transaksi baru, saldo dan koreksi lama |
| D01, D03 bila unit tambahan dipakai | Unit dasar tiap jenis barang, konversi fisik pcs/lusin dan presisinya, apakah unit dasar existing boleh berubah, cara menyimpan input/unit/faktor/revisi asal tanpa menafsirkan ulang histori; rol/lembar/setelan tidak diberi faktor tebakan |
| D01, D13 bila harga dipakai untuk costing | Definisi harga referensi bahan, unit/currency/efektivitas, izin edit dan apakah hanya referensi input. Pemakaian untuk valuasi menunggu keputusan costing |
| D17 / EX12 | Role yang membaca, membuat, mengubah klasifikasi/harga, menonaktifkan, mengimpor dan menyetujui mapping; scope unit bila diperlukan |
| D18/D19 bila impor/cutover dipakai | Namespace sumber, authority dan cutoff; pemetaan ke ID internal existing; sumber template dan revision BOM; dry-run serta rekonsiliasi record ditolak/dipetakan |
| F02 / A0 | Penerimaan kontrak M01 oleh domain terkait, reservasi fungsi/file bersama dan nomor migrasi berdasarkan HEAD saat integrasi |

Konversi fisik 12 pcs = 1 lusin tidak menetapkan pembulatan upah 13 pcs.
Rumus payable dan tarif tetap di luar M01 dan menunggu D04. Dokumen ini juga
tidak menganggap semua keputusan F01 lintas domain harus diimplementasikan M01.

## Batas perubahan dan acceptance setelah gerbang terbuka

1. Pertahankan ID/SKU/kode existing beserta seluruh FK. Impor ulang dengan HTTP
   key berbeda tetap tidak boleh membuat master ganda untuk identitas sumber
   yang sama; konflik dilaporkan tanpa menimpa data. Buat kasus sintetis ID sama
   lintas namespace, SKU beda kapital, dan satu ID legacy menuju dua master.
2. Simpan qty ledger dalam unit dasar. Uji input pcs/lusin termasuk 1, 11, 12,
   13 pcs, batas presisi dan overflow setelah konversi. Unit/faktor/revisi input
   harus dapat ditelusuri; expected result mengikuti kontrak yang diterima.
3. Perubahan kategori atau unit tidak boleh mengubah saldo/biaya historis.
   `_material_batch` dan `_bom` saat ini membaca unit dari master terkini:
   mengizinkan edit `materials.unit` langsung berisiko menafsirkan ulang histori.
   Pilih aturan perubahan unit bersama pemilik sebelum menulis migrasi.
4. Gunakan `bom_revisions` untuk versi template. `material_requirements` saat ini
   membaca BOM terbaru untuk estimasi, termasuk order lama; ini berbeda dari
   stok/pengeluaran aktual. Uji kedua hal secara terpisah dan jangan mengklaim
   estimasi lama terkunci. Perubahan BOM tidak boleh menulis ulang pergerakan.
5. Cakup pencarian produk/bahan dan pemilihan ID yang benar pada order, penerimaan,
   PO dan BOM; uji kosong, gagal, retry, nonaktif, keyboard dan role terlarang.
   Nonaktif tidak boleh menghilangkan tampilan histori atau koreksi yang sah.
6. Mutasi tetap melalui `_write`: actor/role, idempotency, revision, audit dan
   rollback atomik. Uji konflik dua penyimpan dan gagal penyimpanan. Konversi
   bahan menyentuh receipt/issue/reservation/consumption, PO/QC, BOM dan
   replenishment; telusuri seluruh pemanggil `_material_amount`, bukan satu form.
7. Nomor migrasi belum dipesan. Saat A0 membuka implementasi, cek HEAD dan
   koordinasikan nomor; uji DB baru, upgrade schema 55, rerun, FK/integrity,
   control totals sebelum/sesudah dan backup/restore dengan data sintetis.

## Bukti dan handoff persiapan

Suite existing yang relevan dapat dijalankan dari root repo (PowerShell):

```powershell
$env:PYTHONPATH = 'tests'
python -m unittest test_f02_contracts test_production test_materials test_bom test_product_external_mappings test_material_price_insights -v
```

Eksekusi 22 September 2026: **39 tes lulus** dengan Python 3.12.13; pemeriksaan
dependency `uv pip check` juga lulus. Commit akhir dicatat di PR. Tes ini membuktikan baseline,
bukan acceptance impor, konversi, perubahan master atau UI baru yang belum ada.
Browser acceptance baru belum dijalankan karena tidak ada perubahan UI.

Branch persiapan: `docs/m01-master-readiness`. File berubah: dokumen ini dan tautan
README. Tidak ada perubahan API/model/store/UI/schema, dependency atau versi.
Reviewer yang diperlukan: A1 sebagai pemilik paket, A2 untuk konsumsi stok/biaya,
A3 untuk identitas sumber/impor, A0 untuk kontrak/migrasi; belum ada review atau
sign-off bisnis yang diklaim. PR tetap draft dan #43 tetap terbuka sampai kontrak
diterima, implementasi selesai dan seluruh acceptance diverifikasi.
