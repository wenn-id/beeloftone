import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase
from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_materials


class PurchaseRequestTest(TestCase):
    setUp = test_materials.MaterialsTest.setUp
    post = test_materials.MaterialsTest.post
    material = test_materials.MaterialsTest.material
    order = test_materials.MaterialsTest.order

    def payload(self, material, **changes):
        return dict(reference='PR-001', order_id=None, required_date='2026-10-01',
                    estimated_value='123456.78', reason='Persiapan cutting',
                    lines=[dict(material_id=material['id'], quantity='2.125')]) | changes

    def create(self, payload, **options):
        return self.post('/api/purchase-requests', payload, **options)

    def detail(self, request):
        response = self.client.get('/api/purchase-requests/'+request['id'])
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def decide(self, request, decision, **options):
        return self.post('/api/purchase-requests/'+request['id']+'/decisions',
                         dict(status=decision, expected_revision=request['revision'], reason='Diperiksa'), **options)

    def test_lifecycle_retry_exact_amounts_and_no_inventory_effect(self):
        material, order = self.material(), self.order()
        before = self.client.get('/api/orders/'+order['id']).json()
        payload = self.payload(material, order_id=order['id'])
        request = self.create(payload, key='pr-once', api_key=self.operator['api_key'])
        self.assertEqual(request, self.create(payload, key='pr-once', api_key=self.operator['api_key']))
        self.assertEqual(request['lines'][0]['quantity'], '2.125')
        self.assertEqual(request['estimated_value'], '123456.78')
        self.assertEqual(request['status'], 'submitted')
        approved = self.decide(request, 'approved', key='approve')
        self.assertEqual(approved, self.decide(request, 'approved', key='approve'))
        self.assertEqual(approved['status'], 'approved')
        self.decide(request, 'rejected', status=409)
        cancelled = self.decide(approved, 'cancelled')
        self.decide(cancelled, 'approved', status=409)
        self.assertEqual([e['status'] for e in self.detail(request)['history']], ['cancelled','approved','submitted'])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json(), before)
        self.assertEqual(self.client.get('/api/material-batches').json(), [])
        self.assertEqual(request, self.create(payload, key='pr-once', api_key=self.operator['api_key']))
        self.create(payload | {'reason':'Berbeda'}, key='pr-once', api_key=self.operator['api_key'], status=409)

    def test_validation_normalization_permissions_and_terminal_decisions(self):
        material = self.material()
        payload = self.payload(material)
        self.create(payload, api_key=self.viewer['api_key'], status=403)
        for changes in [
            {'lines':[]}, {'lines':payload['lines']*2}, {'lines':[dict(material_id=material['id'],quantity='0')]},
            {'estimated_value':1}, {'estimated_value':'0'}, {'estimated_value':'1.001'},
            {'estimated_value':'NaN'}, {'estimated_value':'1000000000000.01'},
            {'reason':' '}, {'required_date':'bad'}, {'order_id':'missing'},
        ]:
            self.create(payload | changes, status=404 if changes.get('order_id') else 422)
        self.create(payload | {'lines':[dict(material_id='missing',quantity='1')]}, status=404)
        pcs = self.material('BUTTON','pcs')
        self.create(payload | {'lines':[dict(material_id=pcs['id'],quantity='0.5')]}, status=422)
        a = self.create(payload | {'estimated_value':'2', 'lines':[dict(material_id=pcs['id'],quantity='2')]}, key='normalized')
        self.assertEqual(a, self.create(payload | {'estimated_value':'2.00','lines':[dict(material_id=pcs['id'],quantity='2.000')]}, key='normalized'))
        self.create(payload, status=409)
        self.decide(a, 'approved', api_key=self.operator['api_key'], status=403)
        self.decide(a, 'cancelled', api_key=self.operator['api_key'], status=403)
        own = self.create(payload | {'reference':'PR-OWN'}, api_key=self.operator['api_key'])
        self.decide(own, 'cancelled', api_key=self.operator['api_key'])
        rejected = self.decide(a, 'rejected')
        self.decide(rejected, 'cancelled', status=409)
        for path in ['/api/purchase-requests', '/api/purchase-requests/'+a['id']]:
            self.assertEqual(self.client.get(path,headers={'X-API-Key':self.viewer['api_key']}).status_code,200)
            self.assertEqual(self.client.get(path,headers={'X-API-Key':'bad'}).status_code,401)

    def test_concurrent_decisions_and_atomic_rollback(self):
        request = self.create(self.payload(self.material()))
        barrier = Barrier(2)
        def decide(status):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/purchase-requests/'+request['id']+'/decisions',
                    json=dict(status=status,expected_revision=request['revision'],reason='Diperiksa'),
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':status}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(decide,['approved','rejected'])),[201,409])
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_pr BEFORE INSERT ON requests WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT,'test'); END")
        other = self.create(self.payload(self.material('SECOND'), reference='PR-SECOND'))
        self.decide(other,'approved',key='fail',status=409)
        self.assertEqual(self.detail(other)['status'],'submitted')
        self.assertEqual(len(self.detail(other)['history']),1)
        failed_payload = self.payload(self.material('THIRD'), reference='PR-ROLLED-BACK')
        self.create(failed_payload, key='fail', status=409)
        self.assertEqual(len(self.client.get('/api/purchase-requests').json()),2)
        self.create(failed_payload)

    def test_migration_backup_history_and_cursor(self):
        material, order = self.material(), self.order()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE IF EXISTS purchase_request_events')
            db.execute('DROP TABLE IF EXISTS purchase_requests')
            db.execute('PRAGMA user_version=7')
            db.commit()
        Store(self.path); Store(self.path)
        a = self.create(self.payload(material, order_id=order['id']))
        b = self.create(self.payload(material,reference='PR-B'))
        route = '/api/purchase-requests'
        page = self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'], b['id'])
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],a['id'])
        self.assertEqual(len(self.client.get(route+'?order_id='+order['id']).json()),1)
        self.decide(a,'approved')
        self.assertEqual(self.client.get(route+'?status=submitted').json()[0]['id'],b['id'])
        self.assertEqual(self.client.get(route+'?status=invalid').status_code,422)
        self.assertEqual(self.client.get(route+'?limit=0').status_code,422)
        self.assertEqual(self.client.get(route+'/missing').status_code,404)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],28)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("""INSERT INTO purchase_request_events(request_id,status,reason,actor_id,created_at)
                    VALUES(?,'submitted','Repeat',?,'2026-10-01')""",(a['id'],self.admin['id']))
            for table in ['purchase_requests','purchase_request_events']:
                for sql in ['DELETE FROM '+table,'UPDATE '+table+' SET reason=reason']:
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
        backup = self.path.parent/'pr-backup.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).purchase_request(a['id']),self.detail(a))

    def test_maximum_estimate_and_decision_validation(self):
        payload = self.payload(self.material(), estimated_value='1000000000000.00')
        request = self.create(payload)
        self.assertEqual(request['estimated_value'], '1000000000000.00')
        for changes in [{'status':'submitted'},{'expected_revision':True},{'expected_revision':0},{'reason':' '}]:
            self.post('/api/purchase-requests/'+request['id']+'/decisions',
                      dict(status='approved',expected_revision=request['revision'],reason='Review') | changes,status=422)
        self.app.state.store.disable_user(self.admin['id'])
        self.create(payload, key='revoked', status=401)
