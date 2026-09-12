import hashlib
import json
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
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
            if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24):
                raise RuntimeError(f"Unsupported database schema version: {version}")
            db.execute("PRAGMA journal_mode=WAL")
            if version == 0:
                db.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
            if version < 2:
                db.executescript(Path(__file__).with_name("issues.sql").read_text(encoding="utf-8"))
            if version < 3:
                db.executescript(Path(__file__).with_name("order_changes.sql").read_text(encoding="utf-8"))
            if version < 4:
                db.executescript(Path(__file__).with_name("materials.sql").read_text(encoding="utf-8"))
            if version < 5:
                db.executescript(Path(__file__).with_name("bom.sql").read_text(encoding="utf-8"))
            if version < 6:
                db.executescript(Path(__file__).with_name("reservations.sql").read_text(encoding="utf-8"))
            if version < 7:
                db.executescript(Path(__file__).with_name("consumption.sql").read_text(encoding="utf-8"))
            if version < 8:
                db.executescript(Path(__file__).with_name("purchase_requests.sql").read_text(encoding="utf-8"))
            if version < 9:
                db.executescript(Path(__file__).with_name("purchase_orders.sql").read_text(encoding="utf-8"))
            if version < 10:
                db.executescript(Path(__file__).with_name("po_receipts.sql").read_text(encoding="utf-8"))
            if version < 11:
                db.executescript(Path(__file__).with_name("incoming_qc.sql").read_text(encoding="utf-8"))
            if version < 12:
                db.executescript(Path(__file__).with_name("supplier_returns.sql").read_text(encoding="utf-8"))
            if version < 13:
                db.executescript(Path(__file__).with_name("cutting.sql").read_text(encoding="utf-8"))
            if version < 14:
                db.executescript(Path(__file__).with_name("bundles.sql").read_text(encoding="utf-8"))
            if version < 15:
                db.executescript(Path(__file__).with_name("sewing.sql").read_text(encoding="utf-8"))
            if version < 16:
                db.executescript(Path(__file__).with_name("finishing.sql").read_text(encoding="utf-8"))
            if version < 17:
                db.executescript(Path(__file__).with_name("final_qc.sql").read_text(encoding="utf-8"))
            if version < 18:
                columns={row['name'] for row in db.execute('PRAGMA table_info(final_qc_records)')}
                additions={
                    'defect_type':"TEXT NOT NULL DEFAULT '' CHECK(defect_type=trim(defect_type) AND length(defect_type) BETWEEN 0 AND 160)",
                    'responsible_source':"TEXT NOT NULL DEFAULT '' CHECK(responsible_source=trim(responsible_source) AND length(responsible_source) BETWEEN 0 AND 160)",
                    'disposition':"TEXT NOT NULL DEFAULT '' CHECK(disposition=trim(disposition) AND length(disposition) BETWEEN 0 AND 1000)"}
                for name,definition in additions.items():
                    if name not in columns:
                        db.execute(f'ALTER TABLE final_qc_records ADD COLUMN {name} {definition}')
                db.executescript(Path(__file__).with_name("finished_goods.sql").read_text(encoding="utf-8"))
            if version < 19:
                db.executescript(Path(__file__).with_name("warehouse_movements.sql").read_text(encoding="utf-8"))
            if version < 20:
                db.executescript(Path(__file__).with_name("marketplace_reservations.sql").read_text(encoding="utf-8"))
            if version < 21:
                db.executescript(Path(__file__).with_name("marketplace_picking.sql").read_text(encoding="utf-8"))
            if version < 22:
                db.executescript(Path(__file__).with_name("marketplace_packing.sql").read_text(encoding="utf-8"))
            if version < 23:
                db.executescript(Path(__file__).with_name("marketplace_shipping.sql").read_text(encoding="utf-8"))
            if version < 24:
                db.executescript(Path(__file__).with_name("returns_adjustments.sql").read_text(encoding="utf-8"))

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

    def create_material(self, payload, actor, key):
        def perform(db):
            record = {'id':str(uuid4()), **payload, 'created_by':actor['id'], 'created_at':now()}
            db.execute('INSERT INTO materials VALUES(:id,:code,:name,:unit,:created_by,:created_at)', record)
            return record
        return self._write(actor, ('admin',), key, 'material', payload, perform)

    def materials(self, limit=100, offset=0):
        with self.transaction() as db:
            return [dict(row) for row in db.execute('SELECT * FROM materials ORDER BY code,id LIMIT ? OFFSET ?', (limit, offset))]

    @staticmethod
    def _material_amount(quantity, unit):
        amount = Decimal(quantity)
        if not amount.is_finite() or not 0 < amount <= 1_000_000 or amount * 1000 != (amount * 1000).to_integral_value():
            raise DomainError(422, 'Jumlah bahan harus positif, maksimal 1.000.000 dengan tiga desimal.')
        if unit == 'pcs' and amount != amount.to_integral_value():
            raise DomainError(422, 'Bahan dengan satuan pcs harus berjumlah bulat.')
        return int(amount * 1000)

    @staticmethod
    def _material_decimal(milli):
        return format(Decimal(milli) / 1000, '.3f')

    def _material_batch(self, db, batch_id, order_id=None):
        row = db.execute('''SELECT b.*,m.code,m.name,m.unit,
            (SELECT COALESCE(SUM(quantity_milli),0) FROM material_movements WHERE batch_id=b.id) AS balance_milli,
            (SELECT id FROM material_movements WHERE batch_id=b.id AND kind='receipt') AS receipt_id
            FROM material_batches b JOIN materials m ON m.id=b.material_id WHERE b.id=?''', (batch_id,)).fetchone()
        if not row:
            raise DomainError(404, 'Batch bahan tidak ditemukan.')
        record = dict(row)
        source = db.execute('''SELECT p.id,p.reference,
            EXISTS(SELECT 1 FROM purchase_order_closures WHERE order_id=p.id) AS closed FROM purchase_order_receipts r
            JOIN purchase_orders p ON p.id=r.purchase_order_id WHERE r.batch_id=?''', (batch_id,)).fetchone()
        record['purchase_order_id'] = source['id'] if source else None
        record['purchase_order_reference'] = source['reference'] if source else None
        record['po_closed'] = bool(source and source['closed'])
        balance = record.pop('balance_milli')
        reserved = db.execute('SELECT COALESCE(SUM(quantity_milli),0) FROM material_reservation_events WHERE batch_id=?', (batch_id,)).fetchone()[0]
        own = db.execute('SELECT COALESCE(SUM(quantity_milli),0) FROM material_reservation_events WHERE batch_id=? AND order_id=?', (batch_id,order_id)).fetchone()[0]
        record.update({key:self._material_decimal(value) for key,value in dict(balance=balance,reserved=reserved,
                      available=balance-reserved,reserved_for_order=own,available_to_order=balance-reserved+own).items()})
        qc = db.execute('SELECT intake_id FROM qc_decisions WHERE batch_id=?', (batch_id,)).fetchone()
        record['qc_intake_id'] = qc['intake_id'] if qc else None
        return record

    def material_batch(self, batch_id):
        with self.transaction() as db:
            return self._material_batch(db, batch_id)

    def material_batches(self, limit=100, offset=0, material_id='', order_id=None):
        with self.transaction() as db:
            ids = db.execute('''SELECT id FROM material_batches WHERE (?='' OR material_id=?)
                ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?''', (material_id, material_id, limit, offset)).fetchall()
            if order_id is not None and not db.execute('SELECT 1 FROM orders WHERE id=?', (order_id,)).fetchone():
                raise DomainError(404, 'Order produksi tidak ditemukan.')
            return [self._material_batch(db, row[0], order_id) for row in ids]

    def _material_movement(self, db, batch_id, kind, quantity, order_id, reason, actor_id, reversal_of=None):
        record = dict(id=str(uuid4()), batch_id=batch_id, kind=kind, quantity_milli=quantity,
                      order_id=order_id, reason=reason, actor_id=actor_id, created_at=now(), reversal_of=reversal_of)
        db.execute('''INSERT INTO material_movements(id,batch_id,kind,quantity_milli,order_id,reversal_of,reason,actor_id,created_at)
            VALUES(:id,:batch_id,:kind,:quantity_milli,:order_id,:reversal_of,:reason,:actor_id,:created_at)''', record)
        record['quantity'] = self._material_decimal(record.pop('quantity_milli'))
        return record

    def receive_material(self, payload, actor, key):
        return self._write(actor, ('admin','operator'), key, 'material-receipt', payload,
                           lambda db: self._receive_material(db, payload, actor))

    def _receive_material(self, db, payload, actor):
        material = db.execute('SELECT unit FROM materials WHERE id=?', (payload['material_id'],)).fetchone()
        if not material:
            raise DomainError(404, 'Bahan tidak ditemukan.')
        quantity = self._material_amount(payload['quantity'], material['unit'])
        record = {k:v for k,v in payload.items() if k not in ('quantity','reason')}
        record.update(id=str(uuid4()), created_by=actor['id'], created_at=now())
        db.execute('''INSERT INTO material_batches VALUES(:id,:material_id,:reference,:supplier,:location,
            :received_date,:created_by,:created_at)''', record)
        self._material_movement(db, record['id'], 'receipt', quantity, None, payload['reason'], actor['id'])
        return self._material_batch(db, record['id'])

    def issue_material(self, payload, actor, key):
        def perform(db):
            batch = self._material_batch(db, payload['batch_id'], payload['order_id'])
            if not db.execute('SELECT 1 FROM orders WHERE id=?', (payload['order_id'],)).fetchone():
                raise DomainError(404, 'Order produksi tidak ditemukan.')
            quantity = self._material_amount(payload['quantity'], batch['unit'])
            if Decimal(batch['available_to_order']) * 1000 < quantity:
                raise DomainError(409, 'Bahan untuk order ini tidak cukup. Stok yang direservasi order lain tidak boleh dikeluarkan.')
            movement = self._material_movement(db, batch['id'], 'issue', -quantity, payload['order_id'], payload['reason'], actor['id'])
            consumed = min(quantity, int(Decimal(batch['reserved_for_order']) * 1000))
            if consumed:
                self._reservation_event(db,batch['id'],payload['order_id'],'consume',-consumed,payload['reason'],actor['id'],movement['id'])
            return movement
        return self._write(actor, ('admin','operator'), key, 'material-issue', payload, perform)

    def reverse_material(self, movement_id, payload, actor, key):
        def perform(db):
            if db.execute("""SELECT 1 FROM qc_decisions q JOIN material_movements m ON m.batch_id=q.batch_id
                WHERE m.id=? AND m.kind='receipt'""", (movement_id,)).fetchone():
                raise DomainError(409, 'Penerimaan berasal dari QC. Gunakan koreksi keputusan QC agar jumlah hold ikut diperbarui.')
            return self._reverse_material(db, movement_id, payload, actor)
        return self._write(actor, ('admin',), key, 'material-reverse:'+movement_id, payload, perform)

    def _reverse_material(self, db, movement_id, payload, actor):
        original = db.execute('SELECT * FROM material_movements WHERE id=?', (movement_id,)).fetchone()
        if not original:
            raise DomainError(404, 'Catatan bahan tidak ditemukan.')
        if original['kind'] == 'reversal' or db.execute('SELECT 1 FROM material_movements WHERE reversal_of=?', (movement_id,)).fetchone():
            raise DomainError(409, 'Catatan pembalik atau catatan yang sudah dibalik tidak dapat dikoreksi lagi.')
        if original['kind']=='receipt' and db.execute('''SELECT 1 FROM purchase_order_receipts x
            JOIN purchase_order_closures c ON c.order_id=x.purchase_order_id WHERE x.batch_id=?''', (original['batch_id'],)).fetchone():
            raise DomainError(409, 'PO sudah ditutup; penerimaan sudah final.')
        balance = db.execute('SELECT SUM(quantity_milli) FROM material_movements WHERE batch_id=?', (original['batch_id'],)).fetchone()[0]
        if balance - original['quantity_milli'] < 0:
            raise DomainError(409, 'Bahan sudah dikeluarkan. Periksa dan kembalikan pengeluaran terkait sebelum membalik penerimaan.')
        if original['kind']=='receipt' and db.execute('SELECT COALESCE(SUM(quantity_milli),0) FROM material_reservation_events WHERE batch_id=?', (original['batch_id'],)).fetchone()[0]:
            raise DomainError(409, 'Batch masih direservasi. Lepaskan seluruh reservasi sebelum membalik penerimaan.')
        if original['kind']=='issue' and db.execute('SELECT COALESCE(SUM(used_milli+waste_milli),0) FROM material_consumption WHERE issue_id=?',(movement_id,)).fetchone()[0]:
            raise DomainError(409,'Pengeluaran sudah dicatat terpakai atau waste. Periksa dan koreksi catatan pemakaian sebelum mengembalikan seluruh pengeluaran.')
        return self._material_movement(db, original['batch_id'], 'reversal', -original['quantity_milli'],
            original['order_id'], payload['reason'], actor['id'], movement_id)

    def material_history(self, *, batch_id=None, order_id=None, limit=100, before=None):
        with self.transaction() as db:
            if batch_id is not None:
                self._material_batch(db, batch_id)
            elif not db.execute('SELECT 1 FROM orders WHERE id=?', (order_id,)).fetchone():
                raise DomainError(404, 'Order produksi tidak ditemukan.')
            rows = db.execute('''SELECT x.*,b.reference AS batch_reference,b.location,m.code,m.unit,u.name AS actor_name,
                o.reference AS order_reference,(SELECT id FROM material_movements WHERE reversal_of=x.id) AS reversed_by
                FROM material_movements x JOIN material_batches b ON b.id=x.batch_id
                JOIN materials m ON m.id=b.material_id JOIN users u ON u.id=x.actor_id LEFT JOIN orders o ON o.id=x.order_id
                WHERE (? IS NULL OR x.batch_id=?) AND (? IS NULL OR x.order_id=?) AND (? IS NULL OR x.sequence<?)
                ORDER BY x.sequence DESC LIMIT ?''', (batch_id,batch_id,order_id,order_id,before,before,limit)).fetchall()
            result = []
            for row in rows:
                record = dict(row)
                record['quantity'] = self._material_decimal(record.pop('quantity_milli'))
                result.append(record)
            return result

    def _reservation_event(self, db, batch_id, order_id, kind, quantity, reason, actor_id, movement_id=None):
        record=dict(id=str(uuid4()),batch_id=batch_id,order_id=order_id,kind=kind,quantity_milli=quantity,
                    reason=reason,actor_id=actor_id,movement_id=movement_id,created_at=now())
        db.execute('''INSERT INTO material_reservation_events(id,batch_id,order_id,kind,quantity_milli,movement_id,reason,actor_id,created_at)
            VALUES(:id,:batch_id,:order_id,:kind,:quantity_milli,:movement_id,:reason,:actor_id,:created_at)''',record)
        record['quantity']=self._material_decimal(record.pop('quantity_milli'))
        return record

    def reserve_material(self, payload, actor, key):
        def perform(db):
            batch=self._material_batch(db,payload['batch_id'],payload['order_id'])
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(payload['order_id'],)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            quantity=self._material_amount(payload['quantity'],batch['unit'])
            field='available' if payload['action']=='reserve' else 'reserved_for_order'
            if quantity>Decimal(batch[field])*1000:
                raise DomainError(409,'Jumlah melebihi stok bebas atau reservasi order ini. Muat ulang dan periksa alokasi terbaru.')
            return self._reservation_event(db,batch['id'],payload['order_id'],payload['action'],
                quantity if payload['action']=='reserve' else -quantity,payload['reason'],actor['id'])
        return self._write(actor,('admin',),key,'material-reservation',payload,perform)

    def order_reservations(self, order_id, limit=100, offset=0):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT DISTINCT batch_id FROM material_reservation_events WHERE order_id=?
                ORDER BY batch_id LIMIT ? OFFSET ?''',(order_id,limit,offset)).fetchall()
            return [self._material_batch(db,row[0],order_id) for row in ids]

    def reservation_history(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            rows=db.execute('''SELECT e.*,b.reference AS batch_reference,m.code,m.unit,u.name AS actor_name
                FROM material_reservation_events e JOIN material_batches b ON b.id=e.batch_id
                JOIN materials m ON m.id=b.material_id JOIN users u ON u.id=e.actor_id
                WHERE e.order_id=? AND (? IS NULL OR e.sequence<?) ORDER BY e.sequence DESC LIMIT ?''',(order_id,before,before,limit)).fetchall()
            result=[]
            for row in rows:
                record=dict(row);record['quantity']=self._material_decimal(record.pop('quantity_milli'));result.append(record)
            return result

    def _issue_consumption(self, db, issue_id):
        row=db.execute('''SELECT m.id AS issue_id,m.batch_id,m.order_id,m.quantity_milli,m.created_at,m.reason,
            b.reference AS batch_reference,b.location,s.code,s.name,s.unit,
            (SELECT id FROM material_movements WHERE reversal_of=m.id) AS reversed_by,
            (SELECT COALESCE(SUM(used_milli),0) FROM material_consumption WHERE issue_id=m.id) AS used_milli,
            (SELECT COALESCE(SUM(waste_milli),0) FROM material_consumption WHERE issue_id=m.id) AS waste_milli
            FROM material_movements m JOIN material_batches b ON b.id=m.batch_id JOIN materials s ON s.id=b.material_id
            WHERE m.id=? AND m.kind='issue' ''',(issue_id,)).fetchone()
        if not row:
            if db.execute('SELECT 1 FROM material_movements WHERE id=?',(issue_id,)).fetchone():
                raise DomainError(422,'Pemakaian harus merujuk catatan pengeluaran bahan.')
            raise DomainError(404,'Pengeluaran bahan tidak ditemukan.')
        record=dict(row)
        issued=-record.pop('quantity_milli');used=record.pop('used_milli');waste=record.pop('waste_milli')
        record.update({key:self._material_decimal(value) for key,value in dict(issued=issued,used=used,waste=waste,
                      unreported=0 if record['reversed_by'] else issued-used-waste).items()})
        return record

    def order_consumption(self, order_id, limit=100, offset=0):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT id FROM material_movements WHERE order_id=? AND kind='issue'
                ORDER BY sequence DESC LIMIT ? OFFSET ?''',(order_id,limit,offset)).fetchall()
            return [self._issue_consumption(db,row[0]) for row in ids]

    def _consumption_event(self, db, issue_id, used, waste, reason, actor_id, reversal_of=None):
        record=dict(id=str(uuid4()),issue_id=issue_id,used_milli=used,waste_milli=waste,reason=reason,
                    actor_id=actor_id,created_at=now(),reversal_of=reversal_of)
        db.execute('''INSERT INTO material_consumption(id,issue_id,used_milli,waste_milli,reversal_of,reason,actor_id,created_at)
            VALUES(:id,:issue_id,:used_milli,:waste_milli,:reversal_of,:reason,:actor_id,:created_at)''',record)
        record['used']=self._material_decimal(record.pop('used_milli'));record['waste']=self._material_decimal(record.pop('waste_milli'))
        return record

    def consume_material(self, payload, actor, key):
        return self._write(actor,('admin','operator'),key,'material-consumption',payload,
                           lambda db: self._consume_material(db,payload,actor))

    def _consume_material(self, db, payload, actor):
        issue=self._issue_consumption(db,payload['issue_id'])
        if issue['reversed_by']:
            raise DomainError(409,'Pengeluaran sudah dibalik, tidak dapat dicatat pemakaiannya.')
        amounts=[0 if Decimal(payload[field])==0 else self._material_amount(payload[field],issue['unit']) for field in ('used','waste')]
        if sum(amounts)==0:
            raise DomainError(422,'Isi jumlah terpakai atau waste lebih dari nol.')
        if sum(amounts)>Decimal(issue['unreported'])*1000:
            raise DomainError(409,'Terpakai + waste melebihi jumlah yang belum dilaporkan. Muat ulang dan periksa catatan terbaru.')
        return self._consumption_event(db,issue['issue_id'],*amounts,payload['reason'],actor['id'])

    def reverse_consumption(self, consumption_id, payload, actor, key):
        def perform(db):
            if db.execute('SELECT 1 FROM cutting_runs WHERE consumption_id=?',(consumption_id,)).fetchone():
                raise DomainError(409,'Pemakaian terhubung hasil cutting. Gunakan koreksi hasil cutting agar pcs dan bahan dikoreksi bersama.')
            row=db.execute('SELECT * FROM material_consumption WHERE id=?',(consumption_id,)).fetchone()
            if not row:
                raise DomainError(404,'Catatan pemakaian tidak ditemukan.')
            if row['reversal_of'] or db.execute('SELECT 1 FROM material_consumption WHERE reversal_of=?',(consumption_id,)).fetchone():
                raise DomainError(409,'Catatan pembalik atau catatan yang sudah dibalik tidak dapat dikoreksi lagi.')
            return self._consumption_event(db,row['issue_id'],-row['used_milli'],-row['waste_milli'],payload['reason'],actor['id'],consumption_id)
        return self._write(actor,('admin',),key,'consumption-reverse:'+consumption_id,payload,perform)

    def consumption_history(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            rows=db.execute('''SELECT c.*,b.reference AS batch_reference,s.code,s.unit,u.name AS actor_name,
                (SELECT id FROM cutting_runs WHERE consumption_id=c.id) AS cutting_run_id,
                (SELECT id FROM material_consumption WHERE reversal_of=c.id) AS reversed_by
                FROM material_consumption c JOIN material_movements m ON m.id=c.issue_id
                JOIN material_batches b ON b.id=m.batch_id JOIN materials s ON s.id=b.material_id JOIN users u ON u.id=c.actor_id
                WHERE m.order_id=? AND (? IS NULL OR c.sequence<?) ORDER BY c.sequence DESC LIMIT ?''',(order_id,before,before,limit)).fetchall()
            result=[]
            for row in rows:
                record=dict(row);record['used']=self._material_decimal(record.pop('used_milli'));record['waste']=self._material_decimal(record.pop('waste_milli'));result.append(record)
            return result

    def _cutting_run(self, db, run_id, include_bundles=True):
        row=db.execute('''SELECT r.*,o.reference AS order_reference,c.issue_id,c.used_milli,c.waste_milli,
            b.id AS batch_id,b.reference AS batch_reference,s.code,s.unit,u.name AS actor_name
            FROM cutting_runs r JOIN orders o ON o.id=r.order_id JOIN material_consumption c ON c.id=r.consumption_id
            JOIN material_movements i ON i.id=c.issue_id JOIN material_batches b ON b.id=i.batch_id
            JOIN materials s ON s.id=b.material_id JOIN users u ON u.id=r.actor_id WHERE r.id=?''',(run_id,)).fetchone()
        if not row:
            raise DomainError(404,'Hasil cutting tidak ditemukan.')
        record=dict(row)
        record['used']=self._material_decimal(record.pop('used_milli'))
        record['waste']=self._material_decimal(record.pop('waste_milli'))
        record['outputs']=[dict(row) for row in db.execute('''SELECT m.*,p.sku,p.size,p.color,
            (SELECT id FROM movements WHERE reversal_of=m.id) AS reversed_by
            FROM movements m JOIN order_lines l ON l.id=m.line_id JOIN products p ON p.id=l.product_id
            WHERE m.id IN (SELECT value FROM json_each(?)) ORDER BY p.sku''',(record.pop('movement_ids'),))]
        record['total_output']=sum(row['quantity'] for row in record['outputs'])
        if include_bundles:
            record['bundles']=[self._bundle(db,row['id']) for row in db.execute(
                'SELECT id FROM bundles WHERE cutting_run_id=? ORDER BY sequence DESC',(run_id,))]
            active={}
            for bundle in record['bundles']:
                if bundle['status']=='active':
                    output_id=bundle['output_movement_id']
                    active[output_id]=active.get(output_id,0)+bundle['quantity']
        else:
            active={row['output_movement_id']:row['quantity'] for row in db.execute('''SELECT b.output_movement_id,
                SUM(b.quantity) AS quantity FROM bundles b WHERE b.cutting_run_id=?
                AND NOT EXISTS(SELECT 1 FROM bundle_reversals x WHERE x.bundle_id=b.id)
                GROUP BY b.output_movement_id''',(run_id,))}
        for output in record['outputs']:
            output['bundled_quantity']=active.get(output['id'],0)
            output['unbundled_quantity']=output['quantity']-output['bundled_quantity']
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM cutting_run_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.run_id=?''',(run_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        return record

    def cutting_run(self, run_id):
        with self.transaction() as db:
            return self._cutting_run(db,run_id)

    def cutting_runs(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT id FROM cutting_runs WHERE order_id=? AND (? IS NULL OR sequence<?)
                ORDER BY sequence DESC LIMIT ?''',(order_id,before,before,limit)).fetchall()
            return [self._cutting_run(db,row[0],False) for row in ids]

    def _bundle(self, db, bundle_id):
        row=db.execute('''SELECT b.*,r.reference AS cutting_reference,r.order_id,o.reference AS order_reference,
            m.line_id,p.sku,p.name AS product_name,p.color,p.size,source.id AS batch_id,
            source.reference AS batch_reference,s.code AS material_code,s.unit,u.name AS actor_name
            FROM bundles b JOIN cutting_runs r ON r.id=b.cutting_run_id JOIN orders o ON o.id=r.order_id
            JOIN movements m ON m.id=b.output_movement_id JOIN order_lines l ON l.id=m.line_id
            JOIN products p ON p.id=l.product_id JOIN material_consumption c ON c.id=r.consumption_id
            JOIN material_movements i ON i.id=c.issue_id JOIN material_batches source ON source.id=i.batch_id
            JOIN materials s ON s.id=source.material_id JOIN users u ON u.id=b.actor_id WHERE b.id=?''',(bundle_id,)).fetchone()
        if not row:
            raise DomainError(404,'Bundle tidak ditemukan.')
        record=dict(row)
        reversal=db.execute('''SELECT x.*,u.name AS actor_name FROM bundle_reversals x
            JOIN users u ON u.id=x.actor_id WHERE x.bundle_id=?''',(bundle_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        allocated=db.execute('''SELECT COALESCE(SUM(j.quantity_out),0) FROM sewing_jobs j
            WHERE j.bundle_id=? AND NOT EXISTS(
                SELECT 1 FROM sewing_job_reversals x WHERE x.job_id=j.id)''',(bundle_id,)).fetchone()[0]
        record['sewing_allocated_quantity']=allocated
        record['sewing_unassigned_quantity']=0 if reversal else record['quantity']-allocated
        return record

    def bundle(self, bundle_id):
        with self.transaction() as db:
            return self._bundle(db,bundle_id)

    def bundles(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT b.id FROM bundles b JOIN cutting_runs r ON r.id=b.cutting_run_id
                WHERE r.order_id=? AND (? IS NULL OR b.sequence<?)
                ORDER BY b.sequence DESC LIMIT ?''',(order_id,before,before,limit)).fetchall()
            return [self._bundle(db,row['id']) for row in ids]

    def create_bundle(self, run_id, payload, actor, key):
        def perform(db):
            run=self._cutting_run(db,run_id,False)
            if run['reversal']:
                raise DomainError(409,'Hasil cutting sudah dikoreksi.')
            output=next((row for row in run['outputs'] if row['id']==payload['output_movement_id']),None)
            if not output:
                raise DomainError(422,'Output cutting tidak berasal dari hasil cutting ini.')
            if output['reversed_by']:
                raise DomainError(409,'Output cutting sudah dikoreksi.')
            if payload['quantity']>output['unbundled_quantity']:
                raise DomainError(409,'Jumlah bundle melebihi hasil cutting yang belum dibundel. Muat ulang dan periksa data terbaru.')
            bundle_id=str(uuid4())
            db.execute('''INSERT INTO bundles(id,reference,cutting_run_id,output_movement_id,quantity,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?)''',(bundle_id,payload['reference'],run_id,payload['output_movement_id'],
                                            payload['quantity'],payload['reason'],actor['id'],now()))
            return self._bundle(db,bundle_id)
        return self._write(actor,('admin','operator'),key,'bundle:'+run_id,payload,perform)

    def reverse_bundle(self, bundle_id, payload, actor, key):
        def perform(db):
            bundle=self._bundle(db,bundle_id)
            if bundle['reversal']:
                raise DomainError(409,'Bundle sudah dikoreksi.')
            if bundle['sewing_allocated_quantity']:
                raise DomainError(409,'Koreksi semua job sewing aktif sebelum mengoreksi bundle.')
            db.execute('INSERT INTO bundle_reversals(bundle_id,reason,actor_id,created_at) VALUES(?,?,?,?)',
                       (bundle_id,payload['reason'],actor['id'],now()))
            return self._bundle(db,bundle_id)
        return self._write(actor,('admin',),key,'bundle-reverse:'+bundle_id,payload,perform)

    def _sewing_job(self, db, job_id):
        row=db.execute('''SELECT j.*,b.reference AS bundle_reference,b.quantity AS bundle_quantity,
            b.cutting_run_id,r.reference AS cutting_reference,r.order_id,o.reference AS order_reference,
            m.line_id,p.sku,p.name AS product_name,p.color,p.size,source.id AS batch_id,
            source.reference AS batch_reference,s.code AS material_code,u.name AS actor_name
            FROM sewing_jobs j JOIN bundles b ON b.id=j.bundle_id
            JOIN cutting_runs r ON r.id=b.cutting_run_id JOIN orders o ON o.id=r.order_id
            JOIN movements m ON m.id=b.output_movement_id JOIN order_lines l ON l.id=m.line_id
            JOIN products p ON p.id=l.product_id JOIN material_consumption c ON c.id=r.consumption_id
            JOIN material_movements i ON i.id=c.issue_id JOIN material_batches source ON source.id=i.batch_id
            JOIN materials s ON s.id=source.material_id JOIN users u ON u.id=j.actor_id WHERE j.id=?''',(job_id,)).fetchone()
        if not row:
            raise DomainError(404,'Job sewing tidak ditemukan.')
        record=dict(row)
        record['cost']=format(Decimal(record.pop('cost_minor'))/100,'.2f')
        result=db.execute('''SELECT x.*,u.name AS actor_name FROM sewing_job_results x
            JOIN users u ON u.id=x.actor_id WHERE x.job_id=?''',(job_id,)).fetchone()
        if result:
            record['result']=dict(result)
            record['result']['turnaround_days']=(date.fromisoformat(result['returned_date'])-
                                                 date.fromisoformat(record['sent_date'])).days
        else:
            record['result']=None
        reversal=db.execute('''SELECT x.*,u.name AS actor_name FROM sewing_job_reversals x
            JOIN users u ON u.id=x.actor_id WHERE x.job_id=?''',(job_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'completed' if result else 'open'
        finished=db.execute('''SELECT COALESCE(SUM(f.quantity),0) FROM finishing_records f
            WHERE f.job_id=? AND NOT EXISTS(
                SELECT 1 FROM finishing_record_reversals r WHERE r.record_id=f.id)''',(job_id,)).fetchone()[0]
        record['finishing_completed_quantity']=finished
        record['finishing_remaining_quantity']=0 if reversal or not result else result['completed_quantity']-finished
        return record

    def sewing_job(self, job_id):
        with self.transaction() as db:
            return self._sewing_job(db,job_id)

    def sewing_jobs(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT j.id FROM sewing_jobs j JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs r ON r.id=b.cutting_run_id WHERE r.order_id=?
                AND (? IS NULL OR j.sequence<?) ORDER BY j.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._sewing_job(db,row['id']) for row in ids]

    def create_sewing_job(self, bundle_id, payload, actor, key):
        def perform(db):
            bundle=self._bundle(db,bundle_id)
            if bundle['status']!='active':
                raise DomainError(409,'Bundle sudah dikoreksi.')
            if payload['quantity_out']>bundle['sewing_unassigned_quantity']:
                raise DomainError(409,'Jumlah keluar melebihi bundle yang belum dialokasikan. Muat ulang data terbaru.')
            job_id=str(uuid4())
            db.execute('''INSERT INTO sewing_jobs(id,reference,bundle_id,assignment_type,assignee,quantity_out,
                cost_minor,sent_date,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (job_id,payload['reference'],bundle_id,payload['assignment_type'],payload['assignee'],
                 payload['quantity_out'],int(Decimal(payload['cost'])*100),payload['sent_date'],
                 payload['reason'],actor['id'],now()))
            return self._sewing_job(db,job_id)
        return self._write(actor,('admin','operator'),key,'sewing-job:'+bundle_id,payload,perform)

    def complete_sewing_job(self, job_id, payload, actor, key):
        def perform(db):
            job=self._sewing_job(db,job_id)
            if job['reversal']:
                raise DomainError(409,'Job sewing sudah dikoreksi.')
            if job['result']:
                raise DomainError(409,'Hasil job sewing sudah dicatat.')
            total=payload['completed_quantity']+payload['defect_quantity']+payload['missing_quantity']
            if total!=job['quantity_out']:
                raise DomainError(409,'Jumlah selesai + defect + missing harus sama dengan jumlah keluar.')
            if payload['returned_date']<job['sent_date']:
                raise DomainError(422,'Tanggal kembali tidak boleh sebelum tanggal kirim.')
            completed=None
            if payload['completed_quantity']:
                completed=self._transfer(db,dict(line_id=job['line_id'],from_stage='sewing',to_stage='finishing',
                    quantity=payload['completed_quantity'],reason=payload['reason']),actor)['id']
            rejected=payload['defect_quantity']+payload['missing_quantity']
            rejected_id=None
            if rejected:
                rejected_id=self._transfer(db,dict(line_id=job['line_id'],from_stage='sewing',to_stage='reject',
                    quantity=rejected,reason=payload['reason']),actor)['id']
            db.execute('''INSERT INTO sewing_job_results(job_id,completed_quantity,defect_quantity,missing_quantity,
                returned_date,completion_movement_id,reject_movement_id,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',(job_id,payload['completed_quantity'],payload['defect_quantity'],
                payload['missing_quantity'],payload['returned_date'],completed,rejected_id,payload['reason'],actor['id'],now()))
            return self._sewing_job(db,job_id)
        return self._write(actor,('admin','operator'),key,'sewing-complete:'+job_id,payload,perform)

    def reverse_sewing_job(self, job_id, payload, actor, key):
        def perform(db):
            job=self._sewing_job(db,job_id)
            if job['reversal']:
                raise DomainError(409,'Job sewing sudah dikoreksi.')
            if job['finishing_completed_quantity']:
                raise DomainError(409,'Koreksi semua catatan finishing aktif sebelum mengoreksi job sewing.')
            if job['result']:
                for movement_id in (job['result']['completion_movement_id'],job['result']['reject_movement_id']):
                    if not movement_id:
                        continue
                    original=db.execute('SELECT * FROM movements WHERE id=?',(movement_id,)).fetchone()
                    if db.execute('SELECT 1 FROM movements WHERE reversal_of=?',(movement_id,)).fetchone():
                        raise DomainError(409,'Perpindahan hasil sewing sudah dikoreksi terpisah; periksa riwayat.')
                    self._transfer(db,dict(line_id=original['line_id'],from_stage=original['to_stage'],
                        to_stage=original['from_stage'],quantity=original['quantity'],reason=payload['reason']),
                        actor,reversal_of=movement_id)
            db.execute('INSERT INTO sewing_job_reversals(job_id,reason,actor_id,created_at) VALUES(?,?,?,?)',
                       (job_id,payload['reason'],actor['id'],now()))
            return self._sewing_job(db,job_id)
        return self._write(actor,('admin',),key,'sewing-reverse:'+job_id,payload,perform)

    def _finishing_record(self, db, record_id):
        row=db.execute('''SELECT f.*,j.reference AS sewing_reference,j.assignment_type,j.assignee,
            b.id AS bundle_id,b.reference AS bundle_reference,b.cutting_run_id,
            r.reference AS cutting_reference,r.order_id,o.reference AS order_reference,
            source.line_id,p.sku,p.name AS product_name,p.color,p.size,batch.id AS batch_id,
            batch.reference AS batch_reference,s.code AS material_code,u.name AS actor_name
            FROM finishing_records f JOIN sewing_jobs j ON j.id=f.job_id
            JOIN bundles b ON b.id=j.bundle_id JOIN cutting_runs r ON r.id=b.cutting_run_id
            JOIN orders o ON o.id=r.order_id JOIN movements source ON source.id=b.output_movement_id
            JOIN order_lines l ON l.id=source.line_id JOIN products p ON p.id=l.product_id
            JOIN material_consumption c ON c.id=r.consumption_id
            JOIN material_movements i ON i.id=c.issue_id JOIN material_batches batch ON batch.id=i.batch_id
            JOIN materials s ON s.id=batch.material_id JOIN users u ON u.id=f.actor_id
            WHERE f.id=?''',(record_id,)).fetchone()
        if not row:
            raise DomainError(404,'Catatan finishing tidak ditemukan.')
        record=dict(row)
        for field in ('thread_trimmed','ironed','labels_attached','hangtags_attached','packaged'):
            record[field]=bool(record[field])
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM finishing_record_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.record_id=?''',(record_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'completed'
        inspected=db.execute('''SELECT COALESCE(SUM(q.accepted_quantity+q.rework_quantity+q.reject_quantity),0)
            FROM final_qc_records q WHERE q.finishing_record_id=? AND NOT EXISTS(
                SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id)''',(record_id,)).fetchone()[0]
        record['qc_inspected_quantity']=inspected
        record['qc_remaining_quantity']=0 if reversal else record['quantity']-inspected
        return record

    def finishing_record(self, record_id):
        with self.transaction() as db:
            return self._finishing_record(db,record_id)

    def finishing_records(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT f.id FROM finishing_records f JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN cutting_runs r ON r.id=b.cutting_run_id
                WHERE r.order_id=? AND (? IS NULL OR f.sequence<?)
                ORDER BY f.sequence DESC LIMIT ?''',(order_id,before,before,limit)).fetchall()
            return [self._finishing_record(db,row['id']) for row in ids]

    def create_finishing_record(self, job_id, payload, actor, key):
        def perform(db):
            job=self._sewing_job(db,job_id)
            if job['status']!='completed':
                raise DomainError(409,'Job sewing harus selesai dan aktif sebelum finishing dicatat.')
            if payload['quantity']>job['finishing_remaining_quantity']:
                raise DomainError(409,'Jumlah finishing melebihi hasil sewing yang belum dicatat. Muat ulang data terbaru.')
            if payload['completed_date']<job['result']['returned_date']:
                raise DomainError(422,'Tanggal selesai finishing tidak boleh sebelum tanggal kembali sewing.')
            movement=self._transfer(db,dict(line_id=job['line_id'],from_stage='finishing',to_stage='qc',
                quantity=payload['quantity'],reason=payload['reason']),actor)
            record_id=str(uuid4())
            db.execute('''INSERT INTO finishing_records(id,reference,job_id,quantity,thread_trimmed,ironed,
                labels_attached,hangtags_attached,packaged,completed_date,movement_id,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(record_id,payload['reference'],job_id,payload['quantity'],
                payload['thread_trimmed'],payload['ironed'],payload['labels_attached'],payload['hangtags_attached'],
                payload['packaged'],payload['completed_date'],movement['id'],payload['reason'],actor['id'],now()))
            return self._finishing_record(db,record_id)
        return self._write(actor,('admin','operator'),key,'finishing:'+job_id,payload,perform)

    def reverse_finishing_record(self, record_id, payload, actor, key):
        def perform(db):
            record=self._finishing_record(db,record_id)
            if record['reversal']:
                raise DomainError(409,'Catatan finishing sudah dikoreksi.')
            if record['qc_inspected_quantity']:
                raise DomainError(409,'Koreksi semua catatan final QC aktif sebelum mengoreksi finishing.')
            original=db.execute('SELECT * FROM movements WHERE id=?',(record['movement_id'],)).fetchone()
            if db.execute('SELECT 1 FROM movements WHERE reversal_of=?',(record['movement_id'],)).fetchone():
                raise DomainError(409,'Perpindahan finishing sudah dikoreksi terpisah; periksa riwayat.')
            self._transfer(db,dict(line_id=original['line_id'],from_stage=original['to_stage'],
                to_stage=original['from_stage'],quantity=original['quantity'],reason=payload['reason']),
                actor,reversal_of=record['movement_id'])
            db.execute('''INSERT INTO finishing_record_reversals(record_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(record_id,payload['reason'],actor['id'],now()))
            return self._finishing_record(db,record_id)
        return self._write(actor,('admin',),key,'finishing-reverse:'+record_id,payload,perform)

    def _final_qc_record(self, db, record_id):
        row=db.execute('''SELECT q.*,f.reference AS finishing_reference,f.job_id,
            j.reference AS sewing_reference,j.assignment_type,j.assignee,
            b.id AS bundle_id,b.reference AS bundle_reference,b.cutting_run_id,
            r.reference AS cutting_reference,r.order_id,o.reference AS order_reference,
            source.line_id,p.sku,p.name AS product_name,p.color,p.size,batch.id AS batch_id,
            batch.reference AS batch_reference,s.code AS material_code,u.name AS actor_name
            FROM final_qc_records q JOIN finishing_records f ON f.id=q.finishing_record_id
            JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
            JOIN cutting_runs r ON r.id=b.cutting_run_id JOIN orders o ON o.id=r.order_id
            JOIN movements source ON source.id=b.output_movement_id
            JOIN order_lines l ON l.id=source.line_id JOIN products p ON p.id=l.product_id
            JOIN material_consumption c ON c.id=r.consumption_id
            JOIN material_movements i ON i.id=c.issue_id JOIN material_batches batch ON batch.id=i.batch_id
            JOIN materials s ON s.id=batch.material_id JOIN users u ON u.id=q.actor_id
            WHERE q.id=?''',(record_id,)).fetchone()
        if not row:
            raise DomainError(404,'Catatan final QC tidak ditemukan.')
        record=dict(row)
        record['inspected_quantity']=record['accepted_quantity']+record['rework_quantity']+record['reject_quantity']
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM final_qc_record_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.record_id=?''',(record_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'completed'
        received=db.execute('''SELECT COALESCE(SUM(x.sellable_quantity+x.hold_quantity),0)
            FROM finished_goods_receipts x WHERE x.final_qc_record_id=? AND NOT EXISTS(
                SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)''',(record_id,)).fetchone()[0]
        record['warehouse_received_quantity']=received
        record['warehouse_remaining_quantity']=0 if reversal else record['accepted_quantity']-received
        return record

    def final_qc_record(self, record_id):
        with self.transaction() as db:
            return self._final_qc_record(db,record_id)

    def final_qc_records(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT q.id FROM final_qc_records q
                JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs r ON r.id=b.cutting_run_id WHERE r.order_id=?
                AND (? IS NULL OR q.sequence<?) ORDER BY q.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._final_qc_record(db,row['id']) for row in ids]

    def create_final_qc_record(self, finishing_record_id, payload, actor, key):
        def perform(db):
            source=self._finishing_record(db,finishing_record_id)
            if source['status']!='completed':
                raise DomainError(409,'Catatan finishing harus aktif sebelum final QC dicatat.')
            inspected=payload['accepted_quantity']+payload['rework_quantity']+payload['reject_quantity']
            if inspected>source['qc_remaining_quantity']:
                raise DomainError(409,'Jumlah inspeksi melebihi finishing yang belum diperiksa. Muat ulang data terbaru.')
            if payload['inspection_date']<source['completed_date']:
                raise DomainError(422,'Tanggal inspeksi tidak boleh sebelum tanggal selesai finishing.')
            movements={}
            for field,stage in (('accepted','warehouse'),('rework','rework'),('reject','reject')):
                quantity=payload[field+'_quantity']
                movements[field]=None if not quantity else self._transfer(db,dict(line_id=source['line_id'],
                    from_stage='qc',to_stage=stage,quantity=quantity,reason=payload['reason']),actor)['id']
            record_id=str(uuid4())
            db.execute('''INSERT INTO final_qc_records(id,reference,finishing_record_id,measurement_notes,
                visual_notes,defect_type,responsible_source,disposition,
                accepted_quantity,rework_quantity,reject_quantity,inspection_date,
                accepted_movement_id,rework_movement_id,reject_movement_id,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(record_id,payload['reference'],finishing_record_id,
                payload['measurement_notes'],payload['visual_notes'],payload['defect_type'],payload['responsible_source'],
                payload['disposition'],payload['accepted_quantity'],
                payload['rework_quantity'],payload['reject_quantity'],payload['inspection_date'],
                movements['accepted'],movements['rework'],movements['reject'],payload['reason'],actor['id'],now()))
            return self._final_qc_record(db,record_id)
        return self._write(actor,('admin','operator'),key,'final-qc:'+finishing_record_id,payload,perform)

    def reverse_final_qc_record(self, record_id, payload, actor, key):
        def perform(db):
            record=self._final_qc_record(db,record_id)
            if record['reversal']:
                raise DomainError(409,'Catatan final QC sudah dikoreksi.')
            if record['warehouse_received_quantity']:
                raise DomainError(409,'Koreksi semua penerimaan barang jadi aktif sebelum mengoreksi final QC.')
            for movement_id in (record['accepted_movement_id'],record['rework_movement_id'],record['reject_movement_id']):
                if not movement_id:
                    continue
                original=db.execute('SELECT * FROM movements WHERE id=?',(movement_id,)).fetchone()
                if db.execute('SELECT 1 FROM movements WHERE reversal_of=?',(movement_id,)).fetchone():
                    raise DomainError(409,'Perpindahan final QC sudah dikoreksi terpisah; periksa riwayat.')
                self._transfer(db,dict(line_id=original['line_id'],from_stage=original['to_stage'],
                    to_stage=original['from_stage'],quantity=original['quantity'],reason=payload['reason']),
                    actor,reversal_of=movement_id)
            db.execute('''INSERT INTO final_qc_record_reversals(record_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(record_id,payload['reason'],actor['id'],now()))
            return self._final_qc_record(db,record_id)
        return self._write(actor,('admin',),key,'final-qc-reverse:'+record_id,payload,perform)

    def _warehouse_balances(self, db, receipt_id):
        rows=db.execute('''WITH ledger(location,stock_status,quantity) AS (
            SELECT x.location,'sellable',x.sellable_quantity FROM finished_goods_receipts x
                WHERE x.id=? AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
            UNION ALL
            SELECT x.location,'hold',x.hold_quantity FROM finished_goods_receipts x
                WHERE x.id=? AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
            UNION ALL
            SELECT w.from_location,w.from_status,-w.quantity FROM warehouse_movements w
                WHERE w.receipt_id=? AND NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
            UNION ALL
            SELECT w.to_location,w.to_status,w.quantity FROM warehouse_movements w
                WHERE w.receipt_id=? AND NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
            UNION ALL
            SELECT t.return_location,t.stock_status,t.quantity FROM marketplace_returns t
                JOIN marketplace_shipments s ON s.id=t.shipment_id JOIN marketplace_packs k ON k.id=s.pack_id
                JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                WHERE m.receipt_id=? AND NOT EXISTS(SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
                  AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
            UNION ALL
            SELECT a.location,a.stock_status,a.quantity_delta FROM finished_goods_adjustments a
                WHERE a.receipt_id=? AND NOT EXISTS(
                  SELECT 1 FROM finished_goods_adjustment_reversals r WHERE r.adjustment_id=a.id)
        ) SELECT location,stock_status,SUM(quantity) AS quantity FROM ledger
          GROUP BY location COLLATE NOCASE,stock_status HAVING SUM(quantity)>0
          ORDER BY location COLLATE NOCASE,stock_status''',
          (receipt_id,receipt_id,receipt_id,receipt_id,receipt_id,receipt_id)).fetchall()
        reserved={row['location'].casefold():row['quantity'] for row in db.execute('''SELECT m.location,
            SUM(m.quantity-COALESCE((SELECT SUM(p.quantity) FROM marketplace_picks p WHERE p.reservation_id=m.id
              AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)),0)) AS quantity
            FROM marketplace_reservations m WHERE m.receipt_id=? AND NOT EXISTS(
              SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
            GROUP BY m.location COLLATE NOCASE''',(receipt_id,)).fetchall()}
        picked_from={row['location'].casefold():row['quantity'] for row in db.execute('''SELECT m.location,
            SUM(p.quantity) AS quantity FROM marketplace_picks p JOIN marketplace_reservations m ON m.id=p.reservation_id
            WHERE m.receipt_id=? AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
              AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
            GROUP BY m.location COLLATE NOCASE''',(receipt_id,)).fetchall()}
        picked_to=[dict(row) for row in db.execute('''SELECT p.staging_location AS location,SUM(p.quantity) AS quantity
            FROM marketplace_picks p JOIN marketplace_reservations m ON m.id=p.reservation_id
            WHERE m.receipt_id=? AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
              AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
            GROUP BY p.staging_location COLLATE NOCASE''',(receipt_id,)).fetchall()]
        packed_to=[dict(row) for row in db.execute('''SELECT p.staging_location AS location,SUM(k.quantity) AS quantity
            FROM marketplace_packs k JOIN marketplace_picks p ON p.id=k.pick_id
            JOIN marketplace_reservations m ON m.id=p.reservation_id WHERE m.receipt_id=?
              AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
              AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
              AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
            GROUP BY p.staging_location COLLATE NOCASE''',(receipt_id,)).fetchall()]
        packed={row['location'].casefold():row['quantity'] for row in packed_to}
        shipped={row['location'].casefold():row['quantity'] for row in db.execute('''SELECT p.staging_location AS location,
            SUM(s.quantity) AS quantity FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
            JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
            WHERE m.receipt_id=? AND NOT EXISTS(
              SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
              AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
              AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
              AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
            GROUP BY p.staging_location COLLATE NOCASE''',(receipt_id,)).fetchall()}
        result=[]
        for row in rows:
            item=dict(row)
            if item['stock_status']=='sellable':
                item['quantity']-=picked_from.get(item['location'].casefold(),0)
            item['reserved_quantity']=reserved.get(item['location'].casefold(),0) if item['stock_status']=='sellable' else 0
            item['available_quantity']=item['quantity']-item['reserved_quantity'] if item['stock_status']=='sellable' else 0
            item['movable_quantity']=item['available_quantity'] if item['stock_status']=='sellable' else item['quantity']
            if item['quantity']>0:
                result.append(item)
        result.extend(dict(row,quantity=row['quantity']-packed.get(row['location'].casefold(),0),stock_status='picked',
                      reserved_quantity=0,available_quantity=0,movable_quantity=0) for row in picked_to
                      if row['quantity']-packed.get(row['location'].casefold(),0)>0)
        result.extend(dict(row,quantity=row['quantity']-shipped.get(row['location'].casefold(),0),stock_status='packed',
                      reserved_quantity=0,available_quantity=0,movable_quantity=0) for row in packed_to
                      if row['quantity']-shipped.get(row['location'].casefold(),0)>0)
        return sorted(result,key=lambda row:(row['location'].casefold(),row['stock_status']))

    def _finished_goods_receipt(self, db, receipt_id):
        row=db.execute('''SELECT x.*,q.reference AS final_qc_reference,q.finishing_record_id,
            f.reference AS finishing_reference,f.job_id,j.reference AS sewing_reference,
            b.id AS bundle_id,b.reference AS bundle_reference,r.order_id,o.reference AS order_reference,
            source.line_id,p.id AS product_id,p.sku,p.name AS product_name,p.color,p.size,
            batch.id AS batch_id,batch.reference AS batch_reference,u.name AS actor_name
            FROM finished_goods_receipts x JOIN final_qc_records q ON q.id=x.final_qc_record_id
            JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
            JOIN bundles b ON b.id=j.bundle_id JOIN cutting_runs r ON r.id=b.cutting_run_id
            JOIN orders o ON o.id=r.order_id JOIN movements source ON source.id=b.output_movement_id
            JOIN order_lines l ON l.id=source.line_id JOIN products p ON p.id=l.product_id
            JOIN material_consumption c ON c.id=r.consumption_id
            JOIN material_movements i ON i.id=c.issue_id JOIN material_batches batch ON batch.id=i.batch_id
            JOIN users u ON u.id=x.actor_id WHERE x.id=?''',(receipt_id,)).fetchone()
        if not row:
            raise DomainError(404,'Penerimaan barang jadi tidak ditemukan.')
        record=dict(row)
        record['received_quantity']=record['sellable_quantity']+record['hold_quantity']
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM finished_goods_receipt_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.receipt_id=?''',(receipt_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        record['inventory']=self._warehouse_balances(db,receipt_id)
        record['active_movement_count']=db.execute('''SELECT COUNT(*) FROM warehouse_movements w
            WHERE w.receipt_id=? AND NOT EXISTS(
              SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)''',(receipt_id,)).fetchone()[0]
        record['active_reservation_count']=db.execute('''SELECT COUNT(*) FROM marketplace_reservations m
            WHERE m.receipt_id=? AND NOT EXISTS(
              SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)''',(receipt_id,)).fetchone()[0]
        return record

    def finished_goods_receipt(self, receipt_id):
        with self.transaction() as db:
            return self._finished_goods_receipt(db,receipt_id)

    def finished_goods_receipts(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT x.id FROM finished_goods_receipts x
                JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs r ON r.id=b.cutting_run_id WHERE r.order_id=?
                AND (? IS NULL OR x.sequence<?) ORDER BY x.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._finished_goods_receipt(db,row['id']) for row in ids]

    def finished_goods_inventory(self, limit=100, offset=0):
        with self.transaction() as db:
            rows=db.execute('''WITH receipt_products AS (
                SELECT x.id,x.location,x.sellable_quantity,x.hold_quantity,l.product_id
                FROM finished_goods_receipts x JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id
                WHERE NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
            ), ledger(product_id,stock_status,quantity) AS (
                SELECT product_id,'sellable',sellable_quantity FROM receipt_products
                UNION ALL SELECT product_id,'hold',hold_quantity FROM receipt_products
                UNION ALL SELECT p.product_id,w.from_status,-w.quantity FROM warehouse_movements w
                    JOIN receipt_products p ON p.id=w.receipt_id WHERE NOT EXISTS(
                      SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
                UNION ALL SELECT p.product_id,w.to_status,w.quantity FROM warehouse_movements w
                    JOIN receipt_products p ON p.id=w.receipt_id WHERE NOT EXISTS(
                      SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
                UNION ALL SELECT rp.product_id,t.stock_status,t.quantity FROM marketplace_returns t
                    JOIN marketplace_shipments s ON s.id=t.shipment_id JOIN marketplace_packs k ON k.id=s.pack_id
                    JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                    JOIN receipt_products rp ON rp.id=m.receipt_id WHERE NOT EXISTS(
                      SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
                UNION ALL SELECT rp.product_id,a.stock_status,a.quantity_delta FROM finished_goods_adjustments a
                    JOIN receipt_products rp ON rp.id=a.receipt_id WHERE NOT EXISTS(
                      SELECT 1 FROM finished_goods_adjustment_reversals r WHERE r.adjustment_id=a.id)
            ) SELECT p.id AS product_id,p.sku,p.name,p.color,p.size,
                COALESCE(SUM(CASE WHEN l.stock_status='sellable' THEN l.quantity ELSE 0 END),0) AS sellable_quantity,
                COALESCE(SUM(CASE WHEN l.stock_status='hold' THEN l.quantity ELSE 0 END),0) AS hold_quantity,
                COALESCE(SUM(CASE WHEN l.stock_status='damaged' THEN l.quantity ELSE 0 END),0) AS damaged_quantity
                FROM products p LEFT JOIN ledger l ON l.product_id=p.id
                GROUP BY p.id ORDER BY p.sku LIMIT ? OFFSET ?''',(limit,offset)).fetchall()
            reserved={row['product_id']:row['quantity'] for row in db.execute('''SELECT l.product_id,
                SUM(m.quantity-COALESCE((SELECT SUM(p.quantity) FROM marketplace_picks p
                  WHERE p.reservation_id=m.id AND NOT EXISTS(
                    SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)),0)) AS quantity
                FROM marketplace_reservations m
                JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id WHERE NOT EXISTS(
                  SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
                GROUP BY l.product_id''').fetchall()}
            picked={row['product_id']:row['quantity'] for row in db.execute('''SELECT l.product_id,SUM(p.quantity) AS quantity
                FROM marketplace_picks p JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id WHERE NOT EXISTS(
                  SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
                AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
                GROUP BY l.product_id''').fetchall()}
            packed={row['product_id']:row['quantity'] for row in db.execute('''SELECT l.product_id,SUM(k.quantity) AS quantity
                FROM marketplace_packs k JOIN marketplace_picks p ON p.id=k.pick_id
                JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id WHERE NOT EXISTS(
                  SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
                AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
                AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
                GROUP BY l.product_id''').fetchall()}
            shipped={row['product_id']:row['quantity'] for row in db.execute('''SELECT l.product_id,SUM(s.quantity) AS quantity
                FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
                JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id WHERE NOT EXISTS(
                  SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
                AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
                AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
                AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
                GROUP BY l.product_id''').fetchall()}
            returned={row['product_id']:row['quantity'] for row in db.execute('''SELECT l.product_id,SUM(t.quantity) AS quantity
                FROM marketplace_returns t JOIN marketplace_shipments s ON s.id=t.shipment_id
                JOIN marketplace_packs k ON k.id=s.pack_id JOIN marketplace_picks p ON p.id=k.pick_id
                JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id WHERE NOT EXISTS(
                  SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
                AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
                GROUP BY l.product_id''').fetchall()}
            result=[]
            for row in rows:
                item=dict(row);picked_total=picked.get(item['product_id'],0);packed_total=packed.get(item['product_id'],0);shipped_quantity=shipped.get(item['product_id'],0)
                item['sellable_quantity']-=picked_total
                item['picked_quantity']=picked_total-packed_total
                item['packed_quantity']=packed_total-shipped_quantity
                item['shipped_quantity']=shipped_quantity
                item['returned_quantity']=returned.get(item['product_id'],0)
                item['reserved_quantity']=reserved.get(item['product_id'],0)
                item['available_quantity']=item['sellable_quantity']-item['reserved_quantity']
                item['total_quantity']=item['sellable_quantity']+item['hold_quantity']+item['damaged_quantity']+picked_total-shipped_quantity
                result.append(item)
            return result

    def warehouse_inventory(self, limit=100, offset=0):
        with self.transaction() as db:
            rows=db.execute('''WITH receipt_products AS (
                SELECT x.id,x.location,x.sellable_quantity,x.hold_quantity,l.product_id
                FROM finished_goods_receipts x JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id
                WHERE NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
            ), ledger(product_id,location,stock_status,quantity) AS (
                SELECT product_id,location,'sellable',sellable_quantity FROM receipt_products
                UNION ALL SELECT product_id,location,'hold',hold_quantity FROM receipt_products
                UNION ALL SELECT p.product_id,w.from_location,w.from_status,-w.quantity
                    FROM warehouse_movements w JOIN receipt_products p ON p.id=w.receipt_id
                    WHERE NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
                UNION ALL SELECT p.product_id,w.to_location,w.to_status,w.quantity
                    FROM warehouse_movements w JOIN receipt_products p ON p.id=w.receipt_id
                    WHERE NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
                UNION ALL SELECT rp.product_id,m.location,'sellable',-p.quantity FROM marketplace_picks p
                    JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN receipt_products rp ON rp.id=m.receipt_id
                    WHERE NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                UNION ALL SELECT rp.product_id,p.staging_location,'picked',p.quantity FROM marketplace_picks p
                    JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN receipt_products rp ON rp.id=m.receipt_id
                    WHERE NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                UNION ALL SELECT rp.product_id,p.staging_location,'picked',-k.quantity FROM marketplace_packs k
                    JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                    JOIN receipt_products rp ON rp.id=m.receipt_id WHERE NOT EXISTS(
                      SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                UNION ALL SELECT rp.product_id,p.staging_location,'packed',k.quantity FROM marketplace_packs k
                    JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                    JOIN receipt_products rp ON rp.id=m.receipt_id WHERE NOT EXISTS(
                      SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                UNION ALL SELECT rp.product_id,p.staging_location,'packed',-s.quantity FROM marketplace_shipments s
                    JOIN marketplace_packs k ON k.id=s.pack_id JOIN marketplace_picks p ON p.id=k.pick_id
                    JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN receipt_products rp ON rp.id=m.receipt_id
                    WHERE NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                UNION ALL SELECT rp.product_id,t.return_location,t.stock_status,t.quantity FROM marketplace_returns t
                    JOIN marketplace_shipments s ON s.id=t.shipment_id JOIN marketplace_packs k ON k.id=s.pack_id
                    JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                    JOIN receipt_products rp ON rp.id=m.receipt_id WHERE NOT EXISTS(
                      SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
                      AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
                UNION ALL SELECT rp.product_id,a.location,a.stock_status,a.quantity_delta
                    FROM finished_goods_adjustments a JOIN receipt_products rp ON rp.id=a.receipt_id
                    WHERE NOT EXISTS(SELECT 1 FROM finished_goods_adjustment_reversals r WHERE r.adjustment_id=a.id)
            ) SELECT p.id AS product_id,p.sku,p.name,p.color,p.size,l.location,l.stock_status,
                SUM(l.quantity) AS quantity FROM ledger l JOIN products p ON p.id=l.product_id
                GROUP BY p.id,l.location COLLATE NOCASE,l.stock_status HAVING SUM(l.quantity)>0
                ORDER BY p.sku,l.location COLLATE NOCASE,l.stock_status LIMIT ? OFFSET ?''',(limit,offset)).fetchall()
            reserved={(row['product_id'],row['location'].casefold()):row['quantity'] for row in db.execute('''
                SELECT l.product_id,m.location,
                SUM(m.quantity-COALESCE((SELECT SUM(p.quantity) FROM marketplace_picks p
                  WHERE p.reservation_id=m.id AND NOT EXISTS(
                    SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)),0)) AS quantity
                FROM marketplace_reservations m
                JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id WHERE NOT EXISTS(
                  SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
                AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
                GROUP BY l.product_id,m.location COLLATE NOCASE''').fetchall()}
            result=[]
            for row in rows:
                item=dict(row)
                item['reserved_quantity']=reserved.get((item['product_id'],item['location'].casefold()),0) if item['stock_status']=='sellable' else 0
                item['available_quantity']=item['quantity']-item['reserved_quantity'] if item['stock_status']=='sellable' else 0
                result.append(item)
            return result

    def create_finished_goods_receipt(self, final_qc_record_id, payload, actor, key):
        def perform(db):
            source=self._final_qc_record(db,final_qc_record_id)
            if source['status']!='completed':
                raise DomainError(409,'Final QC harus aktif sebelum barang jadi diterima.')
            quantity=payload['sellable_quantity']+payload['hold_quantity']
            if quantity>source['warehouse_remaining_quantity']:
                raise DomainError(409,'Jumlah penerimaan melebihi hasil QC accepted yang belum diterima. Muat ulang data terbaru.')
            if payload['received_date']<source['inspection_date']:
                raise DomainError(422,'Tanggal penerimaan tidak boleh sebelum tanggal inspeksi.')
            if payload['scanned_sku'].casefold()!=source['sku'].casefold():
                raise DomainError(422,'SKU hasil scan tidak cocok dengan barang dari final QC.')
            receipt_id=str(uuid4())
            db.execute('''INSERT INTO finished_goods_receipts(id,reference,final_qc_record_id,scanned_sku,
                location,sellable_quantity,hold_quantity,received_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(receipt_id,payload['reference'],final_qc_record_id,
                payload['scanned_sku'],payload['location'],payload['sellable_quantity'],payload['hold_quantity'],
                payload['received_date'],payload['reason'],actor['id'],now()))
            return self._finished_goods_receipt(db,receipt_id)
        return self._write(actor,('admin','operator'),key,'finished-goods:'+final_qc_record_id,payload,perform)

    def reverse_finished_goods_receipt(self, receipt_id, payload, actor, key):
        def perform(db):
            receipt=self._finished_goods_receipt(db,receipt_id)
            if receipt['reversal']:
                raise DomainError(409,'Penerimaan barang jadi sudah dikoreksi.')
            if receipt['active_movement_count']:
                raise DomainError(409,'Koreksi semua pergerakan gudang aktif sebelum mengoreksi penerimaan barang jadi.')
            if receipt['active_reservation_count']:
                raise DomainError(409,'Lepaskan semua reservasi marketplace aktif sebelum mengoreksi penerimaan barang jadi.')
            db.execute('''INSERT INTO finished_goods_receipt_reversals(receipt_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(receipt_id,payload['reason'],actor['id'],now()))
            return self._finished_goods_receipt(db,receipt_id)
        return self._write(actor,('admin',),key,'finished-goods-reverse:'+receipt_id,payload,perform)

    def _warehouse_movement(self, db, movement_id):
        row=db.execute('''SELECT w.*,u.name AS actor_name FROM warehouse_movements w
            JOIN users u ON u.id=w.actor_id WHERE w.id=?''',(movement_id,)).fetchone()
        if not row:
            raise DomainError(404,'Pergerakan gudang tidak ditemukan.')
        record=dict(row)
        source=self._finished_goods_receipt(db,record['receipt_id'])
        for key in ('reference','order_id','order_reference','product_id','sku','product_name','color','size',
                    'final_qc_record_id','final_qc_reference','batch_id','batch_reference'):
            record['receipt_reference' if key=='reference' else key]=source[key]
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM warehouse_movement_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.movement_id=?''',(movement_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        return record

    def warehouse_movement(self, movement_id):
        with self.transaction() as db:
            return self._warehouse_movement(db,movement_id)

    def warehouse_movements(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT w.id FROM warehouse_movements w
                JOIN finished_goods_receipts x ON x.id=w.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND (? IS NULL OR w.sequence<?) ORDER BY w.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._warehouse_movement(db,row['id']) for row in ids]

    def create_warehouse_movement(self, receipt_id, payload, actor, key):
        def perform(db):
            receipt=self._finished_goods_receipt(db,receipt_id)
            if receipt['status']!='active':
                raise DomainError(409,'Penerimaan barang jadi harus aktif sebelum stok dipindahkan.')
            if payload['moved_date']<receipt['received_date']:
                raise DomainError(422,'Tanggal pergerakan tidak boleh sebelum tanggal penerimaan barang jadi.')
            if payload['kind']=='transfer':
                from_status=to_status=payload['stock_status']
            else:
                from_status='hold'
                to_status='sellable' if payload['kind']=='hold_release' else 'damaged'
            balance=next((row['movable_quantity'] for row in receipt['inventory']
                          if row['location'].casefold()==payload['from_location'].casefold()
                          and row['stock_status']==from_status),0)
            if payload['quantity']>balance:
                raise DomainError(409,'Jumlah melebihi stok pada lokasi dan status asal. Muat ulang inventori.')
            movement_id=str(uuid4())
            db.execute('''INSERT INTO warehouse_movements(id,reference,receipt_id,kind,from_location,to_location,
                from_status,to_status,quantity,moved_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(movement_id,payload['reference'],receipt_id,payload['kind'],
                payload['from_location'],payload['to_location'],from_status,to_status,payload['quantity'],
                payload['moved_date'],payload['reason'],actor['id'],now()))
            return self._warehouse_movement(db,movement_id)
        return self._write(actor,('admin','operator'),key,'warehouse-movement:'+receipt_id,payload,perform)

    def reverse_warehouse_movement(self, movement_id, payload, actor, key):
        def perform(db):
            movement=self._warehouse_movement(db,movement_id)
            if movement['reversal']:
                raise DomainError(409,'Pergerakan gudang sudah dikoreksi.')
            receipt=self._finished_goods_receipt(db,movement['receipt_id'])
            target=next((row['movable_quantity'] for row in receipt['inventory']
                         if row['location'].casefold()==movement['to_location'].casefold()
                         and row['stock_status']==movement['to_status']),0)
            if target<movement['quantity']:
                raise DomainError(409,'Stok tujuan sudah dipakai oleh pergerakan berikutnya. Koreksi urutan terbaru terlebih dahulu.')
            db.execute('''INSERT INTO warehouse_movement_reversals(movement_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(movement_id,payload['reason'],actor['id'],now()))
            return self._warehouse_movement(db,movement_id)
        return self._write(actor,('admin',),key,'warehouse-movement-reverse:'+movement_id,payload,perform)

    def _marketplace_reservation(self, db, reservation_id):
        row=db.execute('''SELECT m.*,u.name AS actor_name FROM marketplace_reservations m
            JOIN users u ON u.id=m.actor_id WHERE m.id=?''',(reservation_id,)).fetchone()
        if not row:
            raise DomainError(404,'Reservasi marketplace tidak ditemukan.')
        record=dict(row)
        source=self._finished_goods_receipt(db,record['receipt_id'])
        for field in ('reference','order_id','order_reference','product_id','sku','product_name','color','size',
                      'final_qc_record_id','final_qc_reference','batch_id','batch_reference'):
            record['receipt_reference' if field=='reference' else field]=source[field]
        release=db.execute('''SELECT r.*,u.name AS actor_name FROM marketplace_reservation_releases r
            JOIN users u ON u.id=r.actor_id WHERE r.reservation_id=?''',(reservation_id,)).fetchone()
        record['release']=dict(release) if release else None
        record['status']='released' if release else 'active'
        record['picked_quantity']=db.execute('''SELECT COALESCE(SUM(p.quantity),0) FROM marketplace_picks p
            WHERE p.reservation_id=? AND NOT EXISTS(
              SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)''',(reservation_id,)).fetchone()[0]
        record['remaining_quantity']=0 if release else record['quantity']-record['picked_quantity']
        return record

    def marketplace_reservation(self, reservation_id):
        with self.transaction() as db:
            return self._marketplace_reservation(db,reservation_id)

    def marketplace_reservations(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT m.id FROM marketplace_reservations m
                JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND (? IS NULL OR m.sequence<?) ORDER BY m.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._marketplace_reservation(db,row['id']) for row in ids]

    def create_marketplace_reservation(self, receipt_id, payload, actor, key):
        def perform(db):
            receipt=self._finished_goods_receipt(db,receipt_id)
            if receipt['status']!='active':
                raise DomainError(409,'Penerimaan barang jadi harus aktif sebelum stok direservasi.')
            if payload['reserved_date']<receipt['received_date']:
                raise DomainError(422,'Tanggal reservasi tidak boleh sebelum tanggal penerimaan barang jadi.')
            available=next((row['available_quantity'] for row in receipt['inventory']
                            if row['location'].casefold()==payload['location'].casefold()
                            and row['stock_status']=='sellable'),0)
            if payload['quantity']>available:
                raise DomainError(409,'Jumlah reservasi melebihi stok sellable yang tersedia di lokasi. Muat ulang inventori.')
            reservation_id=str(uuid4())
            db.execute('''INSERT INTO marketplace_reservations(id,reference,receipt_id,marketplace,
                external_order_reference,location,quantity,reserved_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(reservation_id,payload['reference'],receipt_id,payload['marketplace'],
                payload['external_order_reference'],payload['location'],payload['quantity'],payload['reserved_date'],
                payload['reason'],actor['id'],now()))
            return self._marketplace_reservation(db,reservation_id)
        return self._write(actor,('admin','operator'),key,'marketplace-reservation:'+receipt_id,payload,perform)

    def release_marketplace_reservation(self, reservation_id, payload, actor, key):
        def perform(db):
            reservation=self._marketplace_reservation(db,reservation_id)
            if reservation['release']:
                raise DomainError(409,'Reservasi marketplace sudah dilepaskan.')
            if reservation['picked_quantity']:
                raise DomainError(409,'Koreksi semua pick aktif sebelum melepas reservasi marketplace.')
            if payload['released_date']<reservation['reserved_date']:
                raise DomainError(422,'Tanggal pelepasan tidak boleh sebelum tanggal reservasi.')
            db.execute('''INSERT INTO marketplace_reservation_releases(reservation_id,released_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?)''',(reservation_id,payload['released_date'],payload['reason'],actor['id'],now()))
            return self._marketplace_reservation(db,reservation_id)
        return self._write(actor,('admin','operator'),key,'marketplace-reservation-release:'+reservation_id,payload,perform)

    def _marketplace_pick(self, db, pick_id):
        row=db.execute('''SELECT p.*,u.name AS actor_name FROM marketplace_picks p
            JOIN users u ON u.id=p.actor_id WHERE p.id=?''',(pick_id,)).fetchone()
        if not row:
            raise DomainError(404,'Catatan pick tidak ditemukan.')
        record=dict(row)
        source=self._marketplace_reservation(db,record['reservation_id'])
        for field in ('reference','receipt_id','receipt_reference','order_id','order_reference','product_id','sku',
                      'product_name','color','size','marketplace','external_order_reference','location',
                      'final_qc_record_id','final_qc_reference','batch_id','batch_reference'):
            record['reservation_reference' if field=='reference' else field]=source[field]
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM marketplace_pick_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.pick_id=?''',(pick_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        record['packed_quantity']=db.execute('''SELECT COALESCE(SUM(k.quantity),0) FROM marketplace_packs k
            WHERE k.pick_id=? AND NOT EXISTS(
              SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)''',(pick_id,)).fetchone()[0]
        record['remaining_quantity']=0 if reversal else record['quantity']-record['packed_quantity']
        return record

    def marketplace_pick(self, pick_id):
        with self.transaction() as db:
            return self._marketplace_pick(db,pick_id)

    def marketplace_picks(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT p.id FROM marketplace_picks p JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND (? IS NULL OR p.sequence<?) ORDER BY p.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._marketplace_pick(db,row['id']) for row in ids]

    def create_marketplace_pick(self, reservation_id, payload, actor, key):
        def perform(db):
            reservation=self._marketplace_reservation(db,reservation_id)
            if reservation['status']!='active':
                raise DomainError(409,'Reservasi marketplace harus aktif sebelum pick dicatat.')
            if payload['picked_date']<reservation['reserved_date']:
                raise DomainError(422,'Tanggal pick tidak boleh sebelum tanggal reservasi.')
            if payload['quantity']>reservation['remaining_quantity']:
                raise DomainError(409,'Jumlah pick melebihi reservasi yang belum dipick. Muat ulang reservasi.')
            pick_id=str(uuid4())
            db.execute('''INSERT INTO marketplace_picks(id,reference,reservation_id,quantity,staging_location,
                picked_date,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',(pick_id,payload['reference'],
                reservation_id,payload['quantity'],payload['staging_location'],payload['picked_date'],
                payload['reason'],actor['id'],now()))
            return self._marketplace_pick(db,pick_id)
        return self._write(actor,('admin','operator'),key,'marketplace-pick:'+reservation_id,payload,perform)

    def reverse_marketplace_pick(self, pick_id, payload, actor, key):
        def perform(db):
            pick=self._marketplace_pick(db,pick_id)
            if pick['reversal']:
                raise DomainError(409,'Catatan pick sudah dikoreksi.')
            if pick['packed_quantity']:
                raise DomainError(409,'Koreksi semua pack aktif sebelum mengoreksi pick.')
            db.execute('''INSERT INTO marketplace_pick_reversals(pick_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(pick_id,payload['reason'],actor['id'],now()))
            return self._marketplace_pick(db,pick_id)
        return self._write(actor,('admin',),key,'marketplace-pick-reverse:'+pick_id,payload,perform)

    def _marketplace_pack(self, db, pack_id):
        row=db.execute('''SELECT k.*,u.name AS actor_name FROM marketplace_packs k
            JOIN users u ON u.id=k.actor_id WHERE k.id=?''',(pack_id,)).fetchone()
        if not row:
            raise DomainError(404,'Catatan pack tidak ditemukan.')
        record=dict(row)
        source=self._marketplace_pick(db,record['pick_id'])
        for field in ('reference','reservation_id','reservation_reference','receipt_id','receipt_reference','order_id',
                      'order_reference','product_id','sku','product_name','color','size','marketplace',
                      'external_order_reference','location','staging_location','picked_date','final_qc_record_id',
                      'final_qc_reference','batch_id','batch_reference'):
            record['pick_reference' if field=='reference' else field]=source[field]
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM marketplace_pack_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.pack_id=?''',(pack_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        record['shipped_quantity']=db.execute('''SELECT COALESCE(SUM(s.quantity),0) FROM marketplace_shipments s
            WHERE s.pack_id=? AND NOT EXISTS(
              SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)''',(pack_id,)).fetchone()[0]
        record['remaining_quantity']=0 if reversal else record['quantity']-record['shipped_quantity']
        return record

    def marketplace_pack(self, pack_id):
        with self.transaction() as db:
            return self._marketplace_pack(db,pack_id)

    def marketplace_packs(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT k.id FROM marketplace_packs k JOIN marketplace_picks p ON p.id=k.pick_id
                JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND (? IS NULL OR k.sequence<?) ORDER BY k.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._marketplace_pack(db,row['id']) for row in ids]

    def create_marketplace_pack(self, pick_id, payload, actor, key):
        def perform(db):
            pick=self._marketplace_pick(db,pick_id)
            if pick['status']!='active':
                raise DomainError(409,'Pick marketplace harus aktif sebelum pack dicatat.')
            if payload['packed_date']<pick['picked_date']:
                raise DomainError(422,'Tanggal pack tidak boleh sebelum tanggal pick.')
            if payload['quantity']>pick['remaining_quantity']:
                raise DomainError(409,'Jumlah pack melebihi pick yang belum dipack. Muat ulang pick.')
            pack_id=str(uuid4())
            db.execute('''INSERT INTO marketplace_packs(id,reference,pick_id,quantity,packed_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?)''',(pack_id,payload['reference'],pick_id,payload['quantity'],
                payload['packed_date'],payload['reason'],actor['id'],now()))
            return self._marketplace_pack(db,pack_id)
        return self._write(actor,('admin','operator'),key,'marketplace-pack:'+pick_id,payload,perform)

    def reverse_marketplace_pack(self, pack_id, payload, actor, key):
        def perform(db):
            pack=self._marketplace_pack(db,pack_id)
            if pack['reversal']:
                raise DomainError(409,'Catatan pack sudah dikoreksi.')
            if pack['shipped_quantity']:
                raise DomainError(409,'Koreksi semua pengiriman aktif sebelum mengoreksi pack.')
            db.execute('''INSERT INTO marketplace_pack_reversals(pack_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(pack_id,payload['reason'],actor['id'],now()))
            return self._marketplace_pack(db,pack_id)
        return self._write(actor,('admin',),key,'marketplace-pack-reverse:'+pack_id,payload,perform)

    def _marketplace_shipment(self, db, shipment_id):
        row=db.execute('''SELECT s.*,u.name AS actor_name FROM marketplace_shipments s
            JOIN users u ON u.id=s.actor_id WHERE s.id=?''',(shipment_id,)).fetchone()
        if not row:
            raise DomainError(404,'Catatan pengiriman tidak ditemukan.')
        record=dict(row)
        source=self._marketplace_pack(db,record['pack_id'])
        for field in ('reference','pick_id','pick_reference','reservation_id','reservation_reference','receipt_id',
                      'receipt_reference','order_id','order_reference','product_id','sku','product_name','color','size',
                      'marketplace','external_order_reference','location','staging_location','picked_date','packed_date',
                      'final_qc_record_id','final_qc_reference','batch_id','batch_reference'):
            record['pack_reference' if field=='reference' else field]=source[field]
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM marketplace_shipment_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.shipment_id=?''',(shipment_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'shipped'
        record['returned_quantity']=db.execute('''SELECT COALESCE(SUM(t.quantity),0) FROM marketplace_returns t
            WHERE t.shipment_id=? AND NOT EXISTS(
              SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)''',(shipment_id,)).fetchone()[0]
        record['returnable_quantity']=0 if reversal else record['quantity']-record['returned_quantity']
        return record

    def marketplace_shipment(self, shipment_id):
        with self.transaction() as db:
            return self._marketplace_shipment(db,shipment_id)

    def marketplace_shipments(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT s.id FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
                JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND (? IS NULL OR s.sequence<?) ORDER BY s.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._marketplace_shipment(db,row['id']) for row in ids]

    def create_marketplace_shipment(self, pack_id, payload, actor, key):
        def perform(db):
            pack=self._marketplace_pack(db,pack_id)
            if pack['status']!='active':
                raise DomainError(409,'Pack marketplace harus aktif sebelum pengiriman dicatat.')
            if payload['shipped_date']<pack['packed_date']:
                raise DomainError(422,'Tanggal kirim tidak boleh sebelum tanggal pack.')
            if payload['quantity']>pack['remaining_quantity']:
                raise DomainError(409,'Jumlah kirim melebihi pack yang belum dikirim. Muat ulang pack.')
            shipment_id=str(uuid4())
            db.execute('''INSERT INTO marketplace_shipments(id,reference,pack_id,quantity,carrier,tracking_number,
                shipped_date,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',(shipment_id,
                payload['reference'],pack_id,payload['quantity'],payload['carrier'],payload['tracking_number'],
                payload['shipped_date'],payload['reason'],actor['id'],now()))
            return self._marketplace_shipment(db,shipment_id)
        return self._write(actor,('admin','operator'),key,'marketplace-shipment:'+pack_id,payload,perform)

    def reverse_marketplace_shipment(self, shipment_id, payload, actor, key):
        def perform(db):
            shipment=self._marketplace_shipment(db,shipment_id)
            if shipment['reversal']:
                raise DomainError(409,'Catatan pengiriman sudah dikoreksi.')
            if shipment['returned_quantity']:
                raise DomainError(409,'Koreksi semua retur aktif sebelum mengoreksi pengiriman.')
            db.execute('''INSERT INTO marketplace_shipment_reversals(shipment_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(shipment_id,payload['reason'],actor['id'],now()))
            return self._marketplace_shipment(db,shipment_id)
        return self._write(actor,('admin',),key,'marketplace-shipment-reverse:'+shipment_id,payload,perform)

    def _marketplace_return(self, db, return_id):
        row=db.execute('''SELECT t.*,u.name AS actor_name FROM marketplace_returns t
            JOIN users u ON u.id=t.actor_id WHERE t.id=?''',(return_id,)).fetchone()
        if not row:
            raise DomainError(404,'Catatan retur tidak ditemukan.')
        record=dict(row)
        source=self._marketplace_shipment(db,record['shipment_id'])
        for field in ('reference','pack_id','pack_reference','pick_id','pick_reference','reservation_id',
                      'reservation_reference','receipt_id','receipt_reference','order_id','order_reference','product_id',
                      'sku','product_name','color','size','marketplace','external_order_reference','location',
                      'staging_location','carrier','tracking_number','shipped_date','packed_date','final_qc_record_id',
                      'final_qc_reference','batch_id','batch_reference'):
            record['shipment_reference' if field=='reference' else field]=source[field]
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM marketplace_return_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.return_id=?''',(return_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        return record

    def marketplace_return(self, return_id):
        with self.transaction() as db:
            return self._marketplace_return(db,return_id)

    def marketplace_returns(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT t.id FROM marketplace_returns t JOIN marketplace_shipments s ON s.id=t.shipment_id
                JOIN marketplace_packs k ON k.id=s.pack_id JOIN marketplace_picks p ON p.id=k.pick_id
                JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND (? IS NULL OR t.sequence<?) ORDER BY t.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._marketplace_return(db,row['id']) for row in ids]

    def create_marketplace_return(self, shipment_id, payload, actor, key):
        def perform(db):
            shipment=self._marketplace_shipment(db,shipment_id)
            if shipment['status']!='shipped':
                raise DomainError(409,'Pengiriman harus aktif sebelum retur dicatat.')
            if payload['returned_date']<shipment['shipped_date']:
                raise DomainError(422,'Tanggal retur tidak boleh sebelum tanggal kirim.')
            if payload['quantity']>shipment['returnable_quantity']:
                raise DomainError(409,'Jumlah retur melebihi barang terkirim yang belum diretur. Muat ulang pengiriman.')
            return_id=str(uuid4())
            db.execute('''INSERT INTO marketplace_returns(id,reference,shipment_id,quantity,return_reason,
                return_location,stock_status,returned_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(return_id,payload['reference'],shipment_id,payload['quantity'],
                payload['return_reason'],payload['return_location'],payload['stock_status'],payload['returned_date'],
                payload['reason'],actor['id'],now()))
            return self._marketplace_return(db,return_id)
        return self._write(actor,('admin','operator'),key,'marketplace-return:'+shipment_id,payload,perform)

    def reverse_marketplace_return(self, return_id, payload, actor, key):
        def perform(db):
            record=self._marketplace_return(db,return_id)
            if record['reversal']:
                raise DomainError(409,'Catatan retur sudah dikoreksi.')
            db.execute('''INSERT INTO marketplace_return_reversals(return_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(return_id,payload['reason'],actor['id'],now()))
            return self._marketplace_return(db,return_id)
        return self._write(actor,('admin',),key,'marketplace-return-reverse:'+return_id,payload,perform)

    def _finished_goods_adjustment(self, db, adjustment_id):
        row=db.execute('''SELECT a.*,u.name AS actor_name FROM finished_goods_adjustments a
            JOIN users u ON u.id=a.actor_id WHERE a.id=?''',(adjustment_id,)).fetchone()
        if not row:
            raise DomainError(404,'Adjustment barang jadi tidak ditemukan.')
        record=dict(row)
        source=self._finished_goods_receipt(db,record['receipt_id'])
        for field in ('reference','order_id','order_reference','product_id','sku','product_name','color','size',
                      'final_qc_record_id','final_qc_reference','batch_id','batch_reference','received_date'):
            record['receipt_reference' if field=='reference' else field]=source[field]
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM finished_goods_adjustment_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.adjustment_id=?''',(adjustment_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        return record

    def finished_goods_adjustment(self, adjustment_id):
        with self.transaction() as db:
            return self._finished_goods_adjustment(db,adjustment_id)

    def finished_goods_adjustments(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT a.id FROM finished_goods_adjustments a
                JOIN finished_goods_receipts x ON x.id=a.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND (? IS NULL OR a.sequence<?) ORDER BY a.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._finished_goods_adjustment(db,row['id']) for row in ids]

    def create_finished_goods_adjustment(self, receipt_id, payload, actor, key):
        def perform(db):
            receipt=self._finished_goods_receipt(db,receipt_id)
            if receipt['status']!='active':
                raise DomainError(409,'Penerimaan barang jadi harus aktif sebelum adjustment dicatat.')
            if payload['adjusted_date']<receipt['received_date']:
                raise DomainError(422,'Tanggal adjustment tidak boleh sebelum tanggal penerimaan.')
            bucket=next((row for row in receipt['inventory'] if row['location'].casefold()==payload['location'].casefold()
                         and row['stock_status']==payload['stock_status']),None)
            usable=0 if not bucket else bucket['available_quantity'] if payload['stock_status']=='sellable' else bucket['quantity']
            if payload['quantity_delta']<0 and -payload['quantity_delta']>usable:
                raise DomainError(409,'Adjustment mengurangi stok melebihi saldo yang tidak terikat reservasi.')
            adjustment_id=str(uuid4())
            db.execute('''INSERT INTO finished_goods_adjustments(id,reference,receipt_id,location,stock_status,
                quantity_delta,adjusted_date,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (adjustment_id,payload['reference'],receipt_id,payload['location'],payload['stock_status'],
                 payload['quantity_delta'],payload['adjusted_date'],payload['reason'],actor['id'],now()))
            return self._finished_goods_adjustment(db,adjustment_id)
        return self._write(actor,('admin','operator'),key,'finished-goods-adjustment:'+receipt_id,payload,perform)

    def reverse_finished_goods_adjustment(self, adjustment_id, payload, actor, key):
        def perform(db):
            record=self._finished_goods_adjustment(db,adjustment_id)
            if record['reversal']:
                raise DomainError(409,'Adjustment barang jadi sudah dikoreksi.')
            db.execute('''INSERT INTO finished_goods_adjustment_reversals(adjustment_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(adjustment_id,payload['reason'],actor['id'],now()))
            return self._finished_goods_adjustment(db,adjustment_id)
        return self._write(actor,('admin',),key,'finished-goods-adjustment-reverse:'+adjustment_id,payload,perform)

    def create_cutting_run(self, order_id, payload, actor, key):
        def perform(db):
            order=self._order(db,order_id)
            issue=self._issue_consumption(db,payload['issue_id'])
            if issue['order_id']!=order_id:
                raise DomainError(422,'Pengeluaran bahan harus berasal dari order hasil cutting ini.')
            line_ids={line['id'] for line in order['lines']}
            if any(row['line_id'] not in line_ids for row in payload['outputs']):
                raise DomainError(422,'Seluruh SKU hasil cutting harus berasal dari order ini.')
            consumption=self._consume_material(db,payload,actor)
            outputs=[self._transfer(db,dict(line_id=row['line_id'],quantity=row['quantity'],from_stage='cutting',
                                           to_stage='sewing',reason=payload['reason']),actor)['id'] for row in payload['outputs']]
            run_id=str(uuid4())
            db.execute('''INSERT INTO cutting_runs(id,reference,order_id,consumption_id,movement_ids,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?)''',(run_id,payload['reference'],order_id,consumption['id'],json.dumps(outputs),
                                          payload['reason'],actor['id'],now()))
            return self._cutting_run(db,run_id)
        return self._write(actor,('admin','operator'),key,'cutting-run:'+order_id,payload,perform)

    def reverse_cutting_run(self, run_id, payload, actor, key):
        def perform(db):
            run=self._cutting_run(db,run_id,False)
            if run['reversal']:
                raise DomainError(409,'Hasil cutting sudah dikoreksi.')
            if any(row['bundled_quantity'] for row in run['outputs']):
                raise DomainError(409,'Koreksi semua bundle aktif sebelum mengoreksi hasil cutting.')
            for row in run['outputs']:
                if row['reversed_by']:
                    raise DomainError(409,'Perpindahan hasil cutting sudah dikoreksi terpisah; periksa riwayat.')
                self._transfer(db,dict(line_id=row['line_id'],quantity=row['quantity'],from_stage='sewing',
                                       to_stage='cutting',reason=payload['reason']),actor,reversal_of=row['id'])
            consumption=db.execute('SELECT * FROM material_consumption WHERE id=?',(run['consumption_id'],)).fetchone()
            self._consumption_event(db,consumption['issue_id'],-consumption['used_milli'],-consumption['waste_milli'],
                                    payload['reason'],actor['id'],consumption['id'])
            db.execute('INSERT INTO cutting_run_reversals(run_id,reason,actor_id,created_at) VALUES(?,?,?,?)',
                       (run_id,payload['reason'],actor['id'],now()))
            return self._cutting_run(db,run_id)
        return self._write(actor,('admin',),key,'cutting-reverse:'+run_id,payload,perform)

    def _purchase_request(self, db, request_id):
        row = db.execute('''SELECT p.*,u.name AS actor_name,o.reference AS order_reference
            FROM purchase_requests p JOIN users u ON u.id=p.actor_id
            LEFT JOIN orders o ON o.id=p.order_id WHERE p.id=?''', (request_id,)).fetchone()
        if not row:
            raise DomainError(404, 'Permintaan pembelian tidak ditemukan.')
        record = dict(row)
        record['estimated_value'] = format(Decimal(record.pop('estimated_value_minor')) / 100, '.2f')
        record['currency'] = 'IDR'
        record['lines'] = json.loads(record['lines'])
        record['history'] = [dict(event) for event in db.execute('''SELECT e.*,u.name AS actor_name
            FROM purchase_request_events e JOIN users u ON u.id=e.actor_id
            WHERE request_id=? ORDER BY sequence DESC''', (request_id,))]
        record['status'] = record['history'][0]['status']
        record['revision'] = record['history'][0]['sequence']
        record['purchase_orders'] = [dict(row) for row in db.execute('''SELECT p.id,p.reference,
            CASE WHEN c.id IS NOT NULL THEN 'cancelled' WHEN z.order_id IS NOT NULL THEN 'closed' ELSE 'issued' END AS status
            FROM purchase_orders p LEFT JOIN purchase_order_cancellations c ON c.order_id=p.id
            LEFT JOIN purchase_order_closures z ON z.order_id=p.id
            WHERE p.request_id=? ORDER BY p.sequence DESC''', (request_id,))]
        return record

    def purchase_request(self, request_id):
        with self.transaction() as db:
            return self._purchase_request(db, request_id)

    def purchase_requests(self, limit=100, before=None, status='all', order_id=None):
        with self.transaction() as db:
            if order_id is not None and not db.execute('SELECT 1 FROM orders WHERE id=?', (order_id,)).fetchone():
                raise DomainError(404, 'Order produksi tidak ditemukan.')
            ids = db.execute('''SELECT p.id FROM purchase_requests p WHERE (? IS NULL OR p.sequence<?)
                AND (? IS NULL OR p.order_id=?) AND (?='all' OR
                (SELECT status FROM purchase_request_events WHERE request_id=p.id ORDER BY sequence DESC LIMIT 1)=?)
                ORDER BY p.sequence DESC LIMIT ?''', (before,before,order_id,order_id,status,status,limit)).fetchall()
            return [self._purchase_request(db, row[0]) for row in ids]

    def create_purchase_request(self, payload, actor, key):
        def perform(db):
            if payload['order_id'] is not None and not db.execute('SELECT 1 FROM orders WHERE id=?', (payload['order_id'],)).fetchone():
                raise DomainError(404, 'Order produksi tidak ditemukan.')
            lines = []
            for line in payload['lines']:
                material = db.execute('SELECT code,name,unit FROM materials WHERE id=?', (line['material_id'],)).fetchone()
                if not material:
                    raise DomainError(404, 'Bahan permintaan tidak ditemukan.')
                self._material_amount(line['quantity'], material['unit'])
                lines.append(line | dict(material))
            request_id, timestamp = str(uuid4()), now()
            db.execute('''INSERT INTO purchase_requests(id,reference,order_id,required_date,estimated_value_minor,lines,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)''', (request_id,payload['reference'],payload['order_id'],payload['required_date'],
                    int(Decimal(payload['estimated_value'])*100),json.dumps(lines),payload['reason'],actor['id'],timestamp))
            db.execute('''INSERT INTO purchase_request_events(request_id,status,reason,actor_id,created_at)
                VALUES(?,'submitted',?,?,?)''', (request_id,payload['reason'],actor['id'],timestamp))
            return self._purchase_request(db, request_id)
        return self._write(actor, ('admin','operator'), key, 'purchase-request', payload, perform)

    def decide_purchase_request(self, request_id, payload, actor, key):
        def perform(db):
            current = self._purchase_request(db, request_id)
            role = db.execute('SELECT role FROM users WHERE id=?', (actor['id'],)).fetchone()[0]
            if role != 'admin' and not (payload['status']=='cancelled' and
                    current['status']=='submitted' and current['actor_id']==actor['id']):
                raise DomainError(403, 'Hanya admin memutuskan PR; pemohon boleh membatalkan pengajuannya yang belum diputuskan.')
            if current['revision'] != payload['expected_revision']:
                raise DomainError(409, 'PR sudah berubah. Buka ulang rincian dan periksa keputusan terbaru.')
            if current['status'] not in ('submitted','approved') or (current['status']=='approved' and payload['status']!='cancelled'):
                raise DomainError(409, 'Status PR tidak mengizinkan keputusan ini.')
            if any(po['status']!='cancelled' for po in current['purchase_orders']):
                raise DomainError(409, 'PR memiliki PO aktif atau ditutup. PR dengan PO ditutup sudah final; PO aktif harus dibatalkan terlebih dahulu.')
            db.execute('''INSERT INTO purchase_request_events(request_id,status,reason,actor_id,created_at)
                VALUES(?,?,?,?,?)''', (request_id,payload['status'],payload['reason'],actor['id'],now()))
            return self._purchase_request(db, request_id)
        return self._write(actor, ('admin','operator'), key, 'purchase-request-decision:'+request_id, payload, perform)

    def suppliers(self, limit=100, offset=0):
        with self.transaction() as db:
            return [dict(row) for row in db.execute('''SELECT s.*,u.name AS actor_name FROM suppliers s
                JOIN users u ON u.id=s.actor_id ORDER BY s.code,s.id LIMIT ? OFFSET ?''', (limit,offset))]

    def create_supplier(self, payload, actor, key):
        def perform(db):
            record = dict(id=str(uuid4()), **payload, actor_id=actor['id'], created_at=now())
            db.execute('''INSERT INTO suppliers(id,code,name,contact,address,reason,actor_id,created_at)
                VALUES(:id,:code,:name,:contact,:address,:reason,:actor_id,:created_at)''', record)
            return record
        return self._write(actor, ('admin',), key, 'supplier', payload, perform)

    def _purchase_order(self, db, order_id):
        row = db.execute('''SELECT p.*,u.name AS actor_name,r.reference AS request_reference,r.order_id AS production_order_id
            FROM purchase_orders p JOIN users u ON u.id=p.actor_id JOIN purchase_requests r ON r.id=p.request_id
            WHERE p.id=?''', (order_id,)).fetchone()
        if not row:
            raise DomainError(404, 'PO tidak ditemukan.')
        record = dict(row)
        record['supplier'] = json.loads(record['supplier'])
        record['lines'] = json.loads(record['lines'])
        record['total'] = format(Decimal(record.pop('total_minor')) / 100, '.2f')
        record['currency'] = 'IDR'
        cancelled = db.execute('''SELECT c.*,u.name AS actor_name FROM purchase_order_cancellations c
            JOIN users u ON u.id=c.actor_id WHERE c.order_id=?''', (order_id,)).fetchone()
        record['cancellation'] = dict(cancelled) if cancelled else None
        closed = db.execute('''SELECT c.*,u.name AS actor_name FROM purchase_order_closures c
            JOIN users u ON u.id=c.actor_id WHERE c.order_id=?''', (order_id,)).fetchone()
        record['closure'] = dict(closed) if closed else None
        record['status'] = 'cancelled' if cancelled else 'closed' if closed else 'issued'
        record['receipts'] = []
        received = {}
        for row in db.execute('''SELECT b.id AS batch_id,b.reference,b.material_id,b.location,b.received_date,
            m.id AS receipt_id,m.quantity_milli,m.reason,m.created_at,u.name AS actor_name,
            (SELECT id FROM material_movements WHERE reversal_of=m.id) AS reversed_by
            FROM purchase_order_receipts x JOIN material_batches b ON b.id=x.batch_id
            JOIN material_movements m ON m.batch_id=b.id AND m.kind='receipt'
            JOIN users u ON u.id=m.actor_id WHERE x.purchase_order_id=? ORDER BY m.sequence DESC''', (order_id,)):
            receipt = dict(row)
            quantity = receipt.pop('quantity_milli')
            receipt['quantity'] = self._material_decimal(quantity)
            record['receipts'].append(receipt)
            if not receipt['reversed_by']:
                received[receipt['material_id']] = received.get(receipt['material_id'],0)+quantity
        record['qc_intakes'] = [self._quality_intake(db, row[0]) for row in db.execute(
            'SELECT id FROM qc_intakes WHERE purchase_order_id=? ORDER BY sequence DESC', (order_id,))]
        for line in record['lines']:
            amount = received.get(line['material_id'],0)
            line['received'] = self._material_decimal(amount)
            line['remaining'] = self._material_decimal(int(Decimal(line['quantity'])*1000)-amount)
            totals = db.execute('SELECT COALESCE(SUM(held),0),COALESCE(SUM(rejected),0) FROM qc_totals WHERE purchase_order_id=? AND material_id=?', (order_id,line['material_id'])).fetchone()
            line['held'] = self._material_decimal(totals[0])
            line['rejected'] = self._material_decimal(totals[1])
            line['receivable'] = self._material_decimal(int(Decimal(line['remaining'])*1000)-totals[0])
            if record['status'] != 'issued':
                line['receivable'] = '0.000'
            returns = db.execute('''SELECT COALESCE(SUM(t.returned),0),COALESCE(SUM(t.return_pending),0)
                FROM qc_return_totals t JOIN qc_intakes q ON q.id=t.id
                WHERE q.purchase_order_id=? AND q.material_id=?''', (order_id,line['material_id'])).fetchone()
            line['returned'] = self._material_decimal(returns[0])
            line['return_pending'] = self._material_decimal(returns[1])
        record['fulfillment'] = ('received' if all(l['remaining']=='0.000' for l in record['lines'])
                                 else 'partial' if received else 'pending')
        return record

    def purchase_order(self, order_id):
        with self.transaction() as db:
            return self._purchase_order(db, order_id)

    def purchase_orders(self, limit=100, before=None, status='all', request_id=None):
        with self.transaction() as db:
            ids = db.execute('''SELECT p.id FROM purchase_orders p
                LEFT JOIN purchase_order_cancellations c ON c.order_id=p.id
                LEFT JOIN purchase_order_closures z ON z.order_id=p.id
                WHERE (? IS NULL OR p.sequence<?) AND (? IS NULL OR p.request_id=?)
                AND (?='all' OR (?='issued' AND c.id IS NULL AND z.order_id IS NULL)
                    OR (?='cancelled' AND c.id IS NOT NULL) OR (?='closed' AND z.order_id IS NOT NULL))
                ORDER BY p.sequence DESC LIMIT ?''', (before,before,request_id,request_id,status,status,status,status,limit)).fetchall()
            return [self._purchase_order(db, row[0]) for row in ids]

    def create_purchase_order(self, payload, actor, key):
        def perform(db):
            pr = self._purchase_request(db, payload['request_id'])
            if pr['status'] != 'approved' or pr['revision'] != payload['expected_revision']:
                raise DomainError(409, 'PR harus disetujui dan memakai revisi terbaru. Buka ulang PR.')
            if any(po['status']!='cancelled' for po in pr['purchase_orders']):
                raise DomainError(409, 'PR sudah memiliki PO aktif atau ditutup. Gunakan PR baru untuk pembelian tambahan.')
            supplier = db.execute('SELECT id,code,name,contact,address FROM suppliers WHERE id=?', (payload['supplier_id'],)).fetchone()
            if not supplier:
                raise DomainError(404, 'Pemasok tidak ditemukan.')
            prices = {line['material_id']:line['unit_price'] for line in payload['prices']}
            if set(prices) != {line['material_id'] for line in pr['lines']}:
                raise DomainError(422, 'Isi harga tepat satu kali untuk seluruh bahan PR. Jumlah bahan mengikuti PR.')
            lines, total = [], 0
            for line in pr['lines']:
                price = prices[line['material_id']]
                minor = int((Decimal(line['quantity'])*Decimal(price)*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                if minor < 1:
                    raise DomainError(422, 'Nilai tiap baris setelah pembulatan harus minimal Rp0,01.')
                total += minor
                lines.append(line | dict(unit_price=price,line_total=format(Decimal(minor)/100,'.2f')))
            if total > int(Decimal(pr['estimated_value'])*100):
                raise DomainError(409, 'Total PO melebihi estimasi PR yang disetujui. Ajukan PR baru dengan nilai yang sesuai.')
            order_id = str(uuid4())
            db.execute('''INSERT INTO purchase_orders(id,reference,request_id,request_revision,supplier_id,supplier,
                expected_date,terms,lines,total_minor,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (order_id,payload['reference'],pr['id'],pr['revision'],supplier['id'],json.dumps(dict(supplier)),
                 payload['expected_date'],payload['terms'],json.dumps(lines),total,payload['reason'],actor['id'],now()))
            return self._purchase_order(db, order_id)
        return self._write(actor, ('admin',), key, 'purchase-order', payload, perform)

    def cancel_purchase_order(self, order_id, payload, actor, key):
        def perform(db):
            po = self._purchase_order(db, order_id)
            if po['status'] != 'issued':
                raise DomainError(409, 'PO sudah dibatalkan atau ditutup.')
            if any(l['return_pending']!='0.000' for l in po['lines']):
                raise DomainError(409, 'Selesaikan retur bahan reject sebelum membatalkan PO.')
            if po['fulfillment'] != 'pending' or any(l['held']!='0.000' for l in po['lines']):
                raise DomainError(409, 'PO memiliki penerimaan aktif atau bahan hold. Selesaikan QC atau koreksi penerimaan sebelum membatalkan PO.')
            db.execute('''INSERT INTO purchase_order_cancellations(id,order_id,reason,actor_id,created_at)
                VALUES(?,?,?,?,?)''', (str(uuid4()),order_id,payload['reason'],actor['id'],now()))
            return self._purchase_order(db, order_id)
        return self._write(actor, ('admin',), key, 'purchase-order-cancel:'+order_id, payload, perform)

    def close_purchase_order(self, order_id, payload, actor, key):
        def perform(db):
            po = self._purchase_order(db, order_id)
            if po['status'] != 'issued':
                raise DomainError(409, 'PO sudah dibatalkan atau ditutup.')
            if po['fulfillment'] == 'pending':
                raise DomainError(409, 'Belum ada penerimaan layak pakai. Gunakan pembatalan jika pembelian tidak dilanjutkan.')
            if any(l['held']!='0.000' or l['return_pending']!='0.000' for l in po['lines']):
                raise DomainError(409, 'Selesaikan bahan hold dan retur reject sebelum menutup PO.')
            db.execute('INSERT INTO purchase_order_closures(order_id,reason,actor_id,created_at) VALUES(?,?,?,?)',
                       (order_id,payload['reason'],actor['id'],now()))
            return self._purchase_order(db, order_id)
        return self._write(actor, ('admin',), key, 'purchase-order-close:'+order_id, payload, perform)

    def receive_purchase_order(self, order_id, payload, actor, key):
        def perform(db):
            po = self._purchase_order(db, order_id)
            if po['status'] != 'issued':
                raise DomainError(409, 'PO sudah dibatalkan atau ditutup; penerimaan tidak diizinkan.')
            line = next((l for l in po['lines'] if l['material_id']==payload['material_id']), None)
            if not line:
                raise DomainError(422, 'Bahan tidak tercantum pada PO.')
            quantity = self._material_amount(payload['quantity'], line['unit'])
            if quantity > int(Decimal(line['receivable'])*1000):
                raise DomainError(409, 'Jumlah penerimaan melebihi sisa PO setelah memperhitungkan bahan hold. Muat ulang rincian PO.')
            batch = self._receive_material(db, payload | {'supplier':po['supplier']['name']}, actor)
            db.execute('INSERT INTO purchase_order_receipts(batch_id,purchase_order_id) VALUES(?,?)', (batch['id'],order_id))
            return self._material_batch(db, batch['id'])
        return self._write(actor, ('admin','operator'), key, 'purchase-order-receipt:'+order_id, payload, perform)

    def _quality_intake(self, db, intake_id):
        row = db.execute('''SELECT q.*,m.code,m.name,m.unit,u.name AS actor_name,p.reference AS purchase_order_reference,
            t.accepted,t.rejected,t.held,
            EXISTS(SELECT 1 FROM purchase_order_closures WHERE order_id=q.purchase_order_id) AS po_closed,
            EXISTS(SELECT 1 FROM purchase_order_cancellations WHERE order_id=q.purchase_order_id) AS po_cancelled FROM qc_intakes q JOIN materials m ON m.id=q.material_id
            JOIN users u ON u.id=q.actor_id JOIN purchase_orders p ON p.id=q.purchase_order_id
            JOIN qc_totals t ON t.id=q.id WHERE q.id=?''', (intake_id,)).fetchone()
        if not row:
            raise DomainError(404, 'Kedatangan QC tidak ditemukan.')
        record = dict(row)
        record['quantity'] = self._material_decimal(record.pop('quantity_milli'))
        for field in ('accepted','rejected','held'):
            record[field] = self._material_decimal(record[field])
        cancelled = db.execute('''SELECT c.*,u.name AS actor_name FROM qc_intake_cancellations c
            JOIN users u ON u.id=c.actor_id WHERE intake_id=?''', (intake_id,)).fetchone()
        record['cancellation'] = dict(cancelled) if cancelled else None
        totals = db.execute('SELECT returned,return_pending FROM qc_return_totals WHERE id=?', (intake_id,)).fetchone()
        record['returned'],record['return_pending'] = map(self._material_decimal, totals)
        record['returns'] = []
        for row in db.execute('''SELECT r.*,u.name AS actor_name,
            (SELECT id FROM supplier_returns WHERE reversal_of=r.id) AS reversed_by,
            (SELECT reference FROM supplier_returns WHERE id=r.reversal_of) AS original_reference
            FROM supplier_returns r JOIN users u ON u.id=r.actor_id WHERE r.intake_id=? ORDER BY r.sequence DESC''', (intake_id,)):
            item = dict(row)
            item['quantity'] = self._material_decimal(item.pop('quantity_milli'))
            record['returns'].append(item)
        record['history'] = []
        for row in db.execute('''SELECT d.*,u.name AS actor_name,b.reference AS batch_reference,
            (SELECT id FROM qc_decisions WHERE reversal_of=d.id) AS reversed_by
            FROM qc_decisions d JOIN users u ON u.id=d.actor_id LEFT JOIN material_batches b ON b.id=d.batch_id
            WHERE d.intake_id=? ORDER BY d.sequence DESC''', (intake_id,)):
            item = dict(row)
            item['quantity'] = self._material_decimal(item.pop('quantity_milli'))
            record['history'].append(item)
        return record

    def quality_intake(self, intake_id):
        with self.transaction() as db:
            return self._quality_intake(db, intake_id)

    def return_supplier(self, intake_id, payload, actor, key):
        def perform(db):
            intake = self._quality_intake(db, intake_id)
            if intake['cancellation'] or intake['po_closed']:
                raise DomainError(409, 'Kedatangan dibatalkan atau PO sudah ditutup.')
            quantity = self._material_amount(payload['quantity'],intake['unit'])
            if quantity>int(Decimal(intake['return_pending'])*1000):
                raise DomainError(409, 'Jumlah retur melebihi reject yang belum dikirim kembali. Muat ulang QC.')
            if payload['returned_date']<intake['received_date']:
                raise DomainError(422, 'Tanggal retur tidak boleh sebelum kedatangan.')
            db.execute('''INSERT INTO supplier_returns(id,intake_id,reference,returned_date,quantity_milli,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?)''', (str(uuid4()),intake_id,payload['reference'],payload['returned_date'],quantity,
                                           payload['reason'],actor['id'],now()))
            return self._quality_intake(db, intake_id)
        return self._write(actor, ('admin',), key, 'supplier-return:'+intake_id, payload, perform)

    def reverse_supplier_return(self, return_id, payload, actor, key):
        def perform(db):
            original = db.execute('SELECT * FROM supplier_returns WHERE id=?', (return_id,)).fetchone()
            if not original:
                raise DomainError(404, 'Catatan retur tidak ditemukan.')
            if original['reversal_of'] or db.execute('SELECT 1 FROM supplier_returns WHERE reversal_of=?',(return_id,)).fetchone():
                raise DomainError(409, 'Retur sudah dikoreksi atau merupakan koreksi.')
            intake = self._quality_intake(db,original['intake_id'])
            if intake['po_closed'] or intake['po_cancelled']:
                raise DomainError(409, 'PO sudah ditutup atau dibatalkan; catatan retur sudah final.')
            db.execute('''INSERT INTO supplier_returns(id,intake_id,quantity_milli,reversal_of,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?)''', (str(uuid4()),intake['id'],-original['quantity_milli'],return_id,
                                          payload['reason'],actor['id'],now()))
            return self._quality_intake(db,intake['id'])
        return self._write(actor, ('admin',), key, 'supplier-return-reverse:'+return_id, payload, perform)

    def create_quality_intake(self, order_id, payload, actor, key):
        def perform(db):
            po = self._purchase_order(db, order_id)
            if po['status'] != 'issued':
                raise DomainError(409, 'PO sudah dibatalkan atau ditutup.')
            line = next((l for l in po['lines'] if l['material_id']==payload['material_id']),None)
            if not line:
                raise DomainError(422, 'Bahan tidak tercantum pada PO.')
            quantity = self._material_amount(payload['quantity'],line['unit'])
            if quantity>int(Decimal(line['receivable'])*1000):
                raise DomainError(409, 'Kedatangan melebihi sisa PO setelah memperhitungkan bahan hold.')
            intake_id = str(uuid4())
            db.execute('''INSERT INTO qc_intakes(id,purchase_order_id,material_id,reference,location,received_date,
                quantity_milli,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (intake_id,order_id,payload['material_id'],payload['reference'],payload['location'],payload['received_date'],
                 quantity,payload['reason'],actor['id'],now()))
            return self._quality_intake(db,intake_id)
        return self._write(actor,('admin','operator'),key,'qc-intake:'+order_id,payload,perform)

    def decide_quality(self, intake_id, payload, actor, key):
        def perform(db):
            intake = self._quality_intake(db,intake_id)
            if intake['cancellation'] or intake['po_closed'] or intake['po_cancelled']:
                raise DomainError(409,'Kedatangan dibatalkan atau PO sudah final.')
            quantity = self._material_amount(payload['quantity'],intake['unit'])
            if quantity>int(Decimal(intake['held'])*1000):
                raise DomainError(409,'Jumlah keputusan melebihi bahan hold. Muat ulang QC.')
            batch = None
            if payload['kind']=='accept':
                po = self._purchase_order(db,intake['purchase_order_id'])
                batch = self._receive_material(db,dict(material_id=intake['material_id'],reference=payload['reference'],
                    location=payload['location'],supplier=po['supplier']['name'],received_date=intake['received_date'],
                    quantity=payload['quantity'],reason=payload['reason']),actor)
            db.execute('''INSERT INTO qc_decisions(id,intake_id,kind,quantity_milli,batch_id,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?)''', (str(uuid4()),intake_id,payload['kind'],quantity,batch['id'] if batch else None,
                                           payload['reason'],actor['id'],now()))
            if batch:
                db.execute('INSERT INTO purchase_order_receipts(batch_id,purchase_order_id) VALUES(?,?)',
                           (batch['id'],intake['purchase_order_id']))
            return self._quality_intake(db,intake_id)
        return self._write(actor,('admin',),key,'qc-decision:'+intake_id,payload,perform)

    def reverse_quality(self, decision_id, payload, actor, key):
        def perform(db):
            original = db.execute('SELECT * FROM qc_decisions WHERE id=?',(decision_id,)).fetchone()
            if not original:
                raise DomainError(404,'Keputusan QC tidak ditemukan.')
            if original['reversal_of'] or db.execute('SELECT 1 FROM qc_decisions WHERE reversal_of=?',(decision_id,)).fetchone():
                raise DomainError(409,'Keputusan sudah dikoreksi atau merupakan catatan koreksi.')
            intake = self._quality_intake(db,original['intake_id'])
            po = self._purchase_order(db,intake['purchase_order_id'])
            if intake['cancellation'] or po['status']!='issued':
                raise DomainError(409,'Kedatangan dibatalkan atau PO sudah final.')
            if original['kind']=='reject':
                if original['quantity_milli']>int(Decimal(intake['return_pending'])*1000):
                    raise DomainError(409, 'Bahan sudah diretur. Koreksi catatan retur sebelum mengoreksi reject.')
                line = next(l for l in po['lines'] if l['material_id']==intake['material_id'])
                if original['quantity_milli']>int(Decimal(line['receivable'])*1000):
                    raise DomainError(409,'Jatah pengganti sudah terisi. Koreksi penerimaan atau kedatangan pengganti sebelum mengembalikan reject ke hold.')
            else:
                receipt = db.execute("SELECT id FROM material_movements WHERE batch_id=? AND kind='receipt'",(original['batch_id'],)).fetchone()
                self._reverse_material(db,receipt['id'],payload,actor)
            db.execute('''INSERT INTO qc_decisions(id,intake_id,kind,quantity_milli,reversal_of,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?)''',(str(uuid4()),intake['id'],original['kind'],-original['quantity_milli'],decision_id,
                                          payload['reason'],actor['id'],now()))
            return self._quality_intake(db,intake['id'])
        return self._write(actor,('admin',),key,'qc-reverse:'+decision_id,payload,perform)

    def cancel_quality_intake(self, intake_id, payload, actor, key):
        def perform(db):
            intake = self._quality_intake(db,intake_id)
            if intake['po_closed']:
                raise DomainError(409,'PO sudah ditutup; kedatangan sudah final.')
            if intake['cancellation'] or intake['accepted']!='0.000' or intake['rejected']!='0.000':
                raise DomainError(409,'Kedatangan sudah dibatalkan atau masih memiliki keputusan QC aktif. Koreksi keputusan terlebih dahulu.')
            db.execute('INSERT INTO qc_intake_cancellations(intake_id,reason,actor_id,created_at) VALUES(?,?,?,?)',
                       (intake_id,payload['reason'],actor['id'],now()))
            return self._quality_intake(db,intake_id)
        return self._write(actor,('admin',),key,'qc-cancel:'+intake_id,payload,perform)

    def _bom(self, db, product_id, before=None):
        product = db.execute('SELECT id,sku,name FROM products WHERE id=?', (product_id,)).fetchone()
        if not product:
            raise DomainError(404, 'SKU tidak ditemukan.')
        row = db.execute('''SELECT b.*,u.name AS actor_name FROM bom_revisions b JOIN users u ON u.id=b.actor_id
            WHERE product_id=? AND (? IS NULL OR revision<?) ORDER BY revision DESC LIMIT 1''', (product_id,before,before)).fetchone()
        record = dict(row) if row else dict(revision=0, product_id=product_id, components='[]', reason='', actor_id=None, actor_name=None, created_at=None)
        record.update(sku=product['sku'], name=product['name'])
        record['components'] = [component | dict(db.execute('SELECT code,name,unit FROM materials WHERE id=?', (component['material_id'],)).fetchone())
                                for component in json.loads(record['components'])]
        return record

    def bom(self, product_id):
        with self.transaction() as db:
            return self._bom(db, product_id)

    def save_bom(self, product_id, payload, actor, key):
        def perform(db):
            current = self._bom(db, product_id)
            if current['revision'] != payload['expected_revision']:
                raise DomainError(409, 'BOM sudah berubah. Tutup form, muat ulang BOM, lalu periksa versi terbaru.')
            components = sorted(payload['components'], key=lambda c: c['material_id'])
            for component in components:
                material = db.execute('SELECT unit FROM materials WHERE id=?', (component['material_id'],)).fetchone()
                if not material:
                    raise DomainError(404, 'Bahan BOM tidak ditemukan.')
                self._material_amount(component['quantity'], material['unit'])
            old = [dict(material_id=c['material_id'], quantity=c['quantity']) for c in current['components']]
            if components == old:
                raise DomainError(409, 'BOM tidak berubah. Ubah bahan atau jumlah sebelum menyimpan.')
            db.execute('INSERT INTO bom_revisions(product_id,components,reason,actor_id,created_at) VALUES(?,?,?,?,?)',
                       (product_id,json.dumps(components),payload['reason'],actor['id'],now()))
            return self._bom(db, product_id)
        return self._write(actor, ('admin',), key, 'bom:'+product_id, payload, perform)

    def bom_history(self, product_id, limit=100, before=None):
        with self.transaction() as db:
            self._bom(db, product_id)
            revisions = db.execute('''SELECT revision FROM bom_revisions WHERE product_id=? AND (? IS NULL OR revision<?)
                ORDER BY revision DESC LIMIT ?''', (product_id,before,before,limit)).fetchall()
            return [self._bom(db, product_id, row[0]+1) for row in revisions]

    def material_requirements(self, order_id):
        with self.transaction() as db:
            order = self._order(db, order_id)
            required, issued, stock = {}, {}, {}
            sources, missing = [], []
            for line in order['lines']:
                bom = self._bom(db, line['product_id'])
                source = dict(product_id=line['product_id'], sku=line['sku'], target_quantity=line['quantity'], revision=bom['revision'])
                sources.append(source)
                if not bom['revision']:
                    missing.append(source)
                for c in bom['components']:
                    material_id = c['material_id']
                    required[material_id] = required.get(material_id,0) + self._material_amount(c['quantity'],c['unit']) * line['quantity']
            for row in db.execute('''SELECT b.material_id,x.quantity_milli FROM material_movements x
                JOIN material_batches b ON b.id=x.batch_id WHERE x.order_id=?''', (order_id,)):
                issued[row['material_id']] = issued.get(row['material_id'],0) - row['quantity_milli']
            reserved, own = {}, {}
            for row in db.execute('''SELECT b.material_id,e.quantity_milli,e.order_id FROM material_reservation_events e
                JOIN material_batches b ON b.id=e.batch_id'''):
                material_id=row['material_id']
                reserved[material_id]=reserved.get(material_id,0)+row['quantity_milli']
                if row['order_id']==order_id:
                    own[material_id]=own.get(material_id,0)+row['quantity_milli']
            ids = set(required) | {key for key,value in issued.items() if value} | {key for key,value in own.items() if value}
            # Sum in Python: a multi-SKU requirement can exceed SQLite's signed 64-bit integer.
            for row in db.execute('''SELECT b.material_id,x.quantity_milli FROM material_movements x
                JOIN material_batches b ON b.id=x.batch_id'''):
                if row['material_id'] in ids:
                    stock[row['material_id']] = stock.get(row['material_id'],0) + row['quantity_milli']
            rows = []
            for material_id in ids:
                material = dict(db.execute('SELECT code,name,unit FROM materials WHERE id=?', (material_id,)).fetchone())
                need, out, available = required.get(material_id,0), issued.get(material_id,0), stock.get(material_id,0)
                remaining = max(need-out,0)
                reserved_own=own.get(material_id,0)
                reserved_other=reserved.get(material_id,0)-reserved_own
                free=available-reserved.get(material_id,0)
                amounts = dict(required=need,issued=out,remaining=remaining,stock=available,reserved_own=reserved_own,
                    reserved_other=reserved_other,available=free,available_to_order=free+reserved_own,shortage=max(remaining-free-reserved_own,0))
                rows.append(dict(material_id=material_id, **material, outside_bom=material_id not in required,
                                 **{key:self._material_decimal(value) for key,value in amounts.items()}))
            return dict(order_id=order_id, reference=order['reference'], basis='latest_bom', complete=not missing,
                        sources=sources, missing_bom=missing, materials=sorted(rows,key=lambda r:(r['code'],r['material_id'])))

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
            if db.execute('SELECT 1 FROM cutting_runs r,json_each(r.movement_ids) x WHERE x.value=?',(movement_id,)).fetchone():
                raise DomainError(409,'Perpindahan berasal dari hasil cutting. Gunakan koreksi hasil cutting agar bahan ikut dikoreksi.')
            if db.execute('''SELECT 1 FROM sewing_job_results
                WHERE completion_movement_id=? OR reject_movement_id=?''',(movement_id,movement_id)).fetchone():
                raise DomainError(409,'Perpindahan berasal dari job sewing. Gunakan koreksi job sewing agar hasil ikut dikoreksi.')
            if db.execute('SELECT 1 FROM finishing_records WHERE movement_id=?',(movement_id,)).fetchone():
                raise DomainError(409,'Perpindahan berasal dari finishing. Gunakan koreksi finishing agar checklist ikut dikoreksi.')
            if db.execute('''SELECT 1 FROM final_qc_records WHERE accepted_movement_id=?
                OR rework_movement_id=? OR reject_movement_id=?''',(movement_id,movement_id,movement_id)).fetchone():
                raise DomainError(409,'Perpindahan berasal dari final QC. Gunakan koreksi final QC agar hasil ikut dikoreksi.')
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
            return [dict(row) for row in db.execute("""SELECT m.*,u.name AS actor_name,p.sku,
                (SELECT r.id FROM cutting_runs r,json_each(r.movement_ids) x WHERE x.value=m.id) AS cutting_run_id,
                (SELECT j.job_id FROM sewing_job_results j WHERE j.completion_movement_id=m.id OR j.reject_movement_id=m.id) AS sewing_job_id,
                (SELECT f.id FROM finishing_records f WHERE f.movement_id=m.id) AS finishing_record_id,
                (SELECT q.id FROM final_qc_records q WHERE q.accepted_movement_id=m.id
                    OR q.rework_movement_id=m.id OR q.reject_movement_id=m.id) AS final_qc_record_id
                FROM movements m
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
