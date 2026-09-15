import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store, audit_category, audit_value
import test_production as production_tests


class AuditTrailTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post
    order=production_tests.ProductionTest.order

    def test_every_committed_write_is_audited_exactly_once(self):
        baseline=self.client.get('/api/audit-events').json()['total']
        body={'reference':'AUDIT-ORDER','title':'Order audit','owner_id':self.operator['id'],
              'due_date':'2026-12-01','lines':[{'product_id':self.product['id'],'quantity':5}]}
        order=self.post('/api/orders',body,key='audit-order')
        self.assertEqual(order,self.post('/api/orders',body,key='audit-order'))
        self.post('/api/orders',body|{'title':'Konflik'},key='audit-order',status=409)
        self.post('/api/issues',{'line_id':order['lines'][0]['id'],'stage':'sewing',
            'description':'Kendala untuk audit','owner_id':self.operator['id']},key='audit-issue',
            api_key=self.operator['api_key'])
        report=self.client.get('/api/audit-events').json()
        self.assertEqual(report['total'],baseline+2)
        events={row['operation']:row for row in report['items']}
        self.assertEqual(events['order']['request_key'],'audit-order')
        self.assertEqual(events['order']['subject_reference'],'AUDIT-ORDER')
        self.assertEqual(events['issue']['actor_id'],self.operator['id'])
        self.assertEqual(events['issue']['actor_name'],self.operator['name'])

    def test_approval_filter_actor_search_and_cursor(self):
        material=self.post('/api/materials',{'code':'AUDIT-CLOTH','name':'Kain audit','unit':'m'})
        request=self.post('/api/purchase-requests',{'reference':'PR-AUDIT-001','order_id':None,
            'required_date':'2026-12-10','estimated_value':'123456.78','reason':'Kebutuhan audit',
            'lines':[{'material_id':material['id'],'quantity':'2.500'}]},
            api_key=self.operator['api_key'])
        self.post('/api/purchase-requests/'+request['id']+'/decisions',{
            'status':'approved','expected_revision':request['revision'],'reason':'Audit approval'})
        approval=self.client.get('/api/audit-events?category=approval').json()
        self.assertEqual(approval['total'],1)
        self.assertEqual((approval['items'][0]['operation'],approval['items'][0]['subject_reference']),
                         ('purchase-request-decision:'+request['id'],'PR-AUDIT-001'))
        operator=self.client.get('/api/audit-events?actor_id='+self.operator['id']).json()
        self.assertEqual([row['operation'] for row in operator['items']],['purchase-request'])
        searched=self.client.get('/api/audit-events?q=pr-audit-001').json()
        self.assertEqual({row['operation'].split(':')[0] for row in searched['items']},
                         {'purchase-request','purchase-request-decision'})
        first=self.client.get('/api/audit-events?limit=2').json()
        self.assertIsNotNone(first['next_before'])
        older=self.client.get('/api/audit-events?limit=2&before='+str(first['next_before'])).json()
        self.assertTrue(older['items'])
        self.assertLess(older['items'][0]['sequence'],first['items'][-1]['sequence'])

    def test_bulk_snapshot_is_summarized_and_secrets_are_redacted(self):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        payload={'started_at':(finished-timedelta(minutes=2)).isoformat(),
            'finished_at':finished.isoformat(),'snapshot_at':finished.isoformat(),
            'external_cursor':'audit-orders','reason':'Audit snapshot','orders':[{
                'external_order_id':'external-audit','external_order_reference':'EXT-AUDIT',
                'marketplace':'Marketplace Audit','status':'completed','ordered_at':finished.isoformat(),
                'lines':[{'external_id':'unknown','external_sku':'UNKNOWN','quantity':1,
                          'gross_revenue':'100000.00'}]}]}
        self.post('/api/integrations/jubelio/order-snapshots',payload,key='audit-snapshot')
        event=self.client.get('/api/audit-events?category=integration&q=audit-snapshot').json()['items'][0]
        self.assertEqual(event['changes']['orders'],{'record_count':1})
        self.assertNotIn('EXT-AUDIT',str(event['changes']))
        self.assertEqual(audit_value({'token':'secret','nested':{'client_secret':'secret',
            'access_token':'secret'}}),{'token':'[REDACTED]','nested':{
                'client_secret':'[REDACTED]','access_token':'[REDACTED]'}})
        self.assertEqual(audit_category('product-external-mapping:product-id'),'master_data')
        self.assertEqual(audit_category('finished-goods-stock-count:receipt-id'),'warehouse')

    def test_admin_only_detail_date_validation_immutability_backup_and_migration(self):
        event=self.client.get('/api/audit-events').json()['items'][0]
        self.assertEqual(self.client.get('/api/audit-events/'+event['id']).json(),event)
        for account in (self.operator,self.viewer):
            headers={'X-API-Key':account['api_key']}
            self.assertEqual(self.client.get('/api/audit-events',headers=headers).status_code,403)
            self.assertEqual(self.client.get('/api/audit-events/'+event['id'],headers=headers).status_code,403)
        self.assertEqual(self.client.get('/api/audit-events/missing').status_code,404)
        for query in ('start_date=2026-09-01','start_date=2026-09-02&end_date=2026-09-01',
                      'start_date=2025-01-01&end_date=2026-09-01'):
            self.assertEqual(self.client.get('/api/audit-events?'+query).status_code,422)
        with closing(sqlite3.connect(self.path)) as db:
            for sql in ('UPDATE audit_events SET operation=operation','DELETE FROM audit_events'):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
        backup=self.path.with_name('audit-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).audit_event(event['id'])['operation'],'product')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE audit_events');db.execute('PRAGMA user_version=44');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],53)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0],0)
