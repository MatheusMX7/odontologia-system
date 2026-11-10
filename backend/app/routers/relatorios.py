from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..core.timeutils import today_local
from ..dependencies.auth import DbDep, require_roles
from ..services import exports, stats
from ..services.settings import get_clinic_settings

router = APIRouter(prefix="/api/relatorios", tags=["Relatórios"])
AdminOnly = require_roles("admin")


def _range(inicio: date | None, fim: date | None) -> tuple[date, date]:
    fim = fim or today_local()
    inicio = inicio or fim.replace(day=1)
    if inicio > fim:
        raise HTTPException(422, "A data inicial deve ser anterior à data final.")
    if (fim - inicio).days > 366:
        raise HTTPException(422, "O período máximo do relatório é de 12 meses.")
    return inicio, fim


def _collect(db, ini: date, end: date):
    st = stats.period_stats(db, ini, end)
    fin = stats.finance_summary(db, ini, end)
    rev = stats.revenue_series(db, ini, end, st["period"]["group_by"])
    return st, fin, rev, stats.no_show_patients(db, ini, end)


@router.get("/resumo")
def resumo(db: DbDep, _=Depends(AdminOnly), inicio: date | None = None, fim: date | None = None):
    ini, end = _range(inicio, fim)
    st, fin, rev, ns = _collect(db, ini, end)
    return {**st, "finance": fin, "revenue_series": rev, "no_shows": ns}


@router.get("/exportar")
def exportar(db: DbDep, _=Depends(AdminOnly), formato: str = Query(pattern="^(pdf|xlsx)$"),
             inicio: date | None = None, fim: date | None = None):
    ini, end = _range(inicio, fim)
    st, fin, rev, ns = _collect(db, ini, end)
    clinic = get_clinic_settings(db).name
    name = f"relatorio_{ini:%Y%m%d}_{end:%Y%m%d}.{formato}"
    if formato == "pdf":
        data, mime = exports.build_pdf(clinic, ini, end, st, fin, rev, ns), "application/pdf"
    else:
        data, mime = exports.build_xlsx(clinic, ini, end, st, fin, rev, ns), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
