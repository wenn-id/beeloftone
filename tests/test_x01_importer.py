"""X01 (#51): kontrak impor dan dry-run importer.

Cakupan: kontrak CSV murni (import_contracts), metadata job schema 63,
dry-run tanpa efek domain, apply per-batch atomik lewat service domain,
idempotency, guard produksi, permission import_data, dan domain yang belum
tersedia (UNSUPPORTED/NOT_READY). Seluruh fixture sintetis.
"""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from beeloft import import_contracts as ic
from beeloft.api import create_app
from beeloft.store import DomainError, Store

CAT_HEADER = "source_id,source_line_id,source_revision,row_kind,code,name"
CFG = {"source_system": "legacy", "source_account": "backoffice",
       "strategy": "active_only"}


def cat_csv(*rows):
    return CAT_HEADER + "\n" + "\n".join(rows)


class ImportContractTest(TestCase):
    def test_contract_version_tagged(self):
        self.assertTrue(ic.IMPORT_CONTRACT_VERSION.startswith("X01-"))

    def test_unknown_adapter_rejected(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.get_adapter("adapter_tidak_ada")
        self.assertEqual(ctx.exception.reason, "unknown_adapter")

    def test_unsupported_payroll_reports_owner(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.get_adapter("payroll")
        self.assertEqual(ctx.exception.reason, "unknown_adapter")
        self.assertIn("UNSUPPORTED", str(ctx.exception))
        self.assertIn("#52", str(ctx.exception))

    def test_not_ready_pos_reports_status(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.get_adapter("pos_invoice")
        self.assertIn("NOT_READY", str(ctx.exception))

    def test_bom_stripped(self):
        rows = ic.parse_csv_text("\ufeff" + cat_csv("S1,,1,active,KAT-01,Kemeja"),
                                 "k.csv")
        self.assertEqual(rows[0]["source_id"], "S1")

    def test_row_limit_10000(self):
        big = cat_csv(*[f"S{i},,1,active,K{i:05d},Nama {i}" for i in range(10000)])
        rows = ic.parse_csv_text(big, "k.csv")
        self.assertEqual(len(rows), 10000)
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.parse_csv_text(
                cat_csv(*[f"S{i},,1,active,K{i:05d},N{i}" for i in range(10001)]),
                "k.csv")
        self.assertEqual(ctx.exception.reason, "file_too_large")

    def test_byte_limit_5mb(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.parse_csv_text("x" * (ic.MAX_IMPORT_BYTES + 1), "k.csv")
        self.assertEqual(ctx.exception.reason, "file_too_large")

    def test_empty_file_rejected(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.parse_csv_text("", "k.csv")
        self.assertEqual(ctx.exception.reason, "empty_file")

    def test_column_mismatch_rejected(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.parse_csv_text("a,b,c\n1,2\n", "k.csv")
        self.assertEqual(ctx.exception.reason, "column_mismatch")

    def test_source_identity_defaults(self):
        identity, errors = ic.validate_source_identity({"source_id": "SRC-1"})
        self.assertEqual(errors, [])
        self.assertEqual(identity["source_revision"], 1)
        self.assertEqual(identity["row_kind"], "active")

    def test_source_identity_missing_source_id(self):
        identity, errors = ic.validate_source_identity({"source_id": "  "})
        self.assertTrue(any(e["reason"] == "missing_required" for e in errors))
        self.assertNotIn("source_id", identity)

    def test_money_valid_to_minor(self):
        self.assertEqual(ic.parse_money_field("15000.50"), 1500050)
        self.assertEqual(ic.parse_money_field("0"), 0)

    def test_money_invalid_format(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.parse_money_field("1.500,00")
        self.assertEqual(ctx.exception.reason, "invalid_money")

    def test_money_negative_rejected(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.parse_money_field("-100")
        self.assertEqual(ctx.exception.reason, "negative_amount")

    def test_date_valid(self):
        self.assertEqual(ic.parse_date_field("2026-09-28"), "2026-09-28")

    def test_date_invalid(self):
        for bad in ("28/09/2026", "2026-02-30", "kemarin"):
            with self.assertRaises(ic.ImportContractError, msg=bad) as ctx:
                ic.parse_date_field(bad)
            self.assertEqual(ctx.exception.reason, "invalid_date")

    def test_job_config_requires_system_account(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.validate_job_config({"source_account": "x", "strategy": "active_only"})
        self.assertEqual(ctx.exception.reason, "missing_required")

    def test_job_config_bad_strategy(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.validate_job_config({"source_system": "s", "source_account": "a",
                                    "strategy": "hitung_dua_duanya"})
        self.assertEqual(ctx.exception.reason, "invalid_type")

    def test_classify_active_only_rejects_history(self):
        disp, rej = ic.classify_row_kind("active_only", "history")
        self.assertEqual(disp, "rejected")
        self.assertEqual(rej["reason"], "history_not_in_scope")

    def test_classify_opening_balance_archives_history(self):
        disp, rej = ic.classify_row_kind("opening_balance", "history")
        self.assertEqual(disp, "archived")
        self.assertIsNone(rej)

    def test_idempotency_key_deterministic_and_valid(self):
        key1 = ic.derive_idempotency_key("legacy", "backoffice", "product_category",
                                         "SRC-1", None)
        key2 = ic.derive_idempotency_key("legacy", "backoffice", "product_category",
                                         "SRC-1", None)
        self.assertEqual(key1, key2)
        ic.validate_idempotency_key(key1)  # lolos regex F02

    def test_batch_duplicate_identical_deduped(self):
        key = ("legacy", "backoffice", "product_category", "S1", None)
        rows = [{"row_no": 1, "key": key, "fingerprint": "h1"},
                {"row_no": 2, "key": key, "fingerprint": "h1"}]
        dupes = ic.check_batch_duplicates(rows)
        self.assertEqual(len(dupes), 1)
        self.assertTrue(dupes[0]["identical"])
        self.assertEqual(dupes[0]["duplicate_of"], 1)

    def test_batch_duplicate_different_payload_conflict(self):
        key = ("legacy", "backoffice", "product_category", "S1", None)
        rows = [{"row_no": 1, "key": key, "fingerprint": "h1"},
                {"row_no": 2, "key": key, "fingerprint": "h2"}]
        dupes = ic.check_batch_duplicates(rows)
        self.assertEqual(len(dupes), 1)
        self.assertFalse(dupes[0]["identical"])
        self.assertEqual(dupes[0]["reason"], "duplicate_in_batch")

    def test_empty_sku_rejected_with_reason(self):
        _, errors = ic.validate_row("product",
                                    {"source_id": "S1", "sku": "  ", "name": "X"},
                                    1, {})
        self.assertTrue(any(e["reason"] == "empty_sku" for e in errors))

    def test_material_unit_validated(self):
        _, errors = ic.validate_row("material",
                                    {"source_id": "S1", "code": "M-1",
                                     "name": "Benang", "unit": "kg"},
                                    1, {})
        self.assertEqual(errors, [])
        _, errors = ic.validate_row("material",
                                    {"source_id": "S1", "code": "M-1",
                                     "name": "Benang", "unit": "liter"},
                                    1, {})
        self.assertTrue(any(e["reason"] == "invalid_unit" for e in errors))

    def test_control_totals(self):
        totals = ic.control_totals(["ok", "mapped", "rejected", "quarantined",
                                    "archived", "applied", "failed"])
        self.assertEqual(totals, {"total": 7, "will_create": 1, "will_map": 1,
                                  "rejected": 1, "quarantined": 1, "archived": 1,
                                  "applied": 1, "failed": 1})


class ImportStoreTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "test.sqlite3")
        self.store = Store(self.db)
        self.admin = self.store.provision_user("Administrator", "admin")
        self.actor = {"id": self.admin["id"]}

    def tearDown(self):
        self.tmp.cleanup()

    def _con(self):
        return sqlite3.connect(self.db)

    def test_schema_63_and_import_permission_insertable(self):
        version = self._con().execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version, 63)
        # permission baru lolos CHECK constraint hasil rebuild
        self.store.set_user_permissions(self.admin["id"], ["read_operational",
                                                           "import_data"],
                                        self.admin["id"], "tes x01")
        perms = self._con().execute(
            "SELECT permission FROM user_permissions WHERE user_id=?",
            (self.admin["id"],)).fetchall()
        self.assertIn("import_data", [r[0] for r in perms])
        with self.assertRaises(sqlite3.IntegrityError):
            self._con().execute(
                "INSERT INTO user_permissions(user_id,permission,granted_by,granted_at) "
                "VALUES(?,?,?,?)", (self.admin["id"], "hack_permission",
                                    self.admin["id"], "2026-09-28T00:00:00+07:00"))

    def test_dry_run_valid_no_domain_writes(self):
        job = self.store.import_dry_run(
            "product_category", CFG,
            cat_csv("S1,,1,active,KAT-01,Kemeja", "S2,,1,active,KAT-02,Celana"),
            "kategori.csv", self.actor)
        self.assertEqual(job["status"], "dry_run")
        self.assertEqual(job["control_totals"]["will_create"], 2)
        count = self._con().execute("SELECT COUNT(*) FROM product_categories").fetchone()[0]
        self.assertEqual(count, 0, "dry-run tidak boleh menulis domain")
        events = self._con().execute(
            "SELECT COUNT(*) FROM import_job_events WHERE job_id=?", (job["id"],)).fetchone()[0]
        self.assertGreaterEqual(events, 1)

    def test_dry_run_orphan_reference(self):
        header = ("source_id,source_line_id,source_revision,row_kind,sku,name,"
                  "category_code")
        csv_text = header + "\nS1,,1,active,SKU-1,Kemeja,KAT-TIDAK-ADA"
        job = self.store.import_dry_run("product", CFG, csv_text, "p.csv", self.actor)
        self.assertEqual(job["control_totals"]["rejected"], 1)
        row = job["rows"][0]
        self.assertEqual(row["status"], "rejected")
        self.assertEqual(row["reject_reason"], "orphan_reference")

    def test_dry_run_duplicate_code_existing_db(self):
        self.store.create_master("product_category", {"code": "KAT-01", "name": "Ada"},
                                 self.actor, "seed-1")
        job = self.store.import_dry_run(
            "product_category", CFG, cat_csv("S1,,1,active,KAT-01,Kemeja"),
            "k.csv", self.actor)
        self.assertEqual(job["rows"][0]["reject_reason"], "duplicate_code")

    def test_dry_run_invalid_money_date_unit(self):
        header = ("source_id,source_line_id,source_revision,row_kind,code,name,"
                  "unit,reference_price")
        csv_text = header + '\nS1,,1,active,M-1,Benang,liter,"1.500,00"'
        job = self.store.import_dry_run("material", CFG, csv_text, "m.csv", self.actor)
        row = job["rows"][0]
        self.assertEqual(row["status"], "rejected")
        reasons = [d["reason"] for d in row["reject_detail"]]
        self.assertIn("invalid_unit", reasons)
        self.assertIn("invalid_money", reasons)

    def test_dry_run_history_rejected_under_active_only(self):
        job = self.store.import_dry_run(
            "product_category", CFG, cat_csv("S1,,1,history,KAT-01,Kemeja"),
            "k.csv", self.actor)
        self.assertEqual(job["rows"][0]["reject_reason"], "history_not_in_scope")

    def test_dry_run_history_archived_under_opening_balance(self):
        cfg = dict(CFG, strategy="opening_balance")
        job = self.store.import_dry_run(
            "product_category", cfg, cat_csv("S1,,1,history,KAT-01,Kemeja"),
            "k.csv", self.actor)
        row = job["rows"][0]
        self.assertEqual(row["status"], "archived")
        res = self.store.apply_import_job(job["id"], self.actor, "apply-opening-1")
        self.assertEqual(res["applied"], 0)
        count = self._con().execute("SELECT COUNT(*) FROM product_categories").fetchone()[0]
        self.assertEqual(count, 0)

    def test_source_conflict_rejected_same_revision(self):
        csv_text = cat_csv("S1,,1,active,KAT-01,Kemeja")
        job1 = self.store.import_dry_run("product_category", CFG, csv_text, "a.csv",
                                         self.actor)
        self.store.apply_import_job(job1["id"], self.actor, "apply-c1")
        csv_text2 = cat_csv("S1,,1,active,KAT-01,Kemeja Beda")
        job2 = self.store.import_dry_run("product_category", CFG, csv_text2, "b.csv",
                                         self.actor)
        self.assertEqual(job2["rows"][0]["reject_reason"], "source_conflict")

    def test_revision_bump_quarantined_then_applied_with_auto(self):
        csv_text = cat_csv("S1,,1,active,KAT-01,Kemeja")
        job1 = self.store.import_dry_run("product_category", CFG, csv_text, "a.csv",
                                         self.actor)
        self.store.apply_import_job(job1["id"], self.actor, "apply-r1")
        csv_text2 = cat_csv("S1,,2,active,KAT-01,Kemeja Baru")
        job2 = self.store.import_dry_run("product_category", CFG, csv_text2, "b.csv",
                                         self.actor)
        self.assertEqual(job2["rows"][0]["status"], "quarantined")
        self.assertEqual(job2["rows"][0]["reject_reason"], "revision_bump_pending_review")
        cfg = dict(CFG, auto_apply_revisions=True)
        job3 = self.store.import_dry_run("product_category", cfg, csv_text2, "c.csv",
                                         self.actor)
        self.assertEqual(job3["rows"][0]["status"], "ok")
        res = self.store.apply_import_job(job3["id"], self.actor, "apply-r2")
        self.assertEqual(res["status"], "applied")
        name = self._con().execute(
            "SELECT name FROM product_categories WHERE code='KAT-01'").fetchone()[0]
        self.assertEqual(name, "Kemeja Baru")

    def test_production_guard_env(self):
        os.environ["BEELOFT_PRODUCTION"] = "1"
        try:
            with self.assertRaises(DomainError) as ctx:
                self.store.import_dry_run("product_category", CFG,
                                          cat_csv("S1,,1,active,KAT-01,X"),
                                          "k.csv", self.actor)
            self.assertEqual(ctx.exception.status, 403)
        finally:
            del os.environ["BEELOFT_PRODUCTION"]

    def test_production_guard_filename(self):
        prod_db = str(Path(self.tmp.name) / "beeloft-prod.sqlite3")
        store = Store(prod_db)
        admin = store.provision_user("Administrator", "admin")
        with self.assertRaises(DomainError) as ctx:
            store.import_dry_run("product_category", CFG,
                                 cat_csv("S1,,1,active,KAT-01,X"),
                                 "k.csv", {"id": admin["id"]})
        self.assertEqual(ctx.exception.status, 403)

    def test_apply_creates_via_service_and_audit(self):
        job = self.store.import_dry_run(
            "product_category", CFG, cat_csv("S1,,1,active,KAT-01,Kemeja"),
            "k.csv", self.actor)
        res = self.store.apply_import_job(job["id"], self.actor, "apply-a1")
        self.assertEqual(res["status"], "applied")
        self.assertEqual(res["applied"], 1)
        row = self._con().execute(
            "SELECT id FROM product_categories WHERE code='KAT-01'").fetchone()
        self.assertIsNotNone(row)
        audit = self._con().execute(
            "SELECT COUNT(*) FROM audit_events WHERE operation='product-category'"
        ).fetchone()[0]
        self.assertGreaterEqual(audit, 1)

    def test_apply_idempotent_replay(self):
        job = self.store.import_dry_run(
            "product_category", CFG, cat_csv("S1,,1,active,KAT-01,Kemeja"),
            "k.csv", self.actor)
        first = self.store.apply_import_job(job["id"], self.actor, "apply-key-x")
        second = self.store.apply_import_job(job["id"], self.actor, "apply-key-x")
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(first["applied"], second["applied"])
        count = self._con().execute("SELECT COUNT(*) FROM product_categories").fetchone()[0]
        self.assertEqual(count, 1)

    def test_apply_batch_atomic_rollback(self):
        csv_text = cat_csv("S1,,1,active,KAT-A,A", "S2,,1,active,KAT-B,B",
                           "S3,,1,active,KAT-C,C")
        job = self.store.import_dry_run("product_category", CFG, csv_text, "k.csv",
                                         self.actor)
        # Konflik muncul setelah dry-run (simulasi tulis konkurensi).
        self.store.create_master("product_category", {"code": "KAT-B", "name": "X"},
                                 self.actor, "konflik-1")
        with self.assertRaises(DomainError):
            self.store.apply_import_job(job["id"], self.actor, "apply-batch-1")
        count = self._con().execute("SELECT COUNT(*) FROM product_categories").fetchone()[0]
        self.assertEqual(count, 1, "rollback total: hanya konflik manual yang tersisa")
        status = self._con().execute("SELECT status FROM import_jobs WHERE id=?",
                                     (job["id"],)).fetchone()[0]
        self.assertEqual(status, "failed")

    def test_apply_retry_reattempts_failed_row(self):
        csv_text = cat_csv("S1,,1,active,KAT-A,A", "S2,,1,active,KAT-B,B")
        job = self.store.import_dry_run("product_category", CFG, csv_text, "k.csv",
                                         self.actor)
        self.store.create_master("product_category", {"code": "KAT-B", "name": "X"},
                                 self.actor, "konflik-2")
        with self.assertRaises(DomainError):
            self.store.apply_import_job(job["id"], self.actor, "apply-retry-1")
        # Retry tanpa perbaikan: baris gagal dicoba lagi, bukan dilewati diam-diam.
        with self.assertRaises(DomainError):
            self.store.apply_import_job(job["id"], self.actor, "apply-retry-2")

    def test_reupload_after_failed_job_treated_as_new(self):
        csv_text = cat_csv("S1,,1,active,KAT-A,A")
        job1 = self.store.import_dry_run("product_category", CFG, csv_text, "a.csv",
                                          self.actor)
        self.store.create_master("product_category", {"code": "KAT-A", "name": "X"},
                                 self.actor, "konflik-3")
        with self.assertRaises(DomainError):
            self.store.apply_import_job(job1["id"], self.actor, "apply-f1")
        job2 = self.store.import_dry_run("product_category", CFG, csv_text, "b.csv",
                                          self.actor)
        # Baris job gagal tidak termaterialisasi -> bukan 'mapped' hantu.
        self.assertEqual(job2["control_totals"]["will_map"], 0)

    def test_product_uom_forced_pcs_at_apply(self):
        # Kontrak: uom produk selalu PCS; nilai CSV tidak diteruskan ke domain.
        spec = ic.get_adapter("product")
        payload = self.store._import_create_payload(
            "product", spec,
            {"sku": "SKU-1", "name": "X", "uom_code": "LUSIN"}, {})
        self.assertEqual(payload["uom_code"], "PCS")

    def test_import_job_detail_roundtrip(self):
        job = self.store.import_dry_run(
            "product_category", CFG, cat_csv("S1,,1,active,KAT-01,Kemeja"),
            "k.csv", self.actor)
        detail = self.store.import_job_detail(job["id"])
        self.assertEqual(detail["job_ref"], job["job_ref"])
        self.assertEqual(len(detail["rows"]), 1)
        self.assertTrue(detail["events"])


class ImportApiTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "api.sqlite3")
        self.store = Store(self.db)
        self.app = create_app(self.db)
        self.client = TestClient(self.app)
        self.admin = self.store.provision_user("Administrator", "admin")
        self.operator = self.store.provision_user("Operator", "operator",
                                                  preset="production_operator")

    def tearDown(self):
        self.tmp.cleanup()

    def _headers(self, user):
        return {"X-API-Key": user["api_key"]}

    def test_adapters_lists_supported_and_blocked(self):
        response = self.client.get("/api/import/adapters",
                                   headers=self._headers(self.admin))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        catalog = body[0] if isinstance(body, list) else body
        names = [a["name"] for a in catalog["supported"]]
        self.assertIn("product", names)
        self.assertIn("supplier", names)
        blocked = {b["name"]: b["status"] for b in catalog["unsupported"]}
        self.assertEqual(blocked.get("payroll"), "UNSUPPORTED")
        self.assertEqual(blocked.get("pos_invoice"), "NOT_READY")

    def test_dry_run_requires_permission(self):
        response = self.client.post(
            "/api/import/dry-run",
            json={"adapter": "product_category", "source_system": "legacy",
                  "source_account": "backoffice", "strategy": "active_only",
                  "filename": "k.csv",
                  "csv_text": cat_csv("S1,,1,active,KAT-01,Kemeja")},
            headers=self._headers(self.operator))
        self.assertEqual(response.status_code, 403)

    def test_apply_requires_permission(self):
        job = self.store.import_dry_run(
            "product_category", CFG, cat_csv("S1,,1,active,KAT-01,Kemeja"),
            "k.csv", {"id": self.admin["id"]})
        response = self.client.post(
            f"/api/import/jobs/{job['id']}/apply", json={},
            headers={**self._headers(self.operator),
                     "Idempotency-Key": "op-apply-1"})
        self.assertEqual(response.status_code, 403)

    def test_full_flow_via_api(self):
        dry = self.client.post(
            "/api/import/dry-run",
            json={"adapter": "product_category", "source_system": "legacy",
                  "source_account": "backoffice", "strategy": "active_only",
                  "filename": "k.csv",
                  "csv_text": cat_csv("S1,,1,active,KAT-01,Kemeja")},
            headers=self._headers(self.admin))
        self.assertEqual(dry.status_code, 201)
        job_id = dry.json()["id"]
        apply = self.client.post(
            f"/api/import/jobs/{job_id}/apply", json={},
            headers={**self._headers(self.admin), "Idempotency-Key": "api-apply-1"})
        self.assertEqual(apply.status_code, 200)
        self.assertEqual(apply.json()["status"], "applied")
        replay = self.client.post(
            f"/api/import/jobs/{job_id}/apply", json={},
            headers={**self._headers(self.admin), "Idempotency-Key": "api-apply-1"})
        self.assertTrue(replay.json()["idempotent_replay"])

    def test_openapi_contract_version(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json()
        self.assertEqual(spec["info"]["version"], "0.121.0")
        self.assertIn("/api/import/dry-run", spec["paths"])
        self.assertIn("/api/import/jobs/{job_id}/apply", spec["paths"])


class ImportMappingTest(TestCase):
    """Alur pemetaan X01: column_map, id_map, reference_mode.

    Kontrak + store + API teruji; UI (index.html/app.mjs) menyediakan tiga
    textarea JSON dan mengirim ketiganya pada body dry-run.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "mapping.sqlite3")
        self.store = Store(self.db)
        self.app = create_app(self.db)
        self.client = TestClient(self.app)
        self.admin = self.store.provision_user("Administrator", "admin")
        self.actor = {"id": self.admin["id"]}

    def tearDown(self):
        self.tmp.cleanup()

    def _headers(self):
        return {"X-API-Key": self.admin["api_key"]}

    def test_apply_column_map_renames_alias(self):
        mapped = ic.apply_column_map({"kode": "K1", "name": "X"},
                                      {"code": "kode"})
        self.assertEqual(mapped, {"code": "K1", "name": "X"})
        self.assertEqual(ic.apply_column_map({"code": "K1"}, {}), {"code": "K1"})

    def test_validate_job_config_accepts_mapping(self):
        cfg = ic.validate_job_config({
            **CFG,
            "column_map": {"name": "nama_produk"},
            "id_map": {"product_categories": {"LEG-01": "abc"}},
            "reference_mode": {"category_code": "name"},
        })
        self.assertEqual(cfg["column_map"], {"name": "nama_produk"})
        self.assertEqual(cfg["id_map"], {"product_categories": {"LEG-01": "abc"}})
        self.assertEqual(cfg["reference_mode"], {"category_code": "name"})

    def test_validate_job_config_rejects_bad_reference_mode(self):
        with self.assertRaises(ic.ImportContractError) as ctx:
            ic.validate_job_config({**CFG, "reference_mode": {"category_code": "sku"}})
        self.assertEqual(ctx.exception.field, "reference_mode")

    def test_dry_run_column_map_alias_header(self):
        cfg = {**CFG, "column_map": {"code": "kode", "name": "nama"}}
        header = "source_id,source_line_id,source_revision,row_kind,kode,nama"
        job = self.store.import_dry_run(
            "product_category", cfg,
            header + "\nS1,,1,active,KAT-01,Kemeja", "k.csv", self.actor)
        self.assertEqual(job["control_totals"]["will_create"], 1)
        self.assertEqual(job["rows"][0]["status"], "ok")

    def _seed_category(self):
        return self.store.create_master(
            "product_category", {"code": "KAT-01", "name": "Kemeja"},
            self.actor, "seed-x01-map")

    def test_dry_run_reference_mode_name_resolves_by_name(self):
        self._seed_category()
        header = ("source_id,source_line_id,source_revision,row_kind,code,name,"
                  "category_code")
        csv_text = header + "\nS1,,1,active,SUB-01,Obras,Kemeja"
        # Tanpa mode: lookup by code gagal -> orphan_reference.
        plain = self.store.import_dry_run("product_subcategory", CFG, csv_text,
                                          "s.csv", self.actor)
        self.assertEqual(plain["rows"][0]["reject_reason"], "orphan_reference")
        # Dengan mode name: cocok pada nama kategori -> valid.
        cfg = {**CFG, "reference_mode": {"category_code": "name"}}
        job = self.store.import_dry_run("product_subcategory", cfg, csv_text,
                                        "s.csv", self.actor)
        self.assertEqual(job["control_totals"]["will_create"], 1)
        self.assertEqual(job["rows"][0]["status"], "ok")

    def test_dry_run_id_map_wins_over_lookup(self):
        cat = self._seed_category()
        header = ("source_id,source_line_id,source_revision,row_kind,code,name,"
                  "category_code")
        csv_text = header + "\nS1,,1,active,SUB-01,Obras,LEG-KAT"
        cfg = {**CFG, "id_map": {"product_categories": {"LEG-KAT": cat["id"]}}}
        job = self.store.import_dry_run("product_subcategory", cfg, csv_text,
                                        "s.csv", self.actor)
        self.assertEqual(job["control_totals"]["will_create"], 1)
        self.assertEqual(job["rows"][0]["status"], "ok")

    def test_dry_run_id_map_orphan_when_target_missing(self):
        header = ("source_id,source_line_id,source_revision,row_kind,code,name,"
                  "category_code")
        csv_text = header + "\nS1,,1,active,SUB-01,Obras,LEG-KAT"
        cfg = {**CFG, "id_map": {"product_categories": {"LEG-KAT": "tidak-ada"}}}
        job = self.store.import_dry_run("product_subcategory", cfg, csv_text,
                                        "s.csv", self.actor)
        self.assertEqual(job["rows"][0]["reject_reason"], "orphan_reference")

    def test_api_dry_run_accepts_mapping_fields(self):
        response = self.client.post(
            "/api/import/dry-run",
            json={"adapter": "product_category", "source_system": "legacy",
                  "source_account": "backoffice", "strategy": "active_only",
                  "filename": "k.csv",
                  "csv_text": ("source_id,source_line_id,source_revision,"
                               "row_kind,kode,nama\nS1,,1,active,KAT-01,Kemeja"),
                  "column_map": {"code": "kode", "name": "nama"},
                  "id_map": {}, "reference_mode": {}},
            headers=self._headers())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["control_totals"]["will_create"], 1)

    def test_ui_provides_mapping_controls(self):
        html = (Path(__file__).resolve().parent.parent / "beeloft" / "static"
                / "index.html").read_text(encoding="utf-8")
        for element_id in ("import-column-map", "import-id-map",
                           "import-reference-mode"):
            self.assertIn(f'id="{element_id}"', html)
        js = (Path(__file__).resolve().parent.parent / "beeloft" / "static"
              / "app.mjs").read_text(encoding="utf-8")
        for element_id in ("import-column-map", "import-id-map",
                           "import-reference-mode"):
            self.assertIn(element_id, js)
        self.assertIn("column_map:", js)


if __name__ == "__main__":
    unittest.main()
