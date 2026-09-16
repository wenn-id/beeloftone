"""Regresi keamanan StaticFiles: UNC path gaya Windows ditolak tanpa I/O ke tujuan UNC.

Referensi advisory:
  GHSA-wqp7-x3pw-xc5r / CVE-2026-48818 - SSRF dan kebocoran NTLMv2 lewat UNC path pada StaticFiles
  di Windows, diperbaiki pada Starlette 1.1.0. `StaticFiles.lookup_path()` memanggil
  `os.path.realpath` sebelum memeriksa containment; pada Windows UNC path bersifat absolut sehingga
  `os.path.join` membuang direktori yang dilayani dan `realpath` benar-benar membuka koneksi SMB ke
  host penyerang sebelum path tersebut ditolak.

Advisory lain yang masih terbuka pada rilis di bawah 1.3.1 dan ikut ditutup oleh upgrade ini:
  GHSA-86qp-5c8j-p5mr / CVE-2026-48710 (BadHost)          diperbaiki 1.0.1
  GHSA-x746-7m8f-x49c / CVE-2026-48817 (HTTPEndpoint)     diperbaiki 1.1.0
  GHSA-jp82-jpqv-5vv3 / CVE-2026-54282 (authority)        diperbaiki 1.3.0
  GHSA-82w8-qh3p-5jfq / CVE-2026-54283 (form limits)      diperbaiki 1.3.1

Tes ini berjalan di platform apa pun dan tidak pernah membuat request SMB nyata. Host uji memakai
TLD `.invalid` yang dijamin tidak dapat di-resolve (RFC 2606), dan seluruh jalur socket dipasangi
guard yang gagal keras bila ada yang mencoba menyentuh host tersebut atau port 445.
"""
import os
import socket
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import starlette
from fastapi.testclient import TestClient
from starlette.staticfiles import StaticFiles

from beeloft.api import create_app

UNC_HOST = "attacker.invalid"
SMB_PORT = 445
SECURITY_FLOOR = (1, 3, 1)
UNC_PREFIXES = (rf"\\{UNC_HOST}", f"//{UNC_HOST}", rf"\\?\UNC\{UNC_HOST}")

# Path yang pada Windows menjadi UNC path, yaitu tepat vektor advisory ini.
UNC_LOOKUP_PATHS = [
    rf"\\{UNC_HOST}\share\payload",
    rf"\\{UNC_HOST}\c$\Windows\win.ini",
    rf"\\?\UNC\{UNC_HOST}\share\payload",
    f"//{UNC_HOST}/share/payload",
    rf"\\127.0.0.1\share",
    "/etc/passwd",
]

UNC_REQUEST_PATHS = [
    f"/static/%5C%5C{UNC_HOST}%5Cshare%5Cpayload",
    f"/static/%5C%5C%3F%5CUNC%5C{UNC_HOST}%5Cshare%5Cpayload",
    f"/static/%5C%5C{UNC_HOST}%5Cc$%5CWindows%5Cwin.ini",
    f"/static/..%5C..%5C%5C%5C{UNC_HOST}%5Cshare",
    f"/static//{UNC_HOST}/share/payload",
    f"/static/%2F%2F{UNC_HOST}%2Fshare",
    f"/static/app.mjs/..%5C%5C{UNC_HOST}%5Cshare",
]


def starlette_version():
    return tuple(int(part) for part in starlette.__version__.split(".")[:3])


def targets_unc(path):
    """True hanya bila path benar-benar berbentuk UNC ke host penyerang.

    Bukan sekadar memuat nama host: `<static>/attacker.invalid/share` adalah path lokal biasa yang
    aman untuk di-stat, sedangkan `\\\\attacker.invalid\\share` adalah tujuan SMB.
    """
    return str(path).startswith(UNC_PREFIXES)


class FilesystemProbe:
    """Mencatat setiap resolusi path yang benar-benar menyentuh filesystem."""

    def __init__(self):
        self.calls = []

    def _wrap(self, name, original):
        def probe(path, *args, **kwargs):
            self.calls.append((name, str(path)))
            return original(path, *args, **kwargs)
        return probe

    def patches(self):
        return [patch.object(os.path, "realpath", self._wrap("realpath", os.path.realpath)),
                patch.object(os.path, "abspath", self._wrap("abspath", os.path.abspath)),
                patch.object(os, "stat", self._wrap("stat", os.stat))]

    @property
    def unc_calls(self):
        return [call for call in self.calls if targets_unc(call[1])]


class NetworkGuard:
    """Gagal keras bila ada yang mencoba menghubungi tujuan UNC; mencegah request SMB nyata."""

    def __init__(self):
        self.attempts = []

    @staticmethod
    def _targets_unc(args, kwargs):
        for item in list(args) + list(kwargs.values()):
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                if UNC_HOST in str(item[0]) or item[1] == SMB_PORT:
                    return True
            elif UNC_HOST in str(item) or item == SMB_PORT:
                return True
        return False

    def _wrap(self, name, original):
        def guard(*args, **kwargs):
            if self._targets_unc(args, kwargs):
                self.attempts.append((name, args, kwargs))
                raise AssertionError(f"{name} mencoba I/O jaringan ke tujuan UNC: {args} {kwargs}")
            return original(*args, **kwargs)
        return guard

    def patches(self):
        return [patch.object(socket, "getaddrinfo", self._wrap("getaddrinfo", socket.getaddrinfo)),
                patch.object(socket, "create_connection", self._wrap("create_connection", socket.create_connection)),
                patch.object(socket.socket, "connect", self._wrap("connect", socket.socket.connect))]


class StarletteSecurityFloorTest(unittest.TestCase):
    def test_installed_starlette_closes_every_known_advisory(self):
        self.assertGreaterEqual(
            starlette_version(), SECURITY_FLOOR,
            f"Starlette {starlette.__version__} terkena advisory yang sudah diperbaiki; batas "
            f"keamanan adalah {'.'.join(map(str, SECURITY_FLOOR))}. Jangan menurunkan lock.")


class StaticUncRejectionTest(unittest.TestCase):
    def setUp(self):
        self.static = Path(__file__).resolve().parents[1] / "beeloft" / "static"
        self.assertTrue((self.static / "app.mjs").is_file(), "direktori static tidak ditemukan")

    def test_unc_lookup_is_refused_before_any_filesystem_resolution(self):
        """Kontrak inti advisory: penolakan terjadi sebelum realpath/abspath/stat dipanggil.

        Pada rilis rentan, lookup_path menggabungkan path lalu memanggil os.path.realpath, dan di
        Windows itulah yang memicu koneksi SMB serta kebocoran NTLMv2. Rilis aman menolak path
        absolut lebih dahulu, sehingga tidak ada satu pun probe filesystem untuk path seperti ini.
        """
        files = StaticFiles(directory=self.static)
        for candidate in UNC_LOOKUP_PATHS:
            with self.subTest(path=candidate):
                probe, guard = FilesystemProbe(), NetworkGuard()
                with ExitStack() as stack:
                    for active in probe.patches() + guard.patches():
                        stack.enter_context(active)
                    result = files.lookup_path(candidate)
                self.assertEqual(result, ("", None), f"{candidate} tidak ditolak")
                self.assertEqual(probe.calls, [],
                                 f"{candidate} sempat di-resolve ke filesystem: {probe.calls}")
                self.assertEqual(guard.attempts, [])

    def test_unc_requests_return_404_without_touching_the_unc_destination(self):
        probe, guard = FilesystemProbe(), NetworkGuard()
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(Path(folder) / "static-security.sqlite3")) as client:
                with ExitStack() as stack:
                    for active in probe.patches() + guard.patches():
                        stack.enter_context(active)
                    for path in UNC_REQUEST_PATHS:
                        with self.subTest(path=path):
                            self.assertEqual(client.get(path).status_code, 404, path)
        self.assertEqual(guard.attempts, [], "ada percobaan I/O jaringan ke tujuan UNC")
        self.assertEqual(probe.unc_calls, [], f"path UNC sempat di-resolve: {probe.unc_calls}")

    def test_legitimate_assets_still_load(self):
        with tempfile.TemporaryDirectory() as folder:
            with TestClient(create_app(Path(folder) / "static-ok.sqlite3")) as client:
                for asset in ("app.mjs", "client.mjs", "style.css"):
                    self.assertEqual(client.get("/static/" + asset).status_code, 200)
                self.assertEqual(client.get("/static/../schema.sql").status_code, 404)
                self.assertEqual(client.get("/").status_code, 200)
