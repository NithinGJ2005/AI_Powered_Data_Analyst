import streamlit as st
import pandas as pd
from services.recommendation_service import RecommendationService


def render_recommendations_section(df: pd.DataFrame, selected_file: str):
    """
    Renders the AI Recommendations Engine section inside the Streamlit dashboard.
    """
    st.markdown("### 🧠 AI Recommendations Engine")
    st.markdown(
        "<p style='color: #94A3B8; font-size: 0.95rem; margin-top: -0.5rem; margin-bottom: 1.5rem;'>"
        "Run deep semantic heuristic audits to identify growth segments, product declines, seasonality, "
        "and generate strategic business recommendations using Gemini."
        "</p>",
        unsafe_allow_html=True,
    )

    cached_rec = st.session_state.recommendations.get(selected_file)

    if st.button("🧠 Run AI Recommendation Engine", use_container_width=True, key="run_recs_btn"):
        with st.spinner("Extracting business indicators and consulting Gemini AI..."):
            res = RecommendationService.run_analysis(df)
            st.session_state.recommendations[selected_file] = res
            cached_rec = res
            st.rerun()

    if cached_rec:
        metrics = cached_rec["metrics"]
        text_report = cached_rec["recommendations_text"]

        # Display Heuristics Summary Cards/Tables
        st.markdown("#### 📊 Derived Analytics Indicators")

        col1, col2 = st.columns(2)
        with col1:
            if metrics["top_customers"]:
                st.markdown("**Top Customers**")
                df_cust = pd.DataFrame(metrics["top_customers"])
                df_cust.columns = ["Customer Name", "Total Purchase Value"]
                st.dataframe(df_cust, use_container_width=True, hide_index=True)
            else:
                st.info("No customer metrics could be identified.")

            if metrics["declining_products"]:
                st.markdown("**Declining Products Alert**")
                df_dec = pd.DataFrame(metrics["declining_products"])
                # Extract and format columns
                df_dec_disp = df_dec[["name", "change_pct"]].copy()
                df_dec_disp.columns = ["Product SKU", "Sales Drop %"]
                df_dec_disp["Sales Drop %"] = df_dec_disp["Sales Drop %"].apply(lambda x: f"{x:.1f}%")
                st.dataframe(df_dec_disp, use_container_width=True, hide_index=True)
            else:
                st.info("No declining products identified.")

        with col2:
            if metrics["top_products"]:
                st.markdown("**Top Products**")
                df_prod = pd.DataFrame(metrics["top_products"])
                df_prod.columns = ["Product Name", "Total Sales Value"]
                st.dataframe(df_prod, use_container_width=True, hide_index=True)
            else:
                st.info("No product metrics could be identified.")

            if metrics["seasonality"]:
                st.markdown("**Seasonality Spikes**")
                df_seas = pd.DataFrame(metrics["seasonality"])
                df_seas.columns = ["Peak Period", "Average Sales Value"]
                st.dataframe(df_seas, use_container_width=True, hide_index=True)
            else:
                st.info("No seasonality indicators found.")

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

        # Renders the Gemini AI Recommendations report
        st.markdown("#### 🧠 Gemini Strategic Recommendations Report")
        with st.container(border=True):
            st.markdown(text_report)

        # Export Report to CSV
        report_data = [
            {"Indicator": "Dataset Quality Score", "Detail": f"{metrics['quality_score']}/100"},
            {"Indicator": "Flagged Anomalies Count", "Detail": str(metrics["anomalies_count"])},
            {"Indicator": "Top Customer", "Detail": metrics["top_customers"][0]["name"] if metrics["top_customers"] else "N/A"},
            {"Indicator": "Top Product", "Detail": metrics["top_products"][0]["name"] if metrics["top_products"] else "N/A"},
            {"Indicator": "Full Strategy Text", "Detail": text_report},
        ]
        df_export = pd.DataFrame(report_data)
        st.download_button(
            label="📥 Export AI Recommendations Report (CSV)",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name=f"ai_recommendations_{selected_file}.csv",
            mime="text/csv",
            key=f"dl_recs_{selected_file}",
            use_container_width=True,
        )

    else:
        with st.container(border=True):
            st.markdown(
                """
                <div style="text-align: center; padding: 3rem 1rem; color: #64748B;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">🧠</div>
                    <h4 style="color: white; margin-bottom: 0.5rem;">Recommendations Engine Ready</h4>
                    <p style="font-size: 0.9rem;">Run the engine above to extract revenue opportunities, declining products, and custom recommendations.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
