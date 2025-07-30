import pandas as pd
from sklearn.preprocessing import MinMaxScaler

def clean_and_prepare(df: pd.DataFrame):
    df.columns = df.columns.str.strip()
    df.set_index("Fecha", inplace=True)
    df.sort_index(inplace=True)
    return df

def scale_dataframe(df: pd.DataFrame, scaler: MinMaxScaler) -> pd.DataFrame:
    scaled_values = scaler.transform(df)
    return pd.DataFrame(scaled_values, columns=df.columns, index=df.index)