"""Regras de agenda: horários disponíveis e criação/reagendamento sem conflito."""
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.constants import ACTIVE_STATUSES, OPEN_STATUSES
from ..core.timeutils import now_local
from ..models import Appointment, Patient, Procedure, Professional, ScheduleBlock, User, professional_procedures
from .settings import get_clinic_settings, working_days


def eligible_professionals(db: Session, procedure_id: int, professional_id: int | None = None) -> list[Professional]:
    q = (
        select(Professional)
        .join(professional_procedures, professional_procedures.c.professional_id == Professional.id)
        .where(professional_procedures.c.procedure_id == procedure_id,
               Professional.is_active.is_(True), Professional.deleted_at.is_(None))
        .order_by(Professional.full_name)
    )
    if professional_id:
        q = q.where(Professional.id == professional_id)
    return list(db.scalars(q).unique())


def available_slots(db: Session, procedure: Procedure, day: date, professional_id: int | None = None,
                    exclude_appointment_id: int | None = None) -> list[dict]:
    """Horários livres do dia, respeitando jornada, intervalo, bloqueios, duração e agendamentos ativos."""
    cs = get_clinic_settings(db)
    now = now_local()
    if day < now.date() or day > now.date() + timedelta(days=cs.max_advance_days):
        return []
    if day.weekday() not in working_days(cs):
        return []
    if not procedure.is_active or procedure.deleted_at is not None:
        return []

    step = timedelta(minutes=cs.slot_minutes)
    dur = timedelta(minutes=procedure.duration_minutes)
    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)
    result: list[dict] = []

    for prof in eligible_professionals(db, procedure.id, professional_id):
        sched = next((s for s in prof.schedules if s.weekday == day.weekday()), None)
        if not sched:
            continue
        busy: list[tuple[datetime, datetime]] = []
        appts = db.execute(
            select(Appointment.start_at, Appointment.end_at).where(
                Appointment.professional_id == prof.id, Appointment.status.in_(ACTIVE_STATUSES),
                Appointment.start_at < day_end, Appointment.end_at > day_start,
                Appointment.id != (exclude_appointment_id or 0))
        ).all()
        busy += [(a, b) for a, b in appts]
        blocks = db.execute(
            select(ScheduleBlock.start_at, ScheduleBlock.end_at).where(
                (ScheduleBlock.professional_id == prof.id) | (ScheduleBlock.professional_id.is_(None)),
                ScheduleBlock.start_at < day_end, ScheduleBlock.end_at > day_start)
        ).all()
        busy += [(a, b) for a, b in blocks]
        if sched.break_start and sched.break_end:
            busy.append((datetime.combine(day, sched.break_start), datetime.combine(day, sched.break_end)))

        cur = datetime.combine(day, sched.start_time)
        limit = datetime.combine(day, sched.end_time)
        while cur + dur <= limit:
            end = cur + dur
            if cur > now and not any(cur < b_end and end > b_start for b_start, b_end in busy):
                result.append({"time": cur.strftime("%H:%M"), "start": cur.isoformat(), "end": end.isoformat(),
                               "professional_id": prof.id, "professional_name": prof.full_name})
            cur += step
    result.sort(key=lambda s: (s["time"], s["professional_name"]))
    return result


def _lock_professional(db: Session, professional_id: int, procedure: Procedure) -> Professional:
    # SELECT ... FOR UPDATE: serializa reservas concorrentes do mesmo profissional no PostgreSQL.
    prof = db.execute(select(Professional).where(Professional.id == professional_id).with_for_update()).scalar_one_or_none()
    if not prof or prof.deleted_at is not None or not prof.is_active:
        raise HTTPException(422, "Profissional indisponível.")
    if not any(p.id == procedure.id for p in prof.procedures):
        raise HTTPException(422, "Este profissional não realiza o procedimento escolhido.")
    return prof


def _validate_slot(db: Session, procedure: Procedure, prof: Professional, start_at: datetime,
                   exclude_id: int | None = None) -> None:
    if start_at <= now_local():
        raise HTTPException(422, "Não é possível agendar em datas ou horários passados.")
    slots = available_slots(db, procedure, start_at.date(), prof.id, exclude_id)
    if not any(s["start"] == start_at.isoformat() for s in slots):
        raise HTTPException(409, "Este horário não está disponível. Escolha outro horário.")


def _check_patient_clash(db: Session, patient_id: int, start: datetime, end: datetime, exclude_id: int | None = None):
    clash = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.patient_id == patient_id, Appointment.status.in_(OPEN_STATUSES),
            Appointment.start_at < end, Appointment.end_at > start, Appointment.id != (exclude_id or 0))
    )
    if clash:
        raise HTTPException(409, "O paciente já possui outro agendamento neste horário.")


def create_appointment(db: Session, patient: Patient, procedure: Procedure, professional_id: int,
                       start_at: datetime, user: User | None, status: str, notes: str | None = None) -> Appointment:
    prof = _lock_professional(db, professional_id, procedure)
    _validate_slot(db, procedure, prof, start_at)
    end_at = start_at + timedelta(minutes=procedure.duration_minutes)
    _check_patient_clash(db, patient.id, start_at, end_at)
    appt = Appointment(patient_id=patient.id, professional_id=prof.id, procedure_id=procedure.id,
                       start_at=start_at, end_at=end_at, status=status, notes=notes,
                       created_by_user_id=user.id if user else None)
    db.add(appt)
    try:
        db.flush()
    except IntegrityError:  # último recurso: índice único parcial do banco
        db.rollback()
        raise HTTPException(409, "Este horário acabou de ser reservado por outra pessoa. Escolha outro horário.")
    return appt


def reschedule_appointment(db: Session, appt: Appointment, start_at: datetime, professional_id: int | None) -> Appointment:
    procedure = db.get(Procedure, appt.procedure_id)
    prof = _lock_professional(db, professional_id or appt.professional_id, procedure)
    _validate_slot(db, procedure, prof, start_at, exclude_id=appt.id)
    end_at = start_at + timedelta(minutes=procedure.duration_minutes)
    _check_patient_clash(db, appt.patient_id, start_at, end_at, exclude_id=appt.id)
    appt.professional_id = prof.id
    appt.start_at, appt.end_at = start_at, end_at
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Este horário acabou de ser reservado por outra pessoa. Escolha outro horário.")
    return appt
