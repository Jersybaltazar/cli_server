"""
Endpoints de gestión de organizaciones y sucursales.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.auth.jwt import create_access_token, create_refresh_token
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.organization import (
    AddClinicToOrgRequest,
    ClinicBranchResponse,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    OrganizationWithClinicsResponse,
    SwitchClinicRequest,
    SwitchClinicResponse,
    UserClinicAccessCreate,
    UserClinicAccessResponse,
)
from app.services import organization_service as org_svc

router = APIRouter()


# ── Rutas fijas (DEBEN ir antes de /{org_id}) ────────

@router.get(
    "/my-clinics",
    summary="Mis sedes accesibles",
    description="Lista todas las sedes a las que el usuario tiene acceso.",
)
async def my_clinics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cualquier usuario autenticado puede ver sus sedes.
    Si no tiene registros en UserClinicAccess, retorna solo su sede principal.
    """
    clinics = await org_svc.get_user_accessible_clinics(db, user.id)
    return [
        {
            "clinic_id": c["clinic"].id,
            "clinic_name": c["clinic"].display_name,
            "organization_id": str(c["clinic"].organization_id) if c["clinic"].organization_id else None,
            "role": c["role"].value if hasattr(c["role"], "value") else c["role"],
            "is_primary": c["is_primary"],
        }
        for c in clinics
    ]


@router.post(
    "/switch-clinic",
    response_model=SwitchClinicResponse,
    summary="Cambiar sede activa",
    description=(
        "Genera nuevos tokens JWT con la sede seleccionada. "
        "El usuario debe tener acceso a la sede destino."
    ),
)
async def switch_clinic(
    data: SwitchClinicRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SwitchClinicResponse:
    # Verificar acceso
    has_access = await org_svc.validate_user_clinic_access(db, user.id, data.clinic_id)
    if not has_access:
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("No tiene acceso a esta sede")

    # Obtener nombre de la clínica
    from sqlalchemy import select
    from app.models.clinic import Clinic
    result = await db.execute(select(Clinic).where(Clinic.id == data.clinic_id))
    clinic = result.scalar_one()

    # Generar nuevos tokens con el nuevo clinic_id
    access_token = create_access_token(
        user_id=user.id,
        clinic_id=data.clinic_id,
        role=user.role.value,
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        clinic_id=data.clinic_id,
    )

    return SwitchClinicResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        clinic_id=data.clinic_id,
        clinic_name=clinic.display_name,
    )


# ── CRUD Organization ────────────────────────────────

@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=201,
    summary="Crear organización",
    description="Crea una nueva organización (grupo empresarial). Solo super_admin.",
)
async def create_organization(
    data: OrganizationCreate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    org = await org_svc.create_organization(
        db=db,
        name=data.name,
        ruc=data.ruc,
        plan_type=data.plan_type,
        max_clinics=data.max_clinics,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
    )
    return OrganizationResponse.model_validate(org)


@router.get(
    "/",
    response_model=list[OrganizationResponse],
    summary="Listar organizaciones",
    description="Lista todas las organizaciones. Solo super_admin.",
)
async def list_organizations(
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationResponse]:
    orgs = await org_svc.list_organizations(db)
    return [OrganizationResponse.model_validate(o) for o in orgs]


@router.get(
    "/{org_id}",
    response_model=OrganizationWithClinicsResponse,
    summary="Obtener organización con sedes",
    description="Obtiene una organización con todas sus sedes. super_admin u org_admin.",
)
async def get_organization(
    org_id: UUID,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> OrganizationWithClinicsResponse:
    org = await org_svc.get_organization(db, org_id)
    return OrganizationWithClinicsResponse.model_validate(org)


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Actualizar organización",
)
async def update_organization(
    org_id: UUID,
    data: OrganizationUpdate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    org = await org_svc.update_organization(
        db=db,
        org_id=org_id,
        **data.model_dump(exclude_unset=True),
    )
    return OrganizationResponse.model_validate(org)


# ── Gestión de sedes ─────────────────────────────────

@router.post(
    "/{org_id}/clinics",
    response_model=ClinicBranchResponse,
    status_code=201,
    summary="Agregar sede a organización",
    description="Agrega una nueva sede o vincula una clínica existente a la organización.",
)
async def add_clinic_to_org(
    org_id: UUID,
    data: AddClinicToOrgRequest,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClinicBranchResponse:
    clinic = await org_svc.add_clinic_to_organization(
        db=db,
        org_id=org_id,
        clinic_id=data.clinic_id,
        name=data.name,
        branch_name=data.branch_name,
        address=data.address,
        phone=data.phone,
        email=data.email,
        specialty_type=data.specialty_type,
    )
    return ClinicBranchResponse.model_validate(clinic)


@router.get(
    "/{org_id}/clinics",
    response_model=list[ClinicBranchResponse],
    summary="Listar sedes de una organización",
)
async def list_org_clinics(
    org_id: UUID,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[ClinicBranchResponse]:
    clinics = await org_svc.list_org_clinics(db, org_id)
    return [ClinicBranchResponse.model_validate(c) for c in clinics]


# ── Acceso multi-sede ────────────────────────────────

@router.post(
    "/access",
    response_model=UserClinicAccessResponse,
    status_code=201,
    summary="Otorgar acceso a sede",
    description="Otorga acceso a un usuario a una sede con un rol específico.",
)
async def grant_access(
    data: UserClinicAccessCreate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserClinicAccessResponse:
    access = await org_svc.grant_clinic_access(
        db=db,
        user_id=data.user_id,
        clinic_id=data.clinic_id,
        role_in_clinic=UserRole(data.role_in_clinic),
    )
    return UserClinicAccessResponse.model_validate(access)


@router.delete(
    "/access/{user_id}/{clinic_id}",
    status_code=204,
    summary="Revocar acceso a sede",
)
async def revoke_access(
    user_id: UUID,
    clinic_id: UUID,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    await org_svc.revoke_clinic_access(db, user_id, clinic_id)
