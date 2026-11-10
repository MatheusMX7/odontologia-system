import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import INSECURE_KEYS, get_settings
from .routers import (agendamentos, atendimentos, auth, configuracoes, dashboard, financeiro, pacientes,
                      procedimentos, profissionais, publico, relatorios, usuarios)

settings = get_settings()
if settings.environment == "production" and settings.secret_key in INSECURE_KEYS:
    raise RuntimeError("Defina um SECRET_KEY forte no .env antes de executar em produção.")

log = logging.getLogger("odontologia")
app = FastAPI(title="Sistema de Gestão Odontológica", version="1.0.0",
              description="API REST do portal do paciente e do painel administrativo.")

FIELD_LABELS = {
    "full_name": "Nome", "cpf": "CPF", "birth_date": "Data de nascimento", "phone": "Telefone", "email": "E-mail",
    "address": "Endereço", "password": "Senha", "password_confirm": "Confirmação de senha", "lgpd_consent": "Consentimento",
    "name": "Nome", "category": "Categoria", "duration_minutes": "Duração", "price": "Valor", "specialty": "Especialidade",
    "start_at": "Início", "end_at": "Fim", "amount": "Valor", "method": "Forma de pagamento", "status": "Situação",
    "slot_minutes": "Duração dos horários", "working_days": "Dias de atendimento", "role": "Perfil",
    "current_password": "Senha atual", "new_password": "Nova senha", "content": "Conteúdo", "cancel_min_hours": "Antecedência para cancelamento",
    "max_advance_days": "Antecedência máxima", "procedure_id": "Procedimento", "professional_id": "Profissional", "patient_id": "Paciente",
}


def _message(err: dict) -> str:
    field = str(err["loc"][-1]) if err.get("loc") else ""
    label = FIELD_LABELS.get(field, field or "Dados")
    t, msg = err.get("type", ""), err.get("msg", "")
    if t == "missing":
        return f"{label} é obrigatório."
    if msg.startswith("Value error, "):
        return msg[len("Value error, "):]
    if "email" in msg.lower() and "valid" in msg.lower():
        return "E-mail inválido."
    if t == "string_too_short":
        return f"{label} deve ter ao menos {err['ctx']['min_length']} caracteres."
    if t == "string_too_long":
        return f"{label} deve ter no máximo {err['ctx']['max_length']} caracteres."
    if t in ("greater_than_equal", "less_than_equal", "greater_than", "less_than"):
        return f"{label} está fora do limite permitido."
    if t.startswith(("date", "time")):
        return f"{label} inválido(a)."
    if t.endswith("_parsing") or t.endswith("_type"):
        return f"{label} inválido(a)."
    return f"{label} inválido(a)."


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = [{"field": str(e["loc"][-1]) if e.get("loc") else "", "message": _message(e)} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": " ".join(dict.fromkeys(e["message"] for e in errors)), "errors": errors})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("Erro não tratado em %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor. Tente novamente em instantes."})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


for r in (auth, usuarios, publico, pacientes, profissionais, procedimentos, agendamentos, atendimentos,
          financeiro, relatorios, configuracoes, dashboard):
    app.include_router(r.router)

settings.upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_path), name="uploads")
if settings.frontend_path.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_path, html=True), name="frontend")
