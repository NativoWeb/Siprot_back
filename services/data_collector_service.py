import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
from schemas import TipoReporte, ParametrosReporte
import pandas as pd

logger = logging.getLogger(__name__)

def format_decimal(value: float, precision: int = 3) -> float:
    """Redondea un número decimal a un máximo de 'precision' decimales"""
    if value is None:
        return 0.0
    return round(float(value), precision)

def sanitize_float(value):
    """Sanitiza valores flotantes para evitar NaN/Infinity"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        if pd.isna(value) or value == float('inf') or value == float('-inf'):
            return 0.0
        return float(value)
    return 0.0

class IntegratedDataCollectorService:
    """Servicio integrado de recolección de datos usando servicios existentes"""
    
    def __init__(self, db: Session):
        self.db = db
        from services.data_service import DataService
        self.data_service = DataService(db)
        self.collectors = self._setup_collectors()
    
    # === MÉTODO PRINCIPAL ===
    def collect_consolidated_data(
        self, 
        tipo: TipoReporte, 
        parametros: ParametrosReporte
    ) -> Dict[str, Any]:
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

    # === COLECCIÓN CONSOLIDADA ===
    def _collect_all_data(self, parametros):
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

    # === INDICADORES ===
    def _collect_indicators_data(self, parametros):
        try:
            from models import Indicador
            indicadores_db = self.db.query(Indicador).filter(Indicador.activo == True).all()
            
            indicadores_procesados = []
            for ind in indicadores_db:
                cumplimiento = format_decimal((ind.valor_actual / ind.meta) if ind.meta and ind.meta > 0 else 0)
                estado = "verde" if cumplimiento >= 0.9 else "amarillo" if cumplimiento >= 0.7 else "rojo"
                indicadores_procesados.append({
                    "id": ind.id,
                    "nombre": ind.nombre,
                    "valor_actual": format_decimal(ind.valor_actual),
                    "meta": format_decimal(ind.meta),
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
            
            cumplimiento_general = format_decimal((verde / total * 100) if total > 0 else 0)
            
            return {
                "indicadores": {
                    "lista": indicadores_procesados,
                    "resumen": {
                        "total_indicadores": total,
                        "verde": verde,
                        "amarillo": amarillo,
                        "rojo": rojo,
                        "cumplimiento_general": cumplimiento_general
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

    # === DOFA ===
    def _collect_dofa_data(self, parametros):
        try:
            from models import DofaItem
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
            
            if not any(dofa.values()):
                dofa = self._get_sample_dofa()
            return {"dofa": dofa}
            
        except Exception as e:
            logger.error(f"Error recolectando DOFA: {str(e)}")
            return {"dofa": self._get_sample_dofa()}

    # === PROSPECTIVA ===
    def _collect_prospective_data(self, parametros):
        """
        Recolecta datos de prospectiva usando el mismo formato que el endpoint /details/{scenario_id}
        para asegurar consistencia en la visualización de PDFs
        """
        try:
            from models import Scenario, ScenarioProjection, ScenarioConfiguration, User, Document
            
            scenarios = self.db.query(Scenario).filter(Scenario.is_active == True).all()
            escenarios_procesados = []
            
            for scenario in scenarios:
                # Obtener creador del escenario
                creator = self.db.query(User).filter(User.id == scenario.created_by).first()
                
                # Obtener proyecciones ordenadas por año
                projections_q = self.db.query(ScenarioProjection).filter(
                    ScenarioProjection.scenario_id == scenario.id
                ).order_by(ScenarioProjection.year.asc()).all()
                
                # Obtener configuraciones del tipo de escenario
                configurations = self.db.query(ScenarioConfiguration).filter(
                    ScenarioConfiguration.scenario_type == scenario.scenario_type
                ).all()
                
                # Construir diccionario de multiplicadores desde configuraciones
                multipliers = {}
                for config in configurations:
                    multipliers[config.parameter_name] = config.parameter_value
                
                logger.info(f"Multiplicadores cargados para escenario {scenario.id}: {multipliers}")
                
                # Procesar proyecciones agrupadas por año (igual que en el endpoint de detalles)
                proyecciones_procesadas = []
                proyecciones_por_año = {}
                proyecciones_por_sector = {}
                
                if projections_q:
                    # Agrupar proyecciones por año
                    by_year = {}
                    for p in projections_q:
                        y = p.year
                        if y not in by_year:
                            by_year[y] = {
                                "year": y,
                                "año": y,  # Alias para compatibilidad
                                "sector": p.sector,
                                "base_value": sanitize_float(p.base_value),
                                "values": {},
                                "multipliers": {}
                            }
                        
                        # Agregar valor del indicador
                        by_year[y]["values"][p.indicator_type] = sanitize_float(p.projected_value)
                        
                        # Encontrar multiplicador específico para este indicador
                        indicator_key = p.indicator_type.lower().replace(' ', '_')
                        multiplier_value = multipliers.get(indicator_key, multipliers.get('default', 1.0))
                        by_year[y]["multipliers"][p.indicator_type] = multiplier_value
                        
                        # También guardar en formato simple para compatibilidad
                        proyeccion_simple = {
                            "año": y,
                            "sector": p.sector,
                            "indicador": p.indicator_type,
                            "valor_proyectado": format_decimal(p.projected_value),
                            "valor_base": format_decimal(p.base_value),
                            "multiplicador_aplicado": format_decimal(p.multiplier_applied),
                            "valor": format_decimal(p.projected_value)
                        }
                        proyecciones_procesadas.append(proyeccion_simple)
                        
                        # Agrupar por año para resumen
                        if y not in proyecciones_por_año:
                            proyecciones_por_año[y] = {"año": y, "proyecciones": [], "valor_promedio": 0}
                        proyecciones_por_año[y]["proyecciones"].append(proyeccion_simple)
                        
                        # Agrupar por sector
                        if p.sector not in proyecciones_por_sector:
                            proyecciones_por_sector[p.sector] = []
                        proyecciones_por_sector[p.sector].append(proyeccion_simple)
                    
                    # Convertir a lista y agregar multiplicador general
                    data_projections = []
                    for year_data in by_year.values():
                        # Calcular multiplicador promedio para el año
                        if year_data["multipliers"]:
                            avg_multiplier = sum(year_data["multipliers"].values()) / len(year_data["multipliers"])
                        else:
                            avg_multiplier = multipliers.get('default', 1.0)
                        
                        year_data["multiplier"] = avg_multiplier
                        data_projections.append(year_data)
                    
                    data_projections = sorted(data_projections, key=lambda x: x["year"])
                    
                    # Calcular promedio por año
                    for year_data in proyecciones_por_año.values():
                        projs = year_data["proyecciones"]
                        if projs:
                            promedio = sum(p["valor_proyectado"] for p in projs) / len(projs)
                            year_data["valor_promedio"] = format_decimal(promedio)
                else:
                    data_projections = []
                
                # Calcular métricas del escenario
                años_proyectados = sorted(list(set(p.year for p in projections_q))) if projections_q else []
                sectores_cubiertos = list(set(p.sector for p in projections_q)) if projections_q else []
                
                # Calcular crecimiento promedio
                crecimiento_promedio = 0
                if len(projections_q) > 1:
                    crecimientos = []
                    for p in projections_q:
                        if p.base_value > 0:
                            crecimiento = ((p.projected_value - p.base_value) / p.base_value * 100)
                            crecimientos.append(crecimiento)
                    crecimiento_promedio = format_decimal(sum(crecimientos)/len(crecimientos) if crecimientos else 0)
                
                # Obtener documento fuente si existe
                source_document = None
                if scenario.parameters and 'source_document_id' in scenario.parameters:
                    doc_id = scenario.parameters['source_document_id']
                    src_doc = self.db.query(Document).filter(Document.id == doc_id).first()
                    if src_doc:
                        source_document = {
                            "id": src_doc.id,
                            "title": src_doc.title,
                            "filename": src_doc.original_filename,
                            "year": src_doc.year,
                            "sector": src_doc.sector,
                            "core_line": getattr(src_doc, 'core_line', None)
                        }
                
                # Construir datos del escenario en formato compatible con endpoint de detalles
                escenario_data = {
                    "id": scenario.id,
                    "nombre": scenario.name,
                    "name": scenario.name,  # Alias para compatibilidad
                    "tipo": scenario.scenario_type,
                    "scenario_type": scenario.scenario_type,  # Alias para compatibilidad
                    "tipo_clasificado": self._clasificar_tipo_escenario(scenario.scenario_type),
                    "descripcion": scenario.description or f"Escenario {scenario.scenario_type}",
                    "description": scenario.description or f"Escenario {scenario.scenario_type}",  # Alias
                    
                    # Información del creador
                    "created_by": {
                        "id": creator.id if creator else None,
                        "email": creator.email if creator else "Usuario eliminado",
                        "role": creator.role if creator else None,
                        "full_name": f"{creator.first_name} {creator.last_name}".strip() if creator and creator.first_name else (creator.email if creator else "Usuario eliminado")
                    } if creator else None,
                    
                    # Documento fuente
                    "source_document": source_document,
                    
                    # Proyecciones en formato detallado (como endpoint /details)
                    "data": data_projections,
                    
                    # Proyecciones en formato simple (para compatibilidad)
                    "proyecciones": proyecciones_procesadas,
                    "proyecciones_por_año": list(proyecciones_por_año.values()),
                    "proyecciones_por_sector": proyecciones_por_sector,
                    
                    # Parámetros y configuración
                    "parametros_originales": scenario.parameters or {},
                    "parameters": scenario.parameters or {},  # Alias
                    "multipliers": multipliers,
                    "parametros_personalizados": multipliers,
                    
                    # Métricas calculadas
                    "metricas": {
                        "total_proyecciones": len(projections_q) if projections_q else 0,
                        "años_cubiertos": len(años_proyectados),
                        "sectores_cubiertos": len(sectores_cubiertos),
                        "crecimiento_promedio": crecimiento_promedio,
                        "año_inicial": min(años_proyectados) if años_proyectados else None,
                        "año_final": max(años_proyectados) if años_proyectados else None
                    },
                    
                    # Metadata adicional (como endpoint /details)
                    "metadata": {
                        "total_years": len(data_projections),
                        "historical_years": len([p for p in data_projections if p.get('year', 0) <= pd.Timestamp.now().year]),
                        "future_years": len([p for p in data_projections if p.get('year', 0) > pd.Timestamp.now().year]),
                        "indicators": list(data_projections[0].get('values', {}).keys()) if data_projections else []
                    },
                    
                    # Listas auxiliares
                    "años_proyectados": años_proyectados,
                    "sectores": sectores_cubiertos,
                    
                    # Fechas
                    "fecha_creacion": scenario.created_at.isoformat() if scenario.created_at else None,
                    "created_at": scenario.created_at.isoformat() if scenario.created_at else None,  # Alias
                    "fecha_actualizacion": scenario.updated_at.isoformat() if scenario.updated_at else None,
                    "updated_at": scenario.updated_at.isoformat() if scenario.updated_at else None,  # Alias
                    
                    # Color para visualización
                    "color": self._get_scenario_color(scenario.scenario_type)
                }
                
                escenarios_procesados.append(escenario_data)
            
            # Si no hay escenarios, usar datos de muestra
            if not escenarios_procesados:
                escenarios_procesados = self._get_sample_scenarios()
            
            # Calcular resumen general
            total_proyecciones = sum(esc.get('metricas', {}).get('total_proyecciones', 0) for esc in escenarios_procesados)
            sectores_unicos = set()
            for esc in escenarios_procesados:
                sectores_unicos.update(esc.get('sectores', []))
            tipos_escenarios = list(set(esc.get('tipo', '') for esc in escenarios_procesados))
            
            resultado = {
                "prospectiva": {
                    "escenarios": escenarios_procesados,
                    "resumen_general": {
                        "total_escenarios": len(escenarios_procesados),
                        "total_proyecciones": total_proyecciones,
                        "sectores_unicos": len(sectores_unicos),
                        "sectores": list(sectores_unicos),
                        "tipos_escenarios": tipos_escenarios
                    },
                    "tendencias_sectoriales": self._get_tendencias_from_projections(),
                    "factores_clave": self._get_factores_clave_from_scenarios(scenarios)
                }
            }
            
            logger.info(f"Datos de prospectiva recolectados: {len(escenarios_procesados)} escenarios")
            return resultado
        
        except Exception as e:
            logger.error(f"Error recolectando prospectiva: {str(e)}", exc_info=True)
            return {
                "prospectiva": {
                    "escenarios": self._get_sample_scenarios(),
                    "resumen_general": {
                        "total_escenarios": 2,
                        "total_proyecciones": 6,
                        "sectores_unicos": 2,
                        "sectores": ["Tecnología", "Salud"],
                        "tipos_escenarios": ["optimista", "conservador"]
                    },
                    "tendencias_sectoriales": self._get_sample_tendencias(),
                    "factores_clave": [
                        "Transformación digital",
                        "Cambios demográficos",
                        "Sostenibilidad"
                    ]
                }
            }
        
    def _get_scenario_color(self, scenario_type: str) -> str:
        """Retorna color según tipo de escenario"""
        colores = {
            "tendencial": "#3B82F6",
            "optimista": "#10B981",
            "pesimista": "#EF4444",
        }
        return colores.get(scenario_type.lower(), "#6B7280")

    # === OFERTA EDUCATIVA ===
    def _collect_educational_data(self, parametros):
        """MODIFICADO: Retorna estructura consistente con diccionario"""
        try:
            from models import Program
            programas = self.db.query(Program).all()
            programas_procesados = []
            
            total_capacidad = 0
            total_estudiantes = 0
            sectores = set()
            regiones = set()
            
            for prog in programas:
                ocupacion = format_decimal((prog.current_students / prog.capacity * 100) if prog.capacity > 0 else 0)
                programa_data = {
                    "id": prog.id,
                    "codigo": prog.code,
                    "nombre": prog.name,
                    "nivel": prog.level,
                    "sector": prog.sector,
                    "linea_base": prog.core_line,
                    "capacidad": prog.capacity,
                    "estudiantes_actuales": prog.current_students,
                    "ocupacion": ocupacion,
                    "region": prog.region
                }
                programas_procesados.append(programa_data)
                
                total_capacidad += prog.capacity
                total_estudiantes += prog.current_students
                if prog.sector:
                    sectores.add(prog.sector)
                if prog.region:
                    regiones.add(prog.region)
            
            if not programas_procesados:
                programas_procesados = self._get_sample_programs()
            
            ocupacion_promedio = format_decimal((total_estudiantes / total_capacidad * 100) if total_capacidad > 0 else 0)
            
            # ESTRUCTURA NORMALIZADA
            return {
                "oferta_educativa": {
                    "programas": programas_procesados,
                    "resumen": {
                        "total_programas": len(programas_procesados),
                        "programas_activos": len([p for p in programas_procesados if p.get("estudiantes_actuales", 0) > 0]),
                        "capacidad_total": total_capacidad,
                        "estudiantes_totales": total_estudiantes,
                        "ocupacion_promedio": ocupacion_promedio,
                        "sectores_atendidos": len(sectores),
                        "sectores": list(sectores),
                        "regiones_cobertura": len(regiones),
                        "regiones": list(regiones)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error recolectando oferta educativa: {str(e)}")
            sample_programs = self._get_sample_programs()
            return {
                "oferta_educativa": {
                    "programas": sample_programs,
                    "resumen": {
                        "total_programas": len(sample_programs),
                        "programas_activos": 1,
                        "ocupacion_promedio": 60.0,
                        "sectores_atendidos": 1,
                        "sectores": ["Tecnología"]
                    }
                }
            }

    # === MÉTODOS AUXILIARES / MUESTRA DE DATOS ===
    def _get_sample_indicators(self):
        return [
            {
                "id": 1,
                "nombre": "Tasa de graduación",
                "valor_actual": format_decimal(85),
                "meta": format_decimal(90),
                "unidad": "%",
                "cumplimiento": format_decimal(0.944),
                "estado_semaforo": "verde",
                "categoria": "Académico"
            },
            {
                "id": 2,
                "nombre": "Satisfacción estudiantil",
                "valor_actual": format_decimal(78),
                "meta": format_decimal(85),
                "unidad": "%",
                "cumplimiento": format_decimal(0.917),
                "estado_semaforo": "verde",
                "categoria": "Calidad"
            },
            {
                "id": 3,
                "nombre": "Empleabilidad egresados",
                "valor_actual": format_decimal(65),
                "meta": format_decimal(80),
                "unidad": "%",
                "cumplimiento": format_decimal(0.812),
                "estado_semaforo": "amarillo",
                "categoria": "Laboral"
            },
            {
                "id": 4,
                "nombre": "Retención estudiantil",
                "valor_actual": format_decimal(88),
                "meta": format_decimal(95),
                "unidad": "%",
                "cumplimiento": format_decimal(0.926),
                "estado_semaforo": "verde",
                "categoria": "Académico"
            },
            {
                "id": 5,
                "nombre": "Investigación publicada",
                "valor_actual": format_decimal(12),
                "meta": format_decimal(20),
                "unidad": "publicaciones",
                "cumplimiento": format_decimal(0.6),
                "estado_semaforo": "rojo",
                "categoria": "Investigación"
            }
        ]
    
    def _get_sample_dofa(self):
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
        año_actual = datetime.now().year
        
        return [
            {
                "id": 1,
                "nombre": "Escenario Optimista - Crecimiento Acelerado",
                "tipo": "optimista",
                "tipo_clasificado": {
                    "nombre": "Optimista",
                    "color": "#10B981",
                    "nivel_optimismo": "alto"
                },
                "descripcion": "Crecimiento económico acelerado con alta demanda educativa y tecnológica",
                "parametros_originales": {"factor_crecimiento": 1.2},
                "parametros_personalizados": {},
                "proyecciones": [
                    {
                        "año": año_actual + 1,
                        "sector": "Tecnología",
                        "indicador": "Demanda de profesionales",
                        "valor_proyectado": format_decimal(1200),
                        "valor_base": format_decimal(1000),
                        "multiplicador_aplicado": format_decimal(1.2),
                        "valor": format_decimal(1200)
                    },
                    {
                        "año": año_actual + 2,
                        "sector": "Tecnología",
                        "indicador": "Demanda de profesionales",
                        "valor_proyectado": format_decimal(1440),
                        "valor_base": format_decimal(1000),
                        "multiplicador_aplicado": format_decimal(1.44),
                        "valor": format_decimal(1440)
                    },
                    {
                        "año": año_actual + 3,
                        "sector": "Tecnología",
                        "indicador": "Demanda de profesionales",
                        "valor_proyectado": format_decimal(1728),
                        "valor_base": format_decimal(1000),
                        "multiplicador_aplicado": format_decimal(1.728),
                        "valor": format_decimal(1728)
                    }
                ],
                "metricas": {
                    "total_proyecciones": 3,
                    "años_cubiertos": 3,
                    "sectores_cubiertos": 1,
                    "crecimiento_promedio": format_decimal(20.0),
                    "año_inicial": año_actual + 1,
                    "año_final": año_actual + 3
                },
                "años_proyectados": [año_actual + 1, año_actual + 2, año_actual + 3],
                "sectores": ["Tecnología"]
            },
            {
                "id": 2,
                "nombre": "Escenario Conservador - Estabilidad",
                "tipo": "conservador",
                "tipo_clasificado": {
                    "nombre": "Conservador",
                    "color": "#A23B72",
                    "nivel_optimismo": "medio-bajo"
                },
                "descripcion": "Crecimiento moderado con estabilidad en la demanda",
                "parametros_originales": {"factor_crecimiento": 1.05},
                "parametros_personalizados": {},
                "proyecciones": [
                    {
                        "año": año_actual + 1,
                        "sector": "Salud",
                        "indicador": "Demanda de servicios",
                        "valor_proyectado": format_decimal(840),
                        "valor_base": format_decimal(800),
                        "multiplicador_aplicado": format_decimal(1.05),
                        "valor": format_decimal(840)
                    },
                    {
                        "año": año_actual + 2,
                        "sector": "Salud",
                        "indicador": "Demanda de servicios",
                        "valor_proyectado": format_decimal(882),
                        "valor_base": format_decimal(800),
                        "multiplicador_aplicado": format_decimal(1.1025),
                        "valor": format_decimal(882)
                    },
                    {
                        "año": año_actual + 3,
                        "sector": "Salud",
                        "indicador": "Demanda de servicios",
                        "valor_proyectado": format_decimal(926),
                        "valor_base": format_decimal(800),
                        "multiplicador_aplicado": format_decimal(1.1576),
                        "valor": format_decimal(926)
                    }
                ],
                "metricas": {
                    "total_proyecciones": 3,
                    "años_cubiertos": 3,
                    "sectores_cubiertos": 1,
                    "crecimiento_promedio": format_decimal(5.0),
                    "año_inicial": año_actual + 1,
                    "año_final": año_actual + 3
                },
                "años_proyectados": [año_actual + 1, año_actual + 2, año_actual + 3],
                "sectores": ["Salud"]
            }
        ]
    
    def _get_sample_tendencias(self):
        return [
            {
                "sector": "Tecnología",
                "crecimiento_esperado": format_decimal(15.2),
                "demanda": "Alta",
                "factores": ["Digitalización", "IA", "Cloud Computing"],
                "valor_promedio_proyectado": format_decimal(1250.0),
                "total_proyecciones": 10
            },
            {
                "sector": "Salud",
                "crecimiento_esperado": format_decimal(12.8),
                "demanda": "Alta",
                "factores": ["Envejecimiento poblacional", "Telemedicina"],
                "valor_promedio_proyectado": format_decimal(850.0),
                "total_proyecciones": 8
            },
            {
                "sector": "Educación",
                "crecimiento_esperado": format_decimal(8.5),
                "demanda": "Alta",
                "factores": ["Educación virtual", "Competencias digitales"],
                "valor_promedio_proyectado": format_decimal(620.0),
                "total_proyecciones": 12
            }
        ]
    
    def _get_sample_programs(self):
        return [
            {
                "id": 1,
                "codigo": "P001",
                "nombre": "Programa Ejemplo",
                "nivel": "Tecnólogo",
                "sector": "Tecnología",
                "linea_base": "Desarrollo Software",
                "capacidad": 50,
                "estudiantes_actuales": 30,
                "ocupacion": format_decimal(60.0),
                "region": "Bogotá"
            }
        ]
    
    def _clasificar_tipo_escenario(self, tipo: str) -> Dict[str, Any]:
        """Clasifica y enriquece información del tipo de escenario"""
        clasificaciones = {
            "tendencial": {
                "nombre": "Tendencial",
                "color": "#3B82F6",
                "icono": "trending_flat",
                "descripcion_corta": "Continuidad de tendencias actuales",
                "nivel_optimismo": "neutral"
            },
            "optimista": {
                "nombre": "Optimista",
                "color": "#10B981",
                "icono": "trending_up",
                "descripcion_corta": "Escenario favorable con crecimiento",
                "nivel_optimismo": "alto"
            },
            "pesimista": {
                "nombre": "Pesimista",
                "color": "#EF4444",
                "icono": "trending_down",
                "descripcion_corta": "Escenario desfavorable con decrecimiento",
                "nivel_optimismo": "bajo"
            },
            "conservador": {
                "nombre": "Conservador",
                "color": "#A23B72",
                "icono": "radio_button_checked",
                "descripcion_corta": "Escenario moderado con estabilidad",
                "nivel_optimismo": "medio-bajo"
            }
        }
        
        return clasificaciones.get(tipo.lower(), {
            "nombre": tipo.title(),
            "color": "#6B7280",
            "icono": "help",
            "descripcion_corta": "Escenario personalizado",
            "nivel_optimismo": "no definido"
        })

    def _get_tendencias_from_projections(self):
        """Calcula tendencias sectoriales mejoradas"""
        try:
            from models import ScenarioProjection, Scenario
            
            projections = self.db.query(ScenarioProjection).join(
                Scenario, Scenario.id == ScenarioProjection.scenario_id
            ).filter(Scenario.is_active == True).all()
            
            if not projections:
                return self._get_sample_tendencias()
            
            # Agrupar por sector
            sectores_data = {}
            for proj in projections:
                if proj.sector not in sectores_data:
                    sectores_data[proj.sector] = {
                        "proyecciones": [],
                        "indicadores": set()
                    }
                sectores_data[proj.sector]["proyecciones"].append(proj)
                sectores_data[proj.sector]["indicadores"].add(proj.indicator_type)
            
            tendencias = []
            for sector, data in sectores_data.items():
                proyecciones = data["proyecciones"]
                
                if len(proyecciones) < 1:
                    continue
                
                # Calcular crecimiento promedio
                crecimientos = []
                for proj in proyecciones:
                    if proj.base_value > 0:
                        crecimiento = ((proj.projected_value - proj.base_value) / proj.base_value * 100)
                        crecimientos.append(crecimiento)
                
                crecimiento_promedio = format_decimal(sum(crecimientos) / len(crecimientos) if crecimientos else 0)
                
                # Determinar nivel de demanda
                if crecimiento_promedio > 10:
                    demanda = "Alta"
                elif crecimiento_promedio > 5:
                    demanda = "Media"
                elif crecimiento_promedio > 0:
                    demanda = "Baja"
                else:
                    demanda = "Decreciente"
                
                # Valor promedio proyectado
                valor_promedio = sum(proj.projected_value for proj in proyecciones) / len(proyecciones)
                
                tendencias.append({
                    "sector": sector,
                    "crecimiento_esperado": crecimiento_promedio,
                    "demanda": demanda,
                    "factores": list(data["indicadores"])[:3],
                    "valor_promedio_proyectado": format_decimal(valor_promedio),
                    "total_proyecciones": len(proyecciones)
                })
            
            return tendencias if tendencias else self._get_sample_tendencias()
            
        except Exception as e:
            logger.error(f"Error calculando tendencias: {str(e)}")
            return self._get_sample_tendencias()

    def _get_factores_clave_from_scenarios(self, scenarios):
        """Extrae factores clave de los escenarios"""
        factores_clave = set()
        
        for scenario in scenarios:
            # Desde parámetros
            if scenario.parameters and isinstance(scenario.parameters, dict):
                for key, value in scenario.parameters.items():
                    if 'factor' in key.lower() or 'tendencia' in key.lower():
                        if isinstance(value, str) and len(value) > 5:
                            factores_clave.add(value)
            
            # Desde descripción
            if scenario.description:
                # Extraer frases clave de la descripción
                palabras_clave = ['crecimiento', 'desarrollo', 'transformación', 'cambio', 'innovación']
                for palabra in palabras_clave:
                    if palabra in scenario.description.lower():
                        factores_clave.add(f"{palabra.title()} identificado en {scenario.name}")
        
        # Si no hay factores, usar valores por defecto
        if not factores_clave:
            factores_clave = {
                "Transformación digital acelerada",
                "Cambios en el mercado laboral",
                "Nuevas competencias requeridas",
                "Sostenibilidad ambiental",
                "Innovación tecnológica"
            }
        
        return list(factores_clave)[:8]

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