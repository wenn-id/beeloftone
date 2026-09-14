# Verifikasi jejak produksi batch bahan, v0.63

Tanggal: 14 September 2026. Base `e44e449`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak mengubah data operasional.

## Backend

Dua acceptance test baru memeriksa rantai penerimaan batch, reservasi, pengeluaran, pemakaian/waste,
cutting, bundle, handoff dua pihak, sewing, finishing, final QC, dan penerimaan barang jadi. Koreksi
setiap tahap tetap tampil sebagai event terpisah, saldo batch berakhir nol setelah koreksi penuh, dan
tautan rincian menunjuk objek yang benar. Snapshot database sebelum dan sesudah GET identik.

Cursor gabungan timestamp/event ID diuji dengan enam event pada timestamp yang sama serta event baru
yang masuk setelah halaman pertama. Hasil paging identik dengan snapshot awal tanpa duplikasi. Admin,
operator, dan viewer mendapat laporan yang sama; limit, pasangan cursor, autentikasi, serta ID hilang
tetap divalidasi.

Modul terkait lulus: 10 test dalam 22,980 detik. Seluruh regression backend lulus: **299 test dalam
578,743 detik**, melalui `python -m unittest discover -s tests -p 'test_*.py'`.

## Browser dan visual

Seluruh suite Edge/Playwright lulus tanpa error JavaScript. QA membuka batch melalui QR sebagai viewer,
memaksa GET pertama gagal, mencoba lagi, lalu memeriksa penerimaan, issue, pemakaian, cutting, bundle,
sewing, hasil sewing, finishing, final QC, dan barang jadi. Teks sumber `<A>` dirender sebagai teks,
tombol barang jadi membuka rincian yang benar, dan cursor yang tidak diperlukan disembunyikan.

Screenshot `outputs/qa-v063/beeloft-material-traceability-mobile.png` diperiksa pada lebar 390 px dan
teks 200%. Dialog tidak overflow horizontal, teks membungkus, dan kontrol tetap dapat dipakai.

## Pemeriksaan rilis

Client checks, syntax 50 file JavaScript, compile Python, dan `pip check` lulus. OpenAPI memakai 0.63.0
dan memuat route beserta limit/cursor. Paket memakai 0.63.0; schema tetap 48 dan `integrity_check`
mengembalikan `ok`. Pemeriksaan `git diff --check` lulus.

## Antislop delivery gate

Design Read: dashboard operasional internal untuk tim Beeloft, bahasa visual tinta/emas dari blueprint,
ENERGY 2 / RHYTHM 2 / MOTION 1.

- R-02 PASS: string UI baru tidak memakai em dash.
- R-03 PASS: dialog diuji pada 390 px dan teks 200% tanpa overflow.
- R-17 PASS: angka berasal dari respons endpoint dan ledger database.
- R-18 PASS: tidak ada testimonial atau identitas rekaan.
- R-23 PASS: tidak ada aset visual atau struktur navigasi baru.
- R-24 PASS: semua tombol menuju dialog/rincian yang sudah tersedia.
- R-25 PASS: komponen memakai token warna tema yang sudah dipakai dan diuji pada kedua tema oleh suite.
- R-26 PASS: scan, retry, muat ulang, history, PO/QC kondisional, dan tautan event mempunyai aksi nyata.
- R-27 PASS: loading dan error diuji; batch valid selalu mempunyai minimal event penerimaan.
- R-28 PASS: tidak ada FAQ.
- R-32 PASS: kontrol native dapat ditab, dialog menutup dengan Escape, dan fokus memakai style proyek.
- R-33 PASS: UI diedit langsung di `app.mjs`, tanpa patcher runtime.
- R-34 PASS: suite browser melewati tema terang dan gelap tanpa error.
- R-35 PASS: seluruh kontrol baru diklik dalam Edge dan console bersih.
- R-36 PASS: tidak ada klaim keamanan, performa, atau pelanggan.
- R-37 PASS: keputusan mengikuti `DESIGN.md` dan dials proyek.
- R-38 PASS: semua isi berasal dari fixture nyata pada database QA.
- R-01 PASS: tidak ada gradient atau glow baru.
- R-04 PASS: tidak ada ikon baru.
- R-06 PASS: typography proyek dipakai tanpa perubahan.
- R-07 PASS: tidak ada pola latar baru.
- R-08 PASS: tidak ada panah dekoratif pada tombol baru.
- R-09 PASS: status ditampilkan sebagai data, tanpa badge dekoratif baru.
- R-10 PASS: tidak ada glassmorphism baru.
- R-12 PASS: tidak ada shadow baru.
- R-13 PASS: tidak ada glow baru.
- R-14 PASS: kartu event dipakai karena tiap ledger membutuhkan struktur detail yang sama.
- R-19 PASS: tidak ada animasi baru, sesuai MOTION 1.
- R-22 PASS: tidak ada ilustrasi.
- Liveliness PASS: identitas tinta/emas, hierarchy saldo lalu event, whitespace, dan accent proyek dipertahankan.
- C-1 PASS: setiap elemen melayani identitas batch, saldo, paging, retry, atau drill-down.
- C-2 PASS: semua elemen interaktif mempunyai perilaku dan telah diklik.
- C-3 PASS: hanya ringkasan batch dan ledger yang diperlukan pengguna ditambahkan.
- C-4 PASS: loading, error, viewer, mobile, teks 200%, kedua tema, dan Escape lulus.
- C-5 PASS: angka dan status dibaca dari database QA.
- R-05 PASS: dialog mengikuti aliran informasi batch, bukan template pemasaran.
- R-11 PASS: radius tetap mengikuti 4 px kontrol dan 8 px dialog dari `DESIGN.md`.
- R-15 PASS: label aksi spesifik, seperti Jejak produksi lengkap dan Riwayat stok bahan.
- R-16 PASS: tidak ada buzzword pemasaran.
- R-20 PASS: struktur tetap khas ledger produksi Beeloft.
- R-21 PASS: pilihan tema proyek tetap berfungsi.
- R-29 PASS: palette tinta, kertas, dan emas tidak berubah.
- R-30 PASS: tidak meniru produk lain.
- R-31 PASS: saldo menjadi fokus, event berupa kartu ledger untuk menjaga pasangan label/nilai dan drill-down.

## Comment gate dan batas

- PASS: satu komentar baru mencatat batas performa dan jalur upgrade yang tidak tampak dari kode.
- PASS: komentar singkat, sentence case, tanpa separator, emoji, narasi langkah, atau TODO samar.
- PASS: komentar tidak mengulang deklarasi dan tidak mengubah logika.

Riwayat satu batch disusun di memori; SQL union diperlukan bila batch mempunyai ribuan event. Quantity
bahan dan pcs tidak dijumlahkan. Model cutting satu batch per run tetap berlaku. Runtime connector
Jubelio/Mekari tidak dicakup sampai akses API resmi tersedia.
