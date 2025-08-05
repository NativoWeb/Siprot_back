import os
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from models import Reporte
from schemas import TipoReporte, ParametrosReporte, EstadoReporte
from services.data_service import DataService
from services.pdf_service import PDFService
from database import SessionLocal  # Importa el creador de sesiones

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
        """Genera un reporte en segundo plano"""
        db = SessionLocal()
        try:
            reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
            if not reporte:
                raise Exception(f"Reporte {reporte_id} no encontrado")

            reporte.estado = EstadoReporte.GENERANDO.value
            db.commit()

            datos = self.data_service.recopilar_datos(tipo, parametros)

            archivo_path = self.pdf_service.generar_pdf(
                tipo, datos, parametros, reporte_id
            )

            if os.path.exists(archivo_path):
                file_size = os.path.getsize(archivo_path)
                reporte.archivo_path = archivo_path
                reporte.tamaño_archivo = file_size
                reporte.estado = EstadoReporte.COMPLETADO.value
            else:
                raise Exception("El archivo PDF no fue generado correctamente")

            reporte.updated_at = datetime.utcnow()
            db.commit()

        except Exception as e:
            print(f"Error generando reporte {reporte_id}: {str(e)}")
            try:
                reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
                if reporte:
                    reporte.estado = EstadoReporte.ERROR.value
                    reporte.updated_at = datetime.utcnow()
                    db.commit()
            except:
                pass
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
            "archivo_disponible": bool(reporte.archivo_path and os.path.exists(reporte.archivo_path))
        }