import csv
import io
from unittest import TestCase
from unittest.mock import patch

import test_production


class ActivityExportTest(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order
    move = test_production.ProductionTest.move

    def test_inclusive_range_and_legacy_single_day(self):
        with patch('beeloft.store.now', return_value='2026-09-09T17:00:00+00:00'):
            order = self.order()
        with patch('beeloft.store.now', return_value='2026-09-11T16:59:59+00:00'):
            self.move(order['lines'][0]['id'],'planned','cutting',1)
        with patch('beeloft.store.now', return_value='2026-09-11T17:00:00+00:00'):
            self.move(order['lines'][0]['id'],'planned','cutting',1)
        report = self.client.get('/api/activity?start_date=2026-09-10&end_date=2026-09-11').json()
        self.assertEqual(report['total'],2)
        self.assertEqual(report['start_date'],'2026-09-10')
        self.assertEqual(report['end_date'],'2026-09-11')
        self.assertEqual(self.client.get('/api/activity?day=2026-09-10').json()['total'],1)
        for path in ['/api/activity','/api/activity.csv']:
            for query in ['start_date=2026-01-01','end_date=2026-01-01','start_date=2026-02-01&end_date=2026-01-01',
                          'start_date=2020-01-01&end_date=2026-01-01','day=2026-01-01&start_date=2026-01-01&end_date=2026-01-01']:
                self.assertEqual(self.client.get(path+'?'+query).status_code,422)

    def test_csv_all_rows_filter_unicode_quotes_and_formula_protection(self):
        with patch('beeloft.store.now',return_value='2026-09-10T01:00:00+00:00'):
            order = self.order(title='=1+1',reference='CSV-TEST')
            for _ in range(55):
                self.move(order['lines'][0]['id'],'planned','cutting',1,reason='=SUM(1,2)\n"Jahitan", café')
        response = self.client.get('/api/activity.csv?day=2026-09-10&kind=movement')
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        self.assertIn('attachment;',response.headers['content-disposition'])
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows),55)
        self.assertEqual(rows[0]['Nama order'],"'=1+1")
        self.assertEqual(rows[0]['Catatan'],"'=SUM(1,2)\n\"Jahitan\", café")
        self.assertEqual(rows[0]['Waktu Jakarta'],'2026-09-10 08:00:00')
        self.assertEqual(rows[0]['Jumlah pcs'],'1')
        self.assertNotIn('api_key',response.text)
        with patch('beeloft.api.MAX_EXPORT_ROWS',2):
            self.assertEqual(self.client.get('/api/activity.csv?day=2026-09-10').status_code,422)

    def test_csv_access_and_empty_file(self):
        for account in [self.admin,self.operator,self.viewer]:
            response = self.client.get('/api/activity.csv?day=2000-01-01',headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))),1)
        self.assertEqual(self.client.get('/api/activity.csv',headers={'X-API-Key':'bad'}).status_code,401)
