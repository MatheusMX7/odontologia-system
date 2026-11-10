from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import contains_eager, joinedload

from ..core.constants import MANUAL_TRANSITIONS
from ..core.timeutils import now_local
from ..dependencies.auth import CurrentUser, DbDep, patient_of, professional_of, require_roles
from ..models import Appointment, Patient, Procedure, Professional
from ..schemas.agenda import AppointmentCreate, AppointmentOut, CancelIn, RescheduleIn, StatusChangeIn
from ..services import agenda
from ..services.audit import audit
from ..services.serializers import appointment_out
from ..services.settings import get_clinic_settings

router = APIRouter(prefix="/api/agendamentos", tags=["Agendamentos"])


@router.get("/disponibilidade")
def disponibilidade(db: DbDep, procedimento_id: int, data: date, profissional_id: int | None = None,
                    excluir_agendamento_id: int | None = None):
    """Horários livres calculados no servidor (jornada, intervalos, bloqueios, duração e reservas)."""
    proc = db.get(Procedure, procedimento_id)
    if not proc or proc.deleted_at or not proc.is_active:
        raise HTTPException(404, "Procedimento não encontrado ou indisponível.")
    return agenda.available_slots(db, proc, data, profissional_id, excluir_agendamento_id)


def _load(db, appt_id: int) -> Appointment:
    a = db.scalar(select(Appointment).where(Appointment.id == appt_id)
                  .options(joinedload(Appointment.patient), joinedload(Appointment.procedure), joinedload(Appointment.professional)))
    if not a:
        raise HTTPException(404, "Agendamento não encontrado.")
    return a


def _ensure_access(db, user, a: Appointment) -> None:
    role = user.role.name
    if role == "paciente" and a.patient_id != patient_of(db, user).id:
        raise HTTPException(404, "Agendamento não encontrado.")  # não revela a existência de dados de terceiros
    if role == "dentista" and a.professional_id != professional_of(db, user).id:
        raise HTTPException(403, "Este agendamento pertence a outro profissional.")


@router.post("", response_model=AppointmentOut, status_code=201)
def criar(body: AppointmentCreate, request: Request, db: DbDep, user=Depends(require_roles("paciente", "admin", "recepcionista"))):
    cs = get_clinic_settings(db)
    if user.role.name == "paciente":
        patient = patient_of(db, user)
        status = "confirmado" if cs.auto_confirm else "pendente"
    else:
        if not body.patient_id:
            raise HTTPException(422, "Informe o paciente.")
        patient = db.get(Patient, body.patient_id)
        if not patient or patient.deleted_at:
            raise HTTPException(404, "Paciente não encontrado.")
        status = "confirmado"  # agendado pela recepção já nasce confirmado
    proc = db.get(Procedure, body.procedure_id)
    if not proc or proc.deleted_at or not proc.is_active:
        raise HTTPException(422, "Este procedimento não está disponível para agendamento.")
    appt = agenda.create_appointment(db, patient, proc, body.professional_id, body.start_at, user, status, body.notes)
    audit(db, user, "create", "appointment", appt.id, f"{proc.name} em {appt.start_at:%d/%m/%Y %H:%M}", request)
    db.commit()
    return appointment_out(_load(db, appt.id), cs)


@router.get("", response_model=list[AppointmentOut])
def listar(db: DbDep, user: CurrentUser, data_inicio: date | None = None, data_fim: date | None = None,
           procedimento_id: int | None = None, profissional_id: int | None = None, q: str | None = None,
           status: str | None = None, limite: int = Query(500, ge=1, le=1000)):
    cs = get_clinic_settings(db)
    stmt = (select(Appointment).join(Appointment.patient)
            .options(contains_eager(Appointment.patient), joinedload(Appointment.procedure), joinedload(Appointment.professional)))
    role = user.role.name
    if role == "paciente":
        stmt = stmt.where(Appointment.patient_id == patient_of(db, user).id)
    elif role == "dentista":
        stmt = stmt.where(Appointment.professional_id == professional_of(db, user).id)
    elif profissional_id:
        stmt = stmt.where(Appointment.professional_id == profissional_id)
    if data_inicio:
        stmt = stmt.where(Appointment.start_at >= datetime.combine(data_inicio, time.min))
    if data_fim:
        stmt = stmt.where(Appointment.start_at < datetime.combine(data_fim + timedelta(days=1), time.min))
    if procedimento_id:
        stmt = stmt.where(Appointment.procedure_id == procedimento_id)
    if status:
        stmt = stmt.where(Appointment.status == status)
    if q and q.strip() and role != "paciente":
        stmt = stmt.where(Patient.full_name.ilike(f"%{q.strip()}%"))
    rows = db.scalars(stmt.order_by(Appointment.start_at).limit(limite)).unique()
    return [appointment_out(a, cs) for a in rows]


@router.get("/{appt_id}", response_model=AppointmentOut)
def obter(appt_id: int, db: DbDep, user: CurrentUser):
    a = _load(db, appt_id)
    _ensure_access(db, user, a)
    return appointment_out(a, get_clinic_settings(db))


@router.patch("/{appt_id}/status", response_model=AppointmentOut)
def alterar_status(appt_id: int, body: StatusChangeIn, request: Request, db: DbDep,
                   user=Depends(require_roles("admin", "recepcionista", "dentista"))):
    a = _load(db, appt_id)
    _ensure_access(db, user, a)
    if body.status not in MANUAL_TRANSITIONS.get(a.status, set()):
        raise HTTPException(422, "Esta alteração de status não é permitida. Início e conclusão são feitos no módulo de Atendimentos.")
    if user.role.name == "dentista" and body.status != "nao_compareceu":
        raise HTTPException(403, "Dentistas só podem registrar falta do paciente por aqui.")
    if body.status == "nao_compareceu" and a.start_at > now_local():
        raise HTTPException(422, "Só é possível registrar falta depois do horário da consulta.")
    a.status = body.status
    if body.status == "cancelado":
        a.cancel_reason = body.reason
    audit(db, user, f"status_{body.status}", "appointment", a.id, body.reason, request)
    db.commit()
    return appointment_out(a, get_clinic_settings(db))


def _patient_rules(a: Appointment, cs, action: str):
    if a.status not in ("pendente", "confirmado"):
        raise HTTPException(422, f"Este agendamento não pode ser {action} no status atual.")
    if a.start_at - now_local() < timedelta(hours=cs.cancel_min_hours):
        raise HTTPException(422, f"Conforme as regras da clínica, alterações só podem ser feitas com {cs.cancel_min_hours}h de antecedência. Entre em contato com a clínica.")


@router.post("/{appt_id}/cancelar", response_model=AppointmentOut)
def cancelar(appt_id: int, body: CancelIn, request: Request, db: DbDep, user: CurrentUser):
    if user.role.name == "dentista":
        raise HTTPException(403, "Você não tem permissão para realizar esta operação.")
    a = _load(db, appt_id)
    _ensure_access(db, user, a)
    cs = get_clinic_settings(db)
    if user.role.name == "paciente":
        _patient_rules(a, cs, "cancelado")
    elif a.status not in ("pendente", "confirmado"):
        raise HTTPException(422, "Este agendamento não pode ser cancelado no status atual.")
    a.status, a.cancel_reason = "cancelado", body.reason
    audit(db, user, "cancel", "appointment", a.id, body.reason, request)
    db.commit()
    return appointment_out(a, cs)


@router.post("/{appt_id}/reagendar", response_model=AppointmentOut)
def reagendar(appt_id: int, body: RescheduleIn, request: Request, db: DbDep, user: CurrentUser):
    if user.role.name == "dentista":
        raise HTTPException(403, "Você não tem permissão para realizar esta operação.")
    a = _load(db, appt_id)
    _ensure_access(db, user, a)
    cs = get_clinic_settings(db)
    if user.role.name == "paciente":
        _patient_rules(a, cs, "reagendado")
        new_status = "confirmado" if cs.auto_confirm else "pendente"
    else:
        if a.status not in ("pendente", "confirmado"):
            raise HTTPException(422, "Este agendamento não pode ser reagendado no status atual.")
        new_status = a.status
    old = a.start_at
    agenda.reschedule_appointment(db, a, body.start_at, body.professional_id)
    a.status = new_status
    audit(db, user, "reschedule", "appointment", a.id, f"{old:%d/%m/%Y %H:%M} -> {a.start_at:%d/%m/%Y %H:%M}", request)
    db.commit()
    return appointment_out(_load(db, a.id), cs)
