from fastapi import APIRouter, Depends, File, Request, UploadFile

from ..dependencies.auth import DbDep, require_roles
from ..schemas.config import SettingsIn
from ..services.audit import audit
from ..services.settings import get_clinic_settings, working_days
from ..services.uploads import save_image

router = APIRouter(prefix="/api/configuracoes", tags=["Configurações"])
AdminOnly = require_roles("admin")


def _out(cs) -> dict:
    return {"name": cs.name, "logo_url": cs.logo_url, "address": cs.address, "phone": cs.phone, "email": cs.email,
            "opening_hours": cs.opening_hours, "working_days": sorted(working_days(cs)), "slot_minutes": cs.slot_minutes,
            "cancel_min_hours": cs.cancel_min_hours, "max_advance_days": cs.max_advance_days,
            "auto_confirm": cs.auto_confirm, "policy_text": cs.policy_text}


@router.get("")
def obter(db: DbDep, _=Depends(AdminOnly)):
    return _out(get_clinic_settings(db))


@router.put("")
def atualizar(body: SettingsIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    cs = get_clinic_settings(db)
    cs.name, cs.address, cs.phone, cs.email, cs.opening_hours = body.name, body.address, body.phone, body.email, body.opening_hours
    cs.working_days = ",".join(str(d) for d in body.working_days)
    cs.slot_minutes, cs.cancel_min_hours, cs.max_advance_days = body.slot_minutes, body.cancel_min_hours, body.max_advance_days
    cs.auto_confirm, cs.policy_text = body.auto_confirm, body.policy_text
    audit(db, admin, "update", "clinic_settings", 1, None, request)
    db.commit()
    return _out(cs)


@router.post("/logo")
async def enviar_logo(request: Request, db: DbDep, file: UploadFile = File(...), admin=Depends(AdminOnly)):
    cs = get_clinic_settings(db)
    cs.logo_url = await save_image(file, "logo")
    audit(db, admin, "update_logo", "clinic_settings", 1, None, request)
    db.commit()
    return _out(cs)
