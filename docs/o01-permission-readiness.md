# O01: kesiapan izin per fungsi dan pemisahan tugas

Persiapan [#45](https://github.com/wenn-id/beeloftone/issues/45), diperiksa pada
22 September 2026, commit `9bb26a3c98778711608e1228930dd11a679bf5d0`,
v0.97.0/schema 55. **BLOCKED_F02/M02: belum implementasi atau business accepted.**

Issue mengizinkan desain permission setelah F02 dan menunggu M02 untuk scope
organisasi final. [F02](f02-shared-contracts.md) masih DRAFT; [M02](m02-master-readiness.md)
masih persiapan tanpa unit/lokasi stabil. Merge PR #77/#80 bukan penerimaan
kontrak. Dokumen ini hanya inventaris akses baseline dan kebutuhan keputusan,
bukan rancangan permission yang disahkan atau penyelesaian #45.

## Fondasi yang dapat dipakai ulang

- `api.actor` menerima API key atau browser session, memeriksa CSRF untuk mutasi
  session dan menolak `X-Beeloft-Actor` yang tidak cocok. Binding tidak memberikan
  hak tambahan ([api.py](../beeloft/api.py)).
- `Store._write` memeriksa ulang akun aktif dan role di dalam write transaction,
  termasuk sebelum replay receipt; key milik aktor lain ditolak. Mutasi, audit
  dan receipt commit atomik ([store.py](../beeloft/store.py)).
- Session membaca role akun terkini; OIDC menghubungkan issuer/subject ke user
  lokal yang aktif. Pencocokan subject harus persis dan identitas yang tidak
  dikenal ditolak. Jangan mengganti mekanisme ini dengan auth kedua.
- Role teknis masih `admin`, `operator`, `viewer`; belum permission per fungsi,
  membership unit atau scope objek. `Actor` membuktikan identitas, bukan izin
  membaca payroll/keuangan perusahaan.

## Matriks baseline, bukan target bisnis

Matriks ini berasal dari route dan guard Store pada commit di atas. Hak perusahaan
belum diputuskan; tabel tidak boleh dijadikan daftar grant otomatis untuk O01.

| Jalur | Admin | Operator | Viewer | Sumber / batas |
|---|---|---|---|---|
| Baca snapshot/summary payroll dan keuangan Mekari | Ya | Ya | Ya | Route GET hanya memerlukan `Actor`; daftar, detail dan summary tidak memeriksa permission domain |
| Baca payroll approval dan rekonsiliasi payment/accounting | Ya | Ya | Ya | Route GET memanggil Store tanpa actor/scope |
| Impor snapshot payroll/keuangan | Ya | Tidak | Tidak | Mutasi Store melalui `_write` dengan role admin |
| Ajukan approval payroll | Ya | Ya | Tidak | `create_payroll_approval_request`; sumber harus reviewing dan terbaru |
| Setujui/tolak payroll | Ya | Tidak | Tidak | `decide_payroll_approval_request`; guard revision/status/stale tetap berlaku |
| Batalkan pengajuan payroll | Tidak | Hanya pemohon | Tidak | Guard existing membatasi cancellation ke operator pemohon; jangan mengganti dengan asumsi admin boleh semua |
| Inbox/summary approval, command center dan investigasi AI | Ya | Ya | Ya | Belum filter izin domain/unit pada entry point atau reader gabungan |
| Ekspor aktivitas CSV | Ya | Ya | Ya | `/api/activity.csv` memerlukan autentikasi saja; bukan ekspor slip payroll |
| Global audit dan backup database HTTP | Ya | Tidak | Tidak | Guard admin eksplisit; backup berisi database lengkap, bukan export tersaring |

Tidak ada guard pemohon berbeda dari approver untuk **approval payroll admin**:
admin dapat mengajukan dan menyetujui pengajuannya sendiri bila guard domain lain
lolos. Ini hasil inspeksi `create_payroll_approval_request` dan
`decide_payroll_approval_request`, bukan kesimpulan bahwa self-approval semua
domain sama atau aturan bisnis tersebut disetujui.

Baseline payroll berupa agregat periode, bukan slip individual. Meski demikian,
nominalnya tetap tersedia pada API baca dan inbox approval. Acceptance pembatasan
gaji pada #45 belum terpenuhi oleh autentikasi atau tombol tersembunyi saja.

## Jalur yang harus tercakup dalam penutupan gap

| Permukaan | Temuan / pekerjaan setelah keputusan tersedia |
|---|---|
| Pembacaan langsung | Lindungi daftar, detail by-ID, summary, histori dan rekonsiliasi dengan hak domain serta scope unit; validasi filter klien tidak cukup |
| Pembacaan gabungan | `Store.approvals` membawa nominal payroll; `approvals_summary` mengagregasikannya; [command_center.py](../beeloft/command_center.py) membaca ringkasan approval/keuangan dan [brain.py](../beeloft/brain.py) membaca approval. Periksa hasil AI, evidence, investigation tersimpan dan proposal juga; menutup endpoint payroll saja tidak cukup |
| Ekspor/backup | Tentukan hak export terpisah dari read. Uji format yang benar-benar tersedia; jangan mengklaim ada payroll CSV native. Backup adalah akses penuh yang perlu keputusan eksplisit tersendiri, termasuk jalur CLI dengan akses filesystem |
| Mutasi/pay | Pemeriksaan hak dan membership harus mengikuti transaksi `_write`, bukan hanya UI. Payment payroll/supplier native belum tersedia; approval tidak boleh dianggap hak atau bukti membayar |
| Akun/SSO | `provision_user`, `disable_user`, `link_oidc_identity`, `unlink_oidc_identity` memakai transaksi langsung di luar audit `_write`; CLI mengelolanya ([__main__.py](../beeloft/__main__.py)). Belum API perubahan role berversi dan audit perubahan grant/role. Tentukan operator administratif dan bukti audit tanpa merekam key/token |
| Session setelah perubahan hak | Hak role aktif dibaca ulang sekarang. Unlink OIDC tidak dengan sendirinya menghapus browser session yang sudah diterbitkan; putuskan aturan pencabutan session bersama perubahan role/membership/SSO dan uji efeknya |

## Keputusan yang dibutuhkan

[D17 / EX12](f01-decisions-evidence.md) harus menetapkan matriks role perusahaan
untuk baca/catat/approve/pay/export per proses dan unit, khususnya payroll dan
keuangan. Isi juga siapa boleh memberi/mencabut hak, delegasi, self-approval per
jenis proses, akses audit/backup, dan kebijakan session setelah perubahan akses.
Setiap keputusan menyebut scope, approver, tanggal efektif dan bukti yang aman
dipublikasikan. Tidak mengarang role HR/finance atau grant default dari nama jabatan.

[D01 / M02](m02-master-readiness.md) menetapkan unit stabil, membership dan mapping
data lama. Objek tanpa unit dan snapshot lintas unit memerlukan aturan eksplisit;
jangan otomatis memberi akses seluruh unit atau memecah agregat payroll dengan
perkiraan. User login, employee dan pihak adalah identitas berbeda.

A0 menerima kontrak F02 bersama A1/A2/A3, mengoordinasikan objek bersama dan nomor
migrasi setelah HEAD diperiksa ulang. Nomor migrasi O01 belum dipesan.

## Kasus acceptance setelah gerbang terbuka

1. Jalankan matriks positif/negatif setiap fungsi dengan dua akun berbeda,
   dua unit, akun multiunit jika disahkan, akun nonaktif dan data tanpa mapping.
   Uji API key dan session/SSO, request langsung tanpa UI, serta ID objek unit lain.
2. Hak baca terbatas tidak mengungkap nominal lewat daftar, detail, summary,
   pagination/count, inbox, dashboard, AI/evidence/history, export atau backup.
   Pakai fixture sintetis berisi data sensitif contoh; respons kosong saja tidak
   membuktikan filter bekerja. Total harus dihitung setelah scope diterapkan.
3. Cabut role/membership ketika form terbuka, lalu submit/replay key yang sama.
   Penolakan tidak membuat mutasi atau receipt baru. Uji perubahan akses bersamaan
   dengan write; guard harus berlaku atomik bersama efek transaksi.
4. Uji approve sendiri dan approve akun lain sesuai keputusan tiap proses,
   delegasi bila dipakai, cancellation oleh pemohon/nonpemohon, revisi basi dan
   role dicabut. Keputusan di server tetap berlaku walau tombol UI dipalsukan.
5. Audit perubahan role/grant/membership/SSO menyimpan aktor, target, sebelum/sesudah,
   alasan dan waktu; tidak menyimpan credential. Uji kegagalan audit menggagalkan
   perubahan, konflik revision, retry, serta identitas issuer/subject salah.
6. Periksa upgrade schema 55, rerun, FK/integrity, backup/restore dan kompatibilitas
   user/session/SSO existing. Mapping role lama harus disahkan; tidak ada eskalasi
   diam-diam. UI mengikuti hak server dan menyediakan error yang dapat ditindaklanjuti.

## Bukti baseline dan handoff

Dari root repo, PowerShell:

```powershell
$env:PYTHONPATH = 'tests'
python -m unittest test_f02_contracts test_idempotency_actor test_browser_sessions test_session_logout test_oidc_sso test_payroll_approvals test_mekari_payroll_snapshots test_mekari_finance_snapshots test_payroll_payment_reconciliation test_payroll_accounting_reconciliation test_backup_download test_audit_trail test_activity_export test_cli -v
```

Eksekusi 22 September 2026 dengan Python 3.12.13: **96 tes lulus** dalam
206.682 detik; `uv pip check` dan pemeriksaan 9 tautan lokal juga lulus.
Commit akhir dicatat di PR. Tes existing menguji autentikasi,
role teknis, idempotency, audit dan transaksi baseline; bukan pembuktian matriks
perusahaan, scope unit atau larangan baca payroll baru. Browser suite tidak
dijalankan karena tidak ada perubahan UI.

Branch `docs/o01-permission-readiness`; file berubah dokumen ini dan tautan README.
API/model/store/UI/schema, dependency dan versi tidak berubah. Pemilik A3,
reviewer A1 payroll/produksi, A2 keuangan/master organisasi dan A0 kontrak/migrasi;
review serta sign-off bisnis masih pending. #45 tetap terbuka dan PR tetap draft
sampai keputusan/dependensi diterima, implementasi dan acceptance selesai.
