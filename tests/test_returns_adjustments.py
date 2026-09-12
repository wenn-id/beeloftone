import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_marketplace_shipping as shipping_tests


class ReturnsAdjustmentsTest(TestCase):
    setUp = shipping_tests.MarketplaceShippingTest.setUp
    post = shipping_tests.MarketplaceShippingTest.post
    order = shipping_tests.MarketplaceShippingTest.order
    material = shipping_tests.MarketplaceShippingTest.material
    receipt = shipping_tests.MarketplaceShippingTest.receipt
    issue = shipping_tests.MarketplaceShippingTest.issue
    setup_stock = shipping_tests.MarketplaceShippingTest.setup_stock
    prepare = shipping_tests.MarketplaceShippingTest.prepare
    cut = shipping_tests.MarketplaceShippingTest.cut
    create_bundle = shipping_tests.MarketplaceShippingTest.create_bundle
    setup_bundle = shipping_tests.MarketplaceShippingTest.setup_bundle
    create_job = shipping_tests.MarketplaceShippingTest.create_job
    complete = shipping_tests.MarketplaceShippingTest.complete
    setup_job = shipping_tests.MarketplaceShippingTest.setup_job
    finish = shipping_tests.MarketplaceShippingTest.finish
    setup_finishing = shipping_tests.MarketplaceShippingTest.setup_finishing
    inspect = shipping_tests.MarketplaceShippingTest.inspect
    setup_qc = shipping_tests.MarketplaceShippingTest.setup_qc
    receive = shipping_tests.MarketplaceShippingTest.receive
    setup_receipt = shipping_tests.MarketplaceShippingTest.setup_receipt
    move = shipping_tests.MarketplaceShippingTest.move
    reserve = shipping_tests.MarketplaceShippingTest.reserve
    release = shipping_tests.MarketplaceShippingTest.release
    pick = shipping_tests.MarketplaceShippingTest.pick
    pack = shipping_tests.MarketplaceShippingTest.pack
    ship = shipping_tests.MarketplaceShippingTest.ship

    def customer_return(self, shipment, reference='RET-001', quantity=1, **options):
        returned_date=options.pop('returned_date','2026-09-26')
        return_reason=options.pop('return_reason','too_small')
        return_location=options.pop('return_location','Area Retur A')
        stock_status=options.pop('stock_status','hold')
        return self.post('/api/marketplace-shipments/'+shipment['id']+'/returns',dict(
            reference=reference,quantity=quantity,return_reason=return_reason,return_location=return_location,
            stock_status=stock_status,returned_date=returned_date,reason='Retur pelanggan diterima dan diperiksa'),
            **options)

    def adjust(self, receipt, reference='ADJ-001', quantity_delta=1, **options):
        adjusted_date=options.pop('adjusted_date','2026-09-27')
        location=options.pop('location','Rak Barang Jadi A')
        stock_status=options.pop('stock_status','sellable')
        return self.post('/api/finished-goods-receipts/'+receipt['id']+'/adjustments',dict(
            reference=reference,location=location,stock_status=stock_status,quantity_delta=quantity_delta,
            adjusted_date=adjusted_date,reason='Selisih hasil stock opname'),**options)

    def flow(self, shipment_quantity=2):
        order,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=4)
        pack=self.pack(pick,quantity=3)
        shipment=self.ship(pack,quantity=shipment_quantity)
        return order,receipt,shipment

    def test_partial_returns_restore_inspected_stock_with_lineage(self):
        order,receipt,shipment=self.flow()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        first=self.customer_return(shipment,key='return-one')
        self.assertEqual(first,self.customer_return(shipment,key='return-one'))
        second=self.customer_return(shipment,reference='RET-002',return_reason='defect',
                                    return_location='Area Retur B',stock_status='damaged')
        self.assertEqual((first['shipment_reference'],first['pack_reference'],first['receipt_reference']),
                         (shipment['reference'],shipment['pack_reference'],receipt['reference']))
        current=self.client.get('/api/marketplace-shipments/'+shipment['id']).json()
        self.assertEqual((current['returned_quantity'],current['returnable_quantity']),(2,0))
        inventory=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((inventory['sellable_quantity'],inventory['picked_quantity'],inventory['packed_quantity'],
                          inventory['shipped_quantity'],inventory['returned_quantity'],inventory['hold_quantity'],
                          inventory['damaged_quantity'],inventory['total_quantity']),(8,1,1,2,2,9,1,20))
        locations={(row['location'],row['stock_status']):row['quantity']
                   for row in self.client.get('/api/warehouse-inventory').json() if row['sku']==receipt['sku']}
        self.assertEqual(locations[('Area Retur A','hold')],1)
        self.assertEqual(locations[('Area Retur B','damaged')],1)
        listed=self.client.get('/api/orders/'+order['id']+'/marketplace-returns').json()
        self.assertEqual([row['id'] for row in listed],[second['id'],first['id']])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)

    def test_return_correction_respects_reserved_stock_and_unblocks_shipment(self):
        _,receipt,shipment=self.flow()
        returned=self.customer_return(shipment,return_location='Rak Retur Sellable',stock_status='sellable')
        self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',dict(reason='Salah kirim'),status=409)
        reserved=self.reserve(receipt,reference='MKT-RETURN',quantity=1,location='Rak Retur Sellable')
        self.post('/api/marketplace-returns/'+returned['id']+'/reverse',dict(reason='Retur salah'),status=409)
        self.release(reserved,key='release-return-stock')
        corrected=self.post('/api/marketplace-returns/'+returned['id']+'/reverse',
                            dict(reason='Paket ternyata bukan retur'),key='return-reverse')
        self.assertEqual(corrected['status'],'corrected')
        self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',dict(reason='Pengiriman salah'))

    def test_adjustments_change_receipt_stock_and_preserve_reservations(self):
        order,_,receipt=self.setup_receipt()
        positive=self.adjust(receipt,quantity_delta=3,location='Rak Opname',key='adjustment-positive')
        self.assertEqual(positive,self.adjust(receipt,quantity_delta=3,location='Rak Opname',key='adjustment-positive'))
        reserved=self.reserve(receipt,reference='MKT-OPNAME',quantity=2,location='Rak Opname')
        self.adjust(receipt,reference='ADJ-OVER',quantity_delta=-2,location='Rak Opname',status=409)
        negative=self.adjust(receipt,reference='ADJ-002',quantity_delta=-1,location='Rak Opname')
        bucket=next(row for row in self.client.get('/api/warehouse-inventory').json()
                    if row['sku']==receipt['sku'] and row['location']=='Rak Opname')
        self.assertEqual((bucket['quantity'],bucket['reserved_quantity'],bucket['available_quantity']),(2,2,0))
        self.post('/api/finished-goods-adjustments/'+positive['id']+'/reverse',dict(reason='Hitung awal salah'),status=409)
        self.release(reserved,key='release-opname')
        self.post('/api/finished-goods-adjustments/'+negative['id']+'/reverse',dict(reason='Pengurangan salah'))
        self.post('/api/finished-goods-adjustments/'+positive['id']+'/reverse',dict(reason='Penambahan salah'))
        self.assertFalse(any(row['location']=='Rak Opname' for row in self.client.get('/api/warehouse-inventory').json()))
        listed=self.client.get('/api/orders/'+order['id']+'/finished-goods-adjustments').json()
        self.assertEqual([row['id'] for row in listed],[negative['id'],positive['id']])

    def test_validation_roles_dates_reasons_statuses_and_missing_records(self):
        _,receipt,shipment=self.flow()
        self.customer_return(shipment,api_key=self.viewer['api_key'],status=403)
        self.customer_return(shipment,quantity=True,status=422)
        self.customer_return(shipment,returned_date='2026-09-24',status=422)
        self.customer_return(shipment,return_reason='changed_mind',status=422)
        self.customer_return(shipment,stock_status='picked',status=422)
        self.adjust(receipt,api_key=self.viewer['api_key'],status=403)
        self.adjust(receipt,quantity_delta=0,status=422)
        self.adjust(receipt,adjusted_date='2026-09-17',status=422)
        self.adjust(receipt,stock_status='packed',status=422)
        self.assertEqual(self.client.get('/api/marketplace-returns/missing').status_code,404)
        self.assertEqual(self.client.get('/api/finished-goods-adjustments/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/marketplace-returns').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/finished-goods-adjustments').status_code,404)

    def test_races_cannot_overreturn_or_overdraw_adjustment(self):
        _,receipt,shipment=self.flow()
        barrier=Barrier(2)
        def save_return(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/marketplace-shipments/'+shipment['id']+'/returns',json=dict(
                    reference='RET-RACE-'+str(index),quantity=2,return_reason='other',
                    return_location='Area Retur',stock_status='hold',returned_date='2026-09-26',
                    reason='Uji retur bersamaan'),headers={'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'return-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save_return,range(2))),[201,409])

        barrier=Barrier(2)
        def save_adjustment(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/finished-goods-receipts/'+receipt['id']+'/adjustments',json=dict(
                    reference='ADJ-RACE-'+str(index),location='Rak Barang Jadi A',stock_status='sellable',
                    quantity_delta=-4,adjusted_date='2026-09-27',reason='Uji opname bersamaan'),
                    headers={'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'adjustment-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save_adjustment,range(2))),[201,409])

    def test_rollback_backup_immutability_and_migration_from_23(self):
        order,receipt,shipment=self.flow()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_return BEFORE INSERT ON requests WHEN NEW.key='fail-return' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.customer_return(shipment,key='fail-return',status=409)
        returned=self.customer_return(shipment)
        adjustment=self.adjust(receipt)
        backup=self.path.with_name('returns-adjustments-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).marketplace_return(returned['id']),returned)
        self.assertEqual(Store(backup).finished_goods_adjustment(adjustment['id']),adjustment)
        with self.app.state.store.transaction(write=True) as db:
            for table in ('marketplace_returns','finished_goods_adjustments'):
                for sql in ('UPDATE '+table+' SET reason=reason','DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)

        fresh_path=self.path.with_name('schema23.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            db.execute('DROP TRIGGER marketplace_shipment_reversal_valid')
            db.execute('DROP VIEW finished_goods_reserved_stock')
            db.execute('DROP VIEW finished_goods_stock_ledger')
            db.execute('DROP TABLE finished_goods_adjustment_reversals')
            db.execute('DROP TABLE finished_goods_adjustments')
            db.execute('DROP TABLE marketplace_return_reversals')
            db.execute('DROP TABLE marketplace_returns')
            db.execute('PRAGMA user_version=23');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],32)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM marketplace_returns').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM finished_goods_adjustments').fetchone()[0],0)
