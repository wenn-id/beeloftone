import sqlite3
from contextlib import closing
from unittest import TestCase
from unittest.mock import patch

from beeloft.store import Store
import test_purchase_orders as po_tests


class MaterialPriceInsightsTest(TestCase):
    setUp=po_tests.PurchaseOrderTest.setUp
    post=po_tests.PurchaseOrderTest.post
    material=po_tests.PurchaseOrderTest.material
    order=po_tests.PurchaseOrderTest.order
    payload=po_tests.PurchaseOrderTest.payload
    create=po_tests.PurchaseOrderTest.create
    decide=po_tests.PurchaseOrderTest.decide
    supplier=po_tests.PurchaseOrderTest.supplier
    setup_po=po_tests.PurchaseOrderTest.setup_po
    submit_po=po_tests.PurchaseOrderTest.submit_po
    approve_po=po_tests.PurchaseOrderTest.approve_po
    issue=po_tests.PurchaseOrderTest.issue
    cancel=po_tests.PurchaseOrderTest.cancel

    def new_order(self, material, supplier_id, reference, price, decision='approved'):
        request=self.decide(self.create(self.payload(material,reference='PR-'+reference)),'approved')
        body={'reference':reference,'request_id':request['id'],'expected_revision':request['revision'],
            'supplier_id':supplier_id,'expected_date':'2026-10-20','terms':'Bayar setelah diterima',
            'reason':'Pembanding harga','prices':[{'material_id':material['id'],'unit_price':price}]}
        if decision=='approved': return self.issue(body)
        order=self.submit_po(body)
        return self.approve_po(order,decision) if decision=='rejected' else order

    def test_price_change_uses_approved_active_orders_for_same_material_and_supplier(self):
        with patch('beeloft.store.now',return_value='2026-10-01T02:00:00+00:00'):
            request,body=self.setup_po()
            first=self.issue(body)
        material=self.client.get('/api/materials').json()[0]
        with patch('beeloft.store.now',return_value='2026-10-10T02:00:00+00:00'):
            latest=self.new_order(material,first['supplier_id'],'PO-PRICE-2','15.00')
            other_supplier=self.post('/api/suppliers',{'code':'KAIN-B','name':'Supplier pembanding',
                'contact':'Tim pembelian','address':'Jakarta','reason':'Pembanding supplier'})
            self.new_order(material,other_supplier['id'],'PO-OTHER-SUPPLIER','30.00')
        with patch('beeloft.store.now',return_value='2026-10-11T02:00:00+00:00'):
            cancelled=self.new_order(material,first['supplier_id'],'PO-PRICE-CANCELLED','99.00')
            self.cancel(cancelled)
        with patch('beeloft.store.now',return_value='2026-10-12T02:00:00+00:00'):
            self.new_order(material,first['supplier_id'],'PO-PRICE-PENDING','98.00',decision='pending')
        with patch('beeloft.store.now',return_value='2026-10-13T02:00:00+00:00'):
            self.new_order(material,first['supplier_id'],'PO-PRICE-REJECTED','97.00',decision='rejected')

        route='/api/material-price-insights?as_of=2026-10-15&window_days=30'
        report=self.client.get(route).json()
        self.assertEqual(report['summary'],{'series':2,'materials':1,'suppliers':2,'observations':3,
            'changed_series':1,'increased_series':1,'decreased_series':0,'stable_series':0,
            'single_observation_series':1})
        self.assertEqual((report['date_basis'],report['currency'],report['grouping'],report['total']),
                         ('purchase_order_created_date','IDR','material_and_supplier',1))
        item=report['items'][0]
        self.assertEqual((item['status'],item['observation_count'],item['earliest_unit_price'],
                          item['latest_unit_price'],item['price_change'],item['price_change_percent']),
                         ('increased',2,'12.34','15.00','2.66','21.56'))
        self.assertEqual((item['minimum_unit_price'],item['maximum_unit_price'],item['average_unit_price']),
                         ('12.34','15.00','13.67'))
        self.assertEqual([row['purchase_order_reference'] for row in item['history']],
                         [latest['reference'],first['reference']])
        self.assertEqual(self.client.get(route+'&status=decreased').json()['total'],0)
        self.assertEqual(self.client.get(route+'&status=all&query=PO-PRICE-2').json()['total'],1)

    def test_single_observation_filters_roles_backup_and_read_only_behavior(self):
        with patch('beeloft.store.now',return_value='2026-10-01T02:00:00+00:00'):
            request,body=self.setup_po()
            order=self.issue(body)
        base='/api/material-price-insights?as_of=2026-10-15&window_days=30'
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        self.assertEqual(self.client.get(base).json()['total'],0)
        report=self.client.get(base+'&status=all').json()
        self.assertEqual((report['total'],report['items'][0]['status'],
                          report['items'][0]['price_change_percent']),
                         (1,'single_observation','0.00'))
        self.assertEqual(self.client.get(base+'&status=single_observation&query=kain-a').json()['total'],1)
        self.assertEqual(self.client.get(base+'&status=all&query=PO-001&offset=1').json()['items'],[])
        self.assertEqual(self.client.get('/api/material-price-insights?as_of=2026-09-30&status=all').json()['total'],0)
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(base,headers={'X-API-Key':role['api_key']}).json(),
                             self.client.get(base).json())
        for invalid in ('window_days=6','window_days=731','status=bad','limit=0','offset=-1','query='+'x'*161):
            self.assertEqual(self.client.get('/api/material-price-insights?'+invalid).status_code,422)
        self.assertEqual(self.client.get('/api/material-price-insights',
                                         headers={'X-API-Key':'bad'}).status_code,401)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
        backup=self.path.with_name('material-price-insights-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).material_price_insights('2026-10-15',30,status='all')
                         ['items'][0]['supplier_id'],order['supplier_id'])
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],52)
