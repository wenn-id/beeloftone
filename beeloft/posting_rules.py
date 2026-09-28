"""Aturan posting jurnal — A01 / issue #46.

Modul ini memuat DUA hal yang dipisahkan eksplisit:

1. **Kontrak posting sintetis** (DEMO_ASSUMPTION): pemetaan event -> debit/
   kredit untuk demo memakai COA sintetis. BUKAN kebijakan resmi Beeloft;
   metode biaya, timing pengakuan, dan pajak belum ditetapkan pemilik
   accounting (D13/D14 DETAIL_OPEN). Jangan menyatakan mapping di sini
   sebagai aturan produksi.

2. **Adapter ke transaksi existing** yang benar-benar diimplementasikan
   (menerima record existing -> baris jurnal). Adapter membaca nilai dari
   sumber authoritative existing dan memakai kontrak uang F02.

Versi kebijakan: ``DEMO_POSTING_POLICY_REF = "DEMO-POST-20260928-1"``.
Setiap jurnal mencatat ``policy_ref`` agar aturan yang dipakai dapat
ditelusuri dan diganti per versi tanpa mengubah kontrak.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Referensi kebijakan posting demo berversi. DEMO_ASSUMPTION.
DEMO_POSTING_POLICY_REF = "DEMO-POST-20260928-1"


# ---------------------------------------------------------------------------
# COA sintetis untuk demo. Kode stabil 4 digit gaya Indonesia.
# DEMO_ASSUMPTION: bukan COA resmi perusahaan.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SyntheticAccount:
    code: str
    name: str
    type: str  # asset|liability|equity|revenue|expense


DEMO_COA: tuple[SyntheticAccount, ...] = (
    SyntheticAccount("1100", "Kas", "asset"),
    SyntheticAccount("1110", "Bank", "asset"),
    SyntheticAccount("1130", "Piutang karyawan (kasbon)", "asset"),
    SyntheticAccount("1200", "Piutang usaha", "asset"),
    SyntheticAccount("1300", "Persediaan bahan baku", "asset"),
    SyntheticAccount("1310", "Persediaan barang dalam proses (WIP)", "asset"),
    SyntheticAccount("1320", "Persediaan barang jadi", "asset"),
    SyntheticAccount("2100", "Utang usaha", "liability"),
    SyntheticAccount("2110", "Utang gaji/upah", "liability"),
    SyntheticAccount("3100", "Modal", "equity"),
    SyntheticAccount("4100", "Pendapatan penjualan", "revenue"),
    SyntheticAccount("5100", "Harga pokok penjualan (COGS)", "expense"),
    SyntheticAccount("5200", "Beban gaji/upah", "expense"),
)

DEMO_COA_BY_CODE = {a.code: a for a in DEMO_COA}


# ---------------------------------------------------------------------------
# Pemetaan event -> (debit, kredit). Setiap fungsi menerima nilai integer
# minor dan mengembalikan daftar baris (account_code, debit_minor,
# credit_minor, description).
#
# DEMO_ASSUMPTION: mapping di bawah ini kontrak sintetis untuk demo.
# ---------------------------------------------------------------------------

def _line(account_code: str, debit_minor: int, credit_minor: int,
           description: str = "") -> dict:
    if account_code not in DEMO_COA_BY_CODE:
        raise ValueError(f"kode akun demo tidak dikenal: {account_code!r}")
    for value in (debit_minor, credit_minor):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"nominal baris harus integer >= 0: {value!r}")
    if (debit_minor > 0) == (credit_minor > 0):
        raise ValueError("tepat satu sisi (debit XOR kredit) harus positif")
    return {"account_code": account_code, "debit_minor": debit_minor,
            "credit_minor": credit_minor, "description": description}


def check_balanced(lines: list[dict]) -> tuple[int, int]:
    """Validasi jurnal seimbang eksak dalam integer minor."""
    debit = sum(line["debit_minor"] for line in lines)
    credit = sum(line["credit_minor"] for line in lines)
    if debit != credit:
        raise ValueError(
            f"jurnal tidak seimbang: debit {debit} != kredit {credit}")
    if debit <= 0:
        raise ValueError("jurnal harus memiliki total positif")
    return debit, credit


def material_receipt_lines(*, amount_minor: int, description: str = "") -> list[dict]:
    """Penerimaan bahan dari PO: persediaan bertambah, utang usaha bertambah."""
    return [
        _line("1300", amount_minor, 0, description or "Penerimaan bahan baku"),
        _line("2100", 0, amount_minor, description or "Utang usaha pemasok"),
    ]


def material_consumption_lines(*, amount_minor: int, description: str = "") -> list[dict]:
    """Pemakaian bahan ke WIP produksi."""
    return [
        _line("1310", amount_minor, 0, description or "Bahan masuk WIP"),
        _line("1300", 0, amount_minor, description or "Persediaan bahan keluar"),
    ]


def finished_goods_lines(*, amount_minor: int, description: str = "") -> list[dict]:
    """Barang jadi masuk gudang dari WIP."""
    return [
        _line("1320", amount_minor, 0, description or "Barang jadi masuk gudang"),
        _line("1310", 0, amount_minor, description or "WIP selesai"),
    ]


def sales_lines(*, revenue_minor: int, cogs_minor: int,
                description: str = "") -> list[dict]:
    """Penjualan: piutang & pendapatan, plus COGS & persediaan keluar."""
    return [
        _line("1200", revenue_minor, 0, description or "Piutang penjualan"),
        _line("4100", 0, revenue_minor, description or "Pendapatan penjualan"),
        _line("5100", cogs_minor, 0, description or "HPP penjualan"),
        _line("1320", 0, cogs_minor, description or "Persediaan barang jadi keluar"),
    ]


def payroll_accrual_lines(*, amount_minor: int, description: str = "") -> list[dict]:
    """Akrual upah: beban diakui, utang upah bertambah."""
    return [
        _line("5200", amount_minor, 0, description or "Beban gaji/upah"),
        _line("2110", 0, amount_minor, description or "Utang gaji/upah"),
    ]


def payroll_payment_lines(*, amount_minor: int, via: str = "1100",
                          description: str = "") -> list[dict]:
    """Pembayaran upah: utang berkurang, kas/bank berkurang."""
    if via not in ("1100", "1110"):
        raise ValueError("pembayaran upah hanya via 1100 (Kas) atau 1110 (Bank)")
    return [
        _line("2110", amount_minor, 0, description or "Pelunasan utang upah"),
        _line(via, 0, amount_minor, description or "Kas/bank keluar"),
    ]


def kasbon_disbursement_lines(*, amount_minor: int, description: str = "") -> list[dict]:
    """Pemberian kasbon: piutang karyawan bertambah, kas berkurang."""
    return [
        _line("1130", amount_minor, 0, description or "Kasbon karyawan"),
        _line("1100", 0, amount_minor, description or "Kas keluar"),
    ]


def kasbon_deduction_lines(*, amount_minor: int, description: str = "") -> list[dict]:
    """Potongan kasbon dari upah: utang upah berkurang, piutang kasbon berkurang."""
    return [
        _line("2110", amount_minor, 0, description or "Potongan kasbon atas upah"),
        _line("1130", 0, amount_minor, description or "Piutang kasbon berkurang"),
    ]


def purchase_payment_lines(*, amount_minor: int, via: str = "1110",
                           description: str = "") -> list[dict]:
    """Pembayaran utang usaha: utang berkurang, kas/bank berkurang."""
    if via not in ("1100", "1110"):
        raise ValueError("pembayaran utang hanya via 1100 (Kas) atau 1110 (Bank)")
    return [
        _line("2100", amount_minor, 0, description or "Pelunasan utang usaha"),
        _line(via, 0, amount_minor, description or "Kas/bank keluar"),
    ]


def sales_receipt_lines(*, amount_minor: int, via: str = "1110",
                        description: str = "") -> list[dict]:
    """Penerimaan piutang: kas/bank bertambah, piutang berkurang."""
    if via not in ("1100", "1110"):
        raise ValueError("penerimaan piutang hanya via 1100 (Kas) atau 1110 (Bank)")
    return [
        _line(via, amount_minor, 0, description or "Kas/bank masuk"),
        _line("1200", 0, amount_minor, description or "Piutang usaha berkurang"),
    ]


#: Registry event -> fungsi pembangun baris, untuk dokumentasi/publikasi kontrak.
POSTING_RULES: dict[str, str] = {
    "material_receipt": "Dr 1300 Persediaan bahan baku / Cr 2100 Utang usaha",
    "material_consumption": "Dr 1310 WIP / Cr 1300 Persediaan bahan baku",
    "finished_goods": "Dr 1320 Persediaan barang jadi / Cr 1310 WIP",
    "sales": "Dr 1200 Piutang usaha / Cr 4100 Pendapatan; Dr 5100 COGS / Cr 1320 Persediaan",
    "payroll_accrual": "Dr 5200 Beban gaji/upah / Cr 2110 Utang gaji/upah",
    "payroll_payment": "Dr 2110 Utang gaji/upah / Cr 1100/1110 Kas/Bank",
    "kasbon_disbursement": "Dr 1130 Piutang karyawan / Cr 1100 Kas",
    "kasbon_deduction": "Dr 2110 Utang gaji/upah / Cr 1130 Piutang karyawan",
    "purchase_payment": "Dr 2100 Utang usaha / Cr 1100/1110 Kas/Bank",
    "sales_receipt": "Dr 1100/1110 Kas/Bank / Cr 1200 Piutang usaha",
}


# ---------------------------------------------------------------------------
# Adapter: transaksi existing -> baris jurnal.
# ---------------------------------------------------------------------------

def adapt_po_receipt(*, po: dict, receipts: list[dict]) -> list[dict]:
    """Adapter NYATA: penerimaan PO (existing) -> baris jurnal penerimaan bahan.

    Membaca nilai authoritative dari record existing: ``po['lines']`` memuat
    ``unit_price`` terkunci per material; ``receipts`` memuat
    ``material_id`` + ``quantity`` (string desimal) yang diterima. Total =
    sum(qty * unit_price) dalam minor memakai kontrak uang F02. Tidak
    mengarang nilai.
    """
    from decimal import Decimal, ROUND_HALF_UP
    prices = {line["material_id"]: line["unit_price"] for line in po.get("lines") or []}
    total_minor = 0
    for receipt in receipts:
        material_id = receipt.get("material_id")
        if material_id not in prices:
            raise ValueError(f"adapter PO receipt: bahan {material_id!r} tidak ada di PO")
        qty = Decimal(str(receipt.get("quantity") or "0"))
        price = Decimal(str(prices[material_id]))
        if qty <= 0:
            raise ValueError("adapter PO receipt: quantity harus positif")
        # Pembulatan eksplisit HALF_UP ke minor, sama seperti pembuatan PO.
        total_minor += int((qty * price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if total_minor <= 0:
        raise ValueError("adapter PO receipt: total nilai harus positif")
    desc = f"Penerimaan PO {po.get('reference') or po.get('id')}"
    return material_receipt_lines(amount_minor=total_minor, description=desc)
