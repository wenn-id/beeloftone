# Verifikasi dashboard v0.2.0

## Hasil

- Python 3.12 / Windows: **21 tes unittest lulus**, termasuk endpoint papan produksi, assets dashboard, role checks dan seluruh invariant backend sebelumnya.
- `node tests/test_client.mjs`: lulus untuk escaping HTML, format tanggal, auth header, normalisasi error, serta body/key yang identik ketika retry.
- `python tests/run_browser.py`: lulus melalui Microsoft Edge headless + Playwright dan server HTTP/SQLite sementara. Runner, script browser dan client checks ikut disertakan dalam source.
- `pip check`: tidak ada dependency yang bertentangan.

## Alur browser yang diuji

1. Key salah ditolak, key admin berhasil masuk.
2. Pencarian tanpa hasil, lalu kembali ke daftar.
3. Membuat SKU (termasuk nama dengan karakter HTML), order dua SKU, dan membaca target 50 pcs dari database.
4. Memindahkan 10 pcs. Respons sengaja diputus setelah server commit, halaman direload, masuk ulang, retry mendapat 401 simulasi, lalu masuk ulang dan retry sekali lagi. Database tetap berisi tepat satu transaksi dengan jumlah 10 pcs.
5. Koreksi membalik transaksi itu sehingga planned kembali 50 pcs, catatan asli tetap terlihat sebagai sudah dibalik.
6. Respons Master SKU sengaja ditunda; dialog ditutup dan form order baru dibuka. Respons lama tidak mengganti atau menghapus draft form yang baru.
7. Viewer tidak memiliki tombol membuat order/perpindahan/koreksi; operator dapat memindahkan barang tetapi tidak mengoreksi. Backend tetap memeriksa role secara independen.
8. Mode gelap dan terang, lebar 320/390/768/1440, dan pembesaran teks 200% pada lebar 390: tidak ada overflow horizontal halaman detail.
9. Dialog native bisa ditutup dengan Escape; Tab tidak mengaktifkan kontrol halaman di belakang dialog. Pemeriksaan visual dilakukan pada screenshot desktop, detail, dark, dan mobile.
10. Tidak ada JavaScript page errors dalam alur acceptance.

## Review dan perbaikan

Reviewer terpisah mereproduksi kehilangan state pemulihan setelah 401, balasan dialog terlambat, dan respons simpan lama yang dapat menghapus pending request lebih baru. Ketiganya diperbaiki. Pemeriksaan ulang reviewer mengonfirmasi state pemulihan dipertahankan, dialog lama tidak menimpa form baru, dan cleanup hanya menghapus key transaksi yang selesai. Tidak ada temuan penting tersisa pada pemeriksaan terbatas tersebut.

## Antislop selama implementasi

Arah berasal dari blueprint pengguna; alasan warna, huruf, komposisi, gerak dan kontrol dijelaskan di `DESIGN.md` (ENERGY 2 / RHYTHM 2 / MOTION 1). Angka berasal dari database; seluruh fixture diberi label DEMO/CONTOH.

Rasio kontras yang dihitung: tinta utama terhadap background 13.02:1, teks sekunder 5.67:1, tombol emas/putih 5.76:1; mode gelap teks utama 12.62:1 dan sekunder 7.67:1. Pasangan error/sukses yang diuji di atas 4.5:1. Batas input 3.93:1 (terang) dan 4.60:1 (gelap). Focus ring mengikuti aksen dengan kontras tinggi. Ini pemeriksaan pasangan warna dan interaksi, bukan sertifikasi aksesibilitas.

## Batas

Rilis tetap lokal: belum deployment banyak perangkat, akun SSO, data riil Beeloft, bundle/barcode atau BOM/kain. Data tidak otomatis refresh dari perangkat lain. QA mobile memakai viewport browser desktop, bukan perangkat fisik dengan keyboard layar. Pemulihan request bergantung pada sessionStorage tab yang sama; key akses hanya disimpan di memori dan harus dimasukkan kembali setelah reload.
