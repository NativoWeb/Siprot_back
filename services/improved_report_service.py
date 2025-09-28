import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from models import Reporte, User
from schemas import TipoReporte, ParametrosReporte, EstadoReporte
from services.pdf_service import PDFService
from services.data_collector_service import IntegratedDataCollectorService
from database import SessionLocal
import logging

logger = logging.getLogger(__name__)

class ImprovedReportService:
    """
    Servicio de reportes mejorado que utiliza el nuevo sistema de recolección de datos
    """
    
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
        """
        Genera un reporte en segundo plano usando el nuevo sistema de recolección
        """
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
                pass
    
    def _validate_collected_data(self, datos: Dict[str, Any], tipo: TipoReporte) -> Dict[str, Any]:
        validacion = {"valido": True, "errores": [], "advertencias": []}
        try:
            if not datos:
                return {"valido": False, "errores": ["No se recolectaron datos"]}
            if "error" in datos:
                return {"valido": False, "errores": [f"Error en recolección: {datos['error']}"]}
            
            if tipo == TipoReporte.INDICADORES:
                if not datos.get("indicadores", {}).get("indicadores"):
                    validacion["errores"].append("No se encontraron indicadores")
                    validacion["valido"] = False
            elif tipo == TipoReporte.PROSPECTIVA:
                if not datos.get("prospectiva", {}).get("escenarios"):
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
    
    def _process_consolidated_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        return {
            "portada": {"titulo": "Informe Consolidado", "fecha": datetime.now()},
            "resumen_ejecutivo": self._generate_executive_summary(datos),
            "analisis_dofa": self._format_dofa_for_report(datos.get("dofa", {})),
            "indicadores_estrategicos": self._format_indicators_for_report(datos.get("indicadores", {})),
            "escenarios_prospectivos": self._format_scenarios_for_report(datos.get("prospectiva", {})),
            "oferta_educativa": self._format_educational_offer_for_report(datos.get("oferta_educativa", {})),
        }
    
    def _process_indicators_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        indicadores_data = datos.get("indicadores", {})
        return {
            "tipo_reporte": "indicadores",
            "indicadores": indicadores_data.get("indicadores", []),
            "resumen": indicadores_data.get("metricas_resumen", {}),
        }
    
    def _process_prospective_report_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        return datos.get("prospectiva", {})
    
    def _process_educational_offer_data(self, datos: Dict[str, Any], parametros: ParametrosReporte) -> Dict[str, Any]:
        return datos.get("oferta_educativa", {})
    
    def _generate_executive_summary(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        return {"mensaje": "Síntesis ejecutiva", "modulos": list(datos.keys())}
    
    def _serialize_metadata(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        return {"timestamp": datetime.now(), "modulos": list(datos.keys())}
    
    def _generate_generation_stats(self, datos: Dict[str, Any]) -> Dict[str, Any]:
        return {"fecha": datetime.now(), "modulos_procesados": len(datos)}
    
    def _log_successful_generation(self, db: Session, reporte_id: int, tipo: TipoReporte, usuario_id: Optional[int], datos: Dict[str, Any]):
        logger.info(f"Reporte {reporte_id} generado exitosamente por usuario {usuario_id}")
    
    def _log_failed_generation(self, db: Session, reporte_id: int, tipo: TipoReporte, usuario_id: Optional[int], error: str):
        logger.error(f"Falla en generación de reporte {reporte_id}: {error}")
    
    def obtener_progreso_reporte(self, reporte_id: int) -> Dict[str, Any]:
        reporte = self.db.query(Reporte).filter(Reporte.id == reporte_id).first()
        if not reporte:
            return {"error": "Reporte no encontrado"}
        return {
            "id": reporte.id,
            "estado": reporte.estado,
            "archivo_disponible": bool(reporte.archivo_contenido),
            "mensaje_error": getattr(reporte, 'mensaje_error', None)
        }
    
    # Métodos auxiliares
    def _format_dofa_for_report(self, dofa_data: Dict[str, Any]) -> Dict[str, Any]:
        return dofa_data
    
    def _format_indicators_for_report(self, indicators_data: Dict[str, Any]) -> Dict[str, Any]:
        return indicators_data
    
    def _format_scenarios_for_report(self, scenarios_data: Dict[str, Any]) -> Dict[str, Any]:
        return scenarios_data
    
    def _format_educational_offer_for_report(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        return offer_data
