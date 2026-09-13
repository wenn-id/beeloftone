import sqlite3
from contextlib import closing
from datetime import date
from unittest import TestCase

from beeloft.store import Store
import test_contribution_margin as margin_tests


class DemandForecastTest(TestCase):
    setUp = margin_tests.ContributionMarginTest.setUp
    post = margin_tests.ContributionMarginTest.post
    material = margin_tests.ContributionMarginTest.material
    order = margin_tests.ContributionMarginTest.order
    payload = margin_tests.ContributionMarginTest.payload
    create = margin_tests.ContributionMarginTest.create
    decide = margin_tests.ContributionMarginTest.decide
    supplier = margin_tests.ContributionMarginTest.supplier
    setup_po = margin_tests.ContributionMarginTest.setup_po
    issue_po = margin_tests.ContributionMarginTest.issue_po
    receive = margin_tests.ContributionMarginTest.receive
    setup_costed_order = margin_tests.ContributionMarginTest.setup_costed_order
    setup_shipment = margin_tests.ContributionMarginTest.setup_shipment

    def forecast(self, **params):
        response = self.client.get('/api/demand-forecast', params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def second_shipment(self, first, quantity=6, marketplace='Tokopedia'):
        receipt_id = first['receipt_id']
        reservation = self.post('/api/finished-goods-receipts/'+receipt_id+'/marketplace-reservations', dict(
            reference='FORECAST-RES-2', marketplace=marketplace,
            external_order_reference='FORECAST-ORDER-2', location='Rak margin', quantity=quantity,
            reserved_date='2026-11-02', reason='Permintaan periode terbaru'))
        pick = self.post('/api/marketplace-reservations/'+reservation['id']+'/picks', dict(
            reference='FORECAST-PICK-2', quantity=quantity, staging_location='Meja forecast',
            picked_date='2026-11-03', reason='Pesanan forecast dipilih'))
        pack = self.post('/api/marketplace-picks/'+pick['id']+'/packs', dict(
            reference='FORECAST-PACK-2', quantity=quantity, packed_date='2026-11-04',
            reason='Pesanan forecast dikemas'))
        return self.post('/api/marketplace-packs/'+pack['id']+'/shipments', dict(
            reference='FORECAST-SHIP-2', quantity=quantity, carrier='JNE',
            tracking_number='FORECAST-TRACK-2', shipped_date='2026-11-05',
            reason='Pesanan forecast dikirim'))

    def test_weighted_two_window_forecast_subtracts_returns(self):
        _, first = self.setup_shipment()
        second = self.second_shipment(first)
        self.post('/api/marketplace-shipments/'+second['id']+'/returns', dict(
            reference='FORECAST-RETURN', quantity=2, return_reason='too_small',
            return_location='Rak retur', stock_status='sellable', returned_date='2026-11-07',
            reason='Retur diterima sebelum tanggal forecast'))

        report = self.forecast(as_of='2026-11-15', window_days=14, horizon_days=30,
                               query=self.product['sku'])
        self.assertEqual((report['history_start'], report['previous_period_end'],
                          report['recent_period_start'], report['as_of']),
                         ('2026-10-19', '2026-11-01', '2026-11-02', '2026-11-15'))
        self.assertEqual((report['method'], report['recent_weight'], report['previous_weight']),
                         ('weighted_two_window_average', '0.70', '0.30'))
        self.assertEqual(report['total_forecast_quantity'], '12.43')
        row = report['items'][0]
        self.assertEqual((row['previous_shipped_quantity'], row['previous_returned_quantity'],
                          row['previous_net_demand']), (10, 0, 10))
        self.assertEqual((row['recent_shipped_quantity'], row['recent_returned_quantity'],
                          row['recent_net_demand']), (6, 2, 4))
        self.assertEqual((row['historical_daily_rate'], row['forecast_daily_rate'],
                          row['forecast_quantity']), ('0.5000', '0.4143', '12.43'))
        self.assertEqual((row['history_status'], row['shipment_count'], row['marketplaces'],
                          row['trend'], row['trend_percent']),
                         ('observed', 2, ['Tokopedia'], 'down', '-60.00'))

    def test_no_history_search_marketplace_and_pagination_are_explicit(self):
        _, first = self.setup_shipment()
        self.second_shipment(first, marketplace='Shopee')
        empty = self.post('/api/products', dict(sku='NO-HISTORY-L', name='Belum terjual',
                                                color='Putih', size='L'))
        no_history = self.forecast(as_of='2026-11-15', query='belum TERJUAL')
        self.assertEqual(no_history['total'], 1)
        self.assertEqual((no_history['items'][0]['id'], no_history['items'][0]['history_status'],
                          no_history['items'][0]['forecast_quantity'], no_history['items'][0]['trend']),
                         (empty['id'], 'no_history', '0.00', 'flat'))
        shopee = self.forecast(as_of='2026-11-15', marketplace='shopee',
                               query=self.product['sku'], limit=1, offset=0)
        self.assertEqual((shopee['marketplace'], shopee['total'], len(shopee['items'])),
                         ('shopee', 1, 1))
        self.assertEqual((shopee['items'][0]['shipment_count'], shopee['items'][0]['marketplaces']),
                         (1, ['Shopee']))
        page = self.forecast(as_of='2026-11-15', limit=1, offset=1)
        self.assertEqual((page['total'], page['offset'], page['limit'], len(page['items'])),
                         (2, 1, 1, 1))

    def test_as_of_excludes_future_and_corrected_shipments(self):
        _, first = self.setup_shipment()
        second = self.second_shipment(first)
        before = self.forecast(as_of='2026-11-01', window_days=14, horizon_days=14,
                               query=self.product['sku'])['items'][0]
        self.assertEqual((before['shipment_count'], before['recent_net_demand'],
                          before['forecast_quantity']), (1, 10, '7.00'))
        self.post('/api/marketplace-shipments/'+first['id']+'/reverse', {'reason':'Salah kirim'})
        after = self.forecast(as_of='2026-11-15', window_days=14, horizon_days=14,
                              query=self.product['sku'])['items'][0]
        self.assertEqual((after['shipment_count'], after['previous_net_demand'],
                          after['recent_net_demand'], after['forecast_quantity']),
                         (1, 0, 6, '4.20'))
        self.assertEqual(after['trend'], 'new')
        self.assertEqual(second['status'], 'shipped')

    def test_access_validation_backup_and_schema_version(self):
        _, shipment = self.setup_shipment()
        params = dict(as_of='2026-11-15', window_days=14, horizon_days=30,
                      query=self.product['sku'])
        response = self.client.get('/api/demand-forecast', params=params,
                                   headers={'X-API-Key':self.viewer['api_key']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/api/demand-forecast', headers={'X-API-Key':'bad'}).status_code, 401)
        for invalid in ({'window_days':6}, {'window_days':91}, {'horizon_days':0},
                        {'horizon_days':181}, {'as_of':'invalid'}, {'limit':501}, {'offset':-1}):
            self.assertEqual(self.client.get('/api/demand-forecast', params=invalid).status_code, 422)

        expected = self.forecast(**params)
        backup = self.path.with_name('forecast-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).demand_forecast(date(2026, 11, 15), 14, 30,
                                                       self.product['sku']), expected)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],44)
        self.assertEqual(shipment['quantity'], 10)
