from pydantic import BaseModel, EmailStr, Field, field_validator, ValidationInfo

from ..core.constants import ROLES
from ..core.validators import clean_text, validate_password
from .common import PersonBase, norm_email


class LoginIn(BaseModel):
    # str (não EmailStr): o login só compara com o cadastro e não deve recusar domínios incomuns/reservados
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v):
        return norm_email(v)


class RegisterIn(PersonBase):
    password: str
    password_confirm: str
    lgpd_consent: bool

    @field_validator("password")
    @classmethod
    def _pwd(cls, v):
        return validate_password(v)

    @field_validator("password_confirm")
    @classmethod
    def _match(cls, v, info: ValidationInfo):
        if info.data.get("password") is not None and v != info.data["password"]:
            raise ValueError("As senhas não conferem.")
        return v

    @field_validator("lgpd_consent")
    @classmethod
    def _consent(cls, v):
        if v is not True:
            raise ValueError("É necessário concordar com o tratamento de dados pessoais para criar a conta.")
        return v


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _pwd(cls, v):
        return validate_password(v)


class UserCreateIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    email: EmailStr
    password: str
    role: str

    @field_validator("full_name", mode="before")
    @classmethod
    def _clean(cls, v):
        return clean_text(v, no_markup=True)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v):
        return norm_email(v)

    @field_validator("password")
    @classmethod
    def _pwd(cls, v):
        return validate_password(v)

    @field_validator("role")
    @classmethod
    def _role(cls, v):
        if v not in ("admin", "recepcionista"):
            raise ValueError("Perfil inválido. Usuários de dentistas são criados no cadastro do profissional.")
        return v


class UserActiveIn(BaseModel):
    is_active: bool
