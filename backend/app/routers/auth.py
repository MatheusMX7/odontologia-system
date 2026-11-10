import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..core.config import get_settings
from ..core.security import (DUMMY_HASH, create_access_token, hash_password, new_csrf_token, verify_password)
from ..core.timeutils import now_local
from ..dependencies.auth import CurrentUser, DbDep
from ..models import Patient, Professional, Role, User
from ..schemas.auth import LoginIn, PasswordChangeIn, RegisterIn
from ..services.audit import audit

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])

# Proteção contra força bruta (em memória; com vários workers use Redis ou um proxy com rate limit)
_failures: dict[str, list[float]] = defaultdict(list)
IP_LIMIT_FACTOR = 6


def reset_limiter() -> None:
    _failures.clear()


def _recent(key: str) -> list[float]:
    window = get_settings().login_lock_minutes * 60
    _failures[key] = [t for t in _failures[key] if time.time() - t < window]
    return _failures[key]


def _is_locked(ip: str, email: str) -> bool:
    s = get_settings()
    return len(_recent(f"{ip}|{email}")) >= s.max_login_attempts or len(_recent(ip)) >= s.max_login_attempts * IP_LIMIT_FACTOR


def _set_cookies(response: Response, user: User) -> None:
    s = get_settings()
    csrf = new_csrf_token()
    token = create_access_token(user.id, user.role.name, csrf)
    max_age = s.access_token_minutes * 60
    response.set_cookie("access_token", token, max_age=max_age, httponly=True, secure=s.cookie_secure,
                        samesite=s.cookie_samesite, path="/")
    response.set_cookie("csrf_token", csrf, max_age=max_age, httponly=False, secure=s.cookie_secure,
                        samesite=s.cookie_samesite, path="/")


def me_payload(db, user: User) -> dict:
    pat = db.scalar(select(Patient.id).where(Patient.user_id == user.id))
    pro = db.scalar(select(Professional.id).where(Professional.user_id == user.id))
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role.name,
            "patient_id": pat, "professional_id": pro}


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: DbDep):
    """Cadastro público de paciente. Coleta apenas dados necessários e registra o consentimento (LGPD)."""
    if db.scalar(select(Patient.id).where(Patient.cpf == body.cpf)):
        raise HTTPException(409, "Já existe um cadastro com este CPF. Se o cadastro é seu, procure a clínica.")
    if db.scalar(select(User.id).where(User.email == body.email)) or db.scalar(select(Patient.id).where(Patient.email == body.email)):
        raise HTTPException(409, "Já existe um cadastro com este e-mail.")
    role = db.scalar(select(Role).where(Role.name == "paciente"))
    user = User(email=body.email, full_name=body.full_name, password_hash=hash_password(body.password), role_id=role.id)
    db.add(user)
    try:
        db.flush()
        patient = Patient(user_id=user.id, full_name=body.full_name, cpf=body.cpf, birth_date=body.birth_date,
                          phone=body.phone, email=body.email, address=body.address, lgpd_consent_at=now_local())
        db.add(patient)
        db.flush()
        audit(db, user, "register", "patient", patient.id, "Autocadastro com consentimento LGPD", request)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "CPF ou e-mail já cadastrado.")
    db.refresh(user)
    _set_cookies(response, user)
    return me_payload(db, user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DbDep):
    ip = request.client.host if request.client else "?"
    key = f"{ip}|{body.email}"
    if _is_locked(ip, body.email):
        raise HTTPException(429, f"Muitas tentativas de acesso. Aguarde {get_settings().login_lock_minutes} minutos e tente novamente.")
    user = db.scalar(select(User).where(User.email == body.email))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not user or not valid or not user.is_active or user.deleted_at is not None:
        _failures[key].append(time.time())
        _failures[ip].append(time.time())
        audit(db, user, "login_failed", "user", user.id if user else None, f"Tentativa de login para {body.email}", request)
        db.commit()
        raise HTTPException(401, "E-mail ou senha incorretos.")
    _failures.pop(key, None)
    user.last_login_at = now_local()
    audit(db, user, "login", "user", user.id, None, request)
    db.commit()
    _set_cookies(response, user)
    return me_payload(db, user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("csrf_token", path="/")


@router.get("/me")
def me(user: CurrentUser, db: DbDep):
    return me_payload(db, user)


@router.post("/senha", status_code=204)
def change_password(body: PasswordChangeIn, request: Request, user: CurrentUser, db: DbDep):
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(422, "A senha atual está incorreta.")
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "password_change", "user", user.id, None, request)
    db.commit()
