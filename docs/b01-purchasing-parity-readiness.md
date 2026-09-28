# B01: validasi parity pembelian (#50) — status implementasi

Branch `feat/b01-purchasing-parity-50`, app **0.120.0**, DB **schema 62**
(migrasi `supplier_invoices.sql`; upgrade 61→62 teruji, FK integrity dicek).
Dokumen ini menggantikan analisis baseline 22 Sep 2026: dependensi
#43 (M01), #44 (M02), #41 (F02), #45 (O01), #46 (A01) sudah merged di main.

**Dependensi merge: PR ini dibuat di atas main tanpa #124 (P03, schema 61).
Jangan merge sebelum #124 mendarat** — migrasi 62 berasumsi tabel P03 sudah ada.

Sign-off bisnis (A1/A2/A3): **PENDING**. Tidak ada klaim praktik legacy
terkonfirmasi; yang diuji adalah aturan kode + asumsi demo di bawah.

## Peta acceptance criteria #50

| Kriteria | Status | Bukti |
|---|---|---|
| PR → PO (approval, revisi, satu PO aktif per PR) | ✅ existing | `test_purchase_requests.py`, `test_purchase_orders.py`, `test_purchase_order_approvals.py` |
| Supplier & material: salah/nonaktif ditolak, histori utuh | ✅ existing + B01 | PO/invoice menolak supplier nonaktif (422); identitas supplier tak dapat diubah (trigger); `test_supplier_invoices.py::test_inactive_supplier_and_material_rejected` |
| Partial receipt; over-receipt ditolak | ✅ existing | `test_po_receipts.py` (parsial, retry, concurrency, rollback); demo step 4 |
| Penerimaan parsial + QC hold/accept/reject | ✅ existing | `test_incoming_qc.py` |
| Retur supplier + reversal berjejak | ✅ existing | `test_supplier_returns.py`; retur menjaga referensi biaya & transaksi asal |
| Close sisa PO (parsial), receipt/retur/koreksi terkunci setelah close | ✅ existing | close: `test_close_requires_hold_and_rejected_material_resolved`; demo step 12–13 |
| Entitas **supplier invoice** terpisah (identitas global supplier+reference) | ✅ **baru B01** | `supplier_invoices.sql`, `Store.create_supplier_invoice`, `tests/test_supplier_invoices.py` (16 tes) |
| PO=pesanan, receipt=fisik, invoice=tagihan, approval=izin, settlement=aktual | ✅ **baru B01** | payment request wajib `invoice_id` (404/422 bila tak cocok); trigger DB `supplier_payment_request_invoice_valid`; settlement TIDAK dibangun (milik #54) |
| Satu invoice = satu payment request aktif; rejected/cancelled boleh diajukan ulang | ✅ **baru B01** | UNIQUE komposit dicabut di schema 62; duplikat aktif ditolak 409 di Python; `test_payment_request_invoice_rules` |
| Harga invoice = harga aktual baris PO; harga referensi master diabaikan | ✅ **baru B01** | mismatch harga 422; master `reference_price` diubah setelah receipt tidak menggerakkan invoice (`test_master_reference_price_change_does_not_move_invoice_price`) |
| Supplier mismatch invoice↔PO ditolak | ✅ **baru B01** | 422 + trigger; demo step 8 |
| Alokasi invoice ≤ penerimaan fisik belum-ditagih (belum direversal) | ✅ **baru B01** | 409; double-invoicing ditolak; `test_double_invoicing_rejected`, `test_partial_invoice_and_second_receipt` |
| Retry/idempotency, concurrency, rollback | ✅ | idempotency-key di semua POST (`_write`); `test_concurrent_invoice_registration_keeps_single_row`; `test_roles_and_retry` |
| Permission + unit scope (O01) | ✅ **baru B01** | `_require_unit_access` di create/decide PO, receipt/intake, retur, invoice, payment; `test_unit_scope_restricts_invoice_and_payment` |
| Upgrade DB 61→62, histori payment legacy utuh | ✅ | `test_upgrade_61_to_62_preserves_payment_history`; `PRAGMA foreign_key_check` pasca-rebuild |
| Adapter receipt journal #46 dipakai ulang; tanpa engine jurnal kedua | ✅ | `test_receipt_journal_adapter_is_idempotent_and_explicit`; invoice & payment TIDAK membuat jurnal (milik #54/#59) |
| UI: form/detail/status/dokumen invoice + loading/error/validasi | ✅ **baru B01** | `app.mjs`: daftar tagihan, form daftar tagihan (prefill sisa belum-ditagih, harga terkunci tampil), rincian tagihan (alokasi + sisa + payment request), form payment memilih invoice terdaftar; error server tampil di `#form-error`, retry tersedia |

## Alur yang bisa dicoba

1. UI: PO issued → tombol **Daftarkan tagihan supplier** → isi nomor tagihan,
   tanggal, qty per bahan (prefill = sisa belum ditagih; harga tampil terkunci
   ke harga PO) → simpan → rincian tagihan menampilkan alokasi, sisa, dan
   payment request terkait.
2. UI: dari rincian PO → **Ajukan pembayaran supplier** → pilih tagihan
   terdaftar (bukan ketik bebas) → nominal → simpan → admin approve.
   Approved = siap dibayar; tidak ada transfer.
3. CLI: `python scripts/demo_b01_purchasing_flow.py` — 17 langkah sintetis:
   PO → partial receipt → **over-receipt DITOLAK (409)** →
   **supplier-mismatch DITOLAK (422)** → receipt lanjutan → invoice →
   **supplier-salah DITOLAK (422)** → **harga-salah DITOLAK (422)** →
   **over-alloc DITOLAK (409)** → invoice kedua → close sisa →
   receipt-setelah-close DITOLAK → payment request menunjuk invoice →
   tanpa-invoice DITOLAK (404) → approve (siap bayar) →
   **duplikat-aktif DITOLAK (409)**.

## Asumsi demo (DEMO_ASSUMPTION)

- Seluruh pemasok/bahan/harga/tanggal/nomor dokumen pada skenario demo sintetis.
- Termin "approved" pada payment request = izin bayar; settlement/kas/bank
  belum ada di aplikasi (scope #54).
- Invoice memakai satu mata uang (IDR); tanpa credit note/reversal invoice;
  tanpa multi-PO per invoice di UI (API mendukung, UI satu PO per form).
- Kontrak harga: unit_price invoice harus sama persis dengan harga aktual
  baris PO; pembulatan half-up ke rupiah per baris.

## Kontrak handoff #54 (settlement/AP)

`supplier_invoices`: identitas global `UNIQUE(supplier_id, reference)`;
snapshot supplier (JSON, immutable); `invoice_date`, `due_date`, `total_minor`,
`allocations` (JSON: `purchase_order_id`, `material_id`, `quantity_milli`,
`unit_price_minor`, `line_total_minor` — qty/nilai berdasar penerimaan fisik
yang belum direversal, harga = harga aktual PO).

`supplier_payment_requests.invoice_id` → `supplier_invoices(id)` (nullable hanya
untuk baris legacy pra-#50; baris baru wajib, ditegakkan trigger
`supplier_payment_request_invoice_valid`). Satu invoice boleh punya banyak
payment request selama jumlah aktif (submitted/approved) tidak melebihi nilai
alokasi invoice untuk PO tersebut (`_invoice_requested_minor` vs
`_invoice_po_allocation_value`); duplikat AKTIF untuk pasangan (PO, invoice)
ditolak 409.

Yang #54 bangun sendiri: posting jurnal AP/utang, credit note, settlement/
alokasi pembayaran aktual, kas/bank, multi-mata uang. Jangan membuat invoice
dari metadata payment request legacy (`invoice_id` NULL) tanpa mapping dan
aturan duplikat yang disepakati.

## Verifikasi

- Full suite: lihat ringkasan PR (angka final setelah CI).
- `tests/test_supplier_invoices.py`: 16 tes (registrasi, alokasi parsial,
  supplier mismatch, validasi harga/qty, double-invoicing, unique per supplier,
  PO issued, supplier/material nonaktif, role+retry, aturan payment request,
  approval≠settlement, unit scope, konkurensi, adapter jurnal #46, upgrade 61→62).
- OpenAPI diregenerate (0.120.0): 299 paths, 130 schemas;
  `test_openapi_contract.py` memblokir kontrak tertinggal.
- Browser acceptance lokal tidak dijalankan (infrastruktur di CI); UI baru
  lolos `node --check`.

## Risiko & pending

- Merge diblokir sampai PR #124 (P03) mendarat — migrasi 62 menumpuk di atas 61.
- Sign-off bisnis A1/A2/A3 PENDING: aturan termin, pajak/diskon/ongkir, dan
  toleransi matching invoice-vs-EX08 belum disahkan pemilik proses.
- Multi-PO per invoice hanya via API; UI form invoice satu PO per pengisian.
- Invoice tidak punya reversal/credit note — koreksi invoice salah =
  keputusan bisnis pending (#54 atau revisi #50).
