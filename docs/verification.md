# Verifikasi fondasi v0.1.0

Lingkungan: Windows, Python 3.12.14; dependencies dipasang di virtual environment proyek dari `requirements.txt` melalui `start.ps1 -SetupOnly`.

## Hasil

- `python -m unittest discover -s tests -v`: **18 tes lulus**, 0 kegagalan/error (3.222 detik pada verifikasi akhir sebelum pengemasan).
- `python -m pip check`: **No broken requirements found**.
- Server uvicorn sungguhan di localhost: health, halaman Swagger, OpenAPI, penolakan request tanpa key, transfer parsial 10 pcs, replay request yang sama, dan persistence setelah restart: **lulus**. Database sementara dan server smoke test sudah ditutup.
- Reviewer terpisah memeriksa source, SQL, tes, launcher dan dokumentasi: **tidak ada temuan kritis/penting dalam cakupan backend lokal**; reviewer menjalankan ulang 18 tes dan semuanya lulus.

## Bukti perilaku utama

- Dua request 80 pcs dari saldo 100 secara bersamaan: satu HTTP 201 dan satu HTTP 409; saldo sumber 20, tujuan 80.
- Dua request identik dengan key yang sama secara bersamaan: satu catatan perpindahan, kedua respons identik.
- Kegagalan menulis catatan perpindahan membatalkan perubahan saldo; retry bisa berhasil setelah kendala hilang.
- Pembalikan menyimpan transaksi asli, memerlukan admin/alasan, dan menolak saldo yang sudah tidak mencukupi.
- Key yang dicabut tidak dapat membaca atau replay penulisan lama.
- Backup dibuka sebagai database baru dengan saldo, riwayat dan akun yang sama; tujuan backup yang sudah ada ditolak.

## Batas verifikasi

Belum diuji dengan data riil Beeloft, operator lapangan, perangkat pemindai, beban produksi besar, atau layanan vendor. Tidak ada klaim kesiapan deployment bersama. Belum ada dashboard khusus; Swagger dipakai untuk mencoba API.

## Langkah 2: penghubung dashboard

Endpoint `/api/production-board` ditambahkan dan diuji dengan API/database sungguhan. Suite saat ini **20 tes lulus** (3.293 detik): dua tes tambahan memeriksa ringkasan lintas halaman, pencarian referensi/SKU, filter status, database kosong, order yang ditutup dengan reject, serta akses tanpa key valid. Ini catatan checkpoint backend sebelum UI. Dashboard v0.2.0 kini sudah selesai; hasil terbaru berada di `docs/dashboard-verification.md`.
