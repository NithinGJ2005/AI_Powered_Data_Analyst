import streamlit as st


def render_homepage() -> list:
    """
    Renders the premium enterprise SaaS landing page layout on the main screen
    when no datasets are loaded.

    Returns:
        list: Any files uploaded via the hero uploader (may be empty).
    """
    # 1. Hero Section — compact, no buttons
    st.markdown("""
    <div class="hero-container">
        <div class="hero-glow"></div>
        <div class="hero-badge">✨ AI Powered Analytics</div>
        <h1 class="hero-title">Enterprise AI Data Analyst</h1>
        <p class="hero-subtitle">Transform raw CSV files into actionable business insights using Gemini AI, SQL, Pandas, and Machine Learning.</p>
    </div>
    """, unsafe_allow_html=True)

    # 2. Centered native Streamlit uploader inside a styled wrapper column
    _, col_c, _ = st.columns([1, 6, 1])
    with col_c:
        hero_files = st.file_uploader(
            "Upload CSV Files",
            type=["csv"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="hero_uploader",
        )

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # 3. Core Features Highlights Grid
    st.markdown("""
    <div class="features-grid">
        <div class="feature-card">
            <div class="feature-icon">💬</div>
            <h3>Conversational Analysis</h3>
            <p>Ask analytical questions in natural language and receive dynamic summaries and Pandas code explanations.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🗄️</div>
            <h3>Sandboxed SQL Engine</h3>
            <p>Automatically generate and execute SQL queries directly against your datasets using an in-memory DuckDB connection.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🔮</div>
            <h3>Predictive Forecasting</h3>
            <p>Auto-detect date and target columns then project future values with 95% confidence intervals and Gemini trend explanations.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🚨</div>
            <h3>Anomaly Detection</h3>
            <p>Detect statistical outliers instantly via Isolation Forest, Z-score, and IQR ensemble with AI-generated business impact.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">📄</div>
            <h3>PDF Report Export</h3>
            <p>Generate branded A4 PDF reports with embedded KPIs, charts, anomalies, forecasts, and AI recommendations.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">📡</div>
            <h3>Observability Dashboard</h3>
            <p>Monitor every AI request, SQL execution, and forecast run with live Plotly charts and a searchable log explorer.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    return hero_files if hero_files else []
