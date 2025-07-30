import numpy as np
import pandas as pd
from .loader import model, scaler
from .preprocessing import scale_dataframe

WINDOW_SIZE = 1
PREDICT_YEARS = 11

def make_positive(array: np.ndarray) -> np.ndarray:
    """Convierte todos los valores negativos a positivos."""
    return np.abs(array)

def predict_future(df: pd.DataFrame):
    # Escalar datos
    scaled_df = scale_dataframe(df, scaler)

    # Preparar última ventana
    last_sequence = scaled_df.iloc[-WINDOW_SIZE:].values
    last_sequence = np.expand_dims(last_sequence, axis=0)

    # Predecir
    predicted_scaled = model.predict(last_sequence)
    predicted_scaled = predicted_scaled.reshape(PREDICT_YEARS, scaled_df.shape[1])
    predicted = scaler.inverse_transform(predicted_scaled)

    # Convertir a positivos
    predicted = make_positive(predicted)

    # Datos históricos
    historical = []
    for i, year in enumerate(df.index):
        historical.append({
            "year": int(year),
            "values": {
                col: int(round(df.iloc[i][col])) for col in df.columns
            }
        })

    # Datos futuros
    last_year = int(df.index[-1])
    future_years = [last_year + i for i in range(1, PREDICT_YEARS + 1)]

    future = []
    for i, year in enumerate(future_years):
        future.append({
            "year": year,
            "values": {
                col: int(round(predicted[i][j])) for j, col in enumerate(df.columns)
            }
        })

    return historical + future
