# Verifikasi pemakaian aktual dan waste cutting

Base implementasi: `6894034`, branch lokal `feature/core-materials`. Perubahan dikerjakan di
worktree dan tidak dipush ke GitHub.

## Cakupan

- pemakaian parsial dan waste pada satu pengeluaran bahan;
- batas jumlah, validasi satuan m/kg/pcs, dan idempotensi retry;
- izin admin/operator/viewer, pembalikan immutable, serta penjagaan pembalikan pengeluaran;
- penulisan bersamaan, rollback transaksi, migrasi schema 6 → 7, backup/restore dan cursor history;
- dialog order, validasi browser, retry, role switching, mobile dan zoom 200%;
- kontrak OpenAPI, client checks, syntax JavaScript dan kebersihan diff.

## Bukti eksekusi

Perintah dijalankan dari root worktree:

```powershell
$env:PYTHONPATH=(Get-Location).Path
..\..\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/test_client.mjs
node --check beeloft/static/app.mjs
..\..\.venv\Scripts\python.exe -m pip check
git diff --check
```

Browser acceptance memakai runner sementara dan Edge:

```powershell
..\..\.venv\Scripts\python.exe tests/run_browser.py `
  --node C:\Users\acer\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe `
  --playwright-module C:\Users\acer\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright `
  --channel msedge
```

Hasil terakhir pada increment ini: **66 backend tests passed**, client checks passed, JavaScript
syntax check passed, `pip check` passed, `git diff --check` bersih, dan seluruh browser suites
(materials, BOM, reservations, consumption) lulus tanpa error JavaScript. Consumption browser QA
memverifikasi validasi overage, pemakaian+waste parsial, retry committed, saldo rack/reservasi/WIP
tetap, role, pembalikan dan tampilan mobile/200%.

Permintaan review independen khusus increment ini mencapai batas penggunaan akun sebelum reviewer
menghasilkan laporan. Tidak ada temuan reviewer yang dapat diklaim; verifikasi di atas dijalankan
langsung terhadap worktree.
