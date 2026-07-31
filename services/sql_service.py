import re
import time
import duckdb
import streamlit as st
import config
from utils import logger, sanitize_table_name

class SQLService:
    @staticmethod
    @st.cache_resource
    def get_connection():
        """
        Caches and returns the persistent DuckDB in-memory database connection.
        """
        logger.info("Initializing in-memory DuckDB connection resource...")
        return duckdb.connect(database=":memory:")

    @classmethod
    def execute_sql_query(cls, sql: str, data_context: dict):
        """
        Validates and executes SQL query against registered DataFrames.
        """
        start_time = time.time()
        if not sql or not sql.strip():
            logger.info("Empty SQL query supplied. Execution skipped.")
            return None

        # Clean query whitespace
        query = sql.strip()
        logger.info(f"Incoming SQL execution request: {query[:100]}...")

        # 1. Block comments
        if "--" in query or "/*" in query or "*/" in query:
            warn_msg = "⚠️ SQL execution rejected: Comments are not allowed in queries for security purposes."
            logger.warning(warn_msg)
            return warn_msg

        # 2. Block multiple statements (semicolon check)
        # Semicolons are allowed at the very end, but not in the middle separating statements
        stmt_check = query.rstrip(";").split(";")
        if len(stmt_check) > 1:
            warn_msg = "⚠️ SQL execution rejected: Multiple SQL statements are not allowed."
            logger.warning(warn_msg)
            return warn_msg

        # 3. Security keyword check
        sql_upper = query.upper()
        for kw in config.BLOCKED_SQL_KEYWORDS:
            if re.search(r'\b' + kw + r'\b', sql_upper):
                warn_msg = f"⚠️ SQL execution rejected: Unsafe statement detected. The query contains the blocked keyword '{kw}'."
                logger.warning(warn_msg)
                return warn_msg

        # 4. Strict SELECT constraint check
        if not re.match(r'^\s*SELECT\b', sql_upper):
            warn_msg = "⚠️ SQL execution rejected: Only SELECT statements are permitted."
            logger.warning(warn_msg)
            return warn_msg

        # Execution using connection resource
        conn = cls.get_connection()
        try:
            # Register each uploaded DataFrame as a DuckDB table using clean names
            for filename, df in data_context.items():
                table_name = sanitize_table_name(filename)
                # Verify that the query uses active registered dataset names
                conn.register(table_name, df)

            result_df = conn.execute(query).fetchdf()
            logger.info(f"SQL execution succeeded in {time.time() - start_time:.3f}s. Row count: {len(result_df)}")
            return result_df

        except Exception as e:
            err_msg = f"SQL Execution Error:\n{e}"
            logger.error(f"SQL query execution failed: {e}", exc_info=True)
            return err_msg
