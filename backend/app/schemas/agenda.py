from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from ..core.constants import PAYMENT_METHODS, PAYMENT_STATUSES, STATUSES
from ..core.timeutils import to_local_naive
from ..core.validators import clean_text


class AppointmentCreate(BaseModel):
    procedure_id: int
    professional_id: int
    start_at: datetime
    patient_id: int | None = None  # somente equipe (admin/recepcionista)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("start_at")
    @classmethod
    def _tz(cls, v):
        return to_local_naive(v)

    @field_validator("notes", mode="before")
    @classmethod
    def _n(cls, v):
        return clean_text(v)


class RescheduleIn(BaseModel):
    start_at: datetime
    professional_id: int | None = None

    @field_validator("start_at")
    @classmethod
    def _tz(cls, v):
        return to_local_naive(v)


class StatusChangeIn(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v not in STATUSES:
            raise ValueError("Status inválido.")
        return v

    @field_validator("reason", mode="before")
    @classmethod
    def _r(cls, v):
        return clean_text(v)


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("reason", mode="before")
    @classmethod
    def _r(cls, v):
        return clean_text(v)


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_age: int
    procedure_id: int
    procedure_name: str
    professional_id: int
    professional_name: str
    start_at: datetime
    end_at: datetime
    status: str
    notes: str | None
    cancel_reason: str | None
    can_cancel: bool
    can_reschedule: bool


class AttendanceStartIn(BaseModel):
    appointment_id: int


class AttendanceFinishIn(BaseModel):
    observations: str | None = Field(default=None, max_length=5000)

    @field_validator("observations", mode="before")
    @classmethod
    def _o(cls, v):
        return clean_text(v)


class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("content", mode="before")
    @classmethod
    def _c(cls, v):
        return clean_text(v)


class PaymentCreateIn(BaseModel):
    patient_id: int
    appointment_id: int | None = None
    procedure_id: int | None = None
    amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    method: str | None = None
    status: str = "pendente"
    notes: str | None = Field(default=None, max_length=255)

    @field_validator("method")
    @classmethod
    def _m(cls, v):
        if v is not None and v not in PAYMENT_METHODS:
            raise ValueError("Forma de pagamento inválida.")
        return v

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v not in ("pendente", "pago"):
            raise ValueError("Situação inválida.")
        return v

    @field_validator("notes", mode="before")
    @classmethod
    def _n(cls, v):
        return clean_text(v)


class PayIn(BaseModel):
    method: str
    paid_at: datetime | None = None

    @field_validator("method")
    @classmethod
    def _m(cls, v):
        if v not in PAYMENT_METHODS:
            raise ValueError("Forma de pagamento inválida.")
        return v

    @field_validator("paid_at")
    @classmethod
    def _tz(cls, v):
        return to_local_naive(v) if v else v
