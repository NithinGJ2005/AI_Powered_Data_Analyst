import streamlit as st
import pandas as pd
import plotly.express as px
from modules.charts import generate_chart
from services.anomaly_service import AnomalyService

def render_dashboard_tab():
    """
    Renders the interactive dashboard containing overview stats, KPI columns,
    interactive visualization cards, suitability alerts, and anomaly detection profiles.
    """
    st.subheader("📈 Interactive Dashboard")

    selected_file = st.selectbox(
        "Select Dataset",
        list(st.session_state.data.keys()),
        key="dashboard_select"
    )

    df = st.session_state.data[selected_file]["df"]

    # --- Section 0: Adaptive Domain Dashboard Profile ---
    from services.dashboard_service import DashboardService

    detected_type = DashboardService.detect_dataset_type(df)

    st.markdown(f"### 🎯 Domain Analytics Profile: **{detected_type}** Dashboard")
    st.markdown(
        f"<p style='color: #60A5FA; font-size: 0.92rem; margin-top: -0.5rem; margin-bottom: 1.5rem;'>"
        f"Custom adaptive dashboard generated for {detected_type} dataset columns configuration."
        f"</p>",
        unsafe_allow_html=True,
    )

    # Render adaptive KPIs
    kpis = DashboardService.generate_kpis(df, detected_type)
    kpi_cols_adaptive = st.columns(len(kpis))
    for i, kpi in enumerate(kpis):
        kpi_cols_adaptive[i].metric(kpi["label"], kpi["value"])

    # Export KPIs button
    kpi_rows = []
    for kpi in kpis:
        kpi_rows.append({"KPI Metric": kpi["label"], "Calculated Value": kpi["value"]})
    kpi_df = pd.DataFrame(kpi_rows)

    st.download_button(
        label="📥 Export Dashboard KPIs (CSV)",
        data=kpi_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{detected_type.lower()}_dashboard_kpis.csv",
        mime="text/csv",
        key=f"dl_kpi_{selected_file}",
        use_container_width=True,
    )

    # Render AI dashboard summary (with caching to avoid 429 quota exceed on session refreshes)
    summary_cache_key = f"dash_summary_{selected_file}_{detected_type}"
    if summary_cache_key not in st.session_state:
        st.session_state[summary_cache_key] = DashboardService.get_dashboard_summary(detected_type, kpis)

    with st.expander("🧠 Gemini AI Executive Dashboard Summary", expanded=True):
        st.markdown(st.session_state[summary_cache_key])

    # Recommended Visualizations
    st.markdown("#### 💡 Recommended Visualizations")
    recs = DashboardService.recommend_charts(df, detected_type)
    if recs:
        rec_cols = st.columns(len(recs))
        for i, rec in enumerate(recs):
            with rec_cols[i]:
                st.markdown(f"**{rec['title']}** ({rec['type']} Chart)")
                try:
                    rec_fig = generate_chart(df, chart_type=rec["type"], x=rec["x"], y=rec["y"])
                    if rec_fig:
                        st.plotly_chart(rec_fig, use_container_width=True, key=f"rec_chart_{selected_file}_{i}")
                    else:
                        st.caption("Could not generate chart.")
                except Exception as e:
                    st.caption(f"Recommendation alert: {e}")

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # Filter out Unnamed columns
    valid_columns = [col for col in df.columns if not str(col).startswith("Unnamed:")]
    if not valid_columns:
        valid_columns = df.columns.tolist()

    # Section 1: Dataset Overview
    st.markdown("### 📊 Dataset Overview")
    st.markdown("<p style='color: #94A3B8; font-size: 0.95rem; margin-top: -0.5rem; margin-bottom: 1.5rem;'>Summary statistics and key metrics for the active dataset.</p>", unsafe_allow_html=True)

    # KPI Metrics Cards
    kpi_cols_dashboard = st.columns(4)
    kpi_cols_dashboard[0].metric("📊 Selected Rows", f"{len(df):,}")
    kpi_cols_dashboard[1].metric("🔢 Numeric Columns", f"{len(df.select_dtypes(include='number').columns)}")
    kpi_cols_dashboard[2].metric("🔤 Categorical Columns", f"{len(df.select_dtypes(exclude='number').columns)}")
    
    cached_result = st.session_state.anomalies.get(selected_file)
    if cached_result:
        num_anomalies = len(cached_result["anomalies"])
        kpi_cols_dashboard[3].metric("🚨 Anomalies Detected", f"{num_anomalies:,}")
    else:
        kpi_cols_dashboard[3].metric("🚨 Anomalies Detected", "Not Run")

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # Section 2: Interactive Visualizations
    st.markdown("### 📈 Interactive Visualizations")
    st.markdown("<p style='color: #94A3B8; font-size: 0.95rem; margin-top: -0.5rem; margin-bottom: 1.5rem;'>Explore trends and relationships across your dataset.</p>", unsafe_allow_html=True)

    col_controls = st.columns(3)
    with col_controls[0]:
        chart_type = st.selectbox(
            "Chart Type",
            ["Bar", "Line", "Scatter", "Histogram", "Pie", "Box"],
            key="chart_type_select"
        )
    with col_controls[1]:
        x_axis = st.selectbox(
            "X-Axis",
            valid_columns,
            key="x_axis_select"
        )
    with col_controls[2]:
        y_axis = st.selectbox(
            "Y-Axis",
            valid_columns,
            index=min(1, len(valid_columns) - 1),
            key="y_axis_select"
        )

    # Visualization Card Wrapper
    with st.container(border=True):
        try:
            chart_fig = generate_chart(df, chart_type, x_axis, y_axis)
            if chart_fig:
                st.plotly_chart(chart_fig, use_container_width=True)
            else:
                st.markdown("""
                <div style="text-align: center; padding: 3rem 1rem; color: #64748B;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
                    <h4 style="color: white; margin-bottom: 0.5rem;">No Chart Rendered</h4>
                    <p style="font-size: 0.9rem;">Select valid columns above to generate a visualization.</p>
                </div>
                """, unsafe_allow_html=True)
        except ValueError as e:
            st.markdown(f"""
            <div style="text-align: center; padding: 3rem 1rem; color: #E11D48;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
                <h4 style="color: #F87171; margin-bottom: 0.5rem;">Unsuitable Visualization</h4>
                <p style="font-size: 0.9rem; color: #FCA5A5;">{str(e)}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.markdown("### 🚨 Anomaly Detection Profile")
    st.markdown("<p style='color: #94A3B8; font-size: 0.95rem; margin-top: -0.5rem; margin-bottom: 1.5rem;'>Automatically scan and isolate statistical outliers inside your data fields.</p>", unsafe_allow_html=True)

    anomaly_method = st.selectbox(
        "Anomaly Detection Method",
        ["Isolation Forest (Default)", "Z-score (> 3.0)", "IQR (1.5x)", "Compare Anomaly Models (Dashboard)"],
        key="anomaly_method_select"
    )

    # Resolve caching key dynamically based on whether it is a comparison or single run
    is_compare = anomaly_method == "Compare Anomaly Models (Dashboard)"
    cache_key = f"multi_{selected_file}" if is_compare else selected_file
    cached_result = st.session_state.anomalies.get(cache_key)

    # Trigger run if button is clicked
    if st.button("🔍 Run Anomaly Detection", use_container_width=True, key="run_anomaly_btn"):
        with st.spinner("Executing outlier detection models..."):
            if is_compare:
                res = AnomalyService.detect_anomalies_multi(df)
                st.session_state.anomalies[cache_key] = res
            else:
                method_name = "Isolation Forest"
                if "Z-score" in anomaly_method:
                    method_name = "Z-score"
                elif "IQR" in anomaly_method:
                    method_name = "IQR"
                
                updated_df, anomalies = AnomalyService.detect_anomalies(df, method=method_name)
                st.session_state.anomalies[cache_key] = {
                    "updated_df": updated_df,
                    "anomalies": anomalies,
                    "method_used": method_name
                }
            st.rerun()

    # Display cached anomaly results if they exist, or show empty state helper
    if cached_result:
        if is_compare:
            # 1. Consensus Comparison dashboard
            st.markdown("#### 📊 Models Consensus Comparison")
            
            comp_cols = st.columns(3)
            comp_cols[0].metric("Agreement Rate", f"{cached_result['agreement_pct']:.1f}%")
            comp_cols[1].metric("Severity Score", f"{cached_result['severity_score']:.1f}/100")
            comp_cols[2].metric("Estimation Confidence", f"{cached_result['confidence']:.1f}%")
            
            # Bar chart comparing counts
            fig_compare = px.bar(
                x=["Isolation Forest", "Z-score", "IQR"],
                y=[cached_result["iforest_count"], cached_result["z_count"], cached_result["iqr_count"]],
                labels={"x": "Algorithm", "y": "Outliers Flagged"},
                title="Outlier Count Comparison by Model Type",
                color=["Isolation Forest", "Z-score", "IQR"],
                color_discrete_sequence=["#3B82F6", "#6366F1", "#10B981"]
            )
            fig_compare.update_layout(template="plotly_dark", paper_bgcolor="#1E293B", plot_bgcolor="#1E293B")
            st.plotly_chart(fig_compare, use_container_width=True)
            
            # consensus AI summary
            ai_cache_key = f"anomaly_ai_{selected_file}"
            if ai_cache_key not in st.session_state:
                st.session_state[ai_cache_key] = AnomalyService.get_anomaly_explanation(cached_result)
                
            with st.expander("🧠 Gemini AI Anomaly Interpretation Summary", expanded=True):
                st.markdown(st.session_state[ai_cache_key])
                
            # Consensus table
            consensus_df = cached_result["consensus_df"]
            st.markdown(f"#### 📋 Consensus Outliers Data Table (Matches ≥ 2 models: {len(consensus_df)} rows)")
            if not consensus_df.empty:
                st.dataframe(consensus_df, use_container_width=True)
                st.download_button(
                    label="📥 Download Consensus Outliers (CSV)",
                    data=consensus_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"consensus_outliers_{selected_file}.csv",
                    mime="text/csv",
                    key=f"dl_consensus_{selected_file}",
                    use_container_width=True
                )
            else:
                st.info("No consensus outliers flagged by 2 or more algorithms.")
                
        else:
            # 2. Backward compatible single model view
            updated_df = cached_result["updated_df"]
            anomalies = cached_result["anomalies"]
            method_used = cached_result.get("method_used", "Isolation Forest")

            st.metric(
                f"Anomalies Found ({method_used})",
                len(anomalies)
            )

            if not anomalies.empty:
                st.dataframe(
                    anomalies,
                    use_container_width=True
                )

                st.download_button(
                    label=f"📥 Download Anomaly Report ({method_used}) (CSV)",
                    data=anomalies.to_csv(index=False).encode("utf-8"),
                    file_name=f"anomaly_{method_used.lower()}_report.csv",
                    mime="text/csv",
                    key=f"dl_anomaly_{selected_file}",
                    use_container_width=True
                )

                # Filter out Unnamed columns for scatter plot axes
                numeric_cols = [col for col in df.select_dtypes(include="number").columns if not str(col).startswith("Unnamed:")]
                if not numeric_cols:
                    numeric_cols = df.select_dtypes(include="number").columns.tolist()

                if len(numeric_cols) >= 2:
                    with st.container(border=True):
                        fig = px.scatter(
                            updated_df,
                            x=numeric_cols[0],
                            y=numeric_cols[1],
                            color="Anomaly",
                            size="AnomalyScore",
                            title="Outliers Highlighted in Feature Space"
                        )
                        fig.update_layout(template="plotly_dark", paper_bgcolor="#1E293B", plot_bgcolor="#1E293B")
                        st.plotly_chart(
                            fig,
                            use_container_width=True
                        )
            else:
                with st.container(border=True):
                    st.markdown("""
                    <div style="text-align: center; padding: 3rem 1rem; color: #10B981;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">✅</div>
                        <h4 style="color: white; margin-bottom: 0.5rem;">No Outliers Found</h4>
                        <p style="font-size: 0.9rem; color: #CBD5E1;">Statistical checks passed successfully. Zero anomalies detected in the dataset.</p>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        with st.container(border=True):
            st.markdown("""
            <div style="text-align: center; padding: 3rem 1rem; color: #64748B;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🔍</div>
                <h4 style="color: white; margin-bottom: 0.5rem;">Anomaly Detection Not Run Yet</h4>
                <p style="font-size: 0.9rem; margin-bottom: 1.5rem;">Select anomaly algorithm and run detection on this dataset.</p>
            </div>
            """, unsafe_allow_html=True)

    # --- Section 3: AI Recommendations Engine ---
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    from ui.recommendations import render_recommendations_section
    render_recommendations_section(df, selected_file)


def render_data_overview_tab():
    """
    Renders standard dataframe previews and missing value summaries.
    """
    st.subheader("👁️ Dataset Preview")

    selected_file = st.selectbox(
        "Dataset",
        list(st.session_state.data.keys()),
        key="preview"
    )

    result = st.session_state.data[selected_file]

    st.dataframe(
        result["df"].head(10),
        use_container_width=True
    )

    st.markdown("### 📐 Statistical Summary")

    st.dataframe(
        pd.DataFrame(result["stats"]),
        use_container_width=True
    )

    st.markdown("### ❌ Missing Values Report")

    st.dataframe(
        pd.DataFrame(
            result["missing_values"].items(),
            columns=["Column", "Missing"]
        ),
        use_container_width=True
    )
