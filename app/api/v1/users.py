"""
Endpoints de gestion de usuarios de la clinica.
CRUD para administrar equipo medico, recepcionistas y permisos.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.security import hash_password
from app.database import get_db
from app.models.clinic import Clinic
from app.models.user import User, UserRole
from app.models.user_clinic_access import UserClinicAccess
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter()

# ── Jerarquía de roles ───────────────────────────────
# Define qué roles puede crear cada rol.
ROLE_CAN_CREATE: dict[UserRole, set[UserRole]] = {
    UserRole.SUPER_ADMIN: {
        UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
        UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST,
    },
    UserRole.ORG_ADMIN: {
        UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST,
    },
    UserRole.CLINIC_ADMIN: {
        UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST,
    },
}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int
    pages: int


class ActiveToggle(BaseModel):
    is_active: bool


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: UserRole | None = Query(None, description="Filtrar por rol"),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
    )),
    db: AsyncSession = Depends(get_db),
):
    """Lista usuarios de la clinica con filtro opcional por rol."""
    query = select(User).where(User.clinic_id == user.clinic_id)
    count_query = select(func.count()).select_from(User).where(
        User.clinic_id == user.clinic_id
    )

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    # Total
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginar
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    users = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 1

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un nuevo usuario en la clinica del administrador.
    - org_admin puede crear: clinic_admin, doctor, receptionist
    - clinic_admin puede crear: doctor, receptionist
    Automaticamente crea UserClinicAccess para la sede destino.

    Si target_clinic_id está presente, el usuario se crea en esa sede
    (debe pertenecer a la misma organización del admin).
    """
    # Validar jerarquía de roles
    allowed = ROLE_CAN_CREATE.get(user.role, set())
    if data.role not in allowed:
        raise ForbiddenException(
            f"El rol {user.role.value} no puede crear usuarios con rol {data.role.value}"
        )

    # Determinar sede destino
    target_clinic_id = data.target_clinic_id or user.clinic_id

    if data.target_clinic_id and data.target_clinic_id != user.clinic_id:
        # Solo org_admin y super_admin pueden asignar a otra sede
        if user.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
            raise ForbiddenException(
                "Solo org_admin o super_admin pueden asignar usuarios a otra sede"
            )

        # Verificar que la sede destino pertenece a la misma organización
        admin_clinic = await db.execute(
            select(Clinic).where(Clinic.id == user.clinic_id)
        )
        admin_clinic_obj = admin_clinic.scalar_one_or_none()

        target_clinic = await db.execute(
            select(Clinic).where(Clinic.id == data.target_clinic_id)
        )
        target_clinic_obj = target_clinic.scalar_one_or_none()

        if not target_clinic_obj:
            raise NotFoundException("Sede destino no encontrada")

        if (
            not admin_clinic_obj
            or not admin_clinic_obj.organization_id
            or admin_clinic_obj.organization_id != target_clinic_obj.organization_id
        ):
            raise ForbiddenException(
                "La sede destino no pertenece a tu organización"
            )

    # Verificar email unico
    existing = await db.execute(
        select(User).where(User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise ConflictException("Ya existe un usuario con ese email")

    new_user = User(
        clinic_id=target_clinic_id,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
        first_name=data.first_name,
        last_name=data.last_name,
        cmp_number=data.cmp_number,
        specialty=data.specialty,
        phone=data.phone,
    )

    db.add(new_user)
    await db.flush()

    # Crear UserClinicAccess para la sede destino
    access = UserClinicAccess(
        user_id=new_user.id,
        clinic_id=target_clinic_id,
        role_in_clinic=data.role,
    )
    db.add(access)
    await db.flush()

    await db.refresh(new_user)
    return UserResponse.model_validate(new_user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
    )),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza datos de un usuario de la clinica."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.clinic_id == user.clinic_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundException("Usuario no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(target, field, value)

    await db.flush()
    await db.refresh(target)
    return UserResponse.model_validate(target)


@router.patch("/{user_id}/active", response_model=UserResponse)
async def toggle_user_active(
    user_id: UUID,
    data: ActiveToggle,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
    )),
    db: AsyncSession = Depends(get_db),
):
    """Activa o desactiva un usuario de la clinica."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.clinic_id == user.clinic_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundException("Usuario no encontrado")

    # No permitir desactivarse a si mismo
    if target.id == user.id and not data.is_active:
        raise ConflictException("No puedes desactivar tu propia cuenta")

    target.is_active = data.is_active
    await db.flush()
    await db.refresh(target)
    return UserResponse.model_validate(target)
