import hashlib
import json
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
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
            if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8):
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
        balance = record.pop('balance_milli')
        reserved = db.execute('SELECT COALESCE(SUM(quantity_milli),0) FROM material_reservation_events WHERE batch_id=?', (batch_id,)).fetchone()[0]
        own = db.execute('SELECT COALESCE(SUM(quantity_milli),0) FROM material_reservation_events WHERE batch_id=? AND order_id=?', (batch_id,order_id)).fetchone()[0]
        record.update({key:self._material_decimal(value) for key,value in dict(balance=balance,reserved=reserved,
                      available=balance-reserved,reserved_for_order=own,available_to_order=balance-reserved+own).items()})
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
        def perform(db):
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
        return self._write(actor, ('admin','operator'), key, 'material-receipt', payload, perform)

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
            original = db.execute('SELECT * FROM material_movements WHERE id=?', (movement_id,)).fetchone()
            if not original:
                raise DomainError(404, 'Catatan bahan tidak ditemukan.')
            if original['kind'] == 'reversal' or db.execute('SELECT 1 FROM material_movements WHERE reversal_of=?', (movement_id,)).fetchone():
                raise DomainError(409, 'Catatan pembalik atau catatan yang sudah dibalik tidak dapat dikoreksi lagi.')
            balance = db.execute('SELECT SUM(quantity_milli) FROM material_movements WHERE batch_id=?', (original['batch_id'],)).fetchone()[0]
            if balance - original['quantity_milli'] < 0:
                raise DomainError(409, 'Bahan sudah dikeluarkan. Periksa dan kembalikan pengeluaran terkait sebelum membalik penerimaan.')
            if original['kind']=='receipt' and db.execute('SELECT COALESCE(SUM(quantity_milli),0) FROM material_reservation_events WHERE batch_id=?', (original['batch_id'],)).fetchone()[0]:
                raise DomainError(409, 'Batch masih direservasi. Lepaskan seluruh reservasi sebelum membalik penerimaan.')
            if original['kind']=='issue' and db.execute('SELECT COALESCE(SUM(used_milli+waste_milli),0) FROM material_consumption WHERE issue_id=?',(movement_id,)).fetchone()[0]:
                raise DomainError(409,'Pengeluaran sudah dicatat terpakai atau waste. Periksa dan koreksi catatan pemakaian sebelum mengembalikan seluruh pengeluaran.')
            return self._material_movement(db, original['batch_id'], 'reversal', -original['quantity_milli'],
                original['order_id'], payload['reason'], actor['id'], movement_id)
        return self._write(actor, ('admin',), key, 'material-reverse:'+movement_id, payload, perform)

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
        def perform(db):
            issue=self._issue_consumption(db,payload['issue_id'])
            if issue['reversed_by']:
                raise DomainError(409,'Pengeluaran sudah dibalik, tidak dapat dicatat pemakaiannya.')
            amounts=[0 if Decimal(payload[field])==0 else self._material_amount(payload[field],issue['unit']) for field in ('used','waste')]
            if sum(amounts)==0:
                raise DomainError(422,'Isi jumlah terpakai atau waste lebih dari nol.')
            if sum(amounts)>Decimal(issue['unreported'])*1000:
                raise DomainError(409,'Terpakai + waste melebihi jumlah yang belum dilaporkan. Muat ulang dan periksa catatan terbaru.')
            return self._consumption_event(db,issue['issue_id'],*amounts,payload['reason'],actor['id'])
        return self._write(actor,('admin','operator'),key,'material-consumption',payload,perform)

    def reverse_consumption(self, consumption_id, payload, actor, key):
        def perform(db):
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
                (SELECT id FROM material_consumption WHERE reversal_of=c.id) AS reversed_by
                FROM material_consumption c JOIN material_movements m ON m.id=c.issue_id
                JOIN material_batches b ON b.id=m.batch_id JOIN materials s ON s.id=b.material_id JOIN users u ON u.id=c.actor_id
                WHERE m.order_id=? AND (? IS NULL OR c.sequence<?) ORDER BY c.sequence DESC LIMIT ?''',(order_id,before,before,limit)).fetchall()
            result=[]
            for row in rows:
                record=dict(row);record['used']=self._material_decimal(record.pop('used_milli'));record['waste']=self._material_decimal(record.pop('waste_milli'));result.append(record)
            return result

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
            db.execute('''INSERT INTO purchase_request_events(request_id,status,reason,actor_id,created_at)
                VALUES(?,?,?,?,?)''', (request_id,payload['status'],payload['reason'],actor['id'],now()))
            return self._purchase_request(db, request_id)
        return self._write(actor, ('admin','operator'), key, 'purchase-request-decision:'+request_id, payload, perform)

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
