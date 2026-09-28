#!/usr/bin/env python3
"""Demo sintetis B01 (#50) — alur pembelian end-to-end.

DEMO_ASSUMPTION: seluruh data di bawah sintetis (pemasok, bahan, harga,
tanggal, nomor dokumen). Tidak ada pembayaran nyata yang dieksekusi:
"approved" pada payment request = siap dibayar, BUKAN kas keluar.

Jalankan dari root repo:
    /home/hatch/workspace/.venv-beeloft/bin/python scripts/demo_b01_purchasing_flow.py

Alur: PR -> PO -> partial receipt -> over-receipt DITOLAK ->
supplier-mismatch DITOLAK -> receipt lanjutan -> invoice (supplier salah &
harga salah DITOLAK) -> close sisa -> payment request menunjuk invoice ->
approve (siap bayar) -> duplikat aktif DITOLAK.
"""
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402

from beeloft.api import create_app  # noqa: E402

ADMIN = OPERATOR = None
CLIENT = None


def step(title):
    print(f"\n== {title} ==")


def show(label, value):
    print(f"   {label}: {value}")


def post(path, body, status=201):
    headers = {"Idempotency-Key": str(uuid4()), "X-API-Key": ADMIN["api_key"]}
    resp = CLIENT.post(path, json=body, headers=headers)
    if resp.status_code != status:
        raise AssertionError(
            f"{path}: expected {status}, got {resp.status_code}: {resp.text}")
    return resp.json()


def expect_reject(path, body, want_status, label):
    headers = {"Idempotency-Key": str(uuid4()), "X-API-Key": ADMIN["api_key"]}
    resp = CLIENT.post(path, json=body, headers=headers)
    assert resp.status_code == want_status, (
        f"{label}: expected {want_status}, got {resp.status_code}: {resp.text}")
    print(f"   DITOLAK ({resp.status_code}) {label}: {resp.json().get('detail')}")


def main():
    global ADMIN, OPERATOR, CLIENT
    folder = tempfile.TemporaryDirectory()
    app = create_app(Path(folder.name) / "demo-b01.sqlite3")
    CLIENT = TestClient(app)
    ADMIN = app.state.store.provision_user("Demo Pemilik", "admin")
    OPERATOR = app.state.store.provision_user("Demo Operator", "operator")

    step("1. Master sintetis (DEMO_ASSUMPTION)")
    material = post("/api/materials", {"code": "DEMO-KAIN", "name": "Kain demo", "unit": "m"})
    supplier = post("/api/suppliers", {"code": "DEMO-SUP", "name": "Pemasok Demo",
                                       "contact": "PIC", "address": "Jakarta",
                                       "reason": "Data sintetis demo B01"})
    other = post("/api/suppliers", {"code": "DEMO-LAIN", "name": "Pemasok Lain",
                                    "contact": "PIC", "address": "Jakarta",
                                    "reason": "Data sintetis demo B01"})
    show("material", f"{material['code']} ({material['unit']})")
    show("supplier", f"{supplier['code']} · {supplier['name']}")

    step("2. PR -> PO -> approve (PO diterbitkan)")
    pr = post("/api/purchase-requests",
              {"reference": "DEMO-PR-001", "required_date": "2026-10-01",
               "estimated_value": "30000.00", "reason": "Demo B01",
               "lines": [{"material_id": material["id"], "quantity": "2.125"}]})
    pr = post(f"/api/purchase-requests/{pr['id']}/decisions",
              {"status": "approved", "expected_revision": pr["revision"],
               "reason": "Disetujui (sintetis)"})
    po = post("/api/purchase-orders",
              {"reference": "DEMO-PO-001", "request_id": pr["id"],
               "expected_revision": pr["revision"], "supplier_id": supplier["id"],
               "expected_date": "2026-10-15", "terms": "Bayar setelah diterima",
               "reason": "Harga disepakati (sintetis)",
               "prices": [{"material_id": material["id"], "unit_price": "12.34"}]})
    po = post(f"/api/purchase-orders/{po['id']}/decisions",
              {"status": "approved", "expected_revision": po["revision"],
               "reason": "PO diterbitkan (sintetis)"})
    line = po["lines"][0]
    show("PO", f"{po['reference']} · {line['quantity']} m × Rp{line['unit_price']}"
               f" = Rp{po['total']} (harga PO terkunci)")

    step("3. Partial receipt 1.125 m")
    batch = post(f"/api/purchase-orders/{po['id']}/receipts",
                 {"material_id": material["id"], "reference": "DEMO-BATCH-A",
                  "quantity": "1.125", "location": "Rak Demo",
                  "received_date": "2026-10-16", "reason": "Diterima sebagian"})
    show("receipt", f"{batch['reference']} · saldo {batch['balance']} m")

    step("4. Over-receipt DITOLAK (melebihi sisa PO)")
    expect_reject(f"/api/purchase-orders/{po['id']}/receipts",
                  {"material_id": material["id"], "reference": "DEMO-OVER",
                   "quantity": "2.000", "location": "Rak Demo",
                   "received_date": "2026-10-16", "reason": "Sengaja berlebih"},
                  409, "quantity 2.000 > sisa 1.000")

    step("5. Supplier-mismatch pada receipt DITOLAK")
    expect_reject(f"/api/purchase-orders/{po['id']}/receipts",
                  {"material_id": material["id"], "reference": "DEMO-FORGE",
                   "supplier": "Pemasok Palsu", "quantity": "0.100",
                   "location": "Rak Demo", "received_date": "2026-10-16",
                   "reason": "Sengaja salah supplier"},
                  422, "field supplier disisipkan")

    step("6. Receipt lanjutan 0.500 m")
    batch2 = post(f"/api/purchase-orders/{po['id']}/receipts",
                  {"material_id": material["id"], "reference": "DEMO-BATCH-B",
                   "quantity": "0.500", "location": "Rak Demo",
                   "received_date": "2026-10-17", "reason": "Kiriman kedua"})
    show("total diterima", "1.625 m dari 2.125 m")

    step("7. Invoice #1: 1.125 m @ Rp12.34 = Rp13.88")
    inv1 = post("/api/supplier-invoices",
                {"reference": "DEMO-INV-001", "supplier_id": supplier["id"],
                 "invoice_date": "2026-10-18", "due_date": "2026-11-01",
                 "lines": [{"purchase_order_id": po["id"],
                            "material_id": material["id"],
                            "quantity": "1.125", "unit_price": "12.34"}],
                 "reason": "Tagihan kiriman pertama (sintetis)"})
    alloc = inv1["allocations"][0]
    show("invoice", f"{inv1['reference']} · total Rp{inv1['total']}")
    show("alokasi", f"{alloc['quantity']} m × Rp{alloc['unit_price']} = Rp{alloc['line_total']}"
                    f" · belum ditagih {alloc['uninvoiced']} m")

    step("8. Invoice supplier-salah DITOLAK")
    expect_reject("/api/supplier-invoices",
                  {"reference": "DEMO-INV-X", "supplier_id": other["id"],
                   "invoice_date": "2026-10-18", "due_date": "2026-11-01",
                   "lines": [{"purchase_order_id": po["id"],
                              "material_id": material["id"],
                              "quantity": "0.100", "unit_price": "12.34"}],
                   "reason": "Sengaja salah supplier"},
                  422, f"PO milik {supplier['code']}")

    step("9. Invoice harga-salah DITOLAK (harga referensi bukan harga aktual)")
    expect_reject("/api/supplier-invoices",
                  {"reference": "DEMO-INV-Y", "supplier_id": supplier["id"],
                   "invoice_date": "2026-10-18", "due_date": "2026-11-01",
                   "lines": [{"purchase_order_id": po["id"],
                              "material_id": material["id"],
                              "quantity": "0.100", "unit_price": "15.00"}],
                   "reason": "Sengaja salah harga"},
                  422, "harga invoice harus sama dengan harga aktual PO")

    step("10. Invoice melebihi sisa belum-ditagih DITOLAK")
    expect_reject("/api/supplier-invoices",
                  {"reference": "DEMO-INV-Z", "supplier_id": supplier["id"],
                   "invoice_date": "2026-10-18", "due_date": "2026-11-01",
                   "lines": [{"purchase_order_id": po["id"],
                              "material_id": material["id"],
                              "quantity": "1.000", "unit_price": "12.34"}],
                   "reason": "Sengaja berlebih"},
                  409, "sisa belum ditagih hanya 0.500 m")

    step("11. Invoice #2 untuk sisa 0.500 m = Rp6.17")
    inv2 = post("/api/supplier-invoices",
                {"reference": "DEMO-INV-002", "supplier_id": supplier["id"],
                 "invoice_date": "2026-10-19", "due_date": "2026-11-02",
                 "lines": [{"purchase_order_id": po["id"],
                            "material_id": material["id"],
                            "quantity": "0.500", "unit_price": "12.34"}],
                 "reason": "Tagihan kiriman kedua (sintetis)"})
    show("invoice", f"{inv2['reference']} · total Rp{inv2['total']}")

    step("12. Close sisa PO (0.500 m tidak datang)")
    closed = post(f"/api/purchase-orders/{po['id']}/close", {"reason": "Sisa tidak dikirim"})
    show("PO", f"status {closed['status']} · fulfillment {closed['fulfillment']}"
               f" · diterima {closed['lines'][0]['received']} m"
               f" · sisa {closed['lines'][0]['remaining']} m")

    step("13. Receipt setelah close DITOLAK")
    expect_reject(f"/api/purchase-orders/{po['id']}/receipts",
                  {"material_id": material["id"], "reference": "DEMO-LATE",
                   "quantity": "0.100", "location": "Rak Demo",
                   "received_date": "2026-10-20", "reason": "Sengaja setelah close"},
                  409, "PO sudah ditutup")

    step("14. Payment request menunjuk DEMO-INV-001")
    pay = post(f"/api/purchase-orders/{po['id']}/payment-requests",
               {"reference": "DEMO-PAY-001", "invoice_id": inv1["id"],
                "invoice_reference": inv1["reference"],
                "invoice_date": inv1["invoice_date"], "due_date": inv1["due_date"],
                "amount": "13.88", "reason": "Bayar tagihan kiriman pertama"})
    show("payment request", f"{pay['reference']} · Rp{pay['amount']} · status {pay['status']}"
                            f" · invoice {pay['invoice']['reference']}")

    step("15. Payment request tanpa invoice DITOLAK")
    expect_reject(f"/api/purchase-orders/{po['id']}/payment-requests",
                  {"reference": "DEMO-PAY-X", "invoice_id": "missing",
                   "invoice_reference": "TIDAK-ADA", "invoice_date": "2026-10-19",
                   "due_date": "2026-11-02", "amount": "1.00",
                   "reason": "Sengaja tanpa invoice"},
                  404, "tagihan tidak terdaftar")

    step("16. Approve payment request (siap bayar, BUKAN kas keluar)")
    decided = post(f"/api/supplier-payment-requests/{pay['id']}/decisions",
                   {"status": "approved", "expected_revision": pay["revision"],
                    "reason": "Disetujui (sintetis)"})
    show("status", f"{decided['status']} — siap dibayar; transfer bank & jurnal "
                   "settlement di luar scope #50 (milik #54)")

    step("17. Duplikat payment request aktif DITOLAK")
    expect_reject(f"/api/purchase-orders/{po['id']}/payment-requests",
                  {"reference": "DEMO-PAY-002", "invoice_id": inv1["id"],
                   "invoice_reference": inv1["reference"],
                   "invoice_date": inv1["invoice_date"], "due_date": inv1["due_date"],
                   "amount": "1.00", "reason": "Sengaja duplikat"},
                  409, "satu invoice = satu payment request aktif")

    print("\nSelesai. Handoff #54:")
    print(f"  invoice #1 id={inv1['id']} ref={inv1['reference']} total={inv1['total']}")
    print(f"  invoice #2 id={inv2['id']} ref={inv2['reference']} total={inv2['total']}")
    print(f"  payment request id={pay['id']} ref={pay['reference']} status={decided['status']}")


if __name__ == "__main__":
    main()
