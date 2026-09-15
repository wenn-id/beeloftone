# Layar People

## Tujuan

Membuat fondasi People v0.76 dapat dipakai langsung oleh admin, operator, dan viewer dari dashboard. Keputusan
utama layar adalah menemukan karyawan aktif yang belum dicatat pada tanggal kerja terpilih.

## Alur

- Roster menggabungkan employee master aktif dengan kehadiran satu tanggal. Selisihnya diberi teks **Belum dicatat**.
- Filter mencari kode, nama, atau departemen dan memilih status hadir, cuti, absen, atau belum dicatat.
- Admin mengelola master dan membuka riwayat revisi. Operator hanya mengelola kehadiran. Viewer membaca.
- Form hadir mewajibkan jam masuk/pulang. Form cuti dan absen menonaktifkan jam serta lembur.
- Koreksi dan perubahan master memakai revisi terakhir; histori lama tidak diedit.

## Arah desain

Roster memakai daftar datar dengan garis pemisah agar padat tetapi tetap mudah dipindai. Emas hanya dipakai pada
aksi utama dan status selalu ditulis sebagai teks. Ringkasan, field, dialog, fokus keyboard, target sentuh, tema
gelap/terang, reflow HP, dan zoom 200% mengikuti sistem desain dashboard yang sudah ada. Semua angka berasal dari
respons API atau selisih langsung antara master aktif dan catatan tanggal terpilih.

## Batas

Milestone ini tidak menambah tabel atau endpoint. Pagination API dihabiskan sebelum roster dirender. Riwayat UI
menampilkan 100 revisi terbaru; API cursor tetap tersedia untuk kebutuhan audit yang lebih panjang. Roster shift,
approval cuti/lembur, data payroll individu, dan runtime connector Mekari/Jubelio ditunda.
