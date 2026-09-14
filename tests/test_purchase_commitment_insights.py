import sqlite3
from contextlib import closing
from unittest import TestCase
from unittest.mock import patch

from beeloft.store import Store
import test_supplier_payment_approvals as payment_tests
import test_purchase_orders as po_tests


class PurchaseCommitmentInsightsTest(TestCase):
    setUp=payment_tests.SupplierPaymentApprovalTest.setUp
    post=payment_tests.SupplierPaymentApprovalTest.post
    material=payment_tests.SupplierPaymentApprovalTest.material
    order=payment_tests.SupplierPaymentApprovalTest.order
    payload=payment_tests.SupplierPaymentApprovalTest.payload
    create=payment_tests.SupplierPaymentApprovalTest.create
    decide=payment_tests.SupplierPaymentApprovalTest.decide
    supplier=payment_tests.SupplierPaymentApprovalTest.supplier
    setup_po=payment_tests.SupplierPaymentApprovalTest.setup_po
    submit_po=po_tests.PurchaseOrderTest.submit_po
    approve_po=po_tests.PurchaseOrderTest.approve_po
    issue=payment_tests.SupplierPaymentApprovalTest.issue
    cancel=po_tests.PurchaseOrderTest.cancel
    setup_receipt=payment_tests.SupplierPaymentApprovalTest.setup_receipt
    receive=payment_tests.SupplierPaymentApprovalTest.receive
    payment_body=payment_tests.SupplierPaymentApprovalTest.payment_body
    request_payment=payment_tests.SupplierPaymentApprovalTest.request_payment

    def test_partial_receipt_exposes_overdue_commitment_and_payment_position(self):
        with patch('beeloft.store.now',return_value='2026-09-30T18:00:00+00:00'):
            po,body=self.setup_receipt()
            self.receive(po,body)
            self.request_payment(po,changes={'amount':'10.00'})
        route='/api/purchase-commitment-insights?as_of=2026-10-20&due_soon_days=7'
        report=self.client.get(route).json()
        self.assertEqual(report['summary'],{'purchase_orders':1,'open_purchase_orders':1,
            'fulfilled_purchase_orders':0,'overdue_purchase_orders':1,'due_soon_purchase_orders':0,
            'scheduled_purchase_orders':0,'purchase_order_value':'26.22',
            'usable_received_value':'13.88','open_commitment_value':'12.34',
            'payment_pending':'10.00','payment_approved':'0.00','payment_unrequested':'3.88'})
        self.assertEqual((report['ledger_basis'],report['received_basis'],report['currency'],report['total']),
                         ('current_active_purchase_orders','usable_material_receipts','IDR',1))
        item=report['items'][0]
        self.assertEqual((item['purchase_order_reference'],item['status'],item['overdue_days'],
                          item['purchase_order_value'],item['usable_received_value'],
                          item['open_commitment_value']),('PO-001','overdue',5,'26.22','13.88','12.34'))
        self.assertEqual(item['lines'],[{'material_id':po['lines'][0]['material_id'],
            'code':po['lines'][0]['code'],'name':po['lines'][0]['name'],'unit':'m','ordered_quantity':'2.125',
            'usable_received_quantity':'1.125','open_quantity':'1.000','unit_price':'12.34',
            'ordered_value':'26.22','usable_received_value':'13.88','open_commitment_value':'12.34'}])
        self.assertEqual(self.client.get(route+'&status=due_soon').json()['total'],0)
        self.assertEqual(self.client.get(route+'&status=all&query='+po['lines'][0]['code']).json()['total'],1)
        self.assertEqual(self.client.get(route+'&status=all&query=PO-001&offset=1').json()['items'],[])
        self.assertEqual(self.client.get('/api/purchase-commitment-insights?as_of=2026-10-10'
                                         '&due_soon_days=7&status=due_soon').json()['total'],1)
        self.assertEqual(self.client.get('/api/purchase-commitment-insights?as_of=2026-10-01'
                                         '&due_soon_days=7&status=scheduled').json()['total'],1)

    def test_population_filters_roles_backup_and_read_only_behavior(self):
        with patch('beeloft.store.now',return_value='2026-10-01T02:00:00+00:00'):
            po,body=self.setup_receipt()
            self.receive(po,body | {'quantity':'2.125'})
            material=self.client.get('/api/materials').json()[0]
            request=self.decide(self.create(self.payload(material,reference='PR-IGNORED')),'approved')
            ignored_body={'reference':'PO-IGNORED','request_id':request['id'],
                'expected_revision':request['revision'],'supplier_id':po['supplier_id'],
                'expected_date':'2026-10-15','terms':'Tunai','reason':'Uji populasi',
                'prices':[{'material_id':material['id'],'unit_price':'10.00'}]}
            pending=self.submit_po(ignored_body)
            self.assertEqual(self.client.get('/api/purchase-commitment-insights?as_of=2026-10-20'
                                             '&status=all').json()['total'],1)
            self.approve_po(pending,'rejected')
            self.assertEqual(self.client.get('/api/purchase-commitment-insights?as_of=2026-10-20'
                                             '&status=all').json()['total'],1)
        base='/api/purchase-commitment-insights?as_of=2026-10-20&due_soon_days=7'
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        self.assertEqual(self.client.get(base).json()['total'],0)
        report=self.client.get(base+'&status=all').json()
        self.assertEqual((report['total'],report['items'][0]['status'],
                          report['items'][0]['open_commitment_value']),(1,'fulfilled','0.00'))
        self.assertEqual(self.client.get(base+'&status=fulfilled&query=kain-a').json()['total'],1)
        self.assertEqual(self.client.get('/api/purchase-commitment-insights?as_of=2026-09-30&status=all')
                         .json()['total'],0)
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(base,headers={'X-API-Key':role['api_key']}).json(),
                             self.client.get(base).json())
        for invalid in ('due_soon_days=0','due_soon_days=91','status=bad','limit=0','offset=-1',
                        'query='+'x'*161):
            self.assertEqual(self.client.get('/api/purchase-commitment-insights?'+invalid).status_code,422)
        self.assertEqual(self.client.get('/api/purchase-commitment-insights',
                                         headers={'X-API-Key':'bad'}).status_code,401)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
        backup=self.path.with_name('purchase-commitment-insights-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).purchase_commitment_insights('2026-10-20',7,status='all')
                         ['items'][0]['purchase_order_id'],po['id'])
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],48)
        self.post('/api/purchase-orders/'+po['id']+'/close',{'reason':'Penerimaan selesai'})
        self.assertEqual(self.client.get(base+'&status=all').json()['total'],0)
