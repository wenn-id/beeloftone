import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_warehouse_movements as warehouse_tests


class MarketplaceReservationsTest(TestCase):
    setUp = warehouse_tests.WarehouseMovementsTest.setUp
    post = warehouse_tests.WarehouseMovementsTest.post
    order = warehouse_tests.WarehouseMovementsTest.order
    material = warehouse_tests.WarehouseMovementsTest.material
    receipt = warehouse_tests.WarehouseMovementsTest.receipt
    issue = warehouse_tests.WarehouseMovementsTest.issue
    setup_stock = warehouse_tests.WarehouseMovementsTest.setup_stock
    prepare = warehouse_tests.WarehouseMovementsTest.prepare
    cut = warehouse_tests.WarehouseMovementsTest.cut
    create_bundle = warehouse_tests.WarehouseMovementsTest.create_bundle
    setup_bundle = warehouse_tests.WarehouseMovementsTest.setup_bundle
    create_job = warehouse_tests.WarehouseMovementsTest.create_job
    complete = warehouse_tests.WarehouseMovementsTest.complete
    setup_job = warehouse_tests.WarehouseMovementsTest.setup_job
    finish = warehouse_tests.WarehouseMovementsTest.finish
    setup_finishing = warehouse_tests.WarehouseMovementsTest.setup_finishing
    inspect = warehouse_tests.WarehouseMovementsTest.inspect
    setup_qc = warehouse_tests.WarehouseMovementsTest.setup_qc
    receive = warehouse_tests.WarehouseMovementsTest.receive
    setup_receipt = warehouse_tests.WarehouseMovementsTest.setup_receipt
    move = warehouse_tests.WarehouseMovementsTest.move

    def reserve(self, receipt, reference='MKT-001', quantity=5, location='Rak Barang Jadi A', **options):
        reserved_date=options.pop('reserved_date','2026-09-20')
        body=dict(reference=reference,marketplace='Tokopedia',external_order_reference='TKP-ORDER-'+reference,
                  location=location,quantity=quantity,reserved_date=reserved_date,
                  reason='Pesanan marketplace dialokasikan ke stok')
        return self.post('/api/finished-goods-receipts/'+receipt['id']+'/marketplace-reservations',body,**options)

    def release(self, reservation, **options):
        released_date=options.pop('released_date','2026-09-21')
        return self.post('/api/marketplace-reservations/'+reservation['id']+'/release',
                         dict(released_date=released_date,reason='Pesanan dibatalkan marketplace'),**options)

    def test_partial_reservations_split_available_and_reserved_with_lineage(self):
        order,qc,receipt=self.setup_receipt()
        first=self.reserve(receipt,key='market-one')
        self.assertEqual(first,self.reserve(receipt,key='market-one'))
        second=self.reserve(receipt,reference='MKT-002',quantity=7,key='market-two')
        self.assertEqual(first['receipt_reference'],receipt['reference'])
        self.assertEqual(first['final_qc_reference'],qc['reference'])
        self.assertEqual(first['order_id'],order['id'])
        detail=self.client.get('/api/finished-goods-receipts/'+receipt['id']).json()
        sellable=next(row for row in detail['inventory'] if row['stock_status']=='sellable')
        self.assertEqual((sellable['quantity'],sellable['reserved_quantity'],sellable['available_quantity']),(12,12,0))
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['reserved_quantity'],
                          aggregate['available_quantity'],aggregate['hold_quantity'],aggregate['total_quantity']),
                         (12,12,0,8,20))
        listed=self.client.get('/api/orders/'+order['id']+'/marketplace-reservations').json()
        self.assertEqual([row['id'] for row in listed],[second['id'],first['id']])

    def test_release_restores_available_without_changing_physical_or_wip(self):
        order,_,receipt=self.setup_receipt()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        reservation=self.reserve(receipt,quantity=8)
        released=self.release(reservation,key='release-market')
        self.assertEqual(released,self.release(reservation,key='release-market'))
        self.assertEqual(released['status'],'released')
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['reserved_quantity'],
                          aggregate['available_quantity']),(12,0,12))
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)

    def test_validation_roles_and_reservation_protects_stock(self):
        _,_,receipt=self.setup_receipt()
        self.reserve(receipt,api_key=self.viewer['api_key'],status=403)
        self.reserve(receipt,quantity=True,status=422)
        self.reserve(receipt,reserved_date='2026-09-17',status=422)
        self.reserve(receipt,location='Rak Tidak Ada',status=409)
        reservation=self.reserve(receipt,quantity=8)
        self.reserve(receipt,reference='MKT-OVER',quantity=5,status=409)
        self.post('/api/finished-goods-receipts/'+receipt['id']+'/reverse',dict(reason='Sumber salah'),status=409)
        self.move(receipt,quantity=5,status=409)
        movement=self.move(receipt,reference='WH-AVAILABLE',quantity=4)
        self.post('/api/warehouse-movements/'+movement['id']+'/reverse',dict(reason='Lokasi salah'))
        self.release(reservation,released_date='2026-09-19',status=422)
        self.release(reservation,api_key=self.viewer['api_key'],status=403)
        self.release(reservation,api_key=self.operator['api_key'])
        self.assertEqual(self.client.get('/api/marketplace-reservations/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/marketplace-reservations').status_code,404)

    def test_reservation_on_transfer_target_blocks_correction_and_race_overallocation(self):
        _,_,receipt=self.setup_receipt(sellable=10,hold=0)
        movement=self.move(receipt,quantity=5)
        reservation=self.reserve(receipt,quantity=5,location='Rak Barang Jadi B')
        self.post('/api/warehouse-movements/'+movement['id']+'/reverse',dict(reason='Lokasi salah'),status=409)
        self.release(reservation)
        self.post('/api/warehouse-movements/'+movement['id']+'/reverse',dict(reason='Lokasi salah'))

        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/finished-goods-receipts/'+receipt['id']+'/marketplace-reservations',json=dict(
                    reference='MKT-RACE-'+str(index),marketplace='Shopee',external_order_reference='SHP-'+str(index),
                    location='Rak Barang Jadi A',quantity=7,reserved_date='2026-09-20',reason='Uji bersamaan'),
                    headers={'X-API-Key':self.operator['api_key'],
                             'Idempotency-Key':'market-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])

    def test_rollback_cursor_backup_guards_and_migration_from_19(self):
        order,_,receipt=self.setup_receipt()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_market BEFORE INSERT ON requests WHEN NEW.key='fail-market' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.reserve(receipt,key='fail-market',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/marketplace-reservations').json(),[])
        first=self.reserve(receipt,quantity=2)
        second=self.reserve(receipt,reference='MKT-002',quantity=2)
        route='/api/orders/'+order['id']+'/marketplace-reservations'
        page=self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'],second['id'])
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],first['id'])
        backup=self.path.with_name('marketplace-reservations-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).marketplace_reservation(first['id']),first)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE marketplace_reservations SET reason=reason','DELETE FROM marketplace_reservations'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO marketplace_reservations(id,reference,receipt_id,marketplace,
                    external_order_reference,location,quantity,reserved_date,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',('bad','MKT-DIRECT',receipt['id'],'Shopee','SHP-X',
                    receipt['location'],99,'2026-09-20','Bypass',self.admin['id'],'2026-09-20T00:00:00+00:00'))

        fresh_path=self.path.with_name('schema19.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            for trigger in ('finished_goods_reversal_valid','warehouse_movement_source_valid',
                            'warehouse_movement_reversal_valid'):
                db.execute('DROP TRIGGER '+trigger)
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
            db.execute('PRAGMA user_version=19');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],37)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM marketplace_reservations').fetchone()[0],0)
