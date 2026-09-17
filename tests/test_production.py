import tempfile
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient

from beeloft.api import create_app


class AuthenticationBoundaryTest(unittest.TestCase):
    def test_production_data_requires_authentication(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(Path(folder) / "test.sqlite3")) as client:
                self.assertEqual(client.get("/api/orders").status_code, 401)


class ProductionTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "test.sqlite3"
        self.app = create_app(self.path)
        self.client = TestClient(self.app).__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.admin = self.app.state.store.provision_user("Pemilik", "admin")
        self.operator = self.app.state.store.provision_user("Tim produksi", "operator")
        self.viewer = self.app.state.store.provision_user("Pengamat", "viewer")
        self.client.headers["X-API-Key"] = self.admin["api_key"]
        self.product = self.post("/api/products", {"sku": "LUNA-BLUE-M", "name": "Luna Blue", "size": "M", "color": "Blue"})

    def post(self, path, body, key=None, status=201, api_key=None):
        headers = {"Idempotency-Key": key or str(uuid4())}
        if api_key:
            headers["X-API-Key"] = api_key
        response = self.client.post(path, json=body, headers=headers)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def order(self, qty=100, **changes):
        body = {"reference": "PROD-" + str(uuid4())[:8], "title": "Luna batch 1",
                "owner_id": self.operator["id"], "due_date": "2026-01-01",
                "lines": [{"product_id": self.product["id"], "quantity": qty}]}
        body.update(changes)
        return self.post("/api/orders", body)

    def move(self, line, source, target, qty, **options):
        reason = options.pop("reason", "")
        return self.post("/api/movements", {"line_id": line, "from_stage": source,
                         "to_stage": target, "quantity": qty, "reason": reason}, **options)

    def detail(self, order):
        response = self.client.get("/api/orders/" + order["id"])
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_partial_moves_conserve_quantity_and_record_real_actor(self):
        order = self.order(500)
        line = order["lines"][0]["id"]
        self.move(line, "planned", "cutting", 300, api_key=self.operator["api_key"])
        self.move(line, "cutting", "sewing", 200)
        detail = self.detail(order)
        self.assertEqual(detail["lines"][0]["balances"], {
            "planned": 200, "cutting": 100, "sewing": 200, "finishing": 0,
            "qc": 0, "rework": 0, "reject": 0, "warehouse": 0})
        self.assertEqual(detail["status"], "active")
        self.assertTrue(detail["overdue"])
        history = self.client.get(f'/api/orders/{order["id"]}/movements').json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["actor_id"], self.operator["id"])
        self.assertTrue(history[0]["created_at"].endswith("+00:00"))

    def test_retry_is_stable_after_more_work_and_conflicting_reuse_is_rejected(self):
        order = self.order()
        line = order["lines"][0]["id"]
        original = self.move(line, "planned", "cutting", 80, key="transfer-once")
        self.move(line, "cutting", "sewing", 20)
        retry = self.move(line, "planned", "cutting", 80, key="transfer-once")
        self.assertEqual(retry, original)
        self.move(line, "planned", "cutting", 1, key="transfer-once", status=409)
        self.assertEqual(self.detail(order)["lines"][0]["balances"]["cutting"], 60)

    def test_order_retry_does_not_duplicate_lines(self):
        body = {"reference": "ONCE", "title": "Sekali", "owner_id": self.operator["id"],
                "due_date": "2026-12-01", "lines": [{"product_id": self.product["id"], "quantity": 5}]}
        first = self.post("/api/orders", body, key="order-once")
        self.assertEqual(first, self.post("/api/orders", body, key="order-once"))
        self.assertEqual(len(self.client.get("/api/orders").json()), 1)
        self.post("/api/orders", body, status=409)

    def test_invalid_quantities_routes_and_missing_reason_do_not_change_balances(self):
        order = self.order()
        line = order["lines"][0]["id"]
        for quantity in [0, -1, 1.5, True, "5", 1_000_000_001]:
            with self.subTest(quantity=quantity):
                self.move(line, "planned", "cutting", quantity, status=422)
        self.move(line, "planned", "warehouse", 5, status=422)
        self.move(line, "planned", "cutting", 101, status=409)
        self.move(line, "planned", "planned", 1, status=422)
        self.assertEqual(self.detail(order)["lines"][0]["balances"]["planned"], 100)
        self.assertEqual(self.client.get(f'/api/orders/{order["id"]}/movements').json(), [])

    def test_generic_qc_dispositions_require_final_qc_and_close_order(self):
        order = self.order(10)
        line = order["lines"][0]["id"]
        for source, target in [("planned", "cutting"), ("cutting", "sewing"),
                               ("sewing", "finishing"), ("finishing", "qc")]:
            self.move(line, source, target, 10)
        self.move(line, "qc", "rework", 2, reason="  ", status=422)
        self.move(line, "qc", "reject", 1, status=422)
        # Keputusan rework dan pengembaliannya sama-sama harus memiliki lineage Final QC.
        self.move(line, "qc", "rework", 2, reason="Jahitan perlu diperbaiki", status=422)
        self.move(line, "rework", "qc", 2, reason="Rework selesai", status=422)
        transitions = self.client.get('/api/stages').json()['transitions']
        self.assertNotIn(['qc', 'rework'], transitions)
        self.assertNotIn(['rework', 'qc'], transitions)
        self.assertEqual(self.detail(order)["lines"][0]["balances"], {
            "planned": 0, "cutting": 0, "sewing": 0, "finishing": 0,
            "qc": 10, "rework": 0, "reject": 0, "warehouse": 0})
        self.move(line, "qc", "reject", 1, reason="Kain sobek")
        self.move(line, "qc", "warehouse", 9)
        detail = self.detail(order)
        self.assertEqual(detail["status"], "closed_with_reject")
        self.assertFalse(detail["overdue"])
        self.assertEqual(detail["lines"][0]["balances"]["warehouse"], 9)
        self.move(line, "reject", "qc", 1, reason="Skip reversal", status=422)

    def test_admin_reversal_retains_original_and_cannot_repeat(self):
        order = self.order()
        line = order["lines"][0]["id"]
        movement = self.move(line, "planned", "cutting", 40)
        route = f'/api/movements/{movement["id"]}/reverse'
        self.post(route, {"reason": "Salah jumlah"}, status=403, api_key=self.operator["api_key"])
        self.post(route, {"reason": " "}, status=422)
        reversal = self.post(route, {"reason": "Salah jumlah"}, key="reverse-once")
        self.assertEqual(reversal["reversal_of"], movement["id"])
        self.assertEqual(reversal, self.post(route, {"reason": "Salah jumlah"}, key="reverse-once"))
        self.post(route, {"reason": "Ulang"}, status=409)
        self.post(f'/api/movements/{reversal["id"]}/reverse', {"reason": "Balik lagi"}, status=409)
        self.assertEqual(self.detail(order)["lines"][0]["balances"]["planned"], 100)
        self.assertEqual(len(self.client.get(f'/api/orders/{order["id"]}/movements').json()), 2)

    def test_reversal_fails_when_goods_have_moved_on(self):
        order = self.order()
        line = order["lines"][0]["id"]
        movement = self.move(line, "planned", "cutting", 40)
        self.move(line, "cutting", "sewing", 30)
        self.post(f'/api/movements/{movement["id"]}/reverse', {"reason": "Salah"}, status=409)
        self.assertEqual(self.detail(order)["lines"][0]["balances"]["cutting"], 10)

    def test_permissions_missing_key_and_forged_actor(self):
        order = self.order()
        line = order["lines"][0]["id"]
        self.move(line, "planned", "cutting", 1, status=403, api_key=self.viewer["api_key"])
        self.move(line, "planned", "cutting", 1, status=401, api_key="invalid")
        self.post("/api/products", {"sku": "OTHER", "name": "Other"}, status=403,
                  api_key=self.operator["api_key"])
        body = {"line_id": line, "from_stage": "planned", "to_stage": "cutting", "quantity": 1}
        self.assertEqual(self.client.post("/api/movements", json=body).status_code, 422)
        self.post("/api/movements", body | {"actor_id": self.viewer["id"]}, status=422)
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("api_key", response.text)
        self.assertNotIn("key_hash", response.text)

    def test_duplicate_sku_invalid_owner_and_missing_product_roll_back(self):
        self.post("/api/products", {"sku": " luna-blue-m ", "name": "Dup"}, status=409)
        self.post("/api/products", {"sku": " ", "name": "Empty"}, status=422)
        body = {"reference": "INVALID", "title": "Bad", "owner_id": self.viewer["id"],
                "due_date": "2026-12-01", "lines": [{"product_id": self.product["id"], "quantity": 5}]}
        self.post("/api/orders", body, status=422)
        body["owner_id"] = self.operator["id"]
        body["lines"].append({"product_id": "missing", "quantity": 10})
        self.post("/api/orders", body, status=404)
        self.assertEqual(self.client.get("/api/orders").json(), [])
        self.assertEqual(self.client.get("/api/orders/missing").status_code, 404)
        self.assertEqual(self.client.get("/api/orders/missing/movements").status_code, 404)

    def test_two_simultaneous_transfers_cannot_overdraw(self):
        order = self.order()
        line = order["lines"][0]["id"]
        barrier = Barrier(2)

        def transfer(_):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post("/api/movements", json={"line_id": line, "from_stage": "planned",
                                   "to_stage": "cutting", "quantity": 80}, headers={
                                   "X-API-Key": self.operator["api_key"],
                                   "Idempotency-Key": str(uuid4())}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(transfer, range(2))), [201, 409])
        balances = self.detail(order)["lines"][0]["balances"]
        self.assertEqual((balances["planned"], balances["cutting"]), (20, 80))

    def test_multi_sku_persistence_and_backup(self):
        second = self.post("/api/products", {"sku": "LUNA-BLUE-L", "name": "Luna Blue", "size": "L"})
        order = self.order(lines=[{"product_id": self.product["id"], "quantity": 20},
                                  {"product_id": second["id"], "quantity": 30}])
        self.move(order["lines"][0]["id"], "planned", "cutting", 12)
        expected = self.detail(order)
        backup = Path(self.folder.name) / "backup.sqlite3"
        self.app.state.store.backup(backup)
        for path in [self.path, backup]:
            with TestClient(create_app(path)) as client:
                actual = client.get(f'/api/orders/{order["id"]}', headers={"X-API-Key": self.admin["api_key"]})
                self.assertEqual(actual.json(), expected)
        with self.assertRaises(FileExistsError):
            self.app.state.store.backup(backup)

    def test_storage_failure_rolls_back_balance_changes_and_allows_retry(self):
        order = self.order()
        line = order["lines"][0]["id"]
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.execute("CREATE TRIGGER fail_movement BEFORE INSERT ON movements BEGIN SELECT RAISE(ABORT, 'write failed'); END")
        self.move(line, "planned", "cutting", 10, key="retry-failed-write", status=409)
        self.assertEqual(self.detail(order)["lines"][0]["balances"]["planned"], 100)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.execute("DROP TRIGGER fail_movement")
        self.move(line, "planned", "cutting", 10, key="retry-failed-write")
        self.assertEqual(self.detail(order)["lines"][0]["balances"]["planned"], 90)

    def test_concurrent_duplicate_request_creates_one_movement(self):
        order = self.order()
        line = order["lines"][0]["id"]
        barrier = Barrier(2)

        def transfer(_):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                response = client.post("/api/movements", json={"line_id": line, "from_stage": "planned",
                                       "to_stage": "cutting", "quantity": 30}, headers={
                                       "X-API-Key": self.operator["api_key"], "Idempotency-Key": "same-event"})
                return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(transfer, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 201)
        self.assertEqual(self.detail(order)["lines"][0]["balances"]["planned"], 70)
        self.assertEqual(len(self.client.get(f'/api/orders/{order["id"]}/movements').json()), 1)

    def test_revoked_key_cannot_read_or_retry_and_audit_is_immutable(self):
        order = self.order()
        line = order["lines"][0]["id"]
        self.move(line, "planned", "cutting", 20, key="before-revoke", api_key=self.operator["api_key"])
        self.app.state.store.disable_user(self.operator["id"])
        self.move(line, "planned", "cutting", 20, key="before-revoke", api_key=self.operator["api_key"], status=401)
        self.assertEqual(self.client.get("/api/orders", headers={"X-API-Key": self.operator["api_key"]}).status_code, 401)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM movements")

    def test_completed_order_and_pagination(self):
        order = self.order(10)
        line = order["lines"][0]["id"]
        for source, target in [("planned", "cutting"), ("cutting", "sewing"), ("sewing", "finishing"),
                               ("finishing", "qc"), ("qc", "warehouse")]:
            self.move(line, source, target, 10)
        self.assertEqual(self.detail(order)["status"], "completed")
        self.assertFalse(self.detail(order)["overdue"])
        history = self.client.get(f'/api/orders/{order["id"]}/movements?limit=2&offset=2').json()
        self.assertEqual([row["to_stage"] for row in history], ["finishing", "qc"])
        self.assertEqual(self.client.get("/api/orders?offset=1").json(), [])
        self.assertEqual(self.client.get("/api/orders?limit=1000").status_code, 422)

    def test_board_summary_covers_all_pages_and_filters_by_reference_or_sku(self):
        first = self.order(100, reference="BATCH-A")
        second = self.order(200, reference="BATCH-B", due_date="2099-01-01")
        self.move(first["lines"][0]["id"], "planned", "cutting", 30)
        response = self.client.get("/api/production-board?limit=1")
        self.assertEqual(response.status_code, 200, response.text)
        board = response.json()
        self.assertEqual(board["total"], 2)
        self.assertEqual(len(board["orders"]), 1)
        self.assertEqual(board["summary"], {"orders": 2, "active": 2, "overdue": 1,
                         "closed": 0, "in_progress": 30, "rework": 0})
        self.assertEqual(self.client.get("/api/production-board?q=batch-b").json()["orders"][0]["id"], second["id"])
        self.assertEqual(self.client.get("/api/production-board?q=luna-blue-m").json()["total"], 2)
        self.assertEqual(self.client.get("/api/production-board?status=overdue").json()["total"], 1)
        self.assertEqual(self.client.get("/api/production-board?q=missing").json()["total"], 0)
        self.assertEqual(self.client.get("/api/production-board?limit=1&offset=1").json()["orders"][0]["id"], second["id"])
        self.assertEqual(self.client.get("/api/production-board?status=invalid").status_code, 422)
        self.assertEqual(self.client.get("/api/production-board", headers={"X-API-Key": "invalid"}).status_code, 401)

    def test_empty_board_and_closed_order_counts(self):
        response = self.client.get("/api/production-board")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["summary"]["orders"], 0)
        self.assertEqual(response.json()["orders"], [])
        order = self.order(10)
        line = order["lines"][0]["id"]
        for source, target in [("planned", "cutting"), ("cutting", "sewing"), ("sewing", "finishing"),
                               ("finishing", "qc")]:
            self.move(line, source, target, 10)
        self.move(line, "qc", "warehouse", 9)
        self.move(line, "qc", "reject", 1, reason="Sobek")
        board = self.client.get("/api/production-board?status=closed").json()
        self.assertEqual(board["summary"], {"orders": 1, "active": 0, "overdue": 0,
                         "closed": 1, "in_progress": 0, "rework": 0})
        self.assertEqual(board["total"], 1)


if __name__ == "__main__":
    unittest.main()
