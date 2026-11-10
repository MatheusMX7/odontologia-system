"""Fixtures. Por padrão roda em SQLite (portável). Para testar com PostgreSQL (recomendado):

    TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/odontologia_test pytest
"""
import os
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_odonto.db")
os.environ["ENVIRONMENT"] = "test"
os.environ["MAX_LOGIN_ATTEMPTS"] = "5"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.constants import ROLES  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.timeutils import now_local  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Appointment, ClinicSettings, Patient, Procedure, Professional, Role, Schedule, User)  # noqa: E402
from app.routers.auth import reset_limiter  # noqa: E402

IS_PG = get_settings().database_url.startswith("postgresql")
PASSWORD = "Senha123"
_counter = {"n": 0}

VALID_CPFS = ["52998224725", "11144477735", "39053344705", "15350946056", "86288366757", "74847693034",
              "23588337066", "12345678909", "98765432100", "00000000191", "45317828791", "71428793860"]


def _cpf(n: int) -> str:
    """Gera CPF válido determinístico."""
    base = f"{n:09d}"
    d = [int(c) for c in base]
    for k in (9, 10):
        d.append((sum(d[i] * (k + 1 - i) for i in range(k)) * 10 % 11) % 10)
    return "".join(map(str, d))


def uniq() -> int:
    _counter["n"] += 1
    return _counter["n"] + 100000


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    reset_limiter()
    with SessionLocal() as db:
        for r in ROLES:
            db.add(Role(name=r))
        db.add(ClinicSettings(id=1, name="Clínica Teste", working_days="0,1,2,3,4,5,6", slot_minutes=30,
                              cancel_min_hours=24, max_advance_days=90, auto_confirm=False))
        db.commit()
    yield


def new_client() -> TestClient:
    return TestClient(app)


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = client.cookies.get("csrf_token")
    return r.json()


def make_user(db, role: str, email: str | None = None, name: str | None = None) -> User:
    n = uniq()
    r = db.scalar(select(Role).where(Role.name == role))
    u = User(email=email or f"{role}{n}@teste.com", full_name=name or f"{role.title()} {n}",
             password_hash=hash_password(PASSWORD), role_id=r.id)
    db.add(u)
    db.flush()
    return u


def make_patient(db, with_user: bool = True) -> Patient:
    n = uniq()
    u = make_user(db, "paciente", f"pac{n}@teste.com", f"Paciente {n}") if with_user else None
    p = Patient(user_id=u.id if u else None, full_name=f"Paciente {n}", cpf=_cpf(n), birth_date=date(1990, 3, 15),
                phone="81999990000", email=f"pac{n}@teste.com", address="Rua Teste, 123")
    db.add(p)
    db.flush()
    return p


def make_professional(db, procedures, with_user: bool = True, full_week: bool = True) -> Professional:
    n = uniq()
    u = make_user(db, "dentista", f"dent{n}@teste.com", f"Dr. {n}") if with_user else None
    p = Professional(user_id=u.id if u else None, full_name=f"Dr. {n}", cpf=_cpf(n), cro=f"CRO{n}",
                     specialty="Clínica geral", phone="81988880000", email=f"dent{n}@teste.com")
    p.procedures = list(procedures)
    if full_week:
        for wd in range(7):
            p.schedules.append(Schedule(weekday=wd, start_time=time(8), end_time=time(18),
                                        break_start=time(12), break_end=time(14)))
    db.add(p)
    db.flush()
    return p


def make_procedure(db, name="Limpeza", minutes=30, price="100.00", active=True) -> Procedure:
    p = Procedure(name=f"{name} {uniq()}", category="geral", description="d", duration_minutes=minutes,
                  price=price, is_active=active)
    db.add(p)
    db.flush()
    return p


def make_appt(db, patient, prof, proc, start: datetime, status="pendente") -> Appointment:
    a = Appointment(patient_id=patient.id, professional_id=prof.id, procedure_id=proc.id, start_at=start,
                    end_at=start + timedelta(minutes=proc.duration_minutes), status=status)
    db.add(a)
    db.flush()
    return a


def future_day(days: int = 3) -> date:
    return (now_local() + timedelta(days=days)).date()


def iso(day: date, hh: int, mm: int = 0) -> str:
    return datetime.combine(day, time(hh, mm)).isoformat()


@pytest.fixture
def clinic():
    """Cenário padrão: admin, recepção, dentista com agenda, 2 pacientes e 1 procedimento."""
    with SessionLocal() as db:
        proc = make_procedure(db)
        prof = make_professional(db, [proc])
        pat_a, pat_b = make_patient(db), make_patient(db)
        admin = make_user(db, "admin", "admin@teste.com")
        recep = make_user(db, "recepcionista", "recep@teste.com")
        db.commit()
        ns = SimpleNamespace(
            proc_id=proc.id, prof_id=prof.id, prof_email=db.get(User, prof.user_id).email,
            pat_a_id=pat_a.id, pat_a_email=pat_a.email, pat_b_id=pat_b.id, pat_b_email=pat_b.email,
            admin_email=admin.email, recep_email=recep.email)
    return ns


@pytest.fixture
def as_admin(clinic):
    c = new_client(); login(c, clinic.admin_email); return c


@pytest.fixture
def as_recep(clinic):
    c = new_client(); login(c, clinic.recep_email); return c


@pytest.fixture
def as_dentist(clinic):
    c = new_client(); login(c, clinic.prof_email); return c


@pytest.fixture
def as_patient_a(clinic):
    c = new_client(); login(c, clinic.pat_a_email); return c


@pytest.fixture
def as_patient_b(clinic):
    c = new_client(); login(c, clinic.pat_b_email); return c
