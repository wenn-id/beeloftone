import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store
import test_bundles as bundle_tests


class BundleHandoffTest(TestCase):
    setUp=bundle_tests.BundleTest.setUp
    post=bundle_tests.BundleTest.post
    order=bundle_tests.BundleTest.order
    material=bundle_tests.BundleTest.material
    receipt=bundle_tests.BundleTest.receipt
    issue=bundle_tests.BundleTest.issue
    setup_stock=bundle_tests.BundleTest.setup_stock
    prepare=bundle_tests.BundleTest.prepare
    cut=bundle_tests.BundleTest.cut
    setup_run=bundle_tests.BundleTest.setup_run
    create_bundle=bundle_tests.BundleTest.create_bundle

    def handoff(self,bundle,to_location='Sewing internal',key='handoff',**options):
        return self.post('/api/bundles/'+bundle['id']+'/handoffs',{
            'to_location':to_location,'reason':'Serahkan bundle fisik'},key=key,**options)

    def test_two_party_handoff_updates_custody_exactly_once(self):
        order,run=self.setup_run();bundle=self.create_bundle(run)
        sent=self.handoff(bundle)
        self.assertEqual(sent,self.handoff(bundle))
        self.assertEqual((sent['status'],sent['from_location'],sent['to_location']),
                         ('pending','Cutting','Sewing internal'))
        detail=self.client.get('/api/bundles/'+bundle['id']).json()
        self.assertEqual(detail['custody_location'],'Cutting')
        self.assertEqual(detail['pending_handoff']['id'],sent['id'])
        received=self.post('/api/bundle-handoffs/'+sent['id']+'/accept',{
            'reason':'Bundle fisik dan jumlah sesuai'},key='accept-handoff',
            api_key=self.operator['api_key'])
        self.assertEqual(received,self.post('/api/bundle-handoffs/'+sent['id']+'/accept',{
            'reason':'Bundle fisik dan jumlah sesuai'},key='accept-handoff',
            api_key=self.operator['api_key']))
        self.assertEqual(received['status'],'received')
        self.assertEqual(received['receiver_id'],self.operator['id'])
        detail=self.client.get('/api/bundles/'+bundle['id']).json()
        self.assertEqual(detail['custody_location'],'Sewing internal')
        self.assertIsNone(detail['pending_handoff'])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals']['sewing'],20)
        audit=self.client.get('/api/audit-events?q=BDL-001').json()['items']
        self.assertEqual({row['operation'].split(':')[0] for row in audit},
                         {'bundle','bundle-handoff','bundle-handoff-acceptance'})

    def test_pending_guards_cancellation_and_next_location(self):
        _,run=self.setup_run();bundle=self.create_bundle(run);sent=self.handoff(bundle)
        self.handoff(bundle,to_location='Finishing',key='duplicate-handoff',status=409)
        self.post('/api/bundles/'+bundle['id']+'/reverse',{'reason':'Salah bundle'},status=409)
        for account in (self.operator,self.viewer):
            self.post('/api/bundle-handoffs/'+sent['id']+'/cancel',{'reason':'Salah tujuan'},
                key='cancel-'+account['role'],api_key=account['api_key'],status=403)
        cancelled=self.post('/api/bundle-handoffs/'+sent['id']+'/cancel',{
            'reason':'Tujuan perlu diganti'},key='cancel-handoff')
        self.assertEqual(cancelled['status'],'cancelled')
        self.post('/api/bundle-handoffs/'+sent['id']+'/accept',{'reason':'Terlambat'},
            key='accept-cancelled',api_key=self.operator['api_key'],status=409)
        replacement=self.handoff(bundle,to_location='Sewing vendor A',key='replacement-handoff')
        self.assertEqual(replacement['from_location'],'Cutting')
        self.post('/api/bundle-handoffs/'+replacement['id']+'/accept',{'reason':'Diterima vendor'},
            key='replacement-accept',api_key=self.operator['api_key'])
        next_handoff=self.handoff(bundle,to_location='Finishing',key='next-handoff')
        self.assertEqual(next_handoff['from_location'],'Sewing vendor A')

    def test_permissions_validation_history_and_immutable_tables(self):
        _,run=self.setup_run();bundle=self.create_bundle(run)
        self.handoff(bundle,to_location='cutting',key='same-location',status=422)
        self.handoff(bundle,api_key=self.viewer['api_key'],status=403)
        sent=self.handoff(bundle)
        self.post('/api/bundle-handoffs/'+sent['id']+'/accept',{'reason':'Akun sama'},
            key='same-account',status=409)
        self.post('/api/bundle-handoffs/'+sent['id']+'/accept',{'reason':'Viewer'},
            key='viewer-accept',api_key=self.viewer['api_key'],status=403)
        received=self.post('/api/bundle-handoffs/'+sent['id']+'/accept',{'reason':'Diterima'},
            key='operator-accept',api_key=self.operator['api_key'])
        history=self.client.get('/api/bundles/'+bundle['id']+'/handoffs?limit=1').json()
        self.assertEqual(history,[received])
        self.assertEqual(self.client.get('/api/bundles/missing/handoffs').status_code,404)
        with self.app.state.store.transaction(write=True) as db:
            for table in ('bundle_handoffs','bundle_handoff_acceptances'):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(f'UPDATE {table} SET created_at=created_at')

    def test_concurrent_receivers_only_record_one_acceptance(self):
        _,run=self.setup_run();bundle=self.create_bundle(run);sent=self.handoff(bundle)
        second=self.app.state.store.provision_user('Penerima kedua','operator')
        barrier=Barrier(2)
        def accept(account,index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/bundle-handoffs/'+sent['id']+'/accept',
                    json={'reason':'Penerima '+str(index)},headers={'X-API-Key':account['api_key'],
                    'Idempotency-Key':'race-accept-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(lambda args:accept(*args),[(self.operator,1),(second,2)]))
        self.assertEqual(sorted(statuses),[201,409])
        self.assertEqual(len(self.client.get('/api/bundles/'+bundle['id']+'/handoffs').json()),1)

    def test_rollback_backup_and_migration_from_45(self):
        _,run=self.setup_run();bundle=self.create_bundle(run)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_handoff BEFORE INSERT ON requests WHEN NEW.key='fail-handoff' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.handoff(bundle,key='fail-handoff',status=409)
        self.assertEqual(self.client.get('/api/bundles/'+bundle['id']+'/handoffs').json(),[])
        backup=self.path.with_name('handoff-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).bundle_handoffs(bundle['id']),[])
        with closing(sqlite3.connect(self.path)) as db:
            for name in ('bundle_handoff_blocks_bundle_reversal','bundle_handoff_cancellations_no_delete',
                         'bundle_handoff_cancellations_no_update','bundle_handoff_acceptances_no_delete',
                         'bundle_handoff_acceptances_no_update','bundle_handoffs_no_delete',
                         'bundle_handoffs_no_update','bundle_handoff_cancellation_valid',
                         'bundle_handoff_acceptance_valid','bundle_handoff_valid'):
                db.execute('DROP TRIGGER '+name)
            db.execute('DROP TABLE bundle_handoff_cancellations')
            db.execute('DROP TABLE bundle_handoff_acceptances')
            db.execute('DROP TABLE bundle_handoffs')
            db.execute('PRAGMA user_version=45');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],54)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM bundle_handoffs').fetchone()[0],0)
