"""
Servicio de Audit Log — registra todas las operaciones sensibles.
INSERT-only, nunca se modifica ni elimina.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def _sanitize_for_json(data: dict | None) -> dict | None:
    """Convierte tipos no serializables (date, datetime, UUID, Decimal) a strings."""
    if data is None:
        return None
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, (date, datetime)):
            sanitized[key] = value.isoformat()
        elif isinstance(value, UUID):
            sanitized[key] = str(value)
        elif isinstance(value, Decimal):
            sanitized[key] = float(value)
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_for_json(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize_for_json(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


async def log_action(
    db: AsyncSession,
    *,
    clinic_id: UUID,
    user_id: UUID | None,
    entity: str,
    entity_id: str,
    action: str,
    old_data: dict | None = None,
    new_data: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Inserta un registro de auditoría inmutable."""
    entry = AuditLog(
        clinic_id=clinic_id,
        user_id=user_id,
        entity=entity,
        entity_id=str(entity_id),
        action=action,
        old_data=_sanitize_for_json(old_data),
        new_data=_sanitize_for_json(new_data),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_audit_logs(
    db: AsyncSession,
    *,
    clinic_id: UUID,
    page: int = 1,
    size: int = 15,
    action: str | None = None,
    entity: str | None = None,
    search: str | None = None,
) -> dict:
    """Consulta paginada del audit log para una clínica."""
    from sqlalchemy import select, func as sa_func
    from math import ceil

    query = select(AuditLog).where(AuditLog.clinic_id == clinic_id)
    count_query = select(sa_func.count(AuditLog.id)).where(AuditLog.clinic_id == clinic_id)

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    if entity:
        query = query.where(AuditLog.entity == entity)
        count_query = count_query.where(AuditLog.entity == entity)

    if search:
        search_filter = (
            AuditLog.entity.ilike(f"%{search}%")
            | AuditLog.entity_id.ilike(f"%{search}%")
            | AuditLog.action.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated items
    offset = (page - 1) * size
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": ceil(total / size) if size > 0 else 1,
    }

