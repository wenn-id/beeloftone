# Bukti pengujian: first paint tema pada modul motion microinteractions

Temuan: flake suite browser — `tests/browser_motion_microinteractions.cjs:17` gagal dengan
`the initial paint never arms the theme transition`. Terjadi pada `main` di run CI PR #67
(`c884f86`) dan pada run pertama PR #68; rerun keduanya hijau tanpa perubahan kode. Kegagalan tidak
berkaitan dengan perubahan yang sedang diuji, jadi sumbernya ada di urutan waktu antar modul.

## Baseline

| | |
|---|---|
| Commit baseline | `c884f8667659086a84a8357a143839d1f9c87509` (`main`) |
| Aplikasi / schema | 0.92.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/browser-motion-first-paint` |
| Working tree awal | bersih; tidak ada perubahan yang dibuang |

Run CI yang gagal: [PR #68 run 35560158025](https://github.com/wenn-id/beeloftone/actions/runs/35560158025)
(assertion yang sama), dan pada `main` run `35558274341` untuk commit `c884f86`.

## Penyebab

- `beeloft/static/app.mjs:89` melepas kelas `is-theming` setelah satu token ditambah 60ms:
  `motionMs('--motion-base') + 60`, dan `--motion-base` bernilai `180ms`
  (`beeloft/static/style.css:61`). Jendela kelas itu karena itu 240ms.
- `tests/browser_motion_data_states.cjs` mengakhiri modulnya tepat sesudah toggle tema pemulihan
  (`if (startTheme !== 'dark') await page.locator('#theme').click();`) tanpa menunggu kelasnya
  dilepas, jadi modul berikutnya mewarisi dokumen yang masih di tengah transisi.
- `tests/browser_motion_microinteractions.cjs` memeriksa kelas itu pada dokumen yang sama sesudah
  `await login(admin)`. Seluruh modul memakai satu halaman, jadi pemeriksaan yang dimaksudkan untuk
  mengukur perilaku startup aplikasi bergantung pada berapa lama `login()` berjalan: bila selesai di
  bawah 240ms, kelasnya masih terpasang dan assertion gagal.

Jarak di CI: modul data states mencatat PASS pada `04:27:55.296` dan assertion M5 gagal pada
`04:27:55.497` — 201ms, di dalam jendela 240ms.

## Reproduksi

Harness menjalankan alur nyata di browser terhadap server demo sekali pakai: login, klik `#theme`
(toggle terakhir modul sebelumnya), lalu memeriksa kelas pada dokumen warisan dan pada dokumen segar.
Empat kali dijalankan pada tree perbaikan:

| Pemeriksaan | Hasil |
| --- | --- |
| Kelas terpasang tepat sesudah toggle | `true` — 4/4 |
| Pemeriksaan pada dokumen warisan tanpa jeda sama sekali | `is-theming=true` → **FAIL** 4/4 |
| `login()` pada dokumen warisan | 246ms, 437ms, 420ms, 418ms (jendela kelas 240ms) |
| Pemeriksaan pada dokumen segar (`reload` lebih dahulu) | `is-theming=false`, `transitionDuration=0s` → **PASS** 4/4 |

Jadi pemeriksaan versi lama ditentukan oleh selisih puluhan milidetik penjadwalan suite: satu run
lokal berada di 246ms (di atas jendela) dan lolos, sementara CI berada di 201ms dan gagal.

## Perbaikan

Modul memuat ulang dokumen sebelum memeriksa first paint:

```js
await page.reload();
await login(admin);
```

Pola `page.reload(); await login(...)` sudah dipakai modul lain (`browser_cutting.cjs`,
`browser_bundles.cjs`, `browser_login_form.cjs`, dan lainnya). Dengan dokumen segar, pemeriksaan itu
mengukur jalur startup aplikasi — jalur yang memang ingin dijaga assertion — bukan sisa transisi
modul sebelumnya, sehingga hasilnya tidak lagi bergantung pada urutan waktu. Dua pemeriksaan
berikutnya (`is-theming` dan `transitionDuration === '0s'`) tidak berubah.

Tidak ada perubahan kode aplikasi: hanya test. Versi aplikasi, schema, endpoint, dan perilaku produk
tidak berubah.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `node --check tests/browser_motion_microinteractions.cjs` | bersih |
| Suite browser penuh, run 1 | 79 modul acceptance **PASS**, tanpa JS error |
| Suite browser penuh, run 2 | 79 modul acceptance **PASS**, tanpa JS error |
| Harness race | dokumen warisan gagal 4/4; dokumen segar lulus 4/4 |

Perintah: `python tests/run_browser.py --node node --playwright-module <playwright> --channel chromium`.
