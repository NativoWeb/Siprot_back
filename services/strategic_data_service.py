from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from models import (
    Indicador, DofaItem, Scenario, ScenarioProjection, Program, 
    Document, DemandIndicator, AuditLog, User
)
from schemas import (
    TipoReporte, ParametrosReporte, IndicadorResponse, 
    DofaMatrixResponse, ScenarioProjectionResponse
)

class StrategicDataService:
    """Servicio integrado para recopilar datos de todos los módulos del sistema"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def recopilar_datos_consolidados(
        self, 
        tipo: TipoReporte, 
        parametros: ParametrosReporte
    ) -> Dict[str, Any]:
        """Método principal para recopilar datos consolidados de la base de datos"""
        
        if tipo == TipoReporte.INDICADORES:
            return self._obtener_datos_indicadores(parametros)
        elif tipo == TipoReporte.PROSPECTIVA:
            return self._obtener_datos_prospectiva(parametros)
        elif tipo == TipoReporte.OFERTA_EDUCATIVA:
            return self._obtener_datos_oferta_educativa(parametros)
        elif tipo == TipoReporte.CONSOLIDADO:
            return self._obtener_datos_consolidados(parametros)
        else:
            return {"error": "Tipo de reporte no válido"}
    
    def _obtener_datos_indicadores(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Obtiene datos reales de indicadores desde la base de datos"""
        
        query = self.db.query(Indicador).filter(Indicador.activo == True)
        
        # Aplicar filtros de fecha si se especifican
        if parametros.fecha_inicio:
            query = query.filter(Indicador.fecha_actualizacion >= parametros.fecha_inicio)
        if parametros.fecha_fin:
            query = query.filter(Indicador.fecha_actualizacion <= parametros.fecha_fin)
        
        # Filtrar indicadores seleccionados
        if parametros.indicadores_seleccionados:
            query = query.filter(Indicador.nombre.in_(parametros.indicadores_seleccionados))
        
        indicadores_db = query.all()
        
        # Convertir a IndicadorResponse con cálculos
        indicadores = []
        for ind in indicadores_db:
            cumplimiento = (ind.valor_actual / ind.meta) if ind.meta > 0 else 0
            
            if cumplimiento >= 0.9:
                estado_semaforo = "verde"
            elif cumplimiento >= 0.7:
                estado_semaforo = "amarillo"
            else:
                estado_semaforo = "rojo"
            
            indicador_response = IndicadorResponse(
                id=ind.id,
                nombre=ind.nombre,
                valor_actual=ind.valor_actual,
                meta=ind.meta,
                unidad=ind.unidad,
                tendencia=ind.tendencia or "estable",
                descripcion=ind.descripcion,
                categoria=ind.categoria or "General",
                fecha_actualizacion=ind.fecha_actualizacion,
                cumplimiento=round(cumplimiento, 2),
                estado_semaforo=estado_semaforo
            )
            indicadores.append(indicador_response)
        
        # Calcular estadísticas
        total = len(indicadores)
        verde = len([i for i in indicadores if i.estado_semaforo == "verde"])
        amarillo = len([i for i in indicadores if i.estado_semaforo == "amarillo"])
        rojo = len([i for i in indicadores if i.estado_semaforo == "rojo"])
        
        # Estadísticas por categoría
        categorias = {}
        for ind in indicadores:
            if ind.categoria not in categorias:
                categorias[ind.categoria] = {"total": 0, "cumplimiento_promedio": 0}
            categorias[ind.categoria]["total"] += 1
            categorias[ind.categoria]["cumplimiento_promedio"] += ind.cumplimiento
        
        for cat in categorias:
            if categorias[cat]["total"] > 0:
                categorias[cat]["cumplimiento_promedio"] = round(
                    categorias[cat]["cumplimiento_promedio"] / categorias[cat]["total"], 2
                )
        
        return {
            "indicadores": indicadores,
            "resumen": {
                "total_indicadores": total,
                "verde": verde,
                "amarillo": amarillo,
                "rojo": rojo,
                "cumplimiento_general": round((verde / total * 100) if total > 0 else 0, 1)
            },
            "categorias": categorias,
            "periodo": {
                "inicio": parametros.fecha_inicio or datetime(2024, 1, 1),
                "fin": parametros.fecha_fin or datetime.now()
            },
            "comentarios": parametros.comentarios_analista or "",
            "ultima_actualizacion": datetime.now()
        }
    
    def _obtener_datos_prospectiva(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Obtiene datos reales de escenarios prospectivos desde la base de datos"""
        
        escenarios_db = self.db.query(Scenario).filter(Scenario.is_active == True).all()
        
        escenarios_procesados = []
        for escenario in escenarios_db:
            # Obtener proyecciones asociadas
            proyecciones = self.db.query(ScenarioProjection).filter(
                ScenarioProjection.scenario_id == escenario.id
            ).all()
            
            # Calcular probabilidad basada en parámetros
            params = escenario.parameters or {}
            probabilidad = self._calcular_probabilidad_escenario(escenario.scenario_type, params)
            
            escenario_data = {
                "id": escenario.id,
                "nombre": escenario.name,
                "tipo": escenario.scenario_type,
                "descripcion": escenario.description or f"Escenario {escenario.scenario_type}",
                "probabilidad": probabilidad,
                "impacto": self._determinar_impacto(escenario.scenario_type),
                "parametros": params,
                "proyecciones_count": len(proyecciones),
                "recomendaciones": self._generar_recomendaciones_escenario(escenario.scenario_type)
            }
            escenarios_procesados.append(escenario_data)
        
        # Obtener tendencias sectoriales desde indicadores de demanda
        tendencias = self._obtener_tendencias_sectoriales()
        
        # Obtener documentos relevantes para prospectiva
        documentos_prospectiva = self.db.query(Document).filter(
            and_(
                Document.document_type.ilike('%prospectiva%'),
                Document.year >= datetime.now().year - 2
            )
        ).limit(5).all()
        
        return {
            "escenarios": escenarios_procesados,
            "tendencias_sectoriales": tendencias,
            "horizonte_temporal": "2025-2030",
            "factores_clave": [
                "Transformación digital",
                "Sostenibilidad ambiental", 
                "Demografía laboral",
                "Políticas públicas",
                "Innovación tecnológica"
            ],
            "documentos_referencia": [
                {
                    "titulo": doc.title,
                    "año": doc.year,
                    "sector": doc.sector
                } for doc in documentos_prospectiva
            ],
            "ultima_actualizacion": datetime.now()
        }
    
    def _obtener_datos_oferta_educativa(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Obtiene datos reales de programas educativos desde la base de datos"""
        
        query = self.db.query(Program).filter(Program.is_active == True)
        
        # Aplicar filtros de fecha si se especifican
        if parametros.fecha_inicio:
            query = query.filter(Program.program_date >= parametros.fecha_inicio)
        if parametros.fecha_fin:
            query = query.filter(Program.program_date <= parametros.fecha_fin)
        
        programas = query.all()
        
        # Agrupar por sector
        programas_por_sector = {}
        for programa in programas:
            sector = programa.sector
            if sector not in programas_por_sector:
                programas_por_sector[sector] = {
                    "sector": sector,
                    "programas_activos": 0,
                    "cupos": 0,
                    "estudiantes_actuales": 0,
                    "ocupacion": 0
                }
            
            programas_por_sector[sector]["programas_activos"] += 1
            programas_por_sector[sector]["cupos"] += programa.capacity or 0
            programas_por_sector[sector]["estudiantes_actuales"] += programa.current_students or 0
        
        # Calcular ocupación por sector
        for sector_data in programas_por_sector.values():
            if sector_data["cupos"] > 0:
                sector_data["ocupacion"] = round(
                    (sector_data["estudiantes_actuales"] / sector_data["cupos"]) * 100, 1
                )
        
        programas_por_sector_list = list(programas_por_sector.values())
        
        # Identificar brechas formativas basadas en indicadores de demanda
        brechas = self._identificar_brechas_formativas()
        
        # Calcular totales
        total_programas = len(programas)
        total_cupos = sum(p.capacity or 0 for p in programas)
        total_estudiantes = sum(p.current_students or 0 for p in programas)
        ocupacion_promedio = round((total_estudiantes / total_cupos * 100) if total_cupos > 0 else 0, 1)
        
        return {
            "programas_por_sector": programas_por_sector_list,
            "brechas_formativas": brechas,
            "total_programas": total_programas,
            "total_cupos": total_cupos,
            "total_estudiantes": total_estudiantes,
            "ocupacion_promedio": ocupacion_promedio,
            "programas_por_nivel": self._obtener_distribucion_por_nivel(programas),
            "ultima_actualizacion": datetime.now()
        }
    
    def _obtener_datos_consolidados(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Obtiene datos consolidados de todos los módulos"""
        
        dofa_items = self.db.query(DofaItem).filter(DofaItem.is_active == True).all()
        
        dofa_consolidado = {
            "fortalezas": [item.text for item in dofa_items if item.category == "F"],
            "oportunidades": [item.text for item in dofa_items if item.category == "O"],
            "debilidades": [item.text for item in dofa_items if item.category == "D"],
            "amenazas": [item.text for item in dofa_items if item.category == "A"]
        }
        
        return {
            "indicadores": self._obtener_datos_indicadores(parametros),
            "prospectiva": self._obtener_datos_prospectiva(parametros),
            "oferta_educativa": self._obtener_datos_oferta_educativa(parametros),
            "analisis_dofa": dofa_consolidado,
            "resumen_ejecutivo": dofa_consolidado,  # Mantener compatibilidad
            "documentos_recientes": self._obtener_documentos_recientes(),
            "estadisticas_sistema": self._obtener_estadisticas_sistema(),
            "ultima_actualizacion": datetime.now()
        }
    
    def _calcular_probabilidad_escenario(self, tipo_escenario: str, parametros: Dict) -> int:
        """Calcula probabilidad basada en el tipo de escenario y parámetros"""
        probabilidades_base = {
            "optimista": 25,
            "tendencial": 50, 
            "pesimista": 25
        }
        
        # Ajustar basado en parámetros económicos
        probabilidad = probabilidades_base.get(tipo_escenario, 33)
        
        if parametros:
            factor_economico = parametros.get("economic_factor", 1.0)
            if factor_economico > 1.5:
                probabilidad += 10 if tipo_escenario == "optimista" else -5
            elif factor_economico < 0.8:
                probabilidad += 10 if tipo_escenario == "pesimista" else -5
        
        return max(5, min(95, probabilidad))
    
    def _determinar_impacto(self, tipo_escenario: str) -> str:
        """Determina el impacto basado en el tipo de escenario"""
        impactos = {
            "optimista": "Alto",
            "tendencial": "Medio",
            "pesimista": "Bajo"
        }
        return impactos.get(tipo_escenario, "Medio")
    
    def _generar_recomendaciones_escenario(self, tipo_escenario: str) -> List[str]:
        """Genera recomendaciones específicas por tipo de escenario"""
        recomendaciones = {
            "optimista": [
                "Ampliar oferta formativa en sectores emergentes",
                "Fortalecer alianzas estratégicas con empresas",
                "Invertir en infraestructura tecnológica avanzada",
                "Desarrollar programas de innovación"
            ],
            "tendencial": [
                "Mantener calidad de programas actuales",
                "Diversificar oferta gradualmente",
                "Optimizar recursos existentes",
                "Fortalecer seguimiento a egresados"
            ],
            "pesimista": [
                "Consolidar programas más demandados",
                "Reducir costos operativos",
                "Buscar nuevos nichos de mercado",
                "Implementar modalidades virtuales"
            ]
        }
        return recomendaciones.get(tipo_escenario, [])
    
    def _obtener_tendencias_sectoriales(self) -> List[Dict[str, Any]]:
        """Obtiene tendencias sectoriales desde indicadores de demanda"""
        
        # Query de indicadores de demanda por sector
        demanda_query = self.db.query(
            DemandIndicator.sector,
            func.avg(DemandIndicator.demand_value).label('demanda_promedio'),
            func.count(DemandIndicator.id).label('registros')
        ).filter(
            DemandIndicator.year >= datetime.now().year - 2
        ).group_by(DemandIndicator.sector).all()
        
        tendencias = []
        for sector, demanda_prom, registros in demanda_query:
            # Calcular crecimiento esperado basado en demanda
            crecimiento = min(30, max(0, (demanda_prom or 0) / 10))
            
            # Determinar nivel de demanda
            if demanda_prom and demanda_prom > 80:
                nivel_demanda = "Alta"
            elif demanda_prom and demanda_prom > 50:
                nivel_demanda = "Media"
            else:
                nivel_demanda = "Baja"
            
            tendencias.append({
                "sector": sector,
                "crecimiento_esperado": round(crecimiento, 1),
                "demanda": nivel_demanda,
                "registros_base": registros
            })
        
        return tendencias
    
    def _identificar_brechas_formativas(self) -> List[Dict[str, Any]]:
        """Identifica brechas formativas comparando demanda vs oferta"""
        
        # Obtener demanda por área/sector
        demanda_areas = self.db.query(
            DemandIndicator.sector,
            func.sum(DemandIndicator.demand_value).label('demanda_total')
        ).filter(
            DemandIndicator.year >= datetime.now().year - 1
        ).group_by(DemandIndicator.sector).all()
        
        # Obtener oferta actual por sector
        oferta_sectores = self.db.query(
            Program.sector,
            func.sum(Program.capacity).label('oferta_total')
        ).filter(Program.is_active == True).group_by(Program.sector).all()
        
        # Crear diccionario de oferta
        oferta_dict = {sector: oferta for sector, oferta in oferta_sectores}
        
        brechas = []
        for sector, demanda in demanda_areas:
            oferta = oferta_dict.get(sector, 0) or 0
            brecha = max(0, (demanda or 0) - oferta)
            
            if brecha > 50:  # Solo mostrar brechas significativas
                brechas.append({
                    "area": sector,
                    "demanda": int(demanda or 0),
                    "oferta": int(oferta),
                    "brecha": int(brecha)
                })
        
        return sorted(brechas, key=lambda x: x["brecha"], reverse=True)[:10]
    
    def _obtener_distribucion_por_nivel(self, programas: List[Program]) -> Dict[str, int]:
        """Obtiene distribución de programas por nivel educativo"""
        distribucion = {}
        for programa in programas:
            nivel = programa.level or "No especificado"
            distribucion[nivel] = distribucion.get(nivel, 0) + 1
        return distribucion
    
    def _obtener_documentos_recientes(self) -> List[Dict[str, Any]]:
        """Obtiene documentos recientes relevantes"""
        documentos = self.db.query(Document).filter(
            Document.uploaded_at >= datetime.now() - timedelta(days=90)
        ).order_by(desc(Document.uploaded_at)).limit(10).all()
        
        return [
            {
                "titulo": doc.title,
                "tipo": doc.document_type,
                "sector": doc.sector,
                "año": doc.year,
                "fecha_subida": doc.uploaded_at.strftime("%d/%m/%Y")
            } for doc in documentos
        ]
    
    def _obtener_estadisticas_sistema(self) -> Dict[str, Any]:
        """Obtiene estadísticas generales del sistema"""
        
        # Contar registros por tabla principal
        total_indicadores = self.db.query(Indicador).filter(Indicador.activo == True).count()
        total_programas = self.db.query(Program).filter(Program.is_active == True).count()
        total_escenarios = self.db.query(Scenario).filter(Scenario.is_active == True).count()
        total_documentos = self.db.query(Document).count()
        total_usuarios = self.db.query(User).filter(User.is_active == True).count()
        
        # Actividad reciente (últimos 30 días)
        fecha_limite = datetime.now() - timedelta(days=30)
        actividad_reciente = self.db.query(AuditLog).filter(
            AuditLog.timestamp >= fecha_limite
        ).count()
        
        return {
            "total_indicadores": total_indicadores,
            "total_programas": total_programas,
            "total_escenarios": total_escenarios,
            "total_documentos": total_documentos,
            "total_usuarios": total_usuarios,
            "actividad_reciente_30d": actividad_reciente,
            "fecha_estadisticas": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
    
    def registrar_generacion_reporte(
        self, 
        usuario_id: int, 
        tipo_reporte: str, 
        parametros: Dict[str, Any],
        ip_address: str = None,
        user_agent: str = None
    ):
        """Registra la generación de un reporte en el log de auditoría"""
        
        audit_log = AuditLog(
            user_id=usuario_id,
            action="GENERAR_REPORTE",
            resource_type="reporte",
            resource_id=tipo_reporte,
            new_values=parametros,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "tipo_reporte": tipo_reporte,
                "parametros": parametros,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        self.db.add(audit_log)
        self.db.commit()
