import pandas as pd
from services.ai_service import AIService
import config
from services.forecast_service import ForecastService
from services.quality_service import QualityService
from utils import logger


class RecommendationService:
    @classmethod
    def run_analysis(cls, df: pd.DataFrame) -> dict:
        """
        Runs heuristics to identify top customers, top products, declining products,
        seasonality spikes, anomalies count, and data quality concerns.
        """
        logger.info(f"Running recommendation heuristics on dataset of size {df.shape}...")

        cols_lower = {str(col).lower(): col for col in df.columns}

        def _find_column(kws):
            for kw in kws:
                for cl, orig in cols_lower.items():
                    if kw in cl:
                        return orig
            return None

        # Resolve columns
        cust_col = _find_column(["customer", "client", "buyer", "user", "customer_id"])
        prod_col = _find_column(["product", "item", "sku", "category", "product_id"])
        rev_col = _find_column(["revenue", "sales", "amount", "price"])
        date_col = _find_column(["date", "time", "timestamp"])

        valid_numeric = rev_col and pd.api.types.is_numeric_dtype(df[rev_col])

        # 1. Top Customers
        top_customers = []
        if cust_col and valid_numeric:
            top_cust_df = df.groupby(cust_col)[rev_col].sum().sort_values(ascending=False).head(5)
            for k, v in top_cust_df.items():
                top_customers.append({"name": str(k), "sales": float(v)})

        # 2. Top Products
        top_products = []
        if prod_col and valid_numeric:
            top_prod_df = df.groupby(prod_col)[rev_col].sum().sort_values(ascending=False).head(5)
            for k, v in top_prod_df.items():
                top_products.append({"name": str(k), "sales": float(v)})

        # 3. Declining Products (Heuristic comparing first half vs second half of timeline)
        declining_products = []
        if prod_col and date_col and valid_numeric:
            try:
                df_temp = df[[date_col, prod_col, rev_col]].dropna().copy()
                df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors="coerce")
                df_temp = df_temp.dropna(subset=[date_col]).sort_values(by=date_col)

                half = len(df_temp) // 2
                p1_df = df_temp.iloc[:half]
                p2_df = df_temp.iloc[half:]

                p1_sales = p1_df.groupby(prod_col)[rev_col].sum()
                p2_sales = p2_df.groupby(prod_col)[rev_col].sum()

                # Align indices
                p1_sales, p2_sales = p1_sales.align(p2_sales, fill_value=0.0)
                changes = ((p2_sales - p1_sales) / p1_sales.replace(0, 1)) * 100.0
                declines = changes[changes < -5.0].sort_values()  # drop steeper than -5%

                for prod, pct in declines.head(5).items():
                    declining_products.append(
                        {
                            "name": str(prod),
                            "change_pct": float(pct),
                            "p1_sales": float(p1_sales[prod]),
                            "p2_sales": float(p2_sales[prod]),
                        }
                    )
            except Exception as de:
                logger.warning(f"Failed to calculate declining products: {de}")

        # 4. Seasonality Spikes
        season_peaks = []
        if date_col and valid_numeric:
            try:
                df_temp = df[[date_col, rev_col]].dropna().copy()
                df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors="coerce")
                df_temp = df_temp.dropna(subset=[date_col])

                df_temp["Month"] = df_temp[date_col].dt.month_name()
                month_avg = df_temp.groupby("Month")[rev_col].mean().sort_values(ascending=False)
                for m, val in month_avg.head(3).items():
                    season_peaks.append({"period": str(m), "avg_sales": float(val)})
            except Exception as se:
                logger.warning(f"Failed to calculate seasonality: {se}")

        # 5. Forecast Alerts
        forecast_alerts = []
        if date_col and valid_numeric:
            try:
                fc = ForecastService.generate_forecast(
                    df, date_col=date_col, target_col=rev_col, horizon_str="Next 30 days"
                )
                if fc.get("error") is None:
                    summary = fc["forecast_summary"]
                    growth = summary["change_pct"]
                    if growth < -5.0:
                        forecast_alerts.append(f"Projected {abs(growth):.1f}% decline in sales for next 30 days.")
                    elif growth > 15.0:
                        forecast_alerts.append(f"Projected {growth:.1f}% growth spike in upcoming month.")
            except Exception as fe:
                logger.warning(f"Failed to generate forecast alerts: {fe}")

        # 6. Anomalies & Quality Flags
        anomalies_count = 0
        try:
            from services.anomaly_service import AnomalyService

            _, anom_df = AnomalyService.detect_anomalies(df)
            anomalies_count = len(anom_df)
        except Exception:
            pass

        quality = QualityService.run_audit(df)

        metrics = {
            "top_customers": top_customers,
            "top_products": top_products,
            "declining_products": declining_products,
            "seasonality": season_peaks,
            "forecast_alerts": forecast_alerts,
            "anomalies_count": anomalies_count,
            "quality_warnings": quality["warnings"][:5],
            "quality_score": quality["score"],
        }

        # 7. Call Gemini for Recommendations Report
        recs_text = cls._generate_ai_recommendations(metrics)

        return {"metrics": metrics, "recommendations_text": recs_text}

    @classmethod
    def _generate_ai_recommendations(cls, metrics: dict) -> str:
        """
        Sends extracted heuristics variables to Gemini to get tailored business actions.
        """
        try:
            

            # Format parameters
            cust_str = "\n".join([f"- {c['name']}: ${c['sales']:,.2f}" for c in metrics["top_customers"]])
            prod_str = "\n".join([f"- {p['name']}: ${p['sales']:,.2f}" for p in metrics["top_products"]])
            dec_str = "\n".join(
                [
                    f"- {d['name']}: {d['change_pct']:.1f}% decline (from ${d['p1_sales']:,.2f} to ${d['p2_sales']:,.2f})"
                    for d in metrics["declining_products"]
                ]
            )
            seas_str = "\n".join([f"- Peak: {s['period']} (Average Sales: ${s['avg_sales']:,.2f})" for s in metrics["seasonality"]])
            alert_str = "\n".join([f"- Alert: {a}" for a in metrics["forecast_alerts"]])
            qual_str = "\n".join([f"- Warning: {q}" for q in metrics["quality_warnings"]])

            prompt = f"""
You are the Chief Business Intelligence Director and Strategic Growth Advisor.

Review the following structured heuristics extracted from the active dataset:

**Top Customers:**
{cust_str or "No customer metrics available."}

**Top Products:**
{prod_str or "No product metrics available."}

**Declining Products:**
{dec_str or "No declining products metrics available."}

**Seasonality Peaks:**
{seas_str or "No seasonal time-series available."}

**Upcoming Forecast Alerts:**
{alert_str or "No immediate trend alerts flagged."}

**Anomalies & Outliers:**
- Flagged Outliers Count: {metrics['anomalies_count']}

**Data Quality Audit:**
- Overall Quality Score: {metrics['quality_score']}/100
{qual_str or "No data quality warnings identified."}

Please write a comprehensive, professional Business Recommendations Report addressing:
1. **Revenue Opportunities**: How can we maximize value from top customers, cross-sell top products, or capture market share?
2. **Declining Products Mitigation**: Actionable mitigation suggestions for products showing sharp declines.
3. **Seasonality Strategy**: Operational plans (inventory, staffing, campaigns) to align with peak seasonality months.
4. **Anomalies & Data Quality Remediation**: What steps are needed to clean outliers or fix the identified data nulls/duplicates?
5. **Business Recommendations**: 3 high-impact, direct business actions stakeholders should execute immediately.
6. **Suggested Follow-Up Analyses**: 2 specific analytical queries or model checks they should run next.

Format your report using clear bold markdown headers and bullet points.
Keep it executive-level, concise, and highly strategic.
"""
            logger.info("Requesting Gemini AI recommendations summary...")
            response_text = AIService.generate_content(prompt)
            return response_text
        except Exception as e:
            logger.error(f"Failed to fetch AI recommendations: {e}", exc_info=True)
            return f"⚠️ Recommendation Summary Generation Failed: {e}"
