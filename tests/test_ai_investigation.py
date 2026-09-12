import sqlite3
from contextlib import closing
from unittest import TestCase

from beeloft.brain import investigate
from beeloft.store import Store
import test_replenishment_recommendations as replenishment_tests


class AiInvestigationTest(TestCase):
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

    def body(self, question, **changes):
        return dict(question=question,as_of='2026-11-15',window_days=14,lead_time_days=180,
                    review_period_days=180,safety_stock_days=90,batch_multiple=12) | changes

    def ask(self, body, api_key=None, status=200):
        headers={'X-API-Key':api_key} if api_key else None
        response=self.client.post('/api/ai/investigate',json=body,headers=headers)
        self.assertEqual(response.status_code,status,response.text)
        return response.json()

    def test_stockout_question_returns_focused_evidence_and_non_executable_proposals(self):
        self.scenario()
        with self.app.state.store.transaction() as db:
            before=db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
        result=self.ask(self.body('SKU LUNA-BLUE-M mana yang berisiko stockout dan perlu beli bahan?'))
        self.assertEqual((result['intent'],result['confidence'],result['interpretation']),
                         ('stockout','high','risiko stockout dan replenishment'))
        self.assertEqual((result['engine'],result['external_model_used'],result['read_only']),
                         ('local_rules_v1',False,True))
        self.assertEqual(result['focus']['products'][0]['sku'],self.product['sku'])
        self.assertIn('156 pcs direkomendasikan untuk produksi',result['answer'])
        facts={row['label']:row for row in result['facts']}
        self.assertEqual((facts['SKU berisiko segera']['value'],facts['Bahan perlu dibeli']['value']),(1,1))
        finding=result['findings'][0]
        self.assertEqual((finding['severity'],finding['entity']['id'],finding['source']),
                         ('high',self.product['id'],'/api/replenishment-recommendations'))
        proposals={row['kind']:row for row in result['recommendations']}
        self.assertEqual(proposals['create_production_order']['preview']['quantity'],156)
        self.assertEqual(proposals['create_purchase_request']['preview']['quantity'],'253.875')
        for proposal in proposals.values():
            self.assertTrue(proposal['approval_required'])
            self.assertFalse(proposal['executable'])
        with self.app.state.store.transaction() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],before)

    def test_routes_questions_to_approvals_production_margin_and_overview(self):
        self.scenario()
        material=self.client.get('/api/materials').json()[0]
        request=self.create(dict(reference='AI-PENDING-PR',order_id=None,required_date='2026-11-20',
            estimated_value='100.00',reason='Menunggu analisis approval',
            lines=[dict(material_id=material['id'],quantity='1')]))
        approvals=self.ask(self.body('Apa saja yang menunggu persetujuan approval?'))
        self.assertEqual(approvals['intent'],'approvals')
        self.assertEqual(next(row for row in approvals['facts'] if row['label']=='Approval tertunda')['value'],1)
        self.assertEqual(approvals['findings'][0]['entity'],{'type':'purchase_request','id':request['id']})

        production=self.ask(self.body('Order produksi terlambat dan kendala apa yang perlu dicek?'))
        self.assertEqual(production['intent'],'production')
        self.assertGreaterEqual(next(row for row in production['facts']
                                     if row['label']=='Order terlambat')['value'],1)
        self.assertTrue(any(row['entity']['type']=='order' for row in production['findings']))

        margin=self.ask(self.body('Bagaimana margin kontribusi bisnis saat ini?'))
        self.assertEqual(margin['intent'],'margin')
        self.assertEqual(next(row for row in margin['facts']
                              if row['label']=='Margin belum lengkap')['value'],1)
        self.assertEqual(margin['findings'][0]['severity'],'high')

        overview=self.ask(self.body('Apa yang harus saya lihat sekarang?'))
        self.assertEqual((overview['intent'],overview['confidence']),('overview','low'))
        self.assertIn('order aktif',overview['answer'])
        self.assertIn('item menunggu keputusan',overview['answer'])
        self.assertIn('SKU berisiko stockout',overview['answer'])
        self.assertEqual(set(overview['evidence']),
                         {'production_board','approvals','replenishment'})

    def test_reference_in_question_focuses_production_and_margin(self):
        first,_,_,_=self.scenario()
        order=self.client.get('/api/orders/'+first['order_id']).json()
        production=self.ask(self.body('Cek produksi '+order['reference']+' apakah terlambat'))
        self.assertEqual(production['focus']['orders'][0]['id'],order['id'])
        self.assertEqual(production['evidence']['production_board']['total'],1)
        margin=self.ask(self.body('Tolong investigasi margin '+order['reference']))
        self.assertEqual(margin['focus']['orders'][0]['id'],order['id'])
        reports=margin['evidence']['contribution_margins']
        self.assertEqual([row['order_id'] for row in reports],[order['id']])

    def test_access_validation_backup_and_schema_remain_read_only(self):
        self.scenario()
        body=self.body('Apakah stok akan habis?')
        expected=self.ask(body,api_key=self.viewer['api_key'])
        self.assertEqual(expected['intent'],'stockout')
        self.ask(body,api_key='bad',status=401)
        invalid=({'question':' '},{'question':'x'},{'question':'x'*1001},{'as_of':'bad'},
                 {'window_days':6},{'lead_time_days':0},{'review_period_days':0},
                 {'safety_stock_days':-1},{'batch_multiple':0},{'window_days':True},
                 {'unexpected':'value'})
        for changes in invalid:
            self.ask(body | changes,status=422)
        backup=self.path.with_name('ai-investigation-backup.sqlite3')
        self.app.state.store.backup(backup)
        payload=body | {'as_of':'2026-11-15'}
        self.assertEqual(investigate(Store(backup),payload),expected)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],33)
