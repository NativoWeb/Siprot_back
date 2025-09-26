import joblib
from tensorflow import keras
from sklearn.preprocessing import MinMaxScaler

model = keras.models.load_model("modelo_lstm_multi_output.h5")
base_scaler: MinMaxScaler = joblib.load("minmax_scaler.pkl")

# Create scalers dictionary for compatibility with predictor
scalers = {
    'Programas': base_scaler,
    'Estudiantes': base_scaler, 
    'Capacidad': base_scaler
}
