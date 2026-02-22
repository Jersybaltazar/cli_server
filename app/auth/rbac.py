"""
Definición de permisos RBAC por rol.
Mapea qué acciones puede realizar cada rol.
"""

from app.models.user import UserRole

# ── Permisos por recurso ─────────────────────────────
# Formato: {recurso: {acción: [roles permitidos]}}
PERMISSIONS: dict[str, dict[str, list[UserRole]]] = {
    "organization": {
        "create": [UserRole.SUPER_ADMIN],
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN],
        "update": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN],
        "delete": [UserRole.SUPER_ADMIN],
    },
    "clinic": {
        "create": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN],
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "update": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN],
        "delete": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN],
    },
    "user": {
        "create": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN],
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "update": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN],
        "delete": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN],
    },
    "patient": {
        "create": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "update": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "delete": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN],
    },
    "appointment": {
        "create": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "update": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "delete": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN],
    },
    "medical_record": {
        "create": [UserRole.SUPER_ADMIN, UserRole.DOCTOR],
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR],
        # Receptionist NO puede ver HCE (NTS 139 Cap. VII)
        # No hay update ni delete (INSERT-only)
    },
    "invoice": {
        "create": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.RECEPTIONIST],
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST],
        "void": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN],
    },
    "report": {
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR],
    },
    "audit_log": {
        "read": [UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN],
    },
}


def has_permission(role: UserRole, resource: str, action: str) -> bool:
    """Verifica si un rol tiene permiso para una acción en un recurso."""
    resource_perms = PERMISSIONS.get(resource, {})
    allowed_roles = resource_perms.get(action, [])
    return role in allowed_roles
