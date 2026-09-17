import sqlite3
from contextlib import closing
from unittest import TestCase

from beeloft.store import Store
import test_final_qc


class ProductionQualityInsightsTest(TestCase):
    setUp=test_final_qc.FinalQcTest.setUp
    post=test_final_qc.FinalQcTest.post
    order=test_final_qc.FinalQcTest.order
    material=test_final_qc.FinalQcTest.material
    receipt=test_final_qc.FinalQcTest.receipt
    issue=test_final_qc.FinalQcTest.issue
    setup_stock=test_final_qc.FinalQcTest.setup_stock
    prepare=test_final_qc.FinalQcTest.prepare
    cut=test_final_qc.FinalQcTest.cut
    create_bundle=test_final_qc.FinalQcTest.create_bundle
    setup_bundle=test_final_qc.FinalQcTest.setup_bundle

    def setup_quality(self):
        order,_,bundle=self.setup_bundle()

        def job(reference,assignment_type,assignee):
            created=self.post('/api/bundles/'+bundle['id']+'/sewing-jobs',{
                'reference':reference,'assignment_type':assignment_type,'assignee':assignee,
                'quantity_out':10,'cost':'100000.00' if assignment_type=='makloon' else '0.00',
                'sent_date':'2026-09-11','reason':'Uji sumber kualitas'})
            return self.post('/api/sewing-jobs/'+created['id']+'/complete',{
                'completed_quantity':10,'defect_quantity':0,'missing_quantity':0,
                'returned_date':'2026-09-15','reason':'Hasil sewing diterima'})

        def finishing(job,reference):
            return self.post('/api/sewing-jobs/'+job['id']+'/finishing-records',{
                'reference':reference,'quantity':10,'thread_trimmed':True,'ironed':True,
                'labels_attached':True,'hangtags_attached':True,'packaged':True,
                'completed_date':'2026-09-16','reason':'Finishing selesai'})

        def qc(finishing,reference,inspection_date,accepted,rework,reject,defect,source):
            return self.post('/api/finishing-records/'+finishing['id']+'/qc-records',{
                'reference':reference,'measurement_notes':'Ukuran diperiksa',
                'visual_notes':'Visual diperiksa','defect_type':defect,
                'responsible_source':source,'disposition':'Pisahkan sesuai hasil QC',
                'accepted_quantity':accepted,'rework_quantity':rework,
                'reject_quantity':reject,'inspection_date':inspection_date,
                'reason':'Hasil QC dihitung'})

        vendor=finishing(job('SEW-QUALITY-VENDOR','makloon','Vendor <B>'),'FIN-QUALITY-VENDOR')
        internal=finishing(job('SEW-QUALITY-INTERNAL','internal','Line <A>'),'FIN-QUALITY-INTERNAL')
        records={
            'vendor_previous':qc(vendor,'QC-VENDOR-PREV','2026-09-16',5,0,0,'Tidak ada','Vendor <B>'),
            'vendor_current':qc(vendor,'QC-VENDOR-NOW','2026-09-17',2,2,1,'Jahitan loncat','Vendor <B>'),
            'internal_previous':qc(internal,'QC-INTERNAL-PREV','2026-09-16',4,0,1,'Noda','Finishing'),
            'internal_current':qc(internal,'QC-INTERNAL-NOW','2026-09-17',5,0,0,'Tidak ada','QC internal')}
        return order,records

    def test_yield_vendor_trend_defects_sources_and_filters_are_exact(self):
        _,records=self.setup_quality()
        route=('/api/production-quality-insights?as_of=2026-09-23&window_days=7&'
               'warning_percent=20&change_threshold=5&status=all')
        report=self.client.get(route).json()
        self.assertEqual(report['summary'],{
            'record_count':2,'inspected_quantity':10,'accepted_quantity':7,
            'rework_quantity':2,'reject_quantity':1,'nonconforming_quantity':3,
            'reinspection_record_count':0,'reinspected_quantity':0,
            'reinspection_accepted_quantity':0,'reinspection_rework_quantity':0,
            'reinspection_reject_quantity':0,'reinspection_nonconforming_quantity':0,
            'first_pass_yield_percent':'70.00','nonconforming_rate_percent':'30.00',
            'rework_rate_percent':'20.00','reject_rate_percent':'10.00',
            'reinspection_nonconforming_rate_percent':'0.00','groups':2,
            'attention_groups':1,'previous_inspected_quantity':10,
            'previous_nonconforming_quantity':1,'previous_nonconforming_rate_percent':'10.00',
            'previous_reinspected_quantity':0,'previous_reinspection_nonconforming_quantity':0,
            'nonconforming_rate_change_points':'20.00'})
        self.assertEqual((report['current_period_start'],report['previous_period_start'],
                          report['previous_period_end'],report['source'],report['corrected_records'],
                          report['first_pass_yield_basis'],report['reinspections']),
                         ('2026-09-17','2026-09-10','2026-09-16',
                          'active_final_qc_records','excluded',
                          'initial_inspections_only','reported_separately'))
        vendor=report['items'][0]
        self.assertEqual((vendor['assignee'],vendor['assignment_type'],vendor['status'],
                          vendor['trend'],vendor['nonconforming_rate_change_points']),
                         ('Vendor <B>','makloon','attention','worsening','60.00'))
        self.assertEqual(vendor['attention_reasons'],['above_warning','worsening'])
        self.assertEqual((vendor['current']['inspected_quantity'],
                          vendor['current']['nonconforming_rate_percent'],
                          vendor['previous']['nonconforming_rate_percent']),(5,'60.00','0.00'))
        self.assertEqual(vendor['defect_types'],[{'defect_type':'Jahitan loncat',
            'record_count':1,'nonconforming_quantity':3}])
        self.assertEqual(vendor['responsible_sources'],[{'responsible_source':'Vendor <B>',
            'record_count':1,'nonconforming_quantity':3}])
        self.assertEqual(vendor['recent_records'][0]['id'],records['vendor_current']['id'])
        internal=report['items'][1]
        self.assertEqual((internal['assignee'],internal['status'],internal['trend'],
                          internal['nonconforming_rate_change_points']),
                         ('Line <A>','healthy','improving','-20.00'))
        page=self.client.get(route+'&limit=1&offset=1').json()
        self.assertEqual((page['total'],len(page['items']),page['items'][0]['assignee']),
                         (2,1,'Line <A>'))
        self.assertEqual(self.client.get(route.replace('status=all','status=attention')).json()['total'],1)
        self.assertEqual(self.client.get(route.replace('status=all','status=healthy')).json()['total'],1)
        filtered=self.client.get('/api/production-quality-insights',params={
            'as_of':'2026-09-23','window_days':7,'status':'all','assignment_type':'makloon',
            'query':'jahitan loncat'}).json()
        self.assertEqual((filtered['total'],filtered['items'][0]['assignee']),(1,'Vendor <B>'))

    def test_corrected_records_roles_validation_backup_and_read_only_behavior(self):
        _,records=self.setup_quality()
        self.post('/api/final-qc-records/'+records['vendor_current']['id']+'/reverse',
                  {'reason':'Hasil vendor salah catat'})
        route='/api/production-quality-insights?as_of=2026-09-23&window_days=7&status=all'
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        report=self.client.get(route).json()
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)
        self.assertEqual((report['total'],report['summary']['inspected_quantity'],
                          report['items'][0]['assignee']),(1,5,'Line <A>'))
        self.assertEqual(self.client.get(route+'&assignment_type=makloon').json()['total'],0)
        self.assertEqual(self.client.get(route+'&query=line%20%3CA%3E').json()['total'],1)
        self.assertEqual(self.client.get(
            '/api/production-quality-insights?as_of=2026-09-15&status=all').json()['total'],0)
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(route,headers={'X-API-Key':role['api_key']}).status_code,200)
        for invalid in ('window_days=6','window_days=366','warning_percent=0','warning_percent=101',
                        'change_threshold=0','change_threshold=101','assignment_type=vendor',
                        'status=bad','limit=0','offset=-1','query='+'x'*161):
            self.assertEqual(self.client.get('/api/production-quality-insights?'+invalid).status_code,422)
        self.assertEqual(self.client.get('/api/production-quality-insights',
                         headers={'X-API-Key':'bad'}).status_code,401)
        backup=self.path.with_name('production-quality-backup.sqlite3')
        self.app.state.store.backup(backup);restored=Store(backup)
        self.assertEqual(restored.production_quality_insights('2026-09-23',7,status='all')['total'],1)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],55)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
