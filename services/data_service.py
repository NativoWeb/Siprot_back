from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from models import *

class DataService:
    """Servicio centralizado para manejo de datos del sistema SIPROT"""
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def set_session(self, db: Session):
        """Establece la sesión de base de datos"""
        self.db = db
    
    # Métodos para Usuarios
    def get_users_by_role(self, role: str) -> List[User]:
        """Obtiene usuarios por rol específico"""
        return self.db.query(User).filter(User.role == role).all()
    
    def get_active_users(self) -> List[User]:
        """Obtiene todos los usuarios activos"""
        return self.db.query(User).filter(User.is_active == True).all()
    
    # Métodos para Documentos
    def get_documents_by_type(self, document_type_id: int) -> List[Document]:
        """Obtiene documentos por tipo"""
        return self.db.query(Document).filter(Document.document_type_id == document_type_id).all()
    
    def get_recent_documents(self, days: int = 30) -> List[Document]:
        """Obtiene documentos recientes"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return self.db.query(Document).filter(Document.upload_date >= cutoff_date).all()
    
    def get_documents_by_sector(self, sector_id: int) -> List[Document]:
        """Obtiene documentos por sector"""
        return self.db.query(Document).filter(Document.sector_id == sector_id).all()
    
    # Métodos para Programas
    def get_programs_by_sector(self, sector_id: int) -> List[Program]:
        """Obtiene programas por sector"""
        return self.db.query(Program).filter(Program.sector_id == sector_id).all()
    
    def get_programs_by_core_line(self, core_line_id: int) -> List[Program]:
        """Obtiene programas por línea núcleo"""
        return self.db.query(Program).filter(Program.core_line_id == core_line_id).all()
    
    def get_programs_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de programas"""
        total_programs = self.db.query(Program).count()
        programs_by_sector = self.db.query(
            Sector.name, func.count(Program.id)
        ).join(Program).group_by(Sector.name).all()
        
        return {
            "total_programs": total_programs,
            "programs_by_sector": dict(programs_by_sector)
        }
    
    # Métodos para Indicadores
    def get_indicators_by_type(self, indicator_type: str) -> List[Indicador]:
        """Obtiene indicadores por tipo"""
        return self.db.query(Indicador).filter(Indicador.categoria == indicator_type).all()
    
    def get_indicators_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de indicadores"""
        total_indicators = self.db.query(Indicador).count()
        indicators_by_category = self.db.query(
            Indicador.categoria, func.count(Indicador.id)
        ).group_by(Indicador.categoria).all()
        
        return {
            "total_indicators": total_indicators,
            "indicators_by_category": dict(indicators_by_category)
        }
    
    # Métodos para Escenarios
    def get_scenarios_by_type(self, scenario_type: str) -> List[Scenario]:
        """Obtiene escenarios por tipo"""
        return self.db.query(Scenario).filter(Scenario.type == scenario_type).all()
    
    def get_active_scenarios(self) -> List[Scenario]:
        """Obtiene escenarios activos"""
        return self.db.query(Scenario).filter(Scenario.is_active == True).all()
    
    def get_scenario_projections(self, scenario_id: int) -> List[ScenarioProjection]:
        """Obtiene proyecciones de un escenario"""
        return self.db.query(ScenarioProjection).filter(
            ScenarioProjection.scenario_id == scenario_id
        ).all()
    
    # Métodos para DOFA
    def get_dofa_items_by_type(self, dofa_type: str) -> List[DofaItem]:
        """Obtiene elementos DOFA por tipo (fortaleza, oportunidad, debilidad, amenaza)"""
        return self.db.query(DofaItem).filter(DofaItem.type == dofa_type).all()
    
    def get_dofa_summary(self) -> Dict[str, Any]:
        """Obtiene resumen del análisis DOFA"""
        dofa_by_type = self.db.query(
            DofaItem.type, func.count(DofaItem.id)
        ).group_by(DofaItem.type).all()
        
        return {
            "dofa_by_type": dict(dofa_by_type),
            "total_items": sum(count for _, count in dofa_by_type)
        }
    
    # Métodos para Reportes
    def get_reports_by_type(self, report_type: str) -> List[Reporte]:
        """Obtiene reportes por tipo"""
        return self.db.query(Reporte).filter(Reporte.tipo == report_type).all()
    
    def get_recent_reports(self, days: int = 30) -> List[Reporte]:
        """Obtiene reportes recientes"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return self.db.query(Reporte).filter(Reporte.created_at >= cutoff_date).all()
    
    # Métodos para datos consolidados
    def get_strategic_dashboard_data(self) -> Dict[str, Any]:
        """Obtiene datos consolidados para el dashboard estratégico"""
        return {
            "programs_stats": self.get_programs_statistics(),
            "indicators_summary": self.get_indicators_summary(),
            "dofa_summary": self.get_dofa_summary(),
            "recent_documents": len(self.get_recent_documents()),
            "active_scenarios": len(self.get_active_scenarios()),
            "recent_reports": len(self.get_recent_reports())
        }
    
    def get_sector_analysis(self, sector_id: int) -> Dict[str, Any]:
        """Obtiene análisis completo de un sector"""
        sector = self.db.query(Sector).filter(Sector.id == sector_id).first()
        if not sector:
            return {}
        
        programs = self.get_programs_by_sector(sector_id)
        documents = self.get_documents_by_sector(sector_id)
        
        return {
            "sector": sector,
            "programs_count": len(programs),
            "documents_count": len(documents),
            "programs": programs,
            "recent_documents": [doc for doc in documents if doc.upload_date >= datetime.now() - timedelta(days=30)]
        }
    
    # Métodos para auditoría
    def log_activity(self, user_id: int, action: str, details: str = None):
        """Registra actividad en el log de auditoría"""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            details=details,
            timestamp=datetime.now()
        )
        self.db.add(audit_log)
        self.db.commit()
    
    def get_audit_logs(self, user_id: int = None, days: int = 30) -> List[AuditLog]:
        """Obtiene logs de auditoría"""
        query = self.db.query(AuditLog)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        cutoff_date = datetime.now() - timedelta(days=days)
        query = query.filter(AuditLog.timestamp >= cutoff_date)
        
        return query.order_by(desc(AuditLog.timestamp)).all()
