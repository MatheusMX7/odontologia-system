from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Table, Text, Time, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.timeutils import now_local
from ..database import Base

professional_procedures = Table(
    "professional_procedures",
    Base.metadata,
    Column("professional_id", ForeignKey("professionals.id", ondelete="CASCADE"), primary_key=True),
    Column("procedure_id", ForeignKey("procedures.id", ondelete="CASCADE"), primary_key=True),
)

_ACTIVE_WHERE = text("status IN ('pendente','confirmado','em_atendimento','concluido')")


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    role: Mapped[Role] = relationship(lazy="joined")


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True)
    birth_date: Mapped[date] = mapped_column(Date)
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    address: Mapped[str] = mapped_column(String(255))
    lgpd_consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Professional(Base):
    __tablename__ = "professionals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True)
    cro: Mapped[str | None] = mapped_column(String(20))
    specialty: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    procedures: Mapped[list["Procedure"]] = relationship(secondary=professional_procedures, back_populates="professionals")
    schedules: Mapped[list["Schedule"]] = relationship(cascade="all, delete-orphan", order_by="Schedule.weekday")


class Procedure(Base):
    __tablename__ = "procedures"
    __table_args__ = (CheckConstraint("duration_minutes > 0", name="ck_procedure_duration"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    guidance: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(255))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    professionals: Mapped[list[Professional]] = relationship(secondary=professional_procedures, back_populates="procedures")


class Schedule(Base):
    """Jornada semanal do profissional (uma janela por dia da semana; 0 = segunda)."""
    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint("professional_id", "weekday", name="uq_schedule_prof_weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_schedule_weekday"),
        CheckConstraint("end_time > start_time", name="ck_schedule_times"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("professionals.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_start: Mapped[time | None] = mapped_column(Time)
    break_end: Mapped[time | None] = mapped_column(Time)


class ScheduleBlock(Base):
    """Bloqueio de agenda (férias, feriado, reunião). professional_id nulo = clínica inteira."""
    __tablename__ = "schedule_blocks"
    __table_args__ = (CheckConstraint("end_at > start_at", name="ck_block_times"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    professional_id: Mapped[int | None] = mapped_column(ForeignKey("professionals.id", ondelete="CASCADE"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_appointment_times"),
        # Rede de segurança no banco: dois agendamentos ativos não podem começar no mesmo
        # horário para o mesmo profissional, mesmo sob requisições simultâneas.
        Index(
            "uq_appointment_prof_start_active", "professional_id", "start_at", unique=True,
            postgresql_where=_ACTIVE_WHERE, sqlite_where=_ACTIVE_WHERE,
        ),
        Index("ix_appointment_prof_start", "professional_id", "start_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("professionals.id"))
    procedure_id: Mapped[int] = mapped_column(ForeignKey("procedures.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="pendente", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)

    patient: Mapped[Patient] = relationship()
    professional: Mapped[Professional] = relationship()
    procedure: Mapped[Procedure] = relationship()


class Attendance(Base):
    """Atendimento efetivamente realizado (diferente do agendamento)."""
    __tablename__ = "attendances"
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), unique=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("professionals.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    appointment: Mapped[Appointment] = relationship()
    patient: Mapped[Patient] = relationship()
    professional: Mapped[Professional] = relationship()


class MedicalRecord(Base):
    """Registro clínico (dado sensível de saúde): acesso restrito e sempre auditado."""
    __tablename__ = "medical_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("professionals.id"))
    attendance_id: Mapped[int | None] = mapped_column(ForeignKey("attendances.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    professional: Mapped[Professional] = relationship()


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_payment_amount"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    procedure_id: Mapped[int | None] = mapped_column(ForeignKey("procedures.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    method: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(15), default="pendente", index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    notes: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    patient: Mapped[Patient] = relationship()
    procedure: Mapped[Procedure | None] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, index=True)


class ClinicSettings(Base):
    __tablename__ = "clinic_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), default="Clínica Odontológica")
    logo_url: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    opening_hours: Mapped[str] = mapped_column(String(255), default="Segunda a sexta, das 08h às 18h")
    working_days: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4")
    slot_minutes: Mapped[int] = mapped_column(Integer, default=30)
    cancel_min_hours: Mapped[int] = mapped_column(Integer, default=24)
    max_advance_days: Mapped[int] = mapped_column(Integer, default=60)
    auto_confirm: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_text: Mapped[str] = mapped_column(Text, default="")
