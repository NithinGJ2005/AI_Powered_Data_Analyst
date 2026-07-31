"""
ui/report.py
============
Enterprise Report UI tab.

Provides configuration inputs and a one-click PDF generation + download
button.  All rendering is self-contained; no existing UI modules are touched.
"""

import datetime
import streamlit as st
from utils import logger
from services.report_service import ReportService


def render_report_tab():
    """
    Renders the Enterprise Report generation tab.

    Lets the user configure a company name and report title, previews
    which sections will be populated, then generates and streams a
    branded PDF document for immediate browser download.
    """
    st.subheader("📄 Enterprise Report Generator")
    st.markdown(
        "<p style='color: #94A3B8; font-size: 0.95rem; "
        "margin-top: -0.5rem; margin-bottom: 1.5rem;'>"
        "Generate a professionally formatted PDF report that consolidates all "
        "datasets, AI insights, SQL queries, charts, anomaly findings, and "
        "forecast results into a single executive document."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Configuration Panel ──────────────────────────────────────────────────
    st.markdown("### ⚙️ Report Configuration")
    cfg_col1, cfg_col2 = st.columns(2)

    with cfg_col1:
        company_name = st.text_input(
            "Company / Organisation Name",
            value="Enterprise Analytics",
            key="report_company_name",
            help="Appears in the PDF header and cover page.",
        )

    with cfg_col2:
        report_title = st.text_input(
            "Report Title",
            value="AI Data Analytics Report",
            key="report_title",
            help="Main title shown on the PDF cover page.",
        )

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # ── Section Availability Preview ─────────────────────────────────────────
    st.markdown("### 📋 Report Sections Preview")
    st.markdown(
        "<p style='color: #94A3B8; font-size: 0.88rem; margin-top: -0.4rem; "
        "margin-bottom: 1rem;'>"
        "Sections marked ✅ will be fully populated. "
        "Sections marked ⬜ are included but will show a 'no data' notice."
        "</p>",
        unsafe_allow_html=True,
    )

    data = st.session_state.get("data", {})
    messages = st.session_state.get("messages", [])
    anomalies = st.session_state.get("anomalies", {})
    forecasts = st.session_state.get("forecasts", {})

    has_data = bool(data)
    has_sql = any(
        m.get("sql_query") for m in messages if m.get("role") == "assistant"
    )
    has_pandas = any(
        m.get("pandas_code") for m in messages if m.get("role") == "assistant"
    )
    has_ai = any(m.get("role") == "assistant" for m in messages)
    has_anomalies = bool(anomalies)
    has_forecasts = bool(forecasts)

    def _status(flag: bool) -> str:
        return "✅" if flag else "⬜"

    sections = [
        (_status(True),        "Cover Page",              "Always included"),
        (_status(has_data),    "Executive Summary",       f"{len(data)} dataset(s) loaded"),
        (_status(has_data),    "Dataset Overview",        f"{len(data)} dataset(s)"),
        (_status(has_data),    "KPI Summary",             "Numeric column statistics"),
        (_status(has_ai),      "AI Insights",             f"{sum(1 for m in messages if m.get('role') == 'assistant')} AI response(s)"),
        (_status(has_sql),     "SQL Queries Generated",   "From chat history"),
        (_status(has_pandas),  "Pandas Code Generated",   "From chat history"),
        (_status(has_data),    "Charts",                  "Auto-generated from datasets"),
        (_status(has_data),    "Data Quality Report",     "Missing values & duplicates"),
        (_status(has_forecasts), "Forecast Results",      f"{len(forecasts)} forecast(s)"),
        (_status(has_anomalies), "Anomaly Report",        f"{len(anomalies)} dataset(s) scanned"),
        (_status(True),        "Final Recommendations",   "Heuristic-based action items"),
    ]

    # Render as a clean HTML table for consistent spacing
    rows_html = "".join(
        f"<tr>"
        f"<td style='padding:6px 10px;font-size:1rem;'>{status}</td>"
        f"<td style='padding:6px 10px;font-weight:600;color:#F8FAFC;"
        f"font-size:0.88rem;'>{section}</td>"
        f"<td style='padding:6px 10px;color:#94A3B8;font-size:0.82rem;'>{note}</td>"
        f"</tr>"
        for status, section, note in sections
    )
    st.markdown(
        f"""
        <div style='background:rgba(30,41,59,0.5);border:1px solid #334155;
                    border-radius:10px;overflow:hidden;margin-bottom:1.5rem;'>
          <table style='width:100%;border-collapse:collapse;'>
            <thead>
              <tr style='background:rgba(59,130,246,0.15);'>
                <th style='padding:8px 10px;text-align:left;color:#60A5FA;
                           font-size:0.8rem;width:44px;'>Status</th>
                <th style='padding:8px 10px;text-align:left;color:#60A5FA;
                           font-size:0.8rem;'>Section</th>
                <th style='padding:8px 10px;text-align:left;color:#60A5FA;
                           font-size:0.8rem;'>Details</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # ── Generate Button ───────────────────────────────────────────────────────
    st.markdown("### 🚀 Generate Report")

    if not has_data:
        st.warning(
            "⚠️ No datasets are currently loaded. "
            "Upload one or more CSV files via the sidebar to generate a meaningful report."
        )

    generate_col, _ = st.columns([1, 2])
    with generate_col:
        generate_clicked = st.button(
            "📄 Generate & Download PDF",
            use_container_width=True,
            key="generate_report_btn",
        )

    if generate_clicked:
        _run_report_generation(company_name, report_title)


def _run_report_generation(company_name: str, report_title: str):
    """
    Triggers the ReportService, streams bytes into a download button,
    and shows an inline success / error card.
    """
    with st.spinner("Building your enterprise PDF report…"):
        try:
            pdf_bytes = ReportService.generate_pdf(
                session_state=st.session_state,
                company_name=company_name or "Enterprise Analytics",
                report_title=report_title or "AI Data Analytics Report",
            )
        except Exception as e:
            logger.error(f"Report generation failed in UI: {e}", exc_info=True)
            st.markdown(
                f"""
                <div style="text-align:center;padding:2.5rem 1rem;
                            background:rgba(239,68,68,0.08);
                            border:1px solid rgba(239,68,68,0.25);
                            border-radius:10px;margin-top:1rem;">
                  <div style="font-size:2.5rem;margin-bottom:0.75rem;">❌</div>
                  <h4 style="color:#F87171;margin-bottom:0.5rem;">
                    Report Generation Failed
                  </h4>
                  <p style="font-size:0.88rem;color:#FCA5A5;">{str(e)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

    # Success card
    size_kb = len(pdf_bytes) / 1024
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analytics_report_{ts}.pdf"

    st.markdown(
        f"""
        <div style="text-align:center;padding:2rem 1rem;
                    background:rgba(16,185,129,0.08);
                    border:1px solid rgba(16,185,129,0.25);
                    border-radius:10px;margin-top:1rem;margin-bottom:1rem;">
          <div style="font-size:2.5rem;margin-bottom:0.75rem;">✅</div>
          <h4 style="color:#10B981;margin-bottom:0.4rem;">
            Report Ready — {size_kb:.1f} KB
          </h4>
          <p style="font-size:0.88rem;color:#CBD5E1;">
            Click the button below to download your PDF report.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.download_button(
        label="📥 Download PDF Report",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        key="download_pdf_btn",
        use_container_width=True,
    )

    logger.info(f"PDF report ready for download: {filename} ({size_kb:.1f} KB)")
