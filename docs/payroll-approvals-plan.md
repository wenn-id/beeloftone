# Approval batch payroll Mekari

## Tujuan

Melanjutkan alur People pada blueprint dari snapshot hasil kalkulasi payroll menuju approval manajemen. Mekari tetap
menjadi sumber kalkulasi dan status payroll; Beeloft hanya menyimpan permintaan, keputusan, dan konteks agregat
yang sudah dibaca dari snapshot.

## Kontrak

- Admin dan operator dapat mengajukan periode berstatus `reviewing` dari snapshot payroll Mekari terbaru.
- Satu ID payroll sumber hanya dapat memiliki satu permintaan yang masih menunggu.
- Admin menyetujui atau menolak. Operator pemohon dapat membatalkan permintaannya sendiri selama masih menunggu.
- Request menyimpan hubungan ke periode snapshot immutable. Jumlah karyawan, gaji bruto, potongan, kontribusi
  perusahaan, gaji neto, dan total biaya perusahaan dibaca dari sumber tersebut.
- Jika snapshot yang lebih baru menghapus periode atau mengubah tanggal, status, jumlah karyawan, nilai, maupun
  waktu pembaruannya, request menjadi stale. Request stale dapat ditolak atau dibatalkan, tetapi tidak dapat
  disetujui.
- Request dan event keputusan immutable, memakai idempotency key dan revision guard.
- Approval payroll masuk ke unified approval inbox sebagai `payroll_batch` dan global audit sebagai approval.

## Antarmuka

Ringkasan Payroll Mekari menampilkan status approval Beeloft pada setiap periode. Periode yang memenuhi syarat
memiliki aksi pengajuan. Rincian approval memperlihatkan status Mekari, nilai agregat, status stale, riwayat, dan
aksi keputusan sesuai role.

## Batas

Milestone ini tidak memanggil API Mekari, mengubah status snapshot, menghitung payroll, menyimpan data gaji per
karyawan, menjalankan pembayaran, membuat jurnal, atau mengelola pajak. Schema naik dari 51 ke 52.
