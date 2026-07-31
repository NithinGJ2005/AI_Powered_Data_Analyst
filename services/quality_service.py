import pandas as pd
import numpy as np
from utils import logger


class QualityService:
    @staticmethod
    def run_audit(df: pd.DataFrame) -> dict:
        """
        Executes a data quality audit on the supplied DataFrame.
        """
        start_rows = len(df)
        if start_rows == 0:
            return {
                "score": 0,
                "severity": "Critical",
                "warnings": ["Dataset is empty."],
                "duplicates": 0,
                "missing_total": 0,
                "empty_columns": [],
                "constant_columns": [],
                "high_cardinality_columns": [],
                "mixed_dtype_columns": [],
                "invalid_numeric_count": 0,
                "outlier_count": 0,
                "col_stats": {},
            }

        # 1. Missing & Duplicate row counts
        missing_total = int(df.isnull().sum().sum())
        dupes = int(df.duplicated().sum())

        # 2. Columns audits
        empty_cols = []
        constant_cols = []
        high_card_cols = []
        mixed_dtype_cols = []
        invalid_numeric_count = 0
        outlier_count = 0

        # Calculate IQR outliers for numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [c for c in numeric_cols if not str(c).startswith("Unnamed:")]

        for col in df.columns:
            # Empty column check
            if df[col].isnull().sum() == start_rows:
                empty_cols.append(col)
                continue

            # Constant column check
            if df[col].dropna().nunique() == 1:
                constant_cols.append(col)

            # High cardinality check (categorical columns where unique values are > 90% of rows)
            if not pd.api.types.is_numeric_dtype(df[col]):
                non_null_count = df[col].dropna().count()
                if non_null_count > 10:
                    unique_pct = df[col].dropna().nunique() / non_null_count
                    if unique_pct > 0.90:
                        # Exclude obvious IDs
                        col_l = str(col).lower()
                        if not (col_l == "id" or col_l.endswith("_id") or col_l.endswith("id")):
                            high_card_cols.append(col)

            # Mixed datatypes check
            types_set = df[col].dropna().apply(lambda x: type(x).__name__).unique()
            if len(types_set) > 1:
                mixed_dtype_cols.append(col)

            # Invalid numerics checks
            if pd.api.types.is_numeric_dtype(df[col]):
                inf_count = np.isinf(df[col]).sum()
                invalid_numeric_count += int(inf_count)

        # 3. Calculate numeric outliers (IQR)
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) > 4:
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = series[(series < lower) | (series > upper)]
                outlier_count += len(outliers)

        # 4. Generate Correlation Matrix (standard Pearson on numeric cols)
        correlation_matrix = {}
        if len(numeric_cols) > 1:
            try:
                corr = df[numeric_cols].corr().fillna(0.0).to_dict()
                correlation_matrix = corr
            except Exception as e:
                logger.error(f"Correlation calculation failed: {e}")

        # 5. Column descriptive statistics
        col_stats = {}
        try:
            col_stats = df.describe(include="all").fillna("—").to_dict()
        except Exception:
            pass

        # 6. Overall Quality Score computation
        score = 100
        # Deductions
        if dupes > 0:
            score -= 10
        if empty_cols:
            score -= 5 * len(empty_cols)
        if constant_cols:
            score -= 3 * len(constant_cols)
        if mixed_dtype_cols:
            score -= 5 * len(mixed_dtype_cols)
        if high_card_cols:
            score -= 3 * len(high_card_cols)
        if invalid_numeric_count > 0:
            score -= 10

        # Missing values percentage deduction
        total_cells = start_rows * len(df.columns)
        if total_cells > 0:
            missing_pct = missing_total / total_cells
            score -= int(missing_pct * 30)

        # Outlier counts deduction
        if outlier_count > 0:
            score -= min(10, int(outlier_count / start_rows * 5))

        score = max(0, min(100, score))
        severity = "High (Good)" if score >= 85 else ("Medium" if score >= 60 else "Low (Critical)")

        # Compile warnings list
        warnings = []
        if dupes > 0:
            warnings.append(f"Contains {dupes:,} duplicate rows.")
        if empty_cols:
            warnings.append(f"Found {len(empty_cols)} completely empty columns.")
        if constant_cols:
            warnings.append(f"Found {len(constant_cols)} constant value columns.")
        if mixed_dtype_cols:
            warnings.append(f"Mixed datatypes detected in columns: {mixed_dtype_cols}.")
        if high_card_cols:
            warnings.append(f"High cardinality categories detected in columns: {high_card_cols}.")
        if invalid_numeric_count > 0:
            warnings.append(f"Detected {invalid_numeric_count} infinite numeric values.")

        return {
            "score": score,
            "severity": severity,
            "warnings": warnings,
            "duplicates": dupes,
            "missing_total": missing_total,
            "empty_columns": empty_cols,
            "constant_columns": constant_cols,
            "high_cardinality_columns": high_card_cols,
            "mixed_dtype_columns": mixed_dtype_cols,
            "invalid_numeric_count": invalid_numeric_count,
            "outlier_count": outlier_count,
            "correlation_matrix": correlation_matrix,
            "col_stats": col_stats,
        }
