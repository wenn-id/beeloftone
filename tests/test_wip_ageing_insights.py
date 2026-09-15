import sqlite3
from contextlib import closing
from unittest import TestCase
from unittest.mock import patch

from beeloft.store import Store
import test_production


class WipAgeingInsightsTest(TestCase):
    setUp=test_production.ProductionTest.setUp
    post=test_production.ProductionTest.post
    order=test_production.ProductionTest.order
    move=test_production.ProductionTest.move

    def test_ageing_attention_stage_rollup_and_filters(self):
        with patch('beeloft.store.now',return_value='2026-10-01T02:00:00+00:00'):
            stalled=self.order(100,reference='PROD-STALLED',title='Batch tertahan',
                               due_date='2026-10-10')
        line=stalled['lines'][0]['id']
        with patch('beeloft.store.now',return_value='2026-10-02T02:00:00+00:00'):
            self.move(line,'planned','cutting',70)
        with patch('beeloft.store.now',return_value='2026-10-05T02:00:00+00:00'):
            self.move(line,'cutting','sewing',40)
        with patch('beeloft.store.now',return_value='2026-10-06T02:00:00+00:00'):
            self.post('/api/issues',{'line_id':line,'stage':'sewing',
                'description':'Menunggu komponen <khusus>','owner_id':self.operator['id']})

        with patch('beeloft.store.now',return_value='2026-10-19T02:00:00+00:00'):
            moving=self.order(20,reference='PROD-MOVING',title='Batch lancar',
                              owner_id=self.admin['id'],due_date='2026-10-30')
            self.move(moving['lines'][0]['id'],'planned','cutting',10)
            rework=self.order(5,reference='PROD-REWORK',title='Batch perbaikan',
                              due_date='2026-10-30')
            rework_line=rework['lines'][0]['id']
            for source,target in [('planned','cutting'),('cutting','sewing'),
                                  ('sewing','finishing'),('finishing','qc')]:
                self.move(rework_line,source,target,5)
            self.move(rework_line,'qc','rework',5,reason='Jahitan perlu diperbaiki')

        route='/api/wip-ageing-insights?as_of=2026-10-20&idle_days=7'
        report=self.client.get(route).json()
        self.assertEqual(report['summary'],{'active_orders':3,'attention_orders':2,
            'stalled_orders':1,'overdue_orders':1,'blocked_orders':1,'rework_orders':1,
            'active_quantity':125,'planned_quantity':40,'in_process_quantity':85,
            'stalled_quantity':100,'open_issues':1,'largest_active_stage':'planned',
            'bottleneck_signal_stage':'sewing'})
        self.assertEqual((report['position_basis'],report['age_basis'],report['capacity_basis'],
                          report['bottleneck_signal_basis'],report['timezone'],report['total']),
                         ('current_production_ledger','latest_production_movement_or_order_created',
                          'not_configured','largest_current_quantity_on_stalled_orders',
                          'Asia/Jakarta',2))
        item=report['items'][0]
        self.assertEqual((item['reference'],item['inactive_days'],item['overdue_days'],
                          item['active_quantity'],item['planned_quantity'],item['in_process_quantity'],
                          item['primary_stage'],item['flags'],item['open_issue_count']),
                         ('PROD-STALLED',15,10,100,30,70,'sewing',
                          ['overdue','blocked','stalled'],1))
        self.assertEqual(item['positions'],[{'stage':'planned','quantity':30},
                                            {'stage':'cutting','quantity':30},
                                            {'stage':'sewing','quantity':40}])
        self.assertEqual(item['open_issues'][0]['description'],'Menunggu komponen <khusus>')
        sewing=next(row for row in report['stages'] if row['stage']=='sewing')
        self.assertEqual(sewing,{'stage':'sewing','quantity':40,'orders':1,
                                 'stalled_quantity':40,'stalled_orders':1,
                                 'blocked_quantity':40})
        self.assertEqual(self.client.get(route+'&status=moving').json()['items'][0]['reference'],
                         'PROD-MOVING')
        self.assertEqual(self.client.get(route+'&status=rework').json()['items'][0]['reference'],
                         'PROD-REWORK')
        self.assertEqual(self.client.get(route+'&status=blocked&stage=sewing').json()['total'],1)
        self.assertEqual(self.client.get(route+'&status=all&query=komponen').json()['total'],1)
        self.assertEqual(self.client.get(route+'&status=all&owner_id='+self.admin['id']).json()['total'],1)
        self.assertEqual(self.client.get(route+'&status=all&offset=3').json()['items'],[])

    def test_population_roles_validation_backup_and_read_only_behavior(self):
        with patch('beeloft.store.now',return_value='2026-10-10T02:00:00+00:00'):
            active=self.order(8,reference='PROD-ACTIVE',due_date='2026-10-30')
            completed=self.order(2,reference='PROD-DONE',due_date='2026-10-30')
            line=completed['lines'][0]['id']
            for source,target in [('planned','cutting'),('cutting','sewing'),
                                  ('sewing','finishing'),('finishing','qc'),('qc','warehouse')]:
                self.move(line,source,target,2)
        with patch('beeloft.store.now',return_value='2026-10-21T02:00:00+00:00'):
            self.order(3,reference='PROD-FUTURE',due_date='2026-11-01')
        route='/api/wip-ageing-insights?as_of=2026-10-20&idle_days=7&status=all'
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        report=self.client.get(route).json()
        self.assertEqual((report['total'],report['items'][0]['order_id'],report['owners'][0]['name']),
                         (1,active['id'],'Tim produksi'))
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(route,headers={'X-API-Key':role['api_key']}).json(),report)
        for invalid in ('idle_days=0','idle_days=366','stage=warehouse','status=bad','limit=0',
                        'offset=-1','query='+'x'*161,'owner_id='+'x'*161):
            self.assertEqual(self.client.get('/api/wip-ageing-insights?'+invalid).status_code,422)
        self.assertEqual(self.client.get('/api/wip-ageing-insights',
                                         headers={'X-API-Key':'bad'}).status_code,401)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
        backup=self.path.with_name('wip-ageing-insights-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).wip_ageing_insights('2026-10-20',7,status='all')
                         ['items'][0]['order_id'],active['id'])
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],51)
