from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..core.timeutils import now_local, today_local
from ..core.validators import calc_age
from ..dependencies.auth import DbDep, professional_of, require_roles
from ..models import Appointment, Attendance, MedicalRecord, Patient, Payment
from ..schemas.agenda import AttendanceFinishIn, AttendanceStartIn, NoteIn
from ..services.audit import audit

router = APIRouter(prefix="/api/atendimentos", tags=["Atendimentos"])
Staff = require_roles("admin", "recepcionista", "dentista")
Clinical = require_roles("admin", "dentista")  # recepção nunca acessa conteúdo clínico


def _row(a: Appointment, att: Attendance | None = None) -> dict:
    return {"appointment_id": a.id, "attendance_id": att.id if att else None, "patient_id": a.patient_id,
            "patient_name": a.patient.full_name, "patient_age": calc_age(a.patient.birth_date),
            "procedure_name": a.procedure.name, "professional_id": a.professional_id,
            "professional_name": a.professional.full_name, "start_at": a.start_at, "end_at": a.end_at,
            "status": a.status, "started_at": att.started_at if att else None, "finished_at": att.finished_at if att else None}


def _scope(db, user, stmt, col):
    return stmt.where(col == professional_of(db, user).id) if user.role.name == "dentista" else stmt


def _get_attendance(db, att_id: int, user) -> Attendance:
    att = db.get(Attendance, att_id)
    if not att:
        raise HTTPException(404, "Atendimento não encontrado.")
    if user.role.name == "dentista" and att.professional_id != professional_of(db, user).id:
        raise HTTPException(403, "Este atendimento pertence a outro profissional.")
    return att


@router.get("/aguardando")
def aguardando(db: DbDep, user=Depends(Staff)):
    """Pacientes de hoje aguardando ou em atendimento. Não inclui nenhum conteúdo clínico."""
    s = datetime.combine(today_local(), time.min)
    stmt = (select(Appointment).where(Appointment.start_at >= s, Appointment.start_at < s + timedelta(days=1),
                                      Appointment.status.in_(("confirmado", "em_atendimento")))
            .options(joinedload(Appointment.patient), joinedload(Appointment.procedure), joinedload(Appointment.professional))
            .order_by(Appointment.start_at))
    stmt = _scope(db, user, stmt, Appointment.professional_id)
    atts = {x.appointment_id: x for x in db.scalars(select(Attendance).where(
        Attendance.appointment_id.in_(select(Appointment.id).where(Appointment.start_at >= s, Appointment.start_at < s + timedelta(days=1)))))}
    return [_row(a, atts.get(a.id)) for a in db.scalars(stmt).unique()]


@router.post("/iniciar", status_code=201)
def iniciar(body: AttendanceStartIn, request: Request, db: DbDep, user=Depends(Clinical)):
    a = db.scalar(select(Appointment).where(Appointment.id == body.appointment_id).with_for_update())
    if not a:
        raise HTTPException(404, "Agendamento não encontrado.")
    if user.role.name == "dentista" and a.professional_id != professional_of(db, user).id:
        raise HTTPException(403, "Este agendamento pertence a outro profissional.")
    if a.status != "confirmado":
        raise HTTPException(422, "Só é possível iniciar o atendimento de uma consulta confirmada.")
    if a.start_at.date() != today_local():
        raise HTTPException(422, "O atendimento só pode ser iniciado no dia da consulta.")
    att = Attendance(appointment_id=a.id, patient_id=a.patient_id, professional_id=a.professional_id, started_at=now_local())
    a.status = "em_atendimento"
    db.add(att)
    db.flush()
    audit(db, user, "start", "attendance", att.id, f"Agendamento {a.id}", request)
    db.commit()
    return _row(a, att)


def _add_record(db, att: Attendance, content: str) -> MedicalRecord:
    r = MedicalRecord(patient_id=att.patient_id, professional_id=att.professional_id, attendance_id=att.id, content=content)
    db.add(r)
    return r


@router.post("/{att_id}/observacoes", status_code=201)
def adicionar_observacao(att_id: int, body: NoteIn, request: Request, db: DbDep, user=Depends(Clinical)):
    att = _get_attendance(db, att_id, user)
    if att.finished_at:
        raise HTTPException(422, "Este atendimento já foi finalizado.")
    r = _add_record(db, att, body.content)
    db.flush()
    audit(db, user, "write_medical_record", "attendance", att.id, None, request)
    db.commit()
    return {"id": r.id, "created_at": r.created_at}


@router.post("/{att_id}/finalizar")
def finalizar(att_id: int, body: AttendanceFinishIn, request: Request, db: DbDep, user=Depends(Clinical)):
    att = _get_attendance(db, att_id, user)
    if att.finished_at:
        raise HTTPException(422, "Este atendimento já foi finalizado.")
    a = att.appointment
    att.finished_at = now_local()
    a.status = "concluido"
    if body.observations:
        _add_record(db, att, body.observations)
        audit(db, user, "write_medical_record", "attendance", att.id, None, request)
    if not db.scalar(select(Payment.id).where(Payment.appointment_id == a.id)):
        db.add(Payment(patient_id=a.patient_id, appointment_id=a.id, procedure_id=a.procedure_id,
                       amount=a.procedure.price, status="pendente"))  # cobrança gerada para o financeiro
    audit(db, user, "finish", "attendance", att.id, f"Agendamento {a.id}", request)
    db.commit()
    return _row(a, att)


@router.get("")
def historico(db: DbDep, user=Depends(Staff), data_inicio: date | None = None, data_fim: date | None = None,
              q: str | None = None, limite: int = Query(200, ge=1, le=500)):
    stmt = (select(Attendance).join(Attendance.patient)
            .options(joinedload(Attendance.patient), joinedload(Attendance.professional),
                     joinedload(Attendance.appointment).joinedload(Appointment.procedure))
            .order_by(Attendance.started_at.desc()).limit(limite))
    stmt = _scope(db, user, stmt, Attendance.professional_id)
    if data_inicio:
        stmt = stmt.where(Attendance.started_at >= datetime.combine(data_inicio, time.min))
    if data_fim:
        stmt = stmt.where(Attendance.started_at < datetime.combine(data_fim + timedelta(days=1), time.min))
    if q and q.strip():
        stmt = stmt.where(Patient.full_name.ilike(f"%{q.strip()}%"))
    out = []
    for att in db.scalars(stmt).unique():
        a = att.appointment
        out.append({"attendance_id": att.id, "appointment_id": a.id, "patient_id": att.patient_id,
                    "patient_name": att.patient.full_name, "procedure_name": a.procedure.name,
                    "professional_name": att.professional.full_name, "started_at": att.started_at,
                    "finished_at": att.finished_at, "status": a.status})
    return out


@router.get("/{att_id}/registros")
def registros(att_id: int, request: Request, db: DbDep, user=Depends(Clinical)):
    att = _get_attendance(db, att_id, user)
    rows = db.scalars(select(MedicalRecord).where(MedicalRecord.attendance_id == att.id).order_by(MedicalRecord.created_at))
    items = [{"id": r.id, "created_at": r.created_at, "professional_name": r.professional.full_name, "content": r.content} for r in rows]
    audit(db, user, "read_medical_record", "attendance", att.id, f"{len(items)} registro(s)", request)
    db.commit()
    return items
