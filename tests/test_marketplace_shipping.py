import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_marketplace_packing as packing_tests


class MarketplaceShippingTest(TestCase):
    setUp = packing_tests.MarketplacePackingTest.setUp
    post = packing_tests.MarketplacePackingTest.post
    order = packing_tests.MarketplacePackingTest.order
    material = packing_tests.MarketplacePackingTest.material
    receipt = packing_tests.MarketplacePackingTest.receipt
    issue = packing_tests.MarketplacePackingTest.issue
    setup_stock = packing_tests.MarketplacePackingTest.setup_stock
    prepare = packing_tests.MarketplacePackingTest.prepare
    cut = packing_tests.MarketplacePackingTest.cut
    create_bundle = packing_tests.MarketplacePackingTest.create_bundle
    setup_bundle = packing_tests.MarketplacePackingTest.setup_bundle
    create_job = packing_tests.MarketplacePackingTest.create_job
    complete = packing_tests.MarketplacePackingTest.complete
    setup_job = packing_tests.MarketplacePackingTest.setup_job
    finish = packing_tests.MarketplacePackingTest.finish
    setup_finishing = packing_tests.MarketplacePackingTest.setup_finishing
    inspect = packing_tests.MarketplacePackingTest.inspect
    setup_qc = packing_tests.MarketplacePackingTest.setup_qc
    receive = packing_tests.MarketplacePackingTest.receive
    setup_receipt = packing_tests.MarketplacePackingTest.setup_receipt
    move = packing_tests.MarketplacePackingTest.move
    reserve = packing_tests.MarketplacePackingTest.reserve
    release = packing_tests.MarketplacePackingTest.release
    pick = packing_tests.MarketplacePackingTest.pick
    pack = packing_tests.MarketplacePackingTest.pack

    def ship(self, pack, reference='SHIP-001', quantity=2, **options):
        carrier=options.pop('carrier','JNE')
        tracking_number=options.pop('tracking_number','TRACK-001')
        shipped_date=options.pop('shipped_date','2026-09-25')
        return self.post('/api/marketplace-packs/'+pack['id']+'/shipments',dict(
            reference=reference,quantity=quantity,carrier=carrier,tracking_number=tracking_number,
            shipped_date=shipped_date,reason='Paket diserahkan ke carrier'),**options)

    def test_partial_shipments_leave_warehouse_with_lineage(self):
        order,_,receipt=self.setup_receipt()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=4)
        pack=self.pack(pick,quantity=4)
        first=self.ship(pack,key='ship-one')
        self.assertEqual(first,self.ship(pack,key='ship-one'))
        second=self.ship(pack,reference='SHIP-002',quantity=1,tracking_number='TRACK-002')
        self.assertEqual((first['pack_reference'],first['pick_reference'],first['reservation_reference'],
                          first['receipt_reference']),(pack['reference'],pick['reference'],
                          reservation['reference'],receipt['reference']))
        current=self.client.get('/api/marketplace-packs/'+pack['id']).json()
        self.assertEqual((current['shipped_quantity'],current['remaining_quantity']),(3,1))
        detail=self.client.get('/api/finished-goods-receipts/'+receipt['id']).json()
        balances={(row['location'],row['stock_status']):row['quantity'] for row in detail['inventory']}
        self.assertEqual(balances[('Rak Barang Jadi A','sellable')],8)
        self.assertNotIn(('Meja Packing A','picked'),balances)
        self.assertEqual(balances[('Meja Packing A','packed')],1)
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['picked_quantity'],aggregate['packed_quantity'],
                          aggregate['shipped_quantity'],aggregate['reserved_quantity'],
                          aggregate['available_quantity'],aggregate['total_quantity']),(8,0,1,3,2,6,17))
        listed=self.client.get('/api/orders/'+order['id']+'/marketplace-shipments').json()
        self.assertEqual([row['id'] for row in listed],[second['id'],first['id']])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)

    def test_correction_restores_packed_and_unblocks_pack_correction(self):
        _,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=4)
        pack=self.pack(pick,quantity=4)
        shipment=self.ship(pack,quantity=3)
        self.post('/api/marketplace-packs/'+pack['id']+'/reverse',dict(reason='Salah pack'),status=409)
        for role in (self.operator,self.viewer):
            self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',dict(reason='Salah kirim'),
                      api_key=role['api_key'],status=403)
        corrected=self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',
                            dict(reason='Serah terima carrier dibatalkan'),key='shipment-reverse')
        self.assertEqual(corrected,self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',
                                             dict(reason='Serah terima carrier dibatalkan'),key='shipment-reverse'))
        self.assertEqual(corrected['status'],'corrected')
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['picked_quantity'],aggregate['packed_quantity'],
                          aggregate['shipped_quantity'],aggregate['reserved_quantity'],
                          aggregate['available_quantity'],aggregate['total_quantity']),(8,0,4,0,2,6,20))
        self.post('/api/marketplace-packs/'+pack['id']+'/reverse',dict(reason='Pack salah'))

    def test_validation_roles_dates_allocation_tracking_and_missing_records(self):
        _,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=4)
        pack=self.pack(pick,quantity=4)
        self.ship(pack,api_key=self.viewer['api_key'],status=403)
        self.ship(pack,quantity=True,status=422)
        self.ship(pack,shipped_date='2026-09-23',status=422)
        self.ship(pack,quantity=5,status=409)
        self.ship(pack,quantity=3)
        self.ship(pack,reference='SHIP-OVER',quantity=2,tracking_number='TRACK-OVER',status=409)
        self.assertEqual(self.client.get('/api/marketplace-shipments/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/marketplace-shipments').status_code,404)
        self.post('/api/marketplace-packs/missing/shipments',dict(reference='SHIP-MISSING',quantity=1,
                  carrier='JNE',tracking_number='TRACK-MISSING',shipped_date='2026-09-25',
                  reason='Tidak ada'),status=404)

    def test_race_cannot_ship_more_than_pack(self):
        _,_,receipt=self.setup_receipt(sellable=10,hold=0)
        reservation=self.reserve(receipt,quantity=10)
        pick=self.pick(reservation,quantity=10)
        pack=self.pack(pick,quantity=10)
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/marketplace-packs/'+pack['id']+'/shipments',json=dict(
                    reference='SHIP-RACE-'+str(index),quantity=7,carrier='JNE',
                    tracking_number='TRACK-RACE-'+str(index),shipped_date='2026-09-25',
                    reason='Uji kirim bersamaan'),headers={'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'shipment-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])

    def test_rollback_cursor_backup_guards_and_migration_from_22(self):
        order,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=6)
        pack=self.pack(pick,quantity=6)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_shipment BEFORE INSERT ON requests WHEN NEW.key='fail-shipment' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.ship(pack,key='fail-shipment',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/marketplace-shipments').json(),[])
        first=self.ship(pack,quantity=2)
        second=self.ship(pack,reference='SHIP-002',quantity=2,tracking_number='TRACK-002')
        route='/api/orders/'+order['id']+'/marketplace-shipments'
        page=self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'],second['id'])
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],first['id'])
        backup=self.path.with_name('marketplace-shipping-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).marketplace_shipment(first['id']),first)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE marketplace_shipments SET reason=reason','DELETE FROM marketplace_shipments'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO marketplace_shipments(id,reference,pack_id,quantity,carrier,
                    tracking_number,shipped_date,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    ('bad','SHIP-DIRECT',pack['id'],99,'JNE','TRACK-DIRECT','2026-09-25','Bypass',
                     self.admin['id'],'2026-09-25T00:00:00+00:00'))

        fresh_path=self.path.with_name('schema22.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            db.execute('DROP TRIGGER marketplace_pack_reversal_valid')
            db.execute('DROP VIEW finished_goods_reserved_stock')
            db.execute('DROP VIEW finished_goods_stock_ledger')
            db.execute('DROP TABLE finished_goods_adjustment_reversals')
            db.execute('DROP TABLE finished_goods_adjustments')
            db.execute('DROP TABLE marketplace_return_reversals')
            db.execute('DROP TABLE marketplace_returns')
            db.execute('DROP TABLE marketplace_shipment_reversals')
            db.execute('DROP TABLE marketplace_shipments')
            db.execute('PRAGMA user_version=22');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],41)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM marketplace_shipments').fetchone()[0],0)
