import pandas as pd
from services.sql_service import SQLService
from services.forecast_service import ForecastService
from services.anomaly_service import AnomalyService
from services.quality_service import QualityService
from services.ai_service import AIService
from modules.charts import generate_chart as original_generate_chart


class ToolService:
    @staticmethod
    def generate_sql(prompt: str, data_context: dict, chat_history: list = None) -> dict:
        """
        Generates a SQL query based on user prompt and dataset context.
        """
        sql_resp = AIService.get_chat_response(
            prompt=f"Generate a SQL query to solve: {prompt}", data_context=data_context, chat_history=chat_history
        )
        return {
            "sql_query": sql_resp.get("sql_query", "").strip(),
            "pandas_code": sql_resp.get("pandas_code", "").strip(),
        }

    @staticmethod
    def execute_sql(sql: str, data_context: dict):
        """
        Executes DuckDB SELECT queries against registered datasets.
        """
        return SQLService.execute_sql_query(sql, data_context)

    @staticmethod
    def generate_chart(df: pd.DataFrame, chart_type: str = None, x: str = None, y: str = None):
        """
        Generates Plotly figure object based on data columns.
        """
        return original_generate_chart(df, chart_type=chart_type, x=x, y=y)

    @staticmethod
    def generate_forecast(df: pd.DataFrame, date_col: str, target_col: str, horizon_str: str, agg_func: str = "sum"):
        """
        Aggregates series and runs model predictions.
        """
        return ForecastService.generate_forecast(
            df=df, date_col=date_col, target_col=target_col, horizon_str=horizon_str, agg_func=agg_func
        )

    @staticmethod
    def quality_check(df: pd.DataFrame) -> dict:
        """
        Performs data quality assessments.
        """
        return QualityService.run_audit(df)

    @staticmethod
    def detect_anomalies(df: pd.DataFrame):
        """
        Scans numeric features for outliers.
        """
        return AnomalyService.detect_anomalies(df)

    @staticmethod
    def generate_report(session_state, company_name: str, report_title: str) -> bytes:
        """
        Assembles all diagnostics results to compile A4 PDF bytes.
        """
        from services.report_service import ReportService

        return ReportService.generate_pdf(
            session_state=session_state, company_name=company_name, report_title=report_title
        )

    @staticmethod
    def detect_datetime_columns(df: pd.DataFrame) -> list:
        """
        Scans columns to identify datetime representation candidates.
        """
        return ForecastService.detect_datetime_columns(df)

    @staticmethod
    def detect_numeric_columns(df: pd.DataFrame, datetime_cols: list) -> list:
        """
        Scans columns to identify potential target numeric metrics.
        """
        return ForecastService.detect_numeric_columns(df, datetime_cols)
