import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_production


class OrderChangeTest(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order
    detail = test_production.ProductionTest.detail

    def change(self, order, **changes):
        return dict(owner_id=self.admin['id'], due_date='2099-01-01',
                    expected_revision=order['revision'], reason='Jadwal mesin berubah') | changes

    def test_change_audit_retry_and_board(self):
        order = self.order()
        route = '/api/orders/' + order['id'] + '/changes'
        body = self.change(order)
        updated = self.post(route, body, key='change-once')
        self.assertEqual(updated['due_date'], '2099-01-01')
        self.assertEqual(updated['owner_id'], self.admin['id'])
        self.assertGreater(updated['revision'], order['revision'])
        self.assertEqual(updated['totals'], order['totals'])
        self.assertEqual(updated['lines'], order['lines'])
        self.assertFalse(updated['overdue'])
        second = self.post(route, self.change(updated, due_date='2099-02-01'))
        self.assertEqual(updated, self.post(route, body, key='change-once'))
        self.post(route, body | {'reason': 'Lain'}, key='change-once', status=409)
        self.post(route, body, status=409)
        self.assertEqual(self.detail(order), second)
        rows = self.client.get(route).json()
        self.assertEqual(len(rows), 2)
        original = rows[-1]
        self.assertEqual(original['old_due_date'], order['due_date'])
        self.assertEqual(original['old_owner_id'], self.operator['id'])
        self.assertEqual(original['new_owner_id'], self.admin['id'])
        self.assertEqual(original['actor_id'], self.admin['id'])
        self.assertEqual(original['reason'], body['reason'])
        self.assertEqual(self.client.get(route + '?limit=1&before=' + str(rows[0]['sequence'])).json()[0]['id'], original['id'])
        board = self.client.get('/api/production-board?status=overdue').json()
        self.assertEqual(board['total'], 0)
        with closing(sqlite3.connect(self.path)) as db:
            for sql in ['DELETE FROM order_changes', "UPDATE order_changes SET reason='rewrite'"]:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)

    def test_validation_roles_and_missing_order(self):
        order = self.order()
        route = '/api/orders/' + order['id'] + '/changes'
        body = self.change(order)
        for account in [self.operator, self.viewer]:
            self.post(route, body, status=403, api_key=account['api_key'])
            self.assertEqual(self.client.get(route, headers={'X-API-Key':account['api_key']}).status_code, 200)
        for delta in [{'reason':' '}, {'due_date':'invalid'}, {'owner_id':self.viewer['id']},
                      {'owner_id':'missing'}, {'expected_revision':True}, {'expected_revision':-1},
                      {'actor_id':self.operator['id']}, {'quantity':999}]:
            self.post(route, body | delta, status=422)
        self.post(route, body | {'owner_id':order['owner_id'], 'due_date':order['due_date']}, status=422)
        self.app.state.store.disable_user(self.operator['id'])
        self.post(route, body | {'owner_id':self.operator['id']}, status=422)
        self.post('/api/orders/missing/changes', body, status=404)
        self.assertEqual(self.client.get('/api/orders/missing/changes').status_code, 404)
        self.assertEqual(self.detail(order), order)
        self.assertEqual(self.client.get(route).json(), [])

    def test_concurrent_edits_reject_stale_revision(self):
        order = self.order()
        barrier = Barrier(2)
        def edit(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/orders/' + order['id'] + '/changes',
                    json=self.change(order, due_date=f'2099-01-0{index+1}'),
                    headers={'X-API-Key':self.admin['api_key'], 'Idempotency-Key':f'edit-{index}'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(edit, range(2))), [201,409])
        self.assertEqual(len(self.client.get('/api/orders/' + order['id'] + '/changes').json()), 1)

    def test_audit_failure_rolls_back_order(self):
        order = self.order()
        route = '/api/orders/' + order['id'] + '/changes'
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER fail_change BEFORE INSERT ON order_changes BEGIN SELECT RAISE(ABORT,'fail'); END")
        self.post(route, self.change(order), key='failed-change', status=409)
        self.assertEqual(self.detail(order), order)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TRIGGER fail_change')
        self.post(route, self.change(order), key='failed-change')

    def test_v2_upgrade_keeps_existing_data(self):
        order = self.order()
        self.post('/api/issues', {'line_id':order['lines'][0]['id'], 'stage':'cutting',
                  'description':'Menunggu mesin', 'owner_id':self.operator['id']})
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE order_changes')
            db.execute('PRAGMA user_version=2')
            tables = ['users','products','orders','order_lines','balances','movements','requests','issues']
            before = {table:db.execute('SELECT * FROM ' + table).fetchall() for table in tables}
        for _ in range(2):
            Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],33)
            for table, rows in before.items():
                self.assertEqual(db.execute('SELECT * FROM ' + table).fetchall(), rows)
        self.assertEqual(self.detail(order)['revision'], 0)
