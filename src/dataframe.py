import pandas as pd
from typing import List, Optional
from zoneinfo import ZoneInfo

def group_and_pivot_metrics(
    df: pd.DataFrame,
    project_names: dict,
    metric_type: str = "word_count"
) -> pd.DataFrame:
    """Groups timestamps and pivots the DataFrame to have projects as columns.

    Args:
        df: The input DataFrame with a 'timestamp' column.
        project_names: A dictionary mapping project IDs to project names.
        metric_type: The metric to use for the pivot.

    Returns:
        A new DataFrame with a single timestamp column and each project's
        metric as a separate column.
    """
    if df.empty:
        return pd.DataFrame()

    # Create a copy to avoid modifying the original DataFrame
    df = df.copy()

    # Convert timestamps from UTC to German timezone
    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Europe/Berlin')

    # Round timestamps to the nearest minute for grouping
    # Handle DST transitions by inferring ambiguous times
    df['timestamp_rounded'] = df['timestamp'].dt.round('1min', ambiguous='infer', nonexistent='shift_forward')

    # Pivot the table
    pivot_df = df.pivot_table(
        index='timestamp_rounded',
        columns='project_id',
        values=metric_type
    )

    # Rename columns to project names
    pivot_df.rename(columns=project_names, inplace=True)

    # Forward-fill missing values to create continuous lines
    pivot_df.ffill(inplace=True)
    # Backward-fill to handle any remaining NaNs at the beginning
    pivot_df.bfill(inplace=True)

    return pivot_df