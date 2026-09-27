"""Kontrak transaksi dan data bersama — F02 / issue #41.

Modul ini mengkodifikasi *invariant teknis* kontrak bersama sebagai fungsi
murni tanpa efek samping: tanpa DB, tanpa HTTP, tanpa perubahan schema.
Aturan ini dipakai lintas domain (produksi, payroll, kasbon, pembayaran,
posting jurnal) dan diuji lewat ``tests/test_f02_contracts.py`` memakai
vektor di ``tests/fixtures/f02-contracts.json``.

Dua hal dipisahkan secara eksplisit:

- **Invariant teknis**: tidak boleh dilanggar implementasi mana pun
  (mis. uang tidak lewat float, replay tidak menduplikasi efek ekonomi,
  reversal menautkan transaksi asal, approved != paid != posted).
- **Pilihan kebijakan bisnis**: tarif, pembulatan upah, eligibility dsb.
  yang belum final dibungkus dalam objek ``ContractPolicy`` berversi.
  ``DEMO_POLICY`` berisi asumsi sementara untuk demo dan SELALU dilabeli
  ``DEMO_ASSUMPTION`` — bukan fakta legacy, bukan kebijakan produksi
  yang disetujui. Ganti ``policy`` untuk mengganti asumsi tanpa
  mengubah kontrak.

Lihat ``docs/f02-shared-contracts.md`` untuk narasi lengkap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP
from typing import Iterable, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Identitas entitas dan referensi sumber transaksi
# ---------------------------------------------------------------------------

#: Jenis sumber record. ``native`` = dibuat Beeloft One; ``external_snapshot``
#: = observasi read-only dari sistem luar; ``imported_transaction`` = transaksi
#: ekonomi yang diimpor dan menjadi authoritative; ``opening_balance`` = saldo
#: awal cutover. Snapshot TIDAK PERNAH dijumlah bersama native untuk scope
#: yang sama (lihat :func:`dedupe_contributions`).
SOURCE_KINDS = ("native", "external_snapshot", "imported_transaction", "opening_balance")

_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def validate_idempotency_key(key: str) -> str:
    """Validasi Idempotency-Key sesuai kontrak: 1-128 karakter
    ``[A-Za-z0-9._:-]``. Key mengikat satu transaksi logis di seluruh
    database; key bukan nomor dokumen dan bukan pengganti source identity."""
    if not isinstance(key, str) or not _IDEMPOTENCY_KEY_RE.match(key):
        raise ValueError(
            "Idempotency-Key harus 1-128 karakter [A-Za-z0-9._:-]; "
            f"diterima: {key!r}"
        )
    return key


def source_namespace(system: str, account: str, entity_type: str) -> tuple[str, str, str]:
    """Bangun namespace sumber terstruktur ``(system, account, entity_type)``.

    Ketiga elemen wajib. Namespace dipakai sebagai tuple terstruktur, BUKAN
    string concatenation, supaya record ``42`` di dua account/entity tidak
    bertabrakan (mis. ``("mekari","A","payroll")`` vs ``("mekari","A-pay","roll")``).
    """
    parts = (system, account, entity_type)
    for name, part in zip(("system", "account", "entity_type"), parts):
        if not isinstance(part, str) or not part.strip():
            raise ValueError(f"namespace {name} wajib string non-kosong")
    return (system.strip(), account.strip(), entity_type.strip())


def canonical_source_key(
    system: str,
    account: str,
    entity_type: str,
    source_id: str,
    source_line_id: Optional[str] = None,
) -> tuple[str, str, str, str, Optional[str]]:
    """Kunci kanonis sumber: namespace + ``source_id`` opaque + ``source_line_id``.

    Identifier sumber bersifat opaque (case-sensitive); normalisasi hanya
    menurut kontrak connector masing-masing. Scope line berada di dalam
    source ID. Replay ``(namespace, source_id, source_line_id, revision)``
    yang sama tidak boleh menimbulkan efek ekonomi kedua.
    """
    namespace = source_namespace(system, account, entity_type)
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("source_id wajib string non-kosong")
    return namespace + (source_id, source_line_id)


# ---------------------------------------------------------------------------
# Kuantitas, satuan dasar, konversi pcs/lusin
# ---------------------------------------------------------------------------

#: Konversi fisik: 12 pcs = 1 lusin. Ini konversi satuan, BUKAN keputusan
#: berapa lusin yang dibayar untuk N pcs — itu kebijakan (lihat ContractPolicy).
PCS_PER_LUSIN = Decimal(12)

#: Batas kontrak Quantity: integer strict, 1..1_000_000_000 pcs.
QTY_MIN = 1
QTY_MAX = 1_000_000_000


def check_quantity(pcs: int) -> int:
    """Kontrak qty produk: integer strict dalam [1, 1_000_000_000]."""
    if not isinstance(pcs, int) or isinstance(pcs, bool):
        raise ValueError(f"qty harus integer strict, diterima: {pcs!r}")
    if not QTY_MIN <= pcs <= QTY_MAX:
        raise ValueError(f"qty harus {QTY_MIN}..{QTY_MAX}, diterima: {pcs}")
    return pcs


def pcs_to_lusin(pcs: int) -> Decimal:
    """Konversi pcs -> lusin sebagai Decimal eksak, tanpa pembulatan diam-diam.

    pcs asal SELALU disimpan; hasil konversi ini untuk kalkulasi, bukan
    pengganti data asal.
    """
    check_quantity(pcs)
    return Decimal(pcs) / PCS_PER_LUSIN


def lusin_to_pcs(lusin: Decimal) -> int:
    """Konversi lusin -> pcs; hanya untuk kelipatan eksak 12.

    Menolak nilai non-kelipatan daripada memotong diam-diam — keputusan
    pembulatan kuantitas upah adalah kebijakan, bukan konversi satuan.
    """
    if not isinstance(lusin, Decimal):
        raise ValueError(f"lusin harus Decimal, diterima: {lusin!r}")
    pcs = lusin * PCS_PER_LUSIN
    if pcs != pcs.to_integral_value():
        raise ValueError(f"{lusin} lusin bukan kelipatan pcs bulat")
    return int(pcs)


# ---------------------------------------------------------------------------
# Representasi uang, presisi, titik pembulatan
# ---------------------------------------------------------------------------

#: Uang disimpan sebagai integer minor (100 minor = 1 IDR). Jangan lewatkan
#: uang melalui float atau JavaScript Number untuk kalkulasi authoritative.
MINOR_PER_UNIT = 100

_MONEY_RE = re.compile(r"^[0-9]{1,15}(\.[0-9]{1,2})?$")

_ROUNDING_MODES = {
    "HALF_UP": ROUND_HALF_UP,
    "DOWN": ROUND_DOWN,
    "UP": ROUND_UP,
}


def parse_money(value: str) -> Decimal:
    """Parse string uang sesuai kontrak FinanceAmount: digit biasa, tanpa
    pemisah ribuan/eksponen/tanda; maksimal 15 digit + 2 desimal."""
    if not isinstance(value, str) or not _MONEY_RE.match(value) or len(value) > 18:
        raise ValueError(f"format uang tidak valid: {value!r}")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"format uang tidak valid: {value!r}") from exc


def money_to_minor(amount: Decimal) -> int:
    """Decimal uang (maks 2 desimal) -> integer minor. Menolak >2 desimal
    daripada membulatkan diam-diam; pembulatan harus eksplisit via
    :func:`round_to_minor` dengan mode dan tahap tercatat."""
    if not isinstance(amount, Decimal):
        raise ValueError(f"uang harus Decimal, diterima: {amount!r}")
    scaled = amount * MINOR_PER_UNIT
    if scaled != scaled.to_integral_value():
        raise ValueError(f"uang melebihi 2 desimal, bulatkan eksplisit dulu: {amount}")
    return int(scaled)


def minor_to_money(minor: int) -> Decimal:
    """Integer minor -> Decimal uang eksak 2 desimal."""
    if not isinstance(minor, int) or isinstance(minor, bool):
        raise ValueError(f"minor harus integer, diterima: {minor!r}")
    return Decimal(minor) / MINOR_PER_UNIT


def round_to_minor(amount: Decimal, mode: str = "HALF_UP") -> int:
    """Bulatkan Decimal uang ke integer minor dengan mode eksplisit.

    Mode yang didukung: HALF_UP, DOWN, UP. Titik pembulatan (per baris,
    per batch, dst.) dan mode-nya adalah bagian kontrak kalkulasi dan
    wajib tercatat bersama ``calculation_policy_ref`` pada hasil —
    jangan menghitung ulang histori dengan konfigurasi terbaru.
    """
    if mode not in _ROUNDING_MODES:
        raise ValueError(f"mode pembulatan tidak dikenal: {mode!r}")
    if not isinstance(amount, Decimal):
        raise ValueError(f"uang harus Decimal, diterima: {amount!r}")
    return int((amount * MINOR_PER_UNIT).to_integral_value(rounding=_ROUNDING_MODES[mode]))


# ---------------------------------------------------------------------------
# Kebijakan kalkulasi berversi (pemisah invariant vs pilihan bisnis)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContractPolicy:
    """Satu versi kebijakan kalkulasi. Invariant teknis tetap di fungsi
    murni di atas; semua yang belum final sebagai kebijakan bisnis masuk
    ke sini dan diganti dengan mengganti objek policy (atau versinya),
    bukan dengan mengubah kontrak."""

    policy_ref: str
    #: Cara mengubah pcs realisasi menjadi kuantitas upah: "EXACT" = hitung
    #: dengan pcs/12 eksak (Decimal); kebijakan lain menunggu keputusan D04.
    wage_lusin_rounding: str = "EXACT"
    #: Mode pembulatan nominal upah ke minor.
    wage_money_rounding: str = "HALF_UP"
    #: Tahap pembulatan nominal upah.
    wage_money_rounding_stage: str = "per_employee_per_work_type"
    #: Rasio maksimum potongan kasbon terhadap upah bruto per payroll.
    kasbon_max_deduction_ratio: str = "1.0"


#: DEMO_ASSUMPTION — asumsi sementara, sederhana dan konsisten, HANYA untuk
#: demo. Bukan fakta legacy, bukan kebijakan produksi yang disetujui.
#: Versi ini dirujuk hasil kalkulasi demo via ``calculation_policy_ref``.
DEMO_POLICY = ContractPolicy(
    policy_ref="DEMO-20260928-1",
    # DEMO_ASSUMPTION: upah = (pcs / 12) x tarif_per_lusin, pcs/12 eksak
    # tanpa pembulatan kuantitas; keputusan D04 (13 pcs dibayar berapa)
    # belum final dan tidak diasumsikan di sini.
    wage_lusin_rounding="EXACT",
    # DEMO_ASSUMPTION: nominal upah dibulatkan HALF_UP ke rupiah per
    # pekerja per jenis pekerjaan; tahap/mode final menunggu D04/D06.
    wage_money_rounding="HALF_UP",
    wage_money_rounding_stage="per_employee_per_work_type",
    # DEMO_ASSUMPTION: kasbon boleh dipotong penuh dari upah bruto pada
    # demo; batas potongan, net-tidak-cukup, dan urutan cicilan (D08)
    # belum final.
    kasbon_max_deduction_ratio="1.0",
)


def wage_for_realization(
    *,
    pcs: int,
    rate_per_lusin_minor: int,
    rate_revision: str,
    policy: ContractPolicy = DEMO_POLICY,
) -> dict:
    """Hitung upah satu realisasi kerja -> charge jasa.

    Kontrak: amount Decimal final menjadi SATU sumber biaya jasa dan upah.
    Costing dan payroll membaca charge yang sama; tidak ada rumus kedua.
    Satu realization/work component tidak ditagih dua kali — itu dijamin
    idempotency key + canonical source key di lapisan tulis, bukan di sini.

    Mengembalikan dict dengan ``calculation_policy_ref`` agar konsumen tahu
    asumsi mana yang dipakai dan bisa menggantinya per versi kebijakan.
    """
    check_quantity(pcs)
    minor_to_money(rate_per_lusin_minor)  # validasi rate
    if not rate_revision:
        raise ValueError("rate_revision wajib dicatat (snapshot tarif transaksi)")
    lusin_exact = pcs_to_lusin(pcs)  # EXACT: pcs asal tidak dibulatkan
    wage_minor = round_to_minor(
        lusin_exact * minor_to_money(rate_per_lusin_minor),
        mode=policy.wage_money_rounding,
    )
    return {
        "pcs": pcs,
        "lusin_exact": str(lusin_exact),
        "rate_per_lusin_minor": rate_per_lusin_minor,
        "rate_revision": rate_revision,
        "wage_minor": wage_minor,
        "calculation_policy_ref": policy.policy_ref,
        "rounding_stage": policy.wage_money_rounding_stage,
    }


# ---------------------------------------------------------------------------
# Approved / paid / posted: tiga dimensi terpisah
# ---------------------------------------------------------------------------

#: Dimensi status transaksi. Approval TIDAK membuktikan uang berpindah;
#: payment TIDAK membuktikan jurnal posted; posting TIDAK membuktikan payment.
STATE_DIMENSIONS = ("approved", "paid", "posted")

#: Field bukti per dimensi status.
STATE_REF_FIELDS = {
    "approved": "approval_ref",
    "paid": "payment_ref",
    "posted": "posting_ref",
}


def validate_state_record(record: Mapping[str, Optional[str]]) -> dict:
    """Validasi record status tiga dimensi.

    Setiap dimensi memakai bukti (ref) sendiri: ``approval_ref``,
    ``payment_ref``, ``posting_ref`` — ketiganya opsional dan independen.
    Dua dimensi tidak boleh memakai ref bukti yang SAMA: memakai ref
    approval sebagai bukti payment adalah bug klasik "approved => paid".
    """
    refs = {dim: record.get(STATE_REF_FIELDS[dim]) for dim in STATE_DIMENSIONS}
    seen: dict[str, str] = {}
    for dim, ref in refs.items():
        if ref is None:
            continue
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError(f"{dim}_ref harus string non-kosong atau null")
        if ref in seen:
            raise ValueError(
                f"{dim}_ref memakai ulang bukti {seen[ref]}_ref ({ref!r}); "
                "approved/paid/posted adalah dimensi terpisah"
            )
        seen[ref] = dim
    return dict(record)


# ---------------------------------------------------------------------------
# Pencegahan hitung ganda: native vs snapshot
# ---------------------------------------------------------------------------

def dedupe_contributions(
    records: Iterable[Mapping],
) -> dict:
    """Agregasi kontribusi tanpa hitung ganda.

    Tiap record: ``canonical_transaction_id`` (identitas transaksi ekonomi),
    ``measure`` (ukuran laporan, mis. "qty_pcs" / "amount_minor"),
    ``amount`` (Decimal/int), ``source_kind``.
    Aturan: untuk satu (canonical_transaction_id, measure), kontribusi
    dihitung PALING BANYAK SATU. Bila native/imported sudah authoritative
    untuk transaksi yang dipetakan, snapshot pasangannya hanya untuk
    rekonsiliasi dan dikecualikan dari total.
    """
    winners: dict[tuple[str, str], Mapping] = {}
    excluded: list[Mapping] = []
    for rec in records:
        key = (rec["canonical_transaction_id"], rec["measure"])
        kind = rec["source_kind"]
        if kind not in SOURCE_KINDS:
            raise ValueError(f"source_kind tidak dikenal: {kind!r}")
        current = winners.get(key)
        if current is None:
            winners[key] = rec
            continue
        # native/imported mengalahkan snapshot untuk transaksi yang sama
        rank = {"native": 3, "imported_transaction": 3, "opening_balance": 2,
                "external_snapshot": 1}
        if rank[kind] > rank[current["source_kind"]]:
            excluded.append(current)
            winners[key] = rec
        else:
            excluded.append(rec)
    total = {}
    for (tx, measure), rec in winners.items():
        total[measure] = total.get(measure, 0) + rec["amount"]
    return {"total": total, "winners": list(winners.values()), "excluded": excluded}
