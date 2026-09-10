import hashlib
import json
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from beeloft.models import STAGES, TRANSITIONS, UserCreate

ACTIVITY_SQL = Path(__file__).with_name("activity.sql").read_text(encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


class DomainError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        super().__init__(message)


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3):
                raise RuntimeError(f"Unsupported database schema version: {version}")
            db.execute("PRAGMA journal_mode=WAL")
            if version == 0:
                db.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
            if version < 2:
                db.executescript(Path(__file__).with_name("issues.sql").read_text(encoding="utf-8"))
            if version < 3:
                db.executescript(Path(__file__).with_name("order_changes.sql").read_text(encoding="utf-8"))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def transaction(self, write=False):
        with closing(self.connect()) as db:
            # ponytail: SQLite serializes writers; move to PostgreSQL when lock waits limit throughput.
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def provision_user(self, name, role):
        user = UserCreate(name=name, role=role)
        key = secrets.token_urlsafe(32)
        record = {"id": str(uuid4()), "name": user.name, "role": user.role, "created_at": now()}
        with self.transaction(write=True) as db:
            db.execute("INSERT INTO users(id,name,role,key_hash,created_at) VALUES(?,?,?,?,?)",
                       (record["id"], record["name"], record["role"], hashlib.sha256(key.encode()).hexdigest(), record["created_at"]))
        return record | {"api_key": key}

    def authenticate(self, key):
        with self.transaction() as db:
            user = db.execute("SELECT id,name,role FROM users WHERE key_hash=? AND active=1",
                              (hashlib.sha256(key.encode()).hexdigest(),)).fetchone()
            if not user:
                raise DomainError(401, "API key tidak valid atau akun nonaktif.")
            return dict(user)

    def disable_user(self, user_id):
        with self.transaction(write=True) as db:
            updated = db.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
            if updated.rowcount != 1:
                raise DomainError(404, "Pengguna tidak ditemukan.")

    def users(self):
        with self.transaction() as db:
            return [dict(row) for row in db.execute("SELECT id,name,role,active FROM users ORDER BY name,id")]

    def _write(self, actor, roles, key, operation, payload, perform):
        fingerprint = hashlib.sha256(json.dumps([operation, payload], sort_keys=True).encode()).hexdigest()
        with self.transaction(write=True) as db:
            current = db.execute("SELECT role FROM users WHERE id=? AND active=1", (actor["id"],)).fetchone()
            if not current:
                raise DomainError(401, "Akun nonaktif.")
            if current["role"] not in roles:
                raise DomainError(403, "Role ini tidak diizinkan melakukan tindakan tersebut.")
            receipt = db.execute("SELECT fingerprint,response FROM requests WHERE actor_id=? AND key=?",
                                 (actor["id"], key)).fetchone()
            if receipt:
                if receipt["fingerprint"] != fingerprint:
                    raise DomainError(409, "Idempotency-Key sudah digunakan untuk request berbeda.")
                return json.loads(receipt["response"])
            result = perform(db)
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?)",
                       (actor["id"], key, fingerprint, json.dumps(result), now()))
            return result

    def create_product(self, payload, actor, key):
        def perform(db):
            record = {"id": str(uuid4()), **payload, "created_by": actor["id"], "created_at": now()}
            db.execute("INSERT INTO products VALUES(:id,:sku,:name,:color,:size,:created_by,:created_at)", record)
            return record
        return self._write(actor, ("admin",), key, "product", payload, perform)

    def products(self, limit=100, offset=0):
        with self.transaction() as db:
            return [dict(row) for row in db.execute("SELECT * FROM products ORDER BY sku LIMIT ? OFFSET ?", (limit, offset))]

    def create_order(self, payload, actor, key):
        def perform(db):
            owner = db.execute("SELECT role FROM users WHERE id=? AND active=1", (payload["owner_id"],)).fetchone()
            if not owner or owner["role"] not in ("admin", "operator"):
                raise DomainError(422, "PIC harus akun admin/operator yang aktif.")
            record = {"id": str(uuid4()), **{k: v for k, v in payload.items() if k != "lines"},
                      "created_by": actor["id"], "created_at": now()}
            db.execute("INSERT INTO orders VALUES(:id,:reference,:title,:owner_id,:due_date,:created_by,:created_at)", record)
            for item in payload["lines"]:
                if not db.execute("SELECT 1 FROM products WHERE id=?", (item["product_id"],)).fetchone():
                    raise DomainError(404, "SKU tidak ditemukan.")
                line = str(uuid4())
                db.execute("INSERT INTO order_lines VALUES(?,?,?,?)", (line, record["id"], item["product_id"], item["quantity"]))
                db.executemany("INSERT INTO balances VALUES(?,?,?)", [
                    (line, stage, item["quantity"] if stage == "planned" else 0) for stage in STAGES])
            return self._order(db, record["id"])
        return self._write(actor, ("admin",), key, "order", payload, perform)

    def _order(self, db, order_id):
        row = db.execute("SELECT o.*,u.name AS owner_name FROM orders o JOIN users u ON u.id=o.owner_id WHERE o.id=?", (order_id,)).fetchone()
        if not row:
            raise DomainError(404, "Order produksi tidak ditemukan.")
        result = dict(row)
        result["revision"] = db.execute("SELECT COALESCE(MAX(sequence),0) FROM order_changes WHERE order_id=?", (order_id,)).fetchone()[0]
        result["lines"] = []
        totals = dict.fromkeys(STAGES, 0)
        for row in db.execute("SELECT l.*,p.sku,p.name,p.color,p.size FROM order_lines l JOIN products p ON p.id=l.product_id WHERE l.order_id=? ORDER BY p.sku", (order_id,)):
            line = dict(row)
            line["balances"] = {r["stage"]: r["quantity"] for r in db.execute("SELECT stage,quantity FROM balances WHERE line_id=?", (line["id"],))}
            for stage, quantity in line["balances"].items():
                totals[stage] += quantity
            result["lines"].append(line)
        result["totals"] = totals
        result["target_quantity"] = sum(line["quantity"] for line in result["lines"])
        pending = result["target_quantity"] - totals["warehouse"] - totals["reject"]
        result["status"] = "active" if pending else ("closed_with_reject" if totals["reject"] else "completed")
        today = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
        result["overdue"] = pending > 0 and result["due_date"] < today
        result["open_issues"] = db.execute("""SELECT COUNT(*) FROM issues i JOIN order_lines l ON l.id=i.line_id
            WHERE l.order_id=? AND i.resolved_at IS NULL""", (order_id,)).fetchone()[0]
        return result

    def order(self, order_id):
        with self.transaction() as db:
            return self._order(db, order_id)

    def change_order(self, order_id, payload, actor, key):
        def perform(db):
            original = self._order(db, order_id)
            if original["revision"] != payload["expected_revision"]:
                raise DomainError(409, "Jadwal atau PIC sudah diubah. Tutup form, muat ulang order, lalu periksa perubahan terbaru.")
            if not db.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND role IN ('admin','operator')",
                              (payload["owner_id"],)).fetchone():
                raise DomainError(422, "PIC harus akun admin/operator yang aktif.")
            if original["due_date"] == payload["due_date"] and original["owner_id"] == payload["owner_id"]:
                raise DomainError(422, "Belum ada perubahan tenggat atau PIC.")
            record = {"id": str(uuid4()), "order_id": order_id, "old_due_date": original["due_date"],
                      "new_due_date": payload["due_date"], "old_owner_id": original["owner_id"],
                      "new_owner_id": payload["owner_id"], "reason": payload["reason"],
                      "actor_id": actor["id"], "created_at": now()}
            db.execute("UPDATE orders SET due_date=?,owner_id=? WHERE id=?", (payload["due_date"], payload["owner_id"], order_id))
            db.execute("""INSERT INTO order_changes(id,order_id,old_due_date,new_due_date,old_owner_id,new_owner_id,reason,actor_id,created_at)
                VALUES(:id,:order_id,:old_due_date,:new_due_date,:old_owner_id,:new_owner_id,:reason,:actor_id,:created_at)""", record)
            return self._order(db, order_id)
        return self._write(actor, ("admin",), key, "change-order:" + order_id, payload, perform)

    def order_changes(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM orders WHERE id=?", (order_id,)).fetchone():
                raise DomainError(404, "Order produksi tidak ditemukan.")
            return [dict(row) for row in db.execute("""SELECT c.*,a.name AS actor_name,
                old.name AS old_owner_name,new.name AS new_owner_name FROM order_changes c
                JOIN users a ON a.id=c.actor_id JOIN users old ON old.id=c.old_owner_id
                JOIN users new ON new.id=c.new_owner_id WHERE c.order_id=? AND (? IS NULL OR c.sequence<?)
                ORDER BY c.sequence DESC LIMIT ?""", (order_id, before, before, limit))]

    def orders(self, limit=100, offset=0):
        with self.transaction() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM orders ORDER BY due_date,created_at,id LIMIT ? OFFSET ?", (limit, offset))]
            return [self._order(db, order_id) for order_id in ids]

    def production_board(self, limit=25, offset=0, query="", status="all", owner_id="", stage="all"):
        totals = """WITH production AS (
            SELECT o.id,o.reference,o.title,o.due_date,o.created_at,o.owner_id,
                SUM(CASE WHEN b.stage NOT IN ('warehouse','reject') THEN b.quantity ELSE 0 END) AS pending,
                SUM(CASE WHEN b.stage IN ('cutting','sewing','finishing','qc','rework') THEN b.quantity ELSE 0 END) AS in_progress,
                SUM(CASE WHEN b.stage='rework' THEN b.quantity ELSE 0 END) AS rework
            FROM orders o JOIN order_lines l ON l.order_id=o.id
            JOIN balances b ON b.line_id=l.id GROUP BY o.id
        ) """
        filters = """ FROM production p WHERE
            (:status='all' OR (:status='active' AND p.pending>0)
                OR (:status='overdue' AND p.pending>0 AND p.due_date<:today)
                OR (:status='closed' AND p.pending=0)
                OR (:status='blocked' AND EXISTS(SELECT 1 FROM issues i JOIN order_lines l ON l.id=i.line_id
                    WHERE l.order_id=p.id AND i.resolved_at IS NULL)))
            AND (:owner_id='' OR p.owner_id=:owner_id)
            AND (:stage='all' OR EXISTS(SELECT 1 FROM order_lines l JOIN balances b ON b.line_id=l.id
                WHERE l.order_id=p.id AND b.stage=:stage AND b.quantity>0))
            AND (:query='' OR instr(lower(p.reference),:query)>0 OR instr(lower(p.title),:query)>0
                OR EXISTS(SELECT 1 FROM order_lines l JOIN products s ON s.id=l.product_id
                    WHERE l.order_id=p.id AND (instr(lower(s.sku),:query)>0 OR instr(lower(s.name),:query)>0))) """
        params = {"today": datetime.now(timezone(timedelta(hours=7))).date().isoformat(),
                  "query": query.strip().lower(), "status": status, "limit": limit, "offset": offset,
                  "owner_id": owner_id, "stage": stage}
        with self.transaction() as db:
            row = db.execute(totals + """SELECT COUNT(*) AS orders,
                SUM(pending>0) AS active,SUM(pending>0 AND due_date<:today) AS overdue,
                SUM(pending=0) AS closed,SUM(in_progress) AS in_progress,SUM(rework) AS rework
                FROM production""", params).fetchone()
            summary = {key: value or 0 for key, value in dict(row).items()}
            count = db.execute(totals + "SELECT COUNT(*)" + filters, params).fetchone()[0]
            ids = [r[0] for r in db.execute(totals + "SELECT p.id" + filters +
                                           "ORDER BY p.due_date,p.created_at,p.id LIMIT :limit OFFSET :offset", params)]
            return {"summary": summary, "total": count, "limit": limit, "offset": offset,
                    "owners": [dict(row) for row in db.execute("""SELECT u.id,u.name,u.active FROM users u
                        WHERE EXISTS(SELECT 1 FROM orders o WHERE o.owner_id=u.id) ORDER BY u.name,u.id""")],
                    "open_issues": db.execute("SELECT COUNT(*) FROM issues WHERE resolved_at IS NULL").fetchone()[0],
                    "orders": [self._order(db, order_id) for order_id in ids]}

    def create_issue(self, payload, actor, key):
        def perform(db):
            if not db.execute("SELECT 1 FROM order_lines WHERE id=?", (payload["line_id"],)).fetchone():
                raise DomainError(404, "Baris produksi tidak ditemukan.")
            if not db.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND role IN ('admin','operator')",
                              (payload["owner_id"],)).fetchone():
                raise DomainError(422, "PIC kendala harus akun admin/operator yang aktif.")
            record = {"id": str(uuid4()), **payload, "created_by": actor["id"], "created_at": now(),
                      "resolution": None, "resolved_by": None, "resolved_at": None}
            db.execute("""INSERT INTO issues(id,line_id,stage,description,owner_id,created_by,created_at)
                VALUES(:id,:line_id,:stage,:description,:owner_id,:created_by,:created_at)""", record)
            return record
        return self._write(actor, ("admin", "operator"), key, "issue", payload, perform)

    def resolve_issue(self, issue_id, payload, actor, key):
        def perform(db):
            issue = db.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
            if not issue:
                raise DomainError(404, "Kendala tidak ditemukan.")
            if issue["resolved_at"]:
                raise DomainError(409, "Kendala sudah selesai. Muat ulang untuk melihat catatannya.")
            record = dict(issue) | payload | {"resolved_by": actor["id"], "resolved_at": now()}
            db.execute("UPDATE issues SET resolution=:resolution,resolved_by=:resolved_by,resolved_at=:resolved_at WHERE id=:id", record)
            return record
        return self._write(actor, ("admin", "operator"), key, "resolve-issue:" + issue_id, payload, perform)

    def issues(self, order_id, limit=100, offset=0, before=None):
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM orders WHERE id=?", (order_id,)).fetchone():
                raise DomainError(404, "Order produksi tidak ditemukan.")
            return [dict(row) for row in db.execute("""SELECT i.*,p.sku,u.name AS owner_name,
                u.active AS owner_active,c.name AS creator_name,r.name AS resolver_name
                FROM issues i JOIN order_lines l ON l.id=i.line_id JOIN products p ON p.id=l.product_id
                JOIN users u ON u.id=i.owner_id JOIN users c ON c.id=i.created_by
                LEFT JOIN users r ON r.id=i.resolved_by
                WHERE l.order_id=? AND (? IS NULL OR i.sequence<?)
                ORDER BY i.sequence DESC LIMIT ? OFFSET ?""", (order_id, before, before, limit, offset))]

    def _transfer(self, db, payload, actor, reversal_of=None):
        line = db.execute("SELECT quantity FROM order_lines WHERE id=?", (payload["line_id"],)).fetchone()
        if not line:
            raise DomainError(404, "Baris produksi tidak ditemukan.")
        updated = db.execute("UPDATE balances SET quantity=quantity-? WHERE line_id=? AND stage=? AND quantity>=?",
                             (payload["quantity"], payload["line_id"], payload["from_stage"], payload["quantity"]))
        if updated.rowcount != 1:
            raise DomainError(409, "Jumlah melebihi saldo tahap sumber. Muat ulang posisi barang.")
        updated = db.execute("UPDATE balances SET quantity=quantity+? WHERE line_id=? AND stage=?",
                             (payload["quantity"], payload["line_id"], payload["to_stage"]))
        if updated.rowcount != 1:
            raise DomainError(409, "Saldo tahap tujuan tidak ditemukan.")
        total = db.execute("SELECT SUM(quantity) FROM balances WHERE line_id=?", (payload["line_id"],)).fetchone()[0]
        if total != line["quantity"]:
            raise DomainError(409, "Saldo tidak seimbang; transaksi dibatalkan.")
        record = {"id": str(uuid4()), **payload, "actor_id": actor["id"], "created_at": now(), "reversal_of": reversal_of}
        db.execute("""INSERT INTO movements(id,line_id,from_stage,to_stage,quantity,reason,actor_id,created_at,reversal_of)
                      VALUES(:id,:line_id,:from_stage,:to_stage,:quantity,:reason,:actor_id,:created_at,:reversal_of)""", record)
        return record

    def move(self, payload, actor, key):
        def perform(db):
            if (payload["from_stage"], payload["to_stage"]) not in TRANSITIONS:
                raise DomainError(422, "Perpindahan tahap tidak diizinkan. Gunakan pembalikan untuk koreksi.")
            if payload["to_stage"] in ("rework", "reject") and not payload["reason"].strip():
                raise DomainError(422, "Alasan wajib untuk rework atau reject.")
            return self._transfer(db, payload, actor)
        return self._write(actor, ("admin", "operator"), key, "move", payload, perform)

    def reverse(self, movement_id, payload, actor, key):
        def perform(db):
            original = db.execute("SELECT * FROM movements WHERE id=?", (movement_id,)).fetchone()
            if not original:
                raise DomainError(404, "Perpindahan tidak ditemukan.")
            if original["reversal_of"] or db.execute("SELECT 1 FROM movements WHERE reversal_of=?", (movement_id,)).fetchone():
                raise DomainError(409, "Catatan pembalik atau transaksi yang sudah dibalik tidak dapat dibalik lagi.")
            movement = {"line_id": original["line_id"], "from_stage": original["to_stage"],
                        "to_stage": original["from_stage"], "quantity": original["quantity"], "reason": payload["reason"]}
            return self._transfer(db, movement, actor, reversal_of=movement_id)
        return self._write(actor, ("admin",), key, "reverse:" + movement_id, payload, perform)

    def history(self, order_id, limit=100, offset=0):
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM orders WHERE id=?", (order_id,)).fetchone():
                raise DomainError(404, "Order produksi tidak ditemukan.")
            return [dict(row) for row in db.execute("""SELECT m.*,u.name AS actor_name,p.sku FROM movements m
                JOIN order_lines l ON l.id=m.line_id JOIN users u ON u.id=m.actor_id
                JOIN products p ON p.id=l.product_id WHERE l.order_id=? ORDER BY m.sequence LIMIT ? OFFSET ?""",
                (order_id, limit, offset))]

    def activity(self, day=None, kind="all", limit=50, before_time=None, before_id=None, start_date=None, end_date=None):
        jakarta = timezone(timedelta(hours=7))
        if day and (start_date or end_date):
            raise DomainError(422, "Gunakan day atau rentang start_date/end_date, bukan keduanya.")
        if bool(start_date) != bool(end_date):
            raise DomainError(422, "Tanggal awal dan akhir harus diisi bersama.")
        start_date = start_date or day or datetime.now(jakarta).date()
        end_date = end_date or start_date
        if not 0 <= (end_date - start_date).days < 366:
            raise DomainError(422, "Rentang tanggal harus berurutan dan maksimal 366 hari.")
        try:
            start = datetime.combine(start_date, time(), jakarta).astimezone(timezone.utc)
            end = start + timedelta(days=(end_date - start_date).days + 1)
        except (OverflowError, ValueError):
            raise DomainError(422, "Tanggal di luar jangkauan laporan.")
        if bool(before_time) != bool(before_id):
            raise DomainError(422, "Cursor membutuhkan before_time dan before_id.")
        params = {"start": start.isoformat(), "end": end.isoformat(), "kind": kind,
                  "limit": limit + 1, "before_time": before_time, "before_id": before_id}
        filtered = " FROM daily d WHERE (:kind='all' OR d.kind=:kind) "
        with self.transaction() as db:
            summary = dict(db.execute(ACTIVITY_SQL + """SELECT COUNT(*) AS events,
                COALESCE(SUM(CASE WHEN kind IN ('movement','reversal') THEN
                    CASE WHEN to_stage='warehouse' THEN quantity WHEN from_stage='warehouse' THEN -quantity ELSE 0 END ELSE 0 END),0) AS warehouse_net,
                COALESCE(SUM(kind='issue_opened'),0) AS issues_opened,
                COALESCE(SUM(kind='issue_resolved'),0) AS issues_resolved FROM daily""", params).fetchone())
            total = db.execute(ACTIVITY_SQL + "SELECT COUNT(*)" + filtered, params).fetchone()[0]
            rows = [dict(row) for row in db.execute(ACTIVITY_SQL + """SELECT d.*,o.reference,o.title,
                u.name AS actor_name,p.sku FROM daily d JOIN orders o ON o.id=d.order_id
                JOIN users u ON u.id=d.actor_id LEFT JOIN order_lines l ON l.id=d.line_id
                LEFT JOIN products p ON p.id=l.product_id WHERE (:kind='all' OR d.kind=:kind)
                AND (:before_time IS NULL OR d.created_at<:before_time
                    OR (d.created_at=:before_time AND d.event_id<:before_id))
                ORDER BY d.created_at DESC,d.event_id DESC LIMIT :limit""", params)]
            more = len(rows) > limit
            rows = rows[:limit]
            for row in rows:
                row["details"] = json.loads(row["details"])
            return {"day": start_date.isoformat(), "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
                    "timezone": "Asia/Jakarta", "summary": summary,
                    "total": total, "items": rows,
                    "next_before": {"before_time": rows[-1]["created_at"], "before_id": rows[-1]["event_id"]} if more else None}

    def backup(self, destination):
        destination = Path(destination).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb"):
            pass
        try:
            with closing(self.connect()) as source, closing(sqlite3.connect(destination)) as target:
                source.backup(target)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
