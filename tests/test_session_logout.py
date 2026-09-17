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



class LogoutWithoutABrowserCookieTest(TestCase):
    """Regresi P3-C: logout tanpa cookie session tidak boleh menjadi HTTP 500.

    Autentikasi bersama boleh lolos lewat `X-API-Key` tanpa cookie sama sekali, tetapi endpoint
    logout membaca `request.cookies['beeloft_session']` langsung sehingga klien API key yang sah
    dijawab 500 oleh `KeyError`.

    Kontrak yang ditegakkan di sini:

    * API key sah tanpa cookie      -> 200 `signed_out` sebagai no-op; API key tetap sah.
    * API key sah dengan cookie     -> 200 no-op; cookie yang tidak meng-autentikasi request tidak
                                       dicabut, sehingga API key tidak dapat mengakhiri session
                                       browser akun mana pun tanpa lewat pemeriksaan CSRF.
    * Cookie sah + CSRF benar       -> session dicabut dan kedua cookie dihapus.
    * Cookie sah + CSRF salah/hilang-> 403, session tetap hidup (pengamanan existing).
    * Tanpa kredensial sah          -> 401.
    * Kegagalan penyimpanan         -> bukan 200; logout gagal tidak boleh terlihat berhasil.
    """

    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post

    def sessions(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('SELECT COUNT(*) FROM browser_sessions').fetchone()[0]

    def tokens(self):
        with closing(sqlite3.connect(self.path)) as db:
            return {row[0] for row in db.execute('SELECT token_hash FROM browser_sessions')}

    def api_logout(self, key=None, **kwargs):
        """Logout memakai header API key saja; TestClient tidak menyimpan cookie apa pun di sini."""
        headers = {'X-API-Key': key or self.admin['api_key']}
        headers.update(kwargs.pop('headers', {}))
        return self.client.post('/api/session/logout', headers=headers, **kwargs)

    def login(self, key=None):
        response = self.client.post('/api/session',
                                    json={'api_key': key or self.admin['api_key']})
        self.assertEqual(response.status_code, 200, response.text)
        return self.client.cookies.get('beeloft_csrf')

    # ------------------------------------------------------------------ API key tanpa cookie
    def test_api_key_without_a_cookie_answers_200_instead_of_500(self):
        self.client.headers.pop('X-API-Key', None)
        self.assertEqual(self.client.cookies.get('beeloft_session'), None)
        response = self.api_logout()
        self.assertEqual((response.status_code, response.json()),
                         (200, {'status': 'signed_out'}), response.text)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        # Tidak ada session yang dibuat maupun dicabut sebagai efek samping.
        self.assertEqual(self.sessions(), 0)

    def test_repeated_api_key_logouts_stay_a_safe_no_op(self):
        self.client.headers.pop('X-API-Key', None)
        for attempt in range(4):
            with self.subTest(attempt=attempt):
                response = self.api_logout()
                self.assertEqual((response.status_code, response.json()),
                                 (200, {'status': 'signed_out'}))
        self.assertEqual(self.sessions(), 0)

    def test_the_no_op_logout_does_not_revoke_the_api_key(self):
        """Logout bukan mekanisme pencabutan API key."""
        self.client.headers.pop('X-API-Key', None)
        self.assertEqual(self.api_logout().status_code, 200)
        identity = self.client.get('/api/me', headers={'X-API-Key': self.admin['api_key']})
        self.assertEqual(identity.status_code, 200, identity.text)
        self.assertEqual(identity.json()['id'], self.admin['id'])
        # Kunci yang sama masih dapat menulis maupun logout lagi.
        created = self.post('/api/products', {'sku': 'APIKEY-ALIVE', 'name': 'Masih sah',
                                              'color': '', 'size': ''},
                            api_key=self.admin['api_key'])
        self.assertEqual(created['sku'], 'APIKEY-ALIVE')
        self.assertEqual(self.api_logout().status_code, 200)

    def test_every_role_may_call_the_no_op_logout(self):
        self.client.headers.pop('X-API-Key', None)
        for account in (self.admin, self.operator, self.viewer):
            with self.subTest(role=account['role']):
                response = self.api_logout(account['api_key'])
                self.assertEqual((response.status_code, response.json()),
                                 (200, {'status': 'signed_out'}))
        self.assertEqual(self.sessions(), 0)

    def test_the_no_op_logout_does_not_clear_cookies_it_did_not_revoke(self):
        """Tidak ada Set-Cookie penghapus pada jalur no-op: tidak ada session yang diakhiri."""
        self.client.headers.pop('X-API-Key', None)
        response = self.api_logout()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get_list('set-cookie'), [])

    # ------------------------------------------------------------------ kredensial tidak sah
    def test_an_invalid_api_key_without_a_cookie_is_still_401(self):
        self.client.headers.pop('X-API-Key', None)
        response = self.api_logout('kunci-yang-tidak-ada')
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(self.sessions(), 0)

    def test_no_credentials_at_all_is_still_401(self):
        self.client.headers.pop('X-API-Key', None)
        response = self.client.post('/api/session/logout')
        self.assertEqual(response.status_code, 401, response.text)
        self.assertIn('X-API-Key', response.json()['detail'])
        self.assertEqual(self.sessions(), 0)

    def test_an_inactive_account_key_is_refused(self):
        self.client.headers.pop('X-API-Key', None)
        extra = self.app.state.store.provision_user('Sementara', 'operator')
        with self.app.state.store.transaction(write=True) as db:
            db.execute('UPDATE users SET active=0 WHERE id=?', (extra['id'],))
        self.assertEqual(self.api_logout(extra['api_key']).status_code, 401)

    # ------------------------------------------------------------------ cookie session
    def test_a_valid_cookie_still_revokes_the_session_and_clears_both_cookies(self):
        csrf = self.login()
        self.client.headers.pop('X-API-Key', None)
        response = self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual((response.status_code, response.json()), (200, {'status': 'signed_out'}))
        cleared = response.headers.get_list('set-cookie')
        self.assertTrue(any(value.startswith('beeloft_session=') for value in cleared))
        self.assertTrue(any(value.startswith('beeloft_csrf=') for value in cleared))
        self.assertEqual(self.sessions(), 0)
        self.assertEqual(self.client.get('/api/me').status_code, 401)

    def test_a_missing_or_wrong_csrf_token_is_still_refused(self):
        csrf = self.login()
        self.client.headers.pop('X-API-Key', None)
        missing = self.client.post('/api/session/logout')
        self.assertEqual(missing.status_code, 403, missing.text)
        self.assertEqual(self.sessions(), 1)
        wrong = self.client.post('/api/session/logout',
                                 headers={'X-CSRF-Token': 'token-yang-salah'})
        self.assertEqual(wrong.status_code, 403, wrong.text)
        self.assertEqual(self.sessions(), 1)
        # Session masih dapat dipakai, jadi 403 memang bukan bukti logout.
        self.assertEqual(self.client.get('/api/me').json()['id'], self.admin['id'])
        self.assertEqual(self.client.post('/api/session/logout',
                                          headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.assertEqual(self.sessions(), 0)

    def test_a_revoked_or_expired_cookie_is_still_401(self):
        csrf = self.login()
        self.client.headers.pop('X-API-Key', None)
        token = self.client.cookies.get('beeloft_session')
        self.app.state.store.revoke_browser_session(token)
        revoked = self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual(revoked.status_code, 401, revoked.text)
        csrf = self.login()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""UPDATE browser_sessions SET created_at='1999-01-01T00:00:00+00:00',
                expires_at='2000-01-01T00:00:00+00:00'""")
        expired = self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual(expired.status_code, 401, expired.text)

    # ------------------------------------------- API key dan cookie pada satu request
    def test_an_api_key_beside_its_own_cookie_does_not_revoke_that_session(self):
        """Prioritas kredensial: API key menang, jadi tidak ada session yang meng-autentikasi.

        Pencabutan session browser selalu menuntut bukti kepemilikan token CSRF-nya. Request yang
        lolos lewat API key tidak pernah memberikan bukti itu, jadi cookie yang menempel padanya
        dibiarkan -- termasuk cookie milik akun yang sama.
        """
        self.login()
        before = self.tokens()
        self.assertEqual(len(before), 1)
        self.assertIsNotNone(self.client.cookies.get('beeloft_session'))
        response = self.client.post('/api/session/logout',
                                    headers={'X-API-Key': self.admin['api_key']})
        self.assertEqual((response.status_code, response.json()), (200, {'status': 'signed_out'}))
        self.assertEqual(self.tokens(), before, 'session tidak boleh dicabut tanpa bukti CSRF')
        # Session cookie-nya masih hidup dan masih milik akun yang sama.
        self.client.headers.pop('X-API-Key', None)
        self.assertEqual(self.client.get('/api/me').json()['id'], self.admin['id'])

    def test_an_api_key_never_revokes_another_accounts_session(self):
        """Cookie akun lain yang menempel pada request ber-API-key tidak boleh dicabut."""
        self.login(self.operator['api_key'])
        operator_token = self.client.cookies.get('beeloft_session')
        before = self.tokens()
        response = self.client.post('/api/session/logout',
                                    headers={'X-API-Key': self.admin['api_key']})
        self.assertEqual((response.status_code, response.json()), (200, {'status': 'signed_out'}))
        self.assertEqual(self.tokens(), before)
        self.assertEqual(self.app.state.store
                         .authenticate_browser_session(operator_token)['id'],
                         self.operator['id'])

    def test_the_cookie_path_still_revokes_only_the_session_that_authenticated(self):
        store = self.app.state.store
        _, other_token, _ = store.create_browser_session(self.operator['api_key'])
        csrf = self.login()
        self.client.headers.pop('X-API-Key', None)
        self.assertEqual(self.sessions(), 2)
        self.assertEqual(self.client.post('/api/session/logout',
                                          headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.assertEqual(self.sessions(), 1)
        self.assertEqual(store.authenticate_browser_session(other_token)['id'],
                         self.operator['id'])

    def test_a_no_op_logout_leaves_every_other_session_active(self):
        store = self.app.state.store
        _, first, _ = store.create_browser_session(self.admin['api_key'])
        _, second, _ = store.create_browser_session(self.operator['api_key'])
        self.client.headers.pop('X-API-Key', None)
        self.assertEqual(self.sessions(), 2)
        self.assertEqual(self.api_logout().status_code, 200)
        self.assertEqual(self.sessions(), 2)
        self.assertEqual(store.authenticate_browser_session(first)['id'], self.admin['id'])
        self.assertEqual(store.authenticate_browser_session(second)['id'], self.operator['id'])

    # ------------------------------------------------------------------ kegagalan penyimpanan
    def test_a_storage_failure_is_not_reported_as_a_successful_logout(self):
        csrf = self.login()
        self.client.headers.pop('X-API-Key', None)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_revoke BEFORE DELETE ON browser_sessions
                BEGIN SELECT RAISE(ABORT,'revoke ditolak'); END""")
        response = self.client.post('/api/session/logout', headers={'X-CSRF-Token': csrf})
        self.assertNotEqual(response.status_code, 200, response.text)
        self.assertGreaterEqual(response.status_code, 400)
        # Session memang masih hidup, jadi klien tidak boleh menutup ruang kerjanya.
        self.assertEqual(self.sessions(), 1)
        self.assertEqual(self.client.get('/api/me').json()['id'], self.admin['id'])
        with self.app.state.store.transaction(write=True) as db:
            db.execute('DROP TRIGGER fail_revoke')
        self.assertEqual(self.client.post('/api/session/logout',
                                          headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.assertEqual(self.sessions(), 0)

    # ------------------------------------------------------------------ interaksi P1/P2
    def test_the_actor_binding_header_still_applies_to_logout(self):
        """Binding aktor P1 tidak melemah: pernyataan akun yang salah tetap ditolak."""
        self.client.headers.pop('X-API-Key', None)
        refused = self.api_logout(headers={'X-Beeloft-Actor': self.operator['id']})
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertIn('berpindah', refused.json()['detail'])
        accepted = self.api_logout(headers={'X-Beeloft-Actor': self.admin['id']})
        self.assertEqual(accepted.status_code, 200, accepted.text)

    def test_logout_needs_no_idempotency_key(self):
        """Logout bukan pencatatan: kontraknya tidak berubah menjadi transaksi ber-key."""
        self.client.headers.pop('X-API-Key', None)

        def receipts():
            with closing(sqlite3.connect(self.path)) as db:
                return (db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],
                        db.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0])

        before = receipts()
        self.assertEqual(self.api_logout().status_code, 200)
        self.assertEqual(receipts(), before)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE operation "
                                        "LIKE '%logout%'").fetchone()[0], 0)
