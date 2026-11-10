from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog, User


def audit(db: Session, user: User | None, action: str, entity: str, entity_id: int | None = None,
          detail: str | None = None, request: Request | None = None) -> None:
    """Registra operação relevante. O commit fica a cargo do endpoint (mesma transação da operação)."""
    ip = request.client.host if request is not None and request.client else None
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity,
                    entity_id=entity_id, detail=(detail or "")[:500] or None, ip=ip))
