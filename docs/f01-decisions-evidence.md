# F01: keputusan, bukti, dan sign-off

Pasangan [register proses](f01-process-register.md) untuk
[issue #40](https://github.com/wenn-id/beeloftone/issues/40).
Execution baseline: `96bb48fa8889b3a483411768e2543838e69233b0` (v0.114.0/schema 55). Status paket: **IN_PROGRESS; belum REVIEW_READY, belum Integrated, belum Business accepted**. Audit terdahulu tercatat di Issue #40 sebagai prior UI report only; tidak mengesahkan backend rules. Tidak ada keputusan bisnis atau
contoh dokumen legacy yang diklaim telah disetujui dalam perubahan ini.

## Batas yang sudah dinyatakan sumber

Ketentuan berikut berasal dari #39/#40 dan issue anak, bukan keputusan baru agent:

- Seluruh proses wajib dipetakan ke One atau dihentikan dengan keputusan eksplisit
  pemilik. Tidak terlihat pada akun audit tidak membuktikan proses tidak dipakai.
- Target, realisasi aktual, dan kuantitas layak dibayar adalah konsep terpisah
  ([#49](https://github.com/wenn-id/beeloftone/issues/49)).
- Approved, paid, dan posted harus dibedakan
  ([#41](https://github.com/wenn-id/beeloftone/issues/41)). Approval supplier saat
  ini bukan bukti kas keluar; rekonsiliasi payroll membaca status eksternal.
- Snapshot Jubelio/Mekari tetap read-only pada baseline. Target penggantian
  backoffice tidak otomatis mengizinkan write-back atau menetapkan vendor yang
  dihentikan. Kanal yang perlu sinkronisasi otomatis tidak cukup dengan snapshot
  manual ([#58](https://github.com/wenn-id/beeloftone/issues/58)).
- Pertahankan ledger, invariant uang/qty, idempotency, revision guard, transaksi
  atomik, dan audit/reversal. Jangan menambahkan rumus payroll kedua di costing
  atau menghitung biaya sewing lama dan charge jasa baru dua kali (#52/#53).
- Gunakan data sintetis di repo/PR/CI. Tidak ada akses, perubahan, atau transaksi
  produksi dalam paket discovery ini.

## Akuntansi One: capability inventory at execution baseline

**Scope decision:** arah D14 Opsi B dipilih oleh pengguna dalam instruksi langsung: Beeloft One mencakup COA, jurnal, general ledger, trial balance, neraca, laba rugi, rekonsiliasi, dan tutup buku. Ini hanya persetujuan arah cakupan. Identitas/jabatan approver tidak dicatat; detail kebijakan, keputusan D lainnya, bukti legacy, dan penerimaan akhir tetap terbuka.

**Baseline verified by repository source:** commit `96bb48fa8889b3a483411768e2543838e69233b0`, app `0.114.0`, schema `55`. The references below describe code/tests/documents in that baseline, not an independent production operation.

| Status | Existing capability | Source evidence | Boundary / roadmap |
|---|---|---|---|
| Available: operational ledgers | Immutable, domain-specific records/movements and linked reversal records exist for inventory, production/WIP/QC, PO receipts/returns, marketplace shipments/returns/settlements and related workflows. `Store._write` gives transaction/audit/idempotency behavior to covered mutations. | `docs/f02-ownership.csv` inventory; examples `beeloft/materials.sql`, `beeloft/cutting.sql`, `beeloft/final_qc.sql`, `beeloft/purchase_orders.sql`, `beeloft/marketplace_sale_settlements.sql`; tests `tests/test_idempotency_actor.py`, `tests/test_po_receipts.py`, `tests/test_production_cost.py`. | These are operational subledgers and audit trails, not a unified financial general ledger. Preserve them as event/source of truth; journal integration must consume each source event once. #41 F02 contracts; domain producers #48/#49/#50/#52/#53/#54/#55/#56/#57/#58. |
| Available: read-only external finance snapshots | Immutable Mekari finance snapshots store period aggregates for revenue, returns, COGS, expenses, cash, receivables, and payables. They are imported evidence, not native One-account balances. | `beeloft/mekari_finance_snapshots.sql`; `docs/mekari-finance-snapshot-plan.md`; `docs/mekari-finance-snapshot-verification.md`; `tests/test_mekari_finance_snapshots.py`. | No double-counting with future native accounting. External snapshot IDs/source authority remain separate. #51 X01, #46 A01, #59 A02. |
| Available: payroll accounting reconciliation metadata | Payroll snapshot can include one external journal metadata record with reference, date, debit/credit totals, and draft/posted/reversed state. Reconciliation identifies missing, stale, unbalanced, or mismatched external posting metadata; it does not create the journal. | `beeloft/payroll_accounting.sql` (table `mekari_payroll_snapshot_postings`, `user_version=53` in historical migration); `beeloft/models.py` external snapshot models; `docs/payroll-accounting-reconciliation-plan.md`; `tests/test_payroll_accounting_reconciliation.py`. | Not native journal lines, COA, GL, or posting engine. A snapshot marked posted is not a journal posted in One. Historical schema migration 53 is not the current schema 55. #46 A01. |
| Available: operational approval/reconciliation surfaces | Payroll approval workflow and supplier payment approval requests exist. Supplier approval is not money movement; payroll approval is distinct from payment and posting snapshot states. | `beeloft/payroll_approvals.sql`, `beeloft/supplier_payment_approvals.sql`; `docs/f02-shared-contracts.md` sections “Approved, paid, posted”; `tests/test_payroll_approvals.py`, `tests/test_supplier_payment_approvals.py`. | Do not treat approval ledgers as journal/payment ledgers. Native payment allocation/account posting remain gaps. #54 B02, #55 H01, #56 H02, #46 A01. |
| Partial: operational costing | Production cost reporting derives material use/waste at PO prices and includes active sewing job cost. Inventory operational quantity/value fields and marketplace margin traceability exist. | `Store.production_cost` in `beeloft/store.py`; `docs/a01-ledger-readiness.md`; `tests/test_production_cost.py`, `tests/test_contribution_margin.py`. | Not a complete inventory valuation policy, financial accounting WIP, COGS journal, or GL. Existing sewing job cost must not be added again when future job/payroll charges cover the same work. #53 I01 and #46 A01; #59 A02 reconciliation. |
| Missing: native accounting foundation | No native COA/account master, accounting period master/state, journal header/lines, source-to-journal registry, or native trial balance was found in schema 55 ownership inventory. | `docs/f02-ownership.csv`; `docs/a01-ledger-readiness.md` inventory statement; `docs/f02-shared-contracts.md` explicitly says no native payment/COA/journal/closed period in schema 55. | Build foundations via #46 A01 after #41 F02 and #44 M02 plus D14/D15 detail agreement. Do not implement in F01. |
| Missing: native payment, cash/bank, AR/AP accounting | Operational approvals, supplier receipt/PO, marketplace settlement, and external financial snapshots do not constitute a native payment/allocation, bank ledger, AR/AP subledger, or journal. | `docs/a01-ledger-readiness.md`; `docs/f02-shared-contracts.md`; relevant issue scopes #54/#57/#58. | Producer capabilities land with #54 B02, #55/#56, #57/#58. Native event-to-journal integration and reconciliation via #46/#59. |
| Missing: full statements and period close | No native trial balance, balance sheet, profit-and-loss engine, period close/reopen, posting lock, or financial statement reconciliation was identified in the schema 55 inventory. | `docs/a01-ledger-readiness.md`; `docs/f02-shared-contracts.md` “Locking periode (belum diimplementasikan)”; issue #59 acceptance. | #59 A02 builds AR/AP aging, cash/bank, reconciliation, authorized close/reopen and approved reports after upstream subledgers and #46. |

**No parallel ledger / no double count:** Existing immutable operational ledgers remain authoritative for their domain events. Future accounting should derive one journal effect from a uniquely identified source event/revision; it must not copy the same event into a second operational ledger, count an existing sewing cost plus a new charge twice, or reinterpret an external snapshot as a native journal. Native journal records are a distinct financial projection with source linkage, not a competing source of operational quantity/state. Contract details and idempotency are proposed in #41, not implemented merely by this inventory.

**Issue alignment:**
- **#41 (F02):** shared identity, amount/quantity, charge, payment, posting, idempotency, reversal and source identity contract; OPEN and dependency to #40 unchecked.
- **#46 (A01):** COA, period, journal header/lines/source and atomic posting foundation; depends on #41 and #44; OPEN. Build foundation early after contracts, without claiming complete accounting functionality.
- **#59 (A02):** subledgers, reconciliation, close/reopen, reports and opening balances after #55/#56/#58/#54/#53/#46; OPEN. Completes end-state reporting/period controls, not a second ledger.

All package ownership labels A1/A2/A3 are roadmap role allocations, not named business approvers. No runtime, database, schema or fixture changes are included in this revision.


## Register keputusan

**Semua D01-D20 berstatus OPEN.** PJ di bawah adalah usulan peran penentu, belum
penunjukan orang. Jawaban, approver, tanggal berlaku, dan bukti persetujuan belum
tersedia. Daftar pilihan/kasus di kolom keputusan adalah pertanyaan untuk pemilik,
bukan default implementasi. F02 dan paket domain tidak boleh menganggapnya disahkan
karena dokumen ini di-merge. Batas waktu tiap keputusan: sebelum kontrak paket
penerimanya diterima; A0 menetapkan jadwal bersama pemilik.

| ID | Keputusan yang harus diisi pemilik | PJ bisnis (usulan) | Contoh untuk menetapkan expected result | Memblokir penerimaan |
|---|---|---|---|---|
| D01 | Kolom master wajib/dihapus beserta alasan; kategori/subkategori/tipe/seri; unit dasar/konversi pcs-lusin; unit usaha/storage; position vs department; customer/supplier/metode bayar dan aturan nonaktif | Master, operasi, produksi, finance | EX01; ID lama duplikat, lokasi dengan nama sama lintas unit, nonaktif masih punya saldo | M01 #43, M02 #44, F02 #41 |
| D02 | Status dan approval planning; perubahan target/tenggat/PIC setelah bergerak; partial cancellation; kebutuhan bundle/handoff dan kalender kapasitas | Produksi | EX02; target berubah setelah sebagian menjadi WIP, qty yang boleh dibatalkan | P02 #49, F02 #41 |
| D03 | Arti rol/berat/lembar/setelan per lembar, komposisi model/ukuran, referensi PO; rumus output dan waste serta presisi setiap unit | Produksi + gudang bahan | EX02; cutting campuran ukuran, bahan pecahan, waste dan reversal dengan hasil per baris | P02 #49, I01 #53 |
| D04 | Basis upah per pcs/lusin/jenis kerja; pembulatan pecahan lusin dan uang (skala, mode, tahap per baris/karyawan/periode); tanggal pemilih tarif; tarif hilang/nonaktif; perubahan di tengah periode | Payroll + produksi | EX03/EX04; 1, 11, 12, 13 pcs, tarif berganti, pembulatan per baris vs total. Angka ini hanya input uji sintetis, hasil belum ditetapkan | P01 #48, H01 #55, F02 #41 |
| D05 | Realisasi mana layak dibayar, approval dan batas target; reject, missing, rework berulang dan siapa menanggung; koreksi sebelum/sesudah approval; employee nonaktif; satu sumber charge unik | Produksi + payroll | EX03; target/actual/payable berbeda, reject/rework, koreksi job sudah masuk payroll | P03 #52, H01 #55, I01 #53 |
| D06 | Pengaruh hadir/cuti/absen/lembur ke upah; shift bila diperlukan; premi/transport/bonus/potongan, kelayakan dan tanggal efektif; kebutuhan komponen pajak/potongan wajib ditinjau pemilik | HR/payroll + accounting | EX04; absen/cuti/lembur, komponen positif/negatif, net rendah/negatif; formula dan tindakan eksplisit | H01 #55 |
| D07 | Periode dan cutoff payroll, overlap, job terlambat, persetujuan, pembayaran parsial jika dipakai, koreksi setelah paid/posted, pembatalan dan slip; pisahkan sumber native dari snapshot | Payroll + finance/accounting | EX04; satu siklus penuh, overlap, unpaid job lama, partial pay, reversal setelah paid | H01 #55, A01 #46, X02 #61 |
| D08 | Saldo awal/pencairan/jatuh tempo kasbon, aturan cicilan, batas potongan terhadap saldo dan net pay; pelunasan di luar payroll, cicilan terlewat, nonaktif/resign, reversal lintas payroll/kasbon | Payroll + finance | EX05; cicilan terakhir lebih kecil, net tidak cukup, pelunasan bersamaan, potongan dibalik | H02 #56, A01 #46 |
| D09 | Kanal sales selain POS yang benar-benar dipakai; langkah order/reservasi/pengiriman/invoice/termin; aktor dan status tiap langkah; pisahkan ID sales order dari production order | Sales + gudang + finance | EX06; satu transaksi lengkap **setiap** kanal non-POS yang dikonfirmasi, termasuk koreksinya | S01 #57 |
| D10 | Harga berlaku per unit/customer/kanal; otorisasi diskon, pajak yang disahkan, presisi/rounding total, draft/final invoice, nomor dokumen; harga terkunci pada titik apa | Sales + accounting | EX06; ganti harga saat draft terbuka, diskon di luar batas, stok kurang, finalisasi dua kali | S01 #57, F02 #41 |
| D11 | Metode bayar, amount paid/change, partial payment/piutang, overpayment, retur sebagian, refund vs tukar, void sebelum/sesudah paid/shipped/posted; dampak stok/uang/jurnal dan approver | Sales + finance/accounting | EX06/EX07; uang/stok sebelum-sesudah setiap koreksi dan retry, alokasi dua pembayaran bersamaan | S02 #58, A01 #46 |
| D12 | Parity PR/PO/receipt/return/close; invoice vs receipt; AP Settlement with PO/non-PO, jenis biaya non-PO, multi-PO bila dipakai, partial/overpayment/change, void dan reversal; approval vs pembayaran aktual | Purchasing + AP/finance/accounting | EX08; penerimaan/retur parsial, invoice mismatch, pengeluaran non-PO, approval tanpa kas keluar | B01 #50, B02 #54, A01 #46 |
| D13 | Metode valuasi/COGS yang dipilih pemilik, komponen bahan/jasa/overhead, waste/reject/rework, WIP, transfer unit, pengakuan biaya vs pembayaran, alokasi dan rounding; cegah double count sewing/charge baru | Accounting + produksi | EX09; dua penerimaan berharga berbeda, job approved, QC, barang jadi, transfer, penjualan, retur/reversal | I01 #53, A01 #46 |
| D14 | Arah Opsi B (native full accounting) dipilih pengguna; detail COA, akun kontrol, event/timing, pajak, presisi, periode, laporan dan migrasi tetap OPEN | Pemilik kebijakan accounting (nama/jabatan belum ditetapkan); roadmap role A2 bukan approver bisnis | EX10; penerimaan 10 × Rp25.000 hanya ilustrasi target, bukan aturan legacy | DIRECTION_SELECTED / DETAIL_OPEN / NOT BUSINESS ACCEPTED |
| D15 | Periode buka/tutup, hak close/reopen, late adjustment, rekonsiliasi subledger, laporan keuangan yang wajib, saldo awal dan sign-off selisih | Accounting | EX10; transaksi bertanggal periode tutup, reversal lintas periode, trial balance/AR/AP aging/kas-bank | A02 #59, X02 #61 |
| D16 | Katalog laporan wajib, format PDF/CSV/lainnya, filter tanggal/status/unit, dasar tanggal, kolom/total/nomor dokumen, pembaca dan ekspor; kebutuhan marketing/analitik/AI | Semua pemilik domain + manajemen | EX11; setiap format dan total dari sumber sama, data kosong, koreksi, pemisahan snapshot/native | R01 #60 |
| D17 | Daftar role perusahaan dan matriks baca/catat/approve/pay/export tiap proses/unit; akses gaji **terpisah** dari akses margin/laba (tidak digabung); self-approval/delegasi, akun SSO dan audit perubahan hak | Operasi + seluruh pemilik domain | EX12; positif/negatif lintas akun/unit, payroll API/export, approver=pemohon, akun dicabut | O01 #45, F02 #41 |
| D18 | Vendor/kanal dipertahankan atau dihentikan dengan alasan; sumber order/stok/retur/settlement; arah baca/tulis dan pemilik data per objek; interval/SLA, konflik, retry/deduplikasi/karantina/reconciliation | Sales kanal + operasi + finance | EX13; order sampai settlement, retur terlambat, pengiriman ulang payload, gangguan connector dan selisih | S01 #57, S02 #58, X01 #51 |
| D19 | Inventaris export/arsip, retensi dan akses; cutoff/watermark per domain; replay histori **atau** saldo awal; job sudah dibayar/unpaid, saldo kasbon/AR/AP/kas/WIP, delta setelah snapshot | Operasi + accounting + pemilik domain | EX14; control totals qty/nilai/record/outstanding, dry-run ulang, histori dibayar tidak dibayar ulang | X01 #51, X02 #61, Q02 #63 |
| D20 | Pengguna/volume nyata untuk uji beban, RPO/RTO, jadwal/retensi backup, alert dan pemilik insiden; go/no-go dan perlindungan transaksi baru saat rollback | Operasi + A0 + manajemen | EX15; restore terpisah, downtime, disk penuh, restart, transaksi setelah cutover | O02 #47, Q01 #62, Q02 #63 |

Catatan keputusan yang disahkan harus memuat: `Dxx`, proses `Pxx`, jawaban/rumus
dan opsi yang ditolak beserta alasan, scope unit/role, tanggal efektif, dokumen
`EXxx` dan revisinya, input serta expected result, peran/nama approver yang boleh
dipublikasikan, waktu dan referensi persetujuan. Revisi keputusan membuka ulang
review fixture dan paket yang terpengaruh; tidak menghitung ulang histori diam-diam.

## Katalog dokumen dan calon fixture

**Semua EX01-EX15: MISSING_OWNER_APPROVAL.** Belum ada dokumen legacy yang diterima,
disamarkan, atau disahkan pada paket ini. Tautan tes di bawah adalah contoh sintetis
**teknis yang sudah ada**, bukan dokumen bisnis yang disetujui, bukan oracle aturan
baru, dan bukan tanda acceptance F01 selesai. Tidak menambahkan angka gaji/pelanggan
atau transaksi nyata untuk mengisi kekosongan bukti.

| ID | Dokumen yang harus dikumpulkan | Proses | Calon fixture sintetis yang dapat dipakai ulang / batas |
|---|---|---|---|
| EX01 | Master produk/bahan/unit/lokasi/pihak/employee beserta kamus kolom | P01-P03, P20 | [Master bahan](../tests/test_materials.py), [People](../tests/test_workforce.py); belum contoh struktur legacy |
| EX02 | Planning, cutting campuran ukuran, bon bahan, label/handoff, koreksi | P04-P10 | [Cutting](../tests/test_cutting.py): `test_multi_size_output_and_rollback_when_one_size_is_short`; belum rumus rol/lembar/setelan |
| EX03 | Template tarif, kartu job/approval/realisasi, reject/rework | P03, P11-P13 | [Sewing](../tests/test_sewing_jobs.py): `test_partial_jobs_capture_cost_outcome_turnaround_and_wip`; biaya total bukan rumus upah |
| EX04 | Slip per employee, rekap satu periode, komponen, bukti bayar dan koreksi | P20-P23 | [Payroll](../tests/test_payroll_approvals.py): `test_decisions_roles_and_source_status_stays_immutable`; hanya approval agregat, belum slip/payroll native |
| EX05 | Kasbon: saldo awal, pencairan, jadwal, cicilan, pelunasan dan reversal | P24 | Belum ada fixture ledger kasbon; pemilik menetapkan input dan saldo akhir sintetis |
| EX06 | Daftar harga, struk POS dan dokumen setiap alur non-POS, payment/AR | P17-P18 | Belum ada fixture invoice/payment native; jangan memakai production order sebagai sales order |
| EX07 | Retur/refund/void/tukar, settlement dan rekonsiliasi kanal | P15-P19 | [Retur](../tests/test_returns_adjustments.py): `test_partial_returns_restore_inspected_stock_with_lineage`; [margin](../tests/test_contribution_margin.py): `test_exact_partial_sales_margin_and_lineage`; belum refund uang native |
| EX08 | PR/PO/receipt/retur/close, supplier invoice, AP Settlement with/non-PO | P06-P07, P25, P28 | [Supplier payment](../tests/test_supplier_payment_approvals.py): `test_request_requires_received_po_and_enters_unified_inbox`; hanya approval, belum pembayaran aktual |
| EX09 | Kartu stok/modal/WIP/COGS dengan sumber harga dan biaya | P08, P14, P26 | [Biaya](../tests/test_production_cost.py): `test_exact_priced_material_waste_and_active_sewing_cost`; belum metode valuasi perusahaan |
| EX10 | COA, jurnal, trial balance, AR/AP aging, kas/bank, closing dan laporan keuangan | P23, P27 | [Rekonsiliasi payroll](../tests/test_payroll_accounting_reconciliation.py): `test_reconciles_payment_and_posting_states`; metadata eksternal, bukan jurnal native |
| EX11 | Slip, job, planning/cutting, kasbon, POS/payment, stok/modal, settlement, accounting dan laporan tambahan yang dipakai | P30, P34 dan semua proses domain | [Activity CSV](../tests/test_activity_export.py); belum persetujuan layout, filter dan control totals seluruh laporan |
| EX12 | Daftar role, hak tindakan/unit, approval dan akses export/arsip | P29 | [Workforce approval](../tests/test_workforce_approvals.py): `test_roles_decisions_unified_inbox_and_attendance_remain_separate`; tiga role teknis belum matriks perusahaan |
| EX13 | Daftar kanal, kontrak event/order/stok/retur/settlement, SLA dan pemilik data | P15-P19, P31 | [Sync](../tests/test_integration_sync.py), [order snapshot](../tests/test_jubelio_order_snapshots.py); belum connector/write-back |
| EX14 | Export per domain, mapping ID, cutoff, saldo awal/delta/arsip, control totals | P32 | Belum fixture migrasi penuh; payload snapshot existing hanya contoh ingestion |
| EX15 | Runbook backup/restore, cutover/rollback, target dan hasil latihan | P33 | [Backup](../tests/test_backup_download.py); belum bukti target RPO/RTO operasional |

Alur pengumpulan dan persetujuan:

1. Pemilik proses menyediakan contoh di lokasi akses terbatas. A0 mencatat ID bukti,
   peran pemilik dan ruang lingkup; jangan menaruh file mentah atau tautan ber-token
   di repo/issue publik. Catat juga proses yang tidak terlihat oleh akun pemeriksa.
2. Buat versi sintetis yang mempertahankan struktur, relasi ID, status, kasus tepi,
   dan hubungan hitung. Ganti identitas, kontak, rekening, nominal dan referensi
   sensitif secara konsisten. Simpan mapping ke sumber asli hanya di lokasi terbatas.
3. Pemilik memeriksa bahwa struktur/aturan/kasus tetap representatif, menetapkan
   hasil per baris dan total, serta menyetujui versi untuk PR/CI. Catat checksum
   file yang disetujui, revisi Dxx, approver, waktu dan referensi approval aman.
4. Baru tandai `APPROVED_SYNTHETIC`; tautkan file fixture dan tes paket penerima.
   Tanpa approval tetap `MISSING_OWNER_APPROVAL`; data yang tidak berlaku harus
   diberi keputusan eksplisit beserta alasan, bukan disembunyikan dari register.

## Gerbang freeze dan sign-off

| Pemeriksaan | Status saat ini | Bukti / tindak lanjut |
|---|---|---|
| Tiap proses memiliki input, aktor, status, hasil, koreksi, laporan, PJ | Tersusun untuk 34 proses cakupan roadmap | [Register P01-P34](f01-process-register.md); pemilik masih harus memvalidasi role, cakupan dan state target |
| Matriks legacy ke One ke keputusan | Tersusun; parity belum diterima | Tiap Pxx mempunyai bukti One, Dxx dan paket penerima; bukti legacy belum tersedia |
| Tidak menutup gap hanya karena akun audit tidak melihatnya | Diterapkan pada inventaris | Tidak ada gap berstatus selesai; proses tidak ditemukan tetap terbuka |
| Ketidakpastian bisnis ditutup dan kontrak siap F02 | Belum terpenuhi | D01-D20 OPEN; aturan upah/valuasi/accounting/kanal tidak ditebak |
| Contoh dokumen disamarkan dan disetujui | Belum terpenuhi | EX01-EX15 MISSING_OWNER_APPROVAL |
| Reviewer lintas domain dan A0 menerima hasil | Menunggu | Catat review produksi/payroll, commerce/finance dan quality/operations pada PR; jangan menganggap merge sebagai approval bisnis |
| Seluruh pemilik proses menyetujui freeze | Menunggu | Tabel sign-off di bawah belum disahkan |

| Pemberi sign-off (peran, nama belum ditetapkan) | Lingkup | Status / waktu / referensi approval |
|---|---|---|
| Produksi + QC + gudang | P03-P16, D02-D05/D13 | PENDING / belum ada / belum ada |
| HR/payroll | P20-P24, D04-D08/D17 | PENDING / belum ada / belum ada |
| Sales/kanal + purchasing + marketing | P06-P07, P15-P19, P25/P28, D09-D12/D16/D18 | PENDING / belum ada / belum ada |
| Finance/accounting | P18-P19, P22-P28, D07-D15/D19 | PENDING / belum ada / belum ada |
| Operasi/master/akses/laporan | P01-P02, P29-P34, D01/D16-D20 | PENDING / belum ada / belum ada |
| A0 + reviewer A1/A2/A3 | Kelengkapan register, bukti, kontrak penerima dan dependensi W0 | PENDING / belum ada / belum ada |

Syarat freeze: cakupan dikonfirmasi semua role, Dxx disahkan dengan EXxx yang
representatif (atau keputusan tidak berlaku beserta alasannya), hasil sintetis
dapat dihitung ulang, dan sign-off tertaut ke revisi artefak. Perubahan setelah
freeze harus mencatat dampak pada kontrak/fixture/paket. Sampai syarat ini terpenuhi,
#40 tetap terbuka dan W0 belum lolos; F02 boleh inventaris read-only tetapi tidak
mengklaim kontrak bisnis final. Paket berikutnya mengikuti dependensi penerimaan #39.

## Handoff teknis

- Branch: `docs/f01-business-process-register`, worktree khusus F01.
- Commit dasar: `2bee57075b2e0826dfcd581691d37585e7dd1df2`.
  Commit akhir artefak: commit pada PR yang menambahkan dokumen ini; SHA lengkap
  dicatat pada body PR sesudah commit agar tidak membuat referensi diri yang berubah.
- Perubahan: `README.md`, `docs/f01-process-register.md`,
  `docs/f01-decisions-evidence.md`. Tidak mengubah runtime, kontrak API, schema,
  migrasi atau versi aplikasi; tidak memerlukan nomor migrasi baru.
- Bukti verifikasi dan perintah dicatat pada body PR dengan SHA yang diuji.
  Pemeriksaan struktur/tautan dokumen tidak membuktikan aturan bisnis benar.
  Tes existing menguji perilaku baseline, bukan penerimaan payroll/accounting baru.
- Risiko utama: daftar role/proses belum divalidasi pemilik, belum ada dokumen
  approved, dan snapshot/approval dapat disalahartikan sebagai transaksi native.
  Dxx dan EXxx membuat keterbatasan tersebut terlihat bagi paket penerima.
- Langkah berikutnya: A0 menunjuk pemilik dan reviewer, meminta EX01-EX15,
  menyelesaikan D01-D20, memperbarui state/aktor/laporan register, lalu meminta
  sign-off pada revisi yang sama. Tidak ada klaim reviewer telah menerima hasil.


## Status bukti per keputusan — overlay audit permukaan

`PRIOR_AUDIT_REPORTED` berarti issue #40 merangkum apa yang tampak di UI; sumber mentah dan record-level trace tidak tersedia. Lihat paket keputusan `docs/f01-owner-decisions.md` untuk masing-masing keputusan: legacy yang dilaporkan, unknown, proposal, alternatif, ilustrasi sintetis, dampak, dan pertanyaan. Tidak ada Dxx berstatus APPROVED.

| Dxx | Bukti UI terdahulu yang relevan | Status aturan legacy | Bukti yang kurang |
|---|---|---|---|
| D01 | EV-F01-0008, EV-F01-0009, EV-F01-0012 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | BLOCKED_BY_FIELD_AND_TRANSACTION_EVIDENCE |
| D02 | EV-F01-0011 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_LEGACY_TRACE |
| D03 | EV-F01-0011 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_TRANSACTION_TRACE |
| D04 | EV-F01-0003, EV-F01-0009, EV-F01-0010 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_SLIP_AND_HISTORY_TRACE |
| D05 | EV-F01-0003 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_OWNER_AND_LEGACY_CASES |
| D06 | EV-F01-0002 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_SLIP_TRACE |
| D07 | EV-F01-0002 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_LINKED_SLIP_AND_PAYMENT_TRACE |
| D08 | EV-F01-0004 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_LINKED_CASHBON_PAYROLL_TRACE |
| D09 | EV-F01-0005, EV-F01-0015 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_CHANNEL_TRACE |
| D10 | EV-F01-0005 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_POS_TRANSACTION_TRACE |
| D11 | EV-F01-0006 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_POS_PAYMENT_TRACE |
| D12 | EV-F01-0007 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_AP_TRANSACTION_TRACE |
| D13 | EV-F01-0013, EV-F01-0016 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_COST_AND_ANOMALY_TRACE |
| D14 | EV-F01-0001, EV-F01-0017 | DIRECTION_SELECTED_BY_USER (Opsi B: Native full accounting); detail kebijakan OPEN | Detail COA/akun kontrol, event/timing pengakuan, pajak, periode lock, dan laporan |
| D15 | EV-F01-0019, EV-F01-0002 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_ACCOUNTING_WORKFLOW_EVIDENCE |
| D16 | EV-F01-0014, EV-F01-0015 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_REPORT_AND_DOWNLOAD_TRACE |
| D17 | EV-F01-0012, EV-F01-0015 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_ROLE_OWNER_AND_ACCESS_EVIDENCE |
| D18 | EV-F01-0001, EV-F01-0015 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_CHANNEL_AND_VENDOR_TRACE |
| D19 | EV-F01-0016, EV-F01-0017 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_EXPORT_AND_PROFILE |
| D20 | EV-F01-0001, EV-F01-0018 | PRIOR_AUDIT_REPORTED / PROPOSED (bukan rule verified) | NEEDS_OPERATIONS_AND_UAT_EVIDENCE |

### Koreksi periode akuntansi

Klaim draf awal bahwa `/settings/periods` sudah diamati dihapus. Sumber audit dan daftar navigasi yang tersedia tidak mendukung klaim itu; status path **UNVERIFIED**. Periode payroll bukan bukti period-close akuntansi. Tidak menyimpulkan seluruh proses accounting tidak ada karena menu tidak tampak pada catatan audit.
