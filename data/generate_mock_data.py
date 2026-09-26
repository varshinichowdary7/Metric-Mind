"""
Generate mock corporate sales data for the MetricMind warehouse.

Produces four raw source tables as CSV seeds:
    raw_geography.csv   geo_id, country, region, continent
    raw_products.csv    product_id, product, category
    raw_orders.csv      order_id, order_date, geo_id, product_id, quantity, revenue
    raw_costs.csv       cost_id, order_id, cost_type, cost_amount   (2 rows/order)

The data is fully deterministic (fixed seed) so that governance tests can assert
that a metric such as "Q3 revenue" is byte-identical on every run.

A realistic anomaly is injected: in the most recent quarter (Q3 2025) European
shipping costs jump ~22%, which drags European margin down. This is the exact
pattern the MetricMind agent is meant to discover when asked
"Why did European margins drop last quarter?".

Usage:
    python data/generate_mock_data.py
"""

from __future__ import annotations

import csv
import os
import random
from datetime import date, timedelta

SEED = 42
NUM_ORDERS = 6000
DATE_START = date(2024, 1, 1)
DATE_END = date(2025, 9, 30)

# The quarter whose European shipping cost is inflated (the "last quarter" anomaly).
ANOMALY_YEAR = 2025
ANOMALY_QUARTER = 3
ANOMALY_SHIPPING_MULTIPLIER = 1.22

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS_DIR = os.path.join(HERE, "seeds")

# ── Reference dimensions ─────────────────────────────────────────────────────
# (geo_id, country, region, continent)
GEOGRAPHIES = [
    (1, "Sweden", "Nordics", "Europe"),
    (2, "Norway", "Nordics", "Europe"),
    (3, "Denmark", "Nordics", "Europe"),
    (4, "Germany", "DACH", "Europe"),
    (5, "Austria", "DACH", "Europe"),
    (6, "Switzerland", "DACH", "Europe"),
    (7, "France", "Western Europe", "Europe"),
    (8, "Netherlands", "Western Europe", "Europe"),
    (9, "United States", "US", "North America"),
    (10, "Canada", "Canada", "North America"),
    (11, "Japan", "East Asia", "Asia"),
    (12, "India", "South Asia", "Asia"),
    (13, "Singapore", "SE Asia", "Asia"),
]

# (product_id, product, category, unit_price, material_ratio)
PRODUCTS = [
    (1, "Laptop Pro 14", "Electronics", 1899.00, 0.62),
    (2, "4K Monitor 27", "Electronics", 549.00, 0.58),
    (3, "Wireless Mouse", "Electronics", 39.00, 0.45),
    (4, "USB-C Hub", "Accessories", 79.00, 0.40),
    (5, "Laptop Stand", "Accessories", 59.00, 0.38),
    (6, "Mechanical Keyboard", "Accessories", 129.00, 0.44),
    (7, "Analytics Suite License", "Software", 1200.00, 0.15),
    (8, "Cloud Storage Plan", "Software", 300.00, 0.12),
]

# Continent sampling weights (Europe over-represented so the anomaly is visible).
CONTINENT_WEIGHTS = {"Europe": 0.45, "North America": 0.35, "Asia": 0.20}


def quarter_of(d: date) -> int:
    return (d.month - 1) // 3 + 1


def weighted_geo_ids() -> tuple[list[int], list[float]]:
    ids, weights = [], []
    per_continent_count: dict[str, int] = {}
    for _, _, _, continent in GEOGRAPHIES:
        per_continent_count[continent] = per_continent_count.get(continent, 0) + 1
    for geo_id, _, _, continent in GEOGRAPHIES:
        ids.append(geo_id)
        weights.append(CONTINENT_WEIGHTS[continent] / per_continent_count[continent])
    return ids, weights


def main() -> None:
    random.seed(SEED)
    os.makedirs(SEEDS_DIR, exist_ok=True)

    geo_by_id = {g[0]: g for g in GEOGRAPHIES}
    product_by_id = {p[0]: p for p in PRODUCTS}
    geo_ids, geo_weights = weighted_geo_ids()
    product_ids = [p[0] for p in PRODUCTS]
    total_days = (DATE_END - DATE_START).days

    # ── raw_geography.csv ────────────────────────────────────────────────────
    with open(os.path.join(SEEDS_DIR, "raw_geography.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["geo_id", "country", "region", "continent"])
        for row in GEOGRAPHIES:
            w.writerow(row)

    # ── raw_products.csv ─────────────────────────────────────────────────────
    with open(os.path.join(SEEDS_DIR, "raw_products.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "product", "category"])
        for product_id, product, category, _price, _ratio in PRODUCTS:
            w.writerow([product_id, product, category])

    # ── raw_orders.csv + raw_costs.csv ───────────────────────────────────────
    orders_path = os.path.join(SEEDS_DIR, "raw_orders.csv")
    costs_path = os.path.join(SEEDS_DIR, "raw_costs.csv")
    cost_id = 0
    anomaly_rows = 0

    with open(orders_path, "w", newline="") as of, open(costs_path, "w", newline="") as cf:
        ow = csv.writer(of)
        cw = csv.writer(cf)
        ow.writerow(["order_id", "order_date", "geo_id", "product_id", "quantity", "revenue"])
        cw.writerow(["cost_id", "order_id", "cost_type", "cost_amount"])

        for order_id in range(1, NUM_ORDERS + 1):
            # Slight recency bias: bias the date draw toward the end of the window.
            u = random.random() ** 0.85
            order_date = DATE_START + timedelta(days=int(u * total_days))

            geo_id = random.choices(geo_ids, weights=geo_weights, k=1)[0]
            _, _, _, continent = geo_by_id[geo_id]
            product_id = random.choice(product_ids)
            _, _, category, unit_price, material_ratio = product_by_id[product_id]

            quantity = random.randint(1, 20)
            price = unit_price * random.uniform(0.92, 1.08)  # small list-price variation
            revenue = round(quantity * price, 2)

            # Material cost: category-driven ratio with noise.
            material_cost = round(revenue * material_ratio * random.uniform(0.95, 1.05), 2)

            # Shipping cost: base ~8-14% of revenue, inflated for Europe in the anomaly quarter.
            shipping_ratio = random.uniform(0.08, 0.14)
            is_anomaly = (
                continent == "Europe"
                and order_date.year == ANOMALY_YEAR
                and quarter_of(order_date) == ANOMALY_QUARTER
            )
            if is_anomaly:
                shipping_ratio *= ANOMALY_SHIPPING_MULTIPLIER
                anomaly_rows += 1
            shipping_cost = round(revenue * shipping_ratio, 2)

            ow.writerow([order_id, order_date.isoformat(), geo_id, product_id, quantity, revenue])

            cost_id += 1
            cw.writerow([cost_id, order_id, "material", material_cost])
            cost_id += 1
            cw.writerow([cost_id, order_id, "shipping", shipping_cost])

    print(f"Wrote {len(GEOGRAPHIES)} geographies, {len(PRODUCTS)} products.")
    print(f"Wrote {NUM_ORDERS} orders and {cost_id} cost rows to {SEEDS_DIR}")
    print(f"Injected inflated shipping on {anomaly_rows} European orders in Q{ANOMALY_QUARTER} {ANOMALY_YEAR}.")


if __name__ == "__main__":
    main()
