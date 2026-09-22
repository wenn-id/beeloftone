# B01: kesiapan validasi parity pembelian

Persiapan [#50](https://github.com/wenn-id/beeloftone/issues/50), diperiksa pada
22 September 2026, commit `4ede366f055473c4414fa7bb4542953db300ab95`,
v0.97.0/schema 55. **BLOCKED_M01_M02_F02: belum parity atau business accepted.**

Dependensi #43/#44/#41 masih terbuka. [M01](m01-master-readiness.md) dan
[M02](m02-master-readiness.md) baru dokumen kesiapan; [F02](f02-shared-contracts.md)
masih DRAFT dengan sign-off PENDING. D12 dan contoh EX08 dalam
[F01](f01-decisions-evidence.md) belum disahkan. Sesuai #50, implementasi yang
bergantung pada kontrak tersebut belum dimulai. Bukti di bawah menguji baseline
dan menyiapkan perbandingan; bukan hasil observasi proses nyata atau persetujuan
penghapusan proses legacy.

## Pemetaan proses dan batas baseline

| Proses | Padanan existing dan sumber | Yang perlu dibandingkan dengan EX08 |
|---|---|---|
| Permintaan pembelian (PR) | `PurchaseRequestCreate`: bahan/qty, estimasi, tanggal kebutuhan, alasan, optional order produksi; submitted/approved/rejected/cancelled, revision/idempotency ([test_purchase_requests.py](../tests/test_purchase_requests.py)) | Kolom/dokumen wajib, approval dan revisi kebutuhan/budget. Tidak ada efek stok dari PR |
| Supplier dan PO | PO dari PR approved pada revision terkini; satu supplier, seluruh bahan/qty PR, harga per unit dan termin tersimpan sebagai snapshot. PO submitted/pending menjadi approved/issued atau rejected/cancelled ([test_purchase_orders.py](../tests/test_purchase_orders.py), [test_purchase_order_approvals.py](../tests/test_purchase_order_approvals.py)) | Split supplier/PO, revisi qty/harga, pajak/diskon/ongkir, mata uang dan dokumen pengiriman bila dipakai. Satu PR tidak bisa memiliki lebih dari satu PO aktif atau closed; issued bukan bukti PO dikirim keluar |
| Penerimaan langsung | PO issued dan material harus cocok dengan line; receipt parsial membuat batch dan ledger stok. Qty dibatasi sisa PO setelah hold. Supplier diturunkan dari snapshot PO ([test_po_receipts.py](../tests/test_po_receipts.py)) | Kapan boleh menerima tanpa QC, dokumen surat jalan, toleransi lebih/kurang dan duplikat dokumen supplier. Baseline menolak jumlah lebih tanpa toleransi |
| Kedatangan dan QC | Intake menahan kuota PO, belum stok layak pakai; accept parsial membuat batch/receipt, reject tidak. Koreksi menjaga kuota, pemakaian dan coverage pembayaran ([test_incoming_qc.py](../tests/test_incoming_qc.py)) | Kolom inspeksi dan otorisasi sebenarnya; kapan invoice masuk, apakah invoice boleh mendahului QC, serta penanganan mismatch |
| Retur supplier | Retur parsial dari reject QC dan reversal berjejak. Pengiriman retur tidak menambah stok atau kuota pengganti kedua ([test_supplier_returns.py](../tests/test_supplier_returns.py)) | Bukan retur umum barang yang sudah diterima/terpakai, credit note atau refund uang. Proses itu belum punya kontrak native dan tidak dianggap dihapus |
| Close/cancel | Close PO issued setelah ada penerimaan layak pakai, hold dan return pending nol; boleh partial. Qty/harga/sisa tetap terlihat, receivable menjadi nol. Cancel untuk PO tanpa penerimaan aktif/hold/retur tertunda | Aturan close/reopen/revisi setelah close dan dokumen persetujuan D12. Baseline close mengunci receipt/QC/retur beserta koreksi, tetapi stok diterima masih bisa dipakai dan pembayaran masih bisa diajukan |
| Invoice/pengajuan pembayaran | Satu payment request menunjuk satu PO; invoice reference/tanggal/jatuh tempo/amount menjadi metadata. Submitted/approved memakai batas nilai penerimaan, bukan seluruh nilai pesanan ([supplier_payment_approvals.sql](../beeloft/supplier_payment_approvals.sql), [test_supplier_payment_approvals.py](../tests/test_supplier_payment_approvals.py)) | Belum entitas invoice supplier, matching baris invoice-receipt, multi-PO atau bukti bayar/alokasi native. Approval bukan kas keluar; scope B02/A01 mengikuti D12/D14 |
| Biaya bahan | Harga PO terkunci; `production_cost` memakai konsumsi aktual termasuk waste dari batch berharga PO, bukan seluruh nilai pembelian. Harga tidak tersedia menghasilkan coverage gap ([test_production_cost.py](../tests/test_production_cost.py)) | Valuasi/COGS dan alokasi biaya tambahan D13 belum ditetapkan. Analitik harga atau costing operasional bukan jurnal/AP |

Sumber runtime: [models.py](../beeloft/models.py), [store.py](../beeloft/store.py),
[api.py](../beeloft/api.py). UI sudah memiliki PR, PO, QC/retur dan approval
supplier di [app.mjs](../beeloft/static/app.mjs); ini inspeksi sumber, bukan
browser acceptance atau pembuktian bahwa semua dokumen legacy tersedia.

Izin server baseline: admin membuat supplier; admin/operator mengajukan PR/PO,
receipt/intake dan pembayaran; admin memutuskan approval/QC, retur/reversal,
cancel PO issued dan close. Pemohon boleh membatalkan pengajuan sendiri pada
state yang didukung. Reader terautentikasi. Role tersebut belum pengesahan
matriks purchasing/gudang/finance perusahaan D17.

## Hubungan receipt, invoice dan permintaan pembayaran

Pada HEAD, `purchase_order_receipts` menghubungkan batch ke PO; QC accept juga
membuat hubungan yang sama. `_purchase_order` menjumlah receipt aktif per
material, menghitung nilai dengan harga PO dan half-up dua desimal per line,
lalu mengurangi request submitted/approved untuk mendapatkan `payment_remaining`.
Reversal receipt tidak boleh menurunkan coverage di bawah komitmen tersebut.

`supplier_payment_requests` memiliki `purchase_order_id` dan metadata invoice,
tetapi tidak memiliki alokasi per receipt atau FK invoice. Unik
`(purchase_order_id, invoice_reference)` berlaku juga untuk request yang sudah
rejected/cancelled; ini bukan identitas invoice global atau dukungan cicilan.
Supplier respons diambil dari PO. Receipt menolak field supplier yang disisipkan
klien (422); tes ini **bukan** bukti invoice salah supplier bisa dideteksi,
karena invoice native dan supplier invoice terpisah belum ada.

Kontrak target **PROPOSED**, menunggu D12: tentukan identitas invoice beserta
supplier/currency, hubungan satu/banyak PO dan receipt bila dipakai, alokasi
qty/nominal serta toleransi matching. Pisahkan invoice, approval request,
pembayaran aktual dan posting. B01 menyerahkan sumber receipt/retur/close ke
B02/A01; jangan membuat AP atau kas bergerak hanya karena approval berubah.
Referensi [A01](a01-ledger-readiness.md) dan F02 tetap menunggu penerimaan.

## Keputusan dan bukti sebelum parity

| Referensi / penentu | Bukti yang diperlukan |
|---|---|
| D12 / EX08; purchasing + gudang + AP/finance | Satu contoh aman setiap jalur PR/PO/receipt/QC/retur/close yang dipertahankan, termasuk split, partial, revisi, pembatalan dan koreksi bila dipakai. Kamus kolom/status/dokumen, aktor, input, hasil dan padanan One; proses dihapus hanya dengan keputusan eksplisit pemilik |
| D12; AP/accounting | Invoice vs receipt, supplier/material/qty/harga yang harus cocok, toleransi, invoice sebelum receipt/QC, invoice duplikat lintas PO, credit note, partial/multi-PO dan koreksi setelah approved/paid/posted. Isi expected result; jangan mengubah constraint invoice tanpa kontrak |
| D01 / M01/M02 | Penerimaan ID supplier/material/unit/lokasi, nonaktif dan mapping legacy, unit dasar serta konversi. Nama supplier teks pada batch bukan pengganti identitas pihak stabil |
| D13/D14; accounting | Biaya bahan, pajak/diskon/ongkir bila diperlukan, aturan pembulatan/valuasi, event pengakuan utang/biaya dan sumber posting. Receipt, invoice dan pembayaran tidak boleh menggandakan biaya |
| D16/D17; pemilik laporan/role | Dokumen detail/cetak/ekspor, role dan scope unit untuk setiap langkah, serta pemisahan pemohon/penerima/approver/pembayar bila diperlukan |
| F02 / A0 bersama A1/A2/A3 | Penerimaan kontrak dan koordinasi fungsi/file/migrasi. D18/D19 bila impor dipakai: namespace, cutoff dan deduplikasi dokumen sumber meski key HTTP berbeda |

Semua keputusan memuat scope, jawaban, approver, tanggal efektif dan bukti aman
dipublikasikan. EX08 belum tersedia/disahkan; tabel padanan ini bukan daftar
lengkap proses nyata. Catat jalur yang belum teramati sebagai unresolved, bukan
dianggap tidak dipakai. B01 tidak menetapkan formula settlement non-PO B02.

## Rekonsiliasi sintetis dan acceptance

Tes `test_close_requires_hold_and_rejected_material_resolved` pada
[test_supplier_returns.py](../tests/test_supplier_returns.py) diperkuat tanpa
menambah jumlah tes. Nilai berikut seluruhnya sintetis, membuktikan aturan kode
existing dan bukan persetujuan aturan bisnis perusahaan.

| Tahap | Hasil yang diuji |
|---|---|
| PO 2.125 m × 12.34, intake hold seluruh qty | Nilai PO 26.22; nilai penerimaan untuk payment request masih 0.00 |
| Accept 1.125 m, reject 1.000 m | Nilai penerimaan 13.88; close ditolak selama masih hold atau reject belum diretur |
| Retur 1.000 m, close parsial dan retry | Status closed/partial, nilai PO tetap 26.22; received 1.125, remaining 1.000, returned 1.000, held/return pending/receivable nol. Nilai penerimaan tetap 13.88 |
| Ajukan 13.89 lalu 13.88 dan retry | Kelebihan 0.01 ditolak 409 tanpa request tersimpan. Nilai valid membuat tepat satu submitted request dengan supplier snapshot PO; pending 13.88, approved 0.00, remaining 0.00 |
| Koreksi setelah close | Reversal retur dan QC accept ditolak; stok layak pakai tetap 1.125 m. Tidak ada klaim bahwa request submitted sudah dibayar |

Tes existing lainnya mencakup partial receipt/return/reversal, output stok,
material di luar PO, pemalsuan supplier receipt, jumlah lebih, harga per line,
budget, retry, concurrency, role, audit rollback, migrasi dan backup. Tes costing
memeriksa konsumsi/waste berharga dan coverage gap, bukan pengakuan AP/COGS.

Setelah dependensi dan D12 diterima, acceptance B01 harus membuktikan:

1. Setiap proses EX08 punya padanan UI/API/field/status/dokumen yang diuji atau
   keputusan penghapusan yang disetujui pemilik; hanya gap terbukti ditambahkan.
2. Kasus salah supplier invoice/receipt, material/qty/harga tidak cocok, invoice
   duplikat, receipt/retur parsial, jumlah lebih dan close menghasilkan output
   sesuai contoh disahkan. Validasi dilakukan server, bukan hanya filter form.
3. Qty/uang, idempotency, revision, transaksi atomik, audit/reversal serta batas
   approval/paid/posted dipertahankan. Uji dua penulis, retry key berbeda dengan
   identitas dokumen sama, dan rollback bila penyimpanan audit gagal.
4. Detail/dokumen/ekspor menunjukkan sumber PR/PO/receipt/invoice, supplier,
   nominal/sisa/status/koreksi sesuai kontrak; uji kosong/error/retry/keyboard
   dan role terlarang. Jangan menafsirkan label approved sebagai bukti bayar.
5. Nomor migrasi dikoordinasikan A0, belum dipesan. Uji DB baru, upgrade schema
   55/rerun, FK/integrity, control totals qty/uang per PO/batch, backup/restore
   dan kompatibilitas histori. Jangan membuat invoice dari metadata lama tanpa
   mapping dan aturan duplikat yang diterima.

## Verifikasi dan handoff

Dari root repo, Python 3.12 dengan dependencies terpasang, PowerShell:

```powershell
$env:PYTHONPATH = 'tests'
python -m unittest test_f02_contracts test_purchase_requests test_purchase_orders test_purchase_order_approvals test_po_receipts test_incoming_qc test_supplier_returns test_supplier_payment_approvals test_production_cost test_material_price_insights -v
```

Eksekusi 22 September 2026 dengan Python 3.12.13: **48 tes lulus** dalam
106.323 detik. `uv pip check --python .venv/Scripts/python.exe` lulus untuk
22 package. Browser acceptance tidak dijalankan karena UI tidak berubah;
tes baseline bukan sign-off EX08.

Branch: `docs/b01-purchasing-parity-readiness`. File berubah: dokumen ini,
README dan `tests/test_supplier_returns.py`. Commit akhir dicatat di PR.
Runtime/API/UI, dependency dan v0.97.0/schema 55 tidak berubah. Risiko tersisa:
master/kontrak belum diterima, proses nyata dan keputusan D12 belum disahkan,
matching invoice serta pembayaran/posting native belum tersedia. Reviewer:
A2 purchasing/finance, A1 konsumsi bahan/costing, A3 dokumen/QA/izin, A0
kontrak/migrasi dan pemilik purchasing/gudang/AP. Review/sign-off **PENDING**;
PR draft dan #50 tetap terbuka sampai dependensi diterima, gap diimplementasikan
dan parity disahkan. Merge persiapan ini bukan penyelesaian B01.
