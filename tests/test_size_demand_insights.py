from contextlib import closing
from datetime import date
import sqlite3
from unittest import TestCase

from beeloft.store import Store
import test_demand_forecast as forecast_tests


class SizeDemandInsightsTest(TestCase):
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
        response=self.client.get('/api/size-demand-insights',params=params)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def add_size(self, sku='LUNA-BLUE-L', name='Luna Blue', color='Blue', size='L'):
        return self.post('/api/products',dict(sku=sku,name=name,color=color,size=size))

    def test_size_family_ranks_repeat_demand_and_current_stockout_risk(self):
        _,first=self.setup_shipment()
        second=self.second_shipment(first)
        self.post('/api/marketplace-shipments/'+second['id']+'/returns',dict(
            reference='SIZE-RETURN',quantity=2,return_reason='too_small',return_location='Rak retur',
            stock_status='sellable',returned_date='2026-11-07',reason='Retur untuk demand neto'))
        large=self.add_size()
        report=self.report(as_of='2026-11-15',window_days=14,lookahead_days=15,query=large['sku'])
        self.assertEqual((report['history_start'],report['previous_period_end'],
                          report['recent_period_start'],report['as_of']),
                         ('2026-10-19','2026-11-01','2026-11-02','2026-11-15'))
        self.assertEqual(report['summary'],{'families':1,'size_variants':2,'families_out_of_stock':0,
            'families_within_lookahead':1,'sizes_out_of_stock':0,'consistent_demand_leaders':1,
            'earliest_projected_stockout_date':'2026-11-30'})
        family=report['items'][0]
        self.assertEqual((family['name'],family['color'],family['risk_status'],
                          family['first_stockout_sizes'],family['consistent_leader_sizes']),
                         ('Luna Blue','Blue','within_lookahead',['M'],['M']))
        medium=family['sizes'][0]
        self.assertEqual((medium['sku'],medium['previous_net_demand'],medium['recent_net_demand'],
                          medium['forecast_daily_rate'],medium['available_quantity'],medium['days_of_cover'],
                          medium['projected_stockout_date'],medium['previous_demand_rank'],
                          medium['recent_demand_rank'],medium['risk_rank'],medium['recent_demand_share']),
                         ('LUNA-BLUE-M',10,4,'0.4143',6,'14.48','2026-11-30',1,1,1,'100.00'))
        no_history=family['sizes'][1]
        self.assertEqual((no_history['sku'],no_history['days_of_cover'],no_history['risk_status'],
                          no_history['previous_demand_rank'],no_history['recent_demand_rank']),
                         ('LUNA-BLUE-L',None,'no_observed_demand',None,None))

        self.add_size('OTHER-M','Produk lain','Black','M')
        self.add_size('OTHER-L','Produk lain','Black','L')
        page=self.report(as_of='2026-11-15',window_days=14,lookahead_days=15,limit=1,offset=1)
        self.assertEqual((page['total'],len(page['items']),page['items'][0]['name']),(2,1,'Produk lain'))
        self.post('/api/marketplace-shipments/'+first['id']+'/reverse',{'reason':'Shipment lama dikoreksi'})
        corrected=self.report(as_of='2026-11-15',window_days=14,lookahead_days=15,query='LUNA')
        self.assertEqual(corrected['items'][0]['consistent_leader_sizes'],[])

    def test_filters_roles_validation_backup_and_read_only_behavior(self):
        self.setup_shipment()
        self.add_size()
        params=dict(as_of='2026-11-15',window_days=14,lookahead_days=30,query='luna-blue-l')
        expected=self.report(**params)
        self.assertEqual(expected['total'],1)
        self.assertEqual({row['size'] for row in expected['items'][0]['sizes']},{'M','L'})
        self.add_size('UNSIZED-ONE','Tanpa pembanding','Gray','')
        self.add_size('UNSIZED-M','Tanpa pembanding','Gray','M')
        self.assertEqual(self.report(as_of='2026-11-15',query='Tanpa pembanding')['total'],0)
        self.assertEqual(self.report(**(params|{'marketplace':'Shopee'}))['items'][0]['risk_status'],
                         'no_observed_demand')
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        for role in (self.operator,self.viewer):
            response=self.client.get('/api/size-demand-insights',params=params,
                                     headers={'X-API-Key':role['api_key']})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json(),expected)
        for invalid in ({'window_days':6},{'window_days':91},{'lookahead_days':0},
                        {'lookahead_days':181},{'as_of':'invalid'},{'limit':0},
                        {'offset':-1},{'query':'x'*161}):
            self.assertEqual(self.client.get('/api/size-demand-insights',params=invalid).status_code,422)
        self.assertEqual(self.client.get('/api/size-demand-insights',
                         headers={'X-API-Key':'bad'}).status_code,401)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
        backup=self.path.with_name('size-demand-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).size_demand_insights(date(2026,11,15),14,30,'luna-blue-l'),expected)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],48)
