import pandas as pd
from typing import List

def generate_insights(df: pd.DataFrame) -> List[str]:
    """
    Generates automated business insights from a DataFrame using basic heuristics.
    
    Args:
        df (pd.DataFrame): Input DataFrame to generate insights for.
        
    Returns:
        List[str]: List of calculated insights and recommendations.
    """
    insights = []
    numeric_df = df.select_dtypes(include=['number'])
    
    if numeric_df.empty:
        return ["Not enough numeric data for automated insights."]

    # Basic KPI calculations
    total_rows = len(df)
    insights.append(f"### Executive Summary\n- Total Records: **{total_rows}**")
    
    # Analyze numeric columns
    for col in numeric_df.columns:
        mean_val = numeric_df[col].mean()
        max_val = numeric_df[col].max()
        min_val = numeric_df[col].min()
        
        insights.append(f"- **{col}**: Average: **{mean_val:.2f}**, Range: [{min_val:.2f}, {max_val:.2f}]")

    # Trend/Top performer analysis (heuristic-based)
    cat_cols = df.select_dtypes(include=['object', 'category']).columns
    for cat_col in cat_cols:
        if len(numeric_df.columns) > 0:
            num_col = numeric_df.columns[0]
            try:
                top_perf = df.groupby(cat_col)[num_col].sum().idxmax()
                insights.append(f"- **Top Performer ({cat_col})**: The category with the highest total {num_col} is **{top_perf}**.")
            except Exception:
                pass

    # Recommendations
    insights.append("### Recommendations")
    if df.isnull().values.any():
        insights.append("- **Data Quality**: The dataset contains missing values. Consider cleaning the data or imputing missing entries.")
    
    insights.append("- **Actionable Insight**: Based on the top performers identified, consider allocating more resources or marketing efforts to those high-performing categories.")

    return insights
