from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..core.timeutils import now_local, today_local
from ..dependencies.auth import DbDep, require_roles
from ..models import Appointment, Patient, Payment, Procedure
from ..schemas.agenda import PayIn, PaymentCreateIn
from ..services.audit import audit
from ..services.stats import finance_summary, revenue_series

router = APIRouter(prefix="/api/financeiro", tags=["Financeiro"])
AdminOnly = require_roles("admin")


def _out(p: Payment) -> dict:
    return {"id": p.id, "patient_id": p.patient_id, "patient_name": p.patient.full_name,
            "procedure_name": p.procedure.name if p.procedure else None, "appointment_id": p.appointment_id,
            "amount": p.amount, "method": p.method, "status": p.status, "paid_at": p.paid_at,
            "created_at": p.created_at, "notes": p.notes}


def _range(inicio: date | None, fim: date | None) -> tuple[date, date]:
    fim = fim or today_local()
    inicio = inicio or fim.replace(day=1)
    if inicio > fim:
        raise HTTPException(422, "A data inicial deve ser anterior à data final.")
    return inicio, fim


@router.get("/pagamentos")
def listar(db: DbDep, _=Depends(AdminOnly), inicio: date | None = None, fim: date | None = None,
           situacao: str | None = None, q: str | None = None, limite: int = Query(300, ge=1, le=1000)):
    ini, end = _range(inicio, fim)
    s, e = datetime.combine(ini, time.min), datetime.combine(end + timedelta(days=1), time.min)
    stmt = (select(Payment).join(Payment.patient).options(joinedload(Payment.patient), joinedload(Payment.procedure))
            .where(Payment.created_at >= s, Payment.created_at < e).order_by(Payment.created_at.desc()).limit(limite))
    if situacao:
        if situacao not in ("pendente", "pago", "cancelado"):
            raise HTTPException(422, "Situação inválida.")
        stmt = stmt.where(Payment.status == situacao)
    if q and q.strip():
        stmt = stmt.where(Patient.full_name.ilike(f"%{q.strip()}%"))
    return [_out(p) for p in db.scalars(stmt).unique()]


@router.post("/pagamentos", status_code=201)
def registrar(body: PaymentCreateIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    patient = db.get(Patient, body.patient_id)
    if not patient or patient.deleted_at:
        raise HTTPException(404, "Paciente não encontrado.")
    if body.procedure_id and not db.get(Procedure, body.procedure_id):
        raise HTTPException(404, "Procedimento não encontrado.")
    if body.appointment_id:
        ap = db.get(Appointment, body.appointment_id)
        if not ap or ap.patient_id != body.patient_id:
            raise HTTPException(422, "O agendamento informado não pertence a este paciente.")
    if body.status == "pago" and not body.method:
        raise HTTPException(422, "Informe a forma de pagamento.")
    p = Payment(patient_id=body.patient_id, appointment_id=body.appointment_id, procedure_id=body.procedure_id,
                amount=body.amount, method=body.method, status=body.status, notes=body.notes,
                paid_at=now_local() if body.status == "pago" else None)
    db.add(p)
    db.flush()
    audit(db, admin, "create", "payment", p.id, f"R$ {body.amount}", request)
    db.commit()
    return _out(p)


@router.patch("/pagamentos/{pid}/pagar")
def pagar(pid: int, body: PayIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    p = db.get(Payment, pid)
    if not p:
        raise HTTPException(404, "Pagamento não encontrado.")
    if p.status != "pendente":
        raise HTTPException(422, "Somente pagamentos pendentes podem ser baixados.")
    p.status, p.method, p.paid_at = "pago", body.method, body.paid_at or now_local()
    audit(db, admin, "pay", "payment", p.id, body.method, request)
    db.commit()
    return _out(p)


@router.patch("/pagamentos/{pid}/cancelar")
def cancelar(pid: int, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    p = db.get(Payment, pid)
    if not p:
        raise HTTPException(404, "Pagamento não encontrado.")
    if p.status != "pendente":
        raise HTTPException(422, "Somente pagamentos pendentes podem ser cancelados.")
    p.status = "cancelado"
    audit(db, admin, "cancel", "payment", p.id, None, request)
    db.commit()
    return _out(p)


@router.get("/resumo")
def resumo(db: DbDep, _=Depends(AdminOnly), inicio: date | None = None, fim: date | None = None):
    ini, end = _range(inicio, fim)
    by = "day" if (end - ini).days <= 62 else "month"
    return {"periodo": {"inicio": ini, "fim": end}, **finance_summary(db, ini, end), "revenue_series": revenue_series(db, ini, end, by)}
