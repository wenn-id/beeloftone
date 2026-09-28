"""Modul perizinan kanonikal, pemetaan role, preset demo, dan helper pemisahan tugas (SoD).
Roadmap O01 / Issue #45.
"""
from typing import Any, Mapping, Sequence
from beeloft.store import DomainError

PERMISSIONS: tuple[str, ...] = (
    "read_operational",
    "create_transaction",
    "approve_transaction",
    "record_payment",
    "post_ledger",
    "export_data",
    "view_salary",
    "view_margin_profit",
    "manage_access",
)

# Fallback untuk akun yang belum punya baris izin granular sama sekali (mis. dibuat lewat
# jalur lama). Provisioning dan migrasi SELALU menulis baris eksplisit, jadi fallback ini
# hanya jaring aman; pengetatan nyata datang dari preset/penetapan admin yang tercatat di
# `user_access_events`.
ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "admin": (
        "read_operational", "create_transaction", "approve_transaction",
        "export_data", "manage_access",
    ),
    "operator": ("read_operational", "create_transaction"),
    "viewer": ("read_operational",),
}
DEFAULT_ROLE_PERMISSIONS = ROLE_PERMISSIONS
LEGACY_COMPATIBILITY_PERMISSIONS = PERMISSIONS

DEMO_PRESET_VERSION = "O01-DEMO-20260928-1"

PRESETS: dict[str, dict[str, Any]] = {
    "owner": {
        "label": "Pemilik Usaha (Superadmin)",
        "description": "Akses menyeluruh ke seluruh fungsi, seluruh unit usaha, payroll, dan margin untuk demonstrasi.",
        "permissions": PERMISSIONS,
        "all_units": True,
        "no_self_approval": True,
    },
    "operational_admin": {
        "label": "Admin Operasional",
        "description": "Pengelolaan operasional, transaksi, persetujuan, dan akses pengguna; tanpa akses gaji atau margin/laba.",
        "permissions": (
            "read_operational",
            "create_transaction",
            "approve_transaction",
            "export_data",
            "manage_access",
        ),
        "all_units": True,
        "no_self_approval": True,
    },
    "hr_payroll": {
        "label": "Staf HR & Payroll",
        "description": "Pengelolaan data karyawan, pengajuan dan persetujuan payroll serta rincian gaji; tanpa akses laba/margin atau pembayaran.",
        "permissions": (
            "read_operational",
            "create_transaction",
            "approve_transaction",
            "view_salary",
            "export_data",
        ),
        "all_units": True,
        "no_self_approval": True,
    },
    "finance": {
        "label": "Staf Keuangan",
        "description": "Pencatatan transaksi keuangan, posting buku besar, eksekusi pembayaran, dan analisis margin/laba; tanpa akses rincian gaji.",
        "permissions": (
            "read_operational",
            "create_transaction",
            "approve_transaction",
            "record_payment",
            "post_ledger",
            "view_margin_profit",
            "export_data",
        ),
        "all_units": True,
        "no_self_approval": True,
    },
    "production_operator": {
        "label": "Operator Produksi",
        "description": "Pencatatan produksi harian dalam cakupan unit kerja tertentu; tanpa hak persetujuan atau akses lintas unit.",
        "permissions": (
            "read_operational",
            "create_transaction",
        ),
        "all_units": False,
        "no_self_approval": True,
    },
    "management_viewer": {
        "label": "Manajemen (Viewer)",
        "description": "Pembacaan data operasional dan analisis laba/margin eksekutif; tanpa rincian gaji individual atau mutasi transaksi.",
        "permissions": (
            "read_operational",
            "view_margin_profit",
            "export_data",
        ),
        "all_units": True,
        "no_self_approval": True,
    },
    "auditor_viewer": {
        "label": "Auditor Internal",
        "description": "Pembacaan data operasional dan ekspor jejak audit untuk verifikasi kepatuhan.",
        "permissions": (
            "read_operational",
            "export_data",
        ),
        "all_units": True,
        "no_self_approval": True,
    },
}


def has_permission(actor: Mapping[str, Any] | None, permission: str) -> bool:
    if not actor:
        return False
    perms = actor.get("permissions")
    if perms is not None:
        return permission in perms
    role = actor.get("role")
    if role in ROLE_PERMISSIONS:
        return permission in ROLE_PERMISSIONS[role]
    return False


def require_permission(actor: Mapping[str, Any] | None, permission: str, message: str | None = None) -> None:
    if not actor:
        raise DomainError(401, "Autentikasi diperlukan.")
    if not has_permission(actor, permission):
        default_messages = {
            "view_salary": "Pengguna tidak memiliki izin untuk melihat data kompensasi atau payroll.",
            "view_margin_profit": "Pengguna tidak memiliki izin untuk melihat data margin atau laba.",
            "export_data": "Pengguna tidak memiliki izin untuk mengekspor data.",
            "approve_transaction": "Pengguna tidak memiliki izin untuk menyetujui transaksi.",
            "record_payment": "Pengguna tidak memiliki izin untuk mencatat pembayaran.",
            "post_ledger": "Pengguna tidak memiliki izin untuk melakukan posting buku besar.",
            "manage_access": "Pengguna tidak memiliki izin untuk mengelola akses pengguna.",
            "create_transaction": "Pengguna tidak memiliki izin untuk membuat atau mengubah transaksi.",
            "read_operational": "Pengguna tidak memiliki izin untuk membaca data operasional.",
        }
        err_msg = message or default_messages.get(permission, f"Pengguna tidak memiliki izin '{permission}'.")
        raise DomainError(403, err_msg)


def can_access_unit(actor: Mapping[str, Any] | None, unit_id: str | None) -> bool:
    if not actor:
        return False
    # Pengguna dengan all_units=True memiliki akses global ke seluruh unit dan record legacy
    if actor.get("all_units", True):
        return True
    # Pengguna dengan cakupan terbatas tidak boleh diam-diam mengakses record tanpa unit (legacy)
    if unit_id is None:
        return False
    assigned = actor.get("business_units") or []
    return unit_id in assigned


def require_unit_access(actor: Mapping[str, Any] | None, unit_id: str | None, message: str | None = None) -> None:
    if not actor:
        raise DomainError(401, "Autentikasi diperlukan.")
    if not can_access_unit(actor, unit_id):
        err_msg = message or "Pengguna tidak memiliki akses ke unit usaha tersebut."
        raise DomainError(403, err_msg)


def check_self_approval(actor: Mapping[str, Any] | None, creator_id: str | None, message: str | None = None) -> None:
    if not actor or not creator_id:
        return
    # Larangan menyetujui sendiri berlaku jika aktor memakai preset atau memiliki kebijakan no_self_approval
    enforce = actor.get("no_self_approval") or (actor.get("preset") is not None)
    if enforce and actor.get("id") == creator_id:
        err_msg = message or "Pembuat transaksi tidak boleh menyetujui pengajuannya sendiri (pemisahan tugas / no self-approval)."
        raise DomainError(403, err_msg)
