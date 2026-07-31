import streamlit as st
import datetime
import time
import pandas as pd
from utils import format_summary, format_paragraphs_to_bullets, logger, safe_dataframe_to_markdown

def render_assistant_message(content: str, reasoning: str = None, sql_query: str = None, sql_results = None, pandas_code: str = None, confidence: float = None, timestamp: str = None, msg_key: str = "", plotly_fig = None, forecast_result = None, quality_result = None, anomaly_result = None, pdf_bytes = None):
    """
    Renders structured assistant message content in collapsible containers.
    Handles backwards compatibility logic for merged chat logs.
    """
    if "### 🧠 Reasoning" in content:
        parts = content.split("### 🧠 Reasoning")
        summary_block = parts[0].replace("### 📋 Summary", "").replace("### 📌 Summary", "").strip()
        reasoning_block = parts[1].strip()
    else:
        summary_block = content.replace("### 📋 Summary", "").replace("### 📌 Summary", "").strip()
        reasoning_block = reasoning

    st.markdown("### 📌 Summary")
    st.markdown(summary_block)
    
    if reasoning_block:
        with st.expander("🧠 View Reasoning Process", expanded=False):
            st.markdown(reasoning_block)
    
    if sql_query:
        with st.expander("🗄️ View Generated DuckDB SQL Query", expanded=False):
            st.code(sql_query, language="sql")

        if sql_results is not None:
            with st.expander("📊 View SQL Results Table", expanded=True):
                if isinstance(sql_results, pd.DataFrame):
                    st.dataframe(sql_results, use_container_width=True)
                    st.download_button(
                        label="📥 Download SQL Results (CSV)",
                        data=sql_results.to_csv(index=False).encode("utf-8"),
                        file_name="sql_query_results.csv",
                        mime="text/csv",
                        key=f"dl_sql_{msg_key}",
                        use_container_width=True
                    )
                elif isinstance(sql_results, str):
                    st.warning(sql_results)
    
    if pandas_code:
        with st.expander("🐼 View Generated Pandas Code", expanded=False):
            st.code(pandas_code, language="python")

    # Dynamic Agent Tool Renderers
    if plotly_fig:
        with st.expander("📈 View Generated Chart", expanded=True):
            st.plotly_chart(plotly_fig, use_container_width=True)

    if forecast_result:
        with st.expander("🔮 View Forecast Summary", expanded=True):
            fore_sum = forecast_result.get("forecast_summary", {})
            st.write(f"**Target Metric:** `{forecast_result.get('target_col', 'Metric')}`")
            st.write(f"**Forecast End Value:** `{fore_sum.get('end_value', 0.0):.2f}`")
            st.write(f"**Projected Growth:** `{fore_sum.get('change_pct', 0.0):+.2f}%`")

    if quality_result:
        with st.expander("🧼 View Data Quality Audit", expanded=True):
            st.metric("Data Quality Score", f"{quality_result['score']}/100", delta=quality_result['severity'])
            if quality_result.get('warnings'):
                st.warning("\n".join([f"- {w}" for w in quality_result['warnings']]))

    if anomaly_result:
        with st.expander("🚨 View Anomaly Alerts", expanded=True):
            anom_df = anomaly_result.get("anomalies", pd.DataFrame())
            anom_count = len(anom_df)
            st.write(f"Scanned dataset rows. Detected **{anom_count}** outliers.")

    if pdf_bytes:
        st.download_button(
            label="📥 Download Compiled PDF Report",
            data=pdf_bytes,
            file_name="agentic_report.pdf",
            mime="application/pdf",
            key=f"dl_pdf_agent_{msg_key}",
            use_container_width=True
        )
        
    if confidence is not None:
        try:
            conf_val = float(confidence)
            conf_val = max(0.0, min(conf_val, 1.0))
            st.markdown("### Confidence Score")
            st.progress(conf_val)
            st.caption(f"Confidence: {conf_val:.0%}")
        except Exception:
            pass

    if timestamp:
        st.caption(timestamp)

    # Render thumbs up/down feedback buttons linked to msg_key
    if msg_key:
        feedback_key = f"fb_{msg_key}"
        from services.evaluation_service import EvaluationService
        cols_fb = st.columns([1, 1, 10])
        with cols_fb[0]:
            if st.button("👍", key=f"up_{feedback_key}"):
                EvaluationService.update_feedback(msg_key, "Positive")
                st.toast("Thank you for your feedback!")
        with cols_fb[1]:
            if st.button("👎", key=f"down_{feedback_key}"):
                EvaluationService.update_feedback(msg_key, "Negative")
                st.toast("Feedback recorded. We will improve!")


def render_chat_tab():
    """
    Manages interactive QA conversation inputs, displaying chat bubbles,
    spinning loaders, and appending structured outputs to history logs.
    """
    st.subheader("💬 Interactive Analysis")

    # Display chat history
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(
            message["role"],
            avatar="👤" if message["role"] == "user" else "🤖"
        ):
            if message["role"] == "user":
                st.markdown(f"""
                <div class="user-chat-container">
                    <div class="user-chat-bubble">{message["content"]}</div>
                </div>
                """, unsafe_allow_html=True)
                if "timestamp" in message:
                    st.markdown(f'<div class="chat-timestamp-user">{message["timestamp"]}</div>', unsafe_allow_html=True)
            else:
                render_assistant_message(
                    content=message.get("content", ""),
                    reasoning=message.get("reasoning"),
                    sql_query=message.get("sql_query"),
                    sql_results=message.get("sql_results"),
                    pandas_code=message.get("pandas_code"),
                    confidence=message.get("confidence"),
                    timestamp=message.get("timestamp"),
                    msg_key=message.get("id", f"hist_{idx}")
                )

    if prompt := st.chat_input("Ask a question about your data..."):
        timestamp = datetime.datetime.now().strftime("%H:%M")
        
        # Generate unique interaction ID for evaluations mapping
        interaction_id = f"msg_{int(time.time() * 1000)}"

        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": timestamp,
            "id": interaction_id
        })

        with st.chat_message("user", avatar="👤"):
            st.markdown(f"""
            <div class="user-chat-container">
                <div class="user-chat-bubble">{prompt}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f'<div class="chat-timestamp-user">{timestamp}</div>', unsafe_allow_html=True)
            
        start_eval_time = time.time()

        # Step 1 & 2: Planning & Executing Workflow
        with st.spinner("Executing agentic workflow..."):
            context = {
                name: res["df"]
                for name, res in st.session_state.data.items()
            }
            try:
                from services.router_service import RouterService
                response_data = RouterService.execute_workflow(
                    prompt,
                    context,
                    st.session_state.chat_history
                )
            except Exception as e:
                logger.error(f"Agentic workflow failed: {e}", exc_info=True)
                st.error(f"Workflow execution failed:\n{e}")
                st.stop()

        with st.chat_message("assistant", avatar="🤖"):
            # Summary
            st.markdown("### 📌 Summary")
            summary_text = format_summary(response_data.get("answer", "No answer generated."))
            st.markdown(summary_text)

            # Reasoning
            reasoning_text = format_paragraphs_to_bullets(response_data.get("reasoning", "No reasoning provided."))
            with st.expander("🧠 View Reasoning Process", expanded=False):
                st.markdown(reasoning_text)

            # SQL & SQL Results
            sql_query = response_data.get("sql_query", "").strip()
            sql_results = response_data.get("sql_results")

            if sql_query and sql_query.upper() not in ["N/A", "NONE", "NULL"]:
                with st.expander("🗄️ View Generated DuckDB SQL Query", expanded=False):
                    st.code(sql_query, language="sql")

                if sql_results is not None:
                    with st.expander("📊 View SQL Results Table", expanded=True):
                        if isinstance(sql_results, pd.DataFrame):
                            st.dataframe(sql_results, use_container_width=True)
                            st.download_button(
                                label="📥 Download SQL Results (CSV)",
                                data=sql_results.to_csv(index=False).encode("utf-8"),
                                file_name="sql_query_results.csv",
                                mime="text/csv",
                                key="dl_sql_dyn",
                                use_container_width=True
                            )
                        elif isinstance(sql_results, str):
                            st.warning(sql_results)

            # Pandas Code
            pandas_code = response_data.get("pandas_code", "").strip()
            if pandas_code:
                with st.expander("🐼 View Generated Pandas Code", expanded=False):
                    st.code(pandas_code, language="python")

            # Dynamic Agent Tool Renderers
            plotly_fig = response_data.get("plotly_fig")
            if plotly_fig:
                with st.expander("📈 View Generated Chart", expanded=True):
                    st.plotly_chart(plotly_fig, use_container_width=True)

            forecast_res = response_data.get("forecast_result")
            if forecast_res:
                with st.expander("🔮 View Forecast Summary", expanded=True):
                    fore_sum = forecast_res.get("forecast_summary", {})
                    st.write(f"**Target Metric:** `{forecast_res.get('target_col', 'Metric')}`")
                    st.write(f"**Forecast End Value:** `{fore_sum.get('end_value', 0.0):.2f}`")
                    st.write(f"**Projected Growth:** `{fore_sum.get('change_pct', 0.0):+.2f}%`")

            quality_res = response_data.get("quality_result")
            if quality_res:
                with st.expander("🧼 View Data Quality Audit", expanded=True):
                    st.metric("Data Quality Score", f"{quality_res['score']}/100", delta=quality_res['severity'])
                    if quality_res.get('warnings'):
                        st.warning("\n".join([f"- {w}" for w in quality_res['warnings']]))

            anomaly_res = response_data.get("anomaly_result")
            if anomaly_res:
                with st.expander("🚨 View Anomaly Alerts", expanded=True):
                    anom_df = anomaly_res.get("anomalies", pd.DataFrame())
                    st.write(f"Scanned dataset rows. Detected **{len(anom_df)}** outliers.")

            pdf_bytes = response_data.get("pdf_bytes")
            if pdf_bytes:
                st.download_button(
                    label="📥 Download Compiled PDF Report",
                    data=pdf_bytes,
                    file_name="agentic_report.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_agent_{interaction_id}",
                    use_container_width=True
                )

            # Confidence
            confidence_score = None
            try:
                confidence_score = float(response_data.get("confidence", 0.80))
                confidence_score = max(0.0, min(confidence_score, 1.0))
                st.markdown("### Confidence Score")
                st.progress(confidence_score)
                st.caption(f"Confidence: {confidence_score:.0%}")
            except Exception:
                pass

            st.caption(timestamp)
            
            # Stop latency evaluation timer
            duration = time.time() - start_eval_time
            
            # Check SQL execution success or failures status
            success = True
            failure_reason = ""
            if sql_query and sql_query.upper() not in ["N/A", "NONE", "NULL"]:
                if isinstance(sql_results, str) and sql_results.startswith("SQL Execution Error"):
                    success = False
                    failure_reason = sql_results
            
            # Log results to evaluations engine
            from services.evaluation_service import EvaluationService
            EvaluationService.log_interaction(
                interaction_id=interaction_id,
                prompt=prompt,
                generated_sql=sql_query,
                executed_sql=safe_dataframe_to_markdown(sql_results) if isinstance(sql_results, pd.DataFrame) else (sql_results or ""),
                generated_pandas=pandas_code,
                confidence=confidence_score if confidence_score is not None else 0.80,
                execution_time=duration,
                success=success,
                failure_reason=failure_reason
            )

        st.session_state.messages.append({
            "role": "assistant",
            "content": summary_text,
            "reasoning": reasoning_text,
            "sql_query": sql_query if sql_query and sql_query.upper() not in ["N/A", "NONE", "NULL"] else None,
            "sql_results": sql_results,
            "pandas_code": pandas_code if pandas_code else None,
            "plotly_fig": plotly_fig,
            "forecast_result": forecast_res,
            "quality_result": quality_res,
            "anomaly_result": anomaly_res,
            "pdf_bytes": pdf_bytes,
            "confidence": confidence_score,
            "timestamp": timestamp,
            "id": interaction_id
        })
