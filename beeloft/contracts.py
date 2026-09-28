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
from fractions import Fraction
from typing import Iterable, Mapping, Optional


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


def pcs_to_lusin(pcs: int) -> Fraction:
    """Konversi pcs -> lusin sebagai rasional eksak (``Fraction``).

    Tidak ada pembulatan diam-diam: 13 pcs = Fraction(13, 12), bukan
    Decimal yang terpotong presisinya. pcs asal SELALU disimpan; hasil
    konversi ini untuk kalkulasi/display, bukan pengganti data asal.
    """
    check_quantity(pcs)
    return Fraction(pcs, 12)


def lusin_to_pcs(lusin: Fraction) -> int:
    """Konversi lusin -> pcs; hanya untuk kelipatan eksak 12.

    Menolak nilai non-kelipatan daripada memotong diam-diam — keputusan
    pembulatan kuantitas upah adalah kebijakan, bukan konversi satuan.
    """
    if isinstance(lusin, int) and not isinstance(lusin, bool):
        lusin = Fraction(lusin)
    if not isinstance(lusin, Fraction):
        raise ValueError(f"lusin harus Fraction, diterima: {lusin!r}")
    pcs = lusin * 12
    if pcs.denominator != 1:
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


def divround(numer: int, denom: int, mode: str = "HALF_UP") -> int:
    """Pembagian integer dengan mode pembulatan eksplisit.

    Aritmatika tetap eksak (integer) sampai pembulatan akhir — tidak ada
    Decimal perantara yang memotong pecahan berulang (mis. 13/12).
    Mode: HALF_UP, DOWN, UP. ``denom`` harus positif.
    """
    if mode not in _ROUNDING_MODES:
        raise ValueError(f"mode pembulatan tidak dikenal: {mode!r}")
    if not isinstance(numer, int) or isinstance(numer, bool):
        raise ValueError(f"numer harus integer, diterima: {numer!r}")
    if not isinstance(denom, int) or isinstance(denom, bool) or denom <= 0:
        raise ValueError(f"denom harus integer positif, diterima: {denom!r}")
    quotient, remainder = divmod(numer, denom)
    if remainder == 0:
        return quotient
    if mode == "DOWN":
        return quotient
    if mode == "UP":
        return quotient + 1
    return quotient + (1 if 2 * remainder >= denom else 0)  # HALF_UP


def minor_fraction_to_money(value: Fraction, mode: str = "HALF_UP") -> str:
    """Tampilkan pecahan satuan minor (mis. tarif per pcs hasil konversi eksak
    ``Fraction(minor_lusin, 12)``) sebagai string uang 2 desimal.

    Khusus **DISPLAY**: pembulatan eksplisit ke presisi simpan dengan mode
    tercatat. Nilai authoritative tetap ``Fraction`` asli (``rate_per_pcs_exact``)
    atau integer minor pada basis perhitungan (``rate_per_lusin_minor``); hasil
    fungsi ini TIDAK boleh dipakai untuk perhitungan uang.
    """
    if not isinstance(value, Fraction):
        raise ValueError(f"nilai harus Fraction, diterima: {value!r}")
    if mode not in _ROUNDING_MODES:
        raise ValueError(f"mode pembulatan tidak dikenal: {mode!r}")
    minor = Decimal(value.numerator) / Decimal(value.denominator)
    rounded_minor = minor.to_integral_value(rounding=_ROUNDING_MODES[mode])
    return format(rounded_minor / MINOR_PER_UNIT, '.2f')


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
    #: dengan pcs/12 rasional eksak; kebijakan lain menunggu keputusan D04.
    wage_lusin_rounding: str = "EXACT"
    #: Mode pembulatan nominal upah.
    wage_money_rounding: str = "HALF_UP"
    #: Kelipatan pembulatan nominal upah dalam minor. 100 = rupiah penuh,
    #: 1 = sen/minor. Ini TERPISAH dari unit penyimpanan uang (minor):
    #: kebijakan boleh membulatkan ke kelipatan yang lebih kasar daripada
    #: presisi simpan.
    wage_rounding_multiple_minor: int = 100
    #: Tahap pembulatan nominal upah. Nilai yang dicatat harus sesuai cara
    #: fungsi dipakai: wage_for_realization melakukan tepat SATU pembulatan
    #: di akhir per realisasi ("final_per_realization"). Agregasi per
    #: pekerja/per jenis pekerjaan adalah keputusan pemanggil.
    wage_money_rounding_stage: str = "final_per_realization"
    #: Rasio maksimum potongan kasbon terhadap upah bruto per payroll.
    kasbon_max_deduction_ratio: str = "1.0"


#: DEMO_ASSUMPTION — asumsi sementara, sederhana dan konsisten, HANYA untuk
#: demo. Bukan fakta legacy, bukan kebijakan produksi yang disetujui.
#: Versi ini dirujuk hasil kalkulasi demo via ``calculation_policy_ref``.
DEMO_POLICY = ContractPolicy(
    policy_ref="DEMO-20260928-1",
    # DEMO_ASSUMPTION: upah = (pcs / 12) x tarif_per_lusin dihitung rasional
    # eksak (integer/Fraction) sampai pembulatan akhir; keputusan D04
    # (13 pcs dibayar berapa) belum final dan tidak diasumsikan di sini.
    wage_lusin_rounding="EXACT",
    # DEMO_ASSUMPTION: nominal upah dibulatkan HALF_UP ke RUPIAH PENUH
    # (kelipatan 100 minor), satu kali di akhir per realisasi; tahap/mode
    # final menunggu D04/D06.
    wage_money_rounding="HALF_UP",
    wage_rounding_multiple_minor=100,
    wage_money_rounding_stage="final_per_realization",
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

    Aritmatika eksak sampai akhir: upah = pcs x rate / 12 dihitung sebagai
    integer (``divround``), baru dibulatkan SEKALI ke kelipatan
    ``policy.wage_rounding_multiple_minor``. Tidak ada Decimal perantara
    yang memotong pecahan berulang.

    Mengembalikan dict dengan ``calculation_policy_ref`` agar konsumen tahu
    asumsi mana yang dipakai dan bisa menggantinya per versi kebijakan.
    """
    check_quantity(pcs)
    minor_to_money(rate_per_lusin_minor)  # validasi rate
    if not rate_revision:
        raise ValueError("rate_revision wajib dicatat (snapshot tarif transaksi)")
    multiple = policy.wage_rounding_multiple_minor
    if not isinstance(multiple, int) or isinstance(multiple, bool) or multiple <= 0:
        raise ValueError(f"wage_rounding_multiple_minor harus integer positif, diterima: {multiple!r}")
    lusin_exact = pcs_to_lusin(pcs)  # Fraction eksak, mis. 13/12
    # pcs * rate (integer minor*pcs) / 12 -> minor, dibulatkan ke kelipatan policy
    wage_minor = divround(pcs * rate_per_lusin_minor, 12 * multiple,
                          mode=policy.wage_money_rounding) * multiple
    return {
        "pcs": pcs,
        "lusin_exact": str(lusin_exact),
        "rate_per_lusin_minor": rate_per_lusin_minor,
        "rate_revision": rate_revision,
        "wage_minor": wage_minor,
        "calculation_policy_ref": policy.policy_ref,
        "rounding_mode": policy.wage_money_rounding,
        "rounding_multiple_minor": multiple,
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

#: Peringkat otoritas sumber untuk satu transaksi ekonomi yang sama.
#: native/imported yang sudah authoritative mengalahkan snapshot (yang
#: kemudian hanya untuk rekonsiliasi) — ini aturan kontrak yang
#: terdokumentasi, bukan "record pertama menang".
_AUTHORITY_RANK = {
    "native": 3,
    "imported_transaction": 3,
    "opening_balance": 2,
    "external_snapshot": 1,
}


def dedupe_contributions(
    records: Iterable[Mapping],
) -> dict:
    """Agregasi kontribusi tanpa hitung ganda, dengan deteksi konflik eksplisit.

    Tiap record: ``canonical_transaction_id`` (identitas transaksi ekonomi),
    ``measure`` (ukuran laporan, mis. "qty_pcs" / "amount_minor"),
    ``amount`` (int/Decimal), ``source_kind``.

    Seluruh record dikelompokkan berdasarkan (canonical_transaction_id,
    measure) TERLEBIH DAHULU — hasil tidak bergantung urutan input. Di dalam
    tiap kelompok:
    - periksa konflik nominal pada SETIAP peringkat otoritas sebelum memilih
      pemenang: dua record berotoritas setara dengan nominal berbeda adalah
      KONFLIK dan raise ValueError, meskipun ada record berotoritas lebih
      tinggi di kelompok yang sama.
    - pemenang = peringkat otoritas tertinggi (aturan kontrak:
      native/imported authoritative mengalahkan snapshot, yang kemudian hanya
      untuk rekonsiliasi).
    - replay identik (nominal sama dengan pemenang) -> dideduplikasi ke
      ``excluded``.
    - peringkat lebih rendah dengan nominal berbeda -> dicatat eksplisit di
      ``superseded`` untuk rekonsiliasi, bukan hilang diam-diam.
    """
    groups: dict[tuple[str, str], list[Mapping]] = {}
    for rec in records:
        kind = rec["source_kind"]
        if kind not in SOURCE_KINDS:
            raise ValueError(f"source_kind tidak dikenal: {kind!r}")
        key = (rec["canonical_transaction_id"], rec["measure"])
        groups.setdefault(key, []).append(rec)
    winners: list[Mapping] = []
    excluded: list[dict] = []
    superseded: list[dict] = []
    for key, grouped in groups.items():
        by_rank: dict[int, list[Mapping]] = {}
        for rec in grouped:
            by_rank.setdefault(_AUTHORITY_RANK[rec["source_kind"]], []).append(rec)
        for rank, ranked in sorted(by_rank.items()):
            amounts = {rec["amount"] for rec in ranked}
            if len(amounts) > 1:
                raise ValueError(
                    "konflik dedup: dua record otoritas setara "
                    f"(peringkat {rank}) untuk {key} dengan nominal berbeda "
                    f"({sorted(amounts)}); butuh rekonsiliasi, tidak boleh "
                    "dideduplikasi diam-diam"
                )
        top_rank = max(by_rank)
        winner = by_rank[top_rank][0]  # nominal seragam di peringkat ini
        winners.append(winner)
        for rec in by_rank[top_rank][1:]:
            excluded.append({"record": rec, "reason": "identical_replay"})
        for rank in sorted(by_rank):
            if rank == top_rank:
                continue
            for rec in by_rank[rank]:
                if rec["amount"] == winner["amount"]:
                    excluded.append({"record": rec, "reason": "identical_replay"})
                else:
                    superseded.append({"record": rec,
                                       "reason": "superseded_by_authoritative",
                                       "winner": winner})
    total: dict[str, object] = {}
    for rec in winners:
        total[rec["measure"]] = total.get(rec["measure"], 0) + rec["amount"]
    return {"total": total, "winners": winners,
            "excluded": excluded, "superseded": superseded}
