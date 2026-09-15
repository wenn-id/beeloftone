# Fondasi People dan kehadiran

## Tujuan

Menyediakan sumber data operasional lokal untuk employee master, kehadiran, cuti, absen, dan lembur. Data ini
menutup kebutuhan dasar People pada blueprint tanpa menunggu runtime API Mekari.

## Model data

- `workforce_employees` menyimpan identitas dan kode karyawan yang stabil.
- `workforce_employee_events` menyimpan revisi nama, departemen, dan status aktif.
- `workforce_attendance_records` menjamin satu catatan per karyawan per tanggal.
- `workforce_attendance_events` menyimpan seluruh revisi status, jam kerja, lembur, catatan, alasan, dan aktor.

Keempat tabel tidak dapat diubah atau dihapus. Koreksi dilakukan dengan event revisi baru dan
`expected_revision`, sehingga edit bersamaan tidak menimpa data.

## Aturan operasional

- Admin mengelola employee master. Semua role aktif dapat membaca data.
- Admin dan operator mencatat atau mengoreksi kehadiran.
- Status hadir membutuhkan jam masuk dan pulang pada hari yang sama; menit kerja dihitung dari selisih keduanya.
- Status cuti dan absen tidak membawa jam kerja atau lembur.
- Catatan baru untuk karyawan nonaktif dan tanggal mendatang ditolak. Catatan lama tetap dapat dikoreksi.
- Daftar kehadiran menerima rentang maksimal 366 hari dan menghitung ringkasan dari seluruh hasil filter sebelum
  pagination.

## Batas

Milestone ini belum menambah layar People, roster shift, jenis cuti rinci, approval cuti/lembur, payroll per
karyawan, atau sinkronisasi Mekari. Data sensitif seperti gaji, pajak, rekening, kontak pribadi, dan identitas
pemerintah tidak dicakup.
