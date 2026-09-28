BEGIN IMMEDIATE;
-- Migrasi 58 — P02 parity planning dan cutting (issue #49).
--
-- Prinsip yang dijaga:
-- * SATU ledger: output aktual dan konsumsi aktual tetap dicatat lewat
--   transaksi existing (movements + material_consumption via cutting_runs).
--   Tabel baru di sini hanya PARAMETER operasional (identitas rencana,
--   tanggal cutting, rol, setelan, berat) — bukan stok kedua dan bukan
--   pengganti pencatatan ledger.
-- * Target vs aktual vs layak bayar dipisahkan: target = order_lines.quantity
--   (immutable), aktual = movements net (dihitung, tidak disimpan),
--   kuantitas layak bayar BUKAN domain P02 (milik paket upah/payroll).
-- * Rumus legacy TIDAK diasumsikan: "lembar x setelan per lembar" hanya
--   ESTIMASI berlabel calculation_policy_ref; D02/D03 masih PROPOSED.
--   DEMO_ASSUMPTION: untuk demo 28 Sep 2026, setelan_per_lembar berarti
--   jumlah potongan (pcs) yang dihasilkan satu lembar; estimasi tidak
--   otomatis menjadi konsumsi aktual atau waste; tidak ada konversi kg<->m
--   tanpa faktor konversi yang valid.
-- * Presisi: berat kg disimpan milli-kg (1/1000 kg = 1 gram), berat gram
--   disimpan milli-gram; TIDAK ADA float pada jalur authoritative.
-- * Immutability: tabel parameter tidak dapat di-UPDATE/DELETE; koreksi
--   hanya lewat reversal existing (cutting_run_reversals) yang membalik
--   output + konsumsi sekaligus.
-- * Status planning: draft -> approved -> closed. DEMO_ASSUMPTION (D02
--   PROPOSED): hasil cutting hanya dapat dicatat untuk rencana approved;
--   approval single-step oleh admin dengan revision guard.
-- * Referensi PO pada cutting bersifat opsional; bila diisi harus merujuk
--   purchase_orders yang ada (validasi di store agar pesan 404/422 eksplisit).

CREATE TABLE IF NOT EXISTS production_plans (
    order_id TEXT PRIMARY KEY REFERENCES orders(id),
    note TEXT NOT NULL DEFAULT '' CHECK(length(note) <= 1000),
    start_date TEXT CHECK(start_date IS NULL OR date(start_date) = start_date),
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','closed')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
    approved_by TEXT REFERENCES users(id),
    approved_at TEXT CHECK(approved_at IS NULL OR datetime(approved_at) IS NOT NULL),
    closed_reason TEXT CHECK(closed_reason IS NULL
        OR (closed_reason = trim(closed_reason) AND length(closed_reason) BETWEEN 1 AND 1000)),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

-- Parameter operasional satu hasil cutting (1:1 dengan cutting_runs).
CREATE TABLE IF NOT EXISTS cutting_run_details (
    run_id TEXT PRIMARY KEY REFERENCES cutting_runs(id),
    cut_date TEXT NOT NULL CHECK(date(cut_date) = cut_date),
    po_reference TEXT CHECK(po_reference IS NULL
        OR (po_reference = trim(po_reference) AND length(po_reference) BETWEEN 1 AND 160)),
    weight_kg_milli INTEGER CHECK(weight_kg_milli IS NULL OR weight_kg_milli > 0),
    calculation_policy_ref TEXT NOT NULL DEFAULT 'DEMO-20260928-1'
        CHECK(length(trim(calculation_policy_ref)) BETWEEN 1 AND 64),
    created_at TEXT NOT NULL
) STRICT;

-- Detail tiap rol kain pada satu hasil cutting.
CREATE TABLE IF NOT EXISTS cutting_run_rolls (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES cutting_runs(id),
    roll_no INTEGER NOT NULL CHECK(roll_no > 0 AND roll_no <= 1000),
    weight_kg_milli INTEGER CHECK(weight_kg_milli IS NULL OR weight_kg_milli > 0),
    sheets INTEGER CHECK(sheets IS NULL OR sheets > 0),
    note TEXT NOT NULL DEFAULT '' CHECK(length(note) <= 500),
    created_at TEXT NOT NULL,
    UNIQUE(run_id, roll_no),
    CHECK(weight_kg_milli IS NOT NULL OR sheets IS NOT NULL)
) STRICT;
CREATE INDEX IF NOT EXISTS cutting_run_rolls_run ON cutting_run_rolls(run_id, roll_no);

-- Parameter operasional per baris output (1:1 dengan movement hasil run).
-- setelan_per_lembar: jumlah potongan (pcs) per lembar — DEMO_ASSUMPTION,
-- input manual, BUKAN hasil hitung; estimasi tidak menggantikan aktual.
CREATE TABLE IF NOT EXISTS cutting_run_output_params (
    run_id TEXT NOT NULL REFERENCES cutting_runs(id),
    movement_id TEXT PRIMARY KEY REFERENCES movements(id),
    setelan_per_lembar INTEGER CHECK(setelan_per_lembar IS NULL OR setelan_per_lembar > 0),
    product_weight_gram_milli INTEGER
        CHECK(product_weight_gram_milli IS NULL OR product_weight_gram_milli > 0),
    material_used_gram_milli INTEGER
        CHECK(material_used_gram_milli IS NULL OR material_used_gram_milli > 0),
    UNIQUE(run_id, movement_id)
) STRICT;
CREATE INDEX IF NOT EXISTS cutting_run_output_params_run ON cutting_run_output_params(run_id);

-- Guard: parameter output harus merujuk movement milik run yang sama.
CREATE TRIGGER IF NOT EXISTS cutting_run_output_params_valid BEFORE INSERT ON cutting_run_output_params
WHEN NOT EXISTS(SELECT 1 FROM cutting_runs r, json_each(r.movement_ids) x
    WHERE r.id = NEW.run_id AND x.value = NEW.movement_id)
BEGIN SELECT RAISE(ABORT, 'Parameter output harus merujuk movement hasil cutting run ini'); END;

-- Immutability: koreksi hanya lewat reversal existing.
CREATE TRIGGER IF NOT EXISTS production_plans_no_update BEFORE UPDATE ON production_plans
WHEN OLD.status IS NEW.status AND OLD.revision IS NEW.revision
BEGIN SELECT RAISE(ABORT, 'Rencana hanya berubah lewat approval/closure berversi'); END;
CREATE TRIGGER IF NOT EXISTS production_plans_no_delete BEFORE DELETE ON production_plans
BEGIN SELECT RAISE(ABORT, 'Rencana tidak dapat dihapus'); END;
CREATE TRIGGER IF NOT EXISTS cutting_run_details_no_update BEFORE UPDATE ON cutting_run_details
BEGIN SELECT RAISE(ABORT, 'Immutable cutting detail'); END;
CREATE TRIGGER IF NOT EXISTS cutting_run_details_no_delete BEFORE DELETE ON cutting_run_details
BEGIN SELECT RAISE(ABORT, 'Immutable cutting detail'); END;
CREATE TRIGGER IF NOT EXISTS cutting_run_rolls_no_update BEFORE UPDATE ON cutting_run_rolls
BEGIN SELECT RAISE(ABORT, 'Immutable cutting roll'); END;
CREATE TRIGGER IF NOT EXISTS cutting_run_rolls_no_delete BEFORE DELETE ON cutting_run_rolls
BEGIN SELECT RAISE(ABORT, 'Immutable cutting roll'); END;
CREATE TRIGGER IF NOT EXISTS cutting_run_output_params_no_update BEFORE UPDATE ON cutting_run_output_params
BEGIN SELECT RAISE(ABORT, 'Immutable cutting output param'); END;
CREATE TRIGGER IF NOT EXISTS cutting_run_output_params_no_delete BEFORE DELETE ON cutting_run_output_params
BEGIN SELECT RAISE(ABORT, 'Immutable cutting output param'); END;

-- Backfill: order yang sudah ada sebelum P02 dianggap grandfathered approved
-- (mereka dibuat tanpa konsep status planning). Order baru mulai dari draft.
INSERT INTO production_plans(order_id, note, status, revision, created_by, created_at)
SELECT o.id,
       'Grandfathered: dibuat sebelum migrasi P02 (status planning belum ada).',
       'approved', 0, o.created_by, o.created_at
FROM orders o WHERE NOT EXISTS(SELECT 1 FROM production_plans p WHERE p.order_id = o.id);

PRAGMA user_version = 58;
COMMIT;
