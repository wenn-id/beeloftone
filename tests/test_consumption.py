import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase
from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_reservations


class ConsumptionTest(TestCase):
    setUp=test_reservations.ReservationTest.setUp
    post=test_reservations.ReservationTest.post
    order=test_reservations.ReservationTest.order
    material=test_reservations.ReservationTest.material
    receipt=test_reservations.ReservationTest.receipt
    issue=test_reservations.ReservationTest.issue
    setup_stock=test_reservations.ReservationTest.setup_stock

    def use(self,issue,used='2.125',waste='0.375',**options):
        return self.post('/api/material-consumption',dict(issue_id=issue['id'],used=used,waste=waste,reason='Cutting aktual'),**options)

    def report(self,order):
        response=self.client.get('/api/orders/'+order['id']+'/material-consumption')
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_partial_usage_waste_retry_and_reversal_keep_stock_and_wip(self):
        batch,order,_=self.setup_stock()
        issue=self.issue(batch,order,'6')
        before=self.client.get('/api/orders/'+order['id']).json()
        record=self.use(issue,key='usage-once',api_key=self.operator['api_key'])
        self.assertEqual(record,self.use(issue,key='usage-once',api_key=self.operator['api_key']))
        self.use(issue,'2','0',key='usage-once',api_key=self.operator['api_key'],status=409)
        row=self.report(order)[0]
        self.assertEqual([row[k] for k in ['issued','used','waste','unreported']],['6.000','2.125','0.375','3.500'])
        self.assertEqual(self.client.get('/api/material-batches/'+batch['id']).json()['balance'],'4.000')
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json(),before)
        self.use(issue,'3','0.501',status=409)
        route='/api/material-consumption/'+record['id']+'/reverse'
        reverse=self.post(route,dict(reason='Salah ukur'),key='usage-reverse')
        self.assertEqual(reverse,self.post(route,dict(reason='Salah ukur'),key='usage-reverse'))
        self.post(route,dict(reason='Ulang'),status=409)
        self.post('/api/material-consumption/'+reverse['id']+'/reverse',dict(reason='Balik'),status=409)
        self.assertEqual(self.report(order)[0]['unreported'],'6.000')
        history=self.client.get('/api/orders/'+order['id']+'/consumption-history').json()
        self.assertEqual(history[0]['reversal_of'],record['id'])
        self.assertEqual(history[1]['reversed_by'],reverse['id'])
        self.assertEqual(history[1]['actor_name'],self.operator['name'])

    def test_issue_reversal_guard_and_waste_only(self):
        batch,order,_=self.setup_stock()
        issue=self.issue(batch,order,'5')
        record=self.use(issue,'0','5')
        route='/api/material-movements/'+issue['id']+'/reverse'
        self.post(route,dict(reason='Kembali'),status=409)
        self.post('/api/material-consumption/'+record['id']+'/reverse',dict(reason='Waste keliru'))
        self.post(route,dict(reason='Seluruh bahan kembali'))
        self.use(issue,'1','0',status=409)
        row=self.report(order)[0]
        self.assertTrue(row['reversed_by'])
        self.assertEqual(row['unreported'],'0.000')
        self.assertEqual(row['issued'],'5.000')

    def test_validation_permissions_missing_and_units(self):
        batch,order,_=self.setup_stock()
        issue=self.issue(batch,order,'3')
        self.use(issue,api_key=self.viewer['api_key'],status=403)
        for used,waste in [('0','0'),('-1','0'),('NaN','0'),('1.0001','0'),('1','Infinity'),('1000000.001','0'),(1,'0'),(True,'0')]:
            self.use(issue,used,waste,status=422)
        self.use(dict(id='missing'),status=404)
        self.use(dict(id=batch['receipt_id']),status=422)
        record=self.use(issue,'1','0')
        self.post('/api/material-consumption/'+record['id']+'/reverse',dict(reason='Koreksi'),api_key=self.operator['api_key'],status=403)
        self.post('/api/material-consumption/'+record['id']+'/reverse',dict(reason=' '),status=422)
        material=self.material('LABEL','pcs')
        pieces=self.post('/api/material-batches',self.receipt(material,quantity='5',reference='LABEL-BATCH'))
        pieces_issue=self.issue(pieces,order,'4')
        self.use(pieces_issue,'1.125','0',status=422)
        self.use(pieces_issue,'1','0.125',status=422)
        for path in ['/api/orders/'+order['id']+'/material-consumption','/api/orders/'+order['id']+'/consumption-history']:
            self.assertEqual(self.client.get(path,headers={'X-API-Key':self.viewer['api_key']}).status_code,200)
            self.assertEqual(self.client.get(path,headers={'X-API-Key':'bad'}).status_code,401)

    def test_concurrent_usage_cannot_exceed_issue_and_rollback(self):
        batch,order,_=self.setup_stock()
        issue=self.issue(batch,order,'5')
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_usage BEFORE INSERT ON requests WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.use(issue,key='fail',status=409)
        self.assertEqual(self.report(order)[0]['unreported'],'5.000')
        barrier=Barrier(2)
        def use(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/material-consumption',json=dict(issue_id=issue['id'],used='3',waste='0',reason='Cutting'),
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':'parallel-use-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(use,range(2))),[201,409])
        self.assertEqual(self.report(order)[0]['unreported'],'2.000')

    def test_migration_backup_immutable_history_and_pagination(self):
        batch,order,_=self.setup_stock()
        issue=self.issue(batch,order,'6')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE IF EXISTS material_consumption')
            db.execute('PRAGMA user_version=6');db.commit()
        Store(self.path);Store(self.path)
        self.assertEqual(self.report(order)[0]['unreported'],'6.000')
        first=self.use(issue,'1','0')
        self.use(issue,'2','0')
        route='/api/orders/'+order['id']+'/consumption-history'
        page=self.client.get(route+'?limit=1').json()
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],first['id'])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],33)
            for query in ['DELETE FROM material_consumption','UPDATE material_consumption SET reason=reason']:
                with self.assertRaises(sqlite3.IntegrityError):db.execute(query)
        backup=self.path.parent/'usage-backup.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).order_consumption(order['id'])[0]['unreported'],'3.000')
