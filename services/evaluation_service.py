import os
import json
import pandas as pd
import streamlit as st
from utils import logger

EVAL_FILE = "logs/evaluations.json"


class EvaluationService:
    @staticmethod
    def _load_evaluations() -> list:
        if "evaluations" not in st.session_state:
            # Try loading from local file
            if os.path.exists(EVAL_FILE):
                try:
                    with open(EVAL_FILE, "r", encoding="utf-8") as f:
                        st.session_state.evaluations = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to read evaluation log: {e}", exc_info=True)
                    st.session_state.evaluations = []
            else:
                st.session_state.evaluations = []
        return st.session_state.evaluations

    @staticmethod
    def _save_evaluations(evals: list):
        st.session_state.evaluations = evals
        os.makedirs(os.path.dirname(EVAL_FILE), exist_ok=True)
        try:
            with open(EVAL_FILE, "w", encoding="utf-8") as f:
                json.dump(evals, f, indent=4, default=str)
        except Exception as e:
            logger.error(f"Failed to write evaluations log: {e}", exc_info=True)

    @classmethod
    def log_interaction(
        cls,
        interaction_id: str,
        prompt: str,
        generated_sql: str,
        executed_sql: str,
        generated_pandas: str,
        confidence: float,
        execution_time: float,
        success: bool,
        failure_reason: str,
    ):
        evals = cls._load_evaluations()

        # Check if already exists (prevent duplicate log on refresh)
        for ev in evals:
            if ev["interaction_id"] == interaction_id:
                return

        record = {
            "interaction_id": interaction_id,
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "prompt": prompt,
            "generated_sql": generated_sql,
            "executed_sql": executed_sql,
            "generated_pandas": generated_pandas,
            "confidence": confidence,
            "execution_time": execution_time,
            "success": success,
            "failure_reason": failure_reason,
            "user_feedback": None,
        }
        evals.append(record)
        cls._save_evaluations(evals)

    @classmethod
    def update_feedback(cls, interaction_id: str, feedback: str):
        evals = cls._load_evaluations()
        updated = False
        for ev in evals:
            if ev["interaction_id"] == interaction_id:
                ev["user_feedback"] = feedback
                updated = True
                break
        if updated:
            cls._save_evaluations(evals)

    @classmethod
    def get_evaluations(cls) -> list:
        return cls._load_evaluations()

    @classmethod
    def clear_evaluations(cls):
        cls._save_evaluations([])
        if os.path.exists(EVAL_FILE):
            try:
                os.remove(EVAL_FILE)
            except Exception as e:
                logger.error(f"Failed to delete evaluation log file: {e}", exc_info=True)

    @classmethod
    def get_metrics(cls) -> dict:
        evals = cls._load_evaluations()
        if not evals:
            return {
                "total_queries": 0,
                "avg_response_time": 0.0,
                "avg_confidence": 0.0,
                "sql_success_rate": 0.0,
                "failed_queries": 0,
            }

        total = len(evals)
        success_count = sum(1 for e in evals if e["success"])
        failed_count = total - success_count
        avg_time = sum(e["execution_time"] for e in evals) / total

        conf_vals = [e["confidence"] for e in evals if e["confidence"] is not None]
        avg_conf = sum(conf_vals) / len(conf_vals) if conf_vals else 0.0

        # Calculate success rate for queries containing SQL
        sql_queries = [e for e in evals if e["generated_sql"] and e["generated_sql"].strip()]
        if sql_queries:
            sql_success_count = sum(1 for e in sql_queries if e["success"])
            sql_success_rate = (sql_success_count / len(sql_queries)) * 100
        else:
            sql_success_rate = 100.0 if failed_count == 0 else 0.0

        return {
            "total_queries": total,
            "avg_response_time": avg_time,
            "avg_confidence": avg_conf * 100 if avg_conf <= 1.0 else avg_conf,
            "sql_success_rate": sql_success_rate,
            "failed_queries": failed_count,
        }
