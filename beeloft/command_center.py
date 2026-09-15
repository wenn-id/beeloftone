from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal


JAKARTA = timezone(timedelta(hours=7))


def build_command_center(store):
    generated = datetime.now(timezone.utc)
    today = generated.astimezone(JAKARTA).date()
    production = store.production_board(limit=1)
    approvals = store.approvals(limit=500, status="pending")
    integrations = store.integrations()
    sales = store.jubelio_order_summary()
    inventory = store.jubelio_stock_reconciliation()
    finance = store.mekari_finance_summary()
    payables = store.mekari_payables_summary()
    receivables = store.mekari_receivables_summary()
    replenishment = store.replenishment_recommendations(today, limit=25)
    quality = store.production_quality_insights(
        today, window_days=30, warning_percent=5,
        change_threshold=1, status="attention", limit=25
    )
    capacity = store.capacity_plan(
        today, horizon_days=14, warning_percent=80,
        status="all", limit=100
    )
    employees = store.employees(status="active", limit=1_000_000_000)
    attendance = store.attendance_records(today, today, limit=1_000_000_000)

    production_summary = production["summary"]
    approval_kinds = Counter(row["kind"] for row in approvals)
    approval_amount = sum(
        (Decimal(row["amount"]) for row in approvals if row.get("amount")), Decimal()
    )
    integration_attention = sum(row["attention_count"] for row in integrations["systems"])
    stock_summary = inventory["summary"]
    payable_summary = payables["summary"]
    receivable_summary = receivables["summary"]
    replenishment_summary = replenishment["summary"]
    quality_summary = quality["summary"]
    capacity_summary = capacity["summary"]
    active_ids = {row["id"] for row in employees["items"]}
    attendance_rows = [row for row in attendance["items"]
                       if row["employee_id"] in active_ids]
    workforce = {
        "as_of": today.isoformat(),
        "active_employees": employees["total"],
        "recorded_employees": len(attendance_rows),
        "unrecorded_employees": employees["total"] - len(attendance_rows),
        "present": sum(row["status"] == "present" for row in attendance_rows),
        "leave": sum(row["status"] == "leave" for row in attendance_rows),
        "absent": sum(row["status"] == "absent" for row in attendance_rows),
        "work_minutes": sum(row["work_minutes"] for row in attendance_rows),
        "overtime_minutes": sum(row["overtime_minutes"] for row in attendance_rows),
    }

    attention = []

    def add(item_id, priority, kind, title, detail, action, action_label):
        attention.append({
            "id": item_id, "priority": priority, "kind": kind, "title": title,
            "detail": detail, "action": action, "action_label": action_label,
        })

    if production_summary["overdue"]:
        add("production-overdue", "critical", "production", "Order melewati target",
            f'{production_summary["overdue"]} order masih aktif setelah tanggal target.',
            "production_overdue", "Lihat order overdue")
    if production["open_issues"]:
        add("production-issues", "critical", "production", "Kendala produksi terbuka",
            f'{production["open_issues"]} kendala masih menunggu penyelesaian.',
            "production_issues", "Lihat order terkendala")
    if workforce["unrecorded_employees"]:
        workforce_priority = "critical" if not workforce["recorded_employees"] else "warning"
        add("workforce-incomplete", workforce_priority, "people", "Kehadiran belum lengkap",
            f'{workforce["unrecorded_employees"]} dari {workforce["active_employees"]} '
            f'karyawan aktif belum dicatat untuk {workforce["as_of"]}.',
            "workforce", "Buka roster People")
    if workforce["absent"]:
        add("workforce-absence", "warning", "people", "Karyawan absen hari ini",
            f'{workforce["absent"]} karyawan tercatat absen pada {workforce["as_of"]}.',
            "workforce", "Buka roster People")
    if replenishment_summary["out_of_stock"]:
        add("inventory-out", "critical", "inventory", "SKU kehabisan stok",
            f'{replenishment_summary["out_of_stock"]} SKU dengan demand aktif tidak punya stok tersedia.',
            "replenishment", "Buka rekomendasi stok")
    if payable_summary["overdue_count"]:
        add("payables-overdue", "critical", "finance", "Utang melewati jatuh tempo",
            f'{payable_summary["overdue_count"]} invoice senilai Rp{payable_summary["overdue_amount"]} overdue.',
            "mekari_payables", "Lihat utang Mekari")
    if approvals:
        add("approvals-pending", "warning", "approval", "Keputusan menunggu",
            f"{len(approvals)} pengajuan senilai Rp{format(approval_amount, '.2f')} ada di inbox.",
            "approvals", "Buka inbox approval")
    if quality["items"]:
        top_quality = quality["items"][0]
        current_quality = top_quality["current"]
        subject = top_quality["assignee"] + (" (vendor makloon)" if
            top_quality["assignment_type"] == "makloon" else " (line internal)")
        change = top_quality["nonconforming_rate_change_points"]
        comparison = (f"naik {change} poin dari periode sebelumnya" if change is not None
                      and Decimal(change) > 0 else f'melewati batas {quality["warning_percent"]}%')
        add("production-quality", "warning", "quality", f"Kualitas {subject} perlu perhatian",
            f'Rework + reject {current_quality["nonconforming_rate_percent"]}% dari '
            f'{current_quality["inspected_quantity"]} pcs; {comparison}.',
            "production_quality", "Buka analisis kualitas")
    capacity_risks = (capacity_summary["overloaded_work_centers"]
                      + capacity_summary["deadline_risk_work_centers"])
    if capacity_risks:
        add("production-capacity-risk", "critical", "capacity", "Kapasitas produksi berisiko",
            f'{capacity_summary["overloaded_work_centers"]} work center overload dan '
            f'{capacity_summary["deadline_risk_work_centers"]} berisiko deadline; '
            f'{capacity_summary["at_risk_orders"]} order tidak cukup kapasitas sebelum target.',
            "production_capacity", "Buka rencana kapasitas")
    elif capacity_summary["near_capacity_work_centers"]:
        add("production-capacity-near", "warning", "capacity", "Kapasitas mendekati batas",
            f'{capacity_summary["near_capacity_work_centers"]} work center mencapai sedikitnya '
            f'{capacity["warning_percent"]}% utilisasi dalam 14 hari.',
            "production_capacity", "Buka rencana kapasitas")
    if capacity_summary["coverage_gaps"]:
        add("production-capacity-coverage", "warning", "data_quality",
            "Standar kapasitas belum lengkap",
            f'{capacity_summary["coverage_gaps"]} kebutuhan tahap untuk '
            f'{capacity_summary["missing_standard_quantity"]} pcs belum punya standar aktif.',
            "production_capacity", "Lengkapi standar kapasitas")
    stockout_soon = (replenishment_summary["stockout_before_replenishment"]
                     + replenishment_summary["below_safety_stock"])
    if stockout_soon:
        add("inventory-risk", "warning", "inventory", "Risiko stockout",
            f"{stockout_soon} SKU berada di bawah batas replenishment atau safety stock.",
            "replenishment", "Buka rekomendasi stok")
    if replenishment_summary["materials_to_purchase"]:
        add("materials-shortage", "warning", "inventory", "Bahan perlu dibeli",
            f'{replenishment_summary["materials_to_purchase"]} bahan belum tercakup stok, PR, atau PO aktif.',
            "replenishment", "Lihat kebutuhan bahan")
    mismatch_count = (stock_summary["mismatched"] + stock_summary["missing_from_snapshot"]
                      + stock_summary["quarantined"])
    if mismatch_count:
        add("inventory-mismatch", "warning", "data_quality", "Stok perlu direkonsiliasi",
            f"{mismatch_count} mapping atau record stok Jubelio tidak cocok.",
            "jubelio_stock", "Buka rekonsiliasi stok")
    if receivable_summary["overdue_count"]:
        add("receivables-overdue", "warning", "finance", "Piutang melewati jatuh tempo",
            f'{receivable_summary["overdue_count"]} invoice senilai Rp{receivable_summary["overdue_amount"]} overdue.',
            "mekari_receivables", "Lihat piutang Mekari")
    for system in integrations["systems"]:
        if system["attention_count"]:
            add(f'integration-{system["system"]}', "warning", "integration",
                f'{system["label"]} perlu perhatian',
                f'{system["attention_count"]} scope gagal, stale, atau belum pernah sinkron.',
                "integrations", "Lihat kesehatan integrasi")

    priority = {"critical": 0, "warning": 1, "info": 2}
    attention.sort(key=lambda row: (priority[row["priority"]], row["id"]))
    finance_current = finance["current"]
    return {
        "generated_at": generated.isoformat(),
        "status": {
            "state": "attention" if attention else "clear",
            "attention_count": len(attention),
            "critical_count": sum(row["priority"] == "critical" for row in attention),
        },
        "production": {
            "active_orders": production_summary["active"],
            "overdue_orders": production_summary["overdue"],
            "in_progress_quantity": production_summary["in_progress"],
            "rework_quantity": production_summary["rework"],
            "open_issues": production["open_issues"],
        },
        "quality": {
            "as_of": quality["as_of"],
            "period_start": quality["current_period_start"],
            "inspected_quantity": quality_summary["inspected_quantity"],
            "first_pass_yield_percent": quality_summary["first_pass_yield_percent"],
            "nonconforming_rate_percent": quality_summary["nonconforming_rate_percent"],
            "rework_rate_percent": quality_summary["rework_rate_percent"],
            "reject_rate_percent": quality_summary["reject_rate_percent"],
            "groups": quality_summary["groups"],
            "attention_groups": quality_summary["attention_groups"],
        },
        "capacity": {
            "as_of": capacity["as_of"],
            "horizon_end": capacity["horizon_end"],
            "capacity_complete": capacity["capacity_complete"],
            "required_minutes": capacity_summary["required_minutes"],
            "available_minutes": capacity_summary["available_minutes"],
            "work_centers": capacity_summary["work_centers"],
            "attention_work_centers": capacity_summary["attention_work_centers"],
            "overloaded_work_centers": capacity_summary["overloaded_work_centers"],
            "deadline_risk_work_centers": capacity_summary["deadline_risk_work_centers"],
            "near_capacity_work_centers": capacity_summary["near_capacity_work_centers"],
            "at_risk_orders": capacity_summary["at_risk_orders"],
            "coverage_gaps": capacity_summary["coverage_gaps"],
            "missing_standard_quantity": capacity_summary["missing_standard_quantity"],
        },
        "workforce": workforce,
        "approvals": {
            "pending_count": len(approvals),
            "pending_amount": format(approval_amount, ".2f"),
            "by_kind": {kind: approval_kinds.get(kind, 0) for kind in (
                "purchase_request", "purchase_order", "supplier_payment", "marketing_budget",
                "production_change", "ai_action")},
        },
        "inventory": {
            "snapshot_at": inventory["snapshot"]["snapshot_at"] if inventory["snapshot"] else None,
            **stock_summary,
            "out_of_stock": replenishment_summary["out_of_stock"],
            "at_risk": stockout_soon,
            "materials_to_purchase": replenishment_summary["materials_to_purchase"],
            "recommended_production_quantity": replenishment_summary["recommended_production_quantity"],
            "coverage_complete": replenishment["coverage_complete"],
        },
        "sales": {
            "snapshot_at": sales["snapshot"]["snapshot_at"] if sales["snapshot"] else None,
            **sales["summary"],
        },
        "finance": {
            "snapshot_at": finance["snapshot"]["snapshot_at"] if finance["snapshot"] else None,
            "current": finance_current,
            "payables": {
                "snapshot_at": payables["snapshot"]["snapshot_at"] if payables["snapshot"] else None,
                "outstanding": payable_summary["total_outstanding"],
                "overdue_count": payable_summary["overdue_count"],
                "overdue_amount": payable_summary["overdue_amount"],
                "due_next_7_days_amount": payable_summary["due_next_7_days_amount"],
            },
            "receivables": {
                "snapshot_at": receivables["snapshot"]["snapshot_at"] if receivables["snapshot"] else None,
                "outstanding": receivable_summary["total_outstanding"],
                "overdue_count": receivable_summary["overdue_count"],
                "overdue_amount": receivable_summary["overdue_amount"],
                "due_next_7_days_amount": receivable_summary["due_next_7_days_amount"],
            },
        },
        "integrations": {
            "attention_count": integration_attention,
            "systems": [{"system": row["system"], "label": row["label"],
                         "health": row["health"], "attention_count": row["attention_count"]}
                        for row in integrations["systems"]],
        },
        "attention": attention,
    }
