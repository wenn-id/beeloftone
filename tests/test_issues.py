import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_production


class IssueTest(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order
    detail = test_production.ProductionTest.detail

    def issue(self, order, **changes):
        return dict(line_id=order['lines'][0]['id'], stage='sewing',
                    description='Jarum patah, menunggu pengganti', owner_id=self.operator['id']) | changes

    def test_lifecycle_retry_board_and_unchanged_goods(self):
        order = self.order()
        body = self.issue(order)
        issue = self.post('/api/issues', body, key='issue-once', api_key=self.operator['api_key'])
        self.assertEqual(issue, self.post('/api/issues', body, key='issue-once', api_key=self.operator['api_key']))
        self.post('/api/issues', body | {'description': 'Lain'}, key='issue-once', status=409, api_key=self.operator['api_key'])
        self.assertEqual(self.detail(order)['totals'], order['totals'])
        self.assertEqual(self.detail(order)['open_issues'], 1)
        board = self.client.get('/api/production-board?status=blocked').json()
        self.assertEqual(board['total'], 1)
        self.assertEqual(board['open_issues'], 1)
        route = '/api/issues/' + issue['id'] + '/resolve'
        resolved = self.post(route, {'resolution': 'Jarum diganti dan diuji'}, key='resolve-once')
        self.assertEqual(resolved['resolved_by'], self.admin['id'])
        self.assertEqual(resolved, self.post(route, {'resolution': 'Jarum diganti dan diuji'}, key='resolve-once'))
        self.post(route, {'resolution': 'Timpa'}, status=409)
        rows = self.client.get('/api/orders/' + order['id'] + '/issues').json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['owner_name'], self.operator['name'])
        self.assertEqual(rows[0]['description'], body['description'])
        self.assertEqual(rows[0]['resolution'], resolved['resolution'])
        self.assertEqual(self.client.get('/api/production-board?status=blocked').json()['total'], 0)
        self.assertEqual(self.detail(order)['totals'], order['totals'])

    def test_permissions_validation_and_pagination(self):
        order = self.order()
        body = self.issue(order)
        self.post('/api/issues', body, status=403, api_key=self.viewer['api_key'])
        for changes in [{'description': ' '}, {'stage': 'bad'}, {'owner_id': self.viewer['id']}, {'created_by': self.admin['id']}]:
            self.post('/api/issues', body | changes, status=422)
        self.post('/api/issues', body | {'line_id': 'missing'}, status=404)
        issue = self.post('/api/issues', body)
        route = '/api/issues/' + issue['id'] + '/resolve'
        self.post(route, {'resolution': 'ok'}, status=403, api_key=self.viewer['api_key'])
        self.post(route, {'resolution': ' '}, status=422)
        self.post('/api/issues/missing/resolve', {'resolution': 'ok'}, status=404)
        self.app.state.store.disable_user(self.operator['id'])
        self.post('/api/issues', body, status=422)
        self.post('/api/issues', body, status=401, api_key=self.operator['api_key'])
        second = self.post('/api/issues', body | {'owner_id': self.admin['id']})
        rows = self.client.get('/api/orders/' + order['id'] + '/issues?limit=1&offset=1').json()
        self.assertEqual(rows[0]['id'], issue['id'])
        self.assertNotEqual(second['id'], issue['id'])
        self.assertEqual(self.client.get('/api/orders/missing/issues').status_code, 404)

    def test_cursor_does_not_repeat_after_new_issue_arrives(self):
        order = self.order()
        body = self.issue(order)
        first = self.post('/api/issues', body)
        self.post('/api/issues', body)
        route = '/api/orders/' + order['id'] + '/issues?limit=1'
        page = self.client.get(route).json()
        self.post('/api/issues', body)
        next_page = self.client.get(route + '&before=' + str(page[0]['sequence'])).json()
        self.assertEqual(next_page[0]['id'], first['id'])

    def test_simultaneous_resolution_keeps_first_record(self):
        issue = self.post('/api/issues', self.issue(self.order()))
        barrier = Barrier(2)
        def resolve(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/issues/' + issue['id'] + '/resolve', json={'resolution': str(index)},
                                   headers={'X-API-Key': self.admin['api_key'], 'Idempotency-Key': 'resolve-' + str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(resolve, range(2))), [201, 409])

    def test_v1_upgrade_preserves_records_and_is_repeatable(self):
        order = self.order()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE issues')
            db.execute('PRAGMA user_version=1')
            before = {table: db.execute('SELECT * FROM ' + table).fetchall()
                      for table in ['users', 'products', 'orders', 'order_lines', 'balances', 'movements', 'requests']}
        for _ in range(2):
            Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],51)
            for table, rows in before.items():
                self.assertEqual(db.execute('SELECT * FROM ' + table).fetchall(), rows)
        self.post('/api/issues', self.issue(order))
