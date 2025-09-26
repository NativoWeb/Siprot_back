import os
import tempfile
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from models import Reporte
from schemas import TipoReporte, ParametrosReporte, EstadoReporte
from services.data_service import DataService
from services.pdf_service import PDFService
from database import SessionLocal

class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.data_service = DataService()
        self.pdf_service = PDFService()
    
    def generar_reporte_background(
        self,
        reporte_id: int,
        tipo: TipoReporte,
        parametros: ParametrosReporte
    ):
        """Genera un reporte en segundo plano y lo almacena en BD + filesystem"""
        db = SessionLocal()
        temp_file_path = None
        
        try:
            reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
            if not reporte:
                raise Exception(f"Reporte {reporte_id} no encontrado")
            
            reporte.estado = EstadoReporte.GENERANDO.value
            db.commit()
            
            # Recopilar datos
            data = self.data_service.get_strategic_dashboard_data()
            
            # Generar PDF
            temp_file_path = self.pdf_service.generar_pdf(
                tipo, datos, parametros, reporte_id
            )
            
            if os.path.exists(temp_file_path):
                # Leer el contenido del PDF
                with open(temp_file_path, 'rb') as pdf_file:
                    pdf_content = pdf_file.read()
                
                # Almacenar en la base de datos
                reporte.archivo_contenido = pdf_content
                reporte.archivo_nombre = f"reporte_{reporte_id}_{tipo.value}.pdf"
                reporte.tamaño_archivo = len(pdf_content)
                reporte.estado = EstadoReporte.COMPLETADO.value
                
                # MANTENER archivo_path para compatibilidad con frontend
                reporte.archivo_path = temp_file_path  # ← SE MANTIENE
                
                # NO eliminar archivo aquí
            else:
                raise Exception("El archivo PDF no fue generado correctamente")
            
            reporte.updated_at = datetime.utcnow()
            db.commit()
            
        except Exception as e:
            print(f"Error generando reporte {reporte_id}: {str(e)}")
            # ... manejo de errores ...
        finally:
            db.close()
    
    def obtener_progreso_reporte(self, reporte_id: int) -> Dict[str, Any]:
        """Obtiene el progreso de generación de un reporte"""
        reporte = self.db.query(Reporte).filter(Reporte.id == reporte_id).first()
        
        if not reporte:
            return {"error": "Reporte no encontrado"}
        
        return {
            "id": reporte.id,
            "estado": reporte.estado,
            "fecha_generacion": reporte.fecha_generacion,
            # Verificar si hay contenido en BD o archivo en filesystem
            "archivo_disponible": bool(reporte.archivo_contenido or 
                                      (reporte.archivo_path and os.path.exists(reporte.archivo_path)))
        }
