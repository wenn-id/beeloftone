#!/usr/bin/env python3
"""Data sintetis demo Issue #49 — alur planning -> approval -> cutting -> ledger.

Membuat database SQLite segar lalu menjalankan alur P02 end-to-end lewat API
Store, dan mencetak ringkasannya untuk bahan demo Senin 2026-09-28.

Pemakaian:  python scripts/demo_p02_planning_cutting.py [path-db] [--replace]
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from beeloft.store import Store  # noqa: E402
from beeloft.store import DomainError  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("database", nargs="?", type=Path)
parser.add_argument("--replace", action="store_true", help="Replace an existing caller-supplied database")
args = parser.parse_args()
DB = args.database if args.database is not None else REPO / "data" / "demo-p02.sqlite3"
if DB.exists():
    if args.database is not None and not args.replace:
        parser.error(f"Database already exists: {DB}. Use --replace to reset it.")
    DB.unlink()
DB.parent.mkdir(parents=True, exist_ok=True)

store = Store(str(DB))


def key():
    return "demo-p02-" + uuid.uuid4().hex[:8]


# akun admin demo
ADMIN = store.provision_user("Demo Admin", "admin")
ADMIN = {"id": ADMIN["id"], "name": ADMIN["name"], "api_key": ADMIN["api_key"], "role": "admin"}


def main():
    # 1. produk + bahan
    m = store.create_material({"code": "DEMO-KAIN", "name": "Kain demo P02", "unit": "kg",
                               "reason": "Demo"}, ADMIN, key())
    p_m = store.create_product({"sku": "DEMO-KEMEJA-M", "name": "Kemeja demo M", "color": "Putih",
                                "size": "M", "reason": "Demo"}, ADMIN, key())
    p_l = store.create_product({"sku": "DEMO-KEMEJA-L", "name": "Kemeja demo L", "color": "Putih",
                                "size": "L", "reason": "Demo"}, ADMIN, key())

    # 2. order -> rencana draft otomatis (kode = referensi)
    order = store.create_order({"reference": "DEMO-P02-001", "title": "Order demo planning-cutting",
                                "owner_id": ADMIN["id"], "due_date": "2026-10-05",
                                "plan_note": "Prioritas demo Senin malam",
                                "plan_start_date": "2026-09-28",
                                "lines": [{"product_id": p_m["id"], "quantity": 400},
                                          {"product_id": p_l["id"], "quantity": 200}]},
                               ADMIN, key())
    plan = store.plan(order["id"])
    print("1. Rencana dibuat otomatis:", plan["plan_code"], "| status:", plan["status"],
          "| target:", plan["target_quantity"], "pcs")

    # 3. bahan masuk + keluar untuk order
    batch = store.receive_material({"material_id": m["id"], "reference": "DEMO-BATCH-1",
                                    "supplier": "Pemasok demo", "quantity": "60", "location": "Rak demo",
                                    "received_date": "2026-09-28", "reason": "Demo"}, ADMIN, key())
    issue = store.issue_material({"batch_id": batch["id"], "order_id": order["id"],
                                  "quantity": "30", "reason": "Demo"}, ADMIN, key())
    line_m = next(l for l in order["lines"] if l["product_id"] == p_m["id"])
    line_l = next(l for l in order["lines"] if l["product_id"] == p_l["id"])
    store.move({"line_id": line_m["id"], "from_stage": "planned", "to_stage": "cutting",
                "quantity": 400, "reason": "Demo"}, ADMIN, key())
    store.move({"line_id": line_l["id"], "from_stage": "planned", "to_stage": "cutting",
                "quantity": 200, "reason": "Demo"}, ADMIN, key())

    # 4. cutting sebelum approve -> ditolak (gate)
    try:
        store.create_cutting_run(order["id"], {"reference": "CUT-DITOLAK", "issue_id": issue["id"],
            "used": "1", "waste": "0.1", "reason": "Demo", "cut_date": "2026-09-28",
            "outputs": [{"line_id": line_m["id"], "quantity": 10}]}, ADMIN, key())
    except DomainError as exc:
        print("2. Cutting saat draft ditolak:", exc.message)
    else:
        raise RuntimeError("Cutting unexpectedly succeeded while the plan was draft (gate bocor).")

    # 5. approve rencana -> cutting dengan rol + komposisi
    approved = store.approve_plan(order["id"], {"revision": plan["revision"],
                                                "reason": "Setuju demo"}, ADMIN, key())
    print("3. Rencana disetujui:", approved["status"], "| revisi:", approved["revision"])
    run = store.create_cutting_run(order["id"], {
        "reference": "CUT-DEMO-001", "issue_id": issue["id"], "used": "24.500", "waste": "1.000",
        "reason": "Potong demo 200 lembar", "cut_date": "2026-09-28",
        "weight_kg": "24.500",
        "rolls": [{"roll_no": 1, "weight_kg": "12.250", "sheets": 100, "note": "Rol A"},
                  {"roll_no": 2, "weight_kg": "12.250", "sheets": 100, "note": "Rol B"}],
        "output_params": [
            {"line_id": line_m["id"], "setelan_per_lembar": 3,
             "product_weight_gram": "180.500", "material_used_gram": "16333.333"},
            {"line_id": line_l["id"], "setelan_per_lembar": 3,
             "product_weight_gram": "195.000", "material_used_gram": "8166.667"}],
        "outputs": [{"line_id": line_m["id"], "quantity": 320},
                    {"line_id": line_l["id"], "quantity": 160}]}, ADMIN, key())
    d = run["detail"]
    print("4. Cutting tercatat:", run["reference"], "| tanggal:", d["cut_date"],
          "| rol:", d["roll_count"], "| lembar:", d["total_sheets"],
          "| berat:", d["total_roll_weight_kg"], "kg")
    for o in run["outputs"]:
        print("   -", o["sku"], "| aktual:", o["quantity"], "pcs | estimasi:",
              o["estimated_output_pcs"], "pcs |", o["estimate_basis"])

    # 6. rencana: target / realisasi / sisa
    plan = store.plan(order["id"])
    print("5. Rencana", plan["plan_code"], "| target:", plan["target_quantity"],
          "| realisasi:", plan["realized_quantity"], "| sisa:", plan["remaining_target"])

    # 7. ledger: output masuk tepat sekali, tidak ada stok kedua
    full = store.order(order["id"])
    print("6. Ledger order — sewing:", full["totals"]["sewing"],
          "| cutting:", full["totals"]["cutting"])

    print("\nDB demo:", DB)
    print("Lihat CSV:  GET /api/orders/%s/cutting-runs/export.csv" % order["id"])


if __name__ == "__main__":
    main()
