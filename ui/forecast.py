import streamlit as st
import plotly.graph_objects as go
from services.forecast_service import ForecastService


def render_forecast_tab():
    st.subheader("🔮 Predictive Forecasting")
    st.markdown(
        "<p style='color: #94A3B8; font-size: 0.95rem; margin-top: -0.5rem; margin-bottom: 1.5rem;'>"
        "Detect datetime patterns and target columns automatically to construct time-series "
        "projections with robust fallback models and Gemini business explanations."
        "</p>",
        unsafe_allow_html=True,
    )

    if not st.session_state.data:
        st.info("📂 Please upload a dataset in the sidebar to begin forecasting.")
        return

    # Select Dataset
    selected_file = st.selectbox(
        "Select Dataset", list(st.session_state.data.keys()), key="forecast_dataset_select"
    )

    df = st.session_state.data[selected_file]["df"]

    # Detect Columns
    datetime_cols = ForecastService.detect_datetime_columns(df)
    if not datetime_cols:
        st.warning(
            "⚠️ No valid date/time columns could be detected in this dataset. "
            "Predictive forecasting requires at least one temporal field."
        )
        return

    numeric_cols = ForecastService.detect_numeric_columns(df, datetime_cols)
    if not numeric_cols:
        st.warning(
            "⚠️ No valid numeric target columns could be detected in this dataset. "
            "Forecasting requires a numeric feature to plot and predict."
        )
        return

    # User selections
    col_controls = st.columns(3)
    with col_controls[0]:
        date_col = st.selectbox("Datetime Column", datetime_cols, key="forecast_date_select")
    with col_controls[1]:
        target_col = st.selectbox("Target Metric Column", numeric_cols, key="forecast_target_select")
    with col_controls[2]:
        horizon = st.selectbox(
            "Forecast Horizon", ["Next 30 days", "Next 6 months", "Next 12 months"], key="forecast_horizon_select"
        )

    # Advanced options
    with st.expander("⚙️ Advanced Forecasting Options", expanded=False):
        opt_cols = st.columns(2)
        with opt_cols[0]:
            agg_func = st.selectbox(
                "Aggregation Method",
                ["sum", "mean"],
                format_func=lambda x: "Sum Total (e.g. Sales, Revenue)" if x == "sum" else "Average / Mean (e.g. Price, Temperature)",
                key="forecast_agg_select",
            )

    # Triggers forecasting
    if st.button("🔮 Run Predictive Forecasting", use_container_width=True):
        with st.spinner("Aggregating time-series data and executing forecast models..."):
            result = ForecastService.generate_forecast(
                df=df, date_col=date_col, target_col=target_col, horizon_str=horizon, agg_func=agg_func
            )

            if result.get("error"):
                st.error(f"Forecasting Execution Failed: {result['error']}")
            else:
                # Save to session state
                if "forecasts" not in st.session_state:
                    st.session_state.forecasts = {}
                st.session_state.forecasts[selected_file] = {
                    "historical_df": result["historical_df"],
                    "forecast_df": result["forecast_df"],
                    "freq_label": result["freq_label"],
                    "method_used": result["method_used"],
                    "historical_summary": result["historical_summary"],
                    "forecast_summary": result["forecast_summary"],
                    "date_col": date_col,
                    "target_col": target_col,
                    "horizon": horizon,
                    "agg_func": agg_func,
                }

    # Render results if they exist in state cache
    cached = st.session_state.get("forecasts", {}).get(selected_file)
    if cached:
        # Check if the cache is for the current visual settings
        if (
            cached["date_col"] == date_col
            and cached["target_col"] == target_col
            and cached["horizon"] == horizon
            and cached["agg_func"] == agg_func
        ):
            _render_results(selected_file, cached)
        else:
            st.info("💡 Settings have changed. Click 'Run Predictive Forecasting' to update results.")
    else:
        # Render empty state placeholder card
        with st.container(border=True):
            st.markdown(
                """
                <div style="text-align: center; padding: 3rem 1rem; color: #64748B;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">🔮</div>
                    <h4 style="color: white; margin-bottom: 0.5rem;">Forecasting Engine Ready</h4>
                    <p style="font-size: 0.9rem;">Select date and target metric columns above, then run predictive analysis.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_results(selected_file: str, cached: dict):
    hist_df = cached["historical_df"]
    fore_df = cached["forecast_df"]
    freq_label = cached["freq_label"]
    method_used = cached["method_used"]
    hist_sum = cached["historical_summary"]
    fore_sum = cached["forecast_summary"]
    target_col = cached["target_col"]
    date_col = cached["date_col"]

    st.success(f"Forecast successfully computed using **{method_used}** aggregated at a **{freq_label}** frequency.")

    # 1. Statistics Cards
    st.markdown("### 📊 Forecast Summary Statistics")
    stats_cols = st.columns(4)
    stats_cols[0].metric("Historical Avg", f"{hist_sum['mean']:.2f}")
    stats_cols[1].metric("Forecast Avg", f"{fore_sum['mean']:.2f}")
    stats_cols[2].metric("Target End Value", f"{fore_sum['end_value']:.2f}")

    growth = fore_sum["change_pct"]
    stats_cols[3].metric(
        "Projected Trend", f"{growth:+.2f}%", delta=f"{growth:.2f}%" if growth != 0 else None
    )

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # 2. Plotly Interactive Chart
    st.markdown("### 📈 Time Series & Trend Projections")

    fig = go.Figure()

    # Historical Series
    fig.add_trace(
        go.Scatter(
            x=hist_df["Date"],
            y=hist_df["Actual"],
            name="Historical Actuals",
            mode="lines+markers",
            line=dict(color="#3B82F6", width=2.5),
            marker=dict(size=4),
        )
    )

    # Prepend last historical value to future lines for continuous drawing
    future_dates_idx = [hist_df["Date"].iloc[-1]] + list(fore_df["Date"])
    forecast_values = [hist_df["Actual"].iloc[-1]] + list(fore_df["Forecast"])
    lower_bounds = [hist_df["Actual"].iloc[-1]] + list(fore_df["Lower_Bound"])
    upper_bounds = [hist_df["Actual"].iloc[-1]] + list(fore_df["Upper_Bound"])

    # Upper bound boundary (invisible trace used for fill)
    fig.add_trace(
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
    fig.add_trace(
        go.Scatter(
            x=future_dates_idx,
            y=lower_bounds,
            name="95% Confidence Interval",
            fill="tonexty",
            fillcolor="rgba(16, 185, 129, 0.12)",
            mode="lines",
            line=dict(width=0),
            hoverinfo="skip",
        )
    )

    # Forecast Trend Line
    fig.add_trace(
        go.Scatter(
            x=future_dates_idx,
            y=forecast_values,
            name="Forecasted Trend",
            mode="lines",
            line=dict(color="#10B981", width=2.5, dash="dash"),
        )
    )

    # Premium Dark theme styling
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1E293B",
        plot_bgcolor="#1E293B",
        font=dict(color="#F8FAFC", family="Inter, -apple-system, sans-serif"),
        margin=dict(l=20, r=20, t=35, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
    )

    fig.update_xaxes(
        gridcolor="#334155",
        linecolor="#334155",
        zerolinecolor="#334155",
        title_font=dict(color="#CBD5E1"),
        tickfont=dict(color="#94A3B8"),
    )
    fig.update_yaxes(
        gridcolor="#334155",
        linecolor="#334155",
        zerolinecolor="#334155",
        title_font=dict(color="#CBD5E1"),
        tickfont=dict(color="#94A3B8"),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Download Button
    st.download_button(
        label="📥 Download Forecast Projections (CSV)",
        data=fore_df.to_csv(index=False).encode("utf-8"),
        file_name=f"forecast_projections_{target_col}.csv",
        mime="text/csv",
        key=f"forecast_download_{selected_file}",
        use_container_width=True,
    )

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # 3. AI Insights Panel
    st.markdown("### 🧠 Gemini AI Forecast Analysis")

    explanation_key = f"explanation_{target_col}_{date_col}_{cached['horizon']}_{cached['agg_func']}"
    if explanation_key not in cached:
        with st.spinner("Consulting Gemini AI to interpret forecast trends and business implications..."):
            explanation = ForecastService.get_forecast_explanation(
                target_col=target_col,
                date_col=date_col,
                freq_label=freq_label,
                method_used=method_used,
                historical_summary=hist_sum,
                forecast_summary=fore_sum,
                forecast_df=fore_df,
            )
            cached[explanation_key] = explanation

    st.markdown(cached[explanation_key])
