import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_final_qc as qc_tests


class FinishedGoodsTest(TestCase):
    setUp = qc_tests.FinalQcTest.setUp
    post = qc_tests.FinalQcTest.post
    order = qc_tests.FinalQcTest.order
    material = qc_tests.FinalQcTest.material
    receipt = qc_tests.FinalQcTest.receipt
    issue = qc_tests.FinalQcTest.issue
    setup_stock = qc_tests.FinalQcTest.setup_stock
    prepare = qc_tests.FinalQcTest.prepare
    cut = qc_tests.FinalQcTest.cut
    create_bundle = qc_tests.FinalQcTest.create_bundle
    setup_bundle = qc_tests.FinalQcTest.setup_bundle
    create_job = qc_tests.FinalQcTest.create_job
    complete = qc_tests.FinalQcTest.complete
    setup_job = qc_tests.FinalQcTest.setup_job
    finish = qc_tests.FinalQcTest.finish
    setup_finishing = qc_tests.FinalQcTest.setup_finishing
    inspect = qc_tests.FinalQcTest.inspect

    def setup_qc(self, quantity=20):
        order, _, finishing=self.setup_finishing(quantity)
        qc=self.inspect(finishing,accepted=quantity,rework=0,reject=0)
        return order,finishing,qc

    def receive(self,qc,reference='FG-001',sellable=6,hold=2,received_date='2026-09-18',**options):
        body=dict(reference=reference,scanned_sku=qc['sku'],location='Rak Barang Jadi A',
                  sellable_quantity=sellable,hold_quantity=hold,received_date=received_date,
                  reason='Barang jadi diterima dan dihitung')
        return self.post('/api/final-qc-records/'+qc['id']+'/finished-goods-receipts',body,**options)

    def test_partial_receipts_split_sellable_hold_keep_wip_and_lineage(self):
        order,_,qc=self.setup_qc()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        first=self.receive(qc,key='fg-one')
        self.assertEqual(first,self.receive(qc,key='fg-one'))
        second=self.receive(qc,reference='FG-002',sellable=10,hold=2,key='fg-two')
        self.assertEqual((first['received_quantity'],second['received_quantity']),(8,12))
        self.assertEqual(first['final_qc_reference'],qc['reference'])
        self.assertEqual(first['finishing_reference'],qc['finishing_reference'])
        self.assertEqual(first['bundle_reference'],qc['bundle_reference'])
        self.assertEqual(first['batch_id'],qc['batch_id'])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)
        source=self.client.get('/api/final-qc-records/'+qc['id']).json()
        self.assertEqual((source['warehouse_received_quantity'],source['warehouse_remaining_quantity']),(20,0))
        listed=self.client.get('/api/orders/'+order['id']+'/finished-goods-receipts').json()
        self.assertEqual([row['id'] for row in listed],[second['id'],first['id']])
        inventory=self.client.get('/api/finished-goods-inventory').json()
        row=next(item for item in inventory if item['sku']==qc['sku'])
        self.assertEqual((row['sellable_quantity'],row['hold_quantity'],row['total_quantity']),(16,4,20))

    def test_correction_releases_receipt_without_moving_wip(self):
        order,_,qc=self.setup_qc()
        receipt=self.receive(qc)
        self.post('/api/final-qc-records/'+qc['id']+'/reverse',dict(reason='QC salah'),status=409)
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        corrected=self.post('/api/finished-goods-receipts/'+receipt['id']+'/reverse',
                            dict(reason='Lokasi dan status salah'),key='reverse-fg')
        self.assertEqual(corrected,self.post('/api/finished-goods-receipts/'+receipt['id']+'/reverse',
                                             dict(reason='Lokasi dan status salah'),key='reverse-fg'))
        self.assertEqual(corrected['status'],'corrected')
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)
        source=self.client.get('/api/final-qc-records/'+qc['id']).json()
        self.assertEqual((source['warehouse_received_quantity'],source['warehouse_remaining_quantity']),(0,20))
        self.receive(qc,reference='FG-REPLACEMENT',sellable=20,hold=0)

    def test_validation_roles_scan_date_and_allocation(self):
        _,_,qc=self.setup_qc()
        self.receive(qc,api_key=self.viewer['api_key'],status=403)
        self.receive(qc,sellable=True,status=422)
        self.receive(qc,sellable=0,hold=0,status=422)
        self.receive(qc,received_date='2026-09-16',status=422)
        body=dict(reference='FG-WRONG',scanned_sku='OTHER-SKU',location='Rak A',sellable_quantity=1,
                  hold_quantity=0,received_date='2026-09-18',reason='Uji scan')
        self.post('/api/final-qc-records/'+qc['id']+'/finished-goods-receipts',body,status=422)
        self.receive(dict(id='missing',sku=qc['sku']),status=404)
        receipt=self.receive(qc,sellable=20,hold=0)
        self.receive(qc,reference='FG-OVER',sellable=1,hold=0,status=409)
        self.receive(qc,reference='fg-001',sellable=1,hold=0,status=409)
        for role in (self.operator,self.viewer):
            self.post('/api/finished-goods-receipts/'+receipt['id']+'/reverse',dict(reason='Salah'),
                      api_key=role['api_key'],status=403)
        self.assertEqual(self.client.get('/api/orders/missing/finished-goods-receipts').status_code,404)
        self.assertEqual(self.client.get('/api/finished-goods-receipts/missing').status_code,404)

    def test_race_cannot_overreceive_one_qc_result(self):
        _,_,qc=self.setup_qc()
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/final-qc-records/'+qc['id']+'/finished-goods-receipts',json=dict(
                    reference='FG-RACE-'+str(index),scanned_sku=qc['sku'],location='Rak A',
                    sellable_quantity=15,hold_quantity=0,received_date='2026-09-18',reason='Uji bersamaan'),
                    headers={'X-API-Key':self.operator['api_key'],
                             'Idempotency-Key':'fg-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])
        source=self.client.get('/api/final-qc-records/'+qc['id']).json()
        self.assertEqual((source['warehouse_received_quantity'],source['warehouse_remaining_quantity']),(15,5))

    def test_rollback_cursor_backup_guards_and_migration_from_17(self):
        order,_,qc=self.setup_qc()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_fg BEFORE INSERT ON requests WHEN NEW.key='fail-fg' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.receive(qc,key='fail-fg',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/finished-goods-receipts').json(),[])
        first=self.receive(qc,sellable=3,hold=0)
        second=self.receive(qc,reference='FG-002',sellable=4,hold=0)
        route='/api/orders/'+order['id']+'/finished-goods-receipts'
        page=self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'],second['id'])
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],first['id'])
        backup=self.path.with_name('finished-goods-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).finished_goods_receipt(first['id']),first)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE finished_goods_receipts SET reason=reason','DELETE FROM finished_goods_receipts'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO finished_goods_receipts(id,reference,final_qc_record_id,scanned_sku,
                    location,sellable_quantity,hold_quantity,received_date,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',('bad','FG-DIRECT',qc['id'],qc['sku'],'Rak A',99,0,
                    '2026-09-18','Bypass',self.admin['id'],'2026-09-18T00:00:00+00:00'))

        fresh_path=self.path.with_name('schema17.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            db.execute('DROP TRIGGER finished_goods_reversal_valid')
            db.execute('DROP TABLE marketplace_reservation_releases')
            db.execute('DROP TABLE marketplace_reservations')
            db.execute('DROP TABLE warehouse_movement_reversals')
            db.execute('DROP TABLE warehouse_movements')
            db.execute('DROP TRIGGER finished_goods_blocks_final_qc_reversal')
            db.execute('DROP TABLE finished_goods_receipt_reversals')
            db.execute('DROP TABLE finished_goods_receipts')
            for column in ('disposition','responsible_source','defect_type'):
                db.execute('ALTER TABLE final_qc_records DROP COLUMN '+column)
            db.execute('PRAGMA user_version=17');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],20)
            columns={row[1] for row in db.execute('PRAGMA table_info(final_qc_records)')}
            self.assertTrue({'defect_type','responsible_source','disposition'}<=columns)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM finished_goods_receipts').fetchone()[0],0)
