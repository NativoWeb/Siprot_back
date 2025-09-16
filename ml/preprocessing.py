import pandas as pd
import re
from sklearn.preprocessing import MinMaxScaler
from typing import Optional, List

def load_file_flexible(file_path: str) -> pd.DataFrame:
    """Carga CSV o XLSX detectando delimitadores y limpiando datos."""
    if file_path.endswith(".csv"):
        try:
            df = pd.read_csv(
                file_path,
                sep=";",                 # Forzar punto y coma
                encoding="utf-8-sig"     # Quitar el BOM (ï»¿)
            )
        except Exception:
            # fallback: intentar con coma
            df = pd.read_csv(file_path, sep=",", encoding="utf-8-sig")
    elif file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Formato no soportado. Usa .csv o .xlsx")
    
    # 🔹 Limpiar comas decimales y porcentajes
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].str.replace(",", ".", regex=False)   # 80,5 → 80.5
            df[col] = df[col].str.replace("%", "", regex=False)    # 84,21% → 84.21
            # Intentar convertir a número si aplica
            try:
                df[col] = pd.to_numeric(df[col])
            except:
                pass
    
    return df

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

def clean_and_prepare_flexible(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara el DataFrame detectando automáticamente la columna de fecha."""
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
    
    return df

def scale_dataframe_safe(df: pd.DataFrame, scaler: MinMaxScaler) -> pd.DataFrame:
    """Escala el DataFrame de forma segura manejando errores."""
    try:
        scaled_values = scaler.transform(df)
        return pd.DataFrame(scaled_values, columns=df.columns, index=df.index)
    except Exception as e:
        print(f"⚠️ Error escalando datos: {e}")
        return (df - df.min()) / (df.max() - df.min())

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
