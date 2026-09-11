import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_production


class MaterialsTest(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order
    detail = test_production.ProductionTest.detail

    def material(self, code='KAIN-BIRU', unit='m'):
        return self.post('/api/materials', dict(code=code, name='Katun biru', unit=unit))

    def receipt(self, material, **changes):
        return dict(material_id=material['id'], reference='BATCH-001', supplier='Toko kain',
                    location='Rak A1', received_date='2026-09-11', quantity='10.125',
                    reason='Diterima setelah diperiksa') | changes

    def batch(self, batch_id):
        response = self.client.get('/api/material-batches/' + batch_id)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_receive_issue_reverse_and_trace_order_without_changing_wip(self):
        material = self.material()
        order = self.order()
        body = self.receipt(material)
        received = self.post('/api/material-batches', body, key='receipt', api_key=self.operator['api_key'])
        self.assertEqual(received, self.post('/api/material-batches', body, key='receipt', api_key=self.operator['api_key']))
        self.post('/api/material-batches', body | {'quantity':'11'}, key='receipt', status=409, api_key=self.operator['api_key'])
        issued = self.post('/api/material-issues', dict(batch_id=received['id'], order_id=order['id'], quantity='0.125', reason='Untuk cutting'), key='issue')
        self.assertEqual(self.batch(received['id'])['balance'], '10.000')
        route = '/api/material-movements/' + issued['id'] + '/reverse'
        reversal = self.post(route, {'reason':'Bahan belum dipakai, kembali ke rak'}, key='reverse')
        self.assertEqual(reversal, self.post(route, {'reason':'Bahan belum dipakai, kembali ke rak'}, key='reverse'))
        self.post(route, {'reason':'Ulang'}, status=409)
        self.post('/api/material-movements/' + reversal['id'] + '/reverse', {'reason':'Balik lagi'}, status=409)
        self.assertEqual(self.batch(received['id'])['balance'], '10.125')
        rows = self.client.get('/api/orders/' + order['id'] + '/material-movements').json()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['batch_reference'] for r in rows}, {'BATCH-001'})
        self.assertEqual(rows[0]['reversal_of'], issued['id'])
        self.assertEqual(rows[1]['reversed_by'], reversal['id'])
        self.assertEqual(self.detail(order)['totals'], order['totals'])

    def test_validation_units_duplicates_and_permissions(self):
        body = dict(code=' zip ', name='Resleting', unit='pcs')
        self.post('/api/materials', body, api_key=self.operator['api_key'], status=403)
        material = self.post('/api/materials', body)
        self.assertEqual(material['code'], 'ZIP')
        self.post('/api/materials', body | {'code':'ZIP'}, status=409)
        self.post('/api/materials', body | {'unit':'roll'}, status=422)
        receipt = self.receipt(material, quantity='2')
        for value in ['0', '-1', '1.0001', 'NaN', 'Infinity', '1e3', '1,5', '1000000.001', True, 1.2]:
            self.post('/api/material-batches', receipt | {'quantity':value}, status=422)
        self.post('/api/material-batches', receipt | {'quantity':'1.5'}, status=422)
        self.post('/api/material-batches', receipt | {'location':' '}, status=422)
        self.post('/api/material-batches', receipt | {'material_id':'missing'}, status=404)
        self.post('/api/material-batches', receipt, api_key=self.viewer['api_key'], status=403)
        batch = self.post('/api/material-batches', receipt)
        self.post('/api/material-batches', receipt, status=409)
        order = self.order()
        issue = dict(batch_id=batch['id'], order_id=order['id'], quantity='1', reason='Cutting')
        self.post('/api/material-issues', issue, api_key=self.viewer['api_key'], status=403)
        self.post('/api/material-issues', issue | {'quantity':'0.5'}, status=422)
        self.post('/api/material-issues', issue | {'reason':' '}, status=422)
        self.post('/api/material-issues', issue | {'order_id':'missing'}, status=404)
        movement = self.post('/api/material-issues', issue)
        self.post('/api/material-movements/' + movement['id'] + '/reverse', {'reason':'Salah'}, api_key=self.operator['api_key'], status=403)
        for path in ['/api/materials', '/api/material-batches', '/api/material-batches/'+batch['id'],
                     '/api/material-batches/'+batch['id']+'/movements', '/api/orders/'+order['id']+'/material-movements']:
            self.assertEqual(self.client.get(path, headers={'X-API-Key':self.viewer['api_key']}).status_code, 200)
            self.assertEqual(self.client.get(path, headers={'X-API-Key':'invalid'}).status_code, 401)

    def test_insufficient_stock_receipt_reversal_and_cursor(self):
        batch = self.post('/api/material-batches', self.receipt(self.material(), quantity='1'))
        order = self.order()
        body = dict(batch_id=batch['id'], order_id=order['id'], quantity='0.6', reason='Cutting')
        issued = self.post('/api/material-issues', body, key='once')
        self.post('/api/material-issues', body, status=409)
        self.assertEqual(issued, self.post('/api/material-issues', body, key='once'))
        first = self.client.get('/api/material-batches/'+batch['id']+'/movements?limit=1').json()[0]
        receipt_id = batch['receipt_id']
        self.post('/api/material-movements/'+receipt_id+'/reverse', {'reason':'Salah terima'}, status=409)
        self.post('/api/material-movements/'+issued['id']+'/reverse', {'reason':'Kembali'})
        older = self.client.get('/api/material-batches/'+batch['id']+'/movements?before='+str(first['sequence'])).json()
        self.assertEqual([r['id'] for r in older], [receipt_id])
        self.post('/api/material-movements/'+receipt_id+'/reverse', {'reason':'Salah terima'})
        self.assertEqual(self.batch(batch['id'])['balance'], '0.000')
        self.post('/api/material-issues', body, status=409)

    def test_simultaneous_issues_cannot_overdraw(self):
        batch = self.post('/api/material-batches', self.receipt(self.material(), quantity='1'))
        order = self.order()
        barrier = Barrier(2)
        def issue(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/material-issues', json=dict(batch_id=batch['id'], order_id=order['id'], quantity='0.6', reason='Cutting'),
                    headers={'X-API-Key':self.admin['api_key'], 'Idempotency-Key':'concurrent-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(issue, range(2))), [201, 409])
        self.assertEqual(self.batch(batch['id'])['balance'], '0.400')

    def test_migration_preserves_production_and_ledger_is_immutable(self):
        order = self.order()
        with closing(sqlite3.connect(self.path)) as db:
            for table in ['material_movements', 'material_batches', 'materials']:
                db.execute('DROP TABLE IF EXISTS '+table)
            db.execute('PRAGMA user_version=3')
            db.commit()
        Store(self.path)
        Store(self.path)
        self.assertEqual(self.detail(order), order)
        batch = self.post('/api/material-batches', self.receipt(self.material()))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 15)
            for table in ['materials','material_batches','material_movements']:
                for query in ['DELETE FROM '+table, 'UPDATE '+table+' SET id=id']:
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(query)
        Store(self.path)
        self.assertEqual(self.batch(batch['id'])['balance'], '10.125')

    def test_receipt_rollback_batch_filter_and_backup_restore(self):
        material = self.material()
        other = self.material('BENANG', 'kg')
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_material_receipt BEFORE INSERT ON requests WHEN NEW.key='rollback' BEGIN SELECT RAISE(ABORT,'test failure'); END")
        body = self.receipt(material)
        self.post('/api/material-batches', body, key='rollback', status=409)
        self.assertEqual(self.client.get('/api/material-batches').json(), [])
        with self.app.state.store.transaction(write=True) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM material_movements').fetchone()[0], 0)
            db.execute('DROP TRIGGER fail_material_receipt')
        batch = self.post('/api/material-batches', body, key='rollback')
        self.post('/api/material-batches', self.receipt(other, reference='BATCH-002', quantity='0.001'))
        rows = self.client.get('/api/material-batches?material_id='+material['id']).json()
        self.assertEqual([r['id'] for r in rows], [batch['id']])
        self.assertEqual(len(self.client.get('/api/material-batches?limit=1&offset=1').json()), 1)
        backup = self.path.parent / 'backup.sqlite3'
        self.app.state.store.backup(backup)
        restored = Store(backup)
        self.assertEqual(restored.material_batch(batch['id'])['balance'], '10.125')
        self.assertEqual(restored.material_history(batch_id=batch['id'])[0]['actor_id'], self.admin['id'])
