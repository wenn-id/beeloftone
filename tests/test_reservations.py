import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase
from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_materials


class ReservationTest(TestCase):
    setUp=test_materials.MaterialsTest.setUp
    post=test_materials.MaterialsTest.post
    order=test_materials.MaterialsTest.order
    material=test_materials.MaterialsTest.material
    receipt=test_materials.MaterialsTest.receipt
    batch=test_materials.MaterialsTest.batch

    def setup_stock(self):
        material=self.material()
        batch=self.post('/api/material-batches',self.receipt(material,quantity='10'))
        return batch,self.order(),self.order()

    def reserve(self,batch,order,quantity='6',action='reserve',**options):
        return self.post('/api/material-reservations',dict(batch_id=batch['id'],order_id=order['id'],
            quantity=quantity,action=action,reason='Alokasi cutting'),**options)

    def issue(self,batch,order,quantity,**options):
        return self.post('/api/material-issues',dict(batch_id=batch['id'],order_id=order['id'],
            quantity=quantity,reason='Cutting'),**options)

    def test_protection_consumption_release_and_reversal(self):
        batch,a,b=self.setup_stock()
        first=self.reserve(batch,a,key='reserve-once')
        self.assertEqual(first,self.reserve(batch,a,key='reserve-once'))
        self.reserve(batch,a,'7',key='reserve-once',status=409)
        self.assertEqual([self.batch(batch['id'])[k] for k in ['balance','reserved','available']],['10.000','6.000','4.000'])
        self.issue(batch,b,'4.001',status=409)
        own=self.issue(batch,a,'2.125',key='reserved-issue-once',api_key=self.operator['api_key'])
        self.assertEqual(own,self.issue(batch,a,'2.125',key='reserved-issue-once',api_key=self.operator['api_key']))
        self.assertEqual([self.batch(batch['id'])[k] for k in ['balance','reserved','available']],['7.875','3.875','4.000'])
        self.issue(batch,b,'4')
        self.reserve(batch,b,'0.001',status=409)
        self.reserve(batch,a,'1.125',action='release')
        self.assertEqual(self.batch(batch['id'])['available'],'1.125')
        self.post('/api/material-movements/'+own['id']+'/reverse',{'reason':'Kembali'})
        self.assertEqual([self.batch(batch['id'])[k] for k in ['balance','reserved','available']],['6.000','2.750','3.250'])
        self.reserve(batch,a,'2.751',action='release',status=409)
        self.reserve(batch,a,'2.750',action='release')
        report=self.client.get('/api/orders/'+a['id']+'/material-reservations').json()
        self.assertEqual(report[0]['reserved'],'0.000')
        events=self.client.get('/api/orders/'+a['id']+'/reservation-history').json()
        self.assertEqual({e['kind'] for e in events},{'reserve','release','consume'})
        self.assertEqual(next(e for e in events if e['kind']=='consume')['movement_id'],own['id'])

    def test_own_plus_free_receipt_protection_and_requirement_math(self):
        batch,a,b=self.setup_stock()
        self.reserve(batch,a,'3')
        self.reserve(batch,b,'4')
        self.post('/api/material-movements/'+batch['receipt_id']+'/reverse',{'reason':'Salah batch'},status=409)
        material=self.client.get('/api/materials').json()[0]
        self.post('/api/products/'+self.product['id']+'/bom',dict(expected_revision=0,reason='Standar',
            components=[dict(material_id=material['id'],quantity='0.1')]))
        row=self.client.get('/api/orders/'+a['id']+'/material-requirements').json()['materials'][0]
        self.assertEqual([row[k] for k in ['required','stock','reserved_own','reserved_other','available','available_to_order','shortage']],
                         ['10.000','10.000','3.000','4.000','3.000','6.000','4.000'])
        self.issue(batch,a,'6.001',status=409)
        self.issue(batch,a,'5')
        self.assertEqual([self.batch(batch['id'])[k] for k in ['balance','reserved','available']],['5.000','4.000','1.000'])
        viewed=self.client.get('/api/material-batches?order_id='+b['id']).json()[0]
        self.assertEqual(viewed['available_to_order'],'5.000')
        self.assertEqual(viewed['reserved_for_order'],'4.000')

    def test_permissions_validation_cursor_and_atomic_rollback(self):
        batch,a,b=self.setup_stock()
        for user,status in [(self.operator,403),(self.viewer,403)]:
            self.reserve(batch,a,api_key=user['api_key'],status=status)
        self.reserve(batch,a,'0',status=422)
        self.reserve(batch,a,action='invalid',status=422)
        self.reserve(batch,dict(id='missing'),status=404)
        self.reserve(dict(id='missing'),a,status=404)
        first=self.reserve(batch,a,'6')
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_reservation BEFORE INSERT ON requests WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.issue(batch,a,'2',key='fail',status=409)
        self.reserve(batch,a,'1',action='release',key='fail',status=409)
        self.assertEqual(self.batch(batch['id'])['reserved'],'6.000')
        self.assertEqual(self.batch(batch['id'])['balance'],'10.000')
        estimate=self.client.get('/api/orders/'+a['id']+'/material-requirements').json()
        self.assertFalse(estimate['complete'])
        self.assertTrue(estimate['materials'][0]['outside_bom'])
        self.assertEqual(estimate['materials'][0]['reserved_own'],'6.000')
        self.assertEqual(len(self.client.get('/api/material-batches/'+batch['id']+'/movements').json()),1)
        self.reserve(batch,a,'1',action='release')
        route='/api/orders/'+a['id']+'/reservation-history'
        page=self.client.get(route+'?limit=1').json()
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],first['id'])
        for path in [route,'/api/orders/'+a['id']+'/material-reservations']:
            self.assertEqual(self.client.get(path,headers={'X-API-Key':self.viewer['api_key']}).status_code,200)
            self.assertEqual(self.client.get(path,headers={'X-API-Key':'bad'}).status_code,401)

    def test_simultaneous_reserve_and_issue_do_not_take_same_stock(self):
        batch,a,b=self.setup_stock()
        barrier=Barrier(2)
        def write(index):
            with TestClient(create_app(self.path)) as client:
                body=dict(batch_id=batch['id'],order_id=[a,b][index]['id'],quantity='6',reason='Bersamaan')
                if index==0: body['action']='reserve'
                barrier.wait(timeout=10)
                return client.post(['/api/material-reservations','/api/material-issues'][index],json=body,
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':'parallel-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(write,range(2))),[201,409])
        self.assertEqual(self.batch(batch['id'])['available'],'4.000')

    def test_upgrade_preserves_stock_and_reservation_history(self):
        batch,a,b=self.setup_stock()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE IF EXISTS material_reservation_events')
            db.execute('PRAGMA user_version=5');db.commit()
        Store(self.path);Store(self.path)
        self.assertEqual(self.batch(batch['id'])['balance'],'10.000')
        self.reserve(batch,a,'1.125')
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],24)
            for query in ['DELETE FROM material_reservation_events','UPDATE material_reservation_events SET reason=reason']:
                with self.assertRaises(sqlite3.IntegrityError):db.execute(query)
        backup=self.path.parent/'restore.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).material_batch(batch['id'])['reserved'],'1.125')
