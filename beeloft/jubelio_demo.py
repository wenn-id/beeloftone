"""
Jubelio Demo connector simulation provider.
Generates deterministic synthetic commerce data (apparel products, stock, orders, returns, listings)
and executes sync through existing internal snapshot ingestion contracts.
"""

from contextlib import closing
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import sqlite3
from typing import Any, Dict, List, Optional
from uuid import uuid4

from beeloft.store import Store, DomainError, now

DEMO_ANCHOR_UTC = "2026-09-28T00:00:00+00:00"
ANCHOR_DT = datetime.fromisoformat(DEMO_ANCHOR_UTC)


class JubelioDemoDataset:
    @staticmethod
    def products() -> List[Dict[str, Any]]:
        """Returns 30 apparel SKUs. 28 are mapped, 2 unmapped for quarantine."""
        models = [
            ("LUNA", "Piyama Katun Anak Luna", ["Navy", "Sage", "Terracotta"], ["S", "M"]),
            ("MILO", "Kaos Polos Katun Milo", ["Mustard", "Dusty Pink"], ["S", "M", "L"]),
            ("KIKO", "Kemeja Flanel Anak Kiko", ["Navy", "Terracotta", "Mustard"], ["S", "M"]),
            ("CACA", "Dress Ruffle Anak Caca", ["Sage", "Dusty Pink"], ["S", "M", "L"]),
            ("BIMO", "Celana Chino Anak Bimo", ["Navy", "Terracotta"], ["S", "M", "L"]),
        ]
        items = []
        ext_counter = 1
        for code, name, colors, sizes in models:
            for color in colors:
                for size in sizes:
                    if code == "BIMO" and size == "L" and color == "Navy":
                        sku = "DEMO-BIMO-PANTS-L"
                        is_mapped = False
                    elif code == "CACA" and size == "S" and color == "Sage":
                        sku = "DEMO-CACA-DRESS-S"
                        is_mapped = False
                    else:
                        sku = f"DEMO-{code}-{color.upper().replace(' ', '')}-{size}"
                        is_mapped = True

                    ext_id = f"JUB-EXT-{ext_counter:03d}"
                    ext_sku = f"JUB-SKU-{code}-{color.upper()}-{size}"

                    items.append({
                        "sku": sku,
                        "name": f"{name} {color} {size}",
                        "color": color,
                        "size": size,
                        "external_id": ext_id,
                        "external_sku": ext_sku,
                        "is_mapped": is_mapped,
                        "base_price": Decimal("65000.00") if code in ("MILO", "LUNA") else Decimal("85000.00")
                    })
                    ext_counter += 1
        return items

    @classmethod
    def generate_baseline(cls) -> Dict[str, Any]:
        """Generates baseline dataset: 30 stock items, 120 orders, 30 listings, 4 returns."""
        prods = cls.products()
        # 1. Stock items (all 30 items)
        stock_items = []
        for i, p in enumerate(prods):
            sellable = 60 + (i * 7) % 140
            reserved = (i * 3) % 15
            if reserved > sellable:
                reserved = sellable // 4
            stock_items.append({
                "external_id": p["external_id"],
                "external_sku": p["external_sku"],
                "sellable_quantity": sellable,
                "reserved_quantity": reserved,
            })

        # 2. Orders (120 orders across 30 days prior to ANCHOR_DT)
        marketplaces = ["Shopee", "Tokopedia", "TikTok Shop"]
        orders = []
        for o_idx in range(1, 121):
            mp = marketplaces[o_idx % len(marketplaces)]
            day_offset = 29 - (o_idx * 29 // 120)
            order_time = (ANCHOR_DT - timedelta(days=day_offset, hours=(o_idx % 24), minutes=(o_idx * 7 % 60))).isoformat()
            
            # Status distribution: 80 completed, 20 processing, 15 pending, 5 cancelled
            if o_idx <= 80:
                status = "completed"
            elif o_idx <= 100:
                status = "processing"
            elif o_idx <= 115:
                status = "pending"
            else:
                status = "cancelled"

            # Deterministic lines per order
            line_count = 1 if (o_idx % 3 != 0) else 2
            lines = []
            for l_idx in range(line_count):
                p = prods[(o_idx + l_idx * 7) % len(prods)]
                qty = 1 if (o_idx + l_idx) % 4 != 0 else 2
                gross_rev = format(p["base_price"] * qty, ".2f")
                lines.append({
                    "external_id": p["external_id"],
                    "external_sku": p["external_sku"],
                    "quantity": qty,
                    "gross_revenue": gross_rev,
                })

            orders.append({
                "external_order_id": f"JUB-ORD-2026-{o_idx:04d}",
                "external_order_reference": f"ORD/{mp[:3].upper()}/202609/{o_idx:04d}",
                "marketplace": mp,
                "status": status,
                "ordered_at": order_time,
                "lines": lines,
            })

        # 3. Listings (30 listings)
        listings = []
        for i, p in enumerate(prods):
            mp = marketplaces[i % len(marketplaces)]
            status = "active" if i < 26 else "inactive"
            price = format(p["base_price"] + Decimal("5000.00"), ".2f")
            listings.append({
                "external_listing_id": f"JUB-LST-{i+1:04d}",
                "listing_reference": f"LST-{mp[:3].upper()}-{p['external_sku']}",
                "external_id": p["external_id"],
                "external_sku": p["external_sku"],
                "marketplace": mp,
                "listing_title": f"Baju Anak {p['name']} - Koleksi Beeloft",
                "status": status,
                "listed_price": price,
                "updated_at": (ANCHOR_DT - timedelta(days=15)).isoformat(),
            })

        # 4. Returns (4 returns referencing completed baseline orders)
        completed_orders = [o for o in orders if o["status"] == "completed"]
        returns = []
        ret_configs = [
            ("received", "0.00"),
            ("refunded", "75000.00"),
            ("requested", "0.00"),
            ("refunded", "85000.00"),
        ]
        for r_idx, (r_status, r_amount) in enumerate(ret_configs):
            ref_order = completed_orders[r_idx * 5]
            first_line = ref_order["lines"][0]
            if r_status == "refunded":
                r_amount = first_line["gross_revenue"]
            returns.append({
                "external_return_id": f"JUB-RET-2026-{r_idx+1:04d}",
                "external_return_reference": f"RET/{ref_order['marketplace'][:3].upper()}/{r_idx+1:04d}",
                "external_order_id": ref_order["external_order_id"],
                "external_order_reference": ref_order["external_order_reference"],
                "marketplace": ref_order["marketplace"],
                "status": r_status,
                "updated_at": (ANCHOR_DT - timedelta(days=2)).isoformat(),
                "refund_amount": r_amount,
                "lines": [{
                    "external_id": first_line["external_id"],
                    "external_sku": first_line["external_sku"],
                    "quantity": 1,
                }],
            })

        return {
            "items": stock_items,
            "orders": orders,
            "listings": listings,
            "returns": returns,
        }

    @classmethod
    def generate_scenario_2(cls) -> Dict[str, Any]:
        """
        Generates scenario 2: full cumulative dataset.
        Total 145 orders (120 original with status progressions + 25 new orders),
        updated stock decrements, 6 returns total.
        """
        baseline = cls.generate_baseline()
        prods = cls.products()
        marketplaces = ["Shopee", "Tokopedia", "TikTok Shop"]

        # Progress statuses of baseline orders
        orders = []
        for o in baseline["orders"]:
            o_copy = dict(o)
            if o_copy["status"] == "pending":
                o_num = int(o_copy["external_order_id"].split("-")[-1])
                o_copy["status"] = "processing" if o_num % 2 == 0 else "completed"
            elif o_copy["status"] == "processing":
                o_copy["status"] = "completed"
            orders.append(o_copy)

        # Append 25 new orders (orders 121..145) on 2026-09-28 and 2026-09-29
        sold_quantities: Dict[str, int] = {}
        for o_idx in range(121, 146):
            mp = marketplaces[o_idx % len(marketplaces)]
            day_offset = 0 if o_idx < 135 else 1
            order_time = (ANCHOR_DT + timedelta(days=day_offset, hours=(o_idx % 12), minutes=(o_idx * 11 % 60))).isoformat()
            status = "pending" if o_idx >= 138 else "processing"
            
            p = prods[o_idx % len(prods)]
            qty = 1 if o_idx % 3 != 0 else 2
            gross_rev = format(p["base_price"] * qty, ".2f")
            sold_quantities[p["external_id"]] = sold_quantities.get(p["external_id"], 0) + qty

            orders.append({
                "external_order_id": f"JUB-ORD-2026-{o_idx:04d}",
                "external_order_reference": f"ORD/{mp[:3].upper()}/202609/{o_idx:04d}",
                "marketplace": mp,
                "status": status,
                "ordered_at": order_time,
                "lines": [{
                    "external_id": p["external_id"],
                    "external_sku": p["external_sku"],
                    "quantity": qty,
                    "gross_revenue": gross_rev,
                }],
            })

        # Stock update: decrement sellable for sold units
        items = []
        for item in baseline["items"]:
            it_copy = dict(item)
            sold = sold_quantities.get(it_copy["external_id"], 0)
            it_copy["sellable_quantity"] = max(0, it_copy["sellable_quantity"] - sold)
            if it_copy["reserved_quantity"] > it_copy["sellable_quantity"]:
                it_copy["reserved_quantity"] = it_copy["sellable_quantity"]
            items.append(it_copy)

        # 2 additional returns (total 6 returns)
        returns = list(baseline["returns"])
        new_return_candidates = [o for o in orders if o["status"] == "completed" and int(o["external_order_id"].split("-")[-1]) > 50]
        for add_idx, (r_status, r_amount) in enumerate([("received", "0.00"), ("refunded", "65000.00")]):
            ret_idx = len(returns) + 1
            ref_order = new_return_candidates[add_idx * 7]
            first_line = ref_order["lines"][0]
            if r_status == "refunded":
                r_amount = first_line["gross_revenue"]
            returns.append({
                "external_return_id": f"JUB-RET-2026-{ret_idx:04d}",
                "external_return_reference": f"RET/{ref_order['marketplace'][:3].upper()}/{ret_idx:04d}",
                "external_order_id": ref_order["external_order_id"],
                "external_order_reference": ref_order["external_order_reference"],
                "marketplace": ref_order["marketplace"],
                "status": r_status,
                "updated_at": (ANCHOR_DT + timedelta(days=1)).isoformat(),
                "refund_amount": r_amount,
                "lines": [{
                    "external_id": first_line["external_id"],
                    "external_sku": first_line["external_sku"],
                    "quantity": 1,
                }],
            })

        return {
            "items": items,
            "orders": orders,
            "listings": baseline["listings"],
            "returns": returns,
        }


class JubelioDemoManager:
    """Orchestrates Jubelio Demo state, database concurrency lock, and ingestion execution."""
    def __init__(self, store: Store):
        self.store = store
        self.ensure_table()

    def ensure_table(self):
        """Ensures the jubelio_demo_state table exists."""
        with closing(self.store.connect()) as db:
            db.execute("""
            CREATE TABLE IF NOT EXISTS jubelio_demo_state (
                id TEXT PRIMARY KEY,
                is_demo INTEGER NOT NULL CHECK(is_demo IN (0,1)),
                current_scenario INTEGER NOT NULL CHECK(current_scenario >= 0),
                is_locked INTEGER NOT NULL CHECK(is_locked IN (0,1)),
                lock_expires_at TEXT NOT NULL DEFAULT '',
                last_synced_at TEXT NOT NULL DEFAULT '',
                last_status TEXT NOT NULL DEFAULT 'idle',
                last_error TEXT NOT NULL DEFAULT '',
                last_summary_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            ) STRICT;
            """)
            row = db.execute("SELECT id FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if not row:
                is_demo_file = "demo" in self.store.path.name.casefold()
                db.execute("""
                INSERT INTO jubelio_demo_state(id, is_demo, current_scenario, is_locked, lock_expires_at,
                    last_synced_at, last_status, last_error, last_summary_json, updated_at)
                VALUES('singleton', ?, 0, 0, '', '', 'idle', '', '{}', ?)
                """, (1 if is_demo_file else 0, now()))
                db.commit()

    def mark_as_demo_database(self, is_demo: bool = True):
        """Explicitly tags this database as demo or non-demo."""
        with closing(self.store.connect()) as db:
            db.execute("""
            UPDATE jubelio_demo_state
            SET is_demo = ?, updated_at = ?
            WHERE id = 'singleton'
            """, (1 if is_demo else 0, now()))
            db.commit()

    def is_demo_database(self) -> bool:
        """Verifies if the database is explicitly allowed to run demo mode."""
        with closing(self.store.connect()) as db:
            row = db.execute("SELECT is_demo FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if row and row["is_demo"] == 1:
                return True
        return "demo" in self.store.path.name.casefold()

    def get_status(self) -> Dict[str, Any]:
        """Returns the current demo mode status."""
        with closing(self.store.connect()) as db:
            row = db.execute("SELECT is_demo, current_scenario, is_locked, lock_expires_at, last_synced_at, last_status, last_error, last_summary_json, updated_at FROM jubelio_demo_state WHERE id='singleton'").fetchone()
            if not row:
                return {
                    "is_demo_database": False,
                    "is_active": False,
                    "current_scenario": 0,
                    "is_locked": False,
                    "last_synced_at": "",
                    "last_status": "idle",
                    "last_error": "",
                    "last_summary": {},
                }
            is_demo = row["is_demo"]
            scenario = row["current_scenario"]
            is_locked = row["is_locked"]
            lock_exp = row["lock_expires_at"]
            synced_at = row["last_synced_at"]
            status = row["last_status"]
            error = row["last_error"]
            summary_json = row["last_summary_json"]

            # Expire lock if past expiration
            now_iso = now()
            if is_locked and lock_exp and lock_exp < now_iso:
                is_locked = False
                db.execute("UPDATE jubelio_demo_state SET is_locked=0, lock_expires_at='' WHERE id='singleton'")
                db.commit()
            
            try:
                summary = json.loads(summary_json)
            except Exception:
                summary = {}

            return {
                "is_demo_database": bool(is_demo) or ("demo" in self.store.path.name.casefold()),
                "is_active": scenario > 0,
                "current_scenario": scenario,
                "is_locked": bool(is_locked),
                "last_synced_at": synced_at,
                "last_status": status,
                "last_error": error,
                "last_summary": summary,
            }

    def _acquire_lock(self, timeout_seconds: int = 30):
        """Acquires transactional lock at the database level."""
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        exp_iso = (now_dt + timedelta(seconds=timeout_seconds)).isoformat()
        with self.store.transaction(write=True) as db:
            res = db.execute("""
            UPDATE jubelio_demo_state
            SET is_locked = 1, lock_expires_at = ?, updated_at = ?
            WHERE id = 'singleton' AND (is_locked = 0 OR lock_expires_at < ?)
            """, (exp_iso, now_iso, now_iso))
            if res.rowcount == 0:
                raise DomainError(409, "Sinkronisasi demo sedang berjalan. Mohon tunggu proses sebelumnya selesai.")

    def _release_lock(self, status: str, error: str = "", summary: Optional[Dict[str, Any]] = None, scenario: Optional[int] = None):
        """Releases the transactional database lock and updates execution results."""
        now_iso = now()
        summary_str = json.dumps(summary or {}, ensure_ascii=False)
        with self.store.transaction(write=True) as db:
            if scenario is not None:
                db.execute("""
                UPDATE jubelio_demo_state
                SET is_locked = 0, lock_expires_at = '', current_scenario = ?,
                    last_synced_at = ?, last_status = ?, last_error = ?,
                    last_summary_json = ?, updated_at = ?
                WHERE id = 'singleton'
                """, (scenario, now_iso, status, error, summary_str, now_iso))
            else:
                db.execute("""
                UPDATE jubelio_demo_state
                SET is_locked = 0, lock_expires_at = '',
                    last_synced_at = ?, last_status = ?, last_error = ?,
                    last_summary_json = ?, updated_at = ?
                WHERE id = 'singleton'
                """, (now_iso, status, error, summary_str, now_iso))

    def activate(self, actor: Dict[str, Any], key: str) -> Dict[str, Any]:
        """Activates demo mode on demo database and seeds products & mappings."""
        if not self.is_demo_database():
            raise DomainError(400, "Database ini bukan database demo. Mode Jubelio Demo hanya dapat diaktifkan pada database yang ditandai untuk demo.")
        
        # Seed products & mappings if not present
        demo_products = JubelioDemoDataset.products()
        with closing(self.store.connect()) as db:
            existing_skus = {row[0] for row in db.execute("SELECT sku FROM products").fetchall()}
        
        for p in demo_products:
            if p["sku"] not in existing_skus:
                prod = self.store.create_product({
                    "sku": p["sku"],
                    "name": p["name"],
                    "color": p["color"],
                    "size": p["size"],
                }, actor, f"demo-prod-init-{p['sku']}")
            else:
                with closing(self.store.connect()) as db:
                    row = db.execute("SELECT id FROM products WHERE sku=?", (p["sku"],)).fetchone()
                    prod = {"id": row[0]}

            # Apply mapping if mapped
            if p["is_mapped"]:
                curr_map = self.store.product_external_mapping(prod["id"], "jubelio")
                if curr_map["status"] != "mapped":
                    self.store.save_product_external_mapping(
                        prod["id"],
                        "jubelio",
                        {
                            "expected_revision": curr_map["revision"],
                            "action": "mapped",
                            "external_id": p["external_id"],
                            "external_sku": p["external_sku"],
                            "reason": "Pemetaan otomatis awal Jubelio Demo",
                        },
                        actor,
                        f"demo-map-init-{prod['id']}"
                    )

        # Mark active scenario 1 in state
        with self.store.transaction(write=True) as db:
            db.execute("""
            UPDATE jubelio_demo_state
            SET is_demo = 1, current_scenario = 1, last_status = 'idle', updated_at = ?
            WHERE id = 'singleton'
            """, (now(),))

        return self.get_status()

    def sync(self, actor: Dict[str, Any], key: str, scenario: Optional[int] = None) -> Dict[str, Any]:
        """Synchronizes data for current or specified scenario via existing ingestion contracts."""
        if not self.is_demo_database():
            raise DomainError(400, "Database ini bukan database demo. Mode Jubelio Demo hanya dapat diaktifkan pada database yang ditandai untuk demo.")

        receipt_key = f"jubelio-demo-sync:{key}"
        with closing(self.store.connect()) as db:
            receipt = db.execute("SELECT actor_id, response FROM requests WHERE key=?", (receipt_key,)).fetchone()
            if receipt:
                if receipt["actor_id"] != actor["id"]:
                    raise DomainError(403, "Idempotency-Key ini milik akun lain.")
                return json.loads(receipt["response"])

        current = self.get_status()
        target_scenario = scenario if scenario is not None else max(1, current["current_scenario"])

        self._acquire_lock()
        try:
            if target_scenario >= 2:
                data = JubelioDemoDataset.generate_scenario_2()
                scenario_label = "Skenario 2 (Pembaruan transaksi & stok)"
            else:
                data = JubelioDemoDataset.generate_baseline()
                scenario_label = "Skenario 1 (Baseline)"

            sync_ts = now()
            # 1. Stock snapshot
            stock_res = self.store.import_jubelio_stock_snapshot({
                "started_at": sync_ts,
                "finished_at": sync_ts,
                "snapshot_at": sync_ts,
                "external_cursor": f"cursor-stock-scen-{target_scenario}",
                "reason": f"Sinkronisasi demo stok {scenario_label}",
                "items": data["items"],
            }, actor, f"{key}-stock-{target_scenario}")

            # 2. Order snapshot
            order_res = self.store.import_jubelio_order_snapshot({
                "started_at": sync_ts,
                "finished_at": sync_ts,
                "snapshot_at": sync_ts,
                "external_cursor": f"cursor-orders-scen-{target_scenario}",
                "reason": f"Sinkronisasi demo order {scenario_label}",
                "orders": data["orders"],
            }, actor, f"{key}-orders-{target_scenario}")

            # 3. Return snapshot
            return_res = self.store.import_jubelio_return_snapshot({
                "started_at": sync_ts,
                "finished_at": sync_ts,
                "snapshot_at": sync_ts,
                "external_cursor": f"cursor-returns-scen-{target_scenario}",
                "reason": f"Sinkronisasi demo retur {scenario_label}",
                "returns": data["returns"],
            }, actor, f"{key}-returns-{target_scenario}")

            # 4. Listing snapshot
            listing_res = self.store.import_jubelio_listing_snapshot({
                "started_at": sync_ts,
                "finished_at": sync_ts,
                "snapshot_at": sync_ts,
                "external_cursor": f"cursor-listings-scen-{target_scenario}",
                "reason": f"Sinkronisasi demo listing {scenario_label}",
                "listings": data["listings"],
            }, actor, f"{key}-listings-{target_scenario}")

            total_accepted = (stock_res.get("accepted_count", 0) +
                              order_res.get("accepted_count", 0) +
                              return_res.get("accepted_count", 0) +
                              listing_res.get("accepted_count", 0))
            total_quarantined = (stock_res.get("rejected_count", 0) +
                                order_res.get("rejected_count", 0) +
                                return_res.get("rejected_count", 0) +
                                listing_res.get("rejected_count", 0))

            # Status attention if any scope has quarantine; only succeeded if 0 quarantined
            status = "attention" if total_quarantined > 0 else "succeeded"
            error_note = f"{total_quarantined} record masuk karantina karena SKU belum dipetakan." if total_quarantined > 0 else ""
            summary = {
                "scenario": target_scenario,
                "scenario_label": scenario_label,
                "total_accepted": total_accepted,
                "total_quarantined": total_quarantined,
                "scopes": {
                    "finished_goods": {"status": "succeeded" if stock_res.get("rejected_count", 0) == 0 else "attention", "accepted": stock_res.get("accepted_count", 0), "quarantined": stock_res.get("rejected_count", 0)},
                    "orders": {"status": "succeeded" if order_res.get("rejected_count", 0) == 0 else "attention", "accepted": order_res.get("accepted_count", 0), "quarantined": order_res.get("rejected_count", 0)},
                    "returns": {"status": "succeeded" if return_res.get("rejected_count", 0) == 0 else "attention", "accepted": return_res.get("accepted_count", 0), "quarantined": return_res.get("rejected_count", 0)},
                    "listings": {"status": "succeeded" if listing_res.get("rejected_count", 0) == 0 else "attention", "accepted": listing_res.get("accepted_count", 0), "quarantined": listing_res.get("rejected_count", 0)},
                }
            }
            self._release_lock(status=status, error=error_note, summary=summary, scenario=target_scenario)
            final_status = self.get_status()
            with self.store.transaction(write=True) as db:
                db.execute("""
                INSERT OR REPLACE INTO requests(key, actor_id, fingerprint, response, created_at)
                VALUES(?, ?, 'demo-sync', ?, ?)
                """, (receipt_key, actor["id"], json.dumps(final_status, ensure_ascii=False), now()))
            return final_status
        except Exception as exc:
            self._release_lock(status="failed", error=str(exc))
            raise

    def next_scenario(self, actor: Dict[str, Any], key: str) -> Dict[str, Any]:
        """Advances scenario to next level and syncs."""
        current = self.get_status()
        next_scen = current["current_scenario"] + 1
        return self.sync(actor, key, scenario=next_scen)

    def reset_demo(self, actor: Dict[str, Any], key: str) -> Dict[str, Any]:
        """Resets scenario back to baseline (scenario 1) on demo database."""
        if not self.is_demo_database():
            raise DomainError(400, "Reset skenario demo hanya diizinkan pada database demo.")
        with self.store.transaction(write=True) as db:
            db.execute("""
            UPDATE jubelio_demo_state
            SET current_scenario = 1, last_status = 'idle', last_error = '', updated_at = ?
            WHERE id = 'singleton'
            """, (now(),))
        return self.sync(actor, key, scenario=1)
