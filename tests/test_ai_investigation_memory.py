import sqlite3
from contextlib import closing
from unittest import TestCase

from beeloft.store import Store
import test_replenishment_recommendations as replenishment_tests


class AiInvestigationMemoryTest(TestCase):
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

    def body(self, question='SKU LUNA-BLUE-M mana yang berisiko stockout dan perlu beli bahan?', **changes):
        body=dict(question=question,as_of='2026-11-15',window_days=14,lead_time_days=180,
                  review_period_days=180,safety_stock_days=90,batch_multiple=12)
        body.update(changes)
        return body

    def save(self, body=None, **options):
        return self.post('/api/ai/investigations',body or self.body(),**options)

    def feedback(self, investigation, rating='helpful', reason='Jawaban membantu keputusan stok', **options):
        return self.post('/api/ai/investigations/'+investigation['id']+'/feedback',
                         {'rating':rating,'reason':reason},**options)

    def test_persists_snapshot_idempotently_and_lists_with_filters(self):
        self.scenario()
        saved=self.save(api_key=self.viewer['api_key'],key='save-investigation')
        self.assertEqual(saved,self.save(api_key=self.viewer['api_key'],key='save-investigation'))
        self.assertEqual((saved['intent'],saved['actor_id'],saved['source_payload']),
                         ('stockout',self.viewer['id'],self.body()))
        self.assertEqual(saved['recommendations'][0]['preview']['quantity'],156)
        self.assertEqual(saved['feedback_summary'],{'helpful':0,'not_helpful':0,'respondents':0})
        listed=self.client.get('/api/ai/investigations?intent=stockout&q=LUNA').json()
        self.assertEqual((listed[0]['id'],listed[0]['question'],listed[0]['action_count']),
                         (saved['id'],self.body()['question'],0))
        self.assertEqual(self.client.get('/api/ai/investigations?intent=margin').json(),[])
        second=self.save(self.body('Apa prioritas bisnis hari ini?'),key='second-investigation')
        page=self.client.get('/api/ai/investigations?limit=1').json()
        self.assertEqual(page[0]['id'],second['id'])
        older=self.client.get('/api/ai/investigations?before='+str(page[0]['sequence'])).json()
        self.assertEqual(older[0]['id'],saved['id'])

    def test_snapshot_stays_stable_when_business_data_changes(self):
        _,_,material,_=self.scenario()
        saved=self.save(key='snapshot-before-change')
        original=next(row for row in saved['recommendations']
                      if row['kind']=='create_purchase_request')['preview']['quantity']
        self.create(dict(reference='PR-AFTER-AI',order_id=None,required_date='2026-12-01',
            estimated_value='100.00',reason='Rencana pembelian baru',
            lines=[dict(material_id=material['id'],quantity='1')]))
        detail=self.client.get('/api/ai/investigations/'+saved['id']).json()
        retained=next(row for row in detail['recommendations']
                      if row['kind']=='create_purchase_request')['preview']['quantity']
        fresh=self.save(key='snapshot-after-change')
        current=next(row for row in fresh['recommendations']
                     if row['kind']=='create_purchase_request')['preview']['quantity']
        self.assertEqual((original,retained),('253.875','253.875'))
        self.assertNotEqual(current,retained)

    def test_feedback_is_append_only_and_latest_vote_counts(self):
        self.scenario();saved=self.save(key='feedback-investigation')
        first=self.feedback(saved,api_key=self.viewer['api_key'],key='viewer-feedback')
        self.assertEqual(first,self.feedback(saved,api_key=self.viewer['api_key'],key='viewer-feedback'))
        changed=self.feedback(saved,'not_helpful','Bukti perlu konteks tambahan',
                              api_key=self.viewer['api_key'],key='viewer-feedback-change')
        final=self.feedback(saved,reason='Angka stockout dapat ditindaklanjuti',key='admin-feedback')
        self.assertEqual(final['feedback_summary'],{'helpful':1,'not_helpful':1,'respondents':2})
        self.assertEqual(len(changed['feedback']),2)
        self.feedback(saved,reason='',status=422)
        self.feedback(saved,rating='bad',status=422)
        missing={'id':'missing'}
        self.feedback(missing,status=404)

    def test_linked_action_requires_the_saved_recommendation_to_match(self):
        _,_,material,_=self.scenario();saved=self.save(key='linked-investigation')
        body=self.body() | {'investigation_id':saved['id'],'action_kind':'create_production_order',
            'subject_id':self.product['id'],'reference':'AI-MEMORY-ORDER','title':'Order dari riwayat AI',
            'owner_id':self.operator['id'],'due_date':'2026-12-20','reason':'Tindak lanjut investigasi'}
        proposal=self.post('/api/ai/action-proposals',body,key='linked-action')
        self.assertEqual(proposal['investigation_id'],saved['id'])
        detail=self.client.get('/api/ai/investigations/'+saved['id']).json()
        self.assertEqual((detail['linked_actions'][0]['id'],detail['linked_actions'][0]['status']),
                         (proposal['id'],'submitted'))
        changed=self.body(window_days=28) | body
        changed['window_days']=28;changed['reference']='AI-MEMORY-MISMATCH'
        self.post('/api/ai/action-proposals',changed,key='mismatched-action',status=409)
        self.create(dict(reference='PR-STALE-MEMORY',order_id=None,required_date='2026-12-01',
            estimated_value='100.00',reason='Mengubah rekomendasi bahan',
            lines=[dict(material_id=material['id'],quantity='1')]))
        purchase=self.body() | {'investigation_id':saved['id'],'action_kind':'create_purchase_request',
            'subject_id':material['id'],'reference':'AI-MEMORY-PR','required_date':'2026-12-10',
            'estimated_value':'1000','reason':'Tindak lanjut investigasi lama'}
        self.post('/api/ai/action-proposals',purchase,key='stale-memory-action',status=409)

    def test_rollback_immutability_backup_and_migration_from_31(self):
        self.scenario()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_ai_memory BEFORE INSERT ON requests
                WHEN NEW.key='fail-ai-memory' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.save(key='fail-ai-memory',status=409)
        self.assertEqual(self.client.get('/api/ai/investigations').json(),[])
        with self.app.state.store.transaction(write=True) as db:
            db.execute('DROP TRIGGER fail_ai_memory')
        saved=self.save(key='saved-ai-memory')
        self.feedback(saved,key='saved-ai-feedback')
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('ai_investigations','ai_investigation_feedback'):
                for sql in ('UPDATE '+table+' SET created_at=created_at','DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
        backup=self.path.with_name('ai-memory-backup.sqlite3')
        self.app.state.store.backup(backup)
        restored=Store(backup).ai_investigation(saved['id'])
        self.assertEqual((restored['question'],restored['feedback_summary']['helpful']),
                         (saved['question'],1))
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE ai_investigation_actions')
            db.execute('DROP TABLE ai_investigation_feedback')
            db.execute('DROP TABLE ai_investigations')
            db.execute('PRAGMA user_version=31');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],39)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_investigations').fetchone()[0],0)
