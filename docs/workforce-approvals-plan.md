# Approval cuti dan lembur

## Tujuan

Melanjutkan alur People pada blueprint dari kehadiran menuju cuti, lembur, dan approval tanpa menunggu API
Mekari. Permintaan harus dapat dibaca dari layar People dan inbox approval manajemen yang sama dengan domain lain.

## Model data

- `workforce_requests` menyimpan referensi, karyawan, jenis, tanggal, menit lembur, alasan, dan pemohon.
- `workforce_request_events` menyimpan pengajuan dan keputusan sebagai ledger immutable.
- Cuti dapat memakai rentang berurutan maksimal 366 hari. Lembur selalu satu tanggal dan 1-720 menit.
- Satu karyawan tidak dapat memiliki permintaan pending atau approved yang tanggalnya bertumpang tindih.

Semua koreksi dilakukan melalui status terminal `approved`, `rejected`, atau `cancelled`; baris lama tidak diubah.
Keputusan memakai revisi terbaru dan idempotency key sehingga penyimpanan ulang tidak menggandakan event.

## Hak akses dan alur

- Admin dan operator dapat mengajukan permintaan untuk karyawan aktif.
- Admin menyetujui atau menolak. Pemohon operator dapat membatalkan permintaannya sendiri selama masih pending.
- Viewer dapat membaca daftar dan riwayat, tanpa tombol mutasi.
- Cuti dan lembur muncul sebagai jenis tersendiri di unified approval inbox dan ikut dihitung Command Center.
- Approval menyatakan izin. Ledger kehadiran tetap mencatat kejadian aktual secara terpisah dan tidak diisi otomatis.

## Antarmuka

Layar People menyediakan daftar, filter status/jenis/pencarian, ringkasan, form pengajuan, rincian, dan riwayat
keputusan. Nilai dari API di-escape, status ditulis sebagai teks, dan layout memakai pola responsif yang sudah ada.

## Batas

Milestone ini belum menambah saldo cuti, jenis cuti rinci, jadwal shift, attachment, delegasi approver, payroll per
karyawan, pembayaran, atau sinkronisasi Mekari. Schema naik dari 50 ke 51.
