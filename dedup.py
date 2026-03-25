import pandas as pd

def deduplicar(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicatas exatas de agente + início + fim + estado."""
    if df.empty:
        return df
    return df.drop_duplicates(
        subset=["agente", "inicio", "fim", "estado"]
    ).reset_index(drop=True)
