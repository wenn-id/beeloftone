import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class MekariFinanceSnapshotTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def period(self, **changes):
        period={'source_report_id':'profit-loss-2026-08','period_start':'2026-08-01','period_end':'2026-08-31',
                'currency':'IDR','gross_revenue':'1000000','sales_returns':'100000',
                'cost_of_goods_sold':'400000','operating_expenses':'300000','other_income':'50000',
                'other_expenses':'25000','cash_balance':'500000','receivables_balance':'200000',
                'payables_balance':'150000'}
        period.update(changes);return period

    def body(self, periods=None, **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(minutes=2)).isoformat(),'finished_at':finished.isoformat(),
              'snapshot_at':finished.isoformat(),'external_cursor':'finance-page-4',
              'reason':'Snapshot ringkasan keuangan dari connector Mekari',
              'periods':periods if periods is not None else [self.period()]}
        body.update(changes);return body

    def test_import_is_idempotent_and_summary_uses_latest_period(self):
        september=self.period(source_report_id='profit-loss-2026-09',period_start='2026-09-01',
            period_end='2026-09-30',gross_revenue='2000000',sales_returns='200000',
            cost_of_goods_sold='800000',operating_expenses='500000',other_income='100000',
            other_expenses='50000',cash_balance='900000',receivables_balance='300000',
            payables_balance='250000')
        payload=self.body([self.period(),september])
        batch=self.post('/api/integrations/mekari/finance-snapshots',payload,key='finance-once')
        self.assertEqual(batch,self.post('/api/integrations/mekari/finance-snapshots',payload,key='finance-once'))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],batch['period_count']),
                         ('succeeded',2,2,2))
        run=self.client.get('/api/integration-sync-runs/'+batch['sync_run_id']).json()
        self.assertEqual((run['system'],run['scope'],run['status']),('mekari','finance_summary','succeeded'))
        report=self.client.get('/api/integrations/mekari/finance-summary').json()
        self.assertEqual(report['current']['source_report_id'],'profit-loss-2026-09')
        self.assertEqual({key:report['current'][key] for key in ('net_revenue','gross_profit','net_profit','net_liquidity')},
                         {'net_revenue':'1800000.00','gross_profit':'1000000.00',
                          'net_profit':'550000.00','net_liquidity':'950000.00'})
        self.assertEqual([row['source_report_id'] for row in report['periods']],
                         ['profit-loss-2026-09','profit-loss-2026-08'])

    def test_exact_decimal_negative_result_and_health(self):
        period=self.period(gross_revenue='100.01',sales_returns='0.01',cost_of_goods_sold='80.00',
            operating_expenses='30.00',other_income='1.25',other_expenses='2.25',cash_balance='10.00',
            receivables_balance='5.00',payables_balance='20.00')
        batch=self.post('/api/integrations/mekari/finance-snapshots',self.body([period]))
        row=batch['periods'][0]
        self.assertEqual((row['net_revenue'],row['gross_profit'],row['net_profit'],row['net_liquidity']),
                         ('100.00','20.00','-11.00','-5.00'))
        health=self.client.get('/api/integrations').json()['systems'][1]
        scope=next(item for item in health['scopes'] if item['scope']=='finance_summary')
        self.assertEqual((scope['health'],scope['latest_run']['records_written']),('healthy',1))

    def test_validation_roles_history_empty_and_missing(self):
        duplicate=self.period()
        cases=([duplicate,dict(duplicate)],
               [duplicate,self.period(source_report_id='other')],
               [self.period(period_start='2026-09-01',period_end='2026-08-31')],
               [self.period(sales_returns='1000001')],[self.period(gross_revenue='1000000000000000.01')],
               [self.period(currency='USD')],[self.period(unexpected='field')])
        for periods in cases:
            self.post('/api/integrations/mekari/finance-snapshots',self.body(periods),status=422)
        for changes in ({'started_at':'2026-09-13T10:00:00'},
                        {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                        {'unexpected':'field'}):
            self.post('/api/integrations/mekari/finance-snapshots',self.body(**changes),status=422)
        for account in (self.operator,self.viewer):
            self.post('/api/integrations/mekari/finance-snapshots',self.body(),
                      api_key=account['api_key'],status=403)
        batch=self.post('/api/integrations/mekari/finance-snapshots',self.body(periods=[]))
        listed=self.client.get('/api/integrations/mekari/finance-snapshots').json()[0]
        self.assertEqual(listed['id'],batch['id']);self.assertNotIn('periods',listed)
        self.assertEqual(self.client.get('/api/integrations/mekari/finance-snapshots/'+batch['id']).status_code,200)
        self.assertEqual(self.client.get('/api/integrations/mekari/finance-snapshots/missing').status_code,404)
        for account in (self.operator,self.viewer):
            response=self.client.get('/api/integrations/mekari/finance-summary',
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200);self.assertIsNone(response.json()['current'])

    def test_rollback_immutability_backup_and_migration_from_38(self):
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_finance_snapshot BEFORE INSERT ON requests
                WHEN NEW.key='fail-finance-snapshot' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integrations/mekari/finance-snapshots',self.body(),key='fail-finance-snapshot',status=409)
        self.assertEqual(self.client.get('/api/integrations/mekari/finance-snapshots').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db: db.execute('DROP TRIGGER fail_finance_snapshot')
        batch=self.post('/api/integrations/mekari/finance-snapshots',self.body())
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('mekari_finance_snapshot_batches','mekari_finance_snapshot_periods'):
                for action in (f'UPDATE {table} SET id=id',f'DELETE FROM {table}'):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(action)
        backup=self.path.with_name('mekari-finance-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).mekari_finance_snapshot(batch['id'])['periods'][0]['net_profit'],'225000.00')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE mekari_finance_snapshot_periods')
            db.execute('DROP TABLE mekari_finance_snapshot_batches')
            db.execute('PRAGMA user_version=38');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],48)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM mekari_finance_snapshot_batches').fetchone()[0],0)
