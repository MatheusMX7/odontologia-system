import re
from datetime import date

from .timeutils import today_local

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def is_valid_cpf(cpf: str) -> bool:
    d = only_digits(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        dv = (s * 10 % 11) % 10
        if dv != int(d[n]):
            return False
    return True


def validate_cpf(value: str) -> str:
    if not isinstance(value, str) or not is_valid_cpf(value):
        raise ValueError("CPF inválido.")
    return only_digits(value)


def validate_phone(value: str) -> str:
    d = only_digits(value)
    if len(d) not in (10, 11):
        raise ValueError("Telefone inválido. Informe DDD e número.")
    return d


def validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("A senha deve ter ao menos 8 caracteres.")
    if len(value) > 128:
        raise ValueError("A senha deve ter no máximo 128 caracteres.")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("A senha deve conter letras e números.")
    return value


def clean_text(value, no_markup: bool = False):
    """Remove caracteres de controle e espaços nas pontas. Em campos curtos, rejeita marcação HTML."""
    if not isinstance(value, str):
        return value
    v = _CTRL.sub("", value).strip()
    if no_markup and ("<" in v or ">" in v):
        raise ValueError("O campo contém caracteres não permitidos (< ou >).")
    return v


def calc_age(birth: date, today: date | None = None) -> int:
    today = today or today_local()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
