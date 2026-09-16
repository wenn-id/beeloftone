import sqlite3
from contextlib import closing
from unittest import TestCase
from unittest.mock import patch

from beeloft.store import Store
import test_production


class ProductionCapacityTest(TestCase):
    setUp=test_production.ProductionTest.setUp
    post=test_production.ProductionTest.post
    order=test_production.ProductionTest.order
    move=test_production.ProductionTest.move

    def center(self,code,stage,daily=480,**options):
        return self.post('/api/work-centers',{'code':code,'name':'Line '+code,'stage':stage,
            'daily_minutes':daily,'reason':'Kapasitas awal'},**options)

    def standard(self,stage,center,minutes,product=None,expected_revision=0,**options):
        product=product or self.product
        return self.post(f"/api/products/{product['id']}/routing-standards/{stage}",{
            'expected_revision':expected_revision,'work_center_id':center['id'],
            'minutes_per_unit':str(minutes),'reason':'Studi waktu produksi'},**options)

    def calendar(self,center,work_date,minutes,expected_revision=0,**options):
        return self.post(f"/api/work-centers/{center['id']}/calendar",{
            'work_date':work_date,'expected_revision':expected_revision,
            'available_minutes':minutes,'reason':'Penyesuaian jadwal kerja'},**options)

    def test_remaining_route_calendar_and_capacity_risk_are_exact(self):
        centers={stage:self.center(stage.upper(),stage) for stage in
                 ('cutting','sewing','finishing','qc')}
        for stage,minutes in {'cutting':'35','sewing':'20','finishing':'5','qc':'2'}.items():
            self.standard(stage,centers[stage],minutes)
        self.calendar(centers['sewing'],'2026-10-07',0)
        with patch('beeloft.store.now',return_value='2026-10-01T02:00:00+00:00'):
            order=self.order(100,reference='PROD-CAPACITY',title='Batch kapasitas',
                             due_date='2026-10-09')
            line=order['lines'][0]['id']
            self.move(line,'planned','cutting',80)
            self.move(line,'cutting','sewing',40)

        route='/api/capacity-plan?as_of=2026-10-05&horizon_days=5&warning_percent=80'
        report=self.client.get(route).json()
        self.assertEqual(report['summary'],{'work_centers':4,'attention_work_centers':2,
            'overloaded_work_centers':1,'deadline_risk_work_centers':0,
            'near_capacity_work_centers':1,'orders_in_scope':1,'at_risk_orders':1,
            'coverage_gaps':0,'missing_standard_quantity':0,
            'required_minutes':'4800.000','available_minutes':9120})
        self.assertEqual((report['capacity_complete'],report['ledger_basis'],report['route_basis'],
                          report['calendar_basis'],report['horizon_end'],report['total']),
                         (True,'current_production_balances','remaining_standard_route',
                          'weekday_default_with_latest_date_override','2026-10-09',2))
        sewing=report['items'][0]
        self.assertEqual((sewing['code'],sewing['status'],sewing['required_minutes'],
                          sewing['available_minutes'],sewing['overload_minutes'],
                          sewing['utilization_percent'],sewing['at_risk_order_count']),
                         ('SEWING','overloaded','2000.000',1920,'80.000','104.17',1))
        self.assertEqual(sewing['days'][2]['source'],'override')
        self.assertEqual(sewing['orders'][0]['capacity_shortfall_minutes'],'80.000')
        self.assertEqual(sewing['orders'][0]['products'],[{
            'product_id':self.product['id'],'sku':'LUNA-BLUE-M','product_name':'Luna Blue',
            'stage':'sewing','quantity':100,'minutes_per_unit':'20.000',
            'required_minutes':'2000.000'}])
        cutting=report['items'][1]
        self.assertEqual((cutting['code'],cutting['status'],cutting['required_minutes'],
                          cutting['utilization_percent']),('CUTTING','near_capacity','2100.000','87.50'))
        self.assertEqual(cutting['orders'][0]['products'][0]['quantity'],60)
        self.assertEqual(self.client.get(route+'&status=available').json()['total'],2)
        stage=self.client.get(route+'&status=all&stage=sewing').json()
        self.assertEqual((stage['total'],stage['summary']['required_minutes']), (1,'2000.000'))
        calendar=self.client.get('/api/work-centers/'+centers['sewing']['id']+
            '/calendar?start_date=2026-10-05&end_date=2026-10-09').json()
        self.assertEqual(calendar['items'][0]['available_minutes'],0)

    def test_master_revisions_permissions_validation_and_coverage_gaps(self):
        cutting=self.center('CUT-A','cutting',600,key='center-once')
        self.assertEqual(cutting,self.center('CUT-A','cutting',600,key='center-once'))
        self.center('CUT-A','cutting',600,status=409)
        self.center('NOPE','cutting',status=403,api_key=self.operator['api_key'])
        self.center('NOPE','cutting',status=403,api_key=self.viewer['api_key'])
        sewing=self.center('SEW-A','sewing')
        self.standard('cutting',sewing,'10',status=422)
        standard=self.standard('cutting',cutting,'10')
        self.assertEqual((standard['revision'],standard['minutes_per_unit']),(1,'10.000'))
        self.standard('cutting',cutting,'11',expected_revision=1,status=403,
                      api_key=self.operator['api_key'])
        self.standard('cutting',cutting,'11',expected_revision=0,status=409)
        standard=self.standard('cutting',cutting,'11',expected_revision=1)
        self.assertEqual((standard['revision'],standard['minutes_per_unit']),(2,'11.000'))
        changed=self.post('/api/work-centers/'+cutting['id']+'/changes',{
            'expected_revision':1,'name':'Cutting utama','daily_minutes':720,'active':True,
            'reason':'Tambah satu operator'})
        self.assertEqual((changed['revision'],changed['daily_minutes']),(2,720))
        self.post('/api/work-centers/'+cutting['id']+'/changes',{
            'expected_revision':1,'name':'Lama','daily_minutes':600,'active':True,
            'reason':'Revisi basi'},status=409)
        self.post('/api/work-centers/'+cutting['id']+'/changes',{
            'expected_revision':2,'name':'Lama','daily_minutes':600,'active':'true',
            'reason':'Boolean tidak boleh string'},status=422)
        day=self.calendar(cutting,'2026-10-06',300)
        self.assertEqual(day['revision'],1)
        self.calendar(cutting,'2026-10-07',300,status=403,api_key=self.operator['api_key'])
        self.calendar(cutting,'2026-10-06',200,expected_revision=0,status=409)
        self.assertEqual(self.calendar(cutting,'2026-10-06',200,expected_revision=1)['revision'],2)

        with patch('beeloft.store.now',return_value='2026-10-01T02:00:00+00:00'):
            self.order(10,reference='PROD-GAPS',due_date='2026-10-09')
        report=self.client.get('/api/capacity-plan?as_of=2026-10-05&horizon_days=5&status=all').json()
        self.assertFalse(report['capacity_complete'])
        self.assertEqual((report['summary']['coverage_gaps'],report['summary']['missing_standard_quantity']),
                         (3,30))
        self.assertEqual({row['stage'] for row in report['coverage_gaps']},
                         {'sewing','finishing','qc'})
        for role in (self.operator,self.viewer):
            response=self.client.get('/api/capacity-plan?as_of=2026-10-05&status=all',
                                     headers={'X-API-Key':role['api_key']})
            self.assertEqual(response.status_code,200)
        for invalid in ('horizon_days=0','horizon_days=91','warning_percent=0','warning_percent=101',
                        'stage=planned','status=bad','limit=0','offset=-1','work_center_id='+'x'*161):
            self.assertEqual(self.client.get('/api/capacity-plan?'+invalid).status_code,422)
        self.assertEqual(self.client.get('/api/work-centers?status=bad').status_code,422)
        self.assertEqual(self.client.get('/api/capacity-plan?work_center_id=unknown').status_code,404)
        self.assertEqual(self.client.get('/api/work-centers/'+cutting['id']+
            '/calendar?start_date=2026-10-10&end_date=2026-10-09').status_code,422)
        self.assertEqual(self.client.get('/api/capacity-plan',headers={'X-API-Key':'bad'}).status_code,401)

    def test_migration_immutability_backup_and_read_only_report(self):
        order=self.order(4,reference='PROD-PRESERVED',due_date='2026-10-09')
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('production_capacity_calendar_events','production_routing_standard_events',
                          'production_work_center_events','production_work_centers'):
                db.execute('DROP TABLE '+table)
            db.execute('PRAGMA user_version=48')
        for _ in range(2): Store(self.path)
        center=self.center('QC-A','qc')
        standard=self.standard('qc',center,'1.5')
        day=self.calendar(center,'2026-10-06',240)
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        self.client.get('/api/capacity-plan?as_of=2026-10-05&horizon_days=5&status=all')
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
            for statement in (
                "UPDATE production_work_centers SET code='X' WHERE id='"+center['id']+"'",
                "DELETE FROM production_work_center_events WHERE work_center_id='"+center['id']+"'",
                "UPDATE production_routing_standard_events SET reason='X' WHERE id='"+standard['id']+"'",
                "DELETE FROM production_capacity_calendar_events WHERE id='"+day['id']+"'"):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(statement)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO production_capacity_calendar_events(id,work_center_id,work_date,
                    revision,available_minutes,reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?)''',
                    ('invalid-date',center['id'],'2026-99-99',1,1,'Tanggal invalid',self.admin['id'],
                     '2026-10-01T00:00:00+00:00'))
        backup=self.path.with_name('capacity-backup.sqlite3');self.app.state.store.backup(backup)
        restored=Store(backup)
        self.assertEqual(restored.work_centers()[0]['id'],center['id'])
        self.assertEqual(restored.routing_standard(self.product['id'],'qc')['revision'],1)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],54)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).status_code,200)
