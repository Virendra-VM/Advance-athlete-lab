import pandas as pd
from fit2gpx import Converter


def fit_file_to_dataframes(fit_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert a .fit file into lap and point DataFrames for future activity processing."""
    converter = Converter()
    lap_df, point_df = converter.fit_to_dataframes(fname=fit_path)
    return lap_df, point_df
