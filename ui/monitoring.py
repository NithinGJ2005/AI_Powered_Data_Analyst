import os
import re
import pandas as pd
import streamlit as st
import plotly.express as px
from services.evaluation_service import EvaluationService
import config
from utils import logger

# ─────────────────────────────────────────────
# Log Parsing Helpers
# ─────────────────────────────────────────────

_LOG_PATTERN = re.compile(
    r"\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\]\s+(?P<level>\w+)\s+\[(?P<module>[^\]]+)\]\s+-\s+(?P<msg>.*)"
)

_CLASSIFIERS = {
    "AI Request":       ["get_chat_response", "Requesting gemini", "requesting gemini",
                         "generate_content", "requesting dashboard", "requesting anomaly"],
    "SQL Request":      ["execute_sql", "sql query", "duckdb", "executing sql"],
    "Forecast Request": ["forecast", "triggering forecast", "forecastservice"],
    "Anomaly Request":  ["anomaly detection", "anomalyservice", "isolation forest",
                         "triggering anomaly"],
    "Dataset Upload":   ["load_csv", "dataset loaded", "loaded csv", "loadermodule"],
    "Report Download":  ["generate_pdf", "reportservice", "pdf report"],
    "Recommendation":   ["recommendationservice", "run_analysis", "recommendation"],
    "Error":            [],   # classified by log level
}


def _classify(level: str, msg: str) -> str:
    if level == "ERROR":
        return "Error"
    msg_lower = msg.lower()
    for label, kws in _CLASSIFIERS.items():
        if label == "Error":
            continue
        if any(kw in msg_lower for kw in kws):
            return label
    return "Other"


def _parse_log_file(max_lines: int = 2000) -> pd.DataFrame:
    """
    Reads `logs/app.log`, parses structured fields, and returns a tidy DataFrame.
    Returns empty DataFrame when log file is absent.
    """
    log_path = config.LOG_FILE
    if not os.path.exists(log_path):
        return pd.DataFrame(columns=["timestamp", "level", "module", "message", "category"])

    rows = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()[-max_lines:]
        for line in lines:
            m = _LOG_PATTERN.match(line.strip())
            if not m:
                continue
            ts_str  = m.group("ts").replace(",", ".")   # make parseable
            ts      = pd.to_datetime(ts_str, format="%Y-%m-%d %H:%M:%S.%f", errors="coerce")
            level   = m.group("level")
            module  = m.group("module")
            msg     = m.group("msg")
            category = _classify(level, msg)
            rows.append({"timestamp": ts, "level": level, "module": module,
                         "message": msg, "category": category})
    except Exception as e:
        logger.warning(f"Monitoring: failed to parse log file: {e}")

    if not rows:
        return pd.DataFrame(columns=["timestamp", "level", "module", "message", "category"])

    df = pd.DataFrame(rows).dropna(subset=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    return df


def _bucket_by_10min(df: pd.DataFrame) -> pd.DataFrame:
    """Groups log events into 10-minute time buckets by category."""
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["bucket"] = df["timestamp"].dt.floor("10min")
    grouped = df.groupby(["bucket", "category"]).size().reset_index(name="count")
    return grouped


# ─────────────────────────────────────────────
# Main Render
# ─────────────────────────────────────────────

def render_monitoring_tab():
    """
    Renders the Observability Monitoring dashboard.
    Sources: EvaluationService (evaluations.json) + app.log parser.
    """
    st.subheader("📡 Observability Monitoring")
    st.markdown(
        "<p style='color:#94A3B8;font-size:0.95rem;margin-top:-0.5rem;margin-bottom:1.5rem;'>"
        "Real-time system telemetry parsed from application logs and AI interaction records. "
        "No external monitoring tools required."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Refresh button ────────────────────────────────────────────────────
    if st.button("🔄 Refresh Monitoring Data", use_container_width=True, key="refresh_monitoring"):
        st.rerun()

    # ── Load data sources ────────────────────────────────────────────────
    metrics      = EvaluationService.get_metrics()
    evals        = EvaluationService.get_evaluations()
    log_df       = _parse_log_file()

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 1 — Session Statistics
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("### 📊 Session Statistics")

    num_datasets  = len(st.session_state.get("data", {}))
    total_rows    = sum(len(v["df"]) for v in st.session_state.get("data", {}).values())
    total_cols    = sum(len(v["df"].columns) for v in st.session_state.get("data", {}).values())
    anomaly_runs  = sum(1 for v in st.session_state.get("anomalies", {}).values() if v)
    forecast_runs = sum(1 for v in st.session_state.get("forecasts", {}).values() if v)
    rec_runs      = sum(1 for v in st.session_state.get("recommendations", {}).values() if v)

    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.metric("📂 Datasets Loaded",   num_datasets)
    s2.metric("📊 Total Rows",        f"{total_rows:,}")
    s3.metric("📋 Total Columns",     f"{total_cols:,}")
    s4.metric("🚨 Anomaly Runs",      anomaly_runs)
    s5.metric("🔮 Forecast Runs",     forecast_runs)
    s6.metric("🧠 Rec. Engine Runs",  rec_runs)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 2 — AI Request Metrics (from evaluations.json)
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("### 🤖 AI Request Metrics")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total AI Queries",      metrics["total_queries"])
    m2.metric("SQL Requests",          sum(1 for e in evals if e.get("generated_sql", "").strip()))
    m3.metric("Avg Latency (s)",       f"{metrics['avg_response_time']:.2f}s")
    m4.metric("SQL Success Rate",      f"{metrics['sql_success_rate']:.1f}%")
    m5.metric("Failed Queries",        metrics["failed_queries"])
    m6.metric("Avg Confidence",        f"{metrics['avg_confidence']:.1f}%")

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 3 — Log-derived Metrics
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("### 📋 Log Event Breakdown")

    if log_df.empty:
        st.info("No log data available yet. Interact with the application to generate log entries.")
    else:
        # Category totals
        cat_counts = log_df["category"].value_counts().reset_index()
        cat_counts.columns = ["Category", "Count"]

        l1, l2, l3, l4 = st.columns(4)
        def _cat_count(name):
            row = cat_counts[cat_counts["Category"] == name]
            return int(row["Count"].iloc[0]) if not row.empty else 0

        l1.metric("AI Requests",       _cat_count("AI Request"))
        l2.metric("SQL Requests",      _cat_count("SQL Request"))
        l3.metric("Forecast Requests", _cat_count("Forecast Request"))
        l4.metric("Anomaly Requests",  _cat_count("Anomaly Request"))

        l5, l6, l7, l8 = st.columns(4)
        l5.metric("Dataset Uploads",   _cat_count("Dataset Upload"))
        l6.metric("Report Downloads",  _cat_count("Report Download"))
        l7.metric("Recommendations",   _cat_count("Recommendation"))
        l8.metric("Errors",            _cat_count("Error"))

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

        # ──────────────────────────────────────────────────────────────
        # CHARTS
        # ──────────────────────────────────────────────────────────────
        st.markdown("### 📈 Observability Charts")

        DARK_LAYOUT = dict(
            template="plotly_dark",
            paper_bgcolor="#1E293B",
            plot_bgcolor="#1E293B",
            font=dict(color="#CBD5E1"),
        )

        # Row 1: Request distribution pie + Request count bar
        ch1, ch2 = st.columns(2)

        with ch1:
            fig_pie = px.pie(
                cat_counts,
                names="Category",
                values="Count",
                title="Request Type Distribution",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            fig_pie.update_layout(**DARK_LAYOUT)
            st.plotly_chart(fig_pie, use_container_width=True)

        with ch2:
            fig_bar = px.bar(
                cat_counts.sort_values("Count", ascending=False),
                x="Category",
                y="Count",
                title="Total Events by Category",
                color="Category",
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            fig_bar.update_layout(**DARK_LAYOUT, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        # Row 2: Stacked area chart over 10-min buckets
        bucketed = _bucket_by_10min(log_df)
        if not bucketed.empty:
            fig_area = px.bar(
                bucketed,
                x="bucket",
                y="count",
                color="category",
                barmode="stack",
                title="Request Activity Over Time (10-min buckets)",
                labels={"bucket": "Time", "count": "Events", "category": "Category"},
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            fig_area.update_layout(**DARK_LAYOUT)
            st.plotly_chart(fig_area, use_container_width=True)

        # Row 3: Latency trend from evaluations + Error frequency
        ch3, ch4 = st.columns(2)

        with ch3:
            if evals:
                eval_df = pd.DataFrame(evals)
                eval_df["timestamp"] = pd.to_datetime(eval_df["timestamp"], errors="coerce")
                eval_df = eval_df.dropna(subset=["timestamp"]).sort_values("timestamp")
                fig_lat = px.line(
                    eval_df,
                    x="timestamp",
                    y="execution_time",
                    title="AI Response Latency Over Time (s)",
                    labels={"timestamp": "Time", "execution_time": "Latency (s)"},
                    markers=True,
                    color_discrete_sequence=["#60A5FA"],
                )
                fig_lat.update_layout(**DARK_LAYOUT)
                st.plotly_chart(fig_lat, use_container_width=True)
            else:
                with st.container(border=True):
                    st.markdown(
                        "<div style='text-align:center;padding:2rem;color:#64748B'>"
                        "<div style='font-size:2rem'>⏱️</div>"
                        "<p>No latency data yet — ask the AI a question first.</p></div>",
                        unsafe_allow_html=True,
                    )

        with ch4:
            error_df = log_df[log_df["level"] == "ERROR"].copy()
            if not error_df.empty:
                error_df["hour"] = error_df["timestamp"].dt.floor("h")
                err_counts = error_df.groupby("hour").size().reset_index(name="errors")
                fig_err = px.bar(
                    err_counts,
                    x="hour",
                    y="errors",
                    title="Error Events by Hour",
                    labels={"hour": "Hour", "errors": "Error Count"},
                    color_discrete_sequence=["#EF4444"],
                )
                fig_err.update_layout(**DARK_LAYOUT)
                st.plotly_chart(fig_err, use_container_width=True)
            else:
                with st.container(border=True):
                    st.markdown(
                        "<div style='text-align:center;padding:2rem;color:#10B981'>"
                        "<div style='font-size:2rem'>✅</div>"
                        "<h4 style='color:white'>Zero Errors Logged</h4>"
                        "<p>All system components running without errors.</p></div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

        # ──────────────────────────────────────────────────────────────
        # LOG EXPLORER
        # ──────────────────────────────────────────────────────────────
        st.markdown("### 🔍 Log Explorer")

        filter_cols = st.columns(3)
        with filter_cols[0]:
            level_filter = st.multiselect(
                "Filter by Level",
                options=["INFO", "WARNING", "ERROR", "DEBUG"],
                default=["INFO", "WARNING", "ERROR"],
                key="mon_level_filter",
            )
        with filter_cols[1]:
            cat_options = sorted(log_df["category"].unique().tolist())
            cat_filter = st.multiselect(
                "Filter by Category",
                options=cat_options,
                default=cat_options,
                key="mon_cat_filter",
            )
        with filter_cols[2]:
            search_term = st.text_input("Search Message", placeholder="Type to filter...", key="mon_search")

        display_df = log_df[log_df["level"].isin(level_filter)]
        display_df = display_df[display_df["category"].isin(cat_filter)]
        if search_term:
            display_df = display_df[display_df["message"].str.contains(search_term, case=False, na=False)]

        display_df = display_df.tail(200).iloc[::-1]   # most-recent first

        st.dataframe(
            display_df[["timestamp", "level", "category", "module", "message"]],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 4 — Export
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("### 📥 Export Monitoring Report")

    export_rows = [
        {"Metric": "Total AI Queries",       "Value": metrics["total_queries"]},
        {"Metric": "SQL Requests",           "Value": sum(1 for e in evals if e.get("generated_sql", "").strip())},
        {"Metric": "Avg Latency (s)",        "Value": f"{metrics['avg_response_time']:.3f}"},
        {"Metric": "SQL Success Rate (%)",   "Value": f"{metrics['sql_success_rate']:.1f}"},
        {"Metric": "Failed Queries",         "Value": metrics["failed_queries"]},
        {"Metric": "Avg Confidence (%)",     "Value": f"{metrics['avg_confidence']:.1f}"},
        {"Metric": "Active Datasets",        "Value": num_datasets},
        {"Metric": "Total Rows Loaded",      "Value": total_rows},
        {"Metric": "Anomaly Runs",           "Value": anomaly_runs},
        {"Metric": "Forecast Runs",          "Value": forecast_runs},
        {"Metric": "Recommendation Runs",    "Value": rec_runs},
    ]

    if not log_df.empty:
        for cat, cnt in log_df["category"].value_counts().items():
            export_rows.append({"Metric": f"Log Events — {cat}", "Value": int(cnt)})

    export_df = pd.DataFrame(export_rows)

    st.download_button(
        label="📥 Download Monitoring Report (CSV)",
        data=export_df.to_csv(index=False).encode("utf-8"),
        file_name="monitoring_report.csv",
        mime="text/csv",
        use_container_width=True,
        key="dl_monitoring",
    )
