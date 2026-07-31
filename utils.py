import os
import logging
from logging.handlers import RotatingFileHandler
import config

# Ensure logs directory exists
os.makedirs(config.LOG_DIR, exist_ok=True)

# Centralized Logger setup
def get_logger(name=__name__):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s'
        )
        # Rotating File Handler (Max 5MB per log, backup count 3)
        file_handler = RotatingFileHandler(
            config.LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger

logger = get_logger("app_logger")


def sanitize_table_name(filename: str) -> str:
    """
    Sanitizes a filename into a standard SQL table identifier.
    """
    return (
        filename.replace(".csv", "")
        .replace(" ", "_")
        .replace("-", "_")
    )


def format_summary(text):
    """
    Cleans and formats model summary answer text.
    """
    if not text:
        return "No answer generated."
    formatted = text.strip()
    if formatted.startswith("### 📋 Summary") or formatted.startswith("### 📌 Summary"):
        return formatted
    return formatted


def format_paragraphs_to_bullets(text):
    """
    Converts long paragraph blocks into formatted bullet lists.
    """
    if not text:
        return "No reasoning provided."
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        formatted_paras = []
        for p in paragraphs:
            if p.startswith(("- ", "* ", "1. ")):
                formatted_paras.append(p)
            else:
                formatted_paras.append(f"- {p}")
        return "\n".join(formatted_paras)
    return text


def safe_dataframe_to_markdown(df) -> str:
    """
    Renders a DataFrame as a markdown table when the optional 'tabulate'
    package is available, and gracefully falls back to a plain-text
    representation when it is not installed.

    This prevents ImportError from crashing the application in environments
    where tabulate has not been installed.

    Args:
        df: A pandas DataFrame to render.

    Returns:
        A string containing either a markdown table or a plain-text table.
    """
    try:
        return df.to_markdown(index=False)
    except ImportError:
        logger.warning(
            "'tabulate' is not installed; falling back to DataFrame.to_string(). "
            "Install it with: pip install tabulate"
        )
        return df.to_string(index=False)
