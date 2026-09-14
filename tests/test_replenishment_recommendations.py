import sqlite3
from contextlib import closing
from datetime import date
from unittest import TestCase

from beeloft.store import Store
import test_demand_forecast as forecast_tests


class ReplenishmentRecommendationsTest(TestCase):
    setUp = forecast_tests.DemandForecastTest.setUp
    post = forecast_tests.DemandForecastTest.post
    material = forecast_tests.DemandForecastTest.material
    order = forecast_tests.DemandForecastTest.order
    payload = forecast_tests.DemandForecastTest.payload
    create = forecast_tests.DemandForecastTest.create
    decide = forecast_tests.DemandForecastTest.decide
    supplier = forecast_tests.DemandForecastTest.supplier
    setup_po = forecast_tests.DemandForecastTest.setup_po
    issue_po = forecast_tests.DemandForecastTest.issue_po
    receive = forecast_tests.DemandForecastTest.receive
    setup_costed_order = forecast_tests.DemandForecastTest.setup_costed_order
    setup_shipment = forecast_tests.DemandForecastTest.setup_shipment
    second_shipment = forecast_tests.DemandForecastTest.second_shipment

    def recommendations(self, **params):
        response=self.client.get('/api/replenishment-recommendations',params=params)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def save_bom(self, quantity='1.000'):
        material=self.client.get('/api/materials').json()[0]
        bom=self.post('/api/products/'+self.product['id']+'/bom',dict(expected_revision=0,
            reason='Standar bahan replenishment',components=[dict(material_id=material['id'],quantity=quantity)]))
        return material,bom

    def scenario(self, second_quantity=6, with_bom=True):
        _,first=self.setup_shipment()
        second=self.second_shipment(first,quantity=second_quantity)
        material=bom=None
        if with_bom:
            material,bom=self.save_bom()
        return first,second,material,bom

    def exact_params(self):
        return dict(as_of='2026-11-15',window_days=14,lead_time_days=180,
                    review_period_days=180,safety_stock_days=90,batch_multiple=12,
                    query=self.product['sku'])

    def test_stockout_and_production_recommendation_are_auditable(self):
        self.scenario()
        report=self.recommendations(**self.exact_params())
        self.assertEqual((report['coverage_days'],report['method'],report['coverage_complete']),
                         (450,'forecast_inventory_position',True))
        self.assertEqual(report['planning_horizon_end'],'2028-02-08')
        self.assertEqual(report['forecast'],dict(history_start='2026-10-19',
            previous_period_end='2026-11-01',recent_period_start='2026-11-02',
            recent_weight='0.70',previous_weight='0.30'))
        row=report['product_recommendations'][0]
        self.assertEqual((row['previous_net_demand'],row['recent_net_demand'],
                          row['forecast_daily_rate']), (10,6,'0.5143'))
        self.assertEqual((row['sellable_quantity'],row['reserved_quantity'],
                          row['available_quantity'],row['inbound_production_quantity'],
                          row['inventory_position']), (4,0,4,80,84))
        self.assertEqual((row['days_of_cover'],row['projected_stockout_date'],
                          row['reorder_point_quantity'],row['target_stock_quantity']),
                         ('7.78','2026-11-23',139,232))
        self.assertEqual((row['stockout_risk'],row['batch_multiple'],
                          row['recommended_production_quantity']),
                         ('stockout_before_replenishment',12,156))
        self.assertEqual(report['summary']['recommended_production_quantity'],156)
        material=report['material_purchase_recommendations'][0]
        self.assertEqual((material['existing_production_requirement'],
                          material['recommended_production_requirement'],material['total_requirement']),
                         ('97.875','156.000','253.875'))
        self.assertEqual((material['on_hand_quantity'],material['open_purchase_request_quantity'],
                          material['open_purchase_order_quantity'],material['recommended_purchase_quantity'],
                          material['status']),('0.000','0.000','0.000','253.875','purchase'))

    def test_open_pr_and_po_prevent_duplicate_purchase_recommendations(self):
        _,_,material,_=self.scenario()
        request=self.create(dict(reference='PR-REPLENISH',order_id=None,required_date='2026-11-20',
            estimated_value='1000.00',reason='Rencana pembelian replenishment',
            lines=[dict(material_id=material['id'],quantity='50')]))
        request=self.decide(request,'approved')
        with_request=self.recommendations(**self.exact_params())
        row=with_request['material_purchase_recommendations'][0]
        self.assertEqual((row['open_purchase_request_quantity'],row['open_purchase_order_quantity'],
                          row['recommended_purchase_quantity']),('50.000','0.000','203.875'))
        self.assertEqual(with_request['summary']['open_purchase_requests'],1)

        supplier=self.client.get('/api/suppliers').json()[0]
        purchase_order=self.post('/api/purchase-orders',dict(reference='PO-REPLENISH',
            request_id=request['id'],expected_revision=request['revision'],supplier_id=supplier['id'],
            expected_date='2026-11-20',terms='Bayar setelah diterima',reason='Pesanan replenishment',
            prices=[dict(material_id=material['id'],unit_price='10')]))
        with_order=self.recommendations(**self.exact_params())
        row=with_order['material_purchase_recommendations'][0]
        self.assertEqual((row['open_purchase_request_quantity'],row['open_purchase_order_quantity'],
                          row['recommended_purchase_quantity']),('0.000','50.000','203.875'))
        self.assertEqual((with_order['summary']['open_purchase_requests'],
                          with_order['summary']['open_purchase_orders']),(0,1))

        purchase_order=self.post('/api/purchase-orders/'+purchase_order['id']+'/decisions',dict(
            status='approved',expected_revision=purchase_order['revision'],reason='PO replenishment disetujui'))
        self.receive(purchase_order,dict(material_id=material['id'],reference='REPLENISH-BATCH',
            quantity='10',location='Rak replenishment',received_date='2026-11-20',
            reason='Penerimaan sebagian replenishment'))
        received=self.recommendations(**self.exact_params())['material_purchase_recommendations'][0]
        self.assertEqual((received['on_hand_quantity'],received['open_purchase_order_quantity'],
                          received['recommended_purchase_quantity']),('10.000','40.000','203.875'))
        self.create(dict(reference='PR-TOO-LATE',order_id=None,required_date='2030-01-01',
            estimated_value='1000.00',reason='Kebutuhan di luar horizon',
            lines=[dict(material_id=material['id'],quantity='50')]))
        after_future=self.recommendations(**self.exact_params())
        material_row=after_future['material_purchase_recommendations'][0]
        self.assertEqual(material_row['recommended_purchase_quantity'],'203.875')
        self.assertEqual(after_future['summary']['open_purchase_requests'],0)

    def test_missing_bom_no_history_risk_and_pagination_are_explicit(self):
        self.scenario(with_bom=False)
        missing=self.recommendations(**self.exact_params())
        self.assertFalse(missing['coverage_complete'])
        self.assertEqual({(gap['context'],gap['sku']) for gap in missing['coverage_gaps']},
                         {('active_production',self.product['sku']),
                          ('recommended_production',self.product['sku'])})
        self.assertEqual(missing['material_purchase_recommendations'],[])
        empty=self.post('/api/products',dict(sku='REPLENISH-NONE',name='Produk tanpa demand',
                                             color='Putih',size='L'))
        no_history=self.recommendations(as_of='2026-11-15',query='tanpa DEMAND')
        row=no_history['product_recommendations'][0]
        self.assertEqual((row['id'],row['stockout_risk'],row['days_of_cover'],
                          row['projected_stockout_date'],row['recommended_production_quantity']),
                         (empty['id'],'insufficient_history',None,None,0))
        page=self.recommendations(as_of='2026-11-15',limit=1,offset=1)
        self.assertEqual((page['total'],page['offset'],page['limit'],
                          len(page['product_recommendations'])),(2,1,1,1))

    def test_access_validation_backup_and_schema_version(self):
        self.scenario()
        params=self.exact_params()
        response=self.client.get('/api/replenishment-recommendations',params=params,
                                 headers={'X-API-Key':self.viewer['api_key']})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/replenishment-recommendations',
                                         headers={'X-API-Key':'bad'}).status_code,401)
        invalid=({'window_days':6},{'lead_time_days':0},{'lead_time_days':181},
                 {'review_period_days':0},{'review_period_days':181},{'safety_stock_days':-1},
                 {'safety_stock_days':91},{'batch_multiple':0},{'batch_multiple':100001},
                 {'as_of':'bad'},{'limit':501},{'offset':-1})
        for values in invalid:
            self.assertEqual(self.client.get('/api/replenishment-recommendations',
                                             params=values).status_code,422)
        expected=self.recommendations(**params)
        backup=self.path.with_name('replenishment-backup.sqlite3')
        self.app.state.store.backup(backup)
        actual=Store(backup).replenishment_recommendations(date(2026,11,15),14,180,180,90,12,
                                                           self.product['sku'])
        self.assertEqual(actual,expected)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],47)
