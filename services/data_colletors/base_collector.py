# services/data_collectors/base_collector.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from sqlalchemy.orm import Session
from schemas import ParametrosReporte


class BaseDataCollector(ABC):
    """Clase base para todos los colectores de datos"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @abstractmethod
    def collect_data(self, parametros: ParametrosReporte) -> Dict[str, Any]:
        """Método principal para recolectar datos específicos del módulo"""
        pass
    
    @abstractmethod
    def get_data_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de datos disponibles para validación"""
        pass
    
    def validate_parameters(self, parametros: ParametrosReporte) -> bool:
        """Valida parámetros específicos del colector"""
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """Obtiene metadatos del colector"""
        return {
            "collector_name": self.__class__.__name__,
            "version": "1.0",
            "last_execution": None
        }