import plotly.express as px
import pandas as pd
from typing import Optional, Any

def generate_chart(df: pd.DataFrame, chart_type: Optional[str] = None, x: Optional[str] = None, y: Optional[str] = None, color: Optional[str] = None) -> Any:
    """
    Generates Plotly charts. Automatically chooses best chart type if type is None.
    
    Args:
        df (pd.DataFrame): Data input DataFrame.
        chart_type (Optional[str]): Selected type (Bar, Line, etc.)
        x (Optional[str]): X-axis column name.
        y (Optional[str]): Y-axis column name.
        color (Optional[str]): Color category column name.
        
    Returns:
        plotly.graph_objects.Figure on success.
    """
    
    # Simple auto-selection logic if chart_type is None
    if chart_type is None:
        numeric_cols = df.select_dtypes(include=['number']).columns
        cat_cols = df.select_dtypes(include=['object', 'category']).columns
        
        if len(numeric_cols) >= 2:
            chart_type = "Scatter"
            x, y = numeric_cols[0], numeric_cols[1]
        elif len(cat_cols) >= 1 and len(numeric_cols) >= 1:
            chart_type = "Bar"
            x, y = cat_cols[0], numeric_cols[0]
        else:
            chart_type = "Histogram"
            x = numeric_cols[0] if len(numeric_cols) > 0 else cat_cols[0]

    # Validate column presence
    if x not in df.columns:
        raise ValueError(f"⚠️ Column '{x}' not found in the dataset.")
    if y not in df.columns:
        raise ValueError(f"⚠️ Column '{y}' not found in the dataset.")

    # Rule: Bar chart cardinality limit
    if chart_type == "Bar" and x in df.columns:
        unique_x = df[x].nunique()
        if unique_x > 50:
            raise ValueError(
                f"⚠️ Bar Chart is not recommended because the X-axis '{x}' contains too many unique categories ({unique_x} > 50). "
                f"Plotting this would yield an unreadable chart with overlapping bars. Please select a Box plot or Histogram instead, or choose an X-axis column with fewer unique values."
            )

    # Detect data types
    x_is_num = pd.api.types.is_numeric_dtype(df[x])
    y_is_num = pd.api.types.is_numeric_dtype(df[y])

    # Validate relationships
    if x_is_num and y_is_num:
        # Numeric vs Numeric -> Scatter or Line
        allowed = ["Scatter", "Line", "Histogram"]
        if chart_type not in allowed:
            raise ValueError(
                f"⚠️ '{chart_type}' is unsuitable for a Numeric vs Numeric relationship (X: '{x}', Y: '{y}'). "
                f"Plotting this would create a misleading visualization. Please select a Scatter or Line chart instead."
            )
    elif not x_is_num and y_is_num:
        # Category vs Numeric -> Bar
        allowed = ["Bar", "Pie", "Box", "Histogram"]
        if chart_type not in allowed:
            raise ValueError(
                f"⚠️ '{chart_type}' is unsuitable for a Category vs Numeric relationship (X: '{x}', Y: '{y}'). "
                f"Plotting this would create a misleading visualization. Please select a Bar Chart instead."
            )
    elif x_is_num and not y_is_num:
        # Numeric vs Category -> Box or Histogram
        allowed = ["Box", "Histogram"]
        if chart_type not in allowed:
            raise ValueError(
                f"⚠️ '{chart_type}' is unsuitable for a Numeric vs Category relationship (X: '{x}', Y: '{y}'). "
                f"Plotting this would create a misleading visualization. Please select a Box Plot or Histogram instead."
            )
    else:
        # Category vs Category -> Bar (Count) or Histogram
        allowed = ["Bar", "Histogram"]
        if chart_type not in allowed:
            raise ValueError(
                f"⚠️ '{chart_type}' is unsuitable for a Category vs Category relationship (X: '{x}', Y: '{y}'). "
                f"Plotting this would create a misleading visualization. Please select a Bar (Count) or Histogram chart instead."
            )

    # Plot generation
    fig = None
    if chart_type == "Bar":
        fig = px.bar(df, x=x, y=y, color=color)
    elif chart_type == "Line":
        fig = px.line(df, x=x, y=y, color=color)
    elif chart_type == "Pie":
        fig = px.pie(df, names=x, values=y)
    elif chart_type == "Scatter":
        fig = px.scatter(df, x=x, y=y, color=color)
    elif chart_type == "Histogram":
        fig = px.histogram(df, x=x, color=color)
    elif chart_type == "Heatmap":
        fig = px.imshow(df.corr(numeric_only=True))
    elif chart_type == "Box":
        fig = px.box(df, x=x, y=y, color=color)
    elif chart_type == "Area":
        fig = px.area(df, x=x, y=y, color=color)

    if fig is not None:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#1E293B",  # matches var(--card-bg)
            plot_bgcolor="#1E293B",
            font=dict(color="#F8FAFC", family="Inter, -apple-system, sans-serif"),
            margin=dict(l=20, r=20, t=35, b=20),
            hovermode="closest",
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                bordercolor="rgba(0,0,0,0)"
            )
        )
        # Style axes
        if chart_type not in ["Heatmap", "Pie"]:
            fig.update_xaxes(
                gridcolor="#334155", 
                linecolor="#334155", 
                zerolinecolor="#334155",
                title_font=dict(color="#CBD5E1"),
                tickfont=dict(color="#94A3B8")
            )
            fig.update_yaxes(
                gridcolor="#334155", 
                linecolor="#334155", 
                zerolinecolor="#334155",
                title_font=dict(color="#CBD5E1"),
                tickfont=dict(color="#94A3B8")
            )

    return fig
