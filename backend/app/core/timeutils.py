from datetime import date, datetime
from zoneinfo import ZoneInfo

from .config import get_settings


def clinic_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def now_local() -> datetime:
    """Data/hora atual no fuso da clínica, sem tzinfo (a agenda trabalha em horário local)."""
    return datetime.now(clinic_tz()).replace(tzinfo=None, microsecond=0)


def today_local() -> date:
    return now_local().date()


def to_local_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        dt = dt.astimezone(clinic_tz()).replace(tzinfo=None)
    return dt.replace(second=0, microsecond=0)
