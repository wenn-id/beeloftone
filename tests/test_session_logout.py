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



class SessionIdentityAfterSwitchTest(TestCase):
    """Fakta server yang mendasari kontrak identitas pada logout gagal.

    Klien memutuskan boleh atau tidaknya ruang kerja dipertahankan dengan membandingkan identitas
    yang dijawab `/api/me` terhadap akun yang membuka ruang kerja itu. Perbandingan tersebut hanya
    bermakna bila server benar-benar menjawab identitas pengganti setelah cookie session ditukar,
    dan bila logout yang gagal tidak menyentuh session siapa pun.
    """

    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post

    def login(self, key):
        response = self.client.post('/api/session', json={'api_key': key})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers.pop('X-API-Key', None)
        return self.client.cookies.get('beeloft_csrf')

    def sessions(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('SELECT COUNT(*) FROM browser_sessions').fetchone()[0]

    def test_me_reports_the_replacement_identity_after_a_session_switch(self):
        self.login(self.operator['api_key'])
        self.assertEqual(self.client.get('/api/me').json()['id'], self.operator['id'])
        # Tab lain menukar session bersama ke akun lain pada origin yang sama.
        csrf = self.login(self.admin['api_key'])
        identity = self.client.get('/api/me').json()
        self.assertEqual(identity['id'], self.admin['id'])
        self.assertNotEqual(identity['id'], self.operator['id'])
        # Identitasnya lengkap, jadi peringatan klien dapat menyebut akunnya.
        self.assertEqual(set(identity), {'id', 'name', 'role'})
        self.assertEqual((identity['name'], identity['role']), (self.admin['name'], 'admin'))
        self.assertEqual(self.sessions(), 2, 'session akun sebelumnya tidak dicabut oleh login baru')
        # Logout yang gagal karena CSRF tidak mencabut session siapa pun.
        self.assertEqual(self.client.post('/api/session/logout').status_code, 403)
        self.assertEqual(self.sessions(), 2)
        self.assertEqual(self.client.get('/api/me').json()['id'], self.admin['id'])
        # Logout yang berhasil hanya mencabut session yang sedang dipegang browser ini.
        self.assertEqual(self.client.post('/api/session/logout',
                                          headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.assertEqual(self.sessions(), 1)

    def test_write_under_a_switched_session_is_refused_before_any_mutation(self):
        """Binding aktor P1 tetap menolak pencatatan milik akun lama; ini tidak boleh melemah."""
        self.login(self.operator['api_key'])
        csrf = self.login(self.admin['api_key'])
        refused = self.client.post('/api/products',
            json={'sku': 'SWITCH-GUARD', 'name': 'Tidak boleh tercatat', 'color': '', 'size': ''},
            headers={'Idempotency-Key': 'switched-actor', 'X-CSRF-Token': csrf,
                     'X-Beeloft-Actor': self.operator['id']})
        self.assertEqual(refused.status_code, 403)
        self.assertIn('berpindah', refused.json()['detail'])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM products WHERE sku='SWITCH-GUARD'")
                             .fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests WHERE key='switched-actor'")
                             .fetchone()[0], 0)
