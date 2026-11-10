from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..core.security import hash_password
from ..dependencies.auth import DbDep, require_roles
from ..models import Patient, Role, User
from ..schemas.auth import UserActiveIn, UserCreateIn
from ..services.audit import audit

router = APIRouter(prefix="/api/usuarios", tags=["Usuários (administrador)"])
AdminOnly = require_roles("admin")


def _out(u: User) -> dict:
    return {"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role.name, "is_active": u.is_active,
            "last_login_at": u.last_login_at}


@router.get("")
def listar(db: DbDep, _=Depends(AdminOnly)):
    rows = db.scalars(select(User).join(Role).where(Role.name != "paciente", User.deleted_at.is_(None)).order_by(User.full_name))
    return [_out(u) for u in rows.unique()]


@router.post("", status_code=201)
def criar(body: UserCreateIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    if db.scalar(select(User.id).where(User.email == body.email)) or db.scalar(select(Patient.id).where(Patient.email == body.email)):
        raise HTTPException(409, "Já existe um usuário com este e-mail.")
    role = db.scalar(select(Role).where(Role.name == body.role))
    u = User(email=body.email, full_name=body.full_name, password_hash=hash_password(body.password), role_id=role.id)
    db.add(u)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe um usuário com este e-mail.")
    audit(db, admin, "create", "user", u.id, f"Perfil {body.role}", request)
    db.commit()
    db.refresh(u)
    return _out(u)


@router.patch("/{user_id}/status")
def alterar_status(user_id: int, body: UserActiveIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    u = db.get(User, user_id)
    if not u or u.deleted_at or u.role.name == "paciente":
        raise HTTPException(404, "Usuário não encontrado.")
    if u.id == admin.id and not body.is_active:
        raise HTTPException(422, "Você não pode desativar o seu próprio usuário.")
    u.is_active = body.is_active
    audit(db, admin, "activate" if body.is_active else "deactivate", "user", u.id, None, request)
    db.commit()
    return _out(u)
