import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store
import test_production_cost as cost_tests


class ContributionMarginTest(TestCase):
    setUp = cost_tests.ProductionCostTest.setUp
    post = cost_tests.ProductionCostTest.post
    material = cost_tests.ProductionCostTest.material
    order = cost_tests.ProductionCostTest.order
    payload = cost_tests.ProductionCostTest.payload
    create = cost_tests.ProductionCostTest.create
    decide = cost_tests.ProductionCostTest.decide
    supplier = cost_tests.ProductionCostTest.supplier
    setup_po = cost_tests.ProductionCostTest.setup_po
    issue_po = cost_tests.ProductionCostTest.issue_po
    receive = cost_tests.ProductionCostTest.receive
    setup_costed_order = cost_tests.ProductionCostTest.setup_costed_order

    def setup_shipment(self, quantity=10):
        order, _, job = self.setup_costed_order()
        job = self.post('/api/sewing-jobs/'+job['id']+'/complete', dict(completed_quantity=20,
            defect_quantity=0, missing_quantity=0, returned_date='2026-10-17',
            reason='Hasil jahit lengkap'))
        finishing = self.post('/api/sewing-jobs/'+job['id']+'/finishing-records', dict(
            reference='MARGIN-FIN', quantity=20, thread_trimmed=True, ironed=True,
            labels_attached=True, hangtags_attached=True, packaged=True, completed_date='2026-10-18',
            reason='Finishing lengkap'))
        qc = self.post('/api/finishing-records/'+finishing['id']+'/qc-records', dict(
            reference='MARGIN-QC', measurement_notes='Ukuran sesuai', visual_notes='Visual sesuai',
            defect_type='Tidak ada', responsible_source='Tidak ada', disposition='Terima seluruhnya',
            accepted_quantity=20, rework_quantity=0, reject_quantity=0, inspection_date='2026-10-19',
            reason='QC lengkap'))
        receipt = self.post('/api/final-qc-records/'+qc['id']+'/finished-goods-receipts', dict(
            reference='MARGIN-FG', scanned_sku=qc['sku'], location='Rak margin', sellable_quantity=20,
            hold_quantity=0, received_date='2026-10-20', reason='Barang jadi diterima'))
        reservation = self.post('/api/finished-goods-receipts/'+receipt['id']+'/marketplace-reservations', dict(
            reference='MARGIN-RES', marketplace='Tokopedia', external_order_reference='TKP-MARGIN-1',
            location='Rak margin', quantity=quantity, reserved_date='2026-10-21',
            reason='Stok penjualan dialokasikan'))
        pick = self.post('/api/marketplace-reservations/'+reservation['id']+'/picks', dict(
            reference='MARGIN-PICK', quantity=quantity, staging_location='Meja margin',
            picked_date='2026-10-22', reason='Pesanan dipilih'))
        pack = self.post('/api/marketplace-picks/'+pick['id']+'/packs', dict(reference='MARGIN-PACK',
            quantity=quantity, packed_date='2026-10-23', reason='Pesanan dikemas'))
        shipment = self.post('/api/marketplace-packs/'+pack['id']+'/shipments', dict(
            reference='MARGIN-SHIP', quantity=quantity, carrier='JNE', tracking_number='MARGIN-TRACK',
            shipped_date='2026-10-24', reason='Pesanan diserahkan ke carrier'))
        return order, shipment

    def settlement_payload(self, reference='SETTLE-001', **changes):
        payload = dict(reference=reference, gross_revenue='1000', seller_discount='50',
            customer_refund='0', marketplace_fee='100', shipping_cost='25',
            other_variable_cost='10', settled_date='2026-10-25', reason='Settlement marketplace final')
        return payload | changes

    def settle(self, shipment, **options):
        payload = options.pop('payload', self.settlement_payload())
        return self.post('/api/marketplace-shipments/'+shipment['id']+'/sale-settlements', payload, **options)

    def report(self, order, api_key=None, status=200):
        response=self.client.get('/api/orders/'+order['id']+'/contribution-margin',
            headers={'X-API-Key':api_key} if api_key else None)
        self.assertEqual(response.status_code,status,response.text)
        return response.json()

    def test_exact_partial_sales_margin_and_lineage(self):
        order, shipment = self.setup_shipment()
        settlement = self.settle(shipment, key='settlement-once')
        self.assertEqual(settlement,self.settle(shipment,key='settlement-once'))
        self.assertEqual((settlement['gross_revenue'],settlement['net_revenue'],
            settlement['variable_selling_cost'],settlement['contribution_before_production']),
            ('1000.00','950.00','135.00','815.00'))
        self.assertEqual((settlement['shipment_reference'],settlement['marketplace'],
            settlement['return_quantity'],settlement['return_coverage_status']),
            (shipment['reference'],'Tokopedia',0,'current'))
        report=self.report(order,self.viewer['api_key'])
        self.assertEqual(report['status'],'complete')
        self.assertEqual((report['finished_quantity'],report['shipped_quantity'],report['net_sold_quantity']),
                         (20,10,10))
        self.assertEqual((report['net_revenue'],report['variable_selling_cost'],
            report['allocated_production_cost'],report['contribution_margin'],
            report['contribution_margin_rate']),('950.00','135.00','93.11','721.89','75.99'))
        self.assertEqual(report['production_cost']['total_cost'],'186.22')
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/sale-settlements').json()[0]['id'],
                         settlement['id'])

    def test_missing_and_stale_settlement_keep_margin_incomplete(self):
        order, shipment = self.setup_shipment()
        missing=self.report(order)
        self.assertEqual(missing['status'],'incomplete')
        self.assertIsNone(missing['contribution_margin'])
        self.assertEqual(missing['coverage_gaps'][0]['kind'],'missing_sales_settlement')
        settlement=self.settle(shipment)
        returned=self.post('/api/marketplace-shipments/'+shipment['id']+'/returns', dict(
            reference='MARGIN-RETURN',quantity=2,return_reason='too_small',return_location='Rak retur',
            stock_status='sellable',returned_date='2026-10-26',reason='Retur diterima'))
        stale=self.report(order)
        self.assertEqual(stale['coverage_gaps'][0]['kind'],'stale_return_coverage')
        self.assertEqual((stale['net_sold_quantity'],stale['contribution_margin']),(8,None))
        self.post('/api/marketplace-sale-settlements/'+settlement['id']+'/reverse',
                  {'reason':'Settlement belum mencakup retur'})
        with self.app.state.store.transaction(write=True) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO marketplace_shipment_reversals(shipment_id,reason,actor_id,created_at)
                    VALUES(?,?,?,?)''',(shipment['id'],'Bypass retur',self.admin['id'],
                    '2026-10-26T00:00:00+00:00'))
        replacement=self.settle(shipment,payload=self.settlement_payload('SETTLE-002',customer_refund='200'))
        self.assertEqual((replacement['return_quantity'],replacement['return_coverage_status']),(2,'current'))
        current=self.report(order)
        self.assertEqual((current['status'],current['net_revenue'],current['allocated_production_cost'],
            current['contribution_margin'],current['contribution_margin_rate']),
            ('complete','750.00','74.49','540.51','72.07'))
        self.post('/api/marketplace-returns/'+returned['id']+'/reverse',{'reason':'Retur dibatalkan'})
        self.assertEqual(self.report(order)['coverage_gaps'][0]['kind'],'stale_return_coverage')

    def test_roles_validation_correction_and_shipment_guard(self):
        order, shipment = self.setup_shipment()
        self.settle(shipment,api_key=self.viewer['api_key'],status=403)
        for change in ({'gross_revenue':'0'},{'marketplace_fee':'-1'},{'settled_date':'2026-10-23'},
                       {'unexpected':'x'}):
            self.settle(shipment,payload=self.settlement_payload() | change,status=422)
        settlement=self.settle(shipment,api_key=self.operator['api_key'])
        self.settle(shipment,payload=self.settlement_payload('SETTLE-DUP'),status=409)
        self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',{'reason':'Salah kirim'},status=409)
        self.post('/api/marketplace-sale-settlements/'+settlement['id']+'/reverse',
                  {'reason':'Salah settlement'},api_key=self.operator['api_key'],status=403)
        corrected=self.post('/api/marketplace-sale-settlements/'+settlement['id']+'/reverse',
                            {'reason':'Salah settlement'},key='settlement-reverse')
        self.assertEqual(corrected,self.post('/api/marketplace-sale-settlements/'+settlement['id']+'/reverse',
            {'reason':'Salah settlement'},key='settlement-reverse'))
        self.assertEqual(corrected['status'],'corrected')
        self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',{'reason':'Salah kirim'})
        self.assertEqual(self.client.get('/api/marketplace-sale-settlements/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/contribution-margin').status_code,404)
        empty=self.post('/api/orders',dict(reference='MARGIN-EMPTY',title='Margin kosong',
            owner_id=self.operator['id'],due_date='2026-12-31',lines=[{'product_id':self.product['id'],'quantity':1}]))
        self.assertEqual({gap['kind'] for gap in self.report(empty)['coverage_gaps']},
                         {'no_sales_shipments','incomplete_production_cost','no_finished_quantity'})

    def test_concurrent_write_backup_immutability_and_migration(self):
        order, shipment = self.setup_shipment()
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/marketplace-shipments/'+shipment['id']+'/sale-settlements',
                    json=self.settlement_payload('SETTLE-RACE-'+str(index)),headers={
                    'X-API-Key':self.operator['api_key'],'Idempotency-Key':'settle-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])
        settlement=self.client.get('/api/orders/'+order['id']+'/sale-settlements').json()[0]
        backup=self.path.with_name('margin-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).marketplace_sale_settlement(settlement['id']),settlement)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE marketplace_sale_settlements SET reason=reason',
                        'DELETE FROM marketplace_sale_settlements'):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)

        fresh=self.path.with_name('schema29.sqlite3')
        Store(fresh)
        with closing(sqlite3.connect(fresh)) as db:
            db.execute('DROP TRIGGER marketplace_shipment_reversal_valid')
            db.execute('DROP TABLE marketplace_sale_settlement_reversals')
            db.execute('DROP TABLE marketplace_sale_settlements')
            db.execute('PRAGMA user_version=29')
            db.commit()
        Store(fresh)
        with closing(sqlite3.connect(fresh)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],40)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM marketplace_sale_settlements').fetchone()[0],0)
