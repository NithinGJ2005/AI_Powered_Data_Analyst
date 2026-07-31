import pandas as pd
import numpy as np
from services.ai_service import AIService
import config
from utils import logger


class DashboardService:
    @staticmethod
    def detect_dataset_type(df: pd.DataFrame) -> str:
        """
        Classifies the dataset into Sales, Finance, HR, Marketing, or Generic
        using semantic keyword checks across column names.
        """
        cols = [str(c).lower() for c in df.columns]

        sales_kws = ["sales", "revenue", "price", "amount", "order", "quantity", "profit", "discount", "transaction", "sold", "retail"]
        finance_kws = ["balance", "income", "expense", "cost", "invoice", "cash", "asset", "liability", "tax", "budget", "billing", "payment"]
        hr_kws = ["employee", "salary", "department", "hire", "attrition", "performance", "role", "bonus", "leave", "staff", "recruitment"]
        marketing_kws = ["campaign", "lead", "click", "impression", "spend", "ctr", "roi", "ad", "channel", "conversion", "visit", "clicks"]

        sales_score = sum(1 for col in cols if any(kw in col for kw in sales_kws))
        finance_score = sum(1 for col in cols if any(kw in col for kw in finance_kws))
        hr_score = sum(1 for col in cols if any(kw in col for kw in hr_kws))
        marketing_score = sum(1 for col in cols if any(kw in col for kw in marketing_kws))

        scores = {
            "Sales": sales_score,
            "Finance": finance_score,
            "HR": hr_score,
            "Marketing": marketing_score
        }

        best_type = max(scores, key=scores.get)
        if scores[best_type] > 0:
            logger.info(f"Dataset classified semantically as: {best_type} (score={scores[best_type]})")
            return best_type
        
        logger.info("Dataset did not match domain keywords. Falling back to: Generic")
        return "Generic"

    @classmethod
    def generate_kpis(cls, df: pd.DataFrame, dataset_type: str) -> list:
        """
        Computes 3-4 domain-specific KPIs with names, formatted values, and deltas/notes.
        """
        kpis = []
        cols_lower = {str(col).lower(): col for col in df.columns}

        def _find_column(kws):
            for kw in kws:
                for cl, orig in cols_lower.items():
                    if kw in cl:
                        return orig
            return None

        if dataset_type == "Sales":
            # 1. Total Revenue
            rev_col = _find_column(["revenue", "sales", "amount"])
            if rev_col and pd.api.types.is_numeric_dtype(df[rev_col]):
                total_rev = df[rev_col].sum()
                kpis.append({"label": "💵 Total Sales Revenue", "value": f"${total_rev:,.2f}", "raw": total_rev})
            
            # 2. Total Units Sold
            qty_col = _find_column(["quantity", "units", "sold"])
            if qty_col and pd.api.types.is_numeric_dtype(df[qty_col]):
                total_qty = df[qty_col].sum()
                kpis.append({"label": "📦 Total Units Sold", "value": f"{total_qty:,.0f}", "raw": total_qty})

            # 3. Average Sales
            if rev_col and pd.api.types.is_numeric_dtype(df[rev_col]):
                avg_rev = df[rev_col].mean()
                kpis.append({"label": "📊 Average Transaction Value", "value": f"${avg_rev:,.2f}", "raw": avg_rev})

            # 4. Top Category/Segment
            cat_col = _find_column(["category", "segment", "product"])
            if cat_col and rev_col and pd.api.types.is_numeric_dtype(df[rev_col]):
                top_cat = df.groupby(cat_col)[rev_col].sum().idxmax()
                kpis.append({"label": "🏆 Top Segment", "value": str(top_cat), "raw": top_cat})

        elif dataset_type == "Finance":
            # 1. Total Income
            inc_col = _find_column(["income", "revenue", "balance"])
            if inc_col and pd.api.types.is_numeric_dtype(df[inc_col]):
                total_inc = df[inc_col].sum()
                kpis.append({"label": "💰 Total Ledger Balance", "value": f"${total_inc:,.2f}", "raw": total_inc})

            # 2. Total Costs / Expenses
            exp_col = _find_column(["expense", "cost", "billing"])
            if exp_col and pd.api.types.is_numeric_dtype(df[exp_col]):
                total_exp = df[exp_col].sum()
                kpis.append({"label": "💸 Total Expenses", "value": f"${total_exp:,.2f}", "raw": total_exp})

            # 3. Profit Margin Estimate
            if inc_col and exp_col and pd.api.types.is_numeric_dtype(df[inc_col]) and pd.api.types.is_numeric_dtype(df[exp_col]):
                profit = df[inc_col].sum() - df[exp_col].sum()
                margin = (profit / df[inc_col].sum() * 100) if df[inc_col].sum() > 0 else 0.0
                kpis.append({"label": "📈 Net Margin", "value": f"{margin:.1f}%", "raw": margin})

        elif dataset_type == "HR":
            # 1. Total Headcount
            emp_col = _find_column(["employee", "staff", "id"])
            headcount = df[emp_col].nunique() if emp_col else len(df)
            kpis.append({"label": "👥 Employee Headcount", "value": f"{headcount:,}", "raw": headcount})

            # 2. Average Salary
            sal_col = _find_column(["salary", "pay", "compensation"])
            if sal_col and pd.api.types.is_numeric_dtype(df[sal_col]):
                avg_sal = df[sal_col].mean()
                kpis.append({"label": "💳 Average compensation", "value": f"${avg_sal:,.2f}", "raw": avg_sal})

            # 3. Attrition count
            att_col = _find_column(["attrition", "leave", "status"])
            if att_col:
                attrition_count = df[df[att_col].astype(str).str.lower().str.strip().isin(["yes", "true", "left"])].shape[0]
                kpis.append({"label": "🚪 Attrition Count", "value": f"{attrition_count:,}", "raw": attrition_count})

        elif dataset_type == "Marketing":
            # 1. Total Spend / Budget
            spd_col = _find_column(["spend", "cost", "budget"])
            if spd_col and pd.api.types.is_numeric_dtype(df[spd_col]):
                total_spd = df[spd_col].sum()
                kpis.append({"label": "📢 Marketing Spend", "value": f"${total_spd:,.2f}", "raw": total_spd})

            # 2. Total Impressions/Leads
            imp_col = _find_column(["impression", "clicks", "leads", "lead"])
            if imp_col and pd.api.types.is_numeric_dtype(df[imp_col]):
                total_imp = df[imp_col].sum()
                kpis.append({"label": "🎯 Total Engagement Metrics", "value": f"{total_imp:,.0f}", "raw": total_imp})

            # 3. Average Click-Through-Rate
            ctr_col = _find_column(["ctr", "conversion"])
            if ctr_col and pd.api.types.is_numeric_dtype(df[ctr_col]):
                avg_ctr = df[ctr_col].mean()
                kpis.append({"label": "⚡ Average CTR/Conversions", "value": f"{avg_ctr:.2f}%" if avg_ctr <= 100.0 else f"{avg_ctr:.2f}", "raw": avg_ctr})

        # Fallback KPI configuration for Generic / missing metrics
        if not kpis:
            # 1. Total Rows
            kpis.append({"label": "📊 Total Records Count", "value": f"{len(df):,}", "raw": len(df)})
            # 2. Total Columns
            kpis.append({"label": "🗂️ Total Column Count", "value": f"{len(df.columns)}", "raw": len(df.columns)})
            # 3. Missing Value Percent
            missing = df.isnull().sum().sum()
            total_cells = len(df) * len(df.columns)
            missing_pct = (missing / total_cells * 100) if total_cells > 0 else 0.0
            kpis.append({"label": "❌ Missing Cells Rate", "value": f"{missing_pct:.1f}%", "raw": missing_pct})

        return kpis

    @classmethod
    def recommend_charts(cls, df: pd.DataFrame, dataset_type: str) -> list:
        """
        Recommends 2 visualization configurations matching the dataset profile rules.
        """
        recs = []
        cols_lower = {str(col).lower(): col for col in df.columns}

        def _find_column(kws):
            for kw in kws:
                for cl, orig in cols_lower.items():
                    if kw in cl:
                        return orig
            return None

        # Helper columns
        date_col = _find_column(["date", "time", "year"])
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [c for c in numeric_cols if not str(c).startswith("Unnamed:")]
        categorical_cols = df.select_dtypes(include=[object, "category"]).columns.tolist()

        if dataset_type == "Sales":
            rev_col = _find_column(["revenue", "sales", "amount"])
            cat_col = _find_column(["category", "segment", "product"])
            
            if date_col and rev_col:
                recs.append({"title": "Sales Revenue Over Time", "type": "Line", "x": date_col, "y": rev_col})
            if cat_col and rev_col:
                recs.append({"title": "Sales Revenue by Segment", "type": "Bar", "x": cat_col, "y": rev_col})

        elif dataset_type == "Finance":
            inc_col = _find_column(["income", "balance", "revenue"])
            exp_col = _find_column(["expense", "cost", "billing"])
            
            if inc_col and exp_col:
                recs.append({"title": "Income vs Expenses Comparison", "type": "Scatter", "x": inc_col, "y": exp_col})
            if date_col and inc_col:
                recs.append({"title": "Income Ledger Timeline", "type": "Line", "x": date_col, "y": inc_col})

        elif dataset_type == "HR":
            sal_col = _find_column(["salary", "pay"])
            dept_col = _find_column(["department", "role"])
            
            if dept_col and sal_col:
                recs.append({"title": "Average Compensation by Department", "type": "Bar", "x": dept_col, "y": sal_col})
            if sal_col:
                recs.append({"title": "Salary Distribution Profile", "type": "Box", "x": sal_col, "y": sal_col})

        elif dataset_type == "Marketing":
            spd_col = _find_column(["spend", "cost"])
            ctr_col = _find_column(["ctr", "conversion"])
            camp_col = _find_column(["campaign", "channel"])
            
            if spd_col and ctr_col:
                recs.append({"title": "Marketing Spend vs conversions Effectiveness", "type": "Scatter", "x": spd_col, "y": ctr_col})
            if camp_col and spd_col:
                recs.append({"title": "Ad Spend by Campaign Channel", "type": "Bar", "x": camp_col, "y": spd_col})

        # Generic recommended chart strategies
        if len(recs) < 2:
            if date_col and numeric_cols:
                recs.append({"title": "Numeric Trend Over Time", "type": "Line", "x": date_col, "y": numeric_cols[0]})
            if categorical_cols and numeric_cols:
                recs.append({"title": "Metric Distribution by Category", "type": "Bar", "x": categorical_cols[0], "y": numeric_cols[0]})
            elif len(numeric_cols) >= 2:
                recs.append({"title": "Numerical Correlation", "type": "Scatter", "x": numeric_cols[0], "y": numeric_cols[1]})

        # Double check sizing safety
        return recs[:2]

    @classmethod
    def get_dashboard_summary(cls, dataset_type: str, kpis: list) -> str:
        """
        Submits the metrics of this adaptive dashboard to Gemini for writing an executive explanation.
        """
        try:
            

            kpi_desc = "\n".join([f"- {k['label']}: {k['value']}" for k in kpis])

            prompt = f"""
You are an expert Business Intelligence Executive summarizing metrics for high-level management.

Analyze the following custom dashboard metadata.

**Dashboard Type Activated:** {dataset_type} Analytics Panel
**Generated Key Performance Indicators (KPIs):**
{kpi_desc}

Please write a professional, high-level summary report containing:
1. **Executive Overview**: Summarize what these numbers indicate about the overall health of this business division (Sales, Finance, HR, or Marketing).
2. **Key Insights**: Highlight two critical points, trends, or observations from the KPIs.
3. **Strategic Recommendations**: 2 actionable operational ideas derived from these figures.

Provide your report in clean, professional markdown format using bold headers and concise bullet points.
Keep it strictly under 250 words.
"""
            logger.info("Requesting dashboard executive analysis summary from Gemini...")
            response_text = AIService.generate_content(prompt)
            return response_text
        except Exception as e:
            logger.error(f"Failed to fetch dashboard executive summary from Gemini: {e}", exc_info=True)
            return f"⚠️ Summary Generation Unavailable: {e}"
