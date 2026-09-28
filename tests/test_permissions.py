import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store, DomainError
from beeloft.permissions import (
    PERMISSIONS,
    ROLE_PERMISSIONS,
    DEMO_PRESET_VERSION,
    PRESETS,
    has_permission,
    require_permission,
    can_access_unit,
    require_unit_access,
    check_self_approval,
)


class PermissionsCatalogTest(TestCase):
    def test_ten_permissions_are_explicit(self):
        self.assertEqual(set(PERMISSIONS), {
            "read_operational", "create_transaction", "approve_transaction",
            "record_payment", "post_ledger", "export_data", "view_salary",
            "view_margin_profit", "manage_access", "import_data",
        })

    def test_existing_role_mapping_preserves_compatibility_without_preset(self):
        # Akun tanpa baris izin granular mempertahankan kompatibilitas jalur existing
        # supaya migrasi tidak diam-diam menghilangkan jalur administrasi yang sah.
        self.assertTrue(has_permission({"role": "admin"}, "manage_access"))
        self.assertTrue(has_permission({"role": "operator"}, "read_operational"))

    def test_demo_presets_are_separated_and_versioned(self):
        self.assertTrue(DEMO_PRESET_VERSION.startswith("O01-DEMO-"))
        self.assertIn("operational_admin", PRESETS)
        self.assertIn("hr_payroll", PRESETS)
        self.assertIn("finance", PRESETS)
        self.assertIn("view_salary", PRESETS["hr_payroll"]["permissions"])
        self.assertNotIn("view_margin_profit", PRESETS["hr_payroll"]["permissions"])
        self.assertNotIn("view_salary", PRESETS["finance"]["permissions"])
        self.assertIn("view_margin_profit", PRESETS["finance"]["permissions"])
        self.assertNotIn("record_payment", PRESETS["hr_payroll"]["permissions"])
        self.assertTrue(PRESETS["operational_admin"]["no_self_approval"])

    def test_permission_failure_is_distinct_from_missing_actor(self):
        with self.assertRaises(DomainError) as unauthenticated:
            require_permission(None, "view_salary")
        self.assertEqual(unauthenticated.exception.status, 401)
        with self.assertRaises(DomainError) as forbidden:
            require_permission({"id": "u", "role": "admin",
                                "permissions": ["read_operational"]}, "view_salary")
        self.assertEqual(forbidden.exception.status, 403)
        self.assertIn("kompensasi atau payroll", forbidden.exception.message)

    def test_scoped_actor_cannot_access_unassigned_or_legacy_unit(self):
        actor = {"all_units": False, "business_units": ["BU-JKT"]}
        self.assertTrue(can_access_unit(actor, "BU-JKT"))
        self.assertFalse(can_access_unit(actor, "BU-BDG"))
        self.assertFalse(can_access_unit(actor, None))
        require_unit_access(actor, "BU-JKT")
        with self.assertRaises(DomainError):
            require_unit_access(actor, None)
        with self.assertRaises(DomainError):
            require_unit_access(actor, "BU-BDG")

    def test_self_approval_uses_server_creator_identity(self):
        actor = {"id": "creator-1", "preset": "operational_admin", "no_self_approval": True}
        with self.assertRaises(DomainError) as caught:
            check_self_approval(actor, "creator-1")
        self.assertEqual(caught.exception.status, 403)
        check_self_approval({"id": "approver", "preset": "operational_admin"}, "creator-1")

    def test_permissions_migration_upgrades_legacy_database(self):
        with tempfile.TemporaryDirectory() as d:
            app = create_app(Path(d) / "test.db")
            store: Store = app.state.store
            with store.transaction() as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 63)
                for table in ("user_permissions", "user_business_units", "user_access_profiles", "user_access_events"):
                    self.assertIsNotNone(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


class PermissionFilteredUiTest(TestCase):
    """Filter UI hanya kosmetik; otorisasi tetap di server (lihat tes route di bawah)."""

    APP = (Path(__file__).resolve().parent.parent / "beeloft" / "static" / "app.mjs").read_text()

    def test_workspace_reads_granular_access_after_login(self):
        self.assertIn("  applyUserAccess(me);\n}", self.APP)
        self.assertIn("const access = await api.get('/api/me/access').catch(() => null);", self.APP)
        self.assertIn("if (!access || user !== me) return;", self.APP)

    def test_entry_points_hide_without_the_matching_permission(self):
        for gate in ("if (!allowed('manage_access')) { $('audit-trail').hidden = true; $('backup').hidden = true; }",
                     "if (!allowed('create_transaction')) $('new-order').hidden = true;",
                     "if (!allowed('export_data')) $('activity-export').hidden = true;",
                     "if (!allowed('import_data')) $('import').hidden = true;"):
            with self.subTest(gate=gate[:48]):
                self.assertIn(gate, self.APP)

    def test_session_reset_clears_permission_hiding(self):
        self.assertIn("$('activity-export').hidden = false;", self.APP)


class PermissionsLifecycleApiTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)
        self.store: Store = self.app.state.store
        self.admin = self.store.provision_user("Administrator", "admin")
        # Operator dengan preset production_operator: izin terbatas oleh preset, bukan fallback role
        self.operator = self.store.provision_user("Operator", "operator", preset="production_operator")

    def tearDown(self):
        self.tmp.cleanup()

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 401)

    def test_existing_auth_login_and_api_key_remain_compatible(self):
        login = self.client.post("/api/session", json={"api_key": self.operator["api_key"]})
        self.assertEqual(login.status_code, 200, login.text)
        by_key = self.client.get("/api/me", headers={"X-API-Key": self.operator["api_key"]})
        self.assertEqual(by_key.status_code, 200, by_key.text)
        self.assertEqual(by_key.json()["role"], "operator")
        # Kontrak /api/me tetap tiga kunci identitas; izin dibaca di /api/me/access.
        self.assertEqual(set(by_key.json()), {"id", "name", "role"})
        access = self.client.get("/api/me/access", headers={"X-API-Key": self.operator["api_key"]})
        self.assertEqual(access.status_code, 200, access.text)
        self.assertIn("read_operational", access.json()["permissions"])
        self.assertNotIn("view_salary", access.json()["permissions"])

    def test_non_admin_cannot_read_users(self):
        response = self.client.get("/api/users", headers={"X-API-Key": self.operator["api_key"]})
        self.assertEqual(response.status_code, 403)

    def test_payroll_salary_and_margin_routes_require_separate_permissions(self):
        headers = {"X-API-Key": self.operator["api_key"]}
        for path in ("/api/integrations/mekari/payroll-summary",
                     "/api/payroll-payment-reconciliation",
                     "/api/payroll-accounting-reconciliation",
                     "/api/orders/nonexistent/contribution-margin"):
            with self.subTest(path=path):
                response = self.client.get(path, headers=headers)
                self.assertEqual(response.status_code, 403, (path, response.text))

    def test_export_requires_explicit_export_permission(self):
        response = self.client.get("/api/activity.csv", headers={"X-API-Key": self.operator["api_key"]})
        self.assertEqual(response.status_code, 403, response.text)

    def test_live_session_refreshes_permissions_after_revocation(self):
        login = self.client.post("/api/session", json={"api_key": self.admin["api_key"]})
        self.assertEqual(login.status_code, 200)
        session_client = TestClient(self.app)
        session_client.cookies.update(login.cookies)
        before = session_client.get("/api/me/access")
        self.assertEqual(before.status_code, 200)
        self.assertTrue(has_permission(before.json(), "manage_access"))
        self.store.set_user_permissions(self.admin["id"], ["read_operational"], self.admin["id"], "test revoke")
        after = session_client.get("/api/me/access")
        self.assertEqual(after.status_code, 200)
        self.assertFalse(has_permission(after.json(), "manage_access"))

    def test_admin_may_list_users(self):
        response = self.client.get("/api/users", headers={"X-API-Key": self.admin["api_key"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 2)

    def test_non_admin_cannot_escalate_access_by_payload(self):
        response = self.client.post("/api/users", json={"name": "Escalation", "role": "admin", "permissions": list(PERMISSIONS)}, headers={"X-API-Key": self.operator["api_key"]})
        self.assertNotEqual(response.status_code, 201)
        self.assertEqual(len(self.store.users()), 2)

    def test_access_changes_are_audited_with_server_actor(self):
        self.store.set_user_preset(self.operator["id"], "hr_payroll", self.admin["id"],
                                   "Rotasi tugas payroll")
        events = self.client.get("/api/users/" + self.operator["id"] + "/access-events",
                                 headers={"X-API-Key": self.admin["api_key"]})
        self.assertEqual(events.status_code, 200, events.text)
        items = events.json()["items"]
        latest = items[0]
        self.assertEqual(latest["action"], "set_preset")
        self.assertEqual(latest["after_value"], "hr_payroll")
        self.assertEqual(latest["actor_id"], self.admin["id"])
        self.assertEqual(latest["reason"], "Rotasi tugas payroll")

    def test_route_level_self_approval_is_blocked_for_preset_actor(self):
        # Bukti enforcement di jalur HTTP, bukan hanya unit helper: admin ber-preset
        # mengajukan purchase request lalu mencoba menyetujui pengajuannya sendiri.
        admin = self.store.provision_user("Admin SoD", "admin", preset="operational_admin")
        headers = {"X-API-Key": admin["api_key"]}
        material = self.client.post("/api/materials", json={
            "code": "SOD-001", "name": "Bahan SoD", "unit": "m"},
            headers=headers | {"Idempotency-Key": "sod-material"})
        self.assertEqual(material.status_code, 201, material.text)
        request = self.client.post("/api/purchase-requests", json={
            "reference": "PR-SOD-001",
            "lines": [{"material_id": material.json()["id"], "quantity": "5"}],
            "required_date": "2026-12-31",
            "estimated_value": "50000",
            "reason": "Kebutuhan bahan uji SoD"},
            headers=headers | {"Idempotency-Key": "sod-request"})
        self.assertEqual(request.status_code, 201, request.text)
        body = request.json()
        decision = self.client.post("/api/purchase-requests/" + body["id"] + "/decisions", json={
            "status": "approved", "expected_revision": body["revision"],
            "reason": "Mencoba menyetujui pengajuan sendiri"},
            headers=headers | {"Idempotency-Key": "sod-approve"})
        self.assertEqual(decision.status_code, 403, decision.text)
        self.assertIn("no self-approval", decision.json()["detail"])

    def test_self_disable_is_rejected(self):
        response = self.client.post("/api/users/" + self.admin["id"] + "/disable",
                                    headers={"X-API-Key": self.admin["api_key"]})
        self.assertEqual(response.status_code, 409, response.text)

    def test_disabled_user_cannot_use_existing_auth(self):
        self.store.disable_user(self.operator["id"])
        response = self.client.get("/api/me", headers={"X-API-Key": self.operator["api_key"]})
        self.assertEqual(response.status_code, 401)
