# F01: register proses bisnis

Status: **discovery untuk review, belum dibekukan / belum business accepted**.
Issue [#40](https://github.com/wenn-id/beeloftone/issues/40), induk
[#39](https://github.com/wenn-id/beeloftone/issues/39). Diperiksa 21 September 2026
pada `2bee57075b2e0826dfcd581691d37585e7dd1df2` (v0.97.0, schema 55), menggantikan
baseline teknis issue `f8921e763a8b317f3680229aedb9406ddba687c8` (v0.87.0, schema 55).

Register ini menginventaris cakupan roadmap dan kemampuan kode, bukan hasil
wawancara atau audit akun legacy. Dokumen legacy tersamarkan, daftar role perusahaan,
dan persetujuan pemilik proses belum diterima. Karena itu kelengkapan seluruh proses
perusahaan masih harus dikonfirmasi. Tidak terlihat pada akun audit, tidak ada menu,
atau tidak ditemukan di kode **tidak berarti proses boleh dihapus atau gap selesai**.

## Cara membaca dan sumber

- `P01` dst. adalah ID register ini, bukan kode paket roadmap P01/P02/P03.
- Kolom status menyebut perilaku One yang ada. `Belum ada; perlu keputusan` berarti
  state machine target belum disahkan, bukan status transaksi yang telah diimplementasikan.
- Aktor dan penanggung jawab (PJ) adalah **usulan peran bisnis untuk validasi**,
  bukan penunjukan orang atau bukti persetujuan. A0 mengoordinasikan penetapan pemilik;
  A1/A2/A3 adalah pelaksana teknis sesuai #39, bukan approver bisnis pengganti.
- Laporan berarti kebutuhan keluaran proses; ketersediaan One dijelaskan pada matriks.
- Seluruh baris menunggu sign-off. D01 dst. menunjuk
  [register keputusan](f01-decisions-evidence.md#register-keputusan).
- Sumber teknis: [model input](../beeloft/models.py), [API](../beeloft/api.py),
  [ledger dan guard](../beeloft/store.py), [kontrak OpenAPI](openapi.json),
  [batas arsitektur saat ini](../README.md#arsitektur-dan-model-source-of-truth).
  Tautan relatif dibaca pada commit baseline di atas; rencana milestone lama dapat
  tertinggal dari implementasi. Matriks juga merujuk tes sebagai bukti perilaku.

## Register input sampai hasil

| ID / proses | Input | Aktor | Status / titik keputusan | Hasil | Koreksi / pengecualian | Laporan / dokumen | PJ bisnis (usulan) |
|---|---|---|---|---|---|---|---|
| P01 Master produk, bahan, satuan | SKU, warna, ukuran, kode bahan, unit | Admin master | Master tersimpan; kategori/seri/konversi perlu D01 | Identitas produk dan bahan stabil | Mapping ID duplikat/perubahan satuan historis perlu keputusan; jangan mengubah saldo | Daftar master dan mapping ID | Pemilik master + produksi |
| P02 Unit, lokasi, supplier, customer | Unit usaha, lokasi, pihak, metode bayar | Admin master, gudang, finance | Supplier ada; lokasi masih teks; master unit/customer perlu D01 | Referensi transaksi lintas unit/pihak | Nonaktif, salah mapping, perpindahan unit perlu aturan | Daftar unit/lokasi/pihak | Operasi + finance |
| P03 BOM, pekerjaan dan tarif | SKU, komponen bahan, jenis kerja, tarif, tanggal berlaku | Produksi, payroll, admin | BOM berversi; template jasa/tarif belum ada | Kebutuhan bahan; target tarif historis untuk jasa | Revisi BOM; tarif hilang/nonaktif/berubah perlu D04 | BOM dan riwayat tarif | Produksi + payroll |
| P04 Planning/order dan perubahan | Baris SKU, target pcs, PIC, tenggat | Planner, kepala produksi | Saldo planned sampai warehouse; perubahan PIC/tenggat langsung atau lewat approval | Target dan histori order | Revisi PIC/tenggat; ubah target/partial cancel perlu D02 | Planning, board, WIP ageing | Produksi |
| P05 Kapasitas produksi | Work center, menit standar, kalender kapasitas | Planner, kepala produksi | Master aktif dan revisi kalender/routing | Beban kapasitas per tahap/tanggal | Revisi dengan alasan; menit standar bukan tarif upah | Kapasitas dan alert | Produksi |
| P06 Permintaan pembelian dan PO | Kebutuhan bahan, estimasi, supplier, harga, termin | Purchasing, approver | PR submitted/approved/rejected/cancelled; PO approval terpisah dari issued/closed/cancelled | PO berharga terkunci | Pembatalan/replacement dibatasi dependensi; split/invoice lintas PO perlu D12 | PR, PO, komitmen pembelian | Purchasing + finance |
| P07 Penerimaan bahan, QC masuk, retur supplier, close PO | PO, qty, batch, lokasi, hasil inspeksi | Receiving, QC, purchasing | Penerimaan parsial; hold menjadi accept/reject; close sesuai saldo | Bahan layak pakai dan sisa PO terlacak | Reversal/retur berjejak; tidak melanggar pemakaian dan nilai yang telah diajukan bayar | Receipt, QC, retur, sisa PO | Purchasing + gudang bahan |
| P08 Reservasi, pengeluaran, konsumsi bahan | Batch, order, qty reserve/issue, used, waste | Gudang bahan, produksi | Reserve/release; pemakaian aktif atau dibalik | Saldo bahan, pemakaian aktual, waste | Saldo dan sumber issue dijaga; koreksi event asal | Stok bahan dan konsumsi order | Gudang bahan + produksi |
| P09 Cutting | Issue bahan, used/waste, output tiap SKU | Operator cutting, kepala produksi | Run aktif atau corrected; cutting ke sewing | Pemakaian dan output tercatat atomik | Reverse seluruh run; rol/berat/lembar/setelan perlu D03 | Hasil cutting dan komposisi ukuran | Produksi |
| P10 Bundle dan serah terima | Output cutting, qty bundle, lokasi tujuan | Pengirim dan penerima berbeda | Bundle aktif/corrected; handoff pending/accepted/cancelled | Identitas bundle dan custody | Pending handoff dibatalkan admin; custody tidak otomatis memindahkan WIP | Label, histori custody | Produksi |
| P11 Sewing/makloon dan job karyawan | Bundle, assignee, qty out, biaya total; target employee/job perlu D05 | Kepala jahit, operator, vendor, approver realisasi | Sewing dikirim/diselesaikan/dikoreksi; approval realisasi employee belum ada | Completed/defect/missing dan WIP; charge jasa target belum ada | Reverse seluruh job sesuai saldo; target/actual/payable harus terpisah | Job, realisasi, biaya jasa | Produksi + payroll |
| P12 Finishing | Bundle, qty, checklist, tanggal selesai | Operator finishing | Catatan aktif/corrected; finishing ke QC | Hasil dengan checklist lengkap | Reverse terikat saldo/aktivitas lanjutan | Hasil finishing | Produksi |
| P13 Final QC, reject, rework dan inspeksi ulang | Qty accepted/rework/reject, temuan, catatan QC asal | QC, pelaksana rework | QC ke warehouse/rework/reject; selesai rework kembali ke QC | Disposisi dan ketertelusuran inspeksi | Reversal berjejak; aturan upah rework/reject belum diputuskan | QC, yield, defect | QC + produksi |
| P14 Barang jadi, transfer, hold, adjustment, opname | Receipt asal, scan SKU, lokasi/status, qty fisik | Gudang jadi, QC, penghitung stok | Sellable/hold/damaged; event aktif/dibalik | Stok per receipt/lokasi/status | Reversal perlu saldo; adjustment/opname tidak mengubah WIP produksi | Kartu stok, opname, traceability | Gudang jadi |
| P15 Reservasi marketplace, picking, packing, shipping | Order eksternal, receipt, qty, scan, carrier/resi | Admin kanal, picker, packer, pengiriman | Reserve/release lalu pick/pack/ship | Alokasi dan pengeluaran stok terlacak | Release/reversal sesuai dependensi, cegah alokasi ganda | Pick list, packing, shipment | Sales kanal + gudang |
| P16 Retur pelanggan | Shipment asal, qty, alasan, lokasi/status hasil inspeksi | Customer service, gudang, QC | Retur aktif/dibalik | Stok retur bertaut sumber | Retur qty bukan refund uang; tukar barang/refund perlu D11 | Dokumen retur dan inspeksi | Sales + gudang |
| P17 Harga, POS dan sales non-POS | Harga berlaku, customer, unit, baris barang, diskon/pajak | Kasir, sales, approver diskon | Belum ada; perlu keputusan D09/D10 | Target order penjualan dan invoice berbeda dari order produksi | Draft/final, perubahan harga, void dan stok kurang perlu aturan | Struk, invoice, sales order | Sales + finance |
| P18 Pembayaran sales, piutang, refund dan void | Invoice, metode bayar, amount paid, alokasi, retur | Kasir, finance, approver | Belum ada alur native; snapshot AR tidak menggantikannya | Target penerimaan, kembalian, outstanding dan reversal | Partial/overpayment/void setelah paid dan race alokasi perlu D11 | Bukti bayar, AR, refund | Finance + sales |
| P19 Settlement marketplace dan margin | Shipment, gross, diskon, refund, fee, biaya kirim | Finance kanal | Satu settlement aktif per shipment; margin complete/incomplete | Margin kontribusi dari sumber internal | Koreksi settlement; retur berubah membuat coverage stale; bukan jurnal atau bukti kas | Margin dan rincian settlement | Finance kanal |
| P20 Employee dan kehadiran | Kode employee, department, tanggal, jam, status | HR, pencatat kehadiran | Employee aktif/nonaktif; present/leave/absent | Histori employee dan kehadiran | Event revisi; posisi/shift lintas hari dan dampak upah perlu D06 | Roster dan rekap kehadiran | HR |
| P21 Cuti dan lembur | Employee, rentang tanggal/menit, alasan | HR/operator pemohon, approver | Submitted/approved/rejected/cancelled | Izin terpisah dari kejadian aktual | Pembatalan pending oleh pemohon yang berhak; dampak setelah approval perlu D06 | Cuti/lembur dan approval | HR + payroll |
| P22 Payroll per karyawan | Realisasi approved, tarif historis, premi/transport/bonus/potongan | Payroll, approver, finance | Belum ada native; hanya approval batch snapshot Mekari | Target gross/net per karyawan, slip dan kewajiban | Pecahan lusin, overlap, tarif berganti, reject/rework dan koreksi perlu D04-D07 | Slip dan register payroll | Payroll + finance |
| P23 Pembayaran dan posting payroll | Payroll approved, pembayaran, referensi jurnal | Finance, accounting | Saat ini rekonsiliasi read-only status paid/posted eksternal | Bukti pembayaran/posting sumber; target ledger native | Approval tidak otomatis paid; koreksi setelah paid/posted perlu D07/D14 | Rekonsiliasi payroll-kas-buku | Finance + accounting |
| P24 Kasbon, cicilan dan pelunasan | Employee, saldo awal, pencairan, jadwal, potongan payroll | HR/payroll, kasir finance, approver | Belum ada; perlu keputusan D08 | Target saldo dan histori kasbon | Cicilan dibatasi saldo; payroll reversal harus mengembalikan kedua sisi | Kartu kasbon, outstanding | Payroll + finance |
| P25 AP Settlement dan pengeluaran non-PO | Invoice, PO/receipt bila ada, biaya, metode/tanggal bayar | AP, kasir finance, approver | Approval supplier submitted/approved/rejected/cancelled ada; paid native belum ada | Target pembayaran aktual dan alokasi utang | With/non-PO, partial, overpayment, void perlu D12; approval bukan pengeluaran kas | Bukti bayar, AP, detail biaya | Finance/AP |
| P26 Valuasi persediaan, WIP dan COGS | Saldo/arus qty, harga bahan, charge jasa, overhead | Costing, accounting | Laporan biaya produksi ada; metode valuasi native belum ada | Target nilai WIP/persediaan/COGS | Cegah biaya sewing dan charge job baru dihitung dua kali; retur terkait biaya asal | Stok/modal, WIP, COGS | Accounting + produksi |
| P27 Buku besar, AR/AP, rekonsiliasi dan tutup periode | COA, sumber transaksi, tanggal pengakuan, saldo awal | Accounting, approver close | Snapshot finance/AR/AP ada; posting/close/reopen native belum ada | Target jurnal, saldo kontrol, laporan keuangan | Reversal, late adjustment, periode terkunci perlu D14/D15 | Trial balance, AR/AP aging, kas/bank, P&L/neraca sesuai keputusan | Accounting |
| P28 Anggaran marketing | Campaign, kanal, periode, nominal, tujuan | Marketing, approver | Submitted/approved/rejected/cancelled | Otorisasi batas anggaran | Bukan actual spend; pencatatan pengeluaran mengikuti D12/D16 | Approval budget dan realisasi yang disahkan | Marketing + finance |
| P29 Izin, SSO dan approval lintas domain | Akun, role, scope unit, tindakan | Admin akses, pemohon, approver, auditor | Admin/operator/viewer saat ini; izin perusahaan belum dipetakan | Target baca/catat/approve/pay/export sesuai tugas | Self-approval, delegasi, pencabutan akses perlu D17; handoff sudah melarang penerima= pengirim | Matriks akses dan audit keputusan | Operasi + pemilik domain |
| P30 Laporan, ekspor dan arsip | Domain, tanggal/status/unit, format, penerima | Pemilik domain, manajemen, auditor | Activity CSV/read models ada; format bisnis belum disahkan | Laporan dengan filter dan total yang dapat direkonsiliasi | Format/nomor dokumen/retensi harus disepakati; ekspor mengikuti izin | Katalog laporan dan arsip | Semua pemilik domain + operasi |
| P31 Integrasi kanal dan snapshot | Mapping ID, order/stok/retur/listing, snapshot finance/payroll | Admin integrasi, sales kanal, finance | Run succeeded/failed; unmapped dikarantina; belum ada connector terjadwal | Snapshot berwaktu dan rekonsiliasi | Retry/deduplikasi/konflik/write-back perlu D18; snapshot bukan transaksi native | Sync health, quarantine, rekonsiliasi | Operasi + sales + finance |
| P32 Impor, saldo awal dan cutover | Export legacy, mapping, cutoff, histori, delta | Admin migrasi, pemilik domain, A0 | Paket X01/X02/Q02 belum dilaksanakan | Target saldo awal/arsip terlacak dan kontrol total | Pilih replay atau opening agar tidak ganda; transaksi sesudah cutover tidak boleh hilang | Dry-run, control totals, sign-off | Operasi + accounting + A0 |
| P33 Backup, restore dan insiden | DB, jadwal/retensi, RPO/RTO, pengguna/volume | Admin operasi, petugas insiden | Backup lokal ada; operasi bersama perlu D20 | Salinan pulih dan runbook teruji | Uji restore terpisah; rollback menjaga transaksi baru | Log backup/restore dan insiden | Operasi |
| P34 Kendala, analitik, investigasi dan tindakan AI | Kendala order, ledger/snapshot, pertanyaan, proposal aksi | Operator, planner, manajemen, approver | Kendala open/resolved; investigasi read-only, proposal lewat keputusan | Evidence, rekomendasi, aksi yang diizinkan | Sumber kosong/stale bukan nol; batas aksi dan akses perlu D16/D17 | Kendala, activity, audit, histori investigasi | Produksi + manajemen |

## Matriks legacy ke One ke keputusan

Kolom legacy adalah **proses yang perlu diminta buktinya**, berdasarkan cakupan
#39/#40 dan paket turunannya; bukan klaim telah melihat layar/dokumen legacy.
`Sebagian` berarti fondasi ada tetapi parity belum diterima. `Terbuka` berarti
kontrak bisnis target belum tersedia. Tidak ada baris berstatus selesai.

| Proses | Legacy / bukti yang masih diperlukan | One pada baseline dan bukti | Keputusan / gap | Paket penerima |
|---|---|---|---|---|
| P01 | Master produk/bahan/satuan, kolom wajib dan contoh ID | `ProductCreate`, `MaterialCreate`; [tes master](../tests/test_materials.py) | Sebagian; D01, G06/G04 | M01 #43 |
| P02 | Struktur unit/gudang, supplier/customer/metode bayar | `SupplierCreate`, lokasi teks; [tes PO](../tests/test_purchase_orders.py) | Sebagian; D01, G04/G05/G06 | M02 #44 |
| P03 | Template bahan/jasa dan histori tarif | `BomSave`; [tes BOM](../tests/test_bom.py); tidak ada tarif job employee | Sebagian; D04, G02/G06 | P01 #48 |
| P04 | Planning, approval, koreksi target dan pembatalan parsial | `OrderCreate`, `OrderChange`; [tes perubahan](../tests/test_order_changes.py) | Sebagian; D02, G06 | P02 #49 |
| P05 | Kalender/kapasitas, definisi menit standar | [Kontrak kapasitas](production-capacity-plan.md), [tes](../tests/test_production_capacity.py) | Sebagian; D02/D04, G06 | P01 #48, P02 #49 |
| P06 | PR/PO, split supplier, revisi harga/qty, approval | [Approval PO](purchase-order-approvals-plan.md), [tes](../tests/test_purchase_order_approvals.py) | Sebagian; D12, G05 | B01 #50 |
| P07 | Receipt parsial, QC, retur, close dan invoice asal | [Tes penerimaan](../tests/test_po_receipts.py), [retur](../tests/test_supplier_returns.py) | Sebagian; D12, G05 | B01 #50 |
| P08 | Bon bahan, konsumsi/waste, sisa dan pengembalian | [Tes reservasi](../tests/test_reservations.py), [konsumsi](../tests/test_consumption.py) | Sebagian; D03/D13, G06 | P02 #49, I01 #53 |
| P09 | Cutting rol/berat/lembar/komposisi/setelan/PO | `CuttingRunCreate`; [tes cutting](../tests/test_cutting.py) hanya used/waste dan output pcs | Sebagian; D03, G06 | P02 #49 |
| P10 | Label dan bukti handoff tiap role | [Kontrak handoff](bundle-handoffs-plan.md), [tes](../tests/test_bundle_handoffs.py) | Sebagian; D02/D17, G06/G07 | P02 #49, O01 #45 |
| P11 | Job employee, realisasi, remaining, approval, reject/rework | `SewingJobCreate` memakai assignee teks dan total cost; [tes](../tests/test_sewing_jobs.py) | Sebagian; D04/D05, G02/G06 | P03 #52 |
| P12 | Checklist finishing dan jasa yang dibayar | `FinishingRecordCreate`; [tes](../tests/test_finishing.py) | Sebagian; D05, G02/G06 | P03 #52 |
| P13 | QC/rework berulang, disposisi dan dampak upah | [Tes final QC](../tests/test_final_qc.py), [reinspeksi](../tests/test_rework_reinspection.py) | Sebagian; D05, G02/G06 | P03 #52, H01 #55 |
| P14 | Kartu stok tiap unit/status, adjustment dan opname | [Tes pergerakan](../tests/test_warehouse_movements.py), [rekonsiliasi](../tests/test_inventory_reconciliation.py) | Sebagian; D01/D13, G04/G06 | M02 #44, I01 #53 |
| P15 | SOP order marketplace sampai pengiriman | [Tes reservation](../tests/test_marketplace_reservations.py), [shipping](../tests/test_marketplace_shipping.py) | Sebagian; D18, G04 | S01 #57, S02 #58 |
| P16 | Dokumen retur, refund, tukar dan otorisasi | [Tes retur](../tests/test_returns_adjustments.py) memulihkan qty, bukan refund | Sebagian; D11/D13, G04 | S02 #58, I01 #53 |
| P17 | Harga, struk POS, alur order non-POS yang benar-benar dipakai | Snapshot order Jubelio; tidak ada kontrak POS/sales order native pada model/API | Terbuka; D09/D10, G01/G04 | S01 #57 |
| P18 | Pembayaran tunai/non-tunai, piutang, void/refund | Snapshot receivable dan settlement shipment tidak menyediakan invoice/payment native | Terbuka; D11, G01/G04 | S02 #58 |
| P19 | Settlement kanal, fee dan rekonsiliasi pencairan | `MarketplaceSaleSettlementCreate`; [tes margin](../tests/test_contribution_margin.py) | Sebagian; D11/D13/D18, G04/G05 | S02 #58, A02 #59 |
| P20 | Employee/position, kehadiran dan aturan koreksi | `EmployeeCreate`, `AttendanceSave`; [tes People](../tests/test_workforce.py) | Sebagian; D01/D06/D17, G02 | M02 #44, H01 #55, O01 #45 |
| P21 | Form cuti/lembur dan hubungan ke payroll | [Tes approval workforce](../tests/test_workforce_approvals.py); attendance tetap terpisah | Sebagian; D06/D17, G02 | H01 #55, O01 #45 |
| P22 | Slip dan perhitungan payroll employee yang disetujui | [Approval snapshot agregat](payroll-approvals-plan.md), [tes](../tests/test_payroll_approvals.py); bukan kalkulasi native | Terbuka; D04-D07, G01/G02 | H01 #55 |
| P23 | Bukti bayar, cicilan bayar, jurnal payroll dan koreksi | [Rekonsiliasi bayar](payroll-payment-reconciliation-plan.md), [accounting](payroll-accounting-reconciliation-plan.md) read-only | Terbuka; D07/D14, G01/G02 | H01 #55, A01 #46 |
| P24 | Kartu kasbon, pencairan, jadwal, potongan, pelunasan | Tidak ditemukan model/API ledger kasbon; keberadaan proses legacy tetap perlu validasi | Terbuka; D08, G03 | H02 #56 |
| P25 | AP Settlement with PO/non-PO dan pengeluaran lain | [Approval supplier](supplier-payment-approvals-plan.md), [tes](../tests/test_supplier_payment_approvals.py); belum payment | Sebagian; D12, G01/G05 | B02 #54 |
| P26 | Metode biaya, stok/modal, WIP, COGS dan retur | [Biaya produksi](production-cost-reporting-plan.md), [tes](../tests/test_production_cost.py); belum valuasi buku | Terbuka; D13, G01/G06 | I01 #53, A01 #46 |
| P27 | COA, jurnal, buku besar, AR/AP, kas/bank, closing | Snapshot Mekari dan [metadata jurnal payroll](../tests/test_payroll_accounting_reconciliation.py); belum GL native | Terbuka; D14/D15, G01/G05 | A01 #46, A02 #59 |
| P28 | Approval budget dan actual spend/non-PO | [Kontrak marketing](marketing-budget-approvals-plan.md), [tes](../tests/test_marketing_budget_approvals.py) hanya ceiling | Sebagian; D12/D16, G05 | B02 #54, R01 #60 |
| P29 | Daftar role perusahaan dan hak tiap fungsi/unit | [Akun saat ini](operations.md#akun-dan-hak-akses); pemeriksaan domain di store; tiga role teknis | Terbuka; D17, G07 | O01 #45, F02 #41 |
| P30 | Semua format laporan/export/arsip dan penerimanya | [Activity CSV](../tests/test_activity_export.py) dan read models; bukan parity seluruh laporan | Terbuka; D16/D19, G02/G05/G07 | R01 #60, X01 #51 |
| P31 | Kanal yang dipertahankan, SLA dan hak write-back | `INTEGRATION_CONTRACTS` di store; [tes sync](../tests/test_integration_sync.py); ingestion saja | Terbuka; D18, G01/G04/G07 | S01 #57, S02 #58, X01 #51 |
| P32 | Export, cutoff, saldo/pekerjaan belum dibayar, delta | Belum ada importer seluruh backoffice; snapshot bukan bukti migrasi penuh | Terbuka; D19, G07 | X01 #51, X02 #61, Q02 #63 |
| P33 | Target RPO/RTO, retensi dan SOP pemulihan | [Backup lokal](operations.md#backup-dan-pemulihan), [tes](../tests/test_backup_download.py) | Sebagian; D20, G07 | O02 #47, Q02 #63 |
| P34 | Kendala, laporan manajemen, cakupan AI yang dibutuhkan | [Tes kendala](../tests/test_issues.py), [proposal AI](../tests/test_ai_action_proposals.py) | Sebagian; D16/D17, G07 | R01 #60, O01 #45 |

## Cakupan role dan tindak lanjut

| Peran bisnis yang harus diwawancarai | Proses utama | Bukti penerimaan yang diminta |
|---|---|---|
| Admin master/operasi | P01-P03, P29-P33 | Struktur organisasi, mapping ID, hak fungsi/unit, runbook |
| Planner/kepala produksi | P03-P05, P08-P13, P26, P34 | Planning sampai barang jadi, tarif dan koreksi lintas tahap |
| Cutting/jahit/finishing/makloon | P08-P12 | Input aktual, handoff, realisasi, reject/rework |
| QC | P07, P13, P14, P16 | Keputusan inspeksi dan jalur koreksi |
| Purchasing/receiving | P06-P08, P25 | PR sampai invoice, receipt/return/close parsial |
| Gudang bahan/jadi/picker/packer/pengiriman | P07-P10, P14-P16 | Saldo tiap lokasi/status dan jejak transaksi |
| HR/payroll | P11, P20-P24 | Employee, satu siklus payroll, kasbon dan koreksi |
| Kasir/sales/customer service/admin kanal | P15-P19, P31 | POS dan non-POS, pembayaran, retur, kanal eksternal |
| Finance/AP/AR/kasir keuangan | P18-P19, P23-P28 | Uang aktual, piutang/utang, biaya dan alokasi |
| Accounting | P23-P27, P30, P32 | Metode biaya, akun, periode, control totals dan laporan |
| Marketing | P28, P30 | Anggaran versus actual spend dan laporan |
| Manajemen/approver/auditor | P29-P30, P34 serta approval domain | Pemisahan tugas, laporan, traceability dan penerimaan |

A0 meminta tiap pemilik mengonfirmasi daftar di atas, menambah proses/role yang
terlewat, dan menghubungkan Dxx serta EXxx ke contoh yang disetujui. Akun `viewer`
bukan bukti bahwa semua auditor/manajer boleh melihat seluruh data payroll.
Detail keputusan, katalog dokumen, dan syarat freeze ada di
[F01 keputusan dan bukti](f01-decisions-evidence.md).
