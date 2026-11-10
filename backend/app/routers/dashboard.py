from datetime import timedelta

from fastapi import APIRouter, Depends, Query

from ..core.timeutils import today_local
from ..dependencies.auth import DbDep, professional_of, require_roles
from ..services import stats

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
def dashboard(db: DbDep, user=Depends(require_roles("admin", "recepcionista", "dentista")), dias: int = Query(30, ge=7, le=365)):
    """Indicadores reais. Dentista vê só a própria agenda; o financeiro é exclusivo do administrador."""
    today = today_local()
    start = today - timedelta(days=dias - 1)
    prof_id = professional_of(db, user).id if user.role.name == "dentista" else None
    st = stats.period_stats(db, start, today, prof_id)
    agenda_hoje = stats.today_agenda(db, prof_id)
    out = {
        "period_days": dias,
        "cards": {
            "total_patients": st["total_patients"],
            "today_appointments": len([a for a in agenda_hoje if a["status"] not in ("cancelado",)]),
            "completed": st["status_count"]["concluido"],
            "pending": st["status_count"]["pendente"],
            "cancelled": st["status_count"]["cancelado"],
            "new_patients": st["new_patients"],
        },
        "appointments_series": st["appointments_series"],
        "attendances_series": st["attendances_series"],
        "top_procedures": st["top_procedures"],
        "evolution": stats.evolution_months(db, today, prof_id),
        "today_agenda": agenda_hoje,
        "finance": None,
    }
    if user.role.name == "admin":
        first, _ = stats.last_months(6, today)
        fin = stats.finance_summary(db, start, today)
        out["finance"] = {"received": fin["received"], "pending": fin["pending"],
                          "monthly": stats.revenue_series(db, first, today, "month")}
    return out
