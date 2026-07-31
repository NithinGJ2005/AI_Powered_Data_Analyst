import json
import time
import streamlit as st
from google import genai
from google.genai import types
import config
from utils import logger, sanitize_table_name


class AIService:
    @staticmethod
    @st.cache_resource
    def get_client() -> genai.Client:
        """
        Caches and returns the initialized google.genai Client instance.
        """
        if not config.GEMINI_API_KEY:
            logger.error("Gemini API key is not configured.")
            raise ValueError("GEMINI_API_KEY is not defined in the configuration environment.")

        logger.info("Initializing Google GenAI client resource...")
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        return client

    @classmethod
    def generate_content(cls, prompt: str, system_instruction: str = None, temperature: float = 0.4) -> str:
        """
        Wrapper to run Gemini generate_content with automatic retries, exponential backoff,
        and graceful error handling mapping to user-friendly messages without UI crashes.
        """
        import re

        # Check API key configuration before call
        if not config.GEMINI_API_KEY or config.GEMINI_API_KEY.strip() == "":
            logger.error("Gemini API key is missing or blank.")
            return """⚠️ AI configuration error: Invalid or missing API key.
Your analytical tools are still available.

Available:
✓ SQL
✓ Dashboard
✓ Charts
✓ Forecast
✓ Data Quality
✓ Reports"""

        max_attempts = 3
        base_delay = 2.0

        for attempt in range(1, max_attempts + 1):
            try:
                client = cls.get_client()

                # Setup generation configuration
                generation_config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=2048,
                )
                if system_instruction:
                    generation_config.system_instruction = system_instruction

                logger.info(f"Sending API request to Gemini (Attempt {attempt}/{max_attempts})...")
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL_NAME,
                    contents=prompt,
                    config=generation_config,
                )

                # Check for successful recovery
                if attempt > 1:
                    logger.info(f"Gemini API recovered successfully on attempt {attempt}.")

                return response.text.strip()

            except Exception as e:
                err_str = str(e).lower()
                code = getattr(e, 'code', None)

                logger.warning(f"Gemini API failure on attempt {attempt}/{max_attempts}: Code={code}, Error={e}")

                # Check if this is a terminal configuration error (no retry needed)
                if "api_key" in err_str or "api key" in err_str or "unauthorized" in err_str or "forbidden" in err_str or "not found" in err_str or code in [401, 403, 404]:
                    logger.error("Terminal AI configuration or model error detected (401/403/404). Bypassing retries.")
                    return """⚠️ AI configuration error: Invalid API key, insufficient permissions, or model unavailable.
Your analytical tools are still available.

Available:
✓ SQL
✓ Dashboard
✓ Charts
✓ Forecast
✓ Data Quality
✓ Reports"""

                # Determine if quota was exceeded
                is_quota = (code == 429 or "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str)
                if is_quota:
                    logger.warning("Gemini API quota exceeded (429 Resource Exhausted).")

                # If this was the last attempt, map to professional error message
                if attempt == max_attempts:
                    logger.error(f"Gemini API calls exhausted all {max_attempts} attempts. Mapping error to UI warning.")

                    if is_quota:
                        return """⚠️ AI quota exceeded.
Your analytical tools are still available.

Available:
✓ SQL
✓ Dashboard
✓ Charts
✓ Forecast
✓ Data Quality
✓ Reports

AI-generated explanations will resume once quota becomes available."""

                    # Service unavailable / network issues
                    if code in [500, 503] or "503" in err_str or "500" in err_str or "timeout" in err_str or "connect" in err_str or "unavailable" in err_str:
                        return """⚠️ AI service temporarily unavailable.
Your analytical tools are still available.

Available:
✓ SQL
✓ Dashboard
✓ Charts
✓ Forecast
✓ Data Quality
✓ Reports

AI-generated explanations will resume once the service is restored."""

                    # Generic fallback
                    return f"""⚠️ AI analysis generation failed: {e}
Your analytical tools are still available.

Available:
✓ SQL
✓ Dashboard
✓ Charts
✓ Forecast
✓ Data Quality
✓ Reports"""

                # Parse retryDelay from RetryInfo if available
                delay = base_delay * (2 ** (attempt - 1))  # default exponential backoff: 2s, 4s
                try:
                    from google.genai.errors import APIError
                    if isinstance(e, APIError) and hasattr(e, 'response_json') and isinstance(e.response_json, dict):
                        details = e.response_json.get('error', {}).get('details', [])
                        for d in details:
                            if 'RetryInfo' in d.get('@type', ''):
                                delay_str = d.get('retryDelay', '')
                                match = re.search(r'([0-9.]+)\s*s', delay_str)
                                if match:
                                    delay = float(match.group(1))
                                    logger.info(f"Respecting retryDelay from RetryInfo: {delay}s")
                except Exception:
                    pass

                logger.info(f"Sleeping for {delay:.2f}s before next attempt...")
                time.sleep(delay)

        # Fallback if loop ends unexpectedly
        return """⚠️ AI analysis generation failed.
Your analytical tools are still available.

Available:
✓ SQL
✓ Dashboard
✓ Charts
✓ Forecast
✓ Data Quality
✓ Reports"""

    @classmethod
    def get_chat_response(cls, prompt: str, data_context: dict, chat_history: list = None) -> dict:
        """
        Generates structured JSON response containing answers, SQL query, and Pandas code.
        """
        start_time = time.time()
        if chat_history is None:
            chat_history = []

        logger.info(f"Preparing AI request context for query: {prompt[:50]}...")

        # Build schema references
        context = []
        for filename, df in data_context.items():
            table_name = sanitize_table_name(filename)
            context.append(
                f"Dataset Name: {table_name}\nColumns: {list(df.columns)}\nRows: {len(df)}\n"
            )
        context_str = "\n".join(context)
        history_str = "\n".join(chat_history[-10:])

        # Build System instructions and wrapped user prompts
        full_prompt = f"""
{config.SYSTEM_INSTRUCTION}

Available datasets:

{context_str}

Conversation:

{history_str}

User Question:
<user_query>
{prompt}
</user_query>

IMPORTANT:
Return ONLY valid JSON.
Do NOT wrap the JSON inside ```.
If a SQL query is not required, return an empty string.

Never return:
N/A
NULL
None

{config.RESPONSE_FORMAT}

{config.RULES_INSTRUCTION}
"""

        response_text = cls.generate_content(prompt=full_prompt, temperature=0.4)
        logger.info(f"Gemini response obtained in {time.time() - start_time:.3f}s")

        # Save query to history
        chat_history.append(f"User: {prompt}")

        # Parse output JSON robustly
        try:
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            parsed_result = json.loads(cleaned_text)
            logger.info("Structured response successfully parsed from Gemini output.")
        except Exception as ex:
            logger.warning(f"Failed to parse model output as JSON. Raw output: {response_text}. Exception: {ex}")
            parsed_result = {
                "answer": response_text,
                "reasoning": "The model response did not conform to structured JSON schema.",
                "sql_query": "",
                "pandas_code": "",
                "chart_type": "",
                "confidence": 0.70
            }

        chat_history.append(f"Assistant: {parsed_result.get('answer', '')}")
        return parsed_result
