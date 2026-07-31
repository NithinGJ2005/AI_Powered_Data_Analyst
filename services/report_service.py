"""
services/report_service.py
==========================
Enterprise PDF Report Generator using reportlab.

Assembles session-state data (datasets, chat history, anomaly results,
forecast results) into a professionally formatted, branded PDF document.

All sections are optional — missing data is handled gracefully so the
report always generates without crashing.
"""

import io
import time
import textwrap
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

# reportlab imports
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    HRFlowable,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Frame,
)

from utils import logger

# ── Brand Colours (mirror app CSS variables) ────────────────────────────────
BRAND_BLUE = colors.HexColor("#1D4ED8")
BRAND_INDIGO = colors.HexColor("#6366F1")
ACCENT_LIGHT = colors.HexColor("#3B82F6")
BG_DARK = colors.HexColor("#0F172A")
CARD_BG = colors.HexColor("#1E293B")
TEXT_PRIMARY = colors.HexColor("#F8FAFC")
TEXT_SECONDARY = colors.HexColor("#CBD5E1")
BORDER_COLOR = colors.HexColor("#334155")
SUCCESS_GREEN = colors.HexColor("#10B981")
DANGER_RED = colors.HexColor("#EF4444")

# Light-page equivalents (PDF is white)
PAGE_BG = colors.white
SECTION_HEADER_BG = colors.HexColor("#EFF6FF")  # very light blue
TABLE_ROW_ALT = colors.HexColor("#F8FAFC")
TABLE_HEADER_BG = BRAND_BLUE
TABLE_HEADER_TEXT = colors.white
DIVIDER_COLOR = colors.HexColor("#BFDBFE")

W, H = A4  # 595.27 × 841.89 pts


# ── Helper: safe truncate long strings ──────────────────────────────────────
def _trunc(text: str, max_len: int = 80) -> str:
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_len else text[:max_len - 3] + "..."


def _safe_str(val: Any, max_len: int = 60) -> str:
    """Convert any value to a display-safe string."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    return _trunc(str(val), max_len)


# ── Style Registry ───────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()

    styles = {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontSize=32,
            leading=40,
            textColor=BRAND_BLUE,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            parent=base["Normal"],
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748B"),
            alignment=TA_CENTER,
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            parent=base["Heading1"],
            fontSize=16,
            leading=22,
            textColor=BRAND_BLUE,
            spaceBefore=14,
            spaceAfter=6,
            borderPad=4,
        ),
        "subsection_heading": ParagraphStyle(
            "subsection_heading",
            parent=base["Heading2"],
            fontSize=12,
            leading=16,
            textColor=BRAND_INDIGO,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=4,
        ),
        "body_small": ParagraphStyle(
            "body_small",
            parent=base["Normal"],
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#334155"),
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontSize=7.5,
            leading=11,
            textColor=colors.HexColor("#1E293B"),
            backColor=colors.HexColor("#F1F5F9"),
            borderPad=6,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#1E293B"),
            leftIndent=14,
            bulletIndent=4,
            spaceAfter=3,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontSize=7.5,
            leading=11,
            textColor=colors.HexColor("#64748B"),
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontSize=7,
            leading=10,
            textColor=colors.HexColor("#94A3B8"),
            alignment=TA_CENTER,
        ),
    }
    return styles


# ── Page Template with header/footer ────────────────────────────────────────
class _BrandedDocTemplate(BaseDocTemplate):
    """
    Custom document template that draws a branded header and footer
    on every page after the cover.
    """

    def __init__(self, buf, company_name: str, report_title: str, **kwargs):
        super().__init__(buf, **kwargs)
        self.company_name = company_name
        self.report_title = report_title
        self._page_count = 0

        margin = 18 * mm
        frame = Frame(
            margin, margin + 12 * mm,   # leave room for footer
            W - 2 * margin,
            H - 2 * margin - 22 * mm,   # leave room for header + footer
            id="main",
        )
        cover_frame = Frame(
            margin, margin,
            W - 2 * margin,
            H - 2 * margin,
            id="cover",
        )
        self.addPageTemplates([
            PageTemplate(id="cover_page", frames=[cover_frame]),
            PageTemplate(id="content_page", frames=[frame],
                         onPage=self._draw_chrome),
        ])

    def _draw_chrome(self, canvas, doc):
        """Draw header rule and footer on content pages."""
        canvas.saveState()
        margin = 18 * mm

        # ── Header bar ─────────────────────────────────────────────────────
        canvas.setFillColor(BRAND_BLUE)
        canvas.rect(margin, H - margin - 10 * mm,
                    W - 2 * margin, 0.6 * mm, fill=1, stroke=0)

        # Company name (left) and report title (right)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(BRAND_BLUE)
        canvas.drawString(margin, H - margin - 7 * mm, self.company_name)

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#475569"))
        title_x = W - margin - canvas.stringWidth(
            self.report_title, "Helvetica", 7.5)
        canvas.drawString(title_x, H - margin - 7 * mm, self.report_title)

        # ── Footer ─────────────────────────────────────────────────────────
        canvas.setFillColor(colors.HexColor("#CBD5E1"))
        canvas.rect(margin, margin + 8 * mm,
                    W - 2 * margin, 0.4 * mm, fill=1, stroke=0)

        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94A3B8"))
        canvas.drawString(margin, margin + 3 * mm,
                          f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        page_str = f"Page {doc.page}"
        canvas.drawRightString(W - margin, margin + 3 * mm, page_str)

        canvas.restoreState()


# ── Utility builders ─────────────────────────────────────────────────────────
def _section_header(title: str, styles: dict):
    """Returns a section header block (heading + divider)."""
    return [
        Spacer(1, 6),
        Paragraph(title, styles["section_heading"]),
        HRFlowable(width="100%", thickness=1.2,
                   color=DIVIDER_COLOR, spaceAfter=6),
    ]


def _subsection_header(title: str, styles: dict):
    return [Paragraph(title, styles["subsection_heading"])]


def _make_table(headers: list, rows: list, col_widths=None) -> Table:
    """
    Build a styled reportlab Table with branded header row
    and alternating row shading.
    """
    data = [headers] + rows
    tbl = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), TABLE_HEADER_TEXT),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#1E293B")),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, TABLE_ROW_ALT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _plotly_to_image(fig, width: int = 520, height: int = 260):
    """
    Convert a Plotly figure to PNG bytes via kaleido.
    Returns None if kaleido is unavailable or conversion fails.
    """
    try:
        import plotly.io as pio
        # Use white background for PDF (override dark theme)
        fig_copy = fig
        fig_copy = fig.update_layout(
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(color="#1E293B"),
        )
        png_bytes = pio.to_image(fig_copy, format="png",
                                 width=width * 2, height=height * 2,
                                 scale=1)
        return png_bytes
    except Exception as e:
        logger.warning(f"Chart export to PNG failed (kaleido): {e}")
        return None


def _embed_chart(fig, caption: str, styles: dict,
                 max_width_pt: float = 460) -> list:
    """
    Convert a Plotly figure to an embedded Image flowable.
    Falls back to a text notice if conversion fails.
    """
    png_bytes = _plotly_to_image(fig)
    if png_bytes is None:
        return [Paragraph(
            f"⚠ Chart '{caption}' could not be rendered (kaleido unavailable).",
            styles["body_small"]
        )]

    buf = io.BytesIO(png_bytes)
    img = Image(buf, width=max_width_pt, height=max_width_pt * 0.5)
    return [img, Paragraph(caption, styles["caption"]), Spacer(1, 6)]


def _code_block(code_text: str, styles: dict, max_lines: int = 30) -> list:
    """Render a preformatted code block, truncated to max_lines."""
    if not code_text or not code_text.strip():
        return []
    lines = code_text.strip().splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines)"]
    safe_code = "<br/>".join(
        line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for line in lines
    )
    return [Paragraph(safe_code, styles["code"]), Spacer(1, 4)]


# ── Section builders ─────────────────────────────────────────────────────────

def _build_cover(company_name: str, report_title: str, styles: dict,
                 dataset_names: list) -> list:
    story = []
    story.append(Spacer(1, 60))

    # Logo placeholder rectangle drawn via a Table cell background
    logo_data = [["📊"]]
    logo_tbl = Table(logo_data, colWidths=[50], rowHeights=[50])
    logo_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 24),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    # Center the logo table
    outer = Table([[logo_tbl]], colWidths=[W - 36 * mm])
    outer.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(outer)
    story.append(Spacer(1, 24))

    story.append(Paragraph(report_title, styles["cover_title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(company_name, styles["cover_subtitle"]))
    story.append(Spacer(1, 16))

    ts = datetime.now().strftime("%B %d, %Y — %H:%M")
    story.append(Paragraph(f"Generated: {ts}", styles["cover_meta"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Datasets: {', '.join(dataset_names) if dataset_names else 'None'}",
        styles["cover_meta"]
    ))

    # Decorative divider
    story.append(Spacer(1, 32))
    story.append(HRFlowable(
        width="60%", thickness=2,
        color=BRAND_BLUE, spaceAfter=4,
        hAlign="CENTER"
    ))
    story.append(Paragraph(
        "Enterprise AI Data Analytics Platform",
        styles["cover_meta"]
    ))
    return story


def _build_executive_summary(session_data: dict, styles: dict,
                             company_name: str) -> list:
    story = [*_section_header("1. Executive Summary", styles)]

    data = session_data.get("data", {})
    messages = session_data.get("messages", [])
    anomalies = session_data.get("anomalies", {})
    forecasts = session_data.get("forecasts", {})

    num_ds = len(data)
    total_rows = sum(len(v["df"]) for v in data.values() if "df" in v)
    total_cols = sum(len(v["df"].columns) for v in data.values() if "df" in v)
    total_missing = sum(
        v["df"].isnull().sum().sum() for v in data.values() if "df" in v
    )
    chat_q = sum(1 for m in messages if m.get("role") == "user")
    anomaly_total = sum(
        len(v.get("anomalies", pd.DataFrame()))
        for v in anomalies.values()
    )
    forecast_count = len(forecasts)

    bullets = [
        f"<b>Datasets analysed:</b> {num_ds}",
        f"<b>Total records:</b> {total_rows:,}",
        f"<b>Total columns:</b> {total_cols:,}",
        f"<b>Missing values detected:</b> {int(total_missing):,}",
        f"<b>AI queries answered:</b> {chat_q}",
        f"<b>Anomalies detected:</b> {anomaly_total:,}",
        f"<b>Forecast analyses run:</b> {forecast_count}",
    ]
    for b in bullets:
        story.append(Paragraph(f"• {b}", styles["bullet"]))

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"This report was automatically generated by the {company_name} Enterprise AI "
        "Analytics Platform. It consolidates data quality assessments, machine-learning "
        "anomaly detection outputs, time-series forecasts, and AI-generated insights "
        "into a single executive document.",
        styles["body"]
    ))
    return story


def _build_dataset_overview(session_data: dict, styles: dict) -> list:
    story = [*_section_header("2. Dataset Overview", styles)]
    data = session_data.get("data", {})

    if not data:
        story.append(Paragraph("No datasets were loaded.", styles["body"]))
        return story

    for name, result in data.items():
        df: pd.DataFrame = result.get("df")
        if df is None:
            continue

        story += _subsection_header(f"📂 {name}", styles)

        # Shape + dtype summary table
        shape_rows = [
            ["Rows", f"{len(df):,}"],
            ["Columns", str(len(df.columns))],
            ["Memory", f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB"],
            ["Duplicates", str(df.duplicated().sum())],
        ]
        story.append(_make_table(
            ["Attribute", "Value"], shape_rows,
            col_widths=[120, 300]
        ))
        story.append(Spacer(1, 6))

        # Column summary table (up to 20 cols)
        col_rows = []
        for col in list(df.columns)[:20]:
            dtype = str(df[col].dtype)
            missing = int(df[col].isnull().sum())
            pct = f"{missing / len(df) * 100:.1f}%" if len(df) > 0 else "—"
            unique = df[col].nunique()
            col_rows.append([
                _trunc(col, 28), dtype,
                f"{missing:,} ({pct})", str(unique)
            ])
        if len(df.columns) > 20:
            col_rows.append([
                f"... {len(df.columns) - 20} more columns",
                "", "", ""
            ])

        story.append(_make_table(
            ["Column", "Dtype", "Missing", "Unique"],
            col_rows,
            col_widths=[145, 80, 100, 90]
        ))
        story.append(Spacer(1, 8))

    return story


def _build_kpi_summary(session_data: dict, styles: dict) -> list:
    story = [*_section_header("3. KPI Summary", styles)]
    data = session_data.get("data", {})

    if not data:
        story.append(Paragraph("No data available for KPI calculation.", styles["body"]))
        return story

    for name, result in data.items():
        df: pd.DataFrame = result.get("df")
        if df is None:
            continue

        numeric_df = df.select_dtypes(include="number")
        valid_num = [c for c in numeric_df.columns
                     if not str(c).startswith("Unnamed:")]
        if not valid_num:
            story.append(Paragraph(
                f"No numeric columns in {name}.", styles["body_small"]
            ))
            continue

        story += _subsection_header(f"📊 {name} — Numeric KPIs", styles)
        kpi_rows = []
        for col in valid_num[:15]:
            series = df[col].dropna()
            if series.empty:
                continue
            kpi_rows.append([
                _trunc(col, 24),
                f"{series.mean():.2f}",
                f"{series.median():.2f}",
                f"{series.std():.2f}",
                f"{series.min():.2f}",
                f"{series.max():.2f}",
            ])
        if kpi_rows:
            story.append(_make_table(
                ["Column", "Mean", "Median", "Std Dev", "Min", "Max"],
                kpi_rows,
                col_widths=[120, 64, 64, 64, 58, 58]
            ))
        story.append(Spacer(1, 6))

    return story


def _build_ai_insights(session_data: dict, styles: dict) -> list:
    story = [*_section_header("4. AI Insights", styles)]
    messages = session_data.get("messages", [])

    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    if not assistant_msgs:
        story.append(Paragraph(
            "No AI insights were generated in this session.", styles["body"]
        ))
        return story

    for i, msg in enumerate(assistant_msgs[-10:], 1):
        content = msg.get("content", "")
        if not content:
            continue
        story += _subsection_header(f"Insight #{i}", styles)
        # Wrap long lines
        wrapped = textwrap.fill(content, width=120)
        for line in wrapped.splitlines()[:30]:
            story.append(Paragraph(line or " ", styles["body_small"]))
        story.append(Spacer(1, 4))

    return story


def _build_sql_section(session_data: dict, styles: dict) -> list:
    story = [*_section_header("5. SQL Queries Generated", styles)]
    messages = session_data.get("messages", [])

    sql_msgs = [m for m in messages
                if m.get("role") == "assistant" and m.get("sql_query")]
    if not sql_msgs:
        story.append(Paragraph("No SQL queries were generated.", styles["body"]))
        return story

    for i, msg in enumerate(sql_msgs, 1):
        sql = msg.get("sql_query", "").strip()
        if not sql:
            continue
        story += _subsection_header(f"Query #{i}", styles)
        story += _code_block(sql, styles, max_lines=25)

    return story


def _build_pandas_section(session_data: dict, styles: dict) -> list:
    story = [*_section_header("6. Pandas Code Generated", styles)]
    messages = session_data.get("messages", [])

    pd_msgs = [m for m in messages
               if m.get("role") == "assistant" and m.get("pandas_code")]
    if not pd_msgs:
        story.append(Paragraph("No Pandas code was generated.", styles["body"]))
        return story

    for i, msg in enumerate(pd_msgs, 1):
        code = msg.get("pandas_code", "").strip()
        if not code:
            continue
        story += _subsection_header(f"Snippet #{i}", styles)
        story += _code_block(code, styles, max_lines=25)

    return story


def _build_charts_section(session_data: dict, styles: dict) -> list:
    """
    Auto-generate bar and line charts for each dataset's numeric columns
    and embed them in the PDF.
    """
    story = [*_section_header("7. Charts", styles)]

    try:
        import plotly.express as px
    except ImportError:
        story.append(Paragraph("Plotly not available — charts skipped.", styles["body"]))
        return story

    data = session_data.get("data", {})
    chart_count = 0

    for name, result in data.items():
        df: pd.DataFrame = result.get("df")
        if df is None:
            continue

        numeric_cols = [c for c in df.select_dtypes(include="number").columns
                        if not str(c).startswith("Unnamed:")]
        date_cols = [c for c in df.columns
                     if pd.api.types.is_datetime64_any_dtype(df[c])]

        if not numeric_cols:
            story.append(Paragraph(
                f"No plottable numeric columns in {name}.", styles["body_small"]
            ))
            continue

        story += _subsection_header(f"📂 {name}", styles)

        # 1. Line chart over date if possible
        if date_cols and len(numeric_cols) >= 1:
            try:
                fig = px.line(
                    df.sort_values(date_cols[0]),
                    x=date_cols[0],
                    y=numeric_cols[0],
                    title=f"{numeric_cols[0]} over time",
                    template="plotly_white",
                )
                fig.update_layout(margin=dict(l=30, r=10, t=40, b=30))
                story += _embed_chart(
                    fig,
                    f"Figure {chart_count + 1}: {numeric_cols[0]} trend",
                    styles
                )
                chart_count += 1
            except Exception as e:
                logger.warning(f"Line chart generation failed: {e}")

        # 2. Bar chart of first numeric column (top 15 values by index)
        if len(numeric_cols) >= 1:
            try:
                sample = df[numeric_cols[0]].dropna().head(15).reset_index()
                sample.columns = ["index", numeric_cols[0]]
                fig2 = px.bar(
                    sample,
                    x="index",
                    y=numeric_cols[0],
                    title=f"{numeric_cols[0]} — first 15 records",
                    template="plotly_white",
                )
                fig2.update_layout(margin=dict(l=30, r=10, t=40, b=30))
                story += _embed_chart(
                    fig2,
                    f"Figure {chart_count + 1}: {numeric_cols[0]} distribution (first 15)",
                    styles
                )
                chart_count += 1
            except Exception as e:
                logger.warning(f"Bar chart generation failed: {e}")

        # 3. Scatter if two numeric columns available
        if len(numeric_cols) >= 2:
            try:
                fig3 = px.scatter(
                    df,
                    x=numeric_cols[0],
                    y=numeric_cols[1],
                    title=f"{numeric_cols[0]} vs {numeric_cols[1]}",
                    template="plotly_white",
                    opacity=0.65,
                )
                fig3.update_layout(margin=dict(l=30, r=10, t=40, b=30))
                story += _embed_chart(
                    fig3,
                    f"Figure {chart_count + 1}: {numeric_cols[0]} vs {numeric_cols[1]} scatter",
                    styles
                )
                chart_count += 1
            except Exception as e:
                logger.warning(f"Scatter chart generation failed: {e}")

    if chart_count == 0:
        story.append(Paragraph(
            "No charts could be generated for the current datasets.", styles["body"]
        ))
    return story


def _build_data_quality(session_data: dict, styles: dict) -> list:
    story = [*_section_header("8. Data Quality Report", styles)]
    data = session_data.get("data", {})

    if not data:
        story.append(Paragraph("No datasets loaded.", styles["body"]))
        return story

    for name, result in data.items():
        df: pd.DataFrame = result.get("df")
        if df is None:
            continue

        story += _subsection_header(f"📂 {name}", styles)

        total = len(df)
        dupes = int(df.duplicated().sum())
        missing_total = int(df.isnull().sum().sum())
        missing_pct = f"{missing_total / (total * len(df.columns)) * 100:.1f}%" if total > 0 else "—"

        summary_rows = [
            ["Total Rows", f"{total:,}"],
            ["Duplicate Rows", f"{dupes:,}"],
            ["Total Missing Cells", f"{missing_total:,} ({missing_pct})"],
        ]
        story.append(_make_table(
            ["Metric", "Value"], summary_rows, col_widths=[160, 260]
        ))
        story.append(Spacer(1, 6))

        # Per-column missing breakdown (top 10 worst)
        missing_series = df.isnull().sum()
        missing_series = missing_series[missing_series > 0].sort_values(ascending=False)
        if not missing_series.empty:
            story.append(Paragraph(
                "Columns with missing values (worst first):", styles["body_small"]
            ))
            col_rows = []
            for col, cnt in missing_series.head(10).items():
                pct = f"{cnt / total * 100:.1f}%" if total > 0 else "—"
                col_rows.append([_trunc(str(col), 32), f"{cnt:,}", pct])
            story.append(_make_table(
                ["Column", "Missing Count", "Missing %"],
                col_rows,
                col_widths=[200, 110, 110]
            ))
        else:
            story.append(Paragraph(
                "✓ No missing values detected.", styles["body_small"]
            ))
        story.append(Spacer(1, 8))

    return story


def _build_forecast_section(session_data: dict, styles: dict) -> list:
    story = [*_section_header("9. Forecast Results", styles)]
    forecasts = session_data.get("forecasts", {})

    if not forecasts:
        story.append(Paragraph(
            "No forecast analyses were run in this session. "
            "Navigate to the Forecast tab and run a forecast to include results here.",
            styles["body"]
        ))
        return story

    for dataset_key, fc_result in forecasts.items():
        story += _subsection_header(f"📂 {dataset_key}", styles)

        # Metadata
        meta = fc_result.get("meta", {})
        if meta:
            meta_rows = [[k, _safe_str(v)] for k, v in meta.items()]
            story.append(_make_table(
                ["Parameter", "Value"], meta_rows, col_widths=[160, 260]
            ))
            story.append(Spacer(1, 6))

        # Forecast dataframe preview (first 20 rows)
        fc_df: pd.DataFrame = fc_result.get("forecast_df")
        if fc_df is not None and not fc_df.empty:
            story.append(Paragraph(
                f"Projected values — first {min(20, len(fc_df))} periods:",
                styles["body_small"]
            ))
            headers = [_trunc(str(c), 20) for c in fc_df.columns]
            rows = []
            for _, row in fc_df.head(20).iterrows():
                rows.append([_safe_str(v, 20) for v in row])
            col_w = (W - 36 * mm) / max(len(headers), 1)
            story.append(_make_table(headers, rows,
                                     col_widths=[col_w] * len(headers)))
            story.append(Spacer(1, 6))

        # Embed forecast chart if present
        fc_fig = fc_result.get("fig")
        if fc_fig is None and "historical_df" in fc_result and "forecast_df" in fc_result:
            try:
                import plotly.graph_objects as go
                hist_df = fc_result["historical_df"]
                fore_df = fc_result["forecast_df"]
                t_col = fc_result.get("target_col", "Target")

                fc_fig = go.Figure()

                # Historical Series
                fc_fig.add_trace(
                    go.Scatter(
                        x=hist_df["Date"],
                        y=hist_df["Actual"],
                        name="Historical Actuals",
                        mode="lines",
                        line=dict(color="#1D4ED8", width=2),
                    )
                )

                # Prepend last historical value to future lines for continuous drawing
                future_dates_idx = [hist_df["Date"].iloc[-1]] + list(fore_df["Date"])
                forecast_values = [hist_df["Actual"].iloc[-1]] + list(fore_df["Forecast"])
                lower_bounds = [hist_df["Actual"].iloc[-1]] + list(fore_df["Lower_Bound"])
                upper_bounds = [hist_df["Actual"].iloc[-1]] + list(fore_df["Upper_Bound"])

                # Upper bound boundary (invisible trace used for fill)
                fc_fig.add_trace(
                    go.Scatter(
                        x=future_dates_idx,
                        y=upper_bounds,
                        showlegend=False,
                        mode="lines",
                        line=dict(width=0),
                        hoverinfo="skip",
                    )
                )

                # Shaded confidence interval band
                fc_fig.add_trace(
                    go.Scatter(
                        x=future_dates_idx,
                        y=lower_bounds,
                        name="95% Confidence Interval",
                        fill="tonexty",
                        fillcolor="rgba(16, 185, 129, 0.15)",
                        mode="lines",
                        line=dict(width=0),
                        hoverinfo="skip",
                    )
                )

                # Forecast Trend Line
                fc_fig.add_trace(
                    go.Scatter(
                        x=future_dates_idx,
                        y=forecast_values,
                        name="Forecasted Trend",
                        mode="lines",
                        line=dict(color="#10B981", width=2, dash="dash"),
                    )
                )

                fc_fig.update_layout(
                    title=f"Predictive Forecast Projection — {t_col}",
                    template="plotly_white",
                    margin=dict(l=30, r=10, t=40, b=30),
                )
            except Exception as e:
                logger.warning(f"Could not dynamically reconstruct forecast chart for PDF: {e}", exc_info=True)

        if fc_fig is not None:
            story += _embed_chart(
                fc_fig,
                f"Forecast chart — {dataset_key}",
                styles
            )

        # AI explanation
        explanation = fc_result.get("ai_explanation", "")
        if not explanation:
            # Check for dynamically generated keys starting with explanation_
            explanation_keys = [k for k in fc_result.keys() if k.startswith("explanation_")]
            if explanation_keys:
                explanation = fc_result[explanation_keys[0]]

        if explanation:
            story += _subsection_header("AI Forecast Explanation", styles)
            for line in explanation.splitlines()[:100]:
                story.append(Paragraph(line or " ", styles["body_small"]))

        story.append(Spacer(1, 8))

    return story


def _build_anomaly_section(session_data: dict, styles: dict) -> list:
    story = [*_section_header("10. Anomaly Detection Report", styles)]
    anomalies_store = session_data.get("anomalies", {})

    if not anomalies_store:
        story.append(Paragraph(
            "No anomaly detection was run in this session. "
            "Navigate to the Dashboard tab and run Anomaly Detection to include results here.",
            styles["body"]
        ))
        return story

    for name, cached in anomalies_store.items():
        story += _subsection_header(f"📂 {name}", styles)

        anomalies_df: pd.DataFrame = cached.get("anomalies", pd.DataFrame())
        updated_df: pd.DataFrame = cached.get("updated_df", pd.DataFrame())

        total_rows = len(updated_df) if not updated_df.empty else 0
        anom_count = len(anomalies_df) if not anomalies_df.empty else 0
        pct = f"{anom_count / total_rows * 100:.1f}%" if total_rows > 0 else "—"

        summary_rows = [
            ["Total Records Scanned", f"{total_rows:,}"],
            ["Anomalies Detected", f"{anom_count:,}"],
            ["Anomaly Rate", pct],
        ]
        story.append(_make_table(
            ["Metric", "Value"], summary_rows, col_widths=[160, 260]
        ))
        story.append(Spacer(1, 6))

        if not anomalies_df.empty:
            # Show top 10 anomalies
            story.append(Paragraph(
                "Top anomalous records (up to 10):", styles["body_small"]
            ))
            display_cols = [c for c in anomalies_df.columns
                            if c not in ("Anomaly",) and
                            not str(c).startswith("Unnamed:")][:6]
            headers = [_trunc(str(c), 18) for c in display_cols]
            rows = []
            for _, row in anomalies_df.head(10).iterrows():
                rows.append([_safe_str(row.get(c), 18) for c in display_cols])
            if rows:
                col_w = (W - 36 * mm) / max(len(headers), 1)
                story.append(_make_table(
                    headers, rows,
                    col_widths=[col_w] * len(headers)
                ))
        else:
            story.append(Paragraph(
                "✓ No anomalies were detected in this dataset.", styles["body_small"]
            ))
        story.append(Spacer(1, 8))

    return story


def _build_recommendations(session_data: dict, styles: dict) -> list:
    story = [*_section_header("11. Final Recommendations", styles)]
    data = session_data.get("data", {})
    anomalies_store = session_data.get("anomalies", {})
    forecasts = session_data.get("forecasts", {})

    recs = []

    # Data quality recommendations
    for name, result in data.items():
        df: pd.DataFrame = result.get("df")
        if df is None:
            continue
        missing = df.isnull().sum().sum()
        dupes = df.duplicated().sum()
        if missing > 0:
            recs.append(
                f"<b>Data Quality ({name}):</b> {int(missing):,} missing cells detected. "
                "Consider imputation or removal strategies to improve model reliability."
            )
        if dupes > 0:
            recs.append(
                f"<b>Duplicates ({name}):</b> {int(dupes):,} duplicate rows found. "
                "Review and deduplicate to avoid skewing analytical results."
            )

    # Anomaly recommendations
    for name, cached in anomalies_store.items():
        anom_df = cached.get("anomalies", pd.DataFrame())
        if not anom_df.empty:
            recs.append(
                f"<b>Anomalies ({name}):</b> {len(anom_df):,} outliers identified. "
                "Investigate root causes — these may indicate data-entry errors, "
                "fraud signals, or exceptional business events requiring action."
            )

    # Forecast recommendations
    for dataset_key in forecasts.keys():
        recs.append(
            f"<b>Forecast ({dataset_key}):</b> Review the projected trend and align "
            "resource allocation, budgeting, or inventory planning accordingly."
        )

    # Generic best-practices
    recs += [
        "<b>Automation:</b> Schedule recurring data refreshes to keep insights current.",
        "<b>Model Governance:</b> Re-run anomaly detection after each data ingestion cycle.",
        "<b>Stakeholder Reporting:</b> Distribute this PDF to relevant business units for "
        "cross-functional alignment on data-driven decisions.",
    ]

    if not recs:
        recs.append("Upload datasets and run analyses to generate tailored recommendations.")

    for rec in recs:
        story.append(Paragraph(f"• {rec}", styles["bullet"]))
        story.append(Spacer(1, 3))

    return story


# ── Public API ───────────────────────────────────────────────────────────────
class ReportService:
    """
    Enterprise PDF report generator.

    Usage:
        pdf_bytes = ReportService.generate_pdf(
            session_state=st.session_state,
            company_name="Acme Corp",
            report_title="Monthly Analytics Report"
        )
    """

    @staticmethod
    def generate_pdf(
        session_state,
        company_name: str = "Enterprise Analytics",
        report_title: str = "AI Data Analytics Report",
    ) -> bytes:
        """
        Build and return a PDF document as raw bytes.

        Parameters
        ----------
        session_state : streamlit.runtime.state.SessionStateProxy or dict-like
            The full Streamlit session state (or any dict with the same keys).
        company_name : str
            Company / organisation name shown in the header.
        report_title : str
            Report title shown on the cover page.

        Returns
        -------
        bytes
            Raw PDF bytes ready for download.
        """
        start = time.time()
        logger.info(f"Starting PDF report generation — company='{company_name}'")

        buf = io.BytesIO()
        styles = _build_styles()

        # Build a dict snapshot of session_state so we can pass it around
        sd: dict = {
            "data": dict(getattr(session_state, "data", {}) or {}),
            "messages": list(getattr(session_state, "messages", []) or []),
            "anomalies": dict(getattr(session_state, "anomalies", {}) or {}),
            "forecasts": dict(getattr(session_state, "forecasts", {}) or {}),
        }

        dataset_names = list(sd["data"].keys())

        doc = _BrandedDocTemplate(
            buf,
            company_name=company_name,
            report_title=report_title,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=26 * mm,
            bottomMargin=22 * mm,
            title=report_title,
            author=company_name,
            subject="Enterprise AI Analytics Report",
        )

        story = []

        # ── Cover (no chrome) ───────────────────────────────────────────────
        story += _build_cover(company_name, report_title, styles, dataset_names)
        story.append(NextPageTemplate("content_page"))
        story.append(PageBreak())

        # ── Content sections ────────────────────────────────────────────────
        section_builders = [
            _build_executive_summary,
            _build_dataset_overview,
            _build_kpi_summary,
            _build_ai_insights,
            _build_sql_section,
            _build_pandas_section,
            _build_charts_section,
            _build_data_quality,
            _build_forecast_section,
            _build_anomaly_section,
            _build_recommendations,
        ]

        for builder in section_builders:
            try:
                story += builder(sd, styles) if builder != _build_executive_summary \
                    else builder(sd, styles, company_name)
                story.append(Spacer(1, 8))
            except Exception as e:
                logger.error(
                    f"Report section '{builder.__name__}' failed: {e}",
                    exc_info=True,
                )
                story.append(Paragraph(
                    f"⚠ Section '{builder.__name__}' could not be rendered: {e}",
                    styles["body_small"]
                ))
            story.append(PageBreak())

        # Build the PDF
        doc.build(story)
        pdf_bytes = buf.getvalue()

        elapsed = time.time() - start
        logger.info(
            f"PDF report generated successfully in {elapsed:.2f}s "
            f"({len(pdf_bytes) / 1024:.1f} KB)"
        )
        return pdf_bytes
