#!/usr/bin/env python3
"""Regenerasi docs/openapi.json dari runtime FastAPI yang terinstal.

Kontrak tersimpan drift setiap kali versi naik atau endpoint berubah tanpa dump
ulang (issue #37). Script ini adalah langkah rilisnya; tests/test_openapi_contract.py
adalah penjaganya.

Pemakaian:  python scripts/regenerate_openapi.py
"""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from beeloft.api import create_app

REPO = Path(__file__).resolve().parent.parent
CONTRACT = REPO / "docs" / "openapi.json"


def runtime_schema():
    with TemporaryDirectory() as folder:
        # Database tidak perlu berisi data: skema dibangun dari deklarasi route,
        # bukan dari isi tabel.
        app = create_app(Path(folder) / "contract.sqlite3")
        return app.openapi()


def main():
    schema = runtime_schema()
    CONTRACT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"docs/openapi.json -> {schema['info']['version']} "
          f"({len(schema['paths'])} path, "
          f"{len(schema.get('components', {}).get('schemas', {}))} skema)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
