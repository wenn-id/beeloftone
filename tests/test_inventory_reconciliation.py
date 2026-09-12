import sqlite3
from contextlib import closing
from unittest import TestCase

from beeloft.store import Store
import test_returns_adjustments as returns_tests


class InventoryReconciliationTest(TestCase):
    setUp=returns_tests.ReturnsAdjustmentsTest.setUp
    post=returns_tests.ReturnsAdjustmentsTest.post
    order=returns_tests.ReturnsAdjustmentsTest.order
    material=returns_tests.ReturnsAdjustmentsTest.material
    receipt=returns_tests.ReturnsAdjustmentsTest.receipt
    issue=returns_tests.ReturnsAdjustmentsTest.issue
    setup_stock=returns_tests.ReturnsAdjustmentsTest.setup_stock
    prepare=returns_tests.ReturnsAdjustmentsTest.prepare
    cut=returns_tests.ReturnsAdjustmentsTest.cut
    create_bundle=returns_tests.ReturnsAdjustmentsTest.create_bundle
    setup_bundle=returns_tests.ReturnsAdjustmentsTest.setup_bundle
    create_job=returns_tests.ReturnsAdjustmentsTest.create_job
    complete=returns_tests.ReturnsAdjustmentsTest.complete
    setup_job=returns_tests.ReturnsAdjustmentsTest.setup_job
    finish=returns_tests.ReturnsAdjustmentsTest.finish
    setup_finishing=returns_tests.ReturnsAdjustmentsTest.setup_finishing
    inspect=returns_tests.ReturnsAdjustmentsTest.inspect
    setup_qc=returns_tests.ReturnsAdjustmentsTest.setup_qc
    receive=returns_tests.ReturnsAdjustmentsTest.receive
    setup_receipt=returns_tests.ReturnsAdjustmentsTest.setup_receipt
    move=returns_tests.ReturnsAdjustmentsTest.move
    reserve=returns_tests.ReturnsAdjustmentsTest.reserve
    release=returns_tests.ReturnsAdjustmentsTest.release

    def count(self, receipt, reference='COUNT-001', counted_quantity=10, **options):
        payload=dict(reference=reference,scanned_sku=options.pop('scanned_sku',receipt['sku']),
                     location=options.pop('location','Rak Barang Jadi A'),
                     stock_status=options.pop('stock_status','sellable'),counted_quantity=counted_quantity,
                     counted_date=options.pop('counted_date','2026-09-28'),reason='Hitung fisik stock opname')
        return self.post('/api/finished-goods-receipts/'+receipt['id']+'/stock-counts',payload,**options)

    def test_count_captures_expected_variance_lineage_and_zero_variance(self):
        order,_,receipt=self.setup_receipt()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        shortage=self.count(receipt,key='count-shortage')
        self.assertEqual(shortage,self.count(receipt,key='count-shortage'))
        self.assertEqual((shortage['expected_quantity'],shortage['counted_quantity'],shortage['quantity_delta']),
                         (12,10,-2))
        self.assertEqual((shortage['receipt_reference'],shortage['sku'],shortage['order_id']),
                         (receipt['reference'],receipt['sku'],order['id']))
        self.assertIsNotNone(shortage['adjustment_id'])
        exact=self.count(receipt,reference='COUNT-002',counted_quantity=8,stock_status='hold')
        self.assertEqual((exact['expected_quantity'],exact['quantity_delta'],exact['adjustment_id']),(8,0,None))
        current=self.client.get('/api/finished-goods-receipts/'+receipt['id']).json()
        sellable=next(row for row in current['inventory'] if row['stock_status']=='sellable')
        self.assertEqual(sellable['quantity'],10)
        listed=self.client.get('/api/orders/'+order['id']+'/finished-goods-stock-counts').json()
        self.assertEqual([row['id'] for row in listed],[exact['id'],shortage['id']])
        adjustments=self.client.get('/api/orders/'+order['id']+'/finished-goods-adjustments').json()
        self.assertEqual((len(adjustments),adjustments[0]['stock_count_id']),(1,shortage['id']))
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)

    def test_reserved_stock_guards_count_and_correction(self):
        _,_,receipt=self.setup_receipt()
        reserved=self.reserve(receipt,reference='MKT-COUNT',quantity=6)
        self.count(receipt,reference='COUNT-BLOCK',counted_quantity=5,status=409)
        counted=self.count(receipt,counted_quantity=7)
        self.post('/api/finished-goods-adjustments/'+counted['adjustment_id']+'/reverse',
                  dict(reason='Harus lewat stock opname'),status=409)
        corrected=self.post('/api/finished-goods-stock-counts/'+counted['id']+'/reverse',
                            dict(reason='Penghitungan fisik salah'))
        self.assertEqual(corrected['status'],'corrected')
        self.assertEqual(next(row for row in self.client.get('/api/finished-goods-receipts/'+receipt['id']).json()['inventory']
                              if row['stock_status']=='sellable')['quantity'],12)
        self.release(reserved,key='release-count')

    def test_positive_variance_correction_waits_for_reserved_stock(self):
        _,_,receipt=self.setup_receipt()
        counted=self.count(receipt,location='Rak Opname',counted_quantity=3)
        reserved=self.reserve(receipt,reference='MKT-COUNT-PLUS',location='Rak Opname',quantity=2)
        self.post('/api/finished-goods-stock-counts/'+counted['id']+'/reverse',
                  dict(reason='Hitungan salah'),status=409)
        self.release(reserved,key='release-count-plus')
        self.post('/api/finished-goods-stock-counts/'+counted['id']+'/reverse',dict(reason='Hitungan salah'))
        self.assertFalse(any(row['location']=='Rak Opname' for row in self.client.get('/api/warehouse-inventory').json()))

    def test_validation_roles_scan_date_and_missing_records(self):
        _,_,receipt=self.setup_receipt()
        self.count(receipt,api_key=self.viewer['api_key'],status=403)
        self.count(receipt,scanned_sku='SKU-SALAH',status=422)
        self.count(receipt,counted_date='2026-09-17',status=422)
        self.count(receipt,counted_quantity=True,status=422)
        self.count(receipt,stock_status='packed',status=422)
        self.assertEqual(self.client.get('/api/finished-goods-stock-counts/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/finished-goods-stock-counts').status_code,404)

    def test_direct_guard_immutability_backup_and_migration_from_24(self):
        _,_,receipt=self.setup_receipt()
        counted=self.count(receipt)
        backup=self.path.with_name('inventory-reconciliation-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).finished_goods_stock_count(counted['id']),counted)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE finished_goods_stock_counts SET reason=reason',
                        'DELETE FROM finished_goods_stock_counts'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO finished_goods_stock_counts(id,reference,receipt_id,scanned_sku,
                    location,stock_status,expected_quantity,counted_quantity,counted_date,reason,actor_id,created_at)
                    VALUES('bad','COUNT-BAD',?,?,?,?,99,9,'2026-09-28','Bad direct count',?,?)''',
                    (receipt['id'],receipt['sku'],'Rak Barang Jadi A','sellable',self.operator['id'],
                     '2026-09-28T00:00:00+00:00'))

        fresh=self.path.with_name('schema24.sqlite3')
        Store(fresh)
        with closing(sqlite3.connect(fresh)) as db:
            for trigger in ('finished_goods_stock_count_reverse_adjustment','finished_goods_stock_count_reversal_valid',
                            'finished_goods_stock_count_source_valid','finished_goods_reversal_valid',
                            'finished_goods_adjustment_reversal_valid'):
                db.execute('DROP TRIGGER '+trigger)
            db.execute('DROP INDEX finished_goods_adjustments_stock_count')
            db.execute('DROP TABLE finished_goods_stock_count_reversals')
            db.execute('DROP TABLE finished_goods_stock_counts')
            db.execute('ALTER TABLE finished_goods_adjustments DROP COLUMN stock_count_id')
            db.execute('PRAGMA user_version=24');db.commit()
        Store(fresh)
        with closing(sqlite3.connect(fresh)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],26)
            self.assertIn('stock_count_id',{row[1] for row in db.execute('PRAGMA table_info(finished_goods_adjustments)')})
            self.assertEqual(db.execute('SELECT COUNT(*) FROM finished_goods_stock_counts').fetchone()[0],0)
