from unittest import TestCase

import test_po_receipts as receipt_tests


class ProductionCostTest(TestCase):
    setUp = receipt_tests.PurchaseReceiptTest.setUp
    post = receipt_tests.PurchaseReceiptTest.post
    material = receipt_tests.PurchaseReceiptTest.material
    order = receipt_tests.PurchaseReceiptTest.order
    payload = receipt_tests.PurchaseReceiptTest.payload
    create = receipt_tests.PurchaseReceiptTest.create
    decide = receipt_tests.PurchaseReceiptTest.decide
    supplier = receipt_tests.PurchaseReceiptTest.supplier
    setup_po = receipt_tests.PurchaseReceiptTest.setup_po
    issue_po = receipt_tests.PurchaseReceiptTest.issue
    receive = receipt_tests.PurchaseReceiptTest.receive

    def report(self, order, api_key=None, status=200):
        response = self.client.get('/api/orders/'+order['id']+'/production-cost',
                                   headers={'X-API-Key':api_key} if api_key else None)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def setup_costed_order(self):
        pr, payload = self.setup_po()
        po = self.issue_po(payload)
        batch = self.receive(po, dict(material_id=po['lines'][0]['material_id'], reference='COST-BATCH',
            quantity='2.125', location='Rak biaya', received_date='2026-10-15', reason='Bahan diterima'))
        order = self.client.get('/api/orders/'+pr['order_id']).json()
        line = order['lines'][0]
        self.post('/api/movements', dict(line_id=line['id'], from_stage='planned', to_stage='cutting',
                  quantity=20, reason='Mulai cutting biaya'))
        issue = self.post('/api/material-issues', dict(batch_id=batch['id'], order_id=order['id'],
                          quantity='2.125', reason='Bahan untuk costing'))
        run = self.post('/api/orders/'+order['id']+'/cutting-runs', dict(reference='COST-CUT',
            issue_id=issue['id'], used='2', waste='0.125', reason='Pemakaian aktual costing',
            outputs=[dict(line_id=line['id'], quantity=20)]))
        bundle = self.post('/api/cutting-runs/'+run['id']+'/bundles', dict(reference='COST-BUNDLE',
            output_movement_id=run['outputs'][0]['id'], quantity=20, reason='Bundle costing'))
        job = self.post('/api/bundles/'+bundle['id']+'/sewing-jobs', dict(reference='COST-SEW',
            assignment_type='makloon', assignee='Atelier Biaya', quantity_out=20, cost='160.00',
            sent_date='2026-10-16', reason='Biaya makloon aktual'))
        return order, batch, job

    def test_exact_priced_material_waste_and_active_sewing_cost(self):
        order, batch, job = self.setup_costed_order()
        report = self.report(order)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual((report['material_cost'], report['sewing_cost'], report['known_cost'],
                          report['total_cost']), ('26.22','160.00','186.22','186.22'))
        self.assertEqual(report['target_quantity'], order['target_quantity'])
        self.assertEqual(report['finished_quantity'], 0)
        self.assertEqual(report['cost_per_target_unit'], '1.86')
        self.assertIsNone(report['cost_per_finished_unit'])
        material = report['materials'][0]
        self.assertEqual((material['batch_id'], material['used'], material['waste'],
                          material['consumed'], material['unit_price'], material['cost']),
                         (batch['id'],'2.000','0.125','2.125','12.34','26.22'))
        self.assertEqual(material['purchase_order_reference'], 'PO-001')
        self.assertEqual(report['sewing_jobs'][0]['id'], job['id'])
        self.assertEqual(report['coverage_gaps'], [])

        self.post('/api/sewing-jobs/'+job['id']+'/reverse', {'reason':'Job dibatalkan'})
        corrected = self.report(order)
        self.assertEqual((corrected['sewing_cost'], corrected['known_cost'], corrected['total_cost']),
                         ('0.00','26.22','26.22'))

    def test_unpriced_and_unreported_material_make_total_incomplete(self):
        material = self.material('COST-MANUAL')
        batch = self.post('/api/material-batches', dict(material_id=material['id'],
            reference='COST-MANUAL-BATCH', supplier='Pemasok manual', location='Rak manual',
            received_date='2026-10-01', quantity='3', reason='Stok tanpa PO'))
        order = self.order(reference='PROD-COST-GAP')
        issue = self.post('/api/material-issues', dict(batch_id=batch['id'], order_id=order['id'],
                          quantity='3', reason='Bahan manual'))
        self.post('/api/material-consumption', dict(issue_id=issue['id'], used='1', waste='0.5',
                  reason='Pemakaian parsial'))
        report = self.report(order)
        self.assertEqual(report['status'], 'incomplete')
        self.assertEqual((report['known_cost'], report['material_cost'], report['total_cost']),
                         ('0.00','0.00',None))
        self.assertEqual({gap['kind'] for gap in report['coverage_gaps']},
                         {'unpriced_consumption','unreported_issue'})
        row = report['materials'][0]
        self.assertEqual((row['consumed'], row['unreported'], row['unit_price'], row['cost']),
                         ('1.500','1.500',None,None))

    def test_empty_order_is_explicitly_incomplete(self):
        order = self.order(reference='PROD-NO-COST')
        report = self.report(order)
        self.assertEqual(report['status'], 'incomplete')
        self.assertEqual(report['coverage_gaps'], [{'kind':'no_material_consumption'}])
        self.assertEqual(report['known_cost'], '0.00')
        self.assertIsNone(report['total_cost'])

    def test_access_missing_order_and_backup_recompute(self):
        order, _, _ = self.setup_costed_order()
        self.assertEqual(self.report(order, self.viewer['api_key'])['total_cost'], '186.22')
        self.report(order, 'bad', 401)
        self.assertEqual(self.client.get('/api/orders/missing/production-cost').status_code, 404)
        backup = self.path.parent/'cost-backup.sqlite3'
        self.app.state.store.backup(backup)
        from beeloft.store import Store
        self.assertEqual(Store(backup).production_cost(order['id']), self.report(order))
