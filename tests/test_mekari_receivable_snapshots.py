import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class MekariReceivableSnapshotTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def record(self, **changes):
        record={'external_receivable_id':'receivable-42','reference':'INV-CUSTOMER-0042',
                'external_customer_id':'customer-7','customer_name':'Marketplace Corporate',
                'invoice_date':'2026-08-15','due_date':'2026-09-10','status':'open','currency':'IDR',
                'original_amount':'1000000','received_amount':'0','updated_at':'2026-09-13T11:00:00+07:00'}
        record.update(changes);return record

    def body(self, receivables=None, **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(minutes=2)).isoformat(),'finished_at':finished.isoformat(),
              'snapshot_at':finished.isoformat(),'as_of':'2026-09-13','external_cursor':'receivables-page-3',
              'reason':'Snapshot piutang usaha dari connector Mekari',
              'receivables':receivables if receivables is not None else [self.record()]}
        body.update(changes);return body

    def test_import_is_idempotent_and_summarizes_expected_receipts(self):
        partial=self.record(external_receivable_id='receivable-43',reference='INV-RESELLER-0043',
            external_customer_id='customer-8',customer_name='Marketplace Reseller',invoice_date='2026-09-01',
            due_date='2026-09-17',status='partially_paid',original_amount='500000',received_amount='200000')
        paid=self.record(external_receivable_id='receivable-44',reference='INV-PAID-0044',due_date='2026-09-05',
                         status='paid',original_amount='400000',received_amount='400000')
        void=self.record(external_receivable_id='receivable-45',reference='INV-VOID-0045',status='void')
        payload=self.body([self.record(),partial,paid,void])
        batch=self.post('/api/integrations/mekari/receivable-snapshots',payload,key='receivables-once')
        self.assertEqual(batch,self.post('/api/integrations/mekari/receivable-snapshots',payload,key='receivables-once'))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],batch['receivable_count']),
                         ('succeeded',4,4,4))
        run=self.client.get('/api/integration-sync-runs/'+batch['sync_run_id']).json()
        self.assertEqual((run['system'],run['scope'],run['status']),('mekari','receivables','succeeded'))
        report=self.client.get('/api/integrations/mekari/receivables-summary').json()
        self.assertEqual(report['summary'],{'accepted_receivables':4,'open':1,'partially_paid':1,'paid':1,'void':1,
            'total_original':'1900000.00','total_received':'600000.00','total_outstanding':'1300000.00',
            'overdue_count':1,'overdue_amount':'1000000.00','due_next_7_days_count':1,
            'due_next_7_days_amount':'300000.00'})
        self.assertTrue(report['receivables'][0]['overdue'])
        reseller=next(row for row in report['customers'] if row['external_customer_id']=='customer-8')
        self.assertEqual((reseller['outstanding_invoices'],reseller['outstanding_amount']),(1,'300000.00'))

    def test_exact_decimal_due_boundaries_and_health(self):
        records=[self.record(original_amount='100.01',due_date='2026-09-13'),
                 self.record(external_receivable_id='receivable-next-7',reference='NEXT-7',due_date='2026-09-20',
                             original_amount='50.25'),
                 self.record(external_receivable_id='receivable-next-8',reference='NEXT-8',due_date='2026-09-21',
                             original_amount='75.75')]
        batch=self.post('/api/integrations/mekari/receivable-snapshots',self.body(records))
        self.assertEqual([row['due_in_days'] for row in batch['receivables']],[0,7,8])
        report=self.client.get('/api/integrations/mekari/receivables-summary').json()
        self.assertEqual((report['summary']['due_next_7_days_count'],report['summary']['due_next_7_days_amount']),
                         (2,'150.26'))
        health=self.client.get('/api/integrations').json()['systems'][1]
        scope=next(item for item in health['scopes'] if item['scope']=='receivables')
        self.assertEqual((scope['health'],scope['latest_run']['records_written']),('healthy',3))

    def test_validation_roles_history_empty_and_missing(self):
        duplicate=self.record()
        cases=([duplicate,dict(duplicate)],
               [duplicate,self.record(external_receivable_id='other',reference='inv-customer-0042')],
               [self.record(invoice_date='2026-09-11',due_date='2026-09-10')],
               [self.record(status='overdue')],[self.record(currency='USD')],[self.record(original_amount='0')],
               [self.record(received_amount='1000001')],[self.record(status='open',received_amount='1')],
               [self.record(status='partially_paid',received_amount='0')],
               [self.record(status='paid',received_amount='999999')],
               [self.record(status='void',received_amount='1')],[self.record(updated_at='2026-09-13T11:00:00')],
               [self.record(unexpected='field')])
        for receivables in cases:
            self.post('/api/integrations/mekari/receivable-snapshots',self.body(receivables),status=422)
        for changes in ({'started_at':'2026-09-13T10:00:00'},
                        {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                        {'unexpected':'field'}):
            self.post('/api/integrations/mekari/receivable-snapshots',self.body(**changes),status=422)
        for account in (self.operator,self.viewer):
            self.post('/api/integrations/mekari/receivable-snapshots',self.body(),api_key=account['api_key'],status=403)
        batch=self.post('/api/integrations/mekari/receivable-snapshots',self.body(receivables=[]))
        listed=self.client.get('/api/integrations/mekari/receivable-snapshots').json()[0]
        self.assertEqual(listed['id'],batch['id']);self.assertNotIn('receivables',listed)
        self.assertEqual(self.client.get('/api/integrations/mekari/receivable-snapshots/'+batch['id']).status_code,200)
        self.assertEqual(self.client.get('/api/integrations/mekari/receivable-snapshots/missing').status_code,404)
        for account in (self.operator,self.viewer):
            response=self.client.get('/api/integrations/mekari/receivables-summary',
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200);self.assertEqual(response.json()['receivables'],[])

    def test_rollback_immutability_backup_and_migration_from_40(self):
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_receivable_snapshot BEFORE INSERT ON requests
                WHEN NEW.key='fail-receivable-snapshot' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integrations/mekari/receivable-snapshots',self.body(),key='fail-receivable-snapshot',status=409)
        self.assertEqual(self.client.get('/api/integrations/mekari/receivable-snapshots').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db: db.execute('DROP TRIGGER fail_receivable_snapshot')
        batch=self.post('/api/integrations/mekari/receivable-snapshots',self.body())
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('mekari_receivable_snapshot_batches','mekari_receivable_snapshot_records'):
                for action in (f'UPDATE {table} SET id=id',f'DELETE FROM {table}'):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(action)
        backup=self.path.with_name('mekari-receivable-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).mekari_receivable_snapshot(batch['id'])['receivables'][0]['outstanding_amount'],
                         '1000000.00')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE mekari_receivable_snapshot_records')
            db.execute('DROP TABLE mekari_receivable_snapshot_batches')
            db.execute('PRAGMA user_version=40');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],51)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM mekari_receivable_snapshot_batches').fetchone()[0],0)
