import streamlit as st
import config
from utils import logger
from modules.loader import load_csv
from ui.sidebar import render_sidebar
from ui.homepage import render_homepage
from ui.chat import render_chat_tab
from ui.dashboard import render_dashboard_tab, render_data_overview_tab
from ui.report import render_report_tab
from ui.forecast import render_forecast_tab
from ui.evaluation import render_evaluation_tab
from ui.monitoring import render_monitoring_tab


def initialize_session_state():
    """
    Initializes default session variables once at startup.
    Ensures safe accesses without index errors.
    """
    for key, value in config.SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _process_uploads(files: list, error_target) -> None:
    """
    Runs uploaded file objects through the centralized load_csv pipeline.
    Errors are surfaced to `error_target` (sidebar or main area).

    Args:
        files: List of Streamlit UploadedFile objects.
        error_target: A Streamlit container that has an `.error()` method.
    """
    for file in files:
        if file.name not in st.session_state.data:
            result = load_csv(file)
            if result.get("error"):
                error_target.error(result["error"])
            else:
                st.session_state.data[file.name] = result
                logger.info(f"Dataset '{file.name}' loaded via upload. "
                            f"Shape: {result['shape']}")


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=config.PAGE_TITLE,
    layout=config.LAYOUT,
    page_icon=config.PAGE_ICON,
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
try:
    with open(config.CSS_PATH, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    logger.warning(f"Global CSS file not found at path: {config.CSS_PATH}")

# ── Session state ──────────────────────────────────────────────────────────────
initialize_session_state()

# ── Page title ─────────────────────────────────────────────────────────────────
st.title(f"{config.PAGE_ICON} {config.PAGE_TITLE}")


# ── Sidebar (always visible; returns additional uploads) ───────────────────────
sidebar_files = render_sidebar()
if sidebar_files:
    _process_uploads(sidebar_files, st.sidebar)

# ── Application Router ─────────────────────────────────────────────────────────
if st.session_state.data:
    # ── 1. Global KPI summary (above tabs) ────────────────────────────────────
    num_datasets  = len(st.session_state.data)
    total_rows    = sum(len(res["df"]) for res in st.session_state.data.values())
    total_cols    = sum(len(res["df"].columns) for res in st.session_state.data.values())
    total_missing = sum(res["df"].isnull().sum().sum() for res in st.session_state.data.values())

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("📂 Datasets Loaded", f"{num_datasets}")
    kpi_cols[1].metric("📊 Total Rows",       f"{total_rows:,}")
    kpi_cols[2].metric("📋 Total Columns",    f"{total_cols:,}")
    kpi_cols[3].metric("❌ Missing Values",   f"{total_missing:,}")
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # ── 2. Main Tab View Router ────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "💬 Chat", "📈 Dashboard", "📊 Data Overview",
        "🔮 Forecast", "📄 Report", "📊 Evaluation", "📡 Monitoring",
    ])

    with tab1:
        render_chat_tab()
    with tab2:
        render_dashboard_tab()
    with tab3:
        render_data_overview_tab()
    with tab4:
        render_forecast_tab()
    with tab5:
        render_report_tab()
    with tab6:
        render_evaluation_tab()
    with tab7:
        render_monitoring_tab()

else:
    # ── Homepage with embedded upload card ─────────────────────────────────────
    hero_files = render_homepage()
    if hero_files:
        _process_uploads(hero_files, st)
        # Trigger immediate rerun so the dashboard appears after upload
        st.rerun()