import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session
from models import Scenario, ScenarioProjection, ScenarioConfiguration

ML_DIRECTORY = "ml"
MODEL_DIRECTORY = os.path.join(ML_DIRECTORY, "models")
DATA_DIRECTORY = os.path.join(ML_DIRECTORY, "data")

# Crear directorios si no existen
os.makedirs(MODEL_DIRECTORY, exist_ok=True)
os.makedirs(DATA_DIRECTORY, exist_ok=True)

try:
    from ml.loader import model, scaler
    from ml.preprocessing import clean_and_prepare, scale_dataframe
    from ml.predictor import predict_future
    ML_MODEL_AVAILABLE = True
    print("✅ Modelo ML cargado correctamente desde carpeta ml/")
except ImportError as e:
    print(f"⚠️ No se pudo cargar el modelo ML: {e}")
    print("⚠️ Usando modo de respaldo con datos sintéticos")
    model = None
    scaler = None
    clean_and_prepare = None
    scale_dataframe = None
    predict_future = None
    ML_MODEL_AVAILABLE = False
except Exception as e:
    print(f"⚠️ Error inesperado cargando modelo ML: {e}")
    model = None
    scaler = None
    clean_and_prepare = None
    scale_dataframe = None
    predict_future = None
    ML_MODEL_AVAILABLE = False

class ScenarioType(Enum):
    TENDENCIAL = "tendencial"
    OPTIMISTA = "optimista" 
    PESIMISTA = "pesimista"

@dataclass
class ScenarioConfig:
    """Configuración de parámetros para cada escenario"""
    name: str
    description: str
    multipliers: Dict[str, float]  # Multiplicadores por indicador
    growth_rates: Dict[str, float]  # Tasas de crecimiento anuales
    narrative: str

class ScenarioEngine:
    """Motor de escenarios prospectivos que integra con el modelo LSTM"""
    
    def __init__(self, db: Session):
        self.db = db
        self.model = model
        self.scaler = scaler
        self.scenarios = self._initialize_scenarios()
        self.model_available = self.initialize_model()
    
    def initialize_model(self):
        """Verifica que el modelo LSTM esté disponible"""
        try:
            if ML_MODEL_AVAILABLE and self.model is not None and self.scaler is not None:
                print("✅ Modelo LSTM inicializado correctamente")
                return True
            else:
                print("⚠️ Modelo LSTM no disponible - usando modo de respaldo")
                return False
        except Exception as e:
            print(f"⚠️ Error verificando modelo LSTM: {e}")
            return False
    
    def create_scenario(self, scenario_data: Dict, created_by: int) -> Scenario:
        """Crea un nuevo escenario en la base de datos"""
        scenario = Scenario(
            name=scenario_data["name"],
            scenario_type=scenario_data["scenario_type"],
            description=scenario_data.get("description"),
            parameters=scenario_data["parameters"],
            created_by=created_by
        )
        
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        
        return scenario
    
    def generate_scenario_projections(self, scenario_id: int, historical_data: pd.DataFrame, 
                                    years_ahead: int = 10) -> List[Dict]:
        """Genera proyecciones para un escenario específico"""
        scenario = self.db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise ValueError(f"Escenario {scenario_id} no encontrado")
        
        if self.model_available and ML_MODEL_AVAILABLE:
            try:
                # Preprocesar datos históricos usando las funciones reales
                processed_data = clean_and_prepare(historical_data.copy())
                
                # Generar predicciones base usando la función real
                base_predictions = predict_future(processed_data)
                
                # Aplicar ajustes del escenario
                scenario_type = ScenarioType(scenario.scenario_type)
                adjusted_predictions = self.apply_scenario_adjustments(
                    base_predictions, scenario_type, scenario.parameters
                )
                
                # Guardar proyecciones en la base de datos
                self._save_projections_to_db(scenario_id, adjusted_predictions)
                
                print(f"✅ Proyecciones generadas usando modelo ML para escenario {scenario_id}")
                return adjusted_predictions
                
            except Exception as e:
                print(f"⚠️ Error generando proyecciones con modelo ML: {e}")
                print("⚠️ Cambiando a modo de respaldo")
        
        # Fallback: usar datos simulados
        print(f"ℹ️ Generando proyecciones sintéticas para escenario {scenario_id}")
        return self._generate_fallback_projections(scenario, years_ahead)
    
    def _save_projections_to_db(self, scenario_id: int, projections: List[Dict]):
        """Guarda las proyecciones en la base de datos"""
        # Limpiar proyecciones anteriores
        self.db.query(ScenarioProjection).filter(
            ScenarioProjection.scenario_id == scenario_id
        ).delete()
        
        # Guardar nuevas proyecciones
        for projection in projections:
            if projection.get('year', 0) <= datetime.now().year:
                continue  # Solo guardar proyecciones futuras
                
            for indicator, values in projection.get('values', {}).items():
                if isinstance(values, dict):
                    for sector, value in values.items():
                        proj = ScenarioProjection(
                            scenario_id=scenario_id,
                            sector=sector,
                            year=projection['year'],
                            projected_value=float(value),
                            base_value=float(value * 0.8),  # Estimación del valor base
                            multiplier_applied=1.2,  # Multiplicador aplicado
                            indicator_type=indicator
                        )
                        self.db.add(proj)
        
        self.db.commit()
    
    def _generate_fallback_projections(self, scenario: Scenario, years_ahead: int) -> List[Dict]:
        """Genera proyecciones de respaldo cuando el modelo LSTM no está disponible"""
        current_year = datetime.now().year
        projections = []
        
        # Valores base simulados
        base_values = {
            "poblacion_objetivo": {"Tecnología": 1000, "Salud": 800, "Turismo": 600},
            "demanda_empleo": {"Tecnología": 1200, "Salud": 900, "Turismo": 700},
            "oferta_educativa": {"Tecnología": 800, "Salud": 700, "Turismo": 500}
        }
        
        scenario_config = self.scenarios[ScenarioType(scenario.scenario_type)]
        
        for year_offset in range(years_ahead + 1):
            year = current_year + year_offset
            year_values = {}
            
            for indicator, sectors in base_values.items():
                year_values[indicator] = {}
                multiplier = scenario_config.multipliers.get(indicator, 1.0)
                growth_rate = scenario_config.growth_rates.get(indicator, 0.0)
                
                for sector, base_value in sectors.items():
                    # Aplicar crecimiento compuesto y multiplicador
                    growth_factor = (1 + growth_rate) ** year_offset
                    projected_value = base_value * multiplier * growth_factor
                    year_values[indicator][sector] = int(projected_value)
            
            projections.append({
                'year': year,
                'values': year_values
            })
        
        return projections
    
    def compare_scenarios(self, scenario_ids: List[int]) -> Dict[str, Any]:
        """Compara múltiples escenarios"""
        scenarios_data = []
        
        for scenario_id in scenario_ids:
            scenario = self.db.query(Scenario).filter(Scenario.id == scenario_id).first()
            if not scenario:
                continue
                
            projections = self.db.query(ScenarioProjection).filter(
                ScenarioProjection.scenario_id == scenario_id
            ).all()
            
            scenarios_data.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario.name,
                "scenario_type": scenario.scenario_type,
                "projections": [
                    {
                        "sector": p.sector,
                        "year": p.year,
                        "indicator_type": p.indicator_type,
                        "base_value": p.base_value,
                        "projected_value": p.projected_value,
                        "multiplier_applied": p.multiplier_applied
                    } for p in projections
                ]
            })
        
        # Calcular métricas de comparación
        comparison_metrics = self._calculate_comparison_metrics(scenarios_data)
        
        # Generar recomendaciones
        recommendations = self._generate_recommendations(scenarios_data)
        
        return {
            "scenarios": scenarios_data,
            "comparison_metrics": comparison_metrics,
            "recommendations": recommendations
        }
    
    def _calculate_comparison_metrics(self, scenarios_data: List[Dict]) -> Dict[str, Any]:
        """Calcula métricas de comparación entre escenarios"""
        if not scenarios_data:
            return {}
        
        # Calcular promedios por escenario
        scenario_averages = {}
        for scenario in scenarios_data:
            total_projected = sum(p["projected_value"] for p in scenario["projections"])
            avg_projected = total_projected / len(scenario["projections"]) if scenario["projections"] else 0
            scenario_averages[scenario["scenario_name"]] = avg_projected
        
        # Encontrar mejor y peor escenario
        best_scenario = max(scenario_averages.items(), key=lambda x: x[1]) if scenario_averages else ("N/A", 0)
        worst_scenario = min(scenario_averages.items(), key=lambda x: x[1]) if scenario_averages else ("N/A", 0)
        
        return {
            "scenario_averages": scenario_averages,
            "best_scenario": {"name": best_scenario[0], "avg_value": best_scenario[1]},
            "worst_scenario": {"name": worst_scenario[0], "avg_value": worst_scenario[1]},
            "total_scenarios_compared": len(scenarios_data)
        }
    
    def _generate_recommendations(self, scenarios_data: List[Dict]) -> List[str]:
        """Genera recomendaciones basadas en la comparación de escenarios"""
        recommendations = []
        
        if not scenarios_data:
            return ["No hay datos suficientes para generar recomendaciones"]
        
        # Analizar tendencias por sector
        sector_performance = {}
        for scenario in scenarios_data:
            for projection in scenario["projections"]:
                sector = projection["sector"]
                if sector not in sector_performance:
                    sector_performance[sector] = []
                sector_performance[sector].append(projection["projected_value"])
        
        # Generar recomendaciones por sector
        for sector, values in sector_performance.items():
            avg_value = sum(values) / len(values)
            if avg_value > 1000:
                recommendations.append(f"El sector {sector} muestra alto potencial de crecimiento. Considerar aumentar la oferta educativa.")
            elif avg_value < 500:
                recommendations.append(f"El sector {sector} presenta desafíos. Evaluar estrategias de diversificación.")
        
        # Recomendaciones generales
        recommendations.extend([
            "Monitorear indicadores clave trimestralmente para ajustar estrategias",
            "Desarrollar planes de contingencia para escenarios adversos",
            "Fortalecer alianzas público-privadas para mejorar empleabilidad"
        ])
        
        return recommendations
    
    def initialize_default_scenarios(self, created_by: int):
        """Inicializa escenarios predefinidos en la base de datos"""
        for scenario_type, config in self.scenarios.items():
            existing = self.db.query(Scenario).filter(
                Scenario.scenario_type == scenario_type.value,
                Scenario.name == config.name
            ).first()
            
            if not existing:
                scenario_data = {
                    "name": config.name,
                    "scenario_type": scenario_type.value,
                    "description": config.description,
                    "parameters": {
                        "multipliers": config.multipliers,
                        "growth_rates": config.growth_rates,
                        "narrative": config.narrative
                    }
                }
                
                self.create_scenario(scenario_data, created_by)
                print(f"✅ Escenario '{config.name}' inicializado")
        
        print("✅ Todos los escenarios predefinidos han sido inicializados")
        
    def _initialize_scenarios(self) -> Dict[ScenarioType, ScenarioConfig]:
        """Inicializa los escenarios predefinidos"""
        return {
            ScenarioType.TENDENCIAL: ScenarioConfig(
                name="Escenario Tendencial",
                description="Proyección basada en tendencias históricas actuales",
                multipliers={
                    "poblacion_objetivo": 1.0,
                    "demanda_empleo": 1.0,
                    "oferta_educativa": 1.0,
                    "tecnologia": 1.0
                },
                growth_rates={
                    "poblacion_objetivo": 0.02,  # 2% anual
                    "demanda_empleo": 0.015,     # 1.5% anual
                    "oferta_educativa": 0.01,    # 1% anual
                    "tecnologia": 0.05           # 5% anual
                },
                narrative="En este escenario, las tendencias actuales se mantienen sin cambios significativos. El crecimiento poblacional sigue patrones históricos, la demanda laboral crece moderadamente y la adopción tecnológica avanza a ritmo constante."
            ),
            
            ScenarioType.OPTIMISTA: ScenarioConfig(
                name="Escenario Optimista",
                description="Proyección con condiciones favorables y crecimiento acelerado",
                multipliers={
                    "poblacion_objetivo": 1.2,
                    "demanda_empleo": 1.5,
                    "oferta_educativa": 1.3,
                    "tecnologia": 1.8
                },
                growth_rates={
                    "poblacion_objetivo": 0.035,  # 3.5% anual
                    "demanda_empleo": 0.04,       # 4% anual
                    "oferta_educativa": 0.025,    # 2.5% anual
                    "tecnologia": 0.12            # 12% anual
                },
                narrative="La región logra diversificar su economía exitosamente. La demanda de técnicos en energías renovables y tecnologías emergentes crece un 50%. Nuevas inversiones generan empleos de alta calidad y la oferta educativa se adapta rápidamente a las necesidades del mercado."
            ),
            
            ScenarioType.PESIMISTA: ScenarioConfig(
                name="Escenario Pesimista", 
                description="Proyección con condiciones adversas y crecimiento limitado",
                multipliers={
                    "poblacion_objetivo": 0.8,
                    "demanda_empleo": 0.6,
                    "oferta_educativa": 0.7,
                    "tecnologia": 0.4
                },
                growth_rates={
                    "poblacion_objetivo": 0.005,   # 0.5% anual
                    "demanda_empleo": -0.01,       # -1% anual
                    "oferta_educativa": 0.002,     # 0.2% anual
                    "tecnologia": 0.01             # 1% anual
                },
                narrative="Factores económicos adversos limitan el crecimiento. La migración reduce la población objetivo, sectores tradicionales pierden empleos y la adopción tecnológica se ralentiza por falta de inversión. La oferta educativa debe adaptarse a un mercado laboral contraído."
            )
        }
    
    def apply_scenario_adjustments(self, base_predictions: List[Dict], 
                                 scenario_type: ScenarioType,
                                 custom_params: Optional[Dict] = None) -> List[Dict]:
        """Aplica ajustes de escenario a las predicciones base del modelo LSTM"""
        scenario = self.scenarios[scenario_type]
        adjusted_predictions = []
        
        for i, prediction in enumerate(base_predictions):
            if prediction.get('year', 0) <= datetime.now().year:
                # Datos históricos no se modifican
                adjusted_predictions.append(prediction)
                continue
                
            # Calcular años futuros desde el año base
            future_year_index = i - len([p for p in base_predictions if p.get('year', 0) <= datetime.now().year])
            
            adjusted_values = {}
            for indicator, base_value in prediction['values'].items():
                # Aplicar multiplicador base del escenario
                multiplier = scenario.multipliers.get(indicator, 1.0)
                
                # Aplicar parámetros personalizados si existen
                if custom_params and indicator in custom_params:
                    multiplier *= custom_params[indicator]
                
                # Aplicar tasa de crecimiento compuesta
                growth_rate = scenario.growth_rates.get(indicator, 0.0)
                growth_factor = (1 + growth_rate) ** future_year_index
                
                # Calcular valor ajustado
                adjusted_value = base_value * multiplier * growth_factor
                adjusted_values[indicator] = max(0, int(round(adjusted_value)))
            
            adjusted_predictions.append({
                'year': prediction['year'],
                'values': adjusted_values
            })
        
        return adjusted_predictions
    
    def get_scenario_info(self, scenario_type: ScenarioType) -> Dict[str, Any]:
        """Obtiene información completa de un escenario"""
        scenario = self.scenarios[scenario_type]
        return {
            'type': scenario_type.value,
            'name': scenario.name,
            'description': scenario.description,
            'narrative': scenario.narrative,
            'multipliers': scenario.multipliers,
            'growth_rates': scenario.growth_rates
        }
    
    def get_all_scenarios_info(self) -> List[Dict[str, Any]]:
        """Obtiene información de todos los escenarios disponibles"""
        return [self.get_scenario_info(scenario_type) for scenario_type in ScenarioType]
    
    def update_scenario_parameters(self, scenario_type: ScenarioType, 
                                 new_multipliers: Optional[Dict] = None,
                                 new_growth_rates: Optional[Dict] = None):
        """Actualiza parámetros de un escenario (para usuarios de Planeación)"""
        scenario = self.scenarios[scenario_type]
        
        if new_multipliers:
            scenario.multipliers.update(new_multipliers)
        
        if new_growth_rates:
            scenario.growth_rates.update(new_growth_rates)
    
    def export_scenario_data(self, scenario_type: ScenarioType, 
                           predictions: List[Dict]) -> Dict[str, Any]:
        """Exporta datos de escenario para descarga"""
        scenario = self.scenarios[scenario_type]
        
        return {
            'scenario_info': self.get_scenario_info(scenario_type),
            'predictions': predictions,
            'export_date': datetime.now().isoformat(),
            'summary': {
                'total_years': len(predictions),
                'historical_years': len([p for p in predictions if p.get('year', 0) <= datetime.now().year]),
                'future_years': len([p for p in predictions if p.get('year', 0) > datetime.now().year])
            }
        }
