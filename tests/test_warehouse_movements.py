import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_finished_goods as finished_tests


class WarehouseMovementsTest(TestCase):
    setUp = finished_tests.FinishedGoodsTest.setUp
    post = finished_tests.FinishedGoodsTest.post
    order = finished_tests.FinishedGoodsTest.order
    material = finished_tests.FinishedGoodsTest.material
    receipt = finished_tests.FinishedGoodsTest.receipt
    issue = finished_tests.FinishedGoodsTest.issue
    setup_stock = finished_tests.FinishedGoodsTest.setup_stock
    prepare = finished_tests.FinishedGoodsTest.prepare
    cut = finished_tests.FinishedGoodsTest.cut
    create_bundle = finished_tests.FinishedGoodsTest.create_bundle
    setup_bundle = finished_tests.FinishedGoodsTest.setup_bundle
    create_job = finished_tests.FinishedGoodsTest.create_job
    complete = finished_tests.FinishedGoodsTest.complete
    setup_job = finished_tests.FinishedGoodsTest.setup_job
    finish = finished_tests.FinishedGoodsTest.finish
    setup_finishing = finished_tests.FinishedGoodsTest.setup_finishing
    inspect = finished_tests.FinishedGoodsTest.inspect
    setup_qc = finished_tests.FinishedGoodsTest.setup_qc
    receive = finished_tests.FinishedGoodsTest.receive

    def setup_receipt(self, sellable=12, hold=8):
        order, _, qc = self.setup_qc(sellable + hold)
        receipt = self.receive(qc, sellable=sellable, hold=hold)
        return order, qc, receipt

    def move(self, receipt, reference='WH-001', kind='transfer', from_location='Rak Barang Jadi A',
             to_location='Rak Barang Jadi B', quantity=5, stock_status='sellable', **options):
        moved_date=options.pop('moved_date','2026-09-19')
        body=dict(reference=reference,kind=kind,from_location=from_location,to_location=to_location,
                  quantity=quantity,moved_date=moved_date,reason='Stok gudang dihitung dan dipindahkan')
        if stock_status is not None:
            body['stock_status']=stock_status
        return self.post('/api/finished-goods-receipts/'+receipt['id']+'/warehouse-movements',body,**options)

    def test_transfer_location_preserves_status_and_source_lineage(self):
        order,qc,receipt=self.setup_receipt()
        movement=self.move(receipt,key='warehouse-one')
        self.assertEqual(movement,self.move(receipt,key='warehouse-one'))
        self.assertEqual((movement['from_status'],movement['to_status']),('sellable','sellable'))
        self.assertEqual(movement['receipt_reference'],receipt['reference'])
        self.assertEqual(movement['final_qc_reference'],qc['reference'])
        self.assertEqual(movement['order_id'],order['id'])
        detail=self.client.get('/api/finished-goods-receipts/'+receipt['id']).json()
        balances={(row['location'],row['stock_status']):row['quantity'] for row in detail['inventory']}
        self.assertEqual(balances,{('Rak Barang Jadi A','hold'):8,
                                   ('Rak Barang Jadi A','sellable'):7,
                                   ('Rak Barang Jadi B','sellable'):5})
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['hold_quantity'],
                          aggregate['damaged_quantity'],aggregate['total_quantity']),(12,8,0,20))
        locations=self.client.get('/api/warehouse-inventory').json()
        self.assertEqual(sum(row['quantity'] for row in locations if row['sku']==receipt['sku']),20)

    def test_hold_release_and_damage_update_inventory_without_moving_wip(self):
        order,_,receipt=self.setup_receipt()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        released=self.move(receipt,reference='WH-RELEASE',kind='hold_release',to_location='Rak Jual',
                           quantity=3,stock_status=None)
        damaged=self.move(receipt,reference='WH-DAMAGE',kind='hold_damage',to_location='Area Rusak',
                          quantity=2,stock_status=None)
        self.assertEqual((released['from_status'],released['to_status']),('hold','sellable'))
        self.assertEqual((damaged['from_status'],damaged['to_status']),('hold','damaged'))
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['hold_quantity'],
                          aggregate['damaged_quantity'],aggregate['total_quantity']),(15,3,2,20))
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)
        listed=self.client.get('/api/orders/'+order['id']+'/warehouse-movements').json()
        self.assertEqual([row['id'] for row in listed],[damaged['id'],released['id']])

    def test_validation_roles_dependencies_and_reverse_order(self):
        _,_,receipt=self.setup_receipt()
        self.move(receipt,api_key=self.viewer['api_key'],status=403)
        self.move(receipt,quantity=True,status=422)
        self.move(receipt,to_location='rak barang jadi a',status=422)
        self.move(receipt,kind='hold_release',stock_status='hold',status=422)
        self.move(receipt,moved_date='2026-09-17',status=422)
        self.move(receipt,quantity=13,status=409)
        first=self.move(receipt,quantity=5)
        second=self.move(receipt,reference='WH-002',from_location='Rak Barang Jadi B',
                         to_location='Rak Barang Jadi C',quantity=5)
        self.post('/api/finished-goods-receipts/'+receipt['id']+'/reverse',
                  dict(reason='Penerimaan salah'),status=409)
        self.post('/api/warehouse-movements/'+first['id']+'/reverse',dict(reason='Lokasi salah'),status=409)
        for role in (self.operator,self.viewer):
            self.post('/api/warehouse-movements/'+second['id']+'/reverse',dict(reason='Lokasi salah'),
                      api_key=role['api_key'],status=403)
        corrected=self.post('/api/warehouse-movements/'+second['id']+'/reverse',
                            dict(reason='Tujuan kedua salah'),key='reverse-second')
        self.assertEqual(corrected,self.post('/api/warehouse-movements/'+second['id']+'/reverse',
                                             dict(reason='Tujuan kedua salah'),key='reverse-second'))
        self.post('/api/warehouse-movements/'+first['id']+'/reverse',dict(reason='Tujuan awal salah'))
        self.post('/api/finished-goods-receipts/'+receipt['id']+'/reverse',dict(reason='Penerimaan salah'))
        self.assertEqual(self.client.get('/api/warehouse-movements/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/warehouse-movements').status_code,404)

    def test_race_cannot_overdraw_one_location_status(self):
        _,_,receipt=self.setup_receipt(sellable=10,hold=0)
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/finished-goods-receipts/'+receipt['id']+'/warehouse-movements',json=dict(
                    reference='WH-RACE-'+str(index),kind='transfer',stock_status='sellable',
                    from_location='Rak Barang Jadi A',to_location='Rak '+str(index),quantity=7,
                    moved_date='2026-09-19',reason='Uji transfer bersamaan'),headers={
                    'X-API-Key':self.operator['api_key'],'Idempotency-Key':'wh-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])
        receipt=self.client.get('/api/finished-goods-receipts/'+receipt['id']).json()
        self.assertEqual(sum(row['quantity'] for row in receipt['inventory']),10)

    def test_rollback_cursor_backup_guards_and_migration_from_18(self):
        order,_,receipt=self.setup_receipt()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_wh BEFORE INSERT ON requests WHEN NEW.key='fail-wh' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.move(receipt,key='fail-wh',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/warehouse-movements').json(),[])
        first=self.move(receipt,quantity=2)
        second=self.move(receipt,reference='WH-002',quantity=2,to_location='Rak Barang Jadi C')
        route='/api/orders/'+order['id']+'/warehouse-movements'
        page=self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'],second['id'])
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],first['id'])
        backup=self.path.with_name('warehouse-movements-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).warehouse_movement(first['id']),first)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE warehouse_movements SET reason=reason','DELETE FROM warehouse_movements'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO warehouse_movements(id,reference,receipt_id,kind,from_location,to_location,
                    from_status,to_status,quantity,moved_date,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',('bad','WH-DIRECT',receipt['id'],'transfer',
                    receipt['location'],'Bypass','sellable','sellable',99,'2026-09-19','Bypass',self.admin['id'],
                    '2026-09-19T00:00:00+00:00'))

        fresh_path=self.path.with_name('schema18.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            db.execute('DROP TRIGGER finished_goods_reversal_valid')
            db.execute('DROP TRIGGER marketplace_reservation_release_valid')
            db.execute('DROP TRIGGER marketplace_pick_reversal_valid')
            db.execute('DROP TRIGGER marketplace_pack_reversal_valid')
            db.execute('DROP VIEW finished_goods_reserved_stock')
            db.execute('DROP VIEW finished_goods_stock_ledger')
            db.execute('DROP TABLE finished_goods_adjustment_reversals')
            db.execute('DROP TABLE finished_goods_adjustments')
            db.execute('DROP TABLE marketplace_return_reversals')
            db.execute('DROP TABLE marketplace_returns')
            db.execute('DROP TABLE marketplace_shipment_reversals')
            db.execute('DROP TABLE marketplace_shipments')
            db.execute('DROP TABLE marketplace_pack_reversals')
            db.execute('DROP TABLE marketplace_packs')
            db.execute('DROP TABLE marketplace_pick_reversals')
            db.execute('DROP TABLE marketplace_picks')
            db.execute('DROP TABLE marketplace_reservation_releases')
            db.execute('DROP TABLE marketplace_reservations')
            db.execute('DROP TABLE warehouse_movement_reversals')
            db.execute('DROP TABLE warehouse_movements')
            db.execute('PRAGMA user_version=18');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],33)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM warehouse_movements').fetchone()[0],0)
