import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production


class PayrollApprovalsTest(TestCase):
    setUp=test_production.ProductionTest.setUp
    post=test_production.ProductionTest.post

    def period(self,external_id='payroll-approval-2026-09',**changes):
        row={'external_payroll_id':external_id,'period_start':'2026-09-01','period_end':'2026-09-30',
             'status':'reviewing','currency':'IDR','employee_count':42,'gross_pay':'1000000.00',
             'employee_deductions':'100000.00','employer_contributions':'150000.00',
             'payment_date':None,'updated_at':'2026-09-15T04:00:00+00:00'}
        row.update(changes);return row

    def snapshot(self,periods,**options):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(seconds=5)).isoformat(),
              'finished_at':finished.isoformat(),'snapshot_at':finished.isoformat(),
              'external_cursor':'payroll-approval-cursor','reason':'Snapshot untuk approval payroll',
              'periods':periods}
        return self.post('/api/integrations/mekari/payroll-snapshots',body,
                         key=options.pop('key',None),**options)

    def request(self,period,**options):
        body={'reason':'Payroll sudah direview HR dan siap diputuskan'}
        body.update(options.pop('changes',{}))
        return self.post('/api/integrations/mekari/payroll-periods/'+period['id']+'/approval-requests',body,
                         api_key=options.pop('api_key',self.operator['api_key']),**options)

    def decide(self,request,decision='approved',**options):
        body={'status':decision,'expected_revision':request['revision'],
              'reason':'Keputusan manajemen atas batch payroll'}
        body.update(options.pop('changes',{}))
        return self.post('/api/payroll-approval-requests/'+request['id']+'/decisions',body,
                         api_key=options.pop('api_key',self.admin['api_key']),**options)

    def test_submit_idempotent_list_and_unified_inbox(self):
        period=self.snapshot([self.period()],key='snapshot-payroll')['periods'][0]
        request=self.request(period,key='payroll-approval-once')
        self.assertEqual(request,self.request(period,key='payroll-approval-once'))
        self.assertTrue(request['reference'].startswith('PAY-'))
        self.assertEqual((request['status'],request['stale'],request['source']['net_pay'],
                          request['source']['total_employer_cost']),
                         ('submitted',False,'900000.00','1150000.00'))
        listed=self.client.get('/api/payroll-approval-requests?status=submitted').json()
        self.assertEqual(listed[0]['id'],request['id'])
        queue=self.client.get('/api/approvals?kind=payroll_batch').json()[0]
        self.assertEqual((queue['id'],queue['department'],queue['amount'],
                          queue['context']['employee_count']),
                         (request['id'],'People · Finance','1150000.00',42))
        self.request(period,status=409)
        self.request(period,api_key=self.viewer['api_key'],status=403)

    def test_decisions_roles_and_source_status_stays_immutable(self):
        period=self.snapshot([self.period('payroll-cancel')])['periods'][0]
        request=self.request(period)
        other=self.app.state.store.provision_user('Operator payroll lain','operator')
        self.decide(request,api_key=self.operator['api_key'],status=403)
        self.decide(request,'cancelled',status=403)
        self.decide(request,'cancelled',api_key=other['api_key'],status=403)
        cancelled=self.decide(request,'cancelled',api_key=self.operator['api_key'],key='cancel-payroll')
        self.assertEqual(cancelled,self.decide(request,'cancelled',api_key=self.operator['api_key'],key='cancel-payroll'))

        approved_period=self.snapshot([self.period('payroll-approved')])['periods'][0]
        approved=self.decide(self.request(approved_period),key='approve-payroll')
        self.assertEqual(approved['status'],'approved')
        source=self.client.get('/api/integrations/mekari/payroll-summary').json()['current']
        self.assertEqual((source['status'],source['approval_request']['status']),('reviewing','approved'))
        self.decide(approved,status=409)
        for changes in ({'status':'submitted'},{'expected_revision':0},
                        {'expected_revision':True},{'reason':' '}):
            self.decide(approved,changes=changes,status=422)

    def test_new_snapshot_marks_request_stale_and_blocks_approval(self):
        original=self.snapshot([self.period('payroll-stale')])['periods'][0]
        request=self.request(original)
        latest=self.snapshot([self.period('payroll-stale',gross_pay='1200000.00',
            updated_at='2026-09-15T05:00:00+00:00')])['periods'][0]
        stale=self.client.get('/api/payroll-approval-requests/'+request['id']).json()
        self.assertTrue(stale['stale']);self.assertEqual(stale['current_source_period_id'],latest['id'])
        self.decide(stale,status=409)
        rejected=self.decide(stale,'rejected')
        self.assertEqual(rejected['status'],'rejected')
        self.request(original,status=409)
        replacement=self.request(latest)
        self.assertFalse(replacement['stale'])
        self.snapshot([self.period('payroll-other')])
        self.assertTrue(self.client.get('/api/payroll-approval-requests/'+replacement['id']).json()['stale'])

    def test_source_validation_audit_immutability_backup_and_migration(self):
        for source_status in ('draft','approved','paid','cancelled'):
            changes={'status':source_status}
            if source_status=='paid':changes['payment_date']='2026-09-30'
            period=self.snapshot([self.period('payroll-'+source_status,**changes)])['periods'][0]
            self.request(period,status=409)
        self.post('/api/integrations/mekari/payroll-periods/missing/approval-requests',
                  {'reason':'Tidak ada'},api_key=self.operator['api_key'],status=404)
        latest=self.snapshot([self.period('payroll-audit')])['periods'][0]
        for changes in ({'reason':' '},{'extra':'bad'}):self.request(latest,changes=changes,status=422)
        request=self.request(latest);approved=self.decide(request)
        audit=self.client.get('/api/audit-events?category=approval&q='+request['reference']).json()['items']
        self.assertTrue(any(row['operation']=='payroll-approval-decision:'+request['id'] for row in audit))
        pending_period=self.snapshot([self.period('payroll-trigger')])['periods'][0]
        pending=self.request(pending_period)
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('payroll_approval_requests','payroll_approval_request_events'):
                for sql in ('UPDATE '+table+' SET reason=reason','DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO payroll_approval_request_events
                    (request_id,status,reason,actor_id,created_at) VALUES(?,'cancelled','Tidak sah',?,'2026-09-15')''',
                    (pending['id'],self.admin['id']))
        expected=self.app.state.store.payroll_approval_request(request['id'])
        self.assertTrue(expected['stale'])
        backup=self.path.with_name('payroll-approval-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).payroll_approval_request(request['id']),expected)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('''DROP TABLE payroll_approval_request_events;
                DROP TABLE payroll_approval_requests; PRAGMA user_version=51;''')
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],53)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
