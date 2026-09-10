# Verifikasi kendala produksi v0.3

Tanggal: 10 September 2026. Python 3.12, Windows, Edge headless.

- `python -m unittest discover -s tests -v`: 26 tes lulus. Lima tes baru mencakup create/resolve/retry, konflik request, izin, validasi, PIC nonaktif, dua penyelesaian bersamaan, pagination cursor saat ada catatan baru, serta migrasi berulang tanpa perubahan tabel lama.
- `node tests/test_client.mjs`: lulus; escaping, retry payload/key yang sama, autentikasi dan error.
- `python tests/run_browser.py --node ... --playwright-module ...`: lulus. Alur lama tetap berjalan, termasuk gangguan respons setelah commit, refresh, login ulang, recovery dan pembalikan.
- Alur browser tambahan: catat kendala per SKU/tahap/PIC, tampilkan teks dengan karakter HTML secara aman, filter order berkendala, selesaikan dengan catatan, saldo tetap sama, viewer tidak punya tombol tulis.
- `python -m pip check`: tidak ada dependensi rusak.
- Pemeriksaan visual form desktop 1440px dan mobile 390px: label, tombol, focus dan isi terlihat; tidak ada overflow horizontal. Uji browser umum juga meliputi 320/768/1440px, teks 200%, dan mode gelap.
- Review kode independen menemukan masalah pagination offset saat catatan baru masuk. Diganti cursor `before` berbasis sequence; regression test dan review ulang lulus tanpa temuan tersisa.
- Server demo dihentikan sebelum backup memakai SQLite backup API. Setelah startup v0.3, isi users, products, orders, order_lines, balances, movements, requests dibandingkan dengan backup: identik. Schema naik dari 1 ke 2.
- Preview lokal berhasil dibuka ulang dan form baru diperiksa. Screenshot menggunakan draft contoh yang tidak disimpan.

Artefak: `../docs/openapi.json`, `../../beeloft-kendala.png`, `../../beeloft-one-kendala.zip`.
Backup lokal (tidak ikut ZIP): `../data/backups/demo-before-v03.sqlite3`.

Batas: pengujian lokal, bukan load test/deployment lintas perangkat. Kendala tidak otomatis mengunci perpindahan. Perubahan data oleh pengguna lain terlihat setelah muat ulang.
