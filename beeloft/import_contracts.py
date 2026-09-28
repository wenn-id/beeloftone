"""Kontrak impor dan dry-run importer — X01 / issue #51.

Modul ini mengkodifikasi kontrak input impor sebagai fungsi murni tanpa efek
samping: tanpa DB, tanpa HTTP, tanpa perubahan schema. Dipakai oleh
``Store.import_dry_run`` / ``Store.apply_import_job`` (``beeloft/store.py``)
dan endpoint ``/api/import/*`` (``beeloft/api.py``).

Prinsip yang ditegakkan di sini:

- Identitas sumber memakai namespace F02 — tuple terstruktur
  ``(system, account, entity_type)`` + ``source_id`` opaque +
  ``source_line_id`` opsional + ``source_revision``. Nama orang/produk
  TIDAK PERNAH dipakai sebagai identitas pasti karena dapat bertabrakan.
- Uang selalu integer minor (tanpa float); tanggal bisnis ISO ``YYYY-MM-DD``
  tanpa konversi menjadi instant (zona operasional Asia/Jakarta).
- CSV (UTF-8, koma, boleh BOM) adalah satu-satunya format input. Batas
  10.000 baris / 5 MB konsisten dengan batas ekspor ``MAX_EXPORT_ROWS``.
- Satu job = satu adapter = satu sumber ``(system, account)``. Referensi
  antar-adapter diselesaikan terhadap database, bukan antar-baris CSV.
- Strategi histori vs opening balance adalah pilihan eksplisit per job
  (``replay_history`` | ``opening_balance`` | ``active_only``); tidak ada
  fallback yang menghitung keduanya.
- Domain downstream yang belum ada (payroll native, POS/payment, AP)
  dinyatakan eksplisit ``UNSUPPORTED`` / ``NOT_READY`` — modul ini tidak
  membuat tabel pengganti untuk mereka.

Status kontrak: DRAFT, menunggu business sign-off (A1/A2/A3) seperti F02.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date
from typing import Any, Mapping, Optional, Sequence

from beeloft.contracts import (
    canonical_source_key,
    money_to_minor,
    parse_money,
    source_namespace,
    validate_idempotency_key,
)


#: Revisi kontrak input impor X01. Naikkan bila kolom/aturan berubah dan
#: catat migrasi kolom di bawah CHANGELOG.
IMPORT_CONTRACT_VERSION = "X01-20260928-1"

#: Batas input — sama dengan batas ekspor (``MAX_EXPORT_ROWS`` di api.py).
MAX_IMPORT_ROWS = 10_000
#: Batas ukuran file CSV.
MAX_IMPORT_BYTES = 5 * 1024 * 1024

#: Pilihan strategi histori vs opening balance — wajib eksplisit per job.
JOB_STRATEGIES = ("replay_history", "opening_balance", "active_only")

#: Jenis baris dalam CSV.
ROW_KINDS = ("active", "history", "opening_balance")

#: Alasan reject per baris. Setiap alasan membawa pesan dan saran perbaikan
#: yang bisa ditindaklanjuti pemilik data sumber.
REJECT_REASONS: dict[str, dict[str, str]] = {
    "missing_required": {
        "message": "Kolom wajib kosong.",
        "fix": "Isi kolom tersebut di sistem sumber lalu ekspor ulang.",
    },
    "invalid_type": {
        "message": "Tipe data tidak sesuai kontrak kolom.",
        "fix": "Perbaiki format di CSV sesuai kamus kolom adapter.",
    },
    "invalid_money": {
        "message": "Nominal uang tidak valid (harus digit biasa, maks 2 desimal, tanpa pemisah ribuan).",
        "fix": "Tulis nominal sebagai angka biasa, mis. 15000 atau 15000.50.",
    },
    "negative_amount": {
        "message": "Nominal negatif tidak diterima pada kolom ini.",
        "fix": "Koreksi menjadi nol/positif, atau pindahkan ke adapter koreksi bila memang transaksi minus.",
    },
    "invalid_date": {
        "message": "Tanggal tidak valid (harus ISO YYYY-MM-DD).",
        "fix": "Tulis tanggal sebagai YYYY-MM-DD, mis. 2026-09-28.",
    },
    "invalid_unit": {
        "message": "Satuan tidak dikenal.",
        "fix": "Pakai kode satuan yang terdaftar di kontrak adapter.",
    },
    "invalid_row_kind": {
        "message": "row_kind tidak dikenal.",
        "fix": "Pakai salah satu: active, history, opening_balance.",
    },
    "invalid_revision": {
        "message": "source_revision harus bilangan bulat >= 1.",
        "fix": "Isi revision mulai dari 1; naikkan tiap ada perubahan payload.",
    },
    "duplicate_in_batch": {
        "message": "Identitas sumber duplikat dalam file yang sama.",
        "fix": "Hapus baris duplikat; bila payload berbeda, naikkan source_revision pada baris yang benar.",
    },
    "source_conflict": {
        "message": "Identitas sumber sudah pernah diimpor dengan payload berbeda tanpa revision eksplisit.",
        "fix": "Naikkan source_revision untuk menyatakan revisi baru, atau samakan payload dengan versi yang sudah diimpor.",
    },
    "orphan_reference": {
        "message": "Referensi tidak ditemukan (kode yatim).",
        "fix": "Impor master yang dirujuk lebih dulu, atau perbaiki kodenya.",
    },
    "ambiguous_reference": {
        "message": "Referensi cocok dengan lebih dari satu record (ambigu).",
        "fix": "Pakai mode resolusi 'code' yang unik, atau petakan manual lewat id_map.",
    },
    "empty_sku": {
        "message": "SKU kosong — produk tanpa identitas tidak boleh dibuat diam-diam.",
        "fix": "Isi SKU di sistem sumber; importer tidak membuat SKU pengganti.",
    },
    "duplicate_code": {
        "message": "Kode sudah dipakai record lain di database.",
        "fix": "Pakai kode lain, atau impor sebagai revisi bila ini memang record yang sama.",
    },
    "history_not_in_scope": {
        "message": "Baris histori/opening balance di luar cakupan strategi job.",
        "fix": "Ganti strategi job menjadi replay_history/opening_balance, atau keluarkan baris ini.",
    },
    "unknown_adapter": {
        "message": "Adapter tidak dikenal.",
        "fix": "Pilih adapter dari daftar yang didukung /api/import/adapters.",
    },
    "column_mismatch": {
        "message": "Jumlah kolom baris tidak sama dengan header.",
        "fix": "Samakan jumlah kolom tiap baris dengan header CSV.",
    },
    "file_too_large": {
        "message": "File melebihi batas ukuran/baris.",
        "fix": "Pecah menjadi beberapa file di bawah batas lalu impor berurutan.",
    },
    "empty_file": {
        "message": "File kosong atau tanpa baris data.",
        "fix": "Ekspor ulang dari sistem sumber.",
    },
    "unit_scope_denied": {
        "message": "Di luar cakupan unit usaha pengguna.",
        "fix": "Minta admin memberi akses unit tersebut, atau impor ke unit yang diizinkan.",
    },
    "revision_bump_pending_review": {
        "message": "Revisi payload butuh keputusan eksplisit pemilik data.",
        "fix": "Aktifkan auto_apply_revisions pada konfigurasi job, atau tinjau manual sebelum apply.",
    },
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INT_RE = re.compile(r"^[0-9]+$")


class ImportContractError(ValueError):
    """Kesalahan kontrak impor dengan alasan terstruktur."""

    def __init__(self, reason: str, message: str = "", field: str = ""):
        self.reason = reason
        self.field = field
        info = REJECT_REASONS.get(reason, {})
        super().__init__(message or info.get("message", reason))


def reject(field: str, reason: str, message: str = "") -> dict[str, str]:
    """Bangun satu entri reject per baris."""
    info = REJECT_REASONS.get(reason, {})
    return {
        "field": field,
        "reason": reason,
        "message": message or info.get("message", reason),
        "fix": info.get("fix", ""),
    }


# ---------------------------------------------------------------------------
# Adapter: kamus kolom per domain
# ---------------------------------------------------------------------------
#
# Tipe kolom:
#   code        teks identitas, wajib non-kosong bila required (case dipertahankan;
#               keunikan case-insensitive ditegakkan DB)
#   text        teks bebas (max 255)
#   integer     bilangan bulat non-negatif strict
#   money       teks nominal -> integer minor via kontrak F02 (negatif ditolak eksplisit)
#   date        ISO YYYY-MM-DD
#   bool01      0/1, true/false, ya/tidak, aktif/nonaktif
#   uom_unit    salah satu dari daftar unit yang diizinkan kolom itu
#   row_kind    active | history | opening_balance

def _col(type_: str, required: bool = False, **kw: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {"type": type_, "required": required}
    spec.update(kw)
    return spec


#: Spesifikasi adapter -> kamus kolom CSV dan metadata layanan.
#: ``entity_type`` dipakai pada namespace F02; ``service`` menunjuk fungsi
#: domain yang dipanggil saat apply (lihat Store._import_apply_row).
ADAPTERS: dict[str, dict[str, Any]] = {
    # --- M01: master katalog ------------------------------------------------
    "uom": {
        "label": "Satuan (UOM)",
        "entity_type": "uom",
        "service": "master",
        "master_kind": "uom",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "range_text": _col("text"),
            "note": _col("text"),
        },
        "references": {},
    },
    "product_category": {
        "label": "Kategori produk",
        "entity_type": "product_category",
        "service": "master",
        "master_kind": "product_category",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
        },
        "references": {},
    },
    "product_subcategory": {
        "label": "Subkategori produk",
        "entity_type": "product_subcategory",
        "service": "master",
        "master_kind": "product_subcategory",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "category_code": _col("code", True),
        },
        "references": {
            "category_code": {"table": "product_categories", "field": "category_id",
                              "label": "Kategori produk"},
        },
    },
    "product_type": {
        "label": "Tipe produk",
        "entity_type": "product_type",
        "service": "master",
        "master_kind": "product_type",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "subcategory_code": _col("code", True),
        },
        "references": {
            "subcategory_code": {"table": "product_subcategories", "field": "subcategory_id",
                                 "label": "Subkategori produk"},
        },
    },
    "product_series": {
        "label": "Seri produk",
        "entity_type": "product_series",
        "service": "master",
        "master_kind": "product_series",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
        },
        "references": {},
    },
    "color": {
        "label": "Warna",
        "entity_type": "color",
        "service": "master",
        "master_kind": "color",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
        },
        "references": {},
    },
    "size": {
        "label": "Ukuran",
        "entity_type": "size",
        "service": "master",
        "master_kind": "size",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "sort_order": _col("integer"),
        },
        "references": {},
    },
    "material_class": {
        "label": "Klasifikasi bahan",
        "entity_type": "material_class",
        "service": "master",
        "master_kind": "material_class",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "level": _col("integer", True),
            "parent_code": _col("code"),
        },
        "references": {
            "parent_code": {"table": "material_classes", "field": "parent_id",
                            "label": "Klasifikasi induk", "skip_when": {"level": 1}},
        },
    },
    # --- M02: unit usaha, storage, jabatan, employee, pihak ------------------
    "business_unit": {
        "label": "Unit usaha",
        "entity_type": "business_unit",
        "service": "business_unit",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "reason": _col("text", True),
        },
        "references": {},
    },
    "storage": {
        "label": "Gudang / lokasi penyimpanan",
        "entity_type": "storage",
        "service": "storage",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "kind": _col("text"),
            "business_unit_code": _col("code", True),
            "reason": _col("text", True),
        },
        "references": {
            "business_unit_code": {"table": "business_units", "field": "business_unit_id",
                                  "label": "Unit usaha", "unit_scoped": True},
        },
    },
    "position": {
        "label": "Jabatan",
        "entity_type": "position",
        "service": "position",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "reason": _col("text", True),
        },
        "references": {},
    },
    "employee": {
        "label": "Karyawan",
        "entity_type": "employee",
        "service": "employee",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "department": _col("text", True),
            "position_code": _col("code"),
            "business_unit_code": _col("code"),
            "reason": _col("text", True),
        },
        "references": {
            "position_code": {"table": "positions", "field": "position_id",
                              "label": "Jabatan"},
            "business_unit_code": {"table": "business_units", "field": "business_unit_id",
                                   "label": "Unit usaha", "unit_scoped": True},
        },
    },
    "customer": {
        "label": "Pelanggan (pihak)",
        "entity_type": "customer",
        "service": "customer",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "contact": _col("text"),
            "address": _col("text"),
            "reason": _col("text", True),
        },
        "references": {},
    },
    "supplier": {
        "label": "Supplier (pihak)",
        "entity_type": "supplier",
        "service": "supplier",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "contact": _col("text"),
            "address": _col("text"),
            "reason": _col("text", True),
        },
        "references": {},
    },
    # --- M01: produk & bahan -------------------------------------------------
    "product": {
        "label": "Produk",
        "entity_type": "product",
        "service": "product",
        "columns": {
            "sku": _col("code", True, empty_reason="empty_sku"),
            "name": _col("text", True),
            "color": _col("text"),
            "size": _col("text"),
            "category_code": _col("code"),
            "subcategory_code": _col("code"),
            "type_code": _col("code"),
            "series_code": _col("code"),
            "color_code": _col("code"),
            "size_code": _col("code"),
            "uom_code": _col("code"),
        },
        "references": {
            "category_code": {"table": "product_categories", "field": "category_id",
                              "label": "Kategori produk"},
            "subcategory_code": {"table": "product_subcategories", "field": "subcategory_id",
                                 "label": "Subkategori produk"},
            "type_code": {"table": "product_types", "field": "type_id",
                          "label": "Tipe produk"},
            "series_code": {"table": "product_series", "field": "series_id",
                             "label": "Seri produk"},
            "color_code": {"table": "colors", "field": "color_id",
                            "label": "Warna"},
            "size_code": {"table": "sizes", "field": "size_id",
                           "label": "Ukuran"},
            "uom_code": {"table": "uoms", "field": "uom_code",
                         "label": "Satuan", "resolve_column": "code"},
        },
    },
    "material": {
        "label": "Bahan baku",
        "entity_type": "material",
        "service": "material",
        "columns": {
            "code": _col("code", True),
            "name": _col("text", True),
            "unit": _col("uom_unit", True, allowed=("m", "kg", "pcs")),
            "class_code": _col("code"),
            "description": _col("text"),
            "reference_price": _col("money"),
        },
        "references": {
            "class_code": {"table": "material_classes", "field": "class_id",
                           "label": "Klasifikasi bahan"},
        },
    },
}

#: Domain downstream yang belum memiliki modul native. Status eksplisit —
#: importer TIDAK membuat tabel pengganti untuk mereka (keputusan #51).
UNSUPPORTED_DOMAINS: dict[str, dict[str, str]] = {
    "payroll": {
        "status": "UNSUPPORTED",
        "label": "Payroll native",
        "reason": "Modul payroll native dikerjakan pada #52; kontrak tarif/upah mengikuti F02.",
        "owner_issue": "#52",
    },
    "payroll_cash_receipt": {
        "status": "UNSUPPORTED",
        "label": "Kasbon / cash receipt payroll",
        "reason": "Mengikuti modul payroll native (#52).",
        "owner_issue": "#52",
    },
    "pos_invoice": {
        "status": "NOT_READY",
        "label": "POS invoice",
        "reason": "Belum ada modul POS native; mapping menyusul.",
        "owner_issue": "#61",
    },
    "pos_payment": {
        "status": "NOT_READY",
        "label": "POS payment",
        "reason": "Belum ada modul POS native; mapping menyusul.",
        "owner_issue": "#61",
    },
    "ap_settlement": {
        "status": "NOT_READY",
        "label": "AP settlement",
        "reason": "Belum ada modul AP native; mapping menyusul.",
        "owner_issue": "#61",
    },
    "service_template": {
        "status": "NOT_READY",
        "label": "Template jasa / tarif",
        "reason": "Kontrak template berversi tersedia (#48); adapter impor menyusul.",
        "owner_issue": "#61",
    },
}


def get_adapter(name: str) -> dict[str, Any]:
    """Ambil spesifikasi adapter; raise ImportContractError bila tak dikenal."""
    if name in UNSUPPORTED_DOMAINS:
        info = UNSUPPORTED_DOMAINS[name]
        raise ImportContractError(
            "unknown_adapter",
            f"Domain '{name}' berstatus {info['status']}: {info['reason']} "
            f"(lihat {info['owner_issue']}).",
            field="adapter",
        )
    try:
        return ADAPTERS[name]
    except KeyError:
        raise ImportContractError("unknown_adapter", field="adapter") from None


def adapter_catalog() -> list[dict[str, Any]]:
    """Daftar adapter yang didukung + domain yang belum didukung."""
    supported = [
        {"name": name, "label": spec["label"], "entity_type": spec["entity_type"],
         "columns": list(spec["columns"])}
        for name, spec in ADAPTERS.items()
    ]
    unsupported = [
        {"name": name, **info} for name, info in UNSUPPORTED_DOMAINS.items()
    ]
    return [{"supported": supported, "unsupported": unsupported,
             "contract_version": IMPORT_CONTRACT_VERSION,
             "limits": {"max_rows": MAX_IMPORT_ROWS,
                        "max_bytes": MAX_IMPORT_BYTES}}]


# ---------------------------------------------------------------------------
# Parsing CSV
# ---------------------------------------------------------------------------

def parse_csv_text(text: str, filename: str = "") -> list[dict[str, str]]:
    """Parse CSV (UTF-8, koma, BOM opsional) menjadi list baris dict.

    Melempar ImportContractError: empty_file, file_too_large, column_mismatch.
    """
    if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise ImportContractError("file_too_large", field="file")
    # BOM di awal file dibuang; BOM menempel pada header pertama juga dibersihkan.
    text = text.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(text), delimiter=",")
    header: Optional[list[str]] = None
    rows: list[dict[str, str]] = []
    for lineno, record in enumerate(reader, start=1):
        if header is None:
            header = [h.lstrip("\ufeff").strip() for h in record]
            if not any(header):
                raise ImportContractError("empty_file", field="file")
            continue
        if not any(cell.strip() for cell in record):
            continue  # baris kosong dilewati
        if len(record) != len(header):
            raise ImportContractError(
                "column_mismatch",
                f"Baris {lineno}: {len(record)} kolom, header {len(header)} kolom.",
                field="file",
            )
        if len(rows) >= MAX_IMPORT_ROWS:
            raise ImportContractError("file_too_large",
                                      f"Melebihi batas {MAX_IMPORT_ROWS} baris.",
                                      field="file")
        rows.append({h: (cell or "").strip() for h, cell in zip(header, record)})
    if not rows:
        raise ImportContractError("empty_file", field="file")
    return rows


# ---------------------------------------------------------------------------
# Validasi tipe kolom
# ---------------------------------------------------------------------------

def parse_money_field(raw: str) -> int:
    """Nominal teks -> integer minor. Negatif ditolak eksplisit (negative_amount)."""
    text = (raw or "").strip()
    if text.startswith("-"):
        raise ImportContractError("negative_amount", field="money")
    try:
        return money_to_minor(parse_money(text))
    except ValueError as exc:
        raise ImportContractError("invalid_money", str(exc), field="money") from exc


def parse_date_field(raw: str) -> str:
    """Tanggal ISO YYYY-MM-DD; kembalikan string kanonis."""
    text = (raw or "").strip()
    if not _DATE_RE.match(text):
        raise ImportContractError("invalid_date", field="date")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ImportContractError("invalid_date", str(exc), field="date") from exc
    return parsed.isoformat()


def parse_int_field(raw: str) -> int:
    text = (raw or "").strip()
    if not _INT_RE.match(text):
        raise ImportContractError("invalid_type",
                                  f"'{raw}' bukan bilangan bulat non-negatif.",
                                  field="integer")
    return int(text)


_BOOL_TRUE = {"1", "true", "ya", "aktif", "y"}
_BOOL_FALSE = {"0", "false", "tidak", "nonaktif", "t"}


def parse_bool_field(raw: str) -> int:
    text = (raw or "").strip().lower()
    if text in _BOOL_TRUE:
        return 1
    if text in _BOOL_FALSE:
        return 0
    raise ImportContractError("invalid_type",
                              f"'{raw}' bukan boolean (0/1, ya/tidak, aktif/nonaktif).",
                              field="bool")


def validate_column(field: str, spec: dict[str, Any], raw: str) -> Any:
    """Validasi satu nilai kolom; kembalikan nilai kanonis atau raise."""
    type_ = spec["type"]
    text = (raw or "").strip()
    if not text:
        if spec.get("required"):
            reason = spec.get("empty_reason", "missing_required")
            raise ImportContractError(reason, field=field)
        return None
    if type_ == "code":
        if len(text) > 64:
            raise ImportContractError("invalid_type",
                                      f"Kode '{field}' melebihi 64 karakter.",
                                      field=field)
        return text
    if type_ == "text":
        if len(text) > 255:
            raise ImportContractError("invalid_type",
                                      f"Kolom '{field}' melebihi 255 karakter.",
                                      field=field)
        return text
    if type_ == "integer":
        try:
            return parse_int_field(text)
        except ImportContractError as exc:
            exc.field = field
            raise
    if type_ == "money":
        try:
            return parse_money_field(text)
        except ImportContractError as exc:
            exc.field = field
            raise
    if type_ == "date":
        try:
            return parse_date_field(text)
        except ImportContractError as exc:
            exc.field = field
            raise
    if type_ == "bool01":
        try:
            return parse_bool_field(text)
        except ImportContractError as exc:
            exc.field = field
            raise
    if type_ == "uom_unit":
        allowed = spec.get("allowed", ())
        if text not in allowed:
            raise ImportContractError("invalid_unit",
                                      f"Satuan '{text}' tidak dikenal; pakai {', '.join(allowed)}.",
                                      field=field)
        return text
    if type_ == "row_kind":
        if text not in ROW_KINDS:
            raise ImportContractError("invalid_row_kind", field=field)
        return text
    raise ImportContractError("invalid_type", f"Tipe kolom '{type_}' tidak dikenal.",
                              field=field)


# ---------------------------------------------------------------------------
# Identitas sumber (namespace F02) dan konfigurasi job
# ---------------------------------------------------------------------------

def validate_source_identity(raw: Mapping[str, str]) -> tuple[dict[str, Any], list[dict]]:
    """Validasi kolom identitas per baris: source_id / source_line_id /
    source_revision / row_kind. Kembalikan (identity, errors)."""
    errors: list[dict] = []
    identity: dict[str, Any] = {}
    source_id = (raw.get("source_id") or "").strip()
    if not source_id:
        errors.append(reject("source_id", "missing_required"))
    elif len(source_id) > 128:
        errors.append(reject("source_id", "invalid_type",
                             "source_id melebihi 128 karakter."))
    else:
        identity["source_id"] = source_id
    source_line_id = (raw.get("source_line_id") or "").strip() or None
    if source_line_id and len(source_line_id) > 128:
        errors.append(reject("source_line_id", "invalid_type",
                             "source_line_id melebihi 128 karakter."))
    identity["source_line_id"] = source_line_id
    revision_raw = (raw.get("source_revision") or "").strip()
    if not revision_raw:
        identity["source_revision"] = 1
    else:
        try:
            revision = parse_int_field(revision_raw)
            if revision < 1:
                raise ImportContractError("invalid_revision", field="source_revision")
            identity["source_revision"] = revision
        except ImportContractError as exc:
            errors.append(reject("source_revision", "invalid_revision", str(exc)))
            identity["source_revision"] = 1
    row_kind = (raw.get("row_kind") or "").strip() or "active"
    if row_kind not in ROW_KINDS:
        errors.append(reject("row_kind", "invalid_row_kind"))
        row_kind = "active"
    identity["row_kind"] = row_kind
    return identity, errors


def validate_job_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validasi konfigurasi job; kembalikan config kanonis atau raise."""
    system = str(config.get("source_system") or "").strip()
    account = str(config.get("source_account") or "").strip()
    if not system or not account:
        raise ImportContractError("missing_required",
                                  "source_system dan source_account wajib diisi.",
                                  field="source_system")
    # Namespace F02: tuple terstruktur, bukan string concatenation.
    namespace = source_namespace(system, account, "__adapter__")
    strategy = str(config.get("strategy") or "active_only").strip()
    if strategy not in JOB_STRATEGIES:
        raise ImportContractError("invalid_type",
                                  f"strategy harus salah satu dari {', '.join(JOB_STRATEGIES)}.",
                                  field="strategy")
    column_map = dict(config.get("column_map") or {})
    id_map = {k: dict(v) for k, v in dict(config.get("id_map") or {}).items()}
    reference_mode = dict(config.get("reference_mode") or {})
    for field, mode in reference_mode.items():
        if mode not in ("code", "name"):
            raise ImportContractError("invalid_type",
                                      f"reference_mode '{field}' harus 'code' atau 'name'.",
                                      field="reference_mode")
    return {
        "source_system": namespace[0],
        "source_account": namespace[1],
        "strategy": strategy,
        "column_map": column_map,
        "id_map": id_map,
        "reference_mode": reference_mode,
        "auto_apply_revisions": bool(config.get("auto_apply_revisions", False)),
    }


def classify_row_kind(strategy: str, row_kind: str) -> tuple[str, Optional[dict]]:
    """Tentukan perlakuan baris berdasar strategi job.

    Kembalikan (disposition, reject_or_None) dengan disposition salah satu dari
    'apply' | 'archived' | 'rejected'.
    """
    if row_kind == "history":
        if strategy == "opening_balance":
            # Arsip histori: dicatat sebagai metadata job, TIDAK PERNAH
            # di-apply ke domain aktif.
            return "archived", None
        if strategy == "active_only":
            return "rejected", reject("row_kind", "history_not_in_scope")
        return "apply", None  # replay_history: replay eksplisit
    if row_kind == "opening_balance":
        if strategy == "opening_balance":
            return "apply", None
        return "rejected", reject("row_kind", "history_not_in_scope",
                                   "Baris opening_balance hanya berlaku pada strategi opening_balance.")
    return "apply", None


def canonical_key(system: str, account: str, entity_type: str,
                  source_id: str, source_line_id: Optional[str] = None
                  ) -> tuple[str, str, str, str, Optional[str]]:
    """Kunci kanonis sumber per kontrak F02 (tanpa revision)."""
    return canonical_source_key(system, account, entity_type, source_id, source_line_id)


def derive_idempotency_key(system: str, account: str, entity_type: str,
                           source_id: str,
                           source_line_id: Optional[str] = None,
                           revision: Optional[int] = None) -> str:
    """Turunkan idempotency key deterministik dari identitas sumber.

    source_id bersifat opaque (bisa mengandung karakter di luar alfabet key),
    jadi key = hash, bukan konkatenasi mentah. `revision` opsional membuat
    key revision-scoped untuk jalur update (revision bump) supaya tidak
    bertabrakan dengan key create identitas yang sama.
    """
    parts = [system, account, entity_type, source_id, source_line_id or ""]
    if revision is not None:
        parts.append(f"rev{int(revision)}")
    raw = "\x1f".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]
    key = f"import.{entity_type}.{digest}"
    return validate_idempotency_key(key)


def payload_fingerprint(payload: Mapping[str, Any]) -> str:
    """Fingerprint kanonis payload untuk deteksi konflik source identity."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_watermark(source_system: str, source_account: str,
                    cutoff: str, observed_at: str,
                    note: str = "") -> dict[str, Any]:
    """Bangun watermark delta impor.

    Watermark menandai batas observasi sumber (cutoff) agar delta berikutnya
    dapat diaudit. Ini BUKAN klaim cutover #61 selesai.
    """
    cutoff_date = parse_date_field(cutoff)
    return {
        "contract_version": IMPORT_CONTRACT_VERSION,
        "source_system": source_system,
        "source_account": source_account,
        "cutoff": cutoff_date,
        "observed_at": observed_at,
        "timezone": "Asia/Jakarta",
        "note": note,
        "cutover_61_complete": False,
    }


# ---------------------------------------------------------------------------
# Validasi baris + batch
# ---------------------------------------------------------------------------

def apply_column_map(raw: Mapping[str, str],
                     column_map: Mapping[str, str]) -> dict[str, str]:
    """Petakan nama kolom CSV ke nama kolom kontrak."""
    if not column_map:
        return dict(raw)
    reverse = {alias: canonical for canonical, alias in column_map.items()}
    # column_map: {canonical: alias_di_csv}
    out: dict[str, str] = {}
    for header, value in raw.items():
        out[reverse.get(header, header)] = value
    return out


def validate_row(adapter_name: str, raw: Mapping[str, str], row_no: int,
                 column_map: Optional[Mapping[str, str]] = None
                 ) -> tuple[dict[str, Any], list[dict]]:
    """Validasi satu baris CSV terhadap adapter.

    Kembalikan (fields, errors). fields = nilai kanonis kolom domain;
    errors = list entri reject().
    """
    spec = get_adapter(adapter_name)
    mapped = apply_column_map(raw, column_map or {})
    fields: dict[str, Any] = {}
    errors: list[dict] = []
    identity, identity_errors = validate_source_identity(mapped)
    errors.extend(identity_errors)
    for field, col_spec in spec["columns"].items():
        try:
            value = validate_column(field, col_spec, mapped.get(field, ""))
        except ImportContractError as exc:
            errors.append(reject(exc.field or field, exc.reason, str(exc)))
            continue
        if value is not None:
            fields[field] = value
    return {"identity": identity, "fields": fields}, errors


def check_batch_duplicates(rows: Sequence[dict[str, Any]]) -> list[dict]:
    """Deteksi identitas sumber duplikat dalam satu batch.

    rows: list {"key": canonical_key, "fingerprint": ...}.
    Kembalikan list {"row_no", "reason", "detail"} untuk baris bermasalah.
    Payload identik -> didedup (bukan error); payload beda -> source_conflict.
    """
    seen: dict[tuple, tuple[int, str]] = {}
    problems: list[dict] = []
    for row in rows:
        key = row["key"]
        if key in seen:
            first_no, first_fp = seen[key]
            if row["fingerprint"] == first_fp:
                problems.append({"row_no": row["row_no"], "duplicate_of": first_no,
                                 "identical": True})
            else:
                problems.append({"row_no": row["row_no"], "duplicate_of": first_no,
                                 "identical": False,
                                 "reason": "duplicate_in_batch"})
        else:
            seen[key] = (row["row_no"], row["fingerprint"])
    return problems


def control_totals(statuses: Sequence[str]) -> dict[str, int]:
    """Hitung control totals dari status baris."""
    totals = {"total": len(statuses), "will_create": 0, "will_map": 0,
              "rejected": 0, "quarantined": 0, "archived": 0,
              "applied": 0, "failed": 0}
    mapping = {"ok": "will_create", "mapped": "will_map", "rejected": "rejected",
               "quarantined": "quarantined", "archived": "archived",
               "applied": "applied", "failed": "failed"}
    for status in statuses:
        bucket = mapping.get(status)
        if bucket:
            totals[bucket] += 1
    return totals
