import pandas as pd
from typing import List

def validate_csv(df: pd.DataFrame) -> List[str]:
    """
    Validates a pandas DataFrame for common dataset quality issues.
    
    Args:
        df (pd.DataFrame): Input DataFrame to validate.
        
    Returns:
        List[str]: List of identified data quality issues.
    """
    issues = []
    if df.isnull().values.any():
        issues.append(f"Missing values found: {df.isnull().sum().sum()}")
    if df.duplicated().any():
        issues.append(f"Duplicate rows found: {df.duplicated().sum()}")
    return issues
