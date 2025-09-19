import tensorflow as tf
from tensorflow import keras


# Cargar el modelo
model = keras.models.load_model("modelo_lstm_multi_output.h5")

# Mostrar resumen
model.summary()