# Bukti pengujian: stabilisasi regresi browser penutupan dialog

Dua modul regresi — `tests/browser_motion_dialogs.cjs` dan `tests/browser_dialog_closing.cjs` —
bergantung pada waktu jam dinding di sekitar siklus penutupan dialog beranimasi. Keduanya bisa gagal
sementara semantik produksi tetap benar. Perubahan ini hanya menyentuh pengujian: tidak ada
perubahan sumber produksi, versi aplikasi, OpenAPI, maupun schema.

## Baseline

| | |
|---|---|
| Commit baseline | `bb29dac1099e05f96d40ea958feef1a3cfd430a1` (`main`) |
| Aplikasi / schema | 0.101.0 / `PRAGMA user_version` 55 (keduanya tidak berubah) |
| Branch pekerjaan | `test/stabilize-dialog-motion-regressions` |
| Working tree awal | bersih |

Branch dibuat langsung dari `origin/main`. PR #92 (A4, `42cf6592`) tidak dijadikan dasar dan tidak
disentuh; nilai glass A4 tidak ikut berubah.

## Lingkungan

Python 3.12.13 pada venv repositori (`.venv`), Node.js 22.23.2, Playwright 1.63.0 dengan Chromium
bawaan (Chrome for Testing 153.0.8010.12, build `chromium v1243`), Linux 8 vCPU. Seluruh pengujian
memakai database sementara sekali pakai (`tempfile.TemporaryDirectory` pada runner browser); tidak
ada database bisnis atau produksi yang disentuh.

## Siklus produksi yang diuji (tidak berubah)

`closeDialogAnimated()` (`beeloft/static/app.mjs:1367`) menerima pembatalan, langsung memasang
`inert`, memasang `motion-exit` lalu `is-closing`, dan menutup lewat `transitionend` dengan timer
jaring pengaman `motionMs('--motion-fast') + 60` = **180ms**. Transisi keluarnya sendiri
`--motion-fast` = **120ms** (`beeloft/static/style.css:663-667`). Marginnya 60ms.

## Mekanisme balapan yang diperbaiki

**1. `browser_motion_dialogs.cjs` mewajibkan `transitionend` mengalahkan timer 180ms.**
Bukti satu-satunya bahwa keluar benar-benar terjadi adalah event `transitionend`. Di bawah tekanan
runner, jaring pengaman menang lebih dulu, transisi berakhir sebagai `transitioncancel`, dan modul
gagal walau produksi benar.

Tambahan yang ditemukan saat investigasi: helper lama

```js
const sawTransition = (entries, type) => entries.some(e => e.type === type && e.name === 'opacity');
```

tidak memisahkan transisi milik dialog dari transisi `::backdrop`. Backdrop juga men-transisi
`opacity` dan melaporkannya pada elemen dialog dengan `pseudoElement` terisi, sehingga
`transitionend` milik backdrop ikut dihitung sebagai bukti keluarnya dialog.

**2. `browser_dialog_closing.cjs` mengasumsikan input kedua tiba selama penutupan.**
Polanya `Escape` → kembali ke Node → kirim tombol kedua. Bila perjalanan CDP melewati 180ms, keluar
sudah selesai secara sah dan fokus sudah kembali ke pemicu, sehingga `Enter`/`Space` mengaktifkan
pemicu itu sebagai interaksi **baru** — dilaporkan keliru sebagai pelanggaran guard.

**3. Dua assert yang mengukur hal yang salah.** Keduanya inilah penyebab kegagalan baseline yang
paling sering, dan keduanya bergantung pada blur asinkron Chromium:

- `afterInput.focusInside === false` — Chromium **tidak** langsung melepas fokus dari elemen yang
  sudah terfokus ketika subtree-nya menjadi `inert`; pelepasan itu terjadi pada pembaruan berikutnya.
  Selama jeda itu `focusInside` sah bernilai `true`.
- `focus() cannot re-enter any closing control` — probe lamanya
  `control.focus(); return document.activeElement === control;` tidak membedakan "fokus berhasil
  masuk" dari "kontrol ini memang sudah terfokus". Untuk `#save-form` yang sudah terfokus, hasilnya
  `true` tanpa ada re-entry sama sekali.

Keduanya bukan cacat produk. Konsekuensinya justru dijaga: guard `submit` fase capture
(`beeloft/static/app.mjs:1406-1409`) menelan submit selama `inert`, sehingga tidak ada tulisan yang
lolos. Probe yang benar memarkir fokus di luar dialog lebih dahulu, lalu menguji re-entry.

## Strategi observasi baru

Prinsipnya didokumentasikan sebagai komentar di kepala kedua modul karena berlaku juga untuk
overlay, sheet, dan popover beranimasi berikutnya:

> Assert **keadaan pada saat event tiba**, bukan keadaan saat Node mengira event itu tiba.

Perwujudannya:

- **Snapshot di dalam halaman.** `MutationObserver` mengambil `getAnimations()`, transisi keluar
  terhitung, `inert`, dan `open` pada saat `is-closing` dipasang. Callback observer adalah microtask,
  jadi selalu berjalan sebelum timer 180ms mana pun — tidak ada margin yang bisa hilang, dan bukti
  ini berlaku juga untuk `Escape` yang datang sebagai tombol tepercaya.
- **Bukti keluar yang sebenarnya.** Yang diwajibkan adalah adanya `CSSTransition` untuk `opacity`
  yang berjalan dengan durasi token, pada dialog yang masih `open`, sudah `inert`, dan
  `pointer-events:none`. Hasil akhirnya diklasifikasikan, bukan diwajibkan: `transitionend` **atau**
  `transitioncancel` dari jaring pengaman — tepat satu di antaranya selalu terjadi, jadi
  "salah satu dari dua" bersifat deterministik. Penutupan tanpa transisi sama sekali tetap gagal.
- **Event transisi dipisahkan per `pseudoElement`**, sehingga transisi backdrop tidak lagi bisa
  menyamar sebagai transisi dialog.
- **Klasifikasi per pengiriman.** Setiap probe tepercaya direkam pada fase capture bersama `open`,
  `inert`, daftar kelas, dan elemen aktif. Probe yang tiba saat `open && inert && is-closing` wajib
  membuktikan kontrak penuh; probe yang tiba sesudah penutupan sah diperlakukan sebagai interaksi
  baru, diwajibkan tiba dengan fokus sudah kembali ke pemicu, dan dialog yang dibukanya dibersihkan.
- **Cakupan jendela penutupan tidak pernah opsional.** Dua mekanisme menjaminnya tanpa bergantung
  pada waktu:
  1. `localClosingProbe()` memasang pembatalan lalu menyerang dialog yang sedang menutup — re-entry
     `focus()`, klik terprogram pada kontrol submit, dan `requestSubmit()` — di dalam **satu task
     halaman**. Timer tidak bisa menyela sebuah task, jadi dialog terbukti masih `open`, `inert`,
     dan `is-closing` untuk setiap percobaan.
  2. `trustedKeyDuringClose()` menekan tombol **asli** dan memasang pembatalan dari dalam
     `keydown` capture tombol itu sendiri, sehingga aksi bawaan tombol — mekanisme POST pada PR #87 —
     tuntas saat dialog sudah `inert`, tanpa margin. `KeyboardEvent` sintetis tidak dipakai sebagai
     pengganti karena tidak memicu aksi bawaan itu sama sekali.
- **Jumlah `close` native dihitung monoton**, supaya keluar yang belum selesai tidak tertukar dengan
  dialog yang sudah tertutup lalu dibuka lagi.

### Dua kopling sisa yang ditemukan pada review

Review otomatis (CodeRabbit pada PR #93) menemukan dua tempat yang masih memakai pola lama, dan
keduanya diperbaiki dengan prinsip yang sama:

- **Aktivasi Space terjadi pada `keyup`, bukan `keydown`.** `trustedKeyDuringClose()` semula selalu
  memasang pembatalan dari `keydown`. Chromium mengaktifkan tombol dari Enter pada `keydown` tetapi
  dari Space pada `keyup`, sehingga untuk Space aktivasinya berada di task **berikutnya** dan kembali
  bergantung pada task itu tiba di dalam jendela 180ms. Pembatalan sekarang dipasang dari fase
  capture event yang benar-benar mengaktifkan. Capture berjalan sebelum handler bawaan tombol, jadi
  aktivasi yang menyusul pasti mengenai dialog yang sudah `inert`. Diverifikasi dengan penahanan
  tombol 220ms — jauh melewati jendela 180ms — dan `click` serta `submit` tetap tercatat pada
  `open + inert + is-closing`.
- **Pemeriksaan entry pada kasus overlap terpisah dari penutupannya.** Menunggu `dialog-enter` lewat
  `waitForFunction` lalu memanggil `page.evaluate` terpisah adalah balapan tersendiri: entry hanya
  berumur `--motion-dialog` (260ms), jadi perjalanan yang lambat di antara keduanya tiba setelah
  entry selesai dan menggagalkan produk yang benar. Pembukaan, penungguan, dan penutupan sekarang
  berada dalam satu panggilan halaman; sesudah penungguan tidak ada `await` lagi, sehingga pembacaan
  "entry berjalan" dan dispatch penutupan berbagi satu task.

Review juga menemukan satu kekeliruan urutan: pemeriksaan entry tema gelap berjalan **sesudah** tema
dikembalikan, sehingga assert-nya menguji tema semula. Pengembalian tema kini dilakukan setelah
pemeriksaan itu, dan tema gelap diassert secara eksplisit saat pemeriksaan berjalan.

Assert yang tetap menjadi tulang punggung: tidak ada `submit` yang lolos dari guard, tidak ada POST,
fokus tidak bisa masuk kembali ke subtree yang menutup, `inert` dipasang seketika dan dibersihkan
oleh `close` native, kelas menutup tidak tersisa, fokus kembali ke pemicu, penolakan penutupan saat
sibuk/belum selesai tetap interaktif, dan penyimpanan yang disengaja tetap berhasil sekali.

## Bukti mutasi

Setiap mutasi diterapkan satu per satu pada sumber produksi, modul terkait dijalankan, lalu tree
dipulihkan dengan `git checkout`. Tidak ada berkas mutasi yang ikut di-commit.

| Mutasi | Modul | Hasil |
| --- | --- | --- |
| `inert` seketika dihapus pada pembatalan diterima | `dialog_closing` | **gagal** — `an accepted dismissal inerts the dialog immediately` |
| idem | `motion_dialogs` | **gagal** — `close button: an accepted dismissal inerts the dialog immediately` |
| guard `submit` terpusat dihapus | `dialog_closing` | **gagal** — `neither a scripted click nor requestSubmit() gets a submit past the guard` |
| transisi keluar dihapus (`transition:none`) | `motion_dialogs` | **gagal** — `close button: the exit transition covers opacity :: none` |
| penutupan beranimasi dilewati, `close()` langsung | `motion_dialogs` | **gagal** — `the close button marks the dialog as closing before it closes` |
| kelas menutup dibiarkan sesudah `close` | `motion_dialogs` | **gagal** — dialog berikutnya tidak pernah dapat diklik (`opacity:0`), suite berhenti |
| pemulihan fokus dirusak (diarahkan ke `#refresh`) | `motion_dialogs` | **gagal** — `focus returns to the trigger that opened the dialog` |
| idem | `dialog_closing` | **gagal** — `native close restores the original trigger` |
| **cacat PR #87 dimunculkan ulang** (`inert` seketika dihapus) | `dialog_closing` | **gagal** — termasuk ketika seluruh probe tepercaya dipaksa tiba sesudah penutupan |

Menghapus `target.focus()` saja tidak terdeteksi, dan itu benar: penutupan `<dialog>` native sudah
memulihkan fokus ke elemen sebelum `showModal()`. Mutasi yang bermakna adalah mengarahkan fokus ke
tempat lain, dan itu tertangkap kedua modul.

Dua pemeriksaan toleransi memastikan jaring pengaman **tidak** lagi dianggap kegagalan. Transisi
keluar diperpanjang jauh melewati timer 180ms sementara token `--motion-fast` dibiarkan:

| Pemeriksaan | Modul lama (`main`) | Modul setelah stabilisasi |
| --- | --- | --- |
| Hanya transisi dialog 900ms (backdrop tetap 120ms) | lulus — `transitionend` backdrop ikut terhitung | lulus, kelima jalur tercatat `safety-fallback(transitioncancel)` |
| Transisi dialog **dan** backdrop 900ms | **gagal** — `the exit transition runs to completion` | **lulus**, kelima jalur `safety-fallback(transitioncancel)` |

Baris terakhir adalah inti perubahan ini: modul lama menuntut `transitionend`, modul baru tetap
membuktikan transisi `opacity` yang nyata memang dibuat dan menerima penutupan oleh jaring pengaman.

## Bukti pengulangan

Tekanan dibuat dengan proses pembakar CPU latar (`while :; do :; done`) selama runner berjalan, 8
vCPU. Selama diagnosis, throttling CPU lewat CDP (`Emulation.setCPUThrottlingRate`) juga dipakai
untuk memeriksa keadaan pada saat event tiba.

| Kondisi | Modul | Run | Gagal |
| --- | --- | --- | --- |
| **Baseline `bb29dac`**, 8 pembakar | keduanya | 6 | **5** |
| Setelah stabilisasi, tanpa beban | keduanya | 20 | 0 |
| Setelah stabilisasi, 8 pembakar | keduanya | 20 | 0 |
| Setelah stabilisasi, 16 pembakar (2× vCPU) | keduanya | 10 | 0 |

Seluruh rangkaian di atas diulang sesudah perbaikan temuan review, dengan hasil sama: 20 tanpa beban,
20 dengan 8 pembakar, dan 10 dengan 16 pembakar — 50/50 bersih.

Kegagalan baseline seluruhnya jatuh pada dua assert di bagian "Mekanisme balapan" nomor 3
(`leaves no focus in the inert subtree` dan `focus() cannot re-enter any closing control`), dan
modul yang gagal berpindah-pindah antar run — tanda balapan, bukan cacat tetap.

Tujuannya bukan menjamin waktu, melainkan memastikan pengujian tidak lagi bergantung pada margin
60ms. Karena itu cabang "tiba sesudah penutupan" juga diverifikasi secara sengaja: dengan penundaan
yang dipaksa sebelum setiap probe tepercaya, ketujuh probe tercatat `after-close`, dialog baru yang
sah dibersihkan, dan modul tetap lulus — sementara cacat PR #87 yang dimunculkan ulang pada kondisi
yang sama **tetap gagal**, karena cakupan jendela penutupan dijamin oleh dua mekanisme yang tidak
bisa kalah balapan.

Waktu produksi tidak berubah: `--motion-fast` 120ms, `--motion-dialog` 260ms, dan timer
`+ 60` tetap apa adanya.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests -v` | `Ran 608 tests` — **OK** |
| `python -m pip check` | `No broken requirements found.` |
| `python -m compileall -q beeloft` | bersih |
| `node --check beeloft/static/app.mjs` | bersih |
| `node --check beeloft/static/client.mjs` | bersih |
| `node tests/test_client.mjs` | **PASS** |
| `python tests/run_browser.py --channel chromium` | dijalankan 2×, 83 modul melaporkan **PASS**, tanpa JS error |
| `PRAGMA user_version` pada database demo baru | 55 |
| Versi aplikasi | 0.101.0 (tidak berubah) |
| `git diff --check` | bersih |
| Berkas berubah | hanya `tests/browser_motion_dialogs.cjs`, `tests/browser_dialog_closing.cjs`, dan dokumen ini |

Tidak ada modul browser baru, urutan pemanggilan di `tests/browser_smoke.cjs` tidak berubah, tidak
ada bypass khusus CI, dan tidak ada retry acak.
