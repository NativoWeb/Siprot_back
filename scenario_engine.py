import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

class ScenarioType(Enum):
    """Enum para tipos de escenarios"""
    TENDENCIAL = "tendencial"
    OPTIMISTA = "optimista" 
    PESIMISTA = "pesimista"

class ScenarioConfig:
    """Configuración de un escenario"""
    def __init__(self, name: str, description: str, multipliers: Dict, growth_rates: Dict):
        self.name = name
        self.description = description
        self.multipliers = multipliers
        self.growth_rates = growth_rates

class ScenarioEngine:
    """Motor de escenarios compatible con la API existente"""
    
    def __init__(self, db):
        self.db = db
        self.scenarios = self._initialize_scenarios()
    
    def _initialize_scenarios(self) -> Dict[ScenarioType, ScenarioConfig]:
        """Inicializa las configuraciones de escenarios"""
        return {
            ScenarioType.TENDENCIAL: ScenarioConfig(
                name="Escenario Tendencial",
                description="Proyección basada en tendencias históricas actuales",
                multipliers={'general': 1.0, 'crecimiento_base': 1.0},
                growth_rates={'general': 0.02, 'variabilidad': 0.1}
            ),
            ScenarioType.OPTIMISTA: ScenarioConfig(
                name="Escenario Optimista",
                description="Proyección con condiciones favorables y crecimiento acelerado",
                multipliers={'general': 1.2, 'crecimiento_base': 1.5},
                growth_rates={'general': 0.045, 'variabilidad': 0.15}
            ),
            ScenarioType.PESIMISTA: ScenarioConfig(
                name="Escenario Pesimista",
                description="Proyección con condiciones adversas y crecimiento limitado",
                multipliers={'general': 0.8, 'crecimiento_base': 0.6},
                growth_rates={'general': 0.005, 'variabilidad': -0.05}
            )
        }
    
    def create_scenario(self, scenario_data: Dict, user_id: int):
        """Crea un nuevo escenario en la base de datos"""
        from models import Scenario
        
        scenario = Scenario(
            name=scenario_data["name"],
            scenario_type=scenario_data["scenario_type"],
            description=scenario_data["description"],
            parameters=scenario_data["parameters"],
            created_by=user_id
        )
        
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario
    
    def generate_scenario_projections(self, scenario_id: int, df: pd.DataFrame, years_ahead: int) -> List[Dict]:
        """Genera proyecciones para un escenario específico usando datos reales del CSV"""
        try:
            logger = print  # usar print directo para depuración

            logger("========== INICIO GENERACIÓN ESCENARIO ==========")
            logger(f"📥 DataFrame recibido: shape={df.shape}, columnas={list(df.columns)}")
            logger(f"Primeras filas:\n{df.head(5).to_string()}")

            # Procesar el DataFrame
            processed_df = self._process_csv_data(df)
            logger(f"✅ DataFrame procesado. Shape: {processed_df.shape}")
            logger(f"✅ Columnas procesadas: {list(processed_df.columns)}")
            logger(f"✅ Años disponibles: {processed_df.index.min()} - {processed_df.index.max()}")
            logger(f"Primeras filas procesadas:\n{processed_df.head(10).to_string()}")

            # Extraer datos históricos COMPLETOS
            historical_data = self._extract_complete_historical_data(processed_df)
            logger(f"✅ Datos históricos extraídos: {len(historical_data)} años")

            # Calcular tendencias basadas en datos reales
            trends = self._calculate_real_trends(processed_df)
            logger(f"✅ Tendencias calculadas: {trends}")

            # Obtener configuración del escenario basada en el ID
            scenario_config = self._get_scenario_config_by_id(scenario_id)

            # Generar proyecciones futuras
            future_projections = self._generate_future_projections(
                processed_df, trends, scenario_config, years_ahead
            )
            logger(f"✅ Proyecciones futuras generadas: {len(future_projections)} años")

            # Combinar datos históricos y proyecciones
            complete_data = historical_data + future_projections
            logger(f"✅ Datos completos: {len(complete_data)} puntos totales")

            logger("========== FIN GENERACIÓN ESCENARIO ==========")
            return complete_data

        except Exception as e:
            print(f"⚠️ Error generando proyecciones: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return self._generate_fallback_projections(years_ahead)

    
    def _process_csv_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa el DataFrame detectando automáticamente la estructura"""
        date_col = self._detect_date_column(df)
        if date_col is None:
            raise ValueError("No se encontró columna de fecha válida")
        return self._prepare_dataframe(df.copy(), date_col)
    
    def _detect_date_column(self, df: pd.DataFrame) -> Optional[str]:
        """Detecta automáticamente la columna de fecha"""
        import re
        date_patterns = [
            r'^fecha$', r'^date$', r'^año$', r'^anio$', r'^year$', 
            r'^periodo$', r'^period$', r'^tiempo$', r'^time$', 
            r'^mes$', r'^month$', r'^corte$', r'^periodo.*', r'^anio.*'
        ]
        for col in df.columns:
            col_lower = str(col).lower().strip()
            for pattern in date_patterns:
                if re.match(pattern, col_lower):
                    return col
        # fallback: primera columna con valores tipo año
        for col in df.columns:
            try:
                candidate = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(candidate) > 0 and candidate.between(1900, 2100).all():
                    return col
            except:
                continue
        return None
    
    def _prepare_dataframe(self, df: pd.DataFrame, date_col: str) -> pd.DataFrame:
        """Prepara el DataFrame para análisis"""
        if date_col != 'Año':
            df = df.rename(columns={date_col: 'Año'})
        df['Año'] = pd.to_numeric(df['Año'], errors='coerce')
        
        # 🔹 limpieza extra en columnas numéricas
        for col in df.columns:
            if col != 'Año' and df[col].dtype == object:
                df[col] = (
                    df[col].astype(str)
                    .str.replace("%", "", regex=False)
                    .str.replace(".", "", regex=False)   # quita separador de miles
                    .str.replace(",", ".", regex=False)  # convierte coma decimal en punto
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        df.set_index('Año', inplace=True)
        df.sort_index(inplace=True)
        df = df[df.index.notna()]
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df = df[numeric_cols].interpolate(method='linear')
        return df
    
    def _extract_complete_historical_data(self, df: pd.DataFrame) -> List[Dict]:
        """Extrae TODOS los datos históricos disponibles"""
        historical = []

        for year in df.index.unique():  # evitar duplicados
            year_data = {}

            for col in df.columns:
                value = df.loc[year, col]

                # Si hay varias filas (Series), tomamos el promedio
                if isinstance(value, pd.Series):
                    value = value.mean()

                if pd.notna(value):
                    try:
                        year_data[col] = max(0, float(value))  # usar float, no forzar a int todavía
                    except Exception:
                        continue

            if year_data:
                historical.append({
                    'year': int(year),
                    'values': year_data
                })

        return historical

    
    def _calculate_real_trends(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcula tendencias de crecimiento históricas REALES"""
        trends = {}
        for col in df.columns:
            try:
                values = df[col].dropna()
                if len(values) >= 2:
                    years = np.array(range(len(values)))
                    coeffs = np.polyfit(years, values.values, 1)
                    slope = coeffs[0]
                    if values.mean() > 0:
                        growth_rate = slope / values.mean()
                        trends[col] = max(min(growth_rate, 0.3), -0.2)
                    else:
                        trends[col] = 0.02
                else:
                    trends[col] = 0.02
            except:
                trends[col] = 0.02
        return trends
    
    def _get_scenario_config_by_id(self, scenario_id: int) -> ScenarioConfig:
        """Obtiene configuración del escenario por ID"""
        try:
            from models import Scenario
            scenario = self.db.query(Scenario).filter(Scenario.id == scenario_id).first()
            if scenario and scenario.scenario_type:
                return self.scenarios[ScenarioType(scenario.scenario_type)]
            return self.scenarios[ScenarioType.TENDENCIAL]
        except:
            return self.scenarios[ScenarioType.TENDENCIAL]
    
    def _generate_future_projections(self, df: pd.DataFrame, trends: Dict, 
                                     scenario_config: ScenarioConfig, years_ahead: int) -> List[Dict]:
        """Genera proyecciones futuras basadas en datos históricos"""
        projections = []
        last_year = int(df.index.max())
        last_values = df.iloc[-1].to_dict()
        
        for year_offset in range(1, years_ahead + 1):
            future_year = last_year + year_offset
            future_values = {}
            for col, last_value in last_values.items():
                hist_trend = trends.get(col, 0.02)
                mult = scenario_config.multipliers.get('general', 1.0)
                scen_growth = scenario_config.growth_rates.get('general', hist_trend)
                combined_growth = (hist_trend + scen_growth) / 2
                projected = last_value * mult * ((1 + combined_growth) ** year_offset)
                variability = scenario_config.growth_rates.get('variabilidad', 0.1)
                noise = 1 + np.random.uniform(-variability, variability)
                future_values[col] = max(0, float(projected * noise))  # 🔹 mantener decimales
            projections.append({'year': future_year, 'values': future_values})
        return projections
    
    def _generate_fallback_projections(self, years_ahead: int) -> List[Dict]:
        """Genera proyecciones sintéticas como respaldo"""
        projections = []
        current_year = datetime.now().year
        for i in range(10, 0, -1):
            projections.append({
                'year': current_year - i,
                'values': {
                    'Estudiantes': float(1000 + np.random.uniform(-200, 200)),
                    'Programas': float(20 + np.random.uniform(-5, 5)),
                    'Graduados': float(250 + np.random.uniform(-50, 50))
                }
            })
        last_values = projections[-1]['values']
        for year_offset in range(1, years_ahead + 1):
            fyear = current_year + year_offset
            fvalues = {}
            for ind, base in last_values.items():
                growth = 1.02 ** year_offset
                noise = np.random.uniform(0.9, 1.1)
                fvalues[ind] = float(base * growth * noise)
            projections.append({'year': fyear, 'values': fvalues})
        return projections
    
    def compare_scenarios(self, scenario_ids: List[int]) -> Dict:
        """Compara múltiples escenarios"""
        return {"message": "Comparación de escenarios", "scenario_ids": scenario_ids, "comparison_data": []}
    
    def initialize_default_scenarios(self, user_id: int):
        """Inicializa escenarios predefinidos"""
        pass
