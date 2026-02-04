"""Analyzer node for statistical analysis."""
import logging
from typing import Dict, Any, List
import pandas as pd
import numpy as np

from app.services.agents.summary.state import SummaryAgentState
from app.services.metrics import track_node_execution

logger = logging.getLogger(__name__)


def _convert_to_numeric(value: Any) -> float:
    """Convert value to numeric, handling various formats."""
    if value is None:
        return np.nan
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Try to parse string numbers
        try:
            # Remove common formatting (commas, currency symbols, etc.)
            cleaned = value.replace(",", "").replace("$", "").replace("%", "").strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return np.nan
    return np.nan


@track_node_execution("summary", "analyzer")
async def analyze_data_node(state: SummaryAgentState) -> Dict[str, Any]:
    """
    Perform statistical analysis on view data.
    
    This is a "Reason" step in ReAct - analyze patterns and trends.
    """
    try:
        view_data = state.get("view_data")
        
        if not view_data:
            return {
                **state,
                "error": "No view data available for analysis",
                "column_stats": None,
                "trends": [],
                "outliers": [],
                "correlations": None
            }
        
        data_rows = view_data.get("data", [])
        columns = view_data.get("columns", [])
        
        if not data_rows or not columns:
            return {
                **state,
                "error": "View data is empty",
                "column_stats": None,
                "trends": [],
                "outliers": [],
                "correlations": None
            }
        
        # Convert to pandas DataFrame
        try:
            df = pd.DataFrame(data_rows, columns=columns)
        except Exception as e:
            logger.error(f"Error creating DataFrame: {e}")
            return {
                **state,
                "error": f"Failed to process data: {str(e)}",
                "column_stats": None,
                "trends": [],
                "outliers": [],
                "correlations": None
            }
        
        # Convert columns to numeric where possible
        for col in df.columns:
            df[col] = df[col].apply(_convert_to_numeric)
        
        # Calculate statistics for numeric columns
        column_stats = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                column_stats[col] = {
                    "mean": float(col_data.mean()) if not col_data.empty else None,
                    "median": float(col_data.median()) if not col_data.empty else None,
                    "std": float(col_data.std()) if len(col_data) > 1 else None,
                    "min": float(col_data.min()) if not col_data.empty else None,
                    "max": float(col_data.max()) if not col_data.empty else None,
                    "missing": int(df[col].isna().sum()),
                    "count": int(len(col_data))
                }
        
        # Detect trends (check for monotonic patterns)
        trends = []
        for col in numeric_cols:
            col_data = df[col].dropna()
            if len(col_data) > 2:
                # Check for monotonic increase/decrease
                if col_data.is_monotonic_increasing:
                    trends.append({
                        "column": col,
                        "trend": "increasing",
                        "description": f"{col} shows a consistent increasing trend"
                    })
                elif col_data.is_monotonic_decreasing:
                    trends.append({
                        "column": col,
                        "trend": "decreasing",
                        "description": f"{col} shows a consistent decreasing trend"
                    })
                else:
                    # Check for overall trend using linear regression
                    try:
                        x = np.arange(len(col_data))
                        slope = np.polyfit(x, col_data.values, 1)[0]
                        if abs(slope) > 0.01:  # Significant slope
                            trends.append({
                                "column": col,
                                "trend": "increasing" if slope > 0 else "decreasing",
                                "description": f"{col} shows an overall {'increasing' if slope > 0 else 'decreasing'} trend",
                                "slope": float(slope)
                            })
                    except Exception:
                        pass
        
        # Detect outliers using IQR method
        outliers = []
        for col in numeric_cols:
            col_data = df[col].dropna()
            if len(col_data) > 4:  # Need at least 4 points for IQR
                Q1 = col_data.quantile(0.25)
                Q3 = col_data.quantile(0.75)
                IQR = Q3 - Q1
                
                if IQR > 0:  # Avoid division by zero
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    outlier_mask = (col_data < lower_bound) | (col_data > upper_bound)
                    
                    if outlier_mask.any():
                        outlier_values = col_data[outlier_mask].tolist()
                        outliers.append({
                            "column": col,
                            "count": int(outlier_mask.sum()),
                            "percentage": float(outlier_mask.sum() / len(col_data) * 100),
                            "lower_bound": float(lower_bound),
                            "upper_bound": float(upper_bound),
                            "sample_values": [float(v) for v in outlier_values[:5]]  # Sample of outlier values
                        })
        
        # Calculate correlations between numeric columns
        correlations = None
        if len(numeric_cols) > 1:
            try:
                corr_matrix = df[numeric_cols].corr()
                # Convert to dict format (only strong correlations > 0.5 or < -0.5)
                correlations = {}
                for col1 in numeric_cols:
                    for col2 in numeric_cols:
                        if col1 != col2:
                            corr_value = corr_matrix.loc[col1, col2]
                            if abs(corr_value) > 0.5:
                                if col1 not in correlations:
                                    correlations[col1] = {}
                                correlations[col1][col2] = float(corr_value)
            except Exception as e:
                logger.warning(f"Error calculating correlations: {e}")
                correlations = {}
        
        return {
            **state,
            "column_stats": column_stats,
            "trends": trends,
            "outliers": outliers,
            "correlations": correlations,
            "current_thought": f"Analyzed {len(numeric_cols)} numeric columns, found {len(trends)} trends and {len(outliers)} columns with outliers"
        }
    except Exception as e:
        logger.error(f"Error in analyzer node: {e}", exc_info=True)
        return {
            **state,
            "error": f"Failed to analyze data: {str(e)}",
            "column_stats": None,
            "trends": [],
            "outliers": [],
            "correlations": None
        }
