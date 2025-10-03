import os
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models import Reporte
from schemas import TipoReporte, ParametrosReporte, EstadoReporte
from services.pdf_service import PDFService
from services.data_collector_service import IntegratedDataCollectorService
from database import SessionLocal
import logging

logger = logging.getLogger(__name__)

class ImprovedReportService:
    def __init__(self, db: Session):
        self.db = db
        self.data_collector = IntegratedDataCollectorService(db)
        self.pdf_service = PDFService()
    
    def generar_reporte_background(
        self,
        reporte_id: int,
        tipo: TipoReporte,
        parametros: ParametrosReporte,
        usuario_id: Optional[int] = None
    ):
        db = SessionLocal()
        temp_file_path = None
        
        try:
            reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
            if not reporte:
                raise Exception(f"Reporte {reporte_id} no encontrado")
            
            reporte.estado = EstadoReporte.GENERANDO.value
            db.commit()
            
            logger.info(f"Iniciando generación de reporte {reporte_id} tipo {tipo}")
            
            # 1. Recolectar datos
            datos_consolidados = self.data_collector.collect_consolidated_data(tipo, parametros)
            
            # 2. Validar
            validacion = self._validate_collected_data(datos_consolidados, tipo)
            if not validacion["valido"]:
                raise Exception(f"Datos no válidos: {validacion['errores']}")
            
            # 3. Procesar
            datos_procesados = self._process_data_for_report_type(datos_consolidados, tipo, parametros)
            
            # 4. Generar PDF
            temp_file_path = self.pdf_service.generar_pdf(
                tipo, 
                datos_procesados, 
                parametros, 
                reporte_id
            )
            
            # 5. Guardar en BD
            if os.path.exists(temp_file_path):
                with open(temp_file_path, 'rb') as pdf_file:
                    pdf_content = pdf_file.read()
                
                reporte.archivo_contenido = pdf_content
                reporte.archivo_nombre = f"reporte_{reporte_id}_{tipo.value}.pdf"
                reporte.archivo_path = temp_file_path
                reporte.tamaño_archivo = len(pdf_content)
                reporte.estado = EstadoReporte.COMPLETADO.value
                reporte.datos_utilizados = self._serialize_metadata(datos_consolidados)
                reporte.estadisticas_generacion = self._generate_generation_stats(datos_consolidados)
            else:
                raise Exception("El archivo PDF no fue generado correctamente")
            
            reporte.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Reporte {reporte_id} generado exitosamente")
            self._log_successful_generation(db, reporte_id, tipo, usuario_id, datos_consolidados)
            
        except Exception as e:
            logger.error(f"Error generando reporte {reporte_id}: {str(e)}")
            if 'reporte' in locals():
                reporte.estado = EstadoReporte.ERROR.value
                reporte.mensaje_error = str(e)
                reporte.updated_at = datetime.utcnow()
                db.commit()
            self._log_failed_generation(db, reporte_id, tipo, usuario_id, str(e))
            raise
        finally:
            db.close()
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    def _validate_collected_data(self, datos: Dict[str, Any], tipo: TipoReporte) -> Dict[str, Any]:
        validacion = {"valido": True, "errores": [], "advertencias": []}
        try:
            if not datos:
                return {"valido": False, "errores": ["No se recolectaron datos"]}
            if "error" in datos:
                return {"valido": False, "errores": [f"Error en recolección: {datos['error']}"]}
            
            if tipo == TipoReporte.INDICADORES:
                indicadores = datos.get("indicadores", {}).get("lista", [])
                if not indicadores:
                    validacion["errores"].append("No se encontraron indicadores")
                    validacion["valido"] = False
            elif tipo == TipoReporte.PROSPECTIVA:
                escenarios = datos.get("escenarios") or datos.get("prospectiva", {}).get("escenarios")
                if not escenarios:
                    validacion["errores"].append("No se encontraron escenarios prospectivos")
                    validacion["valido"] = False
            elif tipo == TipoReporte.OFERTA_EDUCATIVA:
                if not datos.get("oferta_educativa", {}).get("total_programas", 0):
                    validacion["errores"].append("No se encontraron programas educativos")
                    validacion["valido"] = False
            elif tipo == TipoReporte.CONSOLIDADO:
                modulos_requeridos = ["indicadores", "dofa", "prospectiva", "oferta_educativa"]
                modulos_presentes = [m for m in modulos_requeridos if datos.get(m)]
                if len(modulos_presentes) < 2:
                    validacion["errores"].append("Datos insuficientes para reporte consolidado")
                    validacion["valido"] = False
        except Exception as e:
            return {"valido": False, "errores": [f"Error en validación: {str(e)}"]}
        return validacion
    
    def _process_data_for_report_type(self, datos: Dict[str, Any], tipo: TipoReporte, parametros: ParametrosReporte) -> Dict[str, Any]:
        if tipo == TipoReporte.CONSOLIDADO:
            return self._process_consolidated_report_data(datos, parametros)
        elif tipo == TipoReporte.INDICADORES:
            return self._process_indicators_report_data(datos, parametros)
        elif tipo == TipoReporte.PROSPECTIVA:
            return self._process_prospective_report_data(datos, parametros)
        elif tipo == TipoReporte.OFERTA_EDUCATIVA:
            return self._process_educational_offer_data(datos, parametros)
        return datos
    
    def obtener_progreso_reporte(self, reporte_id: int) -> Dict[str, Any]:
        reporte = self.db.query(Reporte).filter(Reporte.id == reporte_id).first()
        if not reporte:
            return {"error": "Reporte no encontrado"}
        return {
            "id": reporte.id,
            "estado": reporte.estado,
            "archivo_disponible": bool(reporte.archivo_contenido),
            "mensaje_error": getattr(reporte, 'mensaje_error', None),
            "progreso_estimado": 100 if reporte.estado == "completado" else 50,
            "estadisticas": getattr(reporte, 'estadisticas_generacion', {})
        }
    
    def _process_consolidated_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        indicadores_data = datos.get("indicadores", {})
        dofa_data = datos.get("dofa", {})
        prospectiva_data = datos.get("prospectiva", {})
        oferta_data = datos.get("oferta_educativa", {})
        
        return {
            "portada": {
                "titulo": "Informe Estratégico Consolidado",
                "subtitulo": "Análisis Integral del Sistema",
                "periodo": parametros.periodo if hasattr(parametros, 'periodo') else "2024",
                "version": "1.0",
                "fecha": datetime.now()
            },
            "resumen_ejecutivo": self._generate_executive_summary(datos),
            "analisis_dofa": dofa_data,
            "indicadores_estrategicos": indicadores_data,
            "escenarios_prospectivos": prospectiva_data,
            "oferta_educativa": oferta_data,
            "documentos_relevantes": datos.get("documentos", {}),
            "conclusiones": self._generate_conclusions(datos)
        }
    
    def _process_indicators_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        indicadores_data = datos.get("indicadores", {})
        dofa_data = datos.get("dofa", {})
        escenarios_data = datos.get("prospectiva", {})
        oferta_data = datos.get("oferta_educativa", {})
        
        return {
            "tipo_reporte": "indicadores",
            "indicadores": indicadores_data.get("lista", []),
            "resumen": indicadores_data.get("resumen", {}),
            "oferta_educativa": oferta_data,
            "analisis_dofa": dofa_data,
            "escenarios_prospectivos": escenarios_data
        }
    
    def _process_prospective_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        prospectiva_data = datos.get("prospectiva", {})
        dofa_data = datos.get("dofa", {})
        
        return {
            "tipo_reporte": "prospectiva",
            "prospectiva": prospectiva_data,
            "analisis_dofa": dofa_data
        }
    
    def _process_educational_offer_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        oferta_data = datos.get("oferta_educativa", {})
        
        return {
            "tipo_reporte": "oferta_educativa",
            "oferta_educativa": oferta_data
        }
    
    def _generate_executive_summary(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        indicadores = datos.get("indicadores", {})
        dofa = datos.get("dofa", {})
        prospectiva = datos.get("prospectiva", {})
        oferta = datos.get("oferta_educativa", {})
        
        resumen_ind = indicadores.get("resumen", {})
        cumplimiento = resumen_ind.get("cumplimiento_general", 0)
        
        mensaje = f"""
        El presente informe consolidado presenta un análisis integral del sistema estratégico.
        
        En términos de indicadores, se observa un cumplimiento general del {cumplimiento}% con 
        {resumen_ind.get('verde', 0)} indicadores en estado óptimo, {resumen_ind.get('amarillo', 0)} 
        en estado de alerta y {resumen_ind.get('rojo', 0)} requiriendo atención inmediata.
        
        La oferta educativa cuenta con {oferta.get('total_programas', 0)} programas activos 
        atendiendo {oferta.get('sectores_atendidos', 0)} sectores estratégicos, con una ocupación 
        promedio del {oferta.get('ocupacion_promedio', 0)}%.
        
        El análisis prospectivo contempla {prospectiva.get('resumen_general', {}).get('total_escenarios', 0)} 
        escenarios estratégicos con proyecciones en múltiples sectores.
        """
        
        sintesis = {
            "fortalezas_clave": dofa.get("fortalezas", [])[:3],
            "oportunidades_principales": dofa.get("oportunidades", [])[:3],
            "riesgos_identificados": dofa.get("amenazas", [])[:3],
            "areas_mejora": dofa.get("debilidades", [])[:3]
        }
        
        prioridades = [
            "Fortalecer indicadores en estado crítico",
            "Optimizar ocupación de programas educativos",
            "Implementar estrategias de los escenarios prospectivos",
            "Mitigar riesgos identificados en análisis DOFA"
        ]
        
        return {
            "mensaje_ejecutivo": mensaje.strip(),
            "sintesis_estrategica": sintesis,
            "prioridades_estrategicas": prioridades
        }
    
    def _serialize_metadata(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        try:
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "modulos_incluidos": list(datos.keys()),
                "resumen": {}
            }
            
            if "indicadores" in datos:
                ind_data = datos["indicadores"]
                metadata["resumen"]["indicadores"] = {
                    "total": ind_data.get("resumen", {}).get("total_indicadores", 0),
                    "cumplimiento": ind_data.get("resumen", {}).get("cumplimiento_general", 0)
                }
            
            if "prospectiva" in datos:
                prosp_data = datos["prospectiva"]
                metadata["resumen"]["prospectiva"] = {
                    "total_escenarios": prosp_data.get("resumen_general", {}).get("total_escenarios", 0),
                    "total_proyecciones": prosp_data.get("resumen_general", {}).get("total_proyecciones", 0)
                }
            
            if "oferta_educativa" in datos:
                oferta_data = datos["oferta_educativa"]
                metadata["resumen"]["oferta_educativa"] = {
                    "total_programas": oferta_data.get("total_programas", 0),
                    "ocupacion_promedio": oferta_data.get("ocupacion_promedio", 0)
                }
            
            return metadata
        except Exception as e:
            logger.error(f"Error serializando metadata: {str(e)}")
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}
    
    def _generate_generation_stats(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        try:
            stats = {
                "fecha_generacion": datetime.now().isoformat(),
                "modulos_procesados": len(datos),
                "total_elementos": 0
            }
            
            if "indicadores" in datos:
                stats["total_elementos"] += len(datos["indicadores"].get("lista", []))
            
            if "prospectiva" in datos:
                stats["total_elementos"] += len(datos["prospectiva"].get("escenarios", []))
            
            if "dofa" in datos:
                dofa = datos["dofa"]
                stats["total_elementos"] += sum([
                    len(dofa.get("fortalezas", [])),
                    len(dofa.get("oportunidades", [])),
                    len(dofa.get("debilidades", [])),
                    len(dofa.get("amenazas", []))
                ])
            
            return stats
        except Exception as e:
            logger.error(f"Error generando estadísticas: {str(e)}")
            return {"fecha_generacion": datetime.now().isoformat(), "error": str(e)}
    
    def _log_successful_generation(self, db: Session, reporte_id: int, tipo: TipoReporte, usuario_id: Optional[int], datos: Dict[str, Any]):
        try:
            logger.info(f"✅ Reporte {reporte_id} generado exitosamente")
            logger.info(f"   Tipo: {tipo.value}")
            logger.info(f"   Usuario: {usuario_id}")
            logger.info(f"   Módulos incluidos: {list(datos.keys())}")
        except Exception as e:
            logger.error(f"Error en log de generación exitosa: {str(e)}")
    
    def _log_failed_generation(self, db: Session, reporte_id: int, tipo: TipoReporte, usuario_id: Optional[int], error: str):
        try:
            logger.error(f"❌ Falla en generación de reporte {reporte_id}")
            logger.error(f"   Tipo: {tipo.value}")
            logger.error(f"   Usuario: {usuario_id}")
            logger.error(f"   Error: {error}")
        except Exception as e:
            logger.error(f"Error en log de generación fallida: {str(e)}")
    
    def _generate_conclusions(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        conclusiones_principales = [
            "El sistema presenta un desempeño general satisfactorio con áreas de oportunidad identificadas",
            "La oferta educativa requiere ajustes para optimizar la ocupación y cobertura sectorial",
            "Los escenarios prospectivos señalan tendencias que deben ser consideradas en la planificación",
            "El análisis DOFA revela fortalezas aprovechables y debilidades que requieren atención"
        ]
        
        recomendaciones = {
            "corto_plazo": [
                "Implementar planes de acción para indicadores críticos",
                "Revisar capacidad y demanda de programas educativos",
                "Fortalecer áreas identificadas como debilidades"
            ],
            "mediano_plazo": [
                "Desarrollar estrategias basadas en escenarios prospectivos",
                "Expandir oferta educativa en sectores de alta demanda",
                "Consolidar fortalezas institucionales"
            ],
            "largo_plazo": [
                "Posicionar la institución según tendencias prospectivas",
                "Diversificar y ampliar la oferta formativa",
                "Establecer alianzas estratégicas para aprovechar oportunidades"
            ]
        }
        
        return {
            "conclusiones_principales": conclusiones_principales,
            "recomendaciones_estrategicas": recomendaciones
        }

    
    def _process_indicators_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        """Reporte de indicadores debe incluir: oferta, DOFA, escenarios"""
        indicadores_data = datos.get("indicadores", {})
        dofa_data = datos.get("dofa", {})
        escenarios_data = datos.get("prospectiva", {})
        oferta_data = datos.get("oferta_educativa", {})
        
        return {
            "tipo_reporte": "indicadores",
            "indicadores": indicadores_data.get("lista", []),
            "resumen": indicadores_data.get("resumen", {}),
            "oferta_educativa": oferta_data,
            "analisis_dofa": dofa_data,
            "escenarios_prospectivos": escenarios_data
        }
    
    def _process_prospective_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        """Prospectiva anual: escenarios y DOFA"""
        prospectiva_data = datos.get("prospectiva", {})
        dofa_data = datos.get("dofa", {})
        
        return {
            "tipo_reporte": "prospectiva",
            "prospectiva": prospectiva_data,
            "analisis_dofa": dofa_data
        }
    
    def _process_educational_offer_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        """Análisis y oferta: solo oferta educativa"""
        oferta_data = datos.get("oferta_educativa", {})
        
        return {
            "tipo_reporte": "oferta_educativa",
            "oferta_educativa": oferta_data
        }
    
    def _generate_executive_summary(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Genera resumen ejecutivo con síntesis estratégica"""
        
        # Extraer datos clave
        indicadores = datos.get("indicadores", {})
        dofa = datos.get("dofa", {})
        prospectiva = datos.get("prospectiva", {})
        oferta = datos.get("oferta_educativa", {})
        
        # Construir mensaje ejecutivo
        resumen_ind = indicadores.get("resumen", {})
        cumplimiento = resumen_ind.get("cumplimiento_general", 0)
        
        mensaje = f"""
        El presente informe consolidado presenta un análisis integral del sistema estratégico.
        
        En términos de indicadores, se observa un cumplimiento general del {cumplimiento}% con 
        {resumen_ind.get('verde', 0)} indicadores en estado óptimo, {resumen_ind.get('amarillo', 0)} 
        en estado de alerta y {resumen_ind.get('rojo', 0)} requiriendo atención inmediata.
        
        La oferta educativa cuenta con {oferta.get('total_programas', 0)} programas activos 
        atendiendo {oferta.get('sectores_atendidos', 0)} sectores estratégicos, con una ocupación 
        promedio del {oferta.get('ocupacion_promedio', 0)}%.
        
        El análisis prospectivo contempla {prospectiva.get('resumen_general', {}).get('total_escenarios', 0)} 
        escenarios estratégicos con proyecciones en múltiples sectores.
        """
        
        # Síntesis estratégica
        sintesis = {
            "fortalezas_clave": dofa.get("fortalezas", [])[:3],
            "oportunidades_principales": dofa.get("oportunidades", [])[:3],
            "riesgos_identificados": dofa.get("amenazas", [])[:3],
            "areas_mejora": dofa.get("debilidades", [])[:3]
        }
        
        # Prioridades estratégicas
        prioridades = [
            "Fortalecer indicadores en estado crítico",
            "Optimizar ocupación de programas educativos",
            "Implementar estrategias de los escenarios prospectivos",
            "Mitigar riesgos identificados en análisis DOFA"
        ]
        
        return {
            "mensaje_ejecutivo": mensaje.strip(),
            "sintesis_estrategica": sintesis,
            "prioridades_estrategicas": prioridades
        }
    
    def _serialize_metadata(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Serializa metadatos de los datos recolectados para almacenamiento"""
        try:
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "modulos_incluidos": list(datos.keys()),
                "resumen": {}
            }
            
            # Agregar resumen de cada módulo
            if "indicadores" in datos:
                ind_data = datos["indicadores"]
                metadata["resumen"]["indicadores"] = {
                    "total": ind_data.get("resumen", {}).get("total_indicadores", 0),
                    "cumplimiento": ind_data.get("resumen", {}).get("cumplimiento_general", 0)
                }
            
            if "prospectiva" in datos:
                prosp_data = datos["prospectiva"]
                metadata["resumen"]["prospectiva"] = {
                    "total_escenarios": prosp_data.get("resumen_general", {}).get("total_escenarios", 0),
                    "total_proyecciones": prosp_data.get("resumen_general", {}).get("total_proyecciones", 0)
                }
            
            if "oferta_educativa" in datos:
                oferta_data = datos["oferta_educativa"]
                metadata["resumen"]["oferta_educativa"] = {
                    "total_programas": oferta_data.get("total_programas", 0),
                    "ocupacion_promedio": oferta_data.get("ocupacion_promedio", 0)
                }
            
            return metadata
        except Exception as e:
            logger.error(f"Error serializando metadata: {str(e)}")
            return {"timestamp": datetime.now().isoformat(), "error": str(e)}
    
    def _generate_generation_stats(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Genera estadísticas de la generación del reporte"""
        try:
            stats = {
                "fecha_generacion": datetime.now().isoformat(),
                "modulos_procesados": len(datos),
                "total_elementos": 0
            }
            
            # Contar elementos por módulo
            if "indicadores" in datos:
                stats["total_elementos"] += len(datos["indicadores"].get("lista", []))
            
            if "prospectiva" in datos:
                stats["total_elementos"] += len(datos["prospectiva"].get("escenarios", []))
            
            if "dofa" in datos:
                dofa = datos["dofa"]
                stats["total_elementos"] += sum([
                    len(dofa.get("fortalezas", [])),
                    len(dofa.get("oportunidades", [])),
                    len(dofa.get("debilidades", [])),
                    len(dofa.get("amenazas", []))
                ])
            
            return stats
        except Exception as e:
            logger.error(f"Error generando estadísticas: {str(e)}")
            return {"fecha_generacion": datetime.now().isoformat(), "error": str(e)}
    
    def _log_successful_generation(self, db: Session, reporte_id: int, tipo: TipoReporte, usuario_id: Optional[int], datos: Dict[str, Any]):
        """Registra generación exitosa de reporte"""
        try:
            logger.info(f"✅ Reporte {reporte_id} generado exitosamente")
            logger.info(f"   Tipo: {tipo.value}")
            logger.info(f"   Usuario: {usuario_id}")
            logger.info(f"   Módulos incluidos: {list(datos.keys())}")
        except Exception as e:
            logger.error(f"Error en log de generación exitosa: {str(e)}")
    
    def _log_failed_generation(self, db: Session, reporte_id: int, tipo: TipoReporte, usuario_id: Optional[int], error: str):
        """Registra falla en generación de reporte"""
        try:
            logger.error(f"❌ Falla en generación de reporte {reporte_id}")
            logger.error(f"   Tipo: {tipo.value}")
            logger.error(f"   Usuario: {usuario_id}")
            logger.error(f"   Error: {error}")
        except Exception as e:
            logger.error(f"Error en log de generación fallida: {str(e)}")
    
    def _generate_conclusions(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Genera conclusiones y recomendaciones estratégicas"""
        
        conclusiones_principales = [
            "El sistema presenta un desempeño general satisfactorio con áreas de oportunidad identificadas",
            "La oferta educativa requiere ajustes para optimizar la ocupación y cobertura sectorial",
            "Los escenarios prospectivos señalan tendencias que deben ser consideradas en la planificación",
            "El análisis DOFA revela fortalezas aprovechables y debilidades que requieren atención"
        ]
        
        recomendaciones = {
            "corto_plazo": [
                "Implementar planes de acción para indicadores críticos",
                "Revisar capacidad y demanda de programas educativos",
                "Fortalecer áreas identificadas como debilidades"
            ],
            "mediano_plazo": [
                "Desarrollar estrategias basadas en escenarios prospectivos",
                "Expandir oferta educativa en sectores de alta demanda",
                "Consolidar fortalezas institucionales"
            ],
            "largo_plazo": [
                "Posicionar la institución según tendencias prospectivas",
                "Diversificar y ampliar la oferta formativa",
                "Establecer alianzas estratégicas para aprovechar oportunidades"
            ]
        }
        
        return {
            "conclusiones_principales": conclusiones_principales,
            "recomendaciones_estrategicas": recomendaciones
        }

    
    # Métodos auxiliares
    def _format_dofa_for_report(self, dofa_data: Dict[str, Any]) -> Dict[str, Any]:
        return dofa_data
    
    def _format_indicators_for_report(self, indicators_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "lista": indicators_data.get("lista", []),
            "resumen": indicators_data.get("resumen", {})
        }
    
    def _format_scenarios_for_report(self, scenarios_data: Dict[str, Any]) -> Dict[str, Any]:
        return scenarios_data
    
    def _format_educational_offer_for_report(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        return offer_data
