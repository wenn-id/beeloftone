import hashlib
import json
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from beeloft.models import STAGES, TRANSITIONS, UserCreate
from beeloft.labels import bundle_scan_code, finished_goods_scan_code, material_batch_scan_code

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

AUDIT_BULK_FIELDS = {'items','orders','returns','listings','periods','payables','receivables'}
AUDIT_SECRET_FIELDS = {'api_key','client_secret','code','code_verifier','csrf','password','token'}
AUDIT_APPROVAL_OPERATIONS = {
    'purchase-request-decision','purchase-order-decision','supplier-payment-decision',
    'marketing-budget-decision','production-change-request-decision','ai-action-proposal-decision'
}


def audit_category(operation):
    root=operation.split(':',1)[0]
    if root in AUDIT_APPROVAL_OPERATIONS:
        return 'approval'
    if root.startswith(('integration-', 'jubelio-', 'mekari-')):
        return 'integration'
    if root.startswith('ai-'):
        return 'ai'
    if root.startswith('marketplace-'):
        return 'marketplace'
    if root.startswith(('finished-goods', 'warehouse-')):
        return 'warehouse'
    if root.startswith(('purchase-', 'supplier-', 'qc-')):
        return 'purchasing'
    if root.startswith(('material-', 'consumption-', 'bom')):
        return 'materials'
    if root == 'supplier' or root.startswith('product'):
        return 'master_data'
    return 'production'


def audit_value(value, field=''):
    lowered=field.casefold()
    if lowered in AUDIT_SECRET_FIELDS or lowered.endswith(('_token','_secret','_password','_api_key')):
        return '[REDACTED]'
    if field in AUDIT_BULK_FIELDS and isinstance(value,list):
        return {'record_count':len(value)}
    if isinstance(value,dict):
        return {str(key):audit_value(item,str(key)) for key,item in value.items()}
    if isinstance(value,list):
        return [audit_value(item) for item in value]
    return value


def audit_outcome(result):
    if not isinstance(result,dict):
        return {'result_type':type(result).__name__}
    return {key:audit_value(value,key) for key,value in result.items()
            if not isinstance(value,(dict,list))}


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
            if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49):
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
            if version < 36:
                db.executescript(Path(__file__).with_name("jubelio_order_snapshots.sql").read_text(encoding="utf-8"))
            if version < 37:
                db.executescript(Path(__file__).with_name("jubelio_return_snapshots.sql").read_text(encoding="utf-8"))
            if version < 38:
                db.executescript(Path(__file__).with_name("jubelio_listing_snapshots.sql").read_text(encoding="utf-8"))
            if version < 39:
                db.executescript(Path(__file__).with_name("mekari_finance_snapshots.sql").read_text(encoding="utf-8"))
            if version < 40:
                db.executescript(Path(__file__).with_name("mekari_payable_snapshots.sql").read_text(encoding="utf-8"))
            if version < 41:
                db.executescript(Path(__file__).with_name("mekari_receivable_snapshots.sql").read_text(encoding="utf-8"))
            if version < 42:
                db.executescript(Path(__file__).with_name("mekari_payroll_snapshots.sql").read_text(encoding="utf-8"))
            if version < 43:
                db.executescript(Path(__file__).with_name("browser_sessions.sql").read_text(encoding="utf-8"))
            if version < 44:
                db.executescript(Path(__file__).with_name("oidc_sso.sql").read_text(encoding="utf-8"))
            if version < 45:
                db.executescript(Path(__file__).with_name("audit_trail.sql").read_text(encoding="utf-8"))
            if version < 46:
                db.executescript(Path(__file__).with_name("bundle_handoffs.sql").read_text(encoding="utf-8"))
            if version < 47:
                pick_columns={row['name'] for row in db.execute('PRAGMA table_info(marketplace_picks)')}
                migration=('marketplace_pick_scanning_existing.sql' if 'scanned_code' in pick_columns
                           else 'marketplace_pick_scanning.sql')
                db.executescript(Path(__file__).with_name(migration).read_text(encoding="utf-8"))
            if version < 48:
                movement_columns={row['name'] for row in db.execute('PRAGMA table_info(warehouse_movements)')}
                migration=('warehouse_movement_scanning_existing.sql' if 'scanned_code' in movement_columns
                           else 'warehouse_movement_scanning.sql')
                db.executescript(Path(__file__).with_name(migration).read_text(encoding="utf-8"))
            if version < 49:
                db.executescript(Path(__file__).with_name('production_capacity.sql').read_text(encoding='utf-8'))

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

    def _create_browser_session(self, db, user_id, lifetime_hours):
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        created=datetime.now(timezone.utc);expires=created+timedelta(hours=lifetime_hours)
        user=db.execute('SELECT id,name,role FROM users WHERE id=? AND active=1',(user_id,)).fetchone()
        if not user:
            raise DomainError(401,'Akun tidak ditemukan atau nonaktif.')
        db.execute('DELETE FROM browser_sessions WHERE expires_at<=?',(created.isoformat(),))
        db.execute('''INSERT INTO browser_sessions(token_hash,csrf_hash,user_id,created_at,expires_at)
            VALUES(?,?,?,?,?)''',(hashlib.sha256(token.encode()).hexdigest(),
            hashlib.sha256(csrf.encode()).hexdigest(),user['id'],created.isoformat(),expires.isoformat()))
        return dict(user),token,csrf

    def create_browser_session(self, key, lifetime_hours=8):
        with self.transaction(write=True) as db:
            user=db.execute('SELECT id,name,role FROM users WHERE key_hash=? AND active=1',
                (hashlib.sha256(key.encode()).hexdigest(),)).fetchone()
            if not user:
                raise DomainError(401,'API key tidak valid atau akun nonaktif.')
            return self._create_browser_session(db,user['id'],lifetime_hours)

    def create_browser_session_for_user(self, user_id, lifetime_hours=8):
        with self.transaction(write=True) as db:
            return self._create_browser_session(db,user_id,lifetime_hours)

    def authenticate_browser_session(self, token, csrf_token=None, require_csrf=False):
        token_hash=hashlib.sha256(token.encode()).hexdigest()
        with self.transaction() as db:
            row=db.execute('''SELECT u.id,u.name,u.role,s.csrf_hash FROM browser_sessions s
                JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1''',
                (token_hash,now())).fetchone()
            if not row:
                raise DomainError(401,'Sesi browser berakhir atau akun nonaktif.')
            if require_csrf:
                supplied=hashlib.sha256((csrf_token or '').encode()).hexdigest()
                if not secrets.compare_digest(supplied,row['csrf_hash']):
                    raise DomainError(403,'Token keamanan browser tidak valid.')
            return {name:row[name] for name in ('id','name','role')}

    def revoke_browser_session(self, token):
        with self.transaction(write=True) as db:
            db.execute('DELETE FROM browser_sessions WHERE token_hash=?',
                       (hashlib.sha256(token.encode()).hexdigest(),))

    @staticmethod
    def _oidc_identity_values(issuer, subject):
        issuer=issuer.strip().rstrip('/');subject=subject.strip()
        parsed=urlsplit(issuer)
        if (parsed.scheme!='https' or not parsed.netloc or parsed.fragment or parsed.query
                or parsed.username or parsed.password or not 8<=len(issuer)<=500):
            raise DomainError(422,'Issuer OIDC harus berupa URL HTTPS yang valid.')
        if not 1<=len(subject)<=500:
            raise DomainError(422,'Subject OIDC wajib diisi dan maksimal 500 karakter.')
        return issuer,subject

    def link_oidc_identity(self, issuer, subject, user_id):
        issuer,subject=self._oidc_identity_values(issuer,subject)
        with self.transaction(write=True) as db:
            user=db.execute('SELECT id,name,role,active FROM users WHERE id=?',(user_id,)).fetchone()
            if not user:
                raise DomainError(404,'Pengguna tidak ditemukan.')
            try:
                db.execute('''INSERT INTO oidc_identities(issuer,subject,user_id,created_at)
                    VALUES(?,?,?,?)''',(issuer,subject,user_id,now()))
            except sqlite3.IntegrityError as exc:
                raise DomainError(409,'Identitas atau pengguna sudah ditautkan untuk issuer ini.') from exc
            return {'issuer':issuer,'subject':subject,'user_id':user_id,
                    'user_name':user['name'],'role':user['role'],'active':user['active']}

    def unlink_oidc_identity(self, issuer, subject):
        issuer,subject=self._oidc_identity_values(issuer,subject)
        with self.transaction(write=True) as db:
            deleted=db.execute('DELETE FROM oidc_identities WHERE issuer=? AND subject=?',(issuer,subject))
            if deleted.rowcount!=1:
                raise DomainError(404,'Identitas OIDC tidak ditemukan.')

    def authenticate_oidc_identity(self, issuer, subject):
        issuer,subject=self._oidc_identity_values(issuer,subject)
        with self.transaction(write=True) as db:
            row=db.execute('''SELECT u.id,u.name,u.role,u.active FROM oidc_identities i
                JOIN users u ON u.id=i.user_id WHERE i.issuer=? AND i.subject=?''',(issuer,subject)).fetchone()
            if not row:
                raise DomainError(403,'Identitas SSO belum ditautkan ke akun Beeloft.')
            if not row['active']:
                raise DomainError(401,'Akun Beeloft untuk identitas SSO ini nonaktif.')
            db.execute('UPDATE oidc_identities SET last_login_at=? WHERE issuer=? AND subject=?',
                       (now(),issuer,subject))
            return {name:row[name] for name in ('id','name','role')}

    def create_oidc_login_attempt(self, state, nonce, verifier, lifetime_minutes=10):
        created=datetime.now(timezone.utc);expires=created+timedelta(minutes=lifetime_minutes)
        with self.transaction(write=True) as db:
            db.execute('DELETE FROM oidc_login_attempts WHERE expires_at<=?',(created.isoformat(),))
            db.execute('''INSERT INTO oidc_login_attempts(state_hash,nonce_hash,code_verifier,created_at,expires_at)
                VALUES(?,?,?,?,?)''',(hashlib.sha256(state.encode()).hexdigest(),
                hashlib.sha256(nonce.encode()).hexdigest(),verifier,created.isoformat(),expires.isoformat()))

    def consume_oidc_login_attempt(self, state):
        state_hash=hashlib.sha256(state.encode()).hexdigest()
        with self.transaction(write=True) as db:
            row=db.execute('''SELECT nonce_hash,code_verifier FROM oidc_login_attempts
                WHERE state_hash=? AND expires_at>?''',(state_hash,now())).fetchone()
            db.execute('DELETE FROM oidc_login_attempts WHERE state_hash=?',(state_hash,))
            if not row:
                raise DomainError(401,'State login OIDC tidak valid atau kedaluwarsa.')
            return dict(row)

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
            current = db.execute("SELECT name,role FROM users WHERE id=? AND active=1", (actor["id"],)).fetchone()
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
            self._record_audit(db,dict(current)|{'id':actor['id']},key,operation,payload,result)
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?)",
                       (actor["id"], key, fingerprint, json.dumps(result), now()))
            return result

    def _record_audit(self, db, actor, key, operation, payload, result):
        root=operation.split(':',1)[0]
        subject_type=root.replace('-reverse','').replace('-decision','').replace('-','_')
        subject_id=''
        subject_reference=''
        if isinstance(result,dict):
            subject_id=str(result.get('id') or '')
            subject_reference=str(result.get('reference') or result.get('bundle_reference')
                                  or result.get('sku') or result.get('code') or '')
        if not subject_id and ':' in operation:
            subject_id=operation.split(':',1)[1]
        changes=json.dumps(audit_value(payload),ensure_ascii=False,separators=(',',':'),default=str)
        outcome=json.dumps(audit_outcome(result),ensure_ascii=False,separators=(',',':'),default=str)
        db.execute('''INSERT INTO audit_events(id,category,operation,actor_id,actor_name,actor_role,
            subject_type,subject_id,subject_reference,request_key,changes_json,outcome_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(str(uuid4()),audit_category(operation),operation,
            actor['id'],actor['name'],actor['role'],subject_type,subject_id,subject_reference,key,
            changes,outcome,now()))

    @staticmethod
    def _audit_event(row):
        event=dict(row)
        event['changes']=json.loads(event.pop('changes_json'))
        event['outcome']=json.loads(event.pop('outcome_json'))
        return event

    def audit_event(self, event_id):
        with self.transaction() as db:
            row=db.execute('SELECT * FROM audit_events WHERE id=?',(event_id,)).fetchone()
            if not row:
                raise DomainError(404,'Audit event tidak ditemukan.')
            return self._audit_event(row)

    def audit_events(self, limit=50, before=None, category='all', actor_id='', query='',
                     start_date=None, end_date=None):
        if bool(start_date)!=bool(end_date):
            raise DomainError(422,'Tanggal awal dan akhir audit harus diisi bersama.')
        if start_date:
            if not 0 <= (end_date-start_date).days < 366:
                raise DomainError(422,'Rentang audit harus berurutan dan maksimal 366 hari.')
            jakarta=timezone(timedelta(hours=7))
            try:
                start=datetime.combine(start_date,time(),jakarta).astimezone(timezone.utc).isoformat()
                end=(datetime.combine(end_date,time(),jakarta)+timedelta(days=1)).astimezone(timezone.utc).isoformat()
            except (OverflowError,ValueError):
                raise DomainError(422,'Tanggal audit di luar jangkauan.')
        else:
            start=end=None
        params={'limit':limit+1,'before':before,'category':category,'actor_id':actor_id,
                'query':query.strip().casefold(),'start':start,'end':end}
        filters=''' WHERE (:before IS NULL OR sequence<:before)
            AND (:category='all' OR category=:category)
            AND (:actor_id='' OR actor_id=:actor_id)
            AND (:start IS NULL OR created_at>=:start) AND (:end IS NULL OR created_at<:end)
            AND (:query='' OR instr(lower(operation),:query)>0
                OR instr(lower(subject_reference),:query)>0 OR instr(lower(actor_name),:query)>0
                OR instr(lower(request_key),:query)>0 OR instr(lower(changes_json),:query)>0)'''
        count_filters=filters.replace('(:before IS NULL OR sequence<:before)','1=1',1)
        with self.transaction() as db:
            total=db.execute('SELECT COUNT(*) FROM audit_events'+count_filters,params).fetchone()[0]
            rows=[self._audit_event(row) for row in db.execute(
                'SELECT * FROM audit_events'+filters+' ORDER BY sequence DESC LIMIT :limit',params)]
            more=len(rows)>limit;rows=rows[:limit]
            return {'total':total,'items':rows,
                    'next_before':rows[-1]['sequence'] if more else None}

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

    def _jubelio_order_snapshot(self, db, batch_id, include_orders=True):
        row=db.execute('''SELECT b.*,r.status AS sync_status,r.records_read,r.records_written,
            r.external_cursor,r.error,r.reason,u.name AS actor_name FROM jubelio_order_snapshot_batches b
            JOIN integration_sync_runs r ON r.id=b.sync_run_id JOIN users u ON u.id=b.actor_id
            WHERE b.id=?''',(batch_id,)).fetchone()
        if not row:
            raise DomainError(404,'Snapshot order Jubelio tidak ditemukan.')
        record=dict(row)
        record['accepted_count']=db.execute('SELECT COUNT(*) FROM jubelio_order_snapshot_orders WHERE batch_id=?',
                                            (batch_id,)).fetchone()[0]
        record['rejected_count']=db.execute('SELECT COUNT(*) FROM jubelio_order_quarantine_records WHERE batch_id=?',
                                            (batch_id,)).fetchone()[0]
        if not include_orders:
            return record
        orders=[]
        for source in db.execute('''SELECT * FROM jubelio_order_snapshot_orders
            WHERE batch_id=? ORDER BY ordered_at DESC,sequence DESC''',(batch_id,)):
            order=dict(source)
            lines=[]
            for item in db.execute('''SELECT l.*,p.sku,p.name AS product_name,p.color,p.size
                FROM jubelio_order_snapshot_lines l JOIN products p ON p.id=l.product_id
                WHERE l.order_id=? ORDER BY p.sku,p.id''',(order['id'],)):
                line=dict(item);line['gross_revenue']=format(Decimal(line.pop('gross_revenue_minor'))/100,'.2f')
                lines.append(line)
            order['gross_revenue']=format(Decimal(order.pop('gross_revenue_minor'))/100,'.2f')
            order['total_quantity']=sum(line['quantity'] for line in lines);order['lines']=lines
            orders.append(order)
        quarantine=[]
        for source in db.execute('''SELECT * FROM jubelio_order_quarantine_records
            WHERE batch_id=? ORDER BY ordered_at DESC,external_order_reference COLLATE NOCASE''',(batch_id,)):
            item=dict(source);payload=json.loads(item.pop('payload_json'))
            item['lines']=payload['lines'];item['total_quantity']=sum(line['quantity'] for line in payload['lines'])
            item['gross_revenue']=format(sum((Decimal(line['gross_revenue']) for line in payload['lines']),Decimal()) ,'.2f')
            quarantine.append(item)
        record['orders']=orders;record['quarantine']=quarantine
        return record

    def import_jubelio_order_snapshot(self, payload, actor, key):
        def perform(db):
            accepted=[];rejected=[]
            for order in payload['orders']:
                mapped=[];issues=[]
                for line in order['lines']:
                    matches=db.execute('''SELECT e.product_id,e.external_id,e.external_sku
                        FROM product_external_mapping_events e WHERE e.system='jubelio' AND e.status='mapped'
                        AND e.sequence=(SELECT MAX(x.sequence) FROM product_external_mapping_events x
                            WHERE x.product_id=e.product_id AND x.system=e.system)
                        AND (e.external_id=? OR e.external_sku=? COLLATE NOCASE)''',
                        (line['external_id'],line['external_sku'])).fetchall()
                    exact=[row for row in matches if row['external_id']==line['external_id']
                           and row['external_sku'].casefold()==line['external_sku'].casefold()]
                    if len(exact)==1:
                        mapped.append((line,exact[0]['product_id']))
                    else:
                        issues.append('unmapped' if not matches else 'mapping_mismatch')
                if issues:
                    issue='mapping_mismatch' if 'mapping_mismatch' in issues else 'unmapped'
                    detail=(f'{len(issues)} baris order tidak memiliki pasangan identifier Jubelio yang aman.')
                    rejected.append((order,issue,detail))
                else:
                    accepted.append((order,mapped))
            run_id=str(uuid4());failed=bool(rejected)
            error=f'{len(rejected)} order Jubelio dikarantina.' if failed else ''
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,finished_at,
                records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,'jubelio','orders','failed' if failed else 'succeeded',
                payload['started_at'],payload['finished_at'],len(payload['orders']),len(accepted),
                payload['external_cursor'],error,payload['reason'],actor['id'],now()))
            batch_id=str(uuid4());created=now()
            db.execute('''INSERT INTO jubelio_order_snapshot_batches
                (id,sync_run_id,snapshot_at,actor_id,created_at) VALUES(?,?,?,?,?)''',
                (batch_id,run_id,payload['snapshot_at'],actor['id'],created))
            for order,lines in accepted:
                order_id=str(uuid4())
                total=sum(int(Decimal(line['gross_revenue'])*100) for line,_ in lines)
                db.execute('''INSERT INTO jubelio_order_snapshot_orders(id,batch_id,external_order_id,
                    external_order_reference,marketplace,status,ordered_at,gross_revenue_minor)
                    VALUES(?,?,?,?,?,?,?,?)''',(order_id,batch_id,order['external_order_id'],
                    order['external_order_reference'],order['marketplace'],order['status'],order['ordered_at'],total))
                for line,product_id in lines:
                    db.execute('''INSERT INTO jubelio_order_snapshot_lines(id,order_id,product_id,external_id,
                        external_sku,quantity,gross_revenue_minor) VALUES(?,?,?,?,?,?,?)''',(str(uuid4()),order_id,
                        product_id,line['external_id'],line['external_sku'],line['quantity'],
                        int(Decimal(line['gross_revenue'])*100)))
            for order,issue,detail in rejected:
                db.execute('''INSERT INTO jubelio_order_quarantine_records(id,batch_id,external_order_id,
                    external_order_reference,marketplace,status,ordered_at,payload_json,issue,detail)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''',(str(uuid4()),batch_id,order['external_order_id'],
                    order['external_order_reference'],order['marketplace'],order['status'],order['ordered_at'],
                    json.dumps(order,ensure_ascii=False,separators=(',',':')),issue,detail))
            return self._jubelio_order_snapshot(db,batch_id)
        return self._write(actor,('admin',),key,'jubelio-order-snapshot',payload,perform)

    def jubelio_order_snapshot(self, batch_id):
        with self.transaction() as db:
            return self._jubelio_order_snapshot(db,batch_id)

    def jubelio_order_snapshots(self, limit=100, before=None):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM jubelio_order_snapshot_batches
                WHERE (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',(before,before,limit)).fetchall()
            return [self._jubelio_order_snapshot(db,row['id'],False) for row in rows]

    def jubelio_order_summary(self):
        with self.transaction() as db:
            latest=db.execute('SELECT id FROM jubelio_order_snapshot_batches ORDER BY sequence DESC LIMIT 1').fetchone()
            if not latest:
                return {'snapshot':None,'summary':{'accepted_orders':0,'quarantined_orders':0,'units':0,
                    'gross_revenue':'0.00','pending':0,'processing':0,'completed':0,'cancelled':0},
                    'marketplaces':[],'orders':[],'quarantine':[]}
            snapshot=self._jubelio_order_snapshot(db,latest['id'])
        statuses={status:sum(order['status']==status for order in snapshot['orders'])
                  for status in ('pending','processing','completed','cancelled')}
        completed=[order for order in snapshot['orders'] if order['status']=='completed']
        groups={}
        for order in snapshot['orders']:
            group=groups.setdefault(order['marketplace'],{'marketplace':order['marketplace'],'orders':0,
                'units':0,'gross_revenue_minor':0})
            group['orders']+=1
            if order['status']=='completed':
                group['units']+=order['total_quantity'];group['gross_revenue_minor']+=int(Decimal(order['gross_revenue'])*100)
        marketplaces=[]
        for group in sorted(groups.values(),key=lambda row:row['marketplace'].casefold()):
            group['gross_revenue']=format(Decimal(group.pop('gross_revenue_minor'))/100,'.2f');marketplaces.append(group)
        summary={'accepted_orders':len(snapshot['orders']),'quarantined_orders':len(snapshot['quarantine']),
            'units':sum(order['total_quantity'] for order in completed),
            'gross_revenue':format(sum((Decimal(order['gross_revenue']) for order in completed),Decimal()),'.2f')}|statuses
        header={key:snapshot[key] for key in ('id','sequence','snapshot_at','sync_run_id','sync_status',
            'records_read','records_written','error','created_at')}
        return {'snapshot':header,'summary':summary,'marketplaces':marketplaces,
            'orders':snapshot['orders'],'quarantine':snapshot['quarantine']}

    def _jubelio_return_snapshot(self, db, batch_id, include_returns=True):
        row=db.execute('''SELECT b.*,r.status AS sync_status,r.records_read,r.records_written,
            r.external_cursor,r.error,r.reason,u.name AS actor_name FROM jubelio_return_snapshot_batches b
            JOIN integration_sync_runs r ON r.id=b.sync_run_id JOIN users u ON u.id=b.actor_id
            WHERE b.id=?''',(batch_id,)).fetchone()
        if not row:
            raise DomainError(404,'Snapshot retur Jubelio tidak ditemukan.')
        record=dict(row)
        record['accepted_count']=db.execute('SELECT COUNT(*) FROM jubelio_return_snapshot_records WHERE batch_id=?',
                                            (batch_id,)).fetchone()[0]
        record['rejected_count']=db.execute('SELECT COUNT(*) FROM jubelio_return_quarantine_records WHERE batch_id=?',
                                            (batch_id,)).fetchone()[0]
        if not include_returns:
            return record
        returns=[]
        for source in db.execute('''SELECT * FROM jubelio_return_snapshot_records
            WHERE batch_id=? ORDER BY updated_at DESC,sequence DESC''',(batch_id,)):
            item=dict(source);lines=[]
            for row in db.execute('''SELECT l.*,p.sku,p.name AS product_name,p.color,p.size
                FROM jubelio_return_snapshot_lines l JOIN products p ON p.id=l.product_id
                WHERE l.return_id=? ORDER BY p.sku,p.id''',(item['id'],)):
                lines.append(dict(row))
            item['refund_amount']=format(Decimal(item.pop('refund_amount_minor'))/100,'.2f')
            item['total_quantity']=sum(line['quantity'] for line in lines);item['lines']=lines
            returns.append(item)
        quarantine=[]
        for source in db.execute('''SELECT * FROM jubelio_return_quarantine_records
            WHERE batch_id=? ORDER BY updated_at DESC,external_return_reference COLLATE NOCASE''',(batch_id,)):
            item=dict(source);payload=json.loads(item.pop('payload_json'))
            item['external_order_id']=payload['external_order_id'];item['lines']=payload['lines']
            item['refund_amount']=payload['refund_amount']
            item['total_quantity']=sum(line['quantity'] for line in payload['lines']);quarantine.append(item)
        record['returns']=returns;record['quarantine']=quarantine
        return record

    def import_jubelio_return_snapshot(self, payload, actor, key):
        def perform(db):
            accepted=[];rejected=[]
            for record in payload['returns']:
                mapped=[];issues=[]
                for line in record['lines']:
                    matches=db.execute('''SELECT e.product_id,e.external_id,e.external_sku
                        FROM product_external_mapping_events e WHERE e.system='jubelio' AND e.status='mapped'
                        AND e.sequence=(SELECT MAX(x.sequence) FROM product_external_mapping_events x
                            WHERE x.product_id=e.product_id AND x.system=e.system)
                        AND (e.external_id=? OR e.external_sku=? COLLATE NOCASE)''',
                        (line['external_id'],line['external_sku'])).fetchall()
                    exact=[row for row in matches if row['external_id']==line['external_id']
                           and row['external_sku'].casefold()==line['external_sku'].casefold()]
                    if len(exact)==1:
                        mapped.append((line,exact[0]['product_id']))
                    else:
                        issues.append('unmapped' if not matches else 'mapping_mismatch')
                if issues:
                    issue='mapping_mismatch' if 'mapping_mismatch' in issues else 'unmapped'
                    rejected.append((record,issue,f'{len(issues)} baris retur tidak memiliki pasangan identifier Jubelio yang aman.'))
                else:
                    accepted.append((record,mapped))
            run_id=str(uuid4());failed=bool(rejected)
            error=f'{len(rejected)} retur Jubelio dikarantina.' if failed else ''
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,finished_at,
                records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,'jubelio','returns','failed' if failed else 'succeeded',
                payload['started_at'],payload['finished_at'],len(payload['returns']),len(accepted),
                payload['external_cursor'],error,payload['reason'],actor['id'],now()))
            batch_id=str(uuid4());created=now()
            db.execute('''INSERT INTO jubelio_return_snapshot_batches
                (id,sync_run_id,snapshot_at,actor_id,created_at) VALUES(?,?,?,?,?)''',
                (batch_id,run_id,payload['snapshot_at'],actor['id'],created))
            for record,lines in accepted:
                return_id=str(uuid4())
                db.execute('''INSERT INTO jubelio_return_snapshot_records(id,batch_id,external_return_id,
                    external_return_reference,external_order_id,external_order_reference,marketplace,status,
                    updated_at,refund_amount_minor) VALUES(?,?,?,?,?,?,?,?,?,?)''',(return_id,batch_id,
                    record['external_return_id'],record['external_return_reference'],record['external_order_id'],
                    record['external_order_reference'],record['marketplace'],record['status'],record['updated_at'],
                    int(Decimal(record['refund_amount'])*100)))
                for line,product_id in lines:
                    db.execute('''INSERT INTO jubelio_return_snapshot_lines(id,return_id,product_id,external_id,
                        external_sku,quantity) VALUES(?,?,?,?,?,?)''',(str(uuid4()),return_id,product_id,
                        line['external_id'],line['external_sku'],line['quantity']))
            for record,issue,detail in rejected:
                db.execute('''INSERT INTO jubelio_return_quarantine_records(id,batch_id,external_return_id,
                    external_return_reference,external_order_reference,marketplace,status,updated_at,payload_json,
                    issue,detail) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(str(uuid4()),batch_id,
                    record['external_return_id'],record['external_return_reference'],record['external_order_reference'],
                    record['marketplace'],record['status'],record['updated_at'],
                    json.dumps(record,ensure_ascii=False,separators=(',',':')),issue,detail))
            return self._jubelio_return_snapshot(db,batch_id)
        return self._write(actor,('admin',),key,'jubelio-return-snapshot',payload,perform)

    def jubelio_return_snapshot(self, batch_id):
        with self.transaction() as db:
            return self._jubelio_return_snapshot(db,batch_id)

    def jubelio_return_snapshots(self, limit=100, before=None):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM jubelio_return_snapshot_batches
                WHERE (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',(before,before,limit)).fetchall()
            return [self._jubelio_return_snapshot(db,row['id'],False) for row in rows]

    def jubelio_return_summary(self):
        with self.transaction() as db:
            latest=db.execute('SELECT id FROM jubelio_return_snapshot_batches ORDER BY sequence DESC LIMIT 1').fetchone()
            if not latest:
                return {'snapshot':None,'summary':{'accepted_returns':0,'quarantined_returns':0,
                    'received_units':0,'refunded_amount':'0.00','requested':0,'in_transit':0,'received':0,
                    'refunded':0,'rejected':0,'cancelled':0},'marketplaces':[],'products':[],
                    'returns':[],'quarantine':[]}
            snapshot=self._jubelio_return_snapshot(db,latest['id'])
        statuses={status:sum(item['status']==status for item in snapshot['returns'])
                  for status in ('requested','in_transit','received','refunded','rejected','cancelled')}
        received=[item for item in snapshot['returns'] if item['status'] in ('received','refunded')]
        refunded=[item for item in snapshot['returns'] if item['status']=='refunded']
        groups={};products={}
        for item in snapshot['returns']:
            group=groups.setdefault(item['marketplace'],{'marketplace':item['marketplace'],'returns':0,
                'received_units':0,'refunded_amount_minor':0})
            group['returns']+=1
            if item['status'] in ('received','refunded'):
                group['received_units']+=item['total_quantity']
                for line in item['lines']:
                    product=products.setdefault(line['product_id'],{key:line[key] for key in
                        ('product_id','sku','product_name','color','size')}|{'received_units':0})
                    product['received_units']+=line['quantity']
            if item['status']=='refunded':
                group['refunded_amount_minor']+=int(Decimal(item['refund_amount'])*100)
        marketplaces=[]
        for group in sorted(groups.values(),key=lambda row:row['marketplace'].casefold()):
            group['refunded_amount']=format(Decimal(group.pop('refunded_amount_minor'))/100,'.2f');marketplaces.append(group)
        summary={'accepted_returns':len(snapshot['returns']),'quarantined_returns':len(snapshot['quarantine']),
            'received_units':sum(item['total_quantity'] for item in received),
            'refunded_amount':format(sum((Decimal(item['refund_amount']) for item in refunded),Decimal()),'.2f')}|statuses
        header={key:snapshot[key] for key in ('id','sequence','snapshot_at','sync_run_id','sync_status',
            'records_read','records_written','error','created_at')}
        return {'snapshot':header,'summary':summary,'marketplaces':marketplaces,
            'products':sorted(products.values(),key=lambda row:(row['sku'],row['product_id'])),
            'returns':snapshot['returns'],'quarantine':snapshot['quarantine']}

    def _jubelio_listing_snapshot(self, db, batch_id, include_listings=True):
        row=db.execute('''SELECT b.*,r.status AS sync_status,r.records_read,r.records_written,
            r.external_cursor,r.error,r.reason,u.name AS actor_name FROM jubelio_listing_snapshot_batches b
            JOIN integration_sync_runs r ON r.id=b.sync_run_id JOIN users u ON u.id=b.actor_id
            WHERE b.id=?''',(batch_id,)).fetchone()
        if not row:
            raise DomainError(404,'Snapshot listing Jubelio tidak ditemukan.')
        record=dict(row)
        record['accepted_count']=db.execute('SELECT COUNT(*) FROM jubelio_listing_snapshot_records WHERE batch_id=?',
                                            (batch_id,)).fetchone()[0]
        record['rejected_count']=db.execute('SELECT COUNT(*) FROM jubelio_listing_quarantine_records WHERE batch_id=?',
                                            (batch_id,)).fetchone()[0]
        if not include_listings:
            return record
        listings=[]
        for source in db.execute('''SELECT l.*,p.sku,p.name AS product_name,p.color,p.size
            FROM jubelio_listing_snapshot_records l JOIN products p ON p.id=l.product_id
            WHERE l.batch_id=? ORDER BY l.marketplace COLLATE NOCASE,l.listing_reference COLLATE NOCASE,l.sequence''',
            (batch_id,)):
            item=dict(source);item['listed_price']=format(Decimal(item.pop('listed_price_minor'))/100,'.2f')
            listings.append(item)
        quarantine=[]
        for source in db.execute('''SELECT * FROM jubelio_listing_quarantine_records
            WHERE batch_id=? ORDER BY marketplace COLLATE NOCASE,listing_reference COLLATE NOCASE''',(batch_id,)):
            item=dict(source);payload=json.loads(item.pop('payload_json'))
            for name in ('external_id','external_sku','listing_title','listed_price'):
                item[name]=payload[name]
            quarantine.append(item)
        record['listings']=listings;record['quarantine']=quarantine
        return record

    def import_jubelio_listing_snapshot(self, payload, actor, key):
        def perform(db):
            accepted=[];rejected=[]
            for record in payload['listings']:
                matches=db.execute('''SELECT e.product_id,e.external_id,e.external_sku
                    FROM product_external_mapping_events e WHERE e.system='jubelio' AND e.status='mapped'
                    AND e.sequence=(SELECT MAX(x.sequence) FROM product_external_mapping_events x
                        WHERE x.product_id=e.product_id AND x.system=e.system)
                    AND (e.external_id=? OR e.external_sku=? COLLATE NOCASE)''',
                    (record['external_id'],record['external_sku'])).fetchall()
                exact=[row for row in matches if row['external_id']==record['external_id']
                       and row['external_sku'].casefold()==record['external_sku'].casefold()]
                if len(exact)==1:
                    accepted.append((record,exact[0]['product_id']))
                else:
                    issue='unmapped' if not matches else 'mapping_mismatch'
                    rejected.append((record,issue,'Listing tidak memiliki pasangan identifier Jubelio yang aman.'))
            run_id=str(uuid4());failed=bool(rejected)
            error=f'{len(rejected)} listing Jubelio dikarantina.' if failed else ''
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,finished_at,
                records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,'jubelio','listings','failed' if failed else 'succeeded',
                payload['started_at'],payload['finished_at'],len(payload['listings']),len(accepted),
                payload['external_cursor'],error,payload['reason'],actor['id'],now()))
            batch_id=str(uuid4());created=now()
            db.execute('''INSERT INTO jubelio_listing_snapshot_batches
                (id,sync_run_id,snapshot_at,actor_id,created_at) VALUES(?,?,?,?,?)''',
                (batch_id,run_id,payload['snapshot_at'],actor['id'],created))
            for record,product_id in accepted:
                db.execute('''INSERT INTO jubelio_listing_snapshot_records(id,batch_id,product_id,
                    external_listing_id,listing_reference,external_id,external_sku,marketplace,listing_title,
                    status,listed_price_minor,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(str(uuid4()),batch_id,
                    product_id,record['external_listing_id'],record['listing_reference'],record['external_id'],
                    record['external_sku'],record['marketplace'],record['listing_title'],record['status'],
                    int(Decimal(record['listed_price'])*100),record['updated_at']))
            for record,issue,detail in rejected:
                db.execute('''INSERT INTO jubelio_listing_quarantine_records(id,batch_id,external_listing_id,
                    listing_reference,marketplace,status,updated_at,payload_json,issue,detail)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''',(str(uuid4()),batch_id,record['external_listing_id'],
                    record['listing_reference'],record['marketplace'],record['status'],record['updated_at'],
                    json.dumps(record,ensure_ascii=False,separators=(',',':')),issue,detail))
            return self._jubelio_listing_snapshot(db,batch_id)
        return self._write(actor,('admin',),key,'jubelio-listing-snapshot',payload,perform)

    def jubelio_listing_snapshot(self, batch_id):
        with self.transaction() as db:
            return self._jubelio_listing_snapshot(db,batch_id)

    def jubelio_listing_snapshots(self, limit=100, before=None):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM jubelio_listing_snapshot_batches
                WHERE (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',(before,before,limit)).fetchall()
            return [self._jubelio_listing_snapshot(db,row['id'],False) for row in rows]

    def jubelio_listing_summary(self):
        with self.transaction() as db:
            latest=db.execute('SELECT id FROM jubelio_listing_snapshot_batches ORDER BY sequence DESC LIMIT 1').fetchone()
            if not latest:
                return {'snapshot':None,'summary':{'accepted_listings':0,'quarantined_listings':0,
                    'active_products':0,'active':0,'inactive':0,'draft':0,'blocked':0,
                    'min_active_price':None,'max_active_price':None},'marketplaces':[],
                    'listings':[],'quarantine':[]}
            snapshot=self._jubelio_listing_snapshot(db,latest['id'])
        statuses={status:sum(item['status']==status for item in snapshot['listings'])
                  for status in ('active','inactive','draft','blocked')}
        active=[item for item in snapshot['listings'] if item['status']=='active']
        groups={}
        for item in snapshot['listings']:
            group=groups.setdefault(item['marketplace'],{'marketplace':item['marketplace'],'listings':0,
                'active':0,'inactive':0,'draft':0,'blocked':0,'product_ids':set()})
            group['listings']+=1;group[item['status']]+=1
            if item['status']=='active': group['product_ids'].add(item['product_id'])
        marketplaces=[]
        for group in sorted(groups.values(),key=lambda row:row['marketplace'].casefold()):
            group['active_products']=len(group.pop('product_ids'));marketplaces.append(group)
        prices=[Decimal(item['listed_price']) for item in active]
        summary={'accepted_listings':len(snapshot['listings']),'quarantined_listings':len(snapshot['quarantine']),
            'active_products':len({item['product_id'] for item in active}),**statuses,
            'min_active_price':format(min(prices),'.2f') if prices else None,
            'max_active_price':format(max(prices),'.2f') if prices else None}
        header={name:snapshot[name] for name in ('id','sequence','snapshot_at','sync_run_id','sync_status',
            'records_read','records_written','error','created_at')}
        return {'snapshot':header,'summary':summary,'marketplaces':marketplaces,
            'listings':snapshot['listings'],'quarantine':snapshot['quarantine']}

    @staticmethod
    def _mekari_finance_period(row):
        record=dict(row)
        fields=('gross_revenue','sales_returns','cost_of_goods_sold','operating_expenses',
                'other_income','other_expenses','cash_balance','receivables_balance','payables_balance')
        for name in fields:
            record[name]=format(Decimal(record.pop(name+'_minor'))/100,'.2f')
        net_revenue=Decimal(record['gross_revenue'])-Decimal(record['sales_returns'])
        gross_profit=net_revenue-Decimal(record['cost_of_goods_sold'])
        net_profit=gross_profit-Decimal(record['operating_expenses'])+Decimal(record['other_income'])-Decimal(record['other_expenses'])
        net_liquidity=Decimal(record['cash_balance'])+Decimal(record['receivables_balance'])-Decimal(record['payables_balance'])
        record.update(net_revenue=format(net_revenue,'.2f'),gross_profit=format(gross_profit,'.2f'),
                      net_profit=format(net_profit,'.2f'),net_liquidity=format(net_liquidity,'.2f'))
        return record

    def _mekari_finance_snapshot(self, db, batch_id, include_periods=True):
        row=db.execute('''SELECT b.*,r.status AS sync_status,r.records_read,r.records_written,
            r.external_cursor,r.error,r.reason,u.name AS actor_name FROM mekari_finance_snapshot_batches b
            JOIN integration_sync_runs r ON r.id=b.sync_run_id JOIN users u ON u.id=b.actor_id
            WHERE b.id=?''',(batch_id,)).fetchone()
        if not row:
            raise DomainError(404,'Snapshot keuangan Mekari tidak ditemukan.')
        record=dict(row)
        record['period_count']=db.execute('SELECT COUNT(*) FROM mekari_finance_snapshot_periods WHERE batch_id=?',
                                          (batch_id,)).fetchone()[0]
        if include_periods:
            record['periods']=[self._mekari_finance_period(source) for source in db.execute('''
                SELECT * FROM mekari_finance_snapshot_periods WHERE batch_id=?
                ORDER BY period_end DESC,period_start DESC,sequence DESC''',(batch_id,))]
        return record

    def import_mekari_finance_snapshot(self, payload, actor, key):
        def perform(db):
            run_id=str(uuid4());created=now()
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,finished_at,
                records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,'mekari','finance_summary','succeeded',
                payload['started_at'],payload['finished_at'],len(payload['periods']),len(payload['periods']),
                payload['external_cursor'],'',payload['reason'],actor['id'],created))
            batch_id=str(uuid4())
            db.execute('''INSERT INTO mekari_finance_snapshot_batches
                (id,sync_run_id,snapshot_at,actor_id,created_at) VALUES(?,?,?,?,?)''',
                (batch_id,run_id,payload['snapshot_at'],actor['id'],created))
            for period in payload['periods']:
                values=[int(Decimal(period[name])*100) for name in ('gross_revenue','sales_returns',
                    'cost_of_goods_sold','operating_expenses','other_income','other_expenses','cash_balance',
                    'receivables_balance','payables_balance')]
                db.execute('''INSERT INTO mekari_finance_snapshot_periods(id,batch_id,source_report_id,
                    period_start,period_end,currency,gross_revenue_minor,sales_returns_minor,
                    cost_of_goods_sold_minor,operating_expenses_minor,other_income_minor,other_expenses_minor,
                    cash_balance_minor,receivables_balance_minor,payables_balance_minor)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(str(uuid4()),batch_id,period['source_report_id'],
                    period['period_start'],period['period_end'],period['currency'],*values))
            return self._mekari_finance_snapshot(db,batch_id)
        return self._write(actor,('admin',),key,'mekari-finance-snapshot',payload,perform)

    def mekari_finance_snapshot(self, batch_id):
        with self.transaction() as db:
            return self._mekari_finance_snapshot(db,batch_id)

    def mekari_finance_snapshots(self, limit=100, before=None):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM mekari_finance_snapshot_batches
                WHERE (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',(before,before,limit)).fetchall()
            return [self._mekari_finance_snapshot(db,row['id'],False) for row in rows]

    def mekari_finance_summary(self):
        with self.transaction() as db:
            latest=db.execute('SELECT id FROM mekari_finance_snapshot_batches ORDER BY sequence DESC LIMIT 1').fetchone()
            if not latest:
                return {'snapshot':None,'current':None,'periods':[]}
            snapshot=self._mekari_finance_snapshot(db,latest['id'])
        header={name:snapshot[name] for name in ('id','sequence','snapshot_at','sync_run_id','sync_status',
            'records_read','records_written','error','created_at')}
        return {'snapshot':header,'current':snapshot['periods'][0] if snapshot['periods'] else None,
                'periods':snapshot['periods']}

    @staticmethod
    def _mekari_payable_record(row, as_of):
        record=dict(row)
        original=Decimal(record.pop('original_amount_minor'))/100
        paid=Decimal(record.pop('paid_amount_minor'))/100
        outstanding=Decimal() if record['status']=='void' else original-paid
        remaining_days=(date.fromisoformat(record['due_date'])-date.fromisoformat(as_of)).days
        record.update(original_amount=format(original,'.2f'),paid_amount=format(paid,'.2f'),
                      outstanding_amount=format(outstanding,'.2f'),
                      overdue=outstanding>0 and remaining_days<0,
                      due_in_days=remaining_days if outstanding>0 else None)
        return record

    def _mekari_payable_snapshot(self, db, batch_id, include_payables=True):
        row=db.execute('''SELECT b.*,r.status AS sync_status,r.records_read,r.records_written,
            r.external_cursor,r.error,r.reason,u.name AS actor_name FROM mekari_payable_snapshot_batches b
            JOIN integration_sync_runs r ON r.id=b.sync_run_id JOIN users u ON u.id=b.actor_id
            WHERE b.id=?''',(batch_id,)).fetchone()
        if not row:
            raise DomainError(404,'Snapshot utang Mekari tidak ditemukan.')
        record=dict(row)
        record['payable_count']=db.execute('SELECT COUNT(*) FROM mekari_payable_snapshot_records WHERE batch_id=?',
                                           (batch_id,)).fetchone()[0]
        if include_payables:
            record['payables']=[self._mekari_payable_record(source,record['as_of']) for source in db.execute('''
                SELECT * FROM mekari_payable_snapshot_records WHERE batch_id=?
                ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'partially_paid' THEN 1 ELSE 2 END,
                due_date,reference COLLATE NOCASE,sequence''',(batch_id,))]
        return record

    def import_mekari_payable_snapshot(self, payload, actor, key):
        def perform(db):
            run_id=str(uuid4());created=now()
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,finished_at,
                records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,'mekari','payables','succeeded',
                payload['started_at'],payload['finished_at'],len(payload['payables']),len(payload['payables']),
                payload['external_cursor'],'',payload['reason'],actor['id'],created))
            batch_id=str(uuid4())
            db.execute('''INSERT INTO mekari_payable_snapshot_batches
                (id,sync_run_id,snapshot_at,as_of,actor_id,created_at) VALUES(?,?,?,?,?,?)''',
                (batch_id,run_id,payload['snapshot_at'],payload['as_of'],actor['id'],created))
            for payable in payload['payables']:
                db.execute('''INSERT INTO mekari_payable_snapshot_records(id,batch_id,external_payable_id,
                    reference,external_supplier_id,supplier_name,invoice_date,due_date,status,currency,
                    original_amount_minor,paid_amount_minor,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (str(uuid4()),batch_id,payable['external_payable_id'],payable['reference'],
                     payable['external_supplier_id'],payable['supplier_name'],payable['invoice_date'],
                     payable['due_date'],payable['status'],payable['currency'],
                     int(Decimal(payable['original_amount'])*100),int(Decimal(payable['paid_amount'])*100),
                     payable['updated_at']))
            return self._mekari_payable_snapshot(db,batch_id)
        return self._write(actor,('admin',),key,'mekari-payable-snapshot',payload,perform)

    def mekari_payable_snapshot(self, batch_id):
        with self.transaction() as db:
            return self._mekari_payable_snapshot(db,batch_id)

    def mekari_payable_snapshots(self, limit=100, before=None):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM mekari_payable_snapshot_batches
                WHERE (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',(before,before,limit)).fetchall()
            return [self._mekari_payable_snapshot(db,row['id'],False) for row in rows]

    def mekari_payables_summary(self):
        with self.transaction() as db:
            latest=db.execute('SELECT id FROM mekari_payable_snapshot_batches ORDER BY sequence DESC LIMIT 1').fetchone()
            if not latest:
                return {'snapshot':None,'summary':{'accepted_payables':0,'open':0,'partially_paid':0,
                    'paid':0,'void':0,'total_original':'0.00','total_paid':'0.00','total_outstanding':'0.00',
                    'overdue_count':0,'overdue_amount':'0.00','due_next_7_days_count':0,
                    'due_next_7_days_amount':'0.00'},'suppliers':[],'payables':[]}
            snapshot=self._mekari_payable_snapshot(db,latest['id'])
        active=[row for row in snapshot['payables'] if row['status']!='void']
        unpaid=[row for row in active if Decimal(row['outstanding_amount'])>0]
        overdue=[row for row in unpaid if row['overdue']]
        due_soon=[row for row in unpaid if 0<=row['due_in_days']<=7]
        statuses={status:sum(row['status']==status for row in snapshot['payables'])
                  for status in ('open','partially_paid','paid','void')}
        groups={}
        for row in snapshot['payables']:
            group=groups.setdefault(row['external_supplier_id'],{'external_supplier_id':row['external_supplier_id'],
                'supplier_name':row['supplier_name'],'invoices':0,'outstanding_invoices':0,
                'outstanding_minor':0,'overdue_invoices':0,'overdue_minor':0})
            group['invoices']+=1
            amount=int(Decimal(row['outstanding_amount'])*100)
            if amount:
                group['outstanding_invoices']+=1;group['outstanding_minor']+=amount
            if row['overdue']:
                group['overdue_invoices']+=1;group['overdue_minor']+=amount
        suppliers=[]
        for group in sorted(groups.values(),key=lambda row:(row['supplier_name'].casefold(),row['external_supplier_id'])):
            group['outstanding_amount']=format(Decimal(group.pop('outstanding_minor'))/100,'.2f')
            group['overdue_amount']=format(Decimal(group.pop('overdue_minor'))/100,'.2f');suppliers.append(group)
        total=lambda rows,name:format(sum((Decimal(row[name]) for row in rows),Decimal()),'.2f')
        summary={'accepted_payables':len(snapshot['payables']),**statuses,
            'total_original':total(active,'original_amount'),'total_paid':total(active,'paid_amount'),
            'total_outstanding':total(unpaid,'outstanding_amount'),'overdue_count':len(overdue),
            'overdue_amount':total(overdue,'outstanding_amount'),'due_next_7_days_count':len(due_soon),
            'due_next_7_days_amount':total(due_soon,'outstanding_amount')}
        header={name:snapshot[name] for name in ('id','sequence','snapshot_at','as_of','sync_run_id','sync_status',
            'records_read','records_written','error','created_at')}
        return {'snapshot':header,'summary':summary,'suppliers':suppliers,'payables':snapshot['payables']}

    @staticmethod
    def _mekari_receivable_record(row, as_of):
        record=dict(row)
        original=Decimal(record.pop('original_amount_minor'))/100
        received=Decimal(record.pop('received_amount_minor'))/100
        outstanding=Decimal() if record['status']=='void' else original-received
        remaining_days=(date.fromisoformat(record['due_date'])-date.fromisoformat(as_of)).days
        record.update(original_amount=format(original,'.2f'),received_amount=format(received,'.2f'),
                      outstanding_amount=format(outstanding,'.2f'),
                      overdue=outstanding>0 and remaining_days<0,
                      due_in_days=remaining_days if outstanding>0 else None)
        return record

    def _mekari_receivable_snapshot(self, db, batch_id, include_receivables=True):
        row=db.execute('''SELECT b.*,r.status AS sync_status,r.records_read,r.records_written,
            r.external_cursor,r.error,r.reason,u.name AS actor_name FROM mekari_receivable_snapshot_batches b
            JOIN integration_sync_runs r ON r.id=b.sync_run_id JOIN users u ON u.id=b.actor_id
            WHERE b.id=?''',(batch_id,)).fetchone()
        if not row:
            raise DomainError(404,'Snapshot piutang Mekari tidak ditemukan.')
        record=dict(row)
        record['receivable_count']=db.execute('SELECT COUNT(*) FROM mekari_receivable_snapshot_records WHERE batch_id=?',
                                              (batch_id,)).fetchone()[0]
        if include_receivables:
            record['receivables']=[self._mekari_receivable_record(source,record['as_of']) for source in db.execute('''
                SELECT * FROM mekari_receivable_snapshot_records WHERE batch_id=?
                ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'partially_paid' THEN 1 ELSE 2 END,
                due_date,reference COLLATE NOCASE,sequence''',(batch_id,))]
        return record

    def import_mekari_receivable_snapshot(self, payload, actor, key):
        def perform(db):
            run_id=str(uuid4());created=now()
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,finished_at,
                records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,'mekari','receivables','succeeded',
                payload['started_at'],payload['finished_at'],len(payload['receivables']),len(payload['receivables']),
                payload['external_cursor'],'',payload['reason'],actor['id'],created))
            batch_id=str(uuid4())
            db.execute('''INSERT INTO mekari_receivable_snapshot_batches
                (id,sync_run_id,snapshot_at,as_of,actor_id,created_at) VALUES(?,?,?,?,?,?)''',
                (batch_id,run_id,payload['snapshot_at'],payload['as_of'],actor['id'],created))
            for receivable in payload['receivables']:
                db.execute('''INSERT INTO mekari_receivable_snapshot_records(id,batch_id,external_receivable_id,
                    reference,external_customer_id,customer_name,invoice_date,due_date,status,currency,
                    original_amount_minor,received_amount_minor,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (str(uuid4()),batch_id,receivable['external_receivable_id'],receivable['reference'],
                     receivable['external_customer_id'],receivable['customer_name'],receivable['invoice_date'],
                     receivable['due_date'],receivable['status'],receivable['currency'],
                     int(Decimal(receivable['original_amount'])*100),int(Decimal(receivable['received_amount'])*100),
                     receivable['updated_at']))
            return self._mekari_receivable_snapshot(db,batch_id)
        return self._write(actor,('admin',),key,'mekari-receivable-snapshot',payload,perform)

    def mekari_receivable_snapshot(self, batch_id):
        with self.transaction() as db:
            return self._mekari_receivable_snapshot(db,batch_id)

    def mekari_receivable_snapshots(self, limit=100, before=None):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM mekari_receivable_snapshot_batches
                WHERE (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',(before,before,limit)).fetchall()
            return [self._mekari_receivable_snapshot(db,row['id'],False) for row in rows]

    def mekari_receivables_summary(self):
        with self.transaction() as db:
            latest=db.execute('SELECT id FROM mekari_receivable_snapshot_batches ORDER BY sequence DESC LIMIT 1').fetchone()
            if not latest:
                return {'snapshot':None,'summary':{'accepted_receivables':0,'open':0,'partially_paid':0,
                    'paid':0,'void':0,'total_original':'0.00','total_received':'0.00','total_outstanding':'0.00',
                    'overdue_count':0,'overdue_amount':'0.00','due_next_7_days_count':0,
                    'due_next_7_days_amount':'0.00'},'customers':[],'receivables':[]}
            snapshot=self._mekari_receivable_snapshot(db,latest['id'])
        active=[row for row in snapshot['receivables'] if row['status']!='void']
        unpaid=[row for row in active if Decimal(row['outstanding_amount'])>0]
        overdue=[row for row in unpaid if row['overdue']]
        due_soon=[row for row in unpaid if 0<=row['due_in_days']<=7]
        statuses={status:sum(row['status']==status for row in snapshot['receivables'])
                  for status in ('open','partially_paid','paid','void')}
        groups={}
        for row in snapshot['receivables']:
            group=groups.setdefault(row['external_customer_id'],{'external_customer_id':row['external_customer_id'],
                'customer_name':row['customer_name'],'invoices':0,'outstanding_invoices':0,
                'outstanding_minor':0,'overdue_invoices':0,'overdue_minor':0})
            group['invoices']+=1
            amount=int(Decimal(row['outstanding_amount'])*100)
            if amount:
                group['outstanding_invoices']+=1;group['outstanding_minor']+=amount
            if row['overdue']:
                group['overdue_invoices']+=1;group['overdue_minor']+=amount
        customers=[]
        for group in sorted(groups.values(),key=lambda row:(row['customer_name'].casefold(),row['external_customer_id'])):
            group['outstanding_amount']=format(Decimal(group.pop('outstanding_minor'))/100,'.2f')
            group['overdue_amount']=format(Decimal(group.pop('overdue_minor'))/100,'.2f');customers.append(group)
        total=lambda rows,name:format(sum((Decimal(row[name]) for row in rows),Decimal()),'.2f')
        summary={'accepted_receivables':len(snapshot['receivables']),**statuses,
            'total_original':total(active,'original_amount'),'total_received':total(active,'received_amount'),
            'total_outstanding':total(unpaid,'outstanding_amount'),'overdue_count':len(overdue),
            'overdue_amount':total(overdue,'outstanding_amount'),'due_next_7_days_count':len(due_soon),
            'due_next_7_days_amount':total(due_soon,'outstanding_amount')}
        header={name:snapshot[name] for name in ('id','sequence','snapshot_at','as_of','sync_run_id','sync_status',
            'records_read','records_written','error','created_at')}
        return {'snapshot':header,'summary':summary,'customers':customers,'receivables':snapshot['receivables']}

    @staticmethod
    def _mekari_payroll_period(row):
        record=dict(row)
        for name in ('gross_pay','employee_deductions','employer_contributions'):
            record[name]=format(Decimal(record.pop(name+'_minor'))/100,'.2f')
        net_pay=Decimal(record['gross_pay'])-Decimal(record['employee_deductions'])
        employer_cost=Decimal(record['gross_pay'])+Decimal(record['employer_contributions'])
        record.update(net_pay=format(net_pay,'.2f'),total_employer_cost=format(employer_cost,'.2f'))
        return record

    def _mekari_payroll_snapshot(self, db, batch_id, include_periods=True):
        row=db.execute('''SELECT b.*,r.status AS sync_status,r.records_read,r.records_written,
            r.external_cursor,r.error,r.reason,u.name AS actor_name FROM mekari_payroll_snapshot_batches b
            JOIN integration_sync_runs r ON r.id=b.sync_run_id JOIN users u ON u.id=b.actor_id
            WHERE b.id=?''',(batch_id,)).fetchone()
        if not row:
            raise DomainError(404,'Snapshot payroll Mekari tidak ditemukan.')
        record=dict(row)
        record['period_count']=db.execute('SELECT COUNT(*) FROM mekari_payroll_snapshot_periods WHERE batch_id=?',
                                          (batch_id,)).fetchone()[0]
        if include_periods:
            record['periods']=[self._mekari_payroll_period(source) for source in db.execute('''
                SELECT * FROM mekari_payroll_snapshot_periods WHERE batch_id=?
                ORDER BY period_end DESC,period_start DESC,sequence DESC''',(batch_id,))]
        return record

    def import_mekari_payroll_snapshot(self, payload, actor, key):
        def perform(db):
            run_id=str(uuid4());created=now()
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,finished_at,
                records_read,records_written,external_cursor,error,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(run_id,'mekari','payroll','succeeded',
                payload['started_at'],payload['finished_at'],len(payload['periods']),len(payload['periods']),
                payload['external_cursor'],'',payload['reason'],actor['id'],created))
            batch_id=str(uuid4())
            db.execute('''INSERT INTO mekari_payroll_snapshot_batches
                (id,sync_run_id,snapshot_at,actor_id,created_at) VALUES(?,?,?,?,?)''',
                (batch_id,run_id,payload['snapshot_at'],actor['id'],created))
            for period in payload['periods']:
                values=[int(Decimal(period[name])*100) for name in
                        ('gross_pay','employee_deductions','employer_contributions')]
                db.execute('''INSERT INTO mekari_payroll_snapshot_periods(id,batch_id,external_payroll_id,
                    period_start,period_end,status,currency,employee_count,gross_pay_minor,
                    employee_deductions_minor,employer_contributions_minor,payment_date,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(str(uuid4()),batch_id,period['external_payroll_id'],
                    period['period_start'],period['period_end'],period['status'],period['currency'],
                    period['employee_count'],*values,period['payment_date'],period['updated_at']))
            return self._mekari_payroll_snapshot(db,batch_id)
        return self._write(actor,('admin',),key,'mekari-payroll-snapshot',payload,perform)

    def mekari_payroll_snapshot(self, batch_id):
        with self.transaction() as db:
            return self._mekari_payroll_snapshot(db,batch_id)

    def mekari_payroll_snapshots(self, limit=100, before=None):
        with self.transaction() as db:
            rows=db.execute('''SELECT id FROM mekari_payroll_snapshot_batches
                WHERE (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',(before,before,limit)).fetchall()
            return [self._mekari_payroll_snapshot(db,row['id'],False) for row in rows]

    def mekari_payroll_summary(self):
        with self.transaction() as db:
            latest=db.execute('SELECT id FROM mekari_payroll_snapshot_batches ORDER BY sequence DESC LIMIT 1').fetchone()
            if not latest:
                return {'snapshot':None,'current':None,'status_counts':{'draft':0,'reviewing':0,
                    'approved':0,'paid':0,'cancelled':0},'periods':[]}
            snapshot=self._mekari_payroll_snapshot(db,latest['id'])
        statuses={status:sum(row['status']==status for row in snapshot['periods'])
                  for status in ('draft','reviewing','approved','paid','cancelled')}
        header={name:snapshot[name] for name in ('id','sequence','snapshot_at','sync_run_id','sync_status',
            'records_read','records_written','error','created_at')}
        return {'snapshot':header,'current':snapshot['periods'][0] if snapshot['periods'] else None,
                'status_counts':statuses,'periods':snapshot['periods']}

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
            (SELECT id FROM material_movements WHERE batch_id=b.id AND kind='receipt') AS receipt_id,
            (SELECT quantity_milli FROM material_movements WHERE batch_id=b.id AND kind='receipt') AS received_milli
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
        received = record.pop('received_milli')
        reserved = db.execute('SELECT COALESCE(SUM(quantity_milli),0) FROM material_reservation_events WHERE batch_id=?', (batch_id,)).fetchone()[0]
        own = db.execute('SELECT COALESCE(SUM(quantity_milli),0) FROM material_reservation_events WHERE batch_id=? AND order_id=?', (batch_id,order_id)).fetchone()[0]
        record.update({key:self._material_decimal(value) for key,value in dict(balance=balance,reserved=reserved,
                      available=balance-reserved,reserved_for_order=own,available_to_order=balance-reserved+own).items()})
        record['received_quantity'] = self._material_decimal(received)
        record['scan_code'] = material_batch_scan_code(record['id'])
        corrected = db.execute('SELECT 1 FROM material_movements WHERE reversal_of=?',
                               (record['receipt_id'],)).fetchone()
        record['status'] = 'corrected' if corrected else 'active'
        qc = db.execute('SELECT intake_id FROM qc_decisions WHERE batch_id=?', (batch_id,)).fetchone()
        record['qc_intake_id'] = qc['intake_id'] if qc else None
        return record

    def material_batch(self, batch_id):
        with self.transaction() as db:
            return self._material_batch(db, batch_id)

    def material_batch_traceability(self, batch_id, limit=100, before_time=None, before_event=None):
        if bool(before_time)!=bool(before_event):
            raise DomainError(422,'Cursor waktu dan event harus diisi bersama.')
        with self.transaction() as db:
            batch=self._material_batch(db,batch_id)
            # ponytail: assemble one batch in memory; move to a SQL event union when batches reach thousands of events.
            events=[]

            def add(event_type, record, quantity, unit, business_date, description, detail_action,
                    status='active', event_id=None, actor=None, reason=None, detail_id=None):
                actor=actor or record
                events.append({'event_type':event_type,'event_id':event_id or record['id'],
                    'object_id':record['id'],'detail_id':detail_id or record['id'],
                    'reference':record['reference'],'quantity':quantity,'unit':unit,
                    'business_date':business_date,'created_at':actor['created_at'],
                    'actor_name':actor['actor_name'],'reason':reason if reason is not None else record['reason'],
                    'description':description,'status':status,'detail_action':detail_action})

            def correction(event_type, record, reversal, quantity, unit, detail_action, detail_id=None):
                if reversal:
                    add(event_type,record,quantity,unit,None,'Membalik catatan '+record['reference'],
                        detail_action,'correction',record['id']+':correction',reversal,reversal['reason'],detail_id)

            movements=db.execute('''SELECT x.*,u.name AS actor_name,o.reference AS order_reference,
                original.kind AS original_kind,(SELECT id FROM material_movements WHERE reversal_of=x.id) AS reversed_by
                FROM material_movements x JOIN users u ON u.id=x.actor_id
                LEFT JOIN orders o ON o.id=x.order_id LEFT JOIN material_movements original ON original.id=x.reversal_of
                WHERE x.batch_id=?''',(batch_id,)).fetchall()
            for source in movements:
                row=dict(source);quantity=self._material_decimal(abs(row.pop('quantity_milli')))
                if row['kind']=='receipt':
                    event_type='material_receipt';reference=batch['reference'];business_date=batch['received_date']
                    description=f"Masuk {batch['location']} dari {batch['supplier']}"
                elif row['kind']=='issue':
                    event_type='material_issue';reference=row['order_reference'];business_date=None
                    description='Dikeluarkan ke order '+row['order_reference']
                else:
                    event_type='material_movement_correction';reference=row['order_reference'] or batch['reference'];business_date=None
                    description='Membalik '+('penerimaan batch' if row['original_kind']=='receipt' else 'pengeluaran bahan')
                row['reference']=reference
                status='correction' if row['kind']=='reversal' else 'corrected' if row['reversed_by'] else 'active'
                add(event_type,row,quantity,batch['unit'],business_date,description,'material-batch',status,
                    detail_id=batch_id)

            for source in db.execute('''SELECT e.*,o.reference AS order_reference,u.name AS actor_name
                FROM material_reservation_events e JOIN orders o ON o.id=e.order_id
                JOIN users u ON u.id=e.actor_id WHERE e.batch_id=?''',(batch_id,)):
                row=dict(source);quantity=self._material_decimal(abs(row.pop('quantity_milli')))
                labels={'reserve':('material_reservation','Direservasi untuk order ','active'),
                        'release':('material_reservation_release','Reservasi dilepas dari order ','released'),
                        'consume':('material_reservation_consumption','Reservasi dipakai oleh order ','consumed')}
                event_type,label,status=labels[row['kind']];row['reference']=row['order_reference']
                add(event_type,row,quantity,batch['unit'],None,label+row['order_reference'],
                    'material-batch',status,detail_id=batch_id)

            for source in db.execute('''SELECT c.*,o.reference AS order_reference,u.name AS actor_name,
                r.id AS cutting_run_id,r.reference AS cutting_reference,
                (SELECT id FROM material_consumption WHERE reversal_of=c.id) AS reversed_by
                FROM material_consumption c JOIN material_movements i ON i.id=c.issue_id
                JOIN orders o ON o.id=i.order_id JOIN users u ON u.id=c.actor_id
                LEFT JOIN material_consumption original ON original.id=c.reversal_of
                LEFT JOIN cutting_runs r ON r.consumption_id=COALESCE(original.id,c.id)
                WHERE i.batch_id=?''',(batch_id,)):
                row=dict(source);used=row.pop('used_milli');waste=row.pop('waste_milli')
                row['reference']=row['cutting_reference'] or row['order_reference']
                event_type='material_consumption_correction' if row['reversal_of'] else 'material_consumption'
                status='correction' if row['reversal_of'] else 'corrected' if row['reversed_by'] else 'active'
                description=('Membalik pemakaian' if row['reversal_of'] else
                    f"Terpakai {self._material_decimal(used)} + waste {self._material_decimal(waste)} {batch['unit']}")
                action='cutting-run' if row['cutting_run_id'] else 'material-batch'
                add(event_type,row,self._material_decimal(abs(used+waste)),batch['unit'],None,description,
                    action,status,detail_id=row['cutting_run_id'] or batch_id)

            run_ids=db.execute('''SELECT r.id FROM cutting_runs r JOIN material_consumption c ON c.id=r.consumption_id
                JOIN material_movements i ON i.id=c.issue_id WHERE i.batch_id=?''',(batch_id,)).fetchall()
            for run_row in run_ids:
                run=self._cutting_run(db,run_row['id'],False)
                add('cutting_run',run,run['total_output'],'pcs',None,
                    f"Bahan {run['used']} {batch['unit']} + waste {run['waste']} {batch['unit']} menjadi {run['total_output']} pcs",
                    'cutting-run','corrected' if run['reversal'] else 'active')
                correction('cutting_run_correction',run,run['reversal'],run['total_output'],'pcs','cutting-run')
                for bundle_row in db.execute('SELECT id FROM bundles WHERE cutting_run_id=?',(run['id'],)):
                    bundle=self._bundle(db,bundle_row['id'])
                    add('bundle',bundle,bundle['quantity'],'pcs',None,
                        f"{bundle['sku']} ukuran {bundle['size']} dari {run['reference']}",'bundle',bundle['status'])
                    correction('bundle_correction',bundle,bundle['reversal'],bundle['quantity'],'pcs','bundle')
                    for handoff_row in db.execute('SELECT id FROM bundle_handoffs WHERE bundle_id=?',(bundle['id'],)):
                        handoff=self._bundle_handoff(db,handoff_row['id'])
                        handoff_record=dict(handoff,reference=bundle['reference'],reason=handoff['reason'],
                                            actor_name=handoff['sender_name'])
                        add('bundle_handoff',handoff_record,bundle['quantity'],'pcs',None,
                            f"{handoff['from_location']} menuju {handoff['to_location']}",'bundle-handoffs',
                            handoff['status'],detail_id=bundle['id'])
                        if handoff['accepted_at']:
                            actor={'created_at':handoff['accepted_at'],'actor_name':handoff['receiver_name']}
                            add('bundle_handoff_acceptance',handoff_record,bundle['quantity'],'pcs',None,
                                'Diterima di '+handoff['to_location'],'bundle-handoffs','received',
                                handoff['id']+':acceptance',actor,handoff['acceptance_reason'],bundle['id'])
                        if handoff['cancelled_at']:
                            actor={'created_at':handoff['cancelled_at'],'actor_name':handoff['cancellation_actor_name']}
                            add('bundle_handoff_cancellation',handoff_record,bundle['quantity'],'pcs',None,
                                'Handoff dibatalkan','bundle-handoffs','cancelled',handoff['id']+':cancellation',
                                actor,handoff['cancellation_reason'],bundle['id'])
                    for job_row in db.execute('SELECT id FROM sewing_jobs WHERE bundle_id=?',(bundle['id'],)):
                        job=self._sewing_job(db,job_row['id'])
                        add('sewing_job',job,job['quantity_out'],'pcs',job['sent_date'],
                            f"{job['assignment_type']} ke {job['assignee']}",'sewing-job',job['status'])
                        if job['result']:
                            result=job['result']
                            add('sewing_result',job,job['quantity_out'],'pcs',result['returned_date'],
                                f"Selesai {result['completed_quantity']}, defect {result['defect_quantity']}, missing {result['missing_quantity']}",
                                'sewing-job','corrected' if job['reversal'] else 'completed',job['id']+':result',
                                result,result['reason'])
                        correction('sewing_job_correction',job,job['reversal'],job['quantity_out'],'pcs','sewing-job')
                        for finishing_row in db.execute('SELECT id FROM finishing_records WHERE job_id=?',(job['id'],)):
                            finishing=self._finishing_record(db,finishing_row['id'])
                            add('finishing',finishing,finishing['quantity'],'pcs',finishing['completed_date'],
                                'Checklist finishing lengkap','finishing-record',finishing['status'])
                            correction('finishing_correction',finishing,finishing['reversal'],
                                       finishing['quantity'],'pcs','finishing-record')
                            for qc_row in db.execute('SELECT id FROM final_qc_records WHERE finishing_record_id=?',(finishing['id'],)):
                                qc=self._final_qc_record(db,qc_row['id'])
                                add('final_qc',qc,qc['inspected_quantity'],'pcs',qc['inspection_date'],
                                    f"Pass {qc['accepted_quantity']}, rework {qc['rework_quantity']}, reject {qc['reject_quantity']}",
                                    'final-qc-record',qc['status'])
                                correction('final_qc_correction',qc,qc['reversal'],qc['inspected_quantity'],
                                           'pcs','final-qc-record')
                                for receipt_row in db.execute('SELECT id FROM finished_goods_receipts WHERE final_qc_record_id=?',(qc['id'],)):
                                    receipt=self._finished_goods_receipt(db,receipt_row['id'])
                                    add('finished_goods_receipt',receipt,receipt['received_quantity'],'pcs',receipt['received_date'],
                                        f"{receipt['sku']}: {receipt['sellable_quantity']} sellable + {receipt['hold_quantity']} hold di {receipt['location']}",
                                        'finished-goods-receipt',receipt['status'])
                                    correction('finished_goods_receipt_correction',receipt,receipt['reversal'],
                                               receipt['received_quantity'],'pcs','finished-goods-receipt')

            events.sort(key=lambda row:(row['created_at'],row['event_id']),reverse=True)
            total=len(events)
            if before_time:
                events=[row for row in events if (row['created_at'],row['event_id'])<(before_time,before_event)]
            more=len(events)>limit;events=events[:limit]
            summary={key:batch[key] for key in ('id','reference','status','code','name','unit','supplier','location',
                'received_date','received_quantity','balance','reserved','available','scan_code','purchase_order_id',
                'purchase_order_reference','qc_intake_id')}
            return {'batch':summary,'total':total,'limit':limit,'events':events,
                    'next_before':{'before_time':events[-1]['created_at'],'before_event':events[-1]['event_id']}
                    if more else None}

    def scan_material_batch(self, code):
        value=code.strip()
        prefix='BEELOFT:MATERIAL-BATCH:'
        with self.transaction() as db:
            if value.upper().startswith(prefix):
                batch_id=value[len(prefix):]
                row=db.execute('SELECT id FROM material_batches WHERE id=? COLLATE NOCASE',(batch_id,)).fetchone()
            else:
                row=db.execute('SELECT id FROM material_batches WHERE reference=? COLLATE NOCASE',(value,)).fetchone()
            if not row:
                raise DomainError(404,'Batch bahan dari hasil scan tidak ditemukan.')
            return self._material_batch(db,row['id'])

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
        record['scan_code']=bundle_scan_code(record['id'])
        custody=db.execute('''SELECT h.to_location FROM bundle_handoffs h
            JOIN bundle_handoff_acceptances a ON a.handoff_id=h.id WHERE h.bundle_id=?
            ORDER BY h.sequence DESC LIMIT 1''',(bundle_id,)).fetchone()
        record['custody_location']=custody['to_location'] if custody else 'Cutting'
        pending=db.execute('''SELECT h.id FROM bundle_handoffs h WHERE h.bundle_id=?
            AND NOT EXISTS(SELECT 1 FROM bundle_handoff_acceptances a WHERE a.handoff_id=h.id)
            AND NOT EXISTS(SELECT 1 FROM bundle_handoff_cancellations c WHERE c.handoff_id=h.id)
            ORDER BY h.sequence DESC LIMIT 1''',(bundle_id,)).fetchone()
        record['pending_handoff']=self._bundle_handoff(db,pending['id']) if pending else None
        record['handoff_count']=db.execute('SELECT COUNT(*) FROM bundle_handoffs WHERE bundle_id=?',
                                            (bundle_id,)).fetchone()[0]
        return record

    def bundle(self, bundle_id):
        with self.transaction() as db:
            return self._bundle(db,bundle_id)

    def scan_bundle(self, code):
        value=code.strip()
        prefix='BEELOFT:BUNDLE:'
        with self.transaction() as db:
            if value.upper().startswith(prefix):
                bundle_id=value[len(prefix):]
                row=db.execute('SELECT id FROM bundles WHERE id=? COLLATE NOCASE',(bundle_id,)).fetchone()
            else:
                row=db.execute('SELECT id FROM bundles WHERE reference=? COLLATE NOCASE',(value,)).fetchone()
            if not row:
                raise DomainError(404,'Bundle dari hasil scan tidak ditemukan.')
            return self._bundle(db,row['id'])

    @staticmethod
    def _bundle_handoff(db, handoff_id):
        row=db.execute('''SELECT h.*,b.reference AS bundle_reference,b.quantity,p.sku,p.size,
            o.id AS order_id,o.reference AS order_reference,s.name AS sender_name,s.role AS sender_role,
            a.receiver_id,a.reason AS acceptance_reason,a.created_at AS accepted_at,
            receiver.name AS receiver_name,receiver.role AS receiver_role,
            c.actor_id AS cancellation_actor_id,c.reason AS cancellation_reason,
            c.created_at AS cancelled_at,canceller.name AS cancellation_actor_name
            FROM bundle_handoffs h JOIN bundles b ON b.id=h.bundle_id
            JOIN cutting_runs r ON r.id=b.cutting_run_id JOIN orders o ON o.id=r.order_id
            JOIN movements m ON m.id=b.output_movement_id JOIN order_lines l ON l.id=m.line_id
            JOIN products p ON p.id=l.product_id JOIN users s ON s.id=h.sender_id
            LEFT JOIN bundle_handoff_acceptances a ON a.handoff_id=h.id
            LEFT JOIN users receiver ON receiver.id=a.receiver_id
            LEFT JOIN bundle_handoff_cancellations c ON c.handoff_id=h.id
            LEFT JOIN users canceller ON canceller.id=c.actor_id WHERE h.id=?''',(handoff_id,)).fetchone()
        if not row:
            raise DomainError(404,'Serah-terima bundle tidak ditemukan.')
        record=dict(row)
        record['status']='received' if record['accepted_at'] else 'cancelled' if record['cancelled_at'] else 'pending'
        return record

    def bundle_handoffs(self, bundle_id, limit=100, before=None):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM bundles WHERE id=?',(bundle_id,)).fetchone():
                raise DomainError(404,'Bundle tidak ditemukan.')
            ids=db.execute('''SELECT id FROM bundle_handoffs WHERE bundle_id=?
                AND (? IS NULL OR sequence<?) ORDER BY sequence DESC LIMIT ?''',
                (bundle_id,before,before,limit)).fetchall()
            return [self._bundle_handoff(db,row['id']) for row in ids]

    def create_bundle_handoff(self, bundle_id, payload, actor, key):
        def perform(db):
            bundle=self._bundle(db,bundle_id)
            if bundle['status']!='active':
                raise DomainError(409,'Bundle sudah dikoreksi.')
            if bundle['pending_handoff']:
                raise DomainError(409,'Bundle masih menunggu penerimaan handoff sebelumnya.')
            if bundle['custody_location'].casefold()==payload['to_location'].casefold():
                raise DomainError(422,'Tujuan handoff harus berbeda dari lokasi bundle sekarang.')
            handoff_id=str(uuid4())
            db.execute('''INSERT INTO bundle_handoffs(id,bundle_id,from_location,to_location,reason,
                sender_id,created_at) VALUES(?,?,?,?,?,?,?)''',(handoff_id,bundle_id,
                bundle['custody_location'],payload['to_location'],payload['reason'],actor['id'],now()))
            return self._bundle_handoff(db,handoff_id)
        return self._write(actor,('admin','operator'),key,'bundle-handoff:'+bundle_id,payload,perform)

    def accept_bundle_handoff(self, handoff_id, payload, actor, key):
        def perform(db):
            handoff=self._bundle_handoff(db,handoff_id)
            if handoff['status']!='pending':
                raise DomainError(409,'Serah-terima bundle sudah diputuskan.')
            if handoff['sender_id']==actor['id']:
                raise DomainError(409,'Penerima harus memakai akun yang berbeda dari pengirim.')
            db.execute('''INSERT INTO bundle_handoff_acceptances(handoff_id,receiver_id,reason,created_at)
                VALUES(?,?,?,?)''',(handoff_id,actor['id'],payload['reason'],now()))
            return self._bundle_handoff(db,handoff_id)
        return self._write(actor,('admin','operator'),key,'bundle-handoff-acceptance:'+handoff_id,
                           payload,perform)

    def cancel_bundle_handoff(self, handoff_id, payload, actor, key):
        def perform(db):
            handoff=self._bundle_handoff(db,handoff_id)
            if handoff['status']!='pending':
                raise DomainError(409,'Hanya serah-terima pending yang dapat dibatalkan.')
            db.execute('''INSERT INTO bundle_handoff_cancellations(handoff_id,actor_id,reason,created_at)
                VALUES(?,?,?,?)''',(handoff_id,actor['id'],payload['reason'],now()))
            return self._bundle_handoff(db,handoff_id)
        return self._write(actor,('admin',),key,'bundle-handoff-cancellation:'+handoff_id,
                           payload,perform)

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
            if bundle['pending_handoff']:
                raise DomainError(409,'Batalkan atau terima handoff pending sebelum mengoreksi bundle.')
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
        record['scan_code']=finished_goods_scan_code(record['id'])
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

    def finished_goods_traceability(self, receipt_id, limit=100, before_time=None, before_event=None):
        if bool(before_time)!=bool(before_event):
            raise DomainError(422,'Cursor waktu dan event harus diisi bersama.')
        with self.transaction() as db:
            receipt=self._finished_goods_receipt(db,receipt_id)
            # ponytail: one lot is assembled in memory; use a SQL event union if lot histories outgrow this view.
            events=[]

            def add(event_type, record, quantity, business_date, description, detail_action,
                    status='active', event_id=None, actor=None, reason=None):
                actor=actor or record
                events.append({'event_type':event_type,
                    'event_id':event_id or record['id'],'object_id':record['id'],
                    'reference':record['reference'],'quantity':quantity,
                    'business_date':business_date,'created_at':actor['created_at'],
                    'actor_name':actor['actor_name'],'reason':reason if reason is not None else record['reason'],
                    'description':description,'status':status,'detail_action':detail_action,
                    'scanned_code':record.get('scanned_code') or record.get('scanned_sku')})

            def correction(event_type, record, reversal, quantity, detail_action):
                if reversal:
                    add(event_type,record,quantity,None,
                        'Membalik catatan '+record['reference'],detail_action,'correction',
                        record['id']+':correction',reversal,reversal['reason'])

            add('finished_goods_receipt',receipt,receipt['received_quantity'],receipt['received_date'],
                f"{receipt['sellable_quantity']} sellable + {receipt['hold_quantity']} hold masuk {receipt['location']}",
                'finished-goods-receipt',receipt['status'])
            correction('finished_goods_receipt_correction',receipt,receipt['reversal'],
                       receipt['received_quantity'],'finished-goods-receipt')

            for row in db.execute('SELECT id FROM warehouse_movements WHERE receipt_id=?',(receipt_id,)):
                movement=self._warehouse_movement(db,row['id'])
                add('warehouse_movement',movement,movement['quantity'],movement['moved_date'],
                    f"{movement['from_location']} ({movement['from_status']}) → {movement['to_location']} ({movement['to_status']})",
                    'warehouse-movement',movement['status'])
                correction('warehouse_movement_correction',movement,movement['reversal'],
                           movement['quantity'],'warehouse-movement')

            for row in db.execute('SELECT id FROM marketplace_reservations WHERE receipt_id=?',(receipt_id,)):
                reservation=self._marketplace_reservation(db,row['id'])
                add('marketplace_reservation',reservation,reservation['quantity'],reservation['reserved_date'],
                    f"{reservation['marketplace']} · order {reservation['external_order_reference']} · {reservation['location']}",
                    'marketplace-reservation',reservation['status'])
                if reservation['release']:
                    release=reservation['release']
                    add('marketplace_reservation_release',reservation,reservation['quantity'],release['released_date'],
                        'Melepaskan reservasi '+reservation['reference'],'marketplace-reservation','released',
                        reservation['id']+':release',release,release['reason'])
                for pick_row in db.execute('SELECT id FROM marketplace_picks WHERE reservation_id=?',(reservation['id'],)):
                    pick=self._marketplace_pick(db,pick_row['id'])
                    add('marketplace_pick',pick,pick['quantity'],pick['picked_date'],
                        f"{reservation['reference']} · {pick['location']} → {pick['staging_location']}",
                        'marketplace-pick',pick['status'])
                    correction('marketplace_pick_correction',pick,pick['reversal'],pick['quantity'],'marketplace-pick')
                    for pack_row in db.execute('SELECT id FROM marketplace_packs WHERE pick_id=?',(pick['id'],)):
                        pack=self._marketplace_pack(db,pack_row['id'])
                        add('marketplace_pack',pack,pack['quantity'],pack['packed_date'],
                            f"{pick['reference']} · {pack['staging_location']} · picked menjadi packed",
                            'marketplace-pack',pack['status'])
                        correction('marketplace_pack_correction',pack,pack['reversal'],pack['quantity'],'marketplace-pack')
                        for shipment_row in db.execute('SELECT id FROM marketplace_shipments WHERE pack_id=?',(pack['id'],)):
                            shipment=self._marketplace_shipment(db,shipment_row['id'])
                            add('marketplace_shipment',shipment,shipment['quantity'],shipment['shipped_date'],
                                f"{pack['reference']} · {shipment['staging_location']} → {shipment['carrier']} · resi {shipment['tracking_number']}",
                                'marketplace-shipment',shipment['status'])
                            correction('marketplace_shipment_correction',shipment,shipment['reversal'],
                                       shipment['quantity'],'marketplace-shipment')
                            for return_row in db.execute('SELECT id FROM marketplace_returns WHERE shipment_id=?',(shipment['id'],)):
                                returned=self._marketplace_return(db,return_row['id'])
                                add('marketplace_return',returned,returned['quantity'],returned['returned_date'],
                                    f"{shipment['reference']} · {returned['return_location']} · {returned['stock_status']} · {returned['return_reason']}",
                                    'marketplace-return',returned['status'])
                                correction('marketplace_return_correction',returned,returned['reversal'],
                                           returned['quantity'],'marketplace-return')

            for row in db.execute('SELECT id FROM finished_goods_adjustments WHERE receipt_id=?',(receipt_id,)):
                adjustment=self._finished_goods_adjustment(db,row['id'])
                delta=adjustment['quantity_delta']
                add('finished_goods_adjustment',adjustment,delta,adjustment['adjusted_date'],
                    f"{adjustment['location']} · {adjustment['stock_status']} · selisih {'+' if delta>0 else ''}{delta}",
                    'finished-goods-adjustment',adjustment['status'])
                correction('finished_goods_adjustment_correction',adjustment,adjustment['reversal'],
                           delta,'finished-goods-adjustment')

            for row in db.execute('SELECT id FROM finished_goods_stock_counts WHERE receipt_id=?',(receipt_id,)):
                count=self._finished_goods_stock_count(db,row['id'])
                add('finished_goods_stock_count',count,count['counted_quantity'],count['counted_date'],
                    f"{count['location']} · {count['stock_status']} · sistem {count['expected_quantity']} → fisik {count['counted_quantity']}",
                    'finished-goods-stock-count',count['status'])
                correction('finished_goods_stock_count_correction',count,count['reversal'],
                           count['counted_quantity'],'finished-goods-stock-count')

            events.sort(key=lambda row:(row['created_at'],row['event_id']),reverse=True)
            total=len(events)
            if before_time:
                events=[row for row in events if (row['created_at'],row['event_id'])<(before_time,before_event)]
            more=len(events)>limit
            events=events[:limit]
            summary={key:receipt[key] for key in ('id','reference','status','sku','product_name','color','size',
                'order_id','order_reference','received_quantity','location','received_date','scan_code',
                'final_qc_record_id','final_qc_reference','finishing_record_id','finishing_reference',
                'job_id','sewing_reference','bundle_id','bundle_reference','batch_id','batch_reference')}
            summary['inventory']=receipt['inventory']
            return {'receipt':summary,'total':total,'limit':limit,'events':events,
                    'next_before':{'before_time':events[-1]['created_at'],'before_event':events[-1]['event_id']}
                    if more else None}

    def scan_finished_goods_receipt(self, code):
        value=code.strip()
        prefix='BEELOFT:FINISHED-GOODS:'
        with self.transaction() as db:
            if value.upper().startswith(prefix):
                receipt_id=value[len(prefix):]
                row=db.execute('SELECT id FROM finished_goods_receipts WHERE id=? COLLATE NOCASE',
                               (receipt_id,)).fetchone()
            else:
                row=db.execute('SELECT id FROM finished_goods_receipts WHERE reference=? COLLATE NOCASE',
                               (value,)).fetchone()
            if not row:
                raise DomainError(404,'Penerimaan barang jadi dari hasil scan tidak ditemukan.')
            return self._finished_goods_receipt(db,row['id'])

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
            if payload['scanned_code'].casefold() not in (receipt['sku'].casefold(),
                                                          receipt['scan_code'].casefold()):
                raise DomainError(422,'SKU atau QR lot hasil scan tidak cocok dengan penerimaan barang jadi.')
            movement_id=str(uuid4())
            db.execute('''INSERT INTO warehouse_movements(id,reference,receipt_id,scanned_code,kind,from_location,
                to_location,from_status,to_status,quantity,moved_date,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(movement_id,payload['reference'],receipt_id,
                payload['scanned_code'],payload['kind'],payload['from_location'],payload['to_location'],from_status,
                to_status,payload['quantity'],payload['moved_date'],payload['reason'],actor['id'],now()))
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
        record['receipt_scan_code']=source['scan_code']
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
            if payload['scanned_code'].casefold() not in (reservation['sku'].casefold(),
                                                          reservation['receipt_scan_code'].casefold()):
                raise DomainError(422,'SKU atau QR lot hasil scan tidak cocok dengan reservasi marketplace.')
            pick_id=str(uuid4())
            db.execute('''INSERT INTO marketplace_picks(id,reference,reservation_id,scanned_code,quantity,
                staging_location,picked_date,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (pick_id,payload['reference'],reservation_id,payload['scanned_code'],payload['quantity'],
                 payload['staging_location'],payload['picked_date'],payload['reason'],actor['id'],now()))
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

    def return_insights(self, as_of, window_days=90, query='', marketplace='', limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        start_date=as_of_date-timedelta(days=window_days-1)
        params={'as_of':as_of_date.isoformat(),'start':start_date.isoformat(),
                'query':query.strip().casefold(),'marketplace':marketplace.strip()}
        with self.transaction() as db:
            rows=[dict(row) for row in db.execute('''WITH active_returns AS (
                SELECT t.shipment_id,SUM(t.quantity) AS returned_quantity,
                    SUM(CASE WHEN t.return_reason='too_small' THEN t.quantity ELSE 0 END) AS too_small_quantity,
                    SUM(CASE WHEN t.return_reason='too_big' THEN t.quantity ELSE 0 END) AS too_big_quantity,
                    SUM(CASE WHEN t.return_reason='wrong_item' THEN t.quantity ELSE 0 END) AS wrong_item_quantity,
                    SUM(CASE WHEN t.return_reason='defect' THEN t.quantity ELSE 0 END) AS defect_quantity,
                    SUM(CASE WHEN t.return_reason='color_mismatch' THEN t.quantity ELSE 0 END) AS color_mismatch_quantity,
                    SUM(CASE WHEN t.return_reason='other' THEN t.quantity ELSE 0 END) AS other_quantity,
                    MAX(t.returned_date) AS latest_returned_date
                FROM marketplace_returns t WHERE t.returned_date<=:as_of
                  AND NOT EXISTS(SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
                GROUP BY t.shipment_id
            )
            SELECT product.id AS product_id,product.sku,product.name,product.color,product.size,
                m.marketplace,COUNT(*) AS shipment_count,SUM(s.quantity) AS shipped_quantity,
                SUM(COALESCE(t.returned_quantity,0)) AS returned_quantity,
                SUM(COALESCE(t.too_small_quantity,0)) AS too_small_quantity,
                SUM(COALESCE(t.too_big_quantity,0)) AS too_big_quantity,
                SUM(COALESCE(t.wrong_item_quantity,0)) AS wrong_item_quantity,
                SUM(COALESCE(t.defect_quantity,0)) AS defect_quantity,
                SUM(COALESCE(t.color_mismatch_quantity,0)) AS color_mismatch_quantity,
                SUM(COALESCE(t.other_quantity,0)) AS other_quantity,
                MAX(t.latest_returned_date) AS latest_returned_date
            FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
            JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
            JOIN finished_goods_receipts x ON x.id=m.receipt_id
            JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
            JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
            JOIN movements source ON source.id=b.output_movement_id JOIN order_lines l ON l.id=source.line_id
            JOIN products product ON product.id=l.product_id LEFT JOIN active_returns t ON t.shipment_id=s.id
            WHERE s.shipped_date BETWEEN :start AND :as_of
              AND (:marketplace='' OR m.marketplace=:marketplace COLLATE NOCASE)
              AND (:query='' OR instr(lower(product.sku),:query)>0 OR instr(lower(product.name),:query)>0
                OR instr(lower(product.color),:query)>0 OR instr(lower(product.size),:query)>0)
              AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
            GROUP BY product.id,product.sku,product.name,product.color,product.size,m.marketplace''',params)]
        for row in rows:
            row['return_rate']=format((Decimal(row['returned_quantity'])/row['shipped_quantity']*100).quantize(
                Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
            row['sizing_quantity']=row['too_small_quantity']+row['too_big_quantity']
            row['product_page_quantity']=row['wrong_item_quantity']+row['color_mismatch_quantity']
            row['reason_quantities']={reason:row.pop(reason+'_quantity') for reason in
                ('too_small','too_big','wrong_item','defect','color_mismatch','other')}
        rows.sort(key=lambda row:(-row['returned_quantity'],-Decimal(row['return_rate']),
                                  row['sku'].casefold(),row['marketplace'].casefold(),row['product_id']))
        shipped=sum(row['shipped_quantity'] for row in rows)
        returned=sum(row['returned_quantity'] for row in rows)
        summary={'groups':len(rows),'skus':len({row['product_id'] for row in rows}),
            'marketplaces':len({row['marketplace'].casefold() for row in rows}),
            'shipment_count':sum(row['shipment_count'] for row in rows),'shipped_quantity':shipped,
            'returned_quantity':returned,'return_rate':format((Decimal(returned)/shipped*100).quantize(
                Decimal('.01'),rounding=ROUND_HALF_UP),'.2f') if shipped else '0.00',
            'sizing_quantity':sum(row['sizing_quantity'] for row in rows),
            'product_page_quantity':sum(row['product_page_quantity'] for row in rows),
            'defect_quantity':sum(row['reason_quantities']['defect'] for row in rows),
            'other_quantity':sum(row['reason_quantities']['other'] for row in rows)}
        return {'as_of':as_of_date.isoformat(),'window_days':window_days,'period_start':start_date.isoformat(),
            'query':query.strip(),'marketplace':marketplace.strip() or None,'total':len(rows),
            'limit':limit,'offset':offset,'summary':summary,
            'reason_groups':{'sizing':['too_small','too_big'],
                'product_page':['wrong_item','color_mismatch'],'quality':['defect'],'other':['other']},
            'items':rows[offset:offset+limit]}

    def size_demand_insights(self, as_of, window_days=28, lookahead_days=30, query='', marketplace='',
                             limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        forecast=self.demand_forecast(as_of_date,window_days,lookahead_days,'',marketplace,
                                      1_000_000_000,0)
        inventory={row['product_id']:row for row in self.finished_goods_inventory(1_000_000_000,0)}
        grouped={}
        for row in forecast['items']:
            key=(row['name'].casefold(),row['color'].casefold())
            grouped.setdefault(key,[]).append(row)
        term=query.strip().casefold()
        families=[]
        for grouped_rows in grouped.values():
            rows=[row for row in grouped_rows if row['size'].strip()]
            rows.sort(key=lambda row:(row['size'].casefold(),row['sku'].casefold(),row['id']))
            if (len({row['size'].casefold() for row in rows})<2
                    or term and not any(term in str(row[field]).casefold()
                        for row in grouped_rows for field in ('sku','name','color','size'))):
                continue
            previous_values=sorted({row['previous_net_demand'] for row in rows
                                    if row['previous_net_demand']>0},reverse=True)
            recent_values=sorted({row['recent_net_demand'] for row in rows
                                  if row['recent_net_demand']>0},reverse=True)
            previous_ranks={value:index+1 for index,value in enumerate(previous_values)}
            recent_ranks={value:index+1 for index,value in enumerate(recent_values)}
            recent_total=sum(row['recent_net_demand'] for row in rows)
            size_rows=[]
            covers=[]
            for row in rows:
                stock=inventory.get(row['id'],{})
                available=stock.get('available_quantity',0)
                rate=Decimal(row['forecast_daily_rate'])
                cover=Decimal(available)/rate if rate else None
                if cover is not None:
                    covers.append(cover)
                    projected=(as_of_date+timedelta(days=int(cover.to_integral_value(
                        rounding=ROUND_CEILING)))).isoformat()
                else:
                    projected=None
                previous_rank=previous_ranks.get(row['previous_net_demand'])
                recent_rank=recent_ranks.get(row['recent_net_demand'])
                size_rows.append({'product_id':row['id'],'sku':row['sku'],'size':row['size'],
                    'available_quantity':available,'sellable_quantity':stock.get('sellable_quantity',0),
                    'reserved_quantity':stock.get('reserved_quantity',0),
                    'previous_net_demand':row['previous_net_demand'],
                    'recent_net_demand':row['recent_net_demand'],
                    'forecast_daily_rate':row['forecast_daily_rate'],
                    'recent_demand_share':format((Decimal(row['recent_net_demand'])/recent_total*100).quantize(
                        Decimal('.01'),rounding=ROUND_HALF_UP),'.2f') if recent_total else '0.00',
                    'previous_demand_rank':previous_rank,'recent_demand_rank':recent_rank,
                    'consistent_demand_leader':previous_rank==1 and recent_rank==1,
                    'days_of_cover':format(cover.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
                        if cover is not None else None,
                    'projected_stockout_date':projected,'risk_rank':None,'risk_status':'no_observed_demand'})
            cover_ranks={value:index+1 for index,value in enumerate(sorted(set(covers)))}
            for item,row in zip(size_rows,rows):
                rate=Decimal(row['forecast_daily_rate'])
                if not rate:
                    continue
                cover=Decimal(item['available_quantity'])/rate
                item['risk_rank']=cover_ranks[cover]
                item['risk_status']='out_of_stock' if item['available_quantity']<=0 else (
                    'within_lookahead' if cover<=lookahead_days else 'later')
            first=[row for row in size_rows if row['risk_rank']==1]
            if not first:
                status='no_observed_demand'
            elif any(row['risk_status']=='out_of_stock' for row in first):
                status='out_of_stock'
            elif any(row['risk_status']=='within_lookahead' for row in first):
                status='within_lookahead'
            else:
                status='later'
            size_rows.sort(key=lambda row:(row['risk_rank'] is None,row['risk_rank'] or 0,
                                           row['size'].casefold(),row['sku'].casefold()))
            families.append({'name':rows[0]['name'],'color':rows[0]['color'],'size_count':len(size_rows),
                'risk_status':status,'first_stockout_sizes':[row['size'] for row in first],
                'first_stockout_date':min((row['projected_stockout_date'] for row in first
                                           if row['projected_stockout_date']),default=None),
                'consistent_leader_sizes':[row['size'] for row in size_rows
                                           if row['consistent_demand_leader']],
                'sizes':size_rows})
        severity={'out_of_stock':0,'within_lookahead':1,'later':2,'no_observed_demand':3}
        families.sort(key=lambda row:(severity[row['risk_status']],row['first_stockout_date'] or '9999-12-31',
                                      row['name'].casefold(),row['color'].casefold()))
        size_rows=[size for family in families for size in family['sizes']]
        first_dates=[family['first_stockout_date'] for family in families if family['first_stockout_date']]
        summary={'families':len(families),'size_variants':len(size_rows),
            'families_out_of_stock':sum(row['risk_status']=='out_of_stock' for row in families),
            'families_within_lookahead':sum(row['risk_status']=='within_lookahead' for row in families),
            'sizes_out_of_stock':sum(row['risk_status']=='out_of_stock' for row in size_rows),
            'consistent_demand_leaders':sum(row['consistent_demand_leader'] for row in size_rows),
            'earliest_projected_stockout_date':min(first_dates,default=None)}
        return {'as_of':as_of_date.isoformat(),'window_days':window_days,'lookahead_days':lookahead_days,
            'history_start':forecast['history_start'],'previous_period_end':forecast['previous_period_end'],
            'recent_period_start':forecast['recent_period_start'],'query':query.strip(),
            'marketplace':marketplace.strip() or None,'method':'weighted_two_window_demand_and_current_stock',
            'stock_scope':'all_marketplaces_current_internal_inventory','total':len(families),
            'limit':limit,'offset':offset,'summary':summary,'items':families[offset:offset+limit]}

    def dead_stock_insights(self, as_of, inactivity_days=90, query='', marketplace='',
                            status='dead_stock_candidate', limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        period_start=as_of_date-timedelta(days=inactivity_days-1)
        with self.transaction() as db:
            lots=[dict(row) for row in db.execute('''WITH sellable AS (
                SELECT receipt_id,SUM(quantity) AS quantity FROM finished_goods_stock_ledger
                WHERE stock_status='sellable' GROUP BY receipt_id
            ), reserved AS (
                SELECT receipt_id,SUM(quantity) AS quantity FROM finished_goods_reserved_stock
                GROUP BY receipt_id
            )
            SELECT l.product_id,x.id AS receipt_id,x.reference AS receipt_reference,x.received_date,
                s.quantity-COALESCE(r.quantity,0) AS available_quantity
            FROM finished_goods_receipts x JOIN final_qc_records q ON q.id=x.final_qc_record_id
            JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
            JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
            JOIN order_lines l ON l.id=source.line_id JOIN sellable s ON s.receipt_id=x.id
            LEFT JOIN reserved r ON r.receipt_id=x.id
            WHERE s.quantity-COALESCE(r.quantity,0)>0''')]
            sales=[dict(row) for row in db.execute('''WITH active_returns AS (
                SELECT t.shipment_id,SUM(t.quantity) AS quantity FROM marketplace_returns t
                WHERE t.returned_date<=? AND NOT EXISTS(
                    SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
                GROUP BY t.shipment_id
            )
            SELECT l.product_id,s.shipped_date,s.quantity,m.marketplace,
                COALESCE(t.quantity,0) AS returned_quantity
            FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
            JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
            JOIN finished_goods_receipts x ON x.id=m.receipt_id
            JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
            JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
            JOIN movements source ON source.id=b.output_movement_id JOIN order_lines l ON l.id=source.line_id
            LEFT JOIN active_returns t ON t.shipment_id=s.id
            WHERE s.shipped_date<=? AND (?='' OR m.marketplace=? COLLATE NOCASE)
              AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
            ORDER BY s.shipped_date,s.sequence''',(as_of_date.isoformat(),as_of_date.isoformat(),
                marketplace.strip(),marketplace.strip()))]
        lots_by_product={}
        for lot in lots:
            lots_by_product.setdefault(lot['product_id'],[]).append(lot)
        sales_by_product={}
        for sale in sales:
            sales_by_product.setdefault(sale['product_id'],[]).append(sale)
        term=query.strip().casefold()
        inventory=[row for row in self.finished_goods_inventory(1_000_000_000,0)
                   if row['available_quantity']>0 and (not term or any(term in str(row[field]).casefold()
                       for field in ('sku','name','color','size')))]
        items=[]
        for stock in inventory:
            product_lots=lots_by_product.get(stock['product_id'],[])
            receipt_dates=sorted(lot['received_date'] for lot in product_lots)
            oldest=receipt_dates[0] if receipt_dates else None
            newest=receipt_dates[-1] if receipt_dates else None
            age=max((as_of_date-date.fromisoformat(oldest)).days,0) if oldest else 0
            product_sales=sales_by_product.get(stock['product_id'],[])
            recent=[row for row in product_sales if row['shipped_date']>=period_start.isoformat()]
            recent_shipped=sum(row['quantity'] for row in recent)
            recent_returned=sum(row['returned_quantity'] for row in recent)
            recent_net=recent_shipped-recent_returned
            net_sales=[row for row in product_sales if row['quantity']-row['returned_quantity']>0]
            last_shipped=max((row['shipped_date'] for row in product_sales),default=None)
            last_net=max((row['shipped_date'] for row in net_sales),default=None)
            if recent_net>0:
                item_status='moving'
            elif age>=inactivity_days:
                item_status='dead_stock_candidate'
            else:
                item_status='aging_no_sales'
            rate=(Decimal(recent_net)/inactivity_days).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)
            cover=(Decimal(stock['available_quantity'])/rate if rate else None)
            items.append({key:stock[key] for key in ('product_id','sku','name','color','size')} | {
                'status':item_status,'available_quantity':stock['available_quantity'],
                'sellable_quantity':stock['sellable_quantity'],'reserved_quantity':stock['reserved_quantity'],
                'active_lot_count':len(product_lots),'oldest_available_receipt_date':oldest,
                'newest_available_receipt_date':newest,'oldest_stock_age_days':age,
                'recent_shipped_quantity':recent_shipped,'recent_returned_quantity':recent_returned,
                'recent_net_demand':recent_net,'recent_daily_rate':format(rate,'.4f'),
                'days_of_cover':format(cover.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
                    if cover is not None else None,
                'last_shipped_date':last_shipped,'last_net_sale_date':last_net,
                'days_since_last_net_sale':max((as_of_date-date.fromisoformat(last_net)).days,0)
                    if last_net else None})
        severity={'dead_stock_candidate':0,'aging_no_sales':1,'moving':2}
        items.sort(key=lambda row:(severity[row['status']],-row['oldest_stock_age_days'],
                                   -row['available_quantity'],row['sku'].casefold(),row['product_id']))
        candidates=[row for row in items if row['status']=='dead_stock_candidate']
        aging=[row for row in items if row['status']=='aging_no_sales']
        moving=[row for row in items if row['status']=='moving']
        summary={'products_with_available_stock':len(items),
            'available_quantity':sum(row['available_quantity'] for row in items),
            'dead_stock_candidates':len(candidates),
            'dead_stock_quantity':sum(row['available_quantity'] for row in candidates),
            'aging_no_sales_products':len(aging),
            'aging_no_sales_quantity':sum(row['available_quantity'] for row in aging),
            'moving_products':len(moving),'moving_quantity':sum(row['available_quantity'] for row in moving),
            'oldest_candidate_receipt_date':min((row['oldest_available_receipt_date'] for row in candidates
                                                 if row['oldest_available_receipt_date']),default=None)}
        filtered=items if status=='all' else [row for row in items if row['status']==status]
        return {'as_of':as_of_date.isoformat(),'inactivity_days':inactivity_days,
            'period_start':period_start.isoformat(),'query':query.strip(),
            'marketplace':marketplace.strip() or None,'status':status,
            'definition':'available_stock_aged_without_recent_net_demand',
            'stock_scope':'current_internal_sellable_available_inventory',
            'total':len(filtered),'limit':limit,'offset':offset,'summary':summary,
            'items':filtered[offset:offset+limit]}

    def stock_adjustment_insights(self, as_of, window_days=30, quantity_threshold=5,
                                  percentage_threshold=20, repeat_threshold=3, query='', location='',
                                  stock_status='all', source='all', record_status='all',
                                  classification='flagged', limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        period_start=as_of_date-timedelta(days=window_days-1)
        with self.transaction() as db:
            records=[dict(row) for row in db.execute('''SELECT a.id,a.sequence,a.reference,a.receipt_id,
                a.location,a.stock_status,a.quantity_delta,a.adjusted_date,a.reason,a.stock_count_id,
                a.created_at,u.name AS actor_name,x.reference AS receipt_reference,x.received_date,
                x.sellable_quantity+x.hold_quantity AS received_quantity,p.id AS product_id,p.sku,
                p.name AS product_name,p.color,p.size,o.id AS order_id,o.reference AS order_reference,
                c.reference AS stock_count_reference,r.reason AS reversal_reason,
                r.created_at AS reversed_at,ru.name AS reversal_actor_name
            FROM finished_goods_adjustments a JOIN users u ON u.id=a.actor_id
            JOIN finished_goods_receipts x ON x.id=a.receipt_id
            JOIN final_qc_records q ON q.id=x.final_qc_record_id
            JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
            JOIN bundles b ON b.id=j.bundle_id JOIN cutting_runs run ON run.id=b.cutting_run_id
            JOIN orders o ON o.id=run.order_id JOIN movements movement ON movement.id=b.output_movement_id
            JOIN order_lines l ON l.id=movement.line_id JOIN products p ON p.id=l.product_id
            LEFT JOIN finished_goods_stock_counts c ON c.id=a.stock_count_id
            LEFT JOIN finished_goods_adjustment_reversals r ON r.adjustment_id=a.id
            LEFT JOIN users ru ON ru.id=r.actor_id
            WHERE a.adjusted_date BETWEEN ? AND ? ORDER BY a.adjusted_date DESC,a.sequence DESC''',
                (period_start.isoformat(),as_of_date.isoformat()))]
        buckets={}
        for row in records:
            key=(row['product_id'],row['location'].casefold(),row['stock_status'])
            buckets.setdefault(key,[]).append(row)
        items=[]
        for row in records:
            key=(row['product_id'],row['location'].casefold(),row['stock_status'])
            peers=buckets[key]
            absolute=abs(row['quantity_delta'])
            share=(Decimal(absolute)*100/row['received_quantity']).quantize(
                Decimal('.01'),rounding=ROUND_HALF_UP) if row['received_quantity'] else Decimal('0')
            flags=[]
            if absolute>=quantity_threshold: flags.append('large_quantity')
            if share>=percentage_threshold: flags.append('large_receipt_share')
            if len(peers)>=repeat_threshold: flags.append('repeated_bucket')
            if row['reversal_reason'] is not None: flags.append('corrected_record')
            classification_value='high' if any(flag in flags for flag in
                ('large_quantity','large_receipt_share')) else 'review' if flags else 'normal'
            item={key:row[key] for key in ('id','sequence','reference','receipt_id','receipt_reference',
                'received_date','product_id','sku','product_name','color','size','order_id','order_reference',
                'location','stock_status','quantity_delta','adjusted_date','reason','actor_name','created_at',
                'stock_count_id','stock_count_reference')} | {
                'record_status':'corrected' if row['reversal_reason'] is not None else 'active',
                'source':'stock_count' if row['stock_count_id'] else 'manual',
                'direction':'increase' if row['quantity_delta']>0 else 'decrease',
                'absolute_quantity':absolute,'received_quantity':row['received_quantity'],
                'receipt_share_percent':format(share,'.2f'),'bucket_adjustment_count':len(peers),
                'bucket_absolute_quantity':sum(abs(peer['quantity_delta']) for peer in peers),
                'classification':classification_value,'flags':flags,
                'reversal':{'reason':row['reversal_reason'],'actor_name':row['reversal_actor_name'],
                    'created_at':row['reversed_at']} if row['reversal_reason'] is not None else None}
            items.append(item)
        term=query.strip().casefold();place=location.strip().casefold()
        scoped=[row for row in items if
            (not term or any(term in str(row[field]).casefold() for field in
                ('reference','sku','product_name','color','size','receipt_reference','order_reference','reason')))
            and (not place or place in row['location'].casefold())
            and (stock_status=='all' or row['stock_status']==stock_status)
            and (source=='all' or row['source']==source)
            and (record_status=='all' or row['record_status']==record_status)]
        priority={'high':0,'review':1,'normal':2}
        scoped.sort(key=lambda row:(priority[row['classification']],
                    -date.fromisoformat(row['adjusted_date']).toordinal(),-row['sequence']))
        flagged=[row for row in scoped if row['classification']!='normal']
        repeated={ (row['product_id'],row['location'].casefold(),row['stock_status']) for row in scoped
                   if 'repeated_bucket' in row['flags'] }
        summary={'adjustment_count':len(scoped),'flagged_adjustments':len(flagged),
            'high_risk_adjustments':sum(row['classification']=='high' for row in scoped),
            'review_adjustments':sum(row['classification']=='review' for row in scoped),
            'normal_adjustments':sum(row['classification']=='normal' for row in scoped),
            'active_adjustments':sum(row['record_status']=='active' for row in scoped),
            'corrected_adjustments':sum(row['record_status']=='corrected' for row in scoped),
            'manual_adjustments':sum(row['source']=='manual' for row in scoped),
            'stock_count_adjustments':sum(row['source']=='stock_count' for row in scoped),
            'absolute_quantity':sum(row['absolute_quantity'] for row in scoped),
            'flagged_absolute_quantity':sum(row['absolute_quantity'] for row in flagged),
            'repeated_buckets':len(repeated)}
        if classification=='flagged': filtered=flagged
        elif classification=='all': filtered=scoped
        else: filtered=[row for row in scoped if row['classification']==classification]
        return {'as_of':as_of_date.isoformat(),'period_start':period_start.isoformat(),
            'window_days':window_days,'quantity_threshold':quantity_threshold,
            'percentage_threshold':percentage_threshold,'repeat_threshold':repeat_threshold,
            'query':query.strip(),'location':location.strip() or None,'stock_status':stock_status,
            'source':source,'record_status':record_status,'classification':classification,
            'definition':'large_repeated_or_corrected_finished_goods_adjustment',
            'status_scope':'current_correction_status_for_adjustments_in_business_date_period',
            'total':len(filtered),'limit':limit,'offset':offset,'summary':summary,
            'items':filtered[offset:offset+limit]}

    def supplier_performance_insights(self, as_of, window_days=90, query='', status='attention',
                                      limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        period_start=as_of_date-timedelta(days=window_days-1)
        with self.transaction() as db:
            purchase_orders=[]
            for order_id, in db.execute('SELECT id FROM purchase_orders ORDER BY sequence'):
                order=self._purchase_order(db,order_id)
                if (order['approval_status']!='approved' or order['status']=='cancelled'
                        or not period_start.isoformat()<=order['expected_date']<=as_of_date.isoformat()):
                    continue
                purchase_orders.append(order)
        suppliers={}
        for order in purchase_orders:
            supplier=order['supplier']
            item=suppliers.setdefault(order['supplier_id'],{'supplier_id':order['supplier_id'],
                'supplier_code':supplier['code'],'supplier_name':supplier['name'],
                'purchase_orders':[],'ordered':{},'received':{},'quality':{}})
            active_intakes=[row for row in order['qc_intakes'] if not row['cancellation']]
            arrival_dates=[row['received_date'] for row in active_intakes]
            arrival_dates.extend(row['received_date'] for row in order['receipts'] if not row['reversed_by'])
            first_arrival=min(arrival_dates,default=None)
            delay=(date.fromisoformat(first_arrival)-date.fromisoformat(order['expected_date'])).days \
                if first_arrival else None
            po_item={'id':order['id'],'reference':order['reference'],'expected_date':order['expected_date'],
                'first_arrival_date':first_arrival,'first_arrival_delay_days':delay,'status':order['status'],
                'fulfillment':order['fulfillment']}
            item['purchase_orders'].append(po_item)
            for line in order['lines']:
                unit=line['unit']
                item['ordered'][unit]=item['ordered'].get(unit,Decimal('0'))+Decimal(line['quantity'])
                item['received'][unit]=item['received'].get(unit,Decimal('0'))+Decimal(line['received'])
            for intake in active_intakes:
                quality=item['quality'].setdefault(intake['unit'],{'intake_count':0,'arrived':Decimal('0'),
                    'accepted':Decimal('0'),'rejected':Decimal('0'),'held':Decimal('0')})
                quality['intake_count']+=1
                for field in ('quantity','accepted','rejected','held'):
                    quality['arrived' if field=='quantity' else field]+=Decimal(intake[field])
        term=query.strip().casefold();items=[]
        for item in suppliers.values():
            orders=item['purchase_orders']
            arrived=[row for row in orders if row['first_arrival_date']]
            on_time=[row for row in arrived if row['first_arrival_delay_days']<=0]
            late=[row for row in arrived if row['first_arrival_delay_days']>0]
            overdue_no_arrival=[row for row in orders if not row['first_arrival_date']
                                and row['expected_date']<as_of_date.isoformat()]
            incomplete_due=[row for row in orders if row['fulfillment']!='received'
                            and row['expected_date']<as_of_date.isoformat()]
            closed_shortfall=[row for row in orders if row['status']=='closed'
                              and row['fulfillment']!='received']
            quality=[]
            for unit,values in sorted(item['quality'].items()):
                arrived_quantity=values['arrived']
                usable=(values['accepted']*100/arrived_quantity).quantize(
                    Decimal('.01'),rounding=ROUND_HALF_UP) if arrived_quantity else Decimal('0')
                rejected=(values['rejected']*100/arrived_quantity).quantize(
                    Decimal('.01'),rounding=ROUND_HALF_UP) if arrived_quantity else Decimal('0')
                quality.append({'unit':unit,'intake_count':values['intake_count'],
                    'arrived':format(arrived_quantity,'.3f'),'accepted':format(values['accepted'],'.3f'),
                    'rejected':format(values['rejected'],'.3f'),'held':format(values['held'],'.3f'),
                    'usable_rate':format(usable,'.2f'),'reject_rate':format(rejected,'.2f')})
            flags=[]
            if overdue_no_arrival: flags.append('overdue_no_arrival')
            if late: flags.append('late_first_arrival')
            if incomplete_due: flags.append('overdue_incomplete')
            if closed_shortfall: flags.append('closed_shortfall')
            if any(Decimal(row['rejected'])>0 for row in quality): flags.append('quality_reject')
            if any(Decimal(row['held'])>0 for row in quality): flags.append('quality_hold')
            classification='attention' if flags else 'healthy'
            delays=[row['first_arrival_delay_days'] for row in arrived]
            result={key:item[key] for key in ('supplier_id','supplier_code','supplier_name')} | {
                'status':classification,'flags':flags,'purchase_order_count':len(orders),
                'arrived_purchase_orders':len(arrived),'on_time_first_arrivals':len(on_time),
                'late_first_arrivals':len(late),'overdue_no_arrival':len(overdue_no_arrival),
                'overdue_incomplete_purchase_orders':len(incomplete_due),
                'closed_shortfall_purchase_orders':len(closed_shortfall),
                'average_first_arrival_delay_days':format(Decimal(sum(delays))/len(delays),'.2f')
                    if delays else None,'maximum_first_arrival_delay_days':max(delays,default=None),
                'ordered_by_unit':[{'unit':unit,'quantity':format(quantity,'.3f')}
                                   for unit,quantity in sorted(item['ordered'].items())],
                'received_by_unit':[{'unit':unit,'quantity':format(quantity,'.3f')}
                                    for unit,quantity in sorted(item['received'].items())],
                'quality_by_unit':quality,'purchase_orders':sorted(orders,
                    key=lambda row:(row['expected_date'],row['reference'].casefold()),reverse=True)}
            searchable=[result['supplier_code'],result['supplier_name']]
            searchable.extend(row['reference'] for row in orders)
            if not term or any(term in value.casefold() for value in searchable): items.append(result)
        items.sort(key=lambda row:(0 if row['status']=='attention' else 1,
            -row['overdue_no_arrival'],-row['late_first_arrivals'],row['supplier_name'].casefold(),
            row['supplier_id']))
        scoped=items if status=='all' else [row for row in items if row['status']==status]
        summary={'suppliers':len(items),'attention_suppliers':sum(row['status']=='attention' for row in items),
            'healthy_suppliers':sum(row['status']=='healthy' for row in items),
            'purchase_orders':sum(row['purchase_order_count'] for row in items),
            'arrived_purchase_orders':sum(row['arrived_purchase_orders'] for row in items),
            'on_time_first_arrivals':sum(row['on_time_first_arrivals'] for row in items),
            'late_first_arrivals':sum(row['late_first_arrivals'] for row in items),
            'overdue_no_arrival':sum(row['overdue_no_arrival'] for row in items),
            'overdue_incomplete_purchase_orders':sum(row['overdue_incomplete_purchase_orders'] for row in items),
            'closed_shortfall_purchase_orders':sum(row['closed_shortfall_purchase_orders'] for row in items),
            'qc_intakes':sum(sum(unit['intake_count'] for unit in row['quality_by_unit']) for row in items),
            'quality_units_with_reject':sum(sum(Decimal(unit['rejected'])>0
                for unit in row['quality_by_unit']) for row in items)}
        return {'as_of':as_of_date.isoformat(),'period_start':period_start.isoformat(),
            'window_days':window_days,'query':query.strip(),'status':status,
            'date_basis':'purchase_order_expected_date','delivery_metric':'first_active_arrival',
            'quality_metric':'active_qc_intakes_grouped_by_unit','total':len(scoped),
            'limit':limit,'offset':offset,'summary':summary,'items':scoped[offset:offset+limit]}

    def material_price_insights(self, as_of, window_days=90, query='', status='changed',
                                limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        period_start=as_of_date-timedelta(days=window_days-1)
        observations=[]
        with self.transaction() as db:
            for order_id, in db.execute('SELECT id FROM purchase_orders ORDER BY sequence'):
                order=self._purchase_order(db,order_id)
                recorded_date=datetime.fromisoformat(order['created_at']).astimezone(
                    timezone(timedelta(hours=7))).date().isoformat()
                if (order['approval_status']!='approved' or order['status']=='cancelled'
                        or not period_start.isoformat()<=recorded_date<=as_of_date.isoformat()):
                    continue
                for line in order['lines']:
                    observations.append({'material_id':line['material_id'],'material_code':line['code'],
                        'material_name':line['name'],'unit':line['unit'],
                        'supplier_id':order['supplier_id'],'supplier_code':order['supplier']['code'],
                        'supplier_name':order['supplier']['name'],'purchase_order_id':order['id'],
                        'purchase_order_reference':order['reference'],'recorded_at':order['created_at'],
                        'recorded_date':recorded_date,'expected_date':order['expected_date'],
                        'unit_price':line['unit_price'],'sequence':order['sequence']})
        grouped={}
        for row in observations:
            grouped.setdefault((row['material_id'],row['supplier_id']),[]).append(row)
        term=query.strip().casefold();items=[]
        for rows in grouped.values():
            rows.sort(key=lambda row:(row['recorded_at'],row['sequence']))
            first,last=rows[0],rows[-1]
            first_price,last_price=Decimal(first['unit_price']),Decimal(last['unit_price'])
            change=last_price-first_price
            if len(rows)==1: classification='single_observation'
            elif change>0: classification='increased'
            elif change<0: classification='decreased'
            else: classification='stable'
            percent=(change*100/first_price).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            prices=[Decimal(row['unit_price']) for row in rows]
            result={'material_id':first['material_id'],'material_code':first['material_code'],
                'material_name':first['material_name'],'unit':first['unit'],
                'supplier_id':first['supplier_id'],'supplier_code':first['supplier_code'],
                'supplier_name':first['supplier_name'],'status':classification,
                'observation_count':len(rows),'earliest_purchase_order_id':first['purchase_order_id'],
                'earliest_purchase_order_reference':first['purchase_order_reference'],
                'earliest_recorded_date':first['recorded_date'],'earliest_unit_price':format(first_price,'.2f'),
                'latest_purchase_order_id':last['purchase_order_id'],
                'latest_purchase_order_reference':last['purchase_order_reference'],
                'latest_recorded_date':last['recorded_date'],'latest_unit_price':format(last_price,'.2f'),
                'price_change':format(change,'.2f'),'price_change_percent':format(percent,'.2f'),
                'minimum_unit_price':format(min(prices),'.2f'),'maximum_unit_price':format(max(prices),'.2f'),
                'average_unit_price':format((sum(prices)/len(prices)).quantize(
                    Decimal('.01'),rounding=ROUND_HALF_UP),'.2f'),
                'history':[{key:row[key] for key in ('purchase_order_id','purchase_order_reference',
                    'recorded_at','recorded_date','expected_date','unit_price')} for row in reversed(rows)]}
            searchable=[result['material_code'],result['material_name'],result['supplier_code'],
                        result['supplier_name']]
            searchable.extend(row['purchase_order_reference'] for row in rows)
            if not term or any(term in value.casefold() for value in searchable): items.append(result)
        priority={'increased':0,'decreased':1,'stable':2,'single_observation':3}
        items.sort(key=lambda row:(priority[row['status']],-abs(Decimal(row['price_change_percent'])),
            row['material_code'].casefold(),row['supplier_name'].casefold(),row['material_id'],
            row['supplier_id']))
        scoped=items if status=='all' else ([row for row in items if row['status'] in ('increased','decreased')]
            if status=='changed' else [row for row in items if row['status']==status])
        summary={'series':len(items),'materials':len({row['material_id'] for row in items}),
            'suppliers':len({row['supplier_id'] for row in items}),
            'observations':sum(row['observation_count'] for row in items),
            'changed_series':sum(row['status'] in ('increased','decreased') for row in items),
            'increased_series':sum(row['status']=='increased' for row in items),
            'decreased_series':sum(row['status']=='decreased' for row in items),
            'stable_series':sum(row['status']=='stable' for row in items),
            'single_observation_series':sum(row['status']=='single_observation' for row in items)}
        return {'as_of':as_of_date.isoformat(),'period_start':period_start.isoformat(),
            'window_days':window_days,'query':query.strip(),'status':status,
            'date_basis':'purchase_order_created_date','currency':'IDR','grouping':'material_and_supplier',
            'total':len(scoped),'limit':limit,'offset':offset,'summary':summary,
            'items':scoped[offset:offset+limit]}

    def purchase_commitment_insights(self, as_of, due_soon_days=7, query='', status='open',
                                     limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        due_soon_end=as_of_date+timedelta(days=due_soon_days)
        items=[]
        with self.transaction() as db:
            order_ids=[row[0] for row in db.execute('SELECT id FROM purchase_orders ORDER BY sequence')]
            for order_id in order_ids:
                order=self._purchase_order(db,order_id)
                created_date=datetime.fromisoformat(order['created_at']).astimezone(
                    timezone(timedelta(hours=7))).date().isoformat()
                if (order['approval_status']!='approved' or order['status']!='issued'
                        or created_date>as_of_date.isoformat()):
                    continue
                order_value=Decimal(order['total'])
                received_value=Decimal(order['payment_received_value'])
                open_value=order_value-received_value
                expected=date.fromisoformat(order['expected_date'])
                if open_value<=0: classification='fulfilled'
                elif expected<as_of_date: classification='overdue'
                elif expected<=due_soon_end: classification='due_soon'
                else: classification='scheduled'
                lines=[]
                for line in order['lines']:
                    line_received=(Decimal(line['received'])*Decimal(line['unit_price'])).quantize(
                        Decimal('.01'),rounding=ROUND_HALF_UP)
                    lines.append({'material_id':line['material_id'],'code':line['code'],
                        'name':line['name'],'unit':line['unit'],'ordered_quantity':line['quantity'],
                        'usable_received_quantity':line['received'],'open_quantity':line['remaining'],
                        'unit_price':line['unit_price'],'ordered_value':line['line_total'],
                        'usable_received_value':format(line_received,'.2f'),
                        'open_commitment_value':format(Decimal(line['line_total'])-line_received,'.2f')})
                item={'purchase_order_id':order['id'],'purchase_order_reference':order['reference'],
                    'purchase_request_id':order['request_id'],
                    'purchase_request_reference':order['request_reference'],
                    'production_order_id':order['production_order_id'],
                    'supplier_id':order['supplier_id'],'supplier_code':order['supplier']['code'],
                    'supplier_name':order['supplier']['name'],'created_at':order['created_at'],
                    'created_date':created_date,'expected_date':order['expected_date'],
                    'status':classification,'overdue_days':max((as_of_date-expected).days,0)
                        if open_value>0 else 0,'fulfillment':order['fulfillment'],
                    'purchase_order_value':format(order_value,'.2f'),
                    'usable_received_value':format(received_value,'.2f'),
                    'open_commitment_value':format(open_value,'.2f'),
                    'payment_pending':order['payment_pending'],
                    'payment_approved':order['payment_approved'],
                    'payment_unrequested':order['payment_remaining'],'lines':lines}
                searchable=[item['purchase_order_reference'],item['purchase_request_reference'],
                    item['supplier_code'],item['supplier_name']]
                searchable.extend(value for line in lines for value in (line['code'],line['name']))
                if not query.strip() or any(query.strip().casefold() in value.casefold()
                                            for value in searchable):
                    items.append(item)
        priority={'overdue':0,'due_soon':1,'scheduled':2,'fulfilled':3}
        items.sort(key=lambda row:(priority[row['status']],-Decimal(row['open_commitment_value']),
            row['expected_date'],row['purchase_order_reference'].casefold(),row['purchase_order_id']))
        scoped=items if status=='all' else ([row for row in items if row['status']!='fulfilled']
            if status=='open' else [row for row in items if row['status']==status])
        money=lambda key:format(sum((Decimal(row[key]) for row in items),Decimal('0')),'.2f')
        summary={'purchase_orders':len(items),
            'open_purchase_orders':sum(row['status']!='fulfilled' for row in items),
            'fulfilled_purchase_orders':sum(row['status']=='fulfilled' for row in items),
            'overdue_purchase_orders':sum(row['status']=='overdue' for row in items),
            'due_soon_purchase_orders':sum(row['status']=='due_soon' for row in items),
            'scheduled_purchase_orders':sum(row['status']=='scheduled' for row in items),
            'purchase_order_value':money('purchase_order_value'),
            'usable_received_value':money('usable_received_value'),
            'open_commitment_value':money('open_commitment_value'),
            'payment_pending':money('payment_pending'),'payment_approved':money('payment_approved'),
            'payment_unrequested':money('payment_unrequested')}
        return {'as_of':as_of_date.isoformat(),'due_soon_days':due_soon_days,
            'due_soon_end':due_soon_end.isoformat(),'query':query.strip(),'status':status,'currency':'IDR',
            'ledger_basis':'current_active_purchase_orders','received_basis':'usable_material_receipts',
            'total':len(scoped),'limit':limit,'offset':offset,'summary':summary,
            'items':scoped[offset:offset+limit]}

    def wip_ageing_insights(self, as_of, idle_days=7, query='', owner_id='', stage='all',
                            status='attention', limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        production_stages=tuple(value for value in STAGES if value not in ('warehouse','reject'))
        local_zone=timezone(timedelta(hours=7))
        term=query.strip().casefold();items=[]
        with self.transaction() as db:
            order_ids=[row[0] for row in db.execute('SELECT id FROM orders ORDER BY created_at,id')]
            owners=[dict(row) for row in db.execute('''SELECT u.id,u.name,u.active FROM users u
                WHERE EXISTS(SELECT 1 FROM orders o WHERE o.owner_id=u.id) ORDER BY u.name,u.id''')]
            for order_id in order_ids:
                order=self._order(db,order_id)
                created_date=datetime.fromisoformat(order['created_at']).astimezone(local_zone).date()
                active_quantity=sum(order['totals'][value] for value in production_stages)
                if not active_quantity or created_date>as_of_date:
                    continue
                if owner_id and order['owner_id']!=owner_id:
                    continue
                positions=[{'stage':value,'quantity':order['totals'][value]}
                           for value in production_stages if order['totals'][value]>0]
                if stage!='all' and not any(row['stage']==stage for row in positions):
                    continue
                movement=db.execute('''SELECT m.created_at FROM movements m
                    JOIN order_lines l ON l.id=m.line_id WHERE l.order_id=?
                    ORDER BY m.sequence DESC LIMIT 1''',(order_id,)).fetchone()
                latest_activity_at=movement['created_at'] if movement else order['created_at']
                latest_activity_date=datetime.fromisoformat(latest_activity_at).astimezone(local_zone).date()
                inactive_days=max((as_of_date-latest_activity_date).days,0)
                overdue_days=max((as_of_date-date.fromisoformat(order['due_date'])).days,0)
                issues=[dict(row) for row in db.execute('''SELECT i.id,i.stage,i.description,i.owner_id,
                    u.name AS owner_name FROM issues i JOIN order_lines l ON l.id=i.line_id
                    JOIN users u ON u.id=i.owner_id WHERE l.order_id=? AND i.resolved_at IS NULL
                    ORDER BY i.sequence DESC''',(order_id,))]
                flags=[]
                if overdue_days: flags.append('overdue')
                if issues: flags.append('blocked')
                if inactive_days>=idle_days: flags.append('stalled')
                if order['totals']['rework']>0: flags.append('rework')
                products=[{key:line[key] for key in ('product_id','sku','name','color','size','quantity')}
                          for line in order['lines']]
                searchable=[order['reference'],order['title'],order['owner_name']]
                searchable.extend(value for product in products
                                  for value in (product['sku'],product['name'],product['color'],product['size']))
                searchable.extend(value for issue in issues
                                  for value in (issue['description'],issue['owner_name']))
                if term and not any(term in value.casefold() for value in searchable if value):
                    continue
                primary=max(positions,key=lambda row:(row['quantity'],-production_stages.index(row['stage'])))
                items.append({'order_id':order['id'],'reference':order['reference'],'title':order['title'],
                    'owner_id':order['owner_id'],'owner_name':order['owner_name'],
                    'created_at':order['created_at'],'created_date':created_date.isoformat(),
                    'due_date':order['due_date'],'overdue_days':overdue_days,
                    'latest_activity_at':latest_activity_at,
                    'latest_activity_date':latest_activity_date.isoformat(),
                    'activity_basis':'latest_production_movement' if movement else 'order_created',
                    'activity_after_as_of':latest_activity_date>as_of_date,'inactive_days':inactive_days,
                    'target_quantity':order['target_quantity'],'active_quantity':active_quantity,
                    'planned_quantity':order['totals']['planned'],
                    'in_process_quantity':sum(order['totals'][value] for value in production_stages
                                              if value!='planned'),
                    'warehouse_quantity':order['totals']['warehouse'],
                    'reject_quantity':order['totals']['reject'],
                    'rework_quantity':order['totals']['rework'],'primary_stage':primary['stage'],
                    'flags':flags,'attention':bool(flags),'positions':positions,'products':products,
                    'open_issue_count':len(issues),'open_issues':issues})
        items.sort(key=lambda row:(not bool(row['overdue_days']),not bool(row['open_issue_count']),
            'stalled' not in row['flags'],not bool(row['rework_quantity']),-row['inactive_days'],
            row['due_date'],row['reference'].casefold(),row['order_id']))
        stages=[]
        for value in production_stages:
            rows=[(item,next((position['quantity'] for position in item['positions']
                              if position['stage']==value),0)) for item in items]
            rows=[(item,quantity) for item,quantity in rows if quantity]
            stages.append({'stage':value,'quantity':sum(quantity for _,quantity in rows),
                'orders':len(rows),'stalled_quantity':sum(quantity for item,quantity in rows
                                                          if 'stalled' in item['flags']),
                'stalled_orders':sum('stalled' in item['flags'] for item,_ in rows),
                'blocked_quantity':sum(quantity for item,quantity in rows
                                       if 'blocked' in item['flags'])})
        nonempty=[row for row in stages if row['quantity']]
        stalled=[row for row in stages if row['stalled_quantity']]
        largest=max(nonempty,key=lambda row:(row['quantity'],-production_stages.index(row['stage']))) \
            if nonempty else None
        bottleneck=max(stalled,key=lambda row:(row['stalled_quantity'],
            -production_stages.index(row['stage']))) if stalled else None
        summary={'active_orders':len(items),'attention_orders':sum(item['attention'] for item in items),
            'stalled_orders':sum('stalled' in item['flags'] for item in items),
            'overdue_orders':sum('overdue' in item['flags'] for item in items),
            'blocked_orders':sum('blocked' in item['flags'] for item in items),
            'rework_orders':sum('rework' in item['flags'] for item in items),
            'active_quantity':sum(item['active_quantity'] for item in items),
            'planned_quantity':sum(item['planned_quantity'] for item in items),
            'in_process_quantity':sum(item['in_process_quantity'] for item in items),
            'stalled_quantity':sum(item['active_quantity'] for item in items
                                   if 'stalled' in item['flags']),
            'open_issues':sum(item['open_issue_count'] for item in items),
            'largest_active_stage':largest['stage'] if largest else None,
            'bottleneck_signal_stage':bottleneck['stage'] if bottleneck else None}
        if status=='attention': scoped=[item for item in items if item['attention']]
        elif status=='moving': scoped=[item for item in items if not item['attention']]
        elif status=='all': scoped=items
        else: scoped=[item for item in items if status in item['flags']]
        return {'as_of':as_of_date.isoformat(),'idle_days':idle_days,'query':query.strip(),
            'owner_id':owner_id,'stage':stage,'status':status,'timezone':'Asia/Jakarta',
            'position_basis':'current_production_ledger',
            'age_basis':'latest_production_movement_or_order_created',
            'capacity_basis':'not_configured',
            'bottleneck_signal_basis':'largest_current_quantity_on_stalled_orders',
            'total':len(scoped),'limit':limit,'offset':offset,'owners':owners,
            'summary':summary,'stages':stages,'items':scoped[offset:offset+limit]}

    def production_quality_insights(self, as_of, window_days=30, warning_percent=5,
                                    change_threshold=1, query='', assignment_type='all',
                                    status='attention', limit=100, offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        current_start=as_of_date-timedelta(days=window_days-1)
        previous_end=current_start-timedelta(days=1)
        previous_start=previous_end-timedelta(days=window_days-1)
        params={'previous_start':previous_start.isoformat(),'as_of':as_of_date.isoformat(),
                'query':query.strip().casefold(),'assignment_type':assignment_type}
        with self.transaction() as db:
            rows=[dict(row) for row in db.execute('''SELECT q.sequence,q.id,q.reference,q.inspection_date,
                q.accepted_quantity,q.rework_quantity,q.reject_quantity,q.defect_type,
                q.responsible_source,q.disposition,q.created_at,f.id AS finishing_record_id,
                f.reference AS finishing_reference,j.assignment_type,j.assignee,
                o.id AS order_id,o.reference AS order_reference,o.title AS order_title,
                p.id AS product_id,p.sku,p.name AS product_name,p.color,p.size
                FROM final_qc_records q JOIN finishing_records f ON f.id=q.finishing_record_id
                JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
                JOIN cutting_runs c ON c.id=b.cutting_run_id JOIN orders o ON o.id=c.order_id
                JOIN movements source ON source.id=b.output_movement_id
                JOIN order_lines l ON l.id=source.line_id JOIN products p ON p.id=l.product_id
                WHERE q.inspection_date BETWEEN :previous_start AND :as_of
                  AND NOT EXISTS(SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id)
                  AND (:assignment_type='all' OR j.assignment_type=:assignment_type)
                  AND (:query='' OR instr(lower(q.reference),:query)>0
                    OR instr(lower(q.defect_type),:query)>0
                    OR instr(lower(q.responsible_source),:query)>0
                    OR instr(lower(j.assignee),:query)>0 OR instr(lower(o.reference),:query)>0
                    OR instr(lower(o.title),:query)>0 OR instr(lower(p.sku),:query)>0
                    OR instr(lower(p.name),:query)>0 OR instr(lower(p.color),:query)>0
                    OR instr(lower(p.size),:query)>0)
                ORDER BY q.inspection_date DESC,q.sequence DESC''',params)]

        def blank():
            return {'record_count':0,'inspected_quantity':0,'accepted_quantity':0,
                    'rework_quantity':0,'reject_quantity':0,'nonconforming_quantity':0}

        def add(metric,row):
            inspected=row['accepted_quantity']+row['rework_quantity']+row['reject_quantity']
            metric['record_count']+=1;metric['inspected_quantity']+=inspected
            metric['accepted_quantity']+=row['accepted_quantity']
            metric['rework_quantity']+=row['rework_quantity']
            metric['reject_quantity']+=row['reject_quantity']
            metric['nonconforming_quantity']+=row['rework_quantity']+row['reject_quantity']

        def percent(value,total):
            return format((Decimal(value)*100/total).quantize(
                Decimal('.01'),rounding=ROUND_HALF_UP),'.2f') if total else '0.00'

        def finish(metric):
            total=metric['inspected_quantity']
            return metric|{'first_pass_yield_percent':percent(metric['accepted_quantity'],total),
                'nonconforming_rate_percent':percent(metric['nonconforming_quantity'],total),
                'rework_rate_percent':percent(metric['rework_quantity'],total),
                'reject_rate_percent':percent(metric['reject_quantity'],total)}

        groups={};overall_current=blank();overall_previous=blank()
        for row in rows:
            period='current' if row['inspection_date']>=current_start.isoformat() else 'previous'
            key=(row['assignment_type'],row['assignee'].casefold())
            group=groups.setdefault(key,{'assignment_type':row['assignment_type'],'assignee':row['assignee'],
                'current':blank(),'previous':blank(),'skus':{},'defect_types':{},
                'responsible_sources':{},'recent_records':[]})
            add(group[period],row);add(overall_current if period=='current' else overall_previous,row)
            if period!='current':
                continue
            inspected=row['accepted_quantity']+row['rework_quantity']+row['reject_quantity']
            nonconforming=row['rework_quantity']+row['reject_quantity']
            sku=group['skus'].setdefault(row['product_id'],{'product_id':row['product_id'],'sku':row['sku'],
                'product_name':row['product_name'],'color':row['color'],'size':row['size'],**blank()})
            add(sku,row)
            if nonconforming:
                defect=group['defect_types'].setdefault(row['defect_type'],{
                    'defect_type':row['defect_type'],'record_count':0,'nonconforming_quantity':0})
                defect['record_count']+=1;defect['nonconforming_quantity']+=nonconforming
                source=group['responsible_sources'].setdefault(row['responsible_source'],{
                    'responsible_source':row['responsible_source'],'record_count':0,
                    'nonconforming_quantity':0})
                source['record_count']+=1;source['nonconforming_quantity']+=nonconforming
            group['recent_records'].append({key:row[key] for key in ('id','reference','inspection_date',
                'order_id','order_reference','order_title','finishing_record_id','finishing_reference',
                'product_id','sku','product_name','color','size','defect_type','responsible_source',
                'disposition','accepted_quantity','rework_quantity','reject_quantity')}|{
                'inspected_quantity':inspected,'nonconforming_quantity':nonconforming})

        items=[]
        for group in groups.values():
            if not group['current']['inspected_quantity']:
                continue
            current=finish(group['current']);previous=finish(group['previous'])
            if previous['inspected_quantity']:
                change=(Decimal(current['nonconforming_rate_percent'])-
                        Decimal(previous['nonconforming_rate_percent']))
                change_points=format(change.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')
                trend=('worsening' if change>=change_threshold else
                       'improving' if change<=-change_threshold else 'stable')
            else:
                change_points=None;trend='new_baseline'
            reasons=[]
            if (current['nonconforming_quantity'] and
                    Decimal(current['nonconforming_rate_percent'])>=warning_percent):
                reasons.append('above_warning')
            if trend=='worsening':
                reasons.append('worsening')
            skus=[finish(value) for value in group['skus'].values()]
            skus.sort(key=lambda row:(-row['nonconforming_quantity'],
                -Decimal(row['nonconforming_rate_percent']),row['sku'].casefold(),row['product_id']))
            defects=list(group['defect_types'].values());defects.sort(
                key=lambda row:(-row['nonconforming_quantity'],row['defect_type'].casefold()))
            sources=list(group['responsible_sources'].values());sources.sort(
                key=lambda row:(-row['nonconforming_quantity'],row['responsible_source'].casefold()))
            items.append({'assignment_type':group['assignment_type'],'assignee':group['assignee'],
                'status':'attention' if reasons else 'healthy','attention_reasons':reasons,'trend':trend,
                'nonconforming_rate_change_points':change_points,'current':current,'previous':previous,
                'skus':skus,'defect_types':defects,'responsible_sources':sources,
                'recent_records':group['recent_records'][:5]})
        items.sort(key=lambda row:(row['status']!='attention',
            -Decimal(row['current']['nonconforming_rate_percent']),
            -row['current']['inspected_quantity'],row['assignee'].casefold(),row['assignment_type']))
        scoped=items if status=='all' else [row for row in items if row['status']==status]
        current=finish(overall_current);previous=finish(overall_previous)
        overall_change=(format((Decimal(current['nonconforming_rate_percent'])-
            Decimal(previous['nonconforming_rate_percent'])).quantize(
                Decimal('.01'),rounding=ROUND_HALF_UP),'.2f') if previous['inspected_quantity'] else None)
        summary=current|{'groups':len(items),'attention_groups':sum(row['status']=='attention' for row in items),
            'previous_inspected_quantity':previous['inspected_quantity'],
            'previous_nonconforming_quantity':previous['nonconforming_quantity'],
            'previous_nonconforming_rate_percent':previous['nonconforming_rate_percent'],
            'nonconforming_rate_change_points':overall_change}
        return {'as_of':as_of_date.isoformat(),'window_days':window_days,
            'current_period_start':current_start.isoformat(),
            'previous_period_start':previous_start.isoformat(),
            'previous_period_end':previous_end.isoformat(),'warning_percent':warning_percent,
            'change_threshold':change_threshold,'query':query.strip(),'assignment_type':assignment_type,
            'status':status,'source':'active_final_qc_records','corrected_records':'excluded',
            'total':len(scoped),'limit':limit,'offset':offset,'summary':summary,
            'items':scoped[offset:offset+limit]}

    @staticmethod
    def _capacity_minutes(value):
        return format(Decimal(value)/1000,'.3f')

    def _work_center(self,db,work_center_id):
        row=db.execute('''SELECT c.id,c.code,c.stage,c.created_by,c.created_at,
            e.sequence,e.id AS event_id,e.revision,e.name,e.daily_minutes,e.active,e.reason,
            e.actor_id,e.created_at AS updated_at,u.name AS actor_name
            FROM production_work_centers c JOIN production_work_center_events e
                ON e.work_center_id=c.id AND e.sequence=(SELECT MAX(x.sequence)
                    FROM production_work_center_events x WHERE x.work_center_id=c.id)
            JOIN users u ON u.id=e.actor_id WHERE c.id=?''',(work_center_id,)).fetchone()
        if not row:
            raise DomainError(404,'Work center produksi tidak ditemukan.')
        record=dict(row);record['active']=bool(record['active']);return record

    def work_centers(self,status='all'):
        with self.transaction() as db:
            ids=[row['id'] for row in db.execute('SELECT id FROM production_work_centers ORDER BY code,id')]
            rows=[self._work_center(db,value) for value in ids]
            return rows if status=='all' else [row for row in rows if bool(row['active'])==(status=='active')]

    def create_work_center(self,payload,actor,key):
        def perform(db):
            work_center_id=str(uuid4());created=now()
            db.execute('''INSERT INTO production_work_centers(id,code,stage,created_by,created_at)
                VALUES(?,?,?,?,?)''',(work_center_id,payload['code'],payload['stage'],actor['id'],created))
            db.execute('''INSERT INTO production_work_center_events(id,work_center_id,revision,name,
                daily_minutes,active,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',
                (str(uuid4()),work_center_id,1,payload['name'],payload['daily_minutes'],1,
                 payload['reason'],actor['id'],created))
            return self._work_center(db,work_center_id)
        return self._write(actor,('admin',),key,'work-center',payload,perform)

    def change_work_center(self,work_center_id,payload,actor,key):
        def perform(db):
            current=self._work_center(db,work_center_id)
            if current['revision']!=payload['expected_revision']:
                raise DomainError(409,'Work center sudah berubah. Muat ulang lalu coba lagi.')
            if (current['name']==payload['name'] and current['daily_minutes']==payload['daily_minutes']
                    and bool(current['active'])==payload['active']):
                raise DomainError(422,'Belum ada perubahan pada work center.')
            db.execute('''INSERT INTO production_work_center_events(id,work_center_id,revision,name,
                daily_minutes,active,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',
                (str(uuid4()),work_center_id,current['revision']+1,payload['name'],
                 payload['daily_minutes'],int(payload['active']),payload['reason'],actor['id'],now()))
            return self._work_center(db,work_center_id)
        return self._write(actor,('admin',),key,'work-center:'+work_center_id,payload,perform)

    def _routing_standard(self,db,product_id,stage):
        product=db.execute('SELECT id,sku,name,color,size FROM products WHERE id=?',(product_id,)).fetchone()
        if not product:
            raise DomainError(404,'SKU tidak ditemukan.')
        row=db.execute('''SELECT s.*,c.code AS work_center_code,c.stage AS work_center_stage,
            w.name AS work_center_name,w.active AS work_center_active,u.name AS actor_name
            FROM production_routing_standard_events s
            JOIN production_work_centers c ON c.id=s.work_center_id
            JOIN production_work_center_events w ON w.work_center_id=c.id
                AND w.sequence=(SELECT MAX(x.sequence) FROM production_work_center_events x
                    WHERE x.work_center_id=c.id)
            JOIN users u ON u.id=s.actor_id WHERE s.product_id=? AND s.stage=?
            ORDER BY s.sequence DESC LIMIT 1''',(product_id,stage)).fetchone()
        base=dict(product)|{'stage':stage}
        if not row:
            return base|{'id':None,'sequence':None,'revision':0,'work_center_id':None,
                'work_center_code':None,'work_center_name':None,'work_center_active':None,
                'minutes_per_unit':None,'reason':'','actor_id':None,'actor_name':None,'created_at':None}
        record=dict(row);record['minutes_per_unit']=self._capacity_minutes(
            record.pop('minutes_per_unit_milli'))
        record['work_center_active']=bool(record['work_center_active'])
        return base|record

    def routing_standard(self,product_id,stage):
        with self.transaction() as db:
            return self._routing_standard(db,product_id,stage)

    def routing_standards(self,product_id='',stage='all',limit=100,offset=0):
        with self.transaction() as db:
            rows=db.execute('''SELECT s.product_id,s.stage FROM production_routing_standard_events s
                JOIN products p ON p.id=s.product_id
                WHERE (?='' OR s.product_id=?) AND (?='all' OR s.stage=?)
                AND s.sequence=(SELECT MAX(x.sequence) FROM production_routing_standard_events x
                    WHERE x.product_id=s.product_id AND x.stage=s.stage)
                ORDER BY p.sku,s.stage LIMIT ? OFFSET ?''',
                (product_id,product_id,stage,stage,limit,offset)).fetchall()
            return [self._routing_standard(db,row['product_id'],row['stage']) for row in rows]

    def save_routing_standard(self,product_id,stage,payload,actor,key):
        def perform(db):
            current=self._routing_standard(db,product_id,stage)
            if current['revision']!=payload['expected_revision']:
                raise DomainError(409,'Standar proses SKU sudah berubah. Muat ulang lalu coba lagi.')
            center=self._work_center(db,payload['work_center_id'])
            if center['stage']!=stage:
                raise DomainError(422,'Tahap work center tidak cocok dengan tahap standar.')
            if not center['active']:
                raise DomainError(422,'Work center nonaktif tidak dapat menerima standar baru.')
            minutes=int(Decimal(payload['minutes_per_unit'])*1000)
            if (current['revision'] and current['work_center_id']==center['id']
                    and current['minutes_per_unit']==self._capacity_minutes(minutes)):
                raise DomainError(422,'Standar proses baru sama dengan revisi aktif.')
            db.execute('''INSERT INTO production_routing_standard_events(id,product_id,stage,revision,
                work_center_id,minutes_per_unit_milli,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)''',(str(uuid4()),product_id,stage,current['revision']+1,
                center['id'],minutes,payload['reason'],actor['id'],now()))
            return self._routing_standard(db,product_id,stage)
        return self._write(actor,('admin',),key,'routing-standard:'+product_id+':'+stage,payload,perform)

    def capacity_calendar(self,work_center_id,start_date,end_date):
        start=start_date if isinstance(start_date,date) else date.fromisoformat(start_date)
        end=end_date if isinstance(end_date,date) else date.fromisoformat(end_date)
        if end<start:
            raise DomainError(422,'Tanggal akhir kalender harus sama atau setelah tanggal awal.')
        with self.transaction() as db:
            center=self._work_center(db,work_center_id)
            rows=db.execute('''SELECT e.*,u.name AS actor_name FROM production_capacity_calendar_events e
                JOIN users u ON u.id=e.actor_id WHERE e.work_center_id=? AND e.work_date BETWEEN ? AND ?
                AND e.sequence=(SELECT MAX(x.sequence) FROM production_capacity_calendar_events x
                    WHERE x.work_center_id=e.work_center_id AND x.work_date=e.work_date)
                ORDER BY e.work_date''',(work_center_id,start.isoformat(),end.isoformat())).fetchall()
            return {'work_center':center,'start_date':start.isoformat(),'end_date':end.isoformat(),
                    'items':[dict(row) for row in rows]}

    def save_capacity_calendar(self,work_center_id,payload,actor,key):
        def perform(db):
            center=self._work_center(db,work_center_id);work_date=payload['work_date']
            current=db.execute('''SELECT * FROM production_capacity_calendar_events
                WHERE work_center_id=? AND work_date=? ORDER BY sequence DESC LIMIT 1''',
                (work_center_id,work_date)).fetchone()
            revision=current['revision'] if current else 0
            if revision!=payload['expected_revision']:
                raise DomainError(409,'Kalender kapasitas sudah berubah. Muat ulang lalu coba lagi.')
            if current and current['available_minutes']==payload['available_minutes']:
                raise DomainError(422,'Kapasitas tanggal tersebut belum berubah.')
            record={'id':str(uuid4()),'work_center_id':center['id'],'work_date':work_date,
                'revision':revision+1,'available_minutes':payload['available_minutes'],
                'reason':payload['reason'],'actor_id':actor['id'],'created_at':now()}
            db.execute('''INSERT INTO production_capacity_calendar_events(id,work_center_id,work_date,
                revision,available_minutes,reason,actor_id,created_at)
                VALUES(:id,:work_center_id,:work_date,:revision,:available_minutes,:reason,:actor_id,:created_at)''',record)
            return record|{'work_center_code':center['code'],'work_center_name':center['name']}
        return self._write(actor,('admin',),key,'capacity-calendar:'+work_center_id,payload,perform)

    def capacity_plan(self,as_of,horizon_days=14,warning_percent=80,work_center_id='',stage='all',
                      status='attention',limit=100,offset=0):
        as_of_date=as_of if isinstance(as_of,date) else date.fromisoformat(as_of)
        horizon_end=as_of_date+timedelta(days=horizon_days-1)
        main_route=('cutting','sewing','finishing','qc')
        remaining={'planned':main_route,'cutting':main_route,'sewing':main_route[1:],
            'finishing':main_route[2:],'qc':main_route[3:],'rework':('rework','qc')}
        with self.transaction() as db:
            center_ids=[row['id'] for row in db.execute('SELECT id FROM production_work_centers ORDER BY code,id')]
            all_centers=[self._work_center(db,value) for value in center_ids]
            active_centers={row['id']:row for row in all_centers if row['active']}
            if work_center_id and work_center_id not in {row['id'] for row in all_centers}:
                raise DomainError(404,'Work center produksi tidak ditemukan.')
            centers=[row for row in active_centers.values()
                     if (not work_center_id or row['id']==work_center_id)
                     and (stage=='all' or row['stage']==stage)]
            standard_rows=db.execute('''SELECT product_id,stage FROM production_routing_standard_events s
                WHERE s.sequence=(SELECT MAX(x.sequence) FROM production_routing_standard_events x
                    WHERE x.product_id=s.product_id AND x.stage=s.stage)''').fetchall()
            standards={(row['product_id'],row['stage']):self._routing_standard(
                db,row['product_id'],row['stage']) for row in standard_rows}
            calendar_rows=db.execute('''SELECT e.* FROM production_capacity_calendar_events e
                WHERE e.work_date BETWEEN ? AND ? AND e.sequence=(SELECT MAX(x.sequence)
                    FROM production_capacity_calendar_events x
                    WHERE x.work_center_id=e.work_center_id AND x.work_date=e.work_date)''',
                    (as_of_date.isoformat(),horizon_end.isoformat())).fetchall()
            overrides={(row['work_center_id'],row['work_date']):dict(row) for row in calendar_rows}
            workload={row['id']:{} for row in centers};gaps=[];orders_in_scope=set()
            for order_id, in db.execute('SELECT id FROM orders ORDER BY due_date,created_at,id'):
                order=self._order(db,order_id)
                created=datetime.fromisoformat(order['created_at']).astimezone(
                    timezone(timedelta(hours=7))).date()
                if (order['status']!='active' or created>as_of_date
                        or date.fromisoformat(order['due_date'])>horizon_end):
                    continue
                for line in order['lines']:
                    requirements={}
                    for position,quantity in line['balances'].items():
                        if quantity>0 and position in remaining:
                            for required_stage in remaining[position]:
                                if stage=='all' or required_stage==stage:
                                    requirements[required_stage]=requirements.get(required_stage,0)+quantity
                    for required_stage,quantity in requirements.items():
                        standard=standards.get((line['product_id'],required_stage))
                        if not standard:
                            if not work_center_id:
                                orders_in_scope.add(order_id)
                                gaps.append({'kind':'missing_standard','order_id':order['id'],
                                    'order_reference':order['reference'],'product_id':line['product_id'],
                                    'sku':line['sku'],'product_name':line['name'],'stage':required_stage,
                                    'quantity':quantity})
                            continue
                        center=active_centers.get(standard['work_center_id'])
                        if not center:
                            if not work_center_id or work_center_id==standard['work_center_id']:
                                orders_in_scope.add(order_id)
                                gaps.append({'kind':'inactive_work_center','order_id':order['id'],
                                    'order_reference':order['reference'],'product_id':line['product_id'],
                                    'sku':line['sku'],'product_name':line['name'],'stage':required_stage,
                                    'quantity':quantity,'work_center_id':standard['work_center_id'],
                                    'work_center_code':standard['work_center_code']})
                            continue
                        if center['id'] not in workload:
                            continue
                        orders_in_scope.add(order_id)
                        required_milli=quantity*int(Decimal(standard['minutes_per_unit'])*1000)
                        order_load=workload[center['id']].setdefault(order['id'],{
                            'order_id':order['id'],'order_reference':order['reference'],
                            'order_title':order['title'],'due_date':order['due_date'],
                            'overdue':date.fromisoformat(order['due_date'])<as_of_date,
                            'required_milli':0,'products':{}})
                        order_load['required_milli']+=required_milli
                        product=order_load['products'].setdefault((line['product_id'],required_stage),{
                            'product_id':line['product_id'],'sku':line['sku'],'product_name':line['name'],
                            'stage':required_stage,'quantity':0,'minutes_per_unit':standard['minutes_per_unit'],
                            'required_milli':0})
                        product['quantity']+=quantity;product['required_milli']+=required_milli
            items=[]
            for center in centers:
                days=[];cursor=as_of_date
                while cursor<=horizon_end:
                    override=overrides.get((center['id'],cursor.isoformat()))
                    available=override['available_minutes'] if override else (
                        center['daily_minutes'] if cursor.weekday()<5 else 0)
                    days.append({'date':cursor.isoformat(),'available_minutes':available,
                        'source':'override' if override else ('weekday_default' if cursor.weekday()<5 else 'weekend'),
                        'revision':override['revision'] if override else 0,
                        'reason':override['reason'] if override else ''})
                    cursor+=timedelta(days=1)
                available_minutes=sum(row['available_minutes'] for row in days)
                order_rows=sorted(workload[center['id']].values(),
                                  key=lambda row:(row['due_date'],row['order_reference'],row['order_id']))
                cumulative=0
                for row in order_rows:
                    required=row.pop('required_milli');cumulative+=required
                    due=date.fromisoformat(row['due_date'])
                    available_by_due=sum(day['available_minutes'] for day in days
                                         if date.fromisoformat(day['date'])<=due) if due>=as_of_date else 0
                    row['required_minutes']=self._capacity_minutes(required)
                    row['cumulative_required_minutes']=self._capacity_minutes(cumulative)
                    row['available_minutes_by_due']=available_by_due
                    row['capacity_shortfall_minutes']=self._capacity_minutes(
                        max(cumulative-available_by_due*1000,0))
                    row['at_risk']=cumulative>available_by_due*1000
                    row['products']=[item|{'required_minutes':self._capacity_minutes(
                        item.pop('required_milli'))} for item in row['products'].values()]
                required_milli=cumulative
                available_milli=available_minutes*1000
                utilization=(format((Decimal(required_milli)*100/available_milli).quantize(
                    Decimal('.01'),rounding=ROUND_HALF_UP),'.2f') if available_milli else None)
                if required_milli>available_milli: classification='overloaded'
                elif any(row['at_risk'] for row in order_rows): classification='deadline_risk'
                elif required_milli and Decimal(utilization)>=warning_percent: classification='near_capacity'
                elif required_milli: classification='available'
                else: classification='idle'
                items.append(center|{'status':classification,
                    'required_minutes':self._capacity_minutes(required_milli),
                    'available_minutes':available_minutes,'remaining_minutes':self._capacity_minutes(
                        max(available_milli-required_milli,0)),
                    'overload_minutes':self._capacity_minutes(max(required_milli-available_milli,0)),
                    'utilization_percent':utilization,'order_count':len(order_rows),
                    'at_risk_order_count':sum(row['at_risk'] for row in order_rows),
                    'days':days,'orders':order_rows})
        priority={'overloaded':0,'deadline_risk':1,'near_capacity':2,'available':3,'idle':4}
        stage_order={value:index for index,value in enumerate((*main_route,'rework'))}
        items.sort(key=lambda row:(priority[row['status']],stage_order[row['stage']],row['code'],row['id']))
        if status=='attention': scoped=[row for row in items if row['status'] in
                                       ('overloaded','deadline_risk','near_capacity')]
        elif status=='all': scoped=items
        else: scoped=[row for row in items if row['status']==status]
        summary={'work_centers':len(items),'attention_work_centers':sum(priority[row['status']]<3 for row in items),
            'overloaded_work_centers':sum(row['status']=='overloaded' for row in items),
            'deadline_risk_work_centers':sum(row['status']=='deadline_risk' for row in items),
            'near_capacity_work_centers':sum(row['status']=='near_capacity' for row in items),
            'orders_in_scope':len(orders_in_scope),'at_risk_orders':len({order['order_id'] for row in items
                for order in row['orders'] if order['at_risk']}),'coverage_gaps':len(gaps),
            'missing_standard_quantity':sum(row['quantity'] for row in gaps),
            'required_minutes':self._capacity_minutes(sum(int(Decimal(row['required_minutes'])*1000)
                                                          for row in items)),
            'available_minutes':sum(row['available_minutes'] for row in items)}
        return {'as_of':as_of_date.isoformat(),'horizon_days':horizon_days,
            'horizon_end':horizon_end.isoformat(),'warning_percent':warning_percent,
            'work_center_id':work_center_id,'stage':stage,'status':status,'timezone':'Asia/Jakarta',
            'ledger_basis':'current_production_balances','route_basis':'remaining_standard_route',
            'calendar_basis':'weekday_default_with_latest_date_override',
            'capacity_complete':not gaps,'total':len(scoped),'limit':limit,'offset':offset,
            'summary':summary,'coverage_gaps':gaps,'items':scoped[offset:offset+limit]}

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
