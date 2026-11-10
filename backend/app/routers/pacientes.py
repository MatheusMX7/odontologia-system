from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager

from ..core.constants import ACTIVE_STATUSES
from ..core.timeutils import now_local
from ..core.validators import only_digits
from ..dependencies.auth import CurrentUser, DbDep, patient_of, professional_of, require_roles
from ..models import Appointment, MedicalRecord, Patient, Professional, User
from ..schemas.cadastros import PatientCreate, PatientOut, PatientSelfUpdate, PatientUpdate
from ..services.audit import audit
from ..services.serializers import appointment_out, patient_out
from ..services.settings import get_clinic_settings

router = APIRouter(prefix="/api/pacientes", tags=["Pacientes"])
Staff = require_roles("admin", "recepcionista", "dentista")
Reception = require_roles("admin", "recepcionista")
Clinical = require_roles("admin", "dentista")


def _get(db, pid: int) -> Patient:
    p = db.get(Patient, pid)
    if not p or p.deleted_at is not None:
        raise HTTPException(404, "Paciente não encontrado.")
    return p


def _ensure_access(db, user: User, patient: Patient) -> None:
    """Dentista só acessa pacientes que atende (ou atendeu)."""
    if user.role.name == "dentista":
        prof = professional_of(db, user)
        if not db.scalar(select(func.count(Appointment.id)).where(Appointment.patient_id == patient.id,
                                                                  Appointment.professional_id == prof.id)):
            raise HTTPException(403, "Este paciente não está sob os seus cuidados.")


# ---- Área do próprio paciente (rotas fixas antes de /{id}) ----
@router.get("/me", response_model=PatientOut)
def meu_cadastro(user: CurrentUser, db: DbDep):
    if user.role.name != "paciente":
        raise HTTPException(403, "Disponível apenas para pacientes.")
    return patient_out(patient_of(db, user))


@router.put("/me", response_model=PatientOut)
def atualizar_meu_cadastro(body: PatientSelfUpdate, request: Request, user: CurrentUser, db: DbDep):
    if user.role.name != "paciente":
        raise HTTPException(403, "Disponível apenas para pacientes.")
    p = patient_of(db, user)
    p.phone, p.address = body.phone, body.address
    audit(db, user, "update_self", "patient", p.id, "Telefone/endereço", request)
    db.commit()
    return patient_out(p)


# ---- Gestão pela equipe ----
@router.get("")
def listar(db: DbDep, user=Depends(Staff), q: str | None = None, limite: int = Query(50, ge=1, le=200), pagina: int = Query(1, ge=1)):
    stmt = select(Patient).where(Patient.deleted_at.is_(None))
    if user.role.name == "dentista":
        prof = professional_of(db, user)
        stmt = stmt.where(Patient.id.in_(select(Appointment.patient_id).where(Appointment.professional_id == prof.id)))
    if q and q.strip():
        term, digits = q.strip(), only_digits(q)
        conds = [Patient.full_name.ilike(f"%{term}%")]
        if digits:
            conds.append(Patient.cpf.like(f"%{digits}%"))
        stmt = stmt.where(or_(*conds))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Patient.full_name).limit(limite).offset((pagina - 1) * limite))
    return {"items": [patient_out(p) for p in rows], "total": total}


@router.post("", response_model=PatientOut, status_code=201)
def criar(body: PatientCreate, request: Request, db: DbDep, user=Depends(Reception)):
    if db.scalar(select(Patient.id).where(Patient.cpf == body.cpf)):
        raise HTTPException(409, "Já existe um paciente com este CPF.")
    if db.scalar(select(Patient.id).where(Patient.email == body.email)):
        raise HTTPException(409, "Já existe um paciente com este e-mail.")
    p = Patient(full_name=body.full_name, cpf=body.cpf, birth_date=body.birth_date, phone=body.phone,
                email=body.email, address=body.address)
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "CPF ou e-mail já cadastrado.")
    audit(db, user, "create", "patient", p.id, None, request)
    db.commit()
    return patient_out(p)


@router.get("/{pid}", response_model=PatientOut)
def obter(pid: int, db: DbDep, user=Depends(Staff)):
    p = _get(db, pid)
    _ensure_access(db, user, p)
    return patient_out(p)


@router.put("/{pid}", response_model=PatientOut)
def atualizar(pid: int, body: PatientUpdate, request: Request, db: DbDep, user=Depends(Reception)):
    p = _get(db, pid)
    data = body.model_dump(exclude_none=True)
    if "cpf" in data and db.scalar(select(Patient.id).where(Patient.cpf == data["cpf"], Patient.id != pid)):
        raise HTTPException(409, "Já existe um paciente com este CPF.")
    if "email" in data:
        if db.scalar(select(Patient.id).where(Patient.email == data["email"], Patient.id != pid)):
            raise HTTPException(409, "Já existe um paciente com este e-mail.")
        if p.user_id and db.scalar(select(User.id).where(User.email == data["email"], User.id != p.user_id)):
            raise HTTPException(409, "Este e-mail já está em uso por outro usuário.")
    for k, v in data.items():
        setattr(p, k, v)
    if p.user_id:
        u = db.get(User, p.user_id)
        u.full_name, u.email = p.full_name, p.email
    audit(db, user, "update", "patient", p.id, ", ".join(sorted(data)), request)
    db.commit()
    return patient_out(p)


@router.delete("/{pid}", status_code=204)
def excluir(pid: int, request: Request, db: DbDep, user=Depends(require_roles("admin"))):
    """Exclusão lógica: preserva histórico e integridade dos registros."""
    p = _get(db, pid)
    p.deleted_at = now_local()
    if p.user_id:
        u = db.get(User, p.user_id)
        u.is_active, u.deleted_at = False, now_local()
    audit(db, user, "delete", "patient", p.id, None, request)
    db.commit()


@router.get("/{pid}/agendamentos")
def historico_agendamentos(pid: int, db: DbDep, user=Depends(Staff)):
    p = _get(db, pid)
    _ensure_access(db, user, p)
    cs = get_clinic_settings(db)
    q = (select(Appointment).join(Appointment.professional).where(Appointment.patient_id == pid)
         .options(contains_eager(Appointment.professional)).order_by(Appointment.start_at.desc()))
    if user.role.name == "dentista":
        q = q.where(Appointment.professional_id == professional_of(db, user).id)
    now = now_local()
    items = [appointment_out(a, cs) for a in db.scalars(q).unique()]
    return {"futuros": [a for a in items if a["start_at"] >= now and a["status"] in ("pendente", "confirmado")][::-1],
            "historico": [a for a in items if not (a["start_at"] >= now and a["status"] in ("pendente", "confirmado"))]}


@router.get("/{pid}/prontuario")
def prontuario(pid: int, request: Request, db: DbDep, user=Depends(Clinical)):
    """Dados clínicos (sensíveis): somente dentista responsável ou administrador. Toda leitura é auditada."""
    p = _get(db, pid)
    _ensure_access(db, user, p)
    rows = db.scalars(select(MedicalRecord).where(MedicalRecord.patient_id == pid).order_by(MedicalRecord.created_at.desc()))
    items = [{"id": r.id, "created_at": r.created_at, "professional_name": r.professional.full_name, "content": r.content}
             for r in rows]
    audit(db, user, "read_medical_record", "patient", pid, f"{len(items)} registro(s)", request)
    db.commit()
    return {"patient": patient_out(p), "records": items}
