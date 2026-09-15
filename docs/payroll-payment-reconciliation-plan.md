# Rekonsiliasi pembayaran payroll

## Tujuan

Melanjutkan alur payroll dari approval menuju payment tanpa menganggap Beeloft sebagai bank atau mesin payroll.
Mekari tetap menjadi sumber status pembayaran; Beeloft menghubungkan status itu dengan konteks batch yang telah
disetujui manajemen.

## Kontrak

- Hanya request terbaru per ID payroll yang menjadi dasar rekonsiliasi, dan request tersebut harus approved.
- Status `reviewing` atau `approved` di Mekari berarti menunggu pembayaran.
- Status `paid` beserta `payment_date` berarti sudah dibayar.
- Periode yang hilang dari snapshot lengkap terbaru menjadi exception.
- Perubahan periode, mata uang, jumlah karyawan, gaji bruto, potongan, atau kontribusi perusahaan menjadi
  exception nominal/konteks.
- Status `draft` atau `cancelled` menjadi exception sumber.
- Ringkasan exact-decimal menghitung gaji neto approved dan gaji neto yang sudah dilaporkan dibayar.
- Semua akun aktif dapat membaca, memfilter, mencari, melakukan pagination, dan membuka approval sumber.

## Antarmuka

Layar tersedia dari kartu Mekari pada kesehatan integrasi dan dari ringkasan Payroll Mekari. Setiap baris
menampilkan periode, jumlah karyawan, nominal approved, status Mekari terbaru, tanggal pembayaran bila ada,
exception yang transparan, dan tautan ke rincian approval.

## Batas

Endpoint bersifat read-only. Milestone ini tidak memanggil API Mekari, mengirim uang, mengubah status payroll,
menyimpan identitas/rekening/gaji per karyawan, atau membuat jurnal. Schema tetap 52.
