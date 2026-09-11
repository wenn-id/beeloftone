# Verifikasi QC bahan masuk (v0.16)

Base `ab9fe20` · branch `feature/core-materials` · worktree lokal.

Penerimaan dari PO masuk sebagai hold. Hold mengurangi sisa yang boleh datang, tetapi belum
menambah batch, saldo rak, atau reservasi. Admin memutuskan sebagian/seluruh jumlah sebagai
layak pakai atau reject. Layak pakai membuat batch baru dan hubungan PO; reject membuka jatah
pengganti. Sisa tanpa keputusan tetap hold. Koreksi keputusan menjaga ledger dan syarat stok
yang sudah dipakai/direservasi; pembatalan kedatangan hanya boleh tanpa keputusan aktif.

## Bukti otomatis

- `python -m unittest discover -s tests -q` → **86 tests OK**.
- `tests/test_incoming_qc.py` → **6 tests OK**, termasuk guard database yang menolak pembalikan
  acceptance jika receipt batch belum dibalik.
- `node tests/test_client.mjs` → **Client checks PASS** dan **CSV client checks PASS**.
- `node --check beeloft/static/app.mjs` → **PASS**.
- `python -m pip check` → **No broken requirements found**.
- OpenAPI dibuat ulang dari `create_app()` dan memuat versi `0.16.0` serta route Incoming QC.
- `git diff --check` → **PASS** (peringatan LF/CRLF Git tidak mengubah isi).

## Browser QA

`tests/run_browser.py --channel msedge` lulus seluruh suite dan tidak melaporkan JavaScript
error. Suite Incoming QC menguji kedatangan sebagai hold, retry setelah respons hilang dan
reload, role operator/viewer/admin, partial accept, reject, sisa PO, batch source link, stok
yang baru muncul setelah accept, koreksi accept/reject, pembatalan intake, mobile 320/390/768
px, dan skala font 200%.

Screenshot QA: `beeloft-qc-form-mobile.png` dan `beeloft-incoming-qc.png` di folder output
`beeloft-one-qa`; keduanya diperiksa secara visual.

## Review

Reviewer menemukan celah database-only pada pembalikan keputusan layak pakai: keputusan bisa
dikembalikan ke hold tanpa membalik batch. Guard `qc_decision_valid` kini mensyaratkan receipt
batch sudah memiliki reversal; guard tambahan juga memvalidasi batch acceptance cocok dengan
material, intake dan jumlah keputusan. Tidak ada temuan lain pada transaksi, kuota PO, migrasi,
role atau UI.

## Batas

Hanya bahan yang sudah diputuskan layak pakai masuk stok. Return ke pemasok, penutupan sisa PO,
retur sebagian, pembayaran, dan dokumen pengiriman belum tersedia. Langkah berikutnya adalah
alur return/closure setelah QC selesai.
