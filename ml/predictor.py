import numpy as np
import pandas as pd
from .loader import model, scalers
from .preprocessing import scale_dataframe_safe

WINDOW_SIZE = 5
PREDICT_YEARS = 10


def make_positive(array: np.ndarray) -> np.ndarray:
    """Convierte todos los valores negativos a positivos."""
    return np.abs(array)


def predict_future(df: pd.DataFrame, scalers_dict: dict = None):
    if scalers_dict is None:
        scalers_dict = scalers
    
    # Escalar datos columna por columna
    scaled_df = scale_dataframe_safe(df, scalers_dict)

    # Preparar última ventana
    last_sequence = scaled_df.iloc[-WINDOW_SIZE:].values
    last_sequence = np.expand_dims(last_sequence, axis=0)

    # Predecir
    predicted_scaled = model.predict(last_sequence)
    predicted_scaled = predicted_scaled.reshape(PREDICT_YEARS, scaled_df.shape[1])

    # 🔹 Invertir escalado por columna
    predicted = np.zeros_like(predicted_scaled)
    for j, col in enumerate(df.columns):
        scaler = scalers_dict[col]
        predicted[:, j] = scaler.inverse_transform(predicted_scaled[:, j].reshape(-1, 1)).ravel()

    # Convertir a positivos
    predicted = make_positive(predicted)

    # Datos históricos
    historical = []
    for i, year in enumerate(df.index):
        historical.append({
            "year": int(year),
            "values": {col: float(df.iloc[i][col]) for col in df.columns}
        })

    # Datos futuros
    last_year = int(df.index[-1])
    future_years = [last_year + i for i in range(1, PREDICT_YEARS + 1)]
    future = []
    for i, year in enumerate(future_years):
        future.append({
            "year": year,
            "values": {col: float(predicted[i][j]) for j, col in enumerate(df.columns)}
        })

    return historical + future
