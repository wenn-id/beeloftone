import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store
import test_production


class MarketingBudgetApprovalTest(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post

    def body(self, reference='MKT-001', **changes):
        return dict(reference=reference, campaign_name='Peluncuran koleksi biru', channel='Meta Ads',
                    start_date='2026-10-01', end_date='2026-10-31', amount='2500000.00',
                    objective='Mendatangkan pesanan untuk koleksi baru',
                    reason='Rencana kampanye kuartal empat') | changes

    def request(self, reference='MKT-001', **options):
        body = self.body(reference)
        body.update(options.pop('changes', {}))
        return self.post('/api/marketing-budget-requests', body,
                         api_key=options.pop('api_key', self.operator['api_key']), **options)

    def decide(self, request, decision='approved', **options):
        body = dict(status=decision, expected_revision=request['revision'], reason='Keputusan budget marketing')
        body.update(options.pop('changes', {}))
        return self.post('/api/marketing-budget-requests/'+request['id']+'/decisions', body, **options)

    def test_request_list_detail_inbox_and_approval(self):
        request = self.request(key='marketing-once')
        self.assertEqual(request, self.request(key='marketing-once'))
        self.assertEqual((request['status'], request['amount'], request['currency']),
                         ('submitted', '2500000.00', 'IDR'))
        self.assertEqual(self.client.get('/api/marketing-budget-requests/'+request['id']).json(), request)
        self.assertEqual(self.client.get('/api/marketing-budget-requests?status=submitted').json()[0], request)
        queue = self.client.get('/api/approvals?kind=marketing_budget').json()
        self.assertEqual((queue[0]['id'], queue[0]['department'], queue[0]['amount']),
                         (request['id'], 'Marketing', '2500000.00'))
        self.assertEqual(queue[0]['context'], {'campaign_name':'Peluncuran koleksi biru',
            'channel':'Meta Ads', 'start_date':'2026-10-01', 'end_date':'2026-10-31',
            'objective':'Mendatangkan pesanan untuk koleksi baru'})
        approved = self.decide(request, key='marketing-approved')
        self.assertEqual(approved, self.decide(request, key='marketing-approved'))
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual([event['status'] for event in approved['history']], ['approved','submitted'])
        self.assertEqual(self.client.get('/api/approvals?status=approved&kind=marketing_budget').json()[0]['id'], request['id'])

    def test_roles_cancellation_rejection_pagination_and_validation(self):
        self.request(api_key=self.viewer['api_key'], status=403)
        pending = self.request()
        other = self.app.state.store.provision_user('Operator marketing lain', 'operator')
        self.decide(pending, api_key=self.operator['api_key'], status=403)
        self.decide(pending, 'cancelled', api_key=other['api_key'], status=403)
        cancelled = self.decide(pending, 'cancelled', api_key=self.operator['api_key'])
        self.assertEqual(cancelled['status'], 'cancelled')
        rejected = self.decide(self.request('MKT-REJECT'), 'rejected')
        self.assertEqual(rejected['status'], 'rejected')
        newest = self.request('MKT-NEWEST')
        listed = self.client.get('/api/marketing-budget-requests?limit=1').json()
        self.assertEqual(listed[0]['id'], newest['id'])
        older = self.client.get('/api/marketing-budget-requests?limit=1&before='+str(newest['sequence'])).json()
        self.assertEqual(older[0]['id'], rejected['id'])
        for changes, status in [
            ({'reference':' '},422), ({'campaign_name':' '},422), ({'channel':' '},422),
            ({'amount':'0'},422), ({'amount':'1.001'},422), ({'amount':1},422),
            ({'amount':'1000000000000.01'},422), ({'start_date':'2026-11-01'},422),
            ({'objective':' '},422), ({'reason':' '},422), ({'extra':'bad'},422)
        ]:
            self.request('BAD-'+str(len(str(changes))), changes=changes, status=status)
        for changes in ({'status':'submitted'}, {'expected_revision':True},
                        {'expected_revision':0}, {'reason':' '}):
            self.decide(newest, changes=changes, status=422)
        self.assertEqual(self.client.get('/api/marketing-budget-requests/missing').status_code, 404)
        self.assertEqual(self.client.get('/api/approvals?kind=bad').status_code, 422)

    def test_concurrent_decisions_are_serialized(self):
        request = self.request()
        barrier = Barrier(2)
        def decide(status):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/marketing-budget-requests/'+request['id']+'/decisions', json={
                    'status':status, 'expected_revision':request['revision'], 'reason':'Keputusan bersamaan'},
                    headers={'X-API-Key':self.admin['api_key'],
                             'Idempotency-Key':'marketing-'+status}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(decide, ['approved','rejected'])), [201,409])

    def test_atomic_rollback_immutability_backup_and_migration_from_28(self):
        request = self.request()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_marketing BEFORE INSERT ON requests WHEN NEW.key='marketing-fail' BEGIN SELECT RAISE(ABORT,'fail'); END")
        self.decide(request, key='marketing-fail', status=409)
        self.assertEqual(self.client.get('/api/marketing-budget-requests/'+request['id']).json()['status'], 'submitted')
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('marketing_budget_requests','marketing_budget_request_events'):
                for sql in ('UPDATE '+table+' SET reason=reason', 'DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("""INSERT INTO marketing_budget_request_events(request_id,status,reason,actor_id,created_at)
                    VALUES(?,'submitted','Repeat',?,'2026-09-12')""", (request['id'],self.admin['id']))
        backup = self.path.parent/'marketing-budget-backup.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).marketing_budget_request(request['id']), request)

        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE marketing_budget_request_events')
            db.execute('DROP TABLE marketing_budget_requests')
            db.execute('PRAGMA user_version=28')
            db.commit()
        Store(self.path); Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],37)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM marketing_budget_requests').fetchone()[0],0)
