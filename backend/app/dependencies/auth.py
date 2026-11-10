import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.security import decode_access_token
from ..database import get_db
from ..models import Patient, Professional, User

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbDep) -> User:
    token = request.cookies.get("access_token")
    data = decode_access_token(token) if token else None
    if not data:
        raise HTTPException(401, "Sessão inválida ou expirada. Faça login novamente.")
    if request.method not in SAFE_METHODS:  # CSRF: double-submit com valor assinado dentro do JWT
        sent = request.headers.get("x-csrf-token", "")
        if not sent or not secrets.compare_digest(sent, str(data.get("csrf", ""))):
            raise HTTPException(403, "Falha na verificação de segurança. Recarregue a página e tente novamente.")
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(401, "Sessão inválida ou expirada. Faça login novamente.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    """RBAC aplicado no backend: o frontend apenas esconde menus, quem decide é esta dependência."""

    def dep(user: CurrentUser) -> User:
        if user.role.name not in roles:
            raise HTTPException(403, "Você não tem permissão para realizar esta operação.")
        return user

    return dep


def patient_of(db: Session, user: User) -> Patient:
    p = db.scalar(select(Patient).where(Patient.user_id == user.id, Patient.deleted_at.is_(None)))
    if not p:
        raise HTTPException(404, "Cadastro de paciente não encontrado.")
    return p


def professional_of(db: Session, user: User) -> Professional:
    p = db.scalar(select(Professional).where(Professional.user_id == user.id, Professional.deleted_at.is_(None)))
    if not p:
        raise HTTPException(403, "Seu usuário não está vinculado a um cadastro de profissional.")
    return p
