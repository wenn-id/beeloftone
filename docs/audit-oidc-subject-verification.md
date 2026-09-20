# Bukti pengujian: identitas subject OIDC yang persis

Temuan: [issue #26](https://github.com/wenn-id/beeloftone/issues/26) — dua subject OIDC berbeda dapat
masuk sebagai akun yang sama karena `sub` dipangkas.

## Baseline

| | |
|---|---|
| Commit baseline | `f8921e763a8b317f3680229aedb9406ddba687c8` (`main`) |
| Aplikasi / schema | 0.87.0 / `PRAGMA user_version` 55 |
| Branch pekerjaan | `fix/oidc-subject-exact-match` |
| Working tree awal | bersih selain `uv.lock` yang tidak terlacak (tidak ikut di-commit) |

Temuan direproduksi ulang terhadap commit tersebut sebelum satu baris pun diubah. Tidak ada checkout
paksa ke commit lama dan tidak ada perubahan lokal yang dibuang.

## Lingkungan

Python 3.14.5 pada venv repositori (`.venv`), Node.js 24.16.0, Playwright dengan Chromium pada
`~/.cache/ms-playwright`, Linux. Seluruh pengujian memakai database sementara sekali pakai
(`tempfile.TemporaryDirectory` pada test dan runner browser); tidak ada database bisnis atau
produksi yang disentuh.

## Reproduksi

Pada baseline `beeloft/oidc.py:188` klaim `sub` dipangkas sesudah verifikasi tanda tangan, dan
`Store._oidc_identity_values` (`beeloft/store.py:410-411`) memangkasnya sekali lagi sebelum lookup:

```python
subject = str(claims['sub']).strip()                       # oidc.py
issuer=issuer.strip().rstrip('/');subject=subject.strip()  # store.py
```

Skrip reproduksi memakai transport OIDC palsu bertanda tangan RSA seperti suite `test_oidc_sso.py`:
`employee-123` ditautkan ke akun admin, lalu login diselesaikan dengan token sah yang memuat
`sub = " employee-123 "`.

| Langkah | Baseline `f8921e7` | Sesudah perbaikan |
| --- | --- | --- |
| Callback `/api/sso/callback` | `303` ke `/` | `401` |
| Cookie `beeloft_session` | dibuat | tidak dibuat |
| `GET /api/me` | `200` — `Pemilik / admin` | `401` |

## Perbaikan

- `OidcClient.exchange` memvalidasi `sub` sebagai string 1–500 karakter lalu memakainya apa adanya:
  `str(...)` dan `.strip()` dihapus, jadi subject dari token tidak pernah diubah. Subject dengan spasi
  awal/akhir dijawab `401` sebelum lookup identitas.
- `Store._oidc_identity_values` — satu-satunya jalur validasi untuk link, unlink, dan authenticate —
  tidak lagi memangkas subject. Subject yang memuat spasi awal/akhir atau bukan string ditolak `422`
  dengan pesan yang menyebut syaratnya. Nilai seperti itu memang tidak dapat disimpan persis oleh
  `CHECK(subject=trim(subject))` pada `oidc_identities`, dan pemangkasan itulah yang membuat dua
  subject berbeda bertabrakan; menolaknya membuat exchange, link, unlink, dan lookup memakai
  identitas yang sama persis.
- Validasi issuer dan `OidcConfig` tidak berubah: issuer tetap dinormalkan terhadap konfigurasi, dan
  discovery tetap mensyaratkan kecocokan issuer yang persis.

Tidak ada perubahan schema (`user_version` tetap 55), tidak ada endpoint atau field API baru, dan
tidak ada perubahan perilaku selain penolakan nilai subject yang tidak dapat disimpan apa adanya.

## Bukti pengujian

| Pemeriksaan | Hasil |
| --- | --- |
| `python -m unittest discover -s tests` | `Ran 529 tests` — **OK**. Sebelumnya 527 pada commit audit; 2 test baru. |
| `python -m compileall -q beeloft` | bersih |
| `python tests/run_browser.py --node node --playwright-module <playwright> --channel chromium` | 78 modul acceptance **PASS**, tanpa JS error |
| Skrip reproduksi terhadap baseline dan tree perbaikan | `303` + cookie session + `/api/me` admin → `401` tanpa session |

Test baru di `tests/test_oidc_sso.py`:

- `test_signed_token_with_distinct_whitespace_subject_does_not_open_the_linked_account` — ketika
  `employee-123` sudah ditautkan, token sah dengan `sub = " employee-123 "` dan `"employee-123 "`
  dijawab callback `401`, tidak membuat cookie session, dan `/api/me` `401`; subject yang persis tetap
  masuk lewat `303` dan mengembalikan akun admin.
- `test_identity_values_are_stored_and_compared_exactly` — link, unlink, dan authenticate menolak
  `422` untuk subject berspasi dan non-string, dan `oidc_identities` tetap hanya memuat nilai yang
  benar-benar ditautkan.

Test lama `test_identity_mapping_backup_and_migration_from_43` diperbarui: sebelumnya ia menegaskan
perilaku lama (`' employee-123 '` ditautkan sebagai `'employee-123'`), sekarang menautkan nilai persis
dan tetap memverifikasi backup serta migrasi dari schema 43.

## Catatan operasional

Mapping yang sudah tersimpan dalam bentuk terpangkas tidak dapat dibalik otomatis karena baris lama
tidak menyimpan nilai asli dari penyedia. Sebelum dipakai lagi sesudah upgrade, bandingkan pasangan
issuer/subject pada `oidc_identities` dengan nilai `sub` yang benar-benar diterbitkan penyedia.
Bila provider ternyata menerbitkan subject dengan spasi awal/akhir, nilai itu ditolak — `401` pada
klaim token dan `422` pada `oidc-link`/`oidc-unlink` — jadi tidak ada akun yang terpetakan keliru.
Identitas seperti itu hanya dapat didukung lewat perubahan schema yang melonggarkan
`CHECK(subject=trim(subject))` pada `oidc_identities`; perbaikan ini sengaja tidak melakukannya agar
tidak ada migrasi tabel identitas untuk kasus yang belum terbukti ada pada provider nyata.
