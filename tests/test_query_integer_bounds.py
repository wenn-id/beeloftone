import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from beeloft.api import SQLITE_MAX_INTEGER, create_app

# 2**63: satu di luar integer signed 64-bit SQLite. Nilai ini memicu OverflowError saat binding
# parameter OFFSET/cursor, yang sebelumnya menjawab HTTP 500 (issue #33).
OVERFLOWED = SQLITE_MAX_INTEGER + 1


class QueryIntegerBoundsTest(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "test.sqlite3"
        self.app = create_app(self.path)
        self.client = TestClient(self.app).__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.admin = self.app.state.store.provision_user("Pemilik", "admin")
        self.client.headers["X-API-Key"] = self.admin["api_key"]

    def cursor_endpoints(self):
        """Seluruh endpoint GET yang menerima offset atau before, diambil dari skema OpenAPI.

        Diambil dari skema, bukan ditarik manual, supaya endpoint baru yang membawa parameter
        offset/before otomatis ikut diperiksa dan tidak lolos seperti kedua endpoint contoh pada
        audit issue #33.
        """
        schema = self.app.openapi()
        for path, methods in schema["paths"].items():
            for method, operation in methods.items():
                if method.lower() != "get":
                    continue
                names = sorted({p["name"] for p in operation.get("parameters", [])
                                if p.get("in") == "query" and p["name"] in ("offset", "before")})
                if names:
                    # Parameter path disubstitusi placeholder: validasi query parameter terjadi
                    # sebelum handler, jadi jawaban 422 tidak bergantung pada record yang ada.
                    yield re.sub(r"\{[^}]+\}", "probe", path), names

    def test_oversized_offset_and_before_is_422_not_500(self):
        routes = list(self.cursor_endpoints())
        # Jika daftar kosong, berarti enumerasi skema rusak dan perlindungan ini diam-diam hilang.
        self.assertGreater(len(routes), 60, "skema harus menemukan puluhan endpoint offset/before")
        for path, names in routes:
            for name in names:
                response = self.client.get(f"{path}?{name}={OVERFLOWED}")
                self.assertEqual(response.status_code, 422,
                                 f"{path}?{name}={OVERFLOWED} menjawab {response.status_code}, bukan 422")

    def test_signed_64bit_boundary_is_accepted(self):
        # Tepat pada batas atas masih integer valid bagi SQLite: harus ditangani tanpa HTTP 500.
        for path, name in [("/api/products", "offset"),
                           ("/api/orders", "offset"),
                           ("/api/materials", "offset"),
                           ("/api/ai/investigations", "before"),
                           ("/api/audit-events", "before")]:
            response = self.client.get(f"{path}?{name}={SQLITE_MAX_INTEGER}")
            self.assertEqual(response.status_code, 200,
                             f"{path}?{name}={SQLITE_MAX_INTEGER} menjawab {response.status_code}")

    def test_negative_and_zero_bounds_still_hold(self):
        self.assertEqual(self.client.get("/api/products?offset=-1").status_code, 422)
        self.assertEqual(self.client.get("/api/products?offset=0").status_code, 200)
        self.assertEqual(self.client.get("/api/ai/investigations?before=0").status_code, 422)
        self.assertEqual(self.client.get("/api/ai/investigations?before=1").status_code, 200)


if __name__ == "__main__":
    unittest.main()
