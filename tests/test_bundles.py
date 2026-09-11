from unittest import TestCase

import test_cutting as cutting_tests


class BundleTest(TestCase):
    setUp = cutting_tests.CuttingTest.setUp
    post = cutting_tests.CuttingTest.post
    order = cutting_tests.CuttingTest.order
    material = cutting_tests.CuttingTest.material
    receipt = cutting_tests.CuttingTest.receipt
    issue = cutting_tests.CuttingTest.issue
    setup_stock = cutting_tests.CuttingTest.setup_stock
    prepare = cutting_tests.CuttingTest.prepare
    cut = cutting_tests.CuttingTest.cut

    def setup_run(self):
        _, order, _, body = self.prepare()
        run = self.cut(order, body, key='cut-for-bundle')
        return order, run

    def create_bundle(self, run, reference='BDL-001', quantity=8, **options):
        body = dict(reference=reference,
                    output_movement_id=run['outputs'][0]['id'],
                    quantity=quantity,
                    reason='Pisahkan hasil cutting untuk sewing')
        return self.post('/api/cutting-runs/'+run['id']+'/bundles', body, **options)

    def test_create_partial_bundles_links_source_without_changing_wip(self):
        order, run = self.setup_run()
        before = self.client.get('/api/orders/'+order['id']).json()['totals']
        first = self.create_bundle(run, key='bundle-one')
        self.assertEqual(first, self.create_bundle(run, key='bundle-one'))
        second = self.create_bundle(run, reference='BDL-002', quantity=12, key='bundle-two')
        self.assertEqual((first['quantity'], second['quantity']), (8, 12))
        self.assertEqual(first['order_id'], order['id'])
        self.assertEqual(first['cutting_run_id'], run['id'])
        self.assertEqual(first['output_movement_id'], run['outputs'][0]['id'])
        self.assertEqual(first['status'], 'active')
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'], before)
        detail = self.client.get('/api/cutting-runs/'+run['id']).json()
        self.assertEqual(detail['outputs'][0]['bundled_quantity'], 20)
        self.assertEqual(detail['outputs'][0]['unbundled_quantity'], 0)
        self.assertEqual([row['reference'] for row in detail['bundles']], ['BDL-002', 'BDL-001'])
        listed = self.client.get('/api/orders/'+order['id']+'/bundles').json()
        self.assertEqual([row['id'] for row in listed], [second['id'], first['id']])
        self.assertEqual(self.client.get('/api/bundles/'+first['id']).json(), first)
