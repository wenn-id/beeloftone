import hashlib
import json
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

from beeloft.models import STAGES, TRANSITIONS, UserCreate

ACTIVITY_SQL = Path(__file__).with_name("activity.sql").read_text(encoding="utf-8")
INTEGRATION_CONTRACTS = (
    {'system':'jubelio','label':'Jubelio','scopes':(
        {'scope':'orders','domain':'Marketplace orders','source_of_truth':'Jubelio'},
        {'scope':'finished_goods','domain':'Finished goods stock / fulfillment','source_of_truth':'Jubelio / WMS'},
        {'scope':'returns','domain':'Marketplace returns','source_of_truth':'Jubelio'},
        {'scope':'listings','domain':'Marketplace listings','source_of_truth':'Jubelio'})},
    {'system':'mekari','label':'Mekari','scopes':(
        {'scope':'finance_summary','domain':'Management finance summary','source_of_truth':'Mekari Accounting'},
        {'scope':'payables','domain':'Payables','source_of_truth':'Mekari Accounting'},
        {'scope':'receivables','domain':'Receivables','source_of_truth':'Mekari Accounting'},
        {'scope':'payroll','domain':'Payroll records','source_of_truth':'Mekari HR / Payroll'})},
)


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
            if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35):
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
            if version < 25:
                adjustment_columns={row['name'] for row in db.execute('PRAGMA table_info(finished_goods_adjustments)')}
                if 'stock_count_id' not in adjustment_columns:
                    db.execute('''ALTER TABLE finished_goods_adjustments ADD COLUMN stock_count_id TEXT
                        REFERENCES finished_goods_stock_counts(id)''')
                db.executescript(Path(__file__).with_name("inventory_reconciliation.sql").read_text(encoding="utf-8"))
            if version < 26:
                db.executescript(Path(__file__).with_name("unified_approvals.sql").read_text(encoding="utf-8"))
            if version < 27:
                db.executescript(Path(__file__).with_name("purchase_order_approvals.sql").read_text(encoding="utf-8"))
            if version < 28:
                db.executescript(Path(__file__).with_name("supplier_payment_approvals.sql").read_text(encoding="utf-8"))
            if version < 29:
                db.executescript(Path(__file__).with_name("marketing_budget_approvals.sql").read_text(encoding="utf-8"))
            if version < 30:
                db.executescript(Path(__file__).with_name("marketplace_sale_settlements.sql").read_text(encoding="utf-8"))
            if version < 31:
                db.executescript(Path(__file__).with_name("ai_action_proposals.sql").read_text(encoding="utf-8"))
            if version < 32:
                db.executescript(Path(__file__).with_name("ai_investigations.sql").read_text(encoding="utf-8"))
            if version < 33:
                db.executescript(Path(__file__).with_name("integration_sync.sql").read_text(encoding="utf-8"))
            if version < 34:
                db.executescript(Path(__file__).with_name("product_external_mappings.sql").read_text(encoding="utf-8"))
            if version < 35:
                db.executescript(Path(__file__).with_name("jubelio_stock_snapshots.sql").read_text(encoding="utf-8"))

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

    def _integration_sync_run(self, db, run_id):
        row=db.execute('''SELECT r.*,u.name AS actor_name FROM integration_sync_runs r
            JOIN users u ON u.id=r.actor_id WHERE r.id=?''',(run_id,)).fetchone()
        if not row:
            raise DomainError(404,'Catatan sinkronisasi tidak ditemukan.')
        return dict(row)

    def create_integration_sync_run(self, payload, actor, key):
        def perform(db):
            run_id=str(uuid4())
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,
                finished_at,records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,payload['system'],payload['scope'],
                payload['status'],payload['started_at'],payload['finished_at'],payload['records_read'],
                payload['records_written'],payload['external_cursor'],payload['error'],payload['reason'],
                actor['id'],now()))
            return self._integration_sync_run(db,run_id)
        return self._write(actor,('admin',),key,'integration-sync-run',payload,perform)

    def integration_sync_run(self, run_id):
        with self.transaction() as db:
            return self._integration_sync_run(db,run_id)

    def integration_sync_runs(self, limit=100, before=None, system='all', scope='', status='all'):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM integration_sync_runs WHERE (? IS NULL OR sequence<?)
                AND (?='all' OR system=?) AND (?='' OR scope=?) AND (?='all' OR status=?)
                ORDER BY sequence DESC LIMIT ?''',(before,before,system,system,scope,scope,
                status,status,limit)).fetchall()
            return [self._integration_sync_run(db,row['id']) for row in rows]

    def integrations(self, stale_after_minutes=1440):
        generated=datetime.now(timezone.utc)
        systems=[]
        with self.transaction() as db:
            for contract in INTEGRATION_CONTRACTS:
                scopes=[]
                for definition in contract['scopes']:
                    row=db.execute('''SELECT id FROM integration_sync_runs WHERE system=? AND scope=?
                        ORDER BY sequence DESC LIMIT 1''',(contract['system'],definition['scope'])).fetchone()
                    latest=self._integration_sync_run(db,row['id']) if row else None
                    age=None
                    if latest:
                        finished=datetime.fromisoformat(latest['finished_at'].replace('Z','+00:00'))
                        age=max(0,int((generated-finished).total_seconds()//60))
                    health='never_synced' if latest is None else ('failed' if latest['status']=='failed'
                        else 'stale' if age>stale_after_minutes else 'healthy')
                    scopes.append(definition|{'direction':'inbound','mode':'read_only','health':health,
                        'age_minutes':age,'latest_run':latest})
                healths={item['health'] for item in scopes}
                overall='failed' if 'failed' in healths else ('never_synced' if healths=={'never_synced'}
                    else 'incomplete' if 'never_synced' in healths else 'stale' if 'stale' in healths
                    else 'healthy')
                system={'system':contract['system'],'label':contract['label'],'health':overall,
                    'scopes':scopes,'attention_count':sum(item['health']!='healthy' for item in scopes)}
                if contract['system']=='jubelio':
                    total=db.execute('SELECT COUNT(*) FROM products').fetchone()[0]
                    mapped=db.execute('''SELECT COUNT(*) FROM product_external_mapping_events e
                        WHERE e.system='jubelio' AND e.status='mapped' AND e.sequence=(
                            SELECT MAX(x.sequence) FROM product_external_mapping_events x
                            WHERE x.product_id=e.product_id AND x.system=e.system)''').fetchone()[0]
                    system['product_mapping']={'total_products':total,'mapped_products':mapped,
                                               'unmapped_products':total-mapped}
                systems.append(system)
        return {'generated_at':generated.isoformat(),'stale_after_minutes':stale_after_minutes,
                'systems':systems}

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

    def _product_external_mapping(self, db, product_id, system):
        product=db.execute('SELECT id,sku,name,color,size FROM products WHERE id=?',(product_id,)).fetchone()
        if not product:
            raise DomainError(404,'SKU tidak ditemukan.')
        row=db.execute('''SELECT e.*,u.name AS actor_name FROM product_external_mapping_events e
            JOIN users u ON u.id=e.actor_id WHERE e.product_id=? AND e.system=?
            ORDER BY e.sequence DESC LIMIT 1''',(product_id,system)).fetchone()
        base={'product_id':product['id'],'sku':product['sku'],'product_name':product['name'],
              'color':product['color'],'size':product['size'],'system':system}
        if not row:
            return base|{'id':None,'sequence':None,'revision':0,'status':'unmapped',
                         'external_id':'','external_sku':'','reason':'','actor_id':None,
                         'actor_name':None,'created_at':None}
        return base|dict(row)

    def product_external_mapping(self, product_id, system):
        with self.transaction() as db:
            return self._product_external_mapping(db,product_id,system)

    def product_external_mappings(self, system, status='all', limit=100, offset=0):
        with self.transaction() as db:
            ids=db.execute('''WITH latest AS (
                    SELECT product_id,MAX(sequence) AS sequence FROM product_external_mapping_events
                    WHERE system=? GROUP BY product_id
                ) SELECT p.id FROM products p LEFT JOIN latest l ON l.product_id=p.id
                LEFT JOIN product_external_mapping_events e ON e.sequence=l.sequence
                WHERE (?='all' OR COALESCE(e.status,'unmapped')=?)
                ORDER BY p.sku,p.id LIMIT ? OFFSET ?''',(system,status,status,limit,offset)).fetchall()
            return [self._product_external_mapping(db,row['id'],system) for row in ids]

    def save_product_external_mapping(self, product_id, system, payload, actor, key):
        def perform(db):
            current=self._product_external_mapping(db,product_id,system)
            if payload['expected_revision']!=current['revision']:
                raise DomainError(409,'Mapping SKU sudah berubah. Muat ulang lalu coba lagi.')
            if payload['action']=='unmapped':
                if current['status']!='mapped':
                    raise DomainError(409,'SKU belum memiliki mapping aktif.')
            else:
                if (current['status']=='mapped' and current['external_id']==payload['external_id']
                        and current['external_sku'].casefold()==payload['external_sku'].casefold()):
                    raise DomainError(409,'Mapping baru sama dengan mapping aktif.')
                duplicate=db.execute('''SELECT p.sku FROM product_external_mapping_events e
                    JOIN products p ON p.id=e.product_id WHERE e.system=? AND e.status='mapped'
                    AND e.product_id!=? AND e.sequence=(SELECT MAX(x.sequence)
                        FROM product_external_mapping_events x WHERE x.product_id=e.product_id
                        AND x.system=e.system)
                    AND (e.external_id=? OR e.external_sku=? COLLATE NOCASE) LIMIT 1''',
                    (system,product_id,payload['external_id'],payload['external_sku'])).fetchone()
                if duplicate:
                    raise DomainError(409,'ID atau SKU eksternal sudah dipakai oleh '+duplicate['sku']+'.')
            record={'id':str(uuid4()),'product_id':product_id,'system':system,
                    'revision':current['revision']+1,'status':payload['action'],
                    'external_id':payload['external_id'],'external_sku':payload['external_sku'],
                    'reason':payload['reason'],'actor_id':actor['id'],'created_at':now()}
            db.execute('''INSERT INTO product_external_mapping_events
                (id,product_id,system,revision,status,external_id,external_sku,reason,actor_id,created_at)
                VALUES(:id,:product_id,:system,:revision,:status,:external_id,:external_sku,:reason,:actor_id,:created_at)''',record)
            return self._product_external_mapping(db,product_id,system)
        operation='product-external-mapping:'+product_id+':'+system
        return self._write(actor,('admin',),key,operation,payload,perform)

    def product_external_mapping_history(self, product_id, system, limit=100, before=None):
        with self.transaction() as db:
            self._product_external_mapping(db,product_id,system)
            rows=db.execute('''SELECT e.*,u.name AS actor_name,p.sku,p.name AS product_name,
                p.color,p.size FROM product_external_mapping_events e JOIN users u ON u.id=e.actor_id
                JOIN products p ON p.id=e.product_id WHERE e.product_id=? AND e.system=?
                AND (? IS NULL OR e.sequence<?) ORDER BY e.sequence DESC LIMIT ?''',
                (product_id,system,before,before,limit)).fetchall()
            return [dict(row) for row in rows]

    def _jubelio_stock_snapshot(self, db, batch_id):
        row=db.execute('''SELECT b.*,r.status AS sync_status,r.records_read,r.records_written,
            r.external_cursor,r.error,r.reason,u.name AS actor_name FROM jubelio_stock_snapshot_batches b
            JOIN integration_sync_runs r ON r.id=b.sync_run_id JOIN users u ON u.id=b.actor_id
            WHERE b.id=?''',(batch_id,)).fetchone()
        if not row:
            raise DomainError(404,'Snapshot stok Jubelio tidak ditemukan.')
        record=dict(row)
        record['items']=[dict(item) for item in db.execute('''SELECT i.*,p.sku,p.name AS product_name,
            p.color,p.size FROM jubelio_stock_snapshot_items i JOIN products p ON p.id=i.product_id
            WHERE i.batch_id=? ORDER BY p.sku,p.id''',(batch_id,))]
        record['quarantine']=[dict(item) for item in db.execute('''SELECT * FROM jubelio_stock_quarantine_items
            WHERE batch_id=? ORDER BY external_sku COLLATE NOCASE,external_id''',(batch_id,))]
        record['accepted_count']=len(record['items']);record['rejected_count']=len(record['quarantine'])
        return record

    def import_jubelio_stock_snapshot(self, payload, actor, key):
        def perform(db):
            accepted=[];rejected=[]
            for item in payload['items']:
                matches=db.execute('''SELECT e.product_id,e.external_id,e.external_sku FROM product_external_mapping_events e
                    WHERE e.system='jubelio' AND e.status='mapped' AND e.sequence=(SELECT MAX(x.sequence)
                        FROM product_external_mapping_events x WHERE x.product_id=e.product_id AND x.system=e.system)
                    AND (e.external_id=? OR e.external_sku=? COLLATE NOCASE)''',
                    (item['external_id'],item['external_sku'])).fetchall()
                exact=[row for row in matches if row['external_id']==item['external_id']
                       and row['external_sku'].casefold()==item['external_sku'].casefold()]
                if len(exact)==1:
                    accepted.append((item,exact[0]['product_id']))
                else:
                    issue='unmapped' if not matches else 'mapping_mismatch'
                    detail=('Belum ada mapping aktif untuk identifier Jubelio ini.' if issue=='unmapped'
                            else 'ID dan SKU eksternal tidak menunjuk ke mapping produk yang sama.')
                    rejected.append((item,issue,detail))
            run_id=str(uuid4());failed=len(rejected)>0
            error=f'{len(rejected)} record stok Jubelio dikarantina.' if failed else ''
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,finished_at,
                records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,'jubelio','finished_goods','failed' if failed else 'succeeded',
                payload['started_at'],payload['finished_at'],len(payload['items']),len(accepted),
                payload['external_cursor'],error,payload['reason'],actor['id'],now()))
            batch_id=str(uuid4());created=now()
            db.execute('''INSERT INTO jubelio_stock_snapshot_batches
                (id,sync_run_id,snapshot_at,actor_id,created_at) VALUES(?,?,?,?,?)''',
                (batch_id,run_id,payload['snapshot_at'],actor['id'],created))
            for item,product_id in accepted:
                db.execute('''INSERT INTO jubelio_stock_snapshot_items
                    (id,batch_id,product_id,external_id,external_sku,sellable_quantity,reserved_quantity)
                    VALUES(?,?,?,?,?,?,?)''',(str(uuid4()),batch_id,product_id,item['external_id'],
                    item['external_sku'],item['sellable_quantity'],item['reserved_quantity']))
            for item,issue,detail in rejected:
                db.execute('''INSERT INTO jubelio_stock_quarantine_items
                    (id,batch_id,external_id,external_sku,sellable_quantity,reserved_quantity,issue,detail)
                    VALUES(?,?,?,?,?,?,?,?)''',(str(uuid4()),batch_id,item['external_id'],item['external_sku'],
                    item['sellable_quantity'],item['reserved_quantity'],issue,detail))
            return self._jubelio_stock_snapshot(db,batch_id)
        return self._write(actor,('admin',),key,'jubelio-stock-snapshot',payload,perform)

    def jubelio_stock_snapshot(self, batch_id):
        with self.transaction() as db:
            return self._jubelio_stock_snapshot(db,batch_id)

    def jubelio_stock_snapshots(self, limit=100, before=None):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM jubelio_stock_snapshot_batches
                WHERE (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',
                (before,before,limit)).fetchall()
            return [self._jubelio_stock_snapshot(db,row['id']) for row in rows]

    def jubelio_stock_reconciliation(self):
        internal={row['product_id']:row for row in self.finished_goods_inventory(1_000_000_000,0)}
        with self.transaction() as db:
            latest=db.execute('SELECT id FROM jubelio_stock_snapshot_batches ORDER BY sequence DESC LIMIT 1').fetchone()
            if not latest:
                return {'snapshot':None,'summary':{'mapped_products':0,'matched':0,'mismatched':0,
                    'missing_from_snapshot':0,'quarantined':0},'items':[],'quarantine':[]}
            snapshot=self._jubelio_stock_snapshot(db,latest['id'])
            snap={row['product_id']:row for row in snapshot['items']}
            mappings=db.execute('''SELECT e.product_id,p.sku,p.name AS product_name,p.color,p.size
                FROM product_external_mapping_events e JOIN products p ON p.id=e.product_id
                WHERE e.system='jubelio' AND e.status='mapped' AND e.sequence=(SELECT MAX(x.sequence)
                    FROM product_external_mapping_events x WHERE x.product_id=e.product_id AND x.system=e.system)
                ORDER BY p.sku,p.id''').fetchall()
            items=[]
            for mapping in mappings:
                external=snap.get(mapping['product_id']);core=internal.get(mapping['product_id'],{})
                beeloft=core.get('available_quantity',0)
                if external:
                    jubelio=external['sellable_quantity']-external['reserved_quantity']
                    variance=jubelio-beeloft;status='matched' if variance==0 else 'mismatched'
                else:
                    jubelio=None;variance=None;status='missing_from_snapshot'
                items.append(dict(mapping)|{'beeloft_available_quantity':beeloft,
                    'jubelio_available_quantity':jubelio,'variance_quantity':variance,'status':status})
            summary={'mapped_products':len(items),'matched':sum(x['status']=='matched' for x in items),
                'mismatched':sum(x['status']=='mismatched' for x in items),
                'missing_from_snapshot':sum(x['status']=='missing_from_snapshot' for x in items),
                'quarantined':len(snapshot['quarantine'])}
            return {'snapshot':{key:snapshot[key] for key in ('id','sequence','snapshot_at','sync_run_id','sync_status',
                'records_read','records_written','error','created_at')},'summary':summary,
                'items':items,'quarantine':snapshot['quarantine']}

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
        record['active_adjustment_count']=db.execute('''SELECT COUNT(*) FROM finished_goods_adjustments a
            WHERE a.receipt_id=? AND NOT EXISTS(
              SELECT 1 FROM finished_goods_adjustment_reversals r WHERE r.adjustment_id=a.id)''',(receipt_id,)).fetchone()[0]
        record['active_stock_count_count']=db.execute('''SELECT COUNT(*) FROM finished_goods_stock_counts c
            WHERE c.receipt_id=? AND NOT EXISTS(
              SELECT 1 FROM finished_goods_stock_count_reversals r WHERE r.count_id=c.id)''',(receipt_id,)).fetchone()[0]
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
            if receipt['active_adjustment_count']:
                raise DomainError(409,'Koreksi semua adjustment aktif sebelum mengoreksi penerimaan barang jadi.')
            if receipt['active_stock_count_count']:
                raise DomainError(409,'Koreksi semua stock opname aktif sebelum mengoreksi penerimaan barang jadi.')
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
        settlement=db.execute('''SELECT e.id,e.reference FROM marketplace_sale_settlements e
            WHERE e.shipment_id=? AND NOT EXISTS(
              SELECT 1 FROM marketplace_sale_settlement_reversals r WHERE r.settlement_id=e.id)
            ORDER BY e.sequence DESC LIMIT 1''',(shipment_id,)).fetchone()
        record['sale_settlement_id']=settlement['id'] if settlement else None
        record['sale_settlement_reference']=settlement['reference'] if settlement else None
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
            if shipment['sale_settlement_id']:
                raise DomainError(409,'Koreksi settlement penjualan aktif sebelum mengoreksi pengiriman.')
            db.execute('''INSERT INTO marketplace_shipment_reversals(shipment_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(shipment_id,payload['reason'],actor['id'],now()))
            return self._marketplace_shipment(db,shipment_id)
        return self._write(actor,('admin',),key,'marketplace-shipment-reverse:'+shipment_id,payload,perform)

    def _marketplace_sale_settlement(self, db, settlement_id):
        row=db.execute('''SELECT e.*,u.name AS actor_name FROM marketplace_sale_settlements e
            JOIN users u ON u.id=e.actor_id WHERE e.id=?''',(settlement_id,)).fetchone()
        if not row:
            raise DomainError(404,'Settlement penjualan tidak ditemukan.')
        record=dict(row)
        source=self._marketplace_shipment(db,record['shipment_id'])
        for field in ('reference','order_id','order_reference','product_id','sku','product_name','color','size',
                      'marketplace','external_order_reference','quantity','returned_quantity','carrier',
                      'tracking_number','shipped_date','receipt_id','receipt_reference'):
            record['shipment_reference' if field=='reference' else field]=source[field]
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM marketplace_sale_settlement_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.settlement_id=?''',(settlement_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        record['return_coverage_status']='current' if record['return_quantity']==source['returned_quantity'] else 'stale'
        gross=record['gross_revenue_minor']
        deductions=record['seller_discount_minor']+record['customer_refund_minor']
        selling=record['marketplace_fee_minor']+record['shipping_cost_minor']+record['other_variable_cost_minor']
        record['net_revenue_minor']=gross-deductions
        record['variable_selling_cost_minor']=selling
        record['contribution_before_production_minor']=gross-deductions-selling
        for field in ('gross_revenue','seller_discount','customer_refund','marketplace_fee','shipping_cost',
                      'other_variable_cost','net_revenue','variable_selling_cost','contribution_before_production'):
            record[field]=format(Decimal(record.pop(field+'_minor'))/100,'.2f')
        return record

    def marketplace_sale_settlement(self, settlement_id):
        with self.transaction() as db:
            return self._marketplace_sale_settlement(db,settlement_id)

    def marketplace_sale_settlements(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT e.id FROM marketplace_sale_settlements e
                JOIN marketplace_shipments s ON s.id=e.shipment_id JOIN marketplace_packs k ON k.id=s.pack_id
                JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND (? IS NULL OR e.sequence<?) ORDER BY e.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._marketplace_sale_settlement(db,row['id']) for row in ids]

    def create_marketplace_sale_settlement(self, shipment_id, payload, actor, key):
        def perform(db):
            shipment=self._marketplace_shipment(db,shipment_id)
            if shipment['status']!='shipped':
                raise DomainError(409,'Pengiriman harus aktif sebelum settlement penjualan dicatat.')
            if shipment['sale_settlement_id']:
                raise DomainError(409,'Pengiriman sudah memiliki settlement penjualan aktif.')
            if payload['settled_date']<shipment['shipped_date']:
                raise DomainError(422,'Tanggal settlement tidak boleh sebelum tanggal kirim.')
            settlement_id=str(uuid4())
            money=lambda name:int(Decimal(payload[name])*100)
            db.execute('''INSERT INTO marketplace_sale_settlements(id,reference,shipment_id,return_quantity,
                gross_revenue_minor,seller_discount_minor,customer_refund_minor,marketplace_fee_minor,
                shipping_cost_minor,other_variable_cost_minor,settled_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(settlement_id,payload['reference'],shipment_id,
                shipment['returned_quantity'],money('gross_revenue'),money('seller_discount'),
                money('customer_refund'),money('marketplace_fee'),money('shipping_cost'),
                money('other_variable_cost'),payload['settled_date'],payload['reason'],actor['id'],now()))
            return self._marketplace_sale_settlement(db,settlement_id)
        return self._write(actor,('admin','operator'),key,'marketplace-sale-settlement:'+shipment_id,payload,perform)

    def reverse_marketplace_sale_settlement(self, settlement_id, payload, actor, key):
        def perform(db):
            record=self._marketplace_sale_settlement(db,settlement_id)
            if record['reversal']:
                raise DomainError(409,'Settlement penjualan sudah dikoreksi.')
            db.execute('''INSERT INTO marketplace_sale_settlement_reversals(settlement_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(settlement_id,payload['reason'],actor['id'],now()))
            return self._marketplace_sale_settlement(db,settlement_id)
        return self._write(actor,('admin',),key,'marketplace-sale-settlement-reverse:'+settlement_id,payload,perform)

    def contribution_margin(self, order_id):
        production=self.production_cost(order_id)
        with self.transaction() as db:
            order=self._order(db,order_id)
            ids=db.execute('''SELECT s.id FROM marketplace_shipments s
                JOIN marketplace_packs k ON k.id=s.pack_id JOIN marketplace_picks p ON p.id=k.pick_id
                JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id WHERE c.order_id=?
                AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
                ORDER BY s.sequence''',(order_id,)).fetchall()
            shipments=[]
            totals={name:0 for name in ('gross_revenue_minor','seller_discount_minor','customer_refund_minor',
                'marketplace_fee_minor','shipping_cost_minor','other_variable_cost_minor')}
            gaps=[]
            sold_quantity=0
            for item in ids:
                shipment=self._marketplace_shipment(db,item['id'])
                sold_quantity+=shipment['quantity']-shipment['returned_quantity']
                settlement=None
                if shipment['sale_settlement_id']:
                    settlement=self._marketplace_sale_settlement(db,shipment['sale_settlement_id'])
                    for name in totals:
                        totals[name]+=int(Decimal(settlement[name.removesuffix('_minor')])*100)
                    if settlement['return_coverage_status']=='stale':
                        gaps.append({'kind':'stale_return_coverage','shipment_id':shipment['id'],
                            'shipment_reference':shipment['reference'],'recorded_return_quantity':settlement['return_quantity'],
                            'current_return_quantity':shipment['returned_quantity']})
                else:
                    gaps.append({'kind':'missing_sales_settlement','shipment_id':shipment['id'],
                        'shipment_reference':shipment['reference'],'quantity':shipment['quantity']})
                shipments.append({'id':shipment['id'],'reference':shipment['reference'],'quantity':shipment['quantity'],
                    'returned_quantity':shipment['returned_quantity'],'net_sold_quantity':shipment['quantity']-shipment['returned_quantity'],
                    'marketplace':shipment['marketplace'],'external_order_reference':shipment['external_order_reference'],
                    'settlement':settlement})
            if not shipments:
                gaps.append({'kind':'no_sales_shipments'})
            if production['status']!='complete':
                gaps.append({'kind':'incomplete_production_cost','coverage_gaps':production['coverage_gaps']})
            if not production['finished_quantity']:
                gaps.append({'kind':'no_finished_quantity'})

            gross=totals['gross_revenue_minor']
            net_revenue=gross-totals['seller_discount_minor']-totals['customer_refund_minor']
            variable=totals['marketplace_fee_minor']+totals['shipping_cost_minor']+totals['other_variable_cost_minor']
            before_production=net_revenue-variable
            allocated=None
            if production['status']=='complete' and production['finished_quantity']:
                total_cost_minor=int(Decimal(production['total_cost'])*100)
                allocated=int((Decimal(total_cost_minor)*sold_quantity/production['finished_quantity']).quantize(
                    Decimal('1'),rounding=ROUND_HALF_UP))
            margin=before_production-allocated if allocated is not None and not gaps else None
            money=lambda value:format(Decimal(value)/100,'.2f')
            rate=(format((Decimal(margin)/net_revenue*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
                  if margin is not None and net_revenue>0 else None)
            return {'order_id':order['id'],'order_reference':order['reference'],'order_title':order['title'],
                'currency':'IDR','status':'complete' if not gaps else 'incomplete',
                'finished_quantity':production['finished_quantity'],'shipped_quantity':sum(x['quantity'] for x in shipments),
                'returned_quantity':sum(x['returned_quantity'] for x in shipments),'net_sold_quantity':sold_quantity,
                'gross_revenue':money(gross),'seller_discount':money(totals['seller_discount_minor']),
                'customer_refund':money(totals['customer_refund_minor']),'net_revenue':money(net_revenue),
                'marketplace_fee':money(totals['marketplace_fee_minor']),'shipping_cost':money(totals['shipping_cost_minor']),
                'other_variable_cost':money(totals['other_variable_cost_minor']),
                'variable_selling_cost':money(variable),'contribution_before_production':money(before_production),
                'allocated_production_cost':money(allocated) if allocated is not None else None,
                'contribution_margin':money(margin) if margin is not None else None,
                'contribution_margin_rate':rate,'production_cost':production,'shipments':shipments,
                'coverage_gaps':gaps,'scope':['sales_settlements','active_shipments','active_returns','production_cost_allocation'],
                'excluded_costs':['tax','payment_gateway_fee','advertising','fixed_overhead','return_handling','inventory_write_off']}

    def demand_forecast(self, as_of, window_days=28, horizon_days=30, query='', marketplace='',
                        limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        recent_start=as_of_date-timedelta(days=window_days-1)
        previous_end=recent_start-timedelta(days=1)
        previous_start=previous_end-timedelta(days=window_days-1)
        with self.transaction() as db:
            term=query.strip().casefold()
            products=[dict(row) for row in db.execute('''SELECT id,sku,name,color,size FROM products
                WHERE ?='' OR instr(lower(sku),?)>0 OR instr(lower(name),?)>0
                    OR instr(lower(color),?)>0 OR instr(lower(size),?)>0
                ORDER BY sku,id''',(term,term,term,term,term))]
            sales=db.execute('''SELECT product.id AS product_id,s.id AS shipment_id,s.shipped_date,
                s.quantity,m.marketplace,COALESCE((SELECT SUM(t.quantity) FROM marketplace_returns t
                  WHERE t.shipment_id=s.id AND t.returned_date<=? AND NOT EXISTS(
                    SELECT 1 FROM marketplace_return_reversals z WHERE z.return_id=t.id)),0) AS returned_quantity
                FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
                JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
                JOIN finished_goods_receipts x ON x.id=m.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN movements source ON source.id=b.output_movement_id JOIN order_lines l ON l.id=source.line_id
                JOIN products product ON product.id=l.product_id
                WHERE s.shipped_date BETWEEN ? AND ?
                  AND (?='' OR m.marketplace=? COLLATE NOCASE)
                  AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
                ORDER BY s.shipped_date,s.sequence''',(as_of_date.isoformat(),previous_start.isoformat(),
                as_of_date.isoformat(),marketplace.strip(),marketplace.strip())).fetchall()
        grouped={product['id']:{'product':product,'previous_shipped':0,'previous_returned':0,
            'recent_shipped':0,'recent_returned':0,'shipment_count':0,'marketplaces':set()}
            for product in products}
        for row in sales:
            item=grouped.get(row['product_id'])
            if not item:
                continue
            prefix='recent' if row['shipped_date']>=recent_start.isoformat() else 'previous'
            item[prefix+'_shipped']+=row['quantity']
            item[prefix+'_returned']+=row['returned_quantity']
            item['shipment_count']+=1
            item['marketplaces'].add(row['marketplace'])
        items=[]
        for item in grouped.values():
            previous=item['previous_shipped']-item['previous_returned']
            recent=item['recent_shipped']-item['recent_returned']
            previous_rate=Decimal(previous)/window_days
            recent_rate=Decimal(recent)/window_days
            forecast_rate=recent_rate*Decimal('.70')+previous_rate*Decimal('.30')
            forecast=(forecast_rate*horizon_days).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            historical_rate=(Decimal(previous+recent)/(window_days*2)).quantize(
                Decimal('.0001'),rounding=ROUND_HALF_UP)
            trend_percent=None
            if previous:
                trend_percent=format(((Decimal(recent-previous)/previous)*100).quantize(
                    Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
            trend='new' if not previous and recent else ('up' if recent>previous else 'down' if recent<previous else 'flat')
            product=item['product']
            items.append(product | {'history_status':'observed' if item['shipment_count'] else 'no_history',
                'shipment_count':item['shipment_count'],'marketplaces':sorted(item['marketplaces'],key=str.casefold),
                'previous_shipped_quantity':item['previous_shipped'],
                'previous_returned_quantity':item['previous_returned'],'previous_net_demand':previous,
                'recent_shipped_quantity':item['recent_shipped'],'recent_returned_quantity':item['recent_returned'],
                'recent_net_demand':recent,'historical_daily_rate':format(historical_rate,'.4f'),
                'forecast_daily_rate':format(forecast_rate.quantize(Decimal('.0001'),rounding=ROUND_HALF_UP),'.4f'),
                'forecast_quantity':format(forecast,'.2f'),'trend':trend,'trend_percent':trend_percent})
        items.sort(key=lambda row:(-Decimal(row['forecast_quantity']),row['sku'].casefold(),row['id']))
        total=len(items)
        page=items[offset:offset+limit]
        total_forecast=sum((Decimal(row['forecast_quantity']) for row in items),Decimal(0))
        return {'as_of':as_of_date.isoformat(),'window_days':window_days,'horizon_days':horizon_days,
            'history_start':previous_start.isoformat(),'previous_period_end':previous_end.isoformat(),
            'recent_period_start':recent_start.isoformat(),'marketplace':marketplace.strip() or None,
            'query':query.strip(),'method':'weighted_two_window_average','recent_weight':'0.70',
            'previous_weight':'0.30','total':total,'offset':offset,'limit':limit,
            'total_forecast_quantity':format(total_forecast.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f'),
            'items':page}

    def replenishment_recommendations(self, as_of, window_days=28, lead_time_days=14,
                                      review_period_days=30, safety_stock_days=7, batch_multiple=1,
                                      query='', marketplace='', limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        coverage_days=lead_time_days+review_period_days+safety_stock_days
        planning_horizon_end=as_of_date+timedelta(days=coverage_days)
        forecast=self.demand_forecast(as_of_date,window_days,coverage_days,query,marketplace,
                                      1_000_000_000,0)
        inventory={row['product_id']:row for row in self.finished_goods_inventory(1_000_000_000,0)}
        product_ids={row['id'] for row in forecast['items']}
        with self.transaction() as db:
            production_rows=[dict(row) for row in db.execute('''SELECT l.order_id,l.product_id,l.quantity,o.due_date,
                SUM(CASE WHEN b.stage NOT IN ('warehouse','reject') THEN b.quantity ELSE 0 END) AS pending
                FROM order_lines l JOIN balances b ON b.line_id=l.id JOIN orders o ON o.id=l.order_id
                GROUP BY l.id,l.order_id,l.product_id,l.quantity''')]
            relevant_orders={row['order_id'] for row in production_rows
                             if row['product_id'] in product_ids and row['pending']>0
                             and row['due_date']<=planning_horizon_end.isoformat()}
            inbound={}
            for row in production_rows:
                if (row['product_id'] in product_ids and row['pending']>0
                        and row['due_date']<=planning_horizon_end.isoformat()):
                    inbound[row['product_id']]=inbound.get(row['product_id'],0)+row['pending']

            products=[]
            for row in forecast['items']:
                stock=inventory.get(row['id'],{})
                available=stock.get('available_quantity',0)
                pipeline=inbound.get(row['id'],0)
                rate=Decimal(row['forecast_daily_rate'])
                if rate:
                    cover=Decimal(available)/rate
                    cover_days=format(cover.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
                    stockout=(as_of_date+timedelta(days=int(cover.to_integral_value(
                        rounding=ROUND_CEILING)))).isoformat()
                    reorder_point=int((rate*(lead_time_days+safety_stock_days)).to_integral_value(
                        rounding=ROUND_CEILING))
                    target=int((rate*coverage_days).to_integral_value(rounding=ROUND_CEILING))
                    shortfall=max(target-available-pipeline,0)
                    recommended=((shortfall+batch_multiple-1)//batch_multiple)*batch_multiple
                    if available<=0:
                        risk='out_of_stock'
                    elif cover<=lead_time_days:
                        risk='stockout_before_replenishment'
                    elif available<reorder_point:
                        risk='below_safety_stock'
                    else:
                        risk='covered'
                else:
                    cover_days=stockout=None;reorder_point=target=recommended=0
                    risk='insufficient_history' if row['history_status']=='no_history' else 'no_demand'
                products.append(row | {'sellable_quantity':stock.get('sellable_quantity',0),
                    'reserved_quantity':stock.get('reserved_quantity',0),'available_quantity':available,
                    'hold_quantity':stock.get('hold_quantity',0),'damaged_quantity':stock.get('damaged_quantity',0),
                    'inbound_production_quantity':pipeline,'inventory_position':available+pipeline,
                    'days_of_cover':cover_days,'projected_stockout_date':stockout,
                    'reorder_point_quantity':reorder_point,'target_stock_quantity':target,
                    'batch_multiple':batch_multiple,'recommended_production_quantity':recommended,
                    'stockout_risk':risk})

            bom_cache={}
            gaps={}
            def current_bom(product_id):
                if product_id not in bom_cache:
                    bom_cache[product_id]=self._bom(db,product_id)
                return bom_cache[product_id]
            existing_required={}
            required_by_order={}
            scoped_lines=[row for row in production_rows if row['order_id'] in relevant_orders]
            for line in scoped_lines:
                bom=current_bom(line['product_id'])
                if not bom['revision']:
                    gaps[('active_production',line['product_id'])]={'kind':'missing_bom',
                        'context':'active_production','product_id':line['product_id'],'sku':bom['sku']}
                    continue
                for component in bom['components']:
                    key=(line['order_id'],component['material_id'])
                    required_by_order[key]=required_by_order.get(key,0)+self._material_amount(
                        component['quantity'],component['unit'])*line['quantity']
            issued_by_order={}
            for row in db.execute('''SELECT m.order_id,b.material_id,m.quantity_milli FROM material_movements m
                JOIN material_batches b ON b.id=m.batch_id WHERE m.order_id IS NOT NULL'''):
                if row['order_id'] in relevant_orders:
                    key=(row['order_id'],row['material_id'])
                    issued_by_order[key]=issued_by_order.get(key,0)-row['quantity_milli']
            for key,required in required_by_order.items():
                material_id=key[1]
                remaining=max(required-issued_by_order.get(key,0),0)
                existing_required[material_id]=existing_required.get(material_id,0)+remaining

            recommended_required={}
            for product in products:
                quantity=product['recommended_production_quantity']
                if not quantity:
                    continue
                bom=current_bom(product['id'])
                if not bom['revision']:
                    gaps[('recommended_production',product['id'])]={'kind':'missing_bom',
                        'context':'recommended_production','product_id':product['id'],'sku':bom['sku']}
                    continue
                for component in bom['components']:
                    material_id=component['material_id']
                    recommended_required[material_id]=recommended_required.get(material_id,0)+self._material_amount(
                        component['quantity'],component['unit'])*quantity

            on_hand={}
            for row in db.execute('''SELECT b.material_id,m.quantity_milli FROM material_movements m
                JOIN material_batches b ON b.id=m.batch_id'''):
                on_hand[row['material_id']]=on_hand.get(row['material_id'],0)+row['quantity_milli']
            requested={};request_sources=[]
            for request_id, in db.execute('SELECT id FROM purchase_requests'):
                request=self._purchase_request(db,request_id)
                active_po=any(po['status'] not in ('cancelled','rejected') for po in request['purchase_orders'])
                if (request['status'] not in ('submitted','approved') or active_po
                        or request['required_date']>planning_horizon_end.isoformat()):
                    continue
                request_sources.append({line['material_id'] for line in request['lines']})
                for line in request['lines']:
                    requested[line['material_id']]=requested.get(line['material_id'],0)+self._material_amount(
                        line['quantity'],line['unit'])
            ordered={};order_sources=[]
            for order_id, in db.execute('SELECT id FROM purchase_orders'):
                purchase_order=self._purchase_order(db,order_id)
                if (purchase_order['status'] not in ('pending','issued')
                        or purchase_order['expected_date']>planning_horizon_end.isoformat()):
                    continue
                active_lines=[line for line in purchase_order['lines'] if Decimal(line['remaining'])>0]
                if active_lines:
                    order_sources.append({line['material_id'] for line in active_lines})
                for line in active_lines:
                    ordered[line['material_id']]=ordered.get(line['material_id'],0)+self._material_amount(
                        line['remaining'],line['unit'])

            material_ids=set(existing_required)|set(recommended_required)
            request_count=sum(bool(source&material_ids) for source in request_sources)
            order_count=sum(bool(source&material_ids) for source in order_sources)
            materials=[]
            for material_id in material_ids:
                material=dict(db.execute('SELECT code,name,unit FROM materials WHERE id=?',
                                         (material_id,)).fetchone())
                existing=existing_required.get(material_id,0)
                new=recommended_required.get(material_id,0)
                stock=on_hand.get(material_id,0)
                pr=requested.get(material_id,0)
                po=ordered.get(material_id,0)
                purchase=max(existing+new-stock-pr-po,0)
                materials.append({'material_id':material_id,**material,
                    'existing_production_requirement':self._material_decimal(existing),
                    'recommended_production_requirement':self._material_decimal(new),
                    'total_requirement':self._material_decimal(existing+new),
                    'on_hand_quantity':self._material_decimal(stock),
                    'open_purchase_request_quantity':self._material_decimal(pr),
                    'open_purchase_order_quantity':self._material_decimal(po),
                    'recommended_purchase_quantity':self._material_decimal(purchase),
                    'status':'purchase' if purchase else 'covered'})

        priority={'out_of_stock':0,'stockout_before_replenishment':1,'below_safety_stock':2,
                  'covered':3,'insufficient_history':4,'no_demand':5}
        products.sort(key=lambda row:(priority[row['stockout_risk']],
                      -row['recommended_production_quantity'],row['sku'].casefold(),row['id']))
        materials.sort(key=lambda row:(row['status']!='purchase',row['code'].casefold(),row['material_id']))
        total=len(products)
        page=products[offset:offset+limit]
        risks={name:sum(row['stockout_risk']==name for row in products) for name in priority}
        return {'as_of':as_of_date.isoformat(),'planning_horizon_end':planning_horizon_end.isoformat(),
            'window_days':window_days,
            'lead_time_days':lead_time_days,'review_period_days':review_period_days,
            'safety_stock_days':safety_stock_days,'coverage_days':coverage_days,
            'batch_multiple':batch_multiple,'query':query.strip(),'marketplace':marketplace.strip() or None,
            'method':'forecast_inventory_position','total':total,'offset':offset,'limit':limit,
            'summary':{'total_products':total,**risks,
                'recommended_production_quantity':sum(row['recommended_production_quantity'] for row in products),
                'materials_to_purchase':sum(row['status']=='purchase' for row in materials),
                'open_purchase_requests':request_count,'open_purchase_orders':order_count},
            'coverage_complete':not gaps,'coverage_gaps':sorted(gaps.values(),key=lambda row:(row['sku'],row['context'])),
            'product_recommendations':page,'material_purchase_recommendations':materials,
            'forecast':{'history_start':forecast['history_start'],
                'previous_period_end':forecast['previous_period_end'],
                'recent_period_start':forecast['recent_period_start'],
                'recent_weight':forecast['recent_weight'],'previous_weight':forecast['previous_weight']}}

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
            if record.get('stock_count_id'):
                raise DomainError(409,'Adjustment ini berasal dari stock opname. Koreksi melalui catatan stock opname.')
            db.execute('''INSERT INTO finished_goods_adjustment_reversals(adjustment_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(adjustment_id,payload['reason'],actor['id'],now()))
            return self._finished_goods_adjustment(db,adjustment_id)
        return self._write(actor,('admin',),key,'finished-goods-adjustment-reverse:'+adjustment_id,payload,perform)

    def _finished_goods_stock_count(self, db, count_id):
        row=db.execute('''SELECT c.*,u.name AS actor_name,a.id AS adjustment_id
            FROM finished_goods_stock_counts c JOIN users u ON u.id=c.actor_id
            LEFT JOIN finished_goods_adjustments a ON a.stock_count_id=c.id WHERE c.id=?''',(count_id,)).fetchone()
        if not row:
            raise DomainError(404,'Catatan stock opname tidak ditemukan.')
        record=dict(row)
        source=self._finished_goods_receipt(db,record['receipt_id'])
        for field in ('reference','order_id','order_reference','product_id','sku','product_name','color','size',
                      'final_qc_record_id','final_qc_reference','batch_id','batch_reference','received_date'):
            record['receipt_reference' if field=='reference' else field]=source[field]
        record['quantity_delta']=record['counted_quantity']-record['expected_quantity']
        reversal=db.execute('''SELECT r.*,u.name AS actor_name FROM finished_goods_stock_count_reversals r
            JOIN users u ON u.id=r.actor_id WHERE r.count_id=?''',(count_id,)).fetchone()
        record['reversal']=dict(reversal) if reversal else None
        record['status']='corrected' if reversal else 'active'
        return record

    def finished_goods_stock_count(self, count_id):
        with self.transaction() as db:
            return self._finished_goods_stock_count(db,count_id)

    def finished_goods_stock_counts(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():
                raise DomainError(404,'Order produksi tidak ditemukan.')
            ids=db.execute('''SELECT c.id FROM finished_goods_stock_counts c
                JOIN finished_goods_receipts x ON x.id=c.receipt_id
                JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs r ON r.id=b.cutting_run_id WHERE r.order_id=?
                AND (? IS NULL OR c.sequence<?) ORDER BY c.sequence DESC LIMIT ?''',
                (order_id,before,before,limit)).fetchall()
            return [self._finished_goods_stock_count(db,row['id']) for row in ids]

    def create_finished_goods_stock_count(self, receipt_id, payload, actor, key):
        def perform(db):
            receipt=self._finished_goods_receipt(db,receipt_id)
            if receipt['status']!='active':
                raise DomainError(409,'Penerimaan barang jadi harus aktif sebelum stock opname dicatat.')
            if payload['counted_date']<receipt['received_date']:
                raise DomainError(422,'Tanggal stock opname tidak boleh sebelum tanggal penerimaan.')
            if payload['scanned_sku'].casefold()!=receipt['sku'].casefold():
                raise DomainError(422,'SKU hasil scan tidak cocok dengan penerimaan barang jadi.')
            bucket=next((row for row in receipt['inventory'] if row['location'].casefold()==payload['location'].casefold()
                         and row['stock_status']==payload['stock_status']),None)
            expected=0 if not bucket else bucket['quantity']
            reserved=0 if not bucket else bucket['reserved_quantity']
            if payload['stock_status']=='sellable' and payload['counted_quantity']<reserved:
                raise DomainError(409,'Hasil hitung lebih kecil dari stok sellable yang masih terikat reservasi.')
            count_id=str(uuid4());timestamp=now()
            db.execute('''INSERT INTO finished_goods_stock_counts(id,reference,receipt_id,scanned_sku,location,
                stock_status,expected_quantity,counted_quantity,counted_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(count_id,payload['reference'],receipt_id,payload['scanned_sku'],
                payload['location'],payload['stock_status'],expected,payload['counted_quantity'],payload['counted_date'],
                payload['reason'],actor['id'],timestamp))
            delta=payload['counted_quantity']-expected
            if delta:
                db.execute('''INSERT INTO finished_goods_adjustments(id,reference,receipt_id,location,stock_status,
                    quantity_delta,adjusted_date,reason,actor_id,created_at,stock_count_id)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(str(uuid4()),payload['reference'],receipt_id,payload['location'],
                    payload['stock_status'],delta,payload['counted_date'],payload['reason'],actor['id'],timestamp,count_id))
            return self._finished_goods_stock_count(db,count_id)
        return self._write(actor,('admin','operator'),key,'finished-goods-stock-count:'+receipt_id,payload,perform)

    def reverse_finished_goods_stock_count(self, count_id, payload, actor, key):
        def perform(db):
            record=self._finished_goods_stock_count(db,count_id)
            if record['reversal']:
                raise DomainError(409,'Catatan stock opname sudah dikoreksi.')
            db.execute('''INSERT INTO finished_goods_stock_count_reversals(count_id,reason,actor_id,created_at)
                VALUES(?,?,?,?)''',(count_id,payload['reason'],actor['id'],now()))
            return self._finished_goods_stock_count(db,count_id)
        return self._write(actor,('admin',),key,'finished-goods-stock-count-reverse:'+count_id,payload,perform)

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
            CASE WHEN c.id IS NOT NULL THEN 'cancelled' WHEN z.order_id IS NOT NULL THEN 'closed'
              WHEN (SELECT status FROM purchase_order_approval_events WHERE order_id=p.id ORDER BY sequence DESC LIMIT 1)='submitted' THEN 'pending'
              ELSE (SELECT status FROM purchase_order_approval_events WHERE order_id=p.id ORDER BY sequence DESC LIMIT 1) END AS status
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

    def _create_purchase_request(self, db, payload, actor):
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

    def create_purchase_request(self, payload, actor, key):
        return self._write(actor, ('admin','operator'), key, 'purchase-request', payload,
                           lambda db:self._create_purchase_request(db,payload,actor))

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
            if any(po['status'] not in ('cancelled','rejected') for po in current['purchase_orders']):
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
        total_minor = record.pop('total_minor')
        record['total'] = format(Decimal(total_minor) / 100, '.2f')
        record['currency'] = 'IDR'
        record['approval_history'] = [dict(event) for event in db.execute('''SELECT e.*,u.name AS actor_name
            FROM purchase_order_approval_events e JOIN users u ON u.id=e.actor_id
            WHERE e.order_id=? ORDER BY e.sequence DESC''', (order_id,))]
        record['approval_status'] = record['approval_history'][0]['status']
        record['revision'] = record['approval_history'][0]['sequence']
        cancelled = db.execute('''SELECT c.*,u.name AS actor_name FROM purchase_order_cancellations c
            JOIN users u ON u.id=c.actor_id WHERE c.order_id=?''', (order_id,)).fetchone()
        record['cancellation'] = dict(cancelled) if cancelled else None
        closed = db.execute('''SELECT c.*,u.name AS actor_name FROM purchase_order_closures c
            JOIN users u ON u.id=c.actor_id WHERE c.order_id=?''', (order_id,)).fetchone()
        record['closure'] = dict(closed) if closed else None
        if record['approval_status']=='approved':
            record['status'] = 'cancelled' if cancelled else 'closed' if closed else 'issued'
        else:
            record['status'] = 'pending' if record['approval_status']=='submitted' else record['approval_status']
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
        payment_totals = db.execute("""SELECT
            COALESCE(SUM(CASE WHEN status='submitted' THEN amount_minor ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN status='approved' THEN amount_minor ELSE 0 END),0)
            FROM (SELECT r.amount_minor,(SELECT status FROM supplier_payment_request_events e
                WHERE e.request_id=r.id ORDER BY e.sequence DESC LIMIT 1) AS status
                FROM supplier_payment_requests r WHERE r.purchase_order_id=?)""", (order_id,)).fetchone()
        received_value_minor = sum(int((Decimal(line['received'])*Decimal(line['unit_price'])*100).quantize(
            Decimal('1'),rounding=ROUND_HALF_UP)) for line in record['lines'])
        record['payment_received_value'] = format(Decimal(received_value_minor)/100,'.2f')
        record['payment_pending'] = format(Decimal(payment_totals[0])/100,'.2f')
        record['payment_approved'] = format(Decimal(payment_totals[1])/100,'.2f')
        record['payment_remaining'] = format(Decimal(received_value_minor-payment_totals[0]-payment_totals[1])/100,'.2f')
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
                AND (?='all' OR ?=CASE WHEN c.id IS NOT NULL THEN 'cancelled' WHEN z.order_id IS NOT NULL THEN 'closed'
                    WHEN (SELECT status FROM purchase_order_approval_events WHERE order_id=p.id ORDER BY sequence DESC LIMIT 1)='submitted' THEN 'pending'
                    WHEN (SELECT status FROM purchase_order_approval_events WHERE order_id=p.id ORDER BY sequence DESC LIMIT 1)='approved' THEN 'issued'
                    ELSE (SELECT status FROM purchase_order_approval_events WHERE order_id=p.id ORDER BY sequence DESC LIMIT 1) END)
                ORDER BY p.sequence DESC LIMIT ?''', (before,before,request_id,request_id,status,status,limit)).fetchall()
            return [self._purchase_order(db, row[0]) for row in ids]

    def create_purchase_order(self, payload, actor, key):
        def perform(db):
            pr = self._purchase_request(db, payload['request_id'])
            if pr['status'] != 'approved' or pr['revision'] != payload['expected_revision']:
                raise DomainError(409, 'PR harus disetujui dan memakai revisi terbaru. Buka ulang PR.')
            if any(po['status'] not in ('cancelled','rejected') for po in pr['purchase_orders']):
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
            order_id, timestamp = str(uuid4()), now()
            db.execute('''INSERT INTO purchase_orders(id,reference,request_id,request_revision,supplier_id,supplier,
                expected_date,terms,lines,total_minor,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (order_id,payload['reference'],pr['id'],pr['revision'],supplier['id'],json.dumps(dict(supplier)),
                 payload['expected_date'],payload['terms'],json.dumps(lines),total,payload['reason'],actor['id'],timestamp))
            db.execute('''INSERT INTO purchase_order_approval_events(order_id,status,reason,actor_id,created_at)
                VALUES(?,'submitted',?,?,?)''', (order_id,payload['reason'],actor['id'],timestamp))
            return self._purchase_order(db, order_id)
        return self._write(actor, ('admin','operator'), key, 'purchase-order', payload, perform)

    def decide_purchase_order(self, order_id, payload, actor, key):
        def perform(db):
            po = self._purchase_order(db, order_id)
            role = db.execute('SELECT role FROM users WHERE id=?', (actor['id'],)).fetchone()[0]
            if role != 'admin' and not (payload['status']=='cancelled' and po['actor_id']==actor['id']):
                raise DomainError(403, 'Hanya admin memutuskan PO; pembuat boleh membatalkan pengajuannya.')
            if po['revision'] != payload['expected_revision']:
                raise DomainError(409, 'Approval PO sudah berubah. Buka ulang rincian dan periksa keputusan terbaru.')
            if po['approval_status'] != 'submitted':
                raise DomainError(409, 'Approval PO sudah diputuskan.')
            db.execute('''INSERT INTO purchase_order_approval_events(order_id,status,reason,actor_id,created_at)
                VALUES(?,?,?,?,?)''', (order_id,payload['status'],payload['reason'],actor['id'],now()))
            return self._purchase_order(db, order_id)
        return self._write(actor, ('admin','operator'), key, 'purchase-order-decision:'+order_id, payload, perform)

    def cancel_purchase_order(self, order_id, payload, actor, key):
        def perform(db):
            po = self._purchase_order(db, order_id)
            if po['status'] != 'issued':
                raise DomainError(409, 'PO belum disetujui atau sudah final.')
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
                raise DomainError(409, 'PO belum disetujui atau sudah final.')
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
                raise DomainError(409, 'PO harus disetujui dan aktif sebelum penerimaan.')
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

    def _supplier_payment_request(self, db, request_id):
        row = db.execute("""SELECT r.*,p.reference AS purchase_order_reference,p.supplier,
            a.name AS actor_name FROM supplier_payment_requests r
            JOIN purchase_orders p ON p.id=r.purchase_order_id
            JOIN users a ON a.id=r.actor_id WHERE r.id=?""", (request_id,)).fetchone()
        if not row:
            raise DomainError(404, 'Permintaan pembayaran supplier tidak ditemukan.')
        record = dict(row)
        record['supplier'] = json.loads(record['supplier'])
        record['amount'] = format(Decimal(record.pop('amount_minor'))/100,'.2f')
        record['currency'] = 'IDR'
        record['history'] = [dict(event) for event in db.execute("""SELECT e.*,u.name AS actor_name
            FROM supplier_payment_request_events e JOIN users u ON u.id=e.actor_id
            WHERE e.request_id=? ORDER BY e.sequence DESC""", (request_id,))]
        record['status'] = record['history'][0]['status']
        record['revision'] = record['history'][0]['sequence']
        return record

    def supplier_payment_request(self, request_id):
        with self.transaction() as db:
            return self._supplier_payment_request(db, request_id)

    def supplier_payment_requests(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM purchase_orders WHERE id=?', (order_id,)).fetchone():
                raise DomainError(404, 'PO tidak ditemukan.')
            ids = db.execute("""SELECT id FROM supplier_payment_requests WHERE purchase_order_id=?
                AND (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?""",
                (order_id,before,before,limit)).fetchall()
            return [self._supplier_payment_request(db, row['id']) for row in ids]

    def create_supplier_payment_request(self, order_id, payload, actor, key):
        def perform(db):
            po = self._purchase_order(db, order_id)
            if po['status'] not in ('issued','closed') or po['fulfillment']=='pending':
                raise DomainError(409, 'Pembayaran hanya dapat diajukan untuk PO approved yang sudah memiliki penerimaan.')
            amount_minor = int(Decimal(payload['amount'])*100)
            if amount_minor > int(Decimal(po['payment_remaining'])*100):
                raise DomainError(409, 'Nominal pembayaran melebihi sisa nilai PO yang belum diajukan.')
            request_id, timestamp = str(uuid4()), now()
            db.execute("""INSERT INTO supplier_payment_requests(id,reference,purchase_order_id,invoice_reference,
                invoice_date,due_date,amount_minor,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (request_id,payload['reference'],order_id,
                payload['invoice_reference'],payload['invoice_date'],payload['due_date'],amount_minor,
                payload['reason'],actor['id'],timestamp))
            db.execute("""INSERT INTO supplier_payment_request_events(request_id,status,reason,actor_id,created_at)
                VALUES(?,'submitted',?,?,?)""", (request_id,payload['reason'],actor['id'],timestamp))
            return self._supplier_payment_request(db, request_id)
        return self._write(actor, ('admin','operator'), key, 'supplier-payment-request:'+order_id, payload, perform)

    def decide_supplier_payment_request(self, request_id, payload, actor, key):
        def perform(db):
            request = self._supplier_payment_request(db, request_id)
            role = db.execute('SELECT role FROM users WHERE id=?', (actor['id'],)).fetchone()[0]
            if role!='admin' and not (payload['status']=='cancelled' and request['actor_id']==actor['id']):
                raise DomainError(403, 'Hanya admin memutuskan pembayaran; pemohon boleh membatalkan pengajuannya.')
            if request['revision']!=payload['expected_revision']:
                raise DomainError(409, 'Permintaan pembayaran sudah berubah. Buka ulang rincian keputusan terbaru.')
            if request['status']!='submitted':
                raise DomainError(409, 'Permintaan pembayaran sudah diputuskan.')
            db.execute("""INSERT INTO supplier_payment_request_events(request_id,status,reason,actor_id,created_at)
                VALUES(?,?,?,?,?)""", (request_id,payload['status'],payload['reason'],actor['id'],now()))
            return self._supplier_payment_request(db, request_id)
        return self._write(actor, ('admin','operator'), key, 'supplier-payment-decision:'+request_id, payload, perform)

    def _marketing_budget_request(self, db, request_id):
        row = db.execute("""SELECT r.*,u.name AS actor_name FROM marketing_budget_requests r
            JOIN users u ON u.id=r.actor_id WHERE r.id=?""", (request_id,)).fetchone()
        if not row:
            raise DomainError(404, 'Permintaan budget marketing tidak ditemukan.')
        record = dict(row)
        record['amount'] = format(Decimal(record.pop('amount_minor'))/100,'.2f')
        record['currency'] = 'IDR'
        record['history'] = [dict(event) for event in db.execute("""SELECT e.*,u.name AS actor_name
            FROM marketing_budget_request_events e JOIN users u ON u.id=e.actor_id
            WHERE e.request_id=? ORDER BY e.sequence DESC""", (request_id,))]
        record['status'] = record['history'][0]['status']
        record['revision'] = record['history'][0]['sequence']
        return record

    def marketing_budget_request(self, request_id):
        with self.transaction() as db:
            return self._marketing_budget_request(db, request_id)

    def marketing_budget_requests(self, limit=100, before=None, status='all'):
        with self.transaction() as db:
            ids = db.execute("""SELECT r.id FROM marketing_budget_requests r
                WHERE (? IS NULL OR r.sequence<?) AND (?='all' OR ?=(
                    SELECT e.status FROM marketing_budget_request_events e WHERE e.request_id=r.id
                    ORDER BY e.sequence DESC LIMIT 1))
                ORDER BY r.sequence DESC LIMIT ?""",
                (before,before,status,status,limit)).fetchall()
            return [self._marketing_budget_request(db, row['id']) for row in ids]

    def create_marketing_budget_request(self, payload, actor, key):
        def perform(db):
            request_id, timestamp = str(uuid4()), now()
            amount_minor = int(Decimal(payload['amount'])*100)
            db.execute("""INSERT INTO marketing_budget_requests(id,reference,campaign_name,channel,
                start_date,end_date,amount_minor,objective,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (request_id,payload['reference'],payload['campaign_name'],
                payload['channel'],payload['start_date'],payload['end_date'],amount_minor,
                payload['objective'],payload['reason'],actor['id'],timestamp))
            db.execute("""INSERT INTO marketing_budget_request_events(request_id,status,reason,actor_id,created_at)
                VALUES(?,'submitted',?,?,?)""", (request_id,payload['reason'],actor['id'],timestamp))
            return self._marketing_budget_request(db, request_id)
        return self._write(actor, ('admin','operator'), key, 'marketing-budget-request', payload, perform)

    def decide_marketing_budget_request(self, request_id, payload, actor, key):
        def perform(db):
            request = self._marketing_budget_request(db, request_id)
            role = db.execute('SELECT role FROM users WHERE id=?', (actor['id'],)).fetchone()[0]
            if role!='admin' and not (payload['status']=='cancelled' and request['actor_id']==actor['id']):
                raise DomainError(403, 'Hanya admin memutuskan budget; pemohon boleh membatalkan pengajuannya.')
            if request['revision']!=payload['expected_revision']:
                raise DomainError(409, 'Permintaan budget sudah berubah. Buka ulang rincian keputusan terbaru.')
            if request['status']!='submitted':
                raise DomainError(409, 'Permintaan budget sudah diputuskan.')
            db.execute("""INSERT INTO marketing_budget_request_events(request_id,status,reason,actor_id,created_at)
                VALUES(?,?,?,?,?)""", (request_id,payload['status'],payload['reason'],actor['id'],now()))
            return self._marketing_budget_request(db, request_id)
        return self._write(actor, ('admin','operator'), key, 'marketing-budget-decision:'+request_id, payload, perform)

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
                raise DomainError(409, 'PO harus disetujui dan aktif sebelum QC bahan masuk.')
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

    def _create_order(self, db, payload, actor):
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

    def create_order(self, payload, actor, key):
        return self._write(actor, ("admin",), key, "order", payload,
                           lambda db:self._create_order(db,payload,actor))

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

    def _apply_order_change(self, db, order_id, payload, actor):
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
        return self._order(db, order_id), record["id"]

    def change_order(self, order_id, payload, actor, key):
        def perform(db):
            return self._apply_order_change(db, order_id, payload, actor)[0]
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

    def _production_change_request(self, db, request_id):
        row = db.execute("""SELECT r.*,o.reference AS order_reference,o.title AS order_title,
            a.name AS actor_name,old.name AS old_owner_name,new.name AS new_owner_name
            FROM production_change_requests r JOIN orders o ON o.id=r.order_id
            JOIN users a ON a.id=r.actor_id JOIN users old ON old.id=r.old_owner_id
            JOIN users new ON new.id=r.new_owner_id WHERE r.id=?""", (request_id,)).fetchone()
        if not row:
            raise DomainError(404, "Permintaan perubahan produksi tidak ditemukan.")
        record = dict(row)
        record["history"] = [dict(event) for event in db.execute("""SELECT e.*,u.name AS actor_name
            FROM production_change_request_events e JOIN users u ON u.id=e.actor_id
            WHERE e.request_id=? ORDER BY e.sequence DESC""", (request_id,))]
        record["status"] = record["history"][0]["status"]
        record["revision"] = record["history"][0]["sequence"]
        current = self._order(db, record["order_id"])
        record["current_due_date"] = current["due_date"]
        record["current_owner_id"] = current["owner_id"]
        record["current_owner_name"] = current["owner_name"]
        record["current_order_revision"] = current["revision"]
        record["stale"] = record["status"] == "submitted" and current["revision"] != record["expected_revision"]
        return record

    def production_change_request(self, request_id):
        with self.transaction() as db:
            return self._production_change_request(db, request_id)

    def production_change_requests(self, order_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute("SELECT 1 FROM orders WHERE id=?", (order_id,)).fetchone():
                raise DomainError(404, "Order produksi tidak ditemukan.")
            ids = db.execute("""SELECT id FROM production_change_requests WHERE order_id=?
                AND (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?""",
                (order_id,before,before,limit)).fetchall()
            return [self._production_change_request(db, row["id"]) for row in ids]

    def create_production_change_request(self, order_id, payload, actor, key):
        def perform(db):
            order = self._order(db, order_id)
            if order["revision"] != payload["expected_revision"]:
                raise DomainError(409, "Jadwal atau PIC sudah berubah. Muat ulang order sebelum mengajukan persetujuan.")
            if not db.execute("SELECT 1 FROM users WHERE id=? AND active=1 AND role IN ('admin','operator')",
                              (payload["owner_id"],)).fetchone():
                raise DomainError(422, "PIC harus akun admin/operator yang aktif.")
            if order["due_date"] == payload["due_date"] and order["owner_id"] == payload["owner_id"]:
                raise DomainError(422, "Belum ada perubahan tenggat atau PIC.")
            pending = db.execute("""SELECT 1 FROM production_change_requests r WHERE r.order_id=? AND
                (SELECT status FROM production_change_request_events e WHERE e.request_id=r.id
                 ORDER BY e.sequence DESC LIMIT 1)='submitted'""", (order_id,)).fetchone()
            if pending:
                raise DomainError(409, "Order ini masih memiliki permintaan perubahan yang menunggu keputusan.")
            request_id, timestamp = str(uuid4()), now()
            db.execute("""INSERT INTO production_change_requests(id,reference,order_id,old_due_date,new_due_date,
                old_owner_id,new_owner_id,expected_revision,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (request_id,payload["reference"],order_id,order["due_date"],
                payload["due_date"],order["owner_id"],payload["owner_id"],payload["expected_revision"],
                payload["reason"],actor["id"],timestamp))
            db.execute("""INSERT INTO production_change_request_events(request_id,status,reason,actor_id,created_at)
                VALUES(?,'submitted',?,?,?)""", (request_id,payload["reason"],actor["id"],timestamp))
            return self._production_change_request(db, request_id)
        return self._write(actor, ("admin","operator"), key, "production-change-request:"+order_id, payload, perform)

    def decide_production_change_request(self, request_id, payload, actor, key):
        def perform(db):
            request = self._production_change_request(db, request_id)
            role = db.execute("SELECT role FROM users WHERE id=?", (actor["id"],)).fetchone()[0]
            if role != "admin" and not (payload["status"] == "cancelled" and request["actor_id"] == actor["id"]):
                raise DomainError(403, "Hanya admin memutuskan perubahan produksi; pemohon boleh membatalkan pengajuannya.")
            if request["revision"] != payload["expected_revision"]:
                raise DomainError(409, "Permintaan perubahan produksi sudah diputuskan. Buka ulang rinciannya.")
            if request["status"] != "submitted":
                raise DomainError(409, "Permintaan perubahan produksi sudah diputuskan.")
            order_change_id = None
            if payload["status"] == "approved":
                _, order_change_id = self._apply_order_change(db, request["order_id"], {
                    "owner_id": request["new_owner_id"], "due_date": request["new_due_date"],
                    "expected_revision": request["expected_revision"], "reason": request["reason"]}, actor)
            db.execute("""INSERT INTO production_change_request_events(request_id,status,reason,actor_id,order_change_id,created_at)
                VALUES(?,?,?,?,?,?)""", (request_id,payload["status"],payload["reason"],actor["id"],order_change_id,now()))
            return self._production_change_request(db, request_id)
        return self._write(actor, ("admin","operator"), key, "production-change-request-decision:"+request_id, payload, perform)

    @staticmethod
    def _ai_feedback(db, investigation_id):
        history=[dict(row) for row in db.execute('''SELECT f.*,u.name AS actor_name
            FROM ai_investigation_feedback f JOIN users u ON u.id=f.actor_id
            WHERE f.investigation_id=? ORDER BY f.sequence DESC''',(investigation_id,))]
        latest=[];seen=set()
        for row in history:
            if row['actor_id'] not in seen:
                latest.append(row);seen.add(row['actor_id'])
        return history,{'helpful':sum(row['rating']=='helpful' for row in latest),
                        'not_helpful':sum(row['rating']=='not_helpful' for row in latest),
                        'respondents':len(latest)}

    def _ai_investigation(self, db, investigation_id):
        row=db.execute('''SELECT i.*,u.name AS actor_name FROM ai_investigations i
            JOIN users u ON u.id=i.actor_id WHERE i.id=?''',(investigation_id,)).fetchone()
        if not row:
            raise DomainError(404,'Investigasi AI tidak ditemukan.')
        record=dict(row)
        source_payload=json.loads(record.pop('source_payload'))
        result=json.loads(record.pop('result_snapshot'))
        feedback,summary=self._ai_feedback(db,investigation_id)
        links=[self._ai_action_proposal(db,item['proposal_id']) for item in db.execute(
            '''SELECT proposal_id FROM ai_investigation_actions WHERE investigation_id=?
               ORDER BY created_at DESC,proposal_id DESC''',(investigation_id,))]
        return result|record|{'source_payload':source_payload,'feedback':feedback,
            'feedback_summary':summary,'linked_actions':links}

    def create_ai_investigation(self, payload, actor, key):
        def perform(db):
            from beeloft.brain import investigate
            result=investigate(self,payload)
            investigation_id,timestamp=str(uuid4()),now()
            db.execute('''INSERT INTO ai_investigations(id,question,intent,source_payload,
                result_snapshot,actor_id,created_at) VALUES(?,?,?,?,?,?,?)''',(
                investigation_id,payload['question'],result['intent'],json.dumps(payload),
                json.dumps(result),actor['id'],timestamp))
            return self._ai_investigation(db,investigation_id)
        return self._write(actor,('admin','operator','viewer'),key,'ai-investigation',payload,perform)

    def ai_investigation(self, investigation_id):
        with self.transaction() as db:
            return self._ai_investigation(db,investigation_id)

    def ai_investigations(self, limit=100, before=None, intent='all', query=''):
        query=query.strip().casefold()
        with self.transaction() as db:
            rows=db.execute('''SELECT i.*,u.name AS actor_name FROM ai_investigations i
                JOIN users u ON u.id=i.actor_id WHERE (? IS NULL OR i.sequence<?)
                AND (?='all' OR i.intent=?) AND (?='' OR instr(lower(i.question),?)>0)
                ORDER BY i.sequence DESC LIMIT ?''',(before,before,intent,intent,query,query,limit)).fetchall()
            items=[]
            for row in rows:
                report=json.loads(row['result_snapshot'])
                _,feedback=self._ai_feedback(db,row['id'])
                actions=db.execute('''SELECT COUNT(*) FROM ai_investigation_actions
                    WHERE investigation_id=?''',(row['id'],)).fetchone()[0]
                items.append({'id':row['id'],'sequence':row['sequence'],'question':row['question'],
                    'intent':row['intent'],'interpretation':report['interpretation'],
                    'answer':report['answer'],'actor_id':row['actor_id'],'actor_name':row['actor_name'],
                    'created_at':row['created_at'],'feedback_summary':feedback,'action_count':actions})
            return items

    def create_ai_investigation_feedback(self, investigation_id, payload, actor, key):
        def perform(db):
            if not db.execute('SELECT 1 FROM ai_investigations WHERE id=?',
                              (investigation_id,)).fetchone():
                raise DomainError(404,'Investigasi AI tidak ditemukan.')
            db.execute('''INSERT INTO ai_investigation_feedback(id,investigation_id,rating,reason,
                actor_id,created_at) VALUES(?,?,?,?,?,?)''',(str(uuid4()),investigation_id,
                payload['rating'],payload['reason'],actor['id'],now()))
            return self._ai_investigation(db,investigation_id)
        return self._write(actor,('admin','operator','viewer'),key,
            'ai-investigation-feedback:'+investigation_id,payload,perform)

    @staticmethod
    def _recommendation_fingerprint(recommendation):
        return hashlib.sha256(json.dumps(recommendation,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def _ai_recommendation(self, source_payload, action_kind, subject_id):
        from beeloft.brain import investigate
        report=investigate(self,source_payload)
        subject_key='product_id' if action_kind=='create_production_order' else 'material_id'
        recommendation=next((row for row in report['recommendations']
            if row['kind']==action_kind and row['preview'].get(subject_key)==subject_id),None)
        if recommendation is None:
            raise DomainError(409,'Rekomendasi tidak lagi tersedia. Jalankan investigasi baru sebelum mengajukan tindakan.')
        return recommendation

    def _ai_action_proposal(self, db, proposal_id):
        row=db.execute('''SELECT p.*,u.name AS actor_name FROM ai_action_proposals p
            JOIN users u ON u.id=p.actor_id WHERE p.id=?''',(proposal_id,)).fetchone()
        if not row:
            raise DomainError(404,'Proposal tindakan AI tidak ditemukan.')
        record=dict(row)
        for field in ('source_payload','recommendation','action_payload'):
            record[field]=json.loads(record[field])
        record['history']=[dict(event) for event in db.execute('''SELECT e.*,u.name AS actor_name
            FROM ai_action_proposal_events e JOIN users u ON u.id=e.actor_id
            WHERE e.proposal_id=? ORDER BY e.sequence DESC''',(proposal_id,))]
        record['status']=record['history'][0]['status']
        record['revision']=record['history'][0]['sequence']
        record['executed_entity_type']=record['history'][0]['executed_entity_type']
        record['executed_entity_id']=record['history'][0]['executed_entity_id']
        link=db.execute('''SELECT investigation_id FROM ai_investigation_actions
            WHERE proposal_id=?''',(proposal_id,)).fetchone()
        record['investigation_id']=link['investigation_id'] if link else None
        return record

    def create_ai_action_proposal(self, payload, actor, key):
        source_keys=('question','as_of','window_days','lead_time_days','review_period_days',
                     'safety_stock_days','batch_multiple')
        source_payload={name:payload[name] for name in source_keys}
        def perform(db):
            recommendation=self._ai_recommendation(source_payload,payload['action_kind'],payload['subject_id'])
            investigation_id=payload.get('investigation_id')
            if investigation_id:
                investigation=db.execute('''SELECT source_payload,result_snapshot FROM ai_investigations
                    WHERE id=?''',(investigation_id,)).fetchone()
                if not investigation:
                    raise DomainError(404,'Investigasi AI tidak ditemukan.')
                if json.loads(investigation['source_payload'])!=source_payload:
                    raise DomainError(409,'Asumsi proposal berbeda dari investigasi tersimpan. Jalankan investigasi baru.')
                stored_report=json.loads(investigation['result_snapshot'])
                subject_key='product_id' if payload['action_kind']=='create_production_order' else 'material_id'
                stored=next((row for row in stored_report['recommendations']
                    if row['kind']==payload['action_kind'] and
                    row['preview'].get(subject_key)==payload['subject_id']),None)
                if stored is None or self._recommendation_fingerprint(stored)!=self._recommendation_fingerprint(recommendation):
                    raise DomainError(409,'Rekomendasi investigasi sudah berubah. Jalankan investigasi baru.')
            if payload['action_kind']=='create_production_order':
                action_payload={'reference':payload['reference'],'title':payload['title'],
                    'owner_id':payload['owner_id'],'due_date':payload['due_date'],
                    'lines':[{'product_id':payload['subject_id'],
                              'quantity':recommendation['preview']['quantity']}]}
            else:
                action_payload={'reference':payload['reference'],'order_id':None,
                    'required_date':payload['required_date'],'estimated_value':payload['estimated_value'],
                    'reason':payload['reason'],'lines':[{'material_id':payload['subject_id'],
                        'quantity':recommendation['preview']['quantity']}]}
            fingerprint=self._recommendation_fingerprint(recommendation)
            if payload['action_kind']=='create_production_order':
                if db.execute('SELECT 1 FROM orders WHERE reference=?',(payload['reference'],)).fetchone():
                    raise DomainError(409,'Referensi order produksi sudah digunakan.')
            elif db.execute('SELECT 1 FROM purchase_requests WHERE reference=?',(payload['reference'],)).fetchone():
                raise DomainError(409,'Referensi PR sudah digunakan.')
            proposal_id,timestamp=str(uuid4()),now()
            db.execute('''INSERT INTO ai_action_proposals(id,action_kind,subject_id,reference,source_payload,
                recommendation,recommendation_fingerprint,action_payload,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(proposal_id,payload['action_kind'],payload['subject_id'],
                payload['reference'],json.dumps(source_payload),json.dumps(recommendation),fingerprint,
                json.dumps(action_payload),payload['reason'],actor['id'],timestamp))
            db.execute('''INSERT INTO ai_action_proposal_events(proposal_id,status,reason,actor_id,created_at)
                VALUES(?,'submitted',?,?,?)''',(proposal_id,payload['reason'],actor['id'],timestamp))
            if investigation_id:
                db.execute('''INSERT INTO ai_investigation_actions(investigation_id,proposal_id,created_at)
                    VALUES(?,?,?)''',(investigation_id,proposal_id,timestamp))
            return self._ai_action_proposal(db,proposal_id)
        return self._write(actor,('admin','operator'),key,'ai-action-proposal',payload,perform)

    def ai_action_proposal(self, proposal_id):
        with self.transaction() as db:
            return self._ai_action_proposal(db,proposal_id)

    def ai_action_proposals(self, limit=100, before=None, status='all'):
        with self.transaction() as db:
            ids=db.execute('''SELECT p.id FROM ai_action_proposals p WHERE (? IS NULL OR p.sequence<?)
                AND (?='all' OR (SELECT status FROM ai_action_proposal_events e
                    WHERE e.proposal_id=p.id ORDER BY e.sequence DESC LIMIT 1)=?)
                ORDER BY p.sequence DESC LIMIT ?''',(before,before,status,status,limit)).fetchall()
            return [self._ai_action_proposal(db,row['id']) for row in ids]

    def decide_ai_action_proposal(self, proposal_id, payload, actor, key):
        def perform(db):
            proposal=self._ai_action_proposal(db,proposal_id)
            role=db.execute('SELECT role FROM users WHERE id=?',(actor['id'],)).fetchone()[0]
            if role!='admin' and not (payload['status']=='cancelled' and proposal['actor_id']==actor['id']):
                raise DomainError(403,'Hanya admin memutuskan proposal AI; pemohon boleh membatalkan proposalnya.')
            if proposal['revision']!=payload['expected_revision'] or proposal['status']!='submitted':
                raise DomainError(409,'Proposal tindakan AI sudah diputuskan. Buka ulang rinciannya.')
            executed_type=executed_id=None
            if payload['status']=='approved':
                current=self._ai_recommendation(proposal['source_payload'],proposal['action_kind'],proposal['subject_id'])
                if self._recommendation_fingerprint(current)!=proposal['recommendation_fingerprint']:
                    raise DomainError(409,'Rekomendasi sudah berubah. Tolak proposal ini dan jalankan investigasi baru.')
                if proposal['action_kind']=='create_production_order':
                    executed=self._create_order(db,proposal['action_payload'],actor)
                    executed_type='production_order'
                else:
                    executed=self._create_purchase_request(db,proposal['action_payload'],actor)
                    executed_type='purchase_request'
                executed_id=executed['id']
            db.execute('''INSERT INTO ai_action_proposal_events(proposal_id,status,reason,actor_id,
                executed_entity_type,executed_entity_id,created_at) VALUES(?,?,?,?,?,?,?)''',
                (proposal_id,payload['status'],payload['reason'],actor['id'],executed_type,executed_id,now()))
            return self._ai_action_proposal(db,proposal_id)
        return self._write(actor,('admin','operator'),key,'ai-action-proposal-decision:'+proposal_id,payload,perform)

    def approvals(self, limit=100, offset=0, status="pending", kind="all"):
        with self.transaction() as db:
            items = []
            if kind in ("all","purchase_request"):
                for row in db.execute("SELECT id FROM purchase_requests"):
                    request = self._purchase_request(db, row["id"])
                    current_status = "pending" if request["status"] == "submitted" else request["status"]
                    if status not in ("all", current_status):
                        continue
                    items.append({"id":request["id"],"kind":"purchase_request","department":"Purchasing",
                        "status":current_status,"reference":request["reference"],
                        "title":request["order_reference"] or "Permintaan pembelian umum",
                        "amount":request["estimated_value"],"currency":"IDR","reason":request["reason"],
                        "actor_id":request["actor_id"],"actor_name":request["actor_name"],
                        "created_at":request["created_at"],"context":{"required_date":request["required_date"],
                        "line_count":len(request["lines"]),"order_id":request["order_id"]}})
            if kind in ("all","purchase_order"):
                for row in db.execute("SELECT id FROM purchase_orders"):
                    order = self._purchase_order(db, row["id"])
                    current_status = "pending" if order["approval_status"] == "submitted" else order["approval_status"]
                    if status not in ("all", current_status):
                        continue
                    items.append({"id":order["id"],"kind":"purchase_order","department":"Purchasing",
                        "status":current_status,"reference":order["reference"],
                        "title":order["supplier"]["name"]+" · PR "+order["request_reference"],
                        "amount":order["total"],"currency":"IDR","reason":order["reason"],
                        "actor_id":order["actor_id"],"actor_name":order["actor_name"],
                        "created_at":order["created_at"],"context":{"request_id":order["request_id"],
                        "request_reference":order["request_reference"],"supplier_name":order["supplier"]["name"],
                        "expected_date":order["expected_date"],"line_count":len(order["lines"])}})
            if kind in ("all","supplier_payment"):
                for row in db.execute("SELECT id FROM supplier_payment_requests"):
                    request = self._supplier_payment_request(db, row["id"])
                    current_status = "pending" if request["status"]=="submitted" else request["status"]
                    if status not in ("all",current_status):
                        continue
                    items.append({"id":request["id"],"kind":"supplier_payment","department":"Finance",
                        "status":current_status,"reference":request["reference"],
                        "title":request["supplier"]["name"]+" · PO "+request["purchase_order_reference"],
                        "amount":request["amount"],"currency":"IDR","reason":request["reason"],
                        "actor_id":request["actor_id"],"actor_name":request["actor_name"],
                        "created_at":request["created_at"],"context":{
                        "purchase_order_id":request["purchase_order_id"],
                        "purchase_order_reference":request["purchase_order_reference"],
                        "supplier_name":request["supplier"]["name"],
                        "invoice_reference":request["invoice_reference"],
                        "invoice_date":request["invoice_date"],"due_date":request["due_date"]}})
            if kind in ("all","marketing_budget"):
                for row in db.execute("SELECT id FROM marketing_budget_requests"):
                    request = self._marketing_budget_request(db, row["id"])
                    current_status = "pending" if request["status"]=="submitted" else request["status"]
                    if status not in ("all",current_status):
                        continue
                    items.append({"id":request["id"],"kind":"marketing_budget","department":"Marketing",
                        "status":current_status,"reference":request["reference"],
                        "title":request["campaign_name"]+" · "+request["channel"],
                        "amount":request["amount"],"currency":"IDR","reason":request["reason"],
                        "actor_id":request["actor_id"],"actor_name":request["actor_name"],
                        "created_at":request["created_at"],"context":{
                        "campaign_name":request["campaign_name"],"channel":request["channel"],
                        "start_date":request["start_date"],"end_date":request["end_date"],
                        "objective":request["objective"]}})
            if kind in ("all","production_change"):
                for row in db.execute("SELECT id FROM production_change_requests"):
                    request = self._production_change_request(db, row["id"])
                    current_status = "pending" if request["status"] == "submitted" else request["status"]
                    if status not in ("all", current_status):
                        continue
                    items.append({"id":request["id"],"kind":"production_change","department":"Production",
                        "status":current_status,"reference":request["reference"],
                        "title":request["order_reference"]+" · "+request["order_title"],
                        "amount":None,"currency":None,"reason":request["reason"],
                        "actor_id":request["actor_id"],"actor_name":request["actor_name"],
                        "created_at":request["created_at"],"context":{"order_id":request["order_id"],
                        "old_due_date":request["old_due_date"],"new_due_date":request["new_due_date"],
                        "old_owner_name":request["old_owner_name"],"new_owner_name":request["new_owner_name"],
                        "stale":request["stale"]}})
            if kind in ('all','ai_action'):
                for row in db.execute('SELECT id FROM ai_action_proposals'):
                    proposal=self._ai_action_proposal(db,row['id'])
                    current_status='pending' if proposal['status']=='submitted' else proposal['status']
                    if status not in ('all',current_status):
                        continue
                    action_label='Buat order produksi' if proposal['action_kind']=='create_production_order' else 'Buat purchase request'
                    items.append({'id':proposal['id'],'kind':'ai_action','department':'AI Brain',
                        'status':current_status,'reference':proposal['reference'],'title':action_label,
                        'amount':proposal['action_payload'].get('estimated_value'),'currency':'IDR' if
                            proposal['action_kind']=='create_purchase_request' else None,
                        'reason':proposal['reason'],'actor_id':proposal['actor_id'],
                        'actor_name':proposal['actor_name'],'created_at':proposal['created_at'],
                        'context':{'action_kind':proposal['action_kind'],'subject_id':proposal['subject_id'],
                            'recommendation_title':proposal['recommendation']['title'],
                            'executed_entity_type':proposal['executed_entity_type'],
                            'executed_entity_id':proposal['executed_entity_id']}})
            items.sort(key=lambda row:(row["created_at"],row["kind"],row["id"]), reverse=True)
            return items[offset:offset+limit]

    def production_cost(self, order_id):
        with self.transaction() as db:
            order = self._order(db, order_id)
            issues = db.execute("""SELECT m.id AS issue_id,-m.quantity_milli AS issued_milli,
                b.id AS batch_id,b.reference AS batch_reference,s.id AS material_id,s.code,s.name,s.unit,
                COALESCE((SELECT SUM(c.used_milli) FROM material_consumption c WHERE c.issue_id=m.id),0) AS used_milli,
                COALESCE((SELECT SUM(c.waste_milli) FROM material_consumption c WHERE c.issue_id=m.id),0) AS waste_milli,
                p.id AS purchase_order_id,p.reference AS purchase_order_reference,
                (SELECT json_extract(line.value,'$.unit_price') FROM json_each(p.lines) line
                 WHERE json_extract(line.value,'$.material_id')=s.id) AS unit_price
                FROM material_movements m JOIN material_batches b ON b.id=m.batch_id
                JOIN materials s ON s.id=b.material_id
                LEFT JOIN purchase_order_receipts x ON x.batch_id=b.id
                LEFT JOIN purchase_orders p ON p.id=x.purchase_order_id
                WHERE m.order_id=? AND m.kind='issue' AND NOT EXISTS(
                    SELECT 1 FROM material_movements r WHERE r.reversal_of=m.id)
                ORDER BY m.sequence""", (order_id,)).fetchall()
            grouped = {}
            for source in issues:
                key = source['batch_id']
                item = grouped.setdefault(key, dict(source) | {
                    'issued_milli':0, 'used_milli':0, 'waste_milli':0})
                for field in ('issued_milli','used_milli','waste_milli'):
                    item[field] += source[field]

            material_cost_minor = 0
            materials = []
            gaps = []
            for item in grouped.values():
                issued = item.pop('issued_milli')
                used = item.pop('used_milli')
                waste = item.pop('waste_milli')
                consumed = used+waste
                unreported = issued-consumed
                unit_price = item['unit_price']
                cost_minor = None
                if unit_price is not None:
                    cost_minor = int((Decimal(consumed)/1000*Decimal(unit_price)*100).quantize(
                        Decimal('1'), rounding=ROUND_HALF_UP))
                    material_cost_minor += cost_minor
                    item['unit_price'] = format(Decimal(unit_price),'.2f')
                item.update(issued=self._material_decimal(issued), used=self._material_decimal(used),
                    waste=self._material_decimal(waste), consumed=self._material_decimal(consumed),
                    unreported=self._material_decimal(unreported),
                    cost=None if cost_minor is None else format(Decimal(cost_minor)/100,'.2f'))
                materials.append(item)
                if consumed and unit_price is None:
                    gaps.append({'kind':'unpriced_consumption','batch_id':item['batch_id'],
                        'batch_reference':item['batch_reference'],'material_id':item['material_id'],
                        'code':item['code'],'quantity':self._material_decimal(consumed),'unit':item['unit']})
                if unreported:
                    gaps.append({'kind':'unreported_issue','batch_id':item['batch_id'],
                        'batch_reference':item['batch_reference'],'material_id':item['material_id'],
                        'code':item['code'],'quantity':self._material_decimal(unreported),'unit':item['unit']})
            if not materials:
                gaps.append({'kind':'no_material_consumption'})

            jobs = [dict(row) for row in db.execute("""SELECT j.id,j.reference,j.assignment_type,j.assignee,
                j.quantity_out,j.cost_minor,j.sent_date,
                CASE WHEN EXISTS(SELECT 1 FROM sewing_job_results x WHERE x.job_id=j.id)
                     THEN 'completed' ELSE 'open' END AS status
                FROM sewing_jobs j JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs r ON r.id=b.cutting_run_id WHERE r.order_id=?
                AND NOT EXISTS(SELECT 1 FROM sewing_job_reversals x WHERE x.job_id=j.id)
                ORDER BY j.sequence""", (order_id,))]
            sewing_cost_minor = 0
            for job in jobs:
                sewing_cost_minor += job['cost_minor']
                job['cost'] = format(Decimal(job.pop('cost_minor'))/100,'.2f')

            finished_quantity = db.execute("""SELECT COALESCE(SUM(x.sellable_quantity+x.hold_quantity),0)
                FROM finished_goods_receipts x JOIN final_qc_records q ON q.id=x.final_qc_record_id
                JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
                JOIN bundles b ON b.id=j.bundle_id JOIN cutting_runs r ON r.id=b.cutting_run_id
                WHERE r.order_id=? AND NOT EXISTS(
                    SELECT 1 FROM finished_goods_receipt_reversals z WHERE z.receipt_id=x.id)""",
                (order_id,)).fetchone()[0]
            known_cost_minor = material_cost_minor+sewing_cost_minor
            complete = not gaps
            money = lambda minor: format(Decimal(minor)/100,'.2f')
            per_unit = lambda quantity: format((Decimal(known_cost_minor)/100/quantity).quantize(
                Decimal('.01'), rounding=ROUND_HALF_UP),'.2f') if complete and quantity else None
            return {'order_id':order['id'],'order_reference':order['reference'],'order_title':order['title'],
                'target_quantity':order['target_quantity'],'finished_quantity':finished_quantity,
                'currency':'IDR','status':'complete' if complete else 'incomplete',
                'material_cost':money(material_cost_minor),'sewing_cost':money(sewing_cost_minor),
                'known_cost':money(known_cost_minor),'total_cost':money(known_cost_minor) if complete else None,
                'cost_per_target_unit':per_unit(order['target_quantity']),
                'cost_per_finished_unit':per_unit(finished_quantity),
                'materials':materials,'sewing_jobs':jobs,'coverage_gaps':gaps,
                'scope':['material_consumption','sewing_jobs'],
                'excluded_costs':['internal_labor','finishing','quality_control','packaging','freight','overhead']}

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
