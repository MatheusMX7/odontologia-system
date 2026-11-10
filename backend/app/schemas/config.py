from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, field_validator

from ..core.validators import clean_text, validate_phone


class SettingsIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(default="", max_length=255)
    phone: str = ""
    email: str = Field(default="", max_length=255)
    opening_hours: str = Field(default="", max_length=255)
    working_days: list[int]
    slot_minutes: int
    cancel_min_hours: int = Field(ge=0, le=720)
    max_advance_days: int = Field(ge=1, le=365)
    auto_confirm: bool
    policy_text: str = Field(default="", max_length=3000)

    @field_validator("name", "address", "opening_hours", mode="before")
    @classmethod
    def _clean(cls, v):
        return clean_text(v, no_markup=True)

    @field_validator("policy_text", mode="before")
    @classmethod
    def _p(cls, v):
        return clean_text(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return validate_phone(v) if v else ""

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v):
        v = str(v).strip().lower() if v else ""
        if v:
            try:
                validate_email(v, check_deliverability=False)
            except EmailNotValidError:
                raise ValueError("E-mail inválido.")
        return v

    @field_validator("working_days")
    @classmethod
    def _days(cls, v):
        if not v or any(d < 0 or d > 6 for d in v):
            raise ValueError("Selecione ao menos um dia de atendimento válido.")
        return sorted(set(v))

    @field_validator("slot_minutes")
    @classmethod
    def _slot(cls, v):
        if v not in (10, 15, 20, 30, 40, 45, 60):
            raise ValueError("Duração padrão dos horários inválida.")
        return v
