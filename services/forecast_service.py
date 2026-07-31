import pandas as pd
import numpy as np
import streamlit as st
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from utils import logger

import config
# Try imports for optional libraries to implement priority fallback chain
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

try:
    from statsmodels.tsa.api import ExponentialSmoothing
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


class ForecastService:
    @staticmethod
    def detect_datetime_columns(df: pd.DataFrame) -> list:
        """
        Scans columns to identify datetime representation candidates.
        Uses a 100-row sample for speed and accuracy.
        """
        candidates = []

        # 1. Direct datetime type check
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                candidates.append((col, 3))  # Highest confidence

        # 2. Try parsing object/string/category columns
        for col in df.columns:
            if col in [c for c, _ in candidates]:
                continue

            # Skip numeric target candidates unless named appropriately
            if pd.api.types.is_numeric_dtype(df[col]):
                if not any(kw in str(col).lower() for kw in ["year", "date", "time"]):
                    continue

            if str(col).startswith("Unnamed:"):
                continue

            # Sample non-null values
            non_nulls = df[col].dropna()
            if non_nulls.empty:
                continue

            sample_size = min(100, len(non_nulls))
            sample = non_nulls.sample(sample_size, random_state=42)

            try:
                parsed = pd.to_datetime(sample, errors="coerce")
                success_rate = parsed.notnull().sum() / sample_size
                if success_rate > 0.70:
                    confidence = 2
                    if any(kw in str(col).lower() for kw in ["date", "time", "timestamp", "created_at"]):
                        confidence = 3
                    candidates.append((col, confidence))
            except Exception:
                pass

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates]

    @staticmethod
    def detect_numeric_columns(df: pd.DataFrame, datetime_cols: list) -> list:
        """
        Scans columns to identify potential target numeric metrics.
        Excludes datetime columns and obvious sequential IDs.
        """
        numeric_cols = []
        for col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue
            if col in datetime_cols:
                continue
            if str(col).startswith("Unnamed:"):
                continue

            # Filter out index or ID-like columns (all integers, unique/sequential or ends with _id)
            col_lower = str(col).lower()
            if col_lower == "id" or col_lower.endswith("_id") or col_lower.endswith("id"):
                if df[col].nunique() == len(df):
                    continue

            numeric_cols.append(col)
        return numeric_cols

    @staticmethod
    def get_forecast_horizon_periods(freq: str, horizon_str: str) -> int:
        """
        Maps a user-selected human-readable horizon to the appropriate number
        of forecast periods depending on the resampled time series frequency.
        """
        if freq == "D":
            if horizon_str == "Next 30 days":
                return 30
            elif horizon_str == "Next 6 months":
                return 180
            elif horizon_str == "Next 12 months":
                return 365
        elif freq == "W":
            if horizon_str == "Next 30 days":
                return 4
            elif horizon_str == "Next 6 months":
                return 26
            elif horizon_str == "Next 12 months":
                return 52
        elif freq == "ME":
            if horizon_str == "Next 30 days":
                return 1
            elif horizon_str == "Next 6 months":
                return 6
            elif horizon_str == "Next 12 months":
                return 12
        return 30

    @classmethod
    @st.cache_data
    def generate_forecast(
        cls, df: pd.DataFrame, date_col: str, target_col: str, horizon_str: str, agg_func: str = "sum"
    ) -> dict:
        """
        Aggregates data, chooses the best forecasting approach available,
        projects future values with 95% confidence intervals, and generates statistics.
        """
        logger.info(f"Triggering forecasting pipeline for target: '{target_col}' using date: '{date_col}'...")

        # Clean invalid values
        if date_col not in df.columns:
            return {"error": f"Date column '{date_col}' not found in the dataset."}
        if target_col not in df.columns:
            return {"error": f"Target column '{target_col}' not found in the dataset."}

        df_clean = df[[date_col, target_col]].dropna().copy()
        try:
            df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors="coerce")
            df_clean = df_clean.dropna(subset=[date_col])
        except Exception as e:
            logger.error(f"Datetime conversion failed: {e}", exc_info=True)
            return {"error": f"Failed to parse datetime column: {e}"}

        if len(df_clean) < 3:
            return {"error": "Dataset must contain at least 3 valid rows with parseable dates and target values."}

        # Sort chronologically
        df_clean = df_clean.sort_values(by=date_col)

        # Detect sample frequency dynamically based on median timestamp gaps
        time_diffs = df_clean[date_col].diff().dropna()
        if not time_diffs.empty:
            median_days = time_diffs.dt.total_seconds().median() / (24 * 3600)
        else:
            median_days = 1.0

        if median_days <= 3.0:
            freq = "D"
            freq_label = "Daily"
        elif median_days <= 10.0:
            freq = "W"
            freq_label = "Weekly"
        elif median_days <= 35.0:
            freq = "ME"
            freq_label = "Monthly"
        else:
            freq = "D"
            freq_label = "Daily"

        # Perform aggregation
        try:
            if agg_func == "sum":
                df_agg = df_clean.set_index(date_col).resample(freq).sum()
            else:
                df_agg = df_clean.set_index(date_col).resample(freq).mean()
        except Exception as e:
            logger.error(f"Resampling aggregation failed: {e}", exc_info=True)
            return {"error": f"Failed to aggregate data on frequency {freq_label}: {e}"}

        # Handle potential aggregated gaps
        if agg_func == "sum":
            df_agg = df_agg.fillna(0.0)
        else:
            df_agg = df_agg.interpolate(method="linear").ffill().bfill()

        if len(df_agg) < 3:
            return {"error": f"Dataset aggregation at {freq_label} level yielded fewer than 3 periods."}

        y = df_agg[target_col]
        horizon_periods = cls.get_forecast_horizon_periods(freq, horizon_str)

        # Initialize return frames
        forecast_df = None
        method_used = ""

        # --- Priority 1: Prophet ---
        if PROPHET_AVAILABLE:
            try:
                logger.info("Executing forecast using Prophet...")
                df_p = df_agg.reset_index().rename(columns={date_col: "ds", target_col: "y"})
                model = Prophet(yearly_seasonality=True, daily_seasonality=False)
                model.fit(df_p)
                future = model.make_future_dataframe(periods=horizon_periods, freq=freq)
                forecast = model.predict(future)

                fc_tail = forecast.tail(horizon_periods)
                forecast_df = pd.DataFrame(
                    {
                        "Date": fc_tail["ds"].values,
                        "Forecast": fc_tail["yhat"].values,
                        "Lower_Bound": fc_tail["yhat_lower"].values,
                        "Upper_Bound": fc_tail["yhat_upper"].values,
                    }
                )
                method_used = "Prophet"
            except Exception as pe:
                logger.warning(f"Prophet execution failed: {pe}. Falling back...", exc_info=True)

        # --- Priority 2: Exponential Smoothing (statsmodels) ---
        if forecast_df is None and STATSMODELS_AVAILABLE:
            try:
                logger.info("Executing forecast using Exponential Smoothing...")
                seasonal_periods = 7 if freq == "D" else (12 if freq == "ME" else None)

                if seasonal_periods and len(y) >= 2 * seasonal_periods:
                    model = ExponentialSmoothing(
                        y, trend="add", seasonal="add", seasonal_periods=seasonal_periods
                    )
                else:
                    model = ExponentialSmoothing(y, trend="add")

                fit_model = model.fit()
                future_dates = pd.date_range(
                    start=y.index[-1] + pd.tseries.frequencies.to_offset(freq),
                    periods=horizon_periods,
                    freq=freq,
                )
                forecast_vals = fit_model.forecast(steps=horizon_periods)

                # Compute prediction intervals from residual standard deviation
                residuals = y - fit_model.fittedvalues
                res_std = np.std(residuals) if len(residuals) > 0 else 1.0
                se = res_std * np.sqrt(np.arange(1, horizon_periods + 1))

                forecast_df = pd.DataFrame(
                    {
                        "Date": future_dates,
                        "Forecast": forecast_vals.values,
                        "Lower_Bound": forecast_vals.values - 1.96 * se,
                        "Upper_Bound": forecast_vals.values + 1.96 * se,
                    }
                )
                method_used = "Exponential Smoothing"
            except Exception as se_err:
                logger.warning(f"Exponential Smoothing failed: {se_err}. Falling back...", exc_info=True)

        # --- Priority 3: Linear Regression (scikit-learn) ---
        if forecast_df is None:
            logger.info("Executing forecast using Linear Regression...")
            t = np.arange(len(y)).reshape(-1, 1)
            features = [t]

            # Seasonal category encoding
            has_seasonality = False
            categorical_features = []

            if freq == "D" and len(y) >= 14:
                dow = y.index.dayofweek.values.reshape(-1, 1)
                features.append(dow)
                has_seasonality = True
                categorical_features = [1]
            elif freq == "ME" and len(y) >= 24:
                moy = y.index.month.values.reshape(-1, 1)
                features.append(moy)
                has_seasonality = True
                categorical_features = [1]

            X_raw = np.hstack(features)

            if has_seasonality:
                ct = ColumnTransformer(
                    [("onehot", OneHotEncoder(sparse_output=False, handle_unknown="ignore"), categorical_features)],
                    remainder="passthrough",
                )
                X = ct.fit_transform(X_raw)
            else:
                X = X_raw

            model = LinearRegression()
            model.fit(X, y)
            y_fit = model.predict(X)

            # Build future indices
            try:
                future_dates = pd.date_range(
                    start=y.index[-1] + pd.tseries.frequencies.to_offset(freq),
                    periods=horizon_periods,
                    freq=freq,
                )
            except Exception:
                # Manual date calculations fallback
                if freq == "D":
                    future_dates = [y.index[-1] + pd.Timedelta(days=i) for i in range(1, horizon_periods + 1)]
                elif freq == "W":
                    future_dates = [y.index[-1] + pd.Timedelta(weeks=i) for i in range(1, horizon_periods + 1)]
                else:
                    future_dates = [y.index[-1] + pd.Timedelta(days=30 * i) for i in range(1, horizon_periods + 1)]
                future_dates = pd.DatetimeIndex(future_dates)

            t_future = np.arange(len(y), len(y) + horizon_periods).reshape(-1, 1)
            if freq == "D" and len(y) >= 14:
                dow_future = future_dates.dayofweek.values.reshape(-1, 1)
                X_future_raw = np.hstack([t_future, dow_future])
            elif freq == "ME" and len(y) >= 24:
                moy_future = future_dates.month.values.reshape(-1, 1)
                X_future_raw = np.hstack([t_future, moy_future])
            else:
                X_future_raw = t_future

            if has_seasonality:
                X_future = ct.transform(X_future_raw)
            else:
                X_future = X_future_raw

            y_forecast = model.predict(X_future)

            # Compute prediction interval with standard errors of linear regression
            residuals = y - y_fit
            res_std = np.std(residuals) if len(residuals) > 0 else 1.0

            x_mean = np.mean(t)
            x_dev_sum = np.sum((t - x_mean) ** 2)
            if x_dev_sum == 0:
                se = res_std * np.ones(horizon_periods)
            else:
                se = res_std * np.sqrt(1 + 1 / len(y) + ((t_future.flatten() - x_mean) ** 2) / x_dev_sum)

            lower_bound = y_forecast - 1.96 * se
            upper_bound = y_forecast + 1.96 * se

            forecast_df = pd.DataFrame(
                {
                    "Date": future_dates,
                    "Forecast": y_forecast,
                    "Lower_Bound": lower_bound,
                    "Upper_Bound": upper_bound,
                }
            )
            method_used = "Linear Regression"

        # Clip values to zero if data is strictly positive
        if (y >= 0).all():
            forecast_df["Forecast"] = np.maximum(0, forecast_df["Forecast"])
            forecast_df["Lower_Bound"] = np.maximum(0, forecast_df["Lower_Bound"])
            forecast_df["Upper_Bound"] = np.maximum(0, forecast_df["Upper_Bound"])

        # Construct statistics dictionaries
        hist_sum = {
            "mean": float(y.mean()),
            "min": float(y.min()),
            "max": float(y.max()),
            "std": float(y.std()) if len(y) > 1 else 0.0,
            "last_value": float(y.values[-1]),
            "first_value": float(y.values[0]),
        }

        y_forecast = forecast_df["Forecast"].values
        fore_sum = {
            "mean": float(y_forecast.mean()),
            "min": float(y_forecast.min()),
            "max": float(y_forecast.max()),
            "std": float(np.std(y_forecast)) if len(y_forecast) > 1 else 0.0,
            "start_value": float(y_forecast[0]),
            "end_value": float(y_forecast[-1]),
            "change_pct": float(((y_forecast[-1] - y.values[-1]) / y.values[-1]) * 100)
            if y.values[-1] != 0
            else 0.0,
        }

        historical_df = pd.DataFrame({"Date": y.index, "Actual": y.values})

        logger.info(f"Forecast generation complete using method: {method_used}")

        return {
            "historical_df": historical_df,
            "forecast_df": forecast_df,
            "freq_label": freq_label,
            "method_used": method_used,
            "historical_summary": hist_sum,
            "forecast_summary": fore_sum,
            "error": None,
        }

    @classmethod
    def get_forecast_explanation(
        cls,
        target_col: str,
        date_col: str,
        freq_label: str,
        method_used: str,
        historical_summary: dict,
        forecast_summary: dict,
        forecast_df: pd.DataFrame,
    ) -> str:
        """
        Sends the forecast results to Gemini to explain trend, growth, decline, and business implications.
        """
        try:
            from services.ai_service import AIService
            

            # Format forecast points sample (first 10)
            forecast_points = []
            for idx, row in forecast_df.head(10).iterrows():
                date_str = row["Date"].strftime("%Y-%m-%d")
                forecast_points.append(
                    f"- {date_str}: {row['Forecast']:.2f} (95% CI: [{row['Lower_Bound']:.2f}, {row['Upper_Bound']:.2f}])"
                )
            forecast_points_str = "\n".join(forecast_points)
            if len(forecast_df) > 10:
                forecast_points_str += f"\n... (and {len(forecast_df) - 10} more periods)"

            prompt = f"""
You are an expert Data Analyst and Business Strategy Consultant.

Analyze the following time-series forecasting results and provide a professional business explanation.

**Context:**
- **Target Column:** {target_col}
- **Date/Time Column:** {date_col}
- **Aggregation Frequency:** {freq_label}
- **Forecasting Algorithm:** {method_used}

**Historical Data Summary:**
- Average Value: {historical_summary['mean']:.2f}
- Min Value: {historical_summary['min']:.2f}
- Max Value: {historical_summary['max']:.2f}
- Last Historical Value: {historical_summary['last_value']:.2f}

**Forecasting Summary:**
- Average Forecasted Value: {forecast_summary['mean']:.2f}
- Start Forecast Value: {forecast_summary['start_value']:.2f}
- End Forecast Value: {forecast_summary['end_value']:.2f}
- Projected Change: {forecast_summary['change_pct']:.2f}% (from last historical value)

**Forecasted Data Points (Sample):**
{forecast_points_str}

Please generate a professional business intelligence report addressing:
1. **Trend Explanation**: What is the overall projected direction (upward, downward, seasonal fluctuation, or flat)?
2. **Growth/Decline Analysis**: Quantify and analyze the projected change rate and potential turning points.
3. **Risks and Uncertainties**: What risks does the confidence interval bounds indicate? How should stakeholders interpret the prediction boundaries?
4. **Business Recommendations**: What specific operations/strategy decisions should stakeholders make (e.g. inventory control, resource capacity planning, marketing campaigns)?

Provide your analysis in clean, professional markdown format using bold headers and detailed bullet points.
Avoid complex mathematical definitions; focus on business outcomes and decision support.
"""
            logger.info("Requesting forecast analysis from Gemini model...")
            response_text = AIService.generate_content(prompt)
            return response_text
        except Exception as e:
            logger.error(f"Failed to generate forecast explanation from Gemini: {e}", exc_info=True)
            return f"⚠️ Could not generate AI explanation due to an error: {e}"
