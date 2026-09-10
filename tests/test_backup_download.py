import sqlite3
from contextlib import closing
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from beeloft.api import create_app
import test_production


class BackupDownloadTest(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order
    move = test_production.ProductionTest.move
    detail = test_production.ProductionTest.detail

    def test_download_restores_all_records_and_does_not_change_source(self):
        order = self.order()
        self.move(order['lines'][0]['id'],'planned','cutting',20)
        self.post('/api/issues',{'line_id':order['lines'][0]['id'],'stage':'cutting','owner_id':self.operator['id'],'description':'Menunggu mesin'})
        expected = self.detail(order)
        with closing(sqlite3.connect(self.path)) as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            before = {t:db.execute('SELECT * FROM '+t).fetchall() for t in tables}
        response = self.client.get('/api/backup')
        self.assertEqual(response.status_code,200,response.text[:100])
        self.assertTrue(response.content.startswith(b'SQLite format 3\x00'))
        self.assertIn('attachment;',response.headers['content-disposition'])
        self.assertEqual(response.headers['cache-control'],'no-store')
        backup = Path(self.folder.name)/'download.sqlite3'
        backup.write_bytes(response.content)
        for path in [self.path,backup]:
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
                for table,rows in before.items():
                    self.assertEqual(db.execute('SELECT * FROM '+table).fetchall(),rows)
        with TestClient(create_app(backup)) as restored:
            self.assertEqual(restored.get('/api/orders/'+order['id'],headers={'X-API-Key':self.admin['api_key']}).json(),expected)
        self.assertNotIn(self.admin['api_key'].encode(),response.content)

    def test_only_active_admin_can_download(self):
        for account in [self.operator,self.viewer]:
            self.assertEqual(self.client.get('/api/backup',headers={'X-API-Key':account['api_key']}).status_code,403)
        self.assertEqual(self.client.get('/api/backup',headers={'X-API-Key':'bad'}).status_code,401)
        self.app.state.store.disable_user(self.admin['id'])
        self.assertEqual(self.client.get('/api/backup').status_code,401)

    def test_storage_failure_does_not_return_partial_backup(self):
        with patch.object(self.app.state.store,'backup',side_effect=OSError('Disk unavailable')):
            response = self.client.get('/api/backup')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('SQLite format',response.text)
        self.assertEqual(self.client.get('/api/backup').status_code,200)
