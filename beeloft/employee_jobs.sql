-- P03 (#52): job karyawan dan realisasi.
-- Job adalah penugasan kerja ke karyawan (tidak mencatat stok — pencatatan
-- produksi tetap di sewing_jobs/sewing_job_results). Realisasi mencatat
-- kuantitas kerja untuk perhitungan upah. Approval realisasi menghasilkan
-- service charge yang menjadi SATU-SATUNYA sumber nilai untuk payroll (#55)
-- dan costing (#53); konsumen dilarang menghitung ulang dari master tarif.
--
-- remaining = target_qty_pcs - SUM(realisasi approved) - SUM(adjustments),
-- selalu derived, bukan kolom bebas.

CREATE TABLE IF NOT EXISTS p03_jobs (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES workforce_employees(id),
    sku TEXT NOT NULL,
    work_type_id TEXT NOT NULL REFERENCES service_work_types(id),
    bundle_id TEXT REFERENCES bundles(id),
    target_qty_pcs INTEGER NOT NULL CHECK (target_qty_pcs > 0),
    work_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','in_progress','done','cancelled')),
    notes TEXT,
    unit_id TEXT REFERENCES business_units(id),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX IF NOT EXISTS p03_jobs_employee ON p03_jobs(employee_id, work_date);
CREATE INDEX IF NOT EXISTS p03_jobs_bundle ON p03_jobs(bundle_id) WHERE bundle_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS p03_jobs_unit ON p03_jobs(unit_id) WHERE unit_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS p03_job_realizations (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES p03_jobs(id),
    qty_pcs INTEGER NOT NULL CHECK (qty_pcs > 0),
    work_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','submitted','approved','rejected')),
    notes TEXT,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    actor_id TEXT NOT NULL REFERENCES users(id),
    approved_by TEXT REFERENCES users(id),
    approved_at TEXT,
    reject_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX IF NOT EXISTS p03_realizations_job ON p03_job_realizations(job_id, status);

-- Charge jasa: immutable setelah dibuat. payable_qty_pcs boleh negatif
-- pada charge reversal (reversal_of_charge_id terisi) agar agregat
-- per realisasi kembali nol. Koreksi hanya via reversal bertaut
-- (p03_service_charges baru dengan reversal_of_charge_id terisi).
CREATE TABLE IF NOT EXISTS p03_service_charges (
    id TEXT PRIMARY KEY,
    source_namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_line_id TEXT NOT NULL,
    employee_id TEXT NOT NULL REFERENCES workforce_employees(id),
    sku TEXT NOT NULL,
    work_type_id TEXT NOT NULL REFERENCES service_work_types(id),
    job_id TEXT NOT NULL REFERENCES p03_jobs(id),
    realization_id TEXT NOT NULL REFERENCES p03_job_realizations(id),
    payable_qty_pcs INTEGER NOT NULL,
    rate_snapshot TEXT NOT NULL,
    template_version TEXT,
    calculation_policy_ref TEXT NOT NULL,
    final_amount_minor INTEGER NOT NULL,
    approved_at TEXT NOT NULL,
    approved_by TEXT NOT NULL REFERENCES users(id),
    reversal_of_charge_id TEXT REFERENCES p03_service_charges(id),
    consumed_by TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (source_namespace, source_id, source_line_id)
) STRICT;

CREATE INDEX IF NOT EXISTS p03_charges_employee ON p03_service_charges(employee_id, approved_at);
CREATE INDEX IF NOT EXISTS p03_charges_job ON p03_service_charges(job_id);

-- Guardrail imutabilitas: charge tidak boleh diubah/dihapus langsung.
CREATE TRIGGER IF NOT EXISTS p03_charge_no_update BEFORE UPDATE ON p03_service_charges
BEGIN
    SELECT RAISE(ABORT, 'Service charge immutable; gunakan reversal bertaut.');
END;

CREATE TRIGGER IF NOT EXISTS p03_charge_no_delete BEFORE DELETE ON p03_service_charges
BEGIN
    SELECT RAISE(ABORT, 'Service charge tidak boleh dihapus.');
END;

-- Realisasi yang sudah approved/rejected tidak boleh diubah langsung.
CREATE TRIGGER IF NOT EXISTS p03_realization_locked_update BEFORE UPDATE ON p03_job_realizations
WHEN OLD.status IN ('approved','rejected')
BEGIN
    SELECT RAISE(ABORT, 'Realisasi yang sudah final tidak dapat diubah; gunakan reversal.');
END;

PRAGMA user_version = 61;
