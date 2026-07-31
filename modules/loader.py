import pandas as pd
import chardet
import io
import streamlit as st
from utils import logger

@st.cache_data
def load_csv_from_bytes(file_bytes: bytes, filename: str) -> dict:
    """
    Loads, validates, and performs initial analysis on CSV bytes.
    Returns a dictionary containing the DataFrame and metadata if successful.
    """
    logger.info(f"Loading and parsing dataset: {filename} ({len(file_bytes)} bytes)...")
    try:
        # 1. Detect Encoding
        sample = file_bytes[:50000]
        result = chardet.detect(sample)
        encoding = result.get('encoding') or 'utf-8'

        # 2. Check for duplicate columns in raw header line before pandas renames them
        try:
            first_line = file_bytes.split(b'\n')[0].decode(encoding).strip()
            import csv
            headers = next(csv.reader([first_line]))
            if len(headers) != len(set(headers)):
                seen = set()
                dups = []
                for h in headers:
                    if h in seen:
                        dups.append(h)
                    seen.add(h)
                logger.warning(f"File {filename} has duplicate columns: {dups}")
                return {"error": f"Duplicate columns found: {dups}"}
        except Exception as he:
            logger.warning(f"Header duplicate detection check bypassed: {he}")

        # 3. Read CSV
        df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding)

        # 4. Validation
        if df.empty:
            logger.warning(f"File {filename} is empty.")
            return {"error": "The CSV file is empty."}

        # 4. Statistics and Data Quality Report
        stats = df.describe(include='all').to_dict()
        missing_values = df.isnull().sum().to_dict()
        dtypes = df.dtypes.astype(str).to_dict()

        logger.info(f"Dataset {filename} parsed successfully. Shape: {df.shape}")
        return {
            "df": df,
            "columns": df.columns.tolist(),
            "shape": df.shape,
            "dtypes": dtypes,
            "stats": stats,
            "missing_values": missing_values,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error loading CSV {filename}: {e}", exc_info=True)
        return {"error": str(e)}

def load_csv(file):
    """
    Public wrapper preserving the original load_csv interface.
    """
    file_bytes = file.read()
    file.seek(0)
    return load_csv_from_bytes(file_bytes, file.name)
