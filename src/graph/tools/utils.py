import numpy as np
import pandas as pd

def pad_single_digit_numbers(s) -> str:
    """
    Pad single-digit numbers in a string with a leading zero.

    Args:
        s (str): Input string.

    Returns:
        str: String with single-digit numbers padded with a leading zero.
    """
    s = str(s)  # ensure it's a string

    result = []
    i = 0
    n = len(s)

    while i < n:
        if s[i].isdigit():
            j = i
            while j < n and s[j].isdigit():
                j += 1
            number = s[i:j]

            if len(number) == 1:  # single-digit integer
                result.append("0" + number)
            else:
                result.append(number)

            i = j
        else:
            result.append(s[i])
            i += 1

    return "".join(result)

def swab_result_mapper(result_string):
    """
    Map a swab result string to a simplified code.

    Args:
        result_string (str): Swab result string.

    Returns:
        str: Simplified code ('p' for positive, 'n' for negative, 'i' for inconclusive).
    """
    if 'Positivo' in result_string:
        return 'p' # At least one positive -> Positive
    else:
        n_commas = result_string.count(',')
        n_negatives = result_string.count('Negativo')
        if n_commas == n_negatives - 1: 
            return 'n' # All negatives -> Negative
        return 'i' # At least one Inconclusive and no positive -> Inconclusive

def prepare_incidence_data(
        csv_path: str = 'data/Accessi in PS 2022-2026 con FLU - aggiornato al 8-03-2026.csv',
        output_path: str = 'data/daily_positives_flu.csv'
):
    """
    Prepare incidence data from a CSV file.

    Args:
        csv_path (str): Path to the input CSV file.
        output_path (str): Path to the output CSV file.

    Returns:
        str: Path to the output CSV file.
    """
    df = pd.read_csv(csv_path)
    df['FASCIA ETA'] = df['FASCIA ETA'].apply(lambda s : pad_single_digit_numbers(s))
    df.index = pd.to_datetime(df['D01_DATAORA_ACCETTAZIONE'])
    df = df.dropna(subset = ['ESITO TAMPONE'])
    unstacked = df.groupby([pd.Grouper(freq = 'D'), 'ESITO TAMPONE'])['Totali Accessi'].sum().unstack(0)
    unstacked.index = unstacked.index.map(swab_result_mapper)
    daily_positive_swabs = unstacked.loc['p'].sum()
    daily_positive_swabs.to_csv(output_path)

    return output_path

def load_incidence_from_csv(
    csv_path: str = 'data/Accessi in PS 2022-2026 con FLU - aggiornato al 8-03-2026.csv',
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
    data_path = prepare_incidence_data(csv_path)  # prepare the data and save to CSV if not already done

    if rolling_window < 1:
        raise ValueError("rolling_window must be >= 1")

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)

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