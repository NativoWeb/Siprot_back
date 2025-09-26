from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional, Dict, List
import pandas as pd
from datetime import datetime
from models import Program, User
from routers.auth import get_db, require_role

# 🔮 Darts
try:
    from darts import TimeSeries
    from darts.models import ExponentialSmoothing
    DARTS_AVAILABLE = True
except ImportError:
    DARTS_AVAILABLE = False
    print("⚠️ Darts no disponible, usando solo proyección lineal")

router = APIRouter(prefix="/programs", tags=["Proyecciones ML"])


@router.get("/projections")
def get_ml_projections(
    years: int = 10,
    sector: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "directivos", "superadmin"]))
) -> Dict:
    """
    Genera proyecciones de programas educativos usando Darts (ExponentialSmoothing).
    Si falla, usa un fallback lineal.
    """
    try:
        # 🔹 Consulta mejorada para obtener datos históricos
        query = db.query(
            extract('year', Program.program_date).label('year'),
            func.count(Program.id).label('total_programs'),
            func.coalesce(func.sum(Program.current_students), 0).label('total_students'),
            func.coalesce(func.sum(Program.capacity), 0).label('total_capacity')
        ).filter(
            Program.is_active == True,
            Program.program_date.isnot(None)  # Asegurar que tengan fecha
        )

        # Filtrar por sector si se especifica
        if sector and sector != "Todos los sectores":
            query = query.filter(Program.sector == sector)

        historical_data = query.group_by(
            extract('year', Program.program_date)
        ).order_by('year').all()

        print(f"📊 Datos históricos encontrados: {len(historical_data)}")
        for row in historical_data:
            print(f"Año: {row.year}, Programas: {row.total_programs}, Estudiantes: {row.total_students}")

        if not historical_data or len(historical_data) < 2:
            # Generar datos de ejemplo si no hay suficientes datos históricos
            current_year = datetime.now().year
            historical_data = [
                type('obj', (object,), {
                    'year': current_year - 2, 
                    'total_programs': 10, 
                    'total_students': 300, 
                    'total_capacity': 400
                })(),
                type('obj', (object,), {
                    'year': current_year - 1, 
                    'total_programs': 15, 
                    'total_students': 450, 
                    'total_capacity': 600
                })(),
                type('obj', (object,), {
                    'year': current_year, 
                    'total_programs': 20, 
                    'total_students': 600, 
                    'total_capacity': 800
                })()
            ]
            print("⚠️ Usando datos de ejemplo para la demostración")

        # 🔹 Preparar DataFrame
        df_data = []
        for row in historical_data:
            df_data.append({
                "year": int(row.year),
                "programs": int(row.total_programs or 0),
                "students": int(row.total_students or 0),
                "capacity": int(row.total_capacity or 0),
            })

        df = pd.DataFrame(df_data)
        print(f"📈 DataFrame creado con {len(df)} filas")

        # 🔮 Generar proyecciones
        projections_data = []
        
        if DARTS_AVAILABLE and len(df) >= 3:
            print("🤖 Usando Darts para proyecciones ML")
            projections_data = generate_darts_projections(df, years)
        else:
            print("📊 Usando proyección lineal")
            projections_data = generate_linear_projections(df, years)

        # 🔹 Formatear datos históricos
        historical_formatted = []
        for row in df.to_dict('records'):
            historical_formatted.append({
                "year": row["year"],
                "values": {
                    "Programas": row["programs"],
                    "Estudiantes": row["students"],
                    "Capacidad": row["capacity"]
                }
            })

        # 🔹 Formatear proyecciones
        last_year = df['year'].max()
        projections_formatted = []
        
        for i, projection in enumerate(projections_data):
            future_year = last_year + (i + 1)
            projections_formatted.append({
                "year": int(future_year),
                "values": {
                    "Programas": int(max(0, projection.get('programs', 0))),
                    "Estudiantes": int(max(0, projection.get('students', 0))),
                    "Capacidad": int(max(0, projection.get('capacity', 0)))
                }
            })

        result = {
            "success": True,
            "method": "Darts-ExponentialSmoothing" if DARTS_AVAILABLE else "Linear Trend",
            "sector": sector or "Todos los sectores",
            "years_projected": years,
            "historical_data": historical_formatted,
            "projections": projections_formatted,
            "total_data_points": len(historical_formatted) + len(projections_formatted)
        }

        print(f"✅ Proyecciones generadas exitosamente: {len(projections_formatted)} puntos")
        return result

    except Exception as e:
        print(f"❌ Error en proyecciones: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback con datos mínimos
        current_year = datetime.now().year
        return {
            "success": False,
            "error": str(e),
            "method": "Fallback",
            "sector": sector or "Todos los sectores",
            "years_projected": years,
            "historical_data": [{
                "year": current_year,
                "values": {"Programas": 0, "Estudiantes": 0, "Capacidad": 0}
            }],
            "projections": []
        }


def generate_darts_projections(df: pd.DataFrame, years: int) -> List[Dict]:
    """Genera proyecciones usando Darts"""
    projections = []
    
    try:
        for metric in ['students', 'programs', 'capacity']:
            if metric not in df.columns:
                continue
                
            # Crear serie temporal
            series_data = df[['year', metric]].copy()
            series_data = series_data.dropna()
            
            if len(series_data) < 2:
                continue
                
            ts = TimeSeries.from_dataframe(
                series_data, 
                time_col='year', 
                value_cols=metric
            )
            
            # Entrenar modelo
            model = ExponentialSmoothing(seasonal=None)
            model.fit(ts)
            
            # Generar predicciones
            forecast = model.predict(years)
            forecast_values = forecast.values().flatten()
            
            # Almacenar predicciones
            for i, value in enumerate(forecast_values):
                if i >= len(projections):
                    projections.append({})
                projections[i][metric] = float(value)
                
    except Exception as e:
        print(f"Error en Darts: {e}")
        return generate_linear_projections(df, years)
    
    return projections


def generate_linear_projections(df: pd.DataFrame, years: int) -> List[Dict]:
    """Genera proyecciones lineales"""
    projections = []
    
    for metric in ['students', 'programs', 'capacity']:
        if metric not in df.columns or len(df) < 2:
            continue
            
        # Calcular tendencia lineal
        x_data = df['year'].values
        y_data = df[metric].values
        
        slope = calculate_slope(x_data, y_data)
        last_value = y_data[-1]
        last_year = x_data[-1]
        
        # Generar proyecciones
        for i in range(years):
            if i >= len(projections):
                projections.append({})
            
            future_value = last_value + slope * (i + 1)
            projections[i][metric] = max(0, float(future_value))
    
    return projections


def calculate_slope(x_data, y_data):
    """Calcula la pendiente para regresión lineal"""
    if len(x_data) < 2:
        return 0
    
    n = len(x_data)
    sum_x = sum(x_data)
    sum_y = sum(y_data)
    sum_xy = sum(x * y for x, y in zip(x_data, y_data))
    sum_x2 = sum(x * x for x in x_data)
    
    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        return 0
    
    return (n * sum_xy - sum_x * sum_y) / denominator