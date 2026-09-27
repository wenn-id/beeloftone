"""Modul DEMO presentasi Beeloft One.

ISI FILE INI SEPENUHNYA DATA SINTETIS UNTUK DEMO. Bukan bagian dari skema
produksi: tabel demo dibuat dengan CREATE TABLE IF NOT EXISTS dan TIDAK
menaikkan versi skema database (tetap schema 55). Aturan bisnis di sini
adalah aturan sementara yang disederhanakan untuk presentasi, bukan
aturan produksi.

Alur demo:
  1. Produksi : rencana -> cutting -> pengerjaan (sewing jobs) -> QC -> barang jadi/stok
  2. Payroll  : hasil pekerjaan (sewing job selesai) x tarif/lusin -> slip - kasbon
  3. Penjualan: transaksi demo -> pembayaran simulasi -> stok berkurang -> ringkasan
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from beeloft.models import (
    BundleCreate,
    CuttingRunCreate,
    EmployeeCreate,
    FinalQcRecordCreate,
    FinishedGoodsAdjustmentCreate,
    FinishedGoodsReceiptCreate,
    FinishingRecordCreate,
    MaterialCreate,
    MaterialIssue,
    MaterialReceipt,
    OrderCreate,
    ProductCreate,
    SewingJobComplete,
    SewingJobCreate,
)

DEMO_TAG = "DEMO"

# ----------------------------------------------------------------------------
# Skema tabel demo (di luar migrasi versi skema produksi)
# ----------------------------------------------------------------------------

DEMO_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS demo_piece_tariffs(
  job_type TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  rate_per_lusin INTEGER NOT NULL CHECK(rate_per_lusin >= 0)
);
CREATE TABLE IF NOT EXISTS demo_job_tariffs(
  sewing_job_id TEXT PRIMARY KEY REFERENCES sewing_jobs(id),
  job_type TEXT NOT NULL REFERENCES demo_piece_tariffs(job_type)
);
CREATE TABLE IF NOT EXISTS demo_kasbon(
  employee_name TEXT PRIMARY KEY,
  amount INTEGER NOT NULL DEFAULT 0 CHECK(amount >= 0),
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS demo_kasbon_payments(
  id TEXT PRIMARY KEY,
  employee_name TEXT NOT NULL,
  amount INTEGER NOT NULL CHECK(amount > 0),
  paid_at TEXT NOT NULL,
  actor_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS demo_sales(
  id TEXT PRIMARY KEY,
  reference TEXT NOT NULL,
  product_id TEXT NOT NULL REFERENCES products(id),
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  price_each INTEGER NOT NULL CHECK(price_each >= 0),
  payment_method TEXT NOT NULL,
  adjustment_id TEXT,
  sold_at TEXT NOT NULL,
  actor_id TEXT,
  created_at TEXT NOT NULL
);
"""


def ensure_demo_tables(db):
    db.executescript(DEMO_TABLES_SQL)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _dump(model):
    return model.model_dump(mode="json")


# ----------------------------------------------------------------------------
# Seed: skenario demo yang konsisten ujung ke ujung
# ----------------------------------------------------------------------------
#
# Angka-angka (semua sintetis):
#   Order DEMO-PROD-001: 1.200 pcs Kemeja Flanel Demo
#   Sewing : Sari  480 pcs obras  (40 lusin x Rp1.800  = Rp72.000)
#            Budi  360 pcs jahit  (30 lusin x Rp2.500  = Rp75.000)
#            Dewi  360 pcs jahit  (30 lusin x Rp2.500  = Rp75.000)
#            Total 1.200 pcs = 100 lusin, bruto Rp222.000
#   Kasbon : Budi Rp30.000 -> netto Budi Rp45.000, total netto Rp192.000
#   QC     : 1.180 pcs lolos -> stok gudang 1.180 pcs
#   Jual   : 150 pcs x Rp85.000 = Rp12.750.000 -> stok 1.030 pcs

DEMO_TARIFFS = [
    ("obras", "Obras", 1800),
    ("jahit", "Jahit", 2500),
]

DEMO_WORKERS = [
    # (code, name, job_type, bundle_qty, tariff_label)
    ("DEMO-SARI", "Sari", "obras", 480),
    ("DEMO-BUDI", "Budi", "jahit", 360),
    ("DEMO-DEWI", "Dewi", "jahit", 360),
]

DEMO_QC_PASS = {"Sari": 480, "Budi": 360, "Dewi": 340}  # 20 pcs reject QC (Dewi)


def seed_demo_story(store, actor):
    """Membangun seluruh skenario demo dari nol memakai API store yang asli."""
    with store.transaction() as db:
        ensure_demo_tables(db)
    key = lambda slug: f"demo-seed-{slug}"  # noqa: E731
    today = date.today()

    # 1. Bahan baku (langsung terima sebagai batch; tanpa rantai PO untuk demo)
    material = store.create_material(
        _dump(MaterialCreate(code="KAIN-DEMO", name="Kain Demo Flanel", unit="m")),
        actor, key("material"))
    batch = store.receive_material(
        _dump(MaterialReceipt(material_id=material["id"], reference="DEMO-BATCH-KAIN-001",
                              quantity="500.000", location="GUDANG-DEMO",
                              received_date=today, supplier="Supplier Demo",
                              reason="Stok awal demo")),
        actor, key("batch"))

    # 2. Karyawan demo
    for code, name, _job, _qty in DEMO_WORKERS:
        store.create_employee(
            _dump(EmployeeCreate(code=code, name=name, department="Produksi",
                                 reason="Karyawan demo")),
            actor, key(f"emp-{code}"))

    # 3. Produk + order produksi
    product = store.create_product(
        _dump(ProductCreate(sku="DEMO-KMF-001", name="Kemeja Flanel Demo",
                            color="Flanel", size="M")),
        actor, key("product"))
    order = store.create_order(
        _dump(OrderCreate(reference="DEMO-PROD-001", title="DEMO - Produksi 1.200 pcs",
                          owner_id=actor["id"], due_date=today,
                          lines=[{"product_id": product["id"], "quantity": 1200}])),
        actor, key("order"))
    line_id = order["lines"][0]["id"]

    # 4. Rencana -> cutting, lalu issue bahan -> cutting run (1200 pcs cutting->sewing otomatis)
    store.move({"line_id": line_id, "from_stage": "planned", "to_stage": "cutting",
                "quantity": 1200, "reason": "Mulai cutting demo"},
               actor, key("move-cutting"))
    issue = store.issue_material(
        _dump(MaterialIssue(batch_id=batch["id"], order_id=order["id"],
                             quantity="310.000", reason="Cutting demo 1.200 pcs")),
        actor, key("issue"))
    run = store.create_cutting_run(
        order["id"],
        _dump(CuttingRunCreate(issue_id=issue["id"], used="300.000", waste="10.000",
                               outputs=[{"line_id": line_id, "quantity": 1200}],
                               reference="DEMO-CUT-001", reason="Cutting demo")),
        actor, key("cutting"))
    output_id = run["outputs"][0]["id"]

    # 5. Tarif borongan demo
    with store.transaction() as db:
        ensure_demo_tables(db)
        for job_type, label, rate in DEMO_TARIFFS:
            db.execute("INSERT OR REPLACE INTO demo_piece_tariffs(job_type,label,rate_per_lusin)"
                       " VALUES(?,?,?)", (job_type, label, rate))
        db.execute("INSERT OR REPLACE INTO demo_kasbon(employee_name,amount,note)"
                   " VALUES(?,?,?)", ("Budi", 30000, "Kasbon demo untuk ilustrasi potongan"))

    # 6. Bundle -> sewing job -> selesai -> finishing -> QC -> barang jadi
    for index, (code, name, job_type, qty) in enumerate(DEMO_WORKERS):
        rate = next(r for t, _l, r in DEMO_TARIFFS if t == job_type)
        wage = qty * rate // 12  # selalu habis dibagi untuk angka demo
        bundle = store.create_bundle(
            run["id"],
            _dump(BundleCreate(reference=f"DEMO-BND-00{index + 1}",
                               output_movement_id=output_id, quantity=qty,
                               reason="Bundle demo")),
            actor, key(f"bundle-{index}"))
        job = store.create_sewing_job(
            bundle["id"],
            _dump(SewingJobCreate(reference=f"DEMO-SEW-00{index + 1}",
                                  assignment_type="internal", assignee=name,
                                  quantity_out=qty, cost=f"{wage}.00",
                                  sent_date=today, reason="Borongan demo")),
            actor, key(f"sew-{index}"))
        with store.transaction() as db:
            ensure_demo_tables(db)
            db.execute("INSERT OR REPLACE INTO demo_job_tariffs(sewing_job_id,job_type)"
                       " VALUES(?,?)", (job["id"], job_type))
        store.complete_sewing_job(
            job["id"],
            _dump(SewingJobComplete(completed_quantity=qty, defect_quantity=0,
                                    missing_quantity=0, returned_date=today,
                                    reason="Selesai demo")),
            actor, key(f"sew-done-{index}"))
        finishing = store.create_finishing_record(
            job["id"],
            _dump(FinishingRecordCreate(reference=f"DEMO-FIN-00{index + 1}", quantity=qty,
                                        thread_trimmed=True, ironed=True,
                                        labels_attached=True, hangtags_attached=True,
                                        packaged=True, completed_date=today,
                                        reason="Finishing demo")),
            actor, key(f"fin-{index}"))
        passed = DEMO_QC_PASS[name]
        rejected = qty - passed
        qc = store.create_final_qc_record(
            finishing["id"],
            _dump(FinalQcRecordCreate(
                reference=f"DEMO-QC-00{index + 1}", measurement_notes="Sesuai demo",
                visual_notes="OK demo",
                defect_type="Tidak ada" if not rejected else "Jahitan demo",
                responsible_source="QC demo", disposition="Lolos demo",
                accepted_quantity=passed, rework_quantity=0, reject_quantity=rejected,
                inspection_date=today, reason="QC demo")),
            actor, key(f"qc-{index}"))
        if passed:
            store.create_finished_goods_receipt(
                qc["id"],
                _dump(FinishedGoodsReceiptCreate(
                    reference=f"DEMO-FG-00{index + 1}", scanned_sku=product["sku"],
                    location="GUDANG-DEMO", sellable_quantity=passed, hold_quantity=0,
                    received_date=today, reason="Penerimaan demo")),
                actor, key(f"fg-{index}"))

    return {"order_id": order["id"], "product_id": product["id"]}


# ----------------------------------------------------------------------------
# Payroll demo: hasil pekerjaan x tarif -> slip - kasbon
# ----------------------------------------------------------------------------

def payroll_summary(store):
    with store.transaction() as db:
        ensure_demo_tables(db)
        tariffs = {r["job_type"]: (r["label"], r["rate_per_lusin"])
                   for r in db.execute("SELECT job_type,label,rate_per_lusin FROM demo_piece_tariffs")}
        jobs = db.execute("""
            SELECT j.id, j.assignee, j.quantity_out, r.completed_quantity,
                   t.job_type
            FROM sewing_jobs j
            JOIN sewing_job_results r ON r.job_id = j.id
            LEFT JOIN demo_job_tariffs t ON t.sewing_job_id = j.id
            WHERE NOT EXISTS (SELECT 1 FROM sewing_job_reversals x WHERE x.job_id = j.id)
              AND j.reference LIKE 'DEMO-%'
            ORDER BY j.created_at""").fetchall()
        kasbon = {r["employee_name"]: r["amount"]
                  for r in db.execute("SELECT employee_name, amount FROM demo_kasbon")}
        paid = {}
        for r in db.execute("SELECT employee_name, COALESCE(SUM(amount),0) AS paid"
                            " FROM demo_kasbon_payments GROUP BY employee_name"):
            paid[r["employee_name"]] = r["paid"]

    workers = {}
    for j in jobs:
        name = j["assignee"]
        w = workers.setdefault(name, {"name": name, "jobs": [], "pcs": 0,
                                      "gross": 0, "lines": []})
        pcs = j["completed_quantity"] or 0
        job_type = j["job_type"]
        if job_type and job_type in tariffs:
            label, rate = tariffs[job_type]
            lusin = Decimal(pcs) / Decimal(12)
            wage = int((lusin * Decimal(rate)).to_integral_value())
        else:
            label, rate, lusin, wage = "-", 0, Decimal(0), 0
        w["jobs"].append(j["id"])
        w["pcs"] += pcs
        w["gross"] += wage
        w["lines"].append({"job_type": job_type or "-", "label": label,
                           "pcs": pcs, "lusin": format(lusin.normalize(), "f"),
                           "rate_per_lusin": rate, "wage": wage})
    result = []
    for name, w in workers.items():
        kb = kasbon.get(name, 0)
        already = paid.get(name, 0)
        outstanding = max(kb - already, 0)
        result.append({**w, "kasbon": kb, "kasbon_paid": already,
                       "kasbon_outstanding": outstanding, "net": w["gross"] - outstanding})
    total = {"pcs": sum(w["pcs"] for w in result),
             "gross": sum(w["gross"] for w in result),
             "kasbon": sum(w["kasbon_outstanding"] for w in result),
             "net": sum(w["net"] for w in result)}
    return {"tariffs": [{"job_type": t, "label": l, "rate_per_lusin": r}
                        for t, (l, r) in tariffs.items()],
            "workers": result, "total": total}


def record_kasbon_payment(store, payload, actor, key):
    def perform(db):
        ensure_demo_tables(db)
        row = db.execute("SELECT amount FROM demo_kasbon WHERE employee_name=?",
                         (payload["employee_name"],)).fetchone()
        if not row:
            from beeloft.store import DomainError
            raise DomainError(404, "Kasbon demo untuk nama tersebut tidak ada.")
        already = db.execute("SELECT COALESCE(SUM(amount),0) AS s FROM demo_kasbon_payments"
                             " WHERE employee_name=?", (payload["employee_name"],)).fetchone()["s"]
        if payload["amount"] <= 0 or payload["amount"] > row["amount"] - already:
            from beeloft.store import DomainError
            raise DomainError(422, "Nominal pembayaran kasbon melebihi sisa.")
        pid = str(uuid4())
        db.execute("INSERT INTO demo_kasbon_payments(id,employee_name,amount,paid_at,actor_id,created_at)"
                   " VALUES(?,?,?,?,?,?)",
                   (pid, payload["employee_name"], payload["amount"],
                    payload["paid_at"], actor["id"], now_iso()))
        return {"id": pid, "employee_name": payload["employee_name"],
                "amount": payload["amount"]}
    return store._write(actor, ("admin", "operator"), key,
                        "demo-kasbon:" + payload["employee_name"], payload, perform)


# ----------------------------------------------------------------------------
# Penjualan demo: transaksi -> pembayaran simulasi -> stok berkurang
# ----------------------------------------------------------------------------

def _receipt_sellable(db, product_id):
    rows = db.execute("""
        WITH rp AS (
          SELECT x.id, x.location, x.sellable_quantity
          FROM finished_goods_receipts x
          JOIN final_qc_records q ON q.id = x.final_qc_record_id
          JOIN finishing_records f ON f.id = q.finishing_record_id
          JOIN sewing_jobs j ON j.id = f.job_id
          JOIN bundles b ON b.id = j.bundle_id
          JOIN movements m ON m.id = b.output_movement_id
          JOIN order_lines l ON l.id = m.line_id
          WHERE l.product_id = ?
            AND NOT EXISTS (SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id = x.id)
        )
        SELECT rp.id AS receipt_id, rp.location,
               rp.sellable_quantity
               + COALESCE((SELECT SUM(CASE WHEN w.to_status='sellable' THEN w.quantity
                                          WHEN w.from_status='sellable' THEN -w.quantity ELSE 0 END)
                           FROM warehouse_movements w WHERE w.receipt_id = rp.id
                             AND NOT EXISTS (SELECT 1 FROM warehouse_movement_reversals r
                                             WHERE r.movement_id = w.id)), 0)
               + COALESCE((SELECT SUM(a.quantity_delta) FROM finished_goods_adjustments a
                           WHERE a.receipt_id = rp.id AND a.stock_status = 'sellable'
                             AND NOT EXISTS (SELECT 1 FROM finished_goods_adjustment_reversals r
                                             WHERE r.adjustment_id = a.id)), 0)
               AS sellable
        FROM rp ORDER BY sellable DESC""", (product_id,)).fetchall()
    return [dict(r) for r in rows]


def create_demo_sale(store, payload, actor, key):
    """Catat penjualan demo: kurangi stok via adjustment + simpan transaksi demo."""
    def perform(db):
        ensure_demo_tables(db)
        from beeloft.store import DomainError
        buckets = [b for b in _receipt_sellable(db, payload["product_id"]) if b["sellable"] > 0]
        need = payload["quantity"]
        if sum(b["sellable"] for b in buckets) < need:
            raise DomainError(409, "Stok demo tidak cukup untuk penjualan ini.")
        sale_id = str(uuid4())
        ref = payload.get("reference") or f"DEMO-POS-{sale_id[:8].upper()}"
        remaining, adj_ids = need, []
        for b in buckets:
            if remaining <= 0:
                break
            take = min(b["sellable"], remaining)
            adj = store.create_finished_goods_adjustment(
                b["receipt_id"],
                {"reference": ref, "location": b["location"], "stock_status": "sellable",
                 "quantity_delta": -take, "adjusted_date": payload["sold_at"],
                 "reason": f"Penjualan demo {ref} (simulasi pembayaran: {payload['payment_method']})"},
                actor, key + ":adj:" + b["receipt_id"])
            adj_ids.append(adj["id"])
            remaining -= take
        db.execute("INSERT INTO demo_sales(id,reference,product_id,quantity,price_each,"
                   "payment_method,adjustment_id,sold_at,actor_id,created_at)"
                   " VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (sale_id, ref, payload["product_id"], need, payload["price_each"],
                    payload["payment_method"], ",".join(adj_ids), payload["sold_at"],
                    actor["id"], now_iso()))
        return {"id": sale_id, "reference": ref, "quantity": need,
                "total": need * payload["price_each"],
                "payment_method": payload["payment_method"]}
    return store._write(actor, ("admin", "operator"), key,
                        "demo-sale:" + payload["product_id"], payload, perform)


def sales_summary(store):
    with store.transaction() as db:
        ensure_demo_tables(db)
        rows = db.execute("""
            SELECT s.id, s.reference, s.quantity, s.price_each,
                   s.quantity * s.price_each AS total,
                   s.payment_method, s.sold_at, p.sku, p.name
            FROM demo_sales s JOIN products p ON p.id = s.product_id
            ORDER BY s.sold_at DESC, s.created_at DESC""").fetchall()
        sales = [dict(r) for r in rows]
    return {"sales": sales,
            "total": {"transactions": len(sales),
                      "pcs": sum(s["quantity"] for s in sales),
                      "revenue": sum(s["total"] for s in sales)}}


def demo_overview(store):
    """Satu payload untuk halaman demo: funnel produksi + payroll + penjualan + stok."""
    with store.transaction() as db:
        order = db.execute(
            "SELECT id, reference, title FROM orders WHERE reference='DEMO-PROD-001'").fetchone()
        funnel = []
        if order:
            planned = db.execute(
                "SELECT COALESCE(SUM(quantity),0) FROM order_lines WHERE order_id=?",
                (order["id"],)).fetchone()[0] or 0
            funnel = [{"stage": "planned", "qty": planned}]
            rows = db.execute("""
                SELECT m.to_stage AS stage, COALESCE(SUM(m.quantity),0) AS qty
                FROM movements m JOIN order_lines l ON l.id = m.line_id
                WHERE l.order_id = ? AND m.reversal_of IS NULL
                GROUP BY m.to_stage""", (order["id"],)).fetchall()
            funnel += [{"stage": r["stage"], "qty": r["qty"]} for r in rows]
    payroll = payroll_summary(store)
    sales = sales_summary(store)
    inv = store.finished_goods_inventory(limit=50)
    demo_inv = [r for r in inv if r.get("sku", "").startswith("DEMO-")]
    return {"order": dict(order) if order else None, "funnel": funnel,
            "payroll": payroll, "sales": sales, "inventory": demo_inv}
