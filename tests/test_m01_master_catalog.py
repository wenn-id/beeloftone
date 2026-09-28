"""Focused tests for M01 issue #43: master katalog produk, bahan, satuan.

Covers: migrasi 55->56 tanpa mengubah identitas/histori, PCS-only dengan
lusin sebagai tampilan turunan eksak (F02), validasi hierarki + kode unik,
nonaktif memblokir transaksi baru tanpa merusak riwayat, harga referensi
independen dari harga aktual PO, template BOM berversi + optimistic lock,
serta batasan izin admin/operator/viewer.
"""
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4
import unittest

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store
from beeloft.contracts import pcs_to_lusin, lusin_to_pcs


class Migration56Test(unittest.TestCase):
    def fresh_store(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        store = Store(str(Path(folder.name) / "m01.sqlite3"))
        db = store.connect()
        # WAL sidecar harus di-checkpoint dan koneksi ditutup sebelum folder
        # sementara dihapus, kalau tidak Windows mengunci -wal/-shm.
        self.addCleanup(db.close)
        self.addCleanup(lambda: db.execute("PRAGMA wal_checkpoint(TRUNCATE)"))
        return store

    def db_version(self, store):
        with store.transaction() as db:
            return db.execute("PRAGMA user_version").fetchone()[0]

    def test_fresh_db_reaches_schema_56_with_uom_seeds(self):
        store = self.fresh_store()
        self.assertEqual(self.db_version(store), 62)
        with store.transaction() as db:
            codes = [r[0] for r in db.execute("SELECT code FROM uoms ORDER BY code")]
        self.assertEqual(codes, ["KG", "LSN", "M", "PCS"])

    def test_upgrade_55_to_56_preserves_identity_and_history(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = str(Path(folder.name) / "legacy.sqlite3")
        # Bangun DB skema-55 langsung via sqlite3 tanpa menjalankan migrasi store.
        # Tabel yang di-ALTER migrasi berikutnya (suppliers/workforce/sewing/PO) harus
        # ada, sebagaimana pada DB skema-55 sungguhan; sisnya tetap minimal.
        raw = sqlite3.connect(path)
        raw.executescript("""
            CREATE TABLE users(id TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1,
                role TEXT NOT NULL DEFAULT 'admin');
            CREATE TABLE products(id TEXT PRIMARY KEY, sku TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '', size TEXT NOT NULL DEFAULT '',
                created_by TEXT, created_at TEXT NOT NULL);
            CREATE TABLE materials(id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL, unit TEXT NOT NULL CHECK(unit IN ('m','kg','pcs')),
                created_by TEXT, created_at TEXT NOT NULL);
            CREATE TABLE suppliers(id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, contact TEXT NOT NULL, address TEXT NOT NULL,
                reason TEXT NOT NULL, actor_id TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE workforce_employees(id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE);
            CREATE TABLE workforce_employee_events(id TEXT PRIMARY KEY, employee_id TEXT NOT NULL);
            CREATE TABLE sewing_jobs(id TEXT PRIMARY KEY);
            CREATE TABLE purchase_orders(id TEXT PRIMARY KEY, supplier_id TEXT, lines TEXT);
            -- B01 (#50): ALTER TABLE ... RENAME pada migrasi 62 memaksa SQLite
            -- memvalidasi ulang SEMUA trigger di schema; trigger P02
            -- cutting_run_output_params_valid merujuk cutting_runs (dibuat
            -- cutting.sql, migrasi lama < 55) sehingga tabel minimalnya
            -- harus ada di DB sintetis ini.
            CREATE TABLE cutting_runs(id TEXT PRIMARY KEY, movement_ids TEXT NOT NULL);
            -- B01 (#50): migrasi 62 me-rebuild supplier_payment_requests, jadi
            -- bentuk pre-B01-nya harus ada di DB minimal ini.
            CREATE TABLE supplier_payment_requests(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                reference TEXT NOT NULL UNIQUE CHECK(length(trim(reference)) BETWEEN 1 AND 160),
                purchase_order_id TEXT NOT NULL REFERENCES purchase_orders(id),
                invoice_reference TEXT NOT NULL CHECK(length(trim(invoice_reference)) BETWEEN 1 AND 160),
                invoice_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                amount_minor INTEGER NOT NULL CHECK(amount_minor BETWEEN 1 AND 100000000000000),
                reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
                actor_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL,
                UNIQUE(purchase_order_id,invoice_reference),
                CHECK(invoice_date<=due_date)
            ) STRICT;
            -- B01 (#50): trigger yang dibuat ulang migrasi 62 menempel pada
            -- supplier_payment_request_events (dibuat supplier_payment_approvals.sql,
            -- migrasi lama < 55); tabel minimalnya harus ada.
            CREATE TABLE supplier_payment_request_events(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL REFERENCES supplier_payment_requests(id),
                status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
                reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
                actor_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            ) STRICT;
            -- B01 (#50) lanjutan: trigger yang dibuat ulang migrasi 62 merujuk
            -- tabel/view lama lain (dibuat migrasi < 55). ALTER TABLE ... RENAME
            -- pada migrasi 62 memaksa SQLite memvalidasi ulang seluruh trigger,
            -- jadi bentuk minimalnya harus ada di DB sintetis ini.
            CREATE TABLE purchase_order_approval_events(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE purchase_order_cancellations(order_id TEXT PRIMARY KEY);
            CREATE TABLE purchase_order_receipts(
                purchase_order_id TEXT NOT NULL, batch_id TEXT NOT NULL);
            CREATE TABLE material_batches(id TEXT PRIMARY KEY, material_id TEXT NOT NULL);
            CREATE TABLE material_movements(id TEXT PRIMARY KEY, batch_id TEXT NOT NULL,
                kind TEXT NOT NULL, reversal_of TEXT, quantity_milli INTEGER NOT NULL DEFAULT 0);
            CREATE VIEW supplier_payment_po_received AS
            SELECT p.id AS purchase_order_id,COALESCE(SUM(CAST((
                COALESCE((SELECT SUM(m.quantity_milli) FROM purchase_order_receipts x
                    JOIN material_batches b ON b.id=x.batch_id
                    JOIN material_movements m ON m.batch_id=b.id AND m.kind='receipt'
                    WHERE x.purchase_order_id=p.id
                      AND b.material_id=json_extract(line.value,'$.material_id')
                      AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id)),0)
                *CAST(ROUND(CAST(json_extract(line.value,'$.unit_price') AS NUMERIC)*100) AS INTEGER)+500
                )/1000 AS INTEGER)),0) AS received_value_minor
            FROM purchase_orders p,json_each(p.lines) line GROUP BY p.id;
            CREATE TABLE positions(id TEXT PRIMARY KEY);
            CREATE TABLE business_units(id TEXT PRIMARY KEY);
        """)
        raw.execute("PRAGMA user_version = 55")
        raw.execute(
            "INSERT INTO products(id,sku,name,color,size,created_at) VALUES(?,?,?,?,?,?)",
            ("p-legacy", "SKU-LAMA", "Kemeja Lama", "Biru", "L", "2025-01-01T00:00:00+00:00"))
        raw.execute(
            "INSERT INTO materials(id,code,name,unit,created_at) VALUES(?,?,?,?,?)",
            ("m-legacy", "BHN-001", "Kain Katun", "m", "2025-01-01T00:00:00+00:00"))
        raw.commit()
        raw.close()

        upgraded = Store(path)
        conn = upgraded.connect()
        self.addCleanup(conn.close)
        self.addCleanup(lambda: conn.execute("PRAGMA wal_checkpoint(TRUNCATE)"))
        self.assertEqual(self.db_version(upgraded), 62)
        with upgraded.transaction() as db:
            prod = db.execute("SELECT sku,name,color,size,uom_code,active FROM products WHERE id='p-legacy'").fetchone()
            mat = db.execute(
                "SELECT code,name,unit,active,reference_price_minor FROM materials WHERE id='m-legacy'").fetchone()
        self.assertEqual(tuple(prod), ("SKU-LAMA", "Kemeja Lama", "Biru", "L", "PCS", 1))
        self.assertEqual(tuple(mat), ("BHN-001", "Kain Katun", "m", 1, None))


class PcsOnlyTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app = create_app(Path(self.folder.name) / "test.sqlite3")
        self.client = TestClient(self.app)
        self.admin = self.app.state.store.provision_user("Pemilik", "admin")
        self.client.headers["X-API-Key"] = self.admin["api_key"]

    def post(self, path, body, status=201):
        r = self.client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def test_lusin_rejected_product_uom_must_be_pcs(self):
        self.post("/api/products", {"sku": "LSN-1", "name": "X", "uom_code": "LSN"}, status=422)

    def test_unknown_uom_rejected(self):
        self.post("/api/products", {"sku": "XX-1", "name": "X", "uom_code": "XX"}, status=404)

    def test_default_uom_is_pcs(self):
        self.assertEqual(self.post("/api/products", {"sku": "PCS-1", "name": "X"})["uom_code"], "PCS")

    def test_lusin_is_exact_display_derivative(self):
        lusin = pcs_to_lusin(13)
        self.assertEqual((lusin.numerator, lusin.denominator), (13, 12))
        self.assertEqual(lusin_to_pcs(lusin), 13)


class ClassificationTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app = create_app(Path(self.folder.name) / "test.sqlite3")
        self.client = TestClient(self.app)
        self.admin = self.app.state.store.provision_user("Pemilik", "admin")
        self.client.headers["X-API-Key"] = self.admin["api_key"]
        self.cat_a = self.post("/api/catalog/product-categories", {"code": "CA", "name": "Cat A"})
        self.cat_b = self.post("/api/catalog/product-categories", {"code": "CB", "name": "Cat B"})
        self.sub_a = self.post("/api/catalog/product-subcategories",
                               {"code": "SA", "name": "Sub A", "category_id": self.cat_a["id"]})

    def post(self, path, body, status=201):
        r = self.client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def test_subcategory_must_belong_to_category(self):
        self.post("/api/products", {"sku": "H-1", "name": "H",
                                    "category_id": self.cat_b["id"],
                                    "subcategory_id": self.sub_a["id"]}, status=422)

    def test_type_requires_subcategory(self):
        typ = self.post("/api/catalog/product-types",
                        {"code": "T1", "name": "Tipe 1", "subcategory_id": self.sub_a["id"]})
        self.post("/api/products", {"sku": "H-2", "name": "H", "type_id": typ["id"]}, status=422)

    def test_duplicate_sku_case_insensitive(self):
        self.post("/api/products", {"sku": "DUP-1", "name": "A"})
        self.post("/api/products", {"sku": "dup-1", "name": "B"}, status=409)

    def test_material_class_level_hierarchy(self):
        lvl1 = self.post("/api/catalog/material-classes", {"code": "MC1", "name": "L1", "level": 1})
        self.post("/api/catalog/material-classes",
                  {"code": "MC2", "name": "L2", "level": 2, "parent_id": lvl1["id"]})
        # level 2 tanpa parent -> 422
        self.post("/api/catalog/material-classes",
                  {"code": "MC3", "name": "L2X", "level": 2}, status=422)


class DeactivationTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app = create_app(Path(self.folder.name) / "test.sqlite3")
        self.client = TestClient(self.app)
        self.admin = self.app.state.store.provision_user("Pemilik", "admin")
        self.operator = self.app.state.store.provision_user("Ops", "operator")
        self.client.headers["X-API-Key"] = self.admin["api_key"]

    def post(self, path, body, status=201, api_key=None):
        headers = {"Idempotency-Key": str(uuid4())}
        if api_key:
            headers["X-API-Key"] = api_key
        r = self.client.post(path, json=body, headers=headers)
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def order(self, product_id, status=201):
        return self.post("/api/orders", {"reference": "PROD-" + str(uuid4())[:8], "title": "T",
                                        "owner_id": self.operator["id"], "due_date": "2026-12-01",
                                        "lines": [{"product_id": product_id, "quantity": 12}]},
                         status=status)

    def test_deactivation_blocks_new_order_but_keeps_history(self):
        p = self.post("/api/products", {"sku": "D-1", "name": "D"})
        order = self.order(p["id"])
        self.post(f"/api/products/{p['id']}/changes", {"active": False}, status=200)
        self.order(p["id"], status=422)
        # Riwayat tetap terbaca
        detail = self.client.get(f"/api/orders/{order['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["lines"][0]["product_id"], p["id"])

    def test_name_edit_allowed_with_inactive_classification(self):
        cat = self.post("/api/catalog/product-categories", {"code": "CX", "name": "Cat X"})
        p = self.post("/api/products", {"sku": "D-2", "name": "D", "category_id": cat["id"]})
        self.post(f"/api/catalog/product-categories/{cat['id']}/changes", {"active": False}, status=200)
        updated = self.post(f"/api/products/{p['id']}/changes", {"name": "D Baru"}, status=200)
        self.assertEqual(updated["name"], "D Baru")
        self.assertEqual(updated["category_name"], "Cat X")
        # Referensi baru ke klasifikasi nonaktif tetap ditolak
        self.post("/api/products", {"sku": "D-3", "name": "D", "category_id": cat["id"]}, status=422)

    def test_operator_cannot_write_catalog(self):
        r = self.client.post("/api/catalog/colors", json={"code": "C1", "name": "C1"},
                             headers={"Idempotency-Key": str(uuid4()),
                                      "X-API-Key": self.operator["api_key"]})
        self.assertEqual(r.status_code, 403)


class ReferencePriceTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app = create_app(Path(self.folder.name) / "test.sqlite3")
        self.client = TestClient(self.app)
        self.admin = self.app.state.store.provision_user("Pemilik", "admin")
        self.operator = self.app.state.store.provision_user("Ops", "operator")
        self.client.headers["X-API-Key"] = self.admin["api_key"]

    def post(self, path, body, status=201):
        r = self.client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def test_reference_price_stored_as_minor_and_displayed(self):
        m = self.post("/api/materials", {"code": "RP-1", "name": "Bahan", "unit": "kg",
                                         "reference_price": "15000.50"})
        self.assertEqual(m["reference_price"], "15000.50")
        with self.app.state.store.transaction() as db:
            row = db.execute(
                "SELECT reference_price_minor FROM materials WHERE id=?", (m["id"],)).fetchone()
        self.assertEqual(row[0], 1500050)

    def test_reference_price_independent_from_actual_price_history(self):
        m = self.post("/api/materials", {"code": "RP-2", "name": "Bahan", "unit": "pcs",
                                         "reference_price": "10000.00"})
        # Harga referensi bukan harga aktual: tidak muncul di price insights
        # yang hanya membaca PO yang sudah di-approve.
        insights = self.client.get("/api/material-price-insights?query=RP-2").json()["items"]
        self.assertFalse([i for i in insights if i["material_id"] == m["id"]])
        # Mengubah harga referensi tidak menyentuh histori harga aktual.
        self.post(f"/api/materials/{m['id']}/changes", {"reference_price": "11000.00"}, status=200)
        insights = self.client.get("/api/material-price-insights?query=RP-2").json()["items"]
        self.assertFalse([i for i in insights if i["material_id"] == m["id"]])
        listed = [x for x in self.client.get("/api/materials").json() if x["id"] == m["id"]][0]
        self.assertEqual(listed["reference_price"], "11000.00")


class BomTemplateTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.app = create_app(Path(self.folder.name) / "test.sqlite3")
        self.client = TestClient(self.app)
        self.admin = self.app.state.store.provision_user("Pemilik", "admin")
        self.client.headers["X-API-Key"] = self.admin["api_key"]
        self.mat = self.post("/api/materials", {"code": "BT-1", "name": "Bahan", "unit": "pcs"})
        self.sku = self.post("/api/products", {"sku": "BT-SKU", "name": "SKU"})

    def post(self, path, body, status=201):
        r = self.client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def template(self, **changes):
        body = {"code": "TMPL-" + str(uuid4())[:8], "name": "T",
                "components": [{"material_id": self.mat["id"], "quantity": "2"}]}
        body.update(changes)
        return self.post("/api/bom-templates", body)

    def apply(self, template_id, product_id, revision=0, status=200):
        r = self.client.post(f"/api/bom-templates/{template_id}/apply",
                             json={"product_id": product_id, "reason": "uji",
                                   "expected_revision": revision},
                             headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def test_apply_publishes_revision_and_optimistic_lock(self):
        t = self.template()
        first = self.apply(t["id"], self.sku["id"])
        self.assertEqual(first["revision"], 1)
        # expected_revision basi -> konflik
        self.apply(t["id"], self.sku["id"], revision=0, status=409)
        # Apply identik dengan revisi terkini -> ditolak sebagai no-op
        self.apply(t["id"], self.sku["id"], revision=1, status=409)
        # Template berbeda menerbitkan revisi berikutnya
        t2 = self.template(components=[{"material_id": self.mat["id"], "quantity": "3"}])
        second = self.apply(t2["id"], self.sku["id"], revision=1)
        self.assertEqual(second["revision"], 2)

    def test_template_type_binding_enforced(self):
        cat = self.post("/api/catalog/product-categories", {"code": "TC", "name": "TC"})
        sub = self.post("/api/catalog/product-subcategories",
                        {"code": "TS", "name": "TS", "category_id": cat["id"]})
        typ = self.post("/api/catalog/product-types",
                        {"code": "TT", "name": "TT", "subcategory_id": sub["id"]})
        t = self.template(product_type_id=typ["id"])
        self.apply(t["id"], self.sku["id"], status=422)  # SKU tanpa tipe
        typed = self.post("/api/products", {"sku": "BT-TYPED", "name": "X",
                                            "category_id": cat["id"],
                                            "subcategory_id": sub["id"], "type_id": typ["id"]})
        self.assertEqual(self.apply(t["id"], typed["id"])["revision"], 1)

    def test_inactive_material_rejected_in_new_template(self):
        self.post(f"/api/materials/{self.mat['id']}/changes", {"active": False}, status=200)
        self.post("/api/bom-templates",
                  {"code": "TMPL-X", "name": "X",
                   "components": [{"material_id": self.mat["id"], "quantity": "1"}]},
                  status=422)

    def test_inactive_material_rejected_in_direct_bom_save(self):
        self.post(f"/api/materials/{self.mat['id']}/changes", {"active": False}, status=200)
        self.post(f"/api/products/{self.sku['id']}/bom",
                  {"components": [{"material_id": self.mat["id"], "quantity": "1"}],
                   "reason": "uji", "expected_revision": 0}, status=422)


if __name__ == "__main__":
    unittest.main()
