import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_marketplace_reservations as reservation_tests


class MarketplacePickingTest(TestCase):
    setUp = reservation_tests.MarketplaceReservationsTest.setUp
    post = reservation_tests.MarketplaceReservationsTest.post
    order = reservation_tests.MarketplaceReservationsTest.order
    material = reservation_tests.MarketplaceReservationsTest.material
    receipt = reservation_tests.MarketplaceReservationsTest.receipt
    issue = reservation_tests.MarketplaceReservationsTest.issue
    setup_stock = reservation_tests.MarketplaceReservationsTest.setup_stock
    prepare = reservation_tests.MarketplaceReservationsTest.prepare
    cut = reservation_tests.MarketplaceReservationsTest.cut
    create_bundle = reservation_tests.MarketplaceReservationsTest.create_bundle
    setup_bundle = reservation_tests.MarketplaceReservationsTest.setup_bundle
    create_job = reservation_tests.MarketplaceReservationsTest.create_job
    complete = reservation_tests.MarketplaceReservationsTest.complete
    setup_job = reservation_tests.MarketplaceReservationsTest.setup_job
    finish = reservation_tests.MarketplaceReservationsTest.finish
    setup_finishing = reservation_tests.MarketplaceReservationsTest.setup_finishing
    inspect = reservation_tests.MarketplaceReservationsTest.inspect
    setup_qc = reservation_tests.MarketplaceReservationsTest.setup_qc
    receive = reservation_tests.MarketplaceReservationsTest.receive
    setup_receipt = reservation_tests.MarketplaceReservationsTest.setup_receipt
    move = reservation_tests.MarketplaceReservationsTest.move
    reserve = reservation_tests.MarketplaceReservationsTest.reserve
    release = reservation_tests.MarketplaceReservationsTest.release

    def pick(self, reservation, reference='PICK-001', quantity=4, staging_location='Meja Packing A', **options):
        picked_date=options.pop('picked_date','2026-09-23')
        return self.post('/api/marketplace-reservations/'+reservation['id']+'/picks',dict(
            reference=reference,quantity=quantity,staging_location=staging_location,picked_date=picked_date,
            reason='Barang diambil untuk pesanan marketplace'),**options)

    def test_partial_picks_move_reserved_stock_to_staging_with_lineage(self):
        order,qc,receipt=self.setup_receipt()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        reservation=self.reserve(receipt,quantity=6)
        first=self.pick(reservation,key='pick-one')
        self.assertEqual(first,self.pick(reservation,key='pick-one'))
        second=self.pick(reservation,reference='PICK-002',quantity=2,staging_location='Meja Packing B')
        self.assertEqual((first['reservation_reference'],first['receipt_reference'],first['final_qc_reference']),
                         (reservation['reference'],receipt['reference'],qc['reference']))
        current=self.client.get('/api/marketplace-reservations/'+reservation['id']).json()
        self.assertEqual((current['picked_quantity'],current['remaining_quantity']),(6,0))
        detail=self.client.get('/api/finished-goods-receipts/'+receipt['id']).json()
        balances={(row['location'],row['stock_status']):(row['quantity'],row['reserved_quantity'],
                  row['available_quantity']) for row in detail['inventory']}
        self.assertEqual(balances[('Rak Barang Jadi A','sellable')],(6,0,6))
        self.assertEqual(balances[('Meja Packing A','picked')],(4,0,0))
        self.assertEqual(balances[('Meja Packing B','picked')],(2,0,0))
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['picked_quantity'],aggregate['reserved_quantity'],
                          aggregate['available_quantity'],aggregate['hold_quantity'],aggregate['total_quantity']),
                         (6,6,0,6,8,20))
        listed=self.client.get('/api/orders/'+order['id']+'/marketplace-picks').json()
        self.assertEqual([row['id'] for row in listed],[second['id'],first['id']])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)

    def test_correction_restores_reserved_sellable_and_allows_release(self):
        _,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation)
        self.release(reservation,status=409)
        for role in (self.operator,self.viewer):
            self.post('/api/marketplace-picks/'+pick['id']+'/reverse',dict(reason='Salah pick'),
                      api_key=role['api_key'],status=403)
        corrected=self.post('/api/marketplace-picks/'+pick['id']+'/reverse',dict(reason='Salah meja'),key='pick-reverse')
        self.assertEqual(corrected,self.post('/api/marketplace-picks/'+pick['id']+'/reverse',
                                             dict(reason='Salah meja'),key='pick-reverse'))
        self.assertEqual(corrected['status'],'corrected')
        current=self.client.get('/api/marketplace-reservations/'+reservation['id']).json()
        self.assertEqual((current['picked_quantity'],current['remaining_quantity']),(0,6))
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['picked_quantity'],aggregate['reserved_quantity'],
                          aggregate['available_quantity']),(12,0,6,6))
        self.release(reservation)

    def test_validation_roles_dates_allocation_and_missing_records(self):
        _,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        self.pick(reservation,api_key=self.viewer['api_key'],status=403)
        self.pick(reservation,quantity=True,status=422)
        self.pick(reservation,picked_date='2026-09-19',status=422)
        self.pick(reservation,quantity=7,status=409)
        self.pick(reservation,quantity=4)
        self.pick(reservation,reference='PICK-OVER',quantity=3,status=409)
        self.assertEqual(self.client.get('/api/marketplace-picks/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/marketplace-picks').status_code,404)
        self.post('/api/marketplace-reservations/missing/picks',dict(reference='PICK-MISSING',quantity=1,
                  staging_location='Meja Packing',picked_date='2026-09-23',reason='Tidak ada'),status=404)

    def test_race_cannot_pick_more_than_reservation(self):
        _,_,receipt=self.setup_receipt(sellable=10,hold=0)
        reservation=self.reserve(receipt,quantity=10)
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/marketplace-reservations/'+reservation['id']+'/picks',json=dict(
                    reference='PICK-RACE-'+str(index),quantity=7,staging_location='Meja '+str(index),
                    picked_date='2026-09-23',reason='Uji pick bersamaan'),headers={
                    'X-API-Key':self.operator['api_key'],'Idempotency-Key':'pick-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])

    def test_rollback_cursor_backup_guards_and_migration_from_20(self):
        order,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_pick BEFORE INSERT ON requests WHEN NEW.key='fail-pick' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.pick(reservation,key='fail-pick',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/marketplace-picks').json(),[])
        first=self.pick(reservation,quantity=2)
        second=self.pick(reservation,reference='PICK-002',quantity=2)
        route='/api/orders/'+order['id']+'/marketplace-picks'
        page=self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'],second['id'])
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],first['id'])
        backup=self.path.with_name('marketplace-picking-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).marketplace_pick(first['id']),first)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE marketplace_picks SET reason=reason','DELETE FROM marketplace_picks'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO marketplace_picks(id,reference,reservation_id,quantity,staging_location,
                    picked_date,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',('bad','PICK-DIRECT',
                    reservation['id'],99,'Meja Bypass','2026-09-23','Bypass',self.admin['id'],
                    '2026-09-23T00:00:00+00:00'))

        fresh_path=self.path.with_name('schema20.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
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
            db.execute('PRAGMA user_version=20');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],33)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM marketplace_picks').fetchone()[0],0)
