"""
Interactive Performance Dashboard
=================================
A Streamlit dashboard for analyzing product-level performance metrics
(CVR, page views, clicks, impressions) from CSV/XLSX report data.

Usage:
    streamlit run app.py
"""

import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Performance Dashboard",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Column-mapping helpers
# ---------------------------------------------------------------------------

# Canonical names we work with internally
CANONICAL = {
    "product": "Product",
    "page_views": "Page Views",
    "clicks": "Clicks",
    "impressions": "Impressions",
    "purchases": "Purchases",
    "cvr": "CVR",
    "ctr": "CTR",
    "time": "Time Period",
}

# Patterns (lowercased substrings) we use for auto-detection
_PATTERNS = {
    "product": [
        "asin", "sku", "product", "item", "title", "name", "listing",
    ],
    "page_views": [
        "page view", "pageview", "glance view", "session", "detail page",
        "page_view", "glance_view",
    ],
    "clicks": ["click"],
    "impressions": ["impression"],
    "purchases": ["purchase", "order", "unit", "conversion"],
    "cvr": ["cvr", "conversion rate", "conv rate", "conv. rate"],
    "ctr": ["ctr", "click-through", "click through", "clickthrough"],
    "time": [
        "date", "week", "month", "period", "time", "day", "year", "quarter",
    ],
}


def _score_column(col_lower: str, patterns: list[str]) -> int:
    """Return a relevance score for a column name against patterns."""
    score = 0
    for p in patterns:
        if col_lower == p:
            score += 100
        elif p in col_lower:
            score += 50
    return score


def auto_map_columns(columns: list[str]) -> dict[str, str | None]:
    """Return {canonical_key: actual_column_name} best-effort mapping."""
    mapping: dict[str, str | None] = {}
    used: set[str] = set()

    for key, patterns in _PATTERNS.items():
        best_col = None
        best_score = 0
        for col in columns:
            if col in used:
                continue
            score = _score_column(col.lower().strip(), patterns)
            if score > best_score:
                best_score = score
                best_col = col
        if best_col and best_score > 0:
            mapping[key] = best_col
            used.add(best_col)
        else:
            mapping[key] = None

    return mapping


# ---------------------------------------------------------------------------
# Data loading & caching
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_file(uploaded_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read CSV or Excel bytes into a DataFrame."""
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(uploaded_bytes))
    return pd.read_csv(io.BytesIO(uploaded_bytes))


def coerce_numeric(series: pd.Series) -> pd.Series:
    """Attempt to convert a series to numeric, cleaning common artefacts."""
    if series.dtype == object:
        cleaned = (
            series.astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.strip()
        )
        return pd.to_numeric(cleaned, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


# ---------------------------------------------------------------------------
# KPI tile helper
# ---------------------------------------------------------------------------

def kpi_tile(label: str, value, fmt: str = "{:,.0f}", delta=None):
    """Render a metric tile with optional delta."""
    if pd.isna(value):
        st.metric(label, "N/A")
        return
    formatted = fmt.format(value)
    if delta is not None and not pd.isna(delta):
        st.metric(label, formatted, delta=f"{delta:+.2f}%")
    else:
        st.metric(label, formatted)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    st.title("Interactive Performance Dashboard")

    # --- Sidebar: file upload -------------------------------------------------
    st.sidebar.header("Data Input")
    uploaded = st.sidebar.file_uploader(
        "Upload CSV or XLSX report",
        type=["csv", "xlsx", "xls"],
    )

    pasted = st.sidebar.text_area(
        "…or paste a tab/comma-separated table",
        height=150,
        help="Copy-paste from a spreadsheet or report.",
    )

    # Load data ----------------------------------------------------------------
    df: pd.DataFrame | None = None

    if uploaded is not None:
        raw = uploaded.getvalue()
        df = load_file(raw, uploaded.name)
    elif pasted.strip():
        try:
            df = pd.read_csv(io.StringIO(pasted), sep=None, engine="python")
        except Exception:
            st.error("Could not parse pasted data. Ensure it is tab or comma delimited.")
            return

    if df is None:
        st.info(
            "Upload a CSV/XLSX file or paste a table in the sidebar to get started."
        )
        _show_sample_schema()
        return

    # --- Schema printout & column mapping ------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("Detected Schema")
    schema_df = pd.DataFrame({
        "Column": df.columns,
        "Dtype": [str(d) for d in df.dtypes],
        "Non-null": [int(df[c].notna().sum()) for c in df.columns],
    })
    st.sidebar.dataframe(schema_df, hide_index=True, use_container_width=True)

    auto = auto_map_columns(list(df.columns))

    st.sidebar.markdown("---")
    st.sidebar.subheader("Column Mapping")
    st.sidebar.caption("Confirm or override the auto-detected mapping.")

    none_option = ["(none)"]
    col_options = none_option + list(df.columns)

    def _pick(key: str, label: str) -> str | None:
        default_idx = 0
        if auto.get(key) and auto[key] in df.columns:
            default_idx = col_options.index(auto[key])
        choice = st.sidebar.selectbox(label, col_options, index=default_idx, key=f"map_{key}")
        return None if choice == "(none)" else choice

    col_product = _pick("product", "Product identifier")
    col_pv = _pick("page_views", "Page Views")
    col_clicks = _pick("clicks", "Clicks")
    col_impressions = _pick("impressions", "Impressions")
    col_purchases = _pick("purchases", "Purchases / Orders")
    col_cvr = _pick("cvr", "CVR (provided)")
    col_ctr = _pick("ctr", "CTR (provided)")
    col_time = _pick("time", "Time / Date column")

    # --- Build working dataframe --------------------------------------------
    wdf = pd.DataFrame()

    if col_product:
        wdf["Product"] = df[col_product].astype(str)
    else:
        wdf["Product"] = df.index.astype(str)

    for canon, src in [
        ("Page Views", col_pv),
        ("Clicks", col_clicks),
        ("Impressions", col_impressions),
        ("Purchases", col_purchases),
    ]:
        if src:
            wdf[canon] = coerce_numeric(df[src])
        else:
            wdf[canon] = np.nan

    if col_cvr:
        wdf["CVR_provided"] = coerce_numeric(df[col_cvr])
    if col_ctr:
        wdf["CTR_provided"] = coerce_numeric(df[col_ctr])

    # Compute CVR & CTR
    wdf["CVR"] = np.where(
        wdf["Clicks"].fillna(0) > 0,
        wdf["Purchases"].fillna(0) / wdf["Clicks"],
        np.nan,
    )
    wdf["CTR"] = np.where(
        wdf["Impressions"].fillna(0) > 0,
        wdf["Clicks"].fillna(0) / wdf["Impressions"],
        np.nan,
    )

    # Time column
    has_time = False
    if col_time:
        wdf["Time Period"] = df[col_time]
        # Attempt date parse
        parsed = pd.to_datetime(wdf["Time Period"], errors="coerce", infer_datetime_format=True)
        if parsed.notna().sum() > len(wdf) * 0.5:
            wdf["Time Period"] = parsed
        has_time = True

    time_periods = sorted(wdf["Time Period"].dropna().unique()) if has_time else []
    has_multiple_periods = len(time_periods) > 1

    # --- CVR validation -------------------------------------------------------
    if col_cvr:
        with st.expander("CVR Validation: provided vs recomputed"):
            compare = wdf[["Product", "CVR_provided", "CVR"]].dropna(subset=["CVR_provided"])
            compare["Diff (pp)"] = (compare["CVR"] - compare["CVR_provided"]) * 100
            st.dataframe(compare.head(50), hide_index=True, use_container_width=True)
            max_diff = compare["Diff (pp)"].abs().max()
            if pd.notna(max_diff) and max_diff > 1:
                st.warning(f"Max discrepancy: {max_diff:.2f} pp — check raw data.")
            else:
                st.success("Provided CVR matches recomputed CVR (within 1 pp).")

    # --- Detect time-based deltas -------------------------------------------
    deltas_df: pd.DataFrame | None = None
    if has_multiple_periods:
        deltas_df = _compute_deltas(wdf, time_periods)

    # =========================================================================
    # FILTERS (sidebar)
    # =========================================================================
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")

    products = sorted(wdf["Product"].unique())

    selected_products = st.sidebar.multiselect(
        "Products",
        products,
        default=[],
        help="Leave empty to show all.",
    )

    metric_options = ["Page Views", "Clicks", "Impressions", "CVR"]
    if wdf["Purchases"].notna().any():
        metric_options.append("Purchases")
    metric_options.append("CTR")
    selected_metric = st.sidebar.selectbox("Primary metric", metric_options, index=0)

    top_n = st.sidebar.selectbox("Top N products", [10, 25, 50], index=0)
    sort_by_option = "delta_pct"
    if has_multiple_periods:
        sort_by_option = st.sidebar.radio("Sort movers by", ["Delta %", "Delta abs"], horizontal=True)
        sort_by_option = "delta_pct" if sort_by_option == "Delta %" else "delta_abs"
        movers_direction = st.sidebar.radio("Show", ["Biggest increases", "Biggest decreases"], horizontal=True)
    else:
        movers_direction = "Biggest increases"

    if has_time:
        selected_time = st.sidebar.multiselect(
            "Time periods",
            time_periods,
            default=list(time_periods),
        )
    else:
        selected_time = []

    # Extra segment filters
    _extra_filters = _detect_segment_columns(df, [col_product, col_pv, col_clicks,
                                                   col_impressions, col_purchases,
                                                   col_cvr, col_ctr, col_time])
    segment_selections: dict[str, list] = {}
    if _extra_filters:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Segment Filters")
        for seg_col in _extra_filters:
            unique_vals = sorted(df[seg_col].dropna().unique())
            if 1 < len(unique_vals) <= 200:
                sel = st.sidebar.multiselect(seg_col, unique_vals, default=[])
                if sel:
                    segment_selections[seg_col] = sel

    # --- Apply filters -------------------------------------------------------
    view = wdf.copy()
    if selected_products:
        view = view[view["Product"].isin(selected_products)]
    if has_time and selected_time:
        view = view[view["Time Period"].isin(selected_time)]

    # Apply segment filters on original df indices
    if segment_selections:
        mask = pd.Series(True, index=df.index)
        for seg_col, vals in segment_selections.items():
            mask &= df[seg_col].isin(vals)
        view = view.loc[view.index.intersection(mask[mask].index)]

    if view.empty:
        st.warning("No data matches current filters.")
        return

    # =========================================================================
    # A) KPI TILES
    # =========================================================================
    st.header("Overall KPIs")

    # Aggregate: if time exists, aggregate across all selected periods
    agg = _aggregate(view)

    cols = st.columns(6)
    with cols[0]:
        cvr_val = agg["Purchases"] / agg["Clicks"] if agg["Clicks"] > 0 else np.nan
        kpi_tile("Total CVR", cvr_val * 100 if pd.notna(cvr_val) else np.nan, fmt="{:.2f}%")
    with cols[1]:
        kpi_tile("Total Page Views", agg["Page Views"])
    with cols[2]:
        kpi_tile("Total Clicks", agg["Clicks"])
    with cols[3]:
        kpi_tile("Total Impressions", agg["Impressions"])
    with cols[4]:
        kpi_tile("Total Purchases", agg["Purchases"])
    with cols[5]:
        ctr_val = agg["Clicks"] / agg["Impressions"] if agg["Impressions"] > 0 else np.nan
        kpi_tile("Total CTR", ctr_val * 100 if pd.notna(ctr_val) else np.nan, fmt="{:.2f}%")

    # =========================================================================
    # B) PRODUCT TABLE
    # =========================================================================
    st.header("Product Breakdown")

    product_table = _build_product_table(view, deltas_df, has_multiple_periods)
    st.dataframe(
        product_table,
        hide_index=True,
        use_container_width=True,
        height=min(len(product_table) * 35 + 40, 600),
    )

    # =========================================================================
    # C) CHARTS
    # =========================================================================
    st.header("Charts")

    tab_trend, tab_movers, tab_scatter = st.tabs(
        ["Time Trend", "Top Movers", "Efficiency Scatter"]
    )

    # C1: Time trend -----------------------------------------------------------
    with tab_trend:
        if has_time:
            _chart_time_trend(view, selected_metric, products)
        else:
            st.info("No time dimension detected — time trend chart unavailable.")

    # C2: Top movers -----------------------------------------------------------
    with tab_movers:
        if has_multiple_periods and deltas_df is not None:
            _chart_top_movers(
                deltas_df, selected_metric, top_n, sort_by_option, movers_direction,
                selected_products,
            )
        else:
            # Fallback: show top/bottom by absolute value
            _chart_top_movers_static(view, selected_metric, top_n, movers_direction)

    # C3: Scatter plot ---------------------------------------------------------
    with tab_scatter:
        _chart_scatter(view)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _show_sample_schema():
    """Show expected schema when no data loaded."""
    st.markdown("### Expected data format")
    sample = pd.DataFrame({
        "Product / ASIN": ["B0EXAMPLE1", "B0EXAMPLE2"],
        "Date": ["2025-01-01", "2025-01-01"],
        "Impressions": [10000, 8500],
        "Clicks": [500, 300],
        "Page Views": [450, 280],
        "Purchases": [25, 18],
        "CVR": ["5.0%", "6.0%"],
    })
    st.dataframe(sample, hide_index=True)


def _aggregate(df: pd.DataFrame) -> dict:
    """Sum core metrics across the dataframe."""
    return {
        "Page Views": df["Page Views"].sum(min_count=1),
        "Clicks": df["Clicks"].sum(min_count=1),
        "Impressions": df["Impressions"].sum(min_count=1),
        "Purchases": df["Purchases"].sum(min_count=1),
    }


def _compute_deltas(wdf: pd.DataFrame, time_periods) -> pd.DataFrame:
    """Compute per-product deltas between the first and last time period."""
    first_period = time_periods[0]
    last_period = time_periods[-1]

    metrics = ["Page Views", "Clicks", "Impressions", "Purchases", "CVR", "CTR"]

    first = wdf[wdf["Time Period"] == first_period].groupby("Product")[metrics].sum(min_count=1).reset_index()
    last = wdf[wdf["Time Period"] == last_period].groupby("Product")[metrics].sum(min_count=1).reset_index()

    # Recompute rates for each period group
    for g in [first, last]:
        g["CVR"] = np.where(g["Clicks"].fillna(0) > 0, g["Purchases"].fillna(0) / g["Clicks"], np.nan)
        g["CTR"] = np.where(g["Impressions"].fillna(0) > 0, g["Clicks"].fillna(0) / g["Impressions"], np.nan)

    merged = first.merge(last, on="Product", suffixes=("_first", "_last"), how="outer")

    deltas = pd.DataFrame({"Product": merged["Product"]})
    for m in metrics:
        fc = f"{m}_first"
        lc = f"{m}_last"
        deltas[f"{m}_first"] = merged[fc]
        deltas[f"{m}_last"] = merged[lc]
        deltas[f"{m}_delta"] = merged[lc].fillna(0) - merged[fc].fillna(0)
        deltas[f"{m}_delta_pct"] = np.where(
            merged[fc].fillna(0) != 0,
            (merged[lc].fillna(0) - merged[fc].fillna(0)) / merged[fc].abs() * 100,
            np.nan,
        )

    return deltas


def _build_product_table(
    view: pd.DataFrame,
    deltas_df: pd.DataFrame | None,
    has_multiple_periods: bool,
) -> pd.DataFrame:
    """Aggregate per product and build the display table."""
    metrics = ["Page Views", "Clicks", "Impressions", "Purchases"]
    grouped = view.groupby("Product")[metrics].sum(min_count=1).reset_index()
    grouped["CVR"] = np.where(
        grouped["Clicks"].fillna(0) > 0,
        grouped["Purchases"].fillna(0) / grouped["Clicks"],
        np.nan,
    )
    grouped["CTR"] = np.where(
        grouped["Impressions"].fillna(0) > 0,
        grouped["Clicks"].fillna(0) / grouped["Impressions"],
        np.nan,
    )

    # Format rates as percentages for display
    display = grouped.copy()
    display["CVR"] = display["CVR"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
    display["CTR"] = display["CTR"].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")

    if has_multiple_periods and deltas_df is not None:
        for m in ["Page Views", "Clicks", "Impressions", "Purchases", "CVR", "CTR"]:
            dc = f"{m}_delta"
            dpc = f"{m}_delta_pct"
            if dc in deltas_df.columns:
                delta_sub = deltas_df[["Product", dc, dpc]].copy()
                delta_sub = delta_sub.rename(columns={dc: f"{m} Δ", dpc: f"{m} Δ%"})
                display = display.merge(delta_sub, on="Product", how="left")

    return display


def _detect_segment_columns(
    df: pd.DataFrame,
    mapped_cols: list[str | None],
) -> list[str]:
    """Identify categorical columns that could serve as segment filters."""
    mapped_set = {c for c in mapped_cols if c is not None}
    segments = []
    for col in df.columns:
        if col in mapped_set:
            continue
        if df[col].dtype == object or str(df[col].dtype) == "category":
            nunique = df[col].nunique()
            if 2 <= nunique <= 200:
                segments.append(col)
    return segments[:5]  # cap at 5


def _chart_time_trend(view: pd.DataFrame, metric: str, all_products: list):
    """Line chart of a metric over time, with optional product selector."""
    trend_products = st.multiselect(
        "Select products for trend",
        all_products,
        default=all_products[:5],
        key="trend_products",
    )
    if not trend_products:
        st.info("Select at least one product.")
        return

    sub = view[view["Product"].isin(trend_products)].copy()
    if sub.empty:
        st.info("No data for selected products in current time range.")
        return

    # For rate metrics, recompute per product per period
    if metric in ("CVR", "CTR"):
        grouped = sub.groupby(["Time Period", "Product"]).agg(
            Clicks=("Clicks", "sum"),
            Impressions=("Impressions", "sum"),
            Purchases=("Purchases", "sum"),
        ).reset_index()
        if metric == "CVR":
            grouped["value"] = np.where(grouped["Clicks"] > 0, grouped["Purchases"] / grouped["Clicks"] * 100, np.nan)
        else:
            grouped["value"] = np.where(grouped["Impressions"] > 0, grouped["Clicks"] / grouped["Impressions"] * 100, np.nan)
        grouped["metric_label"] = metric
    else:
        grouped = sub.groupby(["Time Period", "Product"])[metric].sum(min_count=1).reset_index()
        grouped = grouped.rename(columns={metric: "value"})

    fig = px.line(
        grouped,
        x="Time Period",
        y="value",
        color="Product",
        markers=True,
        labels={"value": metric, "Time Period": "Period"},
        title=f"{metric} over Time",
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)


def _chart_top_movers(
    deltas_df: pd.DataFrame,
    metric: str,
    top_n: int,
    sort_by: str,
    direction: str,
    selected_products: list,
):
    """Bar chart of biggest movers (delta-based)."""
    dcol = f"{metric}_delta"
    dpcol = f"{metric}_delta_pct"
    if dcol not in deltas_df.columns:
        st.info(f"No delta data for {metric}.")
        return

    sub = deltas_df.dropna(subset=[dcol]).copy()
    if selected_products:
        sub = sub[sub["Product"].isin(selected_products)]

    sort_col = dpcol if sort_by == "delta_pct" else dcol
    ascending = direction == "Biggest decreases"
    sub = sub.sort_values(sort_col, ascending=ascending).head(top_n)

    fig = px.bar(
        sub,
        x="Product",
        y=dcol,
        color=dpcol,
        color_continuous_scale="RdYlGn",
        labels={dcol: f"{metric} Δ", dpcol: f"{metric} Δ%"},
        title=f"{direction}: {metric}",
        hover_data=[dpcol],
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)


def _chart_top_movers_static(view: pd.DataFrame, metric: str, top_n: int, direction: str):
    """Fallback bar chart when no time deltas exist — show top/bottom by value."""
    if metric in ("CVR", "CTR"):
        grouped = view.groupby("Product").agg(
            Clicks=("Clicks", "sum"),
            Impressions=("Impressions", "sum"),
            Purchases=("Purchases", "sum"),
        ).reset_index()
        if metric == "CVR":
            grouped["value"] = np.where(grouped["Clicks"] > 0, grouped["Purchases"] / grouped["Clicks"] * 100, np.nan)
        else:
            grouped["value"] = np.where(grouped["Impressions"] > 0, grouped["Clicks"] / grouped["Impressions"] * 100, np.nan)
    else:
        grouped = view.groupby("Product")[metric].sum(min_count=1).reset_index()
        grouped = grouped.rename(columns={metric: "value"})

    grouped = grouped.dropna(subset=["value"])
    ascending = direction == "Biggest decreases"
    sub = grouped.sort_values("value", ascending=ascending).head(top_n)

    fig = px.bar(
        sub,
        x="Product",
        y="value",
        labels={"value": metric},
        title=f"{'Bottom' if ascending else 'Top'} {top_n} by {metric}",
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)


def _chart_scatter(view: pd.DataFrame):
    """Scatter: impressions vs clicks, bubble = page views, color = CVR."""
    grouped = view.groupby("Product").agg(
        Impressions=("Impressions", "sum"),
        Clicks=("Clicks", "sum"),
        PageViews=("Page Views", "sum"),
        Purchases=("Purchases", "sum"),
    ).reset_index()
    grouped["CVR"] = np.where(
        grouped["Clicks"] > 0,
        grouped["Purchases"] / grouped["Clicks"] * 100,
        np.nan,
    )
    grouped["PageViews"] = grouped["PageViews"].fillna(1).clip(lower=1)

    grouped = grouped.dropna(subset=["Impressions", "Clicks"])
    if grouped.empty:
        st.info("Not enough data for scatter plot.")
        return

    fig = px.scatter(
        grouped,
        x="Impressions",
        y="Clicks",
        size="PageViews",
        color="CVR",
        color_continuous_scale="Viridis",
        hover_name="Product",
        hover_data={"Impressions": ":,.0f", "Clicks": ":,.0f", "PageViews": ":,.0f", "CVR": ":.2f%"},
        title="Efficiency: Impressions vs Clicks (size = Page Views, color = CVR)",
        size_max=50,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
