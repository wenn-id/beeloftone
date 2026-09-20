# Bukti pengujian: respons mapping yang tertunda tidak mengganti dialog aktif

Temuan: [issue #27](https://github.com/wenn-id/beeloftone/issues/27) — GET mapping yang selesai
setelah dialog asalnya ditutup mengganti dialog yang sedang terbuka. Draft `Tambah SKU` yang belum
disimpan hilang saat respons lama tiba.

## Baseline

| | |
|---|---|
| Commit baseline | `07680ee02c02dfcfdd942ccca5227bde0492de16` (`main`) |
| Aplikasi / schema | 0.88.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/mapping-dialog-race` |
| Working tree awal | bersih selain `uv.lock` yang tidak terlacak (tidak ikut di-commit) |

Temuan direproduksi ulang terhadap commit tersebut sebelum satu baris pun diubah. Tidak ada checkout
paksa ke commit lama dan tidak ada perubahan lokal yang dibuang.

## Lingkungan

Python 3.14.5 pada venv repositori (`.venv`), Node.js 24.16.0, Playwright dengan Chromium pada
`~/.cache/ms-playwright`, Linux. Seluruh pengujian memakai database sementara sekali pakai
(`tempfile.TemporaryDirectory` pada test dan runner browser); tidak ada database bisnis atau
produksi yang disentuh.

## Reproduksi

`productMappingForm()` dan `unmapProductForm()` menunggu GET
`/api/products/{id}/external-mappings/jubelio` hanya dengan pemeriksaan sesi (`version!==epoch`).
Selama `epoch` tidak berubah, respons yang tiba sesudah dialog asal ditutup tetap menjalankan
`formDialog()` — atau, pada jalur unmap dengan status bukan `mapped`, `productMappingDialog()` —
sehingga dialog yang sedang terbuka digantikan.

Modul `tests/browser_product_external_mappings.cjs` menahan satu GET mapping sesudah responsnya tiba,
lalu menutup dialog dan membuka `Tambah SKU`. Hasil pada baseline dijalankan sebelum perbaikan:

| Langkah | Baseline `07680ee` | Sesudah perbaikan |
| --- | --- | --- |
| Klik `Ubah mapping` dengan respons tertunda, tutup dialog, buka `Tambah SKU`, ketik `UNRELATED-DRAFT`, lepas respons | heading `Tambah SKU` hilang dan draft terhapus — dialog berganti menjadi form `Ubah mapping Jubelio` | `Tambah SKU` tetap terbuka, `UNRELATED-DRAFT` utuh |
| Klik `Lepaskan mapping` dengan respons tertunda, tutup dialog, buka `Tambah SKU`, ketik `UNRELATED-UNMAP-DRAFT`, lepas respons | draft terhapus dan dialog mapping/form unmap terbuka kembali di atas draft | tidak ada dialog yang dibuka ulang, draft utuh |
| Respons tertunda dilepas sesudah logout | tidak ada dialog yang terbuka kembali (sudah tertahan pemeriksaan `epoch` yang lama) | sama, dan sekarang juga tertahan versi dialog |

Baseline dijalankan dua kali: sekali dengan seluruh assert baru (gagal pada jalur edit), sekali lagi
dengan assert jalur edit dinonaktifkan sementara supaya jalur unmap ikut tercapai dan gagal pada
assert yang sama. Salinan kerja sementara itu sudah dikembalikan sebelum commit; hanya assert
produksi yang menjadi bagian perubahan ini.

## Perbaikan

- `productMappingForm()` menyimpan `dialogVersion` sebelum `await`, lalu keluar tanpa menggambar apa
  pun bila sesi berganti, versi dialog berubah, atau dialog sudah tertutup:
  `if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;`. Pola ini sama dengan
  `productMappingDialog()` di dekatnya, sehingga form hanya menggantikan dialog asal yang masih
  aktif.
- `unmapProductForm()` memakai guard yang sama. Jalur "status bukan `mapped`" hanya memanggil
  `productMappingDialog()` bila dialog asal masih dialog yang sama dan masih terbuka; sesudah dialog
  ditutup atau sesi berganti, jalur ini tidak membuka dialog apa pun. Sesi yang sudah logout tidak
  lagi dapat memunculkan dialog mapping di layar login.

Tidak ada perubahan schema (`user_version` tetap 55), tidak ada endpoint atau field API baru, dan
tidak ada perubahan perilaku selain respons terlambat yang kini dibuang diam-diam.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | `Ran 529 tests` — **OK** |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs`, `python tests/test_client.mjs` | bersih dan **PASS** |
| `python tests/run_browser.py --node node --playwright-module <playwright> --channel chromium` | 78 modul acceptance **PASS**, tanpa JS error |
| Reproduksi baseline vs tree perbaikan | tabel di atas: jalur edit dan unmap gagal di baseline, lulus sesudah perbaikan |

Skenario baru di `tests/browser_product_external_mappings.cjs`:

- Jalur edit: `Ubah mapping` ditahan, dialog ditutup, `Tambah SKU` dibuka dan diisi `UNRELATED-DRAFT`;
  respons lama tidak mengganti dialog dan draft tetap utuh.
- Jalur unmap: `Lepaskan mapping` ditahan, dialog ditutup, draft `Tambah SKU` diketik; respons lama
  tidak membuka kembali form unmap maupun dialog mapping.
- Logout: respons tertunda dilepas sesudah logout; tidak ada dialog dengan atribut `open` di layar
  login dan form mapping tidak dirender.
