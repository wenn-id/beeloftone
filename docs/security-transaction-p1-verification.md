# Bukti pengujian: dependensi Starlette dan pengikatan idempotency key

Rencana: [security transaction P1 plan](security-transaction-p1-plan.md).

## Lingkungan

Python 3.12.13, Node.js 22.23.2, Playwright 1.63.0 dengan Chromium, Linux. Perintah dijalankan dari
akar repositori.

## Ringkasan hasil

| Pemeriksaan | Hasil |
|---|---|
| `python -m unittest discover -s tests` | 372 test, OK. Sebelumnya 354; 18 test baru. |
| `python -m pip check` | No broken requirements found |
| `python -m compileall -q beeloft` | bersih |
| `node --check` pada `app.mjs` dan `client.mjs` | bersih |
| `node tests/test_client.mjs` | PASS |
| `python tests/run_browser.py --channel chromium` | 63 modul acceptance PASS. Sebelumnya 61; 2 modul baru. |

## 1. Dependensi Starlette

`starlette` dinaikkan dari `0.52.1` ke `1.6.0` pada `requirements.txt`, dan batas deklaratif pada
`pyproject.toml` menjadi `starlette>=1.3.1,<2` dengan `fastapi>=0.134,<1`.

Resolusi ulang seluruh dependensi langsung pada venv Python 3.12 yang bersih menghasilkan set yang
identik dengan lock sebelumnya kecuali Starlette. `uvicorn`, `PyJWT`, `qrcode`, `httpx`, dan seluruh
paket transitif tidak berubah versinya.

Advisory yang tertutup oleh kenaikan ini terdaftar di dokumen rencana. Yang perlu ditegaskan: rilis
1.1.0 sudah menutup GHSA-wqp7-x3pw-xc5r yang disebut dalam laporan, tetapi masih terkena
CVE-2026-54282 dan CVE-2026-54283, sehingga 1.1.0 tidak dipakai sebagai target.

### Regresi UNC path

`tests/test_static_security.py` menambahkan empat test.

- `test_installed_starlette_closes_every_known_advisory` menegaskan batas versi `>= 1.3.1`.
- `test_unc_lookup_is_refused_before_any_filesystem_resolution` memanggil `StaticFiles.lookup_path()`
  langsung untuk enam path UNC-style, memastikan hasilnya `("", None)` dan **tidak ada satu pun**
  panggilan `os.path.realpath`, `os.path.abspath`, atau `os.stat` yang terjadi.
- `test_unc_requests_return_404_without_touching_the_unc_destination` mengirim tujuh varian request
  ke `/static/...`, memastikan semuanya 404, tidak ada resolusi filesystem terhadap path berbentuk
  UNC, dan tidak ada I/O jaringan.
- `test_legitimate_assets_still_load` memastikan aset sah tetap 200 dan path traversal biasa tetap 404.

Guard jaringan memasang wrapper pada `socket.getaddrinfo`, `socket.create_connection`, dan
`socket.socket.connect` yang gagal keras bila menyentuh host uji atau port 445. Host uji memakai TLD
`.invalid` (RFC 2606). Tidak ada request SMB nyata yang pernah dibuat.

Diskriminasi terhadap versi rentan diverifikasi dengan menurunkan Starlette ke 0.52.1 lalu
menjalankan test yang sama. Hasilnya gagal dengan bukti eksplisit bahwa `realpath` menerima path
UNC, yaitu titik tepat terjadinya koneksi SMB pada Windows:

```
FAIL: test_unc_lookup_is_refused_before_any_filesystem_resolution (path='\\attacker.invalid\share\payload')
AssertionError: \\attacker.invalid\share\payload sempat di-resolve ke filesystem:
  [('realpath', '.../beeloft/static/\\\\attacker.invalid\\share\\payload'),
   ('abspath',  '.../beeloft/static/\\\\attacker.invalid\\share\\payload'),
   ('stat',     '.../beeloft/static/\\\\attacker.invalid\\share\\payload')]

FAIL: test_unc_lookup_is_refused_before_any_filesystem_resolution (path='//attacker.invalid/share/payload')
AssertionError: [('realpath', '//attacker.invalid/share/payload'), ...] != []
```

Pada 1.6.0 keenam path ditolak tanpa satu pun panggilan tersebut.

## 2. Retry transaksi tidak pasti lintas akun

### Reproduksi

Kasus yang dilaporkan direproduksi lebih dahulu, lalu dibuktikan gagal pada kode sebelum perbaikan.
Dengan `beeloft/store.py` dikembalikan ke keadaan semula dan migrasi 54 dilepas, enam test baru gagal:

```
FAIL: test_session_switched_in_another_tab_cannot_settle_the_pending_transaction
AssertionError: 201 != 403 : {"id":"4c305671-...","from_stage":"planned","to_stage":"cutting",
  "quantity":10,"actor_id":"b35e78a8-...", ...}
FAIL: test_other_actor_replaying_a_key_cannot_create_a_second_mutation      AssertionError: 201 != 403
FAIL: test_disabled_or_unauthorised_originating_actor_...                  AssertionError: 201 != 403
FAIL: test_retry_after_transient_failure_succeeds_with_the_same_key        AssertionError: 201 != 403
FAIL: test_schema_makes_the_request_key_globally_unique                    AssertionError: IntegrityError not raised
FAIL: test_migration_keeps_the_originating_receipt_and_archives_the_duplicate  AssertionError: 53 != 54
```

`actor_id` pada respons 201 itu adalah akun kedua, bukan akun pencatat asli. Jadi perilaku sebelum
perbaikan memang **dapat** menghasilkan mutasi bisnis kedua, dan mutasi itu diatribusikan kepada akun
yang hanya kebetulan memegang session browser bersama saat retry dikirim.

### Penegakan invarian

`Store._write()` mencari receipt dengan `WHERE key=?` tanpa filter akun, lalu menolak 403 bila
`actor_id` receipt berbeda dari akun sekarang. Urutan pemeriksaan tetap: akun nonaktif 401, pemilikan
key 403, role 403, fingerprint 409, replay, baru eksekusi. Migrasi 53 → 54 menjadikan `key` sebagai
primary key tunggal, sehingga insert kedua dengan key sama melanggar constraint dan dipetakan ke 409
walau pemeriksaan Python suatu saat hilang.

### Cakupan test

`tests/test_idempotency_actor.py`, sembilan test:

| Test | Invarian |
|---|---|
| `test_same_actor_same_key_same_payload_replays_the_first_result` | I3, termasuk tidak adanya event audit baru |
| `test_same_actor_same_key_different_payload_is_rejected_with_conflict` | I4 |
| `test_other_actor_replaying_a_key_cannot_create_a_second_mutation` | I5, I2, I8 |
| `test_session_switched_in_another_tab_cannot_settle_the_pending_transaction` | kasus yang dilaporkan |
| `test_disabled_or_unauthorised_originating_actor_cannot_produce_a_second_mutation` | I7, I5 |
| `test_role_downgrade_still_blocks_replay_for_the_original_actor` | urutan pemeriksaan role tidak berubah |
| `test_retry_after_transient_failure_succeeds_with_the_same_key` | I6 |
| `test_schema_makes_the_request_key_globally_unique` | I1 di tingkat schema |
| `test_migration_keeps_the_originating_receipt_and_archives_the_duplicate` | migrasi dan kompatibilitas |

Test akun kedua sengaja memakai akun admin, yaitu role yang memang diizinkan mencatat perpindahan,
supaya penolakan benar-benar berasal dari pemilikan key dan bukan dari role.

Test session menempuh alur cookie sungguhan: login session akun A, write dengan key K, logout dan
login akun B pada cookie jar yang sama, retry dengan key K ditolak 403, lalu login kembali sebagai
akun A dan retry menghasilkan replay. Sepanjang itu jumlah perpindahan tetap satu.

### Cakupan browser

`tests/browser_cross_account_retry.cjs` dijalankan dari `browser_smoke.cjs`. Modul ini membuktikan
sisi klien pada browser sungguhan: write ditandai belum pasti melalui fetch-then-abort, session
bersama ditukar ke akun lain, tombol Coba ulang penyimpanan ditekan, lalu

- request POST ke endpoint mutasi **tidak pernah bertambah** (`posts` tetap 1), jadi retry lintas akun
  dihentikan sebelum dikirim,
- pesan error memuat "akun lain" dan tombol Masuk ulang muncul,
- draft pending tetap tersimpan dengan `transaction.key` yang sama dan membawa `actor_id` akun asli,
- setelah masuk kembali sebagai akun asli, retry berhasil dan jumlah perpindahan tetap satu, saldo
  cutting 7 pcs, serta draft dibersihkan.

## 3. Submit pertama di bawah session yang sudah berganti

### Reproduksi

Celah ini direproduksi di browser sungguhan sebelum diperbaiki: akun A membuka form perpindahan,
session bersama ditukar ke akun B, lalu submit **pertama** ditekan. Tidak ada penolakan sama sekali,
dan mutasi beserta event auditnya diatribusikan ke akun B:

```
REPRO first submit -> movements=[{"actor":"7dde74a8-...","qty":6}]
                      formOpenedBy=52fda9f3-...
                      sessionNow=7dde74a8-...
                      auditForKey=[{"actor":"7dde74a8-...","op":"move"}]
```

`formOpenedBy` adalah akun A yang membuka form, sedangkan `movements[0].actor` dan `auditForKey[0]`
menunjuk akun B. Jadi submit pertama memang menghasilkan mutasi bisnis nyata dengan atribusi yang
salah secara senyap. Kepemilikan idempotency key tidak dapat menolong karena key-nya masih baru.

### Perbaikan

`beeloft/api.py` memverifikasi header `X-Beeloft-Actor` pada dependency `actor()`, yaitu satu titik
yang dilewati seluruh endpoint, dan menolak 403 sebelum handler mana pun berjalan. `client.mjs`
mengirim header itu pada setiap request yang membawa idempotency key, dan `app.mjs` mengisi
`api.actorId` di `enterWorkspace` serta mengosongkannya di `clearWorkspace`.

### Cakupan test

`tests/test_idempotency_actor.py::StaleSessionActorBindingTest`, lima test:

| Test | Isi |
|---|---|
| `test_matching_actor_binding_is_accepted` | binding yang cocok tidak mengubah apa pun |
| `test_absent_binding_keeps_api_key_clients_unchanged` | tanpa header, perilaku klien API key identik |
| `test_mismatched_binding_creates_no_mutation_and_no_audit_event` | 403, nol mutasi, nol event audit, nol receipt, lalu key yang sama masih dapat dipakai akun yang sah |
| `test_first_submit_is_refused_after_another_tab_replaced_the_session` | kasus yang dilaporkan, memakai cookie session sungguhan, termasuk atribusi benar setelah masuk ulang |
| `test_binding_cannot_grant_access_it_only_refuses` | header bukan mekanisme autentikasi: viewer tetap 403, tanpa kredensial tetap 401 |

`tests/test_client.mjs` menambah assertion bahwa header dikirim untuk pencatatan ber-key, dan **tidak**
dikirim untuk `post()` tanpa key maupun untuk `get()`. Ini yang menjaga jalur login dan logout tetap
dapat berjalan saat session sedang dipegang akun lain.

`tests/browser_stale_session_first_submit.cjs` menguji kedua alur di browser sungguhan:

- **Perpindahan produksi.** Form dibuka akun A, session ditukar ke akun B, submit pertama ditolak
  dengan pesan memuat "akun lain", tombol Masuk ulang muncul, nol mutasi, dan nol event audit untuk
  Idempotency-Key yang terkirim. Setelah masuk ulang sebagai akun A, pencatatan tersimpan tepat satu
  kali dengan `actor_id` akun A dan saldo cutting 6 pcs.
- **Investigasi AI.** Pola yang sama pada `POST /api/ai/investigations`: submit pertama ditolak, nol
  investigasi tersimpan, nol event audit, lalu setelah masuk ulang tepat satu investigasi tersimpan.

### Kompatibilitas namespace key

Sebelum mengubah apa pun, `Store._write()` diinstrumentasi untuk mencatat setiap kemunculan
idempotency key yang sudah dipakai akun lain, lalu seluruh 354 test Python dan 61 modul acceptance
browser dijalankan. Hasilnya nol kejadian pada kedua suite. Tidak ada jalur yang ada sekarang yang
bergantung pada namespace key per akun.

## Perubahan yang menyentuh test lama

57 assertion `PRAGMA user_version` pada 56 file test dinaikkan dari 53 ke 54, mengikuti pola setiap
kenaikan schema sebelumnya. Tidak ada assertion perilaku yang dilemahkan atau dihapus.

## Batas

Isu Final QC/rework tidak disentuh. Tidak ada fitur produk baru, tidak ada connector vendor, tidak
ada perubahan aturan bisnis modul. Tabel `requests` masih tumbuh tanpa TTL, dan notifikasi lintas tab
belum ada.
