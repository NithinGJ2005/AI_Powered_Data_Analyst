import json
from services.ai_service import AIService
import config
from utils import logger, sanitize_table_name


class PlannerService:
    @classmethod
    def generate_plan(cls, prompt: str, data_context: dict, chat_history: list = None) -> dict:
        """
        Uses Gemini to analyze the user query and generate a structured JSON execution plan.
        """
        if chat_history is None:
            chat_history = []

        logger.info(f"Generating agentic plan for query: '{prompt[:50]}'")

        # Build schema reference context
        context = []
        for filename, df in data_context.items():
            table_name = sanitize_table_name(filename)
            context.append(f"Dataset Name: {table_name}\nColumns: {list(df.columns)}\nRows: {len(df)}\n")
        context_str = "\n".join(context)
        history_str = "\n".join(chat_history[-6:])

        planner_prompt = f"""
You are the Lead Coordinator and Planner of an AI Data Analyst system.
Your job is to analyze the user's analytical question and decide which tools are required to answer it.

Available Datasets:
{context_str}

Conversation History:
{history_str}

User Question:
{prompt}

Available Tools:
1. "SQL": Use this if the query requires looking up numbers, aggregates, filtering, sorting, or computing metrics from the dataset.
2. "Charts": Use this if the user specifically asks to plot, visualize, graph, chart, or show distributions.
3. "Forecast": Use this if the user asks to predict, forecast, project, or see future values of a metric.
4. "Data Quality": Use this if the user asks about missing values, duplicates, nulls, cardinality, empty columns, or dataset cleanliness.
5. "Anomaly Detection": Use this if the user asks for outliers, anomalies, deviations, or extreme values.
6. "Report Generation": Use this if the user asks to generate a report, download a PDF, create a PDF, or write a final report.

You MUST decide on a list of tools to run (subset of ["SQL", "Charts", "Forecast", "Data Quality", "Anomaly Detection", "Report Generation"]).
For most standard questions, "SQL" is the primary engine. Multiple tools can be chosen (e.g. ["SQL", "Charts"] if they want to query and plot it).

Return ONLY a valid JSON object matching the following structure:
{{
    "reasoning": "Explain step-by-step why these tools were selected",
    "tools": ["SQL", "Charts"],
    "parameters": {{
        "selected_dataset": "name of the dataset file or clean table identifier",
        "sql_explanation": "What query to run",
        "chart_type": "Bar, Line, Scatter, Histogram, Pie, or Box",
        "chart_x": "column name for X-axis",
        "chart_y": "column name for Y-axis",
        "forecast_column": "numeric column name to forecast",
        "forecast_date_column": "date column name for forecast",
        "forecast_horizon": "Next 30 days, Next 6 months, or Next 12 months",
        "anomaly_column": "target column to verify outliers",
        "report_title": "title for the PDF report if generated"
    }}
}}

Return ONLY the raw JSON. Do not wrap it in markdown backticks or any other text.
"""
        try:
            
            response_text = AIService.generate_content(planner_prompt)
            response_text = response_text
            logger.info("Planner service received prompt execution output.")

            # Parse JSON robustly
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            plan = json.loads(cleaned_text)

            # Safeguards
            if "tools" not in plan or not isinstance(plan["tools"], list):
                plan["tools"] = []
            if "parameters" not in plan or not isinstance(plan["parameters"], dict):
                plan["parameters"] = {}
            if "reasoning" not in plan:
                plan["reasoning"] = "No planning reasoning provided."

            logger.info(f"Plan formulated successfully. Selected tools: {plan['tools']}")
            return plan

        except Exception as e:
            logger.error(f"Planner service failed: {e}", exc_info=True)
            # Safe fallback: assume standard SQL query
            return {
                "reasoning": f"Planner failed due to error: {e}. Falling back to default SQL query flow.",
                "tools": ["SQL"],
                "parameters": {},
            }
