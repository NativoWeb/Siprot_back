import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class ScenarioType(Enum):
    """Enum para tipos de escenarios"""
    TENDENCIAL = "tendencial"
    OPTIMISTA = "optimista" 
    PESIMISTA = "pesimista"


class ScenarioConfig:
    """Configuracion de un escenario"""
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
                description="Proyeccion basada en tendencias historicas actuales",
                multipliers={'general': 1.0, 'crecimiento_base': 1.0},
                growth_rates={'general': 0.02, 'variabilidad': 0.1}
            ),
            ScenarioType.OPTIMISTA: ScenarioConfig(
                name="Escenario Optimista",
                description="Proyeccion con condiciones favorables y crecimiento acelerado",
                multipliers={'general': 1.2, 'crecimiento_base': 1.5},
                growth_rates={'general': 0.045, 'variabilidad': 0.15}
            ),
            ScenarioType.PESIMISTA: ScenarioConfig(
                name="Escenario Pesimista",
                description="Proyeccion con condiciones adversas y crecimiento limitado",
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
    
    def generate_scenario_projections(
        self,
        scenario_id: int,
        df: pd.DataFrame,
        years_ahead: int,
        custom_params: Optional[Dict] = None
    ) -> List[Dict]:
        """Genera proyecciones para un escenario especifico usando datos reales del CSV"""
        try:
            logger.info("=" * 60)
            logger.info("INICIO GENERACION ESCENARIO")
            logger.info(f"Escenario ID: {scenario_id}")
            logger.info(f"DataFrame shape: {df.shape}")
            logger.info(f"Años a proyectar: {years_ahead}")
            logger.info(f"Parametros personalizados: {custom_params}")
            logger.info("=" * 60)

            # Procesar el DataFrame
            processed_df = self._process_csv_data(df)
            logger.info(f"DataFrame procesado - Shape: {processed_df.shape}")
            logger.info(f"Columnas: {list(processed_df.columns)}")
            logger.info(f"Rango años: {processed_df.index.min()} - {processed_df.index.max()}")

            # Extraer datos historicos
            historical_data = self._extract_complete_historical_data(processed_df)
            logger.info(f"Datos historicos: {len(historical_data)} años")

            # Calcular tendencias
            trends = self._calculate_real_trends(processed_df)
            logger.info(f"Tendencias calculadas para {len(trends)} indicadores")

            # Obtener configuracion del escenario
            scenario_config = self._get_scenario_config_by_id(scenario_id)
            logger.info(f"Configuracion: {scenario_config.name}")

            # Generar proyecciones con parametros personalizados
            future_projections = self._generate_future_projections(
                processed_df, 
                trends, 
                scenario_config, 
                years_ahead, 
                custom_params
            )
            logger.info(f"Proyecciones futuras: {len(future_projections)} años")

            # Combinar historico + proyecciones
            complete_data = historical_data + future_projections
            logger.info(f"Dataset completo: {len(complete_data)} puntos")
            
            logger.info("=" * 60)
            logger.info("FIN GENERACION ESCENARIO")
            logger.info("=" * 60)
            
            return complete_data

        except Exception as e:
            logger.error(f"Error generando proyecciones: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return self._generate_fallback_projections(years_ahead)
    
    def _process_csv_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Procesa el DataFrame detectando automaticamente la estructura"""
        date_col = self._detect_date_column(df)
        if date_col is None:
            raise ValueError("No se encontro columna de fecha valida")
        return self._prepare_dataframe(df.copy(), date_col)
    
    def _detect_date_column(self, df: pd.DataFrame) -> Optional[str]:
        """Detecta automaticamente la columna de fecha"""
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
        """Prepara el DataFrame para analisis"""
        if date_col != 'Año':
            df = df.rename(columns={date_col: 'Año'})
        df['Año'] = pd.to_numeric(df['Año'], errors='coerce')
        
        # Limpieza extra en columnas numericas
        for col in df.columns:
            if col != 'Año' and df[col].dtype == object:
                df[col] = (
                    df[col].astype(str)
                    .str.replace("%", "", regex=False)
                    .str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        df.set_index('Año', inplace=True)
        df.sort_index(inplace=True)
        df = df[df.index.notna()]
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df = df[numeric_cols].interpolate(method='linear')
        return df
    
    def _extract_complete_historical_data(self, df: pd.DataFrame) -> List[Dict]:
        """Extrae TODOS los datos historicos disponibles"""
        historical = []

        for year in df.index.unique():
            year_data = {}

            for col in df.columns:
                value = df.loc[year, col]

                if isinstance(value, pd.Series):
                    value = value.mean()

                if pd.notna(value):
                    try:
                        year_data[col] = max(0, float(value))
                    except Exception:
                        continue

            if year_data:
                historical.append({
                    'year': int(year),
                    'values': year_data
                })

        return historical
    
    def _calculate_real_trends(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcula tendencias de crecimiento historicas REALES"""
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
        """Obtiene configuracion del escenario por ID"""
        try:
            from models import Scenario
            scenario = self.db.query(Scenario).filter(Scenario.id == scenario_id).first()
            if scenario and scenario.scenario_type:
                return self.scenarios[ScenarioType(scenario.scenario_type)]
            return self.scenarios[ScenarioType.TENDENCIAL]
        except:
            return self.scenarios[ScenarioType.TENDENCIAL]
    
    def _generate_future_projections(
        self, 
        df: pd.DataFrame, 
        trends: Dict, 
        scenario_config: ScenarioConfig, 
        years_ahead: int,
        custom_params: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Genera proyecciones futuras basadas en datos historicos con parametros personalizados.
        
        Args:
            df: DataFrame con datos historicos
            trends: Tendencias calculadas por indicador
            scenario_config: Configuracion del tipo de escenario
            years_ahead: Años a proyectar
            custom_params: Parametros personalizados del usuario (ej: {'default': 1.2, 'tecnologia': 1.5})
        """
        projections = []
        last_year = int(df.index.max())
        last_values = df.iloc[-1].to_dict()
        
        # Normalizar custom_params si no existe
        custom_params = custom_params or {}
        
        logger.info(f"Generando proyecciones con parametros personalizados: {custom_params}")
        
        # Obtener multiplicador general (default)
        general_multiplier = custom_params.get('default', 1.0)
        
        for year_offset in range(1, years_ahead + 1):
            future_year = last_year + year_offset
            future_values = {}
            projection_multipliers = {}  # 👈 dict para guardar multiplicadores por columna

            for col, last_value in last_values.items():
                # 1. Tendencia historica real del indicador
                hist_trend = trends.get(col, 0.02)
                
                # 2. Multiplicador base del escenario (optimista/pesimista/tendencial)
                base_multiplier = scenario_config.multipliers.get('general', 1.0)
                
                # 3. Aplicar multiplicador general personalizado
                combined_multiplier = base_multiplier * general_multiplier
                
                # 4. Buscar multiplicador especifico para este indicador
                col_normalized = col.lower().replace(' ', '').replace('_', '')
                for param_key, param_value in custom_params.items():
                    if param_key == 'default':
                        continue
                        
                    param_key_normalized = param_key.lower().replace('_', '')
                    if param_key_normalized in col_normalized:
                        combined_multiplier *= param_value
                        logger.debug(f"Aplicando multiplicador {param_value} a {col} (parametro: {param_key})")
                        break
                
                # 5. Tasa de crecimiento del escenario
                scenario_growth = scenario_config.growth_rates.get('general', hist_trend)
                
                # 6. Combinar tendencia historica con escenario
                combined_growth = (hist_trend + scenario_growth) / 2
                
                # 7. Calcular valor proyectado
                projected = last_value * combined_multiplier * ((1 + combined_growth) ** year_offset)
                
                # 8. Variabilidad segun escenario
                variability = scenario_config.growth_rates.get('variabilidad', 0.1)
                noise = 1 + np.random.uniform(-abs(variability), abs(variability))
                
                # 9. Asegurar valor positivo
                final_value = max(0, float(projected * noise))
                
                # Guardar valor y multiplicador aplicado
                future_values[col] = final_value
                projection_multipliers[col] = combined_multiplier

                logger.debug(
                    f"{col} - Año {future_year}: "
                    f"Base={last_value:.2f}, "
                    f"Mult={combined_multiplier:.2f}, "
                    f"Proyectado={final_value:.2f}"
                )

            projections.append({
                'year': future_year,
                'values': future_values,
                'multipliers': projection_multipliers,  # 👈 ahora se guarda detalle por columna
                'sector': 'General',
                'base_value': sum(last_values.values()) / len(last_values) if last_values else 0
            })

        logger.info(f"Generadas {len(projections)} proyecciones con parametros aplicados")
        return projections

    
    def _generate_fallback_projections(self, years_ahead: int) -> List[Dict]:
        """Genera proyecciones sinteticas como respaldo"""
        projections = []
        current_year = datetime.now().year
        
        # Generar datos historicos sinteticos
        for i in range(10, 0, -1):
            projections.append({
                'year': current_year - i,
                'values': {
                    'Estudiantes': float(1000 + np.random.uniform(-200, 200)),
                    'Programas': float(20 + np.random.uniform(-5, 5)),
                    'Graduados': float(250 + np.random.uniform(-50, 50))
                }
            })
        
        # Generar proyecciones futuras
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
        """Compara multiples escenarios"""
        return {
            "message": "Comparacion de escenarios", 
            "scenario_ids": scenario_ids, 
            "comparison_data": []
        }
    
    def initialize_default_scenarios(self, user_id: int):
        """Inicializa escenarios predefinidos"""
        pass
    