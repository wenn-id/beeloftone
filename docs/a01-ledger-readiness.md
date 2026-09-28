# A01: ledger keuangan dan kontrak posting (#46)

Implementasi [#46](https://github.com/wenn-id/beeloftone/issues/46), diperbarui
28 September 2026. F02 [#41](https://github.com/wenn-id/beeloftone/issues/41),
M01 [#43](https://github.com/wenn-id/beeloftone/issues/43) dan M02
[#44](https://github.com/wenn-id/beeloftone/issues/44) sudah merged; skema 57.
Dokumen readiness sebelumnya (22 Sep 2026, schema 55) sudah kedaluwarsa.

**Status:** kontrak posting native A01 diimplementasikan pada skema 59 dengan
aturan demo sintetis. D14 memilih arah akuntansi native lengkap bertahap, tetapi
detail COA, costing, timing pengakuan, pajak, dan periode **belum business
accepted** — mapping di `beeloft/posting_rules.py` berlabel `DEMO_ASSUMPTION`
dengan policy ref `DEMO-POST-20260928-1` dan bukan kebijakan resmi perusahaan.
Jangan presentasikan akun/mapping demo sebagai kebijakan akuntansi Beeloft.

## Yang dibangun

- **Migrasi 59** (`beeloft/financial_ledger.sql`): `coa_accounts`,
  `accounting_periods`, `journals`, `journal_lines`. Uang integer minor;
  trigger melarang UPDATE/DELETE jurnal dan lines, dan hanya mengizinkan
  perubahan status aktif pada COA.
- **Posting atomik** (`Store.post_journal`): satu `BEGIN IMMEDIATE`, seimbang
  eksak debit=kredit, akun harus ada dan aktif, nilai Decimal→minor dengan
  presisi 2 desimal eksplisit, tanggal di dalam periode, periode harus open
  (dicek dalam transaksi yang sama — race post-vs-close ditolak).
- **Sumber sekali** (`source identity`): unique key
  `(source_system, source_account, source_entity_type, source_id)`.
  Replay identik (isi sama, key berbeda) mengembalikan jurnal yang sama;
  payload berbeda untuk sumber sama → 409 konflik. Revision sumber adalah
  metadata, bukan kunci — satu event ekonomi tepat satu jurnal.
- **Reversal bertaut**: `Store.reverse_journal` membuat jurnal baru dengan
  `reversal_of` ke kode jurnal asal; jurnal asal immutable (trigger + API
  menolak edit). Double reversal dan reversal-of-reversal ditolak 409.
  Reversal memakai periode terbuka yang dipilih eksplisit — tidak ada
  pembukaan periode otomatis, dan reversal ke periode tertutup ditolak.
- **Close/reopen periode**: `close_period`/`reopen_period` memakai
  `expected_revision` (optimistic guard) dan alasan wajib; dicatat di audit.
- **Trial balance** (`Store.trial_balance`, `GET /api/trial-balance`):
  dihitung dari lines jurnal native dalam scope periode (dan unit opsional),
  termasuk reversal; total debit=kredit.
- **API**: `GET/POST /api/coa-accounts` (+ seed demo, activate/deactivate),
  `GET/POST /api/accounting-periods` (+ close/reopen),
  `GET/POST /api/journals` (+ detail, reverse),
  `POST /api/purchase-orders/{id}/receipt-journal`,
  `GET /api/trial-balance`. Semua tulis hanya role `admin`; baca butuh
  autentikasi. Ownership tabel+endpoint: `docs/f02-ownership.csv`.
- **UI**: workspace **Keuangan** dengan tab COA, Periode, Jurnal, Neraca saldo;
  jurnal immutable; seed COA demo berlabel sintetis.
- **Tes**: `tests/test_a01_financial_ledger.py` — 33 tes (+12 subtes):
  migrasi 59 & upgrade 58→59, COA, periode (overlap, revision guard, close/
  reopen), posting seimbang/tidak seimbang/akun invalid/nonaktif/tanggal di
  luar periode, replay sumber identik, konflik sumber, idempotency key,
  penolakan periode tertutup, konkurensi 8 thread satu sumber, reversal
  (tautan, double, of-reversal, periode tertutup), immutability trigger,
  izin role, semua builder posting rules seimbang, adapt PO receipt, dan
  endpoint HTTP end-to-end.

## Batas yang tetap dijaga

- Ledger kuantitas/operasional existing (`balances`/`movements`) tidak diubah;
  tidak menduplikasi stok, biaya tenaga kerja, atau snapshot Mekari.
- Snapshot Mekari payroll (`MekariPayrollAccounting`) tetap bukti eksternal,
  bukan jurnal native; rekonsiliasi `posting_unbalanced` dipertahankan.
- Approval supplier/snapshot bukan bukti pembayaran; adapter
  `post_po_receipt_journal` hanya memposting penerimaan barang (material
  receipt) dari PO terkunci — bukan pembayaran AP, bukan payroll, bukan POS.
- #59 (laporan keuangan) di luar scope; yang ada hanya trial balance per
  periode.
- Izin memakai role server existing sampai #45 merged; endpoint keuangan tidak
  tanpa autentikasi/otorisasi.
- #49 tetap lewat PR #116; #110 diabaikan; PR #46 tetap **draft/open**, tanpa
  auto-merge.

## Acceptance yang sudah terpenuhi oleh tes

1. **Seimbang dan tepat**: akun valid/aktif, presisi 2 desimal, tolak tidak
   seimbang; rollback tidak menyisakan jurnal separuh jadi.
2. **Sumber sekali**: key sama, key berbeda, dan 8 thread bersamaan → tepat
   satu jurnal; payload berbeda → 409.
3. **Atomik**: trigger + transaksi tunggal; replay setelah rollback aman.
4. **Reversal/locking**: reversal bertaut, histori dipertahankan; posting ke
   periode tertutup ditolak; race post-vs-close dicek dalam transaksi sama.
5. **Trial balance**: dari lines native dalam scope, termasuk reversal;
   debit=kredit; saldo akun kembali nol setelah reversal penuh.
6. **Kompatibilitas dan akses**: upgrade 58→59, fresh DB 59, ledger existing
   utuh, endpoint HTTP, izin admin-only, UI tanpa console error (browser test).

## Yang masih menunggu business acceptance

D13 (metode valuasi, komponen biaya, waste/reject/rework/overhead, WIP,
alokasi COGS), D14 detail (COA resmi, per event: kapan diakui, akun
debit/kredit, sumber nilai, pajak/potongan, pembulatan), D15 (cutoff, late
entry, reversal lintas periode, reopen), D01/D17 (hak post/reverse/close
akuntansi dan pemisahan tugas), D18/D19 (migrasi/opening balance). Adapter
producer native (PO receipt dari event DB, payroll, sales, kasbon) belum
terhubung ke event domain nyata — `adapt_po_receipt` memakai data sintetis
demo sampai producer tersedia.
