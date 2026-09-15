import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class MekariPayableSnapshotTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def record(self, **changes):
        record={'external_payable_id':'payable-42','reference':'INV-KAIN-0042',
                'external_supplier_id':'supplier-7','supplier_name':'PT Kain Nusantara',
                'invoice_date':'2026-08-15','due_date':'2026-09-10','status':'open','currency':'IDR',
                'original_amount':'1000000','paid_amount':'0','updated_at':'2026-09-13T11:00:00+07:00'}
        record.update(changes);return record

    def body(self, payables=None, **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(minutes=2)).isoformat(),'finished_at':finished.isoformat(),
              'snapshot_at':finished.isoformat(),'as_of':'2026-09-13','external_cursor':'payables-page-3',
              'reason':'Snapshot utang usaha dari connector Mekari',
              'payables':payables if payables is not None else [self.record()]}
        body.update(changes);return body

    def test_import_is_idempotent_and_summarizes_due_obligations(self):
        partial=self.record(external_payable_id='payable-43',reference='INV-ZIPPER-0043',
            external_supplier_id='supplier-8',supplier_name='CV Zipper Jaya',invoice_date='2026-09-01',
            due_date='2026-09-17',status='partially_paid',original_amount='500000',paid_amount='200000')
        paid=self.record(external_payable_id='payable-44',reference='INV-PAID-0044',due_date='2026-09-05',
                         status='paid',original_amount='400000',paid_amount='400000')
        void=self.record(external_payable_id='payable-45',reference='INV-VOID-0045',status='void')
        payload=self.body([self.record(),partial,paid,void])
        batch=self.post('/api/integrations/mekari/payable-snapshots',payload,key='payables-once')
        self.assertEqual(batch,self.post('/api/integrations/mekari/payable-snapshots',payload,key='payables-once'))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],batch['payable_count']),
                         ('succeeded',4,4,4))
        run=self.client.get('/api/integration-sync-runs/'+batch['sync_run_id']).json()
        self.assertEqual((run['system'],run['scope'],run['status']),('mekari','payables','succeeded'))
        report=self.client.get('/api/integrations/mekari/payables-summary').json()
        self.assertEqual(report['summary'],{'accepted_payables':4,'open':1,'partially_paid':1,'paid':1,'void':1,
            'total_original':'1900000.00','total_paid':'600000.00','total_outstanding':'1300000.00',
            'overdue_count':1,'overdue_amount':'1000000.00','due_next_7_days_count':1,
            'due_next_7_days_amount':'300000.00'})
        self.assertTrue(report['payables'][0]['overdue'])
        zipper=next(row for row in report['suppliers'] if row['external_supplier_id']=='supplier-8')
        self.assertEqual((zipper['outstanding_invoices'],zipper['outstanding_amount']), (1,'300000.00'))

    def test_exact_decimal_due_boundaries_and_health(self):
        records=[self.record(original_amount='100.01',due_date='2026-09-13'),
                 self.record(external_payable_id='payable-next-7',reference='NEXT-7',due_date='2026-09-20',
                             original_amount='50.25'),
                 self.record(external_payable_id='payable-next-8',reference='NEXT-8',due_date='2026-09-21',
                             original_amount='75.75')]
        batch=self.post('/api/integrations/mekari/payable-snapshots',self.body(records))
        self.assertEqual([row['due_in_days'] for row in batch['payables']],[0,7,8])
        report=self.client.get('/api/integrations/mekari/payables-summary').json()
        self.assertEqual((report['summary']['due_next_7_days_count'],report['summary']['due_next_7_days_amount']),
                         (2,'150.26'))
        health=self.client.get('/api/integrations').json()['systems'][1]
        scope=next(item for item in health['scopes'] if item['scope']=='payables')
        self.assertEqual((scope['health'],scope['latest_run']['records_written']),('healthy',3))

    def test_validation_roles_history_empty_and_missing(self):
        duplicate=self.record()
        cases=([duplicate,dict(duplicate)],
               [duplicate,self.record(external_payable_id='other',reference='inv-kain-0042')],
               [self.record(invoice_date='2026-09-11',due_date='2026-09-10')],
               [self.record(status='overdue')],[self.record(currency='USD')],[self.record(original_amount='0')],
               [self.record(paid_amount='1000001')],[self.record(status='open',paid_amount='1')],
               [self.record(status='partially_paid',paid_amount='0')],
               [self.record(status='paid',paid_amount='999999')],
               [self.record(status='void',paid_amount='1')],[self.record(updated_at='2026-09-13T11:00:00')],
               [self.record(unexpected='field')])
        for payables in cases:
            self.post('/api/integrations/mekari/payable-snapshots',self.body(payables),status=422)
        for changes in ({'started_at':'2026-09-13T10:00:00'},
                        {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                        {'unexpected':'field'}):
            self.post('/api/integrations/mekari/payable-snapshots',self.body(**changes),status=422)
        for account in (self.operator,self.viewer):
            self.post('/api/integrations/mekari/payable-snapshots',self.body(),api_key=account['api_key'],status=403)
        batch=self.post('/api/integrations/mekari/payable-snapshots',self.body(payables=[]))
        listed=self.client.get('/api/integrations/mekari/payable-snapshots').json()[0]
        self.assertEqual(listed['id'],batch['id']);self.assertNotIn('payables',listed)
        self.assertEqual(self.client.get('/api/integrations/mekari/payable-snapshots/'+batch['id']).status_code,200)
        self.assertEqual(self.client.get('/api/integrations/mekari/payable-snapshots/missing').status_code,404)
        for account in (self.operator,self.viewer):
            response=self.client.get('/api/integrations/mekari/payables-summary',
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200);self.assertEqual(response.json()['payables'],[])

    def test_rollback_immutability_backup_and_migration_from_39(self):
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_payable_snapshot BEFORE INSERT ON requests
                WHEN NEW.key='fail-payable-snapshot' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integrations/mekari/payable-snapshots',self.body(),key='fail-payable-snapshot',status=409)
        self.assertEqual(self.client.get('/api/integrations/mekari/payable-snapshots').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db: db.execute('DROP TRIGGER fail_payable_snapshot')
        batch=self.post('/api/integrations/mekari/payable-snapshots',self.body())
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('mekari_payable_snapshot_batches','mekari_payable_snapshot_records'):
                for action in (f'UPDATE {table} SET id=id',f'DELETE FROM {table}'):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(action)
        backup=self.path.with_name('mekari-payable-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).mekari_payable_snapshot(batch['id'])['payables'][0]['outstanding_amount'],
                         '1000000.00')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE mekari_payable_snapshot_records')
            db.execute('DROP TABLE mekari_payable_snapshot_batches')
            db.execute('PRAGMA user_version=39');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],51)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM mekari_payable_snapshot_batches').fetchone()[0],0)
