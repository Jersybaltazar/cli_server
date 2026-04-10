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
from app.core.security import hash_password_async
from app.database import get_db
from app.models.clinic import Clinic
from app.models.user import User, UserRole
from app.models.user_clinic_access import UserClinicAccess
from app.schemas.user import (
    ControlledAuthorizationUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)


async def _get_visible_clinic_ids(user: User, db: AsyncSession) -> list:
    """
    Devuelve los clinic_ids visibles para un usuario:
    - org_admin / super_admin: todas las sedes de su organización
    - clinic_admin: solo su propia sede
    """
    if user.role in (UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN):
        admin_clinic = await db.execute(
            select(Clinic).where(Clinic.id == user.clinic_id)
        )
        admin_clinic_obj = admin_clinic.scalar_one_or_none()
        if admin_clinic_obj and admin_clinic_obj.organization_id:
            result = await db.execute(
                select(Clinic.id).where(
                    Clinic.organization_id == admin_clinic_obj.organization_id
                )
            )
            return list(result.scalars().all())
    return [user.clinic_id]

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
    clinic_ids = await _get_visible_clinic_ids(user, db)
    query = select(User).where(User.clinic_id.in_(clinic_ids))
    count_query = select(func.count()).select_from(User).where(
        User.clinic_id.in_(clinic_ids)
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

    # Cargar nombres de sedes para enriquecer la respuesta
    clinics_result = await db.execute(
        select(Clinic.id, Clinic.name, Clinic.branch_name).where(
            Clinic.id.in_(clinic_ids)
        )
    )
    clinic_map = {row.id: row for row in clinics_result.all()}

    def _to_response(u: User) -> UserResponse:
        data = UserResponse.model_validate(u)
        clinic = clinic_map.get(u.clinic_id)
        if clinic:
            data.clinic_name = clinic.name
            data.clinic_branch_name = clinic.branch_name
        return data

    return UserListResponse(
        items=[_to_response(u) for u in users],
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
        hashed_password=await hash_password_async(data.password),
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
    clinic_ids = await _get_visible_clinic_ids(user, db)
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.clinic_id.in_(clinic_ids),
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
    clinic_ids = await _get_visible_clinic_ids(user, db)
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.clinic_id.in_(clinic_ids),
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


@router.patch(
    "/{user_id}/controlled-authorization",
    response_model=UserResponse,
)
async def set_controlled_authorization(
    user_id: UUID,
    data: ControlledAuthorizationUpdate,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Autoriza o revoca a un médico para prescribir sustancias controladas
    (psicotrópicos y estupefacientes — DS 023-2001-SA).

    Solo administradores de clínica, organización y super-admin pueden
    modificar este permiso. El cambio queda registrado para auditoría.
    """
    clinic_ids = await _get_visible_clinic_ids(user, db)
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.clinic_id.in_(clinic_ids),
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundException("Usuario no encontrado")

    if target.role not in (UserRole.DOCTOR, UserRole.OBSTETRA):
        raise ConflictException(
            "Solo médicos y obstetras pueden recibir autorización para controlados"
        )

    target.is_authorized_controlled = data.is_authorized_controlled
    if data.is_authorized_controlled:
        target.controlled_authorization_number = data.controlled_authorization_number
        target.controlled_authorization_expiry = data.controlled_authorization_expiry
    else:
        target.controlled_authorization_number = None
        target.controlled_authorization_expiry = None

    await db.flush()
    await db.refresh(target)
    return UserResponse.model_validate(target)
