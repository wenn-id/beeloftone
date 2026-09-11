import sqlite3
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import TestCase
from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_po_receipts as receipt_tests


class IncomingQCTest(TestCase):
    setUp = receipt_tests.PurchaseReceiptTest.setUp
    post = receipt_tests.PurchaseReceiptTest.post
    material = receipt_tests.PurchaseReceiptTest.material
    order = receipt_tests.PurchaseReceiptTest.order
    payload = receipt_tests.PurchaseReceiptTest.payload
    create = receipt_tests.PurchaseReceiptTest.create
    decide = receipt_tests.PurchaseReceiptTest.decide
    supplier = receipt_tests.PurchaseReceiptTest.supplier
    setup_po = receipt_tests.PurchaseReceiptTest.setup_po
    issue = receipt_tests.PurchaseReceiptTest.issue
    detail = receipt_tests.PurchaseReceiptTest.detail
    cancel = receipt_tests.PurchaseReceiptTest.cancel
    setup_receipt = receipt_tests.PurchaseReceiptTest.setup_receipt
    receive = receipt_tests.PurchaseReceiptTest.receive
    reverse = receipt_tests.PurchaseReceiptTest.reverse

    def intake(self, po, body, **options):
        return self.post('/api/purchase-orders/'+po['id']+'/qc-intakes', body, **options)

    def inspect(self, intake, kind='accept', quantity='1', **options):
        body=dict(kind=kind,quantity=quantity,reason='Hasil pemeriksaan')
        if kind=='accept': body.update(reference='QC-READY',location='Rak siap pakai')
        return self.post('/api/qc-intakes/'+intake['id']+'/decisions',body,**options)

    def reverse_decision(self, decision, **options):
        return self.post('/api/qc-decisions/'+decision['id']+'/reverse',dict(reason='Koreksi pemeriksaan'),**options)

    def qc(self, intake):
        response=self.client.get('/api/qc-intakes/'+intake['id'])
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_hold_partial_accept_reject_replacement_and_retry(self):
        po, body=self.setup_receipt()
        intake=self.intake(po,body | {'quantity':'2.125'},key='arrive',api_key=self.operator['api_key'])
        self.assertEqual(intake,self.intake(po,body | {'quantity':'2.125'},key='arrive',api_key=self.operator['api_key']))
        self.assertEqual(intake['held'],'2.125')
        self.assertEqual(self.client.get('/api/material-batches').json(),[])
        line=self.detail(po)['lines'][0]
        self.assertEqual((line['received'],line['held'],line['receivable']),('0.000','2.125','0.000'))
        self.cancel(po,status=409)
        self.receive(po,body | {'reference':'DUP'},status=409)
        self.intake(po,body | {'reference':'DUP'},status=409)
        accepted=self.inspect(intake,quantity='1.125',key='accept')
        self.assertEqual(accepted,self.inspect(intake,quantity='1.125',key='accept'))
        batch=self.client.get('/api/material-batches/'+accepted['history'][0]['batch_id']).json()
        self.assertEqual(batch['balance'],'1.125')
        self.assertEqual(batch['qc_intake_id'],intake['id'])
        self.assertEqual(accepted['held'],'1.000')
        self.inspect(intake,quantity='1.001',status=409)
        rejected=self.inspect(intake,'reject','1',key='reject')
        self.assertEqual((rejected['accepted'],rejected['rejected'],rejected['held']),('1.125','1.000','0.000'))
        self.assertEqual(self.detail(po)['lines'][0]['receivable'],'1.000')
        replacement=self.receive(po,body | {'reference':'REPLACEMENT','quantity':'1'})
        self.assertEqual(self.detail(po)['fulfillment'],'received')
        self.reverse_decision(rejected['history'][0],status=409)
        self.reverse(replacement)
        self.reverse_decision(rejected['history'][0])
        self.assertEqual(self.qc(intake)['held'],'1.000')
        self.assertEqual(rejected,self.inspect(intake,'reject','1',key='reject'))

    def test_accept_reversal_stock_guards_and_cancel_intake(self):
        po,body=self.setup_receipt()
        intake=self.intake(po,body)
        accepted=self.inspect(intake,quantity='1.125')
        decision=accepted['history'][0]
        batch=self.client.get('/api/material-batches/'+decision['batch_id']).json()
        self.reverse(batch,status=409)
        order=self.order()
        reservation=dict(batch_id=batch['id'],order_id=order['id'],action='reserve',quantity='1',reason='Jatah')
        self.post('/api/material-reservations',reservation)
        self.reverse_decision(decision,status=409)
        self.post('/api/material-reservations',reservation | {'action':'release'})
        issued=self.post('/api/material-issues',dict(batch_id=batch['id'],order_id=order['id'],quantity='1',reason='Cutting'))
        self.reverse_decision(decision,status=409)
        self.post('/api/material-movements/'+issued['id']+'/reverse',dict(reason='Dikembalikan'))
        self.reverse_decision(decision,key='undo')
        self.assertEqual(self.qc(intake)['held'],'1.125')
        self.assertEqual(self.client.get('/api/material-batches/'+batch['id']).json()['balance'],'0.000')
        self.reverse_decision(decision,status=409)
        cancelled=self.post('/api/qc-intakes/'+intake['id']+'/cancel',dict(reason='Salah kedatangan'),key='cancel')
        self.assertIsNotNone(cancelled['cancellation'])
        self.assertEqual(self.detail(po)['lines'][0]['receivable'],'2.125')
        self.inspect(intake,status=409)
        self.cancel(po)

    def test_roles_validation_rollback_and_audit(self):
        po,body=self.setup_receipt()
        self.intake(po,body,api_key=self.viewer['api_key'],status=403)
        for changes,status in [({'material_id':'bad'},422),({'quantity':'0'},422),({'quantity':'1.0001'},422),({'reason':' '},422)]:
            self.intake(po,body | changes,status=status)
        intake=self.intake(po,body)
        self.inspect(intake,api_key=self.operator['api_key'],status=403)
        self.inspect(intake,api_key=self.viewer['api_key'],status=403)
        self.post('/api/qc-intakes/'+intake['id']+'/decisions',dict(kind='accept',quantity='1',reason='Test'),status=422)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_qc BEFORE INSERT ON requests WHEN NEW.key='fail-qc' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.inspect(intake,key='fail-qc',status=409)
        self.assertEqual(self.qc(intake)['held'],'1.125')
        self.assertEqual(self.client.get('/api/material-batches').json(),[])
        accepted=self.inspect(intake)
        self.post('/api/qc-intakes/'+intake['id']+'/cancel',dict(reason='Batal'),status=409)
        self.reverse_decision(accepted['history'][0],api_key=self.operator['api_key'],status=403)
        with self.app.state.store.transaction(write=True) as db:
            for table in ['qc_intakes','qc_decisions']:
                for operation in ['DELETE FROM '+table,'UPDATE '+table+' SET reason=reason']:
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(operation)
        self.assertEqual(self.client.get('/api/qc-intakes/'+intake['id'],headers={'X-API-Key':self.viewer['api_key']}).status_code,200)
        self.assertEqual(self.client.get('/api/qc-intakes/missing').status_code,404)

    def test_concurrent_release_and_hold_vs_direct_receipt(self):
        po,body=self.setup_receipt()
        barrier=Barrier(2)
        def compete(action):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/purchase-orders/'+po['id']+('/qc-intakes' if action=='hold' else '/receipts'),
                    json=body | {'quantity':'2.125'},headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':action}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(compete,['hold','receive'])),[201,409])
        detail=self.detail(po)
        if not detail['qc_intakes']:
            self.reverse(detail['receipts'][0])
            self.intake(po,body | {'quantity':'2.125'})
        intake=self.detail(po)['qc_intakes'][0]
        barrier=Barrier(2)
        def release(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/qc-intakes/'+intake['id']+'/decisions',
                    json=dict(kind='accept',quantity='2',reference='QC-'+str(index),location='Rak',reason='QC'),
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':'release-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(release,range(2))),[201,409])
        self.assertEqual(self.qc(intake)['held'],'0.125')

    def test_migration_backup_and_cancelled_po(self):
        po,body=self.setup_receipt()
        old=self.receive(po,body)
        with self.app.state.store.transaction(write=True) as db:
            for table in ['qc_intake_cancellations','qc_decisions','qc_intakes']:
                db.execute('DROP TABLE '+table)
            db.execute('PRAGMA user_version=10')
        Store(self.path)
        self.assertEqual(self.detail(po)['lines'][0]['received'],'1.125')
        self.assertEqual(self.detail(po)['qc_intakes'],[])
        intake=self.intake(po,body | {'reference':'ARRIVAL','quantity':'1'})
        rejected=self.inspect(intake,'reject','1')
        backup=self.path.parent/'qc-backup.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).quality_intake(intake['id']),self.qc(intake))
        self.reverse(old)
        self.cancel(po)
        self.reverse_decision(rejected['history'][0],status=409)
        self.intake(po,body | {'reference':'CLOSED'},status=409)

    def test_database_guard_requires_receipt_reversal_for_accept_reversal(self):
        po,body=self.setup_receipt()
        intake=self.intake(po,body)
        accepted=self.inspect(intake)
        original=accepted['history'][0]
        with self.app.state.store.transaction(write=True) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO qc_decisions(id,intake_id,kind,quantity_milli,reversal_of,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?)''', ('bad-qc-reversal',intake['id'],'accept',-1000,original['id'],'Direct SQL',self.admin['id'],'2026-01-01T00:00:00+00:00'))
