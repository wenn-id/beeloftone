import hashlib
import sqlite3
from contextlib import closing
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class BrowserSessionTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def login(self, key=None, status=200, **body):
        payload={'api_key':self.admin['api_key'] if key is None else key}|body
        response=self.client.post('/api/session',json=payload)
        self.assertEqual(response.status_code,status,response.text)
        return response

    def use_session_only(self):
        self.client.headers.pop('X-API-Key',None)

    def test_login_uses_http_only_session_and_csrf_for_writes(self):
        response=self.login()
        self.assertEqual(response.json(),{key:self.admin[key] for key in ('id','name','role')})
        cookies=response.headers.get_list('set-cookie')
        session_cookie=next(value for value in cookies if value.startswith('beeloft_session='))
        csrf_cookie=next(value for value in cookies if value.startswith('beeloft_csrf='))
        self.assertIn('HttpOnly',session_cookie);self.assertIn('SameSite=strict',session_cookie)
        self.assertNotIn('HttpOnly',csrf_cookie);self.assertIn('SameSite=strict',csrf_cookie)
        self.assertNotIn(self.admin['api_key'],response.text)
        self.use_session_only()
        self.assertEqual(self.client.get('/api/me').json()['id'],self.admin['id'])
        request={'sku':'SESSION-ONE','name':'Session product','color':'','size':''}
        denied=self.client.post('/api/products',json=request,headers={'Idempotency-Key':'session-product'})
        self.assertEqual(denied.status_code,403)
        csrf=self.client.cookies.get('beeloft_csrf')
        created=self.client.post('/api/products',json=request,
            headers={'Idempotency-Key':'session-product','X-CSRF-Token':csrf})
        self.assertEqual(created.status_code,201,created.text)

    def test_logout_requires_csrf_and_revokes_session(self):
        self.login();self.use_session_only()
        self.assertEqual(self.client.post('/api/session/logout').status_code,403)
        csrf=self.client.cookies.get('beeloft_csrf')
        response=self.client.post('/api/session/logout',headers={'X-CSRF-Token':csrf})
        self.assertEqual(response.json(),{'status':'signed_out'})
        self.assertEqual(self.client.get('/api/me').status_code,401)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM browser_sessions').fetchone()[0],0)

    def test_tokens_are_hashed_and_api_key_clients_remain_compatible(self):
        response=self.login();token=self.client.cookies.get('beeloft_session');csrf=self.client.cookies.get('beeloft_csrf')
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute('SELECT token_hash,csrf_hash FROM browser_sessions').fetchone()
            self.assertEqual(row,(hashlib.sha256(token.encode()).hexdigest(),hashlib.sha256(csrf.encode()).hexdigest()))
            self.assertNotIn(token,row);self.assertNotIn(csrf,row)
        self.client.cookies.set('beeloft_session','invalid')
        request={'sku':'API-KEY-STILL-WORKS','name':'API worker','color':'','size':''}
        created=self.client.post('/api/products',json=request,headers={'X-API-Key':self.admin['api_key'],
            'Idempotency-Key':'api-key-client'})
        self.assertEqual(created.status_code,201,created.text)
        self.login('invalid',401)
        self.login('',422)
        self.login(unexpected='field',status=422)
        self.assertNotIn('api_key',response.json())

    def test_disabled_and_expired_sessions_are_rejected(self):
        self.login();self.use_session_only();self.app.state.store.disable_user(self.admin['id'])
        self.assertEqual(self.client.get('/api/me').status_code,401)
        self.client.headers['X-API-Key']=self.operator['api_key'];self.login(self.operator['api_key'])
        self.use_session_only()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("UPDATE browser_sessions SET created_at='1999-01-01T00:00:00+00:00', expires_at='2000-01-01T00:00:00+00:00'")
        self.assertEqual(self.client.get('/api/me').status_code,401)

    def test_backup_and_migration_from_42(self):
        self.login();token=self.client.cookies.get('beeloft_session')
        backup=self.path.with_name('browser-session-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).authenticate_browser_session(token)['id'],self.admin['id'])
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE browser_sessions');db.execute('PRAGMA user_version=42');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],52)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM browser_sessions').fetchone()[0],0)
