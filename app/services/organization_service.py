"""
Servicio de gestión de organizaciones y acceso multi-sede.
"""

import logging
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models.clinic import Clinic
from app.models.organization import Organization, PlanType
from app.models.user import User, UserRole
from app.models.user_clinic_access import UserClinicAccess

logger = logging.getLogger(__name__)


# ── CRUD Organization ────────────────────────────────

async def create_organization(
    db: AsyncSession,
    name: str,
    ruc: str,
    plan_type: PlanType = PlanType.BASIC,
    max_clinics: int = 1,
    contact_email: str | None = None,
    contact_phone: str | None = None,
) -> Organization:
    """Crear una nueva organización."""
    # Verificar RUC duplicado
    existing = await db.execute(
        select(Organization).where(Organization.ruc == ruc)
    )
    if existing.scalar_one_or_none():
        raise ConflictException("Ya existe una organización con este RUC")

    org = Organization(
        name=name,
        ruc=ruc,
        plan_type=plan_type,
        max_clinics=max_clinics,
        contact_email=contact_email,
        contact_phone=contact_phone,
    )
    db.add(org)
    await db.flush()

    logger.info(f"Organización creada: {org.name} (RUC: {org.ruc})")
    return org


async def get_organization(db: AsyncSession, org_id: UUID) -> Organization:
    """Obtener una organización por ID."""
    result = await db.execute(
        select(Organization)
        .options(selectinload(Organization.clinics))
        .where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundException("Organización", f"ID {org_id}")
    return org


async def update_organization(
    db: AsyncSession,
    org_id: UUID,
    **kwargs,
) -> Organization:
    """Actualizar una organización."""
    org = await get_organization(db, org_id)

    for key, value in kwargs.items():
        if value is not None and hasattr(org, key):
            setattr(org, key, value)

    await db.flush()
    return org


async def list_organizations(db: AsyncSession) -> list[Organization]:
    """Listar todas las organizaciones (super_admin only)."""
    result = await db.execute(
        select(Organization)
        .options(selectinload(Organization.clinics))
        .order_by(Organization.name)
    )
    return list(result.scalars().all())


# ── Gestión de sedes ─────────────────────────────────

async def add_clinic_to_organization(
    db: AsyncSession,
    org_id: UUID,
    clinic_id: UUID | None = None,
    name: str | None = None,
    branch_name: str | None = None,
    ruc: str | None = None,
    **clinic_kwargs,
) -> Clinic:
    """
    Agregar una sede a la organización.
    Puede vincular una clínica existente o crear una nueva.
    """
    org = await get_organization(db, org_id)

    # Verificar límite de sedes
    current_count = await db.execute(
        select(func.count(Clinic.id)).where(Clinic.organization_id == org_id)
    )
    count = current_count.scalar() or 0

    if count >= org.max_clinics:
        raise ValidationException(
            f"La organización ha alcanzado el límite de {org.max_clinics} "
            f"sedes (plan {org.plan_type.value}). Actualice su plan para agregar más."
        )

    if clinic_id:
        # Vincular clínica existente
        result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
        clinic = result.scalar_one_or_none()
        if not clinic:
            raise NotFoundException("Clínica", f"ID {clinic_id}")
        if clinic.organization_id and clinic.organization_id != org_id:
            raise ConflictException("Esta clínica ya pertenece a otra organización")
        clinic.organization_id = org_id
        if branch_name:
            clinic.branch_name = branch_name
    else:
        # Crear nueva sede
        if not name:
            raise ValidationException("Se requiere nombre para crear una nueva sede")

        # Verificar unicidad de nombre de sede en esta organización
        if branch_name:
            existing_branch = await db.execute(
                select(Clinic).where(
                    Clinic.organization_id == org_id,
                    Clinic.branch_name == branch_name
                )
            )
            if existing_branch.scalar_one_or_none():
                raise ConflictException(f"Ya existe una sede con el nombre '{branch_name}' en esta organización")

        clinic = Clinic(
            organization_id=org_id,
            name=name,
            branch_name=branch_name,
            ruc=ruc or org.ruc,
            **clinic_kwargs,
        )
        db.add(clinic)

    await db.flush()
    logger.info(f"Sede '{clinic.display_name}' agregada a org '{org.name}'")
    return clinic


async def list_org_clinics(db: AsyncSession, org_id: UUID) -> list[Clinic]:
    """Listar todas las sedes de una organización."""
    result = await db.execute(
        select(Clinic)
        .where(Clinic.organization_id == org_id, Clinic.is_active.is_(True))
        .order_by(Clinic.name, Clinic.branch_name)
    )
    return list(result.scalars().all())


# ── Acceso multi-sede de usuarios ────────────────────

async def grant_clinic_access(
    db: AsyncSession,
    user_id: UUID,
    clinic_id: UUID,
    role_in_clinic: UserRole,
) -> UserClinicAccess:
    """Otorgar acceso a un usuario a una sede con un rol específico."""
    # Verificar que no exista ya
    existing = await db.execute(
        select(UserClinicAccess).where(
            UserClinicAccess.user_id == user_id,
            UserClinicAccess.clinic_id == clinic_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException("El usuario ya tiene acceso a esta sede")

    access = UserClinicAccess(
        user_id=user_id,
        clinic_id=clinic_id,
        role_in_clinic=role_in_clinic,
    )
    db.add(access)
    await db.flush()

    logger.info(f"Acceso otorgado: user={user_id} clinic={clinic_id} role={role_in_clinic.value}")
    return access


async def revoke_clinic_access(
    db: AsyncSession,
    user_id: UUID,
    clinic_id: UUID,
) -> None:
    """Revocar acceso de un usuario a una sede."""
    result = await db.execute(
        select(UserClinicAccess).where(
            UserClinicAccess.user_id == user_id,
            UserClinicAccess.clinic_id == clinic_id,
        )
    )
    access = result.scalar_one_or_none()
    if not access:
        raise NotFoundException("Acceso", f"user={user_id} clinic={clinic_id}")

    await db.delete(access)
    await db.flush()
    logger.info(f"Acceso revocado: user={user_id} clinic={clinic_id}")


async def get_user_accessible_clinics(
    db: AsyncSession,
    user_id: UUID,
) -> list[dict]:
    """
    Obtener todas las sedes a las que un usuario tiene acceso.
    Incluye la sede principal (user.clinic_id) + accesos adicionales.
    """
    # Sede principal
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException("Usuario", f"ID {user_id}")

    clinics = []

    # Sede principal del usuario
    primary = await db.execute(
        select(Clinic).where(Clinic.id == user.clinic_id)
    )
    primary_clinic = primary.scalar_one_or_none()
    if primary_clinic:
        clinics.append({
            "clinic": primary_clinic,
            "role": user.role,
            "is_primary": True,
        })

    # Sedes adicionales via UserClinicAccess
    accesses = await db.execute(
        select(UserClinicAccess)
        .options(selectinload(UserClinicAccess.clinic))
        .where(
            UserClinicAccess.user_id == user_id,
            UserClinicAccess.is_active.is_(True),
            UserClinicAccess.clinic_id != user.clinic_id,
        )
    )
    for access in accesses.scalars().all():
        clinics.append({
            "clinic": access.clinic,
            "role": access.role_in_clinic,
            "is_primary": False,
        })

    return clinics


# ── Helpers cross-sede ────────────────────────────────

async def get_clinic_with_org(db: AsyncSession, clinic_id: UUID) -> Clinic:
    """Carga una clínica con su organization_id. Usada por servicios cross-sede."""
    result = await db.execute(
        select(Clinic).where(Clinic.id == clinic_id)
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise NotFoundException("Clínica")
    return clinic


async def get_org_clinic_ids(db: AsyncSession, organization_id: UUID) -> list[UUID]:
    """Retorna todos los IDs de sedes activas de una organización."""
    result = await db.execute(
        select(Clinic.id).where(
            Clinic.organization_id == organization_id,
            Clinic.is_active.is_(True),
        )
    )
    return [row[0] for row in result.all()]


async def validate_user_clinic_access(
    db: AsyncSession,
    user_id: UUID,
    clinic_id: UUID,
) -> bool:
    """Verificar si un usuario tiene acceso a una sede específica."""
    # Verificar sede principal
    result = await db.execute(
        select(User.clinic_id).where(User.id == user_id)
    )
    user_clinic_id = result.scalar_one_or_none()
    if user_clinic_id == clinic_id:
        return True

    # Verificar acceso adicional
    access = await db.execute(
        select(UserClinicAccess).where(
            UserClinicAccess.user_id == user_id,
            UserClinicAccess.clinic_id == clinic_id,
            UserClinicAccess.is_active.is_(True),
        )
    )
    return access.scalar_one_or_none() is not None
