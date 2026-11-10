"""Endpoints públicos (sem login) que alimentam o portal do paciente com dados reais do banco."""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from ..core.constants import CATEGORIES
from ..dependencies.auth import DbDep
from ..models import Appointment, Procedure, Professional
from ..schemas.cadastros import PublicProcedureOut, PublicProfessionalOut
from ..services.settings import get_clinic_settings, working_days

router = APIRouter(prefix="/api/publico", tags=["Portal público"])


@router.get("/clinica")
def clinica(db: DbDep):
    cs = get_clinic_settings(db)
    return {"name": cs.name, "logo_url": cs.logo_url, "address": cs.address, "phone": cs.phone, "email": cs.email,
            "opening_hours": cs.opening_hours, "working_days": sorted(working_days(cs)),
            "policy_text": cs.policy_text, "auto_confirm": cs.auto_confirm, "cancel_min_hours": cs.cancel_min_hours,
            "max_advance_days": cs.max_advance_days}


def _available(p: Procedure) -> bool:
    return any(x.is_active and x.deleted_at is None and x.schedules for x in p.professionals)


@router.get("/procedimentos", response_model=list[PublicProcedureOut])
def procedimentos(db: DbDep, categoria: str | None = Query(default=None), populares: int | None = Query(default=None, ge=1, le=50)):
    """Procedimentos ativos. Com ?populares=N, devolve os N mais solicitados (agendamentos não cancelados)."""
    q = select(Procedure).where(Procedure.is_active.is_(True), Procedure.deleted_at.is_(None))
    if categoria:
        if categoria not in CATEGORIES:
            raise HTTPException(422, "Categoria inválida.")
        q = q.where(Procedure.category == categoria)
    if populares:
        used = (select(Appointment.procedure_id.label("pid"), func.count(Appointment.id).label("n"))
                .where(Appointment.status != "cancelado").group_by(Appointment.procedure_id).subquery())
        q = q.outerjoin(used, used.c.pid == Procedure.id).order_by(func.coalesce(used.c.n, 0).desc(), Procedure.name).limit(populares)
    else:
        q = q.order_by(Procedure.name)
    return [{"id": p.id, "name": p.name, "category": p.category, "description": p.description, "guidance": p.guidance,
             "image_url": p.image_url, "duration_minutes": p.duration_minutes, "available": _available(p)}
            for p in db.scalars(q).unique()]


@router.get("/procedimentos/{procedure_id}/profissionais", response_model=list[PublicProfessionalOut])
def profissionais_do_procedimento(procedure_id: int, db: DbDep):
    p = db.get(Procedure, procedure_id)
    if not p or not p.is_active or p.deleted_at:
        raise HTTPException(404, "Procedimento não encontrado.")
    return [x for x in sorted(p.professionals, key=lambda x: x.full_name) if x.is_active and x.deleted_at is None]


@router.get("/profissionais", response_model=list[PublicProfessionalOut])
def profissionais(db: DbDep):
    return list(db.scalars(select(Professional).where(Professional.is_active.is_(True), Professional.deleted_at.is_(None))
                           .order_by(Professional.full_name)))
