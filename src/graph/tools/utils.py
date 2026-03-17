import numpy as np
import pandas as pd

def load_incidence_from_csv(
    csv_path: str,
    column: str = "0",
    start_date: str | None = None,
    end_date: str | None = None,
    rolling_window: int = 7,
) -> np.ndarray:
    """
    Load and preprocess incidence data from a CSV file.

    The CSV is expected to have a datetime index in its first column and a
    target incidence column (default: "0").
    """
    if rolling_window < 1:
        raise ValueError("rolling_window must be >= 1")

    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in CSV. Available columns: {list(df.columns)}")

    if start_date is not None:
        df = df[df.index >= start_date]
    if end_date is not None:
        df = df[df.index <= end_date]

    if df.empty:
        raise ValueError("No rows available after applying the requested date filter.")

    incidence = (
        df[column]
        .rolling(rolling_window, min_periods=1, center=False)
        .mean()
        .to_numpy(dtype=float)
    )

    return incidence