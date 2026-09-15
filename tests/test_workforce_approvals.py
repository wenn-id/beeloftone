import sqlite3
from contextlib import closing
from datetime import date, timedelta
from unittest import TestCase

from beeloft.store import Store
import test_production


class WorkforceApprovalsTest(TestCase):
    setUp=test_production.ProductionTest.setUp
    post=test_production.ProductionTest.post

    def employee(self,code='PPL-APP-001',name='Ayu',department='Produksi'):
        return self.post('/api/workforce/employees',{'code':code,'name':name,
            'department':department,'reason':'Data awal approval People'})

    def request(self,employee,kind='leave',start=None,end=None,minutes=0,**options):
        start=start or (date.today()+timedelta(days=1)).isoformat()
        end=end or start
        payload={'employee_id':employee['id'],'kind':kind,'start_date':start,
                 'end_date':end,'overtime_minutes':minutes,'reason':'Kebutuhan operasional People'}
        payload.update(options.pop('changes',{}))
        return self.post('/api/workforce/requests',payload,
                         api_key=options.pop('api_key',self.operator['api_key']),**options)

    def decide(self,request,decision='approved',**options):
        payload={'status':decision,'expected_revision':request['revision'],
                 'reason':'Keputusan manajemen People'}
        payload.update(options.pop('changes',{}))
        return self.post('/api/workforce/requests/'+request['id']+'/decisions',payload,
                         api_key=options.pop('api_key',self.admin['api_key']),**options)

    def test_create_validate_filter_and_prevent_overlapping_pending_request(self):
        employee=self.employee()
        start=(date.today()+timedelta(days=2)).isoformat()
        end=(date.today()+timedelta(days=4)).isoformat()
        leave=self.request(employee,start=start,end=end,key='leave-once')
        self.assertEqual(leave,self.request(employee,start=start,end=end,key='leave-once'))
        self.assertTrue(leave['reference'].startswith('CUTI-'))
        self.assertEqual((leave['kind'],leave['days'],leave['status'],leave['employee_name']),
                         ('leave',3,'submitted','Ayu'))
        self.request(employee,start=end,end=end,status=409)
        overtime_day=(date.today()+timedelta(days=6)).isoformat()
        overtime=self.request(employee,'overtime',start=overtime_day,end=overtime_day,minutes=90)
        self.assertTrue(overtime['reference'].startswith('LBR-'))
        report=self.client.get('/api/workforce/requests?status=submitted&q=produksi').json()
        self.assertEqual((report['total'],report['summary']['leave'],
                          report['summary']['overtime']),(2,1,1))
        self.assertEqual(self.client.get('/api/workforce/requests?kind=overtime').json()
                         ['items'][0]['overtime_minutes'],90)
        for changes in ({'kind':'bad'},{'start_date':'bad'},
                        {'start_date':end,'end_date':start},
                        {'kind':'leave','overtime_minutes':1},
                        {'kind':'overtime','overtime_minutes':0},
                        {'kind':'overtime','start_date':start,'end_date':end,'overtime_minutes':60},
                        {'end_date':(date.today()+timedelta(days=368)).isoformat()},
                        {'reason':' '},{'extra':'bad'}):
            self.request(employee,changes=changes,status=422)
        self.request(employee,api_key=self.viewer['api_key'],status=403)

    def test_roles_decisions_unified_inbox_and_attendance_remain_separate(self):
        employee=self.employee();other=self.app.state.store.provision_user('Operator lain','operator')
        leave=self.request(employee)
        queue=self.client.get('/api/approvals?kind=workforce_leave').json()
        self.assertEqual((queue[0]['id'],queue[0]['department'],queue[0]['context']['days']),
                         (leave['id'],'People',1))
        self.decide(leave,api_key=self.operator['api_key'],status=403)
        self.decide(leave,'cancelled',status=403)
        self.decide(leave,'cancelled',api_key=other['api_key'],status=403)
        cancelled=self.decide(leave,'cancelled',api_key=self.operator['api_key'],key='cancel-once')
        self.assertEqual(cancelled,self.decide(leave,'cancelled',api_key=self.operator['api_key'],key='cancel-once'))
        self.assertEqual(cancelled['status'],'cancelled')

        approved=self.decide(self.request(employee,start=(date.today()+timedelta(days=3)).isoformat()),
                             key='approve-once')
        self.assertEqual(approved['status'],'approved')
        self.assertEqual(self.client.get('/api/workforce/attendance?employee_id='+employee['id']).json()['total'],0)
        self.assertEqual(self.client.get('/api/approvals?status=approved&kind=workforce_leave').json()[0]['id'],
                         approved['id'])
        self.request(employee,start=approved['start_date'],status=409)
        self.decide(approved,status=409)
        rejected=self.decide(self.request(employee,'overtime',
            start=(date.today()+timedelta(days=5)).isoformat(),minutes=60),'rejected')
        self.assertEqual(rejected['status'],'rejected')
        for changes in ({'status':'submitted'},{'expected_revision':0},
                        {'expected_revision':True},{'reason':' '}):
            self.decide(rejected,changes=changes,status=422)

    def test_inactive_employee_audit_immutability_backup_and_migration(self):
        employee=self.employee();request=self.request(employee)
        self.post('/api/workforce/employees/'+employee['id']+'/changes',{
            'expected_revision':1,'name':'Ayu','department':'Produksi','active':False,
            'reason':'Kontrak selesai'})
        self.request(employee,start=(date.today()+timedelta(days=10)).isoformat(),status=422)
        approved=self.decide(request)
        self.assertFalse(approved['employee_active'])
        audit=self.client.get('/api/audit-events?category=approval&q='+request['reference']).json()['items']
        self.assertTrue(any(row['operation']=='workforce-request-decision:'+request['id'] for row in audit))
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('workforce_requests','workforce_request_events'):
                for sql in ('UPDATE '+table+' SET reason=reason','DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO workforce_request_events(request_id,status,reason,actor_id,created_at)
                    VALUES(?,'approved','Ulang',?,'2026-09-15')''',(request['id'],self.admin['id']))
        backup=self.path.with_name('workforce-approval-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).workforce_request(request['id']),approved)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('''DROP TABLE workforce_request_events; DROP TABLE workforce_requests;
                PRAGMA user_version=50;''')
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],52)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
