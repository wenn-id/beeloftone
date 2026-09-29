"""Deterministic internal dataset provider for the Jubelio Demo commerce connector."""

from datetime import datetime, timedelta
from decimal import Decimal

DEMO_ANCHOR_UTC = "2026-09-28T00:00:00+00:00"
_RESERVED_EXTERNAL_IDS = {"JUB-EXT-019", "JUB-EXT-025"}


class JubelioDemoDataset:
    @staticmethod
    def products():
        models = [
            ("LUNA", "Piyama Katun Anak Luna", ["Navy", "Sage", "Terracotta"], ["S", "M"]),
            ("MILO", "Kaos Polos Katun Milo", ["Mustard", "Dusty Pink"], ["S", "M", "L"]),
            ("KIKO", "Kemeja Flanel Anak Kiko", ["Navy", "Terracotta", "Mustard"], ["S", "M"]),
            ("CACA", "Dress Ruffle Anak Caca", ["Sage", "Dusty Pink"], ["S", "M", "L"]),
            ("BIMO", "Celana Chino Anak Bimo", ["Navy", "Terracotta"], ["S", "M", "L"]),
        ]
        products = []
        index = 1
        for code, name, colors, sizes in models:
            for color in colors:
                for size in sizes:
                    unmapped = (code, color, size) in {("BIMO", "Navy", "L"), ("CACA", "Sage", "S")}
                    if unmapped:
                        external_id = "JUB-EXT-025" if code == "BIMO" else "JUB-EXT-019"
                    else:
                        while f"JUB-EXT-{index:03d}" in _RESERVED_EXTERNAL_IDS:
                            index += 1
                        external_id = f"JUB-EXT-{index:03d}"
                        index += 1
                    sku = ("DEMO-BIMO-PANTS-L" if code == "BIMO" and color == "Navy" and size == "L"
                           else "DEMO-CACA-DRESS-S" if code == "CACA" and color == "Sage" and size == "S"
                           else f"DEMO-{code}-{color.upper().replace(' ', '')}-{size}")
                    products.append({
                        "sku": sku,
                        "name": f"{name} {color} {size}",
                        "color": color,
                        "size": size,
                        "external_id": external_id,
                        "external_sku": f"JUB-SKU-{code}-{color.upper()}-{size}",
                        "is_mapped": not unmapped,
                        "base_price": Decimal("65000.00") if code in ("MILO", "LUNA") else Decimal("85000.00"),
                    })
        return products

    @staticmethod
    def _anchor(anchor_at):
        anchor = datetime.fromisoformat(anchor_at)
        if anchor.tzinfo is None or anchor.utcoffset() != timedelta(0):
            raise ValueError("Demo anchor must use an explicit UTC offset.")
        return anchor

    @classmethod
    def generate_baseline(cls, anchor_at=DEMO_ANCHOR_UTC):
        anchor = cls._anchor(anchor_at)
        products = cls.products()
        marketplaces = ["Shopee", "Tokopedia", "TikTok Shop"]
        items = [{
            "external_id": p["external_id"], "external_sku": p["external_sku"],
            "sellable_quantity": 60 + (i * 7) % 140, "reserved_quantity": (i * 3) % 15,
        } for i, p in enumerate(products)]

        orders = []
        for index in range(1, 121):
            marketplace = marketplaces[index % 3]
            day_offset = 29 - index * 29 // 120
            ordered_at = anchor - timedelta(days=day_offset) + timedelta(hours=index % 24, minutes=index * 7 % 60)
            status = "completed" if index <= 80 else "processing" if index <= 100 else "pending" if index <= 115 else "cancelled"
            lines = []
            for line_index in range(1 if index % 3 else 2):
                product = products[(index + line_index * 7) % len(products)]
                quantity = 1 if (index + line_index) % 4 else 2
                lines.append({
                    "external_id": product["external_id"], "external_sku": product["external_sku"],
                    "quantity": quantity, "gross_revenue": format(product["base_price"] * quantity, ".2f"),
                })
            orders.append({
                "external_order_id": f"JUB-ORD-2026-{index:04d}",
                "external_order_reference": f"ORD/{marketplace[:3].upper()}/202609/{index:04d}",
                "marketplace": marketplace, "status": status, "ordered_at": ordered_at.isoformat(), "lines": lines,
            })

        listings = [{
            "external_listing_id": f"JUB-LST-{index + 1:04d}",
            "listing_reference": f"LST-{marketplaces[index % 3][:3].upper()}-{product['external_sku']}",
            "external_id": product["external_id"], "external_sku": product["external_sku"],
            "marketplace": marketplaces[index % 3], "listing_title": f"Baju Anak {product['name']} - Koleksi Beeloft",
            "status": "active" if index < 26 else "inactive",
            "listed_price": format(product["base_price"] + Decimal("5000.00"), ".2f"),
            "updated_at": (anchor - timedelta(days=15)).isoformat(),
        } for index, product in enumerate(products)]

        completed = [order for order in orders if order["status"] == "completed"]
        returns = []
        for index, status in enumerate(("received", "refunded", "requested", "refunded")):
            order = completed[index * 5]
            line = order["lines"][0]
            returns.append({
                "external_return_id": f"JUB-RET-2026-{index + 1:04d}",
                "external_return_reference": f"RET/{order['marketplace'][:3].upper()}/{index + 1:04d}",
                "external_order_id": order["external_order_id"],
                "external_order_reference": order["external_order_reference"],
                "marketplace": order["marketplace"], "status": status,
                "updated_at": (anchor - timedelta(days=2)).isoformat(),
                "refund_amount": line["gross_revenue"] if status == "refunded" else "0.00",
                "lines": [{"external_id": line["external_id"], "external_sku": line["external_sku"], "quantity": 1}],
            })
        return {"items": items, "orders": orders, "listings": listings, "returns": returns}

    @classmethod
    def generate_scenario_2(cls, anchor_at=DEMO_ANCHOR_UTC):
        anchor = cls._anchor(anchor_at)
        baseline = cls.generate_baseline(anchor_at)
        products = cls.products()
        marketplaces = ["Shopee", "Tokopedia", "TikTok Shop"]
        orders = []
        for order in baseline["orders"]:
            progressed = dict(order)
            number = int(progressed["external_order_id"].split("-")[-1])
            if progressed["status"] == "pending":
                progressed["status"] = "processing" if number % 2 == 0 else "completed"
            elif progressed["status"] == "processing":
                progressed["status"] = "completed"
            orders.append(progressed)

        sold = {}
        for index in range(121, 146):
            marketplace = marketplaces[index % 3]
            product = products[index % len(products)]
            quantity = 1 if index % 3 else 2
            orders.append({
                "external_order_id": f"JUB-ORD-2026-{index:04d}",
                "external_order_reference": f"ORD/{marketplace[:3].upper()}/202609/{index:04d}",
                "marketplace": marketplace,
                "status": "pending" if index >= 138 else "processing",
                "ordered_at": (anchor + timedelta(days=0 if index < 135 else 1,
                                                   hours=index % 12, minutes=index * 11 % 60)).isoformat(),
                "lines": [{
                    "external_id": product["external_id"], "external_sku": product["external_sku"],
                    "quantity": quantity, "gross_revenue": format(product["base_price"] * quantity, ".2f"),
                }],
            })
            sold[product["external_id"]] = sold.get(product["external_id"], 0) + quantity

        items = []
        for item in baseline["items"]:
            updated = dict(item)
            updated["sellable_quantity"] = max(0, updated["sellable_quantity"] - sold.get(updated["external_id"], 0))
            updated["reserved_quantity"] = min(updated["reserved_quantity"], updated["sellable_quantity"])
            items.append(updated)

        returns = list(baseline["returns"])
        candidates = [order for order in orders if order["status"] == "completed"
                      and int(order["external_order_id"].split("-")[-1]) > 50]
        for status in ("received", "refunded"):
            order = candidates[(len(returns) - 4) * 7]
            line = order["lines"][0]
            sequence = len(returns) + 1
            returns.append({
                "external_return_id": f"JUB-RET-2026-{sequence:04d}",
                "external_return_reference": f"RET/{order['marketplace'][:3].upper()}/{sequence:04d}",
                "external_order_id": order["external_order_id"],
                "external_order_reference": order["external_order_reference"],
                "marketplace": order["marketplace"], "status": status,
                "updated_at": (anchor + timedelta(days=1)).isoformat(),
                "refund_amount": line["gross_revenue"] if status == "refunded" else "0.00",
                "lines": [{"external_id": line["external_id"], "external_sku": line["external_sku"], "quantity": 1}],
            })
        return {"items": items, "orders": orders, "listings": baseline["listings"], "returns": returns}
