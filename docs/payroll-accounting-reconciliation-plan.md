# Rekonsiliasi akuntansi payroll

## Tujuan

Melanjutkan alur payroll dari payment menuju accounting sambil mempertahankan Mekari sebagai accounting engine.
Beeloft hanya menghubungkan konteks batch yang disetujui dengan status pembayaran dan metadata jurnal agregat
yang dibaca dari snapshot lengkap terbaru.

## Kontrak snapshot

- Metadata accounting bersifat opsional dan menempel pada periode payroll dalam payload snapshot Mekari.
- Satu periode snapshot menyimpan paling banyak satu metadata jurnal immutable.
- Metadata memuat status `draft`, `posted`, atau `reversed`, referensi jurnal, tanggal posting, total debit/kredit,
  dan waktu pembaruan.
- Jurnal draft tidak memiliki tanggal posting; jurnal posted atau reversed wajib memiliki tanggal posting.
- Nilai debit dan kredit disimpan sebagai integer minor unit dan dibandingkan sebagai exact decimal.
- Snapshot boleh memuat debit dan kredit tidak seimbang agar masalah dari sumber tetap dapat direkonsiliasi.

## Rekonsiliasi

- Hanya request terbaru per ID payroll yang menjadi dasar, dan request tersebut harus approved.
- Sumber reviewing atau approved berarti menunggu pembayaran.
- Payroll paid tanpa jurnal atau dengan jurnal draft berarti menunggu posting.
- Jurnal posted harus seimbang dan debitnya harus sama dengan total biaya perusahaan approved.
- Sumber yang hilang atau berubah, status draft/cancelled, jurnal reversed, jurnal tidak seimbang, dan nominal jurnal
  yang berbeda menjadi exception yang eksplisit.
- Ringkasan menghitung biaya perusahaan approved dan biaya yang telah diposting.
- Semua akun aktif dapat membaca, memfilter, mencari, melakukan pagination, dan membuka approval sumber.

## Batas

Milestone ini tidak menambah runtime call ke Mekari, endpoint posting, chart of accounts, detail baris jurnal,
identitas karyawan, rekening, pajak, atau gaji per karyawan. Endpoint rekonsiliasi bersifat read-only. Runtime
connector Mekari/Jubelio tetap ditunda sampai API resmi tersedia. Schema naik dari 52 ke 53.
