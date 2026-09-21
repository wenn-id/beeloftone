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

    def settle(self, shipment):
        return self.post('/api/marketplace-shipments/'+shipment['id']+'/sale-settlements',dict(
            reference='AI-MARGIN-SETTLE',gross_revenue='1000',seller_discount='1000',
            customer_refund='0',marketplace_fee='100',shipping_cost='25',other_variable_cost='10',
            settled_date='2026-10-25',reason='Settlement diskon penuh'))

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
                         {'production_board','production_scope','approvals','replenishment'})

    def test_zero_net_revenue_margin_answers_without_a_ratio(self):
        order,shipment=self.setup_shipment()
        settlement=self.settle(shipment)
        self.assertEqual((settlement['gross_revenue'],settlement['seller_discount'],
                          settlement['net_revenue']),('1000.00','1000.00','0.00'))
        general=self.ask(self.body('Bagaimana margin kontribusi bisnis saat ini?'))
        focused=self.ask(self.body('Tolong investigasi margin '+order['reference']))
        for result in (general,focused):
            self.assertEqual(result['intent'],'margin')
            finding=result['findings'][0]
            self.assertEqual(finding['entity'],{'type':'order','id':order['id']})
            self.assertIn('margin Rp-228.11',finding['title'])
            self.assertEqual(finding['detail'],'Rasio margin belum tersedia (pendapatan bersih Rp0.00).')
            facts={row['label']:row['value'] for row in result['facts']}
            self.assertEqual((facts['Margin lengkap'],facts['Margin belum lengkap'],
                              facts['Total margin terhitung']),(1,0,'-228.11'))
        self.assertEqual(focused['focus']['orders'][0]['id'],order['id'])
        self.assertEqual([(row['net_revenue'],row['contribution_margin'],
                           row['contribution_margin_rate'])
                          for row in focused['evidence']['contribution_margins']],
                         [('0.00','-228.11',None)])

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

    def test_focused_production_answer_never_reports_another_order(self):
        focused=self.order(qty=10,reference='AUDIT-FOCUSED',due_date='2026-12-31')
        late=self.order(qty=500,reference='AUDIT-LATE',due_date='2026-01-01')
        self.post('/api/movements',dict(line_id=late['lines'][0]['id'],from_stage='planned',
            to_stage='cutting',quantity=500,reason='Cutting order lain'))
        board=self.client.get('/api/production-board').json()
        self.assertEqual((board['summary']['active'],board['summary']['overdue'],
                          board['summary']['in_progress']),(2,1,500))
        filtered=self.client.get('/api/production-board',params={'q':'AUDIT-FOCUSED'}).json()
        self.assertEqual((filtered['total'],filtered['summary']),(1,board['summary']))
        report=self.ask(self.body('Cek produksi AUDIT-FOCUSED'))
        self.assertEqual([row['id'] for row in report['focus']['orders']],[focused['id']])
        self.assertEqual(report['intent'],'production')
        self.assertEqual(report['answer'],
            'Ada 1 order aktif, 0 terlambat, 0 kendala terbuka, dan 0 pcs sedang diproses.')
        self.assertEqual({row['label']:row['value'] for row in report['facts']},
            {'Order aktif':1,'Order terlambat':0,'Kendala terbuka':0,'Sedang diproses':0})
        scope=report['evidence']['production_scope']
        self.assertEqual((scope['total'],scope['summary']['orders'],scope['open_issues']),(1,1,0))
        # Ringkasan board tetap global di evidence; yang fokus adalah agregat scope-nya.
        self.assertEqual(report['evidence']['production_board']['summary'],
            {'orders':2,'active':2,'overdue':1,'closed':0,'in_progress':500,'rework':0})

    def test_focused_production_aggregate_covers_results_beyond_one_page(self):
        product=self.post('/api/products',dict(sku='AUDIT-PAGE-M',name='Batch halaman',
            color='Abu',size='M'))
        for index in range(120):
            self.post('/api/orders',dict(reference='AUDIT-PAGE-%03d'%index,title='Batch halaman',
                owner_id=self.operator['id'],due_date='2026-12-31',
                lines=[dict(product_id=product['id'],quantity=1)]))
        # Lima order di luar populasi fokus. Jawaban yang masih bocor dari KPI global akan
        # melaporkan 125 order dan 5 keterlambatan, sedangkan jawaban yang hanya menjumlahkan
        # halaman pertama akan melaporkan 100.
        for index in range(5):
            self.order(qty=40,reference='AUDIT-OUTSIDE-%d'%index,due_date='2026-01-01')
        self.assertEqual(self.client.get('/api/production-board').json()['summary'],
            {'orders':125,'active':125,'overdue':5,'closed':0,'in_progress':0,'rework':0})
        report=self.ask(self.body('Cek produksi AUDIT-PAGE-M'))
        self.assertEqual(report['focus']['products'][0]['sku'],'AUDIT-PAGE-M')
        self.assertEqual(report['focus']['orders'],[])
        self.assertEqual(report['answer'],
            'Ada 120 order aktif, 0 terlambat, 0 kendala terbuka, dan 0 pcs sedang diproses.')
        self.assertEqual({row['label']:row['value'] for row in report['facts']},
            {'Order aktif':120,'Order terlambat':0,'Kendala terbuka':0,'Sedang diproses':0})
        board=report['evidence']['production_board']
        self.assertEqual((board['total'],len(board['orders'])),(120,100))
        self.assertEqual(report['evidence']['production_scope']['total'],120)
        self.assertEqual(report['evidence']['production_scope']['summary']['active'],120)

    def test_production_focus_uses_selected_ids_instead_of_text_search(self):
        first=self.order(qty=10,reference='FOCUS-ONE',due_date='2026-12-31')
        second=self.order(qty=20,reference='FOCUS-TWO',due_date='2026-12-31')
        other_product=self.post('/api/products',dict(sku='OUTSIDE-M',name='Outside',color='Red',size='M'))
        outside=self.post('/api/orders',dict(reference='FOCUS-ONE-EXTRA',title='Other batch',
            owner_id=self.operator['id'],due_date='2026-01-01',
            lines=[dict(product_id=other_product['id'],quantity=500)]))
        self.post('/api/movements',dict(line_id=outside['lines'][0]['id'],from_stage='planned',
            to_stage='cutting',quantity=500,reason='Outside focus'))
        empty=self.post('/api/products',dict(sku='EMPTY-M',name='Unused',color='Blue',size='M'))
        cases=[('FOCUS-ONE',[first['id']]),
               ('FOCUS-ONE dan FOCUS-TWO',[first['id'],second['id']]),
               (self.product['sku']+' dan '+empty['sku'],[first['id'],second['id']]),
               (empty['sku'],[])]
        for question,wanted in cases:
            with self.subTest(question=question):
                report=self.ask(self.body('Cek produksi '+question))
                self.assertEqual({row['label']:row['value'] for row in report['facts']},
                    {'Order aktif':len(wanted),'Order terlambat':0,'Kendala terbuka':0,'Sedang diproses':0})
                board=report['evidence']['production_board']
                self.assertEqual(sorted(row['id'] for row in board['orders']),sorted(wanted))
                self.assertEqual(board['total'],len(wanted))
                self.assertEqual(report['evidence']['production_scope']['total'],len(wanted))
                self.assertEqual(board['summary']['in_progress'],500)
                self.assertEqual(report['findings'],[])
                self.assertEqual(report['recommendations'],[])

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
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],55)
