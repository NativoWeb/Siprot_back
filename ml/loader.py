import joblib
from tensorflow import keras
from sklearn.preprocessing import MinMaxScaler

model = keras.models.load_model("modelo_lstm_multi_output.h5")
scaler: MinMaxScaler = joblib.load("minmax_scaler.pkl")
