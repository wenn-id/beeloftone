# A01: kesiapan ledger keuangan dan kontrak posting

Persiapan [#46](https://github.com/wenn-id/beeloftone/issues/46), diperiksa pada
22 September 2026, commit `4f24ea0ec307ffff419659cf2ea5d22b1dc0e72c`,
v0.97.0/schema 55. **BLOCKED_F02/M02: belum implementasi atau business accepted.**

[F02](f02-shared-contracts.md) masih DRAFT dan [M02](m02-master-readiness.md) baru
pemetaan gap tanpa master organisasi native. #41/#44 masih terbuka. Issue #46
mensyaratkan penerimaan dependensi dan spesifikasi pemilik accounting; keputusan
[D13–D15](f01-decisions-evidence.md) masih OPEN. Dokumen ini tidak menetapkan COA,
metode biaya, pajak, timing pengakuan atau aturan periode, dan tidak menutup #46.

## Baseline dan sumber yang perlu dihubungkan

Belum ada master akun, periode pembukuan buka/tutup, journal header/lines native,
registry sumber posting atau trial balance pada schema 55. Inventaris persisten
ada di [F02 ownership](f02-ownership.csv). Tabel bernama payroll posting adalah
snapshot eksternal, bukan buku besar Beeloft.

| Domain | Bukti existing | Gap sebelum posting native |
|---|---|---|
| Stok/COGS | Ledger bahan/barang jadi dan reversal fisik; `Store.production_cost` menghitung pemakaian + waste dengan harga PO per batch dan biaya total sewing aktif ([test_production_cost.py](../tests/test_production_cost.py)) | Belum akun WIP/persediaan/COGS, valuasi perusahaan atau jurnal. D13 menentukan komponen/metode; D14 memilih event pengakuan dan akun. Harga/biaya tidak lengkap menghasilkan coverage gap, bukan biaya nol |
| Payroll/kasbon | Approval payroll terpisah dari snapshot status payment/accounting; sewing cost merupakan input total job, bukan charge upah per employee ([test_payroll_accounting_reconciliation.py](../tests/test_payroll_accounting_reconciliation.py)) | Belum payroll/charge/kasbon native. P03/H01/H02 harus memakai sumber charge yang sama dengan costing; jangan menjumlah charge baru dan sewing cost lama untuk jasa sama |
| Sales/AR | Settlement marketplace menyimpan nominal komponen dan FK shipment, dengan reversal tersendiri; margin memakai lineage sampai produksi ([marketplace_sale_settlements.sql](../beeloft/marketplace_sale_settlements.sql), [test_contribution_margin.py](../tests/test_contribution_margin.py)) | Belum invoice/AR/payment native atau jurnal sales. Settlement operasional tidak otomatis bukti mutasi bank; D09–D11/D14 menetapkan sumber/timing yang sah |
| Pembelian/AP | PO mengunci harga/supplier; penerimaan, retur dan approval pembayaran berjejak ([test_purchase_orders.py](../tests/test_purchase_orders.py), [test_supplier_payment_approvals.py](../tests/test_supplier_payment_approvals.py)) | Approval supplier bukan pembayaran aktual. Pemilik menetapkan basis receipt/invoice, AP settlement with/non-PO dan event pengakuan; bukan otomatis posting kas ketika approved |
| Kas/bank | Nominal keuangan dan payment status dibaca dari snapshot Mekari; belum ledger kas/bank native | Metode bayar, akun, alokasi, bukti transaksi, partial/overpayment dan reversal mengikuti D11/D12/D14 serta master M02 |

Sumber implementasi: [store.py](../beeloft/store.py), terutama `production_cost`,
`create_marketplace_sale_settlement`, `reverse_marketplace_sale_settlement`,
`create_supplier_payment_request` dan `decide_supplier_payment_request`.
Tabel di atas memetakan bukti yang tersedia; bukan daftar event posting yang
telah disetujui.

## Batas snapshot dan ledger native

`MekariPayrollAccounting` menyimpan reference, tanggal, status dan total debit/
kredit ([models.py](../beeloft/models.py), [payroll_accounting.sql](../beeloft/payroll_accounting.sql)).
Total yang berbeda sengaja diterima dan ditandai `posting_unbalanced` oleh
rekonsiliasi. Pertahankan bukti selisih tersebut; jangan menambahkan validasi
jurnal native pada importer snapshot atau mengubah snapshot menjadi jurnal.

Nomor jurnal eksternal atau `status=posted` bukan bukti jurnal native Beeloft.
Snapshot tidak menyediakan baris akun untuk trial balance. Jangan membuat akun
penyeimbang, mengarang baris debit/kredit atau menyimpulkan distribusi per unit.
Posting seimbang juga belum membuktikan akun, pajak, tanggal atau nilainya benar.

`Store._write` sudah menyatukan mutasi, audit dan receipt idempotency dalam write
transaction, dengan pemeriksaan aktor/role terkini. Ini fondasi yang dapat dipakai
ulang, tetapi uniqueness HTTP key belum menjamin satu sumber ekonomi sekali
diposting jika dikirim dengan key berbeda. F02 mengusulkan identitas sumber dan
revision event; kontrak keunikan bisnisnya masih perlu diterima.

## Isian spesifikasi pemilik accounting

Gunakan [register F01](f01-decisions-evidence.md), tanpa membuat daftar keputusan
baru yang bersaing. Setiap jawaban memuat approver, scope unit, tanggal efektif,
revisi dan referensi contoh EX09/EX10 yang telah disamarkan/disahkan.

| Keputusan | Isian yang membuka implementasi |
|---|---|
| D13 | Metode valuasi dan komponen biaya, waste/reject/rework/overhead, WIP, alokasi COGS serta sumber charge yang tidak dihitung ganda |
| D14 | COA dan akun kontrol; per event domain: kapan diakui, akun debit/kredit, sumber nilai, unit/currency, presisi, mode/tahap pembulatan, pajak/potongan; contoh input dan jurnal expected |
| D15 | Periode, posting date/cutoff, locking, late entry, reversal lintas periode, reopen/close dan aturan koreksi. Jangan otomatis memindahkan tanggal ke periode terbuka |
| D01/D17, M02/O01 | Unit dan pihak valid, identitas aktor, hak post/reverse/close/read/export serta pemisahan tugas; role admin existing bukan pengesahan hak accounting perusahaan |
| D18/D19 bila migrasi sumber dipakai | Namespace/authority/cutoff, opening balance atau replay histori untuk scope sama, deduplikasi snapshot/native, mapping sumber dan control totals |
| F02 / A0 | Kontrak producer-to-journal diterima lintas domain; fungsi/file bersama dan nomor migrasi dikoordinasikan dari HEAD terbaru. Nomor belum dipesan |

Pengecualian pembukuan untuk suatu modul harus disetujui secara eksplisit sesuai
#46. Belum adanya producer native bukan alasan membuat jurnal tebakan atau
mengurangi target penggantian backoffice. A01 menyediakan kontrak bersama lebih
awal; finalisasi lintas subledger dan closing A02 menunggu producer tersedia.

## Acceptance setelah kontrak diterima

1. **Seimbang dan tepat.** Uji akun valid/aktif, unit/currency, nilai Decimal dan
   presisi yang disahkan; tolak overflow serta debit/kredit tidak seimbang.
   Cocokkan baris jurnal dengan contoh pemilik, bukan hanya total yang sama.
2. **Sumber sekali.** Kirim event sumber sama dengan key sama, key berbeda dan
   dua penulis bersamaan; tepat satu efek posting. Payload/revision berbeda
   mengikuti kontrak koreksi, bukan jurnal kedua diam-diam. ID sama lintas
   namespace tidak berbenturan; snapshot pasangan tidak menambah efek ekonomi.
3. **Atomik.** Suntik kegagalan setelah header, sebagian lines, audit dan receipt;
   tidak ada transaksi separuh jadi. Buktikan producer dan posting dalam boundary
   atomik yang disepakati F02. Retry setelah rollback menghasilkan satu jurnal.
4. **Reversal/locking.** Reversal menunjuk jurnal asal dan mempertahankan histori;
   uji ulang/concurrent reversal sesuai batas yang disahkan. Tolak posting ke
   periode terkunci. Race post-vs-close diperiksa di write transaction yang sama;
   tanggal reversal lintas periode mengikuti D15, bukan fallback runtime.
5. **Trial balance.** Hitung dari lines jurnal native posted dalam scope akun,
   unit, currency dan periode yang benar, termasuk reversal dan opening balance
   yang disahkan. Uji saldo pembuka + mutasi = penutup, total debit = kredit,
   serta drill-down ke sumber; jangan menyusun laporan dari agregat snapshot.
6. **Kompatibilitas dan akses.** Pertahankan ledger/snapshot existing dan seluruh
   ID/FK. Uji DB baru, upgrade schema 55, rerun, FK/integrity, control totals dan
   backup/restore sintetis. Uji API/UI/error state dan hak server lintas akun/unit;
   invoice, payroll atau payment baru tidak diklaim sudah ada oleh paket ini.

## Bukti baseline dan handoff

Dari root repo, PowerShell:

```powershell
$env:PYTHONPATH = 'tests'
python -m unittest test_f02_contracts test_payroll_accounting_reconciliation test_payroll_payment_reconciliation test_production_cost test_contribution_margin test_purchase_orders test_supplier_payment_approvals test_marketplace_shipping test_audit_trail -v
```

Eksekusi 22 September 2026 dengan Python 3.12.13: **37 tes lulus** dalam
118.335 detik; `uv pip check` dan pemeriksaan 14 tautan lokal juga lulus.
Commit akhir dicatat di PR. Tes ini membuktikan perilaku
existing dan pemisahan snapshot/approval/biaya; bukan acceptance posting atomik,
periode terkunci atau trial balance native. Browser suite tidak dijalankan karena
tidak ada perubahan UI.

Branch `docs/a01-ledger-readiness`; file berubah dokumen ini dan tautan README.
Runtime/API/schema, versi v0.97.0/schema 55 serta dependency tetap. Pemilik A2,
reviewer A1 untuk charge/payroll/stok, A3 untuk namespace/audit dan A0 untuk kontrak/
migrasi. Review serta sign-off accounting masih pending; #46 tetap terbuka dan
PR tetap draft sampai dependensi diterima, implementasi dan acceptance selesai.
