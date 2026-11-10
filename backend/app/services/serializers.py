from datetime import timedelta

from ..core.timeutils import now_local
from ..core.validators import calc_age
from ..models import Appointment, ClinicSettings, Patient, Procedure, Professional


def appointment_out(a: Appointment, cs: ClinicSettings) -> dict:
    notice_ok = a.start_at - now_local() >= timedelta(hours=cs.cancel_min_hours)
    changeable = a.status in ("pendente", "confirmado") and notice_ok
    return {
        "id": a.id, "patient_id": a.patient_id, "patient_name": a.patient.full_name,
        "patient_age": calc_age(a.patient.birth_date), "procedure_id": a.procedure_id,
        "procedure_name": a.procedure.name, "professional_id": a.professional_id,
        "professional_name": a.professional.full_name, "start_at": a.start_at, "end_at": a.end_at,
        "status": a.status, "notes": a.notes, "cancel_reason": a.cancel_reason,
        "can_cancel": changeable, "can_reschedule": changeable,
    }


def patient_out(p: Patient) -> dict:
    return {"id": p.id, "full_name": p.full_name, "cpf": p.cpf, "birth_date": p.birth_date,
            "age": calc_age(p.birth_date), "phone": p.phone, "email": p.email, "address": p.address,
            "has_account": p.user_id is not None, "created_at": p.created_at}


def procedure_out(p: Procedure) -> dict:
    ids = sorted(x.id for x in p.professionals if x.deleted_at is None)
    return {"id": p.id, "name": p.name, "category": p.category, "description": p.description,
            "guidance": p.guidance, "image_url": p.image_url, "duration_minutes": p.duration_minutes,
            "price": p.price, "is_active": p.is_active, "professional_ids": ids, "professionals_count": len(ids)}


def professional_out(p: Professional) -> dict:
    procs = [x for x in p.procedures if x.deleted_at is None]
    return {"id": p.id, "full_name": p.full_name, "cpf": p.cpf, "cro": p.cro, "specialty": p.specialty,
            "phone": p.phone, "email": p.email, "is_active": p.is_active, "has_account": p.user_id is not None,
            "procedure_ids": sorted(x.id for x in procs), "procedure_names": sorted(x.name for x in procs),
            "schedules": p.schedules}
