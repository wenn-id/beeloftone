import sqlite3
from contextlib import closing
from datetime import date, timedelta
from unittest import TestCase

from beeloft.store import Store, audit_category
import test_production


class WorkforceTest(TestCase):
    setUp=test_production.ProductionTest.setUp
    post=test_production.ProductionTest.post

    def employee(self,code='EMP-001',name='Ayu',department='Produksi',**options):
        return self.post('/api/workforce/employees',{'code':code,'name':name,
            'department':department,'reason':'Data awal karyawan'},**options)

    def attendance(self,employee,**changes):
        options={name:changes.pop(name) for name in ('key','status_code','api_key') if name in changes}
        if 'status_code' in options: options['status']=options.pop('status_code')
        body={'work_date':date.today().isoformat(),'expected_revision':0,'status':'present',
              'clock_in':'08:00','clock_out':'17:30','overtime_minutes':90,'notes':'Shift pagi',
              'reason':'Rekap harian'}
        body.update(changes)
        return self.post('/api/workforce/employees/'+employee['id']+'/attendance',body,**options)

    def test_employee_master_is_versioned_searchable_and_admin_only(self):
        employee=self.employee()
        self.assertEqual((employee['code'],employee['revision'],employee['active']),('EMP-001',1,True))
        self.assertEqual(self.employee('EMP-ONCE','Dewi','Produksi',key='employee-once'),
                         self.employee('EMP-ONCE','Dewi','Produksi',key='employee-once'))
        report=self.client.get('/api/workforce/employees?status=active&q=produksi').json()
        self.assertEqual(report['total'],2)
        changed=self.post('/api/workforce/employees/'+employee['id']+'/changes',{
            'expected_revision':1,'name':'Ayu Lestari','department':'Quality','active':True,
            'reason':'Pindah tim'})
        self.assertEqual((changed['revision'],changed['name'],changed['department']),
                         (2,'Ayu Lestari','Quality'))
        history=self.client.get('/api/workforce/employees/'+employee['id']+'/history').json()
        self.assertEqual([row['revision'] for row in history['items']],[2,1])
        first=self.client.get('/api/workforce/employees/'+employee['id']+'/history?limit=1').json()
        older=self.client.get('/api/workforce/employees/'+employee['id']+'/history?limit=1&before='+
                              str(first['next_before'])).json()
        self.assertEqual((first['items'][0]['revision'],older['items'][0]['revision'],
                          older['next_before']),(2,1,None))
        self.post('/api/workforce/employees/'+employee['id']+'/changes',{
            'expected_revision':1,'name':'Ayu','department':'Produksi','active':True,
            'reason':'Revisi basi'},status=409)
        self.post('/api/workforce/employees/'+employee['id']+'/changes',{
            'expected_revision':2,'name':'Ayu Lestari','department':'Quality','active':True,
            'reason':'Tidak berubah'},status=422)
        self.employee(code='OP-001',api_key=self.operator['api_key'],status=403)
        self.assertEqual(self.client.get('/api/workforce/employees/missing').status_code,404)

    def test_attendance_summary_correction_validation_and_roles(self):
        ayu=self.employee();bima=self.employee('EMP-002','Bima','Gudang')
        present=self.attendance(ayu,api_key=self.operator['api_key'])
        self.assertEqual((present['revision'],present['work_minutes'],present['overtime_minutes']),
                         (1,570,90))
        self.attendance(bima,status='leave',clock_in=None,clock_out=None,overtime_minutes=0,
                        notes='Cuti tahunan')
        report=self.client.get('/api/workforce/attendance?start_date='+date.today().isoformat()).json()
        self.assertEqual(report['summary'],{'records':2,'employees':2,'present':1,'leave':1,
            'absent':0,'work_minutes':570,'overtime_minutes':90})
        corrected=self.attendance(ayu,expected_revision=1,status='absent',clock_in=None,
            clock_out=None,overtime_minutes=0,notes='Sakit',reason='Koreksi supervisor')
        self.assertEqual((corrected['revision'],corrected['status'],corrected['work_minutes']),(2,'absent',0))
        history=self.client.get('/api/workforce/attendance/'+present['id']+'/history').json()
        self.assertEqual([(row['revision'],row['work_minutes']) for row in history['items']],[(2,0),(1,570)])
        self.attendance(ayu,expected_revision=1,status='absent',clock_in=None,clock_out=None,
                        overtime_minutes=0,notes='Sakit',status_code=409)
        self.attendance(ayu,expected_revision=2,status='absent',clock_in=None,clock_out=None,
                        overtime_minutes=0,notes='Sakit',status_code=422)
        invalid={'work_date':date.today().isoformat(),'expected_revision':0,'status':'present',
                 'clock_in':'17:00','clock_out':'08:00','overtime_minutes':0,
                 'notes':'','reason':'Jam terbalik'}
        self.post('/api/workforce/employees/'+bima['id']+'/attendance',invalid,status=422)
        self.attendance(bima,work_date=(date.today()+timedelta(days=1)).isoformat(),status_code=422)
        self.attendance(bima,work_date=(date.today()-timedelta(days=1)).isoformat(),
                        api_key=self.viewer['api_key'],status_code=403)
        self.assertEqual(self.client.get('/api/workforce/attendance?start_date=2026-01-02&end_date=2026-01-01').status_code,422)
        self.assertEqual(self.client.get('/api/workforce/attendance?employee_id=missing').status_code,404)

    def test_inactive_employee_history_audit_immutability_backup_and_migration(self):
        employee=self.employee();attendance=self.attendance(employee)
        self.post('/api/workforce/employees/'+employee['id']+'/changes',{
            'expected_revision':1,'name':'Ayu','department':'Produksi','active':False,
            'reason':'Kontrak selesai'})
        self.attendance(employee,work_date=(date.today()-timedelta(days=1)).isoformat(),status_code=422)
        corrected=self.attendance(employee,expected_revision=1,status='leave',clock_in=None,
            clock_out=None,overtime_minutes=0,notes='Cuti',reason='Koreksi setelah nonaktif')
        self.assertEqual(corrected['revision'],2)
        events=self.client.get('/api/audit-events?q=EMP-001').json()['items']
        self.assertTrue(any(row['category']=='master_data' and row['operation']=='workforce-employee'
                            for row in events))
        self.assertEqual(audit_category('workforce-attendance:employee:day'),'production')
        with closing(sqlite3.connect(self.path)) as db:
            for sql in ("UPDATE workforce_employee_events SET name=name",
                        "DELETE FROM workforce_attendance_events WHERE id='"+attendance['event_id']+"'"):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
        backup=self.path.with_name('workforce-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).employee(employee['id'])['active'],False)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('''DROP TABLE workforce_attendance_events;
                DROP TABLE workforce_attendance_records; DROP TABLE workforce_employee_events;
                DROP TABLE workforce_employees; PRAGMA user_version=49;''')
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],54)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
