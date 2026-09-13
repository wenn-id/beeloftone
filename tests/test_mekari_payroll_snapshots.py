import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class MekariPayrollSnapshotTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def period(self, **changes):
        period={'external_payroll_id':'payroll-2026-08','period_start':'2026-08-01','period_end':'2026-08-31',
                'status':'approved','currency':'IDR','employee_count':42,'gross_pay':'1000000',
                'employee_deductions':'100000','employer_contributions':'150000','payment_date':None,
                'updated_at':'2026-09-13T11:00:00+07:00'}
        period.update(changes);return period

    def body(self, periods=None, **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(minutes=2)).isoformat(),'finished_at':finished.isoformat(),
              'snapshot_at':finished.isoformat(),'external_cursor':'payroll-page-2',
              'reason':'Snapshot ringkasan payroll dari connector Mekari',
              'periods':periods if periods is not None else [self.period()]}
        body.update(changes);return body

    def test_import_is_idempotent_and_summary_uses_latest_period(self):
        september=self.period(external_payroll_id='payroll-2026-09',period_start='2026-09-01',
            period_end='2026-09-30',status='paid',employee_count=45,gross_pay='2000000',
            employee_deductions='200000',employer_contributions='300000',payment_date='2026-09-30')
        payload=self.body([self.period(),september])
        batch=self.post('/api/integrations/mekari/payroll-snapshots',payload,key='payroll-once')
        self.assertEqual(batch,self.post('/api/integrations/mekari/payroll-snapshots',payload,key='payroll-once'))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],batch['period_count']),
                         ('succeeded',2,2,2))
        run=self.client.get('/api/integration-sync-runs/'+batch['sync_run_id']).json()
        self.assertEqual((run['system'],run['scope'],run['status']),('mekari','payroll','succeeded'))
        report=self.client.get('/api/integrations/mekari/payroll-summary').json()
        self.assertEqual(report['current']['external_payroll_id'],'payroll-2026-09')
        self.assertEqual({key:report['current'][key] for key in ('net_pay','total_employer_cost')},
                         {'net_pay':'1800000.00','total_employer_cost':'2300000.00'})
        self.assertEqual(report['status_counts'],
                         {'draft':0,'reviewing':0,'approved':1,'paid':1,'cancelled':0})
        self.assertEqual([row['external_payroll_id'] for row in report['periods']],
                         ['payroll-2026-09','payroll-2026-08'])

    def test_exact_decimal_payment_status_and_health(self):
        period=self.period(status='paid',gross_pay='100.01',employee_deductions='20.02',
            employer_contributions='5.03',payment_date='2026-09-01')
        batch=self.post('/api/integrations/mekari/payroll-snapshots',self.body([period]))
        row=batch['periods'][0]
        self.assertEqual((row['net_pay'],row['total_employer_cost'],row['payment_date']),
                         ('79.99','105.04','2026-09-01'))
        health=self.client.get('/api/integrations').json()['systems'][1]
        scope=next(item for item in health['scopes'] if item['scope']=='payroll')
        self.assertEqual((scope['health'],scope['latest_run']['records_written']),('healthy',1))

    def test_validation_roles_history_empty_and_missing(self):
        duplicate=self.period()
        cases=([duplicate,dict(duplicate)],
               [duplicate,self.period(external_payroll_id='other')],
               [self.period(period_start='2026-09-01',period_end='2026-08-31')],
               [self.period(employee_deductions='1000001')],[self.period(gross_pay='1000000000000000.01')],
               [self.period(currency='USD')],[self.period(status='processed')],
               [self.period(status='paid')],[self.period(payment_date='2026-09-01')],
               [self.period(status='paid',payment_date='2026-07-31')],
               [self.period(updated_at='2026-09-13T11:00:00')],[self.period(unexpected='field')])
        for periods in cases:
            self.post('/api/integrations/mekari/payroll-snapshots',self.body(periods),status=422)
        for changes in ({'started_at':'2026-09-13T10:00:00'},
                        {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                        {'unexpected':'field'}):
            self.post('/api/integrations/mekari/payroll-snapshots',self.body(**changes),status=422)
        for account in (self.operator,self.viewer):
            self.post('/api/integrations/mekari/payroll-snapshots',self.body(),
                      api_key=account['api_key'],status=403)
        batch=self.post('/api/integrations/mekari/payroll-snapshots',self.body(periods=[]))
        listed=self.client.get('/api/integrations/mekari/payroll-snapshots').json()[0]
        self.assertEqual(listed['id'],batch['id']);self.assertNotIn('periods',listed)
        self.assertEqual(self.client.get('/api/integrations/mekari/payroll-snapshots/'+batch['id']).status_code,200)
        self.assertEqual(self.client.get('/api/integrations/mekari/payroll-snapshots/missing').status_code,404)
        for account in (self.operator,self.viewer):
            response=self.client.get('/api/integrations/mekari/payroll-summary',
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200);self.assertIsNone(response.json()['current'])

    def test_rollback_immutability_backup_and_migration_from_41(self):
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_payroll_snapshot BEFORE INSERT ON requests
                WHEN NEW.key='fail-payroll-snapshot' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integrations/mekari/payroll-snapshots',self.body(),key='fail-payroll-snapshot',status=409)
        self.assertEqual(self.client.get('/api/integrations/mekari/payroll-snapshots').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db: db.execute('DROP TRIGGER fail_payroll_snapshot')
        batch=self.post('/api/integrations/mekari/payroll-snapshots',self.body())
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('mekari_payroll_snapshot_batches','mekari_payroll_snapshot_periods'):
                for action in (f'UPDATE {table} SET id=id',f'DELETE FROM {table}'):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(action)
        backup=self.path.with_name('mekari-payroll-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).mekari_payroll_snapshot(batch['id'])['periods'][0]['net_pay'],'900000.00')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE mekari_payroll_snapshot_periods')
            db.execute('DROP TABLE mekari_payroll_snapshot_batches')
            db.execute('PRAGMA user_version=41');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],44)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM mekari_payroll_snapshot_batches').fetchone()[0],0)
