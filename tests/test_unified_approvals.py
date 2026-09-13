import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store
import test_order_changes


class UnifiedApprovalsTest(TestCase):
    setUp = test_order_changes.OrderChangeTest.setUp
    post = test_order_changes.OrderChangeTest.post
    order = test_order_changes.OrderChangeTest.order

    def request(self, order, reference='PCR-001', **options):
        payload = dict(reference=reference, owner_id=self.admin['id'], due_date='2099-01-01',
                       expected_revision=order['revision'], reason='Jadwal produksi perlu disesuaikan')
        payload.update(options.pop('changes', {}))
        return self.post('/api/orders/'+order['id']+'/change-requests', payload,
                         api_key=options.pop('api_key', self.operator['api_key']), **options)

    def decide(self, request, decision='approved', **options):
        payload = dict(status=decision, expected_revision=request['revision'], reason='Keputusan manajemen')
        payload.update(options.pop('changes', {}))
        return self.post('/api/production-change-requests/'+request['id']+'/decisions', payload, **options)

    def purchase_request(self, order):
        material = self.post('/api/materials', dict(code='APP-CLOTH', name='Kain approval', unit='m'))
        return self.post('/api/purchase-requests', dict(reference='PR-APPROVAL', order_id=order['id'],
            required_date='2099-01-10', estimated_value='2500000.00', reason='Bahan untuk produksi',
            lines=[dict(material_id=material['id'], quantity='5')]), api_key=self.operator['api_key'])

    def test_unified_queue_combines_purchase_and_production_without_applying_request(self):
        order = self.order()
        purchase = self.purchase_request(order)
        production = self.request(order, key='production-request')
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json(), order)
        queue = self.client.get('/api/approvals').json()
        self.assertEqual({row['kind'] for row in queue}, {'purchase_request','production_change'})
        by_kind = {row['kind']:row for row in queue}
        self.assertEqual(by_kind['purchase_request']['amount'], '2500000.00')
        self.assertEqual(by_kind['purchase_request']['id'], purchase['id'])
        self.assertEqual(by_kind['production_change']['id'], production['id'])
        self.assertEqual(by_kind['production_change']['context']['new_owner_name'], self.admin['name'])
        self.assertEqual(self.client.get('/api/approvals?kind=production_change').json()[0]['id'], production['id'])
        self.assertEqual(self.client.get('/api/approvals?kind=purchase_request').json()[0]['id'], purchase['id'])
        self.assertEqual(len(self.client.get('/api/approvals?limit=1&offset=1').json()), 1)
        self.assertEqual(self.client.get('/api/approvals?status=approved').json(), [])
        listed = self.client.get('/api/orders/'+order['id']+'/change-requests').json()
        self.assertEqual(listed[0]['id'], production['id'])
        self.assertEqual(self.client.get('/api/production-change-requests/'+production['id']).json(), production)
        self.assertEqual(self.client.get('/api/approvals', headers={'X-API-Key':self.viewer['api_key']}).status_code, 200)

    def test_approval_applies_order_change_and_links_existing_audit(self):
        order = self.order()
        request = self.request(order, key='request-once')
        approved = self.decide(request, key='approve-once')
        self.assertEqual(approved, self.decide(request, key='approve-once'))
        self.assertEqual(approved['status'], 'approved')
        self.assertIsNotNone(approved['history'][0]['order_change_id'])
        current = self.client.get('/api/orders/'+order['id']).json()
        self.assertEqual((current['due_date'],current['owner_id']), ('2099-01-01',self.admin['id']))
        changes = self.client.get('/api/orders/'+order['id']+'/changes').json()
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['id'], approved['history'][0]['order_change_id'])
        self.assertEqual(changes[0]['reason'], request['reason'])
        self.assertEqual(changes[0]['actor_id'], self.admin['id'])
        self.assertEqual(self.client.get('/api/approvals?status=approved&kind=production_change').json()[0]['id'], request['id'])
        self.decide(approved, 'rejected', status=409)

    def test_roles_cancellation_rejection_and_validation(self):
        order = self.order()
        self.request(order, api_key=self.viewer['api_key'], status=403)
        for changes in ({'reference':' '},{'expected_revision':True},{'expected_revision':-1},
                        {'due_date':'invalid'},{'owner_id':self.viewer['id']},{'owner_id':'missing'},
                        {'owner_id':order['owner_id'],'due_date':order['due_date']},{'extra':'bad'}):
            self.request(order, changes=changes, status=422)
        request = self.request(order)
        self.request(order, reference='PCR-PENDING', status=409)
        other = self.app.state.store.provision_user('Operator lain', 'operator')
        self.decide(request, 'approved', api_key=self.operator['api_key'], status=403)
        self.decide(request, 'cancelled', api_key=other['api_key'], status=403)
        cancelled = self.decide(request, 'cancelled', api_key=self.operator['api_key'])
        self.assertEqual(cancelled['status'], 'cancelled')
        next_request = self.request(order, reference='PCR-REJECT')
        rejected = self.decide(next_request, 'rejected')
        self.assertEqual(rejected['status'], 'rejected')
        self.assertEqual(self.client.get('/api/approvals?status=cancelled').json()[0]['id'], request['id'])
        self.assertEqual(self.client.get('/api/approvals?status=rejected').json()[0]['id'], next_request['id'])
        for changes in ({'status':'submitted'},{'expected_revision':True},{'expected_revision':0},{'reason':' '}):
            self.decide(rejected, changes=changes, status=422)
        self.assertEqual(self.client.get('/api/production-change-requests/missing').status_code, 404)
        self.assertEqual(self.client.get('/api/orders/missing/change-requests').status_code, 404)
        self.assertEqual(self.client.get('/api/approvals?kind=bad').status_code, 422)

    def test_stale_request_cannot_overwrite_newer_order_change(self):
        order = self.order()
        request = self.request(order)
        changed = self.post('/api/orders/'+order['id']+'/changes', dict(owner_id=order['owner_id'],
            due_date='2099-02-01', expected_revision=order['revision'], reason='Perubahan langsung admin'))
        stale = self.client.get('/api/production-change-requests/'+request['id']).json()
        self.assertTrue(stale['stale'])
        self.decide(stale, status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json(), changed)
        rejected = self.decide(stale, 'rejected')
        self.assertEqual(rejected['status'], 'rejected')

    def test_concurrent_decisions_and_atomic_rollback(self):
        order = self.order()
        request = self.request(order)
        barrier = Barrier(2)
        def decide(status):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/production-change-requests/'+request['id']+'/decisions',
                    json=dict(status=status,expected_revision=request['revision'],reason='Keputusan bersamaan'),
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':status}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(decide,['approved','rejected'])), [201,409])

        order2 = self.order(reference='PROD-ROLLBACK')
        request2 = self.request(order2, reference='PCR-ROLLBACK')
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_approval BEFORE INSERT ON requests WHEN NEW.key='approval-fail' BEGIN SELECT RAISE(ABORT,'fail'); END")
        self.decide(request2, key='approval-fail', status=409)
        self.assertEqual(self.client.get('/api/orders/'+order2['id']).json(), order2)
        self.assertEqual(self.client.get('/api/production-change-requests/'+request2['id']).json()['status'], 'submitted')
        with self.app.state.store.transaction(write=True) as db:
            db.execute('DROP TRIGGER fail_approval')
        self.decide(request2, key='approval-fail')

    def test_immutable_backup_and_migration_from_25(self):
        order = self.order()
        request = self.request(order)
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('production_change_requests','production_change_request_events'):
                for sql in ('UPDATE '+table+' SET reason=reason','DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("""INSERT INTO production_change_request_events(request_id,status,reason,actor_id,created_at)
                    VALUES(?,'submitted','Repeat',?,'2026-09-12')""", (request['id'],self.admin['id']))
        backup = self.path.parent/'approval-backup.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).production_change_request(request['id']), request)

        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE production_change_request_events')
            db.execute('DROP TABLE production_change_requests')
            db.execute('PRAGMA user_version=25')
            db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],44)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM production_change_requests').fetchone()[0],0)
