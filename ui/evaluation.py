import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from services.evaluation_service import EvaluationService


def render_evaluation_tab():
    st.subheader("📊 AI Interaction Evaluation Dashboard")
    st.markdown(
        "<p style='color: #94A3B8; font-size: 0.95rem; margin-top: -0.5rem; margin-bottom: 1.5rem;'>"
        "Monitor Google Gemini AI engine performance metrics, response times, model confidence, "
        "SQL execution success rates, and user feedback logs."
        "</p>",
        unsafe_allow_html=True,
    )

    evals = EvaluationService.get_evaluations()
    metrics = EvaluationService.get_metrics()

    # 1. Summary Metric Cards
    m_cols = st.columns(5)
    m_cols[0].metric("Total Queries", f"{metrics['total_queries']}")
    m_cols[1].metric("Avg Latency", f"{metrics['avg_response_time']:.2f}s")
    m_cols[2].metric("SQL Success Rate", f"{metrics['sql_success_rate']:.1f}%")
    m_cols[3].metric("Avg Confidence", f"{metrics['avg_confidence']:.1f}%")
    m_cols[4].metric("Failed Queries", f"{metrics['failed_queries']}")

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    if not evals:
        # Empty state placeholder
        with st.container(border=True):
            st.markdown(
                """
                <div style="text-align: center; padding: 3rem 1rem; color: #64748B;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
                    <h4 style="color: white; margin-bottom: 0.5rem;">Evaluation Logs Empty</h4>
                    <p style="font-size: 0.9rem;">Submit natural language queries in the Chat tab to start tracking performance metrics.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    # Convert to DataFrame for charts/tables
    df_evals = pd.DataFrame(evals)

    # 2. Performance Plotly Chart
    st.markdown("### 📈 Response Time & Confidence Over Time")
    fig = go.Figure()

    # Response Time Scatter/Line
    fig.add_trace(
        go.Scatter(
            x=df_evals["timestamp"],
            y=df_evals["execution_time"],
            name="Latency (seconds)",
            mode="lines+markers",
            line=dict(color="#3B82F6", width=2),
            marker=dict(size=6),
            yaxis="y1",
        )
    )

    # Confidence Line
    fig.add_trace(
        go.Scatter(
            x=df_evals["timestamp"],
            y=df_evals["confidence"] * 100,
            name="Model Confidence (%)",
            mode="lines+markers",
            line=dict(color="#10B981", width=2, dash="dash"),
            marker=dict(size=6),
            yaxis="y2",
        )
    )

    # Styling Dual-Y Axis Layout
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1E293B",
        plot_bgcolor="#1E293B",
        font=dict(color="#F8FAFC", family="Inter, -apple-system, sans-serif"),
        margin=dict(l=20, r=20, t=35, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
        yaxis=dict(
            title=dict(
                text="Latency (seconds)",
                font=dict(color="#3B82F6")
            ),
            tickfont=dict(color="#3B82F6"),
            gridcolor="#334155",
        ),
        yaxis2=dict(
            title=dict(
                text="Confidence (%)",
                font=dict(color="#10B981")
            ),
            tickfont=dict(color="#10B981"),
            anchor="x",
            overlaying="y",
            side="right",
        ),
    )


    fig.update_xaxes(
        gridcolor="#334155",
        linecolor="#334155",
        zerolinecolor="#334155",
        title_font=dict(color="#CBD5E1"),
        tickfont=dict(color="#94A3B8"),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # 3. Detailed Data Table
    st.markdown("### 📋 Interaction Diagnostic Log")

    # Format dataframe for display
    display_df = df_evals[
        [
            "timestamp",
            "prompt",
            "generated_sql",
            "confidence",
            "execution_time",
            "success",
            "failure_reason",
            "user_feedback",
        ]
    ].copy()

    # Format numeric column outputs
    display_df["confidence"] = display_df["confidence"].apply(lambda x: f"{x * 100:.1f}%" if x <= 1.0 else f"{x:.1f}%")
    display_df["execution_time"] = display_df["execution_time"].apply(lambda x: f"{x:.2f}s")
    display_df["success"] = display_df["success"].apply(lambda x: "✅ Success" if x else "❌ Failure")
    display_df["user_feedback"] = display_df["user_feedback"].apply(lambda x: f"Feedback: {x}" if x else "Pending")

    st.dataframe(display_df, use_container_width=True)

    # Export & Reset Options
    act_col1, act_col2 = st.columns([1, 1])
    with act_col1:
        # Add CSV Export
        st.download_button(
            label="📥 Export Evaluations Log (CSV)",
            data=df_evals.to_csv(index=False).encode("utf-8"),
            file_name="ai_interactions_evaluation.csv",
            mime="text/csv",
            key="dl_evals_csv",
            use_container_width=True,
        )
    with act_col2:
        # Reset button
        if st.button("🗑️ Reset Evaluations Logs", use_container_width=True):
            EvaluationService.clear_evaluations()
            st.toast("Evaluation logs successfully reset.")
            st.rerun()
