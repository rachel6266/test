# Interactive Performance Dashboard

A Streamlit dashboard for analyzing product-level performance metrics from CSV/XLSX reports.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then upload your CSV/XLSX file or paste a table in the sidebar.

## Generate Sample Data (optional)

```bash
python generate_sample_data.py
# produces sample_report.csv (50 products x 12 weeks)
```

## Features

- **KPI tiles**: Total CVR, Page Views, Clicks, Impressions, Purchases, CTR
- **Sortable product table** with per-product metrics and deltas (when time periods exist)
- **Time trend chart**: select metric and products to see performance over time
- **Top movers bar chart**: biggest increases/decreases by delta or delta %
- **Efficiency scatter plot**: Impressions vs Clicks, bubble size = Page Views, color = CVR
- **Interactive filters**: product multi-select, time range, Top N, segment filters (brand, category, etc.)
- **Auto column mapping**: detects common column names (ASIN, glance views, orders, etc.) with manual override

## Assumptions and Data Mapping

### Column detection

The app auto-maps columns by matching names against known patterns:

| Canonical metric | Matches (case-insensitive substring) |
|---|---|
| Product | asin, sku, product, item, title, name, listing |
| Page Views | page view, pageview, glance view, session, detail page |
| Clicks | click |
| Impressions | impression |
| Purchases | purchase, order, unit, conversion |
| CVR (provided) | cvr, conversion rate |
| CTR (provided) | ctr, click-through |
| Time | date, week, month, period, time, day |

You can override any mapping in the sidebar after uploading data.

### Formulas

- **CVR** = Purchases / Clicks (computed per row; if the report includes a CVR column, it is compared against the recomputed value for validation)
- **CTR** = Clicks / Impressions
- **Deltas** = last time period value − first time period value (both absolute and percent)

### Data cleaning

- Non-numeric characters (`%`, `$`, `,`) are stripped before numeric conversion
- Missing values propagate as NaN; division by zero produces NaN
- Date columns are auto-parsed; if >50% parse successfully, the column is treated as datetime

### Performance

- Uses `@st.cache_data` for file loading
- Tested for datasets with 5,000+ products across multiple time periods
