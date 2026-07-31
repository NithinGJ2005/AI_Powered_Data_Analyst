import streamlit as st


def render_sidebar():
    """
    Renders the sidebar navigation, brand header, pre-upload guide panel,
    post-upload dataset summary cards, and the add-more-files uploader.

    Returns:
        list: Uploaded file objects from the sidebar uploader (only active after first upload).
    """
    # ── Brand header ─────────────────────────────────────────
    st.sidebar.markdown("""
    <div style="text-align:center;padding:1.1rem 0 0.6rem;">
        <div style="font-size:2rem;margin-bottom:0.3rem;">📊</div>
        <h2 style="color:white;margin:0;font-size:1.25rem;font-weight:700;letter-spacing:-0.02em;">DataInsight</h2>
        <p style="color:#64748B;font-size:0.78rem;margin:0.25rem 0 0;">Enterprise AI Analytics</p>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")

    # ── Pre-upload state: guide panel ────────────────────────
    if not st.session_state.data:
        st.sidebar.markdown("""
        <div style="
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 12px;
            padding: 1.2rem 1rem;
            margin-bottom: 1rem;
        ">
            <div style="color:#93C5FD;font-size:0.8rem;font-weight:700;letter-spacing:0.06em;
                        text-transform:uppercase;margin-bottom:0.9rem;">
                🚀 Get Started
            </div>
            <div style="display:flex;flex-direction:column;gap:0.65rem;">
                <div style="display:flex;align-items:flex-start;gap:0.6rem;">
                    <span style="color:#3B82F6;font-size:0.85rem;margin-top:1px;">①</span>
                    <span style="color:#CBD5E1;font-size:0.82rem;line-height:1.4;">Upload a <strong style="color:#F8FAFC;">CSV dataset</strong> using the main panel</span>
                </div>
                <div style="display:flex;align-items:flex-start;gap:0.6rem;">
                    <span style="color:#3B82F6;font-size:0.85rem;margin-top:1px;">②</span>
                    <span style="color:#CBD5E1;font-size:0.82rem;line-height:1.4;">Explore the <strong style="color:#F8FAFC;">AI-generated analysis</strong> dashboard</span>
                </div>
                <div style="display:flex;align-items:flex-start;gap:0.6rem;">
                    <span style="color:#3B82F6;font-size:0.85rem;margin-top:1px;">③</span>
                    <span style="color:#CBD5E1;font-size:0.82rem;line-height:1.4;">Chat with your data, run <strong style="color:#F8FAFC;">SQL queries</strong>, detect anomalies</span>
                </div>
                <div style="display:flex;align-items:flex-start;gap:0.6rem;">
                    <span style="color:#3B82F6;font-size:0.85rem;margin-top:1px;">④</span>
                    <span style="color:#CBD5E1;font-size:0.82rem;line-height:1.4;">Export a branded <strong style="color:#F8FAFC;">PDF report</strong> in one click</span>
                </div>
            </div>
        </div>

        <div style="margin-bottom:0.75rem;">
            <div style="color:#94A3B8;font-size:0.75rem;font-weight:600;letter-spacing:0.05em;
                        text-transform:uppercase;margin-bottom:0.65rem;">
                ✨ Capabilities
            </div>
            <div style="display:flex;flex-direction:column;gap:0.45rem;">
                <div style="display:flex;align-items:center;gap:0.55rem;padding:0.5rem 0.7rem;
                            background:rgba(17,24,39,0.5);border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
                    <span style="font-size:1rem;">🤖</span>
                    <span style="color:#CBD5E1;font-size:0.8rem;">Gemini AI Insights</span>
                </div>
                <div style="display:flex;align-items:center;gap:0.55rem;padding:0.5rem 0.7rem;
                            background:rgba(17,24,39,0.5);border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
                    <span style="font-size:1rem;">🗄️</span>
                    <span style="color:#CBD5E1;font-size:0.8rem;">SQL Query Engine</span>
                </div>
                <div style="display:flex;align-items:center;gap:0.55rem;padding:0.5rem 0.7rem;
                            background:rgba(17,24,39,0.5);border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
                    <span style="font-size:1rem;">🔮</span>
                    <span style="color:#CBD5E1;font-size:0.8rem;">Predictive Forecasting</span>
                </div>
                <div style="display:flex;align-items:center;gap:0.55rem;padding:0.5rem 0.7rem;
                            background:rgba(17,24,39,0.5);border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
                    <span style="font-size:1rem;">🚨</span>
                    <span style="color:#CBD5E1;font-size:0.8rem;">Anomaly Detection</span>
                </div>
                <div style="display:flex;align-items:center;gap:0.55rem;padding:0.5rem 0.7rem;
                            background:rgba(17,24,39,0.5);border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
                    <span style="font-size:1rem;">📄</span>
                    <span style="color:#CBD5E1;font-size:0.8rem;">PDF Report Export</span>
                </div>
                <div style="display:flex;align-items:center;gap:0.55rem;padding:0.5rem 0.7rem;
                            background:rgba(17,24,39,0.5);border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
                    <span style="font-size:1rem;">📡</span>
                    <span style="color:#CBD5E1;font-size:0.8rem;">Observability Dashboard</span>
                </div>
            </div>
        </div>

        <div style="
            background: linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(99,102,241,0.06) 100%);
            border: 1px solid rgba(59,130,246,0.2);
            border-radius:10px;
            padding:0.7rem 0.9rem;
        ">
            <div style="color:#93C5FD;font-size:0.77rem;font-weight:600;">📋 Supported Formats</div>
            <div style="color:#94A3B8;font-size:0.75rem;margin-top:0.3rem;line-height:1.5;">
                CSV files · Up to 200 MB per file · Multiple files supported simultaneously
            </div>
        </div>
        """, unsafe_allow_html=True)

        return []

    # ── Post-upload state: success banner + dataset cards with remove buttons ──
    st.sidebar.markdown("""
    <div class="success-banner">
        <div class="success-banner-title">✓ Dataset uploaded successfully</div>
    </div>
    """, unsafe_allow_html=True)

    # CSS to style the remove button inline with the card
    st.sidebar.markdown("""
    <style>
    /* Make the remove button small, red, compact, and float to the right */
    [data-testid="stSidebar"] .dataset-remove-btn button {
        background: rgba(239, 68, 68, 0.12) !important;
        border: 1px solid rgba(239, 68, 68, 0.35) !important;
        color: #F87171 !important;
        border-radius: 6px !important;
        padding: 0.15rem 0.5rem !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        width: auto !important;
        min-height: unset !important;
        height: 28px !important;
        line-height: 1 !important;
        cursor: pointer !important;
        transition: background 0.2s ease, border-color 0.2s ease !important;
    }
    [data-testid="stSidebar"] .dataset-remove-btn button:hover {
        background: rgba(239, 68, 68, 0.25) !important;
        border-color: rgba(239, 68, 68, 0.6) !important;
    }
    /* Align card name and button on the same row */
    [data-testid="stSidebar"] .dataset-card-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

    datasets_to_remove = []

    for name, res in list(st.session_state.data.items()):
        col_card, col_btn = st.sidebar.columns([5, 1])

        with col_card:
            st.markdown(f"""
            <div class="dataset-stats-card" style="margin-bottom:0;">
                <div class="dataset-stats-name" style="margin-bottom:0.4rem;">📂 {name}</div>
                <div class="dataset-stats-grid">
                    <div><strong>Rows:</strong> {len(res["df"]):,}</div>
                    <div><strong>Cols:</strong> {len(res["df"].columns):,}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_btn:
            st.markdown("<div class='dataset-remove-btn'>", unsafe_allow_html=True)
            if st.button("✕", key=f"remove_{name}", help=f"Remove {name}"):
                datasets_to_remove.append(name)
            st.markdown("</div>", unsafe_allow_html=True)

    # Apply removals and rerun
    if datasets_to_remove:
        for name in datasets_to_remove:
            del st.session_state.data[name]
        st.rerun()

    st.sidebar.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)

    # Sidebar uploader for adding more datasets after first load
    uploaded_files = st.sidebar.file_uploader(
        "Upload CSV Files",
        type=["csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="sidebar_uploader"
    )
    return uploaded_files

