# Verifikasi hasil cutting dan bahan asal — v0.18

Tanggal: 11 September 2026. Base `f405417`; branch `feature/cutting-output`.
Pengujian memakai worktree lokal serta database sementara.

## Hasil

- Tes fitur cutting awal gagal karena endpoint, schema, dan UI belum tersedia.
- Setelah implementasi: `python -m unittest discover -s tests -q` → **104 tests OK**.
  Delapan tes cutting mencakup output beberapa ukuran, pemakaian/waste satu transaksi,
  saldo WIP, race, role, input pecahan pcs, rollback, koreksi, guard SQL, migrasi,
  persistence, backup dan cursor.
- `node tests/test_client.mjs` → Client checks PASS; CSV client checks PASS.
- `node --check beeloft/static/app.mjs` → PASS.
- `python -m pip check` → No broken requirements found.
- OpenAPI diekspor ulang dari `create_app()` dengan versi 0.18.0 dan empat route cutting.
- `git diff --check` → PASS; peringatan LF/CRLF Git tidak mengubah isi.

## Browser

Runner `tests/run_browser.py` memakai Playwright dan Edge pada server/database sementara.
Semua suite lama, supplier returns, dan `browser_cutting.cjs` lulus tanpa JavaScript error.
Suite cutting memeriksa output M/L, saldo cutting/sewing, batch bahan asal, pemakaian dan
waste, batas saldo dan input pcs, respons hilang lalu reload/retry tanpa duplikasi,
operator/viewer/admin, koreksi seluruh run, link dari riwayat, layout 320/390/768 px,
dan skala teks 200%.

Screenshot form cutting mobile dan rincian output diperiksa secara visual dan tersimpan
lokal di folder `outputs/beeloft-one-qa`, di luar repository.

## Review dan batas

Review terhadap store/API/UI dan migration guards tidak menemukan masalah yang perlu
ditindaklanjuti. Hasil cutting sengaja memakai satu pengeluaran bahan agar batch asal jelas;
tidak ada konversi meter-ke-pcs atau alokasi biaya otomatis. Koreksi output harus membalik
semua perpindahan dan pemakaian bersama-sama. Identitas bundle, barcode, multi-material,
scrap valuation, missing pieces, dan vendor/makloon belum termasuk.
