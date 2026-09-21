# M02: kesiapan unit usaha, lokasi, pihak dan employee

Persiapan [#44](https://github.com/wenn-id/beeloftone/issues/44), diperiksa pada
22 September 2026, commit `3dd91b92c121dce79aceb5edc8566158315f46e1`,
v0.97.0/schema 55. **BLOCKED_F02: belum implementasi atau business accepted.**

Issue #44 mensyaratkan penerimaan #41 sebelum implementasi yang bergantung padanya.
[F02](f02-shared-contracts.md) masih DRAFT, sign-off masih PENDING dan keputusan
[F01](f01-decisions-evidence.md) masih OPEN. Merge PR #77 atau dokumen persiapan
M01 #79 tidak membuka gerbang tersebut. Dokumen ini tidak menyelesaikan #44.

## Pemetaan HEAD ke hasil kerja M02

| Area | Perilaku existing dan sumber | Gap terhadap M02 |
|---|---|---|
| Unit usaha | Belum ada master business unit atau FK unit pada transaksi dalam schema 55; inventaris [F02](f02-ownership.csv) | Identitas unit, scope transaksi/akses dan pemetaan histori perlu D01/D17. Jangan memasukkan semua histori ke unit default tanpa keputusan |
| Storage/lokasi | Batch bahan menyimpan `location`; barang jadi, transfer, picking, staging, retur, adjustment dan stock count memakai teks lokasi ([models.py](../beeloft/models.py), [warehouse_movements.sql](../beeloft/warehouse_movements.sql)) | Belum ID storage/lokasi stabil. Nama sama lintas unit atau beda konteks belum dapat dipetakan otomatis |
| Supplier | Master UUID/kode/nama/contact/address; kode diubah ke huruf besar oleh API. PO memakai `supplier_id` FK dan snapshot JSON supplier ([purchase_orders.sql](../beeloft/purchase_orders.sql)) | Belum status aktif, perubahan master berversi atau mapping ID legacy. Penerimaan bahan langsung masih menerima supplier teks, sehingga validasi pihak belum menyeluruh |
| Customer/metode bayar | Piutang Mekari menyimpan external customer ID/nama pada snapshot; supplier payment merupakan approval, bukan pembayaran native ([models.py](../beeloft/models.py), [F02](f02-shared-contracts.md)) | Belum master customer/metode bayar native. Snapshot customer bukan master yang sudah disahkan; terms PO bukan metode bayar |
| Employee | `workforce_employees` menyimpan ID/kode stabil; event menyimpan nama, department, active dan revision. Kehadiran serta permintaan cuti/lembur memakai ID ([workforce.sql](../beeloft/workforce.sql), [store.py](../beeloft/store.py)) | Belum position terpisah, unit usaha atau mapping legacy. Department tidak otomatis berarti jabatan; user login juga bukan employee |
| Job/payroll | `SewingJobCreate` menyimpan `assignment_type=internal/makloon` dan `assignee` teks; snapshot payroll hanya agregat periode dengan employee count ([sewing.sql](../beeloft/sewing.sql), [mekari_payroll_snapshots.sql](../beeloft/mekari_payroll_snapshots.sql)) | Tidak ada FK employee pada job atau payroll per employee. Nama bebas tidak cukup untuk memetakan orang, tim dan vendor; agregat payroll tidak bisa dipecah menjadi slip per employee |

UI People sudah memiliki pencarian/filter employee, form perubahan dan histori.
UI supplier menyediakan master dan pilihan pada PO; form sewing masih meminta
assignee teks. Ini hasil inspeksi sumber [app.mjs](../beeloft/static/app.mjs),
bukan hasil browser acceptance fitur M02 yang belum ada.

Status nonaktif sudah punya aturan khusus pada kehadiran: `save_attendance`
menolak catatan baru untuk employee nonaktif, tetapi mengizinkan koreksi catatan
existing. Jangan menggantinya dengan larangan global yang memutus koreksi histori.
Perilaku baseline ini diuji `test_inactive_employee_history_audit_immutability_backup_and_migration`
di [test_workforce.py](../tests/test_workforce.py); bukan pengesahan aturan semua domain.

## Keputusan sebelum implementasi

| Referensi / pihak penentu | Jawaban atau bukti yang diperlukan |
|---|---|
| D01 / EX01, operasi + pemilik master | Struktur unit/storage/lokasi, kode unik global atau per unit, kolom wajib/dihapus beserta alasan, position berbeda dari department atau tidak, aturan aktif/nonaktif dan tanggal efektif |
| D01 / EX01, HR + produksi | Mapping ID employee legacy ke ID existing; penanganan nama sama, employee ganti nama, assignee tim dan vendor makloon. Jangan membuat employee otomatis dari teks assignee |
| D17 / EX12, pemilik role | Hak baca/catat/ubah/nonaktif/impor/approve per unit dan data pribadi yang diperlukan. Izin admin/operator/viewer baseline belum matriks role perusahaan |
| D09/D11/D12, bila customer/metode bayar dipakai | Proses sales/pembayaran yang disahkan, pihak dan metode yang diperlukan, hubungan vendor makloon dengan supplier. M02 tidak menetapkan invoice, alokasi pembayaran atau rumus settlement |
| D18/D19, bila impor/cutover dipakai | Namespace sumber dan ID, cutoff, kebijakan konflik/duplikat, bukti mapping location teks dan pihak lama; kasus ambigu tetap unresolved sampai diputuskan |
| F02 / A0, A1/A2/A3 | Penerimaan kontrak, scope transaksi wajib referensi baru, pembagian fungsi/file bersama dan nomor migrasi setelah memeriksa HEAD |

Keputusan harus menyertakan scope, approver, tanggal berlaku dan bukti aman
dipublikasikan. Hanya gunakan fixture sintetis di repo/PR/CI. Jangan menambah
alamat, kontak, nomor identitas atau rekening pribadi tanpa kebutuhan proses;
data existing yang dipertahankan/dihapus tetap dicatat dalam kamus kolom F01.

## Acceptance yang harus dibuktikan setelah kontrak diterima

1. Semua transaksi dalam scope yang disahkan menunjuk unit/lokasi/pihak valid;
   ID hilang, salah unit atau nonaktif ditolak server sesuai aturan. Uji juga
   scope baca dan koreksi histori, bukan hanya pilihan di form.
2. Mapping legacy bersumber eksplisit, mempertahankan ID/FK existing, teks asal
   dan jejak persetujuan. Uji lokasi bernama sama di dua unit, variasi kapital,
   supplier/customer dengan nama sama, dan impor ulang dengan key berbeda.
   Konflik tidak digabung diam-diam atau ditimpa dengan kecocokan nama.
3. Pemetaan lokasi mencakup batch bahan, penerimaan/transfer barang jadi,
   fulfillment, retur, adjustment dan opname beserta reversal. `_warehouse_balances`
   dan trigger SQL memakai teks lokasi untuk saldo: migrasi harus menjaga saldo
   per receipt/lokasi/status, bukan sekadar total stok. Jangan mengedit ledger lama
   untuk mengganti label atau menghilangkan bukti lokasi asal.
4. Job internal memakai ID employee yang sama dengan People; kontrak konsumsi
   diserahkan ke A1 P03/H01. Uji employee bernama sama/ganti nama/nonaktif dan job
   makloon secara terpisah. Histori assignee tetap terbaca dan mapping ambigu
   tidak dianggap payroll-ready. Snapshot payroll agregat tetap agregat.
5. Gunakan `_write` dan event/revision existing untuk mutasi yang relevan. Uji
   idempotency, konflik revisi, dua penulis bersamaan, rollback kegagalan audit,
   dan actor/role server. Status nonaktif tidak boleh menghapus histori.
6. UI memakai ID pada pilihan yang jelas unit/kode/namanya, dengan pencarian,
   loading/kosong/error/retry, keyboard dan penolakan nonaktif. Uji alur transaksi
   pengguna sesungguhnya setelah API dan mapping tersedia.
7. Koordinasikan nomor migrasi dengan A0; nomor belum dipesan. Uji database baru,
   upgrade schema 55 dan rerun, `integrity_check`, `foreign_key_check`, control
   totals qty/uang/record sebelum-sesudah serta backup/restore sintetis.

## Bukti baseline dan handoff

Dari root repo, PowerShell:

```powershell
$env:PYTHONPATH = 'tests'
python -m unittest test_f02_contracts test_workforce test_workforce_approvals test_materials test_finished_goods test_warehouse_movements test_purchase_orders test_sewing_jobs test_mekari_payroll_snapshots -v
```

Eksekusi 22 September 2026 dengan Python 3.12.13: **44 tes lulus** dalam
33.472 detik. Commit akhir dicatat di PR. Tes ini memverifikasi perilaku
existing, bukan acceptance master unit/lokasi/pihak atau job/payroll baru.
Browser suite tidak dijalankan karena tidak ada perubahan UI.

Branch: `docs/m02-master-readiness`. File berubah: dokumen ini dan tautan README.
API/model/store/UI/schema, versi dan dependency tidak berubah. Pemilik paket A2,
reviewer A1 untuk employee/job/payroll, A3 untuk identitas sumber/impor dan A0
untuk kontrak/migrasi; seluruh review/sign-off masih pending. PR tetap draft,
#44 tetap terbuka sampai dependensi diterima, implementasi dan acceptance selesai.
