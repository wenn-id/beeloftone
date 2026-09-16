import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production


class PayrollAccountingReconciliationTest(TestCase):
    setUp=test_production.ProductionTest.setUp
    post=test_production.ProductionTest.post

    def accounting(self,status='posted',**changes):
        row={'status':status,'journal_reference':'JV-PAYROLL-001',
             'posting_date':None if status=='draft' else '2026-09-30',
             'debit_total':'1150000.00','credit_total':'1150000.00',
             'updated_at':'2026-09-30T04:00:00+00:00'}
        row.update(changes);return row

    def period(self,external_id,month=9,status='reviewing',accounting=None,**changes):
        start=f'2026-{month:02d}-01';end=f'2026-{month:02d}-28'
        row={'external_payroll_id':external_id,'period_start':start,'period_end':end,
             'status':status,'currency':'IDR','employee_count':42,'gross_pay':'1000000.00',
             'employee_deductions':'100000.00','employer_contributions':'150000.00',
             'payment_date':end if status=='paid' else None,
             'updated_at':'2026-09-30T04:00:00+00:00','accounting':accounting}
        row.update(changes);return row

    def snapshot(self,periods,key=None,status=201):
        finished=datetime(2026,9,30,5,0,tzinfo=timezone.utc)
        return self.post('/api/integrations/mekari/payroll-snapshots',{
            'started_at':(finished-timedelta(seconds=5)).isoformat(),
            'finished_at':finished.isoformat(),'snapshot_at':finished.isoformat(),
            'external_cursor':'payroll-accounting','reason':'Snapshot payroll dan posting Mekari',
            'periods':periods},key=key,status=status)

    def approve(self,period):
        request=self.post('/api/integrations/mekari/payroll-periods/'+period['id']+'/approval-requests',
            {'reason':'Payroll siap diputuskan'},api_key=self.operator['api_key'])
        return self.post('/api/payroll-approval-requests/'+request['id']+'/decisions',
            {'status':'approved','expected_revision':request['revision'],'reason':'Payroll disetujui'})

    def report(self,query=''):
        response=self.client.get('/api/payroll-accounting-reconciliation'+query)
        self.assertEqual(response.status_code,200,response.text);return response.json()

    def test_snapshot_posting_is_idempotent_exact_and_visible(self):
        payload=[self.period('payroll-accounting-import',status='paid',
            accounting=self.accounting(debit_total='1150000.01',credit_total='1150000.02'))]
        batch=self.snapshot(payload,key='accounting-once')
        self.assertEqual(batch,self.snapshot(payload,key='accounting-once'))
        self.assertEqual((batch['period_count'],batch['posting_count']),(1,1))
        posting=batch['periods'][0]['accounting']
        self.assertEqual((posting['status'],posting['journal_reference'],posting['debit_total'],
                          posting['credit_total']),
                         ('posted','JV-PAYROLL-001','1150000.01','1150000.02'))
        stored=self.client.get('/api/integrations/mekari/payroll-snapshots/'+batch['id']).json()
        self.assertEqual(stored['periods'][0]['accounting'],posting)

    def test_reconciles_payment_and_posting_states(self):
        initial=[self.period('payroll-wait-payment',1),self.period('payroll-wait-posting',2),
            self.period('payroll-posted',3),self.period('payroll-reversed',4),
            self.period('payroll-unbalanced',5),self.period('payroll-wrong-amount',6)]
        sources=self.snapshot(initial)['periods']
        for source in sources:self.approve(source)
        latest=[
            self.period('payroll-wait-payment',1,accounting=self.accounting('draft',journal_reference='JV-DRAFT')),
            self.period('payroll-wait-posting',2,'paid'),
            self.period('payroll-posted',3,'paid',self.accounting(journal_reference='JV-POSTED',posting_date='2026-03-28')),
            self.period('payroll-reversed',4,'paid',self.accounting('reversed',journal_reference='JV-REVERSED',posting_date='2026-04-28')),
            self.period('payroll-unbalanced',5,'paid',self.accounting(journal_reference='JV-UNBALANCED',
                posting_date='2026-05-28',credit_total='1149999.00')),
            self.period('payroll-wrong-amount',6,'paid',self.accounting(journal_reference='JV-WRONG',
                posting_date='2026-06-28',debit_total='1200000',credit_total='1200000'))]
        self.snapshot(latest)
        report=self.report()
        self.assertEqual(report['summary'],{'approved_batches':6,'waiting_payment':1,
            'awaiting_posting':1,'posted':1,'exceptions':3,'expected_employer_cost':'6900000.00',
            'posted_employer_cost':'1150000.00'})
        states={row['external_payroll_id']:row['workflow_status'] for row in report['items']}
        self.assertEqual(states['payroll-wait-payment'],'waiting_payment')
        self.assertEqual(states['payroll-wait-posting'],'awaiting_posting')
        self.assertEqual(states['payroll-posted'],'posted')
        reasons={row['external_payroll_id']:row['exception_reason'] for row in report['items']}
        self.assertEqual(reasons['payroll-reversed'],'posting_reversed')
        self.assertEqual(reasons['payroll-unbalanced'],'posting_unbalanced')
        self.assertEqual(reasons['payroll-wrong-amount'],'posting_amount_mismatch')
        filtered=self.report('?status=exception&q=JV-&limit=2&offset=1')
        self.assertEqual((filtered['total'],len(filtered['items'])),(3,2))
        self.assertEqual(self.report('?q=JV-POSTED')['items'][0]['posting_date'],'2026-03-28')
        viewer=self.client.get('/api/payroll-accounting-reconciliation',
            headers={'X-API-Key':self.viewer['api_key']})
        self.assertEqual(viewer.status_code,200)

    def test_validation_immutability_backup_and_migration(self):
        cases=[
            self.period('bad-draft-date',accounting=self.accounting('draft',posting_date='2026-09-30')),
            self.period('bad-posted-date',accounting=self.accounting(posting_date=None)),
            self.period('bad-zero',accounting=self.accounting(debit_total='0')),
            self.period('bad-timezone',accounting=self.accounting(updated_at='2026-09-30T04:00:00')),
            self.period('bad-early',accounting=self.accounting(posting_date='2026-08-31')),
            self.period('bad-field',accounting=self.accounting(unexpected='field'))]
        for period in cases:self.snapshot([period],status=422)

        batch=self.snapshot([self.period('payroll-backup',status='paid',accounting=self.accounting())])
        with closing(sqlite3.connect(self.path)) as db:
            for sql in ('UPDATE mekari_payroll_snapshot_postings SET status=status',
                        'DELETE FROM mekari_payroll_snapshot_postings'):
                with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)
        backup=self.path.with_name('payroll-accounting-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).mekari_payroll_snapshot(batch['id'])['posting_count'],1)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE mekari_payroll_snapshot_postings')
            db.execute('PRAGMA user_version=52');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],54)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_invalid_query_parameters(self):
        self.assertEqual(self.client.get('/api/payroll-accounting-reconciliation?status=bad').status_code,422)
        self.assertEqual(self.client.get('/api/payroll-accounting-reconciliation?limit=0').status_code,422)
        self.assertEqual(self.client.get('/api/payroll-accounting-reconciliation?q='+'x'*161).status_code,422)
