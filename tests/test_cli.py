import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


class CliTest(unittest.TestCase):
    def test_demo_backup_and_account_revocation(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "demo.sqlite3"

            def run(*args):
                return subprocess.run([sys.executable, "-m", "beeloft", "--db", str(database), *args],
                                      capture_output=True, text=True, encoding="utf-8")

            demo = run("demo")
            self.assertEqual(demo.returncode, 0, demo.stderr)
            credentials = json.loads(demo.stdout)
            self.assertEqual(len(credentials["users"]), 3)
            self.assertNotEqual(run("demo").returncode, 0)
            issuer="https://identity.example"
            linked=run("oidc-link","--issuer",issuer,"--subject","admin-subject",
                       "--user-id",credentials["users"][0]["id"])
            self.assertEqual(linked.returncode,0,linked.stderr)
            self.assertEqual(json.loads(linked.stdout)["subject"],"admin-subject")
            self.assertEqual(run("oidc-unlink","--issuer",issuer,"--subject","admin-subject").returncode,0)
            backup = Path(folder) / "backup.sqlite3"
            self.assertEqual(run("backup", str(backup)).returncode, 0)
            self.assertNotEqual(run("backup", str(backup)).returncode, 0)
            operator_id = credentials["users"][1]["id"]
            self.assertEqual(run("disable-user", operator_id).returncode, 0)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute("SELECT active FROM users WHERE id=?", (operator_id,)).fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 1)
            with closing(sqlite3.connect(backup)) as db:
                self.assertEqual(db.execute("SELECT active FROM users WHERE id=?", (operator_id,)).fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT SUM(quantity) FROM balances").fetchone()[0], 500)

    def test_backup_does_not_create_missing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "missing.sqlite3"
            result = subprocess.run([sys.executable, "-m", "beeloft", "--db", str(database),
                                     "backup", str(Path(folder) / "backup.sqlite3")], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"Database sumber belum ada", result.stderr)
            self.assertFalse(database.exists())
