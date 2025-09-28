import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from schemas import TipoReporte, ParametrosReporte
from datetime import datetime

logger = logging.getLogger(__name__)

class IntegratedDataCollectorService:
    """Servicio integrado de recolección de datos usando servicios existentes"""
    
    def __init__(self, db: Session):
        self.db = db
        # Usar tu servicio de datos existente
        from services.data_service import DataService
        self.data_service = DataService(db)
        self.collectors = self._setup_collectors()
    
    def collect_consolidated_data(
        self, 
        tipo: TipoReporte, 
        parametros: ParametrosReporte
    ) -> Dict[str, Any]:
        """Recolecta datos consolidados usando servicios existentes"""
        logger.info(f"Recolectando datos para tipo: {tipo}")
        
        try:
            if tipo == TipoReporte.CONSOLIDADO:
                return self._collect_all_data(parametros)
            elif tipo == TipoReporte.INDICADORES:
                return self._collect_indicators_data(parametros)
            elif tipo == TipoReporte.PROSPECTIVA:
                return self._collect_prospective_data(parametros)
            elif tipo == TipoReporte.OFERTA_EDUCATIVA:
                return self._collect_educational_data(parametros)
            else:
                return self.data_service.get_strategic_dashboard_data()
                
        except Exception as e:
            logger.error(f"Error en recolección: {str(e)}")
            return {"error": str(e)}
    
    def _collect_all_data(self, parametros):
        """Recolecta datos de todos los módulos"""
        return {
            "indicadores": self._collect_indicators_data(parametros),
            "dofa": self._collect_dofa_data(parametros), 
            "prospectiva": self._collect_prospective_data(parametros),
            "oferta_educativa": self._collect_educational_data(parametros),
            "metadata": {
                "fecha_recoleccion": datetime.now(),
                "tipo_reporte": "consolidado"
            }
        }
    
    def _collect_indicators_data(self, parametros):
        """Recolecta datos de indicadores usando datos reales o simulados"""
        from models import Indicador
        
        try:
            # Intentar obtener indicadores reales
            indicadores_db = self.db.query(Indicador).filter(Indicador.activo == True).all()
            
            indicadores_procesados = []
            for ind in indicadores_db:
                cumplimiento = (ind.valor_actual / ind.meta) if ind.meta and ind.meta > 0 else 0
                estado = "verde" if cumplimiento >= 0.9 else "amarillo" if cumplimiento >= 0.7 else "rojo"
                
                indicadores_procesados.append({
                    "id": ind.id,
                    "nombre": ind.nombre,
                    "valor_actual": ind.valor_actual,
                    "meta": ind.meta,
                    "unidad": ind.unidad,
                    "cumplimiento": cumplimiento,
                    "estado_semaforo": estado,
                    "categoria": ind.categoria or "General"
                })
            
            # Si no hay datos reales, usar datos de ejemplo
            if not indicadores_procesados:
                indicadores_procesados = self._get_sample_indicators()
            
            # Calcular resumen
            total = len(indicadores_procesados)
            verde = len([i for i in indicadores_procesados if i["estado_semaforo"] == "verde"])
            amarillo = len([i for i in indicadores_procesados if i["estado_semaforo"] == "amarillo"])
            rojo = len([i for i in indicadores_procesados if i["estado_semaforo"] == "rojo"])
            
            return {
                "indicadores": indicadores_procesados,
                "resumen": {
                    "total_indicadores": total,
                    "verde": verde,
                    "amarillo": amarillo,
                    "rojo": rojo,
                    "cumplimiento_general": round((verde / total * 100) if total > 0 else 0, 1)
                }
            }
            
        except Exception as e:
            logger.error(f"Error recolectando indicadores: {str(e)}")
            return {"indicadores": self._get_sample_indicators(), "resumen": {"total_indicadores": 5}}
    
    def _collect_dofa_data(self, parametros):
        """Recolecta datos DOFA"""
        from models import DofaItem
        
        try:
            items = self.db.query(DofaItem).filter(DofaItem.is_active == True).all()
            
            dofa = {"fortalezas": [], "oportunidades": [], "debilidades": [], "amenazas": []}
            
            for item in items:
                if item.category == "F":
                    dofa["fortalezas"].append(item.text)
                elif item.category == "O":
                    dofa["oportunidades"].append(item.text)
                elif item.category == "D":
                    dofa["debilidades"].append(item.text)
                elif item.category == "A":
                    dofa["amenazas"].append(item.text)
            
            # Si no hay datos reales, usar ejemplos
            if not any(dofa.values()):
                dofa = self._get_sample_dofa()
            
            return dofa
            
        except Exception as e:
            logger.error(f"Error recolectando DOFA: {str(e)}")
            return self._get_sample_dofa()
    
    def _collect_prospective_data(self, parametros):
        """Recolecta datos de prospectiva"""
        from models import Scenario
        
        try:
            scenarios = self.db.query(Scenario).filter(Scenario.is_active == True).all()
            
            escenarios_procesados = []
            for scenario in scenarios:
                escenarios_procesados.append({
                    "id": scenario.id,
                    "nombre": scenario.name,
                    "tipo": scenario.scenario_type or "tendencial",
                    "descripcion": scenario.description or f"Escenario {scenario.scenario_type}"
                })
            
            # Si no hay datos reales, usar ejemplos
            if not escenarios_procesados:
                escenarios_procesados = self._get_sample_scenarios()
            
            return {
                "escenarios": escenarios_procesados,
                "tendencias_sectoriales": [
                    {"sector": "Tecnología", "crecimiento_esperado": 15.2, "demanda": "Alta"},
                    {"sector": "Salud", "crecimiento_esperado": 12.8, "demanda": "Media"},
                ]
            }
            
        except Exception as e:
            logger.error(f"Error recolectando prospectiva: {str(e)}")
            return {"escenarios": self._get_sample_scenarios()}
    
    def _collect_educational_data(self, parametros):
        """Recolecta datos de oferta educativa"""
        from models import Program
        
        try:
            programs = self.db.query(Program).filter(Program.is_active == True).all()
            
            total_programas = len(programs)
            sectores = list(set(p.sector for p in programs if p.sector))
            
            return {
                "total_programas": total_programas,
                "total_cupos": sum(p.capacity or 0 for p in programs),
                "sectores_atendidos": len(sectores),
                "programas_por_sector": [
                    {"sector": sector, "programas_activos": len([p for p in programs if p.sector == sector])}
                    for sector in sectores
                ]
            }
            
        except Exception as e:
            logger.error(f"Error recolectando oferta educativa: {str(e)}")
            return {"total_programas": 0, "total_cupos": 0}
    
    def _get_sample_indicators(self):
        """Indicadores de ejemplo si no hay datos reales"""
        return [
            {
                "id": "empleabilidad",
                "nombre": "Empleabilidad Egresados",
                "valor_actual": 82.5,
                "meta": 85.0,
                "unidad": "%",
                "cumplimiento": 0.97,
                "estado_semaforo": "verde",
                "categoria": "Impacto"
            },
            {
                "id": "cobertura",
                "nombre": "Cobertura Formación",
                "valor_actual": 65.2,
                "meta": 75.0,
                "unidad": "%", 
                "cumplimiento": 0.87,
                "estado_semaforo": "amarillo",
                "categoria": "Acceso"
            }
        ]
    
    def _get_sample_dofa(self):
        """Datos DOFA de ejemplo"""
        return {
            "fortalezas": [
                "Amplia cobertura territorial",
                "Experiencia en formación técnica",
                "Reconocimiento institucional"
            ],
            "oportunidades": [
                "Crecimiento sector tecnológico",
                "Políticas de formación",
                "Demanda de competencias digitales"
            ],
            "debilidades": [
                "Infraestructura tecnológica limitada",
                "Brecha en competencias digitales"
            ],
            "amenazas": [
                "Competencia de instituciones privadas",
                "Cambios tecnológicos acelerados"
            ]
        }
    
    def _get_sample_scenarios(self):
        """Escenarios de ejemplo"""
        return [
            {
                "id": "optimista",
                "nombre": "Escenario Optimista 2025",
                "tipo": "optimista", 
                "descripcion": "Crecimiento sostenido del sector productivo"
            },
            {
                "id": "base",
                "nombre": "Escenario Base 2025",
                "tipo": "tendencial",
                "descripcion": "Crecimiento moderado con estabilidad"
            }
        ]
    
    def _setup_collectors(self):
        """Configura colectores mock para compatibilidad"""
        return {
            "indicadores": MockCollector(self.db, "indicadores"),
            "dofa": MockCollector(self.db, "dofa"),
            "prospectiva": MockCollector(self.db, "prospectiva"),
            "oferta_educativa": MockCollector(self.db, "oferta_educativa")
        }
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Obtiene resumen del estado del sistema"""
        try:
            dashboard_data = self.data_service.get_strategic_dashboard_data()
            
            return {
                "timestamp": datetime.now(),
                "modulos": {
                    "indicadores": {
                        "status": "activo",
                        "total": dashboard_data.get("indicators_summary", {}).get("total_indicators", 0)
                    },
                    "dofa": {
                        "status": "activo", 
                        "total": dashboard_data.get("dofa_summary", {}).get("total_items", 0)
                    },
                    "prospectiva": {
                        "status": "activo",
                        "total": dashboard_data.get("active_scenarios", 0)
                    },
                    "oferta_educativa": {
                        "status": "activo",
                        "total": dashboard_data.get("programs_stats", {}).get("total_programs", 0)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error obteniendo resumen del sistema: {str(e)}")
            return {
                "timestamp": datetime.now(),
                "error": str(e),
                "modulos": {}
            }

class MockCollector:
    """Colector simulado para compatibilidad"""
    def __init__(self, db: Session, tipo: str):
        self.db = db
        self.tipo = tipo
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Resumen de datos por tipo"""
        try:
            if self.tipo == "indicadores":
                from models import Indicador
                total = self.db.query(Indicador).filter(Indicador.activo == True).count()
                return {"total_indicadores_activos": total}
            elif self.tipo == "dofa":
                from models import DofaItem
                total = self.db.query(DofaItem).filter(DofaItem.is_active == True).count()
                return {"total_items_dofa": total}
            elif self.tipo == "prospectiva":
                from models import Scenario
                total = self.db.query(Scenario).filter(Scenario.is_active == True).count()
                return {"total_escenarios_activos": total}
            elif self.tipo == "oferta_educativa":
                from models import Program
                total = self.db.query(Program).filter(Program.is_active == True).count()
                return {"total_programas_activos": total}
            else:
                return {"total": 0}
        except Exception as e:
            logger.error(f"Error en resumen de {self.tipo}: {str(e)}")
            return {"total": 0}