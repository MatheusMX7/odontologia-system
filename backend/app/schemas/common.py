from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from ..core.timeutils import today_local
from ..core.validators import calc_age, clean_text, validate_cpf, validate_phone


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def norm_email(v):
    return str(v).strip().lower() if v is not None else v


class PersonBase(BaseModel):
    """Campos comuns de pessoa (paciente). Toda validação roda também no backend."""
    full_name: str = Field(min_length=3, max_length=150)
    cpf: str
    birth_date: date
    phone: str
    email: EmailStr
    address: str = Field(min_length=5, max_length=255)

    @field_validator("full_name", "address", mode="before")
    @classmethod
    def _clean(cls, v):
        return clean_text(v, no_markup=True)

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

    @field_validator("birth_date")
    @classmethod
    def _birth(cls, v):
        if v > today_local():
            raise ValueError("A data de nascimento não pode ser futura.")
        if v.year < 1900:
            raise ValueError("Data de nascimento inválida.")
        return v


class Page(BaseModel):
    items: list
    total: int


def age_of(birth: date) -> int:
    return calc_age(birth)
