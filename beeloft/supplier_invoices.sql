-- B01 (#50): entitas tagihan supplier (supplier invoice) + identitas invoice
-- untuk permintaan pembayaran supplier.
--
-- Batas scope #50 (fondasi minimal, dipakai #54 untuk settlement/AP):
-- - Invoice = dokumen tagihan dari pemasok: identitas global (supplier_id,
--   reference), snapshot pemasok, tanggal invoice/jatuh tempo, dan alokasi
--   qty/nilai ke baris PO (berdasar penerimaan fisik yang belum direversal).
-- - TIDAK mencakup: credit note/reversal invoice, cicilan multi-request di
--   luar batas nilai alokasi, invoice multi-mata uang, posting jurnal AP/utang
--   otomatis, settlement/kas/bank, dan alokasi pembayaran aktual. Itu #54/#59.
-- - Harga alokasi WAJIB sama dengan harga aktual baris PO (terkunci saat PO
--   diterbitkan); harga referensi master tidak dipakai untuk invoice.
--
-- Perubahan pada supplier_payment_requests:
-- - Kolom invoice_id baru menunjuk invoice terdaftar. Baris legacy
--   (dibuat sebelum #50, invoice_id NULL) dikecualikan dari validasi baru.
-- - UNIQUE(purchase_order_id, invoice_reference) level tabel DICABUT: constraint
--   itu memblokir pengajuan ulang invoice yang sama setelah request
--   ditolak/dibatalkan. Duplikat AKTIF (submitted/approved) tetap ditolak di
--   Python (create_supplier_payment_request).
-- - Rebuild memakai DROP + RENAME; trigger pada tabel induk dibuat SETELAH
--   salin data agar baris legacy (invoice_id NULL) lolos tanpa difabrikasi.

BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS supplier_invoices (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL CHECK(length(trim(reference)) BETWEEN 1 AND 160),
    supplier_id TEXT NOT NULL REFERENCES suppliers(id),
    supplier TEXT NOT NULL CHECK(json_valid(supplier)),
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'IDR' CHECK(currency='IDR'),
    total_minor INTEGER NOT NULL CHECK(total_minor BETWEEN 1 AND 100000000000000),
    allocations TEXT NOT NULL CHECK(json_valid(allocations) AND json_array_length(allocations) BETWEEN 1 AND 100),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(supplier_id, reference),
    CHECK(invoice_date <= due_date)
) STRICT;
CREATE INDEX IF NOT EXISTS supplier_invoices_supplier ON supplier_invoices(supplier_id, sequence);

CREATE TRIGGER IF NOT EXISTS supplier_invoice_no_update BEFORE UPDATE ON supplier_invoices
BEGIN SELECT RAISE(ABORT,'Supplier invoices cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS supplier_invoice_no_delete BEFORE DELETE ON supplier_invoices
BEGIN SELECT RAISE(ABORT,'Supplier invoices cannot be deleted'); END;

-- Rebuild supplier_payment_requests: tambah invoice_id, lepas UNIQUE komposit.
-- Dua trigger pada tabel LAIN yang membaca tabel ini harus dicabut dulu agar
-- DROP TABLE tidak ditolak SQLite, lalu dibuat ulang setelah RENAME.
-- Seluruh trigger pada tabel induk dibuat SETELAH salin data + RENAME agar
-- INSERT ... SELECT tidak memicu validasi baris baru untuk histori legacy.
DROP TRIGGER IF EXISTS supplier_payment_request_event_valid;
DROP TRIGGER IF EXISTS supplier_payment_request_preserve_receipt;
CREATE TABLE supplier_payment_requests_new (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE CHECK(length(trim(reference)) BETWEEN 1 AND 160),
    purchase_order_id TEXT NOT NULL REFERENCES purchase_orders(id),
    invoice_id TEXT REFERENCES supplier_invoices(id),
    invoice_reference TEXT NOT NULL CHECK(length(trim(invoice_reference)) BETWEEN 1 AND 160),
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    amount_minor INTEGER NOT NULL CHECK(amount_minor BETWEEN 1 AND 100000000000000),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK(invoice_date<=due_date)
) STRICT;
INSERT INTO supplier_payment_requests_new(sequence,id,reference,purchase_order_id,invoice_id,
    invoice_reference,invoice_date,due_date,amount_minor,reason,actor_id,created_at)
SELECT sequence,id,reference,purchase_order_id,NULL,
    invoice_reference,invoice_date,due_date,amount_minor,reason,actor_id,created_at
FROM supplier_payment_requests;
DROP TABLE supplier_payment_requests;
ALTER TABLE supplier_payment_requests_new RENAME TO supplier_payment_requests;
CREATE INDEX IF NOT EXISTS supplier_payment_requests_po
ON supplier_payment_requests(purchase_order_id,sequence);
CREATE INDEX IF NOT EXISTS supplier_payment_requests_invoice
ON supplier_payment_requests(invoice_id,sequence);

-- Trigger-trigger di bawah ikut terhapus saat DROP; dibuat ulang verbatim dari
-- supplier_payment_approvals.sql (tanpa PRAGMA user_version), ditambah satu
-- trigger identitas invoice (#50).
CREATE TRIGGER IF NOT EXISTS supplier_payment_request_source_valid
BEFORE INSERT ON supplier_payment_requests
WHEN NOT EXISTS(
    SELECT 1 FROM purchase_orders p JOIN users u ON u.id=NEW.actor_id
    WHERE p.id=NEW.purchase_order_id
      AND u.active=1 AND u.role IN ('admin','operator')
      AND (SELECT status FROM purchase_order_approval_events WHERE order_id=p.id
           ORDER BY sequence DESC LIMIT 1)='approved'
      AND NOT EXISTS(SELECT 1 FROM purchase_order_cancellations WHERE order_id=p.id)
      AND EXISTS(SELECT 1 FROM purchase_order_receipts x
          JOIN material_movements m ON m.batch_id=x.batch_id AND m.kind='receipt'
          WHERE x.purchase_order_id=p.id
            AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id))
      AND NEW.amount_minor+COALESCE((
          SELECT SUM(r.amount_minor) FROM supplier_payment_requests r
          WHERE r.purchase_order_id=p.id AND
            (SELECT status FROM supplier_payment_request_events e WHERE e.request_id=r.id
             ORDER BY e.sequence DESC LIMIT 1) IN ('submitted','approved')),0)
          <=(SELECT received_value_minor FROM supplier_payment_po_received WHERE purchase_order_id=p.id)
)
BEGIN SELECT RAISE(ABORT,'Invalid supplier payment request source or amount'); END;

-- Payment request baru WAJIB menunjuk invoice terdaftar (#50): identitas
-- (supplier, reference) cocok dengan PO dan alokasi invoice mencakup PO ini.
-- Baris legacy (invoice_id NULL) dikecualikan agar histori tidak difabrikasi.
CREATE TRIGGER IF NOT EXISTS supplier_payment_request_invoice_valid
BEFORE INSERT ON supplier_payment_requests
WHEN NEW.invoice_id IS NULL
    OR NOT EXISTS(
        SELECT 1 FROM supplier_invoices i
        JOIN purchase_orders p ON p.id=NEW.purchase_order_id
        WHERE i.id=NEW.invoice_id
          AND i.supplier_id=p.supplier_id
          AND i.reference=NEW.invoice_reference
          AND EXISTS(SELECT 1 FROM json_each(i.allocations) a
                     WHERE json_extract(a.value,'$.purchase_order_id')=NEW.purchase_order_id))
BEGIN SELECT RAISE(ABORT,'Payment request requires a registered supplier invoice for this PO'); END;

CREATE TRIGGER IF NOT EXISTS supplier_payment_request_no_update
BEFORE UPDATE ON supplier_payment_requests
BEGIN SELECT RAISE(ABORT,'Supplier payment requests cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS supplier_payment_request_no_delete
BEFORE DELETE ON supplier_payment_requests
BEGIN SELECT RAISE(ABORT,'Supplier payment requests cannot be deleted'); END;

-- Dua trigger yang dicabut sebelum DROP dibuat ulang verbatim dari
-- supplier_payment_approvals.sql.
CREATE TRIGGER IF NOT EXISTS supplier_payment_request_event_valid
BEFORE INSERT ON supplier_payment_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND EXISTS(
      SELECT 1 FROM supplier_payment_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND r.actor_id=NEW.actor_id AND r.reason=NEW.reason
        AND u.active=1 AND u.role IN ('admin','operator')))
    OR
    (NEW.status IN ('approved','rejected') AND EXISTS(
      SELECT 1 FROM users u WHERE u.id=NEW.actor_id AND u.active=1 AND u.role='admin'))
    OR
    (NEW.status='cancelled' AND EXISTS(
      SELECT 1 FROM supplier_payment_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND u.active=1
        AND (u.role='admin' OR (u.role='operator' AND r.actor_id=NEW.actor_id)))),0)
BEGIN SELECT RAISE(ABORT,'Invalid supplier payment request event'); END;

CREATE TRIGGER IF NOT EXISTS supplier_payment_request_preserve_receipt
BEFORE INSERT ON material_movements
WHEN NEW.reversal_of IS NOT NULL AND EXISTS(
    SELECT 1 FROM material_movements original
    JOIN purchase_order_receipts x ON x.batch_id=original.batch_id
    WHERE original.id=NEW.reversal_of AND original.kind='receipt'
      AND COALESCE((SELECT SUM(r.amount_minor) FROM supplier_payment_requests r
          WHERE r.purchase_order_id=x.purchase_order_id AND
            (SELECT status FROM supplier_payment_request_events e WHERE e.request_id=r.id
             ORDER BY e.sequence DESC LIMIT 1) IN ('submitted','approved')),0)
          >(SELECT COALESCE(SUM(CAST((
              COALESCE((SELECT SUM(other.quantity_milli) FROM purchase_order_receipts other_link
                  JOIN material_batches other_batch ON other_batch.id=other_link.batch_id
                  JOIN material_movements other ON other.batch_id=other_batch.id AND other.kind='receipt'
                  WHERE other_link.purchase_order_id=p.id AND other.id!=original.id
                    AND other_batch.material_id=json_extract(line.value,'$.material_id')
                    AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=other.id)),0)
              *CAST(ROUND(CAST(json_extract(line.value,'$.unit_price') AS NUMERIC)*100) AS INTEGER)+500
              )/1000 AS INTEGER)),0)
            FROM purchase_orders p,json_each(p.lines) line WHERE p.id=x.purchase_order_id)
)
BEGIN SELECT RAISE(ABORT,'Active supplier payment exceeds remaining received value'); END;

PRAGMA user_version=62;
COMMIT;
