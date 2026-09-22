import json
import re
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from beeloft.api import create_app

# Kontrak OpenAPI tersimpan drift diam-diam setiap kali versi naik atau endpoint
# berubah tanpa dump ulang; issue #37 menemukan docs/openapi.json tertinggal satu
# versi penuh. Test ini memblok drift tersebut sebelum mencapai main.
REPO = Path(__file__).resolve().parent.parent
CONTRACT = REPO / "docs" / "openapi.json"
PYPROJECT = REPO / "pyproject.toml"


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


class VersionMetadataConsistencyTest(unittest.TestCase):
    """Tiga tempat versi diumumkan harus selalu bergerak bersama.

    `test_stored_version_matches_runtime` di atas hanya mengikat dua dari tiga: dokumen
    tersimpan dan runtime. Versi paket tidak pernah ikut diperiksa, dan itu memang yang
    terlewat: A2 (PR #90) menaikkan `pyproject.toml` ke 0.100.0 sementara
    `beeloft/api.py` dan `docs/openapi.json` tertinggal di 0.99.0, sehingga rilis paket
    dan kontrak API menyebut versi yang berbeda tanpa satu pun test gagal. A3 memperbaiki
    metadata itu ke 0.101.0 dan menambahkan pengikat ketiganya di sini, supaya milestone
    visual berikutnya tidak bisa lagi menaikkan hanya salah satunya.
    """

    def setUp(self):
        self.package = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
        with TemporaryDirectory() as folder:
            self.runtime = create_app(Path(folder) / "version.sqlite3").version
        self.stored = json.loads(CONTRACT.read_text(encoding="utf-8"))["info"]["version"]

    def test_package_runtime_and_stored_contract_state_one_version(self):
        self.assertEqual(
            {"pyproject.toml": self.package, "FastAPI app.version": self.runtime,
             "docs/openapi.json": self.stored},
            {"pyproject.toml": self.package, "FastAPI app.version": self.package,
             "docs/openapi.json": self.package},
            "versi paket, runtime dan kontrak tersimpan tidak sama; naikkan ketiganya lalu "
            "jalankan python scripts/regenerate_openapi.py")

    def test_every_declared_version_is_a_full_release_triple(self):
        """`0.101` dan `0.101.0` akan dibandingkan sebagai string, jadi bentuknya dikunci."""
        for name, value in (("pyproject.toml", self.package), ("FastAPI app.version", self.runtime),
                            ("docs/openapi.json", self.stored)):
            with self.subTest(source=name):
                self.assertRegex(value, r"^\d+\.\d+\.\d+$", f"{name} menyebut `{value}`")


if __name__ == "__main__":
    unittest.main()
