"""Regresi P2-A (sisi server): apa yang boleh dianggap sebagai bukti logout.

UI memutuskan apakah ruang kerja boleh ditutup berdasarkan hasil `POST /api/session/logout`.
Sebelumnya setiap kegagalan ditelan dan ruang kerja selalu dibersihkan, sehingga layar login
muncul padahal session server masih hidup dan reload membuka kembali akun sebelumnya.

Modul ini menegakkan tabel keputusan yang dipakai klien:

* 200                       -> session benar-benar dicabut, cookie dihapus.
* 401                       -> session memang sudah tidak aktif; menutup ruang kerja itu benar.
* 403 (CSRF)                -> BUKAN bukti apa pun; session masih hidup dan masih dapat dipakai.
* revoke ganda              -> aman diulang, jadi retry dari klien tidak berbahaya.

Perilaku klien atas ketidakpastian jaringan diuji di tests/browser_logout_failure.cjs.
"""

import sqlite3
from contextlib import closing
from unittest import TestCase

import test_production as production_tests


class SessionLogoutEvidenceTest(TestCase):
    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post

    def login(self):
        response = self.client.post('/api/session', json={'api_key': self.admin['api_key']})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers.pop('X-API-Key', None)
        return self.client.cookies.get('beeloft_csrf')

    def sessions(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('SELECT COUNT(*) FROM browser_sessions').fetchone()[0]

    def test_successful_logout_revokes_the_session_and_clears_both_cookies(self):
        csrf = self.login()
        response = self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual((response.status_code, response.json()), (200, {'status': 'signed_out'}))
        cleared = response.headers.get_list('set-cookie')
        self.assertTrue(any(value.startswith('beeloft_session=') for value in cleared))
        self.assertTrue(any(value.startswith('beeloft_csrf=') for value in cleared))
        self.assertEqual(self.sessions(), 0)
        self.assertEqual(self.client.get('/api/me').status_code, 401)

    def test_csrf_rejection_is_not_evidence_that_the_session_ended(self):
        """403 tidak boleh diperlakukan sebagai logout sukses: session masih hidup."""
        csrf = self.login()
        denied = self.client.post('/api/session/logout')
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.sessions(), 1)
        # Session masih dapat dipakai sepenuhnya, termasuk untuk menulis.
        self.assertEqual(self.client.get('/api/me').json()['id'], self.admin['id'])
        created = self.client.post('/api/products',
            json={'sku': 'LOGOUT-CSRF', 'name': 'Masih aktif', 'color': '', 'size': ''},
            headers={'Idempotency-Key': 'logout-csrf-probe', 'X-CSRF-Token': csrf})
        self.assertEqual(created.status_code, 201, created.text)
        # Percobaan ulang dengan token yang benar baru mencabutnya.
        retried = self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(self.sessions(), 0)

    def test_logout_on_an_already_revoked_session_answers_401(self):
        """Klien memakai 401 sebagai bukti sah bahwa session sudah tidak aktif."""
        csrf = self.login()
        token = self.client.cookies.get('beeloft_session')
        self.app.state.store.revoke_browser_session(token)
        self.assertEqual(self.sessions(), 0)
        self.assertEqual(self.client.get('/api/me').status_code, 401)
        repeated = self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual(repeated.status_code, 401)

    def test_logout_on_an_expired_session_answers_401(self):
        csrf = self.login()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""UPDATE browser_sessions SET created_at='1999-01-01T00:00:00+00:00',
                expires_at='2000-01-01T00:00:00+00:00'""")
        expired = self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual(expired.status_code, 401)

    def test_revoking_the_same_token_twice_is_safe_for_client_retries(self):
        """Server sudah mencabut lalu responsnya hilang: retry klien tidak boleh meledak."""
        self.login()
        token = self.client.cookies.get('beeloft_session')
        store = self.app.state.store
        store.revoke_browser_session(token)
        store.revoke_browser_session(token)
        self.assertEqual(self.sessions(), 0)

    def test_one_session_logout_leaves_other_sessions_untouched(self):
        """Logout hanya menyangkut session Beeloft di perangkat ini."""
        store = self.app.state.store
        _, other_token, _ = store.create_browser_session(self.operator['api_key'])
        csrf = self.login()
        self.assertEqual(self.sessions(), 2)
        self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual(self.sessions(), 1)
        self.assertEqual(store.authenticate_browser_session(other_token)['id'], self.operator['id'])
