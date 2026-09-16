"""Regresi P1: satu idempotency key tidak boleh menghasilkan efek samping bisnis kedua.

Kasus yang dilaporkan: akun A memulai write, hasilnya belum pasti dan draft tetap dapat dipulihkan,
tab lain menukar session browser bersama ke akun B, lalu tab semula mengulang transaksi A. Sebelum
perbaikan ini receipt idempotency disimpan dengan primary key (actor_id, key) dan dicari dengan
`WHERE actor_id=? AND key=?`, sehingga retry oleh akun B tidak menemukan receipt milik A dan
menjalankan mutasi bisnis untuk kedua kalinya.

Invarian yang diuji di sini:
  I1 satu key mengikat paling banyak satu transaksi logis pada seluruh database
  I2 satu key menghasilkan paling banyak satu efek samping bisnis, apa pun akun yang retry
  I3 akun asli + key sama + payload sama  -> replay byte-identical, tanpa event audit baru
  I4 akun asli + key sama + payload beda  -> 409, tanpa mutasi
  I5 akun berbeda + key milik akun lain   -> 403, tanpa mutasi
  I6 kegagalan yang rollback tidak meninggalkan receipt, key yang sama masih bisa dipakai
  I7 akun nonaktif ditolak 401 lebih dahulu
  I8 atribusi audit tetap menunjuk akun yang benar-benar melakukan mutasi
"""
import sqlite3
import unittest
from contextlib import closing

from beeloft.store import Store

import test_production as production_tests


class IdempotencyActorBindingTest(unittest.TestCase):
    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post
    order = production_tests.ProductionTest.order
    move = production_tests.ProductionTest.move
    detail = production_tests.ProductionTest.detail

    # helpers -----------------------------------------------------------------

    def movements(self, order):
        response = self.client.get(f'/api/orders/{order["id"]}/movements')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def query(self, sql, *parameters):
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(sql, parameters).fetchall()]

    def receipts(self, key):
        return self.query('SELECT key,actor_id FROM requests WHERE key=?', key)

    def audit(self, key):
        return self.query('SELECT actor_id,operation FROM audit_events WHERE request_key=?', key)

    def login(self, api_key):
        """Menukar API key menjadi session browser. Cookie jar dipakai bersama seluruh tab."""
        response = self.client.post('/api/session', json={'api_key': api_key})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def session_move(self, line, source, target, quantity, key, status):
        response = self.client.post('/api/movements',
            json={'line_id': line, 'from_stage': source, 'to_stage': target,
                  'quantity': quantity, 'reason': ''},
            headers={'Idempotency-Key': key,
                     'X-CSRF-Token': self.client.cookies.get('beeloft_csrf')})
        self.assertEqual(response.status_code, status, response.text)
        return response

    # I3 ----------------------------------------------------------------------

    def test_same_actor_same_key_same_payload_replays_the_first_result(self):
        order = self.order(100)
        line = order['lines'][0]['id']
        first = self.move(line, 'planned', 'cutting', 30, key='replay-same',
                          api_key=self.operator['api_key'])
        replay = self.move(line, 'planned', 'cutting', 30, key='replay-same',
                           api_key=self.operator['api_key'])
        self.assertEqual(replay, first)
        self.assertEqual(len(self.movements(order)), 1)
        self.assertEqual(self.detail(order)['lines'][0]['balances']['cutting'], 30)
        # Replay tidak menambah atribusi audit baru.
        events = self.audit('replay-same')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['actor_id'], self.operator['id'])

    # I4 ----------------------------------------------------------------------

    def test_same_actor_same_key_different_payload_is_rejected_with_conflict(self):
        order = self.order(100)
        line = order['lines'][0]['id']
        self.move(line, 'planned', 'cutting', 30, key='payload-conflict',
                  api_key=self.operator['api_key'])
        self.move(line, 'planned', 'cutting', 31, key='payload-conflict',
                  api_key=self.operator['api_key'], status=409)
        self.assertEqual(len(self.movements(order)), 1)
        self.assertEqual(self.detail(order)['lines'][0]['balances']['cutting'], 30)

    # I5 + I2 -----------------------------------------------------------------

    def test_other_actor_replaying_a_key_cannot_create_a_second_mutation(self):
        """Akun kedua di sini berperan admin, jadi role-nya memang mengizinkan perpindahan.

        Penolakan harus datang dari pemilikan key, bukan dari role, supaya invarian benar-benar
        teruji.
        """
        order = self.order(100)
        line = order['lines'][0]['id']
        original = self.move(line, 'planned', 'cutting', 30, key='cross-actor',
                             api_key=self.operator['api_key'])
        # Payload identik, akun berbeda.
        self.move(line, 'planned', 'cutting', 30, key='cross-actor',
                  api_key=self.admin['api_key'], status=403)
        # Payload berbeda, akun berbeda: pemilikan diperiksa lebih dahulu, tetap 403.
        self.move(line, 'planned', 'cutting', 40, key='cross-actor',
                  api_key=self.admin['api_key'], status=403)
        # Akun ketiga tanpa hak tulis tetap tidak dapat menyentuh key tersebut.
        self.move(line, 'planned', 'cutting', 30, key='cross-actor',
                  api_key=self.viewer['api_key'], status=403)
        self.assertEqual(len(self.movements(order)), 1)
        self.assertEqual(self.detail(order)['lines'][0]['balances']['cutting'], 30)
        self.assertEqual(self.receipts('cross-actor'), [{'key': 'cross-actor',
                                                         'actor_id': self.operator['id']}])
        self.assertEqual([event['actor_id'] for event in self.audit('cross-actor')],
                         [self.operator['id']])
        # Akun pencatat asli tetap dapat mengambil hasilnya.
        self.assertEqual(self.move(line, 'planned', 'cutting', 30, key='cross-actor',
                                   api_key=self.operator['api_key']), original)

    # kasus yang dilaporkan ---------------------------------------------------

    def test_session_switched_in_another_tab_cannot_settle_the_pending_transaction(self):
        order = self.order(100)
        line = order['lines'][0]['id']
        self.client.headers.pop('X-API-Key', None)

        # Tab 1: akun A mengirim write; server commit tetapi klien kehilangan responsnya.
        self.login(self.operator['api_key'])
        self.session_move(line, 'planned', 'cutting', 10, 'tab-pending', 201)

        # Tab 2 pada browser yang sama: logout lalu login sebagai akun B. Cookie session dan CSRF
        # dipakai bersama seluruh tab, sedangkan draft pending bersifat per tab.
        self.client.post('/api/session/logout',
                         headers={'X-CSRF-Token': self.client.cookies.get('beeloft_csrf')})
        self.login(self.admin['api_key'])
        self.assertEqual(self.client.get('/api/me').json()['id'], self.admin['id'])

        # Tab 1 menekan "Coba ulang penyimpanan" dengan session yang sekarang milik akun B.
        self.session_move(line, 'planned', 'cutting', 10, 'tab-pending', 403)

        self.assertEqual(len(self.movements(order)), 1)
        self.assertEqual(self.detail(order)['lines'][0]['balances']['cutting'], 10)
        self.assertEqual(self.receipts('tab-pending'), [{'key': 'tab-pending',
                                                         'actor_id': self.operator['id']}])
        self.assertEqual([event['actor_id'] for event in self.audit('tab-pending')],
                         [self.operator['id']])

        # Setelah masuk kembali sebagai akun pencatat asli, retry menghasilkan replay.
        self.client.post('/api/session/logout',
                         headers={'X-CSRF-Token': self.client.cookies.get('beeloft_csrf')})
        self.login(self.operator['api_key'])
        self.session_move(line, 'planned', 'cutting', 10, 'tab-pending', 201)
        self.assertEqual(len(self.movements(order)), 1)

    # I7 ----------------------------------------------------------------------

    def test_disabled_or_unauthorised_originating_actor_cannot_produce_a_second_mutation(self):
        order = self.order(100)
        line = order['lines'][0]['id']
        self.move(line, 'planned', 'cutting', 20, key='revoked-origin',
                  api_key=self.operator['api_key'])
        self.app.state.store.disable_user(self.operator['id'])
        # Akun nonaktif ditolak 401 sebelum pemilikan key maupun payload diperiksa.
        self.move(line, 'planned', 'cutting', 20, key='revoked-origin',
                  api_key=self.operator['api_key'], status=401)
        # Akun lain yang masih aktif tidak boleh menyelesaikan transaksi milik akun nonaktif itu.
        self.move(line, 'planned', 'cutting', 20, key='revoked-origin',
                  api_key=self.admin['api_key'], status=403)
        self.assertEqual(len(self.movements(order)), 1)
        self.assertEqual(self.detail(order)['lines'][0]['balances']['cutting'], 20)

    def test_role_downgrade_still_blocks_replay_for_the_original_actor(self):
        order = self.order(100)
        line = order['lines'][0]['id']
        self.move(line, 'planned', 'cutting', 15, key='role-downgrade',
                  api_key=self.operator['api_key'])
        with self.app.state.store.transaction(write=True) as db:
            db.execute('UPDATE users SET role=? WHERE id=?', ('viewer', self.operator['id']))
        self.move(line, 'planned', 'cutting', 15, key='role-downgrade',
                  api_key=self.operator['api_key'], status=403)
        self.assertEqual(len(self.movements(order)), 1)

    # I6 ----------------------------------------------------------------------

    def test_retry_after_transient_failure_succeeds_with_the_same_key(self):
        order = self.order(100)
        line = order['lines'][0]['id']
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.execute("CREATE TRIGGER fail_once BEFORE INSERT ON movements "
                       "BEGIN SELECT RAISE(ABORT,'write failed'); END")
        self.move(line, 'planned', 'cutting', 25, key='transient',
                  api_key=self.operator['api_key'], status=409)
        self.assertEqual(self.receipts('transient'), [])
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.execute('DROP TRIGGER fail_once')
        self.move(line, 'planned', 'cutting', 25, key='transient',
                  api_key=self.operator['api_key'])
        self.assertEqual(self.detail(order)['lines'][0]['balances']['cutting'], 25)
        self.assertEqual(self.receipts('transient'), [{'key': 'transient',
                                                       'actor_id': self.operator['id']}])
        # Kegagalan transien tidak boleh membuat akun lain berhak atas key tersebut.
        self.move(line, 'planned', 'cutting', 25, key='transient',
                  api_key=self.admin['api_key'], status=403)
        self.assertEqual(len(self.movements(order)), 1)

    # I1 di tingkat schema ----------------------------------------------------

    def test_schema_makes_the_request_key_globally_unique(self):
        order = self.order(100)
        line = order['lines'][0]['id']
        self.move(line, 'planned', 'cutting', 10, key='schema-guard',
                  api_key=self.operator['api_key'])
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO requests(key,actor_id,fingerprint,response,created_at) '
                           'VALUES(?,?,?,?,?)',
                           ('schema-guard', self.admin['id'], 'x', '{}', '2026-01-01T00:00:00+00:00'))
        self.assertEqual(len(self.receipts('schema-guard')), 1)


class RequestKeyMigrationTest(unittest.TestCase):
    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post
    order = production_tests.ProductionTest.order
    move = production_tests.ProductionTest.move

    OLD_TABLE = '''CREATE TABLE requests (
        actor_id TEXT NOT NULL REFERENCES users(id),
        key TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        response TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(actor_id, key)
    ) STRICT'''

    def test_migration_keeps_the_originating_receipt_and_archives_the_duplicate(self):
        """Database yang sudah terkena bug ini dapat memuat satu key di beberapa akun.

        Migrasi tidak boleh gagal dan tidak boleh membuang data: receipt paling awal dipertahankan
        sebagai pemilik key, sisanya diarsipkan supaya tetap dapat diaudit.
        """
        order = self.order(100)
        self.move(order['lines'][0]['id'], 'planned', 'cutting', 10, key='kept-across-migration',
                  api_key=self.operator['api_key'])
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.execute('PRAGMA foreign_keys=ON')
            existing = db.execute('SELECT actor_id,key,fingerprint,response,created_at '
                                  'FROM requests').fetchall()
            db.execute('DROP TABLE requests')
            db.execute(self.OLD_TABLE)
            db.executemany('INSERT INTO requests VALUES(?,?,?,?,?)', existing)
            # Duplikat historis lintas akun, persis jejak yang ditinggalkan bug ini.
            db.execute('INSERT INTO requests VALUES(?,?,?,?,?)',
                       (self.operator['id'], 'legacy-duplicate', 'fingerprint',
                        '{"origin":"operator"}', '2026-01-01T00:00:00+00:00'))
            db.execute('INSERT INTO requests VALUES(?,?,?,?,?)',
                       (self.admin['id'], 'legacy-duplicate', 'fingerprint',
                        '{"origin":"admin"}', '2026-01-02T00:00:00+00:00'))
            db.execute('PRAGMA user_version=53')

        Store(self.path)
        Store(self.path)

        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 54)
            kept = db.execute('SELECT actor_id,response FROM requests '
                              'WHERE key=?', ('legacy-duplicate',)).fetchall()
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]['actor_id'], self.operator['id'])
            self.assertEqual(kept[0]['response'], '{"origin":"operator"}')
            archived = db.execute('SELECT key,actor_id,response,detected_at '
                                  'FROM request_key_conflicts').fetchall()
            self.assertEqual(len(archived), 1)
            self.assertEqual(archived[0]['key'], 'legacy-duplicate')
            self.assertEqual(archived[0]['actor_id'], self.admin['id'])
            self.assertEqual(archived[0]['response'], '{"origin":"admin"}')
            self.assertTrue(archived[0]['detected_at'].endswith('+00:00'))
            # Receipt sah yang sudah ada sebelumnya tidak hilang.
            self.assertEqual(db.execute('SELECT COUNT(*) FROM requests '
                                        'WHERE key=?', ('kept-across-migration',)).fetchone()[0], 1)
            # Arsip bersifat immutable.
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM request_key_conflicts')

        # Setelah migrasi, invarian berlaku untuk key historis tersebut.
        self.assertEqual(len(self.query_requests('legacy-duplicate')), 1)

    def query_requests(self, key):
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            return db.execute('SELECT key FROM requests WHERE key=?', (key,)).fetchall()
