import sqlite3
from contextlib import closing
from unittest import TestCase

from beeloft.store import Store
import test_replenishment_recommendations as replenishment_tests


class AiActionProposalTest(TestCase):
    setUp = replenishment_tests.ReplenishmentRecommendationsTest.setUp
    post = replenishment_tests.ReplenishmentRecommendationsTest.post
    material = replenishment_tests.ReplenishmentRecommendationsTest.material
    order = replenishment_tests.ReplenishmentRecommendationsTest.order
    payload = replenishment_tests.ReplenishmentRecommendationsTest.payload
    create = replenishment_tests.ReplenishmentRecommendationsTest.create
    decide = replenishment_tests.ReplenishmentRecommendationsTest.decide
    supplier = replenishment_tests.ReplenishmentRecommendationsTest.supplier
    setup_po = replenishment_tests.ReplenishmentRecommendationsTest.setup_po
    issue_po = replenishment_tests.ReplenishmentRecommendationsTest.issue_po
    receive = replenishment_tests.ReplenishmentRecommendationsTest.receive
    setup_costed_order = replenishment_tests.ReplenishmentRecommendationsTest.setup_costed_order
    setup_shipment = replenishment_tests.ReplenishmentRecommendationsTest.setup_shipment
    second_shipment = replenishment_tests.ReplenishmentRecommendationsTest.second_shipment
    save_bom = replenishment_tests.ReplenishmentRecommendationsTest.save_bom
    scenario = replenishment_tests.ReplenishmentRecommendationsTest.scenario

    def source(self):
        return dict(question='SKU LUNA-BLUE-M mana yang berisiko stockout dan perlu beli bahan?',
                    as_of='2026-11-15',window_days=14,lead_time_days=180,
                    review_period_days=180,safety_stock_days=90,batch_multiple=12)

    def production_body(self, **changes):
        body=self.source() | dict(action_kind='create_production_order',subject_id=self.product['id'],
            reference='AI-PROD-001',title='Replenishment Luna',owner_id=self.operator['id'],
            due_date='2026-12-20',reason='Rekomendasi stockout perlu ditinjau')
        body.update(changes)
        return body

    def purchase_body(self, material, **changes):
        body=self.source() | dict(action_kind='create_purchase_request',subject_id=material['id'],
            reference='AI-PR-001',required_date='2026-12-10',estimated_value='5000000',
            reason='Kebutuhan bahan hasil investigasi')
        body.update(changes)
        return body

    def decide_proposal(self, proposal, decision='approved', **options):
        changes=options.pop('changes',{})
        return self.post('/api/ai/action-proposals/'+proposal['id']+'/decisions',
            dict(status=decision,expected_revision=proposal['revision'],reason='Keputusan proposal AI') | changes,
            **options)

    def test_production_proposal_requires_approval_then_executes_once(self):
        self.scenario()
        before=len(self.client.get('/api/orders').json())
        proposal=self.post('/api/ai/action-proposals',self.production_body(),
                           api_key=self.operator['api_key'],key='ai-production')
        self.assertEqual((proposal['status'],proposal['recommendation']['preview']['quantity']),
                         ('submitted',156))
        self.assertEqual(len(self.client.get('/api/orders').json()),before)
        queue=self.client.get('/api/approvals?kind=ai_action').json()
        self.assertEqual((queue[0]['id'],queue[0]['context']['action_kind']),
                         (proposal['id'],'create_production_order'))
        self.assertEqual(self.client.get('/api/ai/action-proposals/'+proposal['id'],
            headers={'X-API-Key':self.viewer['api_key']}).status_code,200)
        self.decide_proposal(proposal,api_key=self.operator['api_key'],status=403)
        approved=self.decide_proposal(proposal,key='approve-ai-production')
        self.assertEqual(approved,self.decide_proposal(proposal,key='approve-ai-production'))
        self.assertEqual((approved['status'],approved['executed_entity_type']),
                         ('approved','production_order'))
        order=self.client.get('/api/orders/'+approved['executed_entity_id']).json()
        self.assertEqual((order['reference'],order['target_quantity'],order['created_by']),
                         ('AI-PROD-001',156,self.admin['id']))
        self.assertEqual(len(self.client.get('/api/orders').json()),before+1)

    def test_purchase_proposal_executes_as_submitted_pr(self):
        _,_,material,_=self.scenario()
        proposal=self.post('/api/ai/action-proposals',self.purchase_body(material),key='ai-purchase')
        self.assertEqual(proposal['action_payload']['lines'][0]['quantity'],'253.875')
        approved=self.decide_proposal(proposal,key='approve-ai-purchase')
        request=self.client.get('/api/purchase-requests/'+approved['executed_entity_id']).json()
        self.assertEqual((approved['executed_entity_type'],request['reference'],request['status']),
                         ('purchase_request','AI-PR-001','submitted'))
        self.assertEqual((request['estimated_value'],request['lines'][0]['quantity']),
                         ('5000000.00','253.875'))
        pending=self.client.get('/api/approvals').json()
        self.assertEqual({row['kind'] for row in pending},{'purchase_request'})

    def test_stale_recommendation_rejects_approval_atomically(self):
        _,_,material,_=self.scenario()
        proposal=self.post('/api/ai/action-proposals',self.purchase_body(material),key='ai-stale')
        self.create(dict(reference='PR-CHANGES-PLAN',order_id=None,required_date='2026-12-01',
            estimated_value='100.00',reason='Mengubah cakupan rekomendasi',
            lines=[dict(material_id=material['id'],quantity='1')]))
        before=len(self.client.get('/api/purchase-requests').json())
        self.decide_proposal(proposal,key='reject-stale-action',status=409)
        self.assertEqual(len(self.client.get('/api/purchase-requests').json()),before)
        self.assertEqual(self.client.get('/api/ai/action-proposals/'+proposal['id']).json()['status'],'submitted')

    def test_roles_cancellation_rejection_validation_and_filters(self):
        _,_,material,_=self.scenario()
        self.post('/api/ai/action-proposals',self.production_body(),
                  api_key=self.viewer['api_key'],status=403)
        invalid=({'subject_id':'missing'},{'subject_id':material['id']},{'title':None},
                 {'owner_id':None},{'due_date':None},{'required_date':'2026-12-01'},
                 {'estimated_value':'1'},{'question':'x'},{'unexpected':'bad'})
        for changes in invalid:
            self.post('/api/ai/action-proposals',self.production_body(**changes),status=422 if
                changes not in ({'subject_id':'missing'},{'subject_id':material['id']}) else 409)
        proposal=self.post('/api/ai/action-proposals',self.production_body(reference='AI-PROD-CANCEL'),
                           api_key=self.operator['api_key'])
        other=self.app.state.store.provision_user('Operator lain','operator')
        self.decide_proposal(proposal,'cancelled',api_key=other['api_key'],status=403)
        cancelled=self.decide_proposal(proposal,'cancelled',api_key=self.operator['api_key'])
        self.assertEqual(cancelled['status'],'cancelled')
        rejected=self.post('/api/ai/action-proposals',self.production_body(reference='AI-PROD-REJECT'))
        rejected=self.decide_proposal(rejected,'rejected')
        self.assertEqual(self.client.get('/api/ai/action-proposals?status=rejected').json()[0]['id'],rejected['id'])
        self.assertEqual(self.client.get('/api/ai/action-proposals?status=cancelled').json()[0]['id'],cancelled['id'])
        self.assertEqual(len(self.client.get('/api/ai/action-proposals?limit=1').json()),1)
        self.assertEqual(self.client.get('/api/approvals?kind=bad').status_code,422)

    def test_rollback_immutability_backup_and_migration(self):
        self.scenario()
        proposal=self.post('/api/ai/action-proposals',self.production_body(),key='rollback-proposal')
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_ai_action BEFORE INSERT ON requests WHEN NEW.key='fail-ai-action' BEGIN SELECT RAISE(ABORT,'fail'); END")
        before=len(self.client.get('/api/orders').json())
        self.decide_proposal(proposal,key='fail-ai-action',status=409)
        self.assertEqual(len(self.client.get('/api/orders').json()),before)
        self.assertEqual(self.client.get('/api/ai/action-proposals/'+proposal['id']).json()['status'],'submitted')
        with self.app.state.store.transaction(write=True) as db:
            db.execute('DROP TRIGGER fail_ai_action')
        self.decide_proposal(proposal,key='fail-ai-action')
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('ai_action_proposals','ai_action_proposal_events'):
                for sql in ('UPDATE '+table+' SET created_at=created_at','DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
        backup=self.path.with_name('ai-action-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).ai_action_proposal(proposal['id'])['status'],'approved')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE ai_action_proposal_events')
            db.execute('DROP TABLE ai_action_proposals')
            db.execute('PRAGMA user_version=30');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],38)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_action_proposals').fetchone()[0],0)
