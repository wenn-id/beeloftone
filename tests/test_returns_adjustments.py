import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_marketplace_shipping as shipping_tests


class ReturnsAdjustmentsTest(TestCase):
    setUp = shipping_tests.MarketplaceShippingTest.setUp
    post = shipping_tests.MarketplaceShippingTest.post
    order = shipping_tests.MarketplaceShippingTest.order
    material = shipping_tests.MarketplaceShippingTest.material
    receipt = shipping_tests.MarketplaceShippingTest.receipt
    issue = shipping_tests.MarketplaceShippingTest.issue
    setup_stock = shipping_tests.MarketplaceShippingTest.setup_stock
    prepare = shipping_tests.MarketplaceShippingTest.prepare
    cut = shipping_tests.MarketplaceShippingTest.cut
    create_bundle = shipping_tests.MarketplaceShippingTest.create_bundle
    setup_bundle = shipping_tests.MarketplaceShippingTest.setup_bundle
    create_job = shipping_tests.MarketplaceShippingTest.create_job
    complete = shipping_tests.MarketplaceShippingTest.complete
    setup_job = shipping_tests.MarketplaceShippingTest.setup_job
    finish = shipping_tests.MarketplaceShippingTest.finish
    setup_finishing = shipping_tests.MarketplaceShippingTest.setup_finishing
    inspect = shipping_tests.MarketplaceShippingTest.inspect
    setup_qc = shipping_tests.MarketplaceShippingTest.setup_qc
    receive = shipping_tests.MarketplaceShippingTest.receive
    setup_receipt = shipping_tests.MarketplaceShippingTest.setup_receipt
    move = shipping_tests.MarketplaceShippingTest.move
    reserve = shipping_tests.MarketplaceShippingTest.reserve
    release = shipping_tests.MarketplaceShippingTest.release
    pick = shipping_tests.MarketplaceShippingTest.pick
    pack = shipping_tests.MarketplaceShippingTest.pack
    ship = shipping_tests.MarketplaceShippingTest.ship

    def customer_return(self, shipment, reference='RET-001', quantity=1, **options):
        returned_date=options.pop('returned_date','2026-09-26')
        return_reason=options.pop('return_reason','too_small')
        return_location=options.pop('return_location','Area Retur A')
        stock_status=options.pop('stock_status','hold')
        return self.post('/api/marketplace-shipments/'+shipment['id']+'/returns',dict(
            reference=reference,quantity=quantity,return_reason=return_reason,return_location=return_location,
            stock_status=stock_status,returned_date=returned_date,reason='Retur pelanggan diterima dan diperiksa'),
            **options)

    def adjust(self, receipt, reference='ADJ-001', quantity_delta=1, **options):
        adjusted_date=options.pop('adjusted_date','2026-09-27')
        location=options.pop('location','Rak Barang Jadi A')
        stock_status=options.pop('stock_status','sellable')
        return self.post('/api/finished-goods-receipts/'+receipt['id']+'/adjustments',dict(
            reference=reference,location=location,stock_status=stock_status,quantity_delta=quantity_delta,
            adjusted_date=adjusted_date,reason='Selisih hasil stock opname'),**options)

    def flow(self, shipment_quantity=2):
        order,_,receipt=self.setup_receipt()
        reservation=self.reserve(receipt,quantity=6)
        pick=self.pick(reservation,quantity=4)
        pack=self.pack(pick,quantity=3)
        shipment=self.ship(pack,quantity=shipment_quantity)
        return order,receipt,shipment

    def test_partial_returns_restore_inspected_stock_with_lineage(self):
        order,receipt,shipment=self.flow()
        before=self.client.get('/api/orders/'+order['id']).json()['totals']
        first=self.customer_return(shipment,key='return-one')
        self.assertEqual(first,self.customer_return(shipment,key='return-one'))
        second=self.customer_return(shipment,reference='RET-002',return_reason='defect',
                                    return_location='Area Retur B',stock_status='damaged')
        self.assertEqual((first['shipment_reference'],first['pack_reference'],first['receipt_reference']),
                         (shipment['reference'],shipment['pack_reference'],receipt['reference']))
        current=self.client.get('/api/marketplace-shipments/'+shipment['id']).json()
        self.assertEqual((current['returned_quantity'],current['returnable_quantity']),(2,0))
        inventory=next(row for row in self.client.get('/api/finished-goods-inventory').json()
                       if row['sku']==receipt['sku'])
        self.assertEqual((inventory['sellable_quantity'],inventory['picked_quantity'],inventory['packed_quantity'],
                          inventory['shipped_quantity'],inventory['returned_quantity'],inventory['hold_quantity'],
                          inventory['damaged_quantity'],inventory['total_quantity']),(8,1,1,2,2,9,1,20))
        locations={(row['location'],row['stock_status']):row['quantity']
                   for row in self.client.get('/api/warehouse-inventory').json() if row['sku']==receipt['sku']}
        self.assertEqual(locations[('Area Retur A','hold')],1)
        self.assertEqual(locations[('Area Retur B','damaged')],1)
        listed=self.client.get('/api/orders/'+order['id']+'/marketplace-returns').json()
        self.assertEqual([row['id'] for row in listed],[second['id'],first['id']])
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'],before)

    def test_return_insights_group_structured_reasons_by_sku_size_and_marketplace(self):
        _,_,shipment=self.flow(shipment_quantity=3)
        small=self.customer_return(shipment,reference='RET-SMALL',return_reason='too_small')
        wrong=self.customer_return(shipment,reference='RET-WRONG',return_reason='wrong_item')
        self.customer_return(shipment,reference='RET-DEFECT',return_reason='defect')
        route='/api/return-insights?as_of=2026-09-30&window_days=7'
        report=self.client.get(route).json()
        self.assertEqual(report['summary'],{'groups':1,'skus':1,'marketplaces':1,
            'shipment_count':1,'shipped_quantity':3,'returned_quantity':3,'return_rate':'100.00',
            'sizing_quantity':1,'product_page_quantity':1,'defect_quantity':1,'other_quantity':0})
        self.assertEqual((report['period_start'],report['as_of']),('2026-09-24','2026-09-30'))
        self.assertEqual(report['reason_groups'],{'sizing':['too_small','too_big'],
            'product_page':['wrong_item','color_mismatch'],'quality':['defect'],'other':['other']})
        row=report['items'][0]
        self.assertEqual((row['sku'],row['size'],row['marketplace']),
                         (small['sku'],small['size'],'Tokopedia'))
        self.assertEqual(row['reason_quantities'],{'too_small':1,'too_big':0,'wrong_item':1,
            'defect':1,'color_mismatch':0,'other':0})
        self.assertEqual((row['sizing_quantity'],row['product_page_quantity'],row['return_rate']),
                         (1,1,'100.00'))
        self.post('/api/marketplace-returns/'+wrong['id']+'/reverse',
                  dict(reason='Barang ternyata sesuai pesanan'))
        corrected=self.client.get(route).json()
        self.assertEqual((corrected['summary']['returned_quantity'],corrected['summary']['return_rate']),
                         (2,'66.67'))
        self.assertEqual(corrected['items'][0]['reason_quantities']['wrong_item'],0)

    def test_return_insights_filters_validates_and_does_not_write(self):
        _,_,shipment=self.flow(shipment_quantity=2)
        self.customer_return(shipment,returned_date='2026-10-05')
        route='/api/return-insights?as_of=2026-09-30&window_days=30'
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        report=self.client.get(route).json()
        self.assertEqual((report['summary']['shipped_quantity'],report['summary']['returned_quantity']),
                         (2,0))
        sku=report['items'][0]['sku']
        self.assertEqual(self.client.get(route+'&query='+sku.lower()).json()['total'],1)
        self.assertEqual(self.client.get(route+'&marketplace=tokopedia').json()['total'],1)
        self.assertEqual(self.client.get(route+'&marketplace=Shopee').json()['total'],0)
        self.assertEqual(self.client.get(route+'&offset=1').json()['items'],[])
        self.assertEqual(self.client.get('/api/return-insights?as_of=2026-09-24&window_days=30').json()['total'],0)
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(route,headers={'X-API-Key':role['api_key']}).json(),report)
        for invalid in ('window_days=6','window_days=366','limit=0','offset=-1','query='+'x'*161):
            self.assertEqual(self.client.get('/api/return-insights?'+invalid).status_code,422)
        self.assertEqual(self.client.get('/api/return-insights',headers={'X-API-Key':'bad'}).status_code,401)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)

    def test_receipt_traceability_includes_fulfillment_and_corrections_without_writes(self):
        order,receipt,shipment=self.flow()
        returned=self.customer_return(shipment)
        movement=self.move(receipt,quantity=1)
        adjustment=self.adjust(receipt,quantity_delta=2)
        counted=self.post('/api/finished-goods-receipts/'+receipt['id']+'/stock-counts',dict(
            reference='TRACE-COUNT',scanned_sku=receipt['sku'],location='Rak Barang Jadi A',
            stock_status='sellable',counted_quantity=8,counted_date='2026-09-28',reason='Hitung ulang'))
        for path in ('/api/finished-goods-stock-counts/'+counted['id'],
                     '/api/finished-goods-adjustments/'+adjustment['id'],
                     '/api/warehouse-movements/'+movement['id'],
                     '/api/marketplace-returns/'+returned['id'],
                     '/api/marketplace-shipments/'+shipment['id'],
                     '/api/marketplace-packs/'+shipment['pack_id'],
                     '/api/marketplace-picks/'+shipment['pick_id']):
            self.post(path+'/reverse',dict(reason='Koreksi <contoh> & cek'))
        reservation=self.client.get('/api/marketplace-reservations/'+shipment['reservation_id']).json()
        self.release(reservation)
        self.post('/api/finished-goods-receipts/'+receipt['id']+'/reverse',dict(reason='Salah penerimaan'))
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        route='/api/finished-goods-receipts/'+receipt['id']+'/traceability'
        report=self.client.get(route).json()
        self.assertEqual(report['total'],20)
        self.assertEqual(report['receipt']['inventory'],[])
        self.assertEqual(report['receipt']['status'],'corrected')
        self.assertEqual(report['receipt']['order_id'],order['id'])
        self.assertEqual(report['receipt']['batch_id'],receipt['batch_id'])
        types={event['event_type']:event for event in report['events']}
        for kind in ('finished_goods_receipt','warehouse_movement','marketplace_pick','marketplace_pack',
                     'marketplace_shipment','marketplace_return','finished_goods_adjustment','finished_goods_stock_count'):
            self.assertIn(kind,types)
            self.assertIn(kind+'_correction',types)
            self.assertEqual(types[kind]['status'],'corrected')
        self.assertIn('marketplace_reservation_release',types)
        self.assertEqual(types['warehouse_movement']['scanned_code'],receipt['sku'])
        self.assertIn(shipment['tracking_number'],types['marketplace_shipment']['description'])
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(route,headers={'X-API-Key':role['api_key']}).json(),report)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)

    def test_traceability_isolates_receipts_and_keeps_cursor_stable(self):
        from unittest.mock import patch
        _,_,qc=self.setup_qc()
        first=self.receive(qc)
        second=self.receive(qc,reference='FG-OTHER')
        with patch('beeloft.store.now',return_value='2026-09-29T10:00:00+00:00'):
            for index in range(4):
                self.adjust(first,reference='TRACE-'+str(index))
            self.adjust(second,reference='OTHER-ONLY')
        route='/api/finished-goods-receipts/'+first['id']+'/traceability'
        expected=self.client.get(route).json()
        page=self.client.get(route,params={'limit':2}).json()
        collected=page['events'][:]
        with patch('beeloft.store.now',return_value='2026-09-30T10:00:00+00:00'):
            self.adjust(first,reference='TRACE-NEW')
        while page['next_before']:
            page=self.client.get(route,params={'limit':2,**page['next_before']}).json()
            collected.extend(page['events'])
        self.assertEqual(collected,expected['events'])
        self.assertEqual(len({row['event_id'] for row in collected}),5)
        self.assertFalse(any(row['reference']=='OTHER-ONLY' for row in collected))
        self.assertEqual(self.client.get(route+'?limit=0').status_code,422)
        self.assertEqual(self.client.get(route+'?before_time=2026').status_code,422)
        self.assertEqual(self.client.get(route,headers={'X-API-Key':'invalid'}).status_code,401)
        self.assertEqual(self.client.get('/api/finished-goods-receipts/missing/traceability').status_code,404)

    def test_material_batch_traceability_connects_receipt_to_finished_goods_and_corrections(self):
        order,_,receipt=self.setup_receipt()
        batch_id=receipt['batch_id']
        self.post('/api/material-reservations',dict(batch_id=batch_id,order_id=order['id'],quantity='1',
                  action='reserve',reason='Cadangan produksi'))
        self.post('/api/material-reservations',dict(batch_id=batch_id,order_id=order['id'],quantity='1',
                  action='release',reason='Cadangan tidak diperlukan'))
        bundle=self.client.get('/api/bundles/'+receipt['bundle_id']).json()
        handoff=self.post('/api/bundles/'+bundle['id']+'/handoffs',dict(
            to_location='Sewing internal',reason='Serahkan bundle ke sewing'))
        self.post('/api/bundle-handoffs/'+handoff['id']+'/accept',dict(reason='Bundle diterima'),
                  api_key=self.operator['api_key'])
        run=self.client.get('/api/cutting-runs/'+bundle['cutting_run_id']).json()
        self.post('/api/finished-goods-receipts/'+receipt['id']+'/reverse',dict(reason='Koreksi penerimaan'))
        self.post('/api/final-qc-records/'+receipt['final_qc_record_id']+'/reverse',dict(reason='Koreksi QC'))
        self.post('/api/finishing-records/'+receipt['finishing_record_id']+'/reverse',dict(reason='Koreksi finishing'))
        self.post('/api/sewing-jobs/'+receipt['job_id']+'/reverse',dict(reason='Koreksi sewing'))
        self.post('/api/bundles/'+receipt['bundle_id']+'/reverse',dict(reason='Koreksi bundle'))
        self.post('/api/cutting-runs/'+run['id']+'/reverse',dict(reason='Koreksi cutting'))
        self.post('/api/material-movements/'+run['issue_id']+'/reverse',dict(reason='Koreksi pengeluaran'))
        batch=self.client.get('/api/material-batches/'+batch_id).json()
        self.post('/api/material-movements/'+batch['receipt_id']+'/reverse',dict(reason='Koreksi penerimaan bahan'))
        with self.app.state.store.transaction() as db:
            before='\n'.join(db.iterdump())
        route='/api/material-batches/'+batch_id+'/traceability'
        report=self.client.get(route).json()
        self.assertEqual(report['total'],23)
        self.assertEqual((report['batch']['status'],report['batch']['balance']),('corrected','0.000'))
        self.assertEqual(report['batch']['reference'],batch['reference'])
        types={event['event_type'] for event in report['events']}
        for kind in ('material_receipt','material_issue','material_movement_correction','material_reservation',
                     'material_reservation_release','material_consumption','material_consumption_correction',
                     'cutting_run','cutting_run_correction','bundle','bundle_correction','bundle_handoff',
                     'bundle_handoff_acceptance','sewing_job','sewing_result',
                     'sewing_job_correction','finishing','finishing_correction','final_qc','final_qc_correction',
                     'finished_goods_receipt','finished_goods_receipt_correction'):
            self.assertIn(kind,types)
        finished=next(event for event in report['events'] if event['event_type']=='finished_goods_receipt')
        self.assertEqual((finished['reference'],finished['detail_id']),(receipt['reference'],receipt['id']))
        self.assertIn(receipt['sku'],finished['description'])
        for role in (self.operator,self.viewer):
            self.assertEqual(self.client.get(route,headers={'X-API-Key':role['api_key']}).json(),report)
        with self.app.state.store.transaction() as db:
            self.assertEqual('\n'.join(db.iterdump()),before)

    def test_material_batch_traceability_cursor_is_stable(self):
        from unittest.mock import patch
        batch,order,_=self.setup_stock()
        route='/api/material-batches/'+batch['id']+'/traceability'
        with patch('beeloft.store.now',return_value='2026-10-02T10:00:00+00:00'):
            for index in range(3):
                self.post('/api/material-reservations',dict(batch_id=batch['id'],order_id=order['id'],
                          quantity='0.001',action='reserve',reason='Cursor '+str(index)))
                self.post('/api/material-reservations',dict(batch_id=batch['id'],order_id=order['id'],
                          quantity='0.001',action='release',reason='Cursor '+str(index)))
        expected=self.client.get(route).json()
        page=self.client.get(route,params={'limit':2}).json();collected=page['events'][:]
        with patch('beeloft.store.now',return_value='2026-10-03T10:00:00+00:00'):
            self.post('/api/material-reservations',dict(batch_id=batch['id'],order_id=order['id'],
                      quantity='0.001',action='reserve',reason='Catatan baru'))
        while page['next_before']:
            page=self.client.get(route,params={'limit':2,**page['next_before']}).json()
            collected.extend(page['events'])
        self.assertEqual(collected,expected['events'])
        self.assertEqual(len({row['event_id'] for row in collected}),7)
        self.assertEqual(self.client.get(route+'?before_time=2026').status_code,422)
        self.assertEqual(self.client.get(route+'?limit=0').status_code,422)
        self.assertEqual(self.client.get('/api/material-batches/missing/traceability').status_code,404)

    def test_return_correction_respects_reserved_stock_and_unblocks_shipment(self):
        _,receipt,shipment=self.flow()
        returned=self.customer_return(shipment,return_location='Rak Retur Sellable',stock_status='sellable')
        self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',dict(reason='Salah kirim'),status=409)
        reserved=self.reserve(receipt,reference='MKT-RETURN',quantity=1,location='Rak Retur Sellable')
        self.post('/api/marketplace-returns/'+returned['id']+'/reverse',dict(reason='Retur salah'),status=409)
        self.release(reserved,key='release-return-stock')
        corrected=self.post('/api/marketplace-returns/'+returned['id']+'/reverse',
                            dict(reason='Paket ternyata bukan retur'),key='return-reverse')
        self.assertEqual(corrected['status'],'corrected')
        self.post('/api/marketplace-shipments/'+shipment['id']+'/reverse',dict(reason='Pengiriman salah'))

    def test_adjustments_change_receipt_stock_and_preserve_reservations(self):
        order,_,receipt=self.setup_receipt()
        positive=self.adjust(receipt,quantity_delta=3,location='Rak Opname',key='adjustment-positive')
        self.assertEqual(positive,self.adjust(receipt,quantity_delta=3,location='Rak Opname',key='adjustment-positive'))
        reserved=self.reserve(receipt,reference='MKT-OPNAME',quantity=2,location='Rak Opname')
        self.adjust(receipt,reference='ADJ-OVER',quantity_delta=-2,location='Rak Opname',status=409)
        negative=self.adjust(receipt,reference='ADJ-002',quantity_delta=-1,location='Rak Opname')
        bucket=next(row for row in self.client.get('/api/warehouse-inventory').json()
                    if row['sku']==receipt['sku'] and row['location']=='Rak Opname')
        self.assertEqual((bucket['quantity'],bucket['reserved_quantity'],bucket['available_quantity']),(2,2,0))
        self.post('/api/finished-goods-adjustments/'+positive['id']+'/reverse',dict(reason='Hitung awal salah'),status=409)
        self.release(reserved,key='release-opname')
        self.post('/api/finished-goods-adjustments/'+negative['id']+'/reverse',dict(reason='Pengurangan salah'))
        self.post('/api/finished-goods-adjustments/'+positive['id']+'/reverse',dict(reason='Penambahan salah'))
        self.assertFalse(any(row['location']=='Rak Opname' for row in self.client.get('/api/warehouse-inventory').json()))
        listed=self.client.get('/api/orders/'+order['id']+'/finished-goods-adjustments').json()
        self.assertEqual([row['id'] for row in listed],[negative['id'],positive['id']])

    def test_validation_roles_dates_reasons_statuses_and_missing_records(self):
        _,receipt,shipment=self.flow()
        self.customer_return(shipment,api_key=self.viewer['api_key'],status=403)
        self.customer_return(shipment,quantity=True,status=422)
        self.customer_return(shipment,returned_date='2026-09-24',status=422)
        self.customer_return(shipment,return_reason='changed_mind',status=422)
        self.customer_return(shipment,stock_status='picked',status=422)
        self.adjust(receipt,api_key=self.viewer['api_key'],status=403)
        self.adjust(receipt,quantity_delta=0,status=422)
        self.adjust(receipt,adjusted_date='2026-09-17',status=422)
        self.adjust(receipt,stock_status='packed',status=422)
        self.assertEqual(self.client.get('/api/marketplace-returns/missing').status_code,404)
        self.assertEqual(self.client.get('/api/finished-goods-adjustments/missing').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/marketplace-returns').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/finished-goods-adjustments').status_code,404)

    def test_races_cannot_overreturn_or_overdraw_adjustment(self):
        _,receipt,shipment=self.flow()
        barrier=Barrier(2)
        def save_return(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/marketplace-shipments/'+shipment['id']+'/returns',json=dict(
                    reference='RET-RACE-'+str(index),quantity=2,return_reason='other',
                    return_location='Area Retur',stock_status='hold',returned_date='2026-09-26',
                    reason='Uji retur bersamaan'),headers={'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'return-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save_return,range(2))),[201,409])

        barrier=Barrier(2)
        def save_adjustment(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/finished-goods-receipts/'+receipt['id']+'/adjustments',json=dict(
                    reference='ADJ-RACE-'+str(index),location='Rak Barang Jadi A',stock_status='sellable',
                    quantity_delta=-4,adjusted_date='2026-09-27',reason='Uji opname bersamaan'),
                    headers={'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'adjustment-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save_adjustment,range(2))),[201,409])

    def test_rollback_backup_immutability_and_migration_from_23(self):
        order,receipt,shipment=self.flow()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_return BEFORE INSERT ON requests WHEN NEW.key='fail-return' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.customer_return(shipment,key='fail-return',status=409)
        returned=self.customer_return(shipment)
        adjustment=self.adjust(receipt)
        backup=self.path.with_name('returns-adjustments-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).marketplace_return(returned['id']),returned)
        self.assertEqual(Store(backup).finished_goods_adjustment(adjustment['id']),adjustment)
        with self.app.state.store.transaction(write=True) as db:
            for table in ('marketplace_returns','finished_goods_adjustments'):
                for sql in ('UPDATE '+table+' SET reason=reason','DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)

        fresh_path=self.path.with_name('schema23.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            db.execute('DROP TRIGGER marketplace_shipment_reversal_valid')
            db.execute('DROP VIEW finished_goods_reserved_stock')
            db.execute('DROP VIEW finished_goods_stock_ledger')
            db.execute('DROP TABLE finished_goods_adjustment_reversals')
            db.execute('DROP TABLE finished_goods_adjustments')
            db.execute('DROP TABLE marketplace_return_reversals')
            db.execute('DROP TABLE marketplace_returns')
            db.execute('PRAGMA user_version=23');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],54)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM marketplace_returns').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM finished_goods_adjustments').fetchone()[0],0)
