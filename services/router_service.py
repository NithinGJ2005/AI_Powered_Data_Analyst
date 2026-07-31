import time
import json
import pandas as pd
from services.planner_service import PlannerService
from services.tool_service import ToolService
from services.ai_service import AIService
import config
from utils import logger, sanitize_table_name


class RouterService:
    @classmethod
    def execute_workflow(cls, prompt: str, data_context: dict, chat_history: list = None) -> dict:
        """
        Orchestrates the lightweight agentic workflow: Plan -> Execute Tools via ToolService -> Synthesize Response.
        """
        start_time = time.time()
        if chat_history is None:
            chat_history = []

        # 1. Plan
        plan = PlannerService.generate_plan(prompt, data_context, chat_history)
        tools = plan.get("tools", [])
        params = plan.get("parameters", {})
        reasoning = plan.get("reasoning", "No planning reasoning provided.")

        # Default dataset selection
        dataset_keys = list(data_context.keys())
        if not dataset_keys:
            return {
                "answer": "No datasets are loaded. Please upload a CSV first.",
                "reasoning": "Plan generation skipped because no data context exists.",
                "sql_query": "",
                "sql_results": None,
                "pandas_code": "",
                "plotly_fig": None,
                "confidence": 0.0,
            }

        selected_dataset = params.get("selected_dataset")
        active_dataset = dataset_keys[0]
        for key in dataset_keys:
            if sanitize_table_name(key) == selected_dataset or key == selected_dataset:
                active_dataset = key
                break

        df = data_context[active_dataset]

        # Context output buffers for tool executions
        execution_results = {}
        plotly_fig = None
        sql_query = ""
        sql_results = None
        pandas_code = ""
        forecast_result = None
        quality_result = None
        anomaly_result = None
        pdf_report_bytes = None

        # 2. Execute Tools sequentially via ToolService
        for tool in tools:
            logger.info(f"Executing workflow tool: {tool}")

            if tool == "SQL":
                try:
                    sql_resp = ToolService.generate_sql(prompt, data_context, chat_history)
                    sql_query = sql_resp.get("sql_query", "").strip()
                    pandas_code = sql_resp.get("pandas_code", "").strip()

                    if sql_query and sql_query.upper() not in ["N/A", "NONE", "NULL"]:
                        sql_results = ToolService.execute_sql(sql_query, data_context)
                        if isinstance(sql_results, pd.DataFrame):
                            execution_results["SQL"] = {
                                "query": sql_query,
                                "row_count": len(sql_results),
                                "columns": list(sql_results.columns),
                                "preview": sql_results.head(5).to_dict(),
                            }
                        else:
                            execution_results["SQL"] = {"query": sql_query, "error": str(sql_results)}
                    else:
                        execution_results["SQL"] = {"query": "No query generated."}
                except Exception as e:
                    execution_results["SQL"] = {"error": f"SQL execution crashed: {e}"}

            elif tool == "Charts":
                c_type = params.get("chart_type")
                x_col = params.get("chart_x")
                y_col = params.get("chart_y")

                valid_cols = [c for c in df.columns if not str(c).startswith("Unnamed:")]
                if not x_col or x_col not in df.columns:
                    x_col = valid_cols[0] if valid_cols else df.columns[0]
                if not y_col or y_col not in df.columns:
                    y_col = valid_cols[min(1, len(valid_cols) - 1)] if valid_cols else df.columns[0]

                try:
                    plotly_fig = ToolService.generate_chart(df, chart_type=c_type, x=x_col, y=y_col)
                    execution_fig_status = "Successfully generated." if plotly_fig else "Failed to draw."
                    execution_results["Charts"] = {
                        "chart_type": c_type,
                        "x": x_col,
                        "y": y_col,
                        "status": execution_fig_status,
                    }
                except Exception as e:
                    execution_results["Charts"] = {"error": f"Chart rendering failed: {e}"}

            elif tool == "Forecast":
                date_c = params.get("forecast_date_column")
                target_c = params.get("forecast_column")
                horizon = params.get("forecast_horizon", "Next 30 days")

                # Fallback column detection through ToolService
                if not date_c:
                    dates = ToolService.detect_datetime_columns(df)
                    date_c = dates[0] if dates else None
                if not target_c:
                    nums = ToolService.detect_numeric_columns(df, [date_c] if date_c else [])
                    target_c = nums[0] if nums else None

                if date_c and target_c:
                    try:
                        fc_res = ToolService.generate_forecast(
                            df, date_col=date_c, target_col=target_c, horizon_str=horizon
                        )
                        if fc_res.get("error"):
                            execution_results["Forecast"] = {"error": fc_res["error"]}
                        else:
                            forecast_result = fc_res
                            execution_results["Forecast"] = {
                                "target": target_c,
                                "date": date_c,
                                "horizon": horizon,
                                "method_used": fc_res["method_used"],
                                "stats": fc_res["forecast_summary"],
                            }
                    except Exception as e:
                        execution_results["Forecast"] = {"error": f"Forecast execution failed: {e}"}
                else:
                    execution_results["Forecast"] = {"error": "Missing valid date/numeric columns."}

            elif tool == "Data Quality":
                try:
                    q_res = ToolService.quality_check(df)
                    quality_result = q_res
                    execution_results["Data Quality"] = {
                        "score": q_res["score"],
                        "severity": q_res["severity"],
                        "warnings": q_res["warnings"][:5],
                        "missing_count": q_res["missing_total"],
                        "outlier_count": q_res["outlier_count"],
                    }
                except Exception as e:
                    execution_results["Data Quality"] = {"error": f"Quality audit failed: {e}"}

            elif tool == "Anomaly Detection":
                try:
                    updated_df, anomalies = ToolService.detect_anomalies(df)
                    anomaly_result = {"updated_df": updated_df, "anomalies": anomalies}
                    execution_results["Anomaly Detection"] = {
                        "scanned": len(updated_df),
                        "anomalies_detected": len(anomalies),
                    }
                except Exception as e:
                    execution_results["Anomaly Detection"] = {"error": f"Anomaly detection failed: {e}"}

            elif tool == "Report Generation":
                try:
                    import streamlit as st

                    title = params.get("report_title", "Branded Analytics Report")
                    pdf_bytes = ToolService.generate_report(
                        st.session_state, company_name="Enterprise AI Platform", report_title=title
                    )
                    pdf_report_bytes = pdf_bytes
                    execution_results["Report Generation"] = {
                        "status": "PDF report compiled successfully.",
                        "size_bytes": len(pdf_bytes),
                    }
                except Exception as e:
                    execution_results["Report Generation"] = {"error": f"Report compilation failed: {e}"}

        # 3. Gemini explanation synthesis based on tool results
        results_str = json.dumps(execution_results, indent=2, default=str)
        synthesis_prompt = f"""
You are the lead Executive AI Data Analyst summarizing tool execution results for the user.

Original User Query:
"{prompt}"

Executed Plan Reasoning:
{reasoning}

Tools Executed:
{list(execution_results.keys())}

Execution Results Output details:
{results_str}

Please compose a comprehensive, professional executive response:
- Directly answer the user query based on the specific statistics and tool output.
- Explain the key business trends, anomalies, outliers, or warnings discovered.
- Offer actionable recommendations.
- Keep formatting professional, clear, and easy to read.

Return only the final explanation text in clean Markdown.
"""
        try:
            
            answer = AIService.generate_content(synthesis_prompt)
            
        except Exception as se:
            logger.error(f"Gemini synthesis failed: {se}", exc_info=True)
            answer = f"Generated tools executed successfully: {list(execution_results.keys())}. Synthesis failed: {se}"

        logger.info(f"Agentic workflow execution complete in {time.time() - start_time:.2f}s")

        return {
            "answer": answer,
            "reasoning": reasoning,
            "sql_query": sql_query,
            "sql_results": sql_results,
            "pandas_code": pandas_code,
            "plotly_fig": plotly_fig,
            "forecast_result": forecast_result,
            "quality_result": quality_result,
            "anomaly_result": anomaly_result,
            "pdf_bytes": pdf_report_bytes,
            "confidence": 0.95,
        }
