# Verifikasi riwayat investigasi dan feedback AI, v0.41

Tanggal: 13 September 2026. Base `3548aef`; branch `feature/ai-investigation-memory` pada worktree
lokal. Semua pengujian memakai database sementara.

## Cakupan backend

Lima acceptance test baru memeriksa snapshot dan retry idempotent, filter intent/pertanyaan, cursor,
snapshot yang tetap sama setelah ledger berubah, feedback semua role, perubahan feedback per aktor,
linkage proposal, penolakan asumsi atau rekomendasi stale, rollback, immutable trigger, backup, serta
migrasi schema 31 ke 32.

Seluruh suite backend lulus: **223 test dalam 139,544 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`).

## Browser dan client

Edge/Playwright menjalankan seluruh browser regression suite. Viewer menyimpan investigasi stockout
dengan respons pertama hilang setelah commit, lalu memperoleh record yang sama melalui retry dengan
Idempotency-Key yang sama. Viewer memberi feedback, mencari snapshot lewat riwayat, dan tetap tidak
melihat tombol proposal. Operator membuat proposal dari investigasi lain; admin menyetujuinya dan
dapat berpindah dari proposal ke investigasi asal serta kembali ke tindakan tertaut.

Escaping HTML, filter, mobile 390 px, skala teks 200%, pemulihan transaksi, seluruh modul lama, dan
ketiadaan error JavaScript ikut diperiksa.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.41.0 dan endpoint riwayat, detail, pembuatan snapshot, serta
feedback. Database baru dan hasil migrasi memakai schema 32.

## Batas

Feedback tidak melatih model atau mengubah hasil analisis otomatis. Engine masih memakai aturan lokal
dan ledger internal. Tidak ada pengiriman data ke model eksternal, kebijakan retensi, atau pembatasan
riwayat per departemen pada increment ini.
