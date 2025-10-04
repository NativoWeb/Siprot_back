import pandas as pd
import re
import chardet
from sklearn.preprocessing import MinMaxScaler
from typing import Optional, List, Tuple, Dict


# ==============================
# 🔹 Detección de encoding
# ==============================
def detect_encoding(file_path: str) -> str:
    """Detecta el encoding del archivo usando chardet."""
    with open(file_path, "rb") as f:
        result = chardet.detect(f.read(100000))
    return result["encoding"] or "utf-8"


# ==============================
# 🔹 Carga flexible de CSV/XLSX
# ==============================
def load_file_flexible(file_path: str) -> pd.DataFrame:
    """Carga CSV o XLSX detectando delimitadores y limpiando datos."""
    if file_path.endswith(".csv"):
        encoding = detect_encoding(file_path)
        try:
            df = pd.read_csv(file_path, sep=";", encoding=encoding)
        except Exception:
            df = pd.read_csv(file_path, sep=",", encoding=encoding)
    elif file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Formato no soportado. Usa .csv o .xlsx")
    
    # 🔹 Limpiar comas decimales y porcentajes
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", ".", regex=False)  # 80,5 → 80.5
                .str.replace("%", "", regex=False)   # 84,21% → 84.21
            )
            try:
                df[col] = pd.to_numeric(df[col])
            except:
                pass
    
    return df


# ==============================
# 🔹 Detección de columna de fecha
# ==============================
def detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """Detecta automáticamente la columna de fecha en diferentes formatos."""
    date_patterns = [
        r'^fecha$', r'^date$', r'^año$', r'^year$', r'^periodo$', r'^period$',
        r'^tiempo$', r'^time$', r'^mes$', r'^month$', r'^dia$', r'^day$'
    ]
    
    for col in df.columns:
        col_lower = str(col).lower().strip()
        for pattern in date_patterns:
            if re.match(pattern, col_lower):
                return col
    
    for col in df.columns:
        try:
            pd.to_datetime(df[col].head(10), errors='raise')
            return col
        except:
            continue
    
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64']:
            values = df[col].dropna()
            if len(values) > 0:
                min_val, max_val = values.min(), values.max()
                if 1900 <= min_val <= 2100 and 1900 <= max_val <= 2100:
                    return col
    
    return None


# ==============================
# 🔹 Ajuste dinámico de ceros
# ==============================
def replace_zeros_dynamic(df, threshold=0.6):
    df = df.copy()
    for col in df.select_dtypes(include=['number']).columns:
        zero_ratio = (df[col] == 0).mean()
        if zero_ratio > threshold:
            # calcular media sin los ceros
            mean_val = df[col].replace(0, None).mean()
            fill_val = mean_val if not pd.isna(mean_val) else 1.0
            df[col] = df[col].replace(0, fill_val * 0.5)
    return df

# ==============================
# 🔹 Limpieza y separación de datos
# ==============================
def clean_and_prepare_flexible(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Prepara el DataFrame detectando la columna de fecha.
    Devuelve dos DataFrames: numérico para proyecciones y categórico (metadatos).
    """
    df.columns = df.columns.str.strip()
    date_col = detect_date_column(df)
    
    if date_col is None:
        raise ValueError("No se pudo detectar una columna de fecha válida en el archivo")
    
    if date_col != 'Fecha':
        df = df.rename(columns={date_col: 'Fecha'})
    
    try:
        df['Fecha'] = pd.to_numeric(df['Fecha'], errors='coerce')
    except:
        df['Fecha'] = pd.to_datetime(df['Fecha']).dt.year
    
    df.set_index("Fecha", inplace=True)
    df.sort_index(inplace=True)
    df = df[df.index.notna()]
    
    # 🔹 Separar numéricas y categóricas
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    meta_cols = df.select_dtypes(exclude=['number']).columns.tolist()
    
    df_numeric = df[numeric_cols].copy()
    df_numeric = replace_zeros_dynamic(df_numeric)  # ✅ Ajuste automático de ceros
    
    df_meta = df[meta_cols].copy()
    
    return df_numeric, df_meta


# ==============================
# 🔹 Escalado por columna
# ==============================
def fit_scalers(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, MinMaxScaler]]:
    """Escala cada columna con su propio MinMaxScaler."""
    scalers = {}
    scaled_data = {}
    for col in df.columns:
        scaler = MinMaxScaler()
        scaled_data[col] = scaler.fit_transform(df[[col]])
        scalers[col] = scaler
    scaled_df = pd.DataFrame(
        {col: scaled_data[col].ravel() for col in df.columns}, 
        index=df.index
    )
    return scaled_df, scalers


def scale_dataframe_safe(df: pd.DataFrame, scalers: Dict[str, MinMaxScaler]) -> pd.DataFrame:
    """Escala un DataFrame usando scalers por columna de forma segura."""
    scaled_data = {}
    for col in df.columns:
        if col in scalers:
            try:
                scaled_data[col] = scalers[col].transform(df[[col]]).ravel()
            except Exception as e:
                print(f"⚠️ Error escalando {col}: {e}")
                scaled_data[col] = (df[col] - df[col].min()) / (df[col].max() - df[col].min())
        else:
            scaled_data[col] = df[col]
    
    return pd.DataFrame(scaled_data, index=df.index)


# ==============================
# 🔹 Validación del CSV
# ==============================
def validate_csv_structure(df: pd.DataFrame) -> List[str]:
    """Valida la estructura del CSV y retorna sugerencias."""
    issues = []
    
    if df.empty:
        issues.append("El archivo está vacío")
    
    if len(df.columns) < 2:
        issues.append("Se necesitan al menos 2 columnas (fecha + datos)")
    
    date_col = detect_date_column(df)
    if date_col is None:
        issues.append("No se encontró una columna de fecha válida. Asegúrate de tener una columna con años o fechas.")
    
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) == 0:
        issues.append("No se encontraron columnas con datos numéricos para analizar")
    
    return issues
