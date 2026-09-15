from contextlib import closing
from datetime import date
import sqlite3
from unittest import TestCase

from beeloft.store import Store
import test_demand_forecast as forecast_tests


class DeadStockInsightsTest(TestCase):
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

    def report(self, **params):
        response=self.client.get('/api/dead-stock-insights',params=params)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def scenario(self):
        _,first=self.setup_shipment()
        second=self.second_shipment(first)
        returned=self.post('/api/marketplace-shipments/'+second['id']+'/returns',dict(
            reference='DEAD-RETURN',quantity=2,return_reason='too_small',return_location='Rak retur',
            stock_status='sellable',returned_date='2026-11-07',reason='Retur untuk demand neto'))
        return first,second,returned

    def test_dead_stock_candidate_uses_available_age_and_recent_net_demand(self):
        first,second,returned=self.scenario()
        report=self.report(as_of='2027-02-15',inactivity_days=90,query=self.product['sku'])
        self.assertEqual((report['period_start'],report['definition'],report['stock_scope']),
            ('2026-11-18','available_stock_aged_without_recent_net_demand',
             'current_internal_sellable_available_inventory'))
        self.assertEqual(report['summary'],{'products_with_available_stock':1,'available_quantity':6,
            'dead_stock_candidates':1,'dead_stock_quantity':6,'aging_no_sales_products':0,
            'aging_no_sales_quantity':0,'moving_products':0,'moving_quantity':0,
            'oldest_candidate_receipt_date':'2026-10-20'})
        row=report['items'][0]
        self.assertEqual((row['sku'],row['status'],row['available_quantity'],row['active_lot_count'],
                          row['oldest_available_receipt_date'],row['newest_available_receipt_date'],
                          row['oldest_stock_age_days']),
                         ('LUNA-BLUE-M','dead_stock_candidate',6,1,'2026-10-20','2026-10-20',118))
        self.assertEqual((row['recent_shipped_quantity'],row['recent_returned_quantity'],
                          row['recent_net_demand'],row['recent_daily_rate'],row['days_of_cover']),
                         (0,0,0,'0.0000',None))
        self.assertEqual((row['last_shipped_date'],row['last_net_sale_date'],
                          row['days_since_last_net_sale']),('2026-11-05','2026-11-05',102))
        self.assertEqual(self.report(as_of='2027-02-15',inactivity_days=90,
                         query=self.product['sku'],status='moving')['total'],0)

        moving=self.report(as_of='2026-11-15',inactivity_days=30,
                           query=self.product['sku'],status='all')['items'][0]
        self.assertEqual((moving['status'],moving['recent_shipped_quantity'],
                          moving['recent_returned_quantity'],moving['recent_net_demand'],
                          moving['recent_daily_rate'],moving['days_of_cover']),
                         ('moving',16,2,14,'0.4667','12.86'))
        aging=self.report(as_of='2026-11-15',inactivity_days=30,query=self.product['sku'],
                          marketplace='Shopee',status='all')['items'][0]
        self.assertEqual((aging['status'],aging['recent_net_demand'],aging['oldest_stock_age_days']),
                         ('aging_no_sales',0,26))

        self.post('/api/marketplace-returns/'+returned['id']+'/reverse',{'reason':'Retur dikoreksi'})
        self.post('/api/marketplace-shipments/'+second['id']+'/reverse',{'reason':'Shipment kedua dikoreksi'})
        self.post('/api/marketplace-shipments/'+first['id']+'/reverse',{'reason':'Shipment pertama dikoreksi'})
        corrected=self.report(as_of='2027-02-15',inactivity_days=90,
                              query=self.product['sku'])['items'][0]
        self.assertEqual((corrected['last_shipped_date'],corrected['last_net_sale_date']),(None,None))

    def test_filters_roles_validation_backup_and_read_only_behavior(self):
        self.scenario()
        params=dict(as_of='2027-02-15',inactivity_days=90,query='luna-blue-m')
        expected=self.report(**params)
        self.assertEqual(self.report(**(params|{'query':'tidak-ada'}))['total'],0)
        self.assertEqual(self.report(**(params|{'offset':1}))['items'],[])
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        for role in (self.operator,self.viewer):
            response=self.client.get('/api/dead-stock-insights',params=params,
                                     headers={'X-API-Key':role['api_key']})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json(),expected)
        for invalid in ({'inactivity_days':6},{'inactivity_days':731},{'status':'unknown'},
                        {'as_of':'invalid'},{'limit':0},{'offset':-1},{'query':'x'*161}):
            self.assertEqual(self.client.get('/api/dead-stock-insights',params=invalid).status_code,422)
        self.assertEqual(self.client.get('/api/dead-stock-insights',
                         headers={'X-API-Key':'bad'}).status_code,401)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
        backup=self.path.with_name('dead-stock-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).dead_stock_insights(date(2027,2,15),90,'luna-blue-m'),expected)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],53)
