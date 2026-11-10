"""Indicadores calculados exclusivamente a partir dos registros reais do banco."""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.timeutils import today_local
from ..core.validators import calc_age
from ..models import Appointment, Attendance, Patient, Payment, Procedure, Professional


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)


def _keys(start: date, end: date, by: str) -> list[str]:
    out, cur = [], start
    while cur <= end:
        k = cur.strftime("%Y-%m-%d") if by == "day" else cur.strftime("%Y-%m")
        if k not in out:
            out.append(k)
        cur += timedelta(days=1)
    return out


def _label(key: str) -> str:
    p = key.split("-")
    return f"{p[2]}/{p[1]}" if len(p) == 3 else f"{p[1]}/{p[0]}"


def _series(keys: list[str], counter: dict) -> dict:
    return {"labels": [_label(k) for k in keys], "values": [counter.get(k, 0) for k in keys]}


def _bucket(d: date, by: str) -> str:
    return d.strftime("%Y-%m-%d") if by == "day" else d.strftime("%Y-%m")


def last_months(n: int, today: date) -> tuple[date, list[str]]:
    y, m = today.year, today.month
    months = []
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    first = date(int(months[0][:4]), int(months[0][5:]), 1)
    return first, months


def revenue_series(db: Session, start: date, end: date, by: str) -> dict:
    s, e = _bounds(start, end)
    rows = db.execute(select(Payment.paid_at, Payment.amount).where(
        Payment.status == "pago", Payment.paid_at >= s, Payment.paid_at < e)).all()
    acc: dict = defaultdict(float)
    for paid_at, amount in rows:
        acc[_bucket(paid_at.date(), by)] += float(amount)
    keys = _keys(start, end, by)
    return {"labels": [_label(k) for k in keys], "values": [round(acc.get(k, 0), 2) for k in keys]}


def period_stats(db: Session, start: date, end: date, professional_id: int | None = None) -> dict:
    """Métricas do período. Quando professional_id é informado, restringe à agenda do profissional."""
    s, e = _bounds(start, end)
    by = "day" if (end - start).days <= 62 else "month"
    q = select(Appointment.start_at, Appointment.status, Appointment.procedure_id,
               Appointment.professional_id, Appointment.patient_id).where(
        Appointment.start_at >= s, Appointment.start_at < e)
    if professional_id:
        q = q.where(Appointment.professional_id == professional_id)
    rows = db.execute(q).all()

    status_count = Counter(r.status for r in rows)
    per_bucket, done_bucket = Counter(), Counter()
    per_proc, per_prof = Counter(), defaultdict(Counter)
    for r in rows:
        k = _bucket(r.start_at.date(), by)
        per_bucket[k] += 1
        if r.status == "concluido":
            done_bucket[k] += 1
        if r.status != "cancelado":
            per_proc[r.procedure_id] += 1
        per_prof[r.professional_id][r.status] += 1

    proc_names = dict(db.execute(select(Procedure.id, Procedure.name)).all())
    prof_names = dict(db.execute(select(Professional.id, Professional.full_name)).all())
    keys = _keys(start, end, by)

    # Pacientes
    if professional_id:
        total_patients = db.scalar(select(func.count(func.distinct(Appointment.patient_id))).where(
            Appointment.professional_id == professional_id)) or 0
        new_patients = len({r.patient_id for r in rows})
    else:
        total_patients = db.scalar(select(func.count(Patient.id)).where(Patient.deleted_at.is_(None))) or 0
        new_patients = db.scalar(select(func.count(Patient.id)).where(
            Patient.deleted_at.is_(None), Patient.created_at >= s, Patient.created_at < e)) or 0

    return {
        "period": {"start": start, "end": end, "group_by": by},
        "total_patients": total_patients,
        "new_patients": new_patients,
        "total_appointments": len(rows),
        "status_count": {k: status_count.get(k, 0) for k in
                         ("pendente", "confirmado", "em_atendimento", "concluido", "cancelado", "nao_compareceu")},
        "appointments_series": _series(keys, per_bucket),
        "attendances_series": _series(keys, done_bucket),
        "top_procedures": [{"name": proc_names.get(pid, "—"), "count": c} for pid, c in per_proc.most_common(8)],
        "productivity": sorted([
            {"professional": prof_names.get(pid, "—"), "total": sum(c.values()),
             "completed": c.get("concluido", 0), "cancelled": c.get("cancelado", 0),
             "no_show": c.get("nao_compareceu", 0),
             "completion_rate": round(100 * c.get("concluido", 0) / max(1, sum(c.values())), 1)}
            for pid, c in per_prof.items()], key=lambda x: -x["completed"]),
    }


def evolution_months(db: Session, today: date, professional_id: int | None = None, n: int = 6) -> dict:
    first, months = last_months(n, today)
    q = select(Appointment.start_at, Appointment.status).where(
        Appointment.start_at >= datetime.combine(first, time.min))
    if professional_id:
        q = q.where(Appointment.professional_id == professional_id)
    total, done = Counter(), Counter()
    for start_at, status in db.execute(q):
        k = start_at.strftime("%Y-%m")
        total[k] += 1
        if status == "concluido":
            done[k] += 1
    labels = [_label(m) for m in months]
    return {"labels": labels, "total": [total.get(m, 0) for m in months], "completed": [done.get(m, 0) for m in months]}


def no_show_patients(db: Session, start: date, end: date) -> list[dict]:
    s, e = _bounds(start, end)
    rows = db.execute(
        select(Patient.full_name, Patient.phone, Appointment.start_at, Procedure.name)
        .join(Patient, Patient.id == Appointment.patient_id)
        .join(Procedure, Procedure.id == Appointment.procedure_id)
        .where(Appointment.status == "nao_compareceu", Appointment.start_at >= s, Appointment.start_at < e)
        .order_by(Appointment.start_at.desc())).all()
    return [{"patient": r[0], "phone": r[1], "start_at": r[2], "procedure": r[3]} for r in rows]


def finance_summary(db: Session, start: date, end: date) -> dict:
    s, e = _bounds(start, end)
    paid = db.execute(select(Payment.amount, Payment.method, Payment.procedure_id).where(
        Payment.status == "pago", Payment.paid_at >= s, Payment.paid_at < e)).all()
    pending = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == "pendente", Payment.created_at >= s, Payment.created_at < e)) or 0
    by_method, by_proc = defaultdict(float), defaultdict(float)
    names = dict(db.execute(select(Procedure.id, Procedure.name)).all())
    for amount, method, pid in paid:
        by_method[method or "outro"] += float(amount)
        by_proc[names.get(pid, "Sem procedimento")] += float(amount)
    return {"received": round(sum(float(a) for a, _, _ in paid), 2), "pending": round(float(pending), 2),
            "paid_count": len(paid),
            "by_method": [{"method": k, "total": round(v, 2)} for k, v in sorted(by_method.items(), key=lambda x: -x[1])],
            "by_procedure": [{"procedure": k, "total": round(v, 2)} for k, v in sorted(by_proc.items(), key=lambda x: -x[1])]}


def today_agenda(db: Session, professional_id: int | None = None) -> list[dict]:
    today = today_local()
    s, e = _bounds(today, today)
    q = (select(Appointment).where(Appointment.start_at >= s, Appointment.start_at < e)
         .order_by(Appointment.start_at))
    if professional_id:
        q = q.where(Appointment.professional_id == professional_id)
    out = []
    for a in db.scalars(q):
        out.append({"id": a.id, "patient_name": a.patient.full_name, "patient_age": calc_age(a.patient.birth_date),
                    "start_at": a.start_at, "end_at": a.end_at, "procedure_id": a.procedure_id,
                    "procedure_name": a.procedure.name, "professional_id": a.professional_id,
                    "professional_name": a.professional.full_name, "status": a.status})
    return out
