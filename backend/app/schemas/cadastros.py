from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from ..core.constants import CATEGORIES
from ..core.validators import calc_age, clean_text, validate_cpf, validate_password, validate_phone
from .common import ORM, PersonBase, norm_email
from ..core.timeutils import to_local_naive


# ---------------- Pacientes ----------------
class PatientCreate(PersonBase):
    pass


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=150)
    cpf: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = Field(default=None, min_length=5, max_length=255)

    @field_validator("full_name", "address", mode="before")
    @classmethod
    def _clean(cls, v):
        return clean_text(v, no_markup=True)

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v):
        return validate_cpf(v) if v is not None else v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return validate_phone(v) if v is not None else v

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v):
        return norm_email(v)

    @field_validator("birth_date")
    @classmethod
    def _birth(cls, v):
        if v is not None and (v > date.today() or v.year < 1900):
            raise ValueError("Data de nascimento inválida.")
        return v


class PatientSelfUpdate(BaseModel):
    """O paciente só pode alterar telefone e endereço (dados cadastrais sensíveis ficam com a clínica)."""
    phone: str
    address: str = Field(min_length=5, max_length=255)

    @field_validator("address", mode="before")
    @classmethod
    def _clean(cls, v):
        return clean_text(v, no_markup=True)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return validate_phone(v)


class PatientOut(ORM):
    id: int
    full_name: str
    cpf: str
    birth_date: date
    age: int
    phone: str
    email: str
    address: str
    has_account: bool
    created_at: datetime


# ---------------- Procedimentos ----------------
class ProcedureIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str
    description: str = Field(default="", max_length=2000)
    guidance: str | None = Field(default=None, max_length=2000)
    duration_minutes: int = Field(ge=5, le=480)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    is_active: bool = True
    professional_ids: list[int] = []

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v):
        return clean_text(v, no_markup=True)

    @field_validator("description", "guidance", mode="before")
    @classmethod
    def _txt(cls, v):
        return clean_text(v)

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v not in CATEGORIES:
            raise ValueError("Categoria inválida.")
        return v


class ProcedureOut(BaseModel):
    id: int
    name: str
    category: str
    description: str
    guidance: str | None
    image_url: str | None
    duration_minutes: int
    price: Decimal
    is_active: bool
    professional_ids: list[int]
    professionals_count: int


class PublicProcedureOut(BaseModel):
    id: int
    name: str
    category: str
    description: str
    guidance: str | None
    image_url: str | None
    duration_minutes: int
    available: bool


# ---------------- Profissionais ----------------
class ScheduleIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.end_time <= self.start_time:
            raise ValueError("O horário final deve ser depois do inicial.")
        if (self.break_start is None) != (self.break_end is None):
            raise ValueError("Informe início e fim do intervalo.")
        if self.break_start is not None:
            if not (self.start_time <= self.break_start < self.break_end <= self.end_time):
                raise ValueError("O intervalo deve estar dentro da jornada.")
        return self


class ScheduleOut(ORM):
    weekday: int
    start_time: time
    end_time: time
    break_start: time | None
    break_end: time | None


class BlockIn(BaseModel):
    start_at: datetime
    end_at: datetime
    reason: str = Field(default="", max_length=200)

    @field_validator("start_at", "end_at")
    @classmethod
    def _tz(cls, v):
        return to_local_naive(v)

    @field_validator("reason", mode="before")
    @classmethod
    def _r(cls, v):
        return clean_text(v, no_markup=True)

    @model_validator(mode="after")
    def _order(self):
        if self.end_at <= self.start_at:
            raise ValueError("O fim do bloqueio deve ser depois do início.")
        return self


class BlockOut(ORM):
    id: int
    professional_id: int | None
    start_at: datetime
    end_at: datetime
    reason: str


class ProfessionalIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    cpf: str
    cro: str | None = Field(default=None, max_length=20)
    specialty: str = Field(min_length=2, max_length=100)
    phone: str
    email: EmailStr
    procedure_ids: list[int] = []
    # Criação de acesso ao painel (somente no cadastro)
    create_account: bool = False
    password: str | None = None

    @field_validator("full_name", "specialty", "cro", mode="before")
    @classmethod
    def _clean(cls, v):
        v = clean_text(v, no_markup=True)
        return v or None if isinstance(v, str) and v == "" else v

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v):
        return validate_cpf(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return validate_phone(v)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v):
        return norm_email(v)

    @model_validator(mode="after")
    def _acct(self):
        if self.create_account:
            if not self.password:
                raise ValueError("Informe uma senha para criar o acesso do profissional.")
            validate_password(self.password)
        return self


class ProfessionalOut(BaseModel):
    id: int
    full_name: str
    cpf: str
    cro: str | None
    specialty: str
    phone: str
    email: str
    is_active: bool
    has_account: bool
    procedure_ids: list[int]
    procedure_names: list[str]
    schedules: list[ScheduleOut]


class PublicProfessionalOut(BaseModel):
    id: int
    full_name: str
    cro: str | None
    specialty: str


class StatusIn(BaseModel):
    is_active: bool
