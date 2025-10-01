import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
from schemas import TipoReporte, ParametrosReporte

logger = logging.getLogger(__name__)

class IntegratedDataCollectorService:
    """Servicio integrado de recolección de datos usando servicios existentes"""
    
    def __init__(self, db: Session):
        self.db = db
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
            elif tipo == TipoReporte.DOFA:
                return self._collect_dofa_data(parametros)
            else:
                return self.data_service.get_strategic_dashboard_data()
                
        except Exception as e:
            logger.error(f"Error en recolección: {str(e)}")
            return {"error": str(e)}
    
    def _collect_all_data(self, parametros):
        """Recolecta datos de todos los módulos"""
        return {
            "indicadores": self._collect_indicators_data(parametros).get("indicadores", {}),
            "dofa": self._collect_dofa_data(parametros).get("dofa", {}),
            "prospectiva": self._collect_prospective_data(parametros).get("prospectiva", {}),
            "oferta_educativa": self._collect_educational_data(parametros).get("oferta_educativa", {}),
            "metadata": {
                "fecha_recoleccion": datetime.now(),
                "tipo_reporte": "consolidado"
            }
        }
    
    def _collect_indicators_data(self, parametros):
        """Recolecta datos de indicadores"""
        try:
            try:
                from models import Indicador
                indicadores_db = self.db.query(Indicador).filter(Indicador.activo == True).all()
            except Exception as import_error:
                logger.warning(f"No se pudo importar modelo Indicador: {import_error}")
                indicadores_db = []
            
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
            
            if not indicadores_procesados:
                indicadores_procesados = self._get_sample_indicators()
            
            total = len(indicadores_procesados)
            verde = len([i for i in indicadores_procesados if i["estado_semaforo"] == "verde"])
            amarillo = len([i for i in indicadores_procesados if i["estado_semaforo"] == "amarillo"])
            rojo = len([i for i in indicadores_procesados if i["estado_semaforo"] == "rojo"])
            
            return {
                "indicadores": {
                    "lista": indicadores_procesados,
                    "resumen": {
                        "total_indicadores": total,
                        "verde": verde,
                        "amarillo": amarillo,
                        "rojo": rojo,
                        "cumplimiento_general": round((verde / total * 100) if total > 0 else 0, 1)
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error recolectando indicadores: {str(e)}")
            return {
                "indicadores": {
                    "lista": self._get_sample_indicators(), 
                    "resumen": {
                        "total_indicadores": 5,
                        "verde": 2,
                        "amarillo": 2,
                        "rojo": 1,
                        "cumplimiento_general": 60.0
                    }
                }
            }
    
    def _collect_dofa_data(self, parametros):
        """Recolecta datos DOFA"""
        try:
            try:
                from models import DofaItem
                items = self.db.query(DofaItem).filter(DofaItem.is_active == True).all()
            except Exception as import_error:
                logger.warning(f"No se pudo importar modelo DofaItem: {import_error}")
                items = []
            
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
            
            if not any(dofa.values()):
                dofa = self._get_sample_dofa()    
            return {"dofa": dofa}
            
        except Exception as e:
            logger.error(f"Error recolectando DOFA: {str(e)}")
            return {"dofa": self._get_sample_dofa()}
    
    def _collect_prospective_data(self, parametros):
        """Recolecta datos de prospectiva desde la tabla scenarios y sus proyecciones"""
        try:
            from models import Scenario, ScenarioProjection
            
            # Obtener escenarios activos
            scenarios = self.db.query(Scenario).filter(Scenario.is_active == True).all()
            logger.info(f"Encontrados {len(scenarios)} escenarios activos en BD")

            escenarios_procesados = []
            
            for scenario in scenarios:
                # Obtener proyecciones para este escenario
                projections = self.db.query(ScenarioProjection).filter(
                    ScenarioProjection.scenario_id == scenario.id
                ).all()
                
                # Procesar proyecciones
                proyecciones_procesadas = []
                for proj in projections:
                    proyecciones_procesadas.append({
                        "sector": proj.sector,
                        "año": proj.year,
                        "valor_proyectado": proj.projected_value,
                        "valor_base": proj.base_value,
                        "multiplicador_aplicado": proj.multiplier_applied,
                        "tipo_indicador": proj.indicator_type
                    })
                
                # Agrupar proyecciones por sector para mejor organización
                proyecciones_por_sector = {}
                for proj in proyecciones_procesadas:
                    sector = proj["sector"]
                    if sector not in proyecciones_por_sector:
                        proyecciones_por_sector[sector] = []
                    proyecciones_por_sector[sector].append(proj)
                
                escenario_data = {
                    "id": scenario.id,
                    "nombre": scenario.name,
                    "tipo": scenario.scenario_type,
                    "descripcion": scenario.description,
                    "parametros": scenario.parameters,
                    "proyecciones": proyecciones_procesadas,
                    "proyecciones_por_sector": proyecciones_por_sector
                }
                
                escenarios_procesados.append(escenario_data)

            if not escenarios_procesados:
                logger.warning("No se encontraron escenarios en BD, usando ejemplos")
                escenarios_procesados = self._get_sample_scenarios()

            # Obtener tendencias sectoriales desde las proyecciones si existen
            tendencias_sectoriales = self._get_tendencias_from_projections()

            return {
                "prospectiva": {
                    "escenarios": escenarios_procesados,
                    "tendencias_sectoriales": tendencias_sectoriales,
                    "factores_clave": self._get_factores_clave_from_scenarios(scenarios)
                }
            }

        except Exception as e:
            logger.error(f"Error recolectando prospectiva: {str(e)}")
            return {
                "prospectiva": {
                    "escenarios": self._get_sample_scenarios(),
                    "tendencias_sectoriales": [
                        {"sector": "General", "crecimiento_esperado": 5.0, "demanda": "Media", "factores": ["Crecimiento económico"]}
                    ],
                    "factores_clave": [
                        "Estabilidad económica",
                        "Desarrollo tecnológico"
                    ]
                }
            }

    def _get_tendencias_from_projections(self):
        """Calcula tendencias sectoriales a partir de las proyecciones"""
        try:
            from models import ScenarioProjection, Scenario
            
            # Obtener todas las proyecciones activas
            projections = self.db.query(ScenarioProjection).join(
                Scenario, Scenario.id == ScenarioProjection.scenario_id
            ).filter(Scenario.is_active == True).all()
            
            if not projections:
                return self._get_sample_tendencias()
            
            # Agrupar por sector
            sectores_data = {}
            for proj in projections:
                if proj.sector not in sectores_data:
                    sectores_data[proj.sector] = []
                sectores_data[proj.sector].append(proj)
            
            tendencias = []
            for sector, proyecciones in sectores_data.items():
                if len(proyecciones) < 2:
                    continue
                    
                # Calcular crecimiento promedio
                crecimiento_promedio = sum(
                    ((proj.projected_value - proj.base_value) / proj.base_value * 100) 
                    for proj in proyecciones
                ) / len(proyecciones)
                
                # Determinar nivel de demanda basado en el crecimiento
                if crecimiento_promedio > 10:
                    demanda = "Alta"
                elif crecimiento_promedio > 5:
                    demanda = "Media"
                else:
                    demanda = "Baja"
                
                # Obtener factores comunes (de los tipos de indicador)
                factores = list(set(proj.indicator_type for proj in proyecciones))
                
                tendencias.append({
                    "sector": sector,
                    "crecimiento_esperado": round(crecimiento_promedio, 1),
                    "demanda": demanda,
                    "factores": factores[:3]  # Máximo 3 factores
                })
            
            return tendencias if tendencias else self._get_sample_tendencias()
            
        except Exception as e:
            logger.error(f"Error calculando tendencias: {str(e)}")
            return self._get_sample_tendencias()

    def _get_factores_clave_from_scenarios(self, scenarios):
        """Extrae factores clave de los parámetros de los escenarios"""
        factores_clave = set()
        
        for scenario in scenarios:
            if scenario.parameters and isinstance(scenario.parameters, dict):
                # Buscar factores en los parámetros
                for key, value in scenario.parameters.items():
                    if any(factor in key.lower() for factor in ['factor', 'tendencia', 'driver', 'impulso']):
                        if isinstance(value, str) and value:
                            factores_clave.add(value)
        
        # Si no se encontraron factores, usar valores por defecto
        if not factores_clave:
            factores_clave = {
                "Transformación digital acelerada",
                "Cambios en el mercado laboral", 
                "Nuevas competencias requeridas",
                "Sostenibilidad ambiental"
            }
        
        return list(factores_clave)

    def _get_sample_tendencias(self):
        """Proporciona tendencias de ejemplo cuando no hay datos"""
        return [
            {"sector": "Tecnología", "crecimiento_esperado": 15.2, "demanda": "Alta", "factores": ["Digitalización", "IA"]},
            {"sector": "Salud", "crecimiento_esperado": 12.8, "demanda": "Media", "factores": ["Envejecimiento", "Telemedicina"]},
            {"sector": "Educación", "crecimiento_esperado": 8.5, "demanda": "Alta", "factores": ["Educación virtual", "Competencias digitales"]},
        ]
    
    def _collect_educational_data(self, parametros):
        """Recolecta datos de oferta educativa"""
        try:
            try:
                from models import Program
                programs = self.db.query(Program).filter(Program.is_active == True).all()
            except Exception as import_error:
                logger.warning(f"No se pudo importar modelo Program: {import_error}")
                programs = []
            
            if programs:
                total_programas = len(programs)
                sectores = list(set(p.sector for p in programs if p.sector))
                total_cupos = sum(p.capacity or 0 for p in programs)
                total_estudiantes = sum(p.current_students or 0 for p in programs)
                
                programas_por_sector = []
                for sector in sectores:
                    progs_sector = [p for p in programs if p.sector == sector]
                    cupos_sector = sum(p.capacity or 0 for p in progs_sector)
                    estudiantes_sector = sum(p.current_students or 0 for p in progs_sector)
                    ocupacion = (estudiantes_sector / cupos_sector * 100) if cupos_sector > 0 else 0
                    
                    programas_por_sector.append({
                        "sector": sector,
                        "programas_activos": len(progs_sector),
                        "cupos": cupos_sector,
                        "estudiantes_actuales": estudiantes_sector,
                        "ocupacion": round(ocupacion, 1)
                    })
                
                return {
                    "oferta_educativa": {
                        "total_programas": total_programas,
                        "total_cupos": total_cupos,
                        "total_estudiantes": total_estudiantes,
                        "sectores_atendidos": len(sectores),
                        "ocupacion_promedio": round((total_estudiantes / total_cupos * 100) if total_cupos > 0 else 0, 1),
                        "programas_por_sector": programas_por_sector
                    }
                }
            else:
                return {
                    "oferta_educativa": {
                        "total_programas": 25,
                        "total_cupos": 750,
                        "total_estudiantes": 620,
                        "sectores_atendidos": 5,
                        "ocupacion_promedio": 82.7,
                        "programas_por_sector": [
                            {"sector": "Tecnología", "programas_activos": 8, "cupos": 240, "estudiantes_actuales": 200, "ocupacion": 83.3},
                            {"sector": "Salud", "programas_activos": 6, "cupos": 180, "estudiantes_actuales": 150, "ocupacion": 83.3},
                            {"sector": "Industrial", "programas_activos": 5, "cupos": 150, "estudiantes_actuales": 120, "ocupacion": 80.0},
                            {"sector": "Servicios", "programas_activos": 4, "cupos": 120, "estudiantes_actuales": 100, "ocupacion": 83.3},
                            {"sector": "Agropecuario", "programas_activos": 2, "cupos": 60, "estudiantes_actuales": 50, "ocupacion": 83.3}
                        ]
                    }
                }
            
        except Exception as e:
            logger.error(f"Error recolectando oferta educativa: {str(e)}")
            return {
                "oferta_educativa": {
                    "total_programas": 0, 
                    "total_cupos": 0,
                    "total_estudiantes": 0,
                    "sectores_atendidos": 0,
                    "ocupacion_promedio": 0,
                    "programas_por_sector": []
                }
            }

    # === Métodos de ejemplo ===
    def _get_sample_indicators(self):
        """Proporciona indicadores de ejemplo cuando no hay datos"""
        return [
            {
                "id": 1,
                "nombre": "Tasa de graduación",
                "valor_actual": 85,
                "meta": 90,
                "unidad": "%",
                "cumplimiento": 0.944,
                "estado_semaforo": "verde",
                "categoria": "Académico"
            },
            {
                "id": 2,
                "nombre": "Satisfacción estudiantil",
                "valor_actual": 78,
                "meta": 85,
                "unidad": "%",
                "cumplimiento": 0.917,
                "estado_semaforo": "verde",
                "categoria": "Calidad"
            },
            {
                "id": 3,
                "nombre": "Empleabilidad egresados",
                "valor_actual": 65,
                "meta": 80,
                "unidad": "%",
                "cumplimiento": 0.812,
                "estado_semaforo": "amarillo",
                "categoria": "Laboral"
            },
            {
                "id": 4,
                "nombre": "Retención estudiantil",
                "valor_actual": 88,
                "meta": 95,
                "unidad": "%",
                "cumplimiento": 0.926,
                "estado_semaforo": "verde",
                "categoria": "Académico"
            },
            {
                "id": 5,
                "nombre": "Investigación publicada",
                "valor_actual": 12,
                "meta": 20,
                "unidad": "publicaciones",
                "cumplimiento": 0.6,
                "estado_semaforo": "rojo",
                "categoria": "Investigación"
            }
        ]
    
    def _get_sample_dofa(self):
        """Proporciona datos DOFA de ejemplo cuando no hay datos"""
        return {
            "fortalezas": [
                "Personal docente calificado",
                "Infraestructura moderna",
                "Alianzas estratégicas con empresas"
            ],
            "oportunidades": [
                "Crecimiento de demanda en educación virtual",
                "Nuevos programas de formación demandados",
                "Fondos gubernamentales para investigación"
            ],
            "debilidades": [
                "Limitada presencia internacional",
                "Falta de diversificación de ingresos",
                "Procesos administrativos lentos"
            ],
            "amenazas": [
                "Competencia de instituciones en línea",
                "Cambios en políticas educativas",
                "Reducción de presupuesto público"
            ]
        }
    
    def _get_sample_scenarios(self):
        """Proporciona escenarios de ejemplo cuando no hay datos en BD"""
        return [
            {
                "id": 1,
                "nombre": "Escenario Optimista",
                "tipo": "optimista", 
                "descripcion": "Crecimiento económico acelerado y alta demanda educativa",
                "parametros": {"factor_crecimiento": 1.2, "tendencia_mercado": "alta"},
                "proyecciones": [
                    {
                        "sector": "Tecnología",
                        "año": 2024,
                        "valor_proyectado": 1200,
                        "valor_base": 1000, 
                        "multiplicador_aplicado": 1.2,
                        "tipo_indicador": "empleo"
                    },
                    {
                        "sector": "Tecnología", 
                        "año": 2025,
                        "valor_proyectado": 1440,
                        "valor_base": 1000,
                        "multiplicador_aplicado": 1.44,
                        "tipo_indicador": "empleo"
                    }
                ],
                "proyecciones_por_sector": {
                    "Tecnología": [
                        {
                            "sector": "Tecnología",
                            "año": 2024,
                            "valor_proyectado": 1200,
                            "valor_base": 1000,
                            "multiplicador_aplicado": 1.2,
                            "tipo_indicador": "empleo"
                        },
                        {
                            "sector": "Tecnología",
                            "año": 2025,
                            "valor_proyectado": 1440,
                            "valor_base": 1000,
                            "multiplicador_aplicado": 1.44,
                            "tipo_indicador": "empleo"
                        }
                    ]
                }
            },
            {
                "id": 2,
                "nombre": "Escenario Conservador",
                "tipo": "conservador",
                "descripcion": "Crecimiento moderado con estabilidad en la demanda",
                "parametros": {"factor_crecimiento": 1.05, "tendencia_mercado": "estable"},
                "proyecciones": [
                    {
                        "sector": "Salud",
                        "año": 2024,
                        "valor_proyectado": 850,
                        "valor_base": 800,
                        "multiplicador_aplicado": 1.0625,
                        "tipo_indicador": "demanda"
                    }
                ],
                "proyecciones_por_sector": {
                    "Salud": [
                        {
                            "sector": "Salud",
                            "año": 2024,
                            "valor_proyectado": 850,
                            "valor_base": 800,
                            "multiplicador_aplicado": 1.0625,
                            "tipo_indicador": "demanda"
                        }
                    ]
                }
            }
        ]
    
    def _setup_collectors(self):
        return {
            "indicadores": MockCollector(self.db, "indicadores"),
            "dofa": MockCollector(self.db, "dofa"),
            "prospectiva": MockCollector(self.db, "prospectiva"),
            "oferta_educativa": MockCollector(self.db, "oferta_educativa")
        }

class MockCollector:
    """Colector simulado para compatibilidad"""
    def __init__(self, db: Session, tipo: str):
        self.db = db
        self.tipo = tipo
    
    def get_data_summary(self) -> Dict[str, Any]:
        try:
            if self.tipo == "indicadores":
                try:
                    from models import Indicador
                    total = self.db.query(Indicador).filter(Indicador.activo == True).count()
                except:
                    total = 0
                return {"total_indicadores_activos": total}
            elif self.tipo == "dofa":
                try:
                    from models import DofaItem
                    total = self.db.query(DofaItem).filter(DofaItem.is_active == True).count()
                except:
                    total = 0
                return {"total_items_dofa": total}
            elif self.tipo == "prospectiva":
                try:
                    from models import Scenario
                    total = self.db.query(Scenario).count()
                except:
                    total = 0
                return {"total_escenarios_activos": total}
            elif self.tipo == "oferta_educativa":
                try:
                    from models import Program
                    total = self.db.query(Program).filter(Program.is_active == True).count()
                except:
                    total = 0
                return {"total_programas_activos": total}
            else:
                return {"total": 0}
        except Exception as e:
            logger.error(f"Error en resumen de {self.tipo}: {str(e)}")
            return {"total": 0}