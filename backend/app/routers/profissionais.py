from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..core.security import hash_password
from ..core.timeutils import now_local
from ..dependencies.auth import DbDep, require_roles
from ..models import Appointment, Patient, Procedure, Professional, Role, Schedule, ScheduleBlock, User
from ..schemas.cadastros import BlockIn, BlockOut, ProfessionalIn, ProfessionalOut, ScheduleIn, StatusIn
from ..services.audit import audit
from ..services.serializers import professional_out

router = APIRouter(prefix="/api/profissionais", tags=["Profissionais"])
Staff = require_roles("admin", "recepcionista", "dentista")
AdminOnly = require_roles("admin")


def _get(db, pid: int) -> Professional:
    p = db.get(Professional, pid)
    if not p or p.deleted_at is not None:
        raise HTTPException(404, "Profissional não encontrado.")
    return p


def _check_unique(db, body: ProfessionalIn, pid: int = 0):
    if db.scalar(select(Professional.id).where(Professional.cpf == body.cpf, Professional.id != pid)):
        raise HTTPException(409, "Já existe um profissional com este CPF.")
    if db.scalar(select(Professional.id).where(Professional.email == body.email, Professional.id != pid)):
        raise HTTPException(409, "Já existe um profissional com este e-mail.")


def _set_procedures(db, p: Professional, ids: list[int]):
    procs = list(db.scalars(select(Procedure).where(Procedure.id.in_(ids), Procedure.deleted_at.is_(None))))
    if len(procs) != len(set(ids)):
        raise HTTPException(422, "Um ou mais procedimentos informados não existem.")
    p.procedures = procs


@router.get("", response_model=list[ProfessionalOut])
def listar(db: DbDep, _=Depends(Staff), incluir_inativos: bool = True):
    q = select(Professional).where(Professional.deleted_at.is_(None)).order_by(Professional.full_name)
    if not incluir_inativos:
        q = q.where(Professional.is_active.is_(True))
    return [professional_out(p) for p in db.scalars(q).unique()]


@router.post("", response_model=ProfessionalOut, status_code=201)
def criar(body: ProfessionalIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    _check_unique(db, body)
    p = Professional(full_name=body.full_name, cpf=body.cpf, cro=body.cro, specialty=body.specialty,
                     phone=body.phone, email=body.email)
    if body.create_account:
        if db.scalar(select(User.id).where(User.email == body.email)) or db.scalar(select(Patient.id).where(Patient.email == body.email)):
            raise HTTPException(409, "Já existe um usuário com este e-mail.")
        role = db.scalar(select(Role).where(Role.name == "dentista"))
        user = User(email=body.email, full_name=body.full_name, password_hash=hash_password(body.password), role_id=role.id)
        db.add(user)
        db.flush()
        p.user_id = user.id
    _set_procedures(db, p, body.procedure_ids)
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "CPF ou e-mail já cadastrado.")
    audit(db, admin, "create", "professional", p.id, p.full_name, request)
    db.commit()
    return professional_out(p)


@router.get("/{pid}", response_model=ProfessionalOut)
def obter(pid: int, db: DbDep, _=Depends(Staff)):
    return professional_out(_get(db, pid))


@router.put("/{pid}", response_model=ProfessionalOut)
def atualizar(pid: int, body: ProfessionalIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    p = _get(db, pid)
    _check_unique(db, body, pid)
    p.full_name, p.cpf, p.cro, p.specialty, p.phone, p.email = body.full_name, body.cpf, body.cro, body.specialty, body.phone, body.email
    if p.user_id:
        u = db.get(User, p.user_id)
        clash = db.scalar(select(User.id).where(User.email == body.email, User.id != u.id))
        if clash:
            raise HTTPException(409, "Já existe um usuário com este e-mail.")
        u.full_name, u.email = body.full_name, body.email
    _set_procedures(db, p, body.procedure_ids)
    audit(db, admin, "update", "professional", p.id, p.full_name, request)
    db.commit()
    return professional_out(p)


@router.patch("/{pid}/status", response_model=ProfessionalOut)
def alterar_status(pid: int, body: StatusIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    p = _get(db, pid)
    p.is_active = body.is_active
    if p.user_id:
        db.get(User, p.user_id).is_active = body.is_active
    audit(db, admin, "activate" if body.is_active else "deactivate", "professional", p.id, p.full_name, request)
    db.commit()
    return professional_out(p)


@router.delete("/{pid}", status_code=204)
def excluir(pid: int, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    p = _get(db, pid)
    if db.scalar(select(func.count(Appointment.id)).where(Appointment.professional_id == p.id)):
        raise HTTPException(409, "Este profissional possui agendamentos no histórico e não pode ser excluído. Desative o cadastro.")
    p.deleted_at, p.is_active = now_local(), False
    if p.user_id:
        u = db.get(User, p.user_id)
        u.is_active, u.deleted_at = False, now_local()
    audit(db, admin, "delete", "professional", p.id, p.full_name, request)
    db.commit()


@router.put("/{pid}/horarios", response_model=ProfessionalOut)
def definir_horarios(pid: int, body: list[ScheduleIn], request: Request, db: DbDep, admin=Depends(AdminOnly)):
    p = _get(db, pid)
    if len({s.weekday for s in body}) != len(body):
        raise HTTPException(422, "Informe apenas uma jornada por dia da semana.")
    p.schedules.clear()
    db.flush()
    for s in body:
        p.schedules.append(Schedule(weekday=s.weekday, start_time=s.start_time, end_time=s.end_time,
                                    break_start=s.break_start, break_end=s.break_end))
    audit(db, admin, "update_schedule", "professional", p.id, f"{len(body)} dia(s) de atendimento", request)
    db.commit()
    db.refresh(p)
    return professional_out(p)


@router.get("/{pid}/bloqueios", response_model=list[BlockOut])
def listar_bloqueios(pid: int, db: DbDep, _=Depends(Staff)):
    _get(db, pid)
    return list(db.scalars(select(ScheduleBlock).where(ScheduleBlock.professional_id == pid,
                                                       ScheduleBlock.end_at >= now_local()).order_by(ScheduleBlock.start_at)))


@router.post("/{pid}/bloqueios", response_model=BlockOut, status_code=201)
def criar_bloqueio(pid: int, body: BlockIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    _get(db, pid)
    b = ScheduleBlock(professional_id=pid, start_at=body.start_at, end_at=body.end_at, reason=body.reason)
    db.add(b)
    db.flush()
    audit(db, admin, "create", "schedule_block", b.id, body.reason, request)
    db.commit()
    return b


@router.delete("/{pid}/bloqueios/{block_id}", status_code=204)
def remover_bloqueio(pid: int, block_id: int, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    b = db.get(ScheduleBlock, block_id)
    if not b or b.professional_id != pid:
        raise HTTPException(404, "Bloqueio não encontrado.")
    db.delete(b)
    audit(db, admin, "delete", "schedule_block", block_id, None, request)
    db.commit()
