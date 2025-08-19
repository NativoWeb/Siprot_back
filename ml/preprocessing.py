import pandas as pd
import re
from sklearn.preprocessing import MinMaxScaler
from typing import Optional, List

def detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """Detecta automáticamente la columna de fecha en diferentes formatos."""
    
    # Patrones comunes para columnas de fecha
    date_patterns = [
        r'^fecha$', r'^date$', r'^año$', r'^year$', r'^periodo$', r'^period$',
        r'^tiempo$', r'^time$', r'^mes$', r'^month$', r'^dia$', r'^day$'
    ]
    
    # Buscar por nombre de columna
    for col in df.columns:
        col_lower = str(col).lower().strip()
        for pattern in date_patterns:
            if re.match(pattern, col_lower):
                return col
    
    # Buscar por tipo de datos que parezcan fechas
    for col in df.columns:
        try:
            # Intentar convertir a datetime
            pd.to_datetime(df[col].head(10), errors='raise')
            return col
        except:
            continue
    
    # Buscar columnas numéricas que parezcan años
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64']:
            values = df[col].dropna()
            if len(values) > 0:
                min_val, max_val = values.min(), values.max()
                # Si parece un rango de años (1900-2100)
                if 1900 <= min_val <= 2100 and 1900 <= max_val <= 2100:
                    return col
    
    return None

def clean_and_prepare_flexible(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara el DataFrame detectando automáticamente la columna de fecha."""
    
    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()
    
    # Detectar columna de fecha
    date_col = detect_date_column(df)
    
    if date_col is None:
        raise ValueError("No se pudo detectar una columna de fecha válida en el archivo")
    
    # Convertir la columna de fecha a índice
    if date_col != 'Fecha':
        df = df.rename(columns={date_col: 'Fecha'})
    
    # Asegurar que la fecha sea numérica (años)
    try:
        df['Fecha'] = pd.to_numeric(df['Fecha'], errors='coerce')
    except:
        # Si es datetime, extraer el año
        df['Fecha'] = pd.to_datetime(df['Fecha']).dt.year
    
    # Establecer como índice y ordenar
    df.set_index("Fecha", inplace=True)
    df.sort_index(inplace=True)
    
    # Eliminar filas con valores nulos en el índice
    df = df[df.index.notna()]
    
    return df

def scale_dataframe_safe(df: pd.DataFrame, scaler: MinMaxScaler) -> pd.DataFrame:
    """Escala el DataFrame de forma segura manejando errores."""
    try:
        scaled_values = scaler.transform(df)
        return pd.DataFrame(scaled_values, columns=df.columns, index=df.index)
    except Exception as e:
        print(f"⚠️ Error escalando datos: {e}")
        # Retornar DataFrame original normalizado manualmente
        return (df - df.min()) / (df.max() - df.min())

def validate_csv_structure(df: pd.DataFrame) -> List[str]:
    """Valida la estructura del CSV y retorna sugerencias."""
    issues = []
    
    if df.empty:
        issues.append("El archivo está vacío")
    
    if len(df.columns) < 2:
        issues.append("Se necesitan al least 2 columnas (fecha + datos)")
    
    date_col = detect_date_column(df)
    if date_col is None:
        issues.append("No se encontró una columna de fecha válida. Asegúrate de tener una columna con años o fechas.")
    
    # Verificar datos numéricos
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) == 0:
        issues.append("No se encontraron columnas con datos numéricos para analizar")
    
    return issues
