# Bukti pengujian: rasio margin null pada investigasi

Temuan: [issue #28](https://github.com/wenn-id/beeloftone/issues/28) — investigasi margin menjawab
HTTP 500 ketika sebuah order memiliki pendapatan bersih nol karena `_margin()` menggabungkan
`contribution_margin_rate` yang bernilai `None` dengan string.

## Baseline

| | |
|---|---|
| Commit baseline | `33ba7ee7bd22fd3e2be40aeed5f63f2d3aa6ae81` (`main`) |
| Aplikasi / schema | 0.89.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/margin-null-ratio` |
| Working tree awal | bersih |

Temuan direproduksi ulang terhadap commit tersebut sebelum satu baris pun diubah. Tidak ada checkout
paksa ke commit lama dan tidak ada perubahan lokal yang dibuang.

## Lingkungan

Python 3.14.4 pada venv repositori (`.venv`), Node.js 24.16.0, Playwright 1.63.0 dengan Chromium pada
`~/.cache/ms-playwright`, Linux. Seluruh pengujian memakai database sementara sekali pakai
(`tempfile.TemporaryDirectory` pada test dan runner browser); tidak ada database bisnis atau
produksi yang disentuh.

## Reproduksi

`Store.contribution_margin` (`beeloft/store.py:4068`) hanya menghitung rasio ketika
`margin is not None and net_revenue>0`. Settlement yang sah dengan `gross_revenue` Rp1000 dan
`seller_discount` Rp1000 menghasilkan laporan berstatus `complete` dengan `net_revenue` `0.00`,
`contribution_margin` `-228.11`, dan `contribution_margin_rate` `None`. `_margin()`
(`beeloft/brain.py:172`) kemudian menyusun `'Rasio margin '+row['contribution_margin_rate']+'%.'`
tanpa memeriksa nilai itu.

Test regresi `AiInvestigationTest.test_zero_net_revenue_margin_answers_without_a_ratio` dijalankan
terhadap baseline sebelum perbaikan:

| Langkah | Baseline `33ba7ee` | Sesudah perbaikan |
| --- | --- | --- |
| `POST /api/ai/investigate` — `Bagaimana margin kontribusi bisnis saat ini?` | `500` — `TypeError: can only concatenate str (not "NoneType") to str` pada `brain.py:172` | `200` |
| `POST /api/ai/investigate` — `Tolong investigasi margin <referensi order>` | `500` — traceback yang sama | `200` |
| `detail` finding order tersebut | tidak pernah dirender karena respons gagal | `Rasio margin belum tersedia (pendapatan bersih Rp0.00).` |
| Nominal margin order tersebut | terhitung di server tetapi tidak sampai ke respons | `margin Rp-228.11` pada title dan `Total margin terhitung` |

## Perbaikan

- `_margin()` (`beeloft/brain.py:169-177`) memeriksa `contribution_margin_rate` sebelum menyusun
  detail. Rasio yang tersedia tetap dirender seperti sebelumnya (`Rasio margin 75.99%.`); rasio
  `None` diganti keterangan `Rasio margin belum tersedia (pendapatan bersih Rp0.00).`, sehingga nilai
  yang tidak dapat dihitung tidak pernah tampil sebagai rasio nol.
- Nominal margin tetap ditampilkan apa adanya pada title finding. Agregat `Margin lengkap`,
  `Margin belum lengkap`, dan `Total margin terhitung` tidak berubah karena order berstatus
  `complete` tetap ikut dihitung.
- Kontrak `Store.contribution_margin` tidak diubah: `None` tetap berarti rasio tidak dapat dihitung.
  Tidak ada perubahan schema (`user_version` tetap 55), tidak ada endpoint atau field API baru, dan
  tidak ada perubahan perilaku selain detail finding yang kini selalu dapat dirender.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | `Ran 530 tests` — **OK**. Sebelumnya 529 pada commit audit; 1 test baru. |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs`, `node --check beeloft/static/client.mjs`, `node tests/test_client.mjs` | bersih dan **PASS** |
| `python tests/run_browser.py --node node --playwright-module <playwright> --channel chromium` | 78 modul acceptance **PASS**, tanpa JS error |
| Reproduksi baseline vs tree perbaikan | tabel di atas: pertanyaan umum dan terfokus gagal `500` di baseline, lulus `200` sesudah perbaikan |

Test baru di `tests/test_ai_investigation.py`:

- `test_zero_net_revenue_margin_answers_without_a_ratio` — order dengan pengiriman 10 pcs, produksi
  selesai, dan settlement tanpa pendapatan bersih menghasilkan `net_revenue` `0.00`,
  `contribution_margin` `-228.11`, dan `contribution_margin_rate` `None`. Pertanyaan margin umum dan
  pertanyaan terfokus yang menyebut referensi order dijawab `200` dengan detail
  `Rasio margin belum tersedia (pendapatan bersih Rp0.00).`, title `margin Rp-228.11`, facts
  `Margin lengkap` 1 / `Margin belum lengkap` 0 / `Total margin terhitung` `-228.11`, serta evidence
  `contribution_margins` yang tetap memuat rasio `None`.
