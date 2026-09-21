# F03 — penutupan temuan audit teknis

Handoff untuk [#42](https://github.com/wenn-id/beeloftone/issues/42), gap G07,
peran A3. Baseline pemeriksaan ulang:
[`1eb3c2d548457a595e154e5fa87c360e0c65b073`](https://github.com/wenn-id/beeloftone/commit/1eb3c2d548457a595e154e5fa87c360e0c65b073),
aplikasi 0.97.0, schema 55. Branch `codex/f03-close-technical-audit`.

Semua issue #26–#37 sudah CLOSED ketika diperiksa. Perbaikan lama ditautkan ke
commit merge di bawah; issue tersebut tidak dibuka ulang. Pemeriksaan F03
menemukan satu sisa bug scope produksi #29 pada HEAD dan memperbaikinya di branch
ini. Status penerimaan bisnis dan reviewer tetap terpisah dari status teknis.

## Matriks bukti

Kolom bukti lama merekam reproduksi sebelum/sesudah perbaikan terdahulu.
F03 juga menjalankan kembali 10 reproducer backend/dokumentasi pada worktree
terpisah `f8921e763a8b317f3680229aedb9406ddba687c8` dan branch ini. Reproducer
browser sebelum perbaikan tetap merujuk bukti lama; suite browser sesudahnya
dijalankan kembali pada F03.

| Issue | Commit perbaikan yang sudah digabung | Bukti lama dan regresi pada HEAD |
|---|---|---|
| #26 — collision subject OIDC | [07680ee](https://github.com/wenn-id/beeloftone/commit/07680ee02c02dfcfdd942ccca5227bde0492de16) | [Bukti token bertanda tangan](audit-oidc-subject-verification.md); `test_oidc_sso.py`: subject berbeda tidak membuat session akun tertaut; link/unlink/authenticate konsisten. Review mapping lama oleh operator masih diperlukan. |
| #27 — draft SKU hilang | [33ba7ee](https://github.com/wenn-id/beeloftone/commit/33ba7ee7bd22fd3e2be40aeed5f63f2d3aa6ae81) | [Bukti race dialog](audit-p2-mapping-dialog-race-verification.md); `browser_product_external_mappings.cjs`: respons edit/unmap tertunda mempertahankan draft baru dan respons setelah logout tidak membuka dialog. |
| #28 — margin net revenue nol | [10d330e](https://github.com/wenn-id/beeloftone/commit/10d330eec508f5ecdceb8f396a49126c12bc08c7) | [Bukti rasio nullable](audit-margin-null-ratio-verification.md); `test_zero_net_revenue_margin_answers_without_a_ratio`: pertanyaan umum/fokus HTTP 200, nominal benar, rasio tetap tidak tersedia. |
| #29 — scope produksi AI | [80c1d03](https://github.com/wenn-id/beeloftone/commit/80c1d03aa9f602fa64fc319aa14b3b04a7f36fd9) | [Bukti agregat fokus awal](audit-p2-focused-production-aggregate-verification.md); `test_ai_investigation.py` dan `test_production_scope.py`. Sisa kebocoran lewat pencarian teks diperbaiki F03, lihat reproduksi berikut. |
| #30 — login paralel | [c884f86](https://github.com/wenn-id/beeloftone/commit/c884f8667659086a84a8357a143839d1f9c87509) | [Bukti login](audit-p2-login-submit-verification.md); `browser_login_form.cjs`: respons tertunda, klik ganda/Enter/requestSubmit, label dan aksi SSO aktif maupun tersembunyi. |
| #31 — query authorization endpoint | [5d0b316](https://github.com/wenn-id/beeloftone/commit/5d0b3160b2d41d540c26dd3a910dc7ad3607ef6e) | [Bukti query endpoint](audit-p2-oidc-authorization-query-verification.md); `test_authorization_endpoint_query_is_kept_as_separate_parameters` serta login PKCE tanpa query. |
| #32 — encoding client_secret_basic | [c388a0f](https://github.com/wenn-id/beeloftone/commit/c388a0f1ed3521257e67780c2223b1f83a305e5e) | [Bukti transport OAuth](audit-p2-oidc-client-secret-basic-verification.md); `OidcBasicAuthTest`: encoding ID/secret terpisah dan kontrol `client_secret_post`. |
| #33 — integer SQLite | [f79d51d](https://github.com/wenn-id/beeloftone/commit/f79d51dd2974bda31c0b5c25746b947da1d1a975) | [PR #74](https://github.com/wenn-id/beeloftone/pull/74); `test_query_integer_bounds.py`: enumerasi offset/before dari OpenAPI, 2**63 ditolak 422, batas valid diterima. |
| #34 — overflow UTC | [4125dcc](https://github.com/wenn-id/beeloftone/commit/4125dccfd24849e6e9d62406eb98073c5faf7c2d) | [PR #73](https://github.com/wenn-id/beeloftone/pull/73); `TimestampTimezoneBoundaryTest`: kedua ujung kalender, 16 validator, timestamp normal, tanpa mutasi saat ditolak dan retry key tetap valid. |
| #35 — state OIDC non-ASCII | [9f897b2](https://github.com/wenn-id/beeloftone/commit/9f897b28c73c7767f515480082680c162cb263f5) | [Bukti state](audit-p3-oidc-state-non-ascii-verification.md); `test_oidc_sso.py`: query/cookie state invalid ditolak 401, state sah sekali pakai. |
| #36 — hidrasi approval | [b2803ec](https://github.com/wenn-id/beeloftone/commit/b2803ecd2c9a1d948b1ecaa027202ae5a8696887) | [Bukti jumlah query lama](audit-p3-approval-focus-hydration-verification.md); `test_ai_focus_hydration.py`: metadata, evidence, agregat tetap benar tanpa membaca detail seluruh order. Pengukuran HEAD di bawah. |
| #37 — drift dokumentasi | [2bee570](https://github.com/wenn-id/beeloftone/commit/2bee57075b2e0826dfcd581691d37585e7dd1df2) | [PR #75](https://github.com/wenn-id/beeloftone/pull/75); `test_openapi_contract.py`, `test_readme_test_count.py`, dan perbandingan penuh OpenAPI dengan runtime pada F03. |

Hasil reproduksi ulang F03 pada baseline audit: 10 test, **16 failure subtest
dan 2 error** (26,590 detik); pada branch ini: **10 test OK** (25,917 detik).
Runtime dimuat dari masing-masing checkout, dengan test regresi dari HEAD.
Kegagalannya sesuai temuan: #26 callback 303 alih-alih 401; #28 `TypeError`
rasio `None`; #29 angka order lain; #31 query endpoint; #32 credential hasil
decode berbeda; #33 kedua GET 500 alih-alih 422; #34 `OverflowError`; #35
callback non-ASCII 500; #36 126 versus 626 pembacaan; #37 versi 0.86.0 versus
0.87.0. Tidak ada kegagalan import yang dihitung sebagai reproduksi bug.

Untuk #33, probe HTTP memakai kedua URL dari issue dengan parameter `2**63`
dan `TestClient(..., raise_server_exceptions=False)`. Test #37 membaca kontrak
dari checkout yang sedang diuji. Sembilan reproducer lainnya adalah test
bernama pada matriks (untuk #36: `test_approval_cost_stays_flat_while_the_order_population_grows`).

## Sisa #29: ID fokus berubah menjadi pencarian teks

`_focus()` sudah memilih ID, tetapi `_production()` mengubah satu order/SKU
menjadi string pencarian board. `FOCUS-ONE` ikut mengambil `FOCUS-ONE-EXTRA`;
lebih dari satu order/SKU menghasilkan query kosong dan seluruh produksi.
Margin sudah memakai ID terpilih melalui `order_ids_for_products()`.

Reproducer baru:
`AiInvestigationTest.test_production_focus_uses_selected_ids_instead_of_text_search`.
Data sintetis: dua order fokus belum jatuh tempo, satu order lain terlambat dengan
500 pcs di cutting, dan satu SKU tanpa order.

| Pertanyaan setelah `Cek produksi` | HEAD sebelum: aktif / terlambat / WIP | Sesudah: aktif / terlambat / WIP |
|---|---|---|
| `FOCUS-ONE` | 2 / 1 / 500 | 1 / 0 / 0 |
| `FOCUS-ONE dan FOCUS-TWO` | 3 / 1 / 500 | 2 / 0 / 0 |
| `LUNA-BLUE-M dan EMPTY-M` | 3 / 1 / 500 | 2 / 0 / 0 |
| `EMPTY-M` (kontrol) | 0 / 0 / 0 | 0 / 0 / 0 |

Satu test gagal pada tiga subtest sebelum perbaikan, lalu lulus. Delapan test
modul investigasi lulus sesudah perbaikan (25,265 detik), termasuk agregat
120 order yang melewati halaman pertama berukuran 100.

Perbaikan memakai ID dari focus, dengan prioritas order lalu produk seperti
jalur margin. Board dan scope menerima filter ID internal yang sama melalui satu
parameter JSON. `None` berarti seluruh populasi; `[]` berarti tidak ada order.
Daftar evidence, finding, rekomendasi dan agregat fokus mengikuti ID itu.
Ringkasan dan jumlah kendala global pada evidence board tetap kontrak board lama;
angka jawaban/facts berasal dari `production_scope`.

## Validasi F03

Lingkungan: Windows, Python 3.12.13, SQLite 3.53.1, Node.js 24.18.0,
Playwright 1.63.0 dengan Chromium; dependencies Python dari `requirements.txt`.
Database hanya sementara dan sintetis. CI memakai Linux/Node.js 22, sehingga
hasil lokal tidak dinyatakan sebagai hasil CI.

| Pemeriksaan | Hasil |
|---|---|
| `python -m unittest discover -s tests -v` | 573 test OK, 1.019,905 detik, exit 0. |
| `python tests/run_browser.py --node node --playwright-module <playwright> --channel chromium` | 79 modul acceptance dan runner utama PASS; exit 0, tanpa error JavaScript. |
| `uv pip check --python .venv/Scripts/python.exe` | 23 package konsisten. |
| `python -m compileall -q beeloft` | Lulus. |
| `node --check beeloft/static/app.mjs` dan `client.mjs` | Lulus. |
| `node tests/test_client.mjs` | Lulus. |
| Perbandingan `create_app(db_sementara).openapi()` dengan `json.loads(docs/openapi.json)` | Sama seluruh dokumen: 221 path, 85 schema, versi 0.97.0. |
| Query approval, memakai `FocusHydrationFixture.executed_sql` | 20 order: 28 statement / 20 pembacaan; 120 order: 28 / 20. Daftar statement identik; tidak membaca `balances`, `order_lines`, `order_changes`. |

Pengukuran approval membandingkan populasi 20 lalu 120 order dengan SQLite trace
yang sudah dipakai tes repository. Bukti sebelum perbaikan #36 tetap ada pada
dokumen lama: 528 / 5.028 / 25.028 statement untuk 100 / 1.000 / 5.000 order,
menjadi 28 untuk ketiganya. Ini bukti hilangnya hidrasi per order, bukan benchmark
latensi produksi. Pencocokan identitas masih membaca populasi identitas; tidak ada
klaim penggunaan memori atau waktu konstan.

## Handoff dan batas penerimaan

- File berubah: `beeloft/brain.py`, `beeloft/store.py`,
  `tests/test_ai_investigation.py`, `README.md`, dan dokumen ini. Commit akhir
  beserta bukti hasil suite dicatat pada PR F03.
- Tidak ada perubahan API publik, schema/migrasi, dependency, aturan nominal/qty,
  penulisan ledger, izin, idempotency, revision guard atau mekanisme reversal.
  Filter ID adalah argumen internal; pencarian teks `/api/production-board`
  tetap berperilaku seperti sebelumnya. Tidak ada nomor migrasi yang diperlukan.
- Tidak memerlukan keputusan rumus bisnis baru. Keputusan F01/F02 yang belum
  disahkan tidak ditebak atau diterapkan oleh perbaikan ini.
- Operator identitas masih harus membandingkan mapping OIDC lama dengan subject
  asli provider. Nilai yang sudah terpangkas tidak dapat dipulihkan otomatis.
  F03 tidak mengakses provider, kredensial atau database produksi.
- Review lintas domain dan penerimaan A0/pemilik bisnis: **PENDING**, tidak
  disimpulkan dari test atau merge. #42 memakai referensi PR tanpa auto-close
  sampai koordinator menerima handoff dan bukti operasional yang diperlukan.
- Tidak ada klaim bahwa aplikasi bebas bug atau siap cutover; temuan di luar
  #26–#37 dan keputusan roadmap lain tetap mengikuti paket masing-masing.
