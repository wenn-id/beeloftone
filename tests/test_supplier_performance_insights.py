import sqlite3
from contextlib import closing
from unittest import TestCase

from beeloft.store import Store
import test_incoming_qc as qc_tests


class SupplierPerformanceInsightsTest(TestCase):
    setUp=qc_tests.IncomingQCTest.setUp
    post=qc_tests.IncomingQCTest.post
    material=qc_tests.IncomingQCTest.material
    order=qc_tests.IncomingQCTest.order
    payload=qc_tests.IncomingQCTest.payload
    create=qc_tests.IncomingQCTest.create
    decide=qc_tests.IncomingQCTest.decide
    supplier=qc_tests.IncomingQCTest.supplier
    setup_po=qc_tests.IncomingQCTest.setup_po
    issue=qc_tests.IncomingQCTest.issue
    detail=qc_tests.IncomingQCTest.detail
    cancel=qc_tests.IncomingQCTest.cancel
    setup_receipt=qc_tests.IncomingQCTest.setup_receipt
    receive=qc_tests.IncomingQCTest.receive
    reverse=qc_tests.IncomingQCTest.reverse
    intake=qc_tests.IncomingQCTest.intake
    inspect=qc_tests.IncomingQCTest.inspect

    def test_supplier_attention_combines_delivery_shortage_and_qc_by_unit(self):
        po,body=self.setup_receipt()
        intake=self.intake(po,body | {'reference':'QC-SUPPLIER','quantity':'2.125'},key='supplier-intake')
        self.inspect(intake,quantity='1.125',key='supplier-accept')
        self.inspect(intake,kind='reject',quantity='1',key='supplier-reject')
        material=self.client.get('/api/materials').json()[0]
        request=self.decide(self.create(self.payload(material,reference='PR-NO-ARRIVAL')),'approved')
        late_po=self.issue({'reference':'PO-NO-ARRIVAL','request_id':request['id'],
            'expected_revision':request['revision'],'supplier_id':po['supplier_id'],
            'expected_date':'2026-10-16','terms':'Bayar setelah diterima','reason':'Pesanan kedua',
            'prices':[{'material_id':material['id'],'unit_price':'12.34'}]})
        route='/api/supplier-performance-insights?as_of=2026-10-20&window_days=7'
        report=self.client.get(route).json()
        self.assertEqual(report['summary'],{'suppliers':1,'attention_suppliers':1,'healthy_suppliers':0,
            'purchase_orders':2,'arrived_purchase_orders':1,'on_time_first_arrivals':1,
            'late_first_arrivals':0,'overdue_no_arrival':1,'overdue_incomplete_purchase_orders':2,
            'closed_shortfall_purchase_orders':0,'qc_intakes':1,'quality_units_with_reject':1})
        self.assertEqual(report['total'],1)
        item=report['items'][0]
        self.assertEqual((item['supplier_code'],item['status'],item['purchase_order_count'],
                          item['average_first_arrival_delay_days'],item['maximum_first_arrival_delay_days']),
                         ('KAIN-A','attention',2,'0.00',0))
        self.assertEqual(item['flags'],['overdue_no_arrival','overdue_incomplete','quality_reject'])
        self.assertEqual(item['ordered_by_unit'],[{'unit':'m','quantity':'4.250'}])
        self.assertEqual(item['received_by_unit'],[{'unit':'m','quantity':'1.125'}])
        self.assertEqual(item['quality_by_unit'],[{'unit':'m','intake_count':1,'arrived':'2.125',
            'accepted':'1.125','rejected':'1.000','held':'0.000','usable_rate':'52.94',
            'reject_rate':'47.06'}])
        self.assertEqual([row['reference'] for row in item['purchase_orders']],
                         [late_po['reference'],po['reference']])

    def test_healthy_filters_roles_backup_and_read_only_behavior(self):
        po,body=self.setup_receipt()
        self.receive(po,body | {'quantity':'2.125','received_date':'2026-10-14'},key='healthy-receipt')
        base='/api/supplier-performance-insights?as_of=2026-10-20&window_days=7'
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        attention=self.client.get(base).json()
        self.assertEqual((attention['total'],attention['summary']['healthy_suppliers']),(0,1))
        report=self.client.get(base+'&status=all').json()
        self.assertEqual((report['total'],report['items'][0]['status'],
                          report['items'][0]['average_first_arrival_delay_days']),
                         (1,'healthy','-1.00'))
        self.assertEqual(report['items'][0]['flags'],[])
        self.assertEqual(self.client.get(base+'&status=healthy&query=kain-a').json()['total'],1)
        self.assertEqual(self.client.get(base+'&status=all&query=PO-001&offset=1').json()['items'],[])
        self.assertEqual(self.client.get('/api/supplier-performance-insights?as_of=2026-10-13').json()['total'],0)
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(base,headers={'X-API-Key':role['api_key']}).json(),attention)
        for invalid in ('window_days=6','window_days=731','status=bad','limit=0','offset=-1','query='+'x'*161):
            self.assertEqual(self.client.get('/api/supplier-performance-insights?'+invalid).status_code,422)
        self.assertEqual(self.client.get('/api/supplier-performance-insights',
                                         headers={'X-API-Key':'bad'}).status_code,401)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
        backup=self.path.with_name('supplier-performance-insights-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).supplier_performance_insights('2026-10-20',7,
            status='all')['items'][0]['supplier_id'],po['supplier_id'])
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],52)
