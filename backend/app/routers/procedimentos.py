from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select

from ..core.timeutils import now_local
from ..dependencies.auth import DbDep, require_roles
from ..models import Appointment, Procedure, Professional
from ..schemas.cadastros import ProcedureIn, ProcedureOut
from ..services.audit import audit
from ..services.serializers import procedure_out
from ..services.uploads import save_image

router = APIRouter(prefix="/api/procedimentos", tags=["Procedimentos"])
Staff = require_roles("admin", "recepcionista", "dentista")
AdminOnly = require_roles("admin")


def _get(db, procedure_id: int) -> Procedure:
    p = db.get(Procedure, procedure_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(404, "Procedimento não encontrado.")
    return p


def _apply(db, p: Procedure, body: ProcedureIn) -> None:
    dup = db.scalar(select(Procedure.id).where(func.lower(Procedure.name) == body.name.lower(),
                                               Procedure.deleted_at.is_(None), Procedure.id != (p.id or 0)))
    if dup:
        raise HTTPException(409, "Já existe um procedimento com este nome.")
    p.name, p.category, p.description = body.name, body.category, body.description or ""
    p.guidance, p.duration_minutes, p.price, p.is_active = body.guidance or None, body.duration_minutes, body.price, body.is_active
    profs = list(db.scalars(select(Professional).where(Professional.id.in_(body.professional_ids), Professional.deleted_at.is_(None))))
    if len(profs) != len(set(body.professional_ids)):
        raise HTTPException(422, "Um ou mais profissionais informados não existem.")
    p.professionals = profs


@router.get("", response_model=list[ProcedureOut])
def listar(db: DbDep, _=Depends(Staff), incluir_inativos: bool = True):
    q = select(Procedure).where(Procedure.deleted_at.is_(None)).order_by(Procedure.category, Procedure.name)
    if not incluir_inativos:
        q = q.where(Procedure.is_active.is_(True))
    return [procedure_out(p) for p in db.scalars(q).unique()]


@router.post("", response_model=ProcedureOut, status_code=201)
def criar(body: ProcedureIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    p = Procedure()
    _apply(db, p, body)
    db.add(p)
    db.flush()
    audit(db, admin, "create", "procedure", p.id, p.name, request)
    db.commit()
    return procedure_out(p)


@router.get("/{procedure_id}", response_model=ProcedureOut)
def obter(procedure_id: int, db: DbDep, _=Depends(Staff)):
    return procedure_out(_get(db, procedure_id))


@router.put("/{procedure_id}", response_model=ProcedureOut)
def atualizar(procedure_id: int, body: ProcedureIn, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    p = _get(db, procedure_id)
    _apply(db, p, body)
    audit(db, admin, "update", "procedure", p.id, p.name + ("" if p.is_active else " (desativado)"), request)
    db.commit()
    return procedure_out(p)


@router.post("/{procedure_id}/imagem", response_model=ProcedureOut)
async def enviar_imagem(procedure_id: int, request: Request, db: DbDep, file: UploadFile = File(...), admin=Depends(AdminOnly)):
    p = _get(db, procedure_id)
    p.image_url = await save_image(file, "procedimentos")
    audit(db, admin, "update_image", "procedure", p.id, None, request)
    db.commit()
    return procedure_out(p)


@router.delete("/{procedure_id}", status_code=204)
def excluir(procedure_id: int, request: Request, db: DbDep, admin=Depends(AdminOnly)):
    """Exclusão lógica. Bloqueada se houver histórico ou agendamentos futuros: nesse caso, desative."""
    p = _get(db, procedure_id)
    used = db.scalar(select(func.count(Appointment.id)).where(Appointment.procedure_id == p.id))
    if used:
        raise HTTPException(409, "Este procedimento possui agendamentos no histórico e não pode ser excluído. Desative-o para ocultá-lo do portal.")
    p.deleted_at, p.is_active = now_local(), False
    audit(db, admin, "delete", "procedure", p.id, p.name, request)
    db.commit()
