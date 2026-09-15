import sqlite3
from contextlib import closing
from unittest import TestCase

from beeloft.store import Store
import test_returns_adjustments as adjustment_tests


class StockAdjustmentInsightsTest(TestCase):
    setUp=adjustment_tests.ReturnsAdjustmentsTest.setUp
    post=adjustment_tests.ReturnsAdjustmentsTest.post
    order=adjustment_tests.ReturnsAdjustmentsTest.order
    material=adjustment_tests.ReturnsAdjustmentsTest.material
    receipt=adjustment_tests.ReturnsAdjustmentsTest.receipt
    issue=adjustment_tests.ReturnsAdjustmentsTest.issue
    setup_stock=adjustment_tests.ReturnsAdjustmentsTest.setup_stock
    prepare=adjustment_tests.ReturnsAdjustmentsTest.prepare
    cut=adjustment_tests.ReturnsAdjustmentsTest.cut
    create_bundle=adjustment_tests.ReturnsAdjustmentsTest.create_bundle
    setup_bundle=adjustment_tests.ReturnsAdjustmentsTest.setup_bundle
    create_job=adjustment_tests.ReturnsAdjustmentsTest.create_job
    complete=adjustment_tests.ReturnsAdjustmentsTest.complete
    setup_job=adjustment_tests.ReturnsAdjustmentsTest.setup_job
    finish=adjustment_tests.ReturnsAdjustmentsTest.finish
    setup_finishing=adjustment_tests.ReturnsAdjustmentsTest.setup_finishing
    inspect=adjustment_tests.ReturnsAdjustmentsTest.inspect
    setup_qc=adjustment_tests.ReturnsAdjustmentsTest.setup_qc
    receive=adjustment_tests.ReturnsAdjustmentsTest.receive
    setup_receipt=adjustment_tests.ReturnsAdjustmentsTest.setup_receipt
    adjust=adjustment_tests.ReturnsAdjustmentsTest.adjust

    def test_flags_large_repeated_and_corrected_adjustments_with_provenance(self):
        _,_,receipt=self.setup_receipt()
        large=self.adjust(receipt,reference='ADJ-LARGE',quantity_delta=6,
                          adjusted_date='2026-10-01',key='large')
        corrected=self.adjust(receipt,reference='ADJ-CORRECTED',quantity_delta=-1,
                              adjusted_date='2026-10-02',key='corrected')
        self.post('/api/finished-goods-adjustments/'+corrected['id']+'/reverse',
                  {'reason':'Hitungan awal salah'},key='reverse-corrected')
        counted=self.post('/api/finished-goods-receipts/'+receipt['id']+'/stock-counts',{
            'reference':'COUNT-INSIGHT','scanned_sku':receipt['sku'],'location':'Rak Barang Jadi A',
            'stock_status':'sellable','counted_quantity':17,'counted_date':'2026-10-03',
            'reason':'Hitung fisik untuk audit'},key='count-insight')
        route=('/api/stock-adjustment-insights?as_of=2026-10-05&window_days=7&quantity_threshold=5'
               '&percentage_threshold=20&repeat_threshold=3&classification=all')
        report=self.client.get(route).json()
        self.assertEqual(report['summary'],{'adjustment_count':3,'flagged_adjustments':3,
            'high_risk_adjustments':1,'review_adjustments':2,'normal_adjustments':0,
            'active_adjustments':2,'corrected_adjustments':1,'manual_adjustments':2,
            'stock_count_adjustments':1,'absolute_quantity':8,'flagged_absolute_quantity':8,
            'repeated_buckets':1})
        self.assertEqual([row['reference'] for row in report['items']],
                         ['ADJ-LARGE','COUNT-INSIGHT','ADJ-CORRECTED'])
        high=report['items'][0]
        self.assertEqual((high['id'],high['classification'],high['receipt_share_percent'],
                          high['bucket_adjustment_count'],high['bucket_absolute_quantity']),
                         (large['id'],'high','30.00',3,8))
        self.assertEqual(high['flags'],['large_quantity','large_receipt_share','repeated_bucket'])
        stock_count=report['items'][1]
        self.assertEqual((stock_count['source'],stock_count['stock_count_id'],
                          stock_count['stock_count_reference'],stock_count['classification']),
                         ('stock_count',counted['id'],'COUNT-INSIGHT','review'))
        correction=report['items'][2]
        self.assertEqual((correction['record_status'],correction['classification']),('corrected','review'))
        self.assertEqual(correction['flags'],['repeated_bucket','corrected_record'])
        self.assertEqual(correction['reversal']['reason'],'Hitungan awal salah')

    def test_filters_validation_roles_backup_and_read_only_behavior(self):
        _,_,receipt=self.setup_receipt()
        normal=self.adjust(receipt,reference='ADJ-NORMAL',quantity_delta=1,location='Rak Audit Utara',
                           adjusted_date='2026-10-01',key='normal')
        base=('/api/stock-adjustment-insights?as_of=2026-10-05&window_days=7'
              '&quantity_threshold=5&percentage_threshold=20&repeat_threshold=3')
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        flagged=self.client.get(base).json()
        self.assertEqual((flagged['total'],flagged['summary']['normal_adjustments']),(0,1))
        all_rows=self.client.get(base+'&classification=all').json()
        self.assertEqual((all_rows['total'],all_rows['items'][0]['id'],all_rows['items'][0]['classification']),
                         (1,normal['id'],'normal'))
        self.assertEqual(self.client.get(base+'&classification=normal&query=adj-normal').json()['total'],1)
        self.assertEqual(self.client.get(base+'&classification=all&location=Audit').json()['total'],1)
        self.assertEqual(self.client.get(base+'&classification=all&stock_status=hold').json()['total'],0)
        self.assertEqual(self.client.get(base+'&classification=all&source=stock_count').json()['total'],0)
        self.assertEqual(self.client.get(base+'&classification=all&record_status=corrected').json()['total'],0)
        self.assertEqual(self.client.get(base+'&classification=all&offset=1').json()['items'],[])
        self.assertEqual(self.client.get('/api/stock-adjustment-insights?as_of=2026-09-30').json()['total'],0)
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(base,headers={'X-API-Key':role['api_key']}).json(),flagged)
        invalid=('window_days=6','window_days=366','quantity_threshold=0','percentage_threshold=0',
                 'percentage_threshold=101','repeat_threshold=1','classification=bad','source=bad',
                 'record_status=bad','stock_status=packed','limit=0','offset=-1','query='+'x'*161)
        for params in invalid:
            self.assertEqual(self.client.get('/api/stock-adjustment-insights?'+params).status_code,422)
        self.assertEqual(self.client.get('/api/stock-adjustment-insights',
                                         headers={'X-API-Key':'bad'}).status_code,401)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
        backup=self.path.with_name('stock-adjustment-insights-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).stock_adjustment_insights('2026-10-05',7,
            classification='all')['items'][0]['id'],normal['id'])
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],53)
