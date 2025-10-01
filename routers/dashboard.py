from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from database import get_db
from models import User, Document

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # Totales
    total_users = db.query(User).count()
    total_documents = db.query(Document).count()

    # Evolución mensual usuarios
    users_by_month = (
        db.query(
            extract('year', User.created_at).label("year"),
            extract('month', User.created_at).label("month"),
            func.count(User.id).label("count")
        )
        .group_by(extract('year', User.created_at), extract('month', User.created_at))
        .order_by("year", "month")

        
        .all()
    )

    # Evolución mensual documentos
    docs_by_month = (
        db.query(
            extract('year', Document.uploaded_at).label("year"),
            extract('month', Document.uploaded_at).label("month"),
            func.count(Document.id).label("count")
        )
        .group_by(extract('year', Document.uploaded_at), extract('month', Document.uploaded_at))
        .order_by("year", "month")
        .all()
    )


    # Distribución de roles (extra: usuarios agrupados por rol)
    roles_distribution = (
        db.query(User.role, func.count(User.id).label("count"))
        .group_by(User.role)
        .all()
    )

    def format_monthly(data):
        return [
            {"year": int(y), "month": int(m), "count": c}
            for y, m, c in data
        ]

    return {
        "usuarios": total_users,
        "documentos": total_documents,
        "usuarios_mensual": format_monthly(users_by_month),
        "documentos_mensual": format_monthly(docs_by_month),
        "roles_distribucion": [
            {"role": r, "count": c} for r, c in roles_distribution
        ]
    }
