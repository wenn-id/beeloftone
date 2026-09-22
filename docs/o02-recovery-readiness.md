# O02: drill pemulihan lokal dan runbook operasional

Persiapan [#47](https://github.com/wenn-id/beeloftone/issues/47), baseline
`2883d17cdb07ef96dce0f8d330c789115143e1b1`, 22 September 2026,
v0.97.0/schema 55. **Drill lokal terverifikasi; deployment dan acceptance O02 belum selesai.**

[F02](f02-shared-contracts.md) masih DRAFT dan menjadi gerbang persiapan staging.
[O01](o01-permission-readiness.md) masih inventaris izin; [F03](f03-technical-audit.md)
sudah memuat perbaikan teknis tetapi penerimaan koordinator/bisnis masih PENDING.
#41/#45/#42 masih terbuka. Verifikasi backup existing ini tidak mengubah status
dependensi, menetapkan RPO/RTO atau mengakses lingkungan produksi.

## Bukti yang tersedia dan batasnya

| Area | Baseline / hasil lokal | Belum terbukti |
|---|---|---|
| Backup | `Store.backup` memakai SQLite backup API, tujuan baru, membersihkan hasil gagal; download HTTP admin-only. Tes existing membandingkan seluruh tabel, FK/integrity dan detail order | Jadwal, retensi, salinan luar host, enkripsi/akses lokasi backup dan alert production |
| Restore terpisah | Tes baru menyalin arsip sintetis ke direktori lain, membuka aplikasi baru, memeriksa health/FK/integrity/detail order, replay receipt dan penulisan terisolasi. Hash arsip dan detail sumber tidak berubah | Restore pada host terpisah, transfer arsip besar, pemulihan secret/SSO, durasi penuh incident-to-service dan RPO/RTO yang disahkan |
| Retry/rollback | Tes server memakai kegagalan penyimpanan terinjeksi; client menguji retry dengan key/payload sama. Tes restore memakai transaksi committed sebagai model respons hilang | Disk filesystem benar-benar penuh, koneksi TCP diputus dan crash proses/power-loss saat transaksi |
| Restart | Tes restore membuka instance aplikasi baru pada salinan DB | Restart proses OS, autostart setelah reboot, restart supervisor dan failover host |
| Health | `/health` membuka koneksi dan menjalankan `SELECT 1` | Pemeriksaan ruang disk, freshness backup, write capability, alert delivery atau kesiapan bisnis; HTTP 200 saja tidak membuktikannya |
| Database | SQLite WAL dan transaksi `BEGIN IMMEDIATE`; tes memakai data sintetis kecil | Kapasitas pengguna/volume nyata, latensi persentil, lock wait, pertumbuhan WAL/DB dan throughput production |

Pada Python 3.12.13 lokal, tes baru mencatat **0,273 detik** dari mulai copy
arsip hingga buka aplikasi, validasi dan replay. Pembuatan backup, penyiapan akun,
penulisan baru dan pemulihan infrastruktur tidak masuk durasi tersebut. Angka
ini bukan klaim RTO atau benchmark kapasitas. Waktu berubah antar-eksekusi.

Jalankan ulang dari root repo, PowerShell:

```powershell
$env:PYTHONPATH = 'tests'
python -m unittest test_backup_download test_cli test_readme_test_count -v
python -m unittest test_production.ProductionTest.test_storage_failure_rolls_back_balance_changes_and_allows_retry test_idempotency_actor.IdempotencyActorBindingTest.test_retry_after_transient_failure_succeeds_with_the_same_key -v
node tests/test_client.mjs
```

Tes baru ada di [test_backup_download.py](../tests/test_backup_download.py).
Eksekusi lokal: 7 tes backup/CLI/jumlah tes lulus dalam 9,993 detik; 2 tes
rollback/retry lulus dalam 1,105 detik; client checks, dependency check dan
pemeriksaan 9 tautan lokal dokumen lulus. Suite penuh 574 tes belum dijalankan
lokal; angka tersebut diverifikasi melalui discovery oleh tes jumlah README.
Semua database, akun dan transaksi fixture sintetis dibuat sementara; key tidak
dicetak oleh tes. [Panduan restore](operations.md#backup-dan-pemulihan) kini selalu
menyalin arsip sebelum startup agar migrasi/login tidak mengubah arsip backup.

## Isian pemilik operasi sebelum deployment

[D20 / EX15](f01-decisions-evidence.md) harus berisi host/OS/domain staging dan
production, jumlah pengguna bersamaan, volume baca/tulis/transaksi/arsip, pola
jam sibuk, target RPO dan RTO, jadwal serta retensi backup, lokasi salinan terpisah,
batas disk, tujuan alert, operator utama/cadangan, dan penentu go/no-go.
Isi nama/kontak internal di catatan akses terbatas, bukan credential atau kontak
pribadi pada issue publik. Saat ini penanggung jawab insiden belum ditunjuk.

F02 menetapkan invariant/retry; D17/O01 menetapkan akses service/admin/backup dan
scope organisasi; D19 menetapkan cutoff, rekonsiliasi transaksi setelah backup dan
perlindungan transaksi baru saat rollback. Semua keputusan memerlukan scope,
approver, waktu berlaku dan bukti. Jangan memilih PostgreSQL atau target kapasitas
dari dugaan; ukur SQLite pada workload yang disahkan terlebih dahulu.

## Runbook deployment, setelah gerbang dibuka

1. Operator mencatat release commit, runtime, schema, dependencies terpin dan
   konfigurasi setiap lingkungan. Pisahkan DB, directory, akun service, backup,
   log dan secret staging/production. `BEELOFT_DB` serta konfigurasi
   `BEELOFT_OIDC_*` tersedia; secret tidak masuk Git, argumen CLI, laporan atau log.
2. Pasang HTTPS dan service supervisor sesuai host yang disetujui. CLI existing
   bind localhost, bukan layanan publik otomatis. Atur trusted proxy secara
   terbatas; uji scheme HTTPS, Secure cookie, redirect URI SSO, login/logout dan
   hak server lewat URL sebenarnya. `start.ps1` bukan service restart manager.
3. Sebelum upgrade, buat backup konsisten dengan versi lama, verifikasi pada
   salinan terisolasi, simpan release asal dan hasil control totals. Latih upgrade
   pada staging; jangan menguji migrasi pada arsip tunggal atau production.
4. Konfigurasikan jadwal backup memakai CLI existing, nama tujuan unik, akses
   terbatas dan salinan terpisah. Alert untuk kegagalan backup, backup terlambat,
   disk rendah dan service tidak sehat harus diuji sampai penerima. Retensi hanya
   menghapus arsip sesuai kebijakan dan sesudah backup baru diverifikasi; tidak
   menghapus satu-satunya salinan terakhir yang dapat dipulihkan.
5. Uji workload baca/tulis campuran yang disahkan; rekam p95/p99, error, lock wait,
   retry, resource, WAL dan hasil invariant. Pilih atau ganti DB berdasarkan
   bukti dan batas yang diterima pemilik, bukan jumlah unit test.
6. Lakukan go/no-go dengan O01/F03 diterima, restore/fault drill berhasil dan
   target operasi terpenuhi. Baru buka akses pengguna. Tidak ada langkah
   deployment di atas yang telah dijalankan oleh PR ini.

## Runbook insiden dan rollback

1. Operator yang ditunjuk mencatat waktu deteksi, release, gejala dan transaksi
   terakhir diketahui. Batasi write bila integritas belum jelas; simpan log dan
   DB/WAL terkait untuk investigasi tanpa mengekspor secret/data sensitif publik.
2. Jika hasil request tidak pasti, periksa receipt/sumber lalu retry sebagai
   aktor asli dengan key dan payload sama. Jangan membuat key baru hanya karena
   timeout. Bedakan respons server ditolak dari commit yang responsnya hilang.
3. Pilih backup terverifikasi dan catat cutoff. Pulihkan **salinan** ke lingkungan
   terpisah, mulai dengan release asal, periksa FK/integrity, control totals,
   saldo, audit/receipt dan sample alur. Ukur durasi deteksi hingga layanan siap,
   serta selisih waktu transaksi terakhir yang dipulihkan terhadap insiden.
4. Rekonsiliasi transaksi setelah cutoff menurut D19 sebelum cutover. Jangan
   menimpa database aktif dengan backup lama karena transaksi baru akan hilang.
   Jangan menurunkan binary ke schema baru yang belum terbukti kompatibel.
5. Periksa kembali akun/grant/session/SSO: backup bisa menghidupkan kembali akses
   yang dicabut setelah cutoff. Terapkan keputusan O01 sebelum membuka jaringan.
6. Koordinator memberi keputusan cutover setelah invariant dan target RPO/RTO
   terukur lolos. Catat data yang belum pulih, penanggung jawab dan tindak lanjut.

Latihan terisolasi berikut masih harus dilakukan setelah host tersedia: penuhi
filesystem/volume khusus disposable, kill/restart service saat write, putuskan
koneksi sebelum dan sesudah commit, lalu retry/reconcile. Jangan memenuhi disk
host pengguna atau menghentikan service production sebagai bagian tes lokal.

## Handoff

Branch `docs/o02-recovery-readiness`; perubahan hanya tes recovery, jumlah tes
README, panduan restore dan runbook ini. Tidak ada perubahan runtime/API/schema,
dependency, migrasi, scheduler, secret atau deployment. Commit akhir dan hasil
uji dicatat di PR. Pemilik A3, reviewer A0 operasi/kontrak dan A1/A2 untuk control
totals domain; sign-off operasi masih pending. #47 tetap terbuka; runbook ini
belum menggantikan konfigurasi host, penunjukan petugas atau fault drill nyata.
