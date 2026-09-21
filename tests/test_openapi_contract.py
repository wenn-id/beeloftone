import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from beeloft.api import create_app

# Kontrak OpenAPI tersimpan drift diam-diam setiap kali versi naik atau endpoint
# berubah tanpa dump ulang; issue #37 menemukan docs/openapi.json tertinggal satu
# versi penuh. Test ini memblok drift tersebut sebelum mencapai main.
REPO = Path(__file__).resolve().parent.parent
CONTRACT = REPO / "docs" / "openapi.json"


class StoredOpenApiContractTest(unittest.TestCase):
    def runtime_schema(self):
        with TemporaryDirectory() as folder:
            # Skema berasal dari deklarasi route, bukan isi tabel: database kosong
            # cukup dan lebih cepat daripada menghidrasi data demo.
            return create_app(Path(folder) / "contract.sqlite3").openapi()

    def test_contract_file_exists(self):
        # File hilang = regenerasi lupa di-commit, dan sisa test di bawah tidak
        # bisa memberi diagnosis yang berguna.
        self.assertTrue(CONTRACT.exists(), f"{CONTRACT} tidak ada; jalankan "
                        "python scripts/regenerate_openapi.py")

    def test_stored_version_matches_runtime(self):
        stored = json.loads(CONTRACT.read_text(encoding="utf-8"))
        runtime = self.runtime_schema()
        self.assertEqual(stored["info"]["version"], runtime["info"]["version"],
                         "info.version docs/openapi.json tertinggal dari runtime; "
                         f"jalankan python scripts/regenerate_openapi.py "
                         f"(tersimpan {stored['info']['version']}, "
                         f"runtime {runtime['info']['version']})")

    def test_stored_paths_match_runtime(self):
        stored = json.loads(CONTRACT.read_text(encoding="utf-8"))
        runtime = self.runtime_schema()
        stored_paths = set(stored["paths"])
        runtime_paths = set(runtime["paths"])
        missing = sorted(runtime_paths - stored_paths)
        extra = sorted(stored_paths - runtime_paths)
        self.assertEqual(missing, [],
                         f"path runtime tidak terdokumentasi: {missing}")
        self.assertEqual(extra, [],
                         f"path dokumen tidak ada di runtime: {extra}")


if __name__ == "__main__":
    unittest.main()
