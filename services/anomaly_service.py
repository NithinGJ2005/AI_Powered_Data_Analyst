import time
import pandas as pd
import numpy as np
import streamlit as st
from sklearn.ensemble import IsolationForest
from services.ai_service import AIService
import config
from utils import logger


class AnomalyService:
    @staticmethod
    @st.cache_data
    def detect_anomalies(df: pd.DataFrame, method: str = "Isolation Forest"):
        """
        Runs anomaly detection using the selected algorithm (Isolation Forest, Z-score, or IQR).
        Returns a copy of the dataframe with 'Anomaly', 'AnomalyScore', and 'Explanation' columns,
        along with a dataframe containing only the anomalies.
        """
        start_time = time.time()
        logger.info(f"Triggering anomaly detection ({method}) on DataFrame of size {df.shape}...")

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [c for c in numeric_cols if not str(c).startswith("Unnamed:")]

        if not numeric_cols:
            logger.warning("No numeric columns found to calculate anomalies on.")
            updated_df = df.copy()
            updated_df["Anomaly"] = False
            updated_df["AnomalyScore"] = 0.0
            updated_df["Explanation"] = "No numeric fields available."
            return updated_df, pd.DataFrame()

        df_clean = df[numeric_cols].fillna(df[numeric_cols].median())
        updated_df = df.copy()

        try:
            if method == "Z-score":
                # Z-score outlier detection (Z > 3.0)
                means = df_clean.mean()
                stds = df_clean.std().replace(0, 1)
                z_scores = (df_clean - means) / stds
                abs_z = np.abs(z_scores)

                preds = abs_z.max(axis=1) > 3.0
                updated_df["Anomaly"] = preds.values
                updated_df["AnomalyScore"] = abs_z.max(axis=1).values / 3.0  # normalize score

                explanations = []
                for idx, row in df_clean.iterrows():
                    if preds.iloc[idx]:
                        max_feature = abs_z.iloc[idx].idxmax()
                        val = row[max_feature]
                        z_val = z_scores.iloc[idx][max_feature]
                        dir_str = "above" if z_val > 0 else "below"
                        explanations.append(
                            f"Z-score outlier in '{max_feature}' ({val:.2f} is {abs(z_val):.2f} stds {dir_str} mean)"
                        )
                    else:
                        explanations.append("Normal data point.")
                updated_df["Explanation"] = explanations

            elif method == "IQR":
                # IQR outlier detection
                q1 = df_clean.quantile(0.25)
                q3 = df_clean.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr

                outliers_low = df_clean < lower
                outliers_high = df_clean > upper
                preds = (outliers_low | outliers_high).any(axis=1)

                updated_df["Anomaly"] = preds.values
                # Anomaly score based on max deviation from bounds
                deviations = []
                for col in numeric_cols:
                    range_col = iqr[col] if iqr[col] > 0 else 1.0
                    dev_low = (lower[col] - df_clean[col]) / range_col
                    dev_high = (df_clean[col] - upper[col]) / range_col
                    deviations.append(np.maximum(dev_low, dev_high))
                max_dev = pd.DataFrame(deviations).T.max(axis=1)

                updated_df["AnomalyScore"] = np.maximum(0, max_dev.values)

                explanations = []
                for idx, row in df_clean.iterrows():
                    if preds.iloc[idx]:
                        # Find col that breached boundary most
                        breaches = {}
                        for col in numeric_cols:
                            if row[col] < lower[col]:
                                breaches[col] = lower[col] - row[col]
                            elif row[col] > upper[col]:
                                breaches[col] = row[col] - upper[col]
                        max_breached_col = max(breaches, key=breaches.get) if breaches else numeric_cols[0]
                        val = row[max_breached_col]
                        boundary = lower[max_breached_col] if val < lower[max_breached_col] else upper[max_breached_col]
                        bound_type = "lower" if val < lower[max_breached_col] else "upper"
                        explanations.append(
                            f"IQR outlier in '{max_breached_col}' ({val:.2f} breached {bound_type} bound {boundary:.2f})"
                        )
                    else:
                        explanations.append("Normal data point.")
                updated_df["Explanation"] = explanations

            else:
                # Default: Isolation Forest
                model = IsolationForest(contamination=0.05, random_state=42)
                fit_preds = model.fit_predict(df_clean)
                scores = model.decision_function(df_clean)

                updated_df["Anomaly"] = fit_preds == -1
                updated_df["AnomalyScore"] = np.abs(scores)

                means = df_clean.mean()
                stds = df_clean.std().replace(0, 1)

                explanations = []
                for idx, row in df_clean.iterrows():
                    if fit_preds[idx] == -1:
                        z_scores = (row - means) / stds
                        max_dev_feature = z_scores.abs().idxmax()
                        val = row[max_dev_feature]
                        mean_val = means[max_dev_feature]
                        direction = "above" if val > mean_val else "below"
                        explanations.append(
                            f"Outlier in '{max_dev_feature}' ({val:.2f} is {direction} mean {mean_val:.2f})"
                        )
                    else:
                        explanations.append("Normal data point.")
                updated_df["Explanation"] = explanations

            anomalies_df = updated_df[updated_df["Anomaly"]].copy()
            logger.info(f"Anomaly detection complete in {time.time() - start_time:.3f}s. Outliers detected: {len(anomalies_df)}")
            return updated_df, anomalies_df

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}", exc_info=True)
            updated_df = df.copy()
            updated_df["Anomaly"] = False
            updated_df["AnomalyScore"] = 0.0
            updated_df["Explanation"] = f"Calculation failed: {e}"
            return updated_df, pd.DataFrame()

    @classmethod
    @st.cache_data
    def detect_anomalies_multi(cls, df: pd.DataFrame) -> dict:
        """
        Runs Isolation Forest, Z-score, and IQR algorithms, returning masks, consensus levels,
        and agreement/severity metrics.
        """
        logger.info(f"Running multi-method anomaly comparison on DataFrame of size {df.shape}...")

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [c for c in numeric_cols if not str(c).startswith("Unnamed:")]

        if not numeric_cols:
            return {
                "iforest_count": 0,
                "z_count": 0,
                "iqr_count": 0,
                "agreement_pct": 100.0,
                "severity_score": 0.0,
                "confidence": 100.0,
                "consensus_df": pd.DataFrame(),
            }

        df_clean = df[numeric_cols].fillna(df[numeric_cols].median())

        # 1. Isolation Forest
        model = IsolationForest(contamination=0.05, random_state=42)
        iforest_mask = model.fit_predict(df_clean) == -1

        # 2. Z-score
        z_scores = np.abs((df_clean - df_clean.mean()) / df_clean.std().replace(0, 1))
        z_mask = z_scores.max(axis=1) > 3.0

        # 3. IQR
        q1 = df_clean.quantile(0.25)
        q3 = df_clean.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        iqr_mask = ((df_clean < lower) | (df_clean > upper)).any(axis=1)

        # Convert to arrays
        iforest_mask = iforest_mask.astype(bool)
        z_mask = z_mask.values.astype(bool)
        iqr_mask = iqr_mask.values.astype(bool)

        # 4. Consensus Metrics
        agreement_mask = (iforest_mask == z_mask) & (z_mask == iqr_mask)
        agreement_pct = (agreement_mask.sum() / len(df)) * 100.0

        consensus_score = iforest_mask.astype(int) + z_mask.astype(int) + iqr_mask.astype(int)
        flagged_mask = consensus_score > 0
        severity_score = (consensus_score[flagged_mask].mean() / 3.0 * 100.0) if flagged_mask.any() else 0.0
        confidence = agreement_pct

        # Construct consensus table (flagged by at least 2 methods)
        consensus_idx = consensus_score >= 2
        consensus_df = df.copy()
        consensus_df["Flagged_By_Count"] = consensus_score
        consensus_df["Isolation_Forest"] = iforest_mask
        consensus_df["Z_score"] = z_mask
        consensus_df["IQR"] = iqr_mask
        consensus_df = consensus_df[consensus_idx].sort_values(by="Flagged_By_Count", ascending=False)

        return {
            "iforest_count": int(iforest_mask.sum()),
            "z_count": int(z_mask.sum()),
            "iqr_count": int(iqr_mask.sum()),
            "agreement_pct": float(agreement_pct),
            "severity_score": float(severity_score),
            "confidence": float(confidence),
            "consensus_df": consensus_df,
        }

    @classmethod
    def get_anomaly_explanation(cls, stats: dict) -> str:
        """
        Requests Gemini to evaluate consensus rates, method counts, and summarize business impact.
        """
        try:
            

            prompt = f"""
You are an expert Risk Analyst and Data Scientist.

Analyze the following anomaly detection comparison report:
- Outliers by Isolation Forest (Default): {stats['iforest_count']}
- Outliers by Z-score (threshold > 3): {stats['z_count']}
- Outliers by IQR (1.5x deviation): {stats['iqr_count']}
- Methods Agreement rate: {stats['agreement_pct']:.1f}%
- Consensus Severity Score: {stats['severity_score']:.1f}/100
- Estimation Confidence: {stats['confidence']:.1f}%

Please write a professional, high-level business intelligence evaluation containing:
1. **AI Explanation**: Interpret the mathematical consensus. Why might one method identify more outliers than another on this dataset?
2. **Business Impact**: How do these specific anomalous records impact key operations, financials, or analysis accuracy?
3. **Recommended Actions**: Actionable operational suggestions to clean, investigate, or segregate these outliers.

Provide your report in clean, professional markdown format using bold headers and concise bullet points.
Strictly keep it under 300 words.
"""
            logger.info("Requesting anomaly executive explanation from Gemini...")
            response_text = AIService.generate_content(prompt)
            return response_text
        except Exception as e:
            logger.error(f"Failed to fetch anomaly summary from Gemini: {e}", exc_info=True)
            return f"⚠️ Summary Generation Unavailable: {e}"
