import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import TestCase

import test_consumption as consumption_tests
from beeloft.store import Store


class CuttingTest(TestCase):
    setUp = consumption_tests.ConsumptionTest.setUp
    post = consumption_tests.ConsumptionTest.post
    order = consumption_tests.ConsumptionTest.order
    material = consumption_tests.ConsumptionTest.material
    receipt = consumption_tests.ConsumptionTest.receipt
    issue = consumption_tests.ConsumptionTest.issue
    setup_stock = consumption_tests.ConsumptionTest.setup_stock

    def prepare(self):
        batch, order, other = self.setup_stock()
        issue = self.issue(batch, order, '6')
        line = order['lines'][0]['id']
        self.post('/api/movements',dict(line_id=line,from_stage='planned',to_stage='cutting',quantity=30))
        return batch,order,other,dict(reference='CUT-001',issue_id=issue['id'],used='2.125',waste='0.375',
                                    reason='Potongan selesai',outputs=[dict(line_id=line,quantity=20)])

    def cut(self, order, body, **options):
        return self.post('/api/orders/'+order['id']+'/cutting-runs',body,**options)

    def reverse_cut(self, run, **options):
        return self.post('/api/cutting-runs/'+run['id']+'/reverse',dict(reason='Hasil cutting salah catat'),**options)

    def detail(self, run):
        response=self.client.get('/api/cutting-runs/'+run['id'])
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_output_links_material_usage_waste_and_wip_once(self):
        batch,order,_,body=self.prepare()
        result=self.cut(order,body,key='cut',api_key=self.operator['api_key'])
        self.assertEqual(result,self.cut(order,body,key='cut',api_key=self.operator['api_key']))
        self.assertEqual(result['used'],'2.125')
        self.assertEqual(result['waste'],'0.375')
        self.assertEqual(result['batch_id'],batch['id'])
        self.assertEqual(result['total_output'],20)
        self.assertEqual(result['outputs'][0]['sku'],self.product['sku'])
        current=self.client.get('/api/orders/'+order['id']).json()
        self.assertEqual((current['totals']['cutting'],current['totals']['sewing']),(10,20))
        self.assertEqual(sum(current['totals'].values()),order['target_quantity'])
        self.assertEqual(self.client.get('/api/material-batches/'+batch['id']).json()['balance'],'4.000')
        issue=self.client.get('/api/orders/'+order['id']+'/material-consumption').json()[0]
        self.assertEqual(issue['unreported'],'3.500')
        history=self.client.get('/api/orders/'+order['id']+'/consumption-history').json()
        self.assertEqual(history[0]['cutting_run_id'],result['id'])
        movements=self.client.get('/api/orders/'+order['id']+'/movements').json()
        self.assertEqual(movements[-1]['cutting_run_id'],result['id'])

    def test_correction_is_atomic_and_blocks_independent_reversals(self):
        _,order,_,body=self.prepare()
        run=self.cut(order,body)
        self.post('/api/material-consumption/'+run['consumption_id']+'/reverse',dict(reason='Terpisah'),status=409)
        output=run['outputs'][0]
        self.post('/api/movements/'+output['id']+'/reverse',dict(reason='Terpisah'),status=409)
        onward=self.post('/api/movements',dict(line_id=output['line_id'],from_stage='sewing',to_stage='finishing',quantity=15))
        self.reverse_cut(run,status=409)
        self.assertIsNone(self.detail(run)['reversal'])
        issue=self.client.get('/api/orders/'+order['id']+'/material-consumption').json()[0]
        self.assertEqual(issue['unreported'],'3.500')
        self.post('/api/movements/'+onward['id']+'/reverse',dict(reason='Kembali ke sewing'))
        reversed_run=self.reverse_cut(run,key='undo')
        self.assertEqual(reversed_run,self.reverse_cut(run,key='undo'))
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals']['cutting'],30)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/material-consumption').json()[0]['unreported'],'6.000')
        self.reverse_cut(run,status=409)
        self.assertEqual(self.detail(run)['total_output'],20)
        self.assertIsNotNone(self.detail(run)['reversal'])

    def test_validation_roles_cross_order_and_rollback(self):
        _,order,other,body=self.prepare()
        self.cut(order,body,api_key=self.viewer['api_key'],status=403)
        self.cut(other,body,status=422)
        for changes,status in [({'outputs':[]},422),({'outputs':body['outputs']*2},422),
                               ({'used':'0'},422),({'used':'6','waste':'1'},409),
                               ({'outputs':[dict(line_id=body['outputs'][0]['line_id'],quantity=True)]},422),
                               ({'outputs':[dict(line_id=other['lines'][0]['id'],quantity=1)]},422),
                               ({'outputs':[dict(line_id=body['outputs'][0]['line_id'],quantity=31)]},409)]:
            self.cut(order,body | changes,status=status)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_cut BEFORE INSERT ON requests WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.cut(order,body,key='fail',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/cutting-runs').json(),[])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals']['cutting'],30)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/material-consumption').json()[0]['unreported'],'6.000')
        run=self.cut(order,body)
        for role in (self.operator,self.viewer):
            self.reverse_cut(run,api_key=role['api_key'],status=403)
        self.cut(order,body,status=409)
        self.assertEqual(len(self.client.get('/api/orders/'+order['id']+'/cutting-runs').json()),1)

    def test_multi_size_output_and_rollback_when_one_size_is_short(self):
        batch,order,_,body=self.prepare()
        second=self.post('/api/products',dict(sku='LUNA-L',name='Luna',size='L',color='Blue'))
        multi=self.order(lines=[dict(product_id=self.product['id'],quantity=30),dict(product_id=second['id'],quantity=10)])
        issue=self.issue(batch,multi,'3')
        for line in multi['lines']:
            self.post('/api/movements',dict(line_id=line['id'],from_stage='planned',to_stage='cutting',quantity=line['quantity']))
        payload=body | dict(issue_id=issue['id'],outputs=[dict(line_id=l['id'],quantity=l['quantity']) for l in multi['lines']])
        bad=payload | dict(outputs=[payload['outputs'][0],payload['outputs'][1] | dict(quantity=11)])
        self.cut(multi,bad,status=409)
        self.assertEqual(self.client.get('/api/orders/'+multi['id']).json()['totals']['sewing'],0)
        result=self.cut(multi,payload)
        self.assertEqual(result['total_output'],40)
        self.assertEqual({x['size'] for x in result['outputs']},{'M','L'})
        self.reverse_cut(result)
        self.assertEqual(self.client.get('/api/orders/'+multi['id']).json()['totals']['cutting'],40)

    def test_race_cannot_overconsume_or_overdraw_cutting(self):
        _,order,_,body=self.prepare()
        barrier=Barrier(2)
        def save(i):
            barrier.wait(timeout=10)
            return self.client.post('/api/orders/'+order['id']+'/cutting-runs',json=body | dict(reference=f'CUT-{i}'),
                                    headers={'Idempotency-Key':f'cut-{i}'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals']['sewing'],20)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/material-consumption').json()[0]['unreported'],'3.500')

    def test_immutable_history_persistence_backup_and_cursor(self):
        _,order,_,body=self.prepare()
        run=self.cut(order,body | dict(outputs=[body['outputs'][0] | dict(quantity=5)]))
        second=self.cut(order,body | dict(reference='CUT-002',outputs=[body['outputs'][0] | dict(quantity=5)]))
        page=self.client.get('/api/orders/'+order['id']+'/cutting-runs?limit=1').json()
        self.assertEqual(page[0]['id'],second['id'])
        older=self.client.get('/api/orders/'+order['id']+'/cutting-runs?before='+str(page[0]['sequence'])).json()
        self.assertEqual(older[0]['id'],run['id'])
        with self.app.state.store.transaction(write=True) as db:
            for statement in ['DELETE FROM cutting_runs','UPDATE cutting_runs SET reason=reason']:
                with self.assertRaises(sqlite3.IntegrityError): db.execute(statement)
        backup=self.path.with_name('cutting-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).cutting_run(run['id']),self.detail(run))

    def test_upgrade_preserves_unlinked_records_and_sql_reversal_guard(self):
        _,order,_,body=self.prepare()
        old=self.post('/api/material-consumption',{k:body[k] for k in ['issue_id','used','waste','reason']})
        before=self.client.get('/api/orders/'+order['id']).json()
        with self.app.state.store.transaction(write=True) as db:
            db.execute('DROP TABLE cutting_run_reversals')
            db.execute('DROP TABLE cutting_runs')
            db.execute('PRAGMA user_version=12')
        Store(self.path)
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json(),before)
        history=self.client.get('/api/orders/'+order['id']+'/consumption-history').json()
        self.assertEqual(history[0]['id'],old['id'])
        self.assertIsNone(history[0]['cutting_run_id'])
        run=self.cut(order,body)
        with self.app.state.store.transaction(write=True) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO cutting_run_reversals(run_id,reason,actor_id,created_at) VALUES(?,?,?,?)',
                           (run['id'],'Koreksi tanpa ledger',self.admin['id'],'2026-09-11T00:00:00+00:00'))
        self.assertIsNone(self.detail(run)['reversal'])

    def test_piece_material_rejects_fractions_and_reversal_rollback(self):
        _,order,_,body=self.prepare()
        pieces=self.material(code='PCS-CUT',unit='pcs')
        batch=self.post('/api/material-batches',self.receipt(pieces,reference='PCS-BATCH',quantity='5'))
        issue=self.issue(batch,order,'5')
        self.cut(order,body | dict(issue_id=issue['id'],used='1.5',waste='0'),status=422)
        run=self.cut(order,body | dict(issue_id=issue['id'],used='2',waste='1'))
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_cut_reverse BEFORE INSERT ON requests WHEN NEW.key='fail-reverse' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.reverse_cut(run,key='fail-reverse',status=409)
        self.assertIsNone(self.detail(run)['reversal'])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals']['sewing'],20)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/material-consumption').json()[0]['unreported'],'2.000')
