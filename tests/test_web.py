import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from beeloft.api import create_app


class WebTest(unittest.TestCase):
    def test_dashboard_shell_and_assets_are_served_without_exposing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(Path(folder) / "web.sqlite3")) as client:
                response = client.get("/")
                self.assertEqual(response.status_code, 200)
                self.assertIn('lang="id"', response.text)
                self.assertIn("/static/app.mjs", response.text)
                self.assertIn('<aside id="app-sidebar"', response.text)
                self.assertIn('aria-label="Navigasi utama"', response.text)
                self.assertIn('id="menu-toggle"', response.text)
                self.assertIn('aria-controls="app-sidebar"', response.text)
                self.assertIn('class="workspace-main"', response.text)
                for asset in ["app.mjs", "client.mjs", "style.css"]:
                    self.assertEqual(client.get("/static/" + asset).status_code, 200)
                self.assertEqual(client.get("/api/production-board").status_code, 401)
                self.assertEqual(client.get("/static/../schema.sql").status_code, 404)
