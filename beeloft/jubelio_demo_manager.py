"""Durable orchestration for the Jubelio Demo commerce connector."""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from uuid import uuid4

from beeloft.store import DomainError, Store, now
from beeloft.jubelio_demo import DEMO_ANCHOR_UTC, JubelioDemoDataset

LEASE = timedelta(minutes=15)
SCOPES = (
    ("finished_goods", "items", "import_jubelio_stock_snapshot"),
    ("orders", "orders", "import_jubelio_order_snapshot"),
    ("returns", "returns", "import_jubelio_return_snapshot"),
    ("listings", "listings", "import_jubelio_listing_snapshot"),
)


class JubelioDemoManager:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def _status(row, summary=None):
        return {
            "is_demo_database": bool(row["is_demo"]),
            "is_active": bool(row["demo_enabled"]),
            "anchor_at": row["anchor_at"],
            "current_scenario": row["current_scenario"],
            "is_locked": bool(row["is_locked"] and row["lock_expires_at"] > now()),
            "last_synced_at": row["last_synced_at"],
            "last_status": row["last_status"],
            "last_error": row["last_error"],
            "last_summary": summary if summary is not None else json.loads(row["last_summary_json"]),
        }

    def mark_as_demo_database(self, enabled=True):
        with self.store.transaction(write=True) as db:
            if not enabled:
                db.execute("""UPDATE jubelio_demo_state SET is_demo=0,demo_enabled=0,current_scenario=0,anchor_at='',
                    last_synced_at='',last_status='idle',last_error='',last_summary_json='{}',updated_at=?
                    WHERE id='singleton'""",(now(),))
            else:
                db.execute("UPDATE jubelio_demo_state SET is_demo=1,updated_at=? WHERE id='singleton'",(now(),))

    def is_demo_database(self):
        with self.store.transaction() as db:
            row = db.execute("SELECT is_demo FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            return bool(row and row["is_demo"])

    def get_status(self):
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if row is None:
                return {"is_demo_database": False, "is_active": False, "anchor_at": "", "current_scenario": 0,
                        "is_locked": False, "last_synced_at": "", "last_status": "idle",
                        "last_error": "", "last_summary": {}}
            return self._status(row)

    @staticmethod
    def _operation_key(kind, key):
        return f"jubelio-demo:{kind}:{key}"

    def _assert_key_unused_by_other_kind(self, actor, key, kind):
        with self.store.transaction() as db:
            rows = db.execute("SELECT request_key,actor_id FROM jubelio_demo_operations").fetchall()
        suffix = f":{key}"
        for row in rows:
            if not row["request_key"].endswith(suffix):
                continue
            if row["actor_id"] != actor["id"]:
                raise DomainError(403, "Idempotency-Key ini milik akun lain.")
            if row["request_key"] != self._operation_key(kind,key):
                raise DomainError(409, "Idempotency-Key sudah dipakai untuk aksi demo berbeda.")

    def _lookup_receipt(self, actor, key, kind, fingerprint):
        operation_key = self._operation_key(kind, key)
        with self.store.transaction() as db:
            receipt = db.execute("SELECT * FROM jubelio_demo_operations WHERE request_key=?", (operation_key,)).fetchone()
            if receipt is None:
                return None
            operation = dict(receipt)
            if operation["actor_id"] != actor["id"]:
                raise DomainError(403, "Idempotency-Key ini milik akun lain.")
            if operation["fingerprint"] != fingerprint:
                raise DomainError(409, "Idempotency-Key sudah dipakai untuk aksi demo berbeda.")
            if operation["response_json"] != "{}":
                retryable = db.execute("""SELECT 1 FROM jubelio_demo_operation_scopes
                    WHERE operation_id=? AND status IN ('pending','running','failed') LIMIT 1""",
                    (operation["id"],)).fetchone()
                if retryable is None:
                    return operation
            return None

    def _claim(self, actor, key, kind):
        operation_key = self._operation_key(kind, key)
        fingerprint = hashlib.sha256(json.dumps({"kind": kind}, sort_keys=True).encode()).hexdigest()
        self._assert_key_unused_by_other_kind(actor, key, kind)
        prior = self._lookup_receipt(actor, key, kind, fingerprint)
        if prior is not None:
            return prior, None, True
        token = str(uuid4())
        instant = now()
        expires = (datetime.now(timezone.utc) + LEASE).isoformat()
        with self.store.transaction(write=True) as db:
            state = db.execute("SELECT * FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if state is None:
                raise DomainError(400,"Database belum memiliki schema Jubelio Demo.")
            if not state["is_demo"]:
                raise DomainError(400, "Database ini bukan database demo.")
            if not state["demo_enabled"]:
                raise DomainError(409, "Aktifkan Jubelio Demo sebelum menjalankan sinkronisasi.")
            operation = db.execute("SELECT * FROM jubelio_demo_operations WHERE request_key=?", (operation_key,)).fetchone()
            if operation:
                operation = dict(operation)
                if operation["actor_id"] != actor["id"]:
                    raise DomainError(403, "Idempotency-Key ini milik akun lain.")
                if operation["fingerprint"] != fingerprint:
                    raise DomainError(409, "Idempotency-Key sudah dipakai untuk aksi demo berbeda.")
                scopes = db.execute("SELECT * FROM jubelio_demo_operation_scopes WHERE operation_id=? ORDER BY scope",
                                    (operation["id"],)).fetchall()
                retryable = any(scope["status"] in ("pending", "running", "failed") for scope in scopes)
                if operation["response_json"] != "{}" and not retryable:
                    return operation, None, True
                if state["is_locked"] and state["lock_expires_at"] > instant:
                    raise DomainError(409, "Sinkronisasi demo sedang berjalan.")
                op = {"id": operation["id"], "scenario": operation["scenario"], "kind": kind,
                      "anchor_at": operation["anchor_at"], "started_at": operation["started_at"],
                      "snapshot_at": operation["snapshot_at"]}
                db.execute("UPDATE jubelio_demo_operations SET status='running',error='',updated_at=? WHERE id=?",
                           (instant, op["id"]))
            else:
                if state["is_locked"] and state["lock_expires_at"] > instant:
                    raise DomainError(409, "Sinkronisasi demo sedang berjalan.")
                unresolved = db.execute("""SELECT 1 FROM jubelio_demo_operations o
                    JOIN jubelio_demo_operation_scopes s ON s.operation_id=o.id
                    WHERE o.status='failed' AND s.status IN ('pending','running','failed') LIMIT 1""").fetchone()
                if unresolved:
                    raise DomainError(409, "Ada scope gagal. Ulangi operasi sebelumnya dengan Idempotency-Key yang sama.")
                if kind == "next_scenario":
                    if state["current_scenario"] != 1:
                        raise DomainError(409, "Skenario berikutnya tersedia setelah baseline dan hanya satu kali.")
                    scenario = 2
                else:
                    scenario = state["current_scenario"] or 1
                op = {"id": str(uuid4()), "scenario": scenario, "kind": kind,
                      "anchor_at": state["anchor_at"] or DEMO_ANCHOR_UTC,
                      "started_at": instant, "snapshot_at": instant}
                db.execute("""INSERT INTO jubelio_demo_operations(id,request_key,actor_id,fingerprint,kind,scenario,
                    anchor_at,started_at,snapshot_at,status,error,summary_json,response_json,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,'running','','{}','{}',?,?)""",
                    (op["id"], operation_key, actor["id"], fingerprint, kind, scenario, op["anchor_at"],
                     instant, instant, instant, instant))
                for scope, _, _ in SCOPES:
                    db.execute("INSERT INTO jubelio_demo_operation_scopes(operation_id,scope,status,updated_at) VALUES(?,?,'pending',?)",
                               (op["id"], scope, instant))
            db.execute("""UPDATE jubelio_demo_state SET is_locked=1,lock_token=?,active_operation_id=?,
                lock_started_at=?,lock_expires_at=?,last_status='running',last_error='',updated_at=? WHERE id='singleton'""",
                (token, op["id"], instant, expires, instant))
            return op, token, False

    def _renew(self, op, token):
        instant = now()
        expires = (datetime.now(timezone.utc) + LEASE).isoformat()
        with self.store.transaction(write=True) as db:
            state = db.execute("SELECT lock_token,active_operation_id,lock_expires_at FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if (state["lock_token"] != token or state["active_operation_id"] != op["id"]
                    or state["lock_expires_at"] <= instant):
                raise DomainError(409, "Lease operasi demo kedaluwarsa atau sudah digantikan.")
            db.execute("UPDATE jubelio_demo_state SET lock_expires_at=?,updated_at=? WHERE id='singleton'", (expires, instant))

    def _save_scope(self, op, token, scope, result=None, error=""):
        instant = now()
        with self.store.transaction(write=True) as db:
            state = db.execute("SELECT lock_token,active_operation_id,lock_expires_at FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if (state["lock_token"] != token or state["active_operation_id"] != op["id"]
                    or state["lock_expires_at"] <= instant):
                raise DomainError(409, "Lease operasi demo kedaluwarsa atau sudah digantikan.")
            prior = db.execute("SELECT * FROM jubelio_demo_operation_scopes WHERE operation_id=? AND scope=?",
                               (op["id"], scope)).fetchone()
            if result is None:
                values = ("failed", prior["batch_id"], prior["records_read"], prior["accepted_count"],
                          prior["rejected_count"], error)
            else:
                values = ("attention" if result["rejected_count"] else "succeeded", result["id"],
                          result["records_read"], result["accepted_count"], result["rejected_count"], result.get("error", ""))
            db.execute("""UPDATE jubelio_demo_operation_scopes SET status=?,batch_id=?,records_read=?,accepted_count=?,
                rejected_count=?,error=?,attempts=attempts+1,updated_at=? WHERE operation_id=? AND scope=?""",
                (*values, instant, op["id"], scope))
            db.execute("UPDATE jubelio_demo_state SET lock_expires_at=?,updated_at=? WHERE id='singleton'",
                       ((datetime.now(timezone.utc) + LEASE).isoformat(), instant))

    def _finalize(self, op, token):
        with self.store.transaction(write=True) as db:
            state = db.execute("SELECT * FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if state["lock_token"] != token or state["active_operation_id"] != op["id"] or state["lock_expires_at"] <= now():
                raise DomainError(409, "Lease operasi demo kedaluwarsa atau sudah digantikan.")
            scopes = [dict(row) for row in db.execute(
                "SELECT * FROM jubelio_demo_operation_scopes WHERE operation_id=? ORDER BY scope", (op["id"],))]
            for scope in scopes:
                if scope["status"] == "running":
                    db.execute("""UPDATE jubelio_demo_operation_scopes SET status='failed',error='Sync interrupted',
                        updated_at=? WHERE operation_id=? AND scope=?""", (now(), op["id"], scope["scope"]))
                    scope["status"] = "failed"
                    scope["error"] = "Sync interrupted"
            summary = {
                "scenario": op["scenario"],
                "scenario_label": "Skenario 1 (Baseline)" if op["scenario"] == 1 else "Skenario 2 (Pembaruan transaksi & stok)",
                "total_accepted": sum(row["accepted_count"] for row in scopes),
                "total_quarantined": sum(row["rejected_count"] for row in scopes),
                "scopes": {row["scope"]: {"status": row["status"], "accepted": row["accepted_count"],
                    "quarantined": row["rejected_count"], "error": row["error"]} for row in scopes},
            }
            retryable = any(row["status"] in ("pending", "running", "failed") for row in scopes)
            quarantined = any(row["status"] == "attention" for row in scopes)
            status = "failed" if retryable or quarantined else "succeeded"
            errors = [f"{row['scope']}: {row['error']}" for row in scopes if row["status"] == "failed" and row["error"]]
            if quarantined:
                errors.append(f"{summary['total_quarantined']} record dikarantina; perbaiki mapping lalu jalankan sinkronisasi baru.")
            error = "; ".join(errors)
            scenario = state["current_scenario"] if retryable else op["scenario"]
            instant = now()
            if retryable:
                status = "failed"
                errors.append("Ada scope belum selesai. Ulangi request dengan key yang sama.")
            error = "; ".join(errors)
            scenario = state["current_scenario"] if retryable else op["scenario"]
            instant = now()
            db.execute("UPDATE jubelio_demo_operations SET status=?,error=?,summary_json=?,updated_at=? WHERE id=?",
                       (status, error, json.dumps(summary, ensure_ascii=False), instant, op["id"]))
            db.execute("""UPDATE jubelio_demo_state SET current_scenario=?,last_synced_at=?,last_status=?,last_error=?,
                last_summary_json=?,is_locked=0,lock_token='',active_operation_id='',lock_started_at='',lock_expires_at='',updated_at=?
                WHERE id='singleton' AND lock_token=?""",
                (scenario, instant, status, error, json.dumps(summary, ensure_ascii=False),
                 instant, token))
            row = dict(db.execute("SELECT * FROM jubelio_demo_state WHERE id='singleton'").fetchone())
            response = self._status(row, summary)
            db.execute("UPDATE jubelio_demo_operations SET response_json=?,updated_at=? WHERE id=?",
                       (json.dumps(response, ensure_ascii=False), instant, op["id"]))
            return response

    def _run(self, actor, key, kind):
        fingerprint = hashlib.sha256(json.dumps({"kind": kind}, sort_keys=True).encode()).hexdigest()
        receipt = self._lookup_receipt(actor, key, kind, fingerprint)
        if receipt is not None:
            return json.loads(receipt["response_json"])
        op, token, replay = self._claim(actor, key, kind)
        if replay:
            return json.loads(op["response_json"])
        dataset = JubelioDemoDataset.generate_baseline(op["anchor_at"]) if op["scenario"] == 1 else JubelioDemoDataset.generate_scenario_2(op["anchor_at"])
        try:
            for scope, payload_key, method_name in SCOPES:
                self._renew(op, token)
                with self.store.transaction(write=True) as db:
                    previous = db.execute("SELECT * FROM jubelio_demo_operation_scopes WHERE operation_id=? AND scope=?",
                                          (op["id"], scope)).fetchone()
                    if previous["status"] in ("succeeded", "attention"):
                        continue
                    db.execute("""UPDATE jubelio_demo_operation_scopes SET status='running',attempts=attempts+1,
                        updated_at=? WHERE operation_id=? AND scope=?""", (now(),op["id"],scope))
                payload = {"started_at": op["started_at"], "finished_at": op["snapshot_at"],
                    "snapshot_at": op["snapshot_at"], "external_cursor": f"jubelio-demo:{op['id']}:{scope}",
                    "reason": f"Jubelio Demo skenario {op['scenario']}", payload_key: dataset[payload_key]}
                try:
                    result = getattr(self.store, method_name)(payload, actor, f"jubelio-demo:{op['id']}:{scope}")
                    self._save_scope(op, token, scope, result=result)
                except Exception as error:
                    self._save_scope(op, token, scope, error=str(error))
            return self._finalize(op, token)
        except Exception as error:
            instant = now()
            with self.store.transaction(write=True) as db:
                state = db.execute("SELECT lock_token,active_operation_id FROM jubelio_demo_state WHERE id='singleton'").fetchone()
                if state["lock_token"] == token and state["active_operation_id"] == op["id"]:
                    db.execute("UPDATE jubelio_demo_operations SET status='failed',error=?,updated_at=? WHERE id=?",
                               (str(error), instant, op["id"]))
                    db.execute("""UPDATE jubelio_demo_operation_scopes SET status='failed',error=?,updated_at=?
                        WHERE operation_id=? AND status='running'""", (str(error), instant, op["id"]))
                    db.execute("""UPDATE jubelio_demo_state SET is_locked=0,lock_token='',active_operation_id='',
                        lock_started_at='',lock_expires_at='',last_status='failed',last_error=?,updated_at=?
                        WHERE id='singleton' AND lock_token=?""", (str(error), instant, token))
            raise

    def activate(self, actor, key):
        self._assert_key_unused_by_other_kind(actor,key,"activate")
        return self._activate(actor,key)

    def _activate(self, actor, key):
        fingerprint = hashlib.sha256(b"jubelio-demo-activate-v1").hexdigest()
        receipt_key = f"jubelio-demo-activate:{key}"
        token = str(uuid4())
        with self.store.transaction(write=True) as db:
            receipt = db.execute("SELECT actor_id,fingerprint,response FROM requests WHERE key=?", (receipt_key,)).fetchone()
            if receipt:
                if receipt["actor_id"] != actor["id"]:
                    raise DomainError(403, "Idempotency-Key ini milik akun lain.")
                if receipt["fingerprint"] != fingerprint:
                    raise DomainError(409, "Idempotency-Key konflik.")
                return json.loads(receipt["response"])
            existing_operation = db.execute("SELECT request_key FROM jubelio_demo_operations WHERE request_key LIKE ?",
                                            (f"jubelio-demo:%:{key}",)).fetchone()
            if existing_operation:
                raise DomainError(409, "Idempotency-Key sudah dipakai untuk aksi sinkronisasi.")
            state = db.execute("SELECT * FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if state is None:
                raise DomainError(400, "Database belum memiliki schema Jubelio Demo.")
            if not state["is_demo"]:
                raise DomainError(400, "Database ini bukan database demo.")
            if state["demo_enabled"]:
                response = self._status(state)
                db.execute("INSERT INTO requests(key,actor_id,fingerprint,response,created_at) VALUES(?,?,?,?,?)",
                           (receipt_key, actor["id"], fingerprint, json.dumps(response), now()))
                return response
            if state["is_locked"] and state["lock_expires_at"] > now():
                raise DomainError(409, "Aktivasi atau sync demo sedang berjalan.")
            instant = now()
            db.execute("""UPDATE jubelio_demo_state SET is_locked=1,lock_token=?,active_operation_id='activate',
                lock_started_at=?,lock_expires_at=?,last_status='running',last_error='',updated_at=? WHERE id='singleton'""",
                (token, instant, (datetime.now(timezone.utc) + LEASE).isoformat(), instant))
        try:
            for product in JubelioDemoDataset.products():
                with self.store.transaction() as db:
                    row = db.execute("SELECT id FROM products WHERE sku=? COLLATE NOCASE", (product["sku"],)).fetchone()
                item = ({"id": row["id"]} if row else self.store.create_product({"sku": product["sku"],
                    "name": product["name"], "color": product["color"], "size": product["size"]}, actor,
                    f"jubelio-demo-product-{product['sku']}"))
                if product["is_mapped"]:
                    mapping = self.store.product_external_mapping(item["id"], "jubelio")
                    if mapping["status"] != "mapped":
                        self.store.save_product_external_mapping(item["id"], "jubelio", {
                            "expected_revision": mapping["revision"], "action": "mapped",
                            "external_id": product["external_id"], "external_sku": product["external_sku"],
                            "reason": "Mapping dataset sintetis Jubelio Demo"}, actor,
                            f"jubelio-demo-map-{product['sku']}")
                self._renew({"id": "activate"}, token)
            with self.store.transaction(write=True) as db:
                state = db.execute("SELECT * FROM jubelio_demo_state WHERE id='singleton'").fetchone()
                if state["lock_token"] != token or state["active_operation_id"] != "activate":
                    raise DomainError(409, "Lease aktivasi sudah digantikan operasi lain.")
                anchor = state["anchor_at"] or DEMO_ANCHOR_UTC
                instant = now()
                db.execute("""UPDATE jubelio_demo_state SET demo_enabled=1,anchor_at=?,current_scenario=0,
                    last_synced_at='',last_status='idle',last_error='',last_summary_json='{}',updated_at=? WHERE id='singleton'""",
                    (anchor, instant))
                state = dict(db.execute("SELECT * FROM jubelio_demo_state WHERE id='singleton'").fetchone())
                response = self._status(state)
                db.execute("INSERT INTO requests(key,actor_id,fingerprint,response,created_at) VALUES(?,?,?,?,?)",
                           (receipt_key, actor["id"], fingerprint, json.dumps(response), instant))
                db.execute("""UPDATE jubelio_demo_state SET is_locked=0,lock_token='',active_operation_id='',
                    lock_started_at='',lock_expires_at='',updated_at=? WHERE id='singleton' AND lock_token=?""",
                    (instant, token))
                return response
        except Exception as error:
            with self.store.transaction(write=True) as db:
                db.execute("""UPDATE jubelio_demo_state SET is_locked=0,lock_token='',active_operation_id='',
                    lock_started_at='',lock_expires_at='',last_status='failed',last_error=?,updated_at=?
                    WHERE id='singleton' AND lock_token=?""", (str(error), now(), token))
            raise

    def sync(self, actor, key):
        return self._run(actor, key, "sync")

    def next_scenario(self, actor, key):
        return self._run(actor, key, "next_scenario")
