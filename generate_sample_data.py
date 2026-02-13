"""
Generate sample CSV data for testing the dashboard.
Run:  python generate_sample_data.py
Produces: sample_report.csv
"""

import random
import csv
from datetime import date, timedelta

PRODUCTS = [f"B0{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=8))}" for _ in range(50)]
BRANDS = ["BrandA", "BrandB", "BrandC", "BrandD"]
CATEGORIES = ["Electronics", "Home", "Kitchen", "Outdoors", "Apparel"]

START = date(2025, 1, 1)
WEEKS = 12

rows = []
for week_i in range(WEEKS):
    week_start = START + timedelta(weeks=week_i)
    for asin in PRODUCTS:
        impressions = random.randint(500, 50000)
        clicks = random.randint(10, int(impressions * 0.15))
        page_views = random.randint(int(clicks * 0.7), int(clicks * 1.3) + 1)
        purchases = random.randint(0, max(1, int(clicks * 0.12)))
        cvr = purchases / clicks * 100 if clicks > 0 else 0
        ctr = clicks / impressions * 100 if impressions > 0 else 0
        rows.append({
            "Date": week_start.isoformat(),
            "ASIN": asin,
            "Brand": random.choice(BRANDS),
            "Category": random.choice(CATEGORIES),
            "Impressions": impressions,
            "Clicks": clicks,
            "Glance Views": page_views,
            "Purchases": purchases,
            "CVR": f"{cvr:.2f}%",
            "CTR": f"{ctr:.2f}%",
        })

with open("sample_report.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} rows to sample_report.csv ({len(PRODUCTS)} products x {WEEKS} weeks)")
