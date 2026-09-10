from unittest import TestCase
from unittest.mock import patch

import test_production


class ActivityTest(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order
    move = test_production.ProductionTest.move

    def test_jakarta_day_boundaries_and_empty_day(self):
        with patch('beeloft.store.now', return_value='2026-09-09T16:59:59+00:00'):
            order = self.order()
        line = order['lines'][0]['id']
        for timestamp in ['2026-09-09T17:00:00+00:00', '2026-09-10T16:59:59.999999+00:00', '2026-09-10T17:00:00+00:00']:
            with patch('beeloft.store.now', return_value=timestamp):
                self.move(line, 'planned', 'cutting', 1)
        result = self.client.get('/api/activity?day=2026-09-10').json()
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['summary']['events'], 2)
        self.assertTrue(all(i['kind'] == 'movement' for i in result['items']))
        self.assertEqual(self.client.get('/api/activity?day=2026-09-11').json()['total'], 1)
        empty = self.client.get('/api/activity?day=2000-01-01').json()
        self.assertEqual(empty['items'], [])
        self.assertEqual(empty['summary']['warehouse_net'], 0)

    def test_all_event_types_and_reversal_on_its_recorded_day(self):
        with patch('beeloft.store.now', return_value='2026-09-10T01:00:00+00:00'):
            order = self.order(10)
            line = order['lines'][0]['id']
            for source, target in [('planned','cutting'),('cutting','sewing'),('sewing','finishing'),('finishing','qc'),('qc','warehouse')]:
                movement = self.move(line, source, target, 10)
            issue = self.post('/api/issues', {'line_id':line,'stage':'qc','owner_id':self.operator['id'],'description':'Periksa label'})
            self.post('/api/issues/' + issue['id'] + '/resolve', {'resolution':'Label sudah sesuai'})
            self.post('/api/orders/' + order['id'] + '/changes', {'owner_id':self.admin['id'], 'due_date':'2099-01-01', 'expected_revision':order['revision'], 'reason':'Target digeser'})
        with patch('beeloft.store.now', return_value='2026-09-11T01:00:00+00:00'):
            self.post('/api/movements/' + movement['id'] + '/reverse', {'reason':'Salah penerimaan'})
        today = self.client.get('/api/activity?day=2026-09-10').json()
        self.assertEqual(today['summary'], {'events':9,'warehouse_net':10,'issues_opened':1,'issues_resolved':1})
        self.assertEqual({i['kind'] for i in today['items']}, {'order_created','movement','issue_opened','issue_resolved','order_changed'})
        tomorrow = self.client.get('/api/activity?day=2026-09-11').json()
        self.assertEqual(tomorrow['summary']['warehouse_net'], -10)
        self.assertEqual(tomorrow['items'][0]['kind'], 'reversal')
        period = self.client.get('/api/activity?start_date=2026-09-10&end_date=2026-09-11').json()
        self.assertEqual(period['summary']['warehouse_net'],0)
        filtered = self.client.get('/api/activity?day=2026-09-10&kind=issue_opened').json()
        self.assertEqual(filtered['total'], 1)
        self.assertEqual(filtered['summary'], today['summary'])
        self.assertEqual(filtered['items'][0]['sku'], self.product['sku'])
        self.assertNotIn('api_key', str(today))

    def test_pagination_same_timestamp_and_new_activity(self):
        with patch('beeloft.store.now', return_value='2026-09-10T01:00:00+00:00'):
            order = self.order()
            line = order['lines'][0]['id']
            for _ in range(4):
                self.move(line,'planned','cutting',1)
        original = self.client.get('/api/activity?day=2026-09-10').json()['items']
        page = self.client.get('/api/activity?day=2026-09-10&limit=2').json()
        with patch('beeloft.store.now', return_value='2026-09-10T02:00:00+00:00'):
            self.move(line,'planned','cutting',1)
        ids = [i['event_id'] for i in page['items']]
        while page['next_before']:
            page = self.client.get('/api/activity', params={'day':'2026-09-10','limit':2,**page['next_before']}).json()
            ids += [i['event_id'] for i in page['items']]
        self.assertEqual(ids, [i['event_id'] for i in original])

    def test_access_and_invalid_filters(self):
        self.assertEqual(self.client.get('/api/activity',headers={'X-API-Key':'bad'}).status_code,401)
        for account in [self.admin,self.operator,self.viewer]:
            self.assertEqual(self.client.get('/api/activity',headers={'X-API-Key':account['api_key']}).status_code,200)
        for query in ['day=bad','day=0001-01-01','kind=bad','limit=0','limit=501','before_time=bad&before_id=x','before_id=x','before_time=2026-09-10T00:00:00Z','before_time=2026-09-10T00:00:00&before_id=x']:
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/api/activity?' + query).status_code,422)
