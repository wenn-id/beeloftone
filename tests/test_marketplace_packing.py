import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_marketplace_picking as picking_tests


class MarketplacePackingTest(TestCase):
    setUp = picking_tests.MarketplacePickingTest.setUp
    post = picking_tests.MarketplacePickingTest.post
    order = picking_tests.MarketplacePickingTest.order
    material = picking_tests.MarketplacePickingTest.material
    receipt = picking_tests.MarketplacePickingTest.receipt
    issue = picking_tests.MarketplacePickingTest.issue
    setup_stock = picking_tests.MarketplacePickingTest.setup_stock
    prepare = picking_tests.MarketplacePickingTest.prepare
    cut = picking_tests.MarketplacePickingTest.cut
    create_bundle = picking_tests.MarketplacePickingTest.create_bundle
    setup_bundle = picking_tests.MarketplacePickingTest.setup_bundle
    create_job = picking_tests.MarketplacePickingTest.create_job
    complete = picking_tests.MarketplacePickingTest.complete
    setup_job = picking_tests.MarketplacePickingTest.setup_job
    finish = picking_tests.MarketplacePickingTest.finish
    setup_finishing = picking_tests.MarketplacePickingTest.setup_finishing
    inspect = picking_tests.MarketplacePickingTest.inspect
    setup_qc = picking_tests.MarketplacePickingTest.setup_qc
    receive = picking_tests.MarketplacePickingTest.receive
    setup_receipt = picking_tests.MarketplacePickingTest.setup_receipt
    move = picking_tests.MarketplacePickingTest.move
    reserve = picking_tests.MarketplacePickingTest.reserve
    release = picking_tests.MarketplacePickingTest.release
    pick = picking_tests.MarketplacePickingTest.pick

    def pack(self, pick, reference='PACK-001', quantity=3, **options):
        packed_date=options.pop('packed_date','2026-09-24')
        return self.post('/api/marketplace-picks/'+pick['id']+'/packs',dict(
            reference=reference,quantity=quantity,packed_date=packed_date,
            reason='Barang selesai dikemas untuk pengiriman'),**options)

    def test_partial_packs_move_picked_stock_to_packed_with_lineage(self):
        order,_,receipt=self.setup_receipt()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=4)
        first=self.pack(pick,key='pack-one')
        self.assertEqual(first,self.pack(pick,key='pack-one'))
        second=self.pack(pick,reference='PACK-002',quantity=1)
        self.assertEqual((first['pick_reference'],first['reservation_reference'],first['receipt_reference']),
                         (pick['reference'],reservation['reference'],receipt['reference']))
        current=self.client.get('/api/marketplace-picks/'+pick['id']).json()
        self.assertEqual((current['packed_quantity'],current['remaining_quantity']),(4,0))
        detail=self.client.get('/api/finished-goods-receipts/'+receipt['id']).json()
        balances={(row['location'],row['stock_status']):row['quantity'] for row in detail['inventory']}
        self.assertEqual(balances[('Rak Barang Jadi A','sellable')],8)
        self.assertNotIn(('Meja Packing A','picked'),balances)
        self.assertEqual(balances[('Meja Packing A','packed')],4)
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['picked_quantity'],aggregate['packed_quantity'],
                          aggregate['reserved_quantity'],aggregate['available_quantity'],aggregate['total_quantity']),
                         (8,0,4,2,6,20))
        listed=self.client.get('/api/orders/'+order['id']+'/marketplace-packs').json()
        self.assertEqual([row['id'] for row in listed],[second['id'],first['id']])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)

    def test_correction_restores_picked_and_unblocks_pick_correction(self):
        _,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=4)
        pack=self.pack(pick)
        self.post('/api/marketplace-picks/'+pick['id']+'/reverse',dict(reason='Salah pick'),status=409)
        for role in (self.operator,self.viewer):
            self.post('/api/marketplace-packs/'+pack['id']+'/reverse',dict(reason='Salah pack'),
                      api_key=role['api_key'],status=403)
        corrected=self.post('/api/marketplace-packs/'+pack['id']+'/reverse',dict(reason='Kemasan rusak'),key='pack-reverse')
        self.assertEqual(corrected,self.post('/api/marketplace-packs/'+pack['id']+'/reverse',
                                             dict(reason='Kemasan rusak'),key='pack-reverse'))
        self.assertEqual(corrected['status'],'corrected')
        aggregate=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((aggregate['sellable_quantity'],aggregate['picked_quantity'],aggregate['packed_quantity'],
                          aggregate['reserved_quantity'],aggregate['available_quantity']),(8,4,0,2,6))
        self.post('/api/marketplace-picks/'+pick['id']+'/reverse',dict(reason='Pick salah'))

    def test_validation_roles_dates_allocation_and_missing_records(self):
        _,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=4)
        self.pack(pick,api_key=self.viewer['api_key'],status=403)
        self.pack(pick,quantity=True,status=422)
        self.pack(pick,packed_date='2026-09-22',status=422)
        self.pack(pick,quantity=5,status=409)
        self.pack(pick,quantity=3)
        self.pack(pick,reference='PACK-OVER',quantity=2,status=409)
        self.assertEqual(self.client.get('/api/marketplace-packs/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/marketplace-packs').status_code,404)
        self.post('/api/marketplace-picks/missing/packs',dict(reference='PACK-MISSING',quantity=1,
                  packed_date='2026-09-24',reason='Tidak ada'),status=404)

    def test_race_cannot_pack_more_than_pick(self):
        _,_,receipt=self.setup_receipt(sellable=10,hold=0)
        reservation=self.reserve(receipt,quantity=10)
        pick=self.pick(reservation,quantity=10)
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/marketplace-picks/'+pick['id']+'/packs',json=dict(
                    reference='PACK-RACE-'+str(index),quantity=7,packed_date='2026-09-24',
                    reason='Uji pack bersamaan'),headers={'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'pack-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])

    def test_rollback_cursor_backup_guards_and_migration_from_21(self):
        order,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=6)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_pack BEFORE INSERT ON requests WHEN NEW.key='fail-pack' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.pack(pick,key='fail-pack',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/marketplace-packs').json(),[])
        first=self.pack(pick,quantity=2)
        second=self.pack(pick,reference='PACK-002',quantity=2)
        route='/api/orders/'+order['id']+'/marketplace-packs'
        page=self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'],second['id'])
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'],first['id'])
        backup=self.path.with_name('marketplace-packing-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).marketplace_pack(first['id']),first)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE marketplace_packs SET reason=reason','DELETE FROM marketplace_packs'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO marketplace_packs(id,reference,pick_id,quantity,packed_date,reason,
                    actor_id,created_at) VALUES(?,?,?,?,?,?,?,?)''',('bad','PACK-DIRECT',pick['id'],99,
                    '2026-09-24','Bypass',self.admin['id'],'2026-09-24T00:00:00+00:00'))

        fresh_path=self.path.with_name('schema21.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
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
            db.execute('PRAGMA user_version=21');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],32)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM marketplace_packs').fetchone()[0],0)
