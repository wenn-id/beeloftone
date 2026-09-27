import argparse
import json
import os
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from beeloft.store import DomainError, Store


def main():
    parser = argparse.ArgumentParser(description="Beeloft One: produksi internal")
    parser.add_argument("--db", default=os.environ.get("BEELOFT_DB", "data/beeloft.sqlite3"))
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Jalankan API lokal")
    serve.add_argument("--port", type=int, default=8000)
    user = commands.add_parser("user", help="Buat akun; API key ditampilkan sekali")
    user.add_argument("--name", required=True)
    user.add_argument("--role", choices=["admin", "operator", "viewer"], required=True)
    disable = commands.add_parser("disable-user", help="Nonaktifkan akun dan API key")
    disable.add_argument("user_id")
    oidc_link = commands.add_parser("oidc-link", help="Tautkan identitas OIDC ke akun Beeloft")
    oidc_link.add_argument("--issuer", required=True)
    oidc_link.add_argument("--subject", required=True)
    oidc_link.add_argument("--user-id", required=True)
    oidc_unlink = commands.add_parser("oidc-unlink", help="Lepaskan identitas OIDC dari akun Beeloft")
    oidc_unlink.add_argument("--issuer", required=True)
    oidc_unlink.add_argument("--subject", required=True)
    backup = commands.add_parser("backup", help="Backup konsisten tanpa menimpa file")
    backup.add_argument("destination")
    demo = commands.add_parser("demo", help="Buat database demo presentasi (data sintetis)")
    demo.add_argument("--fresh", action="store_true",
                      help="Hapus database demo yang ada lalu buat ulang dari nol (reset demo)")
    args = parser.parse_args()
    path = Path(args.db).resolve()

    try:
        if args.command in ("backup", "disable-user", "oidc-link", "oidc-unlink") and not path.is_file():
            parser.error("Database sumber belum ada.")
        if args.command == "demo":
            path.parent.mkdir(parents=True, exist_ok=True)
            if args.fresh and path.is_file():
                path.unlink()
            with path.open("xb"):
                pass
        if args.command == "serve":
            import uvicorn
            from beeloft.api import create_app
            uvicorn.run(create_app(path), host="127.0.0.1", port=args.port)
            return
        store = Store(path)
        if args.command == "user":
            result = store.provision_user(args.name, args.role)
        elif args.command == "disable-user":
            store.disable_user(args.user_id)
            result = {"disabled_user": args.user_id}
        elif args.command == "oidc-link":
            result = store.link_oidc_identity(args.issuer, args.subject, args.user_id)
        elif args.command == "oidc-unlink":
            store.unlink_oidc_identity(args.issuer, args.subject)
            result = {"unlinked_issuer": args.issuer.rstrip('/'), "unlinked_subject": args.subject}
        elif args.command == "backup":
            store.backup(args.destination)
            result = {"backup": str(Path(args.destination).resolve())}
        else:
            # Perintah demo: bangun skenario presentasi sintetis lengkap via beeloft.demo.
            from beeloft.demo import seed_demo_story
            users = [store.provision_user(name, role) for name, role in [
                ("Admin Demo", "admin"), ("Produksi Demo", "operator"), ("Viewer Demo", "viewer")]]
            actor = store.authenticate(users[0]["api_key"])
            story = seed_demo_story(store, actor)
            result = {"notice": "DATA DEMO SINTETIS untuk presentasi. Simpan API key; hanya ditampilkan saat dibuat.",
                      "database": str(path), "users": users, **story}
        print(json.dumps(result, indent=2, ensure_ascii=True))
    except (DomainError, OSError, sqlite3.Error, ValidationError) as exc:
        parser.exit(1, f"Gagal: {exc}\n")


if __name__ == "__main__":
    main()
